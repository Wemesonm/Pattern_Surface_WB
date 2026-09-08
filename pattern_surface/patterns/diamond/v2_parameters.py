"""Parameters owned exclusively by Diamond Pattern Prototype V2."""

import FreeCAD as App


PREFERENCE_PATH = "User parameter:BaseApp/Preferences/Mod/Auzyron_Patterns_WB/Patterns/DiamondPrototypeV2"


def _stored(key, default):
    value = App.ParamGet(PREFERENCE_PATH).GetFloat(key, -1.0)
    return float(default if value < 0.0 else value)


def get_parameters():
    from PySide import QtGui
    try:
        from PySide import QtWidgets
    except ImportError:
        QtWidgets = QtGui
    dialog = QtWidgets.QDialog()
    dialog.setWindowTitle("Diamond Pattern Prototype V2")
    layout = QtWidgets.QFormLayout(dialog)

    fields = []
    for label, key, default, minimum in (
        ("Diamond height:", "DiamondHeight", 12.0, 0.01),
        ("Pyramid height:", "PyramidHeight", 1.0, 0.01),
        ("Transition relief:", "TransitionRelief", 0.55, 0.05),
        ("Cell gap:", "CellGap", 0.40, 0.0),
    ):
        field = QtWidgets.QDoubleSpinBox(dialog)
        if key == "TransitionRelief":
            field.setRange(minimum * 100.0, 100.0)
            field.setValue(_stored(key, default) * 100.0)
        else:
            field.setRange(minimum, 1000.0)
            field.setValue(_stored(key, default))
        field.setDecimals(3)
        field.setSuffix(" %" if key == "TransitionRelief" else " mm")
        layout.addRow(label, field)
        fields.append((key, field))

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
        parent=dialog,
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return None

    values = {}
    for key, field in fields:
        value = float(field.value())
        if key == "TransitionRelief":
            value /= 100.0
        values[key] = value
        App.ParamGet(PREFERENCE_PATH).SetFloat(key, value)
    return {
        "diamond_height": values["DiamondHeight"],
        "pyramid_height": values["PyramidHeight"],
        "transition_relief": values["TransitionRelief"],
        "cell_gap": values["CellGap"],
    }
