# Examples

Each example is a Jupyter notebook in the repository's
[`examples/`](https://github.com/computational-chemical-engineering/openflowsheet/tree/main/examples)
directory. The pages here are the notebooks **executed when the site was built**, so their output
is what the software computes today. The test suite runs them again and compares every number a
notebook's closing cell states in bold with the value it computes, so a page cannot drift from the
code.

| Example | What it shows | Needs |
| --- | --- | --- |
| [Rankine cycle](rankine-cycle.ipynb) | A once-through Rankine cycle on IAPWS-95 water; reading the solved state and the certificate | — |
| [Refrigeration cycle](refrigeration-cycle.ipynb) | An R134a vapour-compression cycle on CoolProp, and its coefficient of performance | the `coolprop` extra; without it the notebook says it is skipped |
| [Methanol–water column](methanol-water-column.ipynb) | A 20-stage distillation column on the Wilson γ–φ basis | — |
| [What-if studies and refusals](what-if-and-refusals.ipynb) | A sweep by edits; a state outside the domain; a unit on a basis it does not support | — |
| [Cost and climate impact](rankine-cost-and-gwp.ipynb) | The Rankine cycle's capital and operating cost, its impact on a synthetic background, and their sensitivity to the boiler temperature | a source checkout (it reads the Rankine change set) |

The notebooks solve through the public application contract only; the cost and impact example
then uses the assessment layer (`openflowsheet.assessment`), which reads the solved state. Run one locally from a source checkout:

```bash
pip install jupyterlab
jupyter lab examples/rankine-cycle.ipynb
```

!!! note "Demonstrations, not evidence"
    An example demonstrates the software on a stated configuration. It is never validation
    evidence: what the project has and has not shown is recorded in its evidence manifests and
    summarised in [Limitations and support](../guide/limitations.md).
