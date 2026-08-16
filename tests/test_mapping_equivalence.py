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
        for property_name in (
                "WrapCarrierChunks", "MapPayloadChunks", "MapAlgorithm",
                "MapColumnWidth", "MapRowHeight", "MapGridOrigin",
                "MapClosureTolerance", "MapCompatible",
                "MapIncompatibleCount", "MapCompatibilityReport"):
            self.assertIn(property_name, source)

    def test_map_grid_dialog_contract(self):
        # MAP-REQ-010: independent persisted grid dimensions and tolerance.
        from pattern_surface.mapping import parameters

        self.assertAlmostEqual(13.85640646055102, parameters.DEFAULT_COLUMN_WIDTH)
        self.assertEqual(12.0, parameters.DEFAULT_ROW_HEIGHT)
        self.assertEqual(0.05, parameters.DEFAULT_CLOSURE_TOLERANCE)
        self.assertIn("ColumnWidth", parameters.COLUMN_WIDTH_KEY)
        self.assertIn("RowHeight", parameters.ROW_HEIGHT_KEY)
        self.assertIn("ClosureTolerance", parameters.CLOSURE_TOLERANCE_KEY)

    def test_generic_grid_uses_independent_centered_axes(self):
        # MAP-REQ-023, MAP-REQ-024, MAP-REQ-025.
        from pattern_surface.compatibility import v4_pipeline as engine

        self.assertEqual([-5.0, 5.0], engine.grid_line_values(-6.0, 8.0, 5.0, 10.0))
        self.assertEqual([-3.0, 3.0, 9.0], engine.grid_line_values(-4.0, 10.0, 3.0, 6.0))

    def test_face_positioning_does_not_snap_to_pattern_grid(self):
        # MAP-REQ-026: grid phase must not move the physical carrier.
        source = ENGINE.read_text(encoding="utf-8")
        position_start = source.index("def position_components")
        position_end = source.index("def atlas_seam_pairs", position_start)
        self.assertNotIn("snap_lower_curved_strips_to_grid(group)",
                         source[position_start:position_end])

    def test_invalid_grid_dimensions_are_rejected(self):
        # MAP-REQ-010: public callers receive the same positive-length guard.
        from pattern_surface.compatibility import v4_pipeline as engine

        for values in ((0.0, 12.0, 0.05), (10.0, -1.0, 0.05),
                       (10.0, 12.0, float("inf"))):
            with self.subTest(values=values):
                with self.assertRaises(RuntimeError):
                    engine.validate_map_grid(*values)

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
