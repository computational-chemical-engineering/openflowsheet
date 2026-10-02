# Design-lane brief — ADR 0008 Amendment 1, transient-extension readiness revisited

**Requested by:** Frank Peters, 2026-09-26, via the build-lane session. **Author to be:** the
`architect` (design lane). **Branch:** `adr/transient-readiness-2` (worktree
`.claude/worktrees/adr-transient-readiness-2`), based on `main` at `63364f8`. **Lineage:**
decision-register R-001, ADR 0008 (accepted 2026-09-16).

## 1. The question

Frank will want dynamic simulation (transient behaviour, switching feeds, later control) at a later
release, and wants the design now to be such that it can be incorporated "in the best possible
way". Dynamics remain deferred by blueprint §2.2; that is not in question. The question is:

> Since ADR 0008 was accepted, `src/` has grown from 561 to about 37 000 lines — twelve SYN-001
> unit models, a PH closure in the unit layer, the phase contract with its `ZERO_FLOW` regime, a
> PTC mass mapping, solve results, certificates and replay — and T07 (job lifecycle, HTTP/MCP
> bindings) and T08 are next. **Which additional provisions, if any, must be fixed now because they
> are cheap now and expensive later — and which candidates below are already additive and need
> nothing?**

For each candidate in §5, rule: **adopt** (with the exact provision, the artifact it changes, and
the executable test that pins it), **adopt as a constraint on a named future package** (no code
now), or **reject as already additive** (with the reason). "Nothing more is needed" for a candidate
is a valid and useful answer. Candidates you find that are not in §5 are welcome.

## 2. Why this needs the design lane

- `docs/interfaces-frozen.md` §1–§2 are frozen; widening a Protocol or a frozen schema takes a
  design-lane ADR (project CLAUDE.md; plan §2.1–§2.2).
- The energy-holdup question (U versus H, §5 C3) is a derivation, and the lane rule (plan §1.3)
  assigns derivations and the PTC mapping to the design lane.
- No existing test would catch a provision that is missing — which by the lane rule makes this a
  design-lane task.

## 3. Current state, with the relevant text pasted in

### 3.1 The deferral that stands (`docs/blueprint-v3.1.md:62`)

> Dynamics and control, electrolytes, solids, polymers, refinery assays, rate-based columns, full
> P&ID authoring, online plant operation, and universal mixed-integer synthesis are deferred.
> Reserving metadata for future dynamics does not justify building a DAE compiler in the first
> release. PTC is a steady-state numerical method, not a dynamic-simulation product commitment.

### 3.2 What ADR 0008 already fixed (R-001, `docs/decision-register.md:21-61`)

> (P-1) that time never reaches an evaluation — a time-varying specification arrives as a pinned
> input; (P-2) what the `state_sha256` identity hash covers; (P-3) that a unit model declares its
> own accumulation slot per conservation row rather than receiving a centrally assigned mass
> matrix. … P-1 adopted-modified — the proposed `EvaluationContext.time` field was *rejected*; the
> concern is closed by freezing the context's field set and the three method arities in an
> executable test instead. P-2 adopted: the hash covers exactly the dense `x` … P-3 adopted and
> made precise: a required per-equation `accumulation` declaration in `ModelManifest` with three
> kinds and no default, plus the balance-row sign convention `F_row = inflow − outflow + sources`.

ADR 0008 D2.3 / "Any later transient ADR" (`docs/adr/0008-transient-extension-readiness.md:37,90`):

> If holdup states are ever introduced, they are free variables: elements of `x` with
> `variable_ids`, columns of the Jacobian. … Holdup states are elements of `x` (D2.3); time reaches
> the orchestrator, never the boundary (D1.1); the accumulation term is formed outside `residual`
> (D1.2). A design that needs otherwise revises this ADR first.

ADR 0008's own residual-risk paragraph (same file, "Consequences"):

> The residual risk is not in the boundary but in the models: a `holdup_balance` energy row whose
> steady-state kernel is written in terms of enthalpy flows will need the `U`–`H` relation of its
> holdup derived at T04, which is derivation work, not refactoring …

ADR 0008 "does not establish": "It **commits the project to no transient release** … a transient
capability requires its own ADR, its own gate and its own place in the roadmap." Its listed later
machinery: "an accuracy-controlled integrator, event detection with consistent re-initialization,
time-varying specification schemas, trajectory-level certificates".

### 3.3 The accumulation declaration as built (`src/process_runtime/models/__init__.py:159-200`, `compiled.py:35`)

`RowAccumulation = Literal["algebraic", "zero_holdup_balance", "holdup_balance", "absent"]`.

```python
@dataclass(frozen=True)
class Accumulation:
    """ADR 0008 D3: every equation says what it conserves. There is no default."""
    kind: RowAccumulation
    reason: str = ""            # required for zero_holdup_balance
    holdup: Holdup | None = None  # required for holdup_balance: symbol, quantity, dimension
```

Holdup-bearing SYN-001 models (recon; manifests validated for presence at
`models/__init__.py:218`): heater, flash, ph_flash, conversion reactor, heat exchanger, component
separator. Energy holdups are declared as internal energy, e.g. `heat_exchanger.py:198`
`"U_hot", "internal energy of the hot-side contents of the exchanger", ENERGY`, and
`conversion_reactor.py:209` `symbol="U", quantity="internal energy of the reactor contents"`.
No holdup variable exists in `x` yet; the declaration is metadata that the PTC mapping reads.

### 3.4 The PTC mass matrix (R-032; `src/process_runtime/orchestrator/mass.py:1-20`)

> PTC needs a mass matrix `M = ∂(holdup)/∂x` … a well-mixed vessel whose every phase inventory
> drains at a rate proportional to itself with a common residence time θ, at its outlet state:
>
>     N_i = θ Σ_π n_i^π,          H = θ Σ_π Σ_i n_i^π h_i^π(T_π, P_π),
>
> with `n_i^π` the phase-resolved outflow … and the energy holdup the *enthalpy* content
> (`U + PV` at the pinned pressure; T04 §6.2, finding F2). … **The pattern comes only from the
> manifests.** A registry entry names a model's manifest equation and the holdup it maps it to …
> every `holdup_balance` row mapped (V1), no entry on any other row (V2), θ > 0 (V3), and each
> entry's holdup dimension the manifest's (V4). … A row nobody mapped is a refusal, never `M = 0`.

So the manifest says `U`, the PTC mapping uses `H = U + PV` at pinned pressure, and the holdup is
expressed through outflow and residence time rather than through holdup states.

### 3.5 The property provider (frozen, `src/process_runtime/thermo/__init__.py:62-230`)

```python
class PropertyCapabilities:  # every field required
    ...
    state_definition: str          # `nTP-v1` (ADR 0001 D2.1)
    properties: tuple[str, ...]    # e.g. `h`, `g`, `lnK`
    flashes: tuple[str, ...]       # "e.g. `TP`. v0.0 is TP only; PH is T05 (plan §3.2)."
    derivative_order: Mapping[str, int]   # e.g. {"T": 1, "P": 1}
    domain: Mapping[str, tuple[float, float]]

@dataclass(frozen=True)
class FlashRequest:
    """Determine the phase split at a state. v0.0 supports `TP` only (plan §3.2)."""
    state: StreamState            # (n, T, P) in nTP-v1
    specification: str = "TP"
    derivatives: tuple[str, ...] = ()

class PropertyProvider(Protocol):   # "Frozen in docs/interfaces-frozen.md §1"
    def describe(self) -> PropertyCapabilities: ...
    def evaluate_phase(self, request: PropertyRequest, context: EvaluationContext) -> PropertyResult: ...
    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult: ...
```

SYN-001 declares `properties=("h", "lnK")`, `flashes=("TP",)` (`thermo/syn001.py:80-112`): no
molar volume, no internal energy. The PH flash was not added to the provider: T05 built it in the
unit layer from the provider's TP flash, `h` and `lnK` (ADR 0011, R-036; `models/syn001/ph_kernel.py`).
`FlashRequest` carries a `StreamState (n, T, P)`, so it has no field for an H, U or V target.

### 3.6 Pressure and flow semantics (`models/syn001/valve.py:107`, `pump.py:122,131`)

Valve: `P_out - P_spec = 0`, with `P_out <= P_in` as a validity inequality on the state. Pump:
`P_out - P_spec = 0`, `eta W - [Hdot^L(n_in, T_in, P_out) - Hdot^L(n_in, T_in, P_in)] = 0`. No
model computes a flow from a pressure difference; no model has a vessel volume.

### 3.7 Results, schemas and specifications

`SolveResult` (`orchestrator/attempts.py:187`) is one solve: `outcome, x, residual_inf, attempts,
iterations, counters, checkpoint, signatures, converged, plan, final_state, best_x, contexts,
branch_provenance, root_fingerprint`. The frozen schema delivery list
(`docs/interfaces-frozen.md` §2) still has **K06/T07: ChangeSet, Job, job events, authorization
capability references** and **K04/K05: SolutionCertificate, FailureBundle, RunManifest, replay
artifact manifest** (delivered). `schemas/specification.schema.json`: `additionalProperties:
false`, `oneOf` exactly one of `value` (`"type": "number"`) or `bounds` (`lower`/`upper`), plus
`target`, `kind`, `unit`, `tolerance`, `role`, `provenance`. A schema changes only with a migration
and migration report (blueprint §4.4).

### 3.8 Structural analysis

`graph/dof.py`, `graph/matching.py`: purely structural; variables carry no differential/algebraic
marker; the `accumulation` declaration is applied as manifest semantics after structure.

### 3.9 What comes next (plan `docs/implementation-plan.md:244-246`)

| T06 | … register 30+ distinct cases, robustness generators, eight reference comparisons … (in progress on `wp/T06`, another session) |
| T07 | T03, K06: job lifecycle and small HTTP/MCP bindings over the local application contract … |
| T08 | T06, T07: v0.1 release evidence, supported envelope and v0.2 real-chemistry selection … |

## 4. Constraints and invariants

- Blueprint §2.2 stands: no DAE compiler, no integrator, no event machinery, no dynamic unit model
  in this amendment. Say explicitly where each adopted provision sits relative to that line, as
  ADR 0008 did.
- ADR 0008 D1–D4 stand unless you revise them explicitly with reasons; D1 (no time in the
  evaluation boundary) in particular.
- Numerics are untouched: every SYN-001 fixture, certificate and replay digest must remain
  bit-identical. A provision that would move a digest is out of scope unless you argue it is
  unavoidable now, and then it is flagged for Frank.
- Frozen interfaces (`docs/interfaces-frozen.md` §1–§2) change only by this ADR, with migration
  impact stated. Schema changes need a migration report (blueprint §4.4).
- Sign convention `F_row = inflow − outflow + sources` (ADR 0008 D4.3); units and state `nTP-v1`
  (ADR 0001).
- Concurrency: T06 is active on `wp/T06` (ADRs 0014–0017 there; the decision register is being
  edited there). **Do not edit `docs/decision-register.md` or any T06 file.** Draft the R-001
  register update as text inside your note; the build lane merges it.

## 5. Candidates (the build lane's hypotheses — rule on each)

- **C1 Flash/closure for holdup states.** A dynamic well-mixed vessel's state is its holdup
  (N_i, U) and volume V; the outlet state follows from a (U, V, N) closure, not a (T, P) or (P, H)
  one. `FlashRequest` cannot carry U or V targets and SYN-001 declares no molar volume and no `u`.
  Is a UV closure buildable in the unit layer the way the PH closure was (from TP flash, `h`,
  `lnK`, plus a molar volume `v`)? If so, is the only provision now a capability convention (e.g.
  the property id `v`, and `u = h − P v`), or must `FlashRequest`/`PropertyCapabilities` widen?
- **C2 Pressure–flow semantics.** Dynamic plants need flows driven by pressure differences
  (valve equations, pump curves) and vessels with volume. All current units pin `P_out`. Is this
  purely additive (new unit models/variants), or do ports, the IR, or DOF analysis assume that
  flows and pressures are specified in a way that would need reopening?
- **C3 Energy holdup: U in manifests, H in the PTC mass.** Must the manifest, the PTC mapping and a
  future physical mass matrix be kept apart explicitly now (e.g. the PTC registry stating that its
  holdup is a pseudo-holdup), so that a later transient ADR cannot reuse R-032's enthalpy content
  as a physical holdup by accident? Derive, or state as a constraint, the U–H relation a future
  holdup unit must use.
- **C4 Steady and dynamic forms of one unit.** Should a future dynamic heater be the same model
  with a mode (IDAES-style `dynamic`/`has_holdup` configuration, steady state = derivatives zero),
  or a separate model variant sharing kernels? What does each imply for `model_version`
  (`<label>@<structure_sha256>`, ADR 0002 D2), manifests, and the equation-level identity? Is any
  factoring of the current unit models cheap now and expensive later?
- **C5 Phase logic under time stepping.** The phase contract (ADR 0005, T05b v2 with `ZERO_FLOW`)
  runs inside one steady-state solve. In an implicit time step each step is a similar nonlinear
  solve, and a phase change becomes an event needing consistent re-initialization. Does anything
  in the phase contract, `AttemptContext`, signatures or `root_fingerprint` assume a single solve
  per run?
- **C6 Result, run, job and replay records.** T07 is about to define `Job` and job events. Should
  the Job/job-event schemas now allow a run that produces many solves or a trajectory (streamed
  partial results, per-step certificates) rather than exactly one `SolveResult`? Does
  `RunManifest`/replay identity assume one final state?
- **C7 Time-varying specifications.** Switching feeds are specifications with a schedule. ADR 0008
  D1/D4.1 routes them through the orchestrator as pinned values. The Specification schema has
  `value: number` or `bounds` under `additionalProperties: false`. Reserve a schedule form now, or
  is a later additive `oneOf` branch with a migration report cheap enough?
- **C8 Differential markers for structural analysis.** A DAE index analysis needs to know which
  variables are differentiated. D2.3 puts holdup states in `x`; the accumulation declaration names
  the holdup symbol per row. Is that link (row → holdup variable) sufficient, or does the variable
  schema/graph layer need a reserved marker now?

## 6. Already decided, not open

- Dynamics deferred (blueprint §2.2); Frank does want them later — this amendment prepares, it
  does not schedule.
- R-001 / ADR 0008 as ruled, including the **rejected** `EvaluationContext.time` field.
- R-032: PTC mass is residence time × phase-resolved outflow content, enthalpy not internal
  energy, one θ. That is a PTC decision and stands; C3 asks only how it is kept separate.
- ADR 0011 / R-036: the PH closure lives in the unit layer, not the provider.
- Backend CasADi 3.8.0 (ADR 0003).

**Genuinely open:** C1–C8 and anything you add.

## 7. Already tried and rejected

- Deferring all readiness provisions until dynamics are scheduled (R-001's rejected alternative):
  rejected because retrofitting accumulation slots reopens every unit model.
- A time coordinate in `EvaluationContext` (P-1 as first proposed): rejected in ADR 0008 D1 — time
  would have to be excluded from the exact-property cache key by an untested rule, and a pinned
  input at the stage time is already the right concept.

## 8. How the answer will be verified

- Each adopted provision names its executable test, in the style of ADR 0008's H1–H6
  (`tests/test_adr_0008_transient_readiness.py`), or is stated as a constraint on a named future
  package with the check that package must pass.
- `PATH=.venv/bin:$PATH ./scripts/check.sh` stays green on the branch; SYN-001 digests and
  fixtures unchanged (bit-identical).
- The build lane implements the adopted provisions on this branch; the design lane (`reviewer`)
  reviews before merge; Frank approves the amendment.

## 9. Deliverable

Write **"Amendment 1"** as a new section appended to `docs/adr/0008-transient-extension-readiness.md`
on this branch, status *Proposed*, containing: the ruling per candidate (adopt / constraint on a
named package / reject as additive) with reasons; for each adopted provision the exact change,
migration impact and acceptance test; the U–H constraint for future holdup units (C3); where each
provision sits relative to blueprint §2.2's line; open questions for Frank with recommended
defaults; and the draft text of an R-001 register update. Keep it as short as the rulings allow.
Commit on the branch with a message naming ADR 0008 Amendment 1.

## 10. Out of scope

Building any dynamic capability; choosing an integrator, index-reduction method or event-location
algorithm; control; any change to T06's branch or files; any numerics change; surveying other
simulators beyond what C4's single design comparison needs.
