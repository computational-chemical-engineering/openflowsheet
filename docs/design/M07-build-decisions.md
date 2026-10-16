# M07 build-lane decisions log (WO-1..)

Each entry: the choice, the alternative, how to reverse it. `[design]` marks a question for the design lane's ruling
round (batched into the M07 `reviewer` pass); `[coverage]` is the build lane's coverage read of `docs/derivations/M07-spec.md`.
None of these changes numerics, identity or a frozen interface.

J1 [design] M05 is not on main (it is on `wp/M05`). The journey imports M05 lazily: R1's e_k and P3 constraint values come
from M05's own `C1Parent.solve` + `checks.noise_floor` at the grid decision (store hits only; its J must equal the grid
solve's J bit for bit, else e_k is refused); without M05 in the tree e_k and constraints are null with the limitation
`R1:noise_floor_unavailable` (spec §14 Q2 default). R3 without M05 (or without a record, or without
`schemas/trust-region-study.schema.json`) is `UNSUPPORTED(m05_study_unavailable)`. Exercised against `origin/wp/M05`
@ dec989e source (stand-in loop, dry run): nine points verified, J re-solve bitwise equal, e_k = 0.0 (the stand-in's
coupling residuals are exactly 0), 89 constraint values per point. Not in the default gate until M05 merges.

J2 [coverage] `run_sha256` is the bundle's `artifact_r0_sha256` (RunManifest), not the sha256 of `manifest.json`, whose
bytes carry `started_at`/`elapsed_seconds` and so could never be reproduced by `replay`. Alternative: manifest file hash.

J3 [design] The spec does not say what a missing noise floor does to FE and TC-1. Built: a pair whose e_before or e_after
is null is `FE_NOT_DETERMINED` (missing `e_before`/`e_after` named); TC-1 is `TC1_NOT_APPLICABLE` when the candidate has
no verified parent value or no e*, or when the best grid point has no e_B (its T still recorded). Alternative: a separate
label. Reversible: `pair()`/`tc1()` in `scripts/m07_journey.py`.

J4 [coverage] "Checks its budget before each evaluation; a rung that would exceed it stops" needs an estimate of the next
evaluation's cost, which the spec does not give. Built: the largest cost seen so far in the rung (cold reactor experiments
and wall), and before the first evaluation R1 assumes M02 G12's 4 experiments per loop (registration
`g12_facts.experiments_per_loop`), every other rung 0. An evaluation that still overruns (actual > estimate) stops the rung
`BUDGET_EXHAUSTED` with the overrun visible in `budget.spent`; `check` accepts an overrun only under that label.
Unevaluated grid points are recorded `NOT_EVALUATED(budget)`, so a rung always has nine entries (W25 (a)).

J5 [design] R2 under a `PROMOTABLE` verdict needs a surrogate-backed loop; none exists (no case file pins
`c1.reactor_surrogate`). Built: an injected evaluator (tested with a mock: nine calls, A15); without one R2 is
`UNSUPPORTED(surrogate_loop_unavailable)`, a reason NOT in the registration's `unsupported_reasons`. Today's verdict is
NOT_PROMOTABLE so the path is dormant. Needs: register the reason, or rule that PROMOTABLE without a loop is an error.

J6 [design] Budget R0 = 0 cold reactor experiments, yet every stand-in loop solve runs 2–4 in-process experiments. Built:
only executions of an out-of-process unit (coupling record `frozen.<unit>.fingerprint.kind != "in_process"`) are charged
to the budget's cold count; every execution is still recorded per grid point (`experiments.cold`, `store_hit`, the store
attribution of W25 (g)). Alternative: charge all and raise R0's budget.

J7 [coverage] §6.1 fixes record names, not state names. X_pass = (n_N2,S3 − n_N2,S4)/n_N2,S3 from the certified state
(equal to ξ/n_N2,in by the reactor's N balance); Q_preheater_W = `preheater.Q`, Q_flash_W = `flash.Q`, n_recycle =
Σ S8 flows (fsum), n_purge_NH3 = `S7.n.NH3`, J = `S6.n.NH3`; `extrapolated` counts experiments in the coupling record whose
envelope `domain_status` is `extrapolated` (all iterations, not only the final one).

J8 [design] R3 consumes a record passed as `--m05-record`; the spec names no path for M05's REAL record and M05's
re-run entry point is not on `wp/M05` yet, so "otherwise re-run M05's study at J" is WO-4's. M05 has no record checker
yet (A21 "validates with M05's checker"): built as JSON-schema validation against `schemas/trust-region-study.schema.json`.
R3's spent budget is copied as `accounting.totals.trf_cold + parent_executions` and `accounting.budgets.wall_s` (field
names as on `wp/M05` @ dec989e; WO-4 must confirm against the real record).

J9 [coverage, design] W25 (c) asks for "the parent's certified state with M05 P3's inequalities evaluated (values and
margins)" for R3's decision, but M05's record (`CandidateCheck.as_document` → `ParentSolve.as_document`) carries only the
P3 summary {n, violated, worst_scaled_violation}, not the values. Built: R3's `constraints` is that P3 summary. To get the
values, WO-4 must re-solve T* with `C1Parent.solve` (store hits, no cold cost) or M05 must add them to its record — a
design choice (M05 record schema vs. a journey re-solve).

J10 [coverage] No test can catch A00 failing today except the new `test_a00_the_generator_check_passes` (A00 is D-gated but
no work order names it); added to WO-1's test module.

J11 [coverage] "R3 candidate status `PARENT_LOCAL_EVIDENCE` and TC-1 holds" (§4.4.7): when the candidate is
`PARENT_LOCAL_EVIDENCE` but TC-1 is `TC1_NOT_APPLICABLE` (J3), the journey falls back to the grid with reason
`TC1_NOT_APPLICABLE`. The journey's grid-only decision is the best verified R1 point, which can differ from R1's rung
decision (an `INDIFFERENT` R1 decides 673.15, its best point need not be 673.15); built literally as the spec says.

J12 [coverage] `check` judges a record's internal consistency and honesty (A10, A12): every label re-derived, the
report equal to its rendering, §11 verbatim, no forbidden word, every honest outcome stated. It does not judge W25 PASS
(a record with R1 `UNSUPPORTED` is accepted by `check`); W25's clause verdict is A20–A26 (WO-4) and the verdict lane's.
`replay` refuses with exit 2 until WO-4 (no placeholder success).

J13 [coverage] Q1 settled: R0's nine stand-in loop solves take ≈ 3 s wall in total (this machine), far under 60 s, so
A08 runs in the default gate.

## WO-2b — spec Amendment 1 applied (R-420…R-427), 2026-10-16

J14 [coverage] Applied, one commit per ruling: G1–G4 + registration (`4139f59`; `test_a06` counts 9 in the same
commit); R-420 null floor never 0, `tc1.missing` (`927881c`); R-422 registered refusal (`677dd93`); R-423 experiments
{cold, store_hit, in_process} (`5bf64d2`); R-424 last-iteration `extrapolated`, R0 closed forms (`140e262`); R-421 stop
re-derivation, extras inside the point's wall (`cfceaf3`); R-427 grid-only = R1's rung decision (`224f3e1`); R-426
margins (`7efe220`); R-425 R3 input conditions, anchor, copied accounting (`4f1c255`). The G4 comment is rewrapped to
the 100-column limit, text unchanged. The T* re-solve, `t_star_resolve`, `omp_num_threads` and replay's refusal (A1.7)
are WO-4's.

J15 [design] A1.4's first identity (`cold + in_process` = the point's coupling-record executions) is not checkable by
`check`: the record holds neither the executions nor the coupling record (only its sha256 under `artifacts`). Built: it
holds by construction in `coupling_attribution` (every attempt goes to exactly one of the two); `check` enforces the
second identity (Σₖ cold = `budget.spent.cold`). `replay` (WO-4) can verify the first against the bundle. Alternative:
an `experiments.executions` member, which changes A1.4's three-member record. Reversible: one line in
`coupling_attribution` plus a check.

J16 [coverage] AQ1 (A1.11) answered from the code: yes. `orchestrator.coupling.couple` appends the accepted iterate and
returns `CONVERGED` immediately after it (the item's `step.kind` is `converged`), and `coupling_evidence` certifies
against `coupling.iterations[-1]`; `final_constants` reads the same item. A non-converged run's last item is a failed
trial, but such a point is never verified. No other marker exists, so the default stands.

J17 [coverage] A1.6 choices: (a) anchor 1 (M05's run commit) and M05's spent wall read nothing until M05 names the
fields (FD-3): `m05_run_commit`/`m05_spent_wall` return `None`, never a guessed key. (b) A manifest "lists" the record
when an `artifacts[*].sha256` equals it; several matches take the first C_M in sorted order. (c) Unreadable JSON is
condition 1; a best candidate that is not exactly one candidate with one decision is condition 4. (d) Without
`--m05-record` R3 is plain `UNSUPPORTED(m05_study_unavailable)` (no limitation code); M05's package is no longer
required to carry a record. (e) R3 stores M05's `store_hits` at rung level; its accounting row is {cold = spent cold,
store_hit, in_process 0}; journey totals are null when a rung's spend is null. (f) `check` requires `carried_from` to be
a 40-hex commit or `rerun`, a null cold/wall iff its limitation is stated, and `wall_source` consistent with the wall
and with how the record was obtained.

J18 [coverage] A1.2: the stop re-derivation runs on R0 and R1; R2's grid (PROMOTABLE with a loop, dormant) is not
stop-checked. A point's `wall_s` now includes its parent extras, but the extras' own experiments are not charged:
they are not in the grid solve's coupling record (J1: store hits only). If M05's noise floor ever runs a cold reactor
experiment it would go unbudgeted — flag for WO-4's real R1.

J19 [coverage] R0 re-taken at `4f1c255` (`OMP_NUM_THREADS=1`, 2.6 s): VERIFIED ×9, INDIFFERENT at 673.15, J in
{0.46705958492513017, 0.4670595849251301} (one ulp, the registered spread), X_pass − 0.25 = −2⁻⁵⁴, recycle
3.11643882923465 and purge 0.0022800377163792337 (spread 0.0), Q_preheater 49278.69 → 54414.24 W (min step 640.40),
Q_flash −57530.13 → −62480.42 W (min step 616.47): unchanged. Moved, as ruled: `experiments` 2 executions per point
from {cold 2, store_hit 0} to {cold 0, store_hit 0, in_process 2} (A1.4); `extrapolated` 1 → 0 at all nine (A1.5).

J20 [coverage] Each commit was gated by the full `scripts/gate.sh` in its own detached worktree (in parallel) before
the push, rather than serially before each local commit; a red gate would have meant a local fixup before pushing.
