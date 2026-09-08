import FreeCADGui as Gui

from ... import core_engine
from ...common.runtime import maybe_reload
from . import engine, parameters


def run():
    selected = Gui.Selection.getSelection()
    map_object = selected[0] if selected else None
    values = parameters.get_parameters()
    if values is None:
        return None
    module = maybe_reload(engine)
    return core_engine.run_guard(
        lambda: module.create_pattern(map_object, values), "Boleado Pattern")
