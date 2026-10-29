# E01 design: cost estimation and life-cycle assessment as differentiable assessment functionals

**Status:** design lane (`architect`), 2026-10-27. Branch `wp/E01` from `main` `5c8f6006`; built after S11 merges.
**Brief:** `docs/briefs/E01-cost-lca-design.md`. **Records:** ADR 0052 (`docs/adr/0052-e01-assessment-functionals.md`,
Proposed); register R-850…R-862.
**Amended:** 2026-10-27, §9 (ruling A on ESC-A2…ESC-A5; register R-863…R-867). §9 wins where it conflicts.
2026-10-29, §10 (ruling B on QA1, the Seider 4th-ed. differences; register R-890…R-894). §10 wins over §1–§9.
2026-10-29, §10.10 (Amendment 1 to §10: the 3rd edition settles QA1; register R-895…R-899). §10.10 wins over §10.1–§10.9.
**Manifest id (2026-10-29, orchestrator ruling on ESC-I2):** E01's evidence manifest is filed as package **`S12`**
(`evidence/S12/<commit>/manifest.json`); E01 stays the package's name in the docs and is its alias. The frozen
`schemas/evidence-manifest.schema.json` admits only `^[PKTMSR][0-9]{2}[a-z]?$`, and R-565 renamed L01 → S04 for the
same reason. Rejected: a schema ADR widening the pattern.
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

*Erratum 2026-10-29 (E01 review M2, R-869):* `_registered()` imports the fixed contributor table, so the default
can never be empty. When a document section has no chosen contributor, `build` returns
`ASSESSMENT_CONTRIBUTOR_MISSING(<section>)`.

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
| `syn001.kinetic_cstr` | `reactor.vessel` | `<U>.vessel` (volume = `τ_R · V̇_out`; `residence_time_s` required; §9.3), plus `<U>.duty` as above |
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
- (Amended §9.4: model-identity volumes and declared liquid volumes come before this refusal.) A provider that does not offer `v` for the phase is refusal `SIZING_INPUT_UNAVAILABLE(<item>.v)`. Example: the
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
  therefore refused `SIZING_INPUT_UNAVAILABLE(<item>.rho_L)`, unless the item declares `dormant_liquid_density`
  (amended §9.3; `liquid_molar_volume` cannot give ρ_L without a liquid composition).
- Design pressure input = inlet pressure (the maximum by construction, since ΔP ≥ 0).

#### 4.4.5 Machines

- Pump and compressor: `power = W` (shaft, > 0).
- Turbine: `power = −W`.
- Pump extras: `vol_flow = V̇_in`, `head = (P_out − P_in) · v_in/(M̄_in g)`.
- Each set entry names the size quantity it uses (e.g. SSLW's centrifugal pump uses `vol_flow·head^{0.5}` in
  gpm·ft^{0.5}).
- Drive (`<U>.drive`): consumed power `W/η_drive`. `η_drive` comes from the set's motor-efficiency correlation if the
  set defines one, else `defaults.drive_efficiency` = 0.95. It is costed by the set's motor entry; absent → the drive is
  refused `NO_CORRELATION(<U>.drive)`. (Amended §9.2.7: a machine entry with `includes_drive` costs its drive; η_drive
  is the motor entry's η_m at the per-unit shaft power.)
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
- **SSLW vessels.** (Superseded by §9.2.4 form II: IDAES 2.13.0 takes the shell thickness as an input and computes no
  ASME thickness.) Cost by shell weight per IDAES's vessel method: ASME wall thickness from design pressure,
  minimum-thickness steps by diameter, weight from D, L and t.
  - Each `max(…)` and each step is a `piece` entry with its own admissibility rows.
  - WO-A3 enumerates the pieces in the set file, each with its source line.

#### 4.5.2 Set file format (`_data/assessment/cost/<set>.json`)

(Amended §9.2.3: every entry names its `form`; this layout is `"form": "generic-v1"`; SSLW entries use §9.2.3's layout.)

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

*Erratum 2026-10-29 (E01 review M1, R-868):* A ratio's denominator is a regime entry `derived.<id>.denominator` of
kind `domain` (one choice, row `den/|den(x₀)| ≥ 0`), and on the float path a denominator ≤ 0 is the evaluation error
`METRIC_UNDEFINED(derived.<id>)` at every state, not only at planning; a study candidate where it occurs is not
verified (§4.10.3). Lower priority, same rule: `.per_fu`, `lcox` and the `mass`/`economic` allocation ratios. Their
denominators are flows, ≥ 0 under M03's bounds, except a flow that is zero at the start, which M03 leaves unbounded.

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

*Erratum 2026-10-29 (E01 review item 3, R-870; confirmed by Frank 2026-10-29):* the guarantee above covers tables,
scores and θ values. Impacts are results of the user's licensed use and, with the reported inventory, may determine
the scores of the activities used. Every impact that depends on such a table carries limitation
`LCA_RESTRICTED_DATA_DERIVED(<table_id>)`; intervals and σ are not redacted.

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
  - linear worst-case interval `y + Σ_k min/max(∂y/∂θ_k·θ_k·lo_k, ∂y/∂θ_k·θ_k·hi_k)` (box worst case; conservative for any correlation — erratum 2026-10-29, E01 review N1; was "fully correlated");
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
6. *Erratum 2026-10-29 (E01 review S2):* Every admissibility row of the program with scaled slack ≤ τ_active at x* is
   listed under `regime_bounds_active`. Each output whose closure contains it carries limitation
   `REGIME_BOUNDARY_ACTIVE(<row>)`: the derivative is one-sided.

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
  - *Erratum 2026-10-29 (E01 review S1):* `ASSESSMENT_OBJECTIVE_UNSCALED` when an objective naming an assessment
    output has |f(x₀)| ∉ [1e-3, 1e3] at a start, f(x₀) = 0 included; the message tells the user to divide by the
    binding's recorded scale. The objective is never normalised silently.

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
  *Erratum 2026-10-29 (E01 review N5):* `KKT_POINT_VERIFIED` means a KKT point of the held-regime problem. When
  `regime_bounds_active` is non-empty the record carries `regime_note`, saying so in words.
- *Limitation 2026-10-29 (E01 review S3, R-871):* the closure (column overlap, §4.10.2) and V7 (every entry) together
  hold every regime of the program for any assessment objective. This is sound — no candidate is verified across a
  regime change — but over-restrictive: an impact objective is held to the capex size regimes whose rows share Q, and
  a floor row whose size columns no bound output shares lies outside the closure, so the optimizer sees slope 0 there
  and V7 rejects the candidate afterwards (a V7 failure, not a binding row). The follow-up: each `OutputDef` declares
  the regime entries it read, and the closure and V7 both use that dependency closure.

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
- **`study.schema.json`** (additive; as a `$ref` to `assessment.schema.json#/$defs/assessment_link`, §9.1): optional
  top-level `assessment {assessment_id, assessment_sha256, regime_sha256}`. `output_functional.coefficients` keys are unconstrained strings already, so `assessment:<id>` is
  valid.
- **`optimization-report.schema.json`** (additive; as a `$ref` to `assessment.schema.json#/$defs/formulation_assessment`,
  §9.1): optional `formulation.assessment {assessment_id,
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
  *Erratum 2026-10-29 (orchestrator ruling on ESC-I1, `docs/E01B_DECISIONS.md`):* `tac(candidate) ≤ tac(start)` is
  judged over the feasible starts only — a start is feasible when the formulation's constraints hold within their
  stated tolerance there (box exactly, inequality slack ≥ −τ_feas, V3's rule). M03's starts 0 and 1 violate
  `recovery_A ≥ 0` (−0.0159, −0.0537) and sit below the constrained optimum's `tac`; they are reported with their
  violations, not compared.
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

---

## 9. Amendment 2026-10-27 — ruling A on track A's escalations ESC-A2…ESC-A5

**Status:** design lane (`architect`), 2026-10-27, at `wp/E01` `ff7a62a7`. Brief: `docs/briefs/E01-ruling-a.md`. Register:
R-863…R-867. This section is normative. Where it conflicts with §1–§8, this section wins. It supersedes these parts:
- the *form* of the study and optimization-report additions in §4.11;
- §4.4.0's `syn001.kinetic_cstr` row;
- §4.4.3's bullet on a provider without `v`;
- §4.4.4's dormant-liquid bullet;
- §4.4.5's drive-costing sentence;
- §4.5.1's "SSLW vessels" paragraph;
- §4.5.2 for SSLW entries.

Nothing under `compile/`, `thermo/` or `models/` changes. No registered file or result moves. `AMENDED_TESTS` gains
nothing from this ruling.

**Pinned source** throughout:
- the IDAES-PSE 2.13.0 wheel, sha256 `2b67301a…85f9`;
- `idaes/models/costing/SSLW.py`, sha256 `362b0a22…1184` ("SSLW.py:N" below);
- `idaes/core/base/costing_base.py`, sha256 `cdd71f36…fc38`;
- `idaes/core/util/math.py` from the same wheel.

Full hashes are in `docs/E01A_DECISIONS.md` ("Facts confirmed before WO-A3"). The line numbers below are anchors for
the transcriber, who records the exact line of every number in the set file.

### 9.1 ESC-A2 — the study and report links are a `$ref` into E01's own schema (R-863)

**Facts.**
- T08's `--check` partitions `sha256` property names by the schema that declares them
  (`scripts/t08_numerical_policy.py:164-197, 278-307, 316-346`).
  - A name in a schema that no addendum lists belongs to v2, and must lie in v2's `float_digests ∪ exact_sha256`.
  - An addendum classifies names only in its own `schemas`.
  - So `assessment_sha256` or `regime_sha256` written as properties of `study.schema.json` or
    `optimization-report.schema.json` would be unclassified v2 names.
- `state_sha256` is a v2 **float digest** (`benchmarks/t08/numerical_policy_v2.yaml:85-90`), not an exact digest. The
  comment in `benchmarks/e01/numerical_policy_external.yaml`, which lists it among A5's exact names, is wrong.

**Decision.** The two link objects are defined once, as `$defs` of `schemas/assessment.schema.json`, a file that E01's
addendum already owns. The two existing schemas reference them by absolute `$id` URL.
- This is the repository's established cross-schema pattern. For example,
  `optimization-report.schema.json:268` refers to `evaluation-result.schema.json#/$defs/sha256`.
- Validation resolves the reference through the published-schema registry (`application/types.py:157-170`).
- No property name containing `sha256` enters a v2-domain schema, so neither the auditor nor v2 changes.

`assessment.schema.json` gains (B below is `https://github.com/frankp/process-runtime/schemas/`):
```json
"$defs": {
  "assessment_link": {"type": "object", "additionalProperties": false,
    "required": ["assessment_id", "assessment_sha256"],
    "properties": {
      "assessment_id": {"type": "string", "minLength": 1},
      "assessment_sha256": {"$ref": "B/evaluation-result.schema.json#/$defs/sha256"},
      "regime_sha256": {"$ref": "B/evaluation-result.schema.json#/$defs/sha256"}}},
  "formulation_assessment": {"type": "object", "additionalProperties": false,
    "required": ["assessment_id", "assessment_sha256", "regime_sha256", "regime_entries", "outputs",
                 "admissibility", "regime_bounds_active"],
    "properties": {
      "assessment_id": {"type": "string", "minLength": 1},
      "assessment_sha256": {"$ref": "B/evaluation-result.schema.json#/$defs/sha256"},
      "regime_sha256": {"$ref": "B/evaluation-result.schema.json#/$defs/sha256"},
      "regime_entries": {"type": "object", "additionalProperties": {"type": "string", "minLength": 1}},
      "outputs": {"type": "array", "items": {"type": "object", "additionalProperties": false,
        "required": ["id", "scale"],
        "properties": {"id": {"type": "string", "minLength": 1}, "scale": {"type": "number", "exclusiveMinimum": 0}}}},
      "admissibility": {"type": "array", "items": {"type": "object", "additionalProperties": false,
        "required": ["id", "nominal"],
        "properties": {"id": {"type": "string", "minLength": 1}, "nominal": {"type": "number", "exclusiveMinimum": 0}}}},
      "regime_bounds_active": {"type": "array", "items": {"type": "object", "additionalProperties": false,
        "required": ["id", "slack", "multiplier"],
        "properties": {"id": {"type": "string", "minLength": 1}, "slack": {"type": "number"},
                       "multiplier": {"type": "number"}}}}}}}
```
(`B/` stands for the full base URL. Write the URL out in the file.)

The other changes:
- `study.schema.json`: its top-level `properties` gains `"assessment": {"$ref": "B/assessment.schema.json#/$defs/assessment_link"}`, optional.
- `optimization-report.schema.json`: `formulation.properties` gains
  `"assessment": {"$ref": "B/assessment.schema.json#/$defs/formulation_assessment"}`, optional.
- **The same commit as the `$defs`** changes `benchmarks/e01/numerical_policy_external.yaml`:
  - it sets `exact_sha256: [assessment_sha256, regime_sha256]`;
  - it corrects the comment: A5's `state_sha256` keeps v2's float-digest class and is never listed, and `regime.sha256`
    and `tables[].sha256` reuse `sha256`, which keeps v2's class.
- **Semantics.**
  - If a study omits `regime_sha256`, the regime is selected at x₀ by §4.3.2.
  - If a study gives it, the regime is held and checked at the start (`ASSESSMENT_REGIME_INADMISSIBLE`, §4.10.2).
  - The optimization report always records it.
- §8.3's note gains this sentence: "The `$defs` `assessment_link` and `formulation_assessment` of
  `assessment.schema.json` are part of the study and optimization-report interfaces and change only with them."

**Rejected.**
- *`classifies_in`*, an addendum that classifies names in schemas it does not own. It makes v2's closed partition
  depend on later tables. It changes an auditor that T08 owns. It also breaks the tests that re-derive the partition
  (the pattern of `tests/test_m02_schemas.py:69`). Finally, it invites every later package to reach into v2's schemas.
- *Editing v2.* That moves a registered policy file.
- *Field names without `sha256`.* They evade a partition whose purpose (ADR 0025 D2.3) is that no digest goes
  unclassified.

### 9.2 ESC-A3 — SSLW as seven code forms over a coefficient table (R-864, R-865)

#### 9.2.1 Decision

The pinned SSLW methods do not fit §4.5.1's generic forms:
- an oversize multiplier;
- a material factor that depends on size;
- a polynomial pressure factor;
- a weight-based vessel with thickness as an input;
- additive platform and tray terms;
- a CE 394 basis for pumps and motors.

**Decision.** Each IDAES SSLW method that a day-one family uses becomes a **form in code**
(`assessment/cost/forms.py`), mirroring the IDAES function one to one. Every number the form uses is data in
`sslw-idaes-v1.json`, with its source: coefficients, factor tables, option defaults and ranges.

The generic forms stay as §4.5.1–§4.5.2 define them, for sets users register (Turton-like) and for quotes:
- `log-polynomial-v1`, `power-law-v1`, `constant-v1`;
- constant factors;
- the piecewise log-polynomial pressure factor;
- the `F_BM` and `B1 + B2·F_M·F_P` bare-module forms.

SSLW has no bare-module factors, so §4.5.1's `BARE_MODULE_FACTOR_MISSING` rule applies to every SSLW item.

**Rejected.**
- *Extending the generic grammar until SSLW fits in data.* That needs size-power and polynomial factors, adders,
  derived variables, products of powers, per-option tables and pieces. The result is an expression interpreter with
  its own test burden, wider than the problem, and harder to audit against IDAES than a function placed beside the
  function it transcribes. Sets that users register do not share SSLW's peculiarities.
- *Re-deriving SSLW from the book* (ASME thickness, or F_P extended down to 0 psig). That is not a transcription, and
  WO-B4 could not check it against the pinned source.

#### 9.2.2 Transcription versus policy

A form transcribes IDAES's arithmetic. The departures below are deliberate. Each one is recorded in the provenance of
the item it affects.
1. **Ranges.** IDAES enforces none. Ours follow §4.3.2 and §9.2.5.
2. **Tray count factor.** IDAES uses `smooth_max(1, 2.25/1.0414^N)` with eps = 1e-4 (SSLW.py:841; `math.py:97`).
   Ours is the exact `max`, evaluated on floats at build time. N_act is structural, and D3 forbids smoothing.
3. **Vessel wrappers.** `cost_vertical_vessel` and `cost_horizontal_vessel` pass hard-coded defaults instead of
   their arguments (SSLW.py:913-926, 957-966). Ours transcribes `cost_vessel` (:509-727) and passes the options
   through.
4. **Vertical platforms.** IDAES's `aspect_ratio_range` is a user option with default 1. Ours is a `piece` regime on
   L (§9.2.4 form II).
5. **Number of units.** IDAES fixes `number_of_units` at 1. Ours is the size regime's N, for parallel forms only.
6. **Compressor drive.** Only `ElectricMotor` is offered for `drive_type` in E01. A steam or gas turbine drive's
   energy is not electricity, and electricity is the only drive energy §4.7.2 prices.
7. **Exchanger design pressure.** IDAES reads the hot-side inlet (SSLW.py:464-498: "Assume higher pressure fluid is
   tube side"). Ours keeps WO-A2's rule:
   - `exchanger.utility`: the process inlet;
   - `exchanger.process`: the higher of the two inlets, fixed at build.

#### 9.2.3 Set-file grammar (`cost-set-v1`, amended before first use)

**Top level.** As §4.5.2, with `source.transcribed_from` as an object:
`{package: "idaes-pse", version: "2.13.0", wheel_sha256, file: "idaes/models/costing/SSLW.py", file_sha256,
aux: [{file: "idaes/core/base/costing_base.py", sha256}]}`.

**Entries.** Every entry names its `form`. `"form": "generic-v1"` is §4.5.2's layout (`size`, `base`, `factors`,
`bare_module`). An SSLW entry has this layout (shown abridged):
```json
{"entry_id": "exchanger.shell_tube", "form": "sslw-exchanger-v1", "method_lines": "SSLW.py:327-507",
 "family": ["exchanger.utility", "exchanger.process"],
 "index_basis": {"series": "CEPCI", "value": 500.0},
 "options": {
   "hx_type": {"default": "Utube", "default_source_line": "SSLW.py:329",
     "choices": {"Utube": {"alpha1": {"value": 11.3852, "source_line": "SSLW.py:403"},
                           "alpha2": {"value": 0.9186, "source_line": "SSLW.py:403"},
                           "alpha3": {"value": 0.09790, "source_line": "SSLW.py:403"}},
                 "floating_head": {"...": "..."}, "fixed_head": {"...": "..."}, "kettle_vap": {"...": "..."}}},
   "material": {"default": "StainlessSteelStainlessSteel", "default_source_line": "SSLW.py:330", "choices": {"...": "..."}},
   "tube_length": {"default": "TwelveFoot", "default_source_line": "SSLW.py:331", "choices": {"...": "..."}}},
 "coefficients": {"oversize": {"value": 1.1, "source_line": "SSLW.py:393"},
                  "material_area_ref_ft2": {"value": 100, "source_line": "SSLW.py:460"},
                  "pressure_a": [{"value": 0.9803, "source_line": "SSLW.py:494"}, {"...": "..."}, {"...": "..."}],
                  "pressure_ref_psig": {"value": 100, "source_line": "SSLW.py:495"}},
 "ranges": {
   "area_ft2": {"role": "size", "min": 150.0, "max": 12000.0,
     "source": {"kind": "primary", "citation": "Seider, Seader, Lewin, Widagdo, 3rd ed., ch. 22, shell-and-tube purchase cost", "verified": false}},
   "pressure_psig": {"role": "input", "min": 100.0, "max": 2000.0, "below": "floor", "above": "refuse",
     "source": {"kind": "pinned", "source_line": "SSLW.py:492"}}},
 "uncertainty": {"relative_range": [-0.3, 0.5]}}
```

**Rules.**
- **Numbers.** Every number taken from the source is `{"value", "source_line"}`. `value` is the decimal exactly as
  printed, as a JSON number that Python's `json` parses correctly rounded. A sign written in the formula (for example
  `− α2·ln z`) stays in the form; the table holds α as printed.
- **Options.**
  - Choice keys are IDAES's enum member names, verbatim (`Utube`, `floating_head`, `StainlessSteelStainlessSteel`,
    `TwelveFoot`, …). `pump_type_factor` keys are the decimal strings `"1.1"`…`"2.2"`; `weight_limit` keys are `"1"`
    and `"2"`.
  - Defaults are IDAES's argument defaults, each with its `default_source_line`. Every default used appears in
    `defaulted_inputs` (§4.5.5).
  - An item option outside `choices`, or a combination IDAES refuses (pump material against pump type,
    SSLW.py:1420-1441), gives `NO_CORRELATION(<item>)` with the reason in the detail.
  - Options are structural θ.
- **Ranges.** `role` is either:
  - `size`: §4.3's size regime with S_min and S_max. No `below` or `above` is written; the form decides whether units
    may be split (`parallel`, §9.2.4);
  - `input`: a `piece` entry, with `below` ∈ {`floor`, `refuse`} and `above` = `refuse` (§9.2.5).
- **Index basis.** `index_basis` is per entry; absent means the set's basis (§9.2.6).
- **Loader refusals.** The loader refuses a set with any of:
  - an unknown `form`;
  - a missing `source_line` on a coefficient, a choice value or a default;
  - a range without `source`, or a `primary` source without `verified`;
  - a `size` range with `max < 2·min` (unchanged);
  - an `input` range declaring `below: floor` whose form value at `min` is smaller than at `min − 1e-6·max(1, |min|)`.
    A floor must never undercut; this is checked on floats at load.

#### 9.2.4 The seven forms

**Common rules.**
- Per-unit quantity = the item quantity divided by N (parallel forms only).
- Unit factors (§2.1), each a binary64 constant computed once:
  - ft² per m² κ_A = 1/0.3048² = 10.763910416709722;
  - gpm per m³/s κ_Q = 60/3.785411784e-3 = 15850.323141488905;
  - hp per W κ_W = 1/745.6998715822702 = 0.0013410220895950279;
  - inches = m/0.0254; ft = m/0.3048;
  - gauge psig p = (P − 101325)/6894.757293168361.
- Notation: ℓ(·) = ln(·). Products are evaluated left to right, in the order IDAES writes them.
- Item cost C_P = N·C_P1 for a parallel form; C_P = C_P1 otherwise.
- Size floor: the size quantity is replaced by S_min wherever it enters. Each form lists where.

**I. `sslw-exchanger-v1`** (SSLW.py:327-507). Entry `exchanger.shell_tube`; parallel.
- Options:
  - `hx_type`: 4 choices with α1, α2, α3 (:400-405); default `Utube` (:329);
  - `material`: 10 choices with A, B (:438-452); default `StainlessSteelStainlessSteel` (:330).
    `CarbonSteelCarbonSteel` gives F_M = 1.0 exactly, as IDAES does (:454-462);
  - `tube_length`: F_L = 1.25 / 1.12 / 1.05 / 1.00 for 8 / 12 / 16 / 20 ft (:384); default `TwelveFoot` (:331).
- Formulas:
  - A = (S/N)·κ_A in ft²; z = 1.1·A (oversize, :393);
  - C_B = exp(α1 − α2·ℓ(z) + α3·ℓ(z)²) (:415-425);
  - F_M = A_mat + (A/100)^B_mat (:454-462), with A per unit and without the oversize;
  - F_P = 0.9803 + 0.0180·u + 0.0017·u², with u = p/100 (:488-498);
  - C_P1 = F_P·F_M·F_L·C_B (:501-507).
- Size: `area_ft2` = S·κ_A (total), [150, 12000] (primary). The floor puts A = 150 into both C_B and F_M.
- Input: `pressure_psig`, [100, 2000] (pinned, :492). Below 100 psig the floor applies, and F_P = 1.0 exactly in
  binary64 with ∂ ≡ 0. Above 2000 psig the item is refused. Piece entry `<item>.pressure.piece`: 0 = floor, 1 = in range.

**II. `sslw-vessel-v1`** (SSLW.py:509-776). Not parallel: N = 1.
- Entries:
  - `vessel.vertical`: orientation vertical; family `drum`, `column.shell`, `reactor.vessel`;
  - `vessel.horizontal`: orientation horizontal; family `drum`.

  The vertical entry comes first, so a drum that declares no orientation is vertical (§4.4.4).
- Options:
  - `material`: 10 choices, each with F_M and ρ_m in lb/in³ (:620-631); default `CarbonSteel` (:512);
  - `weight_limit` (vertical only): `"1"` gives α = (7.0132, 0.18255, 0.02297), `"2"` gives (7.2756, 0.18255, 0.02297)
    (:675-679); default `"1"` (:514). Horizontal: α = (8.9552, −0.2330, 0.04333) (:674);
  - `platforms_ladders`: boolean; default true (:516).
- Continuous θ `t_shell`, in m, default 0.03175 m = 1.25 in (:513). Its `defaulted_inputs` text: "IDAES default
  shell thickness, including pressure allowance; not computed from the design pressure (SSLW.py:643-644)".
- Formulas:
  - D_in = D/0.0254, L_in = L/0.0254, t_in = t_shell/0.0254;
  - W = π·(D_in + t_in)·(L_in + 0.8·D_in)·t_in·ρ_m in lb (:661-669), with π = `math.pi` (IDAES `Constants.pi`, :663);
  - C_v = exp(α1 + α2·ℓ(W) + α3·ℓ(W)²) (:687-699);
  - C_P1 = F_M·C_v + C_PL (:719-727).
- Platforms and ladders, C_PL (only if `platforms_ladders`), with D_ft = D/0.3048 and L_ft = L/0.3048:
  - horizontal: C_PL = 2005·D_ft^0.20294 (:747-753), with no range;
  - vertical, by piece on L_ft (ranges pinned at :536-537):
    - piece 1, [12, 40): C_PL = 361.8·D_ft^0.73960·L_ft^0.70684 (:756-762), D range [3, 21];
    - piece 2, [40, 170]: C_PL = 309.9·D_ft^0.63316·L_ft^0.80161 (:763-769), D range [3, 24];
    - L_ft < 12: floor, using the piece 1 formula at L_ft = 12;
    - D_ft < 3: floor, D_ft = 3;
    - L_ft > 170, or D_ft above the selected piece's maximum: refused by §4.3.2.
  - Piece entries `<item>.platforms.L.piece` (0 = floor, 1, 2) and `<item>.platforms.D.piece` (0 = floor, 1 = in
    range). The upper admissibility row of the D entry uses the D maximum of the selected L piece.
- Size: W in lb, pinned (docstring :534). Ranges: [1000, 920000] for `weight_limit` `"1"` and for horizontal vessels;
  [4200, 1000000] for `"2"`. Choices are `units:1` and `floor`. W > max gives
  `CORRELATION_OUT_OF_RANGE(<item>.weight)`, or the extrapolation of §4.3.2. The floor puts W = W_min into C_v only.
- The design pressure is recorded in the item's inputs and is not used (IDAES :643-644).

**III. `sslw-trays-v1`** (SSLW.py:777-868). Entry `column.trays`, family `column.trays`; not parallel.
- Options:
  - `tray_type`: Sieve 1, Valve 1.18, BubbleCap 1.87 (:803-807); default `Sieve` (:522);
  - `tray_material`: (α1, α2) pairs (:816-822); default `CarbonSteel` (:521).
- N_act is structural (§4.4.6).
- Formulas, with D_ft = (the shell's D)/0.3048:
  - F_TM = α1 + α2·D_ft (:827-831);
  - C_t = 468.00·exp(0.1739·D_ft) (:854-858);
  - F_NT = max(1.0, 2.25/1.0414**N_act), in binary64 at build (:840-845; departure 2);
  - C_P1 = N_act·F_NT·F_TT·F_TM·C_t (:861-868).
- Size: D_ft, [2, 16] (pinned, :825). Choices are `units:1` and `floor`. The floor puts D_ft = 2 into F_TM and C_t.
  D_ft > 16 is refused, or extrapolated by §4.3.2.

**IV. `sslw-pump-v1`** (SSLW.py:1387-1580). Entry `pump`, family `machine.pump`; parallel; `index_basis` CEPCI 394
(:1579).
- Options:
  - `pump_type`: `Centrifugal` (default, :1389), `ExternalGear`, `Reciprocating`;
  - `material`: one table per type (:1527-1546); default `StainlessSteel` (:1390);
  - `pump_type_factor`: Centrifugal only, F_T table at :1554-1561; default `"1.4"` (:1391). F_T = 1 for the other
    types.
- Per-unit variables:
  - Q = (V̇_in/N)·κ_Q in gpm;
  - H_ft = head/0.3048. §4.4.5's head with g = 9.80665 equals IDAES's ΔP/ρ in lbf·ft/lb;
  - W_hp = (W/N)·κ_W.
- Base cost by type:
  - Centrifugal: S = Q·H_ft**0.5 and C_B = exp(9.7171 − 0.6019·ℓ(S) + 0.0519·ℓ(S)²) (:1585-1590);
  - ExternalGear: C_B = exp(7.6964 + 0.1986·ℓ(Q) + 0.0291·ℓ(Q)²) (:1591-1596);
  - Reciprocating: C_B = exp(7.8103 + 0.26986·ℓ(W_hp) + 0.06718·ℓ(W_hp)²) (:1597-1602).
- C_P1 = F_T·F_M·C_B, at CE 394, converted by §9.2.6.
- Size (primary): Centrifugal S in [400, 100000] gpm·ft^0.5; ExternalGear Q in [10, 900] gpm; Reciprocating W_hp in
  [1, 200] hp. The floor puts S_min into C_B.

**V. `sslw-motor-v1`** (SSLW.py:1625-1661). Entry `motor.electric`, family `machine.drive`; `index_basis` CEPCI 394
(:1647).
- N is the machine item's N. Choices are `units:<N_machine>` and `floor`; rows use the per-unit W_m.
- Option `motor_type`: Open 1, Enclosed 1.4, ExplosionProof 1.8 (:1625-1629); default `Open` (:1392).
- Formulas:
  - W_hp = (W_shaft/N)·κ_W;
  - η_m = 0.80 + 0.0319·ℓ(W_hp) − 0.00182·ℓ(W_hp)² (:1637-1641);
  - W_m = W_hp/η_m;
  - C_B = exp(5.8259 + 0.13141·λ + 0.053255·λ² + 0.028628·λ³ − 0.0035549·λ⁴), with λ = ℓ(W_m) (:1650-1661);
  - C_P1 = F_MT·C_B, at CE 394.
- Size: W_m per unit, [1, 700] hp (primary). The floor puts W_m = 1 into C_B and leaves η_m unchanged.
- η_m is the set's motor-efficiency correlation (§4.4.5, §9.2.7). It has no range, since IDAES states none. Domain
  guard: 0 < η_m ≤ 1, else `CORRELATION_OUT_OF_RANGE(<U>.drive.eta)`.

**VI. `sslw-compressor-v1`** (SSLW.py:1080-1178). Entry `compressor`, family `machine.compressor`; parallel;
`includes_drive: true` (§9.2.7).
- Options:
  - `compressor_type`: (α1, α2) per type (:1155-1159); default `Centrifugal` (:1082);
  - `drive_type`: `ElectricMotor` only, with F_D = 1 (:1135-1139; default :1083; departure 6);
  - `material`: CarbonSteel 1, StainlessSteel 2.5, NickelAlloy 5.0 (:1144-1148); default `StainlessSteel` (:1084).
- Formulas:
  - W_hp = (W/N)·κ_W;
  - C_B = exp(α1 + α2·ℓ(W_hp)) (:1164-1169);
  - C_P1 = F_D·F_M·C_B (:1175-1178).
- Size W_hp (primary): Centrifugal [200, 30000], Reciprocating [100, 20000], Screw [10, 750] hp. The floor puts
  W_hp = min into C_B.

**VII. `sslw-turbine-v1`** (SSLW.py:1338-1386). Entry `turbine`, family `machine.turbine`.
- W_hp = (−W/N)·κ_W; C_P1 = 530·W_hp^0.81 (:1376-1386).
- No size range: IDAES states none, and I do not recall the book's reliably (QA1). So there is no size regime (N = 1,
  no floor). The power law is monotone, so it has no non-physical branch. The provenance reads `range: none stated`.

The entries appear in the file in this order: `exchanger.shell_tube`, `vessel.vertical`, `vessel.horizontal`,
`column.trays`, `pump`, `motor.electric`, `compressor`, `turbine`. Every number not anchored above is anchored by
its line in the set file.

#### 9.2.5 Range policy (R-865)

**Sources**, in order of preference:
1. **pinned**: a range stated in the pinned source (code, comment or docstring), cited by line.
2. **primary**: used **for a size quantity only**, where IDAES states none. It is the range of the same equation in
   Seider et al., 3rd ed., ch. 22, cited with `verified: false` until a person checks it against the book (QA1).
   - The size regime needs S_min and S_max.
   - The log-quadratics also turn upward below their minimum. The floating-head form, for example, has its minimum at
     z = exp(α2/(2α3)) = 125.92 ft², below the book's 150 ft². Without a floor, an exchanger would cost more as it
     shrinks.
   - An input range is never taken from memory.
3. **none**: the input is unbounded, and the provenance says `range: none stated`.

The primary ranges in §9.2.4 are my recollection of the book, not a transcription.

**Behaviour.**
- **Size quantity:** §4.3.2, unchanged. Below S_min the floor applies. Above S_max the item is split into units:N if
  the form is parallel, and refused otherwise.
- **Input below `min` with `floor`:** the input is replaced by `min` in that factor. This is a constant piece with
  derivative exactly 0 and admissibility row `min − z ≥ 0`. It costs the least-demanding design the correlation
  covers, and it never undercuts (the loader checks this). For the SSLW floors:
  - the exchanger pressure factor exceeds IDAES's extrapolated F_P by at most 2.28 %: F_P = 0.97769 at full vacuum
    and 1.0 at 100 psig;
  - the vertical platform terms floor at L_ft = 12 and D_ft = 3.
- **Input below `min` with `refuse`, or any input above `max`:** §4.3.2 applies: refused, unless `allow_extrapolation`
  is set, in which case the item is extrapolated, with the limitation and accuracy class `none`.

**No new limitation code.**
- A floor is a regime choice and is listed with the item's regimes.
- A primary range shows its citation and its `verified` flag in the item's provenance. The `source_line`s of §4.5.5
  become `sources`.

**Release gate (A48).** Before a release candidate, every shipped `primary` range must be `verified: true`. An agent
never sets that flag. A person makes or approves the commit that flips it, and the commit cites the book page.

#### 9.2.6 Index basis per entry

- Each entry declares `index_basis` as `{series: "CEPCI", value}`. The pump and motor entries are at CE 394
  (SSLW.py:1579, :1647).
- IDAES converts with `USD_CE394 = 500/394.0 * USD_CE500` (costing_base.py:66). The form does the same: it multiplies
  C_P1, as the last operation, by r = (set index value)/(entry index value), a binary64 constant computed once as
  500.0/394.0 = 1.2690355329949239.
- §4.6 then applies unchanged, on the set's basis:
  - with a user CEPCI series, the result equals I(Y_t)/394 to rounding;
  - without one, the set's `year_equivalent` 2006 and `INDEX_BASIS_MAPPED` apply.
- The provenance records `index_basis: CEPCI 394 → 500 by the source's ratio`.
- **Rejected:** mapping CE 394 to its own year (2000, CEPCI 394.1) and escalating from there with a public PPI. That
  would replace the source's own 394→500 ratio with a different index over 2000–2006, and pump costs would drift
  relative to the rest of the set.

#### 9.2.7 Drives

- The drive item `<U>.drive` is costed by the set's `machine.drive` entry (`motor.electric`), with N equal to the
  machine item's N.
- A machine entry with `includes_drive: true` already costs its drive. In the SSLW compressor, the drive factor is 1.0
  for an electric motor and greater than 1 for turbines, so its base cost includes an electric-motor drive. For such an
  entry:
  - the drive item's capital is exactly 0.0, with provenance `included_in: <U>`;
  - the drive item keeps its electricity.
- For every electric drive, pump or compressor, η_drive is the `machine.drive` entry's η_m at the machine's per-unit
  shaft power, whenever the set has such an entry. Otherwise it is `defaults.drive_efficiency`.
  - Electricity consumed = W/η_m(W/N), with W the total shaft power.
  - The θ `eta_drive` is then not created and does not appear in `defaulted_inputs`.

### 9.3 ESC-A4 — the kinetic CSTR's volume and a drum with a dormant liquid (R-866)

**(i) `syn001.kinetic_cstr`: V = τ_R·V̇_out.**
- **Why this is the CSTR volume.**
  - The model's rate is Da·exp((T_out − T_ref)/T_s)·n_out,k, with Da = k_ref·τ (`models/syn001/kinetic_cstr.py:3-7`).
  - With τ = V/V̇_out, the declared residence time and the outlet's volumetric flow give the CSTR volume exactly.
  - Da alone gives no volume.
- **Input.** `residence_time_s` is a required continuous θ with no default; a default τ would invent k_ref.
- **V̇_out** is the outlet's volumetric flow in its declared phase (§4.4.3, §9.4).
- **Report.** The informational input `implied_rate_constant` = Da/τ_R, in s⁻¹, with Da read from the unit's
  parameters.
- **Missing τ:** refusal `SIZING_INPUT_MISSING(<U>.vessel.residence_time_s)`. The duty item stays.
- **Rejected:** always refusing (the engineer's interim choice). It refuses where one declared number gives the exact
  CSTR volume.

**(ii) A drum whose liquid product is dormant.**
- **New input.** The item θ `dormant_liquid_density` (kg m⁻³, continuous, no default) is ρ_L in Souders–Brown while
  the liquid product is in its `dormant` regime.
- **Active regime.** ρ_L = M̄_L/v_L as before, and the declaration is reported `used: false`.
- **Missing declaration with a dormant liquid:** the V member is refused `SIZING_INPUT_UNAVAILABLE(<item>.rho_L)`, and
  the drum is refused (WO-A2's rule).
- `liquid_molar_volume` cannot rescue this case. Without a liquid composition there is no M̄_L.
- **Rejected:**
  - computing the incipient-liquid composition x = y/K, which needs a flash inside the assessment;
  - using the vapour's M̄ as the liquid's, which has no basis.

### 9.4 ESC-A5 — model-identity volumes and declared liquid volumes (R-867)

**Facts.**
- **SYN-001's potential defines both volumes** (`docs/derivations/SYN-001.md:20-30, 51`):
  - g_i^L = a(T) + v_i(P − P_r) and g_i^V = … + RT ln(P/P_r), with ideal mixing;
  - so v^V = RT/P and v^L = Σ x_i v_i, with v_i = 1.0e-4 m³/mol (`thermo/syn001.py:46, 53`: `R`, `V_MOLAR`).
- **Wilson-ig v1 and v2.**
  - ln φ^V ≡ 0 (`thermo/wilson_ig.py:5, 14`). Since ∂ln φ_i/∂P = (v̄_i − RT/P)/(RT) = 0, v^V = RT/P exactly.
  - The liquid's g does not depend on P (`thermo/wilson_ig_v2.py:33-36`), so the model's v^L is 0, which is not a
    volume.
- **Why the providers do not *offer* `v`:** nothing consumed it (SYN-001), or offering v^L = 0 would let a pump
  compute W = 0 (Wilson).

**Decision.** Where the provider's published potential defines a phase's volume, the assessment computes it from that
model identity:

| provider_id | VAPOR | LIQUID |
| --- | --- | --- |
| `syn001` | RT/P | Σ_c x_c·v_c (`V_MOLAR`) |
| `wilson-ig`, `wilson-ig-v2` | RT/P | none |

**Implementation.**
- The identities are algebraic rows on host variables in `assessment/blocks.py`, with no `PropertyBlock`:
  - V̇^V = (Σ_c n_c)·R·T/P;
  - V̇^L = Σ_c n_c·v_c.
- Derivatives come from the algebra:
  - vapour: ∂V̇/∂n_c = RT/P, ∂V̇/∂T = nR/P, ∂V̇/∂P = −nRT/P²;
  - liquid: ∂V̇/∂n_c = v_c.
- `R` and `V_MOLAR` are imported read-only from `openflowsheet.thermo.syn001` and `openflowsheet.thermo.wilson_ig`.
  Nothing under `thermo/` is edited.
- ρ = M̄/v, as in §4.4.3.

**Where a phase's v comes from**, in order:
1. the provider's own `v`;
2. the model identity in the table above;
3. the item's `liquid_molar_volume` (a mixture θ);
4. the document's `liquid_molar_volumes` (new: per component, mixed by Amagat as V̇^L = Σ n_c·v_c);
5. otherwise, refusal `SIZING_INPUT_UNAVAILABLE(<item>.v)`.

Steps 3 and 4 apply to LIQUID only. A declaration that is not used is reported `used: false`.

**New document field** (track A's schema): top-level `liquid_molar_volumes: {<component_id>: {value, source}}`, with
`value` in m³/mol and > 0, and `source` a string. The θ ids are `asm:liquid_molar_volume.<component_id>`, continuous.
For a Wilson liquid, Amagat mixing is the model-consistent completion: the model's g^E does not depend on P, so its
excess volume is zero.

**Report.** Every volumetric quantity in an item's inputs carries `v_source`, one of `provider`, `model_identity`,
`declared_item` or `declared_components`. None of these is a limitation: an identity is the model's own volume, and a
declaration is an input like U.

**Guards** (falsifiable; A46). A provider id absent from the table never gets an identity.
- syn001: at ≥ 3 states per phase inside the domain, the provider's R·T·∂lnK_i/∂P equals the identity's v_i − RT/P,
  within rel 1e-12 of RT/P.
- Wilson v1 and v2: the vapour `lnphi_<c>` and its T and P derivatives equal 0.0 exactly.
- v2: P·∂s^V/∂P = −R, within rel 1e-15.
- `thermo.wilson_ig.R == thermo.syn001.R == 8.31446261815324`.

**Consequences.**
- P2's drum is sized with no declaration.
- P3's shell and trays are sized once P3's document declares `liquid_molar_volumes`. I1 uses test inputs of 1.0e-4
  m³/mol per component, with `source: "E01 test input; not a property claim"`. A12 then runs on P3.
- Pumps on Wilson liquids get `vol_flow` and `head` from the declarations.

**Rejected.**
- *Only adding a column case on a basis that offers `v`.* Every SYN-001 and Wilson user would still meet refusals.
- *RT/P for any basis.* Where the model has no ideal-gas identity, RT/P is an approximation, not the model.
- *A Rackett liquid volume.* It needs critical data that the records do not carry, and it is a new model.
- *Editing the providers to offer `v`.* `thermo/` is a protected path.

### 9.5 Revised work orders

Track A's file ownership gains nothing new. WO-B3 depends on WO-A3a.

| WO | Content | Depends | Acceptance |
| --- | --- | --- | --- |
| **A3a** links (first) | §9.1: the two `$defs` in `assessment.schema.json`; `exact_sha256` and the corrected comment in `benchmarks/e01/numerical_policy_external.yaml` | A1 | A43 (partition part) |
| **A2b** volumes, CSTR, dormant liquid | §9.3, §9.4: the identity table and rows in `blocks.py`; volume precedence; `liquid_molar_volumes`, `dormant_liquid_density` and `residence_time_s` for `syn001.kinetic_cstr` in `assessment.schema.json`; families; `v_source` on item inputs | A2 | A46, A47; A4 and A5 on the new rows |
| **A3** (revised) | Generic forms and the seven SSLW forms (§9.2.4); `sets.py` with §9.2.3's checks; `sslw-idaes-v1.json` (every number with `source_line` from the pinned file, the notice verbatim, primary ranges `verified: false`); quotes; `cost/index.py`; the three series files | A3a, A1 | A16–A19, A44 (forms), A45 |
| **A4** (amended) | As §5.2, plus §9.2.6's conversion and §9.2.7: drive inclusion, η_m for electric drives, inherited N | A2b, A3 | A20–A23, A44 (drives) |
| **A5** (amended) | As §5.2. The report records the range sources and `verified` flags, the index-basis conversion, the options with `defaulted`, and `v_source`. `assessment-report.schema.json` joins the E01 addendum's `schemas`; `state_sha256` is not listed | A4 | A38–A41, A43 (report part) |
| **B3** (amended) | The two additive properties as the `$ref`s of §9.1; no auditor change | A3a | A38 (study schemas), A43 (validation part) |
| **B4** (amended) | Transcribe forms I–VII independently from SSLW.py (not from the set file), with the pinned ranges and defaults. mpmath values (below). IDAES cross-check (below). Hand cases A11 and A12 compute the identity volumes (RT/P, Amagat) independently | B1 | A14/A15 YAML; the two transcriptions agree number for number |
| **I1** (amended) | P3's document declares `liquid_molar_volumes` (test inputs, §9.4). P1 exchangers above 2000 psig keep their refusal, or I1 sets `allow_extrapolation: true` on that item explicitly and logs it (QA4) | all | as §5.4 |

**WO-B4's mpmath values** are taken at:
- S_min, √(S_min·S_max) and S_max of each size range (turbine: 10, 100 and 1000 hp);
- each floor bound, and 1e-6 relative inside it;
- P1–P3's sizes.

**WO-B4's IDAES cross-check (A15)** runs at our *effective* inputs: floored values, the selected platform formula
passed as `aspect_ratio_range`, and N. It also:
- calls `SSLWCostingData.cost_vessel` directly (departure 3);
- rescales IDAES's tray cost by max(1, f)/value(`number_trays_factor`) (departure 2);
- compares pump and motor costs in `USD_CE500`.

### 9.6 Assertions and gates

**New assertions.**
- **A43 (links).**
  - `PYTHONPATH=src .venv/bin/python scripts/t08_numerical_policy.py --check` exits 0 and prints `equals`, with v2's
    sha256 unchanged (`6b449911…d707c`).
  - E01's `exact_sha256` is exactly `[assessment_sha256, regime_sha256]`, and it does not intersect
    `schema_sha256_names()` (v2's domain).
  - These pass: `test_m04_numerical_policy.py::test_a37_…`, `test_m02_schemas.py::test_g1_…` and the two
    `test_t08_adr0025.py` A1 tests.
  - Every existing study and optimization-report fixture validates. A study carrying `assessment` validates; one with
    an extra key inside `assessment` fails.
- **A44 (forms).**
  - **Exchanger.** F_P at p ≤ 100 psig equals 1.0 bitwise, and its ∂/∂P row is structurally empty. At
    p = 2000·(1 + 1e-9) psig the item is refused `CORRELATION_OUT_OF_RANGE(<item>.pressure)`. `CarbonSteelCarbonSteel`
    gives F_M == 1.0.
  - **Trays.** F_NT(10) = 1.4997082643358985 and F_NT(19) = 1.0409949546984238, each within rel 1e-15.
    F_NT(20) == F_NT(21) == 1.0.
  - **Vessel hand case** (vertical, `weight_limit` "1", CarbonSteel; D = 1 m, L = 3 m, t = 0.03175 m):
    - W = 6777.48970680199 lb (rel 1e-13);
    - C_v = 33222.512431689356 (rel 1e-12);
    - C_PL = 5045.446066094272 (L floored at 12 ft, D in range; rel 1e-12);
    - C_P1 = 38267.95849778363 at CE 500 (rel 1e-12).
  - **CE 394 conversion.** r == 500.0/394.0 == 1.2690355329949239.
  - **Drives.** η_m(1 hp) == 0.8, and η_m(10 hp) = 0.8638030099054395 (rel 1e-15). A compressor's `<U>.drive` capital
    == 0.0, with provenance `included_in`, and its electricity = W/η_m(W/N) (rel 1e-15).
- **A45 (loader).** The loader refuses each of these, built in the test and never shipped:
  - a set missing a `source_line`;
  - a `primary` source without `verified`;
  - a `floor` on a decreasing form;
  - an unknown option choice;
  - non-contiguous pieces.

  The shipped set loads, and the test prints each range's source kind.
- **A46 (volumes).**
  - The §9.4 guards hold.
  - P2's drum is sized, with `v_source = model_identity` on both products.
  - P3's shell and trays are sized from the declared volumes.
  - For the new rows, twin = reference ≤ 1e-13, and A5's finite-difference oracle holds.
- **A47 (ESC-A4).**
  - Kinetic CSTR: V = τ_R·V̇_out against a hand value (rel 1e-14). Without τ it is refused
    `SIZING_INPUT_MISSING(<U>.vessel.residence_time_s)`, and the duty item remains.
  - Drum with a dormant liquid: with `dormant_liquid_density`, D_V matches the hand value (rel 1e-12). Without it, the
    item is refused `SIZING_INPUT_UNAVAILABLE(<item>.rho_L)`.
- **A48 (release candidate).** Every `primary` range in shipped sets is `verified: true`.

**Changed assertions.**
- A12 runs on P3 (§9.4).
- A11 and A12's expectations include the identity volumes.
- A14 and A15 follow WO-B4 (amended).

**Gates.**
- G3 adds A46 and A47.
- G4 adds A44 and A45.
- G7 adds A43.
- New **G10, release-candidate data:** A48. It runs at the release-candidate cut. At E01's merge it is recorded as
  `not run (RC item)`, which is not a pass.

### 9.7 Open questions (each with a default; work proceeds on the default)

| # | Question | Needs | Default |
| --- | --- | --- | --- |
| QA1 | The primary ranges of §9.2.4 against Seider 3rd ed. ch. 22: exchanger 150–12 000 ft²; centrifugal pump S 400–100 000; external gear Q 10–900 gpm; reciprocating pump 1–200 hp; motor 1–700 hp; compressors 200–30 000, 100–20 000 and 10–750 hp. Also: the turbine's range; whether IDAES's docstring weight ranges (:534) match the book; whether `weight_limit` "2" is the book's tower fit | Fact: a person with the book | Ship the recalled values with `verified: false`. The release candidate is blocked until they are verified (A48). The turbine has no size regime **Closed 2026-10-29 by §10.** |
| QA2 | Option defaults: IDAES's argument defaults (stainless steel exchanger, pump and compressor; U-tube; 12 ft tubes; pump type factor 1.4; open motor; carbon-steel vessel; sieve carbon-steel trays) or carbon steel throughout (the book's base) | Frank's preference | IDAES's defaults, each reported in `defaulted_inputs` |
| QA3 | Below a stated lower bound: floors (conservative, at most +2.28 % on F_P; the platform terms at the boundary) or IDAES's extrapolation (with limitation and class `none`) | Frank's preference | Floors |
| QA4 | Does any P1 exchanger's design pressure exceed 2000 psig (13.79 MPa gauge)? | Fact: I1 reads P1's state | The refusal stands. I1 sets `allow_extrapolation` explicitly per item if P1 needs a complete report, and logs it |
| QA5 | Steam-turbine and gas-turbine compressor drives | Frank's preference (scope) | Not offered in E01 |
| QA6 | Does SSLW's compressor base cost include the electric motor? This is inferred from F_D = 1 for an electric motor | Fact: QA1's book check | Included (`includes_drive: true`) **Closed 2026-10-29 by §10.** |
| QA7 | Wilson liquid volumes: declared per component, or a correlation | Frank's preference | Declared (§9.4); no correlation |
| QA8 | Vessel shell thickness: an input (IDAES) or computed from the design pressure (ASME; not in the pinned source) | Frank's preference | An input, default 1.25 in, reported. A pressure-based thickness would need its own ADR |

Risk (fact, measured in I1): on SYN-001 (P2), most items sit in the `floor` regime, because the flows are small. Their
capital is then constant, so ∂tac/∂x comes from operating cost and from the items that are not floored. A33 still
tests what it states. If I1 finds every capital row floored, it records that, and it does not resize P2.

## 10. Amendment 2026-10-29 — ruling B on QA1: the differences from Seider's 4th edition (E01b)

**Status:** design lane (`architect`), 2026-10-29, branch `wp/E01b` from `wp/E01` `84d71df8`. Brief:
`docs/briefs/E01b-seider-ruling.md`. Register R-890…R-894. Evidence manifest id `S12b`. This section is normative and
wins over §1–§9 where they conflict. It supersedes:
- §9.2.3's number rule (extended by §10.4.1);
- §9.2.4 form II's weight ranges, `weight_limit` "2" and two platform formulas; form IV's basis for the reciprocating
  pump; form VI's size quantity; form VII's range and its single unit;
- §9.2.5's definition of a `primary` range (§10.4.6);
- §9.7 QA1 and QA6, which this section closes.

**Amended 2026-10-29 by §10.10** (Amendment 1: the 3rd edition, R-895…R-899), which wins where they conflict.

One build-lane engineer implements it in one batch before 0.3.0 (§10.6). Nothing under `compile/`, `thermo/`,
`models/` changes. Every number that moves is listed in §10.6.3.

**Already decided by Frank (2026-10-29), not reopened here.**
- The five ranges that match (exchanger, three pumps, motor) count as checked. They are cited to the 4th-ed. page, and
  their coefficients stay IDAES's 3rd-ed. ones, stated as such. `QA1.patch` is applied as it stands.
- The differences are fixed before 0.3.0, and the release waits for them. The compressor's size variable follows the
  book. Coefficients are settled by the 3rd ed. when it arrives, or by adopting the 4th ed.'s.
- Standing directives: as few limitations as possible; batch, then test once; independent expectations only;
  post-solve functionals only; nothing outside E01's files moves.

### 10.1 Facts

**Source.** Seider, Lewin, Seader, Widagdo, Gani, Ng, *Product and Process Design Principles*, 4th ed., Wiley 2017,
ch. 16, at CE 567 (Zotero `seider2017product`). Pages below are printed pages. QA1 made the comparison, and this ruling
re-read each cited page. The 3rd ed. (`seider2009product`) is requested and not in hand.

- **F1, motor efficiency** (p. 453, Eq. 16.18): η_M = 0.80 + 0.0319·ln P_B − 0.00182·(ln P_B)², stated for P_B
  1–1,500 Hp. This is the set's `motor.electric` `eta` (SSLW.py:1638-1640). Eq. 16.16 defines P_C = P_B/η_M.
- **F2, compressors** (p. 460). The base cost is plotted "as a function of consumed power, P_C". It "includes an
  electric motor drive". Ranges: P_C 200–30,000, 100–20,000 and 10–750 Hp (Eqs. 16.36–16.38). In Example 16.9
  (p. 461), 8,840 brake hp with an "assumed 95% efficiency for the motor" gives P_C = 9,300 Hp, which is then put into
  Eq. 16.36.
- **F3, screw compressor.** 8.2496 = 8.1238 + ln(567/500) to the printed digit, and 0.7243 is unchanged. It is the same
  fit as IDAES's, and the 4th ed. states it on P_C.
- **F4, exchangers** (p. 462, Eqs. 16.39–16.42).
  - Floating head and kettle: index-only, exact.
  - Fixed head: α1 11.4185 = 11.2927 + ln(567/500), and α3 0.09861 is unchanged. α2 is **0.9228** in the book and
    **0.8228** in IDAES.
  - U-tube: α2 and α3 are unchanged. The book's α1 is **11.5510**; IDAES's 11.3852 + ln(567/500) = **11.5110**. The two
    differ in one printed digit.
- **F5, fixed-head cost order** (computed at CE 500 from IDAES's other coefficients, z = 1.1·A).
  - With α2 = 0.8228, the fixed head costs more than the U-tube at every size (15,715 against 10,375 USD at
    150 ft²). It costs more than the floating head above 410 ft², and more than the kettle above 2,430 ft². At
    12,000 ft² it is 1.85 times the floating head (233,989 against 126,573).
  - With α2 = 0.9228, the order fixed < U-tube < floating < kettle holds over all of [150, 12,000] ft²: 9,431 /
    10,375 / 18,144 / 24,492 at 150 ft², and 90,602 / 97,019 / 126,573 / 170,855 at 12,000 ft².
  - The fixed-tubesheet construction is the simplest and cheapest shell-and-tube type.
- **F6, reciprocating pump** (p. 454, Eq. 16.23): 7.9361 = 7.8103 + ln(567/500) to the printed digit, and 0.26986 and
  0.06718 are unchanged. So the book's authors shifted it from CE 500. The centrifugal pump, the gear pump and the
  motor, which IDAES also labels CE 394, were refit in the 4th ed. IDAES's CE 394 label is a single `units` statement
  for all of `cost_pump` (SSLW.py:1579).
- **F7, platforms** (pp. 464–465).
  - Horizontal vessel: the book gives 2275·D^0.2094 (Eq. 16.55, 3 < D < 12 ft); IDAES has 2005·D^0.20294.
  - Vertical vessel: 410·D^0.73960·L^0.70684 (Eq. 16.56). This is IDAES's 361.8 × 567/500 = 410.3: index-only.
  - Tower: the book gives 341·D^0.63316·L^0.80161 (Eq. 16.58); IDAES's 309.9 × 567/500 = 351.4.
  - The book's worked examples compute with the printed numbers: 2275·(78)^0.2094 = $5,660 (p. 467), and
    341·(10)^0.63316·(212)^0.80161 = $107,300 (p. 468). With 0.20294, or with 351.4, they would give $5,507 and
    $110,700.
- **F8, vessel weights** (pp. 464–465).
  - Horizontal: 1,000–920,000 lb (Eq. 16.53; refit).
  - Vertical: 4,200–1,000,000 lb (Eq. 16.54). This is IDAES's `weight_limit` "1", index-only.
  - Towers: 9,000–2,500,000 lb, C_V = exp(10.5449 − 0.4672·ln W + 0.05482·ln² W) (Eq. 16.57).
  - IDAES's docstring (SSLW.py:534), "1: 1000 to 920,000 lb, 2: 4200 to 1M lb", lists the horizontal range and the
    vertical range. 7.2756 appears nowhere in the 4th ed.
- **F9, turbine** (p. 483, Table 16.32): gas expanders (pressure discharge), with power extracted 20–5,000 Hp and
  C_P = 600·P^0.81 at CE 567. IDAES's 530 × 567/500 = 601.0, with the same exponent.
- **F10, refits.** The 4th ed. has a different fit for the centrifugal pump, the gear pump, the motor cost, the
  centrifugal and reciprocating compressors and the horizontal vessel shell.

### 10.2 Scope

**In scope:** F1–F10, and their effect on the set file, forms VI and VII, the loader, the hand transcription, the
IDAES cross-check, the fixtures and the tests.

**Out of scope:**
- tray cost and the material, type and length factor tables (QA1 did not compare them; they stay pinned);
- re-basing the set to CE 567;
- a separate 4th-ed. set;
- the default `weight_limit` of `column.shell` (Q-B2);
- enforcing the horizontal platform D range (Q-B3);
- liquid expanders (Q-B9);
- turbine drives (QA5);
- ASME thickness (QA8).

### 10.3 Decisions

**D-B1. The compressor is sized on consumed power (R-890).**

*Decision.* Form VI's size quantity is the book's P_C, the power the motor draws:
- per unit, w₁ = (W/N)·κ_W in brake hp, and P_C,1 = w₁/η_m(w₁);
- η_m is the set's `machine.drive` entry's correlation (`motor.electric` `eta`, which is Eq. 16.18). It is evaluated
  by `forms.motor_efficiency`, the same function on the same resolved entry that §9.2.7 uses for the drive's
  electricity;
- the item's size is S(N) = N·P_C,1 in hp. S/κ_W is exactly the electricity that `<U>.drive` charges, so capital and
  energy see one motor;
- the motor stays included (QA6 is now a fact, p. 460): `<U>.drive` capital is 0.0, and the drive keeps W/η_m(W/N);
- C_B = exp(α1 + α2·ℓ(P_C,1)), with ℓ(S_min) when floored.

*Coefficients.* Centrifugal and reciprocating are refits (F10), so IDAES's coefficients stay, stated as 3rd-ed. The
screw compressor is the same fit, stated on P_C (F3). An index-only reprint keeps its variable, so F3 is also the
evidence that the 3rd ed. used P_C.

*η above 1,500 hp brake* (Eq. 16.18's stated range) is extrapolated. There η_m stays within [0.9354, 0.9398] up to
30,000 hp. Adding a range would refuse the electricity of every large machine.

*Effect.* In range, C_B rises by (1/η_m)^α2:
- centrifugal and reciprocating: +12.4 % at 10 hp brake, +7.1 % at 200 hp, and +5.1 % to +5.5 % above 1,500 hp;
- screw: +11.2 % at 10 hp and +5.3 % at 750 hp.

A floored compressor keeps its cost. Only its floor boundary moves: brake 8.60 hp (screw), 90.68 hp (reciprocating)
and 183.36 hp (centrifugal).

*Rejected:*
- *Brake power*: contradicts the book (Frank).
- *A constant η parameter*: two efficiencies for one motor, so capital and electricity would disagree.
- *The 95 % of Example 16.9*: an assumption for one example outside Eq. 16.18's range. At 8,840 hp, Eq. 16.18 gives
  0.9396, 1.1 % apart in P_C.
- *A copy of η's coefficients in the compressor entry*: a second copy that can drift.
- *Printed P_C ranges converted to brake bounds by inverting w/η(w)*: derived numbers that hide the book's variable.

**D-B2. The coefficients that differ (R-891).**

The rule depends on how the 4th ed.'s correlation relates to IDAES's.
- **Same fit, and every number agrees after the CE shift** (floating head, kettle, the fixed head's α1 and α3, the
  U-tube's α2 and α3, the reciprocating pump's coefficients, the screw compressor, the vertical vessel, the
  vertical-vessel platforms, the exchanger pressure factor, the turbine, motor η): unchanged. A49 makes the agreement a
  test.
- **Refit** (F10): IDAES's 3rd-ed. coefficients stay, stated as such (Frank). The 3rd ed. checks them on arrival
  (§10.7).
- **Same fit, but one number disagrees**: decided per number on the evidence in hand.
  - Adopt the 4th ed.'s value where something in hand supports it: a worked example in the book computes with the
    printed number, a physical test rejects IDAES's value, or the authors' own index shift states the basis.
  - Keep IDAES's value where the only single-misprint explanation puts the error in the 4th ed. and nothing in hand
    tells the two apart.

| Number (set path; SSLW.py line) | IDAES | 4th ed. | Ruling | Evidence | Effect |
| --- | --- | --- | --- | --- | --- |
| `exchanger.shell_tube` `hx_type.fixed_head.alpha2` (:402) | 0.8228 | 0.9228 | **adopt** | F4 same fit; F5 cost order | fixed-head C_B × z^−0.1: 0.600 at 150 ft², 0.387 at 12,000 ft² |
| `exchanger.shell_tube` `hx_type.Utube.alpha1` (:403) | 11.3852 | 11.5510 at CE 567 | **keep** | 11.3852 + ln(567/500) = 11.5110 is one printed digit from the book's figure. The reverse needs a two-digit IDAES error (11.4252 → 11.3852). No example uses it, and the cost order holds either way | none. Stated: 4.08 % below the 4th ed. |
| `pump` `pump_type.Reciprocating.a0` basis (:1599, :1579) | CE 394 | CE 500, implied | **adopt CE 500**; coefficients stay IDAES's | F6: the authors' shift | reciprocating C_P × 394/500 = 0.788 exactly |
| `vessel.horizontal` `platforms_horizontal.a`, `.b_D` (:749) | 2005, 0.20294 | 2275 at CE 567, 0.2094 | **adopt both** | F7: example p. 467 | C_PL × 1.000585·D_ft^0.00646 (+0.77 % at 3 ft, +1.68 % at 12 ft) |
| `vessel.vertical` `platforms[1].a`, tower piece (:765) | 309.9 | 341 at CE 567 | **adopt** | F7: examples pp. 468–469 | piece-2 C_PL × 0.970331 |

On fixed-head α2: 0.8228 against 0.9228 is a single-digit difference whichever source erred. Only F5 decides it, and
F5 decides it firmly. When the 3rd ed. arrives it only tells us *whose* slip it was. It does not change the value.

*Rejected:*
- *A second set file from the 4th ed. (CE 567), made the default.* It contradicts Frank's ruling that the five keep
  IDAES's coefficients. It needs either set layering or a full re-transcription, with its own B4 and no IDAES
  cross-check. That is too much machinery for nine numbers.
- *Keep every IDAES value, labelled, until the 3rd ed.* That leaves the fixed head 1.7 to 2.6 times wrong against
  physics, and makes the release wait for a book not in hand.
- *A typed refusal.* Frank wants few limitations, and every difference here has a verified replacement.
- *Adopt every 4th-ed. figure uniformly.* That knowingly adopts the U-tube figure, which the evidence marks as the
  likelier misprint, and moves every default exchanger by 4.08 % for the sake of uniformity.

**D-B3. Vessel weight ranges (R-892).**
- `weight_limit` "1" (the vertical-vessel fit): its range becomes [4,200, 1,000,000] lb. It stays `pinned` to
  SSLW.py:534, text "2: 4200 to 1M lb", with a note naming the 4th ed. (F8).
- `vessel.horizontal` keeps [1,000, 920,000] lb and gains a note.
- `weight_limit` "2" becomes **the 4th-ed. tower fit**, with three amended numbers (§10.4.2) and range
  [9,000, 2,500,000] lb (`primary`, p. 465, Eq. 16.57). IDAES's "2" is not in the 4th ed. Its attached range belongs to
  "1". A correlation without a verifiable range cannot ship under A48.
- The default stays "1" for every family (QA2).

*Effect.*
- A vertical vessel below 4,200 lb floors at 4,200 lb: C_v goes from 11,734.3 to 25,209.2 USD (× 2.148336).
- Vessels from 1,000 to 4,200 lb leave the `units:1` regime and are floored.
- Vessels from 920,000 to 1,000,000 lb are no longer refused.

*Rejected:*
- *"2" kept with the vertical range*: the range belongs to another fit.
- *IDAES's 7.2756 re-ranged to 9,000–2.5 M lb as "the 3rd-ed. tower fit"*: the 4th ed. cannot confirm that
  identification, and a primary range that cannot be verified blocks 0.3.0 under A48.
- *"2" withdrawn*: a limitation, when a verified fit exists.
- *The tower fit as `column.shell`'s default*: out of scope (Q-B2).

**D-B4. Turbine range (R-893).**
- `turbine` gains the size range `power_hp` [20, 5,000] hp (`primary`, p. 483, Table 16.32; F9).
- Form VII becomes **parallel**: N units of at most 5,000 hp each, and a floor below 20 hp.
- 530 matches 600 to the printed precision, so there is nothing to amend.

*Effect.*
- Below 20 hp: C_P = 530·20^0.81 = 5,999.4 USD (CE 500), against 3,422.0 for the power law at 10 hp.
- Above 5,000 hp: N·530·(W/N)^0.81.
- P1's turbine T (21.33 hp) is in range. Its cost is unchanged, and it gains the entry `T.size = units:1`.

*Rejected:*
- *No range*: the provenance would say "none stated" against a stated range, and extrapolate silently.
- *A refusal above 5,000 hp*: a limitation, and parallel expanders can be built.

**D-B5. One mechanism for amended numbers (R-891).** It is specified in §10.4.1.
- A set number may carry `amended`: the book citation, the IDAES value it replaces, and optionally the CE basis it is
  printed at.
- The loader converts that number to the entry's basis. The form code reads effective values only.
- The reciprocating pump uses the same mechanism as a basis-only amendment: its value stays IDAES's 7.8103, declared at
  CE 500.

*Rejected:*
- *A choice-level `index_basis` override*: a second mechanism. It also cannot express a CE-567 term inside a CE-500
  C_P1, which the vessel platforms need.
- *Pre-converting book values to CE 500 in the file*: that writes digits nobody printed.

**D-B6. Verification (R-894).**
- After the batch, every `primary` range is cited to its 4th-ed. page.
- The 4th-ed. consistency test A49 pins every relation in D-B2.
- A48's count falls to 0 only through a commit that a person makes or approves (C7, §10.6). The five flags this ruling
  adds (three compressors, the turbine, the towers) are written `false` by the engineer. Frank approves them as he
  approved `QA1.patch`.

### 10.4 Design

#### 10.4.1 Amended numbers (extends §9.2.3 "Numbers")

```json
{"value": 0.9228, "source_line": "SSLW.py:402",
 "amended": {"ruling": "R-891", "replaces": 0.8228,
             "citation": "Seider, Lewin, Seader, Widagdo, Gani, Ng, Product and Process Design Principles, 4th ed. (Wiley, 2017), ch. 16, p. 462, Eq. (16.40)"}}
```

**Fields.**
- `value` is the decimal as printed: in the book, or in IDAES for a basis-only amendment.
- `source_line` stays the IDAES line of the number replaced, so that B4 and A15 can pair them.
- `amended` contains:
  - `ruling`: a register id (required);
  - `citation`: required;
  - `replaces`: IDAES's printed value, ≠ `value`. It is required unless the amendment changes only the basis;
  - `index_basis`: the CEPCI value of `value`. Optional;
  - `scale`: `log` or `linear`, required exactly when `index_basis` is present.

**Effective value v_e**, the only value a form sees. B is the entry's `index_basis` value, or the set's if the entry has
none, and B/index_basis is one binary64 division.
- With no `index_basis`: v_e = value.
- `log`: v_e = value + math.log(B/index_basis).
- `linear`: v_e = value·(B/index_basis).

**Loader refusals (added to A45's list).** An `amended` object is refused if it:
- lacks `ruling` or `citation`;
- has neither `replaces` nor `index_basis`;
- has `replaces == value`;
- has `scale` without `index_basis`, or `index_basis` without `scale`;
- has an unknown `scale`.

**Top-level `source`** gains `"checked_against": {"citation": "Seider, Lewin, Seader, Widagdo, Gani, Ng, Product and
Process Design Principles, 4th ed. (Wiley, 2017), ch. 16", "scope": "QA1 range check; the numbers marked amended
(design note §10): individual coefficients and bounds cited by page, no text or table reproduced"}`.
`scripts/e01_d04_inventory.py` carries it into `docs/e01-data-licences.json`.

**Unchanged:** `set_id` (`sslw-idaes-v1`, Q-B8) and the form ids. Nothing carrying v1 has been released, so the forms
are amended in place, as §9.2.3 was.

#### 10.4.2 The amended numbers, exactly

All carry `ruling` R-891 unless marked R-892. Each citation is the §10.4.1 prefix followed by the page and equation shown.

| Path | value | replaces | index_basis / scale | v_e (binary64) | Citation tail |
| --- | --- | --- | --- | --- | --- |
| `exchanger.shell_tube` `options.hx_type.choices.fixed_head.alpha2` | 0.9228 | 0.8228 | — | 0.9228 | p. 462, Eq. (16.40) |
| `pump` `options.pump_type.choices.Reciprocating.a0` | 7.8103 | — | 500.0 / log | 7.8103 + log(394/500) = 7.572042810875742 | p. 454, Eq. (16.23): intercept 7.9361 = 7.8103 + ln(567/500), so these coefficients are at CE 500, not CE 394 |
| `vessel.horizontal` `coefficients.platforms_horizontal.a` | 2275 | 2005 | 567.0 / linear | 2006.1728395061727 | p. 464, Eq. (16.55); used in the example on p. 467 |
| `vessel.horizontal` `coefficients.platforms_horizontal.b_D` | 0.2094 | 0.20294 | — | 0.2094 | p. 464, Eq. (16.55) |
| `vessel.vertical` `coefficients.platforms[1].a` | 341 | 309.9 | 567.0 / linear | 300.705467372134 | p. 465, Eq. (16.58); used in the examples on pp. 468–469 |
| `vessel.vertical` `options.weight_limit.choices."2".alpha1` (R-892) | 10.5449 | 7.2756 | 567.0 / log | 10.41914879469444 | p. 465, Eq. (16.57) |
| … `."2".alpha2` (R-892) | −0.4672 | 0.18255 | — | −0.4672 | p. 465, Eq. (16.57) |
| … `."2".alpha3` (R-892) | 0.05482 | 0.02297 | — | 0.05482 | p. 465, Eq. (16.57) |

Form II's C_v = exp(α1 + α2·ℓW + α3·ℓ²W) takes α as printed, sign included. The tower fit's minimum is at
W = exp(0.4672/(2·0.05482)) = 70.9 lb, so the floor at 9,000 lb never undercuts.

#### 10.4.3 Ranges after the batch

| Entry, range | min–max | Kind | Citation (after the §10.4.1 prefix) | `verified` |
| --- | --- | --- | --- | --- |
| exchanger `area_ft2`; pumps `size_factor`, `flow_gpm`, `power_hp`; motor `motor_power_hp` | unchanged | primary | as `QA1.patch` | true (C1) |
| compressor Centrifugal / Reciprocating / Screw `consumed_power_hp` (renamed from `power_hp`) | 200–30,000 / 100–20,000 / 10–750 | primary | p. 460, Eq. (16.36) / (16.37) / (16.38): …, valid from consumed power P_C = … Hp; the base cost includes an electric motor drive (QA1; centrifugal and reciprocating: the coefficients are IDAES's, from the 3rd ed., ch. 22; screw: the same fit, index-shifted) | false (C3) → true (C7) |
| turbine `power_hp` (new) | 20–5,000 | primary | p. 483, Table 16.32: gas expander (pressure discharge), power extracted 20 to 5,000 Hp, C_P = 600 P^0.81 at CE 567, the same row as IDAES's 530 P^0.81 at CE 500 | false (C3) → true (C7) |
| vessel.vertical "1" `weight_lb` | 4,200–1,000,000 | pinned SSLW.py:534, text "2: 4200 to 1M lb" | note: "IDAES's docstring labels this range '2'; the 4th ed. (p. 464, Eq. 16.54) gives it to the vertical-vessel fit, which is weight_limit '1' (7.0132 + ln(567/500) = 7.1390)" | — |
| vessel.vertical "2" `weight_lb` | 9,000–2,500,000 | primary | p. 465, Eq. (16.57): towers, 9,000 < W < 2,500,000 lb | false (C3) → true (C7) |
| vessel.horizontal `weight_lb` | unchanged | pinned :534 | note added: "the 4th ed. gives this range to horizontal vessels (p. 464, Eq. 16.53)" | — |

#### 10.4.4 Form VI, amended (`sslw-compressor-v1`)

**Size.**
- The form declares `size_depends_on_units`. `quantities(e, x, alg, n)` returns two values:
  - `consumed_power_hp` = n·(w₁/η_m(w₁)), with w₁ = (x.power/n)·κ_W;
  - `brake_power_hp` = x.power·κ_W.
- `resolve()` attaches the set's resolved `machine.drive` entry to the compressor's `ResolvedEntry`.
- The loader refuses a set that has an `sslw-compressor-v1` entry but no `machine.drive` entry of form `sslw-motor-v1`.

**Selection** (replaces §4.3.2 rule 4 for forms declaring `size_depends_on_units`; at present that is VI only).
- S(n) = `consumed_power_hp` at n.
- `floor` if S(1) < S_min.
- Otherwise N is the smallest integer n ≥ n₀ with S(n) ≤ n·S_max. Here n₀ is the smallest integer ≥ 1 with
  W_hp ≤ n₀·S_max; it is a lower bound because η_m ≤ 1. Evaluate n = n₀, n₀ + 1, … on floats. A tie selects n.
- Rows keep §4.3.1's form at the held N: `S(N) − N·S_min`, `N·S_max − S(N)`, and `S_min − S(1)` for the floor. S is
  evaluated by `quantities(e, x, alg, N)`, as `contributor.py` already does.

**Loader check.** A `consumed_power_hp` range needs S_max ≥ 3·S_min. For u ≥ 1 hp, η_m(u/2)/η_m(u) ≤ 1.175. So the N
selected for N ≥ 2 has S(N)/N ≥ S_max·η_m(u)/(2·η_m(u/2)) ≥ S_max/2.35 ≥ S_min, with u = W/(N−1). §4.3.3's honesty
argument therefore holds. The shipped ratios are 75, 200 and 150.

**Domain.** 0 < η_m ≤ 1 at every per-unit power evaluated, else `CORRELATION_OUT_OF_RANGE(<U>.eta)`.

**Cost.** p = S_min if floored, else w₁/η_m(w₁) at N. C_P = N·F_D·F_M·exp(α1 + α2·ℓ(p)).

**Provenance.** The range name and its citation state the size variable. `defaulted_inputs` gains nothing: η_m is a
set correlation, not a θ.

#### 10.4.5 Form VII, amended (`sslw-turbine-v1`)

- `parallel = True` and `size_range = "power_hp"`. `quantities` = x.power·κ_W (total), with x.power = −W > 0.
- Selection is §4.3.2 rule 4, unchanged.
- C_P = N·a·p^b, where p = S_min if floored, else (x.power/N)·κ_W.
- The generator (`GENERATOR_NOT_COSTED`) is unchanged.

#### 10.4.6 §9.2.5 amended: what `primary` means

A `primary` range is the range of the same equation in Seider et al., 4th ed. (2017), ch. 16. It is used where the
4th ed.'s equation is the same fit as the set's, or states the same size variable. It is cited by page and equation.

It is still **for size quantities only**: input ranges are never taken from the book (Q-B3). A48 is unchanged: a
person makes or approves every flip to `verified: true`.

#### 10.4.7 Departures from IDAES (appended to §9.2.2)

8. **Compressor size.** IDAES evaluates the base cost at brake power (SSLW.py:1130-1132). Ours uses the consumed
   power P_C = w₁/η_m(w₁) (D-B1).
9. **Amended numbers.** Seven numbers and one basis differ from the pinned source. Each carries `amended` (§10.4.2).
10. **Turbine.** It has a size range [20, 5,000] hp, a floor below it, and parallel units above it. IDAES has no
    range and N = 1.
11. **Vessel weight ranges.** The docstring's two ranges go to the fits the book gives them to (D-B3).

#### 10.4.8 Report

- Each item's `source` gains `amended`: for each amended number its selected options use, the value, `v_e`,
  `replaces` (if any), `index_basis`/`scale` (if any), the citation and the ruling. `source_lines` is unchanged.
- The item `source` is a free object in `assessment-report.schema.json`, so no schema changes.

#### 10.4.9 Independent expectations

**B4, `benchmarks/e01/cost_hand/cost_hand.py`.** Transcribed from this section and from the book, never from the set
file. Changes:
- fixed-head α2 = 0.9228, with one new case `fixed_head` at √(150·12,000) ft²;
- the reciprocating pump's coefficients at CE 500, so no 500/394 factor;
- `VESSEL_W_RANGE` "1" (4,200, 1e6) and "2" (9,000, 2.5e6). "2"'s α is (10.5449 + ln(500/567), −0.4672, 0.05482);
- `PL_HORIZONTAL` = (2275·500/567, 0.2094); `PL_VERTICAL` piece 2 coefficient 341·500/567;
- compressor on P_C with the N rule of §10.4.4. Its targets are built by inverting P_C, the way `motor_shaft_for`
  already does;
- turbine: `size_targets(20, 5000, parallel=True)` replaces (10, 100, 1000) hp.

The A44 vessel hand case stays as it is: W = 6,777 lb, in range.

**A15, `benchmarks/e01/brightway/idaes_crosscheck.py`.** IDAES is evaluated at our effective inputs, and each amended
term is mapped by an exact factor. The YAML records the raw IDAES value, the factor and the compared value.
- Compressor: `work_mechanical` = the case's effective total consumed power (S(N), or S_min floored) in W, with
  `number_of_units` = N.
- Turbine: IDAES at the per-unit effective power, × N.
- Fixed head: C_P × exp(−(0.9228 − 0.8228)·ℓ(1.1·A_unit,ft²)).
- Reciprocating pump: `pump_capital_cost` × 394/500.
- Horizontal platform term × (2275·(500/567)/2005)·D_ft^(0.2094 − 0.20294). Piece-2 platform term ×
  341·(500/567)/309.9.
- `weight_limit` "2": C_v × exp((v_e,α1 − 7.2756) + (−0.4672 − 0.18255)·ℓW + (0.05482 − 0.02297)·ℓ²W), and then
  C_P = F_M·C_v + C_PL.

**A49 expectation, `benchmarks/e01/cost_hand/seider4.yaml`** (new). It holds the book numbers the set's numbers
correspond to, typed from the pages of §10.1: the individual numbers only, each with page and equation, and never book
text. Each record gives a set path, the book value, the page and equation, and a relation:
- `index_log`: |v + ln(567/B_v) − book| ≤ ½ unit of the book's last printed decimal. B_v is the number's own basis:
  `amended.index_basis`, else the entry's, else the set's;
- `index_linear`: |v·567/B_v − book| ≤ ½ unit of its last significant digit. Table 16.32's "600" is read as 2
  significant figures, unit 10;
- `same`: decimal equality (slopes, exponents, pressure factor, η);
- `amended`: `value == book`, with that page in `citation`;
- `kept`: the U-tube α1. Asserts v = 11.3852 and book − (v + ln(567/500)) = 0.0400 ± 5e-5;
- `refit`: entry only, with no numbers typed.

Ranges compare by exact equality of min and max with the book's printed bounds.

### 10.5 Assertions and gates

- **A44 (amended).** The drive assertions stand. Add: the compressor's S(N)/κ_W equals its `<U>.drive` electricity to
  rel ≤ 1e-15.
- **A48 (amended).** After C7, `a48_release_check()` returns (`pass`, 0). The tripwire test pins 0 and `pass`. Its
  negative case flips one primary range to `false` in a copy and asserts that `unverified_primary_ranges` returns
  exactly that pointer.
- **A49 (new, the 4th-ed. consistency).**
  - Every relation in `seider4.yaml` holds.
  - The YAML covers every `primary` range and every `amended` number in the shipped set (completeness), and the set
    has no `amended` number the YAML lacks.
- **A50 (new, compressor).**
  - Shaft powers are constructed so that per-unit P_C sits at S_min·(1 ± 1e-9), S_max·(1 − 1e-12) and, at N = 2,
    S_max·(1 + 1e-9). They select `floor`/`units:1`, `units:1` and `units:3` respectively.
  - C_P equals cost_hand to A14's tolerance.
  - The loader refuses a set with a compressor and no motor entry, and a `consumed_power_hp` range with max < 3·min.
- **A51 (new, loader).**
  - The five refusals of §10.4.1.
  - v_e is bitwise equal to the expression in §10.4.2 for each amended number.
  - The tower floor's no-undercut holds at 9,000 lb.
- **A14 / A15.** Unchanged tolerances, on the regenerated cases. A15 is rel ≤ 1e-9 against IDAES with the factors
  applied.
- **Gates.** G4 adds A49–A51. G10 (A48) passes only after C7. The full `scripts/gate.sh` runs once before the merge,
  and CI must be green on both architectures. A `reviewer` pass is needed: the batch changes numerics.

### 10.6 Work order (one build-lane engineer, branch `wp/E01b`, about 150k context)

#### 10.6.1 Commits, in order (test once, after C6)

1. **C1. Apply `QA1.patch`.** It is Frank-approved, so apply it unchanged. It is committed with this ruling as
   `docs/briefs/E01b-QA1.patch`; apply it with `git apply`.
2. **C2. Loader** (`assessment/cost/sets.py`):
   - `amended` objects and their effective values;
   - the five refusals;
   - the compressor-needs-motor check;
   - the consumed-power 3× check;
   - `resolve()` attaching the drive entry;
   - `source.checked_against`.
3. **C3. Forms and data.**
   - `assessment/cost/forms.py`: form VI (§10.4.4) and form VII (§10.4.5);
   - both copies of `sslw-idaes-v1.json`, kept byte-identical (`cmp`): §10.4.2's amendments, §10.4.3's ranges and
     citations (new flags `false`), the compressor key renamed;
   - the report's `amended` block.
4. **C4. B4.**
   - `cost_hand.py` as in §10.4.9, then regenerate `cost_hand.yaml` with its own `main()`;
   - add `seider4.yaml` and `tests/test_e01_b_seider4.py` (A49).
5. **C5. A15.** Update `idaes_crosscheck.py` and re-run it in the scratch IDAES environment (Q-B6) to regenerate
   `idaes_crosscheck.yaml`.
6. **C6. Fixtures and pins.**
   - regenerate the three golden reports and `invalid/string_output_value.json` with `tests/test_e01_a_report.py`'s
     `_write()`;
   - pin the set's new sha256 in `tests/test_t08_w2_inventory.py`, in `docs/e01-data-licences.json` (by
     `scripts/e01_d04_inventory.py`), and in `docs/E01A_DECISIONS.md` (append the new hash as superseding the old,
     with a pointer to §10);
   - `tests/test_e01_a_cost.py:132`: primary flags as §10.4.3, and 10 primary ranges;
   - the A48 tripwire at 5;
   - A44, A50 and A51 tests.
   - Then run the E01 tests once (§10.6.4).
7. **C7. The verification commit**, and nothing else in it:
   - flip the five new ranges to `verified: true`;
   - set the tripwire to 0/`pass` with its negative case;
   - re-pin the sha256.

   Prepare it as `QA1b.patch` for Frank. Commit it only after the coordinator relays his approval, and name the
   approval in the message (A48). Until then G10 reads "pending person approval".

Log every build choice in `docs/E01B_DECISIONS.md`. Write `evidence/S12b/<commit>/manifest.json`.

#### 10.6.2 Files

**Touched:**
- `src/openflowsheet/assessment/cost/{sets,forms,contributor}.py` (contributor only if the report block lives there);
- `assessment/cost/sslw-idaes-v1.json` and `src/openflowsheet/_data/assessment/cost/sslw-idaes-v1.json`;
- `benchmarks/e01/cost_hand/{cost_hand.py,cost_hand.yaml,seider4.yaml}`;
- `benchmarks/e01/brightway/{idaes_crosscheck.py,idaes_crosscheck.yaml}`;
- `tests/test_e01_*.py`, `tests/test_t08_w2_inventory.py`;
- the four report fixtures;
- `docs/e01-data-licences.json`, `docs/E01A_DECISIONS.md`, `docs/E01B_DECISIONS.md`;
- `evidence/S12b/`.

**Nothing else.** The t08 inventory test pins this data file's hash, so it is the one file outside E01 that moves.

#### 10.6.3 What moves, and by how much (any other moved number: stop and escalate)

- **M1.** `vessel.vertical` with W < 4,200 lb: C_v floors at 25,209.2 instead of 11,734.3 (CE 500).
  - P1 TH-R1 `D.drum` (W = 236.8 lb): C_P1 goes from 16,456.6 to 29,931.5 (C_PL 4,722.3 is unchanged), and every
    quantity derived from it moves with it.
  - P3 M1 `S02.shell` (W = 3,360.4 lb): `units:1` becomes `floor`, and C_v goes from 22,246.1 to 25,209.2
    (+13.3 %). Its rows become the floor row.
  - All `weight_limit` "1" and "2" cases are new.
- **M2.** Horizontal vessels: C_PL × 1.000585·D_ft^0.00646.
- **M3.** Vertical platform piece 2: C_PL × 0.970331.
- **M4.** Reciprocating pump: C_P × 0.788.
- **M5.** Every compressor case and regime boundary (D-B1).
- **M6.** Turbine: the cases are new. P1's `T` cost is unchanged, and its report gains `T.size = units:1`.
- **M7.** Fixed head: × z^−0.1 (new case).
- **M8.** Citations, `verified` flags, range texts and notes in the provenance; the set's sha256.

Exchangers (U-tube), centrifugal pumps and motors do not move.

The batch leaves every P3 capital item floored. Do not resize P3, and do not loosen a test. If an assertion's premise
was a non-floored P3 capital row, record it in `E01B_DECISIONS.md` for the reviewer and carry on. §9.7's risk paragraph
already prescribes this for P2.

#### 10.6.4 Acceptance commands

- `cmp assessment/cost/sslw-idaes-v1.json src/openflowsheet/_data/assessment/cost/sslw-idaes-v1.json` exits 0.
- `.venv/bin/python -I benchmarks/e01/cost_hand/cost_hand.py --check` exits 0.
- `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_e01_*.py tests/test_t08_w2_inventory.py` runs, through a
  one-line wrapper with the log to a file. After C6 every test passes, with the tripwire at 5; after C7, at 0.
- `PYTHONPATH=src .venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); import e01_evidence_manifest as m;
  print(m.a48_release_check())"` prints `('pass', …0…)` after C7.
- `scripts/gate.sh` passes once before the merge. Then CI, then the `reviewer` pass.

### 10.7 When the 3rd edition arrives (conditional work order; one commit per change; a reviewer pass if a number moves)

1. **Refits (F10), and every number QA1 did not compare** (trays, factor tables, the pump and motor CE 394 labels).
   Compare each IDAES number with ch. 22.
   - If they match, record it; nothing changes.
   - If they differ, amend the number to the 3rd ed.'s printed value: `amended` with the 3rd-ed. citation, at that
     edition's stated basis, under a new register id. Add `seider3.yaml`, in the A49 pattern.
2. **Numbers adopted from the 4th ed. (D-B2, D-B3).** Record which printing erred. The values do not change: the 4th ed.'s
   figure is supported by an example, by physics or by the authors' own shift.
3. **U-tube α1.**
   - If the 3rd ed. prints 11.3852, close the item as a 4th-ed. misprint.
   - If it prints 11.4252, amend to 11.5510 at CE 567 (`log`): IDAES miscopied.
4. **Compressor variable.** If the 3rd ed. states the centrifugal or reciprocating fit on brake power, that type reverts
   to brake, by a new ruling. The expected outcome is that it states P_C (F3).
5. **`weight_limit` "2".** Record whether 7.2756 is the 3rd-ed. tower fit. Nothing changes.

### 10.8 Open questions (work proceeds on the default)

| # | Question | Needs | Default |
| --- | --- | --- | --- |
| Q-B1 | U-tube α1: 11.3852 (IDAES) or 11.5510 at CE 567 (4th ed.) | Fact: the 3rd ed. | Keep 11.3852; §10.7 item 3 |
| Q-B2 | Should `column.shell` default to the tower fit ("2"), as the book costs towers? It moves P3 and every column | Frank's preference | No: "1" for every family. A user may select "2" per item |
| Q-B3 | Enforce the horizontal platform range 3 < D < 12 ft (p. 464)? | Frank's preference | Not enforced (no new refusal); recorded here |
| Q-B4 | Ship 7 values, one basis statement and 4 range bounds from the 4th ed. in the wheel | Frank (rights) | Ship: individual facts cited by page, no text or tables; recorded in the licence record via `checked_against` |
| Q-B5 | η_m above 1,500 hp brake | Fact | Extrapolate (0.9354–0.9398 up to 30,000 hp) |
| Q-B6 | The scratch IDAES 2.13.0 environment for A15 | Fact | Re-create it from the pinned wheel (sha256 `2b67301a…85f9`). If that is impossible, stop and report; A15 is not skipped |
| Q-B7 | Approval of the five new `verified` flags | Frank | C7 is held as `QA1b.patch` until he approves; G10 is pending until then |
| Q-B8 | `set_id` now that the set carries amendments | Frank's preference | Keep `sslw-idaes-v1`; the amendments are listed in the file |
| Q-B9 | Liquid expanders (Table 16.32: 150–2,000 Hp, 1,590·P^0.70) | Frank's preference (scope) | Not offered; every turbine is a pressure-discharge gas expander, as in IDAES |
| Q-B10 | Tray cost and the factor tables against the 4th ed. | Fact | Not compared by QA1. Pinned, so outside A48; checked on the 3rd ed.'s arrival |

### 10.9 Records

- Register: R-890 (compressor), R-891 (coefficient rule and amended numbers), R-892 (vessel weights), R-893 (turbine)
  and R-894 (verification and the 3rd-ed. protocol).
- §9.7 QA1 and QA6 are closed by this section.
- Literature: the 4th ed. is already filed (`seider2017product`). The claim that fixed-tubesheet construction is the
  cheapest (F5) is standard. A textbook citation for it, for example Towler and Sinnott, *Chemical Engineering Design*,
  shell-and-tube types, goes to the reference library. No other new reference.

---

### 10.10 Amendment 1 to §10 (2026-10-29): the 3rd edition settles QA1

**Status:** design lane (`architect`), 2026-10-29, branch `wp/E01b` at `15307c6a` (C1, C2, C1 pins). Brief:
`docs/briefs/E01b-seider3-amendment.md`. Register R-895…R-899. This subsection is normative and wins over §10.1–§10.9
where they conflict. It supersedes:
- §10.3 D-B2's rule, its table and its adopted list; D-B3's ruling on `weight_limit` "2"; D-B5's reciprocating-pump
  example; D-B6's first two bullets;
- §10.4.2 and §10.4.3 (replaced by §10.10.5.1 and §10.10.5.3); §10.4.6; §10.4.7 item 9; the B4, A15 and A49 parts of
  §10.4.9;
- §10.5's A49 and A51; §10.6.1–§10.6.3 (replaced by §10.10.7); §10.7 (carried out here, now closed); §10.8 (replaced
  by §10.10.9).

**Stands, with its evidence re-cited to the 3rd ed.:** D-B1 (compressor on P_C, R-890), D-B4 (turbine, R-893), the
amended-number grammar and effective values (§10.4.1), forms VI and VII (§10.4.4, §10.4.5), the report block
(§10.4.8), A44, A48, A50, §10.6.4.

**Already decided by Frank (2026-10-29), not reopened.** The five QA1 ranges count as checked; their citations gain
the 3rd-ed. page where it confirms them. The set's coefficients follow IDAES's 3rd-ed. values where the 4th ed. refit
them. The differences are fixed before 0.3.0 and settled with the 3rd ed. A 4th-ed. number is used only where the 3rd
ed. cannot settle it, and each such number goes to Frank. **Outcome: the 3rd ed. settles every number. No 4th-ed.
number ships; the 4th ed. survives only as a second citation on the five QA1 ranges.**

#### 10.10.1 Facts from the 3rd edition

**Source.** Seider, Seader, Lewin, Widagdo, *Product and Process Design Principles: Synthesis, Analysis, and
Evaluation*, 3rd ed., Wiley 2009, ch. 22, §22.5 and Table 22.32 (Zotero `seider2009product`). Every correlation is
stated at CE 500 (the 2006 average), the set's basis (SSLW.py:343). Pages are printed pages. The copy is licensed:
individual numbers with page and equation only, never text or tables.

- **G1, pumps and motor are at CE 500.**
  - Centrifugal pump: the cost data are stated as indexed to 2006, CE = 500 (p. 561, Eq. 22.14, Fig. 22.3).
  - Motor: the Corripio et al. (1982a) motor correlations, stated as indexed to 2006, CE = 500 (p. 562, Eq. 22.19,
    Fig. 22.4).
  - Gear and reciprocating pumps: base costs stated at the 2006 index, CE = 500 (p. 563, Eqs. 22.21, 22.23, Figs.
    22.5, 22.6).
  - Example 22.6 (pp. 564–565) evaluates the centrifugal pump (C_B = $5,740) and the motor (C_B = $9,710) at CE 500
    with the printed coefficients, then multiplies by 550/500.
  - IDAES labels the pump base cost (SSLW.py:1579, :1604) and the motor base cost (:1647, :1661) `USD_CE394`, and the
    set copies that as `index_basis` 394 (costing_base.py:66). No page of the 3rd ed. supports 394. Every pump and
    motor coefficient is equal to the book's.
- **G2, the exchanger equations print a stale basis.**
  - Eqs. 22.39–22.42 (p. 571) print α1 = 11.667 (floating head), 11.0545 (fixed head), 11.147 (U-tube), 11.967 (kettle).
  - IDAES's α1 are each exactly **0.2382** higher in decimal arithmetic: 11.9052, 11.2927, 11.3852, 12.2052.
    ln(500/394) = 0.238257, so 0.2382 is the CE 394 → 500 shift truncated to four decimals.
  - The book's own Example 22.10 (p. 572) computes at CE 500 with **11.9052** (C_B = $79,500 at A = 7,290 ft²), not
    with the 11.667 of Eq. 22.39.
  - The 4th ed. prints IDAES's α1 + ln(567/500) (§10.1 F4).
  - Conclusion: the printed intercepts are the 2nd edition's CE-394 values under a CE-500 label. IDAES's intercepts are
    the CE-500 values the book itself computes with, and the authors' next edition confirms them.
  - α2 and α3 equal IDAES's, except the fixed head's α2 (G3).
- **G3, fixed-head α2** is **0.9228** (p. 571, Eq. 22.40), as in the 4th ed. (p. 462). IDAES's 0.8228 is in neither
  edition.
- **G4, U-tube α1.** 11.147 + 0.2382 = 11.3852 = IDAES's value. The 4th ed.'s 11.5510 is therefore a misprint of
  11.5110 (= 11.3852 + ln(567/500)).
- **G5, compressors** (p. 569).
  - The base cost is plotted against the consumed power P_C in hp, at CE 500, and it includes an electric motor
    drive.
  - Eqs. 22.36–22.38 are IDAES's coefficients (7.5800/0.80, 7.9661/0.80, 8.1238/0.7243). Ranges: P_C = 200 to 30,000,
    100 to 20,000 and 10 to 750 Hp. F_D = 1.15 (steam turbine) and 1.25 (gas turbine); F_M = 2.5 (stainless steel) and
    5.0 (nickel alloy).
  - Example 22.9 (p. 570): 8,840 BHp with an assumed 95 % motor efficiency gives P_C = 9,300 Hp, which goes into
    Eq. 22.36.
  - P_C = P_B/η_M is Eq. 22.16 (p. 561). η_M is Eq. 22.18 (p. 562), the set's `motor.electric` `eta`, stated for P_B
    from 1 to 1,500 Hp.
- **G6, vessel weights** (pp. 574–575).
  - Horizontal: 1,000 < W < 920,000 lb, (8.9552, −0.2330, 0.04333) (Eq. 22.53) = IDAES. The 4th ed. refit it.
  - Vertical: 4,200 < W < 1,000,000 lb, (7.0132, 0.18255, 0.02297) (Eq. 22.54) = IDAES `weight_limit` "1".
  - Towers: 9,000 < W < 2,500,000 lb, (7.2756, 0.18255, 0.02297) (Eq. 22.57) = IDAES `weight_limit` "2". Examples
    22.13 (p. 578) and 22.14 (p. 579) compute with 7.2756. The 4th ed.'s (10.5449, −0.4672, 0.05482) is a refit.
  - So IDAES's docstring (SSLW.py:534) gives the horizontal range to "1" and the vertical range to "2". Each fit's
    own range is the one above.
- **G7, platforms and ladders** (pp. 574–575).
  - Horizontal: 2,005·D^0.20294, 3 < D < 12 ft (Eq. 22.55) = IDAES. Example 22.12 (p. 577) computes
    2,005(78)^0.20294 = $4,850. The 4th ed.'s 2275·D^0.2094 is a refit: 2005·567/500 = 2273.6, the exponent differs,
    and each edition's example uses its own numbers.
  - Vertical: 361.8·D^0.73960·L^0.70684, 3 < D < 21 ft, 12 < L < 40 ft (Eq. 22.56) = IDAES.
  - Towers: **300.9**·D^0.63316·L^0.80161, 3 < D < 24 ft, 27 < L < 170 ft (Eq. 22.58). Example 22.13 (p. 578):
    300.9(10)^0.63316(212)^0.80161 = $94,700; with 309.9 it would be $97,570. Example 22.14 (p. 579) uses 300.9 again.
    IDAES has **309.9**. The 4th ed.'s 341 is 300.9 × 567/500 = 341.2 to three figures.
- **G8, turbine** (Table 22.32, p. 593): gas expanders (pressure discharge), power extracted 20 to 5,000 Hp,
  C_P = 530·P^0.81 at CE 500 = IDAES. Liquid expanders: 150 to 2,000 Hp, 1,400·P^0.70 (Q-B9).
- **G9, everything else is equal.**
  - Trays (p. 577): C_BT = 468·exp(0.1739·D), 2 to 16 ft (Eq. 22.67); F_NT = 2.25/1.0414^N_T below 20 trays, else 1
    (Eq. 22.68); F_TT 1.0/1.18/1.87; F_TM 1.0, 1.189 + 0.0577·D, 1.401 + 0.0724·D, 1.525 + 0.0788·D, 2.306 + 0.1120·D.
  - Exchangers (p. 571): F_M (Table 22.25, all 20 numbers); F_L 1.25/1.12/1.05/1.00; F_P (Eq. 22.45), 100 to 2,000
    psig; A = 150 to 12,000 ft².
  - Vessels: F_M (Table 22.26, p. 576); W = π(D + t)(L + 0.8·D)·t·ρ with ρ = 0.284 lb/in³ (Eq. 22.59, p. 575).
  - Pumps: S = Q·H^0.5 (Eq. 22.13, p. 560); S = 400 to 100,000 (p. 561); F_T (Table 22.20, p. 561); F_M (Table 22.21,
    p. 562), which gear pumps also use (p. 563); Q = 10 to 900 gpm (p. 563); reciprocating 1 to 200 BHp and F_M
    1.00/1.15/1.50/2.20 (p. 564).
  - Motor: 1 to 700 Hp (p. 562); F_T 1.0/1.4/1.8 in the 3,600-rpm column (Table 22.22, p. 563).
- **G10, motor enclosure ranges.** Table 22.22 states 1 to 700 Hp for the open drip-proof motor, and 1 to 250 Hp for
  the totally enclosed and the explosion-proof ones. The set has one range, [1, 700] Hp, for all three (Q-B12).
- **G11, IDAES's own numbers, not in the book:** the exchanger `oversize` 1.1 (SSLW.py:393, "1.1 to 1.5"); the nine
  vessel densities other than carbon steel; the default `shell_thickness_in` 1.25.

#### 10.10.2 The rule, amended (R-895)

Each number the set takes from SSLW is ruled by the first rule that applies.
1. **IDAES = 3rd ed.:** keep it, and cite the 3rd-ed. page. A range that matches is verified-eligible.
2. **The 3rd ed. contradicts itself** (an equation and the book's own worked example differ): the example's value
   decides, if an independent relation corroborates it (the 4th ed., or a uniform offset that explains the
   difference). Keep IDAES's value if it is that value. This applies to the four exchanger intercepts only (G2).
3. **IDAES ≠ 3rd ed.:** IDAES erred in transcription. Correct the number to the 3rd-ed. value with `amended`
   (§10.4.1), cite the page, and record IDAES's value. This covers CE bases (G1) and range attachments (G6), not only
   coefficients.
4. **3rd ed. ≠ 4th ed., and IDAES = 3rd ed.:** an edition refit. Keep it, and note it.
5. **4th ed. ≠ IDAES + ln(567/500), and IDAES = 3rd ed.:** a 4th-ed. misprint. Keep it, and note it.

*Why rule 2 is added.* Rule 3 alone would cut every shell-and-tube exchanger by 21.2 % (× 394/500), to intercepts
that the book's own example does not use and that IDAES and the authors' 4th edition both correct.

#### 10.10.3 Per-number comparison

"=" means equal as decimals (sign as printed). "Shift" means IDAES + ln(567/500). "n.c." means QA1 did not compare it.
Classes: **M** match (rule 1); **S** stale-basis equation (rule 2); **E** IDAES error (rule 3); **R** refit (rule 4);
**P** 4th-ed. misprint (rule 5); **N** not in the book (G11). SSLW.py lines follow each path.

| # | Set path (entry; line) | IDAES | 3rd ed. (page, eq.) | 4th ed. | Class | Action |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `exchanger.shell_tube` `fixed_head.alpha2` (:402) | 0.8228 | 0.9228 (p. 571, 22.40) | 0.9228 | E | amend to 0.9228 (R-897) |
| 2 | … `floating_head.alpha1` (:401) | 11.9052 | Eq. 22.39: 11.667; Example 22.10: 11.9052 (p. 572) | shift | S | keep |
| 3 | … `fixed_head.alpha1` (:402) | 11.2927 | 11.0545 (22.40) | shift | S | keep |
| 4 | … `Utube.alpha1` (:403) | 11.3852 | 11.147 (22.41) | 11.5510 (shift gives 11.5110) | S, P | keep; Q-B1 closed |
| 5 | … `kettle_vap.alpha1` (:404) | 12.2052 | 11.967 (22.42) | shift | S | keep |
| 6 | … α2, α3 of every type except fixed-head α2 (:401–404) | 0.8709, 0.09005; 0.09861; 0.9186, 0.0979; 0.8709, 0.09005 | = (22.39–22.42; U-tube α3 printed 0.09790) | = | M | keep |
| 7 | … `material` A, B (10 pairs, :439–448); `CarbonSteelCarbonSteel.unity` 1 (:456) | | = (Table 22.25, p. 571; a = b = 0 gives F_M = 1, Eq. 22.44) | n.c. | M | keep |
| 8 | … `tube_length` F_L (:384) | 1.25/1.12/1.05/1.0 | = (p. 571) | n.c. | M | keep |
| 9 | … `pressure_a`, `pressure_ref_psig` (:494–496); range `pressure_psig` 100–2,000 (pinned :492) | | = (22.45, p. 571) | = | M | keep; the range stays pinned (an input range) |
| 10 | … `material_area_ref_ft2` (:460) | 100 | = (22.44) | n.c. | M | keep |
| 11 | … range `area_ft2` | 150–12,000 | = (p. 571) | = (p. 462) | M | add the 3rd-ed. page (C1 range) |
| 12 | … `oversize` (:393) | 1.1 | not in the book | — | N | keep |
| 13 | `vessel.vertical` `weight_limit."1"` α (:676) | 7.0132, 0.18255, 0.02297 | = (22.54, p. 574) | 7.1390 (shift), = | M | keep |
| 14 | … `weight_limit."1"` range (pinned :534, text "1:") | 1,000–920,000 | 4,200–1,000,000 (22.54) | = | E (attachment) | correct to 4,200–1,000,000 (R-898, as R-892) |
| 15 | … `weight_limit."2"` α (:677) | 7.2756, 0.18255, 0.02297 | = (22.57, p. 575: towers; Examples 22.13, 22.14) | 10.5449, −0.4672, 0.05482 | R | keep (reverses R-892) |
| 16 | … `weight_limit."2"` range (pinned :534, text "2:") | 4,200–1,000,000 | 9,000–2,500,000 (22.57) | = | E (attachment) | correct: primary [9,000, 2,500,000] (R-898) |
| 17 | … `platforms[0]` (:758–760) | 361.8, 0.7396, 0.70684 | = (22.56, p. 574) | 410 (shift), = | M | keep |
| 18 | … `platforms[1].a` (:765) | 309.9 | 300.9 (22.58, p. 575; Examples 22.13, 22.14) | 341 (= 300.9 shifted) | E | amend to 300.9 (R-897) |
| 19 | … `platforms[1].b_D`, `.b_L` (:766–767) | 0.63316, 0.80161 | = | = | M | keep |
| 20 | … ranges `platform_length_ft`, `platform_diameter_ft` (pinned :537) | 3–21/12–40; 3–24/27–170 | = (22.56, 22.58) | = | M | keep pinned |
| 21 | both vessels: `diameter_allowance` (:665); CarbonSteel `density_lb_in3` (:621) | 0.8; 0.284 | = (22.59, p. 575) | n.c. | M | keep |
| 22 | both vessels: `material` F_M (10, :621–630) | | = (Table 22.26, p. 576) | n.c. | M | keep |
| 23 | both vessels: the other nine densities (:622–630); `shell_thickness_in` (:513) | | not in the book | — | N | keep |
| 24 | `vessel.horizontal` α (:674) | 8.9552, −0.233, 0.04333 | = (22.53, p. 574; Example 22.12) | 5.6336, 0.4599, 0.00582 | R | keep |
| 25 | … range `weight_lb` (pinned :534, text "1:") | 1,000–920,000 | = (22.53) | = | M | keep pinned; note re-cited |
| 26 | … `platforms_horizontal` (:749) | 2005, 0.20294 | = (22.55, p. 574; Example 22.12, p. 577) | 2275, 0.2094 | R | keep (reverses R-891) |
| 27 | `column.trays` `tray_cost_a`, `_b` (:856); range `diameter_ft` (pinned :825) | 468.0, 0.1739; 2–16 | = (22.67, p. 577) | range = (p. 467) | M | keep |
| 28 | … `count_a`, `count_b`, `count_floor` (:842) | 2.25, 1.0414, 1 | = (22.68) | n.c. | M | keep |
| 29 | … F_TT (:804–806); F_TM (5 pairs, :817–821) | | = (p. 577) | n.c. | M | keep |
| 30 | `pump` entry `index_basis` (costing_base.py:66; `USD_CE394` at :1579, :1604) | 394 | 500 (pp. 561, 563; Example 22.6) | reciprocating: 500 implied (F6) | E | amend to 500 (R-896) |
| 31 | … Centrifugal a0–a2 (:1587–1589) | 9.7171, −0.6019, 0.0519 | = (22.14, p. 561; Example 22.6) | 12.1656, −1.1448, 0.0862 | R | keep |
| 32 | … ExternalGear a0–a2 (:1593–1595) | 7.6964, 0.1986, 0.0291 | = (22.21, p. 563) | 8.2816, −0.2918, 0.0743 | R | keep |
| 33 | … Reciprocating a0–a2 (:1599–1601) | 7.8103, 0.26986, 0.06718 | = (22.23, p. 563) | 7.9361 (from CE 500), = | M | keep; §10's basis-only amendment of a0 is withdrawn (row 30 states it) |
| 34 | … `head_exponent` (:1523) | 0.5 | = (22.13, p. 560) | n.c. | M | keep |
| 35 | … ranges `size_factor`, `flow_gpm`, `power_hp` | 400–100,000; 10–900; 1–200 | = (p. 561; p. 563; p. 564) | = | M | add the 3rd-ed. pages (C1 ranges) |
| 36 | … `pump_type_factor` F_T (6, :1555–1560); `type_factor_other` (:1571) | | = (Table 22.20, p. 561); gear and reciprocating costs carry no F_T (pp. 563–564) | n.c. | M | keep |
| 37 | … F_M centrifugal and gear (9 each, :1529–1537); reciprocating (4, :1541–1544) | | = (Table 22.21, p. 562; p. 563; p. 564) | n.c. | M | keep |
| 38 | `motor.electric` entry `index_basis` (costing_base.py:66; `USD_CE394` at :1647, :1661) | 394 | 500 (p. 562; Example 22.6, p. 565) | refit | E | amend to 500 (R-896) |
| 39 | … `eta` (:1638–1640) | 0.8, 0.0319, 0.00182 | = (22.18, p. 562; P_B 1 to 1,500 Hp) | = | M | keep |
| 40 | … `base` (:1655–1659) | 5.8259, 0.13141, 0.053255, 0.028628, −0.0035549 | = (22.19, p. 562; Example 22.6) | refit | R | keep |
| 41 | … range `motor_power_hp` | 1–700 | = (p. 562; Table 22.22, p. 563, open drip-proof) | = | M | add the 3rd-ed. page; G10 in the citation (Q-B12) |
| 42 | … `motor_type` F_MT (:1626–1628) | 1/1.4/1.8 | = (Table 22.22, 3,600 rpm) | n.c. | M | keep |
| 43 | `compressor` Centrifugal (:1156) | 7.58, 0.8 | = (22.36, p. 569) | refit | R | keep |
| 44 | … Reciprocating (:1157) | 7.9661, 0.8 | = (22.37) | 4.6762, 1.23 | R | keep |
| 45 | … Screw (:1158) | 8.1238, 0.7243 | = (22.38) | 8.2496 (shift), = | M | keep |
| 46 | … size variable and ranges | brake power; no range | P_C; 200–30,000 / 100–20,000 / 10–750 (p. 569; Example 22.9, p. 570) | = | M (confirms R-890) | primary `consumed_power_hp`, 3rd-ed. citation, C7 |
| 47 | … F_D `ElectricMotor` (:1136); F_M (:1145–1147) | 1; 1/2.5/5.0 | = (p. 569) | = | M | keep |
| 48 | `turbine` a, b (:1382–1383) | 530, 0.81 | = (Table 22.32, p. 593) | 600 (shift), = | M | keep |
| 49 | … range | none | 20–5,000 Hp (Table 22.32) | = | M (confirms R-893) | primary `power_hp`, 3rd-ed. citation, C7 |
| 50 | set `basis.index` (:343) | 500 | = (ch. 22) | 567 | M | keep |

The corrections are rows 1, 14, 16, 18, 30 and 38. Nothing else changes value. §10's adoptions of the horizontal
platforms (2275·D^0.2094), the tower-platform coefficient at CE 567 (341) and the 4th-ed. tower fit are withdrawn.

#### 10.10.4 Decisions against §10

- **Stands, now evidenced by the 3rd ed.:** D-B1 (R-890; G5); D-B4 (R-893; G8); fixed-head α2 = 0.9228 (G3, re-cited
  to p. 571); the vertical-vessel range [4,200, 1,000,000] lb (G6).
- **New: the pump and motor entries are at CE 500 (R-896).** Each entry's `index_basis.value` is amended from 394 to
  500. This replaces §10's basis-only amendment of the reciprocating pump's a0. That amendment is withdrawn, since it
  would state the same fact twice. Effect: × 394/500 = 0.788 on every pump and motor purchase cost. Electricity is
  unchanged.
  *Rejected:*
  - *Keep 394.* No source in hand states it. The 3rd ed. states 500 for each of the four correlations, and its
    Example 22.6 computes with them at 500. In the 4th ed. the authors shifted the reciprocating pump from CE 500
    (F6), while the same edition treats the exchanger block as CE 394 (G2). So the authors told the two blocks apart.
  - *Only the reciprocating pump at 500* (§10). The book says the same of all four.
  - *A basis-only amendment on each a0 and on `base[0]`.* That is four amendments for one fact, and the entry would
    still say 394.
  - *Deleting the entry `index_basis`.* That loses the record of IDAES's value.
  Residual risk: Q-B11.
- **Reversed: horizontal platforms (R-897).** Keep IDAES's 2005·D^0.20294 (G7). §10 adopted 2275·D^0.2094 because it
  took the two for the same fit with a misprint. The 3rd ed. shows a refit, and refits follow the 3rd ed. (Frank).
- **Changed: the tower-platform coefficient (R-897).** It is 300.9 at CE 500 (G7), replacing 309.9, with no
  `index_basis`. §10 had 341 at CE 567 (v_e 300.7055). The new value is the printed figure, not a rounded re-index.
- **Reversed: `weight_limit` "2" (R-898).** It keeps IDAES's (7.2756, 0.18255, 0.02297), which is the 3rd-ed. tower
  fit, with the primary range [9,000, 2,500,000] lb (p. 575, Eq. 22.57). The 4th-ed. tower fit is not used. §10
  rejected exactly this as unverifiable, and it is now verified. The default stays "1" (QA2, Q-B2).
- **Kept and closed:** the U-tube α1 11.3852 (G4; Q-B1) and the four exchanger intercepts (G2, rule 2).
- **Verification (R-899):** a `primary` range is the 3rd ed.'s; A49 runs on `seider3.yaml` and covers every number;
  §10.7 is closed. This outcome also closes Q-B4: no 4th-ed. value ships.

#### 10.10.5 Design deltas

##### 10.10.5.1 The amended numbers, exactly (replaces §10.4.2)

Citation prefix **P3** = "Seider, Seader, Lewin, Widagdo, Product and Process Design Principles: Synthesis,
Analysis, and Evaluation, 3rd ed. (Wiley, 2009), ch. 22, ". No amendment carries `index_basis`, so v_e = value for all
four.

| Path | value | replaces | v_e | Ruling | Citation tail (after P3) |
| --- | --- | --- | --- | --- | --- |
| `exchanger.shell_tube` `options.hx_type.choices.fixed_head.alpha2` | 0.9228 | 0.8228 | 0.9228 | R-897 | p. 571, Eq. (22.40); the same in the 4th ed., p. 462, Eq. (16.40) |
| `vessel.vertical` `coefficients.platforms[1].a` | 300.9 | 309.9 | 300.9 | R-897 | p. 575, Eq. (22.58); used in Examples 22.13 (p. 578) and 22.14 (p. 579) |
| `pump` `index_basis.value` | 500.0 | 394.0 | 500.0 | R-896 | pp. 561 and 563, Eqs. (22.14), (22.21), (22.23): pump costs indexed to 2006 (CE = 500), Figs. 22.3, 22.5, 22.6; Example 22.6, p. 564. IDAES labels them USD_CE394 (SSLW.py:1579, :1604) |
| `motor.electric` `index_basis.value` | 500.0 | 394.0 | 500.0 | R-896 | p. 562, Eq. (22.19): motor costs indexed to 2006 (CE = 500), Fig. 22.4; Example 22.6, p. 565. IDAES labels them USD_CE394 (SSLW.py:1647, :1661) |

`source_line` stays as it is on each number (`SSLW.py:402`, `SSLW.py:765`, `costing_base.py:66`), so B4 and A15 pair
them. The pump entry's basis reads:

```json
"index_basis": {"series": "CEPCI",
  "value": {"value": 500.0, "source_line": "costing_base.py:66",
            "amended": {"ruling": "R-896", "replaces": 394.0, "citation": "<P3>pp. 561 and 563, …"}}}
```

The reciprocating pump's a0 stays the plain IDAES number `{"value": 7.8103, "source_line": "SSLW.py:1599"}`.

##### 10.10.5.2 Loader (`assessment/cost/sets.py`, in C3′)

- `_resolve` adds the entry's `index_basis.value` amendment to `ResolvedEntry.amended` under the key
  `index_basis.value`. Every pump and motor item's report `source.amended` then lists it (§10.4.8). The basis the form
  uses is the effective value, 500.0.
- **A sixth refusal** joins A45's list: an `amended` object on an entry's `index_basis.value` that carries
  `index_basis` or `scale`. A basis has no basis of its own.
- Unchanged: v_e, the five refusals, the `checked_against` shape check, compressor-needs-motor, the 3× check.

##### 10.10.5.3 Ranges after the batch (replaces §10.4.3)

| Entry, range | min–max | Kind | Citation or note | `verified` |
| --- | --- | --- | --- | --- |
| exchanger `area_ft2`; pump `size_factor`, `flow_gpm`, `power_hp`; motor `motor_power_hp` | unchanged | primary | `QA1.patch` text, with its closing "(QA1; the coefficients are IDAES's, from the 3rd ed., ch. 22)" replaced by "(QA1); the same range in P3 + tail" (tails below) | true (C1), unchanged |
| compressor Centrifugal / Reciprocating / Screw `consumed_power_hp` (renamed from `power_hp`) | 200–30,000 / 100–20,000 / 10–750 | primary | P3 + "p. 569, Eq. (22.36): centrifugal compressor, valid from consumed power P_C = 200 to 30,000 Hp; the base cost includes an electric motor drive (design note §10, R-890)"; likewise Eq. (22.37), reciprocating, 100 to 20,000 Hp, and Eq. (22.38), screw, 10 to 750 Hp | false (C3′) → true (C7) |
| turbine `power_hp` (new) | 20–5,000 | primary | P3 + "p. 593, Table 22.32: gas expanders (pressure discharge), power extracted P = 20 to 5,000 Hp, C_P = 530 P^0.81 (design note §10, R-893)" | false (C3′) → true (C7) |
| vessel.vertical "2" `weight_lb` | 9,000–2,500,000 | primary | P3 + "p. 575, Eq. (22.57): towers, 9,000 < W < 2,500,000 lb, the fit of weight_limit '2' (design note §10.10, R-898)" | false (C3′) → true (C7) |
| vessel.vertical "1" `weight_lb` | 4,200–1,000,000 | pinned SSLW.py:534, text "2: 4200 to 1M lb" | note: "IDAES's docstring labels this range '2'; the 3rd ed. (p. 574, Eq. 22.54) gives it to the vertical-vessel fit, weight_limit '1' (design note §10.10, R-898)" | — |
| vessel.horizontal `weight_lb` | unchanged | pinned SSLW.py:534 | note: "the 3rd ed. gives this range to horizontal vessels (p. 574, Eq. 22.53)" | — |
| every other pinned range | unchanged | pinned | unchanged; A49 checks the bounds against the 3rd ed. | — |

Tails for the five QA1 ranges: `area_ft2` "p. 571, Eqs. (22.39)-(22.42)"; `size_factor` "p. 561, Eq. (22.14)";
`flow_gpm` "p. 563, Eq. (22.21)"; reciprocating `power_hp` "pp. 563-564, Eq. (22.23)"; `motor_power_hp` "p. 562,
Eq. (22.19), and Table 22.22 (p. 563), which states 1 to 250 Hp for the totally enclosed and explosion-proof
enclosures (not enforced; design note §10.10, Q-B12)". Frank pre-approved these additions; the bounds and flags do
not change.

Primary ranges: 10 (five verified, five to verify).

##### 10.10.5.4 `source.checked_against`

`{"citation": "Seider, Seader, Lewin, Widagdo, Product and Process Design Principles: Synthesis, Analysis, and
Evaluation, 3rd ed. (Wiley, 2009), ch. 22", "scope": "every Seider number in this set compared by page and equation
(design note §10.10; benchmarks/e01/cost_hand/seider3.yaml); individual numbers and bounds only, no text or table
reproduced; the five QA1 ranges are also checked against the 4th ed. (Wiley, 2017), ch. 16"}`.
`scripts/e01_d04_inventory.py` carries it into `docs/e01-data-licences.json` (as §10.4.1).

##### 10.10.5.5 §10.4.6 amended: what `primary` means

A `primary` range is the range that the 3rd ed. (2009), ch. 22 prints for the same equation, cited by page and
equation. That edition is the one the set transcribes. The five QA1 ranges also keep their 4th-ed. citation. Primary
ranges are still for size quantities only (Q-B3), and A48 is unchanged.

##### 10.10.5.6 §10.4.7 amended (departures from IDAES)

- Item 9 is replaced: **Amended numbers.** Two numbers and two entry bases differ from the pinned source: fixed-head
  α2 (0.9228), the tower-platform coefficient (300.9), and the pump and motor bases (CE 500, not 394). Each carries
  `amended` (§10.10.5.1).
- Item 11 is restated: **Vessel weight ranges.** The docstring's two ranges go to the fits the 3rd ed. gives them to,
  and the tower fit "2" gets the book's tower range.
- Items 8 and 10 stand.

##### 10.10.5.7 Independent expectations (replaces the B4, A15 and A49 parts of §10.4.9)

**B4 (`cost_hand.py`)**, against held `c73a0721`, is transcribed from this subsection and the book, never from the
set file:
- all three pumps and the motor at CE 500. No 500/394 factor anywhere, and every base-cost key is `C_B_CE500`;
- `PL_HORIZONTAL` = (2005, 0.20294), IDAES's;
- `PL_VERTICAL` piece 2 coefficient = 300.9;
- vessel "2" α = (7.2756, 0.18255, 0.02297); `VESSEL_W_RANGE` "1" = (4,200, 1e6) and "2" = (9,000, 2.5e6);
- as `c73a0721`: the compressor on P_C with the N rule, the turbine on `size_targets(20, 5000, parallel=True)`, and
  fixed-head α2 0.9228 with its `fixed_head` case. The A44 vessel hand case is unchanged.

**A15 (`idaes_crosscheck.py`)**, against held `02477928`:
- every pump and motor case: IDAES's capital × 394/500. IDAES converts its USD_CE394 base cost into CE 500 by
  500/394, and the set's basis is now 500 throughout;
- the horizontal platform term has no factor, and the "2" vessel has no factor;
- the piece-2 platform term is × 300.9/309.9;
- the compressor, the turbine and the fixed head stay as in `02477928`;
- re-run in `/home/frankp/.cache/idaes-2.13/venv`. The YAML records the raw IDAES value, the factor and the compared
  value.

**A49 (`benchmarks/e01/cost_hand/seider3.yaml`, `tests/test_e01_b_seider3.py`)** replaces `seider4.yaml` and
`test_e01_b_seider4.py`, which are not shipped. It is typed from the pages of §10.10.1: individual numbers, each with
page and equation, never text.
- A record holds the set path (entry id + the path as `ResolvedEntry.amended` writes it), the book value as a
  decimal string with its printed sign, the page, the equation or example, and a relation. One record may list
  several (path, book) pairs under one page and relation.
- `same`: Decimal(v)·sign = Decimal(book), with `sign` the sign the form applies (as held C4 did).
- `shift`: Decimal(v) − Decimal(book) = Decimal("0.2382"), for the four exchanger α1 only, noted "ln(500/394) =
  0.238257 truncated; design note §10.10 G2". The floating-head α1 also has a `same` record against Example 22.10's
  11.9052 (p. 572).
- `amended`: `value` = book, `replaces` = IDAES's value (typed from SSLW.py), and the citation contains the page.
  Applies to fixed-head α2 and `platforms[1].a`.
- `basis`: the entry's effective `index_basis` = 500 = the book's stated CE, with `replaces` 394. Applies to the pump
  and the motor.
- `range`: min and max exactly equal to the book's bounds. Applies to every primary range, and to every pinned range
  whose bounds the book prints (exchanger pressure, vertical "1", horizontal, the platform D and L pieces, tray D).
  One exception, by design: `platform_length_ft` piece 2's min is 40, IDAES's switch between Eqs. 22.56 and 22.58
  (SSLW.py:537), not the book's 27. Its record asserts piece 1 = (12, 40), piece 2's max = 170, and
  27 ≤ piece 2's min = piece 1's max.
- `not_in_book`: the path and a reason (G11).
- **Completeness:** every number object in the set (each `{value, source_line}`, including both bases), and every
  range, is covered by exactly one record or a `not_in_book` line. Every amended number has an `amended` or `basis`
  record. No record names a path the set lacks.

#### 10.10.6 Assertions and gates (amends §10.5)

- **A49 (replaced):** every relation of §10.10.5.7 holds, and so does its completeness.
- **A51 (amended):**
  - the six refusals (§10.4.1's five and §10.10.5.2's);
  - v_e bitwise equal to `value` for each of the four amendments;
  - resolved `pump` and `motor.electric` entries list `index_basis.value` in `amended`, and resolve on basis 500.0;
  - the tower no-undercut clause is dropped. Fit "2" increases with W for W ≥ 1 lb, since α2, α3 > 0.
- **A44, A48, A50, A14, A15** stand as in §10.5. The A48 tripwire is 5 after C6′ and 0 after C7.
- **Gates** as §10.5. A `reviewer` pass is needed after C6′, since numerics change.

#### 10.10.7 Revised work order (replaces §10.6.1–§10.6.3; one build-lane engineer, about 150k context)

**Baseline:** `wp/E01b` at `15307c6a`. Held work is on local `wip/E01b-held` (`e37dacb1` C3, `c73a0721` C4,
`02477928` C5, `f43f7dab` C6 WIP). Its forms, test machinery and A15 script were built correctly for every unchanged
ruling. Its set data, B4 constants, `seider4.yaml`, fixtures and pins carry §10's 4th-ed. numbers and must not be
taken as they are.

1. **C3′. Forms, loader delta, data.**
   - `git checkout e37dacb1 -- src/openflowsheet/assessment/cost/forms.py src/openflowsheet/assessment/cost/contributor.py`
     takes form VI (P_C, N rule), form VII (parallel, floor) and the report's `amended` block. Amendment 1 changes
     none of them.
   - `sets.py`: §10.10.5.2.
   - The set file (one file; the `_data` path is a symlink), edited by hand from its `15307c6a` state:
     §10.10.5.1's four amendments, §10.10.5.3's ranges, citations and notes, the compressor key rename, the turbine
     range, and §10.10.5.4. Do not take `e37dacb1`'s JSON hunk. Its range objects may serve as a structural template,
     but every value and citation comes from this subsection.
   - Re-log `e37dacb1`'s still-valid DECISION lines (report block only when present; form VI's domain refusals),
     with the citations re-pointed to the 3rd ed.
   - *Acceptance:* the loader parses the set, and every entry resolves on its defaults.
2. **C4′. B4 and A49.**
   - `git cherry-pick -n c73a0721`, then apply §10.10.5.7's B4 deltas.
   - `git rm` `seider4.yaml` and `test_e01_b_seider4.py`. Add `seider3.yaml` and `test_e01_b_seider3.py`; the held
     test's `same`/`sign` and completeness code may be reused.
   - Regenerate `cost_hand.yaml` with its `main()`.
   - *Acceptance:* `cost_hand.py --check` exits 0; A49 passes; the `cost_hand.yaml` diff against `15307c6a` contains
     only the moves of item 7 below.
3. **C5′. A15.**
   - `git cherry-pick -n 02477928`, then apply §10.10.5.7's A15 deltas, and re-run.
   - *Acceptance:* every case is within rel 1e-9 of IDAES with the factors applied. The held build measured at most
     1.0e-14.
4. **C6′. Tests, fixtures, pins, manifest generator.**
   - `git checkout f43f7dab -- tests/test_e01_a48_tripwire.py tests/test_e01_a_contributor.py tests/test_e01_a_cost.py tests/test_e01_integration.py`,
     then adapt it:
     - A51 as in §10.10.6;
     - the primary-flag assertion: 10 primary ranges, 5 verified (C1), and 5 unverified (three compressors, the
       turbine, "2");
     - the tripwire at 5;
     - ruff E501/format clean.
   - Keep the P2 drum's `floor` assertion (M1, unchanged) in its own commit, as on the held branch.
   - Regenerate the four report fixtures with `_write()`; do not take `f43f7dab`'s. Pin the new sha256 in
     `tests/test_t08_w2_inventory.py`, in `docs/e01-data-licences.json` (through `scripts/e01_d04_inventory.py`) and
     in `docs/E01A_DECISIONS.md` (appended, superseding the old hash, with a pointer to §10.10).
   - Extend `scripts/e01_evidence_manifest.py` for S12b: package id, and A49 (seider3), A50 and A51 cited by test
     name.
   - Run the E01 tests once, and write the moved-number audit (old → new per item 7) in `docs/E01B_DECISIONS.md`.
5. **C7. The verification commit**, as §10.6.1 item 7: §10.10.8's five flags, the tripwire at 0/`pass` with its
   negative case, and the sha256 re-pinned. It is prepared as `QA1b.patch` and committed only on Frank's relayed
   approval.
6. **Files:** §10.6.2's list, plus `scripts/e01_evidence_manifest.py`, `benchmarks/e01/cost_hand/seider3.yaml` and
   `tests/test_e01_b_seider3.py`. `seider4.yaml` and its test are removed.
7. **What moves, against `15307c6a`** (any other moved number: stop and escalate):
   - **M1** (unchanged from §10): `vessel.vertical` "1" below 4,200 lb floors at C_v = 25,209.24 (CE 500). Measured
     on the held branch:
     - P1 TH-R1 `D.drum`: C_P1 16,456.63 → 29,931.56;
     - P3 M1 `S02.shell`: `units:1` → `floor`, with C_v 22,246.06 → 25,209.24 and C_P1 30,841.27 → 33,804.45;
     - P2: the drum floors, so every P2 capital row is floored. P2 is not resized (§9.7).
   - **M2′** `weight_limit` "2", registered cases only: below 9,000 lb, C_v floors at 51,120.57. Before, the power
     law ran down to 4,200 lb, where it gave 32,773.18. From 1,000,000 to 2,500,000 lb the cases are now in range.
     In-range values are unchanged.
   - **M3′** platform piece 2 (40 < L ≤ 170 ft), registered cases only: C_PL × 300.9/309.9 = 0.97095837. No P1–P3
     item uses piece 2: on the held branch, where §10's M3 applied, `S02.shell`'s C_PL of 8,595.21 did not move.
   - **M4′** every pump (centrifugal, gear, reciprocating) and every motor: C_P × 394/500 = 0.788, to rel ≤ 1e-15
     against old × 0.788. This covers P1 TH-C1 `P` and its drive, TH-R1's pump and drive, every pump and drive in P2
     and P3, every B4/A15 pump and motor case, and every quantity derived from them. Electricity is unchanged.
   - **M5** compressors (D-B1), **M6** turbine and **M7** fixed head: as §10.6.3.
   - **M8** provenance: citations, flags, notes, and `source.amended` on fixed-head items, on every vertical-vessel
     item (the entry carries `platforms[1].a`) and on every pump and motor item; the set's sha256.
   - **Do not move:** horizontal vessels (shell and platforms), floating-head, U-tube and kettle exchangers, trays,
     vertical "1" in range, "2" in range, the turbine in range.
   - *Against the held branch* (for auditing cherry-picked numbers): the horizontal C_PL returns to IDAES's (undo
     × 1.000585·D^0.00646); piece 2 goes × 1.000647 relative to held (0.97095837/0.97033065); "2" returns to IDAES's
     fit; every pump and the motor go × 0.788, where held moved the reciprocating pump only.
8. **The A48 count after C6′ is 5:** the three compressors, the turbine, and "2". After C7 it is 0.
9. **Acceptance additions** to §10.6.4:
   - `grep -n -E '2275|0\.2094|10\.5449|0\.4672|0\.05482|567' assessment/cost/sslw-idaes-v1.json
     benchmarks/e01/cost_hand/cost_hand.py benchmarks/e01/brightway/idaes_crosscheck.py` finds no coefficient,
     factor or basis. A hit inside a hash or a line number is noted in the decisions log, not "fixed".
   - The S12b manifest run (the extended generator, command in `docs/E01B_DECISIONS.md`'s WO-I1 handoff) covers G6
     (A33–A36 in the nlp env). If A33 or A36 fails, stop and escalate: the pump-cost move may reach P2's objective.

#### 10.10.8 The `verified` flags C7 may set (and no others)

1. `compressor` `options.compressor_type.choices.Centrifugal.ranges.consumed_power_hp.source.verified`
2. `compressor` `options.compressor_type.choices.Reciprocating.ranges.consumed_power_hp.source.verified`
3. `compressor` `options.compressor_type.choices.Screw.ranges.consumed_power_hp.source.verified`
4. `turbine` `ranges.power_hp.source.verified`
5. `vessel.vertical` `options.weight_limit.choices."2".ranges.weight_lb.source.verified`

Each one's bounds and citation are exactly as in §10.10.5.3, and A49's `range` record checks the bounds.

#### 10.10.9 Open questions (replaces §10.8; work proceeds on the default)

| # | Question | Needs | Default |
| --- | --- | --- | --- |
| Q-B1 | U-tube α1 | — | **Closed**: keep 11.3852 (G4) |
| Q-B2 | `column.shell` default fit "2" (now verified as the 3rd ed.'s tower fit; × 1.300 on every column shell C_v, moves P3) | Frank's preference | No: "1" for every family (QA2) |
| Q-B3 | Enforce the horizontal platform range 3 < D < 12 ft | Frank's preference | Not enforced |
| Q-B4 | 4th-ed. values in the wheel | — | **Closed**: none ships |
| Q-B5 | η_m above 1,500 hp brake (the 3rd ed. states the same range) | Fact | Extrapolate (0.9354–0.9398 up to 30,000 hp) |
| Q-B6 | Scratch IDAES env | — | **Closed**: `/home/frankp/.cache/idaes-2.13/venv` |
| Q-B7 | Approval of the five flags of §10.10.8 | Frank | C7 held as `QA1b.patch`; G10 pending |
| Q-B8 | `set_id` with amendments | Frank's preference | Keep `sslw-idaes-v1` |
| Q-B9 | Liquid expanders (3rd ed.: 150–2,000 Hp, 1,400·P^0.70 at CE 500) | Frank's preference | Not offered |
| Q-B10 | Trays and factor tables | — | **Closed**: all equal (G9) |
| Q-B11 | Were the 3rd-ed. pump and motor coefficients really re-indexed to CE 500? The exchanger block shows the edition could carry stale CE-394 numbers (G2) | Fact: the 2nd edition's (2004) ch. 16 pump and motor equations, or the IDAES commit that set `USD_CE394` | **CE 500 ships.** If the 2nd ed. prints the same coefficients at CE 394, revert R-896 by a new ruling (two amendments; fixtures regenerated) |
| Q-B12 | Per-enclosure motor ranges (1–250 Hp for totally enclosed and explosion-proof) | Frank's preference | Not enforced; stated in the motor range's citation |

**No question for Frank blocks C3′–C6′.** Q-B7 is the approval step C7 always needed.

#### 10.10.10 Records

- Register: R-895 (the rule and the 3rd ed. as authority), R-896 (pump and motor at CE 500), R-897 (the amended
  coefficients, which supersedes R-891's adopted list), R-898 (vessel weight fits, which supersedes R-892's "2"
  ruling), R-899 (verification, which supersedes R-894). R-890…R-894 each gain a dated "Amended by" line.
- §10.7 is closed. The Towler–Sinnott citation that §10.9 requested for F5 is no longer load-bearing, since both
  editions print 0.9228. No new reference is needed: `seider2009product` is already filed.
