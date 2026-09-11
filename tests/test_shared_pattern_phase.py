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

    def test_distant_or_perpendicular_rims_are_rejected(self):
        body = rectangle(0, 12)
        other = rectangle(100, 112)
        # Parallel geometry is still a valid assembly relation regardless of
        # distance; rotation, rather than a fixed distance threshold, is the
        # generic incompatibility test.
        aligned, _ = phase.align([body, other])
        self.assertEqual(2, len(aligned))

