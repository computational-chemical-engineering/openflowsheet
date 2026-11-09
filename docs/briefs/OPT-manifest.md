# Implementer brief: OPT — evidence manifest re-take and T08 harvest

Status: brief, 2026-11-09. Bounded build-lane item. **Do not spawn sub-agents yourself.**

## Where

Branch `wp/OPT`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/opt`, CI-green head `c1b9b125` (full sha
`c1b9b1255699b2cd9d1f6c1da120f761dd1e80d6`). Work there; do not touch main. Worktrees have no `.venv`: default-env tests
run as `PYTHONPATH=src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial; no xdist) after
confirming `openflowsheet.__file__` points into the worktree. The audited (nlp) env and G2 commands are in
`docs/OPT_HANDOFF.md` "How to run".

## What was run (put these exact facts in `commands` / `checks`)

- Merge condition (CLAUDE.md "Gate by risk", Frank 2026-11-08): CI `ci.yml` run `42534167073` on `c1b9b125`:
  `check (ubuntu-latest)`, `check (ubuntu-24.04-arm)`, `identity`, `default-install` all success. No local full gate
  (not required; do not claim one).
- Spec: ADR 0071 Accepted 2026-11-08 (Frank, decision board) with ADR 0019 Amendment 16; register R-960…R-969 and
  R-988; design and review `docs/reviews/OPT-review.md`; build decisions through D-94 in `docs/OPT_DECISIONS.md` (cite,
  read for wording). Surface chain link c_6, D_6 = `3fdc797ad64485abf63fb491ebd56aa43dc510e62e9e218b0dd7a8fcc2e38a85`
  (stripping OPT gives D_5 exactly); global-state caches 39.

## Do

1. **Audited env re-check after the merge of main** (the merge brought WIT's witness; the 21 nlp-marked tests and G2
   have not run since): run the audited-env OPT tests and the G2 dump per the handoff; compare with the WO-8b numbers in
   `docs/OPT_DECISIONS.md` "WO-8b gates" (audited 21 passed; G2 both envs identical; G22 3/3 verified). Any difference
   that is not explained by D-89 (WIT's held splits now certify) → stop and report without committing. Log the result as
   D-95.
2. If `origin/main` has moved beyond `b31e80ec` only by `docs/` commits, merge it (`git merge origin/main`); if it has
   any non-docs commit, stop and report.
3. Manifest `evidence/OPT/c1b9b1255699b2cd9d1f6c1da120f761dd1e80d6/manifest.json`, `work_package: "OPT"`, in the
   pattern of the branch's earlier `evidence/OPT/a46ea80f…/manifest.json` and of
   `evidence/X02/d26bcd38…/manifest.json` (on main). `status: "tested"`; `review` pending/pending (never `reviewed`).
   `limitations`: the handoff's "Next" item 1 list exactly — D-82's strings (pr-c1-v1 REGIME_MARGIN_UNDEFINED;
   thermal-port boundary fails V1; N1 absolute flow thresholds; S1 dormant splits), D-70's string with starts
   {673.15 K, 650 K}, and D-82 (a) as corrected after WIT ("γ–φ held splits certify and are unguarded
   (`regimes_unguarded`)"); the human description reviews (validate, submit_job) are recorded by Frank on the branch
   (`9869773e`) — cite, do not restate as agent review; the design-lane prose check of D-92's catalogue entries and
   D-93 (corpus C12) is pending. No new claims.
4. Harvest: entries in `benchmarks/t08/support_envelope.yaml` as X02's did; `scripts/t08_support_matrix.py --emit`
   then `--check`; update `HARVEST_SIZE` in `tests/test_m07a_harvest.py` (comment line in the existing style,
   ≤ 120 chars); run `tests/test_m07a_harvest.py tests/test_t08*.py tests/test_evidence_manifests.py
   tests/test_opt*.py tests/test_msg_coverage.py tests/test_t07_global_state.py` (`OMP_NUM_THREADS=1`) — 0 failures;
   F0 `scripts/corpus_identity.py --check` PASS; `ruff check` and `ruff format --check` on the whole tree. If anything
   fails, stop and report without committing.
5. Commit named paths only, message `OPT: evidence manifest at c1b9b125 (tested); T08 harvest (...), HARVEST_SIZE
   (...)`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
   https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/OPT`. Do not merge into main.

TRS2 shared: `uptime` first; targeted tests only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 15 lines)

Audited-env and G2 result vs WO-8b, merge commit (if any), manifest path, harvest counts and HARVEST_SIZE move, test
counts, F0 line, commit sha(s), anything stopped on.
