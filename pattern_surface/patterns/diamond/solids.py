import importlib

from ...compatibility import v4_pipeline


def create_pattern(map_object, parameters):
    del map_object  # Selection remains authoritative during V4 compatibility.
    module = importlib.reload(v4_pipeline)
    return module.run_guard(
        lambda: module.create_full_pattern(height=parameters["height"]),
        "Diamond Pattern",
    )
