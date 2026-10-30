# V03 RC decisions (WO-5, brief `docs/briefs/V03-WO5-K3.md`)

Build-lane choices made while executing WO-5, one line each, with what reverts them.

- DECISION: K3 also sets `scripts/t08_support_matrix.ENVELOPE_ID` and re-emits `docs/support-matrix.md` (both outside
  D2.4) → yes, as 0.2.0's A = `0fcf1ad` did; without them `t08_support_matrix.py --check` fails on the envelope id.
  Alternative: leave them for a later commit. Reversible by: revert of K3 `295a2e65`.
- DECISION: the `assessment_report` fixtures that carry `0.3.0.dev0` are left as they are → they are not in §5.1's
  set (nor in 0.2.0's), and no test reads them as the package version. Alternative: bump them too.

## Stop at K3 (§10.1, F-4) — resolved by R-902

The first K3 (`ad4c23db`, discarded, never pushed) failed
`tests/test_m06_w27_coverage.py::test_committed_coverage_json_is_g14_and_this_builds_classification`: it compared
every snapshot field but `git_commit`, so `package_version` `0.3.0` != the committed `0.3.0.dev0`, and the v1 re-take
refuses (`registry_snapshot: unsupported(provider 'iapws95-v1': no registered records and phases, W27-R63)`).
Orchestrator ruling: `package_version` is build provenance and is excluded beside `git_commit` (R-902, rejected:
base-version comparison). Fix commit `91d1cc54` on 4a664416 (W27 tests at 0.3.0.dev0: 56 passed, 2 skipped), then K3.

## Step 2: the G10 re-take (`2d945b5d`)

From a clean detached worktree at K3 (`.claude/worktrees/rc-k3-295a2e6`), E6/K's recipe (alpha-main's `.venv-nlp`,
OMP 1, `PYTHONNOUSERSITE=1`, `PYTHONPATH=src:<nlp-test-tools>`): `--digest-only --old-version 0.3.0.dev0` PASS for all
five, changed digests / version leaves 41/4, 79/7, 70/4, 91/3, 37/4, `other=0`, `environment=equal`; AM-23 5 passed.

- FINDING: `benchmarks/m05/records/**` is a D2.4 path (`v0_1_gate.TREES` holds `benchmarks`), so the brief's "one
  commit (outside D2.4)" is not literally true; the commit changes nothing outside `benchmarks/m05/records/` (36 files).
  0.2.0 put the records inside K (`2c508b5` = A + records); here they follow K3 by the orchestrator's order.
- DECISION: the journey runs at `2d945b5d` (K3 + the G10 records), not at K3 itself → `carry.journey_files` holds
  `benchmarks/m05/**`, so a journey recorded at K3 cannot carry to C (`git diff --name-only K3 2d945b5d -- <carry
  paths>`: 36 files; `v0_2_gate.journey_carry` would answer `JOURNEY_RERUN`). This is 0.2.0's K exactly (A + the G10
  records). Alternative: run at K3 and re-run at C. Reversible by: re-running at K3 (one hour of compute); the carry
  argument at C is then `--carry-journey 2d945b5d`.

## Step 3: the journey (`93886ac3`)

Clean detached worktree at `2d945b5d`, m05's `.venv-nlp`, OMP 1, `PYTHONNOUSERSITE=1`, `PYTHONPATH=src`,
`--m05-record benchmarks/m05/records/trust-region-study-real.json`, artifacts in `~/.cache/v03rc-journey/artifacts`;
budgets unchanged. Exit 0, 3304 s. Decision `refined`, T* = 653.1500351610193 K, BOUND_LOWER, J = 0.4524965242483627;
R0 INDIFFERENT, R1 DECIDED 653.15 K (cold 36, 1554 s), R2 SURROGATE_NOT_PROMOTABLE, R3 DECISION_STABLE.
- R3: M05's REAL record is **not** carried (`carry_identity_differs` from anchor `cdacc32`); M05's study re-ran at
  `2d945b5d` (cold 48, 1455 s; T* 653.1500351610193).
- Against 0.2.0's K record (`2c508b5`): 69 leaves differ, all walls, coupling/run digests, `commit` and R3's
  `m05_record` {path, sha256}; every other number bitwise equal (K's comparison with J′ had 70: it also held
  `registration_sha256`, unchanged here). No stop: nothing differs for a reason other than the code changes.
- `check` ACCEPT; `replay` at `93886ac3` (clean worktree): bitwise, 19 s; `OMP_NUM_THREADS=2` exit 2.
  `tests/test_m07_journey_record.py`: 56 passed. `v0_2_gate.journey_carry(2d945b5d, 93886ac3)`: carried; from K3 it
  would not carry (36 files of `benchmarks/m05/**`).

## Handoff

- Branch `wp/V03-rc` (not pushed): fix `91d1cc54`, K3 `295a2e65` (on `main`), log, G10 re-take `2d945b5d`, journey
  record `93886ac3` (J = `2d945b5d`), this log.
- WO-5 steps 1–3 done. At C the RC job carries the journey with `--carry-journey 2d945b5d --rc C` (not K3).
- Not done: C itself (WO-6's RC job). Scratch: `~/.cache/v03rc-tmp`, `~/.cache/v03rc-journey`, `~/.cache/v03rc-tools`.
