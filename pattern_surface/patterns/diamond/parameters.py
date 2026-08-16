import FreeCAD as App

from .metadata import (
    DEFAULT_DIAMOND_HEIGHT,
    DEFAULT_PYRAMID_HEIGHT,
    MAX_DIAMOND_HEIGHT,
    MAX_PYRAMID_HEIGHT,
    MIN_DIAMOND_HEIGHT,
    MIN_PYRAMID_HEIGHT,
)


PREFERENCE_PATH = "User parameter:BaseApp/Preferences/Mod/Pattern_Surface_WB/Patterns/Diamond"
PREFERENCE_KEY = "LastHeight"
DIAMOND_HEIGHT_KEY = "LastDiamondHeight"
PYRAMID_HEIGHT_KEY = "LastPyramidHeight"


def preferences():
    return App.ParamGet(PREFERENCE_PATH)


def last_diamond_height():
    return max(MIN_DIAMOND_HEIGHT,
               preferences().GetFloat(DIAMOND_HEIGHT_KEY, DEFAULT_DIAMOND_HEIGHT))


def last_pyramid_height():
    legacy = preferences().GetFloat(PREFERENCE_KEY, DEFAULT_PYRAMID_HEIGHT)
    return max(MIN_PYRAMID_HEIGHT,
               preferences().GetFloat(PYRAMID_HEIGHT_KEY, legacy))


def save_heights(diamond_height, pyramid_height):
    preferences().SetFloat(DIAMOND_HEIGHT_KEY, float(diamond_height))
    preferences().SetFloat(PYRAMID_HEIGHT_KEY, float(pyramid_height))
    preferences().SetFloat(PREFERENCE_KEY, float(pyramid_height))


def get_parameters():
    from PySide import QtGui
    try:
        from PySide import QtWidgets
    except ImportError:
        QtWidgets = QtGui

    dialog = QtWidgets.QDialog()
    dialog.setWindowTitle("Diamond Pattern")
    layout = QtWidgets.QFormLayout(dialog)

    diamond_height = QtWidgets.QDoubleSpinBox(dialog)
    diamond_height.setRange(MIN_DIAMOND_HEIGHT, MAX_DIAMOND_HEIGHT)
    diamond_height.setDecimals(3)
    diamond_height.setSuffix(" mm")
    diamond_height.setValue(last_diamond_height())
    layout.addRow("Diamond height:", diamond_height)

    pyramid_height = QtWidgets.QDoubleSpinBox(dialog)
    pyramid_height.setRange(MIN_PYRAMID_HEIGHT, MAX_PYRAMID_HEIGHT)
    pyramid_height.setDecimals(3)
    pyramid_height.setSuffix(" mm")
    pyramid_height.setValue(last_pyramid_height())
    layout.addRow("Pyramid height:", pyramid_height)

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
        parent=dialog,
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return None
    diamond_value = float(diamond_height.value())
    pyramid_value = float(pyramid_height.value())
    save_heights(diamond_value, pyramid_value)
    return {
        "diamond_height": diamond_value,
        "pyramid_height": pyramid_value,
        "height": pyramid_value,
    }
