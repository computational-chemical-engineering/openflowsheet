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

Not in WO1 (stated in `registry/__init__.py`): `default_registry()` and the built-in table files (WO2, WO3);
entry-point discovery and namespace rules; message-catalogue registration and the MSG pre-freeze call; validation of
`limitations` codes against the catalogue (D2; needs the package's message document, WO3); factory resolution
(`platform_unsupported`, `dependency_missing`); the usage recorder on `resolve`.
