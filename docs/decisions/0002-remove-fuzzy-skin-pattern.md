# Remove Fuzzy Skin Pattern

- Status: Accepted
- Date: 2026-08-22

## Context

The experimental Fuzzy Skin CAD pattern did not provide a reliable advantage
over the Fuzzy Skin feature already available in the slicer. Its generated
surface also increased geometry size and could produce invalid or difficult to
slice meshes at boundaries.

## Decision

Remove Fuzzy Skin from the active Auzyron Patterns WB registry, commands,
documentation contracts, and installed resources. Keep the Diamond Pattern as
the only active registered pattern for now. Slicer-side Fuzzy Skin remains the
chosen workflow.

The implementation history remains available in Git, including commits
`47176d7`, `116917e`, and `5a68b54`, so it can be inspected or restored without
mixing it into the active workbench.

## Consequences

- Pattern Tools exposes Diamond only.
- Map Faces and Trim Surface are unchanged.
- No Fuzzy Skin objects or payloads are created by the workbench.
- Any future procedural surface texture must be proposed as a new pattern with
  its own specification and printability tests.
