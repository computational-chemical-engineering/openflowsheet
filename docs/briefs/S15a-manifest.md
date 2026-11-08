# Implementer brief: S15a — evidence manifest and T08 harvest

Status: brief, 2026-11-08. Bounded build-lane item. **Do not spawn sub-agents yourself.**

## Where

Branch `wp/S15a`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/s15a`, head `d7cb4dbb` (work there;
do not touch main). Manifest `evidence/S15a/<full sha of d7cb4dbb>/manifest.json`, `work_package: "S15a"`.

## What was run (put these exact facts in `commands` / `checks`)

- Merge condition (CLAUDE.md "Gate by risk", amended by Frank 2026-11-08): CI `ci.yml` run `42469977863` on
  `d7cb4dbb`: `check (ubuntu-latest)`, `check (ubuntu-24.04-arm)`, `identity`, `default-install` all success. No
  local full gate (not required any more; do not claim one).
- Targeted on TRS2 (`51c9e7f5`/`d7cb4dbb`): RID.A01–A12 pass (in `tests/test_evidence_manifests.py`; A06 813 616
  strings / 28 000 accepted); `tests/test_evidence_manifests.py` 488 passed (410 + 78); the 11 related test files
  600 passed, 28 skipped; `scripts/corpus_identity.py --check` F0 PASS M1–M9.
- Spec ADR 0074 (Accepted on its condition, `d7cb4dbb`), RP Amendment A-9 (§17.2), register R-970.

## Do

1. Follow the pattern of `evidence/X10a/dbf884ad2b037b9643659fa40b5721ab6b4b5e5c/manifest.json` (on main) and its
   commit `d0dbd128`. `status: "tested"`; `review` pending/pending (never `reviewed`).
2. `limitations`: ADR 0074 §8's open items as the ADR states them — O-3 (nothing ties a line file's
   `evidence_package` to its line; RP amendment RP.L11 before the 0.5 line file), O-4 (ADR 0055 D1 item 5 pointer at
   K-2), O-5 (trailing-newline `$`, no change), and the ADR's "does not establish" points. No new claims.
3. Harvest: entries in `benchmarks/t08/support_envelope.yaml` as for X10a; `scripts/t08_support_matrix.py --emit`
   then `--check`; update `HARVEST_SIZE` in `tests/test_m07a_harvest.py`; run `tests/test_m07a_harvest.py
   tests/test_t08*.py tests/test_evidence_manifests.py` (targeted, `OMP_NUM_THREADS=1`) — 0 failures; then
   `scripts/corpus_identity.py --check`. If anything fails, stop and report without committing.
4. Commit named paths only, message `S15a: evidence manifest at d7cb4dbb (tested); T08 harvest (...), HARVEST_SIZE
   (...)`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
   https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/S15a`. Do not merge.

TRS2 shared: `uptime` first; targeted tests only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 15 lines)

Manifest path, harvest counts and HARVEST_SIZE move, test counts, F0 line, commit sha, anything stopped on.
