# ADR 0047 — The first liquid-capable mixture method: γ–φ with a Wilson liquid and an ideal-gas vapour, a library-only provider `wilson-ig-v1` (package S10)

**Status:** **Accepted, 2026-10-30**, marked by the build lane (V03 spec §6, R-876; the check is recorded in `docs/V03_DECISIONS.md` for S13's manifest). Proposed 2026-10-24 (design lane, `specifier`; register R-700…R-710). It became **Accepted** when:
- WO-S10-1 and WO-S10-2 have an evidence manifest with status `tested`, covering assertions S10.A01–A28;
- `s10_reference.py --check` passes (113 claims at this writing);
- the `reviewer` has passed the provider against spec §3–§5.

*Met 2026-10-30 (V03 WO-4):* `evidence/S10/c4f3751e…/manifest.json` (WO-S10-1/2) is `tested` with S10.A01–A45 passing, and the later S10 manifests `f974cc87…` and `f6f27c3f…` are `tested`; `docs/derivations/scripts/s10_reference.py --check` at `wp/V03` prints "113 claims hold; reference_values.yaml matches" (exit 0; the RC runs it again at C); the reviewer passed the provider (`docs/reviews/S10-review-wo1-wo2.md`, nothing a must-fix; `docs/reviews/S10-review-final.md`, sound).

Three things are **not** acceptance conditions; each is a separate result recorded by its own entry:
- the real records (WO-S10-3);
- the IDAES/DWSIM comparisons (WO-S10-4/5);
- the empirical validation (WO-S10-6).

Shipping the real records is Frank's decision (spec §12, Q-F3).

**Date:** 2026-10-24
**Author:** design lane (`specifier`), S10 (provisional id), brief `docs/briefs/S10-liquid-mixture-properties.md`.
**Normative text:** `docs/derivations/S10-spec.md`. The machine-readable expectations are
`benchmarks/s10/reference_values.yaml`, produced by `docs/derivations/scripts/s10_reference.py` (`--check`) from
`benchmarks/s10/verification-records.yaml`.
**Amends:** nothing. No frozen `Protocol`, schema, quantity kind or check category changes (§Consequences C1).
**Affected requirements:**
- D08: real provider conformance;
- D04: data rights;
- D19: independent references, with matched-model inputs;
- R01: cases and cross-implementation comparisons;
- U02: library-only limitations (R-568, R-569);
- blueprint §2.2 ("selected nonideal vapour–liquid systems after property conformance"), §6.1–§6.3 and §14.4.

**Affected packages:**
- S10 implements this ADR.
- S10-C, a provisional follow-on, takes the consumers: the PH flash and the column (spec §10).
- S03's refusal S11 is unchanged by this ADR.

**Companions:**
- ADR 0001 D2–D5 (state `nTP-v1`, zero flow, conventions);
- ADR 0005/0012 (phase contract), and blueprint §6.3 A01;
- ADR 0022 and ADR 0026 (the cubic route and why it ended vapour-only);
- ADR 0043/0045/0046 (library-only providers);
- the C12 rights lessons (`docs/C12_DECISIONS.md`, `docs/l01-rights-check.md`).

## Context

The project has no route to a realistic liquid mixture:
- SYN-001 is ideal, with K depending on (T, P) only.
- `pr-c1-v1` has a liquid only for pure NH₃.
- `pr-lib-v1` is vapour-only.
- `iapws95-v1` and `coolprop-heos-v1` are pure fluids.

R01 needs 100+ cases and 25 cross-implementation comparisons. Blueprint §6.2 admits nonideal methods "one validated
adapter or implementation at a time, driven by cases"; §6.1 says an excess-Gibbs model alone is not a property package;
§6.3 requires stability to be reported as `STABLE_WITHIN_TESTED_SCOPE`, `UNSTABLE` or `UNKNOWN`. These labels exist
nowhere in the code today. The cubic liquid route stopped for three reasons (ADR 0026):
- IDAES's full PR VLE fell onto the trivial solution of a symmetric tangent-plane test.
- No open k_ij existed for the pairs.
- A feed-based stability test misclassified a near-pure feed.

## Decision

**D1. The method** (spec §3). γ–φ, built from one Gibbs-energy potential. Its parts:
- **Liquid:** ln f_i^L = ln(x_i γ_i(x) P_i^sat(T)). The Wilson activity model has **constant** Λ_ij > 0. The pure-liquid
  reference is the ideal-gas vapour at P_i^sat. There is no Poynting factor and no φ^sat.
- **Vapour:** an ideal gas.
- **Vapour pressure:** ln(P_i^sat/Pa) = a + b/θ + c ln θ + d θ², with θ = T/1000 K (the DIPPR-101 form with E = 2).
- **Ideal-gas properties:** the NASA-7 low-range polynomials.
- **Caloric terms:** follow from the same potential.
  - h_i^0L = h_i^ig − R T² d ln P_i^sat/dT (Gibbs–Helmholtz, i.e. Clapeyron with an ideal-gas vapour and no liquid
    volume).
  - g^E/RT does not depend on T, so h^E = 0, exactly and consistently.
  - It does not depend on P, so v^E = 0.

  No vapour-pressure correlation is paired with an independently chosen liquid c_p or ΔH_vap. Blueprint §6.2's
  consistency requirement is therefore met by construction, and generator claims CONS-* check it.
- **Provider id:** `wilson-ig-v1`.

**D2. Stability** (spec §4).
- **The convexity theorem.** For any Λ_ij > 0, the Wilson liquid's molar Gibbs energy of mixing is strictly convex on
  the simplex. The proof uses the joint convexity of x ln(x/q), with q = Λx. The ideal gas is strictly convex as well.
  It follows that:
  - a stable state has at most one liquid and one vapour, so no LLE is possible;
  - each trial-phase tangent-plane distance has a single stationary point, and that point is its global minimum;
  - any converged L–V common tangent is the global Gibbs minimum within the model;
  - the two phases use different models, so the trivial solution that blocked the PR route cannot occur.
- **The stability analysis** consists of two tests:
  - one closed-form vapour-trial distance, tm_V = 1 − Σ z_i K_i(z);
  - one strictly convex liquid-trial minimisation, solved by successive substitution.
- **Labels** (scope id `S10-tpd-v1`; resolution ε_tpd = 10⁻¹⁰, as R-540 for `pr-lib-v1`):
  - `STABLE_WITHIN_TESTED_SCOPE`: the deciding distance is ≥ −ε_tpd, or the converged L–V tangent holds.
  - `UNSTABLE`: the deciding distance is < −ε_tpd.
  - `UNKNOWN`: a search reached its cap, or the state is dormant or out of domain.

  "Tested scope" names the phase models (one Wilson liquid, one ideal gas), ε_tpd and the convergence tolerance. It does
  not name a set of initial guesses: the convexity theorem makes the search global within the model.

**D3. The TP flash** (spec §5.3). Request checks come first, in `pr-c1-v1`'s order. The flash then proceeds:
- If tm_V ≥ −ε_tpd, the result is LIQUID.
- Otherwise the liquid-trial search runs. If tm_L ≥ −ε_tpd, the result is VAPOR.
- Otherwise the result is two-phase. The flash runs successive substitution on K, with a bracketed Rachford–Rice solve
  inside each step, starting from K(w*).
- Registered constants: δ_K = δ_SS = 10⁻¹³ and SS_MAX = 1000.
- There is no branch for a single flowing component. The step order decides ties, liquid first.
- Reaching a cap returns `not_converged` with `UNKNOWN`, never a split.

**D4. The contract** (spec §5). The frozen `PropertyProvider` protocol is used unchanged.
- **Properties:** `h` (phase molar enthalpy) and `lnphi_<c>`, with ln φ_i^L = ln γ_i + ln(P_i^sat/P) and ln φ_i^V = 0.
  This lets a φ–φ consumer read the method without knowing it is γ–φ.
- **Derivatives:** order 1 in `T`, `P` and `n_<c>`. Zeros are returned as answers (`0.0`), not omitted.
- **Phases and flashes:** phases `("LIQUID", "VAPOR")`; flashes `("TP",)`. A flash that asks for derivatives is refused
  (`flash_derivatives_unsupported`, as for `pr-c1-v1`).
- **The stability label** travels in `FlashResult.message` under a registered grammar, `stability: <LABEL>; scope:
  S10-tpd-v1; …`.
- **A full report** comes from a provider method outside the Protocol, `stability(state, phase, context) ->
  StabilityReport`. The new type lives in `thermo/stability.py`.
- **No PH flash in the provider.** The frozen `FlashRequest` has no enthalpy field. The PH flash belongs to the
  consumer package.

**D5. The reference convention** (spec §3.1). The real records use `WILSON-IG-ref-v1` and the verification records use
`S10-VER-ref-v1`. Both are formation data: h_i^ig(298.15 K) = Δ_fH_i°, where the NASA records' Δ_fH_i° is the low-range
polynomial's own H(298.15 K) (its a6 term).
- Neither convention is added to ADR 0011 D2's reaction-consistent set.
- Streams never mix with another convention (ADR 0001 D5.2). This includes SYN-001's, whose datum is the pure liquid at
  300 K.

**D6. Verification on synthetic records** (spec §6–§7). The closed-form verification uses three invented components:
- data set `S10-verification-v1`;
- all coefficients nonzero;
- Λ pairwise distinct and asymmetric;
- one azeotropic pair.

It therefore never waits for rights-pending data. The provider takes its records path as a constructor argument, and
`data_sha256` distinguishes the two sets. Tolerances are derived from measured binary64 floors and from the SS
error-amplification factor; spec §7 gives the derivation.

**D7. Real data** (spec §9, WO-S10-3).
- **Chemistry:** methanol, ethanol and water. This is Frank's choice; the recommended default is Q-F1.
- **Ideal-gas data:** NASA TM-4513 via Cantera 3.2.0 (C12 row RC-03: permitted with conditions).
- **Vapour pressure:** fitted by the project's own script to saturation pressures that CoolProp 8.0.0 computes from the
  reference equations of state, with water cross-checked against `iapws95-v1`.
- **Wilson Λ:** fitted by the project's own script to published isobaric binary VLE data.
- **No CAS RNs** (C12 F-4, RC-07).
- The records are not package data until a C12-style rights check is complete and Frank decides.

**D8. Independent references** (spec §8). These give numerical verification, not validation.
- **Primary:** IDAES 2.13 `activity_coeff_prop_pack`, Wilson model, with matched inputs:
  - `vol_mol_comp` = 1, and **τ[j,i] = −ln Λ_ij**. IDAES's index convention is transposed; claim IDAES-MAP checks it.
  - The DIPPR vapour-pressure form replaces IDAES's Wagner form in its three places.
  - The liquid and vapour enthalpy polynomials reproduce ours exactly.
  - A pre-registered smoothing-ε and solver ladder.
- **Secondary:** DWSIM 9.0.5's Wilson package, TP flashes only. It may be `NOT_COMPARABLE`.

**D9. Empirical validation is separate** (spec §9.5). Its bands are pre-registered here, before any data is
transcribed. The held-out data are:
- the ternary isobaric data;
- isothermal binary data;
- the implied pure-component ΔH_vap and c_p^L, compared against the reference equations of state.

The quality of the fit is reported, and never called validation.

**D10. Consumers** (spec §10). The provider is library-only by default (Frank, Q-F2):
- it is registered in `LIBRARY_ONLY_PROVIDERS`;
- refusal S11 of the column stays;
- S10-C takes the PH flash and the column, with an `architect` pass, because K(x) changes the cascade's Jacobian
  structure.

**D11. LLE is out of scope.** The frozen `FlashResult` carries one liquid, and the Wilson model cannot split a liquid
anyway. An LLE route needs an interface ADR (spec §13, F-1).

## Alternatives considered

- **(b) A cubic EOS liquid regime with k_ij.** Rejected for S10. ADR 0026's blockers still hold:
  - the symmetric-model tangent-plane test has a trivial solution;
  - no open, cited k_ij exists for polar pairs;
  - van der Waals one-fluid mixing represents alcohol–water badly unless an excess-Gibbs mixing rule is added, and that
    rule brings a γ model in anyway.
- **NRTL first.** NRTL's G^E can be non-convex, so it can predict a false LLE. Its tangent-plane distance can have
  several minima, which makes stability depend on multi-start and makes `UNKNOWN` common. The extra parameter α adds
  data. Even a true LLE could not be carried by the frozen interface. NRTL remains the planned second γ model, to enter
  when an LLE-driving case and an interface ADR exist. The note in ADR 0022 ("the methanol–water NRTL case") is an
  alternative's description there, not a decision.
- **UNIQUAC.** Needs structural r, q parameters (more data, more rights rows) and can also split. No case needs it yet.
- **Temperature-dependent Λ_ij,** for example ln Λ_ij = a_ij + b_ij/T. This is better physics, giving h^E ≠ 0, but:
  - IDAES's package carries a constant τ and no h^E, so a column comparison would need user code;
  - an h^E path needs its own tests.

  Deferred to a `v2` provider version, which will be new identity and new tests, not a silent edit.
- **A Poynting factor and a liquid volume.** These need v_i^L data. Both reference tools omit the factor in their
  Raoult forms, which was T06's comparison obstacle. Over the domain its effect is at most v_max P_max/(R T_min) =
  4.8 × 10⁻³ (spec §3.7). Liquid `v` is refused with `unknown_property`.
- **An independently selected liquid c_p and ΔH_vap.** Inconsistent with the equilibrium potential, and blueprint §6.2
  warns against exactly this pairing. The consistent model's c_p^L error is measured instead (VAL-3).
- **Antoine vapour pressure.** Simpler, but its curvature gives a poor implied c_p^L: about −14 % for water at 373 K by
  the specifier's estimate. That estimate is not a registered claim; VAL-3 measures the chosen form. The c ln θ term is
  the constant-Δc_p (Kirchhoff) term, so it carries the c_p^L physics.
- **The IDAES Wagner 3-6 form,** to make IDAES native. Rejected because:
  - its implied h^L is not a polynomial, so IDAES's enthalpy would need editing instead;
  - DWSIM's support for it is unknown, while DWSIM's eq. 101 is DIPPR-101.
- **Widening `FlashResult` with a typed stability field.** Cleaner for consumers, but it is a frozen field-set change.
  It is recorded as finding F-2, with the default "not now".
- **Ethylene glycol–water,** ADR 0022's other candidate. NASA TM-4513 carries no C₂H₆O₂ (checked in Cantera 3.2.0's
  `nasa_gas.yaml`, SHA-256 `4de6199d…`). Its ideal-gas data would then need a source whose rights are unresolved.
- **Real Λ values from DECHEMA or a tool's databank.** Rejected for rights:
  - DECHEMA is a copyrighted compilation;
  - DWSIM's `nrtl.dat`/`wilson_bips.csv` are embedded under GPL-3/Artistic-2.0 with unknown upstream.

  Fitting our own Λ to primary data leaves only the RC-01-type question about published numbers.

## Consequences

- **C1.** No frozen interface changes.
  - New types and methods sit outside the Protocol (`StabilityReport`, `stability()`).
  - The message grammar is a provider convention.
  - `docs/interfaces-frozen.md` §3 gains a note naming the new conventions. This is a finding (spec §13 F-3), written
    when the ADR is accepted.
- **C2.** `syn001`, `pr-c1-v1`, `pr-lib-v1`, `iapws95-v1` and `coolprop-heos-v1` stay byte-identical (S10.A26), so no
  existing identity moves.
- **C3.** The registrations follow R-568 and R-569:
  - `LIBRARY_ONLY_PROVIDERS` gains `"wilson-ig-v1": "S10"`;
  - U02 gains a typed limitation row;
  - `benchmarks/registry.yaml` gains an S10 family.
- **C4.** Limitations are stated, not fixed:
  - The vapour is an ideal gas. The implied ΔH_vap is high by roughly 1/Z^V_sat, and its T-slope error shows in c_p^L,
    which VAL-3 measures.
  - h^E = 0, so the real excess enthalpy of alcohol–water is absent.
  - Constant Λ extrapolates in T.
  - There is no liquid volume and no LLE.
  - The domain is low-pressure only (P ≤ 2 × 10⁵ Pa).

## Migration impact

None. No existing record, identity, registered value or fixture moves. The provider is new and library-only.

## Acceptance evidence

- `python docs/derivations/scripts/s10_reference.py --check`: 113 claims, the YAML byte-identical.
- S10.A01–A28 pass in the tests that WO-S10-1/2 add, and the evidence manifest is `tested`.
- A `reviewer` pass on `thermo/wilson_ig.py` and `thermo/stability.py` against spec §3–§5.
- Separately, not for acceptance:
  - WO-S10-3: A30–A35, real records with `s10_records.py --check`;
  - WO-S10-4/5: A40–A45, comparison records and a `verdict`;
  - WO-S10-6: A50–A53, the validation report.
