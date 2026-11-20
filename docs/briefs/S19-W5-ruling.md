# S19 W5 identity ruling (design lane, `specifier`)

**Status:** ruling of the design lane, 2026-11-18, on brief `S19-W5-ruling.md` (git common dir `codehealth/briefs/`).
Sections 5 to 9 bind W5 where they stay inside decisions already taken (S19 Q1, ADR 0076 FQ-A). So does ruling R7
(3.3, finding F-2), a design-lane amendment of one test oracle that the orchestrator records in the register. Two
points go beyond those decisions and are **not decided here**: FR-1 (tier 3, run identities) and FR-2 ("once" or
"once per batch"), section 10. Each has a default so W5 can start. Section 11 is an ADR draft, status `proposed`.
**Base:** `wp/S19` at 8d31b89e. Every number below was measured there, on the reference platform `ref-x86-64`, by
the commands in section 3 and appendix A.
**Binding inputs:** `CLAUDE.md`; `docs/S19_RULES.md`; S19 decision Q1 (`docs/S19_DECISIONS.md:33-42`) and the
2026-11-15 entry "registry-hashed files wait for W5" (`:304-313`); ADR 0076 (accepted; affected requirements
`:31-56`, I-19 `:330-348`, acceptance "End of W5" `:462-463`, FQ-A `:487-488`); ADR 0060 (accepted; D3, D6, E-F1-4,
E-F1-5); ADR 0067 (proposed; D5); ADR 0007 D4 as implemented in `run/replay.py`; `docs/interfaces-frozen.md:30`;
`docs/F0_DECISIONS.md` D9, D14, D20.

---

## 0. The ruling in brief

1. The registry-hashed set has **51** files, not 45, and the 35 M9 files are a subset of it (section 2).
2. A comment-only byte change (section 3) moves the following, and nothing else: an `assessment/` file moves
   `registry_sha256` only; `thermo/pr_lib.py` or any of the 27 legacy unit modules moves one M9 key and
   `registry_sha256`; the six other providers' files (`pr_c1`, `iapws95`, `wilson_ig`, `wilson_ig_v2`,
   `coolprop_heos`, `_coolprop_heos_fluids`) also move `model_version` (M2) and `artifact_r0_sha256` (M3) of every
   registered run on their provider (pr-c1 1 run, iapws95 3, wilson-ig-v2 5, coolprop 0) and the provider's two M6
   sample keys; `thermo/syn001.py` moves M2 and M3 of 52 runs, 77 M6 keys and turns all 52 M7 replays into
   `MISMATCH`. M1, M4, M5, M8 and the MCP digest never move.
3. Q1's premise "M1 to M8 unchanged" holds for **tiers 1 and 2** (44 files). It fails for **tier 3** (6 thermo
   files): editing them re-registers run identities, which FQ-A and ADR 0076 ("Replay identity: unchanged") do not
   cover. That needs Frank (FR-1). **Tier 4** (`thermo/syn001.py`) is not edited in S19.
4. Re-registered per batch: M9 values of the edited files, the built-in registry identity, and (tier 3 only, after
   FR-1) M2 and M3 of the affected runs and M6 keys of the affected providers. One re-registration commit per
   batch, judged by its diff against a predicted key set. M7 is never re-registered.
5. Evidence per step: F0 fails exactly on the predicted keys and passes everything else bitwise. For tier 3, where
   predicted keys include run identities, an **identity pin** (F0 with the edited files' identity reads served from
   the batch-base bytes) must pass all nine measures against the unchanged registry. The CoolProp keys are the one
   exception once B7 has changed that provider's hash scope.
6. Batches: **N** (tier 1, `pr_lib.py`, the registry factory switch) first; **P** (tier 3 and B7) after FR-1;
   **L** (the 27 unit modules and the 34 `column_unit` bindings) after Frank's legacy ruling. Default for FR-2:
   batch N closes on `wp/S19-w5` and its merge into `wp/S19` waits for Frank.
7. G-END's "F0 and MCP digest identical" is restated in section 7. **The restatement changes a registered
   criterion**; the orchestrator takes it to Frank with FR-1 and FR-2.
8. B7 goes through its generator: `s07_reference.py` emits the table as eight modules and `--check` (C19) covers
   all eight. The CoolProp provider's hash scope names each of them (section 8). B7 is tier 3.
9. Findings from the full suite (3.3):
   - F-2: S10 A26 compares five providers with `main`, so any branch that edits `pr_lib.py` is red until it
     reaches `main`. Ruling R7 replaces the oracle with F0's registered M9 value (WO-1b, before WO-N3).
   - F-3: S11 A75 pins `wilson_ig.py`'s bytes.
   - F-4: L01 A22 pins `pr_c1.py` and all of `models/c1/`; moving them takes L01's registered-move route, which by
     precedent is Frank's.

---

## 1. Scope

This ruling covers how W5 may edit the files whose bytes enter a registered identity, and how those identities are
re-registered. It covers the 51 files of section 2 and the generator of `_coolprop_heos_fluids.py`. It does not
cover gate mechanics (queue modes, config changes: build lane, orchestrator). It does not cover the health recipes
of individual steps (S19 playbook and design note). It does not cover the legacy `models/` engine question, which
is Frank's.

---

## 2. The two file sets, measured

- **F** (F0 M9): `PYTHONPATH=src .venv/bin/python scripts/codehealth_frozen.py` lists 35 files,
  `corpus_identity.frozen_modules()` (`scripts/corpus_identity.py:715`). They are 8 `thermo/` providers
  (`coolprop_heos`, `_coolprop_heos_fluids`, `iapws95`, `pr_c1`, `pr_lib`, `syn001`, `wilson_ig`, `wilson_ig_v2`)
  and 27 legacy unit modules (`models/c1` 8, `models/syn001` 14, `models/thermal` 5).
- **R** (registry-hashed): the union of the implementation `modules` lists in
  `src/openflowsheet/registry/builtin/legacy.json` and `core.json`: **51** files, F plus the 16 files of
  `assessment/cost/` (10, `__init__` included) and `assessment/lca/` (6).
- F is a subset of R, as ADR 0060 E-F1-4 requires (the legacy implementation sets equal M9).

**Finding F-1 (record correction).** The 2026-11-15 entry (`docs/S19_DECISIONS.md:308`) says "these 45 files". Its
own per-group counts (10 + 6 + 8 + 14 + 5 + 8) sum to 51, and so does the measurement. The decisions log is
append-only: the orchestrator appends the correction. Nothing in W5 may rely on the figure 45. Every W5 set is
computed by a command (WO-0, `sets`), never copied from prose.

---

## 3. The experiment

### 3.1 Method

Fifteen detached scratch worktrees of 8d31b89e lived in the session scratchpad, outside the repository, and were
removed afterwards. Thirteen were probe trees, `x0` to `x12`. In each of `x1` to `x12` one line was appended to one
file: `# W5 identity experiment: a comment-only edit (never committed).`. Tree `x0` had no edit. In each probe tree,
appendix A's `probe.sh` ran four probes with the threads pinned to 1:

| probe | command (in the tree, `V=<main checkout>/.venv/bin`) |
| --- | --- |
| F0 | `PYTHONPATH=src $V/python scripts/corpus_identity.py --check --log <log>` |
| registry | `PYTHONPATH=src $V/python scripts/registry_builtin.py --check` |
| MCP digest | the `mcp_digest` tier of `.codehealth/config.toml:91-97` (`tests/test_t08_w2_surface_digest.py`, `tests/test_m07a_surface_chain.py`) |
| F1 trio | `pytest tests/test_f1_registry_core.py tests/test_f1_discovery.py tests/test_f1_builtin_identity.py` |

Two further trees ran the full default-marker suite. They used `.venv-testmap`, `-n 10` or `-n 12`,
`--timeout=900`, and ran `tests/test_t07_w2d_noncanonical.py` serially, as `test_impact.py`'s `XDIST_SERIAL`
requires. **xall** had four edits (`thermo/pr_lib.py`, `assessment/cost/sets.py`, `thermo/syn001.py`,
`models/syn001/flash.py`). **xall2** had all 50 files of R except `thermo/syn001.py`.

### 3.2 Result per edited file

`n/m` is F0's "failed of judged" for a failing measure. The F0 counts at the base are `M1 50, M2 61, M3 61, M4 61,
M5 61, M6 85, M7 52, M8 105, M9 35`.

| tree | edited file | F0 | moved F0 keys (measure: key) | registry `--check` | MCP digest | F1 trio |
| --- | --- | --- | --- | --- | --- | --- |
| x0 | none | PASS 9/9 | none | clean, `registry_sha256 f251447d06a6...` | 40 passed | 93 passed |
| x1 | `thermo/pr_lib.py` | M9 FAIL 1/35 | M9: the file | FAIL, `12534b86ad25...` | 40 passed | 4 failed |
| x2 | `assessment/cost/sets.py` | PASS 9/9 | none | FAIL, `d1908a39bce8...` | 40 passed | 4 failed |
| x3 | `thermo/syn001.py` | M2 FAIL 52/61, M3 52/61, M6 77/85, M7 52/52, M9 1/35 | M2, M3: all 52 `k05/*` and `g8/*` runs; M6: 62 sample and 15 trail keys; M7: all 52 bundles `MISMATCH` (mode `exact_replay`, integrity true); M9: the file | FAIL | 40 passed | 4 failed |
| x4 | `models/syn001/flash.py` | M9 FAIL 1/35 | M9: the file | FAIL | 40 passed | 4 failed |
| x5 | `thermo/pr_c1.py` | M2 1/61, M3 1/61, M6 2/85, M9 1/35 | M2, M3: `m02/C1-FLASH-F1-M02-v1`; M6: `sample/provider/pr-c1-v1/{evaluate_phase,flash}`; M9: the file | FAIL | 40 passed | 4 failed |
| x6 | `thermo/iapws95.py` | M2 3/61, M3 3/61, M6 2/85, M9 1/35 | M2, M3: `s11-th/TH-C1`, `TH-R1`, `TH-V1`; M6: `sample/provider/iapws95-v1/{evaluate_phase,flash}`; M9 | FAIL | 40 passed | 4 failed |
| x7 | `thermo/wilson_ig.py` | M2 5/61, M3 5/61, M6 2/85, M9 1/35 | M2, M3: `s11-gp/GP-C1`, `GP-C2`, `GP-C3`, `GP-M1`, `GP-M2`; M6: `sample/provider/wilson-ig-v2/{evaluate_phase,flash}`; M9 | FAIL | 40 passed | 4 failed |
| x8 | `thermo/coolprop_heos.py` | M6 2/85, M9 1/35 | M6: `sample/provider/coolprop-heos-v1/{evaluate_phase,flash}`; M9 | FAIL | 40 passed | 4 failed |
| x9 | `models/c1/flash.py` | M9 FAIL 1/35 | M9: the file | FAIL | 40 passed | 4 failed |
| x10 | `models/thermal/heater.py` | M9 FAIL 1/35 | M9: the file | FAIL | 40 passed | 4 failed |
| x11 | `thermo/wilson_ig_v2.py` | M2 5/61, M3 5/61, M6 2/85, M9 1/35 | M2, M3: the five `s11-gp` runs of x7; M6: `sample/provider/wilson-ig-v2/{evaluate_phase,flash}`; M9 | FAIL | 40 passed | 4 failed |
| x12 | `thermo/_coolprop_heos_fluids.py` | M6 2/85, M9 1/35 | M6: `sample/provider/coolprop-heos-v1/{evaluate_phase,flash}`; M9: the file | FAIL | 40 passed | 4 failed |

In every moved M2 entry only `model_version` changed. Within it, only the label's `<implementation_sha256[:12]>`
field changed; `constants_sha256` and the digest after `@` did not (checked on x3, x5, x6, x7). The four F1 tests
that fail on every edit are `test_f1_discovery.py::test_the_generator_writes_without_building_the_process_registry`,
`test_f1_builtin_identity.py::test_e_f1_5_the_built_in_registry_sha256_is_the_committed_constant_in_fresh_processes`,
`::test_sf_8_skipping_the_validation_changes_no_identity` and
`::test_sf_8_a_reformatted_table_is_validated_in_full_and_keeps_its_identity`. The registry tables themselves did
not change in any tree: `--check` failed only on the `builtin-sha256.txt` line.

### 3.3 Tests that move (full suite)

**xall** (four edits, `thermo/syn001.py` among them): 198 failed, 20131 passed, 107 skipped, 3 xfailed in 1112 s.
The largest groups are `test_m06_wo1_structure_index.py` (94) and `test_t07_w5c_signatures.py` (56), then 7
`test_f0_corpus_identity.py`, 6 `test_t08_rename_substitution.py`, 4 `test_t08_w1_identity_substitution.py`, 4
`test_opt_replay.py`, and 27 more in 18 files. They are almost all fixtures that carry the SYN-001 provider's
`[:12]`. This is tier 4's reach in the suite, and it is why tier 4 is excluded.

**xall2** (all 50 files of R except `thermo/syn001.py`): 27 failed, 20302 passed, 107 skipped, 3 xfailed in 852 s.
The serial file passed (95). The 27 failing node ids were then rerun in `x0` and in every single-edit tree. In `x0`
all 27 pass, so every failure is caused by an edit. The attribution, by single-edit tree:

| group | tests (count) | tripped by | what re-records it at K |
| --- | --- | --- | --- |
| G1 registry identity | `test_f1_builtin_identity.py`: `test_e_f1_5_...`, `test_sf_8_skipping_...`, `test_sf_8_a_reformatted_...`; `test_f1_discovery.py::test_the_generator_writes_without_building_the_process_registry`; `test_f1_legacy_builtins.py::test_the_generator_check_is_clean` (5) | every edit of R | `registry_builtin.py --write` |
| G2 F0 itself | `test_f0_corpus_identity.py`: `test_every_implemented_measure_passes`, `test_the_gate_passes`, `test_exit_4_one_byte_in_a_frozen_module_fails_m9_by_name[models/]` and `[thermo/]` (4) | every edit of F (`[thermo/]` not by x12) | `corpus_identity.py --record` |
| G2' F0's M6 | `test_f0_corpus_identity.py`: `test_m6_the_request_sample_recomputes_without_solving`, `test_m6_judges_the_run_trails_only_on_the_reference_platform` (2) | tier 3 only | `corpus_identity.py --record` |
| G3 immutability guards of other packages | `test_s10_provider.py::test_a26_the_other_providers_are_byte_identical_to_main` | pr_lib, pr_c1, iapws95, coolprop_heos | finding F-2: needs an amended oracle first |
| | `test_s11_wilson_v2.py::test_a75_v1_is_not_edited` | wilson_ig | finding F-3: S11 A75's constant `WILSON_V1_SHA256` (`:55`) |
| | `test_l01_records.py::test_a22_the_c1_files_are_byte_identical_to_the_l01_base` | pr_c1, models/c1 units | finding F-4: L01's registered-move route |
| | `test_l01_records.py::test_a22_pr_c1_describes_the_same_identity` | pr_c1 | follows F-4's `MOVED` entry (`a22_expected`) |
| G4 regression fixtures carrying a provider identity | `test_t07_w5c_signatures.py::test_binding_outcome_is_unchanged[...]`: `M02:C1-FLASH-F1-M02-v1`, `-HEATER-`, `-LOOP-`, `-MIXER-`, `-REACTOR-`, `C1-SURROGATE-M04-v1` (6) | pr_c1 | its own regenerator, `python tests/test_t07_w5c_signatures.py` (prints `EXPECTED`) |
| | the same test, `[S11:C-MW]`, `[S11:GP-M1]` (2) | wilson_ig, wilson_ig_v2 | the same |
| | the same test, `[S11:TH-C1]`, `[S11:TH-R1]` (2) | iapws95 | the same |
| | `test_st_cli.py::test_th_c1_golden[json]` | iapws95 | the golden under `tests/fixtures/st/`, by substitution of the `[:12]` only (R5) |
| G5 experiment artifact | `test_m07_journey.py::test_a21_the_carry_identity_is_the_determining_files_at_the_anchor_and_j` | every tree | none. `carry_identical` requires a clean working tree (`scripts/m07_journey.py:764-775`), and the experiment's edits were uncommitted. It is not an identity reach and is not in any L. |

So the measured lists at 8d31b89e, before WO-1 re-measures them at each batch base, are:
- **L_N** = G1 + G2 + S10 A26 (10 tests);
- **L_P** = G1 + G2 + G2' + S10 A26 + S11 A75 + both L01 A22 tests + G4 (26);
- **L_L** = G1 + G2 + L01 A22 (c1 files) (10).

The unit modules of `models/syn001` and `models/thermal` trip only G1 and G2. No S07 test failed on any edit,
`_coolprop_heos_fluids.py` included. C19, the table's byte check, lives in `s07_reference.py --check`, not in the
suite.

**Findings from the suite.**

- **F-2 (S10 A26's oracle is `main`).** `test_s10_provider.py:658-670` compares the working-tree bytes of
  `UNTOUCHED = (syn001, pr_c1, pr_lib, iapws95, coolprop_heos)` (`:649`) with `main` or `origin/main`. CI fetches
  the full history (`.github/workflows/ci.yml:93`, `fetch-depth: 0`), so the test runs there too.
  - Any branch that edits one of those files is red until it is merged into `main`. But merging into `main`
    requires CI green: the condition is circular.
  - **Ruling R7 (design lane):** before the first edit of an UNTOUCHED file (WO-N3), A26's oracle becomes F0's
    registered M9 value. For each name, the SHA-256 of `src/openflowsheet/thermo/<name>` must equal
    `benchmarks/f0/corpus.json`'s `measures.M9["src/openflowsheet/thermo/<name>"]`. The skip without a `main` ref
    goes.
  - The check stays exact byte equality with a registered value. It moves only with a judged re-registration
    (W5-K2), so it is not relaxed. It is one test change outside the gate, read by a `reviewer` (WO-1b). The
    orchestrator records it in the register as an amendment of S10 A26.
- **F-3 (S11 A75: "v1 is not edited").** `test_s11_wilson_v2.py:137-140` pins `wilson_ig.py`'s SHA-256
  (`WILSON_V1_SHA256`, `:55`). V03 D-1 (`docs/V03_DECISIONS.md:24-30`) already rejected an edit to v1 because it
  would break S11.A75 and move both Wilson providers' identities. Editing `wilson_ig.py` in batch P therefore amends
  S11's assertion A75 to "v1 is not edited since <K of batch P>", with the constant re-based at K. That is part of
  FR-1's cost.
- **F-4 (L01 A22 pins `pr_c1.py` and all of `models/c1/`).** `test_l01_records.py:389-455` pins 18 files: `pr_c1.py`,
  `thermo/conventions.py`, every `models/c1/*.py` (the 8 unit modules and 5 that are not hashed), and three data
  files. L01 already has a route for a registered move (spec §15.3 (g), R-983, `a22_move_problems` at `:465-481`):
  a `MOVED` entry with a register ruling whose heading states the moved SHA-256. Its one precedent, R-983 for
  `models/c1/flash.py`, was Frank's decision (Q-WIT-2, 2026-11-08). So the W5 moves of `pr_c1.py` (batch P) and of
  the c1 unit modules (batch L) take that route: one register ruling per batch, listing every moved SHA-256, filed
  with K. By precedent they are Frank's: FR-1 covers P, and the legacy ruling covers L.

### 3.4 Answers to the brief's questions

- **M2.** Yes. A provider's `implementation_sha256` enters `model_version` through the label
  `...-<provider_id>-<implementation_sha256[:12]>-<data_sha256[:12]>` (`models/revision_flowsheet.py:1006-1011`,
  `models/syn001/flowsheet.py:207-212`; also `column_compile.py:255`, `cascade_solve.py:269`). It does not enter
  `constants_sha256`.
- **M3.** Yes. `artifact_r0_sha256` hashes the R0 projection, and R0 carries `model_version` as a structural digest
  compared exactly (`run/compare.py:82`, `STRUCTURAL_DIGEST_FIELDS`).
- **M4.** No. `state_sha256` covers the state vector only (`docs/interfaces-frozen.md:30`). Twelve edited trees
  reproduced M4 61/61 bitwise.
- **M6.** Yes, through the exact cache key, which carries `implementation_sha256` (`thermo/cache.py:184`) and the
  context's `model_version`. For tier 3, only the provider sample keys moved: the m02 and s11 runs key no exact
  cache (`n_keys` 0 in the registry), so their trails are empty, and the sample is F0's only M6 view of those
  providers.
- **M7.** Yes, for `thermo/syn001.py` only, because all 52 v0.3.0 bundles are SYN-001 runs. Replay chooses its mode
  from the environment before anything runs: lock, platform, BLAS, threads (`run/replay.py:86-130`). The mode
  stays `exact_replay`. The verdict compares R0 with `model_version` exactly, so it becomes `MISMATCH`. A unit
  module's `artifact_hash` and `registry_sha256` reach no M7 value: M7 stayed 52/52 in x1, x2, x4, x9, x10.
- **Replay of bundles written before a re-registration.**
  - A v1 bundle (every bundle in the tree, the 0.3.0 set included) whose `model_version` carries the old
    `[:12]` of an edited provider replays as `exact_replay`/`MISMATCH` from then on, or
    `compatible_reproduction`/`MISMATCH` on the other platform. Replay reports this as a structural difference,
    which is "a defect and never noise" (`run/replay.py:14-16`). Nothing in the report distinguishes it from a real
    change of the equations.
  - A v1 bundle on an unedited provider is unaffected. So is every v1 bundle after a tier 1 or tier 2 edit: v1
    manifests record neither `registry_sha256` nor a unit's `artifact_hash` in R0.
  - v2 bundles (ADR 0067, proposed; not built at 8d31b89e, there is no `run/replay_v2.py`) record
    `extensions_used` with each built-in's `self_sha256`. A v2 bundle written before any W5 registry change, tier 1
    included, would replay `compatible_reproduction` with reason `extension_changed` (ADR 0067 D5 step 5). At
    8d31b89e no such bundle exists in the tree.

---

## 4. The four tiers (identity reach)

| tier | files (count) | registered identities a byte change moves (measured) | below health 7.0 at 9f41b5ed |
| --- | --- | --- | --- |
| 1 registry only | `assessment/cost/*.py` (10), `assessment/lca/*.py` (6): 16 | `registry_sha256` (core.json contributors' `self_sha256`), E-F1-5's constant, the tests of 3.3 | cost/contributor 2.8, cost/sets 4.7 |
| 2 M9 and registry | `thermo/pr_lib.py`; the 27 unit modules (`models/c1` 8, `models/syn001` 14, `models/thermal` 5): 28 | one M9 key per file, `registry_sha256`, the tests of 3.3 | pr_lib 6.9; column_unit 4.9, conversion_reactor 6.6, kinetic_cstr 6.8, mixer 6.9 |
| 3 run identity | `thermo/pr_c1.py`, `iapws95.py`, `wilson_ig.py`, `wilson_ig_v2.py`, `coolprop_heos.py`, `_coolprop_heos_fluids.py`: 6 | as tier 2, plus M2 `model_version` and M3 of every registered run on the provider (pr-c1 1, iapws95 3, wilson-ig-v2 5, coolprop 0) and its two M6 sample keys; the tests of 3.3 | pr_c1 4.6, iapws95 6.2, coolprop_heos 6.4, wilson_ig 6.9; B7 `huge_file` |
| 4 excluded | `thermo/syn001.py`: 1 | M2 and M3 of 52 runs, 77 M6 keys, all 52 M7 verdicts; its `[:12]` occurs in 427 committed files outside `src/` and `docs/` (307 under `tests/fixtures/f0/`) | none |

**Rules behind the tiers** (WO-0's `sets` applies them, and refuses to emit if one fails):

- A file is tier 4 if it is attributed to a provider whose `implementation_sha256[:12]` occurs in a file of M7's
  corpus (`tests/fixtures/f0/v0.3.0-bundles`).
- A file is tier 3 if it is attributed to a provider, directly or through a composed hash, whose
  `implementation_sha256[:12]` occurs in a registered M2 `model_version`, or whose id is in `M6_PROVIDERS`
  (`scripts/corpus_identity.py:70`).
  `wilson_ig.py` is attributed to `wilson-ig-v1` and, through `wilson_ig_v2.py:117-118`, to `wilson-ig-v2`.
  `_coolprop_heos_fluids.py` is attributed to `coolprop-heos-v1` (`coolprop_heos.py:249`).
- Any other file of F is tier 2, and any file of R outside F is tier 1.
- Executable claim T-2a: no unit module's `artifact_hash` (64 hex, or its first 12) occurs in a registered M2 to M8
  value or in M7's corpus. (The c1 unit hashes do occur in `tests/test_l01_records.py`, which is L01 A22 in 3.3.
  `reactor_standin.py`'s hash also occurs in two schema fixtures under `tests/fixtures/schemas/experiment_coupling/`,
  but no test compares those with the live file: xall2 edited `reactor_standin.py` and no schema test failed.)

`thermo/syn001.py` is excluded because no behaviour-identical edit can keep M7. Its health is not below 7.0, so
G-END does not need it.

---

## 5. The ruling

**R1. What is re-registered.** In a batch with edited set E, exactly the registered values that are functions of
E's bytes are re-registered, and nothing else:

1. M9 values of the files in E ∩ F. M9 keys change only in B7 (section 8).
2. The built-in registry identity: `tests/fixtures/registry/builtin-sha256.txt`; and `registry/builtin/legacy.json`,
   `core.json` and `tables.sha256` where the batch changes table content (the factory switch of WO-N4, B7's
   implementation set, a contributor's implementation set after a tier 1 split).
3. For tier 3 only, and only once FR-1 admits it: M2 `model_version` and M3 `artifact_r0_sha256` of the runs on an
   edited provider, and that provider's M6 keys.
4. The test fixtures and test constants of the batch's list L that carry one of those values.

M1, M4, M5 and M8 are never re-registered in W5. M7 is never re-registered in W5. A W5 step or batch that moves M7
stops and goes to the design lane.

**R2. Evidence that nothing else moved.** Per step, the unpinned F0 must fail on exactly the predicted keys (W5-S3),
both ways: no predicted key may hold, and no other key may move. Per batch, the diff of the re-registration
commit must equal the predicted set (W5-K2). Where the predicted keys include run identities (tier 3), the
predicted-key check cannot see a behaviour change hidden behind a moved identity. Example: an R0 field that changed
inside an M3 hash that was due to change anyway. Tier 3 therefore also needs the **identity pin** (W5-S2): F0 runs
in one process, and every binary read of a pinned file through `pathlib` (`Path.read_bytes`, `Path.open("rb")`)
returns the bytes of that file at the batch base. Imports do not go through `pathlib`, so the interpreter still
runs the head's code, while every identity read sees the base bytes. If the code is behaviour-identical, the
pinned F0 is identical to the base: PASS on all nine measures against the unchanged registry. Tiers 1 and 2 need
no pin, because no identity they move reaches M1 to M8.

**R3. Batches.** A batch is a sequence of steps on the W5 branch `wp/S19-w5`, from one batch base B to one
re-registration commit K.

- The admitted set of each batch is fixed at B and recorded in the batch brief.
- No step re-registers anything. Every step is judged against the registry at B.
- The batches:
  - **N**: tier 1, `thermo/pr_lib.py`, and the registry factory switch of ADR 0076 I-19 (`MODEL_BUILDERS`).
  - **P**: tier 3 and B7, after FR-1.
  - **L**: the 27 unit modules and the 34 `column_unit.py` bindings of the I-19 inventory, after Frank's legacy
    ruling.
- Tiers do not mix across batches. N comes first. P and L are independent of each other.
- Whether each batch's K merges on its own or all close together is FR-2.

**R4. No identity hole.** At every W5 step, take every file h of R at B that the step edits:

- Every `openflowsheet` module that h imports at head must either have been imported by h at B, or be inside h's
  hash scope at head.
  - Providers: a sibling `*.py` named by a string literal in the `_implementation_sha256` scope, which is the idiom
    M9's scan resolves (`corpus_identity.py:597-643`).
  - Tier 1: a module under `assessment/cost/` or `assessment/lca/`, which are the contributors' implementation
    sets (`scripts/registry_builtin.py`, D7).
  - The one other allowed new edge is a retarget: h imports names from a module M that h did not import at B, and
    for every such name n, h at B already took the same object through a re-export (`M0.n is M.n` at B, with M0
    the module h imported n from). These are the I-19 W5 rows. They add no code to h's dependencies, because the
    object and its home were already behind the re-export.
- Moving code out of a hashed file into a module outside its scope is forbidden. Such a move lets behaviour change
  later without the identity changing, and preventing that is the reason the identity exists.
- Consequences:
  - Providers and unit modules are improved by edits inside the file: function extraction, simplification,
    deduplication within the file. They are not split in W5; B7 is the one exception, and it is data. This also
    keeps the pin valid: it serves base bytes, and a file whose hash scope has changed has no base form.
  - Tier 1 files may be split within their directory.
- Pre-existing imports of unhashed modules are not W5's to change.

**R5. Re-record commands** (at K only, on `ref-x86-64`; `--record` refuses elsewhere, `corpus_identity.py:842-848`):

```
PYTHONPATH=src .venv/bin/python scripts/corpus_identity.py --record     # corpus.json and m6-requests.json
PYTHONPATH=src .venv/bin/python scripts/registry_builtin.py --write     # tables, tables.sha256, builtin-sha256.txt
```

Each L fixture is re-recorded by its committed generator. A literal identity constant in a test file, such as an
expected hash prefix, changes by substitution of the old value for the new one only. W5-K1 checks that the
commit's diff holds nothing else. Records are never rewritten: `evidence/**`, `release/rc-trees/**` and the
decision documents that quote old hashes stay as written.

**R6. Review.**
- One fresh `reviewer` per batch, over B..K, before the merge.
- Its brief holds this ruling, the batch brief, and every step's W5-S2, W5-S3 and W5-S6 lines.
- The S19 cadence for the tier S1 thermo providers still applies inside batch P: a reviewer every three accepted
  steps, under the design note's float-order rules.
- The batch pass reads every diff of a hashed file for behaviour identity, checks R4, and reads K's diff against the
  prediction.

---

## 6. Numbered checks

All checks are exact: set equality, byte equality or an exact summary line. The tolerance is zero, and the floor is
zero too: identities are hashes compared as strings; M4 is bitwise on the reference platform, and the experiment
reproduced it in 12 of 12 independent processes; `registry_sha256` is deterministic across `PYTHONHASHSEED`
(E-F1-5). Any nonzero tolerance would admit an identity change, which is the error these checks exist to catch.
Off the reference platform F0 does not judge M4, M6's run trails or M7's mode (`corpus_identity.py:782-800`). So
W5-S2, W5-S3, W5-K2 and W5-K5 run on `ref-x86-64`, and CI covers the other leg through F0's portable measures.

### 6.1 Tool acceptance (WO-0)

- **W5-T1** `w5_identity.py sets --check` exits 0 at 8d31b89e and reports |R| = 51, |F| = 35, F ⊂ R, and tier
  counts 16 / 28 / 6 / 1 with the files of section 4. It exits 1 and names the failing assertion when F ⊄ R, when
  T-2a fails, or when a tier disagrees with section 4's rules. Falsifier: a copy of `legacy.json` with one module
  removed makes it exit 1.
- **W5-T2** For each of x1 to x12, WO-0 re-runs appendix A's probe on that single comment-only edit at 8d31b89e.
  `w5_identity.py predict --base 8d31b89e --files <f>` must return exactly the moved keys of that re-run's F0 log,
  as sets per measure in both directions, together with the registry change. The per-measure counts must equal 3.2's
  row. For x0 it returns the empty set. The re-measurement, not this document, is the reference: the experiment's
  logs were scratch files.
- **W5-T3** (batch P only; the pin) For x5, x6 and x7, `w5_identity.py pin --base 8d31b89e --
  scripts/corpus_identity.py --check` prints exactly
  `F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35`. The same
  trees unpinned print 3.2's line.
- **W5-T4** (pin mutation control) A one-literal behaviour change in `thermo/pr_c1.py` on the path the m02 run takes
  (WO-0 names the literal and shows the m02 run reads it) makes the pinned F0 FAIL, with at least one of M3, M4 or
  M5 failing on `m02/C1-FLASH-F1-M02-v1`. This proves the pin serves identity reads, not the code.
- **W5-T5** (pin vacuity and reach)
  - The pin records every pinned read with its caller.
  - It exits 3 with `PIN VACUOUS <path>` if a pinned path was never read.
  - It exits 3 with `PIN FOREIGN READ <path> <caller>` if a pinned read comes from outside the identity sites
    measured at 8d31b89e: each provider's `_implementation_sha256`, the two Wilson constructors,
    `canonical.file_sha256` called from a unit's `_artifact_hash`, `registry.selfhash.file_sha`, and
    `corpus_identity.m9`. WO-0 commits that list.
- **W5-T6** `w5_identity.py judge --before <rev> --after <rev>` on synthetic registries:
  - only predicted keys changed: PASS;
  - one unpredicted key also changed: FAIL naming it;
  - one predicted key unchanged: FAIL, `predicted, not moved`.
- **W5-T7** `w5_identity.py coverage --base 8d31b89e` reports 0 at the base. It reports 1 when a scratch copy of
  `thermo/pr_lib.py` gains an import of a function from an unhashed module. It reports 0, listing one retarget, when
  a scratch copy of `assessment/cost/index.py` imports `Refusal` from `assessment.linearization` instead of
  `assessment.program`.

### 6.2 Every W5 step (against the batch base B)

- **W5-S1 Scope.** `git diff --name-only B..HEAD` is a subset of the batch's admitted set, plus the files the
  batch's generator writes, plus the retarget files the batch brief names. It contains no tier 4 file.
- **W5-S2 Pin** (batch P only). `w5_identity.py pin --base B -- scripts/corpus_identity.py --check` pins every file
  of E whose hash scope is unchanged since B. It prints `F0 PASS` with B's counts (at 8d31b89e, W5-T3's line).
  - From the B7 step on, the CoolProp files are not pinned: B7 changes their hash scope, so they have no base form.
    The pinned F0 then fails on exactly the CoolProp keys: M6 `sample/provider/coolprop-heos-v1/{evaluate_phase,flash}`,
    M9 `coolprop_heos.py` and `_coolprop_heos_fluids.py`, and the seven new table modules as "measured, not
    registered".
  - No F0 run exercises `coolprop-heos-v1`, so for the B7 and `coolprop_heos.py` steps the behaviour evidence is
    B7-C1 to B7-C4 (section 8).
- **W5-S3 Exact moved keys.** The failing (measure, key) pairs of the unpinned `corpus_identity.py --check` log
  equal `w5_identity.py predict --base B` for E = `git diff --name-only B..HEAD` ∩ R.
  - M1, M4, M5, M7 and M8 PASS in every batch.
  - In batches N and L, M2, M3 and M6 PASS too, and the summary line is `F0 PASS` (no F file edited) or
    `F0 FAIL: M1 50/50, ..., M8 105/105, M9 FAIL k/35` with k = |E ∩ F|.
- **W5-S4 Registry.**
  - `registry_builtin.py --check` differs from B only on the `builtin-sha256.txt` line, and on the JSON pointers the
    batch predicts: the units' factory `module` pointers for WO-N4; coolprop-heos-v1's implementation `modules`
    for B7; a contributor's implementation `modules` in `core.json` when a tier 1 split adds a module to its
    directory; and none otherwise.
  - The line is present if and only if E is non-empty.
  - A pointer that differs and was not predicted means a descriptor's payload moved, that is a `describe()` or a
    signature changed. That is a behaviour change, and it stops the step.
- **W5-S5 MCP digest.** The `mcp_digest` tier reports `40 passed`. The two test files are byte-identical to
  d90b498f, unless changed by a merge of `main`.
- **W5-S6 Tests.**
  - The tests tier's failures are a subset of L_B ∪ the standing failures measured at B. L_B is registered in the
    batch brief, and the standing failures include the B-6 set.
  - Every other test passes.
  - L_B is the union of two lists: the tests that fail at B with all admitted hashed files comment-edited (the
    method of 3.1), and the tests the batch brief names for its changes to non-hashed files (WO-N4's factory
    switch).
  - L_B is not vacuous: every test in it fails before K, and passes at K.
- **W5-S7 Coverage (R4).** `w5_identity.py coverage --base B` reports 0 new import edges from an edited hashed file
  to a module outside its hash scope, other than retargets that pass R4's object-identity test at B (each one
  listed, with its name and old and new module). M9's key set at head equals M9's at B; B7 is the only exception.
  Falsifier for WO-0: a hashed file given a new import of an unhashed module's function makes it report 1.
- **W5-S8 S19 step rules.**
  - Debt strictly lower for a refactor.
  - `patch_noop.py` 0 flagged.
  - The playbook rules.
  - For tier S1 thermo files, no change in the order of floating-point operations (`docs/S19_RULES.md`
    "Rejected").

### 6.3 Every batch close (commit K)

- **W5-K1 Content.** K changes only:
  - `benchmarks/f0/corpus.json`;
  - `tests/fixtures/registry/builtin-sha256.txt`;
  - `src/openflowsheet/registry/builtin/{legacy.json,core.json,tables.sha256}`;
  - the files of L_B's fixtures and constants (R5). At 8d31b89e these are: `EXPECTED` in
    `tests/test_t07_w5c_signatures.py`, by its regenerator; the TH-C1 JSON golden under `tests/fixtures/st/`, by
    substitution; `WILSON_V1_SHA256` in `tests/test_s11_wilson_v2.py`, by substitution (F-3); and the `MOVED`
    entries of `tests/test_l01_records.py`, with their ruling in `docs/decision-register.md` (F-4).

  It changes no other file under `src/` and no test assertion. `--record` rewrites `benchmarks/f0/m6-requests.json`
  too, and that file must come out byte-identical. A request entry (`m6_entry`, `corpus_identity.py:343-369`)
  records provider id, components, state and context, never `implementation_sha256`. The only runs that key the
  cache are SYN-001 runs (tier 4). So no admitted edit can change an entry, and a change there stops the batch.
- **W5-K2 Judge.** `w5_identity.py judge --before B --after K` prints PASS:
  - the changed (measure, key) pairs of `corpus.json` equal `predict --base B` for the batch's E;
  - every predicted value changed;
  - every other value is JSON-equal;
  - `format`, `reference_platform`, `corpus` and `archived_outputs` are unchanged.
- **W5-K3 Clean at K.**
  - `corpus_identity.py --check` prints `F0 PASS` on all nine measures, with B's counts; B7 adds 7 M9 keys in batch
    P.
  - `registry_builtin.py --check` is clean.
  - The `mcp_digest` tier passes.
- **W5-K4 Suite at K.**
  - The full suite is green apart from B's standing failures.
  - `patch_noop.py` reports 0.
- **W5-K5 Pin at K** (batch P). `pin --base B -- corpus_identity.py --check` against the registry at B gives the
  same result as W5-S2 at the last step: `F0 PASS`, or exactly the CoolProp keys once B7 is in. K changed no code,
  so this confirms that the re-registered values are the only difference.
- **W5-K6 Review.** A fresh `reviewer` over B..K returns `merge`. A rejected step is reverted and logged.
- **W5-K7 Exceptions gone.** At K, `.claude/skills/s19-refactor/i19_scan.py` shows no W5 exception row that belongs
  to the batch:
  - N: `assessment.program.Refusal` in the eight contributor files. `application.revision_binding.MODEL_BUILDERS`
    goes in WO-N6, after K, because the committed table must first point at its new home;
  - L: the 34 bindings `column_unit.py` takes through `models.syn001.cascade`, `.column`, `.column_solve` and
    `orchestrator.region`.
- **W5-K8 Merge.** CI is green on both legs (G-END-CI). After a merge into `main`, `corpus_identity.py --check` runs
  on `main`.

---

## 7. G-END's F0 clause, restated

The registered G-END criterion (`docs/S19_STATE.md`, gates table) reads "F0 and MCP digest identical". Read
literally, it fails at the first W5 byte change to any file of R. Restated:

- **E1** At the merged tip, `corpus_identity.py --check` prints `F0 PASS` on all nine measures.
- **E2** Every commit that changes `benchmarks/f0/`, `tests/fixtures/registry/` or
  `src/openflowsheet/registry/builtin/`, and is reachable from the tip but not from d90b498f, is one of two kinds:
  a W5 re-registration commit with a passing W5-K2; or a commit that arrived through a merge of `main`, judged in
  its own package. At 8d31b89e no commit in `d90b498f..8d31b89e` touches those paths (measured). The registry's
  nine measures and `archived_outputs`, the registry fixture, the tables and the two digest test files are
  byte-identical to d90b498f's.
- **E3** Every W5 batch passed W5-S3 at each step and W5-K2 at its close. A batch P also passed W5-K5.
- **E4** M7's 52 registered values (`MATCH`, `exact_replay`, integrity true) are byte-identical to d90b498f's.
- **E5** The `mcp_digest` tier passes, and both of its files are byte-identical to d90b498f, unless changed by a
  merge of `main`.

**Does this change a registered criterion? Yes.** For M9 and the registry, the restatement only writes out what
FQ-A (Frank, 2026-11-14) and ADR 0076 (accepted) already allow, with one difference: the number of changes (FR-2).
For M2, M3 and M6 (tier 3) it is a permission Frank has not given (FR-1). The orchestrator takes both to Frank.
Until he answers, G-END is judged on the literal text for every change outside W5, and on E1 to E5 for W5 batch N
under the FR-2 default.

If FR-1 is declined, tier 3 stays unedited. Then G-END's "no file below health 7.0" fails on `thermo/pr_c1.py`
(4.6), `iapws95.py` (6.2), `coolprop_heos.py` (6.4) and `wilson_ig.py` (6.9). Its "no `huge_file`" fails on
`_coolprop_heos_fluids.py`. Those failures are reported as misses for those named files, not relaxed (CLAUDE.md,
scientific conduct).

---

## 8. B7's route

**Facts at 8d31b89e.**
- `thermo/_coolprop_heos_fluids.py` has 4919 lines: 123 fluid entries of 35 to 41 lines each, in spec §16.3 order,
  the 9 tier A fluids first and then the 114 tier B fluids.
- It is written by `docs/derivations/scripts/s07_reference.py --emit-fluid-table PATH` (`fluid_table(doc)`,
  `s07_reference.py:2009`). `--check` byte-compares it with the committed file (claim C19, `:341`).
- `coolprop_heos.py`'s `_implementation_sha256` (`:241-255`) hashes its own bytes and the table's bytes, the table
  by the literal file name.
- `FLUIDS` is imported by `coolprop_heos.py:73`, `verify/forms.py:117`, `models/revision_flowsheet.py:189` and
  `:236`, `models/thermal/kernel.py:137`, and `tests/test_s07_near_critical.py:30`.
- `tests/test_s07_registration.py:143` asserts that the wheel holds the file.
- Measured reach (x8, x12): M9, the registry, and M6's two coolprop sample keys. No F0 run uses CoolProp (TH-C2 is
  not run on the reference platform, F0 D20), and no committed file outside `src/` and `docs/` carries its
  `[:12]`.
- B7 is tier 3, so it waits for FR-1.

**Route.** Only the generator is edited, never the generated file.

1. `fluid_table(doc) -> bytes` becomes `fluid_tables(doc) -> dict[str, bytes]`, which emits eight modules in
   `src/openflowsheet/thermo/`:
   - `_coolprop_heos_fluids_a.py`, holding the 9 tier A entries;
   - `_coolprop_heos_fluids_b1.py` to `_b6.py`, holding the tier B entries in consecutive chunks of at most 20, in
     §16.3 order (20, 20, 20, 20, 20, 14);
   - the index `_coolprop_heos_fluids.py`: the generated-file docstring, the imports of the seven group modules,
     and `FLUIDS: Final[tuple[dict[str, Any], ...]] = (*_a.FLUIDS, *_b1.FLUIDS, ..., *_b6.FLUIDS)`.

   Each entry's text is the text the generator writes today. Every module stays under 1000 NLOC: 20 × 41 lines plus
   the header is under 900. `FLUIDS` keeps its one home, the index, so no importer changes and no re-export is
   added.
2. `--emit-fluid-table DIR` writes all eight. `--check` (C19) byte-compares all eight, and fails on any other
   `_coolprop_heos_fluids*.py` in that directory.
3. The CoolProp provider's hash scope: `_implementation_sha256` replaces the single read with
   `"fluid_table_sha256": sha256(canonical_json([[name, sha256(bytes of name)] for name in <the eight names as
   string literals, sorted by UTF-8 bytes>]))`. This is ADR 0060 D3's self-hash form; it is free of prefix
   ambiguity, so moving a line between modules changes the value. The M9 scan resolves the eight sibling literals,
   so M9 has 42 keys at head (35 + 7). The registry generator attributes them to `coolprop-heos-v1`.

**Checks for the B7 step.** These are its behaviour evidence. W5-S2 still runs, with the CoolProp files unpinned:
the pin serves base bytes, a new hash scope has no base form, and F0 exercises no CoolProp behaviour.

- **B7-C1** `FLUIDS` at head equals `FLUIDS` at B: 123 entries, the same `id` order, and every entry equal, with
  floats compared by `float.hex` and the B table imported from `git show B:<path>` in a temporary directory.
- **B7-C2** `python docs/derivations/scripts/s07_reference.py --check` exits 0 at the step head, in the
  `requirements.lock` plus `requirements-coolprop.lock` environment. Its runtime is NF-1.
- **B7-C3** The unpinned F0 moves exactly these keys:
  - M9 `coolprop_heos.py` and `_coolprop_heos_fluids.py`, both changed;
  - the 7 group modules, reported "measured, not registered";
  - M6 `sample/provider/coolprop-heos-v1/{evaluate_phase,flash}`.

  `registry_builtin.py --check` differs on `builtin-sha256.txt` and on coolprop-heos-v1's implementation `modules`
  only.
- **B7-C4** The `tests/test_s07_*` suite passes, with the CoolProp extra installed (as CI's CoolProp job runs it).
  `test_s07_registration.py:143`'s wheel assertion is extended to the seven new modules, in a retarget commit
  placed before the step (S19 rules, "Retarget before the plan").

The B7 step comes after the provider steps whose runs F0 exercises (`pr_c1`, `iapws95`, `wilson_ig`). Until B7,
W5-S2's expected result is plain `F0 PASS`. B7 has the smallest reach of tier 3: no registered run and no committed
fixture.

---

## 9. W5 work orders, in order

| # | work order | lane, agent | depends on | acceptance |
| --- | --- | --- | --- | --- |
| WO-0 | `scripts/w5_identity.py` with `sets`, `predict`, `judge`, `coverage` (for N and L), plus `pin` (for P, may follow later); its tests as their own commit outside the gate | build, `opus-engineer` | this ruling | W5-T1, W5-T2, W5-T6, W5-T7; for P also W5-T3 to W5-T5 |
| WO-1 | W5 base B_N: `i19_scan.py` (must find the 36 bindings and no other); `sets --check`; health scan of R; L_N measured by the 3.1 method with every batch N file comment-edited and the edits committed on a scratch branch (so that G5 does not appear); the gate lane's frozen-rule exemption for batch N's admitted set, and a W5 gate mode that applies W5-S2 to W5-S4 and W5-S6 in place of the plain `f0`, registry and tests verdicts (orchestrator, config and queue) | orchestrator | WO-0 | L_N and admitted set recorded in the batch brief; W5-T1 at B_N |
| WO-1b | Ruling R7 (finding F-2): S10 A26's oracle becomes F0's registered M9 value of each `UNTOUCHED` provider, and the skip without a `main` ref goes. One test commit outside the gate; the register records it as an amendment of S10 A26 | build (`sonnet-implementer`), `reviewer` read | WO-1 | at B_N, A26 passes; with a scratch comment edit of `thermo/pr_lib.py` it fails, naming `pr_lib.py`; after a W5-K2-judged K it passes again |
| WO-N1 | `assessment/cost/contributor.py` (2.8), then `sets.py` (4.7), to health at least 7.0 (target 9.0); retarget `Refusal` in `cost/{contributor,derived,index,operating}.py` to `assessment.linearization` | build | WO-1 | W5-S1, S3 (`F0 PASS` 9/9), S4 to S8 per step |
| WO-N2 | `assessment/lca/`: retarget `Refusal` in `lca/{brightway,impact,inventory,tables}.py`; health steps on any lca file below target; then remove the `Refusal` re-export from `assessment/program.py` (not hashed), its eight importers being retargeted | build | WO-N1 | as WO-N1 |
| WO-N3 | `thermo/pr_lib.py` (6.9): edits inside the file only (R4) | build, S1 tier | WO-N2, WO-1b | W5-S3 (`M9 FAIL 1/35` on pr_lib only), S1, S4 to S8; reviewer cadence S1 |
| WO-N4 | registry factory switch, part 1 (ADR 0076 I-19): only the units' factory constant in `scripts/registry_builtin.py` changes, to `openflowsheet.application.model_builders` (`BINDER` serves the units at `:413` and the methods at `:144`; only the units move). `revision_binding.MODEL_BUILDERS` stays until after K: the registry resolves a factory lazily by `getattr` (`registry/__init__.py:640-647`), so the committed table must point at the new home before the old name goes. The factory reference `tests/test_f1_legacy_builtins.py:373` is an expected value of the registry change: it goes into L_N and changes at K | build | WO-N3 | W5-S4 with exactly the units' factory `module` pointers predicted; S3 unchanged from WO-N3 |
| WO-N5 | close N: R5's re-record, W5-K1 to K4, K6, K7 (the eight `Refusal` rows); merge per FR-2 | orchestrator, `reviewer` | WO-N4 | predicted K diff: M9 `thermo/pr_lib.py` only; `builtin-sha256.txt`; legacy.json's units' factory pointers and `tables.sha256`; core.json only if a tier 1 split added a module; nothing in M1 to M8 |
| WO-N6 | registry factory switch, part 2, after K: a retarget commit for the live patch `tests/test_t07_w5a_inspection.py:130`, then remove `revision_binding.MODEL_BUILDERS` (`revision_binding.py:40`). An ordinary S19 interface step: `revision_binding.py` is not hashed | build | WO-N5 merged | F0 `PASS` 9/9 and `registry_builtin.py --check` clean against the re-registered K (no identity moves); `i19_scan` shows no `MODEL_BUILDERS` row; patch_noop 0 |
| WO-P0 | (after FR-1) WO-0's `pin` with W5-T3 to T5; B_P; L_P by the 3.1 method | build, orchestrator | FR-1, WO-N5 | W5-T3 to W5-T5; L_P recorded |
| WO-P1 | `thermo/pr_c1.py` (4.6), inside the file | build, S1 tier | WO-P0 | W5-S1 to S8, S2 `F0 PASS`; S3 predicted: M2/M3 `m02/C1-FLASH-F1-M02-v1`, M6 pr-c1 sample pair, M9 |
| WO-P2 | `thermo/iapws95.py` (6.2), inside the file | build, S1 tier | WO-P1 | as WO-P1; S3 adds: M2/M3 `s11-th/TH-C1`, `TH-R1`, `TH-V1`, M6 iapws95 pair, M9 |
| WO-P3 | `thermo/wilson_ig.py` (6.9), inside the file; S11 A75 amended to "v1 is not edited since K of batch P" (F-3) | build, S1 tier | WO-P2 | as WO-P1; S3 adds: M2/M3 the five `s11-gp` runs, M6 wilson-ig-v2 pair, M9 |
| WO-P4 | B7 by its generator (section 8) | build | WO-P3 | B7-C1 to B7-C4; W5-S1, S2 (CoolProp keys only), S3, S4, S7 (M9 +7 keys) |
| WO-P5 | `thermo/coolprop_heos.py` (6.4), inside the file (its hash scope as WO-P4 left it) | build, S1 tier | WO-P4 | B7-C4, W5-S1 to S8; S3 adds: M6 coolprop pair, M9 |
| WO-P6 | close P: R5, W5-K1 to K6; the L01 register ruling with the moved SHA-256 of `pr_c1.py` (F-4); `WILSON_V1_SHA256` re-based (F-3); release-note line naming the providers whose `model_version` moved | orchestrator, `reviewer` | WO-P5 | predicted K diff: the union of WO-P1 to P5's keys |
| WO-L0 | (after the legacy ruling) B_L; L_L; `i19_scan` rows for `column_unit.py` | orchestrator | Frank's legacy ruling | L_L recorded |
| WO-L1 | `models/syn001/column_unit.py` (4.9): retarget its 34 bindings to their homes (I-19 inventory; each passes R4's object-identity test); remove the 34 re-exports from `models.syn001.cascade`, `.column`, `.column_solve` and `orchestrator.region` (none of them hashed); then health edits inside the file | build, S1 or S2 per design note | WO-L0 | W5-S1, S3 (`M9 FAIL 1/35`), S4 to S8 |
| WO-L2 | `conversion_reactor.py` (6.6), `kinetic_cstr.py` (6.8), `mixer.py` (6.9), then other unit modules below target | build | WO-L1 | as WO-L1 |
| WO-L3 | close L: R5, W5-K1 to K4, K6, K7 (the 34 bindings); the L01 register ruling with the moved SHA-256 of every edited `models/c1/` file (F-4) | orchestrator, `reviewer` | WO-L2 | predicted K diff: M9 of the edited units; registry; nothing in M1 to M8 |

Within N the order is the worst health first. In P, the providers whose runs F0 exercises come first, worst health
first, so that the pin stays a plain `F0 PASS` until B7 changes the CoolProp hash scope. ADR
0076's "End of W5" (the I-19 exceptions gone, F0 re-registered, `--write` committed) is met only after WO-L3,
because the 34 `column_unit` bindings are in batch L. If the legacy ruling takes `models/` out of S19, that
acceptance item goes back to Frank with the ruling.

---

## 10. Questions for Frank, and facts still to measure

**FR-1 (needs Frank's preference). May W5 edit tier 3?**
- What it costs: new `model_version` strings for every run on `pr-c1-v1`, `iapws95-v1`, `wilson-ig-v1`/`-v2` and
  `coolprop-heos-v1`. In F0 that is M2 and M3 of 9 runs and 8 M6 sample keys. Every bundle written before the
  change on those providers, released 0.4.x bundles included, then replays `MISMATCH` on `model_version`. Two
  other packages' assertions are amended: S11 A75 "v1 is not edited" (F-3), and L01 A22's pin of `pr_c1.py`, by
  L01's registered-move route (F-4).
- What it buys: pr_c1 4.6, iapws95 6.2, coolprop_heos 6.4, wilson_ig 6.9, and B7's `huge_file`.
- The options:
  - (A) Admit all of tier 3, with the pin, closing before the 0.5.0 release-candidate cut, and with a release note
    listing the moved provider fragments.
  - (B) Admit only B7 and `coolprop_heos.py`: no registered run and no committed fixture is affected.
  - (C) Admit none, and record the five G-END misses.
- Recommended: (A). The pin proves that the change is identity only. Leaving four providers below 7.0 contradicts
  the campaign's goal. Closing before 0.5.0 keeps the change between two releases.
- **Default until answered: (C) in effect.** Batch P is not started; batches N and L are unaffected.

**FR-2 (needs Frank's preference). Once, or once per batch?** ADR 0076 (accepted) says "changes once, in W5" for
both identities.
- (a) Literally once: every batch's steps stay on `wp/S19-w5` and one K closes them all. Batch N then waits unmerged
  for FR-1 and for the legacy ruling, and the branch lives long beside 0.5 development.
- (b) Once per batch: at most three identity changes (N, P, L), each one reviewable commit with a judged diff.
- Recommended: (b). The reason for "once" was reviewability (Q1: "one identity change per batch is reviewable, one
  per step is not"), and (b) keeps that per batch.
- **Default until answered:** batch N runs to its K on `wp/S19-w5`, and its merge into `wp/S19` waits for the
  answer. This is (a) until Frank says (b).

**FR-3 (same card).** Approve section 7's restatement of G-END's F0 clause.

**NF-1 (needs a fact).** The runtime of `s07_reference.py --check` on the workstation. Measure it once at B_P, at
the base, before the B7 step. Default: run it once per B7 step, as B7-C2, not in every gate.

**NF-2 (needs a fact).** Whether F8 (ADR 0067 v2 bundles) lands before a batch closes. If it does, committed v2
fixtures enter L, and v2 bundles written in between replay `compatible_reproduction`/`extension_changed`. Measure
it at each batch base with `grep -rl openflowsheet-bundle-v2 tests/fixtures`. Default: they go into L_B, and are
re-recorded by F8's own re-record tool (F8-WO3).

**NF-3 (needs a fact).** Whether `--record` reproduces M1, M4, M5, M7 and M8 byte for byte. W5-K2 measures it at
each K. Default: expected yes. F0 reproduced M1, M4, M5 and M8 in 13 of 13 probe trees, and M7 in the 12 that did
not edit `thermo/syn001.py`. If not, the batch stops and the design lane reads the diff.

---

## 11. ADR draft (status: proposed)

> **ADR 0077 (proposed, number assigned on filing): S19 W5, identity re-registration by batch, with the identity
> pin**
>
> **Status:** Proposed, 2026-11-18, design lane (`specifier`), from `docs/briefs/S19-W5-ruling.md`. Takes effect if
> Frank accepts FR-1 and FR-2. **Amends:** ADR 0076, Affected requirements (F0 M9 and the built-in registry
> identity "change once, in W5"; "Replay identity: unchanged"), Consequences, and Acceptance "End of W5"; S19
> decision Q1 ("M1 to M8 unchanged"); the S19 end gate G-END ("F0 and MCP digest identical").
>
> **Decision.**
> - D1: the files of R are classified into the four tiers of the ruling's section 4, computed by
>   `scripts/w5_identity.py sets`.
> - D2: `thermo/syn001.py` is not edited in S19.
> - D3: W5 re-registers, per batch and in one commit, exactly the values that are functions of the edited files'
>   bytes (R1). The batches are N, P and L.
> - D4: evidence is the exact moved-key check per step and the judged diff per batch; for tier 3 also the identity
>   pin (R2).
> - D5: no identity hole (R4). No provider or unit module is split in W5, except B7's data table through its
>   generator.
> - D6: B7 as in the ruling's section 8.
> - D7: G-END's F0 clause as E1 to E5.
> - D8: S10 A26's oracle is F0's registered M9 value instead of `main` (ruling R7, finding F-2).
>
> **Alternatives rejected.**
> - Re-registration per step: one identity change per step is not reviewable (Q1).
> - Declared implementation versions instead of byte hashes: ADR 0060 D3 has the registry compute identities and
>   never take them from an author; a declared version would let behaviour change unseen.
> - Hashing a normalised AST or stripped source, so that comment edits do not move identities: refactoring changes
>   the AST anyway, and it would change the identity formula of every provider for no gain in W5.
> - Comparing artifacts after textual substitution of old by new identity strings: hashes computed over documents
>   that contain identities (M3, M6, the bundle index) cannot be substituted. The pin moves the substitution to
>   the source.
> - Re-registering M7 as `MISMATCH`, or rewriting the v0.3.0 bundles: either would register a regression as
>   expected, or end the 0.3.0 reproduction check.
> - A production switch that overrides `implementation_sha256`: identity must not be overridable outside a test
>   harness.
>
> **Affected requirements.**
> - F0 registry `benchmarks/f0/corpus.json`: M9 per batch; M2, M3 and M6 in batch P.
> - E-F1-5's constant `tests/fixtures/registry/builtin-sha256.txt` and the built-in tables.
> - The served `registry_sha256`.
> - `model_version` of runs on four providers (batch P).
> - Replay of earlier bundles on those providers, which becomes `MISMATCH` on `model_version`.
> - G-END's F0 clause.
> - Other packages' immutability assertions: S10 A26 (its oracle, D8); S11 A75 "v1 is not edited" (batch P); L01
>   A22's pins of `pr_c1.py` and `models/c1/`, moved by L01's registered-move route (batches P and L).
>
> **Migration impact.**
> - Batches N and L: no user-visible change except `registry_sha256` in `list_capabilities` and in inspection
>   responses.
> - Batch P: 0.5.0 release notes list the moved provider fragments (old and new `[:12]`). v1 bundles from 0.4.x on
>   those providers replay `MISMATCH` with the `model_version` difference listed. Nothing else in their reports
>   changes.
>
> **Acceptance evidence.**
> - W5-T1 to W5-T7.
> - W5-S1 to W5-S8 per step, and W5-K1 to W5-K8 per batch.
> - B7-C1 to B7-C4.
> - E1 to E5 at G-END.

---

## 12. What this ruling does not establish

- **It does not show that any W5 edit is behaviour-identical.** The per-step and per-batch checks do that, step by
  step. The experiment used comment-only appended lines, so it measures **reach**, not refactoring safety.
- **F0 covers only its corpus:** 61 runs, 52 bundles and the M6 sample. It covers no behaviour of
  `thermo/pr_lib.py` (no basis selects `pr-lib-v1`), of `coolprop-heos-v1` (TH-C2 is not run on the reference
  platform), or of `assessment/cost` and `assessment/lca`. For those files, behaviour identity rests on the full
  suite (with the CoolProp extra, for B7) and on the reviewer. A passing F0 is no evidence about them.
- **The pin proves identity over the F0 corpus only,** and only on `ref-x86-64`.
- **It does not decide FR-1, FR-2 or the legacy `models/` question,** and it does not amend ADR 0076, 0060 or 0067:
  section 11 is a proposal.
- **It does not cover the v2 bundles of ADR 0067,** which are not built. Section 3.4 states their consequence only
  as ADR 0067's text implies it.
- **The tier assignment and every count are for 8d31b89e.** Each batch base recomputes them with WO-0's `sets` and
  `predict`. A count in this document that disagrees with the tool at a later base is superseded by the tool, and
  the difference is recorded.
- **The suite lists of 3.3 were measured on uncommitted edits.** G5 is one artifact of that. WO-1 re-measures each L_B
  with the edits committed on a scratch branch.
- **Persisted module paths (design note Q2), such as `__module__` in pickles, are not tested here.** B7 adds
  modules but moves no class or function between modules; the I-19 retargets change import paths only.

---

## Appendix A: the probe script

```bash
#!/bin/bash
# probe.sh <tree> <tag>: F0 check, registry generator check, MCP digest, F1 identity tests.
T=$1; X=$2; L=$(dirname "$0")/logs; V=<main checkout>/.venv/bin
cd "$T" || exit 2
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PYTHONPATH=src $V/python scripts/corpus_identity.py --check --log $L/$X.f0.log
PYTHONPATH=src $V/python scripts/registry_builtin.py --check
PYTHONPATH=src $V/python -m pytest -q -p no:cacheprovider \
    tests/test_t08_w2_surface_digest.py tests/test_m07a_surface_chain.py
PYTHONPATH=src $V/python -m pytest -q -p no:cacheprovider \
    tests/test_f1_registry_core.py tests/test_f1_discovery.py tests/test_f1_builtin_identity.py
```

Trees: `git worktree add --detach <scratch>/xN 8d31b89e`, then
`echo '# W5 identity experiment: a comment-only edit (never committed).' >> <scratch>/xN/src/openflowsheet/<file>`.
They were removed with `git worktree remove --force` and `git worktree prune`. F0 took 43 to 155 s per tree, and up
to 155 s under the load of a parallel full suite.
