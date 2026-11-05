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
