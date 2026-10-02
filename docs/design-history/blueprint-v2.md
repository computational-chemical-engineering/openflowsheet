# Agent-Native Open Process Simulator

**Technical blueprint for a transparent, multi-fidelity process-engineering platform with an original solver-orchestration core**

> **Implementation-agent directive:** Treat this document as the architectural design baseline. Derive an executable implementation plan, ADRs, package boundaries, milestones, and traceable tests from it. Preserve the stated invariants and acceptance criteria unless a proposed ADR explicitly documents evidence, trade-offs, and migration impact.

**Version:** 2.0
**Date:** 6 September 2026
**Supersedes:** v1.0 (29 August 2026)
**Status:** Design baseline
**Audience:** Technical founder, numerical-methods lead, process-modeling lead, and high-end coding agent

---

## 0. What changed in v2.0, and why

v1.0 is architecturally sound. Its weaknesses are not in the abstractions but in four places: (a) decisions it defers that are actually blocking and irreversible; (b) numerical mechanisms that the published literature identifies as decisive but that v1.0 omits or demotes to fallbacks; (c) a v0.1 scope that is not achievable by a small team; and (d) an agent/interop layer written before the 2026 evidence base existed.

The eighteen changes below are the substance of this revision. Each names the evidence that motivated it. Sections later in this document are marked **[C-n]** where they implement a change.

### 0.1 Blocking decisions v1.0 deferred

**C1 — Licensing is an architectural constraint, and v1.0 never names a license.**
v1.0 says "third-party linear algebra is allowed behind stable interfaces" without noting that the obvious candidates are not license-equivalent. Concretely: Pyomo is BSD-3; CasADi is LGPL; SuiteSparse **KLU is LGPL-2.1+** but **UMFPACK is GPL**; MUMPS is CeCILL-C (GPL-compatible, copyleft); HSL MA57/MA48 are not free. A project that intends to host adapters to proprietary property packages and to be embedded by industrial users cannot discover this at v0.3. **Action:** a Phase-0 ADR fixes the project license (recommended: Apache-2.0 for core, with a documented "no GPL in the default install path" rule), and a machine-checked dependency-license gate runs in CI. Default sparse LU: KLU (LGPL, dynamically linked, excellent on the unsymmetric, highly sparse, structurally-repeated systems that flowsheets produce); MUMPS and MA57 are optional, off by default, and cannot change results silently.

**C2 — Buy-vs-build for the compiled-problem/AD layer is the decision that determines whether v0.1 ships.**
v1.0 correctly refuses to write BLAS or AD, but leaves open the far larger question: does the project own a symbolic layer, or sit on an existing algebraic modeling language? IDAES already provides Pyomo blocks, structural diagnostics, a Dulmage–Mendelsohn toolbox, degeneracy detection, scaling reports, and Ipopt integration. Rebuilding that is not "original orchestration"; it is re-implementing a funded national-lab effort. **Action:** define a narrow `CompiledProblem` interface (residuals, sparsity, JVP/VJP, sparse Jacobian, source map) and ship **two backends from day one**: a reference backend on a third-party AD/graph engine, and a thin native backend for models that supply analytic residuals directly. The originality claim moves — explicitly and defensibly — to orchestration, structural policy, initialization, continuation scheduling, certification, provenance, and the agent contract. Backend choice is an ADR with a benchmark prototype, and the two-backend rule is what keeps the interface honest.

### 0.2 Numerics the literature says are decisive and v1.0 under-weights

**C3 — Block triangularization will not decompose real flowsheets, and the plan must say so.**
The decomposition literature is blunt: applied to a model with countercurrent flow or a long recycle loop, block triangularization routinely yields one diagonal block containing almost all variables and equations. v1.0's §7.3 treats SCC/BTF as a primary performance mechanism. It is not. Its primary value is **diagnostic** — Dulmage–Mendelsohn identifies structurally over- and under-determined subsets and maps them to source, which is exactly the DOF-repair story the agent needs. **Action:** reframe §7.3 accordingly, require the solver to report `largest_block_fraction`, and forbid claiming decomposition benefit when that fraction approaches 1. Real leverage in the giant block comes from tearing, phenomena-based partitioning, and C4.

**C4 — Pseudo-transient continuation (PTC) is missing and belongs in the core.**
Pattison & Baldea's reformulation of a selected subset of steady-state algebraic equations as ODEs in a fictitious time — integrated to steady state with a variable-step integrator — is the most effective published mechanism for expanding the convergence basin of equation-oriented flowsheets, and it composes with optimization. It is a different mechanism class from parameter homotopy: no continuation parameter, no path-following, initial *conditions* replace the initial *guess*. **Action:** PTC becomes stage 6b of the solve pipeline and a declared model capability (which equations are PTC-reformulable, with time-constant hints). Later work on inertial-manifold PTC is the performance path.

**C5 — The phase-equilibrium formulation is a core architectural choice, not a fallback.**
v1.0 mentions "complementarity-capable path" once, in the fallback table. But whether VLE is expressed as a procedural inner flash, as complementarity constraints, as smoothed-max complementarity, or as a nonsmooth formulation with generalized (lexicographic) derivatives determines whether the flowsheet is differentiable at all, whether phases may appear and disappear inside a Newton iteration, and whether the process can be optimized across a phase boundary. It also determines a known failure: complementarity VLE admits trivial solutions unless bubble/dew calculations are embedded. **Action:** new §6.4 makes this an explicit, versioned, per-property-package declaration with mandatory test cases, and v0.1 must ship at least one formulation that survives phase disappearance.

**C6 — Restructure thermodynamics around a differentiable potential, not a bag of property functions.**
v1.0's property contract enumerates enthalpy, entropy, density, cp, ... as separate capability calls with separately verified derivatives. The modern open EOS libraries — teqp, FeOs, Clapeyron.jl — all converged on the opposite design: implement the residual Helmholtz energy (or excess Gibbs energy) **once**, and obtain every property and every derivative by automatic differentiation. Less code, no derivative/property inconsistency class of bug, exact derivatives by construction. **Action:** the property contract's primitive is a differentiable potential plus an ideal-gas reference; the property surface is a set of derived accessors with a documented derivative provenance. Packages that can only offer tabulated properties declare a lower capability tier and are excluded from EO paths that need second derivatives.

**C7 — Property *data* licensing is a project-level risk v1.0 does not name.**
DIPPR 801 is copyrighted and distributed only through authorized channels; NIST TDE's evaluated editions are subscription SRD products. The `chemicals`/`thermo` stack (MIT) is the viable redistributable base, and it is explicitly *not* an exhaustive recommended-value database. **Action:** every parameter record carries a license tag and a source citation; the packaged distribution refuses to bundle non-redistributable data; a first-class "bring your own data" ingestion path with provenance is a v0.1 deliverable, not an afterthought. Never claim coverage the license permits you to ship.

**C8 — Conditional equations introduce discrete structure, and v1.0 has no policy for it.**
v1.0's `Equation` object carries "active conditions". That quietly admits switching (phase appearance, flow reversal, regime change, min/max selectors) into a solver whose determinism and convergence story assumes a fixed equation set. Without a policy this is an unbounded source of non-convergence, cycling, and non-reproducible plans. **Action:** new §7.11 requires every conditional to be classified as (i) reformulated to complementarity, (ii) smoothed with a declared smoothing parameter under continuation, or (iii) resolved by an explicit outer discrete loop with cycle detection and a bounded iteration count. Unclassified conditionals fail validation.

**C9 — No distillation column means no credible benchmark story.**
v1.0's v0.1 unit library has no column, yet v1 promises "nonideal separations" and cross-simulator validation. Distillation is where the majority of real convergence difficulty and essentially all of the comparability credibility lives. **Action:** an equilibrium-stage MESH cascade is a named v0.2 deliverable with ChemSep and DWSIM as references, and a v0.1 precursor ships as an explicit N-stage flash cascade so the tearing/EO machinery is exercised on a stiff, strongly coupled block before the full column exists. Add **ChemSep** to the reference-implementation list; it is the canonical open column reference and v1.0 omits it.

### 0.3 Method upgrades

**C10 — Make the surrogate validity envelope conformal.**
v1.0 requires "uncertainty method" and a "soft training envelope" without saying what makes them trustworthy. Split-conformal prediction gives distribution-free, finite-sample marginal coverage regardless of surrogate architecture, costs seconds to calibrate, and — critically for a release gate — is *testable*: empirical coverage on a held-out set is a number that either meets the target or does not. **Action:** conformal prediction sets are the default declared uncertainty for surrogates; a separate geometric/density-ratio check handles domain membership. Coverage becomes a validation criterion in §12.5.

**C11 — Replace ad-hoc fidelity scheduling with trust-region filter methods.**
v1.0 §8.3 step 3 ("estimate expected value of added fidelity") is hand-waving. The trust-region filter framework (Eason & Biegler, and the 2024–2026 refinements including Hessian-informed variants) solves exactly this problem — optimizing a glass-box flowsheet with embedded expensive black-box models by alternating surrogate optimization with intermittent truth-model sampling — and it converges to a stationary point *of the high-fidelity problem*. That is a far stronger and more defensible claim than "surrogate plus validity constraints". **Action:** TRF is the primary gray-box optimization strategy in the study runtime; multi-fidelity Bayesian optimization and expected-information-gain estimators serve experiment *selection*, not the optimization inner loop.

**C12 — The agent layer is written against 2026 evidence now.**
Since v1.0 was drafted, concrete benchmarks exist: CRAFTS/OpenIDAES-450 (450 IDAES process-simulation cases with executable models and auditable execution records, covering unit selection, topology, property-package assignment, specification closure, initialization, recycle handling, solver diagnosis and optimization), the Simona text-to-flowsheet dataset, and PSE-Bench. MCP is the de facto agent transport, including in published Aspen/AVEVA agent work. Reported agent failure modes are specific: hallucinated properties and parameter drift, context overflow on large flowsheets, inability to validate feasibility without simulator feedback, and poor recovery from convergence failures. **Action:** §9 adds MCP as a first-class transport binding; §9.3 adopts an external benchmark for comparability alongside the project's own tasks; API design requirements are derived from the documented failure modes (context-budgeted views, cost-tagged tools, structured recovery affordances); and a **prompt-injection threat model** is added — model manifests, component names, comments, and external model outputs are untrusted text that reaches an LLM, which v1.0's sandboxing section does not cover.

**C13 — Benchmark reporting gets a required statistical form.**
v1.0 asks for "success rate distributions" without fixing a method, which makes cross-release and cross-tool claims unfalsifiable. **Action:** Dolan–Moré performance profiles are the required reporting form for solver comparisons (they summarize robustness and efficiency without letting a few easy or pathological cases dominate), shifted geometric means for timing, published seeds and budgets, an explicit definition of "solved", and a mandatory **NOT_COMPARABLE** verdict for cases whose semantics differ between tools rather than a silent reconciliation.

**C14 — Interoperability targets get sharpened from "opportunistic" to scheduled.**
SFILES 2.0 export/import is cheap, is the emerging FAIR interchange notation for flowsheet topology, and immediately buys comparability and an ML/agent data story — it should be a v0.1 deliverable, not opportunistic. SSP 2.0 (with FMI 3.0 support and layered standards for metadata and digital signatures) is structurally the same idea as the run bundle; align with it rather than inventing a container. DEXPI 2.0 covers PFD/P&ID handover. CAPE-OPEN thermo import is valuable but carries a Windows/COM deployment constraint that must be stated. A JSON-LD projection aligned to OntoCAPE/OntoProcess vocabulary makes the IR a knowledge-graph citizen at the cost of a mapping file — do the projection, do not build on RDF.

### 0.4 Delivery realism

**C15 — v0.1 as specified is not a first release; insert a walking skeleton.**
v1.0's v0.1 requires the IR, migrations, semantic diff, units, provenance, native thermo with verified derivatives, six unit families, full graph/DOF/BTF machinery, initialization layers, SM and EO execution, scaling, continuation, three tested fallback classes, checkpointing, certificates, failure bundles, SDK, CLI, 30 benchmark cases, and eight reconciled cross-simulator comparisons. That is a multi-person-year scope presented as a first milestone, and the 12–16 week plan in §18 cannot reach it. **Action:** insert **v0.0 "walking skeleton"** (4–6 weeks): three components, ideal thermo, mixer/flash/heater/splitter, one recycle with one tear, one damped Newton, and — the actual point — the complete vertical slice of trace, certificate, failure bundle, run manifest, and replay. Prove the *schemas and the provenance chain* before broadening the physics. §13 is rescoped accordingly and a staffing assumption is stated explicitly so the plan can be falsified on effort, not just on architecture.

**C16 — Add the risk that actually kills open process simulators.**
v1.0's risk table covers scope, plugins, agents, surrogates, benchmarks and GUIs, but not maintenance. The dominant failure mode for academic simulation software is that funding supports new features, not maintenance, and the project orphans. **Action:** a governance and sustainability risk entry with concrete mitigations (license and CNAME/trademark clarity, dependency minimalism, a no-orphan-subsystem rule, documented maintainer succession, and an explicit decision about what is deliberately *not* maintained).

**C17 — Property evaluation is the dominant cost; make caching architectural and the call count a reported metric.**
v1.0 mentions batching as a "performance design point" and property calls as a budget. In practice flash and property evaluation dominate EO flowsheet cost. **Action:** a content-addressed property cache keyed by (package hash, spec kind, quantized state, component set) with derivative reuse is part of the property-service architecture, and `property_calls` is a first-class benchmark metric reported alongside time, not merely a budget cap.

**C18 — Make determinism testable rather than asserted.**
D0 claims bitwise-identical decomposition and plan selection. That only holds under a discipline. **Action:** canonical sorted iteration over stable IDs everywhere in the analysis path, seeded and fixed hash behavior, deterministic tie-breaking in matching and SCC ordering, and **no parallelism anywhere in the plan-selection path**. The gate is a CI job asserting structural-hash equality for the full benchmark corpus across two platforms.

---

## Document contract

This blueprint fixes the architectural invariants, interfaces, numerical behavior, quality gates, and release outcomes. It deliberately does not prescribe every library or class. A coding agent should derive an implementation plan, architecture decision records (ADRs), work packages, dependency graph, and estimates without reopening the core design.

> **Product thesis** — Do not build an open clone of Aspen. Build an open scientific runtime in which the process, equations, solution strategy, data lineage, and model-fidelity decisions are explicit machine-readable objects shared by humans and agents.

### Executive decisions

| Decision | Blueprint commitment |
| --- | --- |
| Canonical object | A versioned Process IR, independent of GUI, solver backend, and agent transport. |
| Numerical core | Original orchestration, structural analysis, initialization, scaling, continuation, pseudo-transient reformulation, fallback, diagnostics, and certification. Linear algebra, automatic differentiation, and the expression graph are third-party behind a stable `CompiledProblem` interface with at least two backends. **[C2]** |
| Model composition | Typed contracts support native equations, first-principles modules, reduced-order models, surrogates, FMUs, and external high-fidelity services. |
| Thermodynamics | Pluggable property-service boundary whose primitive is a differentiable thermodynamic potential; validate and integrate open implementations before attempting broad proprietary-grade coverage. **[C6]** |
| Licensing | Apache-2.0 core; no GPL dependency in the default install path; every bundled data record carries a redistribution license tag; CI enforces both. **[C1] [C7]** |
| Clients | Headless Python/HTTP/CLI, MCP tools first; web GUI is another client of the same transactional API. **[C12]** |
| Quality | Deterministic fixtures, property-based tests, Jacobian checks, solver traces, cross-simulator benchmarks with performance profiles, and reproducible validation reports are release gates. **[C13]** |

## 1. Mission, scope, and non-goals

### 1.1 Mission

Create an open, agent-native process-engineering platform for autonomous multi-fidelity process design. Every component can be represented by interchangeable first-principles, reduced-order, surrogate, or external high-fidelity models. Humans and agents operate on the same transparent representation and receive the same validation, diagnostics, provenance, and permissions.

### 1.2 Primary user journeys

- A process engineer builds or imports a steady-state flowsheet, inspects degrees of freedom, solves it, and understands why the chosen numerical path succeeded or failed.

- A coding agent creates a process transactionally, changes topology or specifications, runs validation, solves, compares branches, and produces an auditable engineering report.

- A researcher replaces a simple reactor with a PyMRM model, samples it, trains a surrogate with a conformal validity envelope, reinserts it, and quantifies whether the process decision changes.

- A design agent explores flowsheet alternatives, performs continuous and discrete optimization under a trust-region filter, and escalates model fidelity only where expected decision value justifies cost.

- An educator exposes equations, units, residuals, scaling, initialization, and solver decisions rather than presenting a black-box convergence indicator.

### 1.3 In scope

- Steady-state material and energy balances; vapor/liquid phase equilibrium; core unit operations; recycles and design specifications.

- Transparent Process IR, schema migration, validation, diffing, provenance, scenario branches, and deterministic run manifests.

- Hybrid sequential-modular/equation-oriented/pseudo-transient solution orchestrated from graph and equation structure.

- Pluggable thermodynamics, model adapters, derivatives, uncertainty metadata, validity domains, and multi-fidelity replacement.

- Parameter estimation, sensitivity, optimization, early process synthesis, TEA hooks, and external assessment adapters.

- Typed agent tools over MCP, Python SDK, service API, CLI, event stream, and a diagnostic web interface.

### 1.4 Explicit non-goals

- Matching Aspen's component databank, refinery, polymer, solids, electrolyte, safety, and regulatory breadth in early releases.

- Claiming universal convergence or numerical superiority. The measurable promise is transparent strategy selection, robust benchmark performance under published performance profiles, and actionable failure diagnosis.

- Making an LLM part of the trusted numerical path. Agents propose actions; deterministic validators and runtimes authorize and execute them.

- Building dynamics, control, online digital twins, full P&ID authoring, or plant operations into v1.

- Writing BLAS, sparse direct linear solvers, automatic differentiation, or a general-purpose symbolic expression engine from scratch. These are dependencies behind replaceable interfaces; orchestration and process-specific numerics remain original. **[C2]**

- Redistributing thermophysical parameter data whose license does not permit it. **[C7]**

- Embedding high-fidelity PDE/CFD solves directly inside every nonlinear iteration by default.

## 2. Design principles and invariants

| Principle | Required consequence |
| --- | --- |
| Transparency by construction | Equations, variables, residuals, units, scaling, sparsity, decomposition, iterations, events, and fallbacks are inspectable and serializable. |
| One semantic truth | The Process IR is authoritative. GUI diagrams, code, reports, and solver models are projections or compiled artifacts. |
| Typed contracts | Every model declares ports, quantities, equations/evaluator, derivative capabilities, initialization, validity, fidelity, uncertainty, cost, and provenance. |
| Separate semantics from execution | A model says what it means; adapters and compiler layers say how it runs. |
| Transactions before mutation | All agent and UI changes are proposed, validated, previewed, committed or rolled back, and attributed. |
| Determinism where appropriate | Canonical serialization, graph analysis, compilation, and default strategy choice are deterministic by construction: sorted stable-ID iteration, fixed hash seeds, deterministic tie-breaks, and no parallelism in the plan-selection path. Parallel floating-point reductions are documented where bitwise reproducibility is impossible. **[C18]** |
| No silent repair | Clipping, extrapolation, relaxed tolerances, substituted properties, smoothing-parameter changes, and fallback strategies emit structured events. |
| Physics before convenience | Units, conservation, bounds, phase semantics, and thermodynamic compatibility are enforced at model boundaries. |
| Failure is a product output | Unsuccessful solves return a diagnosis bundle, not only an exception string. |
| Progressive fidelity | Cheap models screen designs; higher fidelity is introduced based on sensitivity, uncertainty, and decision value, under an algorithm with stated convergence properties. **[C11]** |
| Untrusted text is untrusted | Any string that originates outside the core — manifests, component names, annotations, external model output, comments — is data. It is never concatenated into an agent's instruction context without provenance labelling and length bounds. **[C12]** |

## 3. System architecture

The platform is organized as a strict dependency stack. Higher layers may call lower layers; the numerical core must never depend on the web GUI, agent framework, or a specific model provider.

| Layer | Responsibilities | Key outputs |
| --- | --- | --- |
| Process IR & schema | Semantic graph, quantities, equations, specs, objectives, model identities, provenance | Canonical document, validation report, semantic diff |
| Model registry/contracts | Versioned models and adapters; capabilities, validity, uncertainty, cost | Resolved model graph, compatibility report |
| Thermodynamics | Differentiable potentials, property accessors, flash surface, reference states, phase policy, property cache | Typed property results and diagnostics |
| Compiler & structural analysis | Flattening, unit normalization, incidence graph, DOF, SCC/BTF, tearing candidates, sparsity, PTC reformulation | `CompiledProblem` and solve-plan candidates |
| Numerical runtime | Initialization, SM execution, EO blocks, PTC integration, scaling, homotopy, fallbacks, checkpointing | Solution, trace, residual/Jacobian diagnostics |
| Study runtime | Sensitivity, estimation, UQ, optimization (incl. trust-region filter), topology search, fidelity scheduling | Versioned study results |
| Application services | Transactions, jobs, caching, artifacts, auth/policy, collaboration | Stable API and event stream |
| Clients | Python SDK, CLI, MCP tool server, web GUI | Human and agent workflows |

### 3.1 Required boundaries

- IR packages contain no solver objects or UI coordinates in semantic nodes; optional layout is a separate projection.

- Unit models cannot reach global mutable state. They receive typed evaluation contexts and property-service handles.

- Thermodynamic packages cannot mutate process variables or choose global solve strategy.

- External models execute through sandboxed adapters with declared timeout, retry, cache, derivative, and provenance behavior.

- Optimization operates on compiled differentiable problems when possible and uses declared derivative limitations when not.

- Every run pins schema, model, property-package, solver-policy, dependency, and platform versions.

### 3.2 The CompiledProblem boundary and backend policy **[C2]**

The single most consequential interface in the system. `CompiledProblem` exposes: variable and equation vectors with source maps back to IR objects; bounds and nominals; residual evaluation; sparsity pattern; sparse Jacobian, JVP, and VJP with declared provenance (analytic / AD / audited finite difference); optional second-order products; and a structural hash.

Rules:

- At least two backends exist at all times. One is a third-party AD/expression engine (the reference backend, selected by ADR with a benchmark prototype); one is a thin native backend for models supplying analytic residuals and Jacobian blocks directly. Any capability that cannot be expressed through both is a design smell and is reviewed.

- No orchestration code imports a backend type. Backend selection is a run-manifest field.

- Backend licence class is declared. A backend that would pull a GPL dependency into the default install path is opt-in, off by default, and flagged in the run manifest. **[C1]**

- A Pyomo bridge is a first-class *export* target (for Ipopt-based NLP, and for reusing mature structural diagnostics), not a runtime dependency of the core.

## 4. Process IR

### 4.1 Semantic object model

| Object | Minimum fields |
| --- | --- |
| Process | id, name, schema_version, component_set, graph, specs, objectives, scenarios, provenance |
| ModelInstance | model_ref, semantic_role, parameters, variable bindings, fidelity, validity policy, annotations |
| Port | kind, direction, phase capability, quantity schema, conservation basis, causality hints |
| Stream | source/target port, material/energy/signal type, state definition, composition basis, tear metadata |
| Quantity | stable id, meaning, unit dimension, display unit, value/state, bounds, nominal, scale, uncertainty |
| Equation | stable id, residual form, dependencies, differentiability, priority, source, **conditional class** (see §7.11), PTC eligibility and time-constant hint |
| Specification | target variable/equation, fixed/free state, tolerance, rationale, owner |
| Objective/constraint | expression, sense, weight, bounds, scenario scope |
| ComponentRecord | identifiers (CAS, InChIKey, SMILES), parameter values, **source citation, license tag, redistributable flag** **[C7]** |
| ProvenanceRecord | actor, timestamp, parent revision, operation, source references, hashes, environment |

### 4.2 Validation pipeline

- Schema validation: required fields, enum values, identity uniqueness, and migration compatibility.

- Dimensional validation: every equation and connection is dimensionally consistent; conversions are explicit compiled nodes.

- Graph validation: port direction, multiplicity, required connectivity, allowed signal/material/energy edges, and component-set compatibility.

- Physical validation: normalized compositions, nonnegative phase fractions, admissible states, conservation metadata, and model validity domains.

- Structural validation: equation/variable counts, fixed-variable conflicts, unmatched equations/variables via Dulmage–Mendelsohn, rank-risk indicators, and active conditional structure.

- Conditional validation: every conditional equation carries a resolution class (§7.11). Unclassified conditionals are a hard error. **[C8]**

- Capability validation: property methods and derivatives required by each model are available at the declared tier.

- Licensing validation: no component record marked non-redistributable is present in an artifact destined for export or publication. **[C7]**

- Execution validation: external artifacts exist, hashes match, secrets are referenced rather than serialized, and sandbox policies are satisfiable.

### 4.3 Serialization and versioning

Use a canonical human-readable YAML or JSON surface backed by a normative JSON Schema. Define canonical JSON for hashing: sorted keys, normalized numeric representation, explicit units, stable IDs, and no transient runtime fields. Large arrays and model binaries are content-addressed artifacts referenced by URI and cryptographic hash. Every schema release includes forward migrations, golden fixtures, and round-trip tests; no in-place ambiguous migration is allowed.

- Separate files: process.yaml, layout.json, study.yaml, model-lock.json, run-manifest.json, results/ and artifacts/.

- Semantic diff reports added/removed units, rewired streams, changed specs/parameters/models, and downstream invalidations.

- Branching is copy-on-write over immutable revisions. Runs point to a revision and never overwrite prior results.

### 4.4 Interoperability schedule **[C14]**

Interoperability is scheduled, not opportunistic, because each target buys something specific.

| Target | Buys | Milestone | Notes |
| --- | --- | --- | --- |
| SFILES 2.0 | Topology interchange, FAIR flowsheet corpora, agent/ML training data, instant topology comparability | v0.1 | Round-trip test: IR to SFILES to IR preserves topology and unit types; unrepresentable structure is reported, never dropped |
| SSP 2.0 + FMI 3.0 | A standardized system-structure container with layered metadata and digital signatures | v0.3 | Align the run bundle with SSP layered standards rather than inventing a competing container |
| DEXPI 2.0 | PFD/P&ID handover and a standardized unit-operation taxonomy | v0.3 | Lossy import with an explicit capability report |
| CAPE-OPEN thermo | Access to mature property packages | v0.2 | Out-of-process bridge; state the Windows/COM deployment constraint plainly |
| JSON-LD / OntoCAPE-OntoProcess projection | The IR becomes a knowledge-graph citizen | v0.2 | A mapping file and an export. The IR is not built on RDF |

Import/export adapters are lossy only with an explicit capability report, and no adapter may weaken the IR to accommodate a target format.

## 5. Typed model, stream, and unit APIs

### 5.1 Model contract

A model package exposes a manifest plus executable implementations. The manifest is inspectable without importing arbitrary code.

| Contract area | Required declarations |
| --- | --- |
| Identity | name, semantic type, version, license, implementation hash, authorship, citations |
| Interface | typed ports, input/output quantities, dimensions, optionality, multiplicity, component/phase assumptions |
| Mathematics | variables, residual equations or evaluator, conditionals with resolution class, algebraic/dynamic classification |
| Derivatives | analytic/AD/finite-difference availability; Jacobian/JVP/VJP; sparsity; smoothness class; generalized-derivative support where nonsmooth |
| Initialization | defaults, state estimators, staged activation recipe, required upstream information |
| Reformulation | PTC-eligible equation subset with time-constant hints; declared homotopy transformations **[C4]** |
| Validity | hard domain, soft envelope, extrapolation behavior, failure policy |
| Numerics | nominals, scaling hints, bounds, expected stiffness, preferred decomposition, solver capabilities |
| Fidelity & cost | fidelity level, expected runtime/memory, batching, parallelism, cacheability |
| Uncertainty | parameter distributions, predictive uncertainty (conformal where applicable), correlation identifiers, calibration provenance |
| Execution | native, Python/C++ plugin, ONNX, FMU, container, remote service; timeout and reproducibility class |

### 5.2 Core protocol

Conceptual interface (language-neutral): describe(context) to ModelManifest; instantiate(bindings) to ModelInstance; residual(x, context) to ResidualResult; evaluate(inputs, context) to OutputResult for explicit models; jacobian/JVP/VJP where declared; initialize(knowns, context) to InitialGuess; validate(state, context) to ValidationReport; estimate_cost(domain) to CostModel. No model may silently change topology, units, or global tolerances.

### 5.3 Streams

- MaterialStream carries total flow, thermodynamic state, composition, phase policy, component set, and optional phase-resolved state; intensive/extensive distinctions are explicit.

- EnergyStream carries signed duty/power with a declared convention. SignalStream carries nonconserved specifications or controls.

- A stream state is not a bag of properties. It references a state definition (for example T-P-z, P-H-z, or phase-resolved) and property package.

- Connections compile to equality/transform equations and component mappings. Implicit component dropping is forbidden.

### 5.4 v0.0 walking-skeleton unit set **[C15]**

feed, product, mixer, splitter, isothermal flash, heater with duty or outlet-T spec, and a tear. Nothing else. The deliverable is the schema and provenance chain, not the physics.

### 5.5 v0.1 unit library

| Family | Models | Minimum behavior |
| --- | --- | --- |
| Network | feed, product, mixer, splitter, recycle/tear | mass/energy continuity, composition mapping |
| Pressure | pump, valve | pressure change, duty, efficiency, phase checks |
| Thermal | heater/cooler, two-stream heat exchanger | duty/outlet specs; UA or effectiveness option |
| Phase | equilibrium flash | TP, PH, and selected vapor-fraction specifications |
| Phase (cascade) | N-stage flash cascade with interstage flows **[C9]** | exercises tearing, block merge, and EO on a strongly coupled block before a full column exists |
| Reaction | stoichiometric/conversion reactor, equilibrium reactor | element balance, heat effects, extent/conversion semantics |
| Separation | component separator | split specifications and conservation |

### 5.6 v0.2 separation additions **[C9]**

Equilibrium-stage MESH column with configurable specifications, condenser/reboiler options, and at least two solution strategies (an inside-out style scheme and a full-Newton scheme with continuation). ChemSep and DWSIM are the reference implementations; agreement on a defined set of columns is a v0.2 release gate. A rate-based column is explicitly out of scope until v1.

### 5.7 Model replacement

Replacement is allowed when semantic roles and port contracts match, or a declared adapter can prove a mapping. The system compares conserved quantities, thermodynamic requirements, state variables, validity domains, and uncertainty. Replacement creates a new process revision, invalidates dependent results, and optionally initializes the new model from the previous solution.

## 6. Thermodynamics strategy

### 6.1 Architectural position

Thermodynamics is a pluggable, versioned scientific subsystem with a narrow typed interface. The project should not delay its numerical and agent architecture while attempting to reproduce decades of commercial data. Early releases combine a small rigorously validated native package with adapters to mature open implementations.

### 6.2 Property-package contract **[C6]**

The primitive is a **differentiable potential**, not an enumeration of property functions.

- A package declares an ideal-gas reference model and either a residual Helmholtz energy in (T, V, x) or an excess Gibbs energy in (T, P, x), each differentiable to at least second order by the declared mechanism (analytic or AD).

- All thermodynamic properties — enthalpy, entropy, density, heat capacity, fugacity coefficients, partial molar quantities — are **derived accessors** over that potential. A package may override an accessor with a faster analytic implementation only if it also passes an agreement test against the derived form.

- Transport properties (viscosity, thermal conductivity) sit outside the potential and are declared as an independent capability tier with their own derivative provenance.

- Packages that can only supply tabulated or correlation-based properties without consistent derivatives declare capability tier T0 and are excluded from EO paths requiring second derivatives. This is reported before solve, never discovered during it.

Additional required declarations: component registry and identifiers; molecular data provenance and **license tag**; supported phases and state regions; reference-state convention; mixing rules and binary parameters; flash capabilities; smoothness class; uncertainty; thread/process safety.

### 6.3 Flash surface and property cache **[C17]**

- Flash surface: TP, PH, PS, TV, PV, and quality specifications as supported; returns phases, compositions, properties, convergence metadata, and stability indicators.

- Batch evaluation and derivative calls are mandatory interface design points even where initial implementations are scalar.

- A content-addressed property cache keyed by (package hash, spec kind, quantized state, component set, requested derivative order) is part of the property service, not an optimization bolted on later. Cache hits and misses are traced. `property_calls` is a reported benchmark metric.

- Near-critical, phase-appearance, nonphysical input, and flash nonconvergence are typed outcomes, never NaNs without context.

### 6.4 Phase-equilibrium formulation policy **[C5]**

Every property package and every flash-bearing unit model declares which VLE formulation it exposes to the compiler. This is a versioned contract field, not an implementation detail, because it determines the differentiability class of the whole compiled problem.

| Formulation | Behavior across phase boundaries | Derivative class | Required guards |
| --- | --- | --- | --- |
| `PROCEDURAL_INNER` | Inner flash loop; phase set fixed per outer iteration | Outer derivatives via implicit function theorem or finite difference | Phase-set change between outer iterations is an event; cycling is detected and bounded |
| `COMPLEMENTARITY` | Vanishing and reappearing phases handled in one square system | Piecewise smooth; needs an NCP-capable solver or a penalty reformulation | **Trivial-solution rejection via embedded bubble/dew checks is mandatory** |
| `SMOOTHED` | Smooth-max complementarity with parameter epsilon | Smooth | Epsilon must be driven to a declared floor under continuation; the final epsilon appears in the certificate |
| `NONSMOOTH_GENERALIZED` | Nonsmooth inside-out style with lexicographic/generalized derivatives | Generalized derivatives | Solver must declare nonsmooth support; otherwise reject at compile |

Rules:

- v0.1 must ship at least one formulation that survives phase disappearance on the benchmark set, and the choice must be visible in the SolutionCertificate.

- Mixing formulations within one EO block is allowed only when the block's declared smoothness class is the weakest of its members, and the solver honors that class.

- A converged result obtained under `SMOOTHED` with epsilon above the declared floor is reported as a *relaxed* certification, not a full one.

### 6.5 Delivery sequence

1. Native ideal-gas/ideal-liquid and Raoult-law package expressed as a potential, with analytic derivatives, for solver development.
2. Adapter to one permissively licensed open property library for pure-fluid and common mixture properties; pin versions, build a conformance suite.
3. Cubic EOS (PR/SRK) via the residual-Helmholtz route with transparent mixing rules; derivatives verified against an AD-based reference implementation (teqp / FeOs / Clapeyron.jl) rather than only against finite differences.
4. Activity-coefficient models (NRTL/UNIQUAC) as excess-Gibbs potentials, driven by benchmark demand.
5. Adapter to DWSIM-compatible or CAPE-OPEN property packages where deployment permits; out of process when isolation is needed.
6. A curated, provenance-rich, license-tagged parameter store only after interfaces and validation workflows stabilize.

### 6.6 Data licensing policy **[C7]**

- Every parameter record carries source citation, license, and a `redistributable` flag.
- The packaged distribution contains only redistributable records. Non-redistributable data is supported through a documented user-supplied ingestion path that records provenance and never ships upstream.
- Documentation states plainly which components and property methods are validated, and never implies coverage the data licence does not permit.
- Export and publish operations refuse to emit non-redistributable records and say why.

> **Thermodynamic rule** — A converged flowsheet with inconsistent reference states or unsupported extrapolation is a failed engineering result. Compatibility checks occur before solve, and reference-state transformations are explicit.

## 7. Numerical core: solver orchestration

### 7.1 Objective

The solver is a deterministic policy engine over a portfolio of transparent numerical mechanisms. It analyzes the process and equation graphs, proposes and scores solve plans, executes them with checkpoints, observes progress, changes strategy under explicit rules, and emits a complete trace. The default policy is reproducible; optional learned ranking may advise but may not conceal or mutate the trusted path.

### 7.2 Solve pipeline

| Stage | Required work | Artifacts and decisions |
| --- | --- | --- |
| 0. Compile | Resolve models/properties, normalize units, flatten active equations, classify conditionals, apply bounds/specs | CompiledProblem, source map, capability report, smoothness class |
| 1. Graph analysis | Process DAG/cycles; equation-variable bipartite graph; Dulmage–Mendelsohn; SCCs; block triangular form; sparsity; cut candidates | GraphReport, structural hashes, **largest_block_fraction** **[C3]** |
| 2. Structural decomposition | DOF and matching; partition weak/strong blocks; propose tears; identify algebraic loops and singularity risk | DecompositionPlan candidates with scores |
| 3. Initialization | Defaults, bounds projection, property-state estimates, unit-local analytic/heuristic initialization, staged equation activation | InitialState plus confidence and violations |
| 4. Sequential solve | Topological unit execution; Wegstein/Aitken/Anderson recycle acceleration; bounded damping; tear convergence | SM trace, unit failures, recycle metrics |
| 5. Coupled EO solve | Assemble strongly coupled blocks or full problem; sparse Newton/trust-region/line-search methods | Block/full residual and step trace |
| 6a. Parameter continuation | Ramp feed, nonideality, reaction, heat coupling, recycle closure, smoothing epsilon, or specification severity; adaptive step and rollback | Homotopy schedule and checkpoints |
| 6b. Pseudo-transient continuation **[C4]** | Reformulate the declared algebraic subset as ODEs in fictitious time with model-supplied or auto-derived time constants; integrate to steady state with a variable-step DAE integrator | PTC trace, time-constant selection rationale, steady-state residual history |
| 7. Scaling | Variable/residual/Jacobian scaling; refresh only under defined triggers; detect extreme condition estimates | Scale factors, rationale, conditioning diagnostics |
| 8. Fallback | Switch tear set, block merge/split, initialization recipe, EO globalization, PTC reformulation, property formulation, or safe finite differences | Attempt tree and terminal diagnosis |
| 9. Certify | Check residuals, bounds, conservation, property consistency, complementarity/active set, smoothing floor, and requested tolerances | SolutionCertificate or FailureBundle |

Stages 4, 5, 6a and 6b are peers selected by policy, not a fixed waterfall. The plan records why each was chosen.

### 7.3 Graph and structural algorithms **[C3]**

- Maintain both a process connectivity multigraph and an equation-variable incidence bipartite graph; do not infer numerical coupling solely from unit topology.

- **Dulmage–Mendelsohn decomposition is primarily a diagnostic.** Its first-class output is the structurally over-determined and under-determined subsets, mapped back to IR objects, which is what makes DOF repair actionable for a human or an agent. Treat any performance benefit as secondary.

- **Do not assume block triangularization decomposes the problem.** For flowsheets with recycle loops or countercurrent contacting, BTF commonly yields one diagonal block containing nearly all variables. The runtime must compute and report `largest_block_fraction`; when it exceeds a configured threshold the plan scorer must not credit decomposition benefit, and must instead consider tearing within the block, phenomena-based partitioning, or PTC.

- Use strongly connected components and block triangularization to derive ordered blocks where they genuinely exist. Record stable tie-breaking so identical inputs produce identical plans. **[C18]**

- Score tear candidates using cycle coverage, estimated sensitivity/gain, variable dimension, physical bounds, derivative availability, and previous run history.

- Permit phenomenon-level partitions (phase equilibrium, reaction, energy, pressure) when declared coupling supports them; unit-operation boundaries are not privileged.

- Hash structural patterns separately from numerical values so nearby scenarios can reuse symbolic analysis safely.

- Adopt the established Jacobian-based diagnostic set as *acceptance* checks rather than reinventing it: condition-number estimation, detection of near-parallel constraints and irreducible degenerate sets, extreme Jacobian entry detection, and badly-scaled variable/constraint reporting.

### 7.4 Initialization

- Layered sources: user-provided state > warm start from compatible revision > unit initializer > upstream propagation > nominal/bounds midpoint > explicit failure.

- Each guess carries provenance and confidence. Projection onto bounds is logged; mass fractions are normalized only under an explicit repair policy.

- Initialize easy physics first: ideal properties before nonideal; zero/low reaction before full kinetics; open recycles before closure; fixed heat duties before tight design specs.

- Unit initialization must be testable independently and must not alter user specifications.

- Persist successful initialization recipes keyed by structural hash and operating-region signature, while treating them as hints rather than unreviewed truth.

### 7.5 Sequential-modular execution

Sequential execution is preferred for acyclic regions and weak recycles with robust explicit unit evaluators. Recycle convergence measures scaled tear residuals and physical violations. Acceleration methods have safeguarded acceptance: Wegstein bounds, Aitken, and Anderson acceleration with a declared depth, regularized least-squares coefficients, and a safeguard that reverts to damped substitution when the coefficient norm or residual growth exceeds a threshold. Anderson can stabilize non-contractive iterations, which makes an unsafeguarded implementation dangerous rather than merely slow. Divergence, oscillation, stagnation, and invalid property calls trigger rollback and policy escalation.

### 7.6 Equation-oriented execution

- Compile residual and derivative evaluators with source maps. Assemble sparse Jacobians by analytic/AD blocks and audited finite differences only where declared.

- Primary nonlinear strategy: damped sparse Newton with line search or trust region; expose linear solve, factorization, pivot, regularization, and step acceptance statistics.

- Default sparse LU is KLU: license-compatible, and well matched to the unsymmetric, highly sparse, structurally-repeated systems flowsheets produce, with symbolic analysis reused across iterations and across nearby scenarios keyed by structural hash. **[C1] [C17]**

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

Homotopies are typed transformations, not arbitrary equation edits. Each exposes a parameter in [0,1], an easy endpoint, target endpoint, admissibility checks, and rollback. The orchestrator selects from model-declared and generic transformations, adapts step size based on nonlinear effort and curvature, and checkpoints accepted states.

- Recycle closure; feed rate/composition/temperature ramp; reaction extent or kinetic severity; heat-transfer coupling; pressure drop; phase nonideality; complementarity smoothing epsilon; specification tightening; surrogate-to-first-principles blending.

- Known limitation to document and detect: when the start point and the solution lie on separate homotopy branches, monotone parameter stepping can miss the solution entirely. Report branch-loss suspicion (turning point detected, parameter unable to advance) rather than reporting a generic step failure.

- Pseudo-arclength continuation is a later capability for folds; v0.x may use monotone adaptive parameter stepping with the above detection.

- Failure at a step reduces step size; repeated failure selects a different path or returns the closest certified checkpoint.

### 7.9 Pseudo-transient continuation **[C4]**

PTC is a distinct mechanism class and gets its own contract.

- A model declares which of its algebraic equations may be reformulated as first-order ODEs in a fictitious time, and supplies time-constant hints. The reformulation must be **statically equivalent**: the steady state of the PTC system is exactly the solution of the original algebraic system. This equivalence is a required unit test for every PTC-eligible model.

- The runtime chooses time constants from model hints, and where absent, derives them from scaled Jacobian diagonal magnitudes; the choice and its rationale enter the trace.

- Integration uses a variable-step implicit DAE integrator. Termination is on a scaled steady-state residual criterion, and the resulting state is then handed to a Newton polish step that must converge; PTC alone never issues a certificate.

- PTC is a first-class alternative to stage 5 when: initialization confidence is low, the largest structural block is a large fraction of the problem, or an EO attempt failed globalization. It is not a fallback of last resort.

- Because PTC changes the mathematical path but not the answer, PTC-obtained solutions carry the same certification class as Newton-obtained solutions, with the path recorded.

### 7.10 Fallback policy and budgets

Fallbacks form a bounded attempt tree. Every edge has a trigger, precondition, cost class, and maximum count. Global wall-time, property-call, external-model, and factorization budgets prevent uncontrolled search. The terminal outcome names exhausted strategies and the best certified partial state.

| Observed condition | Candidate response |
| --- | --- |
| Structural mismatch | Stop before numerical solve; identify unmatched variables/equations and minimal conflicting spec set via Dulmage–Mendelsohn. |
| Bad initial property state | Switch state-variable formulation, project within declared domain, or request missing initialization. |
| Recycle oscillation/divergence | Reduce damping, change or safeguard acceleration, choose alternate tear, or merge recycle region into an EO or PTC block. |
| EO line search failure | Rescale, trust-region retry, regularize linear system, activate homotopy, switch to PTC, or change block partition. |
| Singular/ill-conditioned Jacobian | Rank diagnostics, identify irreducible degenerate sets and redundant equations/fixed variables, rescale, or use a safeguarded least-squares step. |
| Giant single block after BTF | Do not report decomposition benefit; escalate to tearing within the block, phenomena partitioning, or PTC. **[C3]** |
| Phase-boundary nonsmoothness | Switch VLE formulation per §6.4, guard the property call, continue on smoothing epsilon, or take a complementarity-capable path. |
| Trivial complementarity solution | Reject via bubble/dew embedding and restart from a corrected phase assignment. **[C5]** |
| Conditional cycling | Detect repeated active-set states, bound the discrete loop, and report the cycling set. **[C8]** |
| Surrogate validity violation | Reject, constrain optimization, switch to parent model, or schedule refinement; never silently extrapolate. |
| External model timeout | Use cached certified result if exact inputs/hash match, retry within policy, or fall back to declared lower fidelity. |

### 7.11 Conditional and discrete structure **[C8]**

Every conditional in a model is classified at compile time into exactly one resolution class:

| Class | Meaning | Solver obligation |
| --- | --- | --- |
| `COMPLEMENTARITY` | Rewritten as a complementarity system | Solver must be NCP-capable or apply a declared penalty reformulation |
| `SMOOTHED` | Replaced by a smooth approximation with parameter epsilon | Epsilon appears in the plan, is driven under continuation to a declared floor, and is reported in the certificate |
| `OUTER_DISCRETE` | Resolved by an outer loop over active sets | Loop is bounded, active-set states are hashed, cycling is detected and reported as `CONDITIONAL_CYCLING` |
| `FIXED_AT_COMPILE` | Condition is decided from the IR and fixed for the run | The decision and its basis are recorded; a violated fixed condition at the solution is a certification failure |

Unclassified conditionals fail validation before any numerical work. The compiled problem's overall smoothness class is the weakest class present, and solvers that cannot honor it are rejected at compile with a capability report rather than failing mysteriously at iteration 40.

### 7.12 Failure taxonomy and observability

- STRUCTURAL_UNDER/OVERDETERMINED, STRUCTURAL_SINGULAR_RISK, SPEC_CONFLICT, IRREDUCIBLE_DEGENERATE_SET.

- PROPERTY_DOMAIN, FLASH_NONCONVERGENCE, PHASE_INSTABILITY, REFERENCE_STATE_MISMATCH, TRIVIAL_VLE_SOLUTION.

- MODEL_DOMAIN, CONSERVATION_VIOLATION, EXTERNAL_TIMEOUT/CRASH, DERIVATIVE_MISMATCH, CAPABILITY_TIER_INSUFFICIENT.

- INITIALIZATION_INFEASIBLE, RECYCLE_DIVERGENCE/OSCILLATION/STAGNATION.

- JACOBIAN_SINGULAR/ILL_CONDITIONED, LINEAR_SOLVE_FAILURE, GLOBALIZATION_FAILURE, ITERATION/BUDGET_EXHAUSTED.

- HOMOTOPY_BRANCH_LOST, PTC_STEADY_STATE_NOT_REACHED, SMOOTHING_FLOOR_NOT_REACHED, CONDITIONAL_CYCLING.

- SURROGATE_OUT_OF_DOMAIN, CONFORMAL_COVERAGE_VIOLATED, UNCERTAINTY_THRESHOLD_EXCEEDED, OPTIMIZATION_INFEASIBLE.

- DATA_LICENSE_BLOCKED.

The FailureBundle contains category, severity, causal chain, implicated IR objects/equations/variables, raw evidence, attempted remedies, best state, reproducible replay command, and ranked next actions. Explanation text is generated from this structure and is never the sole record.

### 7.13 Reproducibility classes

| Class | Guarantee |
| --- | --- |
| D0 Structural | Bitwise-identical canonical IR, validation, graph decomposition, and plan selection on supported platforms. Enforced by the discipline in §2 and gated by a cross-platform structural-hash equality job. **[C18]** |
| D1 Numerical deterministic | Same binaries, threads, seed, hardware class, and inputs yield identical trace and outputs within declared bitwise/tolerance policy. Thread counts for BLAS and the linear solver are pinned in the run manifest. |
| D2 Numerically equivalent | Parallel/GPU/external execution may vary; certified outputs remain within specified tolerances and event differences are recorded. |
| D3 External nonreproducible | Provider cannot guarantee replay; inputs, outputs, hashes, environment, and uncertainty are preserved and prominently labeled. |

## 8. Multi-fidelity and external models

### 8.1 Fidelity ladder

A conceptual unit can own a ModelFamily: screening algebraic model, rigorous first-principles model, PyMRM distributed reactor, CFD/particle experiment, and reduced-order or surrogate models derived from high-fidelity data. The family shares semantic ports and conserved quantities while models declare distinct states, costs, validity, and uncertainty.

### 8.2 PyMRM and external experiment integration

- PyMRM adapter maps process stream states and parameters to reactor boundary conditions, executes out of process, returns outlet/integral quantities plus convergence and discretization evidence, and optionally provides sensitivities. Because PyMRM is Python and in-house, it is the right first adapter: the interface can be co-designed rather than reverse-engineered.

- CFD/particle workflows are asynchronous experiment providers, not synchronous residual calls by default. Requests are content-addressed, queued, budgeted, and traced.

- A design-of-experiments service samples the process-relevant domain; data artifacts record process revision, model hash, mesh/numerical settings, and failed samples. Failed samples are data, not noise, and are retained.

- Surrogate training records splits, transforms, metrics, calibration, uncertainty method, derivative tests, and applicability domain. ONNX or another portable form may be an execution artifact, never the only scientific record.

- The process solver enforces validity. Optimizers receive domain constraints or uncertainty penalties; extrapolation requires an explicit policy and emits a warning or failure.

### 8.3 Surrogate validity and uncertainty **[C10]**

- **Default uncertainty mechanism: split-conformal prediction.** It provides distribution-free finite-sample marginal coverage independent of surrogate architecture (polynomial, GP, neural, operator), calibrates in seconds, and yields a release-gate-shaped number: empirical coverage on a held-out set.

- **Domain membership is a separate check** from uncertainty width: a convex-hull, density-ratio, or nearest-neighbour-distance test on the training inputs. A prediction can be in-domain with wide intervals, or out-of-domain with deceptively narrow ones; the system reports both.

- A surrogate's manifest declares target coverage, achieved coverage, the calibration set hash, and the domain test. `CONFORMAL_COVERAGE_VIOLATED` is a typed failure when re-validation on new truth-model samples falls below target.

- Derivative surrogates are validated separately from value surrogates. A surrogate whose values are accurate and whose gradients are not is unusable for gradient-based optimization, and the manifest must say which it supports.

### 8.4 Fidelity-aware optimization **[C11]**

- **Primary strategy: trust-region filter (TRF).** The flowsheet is the glass box; expensive models are the black boxes. TRF alternates optimization over local surrogates with intermittent truth-model sampling, managed by a filter balancing objective and feasibility, and converges to a stationary point of the *high-fidelity* problem. This is the defensible version of "progressive fidelity" and replaces v1.0's informal expected-value scheduling inside the optimization loop.

- Implement the basic Eason–Biegler TRF first; Hessian-informed and efficiency-improved variants are later work behind the same interface.

- **Experiment selection** (which high-fidelity run to buy next, at which fidelity) is a separate problem, addressed by multi-fidelity Bayesian optimization and expected-information-gain acquisition, with sampling cost in the acquisition. This is the correct home for v1.0's "expected value of added fidelity" idea.

- Every fidelity decision is recorded with its rationale, cost estimate, and realized cost, so the schedule can be audited and replayed.

### 8.5 Adaptive refinement loop

1. Solve and optimize with inexpensive models.
2. Rank model inadequacy using objective sensitivity times epistemic uncertainty times decision proximity.
3. Select the next high-fidelity experiment by multi-fidelity acquisition against compute cost and schedule budget.
4. Run targeted higher-fidelity experiments, update calibration/surrogate, re-calibrate conformal intervals, and validate independently.
5. Replace the model in a branch, warm-start, re-optimize under TRF, and compare topology, operating point, economics, safety constraints, and uncertainty.
6. Stop when the decision is stable or refinement budget is exhausted; report unresolved decision risk.

## 9. Agent-native API and safety model

### 9.1 API principles

- Expose process semantics, not GUI coordinates or fragile object paths.

- Separate read, propose, validate, commit, execute, and publish permissions.

- Every mutating call accepts expected_revision and idempotency_key and returns a semantic diff.

- Long operations are jobs with events, budgets, cancellation, checkpoints, and artifact references.

- Tool schemas use stable IDs, typed quantities with units, explicit tolerances, and bounded result summaries; large traces remain queryable artifacts.

- Agent-generated explanations are clearly separated from deterministic validation and solver evidence.

- **Certification policy, tolerances, budgets, and validity enforcement are not agent-writable.** An agent may request a different tolerance as a specification; it may not disable a check. **[C12]**

### 9.2 Requirements derived from observed agent failure modes **[C12]**

The published failure modes of LLM agents driving process simulators translate directly into API obligations.

| Observed failure mode | API obligation |
| --- | --- |
| Hallucinated property values and parameter drift | Property and parameter reads always return provenance and license tag; agents cannot write a property value without a source field; a proposed value outside the package's validity domain is rejected at propose time, not at solve time |
| Context overflow on large flowsheets | Every inspect tool takes a scope and a token budget and returns a bounded, deterministic summary with a continuation handle. There is no tool that returns "the whole flowsheet" |
| Cannot validate feasibility without running the simulator | `validate_change` is cheap, side-effect free, and returns structural, dimensional, and DOF verdicts before any solve is attempted |
| Poor recovery from convergence failure | `explain_failure_evidence` returns the FailureBundle's ranked next actions as *executable tool calls with arguments*, not prose |
| Untraceable cost | Every tool declares an expected cost class; job budgets are enforced server-side and reported in the event stream |

### 9.3 Transport bindings **[C12]**

- The canonical surface is the transactional HTTP API. The MCP server is a thin, generated binding over it, so the tool surface cannot drift from the API.

- MCP tool descriptions are treated as a maintained artifact with their own review: unambiguous names, explicit units in schemas, stated preconditions, and no overlapping tools that an agent must disambiguate by guessing.

- The Python SDK and CLI bind the same API. No capability exists in one client only.

### 9.4 Minimum tool surface

| Group | Representative operations |
| --- | --- |
| Inspect | get_process_summary, list_models, inspect_unit/stream/equations, get_dof_report, get_run_trace, explain_failure_evidence |
| Edit transaction | begin_change, add_unit, connect_stream, set_specification, replace_model, set_property_package, preview_diff, validate_change, commit/rollback |
| Solve | compile, initialize, solve, resume_from_checkpoint, compare_solve_plans, certify_solution |
| Study | create_scenario, sweep, sensitivity, estimate_parameters, optimize, propose_topology, compare_scenarios |
| Fidelity | assess_model_risk, plan_experiments, run_external_model, train_surrogate, validate_surrogate, promote_model |
| Provenance | branch, tag, lock_environment, export_run_bundle, reproduce_run |

### 9.5 Threat model **[C12]**

Two distinct threat surfaces, and v1.0 addressed only the first.

**Code execution.** Untrusted models run out of process or in containers with resource limits, artifact allowlists, secret isolation, signed manifests, and network policy.

**Prompt injection through data.** Model manifests, component names, annotations, citations, comments, external model stdout, and imported flowsheets are attacker-controllable text that reaches an LLM's context. Mitigations:

- All such text is length-bounded and rendered inside explicit provenance-labelled envelopes that mark it as untrusted data.
- The agent's authorization comes from the permission system and the transaction API, never from text content. No instruction found in data can widen permissions, change budgets, or authorize a commit.
- Imported artifacts from third parties are quarantined: they can be inspected and validated, but committing them to a process requires an explicit human or elevated-permission approval step.
- A tool result never carries an unbounded verbatim blob from an external provider into the model's context; blobs become artifacts with hashes.

### 9.6 Agent evaluation **[C12]**

Two tiers, because internal tasks alone are not falsifiable.

**External comparability.** Report results on at least one published third-party benchmark for agentic process simulation (for example the OpenIDAES-450 corpus, whose task taxonomy — unit selection, topology construction, property-package assignment, specification closure, initialization, recycle handling, solver diagnosis, optimization — matches this platform's tool surface closely). Where the platform cannot express a benchmark task, say so; do not silently drop cases.

**Project-owned tasks.** Published, versioned, with seeds:

- Construct a flowsheet from a structured brief without unit/connection errors.
- Repair an under/overspecified model using the DOF report and minimal changes.
- Diagnose recycle divergence from evidence and select a justified solve action.
- Replace a reactor model while preserving semantic contracts and documenting invalidated results.
- Optimize a design without surrogate-domain violations and explain active constraints.
- Reproduce a prior result from a run bundle and detect an intentionally changed dependency.
- **Resist an injected instruction embedded in an imported model manifest.** **[C12]**

The invariant that matters more than any score: the agent must never commit an invalid process, and must never obtain a certification it did not earn.

## 10. Web GUI role

The GUI is a human workbench and observability client, not the source of truth. It must use public application APIs used by agents and scripts. No capability may exist only as a hidden front-end mutation.

- Flowsheet canvas with typed ports, component/phase compatibility feedback, and semantic rather than decorative connections.

- Inspector for model contract, equations, variables, specs, units, bounds, provenance, uncertainty, and validity envelope.

- DOF and structural view: unmatched variables/equations from the Dulmage–Mendelsohn report, SCC/block view with `largest_block_fraction` made visible, tear candidates, and dependency highlighting.

- Solve cockpit: plan stages, live residual norms, raw/scaled residual heatmap, recycle history, homotopy parameter, PTC fictitious-time trace, scaling changes, checkpoints, and fallback tree.

- Scenario workspace: immutable branches, semantic diffs, result comparison, trade-off plots, and decision history.

- Multi-fidelity panel: model family, evidence lineage, training domain, conformal coverage, compute cost, and replacement preview.

- Agent activity timeline showing proposed actions, deterministic validation, commits, jobs, permissions, and rollback points.

- Education mode that reveals equation source and numerical transformations without requiring source-code navigation.

## 11. Study, optimization, and synthesis architecture

- Studies reference immutable process revisions and define decisions, objectives, constraints, scenarios, sampling/optimization method, budgets, and certification rules.

- Expose derivative-aware local NLP first, via the Pyomo/Ipopt export path where that is the fastest route to a credible result. Add derivative-free and mixed-integer methods as plugins; never conceal solver choice or stopping criteria.

- Trust-region filter is the designated strategy for problems containing expensive or surrogate submodels. **[C11]**

- Process synthesis represents superstructures or typed graph rewrite proposals. Every topology candidate passes semantic/DOF validation before simulation. SFILES 2.0 is the interchange form for candidate topologies. **[C14]**

- Separate feasibility restoration from economic optimization; retain infeasible candidates and reasons for learning and debugging.

- TEA/LCA are modular assessment models with currency year, geography, price, emission-factor, and uncertainty provenance.

- Optimization outputs include primal feasibility, active constraints, sensitivities when reliable, domain checks, multi-start evidence, and model/solver limitations.

## 12. Testing and validation strategy

### 12.1 Test hierarchy

| Level | Purpose | Required examples |
| --- | --- | --- |
| L0 Mathematical kernels | Prove local numerical correctness | units, graph algorithms, matching/SCC/BTF/DM, scaling, line search, continuation step control, PTC static equivalence |
| L1 Model contracts | Verify each unit/property/model independently | mass/energy/element balances, limiting cases, derivative checks, invalid domains, potential-vs-accessor agreement |
| L2 Coupled subsystems | Exercise known numerical mechanisms | flash-heater, reactor-cooler, heat integration, one/two recycles, phase appearance, flash cascade |
| L3 Flowsheet regressions | End-to-end expected results and traces | canonical process cases, perturbed initial guesses/specs, warm starts |
| L4 Differential validation | Compare independent simulators/implementations | DWSIM, IDAES, ChemSep (columns), BioSTEAM (conceptual/TEA), CoolProp/thermo/Clapeyron/teqp/FeOs (properties and exact derivatives) |
| L5 Metamorphic/property tests | Test invariants without a single oracle | unit conversion, stream relabeling, split/recombine, component permutation, scaling invariance, SFILES round-trip |
| L6 Robustness campaigns | Measure basins and failure quality | Latin-hypercube initial guesses, parameter perturbations, forced bad scaling, injected property failures |
| L7 Agent/API tests | Ensure safe autonomous operation | transaction conflicts, invalid edits, idempotency, budget/cancel, evidence-grounded diagnosis, prompt-injection resistance |
| L8 Performance/reproducibility | Prevent degradation | compile/solve time, allocations, property calls, trace determinism, cross-platform structural-hash equality |
| L9 Supply chain and licensing | Prevent legal and provenance defects **[C1] [C7]** | dependency license scan, no-GPL-in-default-path check, non-redistributable data cannot reach an export artifact |

### 12.2 Numerical test requirements

- Every analytic or AD derivative implementation is compared with complex-step where valid and high-quality finite differences over nominal, boundary-near, and randomized states. **Where an AD-based open EOS reference exists, thermodynamic derivatives are additionally compared against it**, since finite differences near a phase boundary are themselves unreliable. **[C6]**

- Every PTC-eligible model has a static-equivalence test proving its ODE steady state equals its algebraic solution. **[C4]**

- Every VLE formulation has phase-disappearance, phase-reappearance, and trivial-solution-rejection tests. **[C5]**

- All conservation models have symbolic or numerical balance tests. Elemental balance is checked for reaction models independent of convergence.

- Golden solution fixtures store inputs, expected physical outputs, tolerances, and provenance, not opaque serialized solver objects.

- Random/property-based tests have recorded seeds and minimized failing cases.

- Fallback paths are fault-injected deliberately; untested recovery code cannot be enabled by default.

- Tolerance tests distinguish absolute, relative, and physically meaningful engineering tolerances. No single blanket rule.

### 12.3 Benchmark reporting methodology **[C13]**

Fixed before results are collected, because otherwise the numbers are unfalsifiable.

- **Definition of "solved":** a SolutionCertificate at the declared class within the stated budget. A relaxed certification (e.g. smoothing floor not reached) is reported in a separate column, never counted as solved.

- **Primary comparison form: Dolan–Moré performance profiles** over the benchmark corpus, for each of wall time, Newton iterations, factorizations, and property calls. Profiles summarize robustness and efficiency together and prevent a handful of easy or pathological cases from dominating.

- **Secondary summary: shifted geometric means** with a stated shift, plus the raw per-case table.

- **Robustness ensembles** are reported as success fraction with a confidence interval over a published seed set, with the budget stated; never as a single curated run.

- **Cross-tool comparisons** carry a per-case verdict of AGREE / DISAGREE_EXPLAINED / **NOT_COMPARABLE**. A case whose model semantics differ materially between tools is NOT_COMPARABLE and is reported as such rather than reconciled by adjusting one side until it matches.

- Every published number carries: corpus version, solver policy version, dependency lock hash, hardware class, thread pinning, and seed set.

### 12.4 Benchmark suite

| Tier | Cases | What it stresses |
| --- | --- | --- |
| A: kernels | scalar nonlinear roots; sparse block systems; ill-scaled networks; rank-deficient systems | globalization, scaling, diagnostics, structural analysis |
| B: thermo | ideal and nonideal TP/PH flashes; near phase boundary; dew/bubble; phase disappearance; reference-state checks; derivative agreement with AD references | property correctness, derivatives, typed failures |
| C: units | pump, valve, heater, HX, flash, conversion/equilibrium reactor, mixer/splitter | unit contracts, balances, limiting cases |
| D: networks | single recycle, nested recycles, heat/mass coupled recycle, purge, design spec, flash cascade | tearing, acceleration, EO block merge, PTC, homotopy, largest-block behavior |
| E: processes | flash train; reactor-separator-recycle; heat-integrated process; MESH distillation column | end-to-end results, robustness, optimization |
| F: multi-fidelity | simple reactor to PyMRM to surrogate; external failure and OOD scenarios; TRF optimization with an embedded expensive model | replacement, lineage, conformal coverage, asynchronous orchestration, TRF convergence |
| G: agent | build, diagnose, modify, optimize, refine, reproduce, resist injection | semantic tools, safety, auditability |

### 12.5 Cross-simulator validation protocol

- Use at least two independent open reference implementations whenever the physics overlaps: DWSIM and IDAES for flowsheets; **ChemSep for columns**; BioSTEAM for conceptual/TEA cases; and independent property libraries (CoolProp, thermo, Clapeyron.jl, teqp, FeOs) or published data for thermodynamics.

- Publish exact component data, property methods, reference states, unit conventions, tolerances, and solver settings. A comparison is invalid when model definitions differ materially, and is labelled NOT_COMPARABLE.

- Compare conserved flows, T/P, phase fractions/compositions, duties/work, reaction extent/conversion, objectives, and sensitivities where available.

- Triangulate disagreements: conservation audit, then property-level comparison, then unit-level comparison, then equation/solver comparison. Majority agreement is not proof.

- Pin reference versions in containers or lockfiles and archive input artifacts. License constraints are documented.

- Include nonconvergence and invalid-domain cases. A useful simulator must correctly refuse bad problems and diagnose them.

### 12.6 Validation criteria

| Criterion | Release-gate definition |
| --- | --- |
| Physical correctness | All certified solutions satisfy case-specific material, element, energy, bound, phase, and specification tolerances. |
| Reference agreement | For shared model definitions, key outputs meet predefined per-variable engineering tolerances; discrepancies have reviewed explanations; NOT_COMPARABLE cases are enumerated. |
| Robustness | Target success fraction, reported with performance profiles, is met over a published ensemble within fixed budgets. |
| Derivative quality | Declared derivatives pass numerical checks, AD-reference comparison where available, and optimization sensitivity checks. |
| Surrogate coverage | Every promoted surrogate meets its declared conformal coverage on an independent held-out set. **[C10]** |
| Diagnostic quality | Injected failures map to the correct taxonomy and identify implicated objects with actionable evidence. |
| Reproducibility | Run bundle reproduces certification class and numerical tolerances on supported environments; structural hashes match across platforms. |
| Licensing | Dependency and data license gates pass; no non-redistributable record is present in any published artifact. **[C1] [C7]** |
| Performance | No statistically significant regression beyond approved thresholds on versioned benchmark hardware. |

## 13. Phased roadmap **[C15]**

### 13.0 Staffing assumption

This roadmap assumes a core of roughly two to four full-time-equivalent engineers with a numerical-methods lead and a process-modeling lead, augmented by coding agents for scaffolding, test generation, adapter work, and documentation. State the actual assumption in the implementation plan. If the real figure is materially lower, the correct response is to cut breadth — fewer unit models, fewer property packages, fewer benchmark tiers — and **not** to cut the transparency, certification, or provenance machinery, which is the differentiator.

| Phase | Duration guide | Outcome | Exit focus |
| --- | --- | --- | --- |
| 0 — Foundations | 3–4 weeks | ADRs (license, CompiledProblem backend, IR schema, VLE formulation), units, quantity semantics, provenance schema, benchmark definitions, CI and packaging, license gates | Architecture can be falsified with executable fixtures before broad modeling |
| **v0.0 — Walking skeleton** | **4–6 weeks** | 3 components; ideal thermo as a potential; mixer/splitter/flash/heater; one recycle with one tear; one damped Newton; complete trace, SolutionCertificate, FailureBundle, RunManifest, replay; one CLI; golden fixtures | **The vertical slice works end to end and the schemas are proven under real use before physics breadth begins** |
| v0.1 — Transparent kernel | +3–4 months | Process IR with migrations and semantic diff, native thermo with verified derivatives, unit library of §5.5, DM/graph/DOF/decomposition, layered initialization, SM + EO + PTC orchestration, scaling, bounded fallbacks, SFILES export, CLI/Python SDK | Small steady-state flowsheets solve reproducibly with inspectable traces and strong tests |
| v0.2 — Agent & multi-fidelity | +4–5 months | Transactional service/API, MCP binding, agent tools, web diagnostic shell, open thermo adapters, MESH column, PyMRM adapter, surrogate lifecycle with conformal validity, study runtime with TRF | Agent completes a reactor-separator-recycle refinement workflow safely |
| v0.3–0.9 — Breadth & hardening | ongoing | Richer thermo/units, optimization, synthesis prototypes, performance, SSP/DEXPI/CAPE-OPEN interop, security, docs, governance | Benchmark coverage and contributor ecosystem mature without architectural erosion |
| v1 — Research-grade platform | — | Stable public contracts, validated benchmark suite, full web workbench, supported deployments, governance | Independent users reproduce published results and extend models without core forks |

### 13.1 Workstream ordering

- Lock semantics, invariants, benchmark definitions, and observability before optimizing performance.

- Prove the vertical slice (v0.0) before broadening horizontally. A schema defect found at v0.2 costs an order of magnitude more than the same defect found at v0.0.

- Build graph/structural kernels and tiny synthetic models before flowsheet breadth.

- Implement native ideal thermodynamics as a differentiable potential to isolate solver development; add external property adapters only after conformance contracts exist.

- Ship headless solve and replay before the GUI; ship agent transactions before ambitious autonomous design.

- Introduce PyMRM integration before asynchronous CFD orchestration; establish data/provenance discipline at the smaller scale.

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
| /packages/thermo | Potential-based property interfaces, native ideal package, adapters, property cache, conformance suite |
| /packages/graph | Process/equation graphs, matching, DM/SCC/BTF, tearing and DOF diagnostics |
| /packages/compile | CompiledProblem interface, backends, source maps, PTC reformulation, conditional classification |
| /packages/numerics | Sparse problem interface, nonlinear methods, scaling, continuation, PTC integration, linear-solver adapters |
| /packages/orchestrator | Solve policies, attempt tree, checkpoints, events, certification, replay |
| /packages/adapters | PyMRM, external jobs, FMU/ONNX/container/remote adapters |
| /packages/interop | SFILES 2.0, SSP/FMI, DEXPI, CAPE-OPEN bridge, JSON-LD projection |
| /packages/studies | Sensitivity, estimation, UQ, conformal calibration, optimization, TRF, synthesis, fidelity planning |
| /services/api, /clients/python, /clients/cli, /clients/mcp | Transactional application service and headless clients |
| /apps/web | Flowsheet and diagnostics workbench; contains no private simulation logic |
| /benchmarks | Case definitions, reference adapters, expected metrics, performance-profile tooling, reports, version pins |
| /tests | Cross-package integration, robustness, fault injection, agent, injection-resistance and reproducibility tests |
| /examples | Minimal, tutorial, and north-star multi-fidelity examples |

## 15. Engineering standards

- Specification first: public behavior and invariants are documented before implementation; important choices receive ADRs.

- Strict typing and schema validation at boundaries; dimensions are types or validated quantity objects, not comments.

- Pure/immutable domain operations where practical; explicit execution contexts and dependency injection; no hidden singletons.

- Public APIs use semantic versioning. Schema migrations and model compatibility rules are tested across supported versions.

- Formatting, linting, static typing, unit tests, contract tests, documentation examples, security scanning, **dependency and data license scanning**, and benchmark smoke tests run in CI.

- Core numerical changes require derivation/reference, adversarial tests, trace comparison, benchmark report with performance profiles, and a reviewer with numerical-methods competence.

- Coverage targets are risk-based: 100% branch coverage for schema migrations, transaction validation, conditional classification, fallback routing, and certification logic; exhaustive path tests for enabled fallback states.

- Property/model adapters run conformance suites. Optional dependencies cannot alter default behavior merely by being installed.

- Structured logging uses stable event schemas; no scientific decision exists only in log prose.

- Performance changes require profiles and retained correctness. Fast wrong answers and opaque convergence do not count.

- Security: untrusted models execute out of process or in containers; resource limits, artifact allowlists, secret isolation, signed model packages, and network policy are enforced. Untrusted *text* is handled per §9.5.

- Documentation includes equations, sign conventions, units, assumptions, validity, examples, failure modes, and benchmark provenance.

### 15.1 Definition of done for a model

- Manifest, schema, equations/algorithm, conservation statement, units/sign conventions, validity domain, initialization, scaling hints, conditional classification, PTC eligibility, and provenance are complete.

- Nominal, limiting, invalid-domain, randomized, derivative, conservation, serialization, and adapter-conformance tests pass.

- If PTC-eligible, the static-equivalence test passes. If flash-bearing, the §6.4 phase tests pass.

- At least one coupled flowsheet test and one independent reference comparison pass, or the absence of a reference is explicitly justified.

- Failure modes emit typed diagnostics; examples and API documentation are executable.

- Model package version and compatibility are locked in a reproducible run bundle.

## 16. Risks and mitigations

| Risk | Consequence | Mitigation / kill criterion |
| --- | --- | --- |
| Thermodynamic breadth dominates | Project becomes a property-data effort before core value appears | Narrow native package; potential-based contract; adapters; benchmark-driven additions; never claim unsupported coverage |
| Original solver scope expands | Years spent recreating commodity numerics | Own orchestration and process numerics; the two-backend rule forces reuse of AD and linear algebra; kill criterion: if v0.0 is not solving a recycle end to end within 8 weeks, cut the native backend and ship on the third-party one only **[C2]** |
| Licensing discovered late | Rewrite or inability to distribute | Phase-0 license ADR; CI dependency and data license gates from the first commit **[C1] [C7]** |
| Decomposition assumed to work | Plan scorer credits benefit that does not exist; performance claims fail | `largest_block_fraction` reported and gated; DM positioned as diagnostic **[C3]** |
| Nonsmooth phase behavior | Newton stalls, optimizer fails silently, agents mis-diagnose | Explicit §6.4 formulation policy, mandatory phase tests, smoothing floors in the certificate **[C5]** |
| Architecture overgeneralizes | Complex contracts delay working cases | Prove each abstraction against three unlike implementations and delete unused flexibility |
| Model plugins destabilize core | Crashes, nondeterminism, incompatible derivatives | Conformance kit, capability negotiation, isolation, resource budgets, signed manifests |
| Agent causes unsafe mutations | Invalid or irreproducible engineering results | Transactions, permissions, deterministic validators, budget limits, immutable history, non-agent-writable certification policy |
| Prompt injection via model or import data | Agent takes an attacker's instruction as a user instruction | Untrusted-text envelopes, quarantined imports, permissions independent of content, injection-resistance test in the agent suite **[C12]** |
| Surrogates mislead optimizer | False optimum outside training domain | Conformal coverage, separate domain test, TRF with truth-model sampling, OOD tests, refinement triggers **[C10] [C11]** |
| Benchmark gaming | Good curated demos, weak general robustness | Performance profiles, published ensembles, seeds, budgets, failures, independent references, regression history, NOT_COMPARABLE verdicts **[C13]** |
| GUI consumes roadmap | Attractive shell precedes trustworthy core | Headless acceptance gates; GUI uses only public API and initially prioritizes diagnosis |
| Cross-simulator disagreement | Validation stalls due to semantic differences | Common case specification, property-level triangulation, documented reconciliation workflow, explicit NOT_COMPARABLE |
| Community fragmentation | Adapters and models fork contracts | Stable extension kit, governance, compatibility tests, model registry and deprecation policy |
| **Maintenance and sustainability** **[C16]** | The dominant failure mode for academic simulation software: funding rewards features, not maintenance; the project orphans | Named governance model and maintainer succession from v0.1; dependency minimalism as an explicit budget; a no-orphan-subsystem rule (any subsystem without a named maintainer is deprecated, not left to rot); an explicit published list of what is deliberately unmaintained; a funding plan that names maintenance as a line item, not a residual |

## 17. Release acceptance criteria

### 17.0 v0.0 — Walking skeleton **[C15]**

- Three-component ideal system; mixer, splitter, isothermal flash, heater; one recycle with one tear; damped Newton on the torn system.
- Canonical IR serialization with stable IDs and a content hash; one schema migration exercised end to end.
- SolveEvent stream, SolutionCertificate, FailureBundle, and RunManifest are emitted, serialized, and validated against their schemas.
- `reproduce_run` reconstructs the run from the bundle and detects an intentionally changed dependency.
- One deliberately failing case produces a typed FailureBundle with a correct taxonomy code.
- CI runs on two platforms and asserts structural-hash equality.
- Total scope target: something a reviewer can read in an afternoon. If it is larger, cut it.

### 17.1 v0.1 — Transparent solver kernel

- Canonical Process IR v0.1, schema, migration harness, semantic diff, immutable revision IDs, units, provenance, and round-trip golden tests.

- Native ideal thermodynamics expressed as a differentiable potential, with TP and PH flash cases, verified derivatives, reference states, and typed domain failures.

- Core unit library of §5.5 including the flash cascade; every model satisfies the model definition of done.

- Graph analysis with Dulmage–Mendelsohn diagnostics, DOF/matching, SCC/BTF decomposition with `largest_block_fraction`, stable tear selection, and source-mapped structural reports.

- Conditional classification implemented; unclassified conditionals rejected at validation.

- At least one §6.4 VLE formulation that survives phase disappearance, with its tests passing.

- Orchestrated path implements layered initialization, acyclic/sequential execution, safeguarded recycle acceleration, EO solve for coupled blocks, PTC for at least one model family, adaptive continuation, automatic scaling, checkpoint/rollback, and at least three distinct tested fallback classes.

- Solver trace and SolutionCertificate/FailureBundle are stable serializable schemas; identical seeded runs meet D0/D1 policy, with cross-platform structural-hash equality in CI.

- SFILES 2.0 export/import with a round-trip test.

- Benchmark tiers A–D contain at least 30 cases total. All correctness gates pass; the published nominal robustness ensemble meets its target within fixed budgets, reported as a performance profile, with 100% correct handling of intentionally invalid structural cases.

- DWSIM and IDAES comparison exists for at least eight overlapping cases; each case has reconciled semantics, predefined tolerances, and an explicit verdict.

- Python SDK and CLI can construct, validate, solve, inspect, replay, and export without a GUI.

- Dependency and data license gates pass. No enabled numerical fallback lacks a direct fault-injection test.

### 17.2 v0.2 — Agent-native multi-fidelity workflow

- Transactional API with optimistic concurrency, idempotency, preview/validate/commit/rollback, jobs, budgets, cancellation, events, and artifact store.

- MCP binding generated from the API; typed agent tool surface covers all groups in §9.4; the reference agent passes at least 80% of published project tasks without direct IR text editing, never commits an invalid process, and passes the injection-resistance task. Results on at least one external agentic benchmark are published, including inexpressible cases.

- Equilibrium-stage MESH column with two solution strategies, validated against ChemSep and DWSIM on a defined case set. **[C9]**

- Web GUI supports flowsheet editing, model/equation inspection, DOF view, solve trace/fallback tree, scenario diff, and agent activity timeline using only public APIs.

- At least two additional open thermodynamic/property adapters pass a shared conformance suite; mismatched reference states, insufficient capability tiers, and unsupported extrapolation fail before solve.

- PyMRM adapter executes a version-pinned reactor model out of process with boundary mapping, timeout, cache, provenance, and result validation.

- Surrogate lifecycle supports DOE, training, independent validation, **conformal coverage certification**, domain test, derivative test, portable execution artifact, and promotion/rollback.

- Trust-region filter optimization demonstrated on a flowsheet with an embedded expensive model, with the truth-model sampling schedule recorded. **[C11]**

- North-star reactor–separator–recycle example replaces a simple reactor with a PyMRM-derived surrogate, reoptimizes under TRF, and reports decision change and uncertainty with full lineage.

- Benchmark tiers E–G are active; robustness, API safety, OOD, external timeout, injection, and reproduction scenarios pass in CI/nightly tiers.

### 17.3 v1 — Stable research-grade platform

- Process IR, model contract, property contract, solver trace, run bundle, and transactional API are stable v1 with documented compatibility/deprecation policy.

- Validated steady-state library covers the agreed benchmark envelope, including nonideal separations and coupled reactor/separation/heat-integration cases; unsupported domains are explicit.

- Published benchmark suite includes at least 100 cases, at least 25 cross-simulator comparisons, robustness ensembles reported as performance profiles, machine-readable results, and reproducible containers/locks.

- On the published supported envelope, certified solution success meets the published target within budgets across robustness ensembles; no known false certification; every failure returns a typed, replayable diagnosis bundle.

- Optimization supports derivative-aware constrained studies, trust-region filter for embedded expensive models, multi-start evidence, domain enforcement, sensitivity checks, and at least one synthesis/superstructure demonstrator.

- The complete asynchronous refinement loop is demonstrated: high-fidelity experiment selection by multi-fidelity acquisition, artifact provenance, surrogate update with conformal recalibration, process reinsertion, and decision-stability analysis.

- Web workbench, SDK, CLI, and MCP tools are feature-consistent for core workflows and operate on the same revision/event model.

- Independent external users can reproduce published benchmark and north-star results from clean environments and add a new unit model using the extension kit without modifying core packages.

- Security threat model (code execution and prompt injection), plugin sandboxing, governance with named maintainers and succession, release signing, support matrix, contributor documentation, and long-term benchmark stewardship are in place.

## 18. Implementation-plan handoff

The coding agent receiving this blueprint should produce an implementation plan with the following mandatory outputs. It may refine sequencing and technology choices but must preserve the architectural invariants unless it proposes an ADR with evidence and an explicit migration impact.

- **Phase-0 ADRs, which are blocking:** project license and dependency license policy; `CompiledProblem` backend selection with a benchmark prototype; IR schema v0; default VLE formulation; sparse linear solver; determinism discipline.

- Traceable requirements matrix mapping every v0.0 and v0.1 criterion to packages, work items, tests, owner role, dependencies, and evidence artifact.

- Technology decision matrix for implementation language(s), AD/expression engine, sparse linear algebra, serialization, API framework, job runtime, and web stack; include benchmark prototypes for high-risk choices and a license column for every row.

- A **v0.0 plan measured in weeks**, then a v0.1 milestone plan centered on executable vertical slices, not isolated framework construction.

- Normative initial schemas for Process IR, ModelManifest, CompiledProblem, SolvePlan, SolveEvent, FailureBundle, SolutionCertificate, RunManifest, and SurrogateManifest (with conformal fields).

- Numerical spike plan proving matching/DM/SCC/BTF, tear solve, block EO solve, PTC on one model, scaling, continuation, and fallback on synthetic and small process cases — including a spike that deliberately measures `largest_block_fraction` on a recycle flowsheet to confirm or refute the decomposition assumption early.

- Benchmark acquisition plan with exact reference versions (DWSIM, IDAES, ChemSep, CoolProp/thermo/Clapeyron), licensing, case ownership, reconciliation workflow, performance-profile tooling, and automated report generation.

- Risk register with trigger metrics and kill/pivot criteria, especially for thermodynamics, the AD/backend decision, plugin isolation, multi-language boundaries, and maintenance capacity.

- CI matrix, coverage policy, reproducibility environments, license gates, performance baselines, security model including prompt injection, documentation structure, and release process.

- Backlog that separates v0.0 and v0.1 commitments from explicitly deferred work; no GUI polish or unit-operation breadth may displace solver transparency and validation gates.

> **Final instruction to implementers** — The numerical core is original, transparent, inspectable, deterministic where appropriate, and exhaustively tested. Originality lives in orchestration, structure, initialization, continuation, certification, and provenance; it does not live in re-implementing automatic differentiation, sparse factorization, or diagnostics that a funded open project already provides. Treat every hidden heuristic, silent fallback, unverifiable derivative, unlicensed datum, or unreproducible result as architectural debt requiring an explicit issue and acceptance decision.

## Appendix A — Required core schemas

| Schema | Essential fields |
| --- | --- |
| CompiledProblem | IR revision/hash, backend id and license class, variables/equations with source maps, bounds, nominals, residual/Jacobian capabilities and provenance, sparsity, smoothness class, conditional classification, property dependencies |
| SolvePlan | plan id, structural hash, blocks/order, largest_block_fraction, tears, initialization stages, solver/scaling/homotopy/PTC policies, budgets, deterministic tie-break data |
| SolveEvent | sequence, time, stage/attempt/block, event type, metrics, implicated object IDs, decision rule, artifact refs |
| FailureBundle | taxonomy code, causal chain, evidence, best checkpoint, attempted remedies, exhausted budgets, ranked next actions **as executable tool calls**, replay identity |
| SolutionCertificate | termination, tolerances, raw/scaled residuals, conservation/spec/bounds/property/domain checks, VLE formulation and final smoothing epsilon, solve path (SM/EO/PTC), reproducibility class, warnings, relaxed-certification flag |
| SurrogateManifest | parent model ref, DOE provenance, training/calibration/test splits and hashes, metrics, conformal target and achieved coverage, domain test definition, derivative support, execution artifact hash |
| RunManifest | process/model/property/solver/dependency hashes, backend id, linear solver, thread pinning, platform, seed, policies, inputs, outputs, parent run |

## Appendix B — Initial benchmark case inventory

| Category | Minimum cases |
| --- | --- |
| Structure | acyclic chain; redundant spec; missing spec; algebraic loop; structurally singular but square; irreducible degenerate set; component mapping error; recycle flowsheet whose BTF yields one giant block |
| Scaling | mixed Pa/bar and mol/s/kmol/h; 12-order magnitude variables; badly scaled energy balance; near-zero trace component |
| Thermo | binary ideal flash; PH flash; bubble/dew; phase disappearance and reappearance; trivial complementarity solution; near-critical rejection/handling; reference-state mismatch; derivative agreement against an AD reference |
| Recycle | linear recycle; high-gain recycle; oscillatory recycle; nested recycle; recycle coupled to flash; purge stabilization |
| Reaction | adiabatic conversion; equilibrium with heat; recycle reactor; selectivity-sensitive reactor; infeasible conversion |
| Heat integration | countercurrent HX; approach constraint; heat-integrated recycle; coupled duties/design spec |
| Separation | N-stage flash cascade (v0.1); MESH column with phase disappearance and an infeasible specification (v0.2) |
| Failure injection | bad derivative; property timeout; NaN from plugin; singular Jacobian; homotopy branch loss; PTC steady state not reached; conditional cycling; OOD surrogate; conformal coverage violation |
| Agent | injected instruction in an imported manifest; context-overflow flowsheet; recovery from a certified failure |
| Cross-tool | at least eight v0.1 shared DWSIM/IDAES cases, at least four v0.2 ChemSep column cases, expanded to 25+ by v1 |

## Appendix C — Evidence base for v2.0 changes

Structural analysis and diagnostics: IDAES Diagnostics Toolbox and Degeneracy Hunter (Dowling & Biegler, 2015); applications of the Dulmage–Mendelsohn decomposition for debugging nonlinear optimization problems (Comput. Chem. Eng., 2023); Jacobian-based model diagnostics applied to equation-oriented carbon capture models (Comput. Chem. Eng., 2025); sdopt-tearing (exact and heuristic tearing methods).

Convergence mechanisms: Pattison & Baldea, equation-oriented flowsheet simulation and optimization using pseudo-transient models (AIChE J., 2014) and the fast-algorithms follow-up (I&ECR, 2018); pseudo-transient continuation on inertial manifolds (CMAME, 2019); homotopy continuation for process design and homotopy parameter bounding for branch connection; Anderson acceleration convergence analysis (Walker & Ni; and applications to equilibrium chemistry, 2024).

Phase equilibrium formulation: complementarity-based VLE for equation-oriented simulation and optimization (with bubble/dew embedding to reject trivial solutions); Kamath, Dowling & Biegler penalty/complementarity formulations; Watson & Barton, reliable flash calculations via nonsmooth inside-out algorithms with generalized derivatives; smooth square flash formulations for EO optimization.

Thermodynamics architecture: teqp (NIST); FeOs (I&ECR, 2023); Clapeyron.jl — all three deriving properties and derivatives from a single differentiable potential by AD. Data licensing: DIPPR 801 and NIST TDE distribution terms versus the MIT-licensed `chemicals`/`thermo` stack.

Surrogates and multi-fidelity: Eason & Biegler trust-region filter for glass-box/black-box optimization (2016, 2018), the 2024 efficiency-improved variants, the 2024 TRF survey, and Hessian-informed TRF (AIChE J., 2026); conformal prediction for surrogate UQ with coverage guarantees under out-of-distribution deployment (2024–2026); multi-fidelity Bayesian optimization reviews and multi-fidelity expected-information-gain estimators (2025).

Agents: CRAFTS and the OpenIDAES-450 corpus (2026); multi-agent text-to-simulation workflows and the Simona dataset (AAAI 2026); LLM agents for user-friendly chemical process simulation (2026); agentic AI with MCP against AVEVA Process Simulation (2026); PSE-Bench; MCP tool-description quality studies (2026); MCP security guidance (2026).

Interoperability and semantics: SFILES 2.0 (Optim. Eng., 2023) and the flowsheet transformer trained on 8000+ topologies; SSP 2.0 with FMI 3.0 and layered standards (2025); DEXPI 2.0; Mädler et al., simulation model exchange in the process industry (Chem. Eng. Technol., 2025); OntoCAPE and the OntoModel/OntoProcess knowledge-graph framework for digital twins of chemical processes (Nat. Chem. Eng., 2026).

Benchmarking methodology: Dolan & Moré, benchmarking optimization software with performance profiles (Math. Prog., 2002) and nested performance profiles.

Dependencies and licensing: CasADi (LGPL); Pyomo (BSD-3); SuiteSparse component licensing — KLU LGPL-2.1+, UMFPACK GPL; MUMPS CeCILL-C; HSL MA57 non-free.

Sustainability: open-source scientific software sustainability studies showing maintenance underfunding as the dominant long-term failure mode for academically funded platforms.
