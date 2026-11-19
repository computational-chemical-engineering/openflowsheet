# Installation

OpenFlowsheet needs **Python 3.13 or newer** and runs on Linux (x86-64 and aarch64 are the tested
platforms). Windows (x86-64) and macOS (arm64) are tested in CI since 0.5; see [Windows](#windows)
and [macOS](#macos) for what differs there.

```bash
python -m pip install openflowsheet
```

This installs the simulator, the command line `openflowsheet` and the base dependencies: NumPy,
SciPy, PyYAML, jsonschema and [CasADi](https://web.casadi.org/), all pinned to exact versions.

!!! note "Installing for exact replay"
    A run bundle records the hash of the package's dependency lock only when the installed runtime
    dependencies are exactly at the lock, including jsonschema's own dependencies (`attrs`,
    `jsonschema-specifications`, `referencing`, `rpds-py`), which a plain install leaves free to
    upgrade. To install at the lock, constrain the install by the release's `requirements.lock`
    (in the repository at the release's tag, and in the source distribution):

    ```bash
    python -m pip install -c requirements.lock openflowsheet
    ```

    Without it, a bundle written where one of those four differs records no lock, and replay names
    the distributions that differ.

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

A source checkout also carries the registered benchmark cases.

## Windows

Windows x86-64 is a CI platform since 0.5 (`windows-latest`, the same checks as Linux). Install
Python 3.13 from python.org or the Microsoft Store, then in a terminal:

```powershell
py -3.13 -m pip install openflowsheet
```

What differs from Linux:

- **External models** (isolation profile `external-subprocess-v1`) are refused before any process
  starts, `environment_unavailable` with `external_execution_unsupported_platform` (ADR 0033 D2);
  the `nlp` and reactor environments are not built or tested there. Both are planned for a later
  release.
- **Jobs** run in worker processes as on Linux. A worker puts itself in a Windows Job Object, so
  that a forced kill also ends every process it started.
- **Project directories** should be on a local NTFS drive. A path longer than 260 characters needs
  Windows long paths enabled (`LongPathsEnabled`).
- **From source**, use Git for Windows and run `make` and `scripts/check.sh` in Git Bash. Clone with
  `git config --global core.autocrlf false` set first, so that the checkout has the repository's
  line endings: identity hashes are computed over file bytes.
- The `coolprop` extra installs from PyPI's Windows wheel, but its wheel audit and its tests cover
  Linux only.

## macOS

macOS on Apple silicon (arm64) is a CI platform since 0.5 (`macos-latest`, the same checks as
Linux). Install Python 3.13 (python.org, Homebrew `python@3.13` or `uv python install 3.13`), then:

```bash
python3.13 -m pip install openflowsheet
```

What differs from Linux:

- **External models** run with the same process-group kill chain as on Linux but are best effort
  (ADR 0033 D2: Linux is the registered platform); the `nlp` and reactor environments are not
  built or tested on macOS yet.
- Floating-point results can differ from the Linux reference in their last bits; a bundle written
  on Linux and replayed on macOS is replayed on a different machine class.
- The `coolprop` extra installs from PyPI's macOS wheel, but its wheel audit and its tests cover
  Linux only.
- Intel Macs are not tested.

## Verify the installation

```bash
python -c "import openflowsheet; print(openflowsheet.__version__)"
openflowsheet --help
```

Then solve the quickstart's flowsheet: [Quickstart](quickstart.md). With the `coolprop` extra,
`python -c "import CoolProp"` should succeed as well.
