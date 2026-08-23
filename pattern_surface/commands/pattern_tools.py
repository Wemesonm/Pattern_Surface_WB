import os

import FreeCAD as App

from ..common.runtime import maybe_reload


GROUP_COMMAND_ID = "PatternSurface_PatternTools"
DIAMOND_COMMAND_ID = "PatternSurface_Pattern_Diamond"
FUZZY_SKIN_COMMAND_ID = "PatternSurface_Pattern_FuzzySkin"
ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons", "pattern_tools.svg")
DIAMOND_ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons", "diamond.svg")
FUZZY_SKIN_ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons", "fuzzy_skin.svg")


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

        maybe_reload(command)
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

        maybe_reload(registry)
        return tuple(item["command_id"] for item in registry.patterns())

    def GetDefaultCommand(self):
        return 0

    def IsExclusive(self):
        return False


class FuzzySkinPatternCommand:
    def GetResources(self):
        return {
            "Pixmap": FUZZY_SKIN_ICON,
            "MenuText": "Fuzzy Skin Pattern",
            "ToolTip": "Add deterministic normal displacement to a mapped surface",
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        from ..patterns.fuzzy_skin import command

        maybe_reload(command)
        command.run()
