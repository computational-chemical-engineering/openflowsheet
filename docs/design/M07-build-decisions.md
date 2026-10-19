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

## WO-3b — spec Amendment 3 applied (R-461…R-466), 2026-10-18

J44 [ruled, R-462/R-465] §20 A3.7 step 1. The generator delta applied verbatim (`git apply` of the spec's block, clean
against `958b983`); regenerated `benchmarks/m07/registration.json` sha256
`85e56dd5792e2ead3de3d8eae5b2bfff45bd61f5e32a9d5ec6dd61b9d282506b` (= the spec's), `--check` PASS; the registration
differs from J′'s in `gate` only (`links_item` ×2, RC step 15's text, step 17 → M07.A62). `check`
(`scripts/m07_journey.py` `_check_registration`) implements A3.5's two paths and two texts; `git show
<commit>:benchmarks/m07/registration.json` is read as bytes, and a `commit` that is not 40 lower-case hex digits is an
unknown commit (fails closed without calling git). The tree's registration is read through `_tree_registration()`, the
reader S4 monkeypatches. A32's `_fields` compares `links_item`. A10's states S1–S4 are four tests on the committed J′
record (`tests/test_m07_journey_record.py`); mutations measured: path (ii) removed → S1, S4 and the J′ `check` fail;
`journey` added to the ignored members → S4 fails. CI needs full history for path (ii): every pytest job checks out with
`fetch-depth: 0`.

J45 [ruled, R-461] A31 (b): `test_a31_b_the_alpha_s_tests_are_the_tagged_ones_but_the_three_edited` compares each
top-level node of `tests/test_m07a_v0_2_gate.py` (`ast.dump`, no positions) with `git show 423ae9c54d…:…`, the three
functions of F-a replaced by their names, so an added, removed, reordered or edited node outside them fails (mutation:
one appended assignment → fails). It lives in `tests/test_m07_v0_2_gate.py`: placed in the alpha's module it would
itself be an added node.

J46 [ruled, R-464] A37/A38 as restated in §11: the tests now pin the registered reason on every refusing path — a
member missing on either side of the W27 triple (both directions, not only C_W's), and an unknown J
(`Carry(False, "step 15 requires a re-run of the journey at C", ("<J> is not a commit",))`, the reason was not asserted
before) — and the exclusivity §20 A3.4 states: `--carry-journey` with `--carry-w27`, and either with `--json` or
`--markdown`, is refused by argparse (exit 2), five cases. No code change: `v0_2_gate.py` already behaved so.

J47 [choice, §20 Q-A3-1 default] F3's wording: `GateSet.specification` and `GateSet.rc_section` are properties derived
from `evidence_package` through one module table (`M07a` → "the alpha specification", "§8.2"; `M07` → "the M07
specification", "§8"); no new registered field. The non-acceptance answer and the two RC-record reasons read them. The
alpha's texts are byte for byte today's (its tests, AM-07 and A31 (b) unchanged and green); the v0.2-gate-v1 cases now
expect "amend the M07 specification for it" and "§8 step 15 …". Alternative: leave the alpha's wording under both sets.
Reversible by: reverting this one commit.

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

## W27 (e) repair — `campaign.json` completed (2026-10-18; no model call, nothing spent)

Authority: verdict `docs/reviews/W27-verdict-83f825d.md` §(e) and F-4; registration W27-R52…R56, §23.3. Commit
`89cd931`.
- `scorer.aggregate` gains, keyword-only and defaulting to "not established"/None: `coverage.by_family` (R53, from
  `coverage.json#/summary/*/by_family`); `reported.semantic` and `reported.cost` (R54's §11.10, pooled as V17's
  `_pooled_semantic`/`_pooled_cost`: counts summed, each rate = pooled numerator / pooled denominator over the runs that
  have both, the semantic error rate over parseable limitation answers; cost fields sum, median, runs; jobs summed by
  operation; the cost basis as recorded); `reported.model` and `reported.claude_code_version` (R54: pinned from
  `preflight.json`, requested/recorded from each `run.json`, `init` from each session, as distinct values);
  `gated.operator_identifier_hits` and `gated.preflight_passed_before_first_run` (R56).
- Identifier scan (F-4): `harness.identifier_scan` counts the operator address, case-insensitively, in every file of
  every registered run directory and every canary attempt (nothing under `runs/` is git-ignored, so these are the
  committed files). Only counts leave it. The per-run `run.json#/operator_identifier_hits` (R6.6's four
  `SCANNED_FILES`, V17's RUN-ID-SCAN and the canary verdict) is unchanged, so old records stay valid. Canary hits are
  reported separately and included in `count`.
- Preflight term exactly as §23.3: established iff `preflight.json` exists with `passed` true and every campaign
  `run.json#/preflight_sha256` equals its digest.
- `harness.write_campaign` (used by `campaign`) and `harness aggregate --campaign <name>` (`reaggregate`: refused
  without an existing `campaign.json` or when the served MCP surface differs from the recorded one).
- Regeneration: `PYTHONPATH=$PWD/src python -m benchmarks.m06.w27.harness aggregate --campaign w27-m07-83f825d`.
  `campaign.json` SHA-256 old `15c6b300927342ac04037e34faba4fc7a7b0f20487997b16ca42b5f62d5f5839`, new
  `4812910abb2622b9192c01eae331fa2e97b3f523d78f73510b845c32f20f9e28`. `git diff --stat` on the campaign directory: only
  `campaign.json` (+242 −1; the −1 is the comma after `map_defect_candidates`). Every member of the old document is
  equal in the new one (outcomes included); `harness order --campaign w27-m07-83f825d` exit 0, 0 problems. Pooled
  values equal the verdict's: items 216 (214 judged: 193 matched, 11 contradicted, 10 naming nothing; 2 unjudged;
  0 malformed), semantic error 21/214, API rejection 0/95, draft-commit 0/0, internal errors 0, tool calls 95, turns
  140, jobs 0, job wall 0 s, duplicates 0, tokens 194 / 49 224 / 621 371 / 1 680 942, duration 471 929 ms (API
  468 335 ms), cost 3.1462062 (subscription estimate); identifier hits 0 over 384 files (45 runs, 3 canaries);
  preflight established (45/45 name `56dc325e…d02f`).
- Tests: `tests/test_m06_w27_scorer.py` (by-family, §11.10 pooling incl. null rates, provenance, six preflight states,
  identifier counts incl. a positive hit and a partial scan), `tests/test_m06_w27_harness.py` (scan beyond
  `SCANNED_FILES`, nested, case-insensitive, canary; the committed `campaign.json` reproduced byte for byte from a copy
  of the records; both refusals).
- `CAMPAIGN_SCHEMA` stays `w27-campaign-v1` (members added, none changed or removed).

## WO-6 — release notes, ADR 0042 rows, examples pointer (`wp/M07-wo6`, 2026-10-18)

- `CHANGELOG.md` `## v0.2.0`: M01–M05 and M07 entries (from the ADR titles and the register), the eleven "What it is
  not" phrases verbatim from `benchmarks/m07/registration.json` `gate.changelog_what_it_is_not` (M07.A40). No W27 numbers.
- ADR 0042: headers untouched (A3.6); the D3 table's `—` row replaced by `V14 (b) | pending` (spec §15 N4); the four
  Frank rows already carry their defaults, `V17 carry` names R-192, R-234, R-295; every answer stays `pending`.
- `examples/README.md`: pointer to the journey report `journey.md` (the report's directory is not fixed by the spec; named
  by file, not path). Manifest (A43) not in scope.

## WO-8a — the cut commit K: stopped before K for two rulings (2026-10-18; no model call, nothing spent)

J48 [coverage] K's content, drafted on the local branch `wp/M07-K-draft` (not pushed; `853e7e3` = the version set,
`c38e1ba` = the re-take): `0.2.0` in R-460's file list (`pyproject.toml`, `__init__.py`, the two `project_summary`
fixtures, `test_m06_w27_coverage.py`); envelope pinned `v0.2-envelope-1` / `0.2.0` with `ENVELOPE_ID`, support matrix
re-emitted (`--check` 0 problems); W27 coverage re-taken (G14 PASS; rows, summary and `list_models` f070fbe0… equal to
C_W's `runs/w27-m07-83f825d/coverage.json`; snapshot 6fd235c1…; `registration_sha256` ba627342… → ee099a60…, the
value C_W's coverage already carries). G10 re-take of the five records from the clean tree at `853e7e3` (alpha-main's
`.venv-nlp`, `OMP_NUM_THREADS=1`, `PYTHONPATH=src:<nlp-test-tools>`), proved with `--digest-only --old-version
0.2.0a2.dev0`, every case PASS, `other=0`, `environment=equal`; changed digests / version leaves:
TR-E2 41/4, TR-E2-FAR 79/7, TR-E2-FD 70/4, LOOP-R 91/3, LOOP-S 37/4 (E6's counts exactly).
- DECISION: K as two commits → the version set (A), then K = A + the G10 records, whose `provenance.run_commit` is A.
  Reason: the committed G10 records (E6's) state `provenance.tree_clean: true`; a re-take on K's own uncommitted tree
  would record `false`, and a single commit made after a clean re-take would leave `run_commit` outside the history. Precedent E7 → E6. Alternative: one commit, `run_commit`
  unreachable. Reversible by: squashing before the journey runs.

J49 [stop, design lane] Full gate on the K-equivalent tree `c38e1ba`: 30 failed, 9904 passed, 32 skipped, 5 errors.
29 failures and one teardown error are `tests/test_m06_browser_smoke.py` (BrokenPipe: the browser died under load;
re-run alone 31 passed). The other five are registered behaviour at a `0.2.0` tree, not local bugs:
- (Q-K1) `tests/test_m07a_v0_2_gate.py::test_a10_the_envelope_must_be_pinned_to_the_alpha`: its fixture undoes only the
  alpha's pin (B-WO10-1), so with `v0.2-envelope-1` it asserts `'v0.2-envelope-1' == 'v0.2-envelope-dev'` and fails.
  Editing it breaks A31 (b) (`test_a31_b_…_but_the_three_edited`, R-461 admits three edited functions). Default
  proposed: admit `test_a10_…` as a fourth edited function, the edit being the two pairs that undo the 0.2.0 pin.
- (Q-K2) `tests/test_m07_ledger.py`, four setup errors: `docs/reviews/V02-verdicts.md is missing at a 0.2.0 tree`.
  R-463 rules exactly this, so every commit from K until WO-7's verdict document is red, C included — and RC step 1
  (`check.sh` at C) runs before WO-7 can write the document. Default proposed: at a covered version the four tests
  skip while the verdict document is absent (naming it), the fifth test pins that; `v0_2_gate.py` already answers NO
  without the document, so the release cannot pass over it.
Nothing was committed to `wp/M07` except this entry; the journey has not run (it needs K).
This entry's own gate (docs only, on `c50e6fb`): 29 failed, 9905 passed, 36 skipped, 1 error, all in
`tests/test_m06_browser_smoke.py` (BrokenPipe, load average 29 from other work on the machine); that module alone at
this tree: 31 passed.

## WO-8a (resumed) — F, A, K and the journey at K (2026-10-19; no model call, nothing spent)

J50 [coverage] F = `48db2d3` (§23.1 actions 1–3, §23.2 actions 1–4). Full gate 9939 passed, 35 skipped, 0 failed
(38:53); a first gate at the same tests failed ruff E501 on a docstring line only (pytest 9939/35 green), re-wrapped.
Ledger module at `0.2.0a2.dev0`: 1 passed, 4 skipped (S-UNCOV).

J51 [coverage] A = `0fcf1ad` (re-cut of `853e7e3` on F, §23.3 condition 1). The draft's files re-applied; files that
record a commit or a tree digest regenerated at A's build, not copied: `coverage.json` (`python -m
benchmarks.m06.w27.coverage`, G14 PASS; rows, summary, `list_models` f070fbe0…, `registration_sha256` ee099a60… equal to
the draft; snapshot `git_commit` F, `snapshot_sha256` 211cf4f1…) and `docs/m06-w27-coverage.md` (`report --check` OK);
support matrix re-emitted, `--check` 0 problems. Full gate at the committed A: 9939 passed, 35 skipped, 0 failed
(45:58); `test_a10_…` and both A31 (b) tests pass; ledger module 1 passed, 4 skipped (S-ABSENT). A first gate on the
uncommitted tree had 2 failures that are the tree, not the code (`test_m06_w27_harness::…preflight…` expects P3 to fail
because coverage's `git_commit` ≠ HEAD; `test_m07_journey::test_a21_…` reads `git diff HEAD` of `__init__.py`): both
pass once committed. So A and K were committed locally, gated, then pushed (B-WO10-5's reason, J30's practice).

J52 [coverage] G10 re-take at A's clean tree (§23.3 condition 2; 18 s), alpha-main's `.venv-nlp`, `OMP_NUM_THREADS=1`,
`PYTHONNOUSERSITE=1`, `PYTHONPATH=src:<nlp-test-tools>`; `--digest-only --old-version 0.2.0a2.dev0`:
  PASS tr-e2 changed-digests=41 version=4 · tr-e2-far 79/7 · tr-e2-fd 70/4 · loop-r 91/3 · loop-s 37/4; other=0,
  environment=equal in all five. E6's counts exactly (A6-Q1 answered: reproduced; A6-Q2: the re-take is 18 s).
  A first take without `PYTHONNOUSERSITE=1` gave the same counts but `environment=differs` (26 distributions, not 17:
  seven docs/coverage packages in `~/.local` leaked in); discarded, not used.

J53 [coverage] K = `2c508b5` = A + the 36 record files. `git diff --name-only A K`: 36 files, all `benchmarks/m05/**`;
each re-taken record `run_commit` `0fcf1ad…`, `tree_clean: true`; `git merge-base --is-ancestor A K` exit 0. AM-23
(`-m nlp tests/test_m05_g10_replay.py`, `.venv-nlp`): 5 passed at K. Full gate at K: 9939 passed, 35 skipped, 0 failed
(40:19). `wp/M07-K-draft` deleted.

J54 [coverage] The journey at K (A3.4 items 2–3; J37's recipe: clean tree, m05's `.venv-nlp`, `OMP_NUM_THREADS=1`,
`PYTHONNOUSERSITE=1`, `PYTHONPATH=src`, `--m05-record benchmarks/m05/records/trust-region-study-real.json`): exit 0,
3330 s; record and report `benchmarks/m07/journey/2c508b5…/` (this commit; no file of `carry.journey_files` changes).
- decision `refined` at T* = 653.1500351610193 K, `BOUND_LOWER`; R0 `INDIFFERENT` (18 in-process); R1 `DECIDED` 653.15 K
  `BOUND_LOWER` (cold 36, 1558 s); R2 `SURROGATE_NOT_PROMOTABLE`; R3 `DECISION_STABLE` (M05 re-run, `carry_identity_differs`
  from `cdacc32`, cold 48, 1477 s; 14 distributions as J′'s); T* re-solve cold 4, 291 s; TC-1 `TC1_HOLDS`; pairs P01, P13.
- Against J′'s record: 70 leaves differ, all walls, coupling/record/run digests, `commit`, `registration_sha256` and R3's
  `m05_record` {path, sha256}; every other number bitwise equal.
- `check` ACCEPT; `replay` (after commit; condition 5, J22): bitwise, 18 s; `OMP_NUM_THREADS=2` exit 2;
  `tests/test_m07_journey_record.py` 39 passed (K and J′ parametrized); `v0_2_gate.py --rc HEAD --carry-journey K`:
  `RC step 15: the journey at 2c508b5… carried`, exit 0.

J55 [finding, design lane] Opt-in `-m pymrm` (nlp env): `test_a24_replay_…[2c508b5]` passes, but
`test_a24_replay_…[974c395]` (J′) fails, `replay diverged: a cold execution at {…}`. Pre-existing: the J′ replay passes at
`c4e8467` and fails already at `d3c72cb` (this WO's start), so not caused here; the alpha lineage (0.1.1 → 0.2.0a1 →
0.2.0a2.dev0) moved the request digests J′'s archive is keyed by. Not in the default gate or CI. Default: leave; the
design lane decides whether A24 is judged for J′ only at its own commit.

## WO-8b — C and RC steps 1–17, part 1 (2026-10-19; no model call, nothing spent; HANDOFF, stopped at the context cap)

J56 [coverage] WO-10 done in C: C = **`c899c85ab43fb114cd85c69baf12e692b75a8eab`** (`report.render` emits §22.3's Scope
paragraph; `report --check` OK; the paragraph once; neither file in `carry.journey_files`). Gate at C: 9956 passed,
35 skipped (29:02); ledger module 1 passed, 4 skipped S-ABSENT (§23.2). Pushed.
J57 [finding] §7.2 at C (`v0_2_gate.py --rc HEAD --json`): the six packages' manifests qualify (M01–M06 `tested` at
ancestors). Not met: ADR 0031, 0032 (M03), 0038, 0039 (M05) still `Proposed` although their packages are `tested`;
0041/0042 follow the verdict/Frank's answers. Not fixed here (an ADR's acceptance is not the build lane's to set).
J58 [coverage] CI at C: dispatch **39224213490** (`rc_alpha`, `rc_distribution`; steps 1–10), push **39224203477**
(step 16's browser test = its `check (ubuntu-latest)` job). Both `gh run watch --exit-status` exit 0: dispatch — check
(both runners), identity, dist, clean-install ×2, bundle-set, bundle-replay ×2, rc-steps ×2, rc-ensemble, default-install
all success; push — check ×2, identity, default-install success. Artifacts and job logs not yet fetched.
J59 [coverage] Local RC run: RC worktree `.claude/worktrees/rc-c899c85` (clean throughout), scratch
`~/.cache/of-rc-c899c85/` (`tools/run_local.sh`, `run_step14.sh`, `m07_rc_external.py`, `write_carry.py`, `g12keep.py`,
`collect_records.py`; `summary.txt`, `durations.txt` [s], `logs/`); records under the RC worktree's
`evidence/M07/<C>/artifacts/rc/` (git-ignored), step 17's in `~/.cache/of-rc-c899c85/s17/` ($S). Per step:
- 2 identity PASS (98 s) · 6 ensemble PASS (97 s) · 7 corpus PASS (30 s) · 8 surface PASS (89 s) · 10 local certificates PASS
- 9 a30 **FAIL** (15 s): the A30 project workload imports every `openflowsheet` module; `studies/nlp/greybox.py:60`
  `import cyipopt` (M03's optional NLP path, not in `requirements.lock`) → `ModuleNotFoundError`. New at C (M03 not in
  the alpha's tree). CI `rc-steps` (which runs step 9 on both runners) concluded success: first read its downloaded
  A30 record — if it says PASS, find why CI's workload differs from the local one before asking. **Q1 (design lane):** how A30's closure treats M03's optional NLP modules (exclude and cover by
  the M03 inventory, or import-guard); any fix changes `scripts/`/`src/` and so needs a new C (and K? only if it touches
  `src/openflowsheet/**`, a journey file).
- 11 xcheck + IDAES PASS · 12 G10, G12, G12-edges, m02 tests PASS; **G11 BLOCKED**: the alpha's archived inputs lived
  in the removed `worktrees/m02`; `--previous-v3`, `--previous` recovered byte-identical from git (`bd446ab`), but
  `--d78` (`g11-exp.json`, sha256 afa7325a…) and `--previous-runs` (0656f617…) exist nowhere on disk or in git.
  **Q2 (design lane):** re-take D78 (M02 wo12a experiment) or judge G11 otherwise. Default: none; step 12 not pass.
- 13 W23 PASS: `m04_reference.py --check` (claims passed, every file byte-identical), `m04_schema_fixtures.py` exit 0,
  `tests/test_m04_*.py tests/test_evidence_manifests.py` 485 passed.
- 14 W24 attempt 1 discarded (RC venv's editable install left `src/openflowsheet.egg-info` → 18 distributions vs 17
  recorded; exported OPENBLAS/MKL=1 entered NLP fixtures). Attempt 2 (`run_step14.sh`, clean worktree
  `~/.cache/of-rc-c899c85/nlp-wt`, m05's `.venv-nlp`): `m03_nlp_check.sh` 186 passed, 1 skipped, both inventory
  `--check` PASS; `m05_wo9_real.py --replay` `REPLAY PASS REAL differences=0`; `m03_reference.py --check` exit 0;
  all-tier tests 641 passed, **1 failed** = `tests/test_m03_reference.py` run in the nlp env (no `mpmath`; it belongs to
  the project env, where the generator `--check` passed). **Remaining:** drop that file from `step14-tests` in
  `run_step14.sh` and re-run it (≈5 min); then `record-step14` must be all pass.
- 15 W25 PASS: `RC step 15: the journey at 2c508b5 carried`; `check: ACCEPT`; `replay: bitwise` (19 s).
- 16 W26 local PASS: `tests/test_m06_*.py` (REQUIRE_BROWSER=1) 661 passed; `node --test` exit 0; dry run `A23 PASS (62
  records)`. CI half: the push run's browser job (J58).
- 17 W27 PASS, 17a–17d: tree `95f9fcf2…895a`; coverage at C exit 0; `RC step 17: the W27 campaign carried`; precheck,
  `aggregate` exit 0, `diff -r` empty, `campaign.json` `4812910a…9e28`.
**Not done:** step 14's re-run (above); CI verdicts and `tools/fetch_ci.sh` (alpha's) into `artifacts/rc/ci/`; step 1
skip lines (R-376); `collect_records.py` (retarget `C_ALPHA`/paths to M07 and `docs/v02-rc-record.md`) → commit
`evidence/M07/<C>/rc/` + `tools/` (`.py.txt`); `docs/v02-rc-record.md` (alpha form; steps 9, 12 not passed);
`release/rc-trees/<C>.json` (`v0_2_gate.py --rc C --write-tree-record`); records commit after C (no journey file),
gate, push. Q1 and Q2 decide whether C must be re-cut.
J60 [coverage] Step 14 attempt 3 (`run_step14.sh`; `tests/test_m03_reference.py` dropped from `step14-tests` and from
`m07_rc_external.py`'s command string: it needs `mpmath`, the project env's, where `m03_reference.py --check` exit 0):
`m03_nlp_check.sh` 186 passed, 1 skipped, both inventory `--check` PASS; all-tier tests **640 passed, 2 skipped** (both
"Pyomo is installed"); `REPLAY PASS REAL differences=0`; `record-step14` **w24-nlp-trf: PASS** (4/4; `rc-step14.json`
ea1a64ef…). Attempt-2 logs kept in `~/.cache/of-rc-c899c85/attempt2-step14/`. RC worktree clean after.
J61 [coverage] CI records: `tools/fetch_ci.sh 39224213490` (alpha's) → RC worktree `artifacts/rc/ci/` (12 artifacts,
13 job logs). Step 1 `check`: x86-64 9883 passed, 108 skipped; aarch64 9856 passed, 105 skipped.
J62 [finding] **Q1 premise false: step 9 FAILS on CI too.** `rc-steps-*/a30.log` on both runners is the one line
`a30 exit status 1`; the job logs show `the project workload failed: … studies/nlp/greybox.py, line 60 … import cyipopt
… ModuleNotFoundError` on both. `rc-steps` concludes success because `ci.yml:812-821` runs A30 under `set +e` and
logs its exit status without raising (the T08 design: "a FAIL there is a licence reading … recorded, not hidden");
no `a30/` summary was written. Same cause, same environment class (requirements.lock + `pip install -e .`, no `nlp`
extra) in both places.
J63 [finding] Q1 facts. The workload (`scripts/p03_binary_inventory.py:892-906`, unchanged since 5a35019) imports every
module `pkgutil.walk_packages` yields (182 at C) and stops at the first failure. In the project env three fail:
`studies.nlp.greybox` (cyipopt), `studies.trust_region.projection` and `.trf` (pyomo) — M03's and M05's optional `nlp`
extra (`pyproject.toml:50-57`; ADR 0032 D5); CI hides the M05 two behind the first. cyipopt/pyomo are importable in
neither CI nor the RC venv. Alpha trees (cc73219, e0e198e, 6fec822) have no `studies/` modules, so the alpha passed.
Scope as written: T08.A30 "over every compiled distribution of the default install and the `server` extra" (T08
release spec l.478); MR-12 (alpha spec l.215): "the default install and `server` (unchanged); and every extra that `C_α`
declares and `v0.1.1` did not, through its own [A10] audit and Frank's recorded licence decision (M03's:
`docs/m03-ipopt-audit.md` and M03 N1)"; M07a.A38 (l.865): "T08.A30 at `C_α` on both architectures, with zero
undispositioned objects in a required closure; MR-12's rule for every extra new since `v0.1.1`". The measured
workload's "import every openflowsheet module" therefore reaches modules whose closure MR-12 assigns to the `nlp` audit.
J64 [finding] Q2 facts. No copy of `g11-exp.json` (afa7325a…) or `g11-coverage-v3.runs.json` (0656f617…): a SHA-256
scan of every `*.json` > 1 KiB under `~/Codes`, `~/.cache`, the session scratch found neither; no commit in
`git log --all` adds them; the alpha RC runs' artifacts (38667458248, 38772065394, 38813135468 and the identity runs)
hold none (`ci.yml` never references them; step 12 is local). Provenance: D78 = an **uncommitted** experiment patch
(`child-experiment.patch` 65426a9f…, also lost) on 1328da0's child, runner 8fe0ea58…, variant `…-v3-experiment`
97fc6ef9… (M02 log D78). The runs file = `g11_coverage_v3.py` at `bd446ab` (WO-12a′; 2 runs, 589 s + 608 s, pool 12),
which itself requires `--d78`. Neither is byte-reproducible: every point carries `wall_s`, `solve_s`, `startup_s` (the
three alpha RC runs files differ: a5154500…, 3beb52bb…, ba60c066…). At C, `--previous-runs` is optional (falls back to
`--previous`'s run-1 points, `stage_steps_from: points`); `--d78` is required and read for `stage`, `stage_steps.S1`
and `variant`. Not re-taken: the D78 record needs the lost patch, the runs file needs the D78 record.
J65 [coverage] Step 1 skip lines (R-376): `~/.cache/of-rc-c899c85/tools/step1_skips.sh` → `ci-x86-64.txt` 70 lines,
108 skips, 867ba7dc7ff9c899d1fe1eaca53fd1e06e44839e00b26553cdb25ba6f715c973; `ci-aarch64.txt` 71 lines, 105 skips,
338d361d6777584b53e1d14a2ff05f86d440b607fa4d0403115699fd95e460a2 (sums of `[n]` equal pytest's counts), held in
`~/.cache/of-rc-c899c85/step1-skips/` until the records commit (destination `evidence/M07/<C>/step1-skips/`).
J66 [coverage] Gate at 0335573 + J60–J65 (docs only): 9956 passed, 35 skipped, 192 deselected (38:48).
