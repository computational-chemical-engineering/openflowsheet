# Foundation rulings: the nine questions of the target architecture (roadmap stage 3)

Status: design-lane rulings (`specifier`), 2026-11-02; amended in place by Amendment 1 (2026-11-02, §13), which lists
every changed clause. Brief: `docs/roadmap/brief-specifier-foundation-questions.md`.
Questions and defaults: `docs/roadmap/target-architecture.md` §6 ("the note"). Input to ADR-F2 to ADR-F5, not an ADR:
once an ADR adopts a ruling, the ADR is the authority and this document is archival input.

## 0. Authority, scope and limits

- **Scope.** The scientific semantics behind §6 Q1–Q9, as ruling clauses `Qn.Rk` an ADR can adopt verbatim, numbered
  assertions `Qn.Ak` the foundation's tests must meet, and the edits to the note (§12).
- **Consistency.** ADR 0001 D1–D5, ADR 0005 D2–D7, ADR 0007 D2.4, ADR 0011 D2, ADR 0012 and ADR 0051 D1 stay binding for
  `nTP-v1` and every v1 document. Where a ruling needs one of them amended *for v2 documents*, §10 records a finding;
  this document amends nothing. No ruling touches a v1 document, `nTP-v1`, a legacy provider or a registered fixture.
- **Departures from the note's defaults:** Q1 (enthalpy per unit mass, not molar), Q2 (anchor phase, entropy datum,
  component datum), Q3 (a conserved-group basis replaces the `apparent|true` switch), Q4 (density ordering removed), Q5
  (claim levels and witnesses), Q6 (no-redundancy rule), Q9 (two provenance axes; rights outside identity). Q7 and Q8
  confirm the default with precisions.

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

**Effect on the note.** §2.1.1: `thermal_coordinate: T | h` becomes `T | h_mass`; add Q1.R4. §2.2.1: each state-point
specification carries its quantity kind (molar or specific). §6 Q1: text corrected. §7 R4: decided, mitigated by Q1.R3.
Exits: F2 gains Q1.A5; F4 and F5 gain Q1.A1–A4, A6, A7. Amendment 1: §13 S3, N10.

## Q2. Enthalpy and entropy reference

### Ruling
- **Q2.R1** *One convention per v2 flowsheet;* the default, and for now the only one a method can be shifted to, is
  `ELEMENTAL-ref-v1`: elements in their standard reference phases at T° = 298.15 K, P° = 1e5 Pa have h = 0; each
  component in its anchor phase at (T°, P°) has h = Δf h°_c and s = s°_c (third-law absolute), both per unit of its
  amount basis. Hence `g = h − Ts`, and Σν g at (T°, P°) is Δr g°.
- **Q2.R2** *Anchor phase,* one per component per flowsheet, from its record: `ig` (ideal gas) by default; `aq` for ions
  and solutes without an ideal-gas model (infinite dilution, molality scale, conventional Δf h°(H⁺, aq) = s°(H⁺, aq) =
  0); `s:<form>` for a component modelled only as a condensed solid, `kg`-basis ones included; `l` only when the record
  has no ideal-gas value and no method in the flowsheet has an ideal-gas model for it. Every method evaluating the
  component evaluates it in that phase at (T°, P°); one that cannot is bridged (Q2.R8), and without a bridge datum it is
  refused for it (`anchor_unavailable(<method>, <component>, <phase>)`).
- **Q2.R3** *Shift.* For method m and component c, Δ_{m,c} = Δf h°_c − h^m_c(anchor; T°, P°), h^m_c being the method's
  native pure-component (for `aq`, infinite-dilution) value. Ḣ_shifted = Ḣ_native + Σ_c n_c Δ_{m,c}; S likewise with
  s°_c. The shifts are constants of the composed method, computed once at composition and recorded in its `describe()`;
  derivatives in T and P are unchanged; ∂/∂n_c gains Δ_{m,c}.
- **Q2.R4** *Component datum.* A component whose record has no formation data takes h = 0 (s = s° if given, else 0) in
  its anchor phase at (T°, P°): consistent across methods and admitted across method boundaries, refused in any reaction
  where its coefficient is non-zero (`component_not_reaction_consistent(<component>)`), admitted as an inert in a
  reactor (its datum cancels).
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
  Energy still closes at boundaries (Q1 argument 2); δ appears in the reported T jump.

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

**Effect on the note.** §2.3.6: `ELEMENTAL-ref-v1` with anchor phase, entropy datum and component datum. F4 exit: the
convention-shift clause becomes Q2.A2. §6 Q2: default replaced. §2.3 "ADRs": ADR-F4 also amends ADR 0001 D5.2 (§10).

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
- **Q3.R5** *Method boundaries.* A method m′ may evaluate a stream on basis (A, R) iff its invariants are a linear image
  b′ = C b, which holds when R′ ⊇ R; with fewer fast reactions it is refused (`species_basis_incompatible(<method>,
  <S>)`).
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
- **Q3.A5** *Boundary.* A method with R′ ⊊ R is refused; with R′ ⊋ R it is admitted and b′ = C b exactly (integer C).

**Effect on the note.** §2.1.1: `species_basis: apparent|true` becomes `conserved_basis: {groups, A, R_ref}` with
presets `apparent` and `true`. §2.1.4 and §2.2.8: one object. §6 Q3: the true basis is available from F2 (preset R = ∅),
not "later".

## Q4. Phase labels

### Ruling
- **Q4.R1** *Phase id* = (family, qualifier, ordinal): family ∈ {VAPOR, LIQUID, SOLID}; qualifier none for VAPOR and
  LIQUID, and for SOLID a component (pure solid, with a form id when the record lists polymorphs) or a solid-solution
  model id (an isotherm for an adsorbed phase, Q8.R7); ordinal k ≥ 1. Rendering: `VAPOR`, `LIQUID`, `LIQUID.2`, …,
  `SOLID.<qualifier>[.k]`. The rendering must be **injective over the whole id alphabet** `[A-Za-z0-9_.:-]` (component
  ids may contain `.` and digits); F2 fixes the spelling under that constraint, for example with a separator outside
  the alphabet at the qualifier boundary.
- **Q4.R2** *Interchangeable slots.* Phases of one family and qualifier share one phase model and are interchangeable.
  Their canonical active subsets are prefixes (ordinals 1..k, no gaps), adjacency on such a family is a count change of
  ±1, and note §2.2.3's lattice is taken over these counts. With the two legacy candidates this is ADR 0005 D2 exactly.
- **Q4.R3** *Canonical order* within a family and qualifier: lexicographic ascending on a key vector, compared
  **exactly** (IEEE, signed zeros normalised; richer in the first differing key → higher ordinal). Key vector: x over
  the declared `phase_order_keys`, else water (InChIKey `XLYOFNOQVPJJNP-UHFFFAOYSA-N`) if present, then every other
  component in definition order; last, the phase's mass. x is the mole fraction on the method's composition basis. This
  is a total order (phases tied on every key are bitwise identical, so their order leaves the state unchanged);
  thresholds only flag (Q4.R5). τ_comp = 1e-6. Density is not used.
- **Q4.R4** *When.* Labels are assigned at every attempt opening and at every converged closure; within an attempt,
  labels and variable ids never change. A closure whose canonical order differs from the attempt's labels is relabelled
  by permutation (bitwise exact) and recorded `relabel(<point>: <from>-><to>, …)`. Root fingerprints use canonical
  labels.
- **Q4.R5** *Flags.* For each pair adjacent in canonical order, the deciding key is the first on which they differ; if
  its |Δx| ≤ 10 τ_comp the order is flagged `near_threshold` (ADR 0007 D2.4). If max_c |Δx_c| ≤ τ_comp over all
  components, the pair is indistinguishable (coexisting phases this close occur only near a critical point): flagged,
  and the point carries Q5.R4's `near_critical` limitation.
- **Q4.R6** *VAPOR and LIQUID under one fluid model* (an EOS) name root-selection models. A single phase in the
  single-root region evaluates identically under both and takes, at the opening, the label of the method's declared
  vapour–liquid identification rule. A single phase's label change between attempts is an ordinary phase-set update
  (non-adjacent restart, ADR 0005 D4), recorded. Its cost is O-3.
- **Q4.R7** *Legacy rendering.* A point with candidates {VAPOR, LIQUID} renders `LIQUID`, `VAPOR`, `TWO_PHASE` as today;
  `ZERO_FLOW` stays a stream property.

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
  reversed gives identical labels and state vectors that are bitwise permutations; the water-rich liquid is LIQUID.2.
- **Q4.A2** *Prefix* (R0 scan over every v2 record). No record has LIQUID.k or SOLID.q.k active without k−1 active.
- **Q4.A3** *Relabel.* A registered path on which a liquid disappears and reappears emits `relabel(…)`, and its final
  state compares `SAME` under `same_root` with a run opened directly in the final set.
- **Q4.A4** *Total order* **[gen]**. Liquids over (water, A, B) with x_water = 0.1, 0.1 + 7e-7, 0.1 + 1.4e-6 and x_A =
  0.6, 0.5, 0.4 (a cycle under the former thresholded rule) get labels in that order from all six input orders, both
  pairs flagged, none indistinguishable; 10⁴ random near-tied triples likewise; two water-free liquids (+0.0 = +0.0)
  are decided by the next key.
- **Q4.A5** *Injectivity* **[gen]**. 10⁴ random triples plus adversarial qualifiers (`a.2`, `2`, `a:b`, `SOLID`, `-`, a
  component id equal to a model id) give no colliding rendering.
- **Q4.A6** *Lattice.* With candidates {VAPOR, LIQUID, LIQUID.2}, {VAPOR, LIQUID} is adjacent to {VAPOR, LIQUID,
  LIQUID.2}, and {LIQUID.2} alone is never constructed.
- **Q4.A7** *Legacy.* F5's decision equivalence holds with two-candidate rendering.

**Effect on the note.** §2.1.5: the triple and injectivity. §2.2.2–2.2.3: prefix rule and count lattice; exact order
with flags (Q4.R3, R5). §6 Q4: density removed; water the default key.

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
  τ_comp), is not a witness. **τ_tm = 1e-8**; near-threshold band (ADR 0007 D2.4) |tm*_min| ∈ [1e-9, 1e-7].
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

**Effect on the note.** §2.2.6, §2.2.9: claim levels, witness, trial-set id. F5 exit: τ_tm and the band. §6 Q5:
near-pure trials per component (not "per liquid candidate"), exact levels, witnesses. §8:
`SolutionCertificate.phase_stability` carries claim level, witness and trial-set id. §7 R9 unchanged. Amendment 1: §13.

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
and the boundary report says so.

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

No ruling breaks a foundation's premise. Q6.R2 changes F2's probe design (a third probe) and Q3.R1 changes the meaning
of F2's `species_basis` field; both are inside F2's scope.

## 11. Open questions, each with a recommended default

| # | Question | Kind | What settles it | Default |
| --- | --- | --- | --- | --- |
| O-1 | PH-solver tolerance at elemental magnitudes (Q1.A1's margin) | fact | F4 measures the achieved `ĥ` residual on the IAPWS-95 probes | 1e-12 relative |
| O-2 | τ_tm against F5's equilibrium noise | fact | max \|tm*\| of active phases used as trials at the registered converged states | τ_tm = 1e-8 if the noise is ≤ 1e-10; otherwise amend |
| O-3 | Single-phase label flips for one-fluid-model methods on supercritical paths (Q4.R6) | fact | extra attempts on F5's registered supercritical paths | Q4.R6; above one extra attempt per path, an F5 amendment merges single-fluid {VAPOR} and {LIQUID} into one node |
| O-4 | τ_spin = 1e-4, τ_crit = 1e-2 (Q5.R4) | fact | λ_min(B) and c3 against distance to the critical point on one registered EOS system | 1e-4 and 1e-2 |
| O-5 | τ_comp = 1e-6 | fact | cross-platform agreement of converged x on the X07a legs | 1e-6 |
| O-6 | Water as default first key (Q4.R3) | Frank's preference | — | water first; alternative: component order only |
| O-7 | Mass-specific `ĥ` as the raw coordinate in state documents | Frank's preference | — | mass-specific; reports show specific and molar h |
| O-8 | Cost of N near-pure trials for large N (assays) | fact | F5 times N = 50 | all components; a reduced set keeps claim level `local` |
| O-9 | τ_mono = 1e-12 against the moment rounding floor (Q6.R5) | fact | F2's worst relative deficit on monodisperse probe streams, a recycle of loop gain 100 included | 1e-12; amend if the margin falls below 10× |

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
- Amendment 1 adds the edits listed per finding in §13.

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

**Not established by Amendment 1.** Its numbers are closed forms, synthetic constants or the in-repository water record;
τ_mono's floor is a scratch measurement, τ_crit and c3's accuracy are unmeasured on an EOS (O-4, O-9); nothing has run.
