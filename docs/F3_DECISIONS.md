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
