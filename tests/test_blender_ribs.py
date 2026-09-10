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
        self.assertIn('boundary_solver="MANIFOLD"', command)
        job = (Path(__file__).parents[1] / "pattern_surface" / "blender_bridge" /
               "job.py").read_text(encoding="utf-8")
        self.assertIn('boundary_solver="EXACT"', job)

    def test_blender_worker_removes_factory_scene_objects(self):
        source = (Path(__file__).parents[1] / "pattern_surface" / "blender_bridge" /
                  "worker.py").read_text(encoding="utf-8")
        self.assertIn("def _clear_factory_scene()", source)
        self.assertIn("_clear_factory_scene()", source)
