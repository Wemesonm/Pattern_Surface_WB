import importlib
import os

import FreeCAD as App


COMMAND_ID = "PatternSurface_MapFaces"
ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons", "map_faces.svg")


class MapFacesCommand:
    def GetResources(self):
        return {
            "Pixmap": ICON,
            "MenuText": "Map Faces",
            "ToolTip": "Map selected adjacent faces and create the carrier grid",
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        from ..mapping import service

        importlib.reload(service)
        service.create_map()
