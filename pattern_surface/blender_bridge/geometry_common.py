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
