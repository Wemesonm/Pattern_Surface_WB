import os


PATTERN_ID = "boleado"
LABEL = "Boleado Pattern"
ICON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources", "icons", "boleado.svg")

DEFAULT_BUMP_RADIUS = 2.5
# Kept for compatibility with saved preferences; hemisphere height equals radius.
DEFAULT_BUMP_HEIGHT = DEFAULT_BUMP_RADIUS
DEFAULT_SPACING_X = 5.0
DEFAULT_SPACING_Y = 5.0
DEFAULT_ROW_OFFSET = 0.5
DEFAULT_PENETRATION = 0.05
MIN_LENGTH = 0.01
MAX_LENGTH = 1000.0
MAX_ROW_OFFSET = 1.0
