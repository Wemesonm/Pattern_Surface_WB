"""Shared geometric core for the Wrap Faces V4 FreeCAD macros.

This module intentionally contains no automatic execution.  The three FCMacro
entry points call the public create_wrap/create_full_pattern/create_cut methods.
"""

import base64
import json
import math
import traceback
import zlib

import FreeCAD as App
import FreeCADGui as Gui
import Part


SCHEMA = "WRAP_CARRIER_V4"
WRAP_PREFIX = "DiamondSurfaceWrap_V4"
FULL_PREFIX = "DiamondPatternFullFromWrap_V4"
CUT_PREFIX = "DiamondPatternCutFromWrap_V4"
BUILD_ID = "Pattern_Surface_WB_0.1.4_map_generic_grid_candidate_2026-08-16"
GRID_HEIGHT = 12.0
GRID_SIDE = 2.0 * GRID_HEIGHT / math.sqrt(3.0)
DEFAULT_MAP_COLUMN_WIDTH = GRID_SIDE
DEFAULT_MAP_ROW_HEIGHT = GRID_HEIGHT
DEFAULT_MAP_CLOSURE_TOLERANCE = 0.05
DEFAULT_PATTERN_HEIGHT = 1.0
CONTACT = 0.005
MAX_EDGE = 1.5
SAG = 0.05
EDGE_TOL = 1.0e-5
LOGICAL_TOL = 2.0e-4
MAX_CYCLE_ADJUST = 0.05
CELL_SUBDIVISIONS = 8
EXTERNAL_ROW_LIMIT = max(GRID_SIDE, GRID_HEIGHT) * 1.10
EXTERNAL_ENDPOINT_LIMIT = GRID_SIDE * 0.25
EXTERNAL_INWARD_TOL = GRID_HEIGHT * 0.05
MAX_LATTICE_STEP = (GRID_SIDE / CELL_SUBDIVISIONS) * 2.75
MAX_CANONICAL_EDGE = GRID_SIDE * 1.70
CUT_FRONT_MARGIN = 1.25
CUT_REAR_MARGIN = 1.25


def console(message):
    App.Console.PrintMessage(str(message) + "\n")


def warn(message):
    App.Console.PrintWarning(str(message) + "\n")


def fail(message):
    App.Console.PrintError(str(message) + "\n")
    raise RuntimeError(message)


def v3(value):
    return App.Vector(float(value[0]), float(value[1]), float(value[2]))


def xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def norm(value):
    value = App.Vector(value.x, value.y, value.z)
    if value.Length <= 1.0e-12:
        return None
    value.normalize()
    return value


def is_valid_shape(shape):
    if shape is None:
        return False
    try:
        if shape.isNull():
            return False
    except Exception:
        return False
    try:
        if len(list(shape.Solids)) < 1:
            return False
    except Exception:
        return False
    try:
        return bool(shape.isValid())
    except Exception:
        return True


def qkey2(point, scale=100000.0):
    return (int(round(point[0] * scale)), int(round(point[1] * scale)))


def qkey3(point, scale=100000.0):
    return (int(round(point.x * scale)), int(round(point.y * scale)), int(round(point.z * scale)))


def add_string(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", name, group)
    setattr(obj, name, str(value))


def add_bool(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyBool", name, group)
    setattr(obj, name, bool(value))


def add_integer(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyInteger", name, group)
    setattr(obj, name, int(value))


def add_string_list(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyStringList", name, group)
    setattr(obj, name, [str(item) for item in value])


def add_vector(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyVector", name, group)
    setattr(obj, name, App.Vector(float(value[0]), float(value[1]), 0.0))


def add_length(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyLength", name, group)
    setattr(obj, name, float(value))


def length_value(value, default=DEFAULT_PATTERN_HEIGHT):
    try:
        return float(value.Value)
    except AttributeError:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)


def add_chunks(obj, name, payload, group):
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = base64.b64encode(zlib.compress(raw, 9)).decode("ascii")
    chunks = [encoded[index:index + 60000] for index in range(0, len(encoded), 60000)]
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyStringList", name, group)
    setattr(obj, name, chunks)


def load_chunks(obj, name):
    chunks = list(getattr(obj, name, []) or [])
    if not chunks:
        fail("Objeto {} nao contem {}.".format(obj.Name, name))
    return json.loads(zlib.decompress(base64.b64decode("".join(chunks))).decode("utf-8"))


def next_name(doc, prefix):
    index = 1
    while doc.getObject("{}_Run_{:03d}".format(prefix, index)) is not None:
        index += 1
    return "{}_Run_{:03d}".format(prefix, index)


def outer_edges(face):
    try:
        return list(face.OuterWire.OrderedEdges)
    except Exception:
        return list(face.OuterWire.Edges)


def endpoints(edge):
    vertices = list(edge.Vertexes)
    if len(vertices) >= 2:
        return vertices[0].Point, vertices[-1].Point
    points = edge.discretize(Number=2)
    return points[0], points[-1]


def same_edge(left, right):
    a0, a1 = endpoints(left)
    b0, b1 = endpoints(right)
    return ((a0.distanceToPoint(b0) <= EDGE_TOL and a1.distanceToPoint(b1) <= EDGE_TOL) or
            (a0.distanceToPoint(b1) <= EDGE_TOL and a1.distanceToPoint(b0) <= EDGE_TOL))


def shared_edge(left, right):
    for edge_left in outer_edges(left):
        for edge_right in outer_edges(right):
            if same_edge(edge_left, edge_right):
                return edge_left, edge_right
    return None, None


def selected_faces():
    entries = []
    seen = set()
    for selection in Gui.Selection.getSelectionEx():
        obj = selection.Object
        names = list(selection.SubElementNames or [])
        shapes = list(selection.SubObjects or [])
        picked = None
        try:
            picked = selection.PickedPoints[0]
        except Exception:
            pass
        for pos, shape in enumerate(shapes):
            if getattr(shape, "ShapeType", "") != "Face":
                continue
            name = names[pos] if pos < len(names) else "Face{}".format(pos + 1)
            key = (obj.Name, name)
            if key in seen:
                continue
            seen.add(key)
            entries.append({"object": obj, "sub": name, "face": shape, "picked": picked})
    if not entries:
        fail("Selecione uma ou mais faces antes de executar Wrap Faces V4.")
    entries.sort(key=lambda item: (item["object"].Name, item["sub"]))
    for index, entry in enumerate(entries):
        entry["index"] = index
    return entries


def source_solid(entry):
    shape = getattr(entry["object"], "Shape", None)
    if shape is None or shape.isNull() or not list(shape.Solids):
        fail("{} precisa pertencer a um solido fechado valido.".format(entry["sub"]))
    return shape


def surface_period(surface, axis):
    periodic = getattr(surface, "is{}Periodic".format(axis.upper()), None)
    try:
        if not periodic or not periodic():
            return None
        value = getattr(surface, "{}Period".format(axis.upper()))
        return float(value() if callable(value) else value)
    except Exception:
        return None


def unwrap_parameter(value, lower, upper, period):
    if period is None or period <= 1.0e-12:
        return value
    center = (lower + upper) * 0.5
    return value + round((center - value) / period) * period


def surface_parameters(face, point, bounds=None):
    u, v = face.Surface.parameter(point)
    u0, u1, v0, v1 = bounds or face.ParameterRange
    u = unwrap_parameter(u, u0, u1, surface_period(face.Surface, "u"))
    v = unwrap_parameter(v, v0, v1, surface_period(face.Surface, "v"))
    return u, v


def parameter_range(face):
    native = list(face.ParameterRange)
    values = []
    for edge in outer_edges(face):
        length = max(float(getattr(edge, "Length", 0.0)), 0.01)
        for point in edge.discretize(Number=max(3, int(math.ceil(length / MAX_EDGE)) + 1)):
            try:
                values.append(surface_parameters(face, point, native))
            except Exception:
                pass
    if values:
        us = [item[0] for item in values]
        vs = [item[1] for item in values]
        if max(us) - min(us) > 1.0e-10 and max(vs) - min(vs) > 1.0e-10:
            return [min(us), max(us), min(vs), max(vs)]
    return list(face.ParameterRange)


def face_center(face):
    try:
        return face.CenterOfMass
    except Exception:
        u0, u1, v0, v1 = face.ParameterRange
        return face.valueAt((u0 + u1) * 0.5, (v0 + v1) * 0.5)


def outward(entry):
    face = entry["face"]
    solid = source_solid(entry)
    samples = []
    if entry.get("picked") is not None:
        samples.append(entry["picked"])
    samples.append(face_center(face))
    votes = []
    for point in samples:
        try:
            u, v = face.Surface.parameter(point)
            base = face.valueAt(u, v)
            normal = norm(face.normalAt(u, v))
        except Exception:
            continue
        if normal is None:
            continue
        for distance in (0.02, 0.08, 0.25):
            plus = bool(solid.isInside(base + normal * distance, 1.0e-6, False))
            minus = bool(solid.isInside(base - normal * distance, 1.0e-6, False))
            if plus != minus:
                votes.append(-1.0 if plus else 1.0)
    if votes:
        positive = sum(1 for value in votes if value > 0.0)
        negative = sum(1 for value in votes if value < 0.0)
        if positive != negative:
            if positive and negative:
                warn("Direcao externa ambigua em {}; usando maioria dos testes.".format(entry["sub"]))
            return 1.0 if positive > negative else -1.0
    warn("Direcao externa ambigua em {}; usando normal nativa e alinhamento por vizinhos.".format(entry["sub"]))
    return 1.0


def axis_length_table(face, bounds, axis, samples=64):
    u0, u1, v0, v1 = bounds
    fixed = (v0 + v1) * 0.5 if axis == "u" else (u0 + u1) * 0.5
    table = [(0.0, 0.0)]
    total = 0.0
    previous = None
    for index in range(samples + 1):
        ratio = float(index) / samples
        point = face.valueAt(u0 + (u1 - u0) * ratio, fixed) if axis == "u" else face.valueAt(fixed, v0 + (v1 - v0) * ratio)
        if previous is not None:
            total += point.distanceToPoint(previous)
        table.append((ratio, total))
        previous = point
    if total <= 1.0e-9:
        fail("Metrica degenerada na face.")
    return [[a, b / total] for a, b in table], total


def interp(table, value, inverse=False):
    pairs = [[row[1], row[0]] for row in table] if inverse else table
    if value <= pairs[0][0]:
        return pairs[0][1]
    if value >= pairs[-1][0]:
        return pairs[-1][1]
    for index in range(1, len(pairs)):
        x0, y0 = pairs[index - 1]
        x1, y1 = pairs[index]
        if value <= x1:
            return y0 + (y1 - y0) * ((value - x0) / max(x1 - x0, 1.0e-12))
    return pairs[-1][1]


def tangent(face, bounds, axis):
    u0, u1, v0, v1 = bounds
    u = (u0 + u1) * 0.5
    v = (v0 + v1) * 0.5
    du = max(abs(u1 - u0) * 1.0e-4, 1.0e-8)
    dv = max(abs(v1 - v0) * 1.0e-4, 1.0e-8)
    if axis == "u":
        return norm(face.valueAt(min(u1, u + du), v) - face.valueAt(max(u0, u - du), v))
    return norm(face.valueAt(u, min(v1, v + dv)) - face.valueAt(u, max(v0, v - dv)))


def orient_entry(entry):
    face = entry["face"]
    bounds = parameter_range(face)
    entry["range"] = bounds
    table_u, length_u = axis_length_table(face, bounds, "u")
    table_v, length_v = axis_length_table(face, bounds, "v")
    entry["metric_u"], entry["metric_v"] = table_u, table_v
    entry["length_u"], entry["length_v"] = length_u, length_v
    tu, tv = tangent(face, bounds, "u"), tangent(face, bounds, "v")
    center = face_center(face)
    normal = norm(face.normalAt(*face.Surface.parameter(center)))
    up = App.Vector(0, 1, 0) if normal is not None and abs(normal.z) > 0.85 else App.Vector(0, 0, 1)
    choices = [(abs(tu.dot(up)), "u", 1.0 if tu.dot(up) >= 0 else -1.0),
               (abs(tv.dot(up)), "v", 1.0 if tv.dot(up) >= 0 else -1.0)]
    choices.sort(reverse=True)
    y_axis, y_sign = choices[0][1], choices[0][2]
    x_axis = "v" if y_axis == "u" else "u"
    tx = tv if x_axis == "v" else tu
    # A deterministic handedness removes selection-order dependence.
    reference = up.cross(normal) if normal is not None else App.Vector(1, 0, 0)
    x_sign = 1.0 if tx.dot(reference) >= 0 else -1.0
    entry["x_axis"], entry["y_axis"] = x_axis, y_axis
    entry["x_sign"], entry["y_sign"] = x_sign, y_sign
    entry["width"] = length_v if x_axis == "v" else length_u
    entry["height"] = length_v if y_axis == "v" else length_u
    entry["normal_sign"] = outward(entry)


def edge_fraction(edge, point):
    samples = edge_samples(edge, max(MAX_EDGE, edge.Length / 48.0))
    if len(samples) < 2:
        return 0.0
    total = 0.0
    lengths = [0.0]
    for index in range(1, len(samples)):
        total += samples[index].distanceToPoint(samples[index - 1])
        lengths.append(total)
    if total <= 1.0e-9:
        return 0.0
    best = None
    for index in range(1, len(samples)):
        a, b = samples[index - 1], samples[index]
        ab = b - a
        length2 = ab.dot(ab)
        if length2 <= 1.0e-12:
            continue
        ratio = max(0.0, min(1.0, (point - a).dot(ab) / length2))
        projected = a + ab * ratio
        distance = point.distanceToPoint(projected)
        along = lengths[index - 1] + math.sqrt(length2) * ratio
        candidate = (distance, along / total)
        if best is None or candidate[0] < best[0]:
            best = candidate
    return best[1] if best is not None else 0.0


def local_xy_raw(entry, point):
    face = entry["face"]
    u0, u1, v0, v1 = entry["range"]
    u, v = surface_parameters(face, point, entry["range"])
    ru = interp(entry["metric_u"], (u - u0) / (u1 - u0))
    rv = interp(entry["metric_v"], (v - v0) / (v1 - v0))
    values = {"u": ru, "v": rv}
    x = values[entry["x_axis"]]
    y = values[entry["y_axis"]]
    if entry["x_sign"] < 0:
        x = 1.0 - x
    if entry["y_sign"] < 0:
        y = 1.0 - y
    return [x * entry["width"], y * entry["height"]]


def local_xy(entry, point):
    for seam in entry.get("seam_overrides", []):
        if point_on_edge(point, seam["edge"], 5.0e-4):
            ratio = edge_fraction(seam["edge"], point)
            return [seam["qa"][0] + (seam["qb"][0] - seam["qa"][0]) * ratio,
                    seam["qa"][1] + (seam["qb"][1] - seam["qa"][1]) * ratio]
    return local_xy_raw(entry, point)


def local_uv(entry, local):
    rx = local[0] / entry["width"]
    ry = local[1] / entry["height"]
    if entry["x_sign"] < 0:
        rx = 1.0 - rx
    if entry["y_sign"] < 0:
        ry = 1.0 - ry
    ratios = {entry["x_axis"]: rx, entry["y_axis"]: ry}
    ru = interp(entry["metric_u"], ratios["u"], True)
    rv = interp(entry["metric_v"], ratios["v"], True)
    u0, u1, v0, v1 = entry["range"]
    return u0 + ru * (u1 - u0), v0 + rv * (v1 - v0)


def apply_transform(entry, local):
    matrix = entry["transform"]
    return [matrix[0] * local[0] + matrix[1] * local[1] + matrix[4],
            matrix[2] * local[0] + matrix[3] * local[1] + matrix[5]]


def invert_transform(entry, logical):
    a, b, c, d, tx, ty = entry["transform"]
    det = a * d - b * c
    if abs(det) <= 1.0e-12:
        return None
    x, y = logical[0] - tx, logical[1] - ty
    return [(d * x - b * y) / det, (-c * x + a * y) / det]


def point_from_logical(entry, logical):
    local = invert_transform(entry, logical)
    if local is None:
        return None
    u, v = local_uv(entry, local)
    try:
        point = entry["face"].valueAt(u, v)
        normal = norm(entry["face"].normalAt(u, v)) * entry["normal_sign"]
        return point, normal
    except Exception:
        return None


def edge_samples(edge, spacing=MAX_EDGE):
    count = max(3, int(math.ceil(max(edge.Length, spacing) / spacing)) + 1)
    return list(edge.discretize(Number=count))


def apply_matrix(matrix, local):
    return [matrix[0] * local[0] + matrix[1] * local[1] + matrix[4],
            matrix[2] * local[0] + matrix[3] * local[1] + matrix[5]]


def aligned_edge_samples(left_edge, right_edge):
    ppoints = edge_samples(left_edge, max(MAX_EDGE, left_edge.Length / 16.0))
    tpoints = edge_samples(right_edge, max(MAX_EDGE, right_edge.Length / 16.0))
    if ppoints[0].distanceToPoint(tpoints[0]) > ppoints[0].distanceToPoint(tpoints[-1]):
        tpoints.reverse()
    return ppoints, tpoints


def seam_limit(left_entry, right_entry, left_edge, right_edge):
    limit = 0.05
    if (not isinstance(left_entry["face"].Surface, Part.Plane) or
            not isinstance(right_entry["face"].Surface, Part.Plane)):
        limit = max(limit, min(left_edge.Length, right_edge.Length) * 0.35)
    return limit


def neighbor_transform_candidates(placed, target, placed_edge, target_edge):
    ppoints, tpoints = aligned_edge_samples(placed_edge, target_edge)
    p0 = apply_transform(placed, local_xy_raw(placed, ppoints[0]))
    p1 = apply_transform(placed, local_xy_raw(placed, ppoints[-1]))
    t0 = local_xy_raw(target, tpoints[0])
    t1 = local_xy_raw(target, tpoints[-1])
    sx, sy = t1[0] - t0[0], t1[1] - t0[1]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    sl, dl = math.hypot(sx, sy), math.hypot(dx, dy)
    curved_seam = (not isinstance(placed["face"].Surface, Part.Plane) or
                   not isinstance(target["face"].Surface, Part.Plane))
    if sl <= 1.0e-8 or dl <= 1.0e-8:
        return []
    metric_error = abs(sl - dl) / max(sl, dl)
    if metric_error > 0.05 and not curved_seam:
        return []
    tangent_scale = dl / sl if curved_seam else 1.0
    if curved_seam and abs(dl - sl) > 0.05:
        console("wrap_v4: emenda_curva_escala_tangencial {} <-> {} sl={:.4f} dl={:.4f} escala={:.6f}".format(
            placed["sub"], target["sub"], sl, dl, tangent_scale))
    # Map the target seam basis onto the placed seam basis.  Curved strips can
    # have a different logical length when their metric is sampled away from
    # the shared boundary (for example, a toroidal fillet with changing
    # radius).  Scale only along the seam; preserving the perpendicular basis
    # keeps an already aligned side seam unchanged.
    sux, suy = sx / sl, sy / sl
    dux, duy = dx / dl, dy / dl
    direct = [tangent_scale * dux * sux + duy * suy,
              tangent_scale * dux * suy - duy * sux,
              tangent_scale * duy * sux - dux * suy,
              tangent_scale * duy * suy + dux * sux]
    reflected = [tangent_scale * dux * sux - duy * suy,
                 tangent_scale * dux * suy + duy * sux,
                 tangent_scale * duy * sux + dux * suy,
                 tangent_scale * duy * suy - dux * sux]
    candidates = []
    placed_center = apply_transform(placed, [placed["width"] * 0.5, placed["height"] * 0.5])
    for linear in (direct, reflected):
        tx = p0[0] - linear[0] * t0[0] - linear[1] * t0[1]
        ty = p0[1] - linear[2] * t0[0] - linear[3] * t0[1]
        matrix = linear + [tx, ty]
        center = apply_matrix(matrix, [target["width"] * 0.5, target["height"] * 0.5])
        seam_cross_a = dx * (placed_center[1] - p0[1]) - dy * (placed_center[0] - p0[0])
        seam_cross_b = dx * (center[1] - p0[1]) - dy * (center[0] - p0[0])
        side_penalty = 0.0 if seam_cross_a * seam_cross_b < 0 else 1000.0
        candidates.append((side_penalty, matrix))
    return candidates


def seam_matrix_error(placed, target, placed_edge, target_edge, matrix):
    ppoints, tpoints = aligned_edge_samples(placed_edge, target_edge)
    count = min(len(ppoints), len(tpoints))
    if count <= 0:
        return None
    errors = []
    for index in range(count):
        pi = int(round(index * (len(ppoints) - 1) / max(count - 1, 1)))
        ti = int(round(index * (len(tpoints) - 1) / max(count - 1, 1)))
        lp = apply_transform(placed, local_xy_raw(placed, ppoints[pi]))
        lt = apply_matrix(matrix, local_xy_raw(target, tpoints[ti]))
        errors.append(math.hypot(lp[0] - lt[0], lp[1] - lt[1]))
    return max(errors) if errors else None


def fit_neighbor_to_constraints(target, constraints):
    """Place a face by minimizing error against every already positioned seam."""
    if not constraints:
        return None
    if len(constraints) == 1:
        placed, placed_edge, target_edge = constraints[0]
        candidates = neighbor_transform_candidates(placed, target, placed_edge, target_edge)
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        target["transform"] = candidates[0][1]
        curved_seam = (not isinstance(placed["face"].Surface, Part.Plane) or
                       not isinstance(target["face"].Surface, Part.Plane))
        if curved_seam:
            return 0.0 if candidates[0][0] < 1000.0 else candidates[0][0]
        error = seam_matrix_error(placed, target, placed_edge, target_edge, candidates[0][1])
        return error
    candidates = []
    seen = set()
    for placed, placed_edge, target_edge in constraints:
        for side_penalty, matrix in neighbor_transform_candidates(placed, target, placed_edge, target_edge):
            key = tuple(round(value, 8) for value in matrix)
            if key in seen:
                continue
            seen.add(key)
            max_error = 0.0
            total_error = side_penalty
            valid = True
            for other, other_edge, this_edge in constraints:
                error = seam_matrix_error(other, target, other_edge, this_edge, matrix)
                if error is None:
                    valid = False
                    break
                max_error = max(max_error, error)
                total_error += error
            if valid:
                candidates.append((total_error, max_error, matrix))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    target["transform"] = candidates[0][2]
    return candidates[0][1]


def fit_neighbor(placed, target, placed_edge, target_edge):
    return fit_neighbor_to_constraints(target, [(placed, placed_edge, target_edge)])


def build_graph(entries):
    graph = {entry["index"]: [] for entry in entries}
    shared = []
    for pos, left in enumerate(entries):
        for right in entries[pos + 1:]:
            edge_left, edge_right = shared_edge(left["face"], right["face"])
            if edge_left is None:
                continue
            graph[left["index"]].append((right["index"], edge_left, edge_right))
            graph[right["index"]].append((left["index"], edge_right, edge_left))
            shared.append((left["index"], right["index"]))
    return graph, shared


def signed_normal_at(entry, point):
    try:
        u, v = entry["face"].Surface.parameter(point)
        normal = norm(entry["face"].normalAt(u, v))
        return normal * entry["normal_sign"] if normal is not None else None
    except Exception:
        return None


def edge_midpoint(edge):
    points = edge.discretize(Number=3)
    return points[len(points) // 2]


def align_connected_normals(entries, graph):
    """Keep adjacent selected faces on the same physical outside side."""
    by_index = {entry["index"]: entry for entry in entries}
    pending = set(by_index)
    flips = 0
    while pending:
        root_index = min(pending, key=lambda index: (
            0 if isinstance(by_index[index]["face"].Surface, Part.Plane) else 1,
            -float(by_index[index]["face"].Area),
            by_index[index]["sub"]))
        pending.remove(root_index)
        queue = [root_index]
        while queue:
            current_index = queue.pop(0)
            current = by_index[current_index]
            for neighbor_index, current_edge, neighbor_edge in graph[current_index]:
                if neighbor_index not in pending:
                    continue
                neighbor = by_index[neighbor_index]
                normal_a = signed_normal_at(current, edge_midpoint(current_edge))
                normal_b = signed_normal_at(neighbor, edge_midpoint(neighbor_edge))
                if normal_a is not None and normal_b is not None and normal_a.dot(normal_b) < -0.05:
                    neighbor["normal_sign"] *= -1.0
                    flips += 1
                pending.remove(neighbor_index)
                queue.append(neighbor_index)
    if flips:
        console("wrap_v4: normais_conectadas_invertidas={}".format(flips))


def components(entries, graph):
    by_index = {entry["index"]: entry for entry in entries}
    pending = set(by_index)
    result = []
    while pending:
        root = min(pending)
        pending.remove(root)
        queue, group = [root], []
        while queue:
            current = queue.pop(0)
            group.append(by_index[current])
            for neighbor, _a, _b in graph[current]:
                if neighbor in pending:
                    pending.remove(neighbor)
                    queue.append(neighbor)
        result.append(group)
    return result


def transformed_entry_bounds(entry):
    points = []
    for edge in outer_edges(entry["face"]):
        for point in edge_samples(edge, max(MAX_EDGE, edge.Length / 24.0)):
            points.append(apply_transform(entry, local_xy(entry, point)))
    return [min(point[0] for point in points), max(point[0] for point in points),
            min(point[1] for point in points), max(point[1] for point in points)]


def snap_lower_curved_strips_to_grid(group):
    bounds_by_entry = {entry["index"]: transformed_entry_bounds(entry) for entry in group}
    component_min_y = min(bounds[2] for bounds in bounds_by_entry.values())
    snapped = 0
    for entry in group:
        if isinstance(entry["face"].Surface, Part.Plane):
            continue
        bounds = bounds_by_entry[entry["index"]]
        height = bounds[3] - bounds[2]
        if bounds[2] > component_min_y + MAX_EDGE:
            continue
        if height > GRID_HEIGHT * 1.25:
            continue
        target = math.floor(bounds[0] / GRID_HEIGHT + 1.0e-9) * GRID_HEIGHT
        delta = target - bounds[0]
        if abs(delta) <= MAX_EDGE and abs(delta) > 1.0e-6:
            entry["transform"][4] += delta
            snapped += 1
            console("wrap_v4: faixa_curva_inferior_snap_grid {} dx={:.4f} x0={:.4f}->{:.4f}".format(
                entry["sub"], delta, bounds[0], target))
    return snapped


def position_components(entries, graph):
    by_index = {entry["index"]: entry for entry in entries}
    for entry in entries:
        entry["atlas_seams"] = set()
    groups = components(entries, graph)
    x_offset = 0.0
    for component_index, group in enumerate(groups):
        # Anchor on the largest planar patch whenever possible.  Anchoring on
        # a small fillet makes its short parameter direction the reference for
        # the whole atlas and amplifies metric error in every following face.
        root = min(group, key=lambda item: (
            0 if isinstance(item["face"].Surface, Part.Plane) else 1,
            -float(item["face"].Area),
            face_center(item["face"]).z,
            face_center(item["face"]).x,
            face_center(item["face"]).y,
            item["sub"]))
        root["transform"] = [1.0, 0.0, 0.0, 1.0, x_offset, 0.0]
        root["component"] = component_index
        queue = [root["index"]]
        visited = {root["index"]}
        while queue:
            current = by_index[queue.pop(0)]
            for neighbor_index, current_edge, neighbor_edge in graph[current["index"]]:
                neighbor = by_index[neighbor_index]
                if neighbor_index in visited:
                    continue
                constraints = []
                limits = []
                for placed_index, target_edge, placed_edge in graph[neighbor_index]:
                    if placed_index not in visited:
                        continue
                    placed = by_index[placed_index]
                    constraints.append((placed, placed_edge, target_edge))
                    limits.append(seam_limit(placed, neighbor, placed_edge, target_edge))
                if not constraints:
                    constraints.append((current, current_edge, neighbor_edge))
                    limits.append(seam_limit(current, neighbor, current_edge, neighbor_edge))
                limit = max(limits) if limits else 0.05

                # The carrier atlas must inherit its phase from the most stable
                # already placed reference.  A mostly horizontal seam carries
                # the X phase, so vertical grid lines continue from the upper
                # face into the lower face instead of being reset by a side
                # seam.
                def constraint_priority(item):
                    placed, placed_edge, target_edge = item
                    t0, t1 = endpoints(target_edge)
                    target_q0 = local_xy_raw(neighbor, t0)
                    target_q1 = local_xy_raw(neighbor, t1)
                    target_dx = abs(target_q1[0] - target_q0[0])
                    target_dy = abs(target_q1[1] - target_q0[1])
                    p0, p1 = endpoints(placed_edge)
                    q0 = apply_transform(placed, local_xy_raw(placed, p0))
                    q1 = apply_transform(placed, local_xy_raw(placed, p1))
                    dx = abs(q1[0] - q0[0])
                    dy = abs(q1[1] - q0[1])
                    return (
                        0 if dx >= dy else 1,
                        0 if target_dx >= target_dy else 1,
                        0 if isinstance(placed["face"].Surface, Part.Plane) else 1,
                        -float(getattr(placed_edge, "Length", 0.0)),
                        -float(placed["face"].Area),
                        placed["sub"])

                primary_placed, primary_placed_edge, primary_target_edge = min(
                    constraints, key=constraint_priority)
                primary_pair = tuple(sorted((primary_placed["index"], neighbor["index"])))
                primary_error = fit_neighbor(primary_placed, neighbor,
                                             primary_placed_edge, primary_target_edge)
                primary_transform = list(neighbor.get("transform", []))
                error = primary_error
                if len(constraints) > 1:
                    ignored = []
                    for placed, _placed_edge, _target_edge in constraints:
                        pair = tuple(sorted((placed["index"], neighbor["index"])))
                        if pair != primary_pair:
                            ignored.append("{}<->{}".format(placed["sub"], neighbor["sub"]))
                    if ignored:
                        console("wrap_v4: emenda_atlas_principal={} <-> {}; emendas_extras_ignoradas={}".format(
                            primary_placed["sub"], neighbor["sub"], ",".join(ignored)))
                    if primary_transform:
                        neighbor["transform"] = primary_transform
                if error is None or error > limit:
                    fail("Carrier V4 nao conseguiu posicionar a emenda {} <-> {} (erro {}).".format(
                        primary_placed["sub"], neighbor["sub"], error))
                if error > 0.05:
                    warn("Carrier V4 aceitou emenda curva aproximada {} <-> {} erro={:.4f} limite={:.4f}.".format(
                        primary_placed["sub"], neighbor["sub"], error, limit))
                primary_placed["atlas_seams"].add(primary_pair)
                neighbor["atlas_seams"].add(primary_pair)
                neighbor["component"] = component_index
                visited.add(neighbor_index)
                queue.append(neighbor_index)
        if len(visited) != len(group):
            fail("Componente V4 incompleto.")
        # Move the complete logical component, not each face, to one common
        # lower-left origin.  This is the phase origin consumed by the pattern.
        xs, ys = [], []
        for entry in group:
            for edge in outer_edges(entry["face"]):
                for point in edge_samples(edge, max(MAX_EDGE, edge.Length / 24.0)):
                    logical = apply_transform(entry, local_xy(entry, point))
                    xs.append(logical[0])
                    ys.append(logical[1])
        shift_x = x_offset - min(xs)
        shift_y = -min(ys)
        for entry in group:
            entry["transform"][4] += shift_x
            entry["transform"][5] += shift_y
        # Grid phase is preview metadata. It must never move carrier faces.
        xs = [value + shift_x for value in xs]
        if group:
            xs = []
            for entry in group:
                bounds = transformed_entry_bounds(entry)
                xs.extend([bounds[0], bounds[1]])
        x_offset = max(xs) + MAX_EDGE * 2.0
    return groups


def atlas_seam_pairs(entries):
    pairs = set()
    for entry in entries:
        pairs.update(entry.get("atlas_seams", set()))
    return pairs


def edge_direction_matches(left_edge, right_edge):
    left_start, _left_end = endpoints(left_edge)
    right_start, right_end = endpoints(right_edge)
    return left_start.distanceToPoint(right_start) <= left_start.distanceToPoint(right_end)


def add_logical_seam_overrides(entries, graph, atlas_pairs=None):
    """Force both owners of a shared BRep edge onto the same logical seam."""
    by_index = {entry["index"]: entry for entry in entries}
    for entry in entries:
        entry["seam_overrides"] = []
    checked = set()
    added = 0
    for entry in entries:
        for neighbor_index, edge, other_edge in graph[entry["index"]]:
            pair = tuple(sorted((entry["index"], neighbor_index)))
            if pair in checked:
                continue
            if atlas_pairs is not None and pair not in atlas_pairs:
                continue
            checked.add(pair)
            neighbor = by_index[neighbor_index]
            samples = edge_samples(edge, max(MAX_EDGE, edge.Length / 48.0))
            if len(samples) < 2:
                continue
            shared_a = apply_transform(entry, local_xy_raw(entry, samples[0]))
            shared_b = apply_transform(entry, local_xy_raw(entry, samples[-1]))
            local_a = local_xy_raw(entry, samples[0])
            local_b = local_xy_raw(entry, samples[-1])
            entry["seam_overrides"].append({"pair": pair, "edge": edge, "qa": local_a, "qb": local_b})
            neighbor_a = invert_transform(neighbor, shared_a)
            neighbor_b = invert_transform(neighbor, shared_b)
            if neighbor_a is None or neighbor_b is None:
                continue
            if edge_direction_matches(edge, other_edge):
                neighbor["seam_overrides"].append({"pair": pair, "edge": other_edge, "qa": neighbor_a, "qb": neighbor_b})
            else:
                neighbor["seam_overrides"].append({"pair": pair, "edge": other_edge, "qa": neighbor_b, "qb": neighbor_a})
            added += 1
    if added:
        console("wrap_v4: emendas_logicas_fixadas={}".format(added))


def seam_override(entry, pair):
    for seam in entry.get("seam_overrides", []):
        if seam.get("pair") == pair:
            return seam
    return None


def mapped_vertex(entry, logical):
    mapped = point_from_logical(entry, logical)
    if mapped is None:
        return None
    return {"q": [float(logical[0]), float(logical[1])],
            "p": xyz(mapped[0]), "n": xyz(mapped[1])}


def split_carrier_triangle(entry, vertices, depth):
    if depth <= 0:
        return [vertices]
    points = [v3(vertex["p"]) for vertex in vertices]
    midpoints = []
    for index in range(3):
        qa, qb = vertices[index]["q"], vertices[(index + 1) % 3]["q"]
        logical = [(qa[0] + qb[0]) * 0.5, (qa[1] + qb[1]) * 0.5]
        midpoint = mapped_vertex(entry, logical)
        if midpoint is None:
            return []
        midpoints.append(midpoint)
    a, b, c = vertices
    ab, bc, ca = midpoints
    result = []
    for child in ([a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]):
        result.extend(split_carrier_triangle(entry, child, depth - 1))
    return result


def tessellated_carrier(entry):
    if not isinstance(entry["face"].Surface, Part.Plane):
        return regular_curved_carrier(entry)
    points, facets = entry["face"].tessellate(SAG)
    points = [v3(point) for point in points]
    records = []
    for facet in facets:
        triangle = []
        valid = True
        for vertex_index in facet:
            point = points[vertex_index]
            try:
                logical = apply_transform(entry, local_xy(entry, point))
                vertex = mapped_vertex(entry, logical)
            except Exception:
                valid = False
                break
            if vertex is None:
                valid = False
                break
            triangle.append(vertex)
        if valid and area2([item["q"] for item in triangle]) > 1.0e-8:
            records.append({"face": entry["index"], "component": entry["component"],
                            "curved": not isinstance(entry["face"].Surface, Part.Plane),
                            "v": triangle})
    return records


def entry_contains_logical(entry, logical, tolerance=1.0e-5):
    local = invert_transform(entry, logical)
    if local is None:
        return False
    if (local[0] < -tolerance or local[0] > entry["width"] + tolerance or
            local[1] < -tolerance or local[1] > entry["height"] + tolerance):
        return False
    try:
        u, v = local_uv(entry, local)
        point = entry["face"].valueAt(u, v)
        try:
            return bool(entry["face"].isInside(point, tolerance, True))
        except Exception:
            return entry["face"].distToShape(Part.Vertex(point))[0] <= tolerance
    except Exception:
        return False


def regular_curved_carrier(entry):
    """Build a non-overlapping logical carrier for curved trimmed faces.

    OCC's native tessellation can emit long diagonal facets on cylindrical
    fillets.  Those facets overlap many canonical cells in the atlas and make
    the point mapper jump between unrelated physical regions.
    """
    nx = max(1, int(math.ceil(entry["width"] / MAX_EDGE)))
    ny = max(1, int(math.ceil(entry["height"] / MAX_EDGE)))
    records = []

    def logical_at(ix, iy):
        local = [entry["width"] * float(ix) / nx,
                 entry["height"] * float(iy) / ny]
        return apply_transform(entry, local)

    def add_triangle(points):
        center = [sum(point[0] for point in points) / 3.0,
                  sum(point[1] for point in points) / 3.0]
        if not entry_contains_logical(entry, center):
            return
        triangle = []
        for logical in points:
            vertex = mapped_vertex(entry, logical)
            if vertex is None:
                return
            triangle.append(vertex)
        if area2([item["q"] for item in triangle]) > 1.0e-8:
            records.append({"face": entry["index"], "component": entry["component"],
                            "curved": True, "v": triangle})

    for ix in range(nx):
        for iy in range(ny):
            a = logical_at(ix, iy)
            b = logical_at(ix + 1, iy)
            c = logical_at(ix, iy + 1)
            d = logical_at(ix + 1, iy + 1)
            add_triangle([a, b, c])
            add_triangle([b, d, c])
    return records


def midpoint_vertex(left, right, entry):
    pa, pb = v3(left["p"]), v3(right["p"])
    point = (pa + pb) * 0.5
    try:
        u, v = entry["face"].Surface.parameter(point)
        point = entry["face"].Surface.value(u, v)
        normal = norm(entry["face"].normalAt(u, v))
        if normal is not None and normal.dot(entry["normal_ref"]) < 0:
            normal = -normal
    except Exception:
        normal = None
    if normal is None:
        na, nb = v3(left["n"]), v3(right["n"])
        normal = norm(na + nb) or norm(na) or norm(nb) or App.Vector(0, 0, 1)
    return {"q": [(left["q"][0] + right["q"][0]) * 0.5,
                  (left["q"][1] + right["q"][1]) * 0.5],
            "p": xyz(point), "n": xyz(normal)}


def weld_logical_nodes(triangles):
    """Give coincident physical vertices one shared logical coordinate.

    Normals remain local to each carrier triangle, which is required at a
    physical crease.  Only the mutable q-list is shared.
    """
    groups = {}
    for triangle in triangles:
        for vertex in triangle["v"]:
            key = qkey3(v3(vertex["p"]))
            groups.setdefault(key, []).append(vertex)
    for vertices in groups.values():
        min_x = min(item["q"][0] for item in vertices)
        max_x = max(item["q"][0] for item in vertices)
        min_y = min(item["q"][1] for item in vertices)
        max_y = max(item["q"][1] for item in vertices)
        if math.hypot(max_x - min_x, max_y - min_y) > 0.10:
            # This is a deliberate periodic seam or an invalid atlas closure;
            # welding it would fold unrelated logical regions together.
            continue
        shared = [sum(item["q"][0] for item in vertices) / len(vertices),
                  sum(item["q"][1] for item in vertices) / len(vertices)]
        for vertex in vertices:
            vertex["q"] = shared
    return triangles


def refine_conforming_round(triangles, entries):
    by_face = {entry["index"]: entry for entry in entries}
    split_keys = set()
    for triangle in triangles:
        for index in range(3):
            left, right = triangle["v"][index], triangle["v"][(index + 1) % 3]
            length = v3(left["p"]).distanceToPoint(v3(right["p"]))
            # OCC's tessellation already enforces SAG on the surface.  This
            # conforming pass only controls physical edge length.  Re-testing
            # sag by repeatedly projecting chord midpoints can oscillate at a
            # periodic seam and produce hundreds of thousands of triangles.
            if length > MAX_EDGE + 1.0e-7:
                split_keys.add(triangle_edge_key(left, right))
    if not split_keys:
        return triangles, False

    result = []
    midpoint_cache = {}

    def cached_midpoint(left, right, entry):
        edge_key = triangle_edge_key(left, right)
        key = (edge_key, entry["index"])
        if key not in midpoint_cache:
            midpoint_cache[key] = midpoint_vertex(left, right, entry)
        value = midpoint_cache[key]
        # Across a real crease the point is shared but each face retains its
        # own normal.  q will be welded globally after the refinement round.
        return {"q": list(value["q"]), "p": list(value["p"]), "n": list(value["n"])}

    for triangle in triangles:
        a, b, c = triangle["v"]
        split_ab = triangle_edge_key(a, b) in split_keys
        split_bc = triangle_edge_key(b, c) in split_keys
        split_ca = triangle_edge_key(c, a) in split_keys
        entry = by_face[triangle["face"]]
        ab = cached_midpoint(a, b, entry) if split_ab else None
        bc = cached_midpoint(b, c, entry) if split_bc else None
        ca = cached_midpoint(c, a, entry) if split_ca else None
        children = None
        count = int(split_ab) + int(split_bc) + int(split_ca)
        if count == 0:
            result.append(triangle)
            continue
        if count == 1:
            if split_ab:
                children = ([a, ab, c], [ab, b, c])
            elif split_bc:
                children = ([b, bc, a], [bc, c, a])
            else:
                children = ([c, ca, b], [ca, a, b])
        elif count == 2:
            if split_ab and split_bc:
                children = ([b, bc, ab], [a, ab, c], [ab, bc, c])
            elif split_ab and split_ca:
                children = ([a, ab, ca], [ab, b, c], [ca, ab, c])
            else:
                children = ([c, ca, bc], [a, b, ca], [ca, b, bc])
        else:
            children = ([a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca])
        for vertices in children:
            result.append({"face": triangle["face"], "component": triangle["component"],
                           "curved": triangle.get("curved", False),
                           "v": list(vertices)})
    return weld_logical_nodes(result), True


def conforming_carrier(entries):
    base = []
    for entry in entries:
        base.extend(tessellated_carrier(entry))
    if not base:
        return []
    # OCC already tessellates each support with the requested sag.  Recursively
    # splitting every long tessellation chord here used to multiply a 60-face
    # carrier into hundreds of thousands of patches.  More importantly, the
    # subsequent re-unfolding assigned a second logical position to the same
    # physical node.  The canonical 8x lattice supplies the required 1.5 mm
    # sampling when cells are built, so the carrier only needs the sag mesh.
    carrier = weld_logical_nodes(base)
    longest = max(v3(triangle["v"][index]["p"]).distanceToPoint(
        v3(triangle["v"][(index + 1) % 3]["p"]))
        for triangle in carrier for index in range(3))
    console("wrap_v4: carrier_parametrico={} longest={:.4f} sag={:.4f}".format(
        len(carrier), longest, SAG))
    return carrier


def validate_logical_seams(entries, graph, atlas_pairs=None):
    """Verify that both BRep owners map a real seam to the same logical line."""
    checked = set()
    maximum = 0.0
    for entry in entries:
        for neighbor_index, edge, other_edge in graph[entry["index"]]:
            pair = tuple(sorted((entry["index"], neighbor_index)))
            if pair in checked:
                continue
            if atlas_pairs is not None and pair not in atlas_pairs:
                continue
            checked.add(pair)
            neighbor = next(item for item in entries if item["index"] == neighbor_index)
            left_override = seam_override(entry, pair)
            right_override = seam_override(neighbor, pair)
            left = edge_samples(edge, max(MAX_EDGE, edge.Length / 24.0))
            right = edge_samples(other_edge, max(MAX_EDGE, other_edge.Length / 24.0))
            reverse_right = left[0].distanceToPoint(right[0]) > left[0].distanceToPoint(right[-1])
            if reverse_right:
                right.reverse()
            count = min(len(left), len(right))
            errors = []
            for index in range(count):
                li = int(round(index * (len(left) - 1) / max(count - 1, 1)))
                ri = int(round(index * (len(right) - 1) / max(count - 1, 1)))
                if left_override is not None and right_override is not None:
                    left_ratio = edge_fraction(edge, left[li])
                    right_ratio = edge_fraction(other_edge, right[ri])
                    if reverse_right:
                        right_ratio = 1.0 - right_ratio
                    left_local = [left_override["qa"][0] + (left_override["qb"][0] - left_override["qa"][0]) * left_ratio,
                                  left_override["qa"][1] + (left_override["qb"][1] - left_override["qa"][1]) * left_ratio]
                    right_local = [right_override["qa"][0] + (right_override["qb"][0] - right_override["qa"][0]) * right_ratio,
                                   right_override["qa"][1] + (right_override["qb"][1] - right_override["qa"][1]) * right_ratio]
                    qa = apply_transform(entry, left_local)
                    qb = apply_transform(neighbor, right_local)
                else:
                    qa = apply_transform(entry, local_xy(entry, left[li]))
                    qb = apply_transform(neighbor, local_xy(neighbor, right[ri]))
                errors.append(math.hypot(qa[0] - qb[0], qa[1] - qb[1]))
            error = max(errors) if errors else 1.0e9
            maximum = max(maximum, error)
            limit = 0.05
            if (not isinstance(entry["face"].Surface, Part.Plane) or
                    not isinstance(neighbor["face"].Surface, Part.Plane)):
                limit = max(limit, min(edge.Length, other_edge.Length) * 0.35)
            if error > limit:
                fail("Emenda logica V4 {} <-> {} divergiu {:.4f} mm.".format(
                    entry["sub"], neighbor["sub"], error))
            if error > 0.05:
                warn("Emenda logica V4 curva aproximada {} <-> {} erro={:.4f} limite={:.4f}.".format(
                    entry["sub"], neighbor["sub"], error, limit))
    console("wrap_v4: emendas_logicas={} erro_max={:.4f}".format(len(checked), maximum))
    return maximum


def triangle_edge_key(left, right):
    return tuple(sorted((qkey3(v3(left["p"])), qkey3(v3(right["p"])))))


def third_point_2d(qa, qb, pa, pb, pc, opposite=None):
    edge = pb.distanceToPoint(pa)
    if edge <= 1.0e-10:
        return None
    da, db = pc.distanceToPoint(pa), pc.distanceToPoint(pb)
    x = (da * da - db * db + edge * edge) / (2.0 * edge)
    height2 = da * da - x * x
    if height2 < -SAG * SAG:
        return None
    height = math.sqrt(max(height2, 0.0))
    ex, ey = (qb[0] - qa[0]) / edge, (qb[1] - qa[1]) / edge
    candidates = [[qa[0] + ex * x - ey * height, qa[1] + ey * x + ex * height],
                  [qa[0] + ex * x + ey * height, qa[1] + ey * x - ex * height]]
    if opposite is None:
        return candidates[0]
    side = cross2(qa, qb, opposite)
    candidates.sort(key=lambda point: cross2(qa, qb, point) * side)
    return candidates[0]


def cycle_seam_pairs(groups, graph):
    pairs = set()
    for group in groups:
        nodes = {item["index"] for item in group}
        edges = sorted({tuple(sorted((node, neighbor))) for node in nodes
                        for neighbor, _a, _b in graph[node] if neighbor in nodes})
        if len(edges) >= len(nodes) and edges:
            # A closed carrier is opened at one deterministic BRep edge.  Its
            # two logical sides are recorded as a periodic pair, never joined
            # by selection order.
            pairs.add(edges[-1])
    return pairs


def rotate_component(vertices, triangle_indices):
    used = sorted({id(vertex["q"]): vertex for index in triangle_indices
                   for vertex in vertices[index]}.values(), key=lambda item: qkey3(v3(item["p"])))
    if not used:
        return
    # Least-squares gradient of physical Z in the provisional logical plane.
    mean_qx = sum(item["q"][0] for item in used) / len(used)
    mean_qy = sum(item["q"][1] for item in used) / len(used)
    mean_z = sum(v3(item["p"]).z for item in used) / len(used)
    sxx = syy = sxy = sxz = syz = 0.0
    for item in used:
        x, y, z = item["q"][0] - mean_qx, item["q"][1] - mean_qy, v3(item["p"]).z - mean_z
        sxx += x * x
        syy += y * y
        sxy += x * y
        sxz += x * z
        syz += y * z
    determinant = sxx * syy - sxy * sxy
    if abs(determinant) > 1.0e-12:
        gx = (sxz * syy - syz * sxy) / determinant
        gy = (syz * sxx - sxz * sxy) / determinant
        angle = math.atan2(gx, gy)
        cs, sn = math.cos(angle), math.sin(angle)
        for item in used:
            x, y = item["q"]
            item["q"][:] = [cs * x - sn * y, sn * x + cs * y]
    min_x = min(item["q"][0] for item in used)
    min_y = min(item["q"][1] for item in used)
    for item in used:
        item["q"][:] = [item["q"][0] - min_x, item["q"][1] - min_y]


def close_periodic_component(vertices, triangle_indices, face_ids, seam_pairs):
    periodic = any(left in face_ids and right in face_ids for left, right in seam_pairs)
    if not periodic:
        return None
    used = sorted({id(vertex["q"]): vertex for index in triangle_indices
                   for vertex in vertices[index]}.values(), key=lambda item: qkey3(v3(item["p"])))
    min_x = min(item["q"][0] for item in used)
    max_x = max(item["q"][0] for item in used)
    width = max_x - min_x
    if width <= 1.0e-8:
        fail("Componente periodico V4 sem largura logica.")
    columns = max(1, int(round(width / GRID_SIDE)))
    target = columns * GRID_SIDE
    adjustment = (target - width) / width
    if abs(adjustment) > 0.05:
        fail("Fechamento periodico V4 exige ajuste de {:.2f}% (limite 5%).".format(abs(adjustment) * 100.0))
    scale = target / width
    for item in used:
        item["q"][0] = min_x + (item["q"][0] - min_x) * scale
    return {"faces": sorted(face_ids), "physical_width": width, "logical_width": target,
            "columns": columns, "adjustment": adjustment}


def unfold_carrier(triangles, groups, graph):
    seam_pairs = cycle_seam_pairs(groups, graph)
    periodic_records = []
    maximum_closure_error = 0.0
    edge_map = {}
    for index, triangle in enumerate(triangles):
        for pos in range(3):
            key = triangle_edge_key(triangle["v"][pos], triangle["v"][(pos + 1) % 3])
            edge_map.setdefault(key, []).append((index, pos))
    adjacency = {index: [] for index in range(len(triangles))}
    for occurrences in edge_map.values():
        if len(occurrences) != 2:
            continue
        left, right = occurrences[0][0], occurrences[1][0]
        pair = tuple(sorted((triangles[left]["face"], triangles[right]["face"])))
        if triangles[left]["face"] != triangles[right]["face"] and pair in seam_pairs:
            continue
        adjacency[left].append(right)
        adjacency[right].append(left)
    component_offset = 0.0
    for group in groups:
        face_ids = {item["index"] for item in group}
        members = [index for index, triangle in enumerate(triangles) if triangle["face"] in face_ids]
        if not members:
            fail("Componente do carrier V4 sem triangulos.")
        root = min(members, key=lambda index: (min(v3(item["p"]).z for item in triangles[index]["v"]),
                                               min(v3(item["p"]).x for item in triangles[index]["v"]), index))
        root_vertices = triangles[root]["v"]
        pa, pb, pc = [v3(item["p"]) for item in root_vertices]
        qa, qb = [0.0, 0.0], [pa.distanceToPoint(pb), 0.0]
        qc = third_point_2d(qa, qb, pa, pb, pc)
        if qc is None:
            fail("Triangulo ancora degenerado no carrier V4.")
        root_vertices[0]["q"][:] = qa
        root_vertices[1]["q"][:] = qb
        root_vertices[2]["q"][:] = qc
        logical_nodes = {qkey3(v3(item["p"])) for item in root_vertices}
        placed = {root}
        queue = [root]
        while queue:
            current_index = queue.pop(0)
            current = triangles[current_index]
            for neighbor_index in adjacency[current_index]:
                neighbor = triangles[neighbor_index]
                common = []
                for ci, cv in enumerate(current["v"]):
                    for ni, nv in enumerate(neighbor["v"]):
                        if qkey3(v3(cv["p"])) == qkey3(v3(nv["p"])):
                            common.append((ci, ni))
                if len(common) != 2:
                    continue
                if neighbor_index in placed:
                    continue
                c0, n0 = common[0]
                c1, n1 = common[1]
                third_current = next(index for index in range(3) if index not in (c0, c1))
                third_neighbor = next(index for index in range(3) if index not in (n0, n1))
                ca, cb = current["v"][c0], current["v"][c1]
                na, nb, nc = neighbor["v"][n0], neighbor["v"][n1], neighbor["v"][third_neighbor]
                na["q"][:] = ca["q"]
                nb["q"][:] = cb["q"]
                candidate = third_point_2d(na["q"], nb["q"], v3(na["p"]), v3(nb["p"]), v3(nc["p"]),
                                           current["v"][third_current]["q"])
                if candidate is None:
                    fail("Falha ao desdobrar triangulo vizinho no carrier V4.")
                node_key = qkey3(v3(nc["p"]))
                if node_key in logical_nodes:
                    mismatch = math.hypot(nc["q"][0] - candidate[0], nc["q"][1] - candidate[1])
                    # Curved carriers are not globally isometric to a plane.
                    # A node reached through another triangle can therefore
                    # have a second unfolded candidate.  Its first global q
                    # is authoritative; changing it would crack every edge
                    # already attached to that node.
                    maximum_closure_error = max(maximum_closure_error, mismatch)
                else:
                    nc["q"][:] = candidate
                    logical_nodes.add(node_key)
                placed.add(neighbor_index)
                queue.append(neighbor_index)
        missing = set(members) - placed
        if missing:
            fail("Tessellacao V4 nao compartilha nos BReps: {} triangulos desconectados.".format(len(missing)))
        rotate_component([triangle["v"] for triangle in triangles], members)
        periodic = close_periodic_component([triangle["v"] for triangle in triangles], members,
                                            face_ids, seam_pairs)
        if periodic is not None:
            periodic_records.append(periodic)
        component_vertices = list({id(item["q"]): item for index in members
                                   for item in triangles[index]["v"]}.values())
        for item in component_vertices:
            item["q"][0] += component_offset
        component_offset = max(item["q"][0] for item in component_vertices) + GRID_SIDE * 2.0
    console("wrap_v4: erro_fechamento_logico_max={:.4f}".format(maximum_closure_error))
    return seam_pairs, periodic_records


def point_on_edge(point, edge, tolerance=2.0e-4):
    try:
        return edge.distToShape(Part.Vertex(point))[0] <= tolerance
    except Exception:
        return False


def external_segments(entries, graph, triangles, seam_pairs):
    records = []
    boundary = {}
    for triangle in triangles:
        for pos in range(3):
            a, b = triangle["v"][pos], triangle["v"][(pos + 1) % 3]
            key = triangle_edge_key(a, b)
            boundary.setdefault(key, []).append((a, b, triangle))
    for entry in entries:
        shared_edges = [edge for _neighbor, edge, _other in graph[entry["index"]]]
        for edge in outer_edges(entry["face"]):
            if any(same_edge(edge, candidate) for candidate in shared_edges):
                continue
            for occurrences in boundary.values():
                if len(occurrences) != 1:
                    continue
                a, b, triangle = occurrences[0]
                if triangle["face"] != entry["index"]:
                    continue
                if point_on_edge(v3(a["p"]), edge) and point_on_edge(v3(b["p"]), edge):
                    records.append({"face": entry["index"], "component": entry["component"],
                                    "a": a, "b": b})
    return records


def area2(poly):
    return abs(sum(poly[index][0] * poly[(index + 1) % len(poly)][1] -
                   poly[(index + 1) % len(poly)][0] * poly[index][1]
                   for index in range(len(poly)))) * 0.5


def logical_bounds(points):
    return [min(point[0] for point in points), max(point[0] for point in points),
            min(point[1] for point in points), max(point[1] for point in points)]


def expand_bounds(bounds, margin):
    return [bounds[0] - margin, bounds[1] + margin, bounds[2] - margin, bounds[3] + margin]


def bounds_overlap(left, right, tolerance=0.0):
    return not (left[1] < right[0] - tolerance or right[1] < left[0] - tolerance or
                left[3] < right[2] - tolerance or right[3] < left[2] - tolerance)


def carrier_bounds(carrier):
    return logical_bounds([item["q"] for item in carrier["v"]])


def component_logical_bounds(triangles):
    grouped = {}
    for triangle in triangles:
        grouped.setdefault(triangle.get("component", 0), []).extend(item["q"] for item in triangle["v"])
    return {component: logical_bounds(points) for component, points in grouped.items()}


def line_triangle_points(triangle, value, vertical):
    result = []
    vertices = triangle["v"]
    axis = 0 if vertical else 1
    for index in range(3):
        left, right = vertices[index], vertices[(index + 1) % 3]
        a, b = left["q"][axis] - value, right["q"][axis] - value
        if abs(a) <= 1.0e-8:
            result.append(list(left["q"]))
        if a * b < -1.0e-14:
            ratio = a / (a - b)
            result.append([left["q"][0] + (right["q"][0] - left["q"][0]) * ratio,
                           left["q"][1] + (right["q"][1] - left["q"][1]) * ratio])
    unique = []
    for point in result:
        if not any(math.hypot(point[0] - other[0], point[1] - other[1]) <= 1.0e-7 for other in unique):
            unique.append(point)
    if len(unique) < 2:
        return None
    other_axis = 1 - axis
    unique.sort(key=lambda point: point[other_axis])
    return unique[0], unique[-1]


def grid_line_values(lower, upper, origin, step):
    first = origin + math.ceil((lower - origin) / step - 1.0e-9) * step
    values = []
    current = first
    while current <= upper + 1.0e-8:
        values.append(current)
        current += step
    return values


def validate_map_grid(column_width, row_height, closure_tolerance):
    values = {
        "Column width": column_width,
        "Row height": row_height,
        "Closure tolerance": closure_tolerance,
    }
    for label, value in values.items():
        try:
            value = float(value)
        except (TypeError, ValueError):
            fail("{} must be a finite positive length.".format(label))
        if not math.isfinite(value) or value <= 0.0:
            fail("{} must be a finite positive length.".format(label))


def carrier_preview(triangles, bounds, column_width=DEFAULT_MAP_COLUMN_WIDTH,
                    row_height=DEFAULT_MAP_ROW_HEIGHT, origin=None):
    edges = []
    x0, x1, y0, y1 = bounds
    origin = list(origin or [(x0 + x1) * 0.5, (y0 + y1) * 0.5])
    for vertical, lower, upper, phase, step in (
            (True, x0, x1, origin[0], float(column_width)),
            (False, y0, y1, origin[1], float(row_height))):
        for value in grid_line_values(lower, upper, phase, step):
            for triangle in triangles:
                segment = line_triangle_points(triangle, value, vertical)
                if segment is None:
                    continue
                mapped = [interpolate_vertex(point, triangle) for point in segment]
                if all(item is not None for item in mapped):
                    points = [item[0] + item[1] * 0.01 for item in mapped]
                    length = points[0].distanceToPoint(points[1])
                    if length > 1.0e-7:
                        edges.append(Part.makePolygon(points))
    return Part.makeCompound(edges) if edges else Part.Shape()


def entry_record(entry):
    return {"index": entry["index"], "object": entry["object"].Name, "sub": entry["sub"],
            "range": entry["range"], "metric_u": entry["metric_u"], "metric_v": entry["metric_v"],
            "length_u": entry["length_u"], "length_v": entry["length_v"],
            "x_axis": entry["x_axis"], "y_axis": entry["y_axis"],
            "x_sign": entry["x_sign"], "y_sign": entry["y_sign"],
            "width": entry["width"], "height": entry["height"],
            "normal_sign": entry["normal_sign"], "transform": entry["transform"],
            "component": entry["component"]}


def create_wrap(column_width=DEFAULT_MAP_COLUMN_WIDTH,
                row_height=DEFAULT_MAP_ROW_HEIGHT,
                closure_tolerance=DEFAULT_MAP_CLOSURE_TOLERANCE):
    doc = App.ActiveDocument
    if doc is None:
        fail("Abra um documento antes de executar Wrap Faces V4.")
    validate_map_grid(column_width, row_height, closure_tolerance)
    console("wrap_v4: build={} file={}".format(BUILD_ID, __file__))
    entries = selected_faces()
    for entry in entries:
        orient_entry(entry)
    graph, shared = build_graph(entries)
    groups = position_components(entries, graph)
    atlas_pairs = atlas_seam_pairs(entries)
    add_logical_seam_overrides(entries, graph, atlas_pairs)
    validate_logical_seams(entries, graph, atlas_pairs)
    for entry in entries:
        entry["seam_overrides"] = []
    triangles = conforming_carrier(entries)
    if not triangles:
        fail("Carrier V4 nao gerou triangulos internos.")
    # The face transforms above are the authoritative atlas.  Do not unfold
    # tessellation triangles a second time: that creates overlapping logical
    # regions and switches support in the middle of canonical cells.
    seam_pairs = cycle_seam_pairs(groups, graph)
    periodic_records = []
    boundary = external_segments(entries, graph, triangles, seam_pairs)
    xs = [vertex["q"][0] for tri in triangles for vertex in tri["v"]]
    ys = [vertex["q"][1] for tri in triangles for vertex in tri["v"]]
    bounds = [min(xs), max(xs), min(ys), max(ys)]
    grid_origin = [(bounds[0] + bounds[1]) * 0.5,
                   (bounds[2] + bounds[3]) * 0.5]
    grid = {"column_width": float(column_width),
            "row_height": float(row_height),
            "origin": grid_origin,
            "closure_tolerance": float(closure_tolerance)}
    compatibility = {"status": "not_evaluated", "segments": [],
                     "cycles": [], "arcs": []}
    payload = {"schema": SCHEMA, "version": 1,
               "grid_height": float(row_height),
               "grid_side": float(column_width),
               "grid": grid, "max_edge": MAX_EDGE, "sag": SAG,
               "bounds": bounds, "faces": [entry_record(item) for item in entries],
               "triangles": triangles, "carrier_triangles": triangles,
               "external_segments": boundary, "adjacency": shared,
               "periodic_seams": [list(pair) for pair in sorted(seam_pairs)],
               "periodic_adjustments": periodic_records,
               "components": [[item["index"] for item in group] for group in groups],
               "compatibility": compatibility}
    name = next_name(doc, WRAP_PREFIX)
    run = doc.addObject("PartDesign::Feature", name)
    run.Label = name
    run.Shape = Part.makeCompound([entry["face"] for entry in entries])
    add_string(run, "WrapVersion", "Wrap Faces V4", "Wrap Faces V4")
    add_string(run, "WrapAlgorithm", SCHEMA, "Wrap Faces V4")
    add_string(run, "WrapReady", "True", "Wrap Faces V4")
    add_string(run, "WrapSourceFaces", ";".join("{}|{}".format(e["object"].Name, e["sub"]) for e in entries), "Wrap Faces V4")
    add_string(run, "WrapAdjacency", ";".join("{}>{}".format(a + 1, b + 1) for a, b in shared), "Wrap Faces V4")
    add_chunks(run, "WrapCarrierChunks", payload, "Wrap Faces V4")
    add_string(run, "MapVersion", "1", "Pattern Surface")
    add_string(run, "MapAlgorithm", SCHEMA, "Pattern Surface")
    add_string(run, "MapReady", "True", "Pattern Surface")
    add_length(run, "MapColumnWidth", column_width, "Pattern Surface")
    add_length(run, "MapRowHeight", row_height, "Pattern Surface")
    add_vector(run, "MapGridOrigin", grid_origin, "Pattern Surface")
    add_length(run, "MapClosureTolerance", closure_tolerance, "Pattern Surface")
    add_bool(run, "MapCompatible", True, "Pattern Surface")
    add_integer(run, "MapIncompatibleCount", 0, "Pattern Surface")
    add_string_list(run, "MapCompatibilityReport", [], "Pattern Surface")
    add_chunks(run, "MapPayloadChunks", payload, "Pattern Surface")
    preview = doc.addObject("PartDesign::Feature", name + "_CarrierGrid")
    preview.Label = name + " Carrier Grid"
    preview.Shape = carrier_preview(
        triangles, bounds, column_width, row_height, grid_origin)
    add_string(preview, "WrapParentRun", run.Name, "Wrap Faces V4")
    add_string(preview, "MapParentRun", run.Name, "Pattern Surface")
    view = getattr(preview, "ViewObject", None)
    if view is not None:
        view.LineColor = (0.0, 0.8, 1.0)
        view.LineWidth = 2.0
        view.DisplayMode = "Wireframe"
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(run)
    console("wrap_v4: run={} faces={} carrier_triangles={}".format(name, len(entries), len(triangles)))
    return run


def resolve_wrap_selection(doc):
    for obj in Gui.Selection.getSelection():
        if (getattr(obj, "MapAlgorithm", "") == SCHEMA or
                getattr(obj, "WrapAlgorithm", "") == SCHEMA):
            return obj
        parent = getattr(obj, "WrapParentRun", "")
        if parent:
            run = doc.getObject(parent)
            if run is not None and getattr(run, "WrapAlgorithm", "") == SCHEMA:
                return run
    fail("Selecione o objeto DiamondSurfaceWrap_V4_Run_... antes de executar esta macro.")


def hydrate_entries(doc, payload):
    entries = []
    for record in payload["faces"]:
        obj = doc.getObject(record["object"])
        if obj is None:
            fail("Objeto fonte {} nao encontrado.".format(record["object"]))
        try:
            face = obj.getSubObject(record["sub"])
        except Exception:
            number = int(record["sub"].replace("Face", ""))
            face = obj.Shape.Faces[number - 1]
        entry = dict(record)
        entry["object_ref"], entry["face"] = obj, face
        entries.append(entry)
    return entries


def cross2(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def point_in_triangle(point, tri, tolerance=1.0e-7):
    values = [cross2(tri[0], tri[1], point), cross2(tri[1], tri[2], point), cross2(tri[2], tri[0], point)]
    return min(values) >= -tolerance or max(values) <= tolerance


def barycentric(point, tri):
    den = cross2(tri[0], tri[1], tri[2])
    if abs(den) <= 1.0e-12:
        return None
    w0 = cross2(tri[1], tri[2], point) / den
    w1 = cross2(tri[2], tri[0], point) / den
    return [w0, w1, 1.0 - w0 - w1]


def interpolate_vertex(point, carrier_triangle):
    coords = [item["q"] for item in carrier_triangle["v"]]
    weights = barycentric(point, coords)
    if weights is None:
        return None
    p = App.Vector(0, 0, 0)
    n = App.Vector(0, 0, 0)
    for weight, vertex in zip(weights, carrier_triangle["v"]):
        p += v3(vertex["p"]) * weight
        n += v3(vertex["n"]) * weight
    return p, norm(n)


def clip_polygon(subject, clipper):
    output = [list(point) for point in subject]
    orientation = 1.0 if cross2(clipper[0], clipper[1], clipper[2]) >= 0 else -1.0
    for index in range(len(clipper)):
        a, b = clipper[index], clipper[(index + 1) % len(clipper)]
        source, output = output, []
        if not source:
            break
        for pos, end in enumerate(source):
            start = source[pos - 1]
            end_inside = orientation * cross2(a, b, end) >= -1.0e-8
            start_inside = orientation * cross2(a, b, start) >= -1.0e-8
            if end_inside != start_inside:
                dx1, dy1 = end[0] - start[0], end[1] - start[1]
                dx2, dy2 = b[0] - a[0], b[1] - a[1]
                denominator = dx1 * dy2 - dy1 * dx2
                if abs(denominator) > 1.0e-12:
                    t = ((a[0] - start[0]) * dy2 - (a[1] - start[1]) * dx2) / denominator
                    output.append([start[0] + t * dx1, start[1] + t * dy1])
            if end_inside:
                output.append(end)
    cleaned = []
    for point in output:
        if not cleaned or math.hypot(point[0] - cleaned[-1][0], point[1] - cleaned[-1][1]) > 1.0e-7:
            cleaned.append(point)
    if len(cleaned) > 2 and math.hypot(cleaned[0][0] - cleaned[-1][0], cleaned[0][1] - cleaned[-1][1]) <= 1.0e-7:
        cleaned.pop()
    return cleaned


def canonical_triangles(bounds, extra=True, diamond_height=GRID_HEIGHT):
    """Yield one edge-connected equilateral triangle lattice.

    Consecutive rows are offset by half a side.  The previous implementation
    built an up/down pair inside every rectangular column; adjacent columns
    then met only at a vertex instead of sharing their sloping edge.
    """
    x0, x1, y0, y1 = bounds
    grid_height = float(diamond_height)
    grid_side = 2.0 * grid_height / math.sqrt(3.0)
    margin_x = grid_side if extra else 0.0
    margin_y = grid_height if extra else 0.0
    # The requested margin is exactly one canonical row/column.  A single
    # guard column covers the half-side offset without producing a second
    # ring of cells around curved boundaries.
    col0 = int(math.floor((x0 - margin_x) / grid_side)) - 1
    col1 = int(math.ceil((x1 + margin_x) / grid_side)) + 1
    row0 = int(math.floor((y0 - margin_y) / grid_height))
    row1 = int(math.ceil((y1 + margin_y) / grid_height))

    def point(row, col):
        shift = grid_side * 0.5 if row % 2 else 0.0
        return [col * grid_side + shift, row * grid_height]

    for row in range(row0, row1):
        for col in range(col0, col1):
            lower_left = point(row, col)
            lower_right = point(row, col + 1)
            upper_left = point(row + 1, col)
            upper_right = point(row + 1, col + 1)
            if row % 2:
                up = [lower_left, lower_right, upper_right]
                down = [lower_left, upper_right, upper_left]
            else:
                up = [lower_left, lower_right, upper_left]
                down = [lower_right, upper_right, upper_left]
            yield "r{}_c{}_up".format(row, col), up
            yield "r{}_c{}_down".format(row, col), down


def nearest_carrier(point, triangles):
    best = None
    for triangle in triangles:
        coords = [item["q"] for item in triangle["v"]]
        if point_in_triangle(point, coords):
            return triangle
        center = [sum(item[0] for item in coords) / 3.0, sum(item[1] for item in coords) / 3.0]
        distance = (center[0] - point[0]) ** 2 + (center[1] - point[1]) ** 2
        if best is None or distance < best[0]:
            best = (distance, triangle)
    return best[1] if best else None


def extended_triangles(payload):
    original = list(payload["triangles"])
    result = list(original)
    distance = max(GRID_SIDE, GRID_HEIGHT) * 1.05
    # Only BRep edges without a selected adjacent face are extended.  Inferring
    # this from tessellation incidence reclassifies mismatched seam segments as
    # outside borders and creates the duplicated walls seen in V0.
    for segment in payload.get("external_segments", []):
        a, b = segment["a"], segment["b"]
        midpoint = [(a["q"][0] + b["q"][0]) * 0.5, (a["q"][1] + b["q"][1]) * 0.5]
        candidates = [item for item in original if item["face"] == segment["face"]]
        tri = nearest_carrier(midpoint, candidates)
        if tri is None:
            continue
        qa, qb = a["q"], b["q"]
        center = [sum(v["q"][0] for v in tri["v"]) / 3.0, sum(v["q"][1] for v in tri["v"]) / 3.0]
        dx, dy = qb[0] - qa[0], qb[1] - qa[1]
        length = math.hypot(dx, dy)
        if length <= 1.0e-7:
            continue
        nx, ny = -dy / length, dx / length
        if (center[0] - midpoint[0]) * nx + (center[1] - midpoint[1]) * ny > 0:
            nx, ny = -nx, -ny
        qao = [qa[0] + nx * distance, qa[1] + ny * distance]
        qbo = [qb[0] + nx * distance, qb[1] + ny * distance]

        # Extend the physical carrier in the local tangent plane of the real
        # BRep boundary.  Affine UV extrapolation from a small/skinny carrier
        # triangle magnifies unfolding error and creates long spikes.
        pa, pb = v3(a["p"]), v3(b["p"])
        edge_tangent = norm(pb - pa)
        if edge_tangent is None:
            continue
        physical_center = sum((v3(item["p"]) for item in tri["v"]), App.Vector(0, 0, 0)) / 3.0

        def tangent_extension(vertex, endpoint):
            normal = norm(v3(vertex["n"]))
            if normal is None:
                return None
            tangent = norm(normal.cross(edge_tangent))
            if tangent is None:
                return None
            # The ghost strip must point away from the carrier interior.
            if tangent.dot(physical_center - endpoint) > 0:
                tangent = -tangent
            return endpoint + tangent * distance

        pao = tangent_extension(a, pa)
        pbo = tangent_extension(b, pb)
        if pao is None or pbo is None:
            continue
        ao = {"q": qao, "p": xyz(pao), "n": list(a["n"])}
        bo = {"q": qbo, "p": xyz(pbo), "n": list(b["n"])}
        result.append({"face": tri["face"], "component": tri["component"], "ghost": True, "v": [a, b, bo]})
        result.append({"face": tri["face"], "component": tri["component"], "ghost": True, "v": [a, bo, ao]})
    return result


def face_from_triangle(a, b, c):
    try:
        return Part.Face(Part.makePolygon([a, b, c, a]))
    except Exception:
        return None


def dedupe_vectors(points, tolerance=1.0e-6):
    result = []
    for point in points:
        if not result or point.distanceToPoint(result[-1]) > tolerance:
            result.append(point)
    if len(result) > 2 and result[0].distanceToPoint(result[-1]) <= tolerance:
        result.pop()
    return result


def average_vector(points):
    if not points:
        return None
    return sum(points, App.Vector(0, 0, 0)) / len(points)


def sample_polygon_edges(polygon, segments):
    result = []
    for index in range(len(polygon)):
        start = polygon[index]
        end = polygon[(index + 1) % len(polygon)]
        for step in range(segments):
            ratio = float(step) / float(segments)
            result.append([start[0] + (end[0] - start[0]) * ratio,
                           start[1] + (end[1] - start[1]) * ratio])
    return result


def cap_faces_from_loop(loop, reverse=False):
    center = average_vector(loop)
    if center is None:
        return []
    faces = []
    for index in range(len(loop)):
        a = loop[index]
        b = loop[(index + 1) % len(loop)]
        face = face_from_triangle(center, b, a) if reverse else face_from_triangle(center, a, b)
        if face is not None:
            faces.append(face)
    return faces


def solid_from_fragments(fragments, apex):
    rear_faces = []
    edge_map = {}
    for fragment in fragments:
        polygon = fragment["polygon"]
        carrier = fragment["carrier"]
        mapped = []
        for point in polygon:
            value = interpolate_vertex(point, carrier)
            if value is None:
                mapped = []
                break
            mapped.append(value[0] - value[1] * CONTACT)
        if len(mapped) < 3:
            continue
        for index in range(1, len(mapped) - 1):
            face = face_from_triangle(mapped[0], mapped[index + 1], mapped[index])
            if face is not None:
                rear_faces.append(face)
        for index in range(len(polygon)):
            p0, p1 = polygon[index], polygon[(index + 1) % len(polygon)]
            key = tuple(sorted((qkey2(p0), qkey2(p1))))
            value = (mapped[index], mapped[(index + 1) % len(mapped)])
            if key in edge_map:
                edge_map[key] = None
            else:
                edge_map[key] = value
    side_faces = []
    for value in edge_map.values():
        if value is None:
            continue
        face = face_from_triangle(value[0], value[1], apex)
        if face is not None:
            side_faces.append(face)
    if not rear_faces or not side_faces:
        return None
    try:
        shell = Part.makeShell(rear_faces + side_faces)
        if shell.isNull() or not shell.isClosed():
            return None
        solid = Part.makeSolid(shell)
        if solid.isNull() or not solid.isValid() or len(solid.Solids) != 1:
            return None
        return solid
    except Exception:
        return None


def canonical_shell_solid(canonical, context, height, apex_override=None):
    loop = []
    for logical in sample_polygon_edges(canonical, CELL_SUBDIVISIONS):
        value = map_context_point(logical, context)
        if value is None or value[1] is None:
            return None, None
        loop.append(value[0] - value[1] * CONTACT)
    loop = dedupe_vectors(loop)
    if len(loop) < 3:
        return None, None

    center = [sum(point[0] for point in canonical) / 3.0,
              sum(point[1] for point in canonical) / 3.0]
    center_value = map_context_point(center, context)
    if center_value is None or center_value[1] is None:
        return None, None
    apex = apex_override if apex_override is not None else center_value[0] + center_value[1] * height

    faces = cap_faces_from_loop(loop, reverse=True)
    for index in range(len(loop)):
        face = face_from_triangle(loop[index], loop[(index + 1) % len(loop)], apex)
        if face is not None:
            faces.append(face)
    if len(faces) < 4:
        return None, None
    try:
        shell = Part.makeShell(faces)
        if shell.isNull() or not shell.isClosed():
            return None, None
        solid = Part.makeSolid(shell)
        if solid.isNull() or not solid.isValid() or len(solid.Solids) != 1:
            return None, None
        return solid, apex
    except Exception:
        return None, None


def curved_shell_pyramid_solid(canonical, context, height, apex_override=None):
    """One-apex pyramid for curved border cells with a surface-based rear cap."""
    loop = []
    for logical in sample_polygon_edges(canonical, CELL_SUBDIVISIONS):
        value = map_context_point(logical, context)
        if value is None or value[1] is None:
            return None, None
        loop.append(value[0] - value[1] * CONTACT)
    loop = dedupe_vectors(loop)
    if len(loop) < 3:
        return None, None

    center = [sum(point[0] for point in canonical) / 3.0,
              sum(point[1] for point in canonical) / 3.0]
    center_value = map_context_point(center, context)
    if center_value is None or center_value[1] is None:
        return None, None
    center_rear = center_value[0] - center_value[1] * CONTACT
    apex = apex_override if apex_override is not None else center_value[0] + center_value[1] * height

    faces = []
    for index in range(len(loop)):
        rear = face_from_triangle(center_rear, loop[(index + 1) % len(loop)], loop[index])
        side = face_from_triangle(loop[index], loop[(index + 1) % len(loop)], apex)
        if rear is None or side is None:
            return None, None
        faces.extend([rear, side])
    try:
        shell = Part.makeShell(faces)
        if shell.isNull() or not shell.isClosed():
            return None, None
        solid = Part.makeSolid(shell)
        if solid.isNull() or not solid.isValid() or len(solid.Solids) != 1:
            return None, None
        return solid, apex
    except Exception:
        return None, None


def triangular_height_weight(point, canonical):
    weights = barycentric(point, canonical)
    if weights is None:
        return 0.0
    return max(0.0, min(1.0, 3.0 * min(weights)))


def curved_height_mapped_solid(canonical, context, height, apex_override=None, source_solids=None):
    count = CELL_SUBDIVISIONS
    a, b, c = canonical
    rear_nodes = {}
    top_nodes = {}
    for i in range(count + 1):
        for j in range(count + 1 - i):
            q = [a[0] + (b[0] - a[0]) * i / count + (c[0] - a[0]) * j / count,
                 a[1] + (b[1] - a[1]) * i / count + (c[1] - a[1]) * j / count]
            mapped = map_context_point(q, context)
            if mapped is None or mapped[1] is None:
                return None, None
            base, normal = mapped
            normal = outside_normal_for_point(base, normal, source_solids)
            if normal is None:
                return None, None
            weight = triangular_height_weight(q, canonical)
            rear_nodes[(i, j)] = base - normal * CONTACT
            top_nodes[(i, j)] = base + normal * (height * weight)

    center = [sum(point[0] for point in canonical) / 3.0,
              sum(point[1] for point in canonical) / 3.0]
    center_value = map_context_point(center, context)
    if center_value is None or center_value[1] is None:
        return None, None
    center_normal = outside_normal_for_point(center_value[0], center_value[1], source_solids)
    if center_normal is None:
        return None, None
    apex = apex_override if apex_override is not None else center_value[0] + center_normal * height

    faces = []
    for i in range(count):
        for j in range(count - i):
            rear = face_from_triangle(rear_nodes[(i, j)], rear_nodes[(i, j + 1)], rear_nodes[(i + 1, j)])
            top = face_from_triangle(top_nodes[(i, j)], top_nodes[(i + 1, j)], top_nodes[(i, j + 1)])
            if rear is None or top is None:
                return None, None
            faces.extend([rear, top])
            if i + j <= count - 2:
                rear = face_from_triangle(rear_nodes[(i + 1, j)], rear_nodes[(i, j + 1)], rear_nodes[(i + 1, j + 1)])
                top = face_from_triangle(top_nodes[(i + 1, j)], top_nodes[(i + 1, j + 1)], top_nodes[(i, j + 1)])
                if rear is None or top is None:
                    return None, None
                faces.extend([rear, top])

    rear_boundary = []
    top_boundary = []
    rear_boundary.extend(rear_nodes[(i, 0)] for i in range(count + 1))
    top_boundary.extend(top_nodes[(i, 0)] for i in range(count + 1))
    rear_boundary.extend(rear_nodes[(count - i, i)] for i in range(1, count + 1))
    top_boundary.extend(top_nodes[(count - i, i)] for i in range(1, count + 1))
    rear_boundary.extend(rear_nodes[(0, count - i)] for i in range(1, count))
    top_boundary.extend(top_nodes[(0, count - i)] for i in range(1, count))
    for index in range(len(rear_boundary)):
        rear_a = rear_boundary[index]
        rear_b = rear_boundary[(index + 1) % len(rear_boundary)]
        top_a = top_boundary[index]
        top_b = top_boundary[(index + 1) % len(top_boundary)]
        face_a = face_from_triangle(rear_a, rear_b, top_b)
        face_b = face_from_triangle(rear_a, top_b, top_a)
        if face_a is None or face_b is None:
            return None, None
        faces.extend([face_a, face_b])

    try:
        shell = Part.makeShell(faces)
        if shell.isNull() or not shell.isClosed():
            return None, None
        solid = Part.makeSolid(shell)
        if solid.isNull() or not solid.isValid() or len(solid.Solids) != 1:
            return None, None
        return solid, apex
    except Exception:
        return None, None


def face_domain_polygon(record):
    width, height = record["width"], record["height"]
    matrix = record["transform"]

    def transform(local):
        return [matrix[0] * local[0] + matrix[1] * local[1] + matrix[4],
                matrix[2] * local[0] + matrix[3] * local[1] + matrix[5]]

    return [transform([0.0, 0.0]), transform([width, 0.0]),
            transform([width, height]), transform([0.0, height])]


def domain_fragments(payload, canonical):
    fragments = []
    for record in payload.get("faces", []):
        polygon = clip_polygon(canonical, face_domain_polygon(record))
        if len(polygon) >= 3 and area2(polygon) > 1.0e-7:
            fragments.append({"polygon": polygon, "face": record["index"],
                              "component": record.get("component", 0)})
    return fragments


def subtriangle_points(canonical, i, j, upper):
    count = CELL_SUBDIVISIONS
    a, b, c = canonical

    def point(ii, jj):
        return [a[0] + (b[0] - a[0]) * ii / count + (c[0] - a[0]) * jj / count,
                a[1] + (b[1] - a[1]) * ii / count + (c[1] - a[1]) * jj / count]

    if upper:
        return [point(i + 1, j), point(i, j + 1), point(i + 1, j + 1)]
    return [point(i, j), point(i, j + 1), point(i + 1, j)]


def solid_from_domain_fragments(canonical, fragments, context, apex):
    rear_faces = []
    edge_map = {}

    def add_piece(logical_polygon):
        mapped = []
        for point in logical_polygon:
            value = map_context_point(point, context)
            if value is None or value[1] is None:
                return False
            mapped.append(value[0] - value[1] * CONTACT)
        if len(mapped) < 3:
            return False
        for index in range(1, len(mapped) - 1):
            face = face_from_triangle(mapped[0], mapped[index + 1], mapped[index])
            if face is not None:
                rear_faces.append(face)
        for index in range(len(logical_polygon)):
            p0, p1 = logical_polygon[index], logical_polygon[(index + 1) % len(logical_polygon)]
            key = tuple(sorted((qkey2(p0), qkey2(p1))))
            value = (mapped[index], mapped[(index + 1) % len(mapped)])
            if key in edge_map:
                edge_map[key] = None
            else:
                edge_map[key] = value
        return True

    any_piece = False
    for i in range(CELL_SUBDIVISIONS):
        for j in range(CELL_SUBDIVISIONS - i):
            pieces = [subtriangle_points(canonical, i, j, False)]
            if i + j <= CELL_SUBDIVISIONS - 2:
                pieces.append(subtriangle_points(canonical, i, j, True))
            for piece in pieces:
                for fragment in fragments:
                    clipped = clip_polygon(piece, fragment["polygon"])
                    if len(clipped) >= 3 and area2(clipped) > 1.0e-7:
                        any_piece = add_piece(clipped) or any_piece

    side_faces = []
    for value in edge_map.values():
        if value is None:
            continue
        face = face_from_triangle(value[0], value[1], apex)
        if face is not None:
            side_faces.append(face)
    if not any_piece or not rear_faces or not side_faces:
        return None
    try:
        shell = Part.makeShell(rear_faces + side_faces)
        if shell.isNull() or not shell.isClosed():
            return None
        solid = Part.makeSolid(shell)
        if solid.isNull() or not solid.isValid() or len(solid.Solids) != 1:
            return None
        return solid
    except Exception:
        return None


def build_carrier_index(carriers, cell_size=GRID_HEIGHT * 0.5):
    """Index logical carrier patches without changing their topology."""
    bins = {}
    for index, triangle in enumerate(carriers):
        coords = [item["q"] for item in triangle["v"]]
        x0, x1 = min(item[0] for item in coords), max(item[0] for item in coords)
        y0, y1 = min(item[1] for item in coords), max(item[1] for item in coords)
        ix0, ix1 = int(math.floor(x0 / cell_size)), int(math.floor(x1 / cell_size))
        iy0, iy1 = int(math.floor(y0 / cell_size)), int(math.floor(y1 / cell_size))
        for ix in range(ix0, ix1 + 1):
            for iy in range(iy0, iy1 + 1):
                bins.setdefault((ix, iy), []).append(index)
    return {"triangles": carriers, "bins": bins, "cell_size": cell_size}


def indexed_carriers(point, source):
    if not isinstance(source, dict):
        return source
    size = source["cell_size"]
    key = (int(math.floor(point[0] / size)), int(math.floor(point[1] / size)))
    return [source["triangles"][index] for index in source["bins"].get(key, [])]


def carrier_for_point(point, carriers):
    """Return one deterministic carrier patch for a logical point."""
    inside = []
    for index, triangle in enumerate(indexed_carriers(point, carriers)):
        coords = [item["q"] for item in triangle["v"]]
        weights = barycentric(point, coords)
        if weights is None:
            continue
        margin = min(weights)
        if margin >= -1.0e-7:
            inside.append((not triangle.get("ghost", False), margin, -index, triangle))
    if inside:
        # A real carrier always wins over an external temporary strip.  Margin
        # only resolves ties between patches of the same class.
        return max(inside, key=lambda item: (item[0], item[1], item[2]))[3]
    # A point outside the logical carrier must remain outside.  Falling back
    # to the nearest triangle collapses entire lattice edges onto a boundary
    # and creates the long spikes/non-manifold cells seen at fillets.
    return None


def map_carrier_point(point, carriers):
    carrier = carrier_for_point(point, carriers)
    return interpolate_vertex(point, carrier) if carrier is not None else None


def external_mapping_records(payload, components=None, faces=None, bounds=None):
    """Build continuous one-cell extrapolators for real external BRep edges.

    Ghost triangles leave gaps between independently tessellated edge pieces.
    These records instead project any logical point directly to the closest
    real boundary segment and continue the surface in its local tangent plane.
    """
    real = list(payload["triangles"])
    records = []
    components = set(components) if components is not None else None
    faces = set(faces) if faces is not None else None
    for segment in payload.get("external_segments", []):
        if components is not None and segment.get("component", 0) not in components:
            continue
        if faces is not None and segment["face"] not in faces:
            continue
        a, b = segment["a"], segment["b"]
        qa, qb = list(a["q"]), list(b["q"])
        if bounds is not None and not bounds_overlap(logical_bounds([qa, qb]), bounds, EXTERNAL_ROW_LIMIT):
            continue
        qdx, qdy = qb[0] - qa[0], qb[1] - qa[1]
        qlength = math.hypot(qdx, qdy)
        if qlength <= 1.0e-7:
            continue
        qtx, qty = qdx / qlength, qdy / qlength
        midpoint = [(qa[0] + qb[0]) * 0.5, (qa[1] + qb[1]) * 0.5]
        candidates = [item for item in real if item["face"] == segment["face"]]
        carrier = nearest_carrier(midpoint, candidates)
        if carrier is None:
            continue
        center_q = [sum(v["q"][0] for v in carrier["v"]) / 3.0,
                    sum(v["q"][1] for v in carrier["v"]) / 3.0]
        qnx, qny = -qty, qtx
        if (center_q[0] - midpoint[0]) * qnx + (center_q[1] - midpoint[1]) * qny > 0:
            qnx, qny = -qnx, -qny

        pa, pb = v3(a["p"]), v3(b["p"])
        physical_edge = pb - pa
        physical_length = physical_edge.Length
        if physical_length <= 1.0e-7:
            continue
        ptx = physical_edge / physical_length
        na, nb = norm(v3(a["n"])), norm(v3(b["n"]))
        if na is None or nb is None:
            continue
        middle_normal = norm(na + nb)
        if middle_normal is None:
            middle_normal = na
        pout = norm(middle_normal.cross(ptx))
        if pout is None:
            continue
        center_p = sum((v3(v["p"]) for v in carrier["v"]), App.Vector(0, 0, 0)) / 3.0
        if pout.dot(center_p - (pa + pb) * 0.5) > 0:
            pout = -pout
        records.append({
            "qa": qa, "qb": qb, "qtx": qtx, "qty": qty,
            "qnx": qnx, "qny": qny, "qlength": qlength,
            "pa": pa, "pb": pb, "ptangent": ptx, "pout": pout,
            "na": na, "nb": nb,
            "key": (segment.get("component", 0), segment["face"], qkey2(qa), qkey2(qb)),
        })
    return sorted(records, key=lambda item: item["key"])


def map_external_point(point, records):
    """Map one point outside the carrier, limited to one canonical cell."""
    # Eligibility is tested against the real carrier before this function is
    # used.  Allow only the local outside strip needed to complete one
    # canonical border cell; detached rows must not be created by extrapolation.
    limit = EXTERNAL_ROW_LIMIT + 1.0e-6
    best = None
    for record in records:
        dx = point[0] - record["qa"][0]
        dy = point[1] - record["qa"][1]
        along = dx * record["qtx"] + dy * record["qty"]
        endpoint_overrun = max(-along, along - record["qlength"], 0.0)
        if endpoint_overrun > EXTERNAL_ENDPOINT_LIMIT:
            continue
        clamped = min(record["qlength"], max(0.0, along))
        qpx = record["qa"][0] + record["qtx"] * clamped
        qpy = record["qa"][1] + record["qty"] * clamped
        delta_x, delta_y = point[0] - qpx, point[1] - qpy
        outward = delta_x * record["qnx"] + delta_y * record["qny"]
        if outward < -EXTERNAL_INWARD_TOL:
            continue
        distance = math.hypot(delta_x, delta_y)
        if distance > limit:
            continue
        score = (distance + endpoint_overrun * 4.0, record["key"])
        if best is None or score < best[0]:
            best = (score, record, along, clamped, outward)
    if best is None:
        return None
    _, record, along, clamped, outward = best
    ratio = clamped / record["qlength"]
    p_edge = record["pa"] * (1.0 - ratio) + record["pb"] * ratio
    # `along - clamped` only occurs past an endpoint and closes corner gaps.
    point3d = (p_edge + record["ptangent"] * (along - clamped)
               + record["pout"] * outward)
    normal = norm(record["na"] * (1.0 - ratio) + record["nb"] * ratio)
    return (point3d, normal) if normal is not None else None


def build_mapping_context(payload, include_external, real=None, components=None, faces=None, bounds=None):
    real = list(payload["triangles"] if real is None else real)
    return {
        "real": real,
        "index": build_carrier_index(real),
        "external": external_mapping_records(payload, components, faces, bounds) if include_external else [],
    }


def map_context_point(point, context):
    value = map_carrier_point(point, context["index"])
    if value is not None:
        return value
    return map_external_point(point, context["external"])


def clipped_cell_fragments(carriers, canonical):
    fragments = []
    for carrier in carriers:
        clipped = clip_polygon(canonical, [item["q"] for item in carrier["v"]])
        if len(clipped) >= 3 and area2(clipped) > 1.0e-7:
            fragments.append({"carrier": carrier, "polygon": clipped, "area": area2(clipped)})
    return fragments


def choose_cell_component(fragments):
    by_component = {}
    for fragment in fragments:
        component = fragment["carrier"].get("component", 0)
        by_component[component] = by_component.get(component, 0.0) + fragment["area"]
    return max(by_component.items(), key=lambda item: (item[1], -item[0]))[0]


def local_cell_context(payload, canonical, carriers, include_external):
    """Build a mapper scoped to one canonical cell and its real surface patch."""
    fragments = clipped_cell_fragments(carriers, canonical)
    if not fragments:
        return None, []
    component = choose_cell_component(fragments)
    fragments = [item for item in fragments if item["carrier"].get("component", 0) == component]
    faces = {item["carrier"]["face"] for item in fragments}
    cell_bounds = expand_bounds(logical_bounds(canonical), LOGICAL_TOL)
    local_real = []
    seen = set()
    for fragment in fragments:
        carrier = fragment["carrier"]
        key = id(carrier)
        if key not in seen:
            local_real.append(carrier)
            seen.add(key)
    context = build_mapping_context(payload, include_external, local_real, {component}, faces, cell_bounds)
    return context, fragments


def validate_physical_lattice(nodes, boundary, apex):
    for i in range(CELL_SUBDIVISIONS + 1):
        for j in range(CELL_SUBDIVISIONS + 1 - i):
            here = nodes[(i, j)]
            for neighbor in ((i + 1, j), (i, j + 1), (i + 1, j - 1)):
                if neighbor in nodes and here.distanceToPoint(nodes[neighbor]) > MAX_LATTICE_STEP:
                    return False
    corners = [boundary[0], boundary[CELL_SUBDIVISIONS], boundary[CELL_SUBDIVISIONS * 2]]
    for index in range(3):
        if corners[index].distanceToPoint(corners[(index + 1) % 3]) > MAX_CANONICAL_EDGE:
            return False
    if apex is not None:
        for corner in corners:
            if corner.distanceToPoint(apex) > MAX_CANONICAL_EDGE:
                return False
    return True


def choose_outside_apex(base_center, apex_normal, source_solids, height):
    if not source_solids:
        return base_center + apex_normal * height
    plus = base_center + apex_normal * height
    minus = base_center - apex_normal * height
    plus_inside = False
    minus_inside = False
    checked = False
    for solid in source_solids:
        try:
            plus_inside = plus_inside or bool(solid.isInside(plus, 1.0e-6, False))
            minus_inside = minus_inside or bool(solid.isInside(minus, 1.0e-6, False))
            checked = True
        except Exception:
            pass
    if checked and plus_inside != minus_inside:
        return minus if plus_inside else plus
    return plus


def outside_normal_for_point(base, normal, source_solids):
    """Return a normal that points out of the source solid at this point."""
    normal = norm(normal)
    if normal is None or not source_solids:
        return normal
    for distance in (0.08, 0.35, 0.80, 1.50):
        plus = base + normal * distance
        minus = base - normal * distance
        plus_inside = False
        minus_inside = False
        checked = False
        for solid in source_solids:
            try:
                plus_inside = plus_inside or bool(solid.isInside(plus, 1.0e-6, False))
                minus_inside = minus_inside or bool(solid.isInside(minus, 1.0e-6, False))
                checked = True
            except Exception:
                pass
        if checked and plus_inside != minus_inside:
            return -normal if plus_inside else normal
    return normal


def side_faces_intrude_source(boundary, apex, source_solids):
    """Detect one-apex side faces that cut back into the source solid."""
    if not source_solids:
        return False
    for start in boundary:
        for ratio in (0.35, 0.55, 0.75):
            point = start * (1.0 - ratio) + apex * ratio
            for solid in source_solids:
                try:
                    if solid.isInside(point, 1.0e-5, False):
                        return True
                except Exception:
                    pass
    return False


def canonical_lattice_solid(canonical, context, height, apex_override=None, source_solids=None):
    """Build one closed cell from a single canonical 8x lattice.

    Every logical node is mapped once.  This avoids non-manifold seams caused
    by clipping the same cell independently against overlapping unfolded
    carrier triangles.
    """
    count = CELL_SUBDIVISIONS
    a, b, c = canonical
    nodes = {}
    base_points = []
    outward_normals = []
    for i in range(count + 1):
        for j in range(count + 1 - i):
            q = [a[0] + (b[0] - a[0]) * i / count + (c[0] - a[0]) * j / count,
                 a[1] + (b[1] - a[1]) * i / count + (c[1] - a[1]) * j / count]
            mapped = map_context_point(q, context)
            if mapped is None or mapped[1] is None:
                return None, None
            nodes[(i, j)] = mapped[0] - mapped[1] * CONTACT

    center = [sum(point[0] for point in canonical) / 3.0,
              sum(point[1] for point in canonical) / 3.0]
    center_value = map_context_point(center, context)
    if center_value is None or center_value[1] is None:
        return None, None
    apex = apex_override if apex_override is not None else center_value[0] + center_value[1] * height

    rear_faces = []
    for i in range(count):
        for j in range(count - i):
            face = face_from_triangle(nodes[(i, j)], nodes[(i, j + 1)], nodes[(i + 1, j)])
            if face is None:
                return None, None
            rear_faces.append(face)
            if i + j <= count - 2:
                face = face_from_triangle(nodes[(i + 1, j)], nodes[(i, j + 1)], nodes[(i + 1, j + 1)])
                if face is None:
                    return None, None
                rear_faces.append(face)

    boundary = []
    boundary.extend(nodes[(i, 0)] for i in range(count + 1))
    boundary.extend(nodes[(count - i, i)] for i in range(1, count + 1))
    boundary.extend(nodes[(0, count - i)] for i in range(1, count))
    if not validate_physical_lattice(nodes, boundary, apex):
        return None, None
    side_faces = []
    for index, start in enumerate(boundary):
        end = boundary[(index + 1) % len(boundary)]
        face = face_from_triangle(start, end, apex)
        if face is None:
            return None, None
        side_faces.append(face)
    try:
        shell = Part.makeShell(rear_faces + side_faces)
        if shell.isNull() or not shell.isClosed():
            return None, None
        solid = Part.makeSolid(shell)
        if solid.isNull() or not solid.isValid() or len(solid.Solids) != 1:
            return None, None
        return solid, apex
    except Exception:
        return None, None


def curved_lattice_pyramid_solid(canonical, context, height, apex_override=None, source_solids=None):
    """Curved row pyramid with a fully subdivided rear face and one apex.

    This keeps the face glued to the container as the same small-triangle
    lattice used on the good rows, but avoids the strict lattice rejection that
    can remove valid border cells on a fillet.
    """
    count = CELL_SUBDIVISIONS
    a, b, c = canonical
    nodes = {}

    def logical_node(i, j):
        return [a[0] + (b[0] - a[0]) * i / count + (c[0] - a[0]) * j / count,
                a[1] + (b[1] - a[1]) * i / count + (c[1] - a[1]) * j / count]

    for i in range(count + 1):
        for j in range(count + 1 - i):
            q = logical_node(i, j)
            mapped = map_context_point(q, context)
            if mapped is None or mapped[1] is None:
                return None, None
            normal = outside_normal_for_point(mapped[0], mapped[1], source_solids)
            if normal is None:
                return None, None
            nodes[(i, j)] = mapped[0] - normal * CONTACT

    center = [sum(point[0] for point in canonical) / 3.0,
              sum(point[1] for point in canonical) / 3.0]
    center_value = map_context_point(center, context)
    if center_value is None or center_value[1] is None:
        return None, None
    center_normal = outside_normal_for_point(center_value[0], center_value[1], source_solids)
    if center_normal is None:
        return None, None
    apex = apex_override if apex_override is not None else center_value[0] + center_normal * height

    rear_faces = []
    for i in range(count):
        for j in range(count - i):
            face = face_from_triangle(nodes[(i, j)], nodes[(i, j + 1)], nodes[(i + 1, j)])
            if face is None:
                return None, None
            rear_faces.append(face)
            if i + j <= count - 2:
                face = face_from_triangle(nodes[(i + 1, j)], nodes[(i, j + 1)], nodes[(i + 1, j + 1)])
                if face is None:
                    return None, None
                rear_faces.append(face)

    boundary_keys = []
    boundary_keys.extend((i, 0) for i in range(count + 1))
    boundary_keys.extend((count - i, i) for i in range(1, count + 1))
    boundary_keys.extend((0, count - i) for i in range(1, count))
    boundary = [nodes[key] for key in boundary_keys]
    boundary_logical = [logical_node(*key) for key in boundary_keys]
    side_faces = []
    side_steps = max(3, CELL_SUBDIVISIONS // 2)

    def side_point(edge_q, ratio):
        if ratio >= 1.0 - 1.0e-9:
            return apex
        q = [edge_q[0] * (1.0 - ratio) + center[0] * ratio,
             edge_q[1] * (1.0 - ratio) + center[1] * ratio]
        mapped = map_context_point(q, context)
        if mapped is None or mapped[1] is None:
            return None
        normal = outside_normal_for_point(mapped[0], mapped[1], source_solids)
        if normal is None:
            return None
        return mapped[0] + normal * (height * ratio - CONTACT * (1.0 - ratio))

    for index, start_q in enumerate(boundary_logical):
        end_q = boundary_logical[(index + 1) % len(boundary_logical)]
        previous_start = boundary[index]
        previous_end = boundary[(index + 1) % len(boundary)]
        for step in range(1, side_steps + 1):
            ratio = float(step) / float(side_steps)
            current_start = side_point(start_q, ratio)
            current_end = side_point(end_q, ratio)
            if current_start is None or current_end is None:
                return None, None
            if step == side_steps:
                face = face_from_triangle(previous_start, previous_end, apex)
                if face is None:
                    return None, None
                side_faces.append(face)
            else:
                face_a = face_from_triangle(previous_start, previous_end, current_end)
                face_b = face_from_triangle(previous_start, current_end, current_start)
                if face_a is None or face_b is None:
                    return None, None
                side_faces.extend([face_a, face_b])
            previous_start, previous_end = current_start, current_end
    try:
        shell = Part.makeShell(rear_faces + side_faces)
        if shell.isNull() or not shell.isClosed():
            return None, None
        solid = Part.makeSolid(shell)
        if solid.isNull() or not solid.isValid() or len(solid.Solids) != 1:
            return None, None
        return solid, apex
    except Exception:
        return None, None


def curved_row_pyramid_solid(canonical, context, height, apex_override=None, source_solids=None):
    """Build a curved-row cell without changing the cut behavior.

    The lower curved row needs a surface-following rear base, otherwise a
    simple cap can dip into the body on only some cells. Keep the visible
    pyramid as one apex and reserve the dense height-mapped body as a last
    fallback only.
    """
    solid, apex = curved_lattice_pyramid_solid(
        canonical, context, height, apex_override, source_solids)
    if solid is not None:
        return solid, apex
    solid, apex = curved_shell_pyramid_solid(canonical, context, height, apex_override)
    if solid is not None:
        return solid, apex
    solid, apex = canonical_shell_solid(canonical, context, height, apex_override)
    if solid is not None:
        return solid, apex
    return curved_height_mapped_solid(
        canonical, context, height, apex_override, source_solids)


def build_cells(payload, include_ghost, height=DEFAULT_PATTERN_HEIGHT,
                diamond_height=GRID_HEIGHT,
                allowed_ids=None, apex_records=None, source_shapes=None):
    # Eligibility is always evaluated against the real logical surface.  The
    # external mapper only completes a canonical cell that crosses its border;
    # it must never create detached rows made exclusively from ghost geometry.
    carriers = list(payload["triangles"])
    results, records, rejected = [], [], []
    for triangle_id, canonical in canonical_triangles(
            payload["bounds"], extra=include_ghost, diamond_height=diamond_height):
        if allowed_ids is not None and triangle_id not in allowed_ids:
            continue
        context, fragments = local_cell_context(payload, canonical, carriers, include_ghost)
        if not fragments:
            continue
        apex_override = v3(apex_records[triangle_id]) if apex_records and triangle_id in apex_records else None
        source_solids = []
        if source_shapes:
            for fragment in fragments:
                shape = source_shapes.get(fragment["carrier"]["face"])
                if shape is not None and shape not in source_solids:
                    source_solids.append(shape)
        solid = apex = None
        if any(fragment["carrier"].get("curved", False) for fragment in fragments):
            solid, apex = curved_row_pyramid_solid(
                canonical, context, height, apex_override, source_solids)
        if solid is None:
            solid, apex = canonical_lattice_solid(
                canonical, context, height, apex_override, source_solids)
        if solid is None:
            rejected.append(triangle_id)
            continue
        results.append(solid)
        records.append({"id": triangle_id, "canonical": canonical, "apex": xyz(apex)})
    return results, records, rejected


def build_cut_cells(payload, allowed_ids, apex_records, diamond_height=GRID_HEIGHT):
    """Rebuild only the physical portion of each canonical full cell."""
    carriers = list(payload["triangles"])
    results, records, rejected = [], [], []
    for triangle_id, canonical in canonical_triangles(
            payload["bounds"], extra=False, diamond_height=diamond_height):
        if triangle_id not in allowed_ids:
            continue
        context, carrier_fragments = local_cell_context(payload, canonical, carriers, False)
        fragments = domain_fragments(payload, canonical)
        if not carrier_fragments or not fragments:
            continue
        apex_value = apex_records.get(triangle_id)
        if apex_value is None:
            rejected.append(triangle_id)
            continue
        solid = solid_from_domain_fragments(canonical, fragments, context, v3(apex_value))
        if solid is None:
            rejected.append(triangle_id)
            continue
        results.append(solid)
        records.append({"id": triangle_id, "canonical": canonical, "apex": apex_value})
    return results, records, rejected


def exact_face_cut_envelope(entry, pattern_height):
    """Closed physical domain for one selected source face.

    The cut must be a trim operation on the already-good Full solids.  Rebuilding
    the cell here changes the curved-row height field and reintroduces the
    flattened/deformed lower triangles.
    """
    cached = entry.get("cut_envelope")
    if is_valid_shape(cached):
        return cached
    front_depth = pattern_height + CUT_FRONT_MARGIN
    rear_depth = CONTACT + CUT_REAR_MARGIN
    sign = 1.0 if entry.get("normal_sign", 1.0) >= 0.0 else -1.0
    try:
        front = entry["face"].makeOffsetShape(sign * front_depth, 0.01, fill=True)
        rear = entry["face"].makeOffsetShape(-sign * rear_depth, 0.01, fill=True)
        envelope = front.fuse(rear)
        try:
            envelope = envelope.removeSplitter()
        except Exception:
            pass
        if is_valid_shape(envelope):
            entry["cut_envelope"] = envelope
            return envelope
    except Exception as exc:
        warn("cut_v4: envelope_offset_falhou face={} erro={}".format(entry.get("index", "?"), exc))

    if not entry.get("planar", False):
        return None
    center = face_center(entry["face"])
    normal = signed_normal_at(entry, center)
    if normal is None or normal.Length <= 1.0e-9:
        return None
    normal.normalize()
    try:
        base = entry["face"].copy()
        base.translate(normal * (-rear_depth))
        envelope = base.extrude(normal * (front_depth + rear_depth))
        if is_valid_shape(envelope):
            entry["cut_envelope"] = envelope
            return envelope
    except Exception as exc:
        warn("cut_v4: envelope_plano_falhou face={} erro={}".format(entry.get("index", "?"), exc))
    return None


def fused_cut_envelopes(envelopes):
    if not envelopes:
        return None
    result = envelopes[0]
    for envelope in envelopes[1:]:
        try:
            result = result.fuse(envelope)
        except Exception as exc:
            warn("cut_v4: envelope_fuse_falhou erro={}".format(exc))
            return None
    try:
        result = result.removeSplitter()
    except Exception:
        pass
    return result if is_valid_shape(result) else None


def physical_cut_piece(cell, combined_envelope, envelopes, index):
    pieces = []
    if combined_envelope is not None:
        try:
            result = cell.common(combined_envelope)
            if is_valid_shape(result):
                pieces.extend(list(result.Solids))
        except Exception as exc:
            warn("cut_v4: booleano_combinado_falhou celula={} erro={}".format(index, exc))
    if not pieces:
        for envelope in envelopes:
            try:
                result = cell.common(envelope)
                if is_valid_shape(result):
                    pieces.extend(list(result.Solids))
            except Exception as exc:
                warn("cut_v4: booleano_face_falhou celula={} erro={}".format(index, exc))
    return pieces


def build_cut_cells_from_full(doc, payload, pattern, cell_payload, pattern_height):
    """Trim Full solids by the selected face envelopes, preserving Full geometry."""
    entries = hydrate_entries(doc, payload)
    envelopes = [exact_face_cut_envelope(entry, pattern_height) for entry in entries]
    envelopes = [shape for shape in envelopes if is_valid_shape(shape)]
    if not envelopes:
        return [], [], ["sem_envelope"]
    combined_envelope = fused_cut_envelopes(envelopes)
    full_solids = list(getattr(pattern.Shape, "Solids", []) or [])
    full_records = list(cell_payload.get("cells", []) or [])
    if not full_solids or len(full_solids) != len(full_records):
        warn("cut_v4: full_solidos_registros_incompativeis solidos={} registros={}".format(
            len(full_solids), len(full_records)))
        return [], [], ["full_incompativel"]

    results, records, rejected = [], [], []
    for index, (cell, record) in enumerate(zip(full_solids, full_records), start=1):
        pieces = physical_cut_piece(cell, combined_envelope, envelopes, index)
        if pieces:
            results.extend(pieces)
            records.append(record)
        else:
            rejected.append(record.get("id", "cell{}".format(index)))
    return results, records, rejected


def source_solids_by_face(doc, payload):
    result = {}
    for record in payload.get("faces", []):
        obj = doc.getObject(record["object"])
        shape = getattr(obj, "Shape", None) if obj is not None else None
        if shape is None or shape.isNull():
            continue
        result[record["index"]] = shape
    return result


def create_full_pattern(height=DEFAULT_PATTERN_HEIGHT, diamond_height=None):
    doc = App.ActiveDocument
    if doc is None:
        fail("Abra um documento antes de executar o Pattern Full V4.")
    height = float(height)
    diamond_height = float(diamond_height if diamond_height is not None
                           else GRID_HEIGHT)
    if height < 0.01:
        fail("A altura da piramide deve ser pelo menos 0.01 mm.")
    if diamond_height < 0.01:
        fail("A altura do diamante deve ser pelo menos 0.01 mm.")
    wrap = resolve_wrap_selection(doc)
    payload = load_chunks(wrap, "WrapCarrierChunks")
    if payload.get("schema") != SCHEMA:
        fail("Carrier selecionado nao e V4.")
    solids, records, rejected = build_cells(
        payload, True, height=height, diamond_height=diamond_height,
        source_shapes=source_solids_by_face(doc, payload))
    if not solids:
        fail("Pattern Full V4 nao gerou solidos validos.")
    name = next_name(doc, FULL_PREFIX)
    run = doc.addObject("PartDesign::Feature", name)
    run.Label = name + " Solid"
    run.Shape = Part.makeCompound(solids)
    add_string(run, "DiamondPatternVersion", "Pattern Full From Wrap V4", "Diamond Pattern V4")
    add_string(run, "DiamondPatternAlgorithm", "WRAP_CARRIER_V4_FULL", "Diamond Pattern V4")
    add_string(run, "DiamondPatternWrapSource", wrap.Name, "Diamond Pattern V4")
    add_string(run, "PatternId", "diamond", "Pattern Surface")
    add_string(run, "PatternMapSource", wrap.Name, "Pattern Surface")
    add_length(run, "PatternHeight", height, "Pattern Surface")
    add_length(run, "DiamondHeight", diamond_height, "Pattern Surface")
    add_string(run, "DiamondPatternRejected", ";".join(rejected), "Diamond Pattern V4")
    add_chunks(run, "DiamondPatternCellChunks",
               {"cells": records, "parameters": {
                   "height": height,
                   "pyramid_height": height,
                   "diamond_height": diamond_height,
               }},
               "Diamond Pattern V4")
    doc.recompute()
    console("pattern_full_v4: run={} diamond_height={:.3f} pyramid_height={:.3f} solids={} rejected={}".format(
        name, diamond_height, height, len(solids), len(rejected)))
    if rejected:
        warn("pattern_full_v4: celulas_rejeitadas={}".format(",".join(rejected)))
    return run


def resolve_cut_selection(doc):
    wrap = None
    pattern = None
    for obj in Gui.Selection.getSelection():
        if (getattr(obj, "MapAlgorithm", "") == SCHEMA or
                getattr(obj, "WrapAlgorithm", "") == SCHEMA):
            wrap = obj
        if (getattr(obj, "PatternId", "") and
                getattr(obj, "PatternMapSource", "")):
            pattern = obj
        elif getattr(obj, "DiamondPatternAlgorithm", "") == "WRAP_CARRIER_V4_FULL":
            pattern = obj
    if wrap is None or pattern is None:
        fail("Selecione o Pattern Full V4 e o Wrap V4 correspondentes.")
    pattern_map = (getattr(pattern, "PatternMapSource", "") or
                   getattr(pattern, "DiamondPatternWrapSource", ""))
    if pattern_map != wrap.Name:
        fail("O Pattern Full V4 nao pertence ao Wrap V4 selecionado.")
    return wrap, pattern


def create_cut():
    doc = App.ActiveDocument
    if doc is None:
        fail("Abra um documento antes de executar o Cut V4.")
    wrap, pattern = resolve_cut_selection(doc)
    payload = load_chunks(wrap, "WrapCarrierChunks")
    cell_payload = load_chunks(pattern, "DiamondPatternCellChunks")
    pattern_height = length_value(
        getattr(pattern, "PatternHeight", cell_payload.get("parameters", {}).get(
            "height", DEFAULT_PATTERN_HEIGHT)))
    diamond_height = length_value(
        getattr(pattern, "DiamondHeight", cell_payload.get("parameters", {}).get(
            "diamond_height", GRID_HEIGHT)), GRID_HEIGHT)
    allowed = {record["id"] for record in cell_payload["cells"]}
    apex = {record["id"]: record["apex"] for record in cell_payload["cells"]}
    solids, records, rejected = build_cut_cells_from_full(
        doc, payload, pattern, cell_payload, pattern_height)
    algorithm = "WRAP_CARRIER_V4_PHYSICAL_NORMAL_CUT"
    if not solids:
        warn("cut_v4: corte_fisico_falhou; tentando_rebuild_antigo")
        solids, records, rejected = build_cut_cells(
            payload, allowed, apex, diamond_height=diamond_height)
        algorithm = "WRAP_CARRIER_V4_CUT_REBUILD_FALLBACK"
    if not solids:
        fail("Cut V4 nao gerou solidos validos.")
    name = next_name(doc, CUT_PREFIX)
    run = doc.addObject("PartDesign::Feature", name)
    run.Label = name + " Solid"
    run.Shape = Part.makeCompound(solids)
    add_string(run, "DiamondPatternVersion", "Cut From Wrap V4", "Diamond Pattern V4")
    add_string(run, "DiamondPatternAlgorithm", algorithm, "Diamond Pattern V4")
    add_string(run, "DiamondPatternWrapSource", wrap.Name, "Diamond Pattern V4")
    add_string(run, "DiamondPatternFullSource", pattern.Name, "Diamond Pattern V4")
    add_string(run, "PatternId", "diamond", "Pattern Surface")
    add_string(run, "PatternMapSource", wrap.Name, "Pattern Surface")
    add_string(run, "PatternSource", pattern.Name, "Pattern Surface")
    add_length(run, "PatternHeight", pattern_height, "Pattern Surface")
    add_length(run, "DiamondHeight", diamond_height, "Pattern Surface")
    add_string(run, "DiamondPatternRejected", ";".join(rejected), "Diamond Pattern V4")
    add_chunks(run, "DiamondPatternCellChunks", {
        "cells": records,
        "parameters": {
            "height": pattern_height,
            "pyramid_height": pattern_height,
            "diamond_height": diamond_height,
        },
    }, "Diamond Pattern V4")
    doc.recompute()
    console("cut_v4: run={} algoritmo={} solids={} rejected={}".format(name, algorithm, len(solids), len(rejected)))
    if rejected:
        warn("cut_v4: celulas_rejeitadas={}".format(",".join(rejected)))
    return run


def run_guard(function, label):
    try:
        return function()
    except Exception:
        message = "Erro em {}:\n{}".format(label, traceback.format_exc())
        App.Console.PrintError(message + "\n")
        try:
            from PySide import QtGui
            QtGui.QMessageBox.critical(None, label, message)
        except Exception:
            pass
        return None
