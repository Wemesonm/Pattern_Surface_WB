"""DATA-REQ-056 / PAT-REQ-080: CAD boundaries, not carrier tessellation edges."""
import math
import unittest
from unittest.mock import patch
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
        # DATA-REQ-056 / PAT-REQ-084: a native opening is a separate closed
        # contour, never a collection of accidental vertical exterior edges.
        self.assertIn("inner", {curve["loop_role"] for curve in original})
        self.assertIn("outer", {curve["loop_role"] for curve in original})
        rotation = App.Placement(App.Vector(32, -19, 11), App.Rotation(App.Vector(1, 2, 3), 57))
        moved = face.copy()
        moved.Placement = rotation.multiply(moved.Placement)
        result = boundary_curves([dict(entry, face=moved)])["curves"]
        self.assertEqual(len(original), len(result))
        for a, b in zip(original, result):
            self.assertEqual(a["loop_role"], b["loop_role"])
            self.assertEqual(len(a["points"]), len(b["points"]))
            for p, q in zip(a["points"], b["points"]):
                self.assertLess(rotation.multVec(App.Vector(*p)).distanceToPoint(App.Vector(*q)), 1e-6)
            for p, q in zip(a["inward_y"], b["inward_y"]):
                self.assertAlmostEqual(p, q, places=5)

    def test_data_req_058_partition_recreates_newly_exposed_rim(self):
        from pattern_surface.blender_bridge.reference import prepare_reference
        box = Part.makeBox(20, 10, 20)
        faces = [f for f in box.Faces if f.BoundBox.ZLength > 19]
        entries = [self.entry(f, box, i) for i, f in enumerate(faces)]
        # Combined map has no vertical exterior seams. A per-body partition
        # must recover them from CAD, including when fillets are disabled.
        combined = boundary_curves(entries)["curves"]
        stale = [{"face": c["face"], "component": 0,
                  "a": {"p": a, "q": qa}, "b": {"p": b, "q": qb}}
                 for c in combined if c["face"] == 0
                 for a, b, qa, qb in zip(c["points"], c["points"][1:],
                                        c["logical_points"], c["logical_points"][1:])]
        payload = {"external_segments": stale, "carrier_triangles": []}
        with patch.object(core, "hydrate_entries", return_value=[entries[0]]), \
             patch("pattern_surface.blender_bridge.reference.support_planes", return_value=[]):
            result = prepare_reference(None, payload, rebuild_boundary=True)
        length = lambda rows: sum(App.Vector(*s["a"]["p"]).distanceToPoint(
            App.Vector(*s["b"]["p"])) for s in rows)
        self.assertAlmostEqual(length(stale) + 40, length(result["external_segments"]))
        self.assertEqual(stale, payload["external_segments"])
