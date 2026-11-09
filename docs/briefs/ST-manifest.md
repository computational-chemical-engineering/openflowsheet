# Implementer brief: ST — evidence manifest and T08 harvest

Status: brief, 2026-11-09. Bounded build-lane item. **Do not spawn sub-agents yourself.** Start only when the
orchestrator gives you the CI run id (CI green on both architectures at the head named below).

## Where

Branch `wp/ST`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/st`, CI-green head `45122519` (full sha
`451225195aa30af51de139452c66f462904fa84e`) unless the orchestrator names another. Worktrees have no `.venv`: run
`/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with `PYTHONPATH=src`; confirm `openflowsheet.__file__` points into
the worktree. Serial tests (no xdist), `OMP_NUM_THREADS=1`.

## What was run (exact facts for `commands` / `checks`)

- Merge condition (CLAUDE.md "Gate by risk", Frank 2026-11-08): CI `ci.yml` run **given by the orchestrator** on the
  head: `check (ubuntu-latest)`, `check (ubuntu-24.04-arm)`, `identity`, `default-install` all success. No local full
  gate (not required; do not claim one — a gate only a full gate would give is `unsupported`, as OPT's G21 and RRC's
  FULLGATE).
- Spec: ADR 0068 Accepted (Frank Peters, 2026-11-08) with its dated D3 amendment; design
  `docs/design/ST-stream-table.md` §11 gates G1–G16; review `docs/reviews/ST-review.md` (fix round, rulings, WO-8a
  ruling 5, WO-8b ruling 6); register R-1000…R-1006; build decisions and measured numbers in `docs/ST_DECISIONS.md`
  (fix round, WO-8a, WO-8b, CI-1/CI-2, WO-7) and `docs/ST_HANDOFF.md`. WO-7 numbers: D_7 `553b7612…`, `without_st` = D_6
  `3fdc797a…`; 44 served 0.3.0 documents byte-identical; G7 41 bitwise; G8 0 failures, max 1.756e-4; G8u max 2.7027;
  caches 39; A20 23; catalogue 386 / 90 / 129, digest `03818ed5…`; F0 PASS. Description reviews: both lanes
  reviewed `get_stream_table` (Frank's human review recorded by Frank's own script; never edit it).

## Do

1. ST's first manifest: `evidence/ST/<full head sha>/manifest.json`, `work_package: "ST"`, in the pattern of
   `evidence/RRC/6b892b03…/manifest.json` and `evidence/OPT/c1b9b125…/manifest.json` (on main). `requirements`: only ids
   the schema accepts (`^[DA][0-9]{2}$` — RRC had to drop V20); take them from the design/ADR. One check per §11 gate
   (G1–G16) with its recorded result and where it is recorded (decision id, test file); a gate with no recorded result is
   `unsupported` with the reason — never inferred. Add the CI run and FULLGATE (`unsupported`) as RRC did.
   `status: "tested"` only if every gate is pass or an accepted, documented unsupported; otherwise `implemented` and
   stop and report. `review` pending/pending (never `reviewed`).
2. `limitations`: evidence class (software verification; the table is not a verification — `judged_at: projection`
   for all 52 corpus runs); the open design-lane defaults M1-1, M1-2, M1-3, S1-1; the review Notes left out of scope
   (handoff "Not done"); the ADR 0068 D3 amendment awaiting Frank's glance (board item, default stands); no local full
   gate. No new claims. No angle-bracket text anywhere (write "at most / at least").
3. If `origin/main` moved since ST's merge of it only by `docs/` commits, merge it; any non-docs commit: stop and report.
4. **Harvest (required):** classify every new manifest item (each limitation, each non-pass check) in
   `benchmarks/t08/support_envelope.yaml` in RRC's/MSG's form (`manifest`, `item`, `sha256` = `text_sha256` of the
   item, `class`, `to`, `note`); `scripts/t08_support_matrix.py --emit`, then `--check` = 0 problems; `HARVEST_SIZE` in
   `tests/test_m07a_harvest.py` with one comment line in the existing style (≤ 120 chars). Run
   `tests/test_m07a_harvest.py tests/test_t08*.py tests/test_evidence_manifests.py tests/test_st_*.py` — 0 failures;
   F0 `scripts/corpus_identity.py --check` PASS; `ruff check`, `ruff format --check`.
5. Commit named paths only, message `ST: evidence manifest at <short sha> (tested); T08 harvest (...), HARVEST_SIZE
   (...)`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
   https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/ST`. Do not merge into main.

TRS2 shared: `uptime` first; targeted tests only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 15 lines)

Manifest path and status, per-gate result (one line), harvest counts and HARVEST_SIZE move, test counts, F0 line,
commit sha(s), anything stopped on.
