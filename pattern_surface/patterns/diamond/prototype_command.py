import FreeCADGui as Gui

from ...common.runtime import maybe_reload
from . import parameters, solids


def run():
    maybe_reload(parameters)
    selected = Gui.Selection.getSelection()
    map_object = selected[0] if selected else None
    values = parameters.get_prototype_parameters(map_object)
    if values is None:
        return None
    maybe_reload(solids)
    fit = solids.analyze_prototype_closure_fit(map_object, values)
    if not fit.get("compatible", True):
        parameters.show_closure_incompatible(fit)
        return None
    if fit.get("adjusted") and not parameters.confirm_closure_fit(fit):
        return None
    result = solids.create_prototype_pattern(map_object, values)
    if result is not None:
        parameters.save_parameters(
            values["diamond_height"], values["pyramid_height"],
            values["closure_fit_tolerance"], values["curved_relief_factor"],
            values["cell_gap"], values["cell_gap_x"], values["cell_gap_y"],
        )
    return result
