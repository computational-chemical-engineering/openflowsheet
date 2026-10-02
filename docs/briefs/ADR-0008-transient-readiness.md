# Fable brief — ADR 0008, transient-extension readiness

**Requested by:** Frank Peters, 2026-09-16, via the Opus session. **Author to be:** Fable 5.1
(project CLAUDE.md: Fable leads every ADR, all derivations including the PTC mapping, and every
change to the P01 interface freeze). **Branch:** `adr/0008-transient-readiness`.

## 1. The question

Frank intends, at a later release, to simulate transient behaviour and switching feeds. Dynamics
are deferred by blueprint §2.2 and that deferral stands. The question is **not** whether to build
dynamics now. It is:

> Which three concrete provisions must be fixed **now**, while `src/` is 561 lines and no unit
> model exists, so that adding a transient capability later is an additive extension rather than a
> refactor of every unit model and of the residual/Jacobian boundary?

The Opus session identified three candidate provisions (§5 below) and Frank has directed that all
three be neutralized. Two of them change frozen artifacts and therefore require this ADR; the
third is a constraint on how a future package implements the PTC mass matrix. **Rule on all three**
— including rejecting or reshaping any of them if the analysis does not support it. A reasoned
"provision 1 is unnecessary, here is why" is a valid and useful outcome.

## 2. Why this needs Fable

- `docs/interfaces-frozen.md` §1 is frozen by Fable at the close of P01. Any widening of
  `EvaluationContext` requires a Fable-authored ADR stating reason, affected requirements,
  migration impact, and acceptance evidence.
- Provision 2 concerns what the state identity hash covers and therefore touches the binding rule
  that "residual and jacobian describe the same function at the same state" and the exact-property
  cache rule (blueprint D10). No test would catch a silently inconsistent convention here, which by
  the project's lane rule (plan §1.3) makes it a Fable task.
- Provision 3 concerns the PTC equation-to-variable mapping, which plan §1.3 line 49 assigns to
  Fable explicitly ("all derivations (SYN-001, PTC mapping, sensitivities)").

## 3. Current state, with the relevant text pasted in

### 3.1 The deferral that stands

`docs/blueprint-v3.1.md:62`:

> Dynamics and control, electrolytes, solids, polymers, refinery assays, rate-based columns, full
> P&ID authoring, online plant operation, and universal mixed-integer synthesis are deferred.
> Reserving metadata for future dynamics does not justify building a DAE compiler in the first
> release. PTC is a steady-state numerical method, not a dynamic-simulation product commitment.

Note the precise wording: it forbids *building a DAE compiler*. It does not forbid *reserving
metadata*; it says reserving metadata does not by itself justify the compiler. This ADR must stay
on the right side of that line and say explicitly where it believes the line is.

### 3.2 The PTC form already mandated (blueprint §7.5, `docs/blueprint-v3.1.md:295-309`)

> M(x̂) dx̂/dτ = −F̂(x̂),
>
> where zero rows may retain algebraic equations. The model supplies the equation-to-variable
> mapping, M, sign conventions, time-scale policy, domain, and a consistent initialization
> procedure. In a locally frozen-mass linearized step,
>
> (M_k/Δτ + Ĵ_k) Δx̂ = −F̂_k.
>
> **[A03]** The displayed step is the linearly implicit Euler/Newton-style pseudo-transient step
> associated with the Kelley–Keyes formulation, with the declared mass-matrix extension. It is not
> a converged implicit-Euler time step or a DASSL-style accuracy-controlled DAE integrator. A full
> implicit DAE implementation must include the derivatives required by its own residual
> formulation.
>
> Two qualification routes are acceptable: **(a)** a derivation from physical holdup/thermal-inertia
> equations, documenting which modes and branches are expected to attract and why; or **(b)** an
> explicitly specified artificial reformulation with empirical basin comparisons against damped
> Newton on registered cases.

And D07, `docs/blueprint-v3.1.md:33`:

> Retain as a first-class optional mechanism. Require an explicit equation-to-state mapping, mass
> matrix, sign convention, consistent algebraic initialization, and stability evidence. No generic
> diagonal-magnitude recipe is trusted by default.

### 3.3 The plan has already chosen route (a) — `docs/implementation-plan.md:255`

> **PTC first family:** implement a flash with liquid and vapor holdup (mass and energy
> accumulation) with explicit residual sign and mass mapping; it is the most defensible physical
> derivation for this codebase because SYN-001 already supplies its equilibrium, and SYN-001 at
> r = 0.95 is the registered basin comparison against damped Newton. [...] Do not use −F as
> artificial dynamics without checking the sign/mapping.

T04 owns this (plan §4.3 row T04, Fable lead). K03 owns scales, damped Newton and phase attempts.

### 3.4 The frozen boundary, verbatim (`docs/interfaces-frozen.md` §1)

```python
class CompiledProblem(Protocol):
    metadata: CompiledProblemMetadata
    def residual(self, x, context) -> EvaluationResult: ...
    def jacobian(self, x, context) -> JacobianResult: ...
    def reconstruct(self, x, context) -> ProcessState: ...
```

Binding semantics attached to it, verbatim from the same document:

> - `x` is a dense NumPy vector of the ordered free variables; sparse Jacobians use a documented
>   CSC ordering with explicit row and column IDs and source maps.
> - `EvaluationResult` carries status, active-set (phase) signature, state/model hash, accuracy
>   information, and evaluation counters. `JacobianResult` is valid only for the same state, model
>   version, phase regime, and evaluation policy as its residual; `residual` and `jacobian` describe
>   the same function at the same state.
> - `EvaluationContext` pins model/data versions, phase signature, accuracy policy, and run-local
>   workspace; the outer active-set controller constructs a new context after a phase restart.
> - Metadata is typed and immutable and serializable; executable objects are runtime-local. There is
>   no mutable global property provider.

### 3.5 The code as it stands, `src/process_runtime/compiled.py` (whole relevant extract)

```python
StateVector = npt.NDArray[np.float64]

EvaluationStatus = Literal["ok", "invalid_trial_state", "unsupported", "error"]
PhaseSignature = Literal["LIQUID", "VAPOR", "TWO_PHASE", "ZERO_FLOW"]

@dataclass(frozen=True)
class EvaluationContext:
    model_version: str
    constants_sha256: str
    phase_signature: PhaseSignature | None = None
    accuracy_policy: str = "exact-double"
    workspace: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class EvaluationResult:
    status: EvaluationStatus
    values: tuple[float, ...] | None
    equation_ids: tuple[str, ...]
    phase_signature: PhaseSignature | None
    model_version: str
    constants_sha256: str
    state_sha256: str
    counters: Mapping[str, Mapping[str, int]]
    accuracy: str = "exact-double"
    message: str = ""

@dataclass(frozen=True)
class JacobianResult:
    status: EvaluationStatus
    row_ids: tuple[str, ...]
    col_ids: tuple[str, ...]
    indptr: tuple[int, ...]
    indices: tuple[int, ...]
    data: tuple[float, ...]
    phase_signature: PhaseSignature | None
    model_version: str
    constants_sha256: str
    state_sha256: str
    counters: Mapping[str, Mapping[str, int]]
    pattern_provenance: PatternProvenance
    source_map: Sequence[Mapping[str, Any]] = ()
    format: str = "csc"
    message: str = ""
```

`state_sha256` is currently computed by the P02 harnesses over the state vector; see
`spikes/p02/` and `tests/test_p02_composition.py` for how it is produced and checked. There is no
`time` anywhere in the boundary.

### 3.6 The state definition, ADR 0001 D2 (`docs/adr/0001-state-units-zero-flow.md`)

> 1. A material stream state is the tuple `(n, T, P)` with `n ∈ ℝ^{N_c}` the component molar flows
>    in mol/s [...] identified as `state_definition = "nTP-v1"`.
> 2. Derived quantities are computed, never stored as state [...]
> 4. Phase is **not** a free state variable of a stream. [...]
> 5. Two-phase streams are represented by the single `(n, T, P)` tuple plus the signature; the phase
>    split `(V, L, x, y)` is a reconstructable result [...] Storing the split as state would create
>    two descriptions of the same function and violate the residual/Jacobian identity rule.

Note that `nTP-v1` is a **stream (flow)** state. There is at present no notion of a **unit-internal
holdup** state anywhere in the ADRs, the schemas, or the code. Streams remain flows in a transient
simulation, so `nTP-v1` itself appears to survive unchanged; the gap is the accumulation state.

### 3.7 The exact-property-cache rule (blueprint D10, and CLAUDE.md)

> Exact-input cache only in residual, derivative, and final verification paths. Approximate lookup
> may suggest initial guesses but cannot masquerade as exact property evaluation.

CLAUDE.md, "Scientific conduct":

> Exact property caches key on exact canonical inputs; never quantize state coordinates on the exact
> path.

### 3.8 Repository scale right now

`src/` totals 561 lines: `compiled.py` (the types above) plus nine one-paragraph layer skeletons.
No unit model, no property provider, no solver exists. P00, P01 and P02 are tested; P03 (the
backend verdict) has not started. This is why the question is being asked now: the cost of
provision 3 rises with every unit model written and is near zero today.

## 4. Constraints and invariants that bound your answer

- Blueprint §2.2's deferral of dynamics **stands**. This ADR does not add a dynamic capability, a
  time integrator, event detection, or a DAE compiler, and does not change any release gate.
- The P01 freeze is real. Anything this ADR changes in `docs/interfaces-frozen.md` §1 must be
  enumerated, with migration impact, and must not break the P02 evidence
  (`evidence/P02/507dccfaa46fa905b651ba96de65c2ea8c9f3ca1/manifest.json`) or the 391 passing tests.
- Backward compatibility is available cheaply: `EvaluationContext` is a frozen dataclass and a new
  field with a default is source-compatible. Whether that makes the change better done *now* or
  *later* is part of what you are ruling on.
- No placeholder success paths; a capability that does not exist is reported absent, never as a
  default that reads as present. The `Capabilities` docstring in §3.5 is the house precedent: every
  field required, because a default of `"exact_sparse_csc"` would be a placeholder success path in
  the boundary type itself. Apply the same standard to anything you add.
- Whatever you decide must be **testable now**, on the current repository, or it is not a
  neutralization — it is a note.

## 5. The three provisions to rule on

**P-1 — time in the evaluation context.** `EvaluationContext` has no `t`. A time-dependent boundary
condition (a switching feed) would have to be passed through `workspace: Mapping[str, Any]`, which
is untyped and which risks entering, or failing to enter, the exact-property-cache key silently.
Candidate: an explicit optional field, e.g. `time: float | None = None`, with `None` meaning
"steady-state evaluation, time is not a coordinate of this problem". Rule on whether to add it now,
what its exact type and semantics are, whether it belongs in `EvaluationContext` or elsewhere, and
what the property-cache key rule becomes. Note that properties are state functions and are not
themselves time-dependent; the time dependence is in the boundary specification, not in the
thermodynamics. Consider whether that argues for keeping `t` out of the context entirely and
putting it somewhere else — say so if it does.

**P-2 — what `state_sha256` covers.** The binding rule is that residual and Jacobian describe the
same function at the same state, enforced through matching `state_sha256`. If a time coordinate or
an accumulation state ever exists, the hash must either cover it or explicitly not. Rule on the
convention and state it so that a later session cannot get it wrong by accident. This interacts
with P-1 and with the replay/reproducibility policy pre-allocated to ADR 0007.

**P-3 — the accumulation slot in unit models.** The risk: if K02/K03-era unit models are written as
`Σ_in = Σ_out` with no declared accumulation slot, and PTC's `M` is later supplied centrally as a
diagonal recipe, then (i) blueprint D07's "no generic diagonal-magnitude recipe is trusted by
default" is violated, and (ii) a later transient capability requires reopening every unit model.
Candidate constraint: **every conservation row a unit model declares must name the variable it
accumulates (or declare explicitly that it has no accumulation), as part of that model's own
manifest, rather than receiving a mass matrix assigned centrally.** Rule on whether this is right,
what exactly a unit model must declare, where that declaration lives (`ModelManifest`? a new
field? — note `ModelManifest`'s schema is in the P01 frozen list and changing it is a migration),
and what test would catch a violation. This is the provision Frank most wants closed, because it is
the one that becomes expensive to retrofit.

## 6. Already considered, so you need not re-derive it

The Opus session's analysis, which you are free to contradict:

- Most of the semi-explicit DAE skeleton is already a v0.1 obligation through PTC: the mass matrix,
  the per-equation-to-variable mapping, zero rows for algebraic equations, index awareness,
  consistent algebraic initialization, and the linearly implicit step. A transient capability
  reuses these rather than introducing them.
- `residual(x, context)` with a model-supplied `M` is the semi-explicit form already; no `ẋ`
  argument appears necessary at the boundary.
- `nTP-v1`, the CSC Jacobian boundary, property providers, scaling policy, and SuperLU appear
  unaffected by a later transient capability.
- Phase appearance/disappearance is already an event-with-restart problem owned by the active-set
  controller (A01, K03/T03). A feed switch has the same shape — detect, rebuild context, restart,
  re-initialize consistently — so the event machinery has a natural home and does not need to be
  invented for dynamics.
- Genuinely new later work, all additive: an accuracy-controlled integrator (SER is residual-based,
  not accuracy-based), event detection and consistent re-initialization, time-varying boundary
  specifications in `Specification`/`ProcessRevision`, and trajectory-level certificates.

Nothing has been tried and measured here; there is no experimental evidence to hand you, because
the provisions are about contracts rather than numerics.

## 7. How the answer will be verified

`PATH=.venv/bin:$PATH ./scripts/check.sh` — ruff, ruff format, mypy strict, pytest; currently green
at 391 tests. Whatever you specify must come with at least one test per provision that would fail
if a later session violated it. For P-3, the test may have to be a manifest/schema-level assertion
rather than a numerical one, since no unit model exists yet; say so explicitly and specify it
anyway. The P02 evidence must still reproduce.

## 8. Deliverable

`docs/adr/0008-transient-extension-readiness.md`, following the form of ADR 0001 (Status, Date,
Author, Affected requirements, Affected packages, Blueprint authority, Context, Decision as
numbered rules D1..Dn, Consequences, and a closing statement of what requires a new ADR to change).
It must contain:

1. A ruling on each of P-1, P-2, P-3 — adopt, adopt-modified, or reject, each with its reason.
2. For every adopted provision: the exact normative text, the exact type or field signature, and
   the migration impact on `docs/interfaces-frozen.md`, the schema list, and the P02 evidence.
3. An explicit statement of which lines of `docs/interfaces-frozen.md` §1 change and what they
   become, so the Opus session can apply it verbatim.
4. The required tests, specified precisely enough to implement without further scientific
   judgment (Opus implements; it may not decide scientific content).
5. A statement of what this ADR does **not** establish — specifically that it does not add a
   dynamic capability, does not commit the project to one, and does not relax §2.2.

Also state plainly, in one short section, whether in your judgement a later transient extension is
additive or a refactor **given** your rulings, since that is the question Frank actually asked.

## 9. Out of scope

Do not design a time integrator, event detection, index reduction, a DAE compiler, time-varying
schema fields, or trajectory certificates. Do not reopen the backend decision (P03), ADR 0003/0006,
the state definition `nTP-v1`, the scaling policy, or the phase-attempt contract. Do not write
production code. Do not change any release gate or any requirement status.
