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
- **STOP WO1-4. `PropertyRequest.state` and `.phase` are not widened.** D2 widens them to `StreamState |
  EvaluationState` and `Phase | PhaseId` "with no runtime change". Measured: with both widened, `mypy src` (strict,
  `warn_unreachable`) fails with 51 errors in 7 modules, all identity-bearing legacy providers that F0 M9 freezes
  (`thermo/pr_c1.py` 13, `wilson_ig.py` 11, `coolprop_heos.py` 8, `iapws95.py` 8, `syn001.py` 7, `pr_lib.py` 3,
  `wilson_ig_v2.py` 1: `.is_dormant`, `.total_flow`, `Phase`-typed helpers). Passing would need an edit of a frozen
  module (moves M9) or a relaxed type check, both refused by the rules. Kept narrow; the types are re-exported and the
  exact cache keys both forms at run time (WO1-5), so F4's adapters can build requests either way. **Design-lane
  question**: (a) a v2 request type of ADR-F4's beside `PropertyRequest`; (b) widen and add a mypy override for the 7
  frozen modules; (c) amend D2 to drop the widening. Default (a).
- **DECISION WO1-6. Phase-id reading.** `PhaseId(family, qualifier, ordinal)` has no defaults (D2's signature) and
  refuses at construction a family outside `VAPOR, LIQUID, FLUID, SOLID` (D6: `phase_family` is built-in only), a
  qualifier outside `cid | cid,form | model=mid` (the component alphabet of `process-revision.schema.json`, `form`
  D6's, `mid` F1's `ID_PATTERN`, copied so that `thermo` does not import the registry, a test holds them equal) and an
  ordinal that is not an `int` >= 1. The parser is test-only, as D6 says ("Parse (test-only)"):
  `tests/f2/phase_id_parse.py`, not `phase_id.py` as the brief has it. A phase set is non-empty and distinct;
  `render_phase_set` refuses a tuple not in canonical order; a one-phase set renders as its phase. E-F2-5's "no v2 id
  equals a legacy id" is read for phase ids as: a rendering equals a legacy `Phase` value only for that very phase
  (D6 keeps `LIQUID`, `VAPOR` "as today") and never `TWO_PHASE` or `ZERO_FLOW`. Alternatives: defaults
  `(qualifier=None, ordinal=1)`; families open to the pattern. Lives in `material/phase_id.py`.
- **DECISION WO1-7. `EvaluationState` checks its attribute order.** D2 says the attributes are "sorted by key bytes";
  `__post_init__` refuses (`ValueError`) keys not strictly increasing by UTF-8 bytes, so equal states have one form
  and one cache key. `to_stream_state` refuses a state with attributes (D2). Attribute keys' spelling is not checked
  here (kinds come with WO2). Alternative: sort on construction. Lives in `material/state.py`.
- **E-F2-1 reading.** "Every stream of every corpus run" is every `StreamState` constructed while F0's 61 corpus runs
  are solved as F0 solves them (`StreamState.__init__` recorded): 99,538 built, 21,903 bitwise distinct; each
  `from_stream_state(s).to_stream_state()` equals `s` by `struct.pack('<d')` per float and `n` is the same tuple
  object. `tests/test_f2_material_types.py::test_e_f2_1_every_corpus_stream_round_trips_bitwise`.
- **DECISION WO1-5. D2's exact-cache keys** (`thermo/cache.py`; numbered before WO1-6 in the brief's order, committed
  after it). `_state_document` keeps the `StreamState` document byte for byte (F0 M6 85/85 after the change); an
  `EvaluationState` adds `attributes: [[key, state_sha256(values, ["<key>#0", ...])], ...]` in key order **only when
  it has attributes**, so one without attributes keys exactly as the `StreamState` it round-trips to (one state, one
  key, one result for both request forms; tested). `_phase_key` keys a `PhaseId` by its rendering, so
  `PhaseId("LIQUID", None, 1)` keys as `"LIQUID"`. Flash keys are untouched (`FlashRequest` is not widened, D2).
  Alternative: an `attributes` member always present (an `EvaluationState` would never share a `StreamState` entry).
- **DECISION WO1-8. The basis gate is lifted as ADR 0061 D7 says, "a one-line table change".** `ADMITTED_BASES` is
  `{"mol", "segment_mol", "kg"}`; the `amount_basis_unsupported` code, its catalogue entry and the check stay (no schema
  -valid record reaches it now; catalogue bytes unchanged). Flipped tests: `test_e_f3_3_the_fixtures_register_since_adr
  _0062_d1` (the component fixture's three `s` Constants are `molar_entropy` now, and the segment fixture registers with
  `anchor_undetermined`; this one already failed from the kinds commit `9431853b` on, which registered
  `molar_entropy`), `test_e_f3_13_kg_has_no_anchor_and_registers_since_adr_f2` (E-F3-13, Q2.A10 (b): null anchor,
  `anchor_undetermined`, registered, idempotent), `test_f3_user_file::test_a_v2_record_d2_refuses_keeps_its_errors`
  (a charged `kg` record is refused `amount_basis_invalid(charge_nonzero)`, no longer `amount_basis_unsupported`).
  A reaction over a `kg` record keeps the existing path: `records.reactions` raises `ValueError` (no molar mass), the
  records service refuses `invalid_request`; docstring updated. **Design-lane question for WO2**: should the reaction
  check use D4's M = 1 for `kg` instead (Q7.R3)? Default: unchanged.
- **DECISION WO1-9. Formation and transition kinds follow the amount basis.** ADR 0061 D3 states Δf h° and s° "per
  unit amount" but `FORMATION_KINDS` held only the `mol` kinds, harmless while only `mol` registered. With the gate
  lifted, a `kg` record's Δf h° in J/mol would register and one in J/kg would be refused. ADR 0062 D1's Use column
  names the kinds: `segment_molar_enthalpy` "h, Δf h° per segment-mol", `segment_molar_entropy` "s, s° per
  segment-mol", `specific_enthalpy` "h of a `kg`-basis component", `specific_entropy` "s of a `kg` component". So
  `FORMATION_KINDS` is per basis (`mol`: `molar_*`; `segment_mol`: `segment_molar_*`; `kg`: `specific_*`); `mol`
  records validate exactly as before (F3 304/304, the legacy import unchanged). Test:
  `test_f3_record_model.py::test_d7_formation_kinds_follow_the_amount_basis` (3 bases x 3 kind pairs). Alternative:
  lift the gate alone (admits dimensionally wrong `kg` and `segment_mol` formation data). Isolated in its own commit;
  **design-lane confirmation** wanted (unit semantics read from D1's Use column, not stated as a rule).

## F2-WO2 (definitions and bases), 2026-11-26

Files: `src/openflowsheet/material/{basis,definitions}.py`, `schemas/connection-definition.schema.json`,
`schemas/extension-descriptor.schema.json` (payload `$defs`), `src/openflowsheet/registry/descriptor.py`,
`scripts/registry_builtin.py`, `src/openflowsheet/registry/builtin/material.json`,
`docs/derivations/scripts/f2_basis_reference.{py,json}`, `tests/test_f2_basis.py`, `tests/test_f2_definitions.py`.

- **E-F2-7 reading.** "[gen]" is a reference generator, `docs/derivations/scripts/f2_basis_reference.py` (imports
  nothing of `openflowsheet`; `--check` byte-compares), that decides every case by routes other than `basis.py`'s
  (Bareiss ranks and rank-nullity; a breakpoint search for (iii); Cramer's rule for Q3.R7; the normal equations for C;
  the ruling's own stated Π) and refuses to emit when one of its 67 claims fails. `tests/test_f2_basis.py` (41 tests)
  compares `basis.py` with it exactly. Species masses are synthetic test constants (IUPAC conventional atomic weights
  minus z m_e, rounded once). Measured: Q3.R7's worst deficit over the 11 bases is 0.434 ε·scale (MEA, against the 4ε
  bound: margin 9.2x); the electron-mass control (Na+ given the neutral atom's mass) misses it by 2.1e10 ε·scale and
  reports `NaCl`.
- **DECISION WO2-1. Q3.R1 (iii) reads "admits a non-negative A" as: for every group row g a rational λ_g exists with
  A_g + λ_g z ≥ 0** (the shift Q3.A2 (d) itself uses; on electroneutral n_s ≥ 0 it gives b ≥ 0, which is what (iii)
  protects). λ need not be an integer. Alternative: integer λ, or the declared A ≥ 0 only. **Design-lane question.**
- **DECISION WO2-2. Q3.R5's Π e_s is the particular solution with free reaction coefficients 0** (reduced row echelon
  form over R restricted to the dropped species, reactions in declared order); it must come out integer, else the
  boundary is refused. Q3.A6 (d)'s stated image MEA + HCO3- - H2O is what it gives; b′ = C b does not depend on the
  choice when a C exists (C A R d = 0 for any alternative R d). Alternative: a lattice search for an integer image.
- **DECISION WO2-3. Species match across a boundary by id; a shared id with another charge is refused.** The record
  part of "same record and charge" is the caller's (WO4 can key species by id and record SHA).
- **DECISION WO2-4. Q3.R7's bound reads Σ_g |A_gs M_g|** (a magnitude; equal to the ruling's Σ_g A_gs M_g when A ≥ 0
  and M_g ≥ 0) and is evaluated exactly on the rounded M_g and μ that are recorded. Alternative: the signed sum (can be
  negative for a non-monotone declaration).
- **Codes not assigned here.** `basis.py` returns the facts (each of (i), (ii), (iii), rank, ζ, Π, C, drops); the
  typed refusals and their parameters (`species_basis_*`, `group_amount_negative`, `molar_mass_inconsistent`) are the
  revision validator's (WO4, E-F2-9). Q3.R1 names no code for a failed (i) or (ii) at the definition level; WO4 needs
  one (default: `species_basis_incompatible(<method>, <S>)`, Q3.R5's).
