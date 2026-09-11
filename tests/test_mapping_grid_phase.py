"""MAP-REQ-030 body-anchored Map Faces phase tests."""

import unittest

from pattern_surface.mapping.grid_phase import body_anchored_grid_origin


class Vec(object):
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Vertex(object):
    def __init__(self, point):
        self.Point = point


class Shape(object):
    def __init__(self, vertices):
        self.Vertexes = [Vertex(point) for point in vertices]


class Body(object):
    TypeId = "PartDesign::Body"

    def __init__(self):
        self.Shape = Shape([Vec(0, 0, 0), Vec(30, 0, 0), Vec(0, 12, 0), Vec(30, 12, 0)])


class Feature(object):
    TypeId = "PartDesign::Feature"

    def __init__(self, body):
        self.body = body

    def getParentGeoFeatureGroup(self):
        return self.body


def patch(x0, x1):
    vertices = [
        {"p": [x0, 0, 0], "q": [0, 0]},
        {"p": [x1, 0, 0], "q": [x1 - x0, 0]},
        {"p": [x0, 12, 0], "q": [0, 12]},
    ]
    return [{"v": vertices}]


def vertical_patch(x0=0, x1=10):
    return [{"v": [
        {"p": [x0, 0, 0], "q": [0, 0]},
        {"p": [x1, 0, 0], "q": [x1 - x0, 0]},
        {"p": [x0, 0, 12], "q": [0, 12]},
    ]}]


class GridPhaseTests(unittest.TestCase):
    def test_same_body_maps_project_one_physical_anchor_into_each_local_atlas(self):
        body = Body()
        entries = [{"object": Feature(body)}]
        # Both patches live on one plane but use the normal independent Map
        # Faces local atlas.  The origin of the one body is projected into
        # each chart, retaining a common physical phase.
        left = body_anchored_grid_origin(entries, patch(0, 10), [5, 6])
        right = body_anchored_grid_origin(entries, patch(20, 30), [5, 6])
        self.assertEqual([15.0, 6.0], left)
        self.assertEqual([-5.0, 6.0], right)

    def test_multiple_bodies_keep_the_legacy_centered_fallback(self):
        entries = [{"object": Feature(Body())}, {"object": Feature(Body())}]
        self.assertEqual([5, 6], body_anchored_grid_origin(entries, patch(0, 10), [5, 6]))


class MapObject(object):
    def __init__(self, name, payload):
        import base64
        import json
        import zlib
        self.Name = name
        self.MapPayloadChunks = [base64.b64encode(
            zlib.compress(json.dumps(payload).encode("utf-8"))).decode("ascii")]


class Document(object):
    def __init__(self, objects, named):
        self.Objects = objects
        self._named = named

    def getObject(self, name):
        return self._named.get(name)


def segment(a, b):
    return {"a": {"p": list(a[0]), "q": list(a[1])},
            "b": {"p": list(b[0]), "q": list(b[1])}}


class PersistentGridPhaseTests(unittest.TestCase):
    def test_explicit_column_alignment_starts_rows_at_selected_lower_edge(self):
        from pattern_surface.mapping.grid_phase import grid_origin_for_alignment
        body = Body()
        source = Feature(body)
        document = Document([], {"Source": source})
        entries = [{"object": source}]
        bounds = [0, 10, 0, 12]
        self.assertEqual([0.0, 0.0], grid_origin_for_alignment(
            document, entries, vertical_patch(), bounds, "left"))
        self.assertEqual([5.0, 0.0], grid_origin_for_alignment(
            document, entries, vertical_patch(), bounds, "center"))
        self.assertEqual([10.0, 0.0], grid_origin_for_alignment(
            document, entries, vertical_patch(), bounds, "right"))
        self.assertEqual([5.0, 12.0], grid_origin_for_alignment(
            document, entries, vertical_patch(), bounds, "center", "top"))
        self.assertEqual([5.0, 6.0], grid_origin_for_alignment(
            document, entries, vertical_patch(), bounds, "center", "center"))

    def test_first_body_map_centres_columns_and_starts_rows_at_body_bottom(self):
        from pattern_surface.mapping.grid_phase import body_phase_grid_origin
        body = Body()
        source = Feature(body)
        document = Document([], {"Source": source})
        # The body anchor projects to x=15 in this horizontal local carrier.
        # The column origin is intentionally the selected patch centre (5).
        # On a horizontal face the lower body extent is normal to the chart,
        # so row phase keeps the chart-centred fallback (6).
        self.assertEqual(
            [5.0, 6.0],
            body_phase_grid_origin(document, [{"object": source}], patch(0, 10), [5, 6]))

    def test_non_adjacent_same_body_map_inherits_root_anchor_phase(self):
        from pattern_surface.mapping.grid_phase import body_phase_grid_origin
        body = Body()
        source = Feature(body)
        root = {
            "faces": [{"object": "Source"}],
            "grid": {"origin": [5.0, 0.0]},
            "carrier_triangles": vertical_patch(0, 10),
        }
        document = Document([MapObject("FirstMap", root)], {"Source": source})
        # This patch has no shared edge with the first one. The common Body
        # anchor nevertheless produces the same physical modulo-10 phase:
        # q-origin is -5 at the root left edge and +15 at this left edge.
        self.assertEqual(
            [-15.0, 0.0],
            body_phase_grid_origin(document, [{"object": source}], vertical_patch(20, 30), [5, 6]))

    def test_disconnected_wall_uses_its_own_physical_lower_row(self):
        from pattern_surface.mapping.grid_phase import body_phase_grid_origin
        body = Body()
        source = Feature(body)
        root = {
            "faces": [{"object": "Source"}],
            "grid": {"origin": [5.0, 0.0]},
            "carrier_triangles": vertical_patch(),
        }
        document = Document([MapObject("FirstMap", root)], {"Source": source})
        disconnected = vertical_patch()
        for vertex in disconnected[0]["v"]:
            vertex["q"][1] += 13.43318350724256
        # The chart begins at a different q value, but that value belongs to
        # its physical lower boundary. A remote body vertex must not shift it.
        self.assertEqual(
            13.43318350724256,
            body_phase_grid_origin(document, [{"object": source}], disconnected, [5, 6])[1])

    def test_new_same_body_map_registers_all_grid_axes_to_existing_map(self):
        from pattern_surface.mapping.grid_phase import align_grid_to_existing_body_map
        body = Body()
        source = Feature(body)
        reference = {
            "faces": [{"object": "Source"}],
            "grid": {"origin": [100.0, 50.0]},
            "external_segments": [segment(((0, 0, 0), (100, 50)),
                                           ((10, 0, 0), (110, 50)))],
        }
        document = Document([MapObject("PriorMap", reference)], {"Source": source})
        entries = [{"object": source, "transform": [1, 0, 0, 1, 0, 0]}]
        triangles = patch(0, 10)
        boundary = [segment(((0, 0, 0), (0, 0)), ((10, 0, 0), (10, 0)))]
        origin = align_grid_to_existing_body_map(document, entries, triangles, boundary)
        self.assertEqual([100.0, 50.0], origin)
        self.assertEqual([100.0, 50.0], triangles[0]["v"][0]["q"])
        self.assertEqual([110.0, 50.0], triangles[0]["v"][1]["q"])
        self.assertEqual([1.0, 0.0, 0.0, 1.0, 100.0, 50.0], entries[0]["transform"])

    def test_one_face_map_uses_a_matching_internal_edge_of_a_larger_map(self):
        from pattern_surface.mapping.grid_phase import align_grid_to_existing_body_map
        body = Body()
        source = Feature(body)
        carrier = patch(0, 10)
        for vertex in carrier[0]["v"]:
            vertex["q"] = [vertex["q"][0] + 100.0, vertex["q"][1] + 50.0]
        reference = {
            "faces": [{"object": "Source"}],
            "grid": {"origin": [100.0, 50.0]},
            # This is deliberately not adjacent to the new one-face rim.
            "external_segments": [segment(((0, 20, 0), (100, 70)),
                                           ((10, 20, 0), (110, 70)))],
            "carrier_triangles": carrier,
        }
        document = Document([MapObject("LargerMap", reference)], {"Source": source})
        entries = [{"object": source, "transform": [1, 0, 0, 1, 0, 0]}]
        triangles = patch(0, 10)
        boundary = [segment(((0, 0, 0), (0, 0)), ((10, 0, 0), (10, 0)))]
        origin = align_grid_to_existing_body_map(document, entries, triangles, boundary)
        self.assertEqual([100.0, 50.0], origin)
        self.assertEqual([100.0, 50.0], triangles[0]["v"][0]["q"])
        self.assertEqual([110.0, 50.0], triangles[0]["v"][1]["q"])

    def test_oldest_compatible_map_is_the_same_body_phase_root(self):
        from pattern_surface.mapping.grid_phase import align_grid_to_existing_body_map
        body = Body()
        source = Feature(body)
        first = {"faces": [{"object": "Source"}], "grid": {"origin": [100.0, 50.0]},
                 "external_segments": [segment(((0, 0, 0), (100, 50)), ((10, 0, 0), (110, 50)))]}
        later = {"faces": [{"object": "Source"}], "grid": {"origin": [500.0, 50.0]},
                 "external_segments": [segment(((0, 0, 0), (500, 50)), ((10, 0, 0), (510, 50)))]}
        document = Document([MapObject("Earlier", first), MapObject("Later", later)], {"Source": source})
        entries = [{"object": source, "transform": [1, 0, 0, 1, 0, 0]}]
        triangles = patch(0, 10)
        boundary = [segment(((0, 0, 0), (0, 0)), ((10, 0, 0), (10, 0)))]
        self.assertEqual([100.0, 50.0], align_grid_to_existing_body_map(document, entries, triangles, boundary))

class TopologicalGridPhaseTests(unittest.TestCase):
    def test_new_disconnected_face_inherits_phase_through_source_topology_only(self):
        """MAP-REQ-030: phase is established while creating the new map."""
        import base64
        import copy
        import json
        import zlib
        import FreeCAD as App
        import Part
        from pattern_surface import core_engine
        from pattern_surface.mapping.grid_phase import register_grid_to_body_phase

        class StoredMap(object):
            Name = "FirstMap"

            def __init__(self, payload):
                self.MapPayloadChunks = [base64.b64encode(zlib.compress(
                    json.dumps(payload).encode("utf-8"))).decode("ascii")]

        document = App.newDocument("MapPhaseTopology")
        try:
            body = document.addObject("PartDesign::Body", "Body")
            source = document.addObject("PartDesign::Feature", "Source")
            body.addObject(source)
            source.Shape = Part.makeBox(20, 10, 12)
            document.recompute()
            root = StoredMap({
                "faces": [{"object": "Source", "sub": "Face1",
                           "transform": [1, 0, 0, 1, 100, 50]}],
                "grid": {"origin": [100, 50]},
            })
            root_chunks = copy.deepcopy(root.MapPayloadChunks)

            class DocumentProxy(object):
                Objects = [root]

                @staticmethod
                def getObject(name):
                    return source if name == "Source" else None

            current = {"object": source, "sub": "Face2",
                       "face": source.getSubObject("Face2"), "picked": None,
                       "index": 0}
            core_engine.orient_entry(current)
            current["transform"] = [1, 0, 0, 1, 0, 0]
            triangles = [{"v": [
                {"p": [0, 0, 0], "q": [0, 0]},
                {"p": [1, 0, 0], "q": [1, 0]},
                {"p": [0, 0, 1], "q": [0, 1]},
            ]}]
            origin = register_grid_to_body_phase(DocumentProxy(), [current], triangles, [])

            self.assertEqual([100.0, 50.0], origin)
            self.assertEqual([1.0, 0.0, 0.0, 1.0, 130.0, 50.0], current["transform"])
            self.assertEqual([130.0, 50.0], triangles[0]["v"][0]["q"])
            # The root is a read-only reference; its persisted payload remains
            # byte-for-byte untouched when a later map is created.
            self.assertEqual(root_chunks, root.MapPayloadChunks)
        finally:
            App.closeDocument(document.Name)

class DetachedSourcePhaseTests(unittest.TestCase):
    """MAP-REQ-030: split solids retain a phase without a PartDesign Body."""

    class DetachedFeature(object):
        TypeId = "Part::Feature"
        def __init__(self, name):
            self.Name = name
            self.Shape = Shape([Vec(0, 0, 4), Vec(20, 0, 4),
                                Vec(0, 0, 16), Vec(20, 0, 16)])
            self.Placement = None

    def test_first_detached_map_starts_rows_at_its_physical_lower_edge(self):
        from pattern_surface.mapping.grid_phase import body_phase_grid_origin
        source = self.DetachedFeature("SplitA")
        triangles = [{"v": [
            {"p": [0, 0, 4], "q": [0, 31]},
            {"p": [20, 0, 4], "q": [20, 31]},
            {"p": [0, 0, 16], "q": [0, 43]},
        ]}]
        document = Document([], {"SplitA": source})
        self.assertEqual([10.0, 31.0], body_phase_grid_origin(
            document, [{"object": source}], triangles, [10, 37]))

    def test_detached_neighbour_registers_to_oldest_coincident_map(self):
        from pattern_surface.mapping.grid_phase import align_grid_to_existing_body_map
        left, right = self.DetachedFeature("SplitA"), self.DetachedFeature("SplitB")
        reference = {
            "faces": [{"object": "SplitA"}],
            "grid": {"origin": [100.0, 50.0]},
            "external_segments": [segment(((10, 0, 0), (110, 50)),
                                           ((10, 0, 12), (110, 62)))],
        }
        document = Document([MapObject("FirstSplitMap", reference)],
                            {"SplitA": left, "SplitB": right})
        entries = [{"object": right, "transform": [1, 0, 0, 1, 0, 0]}]
        triangles = [{"v": [
            {"p": [10, 0, 0], "q": [0, 0]},
            {"p": [10, 0, 12], "q": [0, 12]},
            {"p": [20, 0, 0], "q": [10, 0]},
        ]}]
        boundary = [segment(((10, 0, 0), (0, 0)),
                            ((10, 0, 12), (0, 12)))]
        self.assertEqual([100.0, 50.0], align_grid_to_existing_body_map(
            document, entries, triangles, boundary))
        self.assertEqual([110.0, 50.0], triangles[0]["v"][0]["q"])
        self.assertEqual([110.0, 62.0], triangles[0]["v"][1]["q"])
