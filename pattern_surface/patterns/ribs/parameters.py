import FreeCAD as App

from .metadata import (
    DEFAULT_ANGLE, DEFAULT_HEIGHT, DEFAULT_PITCH, DEFAULT_RESOLUTION, DEFAULT_BASE_BLEND,
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
    blend = length("Rounded edge transition:", "BaseBlend", DEFAULT_BASE_BLEND)
    blend.setMinimum(0.0)
    blend.setValue(_last("BaseBlend", DEFAULT_BASE_BLEND))
    all_edges = QtWidgets.QCheckBox("Apply to all edges", dialog)
    all_edges.setChecked(App.ParamGet(PREFERENCE).GetBool("BlendAllEdges", False))
    layout.addRow(all_edges)
    layout.addRow(QtWidgets.QLabel(
        "Width of the rounded transition. 0 mm disables it.\n"
        "Unchecked: lower edges only. Checked: the complete face boundary.", dialog))

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
              "finish_offset": 0.045, "contact": 0.25,
              "base_blend": float(blend.value()), "blend_all_edges": all_edges.isChecked()}
    settings = App.ParamGet(PREFERENCE)
    for key, value in (("Pitch", values["rib_pitch"]), ("Height", values["rib_height"]),
                       ("Angle", values["rib_angle"]), ("Resolution", values["resolution"]),
                       ("BaseBlend", values["base_blend"])):
        settings.SetFloat(key, value)
    settings.SetBool("BlendAllEdges", values["blend_all_edges"])
    return values
