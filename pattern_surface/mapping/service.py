import importlib

from ..compatibility import v4_pipeline
from ..version import BUILD_ID


def engine():
    module = importlib.reload(v4_pipeline)
    module.BUILD_ID = BUILD_ID
    return module


def create_map():
    module = engine()
    return module.run_guard(module.create_wrap, "Map Faces")
