"""Map Faces face-orientation helpers."""


def _core():
    from ..compatibility import v4_pipeline
    return v4_pipeline


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
    return _core().outward(entry)


def orient_entry(entry):
    return _core().orient_entry(entry)


def signed_normal_at(entry, point):
    return _core().signed_normal_at(entry, point)


def align_connected_normals(entries, graph):
    return _core().align_connected_normals(entries, graph)

__all__ = [name for name in globals() if not name.startswith("_")]
