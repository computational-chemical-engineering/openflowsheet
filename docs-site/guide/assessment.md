# Cost estimation and LCA

An **assessment** computes what a solved flowsheet's equipment costs, what it costs to run, and
its life-cycle impact. Each figure is an explicit function `y = G(x, d; θ)` of the verified state
`x`, the pinned inputs `d` and the assessment's own data `θ` (correlation coefficients, prices,
unit scores). It is evaluated after the solve and is never part of the compiled problem, so
attaching an assessment changes neither the solution, nor its certificate, nor the run's replay
identity.

Because `G` is built by the same compiler as the flowsheet's equations, each output has exact
derivatives with respect to the state, the specifications and every input, so a cost or an impact
can be a study output or an optimisation objective (see
[below](#cost-and-impact-in-studies-and-optimisation)).

The assessment layer is a Python library layer, `openflowsheet.assessment`
([API](../api/assessment.md)). The CLI, HTTP and MCP interfaces do not offer it yet. The
[cost and climate impact example](../examples/rankine-cost-and-gwp.ipynb) runs one end to end. The
design is ADR 0052 and its design note, `docs/derivations/E01-design.md`.

!!! warning "Assessment evidence is neither verification nor validation"
    Every report closes with this statement: *"Assessment evidence: an estimate under the stated
    basis, correlations, data and regimes. It is not numerical verification of the flowsheet and
    not empirical validation."* A cost estimate carries an accuracy class. An impact is only as
    good as the unit scores behind it.

## The assessment document

An assessment is a JSON document validated against `schemas/assessment.schema.json`:

| Section | Holds |
| --- | --- |
| `basis` | currency and year of the estimate; optional location factor, escalation series and exchange rates |
| `operation` | operating hours per year, lifetime in years, discount rate |
| `correlation_set`, `data` | the cost correlation set, and any user-supplied sets, index series or LCA tables (each by id and SHA-256) |
| `items` | per costed item (named by unit id; `P.drive` is unit `P`'s motor): its bare-module factor `F_BM`, an optional correlation choice, a quote, or an `exclude` with its reason |
| `utilities`, `materials` | each utility's kind, temperatures and price; each raw material or product by connection, with its price; each with optional LCA exchanges |
| `capital`, `fixed_opex` | the capital chain from bare-module costs to total capital; fixed operating cost lines such as maintenance |
| `lca` | the unit-score tables, direct-emission factor tables, impact categories, functional unit and allocation |
| `derived`, `uncertainty` | derived ratios of outputs; relative ranges of inputs for the uncertainty propagation |

`load_assessment` validates a document and gives it an identity, its canonical SHA-256.
`AssessmentProgram.build` plans it against a solved flowsheet and returns a program or a typed
refusal. `program.report(...)` writes a report valid against
`schemas/assessment-report.schema.json`.

## What is estimated

**Sizing.** Each unit model maps to a sizing family, which turns the unit into its costable items:

| Unit models | Family | Size |
| --- | --- | --- |
| `thermal.heater`, `syn001.tp_heater`, `c1.tp_heater` | utility exchanger | area from the duty, `U` and the mean temperature difference to the selected utility |
| `syn001.heat_exchanger` | process exchanger | area from the duty, `U` and the two streams' temperatures |
| `thermal.flash`, `syn001.tp_flash`, `syn001.ph_flash`, `c1.tp_flash` | drum (vertical by default), with its duty exchanger | vessel dimensions and weight |
| `thermal.pump`, `syn001.liquid_pump` | pump, with its electric motor (`.drive`) | volumetric flow, head, power |
| `thermal.compressor`, `thermal.turbine` | compressor or turbine | power |
| `syn001.column` | column shell and trays; condenser and reboiler as utility exchangers | diameter at the controlling tray, height, number of actual trays; the duties |
| `syn001.kinetic_cstr`, `syn001.conversion_reactor` | reactor vessel, with its duty as an exchanger | volume |
| valves, mixers, splitters, feeds, sinks | no equipment | — |

Any other model is refused `NO_SIZING_MODEL` unless the document gives a quote or excludes it.
The mean temperature difference is Underwood's cube-root approximation of the log mean: it is
smooth everywhere, including where the two end differences are equal, and departs from the exact
log mean by +0.0035 % at an end-difference ratio of 2, +0.38 % at 10 and +2.56 % at 50. An
exchanger with a phase change on its process side carries the limitation
`LMTD_ACROSS_PHASE_CHANGE`.

**Capital cost.** A correlation gives each item's purchased cost at its size. The bare-module
cost is the purchased cost times the item's `F_BM`, which the document states. A capital chain
turns the sum of bare-module costs into the total capital. Two chains ship: `bare-module-total`
(the total is the sum) and `ebtf-prisma-v1` (EPC = 1.10 · 1.14 · 1.30 · TDC; CAPEX = 1.07 · EPC,
after the EBTF method as given in the PrISMa supporting information). A document may also state
its own chain. A quote replaces one item's correlation.

**Operating cost.** Each exchanger is served by a utility selected by a stated rule (the
admissible utility by temperature). Its cost is the duty times the utility's price. Electricity
is netted across the flowsheet: a turbine that generates more than the motors draw gives a credit
(limitation `ELECTRICITY_NETTED`), and the generator itself is not costed
(`GENERATOR_NOT_COSTED`). Materials are priced by mass (total or of one component): raw materials and
waste as costs, products as revenue. Fixed lines are stated amounts or fractions of a capital
figure; none is assumed (`FIXED_OPEX_UNDECLARED` when there are none).

**Annual figures.** The capital charge is the total capital times the capital recovery factor of
the discount rate and the lifetime. The total annualised cost `tac` is the capital charge plus
the operating cost. With a functional unit declared (a stream's mass, a component's mass or
moles), the report also gives its annual amount and the levelised cost per unit of it, `lcox`,
besides revenue and profit.

## Correlations and their provenance

Correlation forms are code; coefficients are data, and every number has a source. The shipped
set is **`sslw-idaes-v1`**: the cost correlations of Seider, Seader, Lewin and Widagdo,
*Product and Process Design Principles: Synthesis, Analysis, and Evaluation*, 3rd ed. (Wiley,
2009), ch. 22. The set has eight entries: shell-and-tube exchanger, vertical vessel, horizontal
vessel, column trays, pump, electric motor, compressor and turbine.

- **Transcribed** from the IDAES process modelling framework's `SSLW.py` (idaes-pse 2.13.0,
  BSD-3-Clause; the file's SHA-256 is recorded). Every coefficient carries the source line it was
  read from.
- **Checked** against the book, number by number, by page and equation. Each validity range
  cites its page, for example the shell-and-tube exchanger's 150–12,000 ft² (p. 571,
  Eqs. 22.39–22.42), the electric motor's range (p. 562, Eq. 22.19) and the gas expander's
  20–5,000 hp (p. 593, Table 22.32).
- **Reported** per item: the set, the entry, the form, the citation, the source lines, the
  ranges, the options and which options were defaulted.

The cost basis of `sslw-idaes-v1` is a CEPCI of 500, mapped to the year 2006 for escalation by
public indices (limitation `INDEX_BASIS_MAPPED`).

Turton's correlations are not shipped; a user may register a set of their own. The `power-law-v1`
form is provided for user data and quotes. CEPCI values are not shipped (they are not openly
licensed), but a user may supply them as a series.

**Regimes.** A correlation has a validity range, and an exchanger may be served by more than one
utility. Choices like these are discrete. An assessment never smooths them: it holds a
**regime** (the size piece, the number of parallel units, the utility, the service, the
controlling column stage) selected by a stated rule at the solved state. Within its admissible
set every regime is the true cost of a realisable design, so its derivatives are exact. Below a
correlation's smallest size the item is in its `floor` regime: the smallest unit is bought, at a
constant cost whose derivative is exactly zero. Above the largest size the item is split into
parallel units, or refused `CORRELATION_OUT_OF_RANGE`.

## Cost basis and indices

Only public indices ship:

| Series | Use | Source |
| --- | --- | --- |
| `bls-ppi-wpu11-annual-v1` | escalation in US dollars | U.S. Bureau of Labor Statistics, PPI WPU11 (machinery and equipment), via FRED |
| `eurostat-ppi-c28-ea-annual-v1` | escalation in euros | Eurostat, producer prices NACE Rev. 2 C28, euro area |
| `frb-g5a-annual-v1` | exchange rates | Federal Reserve Board, G.5A annual rates, via FRED |

A cost is escalated in its source currency, then converted at the target year's exchange rate,
then multiplied by the location factor. Each report records the series and the index values used.

## Accuracy class and uncertainty

**The accuracy class** of the estimate is the largest AACE class over the costed items, read
from the correlation set's entries or from a quote. An excluded item does not count. An item
computed outside its correlation's range (`CORRELATION_EXTRAPOLATED`) makes the class `none`.
The ranges follow AACE recommended practice 18R-97:

| Class | Low | High |
| --- | --- | --- |
| 5 | −20 % to −50 % | +30 % to +100 % |
| 4 | −15 % to −30 % | +20 % to +50 % |
| 3 | −10 % to −20 % | +10 % to +30 % |
| 2 | −5 % to −15 % | +5 % to +20 % |
| 1 | −3 % to −10 % | +3 % to +15 % |

`sslw-idaes-v1` is class 4.

**Propagation.** Every input with a declared relative range is propagated to first order. Each
correlation entry carries its own range, and the document may add ranges, for example on a
price. Each output gets two figures, each labelled with its assumption:

- a worst-case interval, with each input at its own adverse bound (conservative for any
  correlation between inputs);
- a standard deviation, with the inputs independent and uniform on their ranges.

**Completeness.** A total over an item that was refused is not reported. Every output that
depends on the item is `null`, and the report's status is `PARTIAL`. An `exclude` with a reason
restores the totals and lists the exclusion. The status values are `COMPLETE`, `PARTIAL` and
`REFUSED`.

## Life-cycle assessment

The impact is linear in the inventory at the flowsheet's boundary:

    h = Q · a(x) + C · b(x)

- `a(x)` holds the **technosphere exchanges**. Each utility and material may declare exchanges
  with background activities, as an amount per unit of its boundary quantity (energy, mass or
  electricity; generation and substitution are negative).
- `b(x)` holds the **direct emissions**: a stream with the role `emission` maps each component
  to a biosphere flow.
- `Q` is a **unit-score table**: the impact of one unit of each background activity, computed
  once, offline, and frozen.
- `C` is a **direct-factor table**: characterisation factors for the biosphere flows.

The outputs are `impact.<category>.rate` (per second), `.annual` and `.per_fu` (per functional
unit, a stream's mass or a component's mass). Allocation may be `none`, `substitution`, a
constant `factor`, `mass` or `economic`. The unit scores are inputs of the compiled function, so
the derivative of an impact with respect to a score is that activity's inventory amount. A
contribution analysis therefore comes with every evaluation. Background uncertainty is not
propagated (`LCA_BACKGROUND_UNCERTAINTY_NOT_PROPAGATED`), and capital goods are outside the
foreground (`LCA_CAPITAL_GOODS_EXCLUDED`).

**What ships.**

| Table | Contents | Rights |
| --- | --- | --- |
| `gwp100-ipcc-ar6-v1` | direct factors, climate change, GWP-100 (kg CO2-eq): CO2 fossil 1, CH4 fossil 29.8, CH4 non-fossil 27.0, N2O 273; CO2 non-fossil 0 under the stated cut-off convention for biogenic carbon | five values from IPCC AR6 WG1 (Forster et al., 2021, ch. 7, Table 7.15, p. 1017), with their citation |
| `test-background-v1` | a **synthetic** three-activity background (electricity, heat, a chemical) and its hand-derived unit scores, for tests and examples | Apache-2.0; not the inventory of any real process |

**What never ships:** anything derived from ecoinvent, and the EF 3.1 characterisation factors.
No unit-score table of a real background ships today; an open one (USLCI) would ship only with a
recorded public-domain or CC0 licence.

**Restricted data.** A table whose rights forbid redistribution is used where it lies, in the
user's own directory. Reports, replay bundles, fixtures and evidence refer to it by id and
SHA-256 only, so its scores never leave the user's project. An impact computed from such a table
is a result of the user's licensed use. Together with the reported inventory, it may reveal the
scores of the activities used. Every such impact therefore carries the limitation
`LCA_RESTRICTED_DATA_DERIVED(<table_id>)`; its value is not redacted.

### Building a table: the `lca` extra

```bash
pip install "openflowsheet[lca]"
```

The extra installs Brightway's `bw2data` and `bw2calc`; the repository's
`scripts/build-lca-env.sh` builds the audited environment. It adds an offline adapter,
`openflowsheet.assessment.lca.brightway`:

- `build_unit_score_table(project, activities, categories, rights, table_id=...)` computes the
  score of one unit of each activity in a Brightway project you have prepared, and records the
  versions and database metadata.
- `build_direct_factor_table(...)` takes a method's factors for the biosphere flows you declare.
- `foreground_check(...)` scores a foreground activity with Brightway, as an independent check.

The adapter never downloads a database. You prepare the project yourself: ecoinvent under your
own licence, or USLCI through the Federal LCA Commons. Declare the table you built in the
document under `data.tables`, with its path and SHA-256. Brightway never runs inside a solve, an
optimisation or a replay: without the extra, assessments evaluate from their tables as before,
and only the adapter's calls return `UNSUPPORTED(LCA_ENGINE_UNAVAILABLE)`.

## Cost and impact in studies and optimisation

**Sensitivities.** `assessment_sensitivity` gives `dy/dp` for assessment outputs at a certified
solution, by the chain rule through the flowsheet: `dy/dp = ∇ₓy · dx/dp + ∂y/∂p`. The flowsheet's
own sensitivity `dx/dp` comes from the studies layer, and `revision_sensitivity_host` builds its
host for any solved revision. An output that does not depend on the state (every item at its
`floor`, say) is labelled `STATE_INDEPENDENT`. An output next to a regime boundary carries
`REGIME_BOUNDARY_ACTIVE`, because its derivative there is one-sided. The
[example](../examples/rankine-cost-and-gwp.ipynb) computes the impact's sensitivity to the boiler
temperature.

**Optimisation.** A study names an assessment output as `assessment:<output_id>` in the
objective or the constraints of the general NLP (the `nlp` extra; see
[Studies and optimisation](studies.md)):

- The outputs enter the NLP as grey-box outputs with exact derivatives.
- The held regime's admissibility rows become inequalities.
- A candidate is verified only if re-solving it keeps the regime; otherwise it is refused
  `ASSESSMENT_REGIME_CHANGED` (check V7).
- An objective far from unit scale is refused `ASSESSMENT_OBJECTIVE_UNSCALED`, with the scale to
  divide by. It is never rescaled silently.

The rules:

- The NLP host is the SYN-001 flowsheet; an NLP over a general revision flowsheet is not offered
  yet.
- Assessment inputs (prices, coefficients) are never decision variables
  (`UNSUPPORTED(ASSESSMENT_PARAMETER_DECISION)`).
- A trust-region study cannot take an assessment objective
  (`UNSUPPORTED(ASSESSMENT_OUTPUT_IN_TRF)`).
- `KKT_POINT_VERIFIED` means a KKT point of the held-regime problem. The NLP holds every regime of
  the program, which is sound but can be more restrictive than an objective needs.
