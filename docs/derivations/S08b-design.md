# S08b — Two phase-contract follow-ups from S08: signature items by declaration; saturation consistency for S01 cascades (design note)

**Status:** Proposed, 2026-10-26, design lane (`architect`). Branch `wp/S08b`, cut from main `53228775`. Brief
`docs/briefs/S08b-contract-follow-ups.md`. Register **R-790 to R-794** (main ended at R-752; S10-C holds R-760 to R-781 on
`wp/S10C`; R-753 to R-759 and R-782 to R-789 are unused by design, so the two blocks cannot collide).
*Erratum (2026-10-26, build lane, S08b WO-4):* S10-C used R-782 to R-786 (merged at `8654aabc`), so the unused ids are
R-753 to R-759 and R-787 to R-789; no id collides (`docs/S08b_BUILD_DECISIONS.md` WO-0).
**Evidence:** `docs/derivations/scripts/s08b_design/` — a pytest probe (`s08b_probe.py`), a sharded suite driver, the 52
S08-configuration record comparison, the scan report, and their output in `measured.txt`. Measured on main `53228775` code
(CoolProp 8.0.0 is not installed on the workstation, so its 3 076 tests skipped). Probes only: not production code, generators
or tests.
**Normative here:** §5 (design), §7 (assertions), §8 (work orders), §9 (gates).
**What this amends:** S01 §8 gains a saturation item (S01 Amendment 2, §5.2 here). **No ADR is amended or added:** ADR 0005 D2/D4
and T05b spec §7.8 (i) already say what §5.1 implements; the code read them through a premise (`"."` marks an item) that S01's
stage ids made false. **No contract literal changes.** S10-C (`wp/S10C`) merges first; §8 WO-0 rebases onto it.

---

## 1. Problem and scope

**(a)** `phase_contract._is_item` decides that a signature entry is a dormancy-form item iff its key contains `"."`. Every S01
cascade and S02/S03/S06 column stage id contains `"."` (`S02.stage.4`). So, on every column and cascade solve:
`adjacent()` is `False` for any two signatures (all entries are "items", their key sets equal, no step is counted), ADR 0005 D4's
adjacent-candidate preference never applies, and `_changes()` returns `""`, giving `phase_wall(stall, )` against T03 §4.10's
grammar (S08 F5, R-731).

**(b)** On the lifted path a `TWO_PHASE` branch is always admissible (`region._admissible`). The division-free equilibrium row
`r_i = v_i L − K_i l_i V` gives `1 − Σ K_i x_i = Σ r_i /(L V)`: a state near the trivial manifold (`V → 0` or `L → 0`) meets every
row at any `T`. S08 closed this for columns with S02 §8 item 6 (R-729). Flash-type lifted splits and S01 cascades have no such
check.

**In scope:** (a)'s fix and what it moves; (b)'s decision for S01 cascades and for flash units, with its treatment of saturated
streams; the identity gate; work orders.
**Out of scope:** S10-C's providers in these paths (Wilson flash and column acceptance are S10-C's); a new contract literal;
new unit models; Stage-B-style re-entry for cascades; transient behaviour; the verifier.

## 2. Constraints and invariants

- **Bit-identity.** Every registered record not named in §6 stays bit-identical, proved by two-tree digests against the merge
  base (§9 G1). A record that moves and is not named stops the build lane.
- **ADR 0005 D1:** a rule set is named by its literal (`T03-phase-contract-v1`, `T05b-phase-contract-v2`); a replay under a policy
  without the literal is refused. A **rule change** needs a new literal (and an ADR widening the `solve-policy` enum). A
  **conformance fix** to the rule as written keeps the literal and names the records it moves.
- **ADR 0005 D2/D4, T05b spec §7.8 (i):** the signature is one regime per signature unit in plan order, followed by one item
  `[<U>.<port>, ZERO_FLOW]` per dormancy-form outlet whose zero-flow form the attempt runs. Adjacency: every unit equal or one
  lattice step apart, at least one different; an item's absence and presence are one step apart. Restart point: the largest-α
  candidate adjacent to the frozen signature, else the largest-α candidate.
- **Never relax a check; never invent an epsilon for a phase boundary.** A correct root on a saturation boundary (the SYN-001
  recycle, `mixer.py:30-36`: `Σ z K = 1.0000000000000002`, the provider says `TWO_PHASE` at `β = 1.3e-17`) must not become a
  failure.
- R0 strings carry no measured float (ADR 0005 D8 as amended).
- Interfaces in `docs/interfaces-frozen.md` and the schemas do not change. `phase_contract.adjacent` and `WallObserver.choose` are
  module API, not frozen interfaces.

## 3. Findings that decide the design (measured, `measured.txt`)

**F1. The probe is inert, and the item rule moves no test.** Whole suite, 12 shards, three runs: plain, `observe` (logging
only), `fix` (the §5.1 rule substituted inside `_proposal`): each `passed=12507 failed=0 skipped=3137`. No test pins a
`phase_wall` string on a stage signature.

**F2. Where the two rules disagree, only the change list differs.** 268 `_proposal` calls in 74 tests have an entry the two rules
classify differently. Every such key is a `.stage.` id; no undotted key is an item under the explicit rule, and no dotted key
outside `.stage.` ids disagrees (so no tear-path, T02–T05b or flowsheet record can move). 60 of the 268 consult the restart
selection; in **all 60 the chosen candidate is the same** (index 0, the largest α). Only the change list moves: 26 × `""` →
`S03.stage.7:VAPOR->TWO_PHASE`, 16 × → `S02.stage.7:VAPOR->TWO_PHASE`, 10 × → `S02.stage.5:LIQUID->TWO_PHASE`, 7 × →
`S02.stage.2:LIQUID->TWO_PHASE`, 1 × → `S02.stage.3:VAPOR->TWO_PHASE`.

**F3. On S08's 52 G1 configurations, 11 messages move and nothing else.** No G1 digest, no `stage_a` digest, no signature,
outcome, core outcome, iteration count, attempt reason or state hash moves; no Stage-A restart point and no Stage-B trigger moves.
The 11 moved strings are all `active_set_cycling(<signature>; phase_wall(stall, ))` (listed in §6.1).

**F4. Why restart points can still move in principle.** Old: `adjacent` is always `False` on stage signatures, so `choose`
returns `candidates[0]`. New: it returns the first adjacent candidate, which differs from `candidates[0]` only if `candidates[0]`
moves some stage two lattice steps (`LIQUID ↔ VAPOR`) while a smaller-α candidate is adjacent. No registered or tested solve
reaches that (F2: 0 of 60); it is D4 as written, and A4 (§7) exercises it at the function level.

**F5. S01 cascades: every accepted two-phase stage is saturated within 2.43e-6 K.** 123 accepted closures in the four S01 test
modules: largest `max(|T − T_bub(l)|, |T − T_dew(v)|)` **2.43e-6 K** (41× under item 6's 1e-4 K), smallest `L·V` 0.0135
(mol/s)², smallest `V` or `L` 0.0146 mol/s. Columns (S02/S03/S06) repeat S08's 2.42e-6 K; the only failures are S08's own
adversarial and F1 tests (0.379 K at `V = 5.6e-6`; 23.8 K at `V = 1.9e-11`).

**F6. Flash-type lifted splits (SYN-001): one test module produces near-trivial accepted roots, and item 6 would reject a correct
one.** 2 386 accepted `TWO_PHASE` flash-type splits in 483 tests. With minority fraction `min(V, L)/n ≥ 1e-3`: 2 376, largest
saturation error 1.01e-5 K. Below 1e-3: ten records, all in `test_t05b_candidate_answers.py` (B34 (a)'s sweep, `U-PHF2` fed a
saturated vapour at `Q = 0`):

| `L` (mol/s) | `T − T_bub(l)` | `T − T_dew(v)` | provider TP flash at `(n, T, P)` | what it is |
| --- | --- | --- | --- | --- |
| 1.0e-4, 9.8e-5 (×3 states) | +0.057…+0.059 K | +0.064…+0.067 K | `VAPOR` | B34's six registered false successes (verifier `FAILED`, `false_success_detected`) |
| 5.0e-8 | +9.5e-4 K | +3.3e-5 K | `VAPOR` | the dew point within 3.3e-5 K |
| 1.1e-16, 2.2e-16 | **−30.7 K, −23.8 K** | **0.0** | `TWO_PHASE`, `β = 1 − 1e-16` | the **correct** exact-dew-point root (B31 (b)) |

The last row is the recycle's hazard made concrete: the vapour sits exactly at its dew point, and the 1e-16 mol/s of liquid has a
composition the rows do not determine (`x_i = y_i/K_i + r_i/(K_i L V)`), so its bubble error is noise. **Item 6 transplanted to
flash-type splits would reject a correct root.**

**F7. A kernel-label rule would reject correct pure-component splits.** 147 accepted non-trivial flash-type roots (e.g. T06
A91d, K04-F9 SC-1/SC-2/SC-3) have saturation errors 0.0 while the provider's TP flash of the feed at `(T, P)` says `LIQUID`: a
pure component at `T_sat` has no TP-determined split.

**F8. Near-trivial `TWO_PHASE` provider answers are everywhere and legitimate.** 2 377 provider answers with minority fraction
below 1e-6 in 406 tests across 99 modules (K02's mixer: the recycle; T02 `SYN-001-nominal`, `β = 1.6e-19`; T06 A76: every product
of a two-phase flash re-flashed). Any rule keyed on a provider's `β` or label would hit them.

**F9. PR-C1 (`c1.tp_flash`) near-dew roots are correct with tiny `L`.** 903 accepted records; smallest `L` 5.5e-10 mol/s in M02
G7c ("K18 just past the band"), `L ∝ δ` across δ = 1e-8…1e-4: registered near-dew roots, certified `UNVERIFIED`. No saturation
temperature is defined for PR-C1's pure-NH3 liquid in `band_temperature`.

## 4. Decision

### 4.1 (a) Items are identified by declaration

**Decision.** A signature entry is an item **iff its key is a key of the attempt's `declared_phases`** (the region builds both
from the same dormancy forms; empty on the tear path and under v1). Every other entry is a signature unit, whatever its spelling.
`_is_item` and its `"."` premise are deleted. The literal does not change. The 11 messages of §6.1 are re-registered; nothing
else moves (F2, F3).

**Rejected alternatives.**
- *A new contract literal (v3) for the fix.* The rule text is unchanged; only its implementation was wrong. A literal bump would
  move every v2 record's policy and give no reader anything new to see.
- *Tag entries in `AttemptSignature` (unit vs item).* A schema change (`solve-event`, `attempt-context`) for information the
  region already holds.
- *Rename stage ids without `"."`.* Moves every column and cascade record and every id-keyed fixture.
- *A narrower heuristic (`"." in key and ".stage." not in key`).* It replaces one spelling rule with another; the next dotted id
  breaks it again.
- *Items as "everything after the lifted units" (position).* Equivalent today, but needs the unit count threaded into the
  contract; the key set is already there (`ops.declared_phases`, used by `_changes`).

### 4.2 (b) Saturation consistency for S01 cascades; no new rule in the contract

**Decision.**
1. **S01 cascades get S02 §8 item 6, unchanged:** every `TWO_PHASE` stage lies within `τ₆ = 1e-4 K` of its liquid's bubble and
   its vapour's dew temperature, by the same function as columns. A `CONVERGED` answer that fails it raises S01's existing
   `AcceptanceDefectError` (S01 §8: "an answer that fails is a defect, never a success"). F5: every registered S01 root passes
   with a 41× margin, so no registered record moves.
2. **No `TWO_PHASE` rule is added to `region._admissible`** under either accepted literal.
3. **Flash units keep their present acceptance.** Their exposure is not silent on any certified path: a revision run certifies
   every `CONVERGED` solve, and the verifier's independent split catches the false successes (B34's six are `FAILED` with
   `false_success_detected`; B34 (a) already stops the build lane on a `VERIFIED` inside that set). The causal flash evaluators
   (`PHFlash.evaluate`, `c1.tp_flash.evaluate`) take the provider's split, which is not division-free, and have no exposure.
4. **The recycle-type saturated stream is never judged by a new rule.** No rule reads a provider's phase label or `β`. S01's item
   reads stage temperatures against the band temperatures of the stage's own products, which are well determined on every
   registered S01 stage (F5).
5. **No `specifier` pass is needed.** No state or reference value is registered: `τ₆` and the function are R-729's, B2 (§7) is a
   regression margin, B1 a mutation test, and S01 Amendment 2 is a pointer to §5.2.

**Rejected alternatives, and why (with the numbers).**
- *No rule anywhere.* S01 cascades have neither item 6 nor a certificate: a near-trivial false `CONVERGED` would be returned
  silently. Rejected.
- *Item 6 in `_admissible` for every lifted split.* Rejects the correct exact-dew-point root (F6: bubble error −30.7 K on 1e-16
  mol/s of liquid); moves S08's F1 path (Stage A would restart instead of being item-6-rejected) and B34's tally; has no meaning
  for PR-C1 (F9).
- *Kernel-label agreement in `_admissible` (`TWO_PHASE` admissible iff the provider's TP flash at `(T, P)` says `TWO_PHASE`).*
  Rejects 147 correct pure-component splits (F7).
- *A minority-fraction threshold (`β < φ` is not two-phase).* An invented epsilon on a phase boundary; would hit the 2 377
  legitimate near-trivial provider answers (F8) and the C1 near-dew roots (F9).
- *Feed-band admissibility in `_admissible` (`T_bub(z) − τ₆ ≤ T ≤ T_dew(z) + τ₆` for the split's feed `z`).* Numerically the
  right rule: on the measured cases it accepts the exact-dew root (`T − T_dew(z) = 0`), the pure-component splits and the 5e-8
  near-dew root, and rejects exactly B34's six (+0.064…+0.067 K) and S08's F1 stage (−0.379 K). Rejected **for S08b** because it
  is a change of the rule set under both accepted literals (ADR 0005 D1 asks for a v3 literal and an enum-widening ADR), it moves
  registered records (B34 (a)'s tally; F1's S08 path), and what it closes is already detected on every certified path. Recorded
  as Q1 (§10) for Frank, with this rule as the recommended content if he queues it.
- *A Stage-B-style re-entry for cascades.* New machinery for a failure no registered cascade produces.

## 5. Design

### 5.1 (a) The contract (`orchestrator/phase_contract.py`, `orchestrator/region.py`)

- Delete `_is_item`.
- `_split(signature, items: AbstractSet[str]) -> tuple[AttemptSignature, frozenset[str]]`: unit entries are those whose key is
  not in `items`, in signature order; the item keys are those in `items`.
- `adjacent(frozen, other, *, items: AbstractSet[str]) -> bool`: **`items` keyword-only and required** (a forgotten argument
  must not silently turn items into units). Body unchanged apart from `_split(…, items)`. Docstring: an item is a key of `items`
  (T05b §7.8 (i)); every other entry is a signature unit (ADR 0005 D2), whatever its spelling; drop the R1 sentence.
- `_changes(frozen, other, declared)`: `items = frozenset(declared)`; otherwise unchanged (unit changes in signature order, then
  toggled items in declaration order, absent side named by the declared phase). The `"defect: … no declared phase"` raise becomes
  unreachable; delete it.
- `WallObserver.choose(self, frozen, *, items: AbstractSet[str]) -> Candidate | None`: the first candidate with
  `adjacent(frozen, c.signature, items=items)`, else `candidates[0]` (unchanged rule).
- `_proposal`: compute `items = frozenset(declared)` once, after `declared` is read; pass `items=items` at both `wall.choose`
  calls (patience, stall). Nothing else in `_proposal` or `decide` changes.
- `region.py`: a module-level `_units_and_items_disjoint(splits, dormancy) -> None` computes
  `clash = {s.unit for s in splits} & {form.item for form in dormancy}` and, if non-empty, raises
  `ValueError(f"defect: {sorted(clash)} are both lifted units and dormancy items")`; `_LiftedOps.__init__` calls it once its
  splits and forms are set. It pins the invariant the rule relies on; no registered region reaches it.
- The tear path (`attempts.py`) is unchanged: its ops has no `declared_phases`, so every entry is a unit, as before.

### 5.2 (b) S01 cascades (`models/syn001/cascade_solve.py`, `models/syn001/column_solve.py`)

- **Move, do not copy.** `TWO_PHASE_SATURATION_TOLERANCE: Final = 1e-4` and the body of `column_solve._saturation_pairs` move to
  `cascade_solve` as
  `saturation_pairs(unit: str, components: Sequence[str], provider, state, regimes: Mapping[int, Regime]) -> dict[int, tuple[float, float]]`
  (same body: `band_temperature` at `β = 0` on the liquid outlet and `β = 1` on the vapour outlet, `DECLARATION_CONTEXT`, `inf`
  for a non-`inside` position, a `BandError` or a phase with no positive flow). `column_solve` imports both names from
  `cascade_solve` (so `column_solve.TWO_PHASE_SATURATION_TOLERANCE` stays a module global that the column code reads and its tests
  may patch) and keeps `_saturation_pairs(spec, …)` as a one-line delegation. Column behaviour is bit-identical (G1 family A;
  S08's tests).
- **S01's acceptance.** `cascade_solve.acceptance_failures` gains, after the per-stage loop:

  ```
  # S08b §5.2 (S01 §8 as amended by Amendment 2): S02 §8 item 6's saturation consistency.
  pairs = saturation_pairs(unit, spec.components, provider, state, dict(enumerate(regimes, start=1)))
  for stage, errors in pairs.items():
      for side, error in zip(("bubble", "dew"), errors, strict=True):
          if not error <= TWO_PHASE_SATURATION_TOLERANCE:
              failures.append(f"{SATURATION_PREFIX}TWO_PHASE stage {stage}: {side} error {error!r} K")
  ```

  with `SATURATION_PREFIX: Final = "§8 saturation: "` (exported). `solve_cascade` is unchanged: a non-empty list raises
  `AcceptanceDefectError(failures)` as today. Its docstring and `acceptance_failures`' docstring name the new clause.
- **S01 spec, Amendment 2** (the build lane appends it as §18, verbatim): "*Amendment 2 (2026-10-26, design lane `architect`,
  S08b): pointer.* Normative text `docs/derivations/S08b-design.md` §5.2; register R-791. §8 gains a fifth clause: every
  `TWO_PHASE` stage lies within `1e-4 K` of its liquid's bubble temperature and its vapour's dew temperature (S02 §8 item 6's rule
  and function, `cascade_solve.saturation_pairs`); an answer that fails it is a defect, as §8. For a column, S02 §8 item 6 is this
  clause and is reported once, under S02's prefix. *Limitation:* on a two-phase stage with `L_j V_j` below about 0.1 (mol/s)² the
  clause is tighter than the row tolerances imply (R-735); every registered S01 root passes with a 41× margin (smallest `L_j V_j`
  0.0135 (mol/s)², largest error 2.43e-6 K), and a correct but loosely converged root there would raise."
- S02's spec is not edited: its §8 item 6 already states the rule.

### 5.3 What is deliberately not built

- No change to `region._admissible`, to `_branch_found`, to K03 §8.2, to `PHFlash`, `c1.tp_flash` or `tp_state`.
- No typed cascade outcome for a saturation failure (a frozen `SolveOutcome` change; R-735's reasoning).

## 6. Records that move (re-registration)

### 6.1 (a): the 11 `active_set_cycling` messages of S08's 52 configurations

Each is `active_set_cycling(<signature>; phase_wall(stall, ))` on the merge base and the same string with the change list filled
in on the branch. Path, then the change list:

| Configuration | Path | Change list |
| --- | --- | --- |
| `S02.P1` | `reentry.stage_a.recovered_from.message` | `S02.stage.2:LIQUID->TWO_PHASE` |
| `S02.M1` | `recovered_from.message` | `S02.stage.7:VAPOR->TWO_PHASE` |
| `S02.V-M2.distillate_rate+boilup_ratio` | `recovered_from.message` | `S02.stage.7:VAPOR->TWO_PHASE` |
| `S03.PC-L`, `S03.PC-LI`, `S03.PC-P`, `S03.RC1`, `S03.RC1-BR`, `S03.RC1-RR`, `S03.RC1-z`, `S03.RC7` | `recovered_from.message` | `S03.stage.7:VAPOR->TWO_PHASE` |

P1's held branch (S02 A12, S08 A06) is re-registered with its message:
`active_set_cycling(S02.stage.1:TWO_PHASE,S02.stage.2:TWO_PHASE,S02.stage.3:TWO_PHASE,S02.stage.4:TWO_PHASE,S02.stage.5:TWO_PHASE;
phase_wall(stall, S02.stage.2:LIQUID->TWO_PHASE))`. The S08 review expected A06 and G1's P1 `stage_a` to need re-baselining;
measured, neither pins the string and both digests are unchanged (F1, F3). WO-2 adds the pin.

Elsewhere in the suite, every `phase_wall(patience|stall, )` on a stage signature gains its change list, with the same restart
(F2); `attempt_opened` messages `phase_update(phase_wall(…))` on column and cascade restarts change the same way. No fixture
under `tests/fixtures/`, `benchmarks/` or `evidence/` contains an empty change list (grep at `53228775`).

### 6.2 (b): none

No registered S01, column or flash record moves (F5; §5.2 changes no column computation).

## 7. Assertions (acceptance tests; new module names are the build lane's)

- **A1** `adjacent` on dotted unit ids, `items=frozenset()`: `((S.stage.1, TWO_PHASE), (S.stage.2, LIQUID))` vs
  `((S.stage.1, TWO_PHASE), (S.stage.2, TWO_PHASE))` is adjacent; a `LIQUID → VAPOR` stage is not; identical signatures are not;
  different stage lists are not.
- **A2** `_changes` on those signatures with `declared = {}` is `S.stage.2:LIQUID->TWO_PHASE`; two changed stages are listed in
  signature order, `", "`-separated.
- **A3** A mixed signature, `items = {"U-PUMP.outlet"}`, `declared = {"U-PUMP.outlet": "LIQUID"}`:
  `((C.stage.1, TWO_PHASE), (U-PUMP.outlet, ZERO_FLOW))` vs `((C.stage.1, LIQUID),)` is adjacent, and `_changes` is
  `C.stage.1:TWO_PHASE->LIQUID, U-PUMP.outlet:ZERO_FLOW->LIQUID`.
- **A4** `WallObserver.choose` with two candidates on dotted ids, the first moving one stage `LIQUID → VAPOR`, the second
  adjacent: returns the second. (The old code returned the first; this is the behavioural guard of D4 for columns.)
- **A5** The T05b guards keep their values: `test_items_are_one_step_in_the_lattice` with `items={"U-PUMP.outlet"}` added to each
  call, `test_t05b_zero_flow.py:292-297` with `items=frozenset()` added; every asserted boolean and string unchanged;
  `test_t05b_dormancy.py:938-948`'s `_changes` strings unchanged.
- **A6** P1's held branch: S02 A12 and S08 A06 additionally assert `stage_a.recovered_from.message` equal to §6.1's string.
- **A7** `_units_and_items_disjoint` raises `ValueError` (message starts `defect:`) when a lifted unit id equals a dormancy
  item key, and returns `None` on every disjoint pair (a column's stage ids with a pump's `U-PUMP.outlet`).
- **B1** (wiring) With `cascade_solve.TWO_PHASE_SATURATION_TOLERANCE` patched to `-1.0`, `solve_cascade(C2)` raises
  `AcceptanceDefectError` whose failures are exactly six strings, `§8 saturation: TWO_PHASE stage j: bubble|dew error … K` for
  `j = 1, 2, 3`, and nothing else.
- **B2** (margin, regression) For C1–C5 as registered, `max_j max(saturation_pairs(…)[j]) ≤ 1e-5 K` (measured ≤ 2.43e-6 K
  over all S01 closures; the manifest records the C1–C5 value).
- **B3** (columns unchanged) `column_solve._saturation_pairs(spec, …) == cascade_solve.saturation_pairs(spec.unit_id,
  spec.components, …)` bitwise at F1's Stage-A state (0.379 K at stage 4) and at J8's root; S08's item-6 tests pass untouched.
  *Erratum (2026-10-26, design lane `reviewer`, S08b review):* 'S08's item-6 tests pass untouched' holds for every asserted
  value; one stub target moves — `tests/test_s08_item6.py::test_a_band_answer_other_than_inside_is_a_failure` patches
  `band_temperature` in `cascade_solve`, where §5.2's moved body resolves it (build decision WO3-1).

## 8. Work orders (build lane, about 150k context each, in order)

- **WO-0 — rebase and baseline.** Merge `main` (with S10-C) into `wp/S08b`. Record the merge base `B`. Re-run
  `docs/derivations/scripts/s08b_design/column_records.py` at `B`: it must print `moved=[] stage_a_moved=[]` and exactly §6.1's
  eleven differences. Anything else (for example S10-C cases with stage `phase_wall` strings) is a premise change: stop and
  report to the design lane with the output. *Acceptance:* the line and the eleven diffs, logged in
  `docs/S08b_BUILD_DECISIONS.md`.
- **WO-1 — the identity gate.** `scripts/s08b_identity.py` (+ its recorder plugin and `tests/test_s08b_identity.py` for the
  verdict logic, in the manner of `tests/test_s08_identity.py`), as §9 G1 specifies, with `MERGE_BASE = B` and a
  `--no-change` flag under which the expected differences are none. Run it on the unmodified branch with `--no-change`:
  `PASS a=52 a_texts=0 … b_moved=0` (the control that the gate sees two equal trees as equal); then, with §5.1 applied in a
  scratch commit, without the flag: `PASS a=52 a_texts=11 …`. *Acceptance:* both lines in the build-decisions log; the verdict
  tests (including a twelfth moved text, a moved candidate α and a non-`.stage.` change list, each `FAIL`) pass.
- **WO-2 — (a).** §5.1, A1–A7, the two guard edits (A5), the A12/A06 pins (A6). *Acceptance:* `ruff`, `mypy`, the touched
  tests, `scripts/s08b_identity.py` PASS (family A: the eleven named messages only; family B: no structural difference),
  `scripts/s08_identity.py` and `scripts/s10c_identity.py` still PASS.
- **WO-3 — (b).** §5.2 (the move, S01's clause, the prefix), B1–B3, S01 Amendment 2. *Acceptance:* S01, S02, S03, S06, S08 test
  modules pass; `scripts/s08b_identity.py` PASS unchanged from WO-2; B2's measured value logged.
- **WO-4 — evidence and records.** The full gate (`scripts/gate.sh`) once; `evidence/S08b/<commit>/manifest.json`
  (`status: tested` only if every A/B item and G1–G3 pass); `docs/progress.md`, `docs/CLOUD_WORK.md` (S08b row done),
  `docs/FRANK_QUESTIONS.md` (Q3/Q4 resolved by R-790/R-791; Q1 here added), R-731's "Watch for" answered by a dated line
  pointing at R-790. Then one `reviewer` pass (the package touches phase logic).

## 9. Verification gates

- **G1 — `scripts/s08b_identity.py`, two families, two trees** (merge base `B` in a detached worktree, and the branch; each
  subprocess imports only its own tree), one line, exit code 0/1:
  - *Family A, the 52 configurations* (`s08_identity.column_configurations()` + S01 C1–C5): S08's G1 digest
    (`column_fields`/`cascade_fields`, and `stage_a_fields` wherever `reentry` exists) must be equal for all 52; the **texts** —
    every `RegionResult.message` reachable from the answer (`result`, `recovered_from`, `presolve`, `reentry.stage_a.result`,
    `reentry.stage_a.recovered_from`, each candidate's `result` and `recovered_from`) and every attempt's `reason` — must be
    equal except exactly §6.1's eleven (configuration, path) pairs, where the base string contains `phase_wall(stall, )` and the
    branch string equals it with that substring replaced by `phase_wall(stall, <§6.1's list>)`.
  - *Family B, the decision log of the whole suite:* both trees run every `tests/test_*.py`, the shards dealt round-robin from
    the **base tree's** sorted file list (files that exist only on the branch run in one extra shard, so module-level caches warm
    in the same order in both trees), with a recorder
    that wraps `phase_contract.decide` and logs, per call, keyed by (test node id, call index within the test): `kind`,
    `outcome`, the conversion's `signature`, `source`, `fallbacks`, its trial `(iteration, halving, alpha.hex())` or `None`, the
    SHA-256 of its opening state (a `(state, regimes)` pair: sorted ids and `float.hex` values plus the regimes; a vector: its
    `float.hex` values), then `message` and `cause`. Over the keys both trees share: every structural field equal; `message` and
    `cause` equal except where the base string contains `phase_wall(stall, )` or `phase_wall(patience, )` and the branch string
    equals it with that empty list replaced by a non-empty list whose every entry is `<id>:<a>-><b>` with `.stage.` in `<id>`.
    The line reports the shared-key count, the count of such message moves, and the keys in one tree only (new or renamed tests;
    informational).
  - `S08B-IDENTITY PASS a=52 a_texts=11 b_keys=<N> b_moved=<M>`; any other difference is `FAIL` and names it.
- **G2 — the full gate** (`scripts/gate.sh`) passes once before merge, CI green on both architectures. CoolProp's tests skip on
  this workstation; CI or an environment with CoolProp 8.0.0 is where they run.
- **G3 — the scan, repeated on the branch:** `run_suite.py observe` + `scan_report.py` on the final commit (the probe skips M1
  when `_is_item` no longer exists, so M1 reports `records 0`): S1's S01 rows unchanged (largest error ≤ 2.5e-6 K), S1's
  flash-type rows identical to `measured.txt` (no flash behaviour changed), and the suite counts equal G2's.
  *Erratum (2026-10-26, reviewer):* `measured.txt` predates S10-C; on any later tree S10-C's tests add 46 kernel-agreeing
  flash-type splits to the `[0.001, 2)` bucket. 'Flash-type rows identical to `measured.txt`' reads: identical to the same scan
  of the merge base `B`, both trees dealt as G1 deals them (`s08b_identity.shards`); the three near-trivial buckets also equal
  `measured.txt`'s (build decisions WO4-2, WO4-3).

## 10. Risks and open questions (each with a default)

- **Q1 — Frank's preference: queue a contract v3 with feed-band `TWO_PHASE` admissibility for lifted splits?** It would turn the
  verifier-detected false successes of flash-type splits (B34's six) into restarts in the kernel's regime, at the cost of a new
  literal, an enum-widening ADR and re-registered B34 records. *Default: no, not now.* The exposure is detected on every
  certified path; revisit if a study or flowsheet needs `CONVERGED` + `VERIFIED` where it gets `FAILED`, or if an uncertified
  consumer of `solve_region` appears. If queued: §4.2's feed-band rule, `τ₆ = 1e-4 K`, the split's feed at its `(T, P)`, under
  `T05b-phase-contract-v3`, with a `specifier` pass for PR-C1 and γ–φ feeds.
- **Q2 — fact: CoolProp-backed lifted splits were not scanned** (not installed here). It cannot change §4.2's decision (no flash
  rule is added; CoolProp flowsheet runs are certified). *Default: proceed;* if an environment with CoolProp 8.0.0 is available,
  run G3 there once and log it.
- **Q3 — fact: S10-C's merged state may add stage signatures with `phase_wall` strings.** Family B's rule covers them by form;
  family A is pinned to §6.1. *Default:* WO-0's re-run decides; a twelfth difference stops the build lane for a design-lane
  ruling (it would be a list amendment, not a redesign).
- **Q4 — fact: does any replay bundle outside the repository hold a column restart message?** Only the message strings move, and
  no restart point moves on any measured solve. *Default:* none is registered; a replay of an old column bundle would refuse on
  the message, which is the honest outcome.
- **Q5 — scope (build lane's call within these bounds): ledger linkage of the manifest.** *Default:* `requirements: [D09, X31]`
  (D09: the restart rule; X31: invalid phases in column-family cases), `depends_on: [S08, S01]`, verdicts `null`; logged as a
  build decision.
  *Erratum (2026-10-26, reviewer):* the frozen manifest schema admits only `^[DA][0-9]{2}$`; the manifest carries
  `requirements: [D09]` and names X31 in a limitation; `depends_on` is not a manifest field (build decision WO4-1).
- **Risk — S01's clause raises on a correct, loosely converged, low-traffic stage** (R-735's limitation, now for cascades). Watch
  for an `AcceptanceDefectError` naming `§8 saturation:` on a stage with `L_j V_j < 0.1 (mol/s)²`; the response is a design-lane
  ruling, not a looser `τ₆`.
- **Risk — A4's behaviour (a restart point that moves) is reachable but unexercised.** If a future column case reaches it,
  family B of a later identity gate will show it as a structural difference; that is D4 working as written.

## 11. What this does not establish

- That every lifted flash-type `TWO_PHASE` root is saturated: the contract still accepts near-trivial roots there; the verifier,
  not the solver, rejects them.
- Anything about CoolProp-backed splits (not scanned), Wilson/γ–φ cascades (S10-C's) or PR-C1 saturation (no band temperature).
- That S01's clause can never reject a correct root (R-735).

## 12. Decisions

R-790 ((a): items by declaration; same literal; eleven messages re-registered), R-791 ((b): S01 gets item 6; failure is a
defect), R-792 (no `TWO_PHASE` rule in the contract under v1/v2; feed-band rule parked as Q1), R-793 (no rule reads a provider's
phase label or `β`: the saturated-stream rule), R-794 (the S08b identity gate's two families).
