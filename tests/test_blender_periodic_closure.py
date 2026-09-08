import importlib.util
import math
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "geometry_closed", Path(__file__).parents[1] / "pattern_surface/blender_bridge/geometry_closed.py")
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)


class PeriodicClosureTest(unittest.TestCase):
    def test_approved_september6_vertices_faces_and_relief_are_unchanged(self):
        # PAT-REQ-071: golden output computed from the recovered September 6
        # source, including all coordinates, face indices and facet identities.
        import hashlib
        import json
        def vertex(i, z):
            angle = 2 * math.pi * i / 48
            return {"q": [24*i/48, z],
                    "p": [10*math.cos(angle), 10*math.sin(angle), z],
                    "n": [math.cos(angle), math.sin(angle), 0]}
        carrier = []
        for i in range(48):
            a,b,c,d = vertex(i,0),vertex(i+1,0),vertex(i,8),vertex(i+1,8)
            carrier.extend([{"v":[a,b,c]}, {"v":[b,d,c]}])
        payload = {"carrier_triangles":carrier, "bounds":[0,24,0,8],
                   "grid":{"origin":[0,0]},
                   "periodic_adjustments":[{"axis":0,"period":24,"lower":0}]}
        params = {"diamond_height":4,"diamond_side":4,"pyramid_height":1}
        result = geometry.build(payload, params)
        self.assertEqual("regular_sampled_facets",result["stats"]["algorithm"])
        self.assertEqual(8,result["dimensions"]["resolution"])
        data = {"vertices":[[round(x,8) for x in v] for v in result["vertices"]],
                "faces":result["faces"],"facet_ids":result["facet_ids"]}
        digest = hashlib.sha256(json.dumps(data,separators=(",",":")).encode()).hexdigest()
        self.assertEqual("d6ebfddc2e031425796b2a13daabbbd4576cb5eb7bf5ed23bc4603b5eea8f715",digest)
        # Requested size remains independent of preview grid density.
        payload["grid"].update(column_width=100,row_height=200)
        self.assertEqual(result["vertices"],geometry.build(payload,params)["vertices"])
        # Unaligned open rims retain today's clipping instead of losing rows.
        for t in carrier:
            for v in t["v"]:
                if v["q"][1] == 8:
                    v["q"][1] = 7
                    v["p"][2] = 7
        payload["bounds"][3] = 7
        clipped = geometry.build(payload,params)
        self.assertEqual("regular_sampled_facets",clipped["stats"]["algorithm"])
        self.assertEqual(0,clipped["stats"]["bad_edges_before_weld"])
        for face in clipped["faces"]:
            if len(face)==4:
                zs=[clipped["vertices"][i][2] for i in face]
                self.assertLess(max(zs)-min(zs),1e-6)
                self.assertTrue(abs(zs[0])<1e-6 or abs(zs[0]-7)<1e-6)

    def test_row_axis_follows_rotated_geometry_and_not_triangle_winding(self):
        # PAT-REQ-070: longitudinal relief protection is never tied to global Z.
        vertices=[{"q":[0,0],"p":[0,0,0]},
                  {"q":[1,0],"p":[0,0,1]},
                  {"q":[0,1],"p":[1,0,0]}]
        for vs in (vertices,list(reversed(vertices))):
            axis=geometry._infer_axis([{"v":vs,"curved":False}])
            self.assertAlmostEqual(axis[0],1)
            self.assertAlmostEqual(axis[1],0)
            self.assertAlmostEqual(axis[2],0)

    def test_carrier_t_junction_is_stitched_before_shell_closure(self):
        # PAT-REQ-069: mismatched carrier subdivisions must not create internal caps.
        def v(x,y): return {"q":[x,y],"p":[x,y,0],"n":[0,0,1]}
        a,b,c,d,m=v(0,0),v(12,0),v(0,12),v(12,12),v(6,6)
        payload={"bounds":[0,12,0,12],"carrier_triangles":[
            {"v":[a,b,c]},{"v":[b,d,m]},{"v":[d,c,m]}]}
        data=geometry.build(payload,{"resolution":5})
        self.assertEqual(data["stats"]["bad_edges_before_weld"],0)

    def test_resolution_refines_curved_sampling_without_opening_edges(self):
        # PAT-REQ-069: independent sampling must affect geometry and keep seams.
        def v(x,y):
            return {"q":[x,y], "p":[x,y,0], "n":[math.sin(x/30),0,math.cos(x/30)]}
        payload={"bounds":[0,12,0,12], "carrier_triangles":[
            {"v":[v(0,0),v(12,0),v(0,12)]},
            {"v":[v(12,0),v(12,12),v(0,12)]}]}
        low=geometry.build(payload,{"resolution":2})
        high=geometry.build(payload,{"resolution":20})
        self.assertGreater(len(high["faces"]),len(low["faces"])*4)
        self.assertEqual(high["stats"]["bad_edges_before_weld"],0)
        self.assertEqual(high["dimensions"]["relief"],low["dimensions"]["relief"])

    def test_boundary_relief_follows_carrier_triangle_not_cell_centers(self):
        # PAT-REQ-066: clipping at the diagonal preserves the selected-face
        # boundary instead of leaving a staircase of complete lattice cells.
        def v(x, y):
            return {"q": [x, y], "p": [x, y, 0], "n": [0, 0, 1]}
        data = geometry.build({
            "bounds": [0, 12, 0, 12],
            "carrier_triangles": [{"v": [v(0, 0), v(12, 0), v(0, 12)]}],
            "grid": {"column_width": 4, "row_height": 4, "origin": [0, 0]},
        }, {"resolution": 2, "pyramid_height": 1})
        # All outer vertices remain on or inside x + y = 12.  There are also
        # several non-corner points on that line, proving the edge was clipped
        # geometrically rather than selected by complete-cell centers.
        outer = data["vertices"][:len(data["vertices"]) // 2]
        self.assertTrue(all(point[0] + point[1] <= 12.000001 for point in outer))
        boundary = [point for point in outer
                    if abs(point[0] + point[1] - 12) < 1e-6]
        self.assertGreater(len(boundary), 2)
        self.assertEqual(0, data["stats"]["bad_edges_before_weld"])

    def test_partial_boundary_leaves_no_unreferenced_vertices(self):
        # PAT-REQ-065: rejected samples must not become loose components.
        def v(x, y):
            return {"q": [x, y], "p": [x, y, 0], "n": [0, 0, 1]}
        data = geometry.build({
            "bounds": [0, 10, 0, 10],
            "carrier_triangles": [{"v": [v(0, 0), v(10, 0), v(0, 10)]}],
            "grid": {"column_width": 4, "row_height": 4},
        }, {"resolution": 3})
        self.assertEqual(set(range(len(data["vertices"]))),
                         {i for face in data["faces"] for i in face})
        self.assertEqual(0, data["stats"]["bad_edges_before_weld"])

    def test_planar_tapered_wrap_closes_with_roundoff_origin(self):
        # PAT-REQ-060/062: a tapered atlas, including its periodic sharp corner.
        lower = -1.4210854715202e-14
        corners = [(-35, -25), (35, -25), (35, 25), (-35, 25)]
        tops = [(-50, -40), (50, -40), (50, 40), (-50, 40)]
        widths = [85, 65, 85, 65]
        normals = [(0, -4, -1), (4, 0, -1), (0, 4, -1), (-4, 0, -1)]
        carriers = []
        x = lower
        for i, width in enumerate(widths):
            n = geometry._unit(normals[i])
            def v(u, t):
                a, b = corners[i], corners[(i+1) % 4]
                c, d = tops[i], tops[(i+1) % 4]
                p = [(1-t)*((1-u)*a[k]+u*b[k])+t*((1-u)*c[k]+u*d[k]) for k in range(2)]
                return {"q": [x+u*width, t*60], "p": p+[60*t], "n": n}
            a, b, c, d = v(0, 0), v(1, 0), v(0, 1), v(1, 1)
            carriers.extend([{"face": i, "v": [a, b, c]}, {"face": i, "v": [b, d, c]}])
            x += width
        payload = {"carrier_triangles": carriers, "bounds": [lower, x, 0, 60],
                   "grid": {"column_width": 12.5, "row_height": 15, "origin": [lower, 30]},
                   "periodic_adjustments": [{"axis": 0, "period": 300, "lower": lower}]}
        result = geometry.build(payload, {"resolution": 3,
                                          "diamond_height": 15,
                                          "diamond_side": 12.5})
        self.assertEqual(result["stats"]["algorithm"], "rigid_planar_clip")
        self.assertEqual(result["stats"]["planar_patches"], 4)
        self.assertEqual(result["stats"]["bad_edges_before_weld"], 0)
        self.assertLess(result["stats"]["max_facet_plane_error_mm"], 1e-10)
        strips = geometry._planar_strips(carriers, payload["bounds"], 300)
        nominal = []
        for row in (0, 1):
            for cell in geometry._lattice_cell(row, 0, 12.5, 15, [0, 0]):
                apex = (sum(p[0] for p in cell)/3, sum(p[1] for p in cell)/3, 1.5)
                for i in range(3):
                    nominal.append(geometry._unit(geometry._cross3(
                        geometry._sub(cell[(i+1)%3], cell[i]), geometry._sub(apex, cell[i]))))
        # Every clipped facet has the same inclination as a nominal pyramid,
        # including facets at the tapered edges. No miter or atlas stretching.
        for strip, patch in zip(strips, result["planar_patches"]):
            n = strip["normal"]
            u = geometry._unit(geometry._sub(strip["corners"][2], strip["corners"][0]))
            v = geometry._unit(geometry._cross3(n, u))
            for f in result["faces"][patch["face_start"]:patch["outer_face_end"]]:
                a, b, c = (result["vertices"][i] for i in f)
                normal = geometry._unit(geometry._cross3(geometry._sub(b, a), geometry._sub(c, a)))
                local = [geometry._dot(normal, axis) for axis in (u, v, n)]
                self.assertGreater(max(geometry._dot(local, expect) for expect in nominal), 1-1e-9)
        # Rotating the physical carrier must rotate the result, not change topology.
        # Vertices are shared in this fixture; rotate each only once.
        unique = {id(v): v for t in carriers for v in t["v"]}
        for vertex in unique.values():
            vertex["p"] = [vertex["p"][2], vertex["p"][0], vertex["p"][1]]
            vertex["n"] = [vertex["n"][2], vertex["n"][0], vertex["n"][1]]
        rotated = geometry.build(payload, {"resolution": 3,
                                           "diamond_height": 15,
                                           "diamond_side": 12.5})
        self.assertEqual(result["faces"], rotated["faces"])
        for p, q in zip(result["vertices"], rotated["vertices"]):
            for a, b in zip((p[2], p[0], p[1]), q):
                self.assertAlmostEqual(a, b)

    def test_cylinder_has_no_seam_caps_or_duplicate_vertices(self):
        carriers = []
        period = 24.0
        def vertex(i, z):
            angle = 2 * math.pi * i / 48
            return {"q": [period * i / 48, z],
                    "p": [10 * math.cos(angle), 10 * math.sin(angle), z],
                    "n": [math.cos(angle), math.sin(angle), 0]}
        for i in range(48):
            a, b, c, d = vertex(i, 0), vertex(i+1, 0), vertex(i, 8), vertex(i+1, 8)
            carriers.extend([{"v": [a, b, c]}, {"v": [b, d, c]}])
        data = geometry.build({"carrier_triangles": carriers, "bounds": [0, period, 0, 8],
                               "grid": {"column_width": 4, "row_height": 4, "origin": [0, 0]},
                               "periodic_adjustments": [{"axis": 0, "period": period, "lower": 0}]},
                              {"resolution": 4, "pyramid_height": 1,
                               "diamond_height": 4, "diamond_side": 4})
        self.assertEqual(data["stats"]["bad_edges_before_weld"], 0)
        points = [tuple(round(v, 6) for v in p) for p in data["vertices"]]
        self.assertEqual(len(points), len(set(points)))
        # All side walls must lie on the top/bottom rims, never at the seam.
        for face in data["faces"]:
            if len(face) == 4:
                zs = [data["vertices"][i][2] for i in face]
                self.assertLess(max(zs) - min(zs), 1e-6)

    def test_requested_diamond_size_is_independent_of_map_preview_grid(self):
        payload = {"grid": {"column_width": 3, "row_height": 5},
                   "bounds": [0, 20, 0, 20]}
        dim = geometry.dimensions(payload, {"diamond_height": 12,
                                            "pyramid_height": 1})
        self.assertAlmostEqual(12, dim["row_height"])
        self.assertAlmostEqual(24 / math.sqrt(3), dim["side"])



if __name__ == "__main__":
    unittest.main()
