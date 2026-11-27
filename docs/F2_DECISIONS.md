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
- **DECISION WO2-5. An instance is `{template: <id>, <parameters>}`; D3's preimage `body` is the normalised instance
  without `template`** (so `nTP-v1`'s body is `{}`, as D3 states; the template is named once, in the triple).
  `schemas/connection-definition.schema.json` is a `oneOf` over the five templates' closed grammars.
- **DECISION WO2-6. One spelling per instance.** Every substream member is required (`grids: []`, `attributes: []`
  when empty) and every attribute member (`components`, `grid` may be `null`); a group's content holds non-zero
  integers only (a zero is omitted, D11's stoichiometry precedent). Normalisation is D3's list, nothing more: groups
  by id, attributes by (kind, components) with substream scope (`null`) before any list and lists by their UTF-8
  tuples; grids, substreams, components and species keep their given order. Alternative: optional members with
  defaults (two spellings, two SHAs).
- **DECISION WO2-7. The templates live in a fourth built-in table, `registry/builtin/material.json`**, with ADR
  0062's four phase families; the legacy table admits only legacy-form payloads. Each template's payload is
  `{instance_schema: {package, path, pointer, sha256}}` (its grammar in `connection-definition.schema.json` and that
  file's SHA, as a record type names its schema), so an edit of a grammar moves the template's descriptor; modules
  empty, status `implemented`, version 1.0.0. No v2 payload schema for `connection_definition` is installed (the brief
  lists five kinds; ADR 0062 states no template payload), so extension definitions stay object-only and `preview`.
  **Design-lane question**: the template payload (default: as built).
- **DECISION WO2-8. The five payload envelopes (D5, D6) are installed in `PAYLOAD_DEFS`, the kinds are not added to
  `CORE_KINDS`**: "per ADR-F2" is `preview` until ADR 0062 is Accepted (ADR 0060 D1), so the built-in families and
  templates register `preview`; on Acceptance the five kinds join `CORE_KINDS` (one line) and the families become core.
  Readings where D5 is terse: `phase_family`'s payload is the empty object (the vocabulary is the id, semantics
  ADR-F5's); quantity kinds are strings (the descriptor schema refs no other schema, as `correlation_form`'s kinds);
  `derived_quantity.output` is `"builtin"` or `{vocabulary_item}`, `spec` exactly two `[name, kind]` pairs,
  `candidates` `"method"` or a non-empty list of renderings; an inequality term is `[number, string]`. The rules D5
  states beyond a schema (`attribute_redundant`, "phase_family descriptors are built-in only", family ids matching
  `^[A-Z][A-Z0-9_]*$`) are not enforced by the registry yet: **left for WO4** (the synthetic test family `std.L` is a
  built-in of a test table).
- **Identity.** `legacy.json`, `core.json`, `records.json` byte-identical; `nTP-v1`'s `descriptor_sha256` unchanged
  (`d0a6d025…`). By design: `tables.sha256` moves on every line (the descriptor schema's bytes enter each table's
  digest; core `f34f1b98`→`3538f634`, legacy `1bd31223`→`c2d5190f`, records `6e48244d`→`c6861f41`, material new
  `98354b4b`) and E-F1-5's `registry_sha256` `6a7550d4`→`844d9ba7`. No F0 check reads either (`corpus_identity.py`
  reads neither file nor the registry). Tests that pinned the table set were updated, not relaxed:
  `test_f1_builtin_identity.py` (the table names), `test_f1_legacy_builtins.py` (57 descriptors in 4 tables; the
  process registry's legacy rows still equal the legacy table's, the four templates beside them).
- **Revert recipes** (WO2-5 to WO2-8 share one commit, the built-ins commit): WO2-8 alone is the five `PAYLOAD_DEFS`
  lines, the five `$defs/payload_*` of `extension-descriptor.schema.json`, the guide paragraph
  (`docs-site/guide/plugins.md`, held by `test_x01_example_plugin.py`) and the payload tests of
  `tests/test_f2_definitions.py`, then `scripts/registry_builtin.py --write`.
- **Found, not caused, by WO2: 16 tests fail at the WO1 head `ed5fb6c0`** and identically after WO2:
  `tests/test_t07_w5e_application_results.py` (5: `list_models`' resolved response schema `854fab33…` against the
  snapshot `12d88245…`) and `tests/test_t08_w2_surface_digest.py` (11: the served tool list `9a4b4eb3…` against F3's
  registered `f7ec3c94…`). Cause: WO1's 14 kinds widen `quantity.schema.json`'s kind enum, which `list_models`'
  output schema reaches. WO2 moves neither digest (measured equal before and after). An F2 surface move needs
  registering as F3's was (a decomposition test, `without_f2`, and its R-number): **left for the orchestrator**
  (WO7's close-out or a WO1 fix).

## WO2b: F2's served-surface move registered (2026-11-26)

- **Registered as F3's was.** `tests/f2_schema_support.py`: `without_f2(node)` drops, from every enum that ends in
  ADR 0062 D1's 14 kinds (`F2_KINDS`, WO1's order), those 14 values and the description's sentence `F2_KIND_NOTE`;
  any other node is copied unchanged, so it composes with every `without_*` (ADR 0078 D6). Pins:
  `F2_SERVED_SHA256` = `9a4b4eb3bd9f28e6…` (`tests/test_t08_w2_surface_digest.py`) and `SNAPSHOT_F2["list_models"]` =
  `854fab3332da26b0…` (`tests/test_t07_w5e_application_results.py`). The kind enum is served in `list_models` alone
  (its two `specifications` places: pins and choice options); no other resolved response and no other tool carries it.
- **Proofs.** `test_f2s_surface_move_decomposes_onto_f3s`: without F2's kinds the served list is F3's `f7ec3c94…`;
  only `list_models` moved, only its two kind schemas, each by exactly the 14 kinds and the sentence.
  `test_f2_without_its_additions_every_response_is_its_pre_f2_snapshot`: every one of the 30 resolved responses is its
  pre-F2 snapshot after `without_f2`, and exactly `list_models` moved (to `12d88245…` again). The earlier
  decompositions take F2's additions out first (the latest first). The ADR 0019 pointer comes in WO6.
- **Open: link c_11 of `scripts/m07a_rc.py`.** `tests/test_m07a_surface_chain.py` fails 18 (on `88cc22b8` and after
  this order): the chain ends at F3's c_10 (`D_10` = `f7ec3c94…`) and the served list is now `9a4b4eb3…`. F3 closed
  that with link c_10 and its register entry R-1051 (`a66116d9`). F2 needs `strip_f2` (`without_f2`), a link c_11
  with `D_11` = `F2_SERVED_SHA256`, and an R-number in `docs/decision-register.md`, whose allocation this order does
  not own (X06 runs concurrently). Left for the orchestrator, with the ADR 0019 pointer (WO6).

## F2-WO3 (surface link c_11, variable ids, layout), 2026-11-26

- **c_11 closed.** `scripts/m07a_rc.py` gains `strip_f2` (s_11 = `without_f2`) and link c_11 (R-1072, `D_11` =
  `9a4b4eb3…` = `F2_SERVED_SHA256`), on top of c_10. `tests/test_m07a_surface_chain.py`: the earlier links' tests strip
  F2 first (the latest first), every control carries c_11; new `test_f2_link_c_11_is_f2s_strip_and_digest` and
  `test_f2_control_c_11_left_in_place`. 34 passed, 0 failed (18 failed before). Item 4 is unchanged: F2 adds no tool
  and changes no description file.
- **DECISION WO3-1. R-1072's entry is carried onto wp/F2 with its evidence filled.** The c_4 to c_10 pattern asserts
  that the link's register entry carries `D_k` and `D_{k-1}` in full; R-1072 exists on `main` only (`af1fb212`,
  "reserved", evidence "to come"). Appended on wp/F2 after R-1070 with main's text, its Evidence row filled with the
  two full digests and the two test names; heading and decision text unchanged (status stays "reserved"; the
  orchestrator's). The merge resolves the register hunk by taking main's R-1071 and R-1073 around this entry.
  Alternative: no register assertion in the c_11 test (a weaker test than c_10's). Reversible: revert the register
  commit and drop the test's last five lines.
- **Built.** `src/openflowsheet/material/vid.py` (D7: `VariableId`, render only; the closed field table;
  `legacy_variable_id` = `models`' `flow_id`/`temperature_id`/`pressure_id`, duplicated because `material` sits below
  `models`, a test pins the equality), `src/openflowsheet/material/layout.py` (D8: `MaterialLayout.build`,
  `state(x, c)`, `value(x, c)`, `document()`), `tests/f2/vid_parse.py` (the left inverse),
  `tests/test_f2_vid_layout.py` (36 tests). E-F2-5 (ids): 10^4 structures, 8,756 distinct renderings, parse inverts
  each, 0 collisions, 0 equal to any of 37,457 legacy-form ids, qualified phases on all four families. E-F2-6: 2,000
  generated revisions, 3,514 material states and 59,935 slots bit for bit against an independent D3 builder (shuffled
  variable order, foreign ids, `±0.0`, 5e-324); `vid_parse` not importable from `src/` (subprocess, `-I`), no `src/`
  import of it, no string-splitting call in `vid.py`/`layout.py`. Three order mutations (attribute component order,
  class order, group order) each fail the suite. WO4's fixtures and WO5's probes extend E-F2-6 to their states.
- **DECISION WO3-2. `MaterialState`** (D8 names it; no ADR defines it): `connection`, `definition_sha256`,
  `thermal_coordinate`, `substreams` (`SubstreamState`: `substream`, `carried`, `attributes`, each in layout order),
  `thermal` (h in J/kg or T in K), `pressure`; `is_dormant` per D4 on both. ADR-F4/F6 may widen it.
- **DECISION WO3-3. Layout inputs.** `build(connections, facts, variable_ids)`: each slot's `variable_index` is the
  position of its rendered id in the problem's variable order (render, never parse). `MaterialFacts`: component-set
  order (`nTP-v1`), per component `amount_basis`, molar mass (`None` for `kg`, M = 1), charge; per attribute kind
  `scope`, `partition`, `classed`, `quantity_kind`. M_g is `basis.group_molar_masses` at build.
- **DECISION WO3-4. Slot quantity kinds.** Carried amount by basis (`mol` molar_flow, `kg` mass_flow, `segment_mol`
  segment_molar_flow); a class its component's; a group molar_flow; an attribute its kind's; `h` specific_enthalpy,
  `T`, `P`, `Q` heat_rate, `W` power, `s` the instance's kind.
- **DECISION WO3-5. D3's "component order" for non-partition attributes** is the substream's component order, not the
  attribute's own list order (normalisation keeps that list as given). Changes no byte; for the ruling round.
- **DECISION WO3-6. What the layout refuses (`ValueError`, ahead of WO4's typed codes):** a group basis whose species
  are not exactly the substream's components, or with a partition attribute (D3 is silent on a group basis over a
  subset); a partition attribute without components or classes; a component in two partition attributes; a classed
  attribute without its substream's grid; a slot id missing from the variable order or shared by two slots. The id
  structure does not encode index roles (`n[x]` is a component or a group by the definition), so two slots of one
  connection rendering alike is refused here.
- **DECISION WO3-7. Field-table shapes.** Connection `n`: on a substream, 1-2 indices; `a`: on a substream, 1-3;
  `h T P Q W s`: no substream, no index. State-point fields: substream and indices free (ADR-F5/F6 fix them).
- **DECISION WO3-8. `material_layout`** = per connection `connection`, `definition`, `definition_sha256`, `slots`
  (`substream`, `field`, `index` with class indices as JSON integers, `quantity_kind`); no M and no dormancy
  partition (floats stay out of R0). No schema file yet (E-F2-10 is WO6's).
- **WO2b residue fixed.** The acceptance battery found one failure outside the brief's named suites:
  `tests/test_m02_schemas.py::test_g1c_...` (`list_models` at `854fab33…` = `SNAPSHOT_F2`, not M02's base `12d88245…`),
  and `tests/test_m04_study_job.py::test_a42_...` likewise: both decompositions lacked `without_f2` (WO2b covered
  t07/t08/m07a). Both now take F2's additions out first, the later first; nothing relaxed. Sweep of M0x, MSG, X0x,
  OPT, ST suites after the fix: 4,390 passed, 0 failed.

## F2-WO4 (`ProcessRevision` v2, `Specification` v2), 2026-11-27

Files: `schemas/{process-revision-v2,specification-v2}.schema.json` (+ `registry.json`),
`src/openflowsheet/revision_v2/{__init__,parse,validate,canonical}.py`, `src/openflowsheet/material/layout.py`
(`draft_connection`, `LayoutRefusalError`, `temperature_substream`), `tests/fixtures/schemas/v2/` (context, 2 valid, 9
invalid revisions, 7 specifications, 30 refusal fixtures), `tests/test_f2_revision_v2.py`, layer registrations
(`tests/test_package_imports.py`, `.codehealth/config.toml`). No sha256-named member is added, so no numerical-policy
addendum is needed (the closed partition audits names containing `sha256`).

- **DECISION WO4-1. The validator reads a caller-supplied `ValidationContext`**: component facts by component id
  (`material.layout.ComponentFacts`), attribute-kind payloads, per model id its ports (`PortFacts`: kind, direction,
  accepted templates, signal kind), manipulable parameters (name -> quantity kind) and `one_definition` (D11's generic
  transport unit), the legacy providers and native conventions, the components a method confines (Q8.R7) and its
  equilibrium-solid candidates (Q8.R1). WO6 builds it from the record store, the registry and the manifests.
  Alternative: the validator reads the stores itself (it would sit above `models` and `application`).
- **DECISION WO4-2. Layer and hash rule.** `revision_v2` sits directly above `material` (below `thermo`), so it
  cannot import `application.revisions`; `CONTENT_HASH_EXCLUDED` is repeated in `revision_v2.canonical` with the same
  name and members, a test holds it equal to v1's and `content_hash(d) == application.revisions.content_hash(
  canonical_document(d))` (WO3's `legacy_variable_id` precedent). Alternative: move the v1 function to a low module.
- **DECISION WO4-3. Canonical form and `content_hash`.** The normal form normalises each `materials.definitions` entry
  by D3 (`normalise_instance`; groups by id, attributes by (kind, components)); every other list keeps its order.
  `content_hash` is v1's rule over the normal form, so two spellings of one definition share it. Alternative: the
  hash of the document as given (group order would then move it).
- **DECISION WO4-4. Codes outside ADR 0062's table.** Structural faults take existing catalogue codes:
  `id_duplicate(id)`, `component_unknown(component)`, `instance_missing(instance)`, `model_unsupported(instance,
  model)`, `port_unsupported(instance, port)`, `connection_kind_unsupported(connection, port)`,
  `port_direction_conflict(connection, port)`, `specification_target_unknown(specification)`,
  `capability_unknown(kind)` (an unregistered attribute kind). A D3/D11 rule with no code is
  `schema_invalid(pointer)`: two `mixed` substreams, grid edges not increasing, gcd(p, q) != 1, components not a
  subsequence of the set's order, a reaction component outside its scope, a group basis whose species are not its
  substream's components, an attribute's scope against its `components`, a partition on a group basis, a reference to
  a missing definition or reaction set. Param names (the catalogue entries are WO7's): definition-level codes
  `{definition, substream[, kind | species]}`, state-level `{connection, substream[, kind | group]}`, port-level
  `{connection, port}` with port `<instance>.<port>`, `unit_coordinate_unsupported{instance, coordinate}`,
  `construct_unavailable{construct, foundation}`, `parameter_binding_conflict{target}`.
- **DECISION WO4-5. Schema readings.** Every member is required except `content_hash`, `title`, `description` (one
  spelling; WO2-6's precedent): `reaction_sets: []`, `sections: {}`, `materials.definitions: []`,
  `property_methods.overrides: []`. `materials.definitions` holds `mat-v1` instances only (D11: energy and signal
  connections name templates). Preview members are untyped (`property_methods.default`, `method_set`, `template`,
  `phase_assertion`, section `body`); `references` is a list of strings; `kinetics` is an open object with `kind` and
  `version`. Endpoint positions are the schema's: a probe only in `from`, a parameter or specification only in `to`,
  both only on a signal connection; `quantity_kind` only (and always) on a signal connection.
- **DECISION WO4-6. One fault, one refusal.** A variable target that does not resolve because its connection's
  definition is refused (no ids can be rendered) is not reported a second time.
- **DECISION WO4-7. Specification kind: D10 strict.** A specification's `kind` must equal its target's (D10), else
  `quantity_kind_mismatch(specification)`; a molar kind on a `kg` component's amount is
  `amount_basis_mismatch(component)` (Q7.R5, Q7.A5). Q7.R5 also says a mass input for a `mol` component "is converted
  at validation"; D10 refuses it. **Design-lane question** (D10 against Q7.R5); default: D10 (refusing now and admitting
  later moves no byte).
- **DECISION WO4-8. Solid roles.** `solid_role_conflict(component)` for a component in two substreams other than
  `mixed` plus `solid` (two solids, `mixed` plus `nonconventional`), a solid-substream component the method confines
  (Q8.R2), and (Q8.A6) an attribute in `mixed` on a confined component or an equilibrium-solid candidate (Q8.R4: an
  equilibrium phase carries no attribute). Q8.A2's definition-level part is `mixed_solid_candidates` (a method's
  candidates minus the solid-substream components). **Design-lane question**: Q8.A6's code (none is named).
- **DECISION WO4-9. `state_degenerate_in_definition` is not built.** Q1.R5 decides it at a state point of a
  `T`-coordinate definition (degenerate in T), which needs a property evaluation (ADR-F5/F6). E-F2-9 covers the other
  19 codes; the coverage test names the exception.
- **DECISION WO4-10. State-level codes** (`state_refusals(revision, context, layout, x, connection, feed=)`):
  `attribute_on_zero_parent` (a component-scoped attribute's parent is its component's carried slots, a
  substream-scoped one's the substream), `group_amount_negative` (group bases), `feed_not_electroneutral` when a charge
  row ζ exists and |Σ ζ b| > 1e-12 Σ |ζ| b (Q3.A4's bound, `math.fsum`). Which connections are feeds is the caller's.
- **DECISION WO4-11. Basis results.** (i) or (ii) failing is `species_basis_incompatible(definition, substream)`
  (WO2's open default, at the definition level), rank `species_basis_redundant`; (iii) is the notice
  `species_basis_not_monotone` (`BasisCheck.valid` excludes it, Q3.R1) and Q3.R7's miss the notice
  `molar_mass_inconsistent` (validation class, as `records.reactions` reports it).
- **DECISION WO4-12. Bindings.** `parameter_binding_conflict` when a parameter is bound by more than one of: a signal
  sink, a v1-form specification on `parameters.<p>`; or a specification sink by two signals. D9's "time input" does
  not exist yet (ADR-F7). A signal's kind is checked against its port's `quantity_kind`, a probe target's kind, a
  parameter's manipulable kind and a specification sink's `kind`.
- **DECISION WO4-13. Port compatibility by template.** A port accepts templates; `definition_incompatible` when the
  connection's is not among them. "`h_mass` admits `std.*` units only" reads the model id prefix `std.`. A
  `one_definition` unit fed two definitions: `attribute_grid_mismatch(connection, port)` when they differ only in
  grid edges, else `definition_incompatible`; subset fill and declared maps are ADR-F6's.
- **DECISION WO4-14. Convention and methods.** A convention other than `ELEMENTAL-ref-v1` or a context native one is
  `construct_unavailable(convention:<id>, F4)`; `property_methods` other than one known legacy provider and no
  overrides is `construct_unavailable(property_methods, F4)` (D11's 0.5 rule).
- **DECISION WO4-15. Q8.A4's T rule** (`MaterialLayout.temperature_substream`): `mixed` when it flows, else the first
  flowing substream in instance order, `None` for a dormant stream. **Design-lane confirmation** wanted (Q8.R6 says
  "fixed by the flowing substreams" without an order).
- **E-F2-8 readings.** Q7.A1: with no method map in 0.6 (derived targets refused), the row-level check is a
  specification's kind against its target's; the "admitted through a declared map" half waits for F4. Q7.A2 on the
  fixtures' states (bitwise, 2 connections x 20 states x 2 fixtures and more); WO5's probes add its probe streams.
- **WO3-6, typed.** `LayoutRefusalError(ValueError)` carries `coded` for a classed attribute without its substream's
  grid (`attribute_grid_mismatch`) and a component in two partition attributes (`attribute_redundant`), equal to the
  validator's refusal for the same definition (tested); the layout's other refusals stay `ValueError`.
- **DECISION WO4-16. Minimal catalogue entries now, prose in WO7.** MSG-G2 (`test_msg_coverage`, E-F1-10,
  E-F3-11) requires an entry for every code the scan finds in `src/`; the battery after the first WO4 commits failed
  those 3 tests on 8 scanned codes. Each code the validator emits that had no entry gets an entry in the style of
  `schema_invalid` (`complete: false`, title and one-line summary; 17 refusals in `refusals.yaml`,
  `species_basis_not_monotone` in `notices.yaml`), and `scripts/doc_pages.py` re-emits `docs-site/messages/
  {refusals,notices}.md`. Alternative: allow-list the codes in `scan-allow.yaml` (whose lines are tokens that are not
  codes: a relaxed check, refused). `state_degenerate_in_definition` (not emitted) gets none. The existing
  `molar_mass_inconsistent` entry (F3: `args: [reaction]`) does not declare the basis notice's params
  (`definition, substream, species`): WO7 reconciles it. Isolated in one commit. The catalogue digest moves
  (`9ac09855…` -> `2b227092…`), so the two `message_entry` fixtures of `test_t07_w5e_application_results.py` that
  carry it are re-pinned, as F3-WO5a did (`7e7d4f3d`); no served digest and no F0 check reads it (F0 PASS after).
- **Left for WO5/WO6/WO7.** Section bodies against registered `revision_section` schemas, `construct_unavailable(...,
  F6)` at binding, the context from the stores and `definition_sha256` per connection (`connection_inputs` takes them):
  WO6. Catalogue entries of the new codes: WO7.

## F2-WO5 (probes, E-F2-4), 2026-11-27

- **DECISION WO5-1. The probe kinds' scopes as Q6 names them (test data only).** Q6 ("Probes"): `probe.moments`
  component-scoped, non-partition; `probe.classes` substream-scoped, non-partition counts on a grid. WO3's `KINDS`
  and WO4's `context.yaml` had the two names on each other's payload (`probe.moments` substream-scoped,
  `probe.classes` component-scoped). The two names are swapped in the test data (`context.yaml`, `crystallizer.yaml`,
  three refusal fixtures, `test_f2_vid_layout.py`'s `KINDS` and generator); shapes, counts and verdicts are unchanged
  (`tests/test_f2_*.py` 288 passed before and after). `test_f2_definitions.py` (normalisation only, no kind facts)
  and the render example of `test_f2_vid_layout.py` keep their spellings. Alternative: a second payload under the
  same id in `tests/f2/probes.py` (two meanings of one kind id in one suite). Isolated in one commit.
- **Built.** `tests/f2/probes.py` (the three kinds' D5 payloads and layout facts; a `Flowsheet` of one `mat-v1`
  definition, `liq` mixed A, B, P with λ0, λ2 of P and `cryst` solid C as a size partition with counts per class;
  feed, mixer <= 8 inlets, splitter, heater in (n, ĥ, P); `conservation`, `admissible`, `deficit`),
  `tests/test_f2_probes.py` (13 tests). Measured (`~/.cache/line06/f2wo5/measure.py`): **Q6.A1** worst relative
  conservation 3.39e-16 (1.53 ε) over 1,200 random mixers (1-8 inlets), splitters (2-4 outlets) and remixes, 29x
  below 1e-14; a 1e-3 split-fraction error reads 1.00e-3. **Q1.A5** the flowing outlet's ĥ with and without the
  dormant feed: bitwise equal. **Q6.A5** 1,188 monodisperse feeds, 8-inlet mixtures and splits: all admitted, 227
  fail the strict test, worst deficit 6.27e-16 (<= τ_mono/100 = 1e-14). **O-9** with the recycle of loop gain 100:
  worst deficit 4.86e-14 (≈ 219 ε, on the recycle's iterates), margin to τ_mono **20.6x** (>= 10x, no amendment);
  fixed points reached bitwise in at most 3,295 iterations. **Q7.A2, E-F2-6** on 300+ probe states (the Q1.A5 sheet,
  40 random sheets, the invalid trials): layout read = probe state = independent build, bitwise; ṁ bitwise.
- **DECISION WO5-2. `probe.moments` holds λ0 and λ2 as classes 1 and 2 of a two-class `order` grid** (edges
  `[0, 1, 2]`, `dimensionless`): D3 gives a component-scoped kind one value per (component, class), and Q6 names one
  kind for both moments. Inequality terms (D5 leaves their grammar open): `n` the parent amount (λ1), `a[k]` class k,
  `x*y` a product; `parent_kind: null` on all three. Alternative: two kinds (λ0, λ2). Test-only, `tests/f2/probes.py`.
- **DECISION WO5-3. Probe rows.** Mixer `P_out = min P_k`, energy row solved as `ĥ = Σ(ṁ_k ĥ_k)/ṁ_out`; splitter
  outlets by fraction but the last, which takes the balance; heater duty-specified, `ĥ = (ṁ ĥ_in + Q)/ṁ`; a dormant
  heater needs `Q = +0.0`; a dormant feed's ĥ is `+0.0`. Derived `T` is listed only for a dormant stream (null,
  `zero_flow`): a flowing one needs a property call. Test-only.
- **DECISION WO5-4. O-9's "recycle of loop gain 100"** = recycle fraction `1 - 1/100` of a probe splitter back into
  the feed's mixer, iterated by successive substitution from a dormant tear to a bitwise fixed point of the recycle,
  per monodisperse feed of DP x amount (14 loops); the deficit is the worst over every iterate's three streams.
  Alternative: the converged state only (smaller worst value).
- **Q-WO5-a (design lane). Q6.A2's registration half is not testable as written.** "Registering `probe.partition`
  together with its parent's amount, or a polymer kind with λ1, is refused `attribute_redundant`": D3's layout
  cannot carry a partitioned component's parent at all (tested: C has class slots only), and the D5 payload has no
  field that names λ1 or another index identity, so F1 cannot refuse such a kind at registration (`src/` has no
  such check). Tested instead: the partition alone admitted, a second partition on its component refused
  `attribute_redundant`, the parent sum bitwise reproducible. *Needs:* the payload field (or rule) F1 decides it on.
- **Q-WO5-b (STOP candidate, design lane). A second definition id with an equal body is refused
  `attribute_grid_mismatch`.** `validate.py` `one_definition_rules` compares definition ids; two ids whose bodies
  (and SHAs) are equal, on a `std.mixer`, report `attribute_grid_mismatch(S2, mix.in2)` although the grids are
  identical. D3 makes the SHA the identity ("equal definitions ... share a SHA"). Not changed (a `src/` change); the
  Q6.A4 "same grid admitted" case uses one id. *Default if ruled a defect:* compare bodies (or SHAs), admit equal ones.
- **Q-WO5-c (ADR-F6). A flowing stream whose ṁ underflows to 0.0** (5e-324 of a molar component; dormancy is on the
  amounts, D4) has an energy row of rank 0 in ĥ that is not a zero-flow form. The probe raises
  `ProbeUnresolvedError` (tested) rather than choose; Q1.A5 asserts only that such a stream is flowing.
- **Gate at `15e82c82`.** WO4's battery suites plus `tests/test_f2_probes.py`: 5,609 passed (5,596 + 13), 28 skipped,
  3 xfailed, 0 failed; ruff, ruff format --check, `mypy src` clean; F0 PASS M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52,
  M8 105/105, M9 42/42 (`~/.cache/line06/f2wo5-final.log`). No `src/` file changed in WO5.

## F2-WO6a (lowering, raising, `solution-state-v2`), 2026-11-27

Files: `src/openflowsheet/revision_v2/{lower,raise_v1}.py`, `tests/f2/legacy_providers.py`,
`tests/test_f2_lowering.py`.

- **DECISION WO6a-1. Provider selection is a caller-supplied `LegacyProviders`** (ADR 0050 D1's
  registered record sources by string equality, SYN-001's otherwise; each with its provider id and
  native convention). `revision_v2` sits below `models` and `thermo`, which hold the registry
  (`models.revision_flowsheet.component_basis`) and the conventions; WO4-1's pattern. The legacy
  records are read from the committed legacy index (`records` is below `revision_v2`).
  `tests/f2/legacy_providers.py` builds it from `component_basis` and the providers' constants;
  WO6b builds the same in the application. Alternative: a copy of the table in `revision_v2`
  pinned by a test (WO4-2's pattern).
- **DECISION WO6a-2 (design-lane question). D12's "one file whose component list equals
  `component_set` in order"** is read as: every record is a legacy component record of one file,
  under its id there; the lowered `components` are the set's ids in its order. As written, it
  refuses the corpus's `SYN-001-T06-STA04` (components C, A, B: a permutation v1 binds, T06 §8.6),
  so E-F2-3's "every corpus revision" fails 58/59 (measured at `fa81bdcf`), and it refuses every
  CoolProp revision (one fluid of the S07 file's 123). Isolated in one commit; reverting it
  restores the literal reading (`component_set` refused, F4).
- **DECISION WO6a-3 (design-lane question; STOP class "a construct D12 does not classify").** D11
  fields D12 neither maps nor lists, and v1 has no field for, are refused, not dropped:
  `semantic_role:<role>` for D11's four new roles (F6, which owns the vocabulary),
  `template:<instance>`, `references:<instance>` (F6), `phase_assertion:<connection>` (F5), a
  non-empty `parameter_sets` (F4). Refusing now and admitting later moves no byte (WO4-7's
  argument). `materials` is dropped whatever it holds, as D12 says (`phase_order_keys` included).
  Construct spellings follow `validate`'s `kind:id` (`convention:<id>`, `derived:<id>`).
  Isolated in one commit. *Needs:* a ruling per field (refuse, or drop when empty).

### WO6b dispatch map (measured at WO6a on a raised `SYN-001-T06-NET02`, `~/.cache/line06/f2wo6a/v2today.py`)

| # | Site | What a v2 document meets today | WO6b |
| --- | --- | --- | --- |
| 1 | `models/revision_flowsheet.py:384` `parse_revision` | misread as v1: `RevisionError(unsupported, components_unsupported)` (the component entries are objects) | D12 dispatch on `schema_version` (2: `revision_v2.parse`, `lower` for the v1 path); v1 reader untouched |
| 2 | `application/revision_binding.py:547` (revision binder) | `Unbound` from row 1's error | read the lowered document |
| 3 | `application/binding.py:995` (legacy binder) | row 1's error | as 2 |
| 4 | `application/stream_table.py:263` | row 1's error | as 2 |
| 5 | `verify/certificate.py:444` | row 1's error, through its `RevisionError` branch | as 2 (the verifier must read what the binder read) |
| 6 | `studies/nlp/boundary.py:115` | row 1's error, not caught there | as 2 |
| 7 | `application/validation.py:388` / `:413` `_first_schema_error` | `schema_invalid` at the root: additional properties `convention`, `materials`, `property_methods`, `reaction_sets`, `sections` | v2 schema (`revision_v2.parse`) and `revision_v2.validate` with a context from the stores |
| 8 | `application/capabilities.py:274-280` `_draft_pairs` | `api_error(revision_unsupported)`, "schema_version 1 ... not 2" | admit 2 (D11's draft form; ADR 0060 D11) |
| 9 | `application/validation_service.py:57` `validate`, `:247` `check_admission` | rows 7 and 8 | Amendment 9; F2's checks into `AdmissionReport` notices/refusals |
| 10 | `application/revision_service.py:61` `commit_change`, `:173` `preview_change`, `:219` `diff_revisions` (`local.py:386`, `:507`) | refused by the v1 schema gate (row 7) | Amendment 9: accept v2; `ChangeSet` paths address v2 fields unchanged |
| 11 | `application/revisions.py:67`, `application/store.py:368` `content_hash` | v1's rule over the document as given: equal to `revision_v2.content_hash` only when every definition is in D3's normal form (WO4-3) | `revision_v2.content_hash` for v2 |
| 12 | `application/revision_run.py:205` `select_route`, `:754` `run_revision_session` | no route (rows 2, 3) | run submission of v2 (E-F2-3 run half: the lowered run's artifacts byte-identical, manifest revision ref v2) |
| 13 | `run/bundle.py:175`, `:195` `verify_bundle` | a `solution-state-v2` fails `inconsistencies` (v1 schema) | dispatch to `inconsistencies_v2` on `schema_version` (only v2-compiled runs write v2, ADR-F6; lowered runs write v1) |
| 14 | `LegacyProviders` | built in tests only (`tests/f2/legacy_providers.py`, WO6a-1) | build it in the application from `component_basis` and the providers' conventions |
- **DECISION WO6a-4. `definition_sha256` is classified exact** in a new addendum
  `benchmarks/f2/numerical_policy_external.yaml` (`solution-state-v2.schema.json`; F3's pattern,
  audited after F3's): its preimage is a canonical document (D3), never a solved value.
  `state_sha256` keeps v2's class (float digest). The battery at `9233a9d1` failed 3 tests on the
  new schema and caches (the closed `sha256` partition; the global-state allowlist, `cache` 46 ->
  49: the v2 validator, `legacy_records`, `file_components`); fixed in one commit with the
  registrations (`tests/test_m05_study_record.py`'s ADDENDA order, `tests/test_t07_global_state.py`
  count and allowlist). Alternative: list the name in v2's own `exact_sha256` (moves a registered
  policy's bytes).
- **Gate at `7ce12c23`.** WO5's battery suites plus `tests/test_f2_lowering.py` (93) and
  `tests/test_f2_solution_state_v2.py` (35): 5,737 passed (5,609 + 128), 28 skipped, 3 xfailed, 0
  failed; ruff, ruff format --check, `mypy src` clean; F0 PASS M1 50/50, M2-M5 61/61, M6 85/85,
  M7 52/52, M8 105/105, M9 42/42 (`~/.cache/line06/f2wo6a-final2.log`). E-F2-3 library half:
  59/59 corpus revisions (M1's 50 + F0's 9 basis cases) raise and lower to their canonical bytes.
  Left for WO6b: the dispatch map above; `LegacyProviders` in the application.

## Design-lane rulings R1 (D12), 2026-11-27 (brief `docs/briefs/LINE06-F2-R1.md`)

**R1-1 (WO6a-2), the one-file criterion. Ruling: the engineer's reading; keep `6f81897e`.** Criterion: every
component record is the legacy component record (ADR 0061 D12) of one file F, under the component's own id there, in
any order and for any subset of F's components; the lowered `components` are the set's ids in the set's order.
Reason: v1's `{record_source, components}` carries its own ordered list, and the v1 binder takes a permutation (T06
§8.6) and a subset (CoolProp's one fluid of 123), so F's order holds nothing lowering needs. The literal text is
stricter than v1: "v1-expressible" would exclude v1 documents, and ADR 0062 risk 1 allows excluding a corpus revision
from E-F2-3 only by a ruling; this ruling corrects the criterion instead. Byte identity (D8) holds by construction: the
binder reads a v2 document as `lower(parse(d))` and hands the result to the untouched v1 path, and that result has the
original's canonical bytes and v1 `content_hash` (59/59 at `7ce12c23`, STA04 included); the only artifact field that
sees the v2 document is the manifest's revision reference. Tests: (library, exist)
`test_e_f2_3_corpus_revision_raises_and_lowers_to_its_bytes[SYN-001-T06-STA04]` and
`test_a_permuted_component_set_lowers_in_its_order` (lowered `components` C, A, B, not the file's order: falsifies a
re-sorting lowering); (run, WO6b) E-F2-3's run half over the 59 asserts D8 in full: every bundle artifact of the
raised v2 run byte-identical to the corpus v1 run's, except the manifest's revision reference, which is the v2
`revision_id` and `content_hash`. STA04 and the five `s10` GP cases are in the 59. Add one CoolProp one-fluid `s07`
revision: library half always, run half under the CoolProp extra (CI runs it).

**R1-2 (WO6a-3), fields D12 does not classify. Ruling: keep `90f46174`, with two amendments (fix work order F2-WO6c
below).** Rule: a field v1 has no counterpart for lowers only in its content-free form (absent when optional, empty
when required); any other form is refused. Refusing now and admitting later moves no byte of an accepted document;
dropping now and giving the field meaning later would change what an accepted document computes.

| Field | Ruling | `construct_unavailable` |
| --- | --- | --- |
| `semantic_role` `utility`, `controller`, `shaft`, `relief_device` | refuse (v1's 14 roles are copied) | `semantic_role:<role>`, once per role, F6 |
| instance `template` (preview) | refuse when present, any value (`null` included) | `template:<instance>`, F6 |
| instance `references` | refuse when present, `[]` included (whether `[]` means absent is F6's to define) | `references:<instance>`, F6 |
| connection `phase_assertion` (preview) | refuse when present, any value | `phase_assertion:<connection>`, F5 |
| `component_set.parameter_sets` | **changed:** must equal F's legacy parameter-set records in the legacy index's order (`s10`, `s10-verification`: one each; the other five files: none), else refuse; checked only when the component set names one file (WO4-6's pattern) | `parameter_sets`, F4 |
| `materials.definitions`, `phase_order_keys` | drop whatever they hold: no `nTP-v1` connection reads a definition; the keys order phases within a family (D6 leaves that to F5), and an `nTP-v1` connection has at most one phase per family (v1's `phase_capability`) | none |
| `materials.thermal_coordinate` | **new:** must be `T`, else refuse | `thermal_coordinate:<coordinate>`, F6 |

Why `parameter_sets` changes: the five corpus `s10` revisions (GP-C1, GP-C2, GP-C3, GP-M1, GP-M2) run the Wilson
provider, which reads the file's `wilson_lambda` block; ADR 0061 D12 imports that block as the file's legacy parameter
set. Raised with `parameter_sets: []`, the v2 document states no parameter set while its lowered run uses one, and the
document that states it is refused. D8's fingerprint departure rests on "the problem is identical", so the v2 document
must state the problem it runs as. v1's `record_source` names the whole file; its inverse is the named components'
records plus the file's parameter sets. The 59/59 library identity is unchanged (lowering drops the stated set); only
the five raised `s10` documents gain one SHA. Why `thermal_coordinate`: WO6b's binder lowers without `validate`, and
`validate` checks `unit_coordinate_unsupported` per `h_mass` `mat-v1` definition only, so a document with
`thermal_coordinate: h_mass` and only `nTP-v1` connections passes both today and would run in T. D11: `T` admits
`nTP-v1`; `h_mass` admits `std.*` units only. Lowering checks it itself, so its criterion stands without `validate`.

**R1-3 (WO6a-4): confirmed; keep `7ce12c23`.** `definition_sha256`'s preimage is a canonical input document (D3),
never a solved value: exact, in the F2 addendum (F3's pattern), which moves no registered policy byte.

**D12 text to apply** (the orchestrator replaces D12 from "**Lowering**" to the end of the "**Raising**" sentence; the
Amendment 9 part stays; D13 is unchanged and freezes this criterion):

> **Lowering** (`revision_v2/lower.py`): a v2 document is *v1-expressible* iff (a) its convention is the native one of
> the legacy provider ADR 0050 D1 assigns to its record source, and `property_methods.default` is that provider with
> no override; (b) `materials.thermal_coordinate` is `T`; (c) every material connection is `nTP-v1`, and it has no
> energy or signal connection, reaction set, section, probe or parameter endpoint, specification target outside v1's
> form, connection `phase_assertion`, instance `template` or `references`, or `semantic_role` outside v1's vocabulary;
> (d) its component set is legacy: every component record is the legacy component record (ADR 0061 D12) of one file,
> under the component's own id there, in any order and for any subset of that file's components (as v1's
> `record_source` binds them), and `parameter_sets` lists exactly that file's legacy parameter-set records, in the
> legacy index's order. The criterion stands without `validate`. Such a document lowers to the v1 document with
> `record_source` = that file and `components` = the set's ids in the set's order (ADR 0001 D2.1); anything else is
> refused with every construct found, once each, as `construct_unavailable(<construct>, <foundation>)`:
> `convention:<id>`, `property_methods`, `component:<id>`, `component_set` (records of two files), `parameter_sets`,
> `derived:<id>` (F4); `phase_assertion:<connection>` (F5); `thermal_coordinate:<coordinate>`, `definition:<id>`,
> `energy:<c>`, `signal:<c>`, `probe:<c>`, `parameter:<instance>.<parameter>`, `reaction_set:<id>`,
> `section:<namespace>`, `target:<specification>`, `semantic_role:<role>`, `template:<instance>`,
> `references:<instance>` (F6). `convention`, `property_methods` and `parameter_sets` are checked only when the
> component set names one file. Lowering is a field map. A connection with `definition: nTP-v1` becomes
> `state_definition: nTP-v1`, `component_mapping: revision_component_set`. `phase_capability`, `initialization_hint`
> and `notes` are copied. Instances and specifications in v1's target form are copied. `convention`, `materials`
> (whatever its definitions and `phase_order_keys` hold: no `nTP-v1` connection reads them) and `property_methods` are
> dropped. A field v1 has no counterpart for lowers only in its content-free form, absent when optional and empty when
> required: admitting a construct later moves no byte of a document accepted now, and giving a dropped one meaning
> later would. Lowering does not anticipate the v1 binder: a lowered document the binder refuses is refused as its v1
> twin is. **Raising** (`revision_v2/raise_v1.py`, test and tooling only) inverts the map, with `convention` = that
> provider's native convention, `materials` = `{thermal_coordinate: T, definitions: []}` and `parameter_sets` = the
> file's legacy parameter-set records.

Reason line for the ADR edit: "Corrected before acceptance by design-lane ruling F2-R1 (`docs/F2_DECISIONS.md`): the
literal one-file criterion was stricter than v1 (it refused `SYN-001-T06-STA04` and every CoolProp revision), raised
`s10` documents did not state the parameter set their run uses, and the binder lowers without `validate`."

**Fix work order F2-WO6c** (Opus; after WO6b commits, in `wp/F2`; files `revision_v2/{lower,raise_v1}.py`,
`tests/test_f2_lowering.py`, this log):
1. `lower.py`: `file_parameter_sets(path) -> tuple[str, ...]`, the `parameter_set` records of the legacy index entry
   with that path, in index order. When the component set names one file F, refuse `parameter_sets` (F4) unless
   `component_set.parameter_sets == list(file_parameter_sets(F))`; drop the unconditional non-empty check. Refuse
   `thermal_coordinate:<c>` (F6) unless `materials.thermal_coordinate == "T"`. Module docstring = the D12 text.
2. `raise_v1.py`: `parameter_sets = list(file_parameter_sets(record_source))`.
3. Tests: raised GP-C1 states exactly the legacy index's one `s10` set; the raised syn001 base states none; GP-C1 with
   `[]` and the base with the `s10` set or `["0" * 64]` are refused `parameter_sets`; a two-file component set with a
   non-empty `parameter_sets` gives only the component refusals; the base with `thermal_coordinate: h_mass` is refused
   `thermal_coordinate:h_mass`; E-F2-3 library half stays 59/59.
Acceptance: `tests/test_f2_lowering.py` and WO6b's E-F2-3 run half pass; surface suites and F0 PASS; ruff, format,
mypy clean. A pinned v2 `content_hash` of a raised `s10` document may move (unreleased test data: re-pin and log it);
any served digest or F0 move is a stop.

**Open, with defaults.** (1) `validate` applies D11's "`h_mass` admits `std.*` units only" per `h_mass` definition, not
to every instance of an `h_mass` revision (fact-free design call): default, no `validate` change in F2; the F2
`reviewer` pass rules on it (check the valid `crystallizer` fixture first). (2) The user's ADR 0062 acceptance card
(the user's sign-off): default, one line: "D12's lowering criterion corrected before acceptance (F2-R1): v1's permuted
and subset component sets lower; a legacy file's parameter set is stated; preview and new-role fields are refused;
thermal coordinate T." (3) `s10`'s set names all three components, so a subset `s10` document states a set wider than
its components (F4's design): default, F4 admits a parameter set whose components are a superset of the set's.

## F2-WO6b (v2 dispatch in the application, run submission), 2026-11-27

Files: `models/revision_flowsheet.py` (`legacy_providers`, `lowered_document`, `parse_revision`),
`application/{revision_binding,binding,stream_table,revision_run,revisions,validation,capabilities}.py`,
`application/jobs/runner.py`, `verify/certificate.py`, `studies/nlp/boundary.py`, `run/bundle.py`;
`tests/test_f2_amendment9.py`; ADR 0019 Amendment 9; `docs/interfaces-frozen.md` (F2 paragraph). Built on
`6f81897e`/`90f46174` (WO6a-2, WO6a-3 as committed); F2-R1's corrections come with F2-WO6c.

- **DECISION WO6b-1. `LegacyProviders` is built in `models.revision_flowsheet.legacy_providers()`**, not in
  `application` (map row 14 said the application): `parse_revision` (models, row 1), the verifier (row 5) and the
  NLP boundary (row 6) sit below `application` and must lower. `models` holds the registry (`component_basis`) and
  sits above `thermo`, whose constants give the conventions; the function reads no file and is not cached. A test
  holds it equal to `tests/f2/legacy_providers.py` (built independently). Alternative: build in the application and
  pass it down (a new parameter on `parse_revision` and every reader). Reversible by moving the function.
- **DECISION WO6b-2. A reader's v2 refusal.** `lowered_document` returns a v1 document itself (the same object, so
  every v1 path is byte-for-byte the old one) and lowers a v2 one; the v2 schema's refusal raises
  `RevisionError("unsupported", "schema_invalid(<pointer>)")`, a lowering refusal `RevisionError("unsupported",
  "<first construct_unavailable>", hint=<all>)`. Binders return it as `Unbound`; `select_route` returns `NoRoute`
  with it as both binders' refusal; `bind_route` returns it.
- **DECISION WO6b-3. `validate` of a v2 document**: `SCHEMA-01` applies `process-revision-v2.schema.json`; then
  `revision_v2.validate` (context: WO6b-4) and the lowering; any refusal gives the schema-only `INVALID` report with
  every refusal, sorted and rendered `code(params)`, in `SCHEMA-01`'s message; otherwise every later stage reads the
  lowered document. The validator's notices are not in the report (no field; `check_admission` carries them).
  Measured: 49 of M1's 50 raised revisions give a report equal to the v1 document's; `SYN-001-T06-STR06` (a
  specification naming component `D`, outside the set) is refused at `SCHEMA-01` `component_unknown(D)` where v1
  reports COMP-03; both `INVALID`.
- **DECISION WO6b-4. `revision_context`** (the `ValidationContext` "from the stores"): a component whose record is a
  legacy component record, with its file's basis molar mass, `mol`, charge 0 (a non-legacy record is left out: the
  lowering refuses it `component:<id>`, F4); the registry's `attribute_kind` descriptors (none built in); every
  `MODEL_SIGNATURES` model, a port taking its `state_definition` (`nTP-v1`); the legacy providers and conventions;
  `confined`, `solid_candidates` and `manipulable` empty (F4 to F6). Alternative: components from the project's F3
  record store (F4's).
- **DECISION WO6b-5. `check_admission`, v2 draft**: the v2 schema's refusal is `invalid_request` at
  `/revision<pointer>`; F2's errors and the lowering's refusals, sorted, refuse `revision_unsupported` with the first
  in `detail.unbound` (`unsupported(<code(params)>)`) and all in `detail.hint`; the validator's notices join the
  report's `notices`; the pairs are the lowered draft's. A v1 document labelled `schema_version: 2` (F1's E-F1-10
  third draft request) is now `invalid_request` at the v2 schema's pointer, not `revision_unsupported`.
- **DECISION WO6b-6. `check_admission.md` not changed.** It still says `{"revision": <schema_version 1
  document>}`. Changing it moves the served digest (`F2_SERVED_SHA256`, chain link c_11) and voids both reviews of
  the text (`REVIEW.json`); left for one surface re-pin with F2's `reviewer` pass. Proposed text: `<schema_version 1
  or 2 document>` (1,493 characters, under the 1,500 limit).
- **DECISION WO6b-7. "The run manifest's revision reference" (D8)** is read as the run's record:
  `RunResult.revision_id` and `revision_content_sha256` (the stored v2 revision's, `revision_v2.content_hash`).
  `RunManifest` has no revision field and gains none (Migration proof); `revision.json` holds the lowered v1
  document, so the bundle is the v1 run's byte for byte. Route selection, binding, `run_revision_session` and the job
  runner each lower (idempotent).
- **Not done.** The optimization job (`optimize_revision`) on a v2 revision is not tested (Amendment 9 names run
  submission; its binder path lowers, untested). WO7: the `check_admission` description (WO6b-6).
- **Gate.** At `ea0c1efd`: WO5's battery suites plus `tests/test_f2_amendment9.py` (124): 5,859 passed, 2 failed,
  28 skipped, 2 deselected, 3 xfailed; ruff, ruff format --check, `mypy src` clean; F0 PASS M1 50/50, M2-M5 61/61,
  M6 85/85, M7 52/52, M8 105/105, M9 42/42 (`~/.cache/line06/f2wo6b-final.log`). The 2 failures were F1's pins of
  the pre-Amendment-9 rule "schema_version 2 is `revision_unsupported`" (`tests/test_f1_draft_admission.py`); they now
  pin version 3 as `revision_unsupported` and a v1 body labelled 2 as `invalid_request` (WO6b-5), and that file with
  `tests/test_f2_amendment9.py` passes 249/249 at the next commit. E-F2-3 run half: 56/56 (47 `g8` + 9 basis cases;
  the 5 `k05` are not revision documents; the 3 M1 revisions without a run route as their v1 documents).

## F2-WO6c (ruling F2-R1's two amendments), 2026-11-27

Files: `revision_v2/{lower,raise_v1}.py`, `tests/test_f2_lowering.py`, `tests/data/t07_global_state_allowlist.json`,
`tests/test_t07_global_state.py`. Commit `fa97cddd`.

- **DECISION WO6c-1. `file_parameter_sets(path)` returns record SHA-256s** (the v2 schema's `parameter_sets` items are
  `sha`), in the order the legacy index entry lists them (a `parameter_set` record has no `position`); `()` for a file
  with none or a path the index does not hold. `s10`: `S10-wilson-ig-real-v1` (`6634ea27...`); `s10-verification`:
  `S10-verification-v1` (`c13d5aaa...`); the other five files: none.
- **DECISION WO6c-2. `thermal_coordinate` is checked unconditionally** (with the other D11 fields in `_unclassified`),
  not only when the component set names one file: D12 gates only `convention`, `property_methods` and
  `parameter_sets`. `parameter_sets` moved into the one-file check with the convention and methods (`_one_file`).
- **DECISION WO6c-3. G20 registers the new cache** (WO6a's `7ce12c23` pattern): `revision_v2/lower.py` `@cache`
  occurrences 2 -> 3, the total `cache` pin 49 -> 50.
- **Raised `s10` v2 `content_hash` moves** (unreleased test data; no test pinned them, so nothing re-pinned): GP-C1
  `d4120e66` -> `61ec8610`, GP-C2 `b3e711f7` -> `82e9821e`, GP-C3 `f0937d32` -> `03054252`, GP-M1 `9a365d08` ->
  `42d173ec`, GP-M2 `4e5551e0` -> `8848a951`. Their lowered v1 bytes are unchanged (library half 59/59).
- **Gate** (`~/.cache/line06/f2-wo6c/acc.log`): `tests/test_f2_lowering.py` 96 passed (93 - 1 + 4);
  `tests/test_f2_amendment9.py` 124 passed (E-F2-3 run half 56/56 inside); `tests/test_f2_revision_v2.py` 107;
  `tests/test_f1_draft_admission.py` 125; surface suites 2320 passed, 1 failed, 28 skipped, the failure G20's
  (WO6c-3), then `test_t07_global_state.py` + lowering 99/99 after the fix; F0 PASS M1 50/50, M2-M5 61/61, M6 85/85,
  M7 52/52, M8 105/105, M9 42/42; ruff, ruff format --check, `mypy src` (367 files) clean. No served digest moved.

## F2-WO7 (close-out), 2026-11-27

- **DECISION WO7-1. Catalogue prose for the 18 WO4 entries** (WO4-16): each of the 17 refusals and
  `species_basis_not_monotone` has the complete style's fields (title, args, params, summary, why, action, see_also,
  example) and `complete: true`; kinds unchanged (`construct_unavailable` stays `input`, no `gap`: the entry was
  filed so by WO4, and a kind change moves no digest the gate reads but is a design-lane call). Params are the
  emit sites' (`revision_v2/validate.py`, `lower.py`, `material/layout.py`). `attribute_grid_mismatch` takes two
  parameter sets, all optional: `definition, substream, kind` (the validator, `layout.py`) or `connection, port`
  (D11's one-definition rule). `scripts/doc_pages.py` re-emitted `docs-site/messages/{refusals,notices}.md`.
  Reason text is derived from the emitting code and ADR 0062 D3/D9/D10/D11/D12, the ADR having no per-code meaning
  table; **design-lane read of the wording wanted** with the F2 `reviewer` pass. Isolated in one commit.
- **DECISION WO7-2. `molar_mass_inconsistent` reconciled** (`records.yaml`): `reaction` (F3) and `definition,
  substream, species` (F2 basis notice) are all optional params, the summary has one bracketed clause for each
  emitter, `why` gains a sentence on the species case, and a second example is added. Neither emitter dropped.
- **Catalogue digest re-pin** `2b227092...` -> `b6c8f517c53ed8ef8775acdc37502d455e89a866dcb76eb488f7f9c105f7fff9`
  in `tests/fixtures/schemas/application_results/message_entry/{valid/phase_regime_mismatch,invalid/missing_code}.json`
  (as WO4-16; no served digest, no F0 check reads it).
- **DECISION WO7-3. Optimization on a v2 revision: a finding, test `xfail(strict=True)`.** OPT-A2's revision raised
  with `raise_v1`, optimized with `optimize_revision` as the v1 document is: the optimum is equal (status
  `KKT_POINT_VERIFIED`, `candidate.decisions` equal), but identity is not: `revision.json` of every start's bundles and
  the record's `revision-document.json` are the v2 document (6,954 -> 7,090 bytes, `schema_version: 2`), so the
  `run_id`s (`opt-0a386745fbc1331b-*` -> `opt-9937eb4484b2794a-*`) and `optimization_sha256` differ. D8 says a lowered
  run is a v1 run in every artifact. Cause: neither `optimize_revision` nor the `optimize` job
  (`application/jobs/runner.py` `optimize`, which calls `optimize_revision` on the stored document) lowers; the `solve`
  job does (runner.py `lowered_document`, WO6b-7). **Not fixed (no `src/` change in WO7); orchestrator to decide**
  whether to lower in `optimize` (the fix is one `lowered_document` call there, and the record's input document
  `revision-document.json` then holds the v1 form) or to rule the optimization record's v2 input identity as is.
  Test: `tests/test_f2_amendment9.py` (`nlp` marker; run by `scripts/m03_nlp_check.sh --no-inventory`), xfails at
  the `run_ids` assertion; with `--runxfail` the optimum assertion before it passes.
- **DECISION WO7-4 (orchestrator, 2026-11-27). WO7-3 fixed: `optimize_revision` lowers.** D8 settles it (a lowered
  run is a v1 run in every artifact), so no ruling is needed: `studies/nlp/revision.py` `optimize_revision` calls
  `lowered_document` at its entry, as `run_revision_session` does (WO6b-7); the `optimize` job reaches it through that
  entry. The strict xfail is removed. `scripts/m03_nlp_check.sh --no-inventory <main>/.venv-nlp
  <main>/.reference-downloads/m03-ipopt -- tests/test_f2_amendment9.py tests/test_opt_job_nlp.py`: 7 passed;
  `tests/test_f2_amendment9.py tests/test_t07_global_state.py`: 127 passed.
- **Open (found by F8-WO1, reproduced on wp/F2 at 9d2fbe6c):** `tests/test_v03_semantic_roles.py` a29, a31_a, a31_b
  fail (3 failed, 17 passed): a29's corpus now picks up the v2 fixtures (`crystallizer.yaml` fails the v1 checks);
  a31_a finds `revision_v2/lower.py` naming a role; a31_b differs on binding outcome. Fix work order F2-WO7b.

## F2-WO8 (the F2 review's fix round), 2026-11-27 (brief `docs/briefs/LINE06-F2-WO8.md`, spec `docs/reviews/F2-review.md`)

- **DECISION WO8-1 (M1). `find_source` lowers the ancestor.** `application/revision_continuation.py` `find_source`
  passes `lowered_document(revision.as_document())` to `assemble`; on `RevisionError` it keeps the stored document,
  so A2 still refuses `source_binding(...)` (no v1 twin). Test `test_m1_a_raised_lineage_continues_as_its_v1_lineage`
  (`tests/test_f2_amendment9.py`): NET-02 split 0.5 under `default`, child 0.95 under `RRC-revision-v1`, committed
  as v1 documents and as raised ones; both `solve-path.json` byte-equal, `artifact_r0_sha256` equal, member `taken`.
  Without the fix the test fails at the child's `solve-path.json` (measured).
- **DECISION WO8-2 (M2, ruling item 1). V03 a29, a31_a, a31_b changed as ruled; the code stays.**
  `tests/test_v03_semantic_roles.py`: a29 judges a `schema_version` 2 document by
  `schema_errors("process-revision-v2.schema.json", ...)`, with the ruling's reason in `_a29_failures`'s docstring;
  control `test_a29_control_v2_role_outside_the_enum_fails` (crystallizer, `instances/0` role `purge_sink`, error
  pointer `/instances/0/semantic_role`). a31_a: `naming == [revision_v2/lower.py]`, an AST check that every
  `"semantic_role"` constant lies in `_unclassified` and that its two uses are the `not in V1_ROLES` compare and one
  f-string (the construct). a31_b: over documents whose roles all lie in `V1_ROLES`; reading of "raised v2 documents
  count": v2 documents of the corpus are not filtered out (`legacy_only.yaml` is compared; asserted), no raised
  copies are added. Control `test_a31_b_control_a_d11_role_moves_only_its_refusal`: the binder bounds an `Unbound`
  hint to `HINT_LIMIT` = 512 code points (the crystallizer's hint is 889), which cuts the two hints at different
  entries, so the control lifts `binding_common.HINT_LIMIT` (monkeypatch) and compares the whole hint; removing the
  `construct_unavailable(semantic_role:*)` entries then gives an equal outcome. 22 passed.
- **DECISION WO8-3 (S3, ruling item 2). D11's `h_mass` rule revision-wide.** `revision_v2/validate.py`
  `coordinate_rules` (run after `definition_rules`): in an `h_mass` revision each instance whose model id is not
  `std.*` is `unit_coordinate_unsupported(<instance>, h_mass)` once, connected or not, and each material connection
  with `definition: nTP-v1` is `thermal_coordinate_mismatch(nTP-v1)` (param `definition`, as the per-definition
  code). The per-end check in `connection_rules` is removed. `crystallizer.yaml` drops `lfeed`, `lsink`, `S2` and
  the spec `t_legacy` that targeted `S2`. New refusal fixtures `unit_coordinate_unsupported_unconnected.yaml` (one
  unconnected legacy feed) and `thermal_coordinate_mismatch_ntp.yaml` (the dropped trio: three errors). Index shifts
  in fixtures based on the crystallizer: `parameter_not_manipulable` 7->6, `signal_kind_mismatch` 8->7,
  `energy_definition` 6->5, `signal_without_kind` 8->7, `probe_sink` 7->6 (the same connections as before).
  `definition_incompatible.yaml` and `invalid/component_mapping.yaml` addressed `S2`, the only `nTP-v1` connection;
  both now take `legacy_only` as base (a `T` revision; `definition_incompatible` adds a `std.sink` and points `S2`
  at `sink.in`), keeping their subject. `tests/test_f2_*.py` + V03: 581 passed, 1 deselected.
- **DECISION WO8-4 (S1, WO4-15 changed). `MaterialLayout.thermal_substreams(x, c) -> tuple[str, ...]`** replaces
  `temperature_substream`: the flowing substreams in instance order, `()` when dormant; T solves
  ṁĥ = Σ_s ṁ_s ĥ_s(T, P) over them jointly (Q8.R6); Q8.A4 is the singleton case. The test's both-flowing row
  expects `("liq", "cryst")`; the two singleton rows keep the stub T check. No other caller existed.
