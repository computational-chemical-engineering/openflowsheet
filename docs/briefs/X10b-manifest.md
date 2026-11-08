# Implementer brief: X10b — evidence manifest and T08 harvest

Status: brief, 2026-11-08. Bounded build-lane item. **Do not spawn sub-agents yourself.**

## Where

Branch `wp/X10b`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x05a`, head `c57d449a` (full sha
`c57d449aaed52ca9cff1b7a737a9161cc3fdd093`; work there, do not touch main). Manifest
`evidence/X10b/c57d449aaed52ca9cff1b7a737a9161cc3fdd093/manifest.json`, `work_package: "X10b"`.

## What was run (put these exact facts in `commands` / `checks`)

- Merge condition (CLAUDE.md "Gate by risk", Frank 2026-11-08): CI `ci.yml` run `42503117602` on `c57d449a`:
  `check (ubuntu-latest)`, `check (ubuntu-24.04-arm)`, `identity`, `default-install` all success. No local full gate
  (not required; do not claim one).
- Targeted on TRS2 (engineer's runs): `03709167` — `tests/test_m02_wo8_g7.py`, the model-manifest/artifact-hash
  tests, `tests/test_wit_*.py`; F0 M9 entry re-recorded for `models/c1/flash.py` only (`f228a4a3…` → `b1b47c28…`;
  M1–M8 equal; `--check` PASS); `c57d449a` (L01 §15 Amendment 4, R-983, on main as `1e77b747`): 162 passed, 1 skipped,
  0 failed; F0 PASS. `model_version` and every result unchanged (WIT review M-6). Read `docs/WIT_DECISIONS.md`
  (M-6 part b) for the exact wording.
- Spec: ADR 0073 (Accepted 2026-11-08, Q-WIT-2 yes), WIT review M-6, L01-spec §15 Amendment 4, register R-983.

## Do

1. Follow the pattern of `evidence/X10a/*/manifest.json` (WIT, the parent package) and `evidence/X05a/*/manifest.json`
   (on main). `status: "tested"`; `review` pending/pending (never `reviewed`).
2. `limitations`: carry X10a's limitations that still hold for this text-and-pin change; add that the change is a
   manifest sentence and two docstrings (no numerics moved) and the R-983 note that F0 M9 guards 9 of L01.A22's 18
   files. No new claims.
3. Harvest: entries in `benchmarks/t08/support_envelope.yaml` as for X05a; `scripts/t08_support_matrix.py --emit`
   then `--check`; update `HARVEST_SIZE` in `tests/test_m07a_harvest.py`; run `tests/test_m07a_harvest.py
   tests/test_t08*.py tests/test_evidence_manifests.py` (targeted, `OMP_NUM_THREADS=1`) — 0 failures; then
   `scripts/corpus_identity.py --check`. If the branch lacks main's newest manifests (MSG, X05a) and HARVEST_SIZE
   would then disagree with main, merge `main` into `wp/X10b` first (merge commit, named in the report). If anything
   fails, stop and report without committing.
4. Commit named paths only, message `X10b: evidence manifest at c57d449a (tested); T08 harvest (...), HARVEST_SIZE
   (...)`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
   https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/X10b`. Do not merge into main.

TRS2 shared: `uptime` first; targeted tests only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 15 lines)

Manifest path, harvest counts and HARVEST_SIZE move, test counts, F0 line, commit sha(s), anything stopped on.
