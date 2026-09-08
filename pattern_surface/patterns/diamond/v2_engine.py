"""Independent Diamond Pattern Prototype V2 geometry engine.

This module consumes only the serialized Map Faces payload.  It intentionally
does not import the mapping, trimming, approved Diamond, or Prototype engines.
"""

import base64
import json
import math
import zlib

import FreeCAD as App
import Part

from ...common.identifiers import FULL_PREFIX, SCHEMA
from ...common.properties_core import (
    add_bool, add_float, add_integer, add_length, add_string, next_name,
)
from ...common.ownership import organize_derived_object
from ...common.ownership import map_from_selection_object


ALGORITHM = "AUZYRON_DIAMOND_PROTOTYPE_V2_DIRECT_CAD_BVH_NORMAL"
PATTERN_ID = "diamond_prototype_v2"
CONTACT = 0.005
EPSILON = 1.0e-8
MAX_NORMAL_JUMP = 0.35


def _add_chunks(obj, name, payload, group):
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = base64.b64encode(zlib.compress(raw, 9)).decode("ascii")
    chunks = [encoded[index:index + 60000] for index in range(0, len(encoded), 60000)]
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyStringList", name, group)
    setattr(obj, name, chunks)


def _load_chunks(obj, name):
    chunks = list(getattr(obj, name, []) or [])
    if not chunks:
        raise RuntimeError("Objeto {} nao contem {}.".format(obj.Name, name))
    return json.loads(zlib.decompress(base64.b64decode("".join(chunks))).decode("utf-8"))


def _vec(value):
    return App.Vector(float(value[0]), float(value[1]), float(value[2]))


def _xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def _normal(value):
    result = _vec(value)
    if result.Length <= EPSILON:
        return None
    result.normalize()
    return result


def _barycentric(point, triangle):
    (ax, ay), (bx, by), (cx, cy) = triangle
    denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(denominator) <= EPSILON:
        return None
    wa = ((by - cy) * (point[0] - cx) + (cx - bx) * (point[1] - cy)) / denominator
    wb = ((cy - ay) * (point[0] - cx) + (ax - cx) * (point[1] - cy)) / denominator
    return wa, wb, 1.0 - wa - wb


def _map_object(selected):
    return map_from_selection_object(selected)


def _triangles(payload):
    return list(payload.get("carrier_triangles", payload.get("triangles", [])))


def _build_spatial_index(triangles, cell_size):
    bins = {}
    size = max(float(cell_size), 1.0e-6)
    for index, triangle in enumerate(triangles):
        logical = [vertex.get("q") for vertex in triangle.get("v", [])]
        if len(logical) != 3:
            continue
        x0 = math.floor(min(point[0] for point in logical) / size)
        x1 = math.floor(max(point[0] for point in logical) / size)
        y0 = math.floor(min(point[1] for point in logical) / size)
        y1 = math.floor(max(point[1] for point in logical) / size)
        for ix in range(int(x0), int(x1) + 1):
            for iy in range(int(y0), int(y1) + 1):
                bins.setdefault((ix, iy), []).append(index)
    return {"triangles": triangles, "bins": bins, "cell_size": size}


def _clamp_weights(weights):
    """Project barycentric weights onto the triangle simplex."""
    values = [max(0.0, float(value)) for value in weights]
    total = sum(values)
    if total <= EPSILON:
        nearest = max(range(3), key=lambda index: weights[index])
        values = [1.0 if index == nearest else 0.0 for index in range(3)]
        return values
    return [value / total for value in values]


def _interp(table, value, inverse=False):
    pairs = [[row[1], row[0]] for row in table] if inverse else table
    if not pairs:
        return float(value)
    if value <= pairs[0][0]:
        return pairs[0][1]
    if value >= pairs[-1][0]:
        return pairs[-1][1]
    for index in range(1, len(pairs)):
        x0, y0 = pairs[index - 1]
        x1, y1 = pairs[index]
        if value <= x1:
            return y0 + (y1 - y0) * ((value - x0) / max(x1 - x0, EPSILON))
    return pairs[-1][1]


def _direct_project(point, entries, previous_normal=None):
    """Evaluate the real CAD faces before consulting the carrier mesh."""
    candidates = []
    for entry in entries:
        try:
            a, b, c, d, tx, ty = [float(value) for value in entry["transform"]]
            det = a * d - b * c
            if abs(det) <= EPSILON:
                continue
            x, y = point[0] - tx, point[1] - ty
            local_x = (d * x - b * y) / det
            local_y = (-c * x + a * y) / det
            width, height = float(entry["width"]), float(entry["height"])
            if (local_x < -1.0e-6 or local_x > width + 1.0e-6 or
                    local_y < -1.0e-6 or local_y > height + 1.0e-6):
                continue
            rx = local_x / max(width, EPSILON)
            ry = local_y / max(height, EPSILON)
            if entry.get("x_sign", 1) < 0:
                rx = 1.0 - rx
            if entry.get("y_sign", 1) < 0:
                ry = 1.0 - ry
            ratios = {entry["x_axis"]: rx, entry["y_axis"]: ry}
            u0, u1, v0, v1 = [float(value) for value in entry["range"]]
            ru = _interp(entry.get("metric_u", []), ratios["u"], True)
            rv = _interp(entry.get("metric_v", []), ratios["v"], True)
            u, v = u0 + ru * (u1 - u0), v0 + rv * (v1 - v0)
            face = entry.get("face_ref")
            physical = face.valueAt(u, v)
            normal = _normal(face.normalAt(u, v))
            if normal is None:
                continue
            if float(entry.get("normal_sign", 1.0)) < 0.0:
                normal = -normal
            continuity = (1.0 if previous_normal is None else
                          normal.dot(previous_normal))
            margin = min(local_x, width - local_x, local_y, height - local_y)
            candidates.append((margin, continuity, -int(entry.get("index", 0)),
                               physical, normal, entry))
        except Exception:
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda value: value[:3])[3:]


def _project(point, spatial_index, previous_normal=None, allow_extrapolation=False,
             direct_entries=None):
    direct = _direct_project(point, direct_entries or [], previous_normal)
    if direct is not None:
        return direct
    size = spatial_index["cell_size"]
    ix = int(math.floor(point[0] / size))
    iy = int(math.floor(point[1] / size))
    radius = 3 if allow_extrapolation else 1
    candidate_ids = []
    seen = set()
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            for index in spatial_index["bins"].get((ix + dx, iy + dy), []):
                if index not in seen:
                    seen.add(index)
                    candidate_ids.append(index)
    triangles = spatial_index["triangles"]
    candidates = []
    passes = [candidate_ids]
    if allow_extrapolation:
        # Carrier tessellation can leave narrow logical gaps at a BRep seam.
        # Only border nodes get this bounded nearest-triangle recovery; cell
        # centers still use the local indexed candidates exclusively.
        passes.append([index for index in range(len(triangles))
                       if index not in seen])
    for pass_ids in passes:
        for index in pass_ids:
            triangle = triangles[index]
            vertices = triangle.get("v", [])
            if len(vertices) != 3:
                continue
            logical = [vertex.get("q") for vertex in vertices]
            weights = _barycentric(point, logical)
            if weights is None:
                continue
            outside = max(0.0, -min(weights))
            if outside > 0.0 and not allow_extrapolation:
                continue
            if outside > 1.25:
                continue
            effective_weights = (weights if outside <= 2.0e-6
                                  else _clamp_weights(weights))
            projected_logical = [
                sum(vertex[0] * weight
                    for vertex, weight in zip(logical, effective_weights)),
                sum(vertex[1] * weight
                    for vertex, weight in zip(logical, effective_weights)),
            ]
            logical_distance = math.hypot(
                point[0] - projected_logical[0],
                point[1] - projected_logical[1],
            )
            physical = sum(
                (_vec(vertex["p"]) * weight
                 for vertex, weight in zip(vertices, effective_weights)),
                App.Vector(),
            )
            normal = _normal(sum(
                (_vec(vertex.get("n", [0, 0, 1])) * weight
                 for vertex, weight in zip(vertices, effective_weights)),
                App.Vector(),
            ))
            if normal is None:
                continue
            continuity = (1.0 if previous_normal is None
                          else normal.dot(previous_normal))
            if continuity < -0.25:
                continue
            margin = min(weights)
            # Interior candidates always win.  For a border node, prefer the
            # closest logical carrier while retaining normal continuity.
            border_penalty = outside * 0.25
            distance_penalty = 0.05 * logical_distance / size
            candidates.append((continuity - border_penalty - distance_penalty,
                               margin, -index, physical, normal, triangle))
        if candidates:
            break
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1], item[2]))[3:]


def _lattice(bounds, height, extra=0.0, origin=None,
             grid_side=None, grid_height=None):
    x0, x1, y0, y1 = [float(value) for value in bounds]
    # The mapped grid is the authoritative logical chart.  The nominal
    # diamond height is only a fallback for old map payloads that predate the
    # serialized grid dimensions.
    side = float(grid_side if grid_side is not None
                 else 2.0 * height / math.sqrt(3.0))
    row_height = float(grid_height if grid_height is not None else height)
    if side <= EPSILON or row_height <= EPSILON:
        return
    origin_x, origin_y = [float(value) for value in (origin or (0.0, 0.0))]
    row0 = int(math.floor((y0 - extra - origin_y) / row_height))
    row1 = int(math.ceil((y1 + extra - origin_y) / row_height))
    col0 = int(math.floor((x0 - side - extra - origin_x) / side)) - 1
    col1 = int(math.ceil((x1 + side + extra - origin_x) / side)) + 1

    def point(row, col):
        return [origin_x + col * side + (side * 0.5 if row % 2 else 0.0),
                origin_y + row * row_height]

    for row in range(row0, row1):
        for col in range(col0, col1):
            lower_left = point(row, col)
            lower_right = point(row, col + 1)
            upper_left = point(row + 1, col)
            upper_right = point(row + 1, col + 1)
            if row % 2:
                yield "r{}_c{}_up".format(row, col), [lower_left, lower_right, upper_right]
                yield "r{}_c{}_down".format(row, col), [lower_left, upper_right, upper_left]
            else:
                yield "r{}_c{}_up".format(row, col), [lower_left, lower_right, upper_left]
                yield "r{}_c{}_down".format(row, col), [lower_right, upper_right, upper_left]


def _surface_normal(point, spatial_index, cache, hint=None, allow_extrapolation=False,
                    direct_entries=None):
    key = (round(point[0], 7), round(point[1], 7), bool(allow_extrapolation))
    if key not in cache:
        cache[key] = _project(point, spatial_index, hint, allow_extrapolation,
                              direct_entries)
    return cache[key]


def _face(a, b, c):
    if (b - a).cross(c - a).Length <= EPSILON:
        return None
    try:
        return Part.Face(Part.makePolygon([a, b, c, a]))
    except Exception:
        return None


def _overlap_volume(left, right):
    """Return real volume overlap while ignoring tangent contact."""
    try:
        if (left.BoundBox.XMax < right.BoundBox.XMin - CONTACT or
                right.BoundBox.XMax < left.BoundBox.XMin - CONTACT or
                left.BoundBox.YMax < right.BoundBox.YMin - CONTACT or
                right.BoundBox.YMax < left.BoundBox.YMin - CONTACT or
                left.BoundBox.ZMax < right.BoundBox.ZMin - CONTACT or
                right.BoundBox.ZMax < left.BoundBox.ZMin - CONTACT):
            return 0.0
        common = left.common(right)
        return float(common.Volume) if not common.isNull() else 0.0
    except Exception:
        return 0.0


def _cell(canonical, spatial_index, height, relief, cache, source_shapes,
          direct_entries):
    center = [sum(point[0] for point in canonical) / 3.0,
              sum(point[1] for point in canonical) / 3.0]
    center_value = _surface_normal(center, spatial_index, cache)
    if center_value is None:
        return None, "no_surface"
    center_point, center_normal, center_triangle = center_value
    # Keep the proven carrier interpolation on planar patches.  Direct CAD
    # evaluation is reserved for the curved carrier patches where the
    # triangulated chart is the source of the lower-fillet distortion.
    curved_entries = (direct_entries if center_triangle and
                      center_triangle.get("curved", False) else None)
    if curved_entries is not None:
        curved_center = _direct_project(center, curved_entries, center_normal)
        if curved_center is not None:
            center_point, center_normal, center_triangle = curved_center
    samples = [canonical[0], canonical[1], canonical[2], center]
    mapped = []
    normal_spread = 0.0
    previous = center_normal
    for point in samples:
        value = _surface_normal(point, spatial_index, cache, previous, True,
                                curved_entries)
        if value is None:
            return None, "no_node"
        physical, normal, _triangle = value
        if normal.dot(center_normal) < 0.0:
            normal = -normal
        normal_spread = max(normal_spread, 1.0 - max(-1.0, min(1.0, normal.dot(center_normal))))
        mapped.append((physical, normal))
        previous = normal

    # Relief is continuous in the normal spread, not a per-face switch.
    curved_weight = min(1.0, normal_spread / MAX_NORMAL_JUMP)
    local_relief = 1.0 - curved_weight * (1.0 - relief)
    base = [value[0] - value[1] * CONTACT for value in mapped[:3]]
    apex = center_point + center_normal * (height * local_relief)

    shapes = []
    if center_triangle is not None:
        shape = source_shapes.get(center_triangle.get("face"))
        if shape is not None:
            shapes.append(shape)
    for start in base:
        for ratio in (0.35, 0.65):
            probe = start * (1.0 - ratio) + apex * ratio
            if any(shape.isInside(probe, 1.0e-6, False) for shape in shapes):
                return None, "inside_source"

    # Low-curvature cells use the regular subdivided rear lattice from the
    # first prototype.  The fillet keeps the compact local cell below, where
    # the surface-following relief is more important than extra facets.
    if normal_spread < 0.08:
        count = 4
        nodes = {}
        for i in range(count + 1):
            for j in range(count + 1 - i):
                q = [canonical[0][0] +
                     (canonical[1][0] - canonical[0][0]) * i / count +
                     (canonical[2][0] - canonical[0][0]) * j / count,
                     canonical[0][1] +
                     (canonical[1][1] - canonical[0][1]) * i / count +
                     (canonical[2][1] - canonical[0][1]) * j / count]
                value = _surface_normal(q, spatial_index, cache, center_normal,
                                        True, curved_entries)
                if value is None:
                    nodes = None
                    break
                physical, local_normal, _triangle = value
                if local_normal.dot(center_normal) < 0.0:
                    local_normal = -local_normal
                nodes[(i, j)] = physical - local_normal * CONTACT
            if nodes is None:
                break
        if nodes is not None:
            rear_faces = []
            for i in range(count):
                for j in range(count - i):
                    face_a = _face(nodes[(i, j)], nodes[(i, j + 1)], nodes[(i + 1, j)])
                    if face_a is None:
                        nodes = None
                        break
                    rear_faces.append(face_a)
                    if i + j <= count - 2:
                        face_b = _face(nodes[(i + 1, j)], nodes[(i, j + 1)],
                                       nodes[(i + 1, j + 1)])
                        if face_b is None:
                            nodes = None
                            break
                        rear_faces.append(face_b)
                if nodes is None:
                    break
            if nodes is not None:
                boundary_keys = ([(i, 0) for i in range(count + 1)] +
                                 [(count - i, i) for i in range(1, count + 1)] +
                                 [(0, count - i) for i in range(1, count)])
                boundary = [nodes[key] for key in boundary_keys]
                boundary_logical = []
                for key_i, key_j in boundary_keys:
                    boundary_logical.append([
                        canonical[0][0] +
                        (canonical[1][0] - canonical[0][0]) * key_i / count +
                        (canonical[2][0] - canonical[0][0]) * key_j / count,
                        canonical[0][1] +
                        (canonical[1][1] - canonical[0][1]) * key_i / count +
                        (canonical[2][1] - canonical[0][1]) * key_j / count,
                    ])
                side_faces = []
                side_steps = 3
                for index, start in enumerate(boundary):
                    end = boundary[(index + 1) % len(boundary)]
                    start_q = boundary_logical[index]
                    end_q = boundary_logical[(index + 1) % len(boundary)]
                    previous_start, previous_end = start, end
                    for step in range(1, side_steps + 1):
                        ratio = float(step) / side_steps
                        if step == side_steps:
                            face = _face(previous_start, previous_end, apex)
                            if face is None:
                                side_faces = []
                                break
                            side_faces.append(face)
                            break
                        q_start = [start_q[0] * (1.0 - ratio) + center[0] * ratio,
                                   start_q[1] * (1.0 - ratio) + center[1] * ratio]
                        q_end = [end_q[0] * (1.0 - ratio) + center[0] * ratio,
                                 end_q[1] * (1.0 - ratio) + center[1] * ratio]
                        value_start = _surface_normal(
                            q_start, spatial_index, cache, center_normal, True,
                            curved_entries)
                        value_end = _surface_normal(
                            q_end, spatial_index, cache, center_normal, True,
                            curved_entries)
                        if value_start is None or value_end is None:
                            side_faces = []
                            break
                        point_start, normal_start, _ = value_start
                        point_end, normal_end, _ = value_end
                        if normal_start.dot(center_normal) < 0.0:
                            normal_start = -normal_start
                        if normal_end.dot(center_normal) < 0.0:
                            normal_end = -normal_end
                        normal_start = _normal(normal_start * (1.0 - ratio) +
                                               center_normal * ratio)
                        normal_end = _normal(normal_end * (1.0 - ratio) +
                                             center_normal * ratio)
                        if normal_start is None or normal_end is None:
                            side_faces = []
                            break
                        current_start = point_start + normal_start * (
                            height * ratio - CONTACT * (1.0 - ratio))
                        current_end = point_end + normal_end * (
                            height * ratio - CONTACT * (1.0 - ratio))
                        face_a = _face(previous_start, previous_end, current_end)
                        face_b = _face(previous_start, current_end, current_start)
                        if face_a is None or face_b is None:
                            side_faces = []
                            break
                        side_faces.extend((face_a, face_b))
                        previous_start, previous_end = current_start, current_end
                    if not side_faces:
                        break
                if side_faces:
                    try:
                        shell = Part.makeShell(rear_faces + side_faces)
                        solid = Part.makeSolid(shell)
                        if (not shell.isNull() and shell.isClosed() and
                                not solid.isNull() and solid.isValid() and
                                len(solid.Solids) == 1):
                            if not any(_overlap_volume(solid, shape) > 1.0e-5
                                       for shape in shapes):
                                return (solid, {"canonical": canonical,
                                                "apex": _xyz(apex),
                                                "normal_spread": normal_spread,
                                                "relief": local_relief,
                                                "construction": "subdivided"}), None
                    except Exception:
                        pass

    faces = [_face(base[0], base[2], base[1]),
             _face(base[0], base[1], apex),
             _face(base[1], base[2], apex),
             _face(base[2], base[0], apex)]
    if any(face is None for face in faces):
        return None, "degenerate"
    try:
        shell = Part.makeShell(faces)
        if shell.isNull() or not shell.isClosed():
            return None, "open_shell"
        solid = Part.makeSolid(shell)
        if solid.isNull() or not solid.isValid() or len(solid.Solids) != 1:
            return None, "invalid_solid"
        if any(_overlap_volume(solid, shape) > 1.0e-5
               for shape in shapes):
            return None, "inside_source"
        return (solid, {"canonical": canonical, "apex": _xyz(apex),
                        "normal_spread": normal_spread,
                        "relief": local_relief,
                        "construction": "local"}), None
    except Exception:
        return None, "solid_exception"


def create_pattern(selected, parameters):
    document = getattr(selected, "Document", None) or App.ActiveDocument
    if document is None:
        raise RuntimeError("Abra um documento antes de executar o Diamond Pattern Prototype V2.")
    map_object = _map_object(selected)
    if map_object is None:
        raise RuntimeError("Selecione um objeto Map Faces ou Mapped Surface.")
    payload = _load_chunks(map_object, "MapPayloadChunks")
    if payload.get("schema") and payload.get("schema") != SCHEMA:
        raise RuntimeError("O objeto selecionado possui um schema de mapeamento incompatível.")
    bounds = payload.get("bounds")
    triangles = _triangles(payload)
    if not bounds or not triangles:
        raise RuntimeError("O Mapped Surface não contém uma superfície física válida.")

    diamond_height = float(parameters["diamond_height"])
    pyramid_height = float(parameters["pyramid_height"])
    relief = min(1.0, max(0.05, float(parameters["transition_relief"])))
    if diamond_height <= 0.0 or pyramid_height <= 0.0:
        raise RuntimeError("As alturas do Prototype V2 devem ser positivas.")

    source_shapes = {}
    direct_entries = []
    for record in payload.get("faces", []):
        obj = document.getObject(record.get("object"))
        if obj is not None and getattr(obj, "Shape", None) is not None:
            source_shapes[record.get("index")] = obj.Shape
            try:
                entry = dict(record)
                entry["face_ref"] = obj.getSubObject(record["sub"])
                direct_entries.append(entry)
            except Exception:
                pass

    spatial_index = _build_spatial_index(triangles, diamond_height)
    cache = {}
    solids, records, rejected = [], [], {}
    grid = payload.get("grid", {}) or {}
    grid_origin = grid.get("origin", [0.0, 0.0])
    if len(grid_origin) != 2:
        grid_origin = [0.0, 0.0]
    grid_side = grid.get("column_width")
    grid_height = grid.get("row_height")
    try:
        grid_side = float(grid_side) if grid_side is not None else None
        grid_height = float(grid_height) if grid_height is not None else None
    except (TypeError, ValueError):
        grid_side, grid_height = None, None
    for cell_id, canonical in _lattice(
            bounds, diamond_height, diamond_height, grid_origin,
            grid_side, grid_height):
        center = [sum(point[0] for point in canonical) / 3.0,
                  sum(point[1] for point in canonical) / 3.0]
        if not (bounds[0] - diamond_height <= center[0] <= bounds[1] + diamond_height and
                bounds[2] - diamond_height <= center[1] <= bounds[3] + diamond_height):
            continue
        result, reason = _cell(canonical, spatial_index, pyramid_height, relief,
                               cache, source_shapes, direct_entries)
        if result is None:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        solid, record = result
        if any(_overlap_volume(solid, previous) > 1.0e-5
               for previous in solids):
            rejected["overlap_neighbor"] = rejected.get("overlap_neighbor", 0) + 1
            continue
        solids.append(solid)
        record["id"] = cell_id
        records.append(record)
    if not solids:
        raise RuntimeError("O Diamond Pattern Prototype V2 não gerou sólidos válidos.")

    name = next_name(document, FULL_PREFIX)
    run = document.addObject("PartDesign::Feature", name)
    run.Label = "Diamond Pattern Prototype V2 {}".format(name.rsplit("_", 1)[-1])
    run.Shape = Part.makeCompound(solids)
    add_string(run, "DiamondPatternVersion", "Diamond Pattern Prototype V2", "Pattern Surface")
    add_string(run, "DiamondPatternAlgorithm", ALGORITHM, "Pattern Surface")
    add_string(run, "PatternId", PATTERN_ID, "Pattern Surface")
    add_string(run, "PatternMapSource", map_object.Name, "Pattern Surface")
    add_length(run, "PatternHeight", pyramid_height, "Pattern Surface")
    add_length(run, "DiamondHeight", diamond_height, "Pattern Surface")
    add_float(run, "TransitionRelief", relief, "Pattern Surface")
    add_bool(run, "PrototypeOnly", True, "Pattern Surface")
    add_integer(run, "AcceptedCellCount", len(records), "Pattern Surface")
    add_integer(run, "RejectedCellCount", sum(rejected.values()), "Pattern Surface")
    add_string(run, "RejectedCellReasons", ";".join(
        "{}={}".format(key, value) for key, value in sorted(rejected.items())), "Pattern Surface")
    _add_chunks(run, "DiamondPatternCellChunks", {
        "schema": SCHEMA, "version": 1, "pattern_id": PATTERN_ID,
        "map_source": map_object.Name, "map_schema": payload.get("schema"),
        "parameters": {"diamond_height": diamond_height,
                       "pyramid_height": pyramid_height,
                       "transition_relief": relief,
                       "cell_gap": float(parameters.get("cell_gap", 0.0))},
        "cells": records, "rejected_cells": rejected,
        "generation": {"algorithm": ALGORITHM, "accepted": len(records)},
    }, "Pattern Surface")
    organize_derived_object(run, map_object)
    document.recompute()
    App.Console.PrintMessage(
        "diamond_v2: run={} direct_faces={} accepted={} rejected={} reasons={}\n".format(
            name, len(direct_entries), len(records), sum(rejected.values()), rejected))
    return run
