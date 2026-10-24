# S05 — IAPWS-95 pure water: derivation, domain, refusals and test specification

**Package:** S05 (brief C10; branch `wp/C10`). **Lane:** design (`specifier`) for this document; build for WO-S05-1/2.
**ADR:** 0045 (Proposed). **Register:** R-585…R-594. **Decisions:** `docs/C10_DECISIONS.md`, copied in §13.
**Generators:**
- `docs/derivations/scripts/s05_reference.py`: project venv, mpmath 1.3.0 at 50 digits, `--check`; it writes
  `s05_reference.json`.
- `docs/derivations/scripts/s05_crosscheck.py`: scratch venv only, with CoolProp 8.0.0, iapws 1.5.5 and mpmath 1.3.0,
  `--check`; it writes `s05_iapws95_coefficients.json` and `s05_crosscheck.json`.

## 0. Read this first

- Every expected number in §6 is a key of `s05_reference.json`, which is computed from the closed form of §2 alone.
- CoolProp and `iapws` never supply an expectation. They admit one: a value is registered only if both agree with it
  within §6.2's bounds. They also seed the generator's root solves.
- The release's printed verification tables (R6-95(2018) Tables 6–8) were **not** read, because iapws.org was refused
  on 2026-10-22. The coefficients are therefore evidenced by two independent transcriptions that agree exactly, not by
  the release (§9, §10 Q-1). *(Amended 2026-10-23, §15.1: the release was read on the workstation and compared digit
  by digit, 0 mismatches in 385.)*
- Tolerances are stated with their floor and their margin in §6.2–§6.3. The floors are measured and recorded in the
  JSON's `agreement` and `fd_floor`, and the generator refuses to emit if a floor rises above its stated margin.
- Every refusal is a typed result with a fixed message prefix (§4.5). An implementation that cannot answer says so
  through one of those codes, never through a default value.

## 1. Authority, scope and what this establishes

Authority: ADR 0045 (Proposed), under plan §1.3. The design lane leads the derivation, the phase controller and the
assertions; the build lane implements `thermo/iapws95.py` from this text. It is consistent with ADR 0001 D1–D5,
ADR 0026's provider pattern, R-568/R-569 (library-only providers) and `interfaces-frozen.md` §1. No Protocol or result
type changes: the provider uses `PropertyRequest`, `PropertyResult`, `FlashRequest`, `FlashResult` and
`PropertyCapabilities` as they stand.

This document establishes:
1. the formulation and its constants (§2);
2. every returned property as a closed form in the φ partials, with the derivative rules (§3);
3. the domain, the phase rule, the density-root brackets and the refusal table (§4);
4. the registered states and why each is there (§5);
5. thirty numbered assertions with their expectations and tolerances (§6);
6. the generators' self-claims (§7), the work orders (§11) and the manifest check list (§12).

## 2. The formulation

### 2.1 Coefficients and constants

- **The file.** The coefficients are in `docs/derivations/scripts/s05_iapws95_coefficients.json` (SHA-256
  `b9e93877e37874f1b3a483e298a45692e264d70686d4c158372084b96abbe6ed`).
- **Where they came from.** They were transcribed from CoolProp 8.0.0's `get_fluid_param_string('Water','JSON')`
  (SHA-256 `a10a0da6…0dec4586`, recorded in the file). `s05_crosscheck.py` asserts that each equals `iapws` 1.5.5's
  `IAPWS95._constants` and `IAPWS95.Fi0` exactly; it refuses to write the file otherwise.
- **How they are read.** The values are JSON numbers in shortest round-trip form. The implementation reads them as
  doubles. The generator reads the same text as exact decimals.
- **The provider's copy.** The provider reads `benchmarks/s05/iapws95_coefficients.json`, which is byte-identical to
  this file (S05.A01). Like L01's records, it sits in no `PACKAGED` path until C10-Q1 is answered (§10 Q-1).
  *(Amended 2026-10-23 by §16, R-616: Frank decided to ship; WO-S05-5 packages it, with IAPWS's attribution in NOTICE.)*

| constant | value | role |
| --- | --- | --- |
| R_s | 461.51805 J/(kg·K) | the formulation's specific gas constant |
| M | 0.018015268 kg/mol | molar mass. R6-95 does not print it. Source and status: §15.3, Q-7 |
| R = R_s·M | 8.3143713575874… J/(mol·K) (8.314371357587 to 13 digits) | the molar gas constant used everywhere, **not** CODATA's 8.31446261815324 |
| T_c | 647.096 K | reducing temperature, τ = T_c/T |
| ρ_c | 322 kg/m³ | reducing density, δ = ρ/ρ_c |
| p_c | 22.064 MPa | the critical pressure. It is a registered constant, not an output of the EOS: p(ρ_c, T_c) agrees with it to 1e-5 (claim). R6-95 does not print it. Source: §15.3 |
| T_t | 273.16 K | triple point, and the domain's lower bound |

Molar quantities are the specific ones × M: v = M/ρ, h = M·h_spec, and so on. The flow vector `n` has one entry,
`n_H2O` [mol/s].

### 2.2 The ideal part

φ°(δ, τ) = ln δ + n°₁ + n°₂ τ + n°₃ ln τ + Σ_{i=4}^{8} n°ᵢ ln[1 − exp(−γ°ᵢ τ)]

- The file's `ideal.n` holds n°₁…n°₈, with n°₁ = −8.3204464837497 and n°₂ = 6.6832105275932 (the 2016/2018 revision).
- `ideal.gamma` holds γ°₄…γ°₈.
- φ° depends on δ only through ln δ, so φ°_δ = 1/δ, φ°_δδ = −1/δ² and φ°_δτ = 0 exactly.

### 2.3 The residual part

φʳ = Σ_{i=1}^{7} nᵢ δ^{dᵢ} τ^{tᵢ}
   + Σ_{i=8}^{51} nᵢ δ^{dᵢ} τ^{tᵢ} e^{−δ^{cᵢ}}
   + Σ_{i=52}^{54} nᵢ δ^{dᵢ} τ^{tᵢ} exp[−αᵢ(δ − εᵢ)² − βᵢ(τ − γᵢ)²]
   + Σ_{i=55}^{56} nᵢ Δ^{bᵢ} δ ψ

with
- θ = (1 − τ) + Aᵢ [(δ − 1)²]^{1/(2βᵢ)};
- Δ = θ² + Bᵢ [(δ − 1)²]^{aᵢ};
- ψ = exp[−Cᵢ(δ − 1)² − Dᵢ(τ − 1)²].

File keys:
- `power` holds n, d, t and c, where c = 0 means no exponential factor (terms 1–7).
- `gaussian` holds n, d, t, alpha, beta, gamma and epsilon.
- `nonanalytic` holds n, a, b, B, C, D, A and beta.

The terms are evaluated in file order, and the sum is formed in that order. The order changes only the last bits, and
§6's tolerances sit far above them.

## 3. Derivation

### 3.1 Properties at (T, ρ)

Let φʳ_δ, φʳ_τ, … denote partial derivatives, with φ = φ° + φʳ. Then:

| property | closed form |
| --- | --- |
| p | ρ R_s T (1 + δφʳ_δ) |
| Z | 1 + δφʳ_δ (since Z = Pv/(RT) with v = M/ρ) |
| v | M/ρ |
| h | R T [1 + τ(φ°_τ + φʳ_τ) + δφʳ_δ] (h = u + p/ρ, u = R T τ φ_τ) |
| s | R [τ(φ°_τ + φʳ_τ) − φ° − φʳ] |
| c_v | −R τ² (φ°_ττ + φʳ_ττ) |
| c_p | c_v + R (1 + δφʳ_δ − δτφʳ_δτ)² / (1 + 2δφʳ_δ + δ²φʳ_δδ) |
| ln φ (`lnphi_H2O`) | φʳ + δφʳ_δ − ln(1 + δφʳ_δ), which is (g − g^ig(T, P))/(RT) |
| g | R T (φ° + φʳ + Z) |
| (∂p/∂ρ)_T | R_s T (1 + 2δφʳ_δ + δ²φʳ_δδ) |
| (∂p/∂T)_ρ | ρ R_s (1 + δφʳ_δ − δτφʳ_δτ) |

c_p needs φ partials of order 2. Its (T, P) derivatives need order 3.

### 3.2 The φ partials: one jet, order 3

**Method.**
- The implementation evaluates φ° and φʳ, with all partials in (δ, τ) up to total order 3, in one pass over the
  closed form.
- This uses truncated bivariate Taylor ("jet") arithmetic: +, −, ×, exp, ln, and integer and real powers.
- Hand-written partials are also permitted, provided they agree with S05.A03/A04.
- The function `phi_jet(tau, delta)` is module-level and returns the ten partials φ, φ_δ, φ_δδ, φ_τ, φ_ττ, φ_δτ,
  φ_δδδ, φ_δδτ, φ_δττ, φ_τττ, separately for φ° and φʳ. It is part of the tested surface (A03, A04).
- Values and derivatives come from that one evaluation. That is CLAUDE.md's rule that residual and Jacobian paths
  describe the same function at the same state.

**The δ = 1 special case.**
- [(δ − 1)²]^{1/(2β)} = |δ − 1|^{10/3} and [(δ − 1)²]^{a} = |δ − 1|^{7}.
- At δ = 1 exactly (ρ = 322 kg/m³), each of these factors is zero together with its first three δ-derivatives, because
  10/3 > 3 and 7 > 3.
- The implementation returns the zero jet for those factors at δ = 1. It never forms ln((δ − 1)²) there.
- Δ = θ² = (1 − τ)² stays positive off the critical point, so Δ^{b−k} is finite.
- The point (δ, τ) = (1, 1) lies inside the `near_critical` box and is never evaluated (§4.3).
- Registered state `delta_one` (§5.1) exists because of this case.

### 3.3 (T, P) derivatives

**Chain rule.** Every property X(T, ρ) with ρ = ρ(T, P) on the answered branch has
- (∂X/∂T)_P = (∂X/∂T)_ρ − (∂X/∂ρ)_T (∂p/∂T)_ρ / (∂p/∂ρ)_T
- (∂X/∂P)_T = (∂X/∂ρ)_T / (∂p/∂ρ)_T

**Converting to (δ, τ).** (∂/∂T)_ρ = −(τ/T) ∂/∂τ applied to the φ factors, plus the explicit T factors of §3.1, and
(∂/∂ρ)_T = (1/ρ_c) ∂/∂δ. First-order dual arithmetic over the jets of §3.2 is the recommended way to do this, but it is
not mandated.

**n-derivatives.** Every property is intensive and has one component, so ∂X/∂n_H2O = 0.0 exactly. The derivative
mapping carries that 0.0; an absent derivative would mean "not provided" (contract docstring, `PropertyResult.derivatives`).

### 3.4 Identities

The generator checks each of these against its numerically differentiated values (§7). Tests use them as cross-checks
(A11, A17).

| | identity |
| --- | --- |
| I1 | (∂h/∂T)_P = c_p |
| I2 | (∂s/∂T)_P = c_p/T |
| I3 | (∂s/∂P)_T = −(∂v/∂T)_P |
| I4 | (∂h/∂P)_T = v − T(∂v/∂T)_P |
| I5 | (∂ ln φ/∂P)_T = (Z − 1)/P |
| I6 | (∂ ln φ/∂T)_P = −(h − h^ig)/(R T²), with h − h^ig = R T (τφʳ_τ + δφʳ_δ) |
| I7 | (∂Z/∂P)_T = (Z/P)(1 + (P/v)(∂v/∂P)_T) |
| I8 | Maxwell: p(ρ', T) = p(ρ'', T) and g(ρ', T) = g(ρ'', T), so ln φ' = ln φ'' at P = p_σ |
| I9 | Clausius–Clapeyron: dp_σ/dT = (s'' − s')/(v'' − v') = (h'' − h')/(T(v'' − v')) |

### 3.5 Saturation

- **`Psat`(T)**, for T ∈ [273.16, 647.0] K. Solve I8 for (ρ', ρ'') by Newton in two variables, seeded by an ancillary of
  the implementation's choosing (its source is recorded with a hash in the module docstring, and it is not a runtime
  dependency). Converged means both relative density steps are ≤ 4ε (ε = 2⁻⁵²) and the residuals are at their floor.
  Then p_σ = p(ρ', T).
- **d`Psat`/dT** comes from I9, using the converged phases. d`Psat`/dP is 0.0 exactly.
- **`Tsat`(P)**, for P ∈ [p_σ(273.16 K), p_σ(647.0 K)], with both bounds computed by the provider itself. Newton on
  p_σ(T) = P, using I9 for the slope. d`Tsat`/dP = 1/(dp_σ/dT), and d`Tsat`/dT = 0.0 exactly.
- **Failure** to converge in 50 iterations is `not_converged`, with the prefix `saturation_not_converged:`.
- **Phase check.** A request whose properties are all in {`Psat`, `Tsat`} is answered with no phase-stability check: the
  request's phase is ignored, and the result's `phase_signature` is the request's phase. If a request also names a
  phase property, the phase rule of §4 applies to the whole request.

### 3.6 The reference state `IAPWS95-ref-v1`

- **The datum.** It is the formulation's own: u = 0 and s = 0 for the saturated liquid at T_t = 273.16 K. Because
  n°₁ and n°₂ are rounded to 14 digits, the zeros hold only to that rounding: the generator claims |u'(T_t)| < 1e-6 J/mol
  and |s'(T_t)| < 1e-8 J/(mol·K). The JSON's `datum` key records the measured values.
- **What it is not.** It is not a formation datum and not a member of ADR 0011 D2's reaction-consistent set.
- **What the absolute values can be used for.** Differences of h and s are meaningful within this convention only
  (ADR 0001 D5.2).

## 4. Domain, phase rule and refusals

### 4.1 Domain

T ∈ [273.16, 1273.15] K and P ∈ [1.0e2, 1.0e8] Pa, both inclusive and compared as doubles. A state outside the box is
`out_of_domain`. Ice is excluded: T ≥ T_t, and P ≤ 100 MPa is below the ice Ih/III point at 209.9 MPa.

### 4.2 The phase rule

Let s_σ = ln(P/p_σ(T)) and ε_σ = 1e-6. The rule is applied after the domain check, in this order:

1. If T ∈ (647.0, 648.0) K and P ∈ [2.20e7, 2.22e7] Pa, the request is refused `near_critical`, whatever its phase.
2. If T ≥ T_c, the request is answered VAPOR, and a LIQUID request is refused `phase_not_stable` (C10-Q2 default).
3. If T ∈ (647.0 K, T_c), the request is answered LIQUID iff P ≥ p_c, and VAPOR iff P < 2.20e7 Pa. Step 1 has already
   removed the rest.
4. If T ≤ 647.0 K, LIQUID is answered iff s_σ ≥ −ε_σ, and VAPOR iff s_σ ≤ +ε_σ.
   - Inside the band |s_σ| ≤ ε_σ both phases are answered, each on its own branch root. That is why a round trip
     P → `Tsat` → state at (`Tsat`, P) works for both phases.
   - A phase the rule does not answer is refused `phase_not_stable`.

### 4.3 Why the box and the 647.0 K edge

- **The box contains the critical point.** p_σ(647.0 K) = 22.0384 MPa > 22.0 MPa (claim), and (T_c, p_c) lies inside
  the box (claim). So step 3 never labels a state between the saturation curve's end at 647.0 K and the critical point.
- **The metastable roots exist at the edge.** At 647.0 K both band-edge roots (P = p_σ·e^{±ε_σ}) exist on their
  branches (claim).

### 4.4 Density roots and their brackets

The density root is found by bracketed, safeguarded Newton (bisection whenever a step leaves the bracket), with the
same convergence rule as §3.5. The brackets are:

| region | VAPOR bracket | LIQUID bracket |
| --- | --- | --- |
| T < T_c, stable side | (0, ρ''(T)] | [ρ'(T), 1250 kg/m³] |
| T ≤ 647.0 K, metastable side inside the band | Newton from ρ''(T), accepted iff it stays in (0, ρ_c) | Newton from ρ'(T), accepted iff it stays in (ρ_c, 1250] |
| T ≥ T_c | (0, 1250 kg/m³] | (refused) |

- For T ∈ (647.0 K, T_c) the saturated densities at T bound the brackets, even though `Psat` is not answered there:
  the Maxwell solve is internal. This **amends** the decision's "(0, 1250] for T > 647.0 K". An isotherm below T_c
  crosses the two-phase dome, and (∂p/∂ρ)_T ≤ 0 inside it (§13, amending line).
- **Generator claims, each on a grid of 41 points per bracket:**
  - (∂p/∂ρ)_T > 0 on (ρ_V(p_σe^{+ε_σ})/40, ρ_V(p_σe^{+ε_σ})] and on [ρ_L(p_σe^{−ε_σ}), 1250], at 23 subcritical
    temperatures from 273.16 to 647.05 K (§7 C10);
  - (∂p/∂ρ)_T > 0 on (0, 1250] at 8 temperatures from 647.1 to 1273.15 K;
  - p(1250 kg/m³, T) > 100 MPa at every grid temperature, so every LIQUID root at P ≤ P_max lies inside its bracket.
- A failure to converge is `not_converged`, with the prefix `density_not_converged:`.

### 4.5 Refusal table and precedence

`evaluate_phase` checks in this order, and the first failure wins. The message is `<code>: <detail>`; tests match the
status and `message.startswith(code + ":")`.

| # | code | status | when |
| --- | --- | --- | --- |
| 1 | `undeclared_derivative_input` | unsupported | a derivative input outside {T, P, n_H2O} |
| 2 | `unknown_property` | unsupported | a property outside the eight declared |
| 3 | `state_length` | error | `len(state.n) != 1` |
| 4 | `out_of_domain` | out_of_domain | §4.1 |
| 5 | `dormant_state` | unsupported | n_tot == 0 (ADR 0001 D3; the pr_c1 precedent) |
| 6 | `no_saturation` | unsupported | `Psat` asked at T > 647.0 K, or `Tsat` asked at P outside [p_σ(T_t), p_σ(647.0 K)] |
| 7 | `near_critical` | unsupported | §4.2 step 1, when any phase property is asked |
| 8 | `phase_not_stable` | unsupported | §4.2 steps 2–4, when any phase property is asked |
| 9 | `density_not_converged`, `saturation_not_converged` | not_converged | §4.4 and §3.5 |

`flash` checks, in this order:
1. `unsupported_specification` (not `TP`);
2. `flash_derivatives_unsupported`;
3. `state_length`;
4. `out_of_domain`;
5. a dormant state, which is answered `ok` with `ZERO_FLOW` and two dormant outlets (the pr_c1 precedent);
6. `near_critical`;
7. `tp_flash_degenerate` (unsupported), when both phases are answered (§4.2 step 4's band).

Otherwise the flash is `ok`:
- the answered phase's outlet carries n and the other outlet is the zero stream `n = (0.0,)` at the same T and P;
- `vapor_fraction` is 1.0 (VAPOR) or 0.0 (LIQUID);
- `phase_signature` is that phase;
- `k_values` is empty, because there is no K-value for one component.

Every result, refusals included, carries `provider_id` `iapws95-v1` and `reference_convention` `IAPWS95-ref-v1`.

## 5. Registered states

All inputs are the nearest doubles of the listed decimals, and the generator evaluates at those exact doubles.

### 5.1 φ states, at (T, ρ)

| name | T [K] | ρ [kg/m³] | why |
| --- | --- | --- | --- |
| `R6_500` | 500 | 838.025 | R6-95 Table 6 (its only state; §15.2). Liquid-like; the power terms dominate, and the Gaussian and non-analytic terms are below 1e-20 here, so they are **not** tested by this state |
| `R6_647` | 647 | 358 | A row of R6-95 **Table 7**, not Table 6. The release prints no φ values here, so its φ keys have no printed counterpart; its p, c_v, w and s match Table 7 (§15.2). Near-critical; the Gaussian (≈ 3e-2) and non-analytic (≈ 1e-1·n) terms are large, so a dropped or mis-signed term changes φʳ well above tolerance |
| `delta_one` | 700 | 322 | δ = 1 exactly: the zero-jet rule of §3.2. The non-analytic terms still contribute ≈ 3e-5 through θ = 1 − τ, so an accidental zero is caught |

### 5.2 Single-phase states, at (T, P)

There are eleven, listed with their reasons in `s05_reference.py` `TP_STATES`:
- three liquids: ambient; the corner (T_min, P_max); hot compressed;
- three vapours: dilute; near-saturation; the corner (T_min, P_min);
- three supercritical states: dense; the corner (T_max, P_max); the near-ideal corner (T_max, P_min);
- two in (647.0 K, T_c), one on each side of the box: 647.05 K at 21.9 MPa (VAPOR) and at 22.3 MPa (LIQUID).

The generator claims that the states are pairwise distinct, and that each one's dX/dP differs from every other's for
every X. The second claim means a permuted state index changes an expectation.

### 5.3 Saturation

- `Psat` at T = 273.16 K (the triple point, where the datum vanishes), 275, 450, 625 and 647.0 K (the last answered
  temperature).
- `Tsat` at P = 101325 Pa (the normal boiling point), 1.0e6 and 1.0e7 Pa.

### 5.4 Band probes, at 450 K

P = p_σ(450 K)·exp(k ε_σ), rounded to a double, for k ∈ {−2, −0.5, 0, 0.5, 2}:
- k = −2 is VAPOR only;
- k = −0.5, 0 and 0.5 are both phases;
- k = 2 is LIQUID only.

The generator claims these answered sets and registers each answered phase's values.

### 5.5 Refusal probes and their controls

| probe (T K, P Pa, ask) | expected | control (answered) |
| --- | --- | --- |
| 273.15, 1e5, LIQUID h | out_of_domain | 273.16, 1e8, LIQUID (`L_corner`) |
| 1273.16, 1e5, VAPOR h | out_of_domain | 1273.15, 1e8, VAPOR (`SC_corner`) |
| 400, 99.0, VAPOR h | out_of_domain | 273.16, 1e2, VAPOR (`V_corner`) |
| 700, 1.0000001e8, VAPOR h | out_of_domain | 1273.15, 1e8 (`SC_corner`) |
| 647.5, 2.21e7, VAPOR h; also LIQUID; also flash | near_critical | 648.0, 2.21e7, VAPOR (T = 648.0 is outside the open interval) |
| 647.05, 2.20e7, LIQUID h | near_critical | 647.05, 2.19e7, VAPOR (`NC_vapour`) |
| 700, 3.0e7, LIQUID h | phase_not_stable | the same state, VAPOR (`SC_dense`) |
| 647.05, 2.19e7, LIQUID h | phase_not_stable | `NC_vapour` |
| 647.05, 2.23e7, VAPOR h | phase_not_stable | `NC_liquid` |
| 647.0, 2.21e7, VAPOR h | phase_not_stable (s_σ = +2.8e-3 > ε_σ) | the same state, LIQUID |
| band `out_lo` LIQUID; band `out_hi` VAPOR | phase_not_stable | band `in_lo`, `in_hi`, both phases |
| `Psat` at 647.0001 K and at 700 K | no_saturation | `Psat` at 647.0 K |
| `Tsat` at 2.21e7 Pa and at 1.0e2 Pa | no_saturation | `Tsat` at 1.0e7 Pa |
| flash at band `in_lo` | tp_flash_degenerate | flash at band `out_lo` (vapour fraction 1.0) |
| `Psat` with LIQUID at 450 K, 1e4 Pa (vapour-only state) | answered (no phase check) | the same request with `h` added → phase_not_stable |
| derivative input `n_N2`; property `g`; `n = (1.0, 0.0)`; `n = (0.0,)` | codes 1, 2, 3, 5 | the same request at `L_ambient` with valid fields |
| flash `PH`; flash with derivatives `("T",)` | unsupported_specification; flash_derivatives_unsupported | flash `TP` at `L_ambient` |

## 6. Assertions

### 6.1 The assertions

Expectations are keys of `s05_reference.json`; "ref" below means that file. The test file is
`tests/test_s05_iapws95.py` (WO-S05-1) together with `tests/test_s05_envelope.py` (WO-S05-2). NC means the two
§5.2 states `NC_*`, whose bounds are multiplied by 100 (§6.2).

| id | assertion | expectation | tolerance |
| --- | --- | --- | --- |
| A01 | The provider's coefficient file is byte-identical to the generator's. The module constants R_s, M, T_c, ρ_c, p_c and T_t equal §2.1's bitwise | SHA-256 `b9e93877…abbe6ed` | exact |
| A02 | `describe()`: id `iapws95-v1`, convention `IAPWS95-ref-v1`, `nTP-v1`, components `("H2O",)`, phases `("LIQUID","VAPOR")`, properties = the 8 ids, flashes `("TP",)`, derivative_order `{T:1, P:1, n_H2O:1}`, the domain of §4.1, `numerical_limitations` naming `near_critical` and ε_σ | §2, §4 | exact |
| A03 | `phi_jet` at §5.1's three states, orders ≤ 2, φ° and φʳ | ref `phi_states.*` | \|Δ\| ≤ 1e-12·max(\|ref\|, 1) |
| A04 | `phi_jet` third partials of φʳ at `R6_500` and `R6_647` | ref `phi_states.*_ddd` and the other third-order keys | \|Δ\| ≤ 1e-11·max(\|ref\|, 1) (Q-5) |
| A05 | `evaluate_phase` at §5.2's eleven states in their phase: h, s, v, Z, cp and lnphi_H2O | ref `tp_states` | h: 1e-8·R·T absolute; s: 1e-8·R absolute; v: 1e-9 relative; Z, cp: 1e-8 relative; lnphi: 1e-8 absolute. NC ×100 |
| A06 | The same states' T and P derivatives of all six | ref `d*_dT`, `d*_dP` | 1e-8 relative; NC ×100 |
| A07 | Every `n_H2O` derivative is present and equals 0.0. As a control, the T derivatives at the same state are non-zero | 0.0 | exact |
| A08 | `Psat` at §5.3's five temperatures, and dPsat/dT. dPsat/dP is 0.0 | ref `saturation.*.Psat`, `dPsat_dT` | 2e-9 relative; slope 1e-8 relative |
| A09 | `Tsat` at §5.3's three pressures, and dTsat/dP. dTsat/dT is 0.0 | ref `tsat` | 1e-9 relative; slope 1e-8 relative |
| A10 | Maxwell: at each `Psat` temperature, LIQUID and VAPOR at P = the provider's own Psat(T) are both `ok`. \|lnφ_L − lnφ_V\| is small, and h_V − h_L matches ref | ref `h_v − h_l` | lnφ: 1e-8 absolute; Δh: 1e-9 relative (1e-6 at 647.0 K) |
| A11 | Clausius–Clapeyron (I9) on the provider's own answers: dPsat/dT = (s_V − s_L)/(v_V − v_L) | itself | 1e-8 relative (1e-6 at 647.0 K) |
| A12 | The datum: at 273.16 K and P = Psat(273.16 K), LIQUID has \|h − Pv\| ≤ 1e-6 J/mol and \|s\| ≤ 1e-8 J/(mol·K). As a control, the same quantities at 450 K exceed 1000 J/mol and 10 J/(mol·K) | ref `datum` | as stated |
| A13 | The band probes of §5.4: the answered sets and the values; the refused phase is `phase_not_stable:` | ref `band.probes` | as A05 |
| A14 | `near_critical:` probes of §5.5, for both phases and for the flash, each with its control | §5.5 | exact codes |
| A15 | The supercritical label and the (647.0 K, T_c) rule: the §5.5 `phase_not_stable` probes and their controls | §5.5 | exact codes |
| A16 | The four domain-edge probes of §5.5 → `out_of_domain`, for `evaluate_phase`, `Psat`, `Tsat` and `flash`. Controls at the exact bounds are `ok` | §5.5 | exact codes |
| A17 | Value/derivative consistency: the provider's T and P derivatives against central differences of its own values (step 1e-6·x) at §5.2's states and the band probes | itself | value units, FD_TOL = 1e-10 (§6.3, Q-6) |
| A18 | `no_saturation:` probes of §5.5, with controls | §5.5 | exact codes |
| A19 | A saturation-only request skips the phase check, and the same request with `h` added does not (§5.5) | §5.5 | exact codes |
| A20 | Flash: single-phase outcomes at §5.2's states (vapour fraction, outlets, zero stream, `phase_signature`, empty `k_values`); `tp_flash_degenerate:` at band `in_lo`; dormant → `ZERO_FLOW`; `PH` and derivative refusals | §4.5 | exact |
| A21 | Contract refusals 1, 2, 3 and 5 of §4.5, with controls | §4.5 | exact codes |
| A22 | Robustness grid: T ∈ {273.16, 300, 350, …, 1250, 1273.15} × P ∈ {1e2, 1e3, …, 1e8} plus 3·10⁷. Every non-refused phase is `ok`, `not_converged` never occurs, and every answer has (∂v/∂P)_T < 0 and cp > 0 | none (stability) | exact |
| A23 | Determinism: two calls give bitwise-equal results. Every result, refusals included, carries the provider id and the convention; `achieved_accuracy` is `exact-double` | itself | bitwise |
| A24 | `implementation_sha256` = SHA-256 of `iapws95.py`'s bytes; `data_sha256` = the A01 hash | files | exact |
| A25 | Library-only: absent from `SELECTABLE_BASES`; registered in `LIBRARY_ONLY_PROVIDERS` and `scanned_providers` (F-2); U02's note names `iapws95-v1` | R-568, R-569 | exact |
| A26 | *Superseded by §16.2 (R-616): the assertion is inverted, the file is packaged.* Packaging hold: no `PACKAGED` entry covers `benchmarks/s05/`, and a built wheel holds no `iapws95_coefficients.json` | R-594 | exact |
| A27 | Generator facts: ref's `coefficients_sha256` equals A01's hash, `claim_count` ≥ 300, and `--check` passed (manifest command) | ref | exact |
| A28 | Independence: the AST of `s05_reference.py` imports only the standard library and mpmath. No test imports `s05_crosscheck.py`, CoolProp or iapws | files | exact |
| A29 | Mutation battery, where each mutation must fail the named assertion: (m1) drop Gaussian term 54 → A03 at `R6_647`; (m2) flip the sign of n°₃ → A03; (m3) CODATA R → A05; (m4) ε_σ = 0 → A13; (m5) 647.0 K replaced by T_c in step 3 → A15; (m6) omit the `n_H2O` derivative → A07; (m7) a zero third-order jet → A06 (dcp); (m8) take ln((δ−1)²) at δ = 1 → A03 at `delta_one` | named | each fails |
| A30 | Coverage: every code of §4.5 has a probe, and every probe has an answered control (the test's probe table is checked against the code list) | §4.5 | exact |

### 6.2 Admission and value bounds: floor and margin

- **The floor of a double-precision evaluation.** A value is a sum of 56 terms with cancellation, so its error is
  about ε·Σ|terms| ≈ 1e-14 relative. A density root solved to 4ε relative adds κ·4ε, with κ = (ρ/X)(∂X/∂ρ)_T · p/(ρ(∂p/∂ρ)_T),
  which is O(1–100) away from the critical point.
- **The measured floor.** CoolProp 8.0.0 and iapws 1.5.5 against the 50-digit values: the worst per quantity is in
  ref `agreement`, and the generator refuses to emit if any exceeds its bound (C3).
- **The bounds.** They are those of `s05_crosscheck.py` `ADMISSION_BOUNDS`, and A05/A06/A08 use the same numbers. Each
  sits at least 10× above the measured worst; this is claim C3, and the generator refuses to emit otherwise. The
  measured worsts:
  - φ: 4e-14;
  - Psat: 1.0e-10;
  - h, s, Z, lnφ: up to 4.9e-10 (CoolProp's TP solve);
  - v and ρ: 1.2e-13;
  - cp: 3e-10;
  - the derivatives: 3e-10;
  - Tsat: 1.0e-8 (iapws);
  - NC: 4.3e-8.
  iapws alone agrees to about 2e-12 on every TP value.
- **What the bounds must catch.** The smallest error worth catching is a dropped or mis-signed term. That changes φʳ
  by more than 1e-5 at `R6_647` (Gaussian, non-analytic) and at `delta_one` (non-analytic, ≈ 3e-5). CODATA R shifts
  v at fixed (T, P) by 9e-6. A wrong branch is O(1). So every bound sits at least 3 decades below the smallest error
  worth catching.
- **The two widened bounds.**
  - Near-critical states (NC) take 100× the bounds: CoolProp's solve at 647.05 K, 21.9 MPa disagrees by 4.3e-8 in cp
    and the derivatives (measured), because conditioning grows as the density solve approaches the box.
  - `Tsat`'s admission bound is 1e-7, because iapws's inverse solve is loose (C10_DECISIONS). The implementation is
    held to 1e-9 (A09), which CoolProp meets (see `agreement`).

### 6.3 Central differences (A17): step, stencil and floor

- **The stencil.** It is central and second-order, with step h = 1e-6·x for x ∈ {T, P}.
- **The assertion is in value units:**
  |f(x+h) − f(x−h) − 2h·f′(x)| ≤ FD_TOL · max(|f(x+h)|, |f(x−h)|, s_f),
  with s_f = R·T for h, R for s and cp, and 1 for Z and lnφ (v uses |v|).
- **The bound's terms.**
  - Truncation is (h³/3)|f‴|, which is ≤ 1e-16·s_f away from the box.
  - Roundoff is 2·(the value error). That error is about 1e-14·s_f for a density solve converged to 4ε (§4.4); iapws
    1.5.5's measured value agreement is ≤ 2e-12·s_f away from NC.
  - So **FD_TOL = 1e-10** keeps a margin of ≥ 50× over iapws-level value noise.
- **What it catches.** A derivative wrong by relative δ is caught once δ > FD_TOL·max(|f|, s_f)/(2·10⁻⁶·|x f′|): about
  5e-5 for h(T) and cp, and weaker for Z(P) at dilute states, where |Z|/|P Z′| ≈ 1e3. A06 (against ref, at 1e-8) is
  the primary derivative check, and A17 is the backstop at non-reference states.
- **The measured CoolProp floor.** CoolProp 8.0.0's central differences are recorded in ref `fd_floor.measured_CoolProp`
  for information. It is 1e-4 to 1e-3 relative in the P derivatives, because its density solve is noisy at about
  1e-10. **An implementation with such a solve fails A17 by design**, because §4.4 requires a 4ε solve. If WO-S05-1
  measures its own floor above 1e-11, the tolerance is re-set by the design lane (Q-6). It is never loosened by the
  harness.

## 7. Generator self-claims (each one executable; the generator refuses to emit if any fails)

`s05_reference.py` records every claim's text in `claims`, and their number in `claim_count`. The claims fall into
these groups:

- **C1 — Coefficients.** The file's SHA-256 equals `COEFF_SHA256`. It holds 8 n° and 5 γ°, 51 power terms (1–7 with
  c = 0, 8–51 with c ≥ 1), 3 Gaussian and 2 non-analytic terms. R_s·M rounds to 8.314371357587.
- **C2 — Cross-check provenance.** The cross-check JSON records CoolProp 8.0.0 and iapws 1.5.5, was run over the
  committed coefficient file (by hash), and found iapws's coefficients equal.
- **C3 — Admission.** Every admitted value lies within §6.2's bound of both implementations. The worst disagreement
  per quantity is recorded in `agreement`.
- **C4 — Roots.** Every density root has converged (relative residual ≤ 10^(4−dps)), with (∂p/∂ρ)_T > 0. Every
  saturation solve has ρ' > ρ_c > ρ''.
- **C5 — Identities.**
  - I1–I7 hold to 1e-20 at every §5.2 state;
  - I8 holds (ln φ' = ln φ'' to 1e-30) at every §5.3 temperature;
  - I9 holds to 1e-20 against the 110-digit central difference of p_σ(T).
- **C6 — The datum.** |u'(T_t)| < 1e-6 J/mol and |s'(T_t)| < 1e-8 J/(mol·K). As a control, \|h'(450 K)\| > 1000 J/mol
  and \|s'(450 K)\| > 10 J/(mol·K).
- **C7 — The edge and the box.** p_σ(647.0 K) > 22.0 MPa. (T_c, p_c) lies in the box. |p(ρ_c, T_c)/p_c − 1| < 1e-5.
  The band-edge metastable roots exist on their branches at 647.0 K.
- **C8 — The band.** The 450 K probes answer exactly V, V+L, V+L, V+L, L. At P = p_σ (rounded to a double), the two
  roots' ln φ agree to 1e-14.
- **C9 — The rule and distinctness.**
  - The phase rule of §4.2 reproduces each §5.2 state's answered phase.
  - The §5.2 states are pairwise distinct (T, P).
  - For each property X, dX/dP takes 11 distinct values over the states.
  - `SC_ideal` is not exactly ideal (|Z − 1| > 1e-7).
  - φʳ and its first partials are non-zero at `delta_one`, which has δ = 1 exactly.
- **C10 — Brackets.** (∂p/∂ρ)_T > 0 at 41 points per bracket (§4.4), and p(1250 kg/m³, T) > 100 MPa, at every grid
  temperature. The last subcritical grid temperature is below T_c ≤ the first supercritical one.
- **C11 — The admission margin.** For every `agreement` entry, the worst disagreement × 10 is ≤ its bound. The
  CoolProp central-difference floor is recorded, not claimed (§6.3).

`s05_crosscheck.py` refuses to write when any of these fails:
- CoolProp's `Water` string does not have its recorded hash;
- an unexpected term family appears;
- R_s·M differs from CoolProp's molar R by more than 1e-12;
- the reducing state is not (647.096 K, 322 kg/m³);
- any coefficient differs from iapws 1.5.5's.

## 8. Findings (for other documents; not written here)

- **F-1.** *(Written 2026-10-23, D2: ADR 0001 D5 item 4 and `interfaces-frozen.md` §3.)* When ADR 0045 is accepted, ADR 0001 D5's list of reference conventions and `interfaces-frozen.md` need an
  `IAPWS95-ref-v1` line, as ADR 0026 added `PR-C1-ref-v1`. It is not reaction-consistent, so ADR 0011 D2's set is
  unchanged. This is a design-lane ADR amendment and is not written by C10.
- **F-2.** The T08 support envelope's library-only registry (`tests/test_t08_w2_support_envelope.py:329`
  `LIBRARY_ONLY_PROVIDERS`, and the `scanned_providers` list at line 73) gains `iapws95-v1`. This is build lane, inside
  WO-S05-2, under R-568's existing rule, so it is not a new decision.
- **F-3.** W27's `package_methods` names `iapws95`. Mapping W27's method string to `iapws95-v1` is a binding-package
  decision. S05 makes no claim that the two are the same method variant (for example, the IDAES `iapws95` package
  uses the same formulation but its own phase handling).

## 9. What this does not establish

- **Agreement with the printed release.** The coefficients and the 9-digit φ values are not compared with R6-95(2018)
  Tables 6–8. They equal two independent transcriptions, and their agreement is what §6.2 measures. A shared
  transcription error in CoolProp and iapws would pass every assertion here. §10 Q-1 closes that gap.
- **Independent saturation values.** CoolProp 8.0.0's saturation states and iapws 1.5.5's `_saturation` both draw on the
  NIST superancillary family (fastchebpure). They are evidence of the formulation's curve, but not independent of each
  other. The independent expectation is the generator's own Maxwell solve.
- **Accuracy against experiment.** The release's uncertainty statement is not re-validated. This is numerical
  verification of an implementation against a formulation, not empirical validation.
- **Anything outside the box or inside `near_critical`.** That includes metastable states beyond ε_σ, spinodals, ice,
  and P > 100 MPa.
- **Transport properties, IF97, mixtures, electrolytes.**
- **Any binding.** The provider is library-only, and no development case becomes runnable. Coverage counts are
  unchanged.
- **Performance.** Every T ≤ 647.0 K evaluation runs a Maxwell solve, and caching on exact T is permitted but not
  required.
- **The held-out half.** Nothing here cites it.

## 10. Open questions (each with a recommended default)

- **Q-1, needs a fact (= C10-Q1). Answered 2026-10-23: they match (§15.1). The `R6_647` clause below is corrected by
  §15.2.** Do the release's Tables 6–8 match? The settling measurement: a person with access
  to iapws.org compares the generator's `phi_states.R6_500` and `R6_647` `*_9` keys with Table 6, and the saturation
  and single-phase entries with Tables 7–8, and reads the release's terms.
  *Default:* build and test on the transcription now, and do not package the coefficient file (R-594).
- **Q-2, needs the user's preference (= C10-Q2).** How should T ≥ T_c be labelled? *Default:* VAPOR (R-590).
- **Q-3, needs a fact.** Is the Maxwell solve fast enough for flowsheet use? The settling measurement: WO-S05-1 records
  the median `evaluate_phase` time at `L_ambient` in its build-decisions log. *Default:* no cache. An exact-T cache is
  added only if the measured time exceeds 1 ms.
- **Q-4, needs the user's preference.** Should `g`, `cv` or the speed of sound be exposed? *Default:* no; they are
  additive ids for a later spec.

- **Q-6, needs a fact.** What is A17's floor for the provider itself? *Settling measurement:* WO-S05-1 records, per
  quantity, max |f(x+h) − f(x−h) − 2h f′| / max(|f|, s_f) over §5.2 and writes it in `docs/S05_DECISIONS.md`.
  *Default:* FD_TOL = 1e-10. A floor above 1e-11 is escalated, and the tolerance is never loosened by the harness.
- **Q-5, needs a fact.** What is the floor of A04 (the third partials of φʳ)? The generator admits only orders ≤ 2. *Settling measurement:* add CoolProp's `d3alphar_*` agreement (already present in `s05_crosscheck.json`) to `admit`. *Default:* 1e-11·max(|ref|, 1), which is 10× A03's bound, because the third partials multiply each term by at most d·(d−1)·(d−2) ≤ 6·5·4 relative to the value.

## 11. Work orders (`opus-engineer`, about 120k context each)

**WO-S05-1 — the provider** (`thermo/iapws95.py`, about 120k).
- **Read:** §2–§4 and §6, and `pr_c1.py` (refusal and hash patterns).
- **Build:**
  1. Copy the coefficient file to `benchmarks/s05/iapws95_coefficients.json`.
  2. Write `phi_jet` (§3.2), the (T, ρ) properties (§3.1), the chain rule (§3.3), the brackets (§4.4), the saturation
     solves (§3.5), the phase rule (§4.2), the refusal table (§4.5), `describe()` and `flash`.
- **Tests:** `tests/test_s05_iapws95.py` for A01–A21 and A23–A24, every expectation read from `s05_reference.json`.
- **Stop at the cap:** commit what passes, and record where it stopped in `docs/S05_DECISIONS.md`.
- **Never:** import CoolProp or iapws, and never edit the generator or its JSON. A disagreement is escalated to the
  design lane (rule 6).

**WO-S05-2 — the envelope, the robustness grid and the evidence** (about 120k).
- **Tests:**
  - A22 (the robustness grid);
  - A25 (library-only: F-2's two edits, and the U02 note naming `iapws95-v1`);
  - A26 (packaging hold);
  - A27–A28 (generator facts);
  - A29 (mutations, run as a scripted battery whose logs go under `evidence/S05/<commit>/artifacts/`);
  - A30 (refusal coverage).
- **Then:** run `s05_reference.py --check` (about 10 minutes) and record the command in the manifest; run
  `scripts/gate.sh` before any merge.
- **Write** `evidence/S05/<commit>/manifest.json` at `tested`, never `reviewed`.

## 12. Manifest check list (`evidence/S05/<commit>/manifest.json`)

- **`checks`:** one entry per S05.A01…A30, each `pass` or `fail` with its test node id. A29 lists every mutation, the
  assertion that caught it, and the log's hash.
- **`commands`:**
  - `python docs/derivations/scripts/s05_reference.py --check`, with its two output lines;
  - the pytest invocation;
  - `scripts/gate.sh`'s summary line.
  - `s05_crosscheck.py --check` is listed as "design lane, scratch venv", with the commit at which the design lane
    ran it. It is not re-run by the build lane.
- **`identities`:** `iapws95-v1`'s `implementation_sha256` and `data_sha256` (`b9e93877…abbe6ed`).
- **`limitations`:**
  - the R6-95 tables are not compared (Q-1);
  - the coefficient file is not packaged (R-594);
  - the provider is library-only (R-569 pattern);
  - the `near_critical` box is refused;
  - the band is ε_σ = 1e-6.
- **`status`:** `tested`. **`reviewed`** is set only by the `reviewer`.
- Angle-bracket fields are never valid values.

## 13. Decisions (the authoritative text is `docs/C10_DECISIONS.md`)

| decision | section | register |
| --- | --- | --- |
| package id `S05` | §1 | R-585 |
| independent expectations: mpmath plus two-implementation admission | §0, §6.2 | R-586 |
| generator layout (two scripts) | header, §7 | R-586 |
| coefficient set and R | §2.1 | R-587 |
| reference convention `IAPWS95-ref-v1` | §3.6 | R-588 |
| domain | §4.1 | R-589 |
| phase rule | §4.2 | R-590 |
| properties | §3, §3.5 | R-592 |
| flash | §4.5 | R-593 |
| density root (amended in the second pass: brackets for T ∈ (647.0 K, T_c)) | §4.4 | R-591 |
| metastable band roots by Newton from the saturated density | §4.4 | R-591 |
| derivative method: an order-3 jet, and the zero jet at δ = 1 | §3.2 | R-592 |
| Tsat admission bound 1e-7 | §6.2 | R-586 |
| saturation-only requests skip the phase check | §3.5 | R-592 |
| rights | §9, §10 | R-594 |

## 14. Amendment, 2026-10-22 (design lane, `reviewer`; `docs/reviews/S05-review.md`, R-595…R-599)

This section amends the text above. Where the two disagree, this section governs.

- **§3.5 and §4.4, the convergence rule (R-595).** A Newton iteration has converged when its relative correction is
  ≤ 4ε, and that includes a correction that rounds to zero at the current iterate. The test is made on the Newton
  correction **before** any bracket safeguard. The iteration has also converged at its residual floor when both of
  these hold:
  - the previous Newton step was ≤ √ε = 2⁻²⁶;
  - the current Newton step is not smaller than the previous one, and is itself ≤ √ε.

  A bisection (safeguard) step never satisfies either clause. *Reason:* the measured failure in which a bisection
  midpoint was accepted as converged (review F1: 700 K, 1e8 Pa, VAPOR answered with ρ off by 26 %).
- **§3.5, p_σ (R-596).** "p_σ = p(ρ', T)" becomes **p_σ = p(ρ'', T)**. Both sides equal p_σ at the root. The liquid side
  is amplified by (ρ/p)(∂p/∂ρ)_T ≈ 3e6 at T_t. Measured against ref: 5.4e-8 from the liquid side and ≤ 1.6e-14 from the
  vapour side at 273.16 K.
- **§3.1, Z at a solved root (R-596).** At a density root solved for a given (T, P), the value of Z, and the Z inside
  `lnphi_H2O`, is **P/(ρ R_s T)**. Its T and P partials remain the jet's, which is the same function on the branch.
  On the (T, ρ) path (`phi_states`, the saturation slope), Z = 1 + δφʳ_δ. Because Z then equals Pv/(RT) identically,
  Z no longer witnesses the root.
- **§6.1 A22 (R-595).** Every answer also satisfies |p(M/v, T) − P| / (ρ(∂p/∂ρ)_T) ≤ 1e-12, with p and ∂p/∂ρ taken
  from `phi_jet`. The measured floor is ≤ 5e-16. The same check runs on a dense grid of 180 T × 61 P.
- **§6.3 A17's stencils (R-597).** FD_TOL = 1e-10 is unchanged. The step h = 1e-6·x stays the default, with three
  exceptions:
  - (a) **NC states:** h = 1e-7·x. Truncation (h³/3)|f‴| was measured at 1.25e-9 at 1e-6·x, and a 10× margin needs
    h ≤ 2e-7·x.
  - (b) **A coordinate at a box edge:** the inward one-sided stencil
    |s(−3f₀ + 4f₁ − f₂) − 2h f′| ≤ FD_TOL·max(|f₀|, |f₁|, |f₂|, s_f), with f_k = f(x + k s h). Truncation is
    (2/3)h³|f‴|.
  - (c) **Band probes:** h_P = (ε_σ/4)·P and h_T = (ε_σ/4)/|d ln p_σ/dT|.

  Measured: ≤ 5.7e-13 at NC, ≤ 2.8e-13 at the corners, and ≤ 1.3e-14 at the band probes. No case is dropped.
- **§6.1 A29 m5 (R-598).** m5 becomes "T_c replaced by 647.0 K in step 2 of §4.2", which A15 catches: the `NC_liquid`
  control is refused. The former m5 is an equivalent mutant by construction (§4.3: p_σ on (647.0 K, T_c) lies inside
  the box).
- **§6.1 A04 / Q-5 (R-598).** The bound stays at 1e-11·max(|ref|, 1). The measured provider floor is ≤ 6.8e-13, and
  CoolProp's third partials agree with ref to 6.8e-13. Admitting the third partials in `s05_reference.py` is a
  design-lane follow-up, and it does not block `tested`.
- **§6.2 Tsat admission (R-598).** The admission bound is **2e-7**, as in `s05_crosscheck.py` `ADMISSION_BOUNDS`, not
  1e-7. iapws's worst is 1.03e-8, and C11's 10× margin needs a bound ≥ 1.03e-7. A09 still holds the implementation
  at 1e-9.
- **§4.5 row 4.** `out_of_domain` also covers a negative or non-finite flow (nTP-v1's domain).
- **§12, limitations (R-599).** The manifest states that:
  - the IAPWS terms of use were not read (iapws.org was refused, 2026-10-22);
  - the rights row is `unresolved`;
  - the coefficient file is unpackaged;
  - Tables 6–8 are not compared;
  - ADR 0045 stays Proposed, and nothing is `released` until C10-Q1 is answered.

**Note, 2026-10-22 (design lane, `reviewer`; R-600; review, "Ruling on the WO-S05-3 departure").** This note governs
the R-595 and A22 bullets above.
- **§3.5 and §4.4.** Both clauses are tested on the raw Newton correction at the current iterate, before the safeguard,
  whether or not the Newton point lies in the bracket. The answer is that Newton point, never the iterate or a midpoint.
  After a safeguard bisection, "the previous Newton step" is the raw correction that left the bracket. After a
  bisection forced by ∂p/∂ρ ≤ 0, it is ∞. A Newton step leaves the bracket only by crossing its far end, so the root
  then lies within that step. "A bisection step never satisfies either clause" stands.
- **§6.1 A22.** "The measured floor is ≤ 5e-16" holds only where the residual is not noise-dominated (for example
  400 K, 1e7 Pa). In the liquid near T_t the computed residual is rounding noise over hundreds of ulp: the envelope is
  7.2e-14 at 273.16 K, 10^5.3 Pa, and the worst answer on the dense grid is 3.4e-14. The bound 1e-12 is unchanged.

## 15. Amendment 2, 2026-10-23 (design lane, `specifier`, ruling round D2; R-611, R-612)

The source is the workstation check of IAPWS R6-95(2018), recorded in `docs/C10_DECISIONS.md` at `af04961e`
(branch `wp/S05-tables`). This amendment takes effect when that record is in `main`.

### 15.1 §10 Q-1 is answered: the release matches

- **Read.** IAPWS R6-95(2018), 19 pages, PDF SHA-256
  `512879217b94f4d0741c88cab743d41098268914d538d73e680a736cb1c3aad7`, fetched 2026-10-23. It is not committed.
- **Compared: 385 values, digit by digit, 0 mismatches.** A control run with two printed digits altered reports
  exactly those 2.

  | Source in the release | Count | Compared against |
  | --- | --- | --- |
  | Eqs. 1–3 and T_t | 8 | the file's and the provider's T_c, ρ_c, R and T_t, exactly |
  | Table 1 | 13 | the 8 n°ᵢ and 5 γ°ᵢ, exactly |
  | Table 2 | 241 | all 56 residual rows, exactly |
  | Table 6 | 36 | `R6_500`'s 12 values, each three ways, to 9 figures |
  | Table 7 | 44 | p, c_v, w and s at 11 rows, to 9 figures |
  | Table 8 | 42 | the saturation states at 275, 450 and 625 K, to 9 figures |
  | p_t | 1 | 611.654 771 Pa, to 9 figures |

- **Terms, verbatim.** "Publication in whole or in part is allowed in all countries provided that attribution is
  given to the International Association for the Properties of Water and Steam."
- **§9's first bullet is replaced.** A transcription error shared by CoolProp and `iapws` is now excluded for every
  coefficient of Tables 1–2 and for T_c, ρ_c, R and T_t. What remains unchecked against print is §15.3's M.
- **§12's limitations (R-599) for the next manifest.** They are replaced by these:
  - the terms were read and quoted (`af04961e`);
  - the rights row is `permitted with conditions` (attribution to IAPWS), following `docs/l01-rights-check.md`'s
    RC-03 precedent;
  - Tables 1, 2 and 6–8 are compared, with 0 mismatches;
  - ADR 0045 is Accepted (2026-10-23);
  - the coefficient file stays unpackaged (S05.A26) until Frank decides to ship;
  - `reviewed` covers numerics, not rights.

### 15.2 `R6_647` is a Table 7 row, not "Table 6 point 2"

- The 2018 release's Table 6 has one state: 500 K and 838.025 kg/m³ (`R6_500`).
- The state 647 K and 358 kg/m³ is a row of Table 7, and the release prints no φ derivatives for it. §5.1's row and
  §10 Q-1 are corrected in place.
- What is tested does not change:
  - `R6_647` stays registered for its stated reason: the Gaussian and non-analytic terms are large there.
  - Its φ expectations still come from the 50-digit generator, admitted by both external implementations (§6.2).
    They have no printed counterpart.
  - Its p, c_v, w and s were compared with Table 7 at `af04961e`.
- The generator's `PHI_STATES` labels carry the same mislabel (`s05_reference.py` lines 52 and 57). They are corrected
  by WO-S05-4 item 1.

### 15.3 Where M and p_c come from (new Q-7)

R6-95 prints neither constant. Per the `af04961e` record, the release's R is derived from the R_m and M of its
references, and p_c is the value of IAPWS's critical-parameters release (R6-95's ref. [2]).

- **p_c = 22.064 MPa.**
  - *Citation:* IAPWS's release on the critical parameters of ordinary water substance, R2-83(1992), which is R6-95's
    ref. [2].
  - *Binding:* the value is also tied to the release-checked formulation by generator claim C7, which is executable.
    The measurement is p(ρ_c, T_c) = 22 064 000.000 002 13 Pa (`s05_reference.json#/critical/p_eos_at_rhoc_Tc`), a
    relative deviation of 9.7e-14.
  - *Why C7's bound suffices:* C7's bound of 1e-5 is below 4.5e-5, the relative size of one unit in p_c's last printed
    digit. A mistyped p_c therefore makes the generator refuse to emit.
  - *Conclusion:* T_c, ρ_c, R and every coefficient are release-checked, so p_c's value needs no further fact. It is
    used in §4.2 step 3 and in the box (§4.3).
- **M = 0.018015268 kg/mol.**
  - *Citation:* IAPWS G5-01, the Guideline on the Use of Fundamental Physical Constants and Basic Constants of Water,
    which gives M for water of VSMOW composition. It has not been compared with a printed copy.
  - *What M touches:* only the molar–mass conversion. That is v = M/ρ and the molar h, s, c_p, c_v and u: every molar
    extensive quantity scales by M. T, P, the phase, p_σ, T_σ and every intensive ratio are untouched.
  - *Why no check sees it:* every release comparison is on the mass basis (molar ÷ M), and every S05 expectation uses
    the same M. A wrong M would therefore be invisible to every assertion here and to the Tables check. It would show
    only against another provider's or record's molecular weight for water.
- **Q-7, needs a fact.** Two questions:
  - Does IAPWS G5-01 print M = 18.015268 g/mol?
  - Is R6-95's ref. [2] R2-83(1992), with p_c = 22.064 MPa?

  *Settling measurement:* a person with iapws.org access reads both documents and records them in
  `docs/C10_DECISIONS.md`.
  *Default:* cite them as above. Q-7 is **not** a release condition, for three reasons:
  - p_c's value is bound to the checked formulation (C7);
  - M's only effect is a common scale on molar extensive quantities, which no comparison with the release can test;
  - Frank's C10-Q1 condition named the terms and Tables 6–8, and both are satisfied.

  If G5-01 prints another M, M changes by amendment. `data_sha256` then moves and every expectation is regenerated.

### 15.4 Work order WO-S05-4 (build lane, `sonnet-implementer`, about 40k context; after `wp/S05-tables` merges)

1. **Labels.** In `docs/derivations/scripts/s05_reference.py` `PHI_STATES`, change two `why` strings:
   - `R6_500`'s becomes `"R6-95 Table 6 (its only state), liquid-like; every phi term is non-zero"`;
   - `R6_647`'s becomes `"R6-95 Table 7 row (no printed phi values), near-critical; the non-analytic terms are large"`.

   Re-emit `s05_reference.json` and confirm that `--check` is OK.
   *Acceptance:* load the old and the new JSON and delete every `why` member. The two documents must be equal, so only
   the two strings move. Record that this was run. Re-pin any recorded SHA-256 of the JSON in the same commit.
2. **Manifest.** In `scripts/s05_evidence_manifest.py`, set `requirements: ["D08"]` (R-614) and write §15.1's
   limitations. Re-take `evidence/S05/<commit>/manifest.json` and harvest it. Then cite it in `docs/requirements.yaml`
   under D08's `evidence` and S05's package row.
3. **Not in this work order:** packaging, the inversion of S05.A26, and any binding.

### 15.5 What this amendment does not establish

- **Permission to ship.** The terms are read, but the decision is Frank's (ADR 0045's release condition).
- **M from a printed IAPWS source** (Q-7).
- **Agreement with the release beyond the 385 values of §15.1.** The release's derivative relations (Tables 3–5)
  were used, not compared.
- **Anything about accuracy against experiment**, as before (§9).

## 16. Amendment 3, 2026-10-23 (design lane, `specifier`; Frank's ship decision; R-616)

**Source.** Frank, 2026-10-23 (`docs/FRANK_QUESTIONS.md`, C10, "Ship decision"): "Yes, ship with attribution". S05 may
ship in a release with an IAPWS attribution in NOTICE. This meets ADR 0045's release condition and supersedes R-594's
packaging hold. The terms and the 385-value Tables check are §15.1's. This amendment does not touch §15.4: WO-S05-4
runs first.

*Erratum 1 (§16.12, R-617) amends A33, T08.A32 for F, L40 and the order of WO-S05-5's last steps.*

Two constants are used throughout:
- F = `benchmarks/s05/iapws95_coefficients.json`;
- H_C = `b9e93877e37874f1b3a483e298a45692e264d70686d4c158372084b96abbe6ed`, F's SHA-256 (A01).

### 16.1 What this amendment establishes

1. A26 is inverted: F is package data, and a built wheel holds it (§16.2).
2. The attribution that NOTICE and the provider's documentation carry, verbatim (§16.3).
3. No binding: `iapws95-v1` stays library-only, and A25 is unchanged (§16.4).
4. The identity consequences (§16.5) and three new assertions, A31–A33 (§16.6). §6.1's thirty assertions become
   thirty-three.
5. One recorded erratum (§16.7), one open question (§16.8), one finding (§16.9) and WO-S05-5 (§16.10).

### 16.2 A26, as amended

This row replaces §6.1's A26. Every part is exact (§16.6 gives the reason).

| id | assertion | expectation | tolerance |
| --- | --- | --- | --- |
| A26 | Packaged (R-616). (a) F is an entry of `PACKAGED`. Neither `benchmarks/s05` nor any other path below it is an entry or in `DIRECTORIES`. (b) `packaged(F).read_bytes()` equals the repository copy's bytes and hashes to H_C. `src/openflowsheet/_data/benchmarks/s05/iapws95_coefficients.json` is a symbolic link whose target is `../../../../../benchmarks/s05/iapws95_coefficients.json`. (c) Exactly one `package-data` pattern of `pyproject.toml` matches `_data/` + F. (d) A wheel built from HEAD by T08.A43's hook holds exactly one member ending `iapws95_coefficients.json`, namely `openflowsheet/_data/` + F. Its bytes hash to H_C, and no other member lies below `openflowsheet/_data/benchmarks/s05/`. *Controls:* (a)–(c) hold for `benchmarks/m01/components.yaml`; the same wheel holds `openflowsheet/thermo/iapws95.py` and `openflowsheet/_data/benchmarks/m01/components.yaml` | H_C; the paths stated | exact |

Why each part is there:
- **(a)** A single file entry ships exactly the bytes A01 pins, and nothing placed beside F later.
- **(b)** The link keeps one repository copy (`resources.py`'s rule). The hash ties the package copy to the
  release-checked file.
- **(c)** Without the pattern, setuptools omits the file silently. (a) and (b) would then pass in a checkout while the
  wheel lacked it.
- **(d)** It is the only part that sees the artifact. "Exactly one" catches a second copy at another path.

The wheel half keeps today's harness. It needs `OFS_S05_BUILD_PYTHON` and is skipped without it, and a skipped wheel
node leaves A26 `fail` in the manifest, as now.

### 16.3 The attribution

Three strings, each verbatim from the release's cover page as recorded at `af04961e` (`docs/C10_DECISIONS.md`,
"TERMS"):
- **S0** = `© 2018 International Association for the Properties of Water and Steam`. The sign is U+00A9; the PDF's text
  layer has U+F6D9, a symbol-font glyph.
- **S1** = `Publication in whole or in part is allowed in all countries provided that attribution is given to the
  International Association for the Properties of Water and Steam`.
- **S2** = `Please cite as: International Association for the Properties of Water and Steam, IAPWS R6-95(2018), Revised
  Release on the IAPWS Formulation 1995 for the Thermodynamic Properties of Ordinary Water Substance for General and
  Scientific Use (2018)`.

Here and in every check, a string is compared after each run of whitespace is collapsed to one space.

**NOTICE.** Append one empty line and then exactly this block, with LF line endings and a final newline. No existing
byte changes.

```text
Third-party data: the IAPWS-95 coefficients

The file openflowsheet/_data/benchmarks/s05/iapws95_coefficients.json
(repository path benchmarks/s05/iapws95_coefficients.json), read by the
library-only property provider iapws95-v1, reproduces the coefficients and
constants of the IAPWS-95 formulation, IAPWS R6-95(2018). That release is
© 2018 International Association for the Properties of Water and Steam. Its
terms: "Publication in whole or in part is allowed in all countries provided
that attribution is given to the International Association for the
Properties of Water and Steam". Attribution is hereby given to the
International Association for the Properties of Water and Steam (IAPWS).

Please cite as: International Association for the Properties of Water and
Steam, IAPWS R6-95(2018), Revised Release on the IAPWS Formulation 1995 for
the Thermodynamic Properties of Ordinary Water Substance for General and
Scientific Use (2018).
```

Measured on this text: the old NOTICE is 1292 bytes with SHA-256
`11b9cac850433895cdb7e0e012b71d969c097467ca055274e95a338f3802c38f`. The new NOTICE is the old bytes, `\n` and the
block, with SHA-256 `24790a6d2cf79b6b8c063f383ec2d2bee9105422f4e06d607054ab11ff37dd8a`.
It contains S0, S1 and S2, and the old NOTICE contains none of them.

**`docs/attributions/iapws95-v1.md`** is the provider's documentation that ADR 0045's release condition asks for. It
follows the `pr-lib-v1.md` pattern and states:
- F's two paths, H_C and the provider id;
- S0, S1 and S2;
- the release that was read (PDF SHA-256 `512879217b94f4d0741c88cab743d41098268914d538d73e680a736cb1c3aad7`) and the
  check of 385 values with 0 mismatches (`af04961e`);
- the transcription route: CoolProp 8.0.0 (MIT), none of whose code or text ships; checked equal to `iapws` 1.5.5
  (GPL-3), executed only, with nothing copied (R-594);
- M's citation as Q-7 leaves it (not compared with print);
- that it states facts and quoted terms, and is not a legal opinion.

**Why NOTICE and not only the attribution file.** `docs/` is not in the wheel. NOTICE is in both artifacts (T08.A31),
and its bytes equal the repository's (T08.A43).

### 16.4 Binding: none

`iapws95-v1` is not bound. The following are unchanged:
- `SELECTABLE_BASES`, `MODEL_BASES` and `snapshot.PROVIDER_LINES`;
- the support envelope's `property_model` block;
- `LIBRARY_ONLY_PROVIDERS` and `scanned_providers`;
- the M07 registration, `v0.2-envelope-1`.

A25 holds as written, and it is the executable statement of this section.

**Why.** Binding is not a packaging step. It needs three things this package does not have:
- **A basis key.** The binder selects a basis by `record_source`, a component-record file. `iapws95-v1` reads a
  coefficient file and has no record file. L01 §13.4 measured what a non-matching record source does: it selects
  SYN-001's basis, and the components are refused.
- **Unit models bound on the basis.** The C1 units are bound on `pr-c1-v1`'s basis. A basis with an empty `model_ids`,
  as L01 §4.3 plans for `pr-lib-v1`, makes no flowsheet runnable.
- **F-3's mapping** of W27's `iapws95` method string to `iapws95-v1`, under W27 v2. The W27 v1 files are frozen.

Bound without models, the provider would move the registry's identity, the support matrix and the next envelope, and
make nothing runnable. Whether a release should offer water as a selectable basis, and spend a package on the basis key
and the units, is a scope decision. That is Frank's (Q-8).

**What a wheel user gets.** `iapws95-v1`, constructed directly in Python, reading the packaged coefficients. Every
wheel built since S05 already carries `thermo/iapws95.py` (the old A26's control). From a wheel, its first use raised
`FileNotFoundError` (`load_coefficients`). Packaging closes that gap.

### 16.5 Identity consequences

**Unchanged (A33):**
- F, so `iapws95-v1`'s `data_sha256` stays H_C;
- `src/openflowsheet/thermo/iapws95.py` (SHA-256 `c480f55fa15c97a1b3eb142f755be485ba5025035ae4d4f8bf54935cdbcd8d01`),
  so `implementation_sha256` is unchanged. The reviewed bytes (manifest `4ac00a0…`, R-600) are the shipped bytes;
- the generators and their JSON (`docs/derivations/scripts/s05_*`, as WO-S05-4 leaves them);
- everything else below `src/openflowsheet/`: `thermo/pr_c1.py`, `thermo/pr_lib.py`, `thermo/conventions.py`,
  `models/c1/*` and `application/revision_binding.py`. So `SELECTABLE_BASES`, `MODEL_BASES` and `list_models_sha256`
  do not move;
- `benchmarks/m01/components.yaml` and its `_data` link;
- `benchmarks/l01/components.yaml`, which stays unpackaged (R-541, R-615);
- every committed W27 v1 file: `benchmarks/m06/openidaes450/` `registration.json`, `coverage.json`, `case_facts.json`,
  `dry_illustration.json` and `runs/**`; `benchmarks/m06/w27/snapshot.py` (`PROVIDER_LINES`); every committed snapshot;
- the journey records `benchmarks/m07/journey/*/journey.json` and `benchmarks/m07/registration.json`;
- the M02 and M05 dumps below `benchmarks/m02/` and `benchmarks/m05/`;
- in `benchmarks/t08/support_envelope.yaml`, the `property_model` block and every existing `harvest` row;
- `schemas/`, `docs/interfaces-frozen.md` and ADR 0001 D5. No interface moves.

**New identities:** none. F and the module already have theirs (A24).

**Moved by WO-S05-5 only:**
- `openflowsheet.resources.PACKAGED`, by one added file path, and its docstring;
- `src/openflowsheet/_data/benchmarks/s05/iapws95_coefficients.json`, a new link;
- `pyproject.toml`, by one `package-data` pattern;
- NOTICE, by the appended block (§16.3);
- every sdist and wheel built afterwards, by one member and a new NOTICE. A new build is a new artifact, and no
  committed record hashes a future build;
- `tests/test_s05_envelope.py` (A26 inverted; A31 and A32 added) and `tests/test_t08_w4_package_data.py`, whose count
  of packaged single files goes from 5 to 6;
- `scripts/s05_evidence_manifest.py` (A26's text, the coefficient artifact's description and one limitation), a new S05
  manifest, its appended harvest rows, and D08's note in `docs/requirements.yaml`.
- *Added by §16.12 (R-617):* `tests/test_t08_w2_inventory.py` (T08.A32 for F), L40's text and `docs/support-matrix.md`
  in the packaging range; `HARVEST_SIZE` in `tests/test_m07a_harvest.py` in the harvest range.

**Registry snapshots.** The registry's content does not move (A25, A33). No committed snapshot moves. A snapshot built
afterwards records a different `git_commit`, as any new build does.

**Rejected alternative.** *Correcting `iapws95.py`'s stale sentences (§16.7) in the same commit.* That moves
`implementation_sha256` away from the reviewed bytes, with no change in behaviour.

### 16.6 Assertions added

All three are exact. They compare bytes, strings, paths and exceptions, so the roundoff floor is zero and any
difference is a defect. No tolerance applies.

| id | assertion | expectation | tolerance |
| --- | --- | --- | --- |
| A31 | Attribution. (a) NOTICE contains S0, S1 and S2. (b) `docs/C10_DECISIONS.md` contains each of S0, S1 and S2. (c) `docs/attributions/iapws95-v1.md` contains S0, S1, S2, `iapws95-v1`, F and H_C. (d) The wheel's NOTICE member, located as T08.A31 locates it, equals the repository NOTICE's bytes. Whitespace is collapsed as §16.3 says | S0–S2; equal bytes | exact |
| A32 | The package copy serves the provider. Patch `iapws95._checkout_coefficients` to return `None` and clear `load_coefficients`'s cache: `load_coefficients()` then equals `parse_coefficients(` the repository bytes of F `)`. *Control:* with `iapws95.packaged` also patched to raise `KeyError`, it raises `FileNotFoundError`. The cache is cleared again on exit | equality; the exception | exact |
| A33 | Identity, a manifest command run once over WO-S05-5's range `<base>..<tip>`. (a) Outside `docs/` and `evidence/`, `git diff --name-status` lists exactly: `M NOTICE`, `M pyproject.toml`, `M src/openflowsheet/resources.py`, `A src/openflowsheet/_data/benchmarks/s05/iapws95_coefficients.json`, `M tests/test_s05_envelope.py`, `M tests/test_t08_w4_package_data.py`, `M scripts/s05_evidence_manifest.py` and `M benchmarks/t08/support_envelope.yaml`. (b) In `support_envelope.yaml`, `property_model` is equal at base and tip, and every `harvest` entry at base is present and unchanged at tip. (c) At tip, NOTICE hashes to `24790a6d…37dd8a` and its first 1292 bytes to `11b9cac8…02c38f` (§16.3). At base, NOTICE contains none of S0, S1 and S2. (d) At tip, `iapws95.py` hashes to `c480f55f…cdbcd8d01` and F to H_C | the list; equality; the hashes | exact |

*A33 is amended by §16.12.3 (R-617). That row replaces this one, which is kept as written.*

A31(d) needs the wheel. It runs in A26(d)'s node, and without `OFS_S05_BUILD_PYTHON` it leaves A31 `fail` in the
manifest.

Why each is in the list:
- **A31.** (b) catches a typo in the test's literal, because it ties the literal to the recorded quote rather than to
  the test's own copy. (d) is the only part that sees what a user receives. (a) stays true when a later release appends
  another attribution, so it is a permanent test. The exact bytes are pinned once, in A33(c).
- **A32.** An installed package has no checkout, and A32 shows that the coefficients are still read. The control shows
  that the checkout branch really is disabled, so the pass does not come from the old path. With A26(d), this covers
  the installed wheel without building a venv that holds every dependency.
- **A33.** (a) is exact both ways: a forgotten step (no NOTICE edit) fails it, and so does any path the work order was
  not meant to touch. (c)'s base clause is the control for A31(a): it shows that the old file does not satisfy it. If
  a path outside (a)'s list must change, this amendment is wrong. Stop and escalate (rule 6); do not widen the list.

### 16.7 Recorded erratum (the R-310 pattern)

From WO-S05-5 on, two passages of `thermo/iapws95.py` are false:
- lines 14–15: "sits in no `PACKAGED` path until C10-Q1 is answered (R-594), so only a source checkout reads it; an
  installed package says so on first use";
- `load_coefficients`'s docstring: "it does not until C10-Q1 is answered, R-594".

They are recorded errata. The module's bytes are the reviewed bytes, and the code they describe already handles both
cases (package data first, then the checkout). They are corrected with the module's next substantive change, which
moves `implementation_sha256` anyway.

### 16.8 Open question

- **Q-8, needs the user's preference.** Should a release offer `iapws95-v1` as a basis that a revision can select? That
  needs its own package with five parts:
  - a basis key that does not depend on a record file;
  - unit models bound on the basis;
  - F-3's W27 v2 mapping;
  - a support-matrix L-row;
  - the next envelope's provider list.
  **Answered — Frank, 2026-10-23: "Library only for now".** No binding in S05; a selectable-basis package is planned later, together with S07 (CoolProp), which raises the same question for many fluids.

  *Default:* no. The provider ships library-only (this amendment). The default is cheap to revisit, because a later
  binding undoes nothing here.

### 16.9 Finding (for the release package; not written here)

- **F-5.** The first release that carries F is any release cut from `main` after WO-S05-5. Its envelope's `packages`
  must list S05. Its distribution and data gate (V18, D04) must re-run on the new member and on NOTICE. Its CHANGELOG
  must name the IAPWS data. `v0.2-envelope-1` covers 0.2.0 only and is unchanged.

### 16.10 WO-S05-5 (build lane, `sonnet-implementer`, ~60k; `wp/S05-pack` from `main` after `wp/S05-wo4` and this)

1. **Package F:** a `PACKAGED` entry after M02's (docstring clause), A26(b)'s link, and the `package-data` pattern
   `"_data/benchmarks/s05/iapws95_coefficients.json"`; the comments cite R-616.
2. **Attribution:** append §16.3's block to NOTICE; write `docs/attributions/iapws95-v1.md` as §16.3 lists.
3. **Tests:** in `test_s05_envelope.py`, §16.2's A26 replaces both A26 tests; add A31 ((d) in the wheel node) and A32;
   the thirty-assertions test expects 33. In `test_t08_w4_package_data.py`, 5 becomes 6 (comment: R-616).
4. **Generator** (`s05_evidence_manifest.py`): `ASSERTIONS` = A01–A33; `assertion_table` takes §6.1's rows, replaced or
   extended by id from §16.2's and §16.6's tables. A33 has no test node: it is judged on its measured half alone, run
   from `--a33-base <commit>` (absent → `fail`). The coefficient artifact loses "not packaged"; the unpackaged
   limitation becomes "the coefficient file is package data, with IAPWS's attribution in NOTICE (R-616)".
*Items 1–4 are done at `6acbe4f9`. Erratum 1 (§16.12, R-617) replaces items 5–7 with the following.*

5. **Erratum, in the packaging range (before C_m):**
   - `tests/test_t08_w2_inventory.py`: apply §16.12.1's amendment, using the names and controls exactly as given.
   - `benchmarks/t08/support_envelope.yaml`: set L40's `text` to T_L40. Re-emit `docs/support-matrix.md`, then run
     `t08_support_matrix.py --check`.
   - `scripts/s05_evidence_manifest.py`:
     - `assertion_table` also reads §16.12, after §16.6, and replaces rows by id. The section ends at `### 16.13`.
     - Rewrite A33 per §16.12.3. `A33_PATHS` gains `M\ttests/test_t08_w2_inventory.py`. (b) becomes the whole-document
       comparison with L40's text removed; this drops the `["property_model"]` lookup, and T_L40 becomes a constant.
       Add (e).
     - Add `--check-harvest <C_m>` per §16.12.2: one output line, exit codes 0 and 1.
   - Run `test_s05_envelope.py`, `test_t08_w4_package_data.py`, `test_t08_w2_support_envelope.py` and
     `test_t08_w2_inventory.py -k a32`. The last must report passed with 0 skipped, recorded in `docs/C10_DECISIONS.md`.
     Also run `t08_support_matrix.py --check`.
   - Commit. That commit, or a later docs-only commit, is C_m.
6. **Manifest at C_m:** on a clean tree at C_m, run the generator with `OFS_S05_BUILD_PYTHON` set and
   `--a33-base 92779215aabab270d4630dc6ba6920cd4192c350`.
   - A26(d) and A31(d) run; they never skip.
   - The computed status must be `tested`. If A33 fails, stop and escalate.
7. **Harvest at H:**
   - Commit the manifest.
   - Harvest it into `support_envelope.yaml`.
   - Move `HARVEST_SIZE` and extend its `#:` comment.
   - Cite the manifest under D08 in `docs/requirements.yaml`. D08's "Not claimed" still says that neither `pr-lib-v1`
     nor `iapws95-v1` is selectable, and that `pr-lib-v1` is not shipped.
   - Commit; that commit is H.
   - Run `s05_evidence_manifest.py --check-harvest <C_m>`. It must print PASS. Quote its line in `docs/C10_DECISIONS.md`
     in a docs-only commit.
8. **Gates:** `t08_dist.py`, HG again at the branch tip, and `gate.sh` before the merge. The status is `tested`. There is
   no `reviewer` pass, because A33 and HG are the proof. Do not merge `main` into the branch before H.
9. **Never** edit `iapws95.py`, F, `s05_reference.py`, `s05_crosscheck.py` or their JSON, `revision_binding.py`,
   `snapshot.py` or `LIBRARY_ONLY_PROVIDERS`. If A33(a) or HG(a) fails, stop and escalate.

### 16.11 What this amendment does not establish

- **A legal opinion.** The terms are quoted and Frank decided. Whether CoolProp's MIT notice is owed is not decided
  beyond R-594's reading that the values are IAPWS's, now confirmed against print.
- **A release.** Packaging puts F in every wheel built from `main`. Releasing is a later act (F-5).
- **Any binding.** No flowsheet with water becomes runnable, and no W27 coverage count moves.
- **M from print** (Q-7, unchanged).
- **Anything numerical.** No value, tolerance or expectation of §6 moves.
- **An end-to-end run of an installed wheel in a fresh environment.** A26(d) and A32 cover it in two parts.

### 16.12 Erratum 1 to Amendment 3, 2026-10-23 (design lane, `specifier`; R-617)

**Source.** The build lane stopped WO-S05-5 after items 1–4 (`6acbe4f9`, branch `wp/S05-pack`), as §16.6 told it to,
because A33(a) could not pass. This amendment has four defects:

1. **T08.A32 was not amended.** `tests/test_t08_w2_inventory.py::test_a32_no_third_party_data_in_the_sdist_or_the_wheel`
   fails on the built artifacts. F is third-party data, and `SHIPPED_DATA` (the project's own package data) does not
   match it. §16 changed what the wheel carries and left standing the T08 assertion that forbids it.
2. **The harvest moves an unlisted path.** Item 5's harvest moves `HARVEST_SIZE` in `tests/test_m07a_harvest.py` by
   one manifest and its items, as every manifest does. A33(a) does not list that path.
3. **The order is impossible.** The manifest command judges A33 at the measured commit. The harvest classifies that
   manifest, so it comes after it. Harvest rows can therefore never be inside the measured range, and A33(a)'s
   `M benchmarks/t08/support_envelope.yaml` cannot hold as written. (b) also names a key that does not exist:
   `property_model` is an entry of the envelope's `axes` list, not a top-level key.
4. **L40 becomes false.** L40 is the envelope's statement for T08.A32's third clause. It says the sdist and the wheel
   carry "the project's own code, its package data (...) and its licence files only". After item 1 that is false.

None of the four moves a number, an entry of §16.5's "Unchanged" list, or a frozen interface. The repairs follow:
§16.12.1 for defects 1 and 4, §16.12.2 for defects 2 and 3, and §16.12.3 for the amended A33.

#### 16.12.1 T08.A32, amended for one file (not loosened)

T08.A32 has three clauses (T08 release spec, the A32 row). The second is "no third-party data in sdist or wheel". It
gains one named exception. This follows the pattern of M01 §3.5 (R-158) and L01 §12.4 (R-529): amended for a named
item, not relaxed.

> **T08.A32, second clause, as amended by S05 §16.12 (R-617).** The sdist and the wheel carry no third-party data,
> with one exception. A member is admitted when its path, without a leading `src/`, is a key of `ATTRIBUTED_DATA`,
> and only if both of these hold:
> (i) its bytes hash to that key's SHA-256;
> (ii) the same artifact's NOTICE, whitespace collapsed, contains that path and each of S0, S1 and S2 (§16.3).
> `ATTRIBUTED_DATA` has exactly one key, P_F = `openflowsheet/_data/benchmarks/s05/iapws95_coefficients.json`, and
> its value is H_C. Each artifact holds exactly one admitted member.

**The rights record.** No new rights row is needed. F is not a ComponentRecord, so the first clause's `rights` field
does not apply to it. The admission rests on three things: Frank's decision (C10 "Ship decision", R-616), the terms
quoted at `af04961e`, and the attribution inside the artifact itself. Condition (ii) checks that record in the
artifact a user receives. F cannot be admitted into an artifact whose NOTICE lacks the attribution.

**Implementation in `tests/test_t08_w2_inventory.py`.** The names below are binding, because A33(e) checks them.
- `SHIPPED_DATA` and `PACKAGING` are unchanged. F is not the project's own data. In `SHIPPED_DATA` it would be
  admitted as any bytes at that path, with or without the attribution.
- Two new module-level constants, as plain assignments:

  ```python
  # S05 spec §16.12 (R-617): third-party data shipped under recorded terms, admitted only with its
  # hash and with its attribution in the same artifact's NOTICE (Frank, C10 "Ship decision", R-616).
  ATTRIBUTED_DATA = {
      "openflowsheet/_data/benchmarks/s05/iapws95_coefficients.json": (
          "b9e93877e37874f1b3a483e298a45692e264d70686d4c158372084b96abbe6ed"
      ),
  }
  IAPWS_ATTRIBUTION = (S0, S1, S2)  # the three strings of S05 spec §16.3, verbatim
  ```

- One new helper:

  ```python
  def _attributed(name: str, content: bytes, notice: bytes) -> bool:
      path = name.removeprefix("src/")
      if path not in ATTRIBUTED_DATA:
          return False
      text = " ".join(notice.decode("utf-8").split())
      return (
          hashlib.sha256(content).hexdigest() == ATTRIBUTED_DATA[path]
          and path in text
          and all(" ".join(string.split()) in text for string in IAPWS_ATTRIBUTION)
      )
  ```

- In `test_a32_no_third_party_data_in_the_sdist_or_the_wheel`, each artifact's NOTICE is located the way T08.A31
  locates it: in the sdist, the member `NOTICE`; in the wheel, the single member matching
  `[^/]+\.dist-info/licenses/NOTICE`. A missing NOTICE fails the test. The `other` list also excludes every member
  for which `_attributed(name, content, notice)` is true. Then the test asserts:
  - **(P)** each artifact has exactly one admitted member: `src/` + P_F in the sdist, P_F in the wheel;
  - **controls**, on the wheel's admitted member, each of which must make `_attributed` false:
    - (α) the notice cut to `notice[:1292]`, which is NOTICE before R-616 (A33(c));
    - (β) the content changed to `content + b"\n"`;
    - (γ) the name changed to `openflowsheet/_data/benchmarks/s05/x.json`.
- The test's docstring or comment cites S05 §16.12 and R-617. Nothing else in the file changes (A33(e)).

**Why each part is there.**
- (P) exercises the admission branch, so the test sees a later loss of F from the artifact, or of the condition.
- (α) shows that the attribution condition is live: the old NOTICE fails it.
- (β) shows that the hash condition is live.
- (γ) shows that the exception covers one path only.

All of this compares bytes, hashes and strings, so the tolerance is exact.

**The skip rule.** The node uses the `built` fixture, which skips when the build backend cannot be installed. A skip
is not a pass. Before C_m (§16.12.2), the build lane runs `pytest tests/test_t08_w2_inventory.py -k a32` and records
"passed, 0 skipped" in `docs/C10_DECISIONS.md`.

**L40.** Its `text`, whitespace collapsed, becomes exactly T_L40:

```text
The reference-tool data (the IDAES and DWSIM environments, their downloads and their outputs) and OpenIDAES-450 are not distributed: the sdist and the wheel carry the project's own code, its package data (since M01 including the five C1 records, M01 spec §15 Q-N4's default), its licence files and one third-party data file, the IAPWS-95 coefficients `benchmarks/s05/iapws95_coefficients.json`, under IAPWS's terms with their attribution in NOTICE (S05 spec §16, R-616, R-617), and nothing else; every ComponentRecord is synthetic (SYN-001) or one of M01's five real C1 records, each with its identifiers, rights, per-parameter provenance and retrieval equality (M01 spec §3.5, R-158).
```

- L40's `evidence` does not change.
- T_L40 keeps the three words that T08.A32's third-clause test looks for: `not distributed`, `OpenIDAES-450` and
  `reference`.
- `docs/support-matrix.md` is re-emitted from the envelope (`t08_support_matrix.py`, then `--check`).
- The T08 spec's A32 row is not edited. `t08_support_matrix.py` reads that spec, and this amendment lives here, as
  M01's and L01's do.

#### 16.12.2 Two ranges

WO-S05-5 is judged over two consecutive ranges.

| range | from | to | judged by |
| --- | --- | --- | --- |
| packaging | B = `92779215aabab270d4630dc6ba6920cd4192c350` (`main`, the parent of `6acbe4f9`) | C_m, the measured commit: HEAD when the S05 manifest command runs with `--a33-base B` | A33 as amended (§16.12.3), inside the manifest |
| harvest | C_m | H, the commit that harvests C_m's manifest | the harvest gate HG, `scripts/s05_evidence_manifest.py --check-harvest C_m`, run at H |

HG is a gate of the work order, not an S05 assertion. It comes after the manifest because no manifest can judge its own
harvest. There are still thirty-three assertions.

`main` is not merged into the branch between B and H. A merge would put `main`'s changes into both diffs. A merge with
`main` comes after HG, and `gate.sh` judges it.

**HG.** `--check-harvest <C_m>` refuses (exit 1) unless the working tree is clean. It judges `C_m..HEAD`. It exits 0
only if all four parts hold. Otherwise it exits 1 and names the failing parts.
- **HG(a)** Outside `docs/` and `evidence/`, `git diff --name-status C_m..HEAD` lists exactly
  `M benchmarks/t08/support_envelope.yaml` and `M tests/test_m07a_harvest.py`.
- **HG(b)** In `support_envelope.yaml`:
  - with `harvest` removed, the files at C_m and at HEAD load to equal documents;
  - C_m's `harvest` list is a prefix of HEAD's;
  - the appended entries' `(manifest, item)` pairs have no duplicate;
  - as a set, those pairs equal the `t08_support_matrix.harvest_items()` keys whose manifest is
    `evidence/S05/<C_m>/manifest.json`, and that set is not empty.
- **HG(c)** In `tests/test_m07a_harvest.py`:
  - the module's `ast.dump` at C_m and at HEAD are equal once `HARVEST_SIZE`'s assigned value is removed, so only
    that value and comments may change;
  - HEAD's `HARVEST_SIZE[0]` is C_m's plus 1;
  - the sum of its other two components grows by the size of HG(b)'s set. M07a.A50's own test, run at HEAD, pins how
    that growth splits into limitations and checks.
- **HG(d)** `evidence/S05/<C_m>/manifest.json` is tracked at HEAD, and its `status` is `tested`.

It prints one line, for example
`S05 HG <C_m>..HEAD: PASS (n appended; HARVEST_SIZE (46, 529, 72) -> (47, …, …))`.

**Why each part is there.**
- HG(a) is the harvest commit's identity, exact both ways, as A33(a) is for the packaging range.
- HG(b): the harvest only appends, it appends only this manifest's items, and it appends all of them.
- HG(c): the only code change is the quoted size, and the size follows the harvest.
- HG(d): a failed manifest is never harvested as done.

HG is run at H, and again at the branch tip if docs-only commits follow. Such commits do not change its result.

#### 16.12.3 A33, as amended

This row replaces §16.6's A33. `assertion_table` reads this table after §16.2's and §16.6's tables, and a row replaces
the row with the same id.

| id | assertion | expectation | tolerance |
| --- | --- | --- | --- |
| A33 | Identity of the packaging range B..C_m (§16.12.2): a manifest command run once at C_m with `--a33-base B`. (a) Outside `docs/` and `evidence/`, `git diff --name-status B..C_m` lists exactly: `M NOTICE`, `M pyproject.toml`, `M src/openflowsheet/resources.py`, `A src/openflowsheet/_data/benchmarks/s05/iapws95_coefficients.json`, `M tests/test_s05_envelope.py`, `M tests/test_t08_w4_package_data.py`, `M tests/test_t08_w2_inventory.py`, `M scripts/s05_evidence_manifest.py` and `M benchmarks/t08/support_envelope.yaml`. (b) With L40's `text` removed from both, `support_envelope.yaml` at B and at C_m loads to equal documents. So every `axes` entry (`property_model` among them), every `harvest` entry and every other row is unchanged. At C_m, L40's text, whitespace collapsed, equals T_L40 (§16.12.1). At B, L40's text does not contain `iapws95_coefficients.json`. (c) At C_m, NOTICE hashes to `24790a6d…37dd8a` and its first 1292 bytes to `11b9cac8…02c38f` (§16.3). At B, NOTICE contains none of S0, S1 and S2. (d) At C_m, `iapws95.py` hashes to `c480f55f…cdbcd8d01` and F to H_C. (e) In `tests/test_t08_w2_inventory.py`: `ATTRIBUTED_DATA` is absent at B. At C_m it is a plain module-level assignment, and its value under `ast.literal_eval` is exactly `{"openflowsheet/_data/benchmarks/s05/iapws95_coefficients.json": H_C}`. Every other module-level statement has the same `ast.dump`, in the same order, at B and at C_m. The exceptions are imports, the module docstring, and the definitions of `IAPWS_ATTRIBUTION`, `_attributed` and `test_a32_no_third_party_data_in_the_sdist_or_the_wheel`. So `SHIPPED_DATA`, `PACKAGING` and every sibling test are unchanged | the list; equality; T_L40; the hashes; the dict | exact |

**Why the new parts are there.**
- **(a)'s two added lines** are the T08.A32 amendment and L40. HG covers the harvest paths.
- **(b)** now compares the whole document, so no key lookup can miss its target (defect 3). B's clause is the control:
  it shows the old L40 does not satisfy the new text.
- **(e)** makes "one file, not a general loosening" executable. A widened `SHIPPED_DATA`, a second key or an edited
  sibling test fails A33.

All parts compare names, bytes, strings, hashes and syntax trees. The roundoff floor is zero, and any difference is a
defect.

If a path outside A33(a)'s list or HG(a)'s list must change, the amendment is wrong again. Stop and escalate (rule 6).
Do not widen a list.

#### 16.12.4 Rejected alternatives

- **Add P_F to `SHIPPED_DATA`** (the build lane's proposal). That classes F as the project's own data. It would also
  admit any bytes at that path, without the attribution.
- **Judge A33 after the harvest, with the harvest paths listed.** The manifest would have to be taken after its own
  harvest. A re-take at H would need a harvest of its own, and so on without end.
- **Leave L40 alone until the release (F-5).** That leaves a known-false statement in the live envelope, and T08.A32's
  third-clause test cites L40 as its evidence.
- **Make HG a pytest node.** HG needs C_m and the history after it, and no committed file names C_m before H. The
  generator already reads history for A33.

### 16.13 What the erratum does not establish

- **A new S05 assertion.** There are still thirty-three. HG is a gate of WO-S05-5 and says nothing about S05's
  content.
- **A rule for third-party data in general.** A second file needs its own ruling and its own key.
- **A change to ADR 0006.** Its mode-A row says "the project's own bytes only", and in context that is about CasADi.
  ADR 0045's release condition is the authority for F. **Finding F-6:** clarify ADR 0006 D1 the next time it changes.
  This erratum does not change it.
- **A legal opinion**, as §16.11 says.
- **Anything numerical.**

## 17. Erratum, 2026-10-23 (design lane, `reviewer`; S07 review; R-626)

**§4.4, strip bracket.** For T ∈ (647.0 K, T_c), outside the box, the saturated densities at T bound the
brackets **where the saturation converges**. Where it does not, the bracket is the T ≥ T_c one: (0, 1250 kg/m³],
starting from min(P/(R_S T), 1250 kg/m³).
- **Where that happens.** The Newton from the IAPWS ancillaries fails only for θ ≲ 1e-6, which is above about
  647.0954 K. There the loop's pressure range is ≲ 1e-5·p_c, well inside the box [22.0, 22.2] MPa, so the root on
  (0, 1250] is unique for every state outside the box.
- **What changed.** Before, those states were refused `saturation_not_converged` (§6.5 row 9), even though 647.09 K
  and 647.096 K answered. The rule is implemented in `8cab0e15` (design note
  `docs/design/S07-near-critical-saturation.md`, D3 and D5). No registered value, `s05_reference.json` entry or
  probe outcome changes: the S05 record of 38 010 calls is byte-identical, and `--check` passes.
- **What did not change.** S05 gets no fallback saturation solve. Its Newton converges at every 0.05 K from 273.16 K
  to 647.0 K.
- **Tests.** S07 spec §19.7, A50.
