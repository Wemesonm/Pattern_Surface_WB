# Pattern_Surface_WB Agent Guide

## Mission

`Pattern_Surface_WB` is a specification-driven FreeCAD workbench with three
separate tools:

1. `Map Faces` creates a generic logical map and physical carrier from adjacent
   faces.
2. `Pattern Tools` creates a registered pattern on a map. Diamond is the first
   pattern.
3. `Trim Surface` clips generated pattern solids to the mapped source faces.

The normative requirements are under `docs/specifications/`. Read the relevant
tool specification and the shared data contract before changing code.

## Required Reading

| Change area | Required specification |
| --- | --- |
| Mapping, adjacency, seams, carrier, or preview | [`docs/specifications/map-faces.md`](docs/specifications/map-faces.md) |
| Pattern registry or pattern generation | [`docs/specifications/pattern-tools.md`](docs/specifications/pattern-tools.md) |
| Envelopes, booleans, or physical clipping | [`docs/specifications/trim-surface.md`](docs/specifications/trim-surface.md) |
| Properties, payloads, schemas, or compatibility | [`docs/specifications/data-contracts.md`](docs/specifications/data-contracts.md) |
| Specification process and status | [`docs/specifications/README.md`](docs/specifications/README.md) |
| Architectural decisions | [`docs/decisions/README.md`](docs/decisions/README.md) |

When a change crosses tool boundaries, read every affected specification.

## Global Engineering Rules

- Specifications are authoritative. Update and approve the requirement before
  implementing behavior that conflicts with it.
- Reference requirement IDs in tests, commits, and checkpoint notes.
- Never special-case a FreeCAD face number, selected-face count, object name,
  fixture, screen direction, or global X/Y/Z direction.
- Multiple selected faces must be handled through topology and shared edges.
- Mapping must never import a pattern package. A pattern consumes the public map
  contract.
- Generic trimming must not generate Diamond geometry.
- Keep `archive/v4_original/` and `archive/v3_stable/` immutable.
- Preserve pcurves and native trimmed parameter intervals.
- Test one geometry hypothesis at a time. Restore the preceding checkpoint when
  visual validation fails.
- Do not push runtime changes to `main` until automated checks and the complete
  visual flow pass.
- Do not add an open-source license without owner approval. The project remains
  all rights reserved.

## Architecture

| Path | Ownership |
| --- | --- |
| `Init.py`, `InitGui.py` | FreeCAD startup entry points only. |
| `pattern_surface/workbench.py` | Workbench, menu, and toolbar registration. |
| `pattern_surface/commands/` | Thin command adapters without geometry. |
| `pattern_surface/common/` | Shared errors, geometry primitives, serialization, selection, and properties. |
| `pattern_surface/mapping/` | Map Faces implementation only. |
| `pattern_surface/patterns/` | Pattern registry and independent pattern packages. |
| `pattern_surface/trimming/` | Generic Trim Surface implementation only. |
| `pattern_surface/compatibility/v4_pipeline.py` | Transitional V4 engine; remove only after extracted equivalence tests pass. |
| `tests/fixtures/` | Versioned FreeCAD regression documents. |
| `archive/` | Immutable macro baselines and experiments. |

## Approved Baselines

- Map Faces `0.1.4` (commit message `checkpoint: best approved Map Faces generic
  grid 0.1.4`) is the current approved baseline. It preserves the periodic
  unwrapping and transverse alignment from `44b8f19`, completes the lower row,
  and adds the independent, component-centered orthogonal grid.
- `44b8f19` remains the previous approved Map Faces baseline (`0.1.2`).
- `ada0549` is the approved Diamond dimension-dialog baseline (`0.1.3`).
- The four-face fixture baseline is 2,642 physical carrier triangles, 68 Diamond
  solids, two rejected external cells, and 68 physically trimmed solids.
- A newer Map Faces baseline may be declared only after visual approval. Record
  the commit, fixture, counts, screenshots, and verdict here and in the Map Faces
  specification.

## Specification-Driven Workflow

1. Identify the owning specification and requirement IDs.
2. Change the specification before changing conflicting runtime behavior.
3. Update `data-contracts.md` for every cross-tool contract change.
4. Create a checkpoint with `python3 scripts/checkpoint.py create <label>`.
5. Implement one testable hypothesis.
6. Link automated tests to requirement IDs in test names or comments.
7. Run automated checks and the specification's visual protocol.
8. Mark a requirement `Implemented` only after its acceptance criteria pass.
9. Restore a failed experiment before starting another.
10. Commit an approved tool baseline separately from unrelated changes.

## Validation Commands

```bash
python3 -m compileall -q .
python3 scripts/verify_install.py
python3 scripts/run_freecad_tests.py
```

Use `tests/fixtures/container_four_faces.FCStd` for the established end-to-end
visual regression. Restart FreeCAD after startup, command-registration, or
toolbar changes; geometry service modules reload on command activation.

## Repository

- Project: `Pattern_Surface_WB`
- Remote: `https://github.com/Wemesonm/Pattern_Surface_WB.git`
- Package version: `pattern_surface/version.py` and `package.xml`
- Active code: `pattern_surface/`
- Development installation: symlink from FreeCAD's `Mod/Pattern_Surface_WB`
  directory to this repository.
