# M01 Reconnaissance: Peng–Robinson Provider and Component Records

*Recon-grade digest (read-only reconnaissance, 2026-10-06): locations and excerpts, no judgement. Verify any claim against the code before relying on it.*

## 1. Property-Provider Interface

### Location and Protocol
`src/openflowsheet/thermo/__init__.py:209–224` defines the frozen `PropertyProvider` protocol. Changes require an ADR.

```python
# src/openflowsheet/thermo/__init__.py:209–224
@runtime_checkable
class PropertyProvider(Protocol):
    """Frozen in `docs/interfaces-frozen.md` §1; changes require a Fable-authored ADR."""

    def describe(self) -> PropertyCapabilities: ...

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult: ...

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult: ...
```

### `PropertyCapabilities` Declaration
`src/openflowsheet/thermo/__init__.py:61–101`. A provider must declare (all fields required):

- **`provider_id`**, **`implementation_sha256`**, **`data_sha256`** — exact cache keys (blueprint §6.4)
- **`reference_convention`** — e.g. `"SYN-001-ref-v1"` for the synthetic, or a new one for Peng–Robinson (M01 decision)
- **`state_definition`** — `"nTP-v1"` (ADR 0001 D2)
- **`components`** — ordered tuple; ordering is cached identity (exact-key member)
- **`phases`** — e.g. `("LIQUID", "VAPOR")`
- **`properties`** — e.g. `("h", "lnK")`, or expanded for PR (enthalpy, fugacity, K-values, etc.)
- **`flashes`** — e.g. `("TP",)` (v0.0) or `("TP", "PH")` (T05 adds PH via unit-layer formulation, not provider)
- **`derivative_order`** — `{input_id: order}`, e.g. `{"T": 1, "P": 1}`
- **`domain`** — `{variable: (min, max)}` inclusive
- **`uncertainty`, `data_provenance`, `thread_safety`, `numerical_limitations`** — descriptive

### Result Types

**`PropertyResult`** (`src/openflowsheet/thermo/__init__.py:150–170`):
- **`status`** — `"ok" | "out_of_domain" | "unsupported" | "not_converged" | "error"`
- **`phase_signature`** — `"LIQUID" | "VAPOR" | "TWO_PHASE" | "ZERO_FLOW" | None`
- **`values`** — `{property_id: float}`, keyed by name
- **`derivatives`** — `{property_id: {input_id: d(property)/d(input)}}` (sparse; absent = not computed)
- **`achieved_accuracy`** — `"exact-double"` (v0.0 only value)
- **`provider_id`, `reference_convention`, `message`**

**`FlashResult`** (`src/openflowsheet/thermo/__init__.py:182–206`):
- **`status`** — as above
- **`phase_signature`** — as above
- **`vapor_fraction`** — molar basis, or `None` if undefined (dormant, failed)
- **`vapor`, `liquid`** — `StreamState | None` (both `None` on failed flash)
- **`k_values`** — `{component_id: K_i}`
- **`iterations`** — actual iterations taken (blueprint §6.4)
- **`achieved_accuracy`, `provider_id`, `reference_convention`**

### Exact-Cache Keys
`src/openflowsheet/thermo/cache.py:174–214` builds keys from:
1. Identity (provider_id, implementation_sha256, data_sha256, components, reference_convention, state_definition, accuracy_policy, phase_signature)
2. Request (state via `state_sha256` at full double precision, never quantized; phase; properties; derivatives)
3. For flashes: specification (e.g. "TP")

**Critical rule** (cache.py:24–27): "Quantizing state coordinates is forbidden and is not merely avoided." One-ulp sensitivity enforced by `openflowsheet.canonical.state_sha256()`.

### SYN-001 Implementation (Reference)
`src/openflowsheet/thermo/syn001.py:74–287` shows the pattern. Key excerpts:

- **Closed forms** (lines 292–325): `ln_k()`, `h_liquid()`, `h_vapor()` with declared derivatives
- **Rachford–Rice flash** (lines 186–286): bracketed bisection + Newton, 200 iteration limit, 1e-14 tolerance
- **Domain checks** (lines 328–336): return `out_of_domain` status, never extrapolate
- **Zero flow** (lines 195–211): dormant feed → two dormant outlets, `ZERO_FLOW`, valid result
- **Equilibrium form** (flash.py:8–10, syn001.py comment): uses K-values not mole fractions to avoid ln(0)

## 2. Component Records

### Schema
`schemas/component-record.schema.json` — frozen at P01, required fields:
- **`id`** — stable identity within component set
- **`name`** — display name
- **`synthetic`** — boolean (false for real chemicals)
- **`identifiers`** — `{db: id}`, e.g. `{"cas": "7732-18-5"}` (not present if `synthetic: true`)
- **`molecular_weight`** — `Quantity` with `kind: "molar_mass"` (kg/mol) — **the only route to mass basis** (ADR 0001 D1.4)
- **`elemental_composition`** — `{element: count}` or `null` (pseudo-components must use `null` with `elemental_verification: "NOT_APPLICABLE"`)
- **`elemental_verification`** — status: `"VERIFIED" | "PENDING" | "FAILED" | "NOT_APPLICABLE"`
- **`parameters`** — `{name: Quantity}`, each with own `provenance` — e.g. Tc, Pc, ω, cp, formation enthalpy
- **`rights`** — required: `{source, redistribution, notes?}` — data rights must be explicit (blueprint §15, requirement D04)

### Data Location & Registration
- **Existing records** — `src/openflowsheet/_data/benchmarks/` (symlink to repo copies)
- **Revisions stored as** — `benchmarks/syn001/components.yaml`, `benchmarks/*/revisions/*.yaml`
- **Reference convention declared** — property provider declares it (e.g. `SYN-001-ref-v1`); M01's PR provider will declare its own (e.g. `PR-v1-formation-datum`)
- **Formation datum** — ADR 0001 D5.1 + ADR 0011 D2: formation enthalpy/Gibbs energy at a reference state (`T_r`, `P_r`). SYN-001 uses `h_i^L(300 K, 100 kPa) = 0`; M01 must declare its own for PR (decision pending in docs/decision-register.md).

### Test Verification
K02 `test_k02_syn001_provider.py` pattern: component IDs match provider's `describe().components` tuple order.

## 3. Flash Unit / Phase Logic

### Phase-Attempt Contract (ADR 0005, ADR 0012)
- **Regimes** — `LIQUID | TWO_PHASE | VAPOR` lattice (ADR 0005 D2)
- **Phase signature on stream** — `LIQUID | VAPOR | TWO_PHASE | ZERO_FLOW` result
- **Active set during attempt** — frozen per attempt; phase set cannot change mid-attempt (ADR 0005 D2)
- **Appearance/disappearance** — screened with admissibility check; restart on phase-adjacent candidate (D3–D4)

### TP Flash Declarations
`src/openflowsheet/models/syn001/flash.py:88–189` shows unit contract:

```python
# src/openflowsheet/models/syn001/flash.py:127–189 (EQUATIONS)
DeclaredEquation(
    equation_id="FLASH-mole",
    statement="n_in,i - n_vap,i - n_liq,i = 0 for every component i",
    dependencies=("inlet.state.n", "vapor.state.n", "liquid.state.n"),
    conditional_class="unconditional",
    accumulation=Accumulation(kind="holdup_balance", holdup=...),
),
DeclaredEquation(
    equation_id="FLASH-equilibrium",
    statement="y_i - K_i(T, P) x_i = 0 for every component present...",
    conditional_class="phase_conditional",
),
DeclaredEquation(equation_id="FLASH-T", statement="T_vap - T_spec = 0..."),
DeclaredEquation(equation_id="FLASH-P", statement="P_vap - P_spec = 0..."),
DeclaredEquation(
    equation_id="FLASH-duty",
    statement="Q - (Hdot_vap + Hdot_liq - Hdot_in) = 0...",
    accumulation=Accumulation(kind="holdup_balance", holdup=Holdup(symbol="U", ...)),
),
```

### Rachford–Rice Solver (ADR 0017)
Bracketed bisection: closed forms `sum_zK`, `sum_z_over_K` declare single-phase regions; ADR 0017 D1 classifies on the feed. Limit: 200 iterations, 1e-14 tolerance. Returns `not_converged` status if limit hit (never returns unconverged split as "ok").

### Zero-Flow Behavior (ADR 0001 D3.4)
TP flash with dormant feed: two dormant outlets, exactly zero duty, signature `ZERO_FLOW` — valid result, not failure. No K-values reported (composition undefined).

### PH Flash (T05, ADR 0011 D1)
Unit-layer formulation: fixed outlet enthalpy + outlet temperature free; bracket on provider's TP flash to find T satisfying `Ḣ(n, T, P) = H*`. Provider stays TP-only; no `flashes: ("PH")` capability.

## 4. Verifier (K04)

### Location & Design
`src/openflowsheet/verify/__init__.py:1–20`, with supporting modules in `verify/*.py`. **"The verifier never sees the solver"** — fresh provider, no cache, independent fresh flash of each stream.

### Verification Flow
1. Accept state vector and revision
2. Call provider's `evaluate_phase()` for each stream, each phase (fresh evaluation)
3. Recompute every stream's phase split via fresh `flash()` call
4. Assemble material balances by plain summation (no cached values)
5. Recompute enthalpy from fresh flash split
6. Factorize Jacobian independently

### Provider Calls Required
- **`describe()`** — once, to get capabilities and domain
- **`evaluate_phase()`** — per stream, per phase (residuals, Jacobians)
- **`flash()`** — per stream with two-phase split (independent split verification)

### Check Categories
`verify/__init__.py:27–38`:
```python
CheckCategory = Literal[
    "residual", "alias_certificate", "material_balance", "energy_balance",
    "specification", "bounds_and_domain", "phase_admissibility",
    "independent_split", "derivative_witness",
]
```

**Failing categories** (lines 73–84): residual, balance, specification, bounds, phase_admissibility, independent_split. Derivative witness failure caps verdict at `UNVERIFIED`, not `FAILED`.

## 5. Unit Library

### Existing Models (K02, T05)
`src/openflowsheet/models/syn001/`:
- **Feed** (`feed.py`) — source with specified constant composition
- **Mixer** (`mixer.py`) — adiabatic, two-phase capable (restricted to mixing paths in K02)
- **Heater** (`heater.py`) — TP outlet state (temperature fixed, duty free)
- **Splitter** (`splitter.py`) — isobaric, adiabatic, with composition split specification
- **Flash** (`flash.py`, `tp_state.py`) — TP equilibrium, two outlet phase split
- **Pump** (`pump.py`) — pressure increase with efficiency
- **Valve** (`valve.py`) — isenthalpic throttle
- **Heat Exchanger** (`heat_exchanger.py`) — two-stream energy transfer
- **Conversion Reactor** (`conversion_reactor.py`) — reactive mixer with per-species stoichiometry
- **Kinetic CSTR** (`kinetic_cstr.py`) — well-mixed batch with rate law (ADR 0023)
- **Component Separator** (`component_separator.py`) — split by component mapping
- **PH Flash** (`ph_flash.py`, `ph_kernel.py`) — T05: outlet enthalpy specified, temperature free

### Port Declaration Pattern
`models/syn001/flash.py:88–125`:
```python
PORTS: Final[tuple[Port, ...]] = (
    Port(name="inlet", kind="material", direction="inlet", multiplicity=1,
         component_mapping="revision_component_set", state_definition="nTP-v1",
         phase_capabilities=("liquid", "vapor", "vapor_liquid")),
    Port(name="vapor", kind="material", direction="outlet", multiplicity=1,
         component_mapping="revision_component_set", state_definition="nTP-v1",
         phase_capabilities=("vapor",)),
    ...
    Port(name="duty", kind="energy", direction="inlet", multiplicity=1,
         component_mapping=None, state_definition=None, phase_capabilities=()),
)
```

### Degrees of Freedom & Specifications
Unit declares:
- Free state variables (via ports: `n_i`, `T`, `P` per stream)
- Specification rows that fix some (e.g., flash outlet T at a setpoint)
- Free duty (energy port)
- See `models/__init__.py:119–136` for naming conventions: `flow_id()`, `temperature_id()`, `pressure_id()`, `duty_id()`, `row_id()`

### External/Grey-Box Units
**No support in v0.0.** ADR 0008 (references in models/__init__.py comments) implies future: "a causal evaluator and local initializer" are unit obligations; an opaque evaluator (no residual form) is "exactly what R-008 rejected for the lifted split."

## 6. Model Registration & Identity

### Model Listing
`src/openflowsheet/application/revision_binding.py:89–104` defines `MODEL_BUILDERS` and `MODEL_SIGNATURES`. Each maps:
- Model ID (e.g., `"syn001.tp_flash"`) → builder function + signature

### Benchmark Cases
`benchmarks/registry.yaml` (snapshot structure):
- **Families** — e.g. `SYN-001` (synthetic), `SYN-001-UL` (unit-library test cases), `T08` (real-chemistry target)
- Per family:
  - `derivation`, `specification`, `semantics` (ADRs)
  - `components` (YAML file path)
  - `oracle`, `reference`, `reference_sha256`
  - `property_domain`, `reference_convention`, `state_definition`
  - `tolerances`, `scales`, `budgets`

### Replay Identity (ADR 0009, K05)
SYN-001 structural hash (`canonical.document_sha256()` of flowsheet spec) includes:
- All model IDs and their parameters
- Component set and order
- Provider implementation and data hashes (R-009: provider source hash in `model_version`)
- No unit model changes → same SYN-001 hash

**M01 impact**: New PR provider with different implementation/data hashes will create new structural hashes for models that use it, but SYN-001's identity stays unchanged (uses existing SYN-001 provider).

## 7. Dependencies

### Runtime (pyproject.toml:18–29)
```python
dependencies = [
    "numpy==2.2.4",
    "scipy==1.15.3",
    "pyyaml==6.0.2",
    "jsonschema==4.26.0",
    "casadi==3.8.0",  # compiled backend (ADR 0003), LGPL-3.0-or-later
]
```

**Not present**: `chemicals`, `thermo`, `CoolProp`, `cantera`. **M01 must ship its own PR EOS code** or negotiate external dependency additions (likely policy decision).

### Development (pyproject.toml:32–39)
`mpmath==1.3.0` for derivation reference values (40 digits). Tests use `pytest==8.3.5`.

## 8. Decisions in Decision-Register

### R-120 (v0.2 real chemistry)
- **Date**: 2026-09-29
- **Decision**: Ammonia synthesis loop on group's PyMRM model; runner-up methanol loop
- **Affected**: T08, M01 (chemistry choice)

### R-143 (V19 for C1 IDAES 2.13)
- **Date**: 2026-10-01
- **Decision**: "For C1, 'the selected method' is **Peng–Robinson with H₂, N₂, Ar and CH₄ declared vapour-only** (the liquid is NH₃ alone); IDAES 2.13 represents the skeleton with it, so H4 is met... A61's 'own regression reference' is the group's pytest suite at the pin `6089593`... 69 passed, 0 failed, 3 skipped... H2 reads met (a published rate law with parameters, compared with experimental data); item 5 is met only with the K_NH₃ discrepancy named, and item 11 lists the K_NH₃ enthalpy term among M01's pin items."
- **Affected**: T08 (V19), M01
- **Watch**: Dissolved-gas effects claimed without full-VLE route

### R-152 (M01 K_NH₃ enthalpy term pin)
- **Date**: 2026-10-06
- **Decision by**: Frank Peters (not automated)
- **Text**: "The ammonia kinetics M01 pins carry K_NH₃ = exp(−8.3/R + 7000/RT), R in cal/(mol·K), exactly as the group's reactor at `6089593` implements it. The T08 ruling (release spec Amendment R3 8 (e)) that the term be read from Rossetti et al. 2006 itself is replaced by Frank's decision."
- **Evidence**: reactor code at commit `6089593`, Gargiulo 2025 Table 1 (29 288 J/mol alternative rejected as transposition)
- **Affected**: M01, M02 (reactor pin), M07
- **Watch**: "This is a decision, not a verification: no record may say the value was checked against Rossetti 2006."

### R-153 (v0.2 work order)
- **Date**: 2026-10-06
- **Decision by**: Frank (build-lane recommendation)
- **Text**: "M01's design lane first (critical path M01→M02→M04→M05→M07), M06 built alongside, M03 when the critical path allows; pre-release `0.2.0a1` after M02."

## 9. Test Patterns & Verifier Examples

### Provider Tests
`tests/test_k02_syn001_provider.py:66–97` (pattern):
```python
def test_k_values_agree_with_the_independent_oracle(temperature, pressure):
    """Two separate transcriptions of the same derivation, neither importing the other."""
    expected = oracle.k_values(temperature, pressure)
    for index in range(len(COMPONENTS)):
        assert math.exp(ln_k(temperature, pressure, index)) == pytest.approx(
            expected[index], rel=1e-15
        )

def test_the_flash_split_agrees_with_the_independent_oracle(provider, temperature, pressure):
    state = StreamState(n=(1.0, 1.0, 1.0), temperature=temperature, pressure=pressure)
    result = provider.flash(FlashRequest(state=state), CONTEXT)
    expected = oracle.tp_flash(state.n, temperature, pressure)
    assert result.status == "ok", result.message
    assert result.vapor_fraction == pytest.approx(expected.beta, abs=1e-13)
```

### Adversarial Tests (ADR 0001 coverage)
- **STA-01** — no division by zero in zero-flow mixer
- **STA-02** — zero component in flowing stream (ln(x_i) not evaluated)
- **STA-03** — state conversions (mass ↔ molar basis)
- **Zero-flow variants** — `r=0`, `310K` all-liquid, `420K` all-vapor (SYN-001 oracle)

### Verifier Certificate Test (K04)
`verify/__init__.py:87–97` carries frozen statement text on every certificate; see `verify/certificate.py` for full structure.

## 10. Key Architectural Points for M01

### Exact-Cache Requirement
PR provider must:
- Declare `implementation_sha256`, `data_sha256` (fixed for the version)
- Never quantize state coordinates (one-ulp sensitive)
- Return `out_of_domain` (not extrapolated) outside domain
- Report `achieved_accuracy` (v0.0: only `"exact-double"`)

### Reference Convention
M01 must declare a new one (e.g., `"PR-v1-NH3-liquid-ref-formation"`), with formation enthalpies for H2, N2, Ar, CH4, NH3 (or state why each is zero/undefined given vapor-only light gases).

### Vapour-Only Light Gases
R-143 decision: H₂, N₂, Ar, CH₄ declared vapour-only; liquid is pure NH₃. Implication:
- Equilibrium rows for vapour components; none for liquid (K_vap = n_vap,i / n_liquid,NH3)
- Provider must reject two-phase queries mixing vapour-only with liquid components
- Flash outcome: either all-vapour or pure-liquid NH₃

### Provider Pin
R-152: M01 pins K_NH₃ formula to reactor code, not to Rossetti 2006 check. Verification audit must **not claim** Rossetti agreement if made later (decision, not verification).

### Test Coverage
Verifier (K04) must do fresh flash of each stream; PR provider needs:
- Zero-flow handling (dormant test)
- Single-component tests (NH₃-only liquid)
- All-vapour tests (H₂/N₂/Ar/CH₄ mix)
- Domain-edge tests (Tc, Pc for each component from open sources)

---

## Not Found

1. **Dissolved-gas route (full PR VLE)**: Not found. R-143 records as limitation: "dissolved light gases are a v0.2 limitation the dossier states." M01 is pure NH₃ liquid only.

2. **CoolProp/Cantera as dependency**: Not present in `pyproject.toml`. M01 must either ship PR code (recommended) or add external dependency (policy decision).

3. **Grey-box/external unit hook**: Not found. ADR 0008 references future; v0.0 forbids opaque evaluators. Any reactor model must be native (native equations + evaluator).

4. **Existing PR implementation**: Not found. M01 starts from derivation; no prior implementation in the codebase to port.

5. **Reaction datum for non-SYN-001 providers**: Not found. ADR 0011 D2 registers `{"SYN-001-ref-v1"}` only; extending requires new ADR. M01 must propose its own datum.

---

**Digest compiled 2026-10-06 from:**
- Code: `src/openflowsheet/thermo/__init__.py`, `cache.py`, `syn001.py`; `models/syn001/*.py`; `verify/__init__.py`
- Specs: `docs/adr/0001`, `0005`, `0011`, `0012`, `0017`; `docs/decision-register.md` (R-120, R-143, R-152, R-153)
- Tests: `tests/test_k02_syn001_provider.py`, `test_k02_heater_flash.py`
- Schema: `schemas/component-record.schema.json`; `benchmarks/registry.yaml`
