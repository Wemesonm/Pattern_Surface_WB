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
        "pattern_id": "boleado",
        "label": "Boleado Pattern",
        "command_id": "PatternSurface_Pattern_Boleado",
        "icon": os.path.join(root, "resources", "icons", "boleado.svg"),
    }), validate_descriptor({
        "pattern_id": "diamond_prototype",
        "label": "Diamond Pattern Prototype",
        "command_id": "PatternSurface_Pattern_DiamondPrototype",
        "icon": os.path.join(root, "resources", "icons", "diamond.svg"),
    }), validate_descriptor({
        "pattern_id": "diamond_prototype_v2",
        "label": "Diamond Pattern Prototype V2",
        "command_id": "PatternSurface_Pattern_DiamondPrototypeV2",
        "icon": os.path.join(root, "resources", "icons", "diamond.svg"),
    })]


def get(pattern_id):
    for descriptor in patterns():
        if descriptor["pattern_id"] == pattern_id:
            return descriptor
    raise KeyError(pattern_id)
