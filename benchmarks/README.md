# `benchmarks/`

The benchmark registry and its cases: equations, physical data and provenance, tolerances,
compute budgets, expected failure classes, reference versions and independence assessment, and
the executable ensemble generators with their distributions, domain handling, and saved initial
states (blueprint §16 item 6, §13; amendment **[A04]**).

Present now (introduced by **P01**):

| Path | Contents |
| --- | --- |
| `registry.yaml` | The SYN-001 family and its eight registered cases: fresh feed, temperatures, pressure, r, tolerances, scales, initializers, budgets, oracle callable, reference path, independence statement and expected outcome class |
| `syn001/oracle.py` | The independent scalar oracle (implementation plan §3.2). Pure Python plus `math`; it imports nothing from `openflowsheet` and is never called from a production code path |
| `syn001/reference_values.yaml` | Fable's 20-digit reference values, generated from the plan §3.1 definitions with mpmath at 40 digits. Independent of the oracle and never regenerated from it |
| `syn001/components.yaml` | The three synthetic ComponentRecords, `elemental_verification: NOT_APPLICABLE` |
| `syn001/cases/*.yaml` | One ProcessRevision document per registered flowsheet case |

Two of the eight cases have an expected *outcome type* rather than expected values and sit
outside the success denominator: `SYN-001-conflicting-heater-spec` must be rejected at
validation, and `SYN-001-capped-budget` must terminate with a typed budget-exhausted failure and
no certificate. `SYN-001-capped-budget` reuses the nominal revision byte for byte and differs
only in a solve-policy override, because a budget is a solver choice and must not change the
process being solved.

Later contributions: the v0.0 flash-recycle case and its deliberately failing companion
(K02–K06); the 30+ distinct cases, robustness generators, registered 20x20 ensemble, and eight
reference comparisons of **T06**; the real-chemistry dossier of **T08**; reactor and surrogate
cases (M01–M04); column cases (S02–S03) and the v1 corpus (R01).

Registration and reference-comparison verdicts are design-lane work (`specifier`, `verdict`; implementation plan §1.3). A case
that cannot be obtained or reproduced is documented as unavailable; counts are never silently
reduced (plan §5.1).
