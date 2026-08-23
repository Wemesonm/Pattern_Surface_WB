"""Stable identifiers for the active workbench and legacy aliases."""

SCHEMA = "AUZYRON_MAP_V1"
LEGACY_SCHEMAS = ("WRAP_CARRIER_V4",)
SUPPORTED_SCHEMAS = (SCHEMA,) + LEGACY_SCHEMAS

WRAP_PREFIX = "MappedSurface"
FULL_PREFIX = "DiamondPattern"
CUT_PREFIX = "TrimmedPattern"

MAP_LABEL = "Mapped Surface"
CARRIER_LABEL = "Mapping Grid"
PATTERN_LABEL = "Diamond Pattern"
TRIM_LABEL = "Trimmed Pattern"


def is_supported_schema(value):
    return value in SUPPORTED_SCHEMAS


def short_label(label, name):
    suffix = name.rsplit("_", 1)[-1]
    return "{} {}".format(label, suffix) if suffix.isdigit() else label
