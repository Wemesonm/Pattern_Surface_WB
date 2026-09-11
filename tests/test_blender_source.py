"""PAT-REQ-065: preserve the mapped solid identity during Blender export."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from pattern_surface.blender_bridge.job import _solid_owner, cleanup_jobs


class BlenderSourceTests(unittest.TestCase):
    def test_cleanup_removes_only_transient_auzyron_packages(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'auzyron-old').mkdir()
            (root / 'auzyron-old' / 'source_body.stl').write_text('temporary')
            (root / 'user-export').mkdir()
            self.assertEqual(1, cleanup_jobs(root))
            self.assertFalse((root / 'auzyron-old').exists())
            self.assertTrue((root / 'user-export').exists())

    def test_interactive_worker_keeps_the_stl_import_context(self):
        worker = (Path(__file__).parents[1] / 'pattern_surface/blender_bridge/worker.py')
        source = worker.read_text(encoding='utf-8')
        self.assertIn('if not _interactive():\n            bpy.ops.wm.read_factory_settings', source)

    def test_worker_does_not_open_with_the_cad_stl_selected(self):
        worker = (Path(__file__).parents[1] / 'pattern_surface/blender_bridge/worker.py')
        source = worker.read_text(encoding='utf-8')
        self.assertIn('bpy.context.view_layer.objects.active = None', source)

    def test_mapped_solid_is_not_replaced_by_enclosing_assembly(self):
        import FreeCAD as App
        import Part
        doc = App.newDocument('SourceExportTest')
        try:
            group = doc.addObject('App::Part', 'Assembly')
            source = doc.addObject('PartDesign::Feature', 'MappedFeature')
            source.Shape = Part.makeBox(10, 10, 10)
            sibling = doc.addObject('PartDesign::Feature', 'UnrelatedFeature')
            sibling.Shape = Part.makeBox(5, 5, 5)
            group.addObject(source)
            group.addObject(sibling)
            doc.recompute()
            self.assertIs(source, _solid_owner(source))
        finally:
            App.closeDocument(doc.Name)

    def test_partdesign_feature_prefers_its_finished_body(self):
        import FreeCAD as App
        import Part
        doc = App.newDocument('SourceBodyOwnerTest')
        try:
            body = doc.addObject('PartDesign::Body', 'FinishedBody')
            feature = doc.addObject('PartDesign::Feature', 'FaceProvider')
            body.addObject(feature)
            feature.Shape = Part.makeBox(10, 10, 10)
            doc.recompute()
            self.assertIs(body, _solid_owner(feature))
        finally:
            App.closeDocument(doc.Name)

    def test_overlapping_sources_are_united_before_meshing(self):
        import FreeCAD as App
        import Part
        from pattern_surface.blender_bridge.job import _export_clean_shape
        doc = App.newDocument('SourceUnionTest')
        try:
            a = doc.addObject('Part::Feature', 'First')
            b = doc.addObject('Part::Feature', 'Second')
            a.Shape = Part.makeBox(10, 10, 10)
            b.Shape = Part.makeBox(10, 10, 10, App.Vector(5, 0, 0))
            captured = []
            with patch('Mesh.export', side_effect=lambda objects, path:
                       captured.append(objects[0].Shape.copy())):
                _export_clean_shape(doc, [a, b], 'unused.stl')
            self.assertEqual(1, len(captured[0].Solids))
            self.assertAlmostEqual(1500, captured[0].Volume)
            self.assertEqual(2, len(doc.Objects))
        finally:
            App.closeDocument(doc.Name)

    def test_closed_cavity_preserves_cad_shell_count(self):
        import FreeCAD as App
        import Part
        from pattern_surface.blender_bridge.job import _export_clean_shape
        doc = App.newDocument('CavityExportTest')
        try:
            obj = doc.addObject('Part::Feature', 'HollowSolid')
            obj.Shape = Part.makeBox(10, 10, 10).cut(
                Part.makeBox(6, 6, 6, App.Vector(2, 2, 2)))
            with patch('Mesh.export'):
                topology = _export_clean_shape(doc, [obj], 'unused.stl')
            self.assertEqual(1, topology['solids'])
            self.assertEqual(2, topology['shells'])
            self.assertAlmostEqual(784, topology['volume_mm3'])
        finally:
            App.closeDocument(doc.Name)

    def test_empty_selection_reports_without_startup_gui_api(self):
        from pattern_surface.commands import blender_diamond as command
        with patch.object(command, 'Gui', SimpleNamespace(
                Selection=SimpleNamespace(getSelection=lambda: []))), \
                patch.object(command, 'App') as app:
            command.BlenderDiamondCommand().Activated()
            app.Console.PrintError.assert_called_once()

    def test_blender_command_uses_the_diamond_dialog_without_requiring_a_result(self):
        from pattern_surface.commands import blender_diamond as command
        source = Path(command.__file__).read_text(encoding='utf-8')
        self.assertIn('diamond_parameters.get_parameters(mapped[0], blender=True)', source)
        self.assertIn('include_boundary_curves=parameters.get("base_blend", 0.0) > 0.0', source)

    def test_shared_phase_jobs_keep_independent_component_exports(self):
        source = (Path(__file__).parents[1] / 'pattern_surface/blender_bridge/job.py').read_text(encoding='utf-8')
        worker = (Path(__file__).parents[1] / 'pattern_surface/blender_bridge/worker.py').read_text(encoding='utf-8')
        self.assertIn('job["components"] = components', source)
        self.assertIn('"shared_phase"', source)
        self.assertIn('"shared_map_phase"', source)
        self.assertIn('def _attach_shared_map_phase', source)
        self.assertIn('components_by_sources', source)
        self.assertIn('"maps": [{key: value', source)
        self.assertIn('Auzyron Shared Pattern Assembly', worker)
        self.assertIn('Auzyron CAD Body — {}', worker)
        self.assertIn('"patterns": patterns', worker)

class MultiBodyMapBridgeTests(unittest.TestCase):
    """PAT-REQ-087/DATA-REQ-058 transient multi-body map partitioning."""

    class _Shape:
        Solids = [object()]
        def isNull(self):
            return False

    class _Body:
        TypeId = 'PartDesign::Body'
        def __init__(self, name):
            self.Name = name
            self.Label = name
            self.Shape = MultiBodyMapBridgeTests._Shape()

    class _Feature:
        def __init__(self, name, body):
            self.Name = name
            self._body = body
        def getParentGeoFeatureGroup(self):
            return self._body

    class _Document:
        def __init__(self, objects):
            self._objects = {obj.Name: obj for obj in objects}
        def getObject(self, name):
            return self._objects.get(name)

    @staticmethod
    def _payload():
        point = lambda x, y: {'p': [x, y, 0], 'q': [x, y], 'n': [0, 0, 1]}
        a, b, c = point(0, 0), point(10, 0), point(0, 10)
        d, e, f = point(12, 0), point(22, 0), point(12, 10)
        return {
            'faces': [
                {'index': 10, 'object': 'FeatureA', 'sub': 'Face1'},
                {'index': 20, 'object': 'FeatureB', 'sub': 'Face1'},
            ],
            'carrier_triangles': [
                {'face': 10, 'component': 0, 'v': [a, b, c]},
                {'face': 20, 'component': 1, 'v': [d, e, f]},
            ],
            'external_segments': [
                {'face': 10, 'component': 0, 'a': a, 'b': b},
                {'face': 20, 'component': 1, 'a': d, 'b': e},
            ],
            'adjacency': [], 'periodic_seams': [],
            'components': [[10], [20]],
            'periodic_adjustments': [{'component': 1, 'axis': 0, 'lower': 12}],
            'grid': {'origin': [0, 0]},
        }

    def test_one_multibody_map_becomes_one_transient_payload_per_body(self):
        from pattern_surface.blender_bridge.job import _payloads_by_source_body
        body_a, body_b = self._Body('BodyA'), self._Body('BodyB')
        doc = self._Document([self._Feature('FeatureA', body_a),
                              self._Feature('FeatureB', body_b)])
        original = self._payload()
        split = _payloads_by_source_body(doc, original)
        self.assertEqual(['BodyA', 'BodyB'], [owner for owner, _payload in split])
        self.assertEqual([10, 20], [face['index'] for face in original['faces']])
        for owner, payload in split:
            self.assertEqual([0], [face['index'] for face in payload['faces']])
            self.assertEqual([0], [triangle['face'] for triangle in payload['carrier_triangles']])
            self.assertEqual([0], [segment['face'] for segment in payload['external_segments']])
            self.assertEqual([[0]], payload['components'])
            self.assertEqual([0], [triangle['component'] for triangle in payload['carrier_triangles']])
        self.assertEqual([], split[0][1]['periodic_adjustments'])
        self.assertEqual([0], [row['component'] for row in split[1][1]['periodic_adjustments']])

    def test_multibody_map_job_exports_two_movable_components(self):
        """PAT-REQ-087: one map selection must never fuse movable Bodies."""
        import base64
        import json
        import zlib
        from pattern_surface.blender_bridge import job

        body_a, body_b = self._Body('BodyA'), self._Body('BodyB')
        feature_a, feature_b = self._Feature('FeatureA', body_a), self._Feature('FeatureB', body_b)
        doc = self._Document([feature_a, feature_b])
        doc.Name = 'TransientAssembly'
        payload = self._payload()
        packed = base64.b64encode(zlib.compress(json.dumps(payload).encode('utf-8'))).decode('ascii')
        mapped = SimpleNamespace(Name='MappedSurface', Label='Mapped Surface', Document=doc,
                                 PropertiesList=['MapPayloadChunks'], MapPayloadChunks=[packed])
        with TemporaryDirectory() as temporary, \
             patch('pattern_surface.blender_bridge.reference.prepare_reference', side_effect=lambda _doc, item, **_kw: item), \
             patch('pattern_surface.blender_bridge.shared_phase.align', side_effect=lambda rows: (rows, [{'reference': 0}, {'reference': 0}])), \
             patch('pattern_surface.blender_bridge.job._export_clean_shape', return_value={'valid': True}):
            job_path = job.create_job(mapped, {'module_width': 10}, root=temporary)
            data = json.loads(job_path.read_text(encoding='utf-8'))
        self.assertEqual(2, len(data['components']))
        self.assertEqual([['BodyA'], ['BodyB']], [component['source_bodies'] for component in data['components']])
        self.assertEqual([1, 1], [len(component['maps']) for component in data['components']])
