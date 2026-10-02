# Agent-Native Open Process Simulator

**Technical blueprint for a transparent, multi-fidelity process-engineering platform with an original solver-orchestration core**

> **Implementation-agent directive:** Treat this document as the architectural design baseline. Derive an executable implementation plan, ADRs, package boundaries, milestones, and traceable tests from it. Preserve the stated invariants and acceptance criteria unless a proposed ADR explicitly documents evidence, trade-offs, and migration impact.

**Version:** 1.0  
**Date:** 29 August 2026  
**Status:** Design baseline  
**Audience:** Technical founder, numerical-methods lead, process-modeling lead, and high-end coding agent

---

## Document contract

This blueprint fixes the architectural invariants, interfaces, numerical behavior, quality gates, and release outcomes. It deliberately does not prescribe every library or class. A coding agent should derive an implementation plan, architecture decision records (ADRs), work packages, dependency graph, and estimates without reopening the core design.

> **Product thesis** — Do not build an open clone of Aspen. Build an open scientific runtime in which the process, equations, solution strategy, data lineage, and model-fidelity decisions are explicit machine-readable objects shared by humans and agents.

### Executive decisions

| Decision | Blueprint commitment |
| --- | --- |
| Canonical object | A versioned Process IR, independent of GUI, solver backend, and agent transport. |
| Numerical core | Original orchestration, structural analysis, initialization, scaling, continuation, fallback, diagnostics, and sparse nonlinear runtime; third-party linear algebra is allowed behind stable interfaces. |
| Model composition | Typed contracts support native equations, first-principles modules, reduced-order models, surrogates, FMUs, and external high-fidelity services. |
| Thermodynamics | Pluggable property-service boundary; validate and integrate open implementations before attempting broad proprietary-grade coverage. |
| Clients | Headless Python/HTTP/CLI and agent tools first; web GUI is another client of the same transactional API. |
| Quality | Deterministic fixtures, property-based tests, Jacobian checks, solver traces, cross-simulator benchmarks, and reproducible validation reports are release gates. |

## 1. Mission, scope, and non-goals

### 1.1 Mission

Create an open, agent-native process-engineering platform for autonomous multi-fidelity process design. Every component can be represented by interchangeable first-principles, reduced-order, surrogate, or external high-fidelity models. Humans and agents operate on the same transparent representation and receive the same validation, diagnostics, provenance, and permissions.

### 1.2 Primary user journeys

- A process engineer builds or imports a steady-state flowsheet, inspects degrees of freedom, solves it, and understands why the chosen numerical path succeeded or failed.

- A coding agent creates a process transactionally, changes topology or specifications, runs validation, solves, compares branches, and produces an auditable engineering report.

- A researcher replaces a simple reactor with a PyMRM model, samples it, trains a surrogate with a validity envelope, reinserts it, and quantifies whether the process decision changes.

- A design agent explores flowsheet alternatives, performs continuous and discrete optimization, and escalates model fidelity only where expected decision value justifies cost.

- An educator exposes equations, units, residuals, scaling, initialization, and solver decisions rather than presenting a black-box convergence indicator.

### 1.3 In scope

- Steady-state material and energy balances; vapor/liquid phase equilibrium; core unit operations; recycles and design specifications.

- Transparent Process IR, schema migration, validation, diffing, provenance, scenario branches, and deterministic run manifests.

- Hybrid sequential-modular/equation-oriented solution orchestrated from graph and equation structure.

- Pluggable thermodynamics, model adapters, derivatives, uncertainty metadata, validity domains, and multi-fidelity replacement.

- Parameter estimation, sensitivity, optimization, early process synthesis, TEA hooks, and external assessment adapters.

- Typed agent tools, Python SDK, service API, CLI, event stream, and a diagnostic web interface.

### 1.4 Explicit non-goals

- Matching Aspen's component databank, refinery, polymer, solids, electrolyte, safety, and regulatory breadth in early releases.

- Claiming universal convergence or numerical superiority. The measurable promise is transparent strategy selection, robust benchmark performance, and actionable failure diagnosis.

- Making an LLM part of the trusted numerical path. Agents propose actions; deterministic validators and runtimes authorize and execute them.

- Building dynamics, control, online digital twins, full P&ID authoring, or plant operations into v1.

- Writing BLAS, sparse direct linear solvers, or automatic differentiation from scratch. These are dependencies behind replaceable interfaces; orchestration and process-specific numerics remain original.

- Embedding high-fidelity PDE/CFD solves directly inside every nonlinear iteration by default.

## 2. Design principles and invariants

| Principle | Required consequence |
| --- | --- |
| Transparency by construction | Equations, variables, residuals, units, scaling, sparsity, decomposition, iterations, events, and fallbacks are inspectable and serializable. |
| One semantic truth | The Process IR is authoritative. GUI diagrams, code, reports, and solver models are projections or compiled artifacts. |
| Typed contracts | Every model declares ports, quantities, equations/evaluator, derivative capabilities, initialization, validity, fidelity, uncertainty, cost, and provenance. |
| Separate semantics from execution | A model says what it means; adapters and compiler layers say how it runs. |
| Transactions before mutation | All agent and UI changes are proposed, validated, previewed, committed or rolled back, and attributed. |
| Determinism where appropriate | Canonical serialization, graph analysis, compilation, default strategy choice, and seeded tests must reproduce. Parallel floating-point reductions are documented when bitwise reproducibility is impossible. |
| No silent repair | Clipping, extrapolation, relaxed tolerances, substituted properties, and fallback strategies emit structured events. |
| Physics before convenience | Units, conservation, bounds, phase semantics, and thermodynamic compatibility are enforced at model boundaries. |
| Failure is a product output | Unsuccessful solves return a diagnosis bundle, not only an exception string. |
| Progressive fidelity | Cheap models screen designs; higher fidelity is introduced based on sensitivity, uncertainty, and decision value. |

## 3. System architecture

The platform is organized as a strict dependency stack. Higher layers may call lower layers; the numerical core must never depend on the web GUI, agent framework, or a specific model provider.

| Layer | Responsibilities | Key outputs |
| --- | --- | --- |
| Process IR & schema | Semantic graph, quantities, equations, specs, objectives, model identities, provenance | Canonical document, validation report, semantic diff |
| Model registry/contracts | Versioned models and adapters; capabilities, validity, uncertainty, cost | Resolved model graph, compatibility report |
| Thermodynamics | Property packages, flash calls, derivatives, reference states, phase policy | Typed property results and diagnostics |
| Compiler & structural analysis | Flattening, unit normalization, incidence graph, DOF, SCC/BTF, tearing candidates, sparsity | Executable problem graph and solve plan candidates |
| Numerical runtime | Initialization, SM execution, EO blocks, scaling, homotopy, fallbacks, checkpointing | Solution, trace, residual/Jacobian diagnostics |
| Study runtime | Sensitivity, estimation, UQ, optimization, topology search, fidelity scheduling | Versioned study results |
| Application services | Transactions, jobs, caching, artifacts, auth/policy, collaboration | Stable API and event stream |
| Clients | Python SDK, CLI, MCP-compatible tools, web GUI | Human and agent workflows |

### 3.1 Required boundaries

- IR packages contain no solver objects or UI coordinates in semantic nodes; optional layout is a separate projection.

- Unit models cannot reach global mutable state. They receive typed evaluation contexts and property-service handles.

- Thermodynamic packages cannot mutate process variables or choose global solve strategy.

- External models execute through sandboxed adapters with declared timeout, retry, cache, derivative, and provenance behavior.

- Optimization operates on compiled differentiable problems when possible and uses declared derivative limitations when not.

- Every run pins schema, model, property-package, solver-policy, dependency, and platform versions.

## 4. Process IR

### 4.1 Semantic object model

| Object | Minimum fields |
| --- | --- |
| Process | id, name, schema_version, component_set, graph, specs, objectives, scenarios, provenance |
| ModelInstance | model_ref, semantic_role, parameters, variable bindings, fidelity, validity policy, annotations |
| Port | kind, direction, phase capability, quantity schema, conservation basis, causality hints |
| Stream | source/target port, material/energy/signal type, state definition, composition basis, tear metadata |
| Quantity | stable id, meaning, unit dimension, display unit, value/state, bounds, nominal, scale, uncertainty |
| Equation | stable id, residual form, dependencies, differentiability, priority, source, active conditions |
| Specification | target variable/equation, fixed/free state, tolerance, rationale, owner |
| Objective/constraint | expression, sense, weight, bounds, scenario scope |
| ProvenanceRecord | actor, timestamp, parent revision, operation, source references, hashes, environment |

### 4.2 Validation pipeline

- Schema validation: required fields, enum values, identity uniqueness, and migration compatibility.

- Dimensional validation: every equation and connection is dimensionally consistent; conversions are explicit compiled nodes.

- Graph validation: port direction, multiplicity, required connectivity, allowed signal/material/energy edges, and component-set compatibility.

- Physical validation: normalized compositions, nonnegative phase fractions, admissible states, conservation metadata, and model validity domains.

- Structural validation: equation/variable counts, fixed-variable conflicts, unmatched equations/variables, rank-risk indicators, and active conditional structure.

- Capability validation: property methods and derivatives required by each model are available.

- Execution validation: external artifacts exist, hashes match, secrets are referenced rather than serialized, and sandbox policies are satisfiable.

### 4.3 Serialization and versioning

Use a canonical human-readable YAML or JSON surface backed by a normative JSON Schema. Define canonical JSON for hashing: sorted keys, normalized numeric representation, explicit units, stable IDs, and no transient runtime fields. Large arrays and model binaries are content-addressed artifacts referenced by URI and cryptographic hash. Every schema release includes forward migrations, golden fixtures, and round-trip tests; no in-place ambiguous migration is allowed.

- Separate files: process.yaml, layout.json, study.yaml, model-lock.json, run-manifest.json, results/ and artifacts/.

- Semantic diff reports added/removed units, rewired streams, changed specs/parameters/models, and downstream invalidations.

- Branching is copy-on-write over immutable revisions. Runs point to a revision and never overwrite prior results.

- Import/export adapters are lossy only with an explicit capability report. Target DEXPI/SFILES/FMI/CAPE-OPEN adapters opportunistically, without weakening the IR.

## 5. Typed model, stream, and unit APIs

### 5.1 Model contract

A model package exposes a manifest plus executable implementations. The manifest is inspectable without importing arbitrary code.

| Contract area | Required declarations |
| --- | --- |
| Identity | name, semantic type, version, license, implementation hash, authorship, citations |
| Interface | typed ports, input/output quantities, dimensions, optionality, multiplicity, component/phase assumptions |
| Mathematics | variables, residual equations or evaluator, events/conditions, algebraic/dynamic classification |
| Derivatives | analytic/AD/finite-difference availability; Jacobian/JVP/VJP; sparsity; smoothness class |
| Initialization | defaults, state estimators, staged activation recipe, required upstream information |
| Validity | hard domain, soft training envelope, extrapolation behavior, failure policy |
| Numerics | nominals, scaling hints, bounds, expected stiffness, preferred decomposition, solver capabilities |
| Fidelity & cost | fidelity level, expected runtime/memory, batching, parallelism, cacheability |
| Uncertainty | parameter distributions, predictive uncertainty, correlation identifiers, calibration provenance |
| Execution | native, Python/C++ plugin, ONNX, FMU, container, remote service; timeout and reproducibility class |

### 5.2 Core protocol

Conceptual interface (language-neutral): describe(context) → ModelManifest; instantiate(bindings) → ModelInstance; residual(x, context) → ResidualResult; evaluate(inputs, context) → OutputResult for explicit models; jacobian/JVP/VJP where declared; initialize(knowns, context) → InitialGuess; validate(state, context) → ValidationReport; estimate_cost(domain) → CostModel. No model may silently change topology, units, or global tolerances.

### 5.3 Streams

- MaterialStream carries total flow, thermodynamic state, composition, phase policy, component set, and optional phase-resolved state; intensive/extensive distinctions are explicit.

- EnergyStream carries signed duty/power with a declared convention. SignalStream carries nonconserved specifications or controls.

- A stream state is not a bag of properties. It references a state definition (for example T-P-z, P-H-z, or phase-resolved) and property package.

- Connections compile to equality/transform equations and component mappings. Implicit component dropping is forbidden.

### 5.4 v0.1 unit library

| Family | Models | Minimum behavior |
| --- | --- | --- |
| Network | feed, product, mixer, splitter, recycle/tear | mass/energy continuity, composition mapping |
| Pressure | pump, valve | pressure change, duty, efficiency, phase checks |
| Thermal | heater/cooler, two-stream heat exchanger | duty/outlet specs; UA or effectiveness option |
| Phase | equilibrium flash | TP, PH, and selected vapor-fraction specifications |
| Reaction | stoichiometric/conversion reactor, equilibrium reactor | element balance, heat effects, extent/conversion semantics |
| Separation | component separator | split specifications and conservation |

### 5.5 Model replacement

Replacement is allowed when semantic roles and port contracts match, or a declared adapter can prove a mapping. The system compares conserved quantities, thermodynamic requirements, state variables, validity domains, and uncertainty. Replacement creates a new process revision, invalidates dependent results, and optionally initializes the new model from the previous solution.

## 6. Thermodynamics strategy

### 6.1 Architectural position

Thermodynamics is a pluggable, versioned scientific subsystem with a narrow typed interface. The project should not delay its numerical and agent architecture while attempting to reproduce decades of commercial data. Early releases combine a small rigorously validated native ideal package with adapters to mature open implementations.

### 6.2 Property-package contract

- component registry and identifiers; molecular data provenance; supported phases and state regions; reference-state convention; mixing rules and binary parameters; property/flash capabilities; derivatives and smoothness; uncertainty; licensing; thread/process safety.

- Pure and mixture properties: enthalpy, entropy, density, heat capacity, viscosity and thermal conductivity as capability-dependent calls.

- Flash surface: TP, PH, PS, TV, PV, and quality specifications as supported; return phases, compositions, properties, convergence metadata, and stability indicators.

- Batch evaluation and derivative calls are mandatory performance design points, even if initial implementations are scalar.

- Near-critical, phase-appearance, nonphysical input, and flash nonconvergence are typed outcomes, never NaNs without context.

### 6.3 Delivery sequence

- Native ideal-gas/ideal-liquid and Raoult-law package with analytic derivatives for solver development.

- Adapter to one permissively licensed open property library for pure-fluid and common mixture properties; pin versions and build conformance tests.

- Adapter to DWSIM-compatible or CAPE-OPEN property packages where deployment permits; run out-of-process when isolation is needed.

- Add cubic EOS (PR/SRK) with transparent mixing rules and verified derivatives, then activity-coefficient models (NRTL/UNIQUAC) based on benchmark demand.

- Create a curated, provenance-rich parameter store only after interfaces and validation workflows stabilize.

> **Thermodynamic rule** — A converged flowsheet with inconsistent reference states or unsupported extrapolation is a failed engineering result. Compatibility checks occur before solve, and reference-state transformations are explicit.

## 7. Numerical core: solver orchestration

### 7.1 Objective

The solver is a deterministic policy engine over a portfolio of transparent numerical mechanisms. It analyzes the process and equation graphs, proposes and scores solve plans, executes them with checkpoints, observes progress, changes strategy under explicit rules, and emits a complete trace. The default policy is reproducible; optional learned ranking may advise but may not conceal or mutate the trusted path.

### 7.2 Solve pipeline

| Stage | Required work | Artifacts and decisions |
| --- | --- | --- |
| 0. Compile | Resolve models/properties, normalize units, flatten active equations, apply bounds/specs | CompiledProblem, source map, capability report |
| 1. Graph analysis | Process DAG/cycles; equation-variable bipartite graph; SCCs; block triangular form; sparsity; cut candidates | GraphReport, structural hashes |
| 2. Structural decomposition | DOF and matching; partition weak/strong blocks; propose tears; identify algebraic loops and singularity risk | DecompositionPlan candidates with scores |
| 3. Simple initialization | Defaults, bounds projection, property-state estimates, unit-local analytic/heuristic initialization, staged equation activation | InitialState plus confidence and violations |
| 4. Sequential solve | Topological unit execution; Wegstein/Aitken/Anderson recycle acceleration; bounded damping; tear convergence | SM trace, unit failures, recycle metrics |
| 5. Coupled EO solve | Assemble strongly coupled blocks or full problem; sparse Newton/trust-region/line-search methods | Block/full residual and step trace |
| 6. Continuation | Ramp feed, nonideality, reaction, heat coupling, recycle closure, or specification severity; adaptive step and rollback | Homotopy schedule and checkpoints |
| 7. Scaling | Variable/residual/Jacobian scaling; refresh only under defined triggers; detect extreme condition estimates | Scale factors, rationale, conditioning diagnostics |
| 8. Fallback | Switch tear set, block merge/split, initialization recipe, EO globalization, property formulation, or safe finite differences | Attempt tree and terminal diagnosis |
| 9. Certify | Check residuals, bounds, conservation, property consistency, complementarity/active set, and requested tolerances | SolutionCertificate or FailureBundle |

### 7.3 Graph and structural algorithms

- Maintain both a process connectivity multigraph and an equation-variable incidence bipartite graph; do not infer numerical coupling solely from unit topology.

- Use maximum bipartite matching for structural well/under/over-determination and Dulmage-Mendelsohn-style diagnostics; map unmatched nodes back to model source locations.

- Use strongly connected components and block triangularization to derive ordered blocks. Record stable tie-breaking so identical inputs produce identical plans.

- Score tear candidates using cycle coverage, estimated sensitivity/gain, variable dimension, physical bounds, derivative availability, and previous run history.

- Permit phenomenon-level partitions (phase equilibrium, reaction, energy, pressure) when declared coupling supports them; unit-operation boundaries are not privileged.

- Hash structural patterns separately from numerical values so nearby scenarios can reuse symbolic analysis safely.

### 7.4 Initialization

- Layered sources: user-provided state > warm start from compatible revision > unit initializer > upstream propagation > nominal/bounds midpoint > explicit failure.

- Each guess carries provenance and confidence. Projection onto bounds is logged; mass fractions are normalized only under an explicit repair policy.

- Initialize easy physics first: ideal properties before nonideal; zero/low reaction before full kinetics; open recycles before closure; fixed heat duties before tight design specs.

- Unit initialization must be testable independently and must not alter user specifications.

- Persist successful initialization recipes keyed by structural hash and operating-region signature, while treating them as hints rather than unreviewed truth.

### 7.5 Sequential-modular execution

Sequential execution is preferred for acyclic regions and weak recycles with robust explicit unit evaluators. Recycle convergence measures scaled tear residuals and physical violations. Acceleration methods have safeguarded acceptance; divergence, oscillation, stagnation, and invalid property calls trigger rollback and policy escalation.

### 7.6 Equation-oriented execution

- Compile residual and derivative evaluators with source maps. Assemble sparse Jacobians by analytic/AD blocks and audited finite differences only where declared.

- Primary nonlinear strategy: damped sparse Newton with line search or trust region; expose linear solve, factorization, pivot, regularization, and step acceptance statistics.

- Bounds are handled by transformations or bound-aware steps according to variable semantics; do not clip invisibly.

- Block solves may merge when outer iteration stalls or coupling estimates increase. Full-space EO is available but not the unconditional default.

- Convergence requires scaled residual, step, and physics-certificate criteria; a small optimizer termination metric alone is insufficient.

### 7.7 Automatic scaling

- Initial variable scaling comes from units-aware nominals, bounds, expected magnitude, and model hints; residual scaling comes from equation physical scales.

- Jacobian row/column equilibration may refine factors, with caps and diagnostic warnings for extreme adjustments.

- Scaling is frozen during a local Newton attempt unless a defined stagnation or regime-change trigger fires; changes create new trace segments.

- Report raw and scaled residuals. A solution cannot pass solely because scaling hides a materially large physical residual.

- Property and surrogate outputs use consistent scaling across value and derivative interfaces.

### 7.8 Continuation and homotopy

Homotopies are typed transformations, not arbitrary equation edits. Each exposes λ∈[0,1], an easy endpoint, target endpoint, admissibility checks, and rollback. The orchestrator selects from model-declared and generic transformations, adapts step size based on nonlinear effort and curvature, and checkpoints accepted states.

- Recycle closure; feed rate/composition/temperature ramp; reaction extent or kinetic severity; heat-transfer coupling; pressure drop; phase nonideality; specification tightening; surrogate-to-first-principles blending.

- Pseudo-arclength continuation is a later capability for folds; v0.x may use monotone adaptive parameter stepping.

- Failure at a step reduces step size; repeated failure selects a different path or returns the closest certified checkpoint.

### 7.9 Fallback policy and budgets

Fallbacks form a bounded attempt tree. Every edge has a trigger, precondition, cost class, and maximum count. Global wall-time, property-call, external-model, and factorization budgets prevent uncontrolled search. The terminal outcome names exhausted strategies and the best certified partial state.

| Observed condition | Candidate response |
| --- | --- |
| Structural mismatch | Stop before numerical solve; identify unmatched variables/equations and minimal conflicting spec set. |
| Bad initial property state | Switch state-variable formulation, project within declared domain, or request missing initialization. |
| Recycle oscillation/divergence | Reduce damping, change acceleration, choose alternate tear, or merge recycle region into EO block. |
| EO line search failure | Rescale, trust-region retry, regularize linear system, activate homotopy, or change block partition. |
| Singular/ill-conditioned Jacobian | Rank diagnostics, identify redundant equations/fixed variables, rescale, or use safeguarded least-squares step. |
| Phase-boundary nonsmoothness | Use phase-stable formulation, guarded property call, continuation, or complementarity-capable path. |
| Surrogate validity violation | Reject, constrain optimization, switch to parent model, or schedule refinement; never silently extrapolate. |
| External model timeout | Use cached certified result if exact inputs/hash match, retry within policy, or fall back to declared lower fidelity. |

### 7.10 Failure taxonomy and observability

- STRUCTURAL_UNDER/OVERDETERMINED, STRUCTURAL_SINGULAR_RISK, SPEC_CONFLICT.

- PROPERTY_DOMAIN, FLASH_NONCONVERGENCE, PHASE_INSTABILITY, REFERENCE_STATE_MISMATCH.

- MODEL_DOMAIN, CONSERVATION_VIOLATION, EXTERNAL_TIMEOUT/CRASH, DERIVATIVE_MISMATCH.

- INITIALIZATION_INFEASIBLE, RECYCLE_DIVERGENCE/OSCILLATION/STAGNATION.

- JACOBIAN_SINGULAR/ILL_CONDITIONED, LINEAR_SOLVE_FAILURE, GLOBALIZATION_FAILURE, ITERATION/BUDGET_EXHAUSTED.

- SURROGATE_OUT_OF_DOMAIN, UNCERTAINTY_THRESHOLD_EXCEEDED, OPTIMIZATION_INFEASIBLE.

The FailureBundle contains category, severity, causal chain, implicated IR objects/equations/variables, raw evidence, attempted remedies, best state, reproducible replay command, and ranked next actions. Explanation text is generated from this structure and is never the sole record.

### 7.11 Reproducibility classes

| Class | Guarantee |
| --- | --- |
| D0 Structural | Bitwise-identical canonical IR, validation, graph decomposition, and plan selection on supported platforms. |
| D1 Numerical deterministic | Same binaries, threads, seed, hardware class, and inputs yield identical trace and outputs within declared bitwise/tolerance policy. |
| D2 Numerically equivalent | Parallel/GPU/external execution may vary; certified outputs remain within specified tolerances and event differences are recorded. |
| D3 External nonreproducible | Provider cannot guarantee replay; inputs, outputs, hashes, environment, and uncertainty are preserved and prominently labeled. |

## 8. Multi-fidelity and external models

### 8.1 Fidelity ladder

A conceptual unit can own a ModelFamily: screening algebraic model → rigorous first-principles model → PyMRM distributed reactor → Peclet/CFD experiment → reduced-order or surrogate model derived from high-fidelity data. The family shares semantic ports and conserved quantities while models declare distinct states, costs, validity, and uncertainty.

### 8.2 PyMRM/Peclet integration

- PyMRM adapter maps process stream states and parameters to reactor boundary conditions, executes out of process, returns outlet/integral quantities plus convergence and discretization evidence, and optionally provides sensitivities.

- Peclet-style CFD/particle workflows are asynchronous experiment providers, not synchronous residual calls by default. Requests are content-addressed, queued, budgeted, and traced.

- A design-of-experiments service samples the process-relevant domain; data artifacts record process revision, model hash, mesh/numerical settings, and failed samples.

- Surrogate training records splits, transforms, metrics, calibration, uncertainty method, derivative tests, and applicability domain. ONNX or another portable form may be an execution artifact, never the only scientific record.

- The process solver enforces validity. Optimizers receive domain constraints or uncertainty penalties; extrapolation requires an explicit policy and emits a warning/failure.

### 8.3 Adaptive refinement loop

1. Solve and optimize with inexpensive models.

1. Rank model inadequacy using objective sensitivity × epistemic uncertainty × decision proximity.

1. Estimate expected value of added fidelity against compute cost and schedule budget.

1. Run targeted higher-fidelity experiments, update calibration/surrogate, and validate independently.

1. Replace the model in a branch, warm-start, re-optimize, and compare topology, operating point, economics, safety constraints, and uncertainty.

1. Stop when the decision is stable or refinement budget is exhausted; report unresolved decision risk.

## 9. Agent-native API and safety model

### 9.1 API principles

- Expose process semantics, not GUI coordinates or fragile object paths.

- Separate read, propose, validate, commit, execute, and publish permissions.

- Every mutating call accepts expected_revision and idempotency_key and returns a semantic diff.

- Long operations are jobs with events, budgets, cancellation, checkpoints, and artifact references.

- Tool schemas use stable IDs, typed quantities with units, explicit tolerances, and bounded result summaries; large traces remain queryable artifacts.

- Agent-generated explanations are clearly separated from deterministic validation and solver evidence.

### 9.2 Minimum tool surface

| Group | Representative operations |
| --- | --- |
| Inspect | get_process_summary, list_models, inspect_unit/stream/equations, get_dof_report, get_run_trace, explain_failure_evidence |
| Edit transaction | begin_change, add_unit, connect_stream, set_specification, replace_model, set_property_package, preview_diff, validate_change, commit/rollback |
| Solve | compile, initialize, solve, resume_from_checkpoint, compare_solve_plans, certify_solution |
| Study | create_scenario, sweep, sensitivity, estimate_parameters, optimize, propose_topology, compare_scenarios |
| Fidelity | assess_model_risk, plan_experiments, run_external_model, train_surrogate, validate_surrogate, promote_model |
| Provenance | branch, tag, lock_environment, export_run_bundle, reproduce_run |

### 9.3 Agent evaluation tasks

- Construct a flowsheet from a structured brief without unit/connection errors.

- Repair an under/overspecified model using the DOF report and minimal changes.

- Diagnose recycle divergence from evidence and select a justified solve action.

- Replace a reactor model while preserving semantic contracts and documenting invalidated results.

- Optimize a design without surrogate-domain violations and explain active constraints.

- Reproduce a prior result from a run bundle and detect an intentionally changed dependency.

## 10. Web GUI role

The GUI is a human workbench and observability client, not the source of truth. It must use public application APIs used by agents and scripts. No capability may exist only as a hidden front-end mutation.

- Flowsheet canvas with typed ports, component/phase compatibility feedback, and semantic rather than decorative connections.

- Inspector for model contract, equations, variables, specs, units, bounds, provenance, uncertainty, and validity envelope.

- DOF and structural view: unmatched variables/equations, SCC/block view, tear candidates, and dependency highlighting.

- Solve cockpit: plan stages, live residual norms, raw/scaled residual heatmap, recycle history, homotopy λ, scaling changes, checkpoints, and fallback tree.

- Scenario workspace: immutable branches, semantic diffs, result comparison, trade-off plots, and decision history.

- Multi-fidelity panel: model family, evidence lineage, training domain, uncertainty, compute cost, and replacement preview.

- Agent activity timeline showing proposed actions, deterministic validation, commits, jobs, permissions, and rollback points.

- Education mode that reveals equation source and numerical transformations without requiring source-code navigation.

## 11. Study, optimization, and synthesis architecture

- Studies reference immutable process revisions and define decisions, objectives, constraints, scenarios, sampling/optimization method, budgets, and certification rules.

- Expose derivative-aware local NLP first. Add derivative-free and mixed-integer methods as plugins; never conceal solver choice or stopping criteria.

- Process synthesis represents superstructures or typed graph rewrite proposals. Every topology candidate passes semantic/DOF validation before simulation.

- Separate feasibility restoration from economic optimization; retain infeasible candidates and reasons for learning and debugging.

- TEA/LCA are modular assessment models with currency year, geography, price, emission-factor, and uncertainty provenance.

- Optimization outputs include primal feasibility, active constraints, sensitivities when reliable, domain checks, multi-start evidence, and model/solver limitations.

## 12. Testing and validation strategy

### 12.1 Test hierarchy

| Level | Purpose | Required examples |
| --- | --- | --- |
| L0 Mathematical kernels | Prove local numerical correctness | units, graph algorithms, matching/SCC/BTF, scaling, line search, continuation step control |
| L1 Model contracts | Verify each unit/property/model independently | mass/energy/element balances, limiting cases, derivative checks, invalid domains |
| L2 Coupled subsystems | Exercise known numerical mechanisms | flash-heater, reactor-cooler, heat integration, one/two recycles, phase appearance |
| L3 Flowsheet regressions | End-to-end expected results and traces | canonical process cases, perturbed initial guesses/specs, warm starts |
| L4 Differential validation | Compare independent simulators/implementations | DWSIM, IDAES, BioSTEAM where applicable, CoolProp/thermo/property references |
| L5 Metamorphic/property tests | Test invariants without a single oracle | unit conversion, stream relabeling, split/recombine, component permutation, scaling invariance |
| L6 Robustness campaigns | Measure basins and failure quality | Latin-hypercube initial guesses, parameter perturbations, forced bad scaling, injected property failures |
| L7 Agent/API tests | Ensure safe autonomous operation | transaction conflicts, invalid edits, idempotency, budget/cancel, evidence-grounded diagnosis |
| L8 Performance/reproducibility | Prevent degradation | compile/solve time, allocations, property calls, trace determinism, platform matrix |

### 12.2 Numerical test requirements

- Every analytic or AD derivative implementation is compared with complex-step where valid and high-quality finite differences over nominal, boundary-near, and randomized states.

- All conservation models have symbolic or numerical balance tests. Elemental balance is checked for reaction models independent of convergence.

- Golden solution fixtures store inputs, expected physical outputs, tolerances, and provenance—not opaque serialized solver objects.

- Random/property-based tests have recorded seeds and minimized failing cases.

- Fallback paths are fault-injected deliberately; untested recovery code cannot be enabled by default.

- Tolerance tests distinguish absolute, relative, and physically meaningful engineering tolerances. No single blanket 1e-n rule.

- Benchmark reports show success rate distributions across initial guesses, not only one curated converged run.

### 12.3 Benchmark suite

| Tier | Cases | What it stresses |
| --- | --- | --- |
| A: kernels | scalar nonlinear roots; sparse block systems; ill-scaled networks; rank-deficient systems | globalization, scaling, diagnostics, structural analysis |
| B: thermo | ideal and nonideal TP/PH flashes; near phase boundary; dew/bubble; reference-state checks | property correctness, derivatives, typed failures |
| C: units | pump, valve, heater, HX, flash, conversion/equilibrium reactor, mixer/splitter | unit contracts, balances, limiting cases |
| D: networks | single recycle, nested recycles, heat/mass coupled recycle, purge, design spec | tearing, acceleration, EO block merge, homotopy |
| E: processes | flash train; reactor-separator-recycle; heat-integrated process; distillation surrogate/adapter case | end-to-end results, robustness, optimization |
| F: multi-fidelity | simple reactor ↔ PyMRM ↔ surrogate; external failure and OOD scenarios | replacement, lineage, uncertainty, asynchronous orchestration |
| G: agent | build, diagnose, modify, optimize, refine, reproduce | semantic tools, safety, auditability |

### 12.4 Cross-simulator validation protocol

- Use at least two independent open reference implementations whenever the physics overlaps: primarily DWSIM and IDAES; add BioSTEAM for conceptual/TEA cases and independent property libraries or published data for thermodynamics.

- Publish exact component data, property methods, reference states, unit conventions, tolerances, and solver settings. A comparison is invalid when model definitions differ materially.

- Compare conserved flows, T/P, phase fractions/compositions, duties/work, reaction extent/conversion, objectives, and sensitivities where available.

- Triangulate disagreements: conservation audit → property-level comparison → unit-level comparison → equation/solver comparison. Majority agreement is not proof.

- Pin reference versions in containers or lockfiles and archive input artifacts. License constraints are documented.

- Include nonconvergence and invalid-domain cases. A useful simulator must correctly refuse bad problems and diagnose them.

### 12.5 Validation criteria

| Criterion | Release-gate definition |
| --- | --- |
| Physical correctness | All certified solutions satisfy case-specific material, element, energy, bound, phase, and specification tolerances. |
| Reference agreement | For shared model definitions, key outputs meet predefined per-variable engineering tolerances; discrepancies have reviewed explanations. |
| Robustness | Target convergence rate is met over a published ensemble of initial guesses and parameter perturbations within fixed budgets. |
| Derivative quality | Declared derivatives pass numerical checks and optimization sensitivity checks within method-specific tolerances. |
| Diagnostic quality | Injected failures map to the correct taxonomy and identify implicated objects with actionable evidence. |
| Reproducibility | Run bundle reproduces certification class and numerical tolerances on supported environments. |
| Performance | No statistically significant regression beyond approved thresholds on versioned benchmark hardware. |

## 13. Phased roadmap

| Phase | Outcome | Exit focus |
| --- | --- | --- |
| 0 — Foundations | ADRs, schemas, units, quantity semantics, provenance, benchmark definitions, CI and packaging | Architecture can be falsified with executable fixtures before broad modeling. |
| v0.1 — Transparent kernel | Process IR, native ideal thermo, core units, graph/DOF/decomposition, initialization, SM+EO orchestration, scaling, bounded fallbacks, CLI/Python API | Small steady-state flowsheets solve reproducibly with inspectable traces and strong tests. |
| v0.2 — Agent & multi-fidelity | Transactional service/API, agent tools, web diagnostic shell, open thermo adapters, PyMRM adapter, surrogate lifecycle, study runtime | Agent completes a reactor-separator-recycle refinement workflow safely. |
| v0.3–0.9 — Breadth & hardening | Richer thermo/units, optimization, synthesis prototypes, performance, import/export, security, docs | Benchmark coverage and contributor ecosystem mature without architectural erosion. |
| v1 — Research-grade platform | Stable public contracts, validated benchmark suite, full web workbench, supported deployments, governance | Independent users reproduce published results and extend models without core forks. |

### 13.1 Workstream ordering

- Lock semantics, invariants, benchmark definitions, and observability before optimizing performance.

- Build graph/structural kernels and tiny synthetic models before flowsheet breadth.

- Implement native ideal thermodynamics to isolate solver development; add external property adapters only after conformance contracts exist.

- Ship headless solve and replay before the GUI; ship agent transactions before ambitious autonomous design.

- Introduce PyMRM integration before Peclet orchestration; establish data/provenance discipline at the smaller scale.

- Add optimization only after derivative and solution certification infrastructure is dependable.

## 14. Repository blueprint

Recommended monorepo until interfaces stabilize; packages must remain independently testable and dependency direction is enforced.

| Path | Responsibility |
| --- | --- |
| /docs/adr, /docs/specs | Architectural decisions; normative IR/model/solver/API specifications |
| /schemas | Versioned JSON Schemas, migrations, examples, golden canonicalization fixtures |
| /packages/ir | Immutable domain objects, validation, semantic diff, provenance |
| /packages/units | Physical units, dimensions, quantity types, conversions |
| /packages/models | Native streams and unit-operation models plus contract test kit |
| /packages/thermo | Property interfaces, native ideal package, adapters and conformance suite |
| /packages/graph | Process/equation graphs, matching, SCC/BTF, tearing and DOF diagnostics |
| /packages/numerics | Sparse problem interface, nonlinear methods, scaling, continuation, linear-solver adapters |
| /packages/orchestrator | Solve policies, attempt tree, checkpoints, events, certification, replay |
| /packages/adapters | PyMRM, external jobs, FMU/ONNX/container/remote adapters |
| /packages/studies | Sensitivity, estimation, UQ, optimization, synthesis and fidelity planning |
| /services/api, /clients/python, /clients/cli | Transactional application service and headless clients |
| /apps/web | Flowsheet and diagnostics workbench; contains no private simulation logic |
| /benchmarks | Case definitions, reference adapters, expected metrics, reports, version pins |
| /tests | Cross-package integration, robustness, fault injection, agent and reproducibility tests |
| /examples | Minimal, tutorial, and north-star multi-fidelity examples |

## 15. Engineering standards

- Specification first: public behavior and invariants are documented before implementation; important choices receive ADRs.

- Strict typing and schema validation at boundaries; dimensions are types or validated quantity objects, not comments.

- Pure/immutable domain operations where practical; explicit execution contexts and dependency injection; no hidden singletons.

- Public APIs use semantic versioning. Schema migrations and model compatibility rules are tested across supported versions.

- Formatting, linting, static typing, unit tests, contract tests, documentation examples, security scanning, and benchmark smoke tests run in CI.

- Core numerical changes require derivation/reference, adversarial tests, trace comparison, benchmark report, and reviewer with numerical-methods competence.

- Coverage targets are risk-based: 100% branch coverage for schema migrations, transaction validation, fallback routing, and certification logic; exhaustive path tests for enabled fallback states.

- Property/model adapters run conformance suites. Optional dependencies cannot alter default behavior merely by being installed.

- Structured logging uses stable event schemas; no scientific decision exists only in log prose.

- Performance changes require profiles and retained correctness. Fast wrong answers and opaque convergence do not count.

- Security: untrusted models execute out of process/container; resource limits, artifact allowlists, secret isolation, signed model packages, and network policy are enforced.

- Documentation includes equations, sign conventions, units, assumptions, validity, examples, failure modes, and benchmark provenance.

### 15.1 Definition of done for a model

- Manifest, schema, equations/algorithm, conservation statement, units/sign conventions, validity domain, initialization, scaling hints, and provenance are complete.

- Nominal, limiting, invalid-domain, randomized, derivative, conservation, serialization, and adapter-conformance tests pass.

- At least one coupled flowsheet test and one independent reference comparison pass, or the absence of a reference is explicitly justified.

- Failure modes emit typed diagnostics; examples and API documentation are executable.

- Model package version and compatibility are locked in a reproducible run bundle.

## 16. Risks and mitigations

| Risk | Consequence | Mitigation / kill criterion |
| --- | --- | --- |
| Thermodynamic breadth dominates | Project becomes a property-data effort before core value appears | Narrow native package; adapters; benchmark-driven additions; never claim unsupported coverage. |
| Original solver scope expands | Years spent recreating commodity linear algebra | Own orchestration/process numerics; reuse audited sparse/AD kernels behind interfaces. |
| Architecture overgeneralizes | Complex contracts delay working cases | Prove each abstraction against three unlike implementations and delete unused flexibility. |
| Model plugins destabilize core | Crashes, nondeterminism, incompatible derivatives | Conformance kit, capability negotiation, isolation, resource budgets, signed manifests. |
| Agent causes unsafe mutations | Invalid or irreproducible engineering results | Transactions, permissions, deterministic validators, budget limits, immutable history, human approval policies. |
| Surrogates mislead optimizer | False optimum outside training domain | Validity constraints, uncertainty, OOD tests, parent-model spot checks, refinement triggers. |
| Benchmark gaming | Good curated demos, weak general robustness | Publish ensembles, seeds, budgets, failures, independent references, and regression history. |
| GUI consumes roadmap | Attractive shell precedes trustworthy core | Headless acceptance gates; GUI uses only public API and initially prioritizes diagnosis. |
| Cross-simulator disagreement | Validation stalls due to semantic differences | Common case specification, property-level triangulation, documented reconciliation workflow. |
| Community fragmentation | Adapters and models fork contracts | Stable extension kit, governance, compatibility tests, model registry and deprecation policy. |

## 17. Release acceptance criteria

### 17.1 v0.1 — Transparent solver kernel

- Canonical Process IR v0.1, schema, migration harness, semantic diff, immutable revision IDs, units, provenance, and round-trip golden tests.

- Native ideal thermodynamics with TP and PH flash cases, analytic/verified derivatives, reference states, and typed domain failures.

- Core unit library listed in §5.4; every model satisfies the model definition of done.

- Graph analysis, DOF/matching diagnostics, SCC/BTF decomposition, stable tear selection, and source-mapped structural reports.

- Orchestrated path implements simple initialization, acyclic/sequential execution, recycle acceleration, EO solve for coupled blocks, adaptive continuation, automatic scaling, checkpoint/rollback, and at least three distinct tested fallback classes.

- Solver trace and SolutionCertificate/FailureBundle are stable serializable schemas; identical seeded runs meet D0/D1 policy on the primary platform.

- Benchmark tiers A–D contain at least 30 cases total. All correctness gates pass; at least 90% of the published nominal robustness ensemble converges within fixed budgets, with 100% correct handling of intentionally invalid structural cases.

- DWSIM and IDAES comparison exists for at least eight overlapping cases; each case has reconciled semantics and predefined tolerances.

- Python SDK and CLI can construct, validate, solve, inspect, replay, and export without a GUI.

- No enabled numerical fallback lacks a direct fault-injection test.

### 17.2 v0.2 — Agent-native multi-fidelity workflow

- Transactional API with optimistic concurrency, idempotency, preview/validate/commit/rollback, jobs, budgets, cancellation, events, and artifact store.

- Typed agent tool surface covers all groups in §9.2; the reference agent passes at least 80% of published tasks without direct IR text editing and never commits an invalid process.

- Web GUI supports flowsheet editing, model/equation inspection, DOF view, solve trace/fallback tree, scenario diff, and agent activity timeline using only public APIs.

- At least two additional open thermodynamic/property adapters pass a shared conformance suite; mismatched reference states and unsupported capabilities fail before solve.

- PyMRM adapter executes a version-pinned reactor model out of process with boundary mapping, timeout, cache, provenance, and result validation.

- Surrogate lifecycle supports DOE, training, independent validation, uncertainty/validity envelope, derivative test, portable execution artifact, and promotion/rollback.

- North-star reactor–separator–recycle example replaces a simple reactor with PyMRM-derived surrogate, reoptimizes, and reports decision change and uncertainty with full lineage.

- Benchmark tiers E–G are active; robustness, API safety, OOD, external timeout, and reproduction scenarios pass in CI/nightly tiers.

### 17.3 v1 — Stable research-grade platform

- Process IR, model contract, property contract, solver trace, run bundle, and transactional API are stable v1 with documented compatibility/deprecation policy.

- Validated steady-state library covers the agreed benchmark envelope, including nonideal separations and coupled reactor/separation/heat-integration cases; unsupported domains are explicit.

- Published benchmark suite includes at least 100 cases, at least 25 cross-simulator comparisons, robustness ensembles, machine-readable results, and reproducible containers/locks.

- On the published supported envelope, certified solution success is at least 95% within budgets across robustness ensembles; no known false certification; every failure returns a typed, replayable diagnosis bundle.

- Optimization supports derivative-aware constrained studies, multi-start evidence, domain enforcement, sensitivity checks, and at least one synthesis/superstructure demonstrator.

- The complete PyMRM/Peclet-style asynchronous refinement loop is demonstrated: high-fidelity experiment selection, artifact provenance, surrogate update, process reinsertion, and decision-stability analysis.

- Web workbench, SDK, CLI, and agent tools are feature-consistent for core workflows and operate on the same revision/event model.

- Independent external users can reproduce published benchmark and north-star results from clean environments and add a new unit model using the extension kit without modifying core packages.

- Security threat model, plugin sandboxing, governance, release signing, support matrix, contributor documentation, and long-term benchmark stewardship are in place.

## 18. Implementation-plan handoff

The coding agent receiving this blueprint should produce an implementation plan with the following mandatory outputs. It may refine sequencing and technology choices but must preserve the architectural invariants unless it proposes an ADR with evidence and an explicit migration impact.

- Traceable requirements matrix mapping every v0.1 criterion to packages, work items, tests, owner role, dependencies, and evidence artifact.

- Technology decision matrix for implementation language(s), sparse linear algebra, AD, serialization, API framework, job runtime, and web stack; include benchmark prototypes for high-risk choices.

- First 12–16 week milestone plan centered on executable vertical slices, not isolated framework construction.

- Normative initial schemas for Process IR, ModelManifest, CompiledProblem, SolvePlan, SolveEvent, FailureBundle, SolutionCertificate, and RunManifest.

- Numerical spike plan proving matching/SCC/BTF, tear solve, block EO solve, scaling, continuation, and fallback on synthetic and small process cases.

- Benchmark acquisition plan with exact reference versions, licensing, case ownership, reconciliation workflow, and automated report generation.

- Risk register with trigger metrics and kill/pivot criteria, especially for thermodynamics, AD/sparsity, plugin isolation, and multi-language boundaries.

- CI matrix, coverage policy, reproducibility environments, performance baselines, security model, documentation structure, and release process.

- Backlog that separates v0.1 commitments from explicitly deferred work; no GUI polish or unit-operation breadth may displace solver transparency and validation gates.

> **Final instruction to implementers** — The numerical core is original, transparent, inspectable, deterministic where appropriate, and exhaustively tested. Treat every hidden heuristic, silent fallback, unverifiable derivative, or unreproducible result as architectural debt requiring an explicit issue and acceptance decision.

## Appendix A — Required core schemas

| Schema | Essential fields |
| --- | --- |
| CompiledProblem | IR revision/hash, variables/equations with source maps, bounds, nominals, residual/Jacobian capabilities, sparsity, property dependencies |
| SolvePlan | plan id, structural hash, blocks/order, tears, initialization stages, solver/scaling/homotopy policies, budgets, deterministic tie-break data |
| SolveEvent | sequence, time, stage/attempt/block, event type, metrics, implicated object IDs, decision rule, artifact refs |
| FailureBundle | taxonomy code, causal chain, evidence, best checkpoint, attempted remedies, exhausted budgets, next actions, replay identity |
| SolutionCertificate | termination, tolerances, raw/scaled residuals, conservation/spec/bounds/property/domain checks, reproducibility class, warnings |
| RunManifest | process/model/property/solver/dependency hashes, platform, seed, threads, policies, inputs, outputs, parent run |

## Appendix B — Initial benchmark case inventory

| Category | Minimum cases |
| --- | --- |
| Structure | acyclic chain; redundant spec; missing spec; algebraic loop; structurally singular but square; component mapping error |
| Scaling | mixed Pa/bar and mol/s/kmol/h; 12-order magnitude variables; badly scaled energy balance; near-zero trace component |
| Thermo | binary ideal flash; PH flash; bubble/dew; phase disappearance; near-critical rejection/handling; reference-state mismatch |
| Recycle | linear recycle; high-gain recycle; oscillatory recycle; nested recycle; recycle coupled to flash; purge stabilization |
| Reaction | adiabatic conversion; equilibrium with heat; recycle reactor; selectivity-sensitive reactor; infeasible conversion |
| Heat integration | countercurrent HX; approach constraint; heat-integrated recycle; coupled duties/design spec |
| Failure injection | bad derivative; property timeout; NaN from plugin; singular Jacobian; homotopy step failure; OOD surrogate |
| Cross-tool | at least eight v0.1 shared DWSIM/IDAES cases, expanded to 25+ by v1 |
