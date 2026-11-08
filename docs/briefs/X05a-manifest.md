# Implementer brief: X05a — evidence manifest and T08 harvest

Status: brief, 2026-11-08. Bounded build-lane item. **Do not spawn sub-agents yourself.**

## Where

Branch `wp/X05a`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x05a`, head `b43d94bc` (full sha
`b43d94bc2f6986a10fea2a2d49cb3c04b83ec10c`; work there, do not touch main). Manifest
`evidence/X05a/b43d94bc2f6986a10fea2a2d49cb3c04b83ec10c/manifest.json`, `work_package: "X05a"`.

## What was run (put these exact facts in `commands` / `checks`)

- Merge condition (CLAUDE.md "Gate by risk", Frank 2026-11-08): CI `ci.yml` run `42500882154` on `b43d94bc`:
  `check (ubuntu-latest)`, `check (ubuntu-24.04-arm)`, `identity`, `default-install` all success. No local full gate
  (not required; do not claim one).
- Targeted on TRS2 at `b43d94bc` (engineer's run): `tests/test_x05_*.py tests/test_m01_provider.py` and the
  Requires-Dist packaging tests — 548 passed, 11 skipped; `x05_reference.py --check` PASS; F0 PASS.
- Spec: ADR 0069 (Accepted 2026-11-08 with Q-F1 = no; Amendment 1), ADR 0007 Amendment 2, register R-985…R-987,
  R-140 lifted. Build decisions D-10, D-11 (in the package's build-decisions file; cite it, read it for wording).

## Do

1. Follow the pattern of `evidence/X05/7c8d05e59dcef7c60b260b687b3cc4e06e5cbda0/manifest.json` (the parent package)
   and of `evidence/S15a/*/manifest.json` (on main). `status: "tested"`; `review` pending/pending (never `reviewed`).
2. `limitations`: what ADR 0069 Amendment 1 says an unconstrained install no longer gives (only an install
   constrained by the shipped lock verifies; a plain install records `lock_sha256 = ""` and names the floating
   members), plus the ADR's own "does not establish" points. No new claims.
3. Harvest: entries in `benchmarks/t08/support_envelope.yaml` as for S15a; `scripts/t08_support_matrix.py --emit`
   then `--check`; update `HARVEST_SIZE` in `tests/test_m07a_harvest.py`; run `tests/test_m07a_harvest.py
   tests/test_t08*.py tests/test_evidence_manifests.py` (targeted, `OMP_NUM_THREADS=1`) — 0 failures; then
   `scripts/corpus_identity.py --check`. If the branch lacks main's newest manifests (S15a, X10a) and HARVEST_SIZE
   would then disagree with main, merge `main` into `wp/X05a` first (merge commit, named in the report). If anything
   fails, stop and report without committing.
4. Commit named paths only, message `X05a: evidence manifest at b43d94bc (tested); T08 harvest (...), HARVEST_SIZE
   (...)`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
   https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/X05a`. Do not merge into main.

TRS2 shared: `uptime` first; targeted tests only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 15 lines)

Manifest path, harvest counts and HARVEST_SIZE move, test counts, F0 line, commit sha(s), anything stopped on.
