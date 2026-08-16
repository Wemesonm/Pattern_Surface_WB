import ast
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
ENGINE = ROOT / "pattern_surface/compatibility/v4_pipeline.py"


class DiamondHeightTests(unittest.TestCase):
    def test_relief_global_was_removed(self):
        self.assertNotIn("RELIEF", ENGINE.read_text(encoding="utf-8"))

    def test_height_is_explicit_at_entry_point(self):
        tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == "create_full_pattern")
        self.assertEqual("height", function.args.args[0].arg)
        self.assertEqual("diamond_height", function.args.args[1].arg)

    def test_dialog_contract(self):
        from pattern_surface.patterns.diamond import metadata, parameters

        self.assertEqual(1.0, metadata.DEFAULT_HEIGHT)
        self.assertEqual(0.01, metadata.MIN_HEIGHT)
        self.assertIn("LastHeight", parameters.PREFERENCE_KEY)
        self.assertEqual(12.0, metadata.DEFAULT_DIAMOND_HEIGHT)
        self.assertEqual(1.0, metadata.DEFAULT_PYRAMID_HEIGHT)
        self.assertIn("DiamondHeight", parameters.DIAMOND_HEIGHT_KEY)
        self.assertIn("PyramidHeight", parameters.PYRAMID_HEIGHT_KEY)

    def test_canonical_diamond_height_is_configurable(self):
        from pattern_surface.compatibility import v4_pipeline as engine

        _cell_id, triangle = next(engine.canonical_triangles(
            [0.0, 30.0, 0.0, 30.0], extra=False, diamond_height=9.0))
        ys = [point[1] for point in triangle]
        self.assertAlmostEqual(9.0, max(ys) - min(ys), places=6)


if __name__ == "__main__":
    unittest.main()
