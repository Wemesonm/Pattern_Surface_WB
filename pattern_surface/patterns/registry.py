import os

from .base import validate_descriptor


def patterns():
    root = os.path.dirname(os.path.dirname(__file__))
    return [validate_descriptor({
        "pattern_id": "diamond",
        "label": "Diamond Pattern",
        "command_id": "PatternSurface_Pattern_Diamond",
        "icon": os.path.join(root, "resources", "icons", "diamond.svg"),
    }), validate_descriptor({
        "pattern_id": "fuzzy_skin",
        "label": "Fuzzy Skin Pattern",
        "command_id": "PatternSurface_Pattern_FuzzySkin",
        "icon": os.path.join(root, "resources", "icons", "fuzzy_skin.svg"),
    })]


def get(pattern_id):
    for descriptor in patterns():
        if descriptor["pattern_id"] == pattern_id:
            return descriptor
    raise KeyError(pattern_id)
