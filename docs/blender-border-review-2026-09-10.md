# Blender border rollback and diagnosis — 2026-09-10

The user requested restoration of the preceding working version and analysis
of the live failed Blender result. The initial review did not approve a new
clipping algorithm. The subsequent validation is recorded below.

## Subsequent implementation and validation

Native trimmed curved domains now intersect regular sampling cells. Complete
interior cells and rectangular domains retain the regular sampler; native mesh
triangulation is used only at the trim. On the actual source the carrier rim
overshoot fell from 1.044029 mm to 0.000576 mm, in 1.37 seconds. Raising relief
still produced 0.204426 mm overshoot, so the bridge additionally exports native
adjacent planar supports and clips the displaced relief with Blender Exact.
These planes must support the entire selected domain; no guessed global axis,
face ID or screenshot-derived plane enters production code.

The Manifold Boolean produced a visible overlapping cap despite passing mesh
closure, and was rejected. Exact passed both views of the real model and the
0.001 mm clipping bound. The real saved-map package was generated in 3.11 seconds
without rewriting its stored chunks; Blender generation, clipping and rendering
took approximately 28 seconds. No `.blend` file was saved.

Validation: 66 FreeCAD tests; Blender cavity/volume/rotation clipping regression;
full four-face flow (2,642 carrier triangles, 68 Diamond solids at each of three
heights, 68 Trim solids); compileall and installation check. Real-model relief
has zero nonmanifold edges and one component. Front/back renders were inspected
at `/tmp/auzyron-border-review/final-front.png` and `final-back.png`.

Limit: native domain clipping covers curved footprints and holes, but displaced
relief cutting by an arbitrary nonplanar boundary envelope is not proven by
these planar-support tests. Do not claim universal surface support or silently
substitute a guessed supporting plane for an unsupported boundary.

## Observed failure

The live Blender window contained `Auzyron Diamond Relief` and `Auzyron Map
Faces Pocket Cutter`, without the intended CAD body object. The matching job
reported `The selected-face Pocket cutter is not closed.` The worker failed
before importing the body and left the auxiliary cutter visible. The new
`boundary_pocket` flag bypassed both the established planar trapezoidal path
and the approved regular curved sampling path.

## Restored implementation

Geometry, worker and job packaging were restored from `e402c05`. The synchronous
FreeCAD Full Pattern/Trim computation and experimental Blender cutter/compound
union were removed. The asynchronous launch and per-cell periodic tolerance
were retained. Approved native Diamond and Trim code were not changed.

The same actual job was regenerated in Blender with its original parameters
(triangle height 12.32 mm, relief 1.5 mm, resolution 8). The restored scene has
the complete body and relief; it was also rendered and inspected. No blend
file was saved. The old failed scene was not forcibly closed or overwritten.

## Measured boundary defect

The captured job is Base_Container / MappedSurface_Run_002: 16 source faces,
12,851 carrier triangles and 494 external segments. Four upper curved faces
have zero external segments. Of the physical carrier edges, 1,013 unmatched
edges are absent from the external-segment list. This includes possible internal
T-junctions; they must not all be classified as exterior rims.

For this part, eight endpoints of the four straight upper boundary segments
define a common cutting plane (maximum plane-fit residual 1.1e-13 mm). Checking
the entire CAD-body STL independently confirms it stays within that plane to
0.0000046 mm. This plane fit is a diagnostic for this part, not a proposed
global-axis or planar-only runtime clipping algorithm.

| Geometry | Maximum positive distance beyond the CAD rim plane |
| --- | ---: |
| CAD body STL | 0.0000046 mm |
| Map carrier before relief | 1.044029 mm |
| Restored Diamond relief | 1.120704 mm |

The excess carrier points belong to the same four upper curved faces whose
external segments are missing. Their maxima range from 0.832671 to 1.044029 mm.
The straight upper faces agree with the plane to numerical precision. Thus the
source carrier already misrepresents the trimmed curved boundary; fixing only
the Blender Boolean or welding the resulting mesh cannot establish CAD border
accuracy. The restored relief has 512 vertices exceeding the plane by 0.01 mm.

The earlier planar/trapezoidal regression uses physical planar footprints and
does not cover this curved trimmed-carrier discrepancy. Its passing result is
valid for that scope, not evidence that the mixed curved case is correct.

## Required next correction and acceptance

1. Compare curved carrier boundary samples to the original trimmed CAD faces,
   preserving native trim curves/pcurves. Resolve the boundary discrepancy
   before using the carrier or its external segments as a cutter.
2. Recover complete ordered outer and inner CAD loops and distinguish actual
   rims from selected-face adjacency, periodic seams and internal T-junctions.
3. Preserve full pyramid facets and intersect their displaced geometry with
   the physical boundary support. Clipping only the undisplaced footprint can
   still allow outward relief to cross an inclined rim. Do not flatten/fade
   pyramid vertices to hide this.
4. Keep expensive computations outside the FreeCAD UI process. Reuse the
   approved planar and regular sampling paths where applicable.
5. Test CAD-to-pattern coverage, out-of-domain excess, seam continuity and
   pyramid shape, including curved/sloped transitions, rotated parts and holes.
   A closed mesh is necessary but does not certify the boundary.

## Validation performed

- compileall, installation verification and 63 FreeCAD-runtime tests passed,
  including the historical golden topology, trapezoidal case and per-cell fit.
- Actual-job background generation succeeded: 125,602 vertices, 249,711 faces,
  one connected relief component, zero non-manifold edges. Generation of the
  mesh alone took approximately 13 seconds in the diagnostic run.
- Restored actual-job render was inspected; the body/pattern are present, but
  the small upper rim teeth remain. No claim of final boundary approval.

The failed runtime experiment was checkpointed before rollback at
`.checkpoints/20260910T170249Z_before_user_requested_blender_rollback`.

## Subsequent border and lower-seam correction

The earlier rollback findings above describe an intermediate state. The user
approved the subsequent native-domain border correction, then reported a lower
horizontal seam on the trimmed container absent from the regular container.

The two generation paths differed: the trimmed path imprinted carrier triangle
edges into pyramid facets and suppressed the axial component of relief normals.
Both paths now share uniform facet subdivision; fully covered samples do not
retain internal carrier boundaries. The trimmed path uses interpolated native
CAD normals and full normal displacement. The regular golden geometry is unchanged.
Native supporting-plane clipping remains, with a 0.0002 mm numerical guard,
projection back to the original plane and degenerate-edge cleanup at 0.00001 mm.

Final verification:
- compileall and installation verification passed; 68 FreeCAD-runtime tests passed.
- Added rotated inclined-normal consistency and carrier-seam topology regressions.
- Blender cavity/volume/rotated boundary regression passed.
- Regenerated saved MappedSurface_Run_002 from Base Container.FCStd: one relief
  component, zero non-manifold edges, 309,714 triangulated faces after clipping.
- Strict transverse-intersection audit found zero crossings (1e-5 mm plane
  straddling tolerance); this is not a proof against all coplanar overlaps.
- Generation plus front/back rendering completed in approximately 30 seconds.
- Front and back renders inspected: /tmp/auzyron-border-review/final-validated-front.png
  and final-validated-back.png; audit: final-validated-audit.json in that folder.
- Blender connector was unavailable; validation regenerated the saved CAD map
  in a separate background process. Existing live Blender scenes were untouched.
- No blend file was saved. This implementation is validated, pending user review;
  no claim of universal coverage for every surface topology.
