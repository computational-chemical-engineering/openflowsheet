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
