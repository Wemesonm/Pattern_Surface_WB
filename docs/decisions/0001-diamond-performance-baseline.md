# Diamond Performance Baseline

Status: Accepted; superseded by approved optimization checkpoint `ad0bf1e`

Date: 2026-08-22

## Context

The current Diamond Pattern result is visually approved, but generation is slow.
The expensive operations are expected to be carrier lookup, per-cell mapping,
OCC solid construction, compound assembly, and document recompute. The current
geometry must remain the rollback point while the bottleneck is identified.

## Decision

Treat commit `6882429` as the approved pre-optimization Map Faces baseline. The
approved optimization checkpoint `ad0bf1e` reuses the cell-center outward
normal orientation for curved cells and preserves the approved result.

## Consequences

The current approved run reports approximately 46.3 seconds, 192 solids, and
zero rejected cells on the tested Small Box. The diagnostics remain available
for the next isolated optimization.

## Affected requirements

- PAT-REQ-030
- PAT-REQ-031
- PAT-REQ-032

## Validation

Run Diamond on the approved fixture and compare solids, rejected cells, closure
fit, and visual output with the pre-diagnostic result. Use the reported dominant
stage to select the next isolated optimization.
