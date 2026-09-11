import FreeCAD as App

from .metadata import (
    DEFAULT_DIAMOND_HEIGHT,
    DEFAULT_CLOSURE_FIT_TOLERANCE,
    DEFAULT_PYRAMID_HEIGHT,
    DEFAULT_CURVED_RELIEF_FACTOR,
    DEFAULT_CELL_GAP,
    MAX_DIAMOND_HEIGHT,
    MAX_CLOSURE_FIT_TOLERANCE,
    MAX_PYRAMID_HEIGHT,
    MAX_CURVED_RELIEF_FACTOR,
    MIN_DIAMOND_HEIGHT,
    MIN_CLOSURE_FIT_TOLERANCE,
    MIN_PYRAMID_HEIGHT,
    MIN_CURVED_RELIEF_FACTOR,
    MIN_CELL_GAP,
    MAX_CELL_GAP,
)


PREFERENCE_PATH = "User parameter:BaseApp/Preferences/Mod/Auzyron_Patterns_WB/Patterns/Diamond"
LEGACY_PREFERENCE_PATH = "User parameter:BaseApp/Preferences/Mod/Pattern_Surface_WB/Patterns/Diamond"
PREFERENCE_KEY = "LastHeight"
DIAMOND_HEIGHT_KEY = "LastDiamondHeight"
PYRAMID_HEIGHT_KEY = "LastPyramidHeight"
CLOSURE_FIT_TOLERANCE_KEY = "LastClosureFitTolerance"
CURVED_RELIEF_FACTOR_KEY = "LastCurvedReliefFactor"
CELL_GAP_KEY = "LastCellGap"
CELL_GAP_X_KEY = "LastCellGapX"
CELL_GAP_Y_KEY = "LastCellGapY"
BLENDER_BASE_BLEND_KEY = "BlenderBaseBlend"
BLENDER_EDGE_MODE_KEY = "BlenderEdgeMode"
BLENDER_ALL_EDGES_KEY = "BlenderBlendAllEdges"
BLENDER_RESOLUTION_KEY = "BlenderResolution"


def preferences():
    return App.ParamGet(PREFERENCE_PATH)


def legacy_preferences():
    return App.ParamGet(LEGACY_PREFERENCE_PATH)


def stored_float(key, default):
    value = preferences().GetFloat(key, -1.0)
    if value >= 0.0:
        return value
    return legacy_preferences().GetFloat(key, default)


def last_diamond_height():
    return max(MIN_DIAMOND_HEIGHT,
               stored_float(DIAMOND_HEIGHT_KEY, DEFAULT_DIAMOND_HEIGHT))


def last_pyramid_height():
    legacy = stored_float(PREFERENCE_KEY, DEFAULT_PYRAMID_HEIGHT)
    return max(MIN_PYRAMID_HEIGHT,
               stored_float(PYRAMID_HEIGHT_KEY, legacy))


def last_closure_fit_tolerance():
    return max(MIN_CLOSURE_FIT_TOLERANCE,
               stored_float(CLOSURE_FIT_TOLERANCE_KEY,
                            DEFAULT_CLOSURE_FIT_TOLERANCE))


def last_curved_relief_factor():
    return min(MAX_CURVED_RELIEF_FACTOR, max(MIN_CURVED_RELIEF_FACTOR,
               stored_float(CURVED_RELIEF_FACTOR_KEY,
                            DEFAULT_CURVED_RELIEF_FACTOR)))


def last_cell_gap():
    return min(MAX_CELL_GAP, max(MIN_CELL_GAP,
               stored_float(CELL_GAP_KEY, DEFAULT_CELL_GAP)))


def last_cell_gap_x():
    return min(MAX_CELL_GAP, max(MIN_CELL_GAP,
               stored_float(CELL_GAP_X_KEY, last_cell_gap())))


def last_cell_gap_y():
    return min(MAX_CELL_GAP, max(MIN_CELL_GAP,
               stored_float(CELL_GAP_Y_KEY, last_cell_gap())))


def save_parameters(diamond_height, pyramid_height, closure_fit_tolerance,
                    curved_relief_factor=None, cell_gap=None,
                    cell_gap_x=None, cell_gap_y=None):
    preferences().SetFloat(DIAMOND_HEIGHT_KEY, float(diamond_height))
    preferences().SetFloat(PYRAMID_HEIGHT_KEY, float(pyramid_height))
    preferences().SetFloat(PREFERENCE_KEY, float(pyramid_height))
    preferences().SetFloat(
        CLOSURE_FIT_TOLERANCE_KEY, float(closure_fit_tolerance))
    if curved_relief_factor is not None:
        preferences().SetFloat(CURVED_RELIEF_FACTOR_KEY,
                                float(curved_relief_factor))
    if cell_gap is not None:
        preferences().SetFloat(CELL_GAP_KEY, float(cell_gap))
    if cell_gap_x is not None:
        preferences().SetFloat(CELL_GAP_X_KEY, float(cell_gap_x))
    if cell_gap_y is not None:
        preferences().SetFloat(CELL_GAP_Y_KEY, float(cell_gap_y))


def save_heights(diamond_height, pyramid_height):
    """Compatibility wrapper for callers predating closure-fit tolerance."""
    save_parameters(diamond_height, pyramid_height, last_closure_fit_tolerance())


def _map_cell_dimensions(map_object):
    if map_object is None:
        return None
    try:
        from ... import core_engine
        from ...common.ownership import map_from_selection_object
        run = map_from_selection_object(map_object)
        if run is None:
            return None
        chunk_name = ("MapPayloadChunks"
                      if "MapPayloadChunks" in getattr(run, "PropertiesList", [])
                      else "WrapCarrierChunks")
        payload = core_engine.load_chunks(run, chunk_name)
        grid = payload.get("grid", {})
        bounds = payload.get("bounds", [])
        columns = int(grid.get("column_count") or 0)
        rows = int(grid.get("row_count") or 0)
        if len(bounds) != 4 or columns < 1 or rows < 1:
            return None
        return ((float(bounds[1]) - float(bounds[0])) / columns,
                (float(bounds[3]) - float(bounds[2])) / rows,
                columns, rows)
    except Exception:
        return None


def get_parameters(map_object=None, blender=False):
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
    layout.addRow("Diamond / triangle size (height):", diamond_height)

    pyramid_height = QtWidgets.QDoubleSpinBox(dialog)
    pyramid_height.setRange(MIN_PYRAMID_HEIGHT, MAX_PYRAMID_HEIGHT)
    pyramid_height.setDecimals(3)
    pyramid_height.setSuffix(" mm")
    pyramid_height.setValue(last_pyramid_height())
    layout.addRow("Relief / pyramid height:", pyramid_height)

    layout.addRow(QtWidgets.QLabel(
        "Population is calculated from size and mapped surface dimensions.\n"
        "Rows follow the logical map from bottom to top."))

    closure_tolerance = QtWidgets.QDoubleSpinBox(dialog)
    closure_tolerance.setRange(
        MIN_CLOSURE_FIT_TOLERANCE, MAX_CLOSURE_FIT_TOLERANCE)
    closure_tolerance.setDecimals(3)
    closure_tolerance.setSuffix(" mm")
    closure_tolerance.setValue(last_closure_fit_tolerance())
    layout.addRow("Closure fit tolerance:", closure_tolerance)

    edge_blend = resolution = None
    lower_edge = upper_edge = None
    if blender:
        resolution = QtWidgets.QSpinBox(dialog)
        resolution.setRange(1, 40)
        resolution.setValue(int(round(stored_float(BLENDER_RESOLUTION_KEY, 8.0))))
        layout.addRow("Surface resolution:", resolution)
        edge_blend = QtWidgets.QDoubleSpinBox(dialog)
        edge_blend.setRange(0.0, MAX_DIAMOND_HEIGHT)
        edge_blend.setDecimals(3)
        edge_blend.setSuffix(" mm")
        edge_blend.setValue(stored_float(BLENDER_BASE_BLEND_KEY, 6.0))
        layout.addRow("Concave edge transition:", edge_blend)
        mode = preferences().GetString(BLENDER_EDGE_MODE_KEY, "lower")
        lower_edge = QtWidgets.QCheckBox("Bottom edge", dialog)
        upper_edge = QtWidgets.QCheckBox("Top edge", dialog)
        if mode == "none":
            pass
        elif mode == "upper":
            upper_edge.setChecked(True)
        elif mode == "both" or preferences().GetBool(BLENDER_ALL_EDGES_KEY, False):
            lower_edge.setChecked(True)
            upper_edge.setChecked(True)
        else:
            lower_edge.setChecked(True)
        choices = QtWidgets.QWidget(dialog)
        choices_layout = QtWidgets.QHBoxLayout(choices)
        choices_layout.setContentsMargins(0, 0, 0, 0)
        choices_layout.addWidget(lower_edge)
        choices_layout.addWidget(upper_edge)
        layout.addRow("Concave transition edge:", choices)
        layout.addRow(QtWidgets.QLabel(
            "Mark one or both edges in the map's local orientation. Leave both unchecked for no concave transition."))

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
    values = {
        "diamond_height": diamond_value,
        "pyramid_height": pyramid_value,
        "height": pyramid_value,
        "closure_fit_tolerance": float(closure_tolerance.value()),
    }
    if blender:
        values.update({
            "base_blend": (float(edge_blend.value())
                           if lower_edge.isChecked() or upper_edge.isChecked() else 0.0),
            "blend_all_edges": False,
            "edge_transition": ("both" if lower_edge.isChecked() and upper_edge.isChecked() else
                                "upper" if upper_edge.isChecked() else
                                "lower" if lower_edge.isChecked() else "none"),
            "resolution": int(resolution.value()),
        })
        preferences().SetFloat(BLENDER_BASE_BLEND_KEY, values["base_blend"])
        preferences().SetString(BLENDER_EDGE_MODE_KEY, values["edge_transition"])
        preferences().SetFloat(BLENDER_RESOLUTION_KEY, values["resolution"])
    return values

def get_prototype_parameters(map_object=None):
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

    curved_relief = QtWidgets.QDoubleSpinBox(dialog)
    curved_relief.setRange(MIN_CURVED_RELIEF_FACTOR * 100.0,
                           MAX_CURVED_RELIEF_FACTOR * 100.0)
    curved_relief.setDecimals(0)
    curved_relief.setSuffix(" %")
    curved_relief.setValue(last_curved_relief_factor() * 100.0)
    layout.addRow("Curved-surface relief:", curved_relief)

    cell_gap_x = QtWidgets.QDoubleSpinBox(dialog)
    cell_gap_x.setRange(MIN_CELL_GAP, MAX_CELL_GAP)
    cell_gap_x.setDecimals(3)
    cell_gap_x.setSuffix(" mm")
    cell_gap_x.setValue(last_cell_gap_x())
    layout.addRow("Gap X between columns:", cell_gap_x)

    cell_gap_y = QtWidgets.QDoubleSpinBox(dialog)
    cell_gap_y.setRange(MIN_CELL_GAP, MAX_CELL_GAP)
    cell_gap_y.setDecimals(3)
    cell_gap_y.setSuffix(" mm")
    cell_gap_y.setValue(last_cell_gap_y())
    layout.addRow("Gap Y between rows:", cell_gap_y)

    available_width = QtWidgets.QLabel("-")
    available_height = QtWidgets.QLabel("-")
    calculated_gap = QtWidgets.QLabel("-")
    layout.addRow("Available cell width:", available_width)
    layout.addRow("Available cell height:", available_height)
    layout.addRow("Calculated gap:", calculated_gap)
    dimensions = _map_cell_dimensions(map_object)

    def update_calculated_values():
        if dimensions is None:
            available_width.setText("Map divisions unavailable")
            available_height.setText("Map divisions unavailable")
            calculated_gap.setText("-")
            return
        width, height, columns, rows = dimensions
        side = 2.0 * float(diamond_height.value()) / (3.0 ** 0.5)
        gap = max(0.0, width - side)
        available_width.setText("{:.3f} mm ({} columns)".format(width, columns))
        available_height.setText("{:.3f} mm ({} rows)".format(height, rows))
        calculated_gap.setText("{:.3f} mm".format(gap))
        cell_gap_x.blockSignals(True)
        cell_gap_x.setValue(gap)
        cell_gap_x.blockSignals(False)
        height_gap = max(0.0, height - float(diamond_height.value()))
        cell_gap_y.blockSignals(True)
        cell_gap_y.setValue(height_gap)
        cell_gap_y.blockSignals(False)

    diamond_height.valueChanged.connect(update_calculated_values)
    update_calculated_values()

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
    curved_relief_value = float(curved_relief.value()) / 100.0
    cell_gap_x_value = float(cell_gap_x.value())
    cell_gap_y_value = float(cell_gap_y.value())
    return {
        "diamond_height": diamond_value,
        "pyramid_height": pyramid_value,
        "height": pyramid_value,
        "closure_fit_tolerance": float(closure_tolerance.value()),
        "curved_relief_factor": curved_relief_value,
        "cell_gap": cell_gap_x_value,
        "cell_gap_x": cell_gap_x_value,
        "cell_gap_y": cell_gap_y_value,
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
