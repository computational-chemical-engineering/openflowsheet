# V02 — the release-candidate record at `C`

*`C` here is the re-cut candidate `C′` (M07 spec Amendment 7 §24.6, R-484). The superseded candidate `c899c85` has
no RC record; its account is `docs/design/M07-build-decisions.md` J56–J66 and its small-text records are kept under
`evidence/M07/c899c85ab43fb114cd85c69baf12e692b75a8eab/rc/` (RC.3).*

M07 spec §8 and §24.7 action 7 (WO-8c), in the V02 alpha release spec §8.3's form (`docs/t08-rc-record.md`'s). This
record **reports**; it judges no gate. Each Result cell states what the step's record or CI job says, in the closed
vocabulary `scripts/v0_2_gate.py` reads through `v0_1_gate.py`'s grammar (Ruling 3: `PASS` / `success`; `FAIL` /
`failure` / `skipped` / not measured); the verdicts are the design lane's. Every record the per-step table cites is
committed under `evidence/M07/ce993651ce37c1343e771b276160bd6623e43500/rc/` at the same relative path (a record over
1 MB gzip-compressed beside it), and `rc/records.json` lists all @N@ with sha256, size and how each is kept (the two
ensemble run files and step 17's three carry and coverage documents gzip-compressed). The scripts that ran the local
steps are committed beside them, under `evidence/M07/ce993651ce37c1343e771b276160bd6623e43500/tools/` (byte-identical
to what ran; the Python ones with a `.txt` suffix so that the linters of `check.sh` do not read them).

## The candidate and the runs

- **`C` = `ce993651ce37c1343e771b276160bd6623e43500`** (`C′`, "M07 (WO-8c, action 6, C′): build log J67-J72 —
  Amendment 7 actions 1-5 done; this commit is the re-cut C′"). Package `openflowsheet` `0.2.0`. RC.1: `c899c85` is
  its ancestor, and `git diff --name-only c899c85 C′ -- src benchmarks schemas requirements.lock pyproject.toml` is
  empty; the journey's cut commit K = `2c508b5` stays (§24.6). Its tree record is
  `release/rc-trees/ce993651ce37c1343e771b276160bd6623e43500.json` (M07a.A44).
- **CI dispatch run 39291243747** (`workflow_dispatch`, `rc_alpha=true`, `rc_distribution=true`, head `C`, ref
  `wp/M07-rc-ce99365`): conclusion **success**. **CI push runs** at `C`: 39276061202 (`wp/M07`) and 39291243653
  (`wp/M07-rc-ce99365`), both **success**.
- **Local steps** on `ref-x86-64` (AMD Ryzen Threadripper PRO 5965WX, Linux 6.12.111+deb13-amd64, Python 3.13.5),
  run 2026-10-19 19:06 to 20:40 from a detached worktree at `C` (`.claude/worktrees/rc-ce99365`, clean throughout:
  `git status --porcelain` empty at the start, after the venv, after the W27 archive's hard links and at the end) in
  a fresh venv of `requirements.lock` with the worktree installed editable (`--no-deps`); threads pinned
  (`OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`). Steps 2 and 6–17 ran in one session from one script,
  `tools/run_local.sh` (WO-8b's at `c899c85`, with two changes: step 12's G11 takes `--d78` from the registered
  extract and no `--previous-runs`, §24.3 action 2; step 14 is `tools/run_step14.sh`), with every environment built
  afresh and logs under `~/.cache/of-rc-ce99365/`; its one-line-per-command summary is `tools/run_local.summary.txt`
  (50 commands, every exit 0) and the durations in seconds `tools/durations.txt`. `tools/fetch_ci.sh` downloaded the
  dispatch run's artifacts and job logs; `tools/collect.sh` copied the cited records here and
  `tools/make_record.py.txt` wrote this table's hashes from `rc/records.json`.
- **Step 12** ran in the reactor environment built from `C`'s `src/openflowsheet/adapters/pymrm/reactor-env.lock`
  (`build`, then `verify`: verified) under an external root outside every repository; the G12 runs through
  `tools/g12keep.py.txt`, which keeps the script's scratch directories so that step 10 can audit their certificates
  (R-348). The five kept `solution-certificate.json` files are committed under
  `rc/step12/certificates/<kept bundle path>/`. G11 took 2988 s. The host may have been shared with other sessions'
  work; G11v3's timings are recorded under whatever load there was.
- **Step 14** ran in a second clean detached worktree at `C` (`~/.cache/of-rc-ce99365/nlp-wt`, no install into it),
  every command under `env -i` with only the variables `scripts/m03_nlp_check.sh` and M05's manifest set
  (`OMP_NUM_THREADS=1`, `PYTHONNOUSERSITE=1`, `PYOMO_CONFIG_DIR`), in m05's audited `.venv-nlp`;
  `tests/test_m03_reference.py` is not in its test list (it needs `mpmath`, the project environment's, where
  `m03_reference.py --check` runs; J60).
- **Steps 11–17's records** `stepNN/rc-stepNN.json` are written by `tools/m07_rc_external.py.txt` through
  `t08_rc.finish` from the steps' own records, logs and exit codes.
- **Step 1's skip lines** (R-376): `evidence/M07/ce993651ce37c1343e771b276160bd6623e43500/step1-skips/ci-x86-64.txt`
  (68 lines, 106 skips) and `…/step1-skips/ci-aarch64.txt` (71 lines, 105 skips), outside `rc/`; they are not RC
  records.

### Jobs of run 39291243747

| Job | Conclusion | Step |
| --- | --- | --- |
| `check (ubuntu-latest)` | success — `check.sh: PASSED`; pytest 9911 passed, 106 skipped; the browser test required | 1, 16 |
| `check (ubuntu-24.04-arm)` | success — `check.sh: PASSED`; pytest 9882 passed, 105 skipped | 1 |
| `default-install` | success | — |
| `identity` | success — "G05: R0 structural identity equal across 2 platforms" | 2 |
| `dist` | success | 3 |
| `clean-install (ubuntu-latest)` | success | 4, 10 |
| `clean-install (ubuntu-24.04-arm)` | success | 4, 10 |
| `bundle-set` | success | 5, 10 |
| `bundle-replay (ubuntu-latest)` | success | 5 |
| `bundle-replay (ubuntu-24.04-arm)` | success | 5 |
| `rc-ensemble` (ubuntu-24.04-arm) | success | 6 |
| `rc-steps (ubuntu-latest)` | success; `a30.log` ends `a30 exit status 0` (CI.1) | 2, 7–10 |
| `rc-steps (ubuntu-24.04-arm)` | success; `a30.log` ends `a30 exit status 0` (CI.1) | 2, 7–10 |
| `ensemble`, `ptc-r1`, `ensemble-compare`, `a89-repeats`, `a30-inventory` | skipped (not RC inputs) | — |

All artifacts downloaded (`gh run download 39291243747`); the RC jobs' logs saved under `…/artifacts/rc/ci/job-logs/`
(the `check` and `identity` logs cited below).

## Per step

Paths are relative to `evidence/M07/ce993651ce37c1343e771b276160bd6623e43500/artifacts/rc/` (and, committed, to
`…/rc/`).

| Step | Assertion | Where | Result (as the record says) | Record | sha256 |
| --- | --- | --- | --- | --- | --- |
@TABLE@

**M07a.A43 (provenance).** Every `t08-rc-v1` record above (local and CI, both replay records and the records of steps
11–17 included) carries `commit` = `ce993651…`, `tree_clean = true` and `environment_lock_sha256 = ead4edf1…`;
`t08-a43-dist.json` carries the same at top level. The A30 records carry `lock_sha256` and the host, but no `commit`
or `tree_clean` (format `t08-a30-inventory-v1`); M01's and M02's records (steps 11, 12) carry neither, and are cited
through the step's `t08-rc-v1` record. Stated, not judged.

**J.1** (§24.5): at `C`, in the reactor (`nlp`) environment with `OMP_NUM_THREADS=1`,
`pytest -m pymrm tests/test_m07_journey_record.py -k a24 -rs` gives 1 passed (`2c508b5`) and 1 skipped (`974c395`:
"A24 for 974c395 is judged at its own commit; its carry to this tree does not hold (M07 §24.5, R-483)").

## Step 18

`scripts/v0_2_gate.py --rc C` (M07.A36) is run for its YES line only at a candidate where
`pytest tests/test_m07_ledger.py` gives 5 passed and 0 skipped, after the verdicts (§8, §23.2). It has not been run;
it is pending, not failed.

## Failures

None. Every record of steps 1–17 reports `PASS` or `success`.

## Observations (not failures, not judged)

- **O1** The `check` skip counts differ between the platforms (106 / 105 skipped); the skip lines are in
  `step1-skips/` (R-376). The aarch64 file is byte-identical to `c899c85`'s.
- **O2** The A30 object counts and closures (266 / 150 on x86-64, 232 / 147 on aarch64) are over the default install
  and `server` with the scoped workload (§24.1); the alpha's (381 / 150, 308 / 147) were counted at a tree without
  `studies/` modules. A30's verdict reads the closure, not these counts.
- **O3** The bundle index's three g8 entries that are not CONVERGED have the outcomes their revisions register (2
  initialization, 1 homotopy stall), each with exit 0, as at the alpha (named here, outside the per-step table,
  because the gate script reads any upper-case failure word in a Result cell as a failure).
- **O4** Step 6's class counts equal the alpha's on `ref-x86-64` (434; F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3) and on
  `ci-aarch64` (434; 4, 2).
- **O5** Step 12's G10v3 and G12 values (A42, A45, A46, A47 (b); G12's outer iterations, final k and floor ratios,
  the edges' `y_inert`) equal `cc73219`'s step-12 record exactly; the G12 check differs from it only in record paths,
  hashes and `solve_wall_s` (271.7 s here, 126.7 s there).
