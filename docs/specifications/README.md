# Pattern Surface Specifications

## Purpose

These documents are the normative product and engineering specifications for
`Pattern_Surface_WB`. Runtime behavior must trace to a requirement in one tool
specification or the shared data contract.

## Documents

| Specification | Owner |
| --- | --- |
| [`map-faces.md`](map-faces.md) | Face selection, topology, logical atlas, physical carrier, generic grid, preview, and compatibility diagnostics. |
| [`pattern-tools.md`](pattern-tools.md) | Pattern registry, pattern interfaces, Diamond lattice, pattern parameters, and generated solids. |
| [`trim-surface.md`](trim-surface.md) | Source association, physical envelopes, booleans, hole clipping, and trim fallbacks. |
| [`data-contracts.md`](data-contracts.md) | Shared FreeCAD properties, serialized payloads, schema versions, and legacy compatibility. |

Architectural decisions that change or clarify these specifications are recorded
under [`../decisions/`](../decisions/README.md).

## Requirement Status

Every requirement uses one of these statuses:

- `Baseline`: behavior exists and is part of an approved checkpoint.
- `Implemented`: behavior was added after the baseline and passed acceptance.
- `Specified`: approved behavior that has not been implemented yet.
- `Deferred`: intentionally postponed and not part of current acceptance.
- `Superseded`: replaced by another identified requirement or decision.

Status describes implementation evidence, not importance.

## Change Process

1. Identify the owning tool and shared contracts.
2. Add or revise requirement IDs before modifying conflicting runtime behavior.
3. Record a decision when the change alters ownership, data flow, compatibility,
   or a previously approved invariant.
4. Add automated tests that reference the applicable requirement IDs.
5. Run the automated and visual acceptance protocols.
6. Update status to `Implemented` only after acceptance.
7. Record the approved checkpoint or commit in the specification.

Changes spanning multiple specifications must update all affected documents in
the same documentation checkpoint.

## ID Rules

- Map Faces: `MAP-REQ-NNN`
- Pattern Tools: `PAT-REQ-NNN`
- Trim Surface: `TRIM-REQ-NNN`
- Shared data contract: `DATA-REQ-NNN`

IDs are permanent. Never reuse an ID after superseding a requirement.

## Specification Template

Every tool specification contains:

- purpose and ownership boundary;
- inputs and selection rules;
- outputs and FreeCAD objects;
- user interface;
- algorithm and data flow;
- public properties and payload fields;
- invariants;
- errors and warnings;
- compatibility requirements;
- known limitations and deferred work;
- automated and visual acceptance tests.

