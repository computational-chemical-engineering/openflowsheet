# F0 build decisions (append-only)

Package F0, the corpus identity gate (roadmap 0.4, ADR 0057 D3; brief `docs/briefs/F0-build.md`). Build lane.

## 2026-11-05 — first engineer

- **D1. Corpus for M2–M6 = RC step 4's bundle set.** `scripts/t08_rc.py bundles-write` enumerates it (K05 SYN-001
  variants from `benchmarks/syn001/reference_values.yaml`, solved through the CLI; T07 W3a `ELIGIBLE` revisions under
  the default policy): 52 runs, 26 s. F0 imports those enumerations (`k05_registered_cases`, `g8_revisions`) and runs
  each exactly as step 4 does. Alternative: the K05 structural identity document (one run). Reversible by: editing
  `run_corpus()` and re-recording.
- **D2. M1 corpus = T07's 50 revisions** (`tests/t07_corpus.py` `CORPUS`), hashed with `revisions.content_hash`.
- **D3. M7 not implemented.** No 0.3.0 bundle is in the repository (only v0.0.0 and v0.1.1 fixtures). Proposed: write
  RC step 4's 52 bundles from a `git worktree` of tag `v0.3.0` and commit them as fixtures (4.3 MB of JSON, ~650 kB
  packed), then judge `reproduce_bundle(..., rerun=True)` verdict and mode per bundle (`step_bundles_replay`'s rule:
  `MATCH`, mode `exact_replay` or `compatible_reproduction`). Open for the caller: commit 4.3 MB of fixtures, or a
  K05-only subset (350 kB, 5 bundles), or build them from the tag at check time (fails on shallow CI clones).
- **D4. M8 not implemented.** Proposed: wrap the existing round-trip tests (`test_schemas_p01.py:422`,
  `test_k01_schemas.py:100`, `test_k03_schemas.py:83`, `test_k04_schemas.py:71`, `test_k05_schemas.py:69`,
  `test_t04_schemas.py:82`) by running them in a subprocess and registering each node id, so a removed case is a diff.
- **D5. M4 is judged only on the registered reference platform** (`benchmarks.t06.ensemble.machine_class()`, recorded
  as `ref-x86-64`); elsewhere it is reported `NOT JUDGED`, never `PASS` (K05: CI runners disagree in the last bits).
  The exit-2 test judges M4 regardless of host, since a moved state hash moved everywhere.
- **D6. M4 value per run:** the certificate's `target_state_sha256`, the count, and the digest of every
  `state_sha256`/`target_state_sha256` in the run's artifacts (sorted keys, list order): 1237 state hashes in 52 runs.
- **D7. M5 value per run:** outcome, verification status, number of checks, digest of the ordered (id, result) list.
- **D8. M6 "recorded request sample" = every key `ExactPropertyCache` computes during the corpus runs**, recorded by a
  wrapper that returns the original key unchanged (restored after). Only 15 of 52 runs use the cache (the tear path).
  No pre-existing recorded sample was found. Alternative: a committed request file replayed against each provider.
- **D9. M9 scope = files whose bytes enter an `implementation_sha256`**, found by an AST scan of `src/` (functions or
  attributes named `_implementation_sha256` that read `__file__` bytes, plus sibling `*.py` they name): 8 files
  (`thermo/{coolprop_heos,_coolprop_heos_fluids,iapws95,pr_c1,pr_lib,syn001,wilson_ig,wilson_ig_v2}.py`).
  **Open question:** unit-model modules self-hash into a model manifest's `artifact_hash` (`file_sha256(Path(__file__))`
  in `models/c1/*`, `models/syn001/*`, `models/thermal/*`, 30+ files). They are not `implementation_sha256`, so the
  brief's definition excludes them; S1's intent (legacy families byte-frozen) may include them. Default: excluded.
- **D10. `.gitattributes`:** `*.py *.pyi *.json *.yaml *.yml *.csv *.toml *.lock *.md text eol=lf`. `git add
  --renormalize .` changed nothing (3739 `i/lf`, 0 CRLF, 22 symlinks).
- **D11. A1 (corpus enumerable from existing registries):** held for M1–M6 and M9 (benchmark references, the release
  gate's bit-identity step and bundle set). The W27 snapshot (`benchmarks/m06/openidaes450/runs/w27-m07-83f825d`)
  holds agent-campaign records with no `content_hash`, run manifest or state hash: nothing for F0 to enumerate there.
  For M7, A1 is false today (no 0.3.0 bundles registered).

- **Gate run at 5fa16527 (2026-11-05):** `GATE FAIL`: 1 failed, 14844 passed, 3206 skipped, 197 deselected, 1 xfailed
  (1:57:47). ruff, format, mypy exit 0. The one failure is `test_f6_the_forty_runs_fit_their_budget` (V17's 40-run
  wall-time budget: 401.5 s > 300 s) on a host at load average ~49; F0 touches no `src/` file. Not re-run; a re-run on
  an idle host decides whether it is load. F0's own tests: 6 passed, 1 xfailed (strict) inside that run.

## 2026-11-05 — second engineer

- **D3 resolved (ruling: commit the fixtures).** `scripts/t08_rc.py bundles-write` run in a detached worktree of tag
  `v0.3.0` (b8f47a04), its own `src` on `PYTHONPATH` (`openflowsheet.__version__` 0.3.0), single-threaded, ref-x86-64:
  52 bundles (k05 5, g8 47; 49 CONVERGED/VERIFIED, 2 INITIALIZATION_FAILED, 1 HOMOTOPY_STALLED, the same mix as main),
  540 JSON files, 5.5 MB, no absolute path, no CRLF. Committed as `tests/fixtures/f0/v0.3.0-bundles/` (833e8093);
  tag worktree removed.
- **D12. M7 value per bundle = `verdict`, `mode`, `integrity_ok`** of `reproduce_bundle(rerun=True)` (RC step 5's call
  and run id). Reasons and differences are not registered (prose). Measured: 52 MATCH, `exact_replay`, intact, 47 s.
  Off the reference platform the mode is not judged (`decide_mode` makes it `compatible_reproduction` whenever the
  platform identity differs); verdict and integrity still are. Alternative: M7 `NOT JUDGED` off-reference, as M4 (D5).
  Reversible by: `M7_PORTABLE` and the M7 branch in `compare()`.
- **D13. M8 corpus = ten test functions** (`M8_FUNCTIONS`): D4's six plus the four other functions whose name says
  round-trip and whose body validates against a schema (`test_schemas_p01::test_component_record_round_trips`,
  `test_t07_types::test_each_typed_document_round_trips_through_its_schema`,
  `test_t07_w1f_followup::test_a_job_result_round_trips_through_its_schema`,
  `test_t07_w3e_solution_state::test_the_fixture_validates_round_trips_and_is_consistent`). Excluded: round trips with
  no schema check (`test_the_composite_results_round_trip`, `test_solve_policy_document_round_trips_byte_identically`,
  canonicalization and float round trips). Run in a subprocess with `t08_rc._Recorder`; every node id registered with
  its worst outcome: 105 passed, 8 s. A test asserts no registered node is other than passed. Reversible by: editing
  `M8_FUNCTIONS` and re-recording.
- **D14. M9 follows imports (D9 ruling).** `_hashed_files` also adds the file of an imported module whose `__file__` a
  hash scope reads, and, for a scope that reads another provider's `implementation_sha256`, every hash-site module the
  file imports; an unresolved composition raises. Only composition today: `wilson_ig_v2` → `wilson_ig` (already in the
  set). Registered set unchanged, 8 files. `artifact_hash` unit modules stay out (ruling).
- **Registry re-record for M7, M8:** `git diff` of `benchmarks/f0/corpus.json` = 371 insertions, 0 deletions.
