"""Transient logical phase alignment for separate closed assembly components.

Map Faces intentionally owns one connected atlas.  A drawer and its enclosing
body are separate solids, so the Blender bridge aligns their *job copies* from
the exterior boundary geometry instead of mutating either stored Map Faces
payload.  The resulting payloads still own independent physical carriers.
"""

from __future__ import division

import copy
import math


EPS = 1.0e-8


def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(len(a)))


def _dot(a, b):
    return sum(left * right for left, right in zip(a, b))


def _length(vector):
    return math.sqrt(_dot(vector, vector))


def _unit(vector):
    length = _length(vector)
    return None if length <= EPS else tuple(value / length for value in vector)


def _midpoint(a, b):
    return tuple((float(a[i]) + float(b[i])) * 0.5 for i in range(len(a)))


def _segments(payload):
    """Read the native map rim, with a carrier fallback for legacy maps."""
    result = []
    for record in payload.get("external_segments", []) or []:
        a, b = record.get("a"), record.get("b")
        if a and b and a.get("p") and b.get("p") and a.get("q") and b.get("q"):
            result.append((a, b))
    if result:
        return result
    edges = {}
    for triangle in payload.get("carrier_triangles", payload.get("triangles", [])):
        vertices = triangle.get("v", [])
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            key = tuple(sorted((tuple(round(v, 6) for v in a["p"]),
                                tuple(round(v, 6) for v in b["p"])) ))
            edges.setdefault(key, []).append((a, b))
    return [items[0] for items in edges.values() if len(items) == 1]


def _candidate(reference, moving):
    """Return the best compatible edge pair using physical assembly space."""
    best = None
    reference_segments = _segments(reference)
    moving_segments = _segments(moving)
    # Dense curved maps can expose thousands of tessellation edge segments.
    # Uniform sampling retains the geometry decision while bounding job setup.
    step_a = max(1, len(reference_segments) // 600)
    step_b = max(1, len(moving_segments) // 600)
    for ra, rb in reference_segments[::step_a]:
        rp = _sub(rb["p"], ra["p"])
        rq = _sub(rb["q"], ra["q"])
        rp_unit, rq_length = _unit(rp), _length(rq)
        if rp_unit is None or rq_length <= EPS:
            continue
        for ma, mb in moving_segments[::step_b]:
            mp = _sub(mb["p"], ma["p"])
            mq = _sub(mb["q"], ma["q"])
            mp_unit, mq_length = _unit(mp), _length(mq)
            if mp_unit is None or mq_length <= EPS:
                continue
            parallel = abs(_dot(rp_unit, mp_unit))
            ratio = min(rq_length, mq_length) / max(rq_length, mq_length)
            if parallel < 0.96 or ratio < 0.80:
                continue
            # Pair the endpoint order that describes the closest closed pose.
            direct = _length(_sub(ra["p"], ma["p"])) + _length(_sub(rb["p"], mb["p"]))
            reverse = _length(_sub(ra["p"], mb["p"])) + _length(_sub(rb["p"], ma["p"]))
            if reverse < direct:
                ma, mb = mb, ma
                mq = _sub(mb["q"], ma["q"])
            distance = min(direct, reverse) * 0.5
            # Prefer the nearest compatible physical rim; ties prefer a long
            # common edge, which is less ambiguous at rounded corners.
            score = (distance, -min(_length(rp), _length(mp)))
            if best is None or score < best[0]:
                best = (score, (ra, rb, ma, mb))
    if best is None:
        raise ValueError(
            "The selected maps have no compatible nearby exterior boundaries. "
            "Place the moving parts in their closed position and map matching exterior faces.")
    return best[1]


def _rotation(source_vector, target_vector):
    source = _unit(source_vector)
    target = _unit(target_vector)
    if source is None or target is None:
        raise ValueError("A shared-phase boundary has no usable logical direction.")
    cosine = source[0] * target[0] + source[1] * target[1]
    sine = source[0] * target[1] - source[1] * target[0]
    return ((cosine, -sine), (sine, cosine))


def _apply(point, matrix, offset):
    return [matrix[0][0] * float(point[0]) + matrix[0][1] * float(point[1]) + offset[0],
            matrix[1][0] * float(point[0]) + matrix[1][1] * float(point[1]) + offset[1]]


def _transform_payload(payload, matrix, offset):
    result = copy.deepcopy(payload)
    carrier = result.get("carrier_triangles", result.get("triangles", []))
    # The worker only consumes carrier triangles, but retain the legacy alias
    # as the same data for modules that inspect a packaged job.
    seen = set()
    def transform_vertex(vertex):
        if id(vertex) not in seen:
            seen.add(id(vertex))
            vertex["q"] = _apply(vertex["q"], matrix, offset)
    for triangle in carrier:
        for vertex in triangle.get("v", []):
            transform_vertex(vertex)
    result["carrier_triangles"] = carrier
    result["triangles"] = carrier
    for segment in result.get("external_segments", []) or []:
        for key in ("a", "b"):
            if key in segment and segment[key].get("q"):
                transform_vertex(segment[key])
    qs = [vertex["q"] for triangle in carrier for vertex in triangle.get("v", [])]
    if not qs:
        raise ValueError("A selected map has no logical carrier vertices.")
    result["bounds"] = [min(q[0] for q in qs), max(q[0] for q in qs),
                        min(q[1] for q in qs), max(q[1] for q in qs)]
    grid = dict(result.get("grid", {}) or {})
    grid["origin"] = _apply(grid.get("origin", [0.0, 0.0]), matrix, offset)
    result["grid"] = grid
    # A rotated periodic axis has no single x-period in the Diamond backend.
    # Rejecting it is safer than silently changing module closure.
    if result.get("periodic_adjustments"):
        axis = matrix[0][0], matrix[1][0]
        if abs(abs(axis[0]) - 1.0) > 1.0e-6 or abs(axis[1]) > 1.0e-6:
            raise ValueError("Shared phase currently requires periodic map axes to align with each other.")
        for record in result["periodic_adjustments"]:
            if int(record.get("axis", 0)) == 0:
                record["lower"] = result["bounds"][0]
    return result


def align(payloads):
    """Return job-local payloads sharing the reference map's Diamond phase.

    The first selected map supplies the phase.  Each later map is registered to
    the nearest compatible external rim of the reference map.  No FreeCAD
    object, saved map payload, or body placement is modified.
    """
    if not payloads:
        raise ValueError("Select at least one mapped surface.")
    result = [copy.deepcopy(payloads[0])]
    records = [{"reference": 0, "rotation": [[1.0, 0.0], [0.0, 1.0]],
                "translation": [0.0, 0.0]}]
    for index, payload in enumerate(payloads[1:], 1):
        ra, rb, ma, mb = _candidate(result[0], payload)
        matrix = _rotation(_sub(mb["q"], ma["q"]), _sub(rb["q"], ra["q"]))
        mapped_mid = _apply(_midpoint(ma["q"], mb["q"]), matrix, (0.0, 0.0))
        target_mid = _midpoint(ra["q"], rb["q"])
        offset = (target_mid[0] - mapped_mid[0], target_mid[1] - mapped_mid[1])
        result.append(_transform_payload(payload, matrix, offset))
        records.append({"reference": 0, "rotation": [list(matrix[0]), list(matrix[1])],
                        "translation": list(offset)})
    return result, records
