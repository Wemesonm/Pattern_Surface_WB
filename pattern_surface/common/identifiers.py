"""Stable internal identifiers and user-facing labels."""

SCHEMA = "WRAP_CARRIER_V4"
WRAP_PREFIX = "DiamondSurfaceWrap_V4"
FULL_PREFIX = "DiamondPatternFullFromWrap_V4"
CUT_PREFIX = "DiamondPatternCutFromWrap_V4"

MAP_LABEL = "Mapped Surface"
CARRIER_LABEL = "Mapping Grid"
PATTERN_LABEL = "Diamond Pattern"
TRIM_LABEL = "Trimmed Pattern"


def short_label(label, name):
    """Return a short stable label while retaining legacy object names."""
    suffix = name.rsplit("_", 1)[-1]
    return "{} {}".format(label, suffix) if suffix.isdigit() else label
