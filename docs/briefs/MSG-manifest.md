# Implementer brief: MSG — final evidence manifest (tested) and T08 harvest

Status: brief, 2026-11-08. Bounded build-lane item. **Do not spawn sub-agents yourself.**

## Where

Branch `wp/MSG`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/msg`, head `5e9274db` (full sha
`5e9274dbee91dd25d7201f24b025db2498027744`). Work there; do not touch main. Manifest
`evidence/MSG/5e9274dbee91dd25d7201f24b025db2498027744/manifest.json`, `work_package: "MSG"`.

## What was run (put these exact facts in `commands` / `checks`)

- Merge condition (CLAUDE.md "Gate by risk", Frank 2026-11-08): CI `ci.yml` run `42502713324` on `5e9274db`:
  `check (ubuntu-latest)`, `check (ubuntu-24.04-arm)`, `identity`, `default-install` all success. No local full gate
  at this commit (do not claim one; the earlier full gate at `9c76b939` is in `docs/MSG_DECISIONS.md` line ~611).
- Targeted at `43c0e900` (DM-5 in `docs/MSG_DECISIONS.md` ~668): surface chain c_4 D_4 `eaff4585…` unchanged; read
  DM-5 for the exact counts and copy them. `5e9274db` = Frank's human review of `explain` recorded by Frank himself
  (decision board, 2026-11-08) — so the description-review test (DM-2's one failure) now passes; CI confirms it.
- Register R-975/R-976 (renumbered from R-942/R-943; the earlier manifest `9c76b939…` keeps citing the old numbers —
  leave it untouched).

## Do

1. **Merge `main` into `wp/MSG` first** (merge commit; main moved: X05a merged, `HARVEST_SIZE` on main is
   (77, 993, 126)). Resolve conflicts by keeping both sides' register/log entries; if a conflict is not of that kind,
   stop and report.
2. Manifest following `evidence/MSG/9c76b93985915e6b7452b7573514850c477e712b/manifest.json` and
   `evidence/X05a/*/manifest.json`. `status: "tested"`; `review` as the package's reviews stand (the design-lane review
   `docs/reviews/MSG-review.md` if it exists is the reviewer's, record it as its file says; the human sign-off of
   numerical results is not claimed — never write `reviewed` for the package itself). `limitations`: carry the previous
   MSG manifest's limitations that still hold; no new claims.
3. Harvest: `benchmarks/t08/support_envelope.yaml` entries for this manifest as for X05a; `scripts/t08_support_matrix.py
   --emit` then `--check`; update `HARVEST_SIZE` in `tests/test_m07a_harvest.py` to the new count; run
   `tests/test_m07a_harvest.py tests/test_t08*.py tests/test_evidence_manifests.py tests/test_m07a_surface_chain.py`
   (targeted, `OMP_NUM_THREADS=1`) — 0 failures; then `scripts/corpus_identity.py --check`. Use `.venv/bin/python`.
   If anything fails, stop and report without committing.
4. Commit named paths only, message `MSG: evidence manifest at 5e9274db (tested); T08 harvest (...), HARVEST_SIZE
   (...)`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
   https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/MSG`. Do not merge into main.

TRS2 shared: `uptime` first; targeted tests only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 15 lines)

Merge commit, manifest path, harvest counts and HARVEST_SIZE move, test counts, F0 line, commit shas, anything stopped on.
