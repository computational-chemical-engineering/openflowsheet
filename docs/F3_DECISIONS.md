# F3 build decisions (append-only)

Build-lane choices for package F3 (component data core) that ADR 0061 leaves open. ADR 0061 is Proposed; the build
follows its text as it stands (D1 to D7, Amendment 3, the W1 P1 and P2 rulings applied). Where it is silent or
ambiguous, the reading taken is the one that changes no existing byte. Each line: `DECISION`, the choice, the
alternative, and where it lives. Each is revertible on its own. Batched for the package's one design-lane ruling round
(CLAUDE.md, agent budget).

## F3-WO1 (record model), 2026-11-18

Files: `schemas/record-v2.schema.json` ("DRAFT until ADR 0061 is Accepted" in its `description`),
`src/openflowsheet/records/{__init__,model,normalize,identity,validate}.py`,
`src/openflowsheet/registry/builtin/records.json` (generated), `src/openflowsheet/messages/catalogue/records.yaml`,
`tests/test_f3_record_model.py`, `tests/fixtures/records/`.

- **DECISION WO1-1. Flat layout.** A record's type members (D3, D5) sit beside the envelope (D1) at the top level, the
  schema discriminating on `record_type` by `if`/`then` with `unevaluatedProperties: false` at the root. Read from D2
  ("`parameter_set.components`", "the record without its top-level `volatile` member") and D12 (the set's fields named
  as record fields). Alternative: a nested `payload` member. Lives in the schema and `records.normalize`.
- **DECISION WO1-2. Registrations an added schema and layer require.** `schemas/registry.json` gains
  `record-v2.schema.json` (R-213); its new `sha256` name `file_sha256` is classified exact by
  `benchmarks/f3/numerical_policy_external.yaml` (`F3-numerical-policy-external-v1`), audited after F1's in
  `scripts/t08_numerical_policy.py` `ADDENDA` and in `tests/test_m05_study_record.py`'s pinned order (policy digest
  `6b449911…` unmoved); `tests/test_package_imports.py` `LAYERS` and `.codehealth/config.toml`'s layer order gain
  `records`, above `registry`. Alternative for the policy: add the schema to F1's table (changes F1's table).
- **DECISION WO1-3. Required members** (they keep `null`, `[]` or `{}` at D2 step 2a): envelope `record_format`,
  `record_type`, `type_version`, `id`, `name`, `sources`; source `version`; `legacy` all five (`position` and
  `file_fields` nullable); component `synthetic`, `amount_basis`, `charge`, `elemental_verification` (`molar_mass`'s
  presence is D7's `amount_basis_invalid`, not the schema's); parameter set `components`, `entries`, `synthetic`;
  Constant `value`, `unit`, `kind`, `provenance`; entry `property`, `form`, `provenance` (plus `value`, `unit`, `kind`
  for `constant`, `coefficients` otherwise, the other set forbidden); provenance `origin`, `derivation`, `source` (so an
  empty `origin` stays and is `provenance_invalid`, as D7 states); input `scheme`, `sha256`; formation `phase`, `h`;
  transition `from`, `to`, `h`; uncertainty `type`. `anchor_phase` is optional, so a stated `null` is removed and
  re-derived (D2 step 5's idempotence). Everything else is optional. Alternative: D3's "required" column alone.
- **DECISION WO1-4. Step 2a reads the schema.** `normalize.strip_empty` walks the record with the schema (`$ref`,
  `allOf`, the `if` branch that holds, `anyOf` branches by type) to decide which members are required; a member the
  schema does not describe counts as optional (it is refused at step 6 anyway). `legacy.file_fields` is a free object,
  so its empty members are removed too. Alternative: a hand table of required members (would drift from the schema).
- **DECISION WO1-5. Step 1.** Text starting with `{` is JSON, a repeated key refused `record_schema_invalid("")`; other
  text is `yaml.safe_load` (as D2 says, last duplicate wins there); a non-object, or a node `canonical.first_noncanonical`
  refuses, is `record_schema_invalid(<pointer>)`. A parsed document is copied through canonical JSON, so `1.0` and `1`
  are one value from step 2 on. Alternative: `canonical.load_document` (refuses with a message path, not a pointer).
- **DECISION WO1-6. Step 6 order and form.** The schema is checked first, on the projection with `volatile`
  re-attached (so a member outside the closed volatile set refuses); a schema failure gives one
  `record_schema_invalid(<pointer>)`, the first error by path that is not `unevaluatedProperties` (a member failing its
  type branch is also reported unevaluated at the root), and no other check. Otherwise every D7 error is returned,
  sorted by (code, params). NFC key collisions found at step 3 are reported with step 6's errors. Alternative: all
  schema errors.
- **DECISION WO1-7. Rules D7 names without a code.** A core property id with another form or phase, an un-namespaced
  property unknown to the record type, `elemental_verification` against `elements` (D3's iff), a duplicate key (D2 step
  4), `segment_types` on a basis other than `segment_mol`, a parameter-set index that is not a component key, a
  `wilson_lambda` without two distinct indices or with a value not above 0, and an unregistered (`record_type`,
  `type_version`) are `record_schema_invalid` at the member. A core property with another kind (a constant's, or a
  form's result kind) is `record_unit_invalid`. A validity variable the form lacks (`T`, `P` for a constant and for the
  set's domain) is `validity_range_invalid`. Alternative: new codes (would need catalogue entries the ADR does not list).
- **DECISION WO1-8. Formula and elements.** `formula_elements_invalid` reads the formula as element symbols with
  optional integer counts in any order (`CH3OH`), no parentheses, charges or Hill-order check; a formula that does not
  read so is the same error. Only a `mol` record with a formula and non-null `elements` is checked. Alternative: strict
  Hill order (would refuse the legacy `CH3OH`-style spellings; WO3 sees them first).
- **DECISION WO1-9. Code params.** Strings (F1 W1-12): `<component>` is the record's `id`; `<entry>` and `<pointer>`
  are RFC 6901 pointers into the normalised record (`/entries/2`, `/molar_mass`, `/formation/0/h`); `amount_basis_invalid`'s
  `<rule>` is one of `molar_mass_present`, `molar_mass_absent`, `molar_mass_kind`, `charge_nonzero`. Alternative:
  entries named by (property, phase).
- **DECISION WO1-10. D6 step 3 on solids.** "The first phase in that order in which an entry is phase-tagged" reads the
  entries as step 4 sorted them (by property, phase, indices), since a set's order cannot be identity (E-F3-4). Formation
  keeps record order (step 4 sorts it stably). Alternative: entries' record order (would make the SHA depend on it).
- **DECISION WO1-11. The three core payload schemas** (ADR 0060 D1 erratum F-5: installed with `records.json`), in
  `extension-descriptor.schema.json` and `PAYLOAD_DEFS`: `record_type` = `{payload_schema: null | {package, path,
  pointer}}` (D1: "an extension type names its payload schema"; `null` for `assay`, whose payload X21 owns);
  `correlation_form` = D4's form payload `{variables, coefficients, result {kind, per_amount}, expression, evaluator}`,
  `evaluator` an object or `null` (preview until ADR-F4; the built-ins carry `null`); `data_source` =
  `{record_types, formats}` (D12's formats; ADR 0061 states no other field). **For the design lane:** the
  `record_type` and `data_source` payloads are this build's reading; ADR 0061 freezes no field list for them.
- **DECISION WO1-12. `assay` preview.** `descriptor.PREVIEW_BUILTINS = {("record_type", "assay")}`, read by
  `stability(..., identifier=)`, so the built-in `assay` 0.1.0 is `preview` (ADR 0061 D1; F1 decision W1-10 left it to
  this WO). In the record schema the `assay` branch admits any members beside the envelope until X21 closes it.
  Alternative: no `assay` descriptor until X21.
- **DECISION WO1-13. Built-in descriptor content.** Status `implemented` (the generator's `RECORDS_STATUS`; status is
  not hashed, close-out raises it); `modules` empty and `factory` null for all seven (ADR 0060 D9: a record type's and a
  form's descriptor is its whole content; the importers are WO3's and WO5's, which will fill the data sources'); the
  form's `expression` is D4's table text with θ (and R) appended. Alternative: status `released` like F1's legacy rows.
- **DECISION WO1-14. Reaction checks are WO5's.** D7's Q7.A3 rules (`reaction_*`, `molar_mass_inconsistent`) take
  reactions and a record map; the work-order table puts `records/reactions.py` in F3-WO5, so `validate` does not carry
  them and their catalogue entries wait for WO5.

**What moved.** `registry/builtin/tables.sha256` for `core` and `legacy` (the descriptor schema's bytes enter
`table_sha256`; `legacy.json` and `core.json` are byte-identical) and E-F1-5's built-in `registry_sha256`
(`tests/fixtures/registry/builtin-sha256.txt`) `f251447d…` → `ee9e6b9d…` (seven new descriptors). F1 tests updated:
SF-4's preview rule and FU.D2's generator guard now run with the kinds removed from `PAYLOAD_DEFS`; a new test covers
core-once-installed and quarantine of a refused payload; the table enumerations gain `records` (49 descriptors in 3
tables).
- **DECISION WO1-15. T08.A32's scan skips v2 records.** `tests/test_t08_w2_inventory.py` `_component_records` finds
  every mapping with `elemental_verification` and an `id` and judges it as a v1 ComponentRecord (v1 schema, `rights`
  block, vetted files). The E-F3-3 fixtures are v2 records, which fail the v1 schema by construction and carry no
  `rights` (D11 puts the assessment in the register). A mapping with `record_format` is now skipped; v1 records are
  judged exactly as before (20 passed). Alternative: keep the fixtures outside the scan's reach, or an A32 rule for v2
  records (WO4's rights register). **For the design lane:** whether A32 gains a v2 clause when the register lands.

**Further moved (re-taken, F1-WO4a precedent `ca6cde69`).** `docs-site/messages/{refusals,notices}.md` regenerated by
`scripts/doc_pages.py`; the two `message_entry` fixtures' catalogue sha256 `000dba96…` → `ae4b7d1c…`. No R4-G3
snapshot, MCP digest or F0 measure moved (F0 PASS, M1 to M9 all equal).

## F3-WO1 fix round 1 (`docs/reviews/F3-WO1-review.md`), 2026-11-18

Each review item, its commit and the test that fails on the WO1 head `bc5bd499` and passes after.

| Item | Commit | Change; test |
| --- | --- | --- |
| M2 | `2a7f9fa2` | Every record-schema pattern ends `$(?!\n)`; CAS, InChIKey, formula readers `fullmatch`. Every patterned leaf of the three fixtures and a source key refuse value + `\n` (7 fail on head). |
| S8 | `433d28c9` | `set_component.match.inchikey` has D3's pattern. |
| M4 | `651834a4` | `legacy.position`, `legacy.file_fields` optional; one SHA for absent, `null`, `{}`, `[]`. Revises WO1-3. |
| M3 | `eaa0db88` | Step 2a removes only members the schema names in `properties` and does not require; map entries and undescribed members stay for step 6 (4 refusals). Revises WO1-4; ADR D2 step 2a amended. A free object's (`legacy.file_fields`) empty members now stay, so such a record's SHA differs from WO1's. |
| M1 | `2abe5ba8` | D6's rule on every non-null anchor; `anchor_derived` removed. Idempotence in the 300-record generator and on three records. ADR D6 amended. |
| S1 | `f1fa29e5` | Provenance sets sorted before the outer sets. |
| S2 | `fab1183f` | YAML refuses a repeated key (merge keys exempt); a leading BOM is stripped before the JSON test. Revises WO1-5. |
| S3 | `d9c77407` | Non-UTF-8 bytes, a recursive alias and over-deep nesting are `record_schema_invalid("")`. |
| S4 | `3a905fb6` | Ruling: D6 step 3 takes the smallest `s:` token by canonical-JSON bytes. Replaces WO1-10. ADR D6 step 3 amended. Includes S5's shuffled names and step-3 permutation. |
| S5 | `83b669a3` | Derived 2a list; no required member with two empty spellings (catches M4 on head); keyword whitelist; transitions permuted; E-F3-3 limits stated. |
| S7 | `bb72078c` | Component fixture: invented values, "Fictitious fixture handbook", `LicenseRef-fixture`; the segment fixture's shared citation too. Fixture SHAs move; none is pinned. |
| WO1-11 | `dcd428dd`, `ef4605ba` | `payload_schema.sha256` required, generated and checked at registration; `null` payload_schema extension is `preview`; `formats` `minItems: 1`. ADR D1 payload table. Re-taken: `tables.sha256` core `ea27cf4c`→`f34f1b98`, legacy `1a3fef16`→`4ac7d6eb` (descriptor schema bytes; `core.json`, `legacy.json` byte-identical), records `1238a6a1`→`93436402`; `registry_sha256` `ee9e6b9d`→`affa126f`. |
| WO1-15 | `31f5d954` | A32 skips only `record_format == "openflowsheet-record-v2"`; a test keeps every such mapping under `tests/fixtures/records/`. **WO4 must add A32's v2 clause**: every tracked v2 record outside that directory passes `identify` and is `synthetic: true`, or carries a `legacy.file_sha256` of a vetted v1 file, or has each source covered by a permitting rights-register row. |
| S6 | `b4b2c608` | `docs/interfaces-frozen.md` §2 F3 paragraph (Proposed). |
| N10 | `93f06eef` | ADR D1: envelope member names reserved against every payload. |

- **DECISION fix1-1 (M2).** The legacy `file` pattern also refuses C0 control characters in a segment: its class
  `[^/\\]` admitted the newline itself, so `$(?!\n)` alone did not refuse `"a.yaml\n"`. Alternative: exclude `\n` only.
  The descriptor schema has the same newline exposure (outside WO1; a code-health item).
- **DECISION fix1-2 (WO1-11).** The payload schema file is `<import root>/<package, dots as directories>/<path>`, read
  by `selfhash.file_sha` (the D3 LF rule), for built-ins and extensions alike; a missing file is the same
  `/payload/payload_schema/sha256` refusal. Alternative: `importlib.resources.files(package)` (needs the package
  importable; the test packages are not).
- **DECISION fix1-3 (WO1-11).** `PREVIEW_BUILTINS` stays for the built-in `assay`; the `null` rule applies to
  extensions only, as the ruling states. Alternative: one rule for both.
- **DECISION fix1-4 (S5).** The hand list `OPTIONAL_MEMBERS` stays beside the derived test: it also asserts that each
  spelling is accepted on the minimal record.

**Review notes for later work orders (not one-line changes).** N1 (WO2): `anchor_defaulted` belongs to a submission;
the store keeps registration findings and says which submission wins. N2 (WO2): hash and write the same bytes in one
place; `RecordOutcome.record` is a mutable dict. N3: an extension `record_type`'s records cannot carry a payload
(root `unevaluatedProperties`); state it or refuse `not_supported`, and step 2a will need the extension's schema.
N4: `volatile: {mirror_url: null}` is refused (harmless to identity). N5 (WO3, X11): ions and `Ca(OH)2` are
`formula_elements_invalid`; rule on a charge suffix. N6 (D10): the data lock must pin the form descriptor version.
N7 (E-F3-12 docs): YAML 1.1 scalars (`1e5` a string, `010` is 8, `1:30` is 90). N8: WO1-9 pointers address the
normalised record. N9: cache the `if` validator in `normalize._applicable` before a bulk importer. N11: batch the
`registry_sha256` re-takes at WO3 and WO5.

## F3-WO2 (store and resolution), 2026-11-18

Files: `src/openflowsheet/records/{store,stack,resolve}.py`, `tests/test_f3_store.py`, four entries in
`messages/catalogue/records.yaml`. Commits `e25332bc` (validate's `CAS`, `INCHIKEY`, `formula_counts` made public,
renamed only), `da9ce359` (store, stack, resolution, tests), `d396f0ba` (catalogue).

- **DECISION WO2-1. A corrupt existing object is refused, not replaced.** D8's protocol (`if target exists:
  verify(target)`) and E-F3-8 refuse it `store_object_corrupt`; the W1 P1 review's N7 "replace a corrupt target
  instead of failing forever" is not applied (the ADR carries no edit for it). N7's other three items are applied:
  a failing `unlink(tmp)` after the target verified is ignored, a rebuild skips `.tmp-*`, the object is written
  before its rows. Alternative: fall through to the write when the target fails verification. Lives in
  `RecordStore._write_object`. **For the design lane:** D8 text for the replace, if wanted: "a target that fails
  verification is replaced by the write; a Windows replace failure on it stays `store_object_corrupt`".
- **DECISION WO2-2. `registrations` columns and which submission wins (F3-WO1 review N1).** D8's columns plus
  `sequence INTEGER PRIMARY KEY` (insertion order) and `findings` (the submission's notices, canonical JSON), with
  `UNIQUE (sha, volatile_sha)`: the first registration of one (record, volatile block) pair is kept and a later one
  adds no row, so a defaulted `ig` registered first keeps its `anchor_defaulted`. An absent volatile block is stored
  as `{}` with its SHA. `Registration.findings` returns the call's own findings. Alternative: one row per call (an
  append log). Lives in `store._TABLES`, `RecordStore.register`.
- **DECISION WO2-3. Schema id and the other tables.** A `meta (key, value)` table holds `schema = f3-records-v1`; a
  database with another id is refused (uncoded `RecordStoreError`, as T07's schema mismatch). `objects`, `keys`
  (primary key (scheme, value, sha)) carry no foreign key, so a rebuild can empty them. `rights` = D11's row fields
  plus `sequence` (D11's "latest"), `assessment` checked against D11's three values; WO4 writes it. Alternative:
  `PRAGMA user_version`.
- **DECISION WO2-4. Key spellings.** `inchikey`, `inchi`, `cas`, `id`: as stored, exact (case-sensitive). `name`:
  NFC, casefold, whitespace collapsed, NFC again (casefold can leave non-NFC text). `formula`: Hill order of WO1's
  formula reader; a formula it cannot read (N5's ions) is its own key, NFC without whitespace. A query value is
  spelled by the same rule. Alternative: upper-case InChIKey queries. Lives in `resolve.lookup_keys`, `_key_value`.
- **DECISION WO2-5. Query form.** `<scheme>:<value>` only when the text before the first `:` is one of the seven
  schemes; otherwise the whole text is a bare query. A bare query tries `inchikey` and `cas` only on a whole-string
  pattern match (CAS digits pattern; the check digit is not tested). Lives in `resolve.query_keys`.
- **DECISION WO2-6. Resolution's scope and its empty result.** `resolve` reads `component` records only
  (`record_type` parameter), filtered before "the first scheme with a match wins"; `search` reads every type unless
  given one. No match is `None`; F3-WO5's operation maps it (`not_found`, or `data_unavailable` for `sha256:`).
  Alternative: a coded refusal here (the ADR names none for no match).
- **DECISION WO2-7. `detail.candidates` form.** Per class `{class, records}`: `class` is the sorted list of
  `cas:<v>` and `inchikey:<v>` keys its records carry (`[]` for a record with neither); `records` =
  `[{sha, source_ids, name}]` by SHA; classes sorted by canonical-JSON bytes. Alternative: a class index. Lives in
  `resolve.candidates`. **For the design lane:** D9 states "`[{class, records: [{sha, source ids, name}]}]`" without
  the class value; this reading is identity-free and order-stable (tested over registration orders).
- **DECISION WO2-8. Errors are an exception.** `RecordStoreError(coded)` carries `store_object_corrupt`,
  `store_path_too_long`, `data_unavailable`, or a refused outcome's first error on `register`. `rebuild` returns
  the corrupt objects' codes instead of raising, and keeps `registrations` and `rights`. A copy into the project store
  (`StoreStack.adopt`, D8's data-lock case) writes no registration row.
- **DECISION WO2-9. The legacy store** is an in-memory `RecordStore` filled once from a loader of normalised
  projections (`stack.LegacyStore`); F3-WO3 supplies the loader and its drift check against the legacy index.

**Moved.** The catalogue's sha256 `ae4b7d1c…` → `3aa34e6d…` in the two `message_entry` fixtures
(`scripts/t07_schema_fixtures.py --write`); `docs-site/messages/refusals.md` regenerated (`scripts/doc_pages.py`). No
registry table, `registry_sha256`, R4-G3 snapshot, MCP digest or F0 measure moved.

**Left for later work orders.** WO3: the legacy loader and drift check, the skipped source-checkout E-F3-9 test
(`methanol` across `s07` and `s10`), N9 (cache the `if` validator before the bulk import). WO5: wiring
`LocalApplication` (`in_memory()` gets `RecordStore.in_memory()`), the `register_record` and `search_records`
operations and their mapping of `RecordStoreError` and of `resolve`'s `None`. Windows behaviour stays simulated until
X07a's legs (risk 9).

## F3-WO3 (legacy import), 2026-11-18

Files: `src/openflowsheet/records/importers/{__init__,legacy}.py`, `records/legacy_profiles.yaml`,
`records/legacy_index.json`, `records/legacy_views.py`, `scripts/records_legacy_index.py`, `tests/test_f3_legacy.py`;
`legacy_record_drift` in `messages/catalogue/records.yaml`. Commits `16bf8248` (importer, profiles, generator),
`2d50d0ea` (WO3-2), `274d8edb` (index, package data), `6e038c7c` (views, WO3-4), `b8680e9f` (catalogue), `8fe44cfc`
(tests; E-F3-9 methanol unskipped). Import: 149 records (147 components, 2 sets), 127 `anchor_defaulted`, 17
`fit_inputs_unhashed(/molar_mass)`, every anchor `ig`, as D12 states.

- **DECISION WO3-1. `sources.<id>.citation` is each component's v1 `rights.source`** (D12's table, literally).
  **For the design lane:** the texts differ per component in m01 (5), l01 (9), s07 (77), s10 (3), so the import gives
  99 distinct `source_sha256` values over 7 sources (the two sets add one each, WO3-5), while D11 seeds "one
  whole-source row per legacy source, carrying the `source_sha256` of the importer's entry". WO4 cannot meet both. The
  review's reason for dropping `rights.notes` (one `source_sha256` per source) applies equally to `rights.source`.
  Proposed D12 text, if the design lane wants one row per source: "`citation`: the file's citation, fixed per
  profile in `legacy_profiles.yaml`; the component's `rights.source` goes to `note` of its molar mass" (or is dropped
  like `rights.notes`). Either change regenerates the index (risk 1's cost). Lives in `legacy._component`.
- **DECISION WO3-2. s07's spin-isomer labels are dropped** (`2d50d0ea`): `OrthoDeuterium`, `OrthoHydrogen`,
  `ParaDeuterium` carry CoolProp's `7782-39-0o`, `1333-74-0o`, `7782-39-0p`, which D3 refuses
  (`identifier_invalid`); D12 copies identifiers, so the import failed. The profile's `dropped_identifiers` names
  them; each must be stated in the file. Alternative: strip the suffix (joins them to normal H2's and D2's class).
  **For the design lane:** D12 text "an identifier D3 refuses is dropped where the profile names it".
- **DECISION WO3-3. Index findings are `{code, params}`** (`Coded.as_document`, in D2's order): D12 writes
  `findings: [code…]` but pins `anchor_defaulted(<id>)` with its param. Alternative: code strings only.
- **DECISION WO3-4. `records.legacy_views` sits above `thermo`** in `.codehealth/config.toml`'s repo layers (its own
  module entry): D12 puts the views in `records` and they construct `thermo`'s dataclasses. `codehealth arch`: 0
  violations. Alternative: move the views to `thermo` (contradicts D12's module name).
- **DECISION WO3-5. The parameter set's `name` is its `data_set`, and its source entry is `{version: file_sha256}`**
  (no citation): D12 names neither; `data_provenance` goes to `legacy.file_fields` as D12 says.
- **DECISION WO3-6. The `legacy-yaml` descriptor stays payload-only** (`modules` empty, `factory` null; WO1-13 left it
  to WO3). Filling it moves `records.json`, `tables.sha256` and `registry_sha256`; batched with WO5's `user-file`
  (review N11). Nothing in `registry/builtin` moved in WO3.
- **DECISION WO3-7. The drift check** compares a file's `file_sha256` first (drift at its first indexed record), then
  each record's (id, SHA) in index order. A file neither packaged nor in a checkout contributes nothing (a wheel: m01
  and s10 only). The first legacy-store access imports the available files: 0.74 s cold for all seven (measured).
- **N9 not applied.** Profiled warm import of all seven files: 1.83 s under cProfile, of which `yaml.safe_load` about
  0.95 s, schema validation 0.53 s, `strip_empty` (the `if` validators) 0.06 s. Caching them saves under 4 %.
- **Note (E-F3-1).** D2 sorts object keys, so `elemental_composition` keeps its members but not the YAML's key order;
  the views equal the loaders under dataclass equality and field by field with mappings by key set, floats by
  `struct.pack("<d")` bytes, also after a store round trip.

**Moved.** Catalogue sha256 `3aa34e6d…` → `89f77348…` in the two `message_entry` fixtures; `docs-site/messages/refusals.md`
regenerated. `pyproject.toml` package data and T08.A32's `SHIPPED_DATA` gain the profiles and the index. No registry
table, `registry_sha256`, R4-G3 snapshot, MCP digest or F0 measure moved.

**Left for later work orders.** WO4: the rights register's seed rows (after the design lane rules on WO3-1), A32's v2
clause (WO1-15). WO5: wiring `LegacyStore(legacy.available_records)` into `LocalApplication`, the `legacy-yaml` and
`user-file` descriptors' implementation sets (WO3-6), the user-file adapter's v1 path reusing D12's mapping.

## F3-WO4 (data lock and rights), 2026-11-18

- **DECISION WO4-0. One citation per legacy file** (the orchestrator's default for WO3-1, brief F3-WO4). Each profile
  in `legacy_profiles.yaml` carries `citation`, the `citation` of every component's `sources` entry: the file's text
  verbatim where all its components cite one (syn001, s05, s10-verification), else their shared text with the varying
  part (the reference EOS of each fluid: m01, l01, s07, s10) replaced by "named in its molar mass note". Each
  component's v1 `rights.source` is appended as the last line of its molar mass's `note` (D12's note rule: distinct
  texts joined by a newline, the provenance text first). The import now gives one `source_sha256` per source for the
  components (7) and one per parameter set (2, `{version: file_sha256}`, WO3-5), 9 in all
  (`test_wo4_0_one_citation_and_one_source_sha_per_legacy_source`). All 149 index SHAs moved (the parameter sets match
  the components by SHA); no other index field moved; no test or fixture outside F3 named an old SHA. Alternative: D12
  literal (`citation` = each component's `rights.source`, 99 `source_sha256`), with D11's seed rows per component
  (`record_sha256` set) instead of whole-source rows. Lives in `legacy._component`, `legacy._note`, `Profile.citation`.
  **Proposed D12 text** (mapping table, row `rights.source`): "component `rights.source` | the last line of the
  `note` of its `molar_mass`; `sources.<source id>.citation` is the file's citation, fixed per profile in
  `legacy_profiles.yaml` (one `source_sha256` per legacy source, D11)", and in the "Set for every component" sentence
  `citation: v1 rights.source` becomes `citation: the profile's citation`.
