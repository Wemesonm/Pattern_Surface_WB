import FreeCAD as App

from .metadata import (
    DEFAULT_DEPTH, DEFAULT_FEATURE_SIZE, DEFAULT_SEED, DEFAULT_VARIATION,
    MAX_DEPTH, MAX_FEATURE_SIZE, MIN_DEPTH, MIN_FEATURE_SIZE,
)


PREFERENCE_PATH = "User parameter:BaseApp/Preferences/Mod/Auzyron_Patterns_WB/Patterns/FuzzySkin"


def preferences():
    return App.ParamGet(PREFERENCE_PATH)


def get_parameters():
    from PySide import QtGui
    try:
        from PySide import QtWidgets
    except ImportError:
        QtWidgets = QtGui

    dialog = QtWidgets.QDialog()
    dialog.setWindowTitle("Fuzzy Skin Pattern")
    layout = QtWidgets.QFormLayout(dialog)

    depth = QtWidgets.QDoubleSpinBox(dialog)
    depth.setRange(MIN_DEPTH, MAX_DEPTH)
    depth.setDecimals(3)
    depth.setSuffix(" mm")
    depth.setValue(preferences().GetFloat("LastDepth", DEFAULT_DEPTH))
    layout.addRow("Texture depth:", depth)

    size = QtWidgets.QDoubleSpinBox(dialog)
    size.setRange(MIN_FEATURE_SIZE, MAX_FEATURE_SIZE)
    size.setDecimals(3)
    size.setSuffix(" mm")
    size.setValue(preferences().GetFloat("LastFeatureSize", DEFAULT_FEATURE_SIZE))
    layout.addRow("Feature size:", size)

    variation = QtWidgets.QDoubleSpinBox(dialog)
    variation.setRange(0.0, 1.0)
    variation.setDecimals(3)
    variation.setSingleStep(0.05)
    variation.setValue(preferences().GetFloat("LastVariation", DEFAULT_VARIATION))
    layout.addRow("Random variation:", variation)

    seed = QtWidgets.QSpinBox(dialog)
    seed.setRange(0, 2147483647)
    seed.setValue(preferences().GetInt("LastSeed", DEFAULT_SEED))
    layout.addRow("Seed:", seed)

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
        parent=dialog)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return None
    values = {
        "depth": float(depth.value()),
        "feature_size": float(size.value()),
        "variation": float(variation.value()),
        "seed": int(seed.value()),
    }
    preferences().SetFloat("LastDepth", values["depth"])
    preferences().SetFloat("LastFeatureSize", values["feature_size"])
    preferences().SetFloat("LastVariation", values["variation"])
    preferences().SetInt("LastSeed", values["seed"])
    return values
