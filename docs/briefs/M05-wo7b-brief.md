# M05 WO-7b brief — the study record schema rulings S12–S16, S18 (design note §18.4, R-329)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05`, branch `wp/M05` (head `442eed1`). Build lane,
bounded work order. Read first: `docs/design/M05-trust-region.md` §18.4 (`sed -n '1511,1523p'`), §9.1 and §8.3
(`grep -n '^### 9.1\|^### 8.3'`), and `docs/design/M05-build-decisions.md` sections WO-7 (S11–S18) and WO-6b
(S32–S36). Files: `schemas/trust-region-study.schema.json`, `tests/test_m05_study_record.py`, and only if a
producer field is missing, `src/openflowsheet/studies/trust_region/study.py` (`StudyResult.as_document`,
`TrfStageRunner.__call__`'s run document).

## Deliverables (each is an acceptance item of §18.4)

1. **S14, closed objects.** Every fixed-field object in the schema gets `"additionalProperties": false` and
   declares every field the producer writes at this head (read `as_document` methods in `study.py`, `checks.py`
   (`CandidateCheck`, `CheckResult`, `ParentSolve`, `PollPoint`, `NoiseFloor`), `holders.py` (`EFHolder.summary`:
   counts, `by_purpose` with its six keys, `pmp_point_equals_start`), `trf_state.py` (`IterationRecord`), `trf.py`
   (final/basis documents)). Id-keyed maps (decision ids, holder names, module names) constrain only their values
   (`additionalProperties: <schema>`). Required on every `runs[]` entry: `exit_claim`, `theta_logged`,
   `theta_recheck`, `final_state_is_last_truth_point` (each nullable: null when TRF raised, W4). Top-level `fd_check`
   (object or null) and P2's `judged`/`reason` are already declared and required (WO-6b) — keep them.
2. **S12.** `runs[].ledger` is `{summary, cold_parent}`, both required, closed; no `sha256`. `artifacts.ledger` is
   required, `^[0-9a-f]{64}$`. The test fixtures' `_document` must then pass `artifacts={"ledger": <64 hex>}`.
3. **S13.** Top-level `readiness`, `start`, `stage_a`, `best` required, each object or null.
4. **S15.** `candidates[].indifference_halfwidth` is null or an object of number-or-null values. The producer already
   writes null iff P5 did not run. "Keyed by exactly the decision ids" and "null iff P5 did not run" go into
   `status_violations` (or a sibling checker) in the test file, not the schema. Values: **use `minimum: 0`**, not
   `exclusiveMinimum` (build log S36 is open: a zero-noise parent gives exactly 0.0); note it in the log entry.
5. **S16 / G12.** A checker `request_identity_violations(record)` in `tests/test_m05_study_record.py` applying §8.3's
   identity, as integer equalities, to each run whose ledger summary has a holder with an FD truth (decide FD-truth
   detection from the run document's `truth` list / holder summary — if the record cannot tell, STOP and report):
   `trf_start_value` = 1; `trf_pmp_value` = 1, or 0 with `pmp_point_equals_start`; `trf_trial_value` = K (logged
   iterations ≥ 1); `basis_fd_point` = n_in; `trf_fd_point` = n_in·(1 + A − [final logged iteration accepted]),
   n_in = 7, A = accepted steps (see `trf_state.accepted_steps`). Run it over `COMMITTED_RECORDS` (none exist yet;
   the parametrization must still be there) and test it on two synthetic records: one that holds, one that breaks
   each equality. Known issue S33 (open): live runs currently attribute basis requests to no run; do not fix it.
6. **S18.** `artifacts.coupled_runs[].sha256` required, non-null, `^[0-9a-f]{64}$` (the producer now omits solves
   without a coupling record). A fake parent without an external unit gives no entry: add a test.
7. **Mutation tests.** Extend the existing `test_the_schema_rejects` / `_mutated` tables: a record with
   `runs[].ledger.sha256`, without `artifacts.ledger`, missing any of `readiness`/`start`/`stage_a`/`best`, or with an
   undeclared field at any nesting level (one case per closed object) fails. Every generated record validates.
8. Log decisions as S37+ in `docs/design/M05-build-decisions.md` under a new `## WO-7b` heading, with the measured
   test counts.

## Forbidden to decide (stop and report instead)

- Any change to a producer value, number or check logic (WO-6b is done). Adding a missing *declaration* is fine;
  changing what `study.py` writes is not, except adding `artifacts.ledger` passthrough if `as_document` drops it.
- Relaxing a check or removing a case to make a record validate. If a generated record cannot satisfy a ruling,
  stop and report which field and why.
- The S33/S36 questions.

## Gate and commit

Targeted: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest -q -p no:cacheprovider
tests/test_m05_study_record.py tests/test_m05_study_loop.py > <log> 2>&1; tail -1 <log>`. Then ruff (`ruff check`,
`ruff format --check`) and `mypy` from `/home/frankp/Codes/OpenFlowsheet/.venv/bin`. Do not run the full gate (the
caller does). Commit with message `M05 WO-7b: …` staging named paths only, trailer:

    Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv

Do not push. Report ≤ 25 lines: commit, test counts, decisions, anything you stopped on.
