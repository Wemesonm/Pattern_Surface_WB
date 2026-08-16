import os

import FreeCADGui as Gui

from .commands import COMMANDS, register_commands


ICON = os.path.join(os.path.dirname(__file__), "resources", "icons", "workbench.svg")


class PatternSurfaceWorkbench(Gui.Workbench):
    MenuText = "Pattern_Surface_WB"
    ToolTip = "Map adjacent faces, apply patterns, and trim generated solids"
    Icon = ICON

    def Initialize(self):
        register_commands()
        self.appendToolbar("Pattern Surface", COMMANDS)
        self.appendMenu("Pattern Surface", COMMANDS)

    def Activated(self):
        return

    def Deactivated(self):
        return

    def GetClassName(self):
        return "Gui::PythonWorkbench"


_registered = False


def register_workbench():
    global _registered
    if not _registered:
        Gui.addWorkbench(PatternSurfaceWorkbench())
        _registered = True
