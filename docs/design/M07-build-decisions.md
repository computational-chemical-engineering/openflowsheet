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

## WO-4 — the real journey at J, part 1 (2026-10-17)

J21 [coverage] Main (M05 at `defa458`) merged at `8ef35e6`: the register is a numeric union (R-017, the one entry both
sides held with different text, unchanged on M07's side, taken from main); `support_envelope.yaml` auto-merged to main's;
`docs/support-matrix.md` re-emitted unchanged. Premises read on M05's REAL record as merged (l.831-842): AQ2 holds
(condition 4: the targeted check's `revision_sha256` 03e2b696… = `document_sha256(document_at(c1-loop-real.json, T*))`,
T* = 653.1500351610193); AQ3 holds (M05 states `provenance` {run_commit cdacc322…, tree_clean, wall_s 1454.46}).
Conditions 1–5 pass. `m05_run_commit`/`m05_spent_wall` read those fields (`bf05034`); `C1Parent` now needs
`services=C1_PARENT_SERVICES` (the grid extras were broken against merged M05; fixed in the same commit).

J22 [design] Carry by identity is now checked (`9949eb3`): `git diff anchor HEAD` on `carry.journey_files` as pathspecs
(the prose "reactor environment lock (M02)" is `src/openflowsheet/adapters/pymrm/reactor-env.lock`). M05's anchor
cdacc322 differs from J in `src/openflowsheet/**` (coupled_run, revision_run, boundary, closure, holders, from M05's
later commits), so R3 is re-run at J by `m05_wo9_real.run_real` on a fresh store, written under
`benchmarks/m07/journey/<J>/m05/` with M05's writer; wall `journey_measured`. Choices: (a) without a re-run R3 refuses
with a new limitation code `R3:carry_identity_differs` (A1.6 names only `carry_anchor_missing`); (b) a re-run record
meets conditions 1–4 at run time and condition 5 once committed with the journey (it cannot be tracked at J). Needs:
ratify the code, or name another.

J23 [coverage] A1.7 (`f5de819`): the T* re-solve uses `C1Parent.solve` on the journey's store (R1's), not R3's fresh
M05 store, so it may run up to 4 cold experiments, recorded in `t_star_resolve` and counted only in the journey totals
(`accounting.t_star_resolve`, `accounting.journey`). `check` requires a re-solve on a real record with a verified
candidate. A real `run` refuses (exit 2) without `OMP_NUM_THREADS=1` when the reactor environment is there (A14's
no-reactor path still exits 3).

J24 [coverage] Only the tip `8f85aa2` was gated (the four WO-4 commits are small and sequential): 9412 passed,
31 skipped, 189 deselected (27 min).

J25 [design] `env.verify` still lists the manifest's `variant_id` as a difference although R-259 rules it provenance;
this machine's environment was built by v1 and serves v3 (same env_id), so `reactor_available` read it as unavailable.
The journey ignores that one line (`8f85aa2`). `env.verify` itself (M02's) is unchanged: flag to the design lane.
Also measured: a `PYTHONPATH` that includes `.reference-downloads/m03-ipopt/nlp-test-tools` leaks into the reactor
child's package check (pytest 9.1.1 vs the lock's 8.3.5), so the real run uses `PYTHONPATH=src` only.

## WO-4 — the real journey at J, part 2 (2026-10-17)

J26 [coverage] The environment block is taken before any rung (`672df66`). The J=`8f85aa2` run recorded
`tree_clean: false` only because R3's re-run writes `m05/` under `--out` before the block was read.

J27 [design-adjacent] `replay` (`1623633`). `run` writes `journey.experiments.json` (the spec names no file; M05's
`<stem>.experiments.json` convention, `m05_wo9_real.store_archive`). `replay` restores it and runs `run_journey`'s
steps with M05's `RecordOnlyBackend` for every unit, in process too (nothing executes; a request the archive cannot
serve is a difference and ends the replay). R0/R1 go through `run_grid` against M07-budget-v1 with the record's costs
(so it evaluates the points the record evaluated and stops where it stopped); R3 from the named M05 record (sha256,
conditions 1–5, `_r3_document`), carry and a re-run's wall from the record (the carry is RC step 15's, not replay's);
a refused R3's codes are copied (nothing to re-derive them from); then the T* re-solve. Taken from the record after
checking: measured walls; `experiments`, once the replay's counts equal {cold 0, in_process 0, store_hit = cold +
store_hit + in_process}; the coupling digest (its record carries the attempts and `cache_hit` a store hit changes).
Everything derived (budgets, accounting, labels, pairs, TC-1, parent checks) is re-derived and the whole record is
compared member by member, numbers by JSON text. `run_sha256` needed no exception. Exit 2 `omp_num_threads differs`
on a thread mismatch, or without the archive. Needs a ruling only if the substituted members are not what the spec
means by "every number".

J28 [coverage] J. `672df66` and `1623633` change `run` (the environment timing, the archive), so the `8f85aa2`
output (uncommitted) was not taken as WO-4's record; the journey was re-run at J = `1623633` (clean detached
worktree, `OMP_NUM_THREADS=1`, `.venv-nlp` with `PYTHONPATH=src`; exit 0) and committed at `c1f104f`. Against the
`8f85aa2` run, every number is bitwise equal; the differences are `commit`, `tree_clean` (false → true), walls,
the coupling digests and R3's M05 record (path, sha256: its provenance carries the run commit and wall; the targeted
check's coupling digest follows). Result: decision `refined` at T* = 653.1500351610193 K (R3 `DECISION_STABLE`,
`PARENT_LOCAL_EVIDENCE`, J* = 0.4524965242483627, e* = 1.85395193012364e-06); R1 `DECIDED` at 653.15 K
`BOUND_LOWER`; R0 `INDIFFERENT`; R2 `SURROGATE_NOT_PROMOTABLE`; TC-1 `TC1_HOLDS`; P01 `FE_CHANGED`, P13
`FE_UNCHANGED`; reactor cold R1 36, R3 48 (M05's re-run, wall 1458 s), T* re-solve 4. `check` ACCEPT. `replay` at
`c1f104f`: bitwise, 13.4 s; with `OMP_NUM_THREADS=2` exit 2. The `8f85aa2` record also replayed bitwise (dev check).

J29 [design] Open, carried with their defaults (no code changed for them): (a) J22 — the limitation code
`R3:carry_identity_differs` and condition 5 holding for a re-run record only once committed (default: as
implemented); (b) J25 — `env.verify` lists `variant_id` despite R-259, and `nlp-test-tools` on `PYTHONPATH` breaks the
reactor check, so the opt-in tests run in the main `.venv` and the run in `.venv-nlp` with `PYTHONPATH=src` (default:
leave, documented); (c) T* = 653.15 + 3.5e-5 K reads `INTERIOR` under the registered at-bound tolerance while R1's
653.15 K reads `BOUND_LOWER`; the record reports both labels as the rules give them, and the bound phrase appears for
R1 only (default: no tolerance change).

J30 [coverage] Every WO-4b commit was gated on a clean detached worktree at that commit before it was pushed:
`672df66` 9413 passed / 31 skipped; `1623633` 9419 / 31; `c1f104f` 9435 / 31 (gates and opt-in on the docs commit: its message). A first `31067bd` failed
ruff format on one test line (tests passed); it was amended before any push, which moved J, so the journey started at
the unpushed `1ca7ef0` was stopped and re-run at `1623633`. Opt-in: `-m pymrm` on the journey tests 1 passed (replay).

## WO-4c — the review's fixes and the re-take at J′ (2026-10-17)

J31 [coverage] Retiring the stale record (`7f108d3`). Amendment 2 changes the registration and R3's member, so the
`1623633` record fails `check` from the first fix on, and the default-gate record tests with it. As at J, the commit J′
holds no record and no record tests (`benchmarks/m07/journey/1623633…/` and `tests/test_m07_journey_record.py` removed);
both return in the record commit after J′, the tests with SF3 and the `offered` assertion. Alternative: keep both and
leave J′'s gate red. Reversible by: restoring the directory from `c1f104f`.

J32 [coverage] MF1 / R-452 (`6501016`): G5 applied verbatim (`BOUND_TOL_SCALED = DELTA_T / HALF_WIDTH` = 0.025;
fixtures b-02/b-03/b-05/b-06 at ±0.475 / ±0.525 K, b-08 = 653.15 + 3.5e-5 K `BOUND_LOWER`; catalogue row A07).
Registration regenerated, `--check` PASS; the script reads the tolerance from the registration and is unchanged.

J33 [coverage] MF2 / R-453 (`854deda`): G6 (`CARRY_R3`, `CARRY_JOURNEY`, registration `carry.r3_files`), GC-CARRY-1
(ast, module-body `import`/`from` statements, first name component, resolved in `scripts/` then `tests/support/`;
closure = the five files G6 lists). `carry_paths(key)`, `carry_identical(anchor, key)`, R3 on `r3_files`
(`r3_carry_identical`). The A21 case runs in a scratch git repository with `ROOT` patched: a changed
`scripts/m05_wo9_real.py`, `m05_wo8_runs.py`, `tests/support/m05_replay.py` or the schema carries neither set;
`m07_journey.py` / the registration break only `journey_files`; an unrelated script neither.

J34 [coverage] SF2 / R-454 (`2905034`): `m05_record.offered` {path, sha256, anchor, reason}, null when carried;
`check` requires the member, stated iff `rerun`, reason `carry_anchor_missing` iff anchor null; `replay` copies it
(A2.4); the report's provenance gains one line naming it. `_r3_document(…, offered=)` is keyword-only, no default, so
no caller can drop it silently.

J35 [coverage] SF1 / R-455 (`974c395`): `m05_wo9_real.compare(real, *, stem=STEM)`; `replay` calls
`replay_m05_rerun` for a re-run R3 (`run_real(archive=…)`, then `compare(stem=…)`; a `ReplayDivergedError` is a
difference). M05's REAL replay imports pyomo, so `replay` of a re-run record and the opt-in record tests now need the
nlp environment. pytest there without the J25 leak: the nlp-test-tools directory is appended to `sys.path` in process
(`python -c "…sys.path.append(tools); pytest.main(…)"`), `PYTHONPATH=src` only. Opt-in test on M05's committed REAL
record at a scratch stem: clean replay → no difference; one `result.json` dropped → `replay diverged` (1 passed, 7.4 s).

J36 [coverage] SF3 and the `offered` assertion (`c4e8467`, with the record): A21 asserts R3 equals
`_r3_document(path, m05, chosen, carried_from, wall, offered=…)` of its M05 record, apart from `t_star_resolve` and
`candidate.constraints`, compared by `dumps` text; and that `offered` names a tracked, unmodified file of that sha256,
with the anchor `m05_run_commit` / `manifest_anchor` give and the matching reason. Record tests 18 passed (default).

J37 [coverage] J′ = `974c395fbb2ab60fd69fc8d53e4f33e7207e9f3e` (gated 9436 passed / 31 skipped before the run; pushed).
Journey run in a clean detached worktree, `OMP_NUM_THREADS=1`, m05's `.venv-nlp`, `PYTHONPATH=src`: exit 0, 3324 s;
committed at `c4e8467`. R3 re-ran (`carry.r3_files` differ from `cdacc32`): DECISION_STABLE, T* = 653.1500351610193,
cold 48, wall 1461 s, bijection violations 0. Against the `1623633` record (`json_differences`, 74 members): every
number is bitwise equal; the differences are walls, coupling/store digests (`coupling_sha256`,
`coupling_record_sha256`, `run_sha256` of R3 and journey parent checks), `commit`, `registration_sha256`, R3's
`m05_record` {path, sha256, offered}, and the labels A2.6 predicts: `rungs.R3.bound_activity` and
`decision.bound_activity` INTERIOR → BOUND_LOWER, limitations + `bound:R3`, `bound:journey` (bound phrase now for R1, R3,
journey). The M05 re-run record against `1623633`'s: 15 members, all walls, digests and `provenance`. `offered` =
M05's REAL record (sha256 `09cf5366…`), anchor `cdacc32…`, `carry_identity_differs`. `check` ACCEPT. `replay`
(nlp environment): bitwise, 17.7 s, M05 re-run replay clean; `OMP_NUM_THREADS=2` exit 2. Opt-in (`-m pymrm`, the
J35 in-process path): 2 passed. nlp tier: 186 passed, 1 skipped. Gates: `7f108d3` 9419/31, `6501016` 9420/31,
`854deda` 9427/31, `2905034` 9436/31, `974c395` 9436/31, `c4e8467` 9454/31 (each on a clean detached worktree at that
commit).

## WO-3 — the 0.2.0 gate script (2026-10-18)

J38 [choice] Merge of `origin/main` (the released 0.2.0a1 alpha, `93cfbe5`) at `81cc0cd`: the register's only
conflict was its tail; numeric union R-451 (main), R-452…R-455 (ours), R-456…R-460 (main), no number on both sides,
407 headings, no line lost from either side. Envelope merged clean (`--emit` unchanged, `--check` 0 problems). Gate
9747 passed / 31 skipped. The journey record's default-gate tests pass (its `check` does not require the carry to
HEAD), so no re-take. Note: J′ no longer carries to HEAD (J42).

J39 [choice] The re-judgement line and the ADR's name read from the gate set (`0d5dbfb`). `GateSet.rejudged` is Table
T8's line over the gate alternation of the set's `clause`; `REJUDGED_VALUE` stays the alpha's pinned constant and
equals the alpha's `rejudged`. Without it v0.2-gate-v1's registered wait (W24, M03 N1) can never be listed: the
alpha's grammar stops at W22. `GateSet.adr` = "ADR " + the number in `policy_adr`, so the 0.2.0 report reads ADR 0042
where the alpha's reads ADR 0028 (§7.1). Neither is a new field. Alternative: leave both module-level and accept
that W24 cannot be re-judged and the 0.2.0 report names ADR 0028. Reversible by: reverting `0d5dbfb`.

J40 [needs ruling] M07.A31 ("alpha tests pass unmodified") cannot hold beside A30 (`039cbd8`). Five alpha cases assume
the alpha is the only set: `test_the_registry_is_the_specification_s` (`GATE_SETS` names == [alpha]), and
`test_a01_coverage_is_table_t1` for 0.2.0, 0.2.0b1, 0.2.0rc1 and `test_a12_main_on_an_uncovered_version` (0.2.0),
which assert "not covered" for versions Table T-V gives to v0.2-gate-v1. Minimal edit, isolated, holding with or
without the new entry: the registry test checks `GATE_SETS[0]`; T1 judges the alpha's pattern on every row and skips
the uncovered-report check where another set covers the version; the end-to-end uncovered case uses 0.2.1. Every
other alpha assertion, AM-07 and the alpha ledger test are unmodified, and the alpha's text/--json/--markdown output
at `cc73219`/`423ae9c` is byte-identical after every WO-3 commit. Proposed wording: "the alpha's tests pass,
unmodified except the five cases that assumed it was the only set". Alternative: keep `GATE_SETS` alpha-only and a
second registry for `gate_set_of` (still breaks the T1 and 0.2.0 cases). Reversible by: reverting `039cbd8` (then
those five fail).

J41 [choice] O3 (`d4680b7`): a second new field, `GateSet.links_item` (default None; "V17 carry" for v0.2-gate-v1),
beside §7.2's "only structural change" `clause`; R-457/O3 postdate the spec and need a per-set switch so the alpha
stays byte-identical. The registers are read from `scripts/m07a_rc.py` at the candidate with `ast` (the `LINKS`
tuple's `Link(name, register, …)`; today R-192, R-234, R-295; equal to the imported `LINKS`), and each must appear as
a whole id (`(?<![\w-])R-295(?![\w-])`) in any cell of the decisions-table row; a miss adds "V17 carry does not name
R-…" to Frank's problems. The field is not in the registration, so A32 compares the registration's fields only.
Alternative: a hard-coded check on the set's name. Reversible by: reverting `d4680b7`.

J42 [choice] Carry checks (`9479f97`): `w27_carry` and `journey_carry` return `Carry(carried, reason, differs)`;
the reason is exactly §9's "W27 campaign surface differs between C_W and C" or "step 15 requires a re-run of the
journey at C" (my wording of A38), with the differing members / changed files listed apart from it. The journey's
pathspecs are `m07_journey.carry_paths("journey_files")` (this tree's registration; the RC job's tree is C); an
unknown J does not carry. CLI `--carry-journey J` / `--carry-w27 AT_C_W AT_C` with `--rc C`, exit 0/1. **Measured:**
`--rc HEAD --carry-journey 974c395` → re-run required: main's merge changed `src/openflowsheet/{__init__.py,
application/coupled_run.py, verify/checks.py}` and the 36 `benchmarks/m05/records/trust-region-study-*` files of the
G10 re-take (R-458). Unless a later J is cut, RC step 15 re-runs the journey at C.

J43 [choice] O1 (`8a4c4e0`): `tests/test_m07_ledger.py` judges only on a tree whose version v0.2-gate-v1 covers (there a
missing `docs/reviews/V02-verdicts.md` fails); on main's `.devN` tree its four tests skip naming the version; a fifth
test pins that rule. W21 (M01, M02) and W22 (M01) package citations are carried from the alpha; no per-gate citation is
checked for W23–W27 (the rulings name none). Alternative: no skip (red until C), or citations for W23–W27 by package.
Reversible by: editing the one test file.

Findings (recorded, not acted on): (F1) registration `gate.rc_steps` step 17 names `M07.A53`; spec §8 names M07.A62.
(F2) ADR 0042's tables read "Frank's acceptance (date)" and "Answer (date)"; the gate reads columns "Frank's
acceptance" and "Frank's answer", so today it finds no answers table (WO-6 must use the gate's headers, A42). (F3) A
non-acceptance answer under v0.2-gate-v1 still says "amend the alpha specification for it", and RC-record reasons
say "§8.2 step" (the alpha's numbering); changing them needs a field. (F4) A dry v0.2-gate-v1 run at HEAD as if 0.2.0
lists 35 reasons: no verdicts/RC record/M07 manifest, W23–W27 without ledger verdicts, the dev envelope, ADRs 0031,
0032, 0038, 0039, 0041, 0042 Proposed, and F2.

## WO-5 prerequisites — W27 readiness at `wp/M07-w27` (2026-10-18; no model call, nothing spent)

Verified against registration §21.8/§22.5 at `958b983`: the binder reading (`snapshot.reading_for` → `bases-v1`; the
spec's "`snapshot.READINGS`" has no such symbol), the C1 rows (22 `model_functions`; the three reactors null with
`fixed_design_reactor`, `synthetic_stand_in`, `surrogate_model`), and J3′: the live snapshot equals
`hypothetical_v02_a3` (models and routes); live coverage rows and summary equal the committed `coverage.json` (snapshot
equal but for `git_commit`), 0 CANDIDATE, 0 class/reason differences (`amendment_3`). Stub dry run at `958b983`: G14,
P1–P8 (stub canaries), G15 20/20, A23 all PASS. Added: the harness command line (`27fb4b8`), the spend ceiling (next
commit), `docs/briefs/W27-runbook.md`.
- DECISION: campaign spend guard → stop before a run when recorded spend + USD 5 × (uncosted runs + 1) > 45 (CLI
  default; `within_spend_ceiling`). Alternative: no guard (45 × the USD 5 cap allows 225) or stop only once spend ≥ 45
  (may pass it by one run). Reversible by: reverting its commit.
- Open (design lane): (Q1) U14's rewrite "with the campaign" (R-194) is unwritten: text and test are not settled;
  `test_u14_…` fails on any `/runs/` path, so the records cannot be committed until it is. (Q2) M07.A50 orders
  "canaries, draw", but W27-R31 defines the canaries as frame cases not in the sample: the draw must come first.
  (Q3) R58's `confirmation/` record of an empty C, and a record that the preflight passed (W27-R56), have no writer and
  no format. (Q4) Re-canaries (registration Q3) are not implemented: P6 counts exactly three canary directories.
  (Q5) "Most recent model" is ambiguous across families in 2.1.302's catalog.
- Finding: `tests/test_m07a_harvest.py` fails when `evidence/M06/W27/artifacts` is a real (ignored) directory — it
  harvests the archive's `wheelhouse/manifest.json`; the campaign needs exactly that (a symlink dirties the tree).

## WO-17a — registration Amendment 4 build actions at `wp/M07-w27` (2026-10-18; no model call, nothing spent)

Authority: registration §23 (W27-R64…R68, R-467…R-471), §23.8's list; M07 spec §21. A4-Q1…Q3 take their defaults:
(Q1) an alias in the pinning attempt's `init` stops `canaries` with exit 2 before the next attempt (`model_pin`);
(Q2) the cap counts attempts, 6 (`campaign_records.canary_attempts_max`); (Q3) records 1–3 are re-made in place after a
C_W move, the old digests go into this log (runbook (c)).
- DECISION: what `run.json#/pinned/model` holds for a canary attempt run without `--model` → that attempt's `init`
  model, when it is non-empty and not `claude-sonnet-5` (`harness._unpinned`); `model` (the requested one) stays null.
  Why: §23 registers `model` null and the session check (init model non-empty, not `claude-sonnet-5`) but not `pinned`;
  with `pinned.model` null the scorer's unchanged pin check (`pin_mismatch(model)`, scorer l.863) makes every unpinned
  attempt an infrastructure failure, so no canary could pass, contradicting `p6_states`/`p7_states` (attempt 01 null,
  passed). Alternative: a scorer exemption for an unpinned run (changes a scoring rule; §23 says none changes).
  Reversible by: reverting the `_unpinned` hunk of its commit. For the design lane's ruling round.
  **Ruled (registration §23.12, R-472, `a230156`): accepted as built**; W27-A23 restated to check W27-R58's model rule
  (WO-17b below).
- Done (`1ed4a96`, `b71d86c`, `8a3b17e`): U14 text verbatim and its test (W27-A70…A73); `harness confirm` and P5
  (A74); `canaries` numbering, stop at the first failure, the cap, no `--model`, the pin from the directory, P6/P7
  (A76, A77: 11 and 6 registered states); `preflight.json` in `campaign`, P8, the new `run.json` members (A75);
  `order_check` and the `order` command (A78); the runbook in the new order. Stub dry run at tree `ac59800`
  (= `8a3b17e`; run from a clean temporary commit of the same tree): G14, P1–P8, `preflight.json` (registered
  members, passed), 45 stub runs + `campaign.json`, `order_check` (0 problems), G15 20/20, A23 (59 records) all PASS.
- ~~Note for M07.A51 (other branch): A23's `RUN_RECORD_MEMBERS` requires a non-empty `model`, which an unpinned canary
  attempt records as null by §23.3; A23 is applied to campaign runs only (the dry run does so).~~ Withdrawn: §23.12
  restates A23 (the model rule replaces the non-empty `model`), and M07.A51 applies it to every `run.json`, `canary/`
  included (M07 spec §21 addendum; WO-17b).

## WO-17b — registration §23.12 build actions at `wp/M07-w27` (2026-10-18; no model call, nothing spent)

Authority: registration §23.12 (R-472), M07 spec §21 addendum. No build decision was needed.
- `harness.a23`: `model` leaves `RUN_RECORD_MEMBERS`; it must be present as a key, and `harness.model_rule` (W27-R58's
  model rule, the generator's `ref_run_model` in code) must hold, else the problem `model_rule`. Kind `canary` iff
  `campaign` ends in `/canary`; a missing `pinned` or `session.init` level reads as null.
- W27-A79 in `tests/test_m06_w27_harness.py`: (a) the 11 `run_json_model_states` overlaid on the W27-A23 stub record,
  passing ids R1, R2, R3, R4, R10; (b) one unpinned attempt through `harness.run` with `agent_config(None)` and the dry
  run's stand-in canary `claude` (`dryrun.CANARY`, now a module constant): A23 passes, `model` null, `pinned.model` =
  init = `STUB_MODEL`, no infrastructure failure; its copy with `pinned.model` null re-scores `pin_mismatch(model)`.
- K read from `campaign_records/p6_symbols/K`; `_states_campaign` asserts K differs from HEAD.
- `dryrun`: A23 on every `run.json` under the campaign directory, `canary/` included (keys are paths relative to it).
- Stub dry run at tree `73c7fec` (a clean temporary commit of this commit's code; the archive linked file by file
  under the ignored `evidence/M06/W27/artifacts/`, since a symlink in place of that directory is untracked and dirties
  the tree for P8): G14, P1–P8, `preflight.json` (registered members, passed), 45 campaign runs, `order_check` (0
  problems), G15 20/20, A23 PASS on 62 records (14 state runs, 45 campaign runs, 3 canary attempts; attempt 01
  `model` null, `pinned.model` = `STUB_MODEL`).
