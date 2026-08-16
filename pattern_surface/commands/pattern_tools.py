import importlib
import os

import FreeCAD as App


GROUP_COMMAND_ID = "PatternSurface_PatternTools"
DIAMOND_COMMAND_ID = "PatternSurface_Pattern_Diamond"
ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons", "pattern_tools.svg")
DIAMOND_ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons", "diamond.svg")


class DiamondPatternCommand:
    def GetResources(self):
        return {
            "Pixmap": DIAMOND_ICON,
            "MenuText": "Diamond Pattern",
            "ToolTip": "Generate triangular pyramid cells on a mapped surface",
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        from ..patterns.diamond import command

        importlib.reload(command)
        command.run()


class PatternToolsGroup:
    def GetResources(self):
        return {
            "Pixmap": ICON,
            "MenuText": "Pattern Tools",
            "ToolTip": "Choose a registered surface pattern",
        }

    def GetCommands(self):
        from ..patterns import registry

        importlib.reload(registry)
        return tuple(item["command_id"] for item in registry.patterns())

    def GetDefaultCommand(self):
        return 0

    def IsExclusive(self):
        return False
