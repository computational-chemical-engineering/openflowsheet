# Brief — T08: land the review's fixes before W5; D1 → STR-04; the W5 CI job (not triggered)

**To:** `opus-engineer` (build lane). **From:** the session, 2026-09-29. **Branch:** `wp/T08` at `3eb6051`.
**Review (binding for this work):** `docs/reviews/T08-review.md` — findings S1–S7, notes N1–N7, rulings §3.1
(P-budget), §3.2 (P-trace), §3.3 (P-STR04), §4 (whether W5 may run). Design: `docs/derivations/T08-build-first-spec.md`
with Amendment 1.

## Items (one commit each; messages start `T08 …:`)

1. **S1, S2, S3** in `benchmarks/t08/ptc_r1/compare.py`, exactly as the review says (outcome stored before the
   step is read; B21's missing facts recorded — polish bound blocks, `RegionResult.budget`, attempts and property
   calls per run, summarised; `--run` refuses a dirty tree and refuses to overwrite `results-<machine>.json`).
   These are recording/safety changes only: the calls, arms, starts, classification and criterion do not change.
   Say in the commit body that `case.json` is unchanged and why that is admissible (review N1: it pins the harness
   by path; the method is fixed by `C_case`).
2. **S4** (`executor.py:762`): a warm-started region that ends before any attempt (the §6.2 kernel refusal at
   `region.py:1642`, the settle refusal at `region.py:1794`) records the warm start `rejected(opening:…)` and falls
   through, per §B2. Test it.
3. **S7** (`failure.py:301`): make `step_index` required for `region_bundle` (or otherwise close the zero-counter
   path as the review says). Test it.
4. **Amendment 2 transcription** (message `T08: build-first Amendment 2 — review rulings P-budget, P-trace`): append
   to `docs/derivations/T08-build-first-spec.md` an "Amendment 2 (2026-09-29, transcribed by the build lane from
   `docs/reviews/T08-review.md` §3.1–§3.2, design-lane rulings)" containing: the §A4.1 wording per §3.1; B21's
   added clauses (no run ends `BUDGET_EXHAUSTED` on property calls; every run opens exactly one attempt; either is
   `BLOCKED`, never `FAIL`) per S5/§3.1; the P-trace erratum per §3.2/S6 (B21's 1e-10 governs; the YAML's 1e-12 at
   `t08_build_first_reference.py:1062` is a transcription error; **the YAML and generator are NOT regenerated
   before `C_res`**, since the YAML's sha256 is in `case.json`). Quote the review's words; decide nothing new.
   Register it as **R-128** in `docs/decision-register.md` in the format of R-126/R-127.
5. **The W5 CI job, not triggered.** Add a `workflow_dispatch`-only input and job to `.github/workflows/ci.yml`
   that runs `python -m benchmarks.t08.ptc_r1.compare --run` on the same two machine classes as T06's `ensemble`
   job (follow that job's pattern at `ci.yml:184–240`: machine class, artifact upload). A push must never start it.
   **Do not push and do not dispatch** — the session does that after Frank's go-ahead.
6. **P-STR04 on the side branch** `wp/T08-d1-str05` (currently `18ccc00`, based on `f9a7f66`): first rebase it
   onto the new `wp/T08` tip (or merge; keep it a side branch), then implement §3.3's shared rewrite for
   STR-03/04/05 messages (binder unit ids → instance ids keeping `:<eq>[:<port>]` and `.<pin>` suffixes;
   binder-internal parameters as `<instance>.<param>`), tested with A10's rename pattern (no `U-…` id and no old
   instance id in any message), proved substitution-only like `18ccc00`. Report the combined identity move
   (`t07` key and whole K05 before → after) for Frank's single approval. **Do not merge it into `wp/T08`.**

## Forbidden — stop and report instead

- **No `compare.py --run`, no PTC run on the PTC-R1 flowsheet from any start, no Newton run from any registered
  start**, and no `results-*` file (W5 waits for Frank). The review's single LOW-root probe per arm is already
  recorded; do not repeat it.
- No change to `case.json`, `revision.json`, the arm policies, the YAML, the generators, ADRs, existing spec text
  (Amendment 2 is appended), `requirements.lock`, schemas or MCP tools/descriptions.
- On `wp/T08`: identity byte-equal (`measure_identity`: whole K05 `3ed2911b…`, `t07` `11bcb148…`, minus-`t07`
  `9a7b4e6d…`, structural `915c97e8…`, T02 floats `9a8a5baf…`, keys `t02`…`t06`).

## Working rules

Work in this checkout; nobody else edits it. Commit messages end with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`. Stage named paths only. Never set
`reviewed`. `.venv/bin/python`; quote the path. Budget: the user is near a weekly usage limit — targeted tests
while developing; the full `PATH=.venv/bin:$PATH ./scripts/check.sh` once at the end on `wp/T08`, and targeted
tests on the side branch.

## Report

Commits per item; `check.sh` counts; the side branch's head and its combined identity move; anything you stopped on.
