# Studies and optimisation

The studies layer (`openflowsheet.studies`) works on a compiled problem's pinned inputs. It is a
library layer: apart from the surrogate study, which runs as a job (`submit_job` with the
`surrogate_study` operation), it is not an operation of the application contract, and its scope
is the registered flowsheets it was built and tested on — the SYN-001 flowsheets and the
ammonia-synthesis (C1) loop.

| Capability | What it gives | Scope |
| --- | --- | --- |
| Parametric sensitivities | exact first-order sensitivities of outputs to pinned inputs, from the parametric twin of the compiled problem and one factorisation, issued only at a certified regular root | registered SYN-001 flowsheets |
| Sweeps | a parameter varied over values, each point solved and certified, with its sensitivity | as above |
| Parameter estimation | least-squares estimates of pinned inputs, using the exact sensitivities | as above |
| NLP bridge | the flowsheet as a grey box inside Pyomo, solved by Ipopt | needs the `nlp` extra in its audited environment |
| Surrogates | surrogate models of an expensive unit with their evidence (`SurrogateManifest`) | the C1 reactor |
| Trust-region study | a trust-region refinement of the C1 loop with surrogate and full-fidelity reactor | the C1 loop |

A sensitivity is never computed by finite differences: differencing is a test oracle only.
Studies emit `Study` and `OptimizationReport` documents with their schemas.

!!! warning "No optimality claim"
    Optimality evidence is **not** established for any study. An optimisation result reports what
    the solver returned and how it was checked; it does not claim a global or even a certified
    local optimum.

## The `nlp` extra

The NLP bridge needs Pyomo, cyipopt and Ipopt with `libpynumero_ASL`. PyPI has no cyipopt wheel for
CPython 3.13, so the extra installs only into a conda-forge environment; the repository's
`scripts/build-m03-ipopt-env.sh` builds the audited one, whose binaries and licences are
inventoried in [`docs/m03-ipopt-audit.md`](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/m03-ipopt-audit.md). Tests that need it are
marked `nlp` and deselected by default.

## A what-if loop through the application

For flowsheets outside the studies layer's scope, a sweep is a loop of ordinary solves: edit one
specification with `commit_change`, solve, read the state. Every point is a revision in the
project's history with its own certificate. The
[what-if example](../examples/what-if-and-refusals.ipynb) does this for a Rankine cycle.

The normative texts are ADR 0031 (sensitivities and studies) and ADR 0032 (the NLP adapter), linked
from [Design](../design.md).
