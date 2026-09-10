"""Closed, carrier-driven diagonal rib relief mesh for the Blender backend.

The pattern is a continuous logical height field.  It is intentionally not a
collection of independent tubes: clipped samples share their boundary vertices
so the surface remains closed on curved maps, fillets and trimmed rims.
"""

import importlib.util
import math
from collections import Counter
from pathlib import Path


_SPEC = importlib.util.spec_from_file_location(
    "auzyron_diamond_geometry_helpers", Path(__file__).with_name("geometry_closed.py"))
_HELPERS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_HELPERS)
EPS = _HELPERS.EPS
_add = _HELPERS._add
_barycentric = _HELPERS._barycentric
_clip = _HELPERS._clip
_cross = _HELPERS._cross
_interpolate = _HELPERS._interpolate
_scale = _HELPERS._scale
_sub = _HELPERS._sub


def dimensions(payload, params):
    pitch = float(params.get("rib_pitch", 12.0))
    height = float(params.get("rib_height", 1.5))
    angle = float(params.get("rib_angle", 45.0))
    resolution = int(params.get("resolution", 8))
    finish_offset = float(params.get("finish_offset", 0.045))
    contact = float(params.get("contact", 0.25))
    if not all(math.isfinite(value) and value > 0.0
               for value in (pitch, height, finish_offset, contact)):
        raise ValueError("Rib dimensions must be finite and positive.")
    if not math.isfinite(angle) or not -89.0 <= angle <= 89.0:
        raise ValueError("Rib angle must be between -89 and 89 degrees.")
    if not 3 <= resolution <= 32:
        raise ValueError("Rib resolution must be between 3 and 32.")
    return {"pitch": pitch, "height": height, "angle": math.radians(angle),
            "resolution": resolution, "finish_offset": finish_offset,
            "contact": contact}


def _period(payload):
    adjustments = payload.get("periodic_adjustments", []) or []
    if len(adjustments) == 1 and int(adjustments[0].get("axis", -1)) == 0:
        return float(adjustments[0]["period"]), float(adjustments[0].get("lower", 0.0))
    return None, None


def build(payload, params):
    dim = dimensions(payload, params)
    carrier = list(payload.get("carrier_triangles", payload.get("triangles", [])))
    bounds = payload.get("bounds", []) or []
    if not carrier or len(bounds) != 4:
        raise ValueError("The map has no valid physical carrier.")
    min_x, max_x, min_y, max_y = (float(value) for value in bounds)
    period, period_origin = _period(payload)
    origin = (period_origin if period is not None else min_x, min_y)
    cosine, sine = math.cos(dim["angle"]), math.sin(dim["angle"])
    # A periodic wall must start and finish on the same rib phase.  The nearest
    # whole number of waves is fitted only in the periodic logical direction.
    x_frequency = cosine / dim["pitch"]
    if period is not None:
        x_frequency = round(period * x_frequency) / period

    def phase(point):
        return ((point[0] - origin[0]) * x_frequency +
                (point[1] - origin[1]) * sine / dim["pitch"])

    def relief(point):
        # Cosine has a zero-slope crest and valley.  This gives each printed
        # rib a smooth, intentional profile rather than a triangulation seam.
        return dim["height"] * 0.5 * (1.0 + math.cos(2.0 * math.pi * phase(point)))

    domains = list(carrier)
    if period is not None:
        for offset in (-period, period):
            for item in carrier:
                clone = dict(item)
                clone["v"] = [dict(vertex, q=[vertex["q"][0] + offset, vertex["q"][1]])
                              for vertex in item["v"]]
                domains.append(clone)

    # Spatial buckets keep clipping tied to local carrier triangles instead of
    # scanning the entire CAD tessellation for every rib sample.
    step_y = dim["pitch"] / dim["resolution"]
    # Make periodic samples land exactly on both sides of the logical seam.
    # A nominal pitch subdivision rarely divides a circumference exactly.
    step_x = step_y if period is None else period / max(1, round(period / step_y))
    buckets = {}
    for index, item in enumerate(domains):
        points = [vertex["q"] for vertex in item.get("v", [])]
        if len(points) != 3:
            continue
        low_x, high_x = min(p[0] for p in points), max(p[0] for p in points)
        low_y, high_y = min(p[1] for p in points), max(p[1] for p in points)
        for bx in range(math.floor((low_x-min_x)/step_x), math.floor((high_x-min_x)/step_x)+1):
            for by in range(math.floor((low_y-min_y)/step_y), math.floor((high_y-min_y)/step_y)+1):
                buckets.setdefault((bx, by), []).append(index)

    def candidates(triangle):
        low_x, high_x = min(p[0] for p in triangle), max(p[0] for p in triangle)
        low_y, high_y = min(p[1] for p in triangle), max(p[1] for p in triangle)
        result = set()
        for bx in range(math.floor((low_x-min_x)/step_x), math.floor((high_x-min_x)/step_x)+1):
            for by in range(math.floor((low_y-min_y)/step_y), math.floor((high_y-min_y)/step_y)+1):
                result.update(buckets.get((bx, by), []))
        return (domains[index] for index in result)

    def canonical(point):
        if period is None:
            return tuple(point)
        x = (point[0] - period_origin) % period
        if min(x, period-x) < 1.0e-7:
            x = 0.0
        return (period_origin + x, point[1])

    def locate(point):
        point = canonical(point)
        bx, by = math.floor((point[0]-min_x)/step_x), math.floor((point[1]-min_y)/step_y)
        options = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                options.update(buckets.get((bx+dx, by+dy), []))
        best, margin = None, -float("inf")
        for index in options:
            item = domains[index]
            weights = _barycentric(point, [vertex["q"] for vertex in item["v"]])
            if weights is not None and min(weights) >= -1.0e-7 and min(weights) > margin:
                best, margin = item, min(weights)
        return best

    vertices, backing, faces, facet_ids, vertex_cache = [], [], [], [], {}

    def add_vertex(point):
        logical = canonical(point)
        key = (round(logical[0], 5), round(logical[1], 5))
        if key in vertex_cache:
            return vertex_cache[key]
        source = locate(logical)
        mapped = _interpolate(logical, source) if source else None
        if mapped is None:
            return None
        physical, normal = mapped
        outer = _add(physical, _scale(normal, relief(logical) + dim["finish_offset"]))
        inner = _sub(physical, _scale(normal, dim["contact"]))
        vertex_cache[key] = len(vertices)
        vertices.append(outer)
        backing.append(inner)
        return vertex_cache[key]

    col0, col1 = math.floor((min_x-origin[0])/step_x)-1, math.ceil((max_x-origin[0])/step_x)+1
    row0, row1 = math.floor((min_y-origin[1])/step_y)-1, math.ceil((max_y-origin[1])/step_y)+1
    facet = 0
    for row in range(row0, row1):
        for column in range(col0, col1):
            x0, x1 = origin[0] + column*step_x, origin[0] + (column+1)*step_x
            y0, y1 = origin[1] + row*step_y, origin[1] + (row+1)*step_y
            # geometry_closed._clip carries a third logical component through
            # intersections.  It is unused by the rib phase, but keeping it
            # here gives every clipped boundary sample the same representation.
            for sample in (((x0,y0,0.0), (x1,y0,0.0), (x0,y1,0.0)),
                           ((x1,y0,0.0), (x1,y1,0.0), (x0,y1,0.0))):
                if period is not None:
                    center_x = sum(p[0] for p in sample)/3.0
                    if not period_origin-EPS <= center_x < period_origin+period-EPS:
                        continue
                clips = []
                for carrier_triangle in candidates(sample):
                    clipped = _clip(list(sample), [vertex["q"] for vertex in carrier_triangle["v"]])
                    if len(clipped) >= 3:
                        clips.append(clipped)
                # Carrier triangles are a physical domain, never the visual
                # pattern topology. A wholly-covered rib sample therefore
                # stays one sample, rather than inheriting seams or duplicate
                # fragments from the source CAD tessellation.
                covered_area = sum(abs(_cross(clipped[0], clipped[index], clipped[index+1]))
                                   for clipped in clips for index in range(1, len(clipped)-1))
                if abs(covered_area - abs(_cross(*sample))) <= 1.0e-8:
                    clips = [list(sample)]
                for clipped in clips:
                    for index in range(1, len(clipped)-1):
                        triangle = (clipped[0], clipped[index], clipped[index+1])
                        if abs(_cross(*triangle)) <= EPS:
                            continue
                        ids = [add_vertex(point) for point in triangle]
                        if None not in ids and len(set(ids)) == 3:
                            faces.append(tuple(ids))
                            facet_ids.append(facet + 1)
                facet += 1
    if not faces:
        raise ValueError("No rib sample intersects the mapped carrier.")
    used = sorted({index for face in faces for index in face})
    remap = {old: new for new, old in enumerate(used)}
    vertices = [vertices[index] for index in used]
    backing = [backing[index] for index in used]
    faces = [tuple(remap[index] for index in face) for face in faces]
    outer_faces = list(faces)
    offset = len(vertices)
    vertices.extend(backing)
    faces.extend(tuple(offset+index for index in reversed(face)) for face in outer_faces)
    edge_counts = Counter(tuple(sorted(edge)) for face in outer_faces for edge in zip(face, face[1:]+face[:1]))
    for face in outer_faces:
        for left, right in zip(face, face[1:]+face[:1]):
            if edge_counts[tuple(sorted((left, right)))] == 1:
                faces.append((right, left, offset+left, offset+right))
                facet_ids.append(0)
    counts = Counter(tuple(sorted(edge)) for face in faces for edge in zip(face, face[1:]+face[:1]))
    bad = sum(value != 2 for value in counts.values())
    return {"vertices": vertices, "faces": faces,
            "facet_ids": facet_ids + [0] * (len(faces)-len(facet_ids)),
            "smooth_relief": True,
            "weld_relief": True,
            "cleanup_after_clip": False,
            "stats": {"algorithm": "diagonal_ribs_heightfield", "outer_faces": len(outer_faces),
                      "faces": len(faces), "vertices": len(vertices), "facets": facet,
                      "bad_edges_before_weld": bad}}
