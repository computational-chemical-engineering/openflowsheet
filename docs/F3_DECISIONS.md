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

Files: `schemas/data-lock.schema.json` ("DRAFT until ADR 0061 is Accepted"), `records/{lock,rights}.py`,
`records/rights-register.json`, `RecordStore.append_rights`/`rights_rows`, `tests/test_f3_lock_rights.py`,
`tests/fixtures/records/data-lock{.json,-sha256.txt}`, A32's v2 clause in `tests/test_t08_w2_inventory.py`. Commits
`cc11f918` (WO4-0), `ca71f8c5` (rights, seed, A32), `57d88321` (lock, schema), `5b5fe8bb` (catalogue), `4542b66c`
(tests).

- **DECISION WO4-1. The repository register's file** is `{register_format: "openflowsheet-rights-register-v1", rows}`,
  rows in D11's field order, each checked by `rights.check_row` (exactly D11's eight fields, SHAs 64 lower-case hex,
  the three assessments, non-empty `basis` and `decided_by`, `date` `YYYY-MM-DD`); the project table's rows pass the
  same check. Alternative: a bare JSON list. Lives in `rights.register_rows`.
- **DECISION WO4-2. Seed rows and the S10 row.** One whole-source row per distinct `source_sha256` of a file's records,
  in profile order: 9 (WO4-0). The assessment is D11's reading of the file's one `redistribution` text (the importer
  now refuses a file whose components state several; `ImportedFile.redistribution`, not identity); `basis` quotes the
  file and the text, `decided_by` "ADR 0061 D11 seed", `date` 2026-11-18. D11's S10 row is added once per S10
  `source_sha256` (components and the Wilson set: R-880 ships both), `permitted`, "NOTICE Wilson block", `decided_by`
  Frank, 2026-10-29: 11 rows. `--check` requires, per seed, a first whole-source row of that SHA with the seed's id,
  assessment and conditions, and no `legacy.` row naming a SHA the import does not give. Alternative: give the
  parameter sets the file citation as well (7 seed rows; reverses WO3-5, moves the index again).
- **DECISION WO4-3. Precedence keys.** A record-scoped row matches on (`source_sha256`, `record_sha256`), equivalent
  to (source id, record) since a record has one entry per id. `effective` returns the deciding row and its layer
  (for D13's `rights.rows`/`effective`); `embeddable` needs at least one source, all `permitted`. Lives in `rights`.
- **DECISION WO4-4. `build_lock`'s inputs and uncoded refusals.** `components` are (component id, record SHA) pairs in
  revision order; `methods` are D10 rows (`method_entry(substream, Registered)` builds one). Duplicate component ids,
  a (substream, method, version) locked twice, options for a method not in the lock, and a SHA naming a record of the
  other type are `DataLockError` with `coded` `None` (a caller's bug; the ADR names no code); duplicate set SHAs are
  merged (D10 "unique"). Alternative: new catalogued codes (an ADR change).
- **DECISION WO4-5. `parameter_set_component_missing(<set>, <key>)`'s `<set>` is the set's record `id`**, as
  `<component>` is the record id (WO1-9). Alternative: the set's SHA.
- **DECISION WO4-6. `build_lock` copies the named records into the project store (D8, review item 20) after every
  check passes**, so a refused lock copies nothing. Alternative: callers copy (the builder stays read-only).
- **DECISION WO4-7. T08.A32's v2 clause** (WO1-15): a v2 mapping outside `tests/fixtures/records/` must pass
  `identify` and be `synthetic: true`, or carry the `legacy.file_sha256` (LF-normalised) of a `VETTED_RECORD_FILES`
  file, or be `embeddable` against the repository register alone (packaging reads that layer only, D11). The schema
  fixtures stay skipped (some are refused by construction). The placement test is replaced by the clause and a test
  of each branch. **For the design lane:** whether the clause should also judge the fixture directory.
- **Not built (F4):** the per-provider narrowed lock (`data_sha256`, ADR 0063 D2).

**Moved.** The 149 legacy index SHAs (WO4-0). Catalogue sha256 `89f77348…` → `dd487916…` in the two `message_entry`
fixtures; `docs-site/messages/refusals.md` regenerated. `schemas/registry.json` +1 name; the F3 numerical-policy
addendum lists `data-lock.schema.json` (`implementation_sha256` keeps ST's exact class; policy digest `6b449911…`
unmoved). `pyproject.toml` package data and A32's `SHIPPED_DATA` gain the register.

**Left for WO5.** `assess_rights` (D13: `policy` right, `not_found`, `invalid_request`, one audit row) and E-F3-5's
grant clause (skipped here); the `reserved_namespace(legacy)` refusal on every non-importer path (D11); `effective_rights`
in `search_records`/`get_record`; wiring the project register into `LocalApplication`.

## F3 ruling round 1 build changes (`docs/reviews/F3-rulings-1.md`, B1 to B7), 2026-11-18

Brief `docs/briefs/F3-rulings-1-fix.md`. One commit per item:

- **B1** `d3ec37bd`: `legacy._parameter_set` carries its components' `sources` entry (`_File.sources`: `version`, the
  profile's `citation`, `licence_stated` and `url` null), so the import gives one `source_sha256` per legacy source over
  components and sets, 7 in all. Index regenerated (`scripts/records_legacy_index.py --write`); exactly two `sha256`
  values move, no component's and no finding:
  - `s10` `S10-wilson-ig-real-v1`: `3ed3a9d0d475de5261cc1277ec2a46089f6f78bc9519c4928b0310d2835e6588` →
    `6634ea271566e5acc59d87a55dfa2d6dc973fab7e7073190da369b5444fbd114`;
  - `s10-verification` `S10-verification-v1`: `76d2bcb75fd26b775de08cbea0871e1ecfe02bc8035ebe07f0c1a0ed2f0f022b` →
    `c13d5aaab92879e92a0c45a50be134164691fb504e69c23cc61bc22a30133c9e`.
  The register loses the two set seed rows (`86410eaa…`, `e7943cc1…`) and the second R-880 row (`86410eaa…`).
- **B2** `2ebeff0a`: `test_b2_templated_citations_equal_the_files_but_for_each_fluids_eos` pins m01, l01, s07 and s10's
  citations to the files (departures exactly `{"l01": {"O2"}}`); one word changed outside the placeholder fails it (also
  checked by hand on the file). The `legacy_profiles.yaml` comment corrected; no SHA moves.
- **B3** `33915046`: a dropped identifier must be a `cas` or `inchikey` whose stated value D3's reader refuses, else
  `LegacyImportError`. D3's reader `validate._identifier_ok` is now public as `validate.identifier_ok` (its one caller
  updated) so the importer imports no private name. The index is unchanged.
- **B4** `16318358`: D8's repair on write, file and in-memory branch. `_write_object` returns `created`, `kept` or
  `repaired`; `register` returns `created` false and adds `store_object_repaired(<sha>)` to the findings it returns,
  never to `registrations`. `RecordStore.add` keeps `(sha, created)`. New catalogue notice `store_object_repaired`;
  `store_object_corrupt`'s why and action no longer say a file is never rewritten or must be deleted by hand.
  Catalogue sha256 re-taken in the two `message_entry` fixtures: `dd487916…` →
  `787017d4e34450a65a87a74641015dca7d5e8502dce59c76ee718457d06aff5f`; `docs-site/messages/{notices,refusals}.md`
  regenerated (`scripts/doc_pages.py`). New tests: a Windows replace failing over a corrupt object, `adopt` over a corrupt
  project object (both stay `store_object_corrupt`).
- **B5** `abdde572`: the `legacy.s07` condition row appended after R-880 (seed `source_sha256` `e27b8e71…`). The register
  now holds **nine rows**: seven seeds (`legacy.syn001`, `m01`, `l01`, `s05`, `s07`, `s10`, `s10-verification`), the
  R-880 row for `legacy.s10`, the `s07` row. The register test pins it and that it decides every `s07` record.
- **B6** `7b742cda`: A32's v2 scan takes every `record_format: openflowsheet-record-v2` mapping of any `record_type`;
  inside `tests/fixtures/records/` a record's `sources` must be a non-empty object of `fixture.` keys (no `identify`).
- **DECISION R1-B6. A32's vetted-file branch holds for components only** (`da41b295`, isolated). B6's acceptance (a line
  for the imported `s10` set at `benchmarks/x/sets.json` with an empty register) contradicts its "(b) the three branches
  as built": the set carries `benchmarks/s10/records.yaml`'s `legacy.file_sha256`, a vetted file, and passed (measured:
  no line). A vetted file's vetting (`records-vetting.json`, S10 spec §18 A5-1) vets its registered components, not its
  Wilson block, whose basis is the R-880 row; so a parameter set is judged by the register. Alternative: keep the branch
  as built and drop that acceptance line. Reversible by reverting `da41b295`. **For the design lane.**
- **B7**: this entry.

**Correction to WO4-0's entry.** "The varying part (the reference EOS of each fluid)" is wrong for one record: l01's O2
also states "formation enthalpy: zero by definition" where the profile citation states "ATcT 1.112". O2's own text is
whole in its molar mass's note, so nothing is lost (ruling: keep one citation per file). The WO4-0 and WO4-2 counts
("9 in all", nine seed rows) are superseded by B1: 7 `source_sha256` values, 7 seed rows.

## F3-WO5a (reaction consistency, user-file adapter), 2026-11-18

Brief `docs/briefs/F3-WO5a.md`. Files: `src/openflowsheet/records/reactions.py`,
`records/importers/user_file.py`; `records/importers/legacy.py` (D12's parameter rows public),
`records/normalize.py` (`loaded` public); four codes in `messages/catalogue/records.yaml`;
`tests/test_f3_reactions.py`, `tests/test_f3_user_file.py`. Commits `84dcdb4d` and `ebc7f20d`
(reactions), `7e7d4f3d` (catalogue), `733e5db9` (legacy rows public, WO5a-9), `26194673`
(`normalize.loaded`), `94287fee` (adapter), `425fb4e3` and `7b4c1e9c` (E-F3-10), `b3b9b7d8`
(E-F3-12). E-F3-10's ratios, recomputed exactly from the YAML molecular weights: 6.37e-18,
3.61e-17, 7.77e-6, the ADR's 6.4e-18, 3.6e-17, 7.8e-6 to its two digits (4ε = 8.88e-16).

- **DECISION WO5a-1. `<component>` in `reaction_element_unchecked` is the stoichiometry's component
  key**, not the record `id` (WO1-9's reading for one record): two keys may name records with one
  `id` (E-F3-10's mixed water, `l01`'s and `s10`'s `H2O`). Alternative: the record `id`. Lives in
  `reactions.check_reactions`.
- **DECISION WO5a-2. A component with `elements` null leaves the reaction's element balance
  unjudged**: one `reaction_element_unchecked` per such component and no
  `reaction_element_imbalance` for that reaction (D7's "instead"); charge and molar mass are still
  checked. Alternative: balance the elements of the other components, which can refuse a balanced
  reaction whose pseudo-component carries the missing atoms.
- **DECISION WO5a-3. Malformed reaction input is a caller's `ValueError`, not a code**: a
  stoichiometry key with no record, a ν that is not a finite `int`/`float` (a `bool` included),
  a record without `molar_mass` (`kg`, refused `amount_basis_unsupported` before it can be
  registered). WO5b's `validate_record` request schema must screen the first two. Alternative:
  new catalogued codes (an ADR change). Element counts are converted with `Fraction` as ν is.
- **DECISION WO5a-4. The adapter returns one D2 outcome (`RecordOutcome`) per record**, `identify`
  run inside it, so `register_record` passes each to `RecordStore.register`. Without complete
  `defaults` a v1 record goes through steps 1 to 5 only: no `sources`, every Constant and entry
  `provenance_invalid(<entry>)` at its pointer in the normalised record (`normalize.quantities`),
  no SHA, no other check (step 6 would stop at `record_schema_invalid` for the missing provenance).
  Alternative: return built documents and let `register_record` run `identify`.
- **DECISION WO5a-5. A v1 file off its format is `record_schema_invalid(<pointer into the file>)`**,
  one refused outcome: the envelope (exactly D12's file keys `schema_version` 1, `record_schema`
  the v1 schema, `reference_convention`, `components` a list; a `wilson_lambda` file's keys are
  refused, so a parameter set cannot come from a v1 user file), a component against
  `schemas/component-record.schema.json` (first error), a D12-named group incomplete
  (`ideal_gas_cp_b0…b4` all or none; both bounds or none, and only with the coefficients;
  `vapour_pressure_a…d` all or none) or a parameter outside D12's parameter keys (the v1 quantity's
  `bounds`, `nominal`, `display_unit`, `uncertainty_ref`) at `/components/<i>/parameters` (or
  `/molecular_weight`). `record_schema_invalid`'s `why` gains one sentence saying so.
  Alternative: a new code for a v1 file (an ADR change).
- **DECISION WO5a-6. A v1 user component maps by D12's component rows** through `legacy.py`'s
  functions: its `rights.source` is the last line of its molar mass's `note` (`legacy.molar_mass`);
  `rights.redistribution`, `rights.notes` and `reference_convention` are dropped (rights are
  `assess_rights`', WO5b); `synthetic` and `elemental_verification` are copied when stated and
  otherwise left for D7 to refuse (never defaulted); identifiers are copied, none dropped; no
  `legacy` member (D1). Each parameter D12 names maps by its row (`ideal_gas_cp` takes validity
  `{T: [lower, upper]}` with both bounds, `null` without); every other is `user.<name>`.
- **DECISION WO5a-7. `defaults`** must have exactly D12's five members, `origin` a list of strings
  and the others strings; anything else counts as absent. Each value's provenance is `{origin,
  derivation, source: source_id, inputs: [], transformation: null}`, the record's `sources`
  `{source_id: {version: source_version, citation, licence_stated: null, url: null}}`; their values
  are D7's to judge (an empty `origin` is `provenance_invalid`, a `derivation` off the enum
  `record_schema_invalid`, `fitted` gives `fit_inputs_unhashed` per value). `defaults` is not read
  for a v2 file. Alternative: apply `defaults` to v2 values that lack provenance.
- **DECISION WO5a-8. v2 formats**: both take one record or a list (D12's parenthesis read for
  both); `record-v2-json` is parsed as JSON only, `record-v2-yaml` as YAML; a list element that is
  not an object is refused `record_schema_invalid("")` alone. Each record's `volatile` is replaced
  by `{retrieved_at, local_path (if given), adapter_version: "1.0.0"}` (a bare version, as the
  maximal fixture's `"0.3.1"`). Alternative: merge the file's own volatile block.
- **DECISION WO5a-9. Shared code**: `legacy.py`'s D12 parameter rows lose their underscore
  (`molar_mass`, `constant`, `constant_entry`, `correlation_entry`, `Correlation`, `CP`, `PSAT`,
  `formation`, `note`, `number`, the v1 name constants) and take a `Classifier` protocol
  (`provenance(field)`), which `_File` and the adapter's defaults satisfy; `normalize._loaded`
  becomes `normalize.loaded(source, *, syntax=None)`, step 1 unchanged. Index unchanged.
- **For the design lane (no change made).** ADR 0062 (F2) lists `molar_mass_inconsistent` among its
  new codes with Q3's params `(<S>, <species>)` (`docs/roadmap/foundation-rulings.md` line 520);
  ADR 0061 registers it now as `(<reaction>)`. One code cannot carry both argument lists: F2 needs
  another name, or both ADRs one signature.

**Moved.** Catalogue sha256 `787017d4…` → `afa8e4934c34dc31667ce4fb63bda7ecb35ca12abca0d006cc00c8357aa8e100`
in the two `message_entry` fixtures (`scripts/t07_schema_fixtures.py --write`);
`docs-site/messages/{notices,refusals}.md` regenerated (`scripts/doc_pages.py`). The legacy index,
the registry tables, `registry_sha256`, R4-G3 snapshots, the MCP digest and F0 did not move.

**Left for WO5b.** The five operations on four transports and `assess_rights`; `LocalApplication`
wiring; the `legacy-yaml` and `user-file` descriptors' implementation sets (WO3-6; the adapter's
module is now `openflowsheet.records.importers.user_file`); `reserved_namespace(legacy)`, which
must also cover a user file whose `defaults.source_id` or v2 `sources` names a `legacy.` source;
`register_record` passing `retrieved_at` (now) and `local_path`; `validate_record` calling
`reactions.check_reactions` and its request schema screening WO5a-3's inputs and `defaults`' shape.

## F3-WO5b (Records operations), 2026-11-18, part 1 (stopped at the context cap)

Brief `docs/briefs/F3-WO5b.md`. Commits `363f38f8` (wiring: `ServiceCore.records`, a process-wide
`LEGACY_STORE`), `4eb9747d` (protocol `Records`, five rows, `authz`, `records_service.py`,
`record_types.py`, `application-results` `$defs`, codehealth layers, T07 counts 30/28/26),
`8d30f7ae` (five MCP descriptions, REVIEW.json both reviews pending). Smoke-run by hand on
`in_memory()`: search (methanol: `ambiguous_identity`, 2 items), paging 100 + 49, get, register
(created), assess_rights (row sequence 1, effective `refused`/project), two `allowed` audit rows.

- **DECISION WO5b-1. A record refusal is an `ApiError` by catalogue kind** (`input` →
  `invalid_request`, `not_supported` → `unsupported`, `bug` → `internal_error`), pointer `/record`
  or `/file/content` (+ `record_index`), `detail.reason` the code (MSG renders its chain) and
  `detail.refusal` its `{code, params}`. Every record of a submission is judged (forged legacy
  source first, then its first error) before any is stored: a refused file stores nothing.
  Alternative: per-record errors in `results` (D13's result has no error member). For the design
  lane: D13 names no refusal path for `register_record`.
- **DECISION WO5b-2. One legacy store per process** (`service_core.LEGACY_STORE`): the import
  (0.74 s) runs once. Alternative: one per `LocalApplication`.
- **DECISION WO5b-3. `file.local_path`** (optional) is the only source of the volatile
  `local_path`; D13's `file` names `{format, content}`. Alternative: never pass one.
- **DECISION WO5b-4. `search_records` without a key** lists every stored record (both layers, by
  SHA), and `resolution` is computed over the same set; `scheme` requires `key`
  (`dependentRequired`). Cursor: base64url of `{"after": <sha>}`; another text is
  `invalid_request` at `/cursor`. `store` is `project` when the project store holds the object.
- **DECISION WO5b-5. Rights in responses**: `effective` = `{assessment, conditions, layer}`
  (layer null for `unknown`); `get_record`'s `rows` are the rows naming one of its sources (by
  `source_sha256`, record or whole-source), project rows first, each with `layer` and `sequence`
  (repository: 1-based file order). `assess_rights` returns the row with `layer: project` and its
  `sequence`; `date` is the UTC date; `decided_by` the caller's principal.
- **DECISION WO5b-6. `get_record`/`validate_record`/`assess_rights` on a SHA no layer holds** is
  `not_found` with `record_sha256` (+ `reason: data_unavailable` when the committed legacy index
  names it). `validate_record` refuses `invalid_request` for a `components` record that is not a
  `component`, a stoichiometry key outside `components`, and (last resort) any `ValueError` or
  `KeyError` of `check_reactions`; the request schema requires `components` with `reactions`.

**Where it stopped (next engineer starts here).** The surface tests are red (57 failures in the
T07/T08/M02/M04/M07a/F1 surface files, all expected moves): in order,
(a) request corpora gaining the five operations: `tests/test_t07_w5a_operations.py` (~398, 496,
650), `test_t07_w5b_cli.py` (~373), `test_t07_w6a_http.py` (~355), `test_t07_w6b_mcp.py` (244,
325, 462), `test_t07_conformance.py` (349); (b) `test_t07_w5e_application_results.py`: the def
map (73), R4-G3 snapshot hashes (309) as a `SNAPSHOT_F3`, the per-campaign "without its additions"
strips (`f1_schema_support.py` is the F1 model: an `f3_schema_support.py` with
`F3_OPERATIONS`), schema fixtures (`scripts/t07_schema_fixtures.py --write`); (c) MCP served
digest D_10 and surface link c_10 in `scripts/m07a_rc.py`, register **R-1051** (F3 holds
R-1050..R-1059), `test_t08_w2_surface_digest.py` and `test_m07a_surface_chain.py` (without_f3
must recover F1's D_9 exactly); (d) `test_t08_w2_support_envelope.py` A20 (30 operations),
`docs/support-matrix.md`, `scripts/t08_support_matrix.py`, `benchmarks/t08/support_envelope.yaml`,
`docs-site/api/operations.md`, `apps/web/js/routes.js`; (e) `test_f1_operations.py`'s two
failures (G2 scan, FU-A6) not yet diagnosed. Then brief items 3 (CLI `openflowsheet records
search|get|register|validate|rights`, F1's `_registry_operation` form but on `--project`), 4
(descriptors, WO3-6), 5 (catalogue: `not_found` gains `record_sha256`; message fixtures and
`docs-site/messages` re-taken), 6 (ADR 0019 Amendment 8 pointer headed "Accepted 2026-11-18 with
ADR 0061, Frank Peters; proposed 2026-11-05; F3", `interfaces-frozen.md`), 7
(`tests/test_f3_operations.py`), 8 (this entry completed), and the acceptance runs. Nothing
measured against the acceptance list yet.

## F3-WO5b (Records operations), 2026-11-18, part 2

Brief `docs/briefs/F3-WO5b-2.md` (continuation of `docs/briefs/F3-WO5b.md`).

- **DECISION WO5b-7. Conformance's grant lacks `policy`, so `assess_rights` succeeds only on the
  local-owner clients.** The scenario's `forbidden` steps (`audit everyone`, `newer cancel`) need a
  grant without `policy`; `assess_rights` is the first operation that needs `policy` outright. Its
  step is `forbidden` on python-process, HTTP and MCP (compared equal to the reference), and
  `test_every_carried_operation_succeeds_at_least_once` expects, for a grant client, the carried
  operations whose right the grant holds (computed from `OPERATION_RIGHTS`; for every earlier
  operation the set is unchanged). `assess_rights` on all four transports, as a principal holding
  `policy`, is E-F3-11 in `tests/test_f3_operations.py`. Alternative: a second, `policy`-holding
  grant per client (each client is bound to one credential). Reversible by: that test's one
  `if` and the scenario's `_records`.
- **DECISION WO5b-8. The `Records` response shapes live in a new F3 schema,
  `schemas/record-results.schema.json`, reached by bare `$ref`s (R-1032's structure).** The
  `$defs` part 1 put in `application-results.schema.json` declared `record_sha256` and
  `source_sha256`, which put two unclassified `sha256` names in the v2 policy's domain
  (`t08_numerical_policy.py --check`: "(d) unclassified sha256 names: ['record_sha256',
  'source_sha256']"; `test_f1_operations.py::test_fu_a6_…` red). R-1032's "Watch for" names the
  remedy: the eight `$defs` moved verbatim; F3's addendum lists the new schema and classifies the
  two names exact. Measured after the move: v2 bytes `6b449911…` unchanged, D_10 and the five
  `SNAPSHOT_F3` digests unchanged. Alternative: the `$defs` in `record-v2.schema.json` (changes the
  record schema's bytes and its pinned SHA in the registry). Reversible by: one commit.
- **The other F1 failure, E-F1-10 (MSG-G2 scan):** part 1's `KIND_CODES` in `records_service.py`
  ends in `_CODES`, which MSG-G2's scan reads as a table of codes, so `input`, `not_supported` and
  `bug` (catalogue kinds) were reported as codes without entries. Not a planned move: the constant
  is renamed `API_ERROR_OF_KIND`; the scan is unchanged.
- Part 1's `_decode_cursor` raised `TypeError` for a cursor decoding to a JSON scalar (it called
  `set()` on it before the type check); fixed in the surface commit.
