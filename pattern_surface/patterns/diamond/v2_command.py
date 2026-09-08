"""Command adapter for Diamond Pattern Prototype V2."""

import importlib

import FreeCADGui as Gui

from . import v2_engine, v2_parameters


def run():
    selected = Gui.Selection.getSelection()
    map_object = selected[0] if selected else None
    values = v2_parameters.get_parameters()
    if values is None:
        return None
    # V2 is an isolated experiment and must pick up source changes on every
    # explicit run, even when FreeCAD has kept the workbench module cached.
    engine = importlib.reload(v2_engine)
    return engine.create_pattern(map_object, values)
