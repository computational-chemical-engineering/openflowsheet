# S11 build decisions — WO-0 and track A

Build-lane choices the design note (`docs/derivations/S11-design.md`, ADR 0050) left to the engineer, for WO-0 (the
identity gate) and track A (`wp/S11-a`: A1–A5). One line each, as
`DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.`; each is isolated and revertible. Measurements go
in the run log below.

## WO-0: the identity gate (§5, §6.2 G1)

- DECISION: how are §8.3's entries keyed? → `AMENDED_TESTS` holds node-id prefixes: the test functions that span §8.3's
  lines at the base (or, where the lines hold a constant — `LIBRARY_ONLY_PROVIDERS`, `HARVEST_SIZE` — the tests that
  read it; for `test_l01_*` the two tests that read `SELECTABLE_BASES`; for `test_t08_b50` the two that read
  `list_models`), and the whole file where §8.3 names only a file (`test_t08_w2_unsupported.py`,
  `test_t07_w5c_signatures.py`, `test_t08_w2_edge_identity.py`). 217 of the base's 53856 family-C keys fall under it.
  Alternative: whole files throughout. Reversible by: editing the tuple in `scripts/s11_identity.py`.
- DECISION: do amended tests escape the "no base-only keys" rule too? → yes: an amended test may be renamed by its WO
  (e.g. `test_builders_hold_the_thirteen_models_of_the_table`, `test_b10_the_model_is_the_thirteenth_builder_…`), which
  makes its keys base-only. Alternative: exempt them from the equality rule only. Reversible by: dropping
  `if not amended(key)` from `base_only` in `_verdict_c`.
- DECISION: how do families A and B run? → this script loads the `s10c_identity.py` beside it and applies its
  `column_digests` and `ph_digests` in both trees (one code, each tree's `s08_identity` and tests), so A+B are exactly
  S10-C's 858 keys; the S08 and S10-C lines (S11.A23) and the older `test_*identity*` tests run on their own, not
  inside `s11_identity.py`. Alternative: run each tree's own `s10c_identity.py --digests`. Reversible by: `_s10c`.
- DECISION: family C's document SHA-256 on a clock-named revision → the digest hashes the document with the top-level
  `revision_id` and `parent_revision` set to one marker (the binder reads neither), and a binding's `revision_sha256`
  enters as "equals the raw document's `document_sha256`". Measured: the first run on the unmodified tree (`a4425319`)
  gave `FAIL n=54497` with 25 keys changed, all in three `tests/test_t07_r6_replays.py` tests whose `_commit` names
  revisions `f"…-{time.monotonic_ns()}"`. Alternative: list those tests as not judged, or make the test's ids
  deterministic (a file outside WO-0). Reversible by: reverting the commit that adds `VOLATILE` to
  `scripts/s11_identity_recorder.py`.

## Track A: A1 registry and selection (§4.1–§4.3)

- DECISION: `elemental_verification` of the generated CoolProp records (null formula) → `NOT_APPLICABLE`, because
  `component-record.schema.json`'s `if/then` refuses `PENDING` with `elemental_composition: null` (the fallback §4.1
  names). Alternative: `PENDING` with a schema change. Reversible by: one line in `s11_coolprop_records.py`, re-emit.
- DECISION: does generating `benchmarks/s07/components.yaml` need CoolProp? → no: every value §4.1 names (`id`, `name`,
  `cas`, `M`, `bibtex_eos`) is in the committed `_coolprop_heos_fluids.FLUIDS`, so the generator and its `--check`
  import nothing from CoolProp and run in `.venv`; no scratch venv was used. Alternative: re-read CoolProp 8.0.0 in a
  scratch venv. Reversible by: n/a (no numerics read).
- DECISION: what does DIM-01 use when `component_basis` raises (a CoolProp revision with ≠ 1 admitted fluid)? → an
  empty molar-mass table (a mass-basis value is then DIM-01's unconvertible FAIL beside COMP-02's FAIL); no existing
  revision raises, so every existing report is unchanged (measured: the 56 T07+C1 corpus reports hash to `e6c92d90…`
  at `8c34ecb0` and on the branch). Alternative: the admitted rows' `M` for the declared ids. Reversible by: the
  `except RevisionError` branch in `validation.validate`.
- DECISION: hint texts §4.1/§4.3 leave open → excluded fluid: `'<id>' is excluded from coolprop-heos-v1: <name>:
  <reason>` (the provider constructor's wording); Wilson records absent: `<code>: the records <path> are
  repository-only until Frank's Q-F3 (R-706)`; premises: `<P>: <component> min <value .4g> at T = <T .4g> K`.
  Alternative: other wording. Reversible by: the strings in `revision_flowsheet._coolprop_selected` and
  `revision_binding._wilson_refusal` / `wilson_premises.Minimum.hint`.
- DECISION: S11.A09 at revision level (a bound CoolProp/Wilson revision gives `basis_unavailable`) → tested at A2, where
  the routing models first bind on those bases; A1 tests `provider_for` directly (the binder refuses
  `model_unsupported` before it constructs a provider). Alternative: a monkeypatched `MODEL_BASES` in A1. Reversible
  by: n/a (test placement).
- DECISION: which bases does L01's measurement binding (`benchmarks/l01/retake.py`) carry now that the installed
  binder has 127? → the bases whose providers W27 v1/v2 have provider lines for (`syn001`, `pr-c1-v1`), then
  `pr-lib-v1`, so W27v2-A23's output is unchanged; with all 127 the v2 snapshot refuses `iapws95-v1` (W27-R63) and the
  re-take cannot run. Alternative: carry all 127 and move the re-take to W27 v3. Reversible by: reverting this commit.
- DECISION: W27's tests that snapshot the installed binder (`test_m06_w27_coverage.py`:
  `test_snapshot_of_this_build_is_todays_registry`, `test_each_route_binds_a_revision_with_its_component_set`,
  `test_coverage_document_and_g14`, `test_committed_coverage_json_is_g14_and_this_builds_classification`;
  `test_l01_retake.py::test_a27_2_…`) fail at A1, because v1/v2 have no provider line for S11's bases (D9's own
  statement) and §8.3 does not list them → they read the build through `v2_binder()` (the installed tables with
  `SELECTABLE_BASES` restricted to the bases `snapshot.PROVIDER_LINES` covers), and a new test pins D9's refusal of
  the unrestricted build. Their routes and bind calls are the base's, so no family-C key moves and `AMENDED_TESTS`
  is unchanged. **Escalated** (§4.10 says "all existing W27 tests pass unchanged"; that cannot hold once A1 lands).
  Alternative: list them in `AMENDED_TESTS` and re-point them at v3 in A4. Reversible by: reverting this commit.
- OPEN (escalated, not decided): `tests/test_t08_w2_inventory.py::test_a32_every_component_record_is_synthetic_or_a_
  vetted_real_record_with_rights` (T08.A32, R-158/R-529/R-722) refuses the two new record files: their records are
  `synthetic: false` but the files are not in `VETTED_RECORD_FILES` (no crosscheck JSON, no InChI/InChIKey, no
  retrieval equality), and (v') fails against `l01`/`m01`/`s10` (name `Water` ≠ `water`, null composition, no shared
  parameter, since §4.1 gives them `parameters {}`). The design note does not mention T08.A32. Amending it is a
  test-specification change (design lane); the test is left failing. Default I would propose: a registered class of
  "provider-identity record files" (S11 §4.1: no parameters; the provider's data is pinned by its own hashes),
  exempt from (iv) and (v'), with (ii) reduced to `cas` (InChI/InChIKey could be added to the CoolProp file from
  CoolProp 8.0.0 in a scratch venv). Needs: the `specifier`'s ruling on T08.A32.

## Track A: A2 routing on every basis (§4.4–§4.5)

- DECISION: does a routing unit's `evaluate()` report the bound convention too? → yes, `UnitEvaluation.reference_
  convention = self.reference_convention` (SYN-001's constant by default, so no SYN-001 output moves); reporting
  `SYN-001-ref-v1` for an IAPWS-95 stream would contradict ADR 0001 D5.2. Alternative: only `manifest()` reads the
  fields (§4.5's letter). Reversible by: three lines in feed/sink/splitter `evaluate`.
- DECISION: R-288's hint for a routing model refused on C1 (`syn001.feed_source binds on the … basis only`) → on
  SYN-001's and C1's bases `_basis_refusal` lists only those two bases, so the 22 syn001↔c1 hints stay byte-identical
  (S11.A13; measured digest `71983ce5…` at `8c34ecb0` and on the branch; family C judges them). The text then
  under-states where the routing models bind. On an S11 basis it lists all bases and appends `_UNADMITTED`.
  Alternative: list every basis (moves 4 family-C keys, the WO-0 control's). Reversible by: the `S11_BASES` filter.
- DECISION: the reason for a `c1.*` unit on Wilson (§4.4 lists none) → "the c1.* units carry pr-c1-v1's own physics
  (ADR 0050 D3)"; the C1 routing models get only their namesake hint. Alternative: no reason. Reversible by:
  `_UNADMITTED["c1_physics"]`.
- DECISION: S11.A12's "material balance exact (==)" → holds for flows whose split products are exact in binary64; the
  Wilson case uses (0.25, 0.25, 0.5). The splitter's own rows (`n_rec = r·n`, `n_purge = (1 − r)·n`, unchanged)
  leave one ulp at e.g. n = 0.4: 0.12 + 0.27999999999999997 ≠ 0.4 (measured). Alternative: assert within one ulp.
  Reversible by: the `CASES` row.
- DECISION: the routing units' `domain` field → a `Mapping` with `hash=False` (frozen dataclasses stay hashable).
  Alternative: a tuple of pairs. Reversible by: the field declarations.

## Track A: A3 verifier forms (§4.6)

- DECISION: the declared-mixture admissibility check's numbers → γ–φ: value = `single_phase_admissible`'s temperature
  gap (or degeneracy distance), tolerance its registered `TEMPERATURE_TOLERANCE`, result = its verdict, with A09's
  shared-implementation note; pure fluid: value 0.0 when §4.6's rule holds, else the relative distance past `Psat`
  (1.0 for a liquid at or above `T_c`), tolerance 0.0, so the result is exactly the rule. `Psat` refused →
  `unsupported` with the provider's message. Alternative: other encodings of the same verdicts. Reversible by:
  `verify/forms.py`.
- DECISION: S11.A17 (the A12 flowsheets with no declared phase) → unreachable through the binder: the feed source's
  and splitter's ports take `liquid` or `vapor` only (`port_phase_unsupported` on `vapor_liquid`), so the unlifted
  path is exercised on `revision_checks` directly, with the splitter's products `vapor_liquid` at the declared
  flowsheet's solved state; the blocked reason is the existing `temperature_degenerate_unlifted(<S>)` (§4.6: "the
  existing mechanism"). Alternative: a new reason text. Reversible by: test placement / one string.
- DECISION: `tests/test_m02_wo8_verifier.py::test_the_verifier_builds_its_fresh_provider_from_the_basis` pins the old
  `fresh_provider(provider_id)` and the two-id `FRESH_PROVIDERS` → amended to the basis API and five ids (§4.6 changes
  both; the test makes no bind call, so no family-C key). Alternative: keep a provider-id overload. Reversible by:
  reverting the A3 commit's hunk.

## Track A: A4 W27 registration v3 (§4.10)

- DECISION: §4.10's "all existing W27 tests pass unchanged" vs A1 (handoff open point 2) → keep `7302a507`'s
  `v2_binder()` for the tests that read the installed build under v1/v2; none is re-pointed at v3 (v3's reading of
  the build is pinned by the new `tests/test_s11_w27_v3.py`, which also checks that v3's routes are `v2_binder`'s
  routes plus `record_source`). The one W27 test that cannot stay unchanged is
  `test_c9_w27_v2.py::test_version_switch_refuses_other_versions`, which asserted that `3` is refused: it now loops
  over `(0, 4, True)` and matches `not 1, 2 or 3` (R01 accepts 3). Alternative: list it in `AMENDED_TESTS`.
  Reversible by: reverting the A4 commit's hunk in that test.
- DECISION: how a v3 snapshot carries the key's `record_source` → each route gets `record_source` (the basis'), under
  schema `w27-registry-snapshot-v3`; v1/v2 snapshots are built exactly as before; the 0.1.1 reading under v3 carries
  `benchmarks/syn001/components.yaml`. Alternative: derive it from the provider id at classification. Reversible by:
  `snapshot.SCHEMA_V3` and the two `registration_version == 3` branches.
- DECISION: R05's "every other basis" → a static `PROVIDER_LINES_V3` naming the registered providers (`syn001`,
  `iapws95-v1`, `wilson-ig-v1`, `coolprop-heos-v1` generic; `pr-c1-v1`, `pr-lib-v1` v2 lines); any other id is
  refused (so `wilson-ig-v2` needs D5's row and a line). Alternative: the generic line for any provider. Reversible
  by: the map.
- DECISION: a v3 route with no `record_source` → refused, `routes with no record_source [<ids>]` (no key, R06); the
  duplicate refusal reads `duplicate route keys [<key tuples>]`. Alternative: KeyError. Reversible by:
  `_check_snapshot_v3`.
- DECISION: `units_judged_on` under v3 → stays the chosen route's provider id (v2's row form); the tie-break itself is
  by key (R07), visible in the unit rows' models (W27v3-A05/A06). Alternative: the key. Reversible by: `_units_v3`'s
  return.
- DECISION: R04's `why_none` meaning → `model_none_reasons_added.column_function_unregistered` in
  `registration_v3.json` (text cites S11 §7 Q6). Alternative: none. Reversible by: the generator constant.
- DECISION: v3 code shares v2's → `_check_snapshot_v2`'s spelling and (e) parts extracted (`_unaliased_v2`,
  `_models_on_routes`), and `_route_reasons_v2`/`_classify_case_v2`/`_classify_v2`/`_unit_reasons` take the v3
  variant by parameter. Inert for v1/v2: S11.A30's corpus digest equals the base's (run log). Alternative: copy the v2
  functions. Reversible by: the A4 commit.
- OPEN (design lane, batch with the ruling round): **W27v3 Q-1.** The Wilson records carry no CAS RN; v2's spelling
  rule (kept by v3) refuses them once a case spells them. Measured on this build against `case_facts.json`:
  `CH3OH->None`, `H2O->None`, `ethanol->None`, `methanol->None`, `water->None` (Wilson only; CoolProp and IAPWS-95
  give none), so v3 refuses the S11 build at classification, against §4.10's "its route serves no case". Registered
  as W27v3-A08 (the refusal as the transcribed rules give it). Default proposed: the spelling rule skips a record with
  no CAS RN. Needs: a `specifier` amendment of `W27-registration-v3.md` (and of A08), before the release's W27 run.

## Track A: A5 envelope (providers) (§4.11)

- DECISION: what the three new limitation rows and caveats say about models → "the routing models only" (true on
  this branch); §4.11's "routing and column" for Wilson and the thermal units on IAPWS-95/CoolProp are added by I1/I1b
  with the column and thermal members. Alternative: §4.11's text now (false until I1). Reversible by: the L-S11-1…3
  texts and caveats in `support_envelope.yaml`.
- DECISION: `LIBRARY_ONLY_PROVIDERS`'s docstring says the commit that makes a provider selectable "reclassifies its
  package's U02 items" → not done: §4.11 says no earlier harvest entry is edited; the S05/S07/S10 U02 notes stay as
  their manifests wrote them (C3's check only reads registered providers). Alternative: edit the harvest notes.
  Reversible by: n/a (nothing changed).
- DECISION: `test_t08_w2_support_envelope.py::test_an_unbound_provider_is_rendered_apart_from_the_axes_with_its_
  limitation` (not in §8.3) unpacked the one "Shipped, bound on another basis" line; with four such providers it
  selects `pr-c1-v1`'s line, its assertions unchanged. Alternative: render all providers on one line (changes the
  matrix's existing line). Reversible by: that hunk.
- DECISION: the amended S05 A25, S07 A30, S10 A27 tests keep their names and now assert the reverse (selectable, on
  the providers axis, not library-only), with a docstring citing R-810; S11.A34 is a new test beside
  `LIBRARY_ONLY_PROVIDERS`. Alternative: rename them. Reversible by: the A5 commit.

## Run log

- WO-0 gate, unmodified tree (`acffd034`), 16 shards per tree, 614 s:

      S11-IDENTITY PASS n=54497 changed=[]

  n = A 52 + `stage_a` 3 + B 803 + C 53639 (53856 base keys less 217 amended). Base shards 13288 passed / 3137 skipped
  / 192 deselected; branch 13312 (+24, `tests/test_s11_identity_gate.py`, in the extra shard; its one binding call is
  the one branch-only key). The first run (`a4425319`, 615 s) failed on the 25 clock-named keys (decision above).
- WO-0 control: a detached scratch worktree of `acffd034` with `_basis_refusal`'s hint `only, not` → `only; not`,
  committed there (`ca3f84c2`, not on any branch), 606 s:

      S11-IDENTITY FAIL n=54497 changed=[C:tests/test_m02_join.py::test_a_model_with_no_same_function_model_on_the_other_basis_names_none#0,C:tests/test_m02_join.py::test_syn001s_feed_to_sink_is_refused_on_the_c1_basis#0,C:tests/test_m02_join.py::test_syn001s_splitter_is_refused_on_the_c1_basis#0,C:tests/test_m02_wo8_units.py::test_a_c1_model_in_a_syn001_revision_is_refused#0] (4 digests differ)

  Every shard of both trees exited 0: the tests that state those hints compare `Unbound`s, whose `hint` is
  `compare=False`, so only the gate sees the move.
- `tests/test_s11_identity_gate.py`: 24 passed (2.4 s); ruff, ruff format, mypy clean on the three files.
- A2 gate (`15b81efe`, base tree reused): `S11-IDENTITY FAIL n=54497 changed=[] (C branch shards [1, 5, 14, 15]
  exited non-zero)`. changed=[] and no base-only keys; the failing tests are the `AMENDED_TESTS` A5 owns
  (`test_s05_envelope::test_a25`, `test_s07_registration::test_a30`, `test_s10_provider::test_a27`,
  `test_t08_w2_support_envelope` a20/c3) and T08.A32 (escalated, above). A1's first run (`97dded60`) had in addition
  the 4 base-only keys of `test_each_route_binds_a_revision_with_its_component_set` (fixed by `7302a507`).
- A3 gate (`da6c06df`): `S11-IDENTITY FAIL n=54497 changed=[] (C branch shards [1, 5, 14, 15] exited non-zero)`:
  the same eleven known failures as A2, nothing new (every SYN-001 and C1 certificate test passes).
- A4 (W27 v3): `w27_registration_v3.py --check` identical (8 states, GC-V3-1…6 hold; GC-V3-5: v3 equals v2 on every
  v2 state v2 accepts and on 225/225 development rows). S11.A30: `_a30_corpus()` (v1 over every case at the committed
  and `today` snapshots, v2 over the development half at both, every v2 snapshot × case × version × table; 8 824 782
  bytes) has SHA-256 `e141bab0…c53291` both at `8c34ecb0` (scratch worktree) and on the branch; control: v2's
  tie-break flipped to the largest provider id gives `63735e24…`. `tests/test_s11_w27_v3.py` 26 passed; W27 battery
  (c9, m06 coverage/registration/scorer/harness/campaign/provenance, l01 retake, identity-gate unit tests) 217 passed /
  26 skipped; c2/l01/m02/m04/m07 W27 readers 488 passed / 2 skipped. Identity gate not triggered (no trigger file).
- A5 (`a449d6d9`): `t08_support_matrix.py --check` 0 problems after `--emit`; the envelope, S05/S07/S10, L01 retake
  and unsupported tests 402 passed / 11 skipped; m07a/t08 changelog, harvest, gate and inventory readers 337 passed,
  1 failed (T08.A32, escalated). Identity gate (`a449d6d9`, base tree a scratch checkout of `8c34ecb0`):

      S11-IDENTITY FAIL n=54497 changed=[] (C branch shards [15] exited non-zero)

  Branch shards 14098 passed / 3201 skipped / 1 failed: T08.A32 alone. The `AMENDED_TESTS` failures of A2/A3 (s05
  a25, s07 a30, s10 a27, t08 support-envelope a20/c3) now pass.

## Handoff (2026-10-27, end of the A4–A5 engineer; track A complete)

**Done** on `wp/S11-a` (not pushed): A1 `fba583ac` (+ `97dded60`, `7302a507`), A2 `15b81efe`, A3 `da6c06df`,
A4 `de4b507b` (W27 v3: `docs/derivations/W27-registration-v3.md`, its generator and `registration_v3.json`, the v3
paths in `benchmarks/m06/w27/{coverage,registration,snapshot}.py`, `tests/test_s11_w27_v3.py`), A5 `a449d6d9`
(providers axis, L-S11-1…3, U02, `LIBRARY_ONLY_PROVIDERS = {"pr-lib-v1": "S04"}`, matrix re-emitted).
S11.A30–A34 pass. Identity: `changed=[]`, n=54497; the only failing test is T08.A32.

**Open for the design lane (batch with the package's ruling round):**
1. T08.A32 vs the two new record files (OPEN entry, A1 section): `specifier` ruling; the test is left failing.
2. §4.10's "all existing W27 tests pass unchanged": kept `v2_binder()`; one test amended (version 3 is no longer
   refused). Confirm (A4 section).
3. §6.1 A12's "exact ==" balance (A2 entry).
4. W27v3 Q-1: v2's spelling rule refuses the CAS-less Wilson records once a case spells them (five spellings measured),
   so v3 refuses the S11 build at classification; registered as W27v3-A08; default proposed: skip records with no
   CAS RN. Must be settled before the release's W27 run (A4 section).

**For I1/I1b (not track A's):** add `syn001.column` and the thermal members to the envelope and to the L-S11 texts
("routing models only" today); W27 S4 (I1b) is `snapshot.build_snapshot(registration_version=3)` of the S11 build;
D5's `wilson-ig-v2` needs its W27 v3 row (`PROVIDER_ADD` in the v3 generator, re-emit, and a `PROVIDER_LINES_V3`
entry in `snapshot.py`), else the v3 snapshot refuses it (W27-R63). The thermal models need `model_functions` rows in
v3 as well, or the v3 check refuses them as unregistered model ids.

## WO-I1 (items 1, 2, 6, 13)

DECISION (I1, item 1): T08.A32's rules move into `_a32_problems(records, conventions)` returning clause-tagged problems (same checks as the asserts they replace), so the (vi) defect test can mutate records; the committed records give `([], CAS_COMPARED_IDS)`. Alternative: a separate predicate for (vi) only. Reversible by: inlining.
DECISION (I1, item 6): A12's fourth case `wilson-ulp` is in `A12_PARAMS` only; A11 and A16 keep `CASE_PARAMS` (three), as the ruling says. Reversible by: the list.
DECISION (I1, item 2): Z is `checks.one_sided_columns(columns, state, components)` (basis-agnostic), gated on `ONE_SIDED_BASES` in `verify_revision`; the test reads the one-sided worst by differencing Z alone (`unstenciled` = the rest). The central stencil's arithmetic is unchanged (x+h then x-h, (F+ - F-)/(2h)). Reversible by: the commit.

## Handoff (2026-10-27, end of the I1 engineer at the context cap)

**Done** on `wp/S11` (not pushed): item 2 `c63d56a0` (one-sided witness; A35 on C-MW/C-EW/stripper VERIFIED, |Z| 63/63/34,
one-sided worst 6.089e-10/6.216e-10/3.274e-10, central 8.243e-8/4.644e-8/2.083e-9: the ruling's numbers), item 1
`64970c88` (T08.A32 (vi)), item 6 `0f3c9c0c` (A12), registration `713f5e3d` (MODEL_*, MODEL_CHECKS, R-825 kinds, the
§10.2 step 9 key check, A39/A91/A93, §8.3 count/sample tests), item 9 (b) `65e8f642`, item 13 (this commit).

**Not done (next I1 engineer):**
1. The envelope, which R-561 says belongs in the binding's commit (combine with `713f5e3d` by `git reset --soft`
   before merge if wanted): `unit_models.members` += `syn001.column` (23) and statement; U04 restated (§4.11:
   "`syn001.cascade` as a model id"); L-COL-1…8 (§4.11), L-COL-9 (§10.8 text), L-COL-10 (Q29: PTC policy →
   `PTC_MAPPING_INVALID`); L-S11-3 "routing and column"; `scripts/t08_support_matrix.py`'s A20 counts (14 syn001, 23);
   `LIBRARY_ONLY` in `tests/test_t08_w2_support_envelope.py` loses `syn001.column` (d1 tests then use the cascade
   only); `t08_support_matrix.py --emit` then `--check`.
   OPEN (escalate with the batch): R-561 says the binding package reclassifies S02's 12 U04 harvest items (notes say
   "library-only"); §4.11 says "No earlier harvest entry is edited". Default: follow R-561 (the specific registered
   rule): `to` drops U04 for the matching L-COL rows, notes restated; the sha256 fields untouched.
2. Item 9 (a): every A29 case through the application under `T06-revision-v2` (M1–M4, J1–J8, C-MW, C-EW, stripper,
   recycle), ≤ 3 Newton iterations, A35 certificates.
3. Identity: `scripts/s11_identity.py` on a clean tree (run it from a scratch `git worktree` of the commit, never
   while editing the checkout it tests). Expected now: FAIL only on shard failures of the six
   `test_t08_w2_support_envelope` c3 tests (pre-existing at `f331a629`: `wilson-ig-v2` is a provider module neither
   selectable nor library-only until D5 — escalated, not I1's) plus a20/d1 until the envelope lands. Then
   `s08_identity.py`, `s10c_identity.py`. Q32 (a family-C key moved by the sixteen kinds) is answered by that run.
4. Identity measured at `879ac504` (scratch worktree, clean): `S11-IDENTITY FAIL n=54438 changed=[] (C branch shards
   [1, 2, 7, 10, 15] exited non-zero; C base-only keys (59): test_t08_w1_typed_ends::test_a14_i…)`. No changed key.
   Branch failures (kept logs `scratchpad/i1/idkeep`), all from the registration: the envelope a20/d1 (item 1 above);
   the six c3 (pre-existing, D5); W27 — `test_m06_w27_coverage` (4: `RefusalError: unregistered model ids
   ['syn001.column']`, `SnapshotUnsupportedError` registry/list_models), `test_l01_retake` (6 errors, its retake
   fixture fails on the same refusal); `test_t07_w5e_application_results` (served-response fixture, list_models);
   `test_t08_rename_substitution` (the w5c table's two new S11 rows); `test_t08_w1_typed_ends::test_a14_i` (fails part
   way over the registry, hence the 59 base-only keys). OPEN (escalate): W27 v1/v2 on today's registry now meets
   `syn001.column`, which R-805 registers in v3 only with function null; §9 moves S4 to I1b. Default: I1b's W27 work
   (model_functions rows) closes it; until then these W27 tests fail. The other three are amendable sample tables
   (add to `AMENDED_TESTS` with their §8.3 reason) — typed_ends needs a look for a real column-specific assumption.

## WO-I1 (envelope; item 9 (a); the tests the registration broke)

DECISION (I1, envelope): U04 keeps "a model id not in `MODEL_BUILDERS`" and adds §4.11's "`syn001.cascade` as a model id (bind `syn001.column` with `top`/`bottom`)", with S11.A14 as evidence. Alternative: §4.11's text alone (drops the catch-all the two existing evidence nodes test). Reversible by: the U04 row.
DECISION (I1, envelope): the `unit_models` statement also corrects "SYN-001's thirteen, on SYN-001's basis only", false since A2 for the three routing models. Alternative: the column only. Reversible by: the statement.
DECISION (I1, envelope): L-COL-2 carries S02's "no inside-out or rate-based method" (S02 §14) so the reclassified S02 item has an L-row; L-COL-10's text is B3e's measured outcome. Reversible by: the rows.
DECISION (I1, outside §8.3): `test_t08_w1_typed_ends::test_a14_i` requires its corpus to cover `MODEL_BUILDERS`; the corpus gains the column sample (`COLUMN_SAMPLES`: M1, C-MW), appended last so earlier documents keep their order. Its assertions are unchanged; the column adds 2 declarations and 35 pressure-only rows (11 + 24), all copies or specifications. Alternative: exclude `syn001.column` from the coverage assertion (a weakening). Reversible by: that commit.
DECISION (I1, outside §8.3, follows the w5c sample amendment §8.3 names): `test_t08_rename_substitution::test_with_the_pre_rename_self_hashes_the_w5c_table_is_the_pre_rename_one` filters the `S11:` rows out before the pre-rename digest, as it already filters M02's rows; the digest and the "only binds moved" assertion are unchanged. Alternative: a new pre-rename digest (re-baselining). Reversible by: that commit.
DECISION (I1, outside §8.3, the analogue of its `test_t08_b50_surface_content` `list_models` entry): the two W5e `model_registry_view` fixtures are re-emitted by `t07_schema_fixtures.py --write`, which rewrote only those two; each diff is the `syn001.column` entry added (+41 lines, no line removed, nothing else changed). `test_m02_join::test_the_list_models_fixtures_decompose_onto_the_pre_m02_ones` strips `_AFTER_M02 = ("syn001.column",)` with the C1 entries before its pre-M02 digests (unchanged) and asserts the column is present. Alternative: new pre-M02 digests. Reversible by: that commit.
