# W27 registration, version 3 — S11's bases, the route key, and the column row

**Status:** transcribed 2026-10-27 by the build lane (S11 WO-A4, branch `wp/S11-a`) from the S11 design note
`docs/derivations/S11-design.md` §4.10, which is the normative text (ADR 0050 D9, register R-808), as amended by its §9,
by `docs/derivations/S11-units-design.md` §5.4 item 2 and §4.10, and by the S11 rulings item 3 (R-832, W27v3-R09). Where this document says more than §4.10, the addition is a
build-lane reading, marked **(reading)** and logged in `docs/S11A_DECISIONS.md`; the design lane may overrule it.
**Applies to:** W27 coverage classification when a caller selects registration version 3. The next release's preflight
and release gate select it (W27v3-R01). **Versions 1 and 2 are unchanged**: this document edits none of their files.
**Machine-readable companion:** `benchmarks/m06/openidaes450/registration_v3.json`, written by
`docs/derivations/scripts/w27_registration_v3.py --emit`, which also writes the blocks of this document between
`s11:begin`/`s11:end` markers. `--check` regenerates both in memory and compares them byte for byte. A failed
self-claim (§6) makes it exit 2 and write nothing.

---

## 0. Read this first

- **Version 2** is `docs/derivations/W27-registration-v2.md` with `registration_v2.json`. **Version 3** is version 2
  with the rules of §4 replacing or extending the rules they name. Every other version 2 rule stands unchanged
  (W27v2-R04, the serving rule; W27v2-R08, the spelling rule, except as W27v3-R09 restricts it; the maps, the sample,
  scoring).
- Numbering: **W27v3-R01…R08** are §4.10's rules and **W27v3-R09** is R-832's, **W27v3-A01…A09** are registered
  states, and **GC-V3-1…6** are generator self-claims. S11's own assertions S11.A30–A33 (§5.3) are what the build lane's tests check.
- Every expected value is discrete (a class, a provider id, a reason triple, a refusal string). Comparison is exact
  equality. No tolerance applies anywhere.

## 1. Why a version 3 (ADR 0050 D9)

S11 makes 127 bases selectable: SYN-001, C1, IAPWS-95, Wilson, and one CoolProp basis per admitted fluid. Version 2
cannot judge that build: it has no provider row for `iapws95-v1`, `wilson-ig-v1` or `coolprop-heos-v1` (W27v2-R07(b)),
its R07(d) refuses two routes with one provider id, and with no snapshot line the build's snapshot is refused (W27-R63).
Adding the rows to `registration_v2.json` would move a SHA-256 the version 2 records carry (W27v2-A21). Rejected:
editing version 2; not registering.

## 2. Inputs (pinned)

| Input | Use | Pin |
| --- | --- | --- |
| `registration.json`, `M06-W27-registration.md`, `m06_w27_registration.py` | version 1 | GC-V2-1's SHA-256 (GC-V3-1) |
| `registration_v2.json`, `W27-registration-v2.md`, `w27_registration_v2.py` | version 2, the base, and its reference | SHA-256 at C9 (GC-V3-1) |
| `benchmarks/s05/components.yaml`, `s07/components.yaml`, `s10/records.yaml`, `m01/components.yaml`, `l01/components.yaml` | the routes of the registered snapshots | GC-V3-3 (counts, the water record) |
| `split.json`, `case_facts.json`, `coverage.json` | the development half only (filtered first) | as in version 2 |

## 3. The version switch

**W27v3-R01.** The version switch accepts `3`. Versions 1 and 2 behave byte-identically. The next release's preflight
and release gate select `3`. Nothing selects it implicitly. **(reading)** Version 3 writes its record under version 2's
output-path rules (W27v2-R09, R-580), as `w27-coverage-v3`, carrying `registration_v3_sha256` beside version 2's
members.

## 4. Rules (version 3), from S11 §4.10

- **W27v3-R02.** `provider_methods` is v2's table plus `iapws95-v1 → iapws95`, `wilson-ig-v1 → activity_coefficient`
  and `coolprop-heos-v1 → pure_helmholtz`. (S11 §9 adds `wilson-ig-v2 → activity_coefficient`, keeping v1's row; that
  row is WO-D5's, and since D5 it is in this registration, with its line.)
- **W27v3-R03.** `methods` gains `pure_helmholtz`: "a pure-fluid multiparameter Helmholtz EOS other than IAPWS-95
  (CoolProp HEOS); matches no case method".
- **W27v3-R04.** `model_functions` gains `syn001.column: {function: null, offers: [], why_none:
  "column_function_unregistered"}`. Registering a `column` function against the archive is a workstation follow-on.
  **(reading)** `model_none_reasons` gains the meaning of `column_function_unregistered` (`registration_v3.json`).
  S11 units design §4.10 adds seven rows, each with `offers: []` and onto an existing function of
  `registration.json` `units.functions`: `thermal.heater` → `heater`, `thermal.valve` → `valve`, `thermal.mixer` →
  `mixer`, `thermal.flash` → `flash`, `thermal.pump` → `pump`, `thermal.compressor` → `compressor`, `thermal.turbine`
  → `expander`.
- **W27v3-R05.** `PROVIDER_LINES_V3(basis, ids, every)`:
  - `pr-c1-v1` and `pr-lib-v1` keep their v2 lines;
  - every other basis takes `ROOT / basis.record_source`, reading `{id, name, formula, cas, synthetic}` from each
    record's `identifiers`, with `phases = every` (from `describe().phases`) for each component;
  - a provider with no line is refused.

  **(reading)** "Every other basis" is the registered providers `syn001`, `iapws95-v1`, `wilson-ig-v1` and
  `coolprop-heos-v1`; any other provider id has no line and its snapshot is refused (W27-R63), so a new provider
  (`wilson-ig-v2`) enters by an amendment adding its row and line. A version 3 snapshot's routes carry the
  `record_source` of their basis, under schema `w27-registry-snapshot-v3`; versions 1 and 2 build the snapshot they
  built before.
- **W27v3-R06.** R07(d) is replaced: two routes with the same key `(provider_id, record_source, components)` are
  refused. **(reading)** A route with no `record_source` has no key and is refused (`routes with no record_source
  [<provider ids>]`); the duplicate refusal reads `duplicate route keys [<keys>]`, each key as the tuple of R07.
- **W27v3-R07.** R05's tie-break is the route key in code-point order: `provider_id`, then `record_source`, then the
  components joined by `,`. **(reading)** The same order lists the mismatch details when no route serves (W27v2-R06's
  join). A row's `units_judged_on` stays the chosen route's provider id (version 2's form): `MODEL_BASES` admits a
  model per provider, so every route of one provider in a build carries the same models.
- **W27v3-R08.** Snapshot S4 is the S11 build's routes (127), generated at WO-I1b (S11 §9) and registered with its
  SHA-256. It is not part of this transcription.
  *Registered 2026-10-27 (WO-I1b):* S4 is `benchmarks/m06/openidaes450/snapshot_s4.json#/snapshot`, built at
  `82a1d87b` (127 routes, the Wilson route on `wilson-ig-v2`), SHA-256
  `58ba0d48e5e6f4d6a22bc94b2ad5f135d907b8488134dedb25eaeabf781d3231`. On the 225 development rows it classifies
  under version 3 with no refusal: 3 `CANDIDATE`, 3 `COMPONENT_UNAVAILABLE`, 3 `PROPERTY_ROUTE_UNAVAILABLE`, 32
  `NOT_STEADY_STATE_SIMULATION`, 184 `UNIT_UNAVAILABLE` (`scripts/s11_w27_s4.py --check`; S11.A40).
- **W27v3-R09 (W27v2-R08 under version 3; R-832).** A non-synthetic registry record with no CAS RN (`cas` absent, null
  or empty) takes no part in W27v2-R08: it can match no case component (W27-R15), so no alias can close a collision
  with it. Records with a CAS RN keep W27v2-R08 unchanged. Versions 1 and 2 are unchanged.

**Effects (S11 §4.10).** The Wilson records carry no CAS RN (R-706), so W27v3-R09 skips them and the route serves no
case; CoolProp's method matches no case; IAPWS-95's route serves the property side of IDAES `iapws95` cases.

The provider table and lines:

<!-- s11:begin:providers -->
| Provider id | Method | Line (W27v3-R05) |
| --- | --- | --- |
| `coolprop-heos-v1` | `pure_helmholtz` (added) | the records at ROOT / basis.record_source ({id, name, formula, cas, synthetic} from each record's identifiers); every phase of describe().phases for every component |
| `iapws95-v1` | `iapws95` (added) | the records at ROOT / basis.record_source ({id, name, formula, cas, synthetic} from each record's identifiers); every phase of describe().phases for every component |
| `pr-c1-v1` | `cubic_pr` | version 2's line (pr_c1.RECORDS_PATH; vapor for pr_c1.LIGHT, every phase else) |
| `pr-lib-v1` | `cubic_pr` | version 2's line (pr_lib.RECORDS_PATH; vapor for every component) |
| `syn001` | `synthetic_syn001` | the records at ROOT / basis.record_source ({id, name, formula, cas, synthetic} from each record's identifiers); every phase of describe().phases for every component |
| `wilson-ig-v1` | `activity_coefficient` (added) | the records at ROOT / basis.record_source ({id, name, formula, cas, synthetic} from each record's identifiers); every phase of describe().phases for every component |
| `wilson-ig-v2` | `activity_coefficient` (added) | the records at ROOT / basis.record_source ({id, name, formula, cas, synthetic} from each record's identifiers); every phase of describe().phases for every component |
<!-- s11:end:providers -->

## 5. Registered states and assertions

### 5.1 Snapshots and cases (`registration_v3.json#/snapshots`, `#/cases`)

| Snapshot | Routes, in snapshot order | Why it is in the list |
| --- | --- | --- |
| B | `pr-c1-v1` (the nine `c1.*` models), `iapws95-v1` (H2O), `wilson-ig-v1` (the three records; routing models and `syn001.column`), then 123 `coolprop-heos-v1` routes, one per record of `s07/components.yaml` | S11's bases beside C1; the routing models are `syn001.feed_source`, `product_sink`, `stream_splitter` |
| Bi | B without the Wilson route (and without `syn001.column`) | IAPWS-95 serving an `iapws95` case without the Wilson route (A04; A08 is the same case on B) |
| Bdup | B with the CO2 CoolProp route listed twice | duplicate route key |
| Bsrc | B with the IAPWS-95 route's `record_source` removed | a route with no key |
| T | `pr-c1-v1`, then two `zz-test-pr` routes over the library's H2 and H2O, record sources `benchmarks/zz-test/b.yaml` (feed, product, `c1.tp_heater`) and `…/a.yaml` (the same plus `syn001.tp_heater`) | two routes of one provider that differ only by record source |
| Tr | T with the two `zz-test-pr` routes reversed | the order must not decide |
| S1co | version 2's S1co (W27v2-A16) with each route's `record_source` added | W27v2-R08 still refuses records that have a CAS RN (W27v3-R09) |

Every S11 route admits liquid and vapour for each component (the bases' `describe().phases`). The cases are version
2's **H2** and **H2O** (W27-A13's base row, a PR vapour package), and **H2O-iapws**: the base row declaring H2O
with the one package `idaes.models.properties.iapws95.Iapws95ParameterBlock` in liquid and vapour; and version 2's
**co** (W27v2-A16's case, which spells `co`).

### 5.2 The states (`registration_v3.json#/states`)

The expected values are written by hand from the rules above; the generator refuses to emit unless its reference
reproduces each one (GC-V3-4). A state's outcome also lists, for each unit, the models that serve it; the table shows
the Heater's.

<!-- s11:begin:states -->
| Assertion | Version | Snapshot | Case | Expected | Mutants that must fail | Why |
| --- | --- | --- | --- | --- | --- | --- |
| W27v3-A01 | 3 | B | H2 | `CANDIDATE`, judged on `pr-c1-v1`; reasons: none; Heater models: `c1.tp_heater` | `provider_table_v2`, `column_unregistered`, `duplicate_provider_refusal` | the S11 bases beside C1: 123 CoolProp routes with distinct keys and the column are admitted, and pr-c1-v1 still judges a cubic_pr case |
| W27v3-A02 | 3 | Bdup | H2 | refused: `duplicate route keys [('coolprop-heos-v1', 'benchmarks/s07/components.yaml', 'CO2')]` | `no_key_refusal` | two routes with one key are refused (W27v3-R06) |
| W27v3-A03 | 3 | Bsrc | H2 | refused: `routes with no record_source ['iapws95-v1']` | — | a route with no record_source has no key |
| W27v3-A04 | 3 | Bi | H2O-iapws | `UNIT_UNAVAILABLE`, judged on `iapws95-v1`; reasons: `UNIT_UNAVAILABLE` `Heater` `no_model:heater units=fs.heater`; Heater models: none | `provider_table_v2` | IAPWS-95's route serves an iapws95 case's property side; its routing models judge the units |
| W27v3-A05 | 3 | T | H2O | `CANDIDATE`, judged on `zz-test-pr`; reasons: none; Heater models: `c1.tp_heater`, `syn001.tp_heater` | `first_serving`, `record_source_ignored` | two routes of one provider differ only by record_source; a tie goes to the smaller key (benchmarks/zz-test/a.yaml), not the first route |
| W27v3-A06 | 3 | Tr | H2O | `CANDIDATE`, judged on `zz-test-pr`; reasons: none; Heater models: `c1.tp_heater`, `syn001.tp_heater` | `record_source_ignored` | the same build with the two routes reversed: the order does not decide |
| W27v3-A07 | 2 | T | H2O | refused: `duplicate provider ids ['zz-test-pr']` | — | version 2 is unchanged: it refuses two routes of one provider id |
| W27v3-A08 | 3 | B | H2O-iapws | `UNIT_UNAVAILABLE`, judged on `iapws95-v1`; reasons: `UNIT_UNAVAILABLE` `Heater` `no_model:heater units=fs.heater`; Heater models: none | `cas_less_refused` | A04's outcome, now on B: the Wilson records carry no CAS RN, so W27v3-R09 skips them (R-832) |
| W27v3-A09 | 3 | S1co | co | refused: `archive spellings of registry chemicals not aliased ['co->630-08-0']` | `spelling_rule_off` | W27v2-A16's refusal under version 3: records with a CAS RN keep W27v2-R08 (R-832) |
<!-- s11:end:states -->

### 5.3 S11's assertions (the build lane's tests, `tests/test_s11_w27_v3.py`)

| Id | Assertion |
| --- | --- |
| S11.A30 | The W27 v1 and v2 outputs on every registered state are byte-identical (to the identity base `8c34ecb0`). |
| S11.A31 | v3 refuses a duplicate route key, and admits 123 CoolProp routes with distinct keys. |
| S11.A32 | `w27_registration_v3.py --check` is OK. |
| S11.A33 | An IAPWS-95 route row reads CAS `7732-18-5` from `benchmarks/s05/components.yaml`. |

The production classifier also reproduces every state of §5.2 (`class`, `units_judged_on`, the ordered
`[kind, subject, detail]` reasons and the unit models), and the S11 build's version 3 snapshot (127 routes) builds with
no `SnapshotUnsupportedError`. S11.A40 (that snapshot equals S4) is WO-I1b's.

## 6. Generator self-claims (`w27_registration_v3.py` refuses to emit if one fails)

- **GC-V3-1** — version 1's and version 2's registrations, documents and generators have their pinned SHA-256.
- **GC-V3-2** — the version 3 provider table is version 2's plus exactly the rows of R02 (three, and D5's fourth), onto registered
  methods; `pure_helmholtz` is new and matches no case package; every provider has a line.
- **GC-V3-3** — `syn001.column` and the seven `thermal.*` rows are new to the model table; the column's `why_none` is
  a new registered reason and each thermal row is onto an existing function with `offers: []`; the CoolProp
  file holds 123 records with distinct ids; the IAPWS-95 file holds H2O with CAS `7732-18-5`; B has 126 routes.
- **GC-V3-4** — every state of §5.2 gives its hand-written outcome; every listed mutant changes its state, and each
  mutant is caught by at least one state. The mutants: `provider_table_v2` (no added rows), `column_unregistered`
  (no R04 row), `duplicate_provider_refusal` (v2's (d)), `no_key_refusal`, `record_source_ignored` (a key without
  `record_source`), `first_serving` (snapshot order), `cas_less_refused` (W27v2-R08 applied to CAS-less records, no
  W27v3-R09) and `spelling_rule_off` (W27v2-R08 skipped for every record).
- **GC-V3-5** — version 3 equals version 2 wherever version 2 accepts: on every version 2 registered snapshot × case
  with each route's record source added, and on the 225 development rows at the committed snapshot.
- **GC-V3-6** — the generated blocks of this document are current (`--check`).

## 7. Effects

- **On committed records:** none. Versions 1 and 2 and every W27 record keep their bytes. `registration_v3.json` is
  new and holds no held-out id.
- **On the next release's W27 run:** it selects version 3 and reads the S11 build's 127 routes. The Wilson route
  serves no case (W27v3-R09); the release's W27 record states this conservative under-count (R-832).

## 8. What this does not establish

- No coverage number for the S11 build (that is the release's measured run).
- No `column` function: the column serves no case unit until a workstation follow-on registers one.
- Nothing about the accuracy of any provider: a route's admission is not a validation.

## 9. Open questions, each with a recommended default

- **Q-1 (ruled: R-832; W27v3-R09, A08 restated, A09).** The Wilson records carry no CAS RN, and version 2's spelling rule
  (W27v2-R08, unchanged here) refuses a non-synthetic record whose id, name or formula an archive case spells, unless
  that spelling's alias is the record's CAS RN. Measured on this build's records against `case_facts.json`'s
  spellings: the Wilson route alone gives five, `CH3OH->None`, `H2O->None`, `ethanol->None`, `methanol->None` and
  `water->None` (CoolProp's 123 and IAPWS-95's records give none). So version 3 refuses the S11 build's snapshot at
  classification, which contradicts §4.10's stated effect ("its route serves no case"). State W27v3-A08 registers
  the refusal as the rules now give it; an amendment that settles Q-1 changes that state. *Default proposed:* a record
  with no CAS RN is skipped by the spelling rule (it can match no case component, by W27-R15's CAS identity), as an
  amendment to this document; alternatively the Wilson records gain CAS RNs (R-706 holds them back). *Ruled (R-832):*
  the default, as W27v3-R09; giving the Wilson records CAS RNs stays with R-706.
- **Q-2 (done at WO-D5).** `wilson-ig-v2 → activity_coefficient` and its line are added with WO-D5 (S11 §9).

## 10. Decision-register entries

R-808, R-832 (`docs/decision-register.md`).
