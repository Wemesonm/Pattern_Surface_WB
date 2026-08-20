from ..compatibility import v4_pipeline
from ..common.runtime import maybe_reload


def trim_pattern():
    module = maybe_reload(v4_pipeline)
    return module.run_guard(module.create_cut, "Trim Surface")
