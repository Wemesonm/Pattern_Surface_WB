"""FreeCAD command for opening the mapped surface in an unsaved Blender scene."""

import os
import subprocess

import FreeCAD as App
import FreeCADGui as Gui

from ..blender_bridge.job import (_blender_binary, cleanup_jobs, create_job,
                                  resolve_map, worker_path)
from ..patterns.diamond import parameters as diamond_parameters


COMMAND_ID = "PatternSurface_Blender_Diamond"
ICON = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "resources", "icons", "blender.svg"
)


class BlenderDiamondCommand:
    def GetResources(self):
        return {
            "Pixmap": ICON,
            "MenuText": "Blender: Diamond",
            "ToolTip": "Generate Diamond relief from a mapped surface in an unsaved Blender scene",
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        selected = Gui.Selection.getSelection()
        if not selected:
            App.Console.PrintError(
                "Blender: Diamond requires a Mapped Surface or Mapping Grid selection.\n"
            )
            return
        try:
            mapped = resolve_map(selected[0])
            if mapped is None:
                raise ValueError("Select a Mapped Surface or Mapping Grid first.")
            # Blender is the Diamond generator in this workflow.  Map Faces
            # only supplies the CAD surface and logical coordinates; it does
            # not require a Diamond result to exist in FreeCAD.
            values = diamond_parameters.get_parameters(mapped, blender=True)
            if values is None:
                return
            parameters = {
                **values,
                "finish_offset": 0.045,
                "contact": 0.25,
            }
            removed = cleanup_jobs()
            job_path = create_job(
                mapped, parameters,
                include_boundary_curves=parameters.get("base_blend", 0.0) > 0.0)
            blender = _blender_binary()
            subprocess.Popen([blender, "--factory-startup", "--python",
                              str(worker_path()), "--", str(job_path),
                              "--interactive"])
            App.Console.PrintMessage(
                "Blender: Diamond opened an unsaved scene (removed {} stale temporary job(s)).\n".format(removed)
            )
        except Exception as error:
            App.Console.PrintError("Blender: Diamond failed: {}\n".format(error))
