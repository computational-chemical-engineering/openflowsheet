# Installation

OpenFlowsheet needs **Python 3.13 or newer** and runs on Linux (x86-64 and aarch64 are the tested
platforms).

```bash
python -m pip install openflowsheet
```

This installs the simulator, the command line `openflowsheet` and the base dependencies: NumPy,
SciPy, PyYAML, jsonschema and [CasADi](https://web.casadi.org/), all pinned to exact versions.

!!! note "CasADi's licence"
    CasADi is licensed under the LGPL-3.0-or-later. It is a separate package that pip obtains from
    PyPI; OpenFlowsheet uses it through its Python API only and distributes none of its bytes.
    See [Licence and attributions](../licence.md).

## Optional extras

| Extra | Install | What it enables | Licences of what it adds |
| --- | --- | --- | --- |
| `coolprop` | `pip install "openflowsheet[coolprop]"` | The CoolProp pure-fluid basis (`coolprop-heos-v1`): one of 123 fluids per flowsheet, for the `thermal.*` units | CoolProp (MIT), inventoried in `docs/s07-coolprop-licences.json` |
| `server` | `pip install "openflowsheet[server]"` | The HTTP server (`openflowsheet serve-http`, with the optional web shell) and the MCP server (`openflowsheet serve-mcp`) | mcp (MIT), Starlette and Uvicorn (BSD-3-Clause) and their dependencies, all permissive; the closure is inventoried in the repository (`docs/t07-server-licences.json`) |
| `nlp` | see below | The general NLP bridge of the studies layer (Pyomo and Ipopt through cyipopt) | Pyomo (BSD-3-Clause), cyipopt and Ipopt (EPL-2.0); the audited environment's binaries are inventoried in `docs/m03-ipopt-audit.md` |
| `lca` | `pip install "openflowsheet[lca]"` | The offline Brightway adapter that builds unit-score tables for the LCA from a database you have prepared (see [Cost estimation and LCA](../guide/assessment.md#building-a-table-the-lca-extra)); assessments evaluate without it | Brightway's `bw2data` and `bw2calc` (BSD-3-Clause) and their dependencies, inventoried in `docs/e01-lca-licences.json` |
| `dev` | `pip install -e ".[dev]"` | The test and lint tools, for working on OpenFlowsheet itself | — |

The `nlp` extra cannot be installed from PyPI alone: PyPI has no cyipopt wheel for CPython 3.13. It
installs into a conda-forge environment that provides cyipopt and the Ipopt libraries; the
repository's `scripts/build-m03-ipopt-env.sh` builds exactly the audited one.

## From source

```bash
git clone https://github.com/computational-chemical-engineering/openflowsheet.git
cd openflowsheet
make venv        # .venv with the project and its dev extra, from the pinned lock
make check       # ruff, mypy --strict and the test suite
```

A source checkout also carries the registered benchmark cases and the Wilson model's records
(see [Property bases](../guide/property-bases.md#wilson-activity-model-wilson-ig-v2)).

## Verify the installation

```bash
python -c "import openflowsheet; print(openflowsheet.__version__)"
openflowsheet --help
```

Then solve the quickstart's flowsheet: [Quickstart](quickstart.md). With the `coolprop` extra,
`python -c "import CoolProp"` should succeed as well.
