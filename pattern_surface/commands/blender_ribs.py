"""FreeCAD command for diagonal rib relief in an unsaved Blender scene."""

import os
import subprocess
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui

from ..blender_bridge.job import (_blender_binary, cleanup_jobs, create_job,
                                  resolve_map, worker_path)
from ..patterns.ribs import parameters


COMMAND_ID = "PatternSurface_Blender_DiagonalRibs"
ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons", "ribs.svg")


class BlenderDiagonalRibsCommand:
    def GetResources(self):
        return {"Pixmap": ICON, "MenuText": "Diagonal Ribs",
                "ToolTip": "Generate diagonal rib relief from a mapped surface in an unsaved Blender scene"}

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        selected = Gui.Selection.getSelection()
        if not selected:
            App.Console.PrintError("Diagonal Ribs requires a Mapped Surface or Mapping Grid selection.\n")
            return
        try:
            mapped = resolve_map(selected[0])
            if mapped is None:
                raise ValueError("Select a Mapped Surface or Mapping Grid first.")
            values = parameters.get_parameters(mapped)
            if values is None:
                return
            removed = cleanup_jobs()
            module = Path(__file__).parents[1] / "blender_bridge" / "geometry_ribs.py"
            job_path = create_job(mapped, values, geometry_module=module,
                                  pattern_label="Diagonal Ribs",
                                  boundary_solver="MANIFOLD")
            subprocess.Popen([_blender_binary(), "--factory-startup", "--python",
                              str(worker_path()), "--", str(job_path), "--interactive"])
            App.Console.PrintMessage(
                "Diagonal Ribs opened an unsaved Blender scene (removed {} stale temporary job(s)).\n".format(removed))
        except Exception as error:
            App.Console.PrintError("Diagonal Ribs failed: {}\n".format(error))
