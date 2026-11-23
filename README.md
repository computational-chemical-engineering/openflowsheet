# OpenFlowsheet

An agent-native open process-engineering runtime, in which models, equations, numerical strategies,
validity limits and evidence are explicit objects. Humans and coding agents work against the same
scientific contracts. The project owns solver orchestration and process-specific numerical methods,
and reuses established differentiation, linear-algebra and optimization infrastructure.

A flowsheet is a validated document, a solve is a job with a typed result, and every converged run
comes with a certificate from an independent verifier that says what it checked and what it does
not claim. Python, the `openflowsheet` command line, HTTP and MCP run the same operations with the
same results.

**Documentation:** <https://computational-chemical-engineering.github.io/openflowsheet/>

## Status

**Early development. Version 0.5.0 is released** (23 November 2026). Version 0.4.0 was released on 11 November
2026 and version 0.3.0 on 31 October 2026 (`0.3.0.post1` is the same release with a new description and the
project links; it changes no code).

| | |
| --- | --- |
| Released in 0.5.0 | The application contract (Python, the command line, HTTP and MCP), the unit-model library, the planner, the verifier with its certificate or typed failure, and the replay bundle; the Peng–Robinson route of the ammonia-synthesis loop with the pinned PyMRM reactor as a unit model; sensitivities, studies, the NLP bridge, surrogate evidence, the trust-region study and the diagnostic web shell; countercurrent equilibrium-stage columns (MESH) with blind comparisons against an independent implementation, IDAES, DWSIM and BioSTEAM; IAPWS-95 water, CoolProp's Helmholtz equations of state for 123 pure fluids as an optional extra, and the Wilson liquid-mixture method for methanol–ethanol–water; cost estimation and LCA as post-solve functionals of a verified state. New in 0.4.0: optimisation of revision flowsheets (`optimize`), declared warm starts, revision-region continuation, the stream table, display units at the boundary, replay from the installed wheel and the message-code catalogue. New in 0.5.0: Windows and macOS in CI (the release is still judged on Linux), the extension registry (`list_capabilities`, `check_admission`), the component record store (`search_records` and four more `Records` operations; no solve reads it yet) and the plugin guide. The supported envelope is the [support matrix](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/support-matrix.md): unlisted is unsupported |
| Established | Numerical verification against independent references, for example the P01 oracle against 20-digit reference values (7.1e-15 worst relative deviation); agreement with IDAES, DWSIM and BioSTEAM on shared column cases, which share the equations and are therefore not validation |
| Validation against data | The Wilson method is within its pre-registered bands against measured vapour–liquid equilibrium of methanol–ethanol–water (ternary at 101.3 kPa; binaries with water at 323–333 K); methanol's liquid enthalpy and heat capacity are not within band against CoolProp. The C1 loop and its reactor results are not empirically validated |
| **Not** established | Optimality evidence; human numerical or process-modeling review — `review.numerical` and `review.process_model` are `pending` in every evidence manifest and no agent may set them |

What 0.5.0 claims, and what it is not (judged on Linux only, no global optimality, no liquid–liquid split, no
rate-based columns, no solve that reads the component record store, a plugin that adds no unit model a solve uses,
among others), is in the
[changelog](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/CHANGELOG.md).

## Install

OpenFlowsheet needs Python 3.13 or newer and runs on Linux (x86-64 and aarch64 are tested).
Windows (x86-64) and macOS (arm64) are tested in CI since 0.5, with the limits the
[installation guide](https://computational-chemical-engineering.github.io/openflowsheet/getting-started/install/) lists.

```bash
python -m pip install openflowsheet
```

| Extra | Install | Adds |
| --- | --- | --- |
| `coolprop` | `pip install "openflowsheet[coolprop]"` | The CoolProp pure-fluid basis `coolprop-heos-v1` |
| `server` | `pip install "openflowsheet[server]"` | The HTTP server with the optional web shell, and the MCP server |
| `lca` | `pip install "openflowsheet[lca]"` | The offline Brightway adapter that builds LCA unit-score tables |
| `nlp` | see the [installation guide](https://computational-chemical-engineering.github.io/openflowsheet/getting-started/install/) | The general NLP bridge (Pyomo and Ipopt); needs a conda-forge environment |

## Quickstart

Solve a once-through Rankine cycle on IAPWS-95 water from a ready-made change set:

```bash
curl -sLO https://raw.githubusercontent.com/computational-chemical-engineering/openflowsheet/v0.5.0/examples/rankine-cycle.changeset.json
```

```python
import json
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.transaction_types import Change

with open("rankine-cycle.changeset.json") as handle:
    change_set = json.load(handle)
change, expected_revision, key = Change.from_change_set(change_set)

with LocalApplication.create("plant", exist_ok=True) as app:  # created, or opened on a re-run
    committed = app.commit_change(change, expected_revision, key)
    report = app.validate(committed.revision_id, "simulation")
    print(report.status)                               # READY_FOR_SIMULATION

    run = app.solve(committed.revision_id, "default")
    print(run.outcome, run.verification_status)        # CONVERGED VERIFIED
    run.raise_for_outcome()                            # says why, if the solve failed

    bundle = next(o.artifact_id for o in run.outputs if o.kind == "replay_bundle")
    state = json.loads(app.artifact_bytes(f"{bundle}/solution-state.json"))["variables"]
    print(state["T.W"], state["B.Q"])                  # turbine work, boiler duty (W)
```

The same steps from the command line:

```bash
openflowsheet project init plant
openflowsheet api --project plant commit_change --json-file rankine-cycle.changeset.json
openflowsheet api --project plant solve --json '{"revision_id": "rev-000001", "policy_id": "default"}'
```

The [quickstart](https://computational-chemical-engineering.github.io/openflowsheet/getting-started/quickstart/)
reads the certificate, and the
[tutorials](https://computational-chemical-engineering.github.io/openflowsheet/tutorials/first-flowsheet/)
build a flowsheet step by step.

## Links

- Documentation: <https://computational-chemical-engineering.github.io/openflowsheet/>
- Repository: <https://github.com/computational-chemical-engineering/openflowsheet>
- Changelog: <https://github.com/computational-chemical-engineering/openflowsheet/blob/main/CHANGELOG.md>
- Releases: <https://github.com/computational-chemical-engineering/openflowsheet/releases>
- Issues: <https://github.com/computational-chemical-engineering/openflowsheet/issues>
- Support matrix: <https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/support-matrix.md>
- Limitations: <https://computational-chemical-engineering.github.io/openflowsheet/guide/limitations/>

## Third-party notices

This software uses **CasADi 3.8.0**, which is licensed under the **GNU Lesser General Public License,
version 3 or later (LGPL-3.0-or-later)**. CasADi is a separate work, obtained by the installer from
PyPI as a pinned dependency; this project distributes none of its bytes. It is used through its
Python API only — the interpreter loads the library at run time, nothing is compiled against its
headers or linked against it at build time, and a user may substitute their own build of CasADi
3.8.0 by replacing the installed package.

The full licence text ships inside the CasADi distribution at `casadi/LICENSE/LICENSE.txt` in the
installed package, together with notices for its bundled components at `casadi/include/licenses/`.

An exact inventory of what that distribution contains — every binary with its SHA-256, the bundled
plugin inventory including the bytes that cannot run, and the notices — is
**[`docs/p03-binary-audit.md`](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/p03-binary-audit.md)**,
with the machine-readable record in `spikes/p03/results/`. The terms on which this project may and
may not redistribute any of it are
**[`docs/adr/0006-distribution-data-rights.md`](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/adr/0006-distribution-data-rights.md)**.
Changing the CasADi pin re-runs that audit before the change merges.

Further attributions are in
[`NOTICE`](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/NOTICE).

## Licence

The core licence is **Apache-2.0**, declared in `pyproject.toml` and stated in
[`LICENSE`](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/LICENSE) and
[`NOTICE`](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/NOTICE). The
maintainer confirmed the project's rights to distribute its contributions under it on 2026-09-23
(`120acb4`). Why Apache-2.0 rather than MIT is recorded in the
[decision register](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/decision-register.md)
R-005.

## Developing OpenFlowsheet

```bash
git clone https://github.com/computational-chemical-engineering/openflowsheet.git
cd openflowsheet
make venv        # .venv with the project and its dev extra, from the pinned lock
make check       # ruff, ruff format, mypy --strict, pytest — the gate; a failed gate stays failed
```

The architectural authority is the
[blueprint](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/blueprint-v3.1.md),
the execution authority the
[implementation plan](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/implementation-plan.md),
and the normative decisions are the
[ADRs](https://github.com/computational-chemical-engineering/openflowsheet/tree/main/docs/adr), indexed by the
[decision register](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/decision-register.md).
Coding agents follow
[`CLAUDE.md`](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/CLAUDE.md).
What each package has and has not shown is in `evidence/<ID>/<commit>/manifest.json`, the current
position in
[`docs/progress.md`](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/progress.md),
and how a release is made in
[`docs/RELEASING.md`](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/RELEASING.md).
The diagnostic web shell (`openflowsheet serve-http --ui`, with the `server` extra) is described in
[`docs/web-shell.md`](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/web-shell.md).
