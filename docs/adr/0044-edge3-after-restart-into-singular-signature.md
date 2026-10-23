# ADR 0044 — Recovery edge 3 after a restart that ends `LINEAR_SOLVE_FAILED`

**Status:** Accepted 2026-10-23 — all four conditions and Frank's are met (evidence below and C2); Frank, verbatim: "1: yes" (2026-10-23). Proposed 2026-10-22. **Review 2026-10-22 (S02 `reviewer`, R-550): stays Proposed.** It becomes Accepted when
(1) D1 is narrowed as below and A20 is extended (S02 spec §19 item 1); (2) S02's manifest is `tested`;
(3) `scripts/gate.sh` has passed on the merge candidate (a git checkout), CI is green on both architectures, and C2 records that run in
place of the git-less snapshot; and (4) a workstation scan of registered step records for `LINEAR_SOLVE_FAILED` with ≥ 2 attempts
is logged. The reviewer has read this ADR. Frank (Q-S02-3 follow-up, 2026-10-22) adds: every other unit's results unchanged,
bit-identical at the old configuration.
**Workstation evidence 2026-10-22 (WS1, git checkout of `wp/WS1` at `9384285`, main's code with D1 as narrowed).**
*(4) The scan.* Static: every tracked `.json`/`.jsonl` record holds `LINEAR_SOLVE_FAILED` as a value 9 times in 2 files
(`evidence/T02`, `evidence/T05b` manifests), 0 of them with an `attempts` list of ≥ 2. Dynamic: `eo_recovery_due` wrapped in
every Python process (a `sitecustomize` probe that logs each call whose outcome is `LINEAR_SOLVE_FAILED`) over the full default
suite (10,596 run) and the `nlp`/`pymrm` tiers (193 run): 83 such calls; ≥ 2 attempts in 56, due in 20 — all 20 in
`tests/test_s02_column_wo2.py` (3) and `tests/test_s02_column_wo2b.py` (17). Outside S02 the calls are `test_t04_edge3.py` (3;
0 or 1 attempts) and `test_t05b_dormancy.py` (1; 2 attempts, attempt 0 `CONVERGED`, not due); the `nlp`/`pymrm` tiers make none.
*Frank's condition.* The old configuration is ADR 0010 D3 (`LINEAR_SOLVE_FAILED` never a trigger), so the new path can move a
result only where the predicate returns `True` for it; outside S02 it never does, so every other unit's execution is the old
one. Counter-run with the probe returning the old predicate: the full suite differs from the D1 run in exactly 12 tests, all
S02 column tests (5 in `test_s02_column_wo2.py`, 7 in `wo2b`:
A06/A06b/A08/A09/A13/A14/A15 cases and A20); the other 10,583 pass in both (one further failure in both runs, M07a A50, is the ignored W27 archive copy in the
worktree). Registered records replayed under D1 at `0.3.0.dev0`: the five G10 records digest-only (other = 0) and REAL
`REPLAY PASS differences=0`. Conditions (1), (2) (`evidence/S02/1810dde…` `tested`), (4) and Frank's are met; (3) needs
the merge gate and CI recorded in C2 — done 2026-10-23 (C2).
**Date:** 2026-10-22
**Author:** design lane (`architect`), S02 Amendment 2
**Amends:** ADR 0010 D3 (the trigger set only). ADR 0005 D4 (the decision function) is **not** changed.
**Normative text:** `docs/derivations/S02-spec.md` §18.3; assertions S02.A20 (§18.6)
**Affected requirements:** D01 (the recovery edge the policy names); none other
**Affected packages:** S02 (first user), S01 (`cascade_solve`), T04 (`orchestrator/recovery.py`, `executor.py`'s edge 3)

## Context

ADR 0010 D3 runs edge 3 — one specification-continuation solve from the failed solve's item-0 opening, in its opening
signature — after a region solve ends in a globalization failure. It excludes `LINEAR_SOLVE_FAILED` ("rank"): continuation
cannot repair a rank-deficient system. It includes `ACTIVE_SET_CYCLING` and `ATTEMPTS_EXHAUSTED` because "on the lifted path
the contract converts globalization failures into restarts, so they surface as the contract's terminal outcome".

S02 measured a third surface of the same conversion. A full Newton step from a regular all-two-phase opening crosses a flow
bound; attempt 0 ends `BOUND_BLOCKED`; the contract reads a disappearance and restarts in a signature that is **structurally
singular for the model** — S02 §4.3's adjacent pairs (M1: `(L, L, 2P×5)`, rank 94 of 95) or §4.2's end stage under a rate or
ratio specification (M2: a bottoms-rate reboiler `VAPOR`, so `L_N` is pinned and the slot row has no column). The restart's
first factorization fails and the solve ends `LINEAR_SOLVE_FAILED`; edge 3 never runs. Forced, edge 3 reaches the registered
root on all ten S02 cases and variants (S02 §18.5). The terminal outcome is not even stable: one variant ends
`LINEAR_SOLVE_FAILED` or `ACTIVE_SET_CYCLING` depending on the last bits of its opening.

## Decision

**D1. Trigger.** ADR 0010 D3's trigger set gains: `LINEAR_SOLVE_FAILED` **when the failed region solve ran two or more
attempts** (its final attempt was opened by a contract restart). **Narrowed by review (R-550):** and the failed solve's attempt 0 ended in a core
globalization failure (`LINE_SEARCH_FAILED`, `STAGNATION`, `BOUND_BLOCKED`, `PTC_STALLED`, or `BUDGET_EXHAUSTED` of a core budget). A
restart after a `CONVERGED` attempt 0 is a physical correction. Item 0's signature is known wrong there, and D3's rank reason applies. `LINEAR_SOLVE_FAILED` ending attempt 0 stays excluded: that
is the signature the homotopy would run in, and D3's "rank" reason applies to it unchanged.

**D2. Everything else in D3 is unchanged:** `eo_recovery = "homotopy"` precondition, a continuation parameter required
(else `unsupported(no_continuation_parameter)`), count 1 per region step per solve, attempt 0 of the recovery at the failed
solve's item-0 opening in its opening signature, fresh contract state, dense `branch_provenance`, the recovery's outcome as
the step's outcome. A genuine phase change shows up as `HOMOTOPY_STALLED` (bracketed), as before (S02 P1 measures it).

**D3. Mechanism.** `orchestrator/recovery.py`: `eo_recovery_due(outcome, budget, *, attempts)` — `attempts` is the failed
`RegionResult`'s attempts' solver outcomes in order (`solver_outcomes(result.attempts)`), required and keyword-only (review
N1); D1's core failures are `EO_CORE_FAILURES`; the decision stays in that one function. Its three call sites pass it
(`executor.py` edge 3, `cascade_solve.solve_cascade`, `column_solve.solve_target`). No schema, record kind, outcome value,
policy field or identity changes; `solve-event`'s `eo_recovery` (`taken`/`unsupported`) already records the edge.

## Alternatives considered

- **Teach the phase contract S02's block rule** (`V^a 2P^b L^c`). Rejected: the measured restarts are mostly §4.2's end-stage
  singularity, which the block rule does not describe; and cascade structure inside ADR 0005 D4's single decision function is
  the model-specific screen R-533 already declined.
- **A generic numerical-rank screen on a proposed restart** (refuse to open it; end with the proposing attempt's outcome).
  Rejected: it rewrites the terminal outcome to one the solve did not end with and hides the singular attempt; it also adds a
  factorization to every restart. D1 keeps the honest terminal record and only widens when recovery runs.
- **`LINEAR_SOLVE_FAILED` as an unconditional trigger.** Rejected: in attempt 0 the homotopy's own corrector meets the same
  signature; a genuinely redundant specification (S02's X-DB, refused before evaluation) is D3's case.
- **An S02-local edge-3 decision** in `column_solve`. Rejected: D3's trigger is decided in one place for every region solve;
  a model-local trigger is a second decision function.
- **A target policy with `max_attempts = 1`** (so `BOUND_BLOCKED` surfaces as `ATTEMPTS_EXHAUSTED`). Rejected: it disables
  every legitimate phase change of the target and adds a policy object (T05b B06).

## Consequences

- C1. **Code:** `recovery.py` and three call sites (S02 WO-2b). No schema migration, no fixture regeneration.
- C2. **Re-registrations: none.** Measured: full suite (`pytest tests`, 10,159 run, 51 min) on a git-less snapshot of `7302536` with D1 patched in: every failure and error outside S01/S02 (85 failed, 155 errors: changelog, ledger, campaign and V17 record tests that need git or ignored artifacts) is identical on the unpatched snapshot; D1 moves exactly five tests — S02 A06 M1-from-`x⁰` (a strict xfail that now passes, intended) and four tests whose `eo_recovery_due` stub has the old two-argument signature (S02 A13 M1/M2, A15 M1; S01 `test_a17_forced_edge_3_from_the_presolve_root`), a mechanical stub update. WO-2b updates the four stubs to the three-argument signature
  (no expectation changes) and flips the xfail. Any registered outcome that moves later is listed here before acceptance,
  as ADR 0010 C3 did; none is relaxed.
  **Condition (3), 2026-10-23:** `scripts/gate.sh` PASS on the merge candidate, a git checkout of `main` at `05288372` (merge of
  `wp/WS1`): 10634 passed, 58 skipped (W27 archive absent), 0 failed; CI run 39862529869 on `05288372` green on `ubuntu-latest`
  and `ubuntu-24.04-arm` (and `identity`). This run replaces the git-less snapshot above; no registered outcome outside S01/S02
  moved (WS1 counter-run, Status).
- C3. **Register:** R-547.
- C4. **ADR 0010** gains a pointer to this ADR in its D3 when this ADR is accepted (build lane, documentation).

## Acceptance evidence

- S02.A20 (the predicate's table; M2's natural path recovering after `LINEAR_SOLVE_FAILED` with ≥ 2 attempts) and S02.A06/A07
  through `solve_column`; S02.A06b on M1 from the profile endpoint.
- T04's edge-3 suite and T03's contract suite unchanged and green; `scripts/gate.sh` green on both CI architectures.
