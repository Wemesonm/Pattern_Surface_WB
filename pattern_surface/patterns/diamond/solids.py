import importlib

from ...compatibility import v4_pipeline


def _map_run(map_object):
    if map_object is None:
        return None
    if "MapPayloadChunks" in getattr(map_object, "PropertiesList", []):
        return map_object
    document = getattr(map_object, "Document", None)
    parent_name = (getattr(map_object, "MapParentRun", "") or
                   getattr(map_object, "WrapParentRun", ""))
    return document.getObject(parent_name) if document is not None and parent_name else None


def analyze_closure_fit(map_object, parameters):
    module = importlib.reload(v4_pipeline)
    run = _map_run(map_object)
    if run is None:
        return {"adjusted": False}
    payload = module.load_chunks(run, "MapPayloadChunks")
    return module.periodic_diamond_fit(
        payload,
        parameters["diamond_height"],
        parameters["closure_fit_tolerance"],
    )


def create_pattern(map_object, parameters):
    del map_object  # Selection remains authoritative during V4 compatibility.
    module = importlib.reload(v4_pipeline)
    return module.run_guard(
        lambda: module.create_full_pattern(
            height=parameters["pyramid_height"],
            diamond_height=parameters["diamond_height"],
            closure_fit_tolerance=parameters["closure_fit_tolerance"],
        ),
        "Diamond Pattern",
    )
