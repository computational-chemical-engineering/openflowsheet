# Engineer brief: REL040 review fix round — WO-R1 (+ optional N-1, N-3, N-5)

Status: brief, 2026-11-09. Build lane. **Do not spawn sub-agents yourself.** No tag, no release, no K3.

## Authority

`docs/reviews/REL040-review.md` on main (`git show origin/main:docs/reviews/REL040-review.md`): S-1 and its work order
WO-R1. Read the whole review. WO-R1 asks for the following:
- `--digest-only` compares the coupling records' `inner.state_sha256` and `inner.constants_sha256` and the ledger's
  `requests[].inputs_sha256` **exactly**, as WO-7 (`26ad9d7f`) does for log digests;
- one test per digest, plus the reviewer's case where all 16 state digests move one-to-one (it passes at `5d0c4121`,
  must fail after);
- these must not change: S6R-10's two lines, S77's `42/80/71/92/38`, and the live REAL proof line
  `RETAKE-DIGEST-ONLY PASS trust-region-study-real: changed-digests=103 digest=504 timing=528 path=128 version=0 platform=4 other=0 environment=equal`;
- one log sentence correcting §2's claim about what the proof establishes.

Also fold in, each as its own small commit, if each stays a local change: **N-1** (Q-S6e test, journey commit must be
an ancestor of HEAD), **N-3** (refuse `--old-version` with `--old-platform`), **N-5** (keep child logs when the run
raises). Skip **N-4** (log it as not done). Anything that would change a number, a fingerprint or a registered record:
stop and report.

## Where

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rel040p`, branch `wp/REL040p` at `5d0c4121` (pull
first). `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with `PYTHONPATH=src`; `OMP_NUM_THREADS=1`; nlp env as in
`docs/RP_DECISIONS.md` § S-6. The fresh REAL re-take outputs for the live proof are in
`/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rel040p/.cache/s6r/real-0b62c12d/` (git-ignored; do not delete).

TRS2 (reset twice under load): `uptime` first; one serial test process; never a full suite.

## Finish

1. Rerun the live proof line on that re-take and S77's pair; both must be unchanged.
2. Run the touched tests, plus `tests/test_m05_retake_digest_only.py tests/test_m01_idaes_retake_diff.py
   tests/test_m07_journey_record.py tests/test_rel_*.py`.
3. F0 `scripts/corpus_identity.py --check` PASS; `ruff check`, `ruff format --check`.
4. Log in `docs/RP_DECISIONS.md` (§ REL040 review fix round). Push `wp/REL040p`. No manifest, no merge.

Trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; named paths only. Cap ~150k context. Never read or touch
`~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`; never copy the V17 login
token (R-116).

## Report (at most 15 lines)

Commits; the live proof line and S77's numbers; the new tests (fail before / pass after); test counts; F0 line;
anything stopped on.
