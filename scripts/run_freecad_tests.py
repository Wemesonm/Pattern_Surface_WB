#!/usr/bin/env python3
import os
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).parents[1]
DEFAULT_FREECAD = pathlib.Path("/Applications/FreeCAD.app/Contents/MacOS/FreeCAD")


def main():
    executable = pathlib.Path(os.environ.get("FREECAD_CMD", DEFAULT_FREECAD))
    if not executable.is_file():
        print("FreeCAD executable not found: {}".format(executable), file=sys.stderr)
        return 2
    tests = sorted((ROOT / "tests").glob("test_*.py"))
    command = [str(executable), "-c", str(ROOT / "tests" / "freecad_test_runner.py")]
    print("Running {} test modules with {}".format(len(tests), executable))
    return subprocess.call(command, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
