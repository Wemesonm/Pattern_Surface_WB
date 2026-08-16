import os


PATTERN_ID = "diamond"
LABEL = "Diamond Pattern"
ICON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources", "icons", "diamond.svg")
DEFAULT_DIAMOND_HEIGHT = 12.0
MIN_DIAMOND_HEIGHT = 0.01
MAX_DIAMOND_HEIGHT = 1000.0
DEFAULT_PYRAMID_HEIGHT = 1.0
MIN_PYRAMID_HEIGHT = 0.01
MAX_PYRAMID_HEIGHT = 1000.0

# Compatibility aliases for callers written before the two dimensions were
# exposed separately.
DEFAULT_HEIGHT = DEFAULT_PYRAMID_HEIGHT
MIN_HEIGHT = MIN_PYRAMID_HEIGHT
MAX_HEIGHT = MAX_PYRAMID_HEIGHT
