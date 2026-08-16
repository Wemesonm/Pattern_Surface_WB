import ast
import pathlib
import unittest


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


if __name__ == "__main__":
    unittest.main()
