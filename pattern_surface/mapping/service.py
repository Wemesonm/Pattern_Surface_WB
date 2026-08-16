import importlib

from ..compatibility import v4_pipeline
from ..version import BUILD_ID
from . import parameters


def engine():
    module = importlib.reload(v4_pipeline)
    module.BUILD_ID = BUILD_ID
    return module


def create_map(options=None):
    if options is None:
        importlib.reload(parameters)
        options = parameters.get_parameters()
    if options is None:
        return None
    module = engine()
    return module.run_guard(lambda: module.create_wrap(**options), "Map Faces")
