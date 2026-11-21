# F3 package review and design-lane ruling round 2 (WO5a, WO5b)

Design lane, `reviewer`, 2026-11-18. Brief `docs/briefs/F3-review-2.md`. Branch `wp/F3` at `c7e942a7` (code at
`50e6ca04`). Read: `docs/F3_DECISIONS.md` from F3-WO5a to the end and R1-B6; ADR 0061 D7 to D9, D11 to D14, the exit
tests, the code table and the applied sections; ADR 0019 Amendments 7 and 8; `records/reactions.py`,
`application/records_service.py` and `records/importers/user_file.py` whole; the diffs of `operations.py`,
`service_core.py`, `local.py`, `authz.py`, `record_types.py`, the catalogue and `records.json`;
`schemas/record-results.schema.json`; `tests/test_f3_reactions.py` whole, the E-F3-11, E-F3-12 and D11 tests; the five
descriptions; Q3.R7, Q7.A3 and ADR 0062's code list and `reaction_sets` form.

**Verdict.** Not sound to close out as it stands: four defects must be fixed first (M1 to M4). After the build-lane
changes C1 to C12 the package is sound to close out. The numerics of `reactions.py` are correct against D7: every sum is
an exact `Fraction` of the stored doubles, the inequality is `|Σ ν M| ≤ 4ε Σ |ν M|` with ε = 2⁻⁵² and `≤`, element and
charge imbalance refuse, the molar-mass imbalance is a notice. D11's precedence (`rights.effective`) and the three
named `legacy.` paths (`sources`, a v1 file's `defaults.source_id`, the index copy) are as the ADR states. No ruling
contradicts ADR 0061, ADR 0060, ADR 0019 or Q2, Q7, Q9; one question goes to Frank (Q-F1). ADR 0061 gains the closing
section "F3 ruling round 2 applied" (clarifications only; no D-section is edited), and the register gains R-1052 to
R-1057, in the commit of this file.

## What was run (worktree source, `PYTHONPATH=src:tests`, main checkout's venv)

Three probe scripts on `LocalApplication.in_memory()` through `dispatch`, and one test. Numbers below are from these
runs; nothing was built and no gate was run (the build lane's, per the brief).

| Probe | Result |
| --- | --- |
| `register_record`, `record-v2-yaml`, 903 characters, 24 nested aliases (2²⁴ leaves) before one valid record | refused `record_schema_invalid` after **291.8 s** |
| YAML date, `.nan`, `.inf`, `!!binary`, `!!set`, integer key, list key in a v2 YAML file | each refused `record_schema_invalid`, no crash |
| `register_record {"record": {…, "name": ""}}` | explanation summary "The record is not valid at **/record**."; the record's pointer `/name` only in `detail.refusal.params` |
| the same error document with `detail.reason` = `record_schema_invalid(/name)` (WO5b-9's alternative) | still "/record" (MSG §3.1: `detail` members over chain args) |
| `detail.reason` = `component_ambiguous(a, b: c)` | no chain parsed; `identifier_invalid(user.a, b, cas)` renders "The b identifier of component user.a" |
| `detail.pointer` = `/record/name`, bare `reason` | "The record is not valid at /record/name." |
| `register_record {"file": {"format": "record-v2-json", "content": "[]"}}` | **`{"results": []}`** (schema: `minItems: 1`) |
| `search_records {"limit": 1}` | 1 item, `ambiguous_identity`, **134 classes, 25 796 bytes** |
| `m01`'s H2 with the molar mass doubled, source renamed `user.copy`, `legacy` member kept | **stored** (`created: true`); `legacy.file_sha256` is `m01`'s |
| `legacy_views.c1_records` on `m01`'s five records with every molar mass doubled, `legacy` members kept | `sha256` equal to the real file's, molar masses different; D2 accepts all five |
| forged `legacy.` source through `register_record` | summary "…so the extension package that uses it is not loaded", action "Rename the extension's entry point…" |
| `validate_record`, N2 + 3 H2 → 2 NH3 on `m01` SHAs; the same with ν = −1/3, −1, 2/3 as doubles | no finding; `reaction_element_imbalance(third, H)` |
| `validate_record {"records": [a, b]}`, both with `name: ""` | two identical `record_schema_invalid(/name)`, no record named |
| two reactions with one `id` | accepted; findings carry the shared id |
| `reactions.exact(Fraction(1, 3))` | `ValueError` |
| `molar_mass_consistent` on M = 2⁵⁰ − 1, 2⁵⁰ + 1 (ν = −1, 1), then 2⁵⁰ + 1.25 | `True` (equality), `False` |
| `tests/test_t08_w2_description_reviews.py` | fails at line 33, `assert 26 == 21`, before any review is looked at |

## Findings

**Must fix**

- **M1. A YAML alias bomb holds `register_record` for minutes to hours.** `records/importers/user_file.py:88`
  (`loaded`, `records/normalize.py:106`) expands aliases; `identify` then walks the expansion. 903 characters cost
  292 s and each further line doubles it, so `MAX_FILE_TEXT` bounds nothing. The right is `draft`, which agents hold by
  default. Fix: a user file's YAML may not use aliases (C1). No legacy file uses one (seven files, zero anchors).
- **M2. `record_schema_invalid`'s explanation names the wrong place.** `application/records_service.py:471`: the
  refusal's `pointer` param collides with the error's `pointer` and is dropped, so the most common refusal renders "not
  valid at /record" (or "/file/content"). WO5b-9's recommended alternative does not repair it (measured) and mis-parses
  args that hold `, ` or `: `. Fix: the error's `pointer` continues into the record (ruling WO5b-1/9, C2).
- **M3. A record carrying a forged `legacy` member is stored.** D1: `legacy` is "written by the legacy importer only".
  `records_service.py:67` (`forged`) tests source ids only. `records/legacy_views.py:51,88` take the provider data's
  `sha256` and order from that member, so five such records give a `C1Records` that states `m01`'s file hash over other
  values. Fix: the member is reserved as the prefix is (C3).
- **M4. A file with no record returns a document its schema refuses.** `user_file.py:93` (`[]`) and `:172`
  (`components: []`) give no outcome; `register_record` then returns `{"results": []}` and writes an `allowed` audit
  row. Fix: one refused outcome (C4).

**Should fix**

- **S1.** `reserved_namespace` explains a record's refusal as an extension package's (measured text). A record variant
  of the entry (C3).
- **S2.** `records_service.py:267` reports one error per call, and no operation lists a file's errors
  (`validate_record` takes no file), so a v1 file without `defaults` costs one call per value. `register_record.md`'s
  "Use validate_record to see every error at once" is false for a file. Fix: `detail.errors` (C2).
- **S3.** `records_service.py:154,165`: without a key the resolution is taken over the whole store, every object is read
  for every page, and `limit` does not bound the response (25.8 kB at `limit: 1`). Ruling WO5b-4, C5.
- **S4.** `records_service.py:334`: errors of `records` are merged with nothing saying which record; reaction ids may
  repeat; a record `register_record` would refuse `reserved_namespace` validates clean. C6, C3.
- **S5.** `records/reactions.py:83`: `exact` refuses a `Fraction`. ADR 0062 holds ν as `[p, q]`; F2's validator, which
  D7 names as a caller, can pass 1/3 only as a double, which D7's exact balance refuses. C7.
- **S6. Verification gaps.** No test calls `validate_record` with `reactions` through any transport (`_reactions`,
  `records_service.py:341-372`, is unexercised); no test follows a `next_cursor` or lists without a key (smoke-run by
  hand only); no test pins the 4 of 4ε or the `≤` (E-F3-10 as written passes with any tolerance between the largest stated ratio, 3.6e-17, and about 10⁻¹⁰).
  C8.
- **S7.** `tests/test_t08_w2_description_reviews.py:33` still asserts 21 MCP operations (26 now). The "expected red"
  is this assertion, not the pending reviews, and it stays red after both reviews are recorded. C9.
- **S8.** `tests/test_t08_w2_inventory.py:977`: A32's vetted-file branch trusts the record's own `legacy.file_sha256`.
  A tracked copy of a vetted component with a changed value and another source passes. C10.

**Notes (no change required)**

- N1. `records_service.py:367` maps any `KeyError` of `check_reactions` to `invalid_request`. For a stored `mol`
  component `charge` and `molar_mass` are required, so the branch is unreachable; a defect would be reported as the
  caller's. Narrow it to `ValueError` when the function is next touched.
- N2. D2 step 2a makes `elements: {}` equal to absent, so a species with no atoms (an electron) leaves its reaction's
  element balance unjudged. Conservative; F2 or X18 should know it.
- N3. A zero coefficient and a cursor issued for another query are accepted. Harmless.
- N4. `MAX_FILE_TEXT` (8 MiB) is 90 times the largest legacy file (93.7 kB) and is parsed by the pure-Python YAML
  loader. Linear, not measured.
- N5. `src/openflowsheet/records/__init__.py:4` still says "The operations follow in F3-WO5b" (C12).
- N6. D7's exact element balance refuses decimal coefficients that are balanced in decimal (0.1 + 0.9, thirds). This is
  the accepted text and F2's rationals are the intended carrier; see S5, the `validate_record` description and Q-F1.

## Rulings

| Decision | Ruling | Change and where it lands |
| --- | --- | --- |
| WO5b-1 | **Kept, extended** (R-1052) | The whole call is refused and nothing is stored; `ApiError` code by catalogue kind; `detail.reason` the bare code; `detail.refusal` `{code, params}`. Added: `detail.errors`, `detail.errors_total`, the pointer rule below. `records_service.py`; C2 |
| WO5b-9 | **Kept; the alternative is rejected** (R-1052) | Params travel as `detail` members. `pointer` is the one colliding name, and it is resolved by continuation: `detail.pointer` = `/record` or `/file/content` followed by the refusal's own `pointer` param when it has one. Chain text with args is not used (measured: no effect on the rendering, wrong splits). C2 |
| WO5b-8 | **Accept** (R-1053) | `record-results.schema.json` in R-1032's form. No change |
| WO5b-4 | **Change** (R-1053) | Without a key every record is listed by SHA, and `resolution` is `{status: none, classes: []}`: resolution answers a key (D9). Only the page's records are read. Cursor encoding, `scheme` requires `key`, and `store` accepted. C5 |
| WO5b-5 | **Accept** (R-1053) | Rights shapes as built |
| WO5b-3 | **Accept** (R-1053) | `file.local_path`: D12 names it ("if the client sends one"), D13's request had no carrier |
| WO5a-1 | **Accept** (R-1054) | `<component>` of a reaction code is the stoichiometry's component key |
| WO5a-2 | **Accept** (R-1054) | A null-`elements` component leaves that reaction's element balance unjudged: the unknown composition can carry any residual, so no imbalance can be claimed |
| WO5a-3 | **Kept, one addition** (R-1054) | ν is an `int`, a finite `float` or a `fractions.Fraction`. `reactions.exact`; C7. `validate_record` refuses a repeated reaction id; C6 |
| `molar_mass_inconsistent` (WO5a, "for the design lane") | **F3 keeps `(<reaction>)`; F2 takes another name** (R-1055) | Q7.A3's check and Q3.R7's are two checks with two subjects. ADR 0062 (Proposed) registers Q3.R7's as `group_molar_mass_inconsistent(<S>, <species>)`. No accepted text changes; the edit is ADR 0062's, at its acceptance pass |
| R1-B6 | **Confirmed, tightened** | The vetting (`VETTED_RECORD_FILES`, S10 spec §18 A5-1) covers the listed components, not the Wilson block, whose basis is R-880. The branch is decided by the committed index, not by the record's own member. C10. A32 is T08's: no ADR edit |
| WO5a-4 to WO5a-9, WO5b-2, WO5b-6, WO5b-7 | **No contradiction found** | Kept as built. WO5a-5 gains C4's empty-file clause |
| (new) `legacy` member | **Reserved** (R-1056) | A submitted record with a `legacy` member whose SHA is not in the committed legacy index is `reserved_namespace(legacy)`. C3 |
| (new) YAML aliases | **Refused in a user file** (R-1057) | C1 |
| (new) report items | **`{code, params, at}`** (R-1053) | `at` is the request member the item concerns. C6 |

The refusal sentence of ADR 0019's Amendment 8 paragraph was written by the build lane in `61c740dc`, after the
acceptance (5d085f05 has no such paragraph), and cites WO5b-1. It follows this ruling (C12). D13 is unchanged.

## Question for Frank

**Q-F1. Should `validate_record` accept ADR 0062's rational coefficients, `[p, q]`, beside JSON numbers?**
- The change: D7's input form `{component key: ν}` and D13's `reactions` gain a second spelling of ν.
- The reason: D7 balances exactly. A JSON number carries 1/3 or 0.1 only as a double, so a reaction that is balanced
  in decimal is reported `reaction_element_imbalance` through the operation, while F2 documents hold `[p, q]`.
- The alternative of keeping the text: JSON numbers only; the caller scales to integers, which always exists for
  rational stoichiometry. My preference: keep the text now and add `[p, q]` with ADR 0062's acceptance, as one
  additive amendment by F2.
- Meanwhile the build lane: JSON numbers only; the description says the balances are exact (below); the Python
  function takes `Fraction` (C7).

## The five MCP descriptions (design-lane review)

The review is `reviewed` for the texts exactly as given here, after C2 to C6 make them true. Any other wording voids
it. Lengths after the edits (search, get, register, validate, assess): 1332, 862, 1327, 1358, 1263 characters (limit
1500).

- **`get_record`: accept** as served (`eaf900f8…`).
- **`search_records`: change**, three replacements.
  1. `"inchikey:...", "cas:7732-18-5"` → `"inchikey:...", "inchi:...", "cas:7732-18-5"`
  2. `Without a key every record is listed.` → `Without a key every record is listed and "resolution" is "none".`
  3. `"resolution" judges every match, not just the page` → `"resolution" judges every match of the key, not just the page`
- **`register_record`: change**, one replacement. From `Every record is validated first;` up to and including
  `is refused reserved_namespace.` becomes:
  > Every record is validated first; if one is refused the call is refused and nothing is stored: detail.errors lists every error ({"record_index" in a file, "code", "params"}), detail.refusal is the first and detail.pointer its place in the request. The source prefix "legacy." and the member "legacy" are reserved for the built-in legacy records: another record using one is refused reserved_namespace. A YAML file may not use aliases.
- **`validate_record`: change**, four replacements.
  1. `products positive)` → `products positive, ids distinct)`
  2. `each error and finding a {"code", "params"}, and the SHA` → `each error and finding a {"code", "params", "at"}, "at" the request member it concerns ("/record", "/records/1", "/reactions/0"), and the SHA`
  3. After `which records from different atomic-weight tables can give).` insert: ` The balances are exact: scale a reaction to integer coefficients, since a decimal such as 0.1 or 0.333 is not exact in binary and reports an imbalance.`
  4. `a stoichiometry key missing from "components" is refused invalid_request.` → `a stoichiometry key missing from "components", or a repeated reaction id, is refused invalid_request.`
- **`assess_rights`: change**, one replacement (the old sentence leaves open whether layer or scope ranks first).
  `The register is append-only and the latest row decides: a record row before a whole-source row, the project before the repository.` becomes:
  > The register is append-only. The effective assessment is the latest row of the first of these that has one: this project's rows for the record, this project's whole-source rows, the repository's rows for the record, the repository's whole-source rows; otherwise "unknown".

## Build-lane changes

Each is one commit. Expectations come from this file and the ADR, not from the code's output.

- **C1 (M1, R-1057).** The user-file adapter's YAML parse refuses an alias (and so a merge key): the text is one
  refused outcome `record_schema_invalid("")`. The loader may refuse it for every caller if
  `records_legacy_index.py --check` and the fixtures stay clean. *Acceptance:* the 24-alias file of this review
  (`aN: &aN [*aN-1, *aN-1]`, N = 1…23, then a valid record) is refused `invalid_request`, reason
  `record_schema_invalid`, in under 1 s, for both YAML formats; a v2 YAML file without aliases still round-trips to its
  SHA; the legacy index is unchanged.
- **C2 (M2, S2, R-1052).** In `RecordsService`: (a) `detail.pointer` = `/record` or `/file/content`, followed by the
  first refusal's `pointer` param when it has one; `detail.refusal.params` keeps the bare value. (b) `detail.errors` =
  every error of every record of the submission, `[{record_index (file form only), code, params}]`, records in order,
  per record `reserved_namespace` first when it applies and then D7's errors in their sorted order, at most 200, with
  `detail.errors_total` the full count. `reason`, `refusal`, `record_index` and the `ApiError` code stay those of the
  first. *Acceptance:* `{"record": {…, "name": ""}}` gives `detail.pointer == "/record/name"`,
  `detail.refusal.params.pointer == "/name"` and the explanation summary "The record is not valid at /record/name.";
  `m01`'s YAML as `component-record-v1-yaml` without `defaults` gives `errors_total == 30` (E-F3-12's six
  `M01_VALUES` for each of 5 components), every item `provenance_invalid`, `record_index` 0 to 4; a file of two records
  whose second has two errors lists exactly those two with `record_index: 1`; MSG-G3 stays green.
- **C3 (M3, S1, R-1056).** (a) `forged` also holds for a record with a `legacy` member whose SHA is not in the
  committed index. (b) `validate_record` adds `reserved_namespace(legacy)` to `errors` for a `record` or inline record
  that `register_record` would refuse so, and its `record_sha256` is then `null`. (c) `reserved_namespace` gains a
  record variant, selected by a param only the records path sends; suggested text: summary "The prefix legacy. and the
  member legacy are reserved for the records that come with OpenFlowsheet, so the record is not stored."; why "A source
  id that starts with legacy., and the member legacy, mark a record imported from a file that comes with OpenFlowsheet.
  A rights assessment of such a source holds for every record that carries it, so only the importer's own records,
  recognised by their SHA, may use them."; action "Give the source an id of your own, for example one that starts with
  user., and remove the legacy member if the record has one." *Acceptance:* `m01`'s H2 with one value changed, its
  source renamed `user.copy` and its `legacy` member kept is refused `reserved_namespace(legacy)` and nothing is
  stored; the unchanged record still copies (`created: true`, store `project`); E-F3-12's v2 round trip still passes;
  the extension case of ADR 0060 renders byte-identically to today.
- **C4 (M4).** `import_user_file` never returns an empty tuple: a v2 file holding an empty list is one refused outcome
  `record_schema_invalid("")`, a v1 file with `components: []` one at `/components`. *Acceptance:* both are
  `invalid_request` with `detail.pointer` `/file/content` and `/file/content/components`, and no `allowed` audit row.
- **C5 (S3, R-1053).** `search_records` without `key`: `resolution == {"status": "none", "classes": []}`, and only the
  page's records are read. *Acceptance (source checkout):* `{"limit": 1}` on a fresh project returns one item, `next_cursor` set and that
  resolution; following `next_cursor` at `limit: 50` yields the 149 legacy SHAs once each, ascending, in 3 pages, the
  last with `next_cursor: null`; with `key: "water"` the resolution is unchanged from today.
- **C6 (S4, R-1053, R-1054).** `RecordValidationReport`'s items are `{code, params, at}`, `at` = `/record`,
  `/records/<i>` or `/reactions/<i>` (schema: a `$def` of the report's own; `record_finding` is unchanged elsewhere),
  each list sorted by code, params, then `at`. A repeated reaction `id` is `invalid_request` at `/reactions/<i>/id`
  (the second). *Acceptance:* two inline records
  with `name: ""` give two errors with `at` `/records/0` and `/records/1`; a reaction finding carries its
  `/reactions/<i>`; `SNAPSHOT_F3`'s `validate_record` digest is re-taken and no other snapshot moves.
- **C7 (S5, R-1054).** `reactions.exact` accepts `fractions.Fraction`. *Acceptance:* ν = `Fraction(-1, 3)`,
  `Fraction(-1)`, `Fraction(2, 3)` on `m01`'s N2, H2, NH3 gives `((), ())`; the same three as `float` gives
  `reaction_element_imbalance`.
- **C8 (S6).** Tests. (a) E-F3-11's scenario gains `validate_record` with `components` and `reactions` on legacy SHAs:
  ammonia on `m01` (no finding), water over `l01`'s H2 and O2 and `s10`'s H2O (`molar_mass_inconsistent`, no error),
  ammonia with H2 at −4 (`reaction_element_imbalance(…, H)`), a stoichiometry key outside `components` and a
  `parameter_set` SHA as a component (`invalid_request` at the pointers of `_reactions`), identical on the four
  transports. (b) C5's paging acceptance and a cursor of other text (`invalid_request` at `/cursor`). (c) The 4ε
  boundary on `molar_mass_consistent`: `[(−1, 2⁵⁰ − 1), (1, 2⁵⁰ + 1)]` is `True` (|Σ| = 2 = 4ε·2⁵¹ exactly), and with
  `2⁵⁰ + 1.25` it is `False`.
- **C9 (S7).** `tests/test_t08_w2_description_reviews.py:33`: 26, the comment naming ADR 0061 D13's five.
  *Acceptance:* the test then fails only with the open-items list of the F3 texts.
- **C10 (S8, R1-B6).** A32's vetted-file branch: a component whose record SHA the committed legacy index lists under a
  vetted file. *Acceptance:* `m01`'s H2 with one value changed and source `user.copy`, at `benchmarks/x/h2.json` with
  an empty register, gives a line; the unchanged record gives none; the tree passes.
- **C11.** The four description edits above, after C2 to C6. `REVIEW.json` records the design-lane review
  (`reviewer`, 2026-11-18, this file) at the new hashes and Frank's when he gives it; D_10, R-1051's digest,
  `F3_FILE_SHA256` and the snapshots are re-taken (R-1051's "Watch for").
- **C12.** Documents. ADR 0019 Amendment 8, the `invalid_request` parenthesis: "a record or user file D7 or D11
  refuses: the first refusal's code in `detail.reason` and its `{code, params}` in `detail.refusal`, every error in
  `detail.errors`, `detail.pointer` the request location continued by the refusal's own pointer (R-1052)"; the schema
  bullet names the report's item `$def`. `docs/F3_DECISIONS.md`: this round's entry. `records/__init__.py:4`.

## Not examined

`application/cli.py`'s `records` commands and `contract.py` beyond their signatures; the rename diff of
`importers/legacy.py` (the build log reports the index `--check` clean); the T07, T08, M07a surface tests and their
digests; the HTTP and MCP bindings; `records/store.py` and `stack.py` beyond the calls WO5b makes (round 1 covered
them). F0, the battery, mypy and codehealth were not re-run.
