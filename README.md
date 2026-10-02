# OpenFlowsheet

An agent-native open process-engineering runtime, in which models, equations, numerical strategies,
validity limits and evidence are explicit objects. Humans and coding agents work against the same
scientific contracts. The project owns solver orchestration and process-specific numerical methods,
and reuses established differentiation, linear-algebra and optimization infrastructure.

## Status

**Pre-release. Phase 0 is complete; no capability is released, and nothing here is validated against
experiment or an independent process simulator.**

| | |
| --- | --- |
| Complete | P00 repository and gate, P01 state semantics and the SYN-001 oracle, P02 matched backend spikes, P03 backend and distribution verdicts |
| In progress | K01 — the production `CompiledProblem` compiler on the selected backend |
| Established | Numerical verification against independent references: the P01 oracle agrees with 20-digit reference values to 7.1e-15 worst relative deviation, and P02's two backend routes agree with each other and with that reference inside every registered tolerance |
| **Not** established | Empirical validation against experiment or another simulator; optimality evidence; human numerical or process-modeling review — `review.numerical` and `review.process_model` are `pending` in every evidence manifest and no agent may set them |

What the project has and has not shown is recorded per package in `evidence/<ID>/<commit>/manifest.json`,
and the current position is `docs/progress.md`.

## Authorities

Read these before changing anything they cover.

| Document | Role |
| --- | --- |
| `docs/blueprint-v3.1.md` | Architectural authority. Its SHA-256 is recorded in the implementation plan's header and checked by the test suite |
| `docs/implementation-plan.md` | Execution authority: work packages, order, acceptance evidence, gates |
| `docs/adr/` | Normative decisions. ADR 0001 state/units/zero-flow, 0003 backend, 0006 distribution, 0008 transient-extension readiness |
| `docs/decision-register.md` | What was chosen, what was rejected, and why — the index that makes the ADRs findable by the question they answer |
| `CLAUDE.md` | Working rules for the two coding agents that share this repository |

## Development

Requires Python 3.13.

```bash
make venv                                  # create .venv and install with dev extras
make check                                 # ruff, ruff format, mypy --strict, pytest
make lock                                  # regenerate requirements.lock from the environment
```

`make check` is the gate. It must be green before any merge, and a failed gate stays failed — it is
never relaxed, narrowed or worked around to let a change through.

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
**`docs/p03-binary-audit.md`**, with the machine-readable record in `spikes/p03/results/`. The terms
on which this project may and may not redistribute any of it are **`docs/adr/0006-distribution-data-rights.md`**.
Changing the CasADi pin re-runs that audit before the change merges.

Further attributions are in `NOTICE`.

## Licence

The core licence is **Apache-2.0**, declared in `pyproject.toml` and stated in `LICENSE` and
`NOTICE`. The maintainer confirmed the project's rights to distribute its contributions under it on
2026-09-23 (`120acb4`). Why Apache-2.0 rather than MIT is recorded in `docs/decision-register.md`
R-005.
