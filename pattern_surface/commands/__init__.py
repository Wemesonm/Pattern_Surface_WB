import FreeCADGui as Gui

from .map_faces import COMMAND_ID as MAP_FACES_ID, MapFacesCommand
from .pattern_tools import (
    DIAMOND_COMMAND_ID,
    BOLEADO_COMMAND_ID,
    DIAMOND_PROTOTYPE_COMMAND_ID,
    DIAMOND_PROTOTYPE_V2_COMMAND_ID,
    BLENDER_GROUP_COMMAND_ID,
    BLENDER_RIBS_COMMAND_ID,
    GROUP_COMMAND_ID,
    DiamondPatternCommand,
    BoleadoPatternCommand,
    DiamondPatternPrototypeCommand,
    DiamondPatternPrototypeV2Command,
    PatternToolsGroup,
    BlenderPatternsGroup,
)
from .trim_surface import COMMAND_ID as TRIM_SURFACE_ID, TrimSurfaceCommand
from .blender_diamond import COMMAND_ID as BLENDER_DIAMOND_ID, BlenderDiamondCommand
from .blender_ribs import BlenderDiagonalRibsCommand


COMMANDS = [MAP_FACES_ID, GROUP_COMMAND_ID, TRIM_SURFACE_ID]
BLENDER_COMMANDS = [BLENDER_GROUP_COMMAND_ID]
_registered = False


def register_commands():
    global _registered
    if _registered:
        return
    Gui.addCommand(MAP_FACES_ID, MapFacesCommand())
    Gui.addCommand(DIAMOND_COMMAND_ID, DiamondPatternCommand())
    Gui.addCommand(BOLEADO_COMMAND_ID, BoleadoPatternCommand())
    Gui.addCommand(DIAMOND_PROTOTYPE_COMMAND_ID, DiamondPatternPrototypeCommand())
    Gui.addCommand(DIAMOND_PROTOTYPE_V2_COMMAND_ID, DiamondPatternPrototypeV2Command())
    Gui.addCommand(GROUP_COMMAND_ID, PatternToolsGroup())
    Gui.addCommand(TRIM_SURFACE_ID, TrimSurfaceCommand())
    Gui.addCommand(BLENDER_DIAMOND_ID, BlenderDiamondCommand())
    Gui.addCommand(BLENDER_RIBS_COMMAND_ID, BlenderDiagonalRibsCommand())
    Gui.addCommand(BLENDER_GROUP_COMMAND_ID, BlenderPatternsGroup())
    _registered = True
