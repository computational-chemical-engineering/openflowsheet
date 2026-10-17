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

## Amendment 2: WO-20 (2026-10-15)

- **E29. Finding: A47's evidence comparison differs outside E in four members.** The A19 job's
  ModelEvidence differs from `model_evidence/valid/a19_smooth_prefix.json` at `data[0..3].keys_sha256`
  only (everything else, R1/R2 floats included, is equal within the policy floors). These are the
  evidence's copies of the per-split key-list digests: §A2.12 puts `splits.<s>.keys_sha256` in E
  for the manifest and names only `subject.artifact_ref` in addition for the evidence. Not added
  to E: the test allows exactly these four members, only where each equals the run manifest's own
  `splits.<s>.keys_sha256` (asserted), and still demands E-equality at equal fingerprints. For the
  design lane: name `data[*].keys_sha256` in the evidence's E, or rule otherwise. Reversible by:
  reverting the E29 commit (the evidence comparison then fails as specified).

## WO-11 — iteration 1 of the real reactor, `b2-it1` on v3 (2026-10-15)

Run at `43d6557` (gate green: 8645 passed, 31 skipped). `prepare(v3, "b2-it1")` admits the plan:
632 distinct requests, all inside v3's hard domain (inerts 0.03771…0.06950 ≥ 0.035; T 653.172…
693.068 K; P 9.000154…9.994113 MPa; H₂/N₂ 2.50064…2.99990; per-tube flow 0.005003…0.008592 mol/s).
Pre-warm (`scripts/m04_prewarm.py`, 16 workers, budget 632, retries 2): 632 misses, one round,
0 without result, 0 retries, 0 incomplete; with the study from cache and A41's 8 serial bypass
repeats, 4467 s wall on a shared host (load ≈ 80–96 on 48 threads from other worktrees' runs;
§A2.6 predicted ≈ 27 + 5 min unloaded). Record: `benchmarks/m04/wo11-b2-it1-v3/` by
`scripts/m04_wo11_record.py` (exit 0).

- **Verdict NOT_PROMOTABLE**, NP = [`band_not_finite`], IE = []. 26 of 632 registered experiments
  are deterministic `reactor_not_accepted(certificate)` ("the evaluation reached no accepted
  state", spec §8.7): calibration 5/118, test 18/300, training 3/144, gradient stencils 0/70.
  k = 114 of n = 118 tolerates n − k = 4 null scores, so q̂ = +∞. The failures are spread over
  T 654.6…693.1 K, P 9.01…9.86 MPa, H₂/N₂ 2.51…2.99, inerts 0.040…0.068 — not at the S1 cliff
  at 653.15 K. Overall 4.1 %; §A2.6's table gives P(band finite) = 0.29 at 5 %.
- **Reported, not judged:** the 113 finite calibration scores are ≤ 0.316 and the 282 finite test
  scores ≤ 0.292 (282/300 = 0.94 within width, h_min = 279); test max |e_X| = 7.31 × 10⁻⁴
  (RMS 1.53 × 10⁻⁴), max |e_ΔT| = 0.323 K (RMS 0.072 K); gradient max e = 0.0360 (ρ_g = 0.25),
  all 5 centres complete; `parent_extrapolated` 0; inadmissible predictions 0; admissibility
  margin 47.6.
- **A31** holds: 632 executed requests, 0 outside the plan; both schemas valid; the evidence names
  the manifest (`d65bb022…`); the checker accepts it; the derived verdict equals the stored one.
  **A32** holds: the re-submitted study with budget 0 gives cold 0, hits 632, the same manifest
  SHA-256, 0 new attempts. **A41** holds: `repeat_bitwise_equal` true for test[0..7].
  **A33** is not run (A31 is not PROMOTABLE); Q-A2.1 stays open without its record.
- **E30. Where WO-11's record lives.** `benchmarks/m04/wo11-b2-it1-v3/{record,manifest,evidence}.json`
  (67 KB), committed beside M02's `g12-real-loop-v3.json` pattern; the project itself stays under
  the ignored `evidence/M04/artifacts/wo11/`. The record is produced by a committed script so its
  checks are re-runnable on the project. Rejected: artifacts only (nothing committed would carry
  the verdict's numbers for WO-12's manifest). Reversible by: reverting the E30 commit.
- **E31. Finding: a project opened by a relative path keys experiments differently.** The pymrm
  child's fingerprint replaces the attempt directory in `env_allowlist` by `${ATTEMPT_DIR}`
  (`adapters/pymrm/child.py:422`, `value.replace(str(attempt), …)`), but a project opened as
  `evidence/M04/…` (relative) passes a relative `HOME`, which the child's absolute `attempt` does
  not match. The literal path stays in the fingerprint, so its SHA-256 — and every experiment key —
  changes per attempt directory: a study run that way saw 632 misses on a fully warmed cache and
  refused (`budget_below_plan`, nothing written; job-000642 in the WO-11 project). With absolute
  paths all 642 handshakes of the run share one fingerprint (`dfce4150…`). Not fixed here (WO-11 is a
  run, not a change): `m04_wo11_record.py` resolves its path; `m04_prewarm.py` does not and was
  run with an absolute one. For the build lane: resolve the project
  path in `LocalApplication.open/create` (or normalise in the child by `Path.resolve()` on both
  sides) with a test that a relative and an absolute open give one key.

## E31's fix — the launcher resolves the attempt directory (2026-10-15)

- **E32. The attempt directory is resolved where it is handed to the child.** `launch`
  (`adapters/external/launcher.py`) now calls `attempt_dir.resolve()` after creating it, before
  building the scrubbed environment. Root cause: the launcher spawns the child with
  `cwd=attempt_dir` and sets `HOME`/`TMPDIR` to the same path; a relative path is then relative to
  the wrong directory (it names `<attempt>/<attempt>`), and the child — which reads its attempt
  back as `os.getcwd()`, the physical path — cannot substitute it. Resolving (not only
  `absolute()`) also covers a symlinked project path, which `getcwd` would report resolved.
  Rejected: resolving in `LocalApplication.open/create` (fixes one caller; `ExperimentRunner`
  over an `ExperimentStore` on any relative root, or a direct `launch`, would still break), and
  normalising inside the child (the child would then paper over a wrong `HOME` it was given).
  Inert at absolute, symlink-free paths: `resolve()` is the identity there, as WO-11's 642
  handshakes sharing one fingerprint already show.
  Proof (v3, this host): a direct handshake from a relative and from an absolute attempt
  directory both give `dfce4150194f…beaaf`, WO-11's fingerprint; without the fix the relative one
  gave `b7d475a5d38e…11fb4`. The WO-11 project opened by its *relative* path, study re-submitted
  with budget 0 (job-000650, `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=1`): cold 0, hits 632, misses
  0, 0 new attempts, manifest `d65bb0225f36…1717` — the E30 record's. Tests:
  `test_m02_experiments.py::test_e32_a_relative_and_an_absolute_open_give_one_key` (one key and
  one fingerprint through `LocalApplication.open` either way, synthetic child) and
  `test_m02_kill_chain.py::test_e32_a_relative_attempt_directory_is_the_absolute_ones_fingerprint`
  (absolute, relative, symlinked); both fail without the fix. Reversible by: reverting the E32
  commit.
- **E33. Finding: the study's manifest depends on the BLAS thread count.** Re-submitting WO-11's
  study (budget 0, all 632 hits) under this shell's default threading gives manifest
  `908cbe2f4d94…2e47`, reproducibly (jobs 000645–000649, 000651, with or without E32, relative or
  absolute path, also through `m04_wo11_record.py`, whose A32 then reports `manifest_bitwise_equal`
  false); with `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=1` it gives the record's `d65bb022…`
  (job-000650), and with 8 threads `908cbe2f…` (job-000651). The difference is last-ulp only:
  predictor coefficients, 2 calibration and 7 test scores (≤ 10⁻¹² relative), the error RMSs
  and gradient errors (≤ 10⁻¹⁵ relative); the `promotion` block is identical, and E30's printed
  numbers are unchanged. So
  WO-11 ran single-threaded, and A32's bitwise manifest equality holds at a fixed thread
  environment only. Not fixed (replay identity is the design lane's): either the study pins its
  BLAS threads (e.g. `threadpoolctl` around the fit) or the manifest records the thread
  environment it was computed under. For the design lane, with WO-12's review.

## WO-12 — the evidence manifest (2026-10-15)

- **E34. The manifest is generated, one check per assertion.** `scripts/m04_evidence_manifest.py`
  (M02's pattern) reads A01–A47 and §15's W23 rows from the specification, adds §18's and §19
  A2.13's rows (each amendment sentence must be present verbatim), runs `tests/test_m04_*.py` once
  and assigns each `test_aNN…` node to M04.ANN (the other nodes are `M04.supporting`), decides
  A31, A32 and A41 from WO-11's committed record (manifest and evidence by SHA-256), and lists the
  register entries whose "Decided by" names M04 with the ADRs they cite. A33 is `not_applicable`
  on a non-PROMOTABLE A31 (it would be `fail` on a PROMOTABLE one, since no A33 record exists);
  status is `tested` only when every other check is `pass`. Per N6 the real verdict does not
  enter the status; it is the first limitation, written from the record's numbers. Assertions in
  no W23 row (A09, A10, A34, A35, A41) still have their checks. Rejected: a hand-written JSON
  (nothing would stop an assertion being left out). The manifest's four limitations and its
  `not_applicable` A33 are classified in `benchmarks/t08/support_envelope.yaml#harvest` (T08.A21)
  as class P — they stay in the manifest, as M02's do — by `--harvest-from`, added after the
  evidence commit `a9566a6` (it reads the manifest, never rewrites it). DECISION: class P for the
  real verdict too, rather than an envelope row (E) — the envelope's rows are the design lane's;
  reversible by reclassifying the harvest entry. Status `tested`: 57 of 58 checks pass, A33
  `not_applicable`; gate at `a9566a6` GATE PASS, 8647 passed, 31 skipped. Reversible by:
  reverting the WO-12 commits.

## Amendment 3 — the review's build-lane actions (2026-10-15)

- **E35. An unresolved surrogate does not enter a revision either.** §A3.1 rejects a surrogate
  that no replacement judges unless its re-derived verdict is PROMOTABLE; it does not say what
  happens when the manifest does not resolve (no verdict exists). DECISION: rejected too,
  `surrogate_not_promoted(<instance>)`, cause `the manifest does not resolve
  (surrogate_manifest_mismatch)`. Reason: the replacement path already rejects an unresolved new
  surrogate (`resolvable` and `surrogate_evidence` fail), and admitting it would let the head bind
  a NOT_PROMOTABLE manifest unchecked the day a study job stores one with that (deterministic)
  hash. The same rule judges carried-over instances, so no revision committed after Amendment 3
  holds an unpromoted or unresolved surrogate. Cost: §8.2's `surrogate_manifest_mismatch` is now
  reachable at the project level only for a revision written before Amendment 3; WO-7's project
  test keeps it by writing such a revision through the store. Alternative: leave unresolved
  manifests to the binder (validation not READY, solve refused). Reversible by: reverting the E35
  commit.
- **E36. The fit's one-thread pin is in-tree, not `threadpoolctl` (SF1, R-362).** R-362 leaves the
  mechanism to the build lane: `threadpoolctl` as a declared dependency, or an equivalent.
  Declaring it changes `requirements.lock`, whose SHA-256 is T08's registered `LOCK_SHA256`
  (`ead4edf1…`, `tests/test_t08_w4_rc.py`, T08.A19) and every run manifest's
  `environment.lock_sha256` (the replay class of every earlier bundle); the lock has not moved
  since v0.1.0. DECISION: the equivalent, `studies/surrogate/blas.py`: `single_blas_thread()`
  finds the loaded OpenBLAS libraries in `/proc/self/maps` (`RTLD_NOLOAD`), sets each to one
  thread through its own `*_set_num_threads*` and restores the previous count; here it drives
  NumPy's `libscipy_openblas64_` and SciPy's `libscipy_openblas` (both found, 48 → 1 → 48).
  Process-wide like `threadpoolctl`, which is safe because one job computes per interpreter.
  Off Linux, or under another BLAS, it is a no-op (documented; A1.3's platform classes govern).
  `fit_quadratic` runs its SVD, QR, triangular solve and products inside it. Proofs: A49 (child
  processes at `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS` 1 and 8, N = 141 synthetic rows: unpinned
  coefficients differ, pinned are bitwise equal and equal to the unpinned one-thread bits); WO-11's
  study re-submitted from cache (`m04_wo11_record.py` to a scratch directory) gives manifest
  `d65bb0225f36…` with cold 0 / 632 hits / 0 new attempts both at one thread (job-000652) and at
  the shell's default 48 threads (job-000653), where E33 gave `908cbe2f…` before the pin.
  Alternative: `threadpoolctl==3.6.0` with a new lock and T08 constant (a design-lane/release
  call). Reversible by: replacing `single_blas_thread` with `threadpoolctl.threadpool_limits(1,
  "blas")` in `quadratic.py` and deleting `blas.py`.
- **E37. R-365's class B points to T08 §6.3's B10.** R-365 files the A33/Q-A2.1 limitation and
  the `not_applicable` A33 check as B ("close with A33's record"), but §6.3 (T08 release spec,
  design lane's) has no M04 id, and the harvest check requires one. DECISION: `to: [B10]`, the
  handed-on follow-ups, with the note naming R-366's closure. The real verdict is E with the new
  envelope row L43 (R-365's text), which the `unit_models` statement now cites (E14, R-365's
  wording). Alternative: a new §6.3 id, written by the design lane. Reversible by: changing the
  two `B10` pointers in `scripts/m04_evidence_manifest.py` and re-running `--harvest-from`.
- **E38. A48–A50 enter the manifest from §20's prose, in no W23 row.** §20 states them as
  sentences, not `**M04.Ann**` lines, and names no W23 row for them. DECISION: the generator's
  `ADDED` table reads each statement from the specification (whitespace-normalised, refused if
  absent) and gives each its own check; `M04.W23.not_in_a_w23_row` lists them. Alternative:
  join them to "Promotion and rollback" (A48), "Frozen splits/transforms" (A49) and
  "Insufficient-data outcome" (A50) — a W23 placement is the design lane's. Reversible by: an
  `AMENDMENTS` row per placement.
- **Evidence after Amendment 3.** `evidence/M04/8df0ea7c6248ebe1fbc265b3f39f9fdd9c0a0fa5/manifest.json`
  (the merge of `origin/main` at `8df0ea7`): status `tested`, 60 of 61 checks `pass`, A33
  `not_applicable` (A31 NOT_PROMOTABLE); A48 5 nodes, A49 1, A50 2, A24 16, all passed; gate at
  `8df0ea7` GATE PASS, 8664 passed, 31 skipped. Harvested with `a9566a6`'s manifest by
  `--harvest-from` (10 entries; classes of R-365, E37). Not `reviewed`.

## Follow-up: main's CI on the hosted runners (`wp/M04-ci`)

`ci` failed on every push since 2026-10-16 (run 38975380701; last green 38810003221): three A40
tests on `ubuntu-latest` and `default-install`, A49 on `ubuntu-24.04-arm`, A35 on both `check`
runners. Locally (48 threads) all passed. Each is a machine precondition or a comparison wider than
the spec's claim; no tolerance moved and no case was removed.

- **E39. A40's script path needs four physical cores; the refusals do not.** R-250 caps
  `m04_prewarm.prewarm`'s `max_workers` at `physical_cores()` (2 on `ubuntu-latest`), and A40
  names `max_workers = 4`, so `ValueError` was raised before anything ran (the `cold_experiments
  == 199` line in the log is the traceback's context, it held). DECISION: the script-path test
  skips, with the reason, where `physical_cores() < 4`; the two refusal tests run at
  `min(4, physical_cores())`, since a refusal is decided before any worker exists and their claim
  names no count. A40's A19-bitwise half (four spawned processes, no cap) runs everywhere.
  Alternative: run the script path at 2 workers on small hosts (not A40's parameter). Reversible
  by: reverting the E39 commit.
- **E40. A49's negative control is a precondition.** On `ubuntu-24.04-arm` the unpinned fit at 1
  and 8 BLAS threads agreed bitwise at N = 141, so `unpinned_1 != unpinned_8` failed: the control
  cannot tell the pin from no pin there. DECISION: the claims (`pinned_1 == pinned_8`,
  `pinned_8 == unpinned_1`) are asserted first, everywhere; where the control is vacuous the test
  then skips with the reason instead of passing. Alternative: search a size per host that splits
  (spec: "if no synthetic size reproduces the difference, the opt-in real record is used").
  Reversible by: reverting the E40 commit.
- **E41. A35's rounded float comparison is scoped to the machine class the fixtures were recorded
  on.** `stable` rounds floats to 10 significant digits; rounding is not a tolerance, and a score
  that is a small difference of two predictions keeps fewer digits than binary64 carries.
  Reproduced locally with `OPENBLAS_CORETYPE=Sandybridge|Nehalem|Prescott`: one leaf differs,
  `evaluation.scores[7]` 4.3685482476500205e-05 (fixture) against 4.36854824575524e-05, 1.9e-14
  apart, where A1.3's R1/R2 floor is 1e-10 score units. Spec §18 A1.3 promises R1/R2 for these
  floats across platforms and R0 (conditional; A19 is not near threshold, A37) for every
  non-float member; it claims no cross-platform 10-digit agreement. DECISION:
  `m04_schema_fixtures.RECORDED_ON = "x86_64/Haswell"` (`machine_class()`: `platform.machine()`
  and the OpenBLAS kernel name of NumPy's and SciPy's libraries); on that class the comparison is
  unchanged; on another the non-float members are compared exactly and the test then skips the
  floats with the reason; the failure message lists each differing leaf with both raw values.
  `--write` writes nothing off the recorded class. The committed fixture is unchanged (M05's
  LOOP-S record cites it). Alternative: compare floats off-class under A1.3's per-rule R1/R2
  floors from `benchmarks/m04/numerical_policy_surrogate.yaml` (needs the floor units, e.g. w_o,
  resolved per rule; R-253 says no comparator reads that table yet — a design-lane call).
  Reversible by: reverting the E41 commit.
- **E42. CI prints skip reasons.** Run 38992908629 (E39–E41) is green on both runners, but its
  logs show counts only (`pytest -q`): which test skipped for which machine reason is not on
  record. Counts reconcile — `ubuntu-latest` 8613 passed / 99 skipped (was 8609 / 5 failed / 98),
  `ubuntu-24.04-arm` 8584 / 98 (was 8584 / 2 failed / 96), `default-install` 8356 / 326 (was
  8356 / 3 failed / 323) — but `default-install`'s +3 skips with +0 passes is not what E39 alone
  predicts (+2 passes, +1 skip) and cannot be read from counts. DECISION: `PYTEST_ADDOPTS=-rs`
  on the `check` job's step and `-rs` on `default-install`'s pytest; CI-only, the local gate and
  its summary line are untouched. Reversible by: reverting the E42 commit.
