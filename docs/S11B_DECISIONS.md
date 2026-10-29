# S11 build decisions — track B

Build-lane choices the design note (`docs/derivations/S11-design.md`, ADR 0050) left to the engineer, for track B
(`wp/S11-b`: B1–B4). One line each, as `DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.`; each is
isolated and revertible. Measurements go in the run log below.

## Decisions

DECISION: Q8 (does the application accept `s01-default-v1` for a revision solve?) → fact: no; `application/policies.APPLICATION_POLICIES` holds T06-revision-v2, T04-W12, T08-ptc-v1, T08-warm-v1 only. The note's default (register `s11-column-v1` = `S01_DEFAULT_V1`, isolated commit) is B3's and not done (B3 stopped at Q9). Alternative: n/a. Reversible by: n/a.
DECISION: Q7 (does the binder require every multiplicity-1 port wired?) → fact: it requires every *declared* material port wired, of any multiplicity (`bind_revision_flowsheet`, `port_unwired`), so `many` does not make `top`/`bottom` optional; `ColumnUnit.ports()` declares only the ports its instance wires (the model's `PORTS` lists all five). Alternative: an optional-port notion in the binder (track A / I1 file, frozen-adjacent). Reversible by: making `ports()` return `PORTS`.
DECISION (escalated): where the column's end specifications are read → instance parameters `condenser.<kind>[.<attr>]`, `reboiler.<kind>[.<attr>]` (a `role: fixed` specification with target `parameters.<end>.<kind>…` lands there too), one function `column_unit.end_entries`. The note's revision *pins* need a `condenser.*`/`reboiler.*` target path in `revision_flowsheet._PATH_KINDS` and the routing in `_read` (track A's file), and `PinColumn` has no non-stream quantity (`revision_binding.py`); the column's parameters are also absent from `_PARAMETER_KINDS`, so only SI-unit-of-the-declared-kind is checked. Alternative: the paths as the note says (design lane + A/I1). Reversible by: rewriting `end_entries` to read `view.pins`.
DECISION: a column instance id must be a token (S01's `_token`: its property blocks are named after it) → refused at parse as `id_unsupported(<U>)` with a hint, not left to surface as `value_outside_model_domain`. Alternative: map ids to tokens (changes every row id). Reversible by: deleting the check.
DECISION: every side feed on `feed` shares one declared phase (the revision reader's R4 is one phase per port: `port_phase_ambiguous`) → recorded in L-COL-1. Alternative: one port per feed. Reversible by: n/a (reader rule).
DECISION: inlet ports `feed`/`top`/`bottom` declared `vapor_liquid`, or a `bottoms` not `liquid`, or a distillate neither → `port_unsupported(<U>.<port>)` as §4.7.1 says (the binder's idiom for one-phase ports is `port_phase_unsupported`). Alternative: the binder's idiom. Reversible by: renaming the code in `column_unit`.
DECISION: `column_binding` imports `ModelSignature`/`Configuration` from `revision_binding`; I1 registering it inside `revision_binding` must import it lazily (or at the module end) to avoid a cycle. Alternative: move the two types. Reversible by: n/a (I1's choice).
DECISION: where the recovery definition's row builder lives (`test_k02_unit_models` forbids a builder in a unit module) → `models/rows.py` `scaled_sum_definition_row`, a new function (no existing builder changed), though rows.py is not in track B's §5 list (track A does not touch it). Alternative: a design-lane amendment of the ownership table. Reversible by: reverting the B1 fix-up commit.
DECISION (B3a): the column's manifest declared its derivatives as `output: rows` w.r.t. stage fields, so T02's `eo_capability` read `undeclared` and `plan_or_refusal` refused the M1 region `CAPABILITY_UNAVAILABLE` (found by the spike, after §10.2 placed the stages) → `output: residuals`, `with_respect_to: [free_variables]`, `method: ad`, as every CasADi-differentiated unit declares (the heater, the valve). Alternative: `analytic`. Reversible by: editing `ColumnUnit.manifest`.
DECISION (B3a): `_opening_order(..., owners=None)` takes the owner map as an optional fourth argument, so `test_t05b_openings`' three-argument call (track-free file) is unchanged. Alternative: required, and edit that test. Reversible by: dropping the default.
DECISION (B3a): `ColumnUnit.staged` is a dataclass field with `repr=False` (the 7-stage maps would swamp every repr of the unit). Alternative: plain field. Reversible by: removing `field(repr=False)`.
DECISION (B3a, fact for I1/A91): the revision reader's `_ID` (`revision_flowsheet.py:83`, `^[A-Za-z0-9][A-Za-z0-9_-]*$`) refuses a dotted instance id at parse as `id_unsupported(<id>)`, although the schema admits one (F7). So no document can name an instance `C1.stage.<j>`: A91's revision is refused with exactly A91's code by the reader, before §10.2 step 9's check could run. A89 (3) therefore exercises (a″) with a staged unit whose key is `U-BOT`. Alternative: n/a. Reversible by: n/a.
DECISION (B3b): §10.5 says `_COLUMN`'s signature lists the twelve end names as optional parameters, but `ModelSignature` (`revision_binding.py`, track A/I1) has no optional-parameter field → `_COLUMN` keeps `required=(stage_count,)` and its comment names `column_unit.END_PARAMETERS`; the parser stays the one reader and refuser. Alternative: an `optional` field on `ModelSignature` (I1, if a served description should list them). Reversible by: adding the field at I1.
DECISION (B3b, consequence of R-824): a name now fixes its kind, so S02 §5 S2's "kind not taken at this end" and "kind not offered" items are unreachable from a document; `condenser_boilup_ratio` and `condenser_distillate_ratio` are `parameter_unsupported(<U>.<name>)` (B2's `S2-kind`/`S2-not-offered` cases re-coded; `structural_refusal` keeps the S2 check, now a backstop). Alternative: map a foreign kind to S2's code. Reversible by: a kind lookup in `end_entries`.
DECISION (B3c, escalated — Q8's premise): `s11-column-v1` is NOT registered. Facts: the application's registered revision policy `T06-revision-v2` already carries `T05b-phase-contract-v2` and `newton_refined`; it differs from `S01_DEFAULT_V1` only in `eo_recovery` (`homotopy_or_sequential_restart` vs `homotopy`), and edge 3's homotopy is unsupported on every revision region anyway (F8, L-COL-9). M1 and J2 solve under `T06_REVISION_V2` converged, products equal to the standalone root (Δ = 0). Registering a fifth `APPLICATION_POLICIES` entry would move the served `get_project.solve_policies` (pinned by `test_t07_w5a_inspection`, `test_t08_b50_surface_content`) and need `REGISTERED_POLICY_IDS`/`benchmarks/registry.yaml` (`test_t07_b3_policies`) — files outside track B, a served-surface change for no capability. The cases run under `T06_REVISION_V2` (the application's policy) and `S01_DEFAULT_V1` (the standalone policy object). Alternative: register as the note's default says (one commit in `application/policies.py` + registry + the two pinned tests). Reversible by: that commit.
DECISION (B3d): where A28's check sits → `executor._solve_revision_region`, after the specification-row refusal and before the warm start and the traversal: a region holding a unit whose model is in `STAGED_MODELS` under a policy whose `phase_contract` is not v2 ends `CAPABILITY_UNAVAILABLE`, message `phase_contract_unsupported(<model>)`, no attempt, no property call. (Without it, M1 under `T04-W12` "converged" in 0 iterations from the standalone root with v1's semantics.) Alternative: refuse in `plan_revision` (a `PlanRefusal`). Reversible by: moving the block.
DECISION (B3e): the committed cases name the column instance after the standalone unit (`S02`/`S06`), so its stage columns carry the standalone ids and A29 compares against the registered roots (`test_s02_column_wo2.ref_state`, `test_s06_column_wo2.expected_root`) directly; each file equals `s11_column_support.column_case(name)` (a test; regenerate with `python tests/s11_column_support.py`). Alternative: `UCOL` and an id map. Reversible by: `unit=` in `column_case`.
DECISION (B3e, Q29 fact): a column under `T08-ptc-v1` ends `PTC_MAPPING_INVALID` `ptc_mapping_invalid(<U>:stage:1:mole:A, missing)` before any attempt — a typed refusal, so §10.13's default holds: L-COL-10 at I1. Alternative: n/a. Reversible by: n/a.
DECISION (B3e, Q11 not done): a Wilson column with a `none` end cannot be bound on this branch (the Wilson basis is track A's A1, not merged into wp/S11-b), and no code path refuses `none` for a composition-dependent form (`column.validate` restricts kinds only). Carried to after A merges (with C-MW/C-EW of A29). Alternative: n/a. Reversible by: n/a.
DECISION (B3f, Q11 fact): `solve_column` accepts a Wilson column with a `none` end (C-MW's feed as the `top` liquid of a 10-stage stripper, C-MW's reboiler and `bottoms_rate` 0.6: CONVERGED, accepted), so Q11's default holds as "admitted": the flowsheet binds it and converges in 0 Newton iterations to the library root, |Δ| = 0 on all 145 columns, under `S01_DEFAULT_V1` and `T06_REVISION_V2`; committed as `benchmarks/s11/flowsheets/C-MW-stripper.json`. Alternative: refuse `none` on a composition-dependent form (no code path does; not needed). Reversible by: n/a.
DECISION (B3f): the Wilson A29 cases are checked against S10-C's registered root with its own per-variable tolerances (`test_s10c_columns.deviations`, plus the product streams against the same entries), and also against `solve_column`'s root exactly (|Δ| = 0 measured on 277 shared columns for each). Alternative: S02's flow/T/Q tolerances. Reversible by: `_worst_wilson`.
DECISION (B4, escalated — certificate policy): the Wilson column certificates (C-MW, C-EW, the Q11 stripper) are UNVERIFIED solely because `derivative_witness.{on,off}_pattern` is `unsupported`: the central-difference stencil steps an absent component's exactly-zero internal flow (R-785; e.g. `COL.stage.1.r.C2H5OH`) negative, which the Wilson provider refuses (`witness_stencil_invalid_trial_state`). Every other row passes (407 of 409 on C-MW/C-EW, 232 of 234 on the stripper). Only `pr-c1-v1`'s exactly-zero *stream* flows are exempt (`unstenciled`, R-281). Extending `unstenciled` to a column's exactly-zero stage flows on a γ–φ basis (with the `derivative_witness_partial` limitation) is a certificate-policy change, not made; `test_a35_the_wilson_column_rows_pass` pins the fact. Would need: a design-lane ruling (extend R-281's exemption, or a one-sided stencil at zero flows). A35 is therefore met on the SYN-001 cases and not on the Wilson ones. Alternative: n/a. Reversible by: n/a.
DECISION (B4): `specification.<U>.<end>` is judged in the table's linear form (reflux `r − R·d`, boil-up `v_N − B·l_N`, purity `n_c − π*·P`, recovery `n_c − ν*·F_c`, molar_flow; rates molar_flow; duty heat_rate; temperature), as the splitter's ratio row is, because the check policy has no dimensionless tolerance kind for §4.8's quotient form; a recovery with `F_c ≤ 0` fails outright (`recovery_feed_not_positive(<c>)`, A38). Alternative: the quotient with S06's `target_bound` as tolerance (registered constants, not the policy's). Reversible by: `verify.column._end_check`.
DECISION (B4): the column's duties enter `energy_balance.envelope` (`table.STAGED_DUTY_MODELS`, `verify.column.duty`: each end's `Q_j` at the state, then `Q_j*` from `stage_duty.<j>`) — without it the envelope failed by `Q₁ + Q_N` on every column case (M1: −11077 W). Alternative: `Σ_j state[stage_duty_id]`. Reversible by: the `elif` in `_envelope_energy`.
DECISION (B4): the stage items evaluate the *standalone* declaration (`declared_rows` without links) at the judged state, its pinned inlet columns `<U>.inlet.<name>.*` copied from the inlet streams, with each stage's regime read from the state's totals (never the solve's signature); each failure is attributed to the stage it names (`_stages_of`; an unattributable item raises `acceptance_item_unattributed`). The linked declaration references flowsheet stream columns its own `variable_ids` lack, so `row_values` cannot evaluate it alone. A `ZeroDivisionError` inside S06 §8 item 4 (F_c or P zero) makes the stage rows `unsupported(acceptance_undefined(...))`. Alternative: evaluate the linked declaration with the flowsheet's columns added. Reversible by: `verify.column.admissibility`.
DECISION (B4): `ModelChecks` gains `admissibility: Rule` (default nothing), its rows appended after the declared ports on all three forms (the Wilson form returns before the split checks). Alternative: the column's stage rows under `bounds`. Reversible by: the field and its three appends.
DECISION (B4, escalated — Q10 class): a column stage at `V = L = 0` with a dormant feed would need the column's own per-stage zero-flow form in `verify/zero_flow.py`, which may import nothing of the solver's (`test_t05_table_independence`); such a split now raises `zero_flow_form_unknown(syn001.column)` (unreachable at a converged column with a feed; S10 refuses a zero feed). Would need: the design lane's reading of the column's ZERO_FLOW form for the verifier. Alternative: pass the staged `ZeroFlowForm` in (breaks R-016's rule for that module). Reversible by: the check in `_reduction`.
DECISION (B4): the verifier reads the column's structure with `column_unit.column_structure` (the revision's one reader of a column instance) and its staged splits with `column_staged_splits` (§10.11), in `certificate._staged_splits`; the MODEL_CHECKS entry is I1's, the tests register it in `column_registered` (`column_checks()`). Alternative: n/a. Reversible by: n/a.

## WO-B1 inventory: structural and inlet-dependent items (§4.7.2)

Structural (checked at bind from `ColumnStructure`, B2; `validate` keeps its order and messages):
S02 §5 R1 (`stage_count`), R3's stage-pressure half (`P_j*` in the provider's `P` box), R4 (side-feed
stage in 1..N, one per stage), R6 (declared single phase: the parser's `port_unsupported`), S1 (kinds),
S2 (presence and kind of each end specification), S3 (distillate and bottoms rates together), S4 (a
direct kind's sign and finiteness), S6 (top/bottom inlet against the ends: by construction, the ends
are read from the wiring), S7 (no side feed at a slot stage), S8 (N holds the ends), S9 (pressure
monotone), S10-C D8 (γ–φ kinds: `specification_unsupported(<U>.<end>.<kind>)`), S06 §5 I1 (attribute),
I2 (value, finite and 0 < x < 1).
Inlet-dependent (left to `validate` at evaluate): R2 (inlet flows), R3's inlet `T`/`P` half, R5
(inlet admissibility), S5 (rate ≥ feed), S10 (no feed: zero total flow), I3 (absent component), I4
(temperature band: §4.7.2 lists it here), I5 (rank of the split rows, whose coefficients are the
`F_c`), I6 (product split), R7 (energy precheck).

## WO-B4 inventory: verifier consumers of `split.unit` (§4.8; `grep -n "split.unit\|instances\[" verify/`)

- `table.degeneracy` (`table.py:1548`): `instances[split.unit]` → `instances[owner.get(key, key)]`. A stage is
  heater-style (the column has no `vapor`/`liquid` ports); its `owned`/`enthalpy` entries sit under the stage key, which
  no flowsheet stream is, and its `distances`/`unresolved` keys are the stage key (read back by `_split_checks`).
- `zero_flow._reduction`/`zero_flow_splits` (`zero_flow.py:115,159`): owner lookup; a staged split refused
  (`zero_flow_form_unknown`, escalated above).
- `table._split_checks`, `pr_c1.split_checks`, `revision_phase_branch`, the `_band` label (`table.py:1236,1560,1792,
  1816`; `pr_c1.py:292`): ids only (`<key>.<key>`, `<key>:<key>`); no instance read. The column is not admitted on
  `pr-c1-v1`.

## Run log

- 2026-10-27 B1 `1fb0b8f9`: S08 PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL; S10C PASS n=858 changed=[]; S11 FAIL
  (C branch shard 4: `test_k02_unit_models::test_no_unit_module_defines_a_row_builder_of_its_own`; fixed in `884b4973`).
- 2026-10-27 B1 fix-up `884b4973`: S08 PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL; S10C PASS n=858 changed=[];
  S11 PASS n=54497 changed=[] (698 s for the three).
- 2026-10-27 B2 `ffc68146`: S08 PASS, S10C PASS; S11 FAIL (C branch shard 13: `test_t07_global_state::test_g20`, column_unit's `@cache`); fixed in `33a652a9` (hash uncached).
- 2026-10-27 B2 fix-up `33a652a9` (includes the docs commit `5fdee2d9`): S08 PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL; S10C PASS n=858 changed=[]; S11 PASS n=54497 changed=[] (949 s for the three).

- 2026-10-27 B3a `e41b986b`: tests (§10.12 grep set + `test_s11_*`, 68 files) 2153 passed; S08 PASS n=52 changed=[S02.P1]
  p1_stage_a=EQUAL; S10C PASS n=858 changed=[]; S11 PASS n=54497 changed=[] (703 s for the three).
- 2026-10-27 B3a acceptance 1 (the spike, M1 under `S01_DEFAULT_V1`): CONVERGED, 0 Newton iterations from the
  traversal start, products/T₁/T_N/Q₁/Q_N equal to `solve_column`'s root (|Δ| = 0). Same for M2–M4, J1–J8, P1; M1 and
  J2 also under `T06_REVISION_V2`. `signature_units` = `UCOL.stage.1…7`.
- 2026-10-27 B3d `63dc42a5`: tests (69 files) 2172 passed; S11 PASS n=54497 changed=[].
- 2026-10-27 B3e Q14 timings (bind + plan + execute vs `solve_column`, two orders, cold process each; gate 3×s + 2 s):
  M1 0.46/0.33 s, M2 0.34/0.23, M3 0.18/0.11, M4 0.22/0.14, J1 0.27/0.16, J2 0.25/0.14, J3 0.26/0.14, J4 0.27/0.15,
  J5 0.19/0.11, J6 0.39/0.27, J7 0.28/0.18, J8 0.35/0.24 (all 0 Newton iterations); M1-recycle 0.93/0.33 s, 3 Newton
  iterations (T06-revision-v2). Every case within its gate (worst 0.93 s against 2.96 s).

- 2026-10-27 B3e `655f24f8` (end of B3): tests (69 files) 2201 passed; S08 PASS n=52 changed=[S02.P1]
  p1_stage_a=EQUAL; S10C PASS n=858 changed=[]; S11 PASS n=54497 changed=[] (696 s for the three).
- 2026-10-27 B3f `0e3d6b77`: `test_s11_column_solve.py` 37 passed (tests/benchmarks only: no identity trigger).
  C-MW/C-EW worst |Δ|/tol 1.3e-7/2.1e-8 against S10-C's root, 0 Newton iterations, |Δ| = 0 against
  `solve_column` on 277 columns; the stripper |Δ| = 0 on 145 columns.
- 2026-10-27 B4 `9100ff11`: tests (52 files: every `verify_revision|revision_checks|degeneracy|zero_flow_splits|
  ModelChecks|MODEL_CHECKS` user and `test_s11_*`) 1588 passed / 6 skipped. S08 PASS n=52 changed=[S02.P1]
  p1_stage_a=EQUAL; S10C PASS n=858 changed=[]; S11 FAIL n=54497 changed=[] (C branch shards [1, 5, 14, 15]
  exited non-zero): rerun with `--keep`, exactly A3's eleven known failures (s05 a25, s07 a30, s10 a27, t08
  support-envelope a20 + six c3, T08.A32), nothing new (788 s for the three).

## Q9 spike (WO-B3's first step): STOPPED (resolved by §10, R-822; implemented in B3a) — the region decomposition does not place the stage pseudo-units

A29 on M1 alone (`feed_source → column → 2 product_sinks`, builder registered by monkeypatch, `S01_DEFAULT_V1`;
script `tests/s11_column_support.column_revision` + `plan_revision` + `execute_plan`). Trace:

1. `bind_revision_flowsheet` binds M1 square (`test_the_column_binds_square`); `plan_revision` then raises
   `ValueError: lifted_split_unregistered(syn001.column)` at `orchestrator/splits.check_agreement` (splits.py:470):
   the column's 7 × 3 `CAS-equilibrium` rows are `molar_flow_squared` and no descriptor names them. This is the
   staged-split plumbing §4.7.5 assigns to B3 (expected).
2. The plumbing would not suffice, and this is the Q9 answer. Every region map keys a split by `split.unit`, and
   the standalone solve's region has `units = signature_units = (S02.stage.1 … S02.stage.N)` (column_solve.py:416-
   423). A flowsheet region is built by `execution.build_region` (execution.py:404-437) from flowsheet instances:
   rows by `declaration.rows[row].unit` (the authoring instance, `UCOL`), columns by `graph.column_owner`, and
   `signature_units = _lifted_units(...)` = `(UCOL,)`. The region solve keeps only
   `active_splits = [split for split in splits if split.unit in set(region.units)]` (region.py:1876), so every stage
   split `UCOL.stage.j` would be dropped silently: the column's equilibrium rows would be solved with no phase
   policy, and the attempt signature would carry `UCOL` instead of its stages.
3. `check_agreement` also keys the `molar_flow_squared` rows by authoring instance (splits.py:463-466) and compares
   them to one descriptor's equilibrium rows (b); a column's squared rows are N stages' rows plus the purity and
   recovery definitions (`molar_flow_squared`, not equilibrium rows).

Placing the stages needs a rule for region membership of pseudo-units (`region.units`/`signature_units` gaining
`stage_unit(U, j)` for a column instance, or the filter at region.py:1876 resolving a pseudo-unit to its instance by
the `stage_unit` prefix) and for (a)/(b) of `check_agreement`. That is region structure, which the brief and the
note's Q9 reserve to the design lane; nothing was changed.

## Handoff (where track B stands, 2026-10-27, after B3f and B4)

- Done: B1, B2, B3a–B3e (see the run log), **B3f** `0e3d6b77` (A29 C-MW/C-EW, Q11 admitted: the stripper case),
  **B4** `9100ff11` (`verify/column.py`; `certificate._staged_splits` → `lifted_splits(staged=)`, `split_owners` →
  `degeneracy`/`zero_flow_splits`; `ModelChecks.admissibility`; the column's duties in the envelope).
- Passing: A29 on all fourteen cases + recycle (`test_s11_column_solve.py`, 39), A35 on M1–M4/J1–J8/recycle
  (VERIFIED), A36, A37, A38 (`test_s11_column_verifier.py`, 23).
- Not met: **A35 on C-MW/C-EW** (UNVERIFIED on the derivative witness alone; escalated above, certificate policy).
- Escalated for the batched ruling (with B3a–c's): the witness at absent-component zero flows (B4); the column's
  ZERO_FLOW form in `verify/zero_flow.py` (B4, Q10 class, unreachable today); the linear form of the specification
  rows (B4); the envelope's column duties (B4).
- For I1: `MODEL_CHECKS["syn001.column"] = s11_column_support.column_checks()`'s `ModelChecks` (material, energy,
  specification, `declared_ports=column.DECLARED_PORTS`, admissibility); `column_registered` also patches it today.
- Next action: I1 (not track B's). Track B's WOs are complete except the escalated items.


## WO-I1 (column registration)

DECISION (I1): where `_COLUMN` lives → defined in `revision_binding` beside the other signatures (from `column_unit.PORTS`/`STAGE_COUNT`); `MODEL_BUILDERS` holds `_syn001_column`, which imports `column_binding.build_column` at the call (cycle). Alternative: a mid-module import of `column_binding` (breaks when `column_binding` is imported first), or moving `ModelSignature`/`Configuration`. Reversible by: moving the four lines back.
DECISION (I1): `MODEL_BASES["syn001.column"]` reads `WILSON_BASIS.provider_id` (the Wilson registry row, §9), so D5's switch to v2 carries it. Alternative: the literal `wilson-ig-v1`. Reversible by: the literal.
DECISION (I1): `test_t07_w5c_signatures` on the column: its unit's ports are the signature's in order with the absent ends left out, and its optional parameters are `column_unit`'s grammar (`COLUMN_OPTIONAL`), since `ModelSignature` has no optional field (B3b, R-838). Alternative: `ColumnUnit.ports()` always all PORTS (would make an unwired `top` `port_unwired`). Reversible by: the two branches in the test.
DECISION (I1): the column's sample for the T07/T08 tables is the committed M1 and C-MW cases (`COLUMN_SAMPLES`); `EXPECTED` gains `S11:M1`, `S11:C-MW`, every other row unchanged. Alternative: a new corpus file. Reversible by: `COLUMN_SAMPLES`.
DECISION (I1): A89(3) now asserts the binder's §10.2 step 9 guard (`id_unsupported(U-BOT)` with the design's hint), then the planner's (a'') with the guard bypassed (`split_owners` patched). Alternative: drop the planner half. Reversible by: the test.
DECISION (I1, item 9 (b)): `column_unit.end_parameter(end, kind)` spells the missing-end hint (`condenser_purity.<component>`, `condenser_temperature.<stage>`); the `specification_unsupported` hint still lists bare kinds (not dotted; not required by the ruling). Reversible by: one line.

DECISION: R-561 vs §4.11 on S02's 12 U04 items → R-561 (reclassify in the registration commit). Alternative: append superseding entries. Reversible by: reverting that commit.
  (Orchestrator ruling on the I1 handoff's Q1.) R-561 is the specific ruling for exactly this binding; §4.11's "no earlier harvest entry is edited" is the general rule. Carried by its own commit (the one after `57db68d6`), not squashed into `713f5e3d`: D1-A03's tripwire is a check of the tree's state (bound id vs U04 items), not of commit membership, so a separate commit satisfies it. `to` drops U04 (L-COL-5 added to [2], L-COL-2/3 to [4], L-COL-2 to [5]); notes say "bound by S11 (U04 reclassified, R-561, R-810)"; `sha256` untouched. S03/S06/S08/S09/S10c items that name the column under U04 are not S02's and stay as harvested (§4.11).
