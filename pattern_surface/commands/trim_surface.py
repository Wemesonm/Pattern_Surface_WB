import os

import FreeCAD as App

from ..common.runtime import maybe_reload


COMMAND_ID = "PatternSurface_TrimSurface"
ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons", "trim_surface.svg")


class TrimSurfaceCommand:
    def GetResources(self):
        return {
            "Pixmap": ICON,
            "MenuText": "Trim Surface",
            "ToolTip": "Trim the selected pattern to its mapped source faces",
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        from ..trimming import service

        maybe_reload(service)
        service.trim_pattern()
