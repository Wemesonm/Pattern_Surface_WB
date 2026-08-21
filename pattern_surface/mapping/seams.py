"""Shared-edge sampling primitives for Map Faces seam fitting."""

import math


def _core():
    from ..compatibility import v4_pipeline
    return v4_pipeline


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
        core.console("wrap_v4: emenda_curva_escala_tangencial {} <-> {} sl={:.4f} dl={:.4f} escala={:.6f}".format(
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


__all__ = [
    "aligned_edge_samples", "apply_matrix", "edge_samples",
    "neighbor_transform_candidates", "seam_limit",
]
