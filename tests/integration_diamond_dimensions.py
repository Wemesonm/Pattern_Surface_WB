"""Manual FreeCAD integration test for configurable Diamond dimensions."""
import pathlib
import sys

import FreeCAD as App


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from pattern_surface.compatibility import v4_pipeline as engine


class SelectionHarness:
    def __init__(self):
        self.objects = []

    def getSelection(self):
        return self.objects

    def select(self, *objects):
        self.objects = list(objects)


for open_name in list(App.listDocuments()):
    App.closeDocument(open_name)
doc = App.openDocument(str(ROOT / "tests/fixtures/container_four_faces.FCStd"))
wrap = doc.getObject("DiamondSurfaceWrap_V4_Run_001")
selection = SelectionHarness()
engine.Gui.Selection = selection
selection.select(wrap)

pattern = engine.create_full_pattern(height=1.0, diamond_height=9.0)
payload = engine.load_chunks(pattern, "DiamondPatternCellChunks")
assert abs(float(pattern.DiamondHeight) - 9.0) < 1.0e-9
assert abs(float(pattern.PatternHeight) - 1.0) < 1.0e-9
assert abs(float(payload["parameters"]["diamond_height"]) - 9.0) < 1.0e-9
assert abs(float(payload["parameters"]["pyramid_height"]) - 1.0) < 1.0e-9
assert len(pattern.Shape.Solids) > 0

print("DIAMOND_DIMENSIONS_RESULT=diamond_height=9.0 pyramid_height=1.0 solids={}".format(
    len(pattern.Shape.Solids)))
App.closeDocument(doc.Name)
