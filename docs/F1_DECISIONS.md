# F1 build decisions (append-only)

Build-lane choices for package F1 (the extension registry) that ADR 0060 leaves open. The ADR's core items are frozen by
R-941; nothing here changes one. Each line: `DECISION`, the choice, the alternative, and where it lives. Each is
revertible on its own. Batched for the package's one design-lane ruling round (CLAUDE.md, agent budget).

## F1-WO1 (registry core), 2026-11-11

Files: `src/openflowsheet/registry/{__init__,tokens,descriptor,selfhash,capability,snapshot}.py`,
`schemas/extension-descriptor.schema.json`, `schemas/registry-snapshot.schema.json` (both marked "DRAFT until ADR 0060
is Accepted" in their `description`), `tests/test_f1_registry_core.py`, `tests/fixtures/registry/`.

- **DECISION W1-1. `Registry.build` takes loaded packages in WO1.** `Registry.build(builtin_tables=, packages=,
  attestations=, builtin_root=, builtin_version=)`, where `packages` are `ExtensionPackage` objects (an already loaded
  package document plus its distribution, version, entry point and import root). WO3's `entry_points=` will load entry
  points into `ExtensionPackage`s and apply the namespace rules (reserved, conflict, deduplication) before this path.
  Alternative: no packages until WO3, which would leave E-F1-8's attestation case (non-built-ins only) untestable.
- **DECISION W1-2. Package content quarantine is in WO1, namespace quarantine in WO3.** WO1 quarantines a package for
  `extension_invalid` (package schema, namespace prefix of an id, duplicate (kind, id, version), a non-canonical node),
  `capability_unknown`, `reserved_capability` and `self_hash_unavailable`, first problem wins, in document order. Two
  packages registering the same (kind, id, version) raise (`namespace_conflict`) here, since WO3's discovery quarantines
  both before they reach it. Alternative: all quarantine in WO3.
- **DECISION W1-3. The package document's schema is `$defs/package` of `extension-descriptor.schema.json`.** D7 defines
  the document and `extension_invalid(<entry point>, <pointer>)` implies a schema; pointers are relative to the package
  document (`/descriptors/0/title`). Alternative: a third schema file.
- **DECISION W1-4. Payload schemas present in WO1: `message_entries` only** (`$defs/payload_message_entries`, D7). The
  legacy payloads (D6) are added with WO2, which reads `describe()` to pin their member types, and ADR 0061's with its
  WO. Until a kind has a `$defs/payload_<kind>`, its payload is checked as an object (`descriptor.PAYLOAD_DEFS`).
  Alternative: write the legacy payload schemas now from D6's table without the generator's data.
- **DECISION W1-5. A `connection_definition` must provide `conn:<its id>`** (D5: "P_d always contains conn:<definition
  id>"), checked at registration: `extension_invalid(<entry point>, …/provides)` for a package, a build error for a
  built-in. Alternative: admission adds `conn:<id>` to P_d itself.
- **DECISION W1-6. Resolution is stored on the registered descriptor.** After every descriptor is registered, each one
  records its `unresolved` tokens (registry-derived names no registered descriptor gives, D4), so `admit(unit, method,
  definition)` stays a pure function of three registered descriptors. The token spelled in `capability_unresolved` is
  the normalised one (level kept). Alternative: `admit` takes a resolver argument.
- **DECISION W1-7. Static `vocab` space is empty until ADR-F4 installs its validator**, so every `vocab:` token is
  `capability_unknown`. Alternative: grammar only until F4.
- **DECISION W1-8. Static `convention` space = the four conventions `docs/interfaces-frozen.md` §3 lists**
  (`SYN-001-ref-v1`, `PR-C1-ref-v1`, `IAPWS95-ref-v1`, `COOLPROP-DEF-ref-v1`). `WILSON-IG-ref-v1` and
  `S10-VER-ref-v1` (in `thermo/wilson_ig.py`) are not in §3 and so not in the table. Alternative: also the two Wilson
  conventions. Needs a design-lane look: §3 may be missing them.
- **DECISION W1-9. Registry-derived names are checked against the id grammar** (D2), since their names are ids; `x:`
  names must be `<namespace>.<name>` with D7's namespace grammar. A failure is `capability_unknown`. A built-in
  providing an `x:` token is `reserved_capability` (it has no extension namespace). Alternative: token grammar only.
- **DECISION W1-10. `stability`:** `record_type`, `correlation_form`, `data_source`, `message_entries` core;
  `property_method`, `unit_model`, `connection_definition` core only for descriptors of the built-in table named
  `legacy` (D6's legacy forms); `functional_contributor` core for built-ins; every other kind `preview`. The per-id
  exception ADR 0061 D1 states (`record_type` `assay` 0.1.0 preview) is left to ADR 0061's WO, which registers it.
  Alternative: a payload marker for the legacy form.
- **DECISION W1-11. `evidence_class` `reviewed` = non-built-in with a matching attestation**, whatever its declared
  status, read literally from D9; `effective_status` of a non-built-in is capped at `tested` without one. Alternative:
  `reviewed` only when the attested status is at least `reviewed`.
- **DECISION W1-12. Coded params are strings, with names:** `capability_missing {unit, method, capability}`,
  `model_unsupported {model}` (its catalogue entry's), `capability_unknown`, `reserved_capability`,
  `capability_unresolved {token}`, `extension_invalid {entry_point, pointer}`, `self_hash_unavailable {id, path}`,
  `extension_unreviewed {id, origin}`, `preview_kind {kind, id}`, `namespace_conflict {namespace}`. Notices sort by
  (code, params by name), UTF-8. The catalogue entries are WO4a's.
- **DECISION W1-13. `quarantined` in the snapshot sorts by each row's canonical JSON bytes** (D10 says "sorted").
- **DECISION W1-14. `implementation.modules` paths:** relative POSIX, no empty, `.` or `..` segment, no backslash
  (schema pattern). Alternative: a narrower character set.
- **DECISION W1-15. Registrations an added schema and layer require (existing files touched):**
  `schemas/registry.json` (two lines, R-213); `tests/test_package_imports.py` `LAYERS` gains `registry`;
  `scripts/t08_numerical_policy.py` `ADDENDA` gains `benchmarks/f1/numerical_policy_external.yaml`, which classifies
  `descriptor_sha256`, `self_sha256`, `registry_sha256` as exact (the closed `sha256` partition, ADR 0025 D2.3; the
  ST/OPT precedent), and `tests/test_m05_study_record.py`'s pinned `ADDENDA` order gains `f1`;
  `tests/data/t07_global_state_allowlist.json` gains one `@cache` entry (`registry/descriptor.py`'s schema
  validators) and `tests/test_t07_global_state.py`'s `cache` count goes 39 → 40 (G20: "decide and list them"). No
  identity file is touched.
- **DECISION W1-16. E-F1-5 on synthetic built-ins pins its own constant**,
  `tests/fixtures/registry/synthetic-builtin-sha256.txt`, over `tests/fixtures/registry/synthetic/` (a table file and a
  three-file import root). WO5 commits `builtin-sha256.txt` for the real built-ins. The test also recomputes the value
  with `hashlib` and `json.dumps`, independent of `openflowsheet.canonical`.
- **DECISION W1-17. D1's kind list is stated once, as the schema's `kind` enum; no Python tuple repeats it.** Found by
  V03.A31(a) (`tests/test_v03_semantic_roles.py`: no file under `src/` contains the text `semantic_role`, the proxy
  for "nothing reads ADR 0054's revision role"), which a kind name in `src/` would fail although the registry reads no
  role. The A31 claim stays true: the registry never reads a revision. `tests/test_f1_registry_core.py` holds the enum
  to D1's table. **For the design lane:** A31(a) is a text scan; once ADR-F6 registers `semantic_role` descriptors
  (a source module naming the kind), A31(a) needs an amendment that scopes it to readers of the revision field.
  Alternative: narrow A31 now (a check relaxed by the build lane: not taken).

Not in WO1 (stated in `registry/__init__.py`): `default_registry()` and the built-in table files (WO2, WO3);
entry-point discovery and namespace rules; message-catalogue registration and the MSG pre-freeze call; validation of
`limitations` codes against the catalogue (D2; needs the package's message document, WO3); factory resolution
(`platform_unsupported`, `dependency_missing`); the usage recorder on `resolve`.

## F1-WO2 (legacy built-ins), 2026-11-11

Files: `scripts/registry_builtin.py`, `src/openflowsheet/registry/builtin/legacy.json` (generated),
`src/openflowsheet/registry/legacy.py`, `default_registry()` in `registry/__init__.py`, the legacy payload `$defs` of
`schemas/extension-descriptor.schema.json`, `tests/test_f1_legacy_builtins.py`. `registry_sha256` of the legacy
table on this checkout: `713489f2…` (not committed; WO5 pins `builtin-sha256.txt`).

- **DECISION W2-1. The legacy payload schemas apply to the built-in table `legacy` only.**
  `descriptor.LEGACY_PAYLOAD_DEFS` maps `property_method`, `unit_model`, `connection_definition` to
  `$defs/payload_<kind>_legacy`; `descriptor_problem(..., legacy_form=True)` uses it and refuses any other kind in
  that table (`/kind`). `PAYLOAD_DEFS` stays kind-wide (`message_entries`). Alternative: kind-wide `PAYLOAD_DEFS`
  entries, which would force the legacy shape on extension (v2, `preview`) descriptors of these kinds (D1).
- **DECISION W2-2. CoolProp's payload has a `per_component` member.** `describe()` varies per fluid not only in
  `reference_convention` but in `properties` (`lnphi_<fluid>`) and derivative inputs (`n_<fluid>`). `per_component`
  maps each of the 123 fluids to `{reference_convention, properties, derivative_inputs}`; the top-level `properties`
  and `derivative_inputs` are those every fluid declares, in describe order (`h s v Z cp Psat Tsat`; `T P`);
  `reference_convention` is `per_component`. `per_component` is null for the other six. **For the design lane:**
  D6's closed payload names a fluid → convention map but no member for it; this adds one member carrying it and the
  per-fluid lists. Alternatives: the union of the lists (not faithful per fluid); one descriptor per fluid.
- **DECISION W2-3. Payload member types.** `phases`, `flashes`, `properties`, `derivative_inputs`: distinct non-empty
  strings in describe order (`$defs/names`). `derivative_inputs` are the keys of `describe().derivative_order`
  (orders are not recorded; every legacy order is 1), equal to `DERIVATIVE_INPUTS` where a module declares it.
  `signature` is typed to its six top-level members; the inner shape stays `application-results`'
  `model_registry_view`'s. The schema states three cross-member rules: `selectable` iff `bases` is non-empty;
  `per_component` an object iff `reference_convention` is `per_component`; `signature` null iff not `bindable`.
- **DECISION W2-4. The synthetic fixture's `legacy` table now satisfies the legacy payloads** (its payloads were
  placeholders), so its pinned E-F1-5 constant moved `c20a546d…` → `5334b185…`; the independent recomputation in
  `test_f1_registry_core.py` agrees. Alternative: rename the synthetic table, losing its legacy-stability case.
- **DECISION W2-5. How the generator constructs providers.** Through `basis_provider` for each selectable basis
  (CoolProp once per fluid); `pr-lib-v1` and `wilson-ig-v1`, which no basis selects, by their own constructors (it
  raises if either becomes selectable). The tests construct all seven by their own classes, an independent route.
  `implementation.factory` is `revision_binding:basis_provider` for all seven, as D6 states, although
  `basis_provider` cannot construct `pr-lib-v1` or `wilson-ig-v1`. **For WO3 / the design lane:** factory
  resolution for those two must refuse (or D6 names another factory for unselectable providers).
- **DECISION W2-6. Implementation-set attribution.** Providers: `corpus_identity._hashed_files` of the provider
  class's module (F0's own scan: `coolprop-heos-v1` + `_coolprop_heos_fluids.py`, `wilson-ig-v2` + `wilson_ig.py`).
  Units: F0's cross-check rule (`test_m9_holds_every_legacy_unit_module_d9`): an M9 legacy unit module is attributed
  to every id it declares as `MODEL_ID` or in `MODEL_IDS`. So `c1.reactor_standin` = `c1/reactor.py` +
  `c1/reactor_standin.py` (both declare it); `thermal.pump`, `compressor`, `turbine` = `thermal/machines.py`;
  `c1.reactor_surrogate`, which F0 attributes none to, = `c1/reactor.py` (D6's fallback, R-301). Union = M9's 35.
- **DECISION W2-7. Signatures come from the public `LocalApplication.in_memory().list_models()`.** **For WO3:** when
  `in_memory` starts calling `default_registry()`, `--write` must still run with a stale or absent table (for
  example by building signatures with the binder's `_model_view` instead, or by tolerating a build failure there).
- **DECISION W2-8. Table format and loading.** A JSON array sorted by (kind, id), indent 2, keys sorted, UTF-8,
  final LF; the table name is the file stem. `registry/legacy.py` reads it through `importlib.resources`; package
  data `"openflowsheet.registry" = ["builtin/*.json"]`; T08.A32's `SHIPPED_DATA` lists `registry/builtin/*.json` as
  the project's own data. Envelope fields: titles `Legacy property method <id>`, `Legacy unit model <id>`,
  `Legacy connection definition nTP-v1`; `limitations []`, `data_rights null`, `platforms ["any"]`; `pip_extra`
  `coolprop` (the one extra in `pyproject.toml` naming CoolProp) for `coolprop-heos-v1`, else null.
- **DECISION W2-9. `syn001.cascade` requires `[["conn:nTP-v1"]]`** (D6's "none" read as no legacy clause); legacy
  units provide nothing. Its refusal is step 0's `model_unsupported` either way.
- **DECISION W2-10. `default_registry()`:** a module-level `_process_registry` set once under a `threading.Lock`,
  through one `global` line (T07 G20 allowlist entry; the `global` count 2 → 3). WO2 builds it from `legacy.json`
  alone. Alternative: `functools.cache`, which does not guarantee one build under concurrent first calls.
- **DECISION W2-11. `--check`** compares the committed bytes with the regenerated ones; on a difference it prints
  the JSON pointers (first ten and the count, or "formatting only"); on success it also builds a registry from the
  committed table and prints its `registry_sha256`. D3's import-closure check has nothing to check yet (no v2
  built-in).
- **DECISION W2-12. E-F1-2's probe method** provides every token a registered descriptor names outside `legacy`
  (only `conn:nTP-v1` today) and every static non-`legacy` name (`flash:TP`, the four conventions): a stronger
  probe than the registered set alone, which is a single token.

Not in WO2: entry points in `default_registry()` and the call sites of D8 (WO3); `core.json`, `records.json`;
the real-built-ins constant of E-F1-5 (WO5).
