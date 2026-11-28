# LINE06 X06-CI1: make wp/X06 green in CI (run 45962988409 at 1b9561a3 failed on every leg)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06`, branch `wp/X06`, head `1b9561a3` (clean, pushed). Logs
under `/home/eajfpeters/.cache/line06/x06-ci1/` only; wait on log lines. Tests: `PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH
PYTHONPATH=src`. Log every choice as `DECISION X06-CI1-<n>` in `docs/X06_DECISIONS.md`. Do not touch the f2 or f8
worktrees. Do not push. Budget about 150k.

## The facts (CI log, failed jobs only: `/home/eajfpeters/.cache/line06/ci/x06-1b9561a3-failed.log`; grep it, never read it whole)

The same 11 tests fail on all four `check` legs (ubuntu, ubuntu-arm, macOS, Windows) and in `default-install`; local
per-risk runs never ran them:
1. **sha256 partition:** `(d) unclassified sha256 names: ['actual_sha256', 'expected_sha256']` in
   `tests/test_e01_a_links.py::test_the_policy_check_passes_with_v2_unchanged`, `tests/test_f1_operations.py::test_fu_a6_*`,
   `tests/test_m04_numerical_policy.py::test_a37_*`, `tests/test_t08_adr0025.py::test_a1_*` (two). X06 added schema
   fields with these names. Note: `test_the_policy_check_passes_with_v2_unchanged` pins the v2 policy file's hash, so the
   policy file must not change. Find how earlier packages classified a new `*_sha256` name (the partition in
   `scripts/t08_numerical_policy.py`, `schema_sha256_names`; grep the decision register for the precedent) and follow it.
   If the only fix changes the numerical policy file or its digest, STOP (design lane).
2. **Literal guards:** `tests/test_t05b_literal.py::test_b06_*`, `tests/test_t06_f4_literals.py::test_wo1_*`,
   `tests/test_t06_w18_literal.py::test_w18_*`: an X06 committed fixture (`...policy_id.json`, `..._copy.json`) names a
   policy value these guards forbid in committed documents. Fix the fixture or use the guards' own documented
   exemption mechanism, per their docstrings; do not widen a guard without its precedent.
3. **Snapshot decompositions:** `tests/test_m02_schemas.py::test_g1c_*` and `tests/test_m04_study_job.py::test_a42_*`:
   `KeyError: 'list_branches'`: these strip later packages' additions to reach M02's snapshot; X06's new operations
   need the same strip (X06 has `without_x06`; follow how F3 / F1 operations were handled there).
4. **`tests/test_x06_solve_policies.py::test_q7_a_lowered_budget_run_verifies_and_reproduces`:** expects
   `('compatible_reproduction', 'MATCH')`, CI gets `('exact_replay', 'MATCH')` on every leg. Since ADR 0007 Amendment
   3 (X07a), equal identity, BLAS version and thread pins on both sides give `exact_replay`. Find why this host gives
   the other mode (thread pins? `_pin_threads`, DECISION X06-WO5-1) and make the expectation follow the rule
   (`decide_mode`'s inputs), not the host. State the cause measured.
5. **codehealth job** (`codehealth diff --base origin/main --head HEAD`, `requirements-codehealth.txt`): debt over
   touched files 59.30 -> 99.20 and six new file smells: `application/branch_service.py` duplication (nloc 202),
   `application/solve_policy_service.py` duplication (nloc 165), `application/cli.py` large_file (1008),
   `application/jobs/runner.py` large_file (1002), `application/store.py` large_file (1006). Refactor without
   behaviour change until `codehealth diff --base origin/main --head HEAD` passes locally (install it in a venv under
   your log dir from `requirements-codehealth.txt` as CI does). No served-digest or F0 move.
6. The `identity` job failed downstream of the check legs; recheck it is not independent (grep its section).

## Acceptance (judged on these alone)

Commits on wp/X06 (named paths). At the final head: **the full local gate** `scripts/gate.sh
/home/eajfpeters/.cache/line06/x06-ci1/gate.log` prints `GATE PASS` (run it in the background, wait for its line);
`codehealth diff --base origin/main --head HEAD` passes; F0 PASS (M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8
105/105, M9 42/42); no served digest moved (X06_SERVED_SHA256 `d0f0c8b7...` unchanged; a move is a STOP). No background
job of yours running when you report. Report in 200-300 words: the cause and fix per item, commits, the gate line,
the codehealth line, the F0 line.
