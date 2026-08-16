import ast
import pathlib
import unittest

import FreeCAD as App


ROOT = pathlib.Path(__file__).parents[1]
ORIGINAL = ROOT / "archive/v4_original/Wrap_pipeline_V4_core.py"
ENGINE = ROOT / "pattern_surface/compatibility/v4_pipeline.py"


def functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


class MappingEquivalenceTests(unittest.TestCase):
    def test_no_original_function_was_discarded(self):
        self.assertEqual(set(), functions(ORIGINAL) - functions(ENGINE))

    def test_map_has_generic_and_legacy_metadata(self):
        source = ENGINE.read_text(encoding="utf-8")
        for property_name in ("WrapCarrierChunks", "MapPayloadChunks", "MapAlgorithm"):
            self.assertIn(property_name, source)

    def test_periodic_seam_parameters_stay_in_trimmed_intervals(self):
        from pattern_surface.compatibility import v4_pipeline as engine

        document = App.openDocument(str(ROOT / "tests/fixtures/container_four_faces.FCStd"))
        try:
            source = document.getObject("Thickness001")
            for face_name in ("Face14", "Face4"):
                face = source.getSubObject(face_name)
                u0, u1, _, _ = face.ParameterRange
                for edge in face.OuterWire.OrderedEdges:
                    for point in edge.discretize(Number=17):
                        u, _ = engine.surface_parameters(face, point)
                        self.assertGreaterEqual(u, u0 - 1.0e-9)
                        self.assertLessEqual(u, u1 + 1.0e-9)
        finally:
            App.closeDocument(document.Name)

    def test_curved_face_with_two_neighbors_keeps_both_seams_aligned(self):
        from pattern_surface.compatibility import v4_pipeline as engine

        document = App.openDocument(str(ROOT / "tests/fixtures/container_four_faces.FCStd"))
        try:
            source = document.getObject("Thickness001")
            names = ("Face14", "Face4", "Face8", "Face9")
            entries = [{"object": source, "sub": name,
                        "face": source.getSubObject(name), "picked": None}
                       for name in sorted(names)]
            for index, entry in enumerate(entries):
                entry["index"] = index
                engine.orient_entry(entry)
            graph, _shared = engine.build_graph(entries)
            engine.position_components(entries, graph)
            by_index = {entry["index"]: entry for entry in entries}
            checked = set()
            for entry in entries:
                for neighbor_index, edge, other_edge in graph[entry["index"]]:
                    pair = tuple(sorted((entry["index"], neighbor_index)))
                    if pair in checked:
                        continue
                    checked.add(pair)
                    neighbor = by_index[neighbor_index]
                    left, right = engine.aligned_edge_samples(edge, other_edge)
                    for sample_index in range(9):
                        ratio = sample_index / 8.0
                        li = int(round(ratio * (len(left) - 1)))
                        ri = int(round(ratio * (len(right) - 1)))
                        qa = engine.apply_transform(
                            entry, engine.local_xy_raw(entry, left[li]))
                        qb = engine.apply_transform(
                            neighbor, engine.local_xy_raw(neighbor, right[ri]))
                        self.assertAlmostEqual(qa[0], qb[0], places=4)
                        self.assertAlmostEqual(qa[1], qb[1], places=4)
        finally:
            App.closeDocument(document.Name)


if __name__ == "__main__":
    unittest.main()
