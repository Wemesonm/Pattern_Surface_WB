"""PAT-REQ-077/078 regressions for the Blender Diagonal Ribs pattern."""

import importlib.util
from pathlib import Path
import unittest


def _module():
    path = Path(__file__).parents[1] / "pattern_surface" / "blender_bridge" / "geometry_ribs.py"
    spec = importlib.util.spec_from_file_location("geometry_ribs_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BlenderRibsTests(unittest.TestCase):
    def test_concave_root_is_shared_and_joins_original_rib(self):
        # PAT-REQ-082: this is an envelope, not a scaled-down rib section.
        f = _module()._concave_relief
        self.assertAlmostEqual(f(1.5, 0.1, 6, 1.5), f(0.75, 0.1, 6, 1.5), places=8)
        self.assertEqual(0, f(1.5, 0, 6, 1.5))
        self.assertGreater(f(1.5, 0.6, 6, 1.5)-2*f(1.5, 0.3, 6, 1.5), 0)
        for wave in (0.0, 0.01, 0.75, 1.5):
            samples = [f(wave, i*0.01, 6, 1.5) for i in range(701)]
            self.assertGreaterEqual(min(samples), -1e-10)
            self.assertLessEqual(max(samples), wave+1e-10)
            self.assertTrue(all(b >= a-1e-10 for a, b in zip(samples, samples[1:])))
            self.assertAlmostEqual(wave, samples[600])
            self.assertAlmostEqual(wave, samples[599])

    def test_transition_sampling_limit_precedes_boundary_allocation(self):
        # PAT-REQ-080: reject impractical density before any large index allocation.
        from unittest.mock import patch
        ribs = _module()
        payload = {"bounds": [0, 100, 0, 100], "carrier_triangles": [{}]}
        with patch.object(ribs, "BoundaryDistance") as index:
            with self.assertRaisesRegex(ValueError, "sampling limit"):
                ribs.build(payload, {"base_blend": 0.001})
            index.assert_not_called()

    def test_t_junction_is_joined_before_closing_the_shell(self):
        # PAT-REQ-080: unequal subdivisions must not produce internal side walls.
        from collections import Counter
        ribs = _module()
        vertices = [(0, 0), (2, 0), (0, 2), (1, 1), (2, 2)]
        faces = [(0, 1, 2), (1, 4, 3), (3, 4, 2)]
        def add_vertex(point):
            vertices.append(point)
            return len(vertices)-1
        result, _ = ribs._stitch_surface(faces, [0, 1, 1], vertices, add_vertex, None, 1)
        incidence = Counter(tuple(sorted((a, b))) for f in result
                            for a, b in zip(f, f[1:]+f[:1]))
        self.assertNotIn((1, 2), incidence)
        self.assertEqual(2, incidence[(1, 3)])
        self.assertEqual(2, incidence[(2, 3)])
        self.assertEqual({(0, 1), (0, 2), (1, 4), (2, 4)},
                         {edge for edge, count in incidence.items() if count == 1})

    def test_native_transition_reaches_every_edge_and_preserves_interior(self):
        ribs = _module()
        def v(x, y):
            return {"q": [x, y], "p": [x, y, 0], "n": [0, 0, 1]}
        a, b, c, d = v(0, 0), v(12, 0), v(0, 12), v(12, 12)
        curves = [{"points": [a["p"], b["p"]], "inward_y": [1]},
                  {"points": [c["p"], d["p"]], "inward_y": [-1]},
                  {"points": [a["p"], c["p"]], "inward_y": [0]},
                  {"points": [b["p"], d["p"]], "inward_y": [0]}]
        payload = {"bounds": [0, 12, 0, 12], "native_boundary_curves": {"curves": curves},
                   "carrier_triangles": [{"v": [a, b, c]}, {"v": [b, d, c]}]}
        params = {"rib_pitch": 12, "resolution": 24}
        baseline = ribs.build(payload, params)
        self.assertEqual(baseline, ribs.build(payload, dict(params, base_blend=0)))
        result = ribs.build(payload, dict(params, base_blend=3, blend_all_edges=True))
        # PAT-REQ-083: Ribs owns its carrier/curve termination and must not
        # receive a second planar Boolean cut at a curved native rim.
        self.assertFalse(result["clip_support_planes"])
        self.assertEqual(0, result["stats"]["bad_edges_before_weld"])
        for before, after in zip(baseline["vertices"][:len(baseline["vertices"])//2],
                                 result["vertices"][:len(result["vertices"])//2]):
            x, y, z = after
            if min(x, y, 12-x, 12-y) < 1e-7:
                self.assertAlmostEqual(0.045, z)
            if min(x, y, 12-x, 12-y) >= 3:
                self.assertAlmostEqual(before[2], z)
        lower = ribs.build(payload, dict(params, base_blend=3))
        for before, after in zip(baseline["vertices"][:len(baseline["vertices"])//2],
                                 lower["vertices"][:len(lower["vertices"])//2]):
            if after[1] >= 3:
                self.assertAlmostEqual(before[2], after[2])
        # PAT-REQ-081: a longer finish preserves the skin instead of crossing
        # into the body, and keeps the interior wave at its original height.
        gentle = ribs.build(payload, dict(params, base_blend=6, blend_all_edges=True))
        self.assertEqual(0, gentle["stats"]["bad_edges_before_weld"])
        outer = gentle["vertices"][:len(gentle["vertices"])//2]
        self.assertGreaterEqual(min(p[2] for p in outer), 0.045-1e-9)
        by_xy = {(p[0], p[1]): p[2] for p in outer}
        standard = {(p[0], p[1]): p[2] for p in result["vertices"][:len(result["vertices"])//2]}
        self.assertLess(by_xy[(1.5, 1.5)], standard[(1.5, 1.5)])
        self.assertAlmostEqual(by_xy[(6.0, 6.0)], standard[(6.0, 6.0)])

    def test_transition_requires_native_boundary_and_uses_physical_distance(self):
        ribs = _module()
        with self.assertRaisesRegex(ValueError, "Native CAD boundaries"):
            ribs.BoundaryDistance({"external_segments": []}, 3, True)
        payload = {"native_boundary_curves": {"curves": [
            {"points": [[10, 20, 30], [10, 20, 40]], "inward_y": [1], "component": 2}]}}
        distance = ribs.BoundaryDistance(payload, 3, True)
        self.assertAlmostEqual(1, distance.distance((11, 20, 35), 2))
        self.assertAlmostEqual(3, distance.distance((11, 20, 35), 0))
        self.assertAlmostEqual(0, distance.distance((10, 20, 35), 2))

    def test_rectangular_domain_is_closed_and_has_variable_relief(self):
        ribs = _module()

        def vertex(x, y):
            return {"q": [x, y], "p": [x, y, 0], "n": [0, 0, 1]}
        a, b, c, d = vertex(0, 0), vertex(36, 0), vertex(0, 24), vertex(36, 24)
        result = ribs.build({"bounds": [0, 36, 0, 24],
                             "carrier_triangles": [{"v": [a, b, c]}, {"v": [b, d, c]}]},
                            {"rib_pitch": 12, "rib_height": 1.5,
                             "rib_angle": 45, "resolution": 6})
        self.assertEqual(0, result["stats"]["bad_edges_before_weld"])
        self.assertEqual("diagonal_ribs_heightfield", result["stats"]["algorithm"])
        outer = result["vertices"][:len(result["vertices"]) // 2]
        self.assertGreater(max(point[2] for point in outer) - min(point[2] for point in outer), 1.0)

    def test_periodic_rib_phase_is_fitted_for_the_final_weld(self):
        ribs = _module()
        import math
        carrier = []
        for index in range(40):
            def vertex(i, y):
                angle = 2 * math.pi * i / 40
                return {"q": [100 * i / 40, y],
                        "p": [10 * math.cos(angle), 10 * math.sin(angle), y],
                        "n": [math.cos(angle), math.sin(angle), 0]}
            a, b, c, d = vertex(index, 0), vertex(index + 1, 0), vertex(index, 20), vertex(index + 1, 20)
            carrier.extend(({"v": [a, b, c]}, {"v": [b, d, c]}))
        result = ribs.build({"bounds": [0, 100, 0, 20], "carrier_triangles": carrier,
                             "periodic_adjustments": [{"axis": 0, "period": 100, "lower": 0}]},
                            {"rib_pitch": 13, "rib_height": 1, "rib_angle": 45, "resolution": 6})
        # A periodic CAD carrier may contain independent tessellation fragments
        # on its seam.  The Blender worker welds those coincident fragments
        # before its manifold validation; the generator must explicitly opt in
        # to that final, geometry-preserving weld rather than relying on a
        # visually matching but open seam.
        self.assertTrue(result["weld_relief"])
        self.assertEqual("diagonal_ribs_heightfield", result["stats"]["algorithm"])

    def test_blender_patterns_are_a_single_command_group(self):
        source = (Path(__file__).parents[1] / "pattern_surface" / "commands" /
                  "pattern_tools.py").read_text(encoding="utf-8")
        self.assertIn('return ("PatternSurface_Blender_Diamond", BLENDER_RIBS_COMMAND_ID)', source)
        commands = (Path(__file__).parents[1] / "pattern_surface" / "commands" /
                    "__init__.py").read_text(encoding="utf-8")
        self.assertIn('BLENDER_COMMANDS = [BLENDER_GROUP_COMMAND_ID]', commands)

    def test_ribs_use_its_own_generator_and_preserve_the_diamond_default(self):
        command = (Path(__file__).parents[1] / "pattern_surface" / "commands" /
                   "blender_ribs.py").read_text(encoding="utf-8")
        self.assertIn("geometry_ribs.py", command)
        # PAT-REQ-080 / DATA-REQ-053: a curved/filleted native rim must use
        # Exact clipping.  Manifold can leave an apparently closed saw-tooth
        # cap at a native boundary.
        self.assertIn('boundary_solver="EXACT"', command)
        job = (Path(__file__).parents[1] / "pattern_surface" / "blender_bridge" /
               "job.py").read_text(encoding="utf-8")
        self.assertIn('boundary_solver="EXACT"', job)

    def test_ribs_do_not_depend_on_diamond_geometry(self):
        # PAT-REQ-011: a pattern uses Map Faces plus neutral bridge helpers,
        # never another pattern implementation.
        ribs = (Path(__file__).parents[1] / "pattern_surface" / "blender_bridge" /
                "geometry_ribs.py").read_text(encoding="utf-8")
        self.assertIn('geometry_common.py', ribs)
        self.assertNotIn('geometry_closed.py', ribs)

    def test_blender_worker_removes_factory_scene_objects(self):
        source = (Path(__file__).parents[1] / "pattern_surface" / "blender_bridge" /
                  "worker.py").read_text(encoding="utf-8")
        self.assertIn("def _clear_factory_scene()", source)
        self.assertIn("_clear_factory_scene()", source)
