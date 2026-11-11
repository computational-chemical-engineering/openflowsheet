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

## F1-WO3 (discovery and integration), 2026-11-11

Files: `src/openflowsheet/registry/discovery.py` (new), `registry/__init__.py`, `registry/selfhash.py`,
`registry/builtin/core.json` (generated), `scripts/registry_builtin.py`, `messages/catalogue.py` (the pre-freeze
call), the D8 call sites (`application/local.py`, `cli.py`, `bindings/http.py`, `bindings/mcp.py`),
`tests/f1_harness.py` (fake distributions), `tests/test_f1_discovery.py`; T07's allowlist and counts. The process
registry now holds 42 built-ins; its `registry_sha256` on this checkout is `f4722624…` (the legacy table alone is
still `713489f2…`); WO5 pins the value over all tables.

- **DECISION W3-1. The entry point's name is the `entry_point` string** in quarantine rows, snapshot rows and
  `extension_invalid`/`extension_load_failed` params (it is the namespace, D7). The document's `namespace` must
  equal it, else `extension_invalid(<entry point>, /namespace)`. Alternative: `name = value` spelled out.
- **DECISION W3-2. Discovery order and what is loaded.** Entry points are read from `importlib.metadata.distributions`
  (every copy, so one distribution seen twice is visible), distribution names normalised by PEP 503; deduplicated
  on (normalised name, version, entry-point name); sorted by (name, entry point, version, value). Checks, first
  wins: `namespace_conflict` (two (name, version) pairs declare it; both quarantined), `reserved_namespace` (D7's six
  plus the first segment of every built-in id), then load (`extension_load_failed`, any `Exception`, its class
  logged). A package quarantined by name is not loaded. Alternative: load every entry point first.
- **DECISION W3-3. Import root of an entry-point package:** `find_spec` of the entry point's top-level module; the
  directory above a package's `__init__.py`, or a module's directory. A namespace package or zip import has no
  root: each non-empty `modules` is then `self_hash_unavailable(<id>, <first path>)` (`selfhash` takes `None`).
- **DECISION W3-4. Message catalogues are pre-validated on a scratch `Catalogue()`** with MSG's own `register`
  (schema, namespace, prefix, clashes), so step 4 cannot fail; a failure, or a resource that cannot be read, is
  `extension_invalid(<entry point>, /descriptors/<i>/payload/catalogue)`. Codes are unique across a package's
  documents. Step 4 registers them sorted by (id, version key). `Registry.build(catalogue_register=None)` (the
  default, tests) registers none; `default_registry()` passes `messages.catalogue.register`.
- **DECISION W3-5. Limitation codes** (D2) are checked after the per-descriptor pass, against the core codes (a
  lookup on a throw-away `Catalogue()`, made only when a descriptor has limitations) plus the codes of the package's
  own catalogues; a miss is `extension_invalid(<entry point>, /descriptors/<i>/limitations/<j>/code)`, declared
  order; for a built-in it raises. Alternative: a new code.
- **DECISION W3-6. The pre-freeze call.** `Catalogue(registry_first=True)` is the process `CATALOGUE` only; while not
  frozen its lookups call `registry.before_catalogue_freeze()`, which raises `RuntimeError("catalogue lookup during
  registry build")` on a thread running any `Registry.build` (a `threading.local` depth) and otherwise calls
  `default_registry()`. A re-entrant `default_registry()` on its building thread raises instead of deadlocking.
  T07: one `threading.local` and one `ContextVar` (the usage recorder) allowlisted; counts `ContextVar` 1 → 2,
  `threading.local` 0 → 1.
- **DECISION W3-7. D8 call sites:** `LocalApplication.open` (so `create`) and `in_memory`; `cli.main` inside its
  `try`, after argument parsing. The HTTP and MCP servers start through `cli.main` (`serve-http`, `serve-mcp`) and
  serve an application `LocalApplication.open` made, so both calls precede them; the bindings themselves may import
  only the dispatch surface (T07 G14, `test_t07_w6a_http.py`, `test_t07_w6b_mcp.py`), so they carry no call.
- **DECISION W3-8. `core.json`:** `functional_contributor` `cost`, `lca`, `derived`, version `1.0.0`, status
  `released` (the three shipped in the `v0.4.0` tag), title `Assessment contributor <name>`, `payload {}`;
  `factory` = the class each module passes to `register_contributor` (read by AST, so the generator registers
  nothing); `modules` = every `*.py` under the defining module's directory (D6; `cost` and `derived` share
  `assessment/cost/`); `pip_extra` `lca` for `lca` (Brightway), else null. The generator writes and checks both
  tables; its summary line names the table count.
- **DECISION W3-9. `--write` with a stale or missing table (W2-7):** the generator no longer constructs an
  application; signatures are `local._model_view` over `MODEL_SIGNATURES`, sorted (its key set equals
  `MODEL_BUILDERS`'s, which the generator may not name). A test holds them equal to `list_models()`, and another runs
  `write()` with the process registry unbuilt and its table reader raising. `legacy.json` is byte-identical.
- **DECISION W3-10. Factory resolution** (`Registry.factory`) returns the attribute (indexed by `key`); nothing is
  constructed. Refusals (`FactoryRefusedError`), in order: `factory_unavailable(<kind>, <id>)` for a null factory or
  a legacy-form method with `selectable: false` (`pr-lib-v1`, `wilson-ig-v1`, W2-5; also `syn001.cascade`);
  `platform_unsupported(<id>, <platform>)`; `dependency_missing(<id>, <extra>)` when the import fails and
  `pip_extra` is set (else the `ImportError` propagates). **For the design lane:** `factory_unavailable` is not in
  the ADR's code table; alternatives are `model_unsupported` (units only) or D6 naming another factory.
- **DECISION W3-11. Usage recorder:** `usage()` sets a fresh `Usage` in a `ContextVar` for its block; `resolve` and
  `factory` add (kind, id, version). `admit`, `admission_matrix` and `extensions_used` use an unrecorded lookup
  (queries, not uses). Nested blocks record into the innermost only. No executor copies the context yet (F8).
- **DECISION W3-12. Extensions used:** `Registry.extensions_used(references)` over (kind, id, version or `None` =
  highest) references; rows carry identity and D9's evidence fields; unmatched references are listed apart;
  `notices()` is D9's flag. Extracting the references from a run's documents is left to F8. **For the design lane:**
  a revision's `model.version` (`0.0.0-declared`, `0.3.28`, …) is not a registry version, so "the unit ids and
  versions of its revision" (D8) needs a mapping rule.
- **DECISION W3-13. E-F1-7's process paths run in fresh interpreters** (the test process's catalogue is frozen by
  then); the in-process tests check the guard and a test catalogue.

Not in WO3: catalogue entries for the F1 codes, `factory_unavailable` included (WO4a); the operations (WO4a, WO4b);
`builtin-sha256.txt` over all tables, CI, manifest (WO5); copying the usage context into executors and deriving
references from run documents (F8).

## F1-WO4a (operations, pair form), 2026-11-11

Files: `application/capabilities.py` (new: the two operations over a registry), `contract.py` (`Inspection`), `types.py`
(`CapabilityDescriptor`, `CapabilityPage`, `AdmissionPair`, `AdmissionReport`), `operations.py` rows, `authz.py`
rights, `local.py`, `cli.py` (`capabilities`, `admission`), `schemas/application-results.schema.json` (three `$defs`),
`bindings/descriptions/{list_capabilities,check_admission}.md` and `REVIEW.json`, `messages/catalogue/registry.yaml`
(new) and `api_errors.yaml` (`not_found`), `messages/render.py` (`closest`), `scripts/msg_catalogue.py`,
`scripts/m07a_rc.py` (c_9), `tests/f1_schema_support.py`, `tests/test_f1_operations.py` (E-F1-10); ADR 0019
Amendment 7 pointer, `interfaces-frozen.md`, register R-1030; generated pages, routes, fixtures, support envelope.

- **DECISION W4a-1. The F1 codes live in a new `catalogue/registry.yaml`** (refusals and notices together, 15
  entries, all complete), and MSG-G2's scanner reads the code of `Coded(...)`, so a registry code without an entry
  fails G2. Alternative: append to `refusals.yaml`/`notices.yaml` and leave `Coded` unscanned (G2 would not see them).
- **DECISION W4a-2. `list_capabilities.kind` is one kind or a list** (`anyOf`). Over HTTP a query member carries one
  value (§11.3 refuses a repeated one), so HTTP filters by one kind per request; Python, CLI and MCP take a list.
  Alternative: a comma-separated string, or a binding change admitting repeated query members. **For the design
  lane.**
- **DECISION W4a-3. `check_admission`'s request is a closed object with exactly one of `pair` and `revision`**
  (`minProperties`/`maxProperties` 1); `revision` is `{type: object}`, its checks are WO4b's. Until WO4b the draft
  form is refused `unsupported`, and `check_admission.md` says so; WO4b edits that sentence and re-takes D_9 within
  c_9. Alternative: the pair form only in WO4a (the schema, and the digest, would move twice).
- **DECISION W4a-4. `AdmissionReport.notices` is every pair's notices once each**, in the registry's notice order
  (code, then params by name, W1-12). Alternative: report-level notices only for findings outside any pair.
- **DECISION W4a-5. The default definition** is the one distinct `conn:` name across all of the unit's `requires`
  clauses; none or several is `invalid_request` at `/pair/definition`. Alternative: only a one-token clause counts.
- **DECISION W4a-6. An unknown registry id or version is `not_found` with `detail {kind, id, version?,
  suggestions}`**: close ids by MSG's suggestion rule (`messages.render.closest`, factored out of `suggestions`), or
  for an unknown version the id's registered versions. `not_found`'s entry gains the optional params `kind`, `id`,
  `version` and two variants ("No <kind> with the id <id> is registered."). Alternative: a new code.
- **DECISION W4a-7. The operations look descriptors up through `Registry.descriptors()`**: no usage record (W3-11),
  and the private `_lookup` stays private.
- **DECISION W4a-8. The cursor** is the unpadded base64url of the canonical JSON `[kind, id, version]` of the page's
  last item; the next page is the items after it in (kind, id, version key) order, so it survives later registrations
  and never repeats an item. Filters are not in it. A cursor that does not decode to three strings with a D2 version
  is `invalid_request` at `/cursor`.
- **DECISION W4a-9. CLI conveniences** `capabilities [--kind K]… [--prefix P] [--cursor C] [--limit N]` and
  `admission --unit U --method M [--definition D] [--unit-version V] [--method-version V] | --revision FILE` print
  the operation's canonical JSON, through `dispatch` on `LocalApplication.in_memory()` (no project); a refusal as
  `api` prints it; exit 1 when no call was made. Alternative: `explain`'s direct path; a text rendering.
- **DECISION W4a-10. `capability_descriptor`** `$ref`s each declared field to `extension-descriptor.schema.json`'s
  property and each computed field to `registry-snapshot.schema.json#/$defs/extension`'s, closed; `contributed_by`
  optional. The fixtures mask `registry_sha256`, `self_sha256` and `distribution_version` (`REGISTRY_VOLATILE` in
  `scripts/t07_schema_fixtures.py`): they follow the code, not the shape.
- **DECISION W4a-11. Surface link c_9, R-1030, register block R-1030…R-1039** (R-1010…R-1019 is X04's; R-1020 is
  on `wp/V04-after`). D_9 = `e59f3d22…`; `without_f1` leaves D_8 exactly. Both texts are pinned
  (`F1_FILE_SHA256`) and recorded pending both reviews, so `test_every_description_is_reviewed_by_both_lanes` is
  red until the design lane and Frank record theirs (T08.A18's rule, as X04).
- **DECISION W4a-12. Counts and generated files:** A20's operation count 23 → 25 (envelope, `t08_support_matrix.py`,
  `docs/support-matrix.md`); `routes.js` 23 routes; the message and operations pages; the `message_entry` fixtures
  (catalogue digest).
- **DECISION W4a-13. `capability_missing`'s `gap.capability` is a fixed text**; the missing token is
  `params.capability`. D5 says `gap.capability` = the third param, but MSG's `gap` is static per entry. **For the
  design lane:** a templated gap (an MSG change) or the reading "the agentic layer reads `params.capability`".
- **DECISION W4a-14. `interfaces-frozen.md`** gets the §1 paragraph (two methods, three result-type names, plus
  `AdmissionPair`) and a §2 paragraph that also records WO1's two schemas, which no WO had listed.

Not in WO4a: the draft form (WO4b); the reviews of the two descriptions (design lane, Frank); `builtin-sha256.txt`,
CI and the manifest (WO5).

## F1-WO4b (draft form), 2026-11-11

Files: `application/capabilities.py` (the draft form), docstrings in `local.py` and `operations.py`,
`bindings/descriptions/check_admission.md` and `REVIEW.json`, `scripts/m07a_rc.py` (`F1_FILE_SHA256`, D_9),
`tests/test_t08_w2_surface_digest.py` (`F1_SERVED_SHA256`), register R-1030 (re-taken in place),
`interfaces-frozen.md` (one clause), `tests/test_f1_draft_admission.py` (new, E-F1-11),
`tests/test_f1_operations.py` (draft requests on the four transports). No schema and no R4-G3 snapshot moves.

- **DECISION W4b-1. The draft form reads `schema_version`, `component_set` and each instance's `id` and `model.id`,
  nothing else.** A member it cannot read is `invalid_request` at `/revision/<pointer>` (`schema_version` not an
  integer, `component_set` not an object, `instances` empty or not an array, an instance not an object, an empty or
  missing `id` or `model.id`). Alternative: validate `process-revision.schema.json` first, which a draft without
  `semantic_role`, `parameters` or `policy` fails although admission does not validate a revision (D5, D11).
- **DECISION W4b-2. Versions: the revision's `model.version` is not read**; each pair is taken at the highest
  registered versions, D11's default for the pair form. E-F1-11 needs no mapping rule, so W3-12's question stays
  open; WO3 recorded no default for it. **For the design lane:** if a v1 `model.version` should ever select a registry
  version (W3-12, D8's extensions used), the draft form follows that rule.
- **DECISION W4b-3. What refuses the whole report, and what one pair.** An integer `schema_version` other than 1 is
  `revision_unsupported` (D11 names v2; later versions are not readable either). `components_unsupported` from
  `component_basis` (a CoolProp revision without exactly one admitted fluid) is `revision_unsupported` with
  `detail.unbound` `unsupported(components_unsupported)` and the binder's `hint`, the string form a solve's
  admission and the job runner use. A model id no `unit_model` is registered under is `not_found` with
  `detail {kind, id, suggestions}`, as in the pair form. A registered unit that is not bindable (`syn001.cascade`)
  is that pair's `model_unsupported` (D5 step 0). **For the design lane:** alternative for an unregistered id, that
  instance's pair refused `model_unsupported(<model>)` (the binder's code), keeping the report whole.
- **DECISION W4b-4. E-F1-11's binder half on the revisions the binder refuses earlier.** Every instance of every M1
  revision is replaced once (300 replacements), its model cycled through the 14 models `MODEL_BASES` does not admit on
  SYN-001, the variant-backed `c1.reactor` and `c1.reactor_standin` excepted (the binder refuses an unpinned one
  `model_variant_mismatch` before R-288's check). On 38 revisions (216 replacements) the binder gives
  `model_unsupported(<replacement>)`, and only the replaced instance has that model. The other 12 (the eleven A02
  revisions, GUESS specifications, `specification_role_unsupported`; T06-STR06, `specification_unsupported`) are
  refused by the revision binder's reader before its model check; the test pins them (`BINDER_REFUSES_FIRST`) and
  holds their refusal unchanged by the replacement. `check_admission` refuses the replaced instance
  `capability_missing` on all 50. **For the design lane:** whether this reading of "for the same instance" is
  accepted, or E-F1-11 names the 38.
- **DECISION W4b-5. F0's M1 holds 50 revisions, not 49.** `benchmarks/f0/corpus.json`'s M1 equals T07's `CORPUS`
  (W0.2's 50); the test pins 50. **For the design lane:** E-F1-11's "(49)" reads as a miscount.
- **DECISION W4b-6. The description and D_9.** `check_admission.md` describes the draft form's request and the
  pairs' `instance` in place of "refused unsupported in this build"; to stay within G15's 1500 characters (1489 now)
  it does not name the v2 refusal. Hash `ec6b3349…`, recorded pending both reviews; `F1_FILE_SHA256` follows. D_9
  `e59f3d22…` → `24966bee…`, re-taken within c_9 and R-1030 as that entry's "Watch for" says; `without_f1` still
  leaves D_8 exactly.
- **DECISION W4b-7. Both forms call `Registry.admit`** with the looked-up ids and versions (the pair form called
  `capability.admit` on the same three descriptors: one function, one verdict; E-F1-10's documents are unchanged).
  In-process, neither or both forms is `invalid_request` (was `unsupported`); the request schema refuses both on every
  transport before the call.
- **DECISION W4b-8. E-F1-10's fixture gains three draft requests** (admitted; one instance refused; schema_version 2),
  identical on Python, CLI, HTTP and MCP.

Not in WO4b: the reviews of the two descriptions (design lane, Frank); a v1 `model.version` mapping (W3-12);
`builtin-sha256.txt`, CI and the manifest (WO5).
