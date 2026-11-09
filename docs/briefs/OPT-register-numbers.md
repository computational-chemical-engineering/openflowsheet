# Implementer brief: OPT — number and enter ADR 0071's ten register drafts (D-91 ruling)

Status: brief, 2026-11-09. Bounded docs item. **Do not spawn sub-agents yourself.**

Orchestrator ruling on OPT D-91 (2026-11-09): option (1). ADR 0071's ten drafts (§ "Register entries (drafts,
unnumbered)", `docs/adr/0071*.md` ~line 162) take **R-961…R-969 in ADR order**, and the **tenth** (the R-860 lifts)
takes **R-988** (verified unused on main, wp/OPT, wp/RRC and wp/ST). Do not reorder, merge or reword the drafts.

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/opt`, branch `wp/OPT`, head `a1963353`.

## Do

1. In `docs/decision-register.md`, add the ten entries after R-960, in the form of X02's R-951…R-955 entries on the
   same file (heading `## R-9xx — <title> (2026-11-08)`, the same table rows, "Decided by" Frank on the decision board
   2026-11-08 with ADR 0071 Accepted). Keep the draft text; only number it. R-988 goes in numeric order in the file
   (after R-987 if present, else where numeric order puts it), and its body notes it is OPT's tenth draft, numbered
   outside the block because R-961…R-969 hold nine (D-91).
2. In ADR 0071: status-line lines 7–8 now name the numbers (R-960 surface link; R-961…R-969 and R-988), and the
   drafts section heading drops "unnumbered" with each draft labelled with its number.
3. Replace any "unnumbered"/"to be numbered" mention of these drafts in `docs/OPT_DECISIONS.md` (append a D-94 entry:
   "D-91 resolved by the orchestrator: option (1)…") and `docs/OPT_HANDOFF.md`; grep the worktree for `R-96[1-9]` and
   "unnumbered" to catch other texts (OPT guide, design note, briefs).
4. If a committed generator or check covers the register (grep `scripts/` for `decision-register`), run its
   `--check`; also `PYTHONPATH=src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest -q
   tests/test_evidence_manifests.py` and any test that greps the register (grep `tests/` for `decision-register`).
5. One commit, named paths, message `OPT: ADR 0071's register drafts numbered R-961…R-969, R-988 (D-91, D-94)`,
   trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
   https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/OPT`. No merge, no manifest.

If a draft's text is ambiguous about where it ends, or the register has a format the X02 entries do not show, stop
and report. TRS2 shared: `uptime` first. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`.

Report ≤ 10 lines: commit sha, the ten number→title pairs, checks run.
