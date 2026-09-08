import ast
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
ENGINE = ROOT / "pattern_surface/core_engine.py"
PROTOTYPE_ENGINE = ROOT / "pattern_surface/prototype_engine.py"


class DiamondEquivalenceTests(unittest.TestCase):
    def test_legacy_and_generic_properties_are_preserved(self):
        source = ENGINE.read_text(encoding="utf-8")
        for name in ("DiamondPatternAlgorithm", "DiamondPatternCellChunks",
                     "PatternId", "PatternMapSource", "PatternHeight",
                     "DiamondHeight"):
            self.assertIn(name, source)

    def test_curved_relief_is_scoped_to_curved_cells(self):
        source = PROTOTYPE_ENGINE.read_text(encoding="utf-8")
        self.assertIn("def curved_cell_relief_factor", source)
        self.assertIn("cell_height = height * relief_factor", source)
        self.assertIn("canonical, context, cell_height, apex_override", source)
        self.assertIn('"curved_relief_factor": curved_relief_factor', source)

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
        prototype = registry.get("diamond_prototype")
        self.assertEqual("PatternSurface_Pattern_DiamondPrototype", prototype["command_id"])
        prototype_v2 = registry.get("diamond_prototype_v2")
        self.assertEqual("PatternSurface_Pattern_DiamondPrototypeV2", prototype_v2["command_id"])

    def test_prototype_v2_isolated_from_geometry_engines(self):
        source = (ROOT / "pattern_surface/patterns/diamond/v2_engine.py").read_text(encoding="utf-8")
        self.assertIn('ALGORITHM = "AUZYRON_DIAMOND_PROTOTYPE_V2_DIRECT_CAD_BVH_NORMAL"', source)
        self.assertIn("def _project", source)
        self.assertIn("def _barycentric", source)
        imports = [node for node in ast.walk(ast.parse(source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        imported = " ".join(ast.unparse(node) for node in imports)
        self.assertNotIn("prototype_engine", imported)
        self.assertNotIn("core_engine", imported)
        self.assertNotIn("pattern_surface.mapping", imported)
        self.assertNotIn("pattern_surface.trimming", imported)

    def test_curved_cell_has_closed_final_fallback(self):
        # PAT-REQ-033: eligible curved cells get a final geometry fallback.
        source = PROTOTYPE_ENGINE.read_text(encoding="utf-8")
        self.assertIn("def curved_corner_pyramid_solid", source)
        self.assertIn("if solid is None and is_curved", source)

    def test_full_pattern_overscans_real_boundaries(self):
        # PAT-REQ-034: boundary overscan may complete real border cells only.
        source = PROTOTYPE_ENGINE.read_text(encoding="utf-8")
        self.assertIn("def extended_triangles(payload, distance=None)", source)
        self.assertIn("real_carriers = periodic_carriers", source)
        self.assertIn("if not real_fragments", source)


if __name__ == "__main__":
    unittest.main()
