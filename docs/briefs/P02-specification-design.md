# Fable design brief — P02 composition test specification

Repository: `/home/frankp/Codes/Process Simulator` (branch `wp/P02`, based on `main` at `2c7c50b`).
You are the architect for work package **P02**. You write a specification; you write no production code.

## 1. The question

**What exactly must the P02 composition test assert — which residual system, which evaluation states, which
sparsity pattern, which derivative identities, which tolerances, and which measurements — so that a CasADi
harness and a Pyomo/PyNumero/ASL harness are measured on identical ground, and so that a silently densified
Jacobian, a mis-ordered component index, a dropped chain-rule term, or a missing second-order capability
cannot pass as success?**

What must come back is a specification an implementer who has never seen this conversation can execute twice
(once per backend) and get comparable numbers, plus falsifiable pass/fail rules.

## 2. Why this needs Fable

Plan §4.1 makes P02 a Fable-led package. The risk is not writing the harness; it is writing a test that passes
while the derivative is wrong. The specific traps, named in the plan: a state where a derivative happens to
vanish so a structural zero and a numerical zero are indistinguishable; a backend that quietly densifies a
declared-sparse callback Jacobian; a chain-rule term that is dropped inside the coupled assembly; a
second-order product that is fabricated rather than reported absent. The spec must make each of those a
detectable failure. This is also the last decision point before the backend comparison (P03) inherits the
measurement protocol, so the two harnesses must be matched by construction.

## 3. Current state

### 3.1 What already exists (all merged to `main`, all tests passing: 360 passed, ruff clean, mypy strict clean)

- **P00**: repository bootstrap, `src/process_runtime/` skeleton (only `units` has code), requirements ledger
  `docs/requirements.yaml`, evidence layout `evidence/<pkg>/<code-commit>/manifest.json`, `scripts/check.sh`
  (ruff check, ruff format --check, mypy, pytest), `requirements.lock` with exact pins.
- **P01**: ADR 0001 (`docs/adr/0001-state-units-zero-flow.md`), the SYN-001 derivation
  (`docs/derivations/SYN-001.md`), the oracle specification (`docs/derivations/SYN-001-oracle-spec.md`), the
  independent 20-digit reference values (`benchmarks/syn001/reference_values.yaml`), the oracle
  (`benchmarks/syn001/oracle.py`, pure stdlib, forbidden to import `process_runtime`), the benchmark registry
  (`benchmarks/registry.yaml`), six JSON Schemas under `schemas/`, and the interface freeze
  (`docs/interfaces-frozen.md`).

### 3.2 SYN-001 K-values and their exact derivatives (`docs/derivations/SYN-001.md` §3)

    K_i(T, P) = (P_r/P) exp[ (L_i/R)(1/T_b,i - 1/T) + v_i (P - P_r)/(R T) ]

    d lnK_i/dT = [L_i - v_i (P - P_r)] / (R T^2)        d lnK_i/dP = -1/P + v_i/(R T)

K_i is composition-independent (ideal mixing). K_i(T_b,i, P_r) = 1 exactly. At 360 K, P_r = 100000 Pa:

| | A | B | C |
| --- | --- | --- | --- |
| K_i | 2.840644206559371394 | 1 (exact) | 0.310579751202444149 |
| d lnK_i/dT (1/K) | 0.0232006858 | 0.0278408229 | 0.0324809601 |
| d lnK_i/dP (1/Pa) | -9.96659101e-6 | -9.96659101e-6 | -9.96659101e-6 |

Note the two structural facts an implementer can trip over: **K_B(360 K, P_r) = 1 exactly** (a value, not a
derivative, that coincides with a trivial answer), and **d lnK_i/dP is identical for all three components** at
P_r (v_i are equal in this fixture). Both are reasons the spec must not evaluate at a single state.
Reference values live at key `lnK_derivatives_at_360K_P_r` in `benchmarks/syn001/reference_values.yaml`
(subkeys `dlnK_dT_per_K`, `dlnK_dP_per_Pa`, `formula`). Domain: 280-440 K, 50-200 kPa; outside it the oracle
raises `DomainError`.

### 3.3 Oracle public API (`benchmarks/syn001/oracle.py`, all fully typed, `Triple = tuple[float, float, float]`)

    SYN001: Syn001Constants                    # frozen dataclass of the fixture constants
    class DomainError(ValueError)
    k_values(T, P, c=SYN001) -> Triple
    g_liquid / g_vapor / h_liquid / h_vapor (T, P, c=SYN001) -> Triple
    stream_enthalpy_flow(...)
    class TPFlashResult (frozen)               # state, beta, V, L, x, y, sum_zK, sum_z_over_K, ...
    tp_flash(n, T, P, c=SYN001) -> TPFlashResult
    class RecycleOracleResult (frozen)
    recycle_oracle(F, r, T_flash, *, T_heater=350, P=1e5, T_feed=300, case_id="") -> RecycleOracleResult
    linear_recycle(f, r) -> tuple[float, ...]

Phase classification is exact: sum z_i K_i <= 1 -> LIQUID; sum z_i/K_i <= 1 -> VAPOR; else TWO_PHASE; zero
total flow -> ZERO_FLOW with undefined composition.

### 3.4 Registered fixture states available now

Fresh feed (1, 1, 1) mol/s at 300 K, P_r. Bubble point 347.44118198144020477 K, dew point
374.27030411847760313 K, sum z_i K_i(350 K) = 1.0703142190807741552, sum z_i K_i(310 K) = 0.32806972835518618544,
sum z_i/K_i(420 K) = 0.31715802235115620433. Nominal flash (r = 0.5, T_f = 360 K):
beta = 0.10136872342672776 is the *heater-outlet* vapor fraction; nominal flash q = 0.41508558999232460,
L = 3.2783818615536967 mol/s, V = 1.3608090692231516 mol/s,
x = (0.18166078663538668, 1/3, 0.48500588003127999).

### 3.5 Registered tolerances (ADR 0001 D6, derivation §9) — these are the *balance* tolerances, not
derivative tolerances; the derivative tolerances are yours to set.

| Check | Absolute | Relative x scale |
| --- | --- | --- |
| Component balance | 1e-9 mol/s | 1e-8 x 3 mol/s |
| Energy balance | 1e-5 W | 1e-8 x 1e5 W |
| Temperature | 1e-6 K | - |
| Pressure | 1e-2 Pa | - |
| Normalized composition | 1e-10 | - |

Registered scales: tear component flows 3 mol/s, temperature 100 K, pressure 1e5 Pa, duty 1e5 W.
Registered tear initializer (not a converged answer): recycle_i = r * F_i.

### 3.6 The frozen interface P02 must compose through (`docs/interfaces-frozen.md`, plan §2.1, verbatim)

    class CompiledProblem(Protocol):
        metadata: CompiledProblemMetadata
        def residual(self, x, context) -> EvaluationResult: ...
        def jacobian(self, x, context) -> JacobianResult: ...
        def reconstruct(self, x, context) -> ProcessState: ...

Attached binding semantics: `x` is a dense NumPy vector of the ordered free variables; sparse Jacobians use a
documented CSC ordering with explicit row and column IDs and source maps; `EvaluationResult` carries status,
active-set (phase) signature, state/model hash, accuracy information and evaluation counters; a `JacobianResult`
is valid only for the same state, model version, phase regime and evaluation policy as its residual;
residual and jacobian describe the same function at the same state; optional JVP/VJP/Hessian capabilities are
negotiated through metadata, and **a missing exact Hessian is reported as absent, never replaced with zeros**.
Plan §2.2 assigns the *schemas* `CompiledProblem metadata`, `EvaluationResult`, `Jacobian metadata` and
`PropertyCapabilities` to P02/K01. These signatures are frozen: changing them needs a Fable ADR, which is a
thing you may propose but not assume.

### 3.7 Plan text governing P02 (paste, verbatim, `docs/implementation-plan.md` lines 193-196)

> | P02 | After P01: build matched CasADi and Pyomo/PyNumero/ASL spikes through a minimal CompiledProblem
> boundary and common SuperLU solve. | Values, sparse assembled Jacobian, directional/chain-rule checks,
> callback pattern/count, compilation vs evaluation costs, source-map example, capability limitations. | NUM |
> Fable / Opus |
>
> **P02 callback test:** use the SYN-001 K(T,P) vector and a separate block with intentionally restricted
> variable dependencies. Assert both correctly zero and nonzero derivative positions, component ordering, and
> chain-rule assembly inside the coupled residual. Test multiple states, not just a point where a derivative
> happens to vanish. Check optional second-derivative products separately. Dense fallback or an unsupported ASL
> callback path is an explicit result, not a pass.
>
> Name the composition mechanisms so the spike measures the right thing. CasADi: a `casadi.Callback` subclass
> implementing `get_sparsity_in/out`, `has_jacobian`, and `get_jacobian` (returning a sparse Jacobian
> `Function`), embedded in an `MX` graph; assemble the coupled Jacobian with `jacobian()` and assert its
> sparsity pattern equals the expected pattern with structural zeros preserved. Pyomo route: the algebraic part
> through `PyomoNLP` (ASL), the property callback as an `ExternalGreyBoxModel`, composed with
> `PyomoNLPWithGreyBoxBlocks`; assert the same pattern. Measure with the callback returning first derivatives
> only; then record separately whether either route propagates second-order products through the callback
> boundary (expected: neither without additional declarations). That separate record is the honest answer to
> the blueprint's optional-Hessian question.

Schedule (plan §8.1): days 3-4 this specification plus the CasADi harness; days 5-6 the Pyomo/PyNumero/ASL
harness and the interpretation of the CasADi results including any silent densification; day 7 matched
measurements and the draft decision matrix. Requirements touched: D02 (backend/callback), D03 (linear solver:
explicit SuperLU configuration and linear residual evidence), A05 (backend comparator).

## 4. Constraints and invariants

- **Backends are not in `requirements.lock`.** Each candidate is installed in its own isolated environment
  (`.venv-casadi`, `.venv-pyomo`); the repository environment stays exactly as pinned. Available on PyPI now:
  casadi 3.8.0, pyomo 6.10.1. PyNumero's ASL path additionally needs a compiled `libpynumero_ASL`, whose
  acquisition may fail — if it does, that is an explicit recorded result, not a silent fallback.
- The harness code lives under `benchmarks/` or a new spike directory; **nothing under `benchmarks/syn001/`
  may import `process_runtime`**, and the oracle must remain the independent reference (it is not to be
  reimplemented in either backend's DSL and then compared to itself).
- ADR 0001 semantics are binding: SI units, state definition `nTP-v1` (component molar flows, T, P), the
  four-value phase signature, exact zero-flow rules (never divide by total flow, never evaluate ln 0), duties
  positive into the unit, reference convention `SYN-001-ref-v1`.
- `scripts/check.sh` must pass in the repository environment. Anything that needs a backend must skip
  explicitly (with a reported reason) rather than fail or silently pass when the backend is absent.
- No placeholder success paths; unimplemented capability returns an explicit unsupported result. A failed gate
  stays failed. Self-generated output is a regression fixture, never validation.
- Evidence goes to `evidence/P02/<code-commit>/manifest.json` with `status`, actual commands and their exit
  codes; angle-bracket placeholders are never valid values.

## 5. Already decided — do not reopen

The blueprint and plan (architecture, package order, the two candidates, SuperLU as the common linear solve),
ADR 0001, the SYN-001 fixture and its oracle, the frozen §2.1 signatures and §2.2 schema list, the tolerance
and scale registrations of §3.5 above, and the decision that the backend *selection* happens in P03 under its
own hard criteria (correctness, sparse composition, distributability, installability first; measured runtime
and development cost second). P02 produces the matched measurement, not the verdict.

## 6. Genuinely open — this is what you decide

1. **The coupled residual system itself.** Which SYN-001 subsystem is compiled: the variables and their
   ordering, the equations and their ordering, which quantities are fixed parameters, whether the recycle tear
   is included, and the scaling applied. It must be small enough for two backends in four days, and rich
   enough that a dropped chain-rule term through the property callback is visible in the assembled Jacobian.
2. **The property-callback block**: its declared input and output sparsity, and the exact expected pattern.
3. **The second block with intentionally restricted variable dependencies** — its construction, and the
   pattern that proves the backend preserved the restriction instead of densifying it.
4. **The evaluation states** (the plan demands several, not one), chosen so no assertion is satisfied by an
   accidental zero, and so both single-phase and two-phase regimes are covered.
5. **The derivative assertions and their tolerances**: exact-value comparisons against the analytic
   d lnK/dT and d lnK/dP, structural-zero and nonzero position assertions, component-ordering assertions,
   directional derivative checks, and the `v^T (J u) = (J^T v)^T u` identity, each with the tolerance and the
   argument for why that tolerance is above the roundoff floor and below any error worth catching.
6. **The second-order probe**, kept separate, with the rule for recording "absent" honestly.
7. **The measurement protocol**: what counts as a callback invocation and how it is counted identically in
   both backends, how compile cost is separated from evaluation cost, what memory figure is meaningful, the
   repetition count and which statistic is reported, and the form of the source-map example.
8. **The pass/fail verdict rules**, including what "dense fallback" means operationally and how it is detected.
9. **The SuperLU common solve**: what is solved, and the linear-residual evidence D03 needs.

## 7. Already tried and rejected, with evidence

- **A finite-difference identity check below the roundoff floor.** In P01 I specified a central difference at
  h = 1e-3 K with a 1e-6 J/mol tolerance for the h = g - T dg/dT identity. Measured worst error was
  1.4e-6 J/mol — the specification, not the implementation, was wrong. It was replaced by a fourth-order
  stencil at h = 0.1 K with a 1e-7 J/mol tolerance, and the identity itself is verified at 40 digits by
  mpmath in `docs/derivations/scripts/syn001_reference.py`. **Do not specify a finite-difference tolerance
  without stating the step, the stencil order, and the floor estimate that makes it achievable.**
- **Regenerating reference values from the implementation.** Forbidden: `reference_values.yaml` is generated
  from the plan §3.1 definitions by an independent mpmath script at 40 digits, and the oracle agrees with it
  to 7.1e-15 relative. The same independence rule applies to P02: the expected derivatives come from the
  closed forms in §3.2 above, never from the backend being tested.
- **A single evaluation state.** Rejected in advance for the reasons in §3.2: K_B = 1 exactly at 360 K and the
  three d lnK/dP values coincide at P_r.

## 8. How the answer will be verified

Two harnesses implemented against your specification by Opus, days 3-6, each in its own environment, each
producing: the assembled sparse Jacobian and its pattern, the derivative comparisons against the analytic
values above, the callback counts, the compile and evaluation timings, the memory figure, the source-map
example, the SuperLU linear residual, and the second-order record. Then `scripts/check.sh` in the repository
environment, an `evidence/P02/<commit>/manifest.json` recording the actual commands, and a Fable review of the
completed implementation against this specification. A specification item that cannot be implemented is
reported back to you, not quietly dropped.

## 9. Deliverable

Write `docs/derivations/P02-composition-spec.md` (I commit it). Required sections, in this order:

1. Scope, authority, and what is explicitly out of scope.
2. The compiled subsystem: variables, equations, orderings, parameters, scaling, with the algebra written out.
3. The property-callback block and the restricted-dependency block, with their declared sparsities.
4. The expected Jacobian sparsity pattern, as an explicit table of (row id, column id) entries, distinguishing
   structural zeros from values that merely happen to vanish at some state.
5. The registered evaluation states, with the reason each one is in the list.
6. The assertion catalogue: every assertion, its expected value or pattern, its tolerance, and its
   justification. Number them so the manifest and the tests can cite them.
7. The measurement protocol.
8. The second-order probe and its honest-recording rule.
9. The SuperLU common solve and the linear-residual evidence.
10. Backend-specific execution notes: exactly which CasADi and Pyomo/PyNumero constructs implement each item,
    and what an unsupported path must report.
11. Pass/fail verdict rules, and what P02 does *not* establish.
12. Open questions with recommended defaults, each labelled *needs a fact* or *needs the user's preference*.

Keep it implementable by someone who has not read this brief. Where a number matters, write the number.

## 10. Out of scope

Implementing either harness. Choosing the backend (P03). K01 scaffolding. Canonical hashing (ADR 0002).
Introducing the `typing.Protocol` classes in code. Any change to the frozen interfaces or to ADR 0001 —
if you conclude one is needed, say so as a finding with the reason, and do not write the change.

## 11. Addendum — exact repository facts (verified, use these rather than guessing)

**Ledger requirements P02 must serve** (`docs/requirements.yaml`, all currently `planned`):

| ID | Title | Minimum evidence recorded in the ledger |
| --- | --- | --- |
| D02 | Language and compiled backend | Matched spike, sparse callback and selection ADR |
| D03 | Sparse solver | Explicit SuperLU configuration and linear residual evidence |
| A05 | Named backend comparator | CasADi vs Pyomo/PyNumero/ASL with sparse property callback |

The P02 package entry is `{id, phase: Phase 0, lead: Fable, second: Opus, depends_on: [P01], status: planned,
evidence: []}`. A package test is not requirement closure: P02 may add test node IDs to D02/D03/A05 but does
not by itself move them off `planned`. The selection ADR belongs to P03.

**Evidence manifest required top-level fields** (`schemas/evidence-manifest.schema.json`): `work_package`,
`commit`, `requirements`, `status`, `inputs`, `commands`, `checks`, `artifacts`, `limitations`, `review`.
Say in the specification what each P02 `checks` entry should be, so the manifest can cite your numbered
assertions directly.

**Registry case fields already in use** (`benchmarks/registry.yaml`, top-level keys `schema_version`,
`blueprint_sha256`, `registered_by`, `registered_on`, `families`, `cases`): `case_id`, `family`, `class`,
`revision`, `fresh_feed`, `T_feed_K`, `T_heater_K`, `T_flash_K`, `P_Pa`, `r`, `oracle`, `reference`,
`independence`, `tolerances`, `scales`, `initializer`, `budgets`, `expected`. If P02 needs registered
evaluation states, say whether they extend this registry or live in a new P02 document, and give the fields.

**`process_runtime.units` public API** (the only code in `src/` so far; pure functions):
`DIMENSION_ORDER` = (length, mass, time, temperature, amount, current, luminous_intensity);
`KINDS`, `KIND_SI_UNITS`, `KIND_LOWER_BOUNDS_EXCLUSIVE`, `QUANTITY_ROLES` (fixed, free, decision, derived);
`Dimension` = 7-tuple of ints; `UnknownKindError`; `dimension_of(kind) -> Dimension`;
`normalize_zero(value) -> float`; `combine_kinds(left, operator, right) -> str`;
`check_quantity(mapping) -> tuple[str, ...]` (returns the list of problems).

**Oracle export list** (`benchmarks/syn001/oracle.py` `__all__`), stdlib-only: `DomainError`, `PhaseState`
(= Literal["LIQUID", "VAPOR", "TWO_PHASE", "ZERO_FLOW"]), `Syn001Constants` (fields R, T_r, P_r, c_p, T_b, L,
v, M, T_min, T_max, P_min, P_max), `SYN001`, `TPFlashResult` (state, beta, V, L, vapor, liquid, x, y, K,
sum_zK, sum_z_over_K, rr_residual, iterations), `RecycleOracleResult`, `g_liquid`, `g_vapor`, `h_liquid`,
`h_vapor`, `k_values`, `stream_enthalpy_flow`, `tp_flash`, `recycle_oracle`, `linear_recycle`.

**Existing schemas** under `schemas/`: component-record, evidence-manifest, model-manifest, process-revision,
quantity, requirements-ledger, specification, validation-report (all `.schema.json`), plus `units.json` and a
README. The P02/K01 schema slots (CompiledProblem metadata, EvaluationResult, Jacobian metadata,
PropertyCapabilities) are **not** yet written; say which of them P02 actually needs and which wait for K01.

**Existing tests**: `test_document_hashes.py`, `test_evidence_manifests.py`, `test_package_imports.py`,
`test_requirements_ledger.py`, `test_schemas_p01.py`, `test_syn001_oracle.py`,
`test_syn001_reference_values.py`. pytest config: `testpaths = ["tests"]`, `pythonpath = ["."]`, no addopts,
no markers registered — if you want a backend-skip marker, name it, because it has to be registered.
