# Shared Data Contracts

## Purpose

This specification defines the public data exchanged by Map Faces, Pattern
Tools, and Trim Surface. Tool implementations may change internally without
breaking consumers that follow these contracts.

## Schema Rules

`DATA-REQ-001` **Baseline** - Serialized payloads use compressed JSON stored in
`App::PropertyStringList` chunks.

`DATA-REQ-002` **Baseline** - Every payload carries a schema identifier and
version. Increment a schema version for incompatible changes.

`DATA-REQ-003` **Specified** - Readers remain backward compatible whenever
practical and must not mutate source objects while decoding an older schema.

`DATA-REQ-004` **Specified** - Physical carrier triangles and pattern lattice
cells are separate concepts, fields, and ownership domains.

## Shared V4 Migration Ledger

| Functions | Destination | Current status |
| --- | --- | --- |
| `console`, `warn`, `fail`, `run_guard` | `common/errors.py` | Facade |
| `v3`, `xyz`, `norm`, `is_valid_shape`, `qkey2`, `qkey3` | `common/geometry.py` | Facade |
| `area2`, `logical_bounds`, `expand_bounds`, `bounds_overlap`, `carrier_bounds`, `component_logical_bounds` | shared geometry | Facade |
| `add_string`, `add_chunks`, `load_chunks`, `next_name` | properties and serialization | Facade |
| `add_length`, `length_value` | properties | New helpers without V4-original counterparts |

The immutable source inventory is:

| Archived source | Responsibility | Replacement |
| --- | --- | --- |
| `Wrap_faces_V4.FCMacro` | reload core and call `create_wrap` | Map Faces command/service |
| `Diamond_pattern_full_from_wrap_V4.FCMacro` | reload core and create full pattern | Diamond command/service |
| `Cut_diamond_pattern_to_wrap_V4.FCMacro` | reload core and call `create_cut` | Trim Surface command/service |
| `Wrap_pipeline_V4_core.py` | complete V4 pipeline | transitional compatibility engine and modular destinations |

Original V4 constants include `SCHEMA`, `WRAP_PREFIX`, `FULL_PREFIX`,
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

## Pattern Object and Payload

Generic properties:

- `PatternId`;
- `PatternMapSource`;
- `PatternHeight`.

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
- legacy `parameters.height`.

`DATA-REQ-021` **Baseline** - Cell records preserve canonical ID, logical base,
physical apex, carrier references, and fallback data needed by Trim Surface.

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

The current V4 payload uses:

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
