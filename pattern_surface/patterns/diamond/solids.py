import importlib

from ... import core_engine
from ... import prototype_engine
from ...common.runtime import maybe_reload
from ...common.ownership import map_from_selection_object


def _map_run(map_object):
    return map_from_selection_object(map_object)


def analyze_closure_fit(map_object, parameters):
    module = maybe_reload(core_engine)
    run = _map_run(map_object)
    if run is None:
        return {"adjusted": False}
    payload = module.load_chunks(run, "MapPayloadChunks")
    return module.periodic_diamond_fit(
        payload,
        parameters["diamond_height"],
        parameters["closure_fit_tolerance"],
    )


def analyze_prototype_closure_fit(map_object, parameters):
    module = maybe_reload(prototype_engine)
    run = _map_run(map_object)
    if run is None:
        return {"adjusted": False}
    payload = module.load_chunks(run, "MapPayloadChunks")
    return module.periodic_diamond_fit(
        payload, parameters["diamond_height"],
        parameters["closure_fit_tolerance"],
    )


def create_pattern(map_object, parameters):
    del map_object  # Selection remains authoritative during shared geometry engine.
    # The FreeCAD console keeps imported modules alive between command runs.
    # Reload the engine here so a newly installed parameter contract is used
    # without requiring a full FreeCAD restart.
    module = importlib.reload(core_engine)
    return module.run_guard(
        lambda: module.create_full_pattern(
            height=parameters["pyramid_height"],
            diamond_height=parameters["diamond_height"],
            closure_fit_tolerance=parameters["closure_fit_tolerance"],
        ),
        "Diamond Pattern",
    )


def create_prototype_pattern(map_object, parameters):
    del map_object
    module = importlib.reload(prototype_engine)
    result = module.run_guard(
        lambda: module.create_full_pattern(
            height=parameters["pyramid_height"],
            diamond_height=parameters["diamond_height"],
            closure_fit_tolerance=parameters["closure_fit_tolerance"],
            curved_relief_factor=parameters["curved_relief_factor"],
            cell_gap=parameters["cell_gap"],
            cell_gap_x=parameters["cell_gap_x"],
            cell_gap_y=parameters["cell_gap_y"],
            variant="Diamond Pattern Prototype",
        ),
        "Diamond Pattern Prototype",
    )
    if result is not None:
        result.Label = result.Label.replace("Diamond Pattern", "Diamond Pattern Prototype")
        if "PatternId" in getattr(result, "PropertiesList", []):
            result.PatternId = "diamond_prototype"
        if "DiamondPatternVersion" in getattr(result, "PropertiesList", []):
            result.DiamondPatternVersion = "Diamond Pattern Prototype"
    return result
