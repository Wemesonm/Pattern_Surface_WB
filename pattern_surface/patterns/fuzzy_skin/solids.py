import math

import FreeCAD as App
import FreeCADGui as Gui
import Part

from ...common.properties_core import add_length, add_string, next_name
from ...common.serialization import add_chunks, load_chunks
from ...common.identifiers import short_label
from .metadata import LABEL, PATTERN_ID


def _map_object(doc):
    selected = list(Gui.Selection.getSelection())
    for obj in selected:
        if "MapPayloadChunks" in getattr(obj, "PropertiesList", []):
            return obj
        parent_name = (getattr(obj, "MapParentRun", "") or
                       getattr(obj, "WrapParentRun", ""))
        if parent_name:
            parent = doc.getObject(parent_name)
            if parent is not None:
                return parent
    return None


def _noise(point, feature_size, variation, seed):
    # Stable value noise in physical space keeps periodic seam vertices welded.
    scale = max(feature_size, 1.0e-9)
    x, y, z = (float(value) / scale for value in point)
    value = math.sin(x * 127.1 + y * 311.7 + z * 91.7 + seed * 74.3) * 43758.5453
    unit = value - math.floor(value)
    return (1.0 - variation) + variation * unit


def _vertex(vertex, depth, feature_size, variation, seed):
    point = App.Vector(*[float(value) for value in vertex["p"]])
    normal = App.Vector(*[float(value) for value in vertex.get("n", [0.0, 0.0, 1.0])])
    if normal.Length <= 1.0e-12:
        return point
    normal.normalize()
    amount = depth * _noise(vertex["p"], feature_size, variation, seed)
    return point + normal * amount


def _point_key(point):
    return tuple(round(float(value), 7) for value in point)


def _closed_surface_layer(triangles, parameters):
    """Build one watertight thin layer from the carrier topology."""
    vertices = {}
    edges = {}
    triangle_keys = []
    for triangle in triangles:
        source = triangle.get("v", [])
        if len(source) != 3:
            continue
        keys = []
        for vertex in source:
            key = _point_key(vertex["p"])
            if key not in vertices:
                vertices[key] = {
                    "base": App.Vector(*[float(value) for value in vertex["p"]]),
                    "top": _vertex(vertex, parameters["depth"],
                                   parameters["feature_size"],
                                   parameters["variation"], parameters["seed"]),
                }
            keys.append(key)
        triangle_keys.append(keys)
        for start, end in ((keys[0], keys[1]), (keys[1], keys[2]), (keys[2], keys[0])):
            edge = tuple(sorted((start, end)))
            edges[edge] = edges.get(edge, 0) + 1

    top_faces = []
    bottom_faces = []
    for keys in triangle_keys:
        top = [vertices[key]["top"] for key in keys]
        bottom = [vertices[key]["base"] for key in reversed(keys)]
        top_wire = Part.makePolygon(top + [top[0]])
        bottom_wire = Part.makePolygon(bottom + [bottom[0]])
        top_face = Part.Face(top_wire)
        bottom_face = Part.Face(bottom_wire)
        if top_face.isNull() or bottom_face.isNull():
            continue
        top_faces.append(top_face)
        bottom_faces.append(bottom_face)

    side_faces = []
    for (start, end), count in edges.items():
        if count != 1:
            continue
        base_start = vertices[start]["base"]
        base_end = vertices[end]["base"]
        top_start = vertices[start]["top"]
        top_end = vertices[end]["top"]
        wire = Part.makePolygon([base_start, base_end, top_end, top_start, base_start])
        face = Part.Face(wire)
        if not face.isNull():
            side_faces.append(face)

    faces = top_faces + bottom_faces + side_faces
    if not faces:
        return None, 0
    try:
        shell = Part.makeShell(faces)
        if shell.isNull() or not shell.isClosed():
            return None, len(faces)
        solid = Part.makeSolid(shell)
        if solid.isNull() or not solid.isValid() or len(solid.Solids) != 1:
            return None, len(faces)
        return solid, len(faces)
    except Exception:
        return None, len(faces)


def create_pattern(parameters):
    doc = App.ActiveDocument
    if doc is None:
        raise RuntimeError("Abra um documento antes de executar o Fuzzy Skin Pattern.")
    map_object = _map_object(doc)
    if map_object is None:
        raise RuntimeError("Selecione um objeto Map Faces ou seu preview.")
    payload = load_chunks(map_object, "MapPayloadChunks")
    triangles = payload.get("carrier_triangles") or payload.get("triangles") or []
    if not triangles:
        raise RuntimeError("O mapa selecionado nao possui carrier fisico.")

    selected_triangles = []
    cells = []
    for index, triangle in enumerate(triangles):
        vertices = triangle.get("v", [])
        if len(vertices) != 3:
            continue
        selected_triangles.append(triangle)
        cells.append({"id": index, "carrier": triangle.get("id", index)})

    solid, face_count = _closed_surface_layer(selected_triangles, parameters)
    if solid is None:
        raise RuntimeError(
            "O Fuzzy Skin nao formou uma camada fechada valida. "
            "Faces analisadas: {}.".format(face_count))
    name = next_name(doc, "FuzzySkinPattern")
    result = doc.addObject("PartDesign::Feature", name)
    result.Label = short_label(LABEL, name)
    result.Shape = solid
    add_string(result, "PatternId", PATTERN_ID, "Pattern Surface")
    add_string(result, "PatternMapSource", map_object.Name, "Pattern Surface")
    add_length(result, "PatternHeight", parameters["depth"], "Pattern Surface")
    add_length(result, "FuzzyDepth", parameters["depth"], "Fuzzy Skin Pattern")
    add_length(result, "FuzzyFeatureSize", parameters["feature_size"], "Fuzzy Skin Pattern")
    add_chunks(result, "FuzzyPatternPayloadChunks", {
        "schema": "PATTERN_SURFACE_FUZZY",
        "version": 1,
        "pattern_id": PATTERN_ID,
        "map_source": map_object.Name,
        "parameters": dict(parameters),
        "cells": cells,
        "generation": {"representation": "closed_displaced_surface_layer",
                        "face_count": face_count},
    }, "Fuzzy Skin Pattern")
    doc.recompute()
    return result
