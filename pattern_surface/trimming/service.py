import importlib

from ..compatibility import v4_pipeline


def trim_pattern():
    module = importlib.reload(v4_pipeline)
    return module.run_guard(module.create_cut, "Trim Surface")
