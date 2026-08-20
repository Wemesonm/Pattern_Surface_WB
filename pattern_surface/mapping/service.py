from ..compatibility import v4_pipeline
from ..common.runtime import maybe_reload
from ..version import BUILD_ID
from . import parameters


def engine():
    module = maybe_reload(v4_pipeline)
    module.BUILD_ID = BUILD_ID
    return module


def create_map(options=None):
    if options is None:
        maybe_reload(parameters)
        options = parameters.get_parameters()
    if options is None:
        return None
    module = engine()
    return module.run_guard(lambda: module.create_wrap(**options), "Map Faces")
