# ADR 0071 — OPT: optimisation of revision flowsheets through a separate optimisation request, a held-regime full-space gray box, a cold production re-solve as the truth, and a job operation `optimize`

**Status:** **Proposed, 2026-11-07.**
- Takes effect on `main` when OPT's evidence manifest is `tested` (gates G1–G21 of the design note) and the design-lane
  `reviewer` pass is done. Until then OPT is built on `wp/OPT`.
- Register entries are added on acceptance (drafts below, unnumbered).

**Author:** design lane (`architect`). **Brief:** `docs/briefs/OPT-architect.md`.
**Design note:** `docs/design/OPT-revision-optimisation.md` holds the normative detail; § numbers below refer to it.

**Amends:**
- **ADR 0019 D1, as Amendment 16** (§4.13): job operation `optimize` (enum value, `job_request` branch,
  `job_result.optimization`, six artifact kinds); `validate` input member `optimization`; new
  `schemas/optimization-request.schema.json`; additive optional members of `optimization-report.schema.json`. ADR 0020:
  the `optimize` body's stages, ends, cancellation and outputs (§4.10).
- **ADR 0032:** D1 — the gray box is over a host's *held-regime system* (§4.2.1), not only SYN-001's 47 variables; D3 —
  V1 is the host's production route, cold (§4.6); D4 — bounds for further variable kinds and phase-regime admissibility
  rows as true domain restrictions (§4.2.3, §4.7); D6 — `validate(task="optimization")` returns a `ValidationReport`
  when given a request and an audited solver (§4.11), lifting R-129/R-191's refusal; readiness has a static and a start
  phase, and on revision hosts one certified start suffices (§4.5).
- **ADR 0031 (Q4′, Q4):** a PH-type split given a margin is judged as a TP split; Q4 gains a *held* mode used only by
  OPT's V5 (§4.2.4, §4.7). Callers that pass neither are unchanged.
- **ADR 0052 D10 / R-860:** the revision-flowsheet NLP host and the optimisation bindings are lifted; the other cuts stay
  (§3 D10).
- **Asks ADR 0066 (F7, Proposed)** to admit `job_operation: "optimize"` in D10 under E-F7-8's byte-identity rule
  (§4.15); until it does, F7 open item 4's default holds.

No `Protocol`, `CompiledProblem` method, quantity kind, check category, tolerance or `ProcessRevision` v1 member
changes. No registered result moves.

**Affected requirements:** blueprint §4.1 (Study object), §4.3 (`READY_FOR_OPTIMIZATION`), §10 (true domain
restrictions; local stationarity is not global optimality), [A06] (the bridge); D04/A10 (audited binary, platform);
D14 (evidence classes); D16 (the optimisation closure).
**Affected packages:** OPT (builds it); M03 (refactored behind a host, bit-identical); E01 (consumed); F7, F8, X24
(absorb it, §4.15); MSG, X02, ST (merge-order rule for the schema, catalogue and surface link, §4.13).

## Context

M03 built the NLP bridge as a library over the fixed SYN-001 flowsheet; E01 built cost and LCA as differentiable
post-solve functionals and left the revision-flowsheet NLP host and the bindings as typed refusals (R-860); R-129 keeps
`validate(task="optimization")` refused because a revision had no place for a formulation. The roadmap puts OPT in 0.4:
optimise the user's own revision flowsheets, with cost and LCA objectives, as a certified, recorded, replayable candidate
reachable from CLI, Python, HTTP and MCP.

## Decision

**D1. Routes.** `revision_eo` is admitted, surrogate-backed units included. `revision_coupled` is refused
`OPTIMIZATION_ROUTE_UNAVAILABLE(revision_coupled)`: an external unit has no exact derivative, so no KKT verification is
possible (R-924's exclusion case); M05's trust region is its route. `legacy_eo` is declared and refused
`OPTIMIZATION_ROUTE_UNAVAILABLE(legacy_eo)` in 0.4; the same host serves it later.

**D2. The formulation is a separate optimisation request** (blueprint §4.1 Study): decisions, objective (sense, scale),
inequality constraints, starts, an inline E01 assessment, options. The job names the stored revision; the revision, its
SHA and every solve of it are unchanged; `role: decision` keeps its binder refusal.

**D3. A decision is a `role: fixed` specification; its variable is the one parameter that specification binds to,**
found by two bind probes at the box ends (exactly one parameter changes, bitwise to the written value; nothing else in
the binding changes; else `DECISION_NOT_CONTINUOUS`). Units are the kind's SI unit. **Decisions on derived quantities
(ADR 0057's assignment from ADR 0032):** whatever a specification may target, a decision may target — the binder's v1
targets now, F-wave derived-quantity specifications when they land, with their degeneracy refusal. OPT never swaps
specifications.

**D4. One NLP host protocol** (`studies/nlp/host.py`): `Syn001NlpHost` (M03, bit-identical) and `RevisionNlpHost`.

**D5. The equality set is the held-regime system:** the final converged region attempt's rows, free columns and label
rows (recorded in memory on `RegionResult`), selected by id from the one compiled problem and twin, with regime-pinned
columns held at their certified values. The alias rows are the plan's; Q3 is checked on them.

**D6. V1 is the production route, cold:** the candidate document re-bound on the recorded route, solved from the
registered initializer with the job's policies and no warm start; its bundle is an ordinary revision bundle of the
candidate, so committing the result's change-set and solving reproduces the certificate.

**D7. Phase regimes are held by admissibility rows** (bubble/dew test multiplied by the feed total for single-phase
lifted splits; saturation distance for declared single-phase thermal ports; flow bounds for two-phase). The PH-type
split's margin is the TP margin at its converged (T, P). An optimum on a regime boundary is `KKT_POINT_VERIFIED` *of the
held-regime problem*, with `phase_bounds_active` and `regime_note`; a re-solve in another regime is `NOT_VERIFIED`
(`PHASE_REGIME_CHANGED`).

**D8. Job operation `optimize`** via `submit_job`; admission refuses only a missing audited solver
(`nlp_solver_unavailable`, no job created); stages `resolve`, `starts`, `optimize`, `record`; ends `completed` whatever
the report status; cancellation at stage, start, solve-trace and Ipopt-iteration boundaries; an interrupted job writes no
report. `validate(task="optimization", optimization=<request>)` runs the static readiness only and returns
`READY_FOR_OPTIMIZATION`, `INVALID` or `DRAFT`; without an audited solver it is `unsupported nlp_solver_unavailable`
before the revision is read.

**D9. The optimisation record** (manifest, request, revision, report, per-start start/V1 bundles, optimizer and
verification records) has identity `optimization_sha256` over (format, request, revision, route, solve and check
policies). `reproduce` replays the certification chain (integrity, every bundle through `reproduce_bundle`, V2–V7
recomputed, classification recomputed) and needs no Ipopt; the search is recorded evidence, not identity.

**D10. Platforms.** OPT runs where G-A10 has a `PASS` inventory for the running platform (linux x86-64 today);
elsewhere `NLP_SOLVER_UNAVAILABLE(<platform>)`. Replay runs everywhere.

## Alternatives rejected

- `role: decision` in the revision, or objectives in the revision: `value` and `bounds` are exclusive in a
  specification; two sources of a box; a v1 schema change. (D2)
- Mapping decisions to parameters by id text (R-019); automatic specification swaps. (D3)
- A revision-only copy of M03's closure, gray box and verification. (D4)
- E01's full-declaration sensitivity host as the NLP system: not the certified function on single-phase lifted splits
  (R-010's trivial branches). (D5)
- A V1 warm-started from Ipopt's state: couples the truth to the optimizer. (D6)
- Refusing PH-type splits; smoothing regime switches; relying on V4 alone with no admissibility rows. (D7)
- F7's `submit_run` now; a synchronous `optimize` operation. (D8)
- A bitwise Ipopt re-run as the replay. (D9)
- FD or reduced-space derivatives for co-simulated units; a SciPy fallback optimizer (ADR 0032 N2 stands). (D1)

## Consequences

- Every existing record, bundle, key and replay is unchanged (F0 M1–M9; M03's A32 report bytes; E01 tests).
- `tests/test_t08_w2_unsupported.py::test_u05_…` changes on purpose: the default-install refusal code becomes
  `nlp_solver_unavailable` (listed in `AMENDED_TESTS`). The `validate` and job-tool descriptions change: an agent-surface
  change for the next release's V17 carry.
- Results are local, first order, for the start's held regime; `global_optimality: false` in fields.
- The surface chain gains OPT's link at merge, indexed by merge order (§4.13).

## Migration impact

None for existing documents, runs, certificates, bundles or fixtures. The schemas change additively; tests that pin
their bytes are amended on purpose citing this ADR.

## Acceptance evidence

Design note §6: identity G1–G3; held system and decision map G4–G6; analytic optima G7, G8, G10 (mpmath expectations
from the SYN-001 coefficient table); regime-change and route refusals G9; default install and aarch64 G11; job ≡ library
G12; replay G13; cancellation G14; surface chain G15; candidate = simulation G16; schema and readiness G18; cost and LCA
against E01's hand models with an independent derivative-free optimum G19, G20; full gate and both CI legs G21.

## New catalogue codes (ADR 0058 C3)

Readiness and report reasons: `OPTIMIZATION_ROUTE_UNAVAILABLE`, `REVISION_UNBOUND`, `REVISION_MISMATCH`,
`DECISION_UNIT_NOT_INTERNAL`, `DECISION_NOT_CONTINUOUS`, `TOO_MANY_STARTS`, `REGIME_MARGIN_UNDEFINED`,
`START_NOT_CERTIFIED`, `PHASE_REGIME_CHANGED`. API refusal detail: `nlp_solver_unavailable`. Registered by whichever of
OPT and MSG merges second.

## Register entries (drafts, unnumbered)

- **OPT: the optimisation formulation is a separate request document; decisions are `role: fixed` specifications mapped
  to parameters by bind probes.** Rejected: `role: decision` in the revision; id-text mapping. Normative: design §3 D2,
  D3, §4.2.2. Watch for: a binder change that lets `role: decision` bind without an ADR.
- **OPT: decisions on derived quantities = whatever a specification may target (ADR 0032 open item, assigned by
  ADR 0057).** Rejected: automatic specification swaps. Normative: design §3 D3.
- **OPT: the NLP equality set on a revision is the held-regime system of the final converged region attempt.**
  Rejected: full declaration minus alias rows. Evidence: G4. Watch for: an NLP built on `revision_sensitivity_host`.
- **OPT: V1 is the cold production route on the candidate document.** Rejected: warm start from Ipopt's state.
  Normative: §3 D6. Watch for: `warm_start` passed into V1.
- **OPT: phase regimes held by admissibility rows; PH-type margin = TP margin at the converged (T, P); Q4 held mode for
  V5 only.** Rejected: refusing PH-type splits; smoothing. Normative: §3 D7, §4.7. Watch for: Q4 `held` used outside V5.
- **OPT: R-129/R-191 superseded for `validate(task="optimization")`** — a `ValidationReport` with a request and an
  audited solver; `unsupported nlp_solver_unavailable` otherwise. Rejected: keeping `task_unsupported(optimization)`.
- **OPT: job operation `optimize` (ADR 0019 Amendment 16); replay re-checks the certification chain, not the search.**
  Rejected: `submit_run` now; bitwise Ipopt replay. Watch for: Ipopt imported on a replay path.
- **OPT: R-860 lifts** — revision NLP host and optimisation bindings lifted; TR assessment objectives, θ decisions,
  discrete regimes and the standalone assessment binding stay. Normative: §3 D10.
