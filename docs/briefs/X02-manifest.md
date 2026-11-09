# Implementer brief: X02 — evidence manifest re-take and T08 harvest

Status: brief, 2026-11-08. Bounded build-lane item. **Do not spawn sub-agents yourself.**

## Where

Branch `wp/X02`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x02`, CI-green head `d26bcd38` (full sha
`d26bcd3825ae4f55986a87412c8c1c827497f2c2`). Work there; do not touch main. Worktrees have no `.venv`: run tests as
`PYTHONPATH=src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` and confirm `openflowsheet.__file__`
points into the worktree first.

## What was run (put these exact facts in `commands` / `checks`)

- Merge condition (CLAUDE.md "Gate by risk", Frank 2026-11-08): CI `ci.yml` run `42521075017` on `d26bcd38`:
  `check (ubuntu-latest)`, `check (ubuntu-24.04-arm)`, `identity`, `default-install` all success. No local full gate
  (not required; do not claim one).
- Spec: ADR 0070 (read its status line on the branch), register R-950…R-955 (`docs/decision-register.md`), design
  `docs/design/X02-warm-starts.md`; build decisions D-35…D-39 and the MSG G2 catalogue fix in `docs/X02_DECISIONS.md`
  (cite, read it for wording). Surface chain link c_5, D_5 = `f51b69bf66569e35aebead73b66e98d58f24c84016db639536c0ee35181f4c7b`.

## Do

1. **Merge `origin/main` into `wp/X02` first** (main has X10b's merge, which moved `tests/test_m07a_harvest.py` and
   the harvest to (81, 1015, 129)). Resolve conflicts, if any, by keeping both sides' content; if a conflict needs a
   judgement beyond that (code, digests, a numeric pin), stop and report. Commit the merge.
2. Manifest `evidence/X02/d26bcd3825ae4f55986a87412c8c1c827497f2c2/manifest.json`, `work_package: "X02"`, following
   the pattern of the branch's previous `evidence/X02/2ab11b66…/manifest.json` and of
   `evidence/X10b/*/manifest.json` (on main). The manifest names the CI-green commit `d26bcd38` (the merge commit
   carries only main's already-tested content). `status: "tested"`; `review` pending/pending (never `reviewed`).
   `limitations`: carry over the previous X02 manifest's and ADR 0070's own "does not establish" points; no new claims.
3. Harvest: entries in `benchmarks/t08/support_envelope.yaml` as X10b's did; `scripts/t08_support_matrix.py --emit`
   then `--check`; update `HARVEST_SIZE` in `tests/test_m07a_harvest.py` (with its comment line in the existing
   style, ≤ 120 chars); run `tests/test_m07a_harvest.py tests/test_t08*.py tests/test_evidence_manifests.py
   tests/test_x02_*.py tests/test_msg_coverage.py tests/test_t07_global_state.py` (targeted, `OMP_NUM_THREADS=1`,
   `-n 4` at most) — 0 failures; then `scripts/corpus_identity.py --check` (F0) PASS; `ruff check` and
   `ruff format --check` on the whole tree. If anything fails, stop and report without committing.
4. Commit named paths only, message `X02: evidence manifest at d26bcd38 (tested); T08 harvest (...), HARVEST_SIZE
   (...)`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
   https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/X02`. Do not merge into main.

TRS2 shared: `uptime` first; targeted tests only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 15 lines)

Merge commit, manifest path, harvest counts and HARVEST_SIZE move, test counts, F0 line, commit sha(s), anything
stopped on.
