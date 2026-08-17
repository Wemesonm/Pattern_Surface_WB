import FreeCAD as App

from .metadata import (
    DEFAULT_DIAMOND_HEIGHT,
    DEFAULT_CLOSURE_FIT_TOLERANCE,
    DEFAULT_PYRAMID_HEIGHT,
    MAX_DIAMOND_HEIGHT,
    MAX_CLOSURE_FIT_TOLERANCE,
    MAX_PYRAMID_HEIGHT,
    MIN_DIAMOND_HEIGHT,
    MIN_CLOSURE_FIT_TOLERANCE,
    MIN_PYRAMID_HEIGHT,
)


PREFERENCE_PATH = "User parameter:BaseApp/Preferences/Mod/Pattern_Surface_WB/Patterns/Diamond"
PREFERENCE_KEY = "LastHeight"
DIAMOND_HEIGHT_KEY = "LastDiamondHeight"
PYRAMID_HEIGHT_KEY = "LastPyramidHeight"
CLOSURE_FIT_TOLERANCE_KEY = "LastClosureFitTolerance"


def preferences():
    return App.ParamGet(PREFERENCE_PATH)


def last_diamond_height():
    return max(MIN_DIAMOND_HEIGHT,
               preferences().GetFloat(DIAMOND_HEIGHT_KEY, DEFAULT_DIAMOND_HEIGHT))


def last_pyramid_height():
    legacy = preferences().GetFloat(PREFERENCE_KEY, DEFAULT_PYRAMID_HEIGHT)
    return max(MIN_PYRAMID_HEIGHT,
               preferences().GetFloat(PYRAMID_HEIGHT_KEY, legacy))


def last_closure_fit_tolerance():
    return max(MIN_CLOSURE_FIT_TOLERANCE,
               preferences().GetFloat(
                   CLOSURE_FIT_TOLERANCE_KEY,
                   DEFAULT_CLOSURE_FIT_TOLERANCE))


def save_parameters(diamond_height, pyramid_height, closure_fit_tolerance):
    preferences().SetFloat(DIAMOND_HEIGHT_KEY, float(diamond_height))
    preferences().SetFloat(PYRAMID_HEIGHT_KEY, float(pyramid_height))
    preferences().SetFloat(PREFERENCE_KEY, float(pyramid_height))
    preferences().SetFloat(
        CLOSURE_FIT_TOLERANCE_KEY, float(closure_fit_tolerance))


def save_heights(diamond_height, pyramid_height):
    """Compatibility wrapper for callers predating closure-fit tolerance."""
    save_parameters(diamond_height, pyramid_height, last_closure_fit_tolerance())


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

    closure_tolerance = QtWidgets.QDoubleSpinBox(dialog)
    closure_tolerance.setRange(
        MIN_CLOSURE_FIT_TOLERANCE, MAX_CLOSURE_FIT_TOLERANCE)
    closure_tolerance.setDecimals(3)
    closure_tolerance.setSuffix(" mm")
    closure_tolerance.setValue(last_closure_fit_tolerance())
    layout.addRow("Closure fit tolerance:", closure_tolerance)

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
    return {
        "diamond_height": diamond_value,
        "pyramid_height": pyramid_value,
        "height": pyramid_value,
        "closure_fit_tolerance": float(closure_tolerance.value()),
    }


def confirm_closure_fit(fit):
    from PySide import QtGui
    try:
        from PySide import QtWidgets
    except ImportError:
        QtWidgets = QtGui

    message = (
        "The selected faces form a closed periodic surface.\n\n"
        "Logical period: {period:.6f} mm\n"
        "Modules: {modules}\n"
        "Natural triangle side: {natural_side:.6f} mm\n"
        "Adjusted triangle side: {effective_side:.6f} mm\n"
        "Total closure difference: {adjustment:.6f} mm\n"
        "Allowed tolerance: {tolerance:.6f} mm\n\n"
        "Triangle height will remain {diamond_height:.6f} mm. Continue?"
    ).format(**fit)
    answer = QtWidgets.QMessageBox.question(
        None,
        "Diamond Pattern - Closure fit",
        message,
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        QtWidgets.QMessageBox.No,
    )
    return answer == QtWidgets.QMessageBox.Yes


def show_closure_incompatible(fit):
    from PySide import QtGui
    try:
        from PySide import QtWidgets
    except ImportError:
        QtWidgets = QtGui

    QtWidgets.QMessageBox.warning(
        None,
        "Diamond Pattern - Incompatible closure",
        (
            "The closed surface cannot be fitted within the selected tolerance.\n\n"
            "Logical period: {period:.6f} mm\n"
            "Modules: {modules}\n"
            "Required total adjustment: {adjustment:.6f} mm\n"
            "Allowed tolerance: {tolerance:.6f} mm"
        ).format(**fit),
    )
