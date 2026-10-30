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

## Handoff

- Branch `wp/V03-rc`, worktree `.claude/worktrees/v03rc`, from `main` 4a664416: fix `91d1cc54`, K3 `295a2e65`.
- K3 tests (17 modules: A10 / M07a gate, M07 gate, `test_v03*`, W27 coverage, project_summary schema tests,
  main-version, package imports, T08 gate/surface/envelope, retake digest-only): 806 passed, 2 skipped, 0 failed.
  `t08_support_matrix.py --check`: 0 problems.
- Next: the orchestrator fast-forwards `main` to K3 and sends the go for step 2 (G10 re-take at K3) and step 3
  (journey at K3).
