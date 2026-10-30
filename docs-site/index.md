# OpenFlowsheet

[![PyPI](https://img.shields.io/pypi/v/openflowsheet.svg)](https://pypi.org/project/openflowsheet/)

OpenFlowsheet is an open, equation-oriented process simulator built for people **and** coding
agents. Models, equations, numerical strategies, validity limits and evidence are explicit
objects: a flowsheet is a validated document, a solve is a job with a typed result, and every
converged run comes with a certificate from an independent verifier that says what it checked —
and what it does not claim.

- **Equation-oriented, with process-specific numerics.** Damped Newton on the whole flowsheet,
  tearing and Anderson acceleration for recycles, homotopy and restart recovery; CasADi supplies
  the exact derivatives.
- **Evidence, not just numbers.** A run is `VERIFIED`, `RELAXED`, `UNVERIFIED` or `FAILED`, with
  every residual, balance and specification check listed. Numerical verification, empirical
  validation and optimality are kept apart, and only the first is claimed for a solve.
- **Refusals are results.** An unsupported model, a state outside a property model's domain or an
  incomplete specification ends in a typed refusal, never in a quietly extrapolated answer.
- **One contract, four doors.** Python (`LocalApplication`), the `openflowsheet` command line,
  HTTP and MCP all run the same operations with the same results.

## What it can model

| Area | What is available |
| --- | --- |
| Property bases | IAPWS-95 water; CoolProp Helmholtz equations of state for one pure fluid (optional extra); the Wilson activity model with an ideal-gas vapour for methanol–ethanol–water; Peng–Robinson for the ammonia-synthesis loop; the synthetic SYN-001 test system |
| Units | Pumps, compressors, turbines, valves, heaters and coolers, mixers, splitters, flashes, heat exchangers, reactors, and countercurrent equilibrium-stage distillation columns — see the [unit catalogue](guide/units.md) |
| Flowsheets | Acyclic and recycle flowsheets, solved equation-oriented or by tearing, with specifications on streams or units |
| Studies | Parametric sensitivities, sweeps and estimation on registered flowsheets; an optional NLP bridge (Pyomo/Ipopt) |
| Evidence | Solution certificates, replay bundles that reproduce a run, and the complete project history |

What is **not** supported is listed plainly in [Limitations and support](guide/limitations.md):
anything not listed there as supported is unsupported.

## Status

OpenFlowsheet is in early development. Released versions are on
[PyPI](https://pypi.org/project/openflowsheet/), and the [changelog](changelog.md) says what each
release contains and what it does not claim. Comparisons with IDAES, DWSIM and BioSTEAM on shared
cases agree to tight tolerances; because those tools share the equations, this is verification,
not validation. Human numerical and process-modelling review of the project is still pending.

## Where to go next

- [Install it](getting-started/install.md) and run the [quickstart](getting-started/quickstart.md).
- Build a flowsheet step by step in [Your first flowsheet](tutorials/first-flowsheet.md).
- Browse the [examples](examples/index.md): a Rankine cycle, a refrigeration loop, a distillation
  column, and what-if studies with refusals.
- Working with an AI assistant? Read [Coding Agents](agents.md).
