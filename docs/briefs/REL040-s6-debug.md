# Engineer brief: diagnose S-6's two runner failures (NLP-1 inventory TypeError, M05 REAL replay divergence)

Status: brief, 2026-11-09. Build lane, hard debugging. **Do not spawn sub-agents yourself.** No tag, no release.

## Facts (S-6 rehearsal, `docs/RP_DECISIONS.md` § S-6 on `wp/REL040p`, C = `9743871e` = main + x05 entry + RP.L11)

- nlp environment: `--nlp-prefix` = the `m05` worktree's `.venv-nlp`, `--nlp-cache` its `.reference-downloads/m03-ipopt`
  (0.3.0's choice). `pytest -m nlp`: 211 passed.
- **F-A.** Step 14 `a60.w24.nlp_tier_and_inventory` and step 17 `E01-G6-nlp`: the NLP-1 inventory workload
  (`scripts/m03_ipopt_inventory.py`, function `nlp_1`; also run inside `m03_nlp_check.sh`) raises
  `TypeError: 'NoneType' object is not subscriptable` at `start["final_decisions"]` — a start without
  `final_decisions`. It passed at 0.3.0 in the same environment. Since 0.3.0, OPT (ADR 0071, optimiser on revision
  flowsheets; merged `937223ad`) and X02 (warm starts, `35aa61e1`) landed; suspect a result-shape change for a start
  that did not finish (failed/aborted start) that the inventory script does not handle — or a real regression in the
  optimiser.
- **F-B.** Step 14 `a60.w24.m05_g10_real_replay`: `ReplayDivergedError: replay diverged: a cold execution at {...
  'temperature': 673.15 ...}`; step 15's replay diverges the same way. At 0.3.0 it gave `differences=0`. Earlier C7/V03
  notes ran it in `alpha-main`'s `.venv-nlp`; S-6 used `m05`'s, as 0.3.0's RC did. Suspects: environment (which venv),
  X02's warm-start/cache-key change (ADR 0070: the cache key gains a warm-start member only when one was used), or
  RRC/OPT.
- Rehearsal records: `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/fd59d98d-797a-4da8-93d6-9c61c6d4bdc7/scratchpad/rel040p/s6-work/rc`
  (logs per step).

## Do

1. Reproduce each failure alone, with the smallest command (from the step logs), at current `origin/main` in a fresh
   worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/s6dbg` (branch `wp/S6dbg`). Venv as in other briefs
   (`/home/frankp/Codes/OpenFlowsheet/.venv/bin/python`, `PYTHONPATH=src`) for the default env; the nlp env as above.
2. Bisect against the 0.3.0 tag / the merges since (`git log --merges --oneline v0.3.0..origin/main`) to find the first
   commit where each fails. For F-B, first rule out the environment (run with both `m05`'s and `alpha-main`'s
   `.venv-nlp` if present; record package versions that differ).
3. Classify each: (a) a script/consumer that does not handle a changed but specified result shape → fix the consumer
   in its own commit with a test, citing the spec that defines the shape; (b) a real regression in production code that
   is a local bug with an obvious fix not touching numerics → fix with a test; (c) anything that changes a number, a
   replay identity, a cache key or a registered record, or where the spec is unclear → **stop and report** with the
   evidence (first bad commit, the diverging member, the diff) for the design lane.
4. Log findings in a new `docs/S6DBG_DECISIONS.md` on the branch; push `wp/S6dbg`. Targeted tests for what you touch,
   plus `pytest -m nlp` in the nlp env if you touch the optimiser; F0 `scripts/corpus_identity.py --check` PASS;
   ruff/format. No merge.

Not yours: step 11's IDAES record re-take, the 0.4 journey J (step 15's carry). TRS2 shared: `uptime` first; at most
~16 cores for your runs (another package is in CI and may run tests locally). Trailers `Co-Authored-By: Claude Opus 5.5
<noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; named paths
only. Cap ~150k context: commit, write where you stopped in `docs/S6DBG_DECISIONS.md`, end. Never read or touch
`~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`; never copy the V17 login
token (R-116).

## Report (≤ 20 lines)

Per failure: reproduction command, first bad commit, root cause, class (a/b/c), fix commit or the question for the
design lane; test counts; F0 line.
