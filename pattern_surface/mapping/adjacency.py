"""Generic adjacency and connected-component operations for Map Faces."""

from ..common.selection_core import selected_faces as collect_selected_faces


def _core():
    from ..compatibility import v4_pipeline
    return v4_pipeline


def selected_faces():
    return collect_selected_faces()


def outer_edges(face):
    try:
        return list(face.OuterWire.OrderedEdges)
    except Exception:
        return list(face.OuterWire.Edges)


def endpoints(edge):
    vertices = list(edge.Vertexes)
    if len(vertices) >= 2:
        return vertices[0].Point, vertices[-1].Point
    points = edge.discretize(Number=2)
    return points[0], points[-1]


def same_edge(left, right):
    tolerance = _core().EDGE_TOL
    a0, a1 = endpoints(left)
    b0, b1 = endpoints(right)
    return ((a0.distanceToPoint(b0) <= tolerance and a1.distanceToPoint(b1) <= tolerance) or
            (a0.distanceToPoint(b1) <= tolerance and a1.distanceToPoint(b0) <= tolerance))


def shared_edge(left, right):
    for edge_left in outer_edges(left):
        for edge_right in outer_edges(right):
            if same_edge(edge_left, edge_right):
                return edge_left, edge_right
    return None, None


def source_solid(entry):
    shape = getattr(entry["object"], "Shape", None)
    if shape is None or shape.isNull() or not list(shape.Solids):
        _core().fail("{} precisa pertencer a um solido fechado valido.".format(entry["sub"]))
    return shape


def build_graph(entries):
    graph = {entry["index"]: [] for entry in entries}
    shared = []
    for pos, left in enumerate(entries):
        for right in entries[pos + 1:]:
            edge_left, edge_right = shared_edge(left["face"], right["face"])
            if edge_left is None:
                continue
            graph[left["index"]].append((right["index"], edge_left, edge_right))
            graph[right["index"]].append((left["index"], edge_right, edge_left))
            shared.append((left["index"], right["index"]))
    return graph, shared


def components(entries, graph):
    by_index = {entry["index"]: entry for entry in entries}
    pending = set(by_index)
    result = []
    while pending:
        root = min(pending)
        pending.remove(root)
        queue, group = [root], []
        while queue:
            current = queue.pop(0)
            group.append(by_index[current])
            for neighbor, _a, _b in graph[current]:
                if neighbor in pending:
                    pending.remove(neighbor)
                    queue.append(neighbor)
        result.append(group)
    return result


__all__ = [
    "build_graph",
    "components",
    "endpoints",
    "outer_edges",
    "same_edge",
    "selected_faces",
    "shared_edge",
    "source_solid",
]
