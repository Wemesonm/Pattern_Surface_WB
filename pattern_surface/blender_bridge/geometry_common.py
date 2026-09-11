"""Pattern-neutral geometry primitives for Blender relief generators."""

import math


EPS = 1.0e-9


def _cross(a, b, c):
    return ((b[0] - a[0]) * (c[1] - a[1]) -
            (b[1] - a[1]) * (c[0] - a[0]))


def _cross3(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _unit(value):
    length = math.sqrt(max(0.0, _dot(value, value)))
    return None if length <= EPS else tuple(x / length for x in value)


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _scale(a, value):
    return tuple(x * value for x in a)


def _barycentric(point, triangle):
    denominator = _cross(triangle[0], triangle[1], triangle[2])
    if abs(denominator) <= EPS:
        return None
    return (_cross(triangle[1], triangle[2], point) / denominator,
            _cross(triangle[2], triangle[0], point) / denominator,
            _cross(triangle[0], triangle[1], point) / denominator)


def _interpolate(point, carrier):
    weights = _barycentric(point, [item["q"] for item in carrier["v"]])
    if weights is None:
        return None
    physical = tuple(sum(item["p"][axis] * weight
                         for item, weight in zip(carrier["v"], weights))
                     for axis in range(3))
    normal = _unit(tuple(sum(item["n"][axis] * weight
                              for item, weight in zip(carrier["v"], weights))
                         for axis in range(3)))
    return (physical, normal) if normal is not None else None


def _clip(polygon, triangle):
    sign = 1.0 if _cross(*triangle[:3]) >= 0.0 else -1.0
    result = list(polygon)
    for start, end in zip(triangle, triangle[1:] + triangle[:1]):
        if not result:
            break
        source, result = result, []
        for current, following in zip(source, source[1:] + source[:1]):
            dc, df = sign * _cross(start, end, current), sign * _cross(start, end, following)
            ic, inf = dc >= -EPS, df >= -EPS
            if ic:
                result.append(current)
            if ic != inf:
                ratio = dc / (dc - df)
                result.append(tuple(current[k] + (following[k] - current[k]) * ratio
                                    for k in range(3)))
    return result


def shared_assembly_phase(payload):
    """Read the pattern-neutral logical phase supplied by the Blender job.

    The bridge owns assembly registration and detects a complete physical
    cycle.  Patterns receive only its logical origin and optional perimeter;
    each pattern remains responsible for fitting that perimeter to its own
    repeat geometry.  Invalid or absent transient metadata is treated as an
    ordinary single-map job.
    """
    phase = payload.get("shared_map_phase", {}) or {}
    raw_origin = phase.get("origin")
    origin = None
    if isinstance(raw_origin, (list, tuple)) and len(raw_origin) >= 2:
        try:
            candidate = float(raw_origin[0]), float(raw_origin[1])
            if all(math.isfinite(value) for value in candidate):
                origin = candidate
        except (TypeError, ValueError):
            pass
    period = None
    try:
        candidate = float(phase.get("assembly_period"))
        if math.isfinite(candidate) and candidate > 0.0:
            period = candidate
    except (TypeError, ValueError):
        pass
    return origin, period


class NativeBoundaryDistance:
    """Distance to selected native CAD rims in map-local orientation.

    ``inward_y`` comes from Map Faces' atlas, so lower/upper never means a
    fixed global direction.  This makes the same edge finish usable on any
    mapped surface, including rotated and curved bodies.
    """

    def __init__(self, payload, width, edge_mode="all", include_inner=False):
        data = payload.get("native_boundary_curves")
        if data is None:
            raise ValueError("Native CAD boundaries are missing. Generate a new Blender job from FreeCAD.")
        if isinstance(edge_mode, bool):  # compatibility with the first Ribs dialog
            edge_mode = "all" if edge_mode else "lower"
        if edge_mode not in ("lower", "upper", "both", "all"):
            raise ValueError("Edge transition must be lower, upper, both, or all.")
        self.width = width
        self.buckets = {}
        for curve in data["curves"]:
            # Old Blender jobs did not retain loop topology.  Treat them as
            # external rims so an old job cannot unexpectedly round a hole.
            is_inner = curve.get("loop_role") == "inner"
            if is_inner and edge_mode != "all" and not include_inner:
                continue
            for index, (a, b) in enumerate(zip(curve["points"], curve["points"][1:])):
                inward = curve["inward_y"][index]
                if is_inner and not include_inner:
                    continue
                if not is_inner:
                    if edge_mode == "lower" and inward <= 0.1:
                        continue
                    if edge_mode == "upper" and inward >= -0.1:
                        continue
                    if edge_mode == "both" and -0.1 <= inward <= 0.1:
                        continue
                # An enabled opening is one selectable contour; its full loop
                # is intentionally rounded, including vertical portions.
                component = curve.get("component", 0)
                ranges = [range(math.floor((min(a[i], b[i]) - width) / width),
                                math.floor((max(a[i], b[i]) + width) / width) + 1)
                          for i in range(3)]
                delta = tuple(b[i] - a[i] for i in range(3))
                length2 = sum(value * value for value in delta)
                if length2 <= 1e-16:
                    continue
                segment = (a, delta, length2)
                for x in ranges[0]:
                    for y in ranges[1]:
                        for z in ranges[2]:
                            self.buckets.setdefault((component, x, y, z), []).append(segment)

    def distance(self, point, component=0):
        key = (component,) + tuple(math.floor(value / self.width) for value in point)
        best = self.width * self.width
        for a, delta, length2 in self.buckets.get(key, ()):
            ratio = max(0.0, min(1.0, sum((point[i] - a[i]) * delta[i]
                                          for i in range(3)) / length2))
            best = min(best, sum((point[i] - a[i] - ratio * delta[i]) ** 2
                                 for i in range(3)))
        return math.sqrt(best)


def concave_relief(wave, distance, width, height):
    """Return a wall-tangent, concave attenuation of a positive relief wave."""
    if wave <= 0.0:
        return 0.0
    if distance >= width:
        return wave
    t = max(0.0, distance / width)
    sag = t * t / (1.0 + math.sqrt(max(0.0, 1.0 - t * t)))
    envelope = height * sag / ((1.0 - t) * (1.0 - t))
    if envelope <= 0.0:
        return 0.0
    return wave / math.hypot(1.0, wave / envelope)
