# Implementer brief: WIT — evidence manifest and T08 harvest

Status: brief, 2026-11-08. Bounded build-lane item. **Do not spawn sub-agents yourself.**

## Where

Branch `wp/WIT`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/wit`, head `dbf884ad` (work there; do
not touch main). The package's evidence goes under `evidence/K04/<commit>/manifest.json`, `<commit>` = the full sha of
`dbf884ad` (the tested code commit; the manifest commit comes after it).

## What was run (put these exact facts in `commands` / `checks`)

- Full gate at `dbf884ad`: `GATE PASS dbf884ad: 15194 passed, 3206 skipped, 197 deselected, 1 warning in 6325.54s` (log `/tmp/gate-<sha>.log`, command
  `PYTHONPATH=$PWD/src PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH ./scripts/gate.sh`).
- CI `ci.yml` run `42459637834` on head `dbf884ad`: `check (ubuntu-latest)` success, `check (ubuntu-24.04-arm)`
  success, `identity` success, `default-install` success.
- Spec `docs/derivations/K04-certificate-spec.md` §4.8.1–§4.8.9, ADR 0073 (Proposed), reference
  `docs/derivations/scripts/wit_reference.py`/`.json` (WIT.A01–A15); review `docs/reviews/WIT-review.md` on main
  (`1476a017`), fix round D-5…D-10 in `docs/WIT_DECISIONS.md`.

## Do

1. Follow the pattern of commit `873e6bc3` (X10 manifest + harvest) and the schema of
   `evidence/X10/033f19289a891221537769d8024ec7f61c0f4da7/manifest.json`. `work_package: "K04"` if the D1 id pattern
   requires a registered id (it admits `K[0-9]{2}`; `WIT` does not match — use `K04`, and name WIT in the text).
2. `status: "tested"` — only if the gate line above is a PASS and CI is all success. Otherwise stop and report.
   `review`: point at `docs/reviews/WIT-review.md`; never set `reviewed`.
3. `limitations`: carry over what `docs/WIT_HANDOFF.md` and the review list as open: M-6 part b (flash manifest sentence,
   Frank Q-WIT-2); M-4 (OPT D-42/D-82) waits for the OPT merge; ADR 0073 Proposed. State plainly what was not
   established (copy from the review's "did not establish" section, no new claims).
4. Harvest: `scripts/t08_support_matrix.py --emit`, then `--check`; update `HARVEST_SIZE` in
   `tests/test_m07a_harvest.py` if the harvest count moves; run `tests/test_m07a_harvest.py` and
   `tests/test_t08*` only (targeted, `OMP_NUM_THREADS=1`). Run `scripts/corpus_identity.py --check` (F0) once.
5. Commit named paths only (never `git add -A`), message
   `WIT: evidence manifest at <short> (tested); T08 harvest (...), HARVEST_SIZE (...)` with the session's
   Co-Authored-By / Claude-Session lines. Do not push, do not merge.

## Machine-load rule

TRS2 is shared: `uptime` first; targeted tests only, one at a time; no full gate.

## Report (≤ 20 lines)

Manifest path, harvest counts and HARVEST_SIZE move, F0 result, the commit sha, anything you stopped on.
