#!/usr/bin/env python3
import pathlib
import sys

from install_dev import WORKBENCH_NAME, freecad_mod_dir


REQUIRED = (
    "Init.py",
    "InitGui.py",
    "package.xml",
    "pattern_surface/workbench.py",
    "pattern_surface/compatibility/v4_pipeline.py",
)


def main():
    target = freecad_mod_dir() / WORKBENCH_NAME
    failures = []
    if not target.is_symlink():
        failures.append("{} is not a development symlink".format(target))
    for relative in REQUIRED:
        if not (target / relative).is_file():
            failures.append("missing {}".format(relative))
    if failures:
        for failure in failures:
            print("ERROR: {}".format(failure), file=sys.stderr)
        return 1
    print("Verified {} -> {}".format(target, pathlib.Path(target).resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
