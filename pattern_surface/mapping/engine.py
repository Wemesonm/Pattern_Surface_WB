"""Map Faces execution boundary.

The shared geometry engine is an internal implementation detail; this
boundary exposes only the Map Faces entry point to the mapping service.
Diamond and Trim commands do not import this module.
"""

from .. import core_engine
from ..common.runtime import maybe_reload
from ..common.contracts import DEFAULT_MAP_CLOSURE_TOLERANCE


def create_map(column_count=None, row_count=None,
               closure_tolerance=DEFAULT_MAP_CLOSURE_TOLERANCE,
               column_width=None, row_height=None):
    module = maybe_reload(core_engine)
    spacing = {}
    if column_width is not None:
        spacing["column_width"] = column_width
    if row_height is not None:
        spacing["row_height"] = row_height
    return module.create_wrap(
        **spacing,
        column_count=column_count,
        row_count=row_count,
        closure_tolerance=closure_tolerance,
    )
