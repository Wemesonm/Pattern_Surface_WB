import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
ENGINE = ROOT / "pattern_surface/core_engine.py"


class DiamondEquivalenceTests(unittest.TestCase):
    def test_legacy_and_generic_properties_are_preserved(self):
        source = ENGINE.read_text(encoding="utf-8")
        for name in ("DiamondPatternAlgorithm", "DiamondPatternCellChunks",
                     "PatternId", "PatternMapSource", "PatternHeight",
                     "DiamondHeight"):
            self.assertIn(name, source)

    def test_active_schema_and_object_prefixes_are_neutral(self):
        # DATA-REQ-005: new objects do not carry the retired V4 identity.
        from pattern_surface.common import identifiers

        self.assertEqual("AUZYRON_MAP_V1", identifiers.SCHEMA)
        self.assertEqual("MappedSurface", identifiers.WRAP_PREFIX)
        self.assertEqual("DiamondPattern", identifiers.FULL_PREFIX)
        self.assertEqual("TrimmedPattern", identifiers.CUT_PREFIX)
        self.assertIn("WRAP_CARRIER_V4", identifiers.LEGACY_SCHEMAS)

    def test_pattern_registry_exposes_diamond(self):
        from pattern_surface.patterns import registry

        item = registry.get("diamond")
        self.assertEqual("PatternSurface_Pattern_Diamond", item["command_id"])


if __name__ == "__main__":
    unittest.main()
