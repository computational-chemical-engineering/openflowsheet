# Brief — T08 Phase 2b: [A10] refresh, mode-A hygiene, data provenance, the v0.0.0 bundle probe, A89 repeats

**To:** `opus-engineer` (build lane). **From:** the session, 2026-10-01. **Branch:** `wp/T08`.
**Design (binding):** `docs/derivations/T08-release-spec.md` §4.8 (V18), §6.1's A89 row, §9 rows **T08.A15, A30,
A31, A32, A35**, §15 items W1.6, W2.5, W2.6; ADR 0006 (distribution modes, D4/D5, the METIS remedy, Q1 LGPL); the
P03 audit (`scripts/p03_binary_inventory.py` and its evidence). Plus one test the V13 (e) verdict asked for.

## Items (one commit each; messages `T08 W…:`)

1. **W2.5 — T08.A30, A31, A32.** Generalize `scripts/p03_binary_inventory.py` per A30 (every compiled distribution of
   the default install and the `server` extra at the lock's versions; per object path, sha256, `DT_NEEDED`, notice
   attribution; the METIS closure unreachable from every project path). x86-64 runs locally; **aarch64 needs CI**:
   add a `workflow_dispatch`-only input + job (pattern: the `ptc-r1` job in `.github/workflows/ci.yml`) that runs the
   inventory on `ubuntu-24.04-arm` and uploads the result. Do not push or dispatch — the session does. Write the
   x86-64 result under `evidence/T08/artifacts/` (git-ignored) and a committed summary/digest file the test reads;
   the aarch64 half is filled in after the session dispatches. Any restrictive, non-LGPL GPL-family or unresolved
   object not dispositioned by ADR 0006 D4: **stop and report** (it goes to Frank as a licence reading). A31, A32 as
   tests.
2. **W2.6 — T08.A35.** A worktree at tag `v0.0.0` (`9a4391f`) with its own lock in a throwaway venv (outside the repo
   or in the session scratchpad `/tmp/claude-1003/-home-frankp-Codes-Process-Simulator/c1654ca5-cf40-4fac-b53a-1914bdd081e5/scratchpad/`);
   write the `SYN-001-nominal` bundle with the v0.0.0 CLI; commit that bundle as a test fixture if small (else hash-
   reference it); a test that today's `replay` returns a typed report (`inspected_archived_results` with `NOT_RUN`,
   or a typed refusal naming the schema version) and `inspect` renders it, no unhandled exception. Remove the
   worktree afterwards.
3. **W1.6 — T08.A15.** A `workflow_dispatch`-only CI job that repeats T06 A89's case (THM-09 start 2 under
   `T06-revision-v2`) 20 times on `ubuntu-24.04-arm` and records outcome, VERIFIED, S3's worst ratio and the
   refinement count per repetition; run it once locally on `ref-x86-64` and commit that record. Do not push or
   dispatch.
4. **V13 (e) gap:** a test that injects a refusal of the T03 §5.1 opening check for a warm candidate and shows the run
   records `warm_start_rejected(opening:…)` and falls through to the traversal (in `tests/test_t08_w4_warm_starts.py`).
   If the opening check cannot be made to refuse without changing numerics, stop and report.

## Rules

`requirements.lock` must not change. No schema, MCP, spec, ADR, reference-YAML or registered-result change. Identity
unchanged (`measure_identity`: whole K05 `7f32b143…`, `t07` `422aa7a5…`). Work in this checkout; nobody else edits
it. Messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`. Stage named paths only; never `git add -A`;
never commit large binaries (evidence artifacts are git-ignored; reference them by hash). `.venv/bin/python`; quote
the path. Budget: the user is near a weekly usage limit — targeted tests; full `PATH=.venv/bin:$PATH ./scripts/check.sh`
once at the end (expected green, except tests that need the aarch64 halves: make those skip with a clear reason until
the CI artifacts are committed, never pass vacuously).

## Report

Commits; inventory counts per architecture done; any licence finding; the v0.0.0 probe's outcome; the local A89
record; the two dispatch inputs' names; `check.sh` counts; questions.
