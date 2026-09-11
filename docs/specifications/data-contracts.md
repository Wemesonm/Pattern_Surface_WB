# Shared Data Contracts

## Purpose

This specification defines the public data exchanged by Map Faces, Pattern
Tools, and Trim Surface. Tool implementations may change internally without
breaking consumers that follow these contracts.

## Schema Rules

`DATA-REQ-056` **Implemented** — Optional transient `native_boundary_curves` are
sampled from native selected-face wire edges with 0.005 mm chord tolerance.
Shared selected edges and periodic seams are excluded by topological incidence,
never triangle incidence. Records retain component, source face, ordered physical
points and inward atlas direction for lower-edge classification. Extraction must
verify closed boundary cycles and must not rewrite saved maps. Legacy readers
ignore this optional field; Blender Diamond requests it only when its optional
concave rim transition is enabled.

`DATA-REQ-053` **Implemented** — Blender packaging refreshes legacy trimmed curved
carrier domains from referenced CAD faces without rewriting saved maps. Optional
`boundary_support_planes` contains origin/normal pairs from adjacent native
planar faces only when the complete selected surface lies on their inside side.
These are physical trimming constraints, independent of pattern dimensions.
The Exact Blender cut preserves cavities and facets. Acceptance: rotated tube
volume/cavity regression, native inclined cylinder tests and real saved-map
packaging without modifying MapPayloadChunks (2026-09-10).

`DATA-REQ-054` **Implemented** — Resolve near-coincident Exact cut contacts with a
0.0002 mm outward numerical guard, then project retained outside vertices onto
the original CAD support plane. The guard is not an allowance to enlarge the
model: final boundary validation uses the original plane and 0.001 mm tolerance.
This avoids overlapping cap sheets when full local-normal relief meets the rim.
After projection, dissolve numerical degeneracies at 0.00001 mm; do not remesh
or smooth the physical Diamond facets. Validate the result after this cleanup.

`DATA-REQ-001` **Baseline** - Serialized payloads use compressed JSON stored in
`App::PropertyStringList` chunks.

`DATA-REQ-002` **Baseline** - Every payload carries a schema identifier and
version. Increment a schema version for incompatible changes.

`DATA-REQ-003` **Specified** - Readers remain backward compatible whenever
practical and must not mutate source objects while decoding an older schema.

`DATA-REQ-004` **Specified** - Physical carrier triangles and pattern lattice
cells are separate concepts, fields, and ownership domains.

## Shared Migration Ledger

| Functions | Destination | Current status |
| --- | --- | --- |
| `console`, `warn`, `fail`, `run_guard` | `common/errors.py` | Facade |
| `v3`, `xyz`, `norm`, `is_valid_shape`, `qkey2`, `qkey3` | `common/geometry.py` | Facade |
| `area2`, `logical_bounds`, `expand_bounds`, `bounds_overlap`, `carrier_bounds`, `component_logical_bounds` | shared geometry | Facade |
| `add_string`, `add_chunks`, `load_chunks`, `next_name` | properties and serialization | Facade |
| `add_length`, `length_value` | properties | New helpers without V4-original counterparts |

The immutable source inventory is retained under `archive/`; it is not part of the active runtime. The active workbench uses the neutral geometry engine and modular ownership boundaries.

The historical source inventory is:

| Archived source | Responsibility | Replacement |
| --- | --- | --- |
| `Wrap_faces_V4.FCMacro` | reload core and call `create_wrap` | Map Faces command/service |
| `Diamond_pattern_full_from_wrap_V4.FCMacro` | reload core and create full pattern | Diamond command/service |
| `Cut_diamond_pattern_to_wrap_V4.FCMacro` | reload core and call `create_cut` | Trim Surface command/service |
| `Wrap_pipeline_V4_core.py` | complete V4 pipeline | neutral geometry engine and modular destinations |

Historical V4 constants include `SCHEMA`, `WRAP_PREFIX`, `FULL_PREFIX`,
`CUT_PREFIX`, `BUILD_ID`, `GRID_HEIGHT`, `GRID_SIDE`, `RELIEF`, `CONTACT`,
`MAX_EDGE`, `SAG`, `EDGE_TOL`, `LOGICAL_TOL`, `MAX_CYCLE_ADJUST`,
`CELL_SUBDIVISIONS`, `EXTERNAL_ROW_LIMIT`, `EXTERNAL_ENDPOINT_LIMIT`,
`EXTERNAL_INWARD_TOL`, `MAX_LATTICE_STEP`, `MAX_CANONICAL_EDGE`,
`CUT_FRONT_MARGIN`, and `CUT_REAR_MARGIN`. Ownership follows the tool
specifications; Diamond constants must not remain dependencies of Map Faces.

## Map Object

Generic properties:

- `MapVersion`;
- `MapAlgorithm`;
- `MapReady`;
- `MapPayloadChunks`;
- `MapColumnWidth`;
- `MapRowHeight`;
- `MapGridOrigin`;
- `MapClosureTolerance`;
- `MapCompatible`;
- `MapIncompatibleCount`;
- `MapCompatibilityReport`.

Legacy properties retained during migration:

- `WrapVersion`;
- `WrapAlgorithm`;
- `WrapReady`;
- `WrapSourceFaces`;
- `WrapAdjacency`;
- `WrapCarrierChunks`.

`DATA-REQ-010` **Specified** - The generic map payload contains:

```text
schema, version, grid, bounds, faces[], carrier_triangles[],
boundary_loops[], external_segments[], adjacency[], seams[],
periodic_seams[], periodic_adjustments[], components[], compatibility
```

`grid` contains independent `column_width`, `row_height`, `origin`, and
`closure_tolerance`.

`compatibility` contains overall status, segment records, cycle records, arc
records, and warning geometry references.

`DATA-REQ-011` **Baseline** - A face record preserves source object and
subelement, native parameter range, metric tables, logical dimensions,
orientation signs, normal sign, transform, and component.

`DATA-REQ-012` **Baseline** - A physical carrier vertex preserves logical `q`,
physical `p`, normal `n`, and required UV/face ownership data.

`DATA-REQ-013` **Specified** - Boundary loop records distinguish `outer` and
`inner` roles and preserve face ownership, ordered logical points, physical
edge references, and whether the loop participates in selected adjacency.

`DATA-REQ-014` **Specified** - The physical carrier remains serialized under
`carrier_triangles`. It must never be interpreted as Diamond or another
pattern's cells.

`DATA-REQ-015` **Implemented** — New map objects expose the `MapOwnerGroup`
object name plus `MapSourceBodies` links; single-Body maps also expose
`MapSourceBody`. The group name avoids a dependency cycle because the group
already owns the map object. These associations organize the document tree and
identify ownership for consumers without altering the serialized payload or the
source Body's Part Design history.

## Pattern Object and Payload

Generic properties:

- `PatternId`;
- `PatternMapSource`;
- `PatternHeight`.

Diamond periodic-fit properties may additionally expose requested triangle
height, natural lateral side, effective lateral side, fit tolerance, module
count, and accumulated closure adjustment.

`DATA-REQ-020` **Specified** - A generic pattern payload contains:

```text
schema, version, pattern_id, map_source, map_schema,
parameters, cells[], rejected_cells[], generation
```

`parameters` contains only values owned by the pattern. Grid dimensions are
read from the referenced map.

Diamond compatibility properties and fields remain readable during migration:

- `DiamondHeight`;
- `DiamondPatternVersion`;
- `DiamondPatternAlgorithm`;
- `DiamondPatternWrapSource`;
- `DiamondPatternRejected`;
- `DiamondPatternCellChunks`;
- `parameters.diamond_height`;
- `parameters.pyramid_height`;
- `parameters.diamond_side`;
- `parameters.natural_diamond_side`;
- `parameters.closure_fit_tolerance`;
- `parameters.closure_modules`;
- `parameters.closure_adjustment`;
- `parameters.periodic_phase`;
- legacy `parameters.height`.

`DATA-REQ-021` **Baseline** - Cell records preserve canonical ID, logical base,
physical apex, carrier references, and fallback data needed by Trim Surface.

`DATA-REQ-022` **Implemented** — A pattern or trim result generated from a map
with `MapOwnerGroup` is placed in that group and links its source Body/bodies.
Older maps without ownership links remain valid and retain document-root output.

## Trim Object and Payload

Generic properties:

- `PatternId`;
- `PatternMapSource`;
- `PatternSource`;
- `PatternHeight`.

`DATA-REQ-030` **Specified** - A generic trim payload contains:

```text
schema, version, pattern_id, map_source, pattern_source,
map_schema, pattern_schema, pattern_height, accepted_cells[],
rejected_cells[], envelope_strategy, fallback_strategy
```

Legacy Diamond trim properties remain readable until a versioned migration
removes them.

## Legacy Map Aliases

Archived V4 payloads are read through legacy aliases; new payloads use the active schema.

```text
schema, version, grid_height, grid_side, max_edge, sag, bounds,
faces[], triangles[], external_segments[], adjacency[],
periodic_seams[], periodic_adjustments[], components[]
```

`DATA-REQ-040` **Specified** - During migration:

- legacy `grid_side` maps to generic `grid.column_width`;
- legacy `grid_height` maps to generic `grid.row_height`;
- legacy `triangles` maps to generic `carrier_triangles`;
- `WrapCarrierChunks` and `MapPayloadChunks` may contain identical payloads;
- missing grid origin uses the legacy logical origin behavior;
- missing compatibility data means `unknown`, not automatically compatible.

`DATA-REQ-041` **Specified** - New writers emit generic fields and required
legacy aliases until all archived fixtures and active consumers pass migration
tests.

## Ownership and Dependency Rules

- Map Faces writes map properties and map payloads.
- A pattern reads a map and writes only its own pattern object and payload.
- Trim Surface reads map and pattern data and writes only its trim result.
- Mapping does not import pattern schemas.
- Generic trim code may inspect `PatternId` but does not infer Diamond geometry
  from carrier triangles.

## Error Handling

- Unknown future schema versions fail with a clear compatibility error.
- Missing optional legacy aliases use documented defaults.
- Missing required identity, geometry, or association fields fail before
  geometry mutation.
- Decode errors identify the object and property without dumping compressed
  payload contents.

## Acceptance Tests

- round-trip every generic payload;
- decode archived V4 map, Diamond, and trim payloads;
- distinguish carrier triangles from pattern cells;
- resolve generic fields and legacy aliases consistently;
- reject unsupported future schema versions;
- verify reading old objects causes no mutation.

## Blender job package

`DATA-REQ-050` **Implemented** — Version 1 `auzyron.blender-job` JSON carries units
`mm`, source document/map identity, complete public map payload, source-body
 mesh filename and pattern-owned parameters. `geometry_module` identifies the
 bundled generator and `pattern_label` identifies the resulting Blender object;
 both default to the approved Diamond generator for compatible callers. The package contains no executable code
from the document. A bundled worker reads it with JSON, creates a new result
project, and writes a structured success/failure report for preflight. The
package is transient: after the interactive Blender scene has loaded, the
bridge removes the JSON, source mesh, reports, and any generated result files.
Periodic fit and requested dimensions are recorded; source objects are never
mutated.

`DATA-REQ-055` **Implemented** — A job may select a bundled boundary solver.
The default remains `EXACT`, preserving Diamond's approved path. Diagonal Ribs
uses `MANIFOLD` only after its closed, welded height field is independently
validated; the choice is stored in the transient job and does not alter native
patterns or a saved document.

`DATA-REQ-052` **Implemented** — Blender Diamond receives the requested
`DiamondHeight`, `PatternHeight`, and closure tolerance from its own dialog.
Map Faces preview spacing is never used as a Diamond dimension. The periodic
side is fitted from the requested Diamond size and the mapped period.

`DATA-REQ-042` **Specified** — Map grid dimensions describe the generic preview,
not the Diamond population. Diamond uses its own requested triangle height and
closure-fitted side with map bounds/carrier. No payload schema change is required;
legacy count-based maps remain valid inputs. This clarifies DATA-REQ-020.

`DATA-REQ-051` **Specified** — Blender jobs may include `body_topology` with
CAD validity, solid count, shell count and material volume in mm³. Source mesh
winding is preserved. A CAD-certified single solid may have internal cavity
shells; its mesh must match the certified shell count, have zero nonmanifold
edges, and agree with CAD material volume within max(0.1 mm³, 0.5%). Legacy
jobs without this metadata keep the single-component check.
