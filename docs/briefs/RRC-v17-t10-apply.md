# Build brief: apply the V17-T10 ruling on `wp/RRC`

Status: brief, 2026-11-09. **Do not spawn sub-agents yourself.** Ruling `docs/reviews/RRC-v17-t10.md` (main `a109eea6`):
apply its edits E0–E8 verbatim on `wp/RRC` (worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rrc`, head
`fcba6656`; CI run 42547017088 red only on `test_g16b_reference_run[V17-T10-*]`). Q1/Q2 take the ruling's defaults.

- Run A1 (generator `--check` on the unedited branch) first; if the `f946a88f…` pin does not regenerate, stop and report.
- Then E0–E8 (new `t07_reference_rrc.json` via `--emit-rrc`, Amendment RRC-1 verbatim, `scorer.py`
  `CARRIED_SURFACE_REFERENCE_PATH`, the new positive/negative test, docstrings, register **R-996**, log **D-46** with the
  new file's sha). Check A1–A9; any stated value that does not come out → stop and report, do not adjust.
- Worktrees have no `.venv`: `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with `PYTHONPATH=src`; confirm
  `openflowsheet.__file__` is the worktree's copy. Serial tests (no xdist), `OMP_NUM_THREADS=1`. Also run
  `tests/test_rrc_*.py` and `scripts/corpus_identity.py --check`; `ruff check`, `ruff format --check`, mypy.
- Commits named paths only, messages `RRC: …`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/RRC`. No merge, no manifest.

TRS2 shared: `uptime` first. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`,
`~/.cache/seider4/`. Report ≤ 15 lines: commits, A1–A9 measured, new file sha, tests, F0.
