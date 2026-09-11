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
        self.assertIn('components_by_sources', source)
        self.assertIn('"maps": [{key: value', source)
        self.assertIn('Auzyron Shared Pattern Assembly', worker)
        self.assertIn('Auzyron CAD Body — {}', worker)
        self.assertIn('"patterns": patterns', worker)
