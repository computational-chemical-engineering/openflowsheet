# ADR 0064 — F5: phase-equilibrium framework, stability, the discrete-coordinate contract

**Status:** **Proposed, 2026-11-05.** W1 pass P2; Accepted after the W1 P2 reviewer pass; built in 0.6 on `wp/F5`.
**Author:** design lane (`architect`). **Refines:** `target-architecture.md` §2.2, §3 F5. **Adopts verbatim:** Q4.R2–R8
and Q4.A1–A11 (Amendment 2, S5); Q5.R1–R8 and Q5.A1–A10; Q8.R7, Q8.A3, A5, A7; Q1.A3, A4, A7; Q3.R6. Legacy providers
and their delegating compositions stay `split` (Amendment 2). **Amends:** ADR 0005 for v2 (count lattice,
`relabel`, `root_switch`, discrete-coordinate product); ADR 0051 D1 and ADR 0012 for v2 documents; `SolvePolicy`
(`phase_contract` value `F5-phase-contract-v3`); `SolutionCertificate` (one optional field, D7). Builds on ADR 0062
(`PhaseId`, set rendering) and ADR 0063 (`MaterialModel`, composed methods).

## Decisions

### D1. Service (`openflowsheet/phase/`)

`flash(inputs, spec, candidates, method, basis) -> EquilibriumResult(phases: tuple[PhaseOutlet(phase: PhaseId, n,
T, P, v̂, character?), …], signature, stability: StabilityReport, records)`; `stability(state, active, trial_set) ->
StabilityReport(tm_min, witness, W_p and ι_p per next slot, trial_set, claim, near_threshold, reason)`. Specs `TP, PH,
PS, TV, PBETA(<phase>), TBETA(<phase>)` with quantity kinds (ADR 0062 D2). Providers answer TP evaluations only.

**Unrestricted flash** (openings, discovery): Michelsen's stage-wise scheme. Start from the opening's candidate single
phase of least Gibbs energy at the feed; repeat { stability over the trial set; if a witness, add a slot seeded from W
(next ordinal of its family and qualifier); solve the equilibrium at the enlarged set; drop a slot whose amount is ≤ 0
} until stable or `max_phases` = candidate count. Non-TP specs: outer safeguarded Newton (bracketed) on T, or on the
spec variable, over the TP solve. **Equilibrium at a fixed set** (inside an attempt, procedural): unknowns
ln n_{p,i} for every active slot, residuals ln f_{p,i} − ln f_{ref,i} = 0 and component balances; successive
substitution (≤ 5 steps) then Newton with Gibbs-descent line search; derivatives to the outer problem by the
implicit-function theorem on the converged residual Jacobian. Ln-fugacity residual target ≤ 1e-10 (O-2).

### D2. Trial sets (F1 kind `stability_trial_set`; built-in `F5-trials-v1`, core)

Payload: ordered generators `wilson_vapour` (W = zK), `wilson_liquid` (W = z/K), `near_pure[i]` for each z_i > 0
(others 1e-10), each a local minimisation of tm* in Michelsen's α-variables (SS then Newton, tolerance 1e-12 on the
gradient); triviality per Q5.R3 (τ_comp, plus the root rule under FLUID); ties by generator order. Pure-solid and
one-component confined candidates take the scalar test, claim `exact`. A method may select another registered set.

### D3. Contract value `F5-phase-contract-v3`

Discrete coordinates are F1 `discrete_coordinate` descriptors; F5 ships `phase_set` (per state point; one count chain
per family and qualifier; TX and X25 add theirs). Attempt signature = tuple in plan order of (coordinate, point, value
rendering); adjacency per the note §2.2.3 verbatim. ADR 0005 D2–D7 carry over with "regime" read as "discrete
coordinate". **Dispatch:** a solve whose every phase-selecting point is a two-candidate point of a `split` legacy or
delegating method runs the existing T05b controller code unchanged (same functions; the record carries the new value);
any other solve runs the generalised controller (`phase/contract.py`). Labels: Q4.R3 order at openings and closures,
`relabel(...)` and `root_switch(...)` records.

### D4. Regime discovery (FB-04 (2))

Every opening runs D1's unrestricted flash at the initializer's state for each point; the result is the opening
signature. v2 `phase_assertion` (preview) is checked at closure (`phase_regime_mismatch`); v1 keeps ADR 0051 D1. The
FB-04 turbine's isentropic reference is a PS state point with candidates = the method's; no phase is declared.

### D5. Indicators (Q5.R8)

ι_p = tm*(W_p) for the next slot per family and qualifier, W_p continued from the previous evaluation by one local
Newton solve; defined iff non-trivial and λ_min(B) > 0, else `indicator_untracked`. Closed forms for pure solids and
composition-free K. FLUID: one W per distinct non-trivial minimum found at the opening; ι = their minimum.

### D6. Confined phases beside a FLUID model (A2-c)

Two representations of a phase rich in the confined component are both admitted by default, and the stability test
decides by Gibbs energy (a lower-Gibbs unconfined witness fails the point; generically only one is active). A method
may declare `confined_exclusive: [<component>]` (the X21 free-water choice): its unconfined model then omits that
`near_pure` trial and no unconfined slot whose largest mole fraction is that component (ties by definition order) is
a witness or opened; every pass is then at most `local`, with limitation `confined_exclusion(<component>)`. X21 decides
its method's declaration.

### D7. Certificate and verifier

`SolutionCertificate` gains `phase_report: PhaseReport | None = None`, **omitted from every serialization and from
`r0_projection` when `None`** (legacy certificates byte-identical; F0 M3/M5 prove it). `PhaseReport` per point:
signature rendering, labels, relabels, `phase_stability {result, claim_level, witness: {W, tm, trial} | null, trial_set,
reason, near_threshold, tm_min}`. The verifier's independent implementation (`verify/phase_check.py`, no import of
`phase/`) re-checks equilibrium residuals, non-negative amounts, stability at its claim level and every witness with a
fresh composition (Q5.A3). Unsupported reasons: `no_fugacity_model`, `charged_species_tpd`, `near_critical`,
`near_spinodal`.

### D8. Formulations and the conserved-basis slot

Procedural (default); `smooth` reserved; `lifted` refused `formulation_unsupported(lifted)`. The slot is ADR 0062's
basis object (A, R); F5 solves A = I, R = ∅ only and refuses R ≠ ∅ `capability_missing(…, conserved_basis)` until X13.

## Alternatives rejected

- *The generalised controller for legacy two-candidate solves*: decision equivalence would rest on re-deriving T05b;
  dispatch makes it true by construction, and E-F5-2 still tests the generalisation.
- *Exclusive confinement as the default* (A2-c): suppresses a real instability silently; a declaration says so.
- *Gibbs minimisation in a global solver*: no guarantee at acceptable cost (Q5 rejected list).

## Migration proof

F0 PASS; decision equivalence: every corpus case under `F5-phase-contract-v3` gives identical attempt and event
sequences, signatures and bitwise floats; only `policy_sha256` differs.

## Exit tests

- **E-F5-1** Decision equivalence (dispatch path) over the corpus. **E-F5-2** The same with the generalised controller
  forced (test seam) on every two-candidate point: identical R0 sequences and bitwise floats.
- **E-F5-3** Q4.A1–A11; Q5.A1–A10 (100 % at τ_tm = 1e-8, every registered feed outside [1e-9, 1e-7]).
- **E-F5-4** Registered LLE and VLLE systems: phase compositions within 1e-8 absolute of an independent 50-digit
  implementation; Q1.A3, A4, A7. Default systems (specifier registers): symmetric Margules A = 2.4 with ideal gas and
  synthetic Antoine (`split`); `cubic.pr-v1` water/n-hexane with a synthetic-labelled k_ij (`single`).
- **E-F5-5** Q8.A3, A5, A7. **E-F5-6** FB-04 turbine, no declared phase: `VERIFIED`, outlet `h` within the registered
  tolerance of an independent IAPWS-95 evaluation. **E-F5-7** Q5.A9 (c). **E-F5-8** D6 both ways on Q4.A10's fixture.
- **E-F5-9** O-2: max |tm*| of active phases as trials at the registered converged states ≤ 1e-10; O-8: N = 50 timing
  logged.

## New catalogue codes

`phase_inactive`, `inactive_phase_read`, `indicator_untracked`, `relabel`, `root_switch`, `confined_exclusion`,
`formulation_unsupported`, `no_fugacity_model`, `charged_species_tpd`, `near_critical`, `near_spinodal`,
`reactivation_seed_unavailable`.

## Work orders (`wp/F5`; after F4-WO4)

| # | WO | Files | Acceptance | Identity | Lane |
| --- | --- | --- | --- | --- | --- |
| 1 | **F5-WO1** Stability and trial sets | `phase/{stability,trials}.py`; `F5-trials-v1` descriptor | Q5.A1–A7, A10 | no | Opus |
| 2 | **F5-WO2** N-phase flash, specs, labels | `phase/{flash,order,labels}.py` | E-F5-3 (Q4), E-F5-4, -5 | no | Opus |
| 3 | **F5-WO3** Contract v3 and dispatch | `phase/contract.py`; `solve-policy` enum value; discrete-coordinate descriptor | E-F5-1, -2 | no | Opus; reviewer-adjacent |
| 4 | **F5-WO4** Indicators, certificate, verifier | `phase/indicators.py`; `verify/phase_check.py`; certificate field | Q5.A8, A9; E-F5-7; F0 M3/M5 | no | Opus |
| 5 | **F5-WO5** FB-04 and confinement | registered cases; D6 | E-F5-6, -8, -9 | no | Opus |
| 6 | Close-out | manifest, catalogue, gate, CI | all E-F5 | no | Sonnet |

**Unblocks:** F6 (port routing of FLUID phases by density or `character`, fixed at openings and recorded, A2-b; zero-
holdup forms of Q1.R8 belong to F6/F7), PrISMa (Q8.R7), X21 (D6), X13 (the slot).

## Risks (each with a default)

1. **E-F5-2 may fail** where T05b's choices are not the count lattice (fact). Default: dispatch keeps E-F5-1; a failure
   goes to the reviewer as a finding on ADR 0005's generalisation.
2. **Root continuation near merging roots** (D09 limitation; fact). Default: `near_critical`/`near_spinodal` unsupported.
3. **Registered LLE/VLLE systems** need the specifier's registration (design lane). Default: E-F5-4's two systems.

## Edits `target-architecture.md` needs

§2.2.1–2: Amendment 2's FLUID text and `root_switch`; §2.2.3: dispatch; §2.2.6: `EquilibriumResult`, TP-only providers;
§8: `FlashResult` row → `EquilibriumResult`, certificate row → optional `phase_report`; §9.4 (1): `FLUID(water)` and D6;
§3 F5 exit: "Q4.A1–A7" → "Q4.A1–A11", "Q5.A1–A9" → "Q5.A1–A10", add E-F5-2.
