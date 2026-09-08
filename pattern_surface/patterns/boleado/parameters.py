from FreeCAD import ParamGet

from .metadata import (
    DEFAULT_BUMP_HEIGHT, DEFAULT_BUMP_RADIUS, DEFAULT_PENETRATION,
    DEFAULT_ROW_OFFSET, DEFAULT_SPACING_X, DEFAULT_SPACING_Y,
    MAX_LENGTH, MAX_ROW_OFFSET, MIN_LENGTH,
)


PREFERENCE = "User parameter:BaseApp/Preferences/Mod/PatternSurface/Boleado"


def _last(key, default):
    return ParamGet(PREFERENCE).GetFloat(key, default)


def get_parameters():
    from PySide import QtGui
    try:
        from PySide import QtWidgets
    except ImportError:
        QtWidgets = QtGui

    dialog = QtWidgets.QDialog()
    dialog.setWindowTitle("Boleado Pattern")
    layout = QtWidgets.QFormLayout(dialog)

    def length(label, key, default):
        widget = QtWidgets.QDoubleSpinBox(dialog)
        widget.setRange(MIN_LENGTH, MAX_LENGTH)
        widget.setDecimals(3)
        widget.setSuffix(" mm")
        widget.setValue(_last(key, default))
        layout.addRow(label, widget)
        return widget

    radius = length("Hemisphere radius:", "BumpRadius", DEFAULT_BUMP_RADIUS)
    height_info = QtWidgets.QLabel(
        "The exposed height is fixed to the radius (true half-sphere).",
        dialog,
    )
    layout.addRow("Hemisphere:", height_info)
    spacing_x = length("Horizontal spacing:", "SpacingX", DEFAULT_SPACING_X)
    spacing_y = length("Vertical spacing:", "SpacingY", DEFAULT_SPACING_Y)
    offset = QtWidgets.QDoubleSpinBox(dialog)
    offset.setRange(0.0, MAX_ROW_OFFSET)
    offset.setDecimals(3)
    offset.setSuffix(" x spacing")
    offset.setValue(_last("RowOffset", DEFAULT_ROW_OFFSET))
    layout.addRow("Alternating row offset:", offset)
    penetration = length("Surface penetration:", "Penetration", DEFAULT_PENETRATION)

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
        parent=dialog,
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return None

    values = {
        "bump_radius": float(radius.value()),
        "bump_height": float(radius.value()),
        "spacing_x": float(spacing_x.value()),
        "spacing_y": float(spacing_y.value()),
        "row_offset": float(offset.value()),
        "penetration": float(penetration.value()),
    }
    settings = ParamGet(PREFERENCE)
    for key, value in (
        ("BumpRadius", values["bump_radius"]),
        ("BumpHeight", values["bump_height"]),
        ("SpacingX", values["spacing_x"]),
        ("SpacingY", values["spacing_y"]),
        ("RowOffset", values["row_offset"]),
        ("Penetration", values["penetration"]),
    ):
        settings.SetFloat(key, value)
    return values
