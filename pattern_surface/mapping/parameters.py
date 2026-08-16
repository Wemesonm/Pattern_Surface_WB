import FreeCAD as App


PREFERENCE_PATH = "User parameter:BaseApp/Preferences/Mod/Pattern_Surface_WB/MapFaces"
COLUMN_WIDTH_KEY = "LastColumnWidth"
ROW_HEIGHT_KEY = "LastRowHeight"
CLOSURE_TOLERANCE_KEY = "LastClosureTolerance"

DEFAULT_COLUMN_WIDTH = 13.85640646055102
DEFAULT_ROW_HEIGHT = 12.0
DEFAULT_CLOSURE_TOLERANCE = 0.05
MIN_LENGTH = 0.01
MAX_LENGTH = 100000.0


def preferences():
    return App.ParamGet(PREFERENCE_PATH)


def last_values():
    store = preferences()
    return {
        "column_width": max(
            MIN_LENGTH, store.GetFloat(COLUMN_WIDTH_KEY, DEFAULT_COLUMN_WIDTH)),
        "row_height": max(
            MIN_LENGTH, store.GetFloat(ROW_HEIGHT_KEY, DEFAULT_ROW_HEIGHT)),
        "closure_tolerance": max(
            MIN_LENGTH,
            store.GetFloat(CLOSURE_TOLERANCE_KEY, DEFAULT_CLOSURE_TOLERANCE)),
    }


def save_values(column_width, row_height, closure_tolerance):
    store = preferences()
    store.SetFloat(COLUMN_WIDTH_KEY, float(column_width))
    store.SetFloat(ROW_HEIGHT_KEY, float(row_height))
    store.SetFloat(CLOSURE_TOLERANCE_KEY, float(closure_tolerance))


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

    column_width = QtWidgets.QDoubleSpinBox(dialog)
    column_width.setRange(MIN_LENGTH, MAX_LENGTH)
    column_width.setDecimals(3)
    column_width.setSuffix(" mm")
    column_width.setValue(values["column_width"])
    layout.addRow("Column width:", column_width)

    row_height = QtWidgets.QDoubleSpinBox(dialog)
    row_height.setRange(MIN_LENGTH, MAX_LENGTH)
    row_height.setDecimals(3)
    row_height.setSuffix(" mm")
    row_height.setValue(values["row_height"])
    layout.addRow("Row height:", row_height)

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
        "column_width": float(column_width.value()),
        "row_height": float(row_height.value()),
        "closure_tolerance": float(closure_tolerance.value()),
    }
    save_values(**result)
    return result
