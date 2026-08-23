"""Shared-edge sampling primitives for Map Faces seam fitting."""

import math


def _core():
    from .. import core_engine
    return core_engine


def edge_samples(edge, spacing=None):
    spacing = _core().MAX_EDGE if spacing is None else spacing
    count = max(3, int(math.ceil(max(edge.Length, spacing) / spacing)) + 1)
    return list(edge.discretize(Number=count))


def apply_matrix(matrix, local):
    return [matrix[0] * local[0] + matrix[1] * local[1] + matrix[4],
            matrix[2] * local[0] + matrix[3] * local[1] + matrix[5]]


def aligned_edge_samples(left_edge, right_edge):
    core = _core()
    ppoints = edge_samples(left_edge, max(core.MAX_EDGE, left_edge.Length / 16.0))
    tpoints = edge_samples(right_edge, max(core.MAX_EDGE, right_edge.Length / 16.0))
    if ppoints[0].distanceToPoint(tpoints[0]) > ppoints[0].distanceToPoint(tpoints[-1]):
        tpoints.reverse()
    return ppoints, tpoints


def seam_limit(left_entry, right_entry, left_edge, right_edge):
    core = _core()
    limit = 0.05
    if (not isinstance(left_entry["face"].Surface, core.Part.Plane) or
            not isinstance(right_entry["face"].Surface, core.Part.Plane)):
        limit = max(limit, min(left_edge.Length, right_edge.Length) * 0.35)
    return limit


def neighbor_transform_candidates(placed, target, placed_edge, target_edge):
    core = _core()
    ppoints, tpoints = aligned_edge_samples(placed_edge, target_edge)
    p0 = core.apply_transform(placed, core.local_xy_raw(placed, ppoints[0]))
    p1 = core.apply_transform(placed, core.local_xy_raw(placed, ppoints[-1]))
    t0 = core.local_xy_raw(target, tpoints[0])
    t1 = core.local_xy_raw(target, tpoints[-1])
    sx, sy = t1[0] - t0[0], t1[1] - t0[1]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    sl, dl = math.hypot(sx, sy), math.hypot(dx, dy)
    curved_seam = (not isinstance(placed["face"].Surface, core.Part.Plane) or
                   not isinstance(target["face"].Surface, core.Part.Plane))
    if sl <= 1.0e-8 or dl <= 1.0e-8:
        return []
    metric_error = abs(sl - dl) / max(sl, dl)
    if metric_error > 0.05 and not curved_seam:
        return []
    tangent_scale = dl / sl if curved_seam else 1.0
    if curved_seam and abs(dl - sl) > 0.05:
        core.console("map_faces: emenda_curva_escala_tangencial {} <-> {} sl={:.4f} dl={:.4f} escala={:.6f}".format(
            placed["sub"], target["sub"], sl, dl, tangent_scale))
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
    placed_center = core.apply_transform(placed, [placed["width"] * 0.5, placed["height"] * 0.5])
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
    core = _core()
    ppoints, tpoints = aligned_edge_samples(placed_edge, target_edge)
    count = min(len(ppoints), len(tpoints))
    if count <= 0:
        return None
    errors = []
    for index in range(count):
        pi = int(round(index * (len(ppoints) - 1) / max(count - 1, 1)))
        ti = int(round(index * (len(tpoints) - 1) / max(count - 1, 1)))
        lp = core.apply_transform(placed, core.local_xy_raw(placed, ppoints[pi]))
        lt = apply_matrix(matrix, core.local_xy_raw(target, tpoints[ti]))
        errors.append(math.hypot(lp[0] - lt[0], lp[1] - lt[1]))
    return max(errors) if errors else None


def fit_neighbor_to_constraints(target, constraints):
    """Place a face by minimizing error against every already positioned seam."""
    core = _core()
    if not constraints:
        return None
    if len(constraints) == 1:
        placed, placed_edge, target_edge = constraints[0]
        candidates = neighbor_transform_candidates(placed, target, placed_edge, target_edge)
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        target["transform"] = candidates[0][1]
        curved_seam = (not isinstance(placed["face"].Surface, core.Part.Plane) or
                       not isinstance(target["face"].Surface, core.Part.Plane))
        if curved_seam:
            return 0.0 if candidates[0][0] < 1000.0 else candidates[0][0]
        return seam_matrix_error(placed, target, placed_edge, target_edge,
                                 candidates[0][1])
    candidates = []
    seen = set()
    for placed, placed_edge, target_edge in constraints:
        for side_penalty, matrix in neighbor_transform_candidates(
                placed, target, placed_edge, target_edge):
            key = tuple(round(value, 8) for value in matrix)
            if key in seen:
                continue
            seen.add(key)
            max_error = 0.0
            total_error = side_penalty
            valid = True
            for other, other_edge, this_edge in constraints:
                error = seam_matrix_error(other, target, other_edge,
                                          this_edge, matrix)
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


__all__ = [
    "aligned_edge_samples", "apply_matrix", "edge_samples",
    "fit_neighbor", "fit_neighbor_to_constraints", "neighbor_transform_candidates",
    "seam_limit", "seam_matrix_error",
]
