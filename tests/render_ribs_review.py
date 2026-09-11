"""PAT-REQ-080 manual review: Blender --background --python this.py -- job.json prefix.

Runs the production worker then writes review PNGs only, never a blend/STL.
The render camera exists only in this background review process.
"""
import importlib.util
import sys
from pathlib import Path
import bpy
from mathutils import Vector

job_path, prefix = sys.argv[sys.argv.index("--")+1:]
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("review_worker", root / "pattern_surface/blender_bridge/worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
sys.argv = ["blender", "--", job_path]
worker.main()
scene = bpy.context.scene
points = [obj.matrix_world @ Vector(p) for obj in scene.objects
          if obj.type == "MESH" and not obj.hide_get() and not obj.hide_viewport
          for p in obj.bound_box]
lo = Vector(tuple(min(p[k] for p in points) for k in range(3)))
hi = Vector(tuple(max(p[k] for p in points) for k in range(3)))
center = (lo+hi)/2
camera = bpy.data.objects.new("Review camera", bpy.data.cameras.new("Review camera"))
scene.collection.objects.link(camera)
scene.camera = camera
camera.data.type = "ORTHO"
camera.data.ortho_scale = max(hi-lo)*1.52
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = "BOTH"
scene.display.shading.background_type = "WORLD"
if scene.world is None:
    scene.world = bpy.data.worlds.new("Review background")
scene.world.color = (0.08, 0.08, 0.08)
scene.render.resolution_x = 1400
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
for label, direction in (("front", (290, -430, 160)), ("back", (-320, 420, 130)),
                         ("left", (-400, -200, 100)), ("right", (400, 200, 100))):
    camera.location = center+Vector(direction)
    camera.rotation_euler = (center-camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(prefix)+"-"+label+".png"
    bpy.ops.render.render(write_still=True)
