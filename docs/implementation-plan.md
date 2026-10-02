# Agent-Native Open Process Simulator — Coding-Agent Implementation Plan

**Plan version:** 1.2 (v1.1 folded in fixture verification findings, package fine-tuning, the working protocol and the lane assignment; v1.2, 2026-09-24, restates that protocol as two lanes instead of two named models — terminology only: no package, order, gate or acceptance item changed)  
**Date:** 6 September 2026  
**Architectural authority:** `docs/blueprint-v3.1.md`  
**Baseline SHA-256:** `66f574b07e86a89962236f4a48850e733f3c03379a3a55caf78ef30f7915e8aa`  
**Status:** Execution-ready work plan; the simulator, integrations, and benchmark results described here have not been implemented by this planning task.  
**Audience:** Coding agents working in two lanes — a design lane and a build lane (§1.3) — with Frank Peters and designated numerical/process-modeling reviewers.

## 1. Execution contract

Implement blueprint v3.1 through the work packages below. The blueprint owns scientific invariants and release requirements; this plan supplies task order, initial fixtures, artifacts, and verification procedures. Treat earlier blueprint versions as historical. Where the documents conflict, preserve v3.1 and record the conflict before changing this plan.

The first objective is a reproducible **v0.0 flash–recycle vertical slice**, including an informative failure. Then deliver the v0.1 solver and bounded agent workflow, followed by v0.2 reactor-model replacement. Do not start columns, broad thermodynamic coverage, or GUI polish before their dependencies and release gates are met.

Execute work rather than producing another general implementation plan. At each work package, inspect existing code, implement the smallest complete slice, run its acceptance checks, record evidence, and commit a coherent change when repository policy permits. Do not replace numerical methods with placeholder success responses. Unimplemented capabilities return explicit unsupported results.

Two lanes share this plan: a **design lane** and a **build lane** (§1.3). Owner labels (`NUM`/`MOD`/`SYS`) denote required expertise; the *Lane* column in each package table names the lead and second lane under §1.3 and §4.0. Which model and effort level serves each lane is an operational choice recorded in the agent definitions, not in this plan. Independent lanes may be assigned to additional authorized contributors once shared interfaces are fixed. Do not invent reviewer approvals or imply that agents' generated tests are independent scientific review.

### 1.1 Autonomous decisions and escalation

Proceed autonomously with reversible implementation choices, repository-local edits, tests, documentation, and corrective work within the approved scope. Follow the repository's actual `AGENTS.md` and existing authorization. Do not ask Frank to choose ordinary class names, testing tools, or file organization.

Escalate with concrete evidence only when a scientific requirement must change, rights or external access are unresolved, costly compute exceeds existing authorization, or an irreversible external action is needed. A blocked optional adapter does not stop unrelated core work. A failed release requirement remains failed: do not remove it from the denominator or silently weaken the gate.

### 1.2 Persistent progress files

Create these repository artifacts early and maintain them throughout:

| File | Purpose |
| --- | --- |
| `docs/blueprint-v3.1.md` | Exact authoritative baseline, with source hash |
| `docs/implementation-plan.md` | This plan, with versioned amendments |
| `docs/requirements.yaml` | Requirement → work package → test → evidence → status |
| `docs/progress.md` | Completed packages, current package, next executable action, blockers |
| `docs/adr/NNNN-*.md` | Bounded decisions with alternatives, measurements, and consequences |
| `benchmarks/registry.yaml` | Case semantics, tolerances, generator, budgets, and reference identity |
| `evidence/<package>/<commit>/manifest.json` | Commands, environment, inputs, results, artifacts, and verdict |
| `docs/support-matrix.md` | Implemented and validated scope, experimental paths, limitations |

`docs/progress.md` must be sufficient to resume after a context reset. Evidence files distinguish `planned`, `implemented`, `tested`, `reviewed`, and `released`. These states are not interchangeable.

### 1.3 Two-lane working protocol

**Assumption.** The design lane runs at the highest reasoning effort and costs most per turn; the build lane is the high-throughput implementation lane. Assignments are by *task type* — judgment, derivation, and adversarial verification versus volume implementation, scaffolding, and integration — so if the cost ranking differs in practice only the budget expectation changes, not the assignment logic.

**Operative rule.** If a task has no test that would catch its failure, it is a design-lane task. If it does, it is a build-lane task, with design-lane review whenever it touches residuals, derivatives, phase logic, scaling, certificates, or replay identity.

**The design lane owns:** scientific semantics (units/state/zero-flow, sign conventions, reference states), all derivations (SYN-001, PTC mapping, sensitivities), the backend decision and every ADR, the phase-attempt controller design, scaling and globalization policy, certificate and regularity policy, adversarial verifier tests, benchmark registration and reference-comparison verdicts, and review of any build-lane package in those areas.

**The build lane owns:** repository bootstrap, packaging, CI, dependency and binary inventories, schemas and round-trip fixtures, canonicalization, the application/transaction layer, CLI and Python/HTTP/MCP bindings, job lifecycle, replay bundle mechanics, unit-model library implementation from design-approved equations, property-provider plumbing and caches, adapters, the web shell, reference-environment acquisition, test-suite generation for stated specifications, documentation, and review of design-lane packages for coverage and hygiene.

**Protocol.**

- *Interface freeze.* The Protocol signatures in §2.1 and the schema list in §2.2 are frozen at the end of P01 and thereafter change only by a design-lane ADR. Build-lane work builds against frozen interfaces and may not widen them unilaterally.
- *Branch discipline.* One branch per work package; the lead lane owns it; merge to main only after the package's evidence manifest exists with `status: tested`. No cross-lane edits to another package's files without a handoff note in `docs/progress.md`.
- *Cross-review, never self-review.* A lane may not set `reviewed` on its own package. The design lane reviews every build-lane package touching residuals, derivatives, phases, scaling, certificates, or replay identity. The build lane reviews design-lane packages for test coverage, packaging, and documentation completeness. Human numerical/process-modeling sign-off remains as in §7.
- *Escalation between lanes* is a written note in `docs/progress.md` naming the blocker, the evidence, and the smallest change requested. The build lane does not resolve a scientific ambiguity by choosing; it escalates to the design lane. The design lane does not resolve a tooling/packaging ambiguity by improvising; it delegates to the build lane with a stated acceptance test.

## 2. Repository and first interfaces

If an existing repository is supplied, inspect it before scaffolding. Preserve useful conventions, tests, and user work. If none exists, start one local package with provisional import name `process_runtime`; naming or branding is not a Phase-0 blocker. Do not publish or reserve a public package name as part of this plan.

Use a `src/process_runtime/` layout with modules `ir`, `units`, `models`, `thermo`, `compile`, `graph`, `numerics`, `orchestrator`, and `application`. Introduce `studies`, `adapters`, and clients when their packages start. Keep `schemas/`, `tests/`, `benchmarks/`, `examples/`, and `docs/` alongside it. Empty future service packages are unnecessary.

Python/NumPy/SciPy and explicit SuperLU remain the baseline. CasADi is provisional until the named Pyomo/PyNumero/ASL comparison closes. Pin exact working versions in the implementation environment; do not select a package version solely because it is newest. Reuse existing project tooling where suitable; otherwise use a conventional Python build, pytest, static typing, formatting/linting, and a dependency lock. Audited optional dependencies live in explicit extras or isolated reference environments.

### 2.1 Interface decisions to fix in P01

These are proposed signatures to make the first slice concrete, not a demand for an extensive framework:

```python
class CompiledProblem(Protocol):
    metadata: CompiledProblemMetadata
    def residual(self, x, context) -> EvaluationResult: ...
    def jacobian(self, x, context) -> JacobianResult: ...
    def reconstruct(self, x, context) -> ProcessState: ...

class PropertyProvider(Protocol):
    def describe(self) -> PropertyCapabilities: ...
    def evaluate_phase(self, request, context) -> PropertyResult: ...
    def flash(self, request, context) -> FlashResult: ...

class Application(Protocol):
    def validate(self, revision_id, task) -> ValidationReport: ...
    def commit_change(self, change, expected_revision, idempotency_key): ...
    def solve(self, revision_id, policy_id) -> RunResult: ...
    def reproduce(self, bundle_path, policy) -> ReplayReport: ...
```

Use typed immutable metadata and dense numerical state vectors; sparse Jacobians have a documented CSC ordering. Declare row and column IDs and source maps explicitly. `EvaluationResult` carries status, active-set signature, state/model hash, accuracy information, and evaluation counters. Do not use a mutable global property provider.

`EvaluationContext` pins model/data versions, phase signature, accuracy policy, and run-local workspace. The outer active-set controller constructs a new context after a phase restart. `jacobian` and `residual` must describe the same function at the same state.

Canonical metadata is serializable; executable objects remain runtime-local. Optional JVP/VJP/Hessian capabilities are negotiated. A missing exact Hessian cannot be replaced with fabricated zeros.

### 2.2 Initial schema delivery order

| Package | Schemas to implement and exercise |
| --- | --- |
| P01 | ProcessRevision, Quantity, ComponentRecord, ModelManifest, Specification, ValidationReport |
| P02/K01 | CompiledProblem metadata, EvaluationResult, Jacobian metadata, PropertyCapabilities |
| K03 | SolvePolicy, SolvePlan, SolveEvent, AttemptContext, Checkpoint metadata |
| K04/K05 | SolutionCertificate, FailureBundle, RunManifest, replay artifact manifest |
| K06/T07 | ChangeSet, Job, job events, authorization capability references |
| M01–M04 | ExperimentRequest/Result, ModelEvidence, Study, SurrogateManifest, OptimizationReport |

Implement JSON Schema and round-trip fixtures as each schema is used. Do not design every future field in advance. Test a real migration when a schema actually changes.

## 3. Concrete first scientific fixture

### 3.1 Purpose and assumptions

Implement `SYN-001`, an explicitly synthetic three-component ideal vapor/incompressible ideal-liquid package. It isolates numerical behavior from real-data selection. A, B, and C are artificial pseudo-components with molecular weights 0.100 kg/mol. Do not assign real chemical identifiers or claim experimental/elemental validation. Component and mass balance are defined; elemental validation is `NOT_APPLICABLE` for this fixture.

Constants:

| Parameter | A | B | C |
| --- | --- | --- | --- |
| Reference boiling temperature, K | 320 | 360 | 400 |
| Vapor reference enthalpy offset Lᵢ, J/mol | 25,000 | 30,000 | 35,000 |
| Phase heat capacity cₚ, J/(mol K) | 100 | 100 | 100 |
| Liquid molar volume vᵢ, m³/mol | 0.0001 | 0.0001 | 0.0001 |

Set Tᵣ = 300 K, Pᵣ = 100,000 Pa and R = 8.31446261815324 J/(mol K). Use a declared test domain 280–440 K and 50,000–200,000 Pa, with no critical-region or extra-phase claim. For pure components define

\[
a(T)=c_p[(T-T_r)-T\ln(T/T_r)],
\]

\[
g_i^L=a(T)+v_i(P-P_r),\qquad
g_i^V=a(T)+L_i-TL_i/T_{b,i}+RT\ln(P/P_r).
\]

Add ideal mixing chemical potentials RT ln xᵢ and RT ln yᵢ in their respective phases. Then

\[
h_i^L=c_p(T-T_r)+v_i(P-P_r),\qquad
h_i^V=c_p(T-T_r)+L_i,
\]

\[
K_i(T,P)=\frac{P_r}{P}\exp\left[
\frac{L_i}{R}\left(\frac1{T_{b,i}}-\frac1T\right)
+\frac{v_i(P-P_r)}{RT}\right].
\]

Derive these relations in the fixture documentation and verify h = g − T∂g/∂T and phase-equilibrium consistency. These constitutive assumptions are deliberately simple. Handle zero components by appropriate limits and inactive-variable semantics; never evaluate ln(0) unguarded.

At 360 K and Pᵣ, K ≈ (2.8406442066, 1, 0.3105797512). These values are sanity checks; derive full-precision fixture values from the definitions.

### 3.2 Reference flowsheet

Fresh feed: component flows (1, 1, 1) mol/s, 300 K, Pᵣ, liquid. Mix with the liquid recycle; heat to 350 K; flash isothermally at 360 K and Pᵣ with explicit flash duty. Send vapor to product. Split liquid into recycle fraction r = 0.5 and purge fraction 1 − r. All pressure drops and shaft work are zero in this case. The heater is modeled from the start as a unit with a **TP-state outlet** (a TP flash at the specified outlet temperature with computed duty), so a two-phase outlet is a supported result. This matters: the equimolar fresh feed has a bubble point of 347.44 K at Pᵣ, so at r = 0 the 350 K heater outlet is two-phase (Σ zᵢKᵢ(350 K) = 1.070), while for r = 0.5 and r = 0.95 the lighter-depleted mixed feed remains subcooled (0.962 and 0.792). The r = 0 variant is therefore registered as a phase-appearance case, not treated as an accident. The adiabatic mixer uses an enthalpy closure with a bracketed scalar thermal solve restricted, in v0.0, to the subcooled-liquid domain with a typed failure outside it; general PH support is T05.

Use an adiabatic mixer with component and energy balances. Both heater and flash duties are calculated unknowns; their specified outlet temperatures are not additional fixed duties. The liquid recycle is at flash temperature. Choose component recycle flows as the initial tear vector; temperature and pressure of this particular recycle are known from the flash specification. Do not generalize that reduced tear choice to arbitrary flowsheets: T01 must derive tear dimension from the incidence graph, and a test must confirm that T01 rediscovers this three-variable tear rather than having it hard-coded.

A direct reference bypasses the iterative flowsheet traversal. Let q = V/L and a = 1 − r. Solve

\[
\sum_i\frac{(K_i-1)F_i}{a+qK_i}=0,\qquad
L=\sum_i\frac{F_i}{a+qK_i},\quad
x_i=\frac{F_i}{L(a+qK_i)},\quad y_i=K_i x_i.
\]

For the nominal case, q ≈ 0.4150855900, L ≈ 3.2783818616 mol/s, V ≈ 1.3608090692 mol/s, x ≈ (0.1816607866, 0.3333333333, 0.4850058800). This reduced scalar calculation was checked during plan preparation and independently re-verified for plan v1.1 (K-values, oracle, and the phase state of every registered variant). It is an algebraic reference for the synthetic model, not an experimental validation or a simulator benchmark result. Implement the oracle separately from the production flash/recycle solver.

Check fresh-feed component flow = vapor product + liquid purge. **Register the recycle-invariance metamorphic check:** because the flash is isothermal-isobaric and recycles its own saturated liquid at the same T and P, the overall system is equivalent to a single flash of the fresh feed — V, x, and y are identical for every r and only L scales as 1/(1 − r) (L = 1.639, 3.278, and 32.78 mol/s at r = 0, 0.5, 0.95). Vapor product and phase compositions must agree across r to the oracle tolerance. The corollary is that the SYN-001 tear map is benign: it stresses throughput scaling, not composition–energy coupling, and T06 must not count r-variants as distinct recycle-difficulty cases. Check total heater plus flash duty against external-product enthalpy minus fresh-feed enthalpy. Internal recycle energy cancels. Separately assembled energy bookkeeping shares the same synthetic thermodynamics and must be labeled as such.

### 3.3 Variants and initial tolerances

Register nominal r = 0.5; once-through r = 0 (two-phase heater outlet, see §3.2); high recycle r = 0.95; flash at 310 K for an all-liquid case (Σ zᵢKᵢ = 0.328, zero vapor product); flash at 420 K for an all-vapor/zero-recycle case (Σ zᵢ/Kᵢ = 0.317). Also register a conflicting heater T-and-duty specification and a deliberately capped solve budget.

For the synthetic nominal fixture, propose component-balance tolerance 10⁻⁹ mol/s + 10⁻⁸ times registered throughput; energy tolerance 10⁻⁵ W + 10⁻⁸ times a registered 10⁵ W scale; T tolerance 10⁻⁶ K; P tolerance 10⁻² Pa; normalized-composition tolerance 10⁻¹⁰. These are preimplementation synthetic-fixture choices and must be confirmed against oracle/evaluation accuracy in P01, before comparative scoring. Do not apply them universally to real processes.

Include a separate analytic linear recycle t = f + rt, with solution t = f/(1−r), to isolate solver behavior without a flash.

## 4. Delivery order and work packages

Dependencies below are required predecessors; a package may additionally consume a stable interface from an earlier package. A package is complete only when its named evidence is retained. `NUM` denotes numerical-methods expertise, `MOD` process-modeling expertise, and `SYS` software/platform expertise. One person or agent can implement multiple roles; scientific review is separately recorded.

### 4.0 Lane column

Each package row carries a *Lane* column of the form `Lead / Second`. The lead lane owns the branch and the evidence manifest; the second lane implements to the lead's specification (when Design leads) or reviews (when Build leads), per §1.3. A dash means no second lane is required.

### 4.1 Phase 0 — resolve actual blockers within ten working days

| ID | Work and dependencies | Acceptance evidence | Owner | Lane (lead / second) |
| --- | --- | --- | --- | --- |
| P00 | Inspect repository, baseline tests and instructions; record blueprint hash; bootstrap package and progress/requirements ledger. No dependencies. | Clean baseline report, reproducible environment, no overwritten user work, initial requirement statuses. | SYS | Build / — |
| P01 | After P00: define SI/state/zero-flow semantics and SYN-001; initial metadata schemas and independent scalar oracle. | Derivation, unit/reference tests, oracle outputs, registered tolerances and fixture inputs; initial ADRs. | MOD/NUM | Design / Build |
| P02 | After P01: build matched CasADi and Pyomo/PyNumero/ASL spikes through a minimal CompiledProblem boundary and common SuperLU solve. | Values, sparse assembled Jacobian, directional/chain-rule checks, callback pattern/count, compilation vs evaluation costs, source-map example, capability limitations. | NUM | Design / Build |
| P03 | After P02: complete exact binary/plugin inventories; select backend and close Phase-0 ADR. Inventory work starts during P02. | Artifact hashes/notices, dependency/plugin graph and distribution verdict; decision matrix and measured comparison; approved-by status recorded honestly. | SYS/NUM | Design / Build |

**P02 callback test:** use the SYN-001 K(T,P) vector and a separate block with intentionally restricted variable dependencies. Assert both correctly zero and nonzero derivative positions, component ordering, and chain-rule assembly inside the coupled residual. Test multiple states, not just a point where a derivative happens to vanish. Check optional second-derivative products separately. Dense fallback or an unsupported ASL callback path is an explicit result, not a pass.

Name the composition mechanisms so the spike measures the right thing. CasADi: a `casadi.Callback` subclass implementing `get_sparsity_in/out`, `has_jacobian`, and `get_jacobian` (returning a sparse Jacobian `Function`), embedded in an `MX` graph; assemble the coupled Jacobian with `jacobian()` and assert its sparsity pattern equals the expected pattern with structural zeros preserved. Pyomo route: the algebraic part through `PyomoNLP` (ASL), the property callback as an `ExternalGreyBoxModel`, composed with `PyomoNLPWithGreyBoxBlocks`; assert the same pattern. Measure with the callback returning first derivatives only; then record separately whether either route propagates second-order products through the callback boundary (expected: neither without additional declarations). That separate record is the honest answer to the blueprint's optional-Hessian question.

**P03 decision rule:** correctness, sparse composition, distributability, and installability are hard criteria; then compare measured runtime and development cost. Keep CasADi on a defensible tie. If a candidate is blocked, retain the exact build/error evidence and choose the demonstrated viable route. If neither works, stop model breadth, identify the smallest blocker, and propose a bounded ADR remedy. Do not spend another open-ended month comparing libraries.

**Phase-0 ADRs:** 0001 state/units/zero-flow; 0002 canonicalization and schemas; 0003 CompiledProblem/backend; 0004 explicit SuperLU options; 0005 phase-attempt contract; 0006 distribution/data rights; 0007 reproducibility and certificate policy. Defaults can be recorded immediately; backend/distribution decisions close on evidence.

### 4.2 v0.0 — six-week reference sequence after Phase 0

| ID | Work and dependencies | Acceptance evidence | Owner | Lane (lead / second) |
| --- | --- | --- | --- | --- |
| K01 | P03: turn the selected spike into production compiler and callable adapter; source maps and reconstruction. | Expression/callback conformance fixtures, dimensions and sparsity, original-equation reconstruction; no backend imports in orchestrator. | NUM/SYS | Build / Design |
| K02 | K01: SYN-001 provider and feed/product/mixer/heater/flash/splitter; exact cache and separate warm-start cache. | Nominal, single-phase, zero-flow, cache on/off and perturbed-input tests; documented phase properties and initialization. | MOD | Build / Design |
| K03 | K02: physical scales before initialization; damped Newton on analytic and flash recycle residuals; bounded line search and phase attempts. | Solve traces, invalid-trial rejection, small-step stagnation, known root, bad budget, phase-change restart, bound handling. | NUM | Design / Build |
| K04 | K03: independent reconstructed-balance checks, target-model certificate and final local regularity screen; structured failures. | Correct nominal verdict, injected false-success rejected, original unregularized Jacobian evidence, energy-independence scope, partial-state labeling. | NUM/MOD | Design / Build |
| K05 | K04: immutable RunManifest/events/artifacts, replay, deterministic structural hashes and dependency mismatch detection. | Clean-environment replay; changed dependency fails exact replay; timing excluded from structural identity; two CI platforms. | SYS | Build / Design |
| K06 | K05: local transactions, Python/CLI entry points, integrated example and v0.0 gate. Transaction primitives may start after P01. | Draft vs ready validation, optimistic revision conflict, idempotent commit, complete CLI solve/inspect/replay; G00–G06 below. | SYS | Build / — |

K03 implements only the active-set behavior needed by the first fixture; T03 generalizes and stress-tests it. K04 builds certificate invariants from the first release, while T06 broadens rank diagnostics and adversarial coverage. Do not postpone trustworthy verification until after the kernel is advertised.

Package-specific requirements for v0.0:

- **K02:** heater and flash share one TP-state kernel (§3.2). The mixer outlet closure is restricted to the subcooled-liquid domain with a typed failure outside it. Do not implement a general PH flash in v0.0.
- **K03:** the tear Newton needs dR/dt through the unit chain. Use the assembled sparse Jacobian of the reduced tear residual from the selected backend as the primary path; a finite-difference tear Jacobian is retained only as a test oracle.
- **K04:** the regularity screen uses the concrete recipe in §6.3 (factorization-based reciprocal-condition estimate), not U-diagonal inspection alone.
- **K05:** the two structural-hash CI platforms are one Linux x86-64 and one of {Linux aarch64, macOS arm64}; differing BLAS vendors are preferred over merely differing distributions.

| Week | Demonstrable result |
| --- | --- |
| 1 | Selected backend compiles SYN-001 equations with stable source IDs; native/callback parity |
| 2 | Once-through thermal/flash units with independent balance evidence and invalid-state outcomes |
| 3 | One closed recycle with damped Newton, fixed scales, bounded phase restart and recorded attempts |
| 4 | Passing and deliberately failing runs emit honest certificates/failures and final Jacobian evidence |
| 5 | Pinned replay bundle reconstructs results and detects tampering; structural CI on two platforms |
| 6 | Local Python/CLI transactions and complete demonstration; close or explicitly fail the v0.0 gate |

These are review cadences for the blueprint's stated 2–4 FTE capacity, not estimates that an agent can autonomously compress into six calendar weeks. With one part-time contributor, retain order and re-estimate dates. Report completed packages and actual effort instead of claiming a predicted coding-agent speedup.

### 4.3 v0.1 — transparent solver and bounded agent workflow

| ID | Work and dependencies | Acceptance evidence | Owner | Lane (lead / second) |
| --- | --- | --- | --- | --- |
| T01 | K06: process/equation graphs, fixed/alias elimination, DM/SCC/BTF, source-mapped counts and tear candidates. | Square structural defect vs numerical defect distinguished; block-size metrics; canonical tie-breaks; zero-flow cases. | NUM | Design / Build |
| T02 | T01: acyclic execution, safeguarded Anderson recycle, coupled sparse EO blocks, cross-unit specification promotion. | Analytic/high-gain loops; acceleration restart; EO vs tear agreement; duty-to-downstream-T spec; no nested SM controls. | NUM/MOD | Design / Build |
| T03 | T02: general procedural-phase active-set controller and checkpoint compatibility. | No signature change during attempt; trial rejection/restart; sparsity rebuild; disappearing/reappearing phase; bounded cycling; multiple-root provenance. | NUM/MOD | Design / Build |
| T04 | T03: typed adaptive homotopy and one qualified PTC family with safeguarded SER. | Endpoint equivalence; λ<1 not target-verified; PTC derivation and basin comparison; accepted/rejected step controller tests and budgets. | NUM/MOD | Design / Build |
| T05 | T02: general PH flash, conversion reactor, component separator, valve, liquid pump, one two-stream heat exchanger. | Each model's contract, limiting/failure tests, balance and derivative evidence; at least one coupled case per family. | MOD | Build / Design |
| T06 | T04, T05: strengthen rank/conditioning and verifier; register 30+ distinct cases, robustness generators, eight reference comparisons. Start reference acquisition after P03. | Correct verdicts; 20×20 registered ensemble; retained failures; 95% nominal target; numerical and cost reports; no false verification. | NUM/MOD | Design / Build |
| T07 | T03, K06: job lifecycle and small HTTP/MCP bindings over the local application contract. | Ten agent tasks, ≥80% completion, zero unauthorized changes/false verification; duplicate jobs, cancellation, injection and revision tests. | SYS | Build / Design |
| T08 | T06, T07: v0.1 release evidence, supported envelope and v0.2 real-chemistry selection. | Gate V11–V20; selected chemistry/data/kinetics/property/reference dossier; reproducible release candidate. | MOD/SYS | Design / Build |

T05 and T07 can proceed independently once their inputs stabilize; they do not require a new architecture. T06 reference work must not be deferred to the last week. Overall v0.1 planning allowance remains 10–14 incremental weeks for the blueprint's capacity; review after T02 rather than converting that allowance into an unsupported fixed promise.

Package-specific requirements for v0.1:

- **T02 (A02 test):** the duty-to-downstream-temperature specification must produce a SolvePlan whose EO region lists the heater, every intervening unit, and the specification equation, and must fail with a capability error — not a nested loop — if any unit in the region lacks EO derivatives.
- **T06:** SYN-001 r-variants are one recycle case, not three (§3.2). NET-07, a thermally coupled recycle, is mandatory so that at least one registered recycle has genuine composition–energy coupling.

**PTC first family:** implement a flash with liquid and vapor holdup (mass and energy accumulation) with explicit residual sign and mass mapping; it is the most defensible physical derivation for this codebase because SYN-001 already supplies its equilibrium, and SYN-001 at r = 0.95 is the registered basin comparison against damped Newton. Start with a small stable analytic limit, then the coupled process case, then an exothermic multiple-root reactor — the physically unstable branch of which is exactly the example blueprint §7.5 cites. Derive static equivalence. Do not use −F as artificial dynamics without checking the sign/mapping. Use the precise SER policy of v3.1 §7.5, record pseudo-time scale and limits, and verify the target residual. If no useful qualified family passes, retain PTC as experimental and record the v0.1 gate as incomplete; do not enable it solely because BTF found a large block.

**Recovery minimum:** register three distinct edges: recycle acceleration restart/damping; stalled recycle → EO merge; EO globalization failure → typed homotopy or qualified PTC. Every edge has a direct injected failure, precondition, maximum count, and evidence that fixed physics/specifications did not change.

### 4.4 v0.2 — scientific reactor replacement

| ID | Work and dependencies | Acceptance evidence | Owner | Lane (lead / second) |
| --- | --- | --- | --- | --- |
| M01 | T08: pin the selected PyMRM reactor and one required nonideal property route; derive process boundary mappings. | Model/source/data rights, numerical refinement evidence, ports/DOF/reference-state compatibility, known invalid requests. | MOD | Design / Build |
| M02 | M01: execution adapter, experiment artifacts, timeout/cache/noise controls, frozen model versions and promotion. | Reproducible reactor result, failed experiment retained, model replacement diff and invalidation, incompatible pressure boundary rejected. | MOD/SYS | Build / Design |
| M03 | T08: sweeps, implicit sensitivities and small parameter-estimation example; general NLP gray-box/cyipopt adapter. | Sensitivity/adjoint checks on regular roots; singular-state refusal; identifiable vs unidentifiable fit; optimizer with verified constraints and Hessian policy. | NUM | Design / Build |
| M04 | M02: surrogate training, conserved-output representation, hard/empirical domain tests, independent calibration/test draws and Default split-conformal reporting. | Frozen splits/transforms; finite-sample rule; coverage/error/gradient/domain metrics; insufficient-data outcome; promotion and rollback. | MOD/NUM | Design / Build |
| M05 | M03, M04: distinct trust-region integration spike and fixed-topology refinement loop. | ExternalFunction/glass-box composition with source maps; parent-model checks at candidate optima; true-model call accounting; constraints and limitations retained. | NUM/MOD | Design / Build |
| M06 | T08: diagnostic web shell; bounded topology/SFILES work only if an actual comparison needs it; external agent benchmark adaptation. | All actions use public application contract; equation/trace/scenario views; benchmark coverage and artifact-access report. | SYS | Build / Design |
| M07 | M05, M06: real reference journey and v0.2 gate. | Before/after design decisions, costs, uncertainty and truth checks; W21–W27; reproducible report and artifacts. | MOD/SYS | Design / Build |

The Pyomo general NLP adapter and trust-region adapter are separate deliverables. A cyipopt success does not complete M05. Compile any needed Pyomo glass-box projection from canonical equations; do not maintain a second hand-authored reactor/flowsheet. If the chosen framework cannot consume the intended mixed model, document the failing composition and implement an ADR-backed tested alternative before claiming that gate.

**M04 starting implementation:** use a small smooth quadratic response surface in scaled reactor inputs, preferably predicting reaction extents or another conserved-coordinate representation. Fit with a numerically stable least-squares method and validate independently before increasing model complexity. Record the training domain and enforce nonnegative species/extent constraints where applicable; a differentiable fit is not automatically a physically valid model. Define scalar or explicitly joint conformal scores, calibrate only after predictor/transform selection, and retain interval-width limits alongside coverage. Register training, calibration, and test sample counts before running the parent model, based on the approved experiment budget and the statistical criterion in v3.1. If the budget is insufficient, return insufficient evidence; do not reuse training points as calibration data. More complex surrogates are introduced only to resolve a measured error or derivative limitation.

Select the real chemistry at T08 using a scored dossier: available validated reactor/kinetics, property coverage, data rights, independent simulator case, computational cost, and a continuous design decision affected by reactor fidelity. Prefer a model Frank's group can actually provide. If inputs are unavailable, keep the adapter testable with a synthetic model, but do not claim the real scientific journey is complete.

### 4.5 v0.3 and v1 backlog

| ID | Dependency | Work and exit condition | Lane (lead / second) |
| --- | --- | --- | --- |
| S01 | M07 | Countercurrent equilibrium-stage subsystem with explicit DOF and energy/phase coupling; initializer and Newton continuation | Design / Build |
| S02 | S01 | MESH column, stage indexing, feed/condenser/reboiler/pressure/specification conventions; four matched cases and invalid-spec/phase tests | Design / Build |
| S03 | S02 | Two independent column references across the available suite, perturbation studies and supported nonideal scope; rate-based models remain deferred | Design / Build |
| R01 | S03 | 100+ distinct cases, 25 cross-implementation comparisons, ≥95% registered-domain robustness, independent user reproduction and extension exercise | Build / Design |
| R02 | R01 | Stable public contracts/deprecation policy, supported web workflows, constrained finite synthesis demonstration, release/security/maintenance ownership | Build / Design |
| R03 | M07; conditional | Peclet/CFD asynchronous refinement only with a validated family and authorized compute; otherwise experimental and explicitly outside release claims | Build / Design |

Re-estimate later phases using measured v0.2 effort and scientific availability. Do not build SSP, DEXPI, CAPE-OPEN, broad ontologies, GPU kernels, or multiple column algorithms without a use case and an ADR explaining the cost.

## 5. Requirement traceability

Create machine-readable ledger entries from these mappings. Each entry also records its precise blueprint paragraph, acceptance command/test node, commit hash, evidence URI/path, and status. The following mappings cover all executive decisions and v3.1 amendments.

| Requirement | Owning packages | Minimum evidence |
| --- | --- | --- |
| D01 original orchestration | K03, T02, T04 | Explicit plans/attempts; own policy calls interchangeable numerical interfaces |
| D02 backend/callback | P02, P03, K01 | Matched spike, sparse callback and selection ADR |
| D03 linear solver | P02, K03 | Explicit SuperLU configuration and linear residual evidence |
| D04 licensing | P03, T08 | Exact binary/data inventory and distribution verdict |
| D05 structure vs rank | T01, K04, T06 | Structural and numerical singularity separated |
| D06 scaling order | K03, T02 | Scales precede initialization acceptance; fixed within attempt |
| D07 PTC | T04 | Mapping/equivalence/qualification, SER and final target checks |
| D08 thermodynamic contract | P01, K02, M01 | Consistent synthetic model and real provider conformance |
| D09 phase appearance | K03, T03 | Frozen attempts, bounded restarts, phase-domain outcomes |
| D10 exact cache | K02, M02 | Nearby distinct states do not alias; separate warm-start hints |
| D11 multiple roots | T03, T06 | Branch histories; no uniqueness/dynamic-stability overclaim |
| D12 uncertainty | M04 | Independent calibration/test and qualified coverage/error evidence |
| D13 multi-fidelity optimization | M05 | Tested framework path, assumptions, finite-budget truth checks |
| D14 certificates | K04, T06, M07 | Model verification separated from empirical validation/optimality |
| D15 local and remote clients | K06, T07 | In-process scientific use and common transport semantics |
| D16 drafts/readiness | K06, M03 | Incomplete draft persistence; task-specific closure |
| D17 scope | All release gates | No later breadth substituted for early scientific gates |
| D18 interop | K05, M06, R02 | Replay first; optional topology loss report |
| D19 independent references | T06, S03, R01 | Matched-model inputs, independence disclosure and verdicts |
| D20 reproducibility | K05, T06 | Structural hashes vs controlled numerical replay |
| A01 phase ownership | K03, T03 | Same signature across residual/Jacobian trials; restart on update |
| A02 cross-unit specs | T02 | Affected region promoted to EO; no nested SM controls |
| A03 PTC/SER | T04 | Accepted-step ratio, reject shrink, reset and endpoint tests |
| A04 sampling law | P01, T06 | Executable generator, distributions, scales, domain handling, saved draws |
| A05 backend comparator | P02, P03 | CasADi vs Pyomo/PyNumero/ASL with sparse property callback |
| A06 distinct bridges | M03, M05 | Gray-box NLP and trust-region compositions tested separately |
| A07 Default conformal | M04 | Registered reference distribution, frozen predictor and independent splits |
| A08 regularity | K04, T06 | Final unregularized Jacobian; bounded condition/rank checks |
| A09 energy independence | K04, T06 | Shared provider hashes and limited consistency claim |
| A10 wheel/plugin audit | P03, T08 | Bundled plugin inventory including disabled distributed bytes |

### 5.1 Release-gate ledger

A gate verdict is `PASS`, `FAIL`, or `BLOCKED`, with evidence. `BLOCKED` is never counted as pass. “All tests pass” without a fixed test/case inventory does not close a gate.

| Gate | Required evidence | Owner package |
| --- | --- | --- |
| G00 | Three-component ideal process with all named v0.0 units and one numerical tear | K02/K03 |
| G01 | Damped Newton plus expression/callback interface fixtures | K01/K03 |
| G02 | Canonical revision, locks, source mapping, Python/CLI | K01/K06 |
| G03 | Serialized manifests, events, certificates, failures, replay bundle | K04/K05 |
| G04 | Balances, phase transition, bad spec and numerical failure | K04 |
| G05 | Dependency change detected and two-platform structural equality | K05 |
| G06 | End-to-end example is inspectable without unrelated code | K06 |
| V11 | Semantic diff, drafts, task validation, units/references, real migration when applicable | K06/T01 |
| V12 | Required unit library with per-model definition of done | T05 |
| V13 | DM/SCC/BTF, tear and EO, scaling and initialization | T01/T02 |
| V14 | Homotopy, qualified PTC/SER and three bounded recovery edges | T04 |
| V15 | Frozen phases, EO cross-unit spec, multiple-root evidence | T02/T03 |
| V16 | 30+ distinct cases, eight shared comparisons, two both-reference cases where feasible, registered 20×20 ensemble | T06 |
| V17 | Local/HTTP/MCP, ten agent tasks, ≥80% success, zero unauthorized actions/false verification | T07 |
| V18 | Distribution/data gates, local rank evidence, qualified energy checks, all recovery edges tested | T06/T08 |
| V19 | Real-chemistry dossier with usable data/kinetics/property/reference route | T08 |
| V20 | ≥95% nominal robustness, correct invalid-structure handling, no adversarial false verification | T06/T08 |
| W21 | PyMRM boundary/accuracy/execution and provenance | M01/M02 |
| W22 | One validated needed nonideal property route | M01 |
| W23 | Surrogate conservation/domain/derivative/default UQ and promotion | M04 |
| W24 | Fixed-topology optimization, eligible trust-region example and parent-model checks | M03/M05 |
| W25 | End-to-end real reactor refinement with honest evidence limits | M07 |
| W26 | Diagnostic web shell through shared contract | M06 |
| W27 | External agent benchmark adaptation attempted; inaccessible assets disclosed | M06 |
| X31 | Four matched column cases, invalid specs/phases, two independent references where available | S02/S03 |
| X41 | v1 counts, robustness, independent reproduction/extension and stable governance/workbench | R01/R02 |
| X42 | Conditional CFD integration is genuine or explicitly experimental | R03 |

V16's reference availability qualification is not permission to silently reduce counts. Document each unavailable case or duplicate-provider dependence, pursue a semantically appropriate replacement, and retain unresolved discrepancies in the gate dossier.

## 6. Test and benchmark execution policy

### 6.1 Required initial inventory

Define cases by distinct scientific failure mechanism, not by copying the same case under different IDs. Initial seed values are registered in the repository; the table identifies cases to implement, not completed tests.

| IDs | Cases |
| --- | --- |
| STR-01–06 | Acyclic chain; missing spec; excess spec; square structural defect; valid matching with numerical dependence; component mapping error |
| STA-01–04 | Exact zero stream; zero component; mass/molar and temperature-unit conversion; component permutation |
| NUM-01–06 | Known scalar root; analytic linear recycle; 12-order scaling challenge; exact initial root; small-step stagnation; invalid trial state |
| THM-01–06 | Ideal TP; PH; all-liquid; all-vapor; reference mismatch; exact-cache perturbation |
| NET-01–07 | SYN-001 (all r-variants count as one case); high recycle; nested recycle; oscillation; cross-unit duty specification; heat coupling; thermally coupled recycle (feed–effluent exchanger, or a recycle whose temperature is not pinned by the flash) |
| ADV-01–06 | Active-set cycling; homotopy stall; incomplete endpoint; PTC invalid mapping; multiple roots; noisy callback |
| VER-01–05 | Incorrect energy bookkeeping; regularized matrix masking target rank loss; stale Jacobian; isolated singular root; unauthorized tolerance change |

This provides more than 30 candidates so the counted v0.1 corpus need not rely on near-duplicate cases. At least 20 supported, nominally feasible cases are separately eligible for initial-guess robustness, with 20 saved starts each. Intentionally invalid cases test diagnosis and are outside the success-rate denominator by preregistered classification.

### 6.2 Sampling and cost

Implement the v3.1 generator: perturb selected scaled free coordinates independently by Uniform[−0.2, 0.2] about a registered initializer state, with documented domain rejection, retry cap and special zero-flow parameterizations. Save generator code hash, RNG/version, seeds, scales, initial phase assignments, every accepted state, and rejection counts. Do not initialize from a hidden converged answer.

Keep the nominal gate separate from full-bound-box, log-wide and phase-boundary stress profiles. Report per-case success and clustered uncertainty; 400 related starts are not 400 independent process designs. An explicit support-matrix change is required to move an existing failed supported case outside the envelope.

Register operation-count budgets and machine-dependent wall-time ceilings before scoring. Record compile, initialization, solve and verification time separately. Do not count structural rejection as a converged solution or a relaxed certificate as verified success. Record exact and warm-start cache conditions. Compare iterations or property-call counts across simulators only when their meanings match.

### 6.3 Local rank evidence

At final state, form the unregularized target Jacobian with recorded scales and the right phase regime. Use LU pivots as a screen, a bounded condition estimate when appropriate, and rank-revealing checks on suspicious blocks. Concretely: with `lu = scipy.sparse.linalg.splu(J)`, build a `LinearOperator` whose `matvec` and `rmatvec` call `lu.solve(·)` and `lu.solve(·, trans='T')`, estimate ‖J⁻¹‖₁ with `scipy.sparse.linalg.onenormest`, and report rcond₁ ≈ 1/(‖J‖₁ ‖J⁻¹‖₁) as the factorization-based estimate required by blueprint A08. Escalate to a bounded dense QR/SVD on the implicated block only when rcond₁ is below the registered threshold or the estimate fails. Do not reuse a matrix from a previous state or from J + M/Δτ. A rank warning yields the qualified status required by v3.1, even if residuals are small. Save the diagnostic method and accuracy threshold.

Include an upper-triangular, badly conditioned matrix with innocuous diagonal entries to prevent the implementation from equating U's diagonal with a condition estimate. Include x² = 0 to ensure the diagnostic does not claim every singular root belongs to a continuum.

### 6.4 Independent references

Acquire DWSIM/IDAES examples early, pin exact versions and data, and record whether packages/correlations are shared. Prefer common simple fixtures: mixer, splitter, heater, ideal flash, valve, liquid pump, conversion reactor, and a recycle. Check which tools can represent the same equations before designating the eight release comparisons. SYN-001's analytic oracle does not replace the required external comparisons.

Compare the same model semantics and outputs with preregistered tolerances. Store `AGREE`, `DISAGREE`, or `NOT_COMPARABLE` and reasons. Separate access/build problems from scientific discrepancies. Do not reconcile a mismatch by tuning one side until it agrees.

### 6.5 CI cadence

| Cadence | Run |
| --- | --- |
| Each coherent change | Formatting/types; touched unit/contract tests; canonicalization; synthetic smoke solve and false-verification sentinel |
| Numerical/model change | Relevant derivative/balance/phase/regularity tests; baseline vs changed traces; affected robustness subset |
| Nightly or release-candidate job | Full supported robustness ensemble, reference environments, bounded agent evaluation, replay/platform matrix |
| Release gate | Frozen full inventory, distribution/data audit, independently reviewable report, support matrix and known limitations |

Do not run all costly external experiments after every documentation change. Do not skip the full registered gate after changing a solver policy. Record seeds and minimize failing cases. Failure of a meaningful test is an issue to resolve, not a reason to replace the test with one that mirrors current output.

## 7. Evidence, review, and resumability

For each work package, deliver a short report with: intended behavior; changed files; requirement IDs; equations or assumptions; actual commands and results; retained failing cases; numerical limitations; and next package. Keep exact large traces and binary outputs in artifacts, not in commit prose. Reports point to the tested commit and environment.

A proposed evidence manifest has these fields:

```yaml
work_package: K03
commit: <actual commit hash>
requirements: [D01, D03, D06, D09, A01]
status: tested
inputs:
  case_id: SYN-001
  case_hash: <actual hash>
  environment_lock_hash: <actual hash>
commands: []
checks: []
artifacts: []
limitations: []
review:
  numerical: pending
  process_model: pending
```

Angle-bracket fields are schema examples, never valid evidence values. Populate actual values during execution. A coding agent must not set `reviewed` merely because it generated a report.

Require numerical review for backend selection, residual/derivative semantics, solver globalization, PTC mapping, and regularity policy. Require process-modeling review for thermodynamic consistency, reference-state/energy handling, phase formulation, reactor boundaries and real-data claims. Routine code hygiene need not block implementation pending a human meeting; gate the affected scientific release claim and continue independent work.

On a context reset, read the baseline, current ADRs, progress file, latest package manifest, and repository status. Resume the next incomplete acceptance item. Do not regenerate passed fixtures, restart the architecture discussion, or overwrite concurrent work.

## 8. First-session instructions for the coding agent

The following is a ready-to-use kickoff instruction. Supply it with this plan and blueprint v3.1:

> Implement the agent-native process simulator using blueprint v3.1 and this implementation plan. Start with P00–P03; then continue toward v0.0. Inspect the repository and its instructions before changing anything. Preserve existing work. Create the requirements/progress ledger, record the source-document hashes, and establish a tested baseline. Implement the specified SYN-001 thermodynamics and separate scalar reference, then compare CasADi with Pyomo/PyNumero/ASL using the same sparse property-callback fixture and common SuperLU solve. Audit actual bundled binaries and plugins. Close the backend ADR on evidence. Do not build an AD system, a second production flowsheet model, a GUI, or broad adapters during this stage.
>
> After Phase 0, execute K01–K06 in dependency order. Each package must produce real code, acceptance evidence and an honest progress update. Continue through routine reversible work without asking permission for ordinary implementation decisions. Stop only for a concrete blocked prerequisite, a change to scientific requirements, or an action outside existing authorization; describe the exact blocker and useful completed work. Do not claim release completion from a demo, copied golden outputs, skipped cases, or relaxed checks. At the end of each work session leave the next executable action in `docs/progress.md`.
>
> The first result I should be able to inspect is an ideal flash–recycle solve with trace, original-equation/balance checks, final Jacobian evidence, a deliberately failing companion case, and replay from a pinned bundle. All future extensions must preserve that behavior.
>
> Two lanes share this plan. The design lane leads scientific semantics, derivations, numerical policy, certificates, benchmark verdicts, and all ADRs; the build lane leads scaffolding, schemas, application and client layers, adapters, inventories, campaign execution, and documentation. Neither lane marks its own package as reviewed. Interfaces frozen at P01 change only by a design-lane ADR. When a task has no test that would catch its failure, it is a design-lane task; when it does, it is a build-lane task with a design-lane review if it touches residuals, derivatives, phases, scaling, certificates, or replay identity.

### 8.1 First ten working days

| Day | Design | Build |
| --- | --- | --- |
| 1 | Review repository inventory; confirm ledger structure | Repository/baseline inventory, exact blueprint hash, requirements ledger, skeleton only where absent |
| 2 | ADR 0001 (state/units/zero-flow); SYN-001 derivation including the §3.2 findings; oracle specification | Implement fixture inputs and independent oracle to the derivation; run K-value, oracle, and variant phase-state checks |
| 3–4 | Write the P02 composition test specification (patterns, states, chain-rule assertions) | CasADi harness: `Callback` with declared sparsity, `MX` assembly, common derivative test harness |
| 5–6 | Interpret CasADi results; flag any silent densification | Pyomo/PyNumero/ASL harness with `PyomoNLPWithGreyBoxBlocks`; exact callback route and build limitations recorded |
| 7 | Compare matched measurements; draft decision matrix | Compile/evaluation/derivative timing, memory, source-map example, optional second-order probe |
| 8 | Review inventories for default-install verdicts | Exact binary/plugin inventories for both candidates with hashes and notices |
| 9 | Apply hard criteria; identify any blocked route | Reproduce both candidates in a clean environment |
| 10 | Close ADR 0003/0006 or raise one narrowly evidenced blocker | Begin K01 scaffolding on the demonstrated path |

The timebox limits exploratory breadth. It does not authorize concealing an unresolved sparse-callback or licensing defect.

## 9. Completion report expected by Frank

For v0.0, return the tested repository revision, one-command local reproduction instructions, the passing and failing run bundles, gate G00–G06 verdicts, and known limitations. For v0.1 and later, include the fixed corpus results, supported-domain success rates, cross-simulator comparisons and unresolved disagreements, scientific review status, and extension instructions.

Report implementation progress in completed work packages and verified release gates. Preserve the distinction between “implemented,” “numerically verified,” “independently validated,” and “ready for scientific use.”
