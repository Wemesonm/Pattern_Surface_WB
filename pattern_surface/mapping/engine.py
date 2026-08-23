"""Map Faces execution boundary.

The shared geometry engine is an internal implementation detail; this
boundary exposes only the Map Faces entry point to the mapping service.
Diamond and Trim commands do not import this module.
"""

from .. import core_engine
from ..common.runtime import maybe_reload


def create_map(column_width, row_height, closure_tolerance):
    module = maybe_reload(core_engine)
    return module.create_wrap(
        column_width=column_width,
        row_height=row_height,
        closure_tolerance=closure_tolerance,
    )
