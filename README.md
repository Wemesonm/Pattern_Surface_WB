# Pattern_Surface_WB

FreeCAD workbench for mapping adjacent faces, generating surface patterns, and trimming generated solids to the mapped surface.

## Tools

- **Map Faces** builds the logical carrier and preview grid from selected adjacent faces.
- **Pattern Tools** is a drop-down pattern registry. The first pattern is **Diamond Pattern**.
- **Trim Surface** trims the generated pattern to the mapped source faces.

## Development installation

```bash
python3 scripts/install_dev.py
```

Restart FreeCAD once after installation and select `Pattern_Surface_WB`. Geometry modules are reloaded on every command click, so algorithm edits normally do not require another restart.

## Diamond Pattern

Select a Map Faces result and choose `Pattern Tools > Diamond Pattern`. The command asks for `Diamond height` (the cell dimension on the mapped surface, initially 12 mm) and `Pyramid height` (the relief normal to the surface, initially 1 mm). Both last confirmed values are remembered. Select the map and generated pattern before running `Trim Surface`.

## Status

The modular workbench preserves the V4 geometry engine behind explicit service boundaries. Version 0.1.1 unwraps periodic surface parameters into each trimmed face interval. Version 0.1.2 aligns the transverse grid across a curved face with multiple adjacent sides by prioritizing the already positioned horizontal seam and scaling only its tangent direction. On the four-face fixture, Map Faces produces 2,642 carrier triangles; Diamond produces the same 68 solids at 0.5, 1.0, and 2.0 mm; and Trim Surface produces 68 physically cut solids using the stored height.

Run the automated checks with `python3 scripts/run_freecad_tests.py`. The slower end-to-end geometry check is `tests/integration_full_flow.py`. See `AGENTS.md` for agent rules and [`docs/specifications/`](docs/specifications/README.md) for the normative, tool-specific requirements.
