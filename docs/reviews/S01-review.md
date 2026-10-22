# S01 review (design lane, one `reviewer` pass) — `wp/S01` @ `2ed3c47` (code at `ea12548`)

Date 2026-10-22.

- **Subject:**
  - `src/openflowsheet/models/syn001/cascade.py` (WO-1) and `cascade_solve.py` (WO-2/3);
  - `tests/test_s01_cascade_wo{1,2,3}.py`;
  - the evidence manifest at `ea12548` (`implemented`, 20/26);
  - `docs/S01_DECISIONS.md`.
- **Authority:** `docs/derivations/S01-spec.md` §2–§10, ADR 0018 D2, ADR 0010 D3, T05b §7.8.
- **Rulings:** spec §17 (Amendment 1), register R-510 to R-518.
- **Review commits:** `b5dfc6b` (adversarial tests) and `5b6e8b8` (amendment and register).

**Verdict: fix first, then `tested`.** The numerics are sound:

- The §2 rows are exactly the spec's. Internal streams take the state of the stage they leave, and the closures
  telescope (A08).
- Thomas, the Kremser endpoint, the CMO totals and R7's bounds are right. R7's lower bound at `P_N` is the closure's
  exact minimum.
- The region descriptors and the regime pins and drops are right.
- Edge 3's identity is exact: `p⁰ = Q⁰` through the rebinding spy, dyadic λ, and λ = 1 equal to the target's
  `(model_version, constants_sha256)`.
- A20 holds across processes: C2, C3 and C4 give the same final hashes under `PYTHONHASHSEED` 1, 2 and 777.

The blockers are elsewhere:

- three registered tolerances asked for more than the registered solver promises (rulings 5–7);
- one admissibility definition is inconsistent with the region's (ruling 3);
- A18 never perturbs the target's start.

A mutation run (16 mutants) left 5 alive. They are now killed by `tests/test_s01_review_adversarial.py`, which passes
on the current code.

## Must fix

**MF1. §8 and R5 judge single-phase admissibility differently from the region, so a legitimate boundary state becomes a
defect or a refusal.**

- **Where:**
  - `cascade_solve.py:420-441` and `:471` test `Σ z K ≤ 1` exactly, with `z` taken from `m_j`;
  - `region._admissible` (`region.py:700-733`) accepts `≤ 1 + 1e-12` on the outlet `l_j` (or `v_j`);
  - R5 (`cascade.py:538`) is the same exact sum test on an inlet.
- **Failure 1, R5.** Probe E1: the C2 `top` inlet at the upper adjacent double of its bubble temperature,
  359.1106267639602 K (`Σ zK − 1 = 2.2e-16`). `validate` returns `inadmissible_inlet(top, LIQUID)`, while R-007
  admits it (1.8e-14 K). A saturated-liquid feed is the canonical column feed, and it is refused by rounding.
- **Failure 2, §8.** A `LIQUID` stage that converges within rounding of its bubble point passes the region's screen on
  `l_j`. On `m_j`, which equals `l_j` only to τ_flow, it can fail the exact test. `solve_cascade` then raises
  `AcceptanceDefectError` on a contract-accepted root (`:690`).
- **Correction:** ruling 3 (R-512). Use `tp_state.single_phase_admissible` for R5 (the inlet at its own state) and for
  §8 (the outlet `l_j` or `v_j` at `(T_j, P_j)`). That test also covers `Σ m = 0`, where the current code would
  divide by zero (`:438-441`).

**MF2. Three registered tolerances are tighter than the solver's registered promise. Four strict xfails hold A04, A05,
A06 and A10 at `implemented`.**

- **State tolerance.** The flow floor of 1e-9 mol/s (`test_s01_cascade_wo2.py:58`) lies below `newton_refined`'s
  `τ_flow = 3.1e-8` (ADR 0018 D2). C4's pre-solve passes at 0.454 only because Newton happened to overshoot the
  promise.
- **A05.** 1e-7 K and rel 1e-8 (`:246-255`) lie below `τ_T = 1e-6 K`. Measured: 9.77e-7 K.
- **A10.** The step rule `h = 1e-6·max(1, |x|)` (`:373`) makes the `Q_j` columns' scaled step 1e-10. The 3.39e-8
  floor is rounding in the difference quotient, not a Jacobian error.
- **Correction:** rulings 5–7 (R-514, R-515, R-516), with the derivations in spec §17.5–§17.7. The flow floor becomes
  10·τ_flow, A05 becomes 10·τ_T and 10·τ_flow, and A10's step becomes `1e-6·max(D_x, |x|)` with the tolerance
  unchanged and the floor ≤ 1e-8. The four xfails must then pass.

## Should fix

**SF1. A18 never perturbs the target's path.**

- **Where:** `test_s01_cascade_wo3.py:204-224`. Every opening perturbs `x_K` only. The pre-solve has one root for a
  given `T̄`, so `x⁰` comes back unchanged.
- **Measured (probe E2):** `x⁰` lies within 3.7e-9 (T ± 10 K) and 1.4e-15 (flows) of A06's pre-solve root, scaled.
  The target takes the same 3 iterations each time.
- **What A18 actually tests:** the pre-solve's basin only. §14's "no claim beyond A18's four perturbations" overstated
  that.
- **Correction:** ruling 8 (R-517). "`T̄ ± 10 K`" shifts the pre-solve level.
- **Measured under that reading:** both shifts give a new `x⁰`, 4 target iterations, and the same root (4.5e-10).

**SF2. The §4.6 closed form and `solve_region` judge the same swapped energy row by different rules.**

- **Where:** `cascade.py:1209` uses `value != 0.0`; `region.py:2401` uses `|value| ≤ τ_heat`.
- **Failure scenario.** All inlets dormant and `Q* = (0, 5e-4, 0)` W: the closed form returns
  `SPECIFICATION_CONFLICT`. If a stage of a partly dormant cascade reaches `ZERO_FLOW` with the same 5e-4 W, the
  region path returns `CONVERGED`.
- **Correction:** ruling 9 (R-518). Use the kind tolerance. D1 and D2 are unchanged. *Needs a decision:* I chose
  consistency with T05b §7.8 (iv) 2 over exactness.

**SF3. Five mutants survived the WO suites. Resolved in `b5dfc6b`; the build lane keeps these tests.**

| Mutant | What the suites never drove to its failing side |
| --- | --- |
| §8 admissibility check removed (`cascade_solve.py:471`) | no single-phase stage that fails admissibility |
| `AcceptanceDefectError` raise removed (`:690`) | no `CONVERGED` answer that fails §8 |
| §8 label rows dropped | no `ZERO_FLOW` stage whose label row fails |
| §7.1's dormant route removed from `solve_cascade` (`:637`) | D1/D2 tested only through `dormant_answer`; the route raises in the initializer |
| R7's bound taken at `P_1` (`cascade.py`, `energy_precheck`) | bounds tested only on C1, where `N = 1` |

- **Still alive:** the R5 `≤`/`<` boundary mutant. Ruling 3 makes it moot.

## Notes

- **N1. The pre-solve as built.** TP closure, `x_K` projected, the screen picks the signature, and the cause token
  `not_two_phase`. This deviates from §7.3's literal text but is a logged build decision, and DECISION 2 still holds.
  Confirmed in §17.10.
- **N2. The pre-solve start is recorded wrongly when `opening=` is given.** `initial_sha256` (`cascade_solve.py:646`)
  hashes `x_K`, not the state the pre-solve opened from (A18). Record the actual opening's hash (§7.7).
- **N3. One outcome, two return types.** `INITIALIZATION_FAILED` comes back as a `CascadeFailure` from the
  initializer (`tbar_outside_domain`) and as a `CascadeSolution` from the pre-solve. Callers must check both. Ruling 1
  leaves this to the binding.
- **N4. Edge 3 cannot reach single-phase targets.** It keeps item 0's all-2P signature (ADR 0010 D3), so it cannot
  recover a target whose root is single-phase (C4-like). This is not claimed, and is recorded for S02.
- **N5. A06's citation is coupled to the pre-solve margins.** `test_a04_a06_…` holds A06 to C4/C5's pre-solve margins.
  This is harmless after ruling 5; split the citation if the test is touched.
- **N6. A18's verdict is about its starts, not its tolerance.** With the 3.1e-7 floor, A18's `SAME` verdict is still
  scale-based (`roots.same_root`) and unaffected.

## Rulings on the batched questions (spec §17, register)

| # | Question | Ruling | Spec right / code right / value wrong |
| --- | --- | --- | --- |
| 1 | Refusal outcome vs `SolveOutcome` (R-510) | `INVALID_SPECIFICATION` is a validation category. It is never a `SolveOutcome`. Bindings map it to their invalid-request error. | Code right; spec clarified |
| 2 | R7 with every inlet dormant (R-511) | R7 applies only when `F > 0`. All-dormant goes to §4.6. | Code right; spec order amended |
| 3 | R5 vs code R-007 (R-512) | R-007 (`single_phase_admissible`) for R5 and §8 (outlet). The sum test is struck. | Spec's citation right, its gloss wrong; code to change (MF1) |
| 4 | Phase of `top`/`bottom` (R-513) | Either phase. No refusal. Label stays `T_top`. | Code right; §1 amended |
| 5 | A04/A06 10× margin (R-514) | The flow floor of 1e-9 was wrong. It becomes `10·τ_flow = 3.1e-7 mol/s`. | Registered value wrong (ADR 0018 D2) |
| 6 | A05, 9.77e-7 K vs 1e-7 (R-515) | 1e-5 K and 3.1e-7 mol/s (10·τ_kind). | Registered value wrong |
| 7 | A10 floor 3.4e-8 (R-516) | Step `1e-6·max(D_x, abs(x))`. Tolerance 1e-6 kept. Floor ≤ 1e-8. | Step rule wrong (rounding derivation) |

## Work order WO-4 (build lane, `opus-engineer`: touches phase logic; about 60k context)

Before `tested`, on `wp/S01`:

1. **R-514, R-515.** In `test_s01_cascade_wo2.py`:
   - set `FLOW_ABS = 10 * FLOW_TOLERANCE` (import it; no literal);
   - set A05 to T 1e-5 K and flows abs `10 * FLOW_TOLERANCE`;
   - remove `MARGIN_SHORT` and the A05 xfail. These tests must pass, and the margin test stays at ≤ 0.1.
2. **R-516.** In `_fd_errors`, set `h = 1e-6 * max(D_x, |x|)`. Remove the floor xfail. Assert the floor ≤ 1e-8 at
   `x_K` and at C2's root. Replace `test_a10_where_the_c2_root_floor_sits` with the measured floor under the new rule.
3. **R-512.**
   - R5 in `validate`: `tp_state.single_phase_admissible` on the inlet `(n, T, P)` in its declared phase.
   - §8 in `acceptance_failures`: the same test on `l_j` (LIQUID) or `v_j` (VAPOR) at `(T_j, P_j)`.
   - Tests: E1's saturated `top` at the upper adjacent double of its bubble T passes §5. R5-liquid and R5-vapour are
     still refused. The review's §8 test still passes.
4. **R-518.** `dormant_answer` reports a conflict only when `|swapped| > KIND_TOLERANCE["heat_rate"]`. Tests:
   `Q* = (0, 5e-4, 0)` gives `CONVERGED`, and `(0, 2e-3, 0)` gives `zero_flow_conflict(<U>:stage:2:energy)`.
5. **R-517.** Add a `tbar=` hook or keyword. A18 adds two openings at the pre-solve's `T̄ ± 10 K`, asserting that `x⁰`
   differs from A06's pre-solve root by more than 1 K in T and that the root is `SAME`.
6. **N2.** Record the hash of the actual opening (`opening_sha256`, or `initial_sha256` when no opening is given).
7. **Evidence.**
   - Log each change in `docs/S01_DECISIONS.md`.
   - Rerun `scripts/s01_evidence_manifest.py` (all A01–A20 must pass), ruff and mypy.
   - Run `scripts/gate.sh` before the merge.
   - `reviewed` is not set by any agent.

**Not examined.**

- The generator's internals: I relied on its `--check` as recorded at `ea12548` and did not rerun it.
- `solve_region` beyond `_admissible` and the zero-flow conflict check.
- The contents of A20's record comparison.
- The manifest generator beyond its citation regex and status rule.
