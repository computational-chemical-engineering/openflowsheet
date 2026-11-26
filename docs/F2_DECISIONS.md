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
- **DECISION WO1-2. Display kinds follow the kind table.** ADR 0075 D2.1 defines the display kinds as "the kinds of
  `schemas/units.json`" plus its five display-only kinds, so the nine D1 kinds that were not among the five
  (`specific_volume`, `specific_heat_capacity`, `segment_*` (6), `number_flow`) become display kinds with their SI unit
  as the only spelling (no display row). `docs/derivations/scripts/x04_reference.json` is re-emitted by its generator
  (`--emit`, which reads `units.json`): 117 lines added, none changed; `--check` passes. The five keep their
  `source: "ADR 0062 D1 (display only until F2)"` (the generator's C10 check confirms F2's entries equal them). MSG's
  `J/(mol*K)` spelling (`refusals.yaml`, ADR 0075 line 362) is not touched here: catalogue entries are WO7's.
  Alternative: freeze `DISPLAY_KINDS` at the pre-F2 set (departs from ADR 0075 D2.1's text).
- **DECISION WO1-3. `StreamState` is defined in `material/state.py`, re-exported by `thermo`.** ADR 0062 D2 puts the
  new types in `openflowsheet/material/` re-exported from `openflowsheet.thermo` (so `thermo` imports `material`),
  while `EvaluationState.to_stream_state` returns a `StreamState` (so `material` needs it): with `StreamState` left in
  `thermo` that is an import cycle, which the S19 layer order (`.codehealth/config.toml`, every nesting level) refuses
  in either direction. The class moved verbatim (no character of its body changed); `openflowsheet.thermo.StreamState`
  is the same object, so every import, `repr`, equality, pickle by name and cache key is unchanged; only
  `StreamState.__module__` reads `openflowsheet.material.state`. `material` sits directly below `thermo` in the layer
  order and in `tests/test_package_imports.py` `LAYERS`. Inert, proved: F0 PASS with the pinned counts (M1 50/50, M2-M5
  61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42), `tests/test_k02*.py` and `test_package_imports.py` 340 passed, mypy
  `src` clean. Alternatives: `material` above `thermo` with no runtime re-export (the annotations under
  `TYPE_CHECKING`), departing from D2's "re-exported"; or a lazy upward import (a new layer violation). **Design-lane
  question** (an ADR premise the post-S19 layout contradicts; this is the reading that changes no byte).
