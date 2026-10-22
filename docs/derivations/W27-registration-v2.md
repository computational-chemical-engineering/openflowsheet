# W27 registration, version 2 — several routes per method, and the `Co`/`CO` spelling clash

**Status:** registered 2026-10-22 by the design lane (`specifier`), package C9, branch `wp/C9`. Brief:
`docs/briefs/C9-W27-next-release.md`. Source: Frank's answer L01-Q1 (`docs/FRANK_QUESTIONS.md:15`), L01 spec findings
F-1 and F-2 (`docs/derivations/L01-spec.md:378-386`). Register entries R-570…R-574.
**Applies to:** the W27 coverage classification of **the release after v0.2**, and only when a caller selects
registration version 2. **v0.2's W27 (version 1) is unchanged**: this document edits none of its files.
**Machine-readable companion:** `benchmarks/m06/openidaes450/registration_v2.json`, written by
`docs/derivations/scripts/w27_registration_v2.py --emit`. The generator also writes the blocks of this document between
`c9:begin`/`c9:end` markers. `--check` regenerates both in memory and compares them byte for byte. A failed self-claim
(§6) makes it exit 2 and write nothing.

---

## 0. Read this first

- **Version 1** is `docs/derivations/M06-W27-registration.md` as amended by its §20–§23, with
  `benchmarks/m06/openidaes450/registration.json`. Preflight P2 pins their SHA-256 (`benchmarks/m06/w27/preflight.py:57-65`),
  and GC-V2-1 checks the same pins.
- **Version 2** is version 1 with the rules of §4 replacing the rules they name. Every other version 1 rule stands
  unchanged (W27-R01…R68, the maps, the sample, scoring).
- Numbering: **W27v2-R01…R11** are rules, **W27v2-A01…A23** are assertions and **GC-V2-1…8** are generator self-claims.
  The prefix keeps them apart from version 1's W27-R/A numbers, which other packages are still amending.
- Every expected value here is discrete (a class, a provider id, a reason triple, a refusal string). Comparison is
  exact equality. No tolerance applies anywhere.

## 1. Authority, scope, and what this establishes

**Authority.** W27 registration §0: the tables and rules are semantic judgements of the design lane, and the build lane
implements them as data. L01-Q1 directed this as a small separate package for the next release.

**Establishes:**
1. how a method group is judged when the snapshot holds several routes of that method (W27v2-R04…R06);
2. how the archive-spelling refusal treats a spelling that differs from a registry spelling only by case
   (W27v2-R08), and that `Co` is reviewed as distinct from carbon monoxide;
3. the provider row and snapshot line for `pr-lib-v1` (W27v2-R02, R03);
4. the refusals restated as a whole (W27v2-R07);
5. the version switch and the version 2 coverage record (W27v2-R01, R09);
6. a theorem: wherever version 1 classifies, version 2 gives byte-identical rows (W27v2-R10). The tie-break never
   changes a class (W27v2-R11).

## 2. Inputs (pinned)

| Input | Use | Pin |
| --- | --- | --- |
| `registration.json`, `M06-W27-registration.md`, `m06_w27_registration.py` | version 1, the base | SHA-256 of preflight P2 (GC-V2-1) |
| `benchmarks/m01/components.yaml`, `benchmarks/l01/components.yaml` | the `pr-c1-v1` and `pr-lib-v1` route rows of the registered snapshots | L01.A22 holds C1's; GC-V2-3 holds the library identity order |
| `benchmarks/m06/openidaes450/split.json`, `case_facts.json`, `coverage.json` | the development half only (filtered first) | C2's strict pins; `coverage.json` is read for its snapshot and its development rows, never byte-pinned (R-567) |
| `dry_illustration.json#/adversarial_states/0` | W27-A13's base row, the case of every registered state | GC-V2-3 |

## 3. The version switch

**W27v2-R01.** The classifier takes the registration version as an explicit input, either `1` or `2`, and defaults to
`1`. Version 1 behaves byte-identically to today, including its refusals of the snapshots version 2 accepts (W27v2-A09,
A10, A14, A18). Version 2 reads version 1's tables, then the replacements in `registration_v2.json#/tables`
(`provider_methods` replaces W27-R19's table, and `case_distinct` is new). The next release's own registration (its
preflight and release gate) selects version 2. Nothing selects it implicitly: not a package version and not the
presence of a provider.

## 4. Rules (version 2)

**W27v2-R02 (W27-R19 replaced: provider methods).** The table below. The only row added to version 1's table is
`pr-lib-v1 → cubic_pr` (GC-V2-2).

<!-- c9:begin:providers -->
| Provider id | Method |
| --- | --- |
| `pr-c1-v1` | `cubic_pr` |
| `pr-lib-v1` | `cubic_pr` |
| `syn001` | `synthetic_syn001` |
<!-- c9:end:providers -->

**W27v2-R03 (W27-R63's provider lines, one added).** Under the `bases-v1` reading, the route of the `pr-lib-v1` basis
takes its records from `benchmarks/l01/components.yaml` (`pr_lib.RECORDS_PATH`), in file order: `{id, name, formula,
cas, synthetic}`, where `formula` and `cas` come from the record's `identifiers`. Every component gets `phases =
["vapor"]`. `model_ids` is read from `MODEL_BASES`, as for every basis, and is empty while no model accepts the library
basis (L01 §4.3). A provider with no line here is still refused. The route rows of `registration_v2.json#/snapshots/S2`
are the expected output of this line (W27v2-A23).

**W27v2-R04 (W27-R20 replaced: availability with several routes of a method).** The case's non-reaction packages are
grouped by method, as in version 1. If there is more than one group, every package gets the reason
`multiple_routes_per_revision:<methods>`, as in version 1. One revision binds on one basis, so it has one method. If
there is exactly one group, of method *m*, take the snapshot's routes of method *m*. A route **serves** the group iff
it admits every available component (W27-R16) in every phase kind the group declares. This per-route test is version
1's. The group is available iff **at least one** route of *m* serves it.

**W27v2-R05 (W27-R62 replaced: which route judges the units).** Suppose the case has exactly one method group and at
least one route serves it. Then every unit is judged by W27-R13 against the `model_ids` of the **serving** route that
leaves the **fewest `UNIT_UNAVAILABLE` reasons**. Ties go to the smallest provider id, in code-point order. The row's
`units_judged_on` is that provider id. In every other case (no package, several groups, no serving route) the units
are judged against every model of the snapshot, and `units_judged_on` is null, as in version 1. A serving route with
an empty `model_ids` judges every non-junction unit `no_model:<function>` (W27v2-A04). Routes that do not serve are
never candidates. Neither the snapshot's route order nor a route's position decides.

**W27v2-R06 (the detail when no route serves).** If routes of *m* exist but none serves, the detail of each package
reason is the version 1 per-route detail (`route_mismatch:<provider>:missing=<cas,…>:phase=<cas:kind,…>`) of **every**
route of *m*, sorted by provider id and joined by `;`. With one route of *m* this is exactly version 1's string. With
no route of *m* it is `no_route:<m>`, as in version 1.

**W27v2-R07 (W27-R24 restated whole: refusals).** The classifier refuses to classify a snapshot. It writes no record,
exits non-zero, and names every item, when the snapshot holds:
- **(a)** a model id not in `model_functions` (unchanged);
- **(b)** a provider id not in W27v2-R02's table (unchanged in form);
- **(c)** an archive spelling that W27v2-R08 refuses;
- **(d)** a `routes_per_revision` other than 1 (unchanged), or **two routes with the same provider id**
  (`duplicate provider ids [...]`). This replaces version 1's refusal of two routes of one method: W27v2-R05 needs a
  unique tie-break key, and it judges several routes of one method;
- **(e)** a route model id that is not among the snapshot's models, or a model on no route (unchanged).

The message forms are version 1's (`coverage.py:183-209`), and (d)'s new item is `duplicate provider ids ['<id>', …]`.
Problems are joined by `; ` in the order (a), (b), (c), (d), (e). The (c) list is sorted and has no duplicates.

**W27v2-R08 (W27-R24 (c) restated: spellings that differ only by case).** Take a non-synthetic registry record with
CAS RN *X* and spellings *S* = {`id`, `name`, `formula`}, and an archive spelling *N*, meaning any name a case declares
(W27-R05). If `aliases[N] = X`, the pair passes. Otherwise it is refused iff
- *N* ∈ *S* exactly, or
- *N* equals a member of *S* only after case folding, **and** *X* is not in `case_distinct[N].distinct_from`.

`case_distinct` is a reviewed table. Each entry records a design-lane judgement that a spelling names a substance other
than the listed registry CAS RNs. The entry gives the spelling no identity: *N* stays as W27-R15 classifies it.

<!-- c9:begin:case_distinct -->
| Spelling | Distinct from | Reading | Development evidence |
| --- | --- | --- | --- |
| `Co` | 630-08-0 | cobalt (element symbol; the PrOMMIS nanofiltration solute declared beside Li and Cl), not carbon monoxide (CO, 630-08-0) | `blind_synthesized_prommis_membrane_cascade_flowsheet`, `blind_synthesized_prommis_nanofiltration_membrane_schematic` |
<!-- c9:end:case_distinct -->

*Why this rule.* Version 1's case folding exists so that an unaliased variant such as `co2` or `h2o` cannot leave a
registry chemical silently unavailable. Version 2 keeps that guard: W27v2-A16 refuses an unreviewed `co`. A spelling
that differs from a registry spelling only by case now passes only through a reviewed entry. *Rejected:* (i) matching
formulas and ids case-sensitively. That passes every unreviewed case variant, which is the silence the guard prevents
(mutant `spelling_formula_case_sensitive`). (ii) Aliasing `Co` to cobalt, 7440-48-4. In these cases `Co` is a solute in
an aqueous nanofiltration model, so element or Co²⁺ (22541-53-3) is a reading the archive does not settle. The alias
would also change version 2 rows, from `unidentified` to `chemical:…:not_in_registry`, and break W27v2-R10.

**W27v2-R09 (the version 2 coverage record).** It has version 1's members with their version 1 meanings
(`registration_sha256` is still the SHA-256 of `registration.json`), plus `registration_version: 2` and
`registration_v2_sha256` (the SHA-256 of `registration_v2.json`'s bytes). Its `schema` is `w27-coverage-v2`. G14
applies unchanged. A version 2 record has **no default output path**. The CLI refuses version 2 without `--out`, and
refuses an `--out` that resolves to the committed `coverage.json`. Both refusals happen before any case is classified,
with exit 2. A record over all cases contains held-out ids, so it goes under a `heldout/` path at a release gate (C2
SPLIT-R10 (b)). A development re-take filters to development ids first (L01 §6).

**W27v2-R10 (theorem: version 2 equals version 1 wherever version 1 classifies).** Let σ be a snapshot that version 1
accepts. Then version 2 accepts σ, and every row version 2 writes for σ is identical to version 1's, member by member.
The proof has two steps.
- *Acceptance.* (a) and (e) are the same check. (b): every provider of σ is in version 1's table, and version 2's
  table agrees with it there. (c): version 1 accepted σ, so every case-folded hit has `aliases[N] = X`, and this
  satisfies both clauses of W27v2-R08. (d): version 1 accepted σ, so `routes_per_revision = 1` and no two routes share
  a method. A provider id fixes the method, so no two routes share a provider id.
- *Rows.* The alias table is the same, and so is the registry's set of CAS RNs, so the component rows and reasons are
  the same. Each method has at most one route in σ. When a route serves, it is the only candidate of W27v2-R05 and is
  version 1's `_route_detail` result. When none serves, W27v2-R06 joins one detail, which is version 1's string. With
  no route, or with several groups, both versions give the same detail. The units are therefore judged on the same
  model list. ∎

This is executable: GC-V2-6 checks it on every registered state that version 1 accepts, and on all 225 development
cases at the committed snapshot (225 of 225 rows equal).

**W27v2-R11 (the tie-break never changes a class).** The chosen route minimises the number of unit reasons over the
serving routes, so every minimiser has the same count, and hence the same answer to "is there a unit reason". The
component and route reasons do not depend on the choice. So the class is fixed, and it reads as an existence claim: a
case is `CANDIDATE` iff **some** basis serves its property group **and** its models perform every unit. The choice
among tied routes changes only the unit details and `units_judged_on`.

## 5. Registered states and assertions

### 5.1 Snapshots and cases (`registration_v2.json#/snapshots`, `#/cases`)

The models of every snapshot are the nine `c1.*` ids. `pr-c1-v1` is C1's five records, with NH3 liquid and vapour and
the rest vapour only, and its route carries the nine models. This equals the committed snapshot's route (GC-V2-3).
`pr-lib-v1` is the library's nine records, vapour only, with no models. `zz-test-pr` is a test-only `cubic_pr` provider
holding H2 and H2O (vapour) and the models `c1.feed_source`, `c1.product_sink` and `c1.tp_heater`. Its id sorts after
`pr-lib-v1`, so a tie-break by id alone would pick the wrong route. Test providers come from
`#/test_provider_methods`, as W27-A02 allows.

| Snapshot | Routes, in snapshot order | Why it is in the list |
| --- | --- | --- |
| S1 | `pr-c1-v1` | one route per method: the version 1 equivalence state |
| S1co | `pr-c1-v1` + the CO record (630-08-0, vapour) | isolates the spelling rule from the multi-route rule |
| S2 | `pr-c1-v1`, `pr-lib-v1` | the real two-route build of L01 SC-11 |
| S2r | `pr-lib-v1`, `pr-c1-v1` | the same build with the order reversed: the order must not decide |
| S2co | S2 with CO on `pr-lib-v1` | both fixes together |
| S2dup | `pr-c1-v1`, `pr-lib-v1`, `pr-lib-v1` | duplicate provider id |
| S2rpr | S2 with `routes_per_revision = 2` | (d) stands |
| S2x | S2 with `pr-lib-v1` listing `x.test` | (e) stands |
| S3 | `zz-test-pr`, `pr-lib-v1`, `pr-c1-v1` | fewest reasons beats the smaller id; ties do not go to the first route |

The cases are all W27-A13's base row (Feed → Heater → Product, one package `generic[Vap:VaporPhase:Cubic(type=PR)]`).
**H2** is the row itself. **H2O** declares H2O, which only the library holds. **H2-VL** has its package in liquid and
vapour (as W27-A15). **H2-2M** adds a second package, `generic[Vap:VaporPhase:Ideal]` (as W27-A14). **CO-Co**
declares `CO` and `Co`. **co** declares the unreviewed lowercase `co`.

### 5.2 The states (`registration_v2.json#/states`)

The expected values are derived by hand from the rules above. The generator does not derive them: it refuses to emit
unless its reference reproduces each one (GC-V2-5). Each listed mutant is one rule deliberately broken, and it must
change that state's outcome. The **Version** column gives the registration version. The provider table is that
version's, except `v1+lib`, which is version 1's table with `pr-lib-v1 → cubic_pr` added, as in L01 SC-11. Reasons
list as `kind` `subject` `detail`, in row order.

<!-- c9:begin:states -->
| Assertion | Version | Snapshot | Case | Expected | Mutants that must fail | Why |
| --- | --- | --- | --- | --- | --- | --- |
| W27v2-A01 | 2 | S1 | H2 | `CANDIDATE`, judged on `pr-c1-v1`; reasons: none | — | one route per method: v2's row equals v1's (W27v2-R10) |
| W27v2-A02 | 2 | S2 | H2 | `CANDIDATE`, judged on `pr-c1-v1`; reasons: none | `shared_method_refused` | two cubic_pr routes serve; the one with models judges |
| W27v2-A03 | 2 | S2r | H2 | `CANDIDATE`, judged on `pr-c1-v1`; reasons: none | `first_serving` | snapshot order does not choose the route |
| W27v2-A04 | 2 | S2 | H2O | `UNIT_UNAVAILABLE`, judged on `pr-lib-v1`; reasons: `UNIT_UNAVAILABLE` `Feed` `no_model:feed units=fs.feed`; `UNIT_UNAVAILABLE` `Heater` `no_model:heater units=fs.heater`; `UNIT_UNAVAILABLE` `Product` `no_model:product units=fs.product` | `all_routes` | only the library route serves H2O; units are judged on its (empty) model list |
| W27v2-A05 | 2 | S3 | H2O | `CANDIDATE`, judged on `zz-test-pr`; reasons: none | `smallest_id` | fewest unit reasons beats the smaller provider id |
| W27v2-A06 | 2 | S3 | H2 | `CANDIDATE`, judged on `pr-c1-v1`; reasons: none | `first_serving` | a tie on unit reasons goes to the smaller provider id, not the first route |
| W27v2-A07 | 2 | S2 | H2-VL | `PROPERTY_ROUTE_UNAVAILABLE`, judged on null; reasons: `PROPERTY_ROUTE_UNAVAILABLE` `fs.props` `route_mismatch:pr-c1-v1:missing=:phase=1333-74-0:liquid;route_mismatch:pr-lib-v1:missing=:phase=1333-74-0:liquid` | `detail_last` | no route serves: every route's mismatch, by provider id |
| W27v2-A08 | 2 | S2 | H2-2M | `PROPERTY_ROUTE_UNAVAILABLE`, judged on null; reasons: `PROPERTY_ROUTE_UNAVAILABLE` `fs.props` `multiple_routes_per_revision:cubic_pr,ideal_gas`; `PROPERTY_ROUTE_UNAVAILABLE` `fs.props2` `multiple_routes_per_revision:cubic_pr,ideal_gas` | — | one basis per revision stands (W27-R20's first sentence) |
| W27v2-A09 | 1 | S2 | H2 | refused: `unregistered provider ids ['pr-lib-v1']` | — | v1 is unchanged: pr-lib-v1 is not in v0.2's table |
| W27v2-A10 | 1 (v1+lib) | S2 | H2 | refused: `routes sharing a method ['cubic_pr']` | — | v1 is unchanged: W27-R24 (d) still refuses two routes of one method |
| W27v2-A11 | 2 | S2dup | H2 | refused: `duplicate provider ids ['pr-lib-v1']` | `no_duplicate_refusal` | the tie-break key must be unique |
| W27v2-A12 | 2 | S2rpr | H2 | refused: `routes_per_revision 2 is not 1` | — | one route per revision stands |
| W27v2-A13 | 2 | S2x | H2 | refused: `route model ids not among the models ['x.test']` | — | (e) stands |
| W27v2-A14 | 1 | S1co | CO-Co | refused: `archive spellings of registry chemicals not aliased ['Co->630-08-0']` | — | v1 is unchanged: the casefold check refuses CO against Co (L01 F-2) |
| W27v2-A15 | 2 | S1co | CO-Co | `COMPONENT_UNAVAILABLE`, judged on `pr-c1-v1`; reasons: `COMPONENT_UNAVAILABLE` `Co` `unidentified` | `spelling_v1` | v2 accepts CO beside the reviewed Co; Co stays unidentified |
| W27v2-A16 | 2 | S1co | co | refused: `archive spellings of registry chemicals not aliased ['co->630-08-0']` | `spelling_formula_case_sensitive` | an unreviewed case variant is still refused |
| W27v2-A17 | 2 | S2co | CO-Co | `UNIT_UNAVAILABLE`, judged on `pr-lib-v1`; reasons: `UNIT_UNAVAILABLE` `Feed` `no_model:feed units=fs.feed`; `UNIT_UNAVAILABLE` `Heater` `no_model:heater units=fs.heater`; `UNIT_UNAVAILABLE` `Product` `no_model:product units=fs.product`; `COMPONENT_UNAVAILABLE` `Co` `unidentified` | `spelling_v1` | both fixes together: CO on the library route |
<!-- c9:end:states -->

### 5.3 Assertions for the build lane beyond the states

| Id | Assertion | Expected | Catches |
| --- | --- | --- | --- |
| W27v2-A18 | `tests/test_m06_w27_coverage.py` | unmodified by WO-C9-1 (`git diff main -- tests/test_m06_w27_coverage.py` empty), and green | a version 1 change hidden by an edited test |
| W27v2-A19 | every state of §5.2, run through the production classifier with its version and table | refusal strings equal; `class`, `units_judged_on` and the ordered `[kind, subject, detail]` reasons equal | the implementation disagreeing with the registration |
| W27v2-A20 | production version 2 on the 225 development cases (filtered first) at the committed snapshot | every row equals the committed row, whole | a version 2 path that drifts where version 1 classifies (W27v2-R10) |
| W27v2-A21 | `coverage_document` version 2 for the case H2 at S2 | `schema` `w27-coverage-v2`, `registration_version` 2, `registration_v2_sha256` equal to the file's SHA-256, `units_judged_on` `pr-c1-v1` | a record that does not say which rules made it |
| W27v2-A22 | the CLI with `--registration-version 2` and no `--out`, or with `--out` set to the committed `coverage.json` | exit 2, the message names `SPLIT-R10`, no file is written or changed (that file's bytes stay the same), and no case is classified | a version 2 run overwriting version 1's record, or a held-out record written to an unprotected path |
| W27v2-A23 | the snapshot line of W27v2-R03, when WO-L01-3 has exposed `pr-lib-v1` | the route's `components` equal `registration_v2.json#/snapshots/S2/routes/1/components` | a library route read with the wrong phases or records |

## 6. Generator self-claims (`w27_registration_v2.py` refuses to emit if one fails)

- **GC-V2-1** — version 1's registration, document and generator have their v0.2 SHA-256.
- **GC-V2-2** — the version 2 provider table is version 1's plus exactly `pr-lib-v1 → cubic_pr`, onto a registered
  method, and every added provider has a snapshot line.
- **GC-V2-3** — there are nine C1 models. The library's identity order is L01's. The `pr-c1-v1` rows equal the committed
  snapshot's. The base case is W27-A13's base row.
- **GC-V2-4** — every `case_distinct` spelling is unaliased, collides with an alias of each listed CAS RN (valid check
  digits) only by case, and is declared by exactly the development cases listed as evidence.
- **GC-V2-5** — every state of §5.2 gives its hand-written outcome. Every listed mutant changes its state, and each of
  the eight mutants is caught by at least one state. The mutants: `first_serving` (version 1's loop),
  `smallest_id`, `all_routes` (no serving filter), `detail_last`, `shared_method_refused`, `no_duplicate_refusal`,
  `spelling_v1`, `spelling_formula_case_sensitive`.
- **GC-V2-6** — W27v2-R10 on every state version 1 accepts and on the 225 development rows at the committed snapshot.
- **GC-V2-7** — on development spellings, version 1 refuses the CO record with exactly `['Co->630-08-0']` (L01 SC-13),
  and version 2 accepts it, on S1co and on S2co.
- **GC-V2-8** — the generated blocks of this document are current (`--check`).

Negative controls run while this was written: emptying `case_distinct` makes GC-V2-5 refuse at W27v2-A15, and editing
A05's expected route to `pr-lib-v1` makes GC-V2-5 refuse at A05.

## 7. Effects

- **On committed records:** none. Version 1's files and every W27 record keep their bytes. `registration_v2.json` is
  new and holds no held-out id: its only case ids are the synthetic one and the two development ids of `case_distinct`.
- **On C2's split (SPLIT-R12):** the split reads only `case_id`, `family` and `class`. At every snapshot version 1
  accepts, W27v2-R10 makes these identical under version 2, for every case, held-out included: this follows from the
  rules and was computed on no held-out row. At a snapshot version 1 refuses (two routes of one method, or the CO
  record), version 1 gives no class to compare against. The version 2 record is a new measurement, written outside
  the committed `coverage.json` (W27v2-R09), and SPLIT-A18 is untouched.
- **On S04 / WO-L01-3:** their re-take can now judge a build exposing `pr-lib-v1`, and later a CO record, under version 2.
  This document projects no count for it.

## 8. What this does not establish

- **No coverage number.** No development or held-out count is projected for a two-route build. That is S04's measured
  re-take (L01 §6, WO-L01-3).
- **Acceptance of a CO record is shown on development spellings only.** At a release gate the spelling check reads
  every case. A held-out-only case variant of a registry spelling would be **refused**, which is a loud failure and
  leads to an amendment. It would never pass silently.
- **No identity for `Co`.** It stays `unidentified`, and nothing here says whether it is the element or the ion.
- **No change to scoring.** A limitation in a version 2 campaign is judged against the reasons of `units_judged_on`.
  Reasons that another tied route would have given are not acceptable alternatives (§9 Q-2).
- **No route ranking beyond unit reasons.** Two serving routes are not compared on accuracy, domain or phase
  richness. The rule decides only which models judge the units.
- **Not a validation of `pr-lib-v1`.** Its admission into a snapshot says nothing about its accuracy (L01 §9).

## 9. Open questions, each with a recommended default

- **Q-1 (needs the user's preference; not escalated).** Should the next release also re-report v0.2's coverage under
  version 2? *Default:* no. The next release reports its own coverage under version 2, and v0.2's record stands as
  registered. By W27v2-R10 the two agree on v0.2's snapshot.
- **Q-2 (needs a fact: a version 2 campaign).** Should a limitation that names a reason given only by a tied route
  count as correct? *Default:* no. Revisit only if a registered campaign on version 2 finds such a tie among its
  sampled cases. The fact needed is the number of sampled cases with two or more minimising routes, which the
  campaign's coverage record shows.
- **Q-3 (needs a fact).** Are there further case-only collisions once CO or other records enter a route? *Default:* a
  refusal under W27v2-R08 is closed by a new `case_distinct` entry or alias in an amendment, never by relaxing the rule.

## 10. Work order

**WO-C9-1** (build lane, `opus-engineer`, about 100k context) is in `docs/briefs/C9-WO-1-classifier-v2.md`. It
implements W27v2-R01, R04…R09 in `benchmarks/m06/w27/` behind the version switch, and adds tests W27v2-A18…A22 and the
generator `--check`. W27v2-A23 belongs to WO-L01-3.

## 11. Decision-register entries

R-570 (version 2 and its switch), R-571 (the serving rule), R-572 (the spelling rule and `Co`), R-573 (`pr-lib-v1`'s
row and line; a route with no models), R-574 (the version 2 record and its effect on the split), in
`docs/decision-register.md`.
