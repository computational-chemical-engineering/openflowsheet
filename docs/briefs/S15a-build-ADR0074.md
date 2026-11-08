# Implementer brief: S15a — apply ADR 0074 (release evidence package id), RP K-1

Status: brief, 2026-11-08. Bounded build-lane item from an approved spec. **Do not spawn sub-agents yourself.**
Spec: `docs/adr/0074-release-evidence-package-id.md` (Proposed, on main `930f912d`) — §2 decision, §5 Amendment A-9,
§6 acceptance RID.A01–A12, §9 register line. Read the whole ADR first; it is binding. If it leaves anything you need
open (e.g. where `rel_id` lives, an exact list), **stop and report** — do not choose.

## Where

New branch `wp/S15a` from main, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/s15a`
(`git worktree add -b wp/S15a .claude/worktrees/s15a main`). Package id `S15a` (RP's package is `S15`; this is its
K-1 follow-up). Another agent works in `.claude/worktrees/st` — never touch it.

## Do

1. **Commit 1 (alone, as ADR 0074 requires):** the one appended alternative in
   `schemas/evidence-manifest.schema.json` `properties.work_package.pattern`, exactly as §2 gives it, plus the RID
   tests (one new test file, e.g. `tests/test_adr0074_release_ids.py`, and `rel_id` wherever §2/§6 put it). No other
   file in that commit (check `git show --stat`; if `_data/schemas/` is a symlink to `schemas/`, nothing extra moves).
   Message `S15a: ADR 0074 D1 — work_package admits the release package id (additive)`.
2. Run RID.A01–A12 and `tests/test_evidence_manifests.py` (record its pass count for RID.A12), then the release
   tests that read the pattern (`grep -l "evidence-manifest\|work_package\|REL040" tests/*.py`), targeted, one run at
   a time, `OMP_NUM_THREADS=1`. `scripts/corpus_identity.py --check` must PASS (does the schema file enter F0? if F0
   moves, stop and report). `ruff check`, `ruff format --check`, `mypy` on what you add.
3. **Commit 2 (docs):** paste Amendment A-9 verbatim as §17.2 of `docs/derivations/release-procedure.md` (and change
   D1.5's text only as A-9 says); add the register line from §9 to `docs/decision-register.md` as **R-970**
   (R-950…R-969 are held by unmerged branches; DECISION logged by the orchestrator); mark ADR 0074's status
   **Accepted** with the evidence its acceptance condition names (commit 1's sha, the RID results, the
   `test_evidence_manifests.py` count), in the form ADR 0059's status line uses. Message `S15a: ADR 0074 accepted on
   its condition; RP A-9 (§17.2); R-970`.
4. Push `wp/S15a` (not main). Do not merge. No manifest yet (the orchestrator runs the full gate and CI first).

Commit trailers: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Named paths only, never `git add -A`.

## Rules

No relaxed checks, no edited gates, never set `reviewed`. TRS2 shared: `uptime` first; targeted tests only; no full gate.
Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 20 lines)

Both commit shas, `git show --stat` of commit 1, RID.A01–A12 results, the test counts, F0 line, anything you stopped on.
