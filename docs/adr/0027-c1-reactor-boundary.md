# ADR 0027 — The C1 reactor boundary: the group's 1D reactor behind a zero-pressure-drop, extent-projected, process-side-duty contract

**Status:** Proposed, 2026-10-08. Accepted when M01's evidence manifest is `tested` (WO-6, the stand-in) and M02's
adapter reproduces the probe's design-grid regression values (M01.A41–A48 through the adapter).
**Date:** 2026-10-08
**Author:** design lane (`specifier`), M01.
**Normative text:** `docs/derivations/M01-spec.md` §8 (the boundary), §10 (refinement evidence), §12 (known invalid
requests), §9.6 and §9.9 (assertions). Measured record: `benchmarks/m01/reactor-probe.json` (version 2) from
`benchmarks/m01/reactor_probe.py`; configuration rows `benchmarks/m01/reactor-overlay.json` from
`docs/derivations/scripts/m01_reference.py`.
**Amends:** ADR 0022 D2 (the loop's pressure-drop question it left to M01 is decided here: the zero-pressure-drop
convention); corrects the dossier §6 statement that the reactor uses Peng–Robinson density (ideal gas at the pin).
**Affected requirements:** W21 (PyMRM boundary, accuracy, execution, provenance); M02's acceptance "incompatible
pressure boundary rejected".
**Affected packages:** M01 (boundary module, stand-in), M02 (adapter), M04–M07 (inherit the contract, the grid and
its error estimate).
**Companions:** ADR 0001 D3–D4 (zero flow, signs), ADR 0008 (no time at the evaluation boundary), ADR 0011 D2 (total-
enthalpy balance on a formation datum), ADR 0022 revision 1 (the pin), ADR 0026 (the provider whose enthalpies the
boundary uses), R-152 (K_NH₃).

## Context

The reactor (`ammonia_synthesis_reactor` @ `6089593`, MIT, `MembraneReactor1D`, all permeances zero) takes a molar
flow, composition and temperature at its inlet and a pressure at its **outlet**, has an Ergun pressure drop, its own
ideal-gas thermodynamics and fugacity correlations, a co-current coolant tube, and a pseudo-transient solver whose
acceptance is an absolute residual norm of 10⁻³. It knows three species. Measured for M01 (spec §8, §10): cold starts
with real NH₃ at the inlet stall; at the group's tolerance two accepted states differ by 0.45 % in outlet NH₃; the
residual norm's roundoff floor grows like num_z²; the outlet converges in num_z at an observed order of only 0.6–0.8;
23–33 % of the reaction heat leaves through the inlet face (finding F-R3).

## Decision

**D1. Ports, DOF, scaling.** One vapour inlet, one vapour outlet, one energy port; rows n_out − n_in − ν ξ = 0,
ξ = Ξ, T_out = Θ, P_out = P_in, Q = Ḣ_out − Ḣ_in; DOF 0 given the inlet and the configuration. The reactor is
N_tubes identical tubes (a positive real configuration parameter): per-tube inlet flow n_tot/N_tubes; the map is
homogeneous of degree 1 in (n, N_tubes). The configuration (G2 geometry and coolant, sweep ratio 1, num_z, overlay,
profile, N_tubes) is part of the unit's identity.

**D2. Pressure: the zero-pressure-drop convention.** P_out = P_in; the reactor runs with p_ret_out = P_in; admissible
iff |ΔP_Ergun|/P_in ≤ ε_P = 10⁻³, else `unsupported`, `pressure_drop_exceeds_convention`. Measured at the nominal
point: 5.0 × 10⁻⁵.

**D3. Outlet projection.** ξ = Σ_{H₂,N₂,NH₃} ν_i (n_raw,i − n_in,i)/14, n_out = n_in + ν ξ (inerts exactly their inlet
flows), defect reported; refused `element_balance_defect` iff max |defect|/n_tot,in > 10⁻⁶. The outlet stream conserves
every element exactly.

**D4. Energy and thermodynamics.** The duty is process-side: Q = Ḣ_out − Ḣ_in by `pr-c1-v1` (ADR 0026). The reactor
keeps its own kinetics (with K_NH₃ per R-152), its fugacity-coefficient correlations (evaluated, as pinned, at the
sum of reactive partial pressures, finding F-R2) and its ideal-gas thermodynamics; none of its internal properties
crosses the boundary. The coolant's heat uptake and the inlet-face heat loss are reported diagnostics, never terms of
a balance.

**D5. Five species, by reference.** M01's overlay supplies Ar and CH₄ rows (records' constants; c_p in DIPPR-107 form:
Ar exactly 5/2 R, CH₄ a fit to NASA TM-4513 within 0.42 %; transport columns and binary rows copied at run time from
the pinned database's N₂ row and N₂ pairs). The adapter subclasses the pinned 1D class only to replace one hard-coded
three-species backflow constant (F-R1), proven inert (bitwise) at every registered state. The group's code and data
are never copied into this repository.

**D6. Start strategy and solver profile.** S1 cold at the trace inlet (y_NH₃ := 10⁻⁹) with the group's settings; S2
warm at the true inlet; S3 polish with Newton rtol 10⁻¹², atol 0.1 × target, steady-state target
10⁻⁶ (num_z/100)². Accepted iff S3 converged, the group's KPI-drift certificate passes, the retentate velocity is
positive on every face, every flow is positive, D2 and D3 hold. Anything else is `not_converged` with no outlet.

**D7. The design grid is num_z = 800**, the finest grid at which the profile's state is accepted; every result reports
the registered discretization estimate (spec §10). The profile is registered for num_z ≤ 800; at 1600 and 3200 the
pinned solver's state is not accepted (KPI drift above 10⁻³, element defect up to 2 × 10⁻⁴) and those grids serve only
the refinement estimate.

**D8. The M01/M02 split and the stand-in.** M01 implements the boundary module (mapping, projection, convention
checks, envelope, refusal codes) and a synthetic stand-in reactor `c1.reactor_standin` (ξ = 0.25 n_N₂,in, T_out = T_in)
that exercises every boundary path in the in-repo gate without PyMRM; M02 implements the out-of-process adapter (D5's
subclass, D6's strategy, timeouts, caching, retained failures, frozen versions, promotion) and the PR units.

**D9. The kinetics' data domain is flagged, not refused.** Inlets outside 643–733 K, 50–100 bar or H₂/N₂ ∈ [1.5, 3] but
inside the adapter's hard domain (573.15–773.15 K, 5–15 MPa, H₂/N₂ ∈ [1, 4], inerts ≤ 20 %) return `ok` with
`domain_status: extrapolated` and the violated bounds; outside the hard domain `out_of_domain`.

## Alternatives considered

- **A recycle compressor** (ADR 0022 D2's other option). Rejected for v0.2: it needs PR entropy and an isentropic
  efficiency, a unit and a reference that v0.2 does not otherwise need, to recover a 5 × 10⁻⁵ pressure loss.
- **Inverting for p_ret_out so the reactor's inlet equals P_in** (a scalar solve around every reactor call). Rejected:
  it moves the inconsistency from the inlet to the outlet, multiplies the cost, and under D2's bound changes the
  outlet by less than the discretization error.
- **Extent from N₂ (or NH₃) alone.** Rejected: it hides the defect in the other species; least squares over the three
  reactive species is symmetric and reports the full defect.
- **PR fugacities in the kinetics** (as T08's IDAES CSTR did). Rejected: it changes the group's model, whose rate
  parameters were validated with its own correlations.
- **The group's acceptance (residual 10⁻³) alone.** Rejected: 0.45 % path dependence of the outlet at num_z = 100.
- **Refusing outside the kinetics' data domain.** Rejected: the v0.2 decision variable (reactor inlet temperature) may
  have its optimum below 643 K, and the bed itself leaves the data domain at every registered state.
- **The group's publication grid num_z = 100.** Rejected as the design grid: its outlet NH₃ is ≈ 5 % above the
  refinement estimate (spec §10).
- **Lumping Ar and CH₄ into N₂ in the reactor.** Rejected: CH₄'s heat capacity is twice N₂'s at 700 K.

## Consequences

- The coupled loop sees a deterministic, element-conserving, pressure-consistent reactor map whose iteration noise is
  far below its discretization error (spec §10.3), at ~9 s per solve on one thread.
- Findings for the group (Frank): F-R1 (three-species constant), F-R2 (φ at the reactive-species pressure), F-R3 (heat
  leaves through the inlet face, 23–33 % of the reaction heat), the sub-first-order grid convergence; none is patched here.
- The dossier's §6 PR-density statement is wrong at the pin; recorded here and in the spec (§8.1, §18).

## Migration

None: no existing unit, identity or record changes.

## Acceptance evidence

M01.A25–A32 (stand-in, in the gate); M01.A41–A48 (the probe's record; M02 reproduces them through its adapter);
a `reviewer` pass on M02's adapter against spec §8.
