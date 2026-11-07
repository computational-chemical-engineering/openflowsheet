# X02 handoff (build lane) — after WO-4

Branch `wp/X02` (worktree `.claude/worktrees/x02`). Design: `docs/design/X02-warm-starts.md` (binding), ADR 0070
(Proposed). Choices: `docs/X02_DECISIONS.md` D-1…D-21. Run tests with `PYTHONPATH=src ../../../.venv/bin/python -m
pytest` from the worktree (the shared venv imports the main checkout otherwise).

## Done

- WO-1 Part C, WO-2 contract + explicit x₀ (earlier engineer).
- **WO-3** outer start: `couple(initial=)`, `CoupledStart`, integrity at resolution (`jobs/runner.py`
  `declared_coupled_start`), compatibility/bounds/opening in `solve_coupled`, `warm_start.coupling` + R0, replay
  (`_recorded_coupled_start`), trace messages (E9 producer, D-14). Tests `tests/test_x02_wo3_outer_start.py` (20).
- **WO-4** external plumbing: `build_request(start=)`, profile store, `start_capable`, backend `start.json` /
  `profile.json` check, runner export, `pinned_program` by hash, chaining in `solve_coupled`, `ExternalSource` /
  `external_starts`, `warm_start.external` + R0, replay, D8 disclosure. Synthetic warm child
  `tests/support/synthetic_warm_child.py`; tests `tests/test_x02_wo4_external.py` (14);
  `tests/test_x02_g0_experiment_keys.py` (163 requests, 0 differences).

## Gates measured

- G3 (stand-in): (a) `job_id` = J_c → 1 outer iteration, final w bitwise J_c's, 1 experiment (a cache hit);
  (b) J_c w + (0.01, 5 K) → VERIFIED, ‖Δû‖∞ = 0 ≤ bound 1.1e-15; (c) opening rejected, record byte-equal to a cold
  run's (loop with H₂ make-up 0.725, D-11); (d) compatibility rejection byte-equal; (e) replay MATCH ×3;
  (f) forged `declared` not MATCH.
- G0 after WO-3: F0 PASS M1–M9; battery 4158 passed / 1 failed (A33 inventory, fixed by D-14).
- G0 after WO-4: F0 PASS M1–M9 (unchanged counts); battery t07/t08/m02/m04/m05/m06/x02/a09 + G0 list 4620 passed,
  56 skipped, 1 failed (T07 G20 global-state allowlist, fixed by D-21: 39 passed on the touched files).

## Next

- **WO-5** (not started): `src/openflowsheet/adapters/pymrm/child_warm.py` per §5.6, provisional variant
  `benchmarks/x02/variant-s123w-provisional.json`, the workstation campaign G5a–e. `pinned_program` already selects
  `child_warm.py` by `runner_sha256` once the file exists (`CHILD_SCRIPTS` in `backends.py`).
- **WO-6**: MSG entries (tokens table at the end of the decisions log), register entries, progress, manifest,
  reviewer pass, full gate.

## Open for the reviewer (batched, not decided here)

R-950 provisional number; the c_4 clash with `wp/MSG`; the x₀ rejection-reason form (bare `integrity` in the x₀
record vs `warm_start_rejected(coupling_…)` in the coupling sub-record); D-11 (note's G3c premise false on the
registered loop); D-14 (E9 inventory row); the ulp round trip of a declared w₀ through u = w₀/s (D-13 observation).
