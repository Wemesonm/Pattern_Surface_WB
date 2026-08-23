import os


PATTERN_ID = "fuzzy_skin"
LABEL = "Fuzzy Skin Pattern"
ICON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources", "icons", "fuzzy_skin.svg")
DEFAULT_DEPTH = 0.20
MIN_DEPTH = 0.01
MAX_DEPTH = 5.0
DEFAULT_FEATURE_SIZE = 1.0
MIN_FEATURE_SIZE = 0.05
MAX_FEATURE_SIZE = 100.0
DEFAULT_VARIATION = 0.50
DEFAULT_SEED = 1

