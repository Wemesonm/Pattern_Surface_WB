import ast
import math
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
        self.assertEqual("closure_fit_tolerance", function.args.args[2].arg)

    def test_dialog_contract(self):
        from pattern_surface.patterns.diamond import metadata, parameters

        self.assertEqual(1.0, metadata.DEFAULT_HEIGHT)
        self.assertEqual(0.01, metadata.MIN_HEIGHT)
        self.assertIn("LastHeight", parameters.PREFERENCE_KEY)
        self.assertEqual(12.0, metadata.DEFAULT_DIAMOND_HEIGHT)
        self.assertEqual(1.0, metadata.DEFAULT_PYRAMID_HEIGHT)
        self.assertIn("DiamondHeight", parameters.DIAMOND_HEIGHT_KEY)
        self.assertIn("PyramidHeight", parameters.PYRAMID_HEIGHT_KEY)
        self.assertEqual(0.20, metadata.DEFAULT_CLOSURE_FIT_TOLERANCE)
        self.assertIn("ClosureFitTolerance", parameters.CLOSURE_FIT_TOLERANCE_KEY)

    def test_canonical_diamond_height_is_configurable(self):
        from pattern_surface.compatibility import v4_pipeline as engine

        _cell_id, triangle = next(engine.canonical_triangles(
            [0.0, 30.0, 0.0, 30.0], extra=False, diamond_height=9.0))
        ys = [point[1] for point in triangle]
        self.assertAlmostEqual(9.0, max(ys) - min(ys), places=6)

    def test_canonical_side_can_fit_without_changing_height(self):
        from pattern_surface.compatibility import v4_pipeline as engine

        _cell_id, triangle = next(engine.canonical_triangles(
            [0.0, 30.0, 0.0, 30.0], extra=False,
            diamond_height=12.0, diamond_side=13.8))
        xs = sorted({round(point[0], 6) for point in triangle})
        ys = [point[1] for point in triangle]
        self.assertAlmostEqual(13.8, xs[-1] - xs[0], places=6)
        self.assertAlmostEqual(12.0, max(ys) - min(ys), places=6)

    def test_periodic_fit_uses_user_tolerance(self):
        from pattern_surface.compatibility import v4_pipeline as engine

        natural_side = 2.0 * 12.0 / math.sqrt(3.0)
        period = natural_side * 24.0 - 0.15
        payload = self._periodic_payload(period)
        accepted = engine.periodic_diamond_fit(payload, 12.0, 0.20)
        rejected = engine.periodic_diamond_fit(payload, 12.0, 0.10)
        self.assertTrue(accepted["compatible"])
        self.assertTrue(accepted["adjusted"])
        self.assertEqual(24, accepted["modules"])
        self.assertAlmostEqual(period / 24.0, accepted["effective_side"], places=9)
        self.assertAlmostEqual(12.0, accepted["diamond_height"], places=9)
        self.assertFalse(rejected["compatible"])
        self.assertFalse(rejected["adjusted"])

    def test_periodic_carrier_is_available_across_both_sides(self):
        from pattern_surface.compatibility import v4_pipeline as engine

        payload = self._periodic_payload(100.0)
        carriers = engine.periodic_carriers(payload, payload["triangles"])
        self.assertEqual(3, len(carriers))
        bounds = [engine.carrier_bounds(item) for item in carriers]
        self.assertTrue(any(item[1] <= 0.0 for item in bounds))
        self.assertTrue(any(item[0] >= 100.0 for item in bounds))

    @staticmethod
    def _periodic_payload(period):
        vertex = lambda x, y: {"q": [x, y], "p": [x, y, 0.0], "n": [0.0, 0.0, 1.0]}
        return {
            "faces": [
                {"index": 0, "component": 0, "width": 10.0, "height": 10.0,
                 "transform": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]},
                {"index": 1, "component": 0, "width": 10.0, "height": 10.0,
                 "transform": [1.0, 0.0, 0.0, 1.0, period - 10.0, 0.0]},
            ],
            "periodic_seams": [[0, 1]],
            "triangles": [{
                "component": 0,
                "face": 0,
                "v": [vertex(0.0, 0.0), vertex(period, 0.0), vertex(0.0, 10.0)],
            }],
        }


if __name__ == "__main__":
    unittest.main()
