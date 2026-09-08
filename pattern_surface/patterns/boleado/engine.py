"""Boleado geometry; it owns no Diamond lattice or implementation details."""

import math
import FreeCAD as App
import Part

from ... import core_engine
from ...common.identifiers import SCHEMA, is_supported_schema, short_label
from ...common.properties_core import add_length, add_string, next_name
from ...common.ownership import organize_derived_object
from ...common.ownership import map_from_selection_object
from ...core_engine import add_chunks, load_chunks
from .metadata import LABEL, PATTERN_ID


ALGORITHM = "AUZYRON_BOLEADO_MAPPED_HEMISPHERES_V2"
EDGE_REDUCTION = 0.55
EDGE_ANGLE_LIMIT = math.radians(8.0)


def _map_run(map_object):
    return map_from_selection_object(map_object)


def _valid(values):
    required = ("bump_radius", "bump_height", "spacing_x", "spacing_y",
                "row_offset", "penetration")
    if any(not math.isfinite(float(values[key])) for key in required):
        return False
    return (values["bump_radius"] > 0.0 and values["bump_height"] > 0.0 and
            values["spacing_x"] > 0.0 and values["spacing_y"] > 0.0 and
            0.0 <= values["row_offset"] <= 1.0 and
            values["penetration"] >= 0.0 and
            values["bump_height"] <= 2.0 * values["bump_radius"])


def _external_hemisphere(point, normal, radius, penetration):
    """Create only the outward half of a mapped sphere.

    The clipping plane is the source surface.  The sphere center is moved
    inward by penetration, so the result remains attached without carrying a
    hidden full sphere into Trim Surface.
    """
    center = point - normal * penetration
    sphere = Part.makeSphere(radius, center)
    size = 2.0 * radius + 0.2
    clip = Part.makeBox(size, size, radius + 0.1,
                        App.Vector(-size / 2.0, -size / 2.0, 0.0))
    clip.Placement = App.Placement(
        point, App.Rotation(App.Vector(0.0, 0.0, 1.0), normal))
    result = sphere.common(clip)
    return result if result is not None and not result.isNull() else None


def _mean_normal(triangle):
    normals = [item.get("n") for item in triangle.get("v", [])]
    normals = [normal for normal in normals if normal is not None]
    if not normals:
        return None
    vector = sum((core_engine.v3(normal) for normal in normals), App.Vector(0, 0, 0))
    length = vector.Length
    return vector / length if length > 1.0e-9 else None


def _logical_vector(point):
    return App.Vector(float(point[0]), float(point[1]), 0.0)


def _transition_segments(payload):
    """Return logical edges where adjacent mapped faces form a crease."""
    occurrences = {}
    for triangle in payload.get("triangles", []):
        vertices = triangle.get("v", [])
        if len(vertices) != 3:
            continue
        normal = _mean_normal(triangle)
        if normal is None:
            continue
        for index in range(3):
            left = vertices[index]["q"]
            right = vertices[(index + 1) % 3]["q"]
            key = tuple(sorted((core_engine.qkey2(left), core_engine.qkey2(right))))
            occurrences.setdefault(key, []).append((left, right, triangle, normal))

    segments = []
    for values in occurrences.values():
        for index, current in enumerate(values):
            for other in values[index + 1:]:
                if current[2].get("face") == other[2].get("face"):
                    continue
                dot = max(-1.0, min(1.0, current[3].dot(other[3])))
                angle = math.acos(dot)
                if angle < EDGE_ANGLE_LIMIT:
                    continue
                segments.append((_logical_vector(current[0]), _logical_vector(current[1]), angle))
    return segments


def _distance_to_segment(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length2 = dx * dx + dy * dy
    if length2 <= 1.0e-12:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    ratio = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length2
    ratio = max(0.0, min(1.0, ratio))
    closest_x, closest_y = start[0] + ratio * dx, start[1] + ratio * dy
    return math.hypot(point[0] - closest_x, point[1] - closest_y)


def _edge_adjusted_radius(logical_point, radius, spacing_x, spacing_y, segments):
    """Reduce bump size near non-tangent face transitions."""
    if not segments:
        return radius
    influence = max(radius * 1.25, min(spacing_x, spacing_y) * 0.72)
    nearest = None
    for start, end, angle in segments:
        distance = _distance_to_segment(logical_point, start, end)
        if nearest is None or distance < nearest[0]:
            nearest = (distance, angle)
    if nearest is None or nearest[0] >= influence:
        return radius
    blend = max(0.0, min(1.0, nearest[0] / influence))
    severity = max(0.0, min(1.0, nearest[1] / math.pi))
    minimum = 1.0 - (1.0 - EDGE_REDUCTION) * (0.55 + 0.45 * severity)
    return radius * (minimum + (1.0 - minimum) * blend)


def create_pattern(map_object, values):
    doc = App.ActiveDocument
    if doc is None:
        raise RuntimeError("Abra um documento antes de executar o Boleado Pattern.")
    run = _map_run(map_object)
    if run is None:
        raise RuntimeError("Selecione um Mapped Surface compatível.")
    payload = load_chunks(run, "MapPayloadChunks")
    if not is_supported_schema(payload.get("schema")):
        raise RuntimeError("O objeto selecionado não é um Mapped Surface válido.")
    if not _valid(values):
        raise RuntimeError("Parâmetros inválidos do Boleado Pattern.")

    x0, x1, y0, y1 = [float(value) for value in payload["bounds"]]
    sx, sy = float(values["spacing_x"]), float(values["spacing_y"])
    radius, height = float(values["bump_radius"]), float(values["bump_height"])
    offset_factor = float(values["row_offset"])
    penetration = float(values["penetration"])
    context = core_engine.build_mapping_context(payload, True)
    transition_segments = _transition_segments(payload)
    source_solids = core_engine.source_solids_by_face(doc, payload).values()
    solids, cells, rejected = [], [], []
    row0 = int(math.floor(y0 / sy)) - 1
    row1 = int(math.ceil(y1 / sy)) + 1
    col0 = int(math.floor(x0 / sx)) - 1
    col1 = int(math.ceil(x1 / sx)) + 1
    for row in range(row0, row1 + 1):
        shift = offset_factor * sx if row % 2 else 0.0
        for col in range(col0, col1 + 1):
            q = [col * sx + shift, row * sy]
            mapped = core_engine.map_context_point(q, context)
            if mapped is None or mapped[1] is None:
                continue
            point, normal = mapped
            normal = core_engine.outside_normal_for_point(point, normal, source_solids)
            if normal is None:
                rejected.append("r{}_c{}".format(row, col))
                continue
            # The clipping plane is the mapped wall, so only the outward
            # hemisphere is retained. Penetration moves its center inward.
            local_radius = _edge_adjusted_radius(
                q, radius, sx, sy, transition_segments)
            sphere = _external_hemisphere(point, normal, local_radius, penetration)
            if sphere is None or not sphere.isValid():
                rejected.append("r{}_c{}".format(row, col))
                continue
            identifier = "r{}_c{}".format(row, col)
            solids.append(sphere)
            cells.append({
                "id": identifier,
                "logical_center": q,
                "physical_center": core_engine.xyz(point - normal * penetration),
                "normal": core_engine.xyz(normal),
                "radius": local_radius,
                "height": local_radius,
                "edge_adjusted": local_radius < radius - 1.0e-7,
            })

    if not solids:
        raise RuntimeError("Boleado Pattern não gerou saliências válidas.")
    name = next_name(doc, "BoleadoPattern")
    result = doc.addObject("PartDesign::Feature", name)
    result.Label = short_label(LABEL, name)
    result.Shape = Part.makeCompound(solids)
    add_string(result, "PatternId", PATTERN_ID, "Pattern Surface")
    add_string(result, "PatternMapSource", run.Name, "Pattern Surface")
    add_length(result, "PatternHeight", height, "Pattern Surface")
    add_string(result, "BoleadoPatternAlgorithm", ALGORITHM, "Boleado Pattern")
    for key, label in (("bump_radius", "BumpRadius"), ("bump_height", "BumpHeight"),
                       ("spacing_x", "SpacingX"), ("spacing_y", "SpacingY"),
                       ("penetration", "SurfacePenetration")):
        add_length(result, label, values[key], "Boleado Pattern")
    add_chunks(result, "PatternCellChunks", {
        "schema": SCHEMA, "version": 1, "pattern_id": PATTERN_ID,
        "map_source": run.Name, "map_schema": payload.get("schema"),
        "parameters": dict(values), "cells": cells,
        "rejected_cells": rejected,
        "generation": {"algorithm": ALGORITHM, "elapsed_ms": 0.0},
    }, "Boleado Pattern")
    organize_derived_object(result, run)
    doc.recompute()
    return result
