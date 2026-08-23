import FreeCADGui as Gui

from .map_faces import COMMAND_ID as MAP_FACES_ID, MapFacesCommand
from .pattern_tools import (
    DIAMOND_COMMAND_ID,
    GROUP_COMMAND_ID,
    DiamondPatternCommand,
    PatternToolsGroup,
)
from .trim_surface import COMMAND_ID as TRIM_SURFACE_ID, TrimSurfaceCommand


COMMANDS = [MAP_FACES_ID, GROUP_COMMAND_ID, TRIM_SURFACE_ID]
_registered = False


def register_commands():
    global _registered
    if _registered:
        return
    Gui.addCommand(MAP_FACES_ID, MapFacesCommand())
    Gui.addCommand(DIAMOND_COMMAND_ID, DiamondPatternCommand())
    Gui.addCommand(GROUP_COMMAND_ID, PatternToolsGroup())
    Gui.addCommand(TRIM_SURFACE_ID, TrimSurfaceCommand())
    _registered = True
