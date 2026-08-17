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
    fit = solids.analyze_closure_fit(map_object, values)
    if not fit.get("compatible", True):
        parameters.show_closure_incompatible(fit)
        return None
    if fit.get("adjusted") and not parameters.confirm_closure_fit(fit):
        return None
    result = solids.create_pattern(map_object, values)
    if result is not None:
        parameters.save_parameters(
            values["diamond_height"],
            values["pyramid_height"],
            values["closure_fit_tolerance"],
        )
    return result
