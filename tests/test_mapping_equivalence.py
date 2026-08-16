import ast
import pathlib
import unittest

import FreeCAD as App


ROOT = pathlib.Path(__file__).parents[1]
ORIGINAL = ROOT / "archive/v4_original/Wrap_pipeline_V4_core.py"
ENGINE = ROOT / "pattern_surface/compatibility/v4_pipeline.py"


def functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


class MappingEquivalenceTests(unittest.TestCase):
    def test_no_original_function_was_discarded(self):
        self.assertEqual(set(), functions(ORIGINAL) - functions(ENGINE))

    def test_map_has_generic_and_legacy_metadata(self):
        source = ENGINE.read_text(encoding="utf-8")
        for property_name in ("WrapCarrierChunks", "MapPayloadChunks", "MapAlgorithm"):
            self.assertIn(property_name, source)

    def test_periodic_seam_parameters_stay_in_trimmed_intervals(self):
        from pattern_surface.compatibility import v4_pipeline as engine

        document = App.openDocument(str(ROOT / "tests/fixtures/container_four_faces.FCStd"))
        try:
            source = document.getObject("Thickness001")
            for face_name in ("Face14", "Face4"):
                face = source.getSubObject(face_name)
                u0, u1, _, _ = face.ParameterRange
                for edge in face.OuterWire.OrderedEdges:
                    for point in edge.discretize(Number=17):
                        u, _ = engine.surface_parameters(face, point)
                        self.assertGreaterEqual(u, u0 - 1.0e-9)
                        self.assertLessEqual(u, u1 + 1.0e-9)
        finally:
            App.closeDocument(document.Name)


if __name__ == "__main__":
    unittest.main()
