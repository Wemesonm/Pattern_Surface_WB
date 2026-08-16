import importlib

import FreeCADGui as Gui

from . import parameters, solids


def run():
    importlib.reload(parameters)
    values = parameters.get_parameters()
    if values is None:
        return None
    selected = Gui.Selection.getSelection()
    map_object = selected[0] if selected else None
    importlib.reload(solids)
    return solids.create_pattern(map_object, values)
