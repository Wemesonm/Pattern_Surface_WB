"""Blender background worker. Run with Blender --background --python worker.py -- job.json."""

import importlib.util
import json
import shutil
import sys
from pathlib import Path


def _job_path():
    args = sys.argv[sys.argv.index("--") + 1:]
    paths = [argument for argument in args if argument != "--interactive"]
    if len(paths) != 1:
        raise RuntimeError("Expected exactly one Blender job JSON path.")
    return Path(paths[0])


def _interactive():
    return "--interactive" in sys.argv


def _write_report(path, report):
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def _clear_factory_scene():
    """Remove Blender's startup objects before importing the Auzyron result."""
    import bpy
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def _import_geometry(path):
    spec = importlib.util.spec_from_file_location("auzyron_geometry_closed", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _import_stl(path):
    import bpy
    bpy.ops.object.select_all(action="DESELECT")
    if hasattr(bpy.ops.wm, "stl_import"):
        bpy.ops.wm.stl_import(filepath=str(path))
    else:
        bpy.ops.import_mesh.stl(filepath=str(path))
    selected = list(bpy.context.selected_objects)
    if not selected:
        raise RuntimeError("Blender imported no source body from STL.")
    if len(selected) == 1:
        return selected[0]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in selected:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = selected[0]
    bpy.ops.object.join()
    return bpy.context.object


def _mesh_object(name, data, facet_ids):
    import bpy
    mesh = bpy.data.meshes.new(name + " Mesh")
    mesh.from_pydata(data["vertices"], [], data["faces"])
    mesh.update()
    attribute = mesh.attributes.new("diamond_facet", "INT", "FACE")
    for index, polygon in enumerate(mesh.polygons):
        polygon.use_smooth = False
        attribute.data[index].value = int(facet_ids[index])
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _frame_visible_scene():
    """Persist a practical viewport framing in the interactive result file."""
    import bpy
    from mathutils import Vector

    points = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.hide_get() or obj.hide_viewport:
            continue
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        return
    minimum = Vector((min(point.x for point in points),
                      min(point.y for point in points),
                      min(point.z for point in points)))
    maximum = Vector((max(point.x for point in points),
                      max(point.y for point in points),
                      max(point.z for point in points)))
    center = (minimum + maximum) * 0.5
    distance = max((maximum - minimum).length * 1.25, 1.0)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            space.region_3d.view_location = center
            space.region_3d.view_distance = distance
            space.lens = 50


def _frame_selected_viewport():
    """Use Blender's own fit operator when a GUI viewport is available."""
    import bpy
    if not _interactive() or bpy.context.window is None or bpy.context.screen is None:
        return
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
        if region is None:
            continue
        try:
            with bpy.context.temp_override(window=bpy.context.window,
                                           screen=bpy.context.screen,
                                           area=area, region=region,
                                           region_data=area.spaces.active.region_3d):
                bpy.ops.view3d.view_selected(use_all_regions=False)
        except RuntimeError:
            # The stored bounds framing remains valid for unusual Blender UI
            # layouts where the operator has no active region.
            pass


def _weld_mesh(obj, distance=0.00002, preserve_winding=False):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=distance)
    bm.verts.index_update()
    seen = set()
    duplicate_faces = []
    for face in bm.faces:
        key = tuple(sorted(vertex.index for vertex in face.verts))
        if key in seen:
            duplicate_faces.append(face)
        else:
            seen.add(key)
    if duplicate_faces:
        bmesh.ops.delete(bm, geom=duplicate_faces, context="FACES")
    if not preserve_winding:
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def _recalculate_normals(obj):
    """Orient connected faces consistently without enabling smooth shading."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    for polygon in obj.data.polygons:
        polygon.use_smooth = False
    obj.data.update()


def _finish_facets(obj):
    """PAT-REQ-069: smooth tessellation, retain logical pyramid boundaries."""
    import bmesh
    import math
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    layer = bm.faces.layers.int.get("diamond_facet")
    if layer is None:
        bm.free()
        return
    for face in bm.faces:
        face.smooth = True
    for edge in bm.edges:
        if not edge.is_manifold:
            edge.smooth = False
            continue
        a, b = edge.link_faces
        boundary = a[layer] != b[layer] and (a[layer] > 0 or b[layer] > 0)
        edge.smooth = not boundary and edge.calc_face_angle(0) < math.radians(16)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def _smooth_relief(obj):
    """Smooth a continuous height field while keeping its clipped rim crisp."""
    attribute = obj.data.attributes.get("diamond_facet")
    for index, polygon in enumerate(obj.data.polygons):
        polygon.use_smooth = not attribute or attribute.data[index].value != 0
    obj.data.update()


def _validate(obj):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    nonmanifold = sum(not edge.is_manifold for edge in bm.edges)
    remaining = set(bm.verts)
    components = 0
    while remaining:
        components += 1
        stack = [remaining.pop()]
        while stack:
            vertex = stack.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other in remaining:
                    remaining.remove(other)
                    stack.append(other)
    volume = abs(float(bm.calc_volume(signed=True)))
    dimensions = tuple(float(value) for value in obj.dimensions)
    bm.free()
    return {"nonmanifold_edges": nonmanifold, "connected_components": components,
            "volume_mm3": volume, "dimensions_mm": dimensions,
            "ready_for_export": nonmanifold == 0 and components == 1 and volume > 0.0}


def _clean_planar_union(obj):
    """Remove zero-length Boolean edges, without remeshing the relief facets."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-5)
    wires = [e for e in bm.edges if not e.link_faces]
    if wires:
        bmesh.ops.delete(bm, geom=wires, context="EDGES")
    loose = [v for v in bm.verts if not v.link_edges]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    # A tangential Boolean contact may leave a disconnected, double-sided
    # planar sheet. Remove only components proven to have zero thickness,
    # never choose components by size or discard a valid disconnected solid.
    remaining = set(bm.verts)
    removed_sheets = 0
    while remaining:
        stack = [remaining.pop()]
        component = set(stack)
        while stack:
            vertex = stack.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other in remaining:
                    remaining.remove(other)
                    component.add(other)
                    stack.append(other)
        component_faces = {f for vertex in component for f in vertex.link_faces}
        if not component_faces:
            continue
        face = max(component_faces, key=lambda f: f.calc_area())
        face.normal_update()
        anchor = face.verts[0].co
        direction = max((v.co-anchor for v in component), key=lambda d: d.length_squared)
        direction.normalize()
        is_line = all((v.co-anchor).cross(direction).length < 1e-5 for v in component)
        is_plane = face.normal.length > 0.5 and all(abs((v.co-anchor).dot(face.normal)) < 1e-5 for v in component)
        if is_line or is_plane:
            bmesh.ops.delete(bm, geom=list(component), context="VERTS")
            removed_sheets += 1
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return removed_sheets


def _surface_check(obj):
    """Conservative export gate; manifold edge counts alone miss degeneracies."""
    from mathutils.bvhtree import BVHTree
    mesh = obj.data
    mesh.calc_loop_triangles()
    triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
    tree = BVHTree.FromPolygons([v.co for v in mesh.vertices], triangles,
                               all_triangles=True, epsilon=0.0)
    intersections = sum(a < b and not set(triangles[a]).intersection(triangles[b])
                        for a, b in tree.overlap(tree))
    degenerate = sum(t.area < 1e-10 for t in mesh.loop_triangles)
    return {"intersection_candidates": intersections, "degenerate_triangles": degenerate,
            "passed": intersections == 0 and degenerate == 0}


def _link_only(obj, collection):
    """Place an output in one assembly collection, not Blender's root scene."""
    collection.objects.link(obj)
    for owner in list(obj.users_collection):
        if owner != collection:
            owner.objects.unlink(obj)


def _component_materials():
    import bpy
    relief = bpy.data.materials.get("Auzyron Graphite Blue")
    if relief is None:
        relief = bpy.data.materials.new("Auzyron Graphite Blue")
        relief.diffuse_color = (0.11, 0.24, 0.29, 1.0)
        relief.use_nodes = True
        shader = relief.node_tree.nodes.get("Principled BSDF")
        if shader is not None:
            shader.inputs["Base Color"].default_value = (0.11, 0.24, 0.29, 1.0)
            shader.inputs["Roughness"].default_value = 0.36
    body = bpy.data.materials.get("Auzyron CAD Body Gray")
    if body is None:
        body = bpy.data.materials.new("Auzyron CAD Body Gray")
        body.diffuse_color = (0.38, 0.42, 0.45, 1.0)
        body.use_nodes = True
        shader = body.node_tree.nodes.get("Principled BSDF")
        if shader is not None:
            shader.inputs["Base Color"].default_value = (0.38, 0.42, 0.45, 1.0)
            shader.inputs["Roughness"].default_value = 0.48
    return relief, body


def _build_component(component, job, geometry, collection, index):
    """Create one source body and one independently clipped relief per map."""
    label = str(component.get("body_label") or component.get("map_label") or
                component.get("map_object") or index)
    body = _import_stl(component["body_mesh"])
    _link_only(body, collection)
    _weld_mesh(body, preserve_winding=True)
    body.name = "Auzyron CAD Body — {}".format(label)
    source_copy = body.copy()
    source_copy.data = body.data.copy()
    source_copy.name = "Source CAD Body (hidden copy) — {}".format(label)
    _link_only(source_copy, collection)
    source_copy.hide_set(True)
    source_copy.hide_viewport = True
    source_copy.hide_render = True
    relief_material, body_material = _component_materials()
    body.data.materials.clear()
    body.data.materials.append(body_material)
    body_check = _validate(body)
    topology = component.get("body_topology", {})
    if topology.get("valid") and topology.get("solids") == 1:
        expected = float(topology["volume_mm3"])
        error = abs(body_check["volume_mm3"] - expected)
        body_check["cad_shells"] = int(topology["shells"])
        body_check["cad_volume_mm3"] = expected
        body_check["volume_error_mm3"] = error
        body_check["ready_for_export"] = (
            body_check["nonmanifold_edges"] == 0 and
            body_check["connected_components"] == int(topology["shells"]) and
            expected > 0 and error <= max(0.1, expected * 0.005))
    maps = component.get("maps") or [component]
    patterns = []
    for mapped in maps:
        map_label = str(mapped.get("map_label") or mapped.get("map_object") or len(patterns) + 1)
        data = geometry.build(mapped["map_payload"], job["parameters"])
        relief = _mesh_object("Auzyron Diamond Pattern — {} — {}".format(label, map_label),
                              data, data["facet_ids"])
        _link_only(relief, collection)
        _recalculate_normals(relief)
        if data.get("weld_relief"):
            _weld_mesh(relief)
        supports = mapped["map_payload"].get("boundary_support_planes", [])
        if supports and data.get("clip_support_planes", True):
            boundary = _import_geometry(Path(__file__).with_name("boundary_clip.py"))
            boundary.clip_support_planes(relief, supports, str(job.get("boundary_solver", "EXACT")))
            if data.get("cleanup_after_clip", True):
                _clean_planar_union(relief)
        if data.get("smooth_relief"):
            _smooth_relief(relief)
        elif data.get("stats", {}).get("algorithm") != "regular_sampled_facets":
            _finish_facets(relief)
        relief.data.materials.clear()
        relief.data.materials.append(relief_material)
        patterns.append({"map_object": mapped.get("map_object"), "map_label": map_label,
                         "pattern": _validate(relief), "geometry": data["stats"]})
    return {"body_label": label, "source_bodies": component.get("source_bodies", []),
            "body": body_check, "patterns": patterns}


def _build_shared_phase_scene(job):
    """Create visibly separate assembly components; they are never Boolean-fused."""
    import bpy
    if job.get("pattern_mesh"):
        raise RuntimeError("A shared-phase job cannot use one prebuilt FreeCAD pattern mesh.")
    geometry = _import_geometry(job["geometry_module"])
    assembly = bpy.data.collections.new("Auzyron Shared Pattern Assembly")
    bpy.context.scene.collection.children.link(assembly)
    reports = []
    for index, component in enumerate(job["components"], 1):
        component_collection = bpy.data.collections.new(
            "Auzyron Component {:02d}".format(index))
        assembly.children.link(component_collection)
        reports.append(_build_component(component, job, geometry, component_collection, index))
    _frame_visible_scene()
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = None
    ready = all(item["body"]["ready_for_export"] and
                all(pattern["pattern"]["ready_for_export"] for pattern in item["patterns"])
                for item in reports)
    return {"status": "success" if ready else "preview", "mode": "shared_phase_components",
            "shared_phase": job.get("shared_phase", {}), "components": reports,
            "ready_for_export": ready}


def main():
    import bpy

    job_path = _job_path()
    job = json.loads(job_path.read_text(encoding="utf-8"))
    report_path = job_path.with_name("validation.json")
    try:
        if job.get("format") != "auzyron.blender-job" or job.get("version") != 1:
            raise RuntimeError("Unsupported Blender job format.")
        # `read_factory_settings()` destroys the active window context.  That
        # is harmless in the background preflight, but makes Blender 5.1's STL
        # importer fail when this same worker is launched interactively.
        # Interactive launches already use `--factory-startup` and therefore
        # begin with an empty scene and a valid VIEW_3D context.
        if not _interactive():
            bpy.ops.wm.read_factory_settings(use_empty=True)
        _clear_factory_scene()
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.length_unit = "MILLIMETERS"
        if job.get("components"):
            report = _build_shared_phase_scene(job)
            if _interactive():
                shutil.rmtree(job_path.parent)
                return
            _write_report(report_path, report)
            return
        data = None
        if job.get("pattern_mesh"):
            # The final pattern was built and clipped by FreeCAD.  Import it
            # directly: deriving another relief from map cells changes its
            # periodic closure and boundary geometry.
            relief = _import_stl(job["pattern_mesh"])
        else:
            # Blender Diamond generates directly from the mapped CAD domain;
            # the native FreeCAD Diamond command is not a prerequisite.
            geometry = _import_geometry(job["geometry_module"])
            data = geometry.build(job["map_payload"], job["parameters"])
            pattern_label = str(job.get("pattern_label", "Diamond"))
            relief = _mesh_object("Auzyron {} Relief".format(pattern_label), data, data["facet_ids"])
            _recalculate_normals(relief)
            if data.get("weld_relief"):
                # Boundary samples arrive from adjacent carrier facets. Their
                # coordinates may differ only by CAD tessellation round-off;
                # weld them before the physical rim cut closes the shell.
                _weld_mesh(relief)
            supports = job["map_payload"].get("boundary_support_planes", [])
            if supports and data.get("clip_support_planes", True):
                boundary = _import_geometry(Path(__file__).with_name("boundary_clip.py"))
                boundary.clip_support_planes(
                    relief, supports, str(job.get("boundary_solver", "EXACT")))
                # Remove numerical slivers after the guarded cut is projected
                # back onto the CAD plane, without remeshing Diamond facets.
                if data.get("cleanup_after_clip", True):
                    _clean_planar_union(relief)
        body = _import_stl(job["body_mesh"])
        _weld_mesh(body, preserve_winding=True)
        body.name = "Source CAD Body"
        source_copy = body.copy()
        source_copy.data = body.data.copy()
        source_copy.name = "Source CAD Body (hidden copy)"
        bpy.context.collection.objects.link(source_copy)
        source_copy.hide_set(True)
        source_copy.hide_render = True
        final = body.copy()
        final.data = body.data.copy()
        final.name = "Auzyron {} Union".format(str(job.get("pattern_label", "Diamond")))
        bpy.context.collection.objects.link(final)
        bpy.data.objects.remove(body, do_unlink=True)
        # A copied mesh can retain Blender's stale bounding box.  The Boolean
        # solver uses that box for its broad-phase test; without refreshing it
        # the full CAD body can be treated as a flat strip.
        final.data.update(calc_edges=True)
        final.update_tag(refresh={"DATA"})
        bpy.context.view_layer.update()
        # Keep the CAD body and the closed relief visible as one prepared scene.
        # The live Exact Boolean is intentionally not used here: on this family
        # of imported CAD meshes it can collapse a valid relief into a strip.
        mode = "body_plus_pattern"
        final.name = "Auzyron CAD Body"
        relief.name = "Auzyron {} Pattern".format(str(job.get("pattern_label", "Diamond")))
        final.hide_set(False)
        final.hide_viewport = False
        final.hide_render = False
        source_copy.hide_viewport = True
        source_copy.hide_set(True)
        relief.hide_set(False)
        relief.hide_viewport = False
        relief.hide_render = False
        material = bpy.data.materials.new("Auzyron Graphite Blue")
        material.diffuse_color = (0.11, 0.24, 0.29, 1.0)
        material.use_nodes = True
        shader = material.node_tree.nodes.get("Principled BSDF")
        if shader is not None:
            shader.inputs["Base Color"].default_value = (0.11, 0.24, 0.29, 1.0)
            shader.inputs["Roughness"].default_value = 0.36
        relief.data.materials.clear()
        relief.data.materials.append(material)
        body_material = bpy.data.materials.new("Auzyron CAD Body Gray")
        body_material.diffuse_color = (0.38, 0.42, 0.45, 1.0)
        body_material.use_nodes = True
        body_shader = body_material.node_tree.nodes.get("Principled BSDF")
        if body_shader is not None:
            body_shader.inputs["Base Color"].default_value = (0.38, 0.42, 0.45, 1.0)
            body_shader.inputs["Roughness"].default_value = 0.48
        final.data.materials.clear()
        final.data.materials.append(body_material)
        _frame_visible_scene()
        # Open in Object Mode without selecting the CAD STL.  Its internal
        # tessellation is intentionally present for export, but showing it in
        # Edit Mode looks like a non-continuous Diamond surface even though it
        # is only the triangulation of the source body.
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = None
        body_check = _validate(final)
        topology = job.get("body_topology", {})
        if topology.get("valid") and topology.get("solids") == 1:
            # A sealed cavity adds an internal shell, not a disconnected solid.
            # CAD supplies the expected shell count and signed-material volume.
            expected_volume = float(topology["volume_mm3"])
            volume_error = abs(body_check["volume_mm3"] - expected_volume)
            body_check["cad_shells"] = int(topology["shells"])
            body_check["cad_volume_mm3"] = expected_volume
            body_check["volume_error_mm3"] = volume_error
            body_check["ready_for_export"] = (
                body_check["nonmanifold_edges"] == 0 and
                body_check["connected_components"] == int(topology["shells"]) and
                expected_volume > 0 and
                volume_error <= max(0.1, expected_volume * 0.005))
        pattern_check = _validate(relief)
        validation = {"body": body_check, "pattern": pattern_check,
                      "ready_for_export": body_check["ready_for_export"] and
                                            pattern_check["ready_for_export"]}
        if data and data.get("planar_patches"):
            source_validation = _validate(final)
            final.data.materials.append(material)
            patch_validation = []
            operands = bpy.data.collections.new("Planar union operands")
            bpy.context.scene.collection.children.link(operands)
            for index, patch in enumerate(data["planar_patches"]):
                start = patch["vertex_start"]
                subset = {"vertices": data["vertices"][start:patch["vertex_end"]],
                          "faces": [tuple(v-start for v in f) for f in
                                    data["faces"][patch["face_start"]:patch["face_end"]]]}
                obj = _mesh_object("Planar relief %d" % index, subset, [0]*len(subset["faces"]))
                obj.data.materials.append(body_material)
                obj.data.materials.append(material)
                for polygon in obj.data.polygons:
                    polygon.material_index = 1
                _recalculate_normals(obj)
                bpy.context.view_layer.update()
                check = _validate(obj)
                patch_validation.append(check)
                if not check["ready_for_export"]:
                    raise RuntimeError("A clipped planar relief patch is not closed.")
                operands.objects.link(obj)
            bpy.context.view_layer.objects.active = final
            modifier = final.modifiers.new("Planar relief union", "BOOLEAN")
            modifier.operation = "UNION"
            modifier.solver = "MANIFOLD"
            modifier.operand_type = "COLLECTION"
            modifier.collection = operands
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            for obj in list(operands.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections.remove(operands)
            removed_sheets = _clean_planar_union(final)
            bpy.context.view_layer.update()
            final.name = "Auzyron {} Final".format(str(job.get("pattern_label", "Diamond")))
            relief.select_set(False)
            relief.hide_set(True)
            relief.hide_render = True
            result = _validate(final)
            surface_check = _surface_check(final)
            retains_body = (result["volume_mm3"] >= source_validation["volume_mm3"] - 1e-4 and
                            all(a >= b-1e-4 for a, b in zip(result["dimensions_mm"], source_validation["dimensions_mm"])))
            mode = "rigid_planar_union"
            validation = {"source_body": source_validation, "patches": patch_validation,
                          "final": result, "retains_body": retains_body,
                          "surface_check": surface_check,
                          "zero_thickness_boolean_sheets_removed": removed_sheets,
                          "ready_for_export": result["ready_for_export"] and retains_body and surface_check["passed"]}
        if data and data.get("smooth_relief"):
            _smooth_relief(relief)
        elif data and data.get("stats", {}).get("algorithm") != "regular_sampled_facets":
            for obj in bpy.context.scene.objects:
                if obj.type == "MESH" and obj.data.attributes.get("diamond_facet"):
                    _finish_facets(obj)
        boolean_error = None
        if _interactive():
            # The interactive Blender process has loaded all geometry into
            # memory.  The bridge owns this package, so remove it immediately.
            shutil.rmtree(job_path.parent)
            return
        if not validation["ready_for_export"]:
            preview = validation.get("body", {}).get("ready_for_export", False)
            _write_report(report_path, {
                "status": "preview" if preview else "failed", "mode": mode,
                "error": "Mesh validation failed; STL export was blocked.",
                "warning": ("Preview only: the body is valid but the relief is "
                            "not a closed export mesh.") if preview else None,
                "geometry": data["stats"] if data else {"source": "FreeCAD final pattern"}, "validation": validation})
            return
        report = {"status": "success", "mode": mode,
                  "geometry": data["stats"] if data else {"source": "FreeCAD final pattern"},
                  "validation": validation}
        if boolean_error:
            report["boolean_warning"] = boolean_error
        _write_report(report_path, report)
    except Exception as error:
        _write_report(report_path, {"status": "failed", "error": str(error)})
        raise


if __name__ == "__main__":
    main()
