"""DATA-REQ-055: physical boundary curves from selected BRep topology."""

import math


def boundary_curves(entries, deflection=0.005):
    from ..mapping.parameterization import local_xy_raw, apply_transform

    occurrences = []
    unique_faces = []
    for entry in entries:
        if any(entry["face"].isSame(old["face"]) for old in unique_faces):
            continue
        unique_faces.append(entry)
        # Wire occurrences preserve both uses of a periodic surface seam.
        for wire in entry["face"].Wires:
            for edge in wire.OrderedEdges:
                if edge.Length <= 1e-8:
                    continue
                match = next((item for item in occurrences
                              if item["edge"].isSame(edge)), None)
                if match is None:
                    occurrences.append({"edge": edge, "entry": entry, "uses": 1})
                else:
                    match["uses"] += 1
    if any(item["uses"] > 2 for item in occurrences):
        raise ValueError("Selected CAD faces have a nonmanifold boundary.")
    curves = []
    for item in occurrences:
        if item["uses"] != 1:
            continue
        edge, entry = item["edge"], item["entry"]
        face = entry["face"]
        points = edge.discretize(Deflection=deflection)
        if len(points) < 2:
            raise ValueError("Cannot sample a native CAD boundary edge.")
        inward = []
        for a, b in zip(points, points[1:]):
            middle = (a+b)*0.5
            u, v = face.Surface.parameter(middle)
            middle = face.valueAt(u, v)
            tangent = b-a
            transverse = face.normalAt(u, v).cross(tangent)
            if transverse.Length < 1e-10:
                raise ValueError("Native boundary has an undefined tangent.")
            transverse.normalize()
            step = min(0.01, edge.Length*0.001)
            interior = None
            for sign in (1, -1):
                pu, pv = face.Surface.parameter(middle + transverse*(step*sign))
                candidate = face.valueAt(pu, pv)
                if face.isInside(candidate, 1e-7, False):
                    interior = candidate
                    break
            if interior is None:
                raise ValueError("Cannot determine the inside of a native boundary.")
            q = apply_transform(entry, local_xy_raw(entry, middle))
            qi = apply_transform(entry, local_xy_raw(entry, interior))
            dx, dy = qi[0]-q[0], qi[1]-q[1]
            inward.append(dy/max(math.hypot(dx, dy), 1e-12))
        curves.append({"component": entry.get("component", 0),
                       "face": entry["index"], "points": [list(p) for p in points],
                       "inward_y": inward})
    # Every boundary endpoint must meet exactly one other curve endpoint.
    # Closed edges contribute twice at their common start/end point.
    endpoints = []
    for curve in curves:
        for p in (curve["points"][0], curve["points"][-1]):
            match = next((item for item in endpoints
                          if item[0] == curve["component"] and
                          sum((a-b)**2 for a, b in zip(item[1], p)) < 1e-10), None)
            if match is None:
                endpoints.append([curve["component"], p, 1])
            else:
                match[2] += 1
    if any(item[2] != 2 for item in endpoints):
        raise ValueError("Native selected-face boundary does not form closed cycles.")
    return {"deflection_mm": deflection, "curves": curves}
