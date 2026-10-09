# ADR 0027 — The C1 reactor boundary: the group's 1D reactor behind a zero-pressure-drop, extent-projected, process-side-duty contract

**Status:** Proposed, 2026-10-08; amended before acceptance by Amendment 1 (2026-10-08, below), and still Proposed.
Accepted when M01's evidence manifest is `tested` (WO-6 and WO-8, the stand-in) and M02's
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
positive on every face, every flow is positive, D2 and D3 hold. A failure of D2 or D3 carries that decision's own
code. Any other failure is `not_converged`, `reactor_not_accepted(<stage>)`, with no outlet (Amendment 1, A1.2).

**D7. The design grid is num_z = 800**, the finest grid at which the profile's state is accepted; every result reports
the registered discretization estimate (spec §10). The profile is registered for num_z ≤ 800; at 1600 and 3200 the
pinned solver's state is not accepted (KPI drift above 10⁻³, element defect up to 2 × 10⁻⁴) and those grids serve only
the refinement estimate.

**D8. The M01/M02 split and the stand-in.** M01 implements the boundary module (mapping, projection, convention
checks, envelope, refusal codes) and a synthetic stand-in reactor `c1.reactor_standin` (ξ = 0.25 n_N₂,in, T_out = T_in)
that exercises every boundary path in the in-repo gate without PyMRM; M02 implements the out-of-process adapter (D5's
subclass, D6's strategy, timeouts, caching, retained failures, frozen versions, promotion) and the PR units. The
stand-in is labelled synthetic in the fields the frozen `ModelManifest` schema has, and in every `ok`
result's `identity.synthetic` (Amendment 1, A1.3).

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

M01.A25–A32, A49, A51 and A52 (stand-in and the probe record's form, in the gate); M01.A41–A48 (the probe's record;
M02 reproduces them through its adapter, spec §8.15); a `reviewer` pass on M02's adapter against spec §8.

## Amendment 1 (2026-10-08): the build lane's measurements, ruled

**Status:** Proposed with this ADR; design lane (`specifier`), M01 spec Amendment 1 (§19); register R-195, R-198,
R-199, R-200. No port, row, convention, threshold or refusal code of the draft changes.

- A1.1 (D1–D3, the check order). The boundary checks a request in a fixed order:
  1. component set, including the flow vector's length;
  2. a dormant inlet;
  3. the inlet's TP flash (a provider refusal passes through; a result other than VAPOR is
     `liquid_at_reactor_inlet`);
  4. the NH₃ trace;
  5. the hard domain;
  6. the evaluation;
  7. the pressure convention;
  8. the element defect;
  9. the two enthalpy flows;
  10. `ok`, with the data-domain flag.

  The inlet phase comes before the hard domain because no liquid exists inside the hard domain: 573.15 K lies above
  NH₃'s T_c,EOS (claim BD-06). In the other order, `liquid_at_reactor_inlet` could never be returned (spec §8.12).
- A1.2 (D6, the codes). The evaluation reports its own acceptance failures as `NotAccepted(<stage>)`, which the
  boundary returns as `not_converged`, `reactor_not_accepted(<stage>)`. `<stage>` matches `[A-Za-z0-9_]+`. The
  registered stages are `S1`, `S2`, `S3`, `certificate`, `backflow` and `nonpositive_flow`, and M02 may register more.
  A provider refusal of Ḣ_in or Ḣ_out is `error`, `stream_enthalpy_refused`, carrying the provider's message.
- A1.3 (D8, the synthetic label). The frozen `ModelManifest` schema has no `synthetic` field. The label lives in:
  - the manifest's `title`;
  - its `description`, which begins `SYNTHETIC`;
  - its first limitation, which begins `SYNTHETIC:`;
  - every `ok` result's `identity.synthetic` (`true`).

  The stand-in is not in `MODEL_BUILDERS`, so a revision naming it is refused (T08 U04). The v0.2 envelope does not
  list it at M01. If M02 binds it, the envelope lists it as synthetic only (M01.A49).
- A1.4 (verification). M01.A26's defect vector and element balances are asserted at 10⁻¹³ × n_tot,in. The relative
  10⁻¹² was below the binary64 floor of a difference of O(n_tot) flows (claims BD-04, BD-05). New assertions:
  M01.A49 (the label) and M01.A51 (the boundary paths beyond A30).
- A1.5 (D7 and the acceptance clause, the M02 hand-off). Spec §8.15 splits each of M01.A41–A48 into two halves. The
  record half is checked in the gate on `reactor-probe.json` (M01.A52; the record's bytes are already pinned through
  A34). The adapter half is re-measured by M02. A47's bitwise reproduction is stated at the evaluation, with the
  record's tube inputs (F, y), because §8.3's mapping of the recorded n is 1 ulp off them. Through the full boundary,
  the 10⁻⁶ bound of §10.3 applies. The design grid's discretization estimate is registered machine-readably for every
  result (`derived_from_measured.discretization_estimate`, claim DX-01). Q-F4's corner sweep is defined. The per-tube
  flow, which no hard-domain bound covers, is Q-F5.

## Amendment 2 (2026-10-09): the hard domain and the polish, measured (M02 R-303, R-304)

**Status:** design lane (`specifier`), M02 sixth ruling round; normative text in `docs/design/M02-pymrm-adapter.md`
§14.5 D1–D4.

M02's G11 measured the adapter on the hard domain stated in D3 (573.15–773.15 K, 5–15 MPa, H₂/N₂ ∈ [1, 4], inerts
≤ 20 %). Only the centre of the 16 corners and centre was accepted. Three mechanisms caused the failures:
- S3's stopping rule, which does not bound the element defect;
- a non-finite child result, which was typed as a crash;
- start failures at both temperature faces (S1 at 573.15 K; certificate and non-finite at 773.15 K).

Amended:
- The real variant's profile becomes `M01-S123-v2`, with one conditional polish round and the stage `nonfinite`
  (R-303). The boundary's element-defect limit (10⁻⁶) is unchanged.
- The shipped real variant `pymrm-6089593-g2-nz800-s123-v3` carries a narrower hard domain: the first of three
  registered boxes whose registered points are all accepted (R-304). The box is stated in that variant's document,
  which is the authority on its own domain. D3's numbers above remain the domain of v1 and v2.
- D10's per-tube flow bound [0.5, 2] × F_nom is unchanged; its widening clause is suspended for v3.
- D3's ordering argument (no liquid exists inside the hard domain) holds a fortiori in a narrower box.

Acceptance evidence: M02 gates G10v3, G11v3-1 to -7 and G12v3-1 (design note §14.5), recorded under
`benchmarks/m02/*-v3.json`.

## Amendment 3 (2026-10-09): M02 seventh ruling round (R-311, R-312, R-313)

**Status:** design lane, M02 seventh ruling round; normative text in `docs/design/M02-pymrm-adapter.md` §14.6 E1–E3.
The text below is §14.6 E5's proposed text, transcribed verbatim.

- D6's positivity clause applies to the species present in the inlet. An absent species (only Ar or CH₄ can be) is
  judged by D3's projection defect.
- A45's relative element defect is taken over the elements present in the inlet.
- The polish round reads δ after the KPI-drift certificate, and the certificate is repeated after the round.
- The real variant's hard domain may carry `inert_min` (absent means 0). v3's domain is the first of V1–V3
  (M02 §14.6 E3). Amendment 2's "three registered boxes" is superseded.
- Acceptance evidence: G10v3, G11v3-1 to -10, and G12v3-1.

## Amendment 4 (2026-10-09): M02 eighth ruling round (R-315, R-316); erratum to Amendment 3

**Status:** design lane (`specifier`), M02 eighth ruling round; normative text in `docs/design/M02-pymrm-adapter.md`
§14.7 F1–F3. Still Proposed.

**Erratum.** Amendment 3's fourth bullet says "v3's domain is the first of V1–V3 (M02 §14.6 E3)". That sentence is
withdrawn. Its premise, that one of V1–V3 qualifies, is refuted by measurement (M02 build log D84): in each rung a
653.15 K corner at 2 % inerts and high pressure fails the reactor's own start (S1). The rest of that bullet stands:
the real variant's hard domain may carry `inert_min` (absent means 0), and Amendment 2's "three registered boxes" is
superseded.

Amended:
- **v3's domain** is the first of M02 §14.7 F1's nested rungs V4–V6 whose registered points are all accepted in two
  full runs. All three have T_in ∈ [653.15, 693.15] K and the flow bound [0.5, 2] × F_nom.
  - V4: 9–11 MPa, H₂/N₂ 2.5–3.5, inerts 0.03–0.2.
  - V5: as V4, with inerts 0.035–0.2.
  - V6: as V5, with 9.5–10.5 MPa and H₂/N₂ 2.75–3.25.

  The selected rung's box and floor are stated in v3's variant document, which is the authority on its own domain. If
  no rung qualifies, no v3 is registered.
- **The polish round** (Amendment 3, third bullet) runs whenever the defect read after the first certificate exceeds
  10⁻⁷ (or is not a number), whatever that certificate's verdict. When the round runs and converges, the certificate
  repeated after it decides (M02 §14.7 F2). Where the first certificate passes, or the defect is ≤ 10⁻⁷, the sequence
  is unchanged.
- **Acceptance evidence:** M02 G10v3, G11v3-1 to -12, G12v3-1 and G12v3-2 (design note §14.7), recorded under
  `benchmarks/m02/*-v3.json`.

Amendment 3's other bullets stand.
