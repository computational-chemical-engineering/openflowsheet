# M04 build log: decisions the build lane took (append-only)

Each entry: the decision, the rejected alternative, why, and the commit that carries it. The
authority is `docs/derivations/M04-spec.md` and ADRs 0036/0037; an entry here records only what the
spec left to the build lane, so the design lane can accept, reword or revert it.

## WO-7 — the unit `c1.reactor_surrogate` and its binder resolution (2026-10-09)

- **E1. Where the unit lives.** `studies/surrogate/reactor.py`, beside the pure `quadratic` and
  `plan` modules it wraps. The binder (`application`) imports it, as `application` already imports
  `studies.surrogate` (admission, the job runner). Rejected: `models/c1/reactor_surrogate.py`, which
  would make `models` import `studies` (an upward import across blueprint §15's layers).
- **E2. The coefficients and N_tubes are the block's compile-time constants, not pinned inputs.**
  X̃ and ΔT̃ are one property block of the inlet stream (`<U>_surrogate`, values `predict`, Jacobian
  `inlet_sensitivity`, both from `quadratic`). The builder reports `{surrogate_manifest_sha256,
  n_tubes}` as the instance's configuration, so both enter the flowsheet label and `model_version`
  (ADR 0002 D2.7); `constants_sha256` holds only `ν`. Rejected: (a) 72 coefficient parameters and
  an `n_tubes` parameter that no row reads symbolically — M03's parametric twin would report a
  silent zero derivative with respect to them; (b) the quadratic written as symbolic rows — the
  input map divides by n_tot and n_N2, so the rows are NaN at a dormant inlet and at n_N2 = 0, and
  `Algebra` has no `if_else` (adding one is an architecture cost, spec.py). Consequence: a surrogate's
  N_tubes and coefficients are not in `parameter_ids`, so no study can name them as parameters
  (M03 D1), rather than being answered with a zero.
- **E3. The block's dormant convention.** At an exactly dormant inlet the block answers
  (X̃, ΔT̃) = (0, 0) with every derivative 0, so the rows give ξ = 0 and T_out = T_in exactly (spec
  §3.7); like B17's it acts only on Newton's direction from a dormant iterate. Rejected: X̃ at the
  box centre (β_X[0]), which changes nothing at a solution and reads as a prediction where none is
  made. Reversible by: `SurrogateBlock.values`/`jacobian`.
- **E4. R_T's orientation** is spec §3.3's `(T_out − T_in) − ΔT̃` (∂R_T/∂T_out = +1, M04.A12), not
  M02's `T_in − T_out + ΔT̂` (build log D45, its bitwise negation).
- **E5. The resolver is an explicit keyword.** `bind_revision_flowsheet(document, *, surrogates=)`
  (a `SurrogateResolver`: SHA-256 → manifest or `None`); the binder resolves and checks every
  surrogate instance before building, refuses `surrogate_manifest_mismatch(<instance>)`, and hands
  the manifest to `_c1_reactor_surrogate_of`. The registered builder, called without a manifest,
  refuses the same way. `RevisionBinding.surrogate_manifests` carries the checked manifests to the
  certificate. Rejected: an ambient (context-variable) resolver — implicit state the binder would
  read; a manifest argument on all 21 builders. The binder does not refuse a manifest whose verdict
  is not PROMOTABLE: spec §8.2 lists an unknown id, a mismatched hash and a failed checker;
  promotion is the replacement check's (WO-8).
- **E6. `SURROGATE-DOMAIN:<unit>`** (`verify/surrogate.py`) reads the converged state, the
  revision's wiring and `n_tubes`, and the manifest: z from the manifest's `input_map`,
  admissibility on the state's own X = ξ / n_N2,in and ΔT = T_out − T_in, the hard domain from the
  manifest's copy with the parent's predicates — no unit, block or row (R-016). Value e(z), tolerance
  `null`; `fail` with the refusal codes as its reason; `not_applicable` (`ZERO_FLOW`) at a dormant
  inlet; `fail` with no value when the input map is undefined. Placed after the table's last
  `bounds_and_domain` row (category-major order). Bound tokens: `T`, `P`, `H2_N2`, `inerts`,
  `F_tube`; several refusals in one message are joined by `; `.
- **E7. The verifier's entry.** `c1.reactor_surrogate` joins `pr_c1.REACTOR_MODELS` (M02's
  material and energy rules, the verifier's own ν, `REACTING_MODELS`) and `EXTERNAL_DUTY_MODELS`.
- **E8. Where the application injects the resolver.** `admission.surrogate_resolver(store, root)`
  reads the project's intact `surrogate_manifest` artifacts (`stored_surrogate_manifests`) only
  when a revision binds a surrogate. It is passed to every binding the project performs: `validate`
  (its structural stage and the free-class probe), `select_route`, `bind_route`, `route_structure`
  (`inspect_structure`), `admit_solve`, the solve job's route and re-bind, and a transaction's
  validation. Not to `reproduce_bundle`: a bundle is replayed from its own members, and a
  surrogate run's bundle does not carry the manifest, so its rerun is
  `rerun_unsupported(route_unbound(revision_eo))` until a bundle member carries it (K05/M05). The
  CLI's `validate` of a file has no project and refuses a surrogate-bound revision the same way.

## W27 Amendment 3 on wp/M04 — the surrogate's registration (2026-10-09)

Normative text: `docs/derivations/M06-W27-registration.md` §22.2, §22.4, §22.5 (register R-301, R-302).

- **E9. The registration.** `c1.reactor_surrogate` joins `_C1_SIGNATURES` (last, so
  `MODEL_SIGNATURES` and `MODEL_BUILDERS` keep the same order, t07_w5c), hence `MODEL_BASES`
  (`{pr-c1-v1}`), `list_models` and `MODEL_BUILDERS` (`_c1_reactor_surrogate`, which refuses: the
  binder hands a resolved manifest to `_c1_reactor_surrogate_of`, E5). WO-7's two autouse
  monkeypatch fixtures are removed. Measured at the registration: 0 of 450 cases differ in class or
  reasons from `hypothetical_v02`; live models and routes equal `hypothetical_v02_a3`'s; G14 PASS.
- **E10. The corpus revision's configuration** (§22.4 "the manifest's own"). The A19 manifest
  carries no N_tubes: its parent's requests are per tube (`per_tube_scaling`, spec §5.1). So the
  instance has N_tubes = 1 and the feed is `plan.request_of` at the centre of the manifest's
  `input_map` box (T 673.15 K, P 9.5e6 Pa, F 0.00715 mol/s). Registered as the file
  `benchmarks/m04/c1-surrogate.json` (`C1-SURROGATE-M04-v1`), in `m02_c1_corpus.FILES`, checked
  equal to `corpus_revision()` in `test_m04_wo7_surrogate_unit`. Rejected: M02's reactor
  revision's N_tubes = 1000 (not the manifest's); a code-only factory (the corpus is registered
  files). Reversible by: the file and its builder.
- **E11. WO-16i's `C1_MODEL_IDS` exclusion is removed** (`test_m06_w27_coverage`): the
  constructed-binder tests take Amendment 3's nine C1 ids and compare with `hypothetical_v02_a3`;
  F-A2-1's other answer with `binder_2587f14`'s C1 route plus the surrogate (§22.2). Rejected:
  keeping the exclusion, which `build_snapshot` refuses (`list_models-only
  ['c1.reactor_surrogate']`) once `list_models` serves 22 ids.
- **E12. Earlier packages' registry tests strip M04's model** (R-295's pattern):
  `m04_schema_support.M04_MODELS`, taken out before M02's eight in `test_t08_b50_surface_content`
  and before M02's C1 set in `test_m02_wo8_units`. `test_m02_join.REGISTERED` (the live table)
  gains the row; its R-280 (b) decomposition is unchanged (it strips every `c1.` entry).
- **E13. Re-taken values (old → new).** `list_models` SHA-256 `90d9da8e…9533e` → `f070fbe0c676…ea49b4`
  (22 models; §22.2 predicted `f070fbe0…`). `list_models` response fixtures (file SHA-256):
  `registered_models.json` `19b6c5e1…` → `d45fde36…`, `pin_missing_specifications.json`
  `004731f4…` → `c09ab92b…` (each +29 lines, the surrogate's entry only). t07_w5c gains the row
  `M02:C1-SURROGATE-M04-v1` (`binds 291932ea…`); every other row unchanged. Registry snapshot
  SHA-256 `0b2f4596…cc34` (at `4c57bce`) → `8f4bb0c8df0a…5343` (at `14a1397`; it carries
  `git_commit`), `coverage.json` re-taken there; `registration.json` `14ff19d9…` → `ba627342…` (WO-16i).
- **E14. The v0.2 support envelope lists the surrogate** (T08.A20 compares its `unit_models` axis
  with `MODEL_BUILDERS`): `benchmarks/t08/support_envelope.yaml` gains the member and its statement
  says twenty-two models (the surrogate's Q0–Q7 among the limitations); `scripts/t08_support_matrix.py`'s
  count check is 22; `docs/support-matrix.md` re-emitted. It is not in `synthetic_members`: it has
  no registered variant (`_synthetic_models` reads the variant registry). The evidence reference
  `test_the_registry_holds_the_twenty_one_models_each_on_its_own_basis` keeps its name. For the
  design lane: the statement is a public support claim (wording only; no claim on the surrogate's
  accuracy is added).

## Merge of main (c722df0, M02 merged) and WO-8 — the replacement check's surrogate side (2026-10-15)

- **E15. `surrogate_evidence`'s detail states the verdict first, then the parent relation or
  `parent_mismatch`, always both** (`"verdict=<v>; parent_mismatch: …"`). A27's A18 surrogate is
  NOT_PROMOTABLE *and* its parent is `m04-synthetic-rough-v1`, not the project's smooth parent, so
  in the project spec §11 describes, A27 ("detail `verdict=NOT_PROMOTABLE`") and A28 ("detail
  `parent_mismatch`, whatever that surrogate's verdict") can both hold only if the detail carries
  both reasons; the tests assert each as a `"; "`-separated item. Rejected: a precedence (either
  order breaks A27 or A28 read as equality). For the design lane: confirm, or say whether A27 meant
  a project bound to the rough parent. Reversible by: `replacement._surrogate_evidence`'s `reasons`.
- **E16. A surrogate side whose manifest does not resolve.** New side: `resolvable` fails
  (`surrogate_manifest_mismatch`) and `surrogate_evidence` fails too (no verdict can be derived).
  Old side: its parent is unknown, so a new surrogate is a `parent_mismatch` unless the old
  reference *is* its parent, and a new non-surrogate fails `replace_via_parent`. Rejected:
  `not_applicable`, which would let a replacement of an unresolvable surrogate pass the facet
  unjudged. Reversible by: the two `surrogate is None` branches.
- **E17. The derivatives exception excuses exactly the lost pairs the parent declares
  `unavailable`**, and only when the new reference equals the old manifest's `parent` (id,
  variant id, SHA-256). Any other loss still fails; when something is excused the detail starts
  `restores_parent_declaration`. Rejected: passing every loss on a rollback (ADR 0037 D3 names
  only the `unavailable` outlet-w.r.t.-inlet declaration).
- **E18. Shared rules, extracted rather than copied** (commit `c7bdd10`, inert):
  `revision_binding.resolve_surrogate` (the binder's §8.2 resolution at the reference level) and
  `manifest.derived_verdict` (the verdict re-derived from the stored metrics, which
  `check_manifest` compares and `surrogate_evidence` judges by; `promotion.verdict` is never
  read). Proof: `check_manifest` byte-identical on every fixture and five mutations.
- **E19. Merge: certificate limitations order.** `_finish` takes M02's `external` and M04's
  `appended`; M02's external limitations come first, then the surrogate's. No registered
  flowsheet binds both, so no existing certificate changes.
- **E20. Re-taken for the tenth facet.** M02's `model_replacement` fixtures
  (`scripts/m02_schema_fixtures.py --write`: one `not_applicable` facet appended to each) and
  `test_m02_wo11_promotion`'s all-pass expectations (`VARIANT_PASS`: `surrogate_evidence`
  `not_applicable` between two variants). The merge commit's single gate failure (M02's pin of
  `FACETS` to the schema enum, which M04 had already extended) closes here.
- **E21. A surrogate side's `synthetic`** in the report's `from`/`to` is the manifest's
  `synthetic` (reported, not judged, as for a variant).

## WO-9 — the synthetic loop end to end through a project (2026-10-15)

- **E22. The synthetic parents in a project are test-only injections**: the variant registry
  patch of M02 (`register_variants`) and `adapters.experiments.runner.InProcessBackend` replaced,
  for the module only, by `m04_synthetic_parents.backend_for()` (the synthetic parents by id,
  every other variant the real `InProcessBackend`), because their module is not package data.
  Admission, the `surrogate_study` and `solve` jobs, the replacement check with the project's
  resolver, the transaction, invalidation, routing and certification are the production path.
  The project is built once per module and copied per test (`shutil.copytree` of the closed
  project) so every test starts at the solved base revision. Rejected: a backend hook in
  production code for tests.
- **E23. Finding: the A19 fixture's environment fingerprint is stale.** The fixture names
  `08056d0c…`; both the job and `run_study` now give `7552e907…`, because the fingerprint hashes
  `models/c1/boundary.py`, which M02 changed (`7502515`, inert_min) after the fixture was taken.
  Every number is unchanged (predictor, calibration, evaluation, gradient, domain, promotion,
  qualifications equal; asserted in WO-9). The fixture still passes its checker and is not
  re-taken here: its SHA-256 is the W27 corpus resolver's entry (R-302) and enters W27's re-taken
  values. For the design lane: whether fixtures that carry a fingerprint are re-taken when the
  fingerprinted modules change.

## Amendment 2: WO-18 — the generator's box v2 and the b2 plans (2026-10-15)

- **E24. G5's it1 separation is asserted at 0.2084, not 0.2085.** b2-it1's held-out-to-training
  separation is 0.208490882 (b2-it2 0.180004412, b2-it3 0.143712880), it1's to 10⁻¹⁴ as the shared
  z-design makes it; §A2.5's 0.2085 is it1's registered 0.208491 rounded half up, which no b2-it1
  can reach (0.180 and 0.1437 happen to round down and are kept). The generator asserts
  B2_SEPARATION = (0.2084, 0.180, 0.1437) **and** that each b2 separation equals its it<i> twin's
  registered `min_inf_distance_training_to_heldout` to six digits (the carry-over the spec names).
  For the design lane: confirm, or restate G5's bound. Reversible by: one constant
  (`B2_SEPARATION`, `m04_reference.py`).
- **E25. Where the generator records Amendment 2.** `constants.box_v2` and
  `constants.reference_distributions` are appended at the end of `constants`; the G2 SHA-256 values
  and the measured G3–G6 numbers go to a new top-level member `amendment2` (`sources`, `box_v2`,
  `plans_b2`, `loop`), appended after `later_iterations`. Every pre-existing member is
  byte-identical to `9fbebb5`'s except `claims` (count 8634 → 11943 and the statement list), which
  describes the generator rather than registering a value, as at Amendment 1.
  `plan-it1/2/3.json` are byte-identical to `9fbebb5`'s.

## Amendment 2: WO-19 — box v2 in production (2026-10-15)

- **E26. Finding: §A2.3's "no schema change" does not hold; the manifest schema is widened.**
  `surrogate-manifest.schema.json` pinned `plan_id` to `^it[1-9][0-9]*(-prefix)?$` (the manifest
  and the `surrogate_study` body) and `reference_distribution.id` to `const m04-c1-box7-v1`, so a
  `b2-it1` request or manifest was schema-invalid. Now `^(b2-)?it[1-9][0-9]*(-prefix)?$` and
  `enum [m04-c1-box7-v1, m04-c1-box7-v2]`; the registry still refuses an unregistered id
  (`plan_not_registered`). The schema is M04's own (not on `main`). Served-schema snapshots
  re-taken for the five operations that embed the body (`SNAPSHOT_M04`: `submit_job`, `get_job`,
  `cancel_job`, `list_jobs`, `wait_job`); every other digest stands. For the design lane: confirm,
  or name another encoding of the family. Reversible by: reverting the E26 commit (and with it
  the b2 path).
- **E27. How production carries the box.** `plan.REFERENCE_DISTRIBUTIONS` (id → box, plan prefix,
  `synthetic_only`) and `REGISTERED_PLANS` (`RegisteredPlan`: iteration, counts, the plan's own
  synthetic-only flag, its P_ref) are the registries; a `SamplePlan` carries its P_ref id and box;
  the sampler functions take the box. The scaling z = (u − c)/h is a `Scaling` (c, h): the study
  fits and predicts with its plan's, `QuadraticSurrogate` carries the one it was fitted in, and
  `reactor.surrogate_of` reads c and h from the manifest's `input_map` (A44). `Scaling` defaults to
  box v1's only where box v1's tests and fixtures construct a surrogate or call `scaled` directly;
  every production call passes it. The checker's existing synthetic-only rule now also reads the
  P_ref's flag (a non-synthetic manifest on a v1 plan is a finding); the new rule compares
  `input_map.coordinates` by binary64 bit pattern and its finding begins `input_map`. Tests that
  used `it1`/`it2`/`it3` with `synthetic_parent=False` only for the plan's structure now pass
  `True`; A08's real-parent denominators use `b2-it1` (same counts). Box v1's values are unmoved:
  A02, A36, A17–A23, A26 and WO-9's fixture comparisons pass unchanged.
- **E28. Q1 and the exchangeability assumption name the study's own P_ref.** Spec §6.3's Q1
  reads `marginal over P_ref m04-c1-box7-v1; not pointwise`, a literal; on a `b2` manifest that
  would state a claim over the wrong distribution (ADR 0036 D1′: "marginal over its own P_ref and
  nothing else"). `required_qualifications(reference_id)` and `assumptions(reference_id)` put the
  manifest's `reference_distribution.id` there; the checker expects Q1 by that id. Box v1's
  strings are unchanged (`QUALIFICATIONS`, `ASSUMPTIONS`), so no v1 record moves. For the design
  lane: confirm. Reversible by: reverting the E28 commit.
