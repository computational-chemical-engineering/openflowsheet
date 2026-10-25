# S08 — One-phase column sections: block openings for the SYN-001 column (design note)

**Status:** Proposed, 2026-10-25, design lane (`architect`). Branch `wp/S08`. **ADR 0048** (Proposed) records the decision
against ADR 0005 D4. Register R-728 to R-731. Brief `docs/briefs/S08-one-phase-sections.md`.
**Evidence:** `docs/derivations/scripts/s08_design/` holds the probes and a float prototype, with their output in `measured.txt`.
They were measured on `60dbeae8`, whose code is main `390e0af5`. They are not production code, generators or tests.
**Normative here:** §5 (design), §7 (assertions), §8 (work orders) and §9 (gates).
**What this amends:** S02 §7 gains step 7, S02 §8 gains item 6, and S02 A12 is narrowed to its `CONVERGED` branch for P1. R-632's
limitation is narrowed. ADR 0005 is **not** amended.

---

## 1. Problem and scope

**Problem.** Some SYN-001 columns have a regular root whose signature contains a dry section (`VAPOR` stages) or a flooded
section (`LIQUID` stages). Today such a column ends in a typed failure. S02's P1 ends `HOMOTOPY_STALLED`.

**In scope.**
- `solve_column`: S02, S06 and S03 columns, including `none`/`none` columns.
- Block roots `V^a 2P^b L^c` that the source analysis of §5.2 generates.
- A two-phase saturation acceptance item (§5.5).
- Four new registered cases: P2, P3, F1 and D1 (§6).

**Out of scope.**
- The phase contract (`orchestrator/phase_contract.py`, `orchestrator/region.py`); it is unchanged.
- S01's `solve_cascade`, including its `not_two_phase` gate (§3 F6).
- Other property methods (S10-C), the third reference tool (S09), end-specification kinds not already registered, and
  transient behaviour.
- Partial dormancy: no candidate contains a `ZERO_FLOW` stage.
- The transition regime of a column, where no regular root exists.
- Root selection among several accepted roots.
- Findings F4 and F5 at contract level (§3, §10 Q3 and Q4).

## 2. Constraints and invariants

1. **The block rule** (S02 §4.3, R-533). A regular cascade signature reads `V^a 2P^b L^c` from top to bottom, ignoring
   `ZERO_FLOW`.
2. **End stages** (S02 §4.2, S06 §8 item 2). A partial end stage under any non-duty specification is `TWO_PHASE` at a regular
   root. Non-duty kinds are ratio, rate, purity, recovery and temperature.
3. **Bit-identity.** Every registered S01, S02, S06 and S03 case keeps its states, outcomes, attempt records and certificates.
   P1 alone changes, as intended (§6.1).
4. **No shared code moves.** S08 changes nothing under `src/openflowsheet/{orchestrator,numerics,thermo,compile}/`, nothing
   under `schemas/`, and none of `models/syn001/{cascade,cascade_solve,column}.py` (gate G2). Every non-column attempt record
   is therefore identical by construction.
5. **Frozen interfaces.** S08 adds no schema field, no `SolveOutcome` value and no `SolvePolicy` field. The contract literal
   stays `T05b-phase-contract-v2`.
   - New strings live only in a free-string schema field (`initializer_source`, `solution-certificate.schema.json:236`) and in
     model-level records (`ColumnSolution`, which is in neither plan §2.1 nor §2.2).
6. **Exactness.** The endpoint builder evaluates the provider at exact inputs and never quantizes. Pinned flows are exactly
   `+0.0`, sign bit included.
7. **No placeholder success.** A returned root passes all of S02 §8, including item 6. Everything else ends typed, or raises
   as §8 already does.
8. **Determinism.** Candidate generation and its order are pure functions of the `ColumnSpec`.

## 3. Findings that decide the design (measured, `measured.txt`)

**F1. The obstacle is the restart opening, not the block rule.**
- *P1 with the block rule inserted into the contract* (`contract_closure_probe.py`, `S08_MODE=close`).
  - Each proposal is mapped to the nearest `V^a 2P^b L^c` that keeps the changed unit.
  - Attempt 1 becomes `(2P, L, L, L, L)` and ends `LINE_SEARCH_FAILED` after **0** iterations.
  - The stall's candidate maps back to 2P×5, which gives `ACTIVE_SET_CYCLING`, then edge 3 `HOMOTOPY_STALLED`. The outcome is
    unchanged.
- *The same, with the changed units' openings rebuilt by an energy-consistent single-phase sweep at target duties*
  (`S08_SWEEP=1`).
  - The L-block opens at 355.9 K, and stage 5 at 388.9 K, which is above its bubble point.
  - Stage 1 still sits at attempt 0's end state, one Newton iteration from `x⁰`, in the wrong phase region.
  - The outcome is again unchanged.
- *P3 today* (§6.2).
  - Attempt 0 ends `BOUND_BLOCKED`, and the restart signature `(2P, 2P, 2P, 2P, L)` already conforms to the block rule.
  - That restart still ends `LINE_SEARCH_FAILED` after 0 iterations, then `ACTIVE_SET_CYCLING`, then edge 3
    `HOMOTOPY_STALLED`.
  - A block rule would not have changed this restart.
- *P2 today.* It is the mirror of P1: a `(2P, 2P, V, 2P, 2P)` restart with the same ending.

**F2. A block-conforming opening built from the column's own structure converges at once** (`block_endpoint_prototype.py`).

| Case | Signature | Newton iterations | Root |
| --- | --- | --- | --- |
| P1 | L×5 | 0 | the closed form, `T = (300, 299.999, 299.998, 299.997, 329.996)` K |
| P2 | V×5 | 0 | `T = (390, 420, 420, 420, 420)` K |
| P3 | `(2P, 2P, 2P, L, L)` | 4 | accepted |
| F1 | `(2P, 2P, 2P, L, L)` | 4 | accepted |
| D1 | `(V, V, 2P, 2P, 2P)` | 5 | accepted |

Every root passes S02 §8.

**F3. Every registered configuration has an all-two-phase candidate** (`registered_scan.py`).
- The topological candidate of §5.2, with all sources active, is all-2P on 47 of 47 registered column configurations.
- They are: S02 M1–M4 and P1; V-M1 ×5 and V-M2 ×3; S06 J1–J8, V ×4 and U ×2; S03 RC1–RC7, 10 perturbations and PC-P/L/LI.
- The only registered flowing configurations that do not converge today are P1, U1 and U2.

**F4. A near-trivial two-phase false success exists today.**
- F1 on today's path returns `CONVERGED (2P, 2P, 2P, 2P, L)`.
  - Stage 4 has `V_4 = 5.6e-6` mol/s, and its equilibrium rows are ≤ 1.2e-8, within kind tolerance.
  - But `T_4 = 370.0103` K, while the bubble temperature of `l_4` at `P_4` is 370.3890 K (`Σ K x = 0.9902`).
  - Stage 4 is a subcooled liquid labelled two-phase.
- From another opening the same stage converges at `V_4 = 1.24e-5`. The tolerance admits a continuum.
- Why it passes:
  - S02 §8 checks only `V, L > 0` and row residuals on a two-phase stage.
  - `region._admissible` returns `True` for any `TWO_PHASE` branch.
  - The division-free row `r_i = v_i L − K_i l_i V` gives `|1 − Σ K_i x_i| ≤ Σ|r_i| / (L V)`. A stage with `V → 0` therefore
    satisfies every row while far from saturation.
- On the 42 registered `CONVERGED` roots, the largest saturation error on a two-phase stage is **2.42e-6 K** (J8, RC6). Here the
  error is the largest of `|T_j − T_bub(l_j)|` and `|T_j − T_dew(v_j)|`.
- The smallest `L` or `V` on any two-phase stage of those roots is 0.183 mol/s.

**F5. Dotted column ids are read as dormancy items (a finding, not acted on).**
- Column stage unit ids contain `.` (`S02.stage.2`).
- `phase_contract._is_item` reads `.` as the mark of a dormancy-item key. Its premise is R1: unit ids never contain `.`.
- `adjacent()` is therefore `False` for any two column signatures, so D4's adjacent-candidate preference never applies to a
  column.
- `_changes()` returns `""`, which gives cause strings such as P1's `phase_wall(stall, )` with an empty change list, against
  T03 §4.10's grammar.

**F6. P1 does not meet the `not_two_phase` gate.**
- That gate is on S01's `solve_cascade` path only (`cascade_solve.py:675-691`).
- `solve_column` constructs its endpoint (S02 §18.2) and has no Newton pre-solve.

## 4. Decision

**Route: block re-entry.** After today's path ends typed, the column's initializer builds block-conforming openings from the
column's sources and solves from each in turn. This is S02 §7 step 7.

There is no block rule in the contract, no screen of the contract's proposals, and no change to ADR 0005 D4.

The opening of attempt 0 is already the initializer's to choose:
- ADR 0005 D3: "the opening state of an attempt is not screened".
- Its `opening_source` is `initializer`.
- S02 §18.2 already chooses all-2P.

The contract still decides every restart inside every solve.

**Why this route.**
- It removes the actual obstacle, a restart opening in the wrong phase region (F1).
- It converges every use case (F2).
- It moves no registered result, by construction:
  - Stage A is today's path, byte for byte.
  - Stage B runs only after Stage A fails.
  - The only registered Stage-A failures are P1, U1 and U2, and U1 and U2 generate no candidate (§5.2).

**Rejected.**

- **(a) A block rule in D4** (a closure step in `decide`, with model-declared stage chains).
  - Measured insufficient on P1 and P3 (F1): its openings inherit the failed attempt's state.
  - It would also move the shared function.
  - It would change records wherever a column's walk passes a non-conforming proposal that has a regular closure.
- **(b) A model-side screen around `solve_region`.** It has the same opening problem, and it is the second decision function
  R-632 rejected.
- **(c) A homotopy route.**
  - Edge 3 is frozen-signature (ADR 0010 D3, T04), and it stalls on P1, P2 and P3.
  - For P1's topology the only regular signatures are 2P×5 and L×5. An L-block must contain the reboiler, the only vapour
    source, and then no stage makes vapour.
  - So a path in `Q_r` must pass states where whole sections sit on the phase boundary.
  - A signature-switching continuation is a T04-scale design.
- **(d) Topology first** (opening dead sections single-phase before trying all-2P).
  - It reaches F1 and D1 directly.
  - But it would put on a new path every *unregistered* case that converges today.
  - The failure-driven form costs only one wasted all-2P solve on dead-section columns. It can be reversed later as a
    performance step.
- **(e) A thermal predictor** (CMO with q-lines) in Stage A. A misprediction on a near-boundary case breaks bit-identity.
- **(f) A new ADR 0010 recovery edge.** It would move column source structure into the generic recovery ladder, which is
  R-533's objection relocated.
- **(g) Enumerating every `V^a 2P^b L^c`.** That is O(N²) solves and root selection by search. Sources give at most
  `(n_L + 1)(n_V + 1)` candidates.

## 5. Design

### 5.1 The path (S02 §7, as amended)

**Stage A.** S02 §7 steps 1–6, unchanged, followed by S02 §8's acceptance, which now includes item 6 (§5.5). Its answer is
**A**.

`solve_target` keeps its public behaviour. It gains one keyword, `initializer_source`, whose default is `PRESOLVE_ID`.

Split `solve_target` into two:
- **`target_attempt`.** The same body, but returning `(result, recovered_from, regimes, failures, unsupported)` instead of
  raising.
- **`solve_target`.** `target_attempt` plus today's raises: `AcceptanceDefectError` and `UnsupportedAnswerError`.

**Trigger for step 7 (Stage B).** Stage B runs iff either:
- (i) A is a `ColumnSolution` whose outcome is in `T_B`:

  `T_B = {HOMOTOPY_STALLED, ACTIVE_SET_CYCLING, ATTEMPTS_EXHAUSTED, LINE_SEARCH_FAILED, LINEAR_SOLVE_FAILED, BOUND_BLOCKED,
  STAGNATION, PTC_STALLED, EVALUATION_ERROR}`, plus `BUDGET_EXHAUSTED` when `budget ∈ {newton_iterations, ptc_steps}`.
- (ii) A's `CONVERGED` state fails §8 **only** on item 6.

Nothing else triggers it. In particular, none of these do:
- validation refusals;
- the endpoint's `INITIALIZATION_FAILED` (A22);
- dormant answers;
- `CAPABILITY_UNAVAILABLE` (S06's unsupported answer);
- `CHECKPOINT_INCOMPATIBLE`;
- `BUDGET_EXHAUSTED` on `property_calls`;
- `SPECIFICATION_CONFLICT`;
- any §8 failure other than item 6, which still raises `AcceptanceDefectError` as today.

**Stage B.**
1. Generate the candidates (§5.2), in order.
2. For each candidate, build its endpoint (§5.3). A refusal is recorded, and the next candidate is tried.
3. Otherwise solve from the endpoint (§5.4). Return the first accepted answer. A failure is recorded, and the next candidate
   is tried.
4. If none is accepted, apply §5.7.

### 5.2 Sources, fixed stages and candidates (`models/syn001/column_blocks.py`)

`E` is the list of equilibrium stages, top to bottom: `2..N` with a total condenser, else `1..N`. `n = |E|`.

An inlet **flows** when `Σ n > 0`. A dormant inlet is never a source.

| Set | Members (stage, kind) |
| --- | --- |
| **Liquid sources** | partial condenser `(1, end)`; total condenser `(2, reflux)`; top inlet declared `LIQUID` that flows `(1, inlet)`; side feed `LIQUID` that flows `(stage, inlet)`; intermediate `Q_j* < 0` `(j, duty)` |
| **Vapour sources** | partial reboiler `(N, end)`; bottom inlet `VAPOR` that flows `(N, inlet)`; side feed `VAPOR` that flows; intermediate `Q_j* > 0` |
| **Fixed stages** (must be `TWO_PHASE`) | a partial end stage whose kind is not `duty`; stage 2 under a total condenser; every equilibrium stage named by a `temperature` specification (`EndSpecification.stage`) |

**Candidate.** A candidate is a pair `(a, c)` with `a, c ≥ 0` and `a + c ≤ n`, read as follows.
- Its signature is `σ(a, c) = V^a 2P^b L^c` over `E`, with `b = n − a − c`.
- When `b ≥ 1`, the core top is `t = E[a]` and the core bottom is `s = E[a + b − 1]` (0-based).

A candidate is **valid** iff all four hold:
- **(V1)** Every fixed stage is in the core.
- **(V2)** If `b ≥ 1`, `t` is the stage of a liquid source and `s` the stage of a vapour source.
- **(V3)** If `b = 0`:
  - when `a ≥ 1`, stage `E[a−1]` carries a flowing `VAPOR` inlet;
  - when `c ≥ 1`, stage `E[a]` carries a flowing `LIQUID` inlet.
- **(V4)** `(a, c) ≠ (0, 0)`. All-2P is Stage A's.

Under (V2) and (V3) every stage of a valid candidate has inflow, so no candidate contains `ZERO_FLOW`:
- V-block stages receive vapour from the core top, or from the vapour inlet at stage `E[a−1]`.
- L-block stages receive liquid from the core bottom, or from the liquid inlet at stage `E[a]`.

**Order.** Ascending `a + c`, then ascending `a`. `(a, c)` determines the signature, so this is a total order. At equal size an
L-block comes before a V-block.

**Expected candidate lists** (A01; the first five use §6's inputs):

| Spec | Candidate list |
| --- | --- |
| P1 | `[(0,5)]` (L×5) |
| P2 | `[(5,0)]` (V×5) |
| P3 | `[(0,2)]` |
| F1 | `[(0,2)]` |
| D1 | `[(2,0)]` |
| M3 | `[(0,5)]` |
| V-M1 `duty+duty` | `[(3,0)]` |
| M1, M2, M4, J5 | `[]` |
| U1, U2 | `[]` (fixed stages {2, 7}) |

### 5.3 The block endpoint `s08-block-endpoint-v1`

**Inputs.**
- `spec`.
- The candidate `(a, c)`.
- S02 §6's `ProfileInitial`, unchanged.
- S02 §18.2's hooks `profile_shift`, `ratio_scale` and `max_sweeps`, passed through.

**Stage sets.**
- Core `C = E[a .. a+b−1]`.
- L-block `Lb` = the stages after the core.
- V-block `Vb` = the stages before it.
- When `b = 0`: `Vb = E[0 .. a−1]` and `Lb = E[a ..]`.
- `F_ij` is the sum of component `i` over every flowing inlet at stage `j`, in either phase.
- `Q_j*` is the stage's specified duty: the intermediate value, or the end's `duty` specification. (V1) guarantees one exists
  on every block stage.

**Steps.**

1. **Ratios.**
   - `ρ_j` and `φ` come from `stage_ratios(spec, initial, ratio_scale=…)` (S02 §18.2 step 1). They are used on core stages.
   - On `Lb`, `S_ij := 0`.
2. **Start.** On core stages, `T_j = initial.profile[j−1] + profile_shift`.
3. **Sweeps.** Only when `b ≥ 1`. For `k = 1 … max_sweeps`:
   a. Compute `K_ij` at `(T_j, P_j*)` on core stages (`_k_values`).
   b. Per component, solve the tridiagonal over the liquid-carrying stages `t..N` (core followed by `Lb`) with `thomas`.
      - Row `j`: `[j > t] l_{i,j−1} − (1 + S_ij) l_ij + [j < N] S_{i,j+1} l_{i,j+1} = −F_ij`.
      - `S_ij = K_ij ρ_j` on the core and `0` on `Lb`.
      - With a total condenser, `t = 2` and the first diagonal is `−(1 + S_i2) + φ S_i2`.
      - Then `v_ij = S_ij l_ij`, which is exactly `+0.0` on `Lb`.
   c. On core stages, set `T_j` to the bubble temperature of `l_j` at `P_j*` (`band_temperature`, β = 0). A position other than
      `inside` refuses the candidate: `bubble_point_outside_domain`.
   d. Stop when the largest core `|ΔT|` is ≤ 1e-9 K. If the sweeps run out, refuse the candidate: `sweeps_exhausted`.
4. **Final flows.** Repeat step 3a–3b once at the stopped `T`.
5. **L-block,** top-down, for each `j ∈ Lb`.
   - Liquid:
     - When `b ≥ 1`, `l_j` is step 4's value (`= l_{j−1} + F_j` exactly).
     - When `b = 0`, `l_j = l_{j−1} + F_j`, with `l_{E[a]−1} := 0`.
   - `v_j := +0.0`.
   - `T_j` is the zero of `g(T) = H^L(l_j, T, P_j*) − [H^L(l_{j−1}, T_{j−1}, P_{j−1}*) + Σ_inlets H(inlet at its own T, P and
     declared phase) + Q_j*]`.
     - Every `H` is the provider's enthalpy flow (`tp_state.enthalpy_flow`).
     - Solve on the provider's `T` domain by safeguarded secant–bisection to `|ΔT| ≤ 1e-12` K. For SYN-001, which has
       constant `C_P`, one secant step is exact.
     - No sign change in the domain refuses the candidate: `block_energy_outside_domain`.
6. **V-block,** bottom-up, for each `j ∈ Vb`.
   - `v_j = v_{j+1} + F_j`, where `v_{j+1}` is the core top's vapour or the previous V stage's (for `b = 0`, start from `0`).
   - `l_j := +0.0`.
   - `T_j` is the zero of the vapour analogue of `g`.
7. **Total condenser.** `φ` comes from step 1. `T_c` is the bubble temperature of `v_2` at `P_1*` (S02 §18.2 step 5).
8. **Assemble `x⁰`.**
   - Call `_initial_state(spec, provider, DECLARATION_CONTEXT, liquid, vapor, profile=T, phi=…)`. It gives `m` from `mix`, the
     totals as sums, `D`, and every `Q_j` from its energy row.
   - The pinned columns are exactly `+0.0`. The region therefore opens each stage in `σ(a, c)` by its branch found (T05b §6.4),
     and no projection is recorded.
9. **Admissibility.** Every `Lb` stage's liquid must be admissible as `LIQUID`, and every `Vb` stage's vapour as `VAPOR`, under
   `single_phase_admissible`, the function S02 §8 uses through `_admissibility`. The first failure refuses the candidate:
   `inadmissible_endpoint(<stage>)`.

**Refusals.** A refusal is recorded as `initialization_failed(s08-block-endpoint-v1, <reason>)` on its candidate. It never ends
the solve by itself.

**Identity (A02).**
- `x⁰` satisfies every target row except the continued slot rows (S02 §7.5) within its kind tolerance.
- On a block stage the duty slot row holds within `ENERGY_TOLERANCE`.

### 5.4 Solving from a candidate

Call `target_attempt(spec, provider, target, x⁰, initial.profile, policy=<the same policy>,
initializer_source="s08-block-endpoint-v1")`. Everything else is unchanged:
- the same policy;
- the same contract;
- edge 3 on its usual triggers, from the candidate's item-0 opening, continuing the same slots with `p⁰` read at `x⁰`.

| Candidate result | Treatment |
| --- | --- |
| `CONVERGED` with an empty failure list and no unsupported stage | **accepted** |
| a typed region outcome | failure; recorded with its outcome and cause |
| `CONVERGED` failing only item 6 | failure: `near_trivial_split(<stage>)` |
| an S06 item 3 unsupported answer | failure: `unsupported(temperature_specification_on_single_phase_stage:<j>)` |
| any other §8 failure | raises `AcceptanceDefectError`; a defect is never swallowed |

### 5.5 S02 §8 item 6: two-phase saturation consistency

**Rule.** At an accepted state, every `TWO_PHASE` stage `j` has

`|T_j − T_bub(l_j, P_j)| ≤ τ₆` and `|T_j − T_dew(v_j, P_j)| ≤ τ₆`, with **`τ₆ = 1e-4 K`**,

where `T_bub = band_temperature(provider, l_j, P_j, 0)` and `T_dew = band_temperature(provider, v_j, P_j, 1)`.

**Failure.**
- A band position other than `inside` is a failure.
- The failure string is `§8.6: TWO_PHASE stage <j>: <bubble|dew> error <e> K`.

**Implementation.** A named constant `TWO_PHASE_SATURATION_TOLERANCE = 1e-4`, and a helper
`saturation_errors(spec, provider, state, regimes) -> dict[int, float]` that `acceptance_failures` calls.

**Why 1e-4 K.**
- It is S02's state tolerance in `T`.
- It is 41× the largest registered error (2.42e-6 K, F4) and 3 790× under F1's false root (0.379 K).
- `TEMPERATURE_TOLERANCE = 1e-6` K is too tight: J8 and RC6 measure 2.42e-6 K.

**Rationale.** At a genuine two-phase root `y = K x`, so `T = T_bub(x) = T_dew(y)`. The row bound of F4 shows why rows alone
cannot catch a near-trivial split.

### 5.6 Records

**New field.** `ColumnSolution` gains `reentry: BlockReentry | None = None`.
- It is `None` whenever Stage B is not triggered, which covers every registered `CONVERGED` case.
- It is not part of any `state_sha256`.

**New types.**

| Type | Fields |
| --- | --- |
| `BlockReentry` | `trigger: str` (A's outcome, or `near_trivial_split`); `stage_a: StageARecord`; `candidates: tuple[CandidateRecord, ...]`; `accepted: int \| None` |
| `StageARecord` | `outcome`, `cause`, `result`, `recovered_from`, `endpoint_sha256`, `final_sha256`, `failures` (item-6 strings, or `()`) |
| `CandidateRecord` | `a`, `c`, `signature` (regimes over `E`), `endpoint` (`"built"`, or the refusal cause), `endpoint_sha256 \| None`, `outcome \| None`, `cause`, `result \| None`, `recovered_from \| None` |
| `BlockEndpoint` | `state`, `signature`, `rho` (core), `phi`, `sweeps`, `last_delta` |

**Top-level fields always describe the returned solve.**
- When a candidate is accepted, these come from that candidate: `outcome = CONVERGED`, `signature`, `state`, `endpoint`,
  `continued`, `endpoint_sha256`, `result`, `recovered_from`, `final_sha256`, `inverse` and `unreached`.
  - `endpoint` is typed `BubblePointEndpoint | BlockEndpoint`.
  - `initial`, `profile` and `warnings` are unchanged.
- When no candidate is accepted, the top level is A exactly, and `reentry` is attached.
- When Stage B is triggered with no valid candidate (U1, U2): `reentry = BlockReentry(trigger, stage_a, (), None)`, and the top
  level is A.

### 5.7 Final answer

1. A candidate is accepted: return it.
2. None is accepted and A is typed: return A, with `reentry`.
3. None is accepted and A failed item 6: raise `AcceptanceDefectError` with A's failures, as S02 §8 does for any failed item.
   The message names the candidates tried.

## 6. Registered cases

### 6.1 P1 (S02 §9): new expectations

**Top level.**
- `CONVERGED`, signature `LIQUID ×5`.
- `state` equals `ref.phase_case.P1` (the closed form) within S02's state tolerance.
- The distillate `v_1` is `+0.0`, sign bit checked.
- `result.attempts` is one attempt, `LLLLL`, `CONVERGED`, iterations ≤ 1 (measured 0). `recovered_from` is `None`.
- `initializer_source` is `s08-block-endpoint-v1`.

**`reentry`.**
- `trigger = HOMOTOPY_STALLED`.
- `stage_a` is today's held branch, exactly:
  - outcome `HOMOTOPY_STALLED`, cause `homotopy_stalled(BOUND_BLOCKED)`;
  - attempts: target `BOUND_BLOCKED` 2P×5; target `LINE_SEARCH_FAILED` `(2P, L, 2P, 2P, 2P)`; edge 3 `HOMOTOPY_STALLED` 2P×5;
  - `stage_a.recovered_from.outcome` is `ACTIVE_SET_CYCLING`.
- `candidates == [(0, 5) built, CONVERGED]`.
- `accepted == 0`.

**Tests.**
- **S02 A12** keeps its first branch only for P1. The typed branch is withdrawn for P1.
- `test_a12_p1_measured_branch_is_held` becomes a test of `reentry.stage_a`, with the same expected values.

### 6.2 New cases (WO-G registers them)

The inputs below are normative. WO-G may change one only if a generator claim fails, and then records the reason.

Common to all four:
- `FEED = (0.3, 0.4, 0.3)` mol/s.
- `P_j* = 1.00 + 0.01(j − 1)` bar.
- N = 5.
- Intermediate duties 0.

| Case | Inputs | Role | Expected | Float sanity values (prototype) |
| --- | --- | --- | --- | --- |
| **P2** | M4, with the condenser under `duty` −3000 W and the bottom inlet `VAPOR` FEED at 420 K, 1.04 bar | P1's mirror, all vapour, through Stage B | V×5. Closed form: `v_j = bottom`, `T_j = 420` K for j ≥ 2, `T_1 = 420 + Q_c*/(F C_P) = 390` K; bottoms `+0.0`. Candidates `[(5,0)]` | Dew margin at stage 1 is 16.9 K (`T_dew = 373.128` K at 1 bar) |
| **P3** | Partial condenser, `distillate_rate` 0.5; partial reboiler, `duty` 1000 W; side feed `feed` at stage 3, `VAPOR` FEED, 385 K, 1.02 bar; side feed `cold` at stage 4, `LIQUID` (0.15, 0.2, 0.15), 300 K, 1.03 bar | Partly one-phase. The weak reboiler is quenched by the cold feed; Stage B with a core | `(2P, 2P, 2P, L, L)`. Stage A typed. Candidates `[(0,2)]` | `T = (350.9491, 362.4433, 370.0147, 335.0069, 345.0059)` K; `V = (0.5, 1.08077, 1.04935, 0, 0)` |
| **F1** | M4, with no bottom vapour; bottom inlet `LIQUID` (0.03, 0.04, 0.03) at 330 K, 1.04 bar; side `feed` at stage 3, `VAPOR` FEED, 385 K, 1.02 bar | Flooded bottom: a dead section below a vapour feed | `(2P, 2P, 2P, L, L)` through Stage B, after Stage A is rejected by item 6 at stage 4. Candidates `[(0,2)]` | `T = (350.9491, 362.4433, 370.0147, 370.0137, 363.3439)` K. Stage 4 is subcooled by 0.375 K by pressure alone |
| **D1** | M3, with the top inlet `VAPOR` (0.03, 0.04, 0.03) at 400 K, 1.00 bar; side `feed` at stage 3, `LIQUID` FEED, 340 K, 1.02 bar; reboiler `duty` 30 kW | Dry top: a dead section above a liquid feed | `(V, V, 2P, 2P, 2P)` through **Stage A**: the contract reaches it, disappearing end-first. Candidates `[(2,0)]` | `T = (372.9262, 369.9392, 369.9392, 386.5229, 395.475)` K |

**WO-G's generator claims, per case** (50 digits, `docs/derivations/scripts/s08_reference.py`, which imports nothing from
`src/`):
- the root;
- its signature conforms to the block rule;
- regularity: the scaled `σ_min ≥ 1e-4`, with S02's scaling;
- every block stage admissible, with its margin recorded;
- every core stage has `L, V > 1e-3`;
- overall closure;
- the candidate list, generated by an independent transcription of §5.2;
- **for F1**, the bubble temperature of `l_4` at `P_4` exceeds the root's `T_4` by ≥ 0.3 K. Item 6 rests on this claim.

**Core decoupling.** P3 and F1 share their core (stages 1–3) to within 3e-10 mol/s in prototype, because an L-block sends no
vapour up. WO-G claims this equality.

## 7. Assertions

Tolerances are S02 §10's state tolerance unless stated otherwise.

| Id | Assertion | Expected | Tolerance |
| --- | --- | --- | --- |
| S08.A01 | Candidate lists for the specs of §5.2's table | as tabled | exact |
| S08.A02 | At every built endpoint of P1, P2, P3, F1 and D1: every target row except the continued slots within kind tolerance; block duty slots within `ENERGY_TOLERANCE`; pins `+0.0` with the sign bit checked; the branch found equals `σ(a, c)` | pass | as stated |
| S08.A03 | The builder at all-2P equals S02 §18.2's `x⁰` on M1–M4. This tests the builder only; Stage A never calls it | equal | 1e-12 relative |
| S08.A04 | Refusals, with no `solve_region` call (stubbed to raise): `band_temperature` stubbed to answer `below` at a core stage gives `bubble_point_outside_domain`; `max_sweeps = 1` on P3's `(0,2)` gives `sweeps_exhausted`; P1's `(0,5)` at `Q_r* = 8 kW` gives `inadmissible_endpoint(5)` (`T_5 ≈ 380` K, bubble ≈ 350 K) | codes | exact |
| S08.A05 | P1 as §6.1, top level | §6.1 | as stated |
| S08.A06 | P1's `reentry.stage_a` equals today's held branch | §6.1 | exact |
| S08.A07 | P2 | the closed form of §6.2, through Stage B | — |
| S08.A08 | P3 | WO-G's root, through Stage B | — |
| S08.A09 | F1: Stage A is rejected by item 6 at stage 4 with error ≥ 0.1 K, then Stage B gives WO-G's root | as stated | — |
| S08.A10 | D1 gives WO-G's root through Stage A with `reentry is None`. With Stage A forced to fail (stub `HOMOTOPY_STALLED`), Stage B's `(2,0)` gives the same root | as stated | — |
| S08.A11 | Core decoupling: stages 1–3 of P3 equal those of F1 (`T`, `l`, `v`, `Q_1`) | equal | state tolerance |
| S08.A12 | Item 6 passes on all 42 registered `CONVERGED` roots; the largest error, ≤ 1e-5 K, is recorded. `saturation_errors` flags F1's Stage-A state at stage 4 (≥ 0.3 K) | as stated | as stated |
| S08.A13 | Bit-identity, gate G1 | equal | exact |
| S08.A14 | Each mutation in the next table makes its named assertion fail | as tabled | — |
| S08.A15 | P1 and P3 solved twice give identical final `state_sha256` and identical `reentry` records | equal | exact |
| S08.A16 | Exclusions: S02 A22 is unchanged with no Stage B; S06's unsupported answer (`test_s06_column_wo2.py:732`) is unchanged with no Stage B; U1 and U2 have `reentry.candidates == ()` and an unchanged top level | as stated | exact |

**Mutations for A14.**

| Mutation | Assertion that must fail |
| --- | --- |
| (a) Stage B disabled | A05 |
| (b) The L-block given `S_ij = K ρ`, so no exact zeros | A08 |
| (c) L-block `T_j` set to the core bottom's bubble `T` instead of the energy solve | A05 or A08 |
| (d) `τ₆ = ∞` | A09 |
| (e) The item-6 trigger removed | A09, which then raises |

## 8. Work orders

Each work order runs in about 150k context, in worktree isolation on `wp/S08`.

**WO-G** (design lane, `specifier`). Independent of the other work orders.
- `s08_reference.py` and `.json`, with §6.2's cases and claims, and `--check`.
- P1 stays in `s02_reference.json`.
- Register the cases in the register.

**WO-1** (build lane, `opus-engineer`, about 60k). S02 §8 item 6.
- `saturation_errors`, the constant, and the failure strings.
- Tests: A12, plus a constructed near-trivial state.
- Accept on: the S02, S06 and S03 suites green; the largest registered error logged in `docs/S08_DECISIONS.md`.

**WO-2** (build lane, about 120k). Sources, candidates and the block endpoint.
- `models/syn001/column_blocks.py`: §5.2 and §5.3, the `BlockEndpoint` dataclass, and the refusals.
- Do not modify any Stage-A function. Reuse `stage_ratios`, `_k_values`, `thomas`, `band_temperature`, `_initial_state`,
  `single_phase_admissible` and `tp_state.enthalpy_flow`.
- Tests: A01–A04. The P2/P3/F1/D1 specs are inline; WO-G's values come later.

**WO-3** (build lane, about 120k). Stage B in `solve_column`.
- `target_attempt`, and the `initializer_source` keyword.
- The trigger, the loop, and the records of §5.6–§5.7.
- Tests: A05, A06, A15, A16, and A14 (a), (d) and (e).
- Accept on: the S01, S02, S06 and S03 suites green, and G1 run.

**WO-4** (build lane, about 100k). After WO-G.
- Tests: A07–A11, A13, and A14 (b) and (c).
- `scripts/s08_identity.py` (G1).
- The S08 evidence manifest.
- Replace S03 §10.1's and §14's limitation sentence with: *"the column converges to a block root `V^a 2P^b L^c` that §5.2 of
  S08-design generates (S08); other one-phase-section roots may still end typed"*.
- Record the wall times of P1 and P3 in `docs/S08_DECISIONS.md`.

**Review.** One `reviewer` pass on WO-1 to WO-4 against this note, before the merge. The work touches phase logic and
acceptance.

## 9. Verification gates

- **G1. Bit-identity.**
  - `scripts/s08_identity.py` computes, for every registered configuration, a SHA-256 over the pre-existing fields: outcome,
    cause, signature, `endpoint_sha256` and `final_sha256`; per attempt of `result` and `recovered_from`, the signature,
    outcome, `solver_outcome`, iterations, reason and `state_sha256(end_state)`; and `inverse` and `unreached`.
  - The configurations are the 47 of F3 plus S01 C1–C5.
  - Run it on the merge base, in a separate worktree, and on the branch.
  - It passes iff every digest is equal except P1's, and P1's `reentry.stage_a` digest equals P1's merge-base digest.
  - It prints one line: `S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL`.
- **G2. Structure.** `git diff --stat $(git merge-base main HEAD)..HEAD` is empty over:
  - `src/openflowsheet/orchestrator`, `numerics`, `thermo` and `compile`;
  - `src/openflowsheet/models/syn001/cascade.py`, `cascade_solve.py` and `column.py`;
  - `schemas`.
- **G3. Tests.** S08's A01–A16 pass, and the S01, S02, S06 and S03 suites pass.
- **G4. Before merge.** The full `scripts/gate.sh`, with CI green on x86-64 and aarch64.
- **G5. Recorded numbers** in `docs/S08_DECISIONS.md`: P1's Stage-B iterations (≤ 1), P3's iterations, the largest item-6
  error on registered roots (≤ 1e-5 K), and the wall times.

## 10. Risks and open questions

Each item has a default, so the work can proceed unattended.

1. **Q1 — scope (preference).** Is S08 limited to block roots generated by sources (§5.2)?
   **Default:** yes. Other one-phase roots may still end typed, honestly.
2. **Q2 — generator claims (fact).** Do WO-G's claims hold for P2, P3, F1 and D1, in particular `σ_min ≥ 1e-4` and positive
   margins?
   **Default:** yes. The float prototype reached accepted roots. If a claim fails, WO-G changes only that case's inputs, keeps
   its role, and records why.
3. **Q3 — F5 (preference: whether to queue a package).** Fixing the dotted-id misreading re-baselines column cause strings and
   may move restart points.
   **Default:** queue a small contract-owner package after S08. S08 does not touch it.
4. **Q4 — F4 at contract level (preference).** Should the two-phase admissibility of K03 §8.2 cover every lifted split, which
   includes flash units and S01 cascades?
   **Default:** queue it for Frank's decision. S08 adds only the column acceptance item.
5. **Q5 — item 6 across architectures (fact).** The margin is 41×.
   **Default:** it holds. CI (G4) confirms.
6. **Q6 — item-6 rejection with no candidate accepted (preference).**
   **Default:** raise, as S02 §8 does. The alternative is a typed `CascadeFailure`.
7. **Q7 — provenance of a Stage-B root (preference).**
   **Default:** the certificate's `initializer_source` is `s08-block-endpoint-v1`, and the history lives in
   `ColumnSolution.reentry`. The certificate does not encode Stage A's failure.
8. **Q8 — cost (fact).** Stage B adds at most |candidates| region solves, each of which may run edge 3.
   **Default:** no budget. G5 records the times.
9. **Q9 — endpoint failures (preference).** Should Stage A's endpoint `INITIALIZATION_FAILED` trigger Stage B?
   **Default:** no. A22 stays identical. Reconsider only when a case needs it.

## 11. What this does not establish

- Convergence for block roots that §5.2 does not generate.
- Any claim about a column's transition regime, where no regular root exists.
- Root selection or uniqueness. When Stage A converges, its root is returned even if a block root also exists.
- Any claim beyond SYN-001's composition-independent `K`.
- Anything about S01's `solve_cascade`.
- The near-trivial split outside S02 columns (F4). It may exist wherever a division-free equilibrium row meets a
  `TWO_PHASE`-always-admissible branch.

## 12. Decisions

- DECISION: S08's route → a failure-driven block re-entry in the column's initializer (§5). Alternative: a block rule in ADR
  0005 D4 (measured insufficient, F1). Reversible by: deleting step 7, since Stage A is untouched.
- DECISION: two-phase saturation consistency → S02 §8 item 6, `τ₆ = 1e-4 K`. Alternative: no check, which keeps F4's false
  success. Reversible by: removing item 6.
- DECISION: the order of Stage A → today's all-2P path first, then block candidates. Alternative: topology first.
  Reversible by: swapping the order, a performance step that needs G1 re-run.
- DECISION: S01's `not_two_phase` gate → unchanged (F6). Alternative: relax it. Reversible by: a later S01 amendment.
