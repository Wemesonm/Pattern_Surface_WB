"""Map Faces face-orientation helpers."""


def _core():
    from .. import core_engine
    return core_engine


def tangent(face, bounds, axis):
    u0, u1, v0, v1 = bounds
    u = (u0 + u1) * 0.5
    v = (v0 + v1) * 0.5
    du = max(abs(u1 - u0) * 1.0e-4, 1.0e-8)
    dv = max(abs(v1 - v0) * 1.0e-4, 1.0e-8)
    if axis == "u":
        delta = face.valueAt(min(u1, u + du), v) - face.valueAt(max(u0, u - du), v)
    else:
        delta = face.valueAt(u, min(v1, v + dv)) - face.valueAt(u, max(v0, v - dv))
    return _core().norm(delta)


def outward(entry):
    core = _core()
    face = entry["face"]
    solid = core.source_solid(entry)
    samples = []
    if entry.get("picked") is not None:
        samples.append(entry["picked"])
    samples.append(core.face_center(face))
    votes = []
    for point in samples:
        try:
            u, v = face.Surface.parameter(point)
            base = face.valueAt(u, v)
            normal = core.norm(face.normalAt(u, v))
        except Exception:
            continue
        if normal is None:
            continue
        for distance in (0.02, 0.08, 0.25):
            plus = bool(solid.isInside(base + normal * distance, 1.0e-6, False))
            minus = bool(solid.isInside(base - normal * distance, 1.0e-6, False))
            if plus != minus:
                votes.append(-1.0 if plus else 1.0)
    if votes:
        positive = sum(1 for value in votes if value > 0.0)
        negative = sum(1 for value in votes if value < 0.0)
        if positive != negative:
            if positive and negative:
                core.warn("Direcao externa ambigua em {}; usando maioria dos testes.".format(entry["sub"]))
            return 1.0 if positive > negative else -1.0
    core.warn("Direcao externa ambigua em {}; usando normal nativa e alinhamento por vizinhos.".format(entry["sub"]))
    return 1.0


def orient_entry(entry):
    return _core().orient_entry(entry)


def signed_normal_at(entry, point):
    core = _core()
    try:
        u, v = entry["face"].Surface.parameter(point)
        normal = core.norm(entry["face"].normalAt(u, v))
        return normal * entry["normal_sign"] if normal is not None else None
    except Exception:
        return None


def edge_midpoint(edge):
    points = edge.discretize(Number=3)
    return points[len(points) // 2]


def align_connected_normals(entries, graph):
    core = _core()
    by_index = {entry["index"]: entry for entry in entries}
    pending = set(by_index)
    flips = 0
    while pending:
        root_index = min(pending, key=lambda index: (
            0 if isinstance(by_index[index]["face"].Surface, core.Part.Plane) else 1,
            -float(by_index[index]["face"].Area),
            by_index[index]["sub"]))
        pending.remove(root_index)
        queue = [root_index]
        while queue:
            current_index = queue.pop(0)
            current = by_index[current_index]
            for neighbor_index, current_edge, neighbor_edge in graph[current_index]:
                if neighbor_index not in pending:
                    continue
                neighbor = by_index[neighbor_index]
                normal_a = signed_normal_at(current, edge_midpoint(current_edge))
                normal_b = signed_normal_at(neighbor, edge_midpoint(neighbor_edge))
                if normal_a is not None and normal_b is not None and normal_a.dot(normal_b) < -0.05:
                    neighbor["normal_sign"] *= -1.0
                    flips += 1
                pending.remove(neighbor_index)
                queue.append(neighbor_index)
    if flips:
        core.console("wrap_v4: normais_conectadas_invertidas={}".format(flips))

__all__ = [name for name in globals() if not name.startswith("_")]
