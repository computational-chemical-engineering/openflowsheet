# C7 — build decisions (post-0.2.0 dev version, R-460)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`

- Tag source: `git rev-list -n1 v0.2.0` in this worktree gives `5c82b4cc40dd4fefd3dbce45352910006e5dee13` (the local
  tag; equals `5c82b4c` in `docs/V02_STATE.md` and `TAG_0_2_0` in `tests/test_m07a_harvest.py`).
- Negative control (step 1): with `"0.2.0"` in `RELEASED` and the version still `0.2.0`,
  `tests/test_v02_main_version.py` gives 1 failed, 2 passed — AM-40 fails: `tree_differences(5c82b4c, HEAD)` has 11
  D2.4 paths (`benchmarks/m06/openidaes450/split.json`, `benchmarks/t08/support_envelope.yaml`, 9 under
  `src/openflowsheet/`).
- DECISION: the version label on `main` after 0.2.0 → `0.3.0.dev0` (v0.3 is in progress; PEP 440 sorts it after
  0.2.0). Alternative: `0.2.1.dev0`. Reversible by: reverting the version commit and re-taking W27's coverage. The
  label is Frank's to change (R-460, rulings Q3).
- DECISION: the working envelope after 0.2.0 → `v0.2-envelope-dev` / `release: 0.2.0.dev0`, unchanged from R-193.
  It is the registered form: R-460 / MR-3, the envelope's own header, `t08_support_matrix.py:61-65` ("the first D2.4
  change after the tag returns it to `v0.2-envelope-dev`"), `WORKING_ENVELOPE` in `tests/test_v02_main_version.py`,
  and M07a.A10 (`tests/test_m07a_v0_2_gate.py:1030`), whose edit R-475 pins to exactly two pairs under A31 (b), so a
  new id would need a ruling. R-460 also rejects a dev label equal to the package version. Alternative:
  `v0.3-envelope-dev` / `0.3.0.dev0`. Reversible by: the ruling below, then editing the envelope, `ENVELOPE_ID`,
  `WORKING_ENVELOPE` and A10's pairs together.
- QUESTION: is v0.3's working envelope a new id (`v0.3-envelope-dev`, `release: 0.3.0.dev0`, an R-193 analogue for
  v0.3) or does R-193's `v0.2-envelope-dev` / `0.2.0.dev0` stay the working form until v0.3's cut? The latter is
  what the code and tests now require. A new id touches R-193's scope, `WORKING_ENVELOPE`, and A10's frozen edit (R-475,
  A31 (b)). Default applied: keep `v0.2-envelope-dev`.
- Re-take W27 (R-460 "re-take W27's coverage"), needed: at `954fde3`
  `test_committed_coverage_json_is_g14_and_this_builds_classification` fails (`package_version` `0.3.0.dev0` !=
  committed `0.2.0`). `python -m benchmarks.m06.w27.coverage` then `python -m benchmarks.m06.w27.report` at
  `954fde3` (committed `case_facts.json`; no archive needed): only `snapshot.git_commit` (`48db2d3` → `954fde3`),
  `snapshot.package_version` and `snapshot_sha256` (`211cf4f1…` → `5e36f8ef…`) move; rows, summary and
  `list_models_sha256` `f070fbe0…` unchanged; G14 PASS (450/450 rows). As `4b909af` did after E7.
- BLOCKED (nlp environment): the G10 re-take (R-458; rulings E6/O5). The five in-process G10 records under
  `benchmarks/m05/records/` embed `openflowsheet==0.2.0` in their experiment fingerprints, so `-m nlp
  tests/test_m05_g10_replay.py` (5 tests; deselected by default, not run here) is expected to fail on digests at
  `0.3.0.dev0`. This session has no `.venv-nlp`. Workstation step: in `.venv-nlp`, `OMP_NUM_THREADS=1`, re-run
  TR-E2, TR-E2-FAR, TR-E2-FD, LOOP-R, LOOP-S at `f85fcd7` or later; prove with
  `scripts/m05_retake_diff.py --digest-only --old-version 0.2.0` (expected counts as E6/K: `version=` 4/7/4/3/4,
  changed digests 41/79/70/91/37); then AM-23 (5 passed) and an M05 build-log S-entry.
- BLOCKED (reactor environment): rulings Q1, `scripts/m05_wo9_real.py --replay` at the new version (about 25 min).
  By code reading it does not move with the version (F4); not measured here.
- QUESTION: at `0.3.0.dev0`, R-476's predicate makes the four ledger tests in `tests/test_m07_ledger.py` skip ("not
  one v0.2-gate-v1 covers"). At `0.2.0` they ran. Rulings O1 says that after 0.2.0 is released the ledger "is scoped
  to its tag commit, as R-456 does here". That scoping is not in C7's brief and is not done. Default: leave it to a
  follow-up package (M07 owner), with the skips counted as skips, not passes.
- DONE (WS1 item 1, `5a6b811`): the G10 re-take at `0.3.0.dev0` from the clean tree at `15c0413` (alpha-main's
  `.venv-nlp`, OMP 1). `--digest-only --old-version 0.2.0`: PASS ×5, `version=` 4/7/4/3/4, changed digests
  41/79/70/91/37, other=0, environment equal (the expected counts exactly). AM-23 (`-m nlp
  tests/test_m05_g10_replay.py`): 5 passed. Records tests (m05 replay/basis/wo8/wo9/study record, m07 journey): 369 passed.
- DONE (WS1 item 2, rulings Q1): `scripts/m05_wo9_real.py --replay` at `5a6b811` (`0.3.0.dev0`, clean tree,
  alpha-main's `.venv-nlp`, OMP 1): `REPLAY PASS REAL differences=0`, exit 0. Confirms F4 (REAL's fingerprint carries no
  version) by measurement.
- DONE (WS1 item 3, ADR 0044 condition (4) and Frank's condition; numbers in the ADR's status paragraph). Method: a
  `sitecustomize.py` on `PYTHONPATH` installs a meta-path hook that wraps `orchestrator.recovery.eo_recovery_due` in
  every process; `ADR44_LOG` logs each `LINEAR_SOLVE_FAILED` call (`PYTEST_CURRENT_TEST`, attempts, value);
  `ADR44_MODE=old` returns ADR 0010 D3's `False`. Full suite in both modes (29 + 30 min) and `-m "nlp or pymrm"` in
  `.venv-nlp`. Static scan: every tracked JSON/JSONL, every `LINEAR_SOLVE_FAILED` value with its enclosing `attempts`.
- DECISION: what "registered step records" scans → every tracked JSON/JSONL record (static) plus every
  `eo_recovery_due` call the registered tests make while replaying them (dynamic). Alternative: only campaign step
  records. Reversible by: re-scanning a narrower set; the counts can only fall.
- DECISION: ADR 0044 stays Proposed in this commit; (3) needs the merge gate and CI recorded in C2. Alternative: flip
  now. Reversible by: the flip after the merge gate.
- NOTE: the `pymrm` tier's `tests/test_m02_pymrm_env.py::test_the_environment_verifies_against_its_pins` fails in
  alpha-main's `.venv-nlp` (package list differs from the pins); not ADR 0044 (no `LINEAR_SOLVE_FAILED` call in that
  tier) and not a WS1 item. The M07a A50 harvest test fails while the real W27 archive copy sits in the worktree.
- BLOCKED (WS1 item 4, design lane; parked on branch `wp/WS1-f1` @ `7b5c07f`, reverted here). `case_facts-v2.json`
  was written (450 cases, 3,725 topology units, sha256 `57d43acb…`, kind sets equal to v1's `topology_kinds`; v1
  `facts --check` and split `--check` byte-identical) by a `facts-v2` stage added to the W27 generator. The full gate
  at `6c2364e` then failed 2 registered assertions, both caused by it: (1) SPLIT-A09 (`tests/test_c2_openidaes450_split.py:176`)
  — v2 names every held-out case id and is not in `c2_openidaes450_split.ALL_CASE_FILES`; (2) W27 P2
  (`tests/test_m06_w27_harness.py:314`) — the generator's SHA-256 is pinned (`preflight.REGISTERED_SHA256`). Fixing
  either is a registration change (A09's allowlist; the writer's location or a W27 re-pin), not done by the build
  lane. Needed from the design lane: an amendment naming v2's writer and adding v2 to A09's allowlist; then
  `wp/WS1-f1` is re-applied (or re-done) and `f1/status` moved as the amendment says.
