# S01 — countercurrent equilibrium-stage subsystem: derivation and test specification

Design lane (`specifier`), 2026-10-21. Package S01 (plan v1.2 §4.5, `docs/implementation-plan.md:281`), brief
`docs/briefs/S01-specification.md`. Reference generator `docs/derivations/scripts/s01_reference.py` (mpmath, 50 digits;
`--check` re-derives 153 claims and byte-compares `s01_reference.json`). Decisions are logged in `docs/S01_DECISIONS.md` and
registered as R-505 to R-509. **Amended 2026-10-22 by §17** (Amendment 1, the review's rulings; R-510 to R-518): §1, §4.5,
§4.6, §5 R5/R7, §7.1, §7.3, §8, §10 (state tolerance, A05, A10, A18). **Amended 2026-10-26 by §18** (Amendment 2,
S08b; R-791): §8.

## 0. Authority and scope

This document is normative for S01. It composes with ADR 0001 (units, `nTP-v1`, zero flow, signs), ADR 0005 (phase-attempt
contract), ADR 0008 D3 (balance orientation, accumulation), ADR 0010 D2–D3 (specification continuation, recovery edge 3) and
ADR 0012 D1–D4 (saturation band, PH-type kernel, `T05b-phase-contract-v2`, `ZERO_FLOW`). It reopens none of them and changes
no frozen interface (`docs/interfaces-frozen.md` §1–§3): **no ADR is needed** (DECISION 9). Provider: SYN-001 only
(`thermo/syn001.py:292-325`). PR C1 is vapour-only and cannot form a stage.

**What it establishes.** The equations of an N-stage countercurrent cascade (§2), its DOF and specification set (§3), per-stage
phase and zero-flow handling (§4), refusals (§5), an analytic initializer (§6), the solve path: an isothermal pre-solve, then
the target, then ADR 0010 D3 continuation on failure (§7), its acceptance rule (§8), registered cases (§9), assertions
S01.A01–A20 (§10), work orders (§12) and the manifest check list (§13).

## 1. Conventions

- Stages `j = 1..N`, numbered **top to bottom**. Liquid flows down (stage j to j+1), vapour flows up (stage j to j−1).
  Components `i ∈ (A, B, C)` in that order, `C = 3`.
- External inlets (ports): `top` enters stage 1 as liquid, `bottom` enters stage N as vapour, and zero or more `side` feeds at
  a declared stage with a declared phase. Outlets: `top_vapour` (stage 1's vapour) and `bottom_liquid` (stage N's liquid).
  There is no condenser, reboiler or reflux. Those are S02's.
- SI throughout (ADR 0001 D1). Duty `Q_j` is positive into stage j (ADR 0001 D4.1). Balance rows read `inflow − outflow (+ Q)`
  (ADR 0008 D3.3).
- Enthalpy flows are SYN-001's `Ḣ = Σ n_i h_i^phase(T, P)` (SYN-001.md §2). An internal stream has the state of the stage it
  leaves: the liquid from stage j−1 is at `(T_{j−1}, P_{j−1})`, the vapour from stage j+1 at `T_{j+1}`.

## 2. Variables and rows (normative)

Per stage j (14 columns, 14 rows):

| Columns | Count | Rows | Count | Kind |
| --- | --- | --- | --- | --- |
| `l_ij` liquid out, `v_ij` vapour out | 2C | `mix_ij`: `(l_{i,j−1} or top_i) + (v_{i,j+1} or bottom_i) + Σ side_i@j − m_ij` | C | molar_flow, algebraic |
| `m_ij` lifted mixed inflow (the split's feed) | C | `mole_ij`: `m_ij − v_ij − l_ij` | C | molar_flow, holdup_balance |
| `L_j`, `V_j` lifted totals | 2 | `eq_ij`: `v_ij L_j − K_i(T_j,P_j) l_ij V_j` (`rows.equilibrium_row`) | C | molar_flow_squared |
| `T_j` | 1 | `Ldef_j`, `Vdef_j` (`rows.definition_row`) | 2 | molar_flow |
| `P_j` | 1 | `energy_j`: `Q_j + Ḣ_in − Ḣ^V(v_j,T_j) − Ḣ^L(l_j,T_j,P_j)` (`rows.energy_row`, `source=Q_j`) | 1 | heat_rate, holdup_balance |
| `Q_j` | 1 | `P_j − P_j*` and `Q_j − Q_j*` (`rows.specification_row`) | 2 | pressure; heat_rate |

Per external inlet k (C + 2 columns `n_ik, T_k, P_k`, fixed by C + 2 specification rows, the `syn001.feed` pattern). An inlet's
enthalpy uses its declared phase and its own `(T_k, P_k)`.

**DOF.** Columns `= Rows = 14N + 5·n_in` (`n_in = 2 + n_side`). Before specification, `DOF = 2N + n_in(C + 2)`: per stage
`P_j` and `Q_j`, per inlet its `nTP` state. This is the classical count for a simple countercurrent cascade. Generator claims
`dof.*` check it for every case. Writing equilibrium division-free keeps every row finite at a vanished phase or an absent
component (ADR 0001 D3.2). The trivial splits `V_j = 0` or `L_j = 0` also satisfy `eq_ij`, so the phase contract (§4), not
the rows, excludes them (rows.py:133).

**Overall closure (derivation).** Summing `mix + mole` over j: every internal stream appears once with `+` and once with `−`,
so `Σ_inlets n_ik − v_i1 − l_iN = 0` at any root. Summing `energy_j`: each internal enthalpy flow appears in exactly two rows
with opposite signs, evaluated at the same state, so `Σ_j Q_j + Σ_k Ḣ_k − Ḣ(top_vapour) − Ḣ(bottom_liquid) = 0`.

**N = 1 (derivation).** The stage's rows are `syn001.ph_flash`'s rows (`ph_flash.py:140-202`) with inlet `m_1`. Its root is
the PH flash of the mixed inlet at `Ḣ_top + Ḣ_bottom + Σ Ḣ_side + Q_1`.

## 3. Specification set

Fixed: every inlet's `(n, T, P)` and declared phase (`LIQUID` or `VAPOR`), N, side-feed stages, `P_j*`, `Q_j*` (`0` =
adiabatic). Free: every stage variable. Q is a variable pinned by a specification row (the `PHF-Q` pattern), so ADR 0010 D2
can continue it. No other specification (stage temperature, product flow, recovery) is offered in S01. Those are S02's
conventions.

## 4. Energy and phase coupling (composition with ADR 0005 and ADR 0012)

1. **Each stage is one lifted split, PH-type** (ADR 0012 D3: its energy row fixes its temperature). Its `LiftedSplit`
   (`region.py:186`) is: `feed = m_j`, `temperature = T_j`, `pressure = P_j`, `vapor = v_j`, `liquid = l_j`, totals `V_j`,
   `L_j`, `equilibrium_rows = eq_·j`, definitions `Vdef_j`, `Ldef_j`. Lifting `m_j` (DECISION 3) is what lets the existing
   descriptor, the PH kernel `ph_state(m_j, P_j, H_split)` and the dormancy test ("feed flows all `+0.0`") apply unchanged.
2. **Regimes** are ADR 0005 D2's lattice plus ADR 0012 D4(c)'s `ZERO_FLOW`. The pins and drops are `LiftedSplit.pinned/dropped`
   (`LIQUID`: pin `v_j, V_j`, drop `eq_·j, Vdef_j`; `VAPOR` symmetric) and the stage's `ZeroFlowForm`: pin `l_j, v_j, L_j, V_j`;
   drop `eq_·j, mole_·j, Ldef_j, Vdef_j`; swap `energy_j` for the label row `T_j − T_label`. Each regime pins as many columns
   as it drops rows (generator claim `per_regime_pinned_dropped`).
3. **Label (DECISION 4).** `T_label(j) = T_{j−1}` for j > 1, and `T_label(1) = T_top`. A dormant stage takes the temperature of
   the liquid that would enter it from above.
4. **Contract literal.** `SolvePolicy.phase_contract = "T05b-phase-contract-v2"`. Screens, restarts, disappearance (core ends
   `BOUND_BLOCKED` on a watched total), cycle rule, `max_attempts = 5` and records are `solve_region`'s (`region.py:1666`),
   called unchanged. S01 does not write a controller (DECISION 1).
5. **Typed failures** (no new outcome values): every `SolveOutcome` that `solve_region` can return, plus §5's refusals.
   - A dormant stage whose swapped `energy_j` does not hold (`Q_j* ≠ 0`) ends `SPECIFICATION_CONFLICT`,
     `zero_flow_conflict(<energy_j id>)`.
   - A failed pre-solve ends `INITIALIZATION_FAILED`, `initialization_failed(s01-isothermal-presolve-v1, <outcome>)`.
6. **All inlets exactly dormant** (ADR 0001 D3.1). This is answered in closed form without a Newton solve:
   - every stage `ZERO_FLOW`, every flow `+0.0`, `T_j = T_top` (the label chain);
   - outcome `CONVERGED` if every `Q_j* = 0`, else `SPECIFICATION_CONFLICT` at the first nonzero stage.
7. **Partial dormancy** (some stages dormant, others flowing) is **not claimed** (§14; DECISION 5). Whatever the solve returns
   must be one of item 5's typed outcomes, or a root that passes §8.

## 5. Refusals (validation, before any evaluation)

Each refusal carries `CAPABILITY_UNAVAILABLE` (`unsupported(...)`) or `INVALID_SPECIFICATION`, with the code below:

| Id | Condition | Code |
| --- | --- | --- |
| R1 | N not an integer ≥ 1 | `invalid_spec(stage_count)` |
| R2 | an inlet flow negative or non-finite | `invalid_spec(inlet_flow:<port>)` |
| R3 | an inlet T or P, or a `P_j*`, outside the SYN-001 domain | `invalid_spec(domain:<id>)` |
| R4 | a side feed at a stage ∉ 1..N, or two side feeds at one stage | `invalid_spec(side_feed_stage:<port>)` |
| R5 | a flowing inlet whose declared phase fails R-007 admissibility (liquid: `Σ z_i K_i ≤ 1`; vapour: `Σ z_i/K_i ≤ 1`) | `inadmissible_inlet(<port>, <phase>)` |
| R6 | a declared inlet phase other than `LIQUID`/`VAPOR` | `unsupported(two_phase_inlet:<port>)` |
| R7 | energy precheck: `H* = Σ_k Ḣ_k + Σ_j Q_j*` outside `[Σ_i F_i h_i^L(T_min, P_N), Σ_i F_i h_i^V(T_max)]` | `infeasible_spec(energy_outside_domain)` |

R7 is necessary, not sufficient: no in-domain state can carry `H*`, because `max h^L < min h^V` (a generator claim).

## 6. Initializer `s01-kremser-cmo-v1` (analytic)

1. `F_i = Σ_k n_ik`, `F = Σ F_i`, `z = F_i/F`. If `F = 0`, use §4.6.
2. `β̄ = Σ_{vapour inlets} n_k,tot / F`, clamped to `[0.1, 0.9]`, and `P̄ = (1/N) Σ P_j*`.
3. `T̄ = T(β̄)` of `z` at `P̄`: ADR 0012 D1's band temperature, `saturation_band.band_temperature`. If it lies outside the
   domain, end `INITIALIZATION_FAILED`, `initialization_failed(s01-kremser-cmo-v1, tbar_outside_domain)`.
4. CMO totals: `L_j = Σ_{liquid inlets at stage ≤ j} n_k,tot` and `V_j = Σ_{vapour inlets at stage ≥ j} n_k,tot`, each floored
   at `0.1·F`.
5. With `S_ij = K_i(T̄, P_j*) V_j / L_j`, solve per component the tridiagonal system
   `l_{i,j−1} + S_{i,j+1} l_{i,j+1} − (1 + S_ij) l_ij = −f_ij`. Here `f_ij` is the inlet flow at stage j, with the top inlet
   counted at stage 1 and the bottom inlet at stage N.
   - Solve by the Thomas algorithm without pivoting. It is stable: the matrix is irreducible and weakly column-diagonally
     dominant (column j: off-diagonal `1 + S_ij = |diagonal|`).
   - Then `v_ij = S_ij l_ij`, `L_j = Σ l_ij`, `V_j = Σ v_ij`, `T_j = T̄`, `P_j = P_j*`, `m` from `mix`, and `Q_j` from
     `energy_j`.
6. **Kremser endpoint (derivation).** When `K, L, V` are stage-independent, the recurrence
   `l_{j−1} + S l_{j+1} − (1+S) l_j = 0` has characteristic roots `1` and `1/S`. Therefore:
   - `S ≠ 1`: `l_j = a + b S^{−j}`, with `a + b = l_top` and `a + b S^{−(N+1)} = v_bot/S`.
   - `S = 1`: `l_j = l_top + j (v_bot − l_top)/(N + 1)`.
   - The generator registers N ∈ {1, 2, 5} at `V/L = 1.5` and the exact `S_B = 1` case N = 3, `V/L = 1`. It uses
     `K(360 K, P_r)`, where `K_B = 1` exactly.

## 7. Solve path (algorithm)

1. **Validate** (§5). If every inlet is dormant, use §4.6.
2. **Initialize** (§6), giving `x_K`.
3. **Isothermal pre-solve** `s01-isothermal-presolve-v1`. Same columns as the target. Each `Q_j − Q_j*` row is replaced by
   `T_j − T̄`, and `Q_j` is free. Run one K03 Newton attempt from `x_K` (via `solve_region`, signature all `TWO_PHASE`, no
   restart honoured). It must end `CONVERGED` with every stage two-phase. Otherwise end `INITIALIZATION_FAILED` (§4.5). The
   root is `x⁰`, and `Q⁰_j = Q_j(x⁰)`.
4. **Target.** Call `solve_region` from `x⁰`, `initializer_source = "s01-isothermal-presolve-v1"`, with the policy of §7.6.
5. **Recovery edge 3** (ADR 0010 D3, unchanged) if step 4 ends in one of D3's trigger outcomes. The continued parameters are
   the `Q_j*` of the promoted rows `Q_j − Q_j*`. The map is `p(λ) = Q* + (1 − λ)(Q⁰ − Q*)`.
   - **`x⁰` is an exact root of `H(·, 0)`** (DECISION 2): at `x⁰`, every row but `Q_j − Q_j*` holds, and `Q_j(x⁰) = Q⁰_j`
     by construction.
   - Controller and records are `HomotopyPolicy`'s defaults (`trace.py:542-551`): `Δλ₀ = 1/4`, `Δλ_min = 1/1024`, growth 2,
     shrink 1/2, `corrector_max_iterations = 10`, `max_lambda_trials = 64`. The homotopy never changes the signature.
   - Each λ-level is a real cascade with real duties. λ < 1 is never certified.
6. **Policy** `s01-default-v1`. It is the registered EO default with `phase_contract = "T05b-phase-contract-v2"`,
   `eo_recovery = "homotopy"` and `eo_core = "newton_refined"` (ADR 0018). Build decision: name the base policy in the build
   log.
7. **Records.** Every `branch_provenance` item, the attempt signatures (one regime per stage, in stage order), the
   `HomotopyRecord` when edge 3 fires, the pre-solve's `NewtonResult` summary, and `x_K`'s and `x⁰`'s `state_sha256`.

## 8. Acceptance of a returned state (ADR 0012 D2's pattern)

A `CONVERGED` answer is accepted only if every **declared** row of §2 is within its kind tolerance (`region.KIND_TOLERANCE`),
evaluated by the float reference evaluator (`compile.reference`) at the returned state. The declared rows are those of the
final signature after pins, drops and labels. Each `TWO_PHASE` stage has `V_j, L_j > 0`. Each `LIQUID`/`VAPOR` stage passes
R-007 admissibility at `(m_j, T_j, P_j)`. An answer that fails is a defect (`report_defect`), never a success.

## 9. Registered cases (values in `s01_reference.json`)

All pressures are `P_r` unless stated. The `top` inlet in C1–C2 is `(0.2, 0.3, 0.5)` mol/s, 330 K, liquid. The `bottom` inlet
is `(0.5, 0.3, 0.2)` at 380 K, vapour.

| Case | Why it is in the list | Expected signature; sanity value |
| --- | --- | --- |
| C1 | N = 1 equals the PH flash (A05); the smallest stage | `TWO_PHASE`; `T_1 = 360.95343981…` K |
| C2 | the nominal adiabatic cascade, N = 3 | 2P ×3; `T = 359.0453, 361.0418, 362.9218` K |
| C3 | N = 5 with a side feed at stage 3, pressures 1.00–1.08 bar, duties (−1500, 0, 1000, 0, 2500) W. Every stage index, the P-dependence of K and h, and the duty sign matter. Reversing the duty list moves T by 1.787 K (claim). The Poynting term is worth 8e-3 K (claim). | 2P ×5 |
| C4 | LIQUID disappearance, two stages | (2P, LIQUID, LIQUID); `V_2 = V_3 = 0` |
| C5 | VAPOR disappearance | (VAPOR, 2P); `L_1 = 0` |
| D1 | every inlet dormant: §4.6's closed form; `T_top = 330` K | `ZERO_FLOW` ×3; `T_j = 330` |
| D2 | D1 with `Q = (0, 50, 0)` | `SPECIFICATION_CONFLICT`, `zero_flow_conflict(<energy_2>)` |
| R1–R7 | one per refusal; R7 is C1 with `Q_1 = ±200 kW` (bounds `H_lo = −4000`, `H_hi = 88000`, `H_in = 39500` W) | the §5 code |

Every flowing case is checked in the generator:
- every target and pre-solve stage lies inside the domain;
- two-phase flows exceed 1e-4 mol/s, and single-phase stages have admissibility margins ≥ 0.02;
- the implementation's division-free rows vanish below 1e-38;
- overall closures hold;
- the generator Jacobian is regular (`σ_min ≥ 4.8e-4`).

## 10. Assertions

`ref` = `s01_reference.json`. "State tolerance" means the following:

- flows `|Δ| ≤ 1e-6·|ref| + 1e-9` mol/s, `|ΔT| ≤ 1e-4` K, `|ΔQ| ≤ 1e-2` W.
- **Above the floor:** a Newton-converged double root under `newton_refined` is expected within about 1e-9 of a 50-digit
  root. The generator's `σ_min ≥ 4.8e-4`, with K04 row tolerances, bounds the drift.
- **Below the smallest error worth catching:** a dropped Poynting term moves T on the order of 1e-3 K (80× margin), and a
  permuted duty list moves it 1.787 K.
- *Needs a fact:* WO-2 records the measured maximum deviation. The tolerance must stay ≥ 10× that measurement, and if it
  cannot, this section is amended.

| Id | Assertion | Expected | Tolerance |
| --- | --- | --- | --- |
| A01 | Declared column and row counts for C1–C5 | `ref.dof` (exact integers); per regime, pinned = dropped; row ids unique | exact |
| A02 | Initializer equals Kremser at the four `ref.kremser` entries (built through the public initializer with `K` injected) | `ref.kremser.*.l` | rel 1e-12: Thomas in double ~1e-15; a wrong boundary moves O(1) |
| A03 | Initializer on C1–C5: `β̄`, `T̄`, `L_cmo`, `V_cmo`, `l`, `v` | `ref.cases.*.initializer` | `T̄` abs 1e-8 K (band bisection to adjacent doubles); flows rel 1e-10 |
| A04 | Pre-solve root and `Q⁰` for C1–C5 | `ref.cases.*.presolve` | state tolerance |
| A05 | C1 equals `ph_state(m_1, P_r, H*)` (`ph_kernel.py:250`) and `ref` | same branch; T abs 1e-7 K; flows rel 1e-8 | both are root-finders on the same rows |
| A06 | C2 root | `ref.cases.C2.target`, signature 2P ×3 | state tolerance |
| A07 | C3 root; duty list reversed gives a different T profile | `ref.cases.C3.target` | state tolerance; reversed run differs by > 0.1 K |
| A08 | Overall component and energy closure at every converged case | 0 | `n_rows·τ_kind` |
| A09 | Every accepted state passes §8 (all declared rows, admissibility) | pass | kind tolerances |
| A10 | Compiled Jacobian vs central differences at `x_K` and C2's root. Step `h = 1e-6·max(1, |x|)`; compare `D_r⁻¹ J D_x` with `D_x` = (1 mol/s, 100 K, 1e5 Pa, 1e4 W) and `D_r` the row-kind scales | agree | 1e-6. Measured generator floor at this step: 2.9e-11 (`ref.fd_floor_C2`); a wrong ∂lnK/∂P sign is O(1) after `D_x` |
| A11 | C4 converges to (2P, L, L) with ≥ 1 restart caused by disappearance | `ref.cases.C4` | state tolerance; signature exact |
| A12 | C5 converges to (VAPOR, 2P) | `ref.cases.C5` | as A11 |
| A13 | D1 (`ref.dormant.D1`): dormant answer without Newton iterations | `outcome` `CONVERGED`; `signature` `ZERO_FLOW` ×3; `stages[*].T` = 330 K (the label chain from `inlets`' `T_top`, not the vapour inlet's 380 K); every flow `+0.0` with the sign bit checked (ADR 0001 D3.1) | exact |
| A14 | D2 conflict (`ref.dormant.D2`) | `outcome` `SPECIFICATION_CONFLICT`; `cause` `zero_flow_conflict(<cascade>:stage:2:energy)` with `<cascade>` the unit id; `swapped_energy` = (0, 50, 0) W | exact |
| A15 | R1–R6 refusals | §5 codes | exact |
| A16 | R7, both signs; C1 as registered passes | `infeasible_spec(energy_outside_domain)` | exact |
| A17 | C2 with edge 3 forced from `x⁰`: dyadic λ, `p⁰ = Q⁰` (`ref` presolve Q), λ = 1 instance equals the target's `(model_version, constants_sha256)`, final root `same_root = SAME` as A06 | — | `Q⁰` abs 1e-2 W; rest exact |
| A18 | C2 from four perturbed openings (`T̄ ± 10` K; initializer flows ×0.5, ×2) | `CONVERGED`, `SAME` as A06 | exact |
| A19 | Partial-dormancy probe (`ref.partial_dormancy`): N = 3, `top` and `bottom` dormant (330 K, 380 K), liquid side feed `(0.2, 0.5, 0.3)` mol/s at 340 K only at stage 3, Q = 0. It passes §5 (generator claims R5 and R7) | a §4.5 outcome other than a §5 refusal, or a `CONVERGED` root that passes §8. Under signature (`ZERO_FLOW`, `ZERO_FLOW`, `LIQUID`) the root is unique and analytic and passes §8 (generator claims): stage 3 a liquid pass-through, `T = (330, 330, 340)` K, so a root with that signature equals `ref.partial_dormancy.target` | never an unaccepted `CONVERGED`; `target` within state tolerance; outcome exact |
| A20 | C2 solved twice | identical final `state_sha256` and records | exact |

## 11. Generator

`s01_reference.py` is independent of the implementation: it uses 7 unknowns per stage, mole-fraction equilibrium, its own
damped Newton with complex-step derivatives, and an equal-step duty path in the registered signature. It shares only
SYN-001's closed forms and §6's initializer definition. Every numeric claim in this document is a generator claim
(`ref.claims`, 153). `--check` refuses to emit when one fails.

## 12. Work orders (`opus-engineer`, about 120k context each)

**WO-1: spec object, rows, initializer.**
- Build `models/syn001/cascade.py` (name at the engineer's choice; log it), with the specification dataclass and §5
  validation.
- Add the declared rows of §2 from `rows.py` builders, ids `<U>:stage:<j>:<kind>[:<c>]`.
- Add the §6 initializer, the §4.6 dormant answer, and a test module loading `ref`.
- Closes A01, A02, A03, A13, A14, A15, A16.

**WO-2: compile and solve.**
- Compile to `ProblemSpec` and `CompiledProblem`. Build per-stage `LiftedSplit`, `ZeroFlowForm` (with the label) and
  closure types (PH).
- Implement the §7 pre-solve and the `solve_region` call, plus §8 acceptance and outputs.
- Closes A04, A05, A06, A07, A08, A09, A10, A20. Records the A04/A06 deviation measurement.

**WO-3: phases, continuation, perturbation, evidence.**
- Forced edge 3, C4/C5, perturbations and the A19 probe.
- Writes `evidence/S01/<commit>/manifest.json`.
- Closes A11, A12, A17, A18, A19.

## 13. Evidence manifest check list

- `status: tested` requires a passing test for each of A01–A20, each citing its assertion id.
- `s01_reference.py --check` passes at the manifest commit.
- `ruff check` and `ruff format --check` are clean, and `scripts/gate.sh` passes before merge.
- The A04/A06 measured deviation is recorded with its commit.
- The manifest lists §14 verbatim as limitations.
- `reviewed` is set only by the `reviewer`.

## 14. What this does not establish

- **Synthetic data only.** No real-chemistry or column validation; SYN-001 is a fixture.
- **No S02 scope:** no condenser, reboiler, reflux, product-rate or temperature specifications, and no stage-indexing
  conventions beyond §1.
- **No uniqueness or global convergence.** No claim beyond the registered cases and A18's four perturbations.
- **No partial-dormancy convergence** (A19 asserts no false success; the analytic root it registers is not claimed reachable).
- **No two-phase inlets.**
- **No inside-out or rate-based method.**
- **No sensitivities.**
- **The generator's agreement validates the transcription of SYN-001**, not the property model.

## 15. Open questions (each with a default)

1. *Needs a fact.* Does `solve_region` accept a pre-solve with restarts disabled, and an opening that is not a traversal start
   without a schema change? **Default:** yes, via `initializer_source` and a policy with `max_attempts = 1` for the pre-solve.
   If not, the pre-solve runs `solve_newton` directly, logged as a build decision.
2. *Needs a fact.* Do C4 and C5 reach their signatures within `max_attempts = 5` from the all-2P opening? **Default:** assert
   it (A11, A12). If measurement fails, amend this spec, do not relax the assertion.
3. *Needs the user's preference.* Is partial dormancy acceptable as unclaimed for S01? **Default:** yes (`FRANK_QUESTIONS.md`).

## 16. Decisions

- DECISION: S01 form → a unit-layer cascade (rows, initializer, pre-solve) that calls `solve_region` unchanged. Alternative: its own attempt controller, or N stage units on the traversal path. Reversible by: S02 registering the stage rows as library units.
- DECISION: continuation easy endpoint → the isothermal pre-solve root `x⁰`, an exact root of ADR 0010 D2's `H(·,0)` with `p⁰ = Q(x⁰)`. Alternative: a K-value/CMO model homotopy (not a real flowsheet at λ < 1; needs an ADR). Reversible by: an ADR adding a model homotopy.
- DECISION: split feed → lift `m_j` (C extra columns and rows per stage, DOF-neutral). Alternative: widen `LiftedSplit.feed` to sums (moves its registered digest). Reversible by: an ADR widening `LiftedSplit`.
- DECISION: dormant-stage label → `T_{j−1}` (`T_top` for j = 1). Alternative: the vapour inlet's temperature. Reversible by: amending §4.3 (no registered identity uses it yet).
- DECISION: partial dormancy → not claimed; A19 asserts no false success. Alternative: a structural-dormancy opening rule. Reversible by: a later package adding the rule and an assertion.
- DECISION: inlets → declared single-phase only; two-phase is `unsupported`. Alternative: lifting an inlet split. Reversible by: adding the lifted inlet form.
- DECISION: β̄ clamp → [0.1, 0.9] and CMO floor 0.1·F. Alternative: unclamped (the pre-solve degenerates at β̄ ∈ {0, 1}). Reversible by: changing two constants and re-emitting `ref`.
- DECISION: inlet pressure vs stage pressure → no relation in S01 (enthalpy at the inlet's own state). Alternative: an equality row. Reversible by: S02's feed conventions.
- DECISION: ADR 0043 → not needed (no ADR or frozen interface changes). Alternative: an ADR for the pre-solve. Reversible by: writing it if review disagrees.

## 17. Amendment 1 (2026-10-22, design lane `reviewer`): rulings of the S01 review

Review `docs/reviews/S01-review.md`; register R-510 to R-518. Each item replaces the text it names. No generator claim
moves and `s01_reference.json` is not re-emitted. Items 5–7 change tolerances or a step rule; each comes with the
derivation that shows the registered value was wrong. None of them was chosen to make a test pass.

1. **§5 refusals are validation results, not solve outcomes (R-510).** `INVALID_SPECIFICATION` is S01's refusal
   category. It is not a `SolveOutcome`, and none is added (§4.5 stands). R6 keeps `CAPABILITY_UNAVAILABLE`, which T02
   §7.4's `PlanRefusal` already carries before any evaluation. A refusal (`CascadeFailure`) never enters a trace, a
   `RegionResult` or an outcome field. A binding that exposes the cascade maps `INVALID_SPECIFICATION` to its existing
   invalid-request error (`models.SpecificationError`).
2. **R7's scope (R-511).** R7 applies only when `F > 0`. With every inlet dormant, its interval is `[0, 0]` and it would
   refuse exactly when `Σ_j Q_j* ≠ 0`. That set is contained in §4.6's conflict set (any dormant stage whose energy row
   fails), and §4.6 also names the stage. §7.1 therefore reads: R1–R6; then §4.6 if every inlet is dormant; else R7.
3. **Admissibility is R-007 (R-512).** In R5 and §8, "R-007 admissibility" means `tp_state.single_phase_admissible`:
   intensive, `τ_T = 1e-6 K`, temperature-degenerate streams admitted. The bubble/dew sum tests in parentheses are
   struck.
   - R5 judges a flowing inlet at its own `(n, T, P)` in its declared phase.
   - §8 judges a `LIQUID` stage's outlet `l_j` (a `VAPOR` stage's `v_j`) at `(T_j, P_j)`, not `m_j`. That outlet is
     the stream whose enthalpy the energy row writes single-phase, and it is what the region's K03 §8.2 screen judged.
   - Outside `τ_T` of saturation, R-007 and the sum test agree: SYN-001's `K` does not depend on composition and rises
     with T, so `Σ z K ≤ 1 ⟺ T ≤ T_bub`.
   - At the boundary the sum test refuses the canonical saturated feed. A top inlet at the upper adjacent double of its
     bubble temperature (`Σ zK − 1 = 2.2e-16`) is refused by R5, while R-007 admits it (equivalent error 1.8e-14 K).
4. **Inlet phases (R-513).** §1 reads: `top` enters stage 1 and `bottom` enters stage N, each in its declared phase.
   The registered cases use a liquid `top` and a vapour `bottom`. Rows, initializer (§6.2, §6.4) and generator are
   phase-generic, so there is no refusal. §4.3's label stays `T_top` whatever the phase of `top`.
5. **State tolerance, flows (R-514).** §10's flow term becomes `|Δ| ≤ 1e-6·|ref| + 3.1e-7 mol/s`, where
   `3.1e-7 = 10·τ_flow`. The T (1e-4 K) and Q (1e-2 W) terms are unchanged.
   - *Derivation.* ADR 0018 D2 bounds the distance a `newton_refined` root may keep from the exact root. The terminal
     chord correction `c = −Ĵ⁻¹F̂` estimates `x* − x`, and the core refines unless every `|c_j| ≤ τ_kind(j)`. The
     registered promise is therefore `|x_j − x*_j| ≲ τ_kind(j)`: 3.1e-8 mol/s and 1e-6 K, up to the chord's own error
     (≤ 1 %, or a factor 3.1 at near-singular states).
   - The old floor of 1e-9 mol/s sits 31× below that promise. No conforming run can be held to it, and a pass under it
     depends on Newton happening to overshoot the promise.
   - §10's "about 1e-9 of a 50-digit root" is struck. The margin of ten is the one ADR 0007 D2.4 and ADR 0018 D2 use,
     so the 10× rule now holds by construction: the error stays ≤ τ_kind, or refinement fires.
   - Measured: C4's pre-solve error of 3.80e-9 mol/s becomes 0.012 of the tolerance (before: 0.454).
   - Detection power is unchanged. Every registered defect class shows in T (≥ 1e-3 K against 1e-4 K), and the
     relative term still governs flows ≥ 0.31 mol/s.
6. **A05 (R-515).** The tolerance becomes T abs `1e-5 K` (10·τ_T) and flows abs `3.1e-7 mol/s` (10·τ_flow), replacing
   1e-7 K and rel 1e-8.
   - *Derivation.* The rationale "both are root-finders on the same rows" bounds their difference by the sum of the two
     promises. The cascade's is `τ_kind` (item 5). `ph_state`'s is measured at 1e-13 K against `ref`.
   - 1e-7 K asserted 10× more than the cascade's core promises. Measured: 9.77e-7 K, ρ = 0.98 of `τ_T`, so the margin
     is 10.2×.
   - A dropped Poynting term (8e-3 K) is still caught 800× over.
7. **A10's step (R-516).** The step becomes `h_j = 1e-6·max(D_x(j), |x_j|)`, with `D_x` as in A10. The tolerance 1e-6
   is unchanged. The measured floor must be ≤ 1e-8 at both points, which is the comparison's resolution: 100× under
   the tolerance.
   - *Derivation.* Central differences carry a rounding error of about `ε·|Ḣ|/h_j` in row units, or
     `ε·|Ḣ|·D_x(j)/(h_j·D_r)` scaled.
   - The old rule `h = 1e-6·max(1, |x|)` makes the scaled step `h_j/D_x(j)` 1e-10 for `Q_j = 0` (`D_x = 1e4 W`),
     against 1e-6 to 4e-6 for every other column. The `(Q_j, energy_j)` entries were therefore rounding-dominated
     10⁴× beyond the rest: 3.39e-8 measured, at an exact entry of +1.
   - With a uniform scaled step the floor is 5.9e-11 everywhere, the same order as the generator's 2.9e-11.
   - The old rule tested the difference quotient, not the Jacobian.
8. **A18's openings (R-517).** "`T̄ ± 10 K`" means the pre-solve's isothermal level: `x⁰` becomes the isothermal root at
   `T̄ ± 10 K`. The flow openings (`×0.5`, `×2`) perturb `x_K` as before.
   - The pre-solve has one root for a given `T̄`. Perturbing only `x_K`'s columns therefore leaves `x⁰`, and with it the
     whole target path, unchanged. Measured: `x⁰` within 3.7e-9 (scaled) of A06's, and the same 3 target iterations.
     A18 then tested only the pre-solve's basin.
   - Measured under this reading: both shifts converge, 2P ×3, in 4 target iterations, at 4.5e-10 (scaled) from A06's
     root. A18 keeps the four existing openings and adds these two.
9. **"Holds" for a swapped energy row (R-518).** In §4.5 and §4.6, a dormant stage's swapped `energy_j` holds when
   `|Q_j*| ≤ τ_heat_rate` (`KIND_TOLERANCE`, T05b §7.8 (iv) 2), the rule `solve_region` applies to the same row. The
   parenthetical "(`Q_j* ≠ 0`)" and §4.6's "every `Q_j* = 0`" are replaced. D1 and D2 (0 W and 50 W) are unchanged.
10. **§7.3 as built (no register entry; it confirms WO-2's logged build decision).** The pre-solve's stages are TP-type.
    Its opening is `x_K` as projected by the TP closure (`projected(...)`), and the region's screen picks the opening
    signature. A converged pre-solve that is not all `TWO_PHASE` ends
    `initialization_failed(s01-isothermal-presolve-v1, not_two_phase)`. DECISION 2 is untouched: `x⁰` is still an
    exact root of `H(·, 0)`.

## 18. Amendment 2 (2026-10-26, design lane `architect`, S08b): pointer

*Amendment 2 (2026-10-26, design lane `architect`, S08b): pointer.* Normative text `docs/derivations/S08b-design.md` §5.2;
register R-791. §8 gains a fifth clause: every `TWO_PHASE` stage lies within `1e-4 K` of its liquid's bubble temperature and
its vapour's dew temperature (S02 §8 item 6's rule and function, `cascade_solve.saturation_pairs`); an answer that fails it is
a defect, as §8. For a column, S02 §8 item 6 is this clause and is reported once, under S02's prefix. *Limitation:* on a
two-phase stage with `L_j V_j` below about 0.1 (mol/s)² the clause is tighter than the row tolerances imply (R-735); every
registered S01 root passes with a 41× margin (smallest `L_j V_j` 0.0135 (mol/s)², largest error 2.43e-6 K), and a correct but
loosely converged root there would raise.
