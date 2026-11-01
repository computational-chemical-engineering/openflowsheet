# Architect brief 1 — target architecture for the full simulator

Status: brief, 2026-11-01. Roadmap stage 2 (Frank, "Start now"). Companion digest: `docs/roadmap/00-core-inventory.md`
(today's core structures, with `file:line` and excerpts). Deliverable: `docs/roadmap/target-architecture.md`.

## 1. The question

Which core structures does OpenFlowsheet need so that every capability Frank has put in scope can be added without
breaking them, and in what order should foundations and features be built?

What must come back:
- a target architecture for those structures;
- the foundation packages that build them, with the ADRs each needs;
- a dependency graph over all planned packages;
- a provisional package sequence with entry and exit criteria;
- the scientific questions a specifier must settle first, and only those that shape a foundation.

## 2. Why this needs the architect

Frank (R-927, 2026-11-01, verbatim): "The aim is a 'real simulator' so all these features need to be on board at some
stage, including electrolytes, solids, polymers, petroleum assays, rate-based columns, P&ID drawing and superstructure
(MINLP) synthesis. The issue is planning. I am not in a hurry to have some features available as soon as possible. What
is important is to have a very well designed implementation, that runs well, is very flexible, can very well be used by
agents etc. So what is important is to have a very good plan."

Up to 0.3 the code grew one capability at a time, for the cases each release needed. Some core structures were fixed for
today's scope: stream state variables, phase labels, component sets bound to one provider, unit models with per-basis
coverage, and steady-only problems. Each planned capability that breaks one of them later costs a migration across
evidence, replay identity and frozen interfaces. The leverage is in finding those breaks now, while nothing of the new
scope is built.

## 3. Current state

See `docs/roadmap/00-core-inventory.md`. Facts used below:
- Releases: 0.3.0 and 0.3.0.post1 are on PyPI; main is at 0.4.0.dev0, with about 14 800 tests in the full gate.
  Development is paused for budget; planning is not.
- The blueprint (`docs/blueprint-v3.1.md`) is the architectural authority. Its decision table D01–D20 binds unless an ADR
  departs from it. Relevant rows, verbatim:
  - **D01:** "Own solve-plan construction, initialization, tearing, hybrid SM/EO execution, globalization policy,
    continuation, diagnostics, and verification. Reuse expression engines, AD, sparse factorization, and constrained
    optimization."
  - **D02:** "Python-first orchestration; CasADi is the default expression/AD engine … A residual/Jacobian callback
    adapter provides a second implementation route, not a second full compiler."
  - **D08:** "Public contract is capability-based properties, states, and derivatives. Prefer internally consistent
    potentials for native models. Do not require every external provider to expose a potential."
  - **D09:** "Begin with a guarded procedural flash and explicit active-phase management. Add one validated smooth EO
    formulation for selected systems later. Critical and unsupported phase regions return typed limitations."
  - **D10:** "Exact-input cache only in residual, derivative, and final verification paths."
  - **D14:** "Verify a solution against a pinned mathematical model and policy. Independently track empirical model
    validation and optimization evidence."
  - **D15:** "Local Python/CLI transactions start with the first release; a small MCP/HTTP binding follows in v0.1."
  - **D18:** "SSP, FMI, DEXPI, CAPE-OPEN, and semantic-web projections are demand-driven adapters." The demand now
    exists: R-926, R-927.
  - **D20:** "Separate deterministic structural artifacts from adaptive numerical decisions and timing."
- 55 ADRs (`docs/adr/`). The ones closest to this question:
  - 0001: state, units, zero flow;
  - 0002: canonicalisation and schemas;
  - 0003: the compiled-problem backend;
  - 0005: the phase-attempt contract;
  - 0008: transient readiness;
  - 0011: unit models, PH closure, reaction datum;
  - 0019: application contract v1;
  - 0033/0034: external models;
  - 0043, 0045–0047, 0049: providers;
  - 0050/0051: the S11 binding package and bases;
  - 0052: E01 assessment functionals;
  - 0056 with Amendments 1 and 2: the planned packages.

## 4. Constraints and invariants

- **Existing evidence.** Every released case keeps its numbers. A structural change must be proved bit-identical on the
  existing corpus at the old configuration, or carry a registered, explained difference. Replay of released bundles keeps
  working, or is versioned explicitly.
- **Typed refusals.** Unbuilt capabilities return typed refusals; no placeholder success paths.
- **Evidence classes stay separate:** implemented, tested, reviewed, released; and verification, validation,
  optimality.
- **Exact caches.** Residual and Jacobian describe the same function at the same state; exact caches key on exact
  canonical inputs.
- **Cross-platform.** Linux, Windows and macOS (X07, 0.5 line). Every foundation must be platform-neutral by design: no
  POSIX-only process, path or IPC assumptions.
- **Agent-native.** Each capability is reachable through one application contract (Python, CLI, HTTP, MCP), with typed
  results, typed refusals, discoverable capabilities and student-readable messages (MSG: what, where, why, what to do,
  failure kind).
- **Data rights (R-706).** Shipped data needs rights clearance and Frank's decision. User-fetched or user-licensed data
  lives in the user's project (R-926).
- **Frozen interfaces.** Plan §2.1 and §2.2 change only by a design-lane ADR. Name each change and the ADR that carries
  it.
- **Licensing (D04).** Apache-2.0 core with an audited default dependency set.

## 5. Already decided, not open

- **Scope (R-923–R-927, ADR 0056 and its amendments).** Every package in ADR 0056 is in scope:
  - TX transient, co-simulation included;
  - X01 extensibility; X02 warm start; X04 units; X05 replay from the wheel; X06 application capabilities;
    X07 cross-platform; X08 LLE/VLLE; X09 domain widening; X10 basis coverage; X11 component data;
  - X12 economics; X13 reactors; X14 heat exchange and pinch; X15 CAPE-OPEN; X16 PFD and reports;
    X17 transport properties; X18 electrolytes; X19 solids; X20 polymers; X21 petroleum assays;
    X22 rate-based columns; X23 P&ID; X24 MINLP synthesis; X25 batch; X26 relief and safety;
  - MSG messages; ST stream table; FB-04 (two-phase isentropic reference, then regime discovery).

  Also queued: the NLP optimiser on revision flowsheets, ADR 0055 parts 1–3 (release procedure), revision-region
  continuation and PrISMa.
- **Order already fixed.** MSG goes in 0.4, ahead of X04 (Frank). Every other release line is provisional (Am. 2).
- **No unnecessary restrictions (R-924).** Exclude only when a declaration, a typed limitation or a separate evidence class
  cannot contain the problem.
- **Lanes.** Two-lane working (CLAUDE.md), with one design pass and one reviewer pass per package.

## 6. Genuinely open — decide these

For each area: what today's structure fixes (from the inventory), what the full scope needs, the target design, and when
it must exist (before which packages). Also give a migration path that keeps the existing evidence.

1. **Material model.** How the stream and material state generalises to:
   - more than two fluid phases;
   - solid phases and particle size distributions;
   - true and apparent species (electrolytes);
   - pseudo-components (assays);
   - polymer distributions or moments;
   - per-stream attributes in general.

   Extensibility mechanism, and what the solution state and replay identity hold.
2. **Phase equilibrium framework.** An N-phase flash with stability tests and regime discovery. How unit residuals see a
   phase set that is not declared in advance (FB-04, X08). The relation to D09 and ADR 0005.
3. **Property and data layer.** X01 registration, X11 records and identity, X17 transport properties, and CAPE-OPEN thermo
   (X15) as one capability-based layer (D08). Also: provider composition (a mixture model plus a pure-component data
   source), and pinning by hash.
4. **Unit-model framework.** One interface that serves:
   - any basis;
   - steady and dynamic operation (holdups, ADR 0008);
   - user-defined units;
   - rate-based stages;
   - external and co-simulated models;
   - CAPE-OPEN units;
   - sizing and costing hooks (X12).

   How X10's coverage gaps stop recurring for each new basis.
5. **Problem and solver architecture.** One problem representation that carries:
   - the steady EO/SM hybrid (D01);
   - DAE integration (TX);
   - the NLP optimiser;
   - MINLP superstructures (X24);
   - batch recipes (X25).

   Whether D02/D03 still hold for this scope; if one does not, say so with the reason (an ADR, not a survey).
6. **Application and agent contract.** How new capabilities appear uniformly:
   - capability discovery;
   - messages and `explain`;
   - units of measure at the boundary;
   - branches and resume;
   - stream tables and reports;
   - long-running jobs (dynamics, MINLP).
7. **Identity, replay and evidence** across fetched data, platform differences (X07), co-simulation and stochastic or
   adaptive solvers (D20).
8. **Front ends.** Web shell, PFD editor (X16) and P&ID with DEXPI (X23): their relation to the canonical document.

## 7. Already tried and rejected

- **Phase handling.** One declared phase per stream (S11, R-839) works for the 0.3 cases. It fails the textbook turbine
  case (FB-04: a superheated actual outlet with a wet isentropic state, refused either way). The fix is not "declare
  better"; the users who hit it are students.
- **Component data.** Components bound one by one to a single provider (syn001, pr-c1-v1, pr-lib-v1 vapour-only, IAPWS,
  CoolProp one fluid per revision, Wilson for three species) cannot express Seider's vinyl chloride process (FB-07).
- **Basis coverage.** Per-basis unit coverage produced the X10 gaps: the column on nonideal bases, and the pump refused on
  Wilson (R-631, R-819).
- **Shipped data sources.** Rejected for rights reasons as shipped data (R-706): DECHEMA parameters, the embedded
  DWSIM/ChemSep databanks and REFPROP-derived constants. They remain admissible as user-licensed sources (R-926).
- **Release-line fit.** Planning by release line first and architecture second produced ADR 0056's tables. Frank has now
  made those provisional (R-927).

## 8. How the answer will be verified

- An independent `reviewer` pass on the note (roadmap stage 4). It checks:
  - that every package in §5 maps to foundations that support it;
  - that the dependency graph is acyclic and consistent with the stated needs;
  - that each foundation names its migration proof (bit-identity on the existing corpus) and its ADR;
  - that nothing in §5 is relitigated.
- Frank reviews it next (stage 5). It is then committed as ADR 0057 plus `docs/roadmap/roadmap.md`.

## 9. Deliverable

Write `docs/roadmap/target-architecture.md`, at most about 900 lines, with these sections:

1. Summary, one screen.
2. Target architecture per area of §6, each giving: today, needed, design, foundation package, ADR(s), migration proof.
3. Foundation packages (F-ids), with scope, entry criteria and exit criteria.
4. Dependency graph over all packages (F-ids, X01–X26, TX, MSG, ST, FB-04, optimiser, PrISMa), as a table and a mermaid
   graph.
5. Provisional sequence into release lines, with the reasoning.
6. Questions for the specifier (stage 3), numbered. Include only those that shape a foundation, each with why it blocks
   and a default.
7. Risks, and what would change the plan.
8. Frozen-interface changes, listed with their ADRs.

Write only that file and do not commit; the orchestrator commits. Write no production code. Do not start subagents. Never send personal identifiers to external
services. Never touch `~/.config/procsim/`. Do not read `/home/frankp/s10-papers/`, `~/.cache/seider3/` or
`~/.cache/seider4/`.

## 10. Out of scope

- Production code.
- Choosing specific correlations or parameter sets.
- Detailed per-package specifications; those come in each package's own design pass.
- Re-surveying technologies the blueprint settled, unless a planned capability provably needs a departure. In that case,
  give the reason and the ADR it would need.
- Release-procedure mechanics (ADR 0055).
