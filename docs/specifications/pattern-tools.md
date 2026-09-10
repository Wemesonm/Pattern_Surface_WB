# Pattern Tools Specification

## Boundary correction validation — 2026-09-10

The bridge now refreshes native trimmed curved carrier domains and cuts displaced
relief using supporting planes supplied by adjacent, unselected CAD faces
(DATA-REQ-053). It uses the Exact solver; the Manifold solver produced an
overlapping rear cap despite reporting a closed mesh and was rejected visually.
This is a geometric rule, not a face-index, object-name or world-axis exception.
Native Diamond and Trim construction are unchanged. Arbitrary nonplanar boundary
cutting envelopes remain outside the planar-support guarantee; do not describe
this validation as proof for every possible surface topology.

## Purpose and Ownership

`PAT-REQ-076` **Implemented** — Complete strips and trimmed curved domains must
use the same full local-normal relief offset, including lower fillets. The
superseded longitudinal projection from PAT-REQ-070 must not survive in the
trimmed-domain path. Interior facet subdivisions must not follow internal CAD
carrier seams: use the regular lattice and intersect only partially covered
samples with the carrier domain. Preserve boundary clipping and PAT-REQ-071 golden
geometry. Validate interior topology independence, inclined normals and rotated geometry, plus the approved
real-model border cut. User requested 2026-09-10 after comparing both paths.
The clipped-domain path interpolates the native CAD normal field: derivatives
of clipped carrier chords introduced normal jumps at trims. Regular strips
retain the approved historical sampler and its golden coordinates.

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

`PAT-REQ-077` **Implemented** — Blender-backed patterns are presented through one
`Blender Patterns` toolbar/menu group, matching the native Pattern Tools list.
The group contains the existing Blender Diamond command and Diagonal Ribs;
patterns do not occupy independent workbench toolbar buttons.

`PAT-REQ-078` **Implemented** — Diagonal Ribs is a FreeCAD workbench command
backed by a continuous Blender height-field generator. It owns spacing, relief height, logical angle and sampling
resolution. The height field follows the map's local normal field, fits phase
across an axis-0 periodic seam, clips every sample to the physical carrier and
returns a closed backing-and-side-wall relief mesh. It consumes Map Faces but
does not modify native Diamond or Trim Surface. Its dense continuous mesh is
welded before the boundary cut and does not run Diamond's degenerate-face
cleanup, because that cleanup can reopen a valid smooth height field.

`PAT-REQ-079` **Implemented** — Every interactive Blender job starts by
removing Blender's factory-scene objects. The opened scene contains only the
Auzyron CAD body, the generated pattern, and the hidden source-body copy used
by the bridge; it does not retain the default Cube, Camera, or Light.

## Diamond Pattern

The `Diamond Pattern` command uses the approved baseline engine in
`pattern_surface/core_engine.py`. Experimental curved-surface work is exposed
separately as `Diamond Pattern Prototype` through
`pattern_surface/prototype_engine.py`. Both commands consume the same Map
Faces payload and remain compatible with the shared Trim Surface contract.

`Diamond Pattern Prototype V2` is a third, isolated experiment. It consumes
only the serialized Map Faces payload and creates a complete mapped pattern
without importing the approved Diamond engine, the original Prototype engine,
mapping implementation, or Trim Surface. Its algorithm identifier is
`AUZYRON_DIAMOND_PROTOTYPE_V2_BVH_NORMAL`; it uses shared logical nodes,
barycentric carrier projection, continuous normal selection, local relief, and
per-cell solid validation. It is intentionally not a Trim Surface input.

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

`PAT-REQ-066` **Specified** — Blender Diamond boundary cells must be clipped
against the physical carrier triangles, not admitted or rejected by their
logical center. The resulting exposed relief boundary follows the mapped face
boundary, including curved cutouts and fillets. A boundary intersection may
split one pyramid facet into multiple carrier-conforming fragments, while its
unclipped facet plane and requested relief remain unchanged. User requested
2026-09-08.

`PAT-REQ-067` **Specified** — If the CAD body validates but the separately
displayed relief cannot be exported as a closed manifold, Blender still opens a
clearly labelled preview `.blend`. STL export remains blocked and the command
reports the manifold counts. This does not label the preview ready for export.

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

## Performance Diagnostics

`PAT-REQ-030` **Implemented as diagnostics** - Diamond generation reports elapsed
time for carrier preparation, cell mapping, solid construction, compound assembly,
and document recompute. Diagnostic output must not alter geometry, tolerances,
cell eligibility, fallback order, or object properties.

`PAT-REQ-031` **Pending optimization** - Performance improvements must target a
measured stage, preserve the approved cell counts and rejected-cell behavior, and
be validated on both straight and curved faces before approval.

`PAT-REQ-032` **Implemented in 0.1.7** - Curved Diamond cells may resolve the outward
normal orientation once at the cell center and align local carrier normals to
that reference. This optimization is acceptable only if the approved fixture
retains its solid count, rejected-cell count, closure, and visual boundary.

`PAT-REQ-033` **Candidate fix** - When an eligible curved cell is rejected by
all dense surface-following shells, Diamond may use a final closed three-corner
fallback. It preserves the canonical triangular footprint and local outward
apex, and is never used for planar cells or cells outside the mapped domain.

`PAT-REQ-034` **Candidate fix** - Full-pattern construction shall use a
temporary external carrier strip to complete cells that cross a mapped-face
boundary. Eligibility must still require overlap with a real mapped carrier;
the strip must never create detached pattern rows. Trim Surface remains
responsible for removing the excess geometry.

`PAT-REQ-035` **Candidate refinement** - Diamond shall expose a curved-surface
relief factor, persisted in preferences and on the pattern object. The value
is the minimum relief permitted for strongly curved cells. Cells marked as
curved shall transition continuously from full relief to that minimum using
their local carrier-normal variation; planar cells, cell bases, lattice IDs,
seams, and the Map Faces carrier shall remain unchanged. The requested
`PatternHeight` remains the maximum relief used by Trim Surface envelopes.

## Diamond Migration Ledger

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
| `curved_corner_pyramid_solid` | Curved-cell final fallback | Candidate fix; requires visual approval |
| `extended_triangles` in full-pattern construction | One-cell boundary overscan | Candidate fix; requires visual approval |
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

The independent `Boleado Pattern` creates rounded mapped bumps. It owns its
hemisphere radius, horizontal and vertical spacing, row offset, and surface
penetration. Its exposed height is always equal to the radius, producing a true
half-sphere. It consumes the public Map Faces payload and emits the generic
pattern payload without importing Diamond lattice code.

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
- Diamond still delegates substantial geometry to the shared geometry engine.
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
- eligible curved cells do not disappear solely because OCC rejects their dense
  surface-following shell; the final fallback is reported only when used.
- a curved-relief factor changes only curved-cell apex heights and is serialized
  in the pattern object and payload.

Visual:

1. Generate Diamond on the approved four-face map.
2. Confirm the staggered triangular lattice remains correct after extraction.
3. Test pyramid heights `0.500`, `1.000`, and `2.000 mm`.
4. Confirm only relief changes and the pattern remains aligned across seams.
5. Regenerate the same model with curved-surface relief at 100% and 50%;
   planar cells must remain unchanged while the lower curved band becomes less
   pronounced at 50%.

## Blender backend

`PAT-REQ-060` **Implemented** — An independent Blender command accepts a selected
map run or its grid, asks for Diamond size and relief height, transfers the
source body and public carrier, and generates clipped triangular relief in a
new Blender project. It does not require a Diamond result in FreeCAD. Existing
native Pattern Tools remain unchanged.


`PAT-REQ-061` **Specified** — Preserve original CAD and Blender projects. Keep
body and relief copies hidden in the result. Validate manifold edges, connected
components and positive volume before labelling a result complete. Failure must
be visible and must not be labelled ready for export. No cloud, MCP, or AI is
required by the installed command.

`PAT-REQ-062` **Specified** — Preserve approved finishing: explicit 0.045 mm
finish allowance, shared valley vertices and sharp pyramid facets. For wrap
surfaces, optionally infer a longitudinal axis from carrier normals and remove
relief displacement along that axis. Never assume global Z. Reject unsupported
periodic layouts explicitly. Generic carriers may introduce approximation.

`PAT-REQ-063` **Specified** — On planar walls, use physical orthonormal
coordinates and constant nominal lattice spacing and relief height. The public
map supplies spacing and phase, not a deformation from a rectangle onto a
trapezoid. Clip the nominal facets at the physical wall boundary without
changing their planes. Keep this path separate from curved carrier sampling.
Union closed clipped patches with the CAD body and validate the final mesh;
do not label a failed union ready for export. User requested 2026-09-08.

## Physical-size population

`PAT-REQ-064` **Specified** — The approved Diamond dialog asks for triangle
height (size), default 12 mm, relief height, default 1.5 mm, and the existing
closure tolerance. Experimental gap and curved-relief controls stay in Prototype.
The existing approved lattice derives candidates from physical atlas bounds and
requested size, independently of map preview divisions. Iterate ascending logical
rows (bottom to top in atlas coordinates); preserve phase, IDs, boundary handling,
source-face references and approved solid construction. No global axis is imposed.
This supersedes the map-grid density wording in PAT-REQ-031. Visual approval of
new results remains pending. User requested 2026-09-08.

`PAT-REQ-065` **Specified** — Blender export uses the solid feature referenced
by the mapped faces, never an enclosing App::Part assembly of historical features.
Remove unreferenced generated vertices before closing the relief shell. Keep
nonmanifold/connected-component validation strict and report its failing counts.
An empty selection reports an actionable message without calling startup GUI APIs.
Regression: Large Drawer, 2026-09-08; native Diamond and Trim remain unchanged.

For multiple mapped source solids, unite their exact CAD shapes before meshing;
reject missing sources or a union that is not one valid connected solid. Do not
silently export a partial body or preserve intersecting internal compound walls.

`PAT-REQ-068` **Specified** — Blender Diamond creates a transient local job only
long enough to populate a new interactive Blender scene. It must frame every
visible result object before the viewport is shown, must not save a `.blend` or
STL automatically, and must remove its temporary job package once Blender has
loaded the geometry. The user owns any later manual export or save. Before a
new run, remove stale Auzyron job packages from prior runs. User requested
2026-09-08.


`PAT-REQ-069` **Superseded by PAT-REQ-071** — Restore September 6 independent Diamond sampling
with default resolution 20. Refine the clipped logical facets using conforming
shared-edge splits, reevaluating each vertex on the carrier. Preserve original
pyramid facet identities and planar clipping. Resolution must affect generated
curved geometry, not only a stored parameter. Validate boundary and periodic
closure after refinement. User requested restoring earlier quality, 2026-09-08.

Validation for PAT-REQ-069 (2026-09-08): 60 automated tests passed; the saved
container map generated 317,800 outer triangles / 637,464 total faces in about
24 seconds. Blender 5.1.2 confirmed one connected relief component, zero
nonmanifold edges and positive volume. Workbench installation verified. A
separate background render verified the restored facet shading. This checks the
relief, not a new Boolean union; existing worker body/union behavior is unchanged.
Visual equivalence to the original analytic model remains subject to review;
carrier interpolation and current normal displacement are still used.

`PAT-REQ-070` **Superseded by PAT-REQ-071** — Restore the approved September 6 mesh finish only:
retain resolution 20, shared pyramid facets and longitudinal positions on
periodic rounded wraps. Infer the row axis from carrier derivatives with
winding-independent signs; remove its relief component without renormalizing.
Keep current UI, density controls, selection, export and planar-wall behavior.
Validate lower-boundary positions and rotation invariance. User requested
2026-09-08.


`PAT-REQ-071` **Implemented** — Restore the regular triangular sampling approved
visually on 2026-09-08 from the last 2026-09-06 Python generator. On complete
periodic carrier strips, use
8 uniform subdivisions per pyramid facet, the historical local-normal offset,
shared periodic vertices, backing closure and flat facet display. Do not impose
carrier triangulation on these pattern facets. Preserve requested-size density,
planar physical clipping, partial-boundary clipping, source-body validation,
transient jobs and the current UI. Select the regular path by logical coverage
never by document, face IDs or world axes. Cut uniform triangles at unaligned
open rims; irregular domains and cutouts retain their boundary clipping path. Historical source was
recovered from the full read at 2026-09-06T12:26:41Z and the last periodic seam
patch at 12:27:21Z. The approved relief has 37,248 vertices and 74,112 faces
at the recorded dimensions and resolution 8. Verify exact vertex/face agreement
against the preserved historical test before accepting the restoration.


PAT-REQ-071 acceptance (2026-09-08): the preserved 9,640-triangle map produced
exactly equal vertices, face indices and facet IDs against the recovered source
(37,248 vertices, 74,112 faces). The installed FreeCAD job exporter then read the
saved Base Container map (9,688 carrier triangles), exported the original solid,
and the current Blender worker generated the same pattern topology with zero
nonmanifold edges. Both body and pattern are individually closed; this retains
the existing body-plus-pattern workflow, not a new Boolean union. The complete
piece was opened in Blender Edit Mode at the preserved lower-edge view. All 62
FreeCAD-runtime tests passed, including a golden historical coordinate/topology
regression, unaligned-rim clipping and existing planar/density checks. Installation
symlink verified. Only geometry_closed.py, worker.py and the command's sampling
default changed in runtime. Recovery checkpoint:
`.checkpoints/20260908T231602Z_before_approved_sept6_sampling_restore`.

`PAT-REQ-072` **Specified** — For a periodic Blender Diamond map, closure
tolerance applies to the size correction for each repeated Diamond cell, never
the accumulated correction around the entire closed perimeter. This preserves
the requested physical size on large parts while still rejecting a visibly large
per-cell distortion. User requested 2026-09-10.

`PAT-REQ-073` **Specified** — At an open boundary of a periodic mapped
strip, Blender Diamond must preserve complete boundary pyramids and apply an
exact boundary cut equivalent to the approved FreeCAD Full Pattern plus Trim
Surface workflow. The cut may not fade, flatten, or otherwise change a pyramid
plane at the rim. The rule applies by logical boundary coordinates and is
independent of part shape, face names, and world axes. The synchronous FreeCAD
BRep implementation was deliberately removed on 2026-09-10 because it blocks
the FreeCAD UI on production-sized maps; the replacement must run outside the
FreeCAD UI process. User requested 2026-09-10.

`PAT-REQ-074` **Specified** — The exact boundary workflow applies to
every open boundary recorded by Map Faces as an external BRep segment, including
filleted, cutout, or otherwise non-rectangular maps. It must not infer a border
from carrier-triangle incidence, because a conforming carrier may contain
internal T-junctions. Periodic seam copies are never treated as open rims. User
requested 2026-09-10.

`PAT-REQ-075` **Superseded by PAT-REQ-071** — The experimental native Trim
compound plus Blender MANIFOLD union was withdrawn with the user's rollback
request on 2026-09-10. A closed mesh on the four-face fixture was insufficient
evidence for boundary correctness or performance on the user's actual piece.
Do not reintroduce this experiment as an approved baseline.

Rollback review (2026-09-10): restored geometry, worker and packaging from
`e402c05`, retaining only per-cell closure tolerance and asynchronous Blender
launch. The failed actual job reported `The selected-face Pocket cutter is not
closed.` It left the auxiliary cutter visible before importing the CAD body.
The `boundary_pocket` flag had bypassed both the tested trapezoidal planar path
and the approved regular periodic path. These overrides were removed.

The actual 16-face map contains 12,851 carrier triangles and 494 external
segments. Four curved upper faces have no external segments in that payload.
There are 1,013 unmatched physical carrier edges absent from external segments;
this count includes possible nonconforming internal seams, not just true rims.
Future boundary work must establish complete native CAD boundary loops and
separate internal seams before constructing any trimming volume. Acceptance
must measure border coverage and excess against the CAD contour, preserve
pyramid planes, and inspect sloped planar-to-curved transitions. Manifold counts
alone do not establish these properties. PAT-REQ-073/074 remain pending.

The actual-job CAD comparison also found that the curved map carrier already
exceeds the native upper rim by 1.044029 mm before displacement. The restored
relief exceeds it by 1.120704 mm while passing the manifold check. See
[`../blender-border-review-2026-09-10.md`](../blender-border-review-2026-09-10.md)
for evidence and the required boundary acceptance checks.
