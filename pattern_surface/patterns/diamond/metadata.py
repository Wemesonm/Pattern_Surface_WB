import os


PATTERN_ID = "diamond"
LABEL = "Diamond Pattern"
ICON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources", "icons", "diamond.svg")
DEFAULT_HEIGHT = 1.0
MIN_HEIGHT = 0.01
MAX_HEIGHT = 1000.0
