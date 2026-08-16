#!/usr/bin/env python3
import os
import pathlib
import shutil
import sys


WORKBENCH_NAME = "Pattern_Surface_WB"


def freecad_mod_dir():
    configured = os.environ.get("FREECAD_USER_MOD")
    if configured:
        return pathlib.Path(configured).expanduser()
    if sys.platform == "darwin":
        return pathlib.Path.home() / "Library/Application Support/FreeCAD/v1-1/Mod"
    if os.name == "nt":
        return pathlib.Path(os.environ["APPDATA"]) / "FreeCAD/Mod"
    return pathlib.Path.home() / ".local/share/FreeCAD/Mod"


def install(repo=None):
    source = pathlib.Path(repo or pathlib.Path(__file__).parents[1]).resolve()
    target_dir = freecad_mod_dir()
    target = target_dir / WORKBENCH_NAME
    target_dir.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        if target.resolve() == source:
            print("Development link already installed: {}".format(target))
            return target
        target.unlink()
    elif target.exists():
        raise RuntimeError(
            "Refusing to replace a real directory: {}. Move it first.".format(target))
    target.symlink_to(source, target_is_directory=True)
    print("Installed development link: {} -> {}".format(target, source))
    return target


if __name__ == "__main__":
    try:
        install(sys.argv[1] if len(sys.argv) > 1 else None)
    except Exception as exc:
        print("install_dev failed: {}".format(exc), file=sys.stderr)
        raise SystemExit(1)
