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
