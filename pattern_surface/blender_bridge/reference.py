"""Native CAD boundary references for transient Blender packages."""


def prepare_reference(document, payload, include_boundary_curves=False, rebuild_boundary=False):
    """Refresh trimmed curved domains without rewriting the saved map."""
    import Part
    from .. import core_engine as core
    from ..mapping.trimmed_carrier import trimmed_curved_carrier

    entries = core.hydrate_entries(document, payload)
    original = payload.get("carrier_triangles", payload.get("triangles", []))
    triangles = []
    for entry in entries:
        replacement = (None if isinstance(entry["face"].Surface, Part.Plane)
                       else trimmed_curved_carrier(entry))
        triangles.extend([t for t in original if t["face"] == entry["index"]]
                         if replacement is None else replacement)
    result = dict(payload)
    result["carrier_triangles"] = triangles
    result["triangles"] = triangles
    result["boundary_support_planes"] = support_planes(entries)
    if include_boundary_curves or rebuild_boundary:
        from .native_boundary import boundary_curves
        native = boundary_curves(entries)
        if include_boundary_curves:
            result["native_boundary_curves"] = native
        if rebuild_boundary:
            # DATA-REQ-058: a cut between Bodies becomes an exterior rim.
            result["external_segments"] = []
            for curve in native["curves"]:
                vertices = [dict(p=p, q=q) for p, q in
                            zip(curve["points"], curve["logical_points"])]
                result["external_segments"].extend(
                    dict(face=curve["face"], component=curve["component"], a=a, b=b)
                    for a, b in zip(vertices, vertices[1:]))
    return result


def support_planes(entries):
    """Only native adjacent planar faces supporting the entire selected domain.

    A plane cutting through the selection is deliberately not a global cutter.
    Internal selected-face seams are never boundaries. No screen/world axis is
    used to choose either the plane or its retained side.
    """
    import Part
    selected = [entry["face"] for entry in entries]
    samples = [point for face in selected for point in face.tessellate(0.01)[0]]
    objects = {entry["object_ref"].Name: entry["object_ref"] for entry in entries}
    planes = []
    for obj in objects.values():
        for index in range(len(obj.Shape.Faces)):
            face = obj.getSubObject("Face{}".format(index + 1))
            if not isinstance(face.Surface, Part.Plane):
                continue
            if any(face.isSame(other) for other in selected):
                continue
            if not any(a.isSame(b) for a in face.Edges
                       for other in selected for b in other.Edges):
                continue
            origin = face.CenterOfMass
            normal = face.normalAt(0, 0)
            normal.normalize()
            values = [(p-origin).dot(normal) for p in samples]
            if min(values) >= -1e-6:
                normal = -normal
            elif max(values) > 1e-6:
                continue
            if max(abs(v) for v in values) < 1e-6:
                continue
            offset = origin.dot(normal)
            if any(sum((plane["normal"][i]-normal[i])**2 for i in range(3)) < 1e-12
                   and abs(plane["offset"]-offset) < 1e-6 for plane in planes):
                continue
            planes.append({"origin": list(origin), "normal": list(normal), "offset": offset})
    return planes
