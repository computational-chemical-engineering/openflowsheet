# T05 W0.2 — Generalizing the flowsheet, the lifted-split registry and the K04 check set

**Package:** T05, branch `wp/T05`. **Lane:** design (`architect`), 2026-09-25. **Brief:** `docs/briefs/T05-W0.2-generalization.md`.
**Governs:** spec `docs/derivations/T05-unit-models-spec.md` §11, §12, §21, §22 W1/W11–W13; ADR 0011 D3 (bit identity).
**Status:** design. Nothing here is an implementation result. Every "measure" below is a fact the build lane records in `docs/t05-measurements.md`.
**Amended 2026-09-25, ruling round** (design lane, `specifier`; `docs/briefs/T05-rulings.md` §4; review `docs/reviews/T05-review.md` S1, S3, N4): §1.3 R4 (the converse assembly rule), §2.2 step 5 (the saturation-route exception), §4.3 (summation order; the K02 splitter's energy check), §6 (what R0 admits), §7 W1.d (the pair and the coverage assertion). Each amendment is marked in place with its reason. No registered number changes.

---

## 0. Frozen-interface verdict

**No frozen interface, schema, check category, quantity kind, tolerance, `SolveEvent` outcome or event kind changes.** Checked item by item:

| Frozen item | What this design uses | Change |
| --- | --- | --- |
| `CompiledProblem`, `PropertyProvider`, `Application` (plan §2.1) | unchanged; no new call | none |
| `ProcessRevision` schema | only existing fields: `instances[].parameters` (Quantities, free names), `connections[].phase_capability`, `specifications[].target` with the paths SYN-001's revisions already use (`state.n/T/P`, `outlet.T/P`, `duty.<name>`, `parameters.<name>`) | none |
| `ExecutionPlan` (ADR 0009) | a plan of one `solve_eo` step — the shape SYN-001's `method: eo` plans already have | none |
| `SolvePlan`, `AttemptContext`, `Checkpoint` | unchanged; `initializer_chain` and `initializer_source` are free strings | none |
| `SolveEvent` | outcomes `INITIALIZATION_FAILED`, `UNSUPPORTED_RANK_STRUCTURE`, `PTC_MAPPING_INVALID`; kind `initializer_rejected` — all existing | none |
| `SolutionCertificate` | the nine categories; ids are free strings; `phase_branch` is an open object | none |
| K04 `KIND_TOLERANCE` / `check_policy_sha256` | not edited; shaft work is judged with `heat_rate` (ADR 0011 D3 iv) | none |
| ADR 0001, ADR 0008 semantics | unchanged | none |

One non-frozen obligation is discharged, not changed: ADR 0002 D2.7 ("the label must change whenever the equation set changes") for a revision-built flowsheet is met **by the label** (§1.4), exactly as SYN-001 meets it. `compiled-problem-structure-v2` is **not** introduced (§9, Q-D).

The stop condition is not triggered.

---

## 1. The seams

### 1.1 Decisions and the alternatives rejected

| # | Decision | Rejected | Why |
| --- | --- | --- | --- |
| D1 | A revision-built flowsheet is a new class, `RevisionFlowsheet`; `Syn001Flowsheet` is **not edited**. The dispatch rule everywhere is `isinstance(flowsheet, Syn001Flowsheet)` → legacy path, verbatim; otherwise the general path. | A `Protocol` both satisfy | Every consumer that differs (tear, start state, splits, mass mapping, verifier) needs the concrete type anyway; the protocol would add a name without removing a branch. SYN-001 stays the only legacy flowsheet forever; every later flowsheet is revision-built. |
| D2 | A revision-built flowsheet is solved as **one EO region over every unit with rows**, started from a sequential traversal from dormant torn streams (K03's `G(0)` pattern, two passes). The tear path stays SYN-001-only and refuses a general flowsheet, typed. | (a) A generalized tear problem; (b) T02's per-node plan with generic `evaluate` steps | (a) needs a generic Schur tear with `T` in the tear (C3), a generic attempt signature (`SIGNATURE_UNITS`, `flash_signature` are SYN-001's) and a generic traversal-with-partial-guesses — large, and none of it is required by an assertion. The region path is already generic: signature units from equilibrium rows, lifted splits by descriptor, ADR 0005's contract, PTC, edge 3. (b) An `evaluate` step carries no `SolvePlan` and no root fingerprint, so a C1 result could not be certified (`declaration_unidentified`); making evaluate steps solve would change the `ExecutionPlan` document. One region gives one identity over the full state, which is what the certificate and A24 need. T05's flowsheets have ≤ 8 streams. |
| D3 | Lifted splits are discovered through a **registry keyed by model id** (`orchestrator/splits.py`), two styles, one rule per model; `syn001_lifted_splits` is untouched. | A `lifted_splits()` member on each unit | The K02 heater (in C1) must declare its split and K02 files are not edited (brief §6); a registry covers K02 and T05 with one mechanism, as T04's mass mapping already does. Drift between the registry and the rows a unit authors is closed by a structural-agreement test (§3.3), which is stronger than a second naming site. |
| D4 | The verifier gets a **table keyed by model id** (`verify/table.py`) that reads only the state, the revision document and a fresh provider. SYN-001 keeps its legacy entry points and code; the general path is a new entry, `verify_revision`. | Rewriting `checks.py` around the table and deriving SYN-001's legacy ids from it | Every legacy id, order and value is then protected by construction instead of by a mapping test. The duplication (~60 lines of admissibility logic) is pinned by a bitwise cross-validation test (§4.5). |
| D5 | Revision configuration is read from existing schema fields by fixed rules (§1.3); the builder applies **no defaults**. | Encoding configuration in new fields, or defaulting absent inputs | New fields change a frozen schema. Defaults would make "absent" and "0" two labels for one function. |

### 1.2 Modules (all new unless marked)

| Module | Holds |
| --- | --- |
| `src/process_runtime/models/revision_flowsheet.py` | `RevisionError`, `InstanceView`, `RevisionView`, `parse_revision`, `configuration_sha256`, `RevisionFlowsheet`, `FlowsheetPass` |
| `src/process_runtime/application/revision_binding.py` | `RevisionBinding`, `MODEL_BUILDERS`, `bind_revision_flowsheet` |
| `src/process_runtime/orchestrator/splits.py` | `SplitRule`, `SPLIT_RULES`, `lifted_splits` |
| `src/process_runtime/orchestrator/revision.py` | `INITIALIZER_ID`, `InitialStateFailure`, `instances_of`, `initial_state`, `plan_revision` |
| `src/process_runtime/orchestrator/mass.py` (edit, additive) | `residence_time(wiring, components)` |
| `src/process_runtime/orchestrator/executor.py` (edit) | dispatch helpers; typed refusals |
| `src/process_runtime/verify/table.py` | `MODEL_CHECKS`, `revision_checks`, `revision_phase_branch` |
| `src/process_runtime/verify/certificate.py` (edit) | `_issue` (extracted), `verify_revision`, guard in `verify` |
| `src/process_runtime/verify/checks.py` (edit, one parameter) | `bounds_checks(provider, state, streams=STREAMS)` |

No file under `src/process_runtime/models/syn001/`, `thermo/`, `graph/`, `compile/` and no `models/__init__.py` line is edited by W1.

### 1.3 The revision encoding (normative for the builder, the verifier and W11's case files)

- **R1 Ids.** Instance id = unit id, connection id = stream id; both match `^[A-Za-z0-9][A-Za-z0-9_-]*$` (no `.` or `:`, which K02's ids use as separators). `instances` are listed in flow order: that order is the **declaration order** (units, rows, `branch_found`). Material `connections` are listed in stream order: that order is the **stream allocation order**. A multi-stream port carries its streams in connection order.
- **R2 Components** are exactly `[A, B, C]` (the verifier's `stream_of` and `k_values` assume them; anything else is refused `unsupported`).
- **R3 Only material connections**, each with both endpoints and a `phase_capability`. An energy or signal connection, or a missing capability, is refused.
- **R4 Declared phases** come from `phase_capability` of the connection on the port: `liquid` → `LIQUID`, `vapor` → `VAPOR`, `vapor_liquid` → lifted (`inlet_phase = None` on an inlet). One field per stream means a producer's lifted outlet cannot be declared single-phase by its consumer — R-039's assembly rule holds by construction.
  *Amended 2026-09-25, ruling round (review S1, measured P1).* **The converse is checked at binding.**
  - **The rule.** A `vapor_liquid` material connection is admitted only when its `from` end is the `outlet` port of a model with an `outlet`-style `SPLIT_RULES` entry (§3.1). Otherwise `bind_revision_flowsheet` refuses it right after the port check: `Unbound("unsupported", "port_phase_unsupported(<producer unit>.<port>)")`, the existing code in its existing format.
  - **Why.** A consumer with `inlet_phase = None` reads `<S>.vap.*` and `<S>.liq.*`, which only such a producer allocates. A feed, a flash-style product or any other producer declared `vapor_liquid` used to bind and then fail with an untyped `KeyError` in `plan_revision`.
  - **What it moves.** No label: every registered revision (C1–C3X, the SYN-001-shaped one) passes the check.
- **R5 Process-variable specifications** (`role: fixed`) are *pins*, keyed by the column they fix and routed to one instance: connection `state.n` (+`component`), `state.T`, `state.P` → the stream's producer; instance `outlet.T|P` → that coordinate on every outlet stream of the instance; instance `duty.Q` → column `<U>.Q` of that instance. Instance `parameters.<name>` specifications must equal the instance parameter of that name (conflict otherwise; they supply it if the parameter is absent). Every pin must be consumed by the owner's builder, else refused `unsupported` with `specification_unconsumed(<spec id>)`. `role` other than `fixed` is refused `unsupported` (no cross-unit specification in v0.1).
- **R6 Model parameters** are instance `parameters` (Quantity `value`, SI) under the names of this table; all required, no defaults:

| Model id | Instance parameters | Pins consumed | Port phase rule | `configuration` (label digest) |
| --- | --- | --- | --- | --- |
| `syn001.feed_source` | — | outlet `n.<c>` (each), `T`, `P` | — | `{}` |
| `syn001.adiabatic_mixer` | `pressure_drop` optional, must be `0.0` | — | every port `liquid` | `{}` |
| `syn001.tp_heater` | `pressure_drop` optional, `0.0` | outlet `T` | outlet `vapor_liquid` | `inlet_phase` |
| `syn001.tp_flash` | `pressure_drop` optional, `0.0` | `T` and `P` of both outlets (equal) | `vapor`→vapor, `liquid`→liquid | `inlet_phase` |
| `syn001.stream_splitter` | `split_fraction` | — | — | `{}` |
| `syn001.product_sink` | — | — | — | `{}` |
| `syn001.ph_flash` | `pressure_drop` | `<U>.Q` | `vapor`→vapor, `liquid`→liquid | `inlet_phase` |
| `syn001.valve` | — | outlet `P` | outlet `vapor_liquid` | `inlet_phase` |
| `syn001.liquid_pump` | `efficiency` | outlet `P` | inlet, outlet `liquid` | `{}` |
| `syn001.conversion_reactor` | `nu.<c>` (each), exactly one `conversion.<k>` (`<k>` is the key), `pressure_drop` | outlet `T` **xor** `<U>.Q` | outlet `vapor_liquid` | `inlet_phase`, `key_component`, `energy_specification` (`outlet_temperature`/`duty`) |
| `syn001.component_separator` | `split.<c>` (each) | — | `top`, `bottom` ∈ {`liquid`,`vapor`} | `inlet_phase`, `top_phase`, `bottom_phase` |
| `syn001.heat_exchanger` | — | exactly one of `hot_outlet` `T`, `cold_outlet` `T`, `<U>.Q` | each side's inlet = outlet ∈ {`liquid`,`vapor`} | `specification`, `hot_phase`, `cold_phase` |

The builder passes each value to the model's constructor argument of the same meaning; a constructor's `SpecificationError` becomes `Unbound("unsupported", <first line of its message>)`.

### 1.4 Signatures

```python
# models/revision_flowsheet.py
class RevisionError(ValueError):
    kind: Literal["conflict", "incomplete", "unsupported"]; code: str     # R-022's three kinds

@dataclass(frozen=True)
class InstanceView:
    unit_id: str
    model_id: str
    ports: Mapping[str, tuple[str, ...]]            # wired material port -> streams (R1 order)
    directions: Mapping[str, Literal["inlet", "outlet"]]   # from `to.port` / `from.port`
    phases: Mapping[str, Literal["LIQUID", "VAPOR"] | None]  # R4, per wired port
    parameters: Mapping[str, float]                  # R6
    pins: Mapping[str, float]                        # R5: column id -> value
    @property
    def wiring(self) -> Wiring: ...

@dataclass(frozen=True)
class RevisionView:
    components: tuple[str, ...]
    instances: tuple[InstanceView, ...]              # declaration order
    streams: tuple[str, ...]                         # allocation order
    edges: tuple[tuple[str, str, str], ...]          # (stream, producer, consumer), connection order

def parse_revision(document: Mapping[str, Any]) -> RevisionView     # raises RevisionError (R1–R5)

def configuration_sha256(view: RevisionView, configurations: Mapping[str, Mapping[str, str | None]]) -> str
    # ADR 0002 document_sha256 of {"scheme": "FSR1", "components": [...], "streams": [...],
    #   "instances": [{"unit", "model", "ports": {port: [streams]}, "configuration": {...}}, ...]}
    # — the revision minus every pinned value: what selects expressions without changing ids.

@dataclass(frozen=True)
class FlowsheetPass:
    status: PropertyStatus
    streams: Mapping[str, StreamState]               # every stream's value in this pass; a torn stream carries its guess
    evaluations: Mapping[str, UnitEvaluation]        # by unit id
    order: tuple[str, ...]                           # evaluation order
    torn: tuple[str, ...]                            # streams used before produced, first-use order
    computed_torn: Mapping[str, StreamState]         # G(guess) of each torn stream
    failed_unit: str = ""
    code: str = ""                                   # first line of the failing unit's message

@dataclass(frozen=True)
class RevisionFlowsheet:
    provider: PropertyProvider                       # PropertyMeter(Syn001Provider()), metered from construction
    context: EvaluationContext                       # EvaluationContext("revision-structural", "0"*64, None)
    components: tuple[str, ...]
    instances: tuple[UnitModel, ...]                 # declaration order
    wiring: Mapping[str, Wiring]
    streams: tuple[str, ...]
    configuration_sha256: str
    def units(self) -> tuple[UnitModel, ...]: return self.instances
    @property
    def label(self) -> str:   # f"FSR1-{configuration_sha256[:12]}-{provider_id}-{impl[:12]}-{data[:12]}" (50 chars for syn001);
                              # checked against syn001.flowsheet.MODEL_LABEL, SpecificationError otherwise
    def spec(self) -> ProblemSpec:  # assemble(label=self.label, units=list(self.instances), wiring=self.wiring,
                                    #          streams=self.streams, components=self.components)
    def traverse(self, guesses: Mapping[str, StreamState] = MappingProxyType({})) -> FlowsheetPass

# application/revision_binding.py
@dataclass(frozen=True)
class RevisionBinding:
    flowsheet: RevisionFlowsheet
    spec: ProblemSpec                                # flowsheet.spec(), computed once
    graph: ProcessGraph
    row_units: Mapping[str, str]
    revision_sha256: str                             # document_sha256(document)
MODEL_BUILDERS: Final[Mapping[str, Callable[[InstanceView, PropertyProvider, EvaluationContext, tuple[str, ...]],
                                            tuple[UnitModel, Mapping[str, str | None]]]]]
def bind_revision_flowsheet(document: Mapping[str, Any]) -> RevisionBinding | Unbound

# orchestrator/splits.py  — §3
# orchestrator/revision.py
INITIALIZER_ID: Final = "traversal-G0-v1"
@dataclass(frozen=True)
class InitialStateFailure:
    unit: str; code: str
    @property
    def message(self) -> str: return f"initializer_failed({self.unit}): {self.code}"
def instances_of(flowsheet: RevisionFlowsheet) -> tuple[tuple[str, str, Wiring], ...]
def initial_state(flowsheet: RevisionFlowsheet, variable_ids: Sequence[str]) -> dict[str, float] | InitialStateFailure
def plan_revision(binding: RevisionBinding, policy: SolvePolicy, *, trace: Trace | None = None
                  ) -> tuple[ExecutionPlan | PlanRefusal, StructuralReport]

# orchestrator/mass.py (additive)
def residence_time(wiring: Mapping[str, Wiring], components: Sequence[str]) -> MassMapping
    # MassMapping(MASS_POLICY, _registered_rules(), wiring, tuple(components)); syn001_residence_time untouched

# orchestrator/executor.py (signature widened only)
def execute_plan(*, plan, flowsheet: Syn001Flowsheet | RevisionFlowsheet, spec, policy, trace=None) -> PlanResult

# verify/certificate.py (additive)
def verify_revision(binding: RevisionBinding, revision: Mapping[str, Any], result: Any, *,
                    policy: CheckPolicy | None = None, state: Mapping[str, float] | None = None,
                    solve_plan: SolvePlan | None = None) -> SolutionCertificate
```

**`bind_revision_flowsheet`** (in this order; each `RevisionError` → `Unbound(kind, code)`): `parse_revision`; every model id in `MODEL_BUILDERS` (else `unsupported`, `model_unsupported(<id>)`); construct each unit with the metered provider; check every wired port against `unit.ports()` (material kind, direction, multiplicity 1 → one stream) and `unit.model_id == instance.model_id`; check every pin consumed; `flowsheet = RevisionFlowsheet(...)`; `spec = flowsheet.spec()`; `row_units` from each unit's `contribute(wiring, components).equations` (as `structural_inputs` does); `graph = ProcessGraph(units=<all instance ids, declaration order>, connections=<Connection(stream, producer, consumer, state_columns=(*S.n.<c>, S.T, S.P)) for sorted(set(edges))>, instance_ids={u: u}, column_owners=binding._column_owners(spec.variable_ids, {stream: producer}, units))`.

**Variable order of `spec()`**: `assemble`'s own rule, fed by R1 — every stream in allocation order (flows in component order, `T`, `P`), then unit-owned variables in declaration order (each unit's `variable_ids` order, first occurrence kept). No new ordering code.

### 1.5 The traversal (normative)

```
traverse(guesses):
  value = {}; computed = set(); torn = []; computed_torn = {}; evaluations = {}; order = []
  pending = list(instances)                                           # declaration order
  while pending:
    unit = first u in pending whose every inlet stream has a value     # inlet streams: material ports of
    if unit is None:                                                   # u.ports() with direction inlet, in
      unit = first u in pending with >= 1 inlet stream in computed     # ports() order, then R1 stream order
      if unit is None: return fail(pending[0], "no_computed_inlet")
      label = value[first inlet stream of unit that is in computed]
      for s in inlet streams of unit without a value:
        value[s] = guesses[s] if s in guesses else StreamState(n=(0.0,)*|C|, temperature=label.T, pressure=label.P)
        torn.append(s)
    ev = unit.evaluate({port: tuple(value[s] for s in wiring[unit][port]) for inlet ports}, context)
    if ev.status != "ok": return fail(unit.unit_id, ev.status, ev.message.splitlines()[0])
    for each outlet material port p with stream s:
      if s in torn: computed_torn[s] = ev.outlets[p]                 # value[s] keeps the guess
      else: value[s] = ev.outlets[p]
      computed.add(s)
    evaluations[unit.unit_id] = ev; order.append(unit.unit_id); pending.remove(unit)
```

The deadlock rule depends only on the graph, so a second pass tears the same streams. A dormant guess is a legal inlet for every unit (ADR 0001 D3.4); its label is the first computed inlet's `(T, P)`, so a mixer's equal-pressure rule holds.

---

## 2. The solve path

### 2.1 The common path (C1, C2, C3, C3X)

1. `binding = bind_revision_flowsheet(document)`.
2. `plan, report = plan_revision(binding, policy)`: `declaration_identity(spec)`; `trace_declaration` and `analyse` with `row_units=binding.row_units`, `specification_ids={}`; the structural-agreement guard of §3.3 (raises `ValueError`, a defect); `whole = build_region(declaration, graph, report, units)` with `units` = every instance that authors a row, in declaration order (sinks excluded); `plan_or_refusal(..., manifests={u.unit_id: u.manifest() for u in flowsheet.units()}, specifications=(whole,))`. The plan is one `solve_eo` step; its `signature_units` are the lifted units in declaration order. A declaration that T01 does not report `STRUCTURALLY_CLOSED` is refused by `build_execution_plan`'s existing `ValueError` (no registered case is such).
3. `run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)`; `_solve_eo`'s general branch (§2.3) starts from `initial_state`.
4. If `CONVERGED`: `verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)`.

### 2.2 `initial_state(flowsheet, variable_ids)`

1. `p1 = flowsheet.traverse({})`; failure → `InitialStateFailure(p1.failed_unit, p1.code)`.
2. If `p1.torn` is empty, `p = p1`; else `p = flowsheet.traverse(p1.computed_torn)`; `p.torn != p1.torn` is a defect (`ValueError`); failure → `InitialStateFailure`.
3. Streams: `S.n.<c>`, `S.T`, `S.P` from `p.streams[S]` for every `S` in `flowsheet.streams`.
4. Owned variables, per evaluation: `duty_id(U)` ← exactly one of `ev.duty`, `ev.transferred_duty` that is not `None` (both or neither: `ValueError`); `<U>.W` ← `ev.work`; `<U>.xi` ← `ev.extent` — each only if the id is in `variable_ids`, and `None` there is a defect.
5. Lifted splits, per descriptor of `lifted_splits(instances_of(flowsheet), components)`: style `outlet` — `tp_state(flowsheet.provider, p.streams[d.stream], flowsheet.context)` fills `d.vapor`, `d.liquid`, `d.vapor_total = sum(split.vapor.n)`, `d.liquid_total = sum(split.liquid.n)` (a refusal → `InitialStateFailure(d.unit, f"kernel_refused({d.stream})")`); style `products` — `d.vapor_total = sum(state[v] for v in d.vapor)`, likewise liquid.
   *Amended 2026-09-25, ruling round Q-R8 (review S3).* **One known exception: the saturation route** (spec §4.4 step 2), where a heater-style PH-type outlet carries exactly one flowing component with `0 < β < 1`.
   - **What goes wrong.** The re-flash at `(n, T_sat, P)` gives `V = 0`, because the provider classifies `T_sat` as liquid. That is not the unit's lever-rule split, so the start misses the energy row by `β n Δh`.
   - **Why the step is not changed.** The EO path fails on this outlet from any start, the exact split included (spec §4.7 (b), A30), so taking the closure split would change no outcome. On every other route the closure split *is* the provider's flash at the outlet's `(n, T, P)` (spec §4.4 step 6), the same call as this step.
   - **The fix.** The comment at `orchestrator/revision.py` that says the re-flash uses "the kernel the unit used" is corrected to state this exception.
6. Any `variable_ids` entry unassigned → `ValueError(f"initial_state_incomplete({id})")`. Return the dict in `variable_ids` order.

No compiled residual or Jacobian is called (A27 depends on it). Property calls made here fall outside the region's metered window — the legacy start (`Syn001TearProblem(...).reconstruct(...)`) is outside it too.

### 2.3 The executor dispatch (exact)

`_legacy(f) := isinstance(f, Syn001Flowsheet)`. Every legacy expression below stays the pre-T05 expression; only call sites change to helpers.

| Site | Legacy (`_legacy` true) | General |
| --- | --- | --- |
| `_region(...)`, `splits=` | `syn001_lifted_splits(flowsheet.components)` | `lifted_splits(instances_of(flowsheet), flowsheet.components)` |
| `_region(...)`, `mass_mapping=` | `syn001_residence_time(flowsheet.components)` | `residence_time(flowsheet.wiring, flowsheet.components)` |
| `_solve_eo`, no specification rows: `start` | `dict(Syn001TearProblem(flowsheet).reconstruct(flowsheet.initial_recycle()))` | `initial_state(flowsheet, spec.variable_ids)`; on `InitialStateFailure`: record `initializer_rejected` (message `failure.message`, fields as `_missing_guess`) and return `StepResult(index, "solve_eo", region.units, "INITIALIZATION_FAILED", message=failure.message)`, `spent`, `None` |
| `_solve_eo`, `source` | `INITIALIZER_ID` (tear's) | `orchestrator.revision.INITIALIZER_ID` (`"traversal-G0-v1"`) |
| `_solve_eo`, with specification rows | unchanged | `StepResult(..., "UNSUPPORTED_RANK_STRUCTURE", message="specification_region_unsupported(revision_flowsheet)")` |
| `_converge` (first statement) | unchanged | `_refused(step, "tear_path_unsupported(revision_flowsheet)")`, `spent`, `None` |
| `evaluate` step | unchanged | unchanged (unreachable: `plan_revision` emits no evaluate step) |

Also typed at the SYN-001-only public entries, as the first statement: `solve_tear`, `run_session` (and `solve_and_bundle` through it) raise `TypeError("syn001_only(<function>)")`; `verify` raises `VerifierError("syn001_only(verify)")` — for anything that is not a `Syn001Flowsheet`. `bind_revision`, `structural_inputs`, the A02 binding, `Syn001TearProblem`, `build_plan`, `attempts.SIGNATURE_UNITS`/`flash_signature` stay SYN-001-only and are not edited.

### 2.4 Per case

The revisions follow §1.3; instance order, connections and pins are:

| Case | Instances (declaration order) | Connections: id `from.port → to.port` (`capability`) | Pins / parameters |
| --- | --- | --- | --- |
| C1 | U-FEED, U-PUMP, U-HEAT, U-VLV, U-PHF, U-SINK-V, U-SINK-L | S1 FEED.outlet→PUMP.inlet (liquid); S2 PUMP.outlet→HEAT.inlet (liquid); S3 HEAT.outlet→VLV.inlet (vapor_liquid); S4 VLV.outlet→PHF.inlet (vapor_liquid); S5 PHF.vapor→SINK-V.inlet (vapor); S6 PHF.liquid→SINK-L.inlet (liquid) | S1 `(1,1,1)`, 300 K, `P_r`; S2.P `1.8e5`, `efficiency 0.75`; S3.T 360; HEAT `pressure_drop 0`; S4.P `P_r`; PHF `duty.Q 10000`, `pressure_drop 0` |
| C2 | U-FEED, U-MIX, U-RX, U-SEP, U-PROD | S1 FEED.outlet→MIX.inlet (liquid); S2 MIX.outlet→RX.inlet (liquid); S3 RX.outlet→SEP.inlet (vapor_liquid); S4 SEP.top→MIX.inlet (liquid); S5 SEP.bottom→PROD.inlet (liquid) | S1 `(2,1,0)`, 300 K, `P_r`; RX `nu.A −2`, `nu.B −1`, `nu.C 3`, `conversion.A 0.5`, `pressure_drop 0`, S3.T 315; SEP `split.A 0.9`, `split.B 0.8`, `split.C 0.05` |
| C3 / C3X | U-FEED, U-HX, U-MIX, U-PHF, U-SPLIT, U-PROD, U-SINK | S1 FEED.outlet→HX.cold_inlet; S2 HX.cold_outlet→MIX.inlet; S3 MIX.outlet→PHF.inlet; S4 PHF.vapor→PROD.inlet (vapor); S5 PHF.liquid→SPLIT.inlet; S6 SPLIT.recycle→MIX.inlet; S7 SPLIT.purge→HX.hot_inlet; S8 HX.hot_outlet→SINK.inlet (all liquid except S4) | S1 `(1,1,1)`, 300 K, `P_r`; S8.T 310 (C3X: 290); PHF `duty.Q 48000`, `pressure_drop 0`; SPLIT `split_fraction 0.6` |

| Case | Torn by the traversal | Expected path | `branch_found` (A26) |
| --- | --- | --- | --- |
| C1 | none (one pass; the start is the causal solution) | region Newton, `CONVERGED` (A17's "acyclic path's `ok`" is not used) | `[[U-HEAT, LIQUID], [U-VLV, TWO_PHASE], [U-PHF, TWO_PHASE]]` |
| C2 | `S4`, dormant at S1's `(300 K, P_r)` | two passes, region Newton, `CONVERGED` | `[[U-RX, LIQUID]]` |
| C3 | `S7` (label from S1), then `S6` (label from S2) | two passes, region Newton, `CONVERGED` | `[[U-PHF, TWO_PHASE]]` |
| C3X | as C3 | pass 1 passes (hot side dormant: the 290 K spec becomes its label, `Q = 0`); pass 2 reaches U-HX with a flowing hot side and fails `temperature_cross(cold_end)` → `INITIALIZATION_FAILED`, message `initializer_failed(U-HX): temperature_cross(cold_end)` — A20's first branch | — |

A20's second branch (`bounds_and_domain.U-HX.cold_end` = `+10 K`, the only failing check) is exercised by W12 on the twin's C3X state through a `solve_region` call started from that state (no new API; §8).

---

## 3. Lifted-split discovery

### 3.1 The registry

```python
SplitStyle = Literal["outlet", "products"]      # heater-style lifted outlet; flash-style products
@dataclass(frozen=True)
class SplitRule:
    style: SplitStyle
    equilibrium: str                            # the equation family of its equilibrium rows
SPLIT_RULES: Final[Mapping[str, SplitRule]] = {
    "syn001.tp_heater":          SplitRule("outlet",   "HEAT-equilibrium"),
    "syn001.tp_flash":           SplitRule("products", "FLASH-equilibrium"),
    "syn001.valve":              SplitRule("outlet",   "VLV-equilibrium"),
    "syn001.conversion_reactor": SplitRule("outlet",   "RX-equilibrium"),
    "syn001.ph_flash":           SplitRule("products", "PHF-equilibrium"),
}
def lifted_splits(instances: Sequence[tuple[str, str, Wiring]], components: Sequence[str]) -> tuple[LiftedSplit, ...]
    # one descriptor per instance whose model id is in SPLIT_RULES, in the order given (declaration order)
```

One rule per model makes R-039's "at most one lifted split per unit" structural. The descriptor is `region.LiftedSplit`, unchanged:

| Field | `outlet` (unit `U`, `S = wiring.one("outlet")`) | `products` (`I = wiring.one("inlet")`, `V = one("vapor")`, `L = one("liquid")`) |
| --- | --- | --- |
| `unit`, `stream` | `U`, `S` | `U`, `I` |
| `feed` | `flow_id(S, c)` | `flow_id(I, c)` |
| `temperature`, `pressure` | `temperature_id(S)`, `pressure_id(S)` | `temperature_id(V)`, `pressure_id(V)` |
| `vapor`, `liquid` | `vapor_flow_id(S, c)`, `liquid_flow_id(S, c)` | `flow_id(V, c)`, `flow_id(L, c)` |
| `vapor_total`, `liquid_total` | `vapor_total_id(S)`, `liquid_total_id(S)` | `total_flow_id(V)`, `total_flow_id(L)` |
| `equilibrium_rows` | `row_id(U, rule.equilibrium, c)` | same |
| `vapor_definition`, `liquid_definition` | `row_id(U, "Vdef")`, `row_id(U, "Ldef")` | `row_id(U, "Ndef", "vapor")`, `row_id(U, "Ndef", "liquid")` |

### 3.2 SYN-001 stays byte-identical

`syn001_lifted_splits` and its two consumers (`executor._region`, `tear.solve_tear`'s fingerprint) are not edited; the executor reaches it through the legacy branch of §2.3. The generalization is **proved** equal, not assumed: `lifted_splits` applied to SYN-001's instances (`[(u.unit_id, u.model_id, WIRING[u.unit_id]) for u in Syn001Flowsheet(...).units()]`) must `==` `syn001_lifted_splits(("A","B","C"))`, and `sha256(repr(...))` must be `fc36484e…` (W1.a).

### 3.3 Structural agreement (the guard against registry drift)

For a spec `S`, its `row_units`, and `T01`'s `Declaration` `D`, with `lifted = {row_units[r] : S.row_kinds[r] == "molar_flow_squared"}`:
(a) `{d.unit} == lifted` — a unit with equilibrium rows and no rule is `ValueError("lifted_split_unregistered(<model id>)")`, a rule without rows `ValueError("lifted_split_without_rows(<unit>)")`; (b) `d.equilibrium_rows` equals that unit's `molar_flow_squared` rows in `S.equation_ids` order; (c) every variable id of `d` is in `S.variable_ids`; (d) `D.rows[d.vapor_definition].columns == set(d.vapor) | {d.vapor_total}`, likewise liquid; (e) each equilibrium row's columns contain its component's vapor and liquid ids and both totals. `plan_revision` enforces (a); the test of W1.a enforces (a)–(e) on SYN-001, W1.c on the SYN-001-shaped revision, W12 on C1–C3X.

---

## 4. The verifier table

### 4.1 What is shared and what is not (R-016)

Shared with the solve side: ids (the split registry, the unit layer's id helpers) and the revision's values (`parse_revision`) — the declaration's inputs, as `verify_bound` already shares the binding's targets. Not shared: any row builder, causal evaluator, kernel or cache. Energies are fresh flashes of each stream's own `(n, T, P)` (`checks.enthalpy_flow`); phase enthalpies and derivatives come from `provider.evaluate_phase(PropertyRequest(state, phase, ("h",)))`; the provider is a fresh `Syn001Provider()` (every table key is a `syn001.*` model).

### 4.2 `verify_revision`

1. `_require_converged(result)`; `compiled = compile_problem(binding.spec)`; `solved = _guard(binding.spec, compiled, result, state, solve_plan=solve_plan, revision_matches=document_sha256(revision) == binding.revision_sha256)`; context from `compiled.metadata`; `final_state is None` → `_absent(...)`.
2. `target = BoundDeclaration(binding.spec, compiled, final_state)`; with a `solve_plan`, its aliases must equal `target`'s, exactly as `verify_bound` (same refusal text).
3. `view = parse_revision(revision)` (`RevisionError` → `VerifierError(f"revision_unreadable({code})")`); `splits = lifted_splits([(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components)`.
4. `rows, digest = residual_checks(...)`; `checks = rows + alias_checks(target.partition.elimination.eliminated, values) + revision_checks(view, splits, final_state, provider=Syn001Provider(), context=context, tolerances=resolved.tolerances)`.
5. `return _issue(target, result, solved, final_state, checks=checks, digest=digest, policy=resolved, declaration=NOMINAL_DECLARATION, phase_branch=revision_phase_branch(final_state, view.streams, splits))`.

`_issue` is the tail of today's `_certify`, extracted verbatim from `checks += derivative_witness(target, final_state)` to the end, with `phase_branch=` replacing the inline `_phase_branch(final_state)` (a pure function, so its evaluation point does not matter). `_certify` becomes `_run_checks(...)` followed by `_issue(..., phase_branch=_phase_branch(final_state))`.

`revision_phase_branch`: `{S: "ZERO_FLOW" | "FLOWING" for S in streams}` plus, per descriptor, key `f"{d.unit}:{d.stream}"` → `{"vapor_total", "liquid_total", "vapor": [...], "liquid": [...]}` read from the state.

### 4.3 `revision_checks` — ids, formulas, order

Order is category-major, as the legacy engine: material, energy, specification, bounds, admissibility/independent split. Within a category: instances in declaration order, each model's items in the table's row order, components in component order; then the flowsheet rows. Every formula is evaluated **left to right exactly as written**; a sum accumulates from `0.0` in declaration order (ports in the model's port order, streams in R1 order).

*Amended 2026-09-25, ruling round Q-R2; ratifies the build lane's `15aed94`; register R-048.* **One class of sum is not accumulated left to right: a Σ over the components of one stream.**

- **What counts as one.** A sum over the component index of quantities that all belong to a single stream: its flows, its lifted vapour or liquid flows, flow × component-property products of that stream, and its mole fractions and fraction × `K` products.
- **How it is computed.** With Python's builtin `sum` over the components in component order, which is the primitive K04's legacy builders use.
- **Why.** On CPython ≥ 3.12, `sum` of floats is Neumaier-compensated, and the project requires ≥ 3.13 (`pyproject.toml`). Left-to-right accumulation differs from it in the last bit. At the SYN-001-shaped `x⁰`, `Σ S3.liq.*` is 3.7937936767848512 compensated and …517 accumulated, so `material_balance.total.S3.L` is `0.0` legacy against `−4.44e-16` left to right, and the bitwise cross-validation fails.
- **Every other sum** — across ports, streams, instances and envelope terms — accumulates left to right with the `+` and `−` as written. The legacy writes those with explicit operators.
- **What moves if CPython's float `sum` ever changes.** Legacy and general would move together, and the pairing stays bitwise. Only fixtures recorded under the old algorithm could move, in the last bit, and that exposure is K04's already. `Ḣ(S)` is the fresh-flash enthalpy of stream `S`, computed once per stream in allocation order. Two-sided checks use `verify.evaluated`; `τ` = `tolerances[kind]`, `reference` = `KIND_REFERENCE[kind]`. A **one-sided** check (category `bounds_and_domain`) passes iff `value ≤ τ`, `near_threshold` iff `τ/10 < value ≤ 10τ`; it is `dormant(...)` (not applicable, `ZERO_FLOW`) when any inlet of its unit is dormant. Pinned values (`T_spec`, `P_spec`, `Q_spec`) are the view's pins; parameters the view's parameters.

| Model | Category: id (`U` = unit) | Formula | τ kind |
| --- | --- | --- | --- |
| feed | spec: `U.n.<c>`, `U.T`, `U.P` | `n − pin`, `T − pin`, `P − pin` on its outlet | flow, temperature, pressure |
| mixer | mat: `U.<c>`; energy: `U` | `Σ_k n_in(k) − n_out`; `Σ_k Ḣ(in k) − Ḣ(out)` | flow; heat_rate |
| heater | mat: `U.<c>`, `U.lifted_split.<c>`, `U.total.V`, `U.total.L`; energy: `U`; spec: `U.T` | `n_in − n_out`; `n_out − v − l`; `V − Σv`; `L − Σl`; `Ḣ(in) + Q − Ḣ(out)`; `T_out − T_spec` | flow; heat_rate; temperature |
| tp_flash (not in a T05 case; for W1's cross-check) | mat: `U.<c>`, `U.total.vapor`, `U.total.liquid`; energy: `U`; spec: `U.temperature.vapor`, `.liquid`, `U.pressure.vapor`, `.liquid` | `n_in − n_vap − n_liq`; `N − Σn`; `Ḣ(in) + Q − Ḣ(vap) − Ḣ(liq)`; `T − T_spec`; `P − P_spec` | as named |
| splitter | mat: `U.<c>`; energy: `U`; spec: `U.ratio.<c>` | `n_in − n_rec − n_pur`; `Ḣ(inlet) − Ḣ(recycle) − Ḣ(purge)` (ports `inlet`, `recycle`, `purge`; the legacy `flows["S5"] - flows["S6"] - flows["S7"]`, operation for operation); `n_rec − r n_in` — *energy added 2026-09-25, ruling round Q-R3: K04's legacy `energy_balance.splitter` had no general counterpart, and the general certificate was weaker than K04's on the splitter's temperature copies* | flow; heat_rate; flow |
| PH flash, valve, pump, reactor, separator, exchanger | spec §12.2's rows, ids as written there | spec §12.2's formulas | spec §12.2 |
| flowsheet | mat: `material_balance.envelope.<c>` | `Σ_feeds n + Σ_reactors ν_c ξ − Σ_products n`, accumulated in that order | flow |
| flowsheet | energy: `energy_balance.envelope` | `(Σ Q_ext + Σ W) − (Σ Ḣ(products) − Σ Ḣ(feeds))`; `Q_ext` = `<U>.Q` of heater, tp_flash, PH flash, reactor, separator (never the exchanger's internal `Q`); `W` = `<U>.W` of pumps | heat_rate |

Feeds are the outlet streams of `feed_source` instances; products the inlet streams of `product_sink` instances.

**Generic checks** keep their legacy ids and content: `energy_balance.enthalpy.<S>` (not applicable) for each dormant stream in allocation order, first in the energy category; `bounds_checks(provider, state, streams=view.streams)` first in the bounds category, then the one-sided unit checks.

**Admissibility category** — per descriptor in declaration order, `d` read from the state at `(d.temperature, d.pressure)`: V + L = 0 → `dormant(phase_admissibility.<U>.<S>)`; V = 0 → `phase_admissibility.<U>.<S>.bubble` (`Σ x K`, legacy `_one_sided`); L = 0 → `.dew` (`Σ y/K`); else `.closure` (`Σy − Σx`, `COMPOSITION_TOLERANCE`); then a fresh flash of `(state[d.feed], state[d.temperature], state[d.pressure])` → `independent_split.<U>.<S>.total` (`V − ΣV_flash`) and `independent_split.<U>.<S>.<c>` (`v_c − v_c,flash`), flow tolerance; dormant feed → `dormant(independent_split.<U>.<S>)`. Then **declared-phase ports**, instances in declaration order: `phase_admissibility.<U>.<port>` (single-stream port) or `phase_admissibility.<U>.<port>.<S>` (multi-stream port), value `(Ḣ(S) − Ḣ_φ(S)) / Σ_i n_i ∂h_i^φ/∂T` at the stream's `(T, P)`, two-sided, τ = `tolerances["temperature"]`; dormant stream → not applicable. Declared-phase ports per model, in this order: mixer `inlet` (each stream), `outlet`; heater, tp_flash, PH flash, valve, reactor: `inlet` when declared; pump `inlet`, `outlet`; separator `inlet` when declared, `top`, `bottom`; exchanger `hot_inlet`, `hot_outlet`, `cold_inlet`, `cold_outlet`.

**Qualifications:** every energy-category check and every admissibility/independent-split check carries `qualification(provider)`. The reactor's `energy_balance.U`, and `energy_balance.envelope` when any reactor instance is present, carry `qualification(provider) + REACTION_DATUM_NOTE` with
`REACTION_DATUM_NOTE = "; reacting unit: this balance is meaningful only under ADR 0011 D2, the provider's reference convention <convention> declared a formation datum, so the heat of reaction is carried by Hdot and never added separately"` (`<convention>` = `capabilities.reference_convention`).

**A model id without a table entry** yields one `unsupported` check `material_balance.<U>.all`, reason `model_unsupported(<model id>)` → `UNVERIFIED`, never `VERIFIED`.

### 4.4 SYN-001's dispatch

`verify`, `verify_bound`, `run_checks`, `_run_checks` and every builder in `checks.py` keep their code; SYN-001 reaches them exactly as today. The only edits on that path are the `_certify` → `_issue` extraction, the `bounds_checks` default parameter, and the `verify` type guard — each inert by construction and proved by §7's protocol.

### 4.5 Spec errata this section decides (the build lane applies them to spec §12.2 in the same commit as this note)

1. `independent_split.<stream>` → **`independent_split.<U>.<stream>`**: in C1 the valve's split and the PH flash's split are both on `S4` (and the K02 heater's and flash's both on `S3`), so the spec's id collides; §12.1's own principle is `<category>.<unit>.<item>`.
2. A declared-phase port carrying several streams (the K02 mixer's inlet) is `phase_admissibility.<U>.<port>.<stream>`; the K02 mixer's and heater's declared ports are in the set ("every declared-phase port").
3. `energy_balance.envelope` carries the ADR 0011 D2 note when a reactor is present (it sums a reactor's duty against enthalpies of different species).
4. The K02 `tp_flash` rows of §4.3 (not used by any T05 case).

---

## 5. PTC mass mapping

`residence_time(flowsheet.wiring, components)` is `T04-residence-time-v1` with its registered rules (K02 heater and flash only) over the revision flowsheet's wiring. T05 registers no rule (spec §12.4), so `resolve_mass`'s V1 refuses the first `holdup_balance` row of a T05 model in region row order: `PTC_MAPPING_INVALID`, `ptc_mapping_invalid(<row>, missing)`, before any attempt — and `initial_state` makes no compiled call, so A27's "no residual or Jacobian call" holds. The expected rows are `U-PHF:PHF-mole:A` (C1; the K02 heater's rows are mapped), `U-RX:RX-mole:A` (C2), `U-HX:HX-mole-hot:A` (C3) — W12 asserts the row it measures and records it.

---

## 6. R0 identity (A24)

A new top-level key **`t05`** in the K05 identity document, from `scripts/t05_identity.py` `identity()`, included by `k05_structural_identity.py` beside `t02`–`t04`. `structural_sha256` is the SYN-001 run's manifest hash and does not move. Per case (C1, C2, C3, and C3X — its failure trace is R0 too):

```
{"plan": execution_plan_r0(plan.as_document()),
 "outcome": run.outcome,
 **r0_projection({"solve-events.json": [e.as_document() for e in run.trace.events],
                  "structural-report.json": report.as_document(),
                  **({"solution-certificate.json": certificate.as_document()} if converged else {})}),
 "root_fingerprint": t03_identity._fingerprint(<the region result's fingerprint>)}   # None if not converged
```

Only existing projections (A24: "no new R0 field"); no message, float or digest enters. The CI comparator needs no change (it compares every key).

*Amended 2026-09-25, ruling round Q-R5 (with review N4).* **The projections stand as they are; no filter is added.** The sentence above said more than it meant, and is replaced by what R0 admits.

- **Declared constants.** They enter as their shortest decimal strings: the plan's declared `column_scales`, `row_scales` and `bounds` through `execution_plan_r0`, as `t02` has them (ADR 0009 D1 makes the plan R0 entire), and the fingerprint's registered `delta_scaled_inf`, as `t03` has it.
- **Digests of declared inputs.** `constants_sha256` (the pinned constants) and `variable_ids_sha256` (the ids) enter through T03's fingerprint projection, as `t03` has them (T03 A23).
- **Typed messages.** A typed message's first line enters, as T03's `_messages` already admits for `attempt_opened` and `solve_closed`. Registered codes carry no float (R-029, spec §3.5).
- **What never enters.** A computed float, a digest of a computed state (`opening_state_sha256`, `full_state_sha256`, dropped by T03's projection) or free text.

**One addition (review N4).** Each case's entry gains `"message": run.message.splitlines()[0] if run.message else ""`. For C3X that is `initializer_failed(U-HX): temperature_cross(cold_end)`, which is A20's discriminant, so the CI pair now compares *which* check refused and not only that one did. For C1–C3 it is `""`. The whole document's hash moves (it is measured, not registered). Check: the document **minus `t05`** hashes to `b364bb3d…` on the local machine; the full document is equal on the CI pair.

---

## 7. Work orders

**Inertness protocol P (run at the end of every W1 chunk; any item moving is a defect in the chunk, never a re-registration):** (i) `sha256sum src/process_runtime/thermo/syn001.py` = `75c9d5ba…`; (ii) gate green, `1915 + k` passed where `k` is the chunk's new tests, and `git diff --stat <base> -- tests/` lists added files only; (iii) K05 `structural_sha256` = `4ce030ca…` (local; CI pair at merge); (iv) `CheckPolicy().sha256` = `21c44e10…`; (v) `sha256(repr(syn001_lifted_splits(("A","B","C"))))` = `fc36484e…`; (vi) fixture tree sha = `1303efa7…` and the gate's R-015 comparisons pass; (vii) the whole identity document sha = `b364bb3d…`; (viii) `scripts/t02_identity.py --floats-out` output byte-equal to the baseline recorded in W1.a step 0 (same machine).

New tests go in new files; a shared helper `tests/t05_syn001_shaped.py` builds the **SYN-001-shaped revision**: `benchmarks/syn001/cases/SYN-001-nominal.yaml` with instance ids renamed `feed→U-FEED, mixer→U-MIX, heater→U-HEAT, flash→U-FLASH, splitter→U-SPLIT, vapor_product→U-PROD, purge→U-PURGE` (in `instances`, connection endpoints and specification targets), nothing else changed. It is SYN-001's physics in the general machinery — the reference that lets every W1 seam be tested before any T05 model exists.

| WO | Files | What lands | New tests (must pass) | Inertness |
| --- | --- | --- | --- | --- |
| **W1.a** | `orchestrator/splits.py` (new); `orchestrator/mass.py` (+`residence_time`) | Step 0: record the sha of `t02_identity.py --floats-out` on the unedited tree in `docs/t05-measurements.md`. Then the registry (all five rules) and `residence_time`. | `test_t05_w1a_splits.py`: `lifted_splits(SYN-001 instances) == syn001_lifted_splits(...)` and repr sha `fc36484e…`; §3.3 (a)–(e) on the legacy spec; `residence_time(WIRING, COMPONENTS) == syn001_residence_time(COMPONENTS)`; descriptor field table of §3.1 for a valve, reactor and PH flash built from literal `Wiring`s (ids only; no model class needed). | Additive only; P. |
| **W1.b** | `models/revision_flowsheet.py`, `application/revision_binding.py` (new) | Parse, flowsheet, label, traversal, builder with the six K02 entries. | `test_t05_w1b_revision.py`: the SYN-001-shaped binding's spec equals `Syn001Flowsheet(nominal).spec()` in `variable_ids`, `equation_ids` (order), `parameter_ids`, `parameters`, `variable_kinds`, `row_kinds`, `row_accumulation` — only the label differs; label `FSR1-…`, ≤ 64 characters, unchanged by a pinned-value change (r = 0.5 → 0.7), changed by a `phase_capability` change, a parameter-name change and a swapped mixer-inlet order; traversal: pass 1 tears exactly `("S6",)`, pass 2's streams are **bitwise equal** to `Syn001Flowsheet.traverse(initial_recycle())`'s; one test per refusal of R1–R6 (kind and code). | Additive only; P. |
| **W1.c** | `orchestrator/revision.py` (new); `orchestrator/executor.py`, `orchestrator/tear.py` (guard), `run/session.py` (guard) | `initial_state`, `plan_revision`, the dispatch of §2.3, the typed refusals. | `test_t05_w1c_executor.py`: `initial_state(shaped)` **bitwise equal**, variable by variable, to `Syn001TearProblem(sf).reconstruct(sf.initial_recycle())`; `plan_revision(shaped)` → one `solve_eo` step, schema-valid, region = the five units with rows, `signature_units == ("U-HEAT", "U-FLASH")`; `execute_plan` → `CONVERGED`, every stream within T02 §6.4's allowances of `benchmarks/syn001/reference_values.yaml`'s nominal, `branch_found == [["U-HEAT","LIQUID"],["U-FLASH","TWO_PHASE"]]`; `resolve_mass(residence_time(...), rows=region.row_ids)` resolves (no refusal); a test-double unit with a `molar_flow_squared` row and model id `test.lifter` → `lifted_split_unregistered(test.lifter)`; `converge` step on a revision flowsheet → `UNSUPPORTED_RANK_STRUCTURE`, `tear_path_unsupported(revision_flowsheet)`; `solve_tear`, `run_session` on one → `TypeError` `syn001_only(...)`; an initializer failure — the shaped revision with the feed at 400 K, above the equimolar bubble point (347.44 K), which the K02 mixer refuses as a liquid inlet (R-038) → `INITIALIZATION_FAILED`, an `initializer_rejected` event, message `initializer_failed(U-MIX): …`. | **Highest-risk chunk.** P, with (vii) and (viii) mandatory: both exercise `execute_plan` on every registered SYN-001 plan. |
| **W1.d** | `verify/table.py` (new); `verify/certificate.py`, `verify/checks.py` | `_issue` extraction, `bounds_checks(streams=)`, `verify` guard, `verify_revision`, the table with the K02 entries (incl. tp_flash), splits, declared ports, envelope. | `test_t05_w1d_verifier.py`: the W1.c solve → `VERIFIED`, check ids equal to a literal list pinned in the test; **cross-validation**: at (a) the converged shaped state and (b) its `initial_state` x⁰ (a non-root: many nonzero values), each legacy check value (`run_checks(sf, state)`) equals its general counterpart bitwise — pairs: `material_balance.mixer.<c>`↔`U-MIX.<c>`, `heater.<c>`↔`U-HEAT.<c>`, `flash.<c>`↔`U-FLASH.<c>`, `splitter.<c>`↔`U-SPLIT.<c>`, `ratio.<c>`↔`specification.U-SPLIT.ratio.<c>`, `envelope.<c>`↔`envelope.<c>`, `lifted_split.<c>`↔`U-HEAT.lifted_split.<c>`, `total.S3.V/L`↔`U-HEAT.total.V/L`, `total.S4.N/S5.N`↔`U-FLASH.total.vapor/liquid`, energy `mixer/heater/flash/splitter`↔`U-MIX/U-HEAT/U-FLASH/U-SPLIT` (the splitter pair added 2026-09-25, ruling round Q-R3; it was listed on the legacy side only), `envelope`↔`envelope`, specification `S1.T/S1.P/S1.n.<c>/S3.T/S4.T/S5.T`↔`U-FEED.T/P/n.<c>`, `U-HEAT.T`, `U-FLASH.temperature.vapor/liquid`, `phase_admissibility.S3.*`↔`U-HEAT.S3.*`, `independent_split.S3.*`↔`U-HEAT.S3.*`; `verify_revision` with a different revision document → `declaration_mismatch(revision)`; `verify(revision_flowsheet)` → `VerifierError` `syn001_only(verify)`; recommended (c): the once-through shaped revision with S3 forced all-liquid (K04's trivial root) → `FAILED`, `false_success_detected`, the three legacy values under their general ids. *Added 2026-09-25, ruling round Q-R3:* (d) **coverage** — at both states, every legacy check id is either present with the same id in the general certificate (the generic checks: residual, alias, bounds, `energy_balance.enthalpy.<S>`, derivative witness) or is the legacy side of a listed pair; an unpaired legacy id fails the test, and is reported to the design lane rather than paired silently. | P; the certificates in the fixtures and in the identity document make (vi) and (vii) the proof of the extraction. |

Each chunk is one commit naming `T05 W1.x`; W1.c and W1.d each go to `reviewer` only as part of T05's end review (they touch certificates and the region path, spec §22 W14).

---

## 8. What W11–W13 inherit

- **W11** (case revisions, registry): writes `benchmarks/t05/cases/SYN-001-UL-C{1,2,3,3X}.yaml` exactly per §1.3 and §2.4 (schema-valid; `check_quantity` on every Quantity); adds the six T05 entries of `MODEL_BUILDERS` (each returns the constructed unit and its §1.3 `configuration`); the registry family, cases and `typed_failure_or_failed_certificate` (spec §21); the registry's initializer id is `traversal-G0-v1`. Test: each case binds; C1–C3X are `STRUCTURALLY_CLOSED`; §3.3 (a)–(e) on each.
- **W12** (K04 table, discovery, injections): the six T05 entries of `MODEL_CHECKS` with spec §12.2's ids and formulas in §4.3's order and conventions; A26 (descriptors of §3.1 for the T05 units; the `branch_found` lists of §2.4); A27 per §5; A22 through mini-revisions (feed → unit → sinks) solved by `plan_revision`/`execute_plan`, or started by `solve_region(..., state=<twin state>, initializer_source="user_guess")` where the traversal cannot reach the state (INJ-T2, C3X's second branch), then `verify_revision(..., state=<injected state>)`.
- **W13** (coupled solves): the common path of §2.1 for each case; A17–A21 against `ref.coupled_cases`; `scripts/t05_identity.py` and the `t05` key (§6); W0.6/W0.7 read their numbers off these certificates.
- **No unit model needs a new member.** The general machinery reads only the `UnitModel` protocol, `Port.direction`/`kind`/`multiplicity`, and `UnitEvaluation`'s `duty`, `work`, `extent`, `transferred_duty` (spec F6, landed). The builder needs each T05 constructor to accept the inputs of §1.3's table by meaning.

Register entries the build lane adds with this note (decisions a later session could plausibly undo): **R-045** revision-built flowsheets are solved as one EO region from `traversal-G0-v1`; the tear path stays SYN-001-only (rejected: generalized tear, generic evaluate steps). **R-046** lifted splits by a registry keyed by model id; the verifier by a table keyed by model id reading the revision (rejected: per-unit members; rewriting K04's legacy builders). **R-047** a revision-built flowsheet's label carries `configuration_sha256`; `compiled-problem-structure-v2` is not introduced (rejected: module hashes in the label; structure-v2 now).

---

## 9. Risks, open questions and falsifiers

| # | Question | Needs | Default (in force until revisited) |
| --- | --- | --- | --- |
| Q-A | Does the region Newton converge from `traversal-G0-v1` on C2 and C3 within SYN-001's budgets? | fact (W13) | Expected (C3's tear map has spectral radius 0.527; the start is two passes in). If not: report to the design lane; no extra passes, damping or budget change added by the build lane. |
| Q-B | Do T01's certificates equal K03 §7.2's aliases at `x_final` on C1–C3 (the `solve_plan` comparison of §4.2)? | fact (W0.9) | Expected (pressure copy loops only). A mismatch is a design-lane question; the comparison is not dropped. |
| Q-C | Does C3X's pass 2 fail at U-HX with `temperature_cross(cold_end)`, not an earlier check of the evaluator (domain, admissibility)? | fact (W13) | Expected (the exchanger's order puts both terminal checks last and the pass-2 streams are liquid, in domain). If another code appears, A20 stays failed and the design lane decides. |
| Q-D | Does a builder that instantiates Python classes from a revision count as "assembled from `ProcessRevision` documents" under ADR 0002 D2.7, which would require `compiled-problem-structure-v2`? | Frank's preference (identity policy) | No: the equations are Python row builders, as SYN-001's, and the label carries configuration (R-047). Revisit when manifests themselves assemble equations. |
| Q-E | Are §4.5's four errata right? | design lane (this note decides) | As written; the build lane applies them to spec §12.2 with this commit. |
| Q-F | Is W1.b/W1.c's bitwise equality with the legacy traversal real — does the K02 mixer read a dormant inlet's temperature label (300 K here, 360 K in the legacy)? | fact (W1.b) | Expected equal. If not bitwise, the difference is explained before W1.c lands; the tolerance is not loosened. |
| Q-G | Should revision-built flowsheets get `run_session`, bundles and the CLI in T05? | Frank's preference (scope) | No; T05's evidence uses `execute_plan` and `verify_revision` (T02's identity precedent). K06/T07 generalize the session. |
| Q-H | The traversal's property calls are outside the region's metered budget window. | fact (known) | Accepted: identical to the legacy start. |
| Q-I | C3X in the `t05` identity key although A24 names C1–C3. | preference (low stakes) | Included. |

**What would falsify the design** — each is a stop-and-report, not a patch: W1.b/W1.c bitwise equalities fail (the general traversal is not SYN-001's); any item of protocol P moves in W1.c or W1.d; a cross-validation pair in W1.d differs (a formula's operation order departs from the written one); Q-A fails for C3 (EO from `G(0)` is not enough for the thermally coupled loop, and the tear-path rejection in D2 must be revisited); §3.3 fails for a T05 unit (the registry and the unit's rows disagree, so R-039's one-split invariant is not what the unit authored).

**Out of scope, stated:** dormant PH-type outlets in an EO solve (spec §4.7, W0.8); cross-unit specifications on revision flowsheets; component sets other than `[A, B, C]`; a second provider; generalizing the tear path; revision-built flowsheets through `run_session` or the CLI.
