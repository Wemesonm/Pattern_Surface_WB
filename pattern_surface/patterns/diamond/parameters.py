import FreeCAD as App

from .metadata import DEFAULT_HEIGHT, MAX_HEIGHT, MIN_HEIGHT


PREFERENCE_PATH = "User parameter:BaseApp/Preferences/Mod/Pattern_Surface_WB/Patterns/Diamond"
PREFERENCE_KEY = "LastHeight"


def preferences():
    return App.ParamGet(PREFERENCE_PATH)


def last_height():
    return max(MIN_HEIGHT, preferences().GetFloat(PREFERENCE_KEY, DEFAULT_HEIGHT))


def save_height(height):
    preferences().SetFloat(PREFERENCE_KEY, float(height))


def get_parameters():
    from PySide import QtGui

    height, accepted = QtGui.QInputDialog.getDouble(
        None,
        "Diamond Pattern",
        "Triangle height (mm):",
        last_height(),
        MIN_HEIGHT,
        MAX_HEIGHT,
        3,
    )
    if not accepted:
        return None
    save_height(height)
    return {"height": float(height)}
