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

    def test_dialog_contract(self):
        from pattern_surface.patterns.diamond import metadata, parameters

        self.assertEqual(1.0, metadata.DEFAULT_HEIGHT)
        self.assertEqual(0.01, metadata.MIN_HEIGHT)
        self.assertIn("LastHeight", parameters.PREFERENCE_KEY)


if __name__ == "__main__":
    unittest.main()
