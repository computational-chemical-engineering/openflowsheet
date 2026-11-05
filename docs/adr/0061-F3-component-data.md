# ADR 0061 — F3: component data core — records v2, identity, store, data lock, rights register, importers

**Status:** **Proposed, 2026-11-05.** Design wave W1, pass P1 (ADR 0057, R-928). Takes effect when Accepted after the W1
reviewer pass over ADRs 0060 and 0061; built in 0.5 on `wp/F3`, after ADR 0060's WO1.
**Author:** design lane (`architect`). **Brief:** `docs/roadmap/brief-architect-W1-P1.md`.
**Rulings implemented (not re-ruled):** Q7.R1–R5, Q7.A3; Q9.R1–R7, Q9.A1–A3; Q2.R2, R4, R8 as amended by Amendment 2
(the anchor is a record field); Q8.R7 (an isotherm's parameters are an ordinary `parameter_set`; no new record type).
**Refines:** `target-architecture.md` §2.3.1, §2.3.2, §2.7.1, §3 F3. Departures are marked **[departure]**.
**Amends:**
- ADR 0019 D1, as **ADR 0019 Amendment 8**: a new protocol `Records` with five methods (D13). Pointer paragraph on
  acceptance, in the form of Amendment 4.
- `docs/interfaces-frozen.md` §2: `ComponentRecord` gains its v2 schema `record-v2.schema.json` (the v1 schema stays
  byte-identical); `data-lock.schema.json` added; `application-results` widened additively; new frozen result-type
  names `RecordPage`, `RecordView`, `RecordRegistrationResult`, `RecordValidationReport`, `RightsAssessmentResult`.
- ADR 0050 D1, **for v2 documents only**: a v2 revision binds components to records by SHA through the data lock (D10);
  `record_source` paths remain the v1 mechanism, and D1's table and D10 keep governing v1.

**Does not amend:** `component-record.schema.json` (v1) and its fixtures; the legacy loaders and record files (read,
never edited; S1); ADR 0002 D3 (canonical JSON is used as is); ADR 0007; R-706 and R-926 (D11 implements them).

---

## Context (what exists)

Records are YAML files per benchmark directory, validated by the v1 `ComponentRecord` schema, selected by path
(`record_source`, excluded from `content_hash`, ADR 0002 D4.2). Seven files exist: `syn001/components.yaml` (3),
`m01/components.yaml` (5), `l01/components.yaml` (9), `s05/components.yaml` (1), `s07/components.yaml` (123),
`s10/records.yaml` (3 + Wilson Λ), `s10/verification-records.yaml` (3 synthetic + Λ). Loaders return frozen dataclasses:
`pr_c1.load_records() -> C1Records`, `pr_lib.load_records() -> LibraryRecords`, `wilson_ig.load_records(path) ->
WilsonRecords`, each with the SHA-256 of the bytes read. v1 records mix the source citation and the project's rights
assessment in one `rights` block.

---

## Decisions

### D1. Record envelope and types (`schemas/record-v2.schema.json`, draft 2020-12, closed objects)

One schema with a discriminator on `record_type`. Types are F1 `record_type` descriptors (ADR 0060 D1): `component`
1.0.0 and `parameter_set` 1.0.0 are **core**; `assay` 0.1.0 is **preview** (payload owned by X21). An extension type
names its payload schema and must use this envelope and D2's identity rule (Q9.R1: one rule for all).

| Field (all types) | Type | Rule |
| --- | --- | --- |
| `record_format` | const `openflowsheet-record-v2` | a v1 reader refuses it (ADR 0002 D7.5) |
| `record_type` | registered `record_type` id | |
| `type_version` | the type descriptor's version | |
| `id` | `^[A-Za-z0-9][A-Za-z0-9_.:-]*$` (the v1 id pattern) | the record's suggested component (or set) id |
| `name` | string, 1–200 | |
| `sources` | object, key = source id `^[a-z0-9][a-z0-9._-]*$`, ≥ 1 member | value `{version, citation, licence_stated: string \| null, url: string \| null}`; `version` required |
| `legacy` | absent, or `{profile, file, file_sha256, position: integer \| null, file_fields: object \| null}` | written by the legacy importer only (D12). `file` is a repository-relative path of a packaged source file: a source identifier, not a local path |
| `uncertainty_statement` | string, optional | narrative uncertainty of the whole record |
| `volatile` | optional, closed (D2) | excluded from identity |

### D2. Identity

**Identity = SHA-256 of `canonical_json(identity projection)`**, the projection being the normalised record without its
top-level `volatile` member (Q9.R2). `canonical_json` is ADR 0002 D3's (`openflowsheet.canonical`): sorted keys, ECMA
number spelling, `-0.0` → `0`.

**The volatile set is closed and schema-declared:** `volatile` = `{retrieved_at (RFC 3339 string), request {url, method,
query: [[key, value]…], headers {…}}, response {status, headers {…}}, mirror_url, fetch_duration_s, local_path,
adapter_version, host}`, every member optional, no others. Nothing volatile may appear outside it (closed objects
everywhere). So "what moves the SHA" is a schema fact (Q9.A1).

**Normaliser** (`records.normalize`), run on every path that hashes (importer, `register_record`, `validate_record`),
in this order:
1. Parse (JSON, or YAML through `yaml.safe_load`). A value outside the JSON data model (a YAML date, a non-finite float)
   is `record_schema_invalid(<pointer>)`.
2. Detach `volatile`.
   2a. Remove every optional member (one the schema does not list as `required`) whose value is `null`, `[]` or `{}`,
   recursively; required members keep their values. Absent, `null`, `[]` and `{}` then give one SHA, so a fetcher that
   emits `synonyms: []` in one version and omits it in the next produces the same record. A derived `anchor_phase: null`
   is re-inserted by step 5, so normalisation stays idempotent.
3. Every string value and key → Unicode NFC.
4. Sort the set-valued arrays by the canonical-JSON bytes of each element (for `entries`, of its key (property, phase,
   indices); for `parameter_set.components`, of its `key`; for `transitions`, of (from, to)): `synonyms`;
   `provenance.origin`; `provenance.inputs`; `parameter_set.components`; `entries`; `transitions`. Only canonically
   identical elements are removed. Two distinct elements with one key, or two object keys that collide after NFC, are
   left in place and refused at step 6 (`record_schema_invalid(<pointer>)`), never silently dropped. `formation` is
   sorted by phase class (`ig` 0, `aq` 1, `l` 2, `s:` 3), **stably**, so solid forms keep record order (Q2.R2 uses it).
5. If `anchor_phase` is absent, derive it (D6) and insert it, possibly `null`.
6. Validate (D7). Errors refuse.
7. `record_sha256 = sha256(canonical_json(projection))`.

Formula, CAS and InChIKey strings are stored as given; only lookup keys are normalised (D9).

### D3. `component` payload

| Field | Type | Rule |
| --- | --- | --- |
| `synthetic` | boolean, required | true forbids `identifiers` |
| `synonyms` | array of strings (a set) | |
| `identifiers` | `{cas, inchi, inchikey, formula, smiles}`, each optional | CAS checksum valid; InChIKey `^[A-Z]{14}-[A-Z]{10}-[A-Z]$` |
| `amount_basis` | `mol` \| `segment_mol` \| `kg`, required | Q7.R1 |
| `charge` | integer, required | elementary charges per unit amount; 0 for `kg` |
| `molar_mass` | Constant (below), required iff basis ≠ `kg` | kind `molar_mass` (`mol`) or `segment_molar_mass` (`segment_mol`); absent for `kg` (Q7.R2) |
| `elements` | `{symbol: number > 0}` or null | per unit amount: mol element per mol, per segment-mol, or per kg (Q7.R2); symbols from the 118 elements |
| `elemental_verification` | `VERIFIED` \| `PENDING` \| `FAILED` \| `NOT_APPLICABLE` | `NOT_APPLICABLE` iff `elements` is null (v1's rule) |
| `anchor_phase` | `ig` \| `aq` \| `l` \| `s:<form>` \| null | Q2.R2; identity; set by D6 when not stated |
| `formation` | array of `{phase, h: Constant, s: Constant \| null}`, phases unique | Δf h° and s° at T° = 298.15 K, P° = 1e5 Pa, per unit amount |
| `transitions` | array of `{from, to, h: Constant, s: Constant \| null}` | Δ_aφ h°, Δ_aφ s° at (T°, P°): Q2.R8's bridge datum |
| `entries` | array of Entry (D4); (property, phase) unique | |
| `segment_types` | **preview** (X20): array of `{id, molar_mass, elements}`, `segment_mol` only | copolymer segment types (Q7.R2) |

A phase token is `ig`, `aq`, `l` or `s:<form>` with `<form>` matching `^[A-Za-z0-9][A-Za-z0-9_-]*$`.

**Constant** = `{value, unit, kind, uncertainty, provenance, meaning: string | null, note: string | null}`: `kind` a
registered quantity kind (ADR 0001 D1.3, `schemas/units.json`), `unit` its registered SI unit; dimension is derived from
the kind, not stored.

### D4. Entries, provenance, correlation forms

**Entry** = `{property, phase, form, value, unit, kind, coefficients, validity, uncertainty, provenance, meaning, note}`:
- `property`: a **core property id** (table below) or `<namespace>.<name>` for an extension's or a legacy model's own
  parameter (`syn001.heat_capacity`, `user.<name>`).
- `form`: `constant` (then `value`, `unit`, `kind`) or a registered `correlation_form` id (then `coefficients`, an object
  whose names are exactly the form's).
- `validity`: null or `{variable: [lo, hi]}`, finite, lo < hi; variables are the form's (for a constant: `T`, `P`).
- `uncertainty`: null or `{type: standard | expanded | bound, absolute: number | null, relative: number | null,
  coverage_factor: number | null}`.
- `provenance` (Q9.R4, per entry): `{origin: [⊆ {measured, computed, estimated, synthetic}], derivation: direct | fitted
  | generated, source: <a key of sources>, inputs: [{scheme: record | file, sha256, path: string | null}…],
  transformation: string | null}`. `origin` is non-empty. A fitted or generated entry carries the origin set of its
  inputs; `inputs` are the input hashes Q9.R2 makes identity, tagged by what they hash: `record` is a record SHA (Q9.R5
  fits; `path` null), `file` the SHA-256 of a file's LF-normalised bytes (`path` its repository-relative path). An empty
  `inputs` on a fitted or generated entry is admitted with the finding `fit_inputs_unhashed(<entry>)` (R-924).

**Core property ids (component entries, 1.0.0):**

| Property | Form | Kind / unit | Phase |
| --- | --- | --- | --- |
| `critical_temperature` | constant | `temperature` K | null |
| `critical_pressure` | constant | `pressure` Pa | null |
| `acentric_factor` | constant | `dimensionless` 1 | null |
| `ideal_gas_cp` | `cp_ig_poly4_theta` | result `molar_heat_capacity` J/(mol K) | `ig` |
| `vapour_pressure` | `ln_psat_abcd_theta` | result `pressure` Pa | `l` |

**Core property ids (parameter-set entries, 1.0.0):** `wilson_lambda`: constant, `dimensionless`, two indices i ≠ j,
value > 0; Λ_ii = 1 is implied, never stored. Adding a core id is an additive amendment of this ADR.

**Built-in correlation forms** (F1 `correlation_form` descriptors, 1.0.0; θ = T / (1000 K); R = 8.31446261815324
J/(mol K) exactly):

| Form id | Expression | Coefficients (dimensionless) | Variable |
| --- | --- | --- | --- |
| `cp_ig_poly4_theta` | c_p^ig = R Σ_{k=0}^{4} b_k θ^k (per mol) | `b0`…`b4` | `T` (K) |
| `ln_psat_abcd_theta` | ln(P_sat / Pa) = a + b/θ + c ln θ + d θ² | `a`, `b`, `c`, `d` | `T` (K) |

The form payload is `{variables: [{name, kind, unit}], coefficients: [{name, kind, unit}], result: {kind,
per_amount: boolean}, expression: <the normative text above>, evaluator: <preview until ADR-F4>}`. F3 validates and
stores; F4 evaluates.

### D5. `parameter_set` payload

| Field | Type | Rule |
| --- | --- | --- |
| `components` | array of `{key, match}`; `match` = `{record: sha256}` or `{inchikey}` | keys unique (a set); `key` is the label used in indices |
| `entries` | array of Entry plus `indices: [key…]` | (property, phase, indices) unique |
| `validity` | null or `{variable: [lo, hi]}` | the set's domain |
| `synthetic` | boolean | |
| `data_set` | string or null | |

**Matching** (checked when a data lock is built, D10): a component matches by record SHA when it is bound to that
record, or by InChIKey when its bound record carries that InChIKey; an unmatched key is
`parameter_set_component_missing(<set>, <key>)`. Matching by SHA keeps a fit tied to the exact data it was fitted with;
matching by InChIKey lets a published binary parameter apply to any record of that compound.

### D6. Anchor derivation (Q2.R2 as amended; Q2.R4, R8)

At normalisation, when `anchor_phase` is absent:
1. `charge ≠ 0` → `aq`.
2. Else the first of `ig`, `aq`, `l`, then the `s:` forms in record order, in which `formation` has an entry.
3. Else the first phase in that order in which an entry is phase-tagged (the ruling's "any property correlation";
   the component datum of Q2.R4 then applies in F4).
4. Else, when `amount_basis` is `mol`, `ig`, with the notice `anchor_defaulted(<component>)` (Q2.R9).
5. Else `null`, with the finding `anchor_undetermined(<component>)`; F4 refuses the component on `ELEMENTAL-ref-v1` with
   that code until its record states an anchor.

A stated anchor must be a phase with a formation entry when the record has any (else `anchor_phase_invalid(<component>,
<phase>)`), and a charged component's anchor must be `aq`. No method enters the derivation, so adding or removing a
method never re-anchors. Steps 4 and 5 are Q2.R9 (foundation rulings, Amendment 3); a stated `ig` and a defaulted one give the same record,
and only the defaulted one carries the notice.

### D7. Validation

**Errors (refuse registration):** `record_schema_invalid(<pointer>)`; `record_unit_invalid(<entry>)` (unknown kind, or
unit not the kind's SI unit); `amount_basis_invalid(<component>, <rule>)` (molar mass present for `kg`, absent
otherwise, wrong kind; charge ≠ 0 for `kg`); `amount_basis_unsupported(<basis>)` for `kg` and `segment_mol` until
ADR-F2's quantity kinds are in `units.json` (then a one-line table change admits them); `identifier_invalid(<component>,
<scheme>)` (malformed CAS or InChIKey; any identifier on a synthetic component); `formula_elements_invalid(<component>)`
(a `mol` record whose Hill-parsed formula disagrees with `elements`); `anchor_phase_invalid(<component>, <phase>)`;
`correlation_form_unknown(<entry>, <form>)`; `correlation_coefficients_invalid(<entry>, <form>)`;
`validity_range_invalid(<entry>, <variable>)`; `provenance_invalid(<entry>)` (empty origin; source key not in
`sources`). Entropy entries need a `molar_entropy` kind, which ADR-F2 must add (risk 6); until then they are
`record_unit_invalid`.

**Findings (stored, reported):** `anchor_defaulted(<component>)`; `anchor_undetermined(<component>)`; `fit_inputs_unhashed(<entry>)`;
`molar_mass_inconsistent(<reaction>)` (below; Q7.A3 reports it "in the validation class", so it is a notice, not a
refusal).

**Reaction consistency (Q7.A3), in `validate_record` and called by F2's validator.** Input: reactions `{id,
stoichiometry: {component key: ν}}` and a component-key → record map. Every number is converted exactly to a `Fraction`
(binary64 values are dyadic rationals):
- for each element e: Σ_c ν_c A_ec = 0 exactly, else `reaction_element_imbalance(<reaction>, <e>)`; a component with
  `elements: null` gives `reaction_element_unchecked(<reaction>, <component>)` instead;
- Σ_c ν_c z_c = 0 exactly, else `reaction_charge_imbalance(<reaction>)`;
- |Σ_c ν_c M_c| ≤ 4ε Σ_c |ν_c M_c| with ε = 2⁻⁵² and both sums exact, else the notice
  `molar_mass_inconsistent(<reaction>)`. It does not refuse: a reaction mixing records from two atomic-weight conventions
  (E-F3-10) is reported, not blocked. Element and charge imbalance stay refusals.

Exact evaluation of the ruling's inequality is platform-independent and never stricter than it: the exact sum of the
stored doubles is what a rounded evaluation approximates. These are validation-class findings (Q9), never a
verification verdict.

### D8. Store

**Per project:** `<project>/records/`.
- `objects/<sha[0:2]>/<sha[2:4]>/<sha>.json`: the canonical identity-projection bytes, so `sha256(file bytes) == name`
  (integrity is a file hash, as in git). Write-once.
- `records.sqlite3` (WAL, `busy_timeout` 30 s; schema id `f3-records-v1`, independent of the T07 store): `objects`
  (sha, record_type, id, name, amount_basis) and `keys` (sha, scheme, value), both rebuildable from the object files;
  `registrations` (sha, volatile_sha, volatile JSON, at, principal), the volatile blocks; `rights` (D11). The T07
  `project.sqlite3` is not changed.

**Write protocol (N12, all platforms):**
```
target = objects/aa/bb/<sha>.json
if target exists: verify(target); return created=False
tmp = objects/aa/bb/.tmp-<16 random hex>.json ; write, flush, fsync
try: os.replace(tmp, target)
except PermissionError or FileExistsError:            # Windows: a reader holds target open
    if target exists: verify(target); unlink(tmp); return created=False
    raise
fsync(objects/aa/bb) on POSIX; return created=True
verify(p): sha256(bytes of p) == <sha>, else store_object_corrupt(<sha>)
```
Concurrent writers of one object are safe: both produce the same bytes.

**Path length (Windows):** the store is opened lazily, at its first operation, never as part of project open, so a v1
project with a deep path keeps opening. At that first operation, if the platform is Windows, long paths are not enabled
(`HKLM\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled` ≠ 1, any read error counting as disabled), and
`len(str(absolute resolved project root)) + 92 > 259` (92 = `/records/objects/aa/bb/` + 64 + `.json`), the operation
is refused `store_path_too_long(<root>)`. The check takes the platform and the long-path flag as parameters so Linux CI tests it.

**Store stack.** Reads go through `[project store, legacy store]`; writes go to the project store, and a record already
in the project store is not written again. When a project registers a legacy record, or a data lock built for it (D10)
names one, the record is copied into the project store, so the project keeps it however the package is installed: only
the `m01` and `s10` component files are package data (`pyproject.toml:96,108`), so on a wheel the `l01` and `s07` records
are otherwise `data_unavailable`. `LocalApplication.in_memory()` uses an in-memory project store. The **legacy store**
is read-only and virtual: on first access it imports the profiled files available as package data or in a source
checkout (D12) and checks each SHA against the committed legacy index (mismatch: `legacy_record_drift(<file>, <id>)`, a
bug). A file that is not available contributes no records, and a lookup of one of its SHAs is `data_unavailable(<sha>)`.

### D9. Identity-key resolution

Lookup keys per record: `sha256:<sha>`, `inchikey:`, `inchi:`, `cas:`, `id:`, `name:` (NFC, casefolded, whitespace
collapsed; names and synonyms), `formula:` (Hill order). A query `<scheme>:<value>` searches that scheme. A bare query is
tried in this order and the first scheme with a match wins: `inchikey` (if the pattern matches), `cas` (if the pattern
matches), `id`, `name`, `formula`.

Matches are grouped into **identity classes**: a class is a connected component of the matched records under "shares
an InChIKey or a CAS"; a record with neither is its own class. So `l01`'s H2O (InChIKey and CAS) and the `s05` and `s07`
H2O records (CAS only) are one class. **Resolution** (what F2's edits and the data-lock builder call) returns one record SHA, or
`component_ambiguous(<key>)` with `detail.ambiguity` = `identity` (more than one class; for example formula `C2H6O`)
or `source` (one class, several records: the same compound from two sources), and `detail.candidates` =
`[{class, records: [{sha, source ids, name}]}]` sorted. No origin or source is ranked (Q9's rejected alternative): the
caller chooses by SHA. `search_records` lists the same matches without refusing.

### D10. Data lock (`schemas/data-lock.schema.json`)

```
{ "lock_format": "openflowsheet-data-lock-v1",
  "components":     [{"id": <component id>, "record": <sha256>}…],                 # revision order, ids unique
  "parameter_sets": [<sha256>…],                                                  # ascending, unique
  "methods":        [{"substream", "method", "version", "implementation_sha256"}…],  # sorted by (substream, method, version key)
  "method_options": {<method id>: {…}} }                                          # keys ⊆ methods' ids
data_lock_sha256 = document_sha256(lock)
```

**Place in identity.** The lock is *derived*, never stored in the revision: from the v2 revision (record SHAs, method
ids and versions; F2's schema) and the F1 registry (`implementation_sha256` = `sha256(canonical_json([descriptor_sha256,
self_sha256]))` of the method descriptor, ADR 0060 D3). Record SHAs enter the revision's `content_hash` through F2; `data_lock_sha256` is every composed
provider's `data_sha256` (F4), and so enters the exact cache keys and `describe()`; F8 records the lock document and its
SHA in the run manifest and the bundle. The builder `records.lock.build_lock(components, parameter_sets, methods,
method_options, stack)` normalises the order, checks each SHA resolves (else `data_unavailable(<sha>)`) and checks
parameter-set matching (D5). Rights never enter it (Q9.A2).

### D11. Rights register (Q9.R3, R-706, R-926)

Rows `{source_id, source_sha256, record_sha256: sha | null (the whole source), assessment: permitted | unknown |
refused, conditions: string | null, basis: string, decided_by: string, date}`. `source_sha256` =
`document_sha256({<source id>: <sources entry>})`, the SHA of the canonical one-member object a record carries for that
source. **A whole-source row (`record_sha256: null`) is keyed by `source_sha256`, not by `source_id`**: a source id is
chosen by each record, so a key by id would let any record claim a source's assessment (a user file declaring
`source_id: legacy.m01` would inherit `permitted`, and F8 would embed it). The source-id prefix `legacy.` is reserved for
the legacy importer (D12); a record from any other path naming a `legacy.` source is refused
`reserved_namespace(legacy)` (ADR 0060's code). Two layers:
- **Repository register** `src/openflowsheet/records/rights-register.json` (package data, hand-maintained under the lane
  rules), seeded with one whole-source row per legacy source, carrying the `source_sha256` of the importer's entry
  (`scripts/records_legacy_index.py --check` fails if a seed row's SHA differs). The assessment is read from the v1
  `redistribution` text: beginning `permitted` or `synthetic` → `permitted` (`conditions` = the text after `permitted
  with conditions:`); `unresolved` or `unknown` → `unknown`; `refused` or `not permitted` → `refused`; anything else →
  `unknown`. A later register decision on a source is added as its own row citing it: for S10, the row `legacy.s10`,
  `permitted`, conditions "NOTICE Wilson block", basis R-880 (the seed row reads `unknown` from S10's `unresolved` text).
- **Project register**: table `rights` in `records.sqlite3`, append-only with an insertion sequence, written by
  `assess_rights` (right `policy`, audited).

**"Latest"** is the highest insertion sequence (the project table's sequence; the repository file's row order), never
`date`. **Effective assessment** of (source, record): latest project row for (source, record) → latest project whole-source
row for the record's `source_sha256` → latest repository row for (source, record) → latest repository whole-source row for
the record's `source_sha256` → `unknown`. The bundle writer (F8)
embeds a record only when every source of the record is `permitted`, else references it by SHA (Q9.R7). Packaging reads
the repository layer only, and still needs Frank's decision (R-706). No layer enters any hash.

### D12. Importers

**Legacy importer** (`records.importers.legacy`, the `data_source` `legacy-yaml` 1.0.0): one profile per file.

| Profile | File | Source id | Records |
| --- | --- | --- | --- |
| `syn001` | `benchmarks/syn001/components.yaml` | `legacy.syn001` | 3 components |
| `m01` | `benchmarks/m01/components.yaml` | `legacy.m01` | 5 |
| `l01` | `benchmarks/l01/components.yaml` | `legacy.l01` | 9 |
| `s05` | `benchmarks/s05/components.yaml` | `legacy.s05` | 1 |
| `s07` | `benchmarks/s07/components.yaml` | `legacy.s07` | 123 |
| `s10` | `benchmarks/s10/records.yaml` | `legacy.s10` | 3 + 1 parameter set |
| `s10-verification` | `benchmarks/s10/verification-records.yaml` | `legacy.s10-verification` | 3 + 1 parameter set |

147 component records and 2 parameter sets, 149 in all.

**Mapping: a closed table.** Every v1 key in the seven files is mapped or explicitly dropped; a key not in this table,
in any file, fails index generation. Set for every component: `amount_basis: mol`; `charge: 0`; `legacy = {profile,
file, file_sha256 (SHA-256 of the LF-normalised bytes), position (index in components), file_fields: null}`; `sources =
{<source id>: {version: file_sha256, citation: v1 rights.source, licence_stated: null, url: null}}`.

| v1 key | v2 target |
| --- | --- |
| file `schema_version`, `record_schema` | dropped (the v1 envelope; `record_schema` selects the files `--check` requires profiled) |
| file `reference_convention` | the index's `reference_convention`; for `s10`, `s10-verification` also `legacy.file_fields` of the parameter set |
| file `data_set`, `synthetic`, `uncertainty`, `domain`, `data_provenance`, `wilson_lambda` (`s10`, `s10-verification`) | the parameter set (below) |
| component `id`, `name`, `synthetic`, `elemental_verification` | copied |
| component `identifiers` (`cas`, `inchi`, `inchikey`, `formula`) | copied; any other identifier key fails index generation |
| component `elemental_composition` | `elements` |
| component `molecular_weight` | `molar_mass` (a Constant, by the parameter rule) |
| component `parameters` | entries and `formation`, by profile (below); a parameter name a profile does not list fails index generation |
| component `rights.source` | `sources.<source id>.citation` |
| component `rights.redistribution` | the rights register's seed row (D11); not identity |
| component `rights.notes` | dropped: rights commentary, or (`s07`) the fluid's EOS references, which the source file keeps and `legacy.file` with `file_sha256` identifies; copying it into `sources` would give each record its own `source_sha256` (D11) |
| parameter `value`, `unit`, `kind` | `value`, `unit`, `kind` (coefficients of a correlation entry: the coefficient value) |
| parameter `meaning` | `meaning` of a Constant or entry built from one parameter; `null` for an entry merged from several |
| parameter `provenance` | `note`: the distinct v1 provenance texts of the parameters an entry or Constant is built from, joined by a newline in parameter order (one text for a single parameter) |
| parameter `dimension` | dropped (derived from `kind`, D3) |
| parameter `role` | dropped (`fixed` in every file; any other value fails index generation) |
| `wilson_lambda[]` `i`, `j`, `value`, `provenance` | entry `indices: [i, j]`, `value`, `note`; `meaning` null |

For every legacy entry and Constant, `uncertainty` is `null` and `provenance.transformation` is `null`; `provenance` is
the classification below. The v1 `redistribution` text is an assessment and goes to the rights register, not into
identity. Parameters:
- `m01`, `l01`: `critical_temperature`, `critical_pressure`, `acentric_factor` → constant entries; `ideal_gas_cp_b0…b4`
  with `ideal_gas_cp_lower_temperature`, `ideal_gas_cp_upper_temperature` → one `ideal_gas_cp` entry (validity `{T:
  [lower, upper]}`); `standard_formation_enthalpy` → `formation: [{phase: ig, h, s: null}]`.
- `s10`, `s10-verification`: `ideal_gas_cp_b0…b4` → `ideal_gas_cp` (validity null); `vapour_pressure_a…d` →
  `vapour_pressure`; `standard_formation_enthalpy` → `formation` `ig`. The file's `wilson_lambda` → one `parameter_set`
  (id = `data_set`; `components` matched by the component records' SHAs; entries `wilson_lambda` with indices [i, j];
  `validity` from `domain` {T, P}; `synthetic` and `data_set` from the file; `uncertainty_statement` from `uncertainty`;
  `legacy.file_fields = {reference_convention, data_provenance}`).
- `syn001`: each parameter `p` → constant entry `syn001.p`, phase null.
- `s05`, `s07`: no parameters.

Anchors follow D6: `ig` from formation data (step 2) for `m01`, `l01`, `s10`, `s10-verification`; `ig` by default (step 4)
for the 127 records of `syn001`, `s05`, `s07`, each with `anchor_defaulted(<id>)` in its index `findings`. No legacy
record has a null anchor.

**Provenance classification** (identity-bearing; **confirmed with four changes by the W1 P1 review, ruling 1**).
`derivation` describes the step from the cited source to the stored value; a derivation inside the source belongs in
`note`. A value read from, or evaluated with, a reference EOS has origin {measured}. Stored in
`records/legacy_profiles.yaml` with the fit-input SHAs as committed constants:

| Profile, field | origin | derivation | inputs |
| --- | --- | --- | --- |
| `syn001`, `s10-verification`: every field | {synthetic} | direct | — |
| `m01`, `l01`, `s10`: molar mass (formula, atomic weights) | {measured} | generated | — (17 `fit_inputs_unhashed`, pinned in the index) |
| `s05`, `s07`: molar mass (as published) | {measured} | direct | — |
| `m01`, `l01`: Tc, Pc, acentric factor (reference EOS, via chemicals HEOS) | {measured} | direct | — |
| `m01`, `l01`, `s10`: `ideal_gas_cp` (NASA TM-4513) | {computed} | direct | — |
| `m01`, `l01`: Δf h° (ATcT; includes the 7 element zeros "by definition") | {computed, measured} | direct | — |
| `s10`: Δf h° (H(298.15 K) of the NASA-7 polynomial) | {computed, measured} | generated | SHA of `benchmarks/s10/nasa7-low.json` |
| `s10`: `vapour_pressure` (fit to CoolProp 8.0.0 reference-EOS P_sat) | {measured} | fitted | SHA of `benchmarks/s10/saturation-points.json` |
| `s10`: `wilson_lambda` (fit to Kurihara 1993) | {measured} | fitted | SHA of `benchmarks/s10/vle/kurihara1993_binaries.csv` |

Every `inputs` element uses D4's tagged form `{scheme: file, sha256, path}` (the SHA over LF-normalised bytes, `path`
repository-relative). An input file not in the repository leaves `inputs` empty with `fit_inputs_unhashed`.

**Legacy index** `src/openflowsheet/records/legacy_index.json` (package data): `{index_format:
"openflowsheet-legacy-record-index-v1", files: [{path, profile, file_sha256, reference_convention, records:
[{record_type, id, position, sha256, findings: [code…]}]}]}`, files sorted by path; `findings` pins each record's
findings (the 17 `fit_inputs_unhashed` among them). `scripts/records_legacy_index.py --write | --check`
regenerates it; `--check` also fails if a tracked YAML declaring `record_schema: schemas/component-record.schema.json` has
no profile. One summary line.

**Loader views** (`records.legacy_views`, the R18 adapter): `c1_records(records) -> pr_c1.C1Records`,
`library_records(records) -> pr_lib.LibraryRecords`, `wilson_records(components, parameter_set) ->
wilson_ig.WilsonRecords` (Λ_ii = 1.0, the matrix in component position order, domains from the set's validity,
`reference_convention`, `data_provenance` from `file_fields`, `sha256` = `file_sha256`), and `legacy_path_for(records) ->
str`, which returns the packaged path only if the records are exactly one file's indexed records. They construct the
frozen dataclasses; no legacy module changes.

**User-file adapter** (`data_source` `user-file` 1.0.0), reached through `register_record`: formats
`record-v2-json`, `record-v2-yaml` (one record or a list), `component-record-v1-yaml`. A v1 file goes through the legacy
mapping where a parameter name is in it, else to `user.<name>` constant entries; its provenance comes from the
request's `defaults {origin, derivation, source_id, source_version, citation}`, which are required for a v1 file (else
`provenance_invalid` per entry); `volatile = {retrieved_at: now, local_path (if the client sends one), adapter_version}`.

### D13. Operations (ADR 0019 Amendment 8: protocol `Records`; rule C1, four transports)

| Operation | Right | HTTP | Request | Response |
| --- | --- | --- | --- | --- |
| `search_records` | `read` | `POST /v1/records/search` | `{key?, scheme?, record_type?, cursor?, limit? (1–200, default 50)}` | `RecordPage {items: [{record_sha256, record_type, id, name, identifiers, amount_basis, source_ids, store, effective_rights}], resolution: {status: unique \| ambiguous_identity \| ambiguous_source \| none, classes}, next_cursor}` |
| `get_record` | `read` | `GET /v1/records/{record_sha256}` | `{record_sha256}` | `RecordView {record_sha256, record, registrations, store, rights: {effective, rows}}` |
| `register_record` | `draft` | `POST /v1/records` | `{record}` or `{file: {format, content}, defaults?}` | `RecordRegistrationResult {results: [{record_sha256, created, findings}]}` |
| `validate_record` | `read` | `POST /v1/records/validate` | `{record?, records?: [sha \| record], components?: {key: sha}, reactions?}` | `RecordValidationReport {errors, findings, record_sha256 \| null}` |
| `assess_rights` | `policy` | `POST /v1/records/rights` | `{source_id, record_sha256, scope: record \| source, assessment, conditions?, basis}` | `RightsAssessmentResult {row, effective}` |

`register_record` is idempotent by content (no idempotency key); a repeated registration adds a `registrations` row only
for a new volatile block. `register_record` and `assess_rights` write T07 audit rows. An unknown SHA is `not_found`.
MCP tools carry the operation names; CLI `openflowsheet records search|get|register|validate|rights`.

`assess_rights` is a **[departure]** from the note's four operations, **accepted by the W1 P1 review (ruling 3)**:
rights must be settable on every transport (C1 forbids a private path); folding it into `register_record` would mix
assessment with identity (Q9.R3) and hand the `draft` right, which agents hold by default, the power to vet data; and the
right `policy` keeps agents, whose default grant is draft/execute/read, from vetting data. Request validation:
- an unknown `record_sha256` is `not_found`;
- a `source_id` that is not among that record's `sources` is `invalid_request`;
- `scope: record` writes a row for (source, record); `scope: source` writes a whole-source row keyed by the
  `source_sha256` of that record's entry for `source_id` (D11);
- each call writes one audit row;
- "latest" is the highest insertion sequence (D11).

### D14. Core at the end of W1, and `preview`

**Core:** D1's envelope; D2 (identity, volatile set, normaliser); D3 except `segment_types`; D4 (entry, provenance,
core property ids, the two forms except their evaluator); D5; D6; D7's rules; D8; D9; D10; D11; D12's mapping and
index format; D13. **Preview:** `assay` (X21), `segment_types` (X20), the correlation evaluator (ADR-F4). Enabling `kg`
and `segment_mol` waits only for ADR-F2's kinds; the rules are core now.

---

## Alternatives rejected

- **Store objects with their volatile part** (bytes ≠ identity). Integrity could no longer be a file hash, and two
  registrations of one record would race to fill the object. Volatile blocks live in `registrations`.
- **Commit the 149 imported objects to the repository.** It duplicates the YAML; the importer is deterministic, so a
  committed index of SHAs plus regeneration catches drift at less cost.
- **Records referenced by path, or a provider per record file.** Rejected by the note (ADR 0002 D4.4; X10, FB-07).
- **Entries as an object keyed by property.** One property in two phases needs two keys; an array keyed by (property,
  phase) does not.
- **Formation as an object keyed by phase.** Canonical key order would lose the solid forms' record order that Q2.R2's
  anchor rule reads.
- **Parameter sets keyed by component ids.** An id is revision-local; a set would silently apply to another compound.
- **Normalising formula strings into stored records.** It rewrites what a source said; lookup keys are normalised
  instead.
- **Rights or evidence in identity; ranking sources; regenerating fitted records at replay.** Rejected by Q9.
- **Rights in `project.sqlite3`.** Would change the T07 store schema (`t07-store-v1` refuses others); `records.sqlite3`
  is self-contained.

---

## Migration proof

1. **No byte edit** to any legacy module or record file; F0 passes on every work order; `component-record.schema.json`
   and its fixtures are byte-identical (M8).
2. **Loader equality, bitwise** (E-F3-1, E-F3-2).
3. **Deterministic import**: the committed legacy index reproduces on every leg (E-F3-6).
4. **v1 unchanged**: v1 revisions keep `record_source`; legacy runs keep the legacy providers and their `data_sha256`
   (the YAML SHA). Nothing in v1 reads the store.

---

## Exit tests

- **E-F3-1 Loader equality.** `c1_records(import(m01))`, `library_records(import(l01))`, `wilson_records(import(s10))`
  and `wilson_records(import(s10-verification))` equal `pr_c1.load_records()`, `pr_lib.load_records()` and
  `wilson_ig.load_records(path)` field by field, floats compared by `struct.pack("<d")` bytes, including `sha256`,
  domains and Λ.
- **E-F3-2 Molar masses and order.** All 147 imported `molar_mass` values equal the YAML `molecular_weight` values and
  `selectable_bases()`'s `molecular_weights` bitwise; positions equal file order.
- **E-F3-3 Volatile closure (Q9.A1) [gen].** Over every leaf path of `record-v2.schema.json` on a maximal fixture
  record: a change to any `/volatile/…` leaf leaves the SHA; a change to any other leaf (one ulp by `math.nextafter`, a
  character, an enum value, an origin, a validity bound, a source version, `licence_stated`) changes it. Every
  non-volatile leaf is exercised.
- **E-F3-4 Canonicalisation (Q9.A3).** Field-order permutations, `-0.0` against `+0.0`, permutations of every
  set-valued array, and NFD against NFC strings give one SHA; absent, `null`, `[]` and `{}` optional members give one
  SHA; permuting two solid formation forms gives a different SHA and anchor.
- **E-F3-5 Rights (Q9.A2).** Assessments in both layers leave every record SHA and `data_lock_sha256` unchanged; the
  four precedence rows of D11 each decide one fixture; `assess_rights` by a principal with the default agent grant is
  `forbidden`.
- **E-F3-6 Legacy index.** Import reproduces the committed index (149 SHAs) and identical object bytes on each CI leg;
  changing one value by one ulp in a temporary copy of one file changes exactly that file's record SHAs (its
  `file_sha256` is in each); an unprofiled v1 file makes `--check` fail.
- **E-F3-7 Data lock.** Permuting `parameter_sets` or `methods` leaves the SHA; permuting `components` changes it; a
  committed fixture lock's SHA equals `tests/fixtures/records/data-lock-sha256.txt` on every leg; an absent record gives
  `data_unavailable`; an unmatched set key gives `parameter_set_component_missing`.
- **E-F3-8 Store.** Registering a record twice gives one object (`created` false the second time); object bytes hash to
  the name; a flipped byte gives `store_object_corrupt`; two processes registering 200 overlapping records concurrently
  raise nothing and leave only valid objects; a simulated Windows `PermissionError` on replace with a valid target is
  success, with a corrupt target an error; `store_path_too_long` at root length 168 and not at 167 (simulated Windows,
  long paths off).
- **E-F3-9 Resolution.** Fixtures: two sources of one InChIKey → `component_ambiguous`, ambiguity `source`; formula
  `C2H6O` for ethanol and dimethyl ether → ambiguity `identity`; a unique InChIKey resolves; in a source checkout,
  `methanol` is `component_ambiguous`, ambiguity `identity`, two classes (`s07`'s `Methanol`, CAS 67-56-1; `s10`'s
  `CH3OH`, name `methanol`, no identifiers, R-706), `cas:67-56-1` resolves to the `s07` record and `id:CH3OH` to the
  `s10` record; `sha256:` resolves exactly.
- **E-F3-10 Reaction consistency (Q7.A3) [gen].** N2 + 3 H2 → 2 NH3 on the `m01` records passes all three checks
  (measured |Σν M| / Σ|ν M| = 6.4e-18 ≤ 4ε); 2 H2 + O2 → 2 H2O on the `l01` records passes (3.6e-17); the same reaction
  with `l01`'s H2 and O2 (IUPAC standard weights) and `s10`'s H2O (conventional weights) is not refused and carries the notice
  `molar_mass_inconsistent` (7.8e-6); 10³ generated balanced reactions within the `m01`, the `l01` or the `s10` records (one atomic-weight table
  each) pass, and none over `s07` is asserted, since CoolProp's molar masses come from several EOS papers; scaling one M by (1 + 1e-9) gives
  the notice `molar_mass_inconsistent`; one element count off gives `reaction_element_imbalance`.
- **E-F3-11 Operations.** Each of the five returns identical canonical documents on python, CLI, HTTP and MCP; every new
  code has a catalogue entry; MCP digest re-taken; R4-G3 snapshots of existing operations unchanged.
- **E-F3-12 User file.** A v2 file round-trips to the same SHA; a copy of `m01`'s YAML with `defaults` gives records
  whose entries equal the legacy import's except provenance and `sources`; without `defaults` every entry is
  `provenance_invalid`.
- **E-F3-13 Anchor [gen].** Synthetic records: charged → `aq`; formation in `l` only → `l`; in `ig` and `l` → `ig`; two
  solid forms → the first in record order; a stated anchor without formation there while formation exists elsewhere →
  `anchor_phase_invalid`; nothing phase-tagged: `mol` → `ig` and
  `anchor_defaulted`, with the SHA of the same record stating `ig`; `kg` → D6 gives `null` and `anchor_undetermined`,
  and registration is refused `amount_basis_unsupported(kg)` until ADR-F2 (Q2.A10). Legacy anchors as D12 states.

---

## New catalogue codes

| Code | Family | Kind |
| --- | --- | --- |
| `component_ambiguous(<key>)`, `record_schema_invalid(<pointer>)`, `record_unit_invalid(<entry>)`, `amount_basis_invalid(<component>, <rule>)`, `identifier_invalid(<component>, <scheme>)`, `formula_elements_invalid(<component>)`, `anchor_phase_invalid(<component>, <phase>)`, `correlation_form_unknown(<entry>, <form>)`, `correlation_coefficients_invalid(<entry>, <form>)`, `validity_range_invalid(<entry>, <variable>)`, `provenance_invalid(<entry>)`, `parameter_set_component_missing(<set>, <key>)`, `reaction_element_imbalance(<reaction>, <element>)`, `reaction_charge_imbalance(<reaction>)`, `data_unavailable(<sha>)` | refusal | `input` |
| `molar_mass_inconsistent(<reaction>)` | notice | `notice` (explicit override of MSG's `*_inconsistent` → bug rule; `review: false`) |
| `amount_basis_unsupported(<basis>)`, `store_path_too_long(<root>)` | refusal | `not_supported` |
| `anchor_defaulted(<component>)`, `anchor_undetermined(<component>)`, `fit_inputs_unhashed(<entry>)`, `reaction_element_unchecked(<reaction>, <component>)` | notice | `notice` |
| `store_object_corrupt(<sha>)`, `legacy_record_drift(<file>, <id>)` | refusal | `bug` |

`data_unavailable` is Q9.R7's code; F8 reuses this entry.

---

## Work orders (both ADRs, in order; at most two engineers at a time)

| # | WO | Content and files | Acceptance | Identity | Lane |
| --- | --- | --- | --- | --- | --- |
| 1 | F1-WO1 | ADR 0060 | ADR 0060 | no | Opus |
| 2a | F1-WO2 | ADR 0060 | ADR 0060 | no | Opus |
| 2b | **F3-WO1** Record model | `schemas/record-v2.schema.json`; `src/openflowsheet/records/{__init__,model,normalize,identity,validate}.py`; `registry/builtin/records.json` (record types, the two forms, the two data sources) | E-F3-3, -4, -13 (synthetic part) | no | Opus |
| 3a | **F3-WO2** Store and resolution | `records/{store,stack,resolve}.py`; `records.sqlite3` schema; path-length check | E-F3-8, -9 (with synthetic records) | no | Opus |
| 3b | F1-WO3 | ADR 0060 (needs MSG on `main`) | ADR 0060 | no | Opus |
| 4a | **F3-WO3** Legacy import | `records/importers/legacy.py`; `records/legacy_profiles.yaml`; `records/legacy_index.json`; `records/legacy_views.py`; `scripts/records_legacy_index.py` | E-F3-1, -2, -6, -13 (legacy part); `--check` clean | no | Opus |
| 4b | **F3-WO4** Lock and rights | `schemas/data-lock.schema.json`; `records/{lock,rights}.py`; `records/rights-register.json` | E-F3-5, -7 | no | Sonnet |
| 5 | F1-WO4a, F1-WO4b | ADR 0060 | ADR 0060 | no | Sonnet; Opus |
| 6 | **F3-WO5** Operations, user file, Q7.A3 | `records/importers/user_file.py`; `records/reactions.py`; `application/contract.py` (`Records`), `operations.py`, `authz.py`, `local.py`, CLI `records`; `application-results` `$defs`; catalogue YAML; ADR 0019 Amendment 8 pointer; `interfaces-frozen.md` | E-F3-10, -11, -12 | no | Sonnet (ops, user file); Opus reviews `reactions.py` |
| 7 | Close-out | ADR 0060 F1-WO5; F3 evidence manifest; committed fixture SHAs; full gate; CI on both legs; then the W1 reviewer pass | every E-F1 and E-F3 | no | Sonnet |

**What each unblocks.** F3-WO1: F2 can reference records by SHA in `ProcessRevision` v2; X11 rest can write fetcher
output against the schema. F3-WO2: X11 rest fetchers can store records. F3-WO3: F4's delegating compositions can be
built from records (R18 closed; `legacy_path_for` covers path-only constructors). F3-WO4: F4's `data_sha256`, F8's
bundle and rights handling. F3-WO5: X11 rest's `fetch` and `fit` follow the same operation pattern; agents can search
and register data (C2, C8).

**Optional, after both merge (default: do it in the close-out):** add two measures to F0's registered corpus, the
built-in `registry_sha256` and the legacy index's digest, so a later change to either is caught by F0 as well.

---

## Risks and open questions (each with a default; work proceeds on the default)

1. **Legacy provenance classification is identity-bearing** (D12's table). *Resolved:* the W1 P1 review confirmed it
   with four changes (ruling 1), applied in D12; the specifier decides on any later dispute. A correction before any released v2
   document pins these SHAs costs one index regeneration; after, it makes new records.
2. **Anchor for a record with no formation data and nothing phase-tagged** (`syn001`, `s05`, `s07`): *Resolved* by the
   specifier (foundation rulings Amendment 3, Q2.R9, 2026-11-05): `ig` with `anchor_defaulted` for a `mol` record, `null`
   with `anchor_undetermined` otherwise; an `ig` anchor is the method's ideal-gas state, and its evaluation keeps the
   method's guard and domain.
3. **Water for the v2 IAPWS-95 composition.** The `s05` record has no formation data, so F4 must bind a water record
   that has (the `s10` one, as Q2.A9 (b) does, or a merged record). *Needs:* F4's design. *Default:* F4's choice; F3
   imports faithfully.
4. **`kg` and `segment_mol` records** wait for ADR-F2's kinds; enthalpy per segment-mol has no ruled kind. *Needs:*
   ADR-F2 (fact) and the specifier. *Default:* refused `amount_basis_unsupported` until then; ADR-F2 adds
   `segment_molar_enthalpy` alongside its other kinds.
5. **NFC.** If a legacy string is not NFC, E-F3-1 fails. *Needs:* fact (the test). *Default:* NFC; if a legacy string
   changes, record the finding and exempt `legacy`-profile strings from step 3, keeping NFC for every other path.
6. **`molar_entropy` is not a registered kind,** so s° entries cannot validate. *Needs:* ADR-F2 to add it (fact: no
   legacy record has s°). *Default:* refused until then; nothing in 0.5's import needs it, but F4's Q2.A9 fixtures do.
7. **Rights precedence: a project row overrides the repository row.** *Needs:* Frank's preference (a user holding a
   licence). *Default:* as D11 for bundles; packaging uses the repository layer only.
8. **`data_sha256` = the whole lock** changes every composed provider's cache identity when an unrelated method joins
   the flowsheet. *Needs:* fact (cache hit rates, F4). *Default:* the note's rule; F4 may narrow it to a per-substream
   sub-lock before the W1 freeze.
9. **Windows store behaviour** is simulated until X07a's legs exist. *Default:* recorded `pending`.
10. **One file's comment edit moves all its records' SHAs** (`file_sha256` is identity, the raw-payload hash of Q9.R2).
    *Default:* accepted; the files are byte-frozen.

---

## Edits `target-architecture.md` needs (the orchestrator applies them)

1. §3 F3 scope: "operations `search`, `get`, `register` and `validate`" → "`search_records`, `get_record`,
   `register_record`, `validate_record` and `assess_rights`" (the names avoid `Application.validate`; the fifth sets
   rights on every transport).
2. §2.3.1: add "a stored object is the canonical identity projection, so its file hash is its name; volatile blocks are
   kept beside it (ADR 0061 D2, D8)"; "parameter sets match components by record SHA or InChIKey (D5)".
3. §2.3.2: give the lock its format id and orders (D10) and say it is derived, never stored in the revision.
4. §3 F3 exit: "the YAML loaders (`pr_c1.load_records`, `pr_lib.load_records`, the S10 records)" → add "and the S10
   verification records; 149 records from 7 files".
5. §7 R18: resolved by ADR 0061 D12 (loader views; `legacy_path_for` for path-only constructors). Add risks 1, 2 and 6
   above.
6. §8 `ComponentRecord` row: "`record-v2.schema.json`; the anchor is an identity field". Add rows for `data-lock.schema.json`
   and the `Records` protocol (ADR 0019 Amendment 8). ADR 0001 D1.3 row: add `molar_entropy` and
   `segment_molar_enthalpy` to ADR-F2's kinds.

---

## Review applied (W1 P1 review, `docs/reviews/W1-P1-review.md`, 2026-11-05)

Status stays Proposed. The choice on finding 19 follows `docs/roadmap/decisions.md` (2026-11-05, the reviewer's
preference).

| Finding | Edit |
| --- | --- |
| 3 | D10 parenthesis: `implementation_sha256` = `sha256(canonical_json([descriptor_sha256, self_sha256]))` (ADR 0060 D3). |
| 4 | D2 step 2a: optional members equal to `null`, `[]` or `{}` removed recursively; E-F3-4 asserts one SHA. |
| 5 | E-F3-9: in a checkout `methanol` is `component_ambiguous` (identity, two classes); `cas:67-56-1` → `s07`, `id:CH3OH` → `s10`. |
| 14 | D9: an identity class is a connected component of records sharing an InChIKey or a CAS. |
| 15 | D2 step 4: sort by canonical-JSON bytes of the key; only canonically identical elements removed; collisions refused at step 6. |
| 16 | D12: closed v1-key mapping table (unknown key fails index generation); `uncertainty` and `transformation` null for every legacy entry; the meaning and note rule applies to every entry. |
| 17 | D4: `provenance.inputs` = `[{scheme: record \| file, sha256, path}]`, file SHAs over LF-normalised bytes. |
| 18 | D7 and the code table: `molar_mass_inconsistent` is a notice listed with D7's findings; E-F3-10 restated. |
| 19 | D11: whole-source rows keyed by `source_sha256`; `legacy.` reserved for the importer; "latest" = insertion sequence. D13 `assess_rights` takes `scope: record \| source` with a `record_sha256`, from which the `source_sha256` is taken. |
| 20 | D8: a legacy record is copied into the project store when the project registers it or a data lock names it. |
| 21 | D8: the store opens lazily; refusal only at the first store operation; the absolute resolved root is checked. |
| N6 | D11: the S10 row `legacy.s10`, `permitted`, "NOTICE Wilson block", basis R-880. |
| Ruling 1 | D12 provenance table replaced (acentric factor direct; `s10` Δf h° {computed, measured} with `nasa7-low.json`; `saturation-points.json` named; element zeros in the ATcT row); principle stated; tagged `inputs`; 17 findings pinned in the index (`findings` per index record); risk 1 resolved. |
| Ruling 2 | Risk 2: referred to the specifier; build default `null` + `anchor_undetermined`; deadline before ADR-F4 is Accepted; default change regenerates the legacy index. |
| Ruling 3 | D13: `assess_rights` accepted with the request checks (`not_found`, `invalid_request`, one audit row, "latest" per D11). |

**Choices this pass made where the review was silent** (each revertible by editing the named section):
- `rights.notes` is dropped from the record (D12 table). Copying it into `sources` would give every `s07` record its own
  `source_sha256` and defeat whole-source rows. The source file keeps the text.
- A `legacy.` source id outside the importer is refused with ADR 0060's `reserved_namespace(legacy)` (D11), so no new
  code is introduced.
- `assess_rights` names a record even for a whole-source row (`scope: source`; D13), so ruling 3's checks apply to
  every call.
- The legacy index records each record's findings (D12), which is how "pinned in the index" is implemented.

**Not applied:** notes N7 (write-protocol details), N8 (for the specifier, not an ADR fix) and N9 (E-F3-2's
`selectable_bases()` scope): the review lists no exact edit for them. They remain open for F3-WO2 and WO3.

## Amendment 3 applied (`docs/roadmap/foundation-rulings.md` §15, Q2.R9, 2026-11-05)

Status stays Proposed.

| §15 edit | Applied to |
| --- | --- |
| 1 | D6: step 4 split into step 4 (`ig`, `anchor_defaulted`) and step 5 (`null`, `anchor_undetermined`). |
| 2 | D6: last sentence replaced (steps 4 and 5 are Q2.R9). |
| 3 | D7 Findings: `anchor_defaulted(<component>)` added. |
| 4 | D12: anchor sentence replaced (127 records `ig` by default, each with `anchor_defaulted`). |
| 5 | E-F3-13: nothing-phase-tagged clause replaced (`mol` → `ig`; `kg` → refused until ADR-F2). |
| 6 | Code table: `anchor_defaulted(<component>)` added to the notice row. |
| 7 | Risk 2: body replaced by the resolution. |
