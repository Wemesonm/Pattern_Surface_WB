"""Closed, carrier-driven Diamond relief mesh for the Blender backend."""

import importlib.util
import math
from collections import Counter
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "auzyron_geometry_common", Path(__file__).with_name("geometry_common.py"))
_COMMON = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_COMMON)
EPS = _COMMON.EPS
_add = _COMMON._add
_barycentric = _COMMON._barycentric
_clip = _COMMON._clip
_cross = _COMMON._cross
_cross3 = _COMMON._cross3
_dot = _COMMON._dot
_interpolate = _COMMON._interpolate
_scale = _COMMON._scale
_sub = _COMMON._sub
_unit = _COMMON._unit
NativeBoundaryDistance = _COMMON.NativeBoundaryDistance
concave_relief = _COMMON.concave_relief


def _subdivide_facet(triangle, subdivisions):
    """Uniform barycentric samples, independent of carrier triangulation."""
    a, b, c = triangle
    def blend(i, j):
        return tuple((a[k] * (subdivisions-i-j) + b[k]*i + c[k]*j) / subdivisions
                     for k in range(3))
    for i in range(subdivisions):
        for j in range(subdivisions-i):
            yield (blend(i,j), blend(i+1,j), blend(i,j+1))
            if i+j < subdivisions-1:
                yield (blend(i+1,j), blend(i+1,j+1), blend(i,j+1))


def _lattice_cell(row, column, side, row_height, origin):
    def point(r, c):
        return (origin[0] + (c + 0.5 * (r % 2)) * side,
                origin[1] + r * row_height, 0.0)
    a, b, c, d = (point(row, column), point(row, column + 1),
                  point(row + 1, column), point(row + 1, column + 1))
    return ((a, b, d), (a, d, c)) if row % 2 else ((a, b, c), (b, d, c))


def dimensions(payload, params):
    height = float(params.get("diamond_height", 12.32))
    relief = float(params.get("pyramid_height", 1.5))
    resolution = int(params.get("resolution", 8))
    finish_offset = float(params.get("finish_offset", 0.045))
    contact = float(params.get("contact", 0.25))
    blend = float(params.get("base_blend", 0.0))
    if not all(math.isfinite(v) and v > 0 for v in (height, relief, finish_offset, contact)):
        raise ValueError("Diamond parameters must be finite and positive.")
    if not math.isfinite(blend) or blend < 0.0:
        raise ValueError("Edge transition width must be finite and nonnegative.")
    if not 1 <= resolution <= 40:
        raise ValueError("Resolution must be between 1 and 40.")
    # Map Faces divisions are only a visual/reference grid.  Diamond spacing
    # comes from the requested physical triangle height, regardless of how the
    # map preview was divided.
    natural_side = 2.0 * height / math.sqrt(3.0)
    requested_side = float(params.get("diamond_side", natural_side) or natural_side)
    if not math.isfinite(requested_side) or requested_side <= 0.0:
        requested_side = natural_side
    side = requested_side
    row_height = height
    grid = payload.get("grid", {}) or {}
    origin = list(grid.get("origin", [0.0, 0.0]))[:2]
    # A shared assembly may contain independently periodic components. The
    # first selected map fixes the visual Diamond lattice; refitting every
    # later component to its own perimeter would make matching map grids
    # produce differently sized Diamonds at their join.
    shared = payload.get("shared_pattern_phase") or {}
    if shared:
        try:
            side = float(shared["side"])
            row_height = float(shared["row_height"])
            origin = [float(value) for value in shared["origin"][:2]]
        except (KeyError, TypeError, ValueError):
            raise ValueError("Shared Diamond phase is incomplete.")
        if not all(math.isfinite(value) and value > 0.0 for value in (side, row_height)):
            raise ValueError("Shared Diamond phase has invalid dimensions.")
        modules = int(shared["modules"]) if shared.get("reference") and shared.get("modules") else None
    else:
        adjustments = payload.get("periodic_adjustments", []) or []
        if len(adjustments) > 1 or (adjustments and int(adjustments[0].get("axis", -1)) != 0):
            raise ValueError("Only one-axis periodic maps are supported by Blender.")
        modules = None
        if adjustments:
            fit = adjustments[0]
            period = float(fit["period"])
            modules = max(1, round(period / requested_side))
            tolerance = float(params.get("closure_fit_tolerance", 0.2))
            if abs(period / modules - requested_side) > tolerance + 1.0e-8:
                raise ValueError("Periodic Diamond closure exceeds the configured tolerance.")
            side, origin[0] = period / modules, float(fit.get("lower", origin[0]))
    edge_mode = "all" if params.get("blend_all_edges", False) else params.get("edge_transition", "lower")
    return {"diamond_height": height, "relief": relief, "side": side,
            "row_height": row_height, "origin": origin, "modules": modules,
            "resolution": resolution, "finish_offset": finish_offset,
            "contact": contact, "blend": blend, "edge_mode": edge_mode,
            "shared_phase": bool(shared)}


def _infer_axis(carrier):
    """Infer the physical row direction, independent of winding/world axes."""
    straight = [t for t in carrier if not t.get("curved", False)]
    total = (0.0, 0.0, 0.0)
    for triangle in straight or carrier:
        a,b,c = triangle["v"]
        u1,v1 = _sub(b["q"],a["q"])
        u2,v2 = _sub(c["q"],a["q"])
        determinant = u1*v2-u2*v1
        if abs(determinant)<EPS:
            continue
        dp1,dp2 = _sub(b["p"],a["p"]),_sub(c["p"],a["p"])
        tangent = _unit(_scale(_sub(_scale(dp2,u1),_scale(dp1,u2)),1/determinant))
        if tangent is not None:
            total = _add(total,_scale(tangent,abs(determinant)))
    return _unit(total)


def _planar_strips(carrier, bounds, period):
    """Recognize a rectangular atlas of planar walls, independent of world axes.

    Only use this path when the public carrier proves the complete strip topology.
    Curved carriers retain their sampled-surface path.
    """
    if period is None or any("face" not in t for t in carrier):
        return []
    groups = {}
    for triangle in carrier:
        groups.setdefault(triangle["face"], []).append(triangle)
    strips = []
    for triangles in groups.values():
        points = [v for t in triangles for v in t["v"]]
        normal = _unit(points[0]["n"])
        anchor = points[0]["p"]
        if normal is None or any(
                _dot(normal, v["n"]) < 1.0 - 1e-8 or
                abs(_dot(normal, _sub(v["p"], anchor))) > 1e-5 for v in points):
            return []
        low = min(v["q"][0] for v in points)
        high = max(v["q"][0] for v in points)
        bottom = min(v["q"][1] for v in points)
        top = max(v["q"][1] for v in points)
        area = sum(abs(_cross(*(v["q"] for v in t["v"]))) / 2 for t in triangles)
        if (high - low <= EPS or abs(bottom - bounds[2]) > 1e-6 or
                abs(top - bounds[3]) > 1e-6 or
                abs(area - (high-low)*(top-bottom)) > max(1e-5, area*1e-7)):
            return []
        corners = [min(points, key=lambda v: (v["q"][0]-x)**2 + (v["q"][1]-y)**2)["p"]
                   for x, y in ((low, bottom), (low, top), (high, bottom), (high, top))]
        strips.append({"low": low, "high": high, "normal": normal, "corners": corners})
    strips.sort(key=lambda s: s["low"])
    if len(strips) < 2 or abs(strips[-1]["high"]-strips[0]["low"]-period) > 1e-6:
        return []
    for i, strip in enumerate(strips):
        previous = strips[i-1]
        if i and abs(previous["high"] - strip["low"]) > 1e-6:
            return []
        if any(_dot(_sub(a, b), _sub(a, b)) > 1e-10
               for a, b in zip(previous["corners"][2:], strip["corners"][:2])):
            return []
    return strips


def _build_planar(strips, dim, bounds):
    """Tile in physical orthonormal wall coordinates, then clip without warping.

    The logical atlas supplies spacing/phase only. Its rectangular coordinates
    must not stretch a regular lattice to fit a tapered physical footprint.
    Each wall is a closed relief patch; the Blender worker unions it with CAD.
    """
    vertices, faces, facet_ids, patches, metrics = [], [], [], [], []
    side, height = dim["side"], dim["row_height"]
    facet_count = 0
    for strip in strips:
        start_face = len(faces)
        start_vertex = len(vertices)
        bottom_left, top_left, bottom_right, top_right = strip["corners"]
        normal = strip["normal"]
        u = _unit(_sub(bottom_right, bottom_left))
        if u is None:
            raise ValueError("Planar carrier has a degenerate bottom edge.")
        v = _unit(_cross3(normal, u))
        anchor = _scale(_add(bottom_left, bottom_right), 0.5)
        if u is None or v is None or _dot(v, _sub(top_left, bottom_left)) <= EPS:
            raise ValueError("Planar carrier frame has inconsistent orientation.")
        def local(p):
            d = _sub(p, anchor)
            return (_dot(d, u), _dot(d, v), 0.0)
        footprint = [local(p) for p in (bottom_left, bottom_right, top_right, top_left)]
        x0, x1 = min(p[0] for p in footprint), max(p[0] for p in footprint)
        y0, y1 = min(p[1] for p in footprint), max(p[1] for p in footprint)
        origin = (dim["origin"][0] - (strip["low"]+strip["high"])/2,
                  dim["origin"][1] - bounds[2])
        cache, physical_base, outer = {}, [], []
        def add(p):
            key = tuple(round(c, 8) for c in p)
            if key not in cache:
                cache[key] = len(vertices)
                base = _add(anchor, _add(_scale(u, p[0]), _scale(v, p[1])))
                vertices.append(_add(base, _scale(normal, p[2]+dim["finish_offset"])))
                physical_base.append(_sub(base, _scale(normal, dim["contact"])))
            return cache[key]
        rows = range(math.floor((y0-origin[1])/height)-1, math.ceil((y1-origin[1])/height)+1)
        cols = range(math.floor((x0-origin[0])/side)-2, math.ceil((x1-origin[0])/side)+2)
        for row in rows:
            for col in cols:
                for cell in _lattice_cell(row, col, side, height, origin):
                    apex = (sum(p[0] for p in cell)/3, sum(p[1] for p in cell)/3, dim["relief"])
                    for i in range(3):
                        original = [cell[i], cell[(i+1)%3], apex]
                        clipped = _clip(original, footprint)
                        clean = []
                        for p in clipped:
                            if not clean or _dot(_sub(p, clean[-1]), _sub(p, clean[-1])) > 1e-16:
                                clean.append(p)
                        if len(clean) > 1 and _dot(_sub(clean[0], clean[-1]), _sub(clean[0], clean[-1])) < 1e-16:
                            clean.pop()
                        facet_normal = _unit(_cross3(_sub(original[1], original[0]), _sub(original[2], original[0])))
                        for j in range(1, len(clean)-1):
                            triangle = [clean[0], clean[j], clean[j+1]]
                            if abs(_cross(*triangle)) < 1e-10:
                                continue
                            ids = tuple(add(p) for p in triangle)
                            outer.append(ids)
                            faces.append(ids)
                            facet_ids.append(facet_count+1)
                            metrics.append(max(abs(_dot(facet_normal, _sub(p, original[0]))) for p in triangle))
                        facet_count += 1
        if not outer:
            raise ValueError("A planar wall produced no relief facets.")
        count = len(physical_base)
        vertices.extend(physical_base)
        faces.extend(tuple(i+count for i in reversed(f)) for f in outer)
        facet_ids.extend([0]*len(outer))
        edges = Counter(tuple(sorted(e)) for f in outer for e in zip(f, f[1:]+f[:1]))
        for f in outer:
            for a, b in zip(f, f[1:]+f[:1]):
                if edges[tuple(sorted((a, b)))] == 1:
                    faces.append((b, a, a+count, b+count))
                    facet_ids.append(0)
        patches.append({"vertex_start": start_vertex, "vertex_end": len(vertices),
                        "face_start": start_face, "outer_face_end": start_face+len(outer),
                        "face_end": len(faces)})
    edges = Counter(tuple(sorted(e)) for f in faces for e in zip(f, f[1:]+f[:1]))
    return {"vertices": vertices, "faces": faces, "facet_ids": facet_ids,
            "dimensions": dim, "axis": None, "planar_patches": patches,
            "clip_support_planes": False,
            "stats": {"algorithm": "rigid_planar_clip", "faces": len(faces),
                      "vertices": len(vertices), "planar_patches": len(patches),
                      "max_facet_plane_error_mm": max(metrics, default=0),
                      "bad_edges_before_weld": sum(n != 2 for n in edges.values())}}


def _build_planar_shared(strips, dim, bounds):
    """Build planar periodic reference strips directly in shared logical q.

    The older planar path converted the lattice origin to each strip's local
    centre. That is harmless for one closed body, but destroys phase across
    separately exported components. Here q remains the lattice coordinate up
    to clipping; only the resulting points are projected into the physical
    planar strip.
    """
    vertices, faces, facet_ids, patches, metrics = [], [], [], [], []
    side, height, origin = dim["side"], dim["row_height"], dim["origin"]
    facet_count = 0
    for strip in strips:
        start_face, start_vertex = len(faces), len(vertices)
        bottom_left, top_left, bottom_right, top_right = strip["corners"]
        normal = strip["normal"]
        low, high = strip["low"], strip["high"]
        bottom, top = bounds[2], bounds[3]
        u = _unit(_sub(bottom_right, bottom_left))
        v = _unit(_cross3(normal, u)) if u is not None else None
        width = math.sqrt(_dot(_sub(bottom_right, bottom_left), _sub(bottom_right, bottom_left)))
        vertical = _dot(v, _sub(top_left, bottom_left)) if v is not None else 0.0
        if u is None or v is None or width <= EPS or vertical <= EPS:
            raise ValueError("Planar carrier frame has inconsistent orientation.")
        if high - low <= EPS or top - bottom <= EPS:
            raise ValueError("Planar carrier has a degenerate logical domain.")
        logical_footprint = [(low, bottom, 0.0), (high, bottom, 0.0),
                             (high, top, 0.0), (low, top, 0.0)]
        cache, physical_base, outer = {}, [], []

        def physical(point):
            along = (float(point[0]) - low) / (high - low) * width
            rise = (float(point[1]) - bottom) / (top - bottom) * vertical
            return _add(bottom_left, _add(_scale(u, along), _scale(v, rise)))

        def add(point):
            key = tuple(round(float(value), 8) for value in point)
            if key not in cache:
                cache[key] = len(vertices)
                base = physical(point)
                vertices.append(_add(base, _scale(normal, point[2] + dim["finish_offset"])))
                physical_base.append(_sub(base, _scale(normal, dim["contact"])))
            return cache[key]

        rows = range(math.floor((bottom-origin[1])/height)-1,
                     math.ceil((top-origin[1])/height)+1)
        cols = range(math.floor((low-origin[0])/side)-2,
                     math.ceil((high-origin[0])/side)+2)
        for row in rows:
            for col in cols:
                for cell in _lattice_cell(row, col, side, height, origin):
                    apex = (sum(point[0] for point in cell)/3,
                            sum(point[1] for point in cell)/3, dim["relief"])
                    for index in range(3):
                        original = [cell[index], cell[(index+1) % 3], apex]
                        clipped = _clip(original, logical_footprint)
                        clean = []
                        for point in clipped:
                            if not clean or _dot(_sub(point, clean[-1]), _sub(point, clean[-1])) > 1e-16:
                                clean.append(point)
                        if len(clean) > 1 and _dot(_sub(clean[0], clean[-1]), _sub(clean[0], clean[-1])) < 1e-16:
                            clean.pop()
                        physical_triangle = [physical(point) for point in original]
                        facet_normal = _unit(_cross3(_sub(physical_triangle[1], physical_triangle[0]),
                                                     _sub(physical_triangle[2], physical_triangle[0])))
                        for index in range(1, len(clean)-1):
                            triangle = [clean[0], clean[index], clean[index+1]]
                            if abs(_cross(*triangle)) < 1e-10:
                                continue
                            ids = tuple(add(point) for point in triangle)
                            outer.append(ids)
                            faces.append(ids)
                            facet_ids.append(facet_count+1)
                            physical_piece = [physical(point) for point in triangle]
                            metrics.append(max(abs(_dot(facet_normal, _sub(point, physical_triangle[0])))
                                               for point in physical_piece))
                        facet_count += 1
        if not outer:
            raise ValueError("A planar wall produced no relief facets.")
        count = len(physical_base)
        vertices.extend(physical_base)
        faces.extend(tuple(index+count for index in reversed(face)) for face in outer)
        facet_ids.extend([0] * len(outer))
        edges = Counter(tuple(sorted(edge)) for face in outer for edge in zip(face, face[1:]+face[:1]))
        for face in outer:
            for left, right in zip(face, face[1:]+face[:1]):
                if edges[tuple(sorted((left, right)))] == 1:
                    faces.append((right, left, left+count, right+count))
                    facet_ids.append(0)
        patches.append({"vertex_start": start_vertex, "vertex_end": len(vertices),
                        "face_start": start_face, "outer_face_end": start_face+len(outer),
                        "face_end": len(faces)})
    edges = Counter(tuple(sorted(edge)) for face in faces for edge in zip(face, face[1:]+face[:1]))
    return {"vertices": vertices, "faces": faces, "facet_ids": facet_ids,
            "dimensions": dim, "axis": None, "planar_patches": patches,
            "clip_support_planes": False,
            "stats": {"algorithm": "rigid_planar_shared_phase", "faces": len(faces),
                      "vertices": len(vertices), "planar_patches": len(patches),
                      "max_facet_plane_error_mm": max(metrics, default=0),
                      "bad_edges_before_weld": sum(count != 2 for count in edges.values())}}


def _regular_sampled_domain(carrier, bounds, dim):
    """Recognize a complete periodic strip without internal cutouts."""
    if not dim["modules"]:
        return False
    x0, x1, y0, y1 = bounds
    period = dim["side"] * dim["modules"]
    if abs(x1 - x0 - period) > 1e-6:
        return False
    area = sum(abs(_cross(*(v["q"] for v in t["v"]))) / 2 for t in carrier)
    return abs(area - (x1-x0)*(y1-y0)) <= max(1e-6, area*1e-8)


def _build_regular_sampled(payload, dim):
    """PAT-REQ-071: preserve the approved September 6 facet topology."""
    carrier = list(payload.get("carrier_triangles", payload.get("triangles", [])))
    if not carrier:
        raise ValueError("The map has no valid physical carrier.")
    side, row_height, origin = dim["side"], dim["row_height"], dim["origin"]
    subdivisions = dim["resolution"]
    axis = _infer_axis(carrier)
    vertices, faces, facet_ids = [], [], []
    backing, mapped_cache = [], {}
    raw_cache = {}
    boundary = (NativeBoundaryDistance(payload, dim["blend"], dim["edge_mode"])
                if dim["blend"] else None)

    # The map carrier is a dense sampling mesh, not the pattern topology.
    # Project each logical lattice point once and build each logical cell once.
    # The previous implementation iterated every carrier triangle and therefore
    # duplicated the same cells thousands of times on dense mapped surfaces.
    bounds = payload.get("bounds", []) or []
    if len(bounds) != 4:
        raise ValueError("The map does not contain usable logical bounds.")
    min_x, max_x, min_y, max_y = (float(value) for value in bounds)
    period = side * dim["modules"] if dim["modules"] else None
    aligned_rows = all(abs((y-origin[1])/row_height-round((y-origin[1])/row_height)) < 1e-7
                       for y in (min_y, max_y))
    rim_domain = [(min_x-side, min_y), (max_x+side, min_y),
                  (max_x+side, max_y), (min_x-side, max_y)]

    def periodic_point(point):
        if period is None:
            return tuple(point)
        x = (point[0] - origin[0]) % period
        if min(x, period - x) < 1.0e-7:
            x = 0.0
        return (origin[0] + x,) + tuple(point[1:])
    # Keep candidate lists local to the sampled carrier.  Using one whole
    # pattern module per bucket made every projection inspect hundreds of
    # triangles on the dense fillet mesh.
    bucket_size = max(side, row_height) / 4.0
    buckets = {}
    for index, item in enumerate(carrier):
        points = [tuple(vertex["q"]) for vertex in item.get("v", [])]
        if len(points) != 3:
            continue
        low_x, high_x = min(point[0] for point in points), max(point[0] for point in points)
        low_y, high_y = min(point[1] for point in points), max(point[1] for point in points)
        for bx in range(math.floor((low_x - min_x) / bucket_size),
                        math.floor((high_x - min_x) / bucket_size) + 1):
            for by in range(math.floor((low_y - min_y) / bucket_size),
                            math.floor((high_y - min_y) / bucket_size) + 1):
                buckets.setdefault((bx, by), []).append(index)

    def locate(point):
        bx = math.floor((point[0] - min_x) / bucket_size)
        by = math.floor((point[1] - min_y) / bucket_size)
        candidates = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                candidates.update(buckets.get((bx + dx, by + dy), []))
        best = None
        best_margin = -float("inf")
        for index in candidates:
            item = carrier[index]
            weights = _barycentric(point, [vertex["q"] for vertex in item["v"]])
            if weights is None:
                continue
            margin = min(weights)
            if margin >= -1.0e-7 and margin > best_margin:
                best, best_margin = item, margin
        return best

    def raw_point(point):
        point = periodic_point(point)
        key = (round(point[0], 7), round(point[1], 7))
        if key not in raw_cache:
            triangle = locate(point)
            mapped = _interpolate(point, triangle) if triangle else None
            raw_cache[key] = ((*mapped, triangle.get("component", 0))
                              if mapped is not None else None)
        return raw_cache[key]

    def map_point(point):
        point = periodic_point(point)
        key = (round(point[0], 7), round(point[1], 7))
        if key in mapped_cache:
            return mapped_cache[key]
        value = raw_point(point)
        if value is None:
            mapped_cache[key] = None
            return None
        physical, carrier_normal, component = value
        # Blend the placement normal from neighboring physical points.  This
        # removes the serrated strip caused by switching source faces while
        # keeping every generated triangle flat and faceted.
        window = min(side, row_height) * 0.02
        left = raw_point((point[0] - window, point[1]))
        right = raw_point((point[0] + window, point[1]))
        normal = carrier_normal
        # Derive the normal from the mapped positions at every node. Using a
        # carrier face normal here makes adjacent source triangles choose
        # different offsets at the same logical grid seam; that creates the
        # self-overlap which later breaks Blender's Boolean. The finite
        # difference is continuous across those seams and matches the
        # analytic tangent frame used by the original Blender reconstruction.
        down = raw_point((point[0], point[1] - window))
        up = raw_point((point[0], point[1] + window))
        if left and right and down and up:
            tangent_u = _sub(right[0], left[0])
            tangent_v = _sub(up[0], down[0])
            candidate = _unit(_cross3(tangent_u, tangent_v))
            if candidate is not None:
                if _dot(candidate, carrier_normal) < 0.0:
                    candidate = _scale(candidate, -1.0)
                normal = candidate
        mapped_cache[key] = (physical, normal, component)
        return mapped_cache[key]

    def point_pair(point):
        value = map_point(point[:2])
        if value is None:
            return None
        physical, normal, component = value
        # The mapped carrier already provides the local surface normal.  Do
        # not project it onto a global or longitudinal axis: that loses the
        # wall/fillet component and creates a gap exactly at the lower corner.
        relief = concave_relief(point[2], boundary.distance(physical, component),
                                dim["blend"], dim["relief"]) if boundary else point[2]
        outer = _add(physical, _scale(normal, relief + dim["finish_offset"]))
        inner = _sub(physical, _scale(normal, dim["contact"]))
        return outer, inner

    def add_vertex(point):
        point = periodic_point(point)
        key = (round(point[0], 7), round(point[1], 7), round(point[2], 7))
        value = point_pair(point)
        if value is None:
            return None
        if key not in vertex_cache:
            vertex_cache[key] = len(vertices)
            vertices.append(value[0])
            backing.append(value[1])
        return vertex_cache[key]

    facet = 0
    vertex_cache = {}
    row0 = math.floor((min_y - origin[1]) / row_height) - 1
    row1 = math.ceil((max_y - origin[1]) / row_height) + 1
    col0 = math.floor((min_x - origin[0]) / side) - 1
    col1 = math.ceil((max_x - origin[0]) / side) + 1
    for row in range(row0, row1 + 1):
        for column in range(col0, col1 + 1):
            for lattice in _lattice_cell(row, column, side, row_height, origin):
                center = (sum(point[0] for point in lattice) / 3.0,
                          sum(point[1] for point in lattice) / 3.0)
                if period is not None and not origin[0] <= center[0] < origin[0] + period:
                    continue
                if aligned_rows and not (min_x - EPS <= center[0] <= max_x + EPS and
                        min_y - EPS <= center[1] <= max_y + EPS):
                    continue
                apex = (center[0], center[1], dim["relief"])
                for corner in range(3):
                    polygon = [lattice[corner], lattice[(corner + 1) % 3], apex]
                    for index in range(1, len(polygon) - 1):
                        for small in _subdivide_facet((polygon[0], polygon[index], polygon[index + 1]), subdivisions):
                            pieces = [small]
                            if not aligned_rows:
                                # Preserve the uniform facet interior; only cut
                                # samples crossing the actual open strip rims.
                                clipped = _clip(list(small), rim_domain)
                                pieces = [(clipped[0], clipped[j], clipped[j+1])
                                          for j in range(1, len(clipped)-1)]
                            for piece in pieces:
                                if abs(_cross(*[p[:2] for p in piece])) < EPS:
                                    continue
                                ids = [add_vertex(point) for point in piece]
                                if None not in ids and len(set(ids)) == 3:
                                    faces.append(tuple(ids))
                                    facet_ids.append(facet + 1)
                    facet += 1
    if not faces:
        raise ValueError("No Diamond cell intersects the mapped carrier.")
    used = sorted({i for face in faces for i in face})
    remap = {old: new for new, old in enumerate(used)}
    vertices = [vertices[i] for i in used]
    backing = [backing[i] for i in used]
    faces = [tuple(remap[i] for i in face) for face in faces]
    outer_faces = list(faces)
    offset = len(vertices)
    vertices.extend(backing)
    faces.extend(tuple(offset + index for index in reversed(face)) for face in outer_faces)
    edge_counts = Counter(tuple(sorted(edge)) for face in outer_faces
                          for edge in zip(face, face[1:] + face[:1]))
    for face in outer_faces:
        for left, right in zip(face, face[1:] + face[:1]):
            if edge_counts[tuple(sorted((left, right)))] == 1:
                faces.append((right, left, offset + left, offset + right))
                facet_ids.append(0)
    final_counts = Counter(tuple(sorted(edge)) for face in faces
                           for edge in zip(face, face[1:] + face[:1]))
    bad = sum(count != 2 for count in final_counts.values())
    return {"vertices": vertices, "faces": faces,
            "facet_ids": facet_ids + [0] * (len(faces) - len(facet_ids)),
            "dimensions": dim, "axis": axis,
            "clip_support_planes": False,
            "stats": {"algorithm": "regular_sampled_facets", "outer_faces": len(outer_faces), "faces": len(faces),
                      "vertices": len(vertices), "facets": facet,
                      "bad_edges_before_weld": bad}}


def build(payload, params):
    dim = dimensions(payload, params)
    carrier = list(payload.get("carrier_triangles", payload.get("triangles", [])))
    if not carrier:
        raise ValueError("The map has no valid physical carrier.")
    side, row_height, origin = dim["side"], dim["row_height"], dim["origin"]
    subdivisions = dim["resolution"]
    axis = _infer_axis(carrier)
    vertices, faces, facet_ids = [], [], []
    backing, mapped_cache = [], {}
    logical_vertices = []
    raw_cache = {}
    boundary = (NativeBoundaryDistance(payload, dim["blend"], dim["edge_mode"])
                if dim["blend"] else None)

    # The map carrier is a dense sampling mesh, not the pattern topology.
    # Project each logical lattice point once and build each logical cell once.
    # The previous implementation iterated every carrier triangle and therefore
    # duplicated the same cells thousands of times on dense mapped surfaces.
    bounds = payload.get("bounds", []) or []
    if len(bounds) != 4:
        raise ValueError("The map does not contain usable logical bounds.")
    min_x, max_x, min_y, max_y = (float(value) for value in bounds)
    period = side * dim["modules"] if dim["modules"] else None
    strips = _planar_strips(carrier, bounds, period)
    if strips and not dim["blend"]:
        return (_build_planar_shared(strips, dim, bounds)
                if dim.get("shared_phase") else _build_planar(strips, dim, bounds))
    if _regular_sampled_domain(carrier, bounds, dim):
        return _build_regular_sampled(payload, dim)

    # The logical carrier ends at a periodic seam, while a Diamond facet can
    # cross it.  Give boundary clipping a translated copy on each side of that
    # seam.  Physical vertices stay unchanged and are canonicalized later by
    # periodic_point(), so the copies cannot create duplicate seam geometry.
    carrier_domains = list(carrier)
    if period is not None:
        for offset in (-period, period):
            for item in carrier:
                clone = dict(item)
                clone["v"] = []
                for vertex in item["v"]:
                    mapped_vertex = dict(vertex)
                    mapped_vertex["q"] = [vertex["q"][0] + offset,
                                          vertex["q"][1]]
                    clone["v"].append(mapped_vertex)
                carrier_domains.append(clone)

    def periodic_point(point):
        if period is None:
            return tuple(point)
        x = (point[0] - origin[0]) % period
        if min(x, period - x) < 1.0e-7:
            x = 0.0
        return (origin[0] + x,) + tuple(point[1:])
    # Keep candidate lists local to the sampled carrier.  Using one whole
    # pattern module per bucket made every projection inspect hundreds of
    # triangles on the dense fillet mesh.
    bucket_size = max(side, row_height) / max(4, min(subdivisions, 24))
    buckets = {}
    for index, item in enumerate(carrier_domains):
        points = [tuple(vertex["q"]) for vertex in item.get("v", [])]
        if len(points) != 3:
            continue
        low_x, high_x = min(point[0] for point in points), max(point[0] for point in points)
        low_y, high_y = min(point[1] for point in points), max(point[1] for point in points)
        for bx in range(math.floor((low_x - min_x) / bucket_size),
                        math.floor((high_x - min_x) / bucket_size) + 1):
            for by in range(math.floor((low_y - min_y) / bucket_size),
                            math.floor((high_y - min_y) / bucket_size) + 1):
                buckets.setdefault((bx, by), []).append(index)

    def locate(point):
        bx = math.floor((point[0] - min_x) / bucket_size)
        by = math.floor((point[1] - min_y) / bucket_size)
        candidates = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                candidates.update(buckets.get((bx + dx, by + dy), []))
        best = None
        best_margin = -float("inf")
        for index in candidates:
            item = carrier_domains[index]
            weights = _barycentric(point, [vertex["q"] for vertex in item["v"]])
            if weights is None:
                continue
            margin = min(weights)
            if margin >= -1.0e-7 and margin > best_margin:
                best, best_margin = item, margin
        return best

    def overlapping_carriers(triangle):
        """Return carrier facets whose logical domain intersects *triangle*.

        The carrier is the authoritative boundary of the selected faces.  A
        lattice cell may cross that boundary, so its facets must be clipped to
        these triangles rather than kept solely because their center is inside
        the map's rectangular logical bounds.
        """
        low_x = min(point[0] for point in triangle)
        high_x = max(point[0] for point in triangle)
        low_y = min(point[1] for point in triangle)
        high_y = max(point[1] for point in triangle)
        candidates = set()
        for bx in range(math.floor((low_x - min_x) / bucket_size),
                        math.floor((high_x - min_x) / bucket_size) + 1):
            for by in range(math.floor((low_y - min_y) / bucket_size),
                            math.floor((high_y - min_y) / bucket_size) + 1):
                candidates.update(buckets.get((bx, by), []))
        return (carrier_domains[index] for index in candidates)

    def raw_point(point):
        point = periodic_point(point)
        key = (round(point[0], 7), round(point[1], 7))
        if key not in raw_cache:
            triangle = locate(point)
            mapped = _interpolate(point, triangle) if triangle else None
            raw_cache[key] = ((*mapped, triangle.get("component", 0))
                              if mapped is not None else None)
        return raw_cache[key]

    def map_point(point):
        point = periodic_point(point)
        key = (round(point[0], 7), round(point[1], 7))
        if key in mapped_cache:
            return mapped_cache[key]
        value = raw_point(point)
        if value is None:
            mapped_cache[key] = None
            return None
        physical, carrier_normal, component = value
        # The native CAD normal field is continuous across tangent source
        # faces. Finite differences of clipped carrier triangles can instead
        # measure tessellation chords, or jump when a neighbor crosses a trim.
        # Use the interpolated CAD field for this boundary-aware path.
        normal = carrier_normal
        mapped_cache[key] = (physical, normal, component)
        return mapped_cache[key]

    def point_pair(point):
        value = map_point(point[:2])
        if value is None:
            return None
        physical, normal, component = value
        # PAT-REQ-076: use the same full normal as the regular strip path.
        # Removing its longitudinal component changes the fillet relief merely
        # because another part of the domain has a trimmed boundary.
        relief = concave_relief(point[2], boundary.distance(physical, component),
                                dim["blend"], dim["relief"]) if boundary else point[2]
        outer = _add(physical, _scale(normal, relief + dim["finish_offset"]))
        inner = _sub(physical, _scale(normal, dim["contact"]))
        return outer, inner

    def add_vertex(point):
        point = periodic_point(point)
        # The same boundary intersection is evaluated once from each adjacent
        # carrier triangle.  OCC's carrier coordinates differ by tiny floating
        # point noise there; using a 0.00001 mm logical weld gives both
        # fragments the same vertex without changing visible geometry.
        key = (round(point[0], 5), round(point[1], 5), round(point[2], 5))
        value = point_pair(point)
        if value is None:
            return None
        if key not in vertex_cache:
            vertex_cache[key] = len(vertices)
            vertices.append(value[0])
            backing.append(value[1])
            logical_vertices.append(tuple(point))
        return vertex_cache[key]

    facet = 0
    vertex_cache = {}
    row0 = math.floor((min_y - origin[1]) / row_height) - 1
    row1 = math.ceil((max_y - origin[1]) / row_height) + 1
    col0 = math.floor((min_x - origin[0]) / side) - 1
    col1 = math.ceil((max_x - origin[0]) / side) + 1
    for row in range(row0, row1 + 1):
        for column in range(col0, col1 + 1):
            for lattice in _lattice_cell(row, column, side, row_height, origin):
                center = (sum(point[0] for point in lattice) / 3.0,
                          sum(point[1] for point in lattice) / 3.0)
                if period is not None and not origin[0] - EPS <= center[0] < origin[0] + period - EPS:
                    continue
                # A coarse bounds test only eliminates cells that cannot
                # touch the carrier at all.  The precise face boundary is
                # applied below to every subdivided pyramid facet.
                if (max(point[0] for point in lattice) < min_x - EPS or
                        min(point[0] for point in lattice) > max_x + EPS or
                        max(point[1] for point in lattice) < min_y - EPS or
                        min(point[1] for point in lattice) > max_y + EPS):
                    continue
                apex = (center[0], center[1], dim["relief"])
                for corner in range(3):
                    polygon = [lattice[corner], lattice[(corner + 1) % 3], apex]
                    # PAT-REQ-076: the carrier defines the domain, not the
                    # tessellation inside each complete Diamond facet sample.
                    for small in _subdivide_facet(polygon, subdivisions):
                        clips = []
                        for carrier_triangle in overlapping_carriers(small):
                            clipped = _clip(small, [vertex["q"] for vertex in carrier_triangle["v"]])
                            if len(clipped) >= 3:
                                clips.append(clipped)
                        covered_area = sum(abs(_cross(poly[0], poly[k], poly[k+1]))
                                           for poly in clips for k in range(1, len(poly)-1))
                        if abs(covered_area - abs(_cross(*small))) <= 1e-8:
                            clips = [small]
                        for clipped in clips:
                            for vertex_index in range(1, len(clipped)-1):
                                fragment = [clipped[0], clipped[vertex_index], clipped[vertex_index+1]]
                                if abs(_cross(*fragment)) <= EPS:
                                    continue
                                ids = [add_vertex(point) for point in fragment]
                                if None not in ids and len(set(ids)) == 3:
                                    faces.append(tuple(ids))
                                    facet_ids.append(facet+1)
                    facet += 1
    if not faces:
        raise ValueError("No Diamond cell intersects the mapped carrier.")
    # PAT-REQ-069: refine AFTER boundary clipping with shared edge splits.
    # This restores independent pattern resolution without T-junctions at
    # carrier seams. Every new point is evaluated on the original map.
    target = max(side, row_height) / subdivisions
    def unwrap(points):
        points = [list(p) for p in points]
        if period is not None:
            anchor = points[0][0]
            for p in points[1:]:
                p[0] += round((anchor-p[0])/period)*period
        return points
    refinement_rounds = 0
    for iteration in range(16):
        split = {}
        for face in faces:
            for a,b in zip(face, face[1:]+face[:1]):
                edge = tuple(sorted((a,b)))
                if edge in split:
                    continue
                pa,pb = unwrap([logical_vertices[a], logical_vertices[b]])
                if math.hypot(pa[0]-pb[0],pa[1]-pb[1]) > target*1.001:
                    midpoint = tuple((pa[k]+pb[k])/2 for k in range(3))
                    index = add_vertex(midpoint)
                    if index is None:
                        raise ValueError("Cannot refine a mapped boundary point.")
                    split[edge] = index
        if not split:
            break
        new_faces,new_ids = [],[]
        for face,fid in zip(faces,facet_ids):
            a,b,c=face
            mids=[split.get(tuple(sorted(edge))) for edge in ((a,b),(b,c),(c,a))]
            count=sum(m is not None for m in mids)
            if count==0:
                triangles=[face]
            elif count==3:
                ab,bc,ca=mids
                triangles=[(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)]
            else:
                # Rotate so the single split is AB, or the two splits AB/BC.
                pivot=(next(i for i,m in enumerate(mids) if m is not None)
                       if count==1 else (next(i for i,m in enumerate(mids) if m is None)+1)%3)
                a,b,c=face[pivot:]+face[:pivot]
                ab,bc,ca=mids[pivot:]+mids[:pivot]
                triangles=([(a,ab,c),(ab,b,c)] if count==1 else
                           [(b,bc,ab),(a,ab,c),(ab,bc,c)])
            for triangle in triangles:
                if len(set(triangle))==3:
                    new_faces.append(triangle);new_ids.append(fid)
        faces,facet_ids=new_faces,new_ids
        refinement_rounds+=1
        if len(faces)>2000000:
            raise ValueError("Requested pattern resolution exceeds two million faces.")
    else:
        raise ValueError("Pattern refinement did not converge.")
    # Stitch collinear carrier boundary nodes before constructing side walls.
    # Otherwise a T-junction creates two internal caps sharing a four-face edge.
    counts=Counter(tuple(sorted(e)) for f in faces for e in zip(f,f[1:]+f[:1]))
    open_edges=[e for e,n in counts.items() if n==1]
    nodes={i for e in open_edges for i in e}
    bins={}
    bin_size=max(target,0.1)
    for i in nodes:
        p=logical_vertices[i]
        for shift in ((-period,0,period) if period is not None else (0,)):
            q=(p[0]+shift,p[1],p[2])
            bins.setdefault((math.floor(q[0]/bin_size),math.floor(q[1]/bin_size)),[]).append((i,q))
    cuts={}
    for a,b in open_edges:
        pa,pb=unwrap([logical_vertices[a],logical_vertices[b]])
        d=[pb[k]-pa[k] for k in range(3)];length=sum(x*x for x in d)
        if length<1e-12:continue
        found={}
        for ix in range(math.floor(min(pa[0],pb[0])/bin_size)-1,math.floor(max(pa[0],pb[0])/bin_size)+2):
            for iy in range(math.floor(min(pa[1],pb[1])/bin_size)-1,math.floor(max(pa[1],pb[1])/bin_size)+2):
                for i,q in bins.get((ix,iy),[]):
                    if i in (a,b):continue
                    t=sum((q[k]-pa[k])*d[k] for k in range(3))/length
                    if 1e-6<t<1-1e-6 and sum((q[k]-pa[k]-t*d[k])**2 for k in range(3))<1e-10:
                        found[i]=t
        if found:cuts[(a,b)]=[i for i,t in sorted(found.items(),key=lambda x:x[1])]
    if cuts:
        stitched,stitched_ids=[],[]
        for face,fid in zip(faces,facet_ids):
            ring=[]
            for a,b in zip(face,face[1:]+face[:1]):
                ring.append(a)
                edge=tuple(sorted((a,b)));extra=cuts.get(edge,[])
                ring.extend(extra if a==edge[0] else reversed(extra))
            if len(ring)==3:
                stitched.append(face);stitched_ids.append(fid)
            else:
                points=unwrap([logical_vertices[i] for i in face])
                center=add_vertex(tuple(sum(p[k] for p in points)/3 for k in range(3)))
                if center is None:raise ValueError("Cannot stitch the mapped seam.")
                for a,b in zip(ring,ring[1:]+ring[:1]):
                    if len({a,b,center})==3:
                        stitched.append((a,b,center));stitched_ids.append(fid)
        faces,facet_ids=stitched,stitched_ids
    # Adjacent trimmed carrier facets can interpolate the same logical seam
    # point with round-off-level differences.  The cell clipping path may then
    # leave two vertices at one physical point; closing both boundary fans
    # produces four side walls on that edge.  Canonicalize only vertices that
    # agree in logical *and* physical space within the carrier tolerance.
    # This is topology cleanup, not smoothing or a change to Diamond facets.
    canonical = {}
    remap = {}
    for index, logical in enumerate(logical_vertices):
        # Four decimals exceeds the 0.005 mm native-boundary chord tolerance
        # while avoiding round-half-even splits such as 333.144374999 / .144375.
        key = tuple(round(value, 4) for value in logical)
        previous = canonical.get(key)
        if previous is None:
            canonical[key] = index
            remap[index] = index
            continue
        if (sum((vertices[index][axis] - vertices[previous][axis]) ** 2
                for axis in range(3)) <= 1.0e-10 and
                sum((backing[index][axis] - backing[previous][axis]) ** 2
                    for axis in range(3)) <= 1.0e-10):
            remap[index] = previous
        else:
            # A self-overlapping logical atlas can legitimately reuse q at
            # different physical points. Keep those branches distinct.
            canonical[(key, index)] = index
            remap[index] = index
    if any(index != target for index, target in remap.items()):
        compact_faces, compact_ids = [], []
        for face, facet_id in zip(faces, facet_ids):
            face = tuple(remap[index] for index in face)
            if len(set(face)) == len(face):
                compact_faces.append(face)
                compact_ids.append(facet_id)
        faces, facet_ids = compact_faces, compact_ids
    # A failed sample may allocate vertices before a triangle is rejected.
    # Compact both shells together, retaining every accepted face unchanged.
    used = sorted({index for face in faces for index in face})
    remap = {old: new for new, old in enumerate(used)}
    vertices = [vertices[index] for index in used]
    backing = [backing[index] for index in used]
    faces = [tuple(remap[index] for index in face) for face in faces]
    outer_faces = list(faces)
    offset = len(vertices)
    vertices.extend(backing)
    faces.extend(tuple(offset + index for index in reversed(face)) for face in outer_faces)
    edge_counts = Counter(tuple(sorted(edge)) for face in outer_faces
                          for edge in zip(face, face[1:] + face[:1]))
    for face in outer_faces:
        for left, right in zip(face, face[1:] + face[:1]):
            if edge_counts[tuple(sorted((left, right)))] == 1:
                faces.append((right, left, offset + left, offset + right))
                facet_ids.append(0)
    final_counts = Counter(tuple(sorted(edge)) for face in faces
                           for edge in zip(face, face[1:] + face[:1]))
    bad = sum(count != 2 for count in final_counts.values())
    return {"vertices": vertices, "faces": faces,
            "facet_ids": facet_ids + [0] * (len(faces) - len(facet_ids)),
            "dimensions": dim, "axis": axis,
            # PAT-REQ-085: the carrier already clips every partial facet to
            # the exact selected CAD domain. A secondary adjacent-face plane
            # Boolean only approximates a curved/trimmed rim and can deform
            # the last full-height Diamond cells.
            "clip_support_planes": False,
            "stats": {"outer_faces": len(outer_faces), "faces": len(faces),
                      "vertices": len(vertices), "facets": facet,
                      "refinement_rounds": refinement_rounds,
                      "target_edge_mm": target,
                      "bad_edges_before_weld": bad}}
