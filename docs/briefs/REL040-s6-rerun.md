# Engineer brief: S-6 ruling WO-6 rerun from a fresh worktree (S6R-22, S6R-24, S6R-25)

Status: brief, 2026-11-09. Build lane. **Do not spawn sub-agents yourself.** No tag, release or publish.

Context: `wp/REL040p` head `00f15a01` applied the ruling `docs/reviews/REL040-s6-ruling.md` WO-1…WO-5; WO-6 stopped at
S6R-22 (`docs/RP_DECISIONS.md`, last section; outputs in
`/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/fd59d98d-797a-4da8-93d6-9c61c6d4bdc7/scratchpad/wo6/`). The proof
printed `other=0` (no number moved) but FAIL on (1) the environment sidecar 17 → 18 distributions, caused by a
git-ignored `src/openflowsheet.egg-info` in the old worktree, and (2) the empty-file digest `e3b0c442…` mapping to two
images: one attempt (T = 673.65 K) wrote stderr, startup 19.7 s vs 1.7 s committed.

**Orchestrator decision (2026-11-09), defaults pending the design lane's confirmation:** Q-S6a keep class `path`;
Q-S6b "clean worktree" = a fresh `git worktree add` (`git status --porcelain --ignored` empty before the run);
Q-S6c the reactor child's stderr digest stays in the required identity.

## Do

1. Fresh worktree: `git worktree add /home/frankp/Codes/OpenFlowsheet/.claude/worktrees/s6fresh origin/wp/REL040p`
   (detached is fine); confirm `git status --porcelain --ignored` is empty; no `pip install -e`, no egg-info.
2. Run WO-6's REAL re-take and its proof exactly as the ruling and `docs/RP_DECISIONS.md` record them (same commands,
   same nlp env as S6dbg), outputs under the scratchpad (`…/scratchpad/wo6-fresh/`). Then S6R-24 and S6R-25 as the
   ruling states them.
3. Report the proof line verbatim. If it passes: append to `docs/RP_DECISIONS.md` on `wp/REL040p` (from the rel040p
   worktree — clean, named path) and push. If stderr recurs on any attempt: capture that stderr's content (first 40
   lines) and the attempt's T, record it, and stop — that goes to the design lane. Never adjust anything to pass.
4. Remove the `s6fresh` worktree at the end (`git worktree remove`).

TRS2 shared: `uptime` first; another engineer runs a full test suite — keep this run single-process as WO-6 did.
Trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; named paths only. Never read or touch
`~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`; never copy the V17 login
token (R-116).

Report (≤ 12 lines): proof line, S6R-22/24/25 status, stderr finding if any, commit.
