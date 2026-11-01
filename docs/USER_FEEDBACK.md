# User feedback intake

This file logs feedback from people who use OpenFlowsheet from the outside. Each item has a triage line: its lane, the
register entry it touches and a default placement. Placement is Frank's call. Nothing here starts work. Full reports and
repros stay with the sender. The source for now is the `OpenFlowsheet_tutorial` session (SMM-TRS2,
`/home/frankp/Codes/OpenFlowsheet_tutorial/FEEDBACK.md`). It teaches process control against the PyPI release.

Status values: `logged`, then `placed` (in a package), then `done` (with commit) or `declined` (with reason).

## Batch 1 — 2026-11-01, against 0.3.0.post1

| Id | Item | Lane / touches | Default placement | Status |
| --- | --- | --- | --- | --- |
| FB-01 | Re-running the quickstart: `LocalApplication.create("plant")` on an existing project raises `StoreError: plant is not empty; a project is created in a new directory`. Users read the clause as a report of an action. Frank chose to keep the refusal, name `LocalApplication.open()` in the message, add `create(..., exist_ok=True)` (opens an existing project, refuses a non-empty directory that is not a project) and make the quickstart use it. Keep the word "directory". | Build lane; application API, README quickstart (`tests/test_readme_current.py`) | 0.4, with FB-05 | placed |
| FB-02 | The solution state has no vapour fraction or quality (stream S4 shows only `P`, `T`, `n.H2O`, `sat.L`, `sat.V`). Observation: check how a user finds the steam quality. | Build lane; result views, docs | 0.4, folded into ST (FB-06) | placed |
| FB-03 | A failed solve surfaces later as `not_found: no such artifact` when reading `solution-state.json`. `RunResult.error` is `None` on a failed run. The cause (`initializer_failed(T): phase_regime_mismatch(S4)`) sits only in `failure-bundle.json`. Asks: put the failure on `RunResult`; have `not_found` name the member, the outcome and the bundle's members; add an outcome check to the quickstart. | Build lane; `application/types.py` `RunResult`, bundle reads | 0.4, with FB-05 | placed |
| FB-04 | Rankine at 30 → 0.1 bar, η 0.85, boiler ≥ 650 °C: the actual exhaust is superheated but the isentropic state is wet. Declared `vapor_liquid`, it fails `phase_regime_mismatch(S4)`. Declared `vapor`, it fails `isentropic_state_two_phase(T)`. This is the textbook isentropic-efficiency case. Asks: (1) allow a two-phase isentropic reference for a vapour outlet; (2) regime discovery later; (3) meanwhile the docs say the outlet phase must be re-declared. | Design lane (phase logic); lifts part of L-TH-4 (`docs/support-matrix.md`, R-839, S11 OQ-1 "follow-up later"); regime discovery is L-TH-1/L-TH-6. A lift candidate under R-924 | (1) 0.4, specifier pass first; (2) 0.6, with X08's stability-based phase split; (3) with FB-05 | logged |
| FB-05 | Frank's general request, which he cares about: messages a student understands. Each says what, where (user names), why and what to do, and which kind of failure: input error, not supported in this version (limitation id), numerical, or internal bug. Layered: a human first line, then the stable typed code, then details. Raised where the failure happens. Shows the triggering numbers in the user's units. Has a docs page and an `openflowsheet explain <code>` per code. Warnings and certificate statuses get the same treatment. Tested against a corpus of beginner mistakes in CI. Worked examples are in the sender's FEEDBACK.md §FB-05. | Architect pass (error model across API/CLI/HTTP/MCP; typed codes stay stable), then build lane | 0.4, as a package of its own (MSG) ahead of X04; FB-01 and FB-03 fold into it | placed |

Placement of MSG (FB-05, with FB-01 and FB-03) in 0.4 ahead of X04: Frank agreed on 2026-11-01 in the tutorial
session, which relayed it. FB-02 and FB-04 placements are still defaults.

## Batch 2 — 2026-11-01, against 0.3.0.post1

| Id | Item | Lane / touches | Default placement | Status |
| --- | --- | --- | --- | --- |
| FB-06 | No stream table. Checking H(S5) − H(S1) for a Rankine energy balance took about 25 lines of internal API (`Iapws95Provider`, `EvaluationContext`, `PropertyRequest`, phase chosen by hand). Asks: a post-solve stream table (T, P, molar and mass flow, composition, vapour fraction, h, s, density) and an overall energy-balance summary, via API, artifact and CLI. Subsumes FB-02. | Build lane; result views over existing providers | 0.4, package ST (ADR 0056 Am. 1) | placed |
| FB-07 | Seider's vinyl chloride process (C2H4, Cl2, HCl, EDC, VCM, O2, H2O) can't be modelled. Blockers: component records; liquid-phase VLE with k_ij; a basis-independent conversion reactor; column and HX coverage. It carries Frank's direction (R-926): a real simulator, open and agent-enabled, with infrastructure to get and use component data (identity, record schema, adapters including NIST WebBook fetchers and user-licensed databanks, regression, consistency evidence, hash pinning, agent operations). | Architect and specifier; new package X11; touches R-706 (rights of shipped data), X01, X09, X10 | X11 in 0.5 beside X01; VCM acceptance at the end of 0.6 | placed (default) |

## Batch 3 — 2026-11-01

**FB-08: gap analysis against commercial simulators.** Full table at
`/home/frankp/Codes/OpenFlowsheet_tutorial/notes/real_simulator_gaps.md`. Frank asked for it and will discuss it
directly. Status: `placed`. Frank accepted it on 2026-11-01 and extended it to the blueprint's deferred list (R-927,
ADR 0056 Am. 2). Release lines wait for the roadmap.

Not in any plan today; spot-checked against the repo and accurate:
- heat integration and pinch;
- sizing and costing of every unit, with profitability (NPV, IRR, cash flow). E01/S12 has cost and LCA functionals only;
- a Gibbs equilibrium reactor, and kinetic CSTR/PFR with user rate laws on any basis. Blueprint §579: "deferred unless
  already needed by a case"; the VCM case is now such a case;
- CAPE-OPEN. Blueprint D18 and §496, and plan §288, say demand-driven and need a use case and an ADR. R-926 supplies
  the use case;
- a rigorous two-stream exchanger with design and rating on every basis;
- transport properties;
- a PFD editor and reports;
- batch processes;
- relief and safety.

One correction: activity models are already named, since X01 is piloted by NRTL, UNIQUAC and original UNIFAC
(`docs/V02_STATE.md`, queue 2c).

Proposed grouping, all defaults for Frank:

| Package | Contents | Line |
| --- | --- | --- |
| X12 economics | Sizing and costing for every unit, costed utilities, profitability; extends E01/S12 | 0.6, needed for the VCM route comparison |
| X13 reactors | Gibbs reactor; kinetic CSTR/PFR with user rate laws on any basis | 0.6 |
| X14 heat exchange | Rigorous HeatX design and rating on every basis; pinch targets and HEN | 0.6 |
| X15 CAPE-OPEN | Thermo and unit interop, after X07 and X01 | 0.7 |
| X16 PFD and reports | Graphical editor in the web shell; stream and equipment reports | 0.7+ |
| X17 transport properties | Viscosity, conductivity, diffusivity through X01 and X11 | 0.6, with X12 |
| after TX | Batch processes; relief and safety | 0.8+ |

Open question for Frank: does R-924 also lift the blueprint's deferred list (electrolytes, solids, polymers, assays,
rate-based columns, P&ID, MINLP synthesis) as planned packages?

Related: transient simulation for process control is TX in ADR 0056 (0.7+). The tutorial session is collecting control
use cases as design input.
