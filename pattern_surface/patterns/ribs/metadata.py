import os


PATTERN_ID = "diagonal_ribs"
LABEL = "Diagonal Ribs"
ICON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources", "icons", "ribs.svg")

DEFAULT_PITCH = 12.0
DEFAULT_HEIGHT = 1.5
DEFAULT_ANGLE = 45.0
MIN_LENGTH = 0.01
MAX_LENGTH = 1000.0
MIN_ANGLE = -89.0
MAX_ANGLE = 89.0
DEFAULT_RESOLUTION = 8
MIN_RESOLUTION = 3
MAX_RESOLUTION = 32
