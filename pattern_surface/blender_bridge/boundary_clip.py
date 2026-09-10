"""Clip displaced relief against CAD support planes, preserving its facets."""


def clip_support_planes(obj, planes, solver="EXACT"):
    import bpy
    from mathutils import Vector

    for plane in planes:
        normal = Vector(plane["normal"]).normalized()
        origin = Vector(plane["origin"])
        reference_origin = origin.copy()
        points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
        if not points or max((p-origin).dot(normal) for p in points) <= 1e-5:
            continue
        # DATA-REQ-054: avoid tangential Boolean contacts, then restore the
        # exact CAD plane below. This numerical guard does not enlarge relief.
        guard = 0.0002
        origin += normal * guard
        center = sum(points, Vector()) / len(points)
        radius = max((p-center).length for p in points) * 3 + 1
        center -= normal * (center-origin).dot(normal)
        rotation = Vector((0, 0, 1)).rotation_difference(normal)
        verts = [center + rotation @ Vector((x*radius, y*radius, z*radius))
                 for x, y, z in ((-1,-1,-2),(1,-1,-2),(1,1,-2),(-1,1,-2),
                                 (-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0))]
        mesh = bpy.data.meshes.new("_AuzyronBoundaryHalfSpace")
        mesh.from_pydata(verts, [], [(0,3,2,1),(4,5,6,7),(0,1,5,4),
                                    (1,2,6,5),(2,3,7,6),(3,0,4,7)])
        mesh.update()
        cutter = bpy.data.objects.new(mesh.name, mesh)
        bpy.context.collection.objects.link(cutter)
        modifier = None
        try:
            bpy.context.view_layer.update()
            modifier = obj.modifiers.new("Native boundary cut", "BOOLEAN")
            modifier.operation = "INTERSECT"
            modifier.solver = solver
            modifier.object = cutter
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            modifier = None
            if not obj.data.vertices:
                raise RuntimeError("Native boundary clipping removed the entire relief.")
            error = max((obj.matrix_world @ v.co-origin).dot(normal)
                        for v in obj.data.vertices)
            if error > 0.001:
                raise RuntimeError(
                    "Native boundary clipping exceeded 0.001 mm ({:.6f} mm).".format(error))
            inverse = obj.matrix_world.inverted()
            for vertex in obj.data.vertices:
                point = obj.matrix_world @ vertex.co
                distance = (point-reference_origin).dot(normal)
                if distance > 0:
                    vertex.co = inverse @ (point-normal*distance)
            obj.data.update()
            if max((obj.matrix_world @ v.co-reference_origin).dot(normal)
                   for v in obj.data.vertices) > 0.001:
                raise RuntimeError("Native boundary projection exceeded 0.001 mm.")
        finally:
            if modifier is not None:
                obj.modifiers.remove(modifier)
            bpy.data.objects.remove(cutter, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
