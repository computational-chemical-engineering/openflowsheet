# F8 build decisions (append-only)

Build-lane choices for package F8 (identity, replay and evidence v2) that ADR 0067 leaves open. ADR 0067 is Proposed;
the build follows its text as it stands (D1 to D12, the W1 P3 review edits applied). Where it is silent or ambiguous,
the reading taken is the one that changes no existing byte. Each line: `DECISION`, the choice, the alternative, and
where it lives. Each is revertible on its own. Batched for the package's one design-lane ruling round (CLAUDE.md,
agent budget).

## F8-WO1 (manifest v2 and schemas), 2026-11-27

Brief `docs/briefs/LINE06-F8-WO1.md`. Files: `src/openflowsheet/run/{manifest,manifest_v2}.py`,
`schemas/{run-manifest,bundle-v2,records-index,run-evidence}.schema.json`, `schemas/registry.json`,
`benchmarks/f8/numerical_policy_external.yaml`, `scripts/t08_numerical_policy.py` (`ADDENDA`),
`tests/test_f8_manifest_v2.py`, `tests/test_k05_replay.py`.

- **DECISION F8-WO1-1. D2's and D5's member shapes live in a new F8 schema, `schemas/bundle-v2.schema.json`, and
  `run-manifest.schema.json` reaches them by `$ref` (R-1032's structure); its top level is closed by
  `unevaluatedProperties: false` instead of `additionalProperties: false`.** D2 puts `data_lock_sha256` at the
  manifest's top level, and `run-manifest` is in `T08-numerical-policy-v2`'s domain: declared there, the name is an
  unclassified `sha256` name and ADR 0025 A1(d) fails (`t08_numerical_policy.py --check`). A bare `$ref` cannot help
  for a top-level key, so the key is declared in the `$def` `data_lock` of `bundle-v2` and joined by `allOf`;
  `additionalProperties` would then refuse it, `unevaluatedProperties` (draft 2020-12) keeps the object closed to
  every other key. `environment` keeps `additionalProperties: false` (its new key `registry` carries no `sha256`).
  Every v1 manifest validates as before (52 committed 0.3.0 manifests and the K05 fixture, in
  `tests/test_f8_manifest_v2.py`); an unknown key at the top level or in `environment` is still refused (tested).
  Measured: `--check` passes with v2's bytes `6b449911…` unchanged; deleting `data_lock_sha256` from F8's addendum
  makes it fail with "(f8) unclassified sha256 names: ['data_lock_sha256']". Alternatives: add the names to v2's
  `exact_sha256` (changes a registered policy's content; R-1032 rejected (a) and (c) for the same case); a separate
  `run-manifest-v2.schema.json` (departs from D2's "`run-manifest.schema.json`, optional members").
  **Design-lane question** (schema structure under ADR 0025 D2.3).
- **DECISION F8-WO1-2. F8's numerical-policy addendum `F8-numerical-policy-external-v1`**
  (`benchmarks/f8/numerical_policy_external.yaml`, appended to `ADDENDA`): schemas `bundle-v2`, `records-index`,
  `run-evidence`; new exact names `data_lock_sha256`, `snapshot_sha256`, `recorded_registry_sha256`,
  `current_registry_sha256`. `registry_sha256` (F1), `sha256` (v2) and `source_sha256` (F3) keep their classes.
  `run-evidence` holds no `sha256` name yet; it is listed so that WO4's `record_sha256` lands in F8's table.
- **DECISION F8-WO1-3. `RunManifestV2` requires `data_lock_sha256`, `extensions_used` and `environment.registry`;
  `run_kind` and `documents` are optional (absent when `None`).** D2 makes every member optional in the schema,
  which stays so (no conditional `if bundle_format then …`): a v2-compiled run always has a lock, a registry and a
  used set (D3's layout carries `data-lock.json` and `registry-snapshot.json`), while `run_kind`/`documents` are
  ADR 0066's (0.8). `extensions_used` must arrive sorted by (kind, id, version key) with each (kind, id, version)
  once, or the constructor refuses it (`extensions_used_rows` builds it so from `Registered` descriptors).
  Alternative: all members optional in Python too, or a `dependentRequired` in the schema.
- **DECISION F8-WO1-4. `run-evidence.schema.json` is the envelope (brief): the top level, `verification`,
  `validation` and `optimality` are closed and typed from D6; a validation entry and an extension row are open
  objects, their members F8-WO4's (with F4-WO4, after 0.6).** Notices are `{code, params}` as `Coded.as_document`
  writes them. Alternative: type the entries from D6's prose now (types such as `uncertainty` and `origin` are not
  fixed by D6, and a closed shape would bind WO4).
- **DECISION F8-WO1-5. `records-index.schema.json` has exactly D3's members (no format id); `assessment` is ADR 0061
  D11's enum by `$ref` to `record-results.schema.json#/$defs/effective_rights`; `conditions` is string or null.**
  Alternative: a `records_index_format` const as the other v2 documents carry (D3 shows none).
- **DECISION F8-WO1-6. The `forced_replay` refusal is `run.manifest_v2.refuse_reserved_mode(report)`**, which raises
  `ReplayModeRefusedError` carrying `construct_unavailable(forced_replay, TX)` (`RESERVED_REPLAY_MODES`). It is a
  reader-side check before schema validation; `run/replay.py` and `ReplayReport` are untouched (WO3 dispatches). No
  catalogue code is added: `construct_unavailable` exists (ADR 0058 C3: WO1 raises no new code).
- **Note F8-WO1-7.** `tests/test_k05_replay.py`'s exclusion walk asserted `set(full) - set(structural) ==
  NON_STRUCTURAL`; with `bundle_format` listed it now asserts that a v1 manifest has no `bundle_format` and that the
  excluded keys present are `NON_STRUCTURAL - {"bundle_format"}`. `scripts/k05_evidence_manifest.py` lists
  `sorted(NON_STRUCTURAL)` in a K05 evidence manifest when rerun; committed evidence is untouched.
- **STOP F8-WO1-8. `replay-report.schema.json` (Amendment 12: `forced_replay` in `mode`, `registry_comparison`,
  `data_availability`) is not changed: it moves served digests.** Probe at `6209110b` (not committed): adding only
  the enum value `forced_replay` fails 39 of the 85 surface tests (`test_t07_w5e_application_results.py`,
  `test_t08_w2_surface_digest.py`, `test_m07a_surface_chain.py`): R4-G3 (`reproduce` `8e62572a…` -> `f65aba0a…`, and
  `get_job`, `cancel_job`, `get_job_result`, which embed the report) and the MCP served digest (F2's `9a4b4eb3…`), so every chain link fails. The
  member shapes are ready in `bundle-v2.schema.json#/$defs/{registry_comparison,data_availability}` (tested);
  wiring them is two `$ref`s and the enum value, plus the registration of the move (a `without_f8` strip, new
  snapshot constants and a chain link). The link number is the orchestrator's (X06 holds `c_12`, R-1073).
- **STOP F8-WO1-9. `job.schema.json`'s artifact kinds (D3) are not added: they move the R4-G3 snapshots.** Probe at
  `6209110b` (not committed): appending one kind (`data_lock`) to `artifact_ref.kind` fails 7 of the 85 surface
  tests, all in `test_t07_w5e_application_results.py` (R4-G3 `solve`, `submit_job`, `get_job`, `list_jobs`,
  `list_job_events`, `wait_job`, `cancel_job`, `get_job_result` and the `without_<pkg>` decompositions); the MCP
  served digest does not move (MCP serves J5's consumer reading, the enum opened). Adding the kinds also needs
  `jobs/model.py`'s `ArtifactKind` and `ARTIFACT_FILE_NAMES` (D3 names `data-lock.json`, `registry-snapshot.json`,
  `records-index.json`, `run-evidence.json`; `record` and `decision_record` are per instance, `None`;
  `exchange_record`'s name is not given by D10).
- **Note F8-WO1-10. Pre-existing reds, not F8's.** `tests/test_v03_semantic_roles.py` `test_a29`, `test_a31_a`,
  `test_a31_b` fail at the branch point `df796cc2` as at the WO1 head (`crystallizer.yaml` refused
  `capability_unknown(probe.*)`, `revision_v2/lower.py` names the role): wp/F2's, F2-WO6c's territory.

### F8-WO1 gate numbers (SMM-TR09, 2026-11-27)

Commits `6209110b` (NON_STRUCTURAL), `a236a064` (schemas, addendum; WO1-1, WO1-2), `ea6503eb` (`manifest_v2.py`, tests).
- F0 (`scripts/corpus_identity.py --check`, own detached worktree): PASS at `6209110b` and at `ea6503eb`, both
  M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42.
- `t08_numerical_policy.py --check`: PASS, v2 bytes `6b449911…` unchanged.
- Battery 1 (144 files that touch `schemas/` or `run/`, before the pin fixes): 5945 passed, 56 skipped, 6 failed: the
  three v03 reds (WO1-10), `test_x05_lock::test_a12` and `test_m05_study_record::test_the_m05_addendum…` (pins, fixed in
  `a236a064`), `test_m07_journey::test_a21` (the tree was dirty during the run; green on the committed tree).
- Battery 2 at `ea6503eb` (the surface suites `test_t07_*`, `test_t08_w2_*`, `test_m07a_surface_chain` 34, and
  `test_f8_manifest_v2` 34, `test_k05_replay` 30, `test_k05_schemas` 14, `test_f2_amendment9` 124, `test_x05_lock` 50,
  `test_m05_study_record` 211, `test_m07_journey` 111, `test_package_imports` 24, `test_v03_semantic_roles` 20):
  2936 passed, 28 skipped, 3 failed (the v03 reds only). No served digest moved.
- ruff check, ruff format --check (1347 files), mypy `src` (368 files): clean.

## F8-WO1b (STOPs F8-WO1-8 and F8-WO1-9 built as surface link c_13, R-1076), 2026-11-27

Brief `docs/briefs/LINE06-F8-WO1b.md`. Files: `schemas/{replay-report,job}.schema.json`,
`src/openflowsheet/application/jobs/model.py`, `tests/f8_schema_support.py` (new), `scripts/m07a_rc.py`,
`tests/test_{m07a_surface_chain,t07_w5e_application_results,t08_w2_surface_digest}.py`, `docs/decision-register.md`
(R-1076 only).

- **DECISION F8-WO1b-1. `exchange_record`'s file name is `None` (named per instance), as `record` and
  `decision_record`.** ADR 0067 D10 names no file. Alternative: `exchange-record.json`. Revertible by one line in
  `ARTIFACT_FILE_NAMES`; file names enter no schema and no digest.
- **DECISION F8-WO1b-2. D3's seven kinds are appended at the end of `artifact_ref.kind` and `ArtifactKind`, in D3's
  order (`data_lock`, `registry_snapshot`, `records_index`, `record`, `run_evidence`, `decision_record`,
  `exchange_record`); `forced_replay` is appended at the end of `mode`'s enum.** The additive F2 pattern
  (`without_f2` cuts an enum's tail). The enum's and the report's descriptions are unchanged. Alternative: sorted
  insertion (would break the tail-cut decomposition).
- **DECISION F8-WO1b-3. `registry_comparison` and `data_availability` are bare `$ref`s by absolute URI,
  `https://github.com/frankp/process-runtime/schemas/bundle-v2.schema.json#/$defs/<name>`.** `replay-report`'s `$id`
  has the other base (`raw.githubusercontent.com/.../clearsheet/main/schemas/`), so the relative
  `bundle-v2.schema.json#/$defs/...` the brief names would resolve to an id no schema has. Neither is in `required`
  (D5: absent for v1 bundles). D5's `decision_comparison` (TX) is not added. Python `ReplayReport` and
  `ReplayMode` are untouched (WO1-6; WO3 dispatches). Alternative: a relative `$ref` after moving one `$id` (moves
  every digest that resolves either schema).
- **DECISION F8-WO1b-4. R-1076's entry is not on wp/F8 (branched before it landed on `main`): main's text is copied
  after R-1072 with only its Evidence cell filled**, so `test_f8_link_c_13_is_f8s_strip_and_digest` reads it as the
  c_11 test reads R-1072. At the merge into `main`, keep main's entry in place with this Evidence cell (the register
  will conflict on its tail). Alternative: no register check in the c_13 test.
- **Note F8-WO1b-5.** `without_f8` recognises a replay report by its member `verdict_changed_near_threshold` (no
  other schema has it) and drops the two members; it cuts `forced_replay` only from the exact four-value mode enum
  and the seven kinds only from an enum that ends in them. On the served list only `get_job_result`'s
  `replay_report` moves; the job kinds reach R4-G3 alone (MCP serves the kind enum opened, J5).
- **Note F8-WO1b-6.** `jobs/runner.py`'s `KIND_OF_FILE` now also maps `data-lock.json`, `registry-snapshot.json`,
  `records-index.json` and `run-evidence.json`; no v1 bundle or job directory holds these names, so no v1 import or
  producer path changes. WO2's writer relies on it.
- **Note F8-WO1b-7.** `tests/test_m07a_surface_chain.py`'s positional controls count one more passing row before
  each inner link (c_13 is now the first item-2 row); the c_11 control carries `L11` so that it fails at c_11's strip,
  not at item 1. F2's decompositions in the three surface tests now strip F8 first (`without_f8`, `strip_f8`).

### F8-WO1b gate numbers (SMM-TR09, 2026-11-27)

Commits `f2ab3db3` (schemas, `ArtifactKind`, `without_f8`, c_13, re-pins, R-1076 entry), `9cefd000` (M02's and M04's
decompositions strip F8 first).
- Served MCP digest: F2's `9a4b4eb3…` -> `F8_SERVED_SHA256` `c11d38778d2f8aba8240a6a2b5ee9d9e1e7b93c5c6fae4cc40ca82177cb50ddd`
  (`D_13`); `without_f8(served)` = `9a4b4eb3bd9f28e6…` exactly; only `get_job_result` moved.
- R4-G3 re-pins (`SNAPSHOT_F8`, old -> new; `without_f8` returns each to its old value exactly):
  `solve` `e7f66229…` -> `c1689978…`; `reproduce` `8e62572a…` (b13d556) -> `2251b1df…`; `submit_job` `9a6b2d26…` ->
  `2821206f…`; `get_job` and `cancel_job` `8d01b63a…` -> `8026df21…`; `list_jobs` `c7bb7114…` -> `44153df8…`;
  `list_job_events` `751ec851…` (OPT) -> `899d4dab…`; `wait_job` `fd16741d…` -> `75137a9d…`; `get_job_result`
  `866c3ca9…` -> `bddb2dd5…`. Old values are X04's unless marked.
- F0 (`scripts/corpus_identity.py --check`, own detached worktree at `f2ab3db3`): PASS, M1 50/50, M2-M5 61/61, M6
  85/85, M7 52/52, M8 105/105, M9 42/42.
- Surface suites (`test_t07_*`, `test_t08_w2_*`, `test_m07a_surface_chain`; 62 files): 2325 passed, 28 skipped, 0
  failed. Per file: `test_m07a_surface_chain` 36, `test_t07_w5e_application_results` 39, `test_t08_w2_surface_digest`
  14, `test_t07_types` 113, `test_t07_w1f_followup` 11.
- `test_f8_manifest_v2` 34, `test_k05_replay` 30, `test_k05_schemas` 14, `test_m02_schemas` 23, `test_m04_study_job`
  10; 26 files touching job or replay schemas: 634 passed, 4 failed before `9cefd000` (the three v03 reds, WO1-10;
  `test_m04_study_job::test_a42`, fixed by `9cefd000`); 8 digest-dependent files (`test_f1_operations`,
  `test_f3_operations`, `test_m02_schemas`, `test_m04_study_job`, `test_m07_v0_2_gate`, `test_m07_rc_records`,
  `test_rel_ci_release_rc`, `test_t08_w4_rc`): 314 passed.
- ruff check, ruff format --check (1348 files), mypy `src` (368 files): clean.
- Left over: ADR 0019's Amendment 12 pointer paragraph (as F2's Amendment 9 one); `ReplayReport`/`ReplayMode` in
  Python and D5's `decision_comparison` (TX) are WO3's and TX's.

## F8-WO2 (bundle writer v2, test-only factory), 2026-11-27

Brief `docs/briefs/LINE06-F8-WO2.md`. Files: `src/openflowsheet/run/bundle_v2.py` (new),
`tests/f8_bundle_v2_support.py` (new, the factory), `tests/test_f8_bundle_v2.py` (new). `run/bundle.py`
is untouched (D3).

- **DECISION F8-WO2-1. The factory derives a v1 revision's lock and `extensions_used` itself (test-only).**
  A v1 run resolves nothing through the registry (`usage()` records an empty set for TH-C1, GP-C1 and
  SYN-001-nominal, measured), and no `src/` function maps a v1 revision to ADR 0060 D8's references or to
  a lock. The factory takes: components = `component_set.components` in revision order, each the record
  of that id in the legacy file `record_source` names (committed legacy index); parameter sets = every
  `parameter_set` record of that file (`build_lock` checks D5's matching); methods = one row, the
  revision's provider (`component_basis(...).provider_id`); references = each instance's `unit_model`,
  that `property_method`, `connection_definition nTP-v1`, `record_type component` (and `parameter_set`
  when the lock holds one), `data_source legacy-yaml`, each at its highest registered version. The real
  derivation belongs to the v2 compile (F6/F8-WO6) and WO3's usage cross-check. Alternative: the
  `usage()` set (empty for v1 runs). Revertible by editing `tests/f8_bundle_v2_support.py` only.
- **DECISION F8-WO2-2. The `methods` row's substream is `mixed`** (the id v2 fixtures give the one mixed
  substream of an `nTP-v1` material). A v1 revision names no substream. Test-only (`SUBSTREAM`).
- **DECISION F8-WO2-3. The writer refuses, never overwrites, a manifest whose `data_lock_sha256` or
  `environment.registry` disagrees with the lock and snapshot it is given (`BundleError`)**, and refuses a
  caller artifact that takes a D3 name. `data_lock_sha256` is R0 and the run's, so a silent fix would
  change identity at write time; the `artifacts` index is still built from the bytes written, as in v1.
  `run-evidence.json` (D6) is not written: F8-WO4's (out of 0.6).
- **DECISION F8-WO2-4. E-F8-3's referenced records come from the test's own project register.** Every
  corpus source is `permitted` in the repository register (the `legacy.s10` seed `unknown` is overridden
  by the later row "NOTICE Wilson block", 2026-10-29), so no corpus case references a record. Before
  GP-C1 is recorded, `RecordStore.append_rights` adds record-scoped project rows (D11's first precedence
  row) to the test's in-memory project store: `refused` for `S10-wilson-ig-real-v1`'s source, `unknown`
  for C2H5OH's. The bundle then embeds CH3OH and H2O and references the set and C2H5OH. The re-assessment
  test flips them (set and C2H5OH `permitted`, H2O `refused`) in a fresh stack and rewrites; a second
  test appends a whole-source `refused` repository row for TH-C1's `legacy.s05`. Alternative: edit the
  package register (shipped data; not the test's to change).
- **Note F8-WO2-5. `verify_bundle` (v2) reuses `run/bundle.py`'s private cross-checks**
  (`_cross_check_solution_state`, `_cross_check_solve_path`) for the v1 artifacts a v2 bundle carries;
  D3 keeps `bundle.py` untouched, so they are imported, not moved. It adds D3's checks: the lock and the
  snapshot hash to the manifest's values, the index names exactly the lock's records, the record files are
  exactly the embedded entries and each hashes to its own SHA (a forger who rebuilds the index and both
  self-hashes is still caught; tested).
- **Note F8-WO2-6. For WO3.** The v1 `read_manifest` fails on a v2 manifest with `TypeError` at
  `Environment(registry=...)`, before its unknown-member `BundleError`; D5's dispatch must test
  `bundle_format` before calling it (pinned by `test_the_v1_reader_does_not_read_a_v2_bundle`).

### F8-WO2 gate numbers (SMM-TR09, 2026-11-27)

Commits `da02b48a` (`run/bundle_v2.py`), `5e11abb9` (factory and tests).
- F0 (`scripts/corpus_identity.py --check`, own detached worktree at `5e11abb9`): PASS, M1 50/50, M2-M5 61/61,
  M6 85/85, M7 52/52, M8 105/105, M9 42/42.
- `tests/test_f8_bundle_v2.py` 21 passed (E-F8-2: 9 incl. the two-case parametrisation; E-F8-3: 7; writer 2;
  E-F8-10 2; D4 no-network 1). Mutation controls (not committed): embedding forced `True` fails 3 E-F8-3
  tests; dropping the record-name hash check fails the forged-index test; dropping `_cross_check_v2` fails 3
  E-F8-2 tests.
- Battery (`test_f8_bundle_v2` 21, `test_f8_manifest_v2` 34, `test_k05_replay` 30, the 62 surface files,
  `test_v03_semantic_roles` 20, `test_f3_lock_rights` 16, `test_package_imports` 24): 2467 passed, 28 skipped,
  3 failed (the three v03 reds, WO1-10). No served digest moved (surface suites green, no re-pin).
- ruff check, ruff format --check (1351 files), mypy `src` (369 files): clean.
- Left over: `run-evidence.json` (D6, WO4); replay of a v2 bundle and the dispatch (WO3).

## F8-WO3 (replay of a v2 bundle), 2026-11-27

Brief `docs/briefs/LINE06-F8-WO3.md`. Files: `src/openflowsheet/run/{replay,replay_v2,bundle_v2}.py`,
`src/openflowsheet/messages/catalogue/replay.yaml` (new), `docs-site/messages/refusals.md`, the two `message_entry`
fixtures, `tests/f8_bundle_v2_support.py`, `tests/test_f8_replay_v2.py` (new), `scripts/f8_v1_replay_reports.py` (new),
`tests/fixtures/f8/v1-replay-reports.json` (new).

- **DECISION F8-WO3-1 (the step-7 premise). D5 is met as written for the factory's bundles; the rerun provably does
  not need the embedded records.** Measured: the recorded revision (GP-C1, TH-C1) is a v1 document; its binder reads
  the packaged legacy YAML its `component_set.record_source` names and consults no record store, and `usage()` records
  nothing during the rerun (empty set, both cases). Step 7's order is built (`replay_v2.served_stack`: the embedded
  records, identity rule re-applied, before the local project and legacy stores) and handed to callers (`rerecord`
  writes through it); a v1 rerun does not read it. That it needs nothing else is shown by
  `test_e_f8_4_the_rerun_reads_the_records_the_bundle_embeds`: for every record the lock names, the shipped legacy
  files as imported (`LegacyStore(available_records)`, F3-WO3's drift-checked import) hold the same bytes as the
  bundle's `records/<sha>.json`, so the rerun reads exactly the locked data. E-F8-4's "embedded, the replay runs and
  matches" is a replay with a local store holding no record: step 6 resolves every SHA from the bundle (GP-C1
  embedded 4, TH-C1 1, from_store 0), the rerun runs, `exact_replay` / `MATCH`. Not exercisable in 0.6: a rerun whose
  binder reads the served stack (a v2-compiled document; F6, F8-WO6). **Design-lane question** (with the package's
  ruling round): accept this reading, or require WO6 to add a rerun that reads the served stack.
- **DECISION F8-WO3-2. `extension_use_undeclared(<kind>, <id>)` is listed in `differences`, not `reasons`**, so the
  verdict follows from the comparison as every other step-7 finding does. D5 names the code and the verdict, not the
  member. Alternative: `reasons` plus a forced `MISMATCH`.
- **DECISION F8-WO3-3. An unknown `bundle_format` is checked before the v2 reader runs, and step 1 for it re-hashes
  only what every format indexes** (each file under `artifacts/` against the manifest's `artifacts` map; unexpected
  files counted); report: `inspected_archived_results` / `NOT_RUN`, the one reason
  `bundle_format_unsupported(<value>)`, the raw recorded `environment`, no Amendment 12 member. The v2 reader refuses
  any other value, so its `verify_bundle` cannot run. Alternative: integrity "not checked" (`ok: false`).
- **DECISION F8-WO3-4. "A changed built-in of the running distribution" is a used row whose current registry entry
  has `origin: builtin`** (the recorded origin is not consulted). Alternative: built-in on both sides.
- **DECISION F8-WO3-5. A rerun without a usage set (a plain `Rerun`) does not match:** `differences` gets
  `replay_v2.NO_USAGE`. Step 7's cross-check cannot be skipped silently. `RerunV2(Rerun)` adds `usage`; `Rerun` and the
  v1 path are untouched. As in v1 the rerun is the caller's, made before `replay` is called.
- **DECISION F8-WO3-6. E-F8-5's test-only registry is `edited_registry`**: a shallow copy of the process registry
  whose `_entries` map has named descriptors replaced by `dataclasses.replace` (`self_sha256` `0…0`; plus
  `origin: installed` for the non-built-in case) or removed (`extension_unavailable`); `snapshot()` and
  `registry_sha256` then follow from the copy. `replay_v2` compares the recorded rows with `registry.snapshot()` only.
- **DECISION F8-WO3-7. Reasons accumulate in D5's step order** (integrity, policy, environment, extensions in
  `extensions_used` order, data by SHA); steps 3 to 6 are all evaluated before the decision, so every reason is listed.
  An unknown policy is `NOT_RUN` as in v1. `no rerun was supplied` is appended as v1 does. A changed built-in turns
  an `exact_replay` into `compatible_reproduction`; any other mode stays.
- **DECISION F8-WO3-8. The local store `replay_v2` resolves from, when the caller names none, is an empty project
  store over the installation's legacy records** (`LegacyStore(available_records)`); `run.replay.replay`'s dispatch
  uses this default. Alternative: a project store argument on `replay` (changes the v1 signature).
- **DECISION F8-WO3-9. `ReplayMode` gains `forced_replay` and `ReplayReport.__post_init__` refuses it**
  (`refuse_reserved_mode`, WO1-6); `registry_comparison` and `data_availability` are optional members, absent from a
  v1 report's document. The comparison loop of `run.replay` is reused by `replay_v2` through its private helpers
  (`_as_recorded`, `_verdict_drift`, `_is_verdict_only`); the v1 loop is not refactored (the brief's one dispatch).
- **DECISION F8-WO3-10. Catalogue: the four codes WO3 emits, in a new `catalogue/replay.yaml`, all `refusal`,
  `complete: true`:** `bundle_format_unsupported` (`not_supported`, gap), `extension_unavailable` and
  `extension_changed` (`input`), `extension_use_undeclared` (`bug`, as the ADR marks it). Step 6 reuses
  `data_unavailable` and `store_object_corrupt`. `platform_reference_used` (WO5), `record_referenced`,
  `forced_replay_divergence`, `not_rechecked`, `cache_bypassed` are left to the work orders that emit them.
- **Note F8-WO3-11. `bundle_v2._cross_check_v2` (WO2) raised `KeyError` on a lock without D10's members; it now
  reports the lock tampered** (`d16da4f0`), so step 1 never raises on a tampered archive.
- **Note F8-WO3-12. Re-record tool:** `f8_bundle_v2_support.rerecord(bundle, directory, local, registry=...)` reruns
  a registered v2 case's recorded revision (`V2_CASES`) and writes a new v2 bundle with the bundle's own lock, its
  records served from the bundle first, under the given registry. Tested: after a built-in changed on purpose the
  old bundle replays `compatible_reproduction` with `extension_changed`, the re-recorded one `exact_replay` / `MATCH`
  with the same `data_lock_sha256` and `artifact_r0_sha256` (its `structural_sha256` moves with `extensions_used`).

### F8-WO3 gate numbers (SMM-TR09, 2026-11-27)

Commits `d16da4f0` (integrity fix), `a9534610` (catalogue, doc page, digest re-pin), `a269aabc` (`replay_v2.py`, dispatch,
Amendment 12 members), `1b3b55f2` (tests, re-record tool, E-F8-1 expectation).
- E-F8-1 expectation: computed at `ddac950f` (detached worktree; `run/{replay,bundle,compare,identity}.py` identical to
  the branch point `df796cc2`) with `scripts/f8_v1_replay_reports.py`: 52 bundles x 4 scenarios (inspect: 52
  `exact_replay`/`NOT_RUN`; self: 8 `MATCH`, 44 `MISMATCH`; other_platform: `compatible_reproduction` 8/44;
  changed_lock: 52 `inspected_archived_results`/`NOT_RUN`); `--check` at the head: PASS, 0 reports moved.
- Catalogue digest re-pin (the two `message_entry` fixtures, `t07_schema_fixtures.py --write`): `2b22709239d0c823…`
  -> `4ca46ea400613968f4f9c2efac2bf198ba6c5668a0a0a4ea4b35509c0c5db76d`. No other fixture or served digest moved.
  `msg_catalogue.py check`: PASS, 456 entries, G1/G2 0 missing.
- F0 (own detached worktree at `1b3b55f2`): PASS, M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42.
- `tests/test_f8_replay_v2.py` 38 passed (two cases where parametrised). Mutation controls (not committed), each
  KILLED: E-F8-1 a v1 report gains `data_availability: null` (2 fail); E-F8-4 SHAs walked in reverse (1), embedded
  records not resolved from the bundle (5); E-F8-5 every changed extension treated as built-in (2), unused differences
  not counted (2); E-F8-6 usage cross-check skipped (4); an unknown format read as v2 (2).
- Battery (`test_f8_*` 93, `test_k05_replay` 30, the MSG suites, the surface suites, `test_v03_semantic_roles`,
  `test_doc_pages`, `test_t08_adr0025`, `test_opt_replay`, `test_m02_wo10_coupled`, `test_m02_experiment_job`,
  `test_m04_study_job`, `test_m07_journey`, `test_k05_schemas`, `test_x04_messages`, `test_x07a_*`, `test_x05_lock`,
  `test_f1_operations`, `test_f3_operations`, `test_package_imports`): 3081 passed, 28 skipped, 3 xfailed, 3 failed
  (the three v03 reds, WO1-10).
- ruff check, ruff format --check (1354 files), mypy `src` (370 files): clean.
- Left over: a rerun that reads the served stack (v2-compiled documents, F8-WO6); the ADR's other new codes (their
  work orders); ADR 0019's Amendment 12 pointer paragraph (from WO1b).

## F8-WO5 (orchestrator, 2026-11-27)

- **DECISION F8-WO5-0 (orchestrator). The X07a ruling's ADR 0067 D7 errata E-D7-1 to E-D7-5
  (`docs/X07a-platform-ruling.md` section 5.2, "fold in before ADR 0067 is accepted") are folded into D7, the build
  table row 5 and open question 5 before WO5 is briefed.** Consequences for WO5: platform ids are ADR 0060 D2's
  spelling of ADR 0007 D3.3's registered set (`REGISTERED_PLATFORMS`, `run/replay.py:61`); a per-platform record exists
  only for a registered platform other than the reference `linux-x86_64`; there is no ADR 0025 layout, so
  `<case>.<platform>.json`. Goes on the ADR 0067 acceptance card as an edit before acceptance. Alternative: brief WO5 on
  the unamended text. Reversible by: reverting this docs commit.

## F8-WO5 (per-platform reference records, ADR 0067 D7, exit E-F8-8)

- **DECISION F8-WO5-1. Reference record accessor:** no reference-shaped record with per-platform siblings exists in the
  repository (`tests/fixtures`, `benchmarks`: the sweep finds 0 cases; the only `"artifacts"` carriers are M06 store
  exports, a different shape). The brief's shape `{"artifacts": {...}, ...}` is taken as written; one accessor,
  `platform_refs.record_artifacts`, is the only place that names the key. Reversible by: changing that function.
- **DECISION F8-WO5-2. Notice parameter name:** `platform_reference_used` has one parameter, `platform` (type `text`),
  rendered `platform_reference_used(<id>)` by `replay_v2.coded_reason`. Family `notice`, kind `notice` (as the entries
  of `notices.yaml`), in `replay.yaml` after the WO3 entries; doc page `docs-site/messages/notices.md`.
- **DECISION F8-WO5-3. Tests use the v1 policy id (`V1_POLICY_ID`):** v2 policy refuses a solution state without
  `variable_kinds`; the selection logic is policy-independent, and the moved float differs under v1.
- **DECISION F8-WO5-4. R0 mutation in the invariant test is an id** (`solve-plan.json` `inner_row_ids[0]`): a solver
  counter change is not R0 (only `counters` listed by `_solver_counters` are, and GP-C1's change did not move it).
- Catalogue digest re-pin (the two `message_entry` fixtures, `t07_schema_fixtures.py --write`):
  `4ca46ea400613968f4f9c2efac2bf198ba6c5668a0a0a4ea4b35509c0c5db76d` ->
  `bbdcfb51ae0d95785f91507b1596fefa5753e6c6ab55ad7b49147afd92516d0d`. No other fixture or served digest moved.
- Mutation controls (not committed), each KILLED: `select_reference` ignoring the record (2 fail); invariant skipping
  R0 (1); invariant skipping `reference_sha256` (1); loader skipping the self-hash check (1).

## F8-WO5 Opus review (build lane, 2026-11-27; review of 369150d3..dcf4b89f)

- **DECISION F8-WO5-R1. The loader refuses what spec 4's "validates the above" covers but `dcf4b89f` let through as a
  `TypeError`, `ZeroDivisionError` or silent acceptance:** a file not named `<case>.<platform>.json` for its own `case`
  and `platform` (spec 2; a record copied to another case or platform was selected and its notice named the file's
  platform, not the record's); a departure value that is not a number, a bound <= 0, a non-boolean `near_threshold`; a
  non-string `platform`. The self-hash check now precedes the file-name check (a tampered `case` reports
  `bad self_sha256`). Non-finite numbers need no check of their own: the self-hash's canonical JSON refuses them
  (`CanonicalizationError`, a `ValueError`). Alternative: spec 4's list only. Reversible by: reverting the commit.
- **DECISION F8-WO5-R2. `invariant_problems` reports per-platform records without their reference record** (`all_cases`
  derives the reference path from a per-platform file; before, a missing one raised `FileNotFoundError` in the sweep).
- **DECISION F8-WO5-R3. Point 2 measured (GP-C1, `/home/eajfpeters/.cache/line06/f8-wo5r/r0probe.log`):
  `r0_projection` is right about counters; F8-WO5-4's reason was imprecise.** GP-C1 has 6 events; the counters are
  cumulative and the projection carries the last event's three solver counters (`identity.py:84-85`), here
  `residual_calls 1, jacobian_calls 0, factorizations 0`. +1 on `residual_calls`, `jacobian_calls` or `factorizations`
  of the last event (`solve_closed`) moves `r0_sha256` (3/3); +1 on `property_calls`, `requested_evaluations`,
  `cache_hits` there does not (ADR 0007 D1 "recorded, not reproducible", D5.3); +1 on any counter of event 0 does not.
  No FINDING on the replay path. The R0 invariant test now changes an id and the last event's `residual_calls`
  (acceptance 3: "an id or a counter"). Event `message` is outside `_event_r0` by R-104, not an omission.
- **DECISION F8-WO5-R4. F8-WO5-3 answered: a v2-policy case is cheap.** `declared_kinds(select_route(revision)
  .binding.spec)` (as `f8_bundle_v2_support.rerun_v2` does) gives GP-C1's 32 kinds; `test_selection_under_the_v2_policy`
  runs the selection under `T08-numerical-policy-v2`. The v1 tests stay.
- Tests strengthened (`tests/test_f8_platform_refs.py`, 19 -> 29 passed): the reference-platform selection asserts the
  one difference is the moved float at its path and value, against a self-comparison control (before: any non-empty
  list passed); the fake platform is first compared against the reference by `compare_to_reference`; unknown id
  `solaris-sparc`; file name; malformed departures (4); missing reference record; CRLF and indented file loads (ADR
  0060 D3). Mutation controls (not committed), each KILLED: file-name check removed (1 fail), departure value check (3),
  `near_threshold` check (1), missing-reference guard (1), `select_reference` ignoring the record (v2 test, 1).
- Acceptance: ruff, ruff format --check, mypy src clean; `tests/test_f8_*.py tests/test_x07a_*.py
  tests/test_t07_w5e_*.py` 178 passed (before the counter case); F0 PASS: M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52,
  M8 105/105, M9 42/42. No served digest moved (no catalogue or schema change).
- Left for the F8 `reviewer` pass: (a) `select_reference` does not check the record's `reference_sha256` against the
  reference record at selection time (D7 puts the invariant in a test over every case; a stale record would be used
  between a re-record and the next sweep); (b) no check that a departure's `reference_value` and `platform_value` are
  the values at its `path` in the two records (the path syntax is unspecified); (c) `registered_platform_ids()` drops a
  registered pair missing from `PLATFORM_IDS` silently (fail-safe: such a platform's records are refused).
