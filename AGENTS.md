# Pattern_Surface_WB Agent Guide

## Mission

`Pattern_Surface_WB` is a FreeCAD workbench that separates the established macro flow into three tools:

1. `Map Faces`: map any connected set of adjacent faces into a logical carrier.
2. `Pattern Tools`: create a registered pattern on that carrier. The first implementation is Diamond.
3. `Trim Surface`: trim generated pattern solids with the physical mapped-face envelopes.

The V4 geometry is the behavioral baseline. Do not fix the known periodic-face mapping defect while restructuring or proving equivalence. Do not special-case `Face4`, `Face8`, `Face14`, four faces, or any model-specific object name.

## Repository Rules

- Active code lives under `pattern_surface/`.
- `archive/v4_original/` is immutable reference material. Never edit it.
- `archive/v3_stable/` is the last accepted V3 snapshot. Never edit it.
- The development install is a symlink from FreeCAD's `Mod/Pattern_Surface_WB` to this repository.
- Geometry modules reload on every command click. A FreeCAD restart is only required after changing startup or command-registration code.
- Before a geometry experiment run `python3 scripts/checkpoint.py create <short-label>`.
- Test one hypothesis at a time. If visual validation fails, restore that checkpoint before starting the next hypothesis.
- Push to `main` only after automated checks and the full visual flow pass.
- Current copyright policy is `All rights reserved`; do not add an open-source license without owner approval.

## Directory Ownership

| Path | Responsibility |
| --- | --- |
| `Init.py`, `InitGui.py` | FreeCAD startup entry points only. |
| `pattern_surface/workbench.py` | Workbench, toolbar, and menu registration. |
| `commands/` | Thin FreeCAD command adapters; no geometry. |
| `common/` | Errors, vectors, serialization, selection, and FreeCAD properties. |
| `mapping/` | Face graph, orientation, parameterization, seams, carrier, and preview. |
| `patterns/registry.py` | Pattern descriptors and command discovery. |
| `patterns/diamond/` | Diamond parameters, lattice, solids, and metadata only. |
| `trimming/` | Generic envelopes, booleans, selection validation, and trimming. |
| `compatibility/v4_pipeline.py` | Transitional V4 engine; delete only after extracted equivalence tests pass. |
| `tests/fixtures/` | Versioned FreeCAD documents used for repeatable tests. |
| `archive/` | Immutable macro baselines and old experiments. |

## Public Pattern Contract

Every pattern package provides:

```python
PATTERN_ID = "stable-id"
LABEL = "Visible Label"
ICON = "/absolute/or/package/icon/path.svg"

def get_parameters():
    """Return a JSON-compatible dict, or None when the dialog is cancelled."""

def create_pattern(map_object, parameters):
    """Create and return a FreeCAD pattern object."""
```

Register the corresponding command descriptor in `patterns/registry.py`. Mapping must never import a pattern package.

## Diamond Height Contract

- Dialog title: `Diamond Pattern`.
- Field: `Triangle height (mm):`.
- First default: `1.000 mm`; minimum: `0.010 mm`; precision: three decimals.
- Preference: `BaseApp/Preferences/Mod/Pattern_Surface_WB/Patterns/Diamond/LastHeight`.
- Cancel makes no document or preference change.
- Height is measured along the local outward surface normal.
- The base mapping must remain fixed when height changes.
- `height` is explicit through every principal and fallback solid path.
- Pattern and cut objects store `PatternHeight` as `App::PropertyLength`.
- Pattern payload stores `parameters.height`.
- Trim reads the stored height and never asks again.

## FreeCAD Object Schemas

### Map Object

Generic properties:

- `MapVersion`: current object schema version.
- `MapAlgorithm`: mapping algorithm identifier; currently `WRAP_CARRIER_V4`.
- `MapReady`: string compatibility flag.
- `MapPayloadChunks`: compressed JSON map payload.

Legacy properties retained during migration:

- `WrapVersion`, `WrapAlgorithm`, `WrapReady`.
- `WrapSourceFaces`, `WrapAdjacency`, `WrapCarrierChunks`.

The preview object stores `WrapParentRun`. A later schema revision may add `MapParentRun`, but do not remove the legacy property before migration tests cover old documents.

### Pattern Object

Generic properties:

- `PatternId`, initially `diamond`.
- `PatternMapSource`: internal name of the map object.
- `PatternHeight`: FreeCAD length.

Diamond compatibility properties:

- `DiamondPatternVersion`, `DiamondPatternAlgorithm`.
- `DiamondPatternWrapSource`, `DiamondPatternRejected`.
- `DiamondPatternCellChunks`: compressed JSON containing `cells` and `parameters.height`.

### Trim Object

Generic properties:

- `PatternId`, `PatternMapSource`, `PatternSource`, `PatternHeight`.

Diamond compatibility properties:

- `DiamondPatternVersion`, `DiamondPatternAlgorithm`.
- `DiamondPatternWrapSource`, `DiamondPatternFullSource`.
- `DiamondPatternRejected`, `DiamondPatternCellChunks`.

## Payloads

`MapPayloadChunks` and `WrapCarrierChunks` currently contain identical compressed JSON:

```text
schema, version, grid_height, grid_side, max_edge, sag, bounds,
faces[], triangles[], external_segments[], adjacency[],
periodic_seams[], periodic_adjustments[], components[]
```

Each face record contains source object/subelement, native parameter range, metric tables, logical dimensions, orientation signs, normal sign, transform, and component. Carrier vertices contain logical `q`, physical `p`, normal `n`, UV and face ownership data.

The Diamond cell payload contains `cells[]` and `parameters.height`. Cell records preserve canonical ID, logical geometry, physical apex, and data required by the trimming fallback.

## Source Inventory

The four V4 sources are archived verbatim:

| Original source | Responsibility | Current consumer | Status |
| --- | --- | --- | --- |
| `Wrap_faces_V4.FCMacro` | Reload core and call `create_wrap`. | `commands/map_faces.py` -> `mapping/service.py` | Replaced by command; archived and equivalence-covered. |
| `Diamond_pattern_full_from_wrap_V4.FCMacro` | Reload core and call `create_full_pattern`. | Diamond command and solids service | Replaced by command; archived and equivalence-covered. |
| `Cut_diamond_pattern_to_wrap_V4.FCMacro` | Reload core and call `create_cut`. | `commands/trim_surface.py` -> trimming service | Replaced by command; archived and equivalence-covered. |
| `Wrap_pipeline_V4_core.py` | Complete V4 geometry pipeline. | Transitional compatibility engine and modular facades | Copied intact to archive; active copy adapted for explicit height and generic metadata. |

Original constants: `SCHEMA`, `WRAP_PREFIX`, `FULL_PREFIX`, `CUT_PREFIX`, `BUILD_ID`, `GRID_HEIGHT`, `GRID_SIDE`, `RELIEF`, `CONTACT`, `MAX_EDGE`, `SAG`, `EDGE_TOL`, `LOGICAL_TOL`, `MAX_CYCLE_ADJUST`, `CELL_SUBDIVISIONS`, `EXTERNAL_ROW_LIMIT`, `EXTERNAL_ENDPOINT_LIMIT`, `EXTERNAL_INWARD_TOL`, `MAX_LATTICE_STEP`, `MAX_CANONICAL_EDGE`, `CUT_FRONT_MARGIN`, and `CUT_REAR_MARGIN`. Active V4 replaces only `RELIEF` with `DEFAULT_PATTERN_HEIGHT`; runtime height is explicit.

## Complete Function Migration Ledger

Every original core function is listed below. `Facade` means the implementation still lives in `compatibility/v4_pipeline.py` and the named module exposes or consumes it. `Adapted` means the active copy intentionally differs from the immutable original. The equivalence test asserts that no original function name disappeared.

| Original functions | Responsibility | Destination / consumers | Status and test |
| --- | --- | --- | --- |
| `console`, `warn`, `fail`, `run_guard` | Reporting and guarded execution | `common/errors.py`; all services | Facade; `test_imports.py`. |
| `v3`, `xyz`, `norm`, `is_valid_shape`, `qkey2`, `qkey3` | Vector/shape primitives and quantization | `common/geometry.py`; mapping, patterns, trim | Facade; imports and geometry integration. |
| `add_string`, `add_chunks`, `load_chunks`, `next_name` | Properties and compressed JSON | `common/properties.py`, `common/serialization.py` | Facade; mapping/diamond/trim equivalence. |
| `outer_edges`, `endpoints`, `same_edge`, `shared_edge`, `selected_faces`, `source_solid` | Selection and topological edge identity | `common/selection.py`, `mapping/adjacency.py` | Facade; mapping equivalence. |
| `parameter_range`, `face_center`, `axis_length_table`, `interp`, `edge_fraction`, `local_xy_raw`, `local_xy`, `local_uv`, `apply_transform`, `invert_transform`, `point_from_logical` | Surface parameterization and logical atlas conversion | `mapping/parameterization.py` | Facade; periodic seam regression fixed in 0.1.1. |
| `outward`, `tangent`, `orient_entry`, `signed_normal_at`, `edge_midpoint`, `align_connected_normals` | Local axes and consistent normals | `mapping/orientation.py` | Facade; mapping integration. |
| `edge_samples`, `apply_matrix`, `aligned_edge_samples`, `seam_limit`, `neighbor_transform_candidates`, `seam_matrix_error`, `fit_neighbor_to_constraints`, `fit_neighbor` | Pairwise seam fitting | `mapping/seams.py` | Facade; seam visual protocol. |
| `build_graph`, `components` | Adjacency graph and connected components | `mapping/adjacency.py` | Facade; must support N adjacent faces. |
| `transformed_entry_bounds`, `snap_lower_curved_strips_to_grid`, `position_components`, `atlas_seam_pairs`, `edge_direction_matches`, `add_logical_seam_overrides`, `seam_override` | Component placement and logical seam rules | `mapping/seams.py` | Facade; mapping equivalence. |
| `mapped_vertex`, `split_carrier_triangle`, `tessellated_carrier`, `entry_contains_logical`, `regular_curved_carrier`, `midpoint_vertex`, `weld_logical_nodes`, `refine_conforming_round`, `conforming_carrier` | Physical carrier construction | `mapping/carrier.py` | Facade; carrier counts and visual comparison. |
| `validate_logical_seams`, `triangle_edge_key`, `third_point_2d`, `cycle_seam_pairs`, `rotate_component`, `close_periodic_component`, `unfold_carrier` | Seam validation and periodic closure | `mapping/seams.py` and carrier internals | Facade; periodic interval regression covered, broader cycle cases pending. |
| `point_on_edge`, `external_segments` | External boundary extraction | `mapping/carrier.py` | Facade; preview and Diamond boundary tests. |
| `area2`, `logical_bounds`, `expand_bounds`, `bounds_overlap`, `carrier_bounds`, `component_logical_bounds` | 2D bounds helpers | `common/geometry.py`, carrier and Diamond | Facade; static and integration tests. |
| `line_triangle_points`, `carrier_preview` | Preview isolines | `mapping/preview.py` | Facade; screenshot protocol. |
| `entry_record`, `create_wrap`, `resolve_wrap_selection`, `hydrate_entries` | Map orchestration and persistence | `mapping/service.py` | `create_wrap` adapted with generic metadata; mapping equivalence. |
| `cross2`, `point_in_triangle`, `barycentric`, `interpolate_vertex`, `clip_polygon` | 2D triangle operations | `common/geometry.py`, `patterns/diamond/lattice.py` | Facade; Diamond integration. |
| `canonical_triangles`, `nearest_carrier`, `extended_triangles` | Canonical Diamond grid and support lookup | `patterns/diamond/lattice.py` | Facade; Diamond counts. |
| `face_from_triangle`, `dedupe_vectors`, `average_vector`, `sample_polygon_edges`, `cap_faces_from_loop`, `solid_from_fragments` | Solid construction helpers | `patterns/diamond/solids.py` | Facade; solid validity tests. |
| `canonical_shell_solid`, `curved_shell_pyramid_solid`, `curved_height_mapped_solid` | Principal and fallback pyramid solids | `patterns/diamond/solids.py` | Adapted: explicit `height`; `test_diamond_height.py` and three-height visual test. |
| `triangular_height_weight`, `face_domain_polygon`, `domain_fragments`, `subtriangle_points`, `solid_from_domain_fragments` | Height interpolation and clipped domains | `patterns/diamond/lattice.py`, solids | Facade except callers pass explicit height. |
| `build_carrier_index`, `indexed_carriers`, `carrier_for_point`, `map_carrier_point` | Indexed carrier lookup | `patterns/diamond/lattice.py` / solids | Facade; Diamond integration. |
| `external_mapping_records`, `map_external_point`, `build_mapping_context`, `map_context_point` | Mapping outside the physical boundary | `patterns/diamond/lattice.py` / solids | Facade; external row tests. |
| `clipped_cell_fragments`, `choose_cell_component`, `local_cell_context` | Cell clipping and local context | `patterns/diamond/lattice.py` | Facade; Diamond integration. |
| `validate_physical_lattice`, `choose_outside_apex`, `outside_normal_for_point`, `side_faces_intrude_source` | Apex direction and solid validation | `patterns/diamond/solids.py` | `choose_outside_apex` adapted for height; solid validity tests. |
| `canonical_lattice_solid`, `curved_lattice_pyramid_solid`, `curved_row_pyramid_solid`, `build_cells` | Diamond generation and fallback chain | `patterns/diamond/solids.py` | Adapted: explicit `height`; height and equivalence tests. |
| `build_cut_cells`, `exact_face_cut_envelope`, `fused_cut_envelopes`, `physical_cut_piece`, `build_cut_cells_from_full` | Physical trim and rebuild fallback | `trimming/envelopes.py`, `trimming/booleans.py` | Envelope/full cut adapted to stored height; trim tests. |
| `source_solids_by_face`, `create_full_pattern` | Pattern orchestration | Diamond command/solids | Adapted: explicit height and generic metadata; Diamond tests. |
| `resolve_cut_selection`, `create_cut` | Pattern/map association and cut orchestration | `trimming/service.py` | Adapted: generic metadata plus legacy compatibility and stored height; trim tests. |

New helpers `add_length` and `length_value` belong to `common/properties.py`; they have no V4-original counterpart.

## General Topology Requirements

- Input may contain any positive number of selected faces.
- With multiple faces, every face must belong to the same connected adjacency component.
- The topology may be a strip, branch, or cycle. Ordering from selection or OCC face number is not semantic.
- Match adjacency using shared topological edges and geometry tolerances.
- Orient normals through the graph and detect contradictory cycles.
- Never base behavior on a hard-coded face number, screen direction, global X/Y/Z, or the current four-face fixture.
- Preserve pcurves and the native trimmed parameter interval of each face.

## Periodic Face Mapping Regression

The current fixture exposes one bad lower-left face. Investigation found:

- `Face8` is toroidal and its native parameter range is consistent.
- `Face14` is cylindrical with native U approximately `0 .. pi/2`, while the V4 `parameter_range()` derives `0 .. 2*pi`.
- `Face4` is cylindrical with native U approximately `3*pi/2 .. 2*pi`, while V4 also derives `0 .. 2*pi`.
- The physical shared edge between `Face14` and `Face8` is about `11.938052 mm`, but the logical atlas maps the Face14 side to about `35.7998 mm`.

This explained the displaced/duplicated preview lines: trimmed periodic surfaces were being expanded to the full underlying surface domain. Curves WB's Sketch on Surface and Map on Face implementations demonstrated the relevant technique: seam-aware parameter unwrapping around the trimmed `ParameterRange`.

Resolved in 0.1.1 by `surface_period()`, `unwrap_parameter()`, and `surface_parameters()`. Every periodic U/V value returned by the support surface is shifted by an integer number of periods to the representation nearest the center of the trimmed face interval. The same normalization is used while deriving the parameter range and while converting physical points to logical coordinates. Using `face.ParameterRange` alone is not sufficient because later calls to `Surface.parameter(point)` can still return the equivalent value on the opposite side of the seam.

Regression fixture result: `Face14` logical curved length changed from the incorrect `35.7998 mm` to `11.9378 mm`, carrier triangles changed from 2,615 to 2,642, Diamond creates 68 solids with two rejected external cells, and physical trim creates 68 solids.

## Multi-Seam Grid Alignment Regression

After the periodic interval fix, the lower-left curved face had its complete lower boundary but its transverse grid lines did not meet those of the upper face. The fixture diagnosis showed that `Face8` has two already positioned neighbors. The atlas selected `Face14 <-> Face8`, a vertical side seam, as primary and ignored the horizontal `Face4 <-> Face8` seam that carries the transverse grid phase. The selection error came from scoring the target face's local edge orientation before the placed seam's global logical orientation.

Resolved in 0.1.2 by prioritizing the orientation of the already positioned seam. For curved seams, `neighbor_transform_candidates()` maps the target seam basis to the placed seam basis with anisotropic scaling: `dl / sl` only in the tangent direction and scale `1.0` in the perpendicular direction. This matches a boundary whose local metric was sampled at another radius without moving an already aligned perpendicular side seam. The fixture uses tangent scale `1.080146` because the target logical edge is `43.6262 mm` and the placed shared edge is `47.1227 mm`.

The regression test samples all four adjacency pairs at nine positions after atlas placement and requires both logical coordinates to agree to four decimal places. This rule is topology-driven: no face number, selected-face count, object name, or torus-specific conditional is allowed. Full-flow results remain 2,642 carrier triangles, 68 Diamond solids at each tested height, and 68 trimmed solids.

Related future isolated experiments, if another periodic topology fails:

1. Build boundary logical coordinates directly from edge pcurves.
2. Unwrap periodic U/V values relative to the shared pcurve when the trimmed interval spans more than half a period.
3. Score orientation candidates by full shared-edge residual, endpoints, tangent direction, and interval length.
4. Add a cycle-closure optimization only after pairwise seams are correct.

Each experiment gets its own checkpoint and visual verdict. Do not combine them.

## Validation Protocol

Automated:

```bash
python3 -m compileall -q .
python3 scripts/verify_install.py
python3 scripts/run_freecad_tests.py
```

Visual baseline with `tests/fixtures/container_four_faces.FCStd`:

1. Select the same four adjacent faces used by the archived V4 baseline.
2. Run `Map Faces`; record selected face count, adjacency, carrier triangle count, object properties, and screenshot.
3. Select the map and run Diamond at `0.500`, `1.000`, and `2.000 mm`.
4. Confirm only apex height changes; triangle bases and cell IDs remain fixed.
5. Confirm `PatternHeight` and payload height match each run.
6. Select map plus pattern and run `Trim Surface`.
7. Confirm Trim uses stored height, preserves pattern geometry, and records its sources.
8. Close and reopen FreeCAD; confirm the last accepted height is remembered.
9. Compare solids, rejected cells, carrier triangles, properties, and visible seams against V4.

For the known face bug, acceptance is visual and geometric: no isolated line above the seam, no line fan in the lower-left corner, no duplicated border, no missing last row, and all grid lines continue across adjacent faces.

## Checkpoint and Rollback

```bash
python3 scripts/checkpoint.py create before-native-range
python3 scripts/checkpoint.py restore <checkpoint-directory-name>
```

Record in the commit message or task notes: hypothesis, changed functions, fixture, measured counts, screenshot, verdict. A failed test is restored before the next test. Archived V3/V4 sources are not used as a blunt overwrite of active modules.

## Installation and Reload

```bash
python3 scripts/install_dev.py
python3 scripts/verify_install.py
```

The link target is normally `~/Library/Application Support/FreeCAD/v1-1/Mod/Pattern_Surface_WB` on macOS. Command adapters reload their service and geometry module on activation. Restart FreeCAD after changing `InitGui.py`, `workbench.py`, command IDs, or toolbar composition.

## Versioning and GitHub

- Package version is in `pattern_surface/version.py` and `package.xml`.
- `BUILD_ID` must identify the exact active build in FreeCAD's Report View.
- Increment schema versions only for incompatible serialized payload changes.
- Keep readers backward compatible for versioned payloads whenever practical.
- Remote: `https://github.com/Wemesonm/Pattern_Surface_WB.git`.
- Direct `main` publication is allowed by the owner only after the full flow is validated.
- Commit archives and the fixture so regressions remain reproducible.

## Current Migration State

- Workbench and three command surfaces: migrated.
- Pattern registry and Diamond height dialog: migrated.
- Original V3/V4 archives and fixture: present.
- Modular namespaces: present as transitional facades.
- V4 explicit height and generic metadata: adapted and automated checks passing.
- Physical integration on the four-face fixture: passing with 2,642 carrier triangles, 68 solids at each tested height, and 68 physically trimmed solids.
- Interactive toolbar registration: validated after FreeCAD restart; all three tools and the Diamond group command are present.
- The lower-left periodic face regression is corrected and covered by normalized-interval and full-flow tests.
- Periodic interval unwrapping: validated in 0.1.1; broader periodic cycle fixtures remain future work.
- Curved multi-seam transverse grid alignment: validated in 0.1.2 with all four fixture seams at zero sampled logical error.
