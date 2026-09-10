"""MAP-REQ-063 / DATA-REQ-053: native curved boundaries, including rotation."""
import unittest
import FreeCAD as App
import Part
from pattern_surface import core_engine as core
from pattern_surface.mapping.trimmed_carrier import trimmed_curved_carrier
from pattern_surface.blender_bridge.reference import support_planes


class TrimmedCarrierTests(unittest.TestCase):
    def setUp(self):
        self.doc = App.newDocument("NativeTrimTest")

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def entry(self, shape):
        obj = self.doc.addObject("Part::Feature", "Source")
        obj.Shape = shape
        index, face = next((i, f) for i, f in enumerate(shape.Faces)
                           if isinstance(f.Surface, Part.Cylinder))
        entry = {"index": 0, "component": 0, "object_ref": obj, "object": obj,
                 "sub": "Face{}".format(index+1), "face": face,
                 "transform": [1, 0, 0, 1, 0, 0]}
        core.orient_entry(entry)
        return entry

    def test_rectangular_cylinder_retains_approved_sampler(self):
        entry = self.entry(Part.makeCylinder(10, 20, App.Vector(), App.Vector(0,0,1), 90))
        self.assertIsNone(trimmed_curved_carrier(entry))

    def test_inclined_native_boundary_and_rotated_copy(self):
        for rotated in (False, True):
            shape = Part.makeCylinder(10, 20, App.Vector(), App.Vector(0,0,1), 90)
            tool = Part.makeBox(60, 60, 60, App.Vector(-30,-30,0))
            tool.rotate(App.Vector(), App.Vector(0,1,0), 15)
            tool.translate(App.Vector(0,0,15))
            shape = shape.cut(tool)
            if rotated:
                shape.rotate(App.Vector(), App.Vector(1,2,3), 57)
                shape.translate(App.Vector(32,-19,11))
            entry = self.entry(shape)
            triangles = trimmed_curved_carrier(entry)
            self.assertTrue(triangles)
            planes = support_planes([entry])
            self.assertTrue(planes)
            for triangle in triangles:
                for vertex in triangle["v"]:
                    p = App.Vector(*vertex["p"])
                    for plane in planes:
                        self.assertLessEqual((p-App.Vector(*plane["origin"])).dot(
                            App.Vector(*plane["normal"])), 0.01)

    def test_curved_domain_retains_a_native_hole(self):
        shape = Part.makeCylinder(10, 20, App.Vector(), App.Vector(0,0,1), 90)
        hole = Part.makeCylinder(2, 20, App.Vector(0,5,10), App.Vector(1,0,0))
        entry = self.entry(shape.cut(hole))
        triangles = trimmed_curved_carrier(entry)
        self.assertTrue(triangles)
        face = entry["face"]
        for ix in range(1, 20):
            for iy in range(1, 20):
                q = [entry["width"]*ix/20, entry["height"]*iy/20]
                p = core.point_from_logical(entry, q)[0]
                # Boundary samples are approximate within the native mesh sag.
                if min(Part.Vertex(p).distToShape(edge)[0] for edge in face.Edges) < 0.03:
                    continue
                inside = Part.Vertex(p).distToShape(face)[0] < 1e-6
                covered = any(core.point_in_triangle(q, [v["q"] for v in t["v"]])
                              for t in triangles)
                self.assertEqual(inside, covered)
