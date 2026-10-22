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
  the release (§9, §10 Q-1).
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

| constant | value | role |
| --- | --- | --- |
| R_s | 461.51805 J/(kg·K) | the formulation's specific gas constant |
| M | 0.018015268 kg/mol | molar mass |
| R = R_s·M | 8.3143713575874… J/(mol·K) (8.314371357587 to 13 digits) | the molar gas constant used everywhere, **not** CODATA's 8.31446261815324 |
| T_c | 647.096 K | reducing temperature, τ = T_c/T |
| ρ_c | 322 kg/m³ | reducing density, δ = ρ/ρ_c |
| p_c | 22.064 MPa | the critical pressure. It is a registered constant, not an output of the EOS: p(ρ_c, T_c) agrees with it to 1e-5 (claim) |
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
| `R6_500` | 500 | 838.025 | R6-95 Table 6, point 1. Liquid-like; the power terms dominate, and the Gaussian and non-analytic terms are below 1e-20 here, so they are **not** tested by this state |
| `R6_647` | 647 | 358 | R6-95 Table 6, point 2. Near-critical; the Gaussian (≈ 3e-2) and non-analytic (≈ 1e-1·n) terms are large, so a dropped or mis-signed term changes φʳ well above tolerance |
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
- **C11 — The floor's margin.** For each derivative quantity, the measured central-difference floor of CoolProp 8.0.0
  at step 1e-6·x, times 10, is ≤ the tolerance of S05.A17.

`s05_crosscheck.py` refuses to write when any of these fails:
- CoolProp's `Water` string does not have its recorded hash;
- an unexpected term family appears;
- R_s·M differs from CoolProp's molar R by more than 1e-12;
- the reducing state is not (647.096 K, 322 kg/m³);
- any coefficient differs from iapws 1.5.5's.

## 8. Findings (for other documents; not written here)

- **F-1.** When ADR 0045 is accepted, ADR 0001 D5's list of reference conventions and `interfaces-frozen.md` need an
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

- **Q-1, needs a fact (= C10-Q1).** Do the release's Tables 6–8 match? The settling measurement: a person with access
  to iapws.org compares the generator's `phi_states.R6_500` and `R6_647` `*_9` keys with Table 6, and the saturation
  and single-phase entries with Tables 7–8, and reads the release's terms.
  *Default:* build and test on the transcription now, and do not package the coefficient file (R-594).
- **Q-2, needs the user's preference (= C10-Q2).** How should T ≥ T_c be labelled? *Default:* VAPOR (R-590).
- **Q-3, needs a fact.** Is the Maxwell solve fast enough for flowsheet use? The settling measurement: WO-S05-1 records
  the median `evaluate_phase` time at `L_ambient` in its build-decisions log. *Default:* no cache. An exact-T cache is
  added only if the measured time exceeds 1 ms.
- **Q-4, needs the user's preference.** Should `g`, `cv` or the speed of sound be exposed? *Default:* no; they are
  additive ids for a later spec.

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
