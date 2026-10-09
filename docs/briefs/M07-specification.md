# Brief — M07 specification: the real reference journey and the v0.2 gate

**To:** `specifier` (design lane). **From:** the session (build lane), 2026-10-09. **Branch:** `wp/M07` from `main`
(worktree `.claude/worktrees/m07`). **Plan row (v1.2 §4.4 l.269, binding):** *M07 — M05, M06: real reference journey and
v0.2 gate. Acceptance: before/after design decisions, costs, uncertainty and truth checks; W21–W27; reproducible report
and artifacts.* Lane: Design / Build. Gates: **W25** (owned), and the v0.2 release gate over W21–W27.

**Read first:** `docs/briefs/M07-recon-digest.md` (every anchor and excerpt you need: plan, blueprint §2.3/§14.4, the
v0.1 and alpha gates, what M02/M04/M05/M06/M03 deliver, the dossier, numbering). Read sources only narrowly (sed -n,
grep -n) where the digest points.

## 1. The question
Write M07's authority documents so that the build lane can (a) run the C1 ammonia-loop journey end to end — the same
reactor-inlet-temperature decision taken at increasing reactor fidelity (simple/equilibrium-type model → PyMRM v3 via M02 →
M04 surrogate where promoted → M05 trust-region refinement with parent checks) — and record before/after decisions,
constraints, discrepancy, uncertainty, truth checks and compute cost as a reproducible report with artifacts; (b) add
`v0.2-gate-v1` (claim set, verdict document, RC record, RC steps) beside `v0.2-alpha-gate-v1` in `scripts/v0_2_gate.py`
(wp/V02-alpha-gate), re-judging every claimed gate at its own candidate; (c) carry M06 WO-17 (W27 canaries + 45-run campaign
on the v0.2 candidate) into the candidate procedure; and so that a `verdict` agent can later judge W25 and the release from
the evidence alone.

## 2. Why the design lane
W25's meaning ("end-to-end real reactor refinement with honest evidence limits"), what counts as a measured effect of
fidelity on the decision (blueprint §2.3), which truth checks and uncertainty statements are admissible, and the release
claim set are scientific semantics and verdict criteria — no test would catch a wrong choice.

## 3. Settled — do not reopen
- Chemistry C1 (ADR 0022), K_NH₃ (R-152), zero-ΔP loop convention (ADR 0022 D2); the dossier's loop topology.
- Reactor v3 domain (R-315, V5): T_in [653.15, 693.15] K, P [9, 11] MPa, H₂/N₂ [2.5, 3.5], inerts [0.035, 0.2], per-tube
  flow [0.5, 2] × F_nom; refused outside. M02 is merged and `tested`; external subprocess, not a sandbox, Linux-only, R3.
- M05's study design (ADRs 0038–0040, rulings §16–§17, R-296…R-300), REAL decision box [653.15, 693.15] K (R-313/R-315),
  objective max liquid NH₃ at purge 0.02 (N-F1 default), budgets (D13). M05 claims no global optimality and not W25.
- M04: surrogate used only if PROMOTABLE (N-F5); a promoted surrogate never claims coverage at an operating point without a
  parent `targeted_check`.
- Alpha gate (ADR 0028, Proposed) and its registry pattern; the v0.2-gate script judges nothing and only reads verdicts.
- W27 registration (M06) and Frank's approval of the 45-run spend; the sampling seed is fixed.
- Plan §5.1: BLOCKED never counts as pass; insufficient evidence or exhausted budget is an honest outcome (blueprint §14.4).
- No validation claim: the dossier §12 lists what is not established; self-generated outputs are regression fixtures.

## 4. Open — decide these
1. The journey's rungs: exactly which reactor models (the "simple" rung: which existing model — check the C1 stand-in and
   M01's records), at which loop configuration (`benchmarks/m02/c1-loop-real.json` as the base?), and what is compared at
   each rung (T_in*, liquid NH₃, conversion, duties, compute cost).
2. W25's criteria: what "the decision changed/did not change because of fidelity" must show to be met, how discrepancy and
   uncertainty are reported (M05's noise floor/δ_T, M04's UQ), truth checks (parent evaluations at each decision), and the
   honest-outcome rules (budget exhausted, surrogate not promotable, bound-active decision at 653.15 K).
3. The release claim set of `v0.2-gate-v1` (W21–W27 + V11–V20 re-judged), how W24 is judged if M03 stays BLOCKED on Frank's
   N1, and what the release notes must state (R3, Linux-only, not a sandbox, the narrowed domain).
4. The report artifact: format, location, reproducibility class, replay of the journey; whether M07 needs a job operation
   (M05 N-F7 deferred it to M07).
5. W27 at M07: the candidate's coverage re-run, the order (canaries, sample draw, 45 runs), what WO-17 needs (binder reading,
   id rows, U14 rewrite, §20 read), and how the result enters the gate.
6. Compute: the expected real-reactor cost of the journey (a real evaluation is 25–45 s, up to 150 s under load; a loop
   solve ≈ 150 s) and a budget with a stop rule. Anything costing money (W27 runs) stays within Frank's approval.
7. S01 and R03 rows: state explicitly whether they are out of v0.2 (R03 is conditional).
Questions only Frank can answer go to a "Needs Frank" section, each with a default that lets work proceed.

## 5. Verification
Numbered falsifiable assertions with registered values/tolerances where numbers exist; the gate script's tests in the
pattern of tests/test_m07a_v0_2_gate.py; which assertions are default-gate vs opt-in (real reactor, W27 runs).

## 6. Deliverable
On `wp/M07`: `docs/derivations/M07-spec.md` (journey, W25 criteria, gate, work orders with lanes and dependencies, assertion
catalogue, Needs Frank, what M07 does not establish); ADR 0041 (and more if needed; 0029 is unused); register entries
starting at R-319 (check main and every wp/* branch first). Commit with named paths; do not push. No production code.

## 7. Out of scope
Re-deciding any settled item above; implementing anything; running the reactor; the alpha-gate WOs (separate branch).

Report ≤ 300 words: the decisions in one line each, the work-order list, Needs Frank with defaults, commit.
