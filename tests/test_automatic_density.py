"""PAT-REQ-064 / MAP-REQ-062 / DATA-REQ-042 regression coverage."""
import copy
import unittest
from unittest.mock import patch


class AutomaticDensityTests(unittest.TestCase):
    def candidates(self, payload, size):
        from pattern_surface import core_engine as engine
        candidates = []

        def no_overlap(_payload, canonical, _carriers, _ghost):
            candidates.append(canonical)
            return None, []

        # Exercise production candidate enumeration, omitting only OCC solids.
        with patch.object(engine, 'periodic_carriers', side_effect=lambda p, c: c), \
                patch.object(engine, 'extended_triangles', return_value=[]), \
                patch.object(engine, 'canonical_periodic_representative', return_value=True), \
                patch.object(engine, 'local_cell_context', side_effect=no_overlap):
            engine.build_cells(payload, False, diamond_height=size)
        return candidates

    def test_preview_counts_do_not_control_population(self):
        payload = {'bounds': [-15, 120, -25, 60], 'triangles': [],
                   'grid': {'column_count': 2, 'row_count': 1}}
        before = copy.deepcopy(payload)
        first = self.candidates(payload, 12)
        self.assertEqual(before, payload)
        payload['grid'] = {'column_count': 1000, 'row_count': 1000}
        self.assertEqual(first, self.candidates(payload, 12))
        self.assertGreater(len(self.candidates(payload, 6)), len(first))
        self.assertLess(len(self.candidates(payload, 24)), len(first))
        lower_edges = [min(p[1] for p in cell) for cell in first]
        self.assertEqual(sorted(lower_edges), lower_edges)
        self.assertTrue(all(abs(max(p[1] for p in cell) -
                                min(p[1] for p in cell) - 12) < 1e-8
                            for cell in first))

    def test_generic_map_spacing_and_legacy_count_api(self):
        from pattern_surface.mapping import engine
        with patch.object(engine, 'maybe_reload', return_value=engine.core_engine), \
                patch.object(engine.core_engine, 'create_wrap') as create:
            engine.create_map(column_width=15, row_height=10, closure_tolerance=.2)
            self.assertIsNone(create.call_args.kwargs['column_count'])
            self.assertEqual(15, create.call_args.kwargs['column_width'])
            engine.create_map(24, 4, .2)
            self.assertEqual(24, create.call_args.kwargs['column_count'])
            self.assertEqual(4, create.call_args.kwargs['row_count'])
