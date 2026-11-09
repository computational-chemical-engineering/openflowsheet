# Implementer brief: RRC — first evidence manifest and T08 harvest

Status: brief, 2026-11-09. Bounded build-lane item. **Do not spawn sub-agents yourself.** Start only when the
orchestrator gives you the CI run id (CI green on both architectures at the head named below).

## Where

Branch `wp/RRC`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rrc`, CI-green head `6b892b03` (full sha
`6b892b036f2fc82167784daa6bce946345b64515`) unless the orchestrator names another. Worktrees have no `.venv`: run
`/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with `PYTHONPATH=src`; confirm `openflowsheet.__file__` points into
the worktree. Serial tests (no xdist), `OMP_NUM_THREADS=1`.

## What was run (exact facts for `commands` / `checks`)

- Merge condition (CLAUDE.md "Gate by risk", Frank 2026-11-08): CI `ci.yml` run **<given by the orchestrator>** on the
  head: `check (ubuntu-latest)`, `check (ubuntu-24.04-arm)`, `identity`, `default-install` all success. CI runs G7
  (default check, both archs) and G8 (`tests/test_rrc_g8_determinism.py`, N1 and C3, x86-64 R0 pins checked on
  aarch64). No local full gate (not required; do not claim one — mark any gate that only a full gate would give
  `unsupported`, as OPT's G21).
- Spec: ADR 0072 Accepted 2026-11-08 (Frank; FQ1 yes, FQ2–FQ4 default); design `docs/design/RRC-revision-region-continuation.md`
  §8 gates G1–G10, F1, F2; review `docs/reviews/RRC-review.md` (fix round WO-7); register R-990…R-996; V17-T10 ruling
  `docs/reviews/RRC-v17-t10.md` (R-996, `t07_reference_rrc.json` `621003a8…`); build decisions D-1…D-46 in
  `docs/RRC_DECISIONS.md`; gate numbers in `docs/RRC_HANDOFF.md` "Gates" and the WO-5/WO-7 decisions.

## Do

1. This is RRC's **first** manifest: `evidence/RRC/<full head sha>/manifest.json`, `work_package: "RRC"`, in the
   pattern of `evidence/OPT/c1b9b125…/manifest.json` and `evidence/X02/d26bcd38…/manifest.json` (on main). One check per
   design §8 gate (G1–G10, F1, F2) with its recorded result and where it is recorded (decision id or test file); a
   gate that has no recorded result is `unsupported` with the reason — never inferred. `status: "tested"` only if
   every gate is pass or an accepted, documented fail/unsupported; otherwise `implemented` and stop and report.
   `review` pending/pending (never `reviewed`).
2. `limitations`: from the design/ADR/review: L21 narrowed, L-COL-9 narrowed only on the failing-first column case
   (G5), not a superset of T06-revision-v2 (M2), the handoff's "Review notes left as notes", and the
   `results-ref-x86-64.json` missing key (D-30). No new claims.
3. If `origin/main` has moved since RRC's merge of it only by `docs/` commits, merge it; if any non-docs commit, stop
   and report.
4. Harvest: entries in `benchmarks/t08/support_envelope.yaml` as OPT's did; `scripts/t08_support_matrix.py --emit` then
   `--check`; `HARVEST_SIZE` in `tests/test_m07a_harvest.py` (comment line in the existing style, ≤ 120 chars); run
   `tests/test_m07a_harvest.py tests/test_t08*.py tests/test_evidence_manifests.py tests/test_rrc_*.py` — 0 failures
   (angle-bracket text in a manifest fails `test_evidence_manifests`: write "at most / at least"); F0
   `scripts/corpus_identity.py --check` PASS; `ruff check`, `ruff format --check`.
5. Commit named paths only, message `RRC: evidence manifest at <short sha> (tested); T08 harvest (...), HARVEST_SIZE
   (...)`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
   https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/RRC`. Do not merge into main.

TRS2 shared: `uptime` first; targeted tests only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 15 lines)

Manifest path and status, per-gate result table (one line), harvest counts and HARVEST_SIZE move, test counts, F0 line,
commit sha(s), anything stopped on.
