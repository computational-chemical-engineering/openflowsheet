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
Item 9 (a) (R-838), `tests/test_s11_column_application.py`: each case committed to a `LocalApplication` and solved by `solve(…, "T06-revision-v2")`, read back from the job outputs (bundle `solution-state.json`, the certificate). Newton iterations = the sum over the certificate's `branch_provenance`. Measured (iterations/attempts/max |Δ|/tol/status): M1 0/1/1.17e-6, M2 0/1/2.82e-8, M3 0/1/3.28e-3, M4 0/1/3.37e-7, J1 0/1/5.71e-8, J2 0/1/2.33e-5, J3 0/1/6.18e-9, J4 0/1/1.02e-2, J5 0/1/2.41e-7, J6 0/1/1.07e-7, J7 0/1/2.01e-6, J8 0/1/5.34e-2, C-MW 0/1/1.29e-7, C-EW 0/1/2.14e-8, stripper 0/1 (library root exactly), M1-recycle 3/1 (closes, recycle > 0; at the budget); all VERIFIED. 16 passed (40 s).
DECISION (I1, item 9 (a)): the ≤ 3 Newton budget is asserted on the recycle case too (the ruling lists it; A29's own budget is stated "with no recycle"); measured 3, at the bound. Alternative: exempt the recycle as the in-process A29 test does. Reversible by: one line.
DECISION (I1, outside §8.3, found by the identity run): `scripts/t08_evidence_manifest.py`'s B27 counts T08's thirteen SYN-001 models from the working envelope; S02's column is not T08's (B13's rule, as M02's C1 models were excluded by `f71d55ed`), so `_NOT_T08_SYN001 = {"syn001.column"}` is left out of the count, `== 13` unchanged. `test_t08_evidence_manifest::test_tested_with_v14_b_the_only_fail_and_accepted` passes again (15 passed). Alternative: `== 14`. Reversible by: that commit.

## Handoff (2026-10-27, end of the second I1 engineer; WO-I1 complete)

**Done** on `wp/S11` (not pushed), after the first I1 engineer's six commits:
- envelope `57db68d6`: `syn001.column` a member (23; 14 `syn001.*`), statement, U04 (cascade + column hint, S11.A14),
  L-COL-1…10, L-S11-3 "routing and column", A20 counts, `LIBRARY_ONLY = {"syn001.cascade": "S01"}`;
  `t08_support_matrix.py --check` 0 problems.
- R-561 `de7e23c1`: S02's 12 U04 harvest items reclassified (own commit; the D1-A03 tripwire checks the tree's
  state, not commit membership, so no squash into `713f5e3d`). S03/S06/S08/S09/S10c column items untouched (§4.11).
- tests outside the envelope: `31332368` (T08.A14(i) corpus + column sample), `a0218ce3` (pre-rename w5c digest
  leaves out `S11:` rows), `5d89a50c` (W5e `list_models` fixtures + `test_m02_join` pre-M02 decomposition),
  `2587887c` (T08 B27 counts T08's 13). Each with a DECISION line above; none added to `AMENDED_TESTS`.
- item 9 (a) `fa60e6a8`: `tests/test_s11_column_application.py`, 16 cases through `LocalApplication` under
  `T06-revision-v2`, all VERIFIED, 0 Newton iterations except the recycle (3, at the budget).

**Identity** at `fa60e6a8` (scratch worktree, clean): `S11-IDENTITY FAIL n=54497 changed=[] (C branch shards
[1, 7, 11, 15] exited non-zero)` — n back to 54497 (the 59 base-only keys of A14(i) are gone), no changed key.
Branch failures: envelope a20 (its `scanned_providers` assertion: `wilson-ig-v2`) and the six c3 (D5, not I1's);
W27 `test_m06_w27_coverage` 4 and `test_l01_retake` 6 errors (`unregistered model ids ['syn001.column']`, I1b's
`model_functions`); `test_t08_evidence_manifest` B27 (fixed by `2587887c`, after the run).
`S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL`; `S10C-IDENTITY PASS n=858 changed=[]`.

**Open (batch with the package's ruling round):**
1. U04's capability keeps the catch-all beside §4.11's cascade text (DECISION above) — confirm.
2. The ≤ 3 Newton budget asserted on the recycle case through the application (measured 3) — confirm.
3. The four test amendments outside §8.3 (A14(i), rename w5c, W5e fixtures + m02_join, T08 B27): confirm, or name
   them in §8.3 / `AMENDED_TESTS` (the identity run judged their keys equal, so none needed it).
4. a20's `scanned_providers` now fails only on `wilson-ig-v2` (as c3): D5 registers it.

Identity at `079be287` (final, clean scratch worktree): `S11-IDENTITY FAIL n=54497 changed=[] (C branch shards [1, 7, 15] exited non-zero)` — the remaining failures are exactly the envelope a20 + six c3 (`wilson-ig-v2`, D5), `test_m06_w27_coverage` 4 and `test_l01_retake` 6 errors (I1b). S08 and S10C lines as above, unchanged.

## WO-I1b part 3a: rulings item 3 (R-832) and §4.10's model rows

- W27v3-R09 implemented in the generator (`spelling_problems_v3`: W27v2-R08 over the records that have a CAS RN) and in
  `coverage._check_snapshot_v3`; A08 restated by hand (A04's outcome on B), A09 added (S1co with record sources, case
  `co`, `['co->630-08-0']`). Mutants `cas_less_refused` (changes only A08, back to `['H2O->None']`) and
  `spelling_rule_off` (changes only A09, to `COMPONENT_UNAVAILABLE`). The generator's reference reproduced the
  hand-written A08 at the first run. `--check` identical (9 states); GC-V3-5 holds (225/225); S11.A30 holds.
- §4.10's seven `thermal.*` → function rows (`offers: []`) are in `MODEL_FUNCTIONS_ADD`; GC-V3-3 now claims each
  non-null row is onto an existing `units.functions` name and only null rows carry `why_none`.
- DECISION (I1b, item 3): the rules list of `registration_v3.json` names R09 as `c:no_cas_skipped` beside
  `c:case_distinct`. Alternative: no tag (the list is descriptive). Reversible by: the one list entry and `--emit`.
- Diagnosis (not cleared here): `test_m06_w27_coverage` (4) and `test_l01_retake` (6 errors) snapshot the installed
  build under v1/v2 through `v2_binder()`. Since I1, `MODEL_BASES` puts `syn001.column` on SYN-001's basis, which
  `v2_binder()` keeps, and `list_models` lists it; v1/v2's model table has no row for it (R-805: v3 only), so v1/v2
  refuse (`unregistered model ids ['syn001.column']`, `list_models-only ['syn001.column']`,
  `list_models_sha256` moved). v3's rows cannot clear a v1/v2 test, and S4 does not either. OPEN (design lane,
  extends R-837): `v2_binder()` also restricts the models (and `list_models`) to v1's model table — default; or these
  tests are amended under §8.3. The thermal models will meet the same refusal when they enter `MODEL_BASES`.
- S4 (acceptance 4, next WO, after the thermal registry commit): `snapshot.build_snapshot(registration_version=3)` of
  the installed build, then classify the 225 development rows under version 3 with no refusal and record the counts
  (`benchmarks/m06/w27`, S11.A40; register S4's SHA-256 in W27v3-R08).

## WO-I1b part 2: registration, hooks and refusal texts (registration commit), and the handoff

- Registration: the seven `thermal.*` signatures are defined in `revision_binding` (`_THERMAL_*`, as `_COLUMN` is
  for `column_binding`: `thermal_binding` imports `revision_binding`, so a bottom-of-module import breaks when
  `thermal_binding` is imported first); `MODEL_BUILDERS` holds `_thermal_builder(id)`, which imports
  `thermal_binding.BUILDERS` at the call; `thermal_binding.SIGNATURES`/`BASES` now read the binder's rows. The five
  γ–φ-faced `syn001.*` units gain `wilson-ig-v2`. 30 members in all three tables (both import orders checked).
- Hooks: `forms.GAMMA_PHI_UNITS` (`wilson-ig-v2` → it; v1 stays `DECLARED_MIXTURE`); `table.revision_checks`
  dispatches it to `gamma_phi_units.revision_checks` (lazy import). `table.MODEL_CHECKS` is a `MutableMapping`
  over the table's own rows then `verify.thermal.MODEL_CHECKS` (lazy; writes go to the own rows so
  `monkeypatch.setitem` still works). `EXTERNAL_DUTY_MODELS` += thermal heater, flash; `WORK_MODELS` += the three
  machines (without them the envelope misses Q/W; S11D D's DECISION measured −878.17 W).
- DECISION: on a pure-fluid basis only a `vapor_liquid` outlet of a `thermal.*` instance is saturated (read from
  its carried split, `verify.thermal.saturated_*`); any other undeclared stream stays unlifted, because S11.A17
  (restated R-841) drives `vapor_liquid` routing products through `revision_checks` directly and needs them
  blocked. Alternative: every `vapor_liquid` stream on a pure basis (§4.8's literal reading; breaks A17). Reversible
  by: the `saturated` set in `table.revision_checks`.
- DECISION: `thermal.flash` on Wilson names `syn001.ph_flash` (both duty-specified). Alternative: `syn001.tp_flash`.
  Reversible by: `_LIFTED_NAMESAKE`.
- DECISION: the no-volume reason reads "wilson-ig-v2 has no liquid volume, which a pump needs (L-GP-1)" (§4.7 gives
  no literal). Alternative: any other wording. Reversible by: `_UNADMITTED["no_volume"]`.
- OPEN: pairs §4.7 does not rewrite keep their first-pass reason, so `syn001.heat_exchanger`, separator and reactors
  on a pure fluid still say "pure-fluid units are S11b (...)" and on Wilson "γ–φ faces are S11c", which are stale.
  Default: leave (not this WO's text); design lane to give texts.
- Dropped helpers: `test_s11_thermal_binding.register`/`registered`, `s11_gp_support.admit_wilson`,
  `admit_machines`; `dispatch_gamma_phi` became `count_gamma_phi` (a spy on the real dispatch). The test
  `test_until_i1b_the_binder_refuses_the_family` became `test_since_i1b_the_binder_holds_the_family`.

**Handoff (context cap reached; the next engineer resumes here).** Done: brief part 2 items 1–3 (registration
commit). Not done, in order:
1. G1 identity on the registration commit (expect `changed=[]` plus possibly the new-matrix S11-own tests).
2. `tests/test_s11_routing.py` A13 tests (`test_a13_the_admission_matrix`, `..._every_refused_pair_on_a_new_basis...`
   `_expected_reason`) still encode the pre-I1b matrix: restate them to §4.7 (five units + Wilson; thermal rows;
   new reasons) — S11's own tests, no AMENDED_TESTS entry. Add A82 (30 members, admission = §4.7) and the
   `model_unsupported(thermal.pump)` no-volume assertion to GP-M2's test (A81 binder half).
3. Item 12 (R-841): remove the `S11_BASES` filter in `_basis_refusal` ("bases" when > 1). NOTE: until then a
   `thermal.*` refusal on SYN-001/C1 renders an empty basis list (all its bases are S11's) — do it next.
   Expected moved base tests: `tests/test_m02_join.py` feed_source, stream_splitter and valve refusal tests
   (`syn001.valve` gained Wilson) → `AMENDED_TESTS` citing R-841. Re-derive `BASE_SYN001_C1_HINTS` (22 pairs) as
   the unchanged-model subset, measured at the base `8c34ecb0`.
4. Brief items 5 (envelope, support matrix, L-TH-1…8, L-GP-1…3, providers axis, `--emit/--check`), 6 (samples,
   §8.3 count tests), 7 (S4, `v2_binder()` restriction — the default stands: restrict models and `list_models` to
   v1/v2's table, isolated commit, DECISION extending R-837), 8 (item 10: Q-C2, C3-2 new code
   `isentropic_state_single_phase`, O-C6-1 RANK_DEFICIENT check — STOP if not), then G1/S08/S10C.
5. Measured at this commit (`pytest tests/test_s11_*.py test_m02_wo8_registries test_t05_w1d_verifier
   test_m02_wo9_reactor`): 978 passed, 64 skipped, **14 failed**, each the pre-I1b matrix pinned by a test:
   `test_s11_routing` A13 ×6 (item 2/3 above), `test_s11_gp_binding::test_unpatched_the_five_are_refused_on_wilson`
   ×5 (obsolete since the Wilson rows landed: restate as admitted), `test_s11_column_registration::test_a39_...`
   (registry size 23 → 30), `test_s11_w27_v3::test_v3_routes_are_the_v2_routes_with_their_record_sources` (the
   thermal models through `v2_binder()`: item 7's restriction), and the BASE test
   `tests/test_m02_wo8_registries.py::test_the_envelope_sets_gain_the_c1_ids` (pins `EXTERNAL_DUTY_MODELS` /
   `WORK_MODELS`, which now hold the thermal duty and work models). OPEN (design lane, not in §8.3): amend it under
   §8.3 (restricted to non-`thermal.` ids, the C6-2 precedent) — default; or the envelope reads the thermal Q/W from
   a separate set. Thermal/GP solve and verifier tests all pass through the real registration and hooks.

## WO-I1b part 2 (continued): tests restated, R-841, envelope, samples, S4, item 10

- `51dcc31d`: S11's own tests restated to §4.7 (A13, A39 23 → 30, the five admitted on Wilson, the
  `wilson_admitted` fixture dropped); A82; A81's binder half (`thermal.pump` on GP-M2 → no-volume reason).
- R-841 (rulings item 12): `_basis_refusal` names every basis the model binds on ("bases" when more than one); the
  `S11_BASES` filter is gone. Measured at the base `8c34ecb0`: the 14 syn001/c1 pairs of the models whose
  `MODEL_BASES` S11 does not change hash to `3bdca9c1…`, and the branch reproduces it byte for byte. The eight moved
  pairs (three routing models, the five γ–φ units, on C1) and the new column/thermal pairs are asserted literally.
  `AMENDED_TESTS` += `test_m02_join`'s three refusal tests (feed_source, stream_splitter, valve), citing R-841.
- DECISION (orchestrator ruling): the first-pass `_UNADMITTED` reasons that said "S11b"/"S11c" → restated to the
  admission S11 ends with: `syn001` exchanger/separator/reactors on a pure fluid read "pure-fluid streams are
  declared-regime (ADR 0051), which only the thermal.* units take; none of them has this function"; on Wilson "its
  EO face reads lnK and h_<c>, and S11 gives γ–φ faces to the five K02/T05 units only (L-GP-1)"; a non-routing
  `c1.*` model on a pure fluid now reads C1's own-physics reason (ADR 0050 D3), as it does on Wilson. Alternative:
  keep the first-pass texts. Reversible by: the two `_UNADMITTED` strings and the one `c1_physics` branch.
- DECISION (orchestrator ruling): `test_m02_wo8_registries::test_the_envelope_sets_gain_the_c1_ids` → restricted to
  the `EXTERNAL_DUTY_MODELS` ids outside `thermal.` (C6-2 precedent; its recorded operands stay the base's, so no
  `AMENDED_TESTS` entry); `test_s11_thermal_verifier::test_the_envelope_reads_the_thermal_duty_and_work` pins the
  thermal duty and work ids literally. Alternative: leave it failing for the reviewer. Reversible by: the one
  `base_duty` line.
- Item 5 (envelope, §4.10): `unit_models.members` += the seven (30), statement restated; L-TH-1…8 (L-TH-4/5 with
  rulings item 10's appended sentences, L-TH-8 new) and L-GP-1…3 appended after L-COL-10, each with collected test
  evidence; L-S11-1/2 drop "only the routing models", L-S11-3 and the three `other_basis_providers` caveats name what
  binds now; the A13 evidence node follows its rename (`test_a13_a82_the_admission_matrix`). `t08_support_matrix.py`
  A20 counts 30 models / 7 thermal; `--emit`, then `--check` 0 problems. `test_t08_w2_support_envelope::test_a20_…`
  (already in `AMENDED_TESTS`, §8.3) restated to 30/7. A83 in `test_s11_bases`. Providers axis, scanned providers and
  `LIBRARY_ONLY_PROVIDERS` were already §4.10's (A5).
- DECISION (item 5): L-S11-3 and the `wilson-ig-v2` caveat now name the five K02/T05 units and the two vapour machines
  (the old "routing models and the column" became false at I1b; §4.10 says only "L-S11-3 names wilson-ig-v2").
  Alternative: leave L-S11-3's binding sentence as it was. Reversible by: the two text blocks and `--emit`.
- Item 6 (samples, S11.A86): `s11_thermal_support.THERMAL_SAMPLES = ("TH-C1", "TH-R1", "GP-M1")` (committed cases that
  bind without the coolprop extra; together one bound instance of each of the seven), appended last in the T07 W5c,
  T08 edge-identity and T08 typed-ends corpora (COLUMN_SAMPLES precedent). W5c's EXPECTED gains three generated
  binding pins (regression pins; the earlier rows unchanged).
- DECISION (item 6): the W5c "signature describes every bound instance" test exempts the thermal heater's optional
  `pressure_drop`/`outlet_vapor_fraction` and, in quality mode, its specification choice (as B3b exempts the
  column's optional parameters: `ModelSignature` cannot list them; `thermal_binding`'s docstring says so).
  Alternative: samples without a quality-mode heater (would hide the gap). Reversible by: the `quality_mode` block.
- Item 6 (§8.3 count tests and registry corpora): `test_m02_join`'s registry table (in `AMENDED_TESTS`) gains the five
  on Wilson and the seven thermal rows; `test_t08_b50_surface_content`'s `V02_ADDITIONS` registers the seven under
  R-816 and strips them with the column (`S11_MODELS`); the W5e `list_models` fixtures regenerated
  (`t07_schema_fixtures.py --write`; I1's `5d89a50c` precedent); `test_t07_r6_hints` proves the 11 thermal triples on
  `THERMAL_SAMPLES` (`THERMAL_COVERED`).
- DECISION (item 6): base tests that count or tabulate over every registered model and that §8.3 does not name
  (`test_t07_r6_hints` count and coverage table, `test_t07_w5e…::test_g_r6_6…`) are restricted to the ids outside
  `thermal.` and the thermal part is pinned apart (C6-2 precedent; the base's recorded operands stand), the W5e
  thermal entries in `test_s11_thermal_binding::test_list_models_lists_each_thermal_pin_with_its_encodings`.
  Alternative: amend them under §8.3 (needs a design-lane erratum). Reversible by: the filters.
- DECISION (item 6): R-816's register entry spells the seven ids in full (`thermal.valve`, …), which
  `test_m07a_a51_each_v0_2_addition_is_named_by_its_register_entry` requires of the entry naming an addition; the
  decision is unchanged. Alternative: cite another entry. Reversible by: the one register line.
- OPEN (design lane): `test_adr_0008_transient_readiness::test_e1_every_bindable_model_has_declarations_u1_reads`
  fails since the registration commit: `thermal.heater`, `valve`, `mixer` and the machines declare no module-level
  `EQUATIONS` U1 can read (they build `_BASE` + per-mode/per-machine rows; `machines.MODEL_IDS` is a dict, U1 reads a
  tuple). Default: give heater/valve/mixer a module `EQUATIONS` mapping (configuration → rows, as `flash.py` has a
  tuple) and the machines module `EQUATIONS` by machine plus a tuple of ids; this changes the four modules' bytes
  (their manifests' `artifact_hash`), so it wants the reviewer's eye. Not done here.

**Handoff (2026-10-27, context cap; the next engineer resumes here).** Commits since `cbc38ca2`: `51dcc31d` S11 tests
restated to §4.7 + A82 + A81 binder half; `0f3db1b4` R-841 (item 12); `8044d5e2` stale "S11b/S11c" reasons
restated (ruling); `693d9e8c` m02 envelope-sets test non-thermal (ruling); `97e1c456` envelope/support matrix (item
5, A83; `--check` 0 problems); `5774b8d4` + `2c8dce6c` samples and registry-wide tests (item 6, A86). Not done, in
order:
1. ADR 0008 E1 for the thermal modules (OPEN above; default stated there) — touches model-module bytes.
2. Item 7: `v2_binder()` restricts the models and `list_models` to v1/v2's model table (isolated commit, DECISION
   extending R-837); then S4 = `snapshot.build_snapshot(registration_version=3)` of the build (127 routes, Wilson on
   `wilson-ig-v2`), classify the 225 development rows under v3 with no refusal, record the counts
   (`benchmarks/m06/w27`, S11.A40/A84), S4's SHA-256 into W27v3-R08; `w27_registration_v3 --check`. Must clear
   `test_m06_w27_coverage` (4), `test_l01_retake` (6 errors) and
   `test_s11_w27_v3::test_v3_routes_are_the_v2_routes_with_their_record_sources`.
3. Item 8 (rulings item 10): Q-C2 test; C3-2 code `isentropic_state_single_phase` (kernel, blocks, machines +
   manifest limitation text, verifier mirror); O-C6-1 (A62 under `T04-W12`: Q = 0 must certify `RANK_DEFICIENT`, else
   STOP and escalate; Q = 1 kW `LINEAR_SOLVE_FAILED`; record the SYN-001 pump's dormant case); add
   `test_the_dormancy_registry_is_syn001s_and_the_c1_mixers_vapour_outlet` to §8.3's record (design-doc erratum line).
4. Gates on the final tree (scratch worktree, `scratchpad/i1b/identity.sh <commit> <tag>`), `t08_support_matrix.py
   --check`, `w27_registration_v3 --check`, all `tests/test_s11_*`. Expected `AMENDED_TESTS` additions so far: only
   R-841's three `test_m02_join` tests.
Gates at `83185423` (measured): `S11-IDENTITY FAIL n=54490 changed=[]` (failing runs, not changed keys: the T05
family exited 1 and C shards failed; base-only keys = `test_m06_w27_coverage` 4, item 7); `S08-IDENTITY PASS n=52
changed=[S02.P1] p1_stage_a=EQUAL`; `S10C-IDENTITY FAIL n=858 changed=[]` (the same T05 run). The T05 failures were
fixed in the next commit: `verify.table` imported `composition_dependent` from the models (cbc38ca2; T05
table-independence, 3 tests), now `forms.pure_fluid_provider` (same predicate, same values); L-TH-7 spelled the v2
contract id in `benchmarks/` (`test_b06_no_registered_policy_names_v2`), now "T05b's v2 phase contract". T05 modules +
thermal/GP verifier tests: 1450 passed. Gates not re-run after that fix.
Known red at this handoff: ADR 0008 E1 (item 1), the three W27 tests of item 7. Everything else touched passes
(S11 battery, the 24 registry-dependent base files, envelope readers, T07/T08 corpora).

## WO-I1b part 2 (finish): ADR 0008 E1, R-816, item 7 (v2 binder, S4), item 8 (rulings item 10)

- DECISION (orchestrator ruling, closes the OPEN above): ADR 0008 E1 → the four thermal modules gain a module-level
  `EQUATIONS` mapping U1 reads (configuration → rows): heater `(mode, saturated outlet)` (6), valve and mixer
  `saturated outlet` (2 each), machines `(machine, saturated outlet)` over the outlet forms each machine has (4);
  `declared_equations` now returns the mapping's entry (the same rows, in the same order). `machines.MODEL_IDS` becomes
  the tuple U1 reads; the machine → id dict is `MACHINE_MODEL_IDS` (5 call sites in the binders). U1 attributes the
  machine module's rows to all three ids (as `c1/reactor.py`'s ids share one tuple); E1 only checks reach, and no
  machine row is a `holdup_balance`. New S11 modules: no registered result moves; the module bytes (manifest
  `artifact_hash`) change. Alternative: extend U1's reader (a base test). Reversible by: the one commit.
  Measured: `test_adr_0008_transient_readiness` + `test_s11_thermal_*` + `test_s11_gp_*` + `test_s11_bases`: 679
  passed, 58 skipped; `t08_support_matrix.py --check` 0 problems; `t07_schema_fixtures.py` all "same".
- DECISION (orchestrator ruling, replaces item 6's register DECISION above): R-816's decision text restored as the
  ruling round wrote it (register entries are not rewritten); the seven ids in full go in a dated "Amended
  2026-10-27" line under the entry, which `test_t08_b50_surface_content`'s `_register_entry` span includes (its
  comment now says so). Alternative: the rewritten entry. Reversible by: the one commit. Measured: b50 7 passed;
  `test_m07a_surface_chain` + `test_m07_mr12_extras_v02` pass.
- DECISION (item 7, part 3a's OPEN, orchestrator default extending R-837): the v1/v2 reading of the installed build
  also restricts its models: `snapshot.restrict_to_v2_models` keeps `MODEL_BASES`/`MODEL_BUILDERS` on v1/v2's model
  table (W27-R12, 22 ids) and sets `LIST_MODELS`, which `build_snapshot` passes to `list_models_document`; that
  filters the served document to those ids (what `list_models` serves when `MODEL_BUILDERS` holds only them: sorted
  ids, one signature each; an unserved id is refused). Both v1/v2 readers use it: `v2_binder()` (tests) and L01's
  `retake.measurement_binding()`. Follow-on test edits (same reading, no `AMENDED_TESTS` entry): `constructed_binder`
  sets `LIST_MODELS` to the same 22 ids (its 13-id refusal still fires, "list_models-only");
  `test_each_route_binds…` compares routes with `v2_binder().MODEL_BASES` (and checks it equals the installed one on
  those ids); `test_s11_w27_v3::test_v3_routes_are_the_v2_routes…` states that v3's routes gain only S11's models
  (`syn001.column` on SYN-001, none on `pr-c1-v1`). Alternative: amend the W27 tests under §8.3. Reversible by: the
  one commit. Measured: the v2 reading's `list_models_sha256` = A3's `f070fbe0…` again; `test_m06_w27_coverage` +
  `test_l01_retake` + `test_s11_w27_v3`: 95 passed, 2 skipped (was 8 failed, 6 errors).
- Item 7 (S4, W27v3-R08, rulings item 3 acceptance 4, S11.A40/A84): `scripts/s11_w27_s4.py --emit` wrote
  `benchmarks/m06/openidaes450/snapshot_s4.json` (S4 + its SHA-256 + the 225-row version 3 tally), built at
  `82a1d87b`: 127 routes, Wilson on `wilson-ig-v2`, S4 SHA-256 `58ba0d48…3231`. No refusal on the 225 development
  rows: 3 CANDIDATE, 3 COMPONENT_UNAVAILABLE, 3 PROPERTY_ROUTE_UNAVAILABLE, 32 NOT_STEADY, 184 UNIT_UNAVAILABLE
  (committed v2 snapshot on the same rows: 9 COMPONENT_UNAVAILABLE, 0, 0; six rows move: the three IAPWS pump variants
  → CANDIDATE, `official_btx_flash_canary`, `variant_hda_once_through_single_flash`,
  `variant_methanol_water_nrtl_partial_condensation` → PROPERTY_ROUTE_UNAVAILABLE). `--check` rebuilds and compares
  every member but `git_commit`. Tests `test_a40_a84_…` (+ the check-can-fail mutant) in `test_s11_w27_v3`.
- DECISION (item 7): S4's SHA-256 registered by a dated "*Registered 2026-10-27 (WO-I1b)*" sentence under W27v3-R08
  in `W27-registration-v3.md` (outside the generated blocks; `w27_registration_v3.py --check` identical), and S4 kept
  in a record file beside `registration_v3.json`, with a `--check` generator (L01 retake record precedent: snapshot +
  `snapshot_sha256`). Alternative: a member of `registration_v3.json` (would move the transcription the generator
  pins). Reversible by: the record, the script, the one sentence.
- Item 8, C3-2 (rulings item 10, R-839): new code `isentropic_state_single_phase` — `blocks.isentropic_state`'s
  beta_s outside [0, 1], and `kernel.isentropic_temperature`'s root outside the saturation range with the other label;
  `isentropic_state_two_phase` keeps s* past the saturated entropy (and the Wilson UNSTABLE vapour). Both codes are
  `kernel.ISENTROPIC_FORM_CODES`: a `DomainError` at a trial in the block (behaviour unchanged, the code alone moves)
  and `<code>(<U>)` in `machines.evaluate`; the machines' manifest limitation names both. C3-7's turbine (vapor_liquid
  declared, beta_s > 1) → `isentropic_state_single_phase(U1)`; A55's n-pentane compressor still
  `isentropic_state_two_phase(U1)` (CoolProp run). The verifier's mirror (`verify.thermal.isentropic_enthalpy`) names
  no code (`isentropic_state_refused: <message>`): unchanged. Measured: thermal/GP/bases/ADR 0008 with CoolProp: 740
  passed.
- Item 8, Q-C2 (measured on iapws95-v1, `test_q_c2_…` in `test_s11_thermal_solve`): steam 1 MPa, 573.15 K → 0.1 MPa,
  eta = 0.5, outlet `vapor`: x_s = 0.9613, the actual outlet 2.61 kJ/mol above h^V_sat; the revision is
  INITIALIZATION_FAILED `initializer_failed(T): isentropic_state_two_phase(T)` (the ruling's numbers reproduce). The
  `isentropic_phase` parameter's `parameter_unsupported` is the existing binding test. L-TH-4's evidence gains the
  test (`t08_support_matrix.py --emit`, `--check` 0 problems).
- Item 8, O-C6-1 (`test_o_c6_1_…`, two tests): A62's flowsheet under `T04-W12`: Q = 0 → CONVERGED, certificate
  UNVERIFIED, regularity `RANK_DEFICIENT` (the ruling's condition holds, no stop); Q = 1 kW → `LINEAR_SOLVE_FAILED`
  ("SuperLU: Factor is exactly singular"). The SYN-001 pump's dormant case (same topology, SYN-001 basis, 0.1 → 0.18
  MPa, eta 0.75) under `T04-W12`: CONVERGED, VERIFIED, `NO_RANK_LOSS_DETECTED` — so §4.9's "as the SYN-001 pump's is"
  does not hold at the certificate: the verifier reduces a dormant outlet by its own registry
  (`verify.zero_flow.DORMANT_OUTLETS`, spec §7.6), under either phase contract, and that registry has the pump but no
  `thermal.*` entry. Consequence, also measured: A62 at Q = 0 under `T06-revision-v2` converges but certifies
  UNVERIFIED/`RANK_DEFICIENT` too.
- OPEN (design lane, from O-C6-1): should `verify.zero_flow.DORMANT_OUTLETS` gain §4.9's single-phase `thermal.*`
  outlets (so a v2 dormant thermal outlet certifies as the pump's does), and §4.9/L-TH-7's "as the SYN-001 pump's is"
  be restated? Default: neither here (a verifier/certificate change, design-led); the measured pins stand.
- Item 8, records: §8.3's R-839 erratum gains a dated line naming
  `test_the_dormancy_registry_is_syn001s_and_the_c1_mixers_vapour_outlet` (no `AMENDED_TESTS` entry: it passes on both).
- Gate finding (S11 identity at `aad5530f`: C branch shards 11, 12 non-zero) 1/2:
  `test_m02_join::test_the_list_models_fixtures_decompose_onto_the_pre_m02_ones` failed since item 6 regenerated the
  W5e `list_models` fixtures with the thermal entries. DECISION: its `_AFTER_M02` (added at I1 for the column) gains
  the seven `thermal.*` ids, so the pre-M02 SHA-256 operands stand (C6-2 precedent; no `AMENDED_TESTS` entry).
  Alternative: amend it under §8.3. Reversible by: the one tuple. Measured: `test_m02_join` 14 passed.
- Gate finding 2/2: `test_t08_evidence_manifest::test_the_manifest_validates_and_holds_no_angle_bracketed_text`
  failed since item 5: every envelope limitation travels into the T08 manifest, and L-TH-4's appended sentence (rulings
  item 10) spelled `isentropic_state_two_phase(<U>)`. DECISION: L-TH-4 spells it `({U})`, the T08 generator's own
  placeholder convention (it rewrites `<x>` to `{x}` in check descriptions); `test_s11_bases` follows;
  `t08_support_matrix.py --emit`, `--check` 0 problems. Alternative: none that keeps the manifest rule. Reversible
  by: the one envelope line. Measured: `test_s11_bases` + `test_t08_evidence_manifest` + `test_t08_w2_support_envelope`:
  344 passed.
