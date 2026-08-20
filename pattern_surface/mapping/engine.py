"""Map Faces execution boundary.

The V4 compatibility module remains the temporary implementation source, but
this boundary exposes only the Map Faces entry point to the mapping service.
Diamond and Trim commands do not import this module.
"""

from ..compatibility import v4_pipeline
from ..common.runtime import maybe_reload


def create_map(column_width, row_height, closure_tolerance):
    module = maybe_reload(v4_pipeline)
    return module.create_wrap(
        column_width=column_width,
        row_height=row_height,
        closure_tolerance=closure_tolerance,
    )
