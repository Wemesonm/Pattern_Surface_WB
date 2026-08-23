# Decision 0003: Dependency Direction Guard

## Decision

The current working geometry remains protected by the compatibility engine,
but the public tool layers have an enforced dependency direction:

```text
common contracts and helpers
          ^
          |
Map Faces | Pattern Tools | Trim Surface
          ^                 ^
          |                 |
       patterns        map + generic pattern payload
```

- Map Faces must not import a pattern package.
- Pattern packages must not import the Map Faces implementation package.
- Trim Surface must not import Diamond or another concrete pattern package.
- Shared modules must not import any tool package.

`pattern_surface/core_engine.py` is still transitional and is allowed by the
compatibility tests. It must be reduced only through equivalence-tested
extractions.

## Rationale

The user-approved geometry is stable and visually validated. A static guard
allows the migration to continue without reintroducing the coupling that made
Map Faces depend on Diamond behavior.

## Acceptance

`tests/test_architecture_boundaries.py` enforces the four rules above. The
guard must pass with the existing FreeCAD embedded test suite at each
extraction checkpoint.
