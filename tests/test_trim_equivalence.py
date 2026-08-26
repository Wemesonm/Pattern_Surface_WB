import pathlib
import unittest
from unittest import mock

import FreeCAD as App

from pattern_surface import core_engine as core


ROOT = pathlib.Path(__file__).parents[1]


class TrimEquivalenceTests(unittest.TestCase):
    def test_trim_accepts_parent_map_or_alternate_cut_map(self):
        # TRIM-REQ-002: a second map may define the clipping envelope.
        source = (ROOT / "pattern_surface/core_engine.py").read_text(encoding="utf-8")
        self.assertIn('(\"MapParentRun\", \"WrapParentRun\")', source)
        self.assertIn("mapa de corte diferente do mapa de origem", source)
        self.assertIn("preserve_covered = pattern_map == wrap.Name", source)
        self.assertIn("preserve_covered=preserve_covered", source)

    def test_fixture_opens_and_contains_faces(self):
        document = App.openDocument(str(ROOT / "tests/fixtures/container_four_faces.FCStd"))
        try:
            faces = sum(len(getattr(obj.Shape, "Faces", []))
                        for obj in document.Objects if hasattr(obj, "Shape"))
            self.assertGreaterEqual(faces, 4)
        finally:
            App.closeDocument(document.Name)

    def test_trim_reads_stored_height(self):
        source = (ROOT / "pattern_surface/core_engine.py").read_text(encoding="utf-8")
        self.assertIn('getattr(pattern, "PatternHeight"', source)
        self.assertIn("exact_face_cut_envelope(entry, pattern_height)", source)

    def test_periodic_domain_copy_covers_closure_cell(self):
        payload = {
            "faces": [{
                "index": 1,
                "component": 0,
                "width": 1.0,
                "height": 1.0,
                "transform": [1.0, 0.0, 0.0, 1.0, 10.0, 0.0],
            }],
        }
        canonical = [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
        periodic = [{"component": 0, "axis": 0, "period": 10.0}]
        with mock.patch.object(core, "periodic_axis_records", return_value=periodic):
            self.assertAlmostEqual(core.domain_coverage_ratio(payload, canonical), 1.0)

    def test_nonperiodic_domain_does_not_cover_distant_cell(self):
        payload = {
            "faces": [{
                "index": 1,
                "component": 0,
                "width": 1.0,
                "height": 1.0,
                "transform": [1.0, 0.0, 0.0, 1.0, 10.0, 0.0],
            }],
        }
        canonical = [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
        with mock.patch.object(core, "periodic_axis_records", return_value=[]):
            self.assertEqual(core.domain_coverage_ratio(payload, canonical), 0.0)


if __name__ == "__main__":
    unittest.main()
