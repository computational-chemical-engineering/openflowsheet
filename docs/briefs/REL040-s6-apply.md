# Engineer brief: apply the S-6 ruling (A-11, R-1008, WO-1…WO-6) on wp/REL040p

Status: brief, 2026-11-09. Build lane. **Do not spawn sub-agents yourself.** No tag, no release, no publish.

Branch `wp/REL040p`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rel040p` (head `a1a00e17`). Ruling:
`docs/reviews/REL040-s6-ruling.md` (main, `9f7cd613`) — §6 A-11 and §7 R-1008 verbatim, §8 work order WO-1…WO-6 with
assertions S6R-01…25 and §8.0's tolerance. Apply it; decide nothing it settles.

0. First `git merge origin/wp/S6dbg` (the NLP-1 inventory fix `3e25b294` + its log; F-A, class a) and
   `git merge origin/main` (docs only since; keep both sides). Then the ruling's items in order, one commit per WO
   (messages naming REL040 and the WO).
1. WO-6 (rehearse on this host; the open fact "does a kernel change move any REAL or IDAES number"): **if either proof
   fails, stop and report** — do not adjust anything to pass (RP §952: nothing is edited, re-run or re-taken to pass).
   Rehearsal outputs go under the worktree's git-ignored `.cache/` or the scratchpad, never into `docs/` or
   `evidence/` unless the ruling says so.
2. Log in `docs/RP_DECISIONS.md` (S-6 ruling section: commits, S6R measured values).
3. Tests: what each WO names plus `tests/test_rel_*.py tests/test_release_workflows.py tests/test_evidence_manifests.py`
   and the nlp test S6dbg added (nlp env as in `docs/S6DBG_DECISIONS.md`); F0 `scripts/corpus_identity.py --check`
   PASS; `ruff check`, `ruff format --check`. Push `wp/REL040p`. No manifest, no merge.

Venv: `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with `PYTHONPATH=src` (worktree copy confirmed); nlp env per
the S6dbg log. TRS2 shared: `uptime` first, ≤ ~36 busy cores total (X04's CI may run tests locally). Trailers
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; named paths only. Cap ~150k context: commit, write where you
stopped in `docs/RP_DECISIONS.md`, end. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`; never copy the V17 login token (R-116).

Report (≤ 20 lines): commits per WO; S6R-01…25 status with key numbers; WO-6's answer (kernel moves numbers: yes/no,
evidence); test counts; F0 line; anything stopped on.
