# S08b brief: two phase-contract follow-ups from S08 (design lane, `architect`)

Branch `wp/S08b`, worktree `.claude/worktrees/s08b`, from `main` `53228775`. Queue entry `docs/CLOUD_WORK.md` (S08b row);
Frank's defaults to S08 design Q3/Q4 (`docs/FRANK_QUESTIONS.md`). S10-C (`wp/S10C`, merging soon) adds a Wilson branch to
`region._admissible`; the build work orders will start after it merges, so design against that.

## 1. The question

Decide, in one design note with work orders and gates: (a) how to fix the phase contract's misreading of dotted column
stage ids as dormancy items, and what that moves; (b) whether and how flash units and S01 cascades reject near-trivial
("trace-vapour") TWO_PHASE results, as S08's S02 §8 item 6 now does for columns — without breaking registered cases that
legitimately sit on a saturation boundary.

## 2. Why the architect

(a) touches ADR 0005 D4's single decision function (restart selection), shared by every lifted solve; (b) adds an
acceptance rule on paths every flowsheet uses, where a registered case is known to be TWO_PHASE with a vapour fraction of
1.3e-17. Both can move registered attempt records.

## 3. Current state (recon digest, main `53228775`)

**(a) The defect** (`src/openflowsheet/orchestrator/phase_contract.py`):
- `:89 _is_item(unit)` returns `"." in unit` (docstring cites revision reader R1: unit ids never contain ".");
  `:95 _split(signature)` splits units from item keys; `:101 adjacent(frozen, other)` compares unit entries only, so it is
  False for any two column signatures; `:123 _changes(frozen, other, declared)` builds `unit:a->b` for units only, so it
  returns `""` for columns; `:242 WallObserver.choose(frozen)` takes the first adjacent candidate else `candidates[0]`
  (largest α, appended in halving order at `:221`); `:425 _proposal()` builds `phase_wall(patience, …)` (:441) and
  `phase_wall(stall, …)` (:453) via `_changes`.
- `region.py:1271 declared_phases` (from dormancy forms; empty for columns); `:1275 _signature` returns `(*lifted, *_items(...))`;
  `:1044 _items` yields `(form.item, "ZERO_FLOW")` for dormancy items only.
- Column ids: `models/syn001/column_solve.py:342 stage_unit()`; `cascade.py:323 f"{unit}.stage.{stage}"`.
- ADR 0005 (`docs/adr/0005-phase-attempt-contract.md`) `:27` adjacency definition, `:35` D4 restart point; `attempts.py:27-28`;
  register R-028 (`decision-register.md:973`), R-053 (`:1548`, v2 contract with ZERO_FLOW and items), R-065 (`:1787`),
  R-731 (`:14361`, the hand-on).
- S08's account: `docs/derivations/S08-design.md:107-113` (F5); review `docs/reviews/S08-review.md:181-182`: "The
  follow-up will re-baseline A06 and G1's P1 stage_a, because they pin phase_wall(stall, ) strings. It may also move
  Stage-A restart points, and with them whether Stage B triggers on a registered case."
- Tests that would move: `tests/test_s02_column_wo3.py:263-285` (P1 held branch: stage_a outcome/cause and attempt
  signatures), `tests/test_s08_reentry.py:207` (A06), `:85-95` (G1 digest includes `result.message`),
  `scripts/s08_identity.py:53-54,101` and `tests/test_s08_identity.py:42-70`. No test pins the literal `stall, )`.
  Guards that must not move (true dotted dormancy items): `tests/test_t05b_dormancy.py:959-963`,
  `tests/test_t05b_zero_flow.py:292-297`; non-column `phase_wall` literals with undotted ids
  (`tests/test_t03_contract.py:1133`, `tests/test_t05b_contract.py:646`, …).

**(b) The exposure:**
- Columns: `column_solve.py:188 TWO_PHASE_SATURATION_TOLERANCE = 1e-4`, `:553 saturation_errors`, `:568
  acceptance_failures` (item 6 at :629-634). S08 found a false CONVERGED on F1 (stage 4 two-phase on 5.6e-6 mol/s vapour,
  liquid 0.379 K subcooled). Bound from the review: |T − T_bub| ≲ 1.1e-5/(L·V) K, so item 6 is stricter than the row
  tolerances when L·V < ~0.1 (mol/s)² (R-735, a correct loosely converged low-flow root raises).
- Contract: `region.py:706 _admissible`, `:718-719` "if regime == TWO_PHASE: return True, 0.0" (docstring :169 "A
  TWO_PHASE branch is always admissible"); called at :1352 (converged) and :1632 (screen).
- Flash units: `models/syn001/ph_flash.py` (`PHFlash` :225) has no TWO_PHASE saturation check; `models/c1/flash.py:577`
  accepts any TWO_PHASE result with both outlets; `models/c1/phase.py:41-61` classifies by l_NH3/n_tot vs TAU_DEW = 1e-10.
  `tp_state.py:118 single_phase_admissible` is used on single-phase branches only.
- S01 cascades: `cascade_solve.py:450 acceptance_failures` checks V_j, L_j > 0 on TWO_PHASE (:470-474); no saturation check.
- **Registered near-boundary results that must stay accepted:** `models/syn001/mixer.py:30-36`: the SYN-001 recycle is
  the flash's own saturated liquid; Σ z_i K_i = 1.0000000000000002 in double, the provider classifies it TWO_PHASE with
  a vapour fraction of 1.3e-17 while the 20-digit reference registers LIQUID — admissibility is deliberately checked on
  the enthalpy, not the label. `models/c1/flash.py:333-347`: dew-band note, TWO_PHASE side at L/n_tot = 3.4e-5.
  Columns: the smallest L or V on a two-phase stage across 42 registered roots is 0.183 mol/s.
- S08 review Q4: "a correctness exposure, not only a scope choice … A cheap first step is F4's scan: saturation errors on
  every registered CONVERGED flash and cascade root."

## 4. Constraints and invariants

- Every registered case not named by the design stays bit-identical; prove it (G1-style digests against the merge base, as
  `scripts/s08_identity.py` and `scripts/s10c_identity.py` do), and name exactly which records move and why.
- ADR 0005 is Accepted: a change to D4 needs an ADR amendment. Frozen interfaces and schemas change only by ADR.
- Never relax a check to pass; a correct near-boundary root (the recycle) must not become a failure.

## 5. Decided, and open

Decided: S08b exists (Frank's default); S08's item 6 for columns stands (R-729, R-735).
Open: (a) the fix (an explicit item/unit distinction rather than the "." heuristic, or another), the ADR 0005 amendment
text if needed, the re-baselined records (P1 stage_a, A06, G1) and whether any registered Stage-A restart point or Stage-B
trigger moves (measure it); (b) start with the scan the review asks for (saturation errors on every registered CONVERGED
flash and cascade root) and decide from its numbers: no rule, a rule for cascades only, or a rule in `_admissible`, and how
it treats the recycle-type saturated stream; the work orders (~150k context each) with acceptance tests; whether (b) needs a
`specifier` pass for registered states.

## 6. Deliverable

`docs/derivations/S08b-design.md`; an ADR (amending ADR 0005, or new 0050) only if needed; register entries after the
last number on `main` at your start plus S10-C's block on `wp/S10C` (R-760…R-781): start at **R-790** and note the gap.
Scan scripts and their output under `docs/derivations/scripts/s08b_design/` (lint- and format-clean). A docs-only commit on
`wp/S08b` (include this brief). Do not push. Report in at most 25 lines, with any question for Frank and a default.

## 7. Out of scope

S10-C's providers in these paths (Wilson flash/column acceptance is S10-C's); new unit models; transient behaviour.
