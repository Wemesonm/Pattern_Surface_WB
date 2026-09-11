"""DATA-REQ-056 / PAT-REQ-080: CAD boundaries, not carrier tessellation edges."""
import math
import unittest
import FreeCAD as App
import Part
from types import SimpleNamespace
from pattern_surface import core_engine as core
from pattern_surface.blender_bridge.native_boundary import boundary_curves


class NativeBoundaryTests(unittest.TestCase):
    def entry(self, face, shape, index=0):
        entry = {"index": index, "component": 0, "face": face,
                 "object": SimpleNamespace(Shape=shape), "sub": "Face{}".format(index+1),
                 "transform": [1, 0, 0, 1, 0, 0]}
        core.orient_entry(entry)
        return entry

    def test_complete_cylinder_excludes_periodic_seam(self):
        shape = Part.makeCylinder(10, 20)
        face = next(f for f in shape.Faces if isinstance(f.Surface, Part.Cylinder))
        curves = boundary_curves([self.entry(face, shape)])["curves"]
        self.assertEqual(2, len(curves))
        self.assertEqual({0.0, 20.0}, {round(c["points"][0][2], 6) for c in curves})
        for curve in curves:
            self.assertLess(App.Vector(*curve["points"][0]).distanceToPoint(
                App.Vector(*curve["points"][-1])), 1e-6)

    def test_selected_box_sides_exclude_four_internal_seams(self):
        box = Part.makeBox(20, 10, 20)
        faces = [f for f in box.Faces if f.BoundBox.ZLength > 19]
        curves = boundary_curves([self.entry(f, box, i) for i, f in enumerate(faces)])["curves"]
        self.assertEqual(8, len(curves))
        self.assertAlmostEqual(120, sum(App.Vector(*a).distanceToPoint(App.Vector(*b))
                              for c in curves for a, b in zip(c["points"], c["points"][1:])))
        self.assertTrue(all(abs(a[2]-b[2]) < 1e-7 for c in curves
                            for a, b in zip(c["points"], c["points"][1:])))

    def test_hole_and_sloped_curved_rim_survive_rigid_placement(self):
        shape = Part.makeCylinder(10, 20, App.Vector(), App.Vector(0, 0, 1), 90)
        cutter = Part.makeBox(60, 60, 60, App.Vector(-30, -30, 0))
        cutter.rotate(App.Vector(), App.Vector(0, 1, 0), 15)
        cutter.translate(App.Vector(0, 0, 15))
        shape = shape.cut(cutter).cut(Part.makeCylinder(2, 20, App.Vector(0, 5, 8), App.Vector(1, 0, 0)))
        face = next(f for f in shape.Faces if isinstance(f.Surface, Part.Cylinder))
        entry = self.entry(face, shape)
        original = boundary_curves([entry])["curves"]
        self.assertGreater(len(original), 4)
        rotation = App.Placement(App.Vector(32, -19, 11), App.Rotation(App.Vector(1, 2, 3), 57))
        moved = face.copy()
        moved.Placement = rotation.multiply(moved.Placement)
        result = boundary_curves([dict(entry, face=moved)])["curves"]
        self.assertEqual(len(original), len(result))
        for a, b in zip(original, result):
            self.assertEqual(len(a["points"]), len(b["points"]))
            for p, q in zip(a["points"], b["points"]):
                self.assertLess(rotation.multVec(App.Vector(*p)).distanceToPoint(App.Vector(*q)), 1e-6)
            for p, q in zip(a["inward_y"], b["inward_y"]):
                self.assertAlmostEqual(p, q, places=5)
