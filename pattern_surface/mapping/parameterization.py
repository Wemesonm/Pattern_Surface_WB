"""Face parameter and logical-coordinate conversions owned by Map Faces."""

import math


def _core():
    # Kept lazy while V4 compatibility remains the temporary geometry source.
    from ..compatibility import v4_pipeline
    return v4_pipeline


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
    core = _core()
    native = list(face.ParameterRange)
    values = []
    for edge in core.outer_edges(face):
        length = max(float(getattr(edge, "Length", 0.0)), 0.01)
        for point in edge.discretize(Number=max(3, int(math.ceil(length / core.MAX_EDGE)) + 1)):
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


def axis_length_table(face, bounds, axis, samples=64):
    u0, u1, v0, v1 = bounds
    fixed = (v0 + v1) * 0.5 if axis == "u" else (u0 + u1) * 0.5
    table = [(0.0, 0.0)]
    total = 0.0
    previous = None
    for index in range(samples + 1):
        ratio = float(index) / samples
        point = (face.valueAt(u0 + (u1 - u0) * ratio, fixed)
                 if axis == "u" else
                 face.valueAt(fixed, v0 + (v1 - v0) * ratio))
        if previous is not None:
            total += point.distanceToPoint(previous)
        table.append((ratio, total))
        previous = point
    if total <= 1.0e-9:
        _core().fail("Metrica degenerada na face.")
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


def edge_fraction(edge, point):
    core = _core()
    samples = core.edge_samples(edge, max(core.MAX_EDGE, edge.Length / 48.0))
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


def local_xy(entry, point):
    core = _core()
    for seam in entry.get("seam_overrides", []):
        if core.point_on_edge(point, seam["edge"], 5.0e-4):
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
    core = _core()
    local = invert_transform(entry, logical)
    if local is None:
        return None
    u, v = local_uv(entry, local)
    try:
        point = entry["face"].valueAt(u, v)
        normal = core.norm(entry["face"].normalAt(u, v)) * entry["normal_sign"]
        return point, normal
    except Exception:
        return None


__all__ = [name for name in globals() if not name.startswith("_")]
