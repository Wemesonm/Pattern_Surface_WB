from ..common.runtime import maybe_reload
from ..version import BUILD_ID
from . import engine as map_engine
from . import parameters


def compatibility_engine():
    from ..compatibility import v4_pipeline
    module = maybe_reload(v4_pipeline)
    module.BUILD_ID = BUILD_ID
    return module


def create_map(options=None):
    if options is None:
        maybe_reload(parameters)
        options = parameters.get_parameters()
    if options is None:
        return None
    module = compatibility_engine()
    return module.run_guard(
        lambda: map_engine.create_map(**options), "Map Faces")
