# Map Faces Specification

## Purpose and Ownership

Map Faces converts a connected selection of FreeCAD faces into a shared logical
2D atlas and a physical interpolation carrier. It also presents a generic,
orthogonal reference grid comparable to graph paper.

Map Faces owns face selection, adjacency, orientation, parameterization, seam
placement, physical carrier triangulation, grid preview, persistence, and map
compatibility diagnostics. It does not own Diamond cells, staggered triangular
lattices, pyramid relief, or physical trimming.

## Approved Baseline

Map Faces `0.1.4` (commit message `checkpoint: best approved Map Faces generic
grid 0.1.4`) is the current approved checkpoint. `44b8f19` remains the previous
approved checkpoint (`0.1.2`). The reference fixture is
`tests/fixtures/container_four_faces.FCStd`.

Baseline evidence:

- 2,642 physical carrier triangles;
- all four sampled adjacency seams agree to four decimal places;
- the lower-left periodic face has its complete lower line;
- transverse lines continue into the upper adjacent face;
- no isolated duplicate row, lower-left line fan, duplicated border, or missing
  final row.

`MAP-REQ-001` **Baseline** - Changes must preserve this result until a new Map
Faces baseline is visually approved and recorded.

## Inputs and Selection

`MAP-REQ-002` **Baseline** - Accept one or more selected faces. With multiple
faces, all faces must belong to one connected adjacency component.

`MAP-REQ-003` **Baseline** - Support strips, branches, and cycles. Selection
order and OCC face numbering are not semantic.

`MAP-REQ-004` **Baseline** - Build adjacency from shared topological edges and
geometry tolerances. Never branch on a known face number, selected-face count,
object name, or fixture.

`MAP-REQ-005` **Baseline** - Orient normals through the adjacency graph and
detect contradictory cycles.

## Mapping Migration Ledger

The following V4 functions belong to Map Faces. `Facade` means the active
implementation still resides in `core_engine.py` and is re-exported
or called by a modular file.

| Functions | Destination | Current status |
| --- | --- | --- |
| `outer_edges`, `endpoints`, `same_edge`, `shared_edge`, `selected_faces`, `source_solid`, `build_graph`, `components` | `mapping/adjacency.py` | Migrated; V4 names remain compatibility wrappers |
| `surface_period`, `unwrap_parameter`, `surface_parameters`, `parameter_range`, `face_center`, `interp`, `edge_fraction`, `local_xy_raw`, `local_xy`, `local_uv`, `apply_transform`, `invert_transform`, `point_from_logical` | `mapping/parameterization.py` | Migrated; V4 names remain compatibility wrappers |
| `axis_length_table` | `mapping/parameterization.py` | Migrated; V4 name remains a compatibility wrapper |
| `tangent`, `outward`, `signed_normal_at`, `edge_midpoint`, `align_connected_normals` | `mapping/orientation.py` | Migrated; V4 names remain compatibility wrappers |
| `orient_entry` | `mapping/orientation.py` | Facade; orchestration retained with parameterization |
| `edge_samples`, `apply_matrix`, `aligned_edge_samples`, `seam_limit`, `neighbor_transform_candidates` | `mapping/seams.py` | Migrated; V4 names remain compatibility wrappers |
| `seam_matrix_error`, `fit_neighbor_to_constraints`, `fit_neighbor` | `mapping/seams.py` | Migrated; V4 names remain compatibility wrappers |
| `transformed_entry_bounds`, `snap_lower_curved_strips_to_grid`, `position_components`, `atlas_seam_pairs`, `edge_direction_matches`, `add_logical_seam_overrides`, `seam_override` | `mapping/seams.py` | Facade; pattern-size dependency pending removal |
| `mapped_vertex`, `split_carrier_triangle`, `tessellated_carrier`, `entry_contains_logical`, `regular_curved_carrier`, `midpoint_vertex`, `weld_logical_nodes`, `refine_conforming_round`, `conforming_carrier` | `mapping/carrier.py` | Facade |
| `validate_logical_seams`, `triangle_edge_key`, `third_point_2d`, `cycle_seam_pairs`, `rotate_component`, `close_periodic_component`, `unfold_carrier` | seams and carrier internals | Facade |
| `point_on_edge`, `external_segments` | `mapping/carrier.py` | Facade |
| `line_triangle_points`, `grid_line_values`, `preview_point_key`, `preview_line_edges`, `carrier_preview` | `mapping/preview.py` | Migrated; V4 names remain compatibility wrappers |
| `entry_record`, `create_wrap`, `resolve_wrap_selection`, `hydrate_entries` | `mapping/service.py` | Transitional orchestration |

## User Interface

`MAP-REQ-010` **Implemented in 0.1.4** - Before creating a map, show a modal dialog with:

- `Column width`, default `13.856 mm`;
- `Row height`, default `12.000 mm`;
- `Closure tolerance`, default `0.050 mm`.

All values use millimeters, a minimum of `0.010 mm`, and three decimals. Save
confirmed values in FreeCAD preferences. Cancel must not create or alter objects
or preferences.

`MAP-REQ-011` **Implemented in 0.1.4** - Grid orientation remains automatic and follows the
geometric atlas orientation. The dialog provides no rotation control.

## Algorithm and Data Flow

1. Resolve selected source faces.
2. Orient every face using local surface geometry and connected normals.
3. Build the adjacency graph and connected component.
4. Normalize periodic parameters into each trimmed face interval.
5. Position faces in a shared logical atlas from seam constraints.
6. Validate all logical seams.
7. Build the physical carrier triangulation.
8. Compute the generic grid origin and preview.
9. Diagnose segment and cycle compatibility without deforming geometry.
10. Serialize the map and create the run, preview, and warning objects.

`MAP-REQ-020` **Baseline** - Preserve pcurves and native trimmed parameter
intervals. Values returned by a periodic support surface must be unwrapped to the
equivalent value nearest the center of the trimmed interval.

`MAP-REQ-021` **Baseline** - When a new face has multiple already positioned
neighbors, prioritize the orientation of the already positioned seam. A mostly
horizontal placed seam carries transverse grid phase. Curved seam fitting may
scale only the seam tangent direction; the perpendicular scale remains `1.0`.

`MAP-REQ-022` **Implemented in 0.1.4** - The physical carrier remains a triangulated,
invisible interpolation structure. Its triangles transport logical coordinates,
physical points, normals, UV values, and face ownership; they are not pattern
cells and do not define the visible grid.

`MAP-REQ-023` **Implemented in 0.1.4** - The visible map grid is orthogonal. Vertical lines
use `Column width`; horizontal lines use `Row height`. Rows never receive an
alternating half-column offset.

`MAP-REQ-024` **Implemented in 0.1.4** - Column width and row height are independent. Map
Faces must not derive either value from an equilateral-triangle formula.

`MAP-REQ-025` **Implemented in 0.1.4** - Grid phase is stored separately and
must not translate, rotate, scale, or otherwise modify the physical carrier.

`MAP-REQ-030` **In validation** - When all selected faces belong to one source
Body, Map Faces establishes one persistent Body grid phase. The first saved map
is the phase root: its lateral grid origin is the centre of its selected logical
region. While creating each later map, Map Faces must find a topological route
through the source BRep from an already mapped face to the newly selected face,
including unselected intermediate faces when necessary. It transports the
root's logical orientation and translation along that route, then applies the
result only to the new carrier atlas. Any metric scale accumulated through a
curved intermediate seam must be discarded: the new carrier retains its own
physical metric and the user's pattern dimensions. Existing maps and their
payloads are read-only phase references and must never be repositioned when a
new map appears. The bottom-to-top phase remains anchored at each map's actual
physical lower carrier boundary, measured in the owning Body's placement. This
prevents an unrelated, disconnected wall from inheriting a vertical offset by
projecting a remote Body vertex through its carrier. Separate Map Faces runs
therefore retain a common phase across adjacent and non-adjacent faces, without
moving physical carrier points or changing the map payload schema. A multi-body
map keeps the centred fallback. The rule must use source topology, the source
owner placement, and carrier geometry; it must not name a body, face, fixture,
screen direction, or world axis. When a selected source is not inside a
PartDesign Body (for example, a solid created by a split operation), its own
Shape and Placement become the phase owner. A later map belonging to a
different phase owner may join the phase only through a coincident physical
carrier boundary; it then adopts the oldest compatible map's phase. A
disconnected owner remains independent until such a boundary is available.

`MAP-REQ-031` **In validation** - Map Faces offers independent placement
choices for vertical and horizontal preview-grid lines. Vertical lines may use
**Left**, **Centre**, **Right**, or **Follow global phase**; horizontal lines
may use **Bottom**, **Centre**, **Top**, or **Follow global phase**. The local
choices place a line on the corresponding selected-carrier edge; global is the
default and uses the first same-Body map as the phase root. The choices adjust
only the existing two-number grid origin. They must not move carrier vertices,
add payload fields, or imply a Diamond size.

`MAP-REQ-026` **Implemented in 0.1.4** - Remove Map Faces dependencies on Diamond constants
and limits. Characterize `snap_lower_curved_strips_to_grid()` before changing it;
if its effect is required by the approved baseline, replace its pattern-size
dependency with a topology- and seam-based rule.

The import boundary is guarded by `tests/test_architecture_boundaries.py`.
The remaining `core_engine.py` dependency is transitional and must be removed
through an equivalence-tested extraction checkpoint.

`MAP-REQ-027` **Implemented in 0.1.5** - In a cyclic component, record cycle
closure seams from adjacency edges that were not used by the atlas positioning
tree. Never infer the opened or periodic seam from face indices, selection
order, or the lexicographically last adjacency pair. Local non-periodic cycles
remain eligible for later geometric filtering. Multiple physical boundary
edges that describe the same component axis and period produce one component-
level periodic record.

`MAP-REQ-028` **Implemented in 0.1.5** - A periodic logical axis anchors its grid
phase at the lower periodic boundary. The physical location of that boundary
is determined by the atlas and may appear between any source faces. Centering
the phase must not create a double-width closure cell. This changes only the
logical grid origin; carrier geometry and physical dimensions remain intact.

`MAP-REQ-029` **Implemented in 0.1.5** - The visible grid is a lightweight view
of the carrier interpolation. Connected samples of one logical row or column
are represented by a smooth preview edge instead of one selectable BRep edge
per carrier triangle. Preview simplification must not alter serialized carrier
triangles or the geometry consumed by Pattern Tools.

## Regression Evidence

### Periodic trimmed intervals

The reference fixture originally exposed a displaced lower-left line because
periodic support parameters were expanded to the full underlying domain:

- `Face8` is toroidal and its native interval was already consistent;
- `Face14` is cylindrical with native U near `0 .. pi/2`, but the old range
  derivation produced `0 .. 2*pi`;
- `Face4` is cylindrical with native U near `3*pi/2 .. 2*pi`, but the old range
  derivation also produced `0 .. 2*pi`;
- the physical `Face14`/`Face8` shared edge is about `11.938052 mm`, while the
  incorrect logical atlas measured about `35.7998 mm`.

The approved fix normalizes every value returned by `Surface.parameter(point)`
to the equivalent periodic value nearest the trimmed interval center. Using
`face.ParameterRange` only at initialization is insufficient because later
surface calls can return the opposite periodic representation.

### Multiple already positioned seams

After periodic unwrapping, the lower-left curved face had a complete lower
boundary but transverse lines still missed the upper face. `Face8` had two
already positioned neighbors. The atlas chose the vertical `Face14`/`Face8`
seam and ignored the horizontal `Face4`/`Face8` seam that carries transverse
phase.

The approved fix scores the placed seam in global logical coordinates before
the target face's local edge. For the curved seam, the target tangent is scaled
by `1.080146` (`43.6262 mm` to `47.1227 mm`) while perpendicular scale remains
`1.0`. Tests sample every adjacency pair at nine positions and require both
logical coordinates to agree to four decimal places.

If another periodic topology fails, isolate these experiments in order:

1. derive logical boundary coordinates directly from edge pcurves;
2. unwrap values relative to the shared pcurve for intervals spanning more than
   half a period;
3. score candidates using full-edge residual, endpoints, tangent, and interval
   length;
4. add cycle optimization only after all pairwise seams are correct.

## Dimensional Compatibility

`MAP-REQ-030` **Specified** - Open boundaries may contain partial cells. This is
informational and does not make a map invalid.

`MAP-REQ-031` **Specified** - Never deform, scale, or reposition the physical
carrier to force a grid fit.

`MAP-REQ-032` **Specified** - For geometric segments between corners, report
length, nearest integer cell count, signed remainder, and nearest compatible
length for the relevant grid axis.

`MAP-REQ-033` **Specified** - Build a deterministic cycle basis from the
adjacency graph. Compare every logical cycle displacement with the nearest
integer multiple of column width and row height.

`MAP-REQ-034` **Specified** - Maps with incompatible closed cycles are still
created. Set compatibility properties, print diagnostics in Report View, and
show incompatible seams or segments in a separate red warning object.

`MAP-REQ-035` **Specified** - For arcs, report arc length, sweep angle, current
radius, nearest integer cell count, recommended length, and recommended radius.
Use `R = length / angle`; for a quarter circle use `R = 2 * length / pi`.

## Internal Holes

`MAP-REQ-040` **Specified** - Record inner boundary loops separately from outer
boundary loops in map metadata.

`MAP-REQ-041` **Specified** - An internal hole does not restart or change grid
phase. The logical grid and pattern continue conceptually through the hole.

`MAP-REQ-042` **Deferred** - Map Faces does not cut the carrier or pattern around
an internal hole in the current phase. Trim Surface owns the eventual physical
removal.

`MAP-REQ-043` **Deferred** - Adjacency through an inner contour, such as a
selected cylindrical hole wall, must not be enabled implicitly. It requires a
separate specification update and fixtures.

## Outputs and FreeCAD Objects

Map Faces creates:

- a map run object containing selected source faces and serialized map data;
- a blue wireframe grid preview;
- when required, a separate red closure-warning object.

`MAP-REQ-052` **Implemented** — A map run and its carrier preview are grouped
with the source component without becoming Part Design features. For one source
Body, create a neutral `Pattern Surface (<Body label>)` group inside its nearest
`App::Part`; link the map, preview, and group to that Body. A map involving
multiple Bodies uses its own neutral group and links every source Body. Never
add map objects directly to a `PartDesign::Body`, because that changes its Tip
and may replace the finished CAD solid.

Selecting the neutral ownership group is equivalent to selecting its map run
for every Pattern Surface and Blender command.

`MAP-REQ-050` **Specified** - The map object exposes `MapColumnWidth`,
`MapRowHeight`, `MapGridOrigin`, `MapClosureTolerance`, `MapCompatible`,
`MapIncompatibleCount`, and `MapCompatibilityReport`.

`MAP-REQ-051` **Baseline** - Preserve the current generic and legacy properties
until the migration rules in `data-contracts.md` allow removal.

## Invariants

- Mapping imports no pattern package.
- Logical seams are based on topology and geometry, not screen coordinates.
- Pattern dimensions do not influence face placement or carrier geometry.
- Grid preview lines use one shared phase across every face in the component.
- Carrier triangulation and pattern lattices remain distinct data structures.

## Errors and Warnings

- Error when there is no active document or no selected face.
- Error when selected faces do not form one connected component.
- Error when normals or required seam placement are contradictory.
- Warning, not error, for approximate curved seams within the accepted limit.
- Warning, not error, for dimensional closure incompatibility.

## Compatibility

`MAP-REQ-060` **Specified** - Continue reading and writing legacy `grid_side` and
`grid_height` aliases while adding the generic grid contract.

`MAP-REQ-061` **Baseline** - Continue exposing `Wrap*` properties and payloads
while old documents and commands depend on them.

## Known Limitations and Deferred Work

- Broader periodic-cycle fixtures are still required.
- Inner-contour adjacency and physical hole clipping are deferred.
- Cycle closure is diagnosed but never optimized by deforming the map.
- The active implementation remains partly inside the shared geometry engine.

## Acceptance Tests

`MAP-REQ-063` **Implemented** — Curved carrier cells that cross a native trimmed
face boundary must be intersected with that domain, not retained or discarded
by a centroid test. Preserve the regular carrier on rectangular parameter
domains. Boundary approximation must follow native tessellation tolerance,
including sloped rims and holes; no face IDs or global axes are special-cased.
Validated with rectangular and inclined cylindrical domains, rotated geometry,
a native hole, and the unchanged 2,642-triangle four-face integration baseline.
This does not declare a new visually approved mapping baseline.

Automated:

- preserve the approved carrier count and sampled seam agreement;
- verify periodic parameters remain inside trimmed intervals;
- verify arbitrary connected face counts and selection order independence;
- verify orthogonal spacing with independent dimensions and no stagger;
- verify carrier coordinates do not change when grid dimensions change;
- verify open partial cells and compatible/incompatible cycles;
- verify legacy map payloads remain readable.

Visual:

1. Run the four-face fixture and compare against the `44b8f19` baseline.
2. Confirm the lower line is complete and transverse lines meet at every seam.
3. Confirm no duplicate rows, line fans, missing rows, or duplicated borders.
4. Change only column width, then only row height, and verify independent spacing.
5. Confirm incompatible diagnostics are red and the normal grid remains blue.

## Automatic density workflow

`MAP-REQ-062` **Specified** — The Map Faces dialog no longer requests fixed
row/column counts. It uses generic physical preview spacing internally and asks
only for closure tolerance. Explicit count arguments remain supported for scripts.
The preview does not determine pattern density. User requested 2026-09-08.
