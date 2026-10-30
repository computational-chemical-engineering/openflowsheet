# `examples/`

Executable tutorials and the inspectable end-to-end demonstrations of the runtime
(blueprint §15, §16). An example here must run against the public application contract only,
with no private path that bypasses validation. The one addition is the assessment layer
(`openflowsheet.assessment`, E01), which no transport offers yet: `rankine-cost-and-gwp.ipynb`
solves through the contract and then assesses the solved state read from the run's replay bundle.

**The notebooks.** Five Jupyter notebooks, rendered with their output on the documentation site
(`docs-site/examples/`, built by `.github/workflows/site.yml`). Outputs are not committed; the site
build executes them, and `tests/test_doc_examples.py` executes them again and compares each number a
notebook's closing cell states in bold with the value it computes.

| Notebook | What it shows | Needs |
| --- | --- | --- |
| `rankine-cycle.ipynb` | A Rankine cycle on IAPWS-95 water; reading the state and the certificate | — |
| `refrigeration-cycle.ipynb` | An R134a vapour-compression cycle on CoolProp | the `coolprop` extra (a stated skip without it) |
| `methanol-water-column.ipynb` | A 20-stage methanol–water column on the Wilson γ–φ basis | a source checkout (the Wilson records) |
| `what-if-and-refusals.ipynb` | A sweep by edits; a state outside the domain; a unit on the wrong basis | — |
| `rankine-cost-and-gwp.ipynb` | Capital and operating cost and climate impact of the Rankine cycle (E01 assessment, synthetic LCA background) | a source checkout (the Rankine change set) |

An example is a demonstration, never gate evidence by itself: release claims come from the
registered benchmark cases and the evidence manifests (plan §5.1, §6).

**The reference journey (M07).** `scripts/m07_journey.py run` writes the journey's record and
`render` its report, `journey.md` (M07 spec §6.2, ADR 0041): one decision taken through four
rungs of fidelity, with its limits stated. The report is a demonstration of a workflow on a
registered test configuration, never gate evidence by itself; nothing in it is validated against
plant data.
