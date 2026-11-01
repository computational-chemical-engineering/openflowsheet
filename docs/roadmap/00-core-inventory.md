# Roadmap inventory: today's core structures (OpenFlowsheet, as of 2026-11-01)

Read-only reconnaissance. Paths are relative to `/home/frankp/Codes/OpenFlowsheet`. Line numbers
are from the working tree at `main` (`ed5d2a5f`). Excerpts are trimmed; signatures and fields are
verbatim. "Not verified" marks anything I did not open.

---

## 1. Material / stream state and phase labels

### 1a. Stream state (`nTP-v1`)

`src/openflowsheet/thermo/__init__.py:105`
```python
@dataclass(frozen=True)
class StreamState:
    """A material stream in the `nTP-v1` state definition (ADR 0001 D2.1).
    `n` is component molar flows in `components` order, mol/s; `T` is absolute temperature in K;
    `P` is pressure in Pa. Nothing derived is stored: ...
    """
    n: tuple[float, ...]
    temperature: float
    pressure: float
    @property
    def total_flow(self) -> float: ...
    @property
    def is_dormant(self) -> bool:   # exact 0.0 after signed-zero normalization (ADR 0001 D3.1)
```
Fixes: per-stream state is `n` (one molar flow per component, in provider component order), `T`
(K), `P` (Pa). Nothing derived is stored. A dormant stream (`total_flow == 0.0`, exact) has
undefined composition.

Solution-vector variables per material stream (`src/openflowsheet/models/__init__.py`):
- `flow_id(stream, c)` = `"<S>.n.<C>"` (line 101), one per component
- `temperature_id(stream)` = `"<S>.T"` (106); `pressure_id(stream)` = `"<S>.P"` (110)
- `stream_variables(stream, components)` (559): flows first in component order, then T, then P
- `stream_variable_kinds` (552): kinds `molar_flow`, `temperature`, `pressure`
- `duty_id(unit)` = `"<U>.Q"` (114), W, positive into the unit
- Saturated pure-fluid streams add `"<S>.sat.V"` and `"<S>.sat.L"` (`models/thermal/state.py:40-48`;
  the carried split, mol/s). In the causal traversal they travel as
  `SaturatedStreamState(StreamState)` (`models/thermal/state.py:28`) with
  `vapor_fraction` in [0, 1] (`__post_init__` checks it).

### 1b. Phase labels (four vocabularies; each is a different Literal)

| Where | Definition | Members |
|---|---|---|
| `thermo/__init__.py:58` | `Phase = Literal["LIQUID", "VAPOR"]` | what `evaluate_phase` may be asked for; `ZERO_FLOW` is excluded |
| `compiled.py:27` | `PhaseSignature = Literal["LIQUID", "VAPOR", "TWO_PHASE", "ZERO_FLOW"]` | the active-set signature of a state; `ZERO_FLOW` is a stream property |
| `models/__init__.py:81` | `PhaseCapability = Literal["liquid", "vapor", "vapor_liquid"]` | manifest and port vocabulary; comment says it is deliberately not `thermo.Phase` |
| `orchestrator/region.py:161` | `Regime = Literal["TWO_PHASE", "LIQUID", "VAPOR", "ZERO_FLOW"]` | region regimes in the EO solve |
| `models/thermal/kernel.py:66` | `Regime = Literal["LIQUID", "VAPOR", "SATURATED"]` | pure-fluid declared regimes (ADR 0051 D1) |

Also: `orchestrator/trace.py:99` `AttemptSignature = tuple[tuple[str, PhaseSignature], ...]`.

`phase_capability` on a port or connection: `models/__init__.py:240` (`Port.phase_capabilities`)
and `schemas/process-revision.schema.json` `connections[].phase_capability` enum
`["liquid","vapor","vapor_liquid"]`. Declared regimes for pure-fluid streams are ADR 0051 D1
(`docs/adr/0051-s11-thermal-units-on-the-new-bases.md`). `application/thermal_binding.py:9-12`
states the rule: liquid and vapor are single-phase, `vapor_liquid` is SATURATED. A declared
mismatch is refused `phase_regime_mismatch(<S>)` (`models/thermal/__init__.py` docstring).

### 1c. FlashResult (`thermo/__init__.py:183`)

```python
@dataclass(frozen=True)
class FlashResult:
    status: PropertyStatus
    phase_signature: PhaseSignature | None
    vapor_fraction: float | None      # molar basis; None if undefined (dormant or status != ok)
    vapor: StreamState | None
    liquid: StreamState | None
    k_values: Mapping[str, float] = field(default_factory=dict)
    iterations: int = 0
    achieved_accuracy: str = "exact-double"
    provider_id: str = ""
    reference_convention: str = ""
    message: str = ""
```
Fixes: two outlet slots (`vapor`, `liquid`). A flash result holds at most two phase outlets. No
third-phase or liquid–liquid slot exists. `FlashRequest` (line 174) has `specification: str = "TP"`
only, and `FlashRequest.derivatives`. Dormant feed gives `ZERO_FLOW` (valid result, not failure).

`PropertyStatus` (line 54): `Literal["ok", "out_of_domain", "unsupported", "not_converged", "error"]`.
There is no "extrapolated" value.

---

## 2. Components: set, binding, identity, records

### 2a. Revision-level component set

`schemas/process-revision.schema.json` `properties.component_set`: object, required
`record_source` (string, path of the ComponentRecords file) and `components` (array, minItems 1,
uniqueItems, string ids). Array order matters (the binder maps it onto the provider order).

`src/openflowsheet/models/revision_flowsheet.py`:
- `:93` `_COMPONENTS = ("A", "B", "C")`, the SYN-001 set, which the verifier assumes.
- `:103` `@dataclass(frozen=True) class ComponentBasis` with fields `provider_id: str`,
  `components: tuple[str, ...]` (the provider's order), `molecular_weights: Mapping[str, float]`
  (kg/mol by id), `record_source: str` (keyword-only). It is "the component set, molar masses and
  property provider a revision binds on".
- `:212` `component_basis(document) -> ComponentBasis`: selects from `record_source`. Any value not
  in the registry (absent included) selects SYN-001.
- `:230` `selectable_bases() -> tuple[ComponentBasis, ...]`: SYN-001, C1, IAPWS-95, Wilson, then one
  CoolProp basis per row of the S07 table (docstring says 127 in all).
- `:411` `canonical_components(declared, basis=SYN001_BASIS) -> tuple[str, ...]`: maps a declared
  set onto the provider's component order.

Record-source paths (`revision_flowsheet.py`, constants before `ComponentBasis`):
`SYN001_RECORDS = "benchmarks/syn001/components.yaml"`;
`IAPWS95_RECORDS = "benchmarks/s05/components.yaml"`;
`WILSON_RECORDS = "benchmarks/s10/records.yaml"`;
`COOLPROP_RECORDS = "benchmarks/s07/components.yaml"`.
C1 uses `pr_c1.RECORDS_PATH = "benchmarks/m01/components.yaml"` (`thermo/pr_c1.py:67`).
`pr_lib.RECORDS_PATH = "benchmarks/l01/components.yaml"` (`thermo/pr_lib.py:75`) is **not** a
registered record source and is not in `selectable_bases()`. It is not in `FRESH_PROVIDERS`
(`verify/certificate.py:618`). ADR 0043 describes it as a separate vapour-only PR library route.

### 2b. Component identity fields

Schema `schemas/component-record.schema.json`: properties `id`, `name`, `synthetic`, `identifiers`
(optional: `cas`, `inchi`, `inchikey`, `formula`), `molecular_weight` (Quantity, kind
`molar_mass`, kg/mol), `elemental_composition` (null for pseudo-components), `elemental_verification`
(`NOT_APPLICABLE` is mandatory when there is no formula), `parameters`, `rights`. Required:
`id, name, molecular_weight, elemental_composition, parameters, rights`.

Example, `benchmarks/l01/components.yaml:20-35` (H2): `id: H2`, `name: hydrogen`,
`synthetic: false`, `identifiers: {cas: "1333-74-0", inchi: ..., inchikey: ..., formula: "H2"}`,
`molecular_weight: {value: 0.00201588, unit: kg/mol, kind: molar_mass, ...}`.

SYN-001 records (`benchmarks/syn001/components.yaml`, lines 1-40): A, B, C are artificial, with
`synthetic: true` and `elemental_verification: NOT_APPLICABLE`.

Provider component tuples (fixed per provider; `describe().components`):
- `syn001`: `("A", "B", "C")` (`thermo/syn001.py:51`)
- `pr-c1-v1`: `("H2", "N2", "NH3", "Ar", "CH4")` (`thermo/pr_c1.py:70`)
- `pr-lib-v1`: nine records, `COMPONENTS` at `thermo/pr_lib.py:78`
- `iapws95-v1`: water only (`benchmarks/s05`)
- `coolprop-heos-v1`: exactly one fluid per basis (`verify/certificate.py` `fresh_provider` raises
  `basis_mismatch` when `len(basis.components) != 1`)
- `wilson-ig-v2`: from `benchmarks/s10/records.yaml`

Record dataclasses as the provider reads them: `C1Component` (`thermo/pr_c1.py:89`) and
`LibraryComponent` (`thermo/pr_lib.py:112`). Both carry `id, name, molar_mass, critical_temperature,
critical_pressure, acentric_factor, formation_enthalpy, cp_coefficients (5), cp_temperature_range,
elemental_composition`. There is no CAS or formula field on the dataclass itself. Those live in the
YAML `identifiers` block (L01 records; SYN-001 records have none).

Schema-level component record loader: `thermo/pr_c1.py:178` `load_records() -> C1Records`,
`thermo/pr_lib.py:200` `load_records() -> LibraryRecords`.

---

## 3. Property providers

### 3a. Protocol (frozen)

`src/openflowsheet/thermo/__init__.py:210`
```python
@runtime_checkable
class PropertyProvider(Protocol):
    def describe(self) -> PropertyCapabilities: ...
    def evaluate_phase(self, request: PropertyRequest, context: EvaluationContext) -> PropertyResult: ...
    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult: ...
```
Frozen by `docs/interfaces-frozen.md` §1 (change rule: ADR). The docstring says "no mutable global
provider" (plan §2.1); a provider is an object handed to a unit.

Context: `compiled.py:39` `EvaluationContext(model_version, constants_sha256, phase_signature=None,
accuracy_policy="exact-double", workspace={})`. It carries no provider reference and no time (ADR 0008 D1).

### 3b. Request and result types

- `PropertyCapabilities` (`thermo/__init__.py:62`), all fields required: `provider_id`,
  `implementation_sha256`, `data_sha256`, `reference_convention`, `state_definition` (`nTP-v1`),
  `components` (ordered; part of identity), `phases`, `properties`, `flashes`,
  `derivative_order: Mapping[str,int]` (per named input), `domain: Mapping[str, (lo,hi)]`,
  `uncertainty`, `data_provenance`, `thread_safety`, `numerical_limitations`.
- `PropertyRequest` (`:133`): `state: StreamState`, `phase: Phase`, `properties: tuple[str,...]`,
  `derivatives: tuple[str,...] = ()`. The phase is given, not inferred.
- `PropertyResult` (`:150`): `status`, `phase_signature`, `values: Mapping[str,float]`,
  `derivatives: Mapping[str, Mapping[str,float]]` (absent key means "no derivative", not zero),
  `achieved_accuracy="exact-double"`, `provider_id`, `reference_convention`, `message`.

### 3c. Registered providers (class, PROVIDER_ID, declared surface)

| Provider | Class (file:line) | PROVIDER_ID | phases | properties | flashes | ref. convention |
|---|---|---|---|---|---|---|
| SYN-001 | `Syn001Provider` `thermo/syn001.py:74` | `"syn001"` (:63) | LIQUID, VAPOR | `h`, `lnK` | TP | `SYN-001-ref-v1` |
| PR C1 | `PrC1Provider` `thermo/pr_c1.py:711` | `"pr-c1-v1"` (:199) | LIQUID, VAPOR | `h`, `Z`, `v`, `lnphi_<c>` | TP | `PR-C1-ref-v1` (:73) |
| PR library (vapour) | `PrLibProvider` `thermo/pr_lib.py:686` | `"pr-lib-v1"` (:217) | VAPOR | `h`, `Z`, `v`, `lnphi_<c>` | none (`()`) | `PR-C1-ref-v1` (:92) |
| IAPWS-95 | `Iapws95Provider` `thermo/iapws95.py:806` | `"iapws95-v1"` (:74) | LIQUID, VAPOR | `h,s,v,Z,cp,lnphi_H2O,Psat,Tsat` | TP | `IAPWS95-ref-v1` (:75) |
| CoolProp HEOS | `CoolPropHeosProvider` `thermo/coolprop_heos.py:390` | `"coolprop-heos-v1"` (:76) | LIQUID, VAPOR | phase props + `Psat,Tsat` | TP | per fluid |
| Wilson γ–φ v1 | `WilsonIdealGasProvider` `thermo/wilson_ig.py:433` | `"wilson-ig-v1"` (:76) | LIQUID, VAPOR | `h`, `lnphi_<c>` (`self._properties`, :446) | TP | per module |
| Wilson γ–φ v2 | `WilsonIdealGasProviderV2` `thermo/wilson_ig_v2.py:108` | `"wilson-ig-v2"` (:66) | as v1 | v1 + `s` | TP | wraps v1 |

Derivative inputs: SYN-001 `{T:1, P:1}`; C1 and PR-lib `T, P, n_<c>` (`DERIVATIVE_INPUTS`,
`pr_c1.py:227`, `pr_lib.py:244`); IAPWS-95 `T, P, n_H2O` (`iapws95.py:131`).
Domains: `domain={"T": ..., "P": ...}` on each provider's `describe()` (for example `syn001.py:96`,
`pr_c1.py:730`, `iapws95.py:826`, `coolprop_heos.py:932` using the per-fluid table).
Wilson phases and flash: `wilson_ig.py:462-464` (`phases=("LIQUID","VAPOR")`, `flashes=("TP",)`).
Not verified: `thermo/stability.py` (47 lines) and `thermo/wilson_premises.py` in detail.

Quantities a request may name: the strings in `properties` above and `derivatives` as named
inputs. Asking for an undeclared input is `unsupported` (docstring, `thermo/__init__.py:133-140`).

### 3d. Registration and selection

- No global registry of providers in the thermo layer. A provider object is constructed by whoever
  needs it.
- Revision path: `component_basis(document)` (`revision_flowsheet.py:212`) returns a `ComponentBasis`
  whose `provider_id` selects the provider. `MODEL_BASES` in
  `application/revision_binding.py:1613` lists, for each model id, which provider ids it binds on.
- Verifier path: `fresh_provider(basis)` at `verify/certificate.py:645` constructs a fresh provider
  by id, from its own table. `FRESH_PROVIDERS` (`:618`) is `syn001, pr-c1-v1, iapws95-v1,
  wilson-ig-v2, coolprop-heos-v1`. It checks `describe()` matches the basis (else `basis_mismatch`),
  and an unknown id is `provider_unknown(<id>)`.
- Bases constants: `application/revision_binding.py:1587-1589`: `S11_BASES = (_IAPWS95, _COOLPROP, _WILSON)`.

### 3e. Cache keys

`src/openflowsheet/thermo/cache.py`
- `ExactPropertyCache` (`:123`). It is itself a `PropertyProvider` and wraps one.
- `_identity(context)` (`:173-190`) returns the members that every key contains:
  `provider_id`, `implementation_sha256`, `data_sha256`, `components` (ordered), `reference_convention`,
  `state_definition`, `accuracy_policy`, `phase_signature`.
- `_property_key` (`:193`) adds `kind="evaluate_phase"`, the state through `_state_document` (`:116`,
  exact canonical floats, no quantization), `phase`, `properties`, `derivatives`. `_flash_key` (`:205`)
  is the flash analogue. Keys are `document_sha256(...)` (`openflowsheet.canonical`).
- `_satisfies(achieved, requested)` (`:254`): a cache entry cannot serve a tighter request than it
  achieved.
- `WarmStartCache` (`:270`) is approximate, and returns only `FlashGuess` (`:96`), which has no status
  or outlets. `CacheCounters` at `:63`.

---

## 4. Unit models

### 4a. Unit-model interface (declaration and causal evaluator)

`src/openflowsheet/models/__init__.py:369`
```python
class UnitModel(Protocol):
    """A SYN-001 unit: a declaration, a set of residual rows, and a causal evaluator."""
    @property
    def model_id(self) -> str: ...        # e.g. "syn001.tp_heater"
    @property
    def unit_id(self) -> str: ...         # e.g. "U-HEAT"; prefixes rows and variables
    def ports(self) -> tuple[Port, ...]: ...
    def declared_equations(self) -> tuple[DeclaredEquation, ...]: ...
    def manifest(self) -> Mapping[str, Any]: ...       # ModelManifest document
    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution: ...
    def evaluate(self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext) -> UnitEvaluation: ...
```
- `contribute` returns the rows and owned variables a unit adds to a `ProblemSpec` (`Contribution`, `:296`).
- `evaluate` computes outlets causally, keyed by port name (`UnitEvaluation`, `:319`).

**There is no `residual()` or `jacobian()` method on a unit.** Residual rows are `EquationSpec`
objects whose `build` callable receives an `Algebra` (`compile/spec.py:112`). The Jacobian is
produced by the backend from the symbolic graph (ADR 0003 D4.1). Opaque property evaluators implement
`PropertyBlock` (`compile/spec.py:67`): `block_id`, `input_ids`, `output_ids`, `jacobian_pattern()`
(declared structural nonzeros), `values(inputs)`, `jacobian(inputs)`. An out-of-domain block raises
`DomainError` (`compile/spec.py:102`).

Port (`models/__init__.py:240`):
```python
@dataclass(frozen=True)
class Port:
    name: str
    kind: PortKind            # "material" | "energy" | "signal"
    direction: PortDirection  # "inlet" | "outlet"
    multiplicity: int | Literal["many"]
    component_mapping: Literal["revision_component_set"] | tuple[str, ...] | None
    state_definition: Literal["nTP-v1"] | None
    phase_capabilities: tuple[PhaseCapability, ...]
```

Manifest parts (`models/__init__.py`): `DerivativeDeclaration` (`:54`: `output`, `with_respect_to`,
`method` in analytic|ad|implicit|finite_difference|unavailable, `regime`, `notes`); `Initialization`
(`:77`: `strategy` in none|registered_initializer|local_initializer|upstream_propagation,
`registered_initializer`); `Validity` (`:93`: `components`, `phases`, `limitations`, `temperature_k`,
`pressure_pa`). `ManifestStatus` (`:406`) is `declared | implemented | tested | reviewed | released`.
`manifest_document(...)` at `:482`. `UNCLAIMABLE_STATUS = {reviewed, released}` (`:51`): manifests
written by agents cannot claim these.

Manifest schema: `schemas/model-manifest.schema.json`. Required: `id, version, status, ports,
mathematics, derivatives, initialization, validity, implementation_artifact, execution_requirements`.

Row/variable id helpers (`models/__init__.py`): `flow_id` `:101`, `temperature_id` `:106`,
`pressure_id` `:110`, `duty_id` `:114`, `row_id(unit, equation, *suffix)` `:119`, `origin` `:129`.

### 4b. Registration

- `MODEL_SIGNATURES` `application/revision_binding.py:1579`: parameters and ports per model id.
- `MODEL_BUILDERS` `application/revision_binding.py:1642`: model id to builder. Comment says it covers
  the six K02 models, six T05, T08's kinetic CSTR, S11's column, M02's C1 units, the C1 reactors, and
  the seven `thermal.*` models through `_thermal_builder`.
- `MODEL_BASES` `application/revision_binding.py:1613`: model id to frozenset of provider ids (see table below).
- `_NAMESAKES` `:1674`: C1 and SYN-001 counterparts for routing hints.
- A refusal-hint table near `application/revision_binding.py:1819` names ids that exist but are not
  revision-bindable, for example `"syn001.cascade"`.
- The builder table lives in the application layer, not in `models/`. `RevisionFlowsheet` gets
  builders from it (`models/revision_flowsheet.py:268` mentions the S11 registration).

### 4c. Unit types that exist (model id, module) and bases each binds on

Basis key: `S` = `syn001`; `C` = `pr-c1-v1`; `I` = `iapws95-v1`; `K` = `coolprop-heos-v1`;
`W` = `wilson-ig-v2`.

| Model id | Module | Bases (`MODEL_BASES`) |
|---|---|---|
| `syn001.feed_source` | `models/syn001/feed.py:59` | S + I, K, W (routing model) |
| `syn001.product_sink` | `models/syn001/sink.py:47` | S + I, K, W (routing) |
| `syn001.stream_splitter` | `models/syn001/splitter.py:63` | S + I, K, W (routing) |
| `syn001.adiabatic_mixer` | `models/syn001/mixer.py:112` | S + W (γ–φ face) |
| `syn001.tp_heater` | `models/syn001/heater.py:89` | S + W (γ–φ face) |
| `syn001.tp_flash` | `models/syn001/flash.py:83` | S + W (γ–φ face) |
| `syn001.ph_flash` | `models/syn001/ph_flash.py:96` | S + W (γ–φ face) |
| `syn001.valve` | `models/syn001/valve.py:70` | S + W (γ–φ face) |
| `syn001.liquid_pump` | `models/syn001/pump.py:74` | S |
| `syn001.conversion_reactor` | `models/syn001/conversion_reactor.py:104` | S |
| `syn001.component_separator` | `models/syn001/component_separator.py:83` | S |
| `syn001.heat_exchanger` | `models/syn001/heat_exchanger.py:92` | S |
| `syn001.kinetic_cstr` | `models/syn001/kinetic_cstr.py:93` | S |
| `syn001.column` | `models/syn001/column.py:130` | S + W |
| `syn001.cascade` | `models/syn001/cascade.py:87` | not revision-bindable (refused, `revision_binding.py:1819`) |
| `c1.feed_source` / `c1.product_sink` / `c1.stream_splitter` | `models/c1/feed.py:53`, `sink.py:34`, `splitter.py:53` | C (listed in `_C1_SIGNATURES`; they are C1 namesakes of the SYN-001 routing units, not in `ROUTING_MODELS`) |
| `c1.adiabatic_mixer` | `models/c1/mixer.py:74` | C |
| `c1.tp_heater` | `models/c1/heater.py:72` | C |
| `c1.tp_flash` | `models/c1/flash.py:95` | C |
| `c1.reactor` | `models/c1/reactor.py:98` | C |
| `c1.reactor_standin` | `models/c1/reactor_standin.py:69` | C (registered to `_c1_reactor`) |
| `c1.reactor_surrogate` | `MODEL_ID` at `studies/surrogate/study.py:87` and `verify/surrogate.py:39` (two modules define it) | C (builder `_c1_reactor_surrogate`, `revision_binding.py:1667`) |
| `thermal.heater`, `thermal.valve`, `thermal.mixer`, `thermal.flash`, `thermal.pump` | `models/thermal/{heater,valve,mixer,flash}.py` (MODEL_ID lines 63, 46, 47, 53); pump via `machines.py` (`MACHINE_MODEL_IDS` :92) | I, K |
| `thermal.compressor`, `thermal.turbine` | `models/thermal/machines.py` (`MACHINE_MODEL_IDS`) | I, K, W |

Notes:
- The routing set is `ROUTING_MODELS` at `revision_binding.py:1591`: feed, sink, splitter.
- The γ–φ set is `_GAMMA_PHI_MODELS` at `revision_binding.py:1593`: tp_heater, tp_flash, ph_flash,
  valve, adiabatic_mixer. These also bind on Wilson.
- `_PURE_FLUID_BASES = frozenset({_IAPWS95, _COOLPROP})` (`:1602`). `_WILSON_MACHINES` (`:1603`) are
  compressor and turbine.
- `S11_BASES` (`:1589`) is `(iapws95, coolprop, wilson)`.
- Reactor-related `c1.reactor` model ids are in the C1 signature table (`revision_binding.py:627`).
- The `thermal.*` family is documented in `models/thermal/__init__.py:1-17`: kernel, blocks, rows,
  state, one module per unit.

---

## 5. Problem compilation and solving

### 5a. Compiled-problem backend (ADR 0003, Accepted 2026-09-17)

- Protocol `CompiledProblem` (`compiled.py:163`): `metadata: CompiledProblemMetadata`;
  `residual(x, context) -> EvaluationResult`; `jacobian(x, context) -> JacobianResult` (CSC);
  `reconstruct(x, context) -> ProcessState`.
- `CompiledProblemMetadata` (`compiled.py:75`): `model_version`, `backend`, `backend_version`,
  `variable_ids`, `equation_ids`, `parameter_ids`, `column_scales`, `row_scales`, `row_accumulation`
  (`algebraic | zero_holdup_balance | holdup_balance | absent`), `capabilities`, `constants_sha256`.
- `Capabilities` (`compiled.py:61`): `jacobian` (`exact_sparse_csc | absent`), `jvp`, `vjp`, `hessian`
  (`exact | absent`).
- `EvaluationResult` (`compiled.py:105`): `status` (`ok | invalid_trial_state | unsupported | error`),
  `values`, `equation_ids`, `phase_signature`, `model_version`, `constants_sha256`, `state_sha256`,
  `counters`, `accuracy`, `message`.
- `JacobianResult` (`compiled.py:123`): `row_ids`, `col_ids`, CSC `indptr`/`indices`/`data`,
  `pattern_provenance` (`backend-declared | thresholded`), `source_map`.
- `ProcessState` (`compiled.py:155`): `variables: Mapping[str,float]`, `phase_signature`.
- Implementation: `compile/casadi_backend.py`. `compile_problem(spec)` at `:639`,
  `CasadiCompiledProblem` at `:303` (CasADi `Callback` per opaque block, `_JacobianCallback` `:151`,
  `_BlockCallback` `:191`). `compile_parametric_twin` at `:867`.
- Backend choice: CasADi 3.8.0 pinned. Pyomo/PyNumero/ASL was rejected on installability (ADR 0003
  D1.4). The harness is retained as evidence. Linear solve is SciPy SuperLU with explicit options
  (ADR 0003 D4.2, ADR 0004).
- `ProblemSpec` (`compile/spec.py:127`): `label`, `variable_ids`, `equations: tuple[EquationSpec]`,
  `parameter_ids`, `parameters`, `blocks`, `block_inputs`, `column_scales`, `row_scales`, plus
  physical kinds for scaling. It holds no backend objects.

### 5b. Equation-oriented vs sequential: what the code does

- The flowsheet is solved as an `ExecutionPlan` (`orchestrator/execution.py:149`), built by
  `build_execution_plan` (`:597`). Steps are `evaluate(unit)`, `converge(loop)`, `solve_eo(region)`
  (module docstring, `execution.py:1-20`). Order is the condensation order of the process graph.
- `execute_plan` (`orchestrator/executor.py:215`) runs the steps. `StepResult` `:107`, `PlanResult` `:134`.
- Causal (sequential) traversal: `RevisionFlowsheet.traverse` (`models/revision_flowsheet.py`) runs units
  in declaration order, tearing a stream only where the graph deadlocks (module docstring, lines 1-17).
- Each EO region is solved as one compiled problem: `solve_region(...)` at `orchestrator/region.py:1763`.
  Its `Regime` is at `region.py:161`.
- Attempts: `solve_with_attempts(...)` at `orchestrator/attempts.py:223`. `AttemptCore`
  `Literal["newton","anderson","ptc","homotopy"]` at `:86`. `AttemptContext` `:101`. `SolveResult` `:187`.
- The per-attempt Newton is `solve_newton(problem, x0, policy, *, trace, ...)` at `numerics/newton.py:248`.
  It is damped Newton with Armijo line search, bound-aware steps (`_bound_aware_alpha` `:768`), and chord
  steps (`_chord` `:731`). `Problem` `:213`, `NewtonResult` `:172`.
- PTC: `numerics/ptc.py` (759 lines). Experimental in v0.1 per ADR 0010 D5.
- Anderson: `numerics/anderson.py:175` `solve_recycle(...)`; `RecycleResult` `:103`. Called from
  `orchestrator/attempts.py:304` and `orchestrator/merge.py:130`.

### 5c. Tears, recycles and the initializer

- Tear: `orchestrator/tear.py`: `Syn001TearProblem` `:130`, `build_plan` `:493`, `solve_tear` `:540`.
  Candidate tears come from `graph/tear.py` (404 lines); `iterated_tear_set` in `execution.py:243`.
- Initializer: `SolvePolicy.initializer_chain` (`orchestrator/trace.py:659` class `SolvePolicy`).
  Compatible warm starts are an opt-in source id `WARM_START_SOURCE = "compatible_warm_start"`
  (`orchestrator/warm_start.py:48`). The opt-in chain is `("compatible_warm_start", "traversal-G0-v1")`
  (`application/policies.py:13`). It is never a route default.
- Per-model local initializers: `INITIALIZER_ID` in `models/syn001/column.py:136`
  (`"s02-profile-cmo-v1"`) and `models/syn001/cascade.py:93` (`"s01-kremser-cmo-v1"`).

### 5d. Globalization and homotopy (ADR 0010)

- `SolvePolicy.globalization` (ADR 0010 D1): `eo_core` in `newton | ptc`; `eo_recovery` in
  `homotopy | none`; `eo_recovery_max_count = 1`; `homotopy` = `specification_continuation` with
  `delta_lambda_initial`, `delta_lambda_min`, `growth`, `shrink`, `corrector_max_iterations`,
  `max_lambda_trials`; `ptc` block (experimental).
- Homotopy: `orchestrator/homotopy.py:61` `Continuation`, `:222` `continue_specification(...)`.
  H(x, λ) = F(x; p(λ)), with p(λ) = p* + (1−λ)(p⁰ − p*) on the specified-row parameters (ADR 0010 D2).
  λ < 1 is never target-verified.
- Recovery edge 3: `orchestrator/recovery.py:68` `eo_recovery_due(outcome, budget, *, attempts)`.
  Fires at most once per region step per solve (ADR 0010 D3, amended by ADR 0044).
- Phase-attempt contract: ADR 0005; code `orchestrator/phase_contract.py` (527 lines), `orchestrator/attempts.py`.

### 5e. Solve outcomes (`orchestrator/trace.py:28`, `SolveOutcome` Literal)

`CONVERGED, INITIALIZATION_FAILED, SCALE_UNAVAILABLE, SPECIFICATION_CONFLICT,
UNSUPPORTED_RANK_STRUCTURE, PHASE_UPDATE_REQUIRED, ACTIVE_SET_CYCLING, ATTEMPTS_EXHAUSTED,
BUDGET_EXHAUSTED, STAGNATION, LINE_SEARCH_FAILED, BOUND_BLOCKED, LINEAR_SOLVE_FAILED,
INNER_SOLVE_INCONSISTENT, EVALUATION_ERROR, RECYCLE_STAGNATION, CAPABILITY_UNAVAILABLE,
CHECKPOINT_INCOMPATIBLE`, plus homotopy and PTC terminal values added by ADR 0010 D7.2.

### 5f. Verifier and certificate

- `verify(flowsheet, result, *, policy, state) -> SolutionCertificate` at `verify/certificate.py:486`.
  A solve that is not `CONVERGED` gets no certificate (docstring).
- `verify_bound` `:534`; `verify_revision(...)` `:681` (the revision path); `grade(checks, *, policy,
  regularity_status, regularity_reason)` `:257`.
- `SolutionCertificate` dataclass `:326`: `certificate_id`, `model_version`, `constants_sha256`,
  `policy_id`, `plan_id`, `target_state_sha256`, `check_policy_id`, `check_policy_sha256`,
  `verification_status: VerificationStatus`, `false_success_detected`, `checks: tuple[CheckResult]`,
  `regularity`, `solution_error_bound_scaled`, `phase_branch`, `branch_provenance`, `transformations`,
  `derivative_provenance`.
- Verdict literal `VerificationStatus = Literal["VERIFIED","RELAXED","UNVERIFIED","FAILED"]`
  (`verify/__init__.py:41`). Decision logic at `verify/certificate.py:~290-305`, in this order:
  `FAILED` if any check failed; `UNVERIFIED` if evidence missing, rank limitation, or derivative
  limitation; `RELAXED` if the check policy is not a registered one; otherwise `VERIFIED`.
- `CheckOutcome = Literal["pass","fail","unsupported","not_applicable"]` (`verify/__init__.py:39`).
- `RegularityStatus = Literal["NO_RANK_LOSS_DETECTED","RANK_DEFICIENT","ILL_CONDITIONED","INCONCLUSIVE"]`
  (`verify/__init__.py:42`).
- `CheckResult` (`verify/__init__.py:108`): value, tolerance, reference, independence.
- Residual tolerances and the solution-error bound: certificate certifies residual accuracy, not
  solution accuracy (`verify/__init__.py` comment at ~line 50).
- The policy record: `SolvePolicy` schema `schemas/solve-policy.schema.json`; its required keys
  include `residual_tolerances, scales, merit, linear_solver, initializer_chain, cycle_rule,
  phase_contract, recycle, globalization`.
- Dependent rules: ADR 0007 (certificate policy), ADR 0009 (execution plan and recycle trace).

### 5g. Validation status (revision readiness)

`application/validation.py:36`: `ValidationStatus = Literal["DRAFT","READY_FOR_SIMULATION",
"READY_FOR_OPTIMIZATION","INVALID"]`. `Task = Literal["simulation","optimization"]` (`:35`).
`admission.py:144` refuses a solve unless `READY_FOR_SIMULATION`.

---

## 6. Flowsheet / revision document

### 6a. Canonical schema

`schemas/process-revision.schema.json` (title `ProcessRevision`). Top-level properties:
`schema_version, revision_id, parent_revision, content_hash, title, description, component_set,
instances, connections, specifications, provenance`.
Required: `schema_version, revision_id, parent_revision, component_set, instances, connections,
specifications, provenance`.

- `component_set`: `{record_source, components[]}` (see 2a).
- `instances[]`: `id, model, semantic_role, parameters, policy`. `semantic_role` enum:
  `feed, product_sink, mixer, heater, flash, splitter, reactor, separator, valve, pump,
  heat_exchanger, compressor, turbine, other`.
- `connections[]`: `id, kind, from, to, state_definition, component_mapping, phase_capability,
  initialization_hint, notes`. Required: `id, kind, from, to, state_definition, component_mapping`.
  `kind` enum `material | energy | signal`. `phase_capability` enum `liquid | vapor | vapor_liquid`.
  `from`/`to` use `$defs/endpoint`.
- `specifications[]` (`schemas/specification.schema.json`): `id, target, kind, unit, value, bounds,
  tolerance, role, provenance, notes`. Required: `id, target, kind, unit, tolerance, role, provenance`.
  `role` enum `fixed | free | decision`.

Parser: `models/revision_flowsheet.py:383` `parse_revision(document, instance_targets=None) -> RevisionView`.
Rules R1–R6 (module docstring 1-17; `_read` at `:458`). It refuses with typed `RevisionError`
(`:309`); there are no defaults (the module docstring cites "D5"). `RevisionView` `:370`, `InstanceView` `:325`,
`InputMapping` `:351`. Pins: `pin_specifications` `:395`.
Construction: `RevisionFlowsheet` at `:906`. Builder table is in `application/revision_binding.py`.
Identity: `configuration_sha256(view, configurations)` at `:858` (revision minus pinned values).

Revision-level content hash: `application/revisions.py:24`
`CONTENT_HASH_EXCLUDED = {content_hash, revision_id, parent_revision, title, description, provenance}`;
`content_hash(document)` at `:51`.

### 6b. Edit operations

- `schemas/change-set.schema.json` (`ChangeSet`): `edits, expected_revision, idempotency_key,
  new_revision_id, restore_from, task, author`.
- `$defs/edit`: `{operation: "set"|"remove"|"append", path: [string | integer>=0] (minItems 1), value}`.
  `value` is required for `set` and `append` and absent for `remove`.
- Python: `EditOperation = Literal["set","remove","append"]` (`application/types.py:111`);
  `Edit` dataclass `:308`; `Change` `:359` (edits, new_revision_id, restore_from, task, author).
- Application: `apply_edits(base, edits)` `application/transactions.py:96`; `_apply` `:114`;
  `semantic_diff` `:168`; `element_diff` `:237`.
- Operations: `LocalApplication.commit_change` `application/local.py:488`,
  `preview_change` `:1144`, `diff_revisions` `:1258`. `TransactionResult` `application/types.py:544`.

### 6c. Frozen schema list (plan §2.2; `docs/interfaces-frozen.md` §2)

| Package | Schemas (verbatim from the frozen table) |
|---|---|
| P01 | ProcessRevision, Quantity, ComponentRecord, ModelManifest, Specification, ValidationReport |
| P02/K01 | CompiledProblem metadata, EvaluationResult, Jacobian metadata, PropertyCapabilities |
| K03 | SolvePolicy, SolvePlan, SolveEvent, AttemptContext, Checkpoint metadata (delivered 2026-09-21) |
| K04/K05 | SolutionCertificate, FailureBundle, RunManifest, replay artifact manifest |
| K06/T07 | ChangeSet, Job, job events, authorization capability references |
| M01–M04 | ExperimentRequest/Result, ModelEvidence, Study, SurrogateManifest, OptimizationReport |

Schemas are JSON Schema draft 2020-12 under `schemas/`, with round-trip fixtures under `tests/fixtures/schemas/`.
A schema changes only with a migration (blueprint §4.4). Changes to the freeze need a design-lane ADR.

---

## 7. Frozen interfaces (`docs/implementation-plan.md` §2.1, verbatim)

Header of the section: "These are proposed signatures to make the first slice concrete, not a
demand for an extensive framework." Frozen copy: `docs/interfaces-frozen.md` §1 ("Frozen by: Fable
5.1 at the close of P01, 2026-09-06").

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
Also verbatim in §2.1: dense NumPy state vectors; sparse Jacobians have documented CSC ordering; row and
column IDs and source maps declared; `EvaluationResult` carries status, active-set signature,
state/model hash, accuracy, counters; no mutable global property provider; `EvaluationContext` pins
model/data versions, phase signature, accuracy policy and workspace; optional JVP/VJP/Hessian are
negotiated; a missing exact Hessian is never replaced with zeros.

Change rule (interfaces-frozen.md:3): any widening, narrowing, renaming or re-typing needs a
design-lane ADR. The code's `Application` Protocol is at `application/contract.py:66` with the
docstring "Frozen, `docs/interfaces-frozen.md` §1 — verbatim (ADR 0019 D1)".

---

## 8. Application contract

- `ApplicationError(Exception)` `application/contract.py:45`: `.error: ApiError`; `.code` property.
- `Application` Protocol `contract.py:66`:
  `validate(revision_id, task) -> ValidationReport`;
  `commit_change(change, expected_revision, idempotency_key) -> TransactionResult`;
  `solve(revision_id, policy_id) -> RunResult`;
  `reproduce(bundle_path, policy: ReplayPolicy) -> ReplayReport`.
- `JobControl` (`contract.py:126`): `submit_job`, `get_job`, `list_jobs`, `list_job_events`,
  `wait_job`, `cancel_job`, `get_job_result` (7 methods).
- `Inspection` (`contract.py:150`): `get_project`, `list_models`, `list_revisions`, `get_revision`,
  `diff_revisions`, `inspect_structure`, `preview_change`, `get_artifact`, `list_audit` (9 methods).
  `artifact_bytes` is the raw export row.
- `Page[T]` `:83`, `Projection` `:96`.

### 8a. LocalApplication (`application/local.py:155`)

```python
class LocalApplication:
    """One project, opened by one owner. Construct through `create`, `open` or `in_memory`."""
    @classmethod
    def create(cls, directory, *, project_id: str | None = None) -> LocalApplication: ...   # :190
    @classmethod
    def open(cls, directory, *, ...) -> LocalApplication: ...                              # :214
    @classmethod
    def in_memory(cls) -> LocalApplication: ...                                            # :278
    def solve(self, revision_id: str, policy_id: str) -> RunResult: ...                   # :608
```
`solve` submits a job with an `auto:` idempotency key, waits, then returns
`get_job_result(...).run_result`. `policy_id="default"` resolves to the route's registered policy.
A refusal at submission is raised as `ApplicationError`. A failed solve is a result, not an exception.
Other methods: `validate :443`, `commit_change :488`, `reproduce :645`, `submit_job :669`,
`wait_job :719`, `get_job_result :767`, `list_audit :1359`, `artifact_bytes :1440`.

### 8b. RunResult (`application/types.py:1142`)

Fields: `job_id, run_id, revision_id, revision_content_sha256, policy_id, policy_sha256,
check_policy_sha256, job_status: TerminalStatus, outcome, verification_status: VerificationStatus | None,
structural_sha256, outputs: tuple[ArtifactRef, ...], error: ApiError | None = None,
solve_path: SolvePath = "revision_eo"`.
`__post_init__` refuses a `verification_status` without a `solution_certificate` output (§5.7).
`job_status` is not `verification_status`.

`TerminalStatus = Literal["completed","failed","cancelled","timed_out"]` (`application/jobs/model.py:31`).
`SolvePath = Literal["revision_eo","legacy_eo","revision_coupled"]` (`application/types.py:116`).

### 8c. ApiError and codes (`application/types.py`)

- `ApiErrorCode` Literal at `:69` (15 codes): `invalid_request, document_not_canonical,
  unauthenticated, forbidden, not_found, idempotency_key_reused, not_ready, revision_not_ready,
  revision_unsupported, verification_weakening_refused, budget_exceeds_ceiling, limit_exceeded,
  unsupported, internal_error, model_replacement_incompatible`.
- `API_ERROR_HTTP_STATUS` at `:88`: code to HTTP status (422, 401, 403, 404, 409, 429, 501, 500, ...).
- `@dataclass(frozen=True) class ApiError` at `:261`:
  ```python
  code: ApiErrorCode; message: str; retryable: bool; detail: Mapping[str, Any] = {}
  @property http_status -> int   # API_ERROR_HTTP_STATUS[code]
  ```
  "§5.8: the one error shape. Domain outcomes are results, never an `ApiError`."
- Schema: `schemas/api-error.schema.json`.

### 8d. How bindings derive from the contract

- One table: `application/operations.py:293` `OPERATIONS: Mapping[str, Operation]`. Each row names its
  method, right, request and response schemas, HTTP verb and path, MCP tool name, transports, and
  description. `ALL_TRANSPORTS = ("python","cli","http","mcp")` (`:75`).
- `dispatch(app, name, request)` at `operations.py:544` is the single path for all bindings. Steps:
  canonical form, request schema, typed decoding, method call, response bounding (`project_response` `:536`).
- CLI: `application/cli.py` builds argparse subcommands `validate` (:470), `solve` (:478), `inspect`
  (:483), `replay` (:487), `project init|grant|revoke` (:495-520), `api` (:525), `serve-http` (:547),
  `serve-mcp` (:562). Console script: `pyproject.toml` `[project.scripts] openflowsheet =
  openflowsheet.application.cli:main`.
- HTTP: `application/bindings/http.py`. `HTTP_OPERATIONS` (`:83`) and one `OperationRoute` per row (`:424`).
- MCP: `application/bindings/mcp.py`. `TOOL_OPERATIONS` (`:81`); `list_tools` and `call_tool` (`:197`, `:207`).
- Web shell: `application/bindings/web.py` adds static routes after the OPERATIONS routes.
- Authorization: `Right = Literal["read","draft","execute","install","policy","publish"]`
  (`application/types.py:106`); `application/authz.py`.

---

## 9. Replay and identity

### 9a. What a replay bundle contains

Writer: `run/bundle.py:53` `write_bundle(directory, manifest: RunManifest, artifacts: Mapping[str, Any])`.
It writes `run-manifest.json` (`MANIFEST_NAME`, `:27`) and `artifacts/` (`ARTIFACT_DIR`, `:28`). The
manifest's `artifacts` index is built from the bytes written, not from the caller. `verify_bundle` at
`:121` re-hashes each file (returns `BundleIntegrity`, a typed result; "tampered" is a result, not an exception).

Artifact file names assembled by `application/revision_run.py` (around lines 841-864):
`solve-events.json`, `structural-report.json`, `revision.json`, `solve-policy.json`,
`check-policy.json`, `solve-path.json`, `execution-plan.json` (ExecutionPlan route),
`solve-plan.json` (when present), `solution-certificate.json` (when a certificate exists),
`failure-bundle.json` (on failure). `solution-state.json` (`run/solution_state.py:36`, schema
`solution-state-v1`) is written beside a certificate of any verdict.
Artifact kinds (`application/jobs/model.py:51` `ArtifactKind`, `:81` `ARTIFACT_KINDS`) include
`solve_trace, solve_plan, execution_plan, structural_report, solution_certificate, solution_state,
failure_bundle, revision_document, solve_policy, check_policy, solve_path, run_manifest,
replay_bundle, replay_report, partial_solve_trace`, and more (list truncated in my read).

ADR 0006 D1.3: the bundle references the backend by hash and never embeds it.

### 9b. RunManifest (`run/manifest.py:221`)

Fields: `run_id, model_version, constants_sha256, policy_id, plan_id, check_policy_sha256,
policy_sha256, artifact_r0_sha256, numerical_policy_id, environment: Environment, artifacts:
Mapping[str,str], outcome, verification_status, seeds, reproducibility_class="R1", parent_run_id,
started_at, elapsed_seconds, hostname`. `structural_sha256` is computed from the document, not stored.

`NON_STRUCTURAL` (`run/manifest.py:66`): `run_id, started_at, elapsed_seconds, parent_run_id,
hostname, environment, artifacts`.

### 9c. What is hashed into identity

- `RunManifest.structural_sha256` is computed from the document (`run/manifest.py:221` docstring); the
  fields in `NON_STRUCTURAL` (`:66`) are excluded. Its R0 preimage is `r0_projection(artifacts)`
  (`run/identity.py:59`), with no floats at any depth: plan
  structure (tear and inner variable/row ids, eliminated rows), event sequence, certificate check ids
  and results, solver counters. `r0_sha256` at `:169`. ADR 0007 D2.4: near-threshold flags are carried
  as booleans.
- `model_version` and `constants_sha256` (`EvaluationContext`, ADR 0002 and 0008 D4.1): structure digest
  of the spec plus the parameter hash in `parameter_ids` order.
- Revision: `configuration_sha256` (`models/revision_flowsheet.py:858`) and `content_hash`
  (`application/revisions.py:51`) as in 6a.
- `policy_sha256(policy)` (`run/manifest.py:343`); `check_policy_sha256` for the check policy.
- Exact property cache key (`thermo/cache.py:173-190`): see 3e.

### 9d. Environment recording

`run/manifest.py:80` `class Environment` with fields `architecture, os_name, os_release,
python_version, lock_sha256, blas: Mapping[str,str], threads: Mapping[str, str|None],
superlu_options_ref="ADR 0004 D1"`. Built by `environment(lock_path=None)` at `:169`.
`blas_identity()` `:151` (what SciPy reports). `THREAD_VARIABLES` (`:37`): `OPENBLAS_NUM_THREADS`,
`OMP_NUM_THREADS`, `MKL_NUM_THREADS`. Lock hashing via `_repository_lock` `:185` and `_checkout_lock` `:189`.

Replay (`run/replay.py`): `ReplayMode = Literal["exact_replay","compatible_reproduction",
"inspected_archived_results"]` (`:39`). `REGISTERED_PLATFORMS` (`:52`). `ReplayReport` (`:58`):
`mode, verdict, integrity, recorded_environment, current_environment, reasons, differences,
bitwise_floats, verdict_changed_near_threshold`. `decide_mode(recorded, current)` `:85` compares lock
hashes first (ADR 0007 D4). `replay(...)` `:173`.

---

## 10. Transient readiness (ADR 0008 and amendments)

`docs/adr/0008-transient-extension-readiness.md`. Status: Accepted 2026-09-16 (R-001).

Steady-state decisions (ADR body, lines 22-91):
- D1 (line 24): time is not a coordinate of the evaluation boundary. `residual`, `jacobian`,
  `reconstruct` are functions of `x` and `context`. `EvaluationContext` has no time field. `workspace`
  is inert (D1.4). The field set is pinned by `tests/test_adr_0008_transient_readiness.py`.
- D2 (line 33): `state_sha256` covers exactly the dense `x`, after signed-zero normalization.
  Pairing identity; one-ulp sensitive by construction (D2.6).
- D3 (line 42): every declared equation carries an accumulation declaration
  (`algebraic | zero_holdup_balance | holdup_balance | absent`); no default; dimension consistency
  checked; balance-row sign convention.
- D4 (line 81): obligations on later packages: K01 pinned-input identity; K01 inert workspace; K02
  balance-row sign; K01 row accumulation in metadata; T04 pattern of `M` from manifests; any later
  transient ADR.

Amendment 1 (line 580, "transient readiness revisited at ~37 000 lines"):
- A1.0 table (lines ~590-602), candidates C1–C10 with a "Later" column that maps each C_n to an X_n:
  - C1 UV closure for holdup states: no widening; convention registered in text (→ X1)
  - C2 pressure–flow semantics: already additive (→ X2)
  - C3 U in manifests, H in PTC mass: adopt; U–H constraint A1.2 (→ X3)
  - C4 steady and dynamic forms: separate model variant sharing kernels (→ X4)
  - C5 phase logic under time stepping: already additive (→ X5)
  - C6 result, run, job and replay records: adopt as constraint on T07, J1–J3, J5 binding, J4, J6
    recommended; RunManifest and replay unchanged (→ X6)
  - C7 time-varying specifications: additive `oneOf` branch later (→ X7)
  - C8 differential markers: reject the marker; row to column map later (→ X8)
  - C9 pinned-input re-binding without recompiling: reject; backend-internal (→ X9)
  - C10 non-conservation differential rows: reject; new kind via ADR (→ X10)
- A1.2 (line 634): U–H.1 to U–H.8, the internal-energy and holdup relations for future holdup units.
- A1.3 (line 647): where each provision sits relative to blueprint §2.2.
- A1.5 open questions (line 660); A1.6 work orders; A1.9 disposition of the review.

Amendment 2 (line 726, "re-checked at the 0.2.0 cut", 2026-10-21):
- A2.1 findings F1–F11 (line 765). F8: X4 (i)–(ii) are stale; 24 modules hash their own bytes into
  an identity at 0.2.0.
- A2.2 (line 779): X4′ replaces X4 (i)–(ii) with a rule based on self-hashing modules; X11 (line 785)
  external models in a transient problem, two admitted forms: (a) quasi-steady, (b) model exchange;
  co-simulation excluded. J5 widened.
- A2.3 decisions (line 793), including recording X11 now.

Not verified: that every X-id body text is reproduced here. I used the A1.0 table mapping and the
A2.2 text.

---

## 11. Optimisation and economics (E01 / "S12")

Governing ADR: `docs/adr/0052-e01-assessment-functionals.md`, Accepted 2026-10-30. The ADR text names
the evidence manifest id `S12` (`evidence/S12/d87078af7531b3b0d260ec3cc4a9317efc35b1ac/manifest.json`,
status `tested`). Design note: `docs/derivations/E01-design.md`. Briefs under `docs/briefs/`.

Core idea (`src/openflowsheet/assessment/__init__.py` docstring; `assessment/program.py` docstring):
an assessment is an explicit post-solve functional `y = G(x, d; θ, ρ)` of a verified state, compiled
by the existing compiler as a *functional* `ProblemSpec` and never part of a `CompiledProblem`.
It does not change any certificate or replay identity (§4.14).

Entry points:
- `assessment/spec.py:39` `class AssessmentSpec` (validated document plus `assessment_sha256`);
  `load_assessment(source)` (~line 50). Schema `schemas/assessment.schema.json`; report
  `schemas/assessment-report.schema.json`.
- `assessment/program.py`: "the assessment program". `register_contributor(name, factory)` `:173`;
  `Contributor` protocol `:164`; `ContributionPlan` `:148`; `OutputDef` `:141`; `Theta` `:118`;
  `Symbols` `:210`; `_assemble` `:336`. Contributors `cost`, `lca`, `derived`, in that order.
  The program assembles a functional `ProblemSpec` and evaluates it with `ParametricTwin`
  (`compile/casadi_backend.py:680`), so value, `∂/∂x` and `∂/∂p` come from one graph.
- `assessment/report.py` (324 lines): report assembly.

Cost (`assessment/cost/`):
- `operating.py:61` `price_on_basis(...)` (`PriceOnBasis` `:51`) and `annual(rate, hours_per_year)` `:94`:
  annual operating cost from prices and hours.
- `capital.py:156` `crf(rate, years)`: capital recovery factor. `Chain` `:83`; `load_chain(chain_id)` `:138`:
  capital cost chains (`ChainTerm` `:52`, `ChainStep` `:68`). `discount_rate_domain` `:162`.
- `index.py:166` `escalate(...)`: cost-index escalation between source and target bases
  (`SourceBasis` `:131`, `TargetBasis` `:143`, `Escalation` `:153`); `load_series` `:120`,
  `load_rates` `:125` (default series `frb-g5a-annual-v1`).
- `forms.py` (801 lines) and `contributor.py` (1154 lines): cost forms and the cost contributor.
- `sets.py` (653 lines), `quotes.py`, `uncertainty.py`, `defaults.py`: equipment cost sets, quotes, uncertainty.
- Sizing: `assessment/sizing/__init__.py:135` `SizingPlan`; `families.py` (1058 lines); `SizingInput` `:90`.
- Not verified in depth: `assessment/cost/derived.py` and `cost/forms.py` formula text.

LCA (`assessment/lca/`):
- `impact.py:338` `plan_impacts(...)`: impact categories per functional unit; `ImpactPlan` `:49`;
  `categories_of` `:60`; `_priced` `:302`, `_annual` `:309`, `_per_fu` `:316`, `_rate` `:323`.
- `inventory.py:179` `plan_inventory(...)`: inventory exchanges; `Exchange` `:63`; `InventoryPlan` `:85`;
  `stream_flow` `:111`; electricity exchange `_Electricity` `:135`.
- `brightway.py` (474 lines): Brightway LCA backend. `tables.py` (409 lines): LCA tables.
  Data licences: `docs/e01-data-licences.json`, `docs/e01-lca-licences.json`.

Studies using functionals: `studies/` (not read in depth).

---

## 12. Sizes

Lines of Python (`find ... -name "*.py" | xargs cat | wc -l`, excluding `__pycache__`):

| Subpackage (src/openflowsheet/) | Lines |
|---|---:|
| models | 28,479 |
| studies | 16,530 |
| application | 19,184 |
| orchestrator | 11,214 |
| thermo | 11,501 |
| assessment | 9,008 |
| verify | 8,796 |
| graph | 2,307 |
| numerics | 2,665 |
| adapters | 3,352 |
| run | 2,197 |
| compile | 1,220 |
| units | 601 |
| ir | 10 |
| _data | 0 (data only) |
| root files (`__init__`, `canonical.py` 599, `serialize.py` 309, `compiled.py` 172, `resources.py` 112, `_files.py` 29) | 1,237 |
| **Total under src/openflowsheet** | **118,301** |

(Subpackage sum is 117,064; root files are 1,237.)

Sub-totals for the big ones: `application/revision_binding.py` 2131; `application/local.py` 1864;
`application/types.py` 1694; `application/store.py` 1268; `application/revision_run.py` 1254;
`orchestrator/region.py` 2794; `models/syn001/column.py` 2080; `thermo/_coolprop_heos_fluids.py` 4919 (data table);
`verify/certificate.py` 1435.

Test files:
- `tests/`: 465 files matching `test_*.py`; 513 `.py` files in total (including `conftest.py`,
  helpers, `tests/fixtures/`, `tests/data/`). Total lines of `test_*.py`: 169,830.
- Prefix counts (module names): `t07:52, t05:46, t06:37, t08:35, s11:23, m02:23, m04:17, m05:21,
  s10:14, m03:12, k03:10, k04:10, t04:10, v03:8, s08:8, m01:7, m06:16, m07:15, e01:18, k02:6, k01:4,
  l01:5`, and others.
- Test paths and run: `pyproject.toml:187` `[tool.pytest.ini_options]` `testpaths = ["tests"]`,
  `pythonpath = ["."]`. `scripts/check.sh` runs `ruff check`, `ruff format --check`, `mypy`, `pytest -q -rs`.
  `scripts/gate.sh` wraps the gate.

Worktree caveat: `.claude/worktrees/` holds full checkouts of older or parallel branches (for example
`m03`, `m06-w27h`, `m07`, `alpha-gate`, `rc-cc73219`). Their `schemas/` and `src/` copies are not the
`main` tree. I did not read them.

---

## Not found / not verified

- Item 4: no `residual()` or `jacobian()` method on unit models. The residual is built through `EquationSpec.build`, and the Jacobian is produced by the backend. This is the code's actual shape, not a gap in my search.
- Item 3: `pr-lib-v1` is not registered as a `ComponentBasis` and not in `FRESH_PROVIDERS`. I did not find a revision path that selects it.
- Item 5: no separate "linear solver registry" beyond SuperLU options (ADR 0004, `numerics/linear.py`, 261 lines; not read).
- Item 9: the exact contents of `solution-state.json` and of the replay bundle beyond the artifact names listed in 9a were not opened in full. `ArtifactKind` was truncated in my read after `partial_solve_trace`.
- Item 11: `studies/` (16.5k lines) was not read beyond its module list. Cost formula text in `cost/forms.py` and `cost/derived.py` was not read.
- Item 10: the full body text of every X1–X11 constraint was not reproduced. X-ids are taken from the A1.0 mapping and A2.2.
- Searched and not found: a `ModelManifest` Python dataclass named exactly that (the manifest is a document built by `manifest_document`, and `Port`/`DerivativeDeclaration`/`Initialization`/`Validity` are its typed parts); a `component record` class (components are YAML parsed into `C1Component`/`LibraryComponent` and the schema validates the YAML); `vapor_liquid` as a `Phase` member (deliberately absent by design, per `models/__init__.py:78-80`).
- Not read, by rule: `~/.config/procsim/*`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.

## Guidance documents that govern these areas

- `CLAUDE.md` (repo): authority is `docs/blueprint-v3.1.md`; plan is `docs/implementation-plan.md` v1.2; `docs/decision-register.md` (about 18,300 lines) indexes decisions. Lane rules §1.3. A departure from the blueprint or plan needs an ADR under `docs/adr/`.
- `docs/adr/0056-capability-extension-plan.md`: the 2026-11-01 capability-extension plan (current, packages MSG, ST, X01–X26 provisional).
- `docs/USER_FEEDBACK.md`: intake log; `docs/FRANK_QUESTIONS.md`.
- Per-area ADRs as cited above: 0001 (state, units, zero flow), 0002 (canonicalization, schemas), 0003 (backend), 0004 (SuperLU), 0005 (phase attempt), 0007 (certificate policy), 0008 (transient readiness), 0009 (execution plan and recycle), 0010 (globalization), 0019 (application contract), 0020 (jobs), 0034 (external models), 0043 (pr-lib), 0047 (Wilson), 0050 (binding package), 0051 (thermal units), 0052 (E01 functionals), 0054 (semantic roles).
- `docs/interfaces-frozen.md`: frozen signatures and schema list; any change needs a design-lane ADR.
- `docs/design/` and `docs/derivations/`: design notes (for example `docs/derivations/E01-design.md`, `docs/derivations/T04-globalization-spec.md`).
