"""Stable logical grid phase for Map Faces.

The carrier atlas remains local to one Map Faces run.  The grid is separate
metadata, so it can be anchored to the owning body's geometry without moving a
single carrier vertex.  Separate maps of the same body therefore show the same
phase when their local charts describe a common physical wall.
"""

from __future__ import division

import math

from ..common.ownership import source_body


EPS = 1.0e-10


def _core():
    from .. import core_engine
    return core_engine


PHASE_ALIGNMENTS = ("global", "left", "center", "right")
ROW_ALIGNMENTS = ("global", "bottom", "center", "top")


def _sub(a, b):
    return [float(left) - float(right) for left, right in zip(a, b)]


def _dot(a, b):
    return sum(left * right for left, right in zip(a, b))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _length_squared(a):
    return _dot(a, a)


def _point(value):
    return [float(value.x), float(value.y), float(value.z)]


def _single_source_body(entries):
    bodies = []
    for entry in entries:
        body = source_body(entry.get("object"))
        if body is not None and body not in bodies:
            bodies.append(body)
    return bodies[0] if len(bodies) == 1 else None


def _single_phase_owner(entries):
    """Return the rigid CAD owner that supplies a map's native up direction.

    A Boolean split can produce standalone solids that are deliberately not in
    a PartDesign Body. They still have a Shape and Placement and must not fall
    back to a chart-centred row phase merely because they lack a Body.
    """
    owners = []
    for entry in entries:
        source = entry.get("object")
        owner = source_body(source) or source
        if owner is not None and owner not in owners:
            owners.append(owner)
    return owners[0] if len(owners) == 1 else None


def _single_phase_owner(entries):
    """Return the rigid CAD owner that supplies a map's native up direction.

    A Boolean split can produce standalone solids that are deliberately not in
    a PartDesign Body.  They still have a Shape and Placement and must not
    fall back to a chart-centred row phase merely because they lack a Body.
    """
    owners = []
    for entry in entries:
        source = entry.get("object")
        owner = source_body(source) or source
        if owner is not None and owner not in owners:
            owners.append(owner)
    return owners[0] if len(owners) == 1 else None


def normalize_phase_alignment(value):
    value = str(value or "global").strip().lower()
    if value not in PHASE_ALIGNMENTS:
        raise ValueError("Unknown Map Faces phase alignment: {}".format(value))
    return value


def normalize_row_alignment(value):
    value = str(value or "global").strip().lower()
    if value not in ROW_ALIGNMENTS:
        raise ValueError("Unknown Map Faces row alignment: {}".format(value))
    return value


def _body_local_height(body, point):
    """Measure a carrier point along the owning Body's native vertical axis."""
    placement = getattr(body, "Placement", None)
    if placement is not None:
        try:
            import FreeCAD as App
            return float(placement.inverse().multVec(
                App.Vector(float(point[0]), float(point[1]), float(point[2]))).z)
        except Exception:
            pass
    return float(point[2])


def mapped_edge_row(entries, triangles, fallback, upper=False):
    """Return the q row at the selected carrier's physical lower/upper edge.

    A horizontal face has no vertical range in its own chart; retaining the
    centred fallback in that case avoids inventing a direction within the
    face.  Vertical and sloped maps use their actual native lower boundary.
    """
    body = _single_phase_owner(entries)
    vertices = [vertex for triangle in triangles for vertex in triangle.get("v", [])
                if vertex.get("p") and vertex.get("q")]
    if body is None or not vertices:
        return float(fallback[1])
    measured = [(_body_local_height(body, vertex["p"]), float(vertex["q"][1]))
                for vertex in vertices]
    lower, highest = min(item[0] for item in measured), max(item[0] for item in measured)
    if highest - lower <= EPS:
        return float(fallback[1])
    target = highest if upper else lower
    candidates = [item[1] for item in measured
                  if abs(item[0] - target) <= EPS * 100.0]
    return (max(candidates) if upper else min(candidates))


def mapped_lower_row(entries, triangles, fallback):
    return mapped_edge_row(entries, triangles, fallback, upper=False)


def _shape_anchor(body, carrier_points):
    """Find a body-local bottom reference in the coordinate frame of ``p``.

    FreeCAD shapes can expose points either with their Placement applied or in
    their object's local coordinates.  Choose the representation nearest the
    carrier points, so the calculation remains correct for either form.
    """
    shape = getattr(body, "Shape", None)
    vertices = list(getattr(shape, "Vertexes", []) or [])
    if not vertices:
        return None
    direct = [_point(vertex.Point) for vertex in vertices]
    placement = getattr(body, "Placement", None)
    transformed = []
    if placement is not None:
        try:
            transformed = [_point(placement.multVec(vertex.Point)) for vertex in vertices]
        except Exception:
            transformed = []
    target = carrier_points[0]

    def nearest_distance(points):
        return min(_length_squared(_sub(point, target)) for point in points)

    points = direct
    if transformed and nearest_distance(transformed) + EPS < nearest_distance(direct):
        points = transformed

    # The body placement, rather than a screen or world axis, supplies the
    # stable CAD up direction.  In the already-applied form this is the
    # placement's Z axis; in local coordinates it is simply the body Z axis.
    if transformed and points is transformed and placement is not None:
        try:
            inverse = placement.inverse()
            local = [_point(inverse.multVec(type(vertices[0].Point)(*point))) for point in points]
            minimum = min(point[2] for point in local)
            reference = [sum(point[0] for point in local) / len(local),
                         sum(point[1] for point in local) / len(local), minimum]
            return _point(placement.multVec(type(vertices[0].Point)(*reference)))
        except Exception:
            pass
    minimum = min(point[2] for point in points)
    return [sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points), minimum]


def _logical_projection(anchor, triangles):
    """Extrapolate a physical anchor through the nearest carrier triangle."""
    best = None
    for triangle in triangles:
        vertices = triangle.get("v", [])
        if len(vertices) != 3:
            continue
        a, b, c = [vertex.get("p") for vertex in vertices]
        if not a or not b or not c:
            continue
        ab, ac = _sub(b, a), _sub(c, a)
        normal = _cross(ab, ac)
        normal_length = _length_squared(normal)
        if normal_length <= EPS:
            continue
        offset = _sub(anchor, a)
        projected = [anchor[index] - normal[index] * _dot(offset, normal) / normal_length
                     for index in range(3)]
        score = _length_squared(_sub(anchor, projected))
        # Stable tie-breaker: prefer the carrier point nearest the anchor.
        score += min(_length_squared(_sub(anchor, point)) for point in (a, b, c)) * 1.0e-9
        if best is None or score < best[0]:
            best = (score, projected, vertices)
    if best is None:
        return None
    _score, point, vertices = best
    a, b, c = [vertex["p"] for vertex in vertices]
    v0, v1, v2 = _sub(b, a), _sub(c, a), _sub(point, a)
    d00, d01, d11 = _dot(v0, v0), _dot(v0, v1), _dot(v1, v1)
    denominator = d00 * d11 - d01 * d01
    if abs(denominator) <= EPS:
        return None
    v = (_dot(v2, v0) * d11 - _dot(v2, v1) * d01) / denominator
    w = (_dot(v2, v1) * d00 - _dot(v2, v0) * d01) / denominator
    u = 1.0 - v - w
    qs = [vertex.get("q") for vertex in vertices]
    if any(q is None for q in qs):
        return None
    return [u * float(qs[0][0]) + v * float(qs[1][0]) + w * float(qs[2][0]),
            u * float(qs[0][1]) + v * float(qs[1][1]) + w * float(qs[2][1])]


def body_anchored_grid_origin(entries, triangles, fallback):
    """Return a grid origin without changing the local carrier atlas.

    Multiple source bodies deliberately retain the historical centered origin:
    no single body placement can be a neutral reference for that map.
    """
    body = _single_phase_owner(entries)
    points = [vertex.get("p") for triangle in triangles
              for vertex in triangle.get("v", []) if vertex.get("p")]
    if body is None or not points:
        return list(fallback)
    anchor = _shape_anchor(body, points)
    logical = _logical_projection(anchor, triangles) if anchor is not None else None
    return logical if logical is not None and all(math.isfinite(value) for value in logical) else list(fallback)


def _oldest_body_payload(document, body):
    """Return the first persisted map that owns exactly ``body``."""
    for obj in list(getattr(document, "Objects", []) or []):
        payload = _payload_from_object(obj)
        if payload is not None and _same_source_body(document, payload, body):
            return payload
    return None


def _body_root_origin(document, body):
    root = _oldest_body_payload(document, body)
    origin = root.get("grid", {}).get("origin") if root is not None else None
    if isinstance(origin, (tuple, list)) and len(origin) == 2:
        return [float(origin[0]), float(origin[1])]
    return None


def body_phase_grid_origin(document, entries, triangles, fallback):
    """Resolve a stable Body grid phase without altering the carrier atlas.

    The first map is centred laterally so partial columns balance at the two
    selected ends.  Its rows start at the Body's physical lower extent. Later
    maps use that same physical anchor to inherit the phase even without an
    adjacent or coincident map edge.
    """
    body = _single_source_body(entries)
    owner = _single_phase_owner(entries)
    points = [vertex.get("p") for triangle in triangles
              for vertex in triangle.get("v", []) if vertex.get("p")]
    if owner is None or not points:
        return list(fallback)
    # A disconnected wall does not share a carrier plane with the owner anchor.
    # Projecting that remote point into its local chart makes its lower row
    # drift, as happened on the rear wall of the regression container.  The
    # Body placement is still used by ``mapped_lower_row`` to identify the
    # actual physical bottom, but each chart supplies its own logical row.
    lower_row = mapped_lower_row(entries, triangles, fallback)
    anchor = _shape_anchor(owner, points)
    current = _logical_projection(anchor, triangles) if anchor is not None else None
    if current is None or not all(math.isfinite(value) for value in current):
        return [float(fallback[0]), float(lower_row)]
    # A standalone split solid has no Body phase root. It still establishes
    # its first map from its true lower boundary; a compatible neighbouring
    # owner is registered later by the physical-rim routine below.
    if body is None:
        return [float(fallback[0]), float(lower_row)]
    root = _oldest_body_payload(document, body)
    if root is None:
        return [float(fallback[0]), float(lower_row)]
    root_triangles = root.get("carrier_triangles", root.get("triangles", [])) or []
    root_points = [vertex.get("p") for triangle in root_triangles
                   for vertex in triangle.get("v", []) if vertex.get("p")]
    root_anchor = _shape_anchor(owner, root_points) if root_points else None
    reference = (_logical_projection(root_anchor, root_triangles)
                 if root_anchor is not None else None)
    origin = root.get("grid", {}).get("origin")
    if (reference is None or not all(math.isfinite(value) for value in reference) or
            not isinstance(origin, (tuple, list)) or len(origin) != 2):
        return [float(fallback[0]), float(lower_row)]
    # Keep the shared physical Body anchor at the same logical displacement
    # from the grid origin in each independent local atlas.
    return [float(current[0]) - (float(reference[0]) - float(origin[0])),
            float(lower_row)]



def _face_number(sub):
    value = str(sub or "")
    if not value.startswith("Face"):
        return None
    try:
        number = int(value[4:])
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _edge_key(edge, precision=6):
    """Bucket an edge without assuming a particular CAD axis or face number."""
    try:
        vertices = list(edge.Vertexes)
        if len(vertices) >= 2:
            points = [_point(vertices[0].Point), _point(vertices[-1].Point)]
        else:
            points = [_point(point) for point in edge.discretize(Number=2)]
        endpoints = tuple(sorted(tuple(round(value, precision) for value in point)
                                 for point in points[:2]))
        return (endpoints, round(float(edge.Length), precision))
    except Exception:
        return None


def _source_face_graph(source):
    """Return source-face adjacency indexed by the source BRep face number.

    This graph intentionally comes from all faces of the source feature.  It is
    only used to transport a grid phase through a Body; it never becomes a
    carrier or changes the selected Map Faces payload.
    """
    from .adjacency import outer_edges, same_edge
    faces = list(getattr(getattr(source, "Shape", None), "Faces", []) or [])
    buckets, graph = {}, {index + 1: set() for index in range(len(faces))}
    for number, face in enumerate(faces, 1):
        for edge in outer_edges(face):
            key = _edge_key(edge)
            if key is not None:
                buckets.setdefault(key, []).append((number, edge))
    for candidates in buckets.values():
        for position, (left_number, left_edge) in enumerate(candidates):
            for right_number, right_edge in candidates[position + 1:]:
                if left_number != right_number and same_edge(left_edge, right_edge):
                    graph[left_number].add(right_number)
                    graph[right_number].add(left_number)
    return faces, graph


def _body_up(body):
    """Return the Body's placed native Z direction, never a screen direction."""
    placement = getattr(body, "Placement", None)
    rotation = getattr(placement, "Rotation", None)
    if rotation is None:
        return None
    try:
        import FreeCAD as App
        vector = rotation.multVec(App.Vector(0.0, 0.0, 1.0))
        values = [float(vector.x), float(vector.y), float(vector.z)]
        length = math.sqrt(_length_squared(values))
        return None if length <= EPS else [value / length for value in values]
    except Exception:
        return None


def _face_verticality(face, up):
    """Measure how much a face normal follows the Body's native up direction."""
    if up is None:
        return 0.0
    try:
        center = face.CenterOfMass
        u, v = face.Surface.parameter(center)
        normal = face.normalAt(u, v)
        values = [float(normal.x), float(normal.y), float(normal.z)]
        length = math.sqrt(_length_squared(values))
        return 0.0 if length <= EPS else abs(_dot([value / length for value in values], up))
    except Exception:
        return 0.0


def _shortest_route(graph, starts, goals, faces=None, body=None):
    """Find a deterministic route, preserving a lateral wall around its rim.

    A top or bottom face often touches every side wall and is topologically
    short but visually wrong for a wrap.  When both endpoints are side walls,
    a route through a face normal to the Body's own vertical axis receives a
    large cost. It remains available as a fallback for a solid with no lateral
    route.
    """
    import heapq
    starts = sorted(set(number for number in starts if number in graph))
    goals = set(number for number in goals if number in graph)
    if not starts or not goals:
        return None
    up = _body_up(body) if body is not None else None
    verticality = {}
    if faces is not None and up is not None:
        verticality = {number: _face_verticality(face, up)
                       for number, face in enumerate(faces, 1)}
    side_mode = bool(verticality and
                     all(verticality.get(number, 0.0) < 0.80 for number in starts) and
                     all(verticality.get(number, 0.0) < 0.80 for number in goals))
    queue, previous, costs = [], {}, {}
    for start in starts:
        costs[start] = 0.0
        previous[start] = None
        heapq.heappush(queue, (0.0, start))
    while queue:
        cost, current = heapq.heappop(queue)
        if cost != costs.get(current):
            continue
        if current in goals:
            route = []
            while current is not None:
                route.append(current)
                current = previous[current]
            return list(reversed(route))
        for neighbor in sorted(graph.get(current, ())):
            penalty = 1000.0 if side_mode and verticality.get(neighbor, 0.0) >= 0.80 else 0.0
            candidate = cost + 1.0 + penalty
            if candidate < costs.get(neighbor, float("inf")):
                costs[neighbor] = candidate
                previous[neighbor] = current
                heapq.heappush(queue, (candidate, neighbor))
    return None


def _synthetic_entries(source, faces, route):
    """Hydrate only the source faces required to carry phase across a route."""
    core = _core()
    result = []
    for index, number in enumerate(route):
        entry = {"object": source, "sub": "Face{}".format(number),
                 "face": faces[number - 1], "picked": None, "index": index}
        core.orient_entry(entry)
        result.append(entry)
    graph, _shared = core.build_graph(result)
    core.position_components(result, graph)
    return result


def _linear(transform):
    return [[float(transform[0]), float(transform[1])],
            [float(transform[2]), float(transform[3])]]


def _offset(transform):
    return [float(transform[4]), float(transform[5])]


def _inverse(matrix):
    determinant = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    if abs(determinant) <= EPS:
        return None
    return [[matrix[1][1] / determinant, -matrix[0][1] / determinant],
            [-matrix[1][0] / determinant, matrix[0][0] / determinant]]


def _multiply(left, right):
    return [[left[0][0] * right[0][0] + left[0][1] * right[1][0],
             left[0][0] * right[0][1] + left[0][1] * right[1][1]],
            [left[1][0] * right[0][0] + left[1][1] * right[1][0],
             left[1][0] * right[0][1] + left[1][1] * right[1][1]]]


def _affine_between(source_transform, target_transform):
    """Return the affine map taking one logical atlas into another."""
    inverse = _inverse(_linear(source_transform))
    if inverse is None:
        return None
    matrix = _multiply(_linear(target_transform), inverse)
    source_offset, target_offset = _offset(source_transform), _offset(target_transform)
    offset = [target_offset[0] - matrix[0][0] * source_offset[0] - matrix[0][1] * source_offset[1],
              target_offset[1] - matrix[1][0] * source_offset[0] - matrix[1][1] * source_offset[1]]
    return matrix, offset


def _transformed_transform(transform, matrix, offset):
    linear = _multiply(matrix, _linear(transform))
    old_offset = _offset(transform)
    return [linear[0][0], linear[0][1], linear[1][0], linear[1][1],
            matrix[0][0] * old_offset[0] + matrix[0][1] * old_offset[1] + offset[0],
            matrix[1][0] * old_offset[0] + matrix[1][1] * old_offset[1] + offset[1]]


def _nearest_isometry(matrix):
    """Discard metric stretch from an auxiliary curved-face atlas route.

    A Map Faces carrier keeps its own local metric.  The route establishes
    orientation and phase only, so a curved seam's tangential scale must never
    stretch the newly created carrier or change its pattern dimensions.
    """
    column = [matrix[0][0], matrix[1][0]]
    length = math.sqrt(_length_squared(column))
    if length <= EPS:
        return None
    x_axis = [column[0] / length, column[1] / length]
    determinant = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    sign = 1.0 if determinant >= 0.0 else -1.0
    y_axis = [-sign * x_axis[1], sign * x_axis[0]]
    return [[x_axis[0], y_axis[0]], [x_axis[1], y_axis[1]]]


def _apply_atlas_transform(entries, triangles, boundary, matrix, offset):
    """Register the just-created atlas. Existing persisted maps are untouched."""
    seen = set()
    for triangle in triangles:
        for vertex in triangle.get("v", []):
            if id(vertex) not in seen:
                seen.add(id(vertex))
                vertex["q"] = _apply(vertex["q"], matrix, offset)
    for segment in boundary:
        for key in ("a", "b"):
            vertex = segment.get(key)
            if vertex is not None and id(vertex) not in seen:
                seen.add(id(vertex))
                vertex["q"] = _apply(vertex["q"], matrix, offset)
    for entry in entries:
        entry["transform"] = _transformed_transform(entry["transform"], matrix, offset)


def _payload_record(payload, source_name, face_number):
    for record in payload.get("faces", []) or []:
        if (str(record.get("object", "")) == str(source_name) and
                _face_number(record.get("sub")) == face_number and
                len(record.get("transform", [])) == 6):
            return record
    return None


def _topology_phase_registration(document, entries, triangles, boundary):
    """Place a new atlas in an existing Body phase through its BRep topology.

    The route may traverse unselected faces, but only the new selected map is
    transformed.  This gives a disconnected selection the phase it would have
    had if all intermediate faces had been mapped in one run.
    """
    body = _single_source_body(entries)
    if body is None or not entries:
        return None
    sources = []
    for entry in entries:
        source = entry.get("object")
        if source is not None and source not in sources:
            sources.append(source)
    if len(sources) != 1:
        return None
    source = sources[0]
    targets = [_face_number(entry.get("sub")) for entry in entries]
    targets = [number for number in targets if number is not None]
    if not targets:
        return None

    references = []
    for order, obj in enumerate(list(getattr(document, "Objects", []) or [])):
        payload = _payload_from_object(obj)
        if payload is None:
            continue
        # Candidate matching below requires a coincident physical rim. That
        # geometry check is also the scope for a split solid or a different
        # movable Body, whose document ownership cannot define phase.
        for record in payload.get("faces", []) or []:
            number = _face_number(record.get("sub"))
            if (str(record.get("object", "")) == str(getattr(source, "Name", "")) and
                    number is not None and len(record.get("transform", [])) == 6):
                references.append((order, payload, record, number))
    if not references:
        return None

    faces, graph = _source_face_graph(source)
    if not faces:
        return None
    # Shortest BRep route is selected before document order; the latter makes
    # ties deterministic and retains the first map as the stable root.
    candidates = []
    for order, payload, record, number in references:
        route = _shortest_route(graph, [number], targets, faces=faces, body=body)
        if route is not None:
            # A mapped main wall is a more stable phase reference than a
            # neighbouring fillet. This resolves two equally short perimeter
            # routes without relying on face labels or selection order.
            target_area = float(getattr(faces[route[-1] - 1], "Area", 0.0))
            anchor_area = float(getattr(faces[number - 1], "Area", 0.0))
            candidates.append((len(route), -min(anchor_area, target_area),
                               -anchor_area, order, str(record.get("sub")),
                               payload, record, route))
    if not candidates:
        return None
    _distance, _area, _anchor_area, _order, _name, payload, record, route = min(candidates)
    synthetic = _synthetic_entries(source, faces, route)
    by_sub = {entry["sub"]: entry for entry in synthetic}
    anchor = by_sub.get(record.get("sub"))
    target_subs = set(entry.get("sub") for entry in entries)
    target = next((entry for entry in synthetic if entry["sub"] in target_subs), None)
    actual = next((entry for entry in entries if entry.get("sub") == target.get("sub")), None)
    if anchor is None or target is None or actual is None:
        return None
    root_to_global = _affine_between(anchor["transform"], record["transform"])
    if root_to_global is None:
        return None
    root_matrix, root_offset = root_to_global
    desired_target = _transformed_transform(target["transform"], root_matrix, root_offset)
    current_to_global = _affine_between(actual["transform"], desired_target)
    if current_to_global is None:
        return None
    route_matrix, _route_offset = current_to_global
    matrix = _nearest_isometry(route_matrix)
    if matrix is None:
        return None
    current_offset, desired_offset = _offset(actual["transform"]), _offset(desired_target)
    offset = [desired_offset[0] - matrix[0][0] * current_offset[0] - matrix[0][1] * current_offset[1],
              desired_offset[1] - matrix[1][0] * current_offset[0] - matrix[1][1] * current_offset[1]]
    _apply_atlas_transform(entries, triangles, boundary, matrix, offset)
    # The closest mapped face carries the reliable local atlas orientation,
    # while the oldest map remains the one persistent phase origin.
    return _body_root_origin(document, body)


def register_grid_to_body_phase(document, entries, triangles, boundary):
    """Register only the new map to the persistent Body phase at creation."""
    registered = _topology_phase_registration(document, entries, triangles, boundary)
    if registered is not None:
        return registered
    return align_grid_to_existing_body_map(document, entries, triangles, boundary)

def grid_origin_for_alignment(document, entries, triangles, bounds,
                              column_alignment, row_alignment="global"):
    """Choose a Map Faces preview phase from the requested alignment mode."""
    column_alignment = normalize_phase_alignment(column_alignment)
    row_alignment = normalize_row_alignment(row_alignment)
    centered = [(float(bounds[0]) + float(bounds[1])) * 0.5,
                (float(bounds[2]) + float(bounds[3])) * 0.5]
    global_origin = body_phase_grid_origin(document, entries, triangles, centered)
    x_index = {"left": 0, "center": None, "right": 1}.get(column_alignment)
    x_value = (float(global_origin[0]) if column_alignment == "global" else
               centered[0] if x_index is None else float(bounds[x_index]))
    if row_alignment == "global":
        y_value = float(global_origin[1])
    elif row_alignment == "center":
        y_value = centered[1]
    elif row_alignment == "bottom":
        y_value = mapped_edge_row(entries, triangles, centered, upper=False)
    else:
        y_value = mapped_edge_row(entries, triangles, centered, upper=True)
    return [x_value, y_value]



def _payload_from_object(obj):
    """Read a stored map payload without depending on any pattern package."""
    import base64
    import json
    import zlib
    chunks = list(getattr(obj, "MapPayloadChunks", []) or [])
    if not chunks:
        return None
    try:
        return json.loads(zlib.decompress(base64.b64decode("".join(chunks))).decode("utf-8"))
    except Exception:
        return None


def _same_source_body(document, payload, body):
    """A stored map is a phase reference only when it belongs to this Body."""
    faces = list(payload.get("faces", []) or [])
    if not faces:
        return False
    owners = []
    for record in faces:
        source = document.getObject(str(record.get("object", "")))
        owner = source_body(source)
        if owner is None:
            return False
        if owner not in owners:
            owners.append(owner)
    return len(owners) == 1 and owners[0] is body


def _segments(payload):
    return [(record.get("a"), record.get("b"))
            for record in payload.get("external_segments", []) or []
            if record.get("a", {}).get("p") and record.get("a", {}).get("q") and
            record.get("b", {}).get("p") and record.get("b", {}).get("q")]


def _carrier_segments(payload):
    """Read every physical carrier edge for a map nested within another map.

    A one-face map can meet an edge which is internal to a larger existing map,
    so that edge is not in the latter map's external rim.  The physical carrier
    still contains it, and its endpoints provide the neutral alignment record.
    """
    unique, result = set(), []
    for triangle in payload.get("carrier_triangles", payload.get("triangles", [])) or []:
        vertices = triangle.get("v", [])
        for left, right in zip(vertices, vertices[1:] + vertices[:1]):
            if not left.get("p") or not left.get("q") or not right.get("p") or not right.get("q"):
                continue
            key = tuple(sorted((tuple(round(float(value), 6) for value in left["p"]),
                                tuple(round(float(value), 6) for value in right["p"]))))
            if key not in unique:
                unique.add(key)
                result.append((left, right))
    return result


def _near_carrier_segments(payload, moving_segments, tolerance=0.05):
    """Return carrier edges that share an endpoint neighbourhood with a rim."""
    if not moving_segments:
        return _carrier_segments(payload)
    scale = 1.0 / tolerance
    buckets = {}
    for index, (left, right) in enumerate(_carrier_segments(payload)):
        for point in (left["p"], right["p"]):
            key = tuple(int(round(float(value) * scale)) for value in point)
            buckets.setdefault(key, set()).add(index)
    carrier = _carrier_segments(payload)
    found = set()
    for left, right in moving_segments:
        for point in (left["p"], right["p"]):
            base = tuple(int(round(float(value) * scale)) for value in point)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        found.update(buckets.get((base[0] + dx, base[1] + dy, base[2] + dz), set()))
    return [carrier[index] for index in sorted(found)]


def _unit(vector):
    length = math.sqrt(_length_squared(vector))
    return None if length <= EPS else [value / length for value in vector]


def _candidate(reference, moving, include_carrier=False):
    """Find the nearest physically coincident edge pair in two independent maps."""
    best = None
    left_segments, right_segments = _segments(reference), _segments(moving)
    if include_carrier:
        # The moving map's rim is the actual boundary to continue.  Search
        # only nearby edges in the reference carrier, so dense maps stay fast
        # and an unrelated interior diagonal cannot become a phase reference.
        left_segments += _near_carrier_segments(reference, right_segments)
    step_left, step_right = max(1, len(left_segments) // 600), max(1, len(right_segments) // 600)
    for left_a, left_b in left_segments[::step_left]:
        physical_left = _sub(left_b["p"], left_a["p"])
        logical_left = _sub(left_b["q"], left_a["q"])
        left_unit = _unit(physical_left)
        left_length = math.sqrt(_length_squared(logical_left))
        if left_unit is None or left_length <= EPS:
            continue
        for right_a, right_b in right_segments[::step_right]:
            physical_right = _sub(right_b["p"], right_a["p"])
            logical_right = _sub(right_b["q"], right_a["q"])
            right_unit = _unit(physical_right)
            right_length = math.sqrt(_length_squared(logical_right))
            if right_unit is None or right_length <= EPS:
                continue
            parallel = abs(_dot(left_unit, right_unit))
            ratio = min(left_length, right_length) / max(left_length, right_length)
            if parallel < 0.96 or ratio < 0.80:
                continue
            direct = (math.sqrt(_length_squared(_sub(left_a["p"], right_a["p"]))) +
                      math.sqrt(_length_squared(_sub(left_b["p"], right_b["p"]))))
            reverse = (math.sqrt(_length_squared(_sub(left_a["p"], right_b["p"]))) +
                       math.sqrt(_length_squared(_sub(left_b["p"], right_a["p"]))))
            if reverse < direct:
                right_a, right_b = right_b, right_a
            distance = min(direct, reverse) * 0.5
            # Registration is only valid at a real shared physical edge.  A
            # merely nearby parallel wall cannot provide a logical phase.
            if distance > 0.05:
                continue
            score = (distance,
                     -min(math.sqrt(_length_squared(physical_left)),
                          math.sqrt(_length_squared(physical_right))))
            if best is None or score < best[0]:
                best = (score, (left_a, left_b, right_a, right_b))
    return best


def _rotation(source, target):
    source, target = _unit(source), _unit(target)
    if source is None or target is None:
        return None
    cosine = _dot(source, target)
    sine = source[0] * target[1] - source[1] * target[0]
    return [[cosine, -sine], [sine, cosine]]


def _apply(point, matrix, offset):
    return [matrix[0][0] * float(point[0]) + matrix[0][1] * float(point[1]) + offset[0],
            matrix[1][0] * float(point[0]) + matrix[1][1] * float(point[1]) + offset[1]]


def _transform_entry(entry, matrix, offset):
    a, b, c, d, tx, ty = entry["transform"]
    entry["transform"] = [matrix[0][0] * a + matrix[0][1] * c,
                          matrix[0][0] * b + matrix[0][1] * d,
                          matrix[1][0] * a + matrix[1][1] * c,
                          matrix[1][0] * b + matrix[1][1] * d,
                          matrix[0][0] * tx + matrix[0][1] * ty + offset[0],
                          matrix[1][0] * tx + matrix[1][1] * ty + offset[1]]


def align_grid_to_existing_body_map(document, entries, triangles, boundary):
    """Register a new map through the closest coincident existing map rim.

    A map's initial atlas is deliberately local. When a prior map shares a
    physical boundary, its phase is transferred rigidly before the preview is
    made. This works for same-Body maps and independent solids from a split,
    while retaining the carrier and schema.
    """
    body = _single_source_body(entries)
    # Standalone split solids have no PartDesign Body. Registration remains
    # valid whenever two map carriers prove a shared physical rim; the rim is
    # the generic relation, not a body name or object-tree assumption.
    moving = {"carrier_triangles": triangles, "triangles": triangles,
              "external_segments": boundary}
    best = None
    for obj in list(getattr(document, "Objects", []) or []):
        payload = _payload_from_object(obj)
        if payload is None:
            continue
        # Candidate matching below requires a coincident physical rim. That
        # geometry check is also the scope for a split solid or a different
        # movable Body, whose document ownership cannot define phase.
        candidate = _candidate(payload, moving)
        if candidate is None:
            # The reference map may cover the shared edge on both sides, so
            # its native edge is internal rather than an exterior segment.
            candidate = _candidate(payload, moving, include_carrier=True)
        if candidate is None:
            continue
        score, pair = candidate
        # The oldest compatible map is the stable phase root for this rim.
        # Prefer document order over a later map's tiny proximity advantage:
        # otherwise a legacy or independently created map could restart the
        # phase that subsequent one-face maps inherit.
        key = (list(getattr(document, "Objects", []) or []).index(obj), score,
               str(getattr(obj, "Name", "")))
        if best is None or key < best[0]:
            best = (key, payload, pair)
    if best is None:
        return None
    _key, reference, (left_a, left_b, right_a, right_b) = best
    matrix = _rotation(_sub(right_b["q"], right_a["q"]),
                       _sub(left_b["q"], left_a["q"]))
    if matrix is None:
        return None
    right_mid = [(right_a["q"][0] + right_b["q"][0]) * 0.5,
                 (right_a["q"][1] + right_b["q"][1]) * 0.5]
    left_mid = [(left_a["q"][0] + left_b["q"][0]) * 0.5,
                (left_a["q"][1] + left_b["q"][1]) * 0.5]
    mapped_mid = _apply(right_mid, matrix, [0.0, 0.0])
    offset = [left_mid[0] - mapped_mid[0], left_mid[1] - mapped_mid[1]]
    seen = set()
    for triangle in triangles:
        for vertex in triangle.get("v", []):
            if id(vertex) not in seen:
                seen.add(id(vertex))
                vertex["q"] = _apply(vertex["q"], matrix, offset)
    for segment in boundary:
        for key in ("a", "b"):
            vertex = segment.get(key)
            if vertex is not None and id(vertex) not in seen:
                seen.add(id(vertex))
                vertex["q"] = _apply(vertex["q"], matrix, offset)
    for entry in entries:
        _transform_entry(entry, matrix, offset)
    # The selected reference is the oldest compatible physical neighbour;
    # use its stored phase even when it belongs to a different movable Body.
    origin = reference.get("grid", {}).get("origin")
    if not isinstance(origin, (tuple, list)) or len(origin) != 2:
        return None
    return [float(origin[0]), float(origin[1])]
