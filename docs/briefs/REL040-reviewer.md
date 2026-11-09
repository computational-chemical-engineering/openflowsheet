# Reviewer brief: REL040 prep (wp/REL040p) — the package's single `reviewer` pass

Status: brief, 2026-11-09. Design lane. **Do not spawn sub-agents yourself.** Reading and running targeted tests only;
no code edits.

## What to review

Branch `wp/REL040p` at `5d0c4121` (main with X04 merged in), worktree
`/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rel040p` (read there; do not commit there). Commits:
`git log --oneline --no-merges origin/main..5d0c4121` (19 commits, about 1800 lines). The ruling
`docs/reviews/REL040-s6-ruling.md` (on main; §8 work order, §11 confirmation round) names this pass as the review of
**WO-1** (`5d862052`, `--digest-only` platform class and archive walk), **WO-3** (`cb2a3a6c`,
`scripts/m01_idaes_retake_diff.py`), **WO-4** (`4ba52083`, `host_platform`/`record_platform` in `release_rc_local`
steps 14/15) and **WO-7 (a)** (`26ad9d7f`, log digests compared exactly; `--retake-into` keeps non-empty child logs).

Also in scope, smaller:
- `81716c0a` the class `path` (Q-S6a, confirmed in §11.1).
- `9743871e` RP.L11 (ADR 0074 O-3) in `scripts/release_gate.py`, with R-1007.
- `c46ef9fc` the x05 gate entry in `release/lines/0.4.json`.
- `3e25b294` S6dbg F-A, the NLP-1 inventory consumer fix after OPT's signature change.
- Test-only commits under §8.0's no-host-dependence rule: `0282e4d6` (Q-S6d), `d7258775` (WO-8).
- `c8be15dc` (**Q-S6e, not yet ruled**). S6R-29 found
  `tests/test_m07_journey_record.py::test_a21_a_re_run_names_the_offered_m05_record_tracked_with_its_sha256`
  comparing the working tree's REAL record against three committed journeys' `offered.sha256`. The orchestrator's
  default reads the offered file at the journey's own `commit` (`git show`; CI uses `fetch-depth: 0`).
- RP text: A-11 (`4f8deeb2`) and A-11 item 7 (`0b62c12d`), checked against §6 and §11.2 verbatim.

## Measured (build lane; log `docs/RP_DECISIONS.md` on the branch)

- WO-7's live digest-only proof on a fresh re-take at `0b62c12d`:
  `RETAKE-DIGEST-ONLY PASS trust-region-study-real: changed-digests=103 digest=504 timing=528 path=128 version=0 platform=4 other=0 environment=equal`.
  This is byte-equal to the earlier fresh rerun. IDAES re-take diff PASS `platform=1 inputs=1 other=0`.
- S6R-29 at J′ (head + both re-takes):
  - re-take modules 50/50 at head and at J′;
  - default tier serial, head 16007 passed 0 failed, J′ 16004 passed 3 failed — exactly the three Q-S6e cases, same
    19216 ids.
- After Q-S6e the M07 module passes at head (56) and with the working-tree REAL record altered (56).
- At `5d0c4121`: release/register/harvest/re-take/journey tests 1114 passed, 1 skipped; F0 PASS M1–M9.
- CI on `5d0c4121` is running.

## Where I am least sure — look hardest here

1. WO-1/WO-7: can the digest-only proof pass a re-take that changed something other than digests, timing, path,
   version and platform? For example a relabelling that hides a real value change, or the archive walk missing a file.
   §11.3 said a uniform log change would have passed before WO-7. Is that closed now?
2. WO-3: does `m01_idaes_retake_diff` admit only `environment.platform` and the `inputs.*` hash, and is the
   `reference_values_yaml_sha256` change judged by the rule the ruling set?
3. Q-S6e: is reading at the journey's commit as strong as the old check (tracked, unmodified, sha256, anchor)? Rule it.
4. Any other default-tier test still bound to the committed records' host or content (O-6)?

## Deliverable

`docs/reviews/REL040-review.md` containing:
- a verdict;
- M / S / N findings, each with file:line and a stated fix;
- a ruling on Q-S6e;
- a numbered fix-round work order if one is needed;
- a line on whether anything needs Frank (default: no).

Commit on **main** (docs only, named path, message `docs: REL040 review`, trailers `Co-Authored-By: Claude Opus 5.5
<noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; `git pull
--rebase` before push). Report in at most 15 lines.

TRS2 (reset twice under load): `uptime` first, targeted tests only, serial, one process; never a full suite. Never read
or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`; never copy the
V17 login token (R-116).
