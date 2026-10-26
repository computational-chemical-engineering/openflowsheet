# S09 brief: WO-S09-2, blind qualification of BioSTEAM (build lane, fresh agent)

Branch `wp/S09`, worktree `.claude/worktrees/s09`, head `e244bac4`.

**Second attempt (WO-S09-2b).** A first agent built the harness (`080290c8`) and stopped before the recorded run on a
registered string that contradicted the tool. Amendment 1 (spec §18, R-748…R-750) ruled; §18.6 lists the harness
changes required before the recorded run: B2 on R3 (fsolve `nfev`), the L2(c) rerun as one evaluation at the final x
(`floor_rerun.ytol_factor` removed), the closed list of margin rows, and 19 records. Make those changes, re-run the
tool-free tests, then make the recorded run. The environment `.venv-biosteam/` in this worktree
was built by WO-S09-1 (`scripts/build-reference-envs.sh biosteam`; fingerprint in `docs/reference-environments.md` §9).

## Your task

Do **WO-S09-2** exactly as `docs/derivations/S09-spec.md` §14 (the WO-S09-2 entry) states, with the rules of §9.2 and
S03 §12 that the spec carries over. The spec is the authority for everything you build: §2 (levels, the order, the
inspection), §4 (the property mapping: §4.2, §4.3), §5 (path, ladder, the L2(c) loop), §6 (rule values computed from the
tool's own record), §10 (record fields), A03, A06–A08, A16, A17.

## What you may read

- `docs/derivations/S09-spec.md`, `docs/derivations/scripts/s09_cases.json` (and `s09_reference.py`, which writes it),
  `benchmarks/s03/` **case inputs only** (`s03_cases.json`), `docs/derivations/scripts/s09_design/`, the tool's own
  source and documentation in `.venv-biosteam/`, `docs/S09_BUILD_DECISIONS.md`, and S03's harnesses
  `spikes/references/s03_qualify_{idaes,dwsim}.py` for structure only.

## What you must not open (blindness, §9.2)

- `docs/derivations/scripts/s09_spike/`, `docs/briefs/S09-third-reference-tool.md`;
- `benchmarks/s03/references/results/`, `benchmarks/s03/references/comparison.json`, `docs/derivations/scripts/s03_reference.json`
  or any twin or reference value, `benchmarks/s09/` before your own run writes it;
- any value of this project's column results.

If a file you need is not on the "may read" list, stop and report rather than open it.

## Rules

- Nothing scientific is chosen on the build lane. A measurement that contradicts the spec (a floor above §6.6's
  thresholds, a hook that behaves otherwise, a realization that cannot be built) stops the work order **before the
  recorded run**; report it. The harness is never bent to make a case pass; a case the tool cannot express is
  `NOT_COMPARABLE(capability: <what>)`.
- Log build choices as DECISION lines (with alternative and reversal) and measurements as MEASURED lines in
  `docs/S09_BUILD_DECISIONS.md`.
- Commit the qualification records before any classifier work (A16). Run the tool-free tests (A03, A06–A08), `ruff check
  .`, `ruff format --check .`.
- Stage named paths (never `git add -A`). Commit messages name S09 WO-S09-2 and end with:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Do not push.
- Context cap about 150k: commit what is complete, note where you stopped in the build-decisions file, end.

## Report

At most 15 lines: commits; per case the level reached or the `NOT_COMPARABLE` reason; whether the two runs were
identical (A17); anything stopped or escalated. Do not report any value compared with a reference — you have none.
