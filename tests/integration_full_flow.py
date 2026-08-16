"""Manual FreeCAD integration test for the versioned four-face fixture."""
import json
import pathlib
import sys
from types import SimpleNamespace

import FreeCAD as App
import FreeCADGui as Gui


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from pattern_surface.compatibility import v4_pipeline as engine


FIXTURE = ROOT / "tests/fixtures/container_four_faces.FCStd"
OUTPUT = ROOT / "tests/output/integration_full_flow.FCStd"
FACE_NAMES = ("Face14", "Face4", "Face8", "Face9")


class SelectionHarness:
    def __init__(self):
        self.objects = []
        self.extended = []

    def clearSelection(self):
        self.objects = []
        self.extended = []

    def select_faces(self, obj, names):
        self.clearSelection()
        self.objects = [obj]
        self.extended = [SimpleNamespace(
            Object=obj,
            SubElementNames=list(names),
            SubObjects=[obj.getSubObject(name) for name in names],
            PickedPoints=[],
        )]

    def select_objects(self, objects):
        self.clearSelection()
        self.objects = list(objects)

    def getSelection(self):
        return self.objects

    def getSelectionEx(self):
        return self.extended

    def addSelection(self, obj, *args):
        del args
        if hasattr(obj, "Name"):
            self.objects.append(obj)


selection = SelectionHarness()
engine.Gui.Selection = selection


def select_faces(doc, obj):
    del doc
    selection.select_faces(obj, FACE_NAMES)


def select_objects(*objects):
    selection.select_objects(objects)


def assert_equal(left, right, label):
    if left != right:
        raise AssertionError("{}: {!r} != {!r}".format(label, left, right))


for open_name in list(App.listDocuments()):
    App.closeDocument(open_name)
doc = App.openDocument(str(FIXTURE))
source = doc.getObject("Thickness001")
baseline = doc.getObject("DiamondSurfaceWrap_V4_Run_001")
baseline_payload = engine.load_chunks(baseline, "WrapCarrierChunks")

select_faces(doc, source)
mapped = engine.create_wrap()
mapped_payload = engine.load_chunks(mapped, "WrapCarrierChunks")
assert_equal(len(mapped_payload["faces"]), 4, "mapped face count")
assert_equal(mapped_payload["adjacency"], baseline_payload["adjacency"], "adjacency")
assert hasattr(mapped, "MapPayloadChunks")
face14 = next(record for record in mapped_payload["faces"] if record["sub"] == "Face14")
assert abs(face14["height"] - 11.938052083641217) < 0.01
assert len(mapped_payload["triangles"]) == 2642

patterns = []
cell_ids = None
for height in (0.5, 1.0, 2.0):
    select_objects(mapped)
    pattern = engine.create_full_pattern(height=height)
    payload = engine.load_chunks(pattern, "DiamondPatternCellChunks")
    ids = [record["id"] for record in payload["cells"]]
    if cell_ids is None:
        cell_ids = ids
    else:
        assert_equal(ids, cell_ids, "cell IDs at height {}".format(height))
    assert abs(float(pattern.PatternHeight) - height) < 1.0e-9
    assert abs(float(pattern.DiamondHeight) - 12.0) < 1.0e-9
    assert abs(float(payload["parameters"]["height"]) - height) < 1.0e-9
    assert abs(float(payload["parameters"]["pyramid_height"]) - height) < 1.0e-9
    assert abs(float(payload["parameters"]["diamond_height"]) - 12.0) < 1.0e-9
    patterns.append(pattern)

select_objects(mapped, patterns[-1])
trimmed = engine.create_cut()
assert abs(float(trimmed.PatternHeight) - 2.0) < 1.0e-9
assert abs(float(trimmed.DiamondHeight) - 12.0) < 1.0e-9
assert_equal(trimmed.PatternMapSource, mapped.Name, "trim map source")
assert_equal(trimmed.PatternSource, patterns[-1].Name, "trim pattern source")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
doc.recompute()
doc.saveAs(str(OUTPUT))
summary = {
    "faces": len(mapped_payload["faces"]),
    "adjacency": mapped_payload["adjacency"],
    "carrier_triangles": len(mapped_payload["triangles"]),
    "pattern_cells": len(cell_ids),
    "pattern_solids": [len(pattern.Shape.Solids) for pattern in patterns],
    "trim_solids": len(trimmed.Shape.Solids),
    "trim_algorithm": trimmed.DiamondPatternAlgorithm,
    "output": str(OUTPUT),
}
print("INTEGRATION_RESULT=" + json.dumps(summary, sort_keys=True))
App.closeDocument(doc.Name)
