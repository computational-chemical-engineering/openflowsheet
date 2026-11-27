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
