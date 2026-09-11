"""DATA-REQ-055: physical boundary curves from selected BRep topology."""

import math


def _same_point(a, b, tolerance=1.0e-10):
    return sum((x-y)**2 for x, y in zip(a, b)) < tolerance


def _classify_boundary_loops(curves):
    """Mark native boundary fragments as outer rims or inner opening rims.

    Edge orientation supplied by OCC is not stable.  We first orient every
    fragment so the selected surface is on its local-left side, then connect
    the fragments through their native endpoints.  The largest enclosed atlas
    area is the exterior loop; every smaller closed loop is an opening.  This
    uses Map Faces coordinates only; it does not depend on a FreeCAD/Blender
    world direction or a face number.
    """
    fragments = []
    for index, curve in enumerate(curves):
        q = curve["logical_points"]
        inward = curve["inward_q"]
        tangent = (q[-1][0]-q[0][0], q[-1][1]-q[0][1])
        reverse = tangent[0]*inward[0][1] - tangent[1]*inward[0][0] < 0.0
        fragments.append({"index": index, "component": curve["component"],
                          "points": list(reversed(curve["points"])) if reverse else curve["points"],
                          "logical_points": (list(reversed(curve["logical_points"]))
                                             if reverse else curve["logical_points"])})
        curve["loop_role"] = "outer"  # Safe fallback for an incomplete loop.

    unused = set(range(len(fragments)))

    completed = []

    def record_loop(loop):
        points = []
        for position, index in enumerate(loop):
            fragment = fragments[index]["logical_points"]
            points.extend(fragment if position == 0 else fragment[1:])
        area = sum(a[0]*b[1] - a[1]*b[0]
                   for a, b in zip(points, points[1:] + points[:1]))
        completed.append((fragments[loop[0]]["component"], loop, abs(area)))

    while unused:
        first = unused.pop()
        loop = [first]
        end = fragments[first]["points"][-1]
        if _same_point(end, fragments[first]["points"][0]):
            record_loop(loop)
            continue
        while True:
            match = None
            for index in unused:
                candidate = fragments[index]
                if candidate["component"] != fragments[first]["component"]:
                    continue
                if _same_point(candidate["points"][0], end):
                    match = index
                    break
                if _same_point(candidate["points"][-1], end):
                    candidate["points"] = list(reversed(candidate["points"]))
                    candidate["logical_points"] = list(reversed(candidate["logical_points"]))
                    match = index
                    break
            if match is None:
                break
            unused.remove(match)
            loop.append(match)
            end = fragments[match]["points"][-1]
            if _same_point(end, fragments[first]["points"][0]):
                record_loop(loop)
                break

    # A connected selected atlas has one exterior cycle.  Its logical area
    # encloses every opening, so it is the largest cycle for that component.
    # This remains stable even when the source surface or its UV direction is
    # mirrored, where a signed-area-only classification would be reversed.
    by_component = {}
    for component, loop, area in completed:
        by_component.setdefault(component, []).append((loop, area))
    for loops in by_component.values():
        outer = max(loops, key=lambda item: item[1])[0]
        for loop, _ in loops:
            role = "outer" if loop == outer else "inner"
            for index in loop:
                curves[fragments[index]["index"]]["loop_role"] = role


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
        inward_q = []
        logical_points = []
        for point in points:
            logical_points.append(list(apply_transform(
                entry, local_xy_raw(entry, point))))
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
            length = max(math.hypot(dx, dy), 1e-12)
            inward.append(dy/length)
            inward_q.append([dx/length, dy/length])
        curves.append({"component": entry.get("component", 0),
                       "face": entry["index"], "points": [list(p) for p in points],
                       "logical_points": logical_points, "inward_q": inward_q,
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
    _classify_boundary_loops(curves)
    return {"deflection_mm": deflection, "curves": curves}
