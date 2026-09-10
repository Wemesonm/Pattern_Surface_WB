# Native rib edge transition review — 2026-09-10

Requirements: PAT-REQ-080, DATA-REQ-056.

## Checkpoint and scope

The user-approved baseline is `f3a6384`, pushed to `origin/main` before this
experiment. The new work is on `feature/ribs-native-edge-fillet`. It is not a
new user-approved baseline. Local checkpoint:
`.checkpoints/20260910T214656Z_before_native_ribs_edge_transition`.

Diagonal Ribs now offers a rounded transition width (3 mm default, 0 disables)
and an all-edges checkbox. The default applies the transition to lower edges.
Map Faces, Diamond generation and Trim Surface algorithms are unchanged.

## Cause and correction

Legacy external atlas segments did not cover four upper curved faces of the
real test map. Native BRep wire incidence supplies the complete contour instead.
Use `OrderedEdges`: unlike `Edges`, it retains repeated seam occurrences, so a
periodic cylinder seam is excluded correctly. Selected-face shared edges are
also excluded. Boundary endpoint incidence must form closed cycles.

Sample curves with 0.005 mm chord tolerance. Component-aware physical distance
to these curves drives a cubic smooth transition, including the finish offset.
The edge embeds by at most 0.02 mm (limited by contact depth) to avoid a lip.
The interior rib phase and relief are unchanged. The saved map is not rewritten.

T junctions between unequal carrier subdivisions are joined before closing the
relief backing. This removed internal walls and changed the real test relief
from three disconnected pieces to one closed component. Disabled transitions
retain the preceding generator output exactly.

Very small transition widths can demand excessive sampling; reject more than
1.5 million logical cells before allocating the boundary index.

## Evidence

- CAD tests: full periodic cylinder, four selected box walls, sloped cylindrical
  rim with a hole, rotated and translated geometry. Native boundaries exclude
  internal seams and preserve lower-edge classification.
- Geometry tests: complete boundary taper, unchanged interior, disabled
  equivalence, physical/component distance, missing-data rejection, T junction
  closure and early sampling-limit rejection.
- Actual saved `Base Container.FCStd`, `MappedSurface_Run_002`: 16 selected
  faces, 16 native boundary curves, 356 sampled segments. Saved map unchanged.
- Real 12 mm pitch / resolution 8: lower-only and all-edge variants both passed
  the production Blender worker validation, one relief component and zero
  nonmanifold edges before and after physical clipping.
- Real 4 mm pitch / resolution 16 / height 1.5 mm / transition 3 mm / all edges:
  also one component and zero nonmanifold edges; 2,335,908 generated triangles.
  Approximately 78 seconds including four 1400 × 1000 review renders.
- The registered FreeCAD command was executed by a FreeCAD macro with the same
  dense parameters. It launched an interactive, unsaved Blender scene; its
  transient job package was deleted after loading. Parameter injection bypassed
  the modal dialog only; command packaging and launch were the production path.
- Two attempts at UI automation crashed FreeCAD in `QMacAccessibilityElement`
  destruction (macOS/Qt accessibility). The command/macro route completed.
  This is not evidence that the separate GUI crash issue has been fixed.

Review images reside in `/tmp/auzyron-border-review/`:
`native-dense-{front,back,left,right}.png` and
`native-lower-{front,back,left,right}.png`. They are renders of the actual
generated geometry, not illustrative images. No blend or STL result was saved
for the user automatically. Diagnostic CAD input meshes are temporary.

## Limits

This is a smooth relief transition, not an exact constant-radius CAD fillet.
The distance is Euclidean to sampled native curves, not a geodesic on folded
surfaces. Closely spaced folds and arbitrary nonplanar cutting envelopes still
need separate validation. Lower-edge classification follows the map row
direction. This does not guarantee support-free printing for every orientation,
material or relief size. Manifold checks do not certify every self-intersection.

The four rendered views were inspected. User aesthetic approval of this new
transition remains pending; do not replace the approved main baseline silently.
