"""Intersect regular curved sampling with the native trimmed parameter domain."""

import math


def trimmed_curved_carrier(entry):
    """Return None for a complete rectangular domain, otherwise clipped cells.

    Native face tessellation supplies trim topology (including holes); regular
    cells supply sampling density. The centroid is never a boundary classifier.
    """
    from .. import core_engine as core

    points, facets = entry["face"].tessellate(min(core.SAG, 0.01))
    local = [core.local_xy_raw(entry, point) for point in points]
    domains = [[local[i] for i in facet] for facet in facets]
    domains = [p for p in domains if core.area2(p) > 1e-10]
    area = sum(core.area2(p) for p in domains)
    rectangle = entry["width"] * entry["height"]
    if abs(area - rectangle) <= max(1e-7, rectangle * 1e-8):
        return None
    if not domains:
        raise ValueError("Native trimmed face has no usable parameter domain.")

    nx = max(1, int(math.ceil(entry["width"] / core.MAX_EDGE)))
    ny = max(1, int(math.ceil(entry["height"] / core.MAX_EDGE)))
    sx, sy = entry["width"] / nx, entry["height"] / ny
    buckets = {}
    for poly in domains:
        for ix in range(max(0, int(math.floor(min(p[0] for p in poly)/sx))),
                        min(nx-1, int(math.floor(max(p[0] for p in poly)/sx)))+1):
            for iy in range(max(0, int(math.floor(min(p[1] for p in poly)/sy))),
                            min(ny-1, int(math.floor(max(p[1] for p in poly)/sy)))+1):
                buckets.setdefault((ix, iy), []).append(poly)
    result, cache = [], {}
    def vertex(p):
        key = tuple(round(x, 9) for x in p)
        if key not in cache:
            cache[key] = core.mapped_vertex(entry, core.apply_transform(entry, p))
        return cache[key]
    for (ix, iy), clips in sorted(buckets.items()):
        a, b = [ix*sx, iy*sy], [(ix+1)*sx, iy*sy]
        c, d = [ix*sx, (iy+1)*sy], [(ix+1)*sx, (iy+1)*sy]
        for cell in ([a,b,c], [b,d,c]):
            polygons = [core.clip_polygon(cell, clip) for clip in clips]
            polygons = [poly for poly in polygons if len(poly) >= 3]
            # Native triangulation partitions the domain. Keep the original
            # regular interior instead of copying every tessellation seam.
            covered = sum(core.area2(poly) for poly in polygons)
            if abs(covered - core.area2(cell)) <= 1e-8:
                polygons = [cell]
            for poly in polygons:
                for i in range(1, len(poly)-1):
                    part = [poly[0], poly[i], poly[i+1]]
                    if core.area2(part) <= 1e-9:
                        continue
                    vertices = [vertex(p) for p in part]
                    if any(v is None for v in vertices):
                        raise ValueError("Cannot evaluate native trimmed carrier point.")
                    result.append({"face": entry["index"], "component": entry["component"],
                                   "curved": True, "v": vertices})
    return result
