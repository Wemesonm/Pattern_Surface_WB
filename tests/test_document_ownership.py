"""MAP-REQ-052 / DATA-REQ-015: helpers never become PartDesign Body Tips."""

import unittest

import FreeCAD as App
import Part

from pattern_surface.common.ownership import (
    map_from_selection_object, organize_derived_object, organize_map,
)


class DocumentOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.document = App.newDocument("PatternSurfaceOwnership")
        self.component = self.document.addObject("App::Part", "Product")
        self.body = self.document.addObject("PartDesign::Body", "Housing")
        self.component.addObject(self.body)
        self.source = self.body.newObject("PartDesign::Feature", "FinishedFeature")
        self.source.Shape = Part.makeBox(10, 10, 10)
        self.document.recompute()

    def tearDown(self):
        App.closeDocument(self.document.Name)

    def test_map_and_preview_group_with_source_component_without_changing_tip(self):
        # A Body may only contain sequential PartDesign features. Map helpers
        # must stay in a neutral group or they replace the finished Body Tip.
        original_tip = self.body.Tip
        map_object = self.document.addObject("PartDesign::Feature", "MappedSurface")
        preview = self.document.addObject("PartDesign::Feature", "MappingGrid")
        group = organize_map(self.document, map_object, preview, [self.source])
        self.document.recompute()

        self.assertIs(self.body, map_object.MapSourceBody)
        self.assertEqual([self.body], list(map_object.MapSourceBodies))
        self.assertEqual(group.Name, map_object.MapOwnerGroup)
        self.assertIn(group, self.component.Group)
        self.assertEqual([map_object, preview], group.Group)
        self.assertIs(original_tip, self.body.Tip)
        self.assertAlmostEqual(1000.0, self.body.Shape.Volume)

    def test_derived_result_stays_with_its_map(self):
        map_object = self.document.addObject("PartDesign::Feature", "MappedSurface")
        preview = self.document.addObject("PartDesign::Feature", "MappingGrid")
        group = organize_map(self.document, map_object, preview, [self.source])
        result = self.document.addObject("PartDesign::Feature", "DiamondPattern")
        organize_derived_object(result, map_object)

        self.assertIn(result, group.Group)
        self.assertEqual(group.Name, result.PatternOwnerGroup)
        self.assertIs(self.body, result.PatternSourceBody)

    def test_ownership_group_resolves_to_its_map_for_every_consumer(self):
        map_object = self.document.addObject("PartDesign::Feature", "MappedSurface")
        preview = self.document.addObject("PartDesign::Feature", "MappingGrid")
        preview.addProperty("App::PropertyString", "MapParentRun")
        preview.MapParentRun = map_object.Name
        group = organize_map(self.document, map_object, preview, [self.source])

        self.assertIs(map_object, map_from_selection_object(group))
        self.assertIs(map_object, map_from_selection_object(preview))

    def test_multiple_bodies_do_not_get_assigned_to_one_body_container(self):
        other = self.document.addObject("PartDesign::Body", "OtherHousing")
        other_feature = other.newObject("PartDesign::Feature", "OtherFeature")
        other_feature.Shape = Part.makeBox(5, 5, 5)
        map_object = self.document.addObject("PartDesign::Feature", "MappedSurface")
        preview = self.document.addObject("PartDesign::Feature", "MappingGrid")
        group = organize_map(
            self.document, map_object, preview, [self.source, other_feature])

        self.assertEqual([self.body, other], list(map_object.MapSourceBodies))
        self.assertFalse(hasattr(map_object, "MapSourceBody"))
        self.assertNotIn(group, self.component.Group)
