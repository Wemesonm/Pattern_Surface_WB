# Trim Surface Specification

## Purpose and Ownership

Trim Surface physically clips generated pattern solids to the mapped source
faces. It owns source association, physical envelopes, boolean operations,
fallback reconstruction, hole removal, and trim metadata.

Trim Surface does not create logical maps, repair seams, choose grid phase, or
generate a pattern lattice.

## Inputs and Selection

`TRIM-REQ-001` **Baseline** - Resolve one map and one generated pattern from the
selection or from their stored associations.

`TRIM-REQ-002` **Baseline** - Validate that the pattern belongs to the selected
map before performing geometry operations.

`TRIM-REQ-003` **Specified** - Accept any registered pattern that satisfies the
shared pattern contract. Generic selection and trimming code must not require a
Diamond object name.

## User Interface

`TRIM-REQ-010` **Baseline** - Trim Surface runs directly from the selected map
and pattern. It does not ask again for pattern height.

`TRIM-REQ-011` **Specified** - Errors and warnings identify missing, ambiguous,
or incompatible map-pattern associations before starting expensive booleans.

## Algorithm and Data Flow

1. Resolve and validate the map-pattern relationship.
2. Load source faces, map payload, pattern payload, and stored relief.
3. Build physical cutting envelopes from mapped source faces.
4. Include outer and inner source boundaries in the envelope topology.
5. Cut generated solids with the envelopes.
6. Use pattern-independent reconstruction fallbacks when a boolean fails.
7. Validate resulting solids and persist generic trim metadata.

`TRIM-REQ-020` **Baseline** - Envelope depth uses stored `PatternHeight` plus the
required front and rear safety margins.

`TRIM-REQ-021` **Baseline** - Trimming preserves accepted pattern geometry and
does not regenerate cell placement.

`TRIM-REQ-022` **Specified** - Physical clipping removes portions of pattern
solids that occupy internal holes in source faces. Map Faces does not perform
this removal.

`TRIM-REQ-023` **Specified** - Boolean and reconstruction fallbacks are generic.
Pattern-specific reconstruction, when unavoidable, is provided through the
pattern package contract rather than imported into generic trim modules.

## V4 Trim Migration Ledger

| Functions | Destination | Current status |
| --- | --- | --- |
| `build_cut_cells` | trim cell orchestration | Facade |
| `exact_face_cut_envelope`, `fused_cut_envelopes` | `trimming/envelopes.py` | Facade; stored-height adaptation |
| `physical_cut_piece`, `build_cut_cells_from_full` | `trimming/booleans.py` | Facade; reconstruction fallback |
| `resolve_cut_selection`, `create_cut` | `trimming/service.py` | Transitional orchestration with generic metadata |

## Outputs and FreeCAD Objects

`TRIM-REQ-030` **Baseline** - The trim result records `PatternId`,
`PatternMapSource`, `PatternSource`, and `PatternHeight`.

`TRIM-REQ-031` **Baseline** - Preserve legacy Diamond compatibility properties
while old documents and readers depend on them.

`TRIM-REQ-032` **Specified** - The trim payload records input object identities,
map and pattern schema versions, accepted/rejected cell IDs, envelope strategy,
fallback strategy, and stored relief used by the operation.

## Invariants

- Trim Surface never asks for or changes pattern dimensions.
- Trim Surface does not alter the source map or full pattern object.
- Generic trimming code does not generate Diamond cells.
- Inner holes are removed from final physical solids.
- Output metadata preserves traceability to map and pattern inputs.

## Errors and Warnings

- Error for missing or ambiguous map-pattern association.
- Error when required payloads cannot be decoded or are incompatible.
- Warning when a principal boolean fails and a documented fallback is used.
- Reject only the affected cell when possible; do not silently return an
  incomplete result without diagnostics.

## Compatibility

`TRIM-REQ-040` **Baseline** - Read stored height from generic properties first
and legacy Diamond fields as a compatibility fallback.

`TRIM-REQ-041` **Specified** - Read legacy payloads through the migration rules
in `data-contracts.md`; do not rewrite source objects merely by reading them.

## Known Limitations and Deferred Work

- Current envelopes and fallbacks remain partly in the transitional V4 engine.
- Internal-hole trimming needs dedicated planar and curved fixtures.
- Pattern-independent fallback hooks are not yet part of the registry contract.

## Acceptance Tests

Automated:

- reject mismatched map-pattern selections;
- use stored pattern height without opening a dialog;
- preserve accepted cell identity and metadata;
- validate principal and fallback trim paths;
- remove pattern geometry inside planar and curved internal holes;
- read legacy Diamond trim payloads.

Visual:

1. Trim the approved 68-solid Diamond fixture and confirm 68 valid results.
2. Repeat at stored heights `0.500`, `1.000`, and `2.000 mm`.
3. Verify a perforated-face fixture removes pattern solids inside the hole.
4. Inspect seams and source boundaries for duplicate or missing solids.
