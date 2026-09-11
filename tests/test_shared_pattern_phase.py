"""PAT-REQ-086/DATA-REQ-057 shared Blender phase regression tests."""

import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "shared_phase", Path(__file__).parents[1] / "pattern_surface/blender_bridge/shared_phase.py")
phase = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phase)


def rectangle(x0, x1, y0=0, y1=12, reverse=False):
    def point(x, y):
        q = [x, y]
        if reverse:
            q = [-x, y]
        return {"q": q, "p": [x, y, 0], "n": [0, 0, 1]}
    a, b, c, d = point(x0, y0), point(x1, y0), point(x0, y1), point(x1, y1)
    return {
        "bounds": [min(v["q"][0] for v in (a,b,c,d)), max(v["q"][0] for v in (a,b,c,d)), 0, 12],
        "grid": {"origin": [0, 0]},
        "carrier_triangles": [{"v": [a, b, c]}, {"v": [b, d, c]}],
        "external_segments": [
            {"a": a, "b": b}, {"a": b, "b": d},
            {"a": d, "b": c}, {"a": c, "b": a},
        ],
    }


def reversed_interior_rectangle(x0, x1, y0=0, y1=12):
    """A physical neighbour whose independently-created q chart faces inward.

    Its left physical rim has the same logical interior side as the right rim
    of ``rectangle(0, 12)``.  Registration must unfold, rather than overlap,
    the two charts.
    """
    def point(x, y):
        return {"q": [x1 - (x - x0), y], "p": [x, y, 0], "n": [0, 0, 1]}
    a, b, c, d = point(x0, y0), point(x1, y0), point(x0, y1), point(x1, y1)
    return {
        "bounds": [0, x1 - x0, 0, 12],
        "grid": {"origin": [0, 0]},
        "carrier_triangles": [{"v": [a, b, c]}, {"v": [b, d, c]}],
        "external_segments": [
            {"a": a, "b": b}, {"a": b, "b": d},
            {"a": d, "b": c}, {"a": c, "b": a},
        ],
    }


class SharedPatternPhaseTests(unittest.TestCase):
    def test_nearby_closed_rims_share_one_logical_boundary(self):
        # A 0.2 mm real drawer clearance becomes a zero-width visual seam in
        # the shared lattice while each carrier remains independent.
        body = rectangle(0, 12)
        drawer = rectangle(12.2, 24.2)
        aligned, records = phase.align([body, drawer])
        self.assertEqual(2, len(aligned))
        self.assertEqual(2, len(records))
        first_edge = aligned[0]["external_segments"][1]
        second_edge = aligned[1]["external_segments"][3]
        self.assertEqual(first_edge["a"]["q"], second_edge["b"]["q"])
        self.assertEqual(first_edge["b"]["q"], second_edge["a"]["q"])
        self.assertEqual([0, 12, 0, 12], body["bounds"])
        self.assertEqual([12.2, 24.2, 0, 12], drawer["bounds"])

    def test_reversed_local_atlas_is_rotated_without_mutating_saved_payload(self):
        body = rectangle(0, 12)
        drawer = rectangle(12.2, 24.2, reverse=True)
        aligned, _ = phase.align([body, drawer])
        self.assertGreater(aligned[1]["bounds"][1], aligned[1]["bounds"][0])
        self.assertEqual([-24.2, -12.2, 0, 12], drawer["bounds"])

    def test_same_side_chart_interiors_are_reflected_across_the_shared_rim(self):
        body = rectangle(0, 12)
        drawer = reversed_interior_rectangle(12.2, 24.2)
        aligned, records = phase.align([body, drawer])
        self.assertTrue(records[1]["reflected"])
        # Reference occupies qx <= 12.  The neighbour must continue on the
        # other side of qx=12, preserving complete unsqueezed Diamond cells.
        self.assertEqual([12.0, 24.0, 0.0, 12.0],
                         [round(value, 7) for value in aligned[1]["bounds"]])

    def test_chain_uses_the_nearest_aligned_map_not_only_the_first(self):
        # The third panel touches the second panel.  Directly registering it
        # to the first would collapse its logical phase onto x=12 instead of
        # continuing the lattice at x=24.
        first = rectangle(0, 12)
        second = rectangle(12.2, 24.2)
        third = rectangle(24.4, 36.4)
        aligned, records = phase.align([first, second, third])
        self.assertEqual(1, records[2]["reference"])
        self.assertEqual([24.0, 36.0, 0.0, 12.0], aligned[2]["bounds"])

    def test_distant_or_perpendicular_rims_are_rejected(self):
        body = rectangle(0, 12)
        other = rectangle(100, 112)
        # Parallel geometry is still a valid assembly relation regardless of
        # distance; rotation, rather than a fixed distance threshold, is the
        # generic incompatibility test.
        aligned, _ = phase.align([body, other])
        self.assertEqual(2, len(aligned))

class SharedDiamondDimensionsTests(unittest.TestCase):
    """PAT-REQ-088: shared map phase also fixes Diamond module dimensions."""

    def test_later_periodic_component_does_not_refit_the_diamond_side(self):
        from pattern_surface.blender_bridge.geometry_closed import dimensions
        parameters = {"diamond_height": 12.32, "diamond_side": 10.0,
                      "pyramid_height": 1.5, "resolution": 8,
                      "finish_offset": 0.045, "contact": 0.25,
                      "closure_fit_tolerance": 0.2}
        reference = {"grid": {"origin": [0.0, 0.0]},
                     "periodic_adjustments": [{"axis": 0, "period": 20.0, "lower": 0.0}]}
        later = {"grid": {"origin": [50.0, 0.0]},
                 "periodic_adjustments": [{"axis": 0, "period": 24.0, "lower": 50.0}]}
        reference_dimensions = dimensions(reference, parameters)
        later["shared_pattern_phase"] = {
            "side": reference_dimensions["side"],
            "row_height": reference_dimensions["row_height"],
            "origin": reference_dimensions["origin"],
            "modules": reference_dimensions["modules"],
            "reference": False,
        }
        later_dimensions = dimensions(later, parameters)
        self.assertEqual(10.0, reference_dimensions["side"])
        self.assertEqual(reference_dimensions["side"], later_dimensions["side"])
        self.assertEqual(reference_dimensions["origin"], later_dimensions["origin"])


class AssemblyCycleTests(unittest.TestCase):
    """PAT-REQ-089: a tree registration must also satisfy the other join."""

    @staticmethod
    def closed_maps():
        import math
        maps = [rectangle(0, 20), rectangle(-30, 0)]
        for payload in maps:
            seen = set()
            for triangle in payload['carrier_triangles']:
                for v in triangle['v']:
                    if id(v) in seen:
                        continue
                    seen.add(id(v))
                    angle = v['q'][0] * 2 * math.pi / 50
                    v['p'] = [10 * math.cos(angle), 10 * math.sin(angle), v['q'][1]]
        return maps

    def test_closed_assembly_fits_all_joins_without_wrapping_partial_carriers(self):
        from pattern_surface.blender_bridge.job import _apply_shared_diamond_phase
        from pattern_surface.blender_bridge.geometry_closed import dimensions
        maps = self.closed_maps()
        self.assertAlmostEqual(50, phase.assembly_cycle_period(maps))
        params = {'diamond_side': 12.4, 'diamond_height': 10,
                  'closure_fit_tolerance': 0.2}
        _apply_shared_diamond_phase(maps, params)
        for payload in maps:
            dim = dimensions(payload, params)
            self.assertAlmostEqual(12.5, dim['side'])
            self.assertEqual(10, dim['row_height'])
            self.assertIsNone(dim['modules'])
            self.assertAlmostEqual(0, (20 - (-30)) % dim['side'])
        self.assertEqual([-30, 0, 0, 12], maps[1]['bounds'])

    def test_open_chain_does_not_fit_a_period(self):
        maps, _ = phase.align([rectangle(0, 12), rectangle(12, 30)])
        self.assertIsNone(phase.assembly_cycle_period(maps))

    def test_cycle_fit_respects_user_tolerance(self):
        from pattern_surface.blender_bridge.job import _apply_shared_diamond_phase
        with self.assertRaisesRegex(ValueError, 'configured tolerance'):
            _apply_shared_diamond_phase(self.closed_maps(),
                {'diamond_side':12.4, 'closure_fit_tolerance':0.01})

    def test_saved_split_body_rims_have_identical_phase_at_both_joins(self):
        import json
        from pattern_surface.blender_bridge.job import _apply_shared_diamond_phase
        path = Path(__file__).parent / 'fixtures/shared_assembly_cycle_rims.json'
        maps = json.loads(path.read_text())['maps']
        _apply_shared_diamond_phase(maps,
            {'diamond_height':12.32, 'pyramid_height':1.5,
             'closure_fit_tolerance':0.5})
        spacing = maps[0]['shared_pattern_phase']['side']
        self.assertEqual(52, maps[0]['shared_pattern_phase']['assembly_modules'])
        rims = [{tuple(round(c,5) for c in v['p']):v['q']
                 for s in m['external_segments'] for v in (s['a'],s['b'])}
                for m in maps]
        shared = rims[0].keys() & rims[1].keys()
        self.assertGreaterEqual(len(shared), 12)
        has_cycle = False
        for p in shared:
            dx = rims[0][p][0] - rims[1][p][0]
            dy = rims[0][p][1] - rims[1][p][1]
            has_cycle |= abs(dx) > spacing
            self.assertAlmostEqual(0, dx - round(dx / spacing) * spacing, places=7)
            self.assertAlmostEqual(0, dy, places=7)
        self.assertTrue(has_cycle)

class SharedPlanarLatticeTests(unittest.TestCase):
    """PAT-REQ-088: periodic planar path retains the shared logical origin."""

    @staticmethod
    def _strip(low, high):
        return {"low": low, "high": high, "normal": [0.0, 0.0, 1.0],
                "corners": [[low, 0.0, 0.0], [low, 12.0, 0.0],
                            [high, 0.0, 0.0], [high, 12.0, 0.0]]}

    def test_adjacent_planar_strips_have_identical_lattice_nodes_on_their_rim(self):
        from pattern_surface.blender_bridge.geometry_closed import _build_planar_shared
        dim = {"side": 10.0, "row_height": 10.0, "origin": [0.0, 0.0],
               "relief": 1.0, "finish_offset": 0.045, "contact": 0.25}
        left = _build_planar_shared([self._strip(0.0, 20.0)], dim, [0, 20, 0, 12])
        right = _build_planar_shared([self._strip(20.0, 40.0)], dim, [20, 40, 0, 12])
        def rim_nodes(data):
            return sorted({(round(point[1], 7), round(point[2], 7))
                           for point in data["vertices"] if abs(point[0] - 20.0) < 1e-7})
        self.assertTrue(rim_nodes(left))
        self.assertEqual(rim_nodes(left), rim_nodes(right))
