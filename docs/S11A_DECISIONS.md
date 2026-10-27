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
