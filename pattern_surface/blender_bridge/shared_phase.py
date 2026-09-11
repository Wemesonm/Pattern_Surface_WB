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


def _multiply(left, right):
    return ((left[0][0] * right[0][0] + left[0][1] * right[1][0],
             left[0][0] * right[0][1] + left[0][1] * right[1][1]),
            (left[1][0] * right[0][0] + left[1][1] * right[1][0],
             left[1][0] * right[0][1] + left[1][1] * right[1][1]))


def _edge_side(payload, a, b):
    """Return the logical side occupied by a carrier beside physical edge AB."""
    edge = _sub(b["p"], a["p"])
    if _length(edge) <= EPS:
        return None
    for triangle in payload.get("carrier_triangles", payload.get("triangles", [])):
        vertices = triangle.get("v", [])
        if len(vertices) != 3:
            continue
        matched = []
        for vertex in vertices:
            if _length(_sub(vertex.get("p", ()), a["p"])) <= 1.0e-5:
                matched.append((0, vertex))
            elif _length(_sub(vertex.get("p", ()), b["p"])) <= 1.0e-5:
                matched.append((1, vertex))
        if len(matched) != 2 or {item[0] for item in matched} != {0, 1}:
            continue
        third = next(vertex for vertex in vertices if vertex not in [item[1] for item in matched])
        q_edge = _sub(b["q"], a["q"])
        q_inner = _sub(third["q"], a["q"])
        side = q_edge[0] * q_inner[1] - q_edge[1] * q_inner[0]
        if abs(side) > EPS:
            return side
    return None


def _edge_isometry(source_vector, target_vector, reflect=False):
    """Map a source rim tangent to target, optionally unfolding its interior."""
    matrix = _rotation(source_vector, target_vector)
    if not reflect:
        return matrix
    target = _unit(target_vector)
    if target is None:
        raise ValueError("A shared-phase boundary has no usable logical direction.")
    # Reflection in the target edge keeps its tangent fixed and moves the
    # moving carrier to the opposite half-plane of the shared logical seam.
    x, y = target
    mirror = ((2.0 * x * x - 1.0, 2.0 * x * y),
              (2.0 * x * y, 2.0 * y * y - 1.0))
    return _multiply(mirror, matrix)


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

    The first selected map supplies the phase.  Every later map is registered
    to the nearest compatible rim of *an already aligned neighbour*.  This
    grows a physical adjacency tree instead of forcing distant regions to
    match the first selected map directly.  No FreeCAD object, saved map
    payload, or body placement is modified.
    """
    if not payloads:
        raise ValueError("Select at least one mapped surface.")
    aligned = {0: copy.deepcopy(payloads[0])}
    records = {0: {"reference": 0, "rotation": [[1.0, 0.0], [0.0, 1.0]],
                   "translation": [0.0, 0.0]}}
    pending = list(range(1, len(payloads)))
    while pending:
        best = None
        for reference_index in sorted(aligned):
            reference = aligned[reference_index]
            for moving_index in pending:
                try:
                    candidate = _candidate(reference, payloads[moving_index])
                except ValueError:
                    continue
                ra, rb, ma, mb = candidate
                # `_candidate` chooses its pair by physical proximity.  Keep
                # the same ordering here so the next map joins the closest
                # already aligned neighbour, even when it was selected later.
                distance = (_length(_sub(ra["p"], ma["p"])) +
                            _length(_sub(rb["p"], mb["p"]))) * 0.5
                score = (distance, reference_index, moving_index)
                if best is None or score < best[0]:
                    best = (score, reference_index, moving_index, candidate)
        if best is None:
            raise ValueError(
                "The selected maps have no compatible nearby exterior boundaries. "
                "Place the moving parts in their closed position and map matching exterior faces.")
        _score, reference_index, index, (ra, rb, ma, mb) = best
        reference_side = _edge_side(aligned[reference_index], ra, rb)
        moving_side = _edge_side(payloads[index], ma, mb)
        # Two independently created charts can put their carrier interiors on
        # the same q side of a physical split. A rotation aligns the rim but
        # leaves those domains overlapping; unfold the moving chart by a
        # reflection so the Diamond cells complete each other at the seam.
        reflect = (reference_side is not None and moving_side is not None and
                   reference_side * moving_side > 0.0)
        matrix = _edge_isometry(_sub(mb["q"], ma["q"]), _sub(rb["q"], ra["q"]), reflect)
        mapped_mid = _apply(_midpoint(ma["q"], mb["q"]), matrix, (0.0, 0.0))
        target_mid = _midpoint(ra["q"], rb["q"])
        offset = (target_mid[0] - mapped_mid[0], target_mid[1] - mapped_mid[1])
        aligned[index] = _transform_payload(payloads[index], matrix, offset)
        records[index] = {"reference": reference_index,
                          "rotation": [list(matrix[0]), list(matrix[1])],
                          "translation": list(offset), "reflected": reflect}
        pending.remove(index)
    return [aligned[index] for index in range(len(payloads))], [records[index] for index in range(len(payloads))]


def assembly_cycle_period(payloads, tolerance=1.0e-5):
    """Find a logical wrap identified by coincident physical assembly rims.

    Registration aligns a spanning tree. A second shared rim can close a
    cycle, leaving a nonzero logical translation equal to the full perimeter.
    Require two distinct physical samples per translation to avoid mistaking
    a single touching corner for a closure. Coordinates here are map q, never
    a chosen physical world direction.
    """
    rims = []
    for payload in payloads:
        points = {}
        for a, b in _segments(payload):
            for vertex in (a, b):
                key = tuple(round(float(x) / tolerance) for x in vertex['p'])
                points[key] = vertex
        rims.append(points)
    cycles = []
    for i, left in enumerate(rims):
        for right in rims[i+1:]:
            groups = {}
            for key in left.keys() & right.keys():
                delta = _sub(left[key]['q'], right[key]['q'])
                if _length(delta) <= tolerance * 10:
                    continue
                if delta[0] < 0 or (abs(delta[0]) <= tolerance and delta[1] < 0):
                    delta = tuple(-x for x in delta)
                group = tuple(round(x / (tolerance * 10)) for x in delta)
                groups.setdefault(group, []).append((delta, left[key]['p']))
            for samples in groups.values():
                if len(samples) < 2 or max(_length(_sub(p, samples[0][1]))
                                           for _, p in samples) <= tolerance * 10:
                    continue
                delta = samples[0][0]
                if abs(delta[1]) > tolerance * 10 or delta[0] <= tolerance * 10:
                    raise ValueError('Assembly closure has incompatible logical row directions.')
                cycles.append(delta[0])
    if not cycles:
        return None
    period = min(cycles)
    if any(abs(value - round(value / period) * period) > tolerance * 10
           for value in cycles):
        raise ValueError('Assembly maps have incompatible logical closure periods.')
    return period
