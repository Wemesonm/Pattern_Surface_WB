# Blender as an optional mesh backend

Status: Accepted (user requested in voice session)
Date: 2026-09-06

## Context
The user wants CAD face selection through existing Map Faces, with the approved
Blender Diamond finish and Boolean union, without reselecting triangles.

## Decision
Add a separate Blender toolbar command and local worker. Consume the serialized
map and source body; open a separate Blender result. Do not replace native
Diamond or Trim Surface, and do not convert mesh relief back to BRep.

## Consequences
Blender is a local dependency. CAD stays unchanged. Unsupported maps and failed
union validation must report failure. The command uses a new Blender process so
an already-open Blender project is not overwritten.

## Affected requirements
PAT-REQ-060 through PAT-REQ-062; DATA-REQ-050.

## Validation
Pure contract tests, architecture checks, installed-command registration, and
end-to-end generation on planar and rounded mapped surfaces.
