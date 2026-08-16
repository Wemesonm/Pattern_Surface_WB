import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
ENGINE = ROOT / "pattern_surface/compatibility/v4_pipeline.py"


class DiamondEquivalenceTests(unittest.TestCase):
    def test_legacy_and_generic_properties_are_preserved(self):
        source = ENGINE.read_text(encoding="utf-8")
        for name in ("DiamondPatternAlgorithm", "DiamondPatternCellChunks",
                     "PatternId", "PatternMapSource", "PatternHeight"):
            self.assertIn(name, source)

    def test_pattern_registry_exposes_diamond(self):
        from pattern_surface.patterns import registry

        item = registry.get("diamond")
        self.assertEqual("PatternSurface_Pattern_Diamond", item["command_id"])


if __name__ == "__main__":
    unittest.main()
