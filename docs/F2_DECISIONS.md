# F2 build decisions (append-only)

Build-lane choices for package F2 (material model) that ADR 0062 leaves open. ADR 0062 is Proposed; the build follows
its text as it stands (D1 to D13, the W1 P2 and P3 review edits applied). Where it is silent or ambiguous, the reading
taken is the one that changes no existing byte. Each line: `DECISION`, the choice, the alternative, and where it lives.
Each is revertible on its own. Batched for the package's one design-lane ruling round (CLAUDE.md, agent budget).

## F2-WO1 (kinds and types), 2026-11-26

Files: `schemas/units.json`, `schemas/quantity.schema.json` (kind enum), `src/openflowsheet/units/__init__.py`,
`src/openflowsheet/material/{__init__,state,phase_id}.py`, `src/openflowsheet/thermo/{__init__,cache}.py`,
`src/openflowsheet/records/{model,validate}.py`, `tests/test_f2_*.py`, `tests/f2/phase_id_parse.py`.

- **DECISION WO1-1. Lower bounds of the 14 D1 kinds** (D1 gives none). `segment_molar_mass` takes
  `lower_bound_exclusive: 0.0`, as `molar_mass` does (it is the `molar_mass` of a `segment_mol` record, Q7.R2, ADR 0061
  D3); every other new kind takes `null`, so the kind refuses nothing a quantity's own bounds would not (ADR 0001 D2:
  bounds are declared per quantity). `specific_volume` and `segment_molar_volume` do not copy `molar_volume`'s `0.0`:
  partial and excess volumes may be negative. Alternative: `0.0` for both volumes too. Lives in `schemas/units.json`
  and `units._KIND_LOWER_BOUNDS_EXCLUSIVE`. **Design-lane question** (unit semantics the ADR does not state).
