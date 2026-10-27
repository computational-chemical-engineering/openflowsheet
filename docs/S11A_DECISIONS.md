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
