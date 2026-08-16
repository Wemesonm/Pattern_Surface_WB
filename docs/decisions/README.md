# Architectural Decision Records

Use this directory for decisions that change ownership, data flow, compatibility,
or an approved invariant in the specifications.

## File Naming

```text
NNNN-short-decision-title.md
```

Numbers are sequential and never reused.

## Required Sections

- `Status`: Proposed, Accepted, Superseded, or Rejected.
- `Date`.
- `Context`.
- `Decision`.
- `Consequences`.
- `Affected requirements`.
- `Validation`.

Accepted decisions update the normative specifications in the same documentation
checkpoint. Decision records explain why; specifications define current required
behavior.

## Current Decisions Embedded in Specifications

The following decisions predate this directory and are currently recorded in
the linked specifications:

- Map Faces exposes a generic orthogonal grid while retaining an internal
  triangulated physical carrier.
- Staggered triangular lattice behavior belongs exclusively to Diamond.
- Map Faces never deforms the carrier to force dimensional closure.
- Internal holes preserve logical grid phase; physical removal belongs to Trim
  Surface and remains deferred.
- `44b8f19` remains the approved Map Faces baseline until a newer result receives
  visual approval.

Create dedicated decision records if any of these decisions are revised.

