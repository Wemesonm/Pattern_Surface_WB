import FreeCAD as App

from ..common.contracts import (
    DEFAULT_MAP_CLOSURE_TOLERANCE,
    DEFAULT_MAP_COLUMN_WIDTH,
    DEFAULT_MAP_ROW_HEIGHT,
)


PREFERENCE_PATH = "User parameter:BaseApp/Preferences/Mod/Auzyron_Patterns_WB/MapFaces"
LEGACY_PREFERENCE_PATH = "User parameter:BaseApp/Preferences/Mod/Pattern_Surface_WB/MapFaces"
COLUMN_WIDTH_KEY = "LastColumnWidth"
ROW_HEIGHT_KEY = "LastRowHeight"
COLUMN_COUNT_KEY = "LastColumnCount"
ROW_COUNT_KEY = "LastRowCount"
CLOSURE_TOLERANCE_KEY = "LastClosureTolerance"

DEFAULT_COLUMN_WIDTH = DEFAULT_MAP_COLUMN_WIDTH
DEFAULT_ROW_HEIGHT = DEFAULT_MAP_ROW_HEIGHT
DEFAULT_CLOSURE_TOLERANCE = DEFAULT_MAP_CLOSURE_TOLERANCE
MIN_LENGTH = 0.01
MAX_LENGTH = 100000.0
MIN_COUNT = 1
MAX_COUNT = 100000


def preferences():
    return App.ParamGet(PREFERENCE_PATH)


def legacy_preferences():
    return App.ParamGet(LEGACY_PREFERENCE_PATH)


def stored_float(key, default):
    value = preferences().GetFloat(key, -1.0)
    if value >= 0.0:
        return value
    return legacy_preferences().GetFloat(key, default)


def stored_int(key, default):
    value = preferences().GetInt(key, -1)
    if value >= 0:
        return value
    return legacy_preferences().GetInt(key, default)


def last_values():
    return {
        "column_count": max(MIN_COUNT, stored_int(COLUMN_COUNT_KEY, 24)),
        "row_count": max(MIN_COUNT, stored_int(ROW_COUNT_KEY, 4)),
        "column_width": max(
            MIN_LENGTH, stored_float(COLUMN_WIDTH_KEY, DEFAULT_COLUMN_WIDTH)),
        "row_height": max(
            MIN_LENGTH, stored_float(ROW_HEIGHT_KEY, DEFAULT_ROW_HEIGHT)),
        "closure_tolerance": max(
            MIN_LENGTH, stored_float(CLOSURE_TOLERANCE_KEY,
                                     DEFAULT_CLOSURE_TOLERANCE)),
    }


def save_values(column_width, row_height, closure_tolerance):
    store = preferences()
    store.SetFloat(COLUMN_WIDTH_KEY, float(column_width))
    store.SetFloat(ROW_HEIGHT_KEY, float(row_height))
    store.SetFloat(CLOSURE_TOLERANCE_KEY, float(closure_tolerance))


def save_counts(column_count, row_count):
    store = preferences()
    store.SetInt(COLUMN_COUNT_KEY, int(column_count))
    store.SetInt(ROW_COUNT_KEY, int(row_count))


def get_parameters():
    from PySide import QtGui
    try:
        from PySide import QtWidgets
    except ImportError:
        QtWidgets = QtGui

    values = last_values()
    dialog = QtWidgets.QDialog()
    dialog.setWindowTitle("Map Faces")
    layout = QtWidgets.QFormLayout(dialog)

    explanation = QtWidgets.QLabel(
        "Select the source faces to create a generic map.\n"
        "Pattern size is chosen in the pattern command.")
    layout.addRow(explanation)

    closure_tolerance = QtWidgets.QDoubleSpinBox(dialog)
    closure_tolerance.setRange(MIN_LENGTH, MAX_LENGTH)
    closure_tolerance.setDecimals(3)
    closure_tolerance.setSuffix(" mm")
    closure_tolerance.setValue(values["closure_tolerance"])
    layout.addRow("Closure tolerance:", closure_tolerance)

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
        parent=dialog,
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return None

    result = {
        "column_width": values["column_width"],
        "row_height": values["row_height"],
        "closure_tolerance": float(closure_tolerance.value()),
    }
    save_values(**result)
    return result
