# User feedback intake

This file logs feedback from people who use OpenFlowsheet from the outside. Each item has a triage line: its lane, the
register entry it touches and a default placement. Placement is Frank's call. Nothing here starts work. Full reports and
repros stay with the sender. The source for now is the `OpenFlowsheet_tutorial` session (SMM-TRS2,
`/home/frankp/Codes/OpenFlowsheet_tutorial/FEEDBACK.md`). It teaches process control against the PyPI release.

Status values: `logged`, then `placed` (in a package), then `done` (with commit) or `declined` (with reason).

## Batch 1 — 2026-11-01, against 0.3.0.post1

| Id | Item | Lane / touches | Default placement | Status |
| --- | --- | --- | --- | --- |
| FB-01 | Re-running the quickstart: `LocalApplication.create("plant")` on an existing project raises `StoreError: plant is not empty; a project is created in a new directory`. Users read the clause as a report of an action. Frank chose to keep the refusal, name `LocalApplication.open()` in the message, add `create(..., exist_ok=True)` (opens an existing project, refuses a non-empty directory that is not a project) and make the quickstart use it. Keep the word "directory". | Build lane; application API, README quickstart (`tests/test_readme_current.py`) | 0.4, with FB-05 | logged |
| FB-02 | The solution state has no vapour fraction or quality (stream S4 shows only `P`, `T`, `n.H2O`, `sat.L`, `sat.V`). Observation: check how a user finds the steam quality. | Build lane; result views, docs | 0.4 docs, or a derived output with FB-05 | logged |
| FB-03 | A failed solve surfaces later as `not_found: no such artifact` when reading `solution-state.json`. `RunResult.error` is `None` on a failed run. The cause (`initializer_failed(T): phase_regime_mismatch(S4)`) sits only in `failure-bundle.json`. Asks: put the failure on `RunResult`; have `not_found` name the member, the outcome and the bundle's members; add an outcome check to the quickstart. | Build lane; `application/types.py` `RunResult`, bundle reads | 0.4, with FB-05 | logged |
| FB-04 | Rankine at 30 → 0.1 bar, η 0.85, boiler ≥ 650 °C: the actual exhaust is superheated but the isentropic state is wet. Declared `vapor_liquid`, it fails `phase_regime_mismatch(S4)`. Declared `vapor`, it fails `isentropic_state_two_phase(T)`. This is the textbook isentropic-efficiency case. Asks: (1) allow a two-phase isentropic reference for a vapour outlet; (2) regime discovery later; (3) meanwhile the docs say the outlet phase must be re-declared. | Design lane (phase logic); lifts part of L-TH-4 (`docs/support-matrix.md`, R-839, S11 OQ-1 "follow-up later"); regime discovery is L-TH-1/L-TH-6. A lift candidate under R-924 | (1) 0.4, specifier pass first; (2) 0.6, with X08's stability-based phase split; (3) with FB-05 | logged |
| FB-05 | Frank's general request, which he cares about: messages a student understands. Each says what, where (user names), why and what to do, and which kind of failure: input error, not supported in this version (limitation id), numerical, or internal bug. Layered: a human first line, then the stable typed code, then details. Raised where the failure happens. Shows the triggering numbers in the user's units. Has a docs page and an `openflowsheet explain <code>` per code. Warnings and certificate statuses get the same treatment. Tested against a corpus of beginner mistakes in CI. Worked examples are in the sender's FEEDBACK.md §FB-05. | Architect pass (error model across API/CLI/HTTP/MCP; typed codes stay stable), then build lane | 0.4, as a package of its own ahead of X04; FB-01 and FB-03 fold into it | logged |

Related: transient simulation for process control is TX in ADR 0056 (0.7+). The tutorial session is collecting control
use cases as design input.
