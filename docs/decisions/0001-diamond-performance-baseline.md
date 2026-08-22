# Diamond Performance Baseline

Status: Accepted

Date: 2026-08-22

## Context

The current Diamond Pattern result is visually approved, but generation is slow.
The expensive operations are expected to be carrier lookup, per-cell mapping,
OCC solid construction, compound assembly, and document recompute. The current
geometry must remain the rollback point while the bottleneck is identified.

## Decision

Treat commit `6882429` as the approved pre-optimization Map Faces baseline. Add
stage timing diagnostics to the Diamond generation path before changing any
geometry or fallback behavior.

## Consequences

The next FreeCAD run will report timings and cell counts in the Report View. The
diagnostics are temporary-compatible and do not change the generated object.

## Affected requirements

- PAT-REQ-030
- PAT-REQ-031
- PAT-REQ-032

## Validation

Run Diamond on the approved fixture and compare solids, rejected cells, closure
fit, and visual output with the pre-diagnostic result. Use the reported dominant
stage to select the next isolated optimization.
