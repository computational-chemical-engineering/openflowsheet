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
