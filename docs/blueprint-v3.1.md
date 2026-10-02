# Agent-Native Open Process Simulator

**Version 3.1 — Targeted amendments to the consolidated implementation blueprint**  
**Date:** 6 September 2026  
**Supersedes:** version 3.0 (6 September 2026), which superseded versions 1.0 and 2.0  
**Status:** Final architectural baseline for implementation planning; not a claim that the proposed software or benchmarks already exist.  
**Audience:** Frank Peters, scientific and technical leads, and implementation agents.

> Build an open process-engineering runtime in which models, equations, numerical strategies, validity limits, and evidence are explicit objects. Humans and coding agents use the same scientific contracts. Own the solver orchestration and process-specific numerical methods; reuse established differentiation, linear algebra, and optimization infrastructure.

## Document authority

This is a standalone replacement for versions 1.0, 2.0, and 3.0. Its requirements, release gates, and explicit deferrals are authoritative; requirements in earlier versions are not additional obligations. **MUST** denotes an invariant or release requirement. **Default** denotes the implementation choice to use unless an evidence-backed architecture decision record (ADR) changes it. **Deferred** means outside the named release, not an unfinished prerequisite.

The implementation agent must turn this blueprint into executable work packages, schemas, ADRs, and tests. It must not reopen all technology choices, build every future interface in advance, or replace numerical evidence with plausible demonstrations. A proposed departure must state its reason, affected requirements, migration impact, and acceptance evidence.

External sources support the specific methods and capabilities cited. Architectural choices, scope, numerical safeguards, and proposed thresholds are design judgments in this document. No benchmark performance is asserted without measurements.

**Version 3.1 amendment guide.** The section structure and release ordering of v3.0 are retained. Marked amendments A01–A10 clarify: A01 phase-set ownership (§6.3/§7.6); A02 cross-unit specifications (§7.2); A03 PTC qualification and step control (§7.5); A04 robustness sampling (§13.4); A05 backend comparison (§3.1); A06 optimization bridges (§10); A07 default uncertainty reporting (D12/§9.2); A08 local numerical regularity (§8.1); A09 energy-check independence (§8.1); and A10 binary-license audit (§3.1/§15). Corresponding acceptance gates and evidence schemas are updated in place. These amendments specify implementation behavior; they do not claim the spikes or tests have already been executed.

## 1. Executive decisions and resolution of open issues

Version 1 established the right product and architectural direction. Version 2 usefully added pseudo-transient continuation, explicit phase handling, stronger provenance, and staged delivery. However, it also introduced excessive early scope, conflicting backend requirements, and several scientific claims that need qualification. Version 3 resolves them as follows.

| ID | Issue | Version 3 decision |
| --- | --- | --- |
| D01 | Meaning of an original numerical core | Own solve-plan construction, initialization, tearing, hybrid SM/EO execution, globalization policy, continuation, diagnostics, and verification. Reuse expression engines, AD, sparse factorization, and constrained optimization. |
| D02 | Language and compiled backend | Python-first orchestration; CasADi is the default expression/AD engine, subject to a bounded integration and distribution spike. A residual/Jacobian callback adapter provides a second implementation route, not a second full compiler. |
| D03 | Sparse solver | Start with explicit SciPy SuperLU through `splu`. KLU and other solvers are later benchmark-driven adapters. Do not assume symbolic-factorization reuse is exposed by every backend. |
| D04 | Licensing | Design for an Apache-2.0 core and an audited default dependency set. Inspect exact binary artifacts and bundled plugins; a top-level package license is insufficient. Keep data-use rights separate from software licensing. |
| D05 | Structural decomposition | Retain both diagnostic and computational value. Measure block sizes and solve cost; neither promise decomposition nor dismiss it in advance. Structural matching does not establish numerical rank or nonlinear feasibility. |
| D06 | Scaling order | Establish scales before initialization tests, tearing, and nonlinear iterations. Scaling is a cross-cutting policy, never a late rescue stage only. |
| D07 | Pseudo-transient continuation | Retain as a first-class optional mechanism. Require an explicit equation-to-state mapping, mass matrix, sign convention, consistent algebraic initialization, and stability evidence. No generic diagonal-magnitude recipe is trusted by default. |
| D08 | Thermodynamic primitive | Public contract is capability-based properties, states, and derivatives. Prefer internally consistent potentials for native models. Do not require every external provider to expose a potential. |
| D09 | Phase appearance | Begin with a guarded procedural flash and explicit active-phase management. Add one validated smooth EO formulation for selected systems later. Critical and unsupported phase regions return typed limitations. |
| D10 | Property cache | Exact-input cache only in residual, derivative, and final verification paths. Approximate lookup may suggest initial guesses but cannot masquerade as exact property evaluation. |
| D11 | Multiple steady states | Preserve branch provenance and distinguish numerical, thermodynamic, and dynamic stability. Continuation and PTC can select different roots; neither establishes uniqueness. |
| D12 | Surrogate uncertainty | Separate model discrepancy, numerical error, predictive uncertainty, and domain membership. Split-conformal is the Default reporting baseline with independent calibration/test draws from a registered reference distribution; alternatives require an ADR. Coverage qualifications remain mandatory. **[A07]** |
| D13 | Multi-fidelity optimization | Use a tested trust-region framework for eligible smooth gray-box problems. State theorem assumptions and finite-budget limitations. Do not promise convergence for arbitrary CFD, switches, or discrete synthesis. |
| D14 | Meaning of a certificate | Verify a solution against a pinned mathematical model and policy. Independently track empirical model validation and optimization evidence. A converged model is not proof of physical truth or plant safety. |
| D15 | Agent workflow | Local Python/CLI transactions start with the first release; a small MCP/HTTP binding follows in v0.1. No mandatory HTTP round trip for local scientific use. |
| D16 | Draft editing | Incomplete drafts are persistable. A run requires a revision validated for that task. Simulation closure and optimization closure are different requirements. |
| D17 | Release scope | v0.0 proves an end-to-end solve; v0.1 proves transparent orchestration and a bounded agent workflow; v0.2 proves reactor-model replacement; v0.3 develops columns and separations. |
| D18 | Interoperability | Canonical JSON/YAML and replay bundles first. SFILES is a topology projection. SSP, FMI, DEXPI, CAPE-OPEN, and semantic-web projections are demand-driven adapters. |
| D19 | External references | DWSIM and IDAES are principal process references. ChemSep is a useful additional column reference; free availability alone must not be called an open-source license. |
| D20 | Reproducibility | Separate deterministic structural artifacts from adaptive numerical decisions and timing. Deterministic planning may use parallel work if aggregation and tie-breaking are deterministic. |

## 2. Mission, scope, and success

### 2.1 Product mission

Create an open, agent-native process simulator for transparent, multi-fidelity process design. An engineer or agent can construct a flowsheet, inspect its equations and degrees of freedom, solve it, understand failure, replace a component model, and assess whether the engineering decision changes.

The long-term ambition is to match or exceed leading simulators within a declared application envelope. Early success means reproducible balances, robust and explainable solves, useful integration with research models, and a smaller gap between process design and computational model development. It does not mean matching Aspen's property databank or industrial breadth.

### 2.2 Supported early envelope

Steady-state, continuous material and energy networks; a declared finite component set; ideal systems initially; selected nonideal vapor–liquid systems after property conformance; recycles; heat exchange; conversion and kinetic reactor models; process specifications; later constrained operating-point optimization.

Each release publishes a support matrix listing component data, phase types, property methods, unit models, derivative capabilities, and tested operating regions. Unlisted capabilities are unsupported, even if an adapter happens to accept them.

Dynamics and control, electrolytes, solids, polymers, refinery assays, rate-based columns, full P&ID authoring, online plant operation, and universal mixed-integer synthesis are deferred. Reserving metadata for future dynamics does not justify building a DAE compiler in the first release. PTC is a steady-state numerical method, not a dynamic-simulation product commitment.

### 2.3 Two reference journeys

**Numerical reference journey:** a three-component synthetic ideal system with feed, heater, flash, splitter/purge, mixer, and recycle. Transparent synthetic data isolates solver correctness from real-data uncertainty. A once-through variant, a high-recycle variant, a disappearing-phase variant, and invalid specifications exercise the same vertical slice.

**Scientific reference journey:** a reactor–separator–recycle process whose reactor progresses from a simple model to a PyMRM distributed model and a derived surrogate, with later Peclet/CFD-informed closures or experiments. Compare operating-point decisions, conversion/selectivity, duties, pressure drop where modeled, and computational cost. The real chemistry and dataset are selected by the end of v0.1 using available kinetics, redistribution rights, a property package, and an independent reference implementation. The synthetic example must never be presented as validated real chemistry.

The first refinement demonstration uses one continuous design decision and one fixed topology. More expensive models are introduced because their effect on that decision can be measured, not simply because their fidelity label is higher.

## 3. Architectural boundaries

| Layer | Owns | Must not own |
| --- | --- | --- |
| Process IR | Components, model instances, connections, specifications, scenarios, semantic identities | Backend objects, live solver state, GUI layout |
| Model and property contracts | Equations/evaluators, state definitions, validity, derivative declarations, initialization recipes | Global solve strategy, undeclared mutations |
| Compilation and analysis | Lowering, units, aliases, source maps, incidence graphs, structural diagnostics, capabilities | New physical assumptions introduced without a recorded transformation |
| Numerical runtime | Residual evaluation, linear solves, steps, scaling, local convergence measures | Permission decisions or agent-generated mathematics |
| Orchestrator | Plans, bounded attempts, continuation, checkpoints, verification, provenance | A hidden LLM inside the trusted solve path |
| Study runtime | Sensitivity, estimation, optimization, fidelity experiments | Unrecorded model substitution during a fixed solve |
| Application service | Transactions, revisions, jobs, artifacts, authorization | Client-specific scientific behavior |
| Clients | Python, CLI, HTTP/MCP, web workbench | Private mutations that bypass application validation |

Use a modular monorepo and a single deployable local application initially. Logical packages are not an instruction to create microservices. Parallel scenario evaluation and external experiments are more valuable early than parallelizing every graph operation.

### 3.1 Default implementation stack

Python hosts semantic objects, orchestration, model authoring, and adapters. NumPy/SciPy provide array and numerical infrastructure. CasADi supplies expression graphs and sparse AD behind `CompiledProblem`; its documented graph and callback facilities are the relevant capabilities, not a mandate to use its nonlinear solvers. [CasADi documentation](https://web.casadi.org/docs/)

Default linear factorization uses `scipy.sparse.linalg.splu` with explicit options and CSC assembly. Record ordering, pivoting, and linear residuals. Its public interface supplies factorization and solves; persistent symbolic-analysis reuse is not assumed. [SciPy `splu`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.splu.html)

A thin callable backend accepts native or external residual/Jacobian blocks. It shares conformance tests with the expression backend, but need not expose optional Hessian or code-generation capabilities. A mature NLP adapter and a Pyomo bridge are added when optimization needs them. IDAES diagnostics provide reference behavior and an optional comparison path; orchestration does not import IDAES objects. [IDAES diagnostics workflow](https://idaes-pse.readthedocs.io/en/stable/explanations/model_diagnostics/index.html)

**[A05 — named backend comparator]** The Phase-0 spike has a ten-working-day maximum and compares **CasADi against Pyomo + PyNumero/ASL** on the same ideal flash/recycle equations, physical inputs, scales, and SuperLU solve policy. The small comparator fixture is not a second production model library. Report build/installation effort, compilation, evaluation and derivative cost, memory, source mapping, sparse first derivatives, and optional second-derivative products. Record NL generation/loading separately from repeated in-memory evaluation; do not assume an NL round trip per residual call. PyNumero's ASL route is the named derivative comparator. [PyNumero NLP interfaces](https://pyomo.readthedocs.io/en/6.8.0/contributed_packages/pynumero/tutorial.nlp_interfaces.html)

Both candidates MUST compose a nontrivial property callback with **declared Jacobian sparsity** into the coupled problem. Check values, directional derivatives, the assembled sparse pattern and expected nonzero count across registered states, and absence of silent densification. Also test the callback chain rule and source mapping; nominal solve agreement alone is insufficient. State the exact integration route and any callback/ASL limitation. Compare the expression engine and external-block route separately where their capabilities differ. A blocked native callback path is a recorded outcome, not grounds to substitute a dense approximation without disclosure.

CasADi remains the provisional Default. The closing ADR selects the demonstrated route based first on correctness, sparse composition, distributability, and deployment, then measured cost. A Pyomo win changes the backend default without changing the IR or orchestration contracts. Do not build an AD engine as the fallback.

**[A10 — required spike artifact]** Produce a binary dependency inventory for the exact CasADi wheel(s): bundled solver/plugin libraries, dependency relationships, artifact hashes, license texts/notices, and default-install-policy verdicts, including disabled plugins whose bytes are distributed. Apply the same audit to the Pyomo/PyNumero/ASL/cyipopt comparator and its numerical dependencies. A top-level LGPL or BSD label is not the inventory. Record any compliant build or packaging action needed before selecting the production distribution.

### 3.2 CompiledProblem contract

The minimum interface provides ordered free variables and residual equations, bounds and physical nominals, source maps, `residual(x, context)`, declared sparsity, a sparse Jacobian or an explicitly permitted derivative fallback, and a structural fingerprint. Parameter and specification values are pinned inputs.

Optional capabilities are JVP, VJP, parameter derivatives, Hessian-vector products, batched evaluation, symbolic export, and generated code. JVP/VJP may use an assembled Jacobian when appropriate. Capability absence must not force a model to invent derivatives.

Each evaluation returns a validity status, error estimate when available, active-phase signature, derivative provenance, and cost counters. A Jacobian is valid only for the same state, model version, phase regime, and evaluation policy as its residual. Mutable evaluation workspaces are run-local; shared model descriptions remain immutable.

## 4. Process IR and semantic rules

### 4.1 Required objects

| Object | Required information |
| --- | --- |
| ProcessRevision | Parent revision, semantic content hash, schema version, component set, instances, connections, specifications |
| ModelInstance | Stable ID, model/version/artifact reference, parameter bindings, semantic role, fidelity and validity policy |
| Port / Stream | Material/energy/signal kind, direction, multiplicity, component mapping, state definition, phase capabilities |
| Quantity | Physical meaning, dimensions, display unit, role, bounds, nominal, uncertainty reference |
| Equation | Stable ID, expression or evaluator reference, dependencies, dimension, source, conditional class |
| Specification | Target/expression, value or bounds, units, tolerance, fixed/free/decision role, provenance |
| ModelManifest | Ports, mathematics, derivatives, initialization, validity, implementation artifact, execution requirements |
| ComponentRecord | Stable chemical identity, elemental composition where known, molecular weight, parameter data and provenance |
| Study | Revision reference, decisions, objectives, constraints, scenarios, budgets, evidence requirements |
| ProvenanceRecord | Actor, operation, parent, source references, artifact hashes, timestamp outside semantic hash |

The semantic IR records model identity and parameterization; compiled equations are generated artifacts with source maps. A small serialized expression vocabulary supports custom algebraic equations. It is not a home-grown optimizer, symbolic simplifier, or AD system. Opaque models supply inspectable metadata and algorithm/source references; they must not falsely claim equation-level transparency.

### 4.2 State representation and conservation

Internal units are SI with explicit amount and mass bases. Absolute temperature and temperature difference are distinct quantities. Use component molar flows as the default extensive material variables; derive total flow and mole fractions where total flow is positive. Alternative state definitions are permitted through explicit adapters.

At exactly zero material flow, composition and some intensive properties are undefined. A dormant stream may retain a labeled initialization hint, but that hint is not a physical constraint. Do not divide by total flow or impose arbitrary normalized composition to force solvability. Positive log transforms are inappropriate for variables that must reach zero; use bound-aware coordinates or phase-specific formulations.

Pressure connections, heat duty, shaft work, stream enthalpy, and reaction energy have explicit signs and reference states. For example, positive heat and shaft work are into the unit unless a model declares and maps another convention. A valve and pump cannot silently create pressure compatibility for an invalid network.

For reaction stoichiometry matrix N and element matrix A, require A N = 0 when the component identities support elemental accounting. Total molar flow need not be conserved in a reaction. Formation enthalpy and heat-of-reaction conventions must be reconciled to avoid double counting. Pseudo-components without elemental formulas explicitly limit the verification scope.

Tears are numerical choices in a SolvePlan, not physical units. Alias elimination and connection reduction preserve a reconstruction map so all original stream equations can be independently checked.

### 4.3 Validation by task

Validation runs schema, dimensions, graph connectivity, component/reference compatibility, conditional classification, capability checks, then task-specific structural analysis. Physical checks distinguish fixed specifications, tentative initial guesses, and solved states: a poor guess is not proof that the specified process is impossible.

`DRAFT` revisions may be incomplete or under-specified. `READY_FOR_SIMULATION` requires an appropriate closed system after fixed-variable elimination. `READY_FOR_OPTIMIZATION` permits declared decision variables and requires a valid optimization formulation. These are validation results tied to a revision and task, not editable badges. A syntactically valid draft can be committed without being executable.

Matching and Dulmage–Mendelsohn decomposition identify structural deficiencies. They do not prove nonlinear feasibility, numerical nonsingularity, or a unique minimal conflict set. Additional rank or conflict searches must label whether results are structural, local numerical evidence, or a verified minimal subset.

### 4.4 Serialization and identity

Provide readable YAML and normative JSON Schema, with canonical JSON for hashes. Define numeric representation, stable ID ordering, unit normalization, and handling of signed zero. Reject nonfinite numbers in semantic inputs; missing values have explicit states. Presentation metadata, timestamps, and layout are outside the physical-model hash.

Separate schema, structure, numerical model, solve-policy, and full run fingerprints. Sparsity reuse requires a compatible structural pattern and active formulation, not merely an unchanged drawing. Units, model parameters, reference states, and source-data versions affect numerical identity. Cross-component permutations may change byte identity while still passing a semantic equivalence test.

Runs are immutable. Schema migrations produce new revisions with a migration report and retained originals. Store large arrays and binaries as hashed artifacts; replay never executes an arbitrary pickle.

## 5. Model composition and derivative contracts

### 5.1 Three execution classes

**Native equation model:** contributes residuals and inspectable equations to an EO system. It may also supply a causal evaluator and local initializer.

**Explicit or reduced model:** maps u to y = f(u). It participates in an EO block through r = y − f(u), provided the required value and derivative accuracy is available. An evaluator is not automatically smooth or inexpensive.

**Experiment provider:** a long-running PyMRM, Peclet, particle, or remote job that yields data and numerical evidence asynchronously. It does not run inside every Newton iteration by default. Fast, deterministic reduced PyMRM models may opt into synchronous evaluation after conformance testing.

If an inner model solves g(w,u) = 0 and returns y = h(w,u), its local derivatives can use

\[
\frac{dw}{du}=-g_w^{-1}g_u,\qquad
\frac{dy}{du}=h_u-h_w g_w^{-1}g_u.
\]

This requires a locally nonsingular inner Jacobian, consistent branch selection, and sufficiently accurate inner solves. The adapter records these assumptions and its inner tolerance. A derivative through an incompletely converged algorithm is not automatically the derivative of the intended model.

### 5.2 Accuracy and differentiability

Declare analytic, AD, implicit, finite-difference, generalized, or unavailable derivatives by output and operating regime. Native simulation normally needs first residual derivatives. Exact-Hessian optimization may need more; second derivatives of properties and second derivatives of their generating potential are not interchangeable requirements.

Finite differences are audited using step sweeps, scales, evaluation noise, and phase awareness. Complex-step is used only through analytic, complex-compatible code. Check directional derivatives and the identity vᵀ(Ju) = (Jᵀv)ᵀu. Cross-checks sharing the same implementation or property backend are useful consistency tests, not independent validation.

External noise and incomplete inner solves set an accuracy floor. The orchestrator may tighten inner tolerances using a recorded forcing policy; it must not demand outer residual tolerances below achievable evaluation accuracy without reporting the conflict.

### 5.3 Replacement contract

A replacement checks ports, components, conserved quantities, reference states, boundary-condition meaning, degrees of freedom, derivatives, and validity. Matching the label “reactor” is insufficient. A model requiring both imposed inlet/outlet pressure and imposed flow may conflict with the process pressure network.

Promotion creates a new revision and invalidates affected runs and derivative/optimization evidence. Warm starts are transferred through an explicit state mapping. During one solve attempt, all model versions are frozen. Falling back to a lower-fidelity physical model creates a distinct run and certificate; numerical fallback may not silently change the engineering problem.

## 6. Thermodynamics and phase handling

### 6.1 Public capability contract

A provider declares supported components/phases/state variables; reference convention; properties and flashes; derivative order with respect to named inputs; domain; uncertainty and data provenance; thread safety; and numerical limitations. Require the capabilities used by a unit, not a universal tier that unnecessarily excludes valid providers.

Native implementations should derive equilibrium and caloric properties from consistent thermodynamic potentials and reference contributions. Helmholtz-based EOS differentiation is a useful implementation pattern, demonstrated by teqp. It reduces manual derivative work, but AD differentiates the implemented model; it does not prove correct thermodynamics. [teqp introduction](https://teqp.readthedocs.io/en/latest/getting_started/)

An excess Gibbs-energy model alone is not a complete property package: pure-component references, ideal mixing, caloric terms, phase models, and volume behavior still matter. Transport correlations remain separate. A black-box provider with accurate first derivatives may serve Newton solves even without a public potential or second derivatives.

### 6.2 Initial implementation and accuracy

The synthetic ideal package uses explicitly consistent chemical potentials and enthalpy references, with documented idealizations. A convenient vapor-pressure correlation and independently selected heat capacities must not be labeled fully thermodynamically consistent without checking their relationships. Real-data fixtures declare any approximation and its effect on the supported calculations.

Start with TP flash, then bracketed PH flash on supported single/two-phase regions. For ideal VLE, use a safeguarded Rachford–Rice solve, explicit single-phase endpoints, and zero-component handling. Entropy and PS flash are added when equipment models need them. PR/SRK and NRTL/UNIQUAC enter through one validated adapter or implementation at a time, driven by cases.

### 6.3 Formulations

| Formulation | Initial role | Required evidence |
| --- | --- | --- |
| Procedural flash with active-phase management | Default v0.0/v0.1 simulation | Material/energy closure; stable branch on the supported domain; phase disappearance/reappearance; regime-aware derivatives |
| Smooth EO VLE | Selected v0.2+ models and optimization | Recorded smoothing; tests against unsmoothed physical conditions; rejection of trivial/unphysical roots |
| Complementarity or generalized nonsmooth | Optional later strategy | An appropriate solver; normalized residual definitions; formulation-specific stability and root checks |
| Fixed phase set | Allowed for a declared domain | Final phase admissibility check; failure if the assumed regime is inconsistent |

**[A01 — phase-set ownership]** In the Default procedural-flash EO path, the active phase set belongs to the **local nonlinear attempt**, not to individual residual calls. Freeze it for all accepted iterates, trial points, residual/Jacobian calls, and derivative perturbations within that attempt. The callback evaluates the declared fixed-regime equations; it must not silently run a globally stable flash that chooses another phase set. A supported metastable continuation, if used numerically, is declared and never treated as a final stability result.

A trial that cannot be evaluated in the fixed formulation returns a typed domain or `PHASE_UPDATE_REQUIRED` outcome. The orchestrator can reject the trial or terminate the attempt, restore a valid checkpoint, and ask the bounded outer active-set controller to select a new phase set and restart. It need not wait for an impossible fixed-regime root to converge. Rebuild affected dimensions/sparsity, caches, and derivative state on the restart. Candidate phase selection/stability probes are separate from the attempt's residual function. Standalone flashes and sequential unit evaluation may select phases at their own boundaries; the accepted signature becomes the EO starting regime. Explicit smooth/complementarity formulations retain their declared semantics instead of inheriting this procedural rule.

Smooth VLE with bubble/dew constructions has an established reference implementation in IDAES. This supports testing that formulation, not imposing bubble/dew embedding as a universal stability proof. [IDAES SmoothVLE](https://idaes-pse.readthedocs.io/en/2.9.0/explanations/components/property_package/general/pe/smooth_flash.html)

General nonideal stability requires appropriate stability analysis, for example tangent-plane-distance searches over the supported phase space. A finite local search does not establish global stability. Report `STABLE_WITHIN_TESTED_SCOPE`, `UNSTABLE`, or `UNKNOWN`, with the search scope and residuals. Bubble/dew checks alone cannot establish every possible liquid–liquid or multiphase equilibrium.

At phase boundaries, derivatives may be one-sided, nonsmooth, or undefined. Near critical points, implicit flash sensitivities can become ill-conditioned. Do not return an ordinary smooth Jacobian with no qualification. Crossing a phase boundary is allowed in simulation through the chosen policy; it does not automatically authorize smooth gradient-based optimization across it.

Smoothing parameters are scaled and recorded. A small epsilon alone does not establish acceptable physical error. Full target-model verification requires original balance, complementarity, and phase tolerances to pass; otherwise label the result relaxed or unverified.

### 6.4 Exact cache and warm-start cache

An exact property key includes provider implementation and data hashes, ordered components, reference convention, state-definition ID, exact canonical numerical inputs, phase/branch policy, requested properties, derivative order, and accuracy policy. Complex perturbations cannot be discarded in complex-step tests. Cache entries record achieved accuracy and cannot satisfy a tighter request without evidence.

The residual and derivative paths must represent the same function. Quantizing state coordinates can make that function piecewise constant while returning nonzero derivatives; it is forbidden in exact evaluation. Nearby states may retrieve flash starting guesses, followed by a fresh converged property calculation. Negative cache entries cannot permanently hide a retry with a different authorized strategy.

Report requested evaluations, actual provider calls, flash iterations where available, cache hits, cache memory, and derivative calls separately. Whether properties dominate total cost is measured, not assumed.

## 7. Solver orchestration

### 7.1 State machine

The intended flow is graph analysis → structural decomposition → scaled initialization → sequential solve where useful → strongly coupled EO where required → continuation and qualified PTC → bounded fallback → independent verification. These are selectable strategies, not a rigid waterfall.

| Stage | Action and output |
| --- | --- |
| Validate and compile | Task-specific closure, capabilities, source map, fixed-variable elimination, original-equation reconstruction |
| Analyze | Process graph and equation graph; DM/SCC/BTF; sparsity, block metrics, tear candidates, rank risks |
| Scale and initialize | Physical scales, guess provenance, local initializers, domain checks, feasible starting attempts |
| Select plan | Deterministic structural rules; recorded estimates for coupling, cost, and derivative quality |
| Execute | Acyclic evaluators, safeguarded tear iteration, sparse EO, homotopy, or eligible PTC |
| Adapt | Accept/rollback; bounded changes of damping, partition, initialization, or numerical formulation |
| Verify | Reconstruct and reevaluate the target problem; balances, specifications, bounds, domains, phase checks |
| Return | SolutionCertificate plus evidence, or FailureBundle plus clearly qualified checkpoints |

The plan distinguishes structural-only decisions from numerical observations. Warm-start history and learned ranking are opt-in inputs with hashes. An LLM can propose an authorized action but cannot alter residuals or validation policy inside the runtime.

### 7.2 Structural analysis and tearing

Maintain a material/energy/signal process multigraph and an equation-variable incidence graph. Report free-variable count, equation count, matched/unmatched sets, block-size distribution, largest-block fraction, Jacobian nonzeros, and factorization cost when measured. Fixed/free decisions and alias elimination occur before the relevant counts.

BTF can greatly reduce a problem or produce one large block. Large blocks motivate tearing, physical partitioning, or full EO; they do not by themselves prove PTC is preferable. Score tears using cycle coverage, tear dimension, input domain, evaluator reliability, and estimated coupling. Early scores use simple documented rules, not a large untrained cost model.

**[A02 — cross-unit design specifications]** In v0.1, any specification coupling an adjusted variable to a target in another unit promotes the affected dependency region to an EO block. Include the specification equation, free adjusted variable, all intervening dependencies, and any connected recycle SCC needed for closure; upstream boundary values can remain fixed from the sequential solve. For example, adjusting heater duty to meet a downstream outlet temperature creates an EO region spanning the heater and the downstream calculation. Validate its degrees of freedom after promotion. A truly unit-local specification may use that unit's evaluator. **No nested SM secant/control loops for cross-unit specifications in v0.1.** If the region lacks required EO capabilities, return a capability failure rather than inventing a nested loop.

For recycle map G(t), solve R(t) = G(t) − t = 0. Closure tests use component flows and thermal/pressure variables with appropriate scales. A small change in successive tear iterates is not sufficient if closure residuals remain large.

Start with damped substitution and safeguarded Anderson acceleration. Record depth, regularization, restart, and coefficient safeguards. Add Wegstein/Aitken only when measured benefit justifies maintenance. Detect oscillation, stagnation, and invalid states; merge a troublesome recycle into an EO block when supported. Tearing eliminates variables only with a valid local evaluator and reconstructed-equation checks.

### 7.3 Scaling and nonlinear steps

For F(x) = 0, define positive variable scales Sx and residual scales SF:

\[
x=x_{ref}+S_x\hat x,\qquad
\hat F=S_F^{-1}F,\qquad
\hat J=S_F^{-1}J S_x.
\]

Physical nominals and balance-throughput scales are the starting point; Jacobian equilibration may refine them with caps. Bounds are not always good nominal values. Avoid a division by zero for absent components. Freeze scales inside a local attempt; refreshes start a recorded segment. Keep verification tolerances independent of numerical scaling.

Default EO is damped sparse Newton with a bound-aware line search on a declared scaled residual merit function. Check linear-system residuals, invalid property trials, and step acceptance. Rank-deficient systems trigger diagnostics; regularized least-squares steps are numerical recovery, not permission to discard equations. Small steps with large residuals indicate stagnation, not convergence. An already valid root need not take a small additional step to qualify.

Add trust-region globalization when a concrete benchmark family motivates it. Iterative/Krylov linear solves and block preconditioning follow profiling; a matrix-free path requires useful preconditioning and accuracy control, not merely a JVP interface.

### 7.4 Initialization and homotopy

Use user guesses, compatible warm starts, local model initializers, upstream propagation, and physical nominals in that order, while checking every candidate. Initializer projection is logged and does not rewrite fixed specifications. Local pressure, heat, reaction, and phase assumptions are explicit.

Homotopy defines H(x, λ), an easy endpoint and H(x,1) = F(x), including all original specifications. Examples include recycle closure, reaction activation, heat coupling, and nonideality. Each transformation declares its path domain, scales, and endpoint mapping. Adaptive steps retain rollback checkpoints.

A checkpoint at λ < 1 solves a modified problem and cannot receive a target-problem certificate. Failure to advance is `HOMOTOPY_STALLED`; branch loss is a hypothesis unless supported by diagnostics. Pseudo-arclength continuation for folds is deferred, with a multiple-root benchmark retained from v0.1.

### 7.5 Pseudo-transient continuation contract

For a suitably ordered and scaled residual, a permitted reformulation is

\[
M(\hat x)\frac{d\hat x}{d\tau}=-\hat F(\hat x),
\]

where zero rows may retain algebraic equations. The model supplies the equation-to-variable mapping, M, sign conventions, time-scale policy, domain, and a consistent initialization procedure. In a locally frozen-mass linearized step,

\[
\left(\frac{M_k}{\Delta\tau}+\hat J_k\right)\Delta\hat x=-\hat F_k.
\]

**[A03 — PTC execution and qualification]** The displayed step is the linearly implicit Euler/Newton-style pseudo-transient step associated with the Kelley–Keyes formulation, with the declared mass-matrix extension. It is not a converged implicit-Euler time step or a DASSL-style accuracy-controlled DAE integrator. A full implicit DAE implementation must include the derivatives required by its own residual formulation. [Kelley and Keyes, 1998](https://doi.org/10.1137/S0036142996304796)

Steady-state equivalence is necessary but insufficient: the artificial dynamics must have useful attraction properties on the tested region. For a nonsingular M, local behavior involves −M⁻¹J; diagonal magnitudes alone do not determine stability. Algebraic rows require consistent treatment and index awareness. State ordering must not accidentally determine the physics of the pseudo-dynamics.

Two qualification routes are acceptable: **(a)** a derivation from physical holdup/thermal-inertia equations, documenting which modes and branches are expected to attract and why; or **(b)** an explicitly specified artificial reformulation with empirical basin comparisons against damped Newton on registered cases. Both require steady-state equivalence, dimensional/sign checks, algebraic consistency, and bounded domain handling. Physical derivation is a useful basis, not stability by construction: an exothermic reactor can have an unstable physical steady state. A general stability theorem is not required; empirical qualification is labeled as such and limited to its tested envelope. v0.1 delivers one qualified family and retains measured successes and failures for either route.

The Default step controller is **safeguarded switched-evolution relaxation (SER)**. For accepted iterates, with fixed scales, set \(\phi_k=\|\hat F_k\|_2\) and propose

\[
\Delta\tau_{k+1}=\operatorname{clip}_{[\tau_{min},\tau_{max}]}
\left[\Delta\tau_k\,
\operatorname{clip}_{[\gamma_{min},\gamma_{max}]}
\left(\frac{\phi_k}{\max(\phi_{k+1},\phi_{floor})}\right)\right].
\]

This is a safeguarded residual-ratio controller, not a claim that the safeguards reproduce every assumption of the original convergence analysis. Register the initial pseudo-step, limits, residual floor, and growth/shrink limits in SolvePolicy before benchmarking. Suggested starting growth/shrink limits are 2 and 0.2. On a rejected/domain-invalid trial or failed linear solve, retain the previous state and residual, shrink the attempted step by 0.5, and retry within a bound; rejected trials never enter the accepted-step ratio. Stop on the original verification criteria before a near-zero residual inflates the ratio. Reset the controller on a scale, mass-policy, or active-set restart. Trace proposed/accepted pseudo-steps and rejection reasons. A general variable-step DAE adapter remains later work. Newton polishing is used when useful, not a mandatory ritual after an already verified steady state.

PTC can favor some roots over others and does not prove dynamic stability of the actual process. Pattison and Baldea provide the process-flowsheet motivation for this mechanism; it is not a universal convergence result. [Pseudo-transient flowsheet models](https://doi.org/10.1002/aic.14567)

### 7.6 Conditional equations and multiple roots

Classify conditions as fixed-at-compile, explicit outer active-set, smooth approximation, complementarity, or supported generalized nonsmooth form. Each has a declared solver capability and final admissibility test. Outer active sets have change events, bounded retries, cycle detection, and deterministic tie-breaking. Hysteresis may stabilize iteration but cannot change final physical acceptance conditions.

**[A01]** For the procedural EO path, §6.3 defines the frozen-attempt phase policy. Only the outer controller changes that phase set; every change closes an attempt and opens a new one.

A solve returns one admissible root unless a root-search study was requested. Store branch provenance, starting point, continuation history, and a root fingerprint with comparison tolerances. Multi-start may find additional roots but does not prove completeness. Separate:

- Numerical validity: does this state satisfy the selected equations?
- Thermodynamic stability: has the relevant phase equilibrium passed the declared checks?
- Dynamic stability: has a physical dynamic model been analyzed? Default `NOT_ASSESSED`.
- Optimality: what constrained optimization evidence is available for this branch?

### 7.7 Fallbacks and budgets

Every fallback edge has a trigger, preconditions, maximum count, estimated cost, checkpoint policy, and typed outcome. Budget wall time, residual/property calls, factorizations, external compute, and cancellation latency. Do not call failure to converge `PHYSICALLY_INFEASIBLE` unless there is independent evidence of infeasibility.

| Evidence | Authorized candidate action |
| --- | --- |
| Structural mismatch | Return actionable unmatched objects; revise a draft outside the solve |
| Invalid trial state | Shorten step, choose a supported state parameterization, or reinitialize |
| Recycle stagnation | Restart acceleration, damp, change a tear, or merge into EO |
| EO globalization failure | Refresh scales in a new attempt; try another globalization, homotopy, or eligible PTC |
| Rank deficiency | Local rank diagnostics; inspect redundant constraints; bounded regularized step |
| Phase cycling | Bounded active-set restart or a validated alternative numerical formulation |
| Surrogate domain violation | Stop or return to the study controller for a revised model/run |
| External timeout or noise | Bounded retry or exact compatible cached result; report accuracy/budget limits |

## 8. Verification, failure, and reproducibility

### 8.1 SolutionCertificate

The certificate is a reproducible numerical verification report. It includes model/revision/policy hashes; termination; raw and scaled residuals; specification, bound, component/element/energy balances; property and phase checks; domain compliance; derivative limitations; branch provenance; transformations; and explicit unchecked claims.

For residual or balance eᵢ use a registered acceptance rule such as

\[
|e_i|\le a_i+r_i s_i,
\]

with absolute tolerance aᵢ in physical units and a physically meaningful reference sᵢ. Report all three. Engineering tolerances are case-specific. The solver cannot inflate sᵢ using an enormous iterate or silently relax tolerances to pass.

Use `VERIFIED`, `RELAXED`, `UNVERIFIED`, or `FAILED` for target-model verification, together with structured checks. Experimental validation has a separate evidence record. An optimization result has a separate optimality report. A single green badge must not imply all three.

Final verification reconstructs the original equations after aliasing, tearing, and transformations. Reevaluate without approximate caches or unauthorized substitutions; independent balance evaluators are required. Exact caches may be bypassed for selected audit checks. No finite test suite constitutes a proof that the verifier has no defects.

**[A08 — local numerical regularity]** At the final state, evaluate the **unregularized target Jacobian** for the closed simulation problem after legitimate fixed-variable/alias elimination, using the declared phase regime and recorded scales. Never diagnose target rank from the regularized or PTC matrix. Store dimension, derivative accuracy, method, thresholds, permutation/scaling, and `NO_RANK_LOSS_DETECTED`, `RANK_DEFICIENT`, `ILL_CONDITIONED`, or `INCONCLUSIVE` as local numerical evidence. Reuse a factorization only if it belongs to that final Jacobian; a prior Newton factorization need not do so.

LU pivot/U-diagonal information is an inexpensive warning screen, **not a rank-revealing test or a condition-number estimate**. For background on the distinction between triangular factors and condition estimation, see [Higham’s survey](https://eprints.maths.manchester.ac.uk/695/1/high87t.pdf). Use a factorization-based reciprocal-condition estimate where reliable; suspicious or inconclusive cases trigger a bounded rank-revealing QR/SVD check on the relevant block, or retain `INCONCLUSIVE` when the budget/size prevents it. Thresholds account for scales and derivative/evaluation uncertainty. Include redundant-equation, nearly singular, and isolated-singular-root fixtures.

Residual satisfaction and regularity are separate checks: a rank-deficient root can be isolated (for example x² = 0), so deficiency does not prove a continuum or make the residual false. The Default closed-simulation verification policy requires no unresolved regularity warning for an unqualified `VERIFIED` result; otherwise retain passing residual/balance checks but return `UNVERIFIED` with the rank limitation. A study may explicitly request residual-only evidence for a singular problem, but it cannot relabel that as regularity or reliable sensitivity evidence. Optimization uses task-appropriate constraint/KKT diagnostics rather than applying the square-simulation rank test to free decision variables.

**[A09 — independence of energy verification]** A separately assembled energy balance using the same property package checks process bookkeeping and consistency. It is not an independent validation of enthalpy correlations or reference data. Record the shared provider/data hashes in the check; thermodynamic independence is established by the property's conformance suite and genuinely independent reference/data comparisons. Apply the same distinction to any shared implementation used by other certificate checks.

### 8.2 FailureBundle

Include taxonomy, evidence, implicated source objects, attempt tree, budgets, numerical state, best checkpoint and its verification scope, replay identity, and ranked suggested actions. Distinguish observations from inferred causes.

Minimum taxonomy covers structure/specification conflicts; property domain/flash/stability/reference mismatch; model domain/conservation/derivative defects; initialization and recycle failures; rank/linear/globalization failures; homotopy/PTC/active-set stalls; surrogate domain/accuracy issues; external crash/timeout; missing artifact; and budget/cancellation outcomes.

Suggested actions are typed proposals with preconditions and required permissions. They are not arbitrary code or instructions automatically executed from model output. An injected failure must not become a successful certificate through fallback.

### 8.3 Reproducibility contract

| Class | Promise |
| --- | --- |
| R0 Structural | Same canonical model and structural policy yield identical structural artifacts on supported platforms |
| R1 Controlled numerical | Same locked environment, hardware class, seed, and threads reproduce within the declared numerical policy |
| R2 Equivalent numerical | Supported differing environments reproduce target verification and specified outputs within tolerances |
| R3 Recorded external | Inputs and returned artifacts are preserved, but the provider cannot guarantee rerunning them |

Hashes exclude timestamps, job IDs, elapsed time, and other nondeterministic telemetry as appropriate. Adaptive floating-point decisions are not included in a cross-platform bitwise promise. Operation-count budgets support deterministic tests; wall-time cancellation may legitimately alter traces.

The RunManifest pins process, data, model, solver, scaling, backend, dependency artifacts, platform, threads, seeds, and policies. Replay detects missing or changed dependencies and reports whether it performed exact replay, compatible reproduction, or merely inspected archived results. User-supplied restricted data may require reattachment through authorized references.

## 9. Multi-fidelity science and uncertainty

### 9.1 Evidence hierarchy

Model families contain related models, not an automatically ordered truth ladder. CFD can have discretization error, constitutive-model error, uncertain boundaries, and statistical noise. A surrogate of CFD inherits those limitations. Maintain separate evidence for parameter uncertainty, experimental noise, numerical error, high-fidelity model discrepancy, and surrogate approximation error.

PyMRM results include boundary mapping, version, discretization settings, convergence evidence, conserved fluxes, and cost. Peclet/particle experiments additionally record mesh/time-step and averaging evidence where relevant. Failed experiments remain in the dataset with failure labels; they are not assigned fabricated outputs for regression.

DOE/training/calibration/test splits, transformations, seeds, parent-model lineage, and independent validation are immutable artifacts. Avoid leakage across shared trajectories, meshes, or nearly duplicated parameter samples. Surrogates are trained to preserve conservation where possible, for example through reaction extents or reduced conserved coordinates. Any corrective projection is explicit and its derivative is accounted for.

### 9.2 Domain and uncertainty are different

Hard admissibility constraints come from physics and the parent model. Empirical domain tests operate in scaled coordinates and may use distances, density, or other documented criteria. Convex-hull membership alone does not establish accuracy in a sparsely sampled high-dimensional interior.

**[A07 — Default uncertainty reporting]** Split-conformal is the Default reporting baseline for v0.2 surrogate prediction error; alternatives require an ADR stating the evidence, assumptions, and replacement acceptance tests. Standard split-conformal coverage is marginal under exchangeability; it is not pointwise coverage, guaranteed optimizer-selected coverage, or protection under arbitrary distribution shift. Adaptive DOE and repeated optimizer queries require special care. [Angelopoulos and Bates](https://arxiv.org/abs/2107.07511)

Freeze the predictor, transforms, and score before calibration. Draw disjoint calibration and test sets independently and i.i.d. from a registered process-relevant reference distribution associated with the DOE. Adaptive training DOE is allowed, but its adaptively selected samples are not automatically an exchangeable calibration set. Deterministic grids or Latin-hypercube designs are not labeled i.i.d. draws. Fresh random draws from the reference distribution provide the reporting baseline; targeted optimum/phase-boundary checks are additional, separately labeled evidence. Do not tune or repeatedly select models using the final test set. If independent calibration is unaffordable, report `INSUFFICIENT_EVIDENCE` or use an approved alternative instead of asserting coverage.

For scalar scores and n calibration points, record the finite-sample quantile rule, including the ceiling correction and insufficient-sample behavior. Multi-output and multi-query claims require an explicit joint-coverage construction or are labeled marginal. Noisy-data intervals are not automatically bounds on a deterministic parent model's discrepancy.

An observed held-out coverage below its nominal target is not by itself evidence that a theoretical guarantee has been violated. Promotion uses a predeclared sample-size plan, confidence interval or test, interval-width/error limits, and an independent evaluation set. For an optional initial 95% coverage profile, report a one-sided 95% coverage bound and require it to exceed a separately declared minimum acceptable coverage, default 90%; retain the nominal target and the distinction. Too few samples give `INSUFFICIENT_EVIDENCE`, not a fabricated pass. Distribution-shift checks and targeted accuracy near the selected optimum remain necessary.

### 9.3 Decision-driven refinement

Begin with sensitivities and direct discrepancy checks. For constraints close to active, require parent-model evaluation or a justified error bound with engineering margin. Cheap screening may rank candidates; final decisions must state which models and uncertainties were actually checked.

Sensitivity-weighted error is a prioritization heuristic, not an expected-value theorem. Where F(x,p,m) = 0 is locally regular, process adjoints can translate model residual discrepancy into approximate objective or constraint impact. Correlation and nonlinear effects require further checks. If rankings are indistinguishable within uncertainty, report the ambiguity.

Freeze the surrogate during a solve/optimization subproblem. Refine in a new study iteration, rerun validation, promote a new version, and re-solve. Stop on predefined decision tolerances and evidence, or budget exhaustion. Budget exhaustion is not decision stability.

## 10. Studies, optimization, and synthesis

First implement sweeps, local sensitivities, and parameter estimation; then continuous constrained optimization on a fixed topology. Studies distinguish free simulation variables from design decisions, measured data from exact specifications, and physical feasibility from optimizer termination.

For a regular reduced simulation, compute sensitivities from Fₓ xₚ = −Fₚ using the converged Jacobian, with branch and conditioning qualifications. Estimation records observation covariance, identifiability, parameter bounds, and validation data. Optimizers receive true domain restrictions; a penalty is not equivalent to guaranteed constraint satisfaction.

Use an established constrained NLP implementation through a source-mapped adapter. Reduced-space and full-space formulations share model semantics but have different execution costs and derivative requirements. Record objective, primal violations, active constraints, KKT measures where available, multistart evidence, and termination limitations. Local stationarity is not global optimality.

For eligible expensive smooth gray-box models, default to a tested trust-region framework through the Pyomo bridge before writing a new optimizer. The documented framework imposes differentiability assumptions and uses consistency corrections; arbitrary surrogate retraining does not preserve its convergence theory. [Pyomo trust-region framework](https://pyomo.readthedocs.io/en/stable/explanation/solvers/trustregion.html)

**[A06 — two distinct bridge mechanisms]** The Default general NLP bridge wraps `CompiledProblem` as a PyNumero `ExternalGreyBoxModel`/block, exposing variables, residuals, sparse Jacobian, and optional multiplier-weighted Hessian to cyipopt. Supply objective/constraint metadata and scaling consistently. Without reliable Hessians, explicitly configure a supported approximation. This numerical adapter does not hand-transpile a second flowsheet model. [Pyomo external gray-box interface](https://pyomo.readthedocs.io/en/6.6.2/contributed_packages/pynumero/pynumero.interfaces.external_grey_box_model.html)

The documented Pyomo trust-region framework instead identifies black-box calls through **Pyomo `ExternalFunction`** and builds local surrogate subproblems; it is not automatically compatible with an opaque `ExternalGreyBoxModel`. Its separate adapter must expose expensive-model inputs/outputs and a framework-supported glass-box structure, generated from the canonical model where needed, with source maps and equivalence tests. This is a compiled projection, not a separately authored physical model. Demonstrate that exact composition in the v0.2 spike. If unsupported, use an explicit ADR and a tested alternative framework; do not claim trust-region guarantees merely because the generic cyipopt bridge solves an NLP.

The adapter must expose truth-model evaluation, reliable gradients or an explicitly qualified alternative, local model construction, trust-region/filter state, rejected steps, and cost. Pin the implementation and its assumptions. Finite-budget noisy experiments, phase switches, discrete topology changes, and unsupported derivative regimes receive empirical outcomes without an inherited stationarity guarantee.

Experiment selection is a study policy: start with bounded space-filling and sensitivity-directed sampling. Multi-fidelity Bayesian optimization and information-gain methods are optional later strategies, including standalone optimization where appropriate; they are not prohibited from optimization by architecture.

Synthesis initially uses a finite declared candidate set or typed graph rewrites. Every candidate passes task-specific validation. Optimize and compare each topology with its own model and evidence; no claim of global synthesis optimality follows. TEA/LCA remain assessment adapters with currency year, location, factors, uncertainty, and provenance.

## 11. Agent and application API

### 11.1 Shared local and remote service

The canonical application contract is transport-independent. Local Python and CLI call it in process; HTTP and MCP wrap the same operations and validation. A server is optional for local modeling. Schema generation may assist binding consistency, but human-reviewed tool descriptions and bounded projections are still required.

Transactions accept an expected revision and idempotency key. They return validation, semantic diff, and downstream invalidations. Draft edits can be grouped atomically. Long work is a job with budgets, progress, cancellation, checkpoint/resume semantics, and artifacts. Retrying an idempotent request cannot duplicate an expensive experiment.

### 11.2 Minimum tool surface

| Group | Operations |
| --- | --- |
| Inspect | Summary, model registry, unit/stream/equation views, DOF report, trace slices, failure evidence |
| Edit | Begin, add/replace model, connect, set specification, preview, validate, commit, rollback |
| Execute | Compile, initialize, solve, cancel, resume compatible checkpoint, verify |
| Compare | Branch, semantic diff, compare runs, compare plans, replay |
| Study, later | Sweep, sensitivity, estimate, optimize, experiment plan, surrogate validation and promotion |

Inspection supports bounded scope and pagination; complete exports remain available as files for scripts and audits. Do not ban access to the whole process merely to protect an LLM context window. Every property/parameter value carries provenance; user assumptions are allowed if labeled, not passed off as sourced measurements.

### 11.3 Authorization and trust

Separate read, draft mutation, execution, model installation, policy administration, and publication. Authorized agents may operate autonomously within project policy, including draft commits. Policy changes are explicit transactions; ordinary solve tools cannot weaken verification. Tighter requested tolerances and budgets within authorized limits do not require a new global approval mechanism.

Models and imported text are untrusted data. Inspect manifests without executing them. External code runs through configured isolation, resource limits, network policy, and artifact access. Out-of-process execution alone is not a sandbox; isolation profiles state their actual guarantees. Signing identifies provenance but does not establish scientific correctness.

Names, citations, comments, and stdout cannot grant permissions. Envelope and bound untrusted text, retain raw artifacts, and test prompt-injection attempts. Validating data-only imports need not force a human interruption if existing policy authorizes them. Installing executable plugins is a distinct capability.

### 11.4 Evaluation

Publish internal tasks for constructing, diagnosing, repairing, replacing, optimizing, reproducing, and resisting injected instructions. Report task completion, false verification, unauthorized actions, semantic error rate, and cost separately. A no-false-verification gate is stricter than a high task-success percentage.

CRAFTS/OpenIDAES-450 is a relevant external comparator with typed stages and deterministic engineering gates. It was posted in August 2026, before v1's date; v2's claim that this evidence appeared only after v1 is not retained. Obtain and check executable artifacts, splits, and licensing before making it a gate. Adapted subsets must report coverage and cannot inherit the original benchmark's headline score. [CRAFTS paper](https://arxiv.org/abs/2608.01369)

## 12. Human workbench and interoperability

The early web workbench prioritizes model inspection, DOF diagnostics, raw/scaled residuals, attempts, phase changes, and branch comparisons. A minimal canvas follows reliable headless workflows. Equations and units are reachable from every diagnostic; education mode exposes the relevant transformations. GUI operations use the same revision and application contracts as agents.

The replay bundle contains canonical model/study files, locks, run manifests, structured events, checks, results, and hashed artifacts. This is a scientific evidence bundle, not just a connected-system description.

| Adapter | Scope and timing |
| --- | --- |
| JSON/YAML | Required v0.0; full supported semantics and replay |
| SFILES 2.0 | Bounded topology import/export in v0.2 if it supports a real comparison; round-trip topology equivalence, not full numerical semantics |
| Pyomo | Optimization and diagnostics bridge in v0.2, with explicit unsupported operations |
| FMI/SSP | Later external-model/system exchange; preserve separate scientific evidence bundle |
| DEXPI | Later process/plant diagram handover with explicit missing simulation specifications |
| CAPE-OPEN | Later property integration when an actual package justifies deployment and platform work |
| JSON-LD/ontology | Later projection driven by a consumer; not the IR foundation |

SFILES provides topology representations; SSP provides system structure/parameterization including FMUs; DEXPI 2.0 covers process and plant information. These are useful boundaries but not interchangeable complete process-simulation schemas. Every adapter reports losses and unsupported semantics. [SFILES implementation](https://github.com/process-intelligence-research/SFILES2), [SSP standard](https://ssp-standard.org/), [DEXPI specifications](https://dexpi.org/specifications/)

## 13. Validation and benchmarking

### 13.1 Test hierarchy

1. Mathematical kernels: matching, SCC/BTF/DM, scales, sparse assembly, steps, continuation and eligible PTC.
2. Model conformance: dimensions, balances, domains, limits, initialization, derivatives, state mapping.
3. Coupled systems: recycles, heat coupling, phase disappearance, design specifications, multiple roots.
4. Independent comparisons: analytical cases, different implementations, then measured data where available.
5. Robustness: published initial-state and parameter ensembles, typed external failures, bounded recovery.
6. API/replay: transactions, idempotency, stale revisions, budget/cancel, policy enforcement, artifact integrity.
7. Agent tasks: semantic correctness, useful diagnosis, unsupported requests, injection resistance, cost.

Correctness fixtures have analytically or independently established expectations. Self-generated golden results are regression tests, not validation. Test the verifier adversarially: for example, introduce a balanced-looking but wrong reaction energy or an unauthorized relaxed specification.

### 13.2 Essential adversarial inventory

| Category | Cases |
| --- | --- |
| Structure | Missing/excess spec; square structural defect; numerically dependent equations with valid matching; optimization decisions |
| State | Zero-flow stream; zero component; component permutation; mass/molar conversion; absolute/difference temperature |
| Numerics | Very unequal variable scales; rank loss; small-step stagnation; invalid line-search trial; exact initial root |
| Recycle | Analytic linear loop; high gain; oscillation; nested loop; heat-coupled loop; alternate tearing |
| Thermodynamics | TP/PH; single/two-phase transition; trivial root; reference mismatch; unsupported critical or multiphase state |
| Cache/derivatives | Nearby unequal states; finite-difference perturbation; changed data/reference; inner solve tolerance; cache on/off equivalence |
| Continuation/PTC | Incomplete homotopy endpoint; artificial unstable dynamics; inconsistent algebraic start; multiple valid roots |
| Model substitution | Domain mismatch; missing pressure semantics; changed model mid-run rejected; conservation after promotion |
| External/agent | Timeout, noise, missing artifact, duplicate job retry, prompt injection, forbidden policy change |

### 13.3 Comparisons and independence

DWSIM and IDAES are the principal independent process implementations; BioSTEAM is useful for overlapping conceptual/assessment cases. Property libraries provide additional comparisons, but shared correlations and datasets are disclosed. For columns, ChemSep is an optional additional reference, with access and redistribution handled under its actual terms; its public site advertises a free LITE edition, which does not by itself establish an open-source grant. [ChemSep overview](https://www.chemsep.org/)

Every comparison fixes chemical data, equations, property methods, reference states, units, phases, specs, initial conditions, budgets, and acceptance tolerances before results are collected. Report `AGREE`, `DISAGREE`, or `NOT_COMPARABLE`, with an explanation field. A justified explanation is not automatically numerical agreement. Nonconvergence and unsupported cases stay visible.

### 13.4 Reporting and proposed gates

Publish raw per-case results, failures, time distributions, and robustness fractions with confidence intervals. Use Dolan–Moré profiles for positive comparable costs and appropriate data profiles for fixed-budget robustness. Cross-algorithm iteration counts often have different meanings; record them but do not force a misleading profile. Zero counts and timer resolution require an explicit convention. [Dolan and Moré](https://arxiv.org/abs/cs/0102001)

Separate cold compilation, initialization, numerical solve, verification, and total time. Compare warm starts and caching under the same conditions. Report property calls only when their counting semantics align, otherwise keep them within-platform diagnostics. Include median and tail latency and a shifted geometric mean only with the shift stated.

Proposed v0.1 gates are: all fixed nominal correctness fixtures pass; all injected invalid structural cases are rejected for the right reason; no false `VERIFIED` result in the adversarial suite; and at least 95% verified success over a registered supported-domain initial-guess ensemble. Use at least 20 eligible cases × 20 published initial guesses, report per-case rates and uncertainty, and do not treat correlated attempts as independent without qualification. Initial-guess campaigns hold valid specifications fixed; separate parameter campaigns enumerate infeasible and unsupported instances.

**[A04 — register the sampling law]** The ensemble registry MUST include executable generator/version/hash, seeds and random-number algorithm, reference initial state and its provenance, perturbed free variables, scales and coordinate transforms, support widths, probability distributions/correlations, initial phase assignments, and domain/rejection/projection rules. Save generated states as artifacts. Do not perturb fixed specifications. Count and report rejected/projection-adjusted draws; no replacement after seeing solver outcomes.

The Default nominal robustness profile perturbs each selected scaled free coordinate independently with Uniform[−0.2, 0.2] about a registered model-initializer state. This is ±20% of the declared variable scale, not necessarily ±20% of its value. Use rejection sampling for declared hard domain constraints and a registered retry cap; record the resulting conditioning and any generation failures. Zero-flow/composition and phase constraints require a valid parameterization or explicit special cases, not silent clipping. The initializer reference is fixed before campaign scoring and must not be a hidden converged answer. Full-bound-box, log-wide, and phase-boundary stress profiles are separate campaigns with their own generators and scores; the nominal 95% gate does not claim success over those larger domains.

Default development policies may use a scaled nonlinear residual target of 10⁻⁸ and a 50-iteration local Newton limit, with bounded outer attempts. These are tunable numerical starting points, not blanket engineering tolerances or performance claims. Phase-0 fixtures register physical tolerances and CPU/evaluation budgets before algorithms are scored. Threshold changes require versioned evidence and cannot be retroactive.

## 14. Delivery roadmap and acceptance

### 14.1 Planning basis

Capacity assumption: two to four full-time-equivalent contributors with identifiable numerical and process-modeling expertise, supported by coding agents. Durations below are planning estimates for that capacity, not evidence-backed promises. Part-time academic leadership and agents alone require a revised capacity plan. Reduce breadth before weakening source mapping, verification, and reproducibility.

| Release | Incremental planning allowance | Required outcome | Explicitly outside that gate |
| --- | --- | --- | --- |
| Phase 0 | 2 weeks | Backend/callback and distribution spike; semantic rules; synthetic case; registered tolerances; first ADRs | Full framework, production service |
| v0.0 | 4–6 weeks | Ideal recycle vertical slice, trace, checks, failure, replay, local transactions | General PTC, optimization, GUI, real-data breadth |
| v0.1 | 10–14 weeks | Transparent SM/EO kernel, homotopy, one PTC family, small agent binding, robust tests | Columns, broad adapters, advanced UQ |
| v0.2 | 12–16 weeks | PyMRM replacement, one nonideal pathway, surrogate lifecycle, fixed-topology optimization, diagnostic web shell | Two column algorithms, general synthesis, mandatory CFD jobs |
| v0.3 | Re-estimate after v0.2 | Validated equilibrium-stage column and stronger separations/heat integration | Rate-based columns and universal property coverage |
| v1 | Evidence-driven | Stable research release within published envelope; independent user reproduction | Unqualified industrial parity or global convergence claims |

### 14.2 v0.0 acceptance

- Three-component synthetic ideal TP-flash process with feed/product, heater, mixer, splitter/purge and one numerical tear.
- One damped Newton path on the tear residual with native residual/Jacobian evaluation; the expression engine and callback route both pass small interface fixtures.
- Canonical revision, parameter/data locks, source mapping, local CLI and Python operations.
- Serialized RunManifest, SolveEvent, SolutionCertificate, FailureBundle, and replay bundle.
- Independent material and energy checks; one phase transition, one bad specification, and one numerical failure.
- Replay detects a changed dependency or input; structural hashes agree on two supported CI environments.
- A reviewer can follow one complete run from input to every acceptance check without reading unrelated packages.

Do not fabricate a historical schema migration merely to claim migration coverage. Provide migration infrastructure and add a real migration when the schema changes.

### 14.3 v0.1 acceptance

- Semantic diff, immutable drafts, task-specific validation, units and component/reference checks, real migration fixture if applicable.
- Core models: network units, heater/cooler, TP/PH flash, component separator, conversion reactor, simple valve and liquid pump, one two-stream exchanger formulation. Equilibrium reactors and elaborate equipment modes are deferred unless already needed by a case.
- DM/SCC/BTF diagnostics, block statistics, safeguarded recycle solve and a coupled EO block, physical scales before iteration, model initialization and warm starts.
- One typed homotopy, one PTC family qualified by §7.5 with tested SER control, and three tested recovery edges with budgets, rollback, and unchanged target semantics. **[A03]**
- Phase disappearance/reappearance with frozen-attempt/restart tests; cross-unit specification promotion to EO without nested SM loops; and a multiple-root example with honest branch reporting. **[A01/A02]**
- At least 30 distinct correctness/diagnostic cases; eight shared-model comparisons across DWSIM and IDAES, at least two using both where feasible. Registered robustness ensemble from §13.4.
- Local transactions and small HTTP/MCP surface for inspect, edit, validate, solve, diagnose, and reproduce. At least ten versioned agent tasks; target 80% completion with zero unauthorized policy changes or false verification in the suite.
- Dependency/data provenance gates, including the binary inventory of §3.1; final target-Jacobian regularity diagnostics and qualified energy checks; no enabled recovery edge without a direct failure test. **[A08/A09/A10]**
- Real-chemistry reference journey selected and specified for v0.2 with data and comparison feasibility established.

### 14.4 v0.2 acceptance

- PyMRM adapter with port mapping, accuracy contract, out-of-process execution policy, timeout, provenance, and parent-model validation.
- One additional validated nonideal property route sufficient for the selected chemistry; no requirement to ship two adapters merely to satisfy an interface count.
- Surrogate training/promotion with conserved quantities, independent errors, domain enforcement, derivative tests, and Default split-conformal reporting under §9.2, or an ADR-approved alternative. Coverage at adaptively chosen optima is not implied. **[A07]**
- Fixed-topology continuous optimization with final parent-model checks; a tested trust-region adapter for one eligible smooth gray-box example, with assumptions and costs reported.
- End-to-end reactor refinement workflow reports before/after decisions, constraints, discrepancy and compute cost. Insufficient evidence or exhausted refinement budget remains a valid honest outcome.
- Diagnostic web shell supports inspection, traces, revision comparison, and agent history through public contracts.
- External benchmark adaptation attempted with exact provenance and coverage; inaccessible artifacts are reported and do not block core scientific acceptance.

### 14.5 v0.3 separation acceptance

Build an equilibrium-stage MESH column with explicit component and energy balances, equilibrium relations, summation/state conventions, pressure profile, feeds, condenser and reboiler, stage indexing, and valid specification combinations. Initialization uses staged activation and continuation. Ship one trustworthy full-Newton strategy first; add inside-out only after a measured need.

A countercurrent equilibrium-stage subsystem is the precursor. A once-through flash train is not claimed to reproduce column coupling. Gates include at least four matched column cases, phase disappearance, infeasible specs, convergence perturbations, and at least two independent references across the suite when available. Nonideal and azeotropic cases are included only with validated data and supported phase behavior.

### 14.6 v1 acceptance

Stable documented contracts; at least 100 scientifically distinct benchmark cases and 25 cross-implementation comparisons; versioned robustness and performance reports with at least 95% verified success on the registered supported-domain ensemble within its budgets; no known unresolved false-verification defect; independent users reproduce the reference workflows and add a unit without core modifications. Support a constrained optimization and finite synthesis demonstration with qualified evidence, a usable web workbench, and documented deployment/maintenance ownership.

An asynchronous Peclet/CFD refinement demonstration is part of v1 only if the project has an actual validated model family and compute provision. It is otherwise explicitly labeled experimental rather than implemented as an empty orchestration showcase.

## 15. Repository, governance, and risk controls

| Area | Initial responsibility |
| --- | --- |
| `schemas/`, `src/ir/`, `src/units/` | Semantic contracts, canonicalization, quantities, migrations |
| `src/models/`, `src/thermo/` | Models, states, property adapters, exact caches, conformance kit |
| `src/compile/`, `src/graph/` | CompiledProblem, backend/callback lowering, source mapping, structure |
| `src/numerics/`, `src/orchestrator/` | Numerical methods, policies, attempts, verification, replay |
| `src/application/`, `clients/` | Transactions, local service, CLI/Python and HTTP/MCP bindings |
| `src/studies/`, `src/adapters/` | Later optimization, uncertainty, PyMRM and experiments |
| `apps/web/`, `src/interop/` | Later workbench and exchange adapters |
| `benchmarks/`, `tests/`, `examples/`, `docs/` | Evidence, failure cases, executable tutorials, ADRs and method derivations |

Start as one installable package with optional extras. Split distributions only when dependencies or release lifecycles justify it. Optional dependencies cannot change default algorithms merely by being installed.

The intended core license is Apache-2.0; adoption requires that the project has the rights to distribute its contributions. The license text is authoritative, not this design summary. The default install must not require GPL-licensed components; optional reference-tool environments are separate. Audit exact dependency versions, transitive binaries, optional plugins, and notices; do not reproduce v2's blanket assumptions about every solver or linking arrangement. Disabling a bundled plugin does not itself establish that distributing its bytes meets this policy. **[A10]** The wheel/plugin inventory and distribution verdict required by §3.1 are named Phase-0 deliverables and are refreshed when the selected binaries change. [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)

Parameter records carry source, rights metadata, attribution, scope of authorized use, and distribution policy. Unknown rights are not assumed redistributable. User-supplied data can be used within its permitted scope. Portable exports may omit restricted bytes and retain references; report replay dependencies clearly. A boolean redistribution flag alone cannot decide all private export and public publication cases.

Name a maintainer and reviewer for every supported subsystem. Keep a dependency budget, deprecation policy, contribution guide, release ownership, and maintenance allocation. Distinguish supported, experimental, and archived modules. A maintainer departure triggers reassignment or a published support downgrade.

| Risk trigger | Required response |
| --- | --- |
| Backend spike exceeds ten working days | Decide on the demonstrated alternative; stop general backend abstraction work |
| v0.0 fails to produce a replayable recycle after eight implementation weeks | Freeze breadth, isolate blockers, simplify packaging/model scope; retain verification |
| Thermodynamic integration consumes more than one planned iteration without a conformance case | Return to a narrower validated package; defer affected chemistry |
| PTC lacks a defensible mapping or improves no tested basin | Keep it experimental; do not auto-enable it from block size alone |
| False verification found | Disable the defective path, identify affected releases/runs, add adversarial regression, then restore |
| Surrogate error changes active constraints or design ranking | Require parent-model checks/refinement; qualify the decision |
| GUI or interop displaces a scientific gate | Defer the front-end/adapter feature |
| A dependency or subsystem has no sustainable owner | Reduce supported scope or replace it through an ADR |

Tests are risk-based. Exercise every enabled recovery transition, transaction conflict, certificate branch, and migration behavior; use coverage as a diagnostic. Do not assert exhaustive mathematical correctness from 100% branch coverage. Numerical changes require derivation or a reference, adversarial tests, trace comparison, and relevant benchmark results.

## 16. Implementation-agent handoff

Produce these concrete outputs in order:

1. **Requirements ledger:** map D01–D20 and each release gate to owning module, work item, dependency, acceptance test, and evidence artifact.
2. **Initial ADRs:** default backend/callback boundary; explicit SuperLU path; state and zero-flow semantics; phase policy; rights/distribution audit; structural/numerical reproducibility split. Record defaults rather than reopening an unlimited technology survey.
3. **Executable Phase-0 spike:** matched CasADi and Pyomo/PyNumero/ASL fixtures, sparse property-callback composition checks, first/optional second derivative evidence, source mapping, common sparse solve, binary/plugin inventories, and a selection ADR. **[A05/A10]**
4. **Normative schemas:** ProcessRevision, ModelManifest, EvaluationResult, CompiledProblem metadata, SolvePlan/Event, RunManifest, SolutionCertificate, FailureBundle, and transaction/job states. Add study/surrogate schemas when their vertical slice begins.
5. **Six-week v0.0 work plan:** weekly demonstrable outcomes, critical path, owner roles, uncertainties, and explicit scope cuts if the spike fails.
6. **Benchmark registry:** equations, physical data, provenance, tolerances, budgets, expected failure classes, reference versions, independence assessment, and executable ensemble generators with distributions, domain handling, and saved initial states. **[A04]**
7. **v0.1 implementation plan:** dependencies and estimates for SM/EO, scaling, homotopy, one PTC family, phase handling, agent tasks, and verification gates.
8. **Later backlog:** separate mandatory v0.2 reactor integration from v0.3 columns and optional research methods. Each research item states a hypothesis, evidence needed, and fallback if unsuccessful.

The first demonstrable result must be a small, interpretable process solve with trustworthy failure and replay behavior. Subsequent releases broaden the physics and autonomy while preserving that contract. Numerical success, scientific credibility, and useful engineering decisions must remain separately inspectable throughout.

## Appendix A. Minimum evidence schemas

| Schema | Essential fields beyond identity/version |
| --- | --- |
| EvaluationResult | Input/state hash, output/residual, validity, accuracy, derivative provenance, phase signature, cost |
| SolvePlan | Structure hash, blocks/order, cross-unit spec regions, tears, scales, initialization, frozen phase signature/restart policy, PTC/SER parameters, budgets, deterministic tie-breaks **[A01/A02/A03]** |
| SolveEvent | Sequence, attempt/block, event type, metrics, implicated source IDs, policy rule, artifact refs; timing separate |
| SolutionCertificate | Target hash, check-policy hash, verification status, per-check value/tolerance/scope, final target-Jacobian regularity evidence, shared-provider independence qualifications, phase/branch, transformations, limitations **[A08/A09]** |
| FailureBundle | Observed category, hypotheses, causal evidence, attempts/budgets, checkpoint scope, proposed actions, replay refs |
| ModelEvidence | Parent/data hashes, numerical convergence, experimental/reference comparisons, uncertainty and validation scope |
| SurrogateManifest | Parent model, input/output mapping, splits, transforms, error/gradient metrics, domain, calibration assumptions, promotion result |
| OptimizationReport | Model/study hash, candidate, feasibility, stationarity evidence, truth evaluations, domains, starts, budget and limits |
| RunManifest | Model/data/solver/backend/dependency hashes, environment, threads/seeds, policies, artifacts, parent run, reproducibility class |

## Appendix B. Evidence audit of version 2

The following distinctions explain why some strong v2 prescriptions were not carried forward:

- **AD and potentials:** valuable implementation tools; neither mathematical-model correctness nor a complete property package follows from AD alone.
- **PTC:** supported as a process method, with problem-dependent reformulation and attraction properties; “changes the path but not the answer” is too strong when multiple steady states exist.
- **Conformal prediction:** exchangeability-qualified marginal coverage; not automatic coverage at adaptively selected process optima. Finite test coverage is a statistical estimate.
- **Trust-region methods:** useful under stated model, smoothness, accuracy, and algorithm assumptions; not a universal guarantee for arbitrary model families or topology search.
- **BTF/DM:** retain diagnostics and measured computational benefits. Do not equate structural matching with numerical rank or automatic identification of minimal specification conflicts.
- **ChemSep:** useful comparison software; free access does not prove open-source redistribution rights.
- **2026 agent evidence:** CRAFTS/OpenIDAES-450 is verifiable, but predates v1's stated date. Other loosely named v2 studies are not release dependencies without exact sources and accessible artifacts.
- **SSP and DEXPI:** established exchange scopes justify adapters; they do not remove the need for simulation-specific provenance, solver traces, and verification records.
- **Timing and maintenance assertions:** treated as planning risks and estimates rather than universal empirical laws. No unsupported claim that one method is the most effective or one project failure mode is dominant is needed to justify this design.

The linked primary documentation and papers establish method availability and limitations. Exact installed versions and artifact licenses must be pinned during implementation; the links themselves are not a dependency lockfile.
