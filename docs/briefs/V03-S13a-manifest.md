# V03 brief 6: the S13a manifest so `wp/V03` can merge before K3 (build lane, one engineer)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/v03`, branch `wp/V03`, head `0ce3748a`. Full gate PASS at
`0ce3748a` (14712 passed, 3206 skipped, 196 deselected; log `/home/frankp/.cache/v03-gate/gate-0ce3748a.log`).

**Why.** Spec P3 (`docs/derivations/V03-release-spec.md` §4) merges WO-1…WO-4 into `main` before the cut K3, but S13's
manifest is written only at C (WO-6). `CLAUDE.md` allows a merge into `main` only with a `tested` manifest. Orchestrator's
DECISION: a sub-manifest **S13a** for WO-1…WO-4, as E01b used S12b (`evidence/S12b/1fd29546…/manifest.json` is the pattern;
id pattern `^[PKTMSR][0-9]{2}[a-z]?$`). S13 at C stays as the spec says and may cite S13a.

1. Write `evidence/S13a/0ce3748a…/manifest.json` (full sha) — `status: tested`, never `reviewed`. Items: the V03 assertions
   that WO-1…WO-4 own and that are testable before K3 (spec §7 and the §10 table: A01–A08, A10–A16, A18, A28–A31 — check each
   against §7; any whose evidence only exists at K3/C is listed `planned` with that reason, and if that leaves the package
   not honestly `tested`, stop and report). Each item: the test node ids or script and the actual result at `0ce3748a`
   (run them; quote real counts). The review record: `docs/reviews/V03-review.md` and the fix commits. Commands actually run,
   including the gate line above. No angle-bracket values.
2. Harvest: add the manifest to whatever S12b/S14 were added to (support-envelope harvest, `HARVEST_SIZE`, the matrix);
   recount (now (65, 921, 119) plus S13a's increments), `scripts/t08_support_matrix.py --emit`, `--check` 0. Map any new
   limitation (A21 fails on unmapped ones).
3. Run the tests the manifest and harvest touch (`tests/test_m07a_harvest.py`, the evidence-schema tests, `tests/test_t08*`
   matrix/envelope tests, the A21 test) and report the counts. Commit (named paths; message names V03 and S13a).
4. DECISION line in `docs/V03_DECISIONS.md` recording the orchestrator's choice (alternative: merge without a manifest —
   forbidden by `CLAUDE.md`; reversible by reverting the commit).

Rules: pytest with `TMPDIR=/home/frankp/.cache/v03-tmp PYTEST_ADDOPTS="--basetemp=/home/frankp/.cache/v03-tmp/pt"`,
`PYTHONPATH=$PWD/src:$PWD`, `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python`; do not push; no subagents; no personal
identifiers to external services; never touch `~/.config/procsim/v17-token`. Report in at most 12 lines (sha, item counts,
HARVEST_SIZE, test counts).
