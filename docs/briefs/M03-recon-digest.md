# M03 recon digest (read-only)

Source tree read: worktree `.claude/worktrees/m06-contract`
(branch wp/M06-contract, HEAD f085d14). Relative to main at the files that matter for M03, the only
difference is decision-register.md (main adds R-170..R-175, none M03-related). Venv: `.venv`.
Root below = `.claude/worktrees/m06-contract`.

## 0. Bottom line

- M03 has NO code yet: no sensitivity, dR/dp, adjoint, sweep, Study, ExperimentRequest, OptimizationReport,
  estimation, identifiability, or NLP adapter. V02_STATE.md:20 says `M03 | Design | T08 | W24 (part) | not started`.
- The only derivative machinery: K01 exact sparse Jacobian, JVP, VJP (casadi_backend.py); K03 Schur-complement dR/dt for the 3-variable tear (orchestrator/tear.py).
- Parameters are pinned inputs baked into compiled functions as constants. There is no symbolic dF/dp anywhere. `Capabilities` has no parameter-derivative field.
- No ipopt/cyipopt/pyomo in requirements.lock, pyproject, or the venv. CasADi's bundled `nlpsol:ipopt` IS present and loadable, but ADR 0003 Q3 and ADR 0006 D2.4 forbid using it (METIS closure).

## 1. Requirements text (plan, blueprint)

### 1a. Plan (`docs/implementation-plan.md`)
- L265 (M03 row, §4.4): `| M03 | T08: sweeps, implicit sensitivities and small parameter-estimation example; general NLP gray-box/cyipopt adapter. | Sensitivity/adjoint checks on regular roots; singular-state refusal; identifiable vs unidentifiable fit; optimizer with verified constraints and Hessian policy. | NUM | Design / Build |`
- L271: "The Pyomo general NLP adapter and trust-region adapter are separate deliverables. A cyipopt success does not complete M05. Compile any needed Pyomo glass-box projection from canonical equations; do not maintain a second hand-authored reactor/flowsheet. If the chosen framework cannot consume the intended mixed model, document the failing composition and implement an ADR-backed tested alternative before claiming that gate."
- L353 (W24): `| W24 | Fixed-topology optimization, eligible trust-region example and parent-model checks | M03/M05 |`
- L308 (D13): `| D13 multi-fidelity optimization | M05 | Tested framework path, assumptions, finite-budget truth checks |`
- L311 (D16): `| D16 drafts/readiness | K06, M03 | Incomplete draft persistence; task-specific closure |`
- L321 (A06): `| A06 distinct bridges | M03, M05 | Gray-box NLP and trust-region compositions tested separately |`
- L95: "Optional JVP/VJP/Hessian capabilities are negotiated. A missing exact Hessian cannot be replaced with fabricated zeros."
- L107 region (§2.1 minimum interface): "Optional capabilities are JVP, VJP, parameter derivatives, Hessian-vector products, batched evaluation, symbolic export, and generated code." (That sentence is from blueprint §3.2 at L107; plan L95 is the short form.)
- L413-ish is A07 (not M03).
- L593 (v0.2 scope): "Fixed-topology continuous optimization with final parent-model checks; a tested trust-region adapter for one eligible smooth gray-box example, with assumptions and costs reported."
- L606 (v1 acceptance): "Support a constrained optimization and finite synthesis demonstration with qualified ev[idence]".
- L560 (v0.2 scope row): "fixed-topology optimization" in v0.2.
- L199-ish (spike): CasADi `casadi.Callback` composition; assert sparsity pattern; plan §4.1-4.2 spike text.
- L33-50 plan §1.3 lane rule: design lane owns "all derivations (SYN-001, PTC mapping, sensitivities)"; "backend decision and every ADR"; "adversarial verifier tests". Build lane owns "unit-model implementation". M03 lead = Design (NUM), second Build.

### 1b. Blueprint (`docs/blueprint-v3.1.md`)
- §10 Studies, optimization (L429-447):
  - L431: "First implement sweeps, local sensitivities, and parameter estimation; then continuous constrained optimization on a fixed topology. Studies distinguish free simulation variables from design decisions, measured data from exact specifications, and physical feasibility from optimizer termination."
  - L433: "For a regular reduced simulation, compute sensitivities from Fₓ xₚ = −Fₚ using the converged Jacobian, with branch and conditioning qualifications. Estimation records observation covariance, identifiability, parameter bounds, and validation data. Optimizers receive true domain restrictions; a penalty is not equivalent to guaranteed constraint satisfaction."
  - L435: "Use an established constrained NLP implementation through a source-mapped adapter. Reduced-space and full-space formulations share model semantics but have different execution costs and derivative requirements. Record objective, primal violations, active constraints, KKT measures where available, multistart evidence, and termination limitations. Local stationarity is not global optimality."
  - L437: "For eligible expensive smooth gray-box models, default to a tested trust-region framework through the Pyomo bridge before writing a new optimizer."
  - L439 **[A06 — two distinct bridge mechanisms]**: "The Default general NLP bridge wraps `CompiledProblem` as a PyNumero `ExternalGreyBoxModel`/block, exposing variables, residuals, sparse Jacobian, and optional multiplier-weighted Hessian to cyipopt. Supply objective/constraint metadata and scaling consistently. Without reliable Hessians, explicitly configure a supported approximation. This numerical adapter does not hand-transpile a second flowsheet model."
  - L441: trust-region framework uses Pyomo `ExternalFunction`, is "not automatically compatible with an opaque `ExternalGreyBoxModel`"; needs glass-box projection; "do not claim trust-region guarantees merely because the generic cyipopt bridge solves an NLP."
  - L443: adapter must expose "truth-model evaluation, reliable gradients or an explicitly qualified alternative, local model construction, trust-region/filter state, rejected steps, and cost."
  - L445: experiment selection = bounded space-filling and sensitivity-directed sampling.
- §5.1 nested-solve sensitivities (~L173-175): "If an inner model solves g(w,u) = 0 and returns y = h(w,u), its local derivatives can use dw/du = −g_w⁻¹ g_u, dy/du = h_u − h_w g_w⁻¹ g_u." Also "This requires a locally nonsingular inner Jacobian ... A derivative through an incompletely converged algorithm is not automatically the derivative of the intended model."
- §5.2 (L179-181): "Declare analytic, AD, implicit, finite-difference, generalized, or unavailable derivatives by output and operating regime. ... Exact-Hessian optimization may need more; second derivatives of properties and second derivatives of their generating potential are not interchangeable requirements." "Check directional derivatives and the identity vᵀ(Ju) = (Jᵀv)ᵀu."
- §6.3 phase boundaries (L224): "Near critical points, implicit flash sensitivities can become ill-conditioned. Do not return an ordinary smooth Jacobian with no qualification. Crossing a phase boundary is allowed in simulation ...; it does not automatically authorize smooth gradient-based optimization across it."
- §3 table (L81): "Study runtime | Sensitivity, estimation, optimization, fidelity experiments | Unrecorded model substitution during a fixed solve".
- §3.2 (L107) optional capabilities quoted above; "Capability absence must not force a model to invent derivatives."
- §4.3 L146: "`READY_FOR_OPTIMIZATION` permits declared decision variables and requires a valid optimization formulation."
- §4.3 L148: matching/DM structural; "They do not prove nonlinear feasibility, numerical nonsingularity".
- §8.1 A08 (L370-374): "Never diagnose target rank from the regularized or PTC matrix." ... "Residual satisfaction and regularity are separate checks: a rank-deficient root can be isolated (for example x² = 0)..." and L374 last sentence: "A study may explicitly request residual-only evidence for a singular problem, but it cannot relabel that as regularity or reliable sensitivity evidence. Optimization uses task-appropriate constraint/KKT diagnostics rather than applying the square-simulation rank test to free decision variables."
- §9.3 (L423-425): "Where F(x,p,m) = 0 is locally regular, process adjoints can translate model residual discrepancy into approximate objective or constraint impact."
- §12/Appendix A L670: `OptimizationReport | Model/study hash, candidate, feasibility, stationarity evidence, truth evaluations, domains, starts, budget and limits`. L669-ish: `ModelEvidence`, `SurrogateManifest` rows.
- L366: "An optimization result has a separate optimality report. A single green badge must not imply all three."
- L493 tooling: "Pyomo | Optimization and diagnostics bridge in v0.2, with explicit unsupported operations".
- A05 (L95): CasADi vs Pyomo/PyNumero/ASL comparator.
- A10 (L101): binary inventory includes "the Pyomo/PyNumero/ASL/cyipopt comparator and its numerical dependencies".
- Appendix/§14.4 v0.2 (L588-597).

### 1c. Requirements register (`docs/requirements.yaml`)
- D13 (L279-285): `packages: [M05]`, minimum_evidence "Tested framework path, assumptions, finite-budget truth checks", tests: [], status: planned.
- D16 (L330-352): `packages: [K06, M03]`, minimum_evidence "Incomplete draft persistence; task-specific closure". L347-350 comment: "Status `implemented`, not `tested`: M03 owns the optimization closure, which is a different requirement from simulation closure (D16 says so)." tests: `tests/test_k06_application.py::test_d16_an_incomplete_draft_is_committable`.
- A06 (L502-506): `packages: [M03, M05]`, minimum_evidence "Gray-box NLP and trust-region compositions tested separately", tests: [], evidence: [].
- A08 (L520-524): `packages: [K04, T06]`, "Final unregularized Jacobian; bounded condition/rank checks".
- W24 (L739-742): required_evidence "Fixed-topology optimization, eligible trust-region example and parent-model checks"; owner_packages [M03, M05]; verdict null; evidence [].
- M03 package entry (L955-960): `phase: "v0.2"`, `lead: Fable`, `second: Opus`, `depends_on: [T08]`, `status: planned`, `evidence: []`.
- M05 entry (L975ish): `depends_on: [M03, M04]`.
- Note the register keeps `lead: Fable` (design-lane naming); CLAUDE.md says Fable reads as design lane.

### 1d. Frozen interfaces / schemas
- `schemas/README.md:63` and `docs/interfaces-frozen.md:47`: `M01–M04 | ExperimentRequest/Result, ModelEvidence, Study, SurrogateManifest, OptimizationReport`. These are NAMED but NOT implemented: no files in `schemas/` for them (listing shows only api-error, application-results, attempt-context, ..., validation-report, units.json; none for Study/Experiment/OptimizationReport/Surrogate), and no class in `src`.
- `docs/interfaces-frozen.md:31,33`: JVP/VJP/Hessian negotiated; missing Hessian "reported as absent, never replaced with zeros".

## 2. Requirement-level tensions to surface to specifier (facts only)

- Hessian: `capabilities.hessian = "absent"` (casadi_backend.py:369). ADR 0003 D5.4 + R-003 say exact Hessian through opaque callbacks is absent. A06 requires optional multiplier-weighted Hessian "without reliable Hessians, explicitly configure a supported approximation." Consistent so far, but NO approximation is implemented.
- Parameter derivatives: blueprint §3.2 lists them as optional; `Capabilities` (compiled.py:61-73) has jacobian/jvp/vjp/hessian only.
- Sensitivity refusals: many SYN-001 unit models declare sensitivity `unavailable` by note (see §3c). Declaring `analytic` for a parameter derivative would have no caller.

## 3. Code

### 3a. K01 compiled problem (CasADi) — the derivative substrate
- `src/openflowsheet/compiled.py:163` `class CompiledProblem(Protocol)` with `metadata`, `residual(x, context) -> EvaluationResult` (L168), `jacobian(x, context) -> JacobianResult` (L170), `reconstruct(x, context) -> ProcessState` (L172). Frozen per interfaces-frozen.md §1.
- `compiled.py:61` `class Capabilities` fields: `jacobian: JacobianCapability; jvp; vjp; hessian: CapabilityLevel` (no parameter-derivative field).
- `compiled.py:75` `class CompiledProblemMetadata`: `variable_ids`, `equation_ids`, `parameter_ids` (L~88), `column_scales`, `row_scales`, `row_accumulation`, `capabilities`, `constants_sha256`. Docstring L~84-87: `parameter_ids` and `row_accumulation` added by K01 at schema promotion.
- `compiled.py:39` `class EvaluationContext`: `model_version`, `constants_sha256`, `phase_signature`, `accuracy_policy`, `workspace`. Docstring: time is not a coordinate (ADR 0008 D1); "a `JacobianResult` is valid only for the same context as its residual."
- `compiled.py:123` `class JacobianResult`: sparse CSC `row_ids, col_ids, indptr, indices, data`, `pattern_provenance`, `source_map`.
- `src/openflowsheet/compile/casadi_backend.py:302` `class CasadiCompiledProblem`; `:638` `def compile_problem(spec: ProblemSpec) -> CasadiCompiledProblem`.
- Excerpt (casadi_backend.py:317-334), parameters baked as constants:
  ```
  symbols = {name: ca.MX.sym(name) for name in spec.variable_ids}      # only variables are symbols
  ...
  rows = [equation.build(symbols, outputs, spec.parameters, algebra) ...]  # parameters are plain floats
  self._residual = ca.Function("residual", [argument], [vector])
  self._jacobian = ca.Function("jacobian", [argument], [ca.jacobian(vector, argument)])
  self._jvp = ca.Function("jvp", [argument, seed], [ca.jtimes(vector, argument, seed)])
  self._vjp = ca.Function("vjp", [argument, adjoint], [ca.jtimes(vector, argument, adjoint, True)])
  ```
  So dF/dp is NOT available from the compiled function: `ca.jacobian` is taken w.r.t. variables only.
- L369-371: `hessian="absent"`; `constants_sha256=constants_sha256(spec.parameters, spec.parameter_ids)`.
- L582-600: `def jvp(self, x, seed, context) -> tuple[float,...]` and `def vjp(self, x, adjoint, context)`; exact (ADR 0003 D5.3).
- L602-614: `def hessian(self, x, context) -> None` raises NotImplementedError ("It is not zero; it is unavailable.").
- Block callbacks: `_JacobianCallback` (L150), `_BlockCallback` (L190, `has_jacobian` L230, `get_jacobian` L247). Opaque property blocks; their derivatives come from `PropertyBlock.jacobian()` (compile/spec.py:94).
- `src/openflowsheet/compile/spec.py:123` `class ProblemSpec`: `label, variable_ids, equations, parameter_ids (L140), parameters: Mapping[str,float] (L141), blocks, block_inputs, column_scales, row_scales`. L162 `validate()`: `parameter_ids` must equal `parameters` keys.
- `spec.py:108` `class EquationSpec`: `equation_id, build, accumulation, origin`.
- The only importer of CasADi is casadi_backend.py (its docstring line 1-3 says so, ADR 0003 D5.7).
- Compile call sites: `verify/certificate.py:486,531,616`; `orchestrator/executor.py:806,859,1045`; `orchestrator/tear.py:142`.

### 3b. Existing derivative/sensitivity-adjacent code
- `src/openflowsheet/orchestrator/tear.py:318` `Syn001TearProblem.jacobian(self, t, context=None, flowsheet=None) -> sp.csc_matrix` — "§3.4's Schur complement, with the mandatory consistency check first." Excerpt (tear.py ~L355-371):
  ```
  inner_sensitivity, inner_record = solve_linear(j_phi_u, j_phi_t)   # one factorization, three RHS
  # §3.1's row sign: the tear rows evaluate `−R`, so the derivative of `R` is the negation.
  scaled_derivative = -(j_rho_t - j_rho_u @ inner_sensitivity)
  ```
  This is exactly `dy/du = h_u − h_w g_w⁻¹ g_u` (blueprint §5.1) specialised to the tear. Note `inner_sensitivity` = g_w⁻¹ g_t. The inner-solve sensitivity is not exposed as a public API.
- `tear.py:374` `check_inner_consistency(state, context) -> float` (η ≤ 1e-10, §3.4).
- `tear.py:417` `finite_difference_jacobian(self, t, step=FD_STEP)`: test oracle only; raises at t* (domain boundary).
- `tear.py:446` `as_newton_problem(attempt=None) -> Problem`.
- `tear.py:493` `build_plan(tear, policy) -> SolvePlan`; `tear.py:540` `solve_tear(flowsheet, *, initial_recycle=None, policy=None, trace=None) -> tuple[SolveResult, Trace]`.
- `src/openflowsheet/numerics/linear.py:127` `solve_linear(matrix, rhs) -> tuple[ndarray, LinearSolveRecord]`; `:149` `class KeptFactorization`; `:172` `solve_linear_kept(...)`; `:102` `class StructurallySingularError(RuntimeError)`; `:50` `class LinearSolveFailedError` (reason e.g. "exactly_singular", tests/test_k03_linear.py:128).
- `src/openflowsheet/numerics/newton.py:244` `solve_newton(problem, x0, policy, *, trace, signature=(), attempt=0, counters=None) -> NewtonResult`; `:209` `class Problem` (variable_ids, row_ids, residual, jacobian); `:110` `JacobianUnavailableError`.
- Unit-model sensitivity notes (all declare the derivative unavailable, none expose dR/dp):
  - `models/syn001/mixer.py:~200` `_SENSITIVITY_NOTE`: "its sensitivity would need the implicit-function route of blueprint §5.1. K02 exposes no such interface, so this stays `unavailable` ... (blueprint §5.2)."
  - `models/syn001/splitter.py:~115`: "The relation is linear and its derivative is r, but K02 exposes no sensitivity interface ... so this stays `unavailable`."
  - `models/syn001/ph_flash.py:~210`: sensitivity runs through the PH closure; "dT/dH* changes slope at every phase boundary; no interface supplies it".
  - `component_separator.py:186`, `heat_exchanger.py:229`, `kinetic_cstr.py:210` (multiple steady states; no unique causal sensitivity), `heater.py:181`, `flash.py:192`, `feed.py:103`, `pump.py:150`, `valve.py:137`, `conversion_reactor.py:246`: same pattern.
- Nothing in src matches sensitivity, dR/dp, adjoint, sweep, Study, OptimizationReport, ExperimentRequest, estimation, identifiab*, covariance, cyipopt, ipopt, pyomo, nlpsol, trust-region.
  - Exception: `observation|estimat` hits in application/jobs/interrupt.py, orchestrator/execution.py, homotopy.py, application/jobs/executor.py, tear.py are incidental wording, not estimation code.
  - `sweep` hits: merge.py:11 (comment "no damping sweep"), benchmarks/t08/v19/c1_reactor_run.py (external reactor GHSV sweep). No study runner.
- Closest existing "many-run" machinery: sampling ensemble `benchmarks/t06/ensemble.py`, `benchmarks/t06/generator.py` (20x20 registered ensemble), `tests/t06_ensemble_support.py`. Not a Study type.

### 3c. Parameters vs states in the canonical model
- Unknowns = `variable_ids` (the state x, solved by Newton). Pinned inputs = `parameters` / `parameter_ids` (spec.py:140-141), identified at the boundary by `(model_version, constants_sha256)` (ADR 0008 D4.1, compiled.py:85-87).
- Specification rows are promoted to residual rows with the pinned value as parameter. `application/binding.py:204-214`:
  ```
  def _promotion_row(column, parameter):
      def build(variables, blocks, parameters, algebra):
          return variables[column] - parameters[parameter]
  ```
  Promotion happens at binding.py ~L775-800 (`parameter = f"{_SPEC_ROW_PREFIX}{name}"`, `parameter_ids.append(parameter)`, `parameters[parameter] = values[name]`). A specification value is therefore a parameter, and it becomes a row when fixed.
- Continuation (T04/ADR 0010 D2) re-binds these pinned inputs: `orchestrator/homotopy.py:74` `continuation_parameter(...)` (requires row of form `v − p`), `:106` `level_values(...)`, `:128` `rebind(spec, values)` ("replaced **by id**, nothing else"). Continuation requires the spec row to be `v − p`; this is the existing precedent for "a parameter" in code.
- Unit parameters (names as keys in `parameter_ids`): `splitter.split_fraction` (splitter.py), `parameters.conversion`, `parameters.nu` (conversion_reactor.py), `parameters.damkohler`, `parameters.coolant_flow`, `parameters.coolant_cp`, `parameters.coolant_temperature`, `parameters.reference_temperature`, `parameters.temperature_scale`, `parameters.pressure_drop` (kinetic_cstr.py ~L580-595), `parameters.pressure_drop` (heater, flash, mixer), `duty_parameter` (ph_flash.py:500).
- Consequence for the specifier: a "parameter" for estimation/sensitivity would be one of these pinned inputs. The compiled function already takes them as floats, so any `dF/dp` would need a new symbolic route (CasADi symbols for parameters, or a finite-difference path that the plan demotes to test oracle). Neither exists.

### 3d. Regularity screen (K04, [A08])
- `src/openflowsheet/verify/regularity.py` (module docstring L1-~70: "The [A08] regularity screen and the solution-error bound. K04 §7.").
- Constants: `TAU_ILL = 1e-8` (L~58), `SVD_DIMENSION_CAP = 2000` (L~60), `TAU_SCALED_MIN = 1e-8`, `ONENORMEST_SEED`.
- `:75` `inverse_one_norm_estimate(operator) -> float`; `:92` `absolute_conditioning_threshold(...)`; `:103` `class RegularityEvidence` (matrix, dimension, nnz, scales_provenance, one_norm, status, rcond_1, escalation, inconclusive_reason).
- `:156` `def screen(matrix, *, scales_provenance=..., jacobian_identity=None, target_identity=None, scaled_residual=None, tau_scaled_min=TAU_SCALED_MIN) -> RegularityEvidence`. Input is a matrix (not a factorization, §7.5). Refuses on identity mismatch (R-084).
- `:322` `solution_error_bound(matrix, residual)` -> None when singular (test_k04_regularity.py:~160).
- `:348` `target_jacobian(tear, state, zero_flow=()) -> (csc, scaled residual, identity)`; `:375` `assemble_target(...)`.
- Status vocabulary: `verify/__init__.py:42` `RegularityStatus = Literal["NO_RANK_LOSS_DETECTED","RANK_DEFICIENT","ILL_CONDITIONED","INCONCLUSIVE"]`; `:41` `VerificationStatus = Literal["VERIFIED","RELAXED","UNVERIFIED","FAILED"]`.
- Call sites: `verify/certificate.py:1025` `regularity = screen(...)`; `_screen` at certificate.py:678, :962.
- Rule (blueprint §8.1 L374): default closed-simulation policy: no unresolved regularity warning for unqualified VERIFIED; a study may request residual-only evidence but may not relabel it as regularity or sensitivity evidence.
- The screen applies to the square SIMULATION Jacobian (47x47 after alias elimination). Optimization is explicitly NOT to use this test on free decision variables (blueprint L374). The screen has no concept of KKT/constraint Jacobian.

### 3e. Certificates and statuses
- `verify/certificate.py:77` `REGISTERED_POLICY_ID = "K04-check-policy-v1"`; `:81` `class CheckPolicy`; `:127` `class CheckReport`; `:315` `class SolutionCertificate`; `:804` `class BoundDeclaration`.
- Schema: `schemas/solution-certificate.schema.json`, `schemas/regularity-evidence.schema.json`.
- No OptimizationReport certificate/status type exists; blueprint L366 wants it separate.

### 3f. Homotopy / continuation (T04)
- `orchestrator/homotopy.py:61` `class Continuation` (type "specification_continuation", parameter_ids, variable_ids; `as_context()` L69).
- `:141` `CorrectorOutcome`, `:151` `HomotopyTrial`, `:162` `HomotopyRecord`, `:222` `continue_specification(*, correct, x0, continuation, policy, trace, attempt, signature, variable_ids, counters) -> tuple[NewtonResult, HomotopyRecord]`.
- Governed by ADR 0010 D2-D3 and R-030 (line 1034 of decision-register.md).
- PTC: `src/openflowsheet/numerics/ptc.py` (759 lines), experimental per ADR 0010 D5.
- Globalization policy: `SolvePolicy.globalization` (ADR 0010 D1).

### 3g. Other
- `numerics/scaling.py` (REGISTERED_NOMINALS; row/column scales used by Jacobian scaling in tear.py L~330-345).
- `numerics/anderson.py` (507 lines) acceleration.
- `orchestrator/rank.py:141` `eliminate_alias_rows(...)`, `:46` `SpecificationConflictError`, `:55` `UnsupportedRankStructureError`.
- `orchestrator/roots.py` root fingerprint/branch comparison (`:54 branch_found`, `:77 root_fingerprint`).

## 4. Dependencies and environment

- `requirements.lock`: `casadi==3.8.0` (L8), `numpy==2.2.4` (L25), `scipy==1.15.3` (L40). grep for ipopt/cyipopt/pyomo/nlpsol: no matches.
- `pyproject.toml:18-28` `dependencies` = numpy 2.2.4, scipy 1.15.3, casadi 3.8.0 (L28; comment L25-27 re ADR 0006 D5.4 audit refresh).
- `pyproject.toml:31-37` `[project.optional-dependencies] dev = [pytest 8.3.5, mypy 1.15.0, ruff 0.12.11, types-*, mpmath 1.3.0]`. `:40` comment: the HTTP and MCP bindings' libraries are optional extras. No `optim`/`ipopt`/`nlp` extra exists.
- Venv `.venv` (site-packages):
  - casadi 3.8.0 present. `casadi.has_nlpsol('ipopt')` returned **True** (read-only import check). `has_conic('qpoases')` True.
  - Bundled libs present in casadi/: `libcasadi_nlpsol_ipopt.so(.3.7)`, `libipopt.so.3.14.19`, `libcoinmumps.so.3.0.12`, `libcoinmetis.so.2.0.0`, `libsipopt.so.3.14.19`, `libcasadi_linsol_mumps.so`.
  - `import cyipopt` -> ModuleNotFoundError. `import pyomo` -> ModuleNotFoundError. No pynumero.
- ADR 0006 D2.4 (`docs/adr/0006-distribution-data-rights.md:54`): "M03 must not use CasADi's bundled `nlpsol:ipopt` (Q3 of ADR 0003) and, if it needs Ipopt, obtains it from a separately distributed package whose own [A10] audit is run first." Also L118: "M03 obtains Ipopt, if it needs it, from a separately distributed package with its own audit, not from the CasADi wheel." Also ADR 0006 notes METIS-4 use restriction (D1.5 L35) that affects bundled ipopt/mumps.
- ADR 0003 Q3 (`docs/adr/0003-compiled-problem-backend.md:170`): "Is the M03 NLP adapter allowed to use CasADi's bundled `nlpsol:ipopt`? ... No: it enters the METIS closure (ADR 0006 D2). Use a separately distributed Ipopt (cyipopt, as the plan names) and refresh the audit for *that* distribution when M03 starts."
- ADR 0003 D5.4 (L122): second order through opaque callbacks is absent; "M03's Hessian policy is written against the negotiated capability rather than against an assumption."
- ADR 0003 T5 (L180): trigger for revisiting: a second-order requirement M03 cannot meet on CasADi.
- Consequence: a cyipopt install is NOT in lock or venv. Adding it needs a new pin and an [A10] audit of its wheel/binaries (plan A10 L101 names cyipopt explicitly). Not done.

## 5. ADRs and decision-register entries

ADRs (`docs/adr/`): 0001 state/units/zero-flow; 0002 canonicalization & schemas; 0003 CasADi backend; 0004 SuperLU options; 0005 phase-attempt contract; 0006 distribution/data rights; 0007 reproducibility/certificate policy; 0008 transient extension readiness; 0009 execution plan & recycle trace; 0010 globalization/homotopy/PTC; 0011 unit models PH closure; 0012 saturation band; 0013 K04 fresh flash; 0014 T06 corpus; 0015 edge3 sequential restart; 0016 unit conversion v2. **No ADR mentions M03 by name except 0003 (Q3, D5.4, affected packages) and 0006 (D2.4, affected packages, M03 Ipopt).** No ADR on sensitivities, adjoints, optimization, or Hessian policy. Anything M03 decides about optimization needs a new ADR (CLAUDE.md "departure from the blueprint or plan requires an ADR").

Decision register (`docs/decision-register.md`):
- R-003 (L70) CasADi 3.8.0 backend. Affected: K01, K02, K03, K05, M03, T08. Rejected: Pyomo/PyNumero/ASL (installability, 2.5x slower per Newton iteration at boundary, etc.). Watch-for L103-105: reviving Pyomo as "fallback" needs a new ADR naming triggers T1-T5.
- R-010 (L416) K03 tear Newton on 3-var tear residual; dR/dt by exact block elimination; FD is test oracle only. Rejected: lifted 47-var Newton; FD of traversal.
- R-016 (L536) certificate verifier shares nothing with solver; 47x47 target Jacobian.
- R-030 (L1034) typed homotopy = specification continuation via re-bound pinned inputs.
- R-084 (L2127) regularity screen refuses matrix with wrong identity.
- R-120 (L2863) v0.2 real chemistry: ammonia loop (C1) on group's PyMRM model, runner-up methanol; pending Frank, decided 2026-09-29.
- R-129 (L3027) `validate(task="optimization")` returns typed `unsupported`; `READY_FOR_OPTIMIZATION` is never returned. Watch-for: "a new operation returning it without an optimizer behind it." Directly relevant to D16/M03.
- R-153 (L3548) v0.2 order: M01 design first, M06 alongside, M03 "when the critical path allows"; `0.2.0a1` after M02 tested.
- Register index table rows (~L664-676): R-A03 backend, R-A04 SuperLU, etc.
- The register has no entry on Hessian policy, sensitivity method, estimation, or optimizer choice. These are open.

## 6. Test patterns for derivative verification

- K03 tear derivative — `tests/test_k03_tear.py`:
  - L152 `test_the_schur_complement_matches_a_finite_difference_of_the_traversal`: central FD of traversal at OFF_A, `< 1e-9`. (Oracle route independent of assembled Jacobian.)
  - L165 `test_the_finite_difference_oracle_refuses_at_the_solution`.
  - L180 `test_the_derivative_satisfies_the_affine_ray_identity`: `J t* = −(1−r) t*` for SYN-001-nominal and SYN-001-high-recycle, `< 1e-12`. Module docstring L6-9: three checks, closed form (mpmath 40 digits), FD, affine-ray.
  - Closed form reference values from `benchmarks/k03/reference_values.yaml`.
  - Consistency check test near L~200.
- Affine-ray metamorphic relation: `tests/test_k02_flowsheet.py:288` `test_the_tear_map_is_exactly_affine_along_the_ray_through_its_fixed_point`; `tests/test_t02_recycle.py:499`.
- K01 JVP/VJP — `tests/test_k01_compiler.py`:
  - L235 section header "D5.3 JVP and VJP are exact".
  - L241 `test_jvp_is_exact_against_a_fourth_order_finite_difference` (seeds e1, e2, (1,-2); 4th-order central FD, step 1e-5, abs 1e-7). Independent expectation, not the oracle.
  - L254 `test_vjp_is_the_transpose_of_the_assembled_jacobian` (dense.T @ adjoint).
  - L547 `test_vjp_is_the_transpose_on_a_non_symmetric_jacobian`; L568 also checks jvp = dense @ adjoint.
  - L267 `test_the_hessian_is_reported_absent_and_raises_rather_than_returning_zeros` (capabilities.hessian == "absent"; calling hessian raises).
  - L161 CSC ordering; L174 permuted-reading detection.
  - L289 comment: "a value call per input plus one is what a finite-difference fallback looks like" (a call-count guard against silent FD fallback).
  - `tests/test_k01_syn001_conformance.py:255` asserts `(jvp, vjp) == ("exact","exact")`.
- Directional identity from blueprint §5.2 (vᵀ(Ju) = (Jᵀv)ᵀu): covered by test_k01_compiler.py:254-261 pattern (VJP vs dense transpose). No dedicated test of the scalar identity itself found.
- Parameter derivative tests: none exist (no dR/dp).
- Singular-state refusal tests:
  - `tests/test_k04_regularity.py:152` `test_a24_an_exactly_singular_matrix_is_rank_deficient_not_a_crash` (x²=0: RANK_DEFICIENT, rank 0; `solution_error_bound` is None). Fixture: `benchmarks/k04/reference_values.yaml:369-375` (`x_squared.exact_root`).
  - `tests/test_k04_regularity.py:~140` `test_a26_a_matrix_too_large_to_decide_says_so` (INCONCLUSIVE svd_budget).
  - `tests/test_k04_regularity.py:338` `test_a_structurally_singular_matrix_never_reaches_superlu`.
  - `tests/test_k04_regularity.py:~170` A25 bound recorded; VERIFIED at tau 1e-8, UNVERIFIED at tau 1e-12 (docstring L~170-220).
  - `tests/test_k03_linear.py:128` `test_an_exactly_singular_matrix_is_a_typed_failure` (NUM-02 at r=1; LinearSolveFailedError reason "exactly_singular").
  - `tests/test_t05_factorize_guard.py:48`; `tests/test_t04_review.py:255`; `tests/test_k03_newton.py:122` `test_num02_at_r_one_is_a_typed_singular_failure`.
  - Also x²=0 seed in K03 Newton (`tests/test_k04_regularity.py` docstring L12-19).
- Gray-box/Pyomo composition: spikes only (no tests in tests/). `spikes/p02/casadi/{harness.py,memory_probe.py,run.sh}`, `spikes/p02/pyomo/{harness.py,run.sh}`, `spikes/p02/results`, `spikes/p03/results`. Not run by the default test suite.
- Test run: `make check` -> `scripts/check.sh` (ruff check, ruff format --check, mypy (pyproject `files`), pytest -q). Makefile L2-3 `VENV := .venv`. pytest config `pyproject.toml:105-109`: testpaths=["tests"], pythonpath=["."]. Individual: `.venv/bin/pytest -q tests/test_k03_tear.py`.

## 7. Benchmarks that could host a small parameter-estimation example

### SYN-001 (synthetic ideal flash-recycle; algebraic reference)
- Registry: `benchmarks/registry.yaml:23` (SYN-001), `:88` (SYN-001-UL), `:148` (SYN-001-T06). Components `benchmarks/syn001/components.yaml` (A, B, C). Oracle `benchmarks/syn001/oracle.py` (`recycle_oracle`). Reference values `benchmarks/syn001/reference_values.yaml` (20-digit, generated by `docs/derivations/scripts/syn001_reference.py`; not from oracle, per registry note).
- Cases: `benchmarks/syn001/cases/`: SYN-001-nominal.yaml, -high-recycle, -once-through, -all-liquid-310K, -all-vapor-420K, -conflicting-heater-spec, SYN-001-A02-340..365 (guess variants).
- SYN-001-nominal.yaml pinned values (verified):
  - Instances and parameters: `splitter.split_fraction = 0.5` (L126-127); mixer/heater/flash `pressure_drop = 0.0 Pa`.
  - Specifications (fixed): SPEC-feed-n-A/B/C = 1.0 mol/s (feed component flows); SPEC-feed-T = 300.0 K; SPEC-feed-P = 100000 Pa; SPEC-heater-outlet-T = 350.0 K (S3); SPEC-flash-T = 360.0 K (object flash, L353); SPEC-flash-P = 100000 Pa (L367); SPEC-splitter-r = 0.5 (path parameters.split_fraction; "Must equal the splitter instance's split_fraction").
  - Feed T = reference T (zero fresh-feed enthalpy flow).
- Natural estimation candidates in SYN-001: the recycle split `r` (sole "free" parameter of the tear; blueprint §3 and K03 derivation: `J t* = −(1−r) t*`), the flash temperature, the heater outlet temperature. Caveat: a flash-recycle reduces to a single flash (recycle_case_group_note in registry L~30-35); parameter identifiability for r may be degenerate in SYN-001 with ideal VLE only. Specifier must judge; I am not assessing this.
- The reference values are algebraic; there is no experimental data in repo for SYN-001 (no measured observations).

### T0x / C0 / C1 cases
- `benchmarks/t05/cases/`: SYN-001-UL-C1.yaml (pressure chain: pump, heater, valve, PH flash; acyclic), SYN-001-UL-C2, SYN-001-UL-C3, SYN-001-UL-C3X. Parameters include pump/valve/heater pressures and duties (names in models/syn001/pump.py, valve.py, ph_flash.py `duty_parameter`, `pressure_drop`).
- `benchmarks/t06/cases/`: 23 cases, e.g. `SYN-001-T06-NET02.yaml`, `NET03`, `NET06`, `NET09`, `NET10` (network/corpus cases; ensemble generator `benchmarks/t06/generator.py`, `ensemble.py`; 20x20 registered ensemble per registry/ADR 0014).
- `benchmarks/t08/`: `ptc_r1/case.json` (PTC case), `v19/` (C1 ammonia loop evidence: `c1-reactor.json`, `c1-idaes.json`, `c1-provenance.json`, runner scripts `c1_reactor_run.py`, `c1_idaes_loop.py`). The C1 reactor is the group's external `ammonia_synthesis_reactor` (PyMRM), run in a separate venv, NOT importable from this repo (c1_reactor_run.py docstring). Its rate-law parameters live in `c1-provenance.json` (not read in detail). The in-repo C1 model is not yet a CompiledProblem; ADR 0022 is Proposed (R-145).
- v0.2 chemistry dossier: `docs/v02-real-chemistry-dossier.md` (C1 ammonia; reactor pin `6089593`, MIT; R-120/R-143/R-152: K_NH3 enthalpy term 7000 cal/mol decided by Frank).
- Kinetic CSTR in `src/openflowsheet/models/syn001/kinetic_cstr.py` (703 lines): pinned params `damkohler`, coolant params, `reference_temperature`, `temperature_scale`; has multiple steady states (L~210 note: no unique causal sensitivity). Conversion reactor `conversion_reactor.py`: params `conversion`, `nu`, `pressure_drop`. Not a benchmark case per se but a unit model usable in a custom spec.

## 8. Guidance documents governing M03

- `CLAUDE.md` (repo rules): design lane vs build lane; "If a task has no test that would catch its failure, it is a design-lane task"; blueprint is authority; departures need ADR; "Never set `reviewed` on your own package"; no placeholder success paths; "Residual and Jacobian paths must describe the same function at the same state."; "Distinguish `implemented`, `tested`, `reviewed`, and `released`."; "Self-generated outputs are regression fixtures, not validation."
- `docs/implementation-plan.md` §1.3 (lanes), §4.4 M03 row L265, W24 L353, D16 L311, A06 L321, plan L271 two-adapter rule.
- `docs/progress.md`, `docs/V02_STATE.md` (M03 "not started" L20; R-153 order L10), `docs/V02_DECISIONS.md`.
- `docs/interfaces-frozen.md` §1 (CompiledProblem frozen; changes need Fable ADR).
- `docs/requirements.yaml` (entries in §1c).
- Blueprint §10 (L429-447) is the primary normative text for M03.

## 9. Not found (explicitly)

Looked for and did not find:
- Any sensitivity, `dR/dp`, `dF/dp`, parametric derivative, adjoint (beyond VJP), implicit-function sensitivity code in `src/`, `benchmarks/`, `tests/`, `spikes/`.
- Any sweep runner, Study or experiment type, `ExperimentRequest`, `ExperimentResult`, `ModelEvidence`, `Study`, `SurrogateManifest`, `OptimizationReport` (named in plan/interfaces-frozen/schemas README only; no schema file in `schemas/`, no class in `src/`).
- Parameter estimation, observation/covariance, identifiability, parameter bounds (only blueprint prose).
- Any NLP solver adapter, `nlpsol` use, `cyipopt`, `pyomo`, `pynumero`, `ExternalGreyBoxModel`, `ExternalFunction`, trust-region framework use, filter, multistart.
- Hessian implementation of any kind (only the absent-raising stub at casadi_backend.py:602).
- Any ADR about optimization, sensitivities, Hessian policy, estimation, or identifiability (ADR list in §5).
- Decision-register entry on Hessian approximation, optimizer choice, sensitivity method, or identifiability.
- `ipopt`/`cyipopt`/`pyomo` in requirements.lock, pyproject dependencies, or the venv (cyipopt and pyomo not importable).
- Existing tests on optimization, sensitivities (beyond K03 tear and K01 JVP/VJP), identifiability, or sweeps.
- A `tests/test_m03*` or `tests/test_*optim*` file: none.
- `docs/derivations/M03*` or `docs/briefs/M03*`: none (only M01-*, M06-* exist in derivations/briefs).
- Measured or observed experimental data for SYN-001 or C1 usable for estimation in-repo (C1 external; SYN-001 reference is algebraic).

Not judged (per scout rules, left to specifier/architect): whether SYN-001 r is identifiable, whether a reduced-space vs full-space formulation is preferable, whether a finite-difference Hessian approximation is acceptable under A06, whether the tear's Schur derivative extends to parameter columns, and whether an IPOPT audit is needed before adding cyipopt.
