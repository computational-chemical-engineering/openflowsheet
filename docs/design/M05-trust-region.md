# M05 design — the trust-region integration spike and the fixed-topology refinement loop

**Status:** Proposed, 2026-10-09. Design lane (`architect`). Branch `wp/M05` from `main` `1ecf576`.
**Brief:** `docs/briefs/M05-design.md`. **ADRs:** 0038 (the trust-region adapter and its composition), 0039 (the C1
study: decision, objective, parent checks, refinement loop, accounting, records), 0040 (the conditional fallback).
**Register:** R-260 to R-279 (R-274 to R-279: §16 rulings).
**Plan row (v1.2 §4.4, L267):** "M05 — M03, M04: distinct trust-region integration spike and fixed-topology refinement
loop." Acceptance: ExternalFunction/glass-box composition with source maps; parent-model checks at candidate optima;
true-model call accounting; constraints and limitations retained. Gate W24 (M05's half). Requirements A06, D13.

This note stands alone. Every number in it is registered here or in the ADRs, and the implementer decides nothing
the note leaves open: anything not settled is in §15 with a default.

---

## 1. Problem and scope

M05 builds two things.

1. **A trust-region adapter.** It composes the documented Pyomo trust-region framework (`pyomo.contrib.trustregion`,
   "TRF") with OpenFlowsheet models. The glass box is compiled from the canonical model. The expensive model enters as
   a Pyomo `ExternalFunction`. M05 demonstrates the adapter on eligible smooth gray-box examples, with every theorem
   assumption stated.
2. **A fixed-topology refinement study on C1** (the ammonia loop `C1-LOOP-M02-v1`). It optimizes one continuous
   decision with the reactor in the loop, checks every candidate against the parent reactor, and accounts for every
   true-model call.

**In scope:**
- the Pyomo projection of a `ProblemSpec`, with its source map and equivalence tests;
- the `ExternalFunction` contract;
- the TRF runner and its state exposure;
- the truth adapters (parent reactor, M04 surrogate, test-only synthetic);
- the finite-difference policy for a derivative-free truth;
- the C1 study registration and the refinement loop;
- parent checks at candidates and their statuses;
- true-model call accounting and budgets;
- the record schema and replay;
- the conditional fallback (ADR 0040);
- the audit extension for the Ipopt executable.

**Out of scope:**
- topology synthesis;
- Bayesian or multi-fidelity experiment design;
- surrogate retraining (M04 owns its iterations, §7.6);
- M07's journey report and W25 (the end-to-end real-reactor refinement);
- any change to M02, M03 or M04 semantics. Three additive accessors may be needed (§12, WO-4 and WO-5); they are
  bitwise-inert and escalated if they are not;
- an application job operation for trust-region studies (§9.5);
- sensitivities of any kind. ADR 0031 C3 is untouched (§6.9).

## 2. Constraints and invariants

- **No identity moves.** SYN-001, K05, T06, M01's registered values and M02's experiment identity stay fixed. M05 is
  additive: new modules, one new schema, new records.
- **No second model.** The glass box is the canonical `ProblemSpec` evaluated with a different algebra (§6.1). No unit,
  flowsheet or property equation is re-authored (plan L271; R-003: Pyomo is not a compile backend).
- **No CasADi `nlpsol` and no METIS-closure object** (ADR 0006 D1.5). The Ipopt executable is a newly loaded binary set
  and needs an [A10] audit extension (WO-1).
- **Candidates are judged on the re-solved certified simulation** (R-188). Optimizer termination is not feasibility,
  and local stationarity is not optimality. Domain restrictions are constraints, never penalties (R-189).
- **The surrogate is frozen within a subproblem.** Refinement is a new study iteration (blueprint §9.3, L427).
- **Exact keys.** Truth evaluations are memoized and requested on the exact binary64 inputs, never quantized (CLAUDE.md
  scientific conduct; ADR 0033 D4).
- **Gates.** The default gate never runs Ipopt, Pyomo or the reactor. Those runs are opt-in tiers (`nlp`, `pymrm`)
  whose committed records the default gate checks.
- **Budgets are in cold experiments and wall time.** A reactor evaluation costs 25–45 s (R-250). Distinct keys run
  concurrently, with no more workers than physical cores. The build machine has 24 physical cores (measured).
- **Precision.** Everything is binary64. The TRF and Ipopt are deterministic on one machine and environment: in the
  probe, a repeat run was bitwise identical. Across architectures, records are compared under
  `T08-numerical-policy-v2` (R-253's pattern).

## 3. Decisions at a glance

| # | Decision | Rejected alternative (why) | Register |
| --- | --- | --- | --- |
| D1 | Use Pyomo 6.10.1 `contrib.trustregion`, pinned by version and module hashes. No fallback is active. | Our own TR loop (not a tested framework, D13); the cyipopt gray-box bridge (that is M03's bridge, A06; TRF does not consume an `ExternalGreyBoxModel`, blueprint L441) | R-260 |
| D2 | The glass box is an in-memory projection: the `ProblemSpec`'s own row builders are called with a `PyomoAlgebra`, and each property-block output becomes one Python-callback `ExternalFunction` behind an explicit output variable | A text code generator (a second artifact to keep in sync); Peng–Robinson as Pyomo algebra (a second model of the provider, with its root selection); grey-box blocks inside the TRF subproblem (TRF passes `keepfiles`, and its DOF count and step rejection cannot see inside them) | R-261 |
| D3 | The reactor enters full-space, as two EFs (X, ΔT: M02's coupling coordinates) of the 7 inlet variables, linked to the coupled route's (X̂, ΔT̂) promoted to variables. TRF solves the coupling and the optimization together | The M02 coupled solve as the black box in reduced space: each evaluation is a 2–6 min solve carrying coupling-tolerance noise, and a gradient costs n_d more of them. Full space evaluates the reactor only at the inlet: 1 + 7 experiments per accepted iteration | R-261 |
| D4 | The subproblem solver is the audited Ipopt 3.14.20 ASL executable, through a registered alias with options `M05-trsp-ipopt-v1`, the exact Hessian (ASL) and an executable pinned by sha256 | PyNumero cyipopt (probe: TRF passes `keepfiles`, which cyipopt refuses); a cyipopt shim as primary (a configuration the framework never tested; kept as a contingency) | R-263 |
| D5 | Callback contract: identity under `deepcopy`, exact-key memo, never a non-finite value, refusals raised as typed exceptions, budget enforced in the callback | Plain callbacks (probe: TRF's clone deep-copies them and accounting sees 0 of 23 calls); returning NaN (probe: TRF accepts NaN silently and reports optimal) | R-262 |
| D6 | TRF state is read from the `pyomo.contrib.trustregion` INFO log and the captured EXIT lines; the filter is reconstructed from θ-type steps | Patching TRF internals (breaks the pin) | R-260 |
| D7 | Basis b(w): property EFs get the affine Taylor model at w₀; the reactor EF gets the promoted M04 quadratic, or else the constant d(w₀) | TRF's default b = 0 (the first subproblem would see zero enthalpies and fugacities); an unpromoted surrogate (promotion is the project's permission to use) | R-264 |
| D8 | A derivative-free truth gets forward differences in the 7 inlet coordinates, η = 2⁻¹⁴, exact differences, inward at hard bounds, 7 concurrent workers and a gradient-quality check (amended by §17.2, R-297: `M05-fd-v2`, three steps, escalation for noise only) | Central differences (twice the cost, while the measured precision floor makes forward accurate); a finite-difference Hessian (not needed: TRF's model is first order) | R-265 |
| D9 | The eligible example is TR-E2: the C1 formulation with the reactor EF bound to the test-only C^∞ truth `m05-synthetic-interior-v1`, with an analytic gradient. TR-E1, Eason–Biegler example 1 as a `ProblemSpec`, is the framework-equivalence oracle | The real reactor (its gradient is FD and its smoothness is unproven, so it is qualified rather than eligible); Pyomo's example alone (no flowsheet composition) | R-266 |
| D10 | The C1 decision is the reactor inlet temperature T_in ∈ [643.15, 733.15] K, with φ fixed at 0.02. The objective maximizes the liquid NH₃ product. Hard domains are constraints; `extrapolated` is a stated limit | (T_in, φ) jointly (under this objective φ runs to its bound); an economic objective (needs prices: Needs Frank N-F1); `extrapolated` as a constraint (infeasible: every registered state is extrapolated, R-169) | R-267 |
| D11 | The refinement loop: stage A (TRF on the promoted surrogate) → B (parent checks) → C (TRF on the parent, basis = promoted surrogate or constant) → B, at most 3 study iterations, stopping on parent evidence. M05 does no retraining | Surrogate-based optimization with retraining between iterations (blueprint L437: retraining breaks the convergence theory; M04 owns its iterations) | R-268 |
| D12 | Parent checks P1–P5, as in §7.4: the targeted check, gross agreement, constraints, regimes, and a poll at the decision tolerance against a noise floor computed from the coupling residuals | M03's V5 (adjoint sensitivities, refused on this path by ADR 0031 C3); a finite-difference KKT test as the verdict (no decidable tolerance without J‴) | R-269 |
| D13 | A truth ledger per request, plus coupled-check summaries. Cold, store hit and memo hit are counted per stage, iteration and candidate. Budgets: study 400 cold / 4 h; TRF run 250 cold / 30 iterations | Counting from the experiment store alone (it cannot attribute a call to a purpose or an iteration) | R-270 |
| D14 | A new schema `trust-region-study-v1`. Replay classes follow M02. R-253's move into `run/compare` is deferred, because M05 adds no product-level study replay | Extending M03's `optimization-report` (disjoint content; A06 wants the bridges kept apart) | R-271 |
| D15 | ADR 0040, conditional: a scipy-only reduced-space trust-region model management over certified simulations, activated only by a recorded trigger | No fallback (plan L271 requires one ready); our own copy of TRF (the same assumptions without the "tested" claim) | R-272 |
| D16 | Exposure: the library `openflowsheet.studies.trust_region`, evidence scripts and `trust_region_readiness`. No job operation in M05 | A job operation now (ADR 0019 amendment; M07 decides whether its journey needs one) | R-273 |

## 4. The probe (a probe, not evidence)

The probe ran in the audited M03 environment (`…/scratchpad/m03-ipopt/nlp`, Pyomo 6.10.1, Ipopt 3.14.20 with MUMPS
5.8.2), with `PYTHONNOUSERSITE=1`, `OMP_NUM_THREADS=1` and a private `PYOMO_CONFIG_DIR`. The scripts are
`scratchpad/m05-probe/probe{1,2,3}.py`, outside the repository. They are throwaway: WO-3 re-establishes each finding
as a test.

| # | Question | Finding |
| --- | --- | --- |
| P1 | Native Eason example 1 | 5 iterations, 0 rejected, "EXIT: Optimal solution found."; z = (1.286931683273266, 1.4802348006326804, 1.3794547317539292), x = (1.3219485331078022, 0.628718497180208), objective 0.27704478876374156 |
| P2 | The same black box behind a `PropertyBlock`-style wrapper (values + Jacobian triples) with an exact-key memo | **Bitwise equal** to native; the iteration log is identical |
| P2′ | Does a stateful callback see TRF's calls? | **No.** `TRFInterface` runs `model.clone()`, which deep-copies the callback's owner, so the original ledger saw 0 calls. With `__deepcopy__` returning `self` it saw 23 calls: 19 values, 6 of them cold (distinct points), and 4 gradients. Sequence `FFfffgfFfffgFfffgFfffgF` |
| P3 | An EF without a gradient callback | Refused: `RuntimeError … not defined with a gradient callback`. TRF needs ∇d |
| P4 | An explicit output variable `y == EF(…)` | Works; the DOF check passes; differs from native by 4.4e-16 |
| P5 | A constant basis b = d(w₀) | Converges to the same point within 4.1e-7 (TRF tolerance level) |
| P6 | A callback that raises | The exception propagates out of `solve()` and aborts TRF. There is no evaluation-failure path |
| P7 | A callback that returns NaN once | **Silently accepted.** TRF continues and reports optimal |
| P8 | `solver='cyipopt'` for the subproblem | Refused: `key 'keepfiles' not defined`. TRF always passes `keepfiles` and `tee`. (`solver=` given to the `SolverFactory('trustregion', …)` constructor is broken as well; give it to `solve()`) |
| P9 | Repeat run | Bitwise-identical values and log |
| P10 | A registered alias of the `ipopt` shell plugin with options and an explicit executable path, passed as `solve(..., solver=alias)` | Works without `ipopt` on `PATH`; banner "Ipopt 3.14.20, MUMPS 5.8.2" |
| P11 | A vector black box (2 outputs) behind two EFs sharing one memo; forward FD from a thread pool inside the gradient callback | Works, with no deadlock. 14 cold evaluations, 8 of them FD points; the FD solution agrees with exact gradients within 1.5e-6 |
| P12 | Executable linkage (`ldd bin/ipopt`) | Loads `libipoptamplinterface.so.3`, `libipopt.so.3`, `libasl.so`, `libspral.so`, `libdmumps_seq.so`, `libmetis.so`, `libgomp.so.1`, `libhwloc`, `libgfortran`. Absent from M03's inventory: `bin/ipopt`, `libipoptamplinterface.so.3.14.20`, `libgomp.so.1` |

| P13 | (found in WO-3, 2026-10-09) An EF refusal during TRF's start-value evaluation | **Swallowed.** `EFReplacement.exitNode` (`interface.py:86`) wraps it in a bare `except:` and sets the holder variable to 0. It is the module's only bare `except` |
| P14 | (2026-10-09, `scratchpad/m05-probe2`) An EF output pinned by the decisions alone (`y − 90z = 0`); a C1-shaped toy | (a) **TRF's default basis b ≡ 0 makes the PMP infeasible at iteration 0.** It forces d = −2 ∉ [−1, 1], before any radius exists and with no restoration. With b(w₀) = d(w₀) (constant or Taylor) the run converges to d = 0.135556. The C1-shaped toy with b ≡ 0 aborts in TRSP₁; with a constant or Taylor basis, 6 of 6 starts end within 4e-3 of the grid optimum (5 Optimal, 1 at maximum iterations with θ = 3.1e-5). (b) **'Optimal' with zero TRSPs when θ_PMP = 0** (`TRF.py:78`, `:109`): one Ipopt solve, θ = 0, objective 0.3721 against a true optimum of 0, with a constant basis. (c) **The stall test compares θ with itself after any accepted step** (`:120` with `:265`), and the radius collapses to γ_c‖s‖ over the decisions (`:196`): 'Feasible solution found' at θ = 1.80 (true y 326.6, holder 96.1) |

**What the probe settles.** The framework composes with Python-callback EFs. It needs a gradient for every EF, the
ASL executable for its subproblems, identity-preserving callbacks, finite values, and an outer handler for refusals.
Nothing found requires the fallback.

## 5. The spike and its examples

### 5.1 TR-E1 — framework equivalence (oracle: Pyomo's own example)

Eason & Biegler's example 1 (Pyomo `contrib/trustregion/examples/example1.py`) is written as a `ProblemSpec`:
- variables `x0`, `x1`;
- parameters `z0`, `z1`, `z2`, which are the decisions: unbounded, centre 0, half-width 1, so the scaled decision
  equals the parameter;
- one `PropertyBlock` `bb`: input (x0, x1), output `s = sin(x0 − x1)`, Jacobian (cos, −cos);
- rows c1: `x0·z0² + bb.s − 2√2` and c2: `z2⁴·z1² + z1 − 8 − √2`;
- the objective of example 1, supplied as an `ObjectiveSpec`.

It is projected (§6.1) and solved by TRF with Pyomo's default configuration except `solver` (the alias). It is
compared with the native example run in the same process. It needs no flowsheet, so it runs before M02 and M04 merge.

### 5.2 TR-E2 — the eligible smooth gray-box example

**Formulation.** The C1 study formulation of §7.1, with three registered test parameters:
- the decision box T_in ∈ [653.15, 693.15] K;
- the reactor EF bound to `m05-synthetic-interior-v1` with its analytic gradient;
- no surrogate.

**The truth `m05-synthetic-interior-v1`.** A test-only, in-process variant in `tests/support/m05_synthetic.py`,
`synthetic: true`, never shipped. Its boundary block is the stand-in's (so it has no flow bound). It is shaped like
M04's synthetic variants (M04 spec §9.1).
- Per tube, z comes from (T, P, r, y_NH₃, y_Ar, y_CH₄, F) with M04's box, centres and half-widths (M04 spec §3.1).
- X = 0.16 · exp(a·z − z_T²), with a = (0.05, 0.04, 0.03, −0.05, −0.01, −0.015, −0.08).
- ΔT = 80 K · exp(b·z), with b = (−0.10, 0.03, 0.02, −0.04, −0.01, −0.01, −0.04) (M04's b).
- It returns n_raw = n_tube + ν X n_N₂,tube and T_out = T + ΔT, and has no failure region.
- Analytic gradient: ∂X/∂z_k = X (a_k − 2 z_T δ_kT) and ∂ΔT/∂z_k = ΔT b_k, chained to the inlet by M04's
  `input_jacobian` and 1/h_k.
- Its standalone maximizer in T is z_T = 0.025 (T ≈ 673.65 K), so the loop optimum is interior. With X ∈ [0.056, 0.16]
  over the box, the loop stays sane.

**Eligibility, per the TRF assumptions** (Eason & Biegler 2016, 2018; Yoshio & Biegler 2020):

| | Assumption | TR-E2 | Real reactor (stage C) |
| --- | --- | --- | --- |
| A1 | Glass-box functions C² near the iterates | Rows: smooth algebra by construction (the nonsmooth scan of §6.1 passes). Properties: C^∞ on a fixed root branch and phase regime (P4 checks the regime) | Same |
| A2 | Truth d is C² with a Lipschitz gradient | By construction (exp-polynomial) | **Assumed** (deterministic fixed-grid march, S3 rtol 1e-12), not proven |
| A3 | Model r_k is fully linear: r_k(w_k) = d(w_k), ∇r_k(w_k) = ∇d(w_k) | Holds: analytic ∇d | **Qualified**: FD ∇d; the gradient-check value is recorded |
| A4 | Each subproblem is solved; restoration exists | Ipopt tol 1e-8. **Pyomo 6.10.1 has no restoration phase**: a subproblem failure aborts (recorded) | Same |
| A5 | Bounded iterates | Finite decision box; domain bounds on states | Same |
| A6 | Constraint qualification at the limit | Not checked by TRF. With n_d = 1 it is trivial (at most one active bound); P5 is the local evidence | Same |
| A7 | Finite budget | 30 iterations, a cold cap; termination by budget is not convergence | Same |

TR-E2 is therefore **eligible**: A1–A3 and A5 hold by construction; A4 and A6 are stated limitations of the
implementation and the problem class; A7 is the budget. The real reactor is **qualified**, not eligible (A2 assumed,
A3 by FD). Its outcome is empirical, with no inherited stationarity guarantee (blueprint L443).

**Independent expectation (test support, not TRF and not Pyomo).** `tests/support/m05_reference.py` solves the C1 loop
at fixed T_in with a tightly coupled reference:
- the inner EO problem is solved at pinned w = (X̂, ΔT̂) through M02's inner-solve accessor (WO-5);
- the synthetic truth is evaluated at the inlet;
- Newton on w − (X_E, ΔT_E) uses a 2 × 2 FD Jacobian (h = 1e-7 scaled; scales 0.1 and 10 K) and stops at |F|_scaled
  ≤ 1e-12;
- golden-section search over T_in ∈ [653.15, 693.15] narrows the bracket to 0.05 K (14 golden steps); T_ref is the best
  point.

The reference has no M02 coupling-tolerance noise; it exists only in tests.

### 5.3 TR-E2-FD — the qualified mode on a known truth

TR-E2 with the reactor EF bound through `ParentExperimentTruth` (the production code path, §6.4) to the same synthetic
variant, using FD gradients (§6.5) instead of the analytic one. This exercises stage C's machinery and the accounting
cheaply, and measures what FD costs in accuracy (G6).

### 5.4 Why not other examples

- **The real reactor** cannot be eligible: its gradient is FD and its smoothness is assumed.
- **The M04 surrogate as truth** *is* eligible (polynomial, analytic gradient) and is used in stage A. But M04's real
  build is still running, and the spike must not depend on its outcome.
- **A SYN-001 unit as a black box** would be an artificial cut: SYN-001's loop has no expensive unit.

## 6. The composition and source maps

### 6.1 The projection compiler (`studies/trust_region/projection.py`)

**Inputs:**
- a `ProblemSpec` (`compile/spec.py`) and a state x₀ (every variable id → binary64);
- decision specs `DecisionSpec(parameter_id, lower, upper)`;
- external links `ExternalLinkSpec(unit_id, x_param_id, dt_param_id, inlet_variable_ids[7], truth)`, with the inlet in
  the order (n_H₂, n_N₂, n_NH₃, n_Ar, n_CH₄, T, P);
- inequality specs `InequalitySpec(inequality_id, build, upper, source, margin_rel)`;
- one `ObjectiveSpec(objective_id, sense, build, scale)`.

Each `build` is a builder over the projection's symbols and an `Algebra`, exactly as a `RowBuilder` is.

**Construction, in this order (the order fixes Pyomo component order and hence TRF's walk order):**

1. **Variables.** `m.x[i]` for `variable_ids[i]`, initialized to x₀. Bounds come from `variable_kinds`:
   - temperature [200, 1000] K and pressure [1e4, 3e7] Pa (the `pr-c1-v1` domain; the SYN-001 provider's own domain on
     SYN-001);
   - molar_flow ≥ 0, except a flow exactly 0.0 in x₀: it is no variable but the constant +0.0, eliminated with its
     certified pinning row (§17.1, R-296; it was left unbounded under ADR 0032 D4);
   - none otherwise.

   Scaling suffix: `scaling_factor = 1/S_x[id]`, with S_x from K03's `Scaling.from_spec` (§16, R-275).
2. **Decisions.** For a bounded `DecisionSpec`: c = (lo + hi)·0.5 and h = (hi − lo)·0.5 in binary64.
   `m.d[j] ∈ [−1, 1]` is initialized to (p₀ − c)/h, and the parameter's symbol is the expression `c + h·m.d[j]`. A
   `DecisionSpec` with `lower = upper = None` (TR-E1 only) is unbounded: `m.d[j]` has no bounds, is initialized to p₀,
   and is itself the symbol.
3. **External links.** For each link, the two pinned parameters become variables `m.w[u, "X"]` ∈ [0, 0.95] and
   `m.w[u, "dT"]` ∈ [−50, 250] K, initialized to their pinned values. Two EFs `m.ef_ext[u, "X"]` and
   `m.ef_ext[u, "dT"]` are created on the inlet variables (§6.3), with constraints
   `m.link[u, k]: m.w[u, k] == s_k · m.ef_ext[u, k](inlet…)`.
4. **Property blocks.** For each `PropertyBlock` b and each output o_k:
   - one EF `m.ef[b, o_k]` on `block_inputs[b]`;
   - one output variable `m.y[b, o_k]`, initialized to `values(x₀ inputs)[k]`, scaling 1/s;
   - one constraint `m.ydef[b, o_k]: m.y[b, o_k] == s · m.ef[b, o_k](inputs…)`.

   All outputs of a block share one holder (§6.3).
5. **Rows.** For each `EquationSpec` e: `expr = e.build(var_map, block_out_map, param_map, PyomoAlgebra)`, where:
   - `var_map[id] = m.x[i]`;
   - `block_out_map["b.o"] = m.y[b, o]`;
   - `param_map[p]` is the float, the decision expression, or `m.w[...]`.

   Then `m.row[i]: expr == 0`, with scaling `1/S_F[id]` (§16, R-275). Rows in the certified alias
   elimination are not projected (§16, R-274).
6. **Inequalities**, as `m.ineq[k]: g ≤ upper_tightened`, where `upper_tightened = upper − margin_rel·|upper|` (or
   `+margin_rel·|upper|` for a lower form).
7. **Objective**: `m.obj`, with `sense` and `1/scale`.

**`PyomoAlgebra`** implements exactly the `Algebra` protocol: `exp`, `log` and `sqrt` map to `pyomo.environ`'s. It is
**not a compile backend**: it implements no `CompiledProblem`, no route can select it, and it is imported only from
`studies/trust_region/` (guard test, G13).

**Refusals** (typed, raised before TRF runs; `PROJECTION_IMPLICIT_EF_INPUT` is added by §16.5, R-278):
- `PARAMETER_NOT_DIFFERENTIABLE(<equation_id>)`: a builder fails when a decision or link symbol is not a float (Pyomo
  raises on a boolean conversion of an expression). This is the same code and the same meaning as ADR 0031 D2.
- `PROJECTION_NONSMOOTH(<equation_id>)`: an expression contains `abs`, `Expr_if` or a piecewise node (walked with
  Pyomo's visitor).
- `PROJECTION_STRUCTURE(<variable_id>)`: a variable appears in no constraint after Pyomo's simplification. TRF's DOF
  count would otherwise fail opaquely.
- `PROJECTION_DOF(<n>)`: the count n_vars − n_equalities ≠ n_decisions. TRF's own check is repeated here so the failure
  is typed.

**EF output scale s.** For every EF output, s = 2^⌈log₂ max(|y(x₀)|, 1e-6)⌉: a power of two (exact), computed once per
projection from the start values and recorded in the source map. TRF's feasibility measure θ = Σ|y − d(w)| is then a
sum of relative discrepancies, so `feasibility_termination` = 1e-5 means about 1e-5 relative per output. For the
reactor with |ΔT| ≈ 90 K this is s = 128 and 1.3e-3 K: tighter than M02's 1e-2 K (ADR 0034 D3).

### 6.2 The source map

A canonical JSON document, `projection-source-map-v1`, stored by sha256 with the record. Pyomo names are index-based;
canonical ids appear only in the map. Fields:

- **`problem`**: `{label, model_version, structure_sha256, constants_sha256}`.
- **`variables`**: `[{pyomo: "x[i]", variable_id, kind, column_scale, bounds}]`.
- **`rows`**: `[{pyomo: "row[i]", equation_id, origin, row_scale}]`.
- **`block_outputs`**: `[{pyomo_var, ef, block_id, output_id, input_variable_ids, output_scale}]`.
- **`decisions`**: `[{pyomo_var: "d[j]", parameter_id, center, half_width, lower, upper}]`.
- **`external_links`**: `[{pyomo_var, ef, unit_id, parameter_id, coordinate: "X"|"dT", input_variable_ids, truth: {kind, id, sha256}, output_scale}]`.
- **`inequalities`**: `[{pyomo, inequality_id, source, upper, margin_rel}]`.
- **`objective`**: `{objective_id, sense, scale}`.
- **`omitted_rows`**: `[{equation_id, origin, reason, retained_path, residual_x0}]` (§16, R-274).
- **`scale_provenance`**: K03's `Scaling.from_spec` provenance, or `unit_no_kinds` (§16, R-275).
- **`trf`**: filled after a successful run from the returned model's `trf_data.truth_models`, as
  `[{holder: "trf_data.ef_outputs[i]", ef}]`.

**Invariants (G4):**
- the map is a bijection on every category;
- each `trf_data.ef_outputs[i]` maps to exactly one EF;
- every EF appears exactly once (the explicit output variables guarantee one EF node per output);
- every basis expression's variables belong to the clone (§6.6).

### 6.3 The `ExternalFunction` contract (`studies/trust_region/holders.py`)

There is one `EFHolder` per black box: per property block, and per external link.

- **Callables.** `value_k(*args)` returns `values(w)[k] / s_k`. `gradient_k(args, fixed)` returns row k of the dense
  Jacobian divided by s_k. Both read only the first `n_in` arguments.
- **Identity under clone.** `EFHolder.__deepcopy__(memo)` returns `self` (probe P2′). The callables are closures over
  the holder, and `deepcopy` treats functions atomically. Tested by a ledger count after a TRF run (G3).
- **Exact-key memo** on `tuple(float(a) for a in args[:n_in])`, separately for values and Jacobians.
- **Never non-finite.** A non-finite output raises `TruthRefused("non_finite_output")` (probe P7).
- **Refusals.** A property `DomainError`, an experiment status other than `ok` (`out_of_domain`, `model_exception`,
  `timed_out`, `external_environment_changed`, …), or a budget stop each raise `TruthRefused(status, reason)`. The TRF
  runner maps it to `TRF_TRUTH_REFUSED(<status>:<reason>)`. TRF has no recovery path (probe P6), so none is attempted
  inside a run (§6.7 gives the retry policy).
- **Budget.** Before every cold request, the holder checks the run's and the study's caps and raises
  `TruthRefused("budget", "budget_exhausted")`. The cap is never exceeded (G7).
- **Ledger.** Every request appends an entry (§8.1). The current TRF iteration number is taken from the log handler
  (§6.7).
- **Threading.** The memo and the ledger are guarded by one lock. Only the FD batch runs in worker threads (§6.5).

### 6.4 Truth adapters (`studies/trust_region/truths.py`)

`TruthModel` protocol: `describe()` returns `{kind, id, sha256, synthetic, gradient: "analytic"|"finite_difference"}`;
`evaluate(inlet)` returns `(X, ΔT, meta)`; `gradient(inlet)` returns a 2 × 7 matrix.

| Adapter | Values | Gradient | Used in |
| --- | --- | --- | --- |
| `ParentExperimentTruth(runner, variant, n_tubes, components)` | One M02 `ExperimentRunner.run` on the exact inlet; (X, ΔT) from M02's coupling coordinates (ξ_E/n_N₂,in, T_E − T_in), using M02's projection function, never a re-implementation. `meta` = {experiment_key, cache_hit, executions, status, extrapolated} | FD (§6.5) | stage C; TR-E2-FD; REAL |
| `SurrogateTruth(manifest)` | M04 `QuadraticSurrogate.predict(z(s))` | Analytic: M04 `inlet_sensitivity` | stage A |
| `SyntheticTruth(variant)` (tests) | Through `ParentExperimentTruth`'s runner path, so records and keys are produced | Analytic, closed form (§5.2) | TR-E2 |

**One `ExperimentRunner` per study.** M02's frozen identity (ADR 0034 D5) therefore covers every TRF call and every
coupled check of the study. A changed fingerprint is `TRF_TRUTH_REFUSED(external_environment_changed)`, and the study
fails.

### 6.5 The finite-difference policy `M05-fd-v1` (derivative-free truths only)

**Amended by §17.2 (R-297):** the policy is `M05-fd-v2`. Its gradient-quality check replaces the one below, and its
truncation analysis supersedes "Why forward". Scheme, steps, side rule and concurrency are unchanged.

- **Scheme.** Forward differences in the process-level inlet coordinates w = (n_H₂, n_N₂, n_NH₃, n_Ar, n_CH₄, T, P).
- **Step.** h_j = η · max(|w_j|, f_j), with f_n = 1e-3 · Σn, f_T = 1 K, f_P = 1e5 Pa and η = 2⁻¹⁴ (≈ 6.1e-5).
- **Exact differences.** w_j′ = fl(w_j + h_j) and h_eff = w_j′ − w_j, which is exact in binary64. The quotient uses
  h_eff.
- **Side.** +h, unless w′ leaves the truth's hard domain (judged by the variant's `Boundary` predicate before the
  request); then −h. If both sides leave it, `TruthRefused("fd_no_admissible_side")`.
- **Concurrency.** The 7 points run on a thread pool of min(7, physical_cores − 1) workers. The base point is always
  evaluated first, so M02's handshake happens before the batch. The two EFs of a link share the result: the second
  gradient call is a memo hit.
- **Gradient-quality check.** Once per study, at the first parent-truth point (the study's start inlet), compute
  G(η) and G(η/4), the forward FD gradients scaled as G_kj = g_kj · max(|w_j|, f_j) / s_k. It passes iff
  ‖G(η) − G(η/4)‖_∞ ≤ 1e-3 · max(1, ‖G(η)‖_∞). On failure η ← 4η, at most twice (η ≤ 2⁻¹⁰). If it still fails, the
  study proceeds with η = 2⁻¹⁰ and the assumption A3 is marked `fd_unstable`. The check costs 14 cold experiments.
- **Why forward.** The parent's march runs at rtol 1e-12 (R-250). With noise ε ≲ 1e-9 relative, forward error is
  ε/η + η·|f″|/2 ≲ 1e-4 relative, which is ample for a first-order model; the check measures it rather than assuming
  it. Central differences double the cost for no decision-relevant gain.
- **No production use beyond this.** FD values are never reported as sensitivities (§6.9).

### 6.6 Basis functions `M05-basis-v1`

TRF's `ext_fcn_surrogate_map_rule(component, ef_expr)` returns b(w) for each EF. The rule identifies the EF by its
component name, which is stable under clone, and **builds the expression on `ef_expr.args`**, the clone's variables,
never the original model's.

- **Property EFs: the affine Taylor model at w₀**, b = d(w₀) + ∇d(w₀)ᵀ(w − w₀), from one cheap block evaluation.
  Because r_k = b + [d(w_k) − b(w_k)] + [∇d(w_k) − ∇b]ᵀ(w − w_k) and b is affine, r_k is exactly the Taylor model at
  w_k: the basis changes only TRF's first subproblem (its "PMP"). There it replaces TRF's default b = 0, under which
  the PMP would see zero enthalpies and zero ln φ.
- **The reactor EF:**
  - with a **promoted** M04 surrogate for the bound parent: its quadratic, compiled from the manifest's coefficients
    through `PyomoAlgebra` on the clone's inlet arguments (M04 `basis(z)` over Pyomo expressions, z from the inlet as
    in M04 spec §3.1). It must agree with `QuadraticSurrogate.predict` at M04's J1–J3 within 1e-14 relative (WO-4);
  - otherwise **the affine Taylor model at w₀** (amended by §16.5, R-277; it was the constant d(w₀)). With a constant
    basis, C1's PMP freezes X̂ and ΔT̂, its objective no longer depends on T_in, Ipopt stays at the start, θ_PMP = 0,
    and TRF exits 'Optimal' with no subproblem step (probe P14 b). The gradient at w₀ comes from the truth adapter;
    for an FD truth, the study's first run reuses the gradient check's G(η) at the same w₀, and later runs pay n_in
    cold experiments.
- **A basis is mandatory** (R-277). `run_trf` refuses a missing or incomplete basis rule
  (`TRF_CONFIGURATION_REFUSED(basis_missing:<ef>)`). TRF's default b ≡ 0 is used only by TR-E1, through an explicit,
  test-only `zero_basis` that reproduces Pyomo's native example and is flagged in the record.
- **Stage A (surrogate as truth):** a constant basis; the truth is already exact and cheap.

The basis is frozen for the whole TRF run and the whole study: blueprint L427, and L437 (retraining voids the theory).

### 6.7 The TRF runner (`studies/trust_region/trf.py`)

**Pin (G2).** Before any run the runner checks:
- `pyomo.version.version == "6.10.1"`;
- the sha256 of `contrib/trustregion/{TRF.py, interface.py, filter.py, funnel.py, util.py}` equals the values WO-1
  records;
- the TRSP executable's sha256 equals the inventory's.

Any mismatch is `UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNPINNED)`.

**TRSP solver alias.** `openflowsheet_trsp_ipopt`, registered with `SolverFactory.register` at module import, is a
subclass of Pyomo's `IPOPT` shell plugin. It calls `set_executable(<sys.prefix>/bin/ipopt, validate=True)` and sets the
options `M05-trsp-ipopt-v1`:

| Option | Value | Why |
| --- | --- | --- |
| `linear_solver` | mumps | Audited; deterministic |
| `hessian_approximation` | exact | The TRSP is pure Pyomo algebra (rows, holder linearizations, basis polynomials), so the ASL computes exact second derivatives. ADR 0032 D2's L-BFGS concerns M03's twin, which has no Hessian; there is no conflict |
| `bound_relax_factor` | 0 | ADR 0032 D4: true domains |
| `honor_original_bounds` | yes | Same |
| `mu_strategy` | monotone | Determinism |
| `tol`, `constr_viol_tol`, `compl_inf_tol` | 1e-8 | As M03 |
| `dual_inf_tol` | 1e-6 | As M03 |
| `acceptable_iter` | 0 | Disables Ipopt's "acceptable" heuristic, so every TRSP is either solved to `tol` or fails typed. TRF's `check_optimal_termination` gate would otherwise depend on how Pyomo maps an acceptable exit |
| `max_iter` | 500 | As M03 |
| `max_wall_time` | 120 s | As M03 |
| `nlp_scaling_method` | user-scaling | Pyomo `scaling_factor` suffixes from §6.1 |
| `print_level` | 0 | `output_file` + `file_print_level 5` + `print_user_options yes` only in the options test |

The TRF's trust region is applied to the decision variables in their own units ("we assume users have correctly
scaled their variables"). The scaled decisions d ∈ [−1, 1] of §6.1 make that true.

**Configuration `M05-trf-config-v1`**, passed to `solve(model, decisions, basis_rule, **config)`, never to the
`SolverFactory` constructor (probe P8):

| Key | Value | Key | Value |
| --- | --- | --- | --- |
| solver | `openflowsheet_trsp_ipopt` | minimum_feasibility | 1e-4 |
| keepfiles, tee, verbose | false | switch_condition_kappa_theta | 0.1 |
| trust_radius | 0.25 | switch_condition_gamma_s | 2.0 |
| minimum_radius | 1e-4 | radius_update_param_gamma_c | 0.5 |
| maximum_radius | 1.0 (set explicitly: Pyomo's default is 100 × the default radius) | radius_update_param_gamma_e | 2.5 |
| maximum_iterations | 30 | ratio_test_param_eta_1 / eta_2 | 0.05 / 0.2 |
| feasibility_termination | 1e-5 | globalization_strategy | filter |
| step_size_termination | σ = 0.5 · min_j(δ_j / h_j), from the study's decision tolerances: 0.005556 for C1 REAL; 0.0125 for TR-E2 and the loops | maximum_feasibility | 50.0 |
| | | param_filter_gamma_theta / gamma_f | 0.01 / 0.01 |

TR-E1 uses Pyomo's defaults except `solver`, to reproduce the native example.

**State exposure (blueprint L443: trust-region and filter state, rejected steps).**
- During the run, a `logging.Handler` sits on `pyomo.contrib.trustregion` at INFO, with `propagate = False`.
- It parses each iteration's records: `****** Iteration k ******`, `trustRadius = …`, `feasibility = …`,
  `objectiveValue = …`, `stepNorm = …`, and the flags `f-type step`, `theta-type step` and `step rejected`. Floats are
  parsed with `float()`; `%s` of a float is its repr, so the round trip is exact.
- For an accepted step the logged radius is the *updated* radius; for a rejected step it is the radius the step used.
  The record says so.
- The filter is reconstructed: each θ-type accepted step adds (f − γ_f θ, (1 − γ_θ) θ).
- `stdout` is captured with `contextlib.redirect_stdout`. This swallows TRF's `model.display()` and keeps only the
  `EXIT:` lines. `redirect_stdout` is process-global, so **one TRF run per process**: the study controller never runs
  two TRF runs concurrently in threads.

**Outcomes** (the EXIT line and the logged values must agree, else `TRF_ERROR(exit_mismatch)`):

| Outcome | When |
| --- | --- |
| `TRF_CONVERGED` | "EXIT: Optimal solution found." with ≥ 1 accepted TRSP step, ‖s_k‖ ≤ σ, and θ re-checked from the returned model ≤ 1e-5 (§16.5, R-279) |
| `TRF_EXIT_WITHOUT_STEP` | "EXIT: Optimal solution found." with no accepted TRSP step (probe P14 b). It is not a convergence claim; the study treats the returned point as a candidate for stage B |
| `TRF_FEASIBLE_STALLED` | "EXIT: Feasible solution found." **and** θ re-checked ≤ 1e-5 (probe P14 c) |
| `TRF_STALLED_INCONSISTENT` | "EXIT: Feasible solution found." or (§17.4, R-299) "EXIT: Optimal solution found." with θ re-checked > 1e-5, which takes precedence over the rows below; `exit_claim` recorded. No candidate; the study treats it as an abort (retry once) |
| `TRF_MAX_ITERATIONS` | the maximum-iterations warning |
| `TRF_SUBPROBLEM_FAILED` | `ArithmeticError` from `solveModel` (the TRSP is not optimal) |
| `TRF_TRUTH_REFUSED(<status>:<reason>)` | `TruthRefused` |
| `TRF_ERROR(<exception class>)` | anything else, including the `ValueError` of TRF's DOF check |

Only `TRF_CONVERGED`, `TRF_FEASIBLE_STALLED` and `TRF_MAX_ITERATIONS` return a model: TRF returns its clone. The final
decision values are read from that clone through the source map. On abort the record keeps the iteration log and the
ledger, and **no candidate**.

### 6.8 Readiness `trust_region_readiness`

`READY` only when all of the following hold:
- the `nlp` environment is importable;
- the pin passes;
- the TRSP executable resolves and matches its hash;
- the projection compiles without refusal;
- the start re-solves certified (P1 at the start decisions).

Otherwise `UNSUPPORTED` lists every failing reason from: `TRUST_REGION_FRAMEWORK_UNAVAILABLE`,
`TRUST_REGION_FRAMEWORK_UNPINNED`, `TRSP_SOLVER_UNAUDITED`, `PARAMETER_NOT_DIFFERENTIABLE`, `PROJECTION_NONSMOOTH`,
`PROJECTION_STRUCTURE`, `PROJECTION_DOF`, `START_NOT_CERTIFIED`. In the default install the result is always
`UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNAVAILABLE)`, naming the audit, until the `nlp` extra is declared (N1). This is
M03 D5's pattern.

### 6.9 What the adapter never claims

- **No sensitivities.** The derivatives inside the TRSP (ASL) and the FD gradients of §6.5 are optimizer internals.
  None is reported as a sensitivity (blueprint §8.1), and ADR 0031 C3 is untouched.
- **No guarantees for qualified truths.** For a qualified truth, the record's `claims.trf_theory` is
  `qualified(<assumption ids>)`, never `assumptions_hold`.

## 7. The C1 study and the fixed-topology refinement loop

### 7.1 Registration `c1-trf-study-v1` (ADR 0039)

- **Case.** `C1-LOOP-M02-v1` (M02 design note §8.1): makeup 1.0 mol/s at 300 K and 10⁷ Pa; mixer → `c1.tp_heater`
  → reactor (N_tubes = 1000) → `c1.tp_flash` at 253.15 K; purge 0.02; zero ΔP.
- **Decision.** The heater outlet temperature specification (the pinned input of `c1.tp_heater`; ADR 0031 D1). The
  box is [643.15, 733.15] K, the inlet span of the kinetics' data domain (R-169), for the REAL study, and
  [653.15, 693.15] K for TR-E2 and the loops. The purge fraction is fixed at 0.02.
- **Objective `c1-obj-nh3-liquid-v1`.** Maximize the NH₃ molar flow of `c1.tp_flash`'s liquid outlet, in mol/s, with
  scale 1 mol/s.
  - *Why:* it is price-free and physical; at fixed makeup and purge it increases monotonically with the reactor's
    conversion; and the reactor's kinetic-versus-equilibrium trade-off gives it an interior optimum in T_in (ADR 0022
    D6).
  - *Rejected:* (T_in, φ) jointly under this objective. By the steady-state inert balance the purge loss of N₂ falls
    as φ falls, so φ runs to its bound: a degenerate "decision". An economic objective is Frank's call (N-F1).
- **Constraints**, generated from the bound variant and the definitions, never authored per case. Expression
  constraints carry a margin of 1e-6 relative:
  - **Hard domain** (the variant's `boundary.hard_domain`):
    - T_in and P_in: bounds on the reactor-inlet variables;
    - H₂/N₂ ∈ [1, 4] as n_H₂ − 4n_N₂ ≤ 0 and n_N₂ − n_H₂ ≤ 0;
    - inerts ≤ 0.2 as n_Ar + n_CH₄ − 0.2 Σn ≤ 0;
    - per-tube flow ∈ [0.5, 2] F₀ as bounds on Σn/N_tubes, for the real variant only (ADR 0034 D10).
  - **Admissibility A(s)** (M04 spec §3.2): X̂ ∈ [0, 0.95] and ΔT̂ ∈ [−50, 250] K (variable bounds);
    3X̂ n_N₂ − n_H₂ ≤ 0 (X̂ ≤ r/3).
  - **Provider domain** on every stream T and P; molar flows ≥ 0 (§6.1).
- **Stated limits, never constraints:**
  - `extrapolated`: counted per evaluation and carried by every candidate. It is not a constraint: the bed leaves the
    data domain at every registered state (R-169), so the constraint would be infeasible;
  - `surrogate_outside_reference_domain` (stage A, M04 spec §3.6);
  - `synthetic` (TR-E2 and the loops);
  - `fd_gradient` (parent truth).
- **Decision tolerance.** δ_T = 0.5 K (N-F2).

### 7.2 Stages

| Stage | What runs | Truth / basis | Start | Parent calls |
| --- | --- | --- | --- | --- |
| S0 | Coupled solve at the nominal decision u₀ (673.15 K); P1 must pass, else `FAILED(start_not_certified)` | parent (M02 `revision_coupled`) | M02 initializer | one coupled solve |
| A | TRF; only with a **promoted** M04 surrogate of the bound parent | surrogate / constant | S0 state | none |
| B | Parent checks P1–P5 at the current candidate (§7.4) | parent via M02 | — | 1 + (≤ 2 poll) coupled solves, plus 4 inner solves (no reactor) |
| C | TRF | parent via EF, FD gradient / promoted surrogate, else constant d(w₀) | the best parent-checked state so far (its certified coupled solution, so TRF's first evaluation at w₀ is a store hit) | 1 + 7 per accepted iteration, 1 per rejected |

### 7.3 The loop (deterministic)

```
S0 → best := u₀ (checked P1 only)
if promoted surrogate S for the bound parent:
    u_A := TRF(stage A);  P2_A := gross agreement with the surrogate-backed revision_eo re-solve at u_A
    cand := B(u_A);  if cand.status = PARENT_LOCAL_EVIDENCE: stop DECISION_STABLE
    best := argmax J over {S0, u_A, B's feasible poll points} among points passing P1, P3 and P4
else: record stage A skipped, reason surrogate_not_promoted
for k in 1..3:                              # K_max = 3 study iterations
    run C from best;  on abort: retry once from the same start with trust_radius × 1/4;
                      a second abort → stop FAILED(trf_aborted:<outcome>)
    cand := B(u_C)
    PARENT_LOCAL_EVIDENCE   → stop DECISION_STABLE
    NOT_STATIONARY_AT_DELTA → best := best feasible poll point; continue
    any other status        → stop FAILED(<status>)          # escalate to the design lane
stop ITERATION_LIMIT (best checked point reported, labelled not stable)
budget checked before every run and check → BUDGET_EXHAUSTED (never "stable", blueprint L427)
```

**"Refinement" in M05** means two things: TRF's per-iteration first-order correction of a frozen basis by parent
values and gradients, and the study-level restart from an improving poll point.

**No surrogate retraining in M05.** Within TRF, retraining voids the convergence theory (L437). Between study
iterations it is M04's business (M04 spec §5.5; its iterations are i.i.d. draws, and M05 must not inject targeted
points into M04's training sets without an M04 amendment). TRF's consistency correction makes retraining unnecessary
for correctness. This is a non-claim, §11.

### 7.4 Parent checks `M05-parent-checks-v1` (stage B)

Every check edits the C1 revision document in memory: the heater T spec takes the candidate's binary64 value. It then
canonicalizes the document, records its sha256, and solves through the route the document selects
(`run_revision_session`), without committing. Each evaluation is labelled `targeted_check` (M04 spec §7.4).

| | Check | Pass iff |
| --- | --- | --- |
| P1 | Targeted check | `revision_coupled` outcome `CONVERGED` and certificate `VERIFIED` |
| P2 | Gross agreement, TRF state against re-solve (a defect detector, not precision) | \|J_TRF − J*\| ≤ 1e-3 · max(\|J*\|, 1e-12), and max over mapped variables of \|x_TRF − x*\| / column_scale ≤ 1e-3 |
| P3 | Constraints on the certified state | every §7.1 inequality and bound holds within 1e-9 × its scale (no margin) |
| P4 | Regimes | every unit's phase regime label equals the S0 state's (fixed topology and fixed regimes) |
| P5 | Poll at the decision tolerance | for every feasible poll point j: J_j − J* ≤ e* + e_j |

**The poll and its noise floor.**
- **Points.** u* ± δ for each decision: 0.5 K for T_in. A decision within 1e-6 (scaled) of a box bound is at the
  bound, and only the inward point is polled. A point that would leave the box by less than δ is clipped to the
  bound. A point that fails P1 or P3 is infeasible and is ignored (extreme barrier).
- **Noise floor.** The coupled solves carry M02's coupling tolerance (ADR 0034 D3). For each solve i:

  e_i = 2 (|∂J/∂X̂| · ΔX_i + |∂J/∂ΔT̂| · ΔT_i)

  - ΔX_i = |ξ_E − X̂ n_N₂,in| / n_N₂,in and ΔT_i = |T_E − T_in − ΔT̂| are the *achieved* residuals, read from the
    certificate's `EXT-COUPLING` checks;
  - ∂J/∂X̂ and ∂J/∂ΔT̂ come from central differences of M02's **inner** EO solve at the candidate's converged w, with
    h_X = 1e-4 and h_T = 1e-2 K. These are 4 inner solves with no reactor call, reused for the poll points;
  - the factor 2 covers linearization and that reuse.

  The *achieved* residuals make the threshold small: the safe failure is an extra refinement, never a false
  stability.
- **Reported, not judged.** The curvature c = (J₊ − 2J* + J₋)/δ², and the indifference half-width √(2(e* + max e_j)/|c|)
  when c < 0: "J is within its noise floor for T_in ∈ [T* − w, T* + w]". This is the decision-relevant statement when
  the objective is flat.

**What P5 establishes.** No change of a decision by its tolerance improves the parent-checked objective by more than
its resolution. With n_d = 1 and the coordinate poll this is complete. By Kolda, Lewis & Torczon (2003, Thm 3.3), for
J ∈ C^{1,1} with constant M it implies |∇J(u*)| ≤ M δ/2 plus a noise term. It does **not** establish KKT on a curved
active constraint; that case does not arise with n_d = 1.

**Candidate statuses.** P1, P4, P3, P2 and P5 are evaluated in that order. All evaluated results are recorded, and the
status is the first failure:

| Status | First failure |
| --- | --- |
| `PARENT_CHECK_FAILED` | P1 |
| `REGIME_CHANGED` | P4 |
| `PARENT_CONSTRAINT_VIOLATED` | P3 |
| `PROJECTION_DISAGREES` | P2 (a defect: escalate) |
| `NOT_STATIONARY_AT_DELTA` | P5 |
| `PARENT_LOCAL_EVIDENCE` | none |

`NOT_CHECKED` means the budget ran out first.

**Study statuses:** `DECISION_STABLE`, `ITERATION_LIMIT`, `BUDGET_EXHAUSTED`, `FAILED(<reason>)` and
`UNSUPPORTED(<reasons>)`. The claims are always `global_optimality: false`.

### 7.5 Budgets `M05-budget-v1`

| Configuration | Study | TRF run |
| --- | --- | --- |
| REAL | ≤ 400 cold parent experiments, ≤ 4 h wall (N-F3) | ≤ 250 cold, ≤ 30 iterations |
| TR-E2, TR-E2-FD, LOOP-S, LOOP-R (in-process) | ≤ 2000 evaluations, ≤ 1 h | — |

The in-process budgets exist so the mechanism is exercised. K_max = 3 for every configuration.

### 7.6 The N6 and N1 branches

- **M04 N6, real surrogate not promotable.** Stage A is skipped (`surrogate_not_promoted`) and stage C runs with the
  constant basis. Nothing else changes.
- **N1 pending.** Build and evidence proceed in the audited environment, as M03's did. Merge with the `nlp` extra
  undeclared; the default install answers `UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNAVAILABLE)`. W24's claim reads "tested
  in the audited environment; not distributed until N1".
- **N1 denied.** ADR 0040 is activated for the distributed product (§10). The Pyomo evidence remains as evidence.

## 8. True-model call accounting

### 8.1 The truth ledger (`truth-ledger-v1`, JSON Lines, stored by sha256)

One entry per request a holder issues:

```
{seq, study_iteration, stage ∈ {S0, A, B, C, fdcheck}, trf_run, trf_iteration | null,
 purpose ∈ {trf_start_value, trf_pmp_value, trf_trial_value, trf_fd_point, fdcheck_point},
 truth: {kind, id}, inlet_sha256, experiment_key | null,
 served ∈ {cold, store_hit, memo_hit}, executions (attempts, M02 §3.3), status, extrapolated, wall_s}
```

Property-block EFs are counted in aggregate per block: values, Jacobians and memo hits. They are cheap and are not
true-model calls.

### 8.2 Coupled-check summaries

One per stage-S0 and stage-B coupled solve and per inner-FD batch:
`{check_id, candidate_id, purpose ∈ {start, targeted_check, poll, noise_floor}, run_id, coupling_record_sha256,
experiments: {executions, store_hits}, wall_s}`. The counts come from the run's `external-coupling.json` (ADR 0034 D6),
which embeds every request and attempt.

### 8.3 Totals and identities (G6, G7)

- **Totals** by stage, by study iteration, by candidate (the experiments spent to produce *and* check it) and overall,
  against the budgets.
- **Store bijection.** Every M02 store attempt record written during the study is attributed to exactly one ledger
  entry or coupled-check summary, keyed by (experiment_key, attempt).
- **TRF request identity.** TRF 6.10.1's call order is fixed:
  1. the start value at w₀ (`EFReplacement`);
  2. the PMP solve;
  3. the value and gradient at the PMP point;
  4. the log record of iteration 0;
  5. for each iteration k ≥ 1: if the previous step was accepted, the gradient at that iterate; then the subproblem;
     then the value at the trial point.

  The holder assigns each *first* request at a key a purpose from this order (the log handler's iteration state and
  the call type). Repeated TRF calls at a key are memo hits that the ledger counts but that carry no purpose; requests the FD policy
  issues carry their purpose whether cold, store or memo hits (§17.5 E3). For each
  TRF run with an FD truth the ledger must show:
  - `trf_start_value` = 1;
  - `trf_pmp_value` = 1, or 0 with the recorded flag `pmp_point_equals_start`;
  - `trf_trial_value` = K, the number of logged iterations ≥ 1;
  - `basis_fd_point` = n_in for a reactor EF with an FD truth and no promoted surrogate (§6.6). These are store or
    memo hits when the gradient check already ran at the same w₀;
  - `trf_fd_point` = n_in · (1 + A − [the final logged iteration was accepted]), with A the number of accepted steps
    and n_in = 7.

  The start is a store hit (the S0 or check state's own inlet). Then cold = requests − store_hit − memo_hit. The
  probe's native trace (§4, P2′: 6 points, 4 gradients, K = 4, A = 4, final accepted) satisfies the identity.

## 9. Records, schema and replay

### 9.1 Schema `schemas/trust-region-study.schema.json` (`trust-region-study-v1`, new, additive; ADRs 0038 and 0039)

Top-level fields:
- **`schema_version`, `study_id`.**
- **`spec`**:
  - `{case, revision_sha256, decisions[], objective, inequalities[], decision_tolerances, budgets}`;
  - `configs {trf, trsp, fd, basis, checks}` (registered ids);
  - `truth {kind, id, sha256, synthetic}`;
  - `surrogate {manifest_sha256, verdict} | null`.
- **`environment`**: `{pyomo_version, trf_module_sha256{}, ipopt_version, mumps_version, trsp_executable_sha256, platform}`.
- **`runs[]`**:
  - `{run_id, stage, study_iteration, retry, truth, basis, projection {source_map_sha256, n_vars, n_rows, n_block_efs, n_link_efs, n_ineq}}`;
  - `iterations[] {k, theta, objective, radius, step_norm, type ∈ {f, theta, rejected}}`;
  - `filter[] {f, theta}`;
  - `outcome`;
  - `final {decisions, objective, theta} | null`;
  - `ledger {sha256, summary}`;
  - `assumptions[] {id: A1..A7, status ∈ {holds_by_construction, checked(value), assumed, qualified(detail), limitation}}`.
- **`candidates[]`**:
  - `{candidate_id, run_id, decisions, label: "targeted_check", revision_sha256}`;
  - `checks {P1..P5 each {pass, values}}`;
  - `poll[] {decisions, J, e, feasible}`;
  - `noise_floor {dJ_dX, dJ_dT, e_star}`;
  - `curvature`, `indifference_halfwidth | null`;
  - `status`, `limitations[]`.
- **`accounting`**: `{totals, by_stage, by_iteration, by_candidate, budgets, exhausted}`.
- **`status`.**
- **`claims`**: `{global_optimality: false, trf_theory ∈ {assumptions_hold, qualified(...)}, stationarity ∈ {not_claimed, poll_at_delta}}`.
- **`limitations[]`.**
- **`artifacts`**: `{source_map, ledger, coupled_runs[]}`.

No existing schema changes. M04's surrogate manifest is read by hash; M02's records are referenced by run id and hash.

### 9.2 Reproducibility class

- An **in-process truth** (synthetic, surrogate) is re-evaluated on replay.
- An **out-of-process truth** is R3: replayed from the record by a recorded backend that serves ledger results under
  ADR 0034 D6's matching rule.
- The coupled checks replay through M02's own `reproduce`.

### 9.3 Replay test (G10)

Re-running a study from its record must reproduce the iteration log, the ledger sequence and the candidates
**bitwise on the same machine and environment** (probe P9 shows determinism). Across architectures the records are
compared under `T08-numerical-policy-v2`, with a test-level pre-pass (R-253's pattern): iteration counters and step
types by value; floats under the policy; `wall_s` positive.

### 9.4 R-253's watch-for

M05 adds **no product-level replay or compare of study records**. Its comparator lives in test support, as M03's
does. The move of the comparison rules into `run/compare` (an ADR 0025 amendment) is therefore a precondition for the
first package that exposes study replay (M07 if its journey needs it), not for M05 (R-271).

### 9.5 Exposure

- The library `openflowsheet.studies.trust_region`: `project`, `run_trf`, `check_candidate`, `run_study` and
  `trust_region_readiness`.
- Evidence scripts `scripts/m05_*.py`.
- Registered configurations under `benchmarks/m05/`.
- Committed records under `benchmarks/m05/records/`.

No job operation (R-273).

## 10. The fallback (ADR 0040, conditional)

**Triggers**, each recorded with evidence. Only these activate it:
- **T1:** Frank denies N1.
- **T2:** a composition failure that the registered remedies cannot fix. Either G4 fails irreparably, or at least 2 of
  the 4 in-process configurations end `FAILED(trf_aborted…)` after the retry.
- **T3:** the A10 extension (G1) fails **and** the cyipopt-shim contingency also fails. The contingency is
  `openflowsheet_trsp_cyipopt`, an alias that accepts and drops `keepfiles` and `tee` and solves through PyNumero
  cyipopt (already audited by M03). It must reproduce TR-E1 within 1e-8.

**Algorithm (scipy only; the project environment).** Reduced-space, first-order-consistent trust-region model
management (Alexandrov, Dennis, Lewis & Torczon 1998) over u ∈ [−1, 1]^{n_d}:
- **High-fidelity J_hi and g_hi**: from the parent-backed certified coupled solve.
- **Model m_k(u)** = J_lo(u) + [J_hi − J_lo](u_k) + [∇J_hi − ∇J_lo](u_k)ᵀ(u − u_k), with J_lo from the
  surrogate-backed certified `revision_eo` solve (promoted surrogate only). Without one it is the quadratic model
  J_hi(u_k) + ∇J_hiᵀs + ½sᵀB_k s, with B_k by damped BFGS (B₀ = −I in scaled units). Constraints get the same
  correction.
- **Gradients.** ∇J_hi by central differences of coupled solves at ±δ_j (the poll points, reused); ∇J_lo by central
  differences of surrogate solves with h = 1e-3 scaled.
- **Subproblem.** `scipy.optimize.minimize(method="SLSQP")` on the box ∩ {‖u − u_k‖_∞ ≤ Δ_k} with the corrected
  constraints.
- **Acceptance.** ρ = (J_hi(u_t) − J_hi(u_k)) / (m_k(u_t) − m_k(u_k)). Accept iff ρ ≥ 0.1 and P1 and P3 pass. If
  ρ < 0.25, Δ ← ½‖s‖; if ρ > 0.75 at the boundary, Δ ← min(2Δ, 1). Δ₀ = 0.25.
- **Stop** when Δ < δ/2 in scaled units. The parent checks of §7.4 then apply unchanged, as do the accounting, budgets
  and records (`runs[].stage = "F"`).

**May claim:** an empirical outcome of a first-order-consistent model management, plus the parent checks.
**May not claim:** "a tested trust-region framework" (D13); convergence guarantees (the gradients are FD of
tolerance-limited coupled solves).
**Cost:** per accepted iteration, 1 + 2n_d coupled solves (12–24+ experiments for n_d = 1), against stage C's 8
experiments. That cost is why it is the fallback.

## 11. What W24's M05 half may claim, and what it may not

**May claim, each with its gate:**
1. The documented Pyomo TRF (6.10.1, pinned) composes with OpenFlowsheet models through a projection compiled from
   the canonical `ProblemSpec` builders, with source maps and equivalence tests, and reproduces Pyomo's own example.
   (G2, G3, G4, G13)
2. On one eligible smooth gray-box example (TR-E2) the TRF converges to the independently computed optimum within the
   decision tolerance, and the candidate passes the parent checks. The theorem assumptions are stated item by item.
   (G5)
3. The same adapter runs with FD gradients on a derivative-free truth. Its accuracy is measured on a known truth (G6),
   and it runs with the real out-of-process reactor with complete true-model accounting (G7, G11).
4. Parent-model checks at candidates (targeted check, poll at the decision tolerance against a noise floor) and the
   fixed-topology refinement loop work, including the N6 branch. (G8, G9)
5. Hard domains and admissibility are kept as constraints; extrapolation, surrogate-domain, synthetic and
   FD-gradient limitations are kept as stated limits. (G7, G11, record content)

**May not claim:**
- global optimality;
- TRF convergence guarantees for the real reactor (A2 assumed, A3 by FD; and Pyomo 6.10.1 has no restoration phase);
- a validated plant optimum: every reactor result is extrapolated beyond the kinetics' data domain (R-169);
- the decision's sensitivities as reactor sensitivities;
- surrogate coverage at any candidate (M04 spec §7.4);
- anything about synthetic-truth results beyond the composition;
- the end-to-end real-reactor refinement (W25, M07).

**What M05 does not establish:**
- a decision for C1's purge fraction, or for any economic objective;
- that the real C1 optimum lies inside [643.15, 733.15] K: a bound-active result is reported as such;
- KKT on curved active constraints;
- cross-architecture bitwise identity;
- any property of the reactor outside its hard domain;
- any distribution of the TRF route before N1.

## 12. Work orders (dependency order)

"Opus" means `opus-engineer`; "bounded" means `sonnet-implementer` under a spec that leaves nothing to decide.
WO-1–WO-3 start from `main` now, with the audited environment from `wp/M03`. WO-4 onward start after M02 and M04
merge and M02's case JSON `C1-LOOP-M02-v1` exists: rebase `wp/M05` onto that merge.

| WO | Lane | Deliverable | Acceptance |
| --- | --- | --- | --- |
| WO-1 | bounded | The TRSP audit extension. A workload `trf-trsp-executable` (TR-E1's native example through the alias) runs in the audited environment with M03's inventory tooling. New files: `benchmarks/m05/trsp-inventory-x86_64.json` (loaded objects, licences, sha256 of `bin/ipopt` and the five TRF modules) and `docs/m05-trsp-audit.md` (verdict). M03's inventory is not edited | G1 |
| WO-2 | Opus | `projection.py`: `PyomoAlgebra`, `project()`, the source map, refusals, scales. `tests/test_m05_projection.py` covers SYN-001 at its K05 registered states and the TR-E1 spec. The backend-import guard's allow-list gains `studies/trust_region/` for `pyomo` only | G4 (SYN-001 and TR-E1 parts), G13 |
| WO-3 | Opus | `trf.py` and `holders.py` (base): pin, alias with `M05-trsp-ipopt-v1`, configuration, log handler and parser, stdout capture, outcomes, the holder (deepcopy identity, memo, non-finite guard, refusal mapping, budget), and TR-E1. The probe's findings P2′, P3, P6, P7 and P8 become tests | G2, G3 |
| WO-4 | Opus | `truths.py`: `ParentExperimentTruth` (M02 runner, the FD policy with thread pool and gradient check, hard-domain side rule), `SurrogateTruth` (M04), and `tests/support/m05_synthetic.py` (§5.2, analytic gradient). Concurrency equivalence: 7 distinct-key FD experiments run concurrently and serially give byte-identical store records (in-process synthetic). If `ExperimentRunner.run` is not safe for that, add `ExperimentRunner.run_batch` additively in M02's module, proven serial-equivalent; escalate if the handshake or lock logic must change. The M04 basis expression must match `predict` at J1–J3 within 1e-14 relative. **Also (§16.4):** the affine property basis of §6.6, and the `meta` contract `{status, cache_hit, experiment_key, executions, extrapolated}` for every adapter | §17.2 (i)–(iv) (replacing "analytic against FD on the synthetic ≤ 1e-6 relative at η", R-297); G7's mechanics on a unit run; §16.4's basis acceptance |
| WO-5 | Opus | `study.py` (formulation): the C1 decision, objective and inequality generation from the boundary block and the admissibility definitions; projection of the coupled route's inner `ProblemSpec` with (X̂, ΔT̂) promoted; M02's inner-solve-at-pinned-w accessor (additive and bitwise-inert if it is not public); `tests/support/m05_reference.py` (§5.2) | G4 (C1 part) |
| WO-6 | Opus | `checks.py` and `study.py` (loop): P1–P5, the noise floor, the poll, statuses, stages S0/A/B/C, retries, budgets, record assembly. **Also (§16.4):** `trust_region_readiness`'s projection and start halves | Unit tests on fakes for every status and precedence; every readiness reason produced by a fixture and `READY` on TR-E2's configuration; LOOP runs in WO-8 |
| WO-7 | bounded | `schemas/trust-region-study.schema.json` from §9.1. Default-gate tests on the committed records: schema, accounting arithmetic and identities (§8.3), status precedence, log-parser fixtures, readiness refusals without Pyomo | G12 |
| WO-8 | Opus | `nlp`-tier runs TR-E2, TR-E2-FD, LOOP-S (M04 smooth synthetic parent, the M04 pipeline's prefix-plan manifest, PROMOTABLE per M04 §9.2) and LOOP-R (rough, NOT_PROMOTABLE); records committed; same-machine replay | G5, G6, G7, G8, G9, G10 |
| WO-9 | Opus (opt-in `pymrm`) | REAL: gradient check at the start inlet; stage A and B if the real surrogate is promoted; stage C and checks under `M05-budget-v1`; record committed; replay from the record | G11, G10 (REAL part) |
| WO-10 | bounded | Support-matrix and limitation lines, `docs/progress.md`, `evidence/M05/<commit>/manifest.json`, the W24 gate table for `verdict` | Manifest `status: tested` with the commands actually run |
| WO-F | Opus, **only if ADR 0040 is activated** | `studies/trust_region/fallback.py` per §10, sharing checks, accounting and records | ADR 0040's gates F1–F3 |

Added by §17.6 (2026-10-09): WO-2b (zero-flow elimination), WO-3b (exit precedence), WO-4a (`M05-fd-v2`, the TR-E1
tolerance, E2's guard test) and WO-5b (`with_coupling` on `wp/M02`).

## 13. Gates (each decidable from a recorded number)

| Gate | Criterion | Configuration |
| --- | --- | --- |
| G1 | The TRSP workload inventory passes M03's G1–G6 criteria. Recorded: no object of unknown origin; no GPL without the runtime exception; no CasADi METIS-closure object; METIS ≥ 5; MUMPS as the linear solver and no HSL; the default install unchanged. The sha256 of `bin/ipopt` and the five TRF modules are recorded | x86_64 audited env |
| G2 | Pin: the run proceeds with 6.10.1 and the recorded hashes; with a patched version string or one changed module byte, readiness is `UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNPINNED)` (two tests) | nlp |
| G3 | TR-E1 against native: same iteration count (5) and step-type sequence; final values within 1e-10 absolute (bitwise equality reported); the original holder's ledger sees 6 distinct cold points and 4 gradient points; the options test finds every `M05-trsp-ipopt-v1` option echoed | nlp |
| G4 | Projection equivalence at the registered states: SYN-001's K05 states; C1 at S0's certified state and at that state with every variable perturbed by a seeded relative 1e-3; TR-E1 at its start. (a) The source map is a bijection with DOF = n_d. (b) max \|r_pyomo − r_casadi\| / row_scale ≤ 1e-12 · max(1, \|r\|/row_scale). (c) x-Jacobian entries agree within 1e-10 · (\|J\| + J_scale), with J_scale = row_scale/column_scale. (d) Decision columns agree with central FD of the CasADi residual (test oracle, h = 1e-6 scaled) within 1e-7 relative. (e) No nonsmooth node. (f) Exact-zero flows are eliminated with certified pins (§17.1, R-296); (a) is over the projected variables and rows; C1's R-278 matching is 68 × 68 | nlp |
| G5 | TR-E2: `TRF_CONVERGED` in ≤ 30 iterations; θ_final ≤ 1e-5; \|T*_TRF − T_ref\| ≤ 0.5 K; candidate `PARENT_LOCAL_EVIDENCE`; study `DECISION_STABLE`; the assumptions block equals §5.2's TR-E2 column | nlp |
| G6 | TR-E2-FD: `TRF_CONVERGED`; \|T*_FD − T*_exact\| ≤ 0.1 K; `fd_check` (`M05-fd-v2`, §17.2) passes at η = 2⁻¹⁴, class `clean` or `truncation_dominated`, no escalation; §8.3's request identity holds exactly for every run | nlp |
| G7 | Accounting, every run: the store bijection holds; cold + store_hit + memo_hit equals requests; 0 non-finite outputs returned to TRF; cold requests ≤ cap (the budget test drives a run into the cap and finds exactly cap cold requests and `TRF_TRUTH_REFUSED(budget:budget_exhausted)`) | nlp, pymrm |
| G8 | LOOP-S: stage A executed with the PROMOTABLE prefix-plan manifest; study `DECISION_STABLE`; \|T* − 653.15 K\| ≤ 1e-6 K (lower bound active: X decreases in T for M04's synthetic, a_T < 0) | nlp |
| G9 | LOOP-R: stage A skipped with `surrogate_not_promoted`; stage C with the constant basis; `DECISION_STABLE`; \|T* − 653.15 K\| ≤ 1e-6 K | nlp |
| G10 | Replay: TR-E2 re-evaluated and REAL from its record give bitwise-identical iteration logs, ledger sequences and candidates on the same machine; the cross-architecture comparison passes under `T08-numerical-policy-v2` with §9.3's pre-pass | nlp, pymrm, CI |
| G11 | REAL mechanics (opt-in): `fd_check` is recorded with its class, τ̂, ν̂ and selected η (§17.2); stage C makes ≥ 1 accepted iteration and ends with a typed outcome within `M05-budget-v1`; G7 holds on the run; every candidate has a status; the limitations include `extrapolated` (with its count) and `fd_gradient`. The optimality outcome is reported, not gated (W25) | pymrm |
| G12 | `./scripts/check.sh` passes with no Pyomo or Ipopt import; the committed records validate and pass §8.3's arithmetic; readiness without the `nlp` environment is `UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNAVAILABLE)` | default |
| G13 | No second model and no backend: `projection.py` imports nothing from `openflowsheet.models`; `pyomo` is imported only under `studies/nlp/` and `studies/trust_region/`; no route or `compile_problem` path reaches `PyomoAlgebra` (guard tests) | default |

## 14. Risks

| Risk | Likelihood / effect | Mitigation and signal |
| --- | --- | --- |
| A TRSP failure aborts TRF (no restoration) at C1 scale | Medium / lost run | Initial radius 0.25, one retry at ¼ radius, typed outcome. Two aborts across the in-process set fire T2 |
| Property linearization rejects steps, and each costs a parent call | Low–medium / cost | Measured by the rejected-step count and θ's share by EF class in the record; the REAL budget caps it |
| A reactor `model_exception` inside the hard domain aborts TRF | Unknown / lost run | Inward FD side rule; retry; typed. A recurrence is a finding for M02/M01, not something M05 works around |
| A flat objective at the coupling noise floor makes P5 pass over a wide interval | Likely on the real case / weak decision | The indifference half-width is reported; the decision is stated "at resolution". Not hidden |
| Pinned Pyomo internals (log text, EXIT prints) | Certain on upgrade / adapter breaks | Version and hash pin; G2 fails loudly; an upgrade is a new ADR |
| `redirect_stdout` is process-global | Certain if misused | One TRF run per process (§6.7), asserted by a test running two studies in two processes |
| The real optimum lies outside [643.15, 733.15] K | Unknown | Bound-active result reported; the box is N-F6 |
| `ExperimentRunner` not thread-safe for concurrent distinct keys | Unknown | The WO-4 test; additive `run_batch` |
| Pyomo's `.sol` precision differs across architectures | Certain at ulp level | Bitwise only on the same machine; cross-architecture under the policy (G10) |
| M02's C1 case JSON or M04's build late | Schedule | WO-1–WO-3 proceed; WO-4 onward wait |

## 15. Open questions, each with a default

### 15.1 Needs Frank (preferences)

- **N-F1 — the C1 objective.**
  DECISION: maximize the liquid NH₃ product at fixed purge 0.02, with one decision T_in. Alternative: an economic
  objective (NH₃ value minus heater and chiller duty at Frank's prices), which also makes φ a meaningful second
  decision. Reversible by: a new objective id and a second `DecisionSpec`. The adapter is generic in n_d; the poll
  becomes ±e_j in each coordinate.
- **N-F2 — the decision tolerance.**
  DECISION: δ_T = 0.5 K. Alternative: 1 K (cheaper; coarser claim) or 0.1 K (likely below the coupling noise floor).
  Reversible by: one registered number, which also feeds `step_size_termination`.
- **N-F3 — the real-reactor budget for M05's opt-in run.**
  DECISION: ≤ 400 cold experiments and ≤ 4 h on the 24-core workstation. Alternative: only a targeted check at a
  stage-A candidate (≈ 20–40 experiments), leaving stage C on the real parent to M07. Reversible by: skipping WO-9;
  G11 is then reported `not_run`, and W24 claim 3 narrows to the synthetic FD evidence.
- **N-F4 — N1, inherited.**
  DECISION: proceed in the audited environment and merge gated (§7.6). Alternative: wait for N1 before merging.
  Reversible by: nothing to undo; the default install is unchanged either way.
- **N-F5 — N6, inherited.**
  DECISION: the surrogate is used only if promoted (as a stage-A truth and as a basis). Alternative: use any fitted
  manifest as a TRF basis; the theory does not need its accuracy. Reversible by: the basis-policy flag
  `promoted_only | any_fitted`.
- **N-F6 — the REAL decision box.**
  DECISION: [643.15, 733.15] K, the kinetics' inlet data span. Alternative: M04's box [653.15, 693.15] K, inside the
  surrogate's reference domain. Reversible by: one registered pair.
- **N-F7 — a job operation.**
  DECISION: none in M05. Alternative: a `trust_region_study` job operation now (ADR 0019 amendment). Reversible by: an
  additive operation in M07.

### 15.2 Facts, with what settles them and the default meanwhile

- **The reactor's output noise.** Settled by WO-9's `fd_check` (21 experiments, §17.2). Default η = 2⁻¹⁴.
- **Whether `ExperimentRunner.run` is safe for concurrent distinct keys.** Settled by WO-4's test. Default: the
  additive `run_batch` if it is not.
- **Whether M02 exposes an inner solve at pinned w.** Settled by WO-5. Default: an additive accessor.
- **Whether the real loop's optimum is interior in [643.15, 733.15] K.** Settled by WO-9. Default: report whatever
  structure is found.
- **Whether M03 audited aarch64.** Default: the TRSP extension, like M03's, covers x86_64 only, and the `nlp` tier runs
  there.

## 16. Rulings on WO-2 and WO-3 as built (2026-10-09)

These rule on the build lane's escalations from `aaa2452`, `545a385` and `dd9e364`. Measured at `dd9e364`: default
gate 7951 passed; `nlp` tier 67 passed; G2, G3 and G13 hold.

### 16.1 Omitted rows (R-274): confirmed, amended to be derived and certified

SYN-001's spec has 49 rows over 47 variables. Two of the rows are certified pressure alias rows that the retained rows
imply. Projecting all 49 makes TRF's DOF count n_d − 2, which is refused as `PROJECTION_DOF`.

**Ruling.** A row is omitted from the projection **iff** `orchestrator/rank.py`'s `eliminate_alias_rows` eliminates
it. This is the same elimination, with the same inputs and tolerances, that the certificate applies
(`verify/certificate.py`) and that M03's sensitivities apply (`studies/sensitivity.py`). The projection computes the set
itself. It is never caller-chosen: a caller-supplied `omitted_rows` is accepted only if it equals the certified set,
and otherwise it is refused as `PROJECTION_OMITTED_ROW_UNCERTIFIED(<id>)`.

**What certifies an omitted row.** All four of the following, recorded in the source map's `omitted_rows`:
1. **Eliminated by the certified algorithm.** The row is affine in pressure columns with ±1 coefficients and lies on a
   retained-forest path. The path is recorded as `retained_path`.
2. **Satisfied at the start.** Its residual at x₀ is within the elimination's `pressure_tolerance`. The value is
   recorded as `residual_x0`.
3. **Consistent with the decisions.** Every decision's tangent residual on the row is ≤ τ_alias = 1e-8 (ADR 0031 D3
   Q3; ADR 0032 D1). Otherwise the projection is refused before any solve.
4. **Satisfied at the final state.** At every TRF final state the omitted rows are evaluated and recorded. A residual
   above `pressure_tolerance` fails P2 (`PROJECTION_DISAGREES`).

P1's certified re-solve checks every row anyway (R-188).

The DOF check remains n_vars − (n_rows − n_omitted) − n_block_outputs − n_links = n_d. C1's zero-ΔP pressure loop is
expected to yield its own alias rows, under the same rule and with no case-specific code.

### 16.2 Scales (R-275): K03's `Scaling.from_spec` everywhere

**Ruling.** One source of row and column scales for the projection: K03's `Scaling.from_spec(spec)`, the scales that
M03's full-space NLP and the certificate use. It governs:
- G4's denominators: (b) row scale, (c) J_scale = S_F/S_x, and (d);
- the Ipopt `scaling_factor` suffixes (1/S_x, 1/S_F);
- P2's state comparison;
- the scales recorded in the source map.

`ProblemSpec.row_scales` and `column_scales` are not read directly.

**A spec without kinds** (only the test-only TR-E1, where `from_spec` cannot build) uses unit scales, recorded as
`scale_provenance: "unit_no_kinds"`. **A spec with partial kinds** is refused as `PROJECTION_SCALES_UNAVAILABLE(<ids>)`.

The measured worst ratios to tolerance stand under this ruling: SYN-001 ≤ 5.9e-4 / 7.1e-7 / 2.3e-3; TR-E1 1.5e-4 / 0 /
2.9e-4. G3 is unchanged, because TR-E1 keeps unit scales. After switching the suffix, re-run G3 and G4 once; nothing
registered depends on SYN-001's TRSP iterates.

**Rejected:** the spec's unit scales. Rounding alone fails G4(b) in raw watts, at a ratio of 21.8.

### 16.3 TRF swallows start-value refusals (R-276): a pre-flight, plus a backstop

P13 (§4): `EFReplacement.exitNode` swallows any exception from the start-value evaluation and sets the holder to 0.
The build lane's holder now records every refusal, and `run_trf` reports it. That is necessary, but not sufficient: a
swallowed start refusal can be followed by a run that ends "optimal".

**Ruling. Pre-flight.** Before calling `solve()`, `run_trf` evaluates every EF holder at x₀ (values only). A refusal
there is `TRF_TRUTH_REFUSED(start:<status>:<reason>)`, and TRF is never invoked. TRF's own start evaluation then becomes
a memo hit. The ledger's `trf_start_value` request is the pre-flight's, so §8.3's identity is unchanged.

**Ruling. Backstop invariant.** If any holder recorded a refusal during a run, the outcome is
`TRF_TRUTH_REFUSED(<first refusal>)` with no candidate, whatever TRF returned or printed. A test drives a refusal
through `exitNode`'s bare `except` and asserts both the pre-flight and the backstop.

Nothing more is needed: `interface.py:86` is the module's only bare `except`, and every other evaluation propagates
(probe P6).

### 16.4 Gaps assigned

| Gap | Assigned to | Acceptance |
| --- | --- | --- |
| Affine property basis (§6.6) | WO-4 (Opus) | At w₀ the basis value equals the block's value bitwise, and its `differentiate` gradient equals the block Jacobian within 1e-15 relative; every basis variable belongs to the clone; TR-E1 with an affine basis on `bb` and native both end `TRF_CONVERGED` with ‖Δz‖_∞ ≤ 2e-5 (probe P5's analogue; amended by §17.3, R-298, from 1e-6) |
| `trust_region_readiness`: projection and start halves (§6.8) | WO-6 (Opus) | Each reason code is produced by a fixture; `READY` on TR-E2's configuration |
| `TruthBox`'s `meta` contract | WO-4 (Opus) | Every `TruthModel.evaluate` returns `meta = {status, cache_hit, experiment_key, executions, extrapolated}`. `SurrogateTruth` and in-process test truths return `status: "ok"`, `cache_hit: false`, `experiment_key: null`, `executions: 0`, `extrapolated: false`; the ledger records them with `truth.kind` and they never count against parent budgets. `ParentExperimentTruth` maps M02's `ExperimentOutcome` exactly |

### 16.5 Probe P14 (R-277 to R-279)

**Verdict.** P14 is a configuration defect and two mislabelled exits. It is not a failure of the trust-region method.
The abort comes from TRF's default b ≡ 0, which ADR 0038 D7 already rejects: `run_trf` had been called with
`basis_rule=None` because M05-basis-v1 was not built yet. **ADR 0040's T2 does not fire.** A
`PROJECTION_IMPLICIT_EF_INPUT` refusal on C1 itself would count as a structural composition failure under T2. That
should not happen: C1 is forward by construction (the inner problem at pinned w is S0's certified simulation).

**R-277 — a basis is mandatory; the reactor's fallback basis is affine.** Recommendations 1 and 3(a) are accepted:
- `run_trf` refuses a missing or incomplete basis rule;
- `zero_basis` exists only for TR-E1;
- without a promoted surrogate, the reactor EF gets the affine Taylor basis at w₀ (§6.6 amended). With a Taylor basis
  and an exact gradient, an early exit at θ_PMP = 0 means the start satisfies the KKT conditions of the true problem;
  with an FD gradient, it is qualified.

**R-278 — shape check `PROJECTION_IMPLICIT_EF_INPUT`.** Recommendation 2 is accepted with one amendment: only the
**link** (expensive) EF outputs are fixed. Property-block relations y = s·EF(inputs) stay structural functions.
- *Why the amendment:* with property outputs fixed as well, the check would refuse every property-based flowsheet. A
  mixer outlet temperature enters the rows only through h(T), so fixing h leaves T undetermined. Property EFs are
  cheap, have exact gradients, and their Taylor models determine those inputs in every TRSP.
- *The test.* Unknowns: every projection variable except the decisions. Equations: the kept rows, the block
  definitions (incident on y and on all of their inputs), and the link definitions (incident on w only, because the
  holder is fixed).
- *Pass iff* the square incidence has a perfect matching: `scipy.sparse.csgraph.maximum_bipartite_matching`, or Pyomo's
  `incidence_analysis` if it yields the same verdict. It is structural; numeric regularity is S0's K04 certificate on
  the same system.
- *Refusal:* the unmatched variables and equations, with the link-EF inputs flagged.
- *Coverage.* This is exactly the probe's definition of "safe". It catches an EF output pinned by the decisions
  (`y = 90z`) and a conversion target. An outlet-temperature specification passes if the remaining glass box still
  determines the inputs given ΔT̂ (a forward loop, like C1's recycle). The criterion, not a list of examples, governs.
- *Exemption.* TR-E1 is exempt, recorded as `shape_check: exempt_oracle`. Pyomo's example is itself implicit: x1 enters
  only through the EF, and c2 involves only decisions.

**R-279 — exits are classified from the model, not from the EXIT line.** Recommendations 3(b) and 4 are accepted and
generalized:
- after every exit, θ is re-computed from the returned model: the truth at the final w against the holder values, all
  memo hits;
- `TRF_CONVERGED` needs at least one accepted TRSP step and θ ≤ 1e-5. An Optimal exit without a step is
  `TRF_EXIT_WITHOUT_STEP`, and the study sends its point to stage B;
- a "Feasible" exit with θ > 1e-5 is `TRF_STALLED_INCONSISTENT`, an abort for the retry policy;
- θ_recheck is recorded for every run.

Defect 2's radius collapse is TRF's own behaviour. It is not patched (pin, R-260); only its labelling is guarded.

**Work orders:**

| Item | WO |
| --- | --- |
| Basis refusal and `zero_basis`; the exit classification (`TRF_EXIT_WITHOUT_STEP`, `TRF_STALLED_INCONSISTENT`, θ_recheck) | WO-3a (amends the built `trf.py`) |
| `PROJECTION_IMPLICIT_EF_INPUT` | WO-2a (amends `projection.py`) |
| Affine reactor basis with FD reuse; `basis_fd_point` in the ledger | WO-4 |
| Study handling of the new outcomes | WO-6 |

**Acceptance:**
- WO-3a reproduces P14 (a)–(c) as tests: refusal on `None`; toy A with a constant basis gives `TRF_EXIT_WITHOUT_STEP`;
  the implicit toy gives `TRF_STALLED_INCONSISTENT` at θ = 1.80.
- WO-2a refuses `y − 90z` and passes SYN-001 and C1 (C1 when it exists).
- G3 is unchanged (TR-E1 with `zero_basis`, exempt from the shape check).

## 17. Rulings on WO-4 and WO-5 as built (2026-10-09)

These rulings answer the build lane's escalations at `wp/M05` `6b54b8d` (brief `docs/briefs/v02-rulings-M05-M04.md`,
Part A). They are register entries R-296 to R-300.

### 17.1 Exact-zero flows at x₀ (R-296): eliminated as constants together with their pinning rows

**Measured.** TRF on C1 TR-E2 stops before iteration 1 with `TRF_TRUTH_REFUSED(property_domain_error:S1_Hdot_V)`. At
the PMP point `S1.n.NH3 = −3.448e-27`, and `pr-c1-v1` refuses n < 0. The flows that are exactly zero at x₀ are
`S1.n.NH3` and `S6.n.{H2,N2,Ar,CH4}`.

**Diagnosis (corrects the escalation's).** The rows that pin these flows *are* projected. R-274 omits only the two
zero-ΔP pressure alias rows (`flash:C1FL-P:inlet`, `splitter:C1SPLIT-P:recycle`; `e1c9af0`). Two kinds of row pin the
five flows:
- `S1.n.NH3` is pinned by the feed's `specification_row`, n − n_spec with n_spec = 0.0 (`models/rows.py:75`);
- the light-gas liquid flows are pinned by the flash's `zero_row`, r = l_i (`models/c1/flash.py:229`).

§6.1 leaves these five flows unbounded (ADR 0032 D4). Ipopt satisfies a linear row only up to linear-algebra roundoff,
so x = −O(1e-27) is a legitimate PMP iterate. TRF evaluates the truth at that iterate, outside Ipopt, and the provider
is right to refuse it. Any projection that leaves an exactly-zero flow free and unbounded will meet this on some TRSP.
Restoring a row cannot help, because the rows were never missing.

**Ruling: rule `M05-zero-flow-v1`.** Such a flow is not a variable of the projection. It is a constant, eliminated
together with the row that pins it. `project()` applies the rule after computing R-274's set and before step 1 of §6.1:

1. **Candidates.** Z₀ = {j : kind(j) = `molar_flow` and x₀[j] == 0.0}. Start with E = ∅ (eliminated flows) and P = ∅
   (their pins).
2. **Pairing, repeated until nothing changes.** Look for a kept row e ∉ P, not omitted by R-274, whose structural
   incidence minus E is exactly {j}, with j ∈ Z₀ \ E. The pair (j, e) is certified iff all three of these hold:
   - (i) r_e(x₀) == 0.0 exactly;
   - (ii) ∂r_e/∂x_j(x₀) ≠ 0, taken from the CasADi Jacobian that G4 already evaluates;
   - (iii) the decision and link tangent of e at x₀ is exactly 0.0, computed as in R-274's criterion 3.

   A certified pair adds j to E and e to P. Rows are visited in spec order and the first certified row for a given j
   wins, so the result is deterministic. Repeating the pass handles a chain of zero flows: once a dormant unit's inlet
   is eliminated, its outlet row has a single incidence.
3. **Refusals.** Every j ∈ Z₀ must end up in E. The projection refuses with one code and three reasons:
   - a j ∈ Z₀ that stays unpaired: `PROJECTION_ZERO_FLOW(<id>:unpinned)`;
   - a kept row whose incidence minus E is empty and which is not in P: `PROJECTION_ZERO_FLOW(<row>:redundant_row)`;
   - a j ∈ E among a link EF's inlet arguments: `PROJECTION_ZERO_FLOW(<id>:link_input)`. The FD policy has no rule for
     a constant inlet coordinate, and no registered case needs one.
4. **Substitution.** In `var_map`, each j ∈ E is the Python float `+0.0` (canonical, via `normalize_zero`), never a
   `Var`. The rows in P are not built. A property-block EF receives the constant as an argument:
   - Pyomo's `differentiate` and TRF's `identify_variables(..., include_fixed=False)` (`trustregion/interface.py:226`)
     skip it, so TRF's Taylor model has no column for it;
   - the affine basis of §6.6 builds terms only for `Var` arguments;
   - the holder receives exactly `+0.0`, so every memo key equals x₀'s.
5. **Record and check.** The source map records `zero_eliminated: [{variable_id, row_id, residual_x0, dr_dx}]`. The
   inverse map writes `+0.0` for these variables into every TRF final state, and so into P1's re-solve start. At every
   final state the rows in P are evaluated and recorded, as in R-274's criterion 4: a residual above the row's
   tolerance fails P2 (`PROJECTION_DISAGREES`).

*Why not `Var.fix`.* TRF counts degrees of freedom over every variable-type node in the active constraints, fixed or
not (`interface.py:60–69`, `:184–193`). A fixed `Var` with its row deactivated is still counted, which is +1 degree of
freedom per variable. With the row left active, Ipopt sees a row with no free variable.

**Effects.**
- *DOF.* |E| variables and |E| rows leave together, so §16.1's count is unchanged (C1: n_d = 1).
- *LICQ.* Each pin has incidence {j} and a nonzero pivot, so J = [[∂_j r_e, 0], [a_j, A]] and rank J = 1 + rank A. The
  reduced problem's constraint qualification is exactly the full problem's, and nothing degenerate is added.
- *R-278 and G4's matching.* In every perfect matching a pin is matched to its own j, so removing the pairs leaves the
  matching perfect. For C1 TR-E2 the matching goes from 73 × 73 to **68 × 68**.
- *G4 (b) and (c)* are evaluated over the projected rows and columns. The perturbed state already keeps exact zeros at
  zero.

**Rejected.**
- *A bound n ≥ 0.* The pin's gradient and the active bound's are parallel, so LICQ fails at every feasible point. With
  `bound_relax_factor = 0` no strictly interior point satisfies n = 0, so MFCQ fails too, and Ipopt's `bound_push`
  moves n off 0 at its start. This is ADR 0032 D4's own reason.
- *Fixing it as a Pyomo `Var`.* It fails TRF's DOF count (above).
- *Restoring a pinning row.* The rows were never missing.
- *Clamping n ∈ (−ε, 0) to 0 in the holder.* It quantizes a state coordinate on the exact path (CLAUDE.md), and the
  truth's key would no longer be the state.
- *Widening `pr-c1-v1`'s domain.* That would move the identity of a frozen provider.

**Scope.** This is an M05 projection rule. **ADR 0032 D4 is not amended.** D4's clause "pinned there by its regime's
own rows" is exactly what (i)–(iii) certify; M05 makes the pin exact by construction instead of leaving it to Ipopt's
roundoff.

*Watch-for (M03; not decided here).* M03's full-space path also evaluates property blocks at Ipopt iterates while such
flows are free and unbounded. If it ever hits n < 0 at O(1e-27), the remedy is this rule, adopted by an ADR 0032
amendment.

**Acceptance (WO-2b).**
- (a) On C1 TR-E2, `zero_eliminated` is exactly five pairs:
  - `S1.n.NH3` with the feed's specification row;
  - `S6.n.{H2,N2,Ar,CH4}` with the four C1FL zero rows.

  Each pair has `residual_x0 = 0.0` and |`dr_dx`| > 0.
- (b) The shape check finds a perfect 68 × 68 matching, and DOF = 1. Any other count stops the work order and is
  reported.
- (c) G4 (a)–(e) are re-run at S0 and at the perturbed S0, and the worst ratios are recorded.
- (d) TRF on TR-E2 gets past iteration 1 with no `TRF_TRUTH_REFUSED`. Every truth request's arguments at the five
  positions are `+0.0`, bitwise.
- (e) Toy fixtures produce each refusal reason: `unpinned` (a zero flow pinned by a decision-dependent row),
  `redundant_row` and `link_input`.
- (f) SYN-001's and TR-E1's G4 parts are unchanged. If SYN-001's K05 states hold exact-zero flows, WO-2b lists them, and
  (a)–(c) apply to them as well.

### 17.2 FD policy `M05-fd-v2` (R-297): forward differences kept, the check made curvature-aware

**The measurement is truncation, and it was predictable.** Take TR-E2's start, where z_T = 0. M04's half-width is
20 K, the step is h_T = η·673.15 K = 0.0411 K, and so δz = h_T / 20 K = 2.05e-3. The synthetic (§5.2) gives X′ = 0.05·X
and X″ = −1.9975·X per unit z. The forward truncation error relative to the entry is then (δz/2)·|X″/X′| =
**4.10e-2**, which is the measured worst value. Three consequences follow:
- No forward scheme can meet 1e-6 at a step above the noise floor.
- Truncation is linear in η, so G(η) − G(η/4) ≈ ¾ of the truncation at η. That is the measured 0.0373.
- Escalating η makes that difference grow; the measurements are 0.149 and 0.598.

`M05-fd-v1`'s check therefore reads curvature as noise.

**What truncation costs the decision.**
- *The optimum moves by about half a step.* Near a stationary point, a forward difference in coordinate j equals the
  exact derivative at w + ½h_j·e_j, to second order. The stationary point of the FD-model problem is therefore
  displaced by about ½h_j in the dominant coordinate. In T that is **≈ 0.02 K**, against δ_T = 0.5 K (N-F2), the poll's
  ±0.5 K and G6's 0.1 K.
- *Convergence is unaffected.* The model error after a step s is ≈ ½h·|d″|·|s|, which is second order, so θ → 0 still.

Truncation is therefore bounded in advance by the step. What can destroy a gradient is noise, which scales as ε/h, and
noise is what the check has to measure.

**Ruling.** The scheme, steps, exact differences, side rule, concurrency and reuse of §6.5 are unchanged (D8 stands).
The gradient-quality check is replaced, and the policy id becomes `M05-fd-v2`. `M05-fd-v1` produced no committed record
and is retired.

- **Three steps.** At the study's first parent-truth point w₀, evaluate d(w₀), then forward gradients at η/4, η and 4η
  with η = 2⁻¹⁴: 1 + 21 cold experiments (v1 needed 1 + 14).
  - G is scaled as before: G_kj = g_kj·m_j / s_k, with m_j = max(|w_j|, f_j).
  - Each column's side is chosen once, at its largest step 4η·m_j, so all three steps of a column lie on one side.
  - The reactor basis gradient at w₀ (§6.6) is the check's G at the selected η, with the check's per-column sides, so
    its n_in requests are memo hits.
- **Statistics,** entrywise:
  - D₀ = G(η) − G(η/4);
  - ρ = G(4η) − 5·G(η) + 4·G(η/4);
  - truncation estimate τ̂ = (4/3)·‖D₀‖_∞;
  - noise estimate ν̂ = ‖ρ‖_∞ / 14.

  *Where the 14 comes from.* Write G(η) = G* + c₁η + c₂η² + noise. Then ρ cancels G* and c₁ exactly, and its truncation
  part is 11.25·c₂η². For independent evaluation noise σ, sd(ρ) = 20.2σ/η, while the noise in G(η) has
  sd = 1.41σ/η.
- **Pass and class.** The check passes iff ν̂ ≤ 1e-3·max(1, ‖G(η)‖_∞), the registered allowance. A pass is classed
  `clean` if τ̂ is also within that allowance, and `truncation_dominated` otherwise. A failure is `noise_dominated`.
- **Escalation, for noise only.**
  - The candidates are η ∈ {2⁻¹⁴, 2⁻¹², 2⁻¹⁰}. Each step up reuses two gradients and adds G(4η): 7 cold.
  - Escalation continues only while ν̂ falls by at least a factor 2 per step. A residual that grows with η is
    curvature, not noise.
  - If the new largest step is not admissible on a column's chosen side, escalation stops (`side_limit`).
  - If no candidate passes, the study proceeds with the candidate of smallest ν̂ (on a tie, the smaller η), and A3 is
    marked `fd_unstable`. Production FD then uses the selected η.
- **Cost.** The worst case is 1 + 35 cold, once per study. TRF iterations still cost 1 + 7.
- **Record** `fd_check`:
  - the policy id;
  - for each candidate η: ‖G‖, τ̂, ν̂ and the class;
  - the selected η and the result;
  - ½h_j for each of the 7 coordinates.

  The study ledger shows 7·(3 + e) check requests, where e is the number of escalations (G7).

**Rejected.**
- *Central differences.* The truncation error becomes h²·|f‴|/6, which is 4.2e-6 relative on dX/dT, so it still fails
  1e-6. It doubles the cost per iteration to 1 + 14: 30 × 15 = 450 cold against the run cap of 250, which would bind at
  about 16 iterations. All of that buys a 0.02 K displacement that is already irrelevant to the decision.
- *Range-scaled steps* (h_T = η·20 K). These would pass v1's check (0.0373/33.7 = 1.1e-3 ≤ 2.27e-3), but only because
  this synthetic's curvature scale happens to equal M04's half-width; the misreading would stay hidden. The steps would
  also depend on a surrogate's box, need a range registry for the flows, and amplify noise 34-fold in T.
- *A smaller η.* It tunes the step to the synthetic, whose noise is about 1e-16, and pushes the real reactor's unknown
  noise floor toward failure.
- *Escalating in both directions.* Choosing a direction needs a classification first, which is the check adopted here.
  Truncation needs no smaller step.

**New WO-4 acceptance, replacing "≤ 1e-6 relative at η".** On the synthetic, at TR-E2's start inlet:
- (i) *Richardson.* ‖(4·G(η/4) − G(η))/3 − G_exact‖_∞ ≤ 1e-5·max(1, ‖G_exact‖_∞). Predicted ≈ 5e-7.
- (ii) *The estimate bounds the error.* ‖G(η) − G_exact‖_∞ ≤ 2τ̂ + 1e-6·max(1, ‖G_exact‖_∞). Predicted 0.044 against
  about 0.10.
- (iii) *The check passes at 2⁻¹⁴ without escalating*, classed `truncation_dominated`. Predicted ν̂ ≈ 4e-6 against
  2.27e-3.
- (iv) *Noise is detected.* Add deterministic pseudo-noise of relative amplitude 1e-6 to (X, ΔT), as a function of the
  exact input bits (SHA-256 mapped to [−1, 1]). The check is then `noise_dominated` at 2⁻¹⁴, and ν̂(2⁻¹²) < ν̂(2⁻¹⁴).

**G6 restated.**
- TR-E2-FD ends `TRF_CONVERGED`, with |T*_FD − T*_exact| ≤ 0.1 K (predicted ≈ 0.02 K).
- `fd_check` passes at 2⁻¹⁴ with class `clean` or `truncation_dominated`, without escalation.
- §8.3's identity holds exactly.

**G11.** `fd_check` is recorded with its class, τ̂, ν̂ and selected η. Implemented by WO-4a.

### 17.3 TR-E1 basis acceptance (R-298): restated at the termination TR-E1 actually runs with

**Facts.**
- *TR-E1's own stopping tolerance is 1e-5.* TR-E1 runs Pyomo's defaults, so `step_size_termination` =
  `feasibility_termination` = 1e-5 (`TRF.py:383`, `:392`). "Within 1e-6" asked the two runs to agree ten times more
  closely than the step at which either may stop.
- *Measured:* |Δz| = 1.18e-6, 1.11e-6 and 5.7e-7, with the objectives within 4e-11 relative.
- *The limit cannot tell bases apart.* Under the affine basis, r_k is the Taylor model at w_k for every k ≥ 1 (§6.6).
  What tests the basis is the bitwise value test, the gradient-at-w₀ test and the clone-membership test.

**Ruling.** §16.4's third criterion becomes:
- both runs end `TRF_CONVERGED` with θ_recheck ≤ 1e-5;
- ‖z_affine − z_native‖_∞ ≤ 2σ = **2e-5**, absolute (TR-E1 has unit scales and O(1) values). Each run's final point
  lies within σ of the limit under a contraction of at most ½;
- |ΔJ| / max(1, |J|) is recorded.

The measured values pass with a margin of 17.

**Rejected.** Tightening TRF's termination for this test. The steps would plateau at Ipopt's `tol` = 1e-8, risking
`TRF_MAX_ITERATIONS`, and the result would still say nothing about the basis.

Implemented by WO-4a; only the test's tolerance changes.

### 17.4 An "Optimal" exit with θ_recheck > 1e-5 (R-299): `TRF_STALLED_INCONSISTENT`

**Ruling.** An "EXIT: Optimal solution found." whose θ, re-checked from the returned model, exceeds 1e-5 is
`TRF_STALLED_INCONSISTENT`. It yields no candidate and counts as an abort for §7.3's retry: once, with trust_radius × ¼.
The record carries:
- `exit_claim: "optimal"`;
- θ_logged and θ_recheck;
- `final_state_is_last_truth_point`: whether the returned w equals, bitwise, the w of the ledger's last truth request.

Exits are classified in this order of precedence:
1. `TRF_TRUTH_REFUSED` (the backstop, R-276);
2. θ_recheck > 1e-5 gives `TRF_STALLED_INCONSISTENT`, whatever the EXIT line says;
3. `TRF_EXIT_WITHOUT_STEP`;
4. `TRF_CONVERGED` or `TRF_FEASIBLE_STALLED`.

`TRF_ERROR(exit_mismatch)` keeps its meaning: an EXIT line that disagrees with TRF's own logged values, which is parser
or framework drift. That is a defect and is never retried.

**Why.** R-279 classifies an exit from the model; the EXIT line is only a claim. A point TRF calls optimal while its
truth disagrees most plausibly means TRF terminated on a state other than the one it returned, for example after a
rejected-step reset. A smaller radius changes the trajectory, which is what the retry is for. A holder defect cannot
hide behind the retry: a second abort is `FAILED(trf_aborted:TRF_STALLED_INCONSISTENT)`, which reaches the design lane
with the diagnostic fields.

**Rejected.** `TRF_ERROR(exit_mismatch)`: it labels an inconsistent model state as a parser defect and forfeits the
retry.

**Acceptance (WO-3b; §6.7's table amended).** A test drives an "Optimal" exit with a holder value perturbed after the
last truth request, and gets `TRF_STALLED_INCONSISTENT` with `exit_claim: "optimal"`. P14 (a)–(c) are unchanged.

### 17.5 Build decisions at WO-4/5 (R-300)

| # | Decision | Ruling |
| --- | --- | --- |
| E1 | The parent-truth `meta` has a sixth key, `code` | **Confirmed.** §16.4's contract has six keys: `{status, code, cache_hit, experiment_key, executions, extrapolated}`. `code` is M02's outcome code verbatim, `""` when there is none. Every adapter emits it, `""` for surrogate and test truths. WO-7's schema includes it |
| E2 | (X, ΔT) computed from the envelope as (ξ/n_N₂,in, T_out − T_in) | **Confirmed, as an interim.** WO-4a adds a guard test at TR-E2's start and at two FD points. There M05's values must equal the coupling coordinates M02's coupled-route residual uses at the same envelope, obtained through M02's own code path. Bitwise is required, or within 4 ulp where only a reconstruction from the residual is available. When M02 exposes a coupling-coordinate function, M05 calls it (register watch-for) |
| E3 | The ledger records explicit FD purposes on memo hits | **Confirmed.** It is needed to attribute requests to purposes under §8.3. §8.3's sentence is amended: repeated *TRF* calls at a key carry no purpose, while requests the FD policy issues (`basis_fd_point`, `trf_fd_point`, the check's) carry theirs, whether cold, a store hit or a memo hit |
| E4 | A non-parent holder refuses a parent budget (`ValueError`) | **Confirmed.** It is a configuration error at construction, never a `TruthRefused` |
| E5 | `project(variable_bounds=…)` | **Confirmed; additive.** It may only intersect a kind's bounds, and the result is recorded in the source map. Naming a decision or an eliminated zero flow (§17.1) raises `ValueError` |
| E6 | The concurrency test runs without the artifact sink, because artifact ids depend on completion order | **Confirmed, for WO-4's store-record test only.** New invariant: nothing a record or the ledger carries may depend on completion order, and artifacts are referenced by SHA-256. WO-6's record assembly enforces this. WO-8 adds a test: the FD batch with the sink, run concurrently and serially, must give byte-identical store records and ledger. If that needs M02's lock or handshake logic changed, escalate (WO-4's clause) |
| E7 | `revision_binding.with_coupling` | **Lands on `wp/M02` as a byte-identical cherry-pick with its inertness test (WO-5b). No separate review:** it changes no existing path, its test proves it inert, and M05's single `reviewer` pass covers it. It stays an accessor of the binding and never becomes a revision parameter (R-287). If `wp/M02` merges first, M05's rebase drops its own copy |

### 17.6 Work orders and gates changed

| WO | Lane | Deliverable | Acceptance |
| --- | --- | --- | --- |
| WO-2b | Opus | §17.1 in `projection.py`: the elimination, the source map's `zero_eliminated`, the refusals, the final-state evaluation of P | §17.1 (a)–(f) |
| WO-3b | Opus | §17.4 in `trf.py` | §17.4's test; G3 unchanged |
| WO-4a | Opus | `M05-fd-v2` (§17.2) in `truths.py`; tests (i)–(iv); §17.3's TR-E1 tolerance; E2's guard test | §17.2 (i)–(iv); §17.3 |
| WO-5b | bounded | E7's cherry-pick to `wp/M02` | The inertness test passes on `wp/M02`; M02's full gate is unchanged |

**Order.** WO-2b comes first, because it unblocks every C1 TRF run. WO-3b, WO-4a and WO-5b depend neither on it nor on
each other. WO-6 continues meanwhile, and WO-8 needs all four.

**Gates.**
- G4 (C1): (a) is taken over the projected variables and rows, with `zero_eliminated` certified (§17.1). R-278's matching
  is 68 × 68.
- G6 is as restated in §17.2.
- G11 also records the check's class.
- §16.4's basis criterion is as restated in §17.3.

### 17.7 Open questions, each with a default

| # | Question | Kind | Default |
| --- | --- | --- | --- |
| F-9 | What is the real reactor's FD noise floor? | Fact: WO-9's `fd_check` | `M05-fd-v2` as ruled. If REAL is `noise_dominated` even at 2⁻¹⁰, the study runs `fd_unstable` and G11 reports it. The policy changes only by a new ruling |
| F-10 | Do SYN-001's K05 states hold exact-zero flows? | Fact: WO-2b (f) | The rule applies uniformly, and G4's SYN-001 part is re-run |
| F-11 | Is M03's full-space path exposed to §17.1's roundoff? | Fact: an M03 run on C1 | No change to M03. A hit opens an ADR 0032 amendment that adopts §17.1 |

None of these needs Frank.
