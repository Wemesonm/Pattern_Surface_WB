"""Tool-neutral contracts shared by Map Faces and downstream tools."""

from dataclasses import dataclass
import math


DEFAULT_MAP_COLUMN_WIDTH = 13.85640646055102
DEFAULT_MAP_ROW_HEIGHT = 12.0
DEFAULT_MAP_CLOSURE_TOLERANCE = 0.05
MIN_GRID_LENGTH = 0.01


@dataclass(frozen=True)
class GridSpec:
    """The generic orthogonal coordinate system produced by Map Faces."""

    column_width: float = DEFAULT_MAP_COLUMN_WIDTH
    row_height: float = DEFAULT_MAP_ROW_HEIGHT
    closure_tolerance: float = DEFAULT_MAP_CLOSURE_TOLERANCE

    def validate(self):
        values = {
            "Column width": self.column_width,
            "Row height": self.row_height,
            "Closure tolerance": self.closure_tolerance,
        }
        for label, value in values.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                raise ValueError(
                    "{} must be a finite positive length.".format(label))
            if not math.isfinite(numeric) or numeric <= 0.0:
                raise ValueError(
                    "{} must be a finite positive length.".format(label))
        return GridSpec(float(self.column_width), float(self.row_height),
                        float(self.closure_tolerance))


def map_grid_spec(column_width=None, row_height=None, closure_tolerance=None):
    """Build and validate a map contract without importing FreeCAD."""
    return GridSpec(
        DEFAULT_MAP_COLUMN_WIDTH if column_width is None else column_width,
        DEFAULT_MAP_ROW_HEIGHT if row_height is None else row_height,
        DEFAULT_MAP_CLOSURE_TOLERANCE if closure_tolerance is None
        else closure_tolerance,
    ).validate()
