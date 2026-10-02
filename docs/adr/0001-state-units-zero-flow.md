# ADR 0001 — State representation, units, sign conventions, and zero-flow semantics

**Status:** Accepted (P01 default; recorded per plan §4.1 "Phase-0 ADRs", blueprint §16 item 2)  
**Date:** 2026-09-06  
**Author:** Fable 5.1 (Fable owns scientific semantics, plan §1.3)  
**Affected requirements:** D08 (thermodynamic contract), A01 (phase ownership, only insofar as phase signatures are stream labels), STA-01–04 and THM-05 cases (plan §6.1), blueprint §4.2, §6.4, §7.3  
**Affected packages:** P01, K02, K03, K04, T01, T05  
**Blueprint authority:** §4.2 "State representation and conservation" is binding; this ADR records the concrete defaults that section leaves open.

## Context

Blueprint §4.2 fixes the invariants: SI internally with explicit amount and mass bases; absolute temperature and temperature difference are distinct quantities; component molar flows are the default extensive material variables; at exactly zero material flow, composition is undefined and must not be forced; heat and shaft work are positive into a unit unless a model declares another convention. Several concrete choices remain open and must be fixed before any unit model, oracle, or schema is written, because every later package builds on them and no test would catch a silently inconsistent convention. This ADR fixes those choices. It does not decide scaling policy (K03, ADR 0004/0005 territory), canonicalization (ADR 0002), or phase-attempt control (ADR 0005).

The SYN-001 fixture already exercises every zero-flow rule below: the recycle stream has exactly zero flow at r = 0, the vapor product has exactly zero flow in the 310 K all-liquid variant, and the liquid, purge, and recycle streams all have exactly zero flow in the 420 K all-vapor variant (see `docs/derivations/SYN-001.md` §7).

## Decision

### D1. Units and dimensions

1. Internal units are unprefixed SI: mol, kg, m, s, K, Pa, J, W. No internal quantity is stored in a display unit. Display units belong to `Quantity.display_unit` and are conversion metadata only.
2. A dimension is the integer exponent vector over the seven SI base dimensions in the fixed order `(length, mass, time, temperature, amount, current, luminous_intensity)`. Pressure is `(-1, 1, -2, 0, 0, 0, 0)`; molar flow is `(0, 0, -1, 0, 1, 0, 0)`; molar enthalpy is `(2, 1, -2, 0, -1, 0, 0)`.
3. Every `Quantity` carries a `kind` in addition to its dimension. Two kinds share the temperature dimension and are not interchangeable: `temperature` (absolute, K, lower bound 0 exclusive) and `temperature_difference` (K, unbounded). Arithmetic rules: `temperature − temperature → temperature_difference`; `temperature ± temperature_difference → temperature`; `temperature + temperature` is a validation error. Converting a `temperature` from °C adds 273.15; converting a `temperature_difference` from °C is the identity. Other kinds (`pressure`, `molar_flow`, `mass_flow`, `heat_rate`, `power`, `molar_enthalpy`, `mole_fraction`, `dimensionless`, and the component-parameter kinds `molar_mass` kg/mol, `molar_heat_capacity` J/(mol K), `molar_volume` m³/mol) exist to make schema validation precise; they add no arithmetic rules beyond dimension checks. The three component-parameter kinds were added during P01 at Opus's request (SYN-001 component records carry M_i, c_p, and v_i) and confirmed by Fable on 2026-09-07; the vocabulary is frozen with the rest of D1 at P01 close and is normative in `schemas/units.json`.
4. Amount basis is primary. Mass basis is derived through the component molecular weight `M_i` (kg/mol) recorded in `ComponentRecord`; there is no independent mass state. A mass-basis input is converted to component molar flows at validation time and the conversion is recorded in provenance (STA-03 tests this both ways).
5. Nonfinite numbers are rejected in every semantic input. Signed zero is normalized to +0.0 in canonical form (ADR 0002 defines the canonical encoding; this ADR fixes the semantic rule that −0.0 and +0.0 are the same state).

### D2. Material stream state

1. A material stream state is the tuple `(n, T, P)` with `n ∈ ℝ^{N_c}` the component molar flows in mol/s (ordered by the revision's component set), `T` absolute temperature in K, and `P` pressure in Pa. This is the *default state definition*, identified as `state_definition = "nTP-v1"`. Alternative definitions (mass basis, `(n, H, P)`, mole-fraction-plus-total) enter only through explicit adapters that declare their state-definition ID (blueprint §4.2).
2. Derived quantities are computed, never stored as state: total molar flow `n_tot = Σ n_i`; mole fractions `x_i = n_i / n_tot` **only when `n_tot > 0`**; mass flow `ṁ = Σ n_i M_i`; enthalpy flow `Ḣ = Σ n_i h_i(T, P, phase)`.
3. Bounds: `n_i ≥ 0` for every component. `T` and `P` bounds come from the property provider's declared domain (for SYN-001: 280–440 K, 50 000–200 000 Pa). A trial state violating a bound is an *invalid trial state* (blueprint §7.7 table) and is reported as such; it is never clipped, projected, or silently replaced inside a residual or Jacobian evaluation. Projection is an initializer action and is logged (blueprint §7.4).
4. Phase is **not** a free state variable of a stream. A stream carries (a) a declared *phase capability* from `{liquid, vapor, vapor_liquid}` set by the connected models and (b) a *phase signature*, which is a result of evaluation: `LIQUID`, `VAPOR`, `TWO_PHASE`, or `ZERO_FLOW`. The phase signature participates in the active-set signature of blueprint A01; ownership of the active set during a nonlinear attempt is decided by ADR 0005, not here.
5. Two-phase streams are represented by the single `(n, T, P)` tuple plus the signature; the phase split `(V, L, x, y)` is a reconstructable result, recomputed from the provider at the same `(n, T, P)` whenever needed. Storing the split as state would create two descriptions of the same function and violate the residual/Jacobian identity rule (CLAUDE.md, blueprint §6.4).

### D3. Zero flow and zero components

1. **Exact zero flow.** A stream with `n_tot == 0` exactly (IEEE equality after signed-zero normalization) is *dormant*. Its composition is undefined. Its `T` and `P` remain labels and are retained (they may be needed as initialization hints and as pressure-network values) but no property that requires composition is evaluated for it. Its enthalpy flow, mass flow, and every component flow are exactly `0`. Its phase signature is `ZERO_FLOW`. An initialization hint attached to a dormant stream (for example a composition guess) is labeled `hint` and is not a constraint (blueprint §4.2).
2. **No division by total flow.** Evaluators and residuals are written in terms of `n_i`, never in terms of `x_i` unless guarded by `n_tot > 0`. Balance residuals are linear in component flows so a zero term is exact. The rule "do not divide by total flow or impose arbitrary normalized composition to force solvability" is a hard invariant with an adversarial test (STA-01).
3. **Zero component in a flowing stream.** If `n_tot > 0` but `n_i == 0` for some `i`, then `x_i = 0` exactly and the component is *inactive* in that stream. Phase equilibrium is formulated as `y_i = K_i x_i` with `K_i = K_i(T, P)`; because the ideal-mixing chemical-potential terms `RT ln x_i` and `RT ln y_i` appear only through their *difference*, the K-value form never evaluates `ln 0`. Enthalpy and balance sums are linear and pass exact zeros through. Any evaluator that needs `ln x_i` directly (none in v0.0) must declare it in its `ModelManifest.validity` and guard it; `ln(0)` is never evaluated unguarded (plan §3.1). Adversarial test STA-02 covers a zero component through mixer, heater, flash, and splitter.
4. **Zero-flow units.** A mixer with one or more dormant inlets treats them as absent (their component and enthalpy contributions are exactly 0). A splitter with a dormant inlet produces dormant outlets. A heater with a dormant inlet produces a dormant outlet and exactly zero duty. A TP flash with a dormant feed produces two dormant outlets, exactly zero duty, and phase signature `ZERO_FLOW`; this is a valid result, not a failure. A flash whose feed flows but whose result has `V = 0` (or `L = 0`) produces a dormant vapor (or liquid) outlet with signature `LIQUID` (or `VAPOR`) on the unit and `ZERO_FLOW` on the dormant stream.
5. **Zero flow in tears and scaling.** Tear variables are component flows bounded below by 0. A tear vector at exactly 0 (SYN-001 at r = 0) is a valid iterate. Variable scales are never derived from a current value that may be zero; they come from registered throughput scales (physical nominals, blueprint §7.3). This ADR fixes the invariant; K03 fixes the scale construction.
6. **Positive log transforms are forbidden** for any variable that must reach zero (component flows, phase amounts). Bound-aware coordinates or phase-specific formulations are used instead (blueprint §4.2).

### D4. Sign conventions and energy bookkeeping

1. Heat duty `Q` and shaft work `W` are positive *into* the unit. The steady-state energy balance of every unit is `Σ_in Ḣ + Q + W = Σ_out Ḣ`. A model using another convention must declare and map it in its `ModelManifest`; no such model exists in v0.0.
2. A *heater* is a unit with a TP-state outlet: the outlet temperature is specified, the duty is a calculated unknown, and the duty may be negative (the unit then cools). SYN-001 at r = 0.95 has `Q_heater ≈ −16 144.6 W` because the adiabatic mixer outlet (354.73 K) is above the 350 K setpoint. This is a supported result, not an error, and is registered as such.
3. A *flash* at specified `(T, P)` likewise has a calculated duty of either sign.
4. Specifying a unit's outlet temperature **and** its duty is an over-specification and is rejected at validation as a structural conflict (plan §3.3 "conflicting heater T-and-duty specification"; STR-03).
5. Pressure: every stream carries `P`; a unit with zero declared pressure drop copies inlet `P` to outlet `P` as an equation, not as an assumption baked into the state. SYN-001 has all pressure drops zero. Pressure compatibility at a mixer (all inlet pressures equal to the outlet pressure) is an explicit equation set; a mismatch is a validation failure, not something a unit silently repairs (blueprint §4.2).

### D5. Reference states and provider compatibility

1. Every property provider declares a `reference_convention` identifier. SYN-001 declares `SYN-001-ref-v1`: pure liquid at `T_r = 300 K`, `P_r = 100 000 Pa` has `h_i^L = 0` and `g_i^L = 0`; the vapor reference enthalpy offset is `L_i` (see the derivation).
2. Enthalpy flows are comparable only between streams evaluated with the same provider implementation hash, data hash, and reference convention. Mixing two streams whose provider/reference identities differ is a validation error (`REFERENCE_MISMATCH`, THM-05). No implicit reference shift is ever applied.
3. Because references are consistent within a provider, *internal* enthalpy contributions cancel in an overall balance. For SYN-001 the sum of the heater and flash duties equals the enthalpy of the external products minus the enthalpy of the fresh feed for every recycle ratio (numerically 56 338.069 W at 360 K); a separately assembled energy check uses this identity and, per blueprint A09, is labeled as sharing the same synthetic thermodynamics.

### D6. Tolerances (registered for SYN-001 only)

The plan §3.3 preimplementation tolerances are adopted for the SYN-001 nominal fixture and confirmed against oracle accuracy in the derivation (§9 there): component balance `1e-9 mol/s + 1e-8 × throughput scale (3 mol/s)`; energy `1e-5 W + 1e-8 × 1e5 W`; `T` `1e-6 K`; `P` `1e-2 Pa`; normalized composition `1e-10`. They are case-specific and are not applied to any real process (blueprint §8.1).

## Alternatives considered

- **Mole fractions plus total flow as state.** Rejected: undefined at zero flow, and forces either division by total flow or an arbitrary composition (blueprint §4.2 forbids both).
- **Phase fraction as a stream state variable.** Rejected: it duplicates information that the provider computes from `(n, T, P)`, which would let residual and Jacobian paths drift apart.
- **Log-flow coordinates for positivity.** Rejected for flows: components and phases must be able to reach exactly zero (blueprint §4.2). May be reconsidered for strictly positive variables in a later ADR.
- **Heat positive out of a heater ("duty consumed").** Rejected: one global sign rule (positive into the unit) with explicit per-model mapping is simpler to verify than per-unit-type conventions.
- **Storing −0.0.** Rejected: canonical identity would then distinguish physically identical states.

## Consequences

- `Quantity`, `ComponentRecord`, and `Specification` schemas (P01) must carry `kind`, `dimension`, `unit`, and for `ComponentRecord` the molecular weight and the `elemental_composition: null` state that marks elemental verification `NOT_APPLICABLE` for pseudo-components.
- K02 unit models must implement the zero-flow behaviors of D3.4 and are tested by STA-01/02 and by the r = 0, 310 K, and 420 K SYN-001 variants.
- K03 must construct scales from registered nominals, never from iterate values (D3.5).
- K04 energy checks carry the shared-provider qualification of D5.3.
- Any change to D1–D5 requires a new ADR; these rules are part of the P01 interface freeze.

## Acceptance evidence

- This ADR is exercised, not merely stated, by: the P01 oracle tests (zero-flow recycle at r = 0; zero-flow vapor at 310 K; zero-flow liquid/recycle/purge at 420 K; negative heater duty at r = 0.95; two-phase heater outlet at r = 0, 310 K, and 420 K), and by the STA-01–04 and THM-05 cases registered for K02/K04.
- Numerical verification: `docs/derivations/SYN-001.md` and `evidence/P01/<commit>/manifest.json`.
- Process-modeling review: pending (human sign-off recorded separately; not claimable by an agent).
