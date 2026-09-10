"""Run with Blender --background --factory-startup --python this_file.

DATA-REQ-053: a physical rim cut must preserve the cavity, facets and closure,
including after arbitrary rigid placement. This is not a screenshot test.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy
import bmesh
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree
from pattern_surface.blender_bridge.boundary_clip import clip_support_planes

for rotated in (False, True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rotation = Quaternion(Vector((1, 2, 3)).normalized(), 0.83) if rotated else Quaternion()
    translation = Vector((31, -12, 17)) if rotated else Vector()
    square = [(-2,-2),(2,-2),(2,2),(-2,2)]
    inner = [(-1,-1),(1,-1),(1,1),(-1,1)]
    vertices = [rotation @ Vector((x,y,z)) + translation
                for z in (-1,1) for ring in (square,inner) for x,y in ring]
    faces = []
    for i in range(4):
        j = (i+1)%4
        faces.extend([(i,j,j+8,i+8),(i+4,i+12,j+12,j+4),
                      (i+8,j+8,j+12,i+12),(i,i+4,j+4,j)])
    mesh = bpy.data.meshes.new('Tube')
    mesh.from_pydata(vertices, [], faces)
    obj = bpy.data.objects.new('Tube', mesh)
    bpy.context.collection.objects.link(obj)
    normal = rotation @ Vector((0,0,1))
    clip_support_planes(obj, [{"origin": list(translation), "normal": list(normal)}])
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    assert all(e.is_manifold for e in bm.edges)
    assert abs(abs(bm.calc_volume())-12) < 0.0002
    assert max((v.co-translation).dot(normal) for v in bm.verts) < 0.0001
    tree = BVHTree.FromBMesh(bm)
    assert tree.ray_cast(translation+normal*3, -normal)[0] is None, 'Cap filled the cavity'
    assert len([o for o in bpy.data.objects if o.type == 'MESH']) == 1
    bm.free()
print('BLENDER_BOUNDARY_REGRESSION_OK', flush=True)
