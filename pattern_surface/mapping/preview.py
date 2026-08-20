"""Map Faces carrier-grid preview generation."""

import math

import Part

from ..compatibility.v4_pipeline import interpolate_vertex
from .parameters import DEFAULT_COLUMN_WIDTH, DEFAULT_ROW_HEIGHT


def line_triangle_points(triangle, value, vertical):
    result = []
    vertices = triangle["v"]
    axis = 0 if vertical else 1
    for index in range(3):
        left, right = vertices[index], vertices[(index + 1) % 3]
        a, b = left["q"][axis] - value, right["q"][axis] - value
        if abs(a) <= 1.0e-8:
            result.append(list(left["q"]))
        if a * b < -1.0e-14:
            ratio = a / (a - b)
            result.append([left["q"][0] + (right["q"][0] - left["q"][0]) * ratio,
                           left["q"][1] + (right["q"][1] - left["q"][1]) * ratio])
    unique = []
    for point in result:
        if not any(math.hypot(point[0] - other[0], point[1] - other[1]) <= 1.0e-7
                   for other in unique):
            unique.append(point)
    if len(unique) < 2:
        return None
    other_axis = 1 - axis
    unique.sort(key=lambda point: point[other_axis])
    return unique[0], unique[-1]


def grid_line_values(lower, upper, origin, step):
    first = origin + math.ceil((lower - origin) / step - 1.0e-9) * step
    values = []
    current = first
    while current <= upper + 1.0e-8:
        values.append(current)
        current += step
    return values


def preview_point_key(point, tolerance=1.0e-4):
    return tuple(int(round(value / tolerance))
                 for value in (point.x, point.y, point.z))


def preview_line_edges(samples):
    """Collapse triangle-sized preview segments into connected spline edges."""
    graph = {}
    points = {}
    parameters = {}
    for ta, pa, tb, pb in samples:
        left, right = preview_point_key(pa), preview_point_key(pb)
        if left == right:
            continue
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set()).add(left)
        points.setdefault(left, pa)
        points.setdefault(right, pb)
        parameters[left] = min(parameters.get(left, ta), ta)
        parameters[right] = min(parameters.get(right, tb), tb)
    result = []
    remaining = set(graph)
    while remaining:
        seed = remaining.pop()
        component = {seed}
        queue = [seed]
        while queue:
            current = queue.pop()
            for neighbor in graph[current]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        ordered = sorted(component, key=lambda item: parameters[item])
        vectors = [points[item] for item in ordered]
        if len(vectors) < 2:
            continue
        if len(vectors) == 2:
            result.append(Part.makeLine(vectors[0], vectors[1]))
            continue
        periodic = all(len(graph[item] & component) == 2 for item in component)
        try:
            curve = Part.BSplineCurve()
            # Degree one preserves every mapped sample exactly. Cubic
            # interpolation can overshoot at face seams.
            curve.buildFromPoles(vectors, periodic, 1)
            result.append(curve.toShape())
        except Exception:
            fallback = vectors + [vectors[0]] if periodic else vectors
            result.append(Part.makePolygon(fallback))
    return result


def carrier_preview(triangles, bounds, column_width=DEFAULT_COLUMN_WIDTH,
                    row_height=DEFAULT_ROW_HEIGHT, origin=None):
    """Build the connected logical grid preview on the mapped carrier."""
    edges = []
    x0, x1, y0, y1 = bounds
    origin = list(origin or [(x0 + x1) * 0.5, (y0 + y1) * 0.5])
    for vertical, lower, upper, phase, step in (
            (True, x0, x1, origin[0], float(column_width)),
            (False, y0, y1, origin[1], float(row_height))):
        for value in grid_line_values(lower, upper, phase, step):
            samples = []
            for triangle in triangles:
                segment = line_triangle_points(triangle, value, vertical)
                if segment is None:
                    continue
                mapped = [interpolate_vertex(point, triangle) for point in segment]
                if all(item is not None for item in mapped):
                    points = [item[0] + item[1] * 0.01 for item in mapped]
                    length = points[0].distanceToPoint(points[1])
                    if length > 1.0e-7:
                        axis = 1 if vertical else 0
                        samples.append((segment[0][axis], points[0],
                                        segment[1][axis], points[1]))
            edges.extend(preview_line_edges(samples))
    return Part.makeCompound(edges) if edges else Part.Shape()


__all__ = [
    "carrier_preview",
    "grid_line_values",
    "line_triangle_points",
    "preview_line_edges",
    "preview_point_key",
]
