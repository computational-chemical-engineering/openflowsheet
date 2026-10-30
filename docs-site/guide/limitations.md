# Limitations and support

**Unlisted is unsupported.** The authoritative envelope is the repository's
[support matrix](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/support-matrix.md), generated from the registered envelope with the
evidence for every row (a test, a manifest check or a document). This page states its substance in
plain words.

## Supported

- **Property bases:** the five of [Property bases](property-bases.md), each within its domain.
- **Units:** the models of the [unit catalogue](units.md), each on the bases listed there.
- **Topologies:** acyclic flowsheets; recycles (single, nested, high-gain) by tearing with
  safeguarded Anderson acceleration and restart, or merged into one equation-oriented region;
  cross-unit specifications; exact zero flows. More than one loop or region per plan is not
  exercised by a registered case.
- **Solve policies:** `T06-revision-v2` (the default for revision solves), `T04-W12`, and by
  explicit id `T08-warm-v1` and the experimental `T08-ptc-v1`.
- **Interfaces:** Python, CLI, HTTP and MCP, as in [Interfaces](interfaces.md).
- **Platforms:** Linux x86-64 and aarch64, Python 3.13, with the pinned dependency set.

## Not supported, and how each is refused

| Request | What happens |
| --- | --- |
| A property method other than the selectable bases | not representable: a revision has no property-method member; another provider's components are `components_unsupported` |
| A model not in the registry, or on a basis it does not bind on | `model_unsupported(<id>)` at binding, with the bases it does support |
| A state outside a basis's domain | `INITIALIZATION_FAILED`, or `invalid_trial_state` inside a solve; never extrapolated |
| Validation for optimisation through the application | `unsupported` (`task_unsupported(optimization)`) |
| Dynamics or time-varying specifications | not representable; a time member is a schema refusal |
| Gauge pressure, unregistered unit spellings | refused at validation |
| Second derivatives through the property callback | reported absent; never zeros |
| A specification pairing other than one freed column per promoted target | `UNSUPPORTED_RANK_STRUCTURE` at plan construction |
| Container or installer artifacts, container replay | not provided |

## Known limitations worth knowing first

- A `VERIFIED` certificate certifies residuals at registered tolerances; the solution-error bound
  is recorded, not promised. Energy checks share the property provider with the solver.
- Bitwise reproduction is reported, never promised across platforms.
- Pseudo-transient continuation (`T08-ptc-v1`) is experimental.
- Pure-fluid stream regimes are declared; there is no regime discovery, and a closure in another
  regime is refused `phase_regime_mismatch`. A dormant single-phase thermal outlet certifies
  `UNVERIFIED` (rank-deficient).
- The column: see [Distillation column](column.md#what-the-column-does-not-do).
- Cancellation is not cooperative inside the verifier.
- Agent evidence: one pinned model and configuration, over MCP only, not out of sample.

## Verification, validation, optimality

| | Status |
| --- | --- |
| Numerical verification | established against independent references (for example the SYN-001 oracle against 20-digit reference values) and by blind comparison with IDAES, DWSIM and BioSTEAM on shared cases — which share the equations, so this is verification |
| Empirical validation | the Wilson basis against measured vapour–liquid equilibrium (within its bands; methanol's liquid enthalpy and heat capacity not within band); IAPWS-95 and CoolProp carry their own published validation; the ammonia loop, its reactor and every SYN-001 result are **not** empirically validated |
| Optimality | **not** established |
| Human review | numerical and process-modelling review by a person is pending in every evidence manifest |

What each work package has and has not shown is recorded in its evidence manifest
([`evidence/`](https://github.com/computational-chemical-engineering/openflowsheet/tree/main/evidence)).
