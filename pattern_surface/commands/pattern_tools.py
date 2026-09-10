import os

import FreeCAD as App

from ..common.runtime import maybe_reload


GROUP_COMMAND_ID = "PatternSurface_PatternTools"
DIAMOND_COMMAND_ID = "PatternSurface_Pattern_Diamond"
BOLEADO_COMMAND_ID = "PatternSurface_Pattern_Boleado"
DIAMOND_PROTOTYPE_COMMAND_ID = "PatternSurface_Pattern_DiamondPrototype"
DIAMOND_PROTOTYPE_V2_COMMAND_ID = "PatternSurface_Pattern_DiamondPrototypeV2"
BLENDER_GROUP_COMMAND_ID = "PatternSurface_BlenderPatterns"
BLENDER_RIBS_COMMAND_ID = "PatternSurface_Blender_DiagonalRibs"
ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons", "pattern_tools.svg")
DIAMOND_ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons", "diamond.svg")
BOLEADO_ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons", "boleado.svg")


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


class BoleadoPatternCommand(DiamondPatternCommand):
    def GetResources(self):
        return {
            "Pixmap": BOLEADO_ICON,
            "MenuText": "Boleado Pattern",
            "ToolTip": "Generate independent rounded bumps on a mapped surface",
        }

    def Activated(self):
        from ..patterns.boleado import command

        maybe_reload(command)
        command.run()


class DiamondPatternPrototypeCommand(DiamondPatternCommand):
    def GetResources(self):
        resources = super().GetResources()
        resources["MenuText"] = "Diamond Pattern Prototype"
        resources["ToolTip"] = "Generate the experimental Diamond Pattern implementation"
        return resources

    def Activated(self):
        from ..patterns.diamond import prototype_command

        maybe_reload(prototype_command)
        prototype_command.run()


class DiamondPatternPrototypeV2Command(DiamondPatternCommand):
    def GetResources(self):
        resources = super().GetResources()
        resources["MenuText"] = "Diamond Pattern Prototype V2"
        resources["ToolTip"] = "Generate the independent V2 surface-following Diamond pattern"
        return resources

    def Activated(self):
        import importlib
        from ..patterns.diamond import v2_command

        importlib.reload(v2_command).run()


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


class BlenderPatternsGroup:
    """Same drop-down pattern list used by native Pattern Tools."""

    def GetResources(self):
        return {"Pixmap": ICON, "MenuText": "Blender Patterns",
                "ToolTip": "Choose a Blender surface pattern"}

    def GetCommands(self):
        return ("PatternSurface_Blender_Diamond", BLENDER_RIBS_COMMAND_ID)

    def GetDefaultCommand(self):
        return 0

    def IsExclusive(self):
        return False
