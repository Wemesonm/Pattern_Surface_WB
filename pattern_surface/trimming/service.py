from .. import core_engine
from ..common.runtime import maybe_reload


def trim_pattern():
    module = maybe_reload(core_engine)
    return module.run_guard(module.create_cut, "Trim Surface")
