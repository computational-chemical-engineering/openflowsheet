# F2 review (ADR 0062, material model), WO1 to WO7, with the F2 ruling batch

Design lane, `reviewer`, 2026-11-27. Brief: `docs/briefs/F2-reviewer.md`. Branch `wp/F2` at `39244e80` (diff
`d00f659a...39244e80`). Read against ADR 0062 (D1 to D13, D12 as replaced by F2-R1), `docs/F2_DECISIONS.md` and
`evidence/F2/a3081770…/manifest.json`. Runs (logs under `~/.cache/line06/f2rev/`): `tests/test_f2_*.py` 556 passed,
1 deselected; `tests/test_v03_semantic_roles.py -k 'a29 or a31'` 3 failed, 2 passed (the known red, item 1); probe
scripts for the findings below (scratch, not committed).

## Verdict

**Not ready to merge; ready after one fix round.** The core is sound: lowering is a field map whose output matches
the v1 schema member for member (instances, connections, specifications and the top-level fields compared
sub-schema by sub-schema), every D12 refusal is reachable and tested, the basis code decides in exact rational
arithmetic, the exact cache keys are full-precision and unquantized, and E-F2-3's run half compares every artifact
hash plus the `solution-state.json` bytes, so it would catch a dropped field in any corpus revision. One D8 route
still reads the stored v2 document (M1), the V03 tests are red (M2), and nine should-fix items, mostly the
ruling batch's, belong in the same round.

## Findings

### Must fix

**M1. Revision continuation reads the ancestor's stored v2 document unlowered, which breaks D8.**
`application/revision_continuation.py:426-429` (`find_source`) passes `store.get_revision(...).as_document()` raw to
`assemble`. The target there is the lowered document (`jobs/runner.py:661`, then `_continuation` at `:774`). Scenario:
a v2 revision whose lineage ancestor is a v2 revision with a verified solve, solved on `revision_eo` under a policy
whose edge 3 continues revisions. A2 binds (the binder lowers), but A3 compares a v2 source with a v1 target:
`not_continuable(raise_v1(d), lowered_document(raise_v1(d)))` is `not_continuable(component_set)`, measured on
`SYN-001-T06-NET02`, while the v1 twin gives `None`. So the v2 run is `rejected` where the v1 run continues, and
`solve-path.json`'s `revision_continuation.source_document` (`:178-182`) holds the v2 document. Both break D8 ("a
lowered run is a v1 run in every artifact"). E-F2-3 does not see it because F0's runs have no ancestor.
*Fix:* in `find_source`, use `lowered_document(revision.as_document())`. When that raises `RevisionError`, keep the
raw document, so that A2 refuses `source_binding(...)` as today (such an ancestor has no v1 twin). *Test:* a
two-revision lineage of a continuation case, built once from v1 documents and once from their raised forms, gives
byte-identical `solve-path.json` and an equal `artifact_r0_sha256`.

**M2. `tests/test_v03_semantic_roles.py` a29, a31_a and a31_b fail at the head.** Ruled in item 1 below: the tests
change and the code stays.

### Should fix

**S1. `MaterialLayout.temperature_substream` encodes wrong physics when several substreams flow (WO4-15).**
`material/layout.py:445-459` returns `mixed` whenever it flows, on the docstring's premise that "substreams share ĥ".
They do not. D3 carries one `h` per connection, the mass-weighted mean, so with `mixed` and `solid` both flowing T
solves ṁĥ = Σ_s ṁ_s ĥ_s(T, P) jointly (Q8.R6: "fixed by the flowing substreams"). `tests/test_f2_revision_v2.py:471`
pins `(3.0, 2.0) -> "liq"`, i.e. T = ĥ/4180, which the stub's own energy balance contradicts. *Fix:* replace it with
`thermal_substreams(x, c) -> tuple[str, ...]`, the flowing substreams in instance order, `()` when dormant. Q8.A4 is
the singleton case. Change the test's both-flowing row to expect `("liq", "cryst")`.

**S2. `one_definition_rules` compares definition ids, not definitions (Q-WO5-b, a defect).** At
`revision_v2/validate.py:470`, two ids with equal bodies are refused `attribute_grid_mismatch` although D3 makes the
SHA the identity. *Fix:* treat ends as equal when their normalised bodies are equal (`normalise_instance`, or
`definition_sha256`). Add the Q6.A4 case with two ids admitted.

**S3. D11's `h_mass` rule is applied per `h_mass` definition, not revision-wide (item 2).** See the ruling below. The
changes go in `validate.py:242-248` and `:436-449`, the crystallizer fixture and new refusal fixtures.

**S4. A template's descriptor hashes the whole grammar file (WO2-7).** `registry/builtin/material.json` gives all
four templates `instance_schema.sha256` = the raw bytes of `connection-definition.schema.json` (`41bbfca0…`). Every
`mat-v1` `definition_sha256` therefore moves when anything in that file changes: a `description`, or `heat_v1`'s
grammar. That identity becomes load-bearing in v2-compiled fingerprints (D8) and is frozen by D13, so it cannot be
fixed after 0.6. *Fix:* `sha256` = `document_sha256` of the sub-schema at `pointer` together with the `$defs` it
reaches by `$ref`, with `description` members removed. Regenerate with `scripts/registry_builtin.py --write`, then
re-pin the template SHAs, `tables.sha256` and E-F1-5's `registry_sha256`. No F0 check and no served digest reads them
(WO2's measurement).

**S5. Catalogue prose and kind (item 4).** The exact edits are in the item 4 ruling below.

**S6. One fault gives two refusals for a v2 component without a legacy record.** `application/validation.py`
`revision_context` (`:500-520`) leaves such components out, so `revision_v2/validate.py:177-179` reports
`component_unknown(c)` beside the lowering's `construct_unavailable(component:c, F4)`. Measured on `legacy_only.yaml`
through `validate`. The first refusal is wrong: the component is declared with a record, which this build cannot
serve. This breaks WO4-6's "one fault, one refusal" in `validate` and `check_admission` for every user record.
*Fix:* in `_v2_stage` and `_lowered_draft` (one shared helper), drop `component_unknown(c)` when
`construct_unavailable(component:c, F4)` is present. Add a test.

**S7. F2-R1's CoolProp run half is not built.** R1-1 asked for one CoolProp one-fluid `s07` revision with the
library half always and the run half under the CoolProp extra. Only the library half exists
(`tests/test_f2_lowering.py:221-236`). *Fix:* add the run-half case to `tests/test_f2_amendment9.py` under the
CoolProp marker (CI runs it).

**S8. A lowering that dropped `initialization_hint` would pass every test.** None of the 59 corpus revisions carries
it, and no lowering test sets it, yet it enters `content_hash` and `revision.json`. *Fix:* a test that sets
`initialization_hint` on a corpus connection, raises it and lowers it to the same canonical bytes, and also checks
the raised `content_hash` round trip with the hint present.

**S9. The evidence manifest reports partial exits as `pass`.** E-F2-9 covers 19 of 20 codes
(`state_degenerate_in_definition` is not built, WO4-9). E-F2-4's Q6.A2 registration half is not testable as written
(Q-WO5-a). E-F2-8's Q7.A1 map half waits for F4. The limitations also still describe WO7-3 as an xfail. *Fix:* the
fix round's manifest records each of these as partial, giving the reason and the package that closes it (CLAUDE.md:
no narrowed denominators), and drops the stale WO7-3 sentence.

### Notes

- **N1.** `component_basis` (`models/revision_flowsheet.py:212`) silently returns SYN-001's basis for a raw v2
  document, because it has no `record_source`. Every caller lowers first today. A one-line guard (`RevisionError`
  for `schema_version` 2) would turn a future silent mis-selection into a typed error. Taken into the work order.
- **N2.** Lowering does not check its output against the v1 schema. A v2 document listing one component twice passes
  the v2 schema (no `uniqueItems` on the objects) and lowers to `components: [A, B, C, A]`. That is safe today:
  the binder refuses `components_unsupported` and `validate` refuses `id_duplicate`. Consider `uniqueItems` on
  `component_set.components` the next time the v2 schema moves.
- **N3.** A v2 document that is schema-valid and rule-valid but does not lower is `INVALID` at `SCHEMA-01`. Amendment
  9 says so, and the stage enum has no better place. Revisit when F6 lets such documents compile.
- **N4.** D8's exception ("except the run manifest's revision reference") is empty in this build. `RunManifest` has
  no revision field, the bundle is the v1 run's byte for byte, and the v2 reference is in `RunResult` (WO6b-7). That
  is consistent with D8. The ADR may say so at its next edit; no card is needed.
- **N5.** `lowered_document` re-parses the v2 document (JSON-schema validation included) at each reader, about six
  times per run. That is negligible beside a solve. Cache by `id(document)` only if a profile ever shows it.
- **N6.** `molar_volume` keeps its pre-F2 exclusive lower bound of 0.0, while the new volume kinds take `null` (WO1-1).
  The new kinds are right, and the old bound is out of F2's scope.
- **N7.** Q-WO5-c (a flowing stream whose ṁ underflows to 0.0) goes to ADR-F6. The probe's `ProbeUnresolvedError` is
  the right holding behaviour.

## The ruling batch

**1. V03 A29/A31 against D12: the tests change, the code stays.** A29 and A31 protect ADR 0054's enum and the V03
spec's claim that the role is descriptive. The v1 schema's enum is A29's subject, and A31 asserts that no `src/` code
gives the role meaning. D12 (c), as amended by F2-R1, makes lowering refuse a role outside v1's 14. That is the v2
counterpart of the v1 enum, a vocabulary check like the one A29's control exercises, not a reading of the role's
meaning. The exact changes:
- *a29* keeps the whole corpus. A v1 document is judged as now (`validate`'s `SCHEMA-01`). A `schema_version` 2
  document is judged by `schema_check.schema_errors("process-revision-v2.schema.json", document) == []`. The reason,
  stated in the test docstring: for a v2 document, Amendment 9 puts F2's rules and the lowering, both evaluated
  against this build's stores, into `SCHEMA-01`. The v2 fixtures are valid against
  `tests/fixtures/schemas/v2/context.yaml`, not those stores, and A29's subject is the role enum of the document's own
  schema (ADR 0002 D7.5). Add control `test_a29_control_v2_role_outside_the_enum_fails`: crystallizer with one role
  set to `purge_sink` fails the v2 schema.
- *a31_a*: `naming == ["src/openflowsheet/revision_v2/lower.py"]`, and an AST check that every `"semantic_role"`
  constant in that file lies inside `_unclassified`, whose only use of the role is the `not in V1_ROLES` test and the
  refusal's construct string. Reason: D12 (c), F2-R1.
- *a31_b* compares documents whose roles all lie in v1's 14 (`lower.V1_ROLES`, pinned to the v1 enum by
  `test_f2_lowering.py:365`). Raised v2 documents count, which strengthens the check. Reason: D12 (c) refuses the other
  roles at admission, as the v1 enum does, and A29 covers that. Add control `test_a31_b_control_a_d11_role_moves_only_its_refusal`:
  crystallizer and its all-`other` copy give equal outcomes once the `construct_unavailable(semantic_role:<role>, F6)`
  entries are removed from the first one's hint.

**2. R1 open item (1): `h_mass` revision-wide; change `validate`.** D11 sets the coordinate once per revision ("every
material definition has the revision's coordinate") and lists what each coordinate admits: "`h_mass` admits `std.*`
units only … `T` admits `nTP-v1`, legacy and `std.*` units". `nTP-v1`'s coordinate is T (D3). The valid crystallizer
fixture is an `h_mass` revision with two legacy units (`lfeed` `syn001.feed_source`, `lsink` `syn001.product_sink`)
joined by an `nTP-v1` connection `S2`, and D11 refuses that. Per-definition checking admits it. Admitting now and
refusing later would move an accepted document, while the reverse moves no byte (R1-2's rule). So, in an `h_mass`
revision:
- every instance whose model id does not start with `std.` is refused `unit_coordinate_unsupported(<instance>, h_mass)`,
  once per instance, whatever it connects to;
- every material connection with `definition: nTP-v1` is refused `thermal_coordinate_mismatch(nTP-v1)`.

The per-end check at `:436-449` is subsumed. `crystallizer.yaml` drops `lfeed`, `lsink` and `S2`. E-F2-2 does not
need `nTP-v1` in that fixture, and `legacy_only.yaml` covers `nTP-v1`. Add two refusal fixtures (E-F2-9). D11's text
already says this, so no ADR change is required. The orchestrator may add the clarifying clause "(revision-wide:
every instance `std.*`, no `nTP-v1` connection, whose coordinate is `T`)" with the D2 and D12 edits under the same card.
R1 open item (3) keeps its default; I found no defect.

**3. `check_admission.md`: approved as proposed.** The only edit is `<schema_version 1 document>` →
`<schema_version 1 or 2 document>`, which makes the file 1,493 characters. That text, at its new hash, is reviewed
by this design-lane review. The fix round registers the served-digest move: a new `F2_SERVED_SHA256`; c_11's
`D_11` in `scripts/m07a_rc.py`; R-1072's evidence row; and `REVIEW.json`'s `sha256` and `characters`, with the
design-lane review `reviewed` citing this file and the human review back to `pending`. That human review is the
user's (REVIEW.json: "no agent marks a review done").

**4. Catalogue prose (WO7-1, WO7-2).** These entries misstate their meaning; each gets the edit shown:
- `solid_role_conflict`. The why says a confined component "cannot also be a free species of a mixed substream". That
  inverts D3: a confined component *is* a `mixed` component (Q8.R7) and may not sit in a `solid` substream. Why:
  "A component sits in one substream, or in one `mixed` and one `solid` substream (dissolved and particulate).
  A component the property method confines to a phase model, or forms as an equilibrium solid, is carried in
  `mixed`, where equilibrium decides its phase: it cannot also sit in a `solid` substream, and it takes no attribute."
  Action: drop "or in one mixed and one solid substream" for the confined case. The action becomes "Place {component}
  in one substream (or one `mixed` plus one `solid` if it is not confined), and remove its attributes in `mixed`."
- `species_basis_redundant`. The rank in question is that of the group-content matrix A alone (`basis.py:100`, D3),
  not of A together with the reactions. Why: "The group contents must form a matrix of full row rank: when one group
  is a combination of the others, …".
- `amount_basis_mismatch`. "a conventional one in moles" is wrong: `mixed` may hold `segment_mol` (and `kg`)
  components. Why: "A `nonconventional` substream holds only components counted in kilograms (amount basis `kg`), and
  a specification of a molar kind cannot target an amount counted in kilograms (Q7.R5)."
- `thermal_coordinate_mismatch`. "(the enthalpy per mole or per mass)" is wrong: the coordinates are `h_mass` (the
  specific enthalpy) and `T`. Why: "The document declares one thermal coordinate (`h_mass` or `T`) and every
  material definition uses it; an `nTP-v1` connection's coordinate is `T`."
- `unit_coordinate_unsupported`. The action's "the molar thermal coordinate" does not exist. Action: "Use the thermal
  coordinate `T`, or replace {instance} by a standard (`std.*`) unit." Why, per item 2: "In a revision whose thermal
  coordinate is `h_mass`, every unit must be a standard (`std.*`) unit."
- `construct_unavailable`. The why says "a convention other than the elemental one" is unavailable. The lowering does
  the reverse in 0.6: it refuses every convention but the legacy provider's native one, `ELEMENTAL-ref-v1` included.
  Why: "(a convention other than the legacy provider's native one, property methods beyond that provider, a
  derived target, an energy or signal connection, …)". Kind: **`not_supported`, not `input`**, with
  `gap: {limitation: null, capability: "the construct named, which foundation {foundation} provides"}` (as
  `model_unsupported`). This is a capability the build lacks, not a fault in the input.
- `species_basis_not_monotone` (notice). The why states the converse implication. Q3.R1 (iii) (WO2-1) concerns
  non-negative, electroneutral *species* amounts giving non-negative *group* amounts. Why: "A conserved basis is
  monotone when each group's content can be made non-negative by adding a multiple of the species charges; then a
  physical, electroneutral feed always has non-negative group amounts. With a basis that is not, a physical feed can
  have a negative group amount, which is refused as an invalid state (`group_amount_negative`). The document is
  accepted; this limitation is recorded." Action: "… choose group contents that are non-negative (up to a multiple
  of the charges)."
- Minor: `signal_kind_mismatch`'s why omits an instance port as a source ("Its source (a port or a probe)").
  `species_basis_incompatible`'s action becomes "the groups must fix every quantity the fast reactions conserve
  (elements and charge among them)". `molar_mass_inconsistent`'s species clause becomes "… equal the content-weighted
  sum of its groups' molar masses plus the charge term (Q3.R7) …".

The other entries read correctly against their emit sites: `group_amount_negative`, `feed_not_electroneutral`,
`attribute_redundant`, `attribute_grid_mismatch` (given S2), `attribute_on_zero_parent`, `definition_incompatible`,
`parameter_not_manipulable`, `parameter_binding_conflict`, `quantity_kind_mismatch`. The `molar_mass_inconsistent`
reconciliation with optional params on both emitters is right.

**5. Build decisions.**
- WO1-4 (STOP: `PropertyRequest` not widened): **keep it unwidened; amend D2.** Widening lies about the legacy providers
  (they read `.is_dormant`, which `EvaluationState` lacks), and a mypy override would relax a check. D2's
  "`PropertyRequest.state: StreamState | EvaluationState`; `PropertyRequest.phase: Phase | PhaseId`" becomes
  "**[departure]** `PropertyRequest` is not widened (F2 WO1-4: 51 strict-typing errors in the seven frozen legacy
  providers); a v2 evaluation request is ADR-F4's type; `thermo/cache.py` keys both state forms." D13's "D2's
  types and annotations" then freezes the unwidened form. This is ADR text, so it goes on the card.
- WO1-1 (kind lower bounds): keep (N6).
- WO1-9 (formation kinds follow the basis): confirmed. The kinds come from D1's Use column and are dimensionally
  right.
- `M = 1` for `kg` in the reaction check: keep it unchanged (a `kg` reaction stays refused). An integer
  kg-per-mol-extent stoichiometry has no meaning. A typed code in place of `invalid_request` is F3's or F4's to add.
- WO2-1 (Q3.R1 (iii) with a rational λ_g per row): keep. By Farkas, A_g n ≥ 0 for every n ≥ 0 with zᵀn = 0 holds
  exactly when some real λ gives A_g + λz ≥ 0. The feasible interval has rational ends, so a rational λ suffices,
  while an integer λ would be stricter than the property.
- WO2-7 (template payload): **change** (S4).
- WO3-6 (layout refusals): keep.
- WO4-7 (D10 strict): keep. Refusing now and admitting Q7.R5's conversion later (F4) moves no byte.
- WO4-8 (solid roles; `solid_role_conflict` for Q8.A6): keep, with the prose of item 4.
- WO4-9 (`state_degenerate_in_definition` not built): keep, since it needs a property evaluation at a T state point
  (ADR-F5/F6). E-F2-9 is reported as 19 of 20 (S9) and stated on the card.
- WO4-15 (Q8.A4's T rule): **change** (S1).
- Q-WO5-a: E-F2-4 records Q6.A2's registration half as untestable on D5's payload. The deciding payload field comes
  with the first kind that needs it (X19/X20, ADR 0062 risk 2). The substitute tests stand.
- Q-WO5-b: a defect, so **fix** (S2).
- Q-WO5-c: to ADR-F6 (N7).
- WO5-1 (probe scopes swapped to Q6's names): keep.
- WO6a-4 (`definition_sha256` exact): keep (R1-3).
- WO6b-7 (the run's revision reference is `RunResult`): keep (N4).
- WO6c-2 (`thermal_coordinate` checked unconditionally): keep. D12 gates only `convention`, `property_methods` and
  `parameter_sets` on one file.

## Fix-round work order F2-WO8 (one Opus engineer, `wp/F2`, rules `docs/LINE06_RULES.md`)

1. M1: lower the ancestor in `find_source`, with the lineage identity test.
2. Item 1: the V03 a29, a31_a and a31_b changes and their two controls. `tests/test_v03_semantic_roles.py` goes
   green (22 passed: the 20 tests plus the two controls).
3. Item 2 and S3: the revision-wide `h_mass` rules in `validate.py`, the crystallizer fixture split, and two refusal
   fixtures. `test_f2_revision_v2.py` and the lowering tests then reflect the fixture change.
4. S1: `thermal_substreams` and its test.
5. S2: the one-definition rule by normalised body, with a two-id equal-body case admitted.
6. S6: one fault, one refusal in `_v2_stage` and `_lowered_draft`, with a test on `legacy_only.yaml` through
   `validate`.
7. S4: the template payload hash over the sub-schema closure. Regenerate and re-pin, and log the moved digests.
8. Item 4 and S5: the catalogue edits and `construct_unavailable`'s kind and gap. Re-emit with
   `scripts/doc_pages.py`, re-pin the catalogue digest (WO7's two fixtures) and run the MSG suites.
9. Item 3: the `check_admission.md` text, plus the served-digest registration (`F2_SERVED_SHA256`, c_11, R-1072
   evidence, `REVIEW.json`), done as WO2b/WO3 did.
10. S7 and S8: the CoolProp run half under its marker, and the `initialization_hint` lowering test.
11. N1: the `component_basis` guard for `schema_version` 2, with a test.
12. Close: a `DECISION WO8-*` per item in `docs/F2_DECISIONS.md`, and a new evidence manifest with the partial exits
    of S9. Acceptance: `tests/test_f2_*.py`, `tests/test_v03_semantic_roles.py`, the surface suites
    (`test_t07_*`, `test_t08_w2_*`, `test_m07a_surface_chain.py`), the MSG suites, the nlp tests through
    `scripts/m03_nlp_check.sh`, F0 PASS with the pinned counts, and ruff, format and mypy clean. A move of F0 or of any
    served digest other than item 9's is a stop.

For the orchestrator, not the engineer: the ADR 0062 text edits (D12 per F2-R1, D2 per WO1-4, and optionally item 2's
clarifying clause), applied before the card.

## What needs the user

- **The ADR 0062 acceptance card**, one line: "ADR 0062 accepted as corrected before acceptance: D12's lowering
  criterion (F2-R1: permuted and subset legacy component sets lower, a legacy file's parameter sets are stated,
  preview and new-role fields are refused, thermal coordinate T); D2 no longer widens `PropertyRequest` (a v2 request
  type is ADR-F4's); D11's `h_mass` rule applies revision-wide; E-F2-9's `state_degenerate_in_definition` and Q6.A2's
  registration half wait for F5/F6 and the first polymer kinds."
- **The human review of the new `check_admission.md` text** (item 3). Its `REVIEW.json` human status returns to
  `pending`.

## Not examined

`material/phase_id.py`, `material/vid.py` and `revision_v2/parse.py` in detail; the E-F2-5, E-F2-6 and E-F2-7 test
bodies beyond their claims; `basis.py` outside group masses, group amounts and the rank flag;
`scripts/registry_builtin.py` beyond the template payload; the X04 display-kind re-emission (WO1-2). No CI run was
judged.
