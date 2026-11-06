# Foundation rulings: the nine questions of the target architecture (roadmap stage 3)

Status: design-lane rulings (`specifier`), 2026-11-02; amended in place by Amendment 1 (2026-11-02, §13), Amendment 2
(2026-11-05, §14), Amendment 3 (2026-11-05, §15), Amendment 4 (2026-11-05, §16) and Amendment 5 (2026-11-06, §17), which list every changed clause. Brief: `docs/roadmap/brief-specifier-foundation-questions.md`.
Questions and defaults: `docs/roadmap/target-architecture.md` §6 ("the note"). Input to ADR-F2 to ADR-F5, not an ADR:
once an ADR adopts a ruling, the ADR is the authority and this document is archival input.

## 0. Authority, scope and limits

- **Scope.** The scientific semantics behind §6 Q1–Q9, as ruling clauses `Qn.Rk` an ADR can adopt verbatim, numbered
  assertions `Qn.Ak` the foundation's tests must meet, and the edits to the note (§12).
- **Consistency.** ADR 0001 D1–D5, ADR 0005 D2–D7, ADR 0007 D2.4, ADR 0011 D2, ADR 0012 and ADR 0051 D1 stay binding for
  `nTP-v1` and every v1 document. Where a ruling needs one of them amended *for v2 documents*, §10 records a finding;
  this document amends nothing. No ruling touches a v1 document, `nTP-v1`, a legacy provider or a registered fixture.
  Amendment 5's report clauses (Q1.R11, Q1.R12, Q2.R11, Q4.R10–R12) rule what a derived report (`stream-table-v1`,
  ADR 0068) states about a v1 state; they change no v1 document, fixture or identity input.
- **Departures from the note's defaults:** Q1 (enthalpy per unit mass, not molar), Q2 (anchor phase, entropy datum,
  component datum), Q3 (a conserved-group basis replaces the `apparent|true` switch), Q4 (density ordering removed), Q5
  (claim levels and witnesses), Q6 (no-redundancy rule), Q9 (two provenance axes; rights outside identity). Q7 and Q8
  confirm the default with precisions. Amendment 2 adopts the note's five W1 defaults, each with precisions (§14).

**What this document does not establish.** It chooses no correlation, parameter set, or electrolyte, solid, polymer or
petroleum model. No number in it is validation: sanity values are closed-form consequences, synthetic test constants or
in-repository record values, each labelled; literature values are marked [zotero] and are not expectations until a
record carries them. No tolerance was measured on an implementation (none exists): each states its estimated floor and
margin, the foundation measures the floor, and a failed margin amends this document or its ADR (rule 6), never the
harness. It ships no generator: assertions marked **[gen]** are claims the foundation's reference generator must check
and refuse to emit on. Type, field and code names are suggested spellings; the ADRs fix them.

Notation: ε = 2.220446e-16. "Exactly" = bitwise in IEEE double after signed-zero normalisation (ADR 0001 D1.5). A
*definition* is a connection state definition (note §2.1 item 1). C = number of components, π = number of phases.

## Q1. The general connection state and its zero-flow rule

### Ruling
- **Q1.R1** The general definition for v2 flowsheets is `(n, ĥ, P)`: `n` is one amount flow per carried amount index (a
  component, or a component × partition class, Q6) on its component's amount basis (Q7); `ĥ = Ḣ/ṁ` is the **specific
  enthalpy per unit mass**, J/kg, on the flowsheet's convention (Q2), with `ṁ = Σ_c M_c n_c` (Q7); `P` is in Pa. One `ĥ`
  and one `P` per stream, shared by its substreams.
- **Q1.R2** Rows that define or use `ĥ` are division-free: `ṁ(n)·ĥ − Ḣ(·) = 0`, never `ĥ − Ḣ/ṁ` (ADR 0001 D3.2).
- **Q1.R3** `T` is derived: the `T` of the PH state point at `(n, ĥ, P)` under the producing unit's method. Reports show
  it; it is never a connection variable.
- **Q1.R4** *Dormancy.* A stream (or substream) is dormant iff every carried amount in it is exactly `+0.0`, decided on
  the amounts, never on `ṁ` or `Ḣ`. Then `Ḣ`, `ṁ` and every extensive attribute are exactly `+0.0`; composition, `T` and
  every derived intensive are undefined (null, reason `zero_flow`); and `ĥ` is a **label**: in the unit's zero-flow form
  (the ADR 0012 D4(c)/D12 mechanism), each row that loses rank in `ĥ` is replaced by `ĥ_out − ĥ_label = 0`, where
  `ĥ_label` is the `ĥ` of the unit's first inlet in connection order, or `+0.0` for a unit with no inlet. A label is
  never a property input and never a reported result.
- **Q1.R5** `nTP-v1` stays registered and byte-identical. A v2 definition may still declare `thermal_coordinate: T`
  (R-924). In it, a state point degenerate in `T` (argument 1) is refused typed (`state_degenerate_in_definition(<S>)`),
  as ADR 0051 D1 and ADR 0012 D7 do for v1; it is never resolved silently.
- **Q1.R6** *Reactivation.* A stream flowing at an attempt opening (warm starts included) whose `ĥ` was last written by
  a label row is re-seeded before any state point is evaluated: (1) by its producer's causal evaluation where the unit
  declares one (F6), from flowing non-label inlets (a splitter copies `ĥ`, a feed takes `Ḣ(T_spec, P, n)/ṁ`, a phase
  outlet takes its phase's `ĥ` from the opening flash, seeded by Q5.R8's W_p); else (2) as `Ḣ(T_seed, P, n)/ṁ` from a TP
  flash under the producer's method, `T_seed` the outlet T its specification fixes, else the derived T of its first
  flowing non-label inlet. Passes in plan order repeat until one seeds nothing; a stream left unseeded fails the opening
  (`reactivation_seed_unavailable(<S>)`). No state point is ever evaluated with a label as an input.
- **Q1.R7** *Holdups (F7).* The differential states are the holdups of exactly the carried extensive quantities, on
  their bases: each carried amount (Q3 groups or components; Q6 partition classes, never their parent), each carried
  extensive attribute, and one energy holdup; never true species of a group basis, equilibrium-phase amounts (Q8.R4) or
  derived intensives. Fast reactions and phase equilibria add no balance term; the mass matrix stays 0/1 (note A4).
- **Q1.R8** *Holdup dormancy* (F7; Amendment 2). A material holdup (one control volume; per substream as Q8.R6) is
  dormant iff every held amount is exactly `+0.0`. Its attributes are then `+0.0`; when the whole volume is dormant its
  energy holdup is `+0.0`, every intensive of the contents is null (`holdup_empty`) and, where a row loses rank in it, a
  label in the unit's declared zero-holdup form (Q1.R4's value, Q5.R7's no-read rule), and its outlets are dormant.
  *Entering* is at t₀ (specified empty) or at an event, since integration never reaches exact zero: event function the
  held mass, decreasing; action `empty(<holdup>)` sets every held amount, attribute and the energy holdup to `+0.0` and
  books what it removes as `drain_defect(<holdup>)` in the conservation ledger (an action on an accepted state, not a
  projection; a negative held amount stays an invalid trial, ADR 0001 D2.3). While dormant every balance source is
  `+0.0`; one the zero-holdup form does not route to a Q1.R9 holdup is refused at the event
  (`dormant_holdup_source(<unit>, <term>)`). *Leaving* is at the event opening where an inflow starts: before any state
  point of the holdup is evaluated, the contents take the flowing inflows' composition and, on the energy column (û for
  U), e_seed = Σ Ḣ_in / Σ ṁ_in in fixed order (one inlet: its `ĥ` bitwise), the limit of E/m as m → 0⁺ when the energy
  row has no other source. A unit without a zero-holdup form is refused where it would become dormant
  (`holdup_dormancy_unsupported(<unit>)`); the run ends there with that status and keeps its trajectory.
- **Q1.R9** *Non-material holdups* (F7; Amendment 2). A unit may own conserved holdups no connection carries, of a
  registered kind (F1; seeded: `wall_energy`, J; `angular_momentum`, kg m² s⁻¹), each the column its `holdup_balance`
  row differentiates with coefficient 1 (U_w, not T_w; L = Iω, not ω), so M stays 0/1; its capacity (m_w c_w, I) is
  positive (`holdup_capacity_nonpositive(<unit>, <holdup>)`). A wall energy has a unit-local datum (U_w = 0 at a declared
  T_ref,w) and the scale capacity × s_T (note §2.3.7). A transfer between holdups sits with opposite signs in exactly the
  two rows it couples. They enter the conservation ledger and never go dormant with the material; a `state_rate` state
  (R-930) is not conserved and stays out of the ledger.
- **Q1.R10** *Simultaneous events* (F7; Amendment 4, SQ-F7-2). The integrator registers a location tolerance τ_loc =
  c_loc (|t| + |h|), h the step in which the root is located (reference integrator, ADR 0066 D16: c_loc = 1e-14); τ_ev =
  10 τ_loc. In an accepted step, t* is the earliest located root; the **group** is every event located in that step at
  t ≤ t* + τ_ev, applied to the state at t*. Every action value is evaluated on that pre-group state; the actions then
  apply in ascending (priority, id) order (integer priority, ids by code point). Two actions of one group writing one
  target (a discrete state, a parameter, a holdup by `empty`) with different values end the run
  `simultaneous_event_conflict(<target>, <event>, <event>)`, keeping its trajectory; equal values are one write. One
  consistent re-initialisation (ADR 0066 D6) follows the group. Then every event function is re-evaluated at (t*, x⁺):
  one that is exactly zero is masked until it is non-zero; one that crossed in its direction relative to its pre-group
  value fires as a further group at t*; an event fires at most once per t*, and a second firing ends the run
  `event_chattering(<event>)`, keeping its trajectory. Grouping is a thresholded decision: an event located at
  |t − t*| ∈ [τ_ev/10, 10 τ_ev] flags its group `near_threshold` (ADR 0007 D2.4). The groups in order, each with its
  (event id, assignments) in application order and one `reinit`, are R0.
- **Q1.R11** *A dormant stream in a report* (Amendment 5, SQ-ST-2; ADR 0068 R0; v1 states). A report derived from a
  solved state treats a stream as dormant iff `StreamState.is_dormant` (Σn == 0.0 after signed-zero normalisation, ADR
  0001 D3.1): decided on the amounts, never on ṁ or Ḣ, so a stream whose only amount is 5e-324 flows even when its mass
  underflows (Q4.R11 (c)). For a dormant stream the report makes **no provider call**. Every entry of its `n` and `m`
  (a stored −0.0 normalised) and its `n_total`, `m_total`, `H_flow`, `S_flow` and `V_flow` are exactly `+0.0`; `T`,
  `x`, `w`, every intensive and both vapour fractions are null with `zero_flow(stream)`; its phase list is empty. The
  stored T is a label (ADR 0001 D3.1; ADR 0012 D4 (c), D12) and is never shown, as Q1.R4 rules for ĥ. P is shown as
  stored: v1's zero-flow forms (ADR 0012 D4 (c), D12) drop or swap energy, equilibrium and split rows and never a
  pressure row, so a dormant stream's P is still the pressure-network value ADR 0001 D3.1 retains. This is Q1.R4's reporting half read for v1 states.
- **Q1.R12** *Evaluation state of a carried saturated split* (Amendment 5, SQ-ST-4; ADR 0068 R1; ADR 0051 D2). A report
  evaluates both phases of a carried saturated split (`<S>.sat.V` and `<S>.sat.L` in the state; one component) at
  (T_sat(P), P), **never at the stored T**. T_sat is the verifier's: the provider's `Tsat` from `evaluate_phase` on
  `StreamState((1.0,), T_lo, P)` in LIQUID, T_lo the provider's lowest declared T. Each phase is then requested on
  `StreamState((1.0,), T_sat, P)` in its family, and its extensive values are its carried amount times the per-mole
  values, so the report's Ḣ equals `verify.thermal.saturated_enthalpy` bitwise. The stream's reported `T` is the
  stored T, the coordinate the certificate judged against T_sat(P) at the temperature tolerance; no second temperature
  is reported. A `Tsat` status other than `ok` nulls every property-derived quantity of the substream and its phases
  with `property_evaluation_failed(stream, LIQUID, Tsat, status)`; amounts, masses, compositions, phase fractions and
  vapour fractions, which read no property, are still given.

### Rejected alternatives
- **(a) `nTP` plus phase amounts where Gibbs' rule leaves the state open.** Degeneracy in `T` is not only structural (π
  = C+1): it occurs at azeotropes and in a band around near-pure streams (ADR 0012 D7, D9). A trigger that follows the
  state changes the variable set, and so `model_version`, mid-solve (against ADR 0005 D2); a declared trigger is R-839's
  approach, which FB-04 refuted.
- **(c) `(n, H, P)`.** It loses `T` at zero flow and near it. At 100 mol/s throughput and |h| ≈ 3e5 J/mol, `H` rounds by
  ε·3e7 ≈ 6.7e-9 W; for a 1e-12 mol/s trace that is an error in `h = H/n` of 6.7e3 J/mol, about 89 K at c_p = 75 J/(mol
  K). Carried intensively, `h` errs by ε·3e5 ≈ 6.7e-11 J/mol.
- **Molar `h` (the default's wording).** A stream with `kg`-basis components has no molar normalisation, and summing mol
  with segment-mol mixes entities (Q7). Mass is the only measure defined on every basis and conserved by every reaction;
  in exact arithmetic an adiabatic reactor keeps `ĥ_out = ĥ_in`.
- **Carrying both `T` and `ĥ`.** Two descriptions of one state (ADR 0001 D2.5), and `T` would depend on which method
  wrote it.
- **Specific entropy as the coordinate.** Balances are written in `H`, so every PH-type unit would need an inner flash.

### Argument
1. **Non-degeneracy.** At fixed `(n, P)` the stable equilibrium lies on the concave hull of the entropy over the
   C-dimensional space of `(ĥ, composition)`. A face is a simplex of π ≤ C+1 phases with one `T` (a common tangent).
   Intersecting the face (dimension π−1) with the line of fixed composition leaves generic dimension π − C: for π ≤ C,
   `T` fixes `ĥ`; for π = C+1, `T` fixes only an *interval* of `ĥ` (a pure fluid at saturation, ice–water, a binary at
   VLLE or a eutectic, a ternary with four phases). Non-generic π ≤ C cases occur where the tie simplex is parallel to
   the `ĥ` axis (azeotropes; near-pure streams). In every case `ĥ ↦ state` is single-valued (barycentric coordinates in
   a simplex are unique), and `T(ĥ)` is continuous and non-decreasing with `dT/dĥ = 1/ĉ_p,eff ∈ [0, 1/ĉ_p,min]`, so
   Lipschitz. The inverse `ĥ(T)` is set-valued at a degenerate `T`, with unbounded slope near degeneracy and near a
   critical point. The note's "h is strictly increasing in T" is false at a degenerate `T` (§12). With several
   substreams sharing `T`, each `Ḣ_s(T)` is non-decreasing, the total is a monotone graph, and `T(ĥ)` is a function.
2. **Method boundaries.** `ĥ` is a number on the flowsheet's convention whose energy meaning does not depend on the
   method, so the overall balance closes with no boundary term and `T` jumps by `T_B(ĥ) − T_A(ĥ)`, which is reported.
   Under `nTP` the reverse holds: `T` continuous, energy discontinuous by `Ḣ_B − Ḣ_A`. Energy closure is a certificate
   check (ADR 0001 D5.3); continuity of `T` is not.
3. **Verifier.** A PH flash at `(n, ĥ, P)` is well posed at degenerate states, so ADR 0012 D7's stored-split
   substitution and ADR 0013's near-pure band have no counterpart in an `ĥ` definition.
4. **Zero flow.** An energy row has coefficient `ṁ` on `ĥ` and loses rank at dormancy, as `ṁ·ĉ_p` on `T` does today; the
   zero-flow forms carry over with `ĥ` labels, harmless only while dormant. The producer's rows are linear in `ĥ` (a
   source `ṁĥ − Ḣ(T_spec, P, n)`), but at an opening, where dormancy changes (ADR 0012 D12), consumers would evaluate
   `(n, ĥ_label, P)` first: water at `ĥ = +0.0` J/kg is ~2.4e5 J/mol above its ideal gas at T°, thousands of kelvin out
   of every domain. So Q1.R6 re-seeds, as ADR 0012 D4(c) re-seeds a split leaving `ZERO_FLOW` from `(n, T, P)`.
5. **Floors under Q2's reference.** |ĥ| reaches ~1.6e7 J/kg (liquid water): ε|ĥ| ≈ 3.5e-9 J/kg ≈ 8e-13 K at ĉ_p = 4.2e3
   J/(kg K). A 100 mol/s water stream has |Ḣ| = 2.86e7 W and a floor of 6.3e-9 W, 5 decades below ADR 0001 D6's 1.01e-3
   W at SYN-001's energy scale.
6. **Limiting cases.** Zero flow: Q1.R4. A single amount of 5e-324 flows while `ṁ` underflows to 0; the row `ṁĥ − Ḣ`
   then loses rank and K04's regularity check reports it with its typed status, never silently. A phase appearing or
   disappearing kinks `T(ĥ)` (`ĉ_p,eff` jumps), which the contract's attempt boundary handles exactly as it handles the
   kink in `h(T)` today. At the critical point `ĉ_p → ∞` and `T(ĥ)` is flat but continuous.

### Assertions
- **Q1.A1** *Pure-fluid degeneracy* (F4/F5; the IAPWS-95 method through the thermo face). n = 1 mol/s water, P = 101 325
  Pa, `ĥ = ĥ_L,sat + β(ĥ_V,sat − ĥ_L,sat)` for β ∈ {0.25, 0.5, 0.75}. Expected: `T` = the method's `T_sat(P)` within
  1e-9 K; β within 1e-10 absolute; the off-centre points differ in β by 0.5 ± 1e-10 and in `T` by ≤ 2e-9 K. Source: the
  lever rule on the same method's saturation values (tests the PH logic, not the EOS, which is S05's). Floor on β:
  ε·1.6e7/2.26e6 ≈ 1.6e-15; a PH solver converged to 1e-12 relative in `ĥ` adds ~7e-12; margin ≥ 1 decade. Catches a
  molar/mass confusion (×18), a dropped latent heat, a fallback to `T`.
- **Q1.A2** *Off-degenerate control.* Same n and P: `ĥ_V,sat + 1e5 J/kg` gives `T − T_sat > 20 K` and `ĥ_L,sat − 1e5
  J/kg` gives `T_sat − T > 20 K`, both single phase; round trip |ĥ(T(ĥ)) − ĥ| ≤ 1e-11·max(|ĥ|, 1e5 J/kg).
- **Q1.A3** *Binary three-phase degeneracy* (F5's registered VLLE system). `ĥ` at 1/3 and 2/3 of the three-phase
  interval at the same (n, P): equal `T` within 1e-9 K; vapour amounts differ by > 1e-3·n_tot; Σ_p ṁ_p ĥ_p = ṁĥ within
  1e-11 relative for each. A consistency check; validation is F5's independent comparison.
- **Q1.A4** *Monotonicity* **[gen]**. A 200-point `ĥ` sweep at fixed (n, P) that crosses at least one appearance and one
  disappearance satisfies T_{k+1} ≥ T_k − 1e-9 K for every k, contains at least two consecutive points with equal `T`
  within 1e-9 K (the π = C+1 plateau), and at least one step with ΔT > 1 K.
- **Q1.A5** *Zero flow* (F2 probe: feed → mixer ← dormant feed; dormant branch → heater → splitter). Every dormant
  stream has `Ḣ = ṁ = +0.0` exactly, derived `T` null with reason `zero_flow`, and `ĥ` bitwise equal to its Q1.R4 label
  (`+0.0` from the dormant source on); the label rows are in the zero-flow form; the flowing outlet's `ĥ` equals that of
  the same flowsheet with the dormant branch deleted within 1e-14 relative; a stream whose only amount is 5e-324 is
  classified flowing.
- **Q1.A6** *Method boundary.* One connection between two methods on `ELEMENTAL-ref-v1` that differ (for example a PR
  and an ideal-gas method): the overall energy balance closes within K04's τ_E with no boundary term, and the boundary
  report carries `T_B(ĥ) − T_A(ĥ)` as a non-R0 float, non-zero.
- **Q1.A7** *Verifier.* No check of a run on an `ĥ` definition reports `temperature_degenerate`; on a registered
  near-pure stream (a 1e-7·n trace of a second component) the verifier's independent PH split equals the solver's within
  the split tolerance, with no substitution.
- **Q1.A8** *Legacy.* F0 PASS; `StreamState ↔ EvaluationState` bitwise (as in the note).
- **Q1.A9** *Reactivation* (water, T_spec = 300 K, P = 101 325 Pa; warm starts from a dormant root). (a) Splitter
  fraction 0 → 0.3: opening `ĥ` bitwise the inlet's. (b) Feed 0 → 1 mol/s: bitwise its causal evaluation, > 1.3e7 J/kg
  from the label `+0.0` (|Δf h°(H2O, g)|/M ≈ 1.342e7 J/kg, `benchmarks/s10/records.yaml`). (c) A fixed-(T, P) flash
  opened single-phase with a two-phase root: the restart's vapour `ĥ` bitwise its opening flash's. Each: no state-point
  evaluation with a label input (instrumented count 0), no domain refusal, root `SAME` (`same_root`) as a cold start.
  Mutation control: keeping the label instead, (b) evaluates `ĥ = +0.0` J/kg (count ≥ 1), refused out of domain.
- **Q1.A10** *Holdups* (F7 probe tank). On the MEA–CO2–H2O basis (Q3.A2 (c)) the states are the three group holdups and
  one energy holdup, no species; with `probe.partition`, its classes, not the parent; with `probe.moments`, λ0 and λ2.
- **Q1.A11** *Holdup dormancy* (F7 probe: rigid vessel; synthetic ideal gas, M = 0.028 kg/mol, c_v = 2.5R/M, c_p =
  3.5R/M, R = 8.314 462 618 J/(mol K), Δf h° = 0; closed forms). (a) *Fill:* empty at t₀, inflow 0.01 kg/s at T_in =
  300 K, adiabatic: û_seed is the inlet `ĥ` bitwise and T = γT_in = 420.0 K within 1e-10 relative at every step (m and
  U grow linearly, which BDF integrates to roundoff, floor ≈ n_steps·ε ≤ 1e-12; seeding T_in into the state, or dropping
  Pv, errs by 40 %). (b) *Drain:* 1 kg at T₀ = 300 K, outflow 0.01 kg/s, duty ṁR_sT₀ = 890.835 280 5 W holding T = T₀:
  the event falls at t_d = 100 s within 1e-9 relative; |drain_defect| ≤ 1e-8 kg (floor ≈ ε·1 kg; an unlocated event
  clamps a step, ≥ 1e-4 kg), and the ledger closes with it; the duty left on is refused `dormant_holdup_source`; switched
  off by the action, every held amount and U stay exactly `+0.0`, T null, the outlet dormant. (c) *Refill* at 150 s
  reproduces (a). No state point reads a label (instrumented count 0). Mutation control: without the event the step
  below m = 0 is an invalid trial and the run cannot pass t_d.
- **Q1.A12** *Non-material holdups* (F7 probe: (b)'s vessel with a wall, C_w = 5e4 J/K, 100 W/K to the contents, fire
  duty 1e4 W into the wall; a rotor, I = 2 kg m², net torque 10 N m). M's entries are exactly 1.0 on the declared map, U_w
  and L included; the wall–contents term sits in exactly two rows with opposite signs and is exactly `+0.0` while the
  contents are dormant, T_w then rising at 0.2 K/s within 1e-10 relative; L = L₀ + 10t N m s within 1e-12 relative; the
  ledger lists U_w and L, not a probe PI integral; at ẋ = 0 the wall unit's dynamic residual equals its steady residual
  bitwise. Mutation control: T_w differentiated with coefficient C_w is refused (a non-unit M entry).
- **Q1.A13** *Simultaneous events* (F7, reference integrator; Amendment 4). Probe: one differential state x, ẋ = 1,
  x(0) = 0, fixed h = 0.125 s (t_k = x_k = k/8, exact in binary); event a: g = t − 0.95, rising, assigns d_a := 1;
  event b: g = x − (0.95 + δ), rising, assigns d_b := 1; at t* = 0.95, τ_loc = 1e-14 · 1.075 = 1.075e-14 s and τ_ev =
  1.075e-13 s. (a) δ = 0, equal priorities: one group at t* (|t* − 0.95| ≤ τ_loc), sequence (a, b), one `reinit`; the
  scenario with its event list reversed gives the identical R0 sequence. (b) δ = 0, priority 0 for b and 1 for a:
  (b, a). (c) δ = 5e-15 s: one group, not flagged. (d) δ = 5e-14 s: one group, `near_threshold`. (e) δ = 5e-13 s: two
  groups, two `reinit`, `near_threshold`. (f) δ = 1e-6 s: two groups, not flagged. (g) δ = 0 with b assigning
  d_a := 2: `simultaneous_event_conflict(d_a, a, b)` at t*; with d_a := 1 it is one write. (h) a's action also sets a
  parameter p := 1, and event c (g = p − 0.5, rising) fires in a second group at t*; if c sets p := 0 and event c′
  (g = 0.5 − p, rising) sets p := 1, c's second firing ends the run `event_chattering(c)`. Expectations are orders,
  counts, exact assignments and the located t*. Mutation controls: ordering by id alone fails (b); a `reinit` per event
  fails (a); τ_ev = 0 fails (c).
- **Q1.A14** *Dormant stream in the report* (ST G4; Amendment 5). Every test-local state of Amendment 5 is paired with a
  certificate whose `target_state_sha256` matches, as G3's must be (note §4.1's precondition). (a) On every dormant stream of the ST
  corpus: `T` null with absent `{code: zero_flow, params: {stream: <S>}}`; `P` bitwise the stored value; every entry of
  `n` and `m` and `n_total`, `m_total`, `H_flow`, `S_flow`, `V_flow` equal to 0.0 with a clear sign bit; `x`, `w`, both
  vapour fractions and every intensive null with `zero_flow`; `phases == []`; `flash_near_phase_boundary` false.
  [pre] The corpus has at least one dormant stream (O-21). (b) Two probes on the first undeclared stream S of a SYN-001
  corpus revision, n := (+0.0, −0.0, +0.0) at its stored P: (b1) T := 1234.5 K, outside syn001's [280, 440] K; (b2)
  T := 300.0 K, inside it. Each meets (a); the only code on S is `zero_flow`; a counting provider wrapper records no
  call whose state is dormant. Exact (assignments, not arithmetic). Mutation controls: showing the stored T puts 1234.5
  or 300.0 in `T`; evaluating at the label draws `out_of_domain` at (b1) and yields numbers at (b2), which only the null
  `T` and the call count catch; deciding dormancy on ṁ fails Q4.A14 (d).
- **Q1.A15** *Saturated split at T_sat(P)* (ST G3, G7; Amendment 5). (a) G3's state keeps S4's stored T [pre: |T −
  450 K| > 100 K]; G3's six values within 1e-7 relative of the S05 reference then exclude an evaluation at the stored
  T, which would move h′ alone by about c_p ΔT ≈ 4.2 kJ/(kg K) × 131 K ≈ 0.55 MJ/kg (an estimate, not an
  expectation). (b) S4's reported `T` is bitwise the stored T. (c) On every R1 stream of the corpus a recording provider
  wrapper shows one `Tsat` call on `StreamState((1.0,), T_lo, P)` in LIQUID, then every phase request on
  `StreamState((1.0,), T_sat, P)` with T_sat bitwise the returned value; `H_flow` is bitwise
  `thermal.saturated_enthalpy` (E7). (d) G3's state with P := 2.5e7 Pa, above IAPWS-95's P_c = 22.064 MPa [pre: `Tsat`
  refused, O-21]: `h`, `h_mass`, `s`, `s_mass`, `v`, `rho`, `H_flow`, `S_flow`, `V_flow` of the substream and both
  phases null with `property_evaluation_failed(stream: S4, phase: LIQUID, property: Tsat, status: <the provider's>)`;
  both vapour fractions and both phase fractions exactly 0.5 (0.5/1.0, and M·0.5 is exact); `n`, `m`, `x`, `w`, `T`
  given. Mutation control: nulling the fractions with the properties fails (d).

**Effect on the note.** §2.1.1: `thermal_coordinate: T | h` becomes `T | h_mass`; add Q1.R4. §2.2.1: each state-point
specification carries its quantity kind (molar or specific). §6 Q1: text corrected. §7 R4: decided, mitigated by Q1.R3.
Exits: F2 gains Q1.A5; F4 and F5 gain Q1.A1–A4, A6, A7. Amendment 1: §13 S3, N10. Amendment 2: §14 (F7 gains Q1.A11,
A12).

## Q2. Enthalpy and entropy reference

### Ruling
- **Q2.R1** *One convention per v2 flowsheet;* the default, and for now the only one a method can be shifted to, is
  `ELEMENTAL-ref-v1`: elements in their standard reference phases at T° = 298.15 K, P° = 1e5 Pa have h = 0; each
  component in its anchor phase at (T°, P°) has h = Δf h°_c and s = s°_c (third-law absolute), both per unit of its
  amount basis. Hence `g = h − Ts`, and Σν g at (T°, P°) is Δr g°.
- **Q2.R2** *Anchor phase,* one per component, a function of its record alone (Amendment 2): a record field and part of
  its identity (Q9.R2), stated by the record (in a phase where it gives formation data, if it gives any) or set at
  import by this order. A charged component takes `aq` (infinite dilution, molality scale, conventional Δf h°(H⁺, aq) =
  s°(H⁺, aq) = 0); any other the first of `ig` (ideal gas), `aq`, `l`, `s:<form>` (forms in record order) in which the
  record gives formation data, else (Q2.R4) any property correlation, else Q2.R9's default (Amendment 3); `kg`-basis
  components included. No method enters it, so adding or removing a method never re-anchors. Every method evaluating
  the component evaluates it in that phase at (T°, P°) (for `ig`, its ideal-gas state, Q2.R9 (b)); one that cannot is
  bridged (Q2.R8), and without a bridge datum it is refused for it (`anchor_unavailable(<method>, <component>,
  <phase>)`).
- **Q2.R3** *Shift.* For method m and component c, Δ_{m,c} = Δf h°_c − h^m_c(anchor; T°, P°), h^m_c being the method's
  native pure-component (for `aq`, infinite-dilution) value. Ḣ_shifted = Ḣ_native + Σ_c n_c Δ_{m,c}; S likewise with
  s°_c. The shifts are constants of the composed method, computed once at composition and recorded in its `describe()`;
  derivatives in T and P are unchanged; ∂/∂n_c gains Δ_{m,c}.
- **Q2.R4** *Component datum.* A component whose record has no formation data in any phase takes h = 0 (s = s° if
  given, else 0) in its anchor phase at (T°, P°): consistent across methods and admitted across method boundaries,
  refused in any reaction where its coefficient is non-zero (`component_not_reaction_consistent(<component>)`), admitted
  as an inert in a reactor (its datum cancels).
- **Q2.R5** A method that cannot evaluate its own anchor-state value keeps its native convention and is admitted only in
  a flowsheet whose convention is that native one, where ADR 0001 D5.2 rules (the default's "used alone", narrowed to
  where it is needed).
- **Q2.R6** The energy report states the overall balance on the flowsheet convention; per-method subtotals are
  attribution only.
- **Q2.R7** v1 is unchanged. A legacy datum coinciding numerically with the elemental one (`PR-C1-ref-v1` for h) does
  not license mixing in v1.
- **Q2.R8** *Anchor bridge* (R-924). A method m that can evaluate c only in a phase φ other than its anchor a is
  admitted when a record entry (any origin, Q9.R4) gives Δ_aφ h°_c and Δ_aφ s°_c at (T°, P°) (a = `ig`, φ = `l`: −Δvap
  h°, −Δvap s°): Δ_{m,c} = Δf h°_c + Δ_aφ h°_c − h^m_c(φ; T°, P°), s likewise, else as Q2.R3. It carries
  `anchor_bridged(<method>, <component>, <a>-><φ>)` in `describe()` and the validation class, with the datum's
  provenance, and where another method evaluates c in both phases, δ = Δ_aφ h°_c − (h^{m′}_c(φ) − h^{m′}_c(a))(T°, P°).
  Energy still closes at boundaries (Q1 argument 2); δ appears in the reported T jump. A record with formation data in
  both a and φ gives the datum as Δ_aφ h°_c = Δf h°_c(φ) − Δf h°_c(a) (s likewise), with both entries as provenance.
- **Q2.R9** *Default anchor* (Amendment 3, §15). (a) A record that states no anchor, has charge 0, gives no formation
  data and tags no entry with a phase takes `ig` when its amount basis is `mol`, with the notice
  `anchor_defaulted(<component>)` at normalisation. On `segment_mol` or `kg` it takes none (`null`,
  `anchor_undetermined(<component>)`), and the component is refused on `ELEMENTAL-ref-v1` with that code until its
  record states an anchor. The default is the record's field like any other anchor: part of its identity, a function of
  its charge, basis, formation entries and phase tags alone, and the same record as one stating `ig` (the notice is not
  identity). Q2.R4's datum then sits in the ideal-gas state: h = 0 at T°, s = 0 at (T°, P°). (b) A method evaluates an
  `ig` anchor, defaulted or not, as its own ideal-gas state at (T°, P°), never as its vapour root at P° unless its vapour
  model is an ideal gas. For a Helmholtz-form method, φ = φ° + φʳ, that is φ° alone: h_ig = R T° (1 + τ φ°_τ), s_ig =
  R (τ φ°_τ − φ°(τ, δ°)), with τ = T_red/T°, δ° = P°/(R T° ρ_red) and the method's own R, T_red and molar ρ_red. (c) The
  anchor evaluation passes the method's guard and declared domain like any other evaluation. A refusal there refuses
  the method for the component, `anchor_unavailable(<method>, <component>, ig)` with the method's own reason code as its
  cause, and the method keeps its native convention for it (Q2.R5).
- **Q2.R10** *Entropy datum* (Amendment 4; ADR 0063 risk 5). (a) For a method m providing `s`, Δˢ_{m,c} = s°_c(a) −
  s^m_c(a; T°, P°) (Q2.R3; bridged by Q2.R8's Δ_aφ s°_c where m cannot evaluate the anchor phase a). s°_c(a) is the
  record's third-law entropy in a; else, when the record gives s° in a phase φ ≠ a and a transition datum Δ_aφ s°_c,
  s°_c(φ) − Δ_aφ s°_c; else the **entropy datum** s°_c(a) := 0, with the notice `entropy_datum(<c>)` in `describe()` and
  on every report of an absolute s, ŝ, Ṡ or g of a phase holding c. A Q2.R4 component without s° carries the same
  notice. A method without `s` (PR-C1) gets no S shift and provides no `s`, `s_ig` or `g`; a unit requiring them is
  refused by ADR 0060 D5 (`capability_missing(<unit>, <method>, vocab:s:1)`). A method bridged for c whose record lacks
  Δ_aφ s°_c gets no S shift for c, and its `s` and `g` of a phase holding c are refused `anchor_unavailable(<method>,
  <c>, <a>)` with cause `entropy_bridge_missing`. (b) *Admitted* (datum-free, §16 argument 1): every use in which the
  amount of c is conserved: state points and specifications at fixed amounts (PS, TS, the isentropic reference of ADR
  0065 D16), the entropy balance or entropy generation of a non-reacting unit, and phase equilibrium within one method
  or between methods anchored in a. A specified absolute s is admitted and reported with the notice. (c) *Refused:*
  every quantity in which the amount of c changes while c carries the datum (Δr s, Δr g, an equilibrium constant or
  affinity from g, a Gibbs-energy minimisation in which n_c is free, the entropy generation of a reacting unit) where
  c's coefficient is non-zero: `component_not_reaction_consistent(<c>)` at the declaration. A verifier check that would
  compute such a quantity reports `unsupported` with that code, never `pass` or `fail`. c as an inert in a reactor is
  admitted. A component with Δf h° and no s° is reaction-consistent in h (a conversion reactor's energy balance is
  admitted) and not in s or g.
- **Q2.R11** *Mixture properties in a report* (Amendment 5, SQ-ST-5; ADR 0068 D4, D5). (a) A phase's h is the
  provider's mixture `h`, H_p = n_p,tot·h, or, only when that key is absent and every `h_<c>` is present, H_p =
  Σ_c n_p,c h_c from 0.0 in provider order. The per-component form is admitted for h because the one legacy provider
  returning it, SYN-001, defines its phase enthalpy as that sum (an ideal solution, H^E ≡ 0), the arithmetic of its
  units and of the verifier. (b) s and v come only from the mixture keys `s` and `v`, each requested alone and only when
  declared; a per-component `s_<c>` or `v_<c>` gives `property_not_provided(provider, property)`. Such a key does not
  say whether it holds a pure-component or a partial molar value, and for pure-component values the sum omits the
  entropy of mixing −R Σ_c x_c ln x_c (R ln 3 = 9.134 370 806 J/(mol K) for an equimolar ternary) or the excess
  volume. (c) A density is m/V with V = n·v from the provider's v and from nothing else: **no ideal-gas fallback**, even
  where the method's vapour model is an ideal gas (SYN-001, the Wilson γ–φ vapour). The gap is
  `property_not_provided(provider, v)` with capability `property:v`; the provider closes it by declaring `v` (F4), never
  the report. (d) The report holds no thermodynamic model of its own: every value it shows is a provider value, a
  carried state value, or one of the note's §4.3 combinations of them with amounts and molar masses.

### Rejected alternatives
- **Native conventions with per-method summaries only (the default's fallback).** Energy does not close across a
  boundary; a reaction across methods cannot be written.
- **One common component datum for all components.** Σν h is then not Δr h, and every reaction fails; kept only for
  non-reacting use (Q2.R4).
- **An ideal-gas anchor for everything.** Ions and solid-only components have none.
- **Each method choosing its own anchor.** Two methods anchoring water in different phases disagree at T° by the
  difference between the record's Δvap h° (CODATA ≈ 44.0 kJ/mol [zotero]) and the method's own `h_L − h_ig`, typically
  10–50 J/mol, silently. Q2.R8 keeps one anchor and one recorded datum, reports δ, and replaces this ruling's former
  refusal of such methods, which a declaration can contain (R-924).
- **h now, s at X13.** X13 would reopen the convention (R-927's first failure mode).
- **P° = 101 325 Pa.** The repository's formation data (NASA, M01) use 1e5 Pa; P° affects s and g only.
- **`null` for a record with nothing (ADR 0061's build default; Amendment 3).** It is faithful, but it refuses every
  IAPWS-95 and CoolProp record on `ELEMENTAL-ref-v1` although both methods evaluate their ideal-gas state from φ° (§15).
  With one convention per flowsheet, no such stream can then share a flowsheet with a PR-C1 or Wilson stream. Its
  refusal is no louder than `anchor_unavailable`, which `ig` still gives where a method cannot evaluate the state.
- **A phase chosen per legacy profile by the importer** (`l` for water, each fluid's phase at (T°, P°)). The phase at
  (T°, P°) is a model output, so the anchor would depend on a method (A1-b).
- **The vapour root at P° as the `ig` state.** It is the real gas, off by the departure. For water at (T°, P°) it is
  refused (`phase_not_stable`, P° ≈ 31.5 P_sat), and wherever the fluid is liquid at (T°, P°) it does not exist.
- **`ig` on every basis.** A `kg` material (coal, biomass) or a `segment_mol` polymer has no ideal-gas state.

### Argument
The shift is a constant per component, so residual and Jacobian still describe one function, and exact caches key on the
composed provider's identity (data lock plus method), which fixes the shifts. Excess and departure terms are datum-free,
so per-component constants suffice for mixtures. Σν h_shifted(T°, anchor) = Σν Δf h° by construction, and at other T
Kirchhoff's law holds through the method's own c_p; ADR 0011 D2's total-enthalpy form then covers reactions on every
basis (Δf h° per mol, per segment-mol, or per kg from the record's heating value and ultimate analysis). Every stream
and phase is electroneutral (Σ z_c n_c = 0), so any term proportional to z in ion data cancels in Ḣ and S: the H⁺
convention is invisible to balances. *Limiting cases:* an element in its ideal-gas reference phase (H2, N2, Ar) has
h_shifted(T°) = 0 to roundoff; an element whose reference phase is not its gas (C graphite, Br2 liquid) has non-zero
ideal-gas Δf h° [zotero: Br2(g) ≈ +30.9 kJ/mol], so an implementation setting h_ig(T°) = 0 for every element fails
Q2.A3; a thermoneutral reaction (SYN-001's liquids, ADR 0011 D2) forbids any tolerance relative to Σν h; `h_V − h_L` at
T_sat survives the shift within 2 ulp of the shifted magnitude; at dormancy `+0.0 × Δ` is ±0.0 and the normalised sum is
`+0.0`; the critical region, a binary at VLLE and a phase appearing are unaffected, the shift being a constant per
component. *Floor:* a duty Ḣ_out − Ḣ_in carries ε·max|Ḣ|, 6.3e-9 W at 100 mol/s of water (Q1 argument 5).

### Assertions
- **Q2.A1** *Shift identity* (every registered state of F4's re-composition set, two-phase and phase-boundary states
  included). Ḣ_shifted − Ḣ_native = Σ n_c Δ_{m,c} within 4 ulp of max(|Ḣ_shifted|, |Ḣ_native|); ∂Ḣ/∂T and ∂Ḣ/∂P bitwise
  equal; ∂Ḣ/∂n_c differs by Δ_{m,c} within 2 ulp. Floor: two roundings per term. Catches a shift leaking into the T or P
  derivatives.
- **Q2.A2** *Anchor identity* **[gen]**. For every registered reaction r and method m in its flowsheet, |Σ ν_rc
  h^m_shifted,c(T°, P°) − Σ ν_rc Δf h°_c| ≤ 1e-12·S_r, S_r = Σ |ν_rc|·max(|Δf h°_c|, |h^m_c(anchor)|, 1 J/mol). Floor ≈
  4ε·S_r (≤ 10 terms), margin ≥ 2.5 decades; catches a wrong T° (0.15 K × 30 J/(mol K) = 4.5 J/mol), a wrong anchor (≥
  10 J/mol), a missing shift. Registered cases: (i) N2 + 3 H2 → 2 NH3 on the composed PR-C1 method, expected −91 116.0
  J/mol from `benchmarks/m01/components.yaml` (NH3 −45 558.0, H2 and N2 0.0); (ii) H2 + ½ O2 → H2O(g) across two
  methods, H2 from M01, H2O from `benchmarks/s10/records.yaml` (−241 824.621 625 364 96 J/mol), O2 an element (0 by the
  convention), expected −241 824.621 625 364 96 J/mol; (iii) a synthetic thermoneutral A → B, both Δf h° = 0 in anchor
  `l`, where only the absolute bound is meaningful.
- **Q2.A3** *Elements.* |h_shifted(T°)| ≤ 2 ulp(|h^m(T°)|) for H2, N2, Ar (ideal gas); non-vanishing control: every
  non-element in the registered set has |h_shifted(T°)| ≥ 1 kJ/mol.
- **Q2.A4** *Electroneutral invariance* (with Q3). Adding λ·z_c (λ = 1e4 J/mol) to every ion's Δf h° leaves Ḣ of every
  registered electroneutral stream unchanged within 4ε·Σ_c |n_c|(|h_c| + |λ z_c|), and changes each ion's partial molar
  h by λ·z_c within 2 ulp.
- **Q2.A5** *Component datum.* A pseudo-component without formation data has h = 0 at (T°, P°, anchor) within 2 ulp in
  each of two methods; a reacting unit giving it non-zero ν is refused with the typed code; as an inert, or across a
  non-reacting boundary, it is admitted.
- **Q2.A6** *Entropy.* Σν s_shifted(T°, P°) = Σν s°_c within 1e-12·Σ|ν_c|·max(|s°_c|, 1 J/(mol K)).
- **Q2.A7** *Zero flow.* Ḣ_shifted of a dormant stream is exactly `+0.0`.
- **Q2.A8** *Bridge* (synthetic liquid-only water method, h^m_L = c(T − T°), s^m_L = c ln(T/T°), c = 75.3 J/(mol K);
  anchor `ig`; synthetic Δvap h° = 44 000.0 J/mol, Δvap s° = 118.0 J/(mol K)). h_shifted(l; T°) = −285 824.621 625 364 96
  J/mol (Q2.A2 (ii) minus 44 000.0) and s_shifted(l; T°) = s°_ig − 118.0 within 2 ulp; `anchor_bridged` recorded; no
  datum → `anchor_unavailable`; no bridge for an `ig`-capable method; δ beside a two-phase method within 1e-9 relative.
- **Q2.A9** *Anchor stability* (F4; Amendment 2). (a) Synthetic X with formation data only in `l` (Δf h° = −1.0e5
  J/mol, s° = 150.0 J/(mol K)), a liquid-only method m1 (h = 150.0 (T − T°) J/mol) and m2, a synthetic γ–φ method with
  an ideal-gas vapour and its own liquid: anchor `l` and Δ_{m1,X} = −1.0e5 J/mol exactly under {m1}, {m1, m2} and {m2,
  m1}; a converged {m1} flowsheet keeps every stored `ĥ` bitwise when m2 joins on a disjoint unit; a pure ideal-gas
  method is refused `anchor_unavailable(<method>, X, l)`. Mutation control: the former method-set clause re-anchors X to
  `ig` and refuses m1. (b) Water: the S10 gas record plus a synthetic Δf h°(l) = −285 824.621 625 364 96 J/mol: anchor
  `ig` under every method set; a liquid-only method is bridged by the difference (`anchor_bridged`, both entries named)
  and h_shifted(l; T°) equals that Δf h°(l) within 2 ulp (difference and sum exact by Sterbenz; Q2.R3 rounds twice).
  (c) **[gen]** Each registered record's stored anchor equals the order's; the anchor map is identical over every subset
  and order of the registered methods.
- **Q2.A10** *Default anchor, records* (F3; Amendment 3). Exact; no tolerance. (a) **[gen]** *Legacy.* The importer
  writes `anchor_phase: ig` for the 127 records of `syn001` (A, B, C), `s05` (H2O) and `s07` (123 fluids), each with
  index `findings` exactly `[anchor_defaulted(<id>)]`; the 20 records of `m01`, `l01`, `s10` and `s10-verification` take
  `ig` from their formation entries (ADR 0061 D6 step 2) without the notice; no legacy record has a null anchor or
  `anchor_undetermined`. Mutation control: the superseded step 4 leaves the 127 at `null`, with other SHAs. (b)
  **[gen]** *Order.* R0 is a synthetic record: charge 0, `mol`, molar mass 0.1 kg/mol, no formation, no phase-tagged
  entry, no anchor. R0 → `ig` and `anchor_defaulted`. R0 stating `ig` → no notice and the SHA of normalised R0;
  normalised R0 normalised again → the same bytes, no notice. R0 stating `l` → `l`, no notice. R0 plus one entry tagged
  `l` → `l` (step 3), no notice. R0 with charge +1 → `aq`, no notice. R0 on `kg` without molar mass → D6 gives `null`
  and `anchor_undetermined`, and registration is refused `amount_basis_unsupported(kg)` until ADR-F2 admits the basis
  (both asserted). Each case differs from R0 in one field, and each catches one wrong order: the notice entering
  identity, the default overriding a statement, preceding step 3, preceding step 1, or ignoring the basis.
- **Q2.A11** *Default anchor, methods* (F4; Amendment 3). Expectations **[gen]**: 50-digit closed forms on
  `docs/derivations/scripts/s05_reference.py`'s coefficients, φ°_τ analytic, the liquid by its density root, T° the
  double nearest 298.15; the digits below are a scratch evaluation of those forms (§15). The generator also claims, and
  refuses to emit otherwise, that ln(P°/P_sat(T°)) > ε_σ and that each smallest error and each mutation listed in (a)
  moves the value it acts on by more than 1e3 times that value's bound. (a) *IAPWS-95*
  (`iapws95-v1` composed on `ELEMENTAL-ref-v1` with the `s05` H2O record). Admitted. The anchor evaluation gives
  h^m(ig; T°) = 45 902.570 301 197 764 9 J/mol and s^m(ig; T°, P°) = 125.529 406 457 013 861 3 J/(mol K), each within
  1e-12 relative; the recorded shifts are their negations, exactly (Q2.R4: Δf h° and s are 0); h_shifted(ig; T°) and
  s_shifted(ig; T°, P°) are 0 within 2 ulp (1.5e-11 J/mol, 2.8e-14 J/(mol K)). Non-vanishing controls, the LIQUID at
  (T°, P°): h_shifted = −44 012.428 328 641 234 5 J/mol and s_shifted = −118.914 200 335 262 723 1 J/(mol K), within
  1e-10 relative. *Floor*, measured on the legacy kernel (x86_64): 5.7e-17, 2.4e-16, 5.6e-16 and 2.7e-16 relative, so
  the bounds sit ≥ 3.6 and ≥ 5.2 decades above it. *Smallest error worth catching:* T° off by 0.01 K, 7.3e-6 relative in
  h (c_p,ig(T°) = 33.587 J/(mol K)); CODATA's R for the formulation's, 1.1e-5; P° = 101 325 Pa, 0.109 J/(mol K) in s.
  *Mutation controls:* the VAPOR root at P° is refused `phase_not_stable` (measured), so the composition is refused, not
  admitted; φ° at δ = 1 moves s by R ln(1/δ°) = 50.67 J/(mol K); the real fluid at the ideal-gas density lies inside
  the spinodal (the kernel's Z = −5.99 there); anchoring water on `l` makes the LIQUID control 0. (b) *CoolProp*
  (`coolprop-heos-v1` with the `s07` records, the coolprop extra installed). **[gen]** Of the 123 fluids, the 118 whose
  declared box contains (T°, P°) are admitted; the 5 whose box does not — CycloHexane (T_lo = 329.4 K), D4 (304.8 K),
  MethylPalmitate (317.9 K), MethylStearate (327.5 K), p-Xylene (300.8 K) — are refused
  `anchor_unavailable(coolprop-heos-v1, <id>, ig)` with cause `out_of_domain`, and each is admitted on
  `COOLPROP-DEF-ref-v1` (Q2.R5).
  H2O: h^m(ig; T°) and s^m(ig; T°, P°) equal (a)'s values within 1e-10 relative, and its LIQUID control (a)'s within
  1e-9 relative, an expectation from another code path (CoolProp's Water α° is IAPWS-95's φ°, S05 agreement 9.0e-16 for
  φ° and 1.3e-16 for φ°_τ; the table's R = 8.314 371 357 587 J/(mol K) differs from R_s·M by 4.8e-14 relative, which the
  bound clears by 3.3 decades). Every admitted fluid: h_shifted(ig; T°) = 0 within 2 ulp, and for each phase the method
  answers at (T°, P°), |h_shifted| > 2 ulp(h^m(ig; T°)) (an anchor taken from the answered phase gives exactly 0
  there; O-12). Without the extra every `s07` composition is refused with cause `coolprop_unavailable`, and (b) is
  reported `unsupported` with that cause, never passed. (c) *Reactions.* H2 + ½ O2 → H2O(g), H2O on `iapws95-v1` with
  the `s05` record: refused `component_not_reaction_consistent(H2O)`. Contrast: with H2O on its `s10` record (formation
  data) the same reaction is Q2.A2 (ii), admitted. (d) *No default.* Once ADR-F2 admits `kg`, a `kg` record with
  nothing is refused on `ELEMENTAL-ref-v1` with `anchor_undetermined(<component>)` and admitted on a native
  convention; until then (d) is reported `unsupported` with cause `amount_basis_unsupported(kg)`.
- **Q2.A12** *Entropy datum* (Amendment 4; F4: (a), (d), (e); F6: (b), (c)). The sheet method of
  `docs/derivations/F6-std-seed.md` §2 (SYN-001's potentials composed on `ELEMENTAL-ref-v1`) with records A, B, C given
  a synthetic Δf h°(ig) = (−1.0e5, −1.2e5, −1.4e5) J/mol and either (i) no s° or (ii) s°(ig) = (200, 250, 300)
  J/(mol K). (a) Both compose; (i) carries `entropy_datum(A)`, `(B)`, `(C)`, (ii) none; Δˢ_c(ii) − Δˢ_c(i) = s°_c within
  2 ulp. (b) The sheet's case CMP-1 (compressor, (1, 1, 1) mol/s, 380 K, 6e4 → 1.5e5 Pa, η = 0.8) is admitted on both
  and gives T_out = 417.601 866 113 419 K within 1e-10 relative and W = 11 280.559 834 025 72 W within 1e-9 relative on
  each, (i) and (ii) agreeing to the same bounds. (c) The outlet's reported Ṡ differs, (ii) − (i), by Σ_c n_c s°_c =
  750 W/K within 1e-10 relative. (d) A reaction ν = (−2, −1, 3) declared with an equilibrium constant from g is refused
  `component_not_reaction_consistent(A)` on (i) and admitted on (ii); declared with a conversion and an energy balance
  only (it reads h), it is admitted on both. (e) The TP flash of the equimolar feed at 350 K, P_r (sheet case HTR-T,
  β = 0.101 368 723 426 727 76) gives phase amounts that agree between (i) and (ii) within 1e-12 relative. Floors: the
  datum adds ε·|Σ_c n_c Δˢ_c| ≈ 2e-13 W/K to each Ṡ, ≈ 3e-13 K in T_s; a PS solve converged to 1e-12 relative in Ṡ
  (|Ṡ| ≤ 900 W/K) moves T_s by ≤ 1.2e-9 K, so T_out by ≤ 4e-12 relative and W by ≤ 4e-11 relative; margins ≥ 25.
  Expectations: `docs/derivations/scripts/f6_std_seed_reference.json` (case CMP-1). Mutation controls: the datum on one
  side only (inlet Ṡ shifted, PS point native) moves T_s by hundreds of K; refusing (b) on (i), as the default's "or
  equilibrium" reads, fails (b); dropping the notice fails (a).
- **Q2.A13** *Property forms in the report* (ST G5; Amendment 5). (a) On every SYN-001 substream with phases in the
  corpus: the h-derived members are given, H_p bitwise Σ_c n_p,c h_c from 0.0; `s`, `s_mass`, `S_flow` null with
  `property_not_provided(provider: syn001, property: s)`; `v`, `V_flow`, `rho` null with
  `property_not_provided(syn001, v)` (`rho` copies its first absent input). (b) A test double D_c delegating to SYN-001,
  declaring `s` and `v` and returning only `s_<c>` = (100, 200, 300) J/(mol K) and `v_<c>` = 1e-3 m³/mol, at Q4.A15's
  B-far state: `s`, `v` and every quantity derived from them null with `property_not_provided(<D_c's id>, s | v)`; h
  bitwise as in (a). Mutation control: a per-component sum gives s ≥ 100 J/(mol K), a number. (c) The same double
  returning the mixture keys `s` = 150 J/(mol K) and `v` = 2e-3 m³/mol instead: S_p = n_p,tot·150, V_p =
  n_p,tot·2e-3, rho_p = m_p,tot/V_p and rho = m_tot/V_flow, each bitwise as the test recomputes it. (d) On the
  wilson-ig-v2 corpus revision, a listed VAPOR phase [pre, O-21] has `s` given and `rho` null with
  `property_not_provided(wilson-ig-v2, v)`. Mutation control: an ideal-gas fallback gives PM/(RT), a number. (e)
  IAPWS-95 gives ρ (G3). Exact: null patterns and bitwise recomputation.

**Effect on the note.** §2.3.6: `ELEMENTAL-ref-v1` with anchor phase, entropy datum and component datum. F4 exit: the
convention-shift clause becomes Q2.A2. §6 Q2: default replaced. §2.3 "ADRs": ADR-F4 also amends ADR 0001 D5.2 (§10).
Amendment 2: §14 (A1-b; F4 gains Q2.A9). Amendment 3: §15 (Q2.R9; F3 gains Q2.A10, F4 gains Q2.A11).

## Q3. Electrolyte species basis on connections

### Ruling
- **Q3.R1** *Conserved basis.* Connections carry amounts `b` over declared **groups** g, with a constant content matrix
  A (A_gs = units of g in true species s), relative to the method's declared fast-reaction (speciation) set R and the
  species charges z. A definition is valid against a method iff, in exact integer arithmetic, (i) **A R = 0** (every
  fast reaction conserves every group) and (ii) **ker A ∩ ker zᵀ = span R** (on electroneutral compositions `b` fixes
  the reaction invariants, so `(b, ĥ, P)` fixes the speciated state). (iii) **A ≥ 0** makes `b = A n_s ≥ 0` for every
  n_s ≥ 0; a declaration admitting no non-negative A is admitted with the recorded limitation
  `species_basis_not_monotone` (R-924), and under it a state whose groups would be negative is an invalid trial state
  (`group_amount_negative(<S>, <g>)`), never clipped.
- **Q3.R2** Presets: *apparent* = neutral groups (NaCl, H2O; MEA, CO2, H2O), each ion assigned to one group; *true* = R
  = ∅, A = I (frozen speciation). Both are admitted from F2 on.
- **Q3.R3** Under the apparent preset, true species are state-point outputs, not connection variables; a unit building
  an outlet from per-phase true amounts converts by `b = A n_s`.
- **Q3.R4** *Electroneutrality.* If zᵀ = ζᵀA for some ζ, then Σ_g ζ_g b_g = 0 is a checked invariant of every connection
  and feed; otherwise (neutral groups) it holds by construction and no charge row or check exists.
- **Q3.R5** *Method boundaries* (Amendment 2, A1-a). Let the stream's basis (S, A, z, R) be valid against its producer's
  method (Q3.R1) and a consumer m′ declare (S′, A′, z′, R′), valid on its own. m′ evaluates the stream iff, in exact
  arithmetic, (i) each species s of S \ S′ has an integer vector Π e_s over S ∩ S′ (same record and charge) with e_s −
  Π e_s ∈ span R, Π the identity on S ∩ S′, and (ii) an integer C solves C A = A′ Π. C is then unique (A has full row
  rank, Q3.R7), recorded in the boundary's `describe()`, and m′ evaluates b′ = C b in a fixed order; a negative entry in
  C carries `species_basis_not_monotone` (a negative b′ is an invalid trial, Q3.R1 (iii)). R′ ⊇ R with S ⊆ S′ is
  sufficient, not necessary. Otherwise `species_basis_incompatible(<method>, <S>)`. Each species of S \ S′ is a
  structural limitation, reported `solid_candidate_dropped(<method>, <phase>)` if it forms a solid candidate of the
  producer, else `species_dropped(<method>, <species>)`. Energy closes with no boundary term (Q1 argument 2).
- **Q3.R6** F5's conserved-basis slot (note §2.2.8) is this object (A, R): components (A = I, R = ∅); a Gibbs reactor (R
  = all reactions, A = element-and-charge matrix); X18 speciation (groups).
- **Q3.R7** *Group molar masses.* ṁ = Σ_g M_g b_g (Q1.R1), with (M_g, μ) solving Aᵀ M_g + μ z = M (species masses M;
  μ = 0 if zᵀ is in A's row space): solvable iff M ⊥ ker A ∩ ker zᵀ = span R (fast reactions conserve mass), unique iff
  A has full row rank (else `species_basis_redundant(<S>)`, Q6.R2's rule), and then ṁ = Σ_s M_s n_s on electroneutral
  states. Computed once at composition, exactly on the record doubles from the first independent species columns in
  declaration order, rounded once, in `describe()`; every other species meets |M_s − (Aᵀ M_g + μ z)_s| ≤ 4ε(M_s + Σ_g
  A_gs M_g + |μ z_s|), else `molar_mass_inconsistent(<S>, <species>)` (validation class). All masses use M_g.

### Rejected alternatives
- **True species on connections by default.** Their amounts change with T, P and mixing: a mixer would become a reactor
  or carry a non-equilibrium composition it misreports, and the next state point uses only the invariants anyway. Kept
  as R = ∅.
- **Neutral apparent components unconditionally.** In the reciprocal system (Na⁺, K⁺, Cl⁻, SO4²⁻) the feasible cone has
  four extreme rays (NaCl, KCl, Na2SO4, K2SO4) in three dimensions: any three neutral salts give negative amounts
  somewhere (K2SO4 = −2 NaCl + 2 KCl + Na2SO4), and all four make `b` non-unique, a null direction in every equilibrium
  outlet. Charged groups (Na⁺, K⁺, Cl⁻, SO4²⁻, H2O) satisfy (i)–(iii).
- **Element amounts on connections.** They lose the identity of species no fast reaction links (H2O against H2 + ½O2)
  unless R contains every reaction, which is chemical equilibrium, not speciation.
- **Signed apparent amounts.** They break ADR 0001 D2.3's bounds and D3's dormancy logic.

### Argument and limiting cases
No electrolytes: A = I, R = ∅, today's model bitwise. NaCl–H2O, species (Na⁺, Cl⁻, H2O), Na⁺ → NaCl, Cl⁻ → 0: ker A =
span{Cl⁻} is charged, so the intersection is {0} = span ∅ (complete dissociation). A salt candidate adds NaCl(s) →
NaCl 1, the intersection becomes span{Na⁺ + Cl⁻ − NaCl(s)}, and (ii) needs R ∋ NaCl(s) ⇌ Na⁺ + Cl⁻, the salt's phase
equilibrium; in both, M_NaCl = M_Na⁺ + M_Cl⁻, μ = −M_Cl⁻ (Q3.R7). MEA–CO2–H2O: nine species, A ≥ 0 (HCO3⁻ → (CO2 1,
H2O 1), MEACOO⁻ → (MEA 1, CO2 1), H3O⁺, OH⁻ → H2O 1), rank 3, zᵀ outside A's row space (H3O⁺ − H2O ∈ ker A has charge
+1): the intersection has dimension 9 − 3 − 1 = 5, spanned by the five speciation reactions (water, MEA protonation,
CO2 hydration, bicarbonate, carbamate). Zero flow: dormancy is decided on `b`; with A ≥ 0 a zero group forces every
species containing it to exactly 0, and the method guards ln 0 (ADR 0001 D3.3). A salt appearing: SOLID.NaCl (Q8).

### Assertions
- **Q3.A1** *Reduction.* A non-electrolyte v2 definition has A = I, R = ∅, and its probe amounts are bitwise those
  without the basis layer.
- **Q3.A2** *Admissibility* **[gen]** (exact rational arithmetic, no tolerance; R stated per case). (a) NaCl–H2O,
  species (Na⁺, Cl⁻, H2O), R = ∅: passes (i)–(iii), intersection {0}. (b) With SOLID.NaCl, species (Na⁺, Cl⁻, NaCl(s),
  H2O), R = {NaCl(s) ⇌ Na⁺ + Cl⁻}: passes, intersection span{(1, 1, −1, 0)}; with R = ∅, (ii) fails. (c) MEA–CO2–H2O,
  nine species, R = the five reactions: passes, intersection of dimension 5; without carbamate, (ii) fails. (d)
  Na–K–Cl–SO4 with groups {NaCl, KCl, Na2SO4, H2O}, R = ∅: passes (i)–(ii) and fails (iii) for every A (the NaCl row
  (0, −1, 1, 0) + λzᵀ over (Na⁺, K⁺, Cl⁻, SO4²⁻) is non-negative for no λ), admitted with `species_basis_not_monotone`;
  with charged groups (Na⁺, K⁺, Cl⁻, SO4²⁻, H2O), A = I: passes all three. Each case emits its M_g (Q3.R7).
- **Q3.A3** *Negative decomposition.* Under the neutral reciprocal declaration, a K2SO4-rich equilibrium outlet gives
  b_NaCl < 0 and is an invalid trial; under the charged groups the same state is admissible with b ≥ 0.
- **Q3.A4** *Charge.* On every connection and feed of a registered charged-group flowsheet, |Σ ζ_g b_g| ≤ 1e-12·Σ|ζ_g|
  b_g. Floor: input rounding (~ε per entry) plus mixing sums (k·ε); margin ≥ 3 decades. A feed with a residual of 1e-6
  relative is refused (`feed_not_electroneutral(<S>)`).
- **Q3.A5** *Boundary* (F4; rewritten by Amendment 2). At a registered NaCl–H2O state of Q3.A6 (a) the consumer is
  admitted with `solid_candidate_dropped(<method>, SOLID(NaCl))`, b′ bitwise b, and energy closes within K04's τ_E with
  no boundary term; on (e) b′ equals an independent fixed-order product bitwise; on each registered boundary |ṁ′ − ṁ| ≤
  1e-14·ṁ on electroneutral states (floor (k + k′ + 4)ε ≈ 2.2e-15 at three groups each; a wrong C entry errs by ≥
  1e-3); (c) is refused typed.
- **Q3.A6** *Boundary admissibility* **[gen]** (F2; Amendment 2; exact arithmetic; each method valid by Q3.A2). (a)
  NaCl–H2O apparent, producer with SOLID.NaCl (Q3.A2 (b)), consumer without (Q3.A2 (a); R′ = ∅ ⊊ R): Π(NaCl(s)) = Na⁺
  + Cl⁻, C = I, admitted, one `solid_candidate_dropped`. (b) The reverse (R′ ⊋ R): C = I, nothing dropped. (c) Species
  (A, B, W), producer groups {AB, W} with R = {A ⇌ B}, consumer A′ = I, R′ = ∅: no C (rank 2 against 3), refused; the
  reverse is admitted, C = [[1, 1, 0], [0, 0, 1]]. (d) MEA–CO2–H2O (Q3.A2 (c)) into a consumer without MEACOO⁻ and
  carbamate (eight species, four reactions): Π(MEACOO⁻) = MEA + HCO3⁻ − H2O, C = I, admitted, `species_dropped`. (e)
  True-preset NaCl–H2O (A = I) into the apparent preset: C = [[1, 0, 0], [0, 0, 1]]. Control: the former rule (R′ ⊇ R)
  refuses (a) and (d) and agrees on (b), (c), (e); the generator emits both verdicts and refuses to emit if the new rule
  refuses (a), (b), (d) or (e) or admits (c).

**Effect on the note.** §2.1.1: `species_basis: apparent|true` becomes `conserved_basis: {groups, A, R_ref}` with
presets `apparent` and `true`. §2.1.4 and §2.2.8: one object. §6 Q3: the true basis is available from F2 (preset R = ∅),
not "later". Amendment 2: §14 (A1-a; F2 gains Q3.A6, F4 Q3.A5).

## Q4. Phase labels

### Ruling
- **Q4.R1** *Phase id* = (family, qualifier, ordinal): family from a registered vocabulary, {VAPOR, LIQUID, FLUID
  (Q4.R6), SOLID}; qualifier none for an unconfined fluid phase, the confining component or model id for a confined one
  (Q4.R8), and for SOLID a component (pure solid, with a form id when the record lists polymorphs) or a solid-solution
  model id (an isotherm for an adsorbed phase, Q8.R7); ordinal k ≥ 1. Rendering: `VAPOR`, `LIQUID`, `LIQUID.2`,
  `FLUID.2`, …, `<FAMILY>(<qualifier>)[.k]` on every family (Amendment 2; the note's spelling). The rendering must be
  **injective over the whole id alphabet** `[A-Za-z0-9_.:-]` (component ids may contain `.` and digits); F2 fixes the
  spelling under that constraint, for example with a separator outside the alphabet at the qualifier boundary.
- **Q4.R2** *Interchangeable slots.* Phases of one family and qualifier share one phase model and are interchangeable.
  Their canonical active subsets are prefixes (ordinals 1..k, no gaps), adjacency on such a family is a count change of
  ±1, and note §2.2.3's lattice is taken over these counts. With the two legacy candidates this is ADR 0005 D2 exactly.
- **Q4.R3** *Canonical order* within a family and qualifier: lexicographic ascending on a key vector, compared
  **exactly** (IEEE, signed zeros normalised; richer in the first differing key → higher ordinal). Key vector: x over
  the declared `phase_order_keys`, else water (InChIKey `XLYOFNOQVPJJNP-UHFFFAOYSA-N`) if present, then every other
  component in definition order; for FLUID next the phase's specific volume v̂ (Amendment 2: two phases of one fluid
  model tie on every composition key at a pure component); last, the phase's mass. x is the mole fraction on the
  method's composition basis. This is a total order (phases tied on every key are bitwise identical, so their order
  leaves the state unchanged); thresholds only flag (Q4.R5). τ_comp = 1e-6. Density is not used, except as FLUID's v̂,
  which decides only after every composition key ties.
- **Q4.R4** *When.* Labels are assigned at every attempt opening and at every converged closure; within an attempt,
  labels and variable ids never change. A closure whose canonical order differs from the attempt's labels is relabelled
  by permutation (bitwise exact) and recorded `relabel(<point>: <from>-><to>, …)`. Root fingerprints use canonical
  labels.
- **Q4.R5** *Flags.* For each pair adjacent in canonical order, the deciding key is the first on which they differ; if
  its |Δx| ≤ 10 τ_comp (for v̂: |Δ ln v̂|) the order is flagged `near_threshold` (ADR 0007 D2.4). If max_c |Δx_c| ≤
  τ_comp over all components (and, for FLUID, |Δ ln v̂| ≤ τ_comp), the pair is indistinguishable (coexisting phases this
  close occur only near a critical point): flagged, and the point carries Q5.R4's `near_critical` limitation.
- **Q4.R6** *One fluid model* (rewritten by Amendment 2, S5). A method declares its fluid phases as one model
  (`fluid_model: single`: an EOS such as PR, SRK, CPA, SAFT, IAPWS-95) or as separate vapour and liquid models (`split`:
  γ–φ). Under `single` every unconfined fluid phase is a slot of one interchangeable family FLUID (Q4.R2), ordered by
  Q4.R3; VAPOR and LIQUID are not used. Each FLUID phase reports `character` ∈ {vapour_like, liquid_like} from the
  method's declared identification rule (O-11), never in an id, signature, order, adjacency or fingerprint: a change of
  character, or two phases of one character, changes no signature; appearance or disappearance is a count change of ±1.
  Within an attempt each FLUID slot keeps the root (density branch) it opened on, never re-selected at an iterate; a
  lower-Gibbs root at closure is a Q5.R3 witness, and the next opening records `root_switch(<point>, <slot>)`. Legacy
  providers and their delegating compositions declare `split`: VAPOR and LIQUID name their root-selection models, a
  single phase takes the rule's label at the opening, and a change between attempts is a non-adjacent restart (ADR 0005
  D4), recorded, as today.
- **Q4.R7** *Legacy rendering.* A point of a `split` method with candidates {VAPOR, LIQUID} renders `LIQUID`, `VAPOR`,
  `TWO_PHASE` as today; `ZERO_FLOW` stays a stream property.
- **Q4.R8** *Confined phases* (Amendment 2, S5). A phase model declares its support, the components it can hold; outside
  it amounts are structurally `+0.0`, never trial variables. A fluid family has one unconfined phase model per method; a
  further model in it must have a proper subset as support (*confined*) and forms its own slot chain, qualified by the
  component id if the support is one component (X21's free water: `FLUID(water)` under `single`, `LIQUID(water)` under
  `split`), else by its model id. A one-component confined phase takes Q5.R2's scalar pure-phase test with its own
  chemical potential for μ_S,k, claim `exact`, indicator that tm (Q5.R8); a several-component one takes its own local
  trial. Q8.R7's sorbent is a component outside the support of every phase but one.
- **Q4.R9** *Routing a lone fluid phase* (Amendment 4, SQ-F6-1; ADR 0065 D9). At a point a unit routes, a phase with
  no other active unconfined fluid phase takes the port a lone VAPOR takes under ADR 0065 D9 (i) if it is VAPOR or a
  `vapour_like` FLUID, and the port a lone LIQUID takes otherwise: a FLUID phase routes as the `split` family its
  `character` names. The character is the identification rule's (Q4.R6, O-11) at the opening's root, fixed with the
  routing for the attempt; at closure a changed character closes the attempt `routing_order_changed(<unit>)` and the
  adjacent assignment (the lone phase's other port) opens. Each identification rule declares its scalar q and threshold
  q* (Venkatarathnam and Oellrich's parameter: q* = 1); |q − q*| ≤ 10 τ_char |q*| attaches `near_threshold` to the
  routing (ADR 0007 D2.4), τ_char = 1e-6 (O-14). With two or more active fluid phases Q4.R13 rules (amended by
  Amendment 5), its density flag at τ_ρ = 1e-6 (O-14); beside an active confined phase Q4.R13 rules as well. **This
  gives O-11 a numerical consequence:** the identification rule decides through which outlet a lone dense,
  supercritical or near-critical phase leaves a unit, and (Q4.R13) whether each of several coexisting fluid phases
  leaves by `vapor`.
- **Q4.R10** *Vapour fraction* (Amendment 5, SQ-ST-1; ADR 0068 D5). (a) A substream whose phase list is decided reports
  `vapor_fraction_molar` = N_V/N_P and `vapor_fraction_mass` = M_V/M_P. N_P and M_P are the amounts and masses of its
  listed phases (Q4.R11), N_V and M_V those of its listed phases in the **vapour group**, each accumulated from 0.0 in
  listing order. The vapour group is the VAPOR family in v1; v2 adds every FLUID phase whose recorded `character` is
  `vapour_like`, which is Q4.R13's vapour group, so the vapour fraction is the share a unit with a `vapor` port sends
  there. `phase_fraction_molar` = n_p,tot/N_P and `phase_fraction_mass` = m_p,tot/M_P. (b) Hence, exactly in IEEE
  arithmetic: 0.0 when no listed phase is in the vapour group; 1.0 when every one is; 0 ≤ vf ≤ 1 when no listed amount
  is negative (rounding is monotone); and in v1 `vapor_fraction_molar` is bitwise the VAPOR phase's
  `phase_fraction_molar`. (c) It is an amount ratio, never the thermodynamic quality (h − h_L)/(h_V − h_L); no member
  is named `quality`, and the documentation maps "steam quality" to `vapor_fraction_mass`. On a one-component carried
  split the two agree by the lever rule (E2); outside the dome the vapour fraction is 0.0 or 1.0, where the
  thermodynamic quality leaves [0, 1]; for a mixture the latter is undefined. In v1 the family is the legacy label
  (Q4.R7): a supercritical fluid labelled VAPOR has the vapour fraction 1.0. (d) It is null only when no phase list is
  decided (`zero_flow`, `flash_failed`) or its quotient is not finite (Q4.R11 (c)); a property failure never nulls it.
  (e) v2 keeps both members, adds `character` to FLUID phase objects (Q4.R6), read from the state point and never
  decided again by the report, and counts a listed SOLID phase in N_P and M_P (O-20).
- **Q4.R11** *Listing* (Amendment 5, SQ-ST-6; ADR 0068 D3). (a) A phase of the substream's phase decision is listed iff
  its amount n_p,tot = Σ_c n_p,c (Python `sum`, provider order) is `!= 0.0`: the dormancy test applied to the phase, so
  ±0.0 is not listed and every non-zero amount is, however small and of either sign. Listed phases are ordered by family
  (VAPOR, LIQUID, FLUID, SOLID), then ordinal, and keep the decision's ids, never renumbered (a v2 list therefore need
  not be a Q4.R2 prefix: activity is the state point's, listing is by amount). (b) Amounts are reported as decided and
  **never clamped**. At a verified state a carried V or L may be a small negative within the bounds checks' τ_flow; it is
  listed, its phase fraction is negative, the vapour fraction lies outside [0, 1] by at most |amount|/N_P, and
  `H_flow` still equals Σ_p H_p and the verifier's Ḣ bitwise. (c) *Quotients.* Every quotient the report forms (x, w,
  h, h_mass, s, s_mass, ρ, the phase and vapour fractions) is an IEEE-754 division. A non-finite result (a zero
  denominator, as when the mass of a listed phase or of a flowing stream underflows to +0.0) is null with
  `value_not_finite(subject, quantity)`; the report never raises.
- **Q4.R12** *The report's phase decision for an undeclared, unsplit stream* (Amendment 5, SQ-ST-3; ADR 0068 R3). (a)
  A flowing stream with neither a carried split nor a declared producer-port phase is decided by one TP flash of the
  provider at its stored (n, T, P): the listed phases are the flash's outlets (Q4.R11), with **no ε_adm or τ_dew
  snap**, no lifted split and no further decision; `phase_source` is `flash`. The decision is the report's and is never
  presented as the verifier's. A flash that is not `ok` lists no phases; every phase-derived quantity is null with
  `flash_failed(stream, status)`; n, m, x, w, T and P are given. (b) *Where the two may differ.* Every substream reports
  `flash_near_phase_boundary`, false unless the phase source is `flash`, and then true iff (i) two or more phases are
  listed and min_p |n_p,tot|/N_P ≤ τ_β = 1e-8 (O-19), or (ii) the certificate holds a row for the stream with category
  `independent_split`, result `not_applicable` and reason `temperature_degenerate` or `fresh_flash_unresolved` (the
  verifier could not recompute that stream by a fresh flash). The stream's quoted checks (note §4.4) include those
  `independent_split` rows. (c) *What it covers* (§17 argument 4). The verifier reads a flashed two-phase stream as
  single-phase only where a device acts: on SYN-001's form when Σ z K ≤ 1 + ε_adm or Σ z/K ≤ 1 + ε_adm (ε_adm =
  1e-12); on PR-C1's when l_NH3/n_tot ≤ τ_dew = 1e-10; at a lifted split that is temperature-degenerate or unresolved,
  where it reads the stored split. In the first two the report's minority fraction is at most c·ε_adm, c = max(1,
  K_max)²/Σ_c z_c (K_c − 1)² (dew: K → 1/K), and at most τ_dew/x^L_NH3; so (i) covers them where c ≤ 1e4 and
  x^L_NH3 ≥ 1e-2, and (ii) covers the third. Elsewhere only Q4.A15 (e) watches (§17, not established). (d) *What the
  difference is.* Where the verifier reads single-phase a stream the report lists as two phases, Ḣ_report − Ḣ_verifier
  = Σ_c n_min,c (h_c^min − h_c^maj) at (T, P): the minority phase evaluated in its own family instead of the majority's
  (SYN-001's form; exact in real arithmetic). The energy summary shows the report's closure beside the quoted row
  (ADR 0068 D6); the flag says why they may differ. (e) v2's `state_point` source makes no flash and reports false; the
  state point's own flags (Q4.R5, R9, R13) are added beside it.
- **Q4.R13** *Routing the fluid phases of a point* (Amendment 5, SQ-F6-5; ADR 0065 D9; generalises Q4.R9). At a point a
  unit routes, the active fluid phases (confined ones included, Q4.R8) form two groups. The **vapour group** is every
  VAPOR phase and every FLUID phase whose `character` (Q4.R6, O-11) is `vapour_like`; the **liquid group** is the rest.
  Every phase of the vapour group leaves by `vapor`, or by the first port of `light_to_heavy` when `vapor` is null. The
  liquid group is ordered by mass density, ascending, an exact tie by canonical ordinal; its k-th phase leaves by the
  k-th port of `light_to_heavy`, and phases beyond the last port by the last port. SOLID phases leave by `solids`, else
  by the last port. One rule serves `split` and `single` methods and every phase count: with two `split` candidates it
  is today's routing, and with one fluid phase it is Q4.R9. The characters are fixed with the routing at the opening
  (Q4.R9); at closure a changed group membership or liquid-group order closes the attempt
  `routing_order_changed(<unit>)`, and the adjacent assignment moves one phase between the groups or transposes one
  density-adjacent liquid-group pair. Flags (ADR 0007 D2.4): every FLUID phase with |q − q*| ≤ 10 τ_char |q*|, and
  every adjacent liquid-group pair with |ln ρ_a − ln ρ_b| ≤ 10 τ_ρ (exact ties included), attach `near_threshold` to
  the routing; τ_char = τ_ρ = 1e-6 (O-14). Inside the vapour group nothing is ordered or flagged.

### Rejected alternatives
- **The default's "without a key, descending mass density".** It contradicts its own key rule in the commonest case (a
  water key puts the aqueous phase at LIQUID.2, density order puts the denser aqueous phase at LIQUID); density
  inversions occur in normal operation (heavy oil against water near 1000 kg/m³), so labels would swap inside an
  operating range; many activity-coefficient liquids have no density model. Decanter routing to the light or heavy port
  is a density decision F6 takes and records, independent of labels.
- **Discovery order.** Path-dependent: one root, different labels; breaks fingerprints and `same_root`.
- **Relabelling inside an attempt.** Variable ids would change mid-attempt (ADR 0005 D2).
- **Gaps (LIQUID.2 active without LIQUID).** They make interchangeable phases distinguishable and multiply lattice nodes
  without physical meaning.

### Argument and limiting cases
Binary LLE away from the plait point: |Δx_water| ≈ 0.9 ≫ τ_comp, unique. VLLE: VAPOR, LIQUID, LIQUID.2. A liquid
disappears: the remaining one becomes LIQUID at the next opening (relabel recorded). A new liquid poorer in water takes
LIQUID and the old one becomes LIQUID.2. The plait point: a tie, inside D09's critical-region limitation. τ_comp sits
about 4 decades above the expected cross-platform agreement of converged mole fractions at well-conditioned points (ADR
0007 measured ≤ 2.2e-14 relative on ordinary quantities); measuring it is O-5.

### Assertions
- **Q4.A1** *Order invariance.* On the registered LLE and VLLE states, the flash with its trial list forward and
  reversed gives identical labels and state vectors that are bitwise permutations; the water-richest phase has the
  highest ordinal of its family (LIQUID.2 under `split`; amended by Amendment 2).
- **Q4.A2** *Prefix* (R0 scan over every v2 record). No record has LIQUID.k or SOLID.q.k active without k−1 active.
- **Q4.A3** *Relabel.* A registered path on which a liquid disappears and reappears emits `relabel(…)`, and its final
  state compares `SAME` under `same_root` with a run opened directly in the final set.
- **Q4.A4** *Total order* **[gen]**. Liquids over (water, A, B) with x_water = 0.1, 0.1 + 7e-7, 0.1 + 1.4e-6 and x_A =
  0.6, 0.5, 0.4 (a cycle under the former thresholded rule) get labels in that order from all six input orders, both
  pairs flagged, none indistinguishable; 10⁴ random near-tied triples likewise; two water-free liquids (+0.0 = +0.0)
  are decided by the next key.
- **Q4.A5** *Injectivity* **[gen]**. 10⁴ random triples plus adversarial qualifiers (`a.2`, `2`, `a:b`, `SOLID`, `-`, a
  component id equal to a model id) give no colliding rendering, with qualifiers on every family (`FLUID(a.2)`,
  `LIQUID(FLUID)`, `FLUID(water).2`; Amendment 2; also F2's id exit).
- **Q4.A6** *Lattice.* With candidates {VAPOR, LIQUID, LIQUID.2}, {VAPOR, LIQUID} is adjacent to {VAPOR, LIQUID,
  LIQUID.2}, and {LIQUID.2} alone is never constructed.
- **Q4.A7** *Legacy.* F5's decision equivalence holds with two-candidate rendering.
- **Q4.A8** *Pure-fluid order* **[gen]** (F5; Amendment 2; F4's re-implemented cubic, a `single` method, on pure water
  at 101 325 Pa, `ĥ` at β ∈ {0.25, 0.5, 0.75} of the saturation interval as in Q1.A1). The two FLUID phases have x = 1.0
  bitwise; the liquid-like one is FLUID and the vapour-like one FLUID.2 at all three β, decided by v̂. At β = 0.5 the
  masses are bitwise equal (registered for that reason): with v̂ dropped the order is undecided there, and mass alone
  swaps the labels between β = 0.25 and 0.75.
- **Q4.A9** *No family churn* (F5; Amendment 2; same method, warm-started isobaric paths, in the method's T_c, P_c). At
  1.13 P_c, T from 0.93 T_c to 1.08 T_c (one root throughout): signature {FLUID: 1} at every point, no restart, at least
  one change of `character`. At 0.9 P_c, `ĥ` from compressed liquid to superheated vapour: counts 1 → 2 → 1 by adjacent
  steps only. Mutation control: the same EOS declared `split` with the same identification rule (test double) restarts
  non-adjacently on the first path.
- **Q4.A10** *Confined phase* (F5; Amendment 2; synthetic `single` method with the ideal gas as fluid model and a
  confined pure-water liquid with f_w = P_sat(T), ln P_sat = ln 101 325 − (40 650/R)(1/T − 1/373.15), R = 8.314 462
  618; feed water 0.1, N2 0.9 mol/mol at 1e5 Pa). The water phase is `FLUID(water)`, never FLUID.k, its N2 amount is
  exactly `+0.0`, and its test is tm_w = ln P_sat(T) − ln(z_w P), claim `exact`: tm_w(T_d ∓ 0.01 K) = ∓4.862e-4 (3.7
  decades outside the band), and the point is {FLUID, FLUID(water)} below T_d and {FLUID} above, with the boundary at
  T_d = 317.103 397 758 K (1/T_d = 1/373.15 − (R/40 650) ln(1e4/101 325)) within 1e-9 K (floor ~1e-13 K).
- **Q4.A11** *Family scan* (F5 R0 scan; Amendment 2). No record of a `single` method has a VAPOR or LIQUID phase, none
  of a `split` method has FLUID, every `character` sits outside ids and fingerprints, and legacy-provider records are
  unchanged (Q4.A7).
- **Q4.A12** *Lone-phase routing* (F6, E-F6-10 (c), (d); Amendment 4). Q4.A9's method and paths, through a `std.flash`
  (ports `vapor`, `liquid`; the drum's ĥ set by its duty). (a) At 1.13 P_c, T from 0.93 T_c to 1.08 T_c: one FLUID
  phase at every point; the whole flow leaves by `liquid` while it is `liquid_like` and by `vapor` while `vapour_like`;
  the port changes exactly once, at the path index where the reported character changes, recorded
  `routing_order_changed`; the other outlet is dormant with its Q1.R4 label; energy closes within τ_E at every point.
  (b) At 0.9 P_c from compressed liquid to superheated vapour: `liquid` only, then both (the lower mass density on
  `vapor`), then `vapor` only. (c) **[gen]** The generator locates on path (a), by bisection on the method's own q, a
  point with |q − 1| ≤ 5e-6 and one with |q − 1| ≥ 1e-3: the first carries `near_threshold` on its routing, the second
  does not. Mutation control: the map reversed (`vapour_like` → `liquid`) moves the whole flow at both ends of path (a).
- **Q4.A13** *Vapour fraction* (ST G2, G4, G6; Amendment 5). (a) *Definition, bitwise.* On every corpus substream with a
  phase list, the test recomputes in listing order vf_molar = (0.0 + Σ_VAPOR n_p,tot)/N_P, vf_mass likewise, and the
  phase fractions; vf_molar equals the VAPOR phase's `phase_fraction_molar` when VAPOR is listed and is 0.0 when it is
  not. (b) *Exactly 0 and 1.* SYN-001, n = (1, 1, 1) mol/s, P = 1e5 Pa: at T = 340 K the list is [LIQUID] and both
  fractions are 0.0; at T = 385 K it is [VAPOR] and both are 1.0 [pre: the provider's Σ z K < 1 at 340 K and Σ z/K < 1
  at 385 K; sanity −0.184 and −0.256]. Every R2 corpus stream gives 0.0 or 1.0 by its declared family. (c) *Interior.*
  G2's S4 has 1e-3 < vf_molar < 1 − 1e-3 [pre]; G3's state gives 0.5 exactly. (d) *Bases.* Where every listed
  phase's components share one molar mass (SYN-001, water), |vf_mass − vf_molar| ≤ 4(C + 1) ε·vf_molar, C the
  substream's component count (worst-case rounding (2C + 1) ε, §17 argument 9; margin ≥ 2). At the first corpus
  substream with two listed phases and unequal molar masses [pre, O-21], |vf_mass − vf_molar| > 1e-3. Mutation
  control: a mass fraction formed from molar amounts passes on SYN-001 and water and fails there. (e) No key matching
  `/quality/i` occurs in the schema, in a corpus document or among the CLI's CSV columns. (f) *Null.* R0 gives
  `zero_flow` (Q1.A14). Q1.A14 (b)'s stream with n := (1, 1, 1) and T := 450 K, outside the domain, gives phases [] and
  both fractions null with `flash_failed(stream, out_of_domain)`, while n, x, T and P are given. Q1.A15 (d): a property
  failure leaves the fractions given.
- **Q4.A14** *Listing* (ST G4, G6, G7; Amendment 5). TH-C1's S5 [pre: R1] overwritten, n5 and P5 kept: (a) V := +0.0
  and V := −0.0, L := n5: [LIQUID], both fractions 0.0, `H_flow` bitwise `saturated_enthalpy`. (b) V := 1e-300,
  L := n5: [VAPOR, LIQUID], the VAPOR `n_total` 1e-300, vf_molar > 0, `H_flow` bitwise. (c) V := −1e-12·n5, L := n5 −
  V: [VAPOR, LIQUID]; the VAPOR `n_total` and `phase_fraction_molar` negative and unclamped; vf_molar = V/(0.0 + V + L)
  bitwise and < 0; `H_flow` bitwise `saturated_enthalpy` and bitwise Σ_p H_p. (d) Q1.A14 (b)'s SYN-001 stream with
  n := (5e-324, 0.0, 0.0) at (350 K, 1e5 Pa): flowing; `T` = 350.0; phases [VAPOR] with `n_total` 5e-324 [pre: the
  flash answers VAPOR; sanity Σ z/K = 1/K_A = 0.447]; `h` = 30 000.0 exactly (h_A^V(350 K) = 100·50 + 25 000, and
  H_p = 30 000·2⁻¹⁰⁷⁴ is exact among subnormals); `x` = (1.0, 0.0, 0.0); vf_molar = 1.0; `m_total` = +0.0; `h_mass`,
  `w`, vf_mass and `phase_fraction_mass` null with `value_not_finite`; no exception. (e) Every R3 single-phase
  substream of the corpus lists exactly one phase. All exact.
- **Q4.A15** *The report's decision near a phase boundary* (ST G16, new; Amendment 5). SYN-001, n = (1, 1, 1) mol/s,
  P = 1e5 Pa (= P_r, so ln K_i = (L_i/R)(1/T_b,i − 1/T) exactly), on Q1.A14 (b)'s stream. Four temperatures, located
  by bisection in double on the provider's own sums as its flash forms them: B-near, 5e-13 ≤ Σ z K − 1 ≤ 1e-12; B-far,
  1e-5 ≤ Σ z K − 1 ≤ 1e-4; D-near, 5e-13 ≤ Σ z/K − 1 ≤ 1e-12; D-far, 1e-5 ≤ Σ z/K − 1 ≤ 1e-4. Sanity values (50-digit
  scratch evaluation of syn001's closed forms; not expectations): T_bub = 347.441 181 981 440 K, T_dew =
  374.270 304 118 478 K; each near band ≈ 1.9e-11 K wide (≈ 330 doubles); c = 6.831 (bubble), 7.158 (dew). (a)
  *Near.* [pre, O-21] The flash is TWO_PHASE. The list is [VAPOR, LIQUID]; the minority fraction is > 0 and ≤ c·δ, c
  and δ computed by the test from the provider's K (so ≤ 7.2e-12; sanity 7.7e-13 to 1.7e-12);
  `flash_near_phase_boundary` true; the verifier's decision (`checks._admissible_phase`) is LIQUID at B-near and VAPOR
  at D-near. With ΔH = `H_flow` − `checks.enthalpy_flow` at the same state and context, |ΔH − Σ_c n_min,c (h_c^min −
  h_c^maj)| ≤ 64 ε Σ_c (n_c |h_c^maj| + n_min,c |h_c^min|), ΔH > 0 at B-near and < 0 at D-near; [pre] the closed form
  exceeds ten times the tolerance (sanity 6.2e-8 to 1.2e-7 W against 2.0e-10 W at B-near, −8.3e-8 to −1.7e-7 W against
  1.6e-9 W at D-near). Floor: the flash rebuilds n_V,c + n_L,c = n_c (1 + η), |η| ≤ 4ε, and each sum of ≤ 4 terms adds
  ≤ 1.5ε, so the floor is ≤ 16 ε (…); margin ≥ 4. (b) *Far.* TWO_PHASE; minority fraction ≥ δ·min(1, K_min)²/Σ z (K −
  1)² (sanity 0.064 δ and 0.110 δ, so ≥ 6.4e-7 > 64 τ_β); flag false; `_admissible_phase` returns None; `H_flow`
  bitwise `checks.enthalpy_flow`. (c) *Rows.* B-far with a test-local certificate carrying an `independent_split` row
  for the stream (result `not_applicable`, reason `temperature_degenerate`, then `fresh_flash_unresolved`): flag true and
  the row quoted in the stream's `checks`; without the row, false. (If note §4.1's precondition refuses the edited
  certificate, the core's flag function is tested on the same inputs.) (d) Q4.A13 (b)'s single-phase states: false.
  (e) *Corpus* (counts recorded, O-19). On every R3 substream of the SYN-001 and PR-C1 forms the test forms the
  verifier's decision (SYN-001: the flash, then `_admissible_phase` when TWO_PHASE; PR-C1: the flash, then VAPOR when
  TWO_PHASE and `pr_c1.liquid_fraction` ≤ `TAU_DEW`); a decision differing from the listed families requires the flag.
  Recorded per basis: R3 substreams, flagged, disagreeing, max c·ε_adm (SYN-001) and max τ_dew/x^L_NH3 (PR-C1).
  Mutation controls: applying ε_adm lists one phase at B-near and fails (a); dropping the minority phase gives ΔH = 0;
  a flag on vf_molar alone misses D-near.
- **Q4.A16** *Routing groups* (F6, E-F6-10 (g); Amendment 5). The router as a pure function of the declaration and the
  active phases (id, family, character, q, mass density). Phases (q* = 1): a = FLUID, liquid_like, q 0.2, ρ 990
  kg/m³; b = FLUID.2, liquid_like, q 0.3, ρ 660; c = FLUID.3, vapour_like, q 3, ρ 4; d = FLUID.4, vapour_like, q 1.5,
  ρ 1100; e = FLUID.5, vapour_like, q 2, ρ 30. Units: F `{vapor: vapor, light_to_heavy: [liquid]}`; T3 `{vapor: vapor,
  light_to_heavy: [light, heavy]}`; D `{vapor: null, light_to_heavy: [light, heavy]}`. Expected port → phases: (1)
  F{a, b}: vapor ∅, liquid {a, b} (the review's M4 failure 1); (2) F{a, c}: vapor {c}, liquid {a}; (3) T3{a, b, c}:
  vapor {c}, light {b}, heavy {a}; (4) D{a, b, c}: light {c, b}, heavy {a}; (5) D{a, b}: light {b}, heavy {a}; (6)
  T3{a, b, d}: vapor {d}, light {b}, heavy {a}; (7) F{a, c, e}: vapor {c, e}, liquid {a}; (8) F{b}: liquid; F{c}:
  vapor; D{c}: light; D{a}: light. (9) The `split` mirror of (1)–(6) and (8) (c, d → VAPOR; a, b → LIQUID slots, same
  densities) gives the same sets. (10) Flags: T3{a, b′, c} with ρ_b′ = 990·exp(−5e-6) flags the pair, with
  990·exp(−1e-3) does not, and with ρ_b′ = 990 sends a to `light` and b′ to `heavy` (ordinal) and flags; q_c =
  1 + 5e-6 flags cases (2), (3) and (4), q_c = 1 + 1e-3 does not; no other case flags. Exact (the rule against its statement; F6's runs carry the
  physics, E-F6-10 (e), (f)). Mutation controls: SQ-F6-5's default for `vapor: null` gives (4) light {c}, heavy {b, a};
  a density-only rule sends b to `vapor` in (1) and d to `heavy` in (6).

**Effect on the note.** §2.1.5: the triple and injectivity. §2.2.2–2.2.3: prefix rule and count lattice; exact order
with flags (Q4.R3, R5). §6 Q4: density removed; water the default key. Amendment 2: §14 (S5; F5 gains Q4.A8–A11).

## Q5. Stability test, and what a certificate may claim

### Ruling
- **Q5.R1** *Test.* Michelsen's modified tangent-plane distance, `tm*(W) = 1 + Σ_i W_i (ln W_i + ln φ_i(W) − d_i − 1)`,
  `d_i = ln x_i^ref + ln φ_i^ref`, the reference being any active phase of the tested state, over components with
  x_i^ref > 0 only (zero components stay zero, ADR 0001 D3.3).
- **Q5.R2** *Registered trial set `F5-trials-v1`.* Wilson-K vapour-like (W = zK) and liquid-like (W = z/K) trials; one
  near-pure trial per component with z_i > 0 (others at 1e-10); each a local minimisation. A pure-solid candidate takes
  the scalar test `tm_S = μ_S,k/RT − d_k`, exact with no search; a solid-solution candidate takes its own local trial.
- **Q5.R3** *Classification.* A point is **unstable** iff some trial yields a witness W with tm*(W) < −τ_tm (any W,
  stationary or not). A trial converging to the reference composition, or to an active phase (max_i |w_i − x_i| ≤
  τ_comp), is not a witness. **τ_tm = 1e-8**; near-threshold band (ADR 0007 D2.4) |tm*_min| ∈ [1e-9, 1e-7]. Under
  FLUID (Amendment 2), ln φ(W) is taken on the method's minimum-Gibbs root at W, and a trial is trivial only if it also
  matches that phase's root (|Δ ln v̂| ≤ τ_comp): a trial at the reference composition on another root is a witness.
- **Q5.R4** *Claims.* `phase_stability` ∈ {pass, fail, unsupported}.
  - **fail** carries the witness (W, tm*(W), trial id): a proof, re-evaluated by the verifier with a fresh provider. A
    fail at the certified state makes the certificate `FAILED`.
  - **pass** carries a claim level. `exact` when every candidate's test is exhaustive by construction: a pure-solid
    candidate; a method declaring composition-independent K (its two trials have unique stationary points with tm* = 1 −
    Σ z_i K_i and 1 − Σ z_i/K_i, and its ideal liquid cannot split); a one-component point whose method declares its
    phase roots enumerable. `local` otherwise, with the limitation "local search; global stability not established" and
    the trial-set id; it does not prevent `VERIFIED`.
  - **unsupported**, typed: `no_fugacity_model(<phase>)`; `charged_species_tpd` (until X18 registers a TPD over neutral
    combinations); and, when every trial is trivial and λ_min of Michelsen's stability matrix `B_ij = δ_ij + √(z_i z_j)
    ∂ln φ_i/∂n_j` (n_tot = 1, unit eigenvector u) is below τ_spin = 1e-4, `near_critical` if also |c3| < τ_crit = 1e-2,
    else `near_spinodal`; c3 = d²/ds² Σ_i Δn_i ln f_i(z + sΔn) at s = 0, Δn_i = √z_i u_i, is the cubic form that vanishes
    with λ_min at a critical point (Heidemann and Khalil 1980) and not elsewhere on the spinodal (F5's error on it ≤
    1e-4, Q5.A6). Listed as "stability NOT_ASSESSED" (ADR 0005 D7's pattern); never read as pass; not by itself
    preventing `VERIFIED`.
- **Q5.R5** *Where it runs.* The solve's screen uses the same function and τ_tm at every point whose method is not a
  legacy provider or that has more than the two legacy candidates; at two-candidate points of a legacy provider the
  legacy admissibility decision stays, so decision equivalence holds. The verifier has its own implementation (R-016).
- **Q5.R6** *Records.* Each stability decision records tm*_min, the witness if any, the trial-set id and the
  `near_threshold` flag; its result word is R0 conditionally (ADR 0007 D2.4).
- **Q5.R7** *Inactive phases at a procedural point.* Amounts exactly `+0.0`; every other output (composition, h, s, v,
  ln φ, …) the label `+0.0` with derivative `+0.0`, reported null (`phase_inactive`). No row of the attempt reads such an
  output except times an amount of that phase; a row that would is swapped by its unit's zero-flow form (Q1.R4), or,
  if its manifest (F6) declares none, refused at the opening (`inactive_phase_read(<row>, <phase>)`). So no residual or
  Jacobian entry depends on the labels (the lifted form drops inactive phases, ADR 0005 D5). The incipient composition
  is Q5.R8's W_p, kept in the stability record; it seeds the phase when an opening activates it.
- **Q5.R8** *Appearance indicator* (note §2.2.7). For the next inactive slot of each family and qualifier (Q4.R2),
  ι_p = tm*(W_p) against the attempt's active phases, W_p *tracked*: at an opening, or when p leaves the active set, the
  lowest-tm* non-trivial stationary point its `F5-trials-v1` trials reach (ties by trial id), then continued from the
  previous evaluation. ι_p is defined where the continuation reaches a non-trivial local minimum (max_i |w_i − x_i| >
  τ_comp, λ_min of the stability matrix at W_p > 0); elsewhere `indicator_untracked(<point>, <p>)`, never read as a
  sign, and undefined → negative is an unbracketed event (the step is refined). ι = tm_S (pure solid) and ι_V = 1 − Σ
  z_i K_i, ι_L = 1 − Σ z_i/K_i (composition-free K) are defined everywhere. Disappearance keeps the phase amount.
  For FLUID (Amendment 2), one W is tracked per distinct non-trivial minimum the trials reach at the opening (vapour-
  and liquid-like alike), each recorded, and ι of the next FLUID slot is their minimum.
- **Q5.R9** *Steady controller closure* (Amendment 4, SQ-F6-3; ADR 0065 D10). A steady `std.pid` with integral
  action, limits out_min ≤ out_max (out_min > out_max is refused at binding by ADR 0065 D2's parameter validation) and
  σ = +1 for `reverse`, −1 for `direct` has as its steady states exactly the solutions of σ·e ∈ N(out), e = sp − pv,
  N the normal cone of [out_min, out_max] at out: the rest points of the integrator with clamping anti-windup. So
  `tracking` closes iff out_min ≤ out ≤ out_max, `saturated_high` iff σe ≥ 0, `saturated_low` iff σe ≤ 0 (ADR 0065
  D10's condition, confirmed). A failed closure opens: from `tracking` above out_max, `saturated_high`; below out_min,
  `saturated_low`; from a saturated regime with the wrong sign, `tracking` if this solve has not visited it, else the
  other saturated regime (a recorded non-adjacent restart, ADR 0005 D4), so ADR 0005's `no_repeated_signature` is never
  needed and three attempts suffice; if all three fail, the solve ends with ADR 0005's cycle status. At out_min =
  out_max the two saturated rows coincide and one of them closes. A closure is near threshold, flagged `near_threshold`
  (ADR 0007 D2.4), when a saturated regime has |e| ≤ 10 τ_pv or `tracking` has min(out − out_min, out_max − out) ≤
  10 τ_out (τ the certificate tolerances of the two signals' kinds); a saturated regime at closure carries the notice
  `controller_saturated`. TX's dynamic `std.pid` must have these rest points (a clamped integrator); a law with another
  anti-windup is another unit.
- **Q5.R10** *`heat_direction`* (Amendment 4, SQ-F6-4; ADR 0065 D11). For a heat connection with Q its variable,
  positive from endpoint A into B (ADR 0001 D4.1), and the temperature intervals I_A, I_B of D11: if Q > τ_Q the value
  is min I_B − max I_A; if Q < −τ_Q it is min I_A − max I_B. The check passes iff value ≤ τ_hd and is near threshold iff
  τ_hd/10 < value ≤ 10 τ_hd, the one-sided rule of the exchanger's temperature-cross check (`verify/table.py:275–298`,
  `:965`). |Q| ≤ τ_Q gives `not_applicable(no_heat_flow)`; a dormant `from` or `to` stream gives
  `not_applicable(zero_flow)` (T05b §9.3's rule). τ_hd is the policy's `temperature` tolerance (1e-6 K registered;
  O-15), τ_Q its `heat_rate` tolerance. Equality (value 0) passes, as the exchanger's pinch does. The check is
  necessary, not sufficient: it excludes a source wholly colder than its sink, not a crossing inside an exchanger.
- **Q5.R11** *Near-singular algebraic block* (Amendment 4, SQ-F7-1; ADR 0066 D7). At every consistent
  (re-)initialisation, Ĝ = S_g⁻¹ (∂g/∂z) S_z on D7's algebraic rows g and columns z with the policy's scales, and
  rcond₁(Ĝ) by K04's estimate (SuperLU with ADR 0004's options, `onenormest`). τ_idx = K04's τ_ill = 1e-8 (O-16): below
  it the trajectory certificate carries the typed limitation `dae_index_near_singular` with rcond₁ and t recorded, and
  the run continues; rcond₁/τ_idx ∈ [1/10, 10] flags `near_threshold` (ADR 0007 D2.4). A structurally deficient block
  stays `dae_index_unsupported` at build. The reason is K04's: below 1e-8 the algebraic columns are not determined to
  better than 1e-8 relative under perturbations at the Jacobian's 1e-14 error, and a sensitivity through Ĝ loses more
  than 1e-6. A liquid in a rigid vessel is near-singular only when its scaled expansivity and compressibility are both
  small (§16 argument 5): a PR liquid (α s_T ≈ 0.1) is regular, contrary to ADR 0066 D7's example.

### Rejected alternatives
- **A fixed trial set claimed as global.** False for non-ideal liquids, which can have several LL minima.
- **A global method (interval Newton, tunnelling) as default.** No general guarantee at acceptable cost for EOS
  mixtures; a future `global` claim level with its own registration stays open (R-924).
- **τ_tm at roundoff (1e-12).** An active phase used as a trial gives tm* ≈ ±(the ln-fugacity residual), so converged
  equilibria would be misclassified.
- **τ_tm = 1e-6.** Misses phases of ~1e-6 of the feed, above the 1e-8 relative balance resolution.
- **Requiring a stationary witness.** Only weakens the proof and its recheck.
- **Unsupported read as pass, or as fail.** Rule 5; R-924.

### Argument and limiting cases
*Asymmetry:* one point proves instability; stability is a global statement, hence claim levels. *τ_tm:* near the binodal
tm*_min ≈ −a·δ (δ the depth inside, a = O(1)), so the incipient phase amount is of order |tm*| and τ_tm = 1e-8 matches
ADR 0001 D6's relative balance resolution. Roundoff floor ≈ N·ε·max|ln φ| ≈ 4e-14; the equilibrium solve adds its
ln-fugacity residual, which F5 must register at ≤ 1e-10, two decades under τ_tm (O-2). *Ideal-K closed form:* ln φ_i^V −
d_i = −ln z_i − ln K_i, stationarity W_i = z_i K_i, tm* = 1 − Σ z_i K_i; tm* is strictly convex in W (Hessian
diag(1/W_i)), so the stationary point is global. Example: z = (0.3, 0.7), K = (2.0, 0.8) gives tm*_V = −0.16, tm*_L =
−0.025, inside the two-phase band. *Pure solid* (synthetic fixture: ideal liquid, constant Δh_fus): tm_S =
−(Δh_fus/R)(1/T − 1/T_m) − ln x_w; with Δh_fus = 6009.5 J/mol, T_m = 273.15 K, x_w = 0.95 the root is T_f = 1/(1/T_m − R
ln x_w/Δh_fus) = 267.955 774 920 K, slope 1.0066e-2 K⁻¹ (test constants, not water data). Zero flow: no test,
`not_applicable` reason `zero_flow`. A pure fluid at saturation: exact root enumeration for a cubic EOS. A binary at
VLLE: the near-pure trials find the second liquid. A phase appearing: ι_p crosses 0. The critical region:
`unsupported(near_critical)`. *Indicator domain:* on a boundary the incipient stationary point W* is a minimum with
tm* = 0; where non-degenerate (generic; not at critical points, where W* → x) the implicit-function theorem continues
it to both sides, with ι_p smooth, zero on the boundary and of opposite signs across it, so non-critical crossings are
bracketed (the note's "minimal tm" fell to the trivial solution on the stable side). *Margules fixture (Q5.A6):* u ∝
(√z2, −√z1), λ_min = 1 − 2A z1 z2, c3 = (z1 − z2)/√(z1 z2): c3 ≈ 4δ at A = 2, z1 = ½ + δ; −2/√5 on A = 2.4's spinodal.

### Assertions
- **Q5.A1** *Ideal closed form.* Six SYN-001 states (two below the bubble point, two inside the band, two above the dew
  point): tm*_V = 1 − Σ z_i K_i and tm*_L = 1 − Σ z_i/K_i within 1e-13 absolute (floor ~1e-15); classification matches
  the Rachford–Rice end signs at claim level `exact`; tm*_V takes both signs across the six.
- **Q5.A2** *Pure solid* (synthetic constants above). tm_S(T_f − 0.01 K) < 0 < tm_S(T_f + 0.01 K) (≈ ±1e-4, 3 decades
  outside the band); the implementation's root agrees with 267.955 774 920 K within 1e-9 K (floor ~1e-13 K); claim level
  `exact`.
- **Q5.A3** *Witness recheck.* Every fail carries (W, tm*(W)); the verifier reproduces tm*(W) within 1e-12 absolute and
  below −τ_tm; a witness with one W component perturbed so that tm* > 0 fails the recheck.
- **Q5.A4** *Existing phases.* At each registered converged VLE and LLE state, trials reaching an active phase are
  reported as such and the verdict is pass; each registered unstable feed fails with |tm*_min| ≥ 1e-6 **[gen]**.
- **Q5.A5** *Claim text.* Every pass(local) carries exactly "local search; global stability not established" and the
  trial-set id; no pass(exact) carries it; every unsupported carries a typed reason and never the word pass.
- **Q5.A6** *Near-critical against near-spinodal* **[gen]** (synthetic liquid, g^E/RT = A z1 z2). NC: A = 2, z1 = 0.501,
  λ_min = 4.000 000e-6, c3 = 4.000 008e-3, trials trivial (no split at A = 2) → `unsupported(near_critical)`. NS: A =
  2.4, z1 = 0.295 85, λ_min = 5.066 8e-5, c3 = −0.894 563, inside the binodal (x_b = 0.170 715): fail with a witness,
  and with every trial forced trivial (test double) `unsupported(near_spinodal)`, never `near_critical`. Control: A = 2,
  z1 = 0.3, λ_min = 0.16 → pass. λ_min and c3 match the closed forms within 1e-12 and 1e-4 absolute.
- **Q5.A7** *Classification* (F5's exit, kept). 100 % correct on the registered feeds, and every registered feed has
  |tm*_min| ∉ [1e-9, 1e-7] **[gen]**.
- **Q5.A8** *Inactive-phase invariance.* At each registered procedural point with an inactive candidate, setting its
  labels to 1.0 (test seam) leaves every residual and Jacobian entry bitwise unchanged after signed-zero normalisation,
  all finite, outputs null with `phase_inactive`. Mutation control: a probe row reading LIQUID.2's water fraction
  directly changes under the seam and, with no declared form, is refused `inactive_phase_read`.
- **Q5.A9** *Indicator.* (a) SYN-001, T sweep at fixed (z, P) across the bubble point: ι_V = 1 − Σ z_i K_i within 1e-13
  (floor ~1e-15), changing sign within 1e-8 relative of the generator's closed-form bubble point **[gen]**. (b) Q5.A2's
  fixture: ι = tm_S. (c) On F5's registered LLE and VLE boundary paths, ι is defined at both bracket ends with opposite
  signs, bracketing the flash's boundary within 1e-8 relative in T. (d) At Q5.A6's NC, ι is `indicator_untracked`.
- **Q5.A10** *FLUID roots* (F5; Amendment 2). (a) Q4.A8's method at 101 325 Pa and its T_sat + 5 K, an attempt held on
  the liquid-like root: the closure finds W = x on the vapour-like root with tm* = (g_V − g_L)/(RT) from the method's
  own roots within 1e-12 absolute (floor ~1e-15; |tm*| ≈ Δs_vap·5 K/(RT) ≈ 0.2), fails with that witness, and the next
  opening records `root_switch` and converges on the vapour-like root, count 1; the composition-only triviality rule
  (mutation control) discards the witness and passes. (b) **[gen]** F5 registers at least one single-FLUID state where
  the trials reach two distinct non-trivial minima; both W are recorded and ι equals the lower tm*.
- **Q5.A11** *Steady PI* (F6, E-F6-14; Amendment 4). The sheet method (`docs/derivations/F6-std-seed.md` §2): liquid
  (1, 1, 1) mol/s at 300 K, P_r → `std.heater` (no drop) whose duty is `std.pid`'s `out`; pv the outlet's derived T;
  sp = 320 K; out_min = 0 W. Closed form (sheet cases HTR-L*): T_out = 300 K + Q/(300 W/K). (a) `reverse`, out_max =
  1e4 W: `tracking`, Q = 6000 W, T_out = 320 K. (b) `reverse`, out_max = 3000 W: `tracking` → `saturated_high`, Q =
  3000 W, T_out = 310 K, e = +10 K, notice `controller_saturated`. (c) `direct`, out_max = 3000 W: `tracking` →
  `saturated_high` → `saturated_low`, Q = 0 W, T_out = 300 K, σe = −20 K. (d) `reverse`, out_max = 6000 W: Q = 6000 W
  and T_out = 320 K in whichever regime closes, flagged `near_threshold`. Each `VERIFIED`; T within 3.4e-6 K (τ_T where the
  tracking row decides, τ_E/(ṁ ĉ_p) where the energy row does) and Q within 1.01e-3 W: the certificate tolerances,
  ≥ 7 decades above the solved residuals at registered states (ADR 0007 D2.4). Mutation
  controls: σ's sign flipped closes (b) at `saturated_low` and (c) at `saturated_high`; without the closure condition
  (b) stays at `tracking` with Q = 6000 W > out_max.
- **Q5.A12** *`heat_direction`* (F6, E-F6-18; Amendment 4). The sheet method: two `std.heater`s joined by `heat-v1`,
  both fed liquid (1, 1, 1) mol/s at P_r, the donor's outlet T specified, the connection from donor to receiver;
  closed forms (sheet cases HD-*): Q = 300 W/K·(T_d,in − T_d,out), T_r,out = T_r,in + Q/(300 W/K). (a) Donor 340 → 320
  K, receiver 300 → 320 K: value −40 K, `pass`, not flagged. (b) Donor 300 → 290 K, receiver 320 → 330 K: value +20 K,
  `fail`. (c) Donor 310 → 300 K, receiver 310 → 320 K: value 0, `pass` (equality), not flagged. (d) Donor outlet T =
  its inlet T: |Q| ≤ τ_Q, `not_applicable(no_heat_flow)`. (e) Donor fed (0, 0, 0): `not_applicable(zero_flow)`. (f)
  (b) with the connection declared from receiver to donor (Q < 0 in its variable): value +20 K, `fail`. Values within
  τ_E/(ṁ ĉ_p) = 3.4e-6 K of the closed forms (the sheet's (S) class), result words exact; (c)'s `pass` presumes an
  achieved |r_E|/(ṁ ĉ_p) ≤ τ_T/10 (O-15). Mutation control: ignoring the sign of Q passes (f).
- **Q5.A13** *Index probe* (F7; Amendment 4). Test probe: a rigid vessel V = N v0 holding N = 1000 mol of a synthetic
  liquid with v = v0 [1 + α(T − T0) − κ(P − P0)] and h consistent with it ((∂h/∂T)_P = c_p at P0, (∂h/∂P)_T =
  v − T(∂v/∂T)_P), v0 = 1.8e-5 m³/mol, c_p = 75 J/(mol K), T0 = 300 K, P0 = 1e5 Pa; differential N and U; algebraic
  columns T, P; rows N v − V = 0 and U − N(h − Pv) = 0, initialised at (T0, P0); scales s_T = 100 K, s_P = 1e5 Pa, rows
  by V and N c_p s_T. Then Ĝ = [[α s_T, −κ s_P], [−(1 − P0 v0 α/c_p), (T0 α − P0 κ) v0 s_P/(c_p s_T)]] and, for α = 0,
  rcond₁ = κ s_P / (1 + κ s_P P0 v0/(c_p s_T)) exactly. Registered: (a) α = 0, κ = 4.5e-10 Pa⁻¹: rcond₁ =
  4.499 999 951 4e-5, clean; (b) κ = 3e-13: 2.999 999 999 978e-8, no limitation, `near_threshold`; (c) κ = 3e-14:
  3.0e-9, `dae_index_near_singular` and `near_threshold`; (d) κ = 1e-15: 1.0e-10, the limitation, not flagged;
  (e) α = 2.1e-4 K⁻¹ with v independent of P (κ ≡ 0): structurally index 1, rcond₁ = 3.109 876 266e-7, clean
  (registered because incompressibility alone does not make the block singular: the volume row fixes T, the energy
  row P); (f) α ≡ κ ≡ 0: `dae_index_unsupported` naming the volume row. rcond₁ within 1e-9 relative (`onenormest` is
  exact on 2 × 2, K04 A23's measured ratio 1.000; entries exact to ε). **[gen]**: F7's generator recomputes them.

**Effect on the note.** §2.2.6, §2.2.9: claim levels, witness, trial-set id. F5 exit: τ_tm and the band. §6 Q5:
near-pure trials per component (not "per liquid candidate"), exact levels, witnesses. §8:
`SolutionCertificate.phase_stability` carries claim level, witness and trial-set id. §7 R9 unchanged. Amendment 1: §13.
Amendment 2: §14 (S5; F5 gains Q5.A10).

## Q6. Attribute semantics

### Ruling
- **Q6.R1** Every carried attribute is an extensive flow: additive on mixing, proportional on non-classifying splitting.
  Intensive values (mean size, Mn, λ1/λ0, PDI) are derived, never carried. (The note's invariant, confirmed.)
- **Q6.R2** *No definitional identity among carried variables.* **Partition** attributes (class amounts that sum to a
  parent amount by definition: a PSD as amount or mass per class, copolymer segment flows per segment type, NC proximate
  constituents) are component-scoped and carried *instead of* the parent, which is derived as their fixed-order sum.
  **Non-partition** attributes (extensive quantities that do not sum to the parent by definition: particle number per
  class, chain moments λ0 and λ2, PSD moments μ0–μ3) are carried alongside the parent and may be substream-scoped. λ1
  *is* the polymer's segment amount and is never an attribute. A model relation between carried variables (mass =
  ρ·k_v·μ3) is a unit equation, not an identity, and is allowed. F1 refuses a kind whose index set contains a
  definitional identity (`attribute_redundant(<kind>, <identity>)`).
- **Q6.R3** *Zero flow.* When the parent is exactly zero, every extensive attribute is exactly `+0.0` (an invariant
  producers keep and validation checks; a non-zero attribute on a zero parent is an invalid state). A zero attribute on
  a flowing parent is ordinary. A derived intensive is undefined iff its denominator is exactly zero, never ε-guarded.
  This corrects the note: the attribute is zero, not undefined; only derived values are undefined.
- **Q6.R4** *Grids.* A classed attribute's grid is declared once per substream in the definition and is part of its SHA;
  mixing streams on different grids is refused at validation (`attribute_grid_mismatch`); a change of grid is an
  explicit unit.
- **Q6.R5** A kind may declare admissibility inequalities, division-free with a rounding allowance τ_mono = 1e-12: λ0 ≤
  λ1(1 + τ_mono) (at least one segment per chain; equality at DP 1) and λ1²(1 − τ_mono) ≤ λ0·λ2 (Cauchy–Schwarz; equality
  when monodisperse). A trial violating one beyond the allowance is an invalid trial state, never projected (ADR 0001
  D2.3); within it the state is kept unchanged and PDI or λ1/λ0 may report below 1 by at most τ_mono.

### Rejected alternatives
- **Intensive attributes.** Rejected by the note; confirmed.
- **Carrying parent and partition both.** Two descriptions (ADR 0001 D2.5); a crystallizer whose population balance is
  not exactly mass-conserving would emit an inconsistent stream.
- **A substream-scoped partition over several components.** One identity against the component amounts, and closed under
  mixing only if all classes share one composition (an assumption, not an invariant); written instead as a
  component-scoped partition.
- **Grids per unit or per stream.** Mixing would need rebinning, which is not exact.

### Argument and limiting cases
PSD: number per class (non-partition) and mass per class (partition) are both additive on a fixed grid. Polymers: λ0 and
λ2 add under mixing (moments of a union are sums of moments); λ1 is the segment amount; Mn = M_seg·λ1/λ0 is derived; at
zero flow λ0 = λ2 = +0.0 and Mn is undefined. NC constituents: proximate and ultimate analyses partition one mass, so
only one may be carried as a partition; the other needs an independent index set ("by difference" entries derived, never
carried), declared by X20 and checked by F1. A dormant substream inside a flowing stream: Q8.R6. *Moment allowance:*
the admissible set is a convex cone, left only by rounding. On 4·10⁴ synthetic monodisperse states (1–8-inlet mixers,
splits) the worst deficit (λ1² − λ0λ2)/λ1² was 3.6ε, 26 % failing the strict test (scratch measurement, not shipped);
the bound (4k + 1)ε, k ≤ 9, is 8.2e-15: τ_mono is 2 decades above it, 3 below a 1e-9 violation; recycles scale it (O-9).

### Assertions
- **Q6.A1** *Conservation* (F2's probe threshold, kept). Through probe mixers (≤ 8 inlets) and splitters, the relative
  conservation residual of every carried amount and attribute is ≤ 1e-14. Worst-case floor 7ε ≈ 1.6e-15, margin ≥ 6×; F2
  measures it and amends if the margin falls below 3×. Catches a dropped class or a wrong split fraction (≥ 1e-3).
- **Q6.A2** *Redundancy.* Registering `probe.partition` together with its parent's amount, or a polymer kind with λ1, is
  refused `attribute_redundant`; the partition alone is admitted, and its fixed-order parent sum is bitwise
  reproducible.
- **Q6.A3** *Zero flow.* With a dormant parent every attribute stays `+0.0` bitwise through mixer, splitter and
  zero-flow forms, and derived intensives are null with reason `zero_flow`; non-vanishing control: a flowing parent with
  one zero class has defined intensives.
- **Q6.A4** *Grids.* A grid mismatch is refused; the same grid is admitted.
- **Q6.A5** *Inequality* **[gen]**. Monodisperse feeds (DP ∈ {1, 2, 3, 7, 100, 1e4, 1e6}, amounts such as 0.1 and 1/3),
  their 8-inlet probe mixtures and splits are admitted, at least one failing the strict test, none with a deficit above
  τ_mono/100; trials with λ0λ2 = λ1²(1 − 1e-9), λ0 = λ1(1 + 1e-9) or λ0 = λ1(1 + 1e-3) are invalid, stored unclipped.

Probes: `probe.moments` (component-scoped, non-partition); `probe.classes` (substream-scoped, non-partition counts on a
grid); `probe.partition` (new: component-scoped partition on a grid).

**Effect on the note.** §2.1.3: zero-flow wording; partition rule. §2.1.4: λ1 not carried; segment flows a partition. F2
exit: the third probe. §6 Q6: "yes", with Q6.R2. §7 R2 unchanged.

## Q7. Amount bases

### Ruling
- **Q7.R1** Each component has one amount basis, from its record: `mol` (default: every existing component, electrolytes
  on their groups, pseudo-components); `segment_mol` (polymers: amount of repeat units); `kg` (nonconventional
  components).
- **Q7.R2** *Meaning per unit amount.* M_c = mass per unit amount: kg/mol; kg per mol of segments (per segment type for
  copolymers); for `kg` the identity, with no `molar_mass` field. h_c, s_c, μ_c and ∂/∂n_c are per unit amount on that
  basis (J/mol, J/segment-mol, J/kg), and so are a record's Δf h° and s°. The element matrix A_ec is mol of element per
  unit amount (per kg for NC components, from the ultimate analysis).
- **Q7.R3** *Kinds.* `mol` and `segment_mol` share the SI dimension but have distinct quantity kinds (`molar_flow`,
  `segment_molar_flow`), as ADR 0001 D1.3 does for `temperature` and `temperature_difference`; `kg` amounts have kind
  `mass_flow`. Nothing sums across kinds except ṁ (through M_c) and a method's declared composition map. The intensive
  composition common to every basis is the mass fraction.
- **Q7.R4** Bounds and dormancy do not depend on the basis: every amount ≥ 0; dormant iff every amount is exactly zero.
- **Q7.R5** A mass input for a `mol` component is converted at validation (ADR 0001 D1.4, unchanged); a molar input for
  a `kg` component is refused (`amount_basis_mismatch(<component>)`).

### Rejected alternatives
- **`mol` for polymers with a nominal chain molar mass.** The chain count is λ0, which reactions change; a constant M
  per mol of polymer is false after any change of chain length.
- **`mol` for NC components with a nominal M.** Invents a molar mass where none has a meaning (coal).
- **One kind for `mol` and `segment_mol`.** A total-molar-flow sum would add molecules and segments silently.
- **A basis per substream.** An electrolyte crystal (`mol`) and a coal (`kg`) may share a solid substream.

### Argument and limiting cases
Reactions across bases: element balance Σ ν_c A_ec = 0 exactly; mass Σ ν_c M_c = 0 to roundoff when M derives from one
set of atomic weights. Polymerisation: `mol` monomer → `segment_mol` (M_seg = M_mon for an addition polymer). NC
combustion: a `kg` coal with `mol` O2. A homopolymer has one segment type and constant M; a copolymer uses a
segment-type partition (Q6), ṁ = Σ_t M_t n_t. A polymer solution combines `mol` solvent and `segment_mol` polymer
through the method's composition map (segment fractions).

### Assertions
- **Q7.A1** *Kinds.* A v2 document with a row summing `molar_flow` and `segment_molar_flow` outside a method map is
  refused; the same quantities through a declared method map are admitted.
- **Q7.A2** *Mass.* For every v2 probe stream, ṁ from the layout equals an independent fixed-order sum, bitwise.
- **Q7.A3** *Reaction consistency* (F3 validation) **[gen]**. For every registered reaction, Σ ν A_ec = 0 exactly
  (rational) and |Σ ν M| ≤ 4ε·Σ|ν M|; a record set inconsistent by 1e-9 relative in M is reported
  `molar_mass_inconsistent(<reaction>)` in the validation class (Q9), which catches mixed atomic-weight sources. Q3.R7's
  check holds on every registered basis; one ion shifted by the electron mass (9.4e-6 relative, Q3.A2 (b)) is reported.
- **Q7.A4** *Dimensions.* The vocabulary item h has dimension (2,0,−2,0,0,0,0) for a `kg` component and
  (2,1,−2,0,−1,0,0) for a `mol` one; wiring the first into a molar row is refused at validation.
- **Q7.A5** *Input.* A molar input for a `kg` component is refused with the typed code.

**Effect on the note.** §2.1.1: `amount_basis` entries. §2.1.4: polymer M per segment type. §2.3.1 and the F3 record
schema: per-basis fields and per-amount element matrix. §8: the ComponentRecord row.

## Q8. Equilibrium solids against solid substreams

### Ruling
- **Q8.R1** *The criterion is kinetic, not chemical.* A solid whose amount is fixed at each state point by phase
  equilibrium is a phase candidate of `mixed` (`SOLID.<component>`, `SOLID.<model>`): salts, ice, CO2 freeze-out, wax,
  gas hydrates. A solid whose amount is fixed by rates or transfer rows is a component of a `solid` (or
  `nonconventional`) substream: crystals with a PSD, catalyst, inert solids, any solid carrying attributes.
- **Q8.R2** *Exclusive role.* Within one definition, a solid-substream component is not a solid candidate of `mixed`
  nor a component confined to one (Q8.R7), though it may be dissolved in `mixed`; otherwise
  `solid_role_conflict(<component>)`. A supersaturated liquor beside kinetic crystals must be able to stay supersaturated.
- **Q8.R3** Material moves between substreams only through unit rows (crystallizer, dissolver, reactor); no state point,
  flash or connection moves it.
- **Q8.R4** Equilibrium phases carry no attributes. Equilibrium-solid amounts are reconstructed at each state point (ADR
  0001 D2.5) and carried only as `mixed`'s component amounts.
- **Q8.R5** Substreams share `ĥ`, `P` and hence `T` on a connection (Q1.R1); a temperature difference inside a unit (gas
  against solid in a bed) stays internal.
- **Q8.R6** *Dormancy per substream.* A substream may be dormant in a flowing stream: its attributes are `+0.0`, its
  intensives undefined, and the stream's `T` is fixed by the flowing substreams.
- **Q8.R7** *Adsorption* (PrISMa): both roles, by Q8.R1's criterion. *Equilibrium:* the adsorbed phase is a
  `SOLID.<isotherm model>` candidate of `mixed` with the isotherm as phase model, and the sorbent a `mixed` component
  **confined** to it (every other phase model gives it exactly 0). Its activity is no stability decision: active iff the
  carrier is not dormant (Q1.R4), so it changes only with that dormancy and needs no trial; the isotherm fixes its
  adsorbate amounts; no attributes (Q8.R4). *Kinetic:* sorbent and adsorbed amounts are `solid`-substream components
  moved by rate rows (linear driving force) under Q8.R1–R3; a sorbent with attributes (a PSD) takes this role.

### Rejected alternatives
- **All solids as substreams.** Freeze-out and salt solubility would need a kinetic unit wherever a phase may appear;
  regime discovery (FB-04 (2)) would be lost.
- **All solids as phases.** PSDs, inert solids and a supersaturated crystallizer become impossible.
- **Both roles for one component.** The thermodynamic driving force would be counted twice.
- **A temperature per substream on connections.** No planned package needs it (note §2.1.2); a later definition can add
  it.

### Argument and limiting cases
Ice–water at T_m (C = 1, π = 2) and a binary eutectic (C = 2, π = 3) are degenerate in T; `ĥ` resolves both (Q1). A salt
at saturation: its amount reaches 0 and it leaves through `BOUND_BLOCKED` on the watched phase amount, with an exact
indicator tm_S (Q5). A dry solids stream (`mixed` dormant) and a clear liquor (`solid` dormant) are ordinary. At a
method boundary where the downstream method lacks the producer's solid candidate, the stream is interpreted without it
and the boundary report says so (Q3.R5 as amended by Amendment 2: admitted, `solid_candidate_dropped`).

### Assertions
- **Q8.A1** *Role.* A role conflict is refused at validation; a component dissolved in `mixed` with its crystals in
  `solid` is admitted.
- **Q8.A2** *Inertness.* A v2 heater without transfer rows on a supersaturated liquor plus solid-substream crystals
  leaves the solid substream's amounts and attributes bitwise unchanged, and its `mixed` state point has no SOLID
  candidate for that component.
- **Q8.A3** *Ice–water lever rule* (synthetic fusion model, h_ice = h_L − Δh_fus at T_m). Pure water at fixed P, `ĥ =
  ĥ_L(T_m) − f·Δĥ_fus`, f ∈ {0.25, 0.75}: T = T_m within 1e-9 K, ice mass fraction f within 1e-10 (floor as Q1.A1).
- **Q8.A4** *Substream dormancy.* `mixed` dormant, `solid` flowing: T is defined and equals the solid model's T(ĥ)
  within 1e-9 K; the reverse takes T from `mixed`; the dormant substream's attributes are `+0.0`.
- **Q8.A5** *Salt disappearance.* On a registered dilution path the salt amount reaches `+0.0` at an attempt boundary
  with cause `BOUND_BLOCKED`, and tm_S changes sign inside the bracket within F5's 1e-8 relative in T.
- **Q8.A6** An attribute targeting an equilibrium phase is refused at validation.
- **Q8.A7** *Adsorption* (synthetic Langmuir q = q_max K p/(1 + K p), q_max = 5 mol/kg, K = 1e-5 Pa⁻¹, pure CO2, 2 kg
  sorbent, 10 mol CO2). P = 1e5 Pa: q = 2.5 mol/kg, 5 mol adsorbed; P = 1e4 Pa: q = 0.454 545 454 545 454 5 mol/kg; within
  1e-12 relative (equilibrium tolerance, not the few-ε closed form, dominates). A dormant sorbent: phase inactive, no
  stability decision; also in a `solid` substream: `solid_role_conflict`; kinetic heater: adsorbed amounts bitwise kept.

**Effect on the note.** §2.1.2: exclusive role; dormancy per substream. §2.2: solid candidates are tested exactly (Q5);
confined adsorbed phases (Q8.R7). §6 Q8: default confirmed, with Q8.R2, Q8.R6 and Q8.R7.

## Q9. Record kinds, record identity and run evidence

### Ruling
- **Q9.R1** *Record types* in the F3 store: `component`, `parameter_set` (binary or multicomponent), `assay`; one
  identity rule for all.
- **Q9.R2** *Identity* = SHA-256 of the ADR 0002 canonical record minus a **closed, schema-declared volatile set**:
  retrieval timestamp, request and response noise (headers, query order, mirror URL), fetch duration, local paths,
  adapter software version, host. Everything else is identity: values, units, correlation form and coefficients,
  validity ranges, uncertainty, entry provenance, source id and version, the source's stated licence, transformation
  descriptions, the input hashes of fitted and generated entries, the raw payload's hash.
- **Q9.R3** *Rights.* The project's rights assessment (R-706 rows: permitted, unknown, refused) is not in the record but
  in a rights register keyed by source and record SHA, so vetting never moves a record's identity or a data lock.
- **Q9.R4** *Provenance on two axes, per property entry* (not per record): **origin** ∈ {measured, computed, estimated,
  synthetic} and **derivation** ∈ {direct, fitted, generated}. A fitted or generated entry carries the origin set of its
  inputs (a correlation fitted to group-contribution estimates: origin {estimated}, derivation fitted). Every origin is
  admitted.
- **Q9.R5** *Fitted and generated records* are produced once and stored; data locks reference the stored SHA; replay
  uses the stored record and never regenerates. Regeneration is a separate operation compared under the numerical policy
  (R2), never by SHA.
- **Q9.R6** *Run evidence.* The run report's **validation class** lists each (component, entry) the composition read:
  origin, derivation, source id and version, record SHA, uncertainty when given, and whether the converged state lies
  inside the entry's validity range (`extrapolated(<component>, <entry>, <variable>)` otherwise; trial states do not
  count; a final state within 1e-9 relative of a bound is flagged `near_threshold`). None of this enters the
  verification class, and no data origin changes a verification verdict (D14).
- **Q9.R7** *Identity without content.* Identity is computable as a SHA reference, so a bundle may reference a record
  its rights forbid it to carry; replay without that record runs in mode `inspected_archived_results` with verdict
  `NOT_RUN` (ADR 0007 D4), never as a silent pass.
- **Q9.R8** *Grazing events under `forced_replay`* (Amendment 4, SQ-F8-1; ADR 0067 D8). An event disagreement under
  `forced_replay` (a recorded event the replay detects in another step or not at all, an event the record lacks, or a
  different grouping, Q1.R10) is *near threshold* iff the replay's own event function is within τ_g of zero at the
  disputed time: at the recorded located time for a recorded event; the smaller |g| of the two step ends for an event
  only the replay detects; for a grouping, Q1.R10's band on |t − t*|. τ_g = 10 × the floor ADR 0007 D2.2 registers for
  the function's output kind (F7 registers one for every kind an event function may have, D2.3; an event of an
  unregistered kind is refused at scenario validation `event_floor_unregistered(<event>, <kind>)`). A near-threshold
  disagreement is resolved by imposing the record (the event fires, or not, in the recorded step at the recorded t*,
  grouped as recorded) and the comparison continues; with every other field agreeing the verdict is `MATCH` with
  `verdict_changed_near_threshold(<seq>)` (ADR 0007 D2.4). Any other disagreement, and a corrector failure on a
  recorded step, is `forced_replay_divergence(<seq>)`, verdict `MISMATCH`. The default τ_g (the location tolerance, a
  time) is not adopted: g is not a time, and a slow crossing turns a roundoff difference in g into a time difference
  larger than any location tolerance.

### Rejected alternatives
- **One five-value kind (the default).** "fitted" hides whether the data were measured or estimated.
- **Rights status inside identity.** Every vetting would move every data lock.
- **Path identity.** Already rejected in the note.
- **Regenerating generated records at replay.** Last-bit differences across platforms would change SHAs.
- **Ranking origins.** A value judgement: an ideal-gas c_p from statistical mechanics often beats calorimetry.
- **Refusing synthetic or estimated data.** R-924: report it instead.

### Argument and limiting cases
Identity must follow content and claimed provenance, and nothing else. A closed volatile set makes "what moves the SHA"
a schema fact instead of an importer's choice, so it is testable (Q9.A1). The same values from two sources are two
records by design (different provenance and stated licence); a re-fetch that returns identical content is the same
record; a source that changes values without changing its version string yields a new SHA, because content moved.
Keeping data origin out of the verification class is CLAUDE.md's separation of numerical verification from empirical
validation: a certificate verifies the equations of the pinned model (D14), and a synthetic record is a correct model
of nothing real, which only the validation class can say. Extrapolation is judged at the converged state only, because
trial states are not results (ADR 0001 D2.3).

### Assertions
- **Q9.A1** *Volatile closure* **[gen]** (property test over the schema's field list). Changing any volatile field
  leaves the SHA unchanged; changing any other field (one ulp of a value, the source version, the stated licence, an
  origin, a validity bound) changes it.
- **Q9.A2** *Rights.* A changed assessment leaves the record SHA and the data-lock SHA unchanged.
- **Q9.A3** *Canonicalisation.* One record imported in two field orders, and with −0.0 against +0.0, has one SHA.
- **Q9.A4** *Non-interference (D14).* Flipping one entry's origin from measured to synthetic changes the validation
  class and leaves every R0 field of the certificate bitwise identical.
- **Q9.A5** *Coverage.* Every (component, entry) the composition read appears exactly once in the validation class and
  never in the verification class.
- **Q9.A6** *Extrapolation.* A converged state 10 K outside a correlation's range lists `extrapolated(…)`; inside, it
  lists nothing; an iterate outside with a final state inside lists nothing.
- **Q9.A7** *Fit origin.* A correlation fitted to estimated points reports origin {estimated}, derivation fitted.
- **Q9.A8** *Missing record.* Replay with a referenced record absent runs in `inspected_archived_results` with
  `NOT_RUN`.
- **Q9.A9** *Grazing replay* (TX with F8-WO7; Amendment 4). Q1.A13's probe (h = 0.125 s, x_k = k/8) with one event
  g = x − 1 + u, rising, x dimensionless with registered floor 1e-12 (τ_g = 1e-11), u a constant set through a
  test-only seam on one side. (a) Record u = −1e-13 (crossing in (1, 1.125]), replay u = +1e-13 (crossing in
  (0.875, 1]): `MATCH` with `verdict_changed_near_threshold`, the event imposed in the recorded step at the recorded t*,
  every later step bitwise equal. (b) Replay u = +1e-3: `forced_replay_divergence`, `MISMATCH`. (c) g = (x − 1)² − u,
  direction either: record u = +1e-20 (events at 1 ∓ 1e-10), replay u = −1e-20 (none): `MATCH` flagged, both events
  imposed. (d) Q1.A13 (d)'s pair with the replay's b moved by 1e-13 s: `MATCH` flagged, grouped as recorded; moved by
  1e-6 s: `MISMATCH`. Mutation control: τ_g taken as the location tolerance in seconds (the default) makes (a)
  `MISMATCH`.

**Effect on the note.** §2.3.1: two provenance axes, record types, rights register, volatile set. F3 scope and exit:
Q9.A1–A3. §8: the ComponentRecord row. ADR-F8: bundles may reference records they do not carry.

## 10. Findings: ADR and frozen-interface changes these rulings need

Not written here; each belongs to the ADR named, and none moves a released case.

1. **ADR 0001 D1.3 (frozen kinds), in ADR-F2.** Add `specific_enthalpy` (J/kg), `specific_entropy` (J/(kg K)),
   `segment_molar_flow`, `segment_molar_mass` (Q1, Q7).
2. **ADR 0001 D2 and D3, in ADR-F2.** The general definition and Q1.R4 for v2; D3.1's "T and P remain labels" reads "the
   thermal coordinate and P" in v2. (The note already plans "amends ADR 0001 D2".)
3. **ADR 0001 D5.2, in ADR-F4.** D5.2's "no implicit reference shift is ever applied" becomes, for v2, explicit recorded
   shifts to the flowsheet convention applied by the composed method; `ELEMENTAL-ref-v1` joins D5's list and
   `interfaces-frozen.md` §3.
4. **ADR 0011 D2.** The reaction-consistent set gains `ELEMENTAL-ref-v1`, and v2 reaction consistency becomes per
   component (Q2.R4); D2 itself requires a new decision naming the datum.
5. **ADR 0005, in ADR-F5.** The count lattice over interchangeable slots (Q4.R2) and the `relabel` record.
6. **ADR 0012 D7/D8 and ADR 0013.** Not applicable to `ĥ` definitions; unchanged for v1.
7. **`SolutionCertificate`, in ADR-F5.** `phase_stability` gains claim level, witness and trial-set id.
8. **ADR 0008 A1.1 U1/U1b, in ADR-F7** (Amendment 2). U1 admits only `U…` and `N…_i` as `holdup_balance` symbols; Q1.R9's
   `angular_momentum` fails it. U1 becomes a check on registered holdup kinds (amount, internal energy, Q1.R9's kinds),
   still never an enthalpy; U–H.8's kind stays outside (Q-A5).

No ruling breaks a foundation's premise. Q6.R2 changes F2's probe design (a third probe) and Q3.R1 changes the meaning
of F2's `species_basis` field; both are inside F2's scope.

## 11. Open questions, each with a recommended default

| # | Question | Kind | What settles it | Default |
| --- | --- | --- | --- | --- |
| O-1 | PH-solver tolerance at elemental magnitudes (Q1.A1's margin) | fact | F4 measures the achieved `ĥ` residual on the IAPWS-95 probes | 1e-12 relative |
| O-2 | τ_tm against F5's equilibrium noise | fact | max \|tm*\| of active phases used as trials at the registered converged states | τ_tm = 1e-8 if the noise is ≤ 1e-10; otherwise amend |
| O-3 | Single-phase label flips for one-fluid-model methods on supercritical paths (Q4.R6) | fact | extra attempts on F5's registered supercritical paths | Closed by Amendment 2: `single` methods use FLUID (Q4.R6, Q4.A9); legacy providers keep today's behaviour |
| O-4 | τ_spin = 1e-4, τ_crit = 1e-2 (Q5.R4) | fact | λ_min(B) and c3 against distance to the critical point on one registered EOS system | 1e-4 and 1e-2 |
| O-5 | τ_comp = 1e-6 | fact | cross-platform agreement of converged x on the X07a legs | 1e-6 |
| O-6 | Water as default first key (Q4.R3) | Frank's preference | — | water first; alternative: component order only |
| O-7 | Mass-specific `ĥ` as the raw coordinate in state documents | Frank's preference | — | mass-specific; reports show specific and molar h |
| O-8 | Cost of N near-pure trials for large N (assays) | fact | F5 times N = 50 | all components; a reduced set keeps claim level `local` |
| O-9 | τ_mono = 1e-12 against the moment rounding floor (Q6.R5) | fact | F2's worst relative deficit on monodisperse probe streams, a recycle of loop gain 100 included | 1e-12; amend if the margin falls below 10× |
| O-10 | Drain-defect bound and trajectory tolerances (Q1.A11, A12) | fact | F7's measured defect and T error on the probe at its default integrator tolerances | 1e-8·m₀, 1e-10 relative; amend if a margin falls below 10× |
| O-11 | Default identification rule for `character` (Q4.R6) | Frank's preference | — | Venkatarathnam and Oellrich's phase identification parameter; reported, and since Amendment 4 it decides the outlet of a lone fluid phase (Q4.R9); since Amendment 5 also whether each of several coexisting fluid phases leaves by `vapor` (Q4.R13) and which FLUID phases a v2 stream table counts as vapour (Q4.R10) |
| O-12 | CoolProp's anchor evaluation at (T°, δ°) for the 118 in-box fluids, and Q2.A11 (b)'s answered-phase control (Amendment 3) | fact | one run of Q2.A11 (b) on a machine with the coolprop extra | all 118 admitted, every control above 2 ulp; a fluid that fails is refused with its cause and listed here by amendment (rule 6), never dropped from the assertion |
| O-13 | Q2.A11 (a)'s floors on aarch64 (Amendment 3) | fact | the four comparisons on the CI's arm runner | 1e-12 and 1e-10 relative; amend if a margin falls below 100× |
| O-14 | τ_char = τ_ρ = 1e-6 (Q4.R9; Amendment 4) | fact | cross-platform agreement of the identification parameter q and of ln ρ at F5's and F6's registered FLUID states on the X07a legs | 1e-6; amend if a margin falls below 10× |
| O-15 | τ_hd = the `temperature` tolerance against the derived-T floor (Q5.R10; Amendment 4) | fact | E-F6-18's achieved max \|r_E\|/(ṁ ĉ_p) per side at its probes | τ_T; add that term to τ_hd if it exceeds τ_T/10 |
| O-16 | τ_idx = 1e-8 (Q5.R11; Amendment 4) | fact | rcond₁ of Ĝ at TX's and X25's registered dynamic cases | 1e-8; re-argue with the first supported case below 1e-7 |
| O-17 | c_loc = 1e-14, τ_ev = 10 τ_loc (Q1.R10; Amendment 4) | fact | the achieved location error on Q1.A13 with the reference integrator and with TX's BDF | as stated; amend if a located time errs by more than τ_loc/10 |
| O-18 | τ_g = 10 × the kind's floor (Q9.R8; Amendment 4) | fact | max \|Δg\| at recorded step ends between the CI's two platforms on TX's registered transients under `forced_replay` | as stated; amend if a measured \|Δg\| exceeds τ_g/10 |
| O-19 | τ_β = 1e-8 (Q4.R12 (b)), Q4.A15 (a)'s 64 ε, and the rounding tolerances 4(C + 1) ε·vf (Q4.A13 (d)) and 8 ε·x_c (§17 N9) (Amendment 5) | fact | Q4.A15 (e)'s recorded maxima of c·ε_adm (SYN-001) and τ_dew/x^L_NH3 (PR-C1) over the ST corpus and its flagged count; Q4.A15 (a)'s achieved \|ΔH − closed form\|/tolerance; the corpus maxima of \|vf_mass − vf_molar\|/(ε·vf_molar) and \|w_c − x_c\|/(ε·x_c) | as stated; amend τ_β if a maximum exceeds τ_β/10 or a registered stream outside every verifier band is flagged; amend a rounding tolerance if its achieved ratio exceeds a quarter (64 ε) or a half (the others) of it |
| O-20 | A listed SOLID phase in the vapour fraction's denominator (Q4.R10 (e); v2; Amendment 5) | Frank's preference (F4 applies it) | — | counted: the vapour fraction is the vapour share of the substream; a fluid-only share can be added later as an additive member |
| O-21 | The probes' preconditions marked [pre] in Q1.A14, Q1.A15, Q2.A13, Q4.A13–A15 (Amendment 5) | fact | ST WO-1's first test run | each holds; a failed [pre] fails its assertion, and this document is amended with a replacement state (rule 6), never skipped |

[zotero], cited not fetched: Michelsen (1982), *Fluid Phase Equilib.* 9 (TPD; stability matrix); Michelsen and Mollerup
(2007), ch. 9–10 and ch. 12 (critical points); Heidemann and Khalil (1980), *AIChE J.* (criticality cubic form);
Venkatarathnam and Oellrich (2011), phase identification; CODATA key values for Δf h°(H2O, l and g); the ideal-gas
Δf h° of Br2. None is an expectation here.

## 12. Edits to the note (`target-architecture.md`)

- **§2.1.1** (definition document): `thermal_coordinate: T|h` → `T|h_mass`, h_mass in J/kg (Q1.R1); `species_basis:
  apparent|true` → `conserved_basis: {groups, A, R_ref}` with presets `apparent`, `true` (Q3.R1–R2); add the dormancy
  and label rule (Q1.R4).
- **§2.1.2:** exclusive solid role; dormancy per substream (Q8.R2, R6).
- **§2.1.3:** "undefined when its parent flow is exactly zero" → "exactly +0.0 when its parent is exactly zero; derived
  intensives undefined" (Q6.R3); add the partition rule (Q6.R2).
- **§2.1.4:** λ1 not carried; segment flows a partition; polymer M per segment type (Q6, Q7).
- **§2.1.5:** phase id as a triple with an injective rendering (Q4.R1).
- **§2.2.2–2.2.3:** prefix rule and count lattice (Q4.R2). **§2.2.6, §2.2.9:** claim levels, witness, trial set
  (Q5.R2–R4). **§2.2.8:** the conserved-basis slot is the Q3 object (Q3.R6).
- **§2.3.1:** provenance axes, record types, volatile set, rights register (Q9). **§2.3.6:** `ELEMENTAL-ref-v1` with
  anchors, entropy datum, component datum (Q2.R1–R5). **§2.3 "ADRs":** ADR-F4 also amends ADR 0001 D5.2 (§10 item 3).
- **F2 exit:** add Q1.A5 and the third probe `probe.partition` (Q6). **F4 exit:** "Σν·h_shifted … within 1e-10 relative"
  → Q2.A2. **F5 exit:** classification at τ_tm = 1e-8, band [1e-9, 1e-7] (Q5.R3).
- **§6 Q1:** "h is strictly increasing in T" → "T is a continuous, non-decreasing function of `ĥ`, and the state is a
  single-valued function of `(n, ĥ, P)`; `ĥ` is not a function of T where π = C+1"; the enthalpy is per unit mass. **§6
  Q3–Q6, Q9:** defaults replaced by the rulings above.
- **§7 R4:** decided (Q1), mitigated by Q1.R3.
- **§8:** `ComponentRecord` row adds amount basis, anchor and provenance axes; `SolutionCertificate` row adds claim
  level and witness.
- Amendments 1 to 5 add the edits listed per finding or item in §13 to §17.

## 13. Amendment 1 (2026-11-02)

Brief: `docs/roadmap/brief-specifier-rulings-amendment.md`; findings: `docs/roadmap/review-roadmap.md` §2. Edits are in
place; existing clause numbers are kept, new clauses appended. The last column lists the edits the architect makes.

| Finding | Ruling (reviewer's fix?) | Clauses | Assertions | Edits to `target-architecture.md` |
| --- | --- | --- | --- | --- |
| S3 | Adopted, generalised: an opening re-seeds a reactivated stream's `ĥ` from its producer's causal evaluation, else a TP evaluation at a declared or inlet T, else refuses typed; the label value stays | Q1.R6 new; Q1 argument 4 corrected | Q1.A9 new | §2.2.5, §2.4: openings re-seed (Q1.R6); F6's `UnitModel` v2 declares whether a unit has a causal outlet evaluation; F6 exit gains Q1.A9 |
| S4 | Adopted with a change: inactive outputs are exact labels with zero derivatives (no row reads them, so evaluating phase models at incipient compositions would cost every call and risk their domain); the incipient composition is the tracked W_p in the stability record; the indicator is tm*(W_p) with a stated domain | Q5.R7, Q5.R8 new; Q5 argument | Q5.A8, Q5.A9 new | §2.2.1: Q5.R7; §2.2.6: `StabilityReport` carries each W_p and ι_p; §2.2.7: "minimal tm of each inactive candidate" → ι_p (Q5.R8) with its domain; F5 exit, last clause → Q5.A9 (c) |
| S9 | Adopted: R holds the dissolution once SOLID.NaCl is a candidate; the MEA case argued by dimension; M_g defined by Aᵀ M_g + μ z = M with a species check | Q3 argument; Q3.R7 new | Q3.A2 rewritten (R per case); Q7.A3 extended | §2.1.1, §2.2.8: the conserved-basis object carries M_g (Q3.R7) |
| S10 | Adopted with a wider allowance: τ_mono = 1e-12, not 8ε, which the worst case after one 8-inlet mixer (37ε) exceeds | Q6.R5 rewritten; Q6 argument; O-9 new | Q6.A5 rewritten | none |
| N5 | Reviewer's option adopted: equilibrium as `SOLID.<isotherm>` with a confined sorbent; kinetics as `solid`-substream loading with rate rows | Q8.R7 new; Q8.R2, Q4.R1 extended | Q8.A7 new | §2.1.2, §2.2: confined adsorbed phases; §7 O3 and A3: PrISMa's equilibrium part is Q8.R7's first role |
| N6 | Adopted: a declared anchor bridge through a record datum, reported; refusal only without the datum | Q2.R2 amended; Q2.R8 new; Q2 rejected alternatives | Q2.A8 new | §2.3.6: the bridge and `anchor_bridged` |
| N7 | Adopted: exact lexicographic order, flags attached afterwards | Q4.R3, Q4.R5 rewritten | Q4.A4 rewritten | §2.2.2: exact order with flags |
| N8 | Separated, not just renamed: `near_critical` needs λ_min and the cubic form c3 both small, else `near_spinodal`; indistinguishable coexisting phases are `near_critical` | Q5.R4 unsupported reasons; Q4.R5; Q5 argument; O-4 extended | Q5.A6 rewritten | §2.2.9, §8: both reasons in `SolutionCertificate.phase_stability` |
| N10 | Confirmed, extended: non-partition attributes have holdups too; not all are conserved, all accumulate with constant 0/1 coefficients | Q1.R7 new | Q1.A10 new | §2.5.2: "(component amounts, internal energy)" → Q1.R7's list; F7 exit gains Q1.A10 |

**New findings, listed and not fixed.**
- **A1-a.** Q8's argument admits a downstream method without the producer's salt candidate (R′ = ∅ ⊊ R, same groups,
  b′ = b), which Q3.R5 and Q3.A5 refuse; the condition belongs on the invariants (b′ = C b), not R′ ⊇ R. ADR-F2.
- **A1-b.** Q2.R2's anchor depends on the method set: an added `ig`-capable method re-anchors an `l` component (every
  stored `ĥ` moves) and sends a record with only Δf h°(l) to Q2.R4's datum; with Q2.R8 the record could fix it. ADR-F4.
- Both are ruled by Amendment 2 (§14).

**Not established by Amendment 1.** Its numbers are closed forms, synthetic constants or the in-repository water record;
τ_mono's floor is a scratch measurement, τ_crit and c3's accuracy are unmeasured on an EOS (O-4, O-9); nothing has run.

## 14. Amendment 2 (2026-11-05)

Brief: `docs/roadmap/brief-specifier-w1-open-items.md`; items: the note's §3 open items, gating ADR-F2, F4, F5 and F7.
Edits are in place; existing clause numbers are kept, new clauses appended. The last column lists the architect's edits
to `target-architecture.md` and what the gated ADR adopts verbatim.

| Item | Ruling (default adopted?) | Clauses | Assertions (exit) | Edits to the note; the ADR |
| --- | --- | --- | --- | --- |
| A1-a (ADR-F2) | Adopted, made exact: admitted iff an integer C solves C A = A′Π, Π sending each producer species the consumer lacks to shared species modulo R; R′ ⊇ R sufficient, not necessary; every dropped species reported | Q3.R5 rewritten; Q8 argument (pointer) | Q3.A5 rewritten (F4); Q3.A6 new **[gen]** (F2) | §3 F2: delete the open item; F2 exit: "Also Q3.A1–A3" → "Also Q3.A1–A3, A6". §2.3.8: "(ii) the downstream invariants are an image of the upstream ones (Q3.R5; A1-a open); and (iii) a solid candidate the downstream method lacks is reported (Q8 argument; A1-a)" → "(ii) Q3.R5's condition C A = A′Π holds and the consumer evaluates b′ = C b; and (iii) each producer species the consumer lacks is reported (`solid_candidate_dropped`, `species_dropped`)". F4 exit, refusals bullet: add Q3.A5. §6: drop the A1-a row; §7 R13: ruled. ADR-F2 adopts Q3.R5 and Q3.A6; ADR-F4 cites Q3.R5 and adopts Q3.A5 |
| A1-b (ADR-F4) | Adopted: the anchor is a record field set by a fixed order; a record's formation entries in two phases are a bridge datum | Q2.R2 rewritten; Q2.R4, R8 extended | Q2.A9 new (F4) | §2.3.6: "`l` otherwise (Q2.R2; A1-b open, §6)" → "chosen from the record alone: `aq` if charged, else the first of `ig`, `aq`, `l`, `s:<form>` with formation data; adding a method never re-anchors (Q2.R2)"; after "bridged through a record datum" add "or the difference of the record's formation entries (Q2.R8)". §3 F4: delete the open item; F4 exit: "Q2.A1–A8" → "Q2.A1–A9". §8 `ComponentRecord`: the anchor is an identity field. §6: drop the row; §7 R14: ruled. ADR-F4 adopts Q2.R2, R4, R8 and Q2.A9 |
| S5 (ADR-F5; rendering in ADR-F2) | Adopted, with the precisions it forces: v̂ joins FLUID's order key and indistinguishability test; triviality looks at the root; a FLUID slot keeps its root within an attempt (`root_switch`); one W per incipient minimum. Legacy providers stay `split` (decision equivalence). Confinement by declared support | Q4.R1, R3, R5, R7 amended; Q4.R6 rewritten; Q4.R8 new; Q5.R3, R8 extended | Q4.A1, A5 amended; Q4.A8 **[gen]**, A9–A11 new; Q5.A10 new (F5; Q4.A5 also F2) | §2.1.6: "with `VAPOR`, `LIQUID` and `SOLID` at F2 (S5 may add `FLUID`, §6)" → "`VAPOR`, `LIQUID`, `FLUID` and `SOLID` (Q4.R6)", and a qualifier may follow every family (`FLUID(water)`, `LIQUID(water).2`): a core-grammar item of the W1 freeze. §2.2.2: add Q4.R6 (FLUID, `character`, root kept within an attempt, `root_switch`), Q4.R3's v̂ key and Q4.R8; "so ADR-F5 can add one without a grammar change (S5, §6)" → "(FLUID, Q4.R6)". §2.2.6–7: Q5.R3, R8 as extended. §3 F5: delete the open item; F5 exit: "Q4.A1–A7" → "Q4.A1–A11", "Q5.A1–A9" → "Q5.A1–A10". F2 exit, ids: qualifiers on every family. §6: drop the row; Q4 "(R1–R7)" → "(R1–R8)". §7 R12: ruled, O-3 closed. §9.4 (1): "is a qualified fluid phase, which Q4.R1 does not allow. It is part of the S5 input to ADR-F5 (§3 F5)" → "is `FLUID(water)` (Q4.R8)". §9.11: drop "(ruling pending)". ADR-F5 adopts the Q4 and Q5 clauses and assertions listed; ADR-F2 adopts the family vocabulary and rendering; F4's comparison (iii) maps legacy VAPOR/LIQUID requests to FLUID with `character`, in its harness only |
| Holdup dormancy (ADR-F7) | Adopted, with the mechanism: entered only at t₀ or by a located drain event whose removed content is ledgered; sources zero while dormant; the seed sits on the energy column (û, not T); refused typed without a zero-holdup form | Q1.R8 new | Q1.A11 new (F7) | §2.5.2 (a): add "dormancy, the drain event and re-seeding per Q1.R8". §3 F7: delete the first open item; F7 exit: add Q1.A11. §6: drop the row; Q1 "(R1–R7)" → "(R1–R9)". §7 R15: ruled. §9.6 (4) and §9.9: cite Q1.R8. §9.11: drop "(rulings pending)". ADR-F7 adopts Q1.R8 and Q1.A11 |
| Non-material holdups (ADR-F7) | Adopted: registered kinds (wall energy, angular momentum), the conserved quantity as column with coefficient 1, unit-local datum, in the ledger | Q1.R9 new | Q1.A12 new (F7) | §2.5.2 (c): "pending a ruling (§6)" → "(Q1.R9)". §3 F7: delete the second open item; F7 exit: add Q1.A12. §9.10 (1): cite Q1.R9. ADR-F7 adopts Q1.R9 and Q1.A12 and amends ADR 0008 U1/U1b (§10 item 8) |

**New findings, listed and not fixed.**
- **A2-a.** The vessel that empties and refills in practice (X25's vented tank) is ADR 0008 U–H.8's kind, which Frank's
  Q-A5 answer keeps out of TX's first release; until an ADR admits it, Q1.R8's drain is reachable only by evacuating a
  rigid vessel (Q1.A11 (b)). Frank's scope call before X25.
- **A2-b.** Units can no longer route by family (VAPOR to the top outlet): ADR-F6 must declare a port-routing rule for
  FLUID phases (density order or `character`), fixed at openings and recorded, and carry Q1.R8's zero-holdup forms.
- **A2-c.** A confined phase beside a FLUID model that can form a phase rich in its component gives that phase two
  representations; the stability test takes the lower Gibbs energy, but whether a method excludes one is for X21 and F5.

**Not established by Amendment 2.** Its numbers are closed forms of synthetic models, in-repository record values or
exact integer cases; nothing has run; the trajectory tolerances and drain bound are estimated floors (O-10). It does not
show that an identification rule gives meaningful characters near critical endpoints, nor that root continuation
converges where roots merge (D09's limitation applies); Q3.R5's condition is checked on five bases, not proved for every
declaration; it chooses no wall or rotor model, admits no U–H.8 vessel, and validates nothing against data.

## 15. Amendment 3 (2026-11-05)

Brief: `docs/roadmap/brief-specifier-anchor-no-data.md`; item: the anchor of a record with no formation data and nothing
phase-tagged, referred by the W1 P1 review (`docs/reviews/W1-P1-review.md` ruling 2) from ADR 0061 D6 step 4 and its
risk 2; it gates ADR-F4. Edits are in place; existing clause numbers are kept, new clauses appended. The last column
lists the architect's edits to `target-architecture.md` and what the gated ADR adopts verbatim.

**The deciding fact:** can a delegating composition over the legacy IAPWS-95 and CoolProp providers evaluate the
ideal-gas state at (T° = 298.15 K, P° = 1e5 Pa)? Established from the code (paths under `src/openflowsheet/thermo/`) and
from scratch evaluations of the legacy kernel and of `docs/derivations/scripts/s05_reference.py`'s 50-digit forms. No
solve was run, and CoolProp is not installed on this workstation.
- *Through the provider interface, no.* Both declare only `LIQUID` and `VAPOR` (`iapws95.py:822`, `coolprop_heos.py:928`)
  and no ideal-gas property (`iapws95.py:128`, `coolprop_heos.py:434–435`). Their VAPOR is the real fluid, φ° + φʳ
  (`iapws95.py:514`, `coolprop_heos.py:575`). For water at (T°, P°), P° = 31.5 P_sat(T°) (P_sat = 3 169.93 Pa,
  ln(P°/P_sat) = 3.45 against ε_σ = 1e-6), so VAPOR is refused `phase_not_stable` (`iapws95.py:781`, `:902–906`;
  measured), and LIQUID answers h = 1 890.141 972 556 56 J/mol.
- *Through the kernels the compositions delegate to, yes.* φ° is evaluated apart from φʳ: `iapws95.py:347–373`
  (`_ideal_jet`, public as `phi_jet`, `:424–428`) and `coolprop_heos.py:509–545` (`_jet`: CoolProp's α° partials on the
  state its guard creates with the gas phase imposed, `:475`). φ°_τ carries no δ (`iapws95.py:368`, `dt=0.0`), so h_ig
  is the same at every density (measured bitwise equal at δ = δ°, 1 and 1e-3: 45 902.570 301 197 77 J/mol), and s_ig
  needs φ° at δ° only. Q2.R9 (b)'s two lines over these calls stay inside the note's definition of a delegating
  composition, which "calls the legacy kernel functions unchanged" (`target-architecture.md:374–375`). They add no
  native-layer output, so M2 (i)'s bitwise proof is untouched, and the shift is checked by Q2.A1.
- *Domains.* IAPWS-95's box, T ∈ [273.16, 1 273.15] K and P ∈ [1e2, 1e8] Pa (`iapws95.py:97–100`), contains (T°, P°).
  Of the 123 CoolProp boxes (`_coolprop_heos_fluids.py`), 118 contain it and 5 do not (Q2.A11 (b)). IAPWS-95's
  coefficient file is in no packaged path (R-594, `iapws95.py:10–14`) and CoolProp is an extra; without them the
  method's own refusal applies, reported as `anchor_unavailable` with that cause (Q2.R9 (c)).

Both methods therefore evaluate `ig` wherever they evaluate anything at (T°, P°), and that decides for `ig`.

| Item | Ruling (default adopted?) | Clauses | Assertions (exit) | Edits to the note; the ADR |
| --- | --- | --- | --- | --- |
| ADR 0061 risk 2 (ADR-F4) | The build default `null` is replaced by the review's alternative, `ig` for a `mol` record with the notice `anchor_defaulted`. The deciding fact forces four precisions: `ig` is the method's ideal-gas state (φ° alone for a Helmholtz method); its evaluation keeps the method's guard and domain; the notice is not identity; other bases keep `null` | Q2.R9 new; Q2.R2 amended (pointer); Q2 rejected alternatives extended | Q2.A10 new (F3; (a), (b) **[gen]**); Q2.A11 new (F4; its values and (b)'s partition **[gen]**) | §2.3.6: after Amendment 2's anchor text add "; a neutral `mol` record with neither formation data nor phase-tagged entries takes `ig`, reported `anchor_defaulted`, and an `ig` anchor is the method's ideal-gas state, φ° alone for a Helmholtz method (Q2.R9)". F3 exit: add "Q2.A10". F4 exit: "Q2.A1–A9" → "Q2.A1–A9, A11". §6 table, Q2 row: "(R1–R8)" → "(R1–R9)". §7: ADR 0061's risk 2 (its edit 5) enters as ruled by Q2.R9. ADR-F4 adopts Q2.R9 and Q2.A11; ADR 0061 takes the edits below |

**Argument.**
1. *Where the anchor of a datum-only component acts.* Q2.R4's datum is a constant per component. A component that takes
   part in no reaction is conserved unit by unit, so the constant cancels in every balance. The anchor decides only the
   state at which two methods agree (the T jump at a method boundary) and which methods are admitted. Reactions stay
   refused (Q2.R4), so a defaulted anchor never reaches Δr h.
2. *Why `ig`.* It is the first neutral phase of Q2.R2's order, and every neutral `mol` species has it. It is the state a
   Helmholtz method defines on its own (φ°), and it is the phase step 2 gives the record once a gas formation datum is
   added, so the record's shifted values then move by that Δf h°(g) alone.
3. *Why not `null`.* It refuses all 124 IAPWS-95 and CoolProp records on `ELEMENTAL-ref-v1` although their methods
   evaluate `ig`. With one convention per flowsheet, every steam, refrigerant and cryogen stream is then kept out of a
   flowsheet holding a PR-C1 or Wilson stream, against R-924. Its merit, that the field says nothing when the record says
   nothing, is kept by the notice and by the record's empty `formation`.
4. *Identity.* The default is a function of the record alone, so A1-b holds. A defaulted and a stated `ig` are one
   record, so the notice is a registration finding, and the legacy index pins it.
5. *Cost.* No legacy index exists yet (`src/openflowsheet/records/` is absent on `main`, 2026-11-05), so the change costs
   no regeneration; if one has been generated by the time ADR 0061 is edited, one `--write` regenerates it.

**What the legacy importer writes** for the three files the default reaches. Every other field is as D12 maps it.

| Profile and file | Records | `anchor_phase` | Index `findings` of each record |
| --- | --- | --- | --- |
| `syn001`, `benchmarks/syn001/components.yaml` | A, B, C | `ig` | `[anchor_defaulted(<id>)]` |
| `s05`, `benchmarks/s05/components.yaml` | H2O | `ig` | `[anchor_defaulted(H2O)]` |
| `s07`, `benchmarks/s07/components.yaml` | the 123 fluids, in file order | `ig` | `[anchor_defaulted(<id>)]` |

None of the 127 carries `fit_inputs_unhashed`: D12's 17 belong to `m01`, `l01` and `s10`. The finding is spelled as
the index spells its other findings. Q2.A10 (a) asserts these lists exactly.

**Edits ADR 0061 needs** (the orchestrator applies them; this document edits no ADR).
1. D6, step 4 becomes two steps: "4. Else, when `amount_basis` is `mol`, `ig`, with the notice
   `anchor_defaulted(<component>)` (Q2.R9). 5. Else `null`, with the finding `anchor_undetermined(<component>)`; F4
   refuses the component on `ELEMENTAL-ref-v1` with that code until its record states an anchor."
2. D6, last sentence: "Step 4 is a gap in the ruling for records with no phase-tagged data at all (risk 2)." →
   "Steps 4 and 5 are Q2.R9 (foundation rulings, Amendment 3); a stated `ig` and a defaulted one give the same record,
   and only the defaulted one carries the notice."
3. D7, *Findings*: before `anchor_undetermined(<component>)` add `anchor_defaulted(<component>)`.
4. D12, "Anchors follow D6: …" → "Anchors follow D6: `ig` from formation data (step 2) for `m01`, `l01`, `s10`,
   `s10-verification`; `ig` by default (step 4) for the 127 records of `syn001`, `s05`, `s07`, each with
   `anchor_defaulted(<id>)` in its index `findings`. No legacy record has a null anchor."
5. E-F3-13: "nothing phase-tagged → `null` and `anchor_undetermined`" → "nothing phase-tagged: `mol` → `ig` and
   `anchor_defaulted`, with the SHA of the same record stating `ig`; `kg` → D6 gives `null` and `anchor_undetermined`,
   and registration is refused `amount_basis_unsupported(kg)` until ADR-F2 (Q2.A10)".
6. New catalogue codes, the notice row: add `anchor_defaulted(<component>)`.
7. Risk 2: replace the body after its title with "*Resolved* by the specifier (foundation rulings Amendment 3, Q2.R9,
   2026-11-05): `ig` with `anchor_defaulted` for a `mol` record, `null` with `anchor_undetermined` otherwise; an `ig`
   anchor is the method's ideal-gas state, and its evaluation keeps the method's guard and domain."

**New findings, listed and not fixed.**
- **A3-a.** Q2.R9 (b) says what an `ig` anchor means for every record, not only a defaulted one. A composed real-gas
  method evaluates its ideal-gas part, not its vapour at P°. Only Q2.A3 states this, and only for elements: Q2.A2's
  identity cannot see a real-gas method anchored at its vapour at P°, because the shift and the check use the same
  state, which is off the tabulated Δf h°(g) by the departure. ADR-F4 must give each composed real-gas method that
  evaluation (for PR-C1, its ideal-gas c_p integral) or refuse it typed, and its exit should carry one departure control
  on a non-Helmholtz method. ADR-F4.
- **A3-b.** ADR 0061 D7 stores findings. A record registered first by the importer, with the notice, and later stated
  `ig` by a user is one stored object. D8 should state whether the stored findings are the first registration's or
  per registration. ADR 0061.

**Not established by Amendment 3.**
- No CoolProp evaluation was run. The 118/5 partition is read from the fluid table, and whether each in-box fluid's α°
  evaluates at (T°, δ°) is O-12's measurement. An independent value exists only for CoolProp's water.
- The floors come from a scratch script on the legacy kernel on one x86_64 machine; aarch64 is unmeasured (O-13). No
  shipped generator emits the values yet; the reference generator must (**[gen]**).
- The component datum is a convention for non-reacting use, not an elemental enthalpy. Nothing here makes an `s05` or
  `s07` record reaction-capable (that needs a record with formation data), and nothing validates a property against
  data.
- It does not choose how ADR-F4 calls the kernels (`phi_jet`, the provider's `_jet`), nor the ideal-gas evaluation of
  non-Helmholtz methods (A3-a). F4 composes no SYN-001 method (`target-architecture.md:432–433`), so the `syn001`
  default is asserted at F3 only.

## 16. Amendment 4 (2026-11-05)

Brief: `docs/roadmap/brief-specifier-W1-P3-questions.md`; items: ADR 0063 risk 5 (the entropy datum, W1 P2 review S6)
and the specifier questions of ADR 0065 (SQ-F6-1, -3, -4), ADR 0066 (SQ-F7-1, -2) and ADR 0067 (SQ-F8-1). SQ-F6-2 is
ruled by its own sheet, `docs/derivations/F6-std-seed.md`, whose expectations come from
`docs/derivations/scripts/f6_std_seed_reference.py` (`--check`). Edits are in place; existing clause numbers are kept,
new clauses appended. The last column lists the note edits and what each ADR adopts.

| Item | Ruling (default adopted?) | Clauses | Assertions (exit) | Edits to the note; the ADR |
| --- | --- | --- | --- | --- |
| Entropy datum (ADR 0063 risk 5) | Adopted with the refusal narrowed: the default refuses "any reaction or equilibrium" reading s or g; the ruling refuses only uses in which the component's amount changes. Phase equilibrium and every fixed-amount use are datum-free and admitted, so **PS and TS specifications and the isentropic units are admitted** on such a component. Also: s° from another phase plus a transition datum; a bridge without its entropy part refuses s and g | Q2.R10 new | Q2.A12 new (F4: (a), (d), (e); F6: (b), (c)) | §2.3.6: after "entropy datum" add "(s° absent: s = 0 in the anchor phase, notice `entropy_datum`; admitted wherever the component's amount is conserved, refused where it reacts; Q2.R10)". F4 exit: add Q2.A12 (a), (d), (e); F6 exit: Q2.A12 (b), (c). §6 Q2: "(R1–R9)" → "(R1–R10)". ADR 0063 adopts Q2.R10, Q2.A12; edits 0063-1 to -3 |
| SQ-F6-1 (ADR 0065 D9 (iii)) | Adopted, generalised: a FLUID phase routes as the `split` family its character names; τ_ρ = 1e-6 with Q4.R5's flag band (10 τ); a band τ_char added for the character decision, which now has consequences | Q4.R9 new | Q4.A12 new (F6) | §2.2.2 or §2.4 (routing): add Q4.R9. §11 O-11 (here) and the note's §6 O-11 row: "reported only, no numerical consequence" → "decides a lone fluid phase's outlet (Q4.R9)". F6 exit: add Q4.A12. ADR 0065 adopts Q4.R9, Q4.A12; edit 0065-1 |
| SQ-F6-3 (ADR 0065 D10) | Adopted (D10's sign rule), made complete: it is the normal-cone condition of a clamped integrator; the failed-closure transitions are fixed so no signature repeats; flags and notice | Q5.R9 new | Q5.A11 new (F6, E-F6-14) | §2.4.11: `std.pid` steady closure per Q5.R9. ADR 0065 adopts Q5.R9, Q5.A11; edit 0065-2 |
| SQ-F6-4 (ADR 0065 D11) | Adopted (the cross check's tolerance; equality passes), with the direction taken from the sign of Q and the `not_applicable` cases | Q5.R10 new | Q5.A12 new (F6, E-F6-18) | §2.4 heat ports: Q5.R10. ADR 0065 adopts Q5.R10, Q5.A12; edit 0065-3 |
| SQ-F7-1 (ADR 0066 D7) | Adopted (τ_idx = τ_ill = 1e-8 on rcond₁ of the scaled ∂g/∂z, D2.4's band); D7's example is wrong and is corrected | Q5.R11 new | Q5.A13 new (F7) | §2.5.3: τ_idx and its example. F7 exit: add Q5.A13. ADR 0066 adopts Q5.R11, Q5.A13; edit 0066-2 |
| SQ-F7-2 (ADR 0066 D5) | Adopted and defined: τ_loc relative to \|t\| + \|h\| (defined at t = 0), τ_ev = 10 τ_loc, ascending (priority, id), action values on the pre-group state, one re-initialisation per group; conflicts and cascades typed | Q1.R10 new | Q1.A13 new (F7) | §2.5.2: events per Q1.R10. F7 exit: add Q1.A13. §6 Q1: "(R1–R9)" → "(R1–R10)". ADR 0066 adopts Q1.R10, Q1.A13; edits 0066-1, -3 |
| SQ-F8-1 (ADR 0067 D8) | **Changed:** τ_g is in the event function's units, 10 × its kind's D2.2 floor, not the location tolerance (a time); a near-threshold disagreement imposes the record and gives `MATCH` with `verdict_changed_near_threshold`; other mismatches `forced_replay_divergence` (as the default) | Q9.R8 new | Q9.A9 new (TX) | §2.7: `forced_replay` per Q9.R8. TX exit: add Q9.A9. ADR 0067 adopts Q9.R8, Q9.A9; edit 0067-1 |

**Argument.**
1. *Where the entropy datum acts.* The S shift is linear in amounts: S = S_native + Σ_c n_c Δˢ_{m,c}. At fixed amounts
   the second term is a constant, so a PS or TS point, an isentropic reference at (n, Ṡ_in, P_out) and any entropy
   difference see S_native alone. A non-reacting unit conserves every n_c, so Σ_out n_c = Σ_in n_c and the datum terms
   cancel in S_out − Σ S_in. In phase equilibrium μ_c gains Δ_{m,c} − T Δˢ_{m,c} in every phase of method m; between
   methods anchored in a, the shifts differ by h^{m′}_c(a) − h^m_c(a) − T (s^{m′}_c(a) − s^m_c(a)), in which s°_c does
   not appear. Only where n_c changes does Σ_c ν_c s°_c enter (Δr s°, so Δr g° and K). Hence the refusal belongs to
   reactions, as Q2.R4's does for h, and a flash or an isentropic unit on an m01 component on `cubic.pr-v1` is
   admitted. The default's "or equilibrium" would refuse every flash on every legacy record (no legacy record has s°,
   ADR 0061 risk 6) without any number changing.
2. *Floor of the datum.* The isentropic point solves S(T_s, P_out, n) = S_in with the constant on both sides: the
   rounding it adds is ε (|S| + |Σ n_c Δˢ_c|) in S, ≈ 3e-13 K in T_s at CMP-1, five decades under the PS solve.
3. *Routing.* With one fluid phase present, density order says nothing; any rule is a convention. A fixed port sends a
   superheated vapour fed to a drum out of the liquid outlet, unlike every legacy unit and the reference tools; the
   character reproduces `split` routing wherever the identification rule agrees with the legacy label, and it is
   decided once per attempt, so it is a discrete coordinate like the others. Its threshold therefore needs D2.4's
   treatment: D2.4's multiplicative band [q*/10, 10 q*] would cover almost every state, so the band is relative to q*
   at Q4.R5's width.
4. *The steady controller.* The steady state of ṙ = σe with the output clamped to [out_min, out_max] is exactly
   σe ∈ N(out). The transition order makes the regime search finite (three regimes, none repeated) and keeps the
   wrong-action case (Q5.A11 (c)) solvable: its only rest point is `saturated_low`.
5. *Index of a liquid-full vessel.* With z = (T, P), ∂g/∂z of the rows (N v − V, U − N u) has determinant
   N² v (κ c_p − T v α²) = N² v κ c_v (molar c_v); at κ → 0 with α ≠ 0 this tends to −N² T v² α² ≠ 0: the volume row
   then fixes T and the energy row P, index 1. The block is singular only when both v_T and v_P vanish. In scaled form,
   for α = 0, rcond₁ = κ s_P/(1 + κ s_P P0 v0/(c_p s_T)) (Q5.A13); a PR liquid has α s_T ≈ 0.1 and is regular.
6. *Events.* A location tolerance relative to |t| alone vanishes at t = 0; |t| + |h| is the usual form (SUNDIALS'
   root finding uses 100 ε (|t| + |h|) [zotero]), and 1e-14 is 45 ε. τ_ev = 10 τ_loc makes two roots of one exact
   instant, located independently, one group. Evaluating all actions on the pre-group state and refusing conflicting
   writes makes the result independent of the order, which then only orders the record.
7. *Grazing.* The quantity compared with zero is g; its cross-platform difference under imposed steps is bounded by
   the comparison rule of its kind (D2.1, whose floor at zero is D2.2's), and D2.4's margin of 10 makes a sign
   disagreement explainable by roundoff exactly when |g| ≤ τ_g. Continuing a replay with the replay's own decision
   would shift every later step by an action applied one step early, a truncation-level difference no float policy can
   judge; imposing the record keeps the rest at roundoff, which is why `forced_replay` imposes decisions at all.

**Edits the ADRs need** (the orchestrator applies them; this document edits no ADR). Eleven in all.
- **0063-1.** D4 step 5 → "5. The S shift per Q2.R10: for a method providing `s`, Δˢ_{m,c} = s°_c(a) − s^m_c(a; T°, P°),
  s°_c(a) from the record's anchor-phase entry, else another phase's entry with a transition datum, else 0 with the
  notice `entropy_datum(<c>)`; uses in which the amount of c changes (Δr s, Δr g, K or affinity from g, a free-n_c Gibbs
  minimisation) are refused `component_not_reaction_consistent(<c>)`; fixed-amount uses (PS, TS, isentropic references,
  phase equilibrium) are admitted. A method without `s` (PR-C1, `pr_c1.py:761`) gets no S shift and provides no `s`,
  `s_ig` or `g`."
- **0063-2.** Risk 5: replace the body after its title with "*Resolved* by the specifier (foundation rulings Amendment 4,
  Q2.R10, 2026-11-05): the default, with the refusal narrowed to uses in which the component's amount changes; PS and
  TS specifications and isentropic units on such a component are admitted."
- **0063-3.** Header: "Adopts verbatim: Q2.R1–R9 and Q2.A1–A9, A11" → "Q2.R1–R10 and Q2.A1–A9, A11, A12"; exit list:
  add Q2.A12 (a), (d), (e) (F4); catalogue: `anchor_unavailable` gains the cause `entropy_bridge_missing`.
- **0065-1.** D9 (iii) → "(iii) *Exactly one active fluid phase*: it takes the port a lone VAPOR takes under (i) if it
  is VAPOR or `vapour_like`, else the port a lone LIQUID takes (Q4.R9); its character is fixed with the routing at the
  opening, and |q − q*| ≤ 10 τ_char |q*| flags `near_threshold`." Last sentence: "A relative density gap ≤ τ_ρ attaches
  `near_threshold` (Q4.R5's pattern; τ_ρ = 1e-6, SQ-F6-1)" → "An adjacent pair with |ln ρ_a − ln ρ_b| ≤ 10 τ_ρ attaches
  `near_threshold` (Q4.R5's pattern; τ_ρ = τ_char = 1e-6, Q4.R9)". E-F6-10 (c), (d): cite Q4.A12.
- **0065-2.** D10, from "Closure:" to "(**SQ-F6-3**, default as stated)" → "Closure and transitions per Q5.R9 (the
  normal-cone condition σe ∈ N(out); a saturated regime with the wrong sign opens `tracking` unless visited in the
  solve, else the other saturated regime; near-threshold flags; notice `controller_saturated`); out_min ≤ out_max is a
  D2 validation rule." E-F6-14: cite Q5.A11.
- **0065-3.** D11, "for a heat connection from A to B, `max T_A ≥ min T_B − τ_hd`; τ_hd is … (**SQ-F6-4**)" → "with the
  direction from the sign of the connection's Q, `not_applicable(no_heat_flow)` for |Q| ≤ τ_Q and
  `not_applicable(zero_flow)` for a dormant side; τ_hd the policy's `temperature` tolerance (Q5.R10)". E-F6-18: cite
  Q5.A12.
- **0065-4.** Header "Adopts verbatim": add Q4.R9, Q5.R9, Q5.R10, Q2.A12 (b), (c), Q4.A12, Q5.A11, Q5.A12 and the sheet
  `docs/derivations/F6-std-seed.md` (SQ-F6-2); exits: add Q2.A12 (b), (c) beside E-F6-16; "Specifier questions":
  SQ-F6-1, -3, -4 "ruled (Amendment 4)", SQ-F6-2 "ruled (the sheet)"; risk 1 resolved. The sheet's own ADR edits are
  listed in its §7.
- **0066-1.** D5, "Events located in one step at times within τ_ev of each other are simultaneous; they apply in
  (priority, id) order, then one consistent re-initialisation (D6). … (τ_ev, ordering: SQ-F7-2.)" → "Simultaneous
  events, their order, conflicts and cascades follow Q1.R10 (τ_ev = 10 τ_loc; ascending (priority, id); action values
  on the pre-group state; one re-initialisation per group; `simultaneous_event_conflict`, `event_chattering`)."
- **0066-2.** D7, "below τ_idx … as for PR liquid in a fixed volume (SQ-F7-1)" → "below τ_idx = K04's τ_ill = 1e-8 the run
  carries the typed limitation `dae_index_near_singular` (not a refusal), with D2.4's near-threshold band (Q5.R11): for
  example a vessel full of a liquid whose scaled expansivity and compressibility are both small; an ordinary liquid,
  PR's included, is regular (Q5.A13 (e))".
- **0066-3.** D16, "event location by Illinois on the linear interpolant to 1e-14 relative in t" → "… to τ_loc =
  1e-14 (|t| + |h|) (Q1.R10)". Exits: add Q1.A13 and Q5.A13. Codes: `simultaneous_event_conflict`, `event_chattering`,
  `event_floor_unregistered`; F7 registers a D2.2 floor for every quantity kind an event function may have (D2.3).
  Specifier questions: SQ-F7-1, -2 "ruled (Amendment 4)".
- **0067-1.** D8, "Grazing events near a step boundary: SQ-F8-1." → "Event disagreements are judged by Q9.R8: near
  threshold iff the replay's |g| ≤ τ_g (10 × the function kind's D2.2 floor) at the disputed time; then the record is
  imposed and the verdict is `MATCH` with `verdict_changed_near_threshold`; otherwise `forced_replay_divergence`." TX's
  exit (WO7): add Q9.A9. Specifier question SQ-F8-1: "ruled, default changed (Amendment 4)".

**New findings, listed and not fixed.**
- **A4-a.** ADR 0065 D17 runs equivalence step 1 on the `syn001` bases, but ADR 0063 composes no SYN-001 method
  (`0063:21–22`; Amendment 3 asserts the `syn001` anchor at F3 only). F6 needs a delegating SYN-001 composition, or its
  `syn001` leg is `equivalence_pending`. The sheet's checks use a test-only method with SYN-001's potentials (sheet §2).
  ADR 0065.
- **A4-b.** ADR 0007 D2.4's band is multiplicative and has no meaning at a threshold of zero (a sign, an event function,
  a duty direction); Q5.R10 and Q9.R8 use additive bands. ADR 0007 could state the additive form once.
- **A4-c.** The sheet (its §7) finds that a state point whose amounts are all `+0.0` needs a stated behaviour (not
  evaluated, labels, rows reading it swapped) and that a specification on a derived intensive of a dormant stream must
  be swapped by a form; ADR 0065 D6–D7 carry neither. ADR 0065.

**Not established by Amendment 4.**
- Nothing has run. The sheet's closed forms and Q5.A13's values come from 50-digit scratch evaluations and the sheet's
  generator; Q4.A12 (c), Q5.A13 and the event and replay probes need F6's, F7's and TX's generators and runs.
- τ_char, τ_ρ, τ_hd's floor, τ_idx, c_loc and τ_g are estimates with stated margins (O-14 to O-18), not measurements.
- The routing rule makes a choice of O-11 numerically visible; it does not make any identification rule physically
  right near critical endpoints (Amendment 2's limitation stands).
- The entropy datum makes no record reaction-capable in s or g; Q2.A12's s° values are synthetic, not data. Nothing
  here validates a property, a controller or an integrator against measurement.

## 17. Amendment 5 (2026-11-06)

Brief: `docs/roadmap/brief-specifier-amendment5.md`; items: the stream table's specifier questions SQ-ST-1…6 (ADR 0068;
`docs/design/ST-stream-table.md` §13) and SQ-F6-5 (ADR 0065 D9; W1 P3 review M4). Edits are in place: new clauses and
assertions are appended to Q1, Q2 and Q4, Q4.R9's last sentence is amended, O-11 is extended and O-19 to O-21 are added.
Nothing released moves: ST is computed on read and enters no identity (ADR 0068 C-1), F6 is unreleased, no F0 measure
is touched, and no catalogue code is added (every null carries one of ADR 0068's seven codes, R-924).

| Item | Ruling (default adopted?) | Clauses | Assertions (exit) | Edits |
| --- | --- | --- | --- | --- |
| SQ-ST-1 | Adopted, with precisions: the denominators are the listed phases' sums, so 0.0 and 1.0 are exact, vf ∈ [0, 1] by monotone rounding and vf_molar is the VAPOR phase fraction bitwise; never nulled by a property failure; v2's vapour group is Q4.R13's (VAPOR or `vapour_like` FLUID) | Q4.R10 new | Q4.A13 new (ST G2, G4, G6) | N5, N8, N9; 0068-3, -5 |
| SQ-ST-2 | Adopted; P stays shown (v1's zero-flow forms keep every pressure row); `n`, `m` normalised to +0.0; no provider call | Q1.R11 new | Q1.A14 new (ST G4) | N1, N9; 0068-2, -5 |
| SQ-ST-3 | Adopted (raw TP flash, no snap), and what the table reports where it may disagree: `flash_near_phase_boundary` (minority fraction ≤ τ_β = 1e-8, or a verifier `independent_split` row `not_applicable` for degeneracy or an unresolved flash), those rows quoted, and the closed form of the Ḣ difference | Q4.R12 new | Q4.A15 new (ST G16, new) | N3, N6, N7, N9, N10; 0068-2, -3, -5, -6, -7 |
| SQ-ST-4 | Adopted; the stream's `T` stays the stored T; a refused `Tsat` nulls the properties only | Q1.R12 new | Q1.A15 new (ST G3, G7) | N2, N9; 0068-2, -5 |
| SQ-ST-5 | Adopted; the reason for refusing `s_<c>`, `v_<c>` restated (the key does not say pure-component or partial molar) | Q2.R11 new | Q2.A13 new (ST G5) | N4, N9; 0068-4, -5 |
| SQ-ST-6 | Adopted, with precisions: negative carried amounts listed and never clamped; ids never renumbered; every quotient IEEE, a non-finite one null with `value_not_finite`, never raised | Q4.R11 new | Q4.A14 new (ST G4, G6, G7) | N3, N5, N9; 0068-2, -3, -5 |
| SQ-F6-5 | **Changed for `vapor: null`:** the vapour group takes the first liquid port, as D9 (i) does for VAPOR, instead of joining the density order; with a `vapor` port, as the default. One rule for `split` and `single` and every phase count; Q4.R9 is its one-phase case | Q4.R13 new; Q4.R9 amended | Q4.A16 new (F6, E-F6-10 (g)) | T1; 0065-5 to -7 |

**Argument.**
1. *The fractions' denominators.* With N_P the sum of the listed amounts, a stream listing VAPOR alone has N_V and N_P
   the same sum, hence 1.0; one without VAPOR has 0.0/N_P = 0.0; and fl(a + b) ≥ a for a, b ≥ 0, so N_V ≤ N_P and the
   quotient is ≤ 1. With the stream's n_tot as denominator (the default formula) an R1 stream gives V/n with V + L ≠ n
   by the saturation row's residual, so a saturated vapour could show 1 + 1e-10, and an R3 stream would depend on how
   the flash rebuilds its outlets. The stream's n_tot remains the denominator of h and s.
2. *Not the thermodynamic quality.* (h − h_L)/(h_V − h_L) needs h_L and h_V at P, so it exists only for one component
   in two phases; there it equals the vapour mass fraction (lever rule, E2), and elsewhere the tools that report it give
   values outside [0, 1] or a sentinel. A member called `quality` would carry one meaning to readers expecting the
   other. Taking Q4.R13's vapour group makes the reported fraction what a drum's `vapor` port would take, a definition
   that holds in v1 and v2 alike.
3. *The dormant T.* At dormancy v1 replaces each row that loses rank in an outlet T by T_out − T_label = 0 (ADR 0012
   D4 (c), D12); a dormant feed keeps its specified T. Either way the stored T describes no material (ADR 0001 D3.1
   calls it a label), and Q1.R4 forbids a label as a property input or a reported result. No v1 zero-flow form swaps a
   pressure row, so P is a solved value.
4. *The report's decision against the verifier's.* Rachford–Rice: f(β) = Σ_c z_c (K_c − 1)/(1 + β(K_c − 1)), f(0) =
   Σ z K − 1 = δ, f′(β) = −Σ_c z_c (K_c − 1)²/(1 + β(K_c − 1))². On [0, 1] each denominator lies between 1 and K_c,
   so g/max(1, K_max)² ≤ |f′| ≤ g/min(1, K_min)², g = Σ_c z_c (K_c − 1)², and the root (δ = ∫₀^β* |f′|) obeys
   δ min(1, K_min)²/g ≤ β* ≤ δ max(1, K_max)²/g; the dew side is the same with K → 1/K and β → 1 − β. Inside SYN-001's
   band δ ≤ ε_adm, so the minority fraction is ≤ c·ε_adm; at the probes c ≈ 7, three decades inside the reach c ≤ 1e4.
   c grows as every K_c approaches 1 (near-critical, azeotropic or near-pure streams, the temperature-degenerate case),
   which is where (i) stops covering and (ii) or nothing must. On PR-C1 the liquid's total is l_NH3/x^L_NH3. The snaps
   are not copied because they exist so that the verifier's energy row reads the phase its admissibility row admitted
   (ADR 0013 D2), a device for a consistent verdict at a band's edge; in a report they would put a step of width 1e-12
   into a continuous quantity and need per-form code that ADR 0068 D3 rejected. The verifier evaluates Σ_c n_c
   h_c^maj, the report Σ_c n_maj,c h_c^maj + Σ_c n_min,c h_c^min; with n_maj + n_min = n the difference is
   Σ_c n_min,c (h_c^min − h_c^maj), about 1e-7 W at the probes against the energy rows' 1.01e-3 W (SYN-001's
   `ENERGY_TOLERANCE`), which is why the verdict and the report can both stand and the flag only explains.
5. *T_sat.* A one-component two-phase state is degenerate in T (Q1 argument 1): the stored T sits within the solver's
   tolerance of T_sat(P), on either side, where one phase is metastable or not offered. ADR 0051 D2 defines Ḣ at
   (T_sat(P), P) for that reason and the verifier evaluates there. The stored T stays the reported coordinate because a
   report never replaces a state value with a derived one; the two differ by at most the temperature tolerance the
   certificate judged.
6. *Property forms.* For an ideal solution the partial molar and pure-component enthalpies coincide, so Σ_c n_c h_c is
   exact whichever SYN-001 means; entropies differ by −R ln x_c and volumes by the partial excess volume. A key that
   does not say which cannot be summed safely. The refusal costs nothing today (no legacy provider returns `s_<c>` or
   `v_<c>`) and stops a future provider from being summed wrongly. An ideal-gas density would be a second thermodynamic
   model inside a report; a provider with a vapour volume declares `v`, and the report then shows it.
7. *Listing, signs and underflow.* The dormancy test is exact (ADR 0001 D3.1); a threshold would move the line between
   a trace phase and none. Listing only positive amounts would drop a term the verifier's Ḣ contains (E7) and break
   Σ_p = substream; clamping would invent a state. M·n rounds to +0.0 when M·n < 2⁻¹⁰⁷⁵ (n = 5e-324 mol/s, M = 0.1
   kg/mol): such a phase flows and has no mass. IEEE then yields inf or NaN, and Python raises on a float division by
   zero, hence the explicit rule.
8. *Routing (SQ-F6-5).* Under Q4.R13 a phase's port depends on its own character and, in the liquid group, on the
   density order among liquid-group phases only. A vapour-group phase appearing or vanishing moves no liquid-group
   phase, so the count changes ±1 of Q4.A12 (b) keep every persisting phase on its port. The default's "a unit with
   `vapor: null` routes them all by density" breaks the equivalence with `split` that Amendment 4 (argument 3) relied
   on: a VLLE feed at a two-port decanter sends the vapour to the light port and the light liquid to the heavy port
   (Q4.A16 (4)), while (i) sends VAPOR and the light liquid to the light port, which is the review's M4 failure 2 on the
   `single` side. Treating the vapour group as a block that takes the vapour port, or the lightest port when there is
   none, is (i) with the character in place of the family, so `single` and `split` route alike wherever the
   identification rule agrees with the legacy label. A dense vapour-like phase leaves by `vapor` whatever its density,
   as VAPOR does under (i); two vapour-like phases (gas–gas immiscibility) share `vapor`, and nothing inside the vapour
   group is ordered, so nothing there is flagged.
9. *Rounding bounds* (u = ε/2; a rounding count, not a measurement). With one molar mass M shared by a phase's C
   components, m_p,tot = M n_p,tot (1 + θ_p), |θ_p| ≤ (2C − 1) u (C products and two sums of C terms). vf_mass/vf_molar
   is the VAPOR phase's ratio over the amount-weighted mean of both phases', with four more roundings, so
   |vf_mass/vf_molar − 1| ≤ (4C + 2) u = (2C + 1) ε; likewise |w_c/x_c − 1| ≤ (C + 1) ε. Since an ulp of x lies between
   εx/2 and εx, the note's "4 ulp" (G2 for water's vf, G4 for SYN-001's w) sits below these worst cases (up to 6 and 8
   ulp). Q4.A13 (d) takes 4(C + 1) ε·vf and N9 takes 8ε·vf (water) and 8ε·x_c (SYN-001), a margin ≥ 2.

**Edits the ADRs and the design note need** (the orchestrator applies them; this document edits none). Twenty-one in all.
- **0068-1.** Header, "Builds on": append "Adopts verbatim foundation rulings Amendment 5: Q1.R11, Q1.R12, Q2.R11,
  Q4.R10, Q4.R11, Q4.R12 and Q1.A14, Q1.A15, Q2.A13, Q4.A13–A15."
- **0068-2.** D3: R0 bullet, after "with `zero_flow` (Q1.R4)" add "; no provider call; `n` and `m` are `+0.0`
  (Q1.R11)". R1 bullet: append "The stream's `T` is the stored T; a refused `Tsat` nulls the properties only
  (Q1.R12)." R3 bullet: append "Each substream reports `flash_near_phase_boundary` (Q4.R12 (b))." "A phase is listed
  iff its amount is `!= 0.0`, in the order VAPOR, LIQUID." → "A phase is listed iff its amount is `!= 0.0`, of either
  sign and never clamped, in the order VAPOR, LIQUID, with the decision's ids (Q4.R11)."
- **0068-3.** D5: "Per substream: `vapor_fraction_molar` and `vapor_fraction_mass` over the VAPOR family." → "Per
  substream: `vapor_fraction_molar` and `vapor_fraction_mass` over the vapour group (v1: VAPOR), with the listed phases'
  sums as denominators, which `phase_fraction_molar` and `phase_fraction_mass` share (Q4.R10); and
  `flash_near_phase_boundary` (Q4.R12)." New last bullet: "Every quotient is an IEEE division; a non-finite result is
  null with `value_not_finite` (Q4.R11 (c))."
- **0068-4.** Alternatives rejected, last bullet: "the sum also drops the entropy of mixing." → "a per-component key
  does not say whether it is pure-component or partial molar, and summed pure-component values drop the entropy of
  mixing (Q2.R11)."
- **0068-5.** Exit tests. E2: "At S5, `vf ≤ 1e-12` and `h = h_L(P5)` to 1e-12." → "At S5, `vf_molar = V5/(0.0 + V5 +
  L5)` and `|h − h_L(P5)| ≤ (|V5|(h_V − h_L) + |V5 + L5 − n5|·|h_L|)/n5 + 8ε|h_L|`." E3: append "S4's stored T is
  kept (Q1.A15)." E4: "on SYN-001, `w = x` within 4 ulp" → "on SYN-001, `|w − x| ≤ 8ε·x`; Q1.A14, Q4.A13 (b), (f),
  Q4.A14 (d)". E5: append "Q2.A13." E6: append "Q4.A13 (a), (d)." E7: append "Q1.A15 (c); Q4.A14 (a)–(c)." After E15
  add "**E16** The report's decision near a phase boundary: Q4.A15 (note G16)."
- **0068-6.** "Riskiest point": append "*Ruled by Q4.R12 (Amendment 5):* the raw flash stays;
  `flash_near_phase_boundary` and the quoted `independent_split` rows mark where the verifier may have decided
  otherwise; E16 tests it." "Specifier questions": under the heading add "Ruled 2026-11-06 (foundation rulings
  Amendment 5): SQ-ST-1 Q4.R10, SQ-ST-2 Q1.R11, SQ-ST-3 Q4.R12, SQ-ST-4 Q1.R12, SQ-ST-5 Q2.R11, SQ-ST-6 Q4.R11; each
  default adopted with the precisions of §17's table."
- **0068-7.** Frozen-list changes, the schema bullet: append "The substream object carries `flash_near_phase_boundary:
  boolean` from v1 on, and a stream's `checks` also quote its `independent_split` rows (Q4.R12)."
- **0065-5.** D9, from "At every **opening** the routing is fixed for the attempt: (i)" through "flags
  `near_threshold`." → "At every **opening** the routing is fixed for the attempt by Q4.R13 (Amendment 5, SQ-F6-5): the
  vapour group (VAPOR phases and FLUID phases whose `character` is `vapour_like`) leaves by `vapor`, or by the first
  liquid port when `vapor` is null; the liquid group (the other fluid phases, confined ones included) goes over
  `light_to_heavy` in mass-density order, ascending, an exact tie by canonical ordinal, phases beyond the last liquid
  port by the last port; SOLID phases by `solids`, else by the last port. With two `split` candidates this is today's
  routing exactly (equivalence step 1 depends on it); with one fluid phase it is Q4.R9. Each character is fixed with
  the routing at the opening, and |q − q*| ≤ 10 τ_char |q*| on any FLUID phase flags `near_threshold`." Then
  "adjacency: one transposition of density-adjacent phases, or a change of the single phase's port" → "adjacency: one
  transposition of density-adjacent liquid-group phases, or one fluid phase moved between the groups"; "Closure checks
  the order at the converged state; a different order closes" → "Closure checks the groups and the order at the
  converged state; a difference closes"; "An adjacent pair with" → "An adjacent liquid-group pair with", and "Q4.R9)."
  at the end → "Q4.R9, R13)."
- **0065-6.** E-F6-10: append "(g) the routing vectors of Q4.A16, the `vapor: null` VLLE case (4) included." F6-WO4's
  acceptance: "E-F6-10 (b–d, f)" → "E-F6-10 (b–d, f, g)".
- **0065-7.** Header "Adopts verbatim", after "as the W1 P3 review rules them.": add "From Amendment 5 (2026-11-06):
  Q4.R13, Q4.A16, and Q4.R9 as amended." SQ-F6-5: replace the item with "*Ruled (Amendment 5): Q4.R13; default changed
  for `vapor: null`* (the vapour group takes the first liquid port, as (i) does for VAPOR; the default's 'all by
  density' sent the light liquid of a VLLE feed to the heavy port)."
- **N1.** Note §4.2 R0: "The arrays `n` and `m` hold the stored flows and `M_c·n_c`;" → "The arrays `n` and `m` are
  `+0.0` (a stored −0.0 normalised), and no provider call is made (Q1.R11);".
- **N2.** §4.2 R1, after "which is what the verifier's `_properties` assumes." add "The stream's `T` is the stored T. A
  `Tsat` status other than `"ok"` nulls every property-derived quantity of the substream and its phases with
  `property_evaluation_failed(stream=S, phase=LIQUID, property=Tsat, status=…)`; amounts, compositions and fractions are
  still given (Q1.R12)."
- **N3.** §4.2 R3, after "There is **no snap**." add "The substream's `flash_near_phase_boundary` is true iff two or
  more phases are listed and min_p |n_p,tot|/N_P ≤ τ_β = 1e-8, or the stream has a quoted `independent_split` row with
  result `not_applicable` and reason `temperature_degenerate` or `fresh_flash_unresolved` (Q4.R12 (b)); it is false
  for R0–R2." Listing bullet: "A phase is listed iff it exists and its total amount is `!= 0.0`" → "A phase is listed
  iff it exists and its total amount is `!= 0.0` (either sign, never clamped; ids never renumbered; Q4.R11)".
- **N4.** §4.3, s and v bullet: "because summing x·s_c drops the entropy of mixing." → "because such a key does not say
  whether it holds a pure-component or a partial molar value, and summed pure-component values drop the entropy of
  mixing (s) or the excess volume (v) (Q2.R11)."
- **N5.** §4.3 Phase intensives: "`phase_fraction_molar = n_p,tot / n_tot`; `phase_fraction_mass = m_p,tot / m_tot`." →
  "`phase_fraction_molar = n_p,tot / N_P`; `phase_fraction_mass = m_p,tot / M_P`, with N_P = Σ_p n_p,tot and M_P =
  Σ_p m_p,tot over the listed phases from 0.0 in listing order (Q4.R10)." The **Vapour fractions** bullet →
  "`vapor_fraction_molar = (Σ_{p in the vapour group} n_p,tot)/N_P` and `vapor_fraction_mass = (Σ m_p,tot)/M_P`,
  accumulated from 0.0 (v1: the vapour group is VAPOR); exactly 0.0 with no VAPOR listed and 1.0 with VAPOR alone, in
  [0, 1] when no listed amount is negative, bitwise the VAPOR `phase_fraction_molar`; null only for R0, a failed flash
  or a non-finite quotient (Q4.R10)." New bullet after it: "**Quotients.** Every division in §4.3 is an IEEE division: a
  non-finite result (for example a zero mass after underflow) is null with `value_not_finite(subject, quantity)`, never
  an exception (Q4.R11 (c))."
- **N6.** §4.4: "every certificate row with `category == "phase_admissibility"` and `subject == S`" → "every
  certificate row with `category` in {`phase_admissibility`, `independent_split`} and `subject == S`".
- **N7.** §5, substream line: after "`phase_source: str (…; open)`," add "`flash_near_phase_boundary: bool`,".
- **N8.** §8: "FLUID phases gain `character`, and a vapour fraction counts FLUID phases with `character ==
  vapour_like` (Q4.R6, R9); how SOLID enters is F4's decision." → "FLUID phases gain `character`, read from the state
  point; the vapour fractions count Q4.R13's vapour group (VAPOR and `vapour_like` FLUID) over all listed phases, a
  SOLID phase included by default (Q4.R10, O-20); `flash_near_phase_boundary` is false for `state_point`, whose own
  flags are added beside it (Q4.R12 (e))."
- **N9.** §10–§11. WO-1's acceptance: "G1–G10, G14" → "G1–G10, G14, G16". G2: "and `|vf_mass − vf_molar| ≤ 4 ulp`" →
  "and `|vf_mass − vf_molar| ≤ 8ε·vf_molar` (worst case 3ε, §17 argument 9)"; "S5 (`outlet_vapor_fraction 0`):
  `vf_molar ≤ 1e-12`, and `h(S5)` is within 1e-12 relative of `h_L(P5)`." → "S5 (`outlet_vapor_fraction 0`):
  `vf_molar = V5/(0.0 + V5 + L5)` bitwise, and `|h(S5) − h_L(P5)| ≤ (|V5|(h_V − h_L) + |V5 + L5 − n5|·|h_L|)/n5 +
  8ε|h_L|` (the bounds checks admit |V5| up to τ_flow; record |V5|/n5)." G3: append "S4's stored T is kept and
  `|T − 450 K| > 100 K` asserted (Q1.A15 (a))." G4: "`|w_c − x_c| ≤ 4 ulp`" → "`|w_c − x_c| ≤ 8ε·x_c` (worst case
  4ε)"; append "Q1.A14; Q4.A13 (b), (f); Q4.A14 (d)." G5: append "Q2.A13." G6: "`0 ≤ vf ≤ 1 + 1e-12` on VERIFIED runs"
  → "`0 ≤ vf ≤ 1` exactly where no listed amount is negative, otherwise within Σ|negative amounts|/N_P of [0, 1]
  (Q4.R10, R11; Q4.A13 (a), (d))". G7: append "Q1.A15 (c); Q4.A14 (a)–(c)." New: "**G16 The report's decision near a
  phase boundary.** Q4.A15 (a)–(e); the counts of (e) recorded in the manifest."
- **N10.** §12 "Riskiest point": append "Ruled by Q4.R12 (Amendment 5): the raw flash stays;
  `flash_near_phase_boundary` and the quoted `independent_split` rows mark where the verifier may have decided
  otherwise; G16." §13: append "Ruled 2026-11-06 (foundation rulings Amendment 5): SQ-ST-1 Q4.R10, SQ-ST-2 Q1.R11,
  SQ-ST-3 Q4.R12, SQ-ST-4 Q1.R12, SQ-ST-5 Q2.R11, SQ-ST-6 Q4.R11."
- **T1.** `target-architecture.md` item 13 (Phase routing): the bullets from "VAPOR, or a lone `vapour_like` FLUID
  (Q4.R9), goes to `vapor`" through "flags `near_threshold`;" → "- the vapour group (VAPOR and `vapour_like` FLUID)
  goes to `vapor`, else to the first liquid port when `vapor` is null; - the liquid group (the other fluid phases) goes
  over `light_to_heavy` by mass density, ascending (with two `split` candidates, today's routing exactly; with one fluid
  phase, Q4.R9); characters are fixed with the routing at the opening, and |q − q*| ≤ 10 τ_char |q*| flags
  `near_threshold` (Q4.R13);". In the closure paragraph: "(one transposition of density-adjacent phases, or the lone
  phase's other port)" → "(one transposition of density-adjacent liquid-group phases, or one phase moved between the
  groups)"; "(Q4.R9)." at its end → "(Q4.R9, R13)."

**New findings, listed and not fixed.**
- **A5-a.** `verify.table.blocked_check` records the reason `temperature_degenerate_unlifted(<S>)`
  (`src/openflowsheet/verify/table.py:310–319`) as a string with the stream inside it, not as a code with params, so a
  report can recognise it only by parsing a rendered string, which ADR 0068 C-2 forbids. Q4.R12 (b) (ii) therefore does
  not cover that case. T05's S1 ruling makes it unreachable today. A typed reason would close it. Owner: the verifier
  (ADR 0013).

**Not established by Amendment 5.**
- Nothing has run. Every [pre] is a stated fact awaiting ST WO-1 (O-21). The sanity values come from 50-digit scratch
  evaluations of syn001's closed forms, and no generator ships with them. The ST tests compute each expectation from
  the provider's own K and h and from the verifier's helpers. Those helpers are comparators of the same code base, so
  Q4.A15 tests the report against the verifier's devices, not against thermodynamics.
- τ_β covers the SYN-001 and PR-C1 bands only where c ≤ 1e4 and x^L_NH3 ≥ 1e-2. Two kinds of stream can disagree with
  the verifier without the flag: near-critical, azeotropic or near-pure R3 streams outside that domain, and
  temperature-degenerate streams outside lifted splits (A5-a). Q4.A15 (e) catches either only at registered states.
- The vapour fraction is a label-based amount ratio. In v1 it follows the legacy split label (a supercritical fluid
  labelled VAPOR counts 1.0), and in v2 it inherits O-11's identification rule. Neither is a claim of physical
  gas-likeness. Nothing here validates a vapour fraction against steam tables beyond G2's lever rule and G3's six
  values.
- Q4.R13 makes O-11 decide the outlets of coexisting phases. It does not make any identification rule right near
  mixture critical points. Q4.A16's vectors are synthetic and test the rule against its own statement; the end-to-end
  behaviour rests on E-F6-10 (e), (f) and F6's runs.
- SYN-001 and the Wilson γ–φ method get no density until their providers declare `v` (F4). The null there is a
  capability gap, not a value.
- The report evaluates R1 phases at T_sat(P) per ADR 0051 and does not re-judge how far the stored T is from T_sat(P).
  The tolerances 64ε, 4(C + 1)ε and 8ε rest on rounding counts and τ_β on an argument with a domain; none of them is a
  measured floor yet (O-19).
