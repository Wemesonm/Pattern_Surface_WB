#!/usr/bin/env python3
import argparse
import hashlib
import json
import pathlib
import shutil
from datetime import datetime, timezone


ROOT = pathlib.Path(__file__).parents[1]
CHECKPOINTS = ROOT / ".checkpoints"
TRACKED = ("pattern_surface", "Init.py", "InitGui.py", "package.xml")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create(label):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = CHECKPOINTS / "{}_{}".format(stamp, label)
    destination.mkdir(parents=True)
    manifest = {"created_utc": stamp, "label": label, "files": {}}
    for relative in TRACKED:
        source = ROOT / relative
        target = destination / relative
        if source.is_dir():
            shutil.copytree(source, target)
        elif source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for path in destination.rglob("*"):
        if path.is_file():
            manifest["files"][str(path.relative_to(destination))] = digest(path)
    (destination / "checkpoint.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(destination)


def restore(name):
    source = CHECKPOINTS / name
    if not (source / "checkpoint.json").is_file():
        raise RuntimeError("Unknown checkpoint: {}".format(name))
    for relative in TRACKED:
        saved = source / relative
        target = ROOT / relative
        if not saved.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists() or target.is_symlink():
            target.unlink()
        if saved.is_dir():
            shutil.copytree(saved, target)
        else:
            shutil.copy2(saved, target)
    print("Restored {}".format(source))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create_parser = sub.add_parser("create")
    create_parser.add_argument("label")
    restore_parser = sub.add_parser("restore")
    restore_parser.add_argument("name")
    args = parser.parse_args()
    create(args.label) if args.command == "create" else restore(args.name)


if __name__ == "__main__":
    main()
