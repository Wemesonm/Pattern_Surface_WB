import FreeCAD as App

from .metadata import (
    DEFAULT_ANGLE, DEFAULT_HEIGHT, DEFAULT_PITCH, DEFAULT_RESOLUTION,
    MAX_ANGLE, MAX_LENGTH, MAX_RESOLUTION, MIN_ANGLE, MIN_LENGTH,
    MIN_RESOLUTION,
)


PREFERENCE = "User parameter:BaseApp/Preferences/Mod/Auzyron_Patterns_WB/Patterns/DiagonalRibs"


def _last(key, default):
    return App.ParamGet(PREFERENCE).GetFloat(key, default)


def get_parameters(map_object=None):
    from PySide import QtGui
    try:
        from PySide import QtWidgets
    except ImportError:
        QtWidgets = QtGui

    dialog = QtWidgets.QDialog()
    dialog.setWindowTitle("Diagonal Ribs")
    layout = QtWidgets.QFormLayout(dialog)

    def length(label, key, default):
        widget = QtWidgets.QDoubleSpinBox(dialog)
        widget.setRange(MIN_LENGTH, MAX_LENGTH)
        widget.setDecimals(3)
        widget.setSuffix(" mm")
        widget.setValue(_last(key, default))
        layout.addRow(label, widget)
        return widget

    pitch = length("Rib spacing:", "Pitch", DEFAULT_PITCH)
    height = length("Relief height:", "Height", DEFAULT_HEIGHT)
    angle = QtWidgets.QDoubleSpinBox(dialog)
    angle.setRange(MIN_ANGLE, MAX_ANGLE)
    angle.setDecimals(1)
    angle.setSuffix(" deg")
    angle.setValue(_last("Angle", DEFAULT_ANGLE))
    layout.addRow("Rib angle:", angle)
    resolution = QtWidgets.QSpinBox(dialog)
    resolution.setRange(MIN_RESOLUTION, MAX_RESOLUTION)
    resolution.setValue(int(round(_last("Resolution", DEFAULT_RESOLUTION))))
    layout.addRow("Surface resolution:", resolution)
    layout.addRow(QtWidgets.QLabel(
        "Ribs follow the mapped surface and are clipped at its physical edges.", dialog))

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
        parent=dialog)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return None

    values = {"rib_pitch": float(pitch.value()), "rib_height": float(height.value()),
              "rib_angle": float(angle.value()), "resolution": int(resolution.value()),
              "finish_offset": 0.045, "contact": 0.25}
    settings = App.ParamGet(PREFERENCE)
    for key, value in (("Pitch", values["rib_pitch"]), ("Height", values["rib_height"]),
                       ("Angle", values["rib_angle"]), ("Resolution", values["resolution"])):
        settings.SetFloat(key, value)
    return values
