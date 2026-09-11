# PAT-REQ-089 — split-body assembly closure validation

The September 11 split-body document was read from the active FreeCAD session.
Mapped Surface 002 covers Slice001.1; Mapped Surface 003 covers Slice001.0.
No stored map or source geometry was changed.

The registration tree aligned one rim. The other coincident physical rim had
logical translation (737.3493142675137, 0) mm. Neither partial map declared an
individual periodic adjustment, so the old bridge omitted joint cycle closure.
Rotation/reflection cannot remove a full-cycle mismatch at both joins.

One assembly-wide fit produces 52 modules, side 14.179794505144494 mm, with
triangle height 12.32 mm, relief 1.5 mm, resolution 12, no edge transition,
finish offset 0.045 mm, contact 0.25 mm and closure tolerance 0.5 mm per module.
Each partial carrier remains nonperiodic and is independently clipped.

Validation performed using the normal FreeCAD create_job and Blender worker:

- Both source bodies exported separately.
- Both relief meshes: one connected component, zero nonmanifold edges.
- The generated meshes were inspected at both split rims in both directions.
  260 and 292 seam vertices per side were compared against the opposing mesh
  using a Blender BVH; maximum distance was 0.000007865 mm.
- Images from both sides visually show continuous Diamond facets at the joins.
- 110 automated tests pass, including a regression using the actual native rim
  samples in tests/fixtures/shared_assembly_cycle_rims.json.
- Installation verification, compilation and git diff whitespace checks pass.

Artifacts are saved in
/Users/wemesonaraujo/.local/share/codex-cad/assembly-cycle-validation-20260911/.
The corrected blend contains only the project; inspection cameras were temporary.
This is a validation checkpoint, not a newly user-approved baseline or main merge.
