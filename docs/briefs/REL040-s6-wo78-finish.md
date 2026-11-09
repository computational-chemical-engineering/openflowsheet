# Engineer brief: finish S-6 confirmation work — S6R-29 and WO-7's live proof line (wp/REL040p)

Status: brief, 2026-11-09. Build lane. **Do not spawn sub-agents yourself.** No tag, no release, no K3.

## State

The previous engineer (brief `docs/briefs/REL040-s6-wo78.md`, read it) was cut off by a TRS2 reset after pushing
WO-8 `d7258775`, WO-7 `26ad9d7f` and A-11 item 7 `0b62c12d` (`wp/REL040p` head `0b62c12d`). Not done: **S6R-29**
(ruling §11.4, `git show origin/main:docs/reviews/REL040-s6-ruling.md`) and **WO-7's live proof line** (§11.3: the
digest-only proof on the fresh re-take must print `path=128 version=0 platform=4 other=0 environment=equal`, as
before), and their log entries in `docs/RP_DECISIONS.md` (none yet for WO-8/WO-7/item 7 either — check, add if missing).
Its scratch worktrees were pruned; rebuild what you need. Re-take outputs:
`/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/fd59d98d-797a-4da8-93d6-9c61c6d4bdc7/scratchpad/wo6-fresh/`.

## Do

1. WO-7 live proof line on the fresh re-take; record it.
2. S6R-29 at a scratch J′ = head + both re-takes (never pushed), exactly as §11.4 names; record the result and O-6's
   answer (§11.7). If a host-bound test turns up: stop and report it (no fix without the design lane).
3. Log everything in `docs/RP_DECISIONS.md`; commit (named paths, message naming REL040); push `wp/REL040p`. Remove the
   scratch worktree and branch; `git status` clean.

## Machine (TRS2 reset twice under load)

`uptime` first and before each heavy run. Keep the whole machine at or below ~36 busy threads; **at most ~12 cores for
your runs** (a default-tier run serial or with at most `-n 8`); never pytest/mypy in several worktrees at once (another
agent runs targeted tests in the x04 worktree). If TRS2 resets, the orchestrator tells hub.

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rel040p`; `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python`
with `PYTHONPATH=src`; nlp env as in `docs/RP_DECISIONS.md` § S-6; `OMP_NUM_THREADS=1`. Trailers `Co-Authored-By:
Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`.
Cap ~150k context. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`,
`~/.cache/seider4/`; never copy the V17 login token (R-116).

## Report (at most 15 lines)

WO-7 proof line; S6R-29 result and O-6 answer; commits; anything stopped on.
