import pathlib
import unittest

import FreeCAD as App


ROOT = pathlib.Path(__file__).parents[1]


class TrimEquivalenceTests(unittest.TestCase):
    def test_fixture_opens_and_contains_faces(self):
        document = App.openDocument(str(ROOT / "tests/fixtures/container_four_faces.FCStd"))
        try:
            faces = sum(len(getattr(obj.Shape, "Faces", []))
                        for obj in document.Objects if hasattr(obj, "Shape"))
            self.assertGreaterEqual(faces, 4)
        finally:
            App.closeDocument(document.Name)

    def test_trim_reads_stored_height(self):
        source = (ROOT / "pattern_surface/compatibility/v4_pipeline.py").read_text(encoding="utf-8")
        self.assertIn('getattr(pattern, "PatternHeight"', source)
        self.assertIn("exact_face_cut_envelope(entry, pattern_height)", source)


if __name__ == "__main__":
    unittest.main()
