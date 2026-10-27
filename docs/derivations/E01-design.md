# E01 design: cost estimation and life-cycle assessment as differentiable assessment functionals

**Status:** design lane (`architect`), 2026-10-27. Branch `wp/E01` from `main` `5c8f6006`; built after S11 merges.
**Brief:** `docs/briefs/E01-cost-lca-design.md`. **Records:** ADR 0052 (`docs/adr/0052-e01-assessment-functionals.md`,
Proposed); register R-850…R-862.
**Normative for:** where cost and impact live and how they are differentiated; the assessment document, program,
regimes and report; the sizing model of every day-one unit family; the cost-provider forms, data sets, quotes and
provenance; the cost basis (index, currency, location); operating cost and annualisation; the LCA formulation, its
Brightway adapter and the data-rights policy; how a study names a cost or impact quantity; the verification; the
identity statement; two parallel build tracks. Everything here stands alone; the brief is not needed to implement it.

---

## 0. The decisions in one screen

1. **Cost and impact are explicit post-solve functionals `y = G(x, d; θ, ρ)` of a verified state, never rows of a
   `CompiledProblem`.** The simulation, its certificate and its replay identity do not change when an assessment is
   attached. An optimizer sees `y` and `∂y/∂(x, d)` exactly, as gray-box **outputs** of the existing NLP adapter. (§3 D1)
2. **One source, the existing compiler.** Every functional is a `RowBuilder` written against the `Algebra` protocol
   (`exp`, `log`, `sqrt`, operator overloading). A set of functionals is compiled as a `ProblemSpec` whose rows are the
   outputs, through the unchanged `ParametricTwin` (value, `∂/∂x`, `∂/∂p` from one graph). `compile/reference.py`
   evaluates the same builders on floats. No file under `compile/` changes. (D2)
3. **Non-smooth choices are held regimes, never smoothed.** Parallel units, minimum size, correlation pieces, the
   heating/cooling service, the utility, the controlling column stage and the drum's controlling dimension are each a
   discrete *regime*. It is selected by a stated rule at a state. A study holds it and imposes its admissibility
   inequalities. Inside its admissible set every regime is the true cost of a realisable design, so no gradient lies.
   (D3, §4.3)
4. **ΔT_lm is Underwood's cube-root mean.** Its deviation from the exact log mean is +0.0035 % at ratio 2, +0.38 % at 10
   and +2.56 % at 50. It is smooth and glass-box everywhere ΔT > 0, including ΔT₁ = ΔT₂, where the exact form is 0/0.
   (D4)
5. **Correlation forms are code; coefficients are data with provenance.** Shipped sets: `sslw-idaes-v1` (Seider et
   al. 3rd ed. coefficients, transcribed from IDAES's BSD-licensed `SSLW.py`) and the `power-law-v1` form for user
   data and quotes. Turton is not shipped; a user may register it. A quote overrides one item. (D5)
6. **Public cost indices only.** BLS PPI WPU11 (USD) and Eurostat PPI NACE C28 (EUR) are shipped as annual series.
   Federal Reserve G.5A annual exchange rates are shipped. CEPCI values are never shipped, but a user may supply them.
   The order is: escalate in the source currency, then convert at the target year's rate, then apply the location
   factor. (D6)
7. **LCA is linear in the boundary inventory: `h = Q·a(x) + C·b(x)`.** `Q` is a frozen unit-score table that the
   Brightway adapter (optional extra `lca`) computes offline. Brightway never runs inside a solve, an optimization or a
   replay. (D7)
8. **Data rights.** Shipped: the IPCC AR6 GWP100 direct-emission factors and a synthetic test background. A USLCI
   GWP100 table ships only if its CC0/public-domain licence is recorded. EF 3.1 factors and anything derived from
   ecoinvent are never shipped. A table whose rights forbid redistribution enters bundles and fixtures by hash only.
   (D8)
9. **Studies name `assessment:<output_id>`.** The name can appear in M03 NLP objectives and constraints and in
   sensitivity outputs. The Study and OptimizationReport schemas gain one optional `assessment` property each (additive),
   and there are two new schemas. The trust-region study, a revision-flowsheet NLP host and the CLI/HTTP/MCP bindings
   are deferred with typed refusals. (D9, D10)
10. **Identity.** No file under `compile/`, `thermo/`, `models/`, `verify/`, `orchestrator/`, `numerics/`,
    `application/` changes, and no registered result moves. The M03 adapter's edits are inert when no assessment
    output is named, as proved by the M03 fixtures being bit-identical. (§4.14)

---

## 1. Problem and scope

**Build:** capital cost, operating cost, annualised cost and life-cycle impact as first-class, exactly differentiable
quantities of a solved flowsheet. They must be usable (a) as a report, (b) as sensitivities with respect to pinned
inputs and assessment parameters, and (c) as objective or constraint of the M03 NLP. They carry provenance, an accuracy
class and an uncertainty statement (blueprint §10: "TEA/LCA remain assessment adapters with currency year, location,
factors, uncertainty, and provenance"; D14: assessment evidence is distinct from verification and validation).

**Day-one unit families** (§4.4): one-sided utility exchangers (`thermal.heater`, `syn001.tp_heater`, the C1 TP
heater), the two-stream `syn001.heat_exchanger`, flash drums (`thermal.flash`, `syn001.tp_flash`, `syn001.ph_flash`,
the C1 flash), pumps, compressors and turbines (`thermal.*`, `syn001.pump`), the distillation column (`syn001.column`:
shell, trays, condenser, reboiler) and the two SYN-001 reactors as vessels. Valves, mixers, splitters, feeds and sinks
carry no equipment. Feeds and sinks are the material and inventory boundary.

**Out of scope:**
- vendor-grade estimating, cash-flow schedules beyond a constant-annuity model, taxes and depreciation schedules;
- Monte Carlo uncertainty (first-order propagation only, §4.9);
- dynamic or cyclic units (PrISMa's package);
- the PrISMa case itself;
- fired heaters, refrigeration cycles as equipment (a refrigerant is a cooling utility with a price);
- capital goods in the LCA foreground;
- the trust-region study, an NLP host over revision flowsheets, and the CLI/HTTP/MCP bindings (§4.10.4, §7 Q1–Q3);
- optimization over discrete regimes (an outer enumeration; §7 Q4);
- GUI.

---

## 2. Constraints and invariants

### 2.1 Conventions

- **Units.** SI internally (ADR 0001 D1): K, Pa, m, m², m³, s, W, J, mol, kg. Absolute pressure. Money is in the
  assessment's basis currency at its basis year, in real terms; the discount rate is real. Annual quantities =
  rate (per s) × 3600 × `hours_per_year`. Assessment documents are SI-only for physical quantities. Prices carry a `per`
  unit from the closed table of §4.5.6.
- **Signs.** Heat and shaft work are positive into the unit (ADR 0001 D4.1). Heating utility energy = `+Q` (Q > 0),
  cooling utility energy = `−Q` (Q < 0). Electricity consumed = `W/η_drive` for pumps and compressors. Electricity
  generated = `−W·η_gen` for a turbine (W < 0). Inventory amounts are positive for consumption and for emission to the
  environment, and negative for avoided (substituted) products.
- **Precision.** binary64 throughout. Sums are formed in a fixed construction order (the order of §4.2.4), never by dict
  iteration.
- **Correlation units.** A correlation in non-SI units converts its size argument inside the form with exact constants:
  1 ft = 0.3048 m; 1 lb = 0.45359237 kg; 1 US gal = 3.785411784e-3 m³; 1 psi = 6894.757293168361 Pa;
  1 hp (mechanical) = 745.6998715822702 W; g = 9.80665 m/s²; gauge pressure = P − 101325 Pa.

### 2.2 Bit-exact and tolerances

- **Bit-exact:** every registered result, fixture and hash on `main` (G1); the M03 optimization fixtures with no
  assessment named (G9); a sensitivity request with no assessment output (it never enters the wrapper of §4.10.1).
- **Within stated tolerances:** the program's CasADi value against its float reference (rel 1e-13); gradients against
  a finite-difference oracle (§6); hand-calculated and independently implemented expectations (§6).

### 2.3 Frozen interfaces

The `Protocol`s `CompiledProblem`, `PropertyProvider`, `Application`, the quantity kinds, check categories and
tolerances do not change. **The schema list changes:** two new schemas, plus one additive optional property in each of
`study.schema.json` and `optimization-report.schema.json` (ADR 0052 D8; `docs/interfaces-frozen.md` gains a note). No
existing document becomes invalid.

### 2.4 Evidence classes (D14)

An assessment report is *assessment evidence*. It is not numerical verification and not empirical validation. Every
report states its accuracy class, its uncertainty, its defaulted inputs and its limitations. Correctness of the code is
established only against hand calculations, independent implementations and an independent Brightway calculation,
never against its own output (CLAUDE.md "Scientific conduct").

### 2.5 Parallel and device contract

None. Single process, deterministic, CPU. Compiled programs are cached per process (§4.13).

---

## 3. Decisions and rejected alternatives

**D1. Post-solve functionals, not model rows.** An assessment output is an explicit function of the solved state `x`,
the pinned inputs and decisions `d`, the assessment parameters `θ` and the held regime `ρ`. Every sizing relation needed
(area from duty and ΔT, diameter from vapour load, volume from residence time, cost from size) is explicit in a solved
state, so no implicit equation is needed.
- *In the NLP* (full space), `y = G(z)` with `z = (x, d)` becomes PyNumero gray-box outputs. PyNumero adds
  `y − G(z) = 0` to the NLP with the exact Jacobian `∂G/∂z`, and the Pyomo objective and constraints stay linear or
  quadratic in named quantities. For the optimizer the outputs *are* in-problem quantities with exact derivatives. For
  the simulation they do not exist.
- *In reduced space* (sensitivity, M03's V5), `dJ/dp = ∂J/∂p + ∇ₓJ · X` with `F_x X = −F_p` (forward), or one transposed
  solve per output (adjoint). This is M03's machinery with `∇ₓJ(x*)` in place of a linear output row (§4.10.1).

*Rejected: cost and impact as variables with rows in F.*
- It changes `model_version`, `constants_sha256`, the certificate scope and the replay identity of every flowsheet that
  carries an assessment.
- A log of a non-positive area during a *simulation's* Newton iteration would fail simulations that are physically
  fine.
- Regime selections inside F would break K04's regularity assumptions.
- Re-costing at another year, location or database would need a new revision and a re-solve.
- A certificate would appear to verify cost equations, conflating assessment with verification (D14).

*Rejected: appending `y − G = 0` to the twin's equality set inside `FullSpaceNlp`.* The mathematics is identical, but
the equality set would then differ from the simulation's kept rows, which V2 and V5 compare. Gray-box outputs keep the
two apart and have their own scaling.

*Rejected: finite-difference or black-box cost gradients* (R-010).

*Rejected: IDAES or BioSTEAM costing as a dependency.* Both cost their own unit and stream models. Using either means a
second hand-authored model of the flowsheet (blueprint A06, R-003) and binds costing to their unit libraries.

*Rejected: OpenPyTEA (MIT) for the finance.* The finance is about 50 lines (CRF, annuity, factor chains), and its
functions are not algebra-generic, so they cannot give exact derivatives through CasADi.

**D2. One source compiled by the existing compiler.** The program assembles a *functional* `ProblemSpec`:
- `variable_ids` are the host spec's, in its order;
- `equations` are the outputs and admissibility rows, each an `EquationSpec` with `accumulation = "algebraic"`;
- `parameters` are the host's pinned inputs plus `θ`;
- `blocks` are the volumetric-flow blocks the sizing needs.

`ParametricTwin(functional_spec, symbolic_ids)` gives `residual` (= the output values), `jacobian_x` and `jacobian_p`
from one graph. `reference.row_values` gives the float path. The functional spec is never handed to a solver or a
certificate: `AssessmentProgram` holds it privately and exposes no `CompiledProblem`.

*Rejected: a new `FunctionalSpec` type and a compile entry point.* That edits the compiler (ADR 0003 D5.7 territory) to
gain nothing the twin does not already provide.

*Rejected: a separate symbolic layer for costing* (sympy, or a hand-written AD). It is a second derivative path that
would have to be kept consistent with the first.

**D3. Regimes with admissibility, never smoothing.** Detail in §4.3. The project already treats phase this way
(declared regimes, verified at the candidate).

*Rejected: `max`, `min`, `abs` or `ceil` in a functional.* `Algebra` has none, and adding one adds a kink.

*Rejected: softplus or p-norm smoothing.* It changes the value (a positive bias up to ε ln 2) and gives gradients of a
function that is not the cost.

*Rejected: the epigraph reformulation* (an auxiliary variable `D ≥ D_j`). It adds assessment-only decision variables to
the NLP, and it is exact only when the objective is monotone in the auxiliary variable, a property the code would have
to prove per study.

*Rejected: refusing every out-of-range size.* Parallel units and minimum-size units are what a cost engineer does, and
they are exact designs.

**D4. Underwood's ΔT_lm.** `ΔT_lm ≈ ((ΔT₁^{1/3} + ΔT₂^{1/3})/2)³`.

*Rejected: the exact log mean as an opaque `PropertyBlock`* with an internal series branch near ΔT₁ = ΔT₂. It would be
exact to machine precision, but it adds an opaque evaluator per exchanger. It would also become a trust-region
`ExternalFunction` (a surrogate-modelled black box) in the deferred TR follow-up.

*Rejected: Chen's approximation* (−2.70 % at ratio 10). *Rejected: Paterson's approximation* (+0.84 % at ratio 10).

*Rejected: a two-piece exact or series form as a regime.* It would constrain the process temperature ratio for a purely
numerical reason.

Underwood's error is two orders below a class-4 estimate's range. The report states each exchanger's ratio and its
deviation from the exact log mean.

**D5. Forms in code, coefficients in data.**
- Forms: `log-polynomial-v1`, `power-law-v1` and the factor terms (§4.5).
- Data: `sslw-idaes-v1`, transcribed from IDAES-PSE's `idaes/models/costing/SSLW.py` at a pinned release. IDAES uses a
  BSD-style licence; the notice is retained. The coefficients are Seider, Seader, Lewin & Widagdo, *Product and Process
  Design Principles*, 3rd ed., ch. 22, on a CE-index-500 basis.
- `power-law-v1` (`C = C_ref (S/S_ref)^n`) carries user data: Woods bare-module costs, Aspen ACCE base costs the user
  licenses, vendor quotes.

*Rejected: shipping Turton/CAPCOST coefficients.* Their redistribution rights are not established, and a user can
register them as data (§7 Q8).

*Rejected: hard-coding coefficients in Python.* Provenance per coefficient is then unauditable.

**D6. Public indices; escalate, then convert, then locate** (§4.6). CEPCI is owned by *Chemical Engineering* magazine.
Its values are never shipped, but a user who holds them can supply them as a user series. The order follows where the
price change happens (the quoting region) and when money is spent (the target year).

*Rejected: convert first, then escalate with the target region's index.* That attributes the source region's price
movement to the target region.

**D7. LCA as a frozen linear map.** The foreground is the flowsheet. Each boundary flow `a_k(x)` (feed, utility,
waste, co-product) links to a background activity `k` whose characterised unit score `q_{m,k}` is a constant. Direct
emissions `b_e(x)` are characterised by `c_{m,e}`. Hence `h_m(x) = Σ_k q_{m,k} a_k(x) + Σ_e c_{m,e} b_e(x)`, which is
linear in flows, duties and work, with exact derivatives. Brightway computes `Q` offline from the user's project
(`q = c^T B A⁻¹ e_k`).

*Rejected: Brightway in the loop.* `A⁻¹` is constant, so per-evaluation LCA solves are pure waste, and Brightway would
become a runtime dependency of optimization and replay.

*Rejected: openLCA over IPC.* It needs an external Java server.

*Rejected: our own matrix LCA over imported databases.* That re-implements Brightway's database handling (D01: reuse).

**D8. Rights.**
- The EF 3.1 method report (Andreasi Bassi et al., JRC130796, 2023) is published under CC BY 4.0, by the Commission
  reuse policy (Decision 2011/833/EU). The factor workbook at
  `https://eplca.jrc.ec.europa.eu/permalink/EF3_1/EF-LCIAMethod_CF(EF-v3.1).xlsx` has terms this design could not
  confirm, and using it needs flow mapping.
- Hence no EF factors ship in E01. EF 3.x enters through the user's Brightway method (§7 Q5).
- ecoinvent is licensed per user. Tables derived from it are `redistribution: forbidden` by default.

**D9. Studies name assessment outputs.** The NLP's `QuadraticExpression` and the sensitivity's `OutputFunctional`
keys may be `assessment:<output_id>`. The schemas gain one optional `assessment` property each.

*Rejected: a new study kind.* It duplicates M03's closure and verification.

*Rejected: a general expression language in the study.* Ratios that a user needs are `derived` outputs of the
assessment (§4.7.5).

**D10. Scope cuts with typed refusals.**
- Trust-region: `UNSUPPORTED(ASSESSMENT_OUTPUT_IN_TRF)`.
- An NLP over revision flowsheets is not built here; the existing host is SYN-001's `FullSpaceNlp`.
- The bindings (CLI, HTTP, MCP) are not built here.

The functionals are host-agnostic, so each follow-up only wires an existing host. Defaults and rationale are in §7.

---

## 4. The design

### 4.1 Objects, identities and names

| Object | Where | Identity |
| --- | --- | --- |
| `AssessmentSpec` (document, `schemas/assessment.schema.json`) | user/project file | `assessment_sha256` = canonical JSON hash (`canonical.py`) of the document. Every referenced data file (correlation set, index series, exchange rates, LCA tables) is named by `{id, sha256}` inside it, so the hash covers data content |
| `AssessmentProgram` | `assessment/program.py` | (`assessment_sha256`, host `structure`/label, regime signature) |
| `Regime` | `assessment/regimes.py` | `regime_signature` = canonical JSON of the sorted entries `{entry_id: choice}`; `regime_sha256` its hash |
| `AssessmentReport` (`schemas/assessment-report.schema.json`) | output | contains `assessment_sha256`, `state_sha256` of the evaluated `x`, `regime_sha256` |

**Output ids** (inside the report, unprefixed; in a study, prefixed `assessment:`). `<item>` is the item id (§4.4.0);
`<u>` a utility id; `<s>` a boundary connection id; `<m>` an impact category id.

| Id | Unit | Meaning |
| --- | --- | --- |
| `size.<item>.<q>` | SI of `q` | sizing quantities: `area`, `volume`, `diameter`, `height`, `power`, `vol_flow`, `head`, `n_parallel` (a constant) |
| `capex.purchased.<item>`, `capex.bare_module.<item>` | currency | per item, escalated to the basis |
| `capex.sum_purchased`, `capex.sum_bare_module` | currency | Σ over costed items |
| `capex.<step>` | currency | each capital-chain step (§4.7.1); `capex.total` aliases the chain's declared `capital_total`; `capex.fci` its declared `fci` |
| `opex.utility.<u>`, `opex.material.<s>`, `opex.waste.<s>`, `opex.fixed.<line>`, `opex.total` | currency/yr | `opex.total` = utilities + raw materials + waste + fixed (revenue excluded) |
| `revenue.<s>`, `revenue.total` | currency/yr | products and co-products with a price |
| `annual.capital_charge` | currency/yr | `CRF · capex.total` |
| `tac` | currency/yr | `annual.capital_charge + opex.total` |
| `profit` | currency/yr | `revenue.total − tac` |
| `product.annual` | kg/yr (or mol/yr) | functional-unit amount per year, if a functional unit is declared |
| `lcox` | currency/kg | `tac / product.annual` |
| `inventory.<k>.rate` | activity unit/s or kg/s | each foreground exchange `a_k` or `b_e` |
| `impact.<m>.rate`, `impact.<m>.annual`, `impact.<m>.per_fu` | category unit /s, /yr, /FU | §4.8 |
| `derived.<id>` | declared | §4.7.5 |
| `adm.<entry>.<k>` | dimensionless | admissibility rows (§4.3); ≥ 0 required; not user objectives |

The WO-A1 test asserts that no host variable id starts with `assessment:`. Variable ids use dots, as in
`models.flow_id`.

### 4.2 The functional program

#### 4.2.1 API (pseudocode; names binding)

```python
class FlowsheetView(Protocol):            # assessment/views.py
    components: tuple[str, ...]
    provider: PropertyProvider
    context: EvaluationContext
    def units(self) -> tuple[UnitRef, ...]          # UnitRef(unit_id, model_id, ports: {port: (stream ids)},
                                                    #         parameters: {name: float}, structure: Any)
    def molar_masses(self) -> Mapping[str, float]   # kg/mol, from the bound basis's component records
def view_of(flowsheet: RevisionFlowsheet | Syn001Flowsheet) -> FlowsheetView

class AssessmentProgram:                  # assessment/program.py
    @classmethod
    def build(cls, view: FlowsheetView, host_spec: ProblemSpec, spec: AssessmentSpec,
              state: Mapping[str, float], regime: Regime | None = None) -> "AssessmentProgram | Refusal"
    output_ids: tuple[str, ...]           # catalogue order, then admissibility rows
    regime: Regime
    theta: Mapping[str, Theta]            # id -> value, unit, provenance, uncertainty, structural: bool
    def evaluate(self, x: Mapping[str, float], decisions: Mapping[str, float] = {}) -> Mapping[str, float]
        # reference path: compile/reference.row_values on the functional spec
    def twin(self, symbolic: Sequence[str]) -> ParametricTwin      # cached per symbolic tuple
    def linearize(self, x, decisions, outputs: Sequence[str], symbolic: Sequence[str] = ()) -> Linearization
        # values (twin), d_dx: TwinMatrix (outputs x host variable_ids), d_dp: TwinMatrix (outputs x symbolic)
    def select(self, x) -> Regime         # the rule of §4.3.2 (prefers self.regime where admissible)
    def report(self, x, *, state_sha256: str, uncertainty: bool = True) -> dict   # schema assessment-report
```

`build` with `regime=None` selects the regime at `state` (§4.3.2). With a regime given, it validates every admissibility
row ≥ −τ_feas at `state` and refuses `ASSESSMENT_REGIME_INADMISSIBLE` otherwise. τ_feas is M03's V3 feasibility
tolerance on scaled inequalities (M03 spec §8.5), imported from `studies/nlp/verification.py`, never redefined.

#### 4.2.2 Contributors

`program.py` defines the plug-in protocol. Track B codes against it.

```python
class Contributor(Protocol):
    name: str                                   # "cost" | "lca" | "derived"
    def plan(self, ctx: BuildContext, state: Mapping[str, float]) -> ContributionPlan
@dataclass(frozen=True)
class ContributionPlan:
    outputs: tuple[OutputDef, ...]              # OutputDef(output_id, unit, build: FunctionalBuilder)
    theta: tuple[Theta, ...]
    blocks: tuple[tuple[PropertyBlock, tuple[str, ...]], ...]   # block, its input variable ids
    regime_entries: tuple[RegimeEntry, ...]     # RegimeEntry(entry_id, choice, rule_text,
                                                #   admissibility: tuple[(row_id, FunctionalBuilder, nominal)], kind)
    refusals: tuple[Refusal, ...]               # per item/output; never raised
    limitations: tuple[Limitation, ...]
    section: Callable[[Mapping[str, float]], dict]   # its report section from evaluated values
```

`FunctionalBuilder = Callable[[Symbols, Algebra], Expr]`. `Symbols` gives `x(id)`, `theta(id)`, `pin(id)`,
`block(block_id, output_id)` and `out(output_id)`. `out` is an earlier output's expression, so the DAG is shared.

`BuildContext` carries the view, the host spec, the `AssessmentSpec` and the **regime as data**. Builders never branch
on a symbol: a choice is made in the selection pass from float values and passed in.

Contributors run in the order `cost`, `lca`, `derived`. `derived` may reference any earlier output id.

#### 4.2.3 Compiling

- The functional spec's label is `ASM1-<assessment_sha256[:12]>-<regime_sha256[:8]>`.
- Each output becomes one `EquationSpec(equation_id=output_id, build=<closure>, accumulation="algebraic",
  origin="assessment:<contributor>")`. The closure adapts `RowBuilder`'s `(variables, blocks, pins, algebra)` arguments
  into `Symbols`.
- **Sub-expression memo.** Within one build pass, `out(id)` returns the expression already built, keyed by the identity
  of the `variables` mapping object.
  - WO-A1 verifies that `ParametricTwin._builds` (`casadi_backend.py:774`) and `reference.row_values` pass one mapping
    object to every row of a pass.
  - If they do not, the memo is disabled (correct, slower), and the compile and evaluation times are recorded in
    `docs/E01A_DECISIONS.md`.
- **θ ids** are `asm:<path>`, for example `asm:item.E-101.U`, `asm:utility.LPS.price`, `asm:lca.q.<table>.<m>.<k>`.
  A θ marked `structural` (integers, materials, `E_o`, anything that selects a regime) is never symbolic. Requesting it
  symbolic is refused `ASSESSMENT_PARAMETER_STRUCTURAL`.
- **Domain.** A non-finite value or a block `DomainError` surfaces as `TwinEvaluationError`, which is an evaluation
  error, never NaN in a report. Examples: log of a non-positive size, a cube root of a negative ΔT.

#### 4.2.4 Construction order (fixes summation order)

1. Items, in the host's unit declaration order, then each unit's items in the order of §4.4.
2. Utilities, in document order.
3. Materials, in document order.
4. Capital-chain steps.
5. Fixed-OPEX lines.
6. LCA exchanges, in document order.
7. Derived outputs.

Each sum is a left fold in this order.

### 4.3 Regimes

#### 4.3.1 Entry kinds

| Kind | Entry | Choices | Admissibility rows (each `a/nominal ≥ 0`) |
| --- | --- | --- | --- |
| `service` | `<item>.service` | `heating`, `cooling` | heating: `Q`; cooling: `−Q` |
| `utility` | `<item>.utility` | a utility id | `ΔT₁ − ΔT_min,u`, `ΔT₂ − ΔT_min,u` (§4.4.1) |
| `size` | `<item>.size` | `units:N` (N ≥ 1) or `floor` | `units:N`: `N·S_max − S`, `S − N·S_min`; `floor`: `S_min − S` |
| `piece` | `<item>.<factor>.piece` | piece index | `z − z_lo`, `z_hi − z` (finite sides only) |
| `argmax` | `<item>.controlling` | a member index j* | `f_{j*} − f_j` for every member j ≠ j* (squared forms, §4.4) |
| `dormant` | `<item>.<stream>.dormant` | `dormant`, `active` | none (verified post hoc, §4.10.3 V7) |

- Nominals are the absolute value of the row's leading quantity at the selection state (e.g. `S_max` for size rows).
  A zero nominal is replaced by the quantity's K03 nominal when the quantity is a host variable, else by 1.
- Admissibility rows of a square-root quantity are written squared (`D_{j*}² − D_j²`), so a dormant member never puts
  `sqrt(0)` into a derivative.

#### 4.3.2 The selection rule (deterministic)

Evaluated on floats at a state, per item, in this order:

1. **Service.** `Q > 0` → `heating`; `Q < 0` → `cooling`; `Q == 0.0` → `heating`, unless the item declares
   `service`.
2. **Utility.** Take the declared one. For `auto`: the cheapest admissible utility of the service's kind, by price per
   J (ties: document order). If none is admissible: refusal `NO_ADMISSIBLE_UTILITY(<item>)`.
3. **Dormancy.** A stream whose total flow is exactly 0.0 → `dormant`; else `active`.
4. **Size.**
   - `S < S_min` → `floor`;
   - otherwise `N = max(1, ⌈S/S_max⌉)` computed exactly as: the smallest integer N ≥ 1 with `S ≤ N·S_max`.
   - Ties: `S = N·S_max` selects N.
   - A registered set must satisfy `S_max ≥ 2 S_min` (checked at set load). This guarantees `S/N ≥ S_min` for N ≥ 2.
5. **Pieces.** Each piecewise factor: the first piece, in declared order, with `z_lo ≤ z < z_hi`; the last piece has a
   closed upper bound.
6. **Argmax.** The member j with the largest value; ties go to the lowest index.

**Holding.** `select(x)` with a held regime returns the held choice for every entry whose admissibility rows are
≥ −τ_feas at `x`, and applies the rule only to the others. This keeps a study's regime at boundaries reached within
tolerance.

**Out of overall validity in an input other than size** (for example pressure above a correlation's maximum): the item
is refused `CORRELATION_OUT_OF_RANGE(<item>.<input>)`. The exception is an item that declares
`allow_extrapolation: true`. It is then computed with limitation `CORRELATION_EXTRAPOLATED(<item>.<input>, value,
range)`, and the item's accuracy class is reported as `none`.

#### 4.3.3 Why each regime is honest

Inside its admissible set, each regime's cost is the exact cost of a realisable design:
- `units:N`: N identical units each of size S/N ∈ [S_min, S_max]; still valid if N−1 would also do (suboptimal, not
  wrong);
- `floor`: the minimum unit, bought regardless of S ≤ S_min; constant cost, derivative exactly 0;
- `piece`: the piece's formula on its interval;
- `argmax`: the true maximum.

A study holds `ρ`. A binding admissibility row means a cheaper design may exist in a neighbouring regime. The report
lists it with its multiplier under `regime_bounds_active`. Moving to the neighbour is a discrete study decision (§7 Q4).

### 4.4 Sizing models per unit family

#### 4.4.0 Items and the family registry

`assessment/sizing/__init__.py` holds `FAMILIES: Mapping[model_id, Family]` and `register_family(model_id, family)`,
the extension point for later unit packages. WO-A2 verifies every model id against the model registry and records the
port and variable names it reads (duty `models.duty_id(U)` = `U.Q`; work `models.syn001.pump.work_id(U)`; the column's
condenser and reboiler duty columns and stage variables as `syn001.column` declares them).

| Model ids | Family | Items (id) |
| --- | --- | --- |
| `thermal.heater`, `syn001.tp_heater`, C1 TP heater | `exchanger.utility` | `<U>` |
| `syn001.heat_exchanger` | `exchanger.process` | `<U>` |
| `thermal.flash`, `syn001.tp_flash`, `syn001.ph_flash`, C1 TP flash | `drum` | `<U>.drum`, plus `<U>.duty` (`exchanger.utility`) unless the duty is a pin equal to 0.0 and not a decision |
| `thermal.pump`, `syn001.pump` | `machine.pump` | `<U>`, `<U>.drive` |
| `thermal.compressor` | `machine.compressor` | `<U>`, `<U>.drive` |
| `thermal.turbine` | `machine.turbine` | `<U>` |
| `syn001.column` | `column` | `<U>.shell`, `<U>.trays`, `<U>.condenser` (if a condenser), `<U>.reboiler` (if a reboiler) |
| `syn001.kinetic_cstr` | `reactor.vessel` | `<U>.vessel` (volume = its volume parameter), plus `<U>.duty` as above |
| `syn001.conversion_reactor` | `reactor.vessel` | `<U>.vessel` (volume = `τ_R · V̇_out`; `residence_time_s` required), plus `<U>.duty` |
| valves, mixers, splitters, feeds, sinks (`thermal.valve`, `thermal.mixer`, `syn001.valve`, the SYN-001/C1 mixers, splitters, feeds, sinks) | `none` | none: listed `NO_EQUIPMENT` |
| `syn001.component_separator`, the C1 reactor, any unknown model id | `unsupported` | `<U>`: refused `NO_SIZING_MODEL(<U>)` unless it has a `quote` or `exclude` |

Every item may carry a `quote` (§4.5.4) or `exclude: {reason}`. Every item records its inputs, defaulted or not.

#### 4.4.1 `exchanger.utility`

- Process temperatures: `T_pi` = inlet T, `T_po` = outlet T (for a saturated outlet, its T = T_sat).
- Utility `u`: `T_us` (supply) and `T_ur` (return); isothermal when equal.
- Counter-current temperature differences:
  - heating: `ΔT₁ = T_us − T_po`, `ΔT₂ = T_ur − T_pi`;
  - cooling: `ΔT₁ = T_pi − T_ur`, `ΔT₂ = T_po − T_us`.
- `ΔT_lm = ((ΔT₁^{1/3} + ΔT₂^{1/3})/2)³`, written with `**(1.0/3.0)`.
- `S = area = |Q| / (U · F_T · ΔT_lm)`, with `|Q|` written as `Q` (heating) or `−Q` (cooling).
- Inputs:
  - `U` (W m⁻² K⁻¹) is **required**. It comes from the item or from `defaults.U_by_service.{heating,cooling}` in the
    document; there is no built-in value (R-856).
  - `F_T` defaults to 1.0.
  - `ΔT_min,u` is required per utility.
- Limitation `LMTD_ACROSS_PHASE_CHANGE(<item>)` when the inlet and outlet phase signatures differ. Report: ratio
  `r = max/min(ΔT₁, ΔT₂)` and `Underwood/LMTD − 1`, computed on floats for information.

#### 4.4.2 `exchanger.process`

- `ΔT₁ = T_h,in − T_c,out`, `ΔT₂ = T_h,out − T_c,in`.
- `Q` = the unit's duty variable; Underwood as above.
- `S = area = Q/(U F_T ΔT_lm)`.
- `U` and `ΔT_min` are required per item.
- Admissibility: `ΔT₁ − ΔT_min ≥ 0`, `ΔT₂ − ΔT_min ≥ 0` (entry kind `utility`-like, entry id `<item>.approach`, a
  single choice).

#### 4.4.3 Volumetric flows (`assessment/blocks.py`)

`VolumetricFlowBlock(stream, phase)` is a `PropertyBlock`.
- Single-phase stream: inputs `(n_1…n_C, T, P)`; output `V̇ = Σn · v^φ(T, P, n)` from `provider.evaluate_phase(…,
  properties=("v",), derivatives=…)`.
- Saturated pure-fluid stream: `V̇ = V·v^V_sat(P) + L·v^L_sat(P)`, from the S11 saturation routine. WO-A2 names it: in
  `models/thermal/kernel.py`, or the provider's saturation properties. A missing derivative is refusal
  `SIZING_INPUT_UNAVAILABLE(<item>.v_sat)`, not an approximation.
- A provider that does not offer `v` for the phase is refusal `SIZING_INPUT_UNAVAILABLE(<item>.v)`. Example: the
  Wilson liquid; S11 records that "the method's liquid has no volume". The exception is an item that declares
  `liquid_molar_volume` (m³/mol, a θ), used as `V̇ = Σn · v_decl`.
- The derivatives come from the provider's own derivative outputs and are declared sparse.
- A dormant stream (`dormant` regime) has no block: its V̇ is the constant 0.
- Mass flow `ṁ = Σ M_c n_c`. Mean molar mass `M̄ = ṁ/Σn`. Density `ρ = M̄/v`.

#### 4.4.4 `drum` (vertical by default)

```
V̇_L = liquid product volumetric flow;  V̇_V = vapour product volumetric flow
V   = τ · V̇_L / φ_fill                                        (vessel volume, m³)
D_L² = (4 V / (π · LD))^{2/3}                                 (liquid-controlled diameter², LD = L/D)
u_V  = K_SB · sqrt((ρ_L − ρ_V)/ρ_V)                           (Souders–Brown)
D_V² = 4 V̇_V / (π u_V)                                        (vapour-controlled diameter²)
argmax regime over {L: D_L², V: D_V²};  D = sqrt(D_{j*}²);  height L = LD · D
```
- Defaults (each reported if used): `τ = 300 s`, `φ_fill = 0.5`, `LD = 3`, `K_SB = 0.07 m/s`.
- Orientation `horizontal` uses the same D and L with the set's horizontal-vessel entry.
- A dormant vapour product removes the `V` member (no admissibility row).
- A dormant liquid product gives `V = 0` and the `floor` regime, but `ρ_L` is then undefined. The `V` member is
  therefore refused `SIZING_INPUT_UNAVAILABLE(<item>.rho_L)`, unless the item declares `liquid_molar_volume`.
- Design pressure input = inlet pressure (the maximum by construction, since ΔP ≥ 0).

#### 4.4.5 Machines

- Pump and compressor: `power = W` (shaft, > 0).
- Turbine: `power = −W`.
- Pump extras: `vol_flow = V̇_in`, `head = (P_out − P_in) · v_in/(M̄_in g)`.
- Each set entry names the size quantity it uses (e.g. SSLW's centrifugal pump uses `vol_flow·head^{0.5}` in
  gpm·ft^{0.5}).
- Drive (`<U>.drive`): consumed power `W/η_drive`. `η_drive` comes from the set's motor-efficiency correlation if the
  set defines one, else `defaults.drive_efficiency` = 0.95. It is costed by the set's motor entry; absent → the drive is
  refused `NO_CORRELATION(<U>.drive)`.
- Turbine generation `−W·η_gen`, with `η_gen` = `defaults.generator_efficiency` = 0.95. No generator equipment is
  costed: limitation `GENERATOR_NOT_COSTED`.

#### 4.4.6 `column`

Stage convention (S02):
- stage 1 is the condenser if the condenser kind ≠ `none`; stage N is the reboiler if the reboiler kind ≠ `none`;
- trays: `N_tr = N − [condenser] − [reboiler]` (structural);
- `N_act = ⌈N_tr / E_o⌉`, computed at build time; `E_o` is structural.

```
for each tray stage j with active vapour V_j > 0:
  V̇_j = V_j · v^V_j ;  ρ_V,j = M̄_V,j / v^V_j ;  ρ_L,j = M̄_L,j / v^L_j     (stage vapour and liquid leaving j)
  u_f,j = C_SB · sqrt((ρ_L,j − ρ_V,j)/ρ_V,j)
  D_j²  = 4 V̇_j / (π · f_flood · φ_active · u_f,j)
argmax regime over trays (j* = largest D_j², ties lowest j);  D = sqrt(D_{j*}²)
H = (N_act − 1) · s_tray + H_top + H_bottom
```
- Defaults: `C_SB = 0.09 m/s`, `f_flood = 0.80`, `φ_active = 0.85`, `s_tray = 0.6096 m`, `E_o = 0.70`,
  `H_top = 1.2192 m`, `H_bottom = 3.048 m`.
- Design pressure = the maximum of the `stage_pressure.<j>` instance parameters (constants).
- Shell = the set's vertical-vessel entry at (D, H, P_design, material). Trays = the set's tray entry at
  (N_act, D, tray type, material).
- Condenser = `exchanger.utility` with cooling service, `Q` = the condenser duty, `T_pi` = the T of stage 2,
  `T_po` = the T of stage 1.
- Reboiler = `exchanger.utility` with heating service, `Q` = the reboiler duty, `T_pi` = the T of stage N−1,
  `T_po` = the T of stage N.
- A column with a `top` (`bottom`) inlet has no condenser (reboiler) item.
- Limitation: `COLUMN_AUXILIARIES_NOT_COSTED` (reflux drum and pumps).

#### 4.4.7 `reactor.vessel`

- `V` as in §4.4.0. `D = (4V/(π LD))^{1/3}`, `L = LD·D`, `LD` = `defaults.reactor_LD` = 3.
- Vertical-vessel entry; design pressure = inlet P.
- The duty item, if present, is `exchanger.utility` with `T_pi = T_po` = the reactor outlet T (isothermal process
  side; limitation `JACKET_AS_EXCHANGER`).

### 4.5 Cost providers

#### 4.5.1 Forms (`assessment/cost/forms.py`)

- `log-polynomial-v1`: `C_base(S) = B^{Σ_{i=0}^{m} a_i (log_B S')^i}`, with `B ∈ {e, 10}` declared and
  `S' = S · κ` (κ the declared exact unit factor, §2.1).
  - It is written `exp(ln(B) · Σ a_i (ln S'/ln B)^i)`, with `ln 10 = 2.302585092994046` as a binary64 constant.
  - Coefficients are stored exactly as the source prints them; never converted between bases.
- `power-law-v1`: `C_base(S) = C_ref · (S/S_ref)^n`, written `C_ref · exp(n · ln(S/S_ref))`.
- `constant-v1`: `C_base = C` (a quote without scaling).
- **Factor terms** multiply `C_base` in declared order:
  - `material`: F_M constant per material; a structural θ selects it.
  - `pressure`: a piecewise `log-polynomial` in the gauge design pressure (pieces → regime) or SSLW's
    vessel-weight method.
  - `type`: F_T constant per subtype.
  - `count`: a function of N_act for trays (constant).
- **Purchased cost** of one unit `C_P1 = C_base · Π factors`. Per item `C_P = N · C_P1(S/N)` (`units:N`) or
  `C_P1(S_min)` (`floor`).
- **Bare module:**
  - `C_BM = F_BM · C_P` if the entry or the item gives a constant `F_BM`;
  - else `C_BM = C_base · (B1 + B2·F_M·F_P)` for a set using that form;
  - else the item has no bare-module cost (`BARE_MODULE_FACTOR_MISSING(<item>)`). A chain that references
    `sum_bare_module` is then refused, while a chain on `sum_purchased` still works.
- **SSLW vessels.** Cost by shell weight per IDAES's vessel method: ASME wall thickness from design pressure,
  minimum-thickness steps by diameter, weight from D, L and t.
  - Each `max(…)` and each step is a `piece` entry with its own admissibility rows.
  - WO-A3 enumerates the pieces in the set file, each with its source line.

#### 4.5.2 Set file format (`_data/assessment/cost/<set>.json`)

```json
{"set_id": "sslw-idaes-v1", "schema": "cost-set-v1",
 "source": {"citation": "Seider, Seader, Lewin, Widagdo, Product and Process Design Principles, 3rd ed., ch. 22",
            "transcribed_from": "idaes-pse <version> idaes/models/costing/SSLW.py", "licence": "BSD-3-Clause-style (IDAES)",
            "notice": "<IDAES copyright notice, verbatim>"},
 "basis": {"currency": "USD", "index": {"series": "CEPCI", "value": 500.0},
           "year_equivalent": {"year": 2006, "note": "CE 500 ≈ 2006 annual average; mapping for public-index escalation"}},
 "accuracy_class": 4,
 "entries": [{"entry_id": "exchanger.floating_head", "family": ["exchanger.utility", "exchanger.process"],
              "size": {"quantity": "area", "unit_factor": 10.763910416709722, "native_unit": "ft2",
                       "min": 150.0, "max": 12000.0},
              "base": {"form": "log-polynomial-v1", "base": "e", "a": [ ... ], "source_line": "SSLW.py:<line>"},
              "factors": [ ... ], "bare_module": {"F_BM": ...}, "uncertainty": {"relative_range": [-0.3, 0.5]}}]}
```

`size.min`/`max` are in native units; validity in SI is `[min, max]/unit_factor`. Every number has a `source_line`.
The loader refuses a set with `max < 2·min`, a missing `source_line`, or a form it does not know.

#### 4.5.3 Correlation choice per item

- The item's `correlation: {set, entry}` if declared.
- Else the assessment's `correlation_set` and the set's first entry whose `family` list contains the item's family
  (and orientation or subtype, if declared).
- None found → `NO_CORRELATION(<item>)`.

#### 4.5.4 Quotes

```json
"quote": {"cost": 1.2e6, "currency": "EUR", "year": 2021, "location": "NL", "kind": "purchased|bare_module",
          "size": {"quantity": "area", "value": 120.0}, "exponent": 0.6,
          "source": "...", "accuracy_class": 3, "relative_range": [-0.15, 0.2]}
```

- With `exponent`: `power-law-v1` (`C_ref = cost`, `S_ref = size.value`).
- Without it: `constant-v1`. If `size` is given and `|S/S_q − 1| > 0.1` at the evaluation state, limitation
  `QUOTE_SIZE_MISMATCH(<item>)`.
- A quote replaces the item's correlation entirely, including its regime entries (no `size` regime). It is escalated by
  §4.6.

#### 4.5.5 Provenance per item (in the report)

The item records:
- set and entry, or quote;
- source citation and `source_line`s;
- basis (currency, index basis or year);
- escalation factor and its parts;
- location factor;
- accuracy class;
- relative range;
- the regime choices;
- every input with `defaulted: bool`.

#### 4.5.6 Price units (`per`)

Exact SI factors:
- energy: `J` 1, `kJ` 1e3, `MJ` 1e6, `GJ` 1e9, `kWh` 3.6e6, `MWh` 3.6e9;
- mass: `kg` 1, `t` 1e3;
- amount: `mol` 1, `kmol` 1e3;
- volume: `m3` 1;
- time: `year` (a fixed line), `s`.

A price is converted to currency per SI unit by division by the factor.

### 4.6 Cost basis: index, currency, location (`assessment/cost/index.py`)

**Series file** (`_data/assessment/index/<series>.json`):
```
{series_id, publisher, title, code, frequency: "annual_average", base_note,
 values: {year: value}, licence, licence_text, retrieved, url, sha256}
```

Shipped (WO-A3 retrieves the data and records the facts):

| Series id | Content | Licence |
| --- | --- | --- |
| `bls-ppi-wpu11-annual-v1` | BLS PPI commodity WPU11 "Machinery and equipment", annual averages | US public domain (BLS states site material is public domain; citation requested) |
| `eurostat-ppi-c28-ea-annual-v1` | Eurostat producer prices in industry, domestic market, annual (`sts_inppd_a`), NACE C28, euro area | Eurostat reuse policy (CC BY 4.0) |
| `frb-g5a-annual-v1` | Federal Reserve G.5A annual average exchange rates vs USD (EUR, GBP, CHF, CNY, JPY at least) | US public domain |

**Escalation** of an item or price with basis `(cur_b, Y_b)` to the assessment basis `(cur_t, Y_t, location)`:
```
E = [I_s(Y_t) / I_s(Y_b)] · X(cur_b → cur_t, Y_t) · LF
```
- `s = basis.escalation_series[cur_b]`.
- `X` is the annual-average rate for `Y_t`, crossed through USD. X = 1 when the currencies are equal.
- `LF = basis.location_factor.value`, default 1.0, reported.
- For a set whose basis is an index value (SSLW: CEPCI 500):
  - if the user supplied a series with that `code` (CEPCI), `I_s(Y_b)` is the basis value itself;
  - otherwise the set's `year_equivalent` is used with the currency's public series, with limitation
    `INDEX_BASIS_MAPPED(<set>, CEPCI 500 → 2006)`.
- Refusals: `ESCALATION_SERIES_MISSING(<cur>)`, `INDEX_YEAR_UNAVAILABLE(<series>, <year>)`,
  `EXCHANGE_RATE_UNAVAILABLE(<cur>, <year>)`.
- Prices of utilities and materials must be stated in `(cur_t, Y_t)`, or carry `escalation_series`. Otherwise:
  `PRICE_BASIS_MISMATCH(<id>)`.
- `E` is a θ product of constants, evaluated left to right in the order written above.

### 4.7 Capital chain, operating cost, annualisation, derived outputs

#### 4.7.1 Capital chain (`assessment/cost/capital.py`)

The chain is an ordered list of steps `{name, terms: [{of, factor | factor_product}]}`:
- `name = Σ_terms (Π factor_product, left to right) · value(of)`;
- `of` ∈ {`sum_purchased`, `sum_bare_module`, an earlier step};
- plus `capital_total: <name>` (annualised) and `fci: <name>` (the base for fixed-OPEX fractions).

Presets (`_data/assessment/cost/chains.json`):
- `bare-module-total`: `TCI = sum_bare_module`; `capital_total = fci = TCI`.
- `ebtf-prisma-v1` (PrISMa SI §6.3.3, CC BY; `docs/briefs/PrISMa-scoping.md:115`):
  - `TDC = sum_bare_module` (LM as each item's F_BM);
  - `EPC = (1.10·1.14·1.30)·TDC`;
  - `CAPEX = 1.07·EPC`;
  - `capital_total = fci = CAPEX`.

  PrISMa's IDC/TCR step is the PrISMa package's to add.

#### 4.7.2 Operating cost (`assessment/cost/operating.py`)

- **Utilities.** Per utility, `opex.utility.<u> = price_u · Σ_{items using u} energy_i · 3600·h_op`.
- **Electricity.** `price_import · Σ consumption − price_export · Σ generation`. `export_price` defaults to the import
  price (netting; limitation `ELECTRICITY_NETTED`).
- **Materials.** For each `materials` entry, the mass `ṁ = Σ_c M_c n_c` (`basis: mass_total`) or `M_c n_c`
  (`component`), with the price per kg (or per mol on a molar basis):
  - raw materials → `opex.material.<s>`;
  - waste → `opex.waste.<s>`;
  - products and co-products → `revenue.<s>`.
- **Fixed lines.** `constant` (currency/yr) or `fraction_of` (a capex name). No fixed line is assumed. With none
  declared: limitation `FIXED_OPEX_UNDECLARED`.

#### 4.7.3 Annualisation

- `CRF(i, n) = i(1+i)^n / ((1+i)^n − 1)`, with `i = discount_rate` and `n = lifetime_years`.
- Domain: `i ≥ 0.001`, else `DISCOUNT_RATE_OUT_OF_DOMAIN`; `n ≥ 1`.
- Defaults (reported): `h_op = 8000 h/yr`, `n = 20`, `i = 0.08`.
- `tac = CRF·capex.total + opex.total`. With constant annual values this equals PrISMa's discounted
  `LCOC·product`, since `Σ_{y=1}^{n}(1+i)^{−y} = 1/CRF`.

#### 4.7.4 Functional unit

- `functional_unit: {connection, basis: mass_total | component | molar_total, component?}`.
- `product.annual = f(x)·3600·h_op`; `lcox = tac / product.annual`.

#### 4.7.5 Derived outputs

A derived output is a ratio of affine combinations of earlier outputs:
```
derived.<id> = (Σ α_i y_i + α_0) / (Σ β_j y_j + β_0)
```
`β` all zero means no ratio. Derived outputs may reference earlier derived outputs (acyclic, checked).

Example, PrISMa's nCAC = CCC/(1 − CC):
- `derived.cc = impact.climate_change.per_fu`;
- `derived.ncac = (ccc) / (1 − derived.cc)`.

A non-positive denominator is an evaluation error: `METRIC_UNDEFINED(<id>)`. It is never a negative "cost".

### 4.8 LCA

#### 4.8.1 Inventory (`assessment/lca/inventory.py`)

Each exchange is declared in the document (`materials[].lca`, `utilities[].lca`):

- **Technosphere:** `a_k(x) = α_k · φ_k(x)`.
  - `φ_k` is a boundary quantity in SI: a utility's energy, a stream's mass `ṁ` or component mass, electricity
    consumption or generation.
  - `α_k` is the activity amount per SI unit. The document states the amount per its own `per` unit, and the table
    activity's `si_per_unit` converts it.
  - Generation and substitution carry a negative sign.
- **Biosphere (direct emissions):** a stream with role `emission` maps each component to a flow id of a direct-factor
  table, `b_e(x) = M_c n_c` (kg/s).
- **Allocation** (applied to all `h_m` of the system):
  - `none`;
  - `substitution` (declared avoided activities, negative `a_k`);
  - `factor` (a constant θ ∈ (0, 1]);
  - `mass`: `ṁ_FU / Σ ṁ_products`;
  - `economic`: `p_FU ṁ_FU / Σ p_i ṁ_i`.

  The last two are smooth ratios; a non-positive denominator is an evaluation error.

#### 4.8.2 Tables (`assessment/lca/tables.py`)

```
unit-score-table-v1: {table_id, producer: {engine, versions…, created (outside hash)},
  background: [{database, declared_version, system_model, metadata_sha256}],
  categories: [{category_id, method: [..], unit}], activities: [{activity_id, key, name, location, unit, si_per_unit}],
  scores: [[q_{m,k}]] (categories × activities), rights: {class: open|user-licensed, licence, redistribution:
  allowed|forbidden, notice}, sha256}
direct-factor-table-v1: {table_id, categories, flows: [{flow_id, name, compartment, unit}], factors: [[c_{m,e}]],
  source, rights, sha256}
```

`sha256` is the canonical hash of the table without `created` and `sha256`. The program refuses a table whose stored
hash disagrees: `LCA_TABLE_HASH_MISMATCH`.

#### 4.8.3 Impact

- `impact.<m>.rate = A_fac · (Σ_k q_{m,k} a_k + Σ_e c_{m,e} b_e)`, with `A_fac` the allocation factor.
- `.annual = rate·3600·h_op`.
- `.per_fu = rate / f(x)`.
- `q`, `c` and `α` are θ, so `∂h/∂q = a(x)`, which gives contribution analysis for free.
- Background uncertainty is not propagated (limitation `LCA_BACKGROUND_UNCERTAINTY_NOT_PROPAGATED`). Capital goods are
  excluded from the foreground (`LCA_CAPITAL_GOODS_EXCLUDED`).

#### 4.8.4 Brightway adapter (`assessment/lca/brightway.py`, extra `lca`)

- **Dependencies.** `bw2data` and `bw2calc` only, at versions pinned after the WO-B1 audit. Not `bw2io`, and not
  `pypardiso`: bw2calc falls back to SciPy, and MKL is excluded (§7 Q11).
- **Import guard.** Without them, every adapter call returns `UNSUPPORTED(LCA_ENGINE_UNAVAILABLE)`. The core LCA path
  imports nothing from Brightway.
- `build_unit_score_table(project, activities: [(activity_id, key)], categories: [(category_id, method)], rights)
  -> table`:
  - it sets the current project;
  - computes `q_{m,k}` as the LCIA score of one unit of each activity (one LCI factorization reused across demands,
    the API per pinned version);
  - records versions and database metadata.
  - It never downloads a database: the user prepares the project (ecoinvent through their own credentials, USLCI
    through the Federal LCA Commons import).
- `build_direct_factor_table(project, method, flows)` takes the method's characterisation factors for the declared
  biosphere flows.
- `foreground_check(project, exchanges, emissions, method) -> float` is the independent check (§6, A25):
  - it writes a temporary foreground activity with these exchange amounts into a scratch database in a scratch project;
  - computes its score with Brightway;
  - deletes the scratch database.

#### 4.8.5 Shipped LCA data (`_data/assessment/lca/`)

- `gwp100-ipcc-ar6-v1.json` (direct factors, category `climate_change_gwp100_ar6`, unit kg CO2-eq):
  - `co2_fossil_air` 1.0; `co2_non_fossil_air` 0.0 (biogenic, cut-off convention, stated);
  - `ch4_fossil_air` 29.8; `ch4_non_fossil_air` 27.0;
  - `n2o_air` 273.0.
  - Source: IPCC AR6 WG1 ch. 7, Table 7.15; WO-B1 verifies each value.
- `test-background-v1.json`: a synthetic background shipped as a Brightway-importable description, plus its
  hand-derived unit-score table. Activities and units:
  - `tb.electricity` (kWh): consumes 0.25 MJ heat; emits 0.5 kg CO2 fossil;
  - `tb.heat` (MJ): consumes 0.125 kWh electricity; emits 0.0625 kg CO2 fossil and 0.001953125 kg CH4 fossil;
  - `tb.chemical_x` (kg): consumes 0.5 kWh electricity and 2 MJ heat; emits 0.25 kg CO2 fossil;
  - category `climate_change_test` with CO2 fossil 1.0 and CH4 fossil 29.8.

  Hand solution of `A s = e_k`, with `A = [[1, −0.125, −0.5], [−0.25, 1, −2], [0, 0, 1]]`:
  - `q_E = 16.965625/31 = 0.5472782258064516`;
  - `q_H = 5.8625/31 = 0.18911290322580646`;
  - `q_X = 27.9578125/31 = 0.9018649193548387`.
- `uslci-<release>-gwp100-v1.json` ships **only if** WO-B1 records the release's licence as CC0 or US public domain,
  and Brightway can import it. The curated activities: US-average electricity, natural-gas industrial heat, process
  water, and any of the C1/SYN-001 basis chemicals present. Otherwise the recipe is documented and nothing is shipped
  (§7 Q6).

#### 4.8.6 Rights enforcement

- A table with `redistribution: forbidden` is referenced by `{table_id, sha256}` in reports, bundles, fixtures and
  evidence. Its scores never leave the user's project directory.
- Test A28 asserts this on an export.
- Tables and direct factors that ship carry their licence text and notice in the file and in the D04 inventory.

### 4.9 Uncertainty and evidence statements

- **AACE class.** The estimate's class = the maximum class number over costed items (a set entry's class, or a quote's
  class). An excluded item does not count. Ranges follow AACE 18R-97:

  | Class | Low | High |
  | --- | --- | --- |
  | 5 | −20 % to −50 % | +30 % to +100 % |
  | 4 | −15 % to −30 % | +20 % to +50 % |
  | 3 | −10 % to −20 % | +10 % to +30 % |
  | 2 | −5 % to −15 % | +5 % to +20 % |
  | 1 | −3 % to −10 % | +3 % to +15 % |

  An item computed with `CORRELATION_EXTRAPOLATED` makes the class `none`.
- **First-order propagation.** Every θ with a declared `relative_range [lo, hi]` (set entries carry theirs) is
  symbolic in a twin. For each output y:
  - linear worst-case interval `y + Σ_k min/max(∂y/∂θ_k·θ_k·lo_k, ∂y/∂θ_k·θ_k·hi_k)` (fully correlated, conservative);
  - RSS standard deviation `σ_y = sqrt(Σ_k (∂y/∂θ_k·θ_k)² (hi_k − lo_k)²/12)` (independent uniform inputs).

  Both are labelled with their assumptions.
- **Statement** (verbatim in every report): "Assessment evidence: an estimate under the stated basis, correlations,
  data and regimes. It is not numerical verification of the flowsheet and not empirical validation."
- **Totals over unsupported items are not reported.** If any item is refused and not `exclude`d, every output that
  depends on it is `null`, and the report status is `PARTIAL`. An `exclude` with a reason restores the totals and lists
  the exclusion. Status values: `COMPLETE`, `PARTIAL`, `REFUSED`.

### 4.10 Study integration

#### 4.10.1 Sensitivities (`studies/assessment.py`, new)

`assessment_sensitivity(program, host, request, state, outputs: Sequence[str], certificate=None)`:
1. `lin = program.linearize(x*, decisions, outputs, symbolic=request.parameter_ids ∩ program pins)`.
2. For each output with a non-empty `d_dx` row: `OutputFunctional(output_id, coefficients = {variable_id: ∂y/∂x}
   (stored nonzeros), scale = declared)`. Then the existing `evaluate_sensitivity(host, request', state, …)` runs
   unchanged.
3. `dy/dp = (C X)_y + lin.d_dp[y, p]`. The wrapper adds the direct term; `sensitivity.py` does not change.
4. An output with an empty `d_dx` row (e.g. all items in `floor`) gets `dy/dp = d_dp` only, labelled
   `STATE_INDEPENDENT`.
5. A refusal of the underlying request propagates unchanged, with `None` values.

`revision_sensitivity_host(flowsheet: RevisionFlowsheet, state) -> SensitivityHost` is built as `studies/syn001.py:71`
`host_of` is: `spec = flowsheet.spec()`, the compiled problem, K03 scaling, and the alias rows eliminated by
`orchestrator/rank.py`'s elimination at `x*`. This gives assessment sensitivities on any certified S11 revision solve.

#### 4.10.2 The M03 NLP (`studies/nlp/formulation.py`, `greybox.py`)

- `NlpFormulation` gains `assessment: AssessmentBinding | None = None`, where
  `AssessmentBinding(program, outputs, output_scales)`.
- `QuadraticExpression.variables` may contain `assessment:<id>`. `FullSpaceNlp` splits names into state and
  assessment names and refuses an unknown name `ASSESSMENT_OUTPUT_UNKNOWN` before any solve.
- **Outputs of the gray box.** The referenced outputs, plus every admissibility row whose regime entry is in the
  dependency closure of a referenced output (computed from the twin's structural pattern), in catalogue order.
  - `evaluate_outputs` = `twin(decisions).residual(x, d)[rows]`.
  - `evaluate_jacobian_outputs` = `hstack(jacobian_x, jacobian_p)`, in canonical CSC with a fixed pattern. The same
    pattern guard as the equality Jacobian applies.
  - `get_output_constraint_scaling_factors` = 1/scale. The scale is `max(|y(x₀)|, 1)` for outputs and the row nominal
    for admissibility rows; both are recorded.
- In Pyomo:
  - the objective and constraints map `assessment:<id>` to `model.greybox.outputs[<id>]`;
  - each admissibility row becomes an inequality `outputs[adm…] ≥ 0` with constraint scaling 1;
  - output initial values are `G(x₀)`.
- With `assessment is None`, `output_names()` returns `[]` exactly as now and `build_model` is unchanged (G9).
- `optimization_readiness` adds:
  - `ASSESSMENT_REGIME_INADMISSIBLE` at the start;
  - `ASSESSMENT_OUTPUT_UNAVAILABLE` when a named output is `null` (§4.9);
  - `ASSESSMENT_PARAMETER_STRUCTURAL` when a decision is a structural θ.

  Assessment parameters are never decisions on day one: `UNSUPPORTED(ASSESSMENT_PARAMETER_DECISION)`.

#### 4.10.3 Verification (`studies/nlp/verification.py`, `closure.py`)

At `x_sim`, the re-solved certified state:
- **V3.** Admissibility rows are formulation inequalities and are checked like any declared constraint.
- **V5.** The gradient of an assessment output with respect to the decisions is `∇ₓG(x_sim)·X + ∂G/∂d`, from
  `linearize` plus M03's adjoint sensitivities: the same construction as §4.10.1.
- **V6.** Values come from `program.evaluate(x_sim)`, the float reference path.
- **V7 (new).**
  - `program.select(x_sim)` with the held regime must return the held regime. Dormancy entries are compared exactly
    (zero flow stays zero); other entries are held within τ_feas by construction.
  - On mismatch: `ASSESSMENT_REGIME_CHANGED(<entry>)` and the candidate is `NOT_VERIFIED`.
  - Status precedence: as V2.
- **Report.** `regime_bounds_active`: each admissibility row with scaled slack ≤ τ_feas, with its multiplier from V5's
  least squares.

#### 4.10.4 Trust region

`studies/trust_region/` does not change, and its objective is a registered, generated formulation
(`c1-trf-study-v1`) that names no assessment. The only route from an assessment output to a TR objective is
`studies/assessment.py: trf_objective_from_assessment(program, output_id)`. On day one it returns
`UNSUPPORTED(ASSESSMENT_OUTPUT_IN_TRF)` and nothing else (A37). It is the documented hook for the follow-up. The
builders are already algebra-generic (`PyomoAlgebra` can call them); what remains is to project the volumetric-flow
blocks as `EFHolder` outputs and register a TR formulation with an assessment objective and its own evidence (§7 Q1).

### 4.11 Schemas

- **`schemas/assessment.schema.json`** (new). Mirrors §4.1–§4.8. Top-level keys:
  - `schema_version`, `assessment_id`;
  - `applies_to {revision_id, configuration_sha256}`;
  - `basis {currency, year, location, location_factor {value, source}, escalation_series {cur: series_id},
    exchange_rates}`;
  - `operation {hours_per_year, lifetime_years, discount_rate}`;
  - `correlation_set`, `data {sets, series, tables: [{id, sha256, path}]}`, `defaults`;
  - `items {<unit_id>: {...}}`, `utilities []`, `materials []`;
  - `capital {chain | steps, capital_total, fci}`, `fixed_opex []`;
  - `lca {tables [], direct_factors [], categories [], functional_unit, allocation}`;
  - `derived []`, `uncertainty {<θ path>: {relative_range}}`.

  `additionalProperties: false` at every level.
- **`schemas/assessment-report.schema.json`** (new). Holds:
  - `assessment_sha256`, `state_sha256`, `regime {signature, sha256, entries}`, `status`;
  - `basis` (resolved), `items []` (§4.5.5), `capex {}`, `opex {}`, `annual {}`;
  - `lca {inventory [], impacts [], tables [{id, sha256, rights}]}`, `derived {}`;
  - `uncertainty {aace_class, aace_range, linear_interval {}, rss_sigma {}}`;
  - `defaulted_inputs []`, `limitations []`, `refusals []`, `excluded []`;
  - `statement`;
  - `provenance` (versions, timestamps; outside every hash).
- **`study.schema.json`** (additive): optional top-level `assessment {assessment_id, assessment_sha256,
  regime_sha256}`. `output_functional.coefficients` keys are unconstrained strings already, so `assessment:<id>` is
  valid.
- **`optimization-report.schema.json`** (additive): optional `formulation.assessment {assessment_id,
  assessment_sha256, regime_sha256, regime_entries, outputs [{id, scale}], admissibility [{id, nominal}],
  regime_bounds_active [{id, slack, multiplier}]}`. The V7 check is recorded in the existing per-start check list,
  under the name `V7`.
- `schemas/registry.json` gains the two new files. `docs/interfaces-frozen.md` gains an E01 note (§8).

### 4.12 Codes

Refusals (typed, never exceptions to the caller):
- `NO_SIZING_MODEL`, `NO_CORRELATION`, `NO_ADMISSIBLE_UTILITY`, `SIZING_INPUT_MISSING(<item>.<input>)`,
  `SIZING_INPUT_UNAVAILABLE`;
- `CORRELATION_OUT_OF_RANGE`, `BARE_MODULE_FACTOR_MISSING`;
- `ESCALATION_SERIES_MISSING`, `INDEX_YEAR_UNAVAILABLE`, `EXCHANGE_RATE_UNAVAILABLE`, `PRICE_BASIS_MISMATCH`;
- `DISCOUNT_RATE_OUT_OF_DOMAIN`, `METRIC_UNDEFINED`;
- `LCA_TABLE_HASH_MISMATCH`, `LCA_ACTIVITY_UNKNOWN`, `LCA_FLOW_UNKNOWN`;
- `ASSESSMENT_VARIABLE_UNKNOWN`, `ASSESSMENT_OUTPUT_UNKNOWN`, `ASSESSMENT_OUTPUT_UNAVAILABLE`;
- `ASSESSMENT_REGIME_INADMISSIBLE`, `ASSESSMENT_REGIME_CHANGED`, `ASSESSMENT_PARAMETER_STRUCTURAL`;
- `ASSESSMENT_EVALUATION_FAILED(<output>, message)`.

Unsupported: `ASSESSMENT_OUTPUT_IN_TRF`, `ASSESSMENT_PARAMETER_DECISION`, `LCA_ENGINE_UNAVAILABLE`.

Limitations:
- `CORRELATION_EXTRAPOLATED`, `INDEX_BASIS_MAPPED`, `QUOTE_SIZE_MISMATCH`;
- `LMTD_ACROSS_PHASE_CHANGE`, `JACKET_AS_EXCHANGER`;
- `GENERATOR_NOT_COSTED`, `COLUMN_AUXILIARIES_NOT_COSTED`;
- `ELECTRICITY_NETTED`, `FIXED_OPEX_UNDECLARED`;
- `LCA_BACKGROUND_UNCERTAINTY_NOT_PROPAGATED`, `LCA_CAPITAL_GOODS_EXCLUDED`.

### 4.13 Performance

- **Compile.** Once per (`assessment_sha256`, regime, symbolic tuple), cached in the program. It is rebuilt only when
  the regime changes (a new study iteration).
- **Evaluation** is one CasADi call: a few hundred nodes, plus the volumetric-flow blocks. Cost per evaluation:
  - 2 provider calls per drum;
  - 2 per active column tray stage;
  - 1 per pump;
  - with derivatives requested only in `linearize`.
- **Memory** is negligible.
- **Budget, measured at G6 on the S11 column case:**
  - program build and compile ≤ 2 s;
  - `evaluate` ≤ 50 ms;
  - `linearize` ≤ 200 ms.

  Exceeding them is reported in the decisions log; it is not a gate failure. The NLP iteration cost is dominated by the
  equality rows; gray-box outputs add at most one functional evaluation and one Jacobian per Ipopt evaluation.

### 4.14 The identity statement

- **No file changes** under `src/openflowsheet/{compile,thermo,models,verify,orchestrator,numerics,application,
  adapters,graph,ir,run,units,canonical.py,compiled.py,serialize.py}`, nor under `studies/trust_region/`, nor in
  `studies/sensitivity.py`, `studies/sweep.py` or `studies/estimation.py`.
- **Edited files:**
  - `studies/nlp/{formulation,greybox,verification,closure}.py` (additive, inert without an assessment);
  - `schemas/{study,optimization-report}.schema.json` (additive optional properties);
  - `schemas/registry.json`, `pyproject.toml` (extra `lca`, package data), `docs/interfaces-frozen.md`.
- **New:** `src/openflowsheet/assessment/**`, `src/openflowsheet/studies/assessment.py`,
  `src/openflowsheet/_data/assessment/**`, two schemas, tests, `benchmarks/e01/**`, docs.
- **No registered result moves (G1, G9).** If a test pins the bytes or hash of an edited schema or of
  `pyproject.toml`, it is amended on purpose, citing ADR 0052, and listed in `AMENDED_TESTS` (§8.3).

---

## 5. Work orders

### 5.1 Rules

- **Two engineers in parallel** on `wp/E01`, in two worktrees (`e01a`, `e01b`) branched from `wp/E01` after S11 has
  merged into `main` and `wp/E01` has been rebased onto it. File ownership is disjoint as listed. A file not listed is
  touched by no one; if one is needed, escalate.
- **Frank's batch-then-test.** Each WO's acceptance runs only the tests it adds. The full gate runs once, in I1.
- **Logs.** Each track logs its choices in `docs/E01A_DECISIONS.md` or `docs/E01B_DECISIONS.md` (one line each:
  question, choice, alternative, reversible-by). The design-lane ruling round is folded into the single `reviewer`
  pass.
- **Stop instead of choosing** when a choice would change a formula, a regime rule, an output id, a schema field or a
  tolerance in this note.
- **Cross-authored expectations (R-861).** Track B writes the cost expectations (WO-B4); track A writes the LCA
  expectations (WO-A5). Expectation scripts live in `benchmarks/e01/`, import nothing from `openflowsheet`, use
  `mpmath` at 30 digits, and commit their outputs as YAML with the script's sha256.
- **Agents.** At most two agents at a time (CLAUDE.md). The build lane's model choice follows the agent table.

### 5.2 Track A — core, sizing, cost (owner: engineer A)

**Owns:**
- `src/openflowsheet/assessment/{__init__,spec,views,program,regimes,quantities,blocks,report,defaults}.py`;
- `assessment/sizing/**`, `assessment/cost/**`, `src/openflowsheet/_data/assessment/{cost,index}/**`;
- `schemas/assessment.schema.json`, `schemas/assessment-report.schema.json`, `schemas/registry.json`;
- `tests/test_e01_a_*.py`, `benchmarks/e01/lca_hand/**`, `docs/E01A_DECISIONS.md`.

| WO | Content | Depends | Acceptance |
| --- | --- | --- | --- |
| **A1** core | `spec.py` (load, validate against the schema, canonical hash); `views.py` (`view_of` for `RevisionFlowsheet` and `Syn001Flowsheet`); `regimes.py` (§4.3: kinds, rule, holding, signature); `program.py` (§4.2: contributors, functional spec, memo, twin cache, `evaluate`, `linearize`, `select`); `quantities.py` (output catalogue, §4.1); `defaults.py` (every default of this note with its text); `assessment.schema.json` and its registry entry; the memo verification of §4.2.3 | S11 on main | A toy contributor (`y = x₁·x₂`, `y = exp(θ) x₁`, one `size` regime) passes A4–A8 on a SYN-001 state |
| **A2** sizing | `blocks.py` (§4.4.3) and the families of §4.4.0–§4.4.7, with their regime entries and limitations; the model-id and variable-id facts recorded | A1 | A9–A13 |
| **A3** cost data and forms | `cost/forms.py`, `cost/sets.py`; `sslw-idaes-v1.json` transcribed from the pinned IDAES release (every number with `source_line`; the IDAES notice verbatim); quotes; `cost/index.py`; the three series files retrieved, with licence text captured; D04 facts for these data files written into `docs/E01A_DECISIONS.md` for B's inventory WO | A1 | A16–A19. A14 and A15 run in I1, against WO-B4's committed YAML |
| **A4** chain, OPEX, annualisation, derived, uncertainty | `cost/capital.py` with presets; `cost/operating.py` (§4.7.2–§4.7.5); the cost contributor wiring sizing, forms, escalation, chain and OPEX; the uncertainty pass (§4.9) | A2, A3 | A20–A23 |
| **A5** report, LCA expectations | `report.py`; `assessment-report.schema.json` and its registry entry; report fixtures from real evaluations of P1 and P3; the LCA hand expectations `benchmarks/e01/lca_hand/` (P4's inventory from P1's solved state taken as recorded inputs, `test-background-v1` solved by hand in mpmath, superposition) | A4; B2's section output for the fixture | A38 (assessment schemas), A39, A40, A41 |

### 5.3 Track B — LCA, study integration, data rights (owner: engineer B)

**Owns:**
- `src/openflowsheet/assessment/lca/**`, `src/openflowsheet/_data/assessment/lca/**`;
- `src/openflowsheet/studies/assessment.py`, `studies/nlp/{formulation,greybox,verification,closure}.py`;
- `schemas/study.schema.json`, `schemas/optimization-report.schema.json`;
- `pyproject.toml` (extra `lca = [bw2data==…, bw2calc==…]`; package-data glob `_data/assessment/**/*.json`);
- the D04 dependency and data inventory files the repository uses (as S07 did for CoolProp);
- `tests/test_e01_b_*.py`, `benchmarks/e01/cost_hand/**`, `benchmarks/e01/brightway/**`, `docs/E01B_DECISIONS.md`.

| WO | Content | Depends | Acceptance |
| --- | --- | --- | --- |
| **B1** rights, extra, adapter | Licence audit: bw2data/bw2calc LICENSE files at the pinned versions; IPCC AR6 table values; USLCI release licence (CC0/US-PD or not); EF 3.1 workbook terms if reachable (record, do not ship). D04 inventory entries for every new dependency and data file (A's included, from A3's facts). The `lca` extra in an audited venv `.venv-lca` built by a script. `lca/tables.py`, `lca/brightway.py`, `gwp100-ipcc-ar6-v1.json`, `test-background-v1.json`; the conditional USLCI table | none | A24, A27, A29, A42 (B's part) |
| **B2** LCA contributor | `lca/inventory.py`, `lca/impact.py`, `lca/section.py` against A1's `Contributor` protocol (§4.2.2); allocation forms; rights enforcement (§4.8.6) | A1 | A26, A28; P4 evaluates |
| **B3** study integration | `studies/assessment.py` (§4.10.1 wrapper, revision host, TR refusal hook); NLP outputs (§4.10.2); V3/V5/V6 extension and V7 (§4.10.3); the two additive schema properties | A1 (A4 for TAC) | A30–A37, A38 (study schemas) |
| **B4** cost expectations | `benchmarks/e01/cost_hand/`: an independent transcription of the SSLW entries used by P1–P3 directly from the pinned IDAES source; mpmath evaluation at S_min, geometric mean, S_max per entry and at P1–P3's sizes (taken from the recorded solved states); the A10 exchanger case; the chain, CRF and escalation cases. `benchmarks/e01/brightway/`: IDAES cross-check values (one-off run in a scratch IDAES env, version and script hash recorded) and the Brightway `foreground_check` expectation for P4 | B1 (for the Brightway expectation) | A14/A15 YAML committed; the two transcriptions agree number for number, any disagreement is escalated |

### 5.4 Integration (one engineer, after both tracks; owns `docs/interfaces-frozen.md`, `tests/test_e01_integration.py`, the manifest)

**I1.**
- End-to-end runs:
  - P1 and P3 reports;
  - P1 sensitivities (A30, A31);
  - P2 NLP with `assessment:tac` (A33, A36), in the `nlp` env;
  - P4 against Brightway (A25), in the `lca` env.
- G1 identity, G9 M03 fixtures.
- The E01 note in `docs/interfaces-frozen.md` (§8).
- The evidence manifest, then the full `scripts/gate.sh` once and CI on both architectures.

**Configurations:**
- **P1:** a registered S11 thermal flowsheet containing at least a heater, a pump or compressor, a turbine or a
  second heater, and a `thermal.flash`. I1 names it from S11's registered cases.
- **P2:** SYN-001 (tear flowsheet, M03 host).
- **P3:** S11's registered column-in-flowsheet case.
- **P4:** P1 with an LCA section on `test-background-v1` plus `gwp100-ipcc-ar6-v1`.

---

## 6. Assertions and verification gates

### 6.1 Assertions (E01.A#)

Core and identity:
- **A1** `git diff --stat main...wp/E01` over the protected paths of §4.14 is empty.
- **A2** `scripts/s11_identity.py` (S11's recorder, unchanged) prints `PASS … changed=[]` at the E01 head against its
  `main` baseline.
- **A3** Every committed M03 optimization fixture is reproduced bit-for-bit in the `nlp` environment, with no
  assessment named.
- **A4** For every output and admissibility row of P1–P4 at their solved states:
  `|twin − reference| ≤ 1e-13 · max(1, |reference|)`.
- **A5** Gradient oracle. Central differences on the float path with `h_j = 1e-6 · max(|x_j|, S_x,j)` (and likewise
  for continuous θ, with `S_x,j` replaced by `max(|θ|, 1)`):
  `|∂y/∂x_j − FD| ≤ 1e-6 · max(|∂y/∂x_j|, |y|/S_x,j) + 1e-12/S_x,j`. This is checked for every stored nonzero and for
  20 seeded structural zeros.
- **A6** `select` twice at one state gives identical signatures. Evaluation with the held regime at its selection state
  is bitwise equal to evaluation after selection.
- **A7** Every admissibility row is ≥ 0 at its selection state. At `S = 2·S_max` exactly, `units:2` is selected.
- **A8** Compiling P1–P4 with every continuous θ symbolic raises nothing. Requesting a structural θ symbolic gives
  `ASSESSMENT_PARAMETER_STRUCTURAL`.

Sizing:
- **A9** Underwood:
  - `ΔT₁ = ΔT₂ = 10 K` → 10 K within 4 ulp;
  - ratio 10: `ΔT_lm/LMTD − 1 = 3.801e-3 ± 1e-6`;
  - ratio 50: `2.5592e-2 ± 1e-6`.
- **A10** Exchanger hand case: `Q = 1.0e6 W`, `U = 500`, `F_T = 1`, isothermal steam at 433.15 K, process
  300 → 400 K. Expected `ΔT_lm = 71.95947205233731 K` and `area = 27.79342236620868 m²` (rel 1e-13). The deviation from
  the exact LMTD of 71.92001136510889 K is reported as +5.4867e-4.
- **A11** Drum: B4's hand case on P1's flash (inputs: the recorded V̇_L, V̇_V, ρ_L, ρ_V). D, L, V and the controlling
  member match (rel 1e-12).
- **A12** Column: B4's hand case on P3 (stage vapour and liquid states recorded). Every `D_j²`, j*, D and H match
  (rel 1e-12).
- **A13** `VolumetricFlowBlock` values and derivatives are bitwise equal to `n·v` and to the provider's derivatives at
  the same state, for every provider in P1–P3.

Cost:
- **A14** Every SSLW entry used by P1–P3: our value vs B4's mpmath value at the 3 registered sizes and at the P-sizes,
  rel ≤ 1e-10.
- **A15** The same cases vs the IDAES evaluation, rel ≤ 1e-9. A larger difference is escalated to the design lane,
  never loosened.
- **A16** Escalation with target = base year and currency gives a factor of exactly 1.0. A base → target → base round
  trip is within 2 ulp.
- **A17** `S = 2.5·S_max` → `units:3` and `C_P = 3·C_P1(S/3)`, bitwise equal to the formula.
- **A18** `S = 0.5·S_min` → `floor`, `C_P = C_P1(S_min)`, and `∂C_P/∂x ≡ 0` (an empty row).
- **A19** Quote: `C = cost·E` bitwise. With an exponent: `cost·E·(S/S_q)^n` (rel 1e-15).
- **A20** `ebtf-prisma-v1`: `capex.total/capex.TDC = 1.744314` within 4 ulp.
- **A21** `CRF(0.08, 20) = 0.10185220882315059 ± 2 ulp`. `i = 0.0009` is refused.
- **A22** `tac` equals `CRF·capex.total + opex.total` computed independently from the report's own fields (rel 1e-15).
- **A23** The AACE class is the maximum over items, and the ranges equal §4.9's table. One extrapolated item →
  class `none`.

LCA:
- **A24** `build_unit_score_table` on `test-background-v1` reproduces `q_E, q_H, q_X` of §4.8.5, rel ≤ 1e-12.
- **A25** P4: our `impact.climate_change_test.rate` vs Brightway's `foreground_check` on the same exchange amounts,
  rel ≤ 1e-10. It also matches WO-A5's hand superposition (`benchmarks/e01/lca_hand/`), rel ≤ 1e-12.
- **A26** Doubling every inventory amount doubles `h` bitwise. `∂h/∂x` equals the hand-assembled `Σ_k q_k α_k ∂φ_k/∂x`
  bitwise.
- **A27** 1 kg/s CH4 fossil to air gives exactly 29.8 kg CO2-eq/s with `gwp100-ipcc-ar6-v1`.
- **A28** An assessment using a `redistribution: forbidden` table yields a report and bundle export containing that
  table's id and sha256 and none of its scores (byte search).
- **A29** Without `bw2data`/`bw2calc` importable, P4 evaluates from its tables and every adapter call returns
  `UNSUPPORTED(LCA_ENGINE_UNAVAILABLE)`.

Studies:
- **A30** P1: `d tac/d p` and `d impact/d p` for 2 pinned inputs (a heater outlet T, a pump outlet P), via the wrapper,
  vs central differences of certified re-solves (step `1e-4·s_p`): rel ≤ 1e-5.
- **A31** Forward and adjoint modes agree, rel ≤ 1e-10.
- **A32** A request with no assessment output never calls the wrapper. Its result is bitwise equal to the direct
  `evaluate_sensitivity`.
- **A33** P2 with objective `1/|tac(x₀)| · assessment:tac`, from 2 starts. The candidate passes V1–V7. `tac` at `x_sim`
  agrees with the optimizer's output within 1e-6 relative, and `tac(candidate) ≤ tac(start)`.
- **A34** The gray-box output Jacobian pattern never changes during A33's runs and equals the twin's structural
  pattern.
- **A35** With `assessment=None`, `output_names() == []`, and the Pyomo model's component list equals that of `main`.
- **A36** A constructed P2 variant whose dormant stream becomes active at `x_sim` gives V7
  `ASSESSMENT_REGIME_CHANGED` and `NOT_VERIFIED`.
- **A37** Naming an assessment output for a TR study → `UNSUPPORTED(ASSESSMENT_OUTPUT_IN_TRF)` before any solve.

Schemas, reports, rights:
- **A38** Fixtures emitted by real runs validate against the new schemas. Every existing `study` and
  `optimization-report` fixture validates unchanged against the widened schemas. The registry lists both new files.
- **A39** Two evaluations give byte-identical canonical reports (excluding `provenance`).
- **A40** One refused item: dependent totals are `null` and status is `PARTIAL`. With `exclude`, the totals return and
  the exclusion is listed. A study naming a `null` output → `ASSESSMENT_OUTPUT_UNAVAILABLE`.
- **A41** Every default used is in `defaulted_inputs`. The test enumerates `defaults.py` against P1–P3's reports.
- **A42** Every new dependency and data file has a D04 entry with licence text and sha256. The checker script exits
  non-zero otherwise.

### 6.2 Gates

| Gate | Criterion |
| --- | --- |
| **G1 identity** | A1, A2 |
| **G2 core** | A4–A8 |
| **G3 sizing** | A9–A13 |
| **G4 cost** | A14–A23 |
| **G5 LCA** | A24–A29 (A24, A25 in `.venv-lca`; their absence is `not run`, which is not a pass) |
| **G6 studies** | A30–A37 (A33–A36 in the `nlp` env), with §4.13's timings recorded |
| **G7 schemas and rights** | A38–A42 |
| **G8 release-level** | full `scripts/gate.sh` PASS once before merge; CI green on x86-64 and aarch64 |
| **G9 M03 inert** | A3, A35 |

---

## 7. Risks and open questions (each with a default)

| # | Question | Needs | Default (work proceeds on it) |
| --- | --- | --- | --- |
| Q1 | Trust-region study with assessment objectives on day one? | Frank's preference (scope) | Deferred: typed refusal (A37). The follow-up projects volumetric-flow blocks as `EFHolder` outputs and adds an assessment-objective formulation with its own TR evidence |
| Q2 | Generalise the M03 NLP host from SYN-001 to revision flowsheets (so S11 flowsheets can be cost-optimized)? | Frank's preference (scope) | A separate package right after E01 ("M03-G"). E01's functionals and the revision sensitivity host are host-agnostic, so M03-G only wires `FullSpaceNlp` to a host protocol and V1's re-solve |
| Q3 | CLI/HTTP/MCP binding of assessments? | Frank's preference | The next binding pass. E01 is a library API |
| Q4 | Optimization over discrete regimes (N parallel, utility, material)? | Frank's preference | Not in E01: the report lists `regime_bounds_active` with multipliers; a user re-runs with a regime override |
| Q5 | EF 3.1 factor workbook terms; ship EF 3.1 mapped to a shipped background? | Fact (terms page) + effort (flow mapping) | Not shipped. EF 3.x is used through the user's Brightway method. The report of JRC130796 is CC BY 4.0, as recorded |
| Q6 | USLCI licence per release, and a working Brightway import | Fact | Ship `uslci-…-gwp100-v1` only if CC0/US-PD is recorded and the import works; else the recipe only |
| Q7 | IDAES SSLW coverage (which families) and the CE-500 → year mapping | Fact | The pinned latest IDAES release at WO time (at least 2 weeks old). Mapping 2006 (CEPCI 2006 ≈ 499.6), limitation `INDEX_BASIS_MAPPED`. Families SSLW lacks → `NO_CORRELATION` with quote override |
| Q8 | Ship Turton/CAPCOST? | Frank's preference + a rights fact | Not shipped. Users register it as a `cost-set-v1` data file |
| Q9 | The sizing defaults (τ, φ_fill, LD, K_SB, C_SB, f_flood, φ_active, s_tray, E_o, H_top, H_bottom, η_drive, η_gen, h_op, n, i) | Frank's preference (values) | As in §4.4–§4.7, always reported as `defaulted_inputs`. U and ΔT_min have no default |
| Q10 | ecoinvent EULA on publishing derived unit scores (bundles, papers) | Fact | Forbidden by default: hash only (§4.8.6). A user may set `redistribution: allowed` on their own table, at their responsibility, recorded |
| Q11 | `pypardiso`/MKL in the `lca` extra | Fact (D04) | Excluded; bw2calc's SciPy path. Measured timing recorded |
| Q12 | Electricity export price default | Frank's preference | Equal to import (netting), limitation `ELECTRICITY_NETTED` |
| Q13 | A test pinning bytes of `study`/`optimization-report` schemas or `pyproject.toml` | Fact | Amend on purpose, citing ADR 0052, in `AMENDED_TESTS` |
| Q14 | BLS WPU11 and Eurostat C28 as the default escalation series | Fact (series availability) + preference | As stated. A user can name any series file, including their own CEPCI |
| Q15 | Underwood instead of the exact LMTD | Settled here (R-853) | Revisit only with a measured case where the 0.38 %–2.6 % deviation matters against the estimate's class |
| Q16 | Whether `ParametricTwin` passes one mapping per pass (memo) | Fact | If not, no memo, timings recorded (§4.2.3) |

Risk: **S11 ids drift before merge** (column duty and stage variable names, the saturation routine). WO-A2 reads them
from merged `main` and records them; a missing derivative is a refusal, not an approximation.

---

## 8. Records

### 8.1 ADR 0052 (Proposed)

`docs/adr/0052-e01-assessment-functionals.md`: D1–D10 of §3, the schema additions, the acceptance conditions.

### 8.2 The register

R-850…R-862 in `docs/decision-register.md` (written with this note).

### 8.3 `docs/interfaces-frozen.md` note (written at I1)

> **E01, ADR 0052 (Proposed).**
> - Two schemas are added: `schemas/assessment.schema.json` and `schemas/assessment-report.schema.json`.
> - `study.schema.json` gains an optional top-level `assessment`.
> - `optimization-report.schema.json` gains an optional `formulation.assessment`.
>
> No existing document becomes invalid. No `Protocol`, quantity kind, check category or tolerance changes. Assessment
> outputs never enter a `CompiledProblem`.

`AMENDED_TESTS`: empty unless Q13 finds a pinned byte or hash; each entry cites ADR 0052.

### 8.4 Decisions logs

`docs/E01A_DECISIONS.md` and `docs/E01B_DECISIONS.md`, one line per choice, folded into the single `reviewer` pass.
