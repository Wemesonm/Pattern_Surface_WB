# Pattern Tools Specification

## Purpose and Ownership

Pattern Tools creates registered patterns on a Map Faces logical coordinate
system. Each pattern package owns its lattice, parameters, cell construction,
solid fallbacks, metadata, and icon.

Pattern Tools does not position source faces, repair map seams, or physically
trim pattern solids.

## Inputs and Selection

`PAT-REQ-001` **Baseline** - A pattern command requires a selected compatible
Map Faces object or its preview object with a resolvable parent.

`PAT-REQ-002` **Specified** - A pattern consumes only the public map properties
and payload defined in `data-contracts.md`; it must not depend on fixture names
or private mapping implementation state.

## Pattern Registry Interface

`PAT-REQ-010` **Baseline** - Every pattern package exposes:

```python
PATTERN_ID = "stable-id"
LABEL = "Visible Label"
ICON = "/absolute/or/package/icon/path.svg"

def get_parameters():
    """Return a JSON-compatible dict, or None when cancelled."""

def create_pattern(map_object, parameters):
    """Create and return a FreeCAD pattern object."""
```

`PAT-REQ-011` **Baseline** - New patterns are added through the registry and an
independent package. Existing pattern modules must not require modification
unless a shared public contract changes.

## User Interface

Pattern Tools is a toolbar/menu group populated from the pattern registry. Each
registered pattern supplies its visible label, icon, and owned parameter dialog.

`PAT-REQ-012` **Baseline** - Selecting a pattern opens only that pattern's
parameter interface. Cancelling returns without creating or modifying document
objects.

## Diamond Pattern

`PAT-REQ-020` **Baseline** - Diamond owns triangular pyramid generation,
canonical cell IDs, clipped cell fragments, apex placement, curved-solid
fallbacks, and rejected-cell reporting.

`PAT-REQ-021` **Specified** - Move `canonical_triangles()`, alternating
half-column row offsets, `up/down` triangle generation, and all Diamond-specific
lattice limits out of mapping and into `patterns/diamond/`.

`PAT-REQ-022` **Implemented in 0.1.5** - Diamond owns its requested triangle height and
derives the natural equilateral side from it. On an open map this natural side
is used unchanged. On a closed periodic component, `PAT-REQ-026` may adjust only
the lateral side; the requested triangle height remains unchanged.

`PAT-REQ-023` **Implemented** - The Diamond dialog asks for `Diamond height`,
`Pyramid height`, and `Closure fit tolerance`. All use millimeters, a minimum of
`0.010 mm`, three decimals, and their last confirmed preference values. The
default closure tolerance is `0.200 mm`. Cancel causes no document or preference
mutation.

`PAT-REQ-024` **Baseline** - Pyramid height is applied along the local outward
surface normal and is explicit in principal and fallback solid paths.

`PAT-REQ-025` **Implemented in 0.1.5** - A closed periodic component must be sampled across
its logical closing seam. Diamond creates one canonical representative for a
cell crossing that seam and must not reject, duplicate, or externally extend it
as though the seam were an open boundary. A local adjacency cycle is not enough
to classify a map as periodic: the seam owners must occupy opposite limits of
the complete logical component.

`PAT-REQ-026` **Implemented in 0.1.5** - Let `P` be the closed logical period, `S` the
natural equilateral side derived from the requested Diamond height, and `N` the
nearest positive integer to `P / S`. If `abs(N * S - P)` is within the
user-supplied closure fit tolerance, Diamond uses the fitted lateral side
`P / N` while preserving the requested vertical triangle height.

`PAT-REQ-027` **Implemented in 0.1.5** - Before applying a non-zero periodic fit, show a
confirmation containing the measured period, module count, natural side,
effective side, total adjustment, and configured tolerance. Cancelling creates
no object and changes no preferences. If the error exceeds the tolerance,
report incompatibility and do not silently fit the lattice.

`PAT-REQ-028` **Implemented in 0.1.5** - A periodic Diamond lattice uses a deterministic
`0.001 mm` logical phase epsilon to prevent lattice vertices from coinciding
exactly with BRep corner transitions. This epsilon changes only lattice origin,
not triangle height, effective side, module count, or closure. Store and reuse
the phase in trimming fallbacks.

## V4 Diamond Migration Ledger

| Functions | Destination | Current status |
| --- | --- | --- |
| `cross2`, `point_in_triangle`, `barycentric`, `interpolate_vertex`, `clip_polygon` | shared geometry and Diamond lattice | Facade |
| `canonical_triangles`, `nearest_carrier`, `extended_triangles` | `patterns/diamond/lattice.py` | Facade; ownership extraction pending |
| `triangular_height_weight`, `face_domain_polygon`, `domain_fragments`, `subtriangle_points`, `solid_from_domain_fragments` | Diamond lattice and solids | Facade |
| `build_carrier_index`, `indexed_carriers`, `carrier_for_point`, `map_carrier_point` | Diamond support lookup | Facade |
| `external_mapping_records`, `map_external_point`, `build_mapping_context`, `map_context_point` | Diamond external mapping | Facade |
| `clipped_cell_fragments`, `choose_cell_component`, `local_cell_context` | Diamond cell clipping | Facade |
| `face_from_triangle`, `dedupe_vectors`, `average_vector`, `sample_polygon_edges`, `cap_faces_from_loop`, `solid_from_fragments` | Diamond solid helpers | Facade |
| `canonical_shell_solid`, `curved_shell_pyramid_solid`, `curved_height_mapped_solid` | Diamond principal/fallback solids | Adapted for explicit relief |
| `validate_physical_lattice`, `choose_outside_apex`, `outside_normal_for_point`, `side_faces_intrude_source` | Diamond validation | Facade/adapted |
| `canonical_lattice_solid`, `curved_lattice_pyramid_solid`, `curved_row_pyramid_solid`, `build_cells` | Diamond generation | Adapted for explicit relief |
| `source_solids_by_face`, `create_full_pattern` | Diamond orchestration | Transitional service |

## Algorithm and Data Flow

1. Resolve the selected map through the public map contract.
2. Read the map grid dimensions, origin, carrier, boundaries, and components.
3. Ask only for parameters owned by the selected pattern.
4. Generate the pattern's canonical logical lattice.
5. Clip or extend candidate cells according to the pattern algorithm.
6. Map cell bases and apexes to the physical carrier.
7. Validate and construct principal or fallback solids.
8. Serialize pattern metadata and create the pattern object.

## Outputs and FreeCAD Objects

`PAT-REQ-030` **Baseline** - Pattern objects expose `PatternId`,
`PatternMapSource`, and `PatternHeight`.

`PAT-REQ-031` **Specified** - Diamond continues exposing compatibility properties
and payload fields while generic consumers migrate. Grid dimensions come from
the referenced map, not duplicated dialog state.

The Diamond payload preserves canonical cell ID, logical base geometry,
physical apex, source carrier references, rejection information, and data needed
by Trim Surface fallbacks.

## Invariants

- Each pattern owns its own lattice.
- Only Diamond may use the staggered triangular lattice.
- A pattern never modifies map transforms, seams, carrier vertices, or grid
  origin.
- Changing pyramid height changes apex relief only; cell bases and IDs remain
  fixed.
- Pattern generation does not physically trim source holes.

## Errors and Warnings

- Error for a missing or invalid map.
- Error for non-positive or non-finite owned parameters.
- Report rejected cells without corrupting accepted solids.
- Cancel closes the parameter dialog without creating or changing objects.

## Compatibility

`PAT-REQ-040` **Baseline** - Read legacy map aliases and Diamond payload fields
according to `data-contracts.md`.

`PAT-REQ-041` **Specified** - During migration, readers accept legacy
`diamond_height`. New payloads distinguish requested `diamond_height`, natural
`diamond_side`, effective `diamond_side`, `closure_fit_tolerance`, module count,
and total closure adjustment.

## Known Limitations and Deferred Work

- Diamond is the only registered pattern.
- Diamond still delegates substantial geometry to the transitional V4 engine.
- Pattern behavior around internal holes relies on future Trim Surface work.
- Removing the legacy Diamond dimension field requires a schema migration.

## Acceptance Tests

Automated:

- registry discovers Diamond through the public interface;
- Diamond lattice code imports no mapping implementation internals beyond the
  public map contract;
- alternating half-column offsets exist only in the Diamond package;
- pyramid height changes apexes but not bases or cell IDs;
- legacy pattern payloads remain readable;
- cancellation creates no objects and changes no preferences.
- a periodic map within the user tolerance fits only its lateral side,
  preserves triangle height, and creates one copy of every seam cell;
- a periodic map outside the user tolerance reports incompatibility.

Visual:

1. Generate Diamond on the approved four-face map.
2. Confirm the staggered triangular lattice remains correct after extraction.
3. Test pyramid heights `0.500`, `1.000`, and `2.000 mm`.
4. Confirm only relief changes and the pattern remains aligned across seams.
