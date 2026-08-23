import math

import FreeCAD as App
import FreeCADGui as Gui
import Part

from ...common.properties_core import add_chunks, add_length, add_string, next_name
from ...common.serialization import load_chunks
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


def _noise(q, feature_size, variation, seed):
    # Stable value noise: identical logical vertices remain welded across
    # neighboring carrier triangles and the seed is persisted in the payload.
    x = q[0] / max(feature_size, 1.0e-9)
    y = q[1] / max(feature_size, 1.0e-9)
    value = math.sin(x * 127.1 + y * 311.7 + seed * 74.3) * 43758.5453
    unit = value - math.floor(value)
    return (1.0 - variation) + variation * unit


def _vertex(vertex, depth, feature_size, variation, seed):
    point = App.Vector(*[float(value) for value in vertex["p"]])
    normal = App.Vector(*[float(value) for value in vertex.get("n", [0.0, 0.0, 1.0])])
    if normal.Length <= 1.0e-12:
        return point
    normal.normalize()
    amount = depth * _noise(vertex.get("q", [0.0, 0.0]), feature_size, variation, seed)
    return point + normal * amount


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

    faces = []
    cells = []
    for index, triangle in enumerate(triangles):
        vertices = triangle.get("v", [])
        if len(vertices) != 3:
            continue
        points = [_vertex(item, parameters["depth"], parameters["feature_size"],
                          parameters["variation"], parameters["seed"])
                  for item in vertices]
        try:
            wire = Part.makePolygon(points + [points[0]])
            face = Part.Face(wire)
        except Exception:
            continue
        if face.isNull():
            continue
        faces.append(face)
        cells.append({"id": index, "carrier": triangle.get("id", index)})

    if not faces:
        raise RuntimeError("O Fuzzy Skin Pattern nao gerou faces validas.")
    name = next_name(doc, "FuzzySkinPattern")
    result = doc.addObject("PartDesign::Feature", name)
    result.Label = short_label(LABEL, name)
    result.Shape = Part.makeCompound(faces)
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
        "generation": {"representation": "displaced_carrier_surface"},
    }, "Fuzzy Skin Pattern")
    doc.recompute()
    return result
