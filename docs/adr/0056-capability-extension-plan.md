# ADR 0056 — Capability extension plan: the restrictions Frank lifted on 2026-11-01, as planned packages

**Status:** **Accepted, 2026-11-01** — Frank's directive (verbatim below); the packages are planned, not built. Each package
still gets its own design pass, ADR where a frozen interface or a scientific semantic changes, manifest and review.
**Author:** build lane (orchestrator), from Frank's directive; no design-lane ruling is made here.
**Builds on:** R-923 (co-simulation allowed), R-924 (no unnecessary restrictions on capability), ADR 0008 (transient
readiness), plan v1.2 (this ADR adds packages to it; it changes no existing package's acceptance evidence).

## Frank's directive (2026-11-01, verbatim)

> "All restrictions in the table, I want lifted. This is not needed right away, but should be planned. Also windows and
> mac users should be able to use OpenFlowsheet. Otherwise it is very restricted. Explicitly plan for the extended
> capabilities."

"The table" is the list of capability restrictions put to Frank on 2026-11-01 (rows 1–10 below). Earlier the same day he
reversed the co-simulation exclusion and set R-924.

## Decision

Each restriction below is lifted as a planned capability. Until its package lands, the current behaviour stays exactly as
it is today: the capability returns its typed `unsupported` / refusal (CLAUDE.md "no placeholder success paths"). Lifting a
restriction never relaxes a check: the result of a newly admitted capability is declared, carries its limitations and
states the evidence it has and lacks (R-924).

| Row | Restriction today | Registered in | Package | Lifts it by |
| --- | --- | --- | --- | --- |
| 1 | Steady state only; dynamics deferred | R-001, blueprint §2.2, ADR 0008 | **TX** transient | Holdups, a DAE integrator, transient verifier and replay on ADR 0008's readiness (A1, A2, X1–X11); external models quasi-steady, model exchange **and co-simulation** (R-923) |
| 2 | External models start cold every call; the coupled reactor's initial iterate is refused | R-224, R-287 (M02 N6) | **X02** warm start | A declared warm start (previous converged state, or a user iterate) for external and coupled units; the certificate checks the converged answer independently; bitwise identity across warm/cold is not claimed and the cache key states whether a warm start was used |
| 3 | Library-only providers and units (`pr-lib-v1`, `syn001.cascade`, the library-only rule) | R-809, R-807, R-561 | **X01** (extended) | X01's one registration point per provider makes every conforming provider and unit selectable in flowsheets, CLI, HTTP and MCP; library-only becomes a transitional state, not a policy |
| 4 | No liquid–liquid split (LLE / VLLE) | R-709 | **X08** liquid–liquid | An interface ADR (`FlashResult` with more than one liquid), stability-based phase split, three-phase flash, decanter and extraction units, verifier support; on X01's activity models |
| 5 | Linux only; the reactor's child process refused on Windows, best effort on macOS | R-221 (ADR 0033 D2), README | **X07** cross-platform | Windows and macOS supported: CI legs on `windows-latest` and `macos-latest` (arm64), process isolation and kill chain per platform (Job Objects on Windows, process groups on POSIX), path and spawn handling, per-platform reference records where floating point differs, the support envelope's machine axis, install docs; the `nlp` and reactor environments on all three |
| 6 | An installed package's bundles replay `NOT_RUN` (no lock in the wheel) | R-140 | **X05** replay from the wheel | The wheel carries the environment record replay needs; an installed package replays its own bundles, with the environment match stated |
| 7 | Only ADR 0001's input units accepted | R-077 | **X04** units of measure | A unit registry for inputs and outputs (°C, bar, kmol/h, …) converted at the boundary; internal state stays ADR 0001's SI; display units in the web shell |
| 8 | No resume, no branches, no in-band policy administration, no MCP over HTTP, no further solve policies | R-110 | **X06** application capabilities | MCP over HTTP first (remote agents), then branches (what-if revisions), job resume, further solve policies, policy administration |
| 9 | Column on nonideal bases limited; the pump refused on Wilson | R-631, R-819 | **X10** basis coverage | First a measured inventory of which unit × basis pairs refuse today (some may be lifted by S10-C and S11); then every physically meaningful pair is built or carries a stated limitation |
| 10 | Peng–Robinson liquid regime deferred; reactor domain a narrow box | M02 N5, N7 (R-315) | **X09** domain widening | The PR liquid regime and pure-NH₃ flash; a wider reactor inlet box with a start strategy (needs the reactor owner's model behaviour outside today's box) |

Already planned and not repeated here: optimisation of revision flowsheets (lifts E01's typed refusals, R-860, R-129;
next package), revision-region continuation, PrISMa. Not yet designed, stated as such in the README: rate-based
columns, global optimality — candidates for a later round under R-924.

## Order (default; Frank may reorder)

| Release line | Packages | Why this order |
| --- | --- | --- |
| 0.4 | ADR 0055 parts 1–3; optimiser on revision flowsheets; **X04** units; **X05** replay from the wheel; **X02** warm start; **X10** inventory | Small or already queued; each makes the existing capability more usable |
| 0.5 | **X07** cross-platform; **X01** extensibility (with row 3); **X06** MCP over HTTP | X07 early: every later package is then built and tested on three operating systems from the start, which is cheaper than porting afterwards |
| 0.6 | **X08** liquid–liquid; **X09** domain widening; X10 gaps; PrISMa (on X01's isotherm models) | X08 needs X01's activity models |
| 0.7+ | **TX** transient, co-simulation included | Largest; ADR 0008 keeps the steady modules ready for it |

DECISION (orchestrator, 2026-11-01): X07 in the 0.5 line rather than last → yes. Alternative: after TX. Reversible by:
moving the row.

## Per-package entry conditions (standing)

- A package that changes a frozen interface (plan §2.1, §2.2), state/units semantics, phase logic, residuals, certificates
  or replay identity starts with its design-lane pass (`architect` or `specifier`) and its ADR; the others start in the
  build lane.
- Each design brief carries R-924 and this ADR: exclusions inside a package need the reason R-924 demands.
- X07 measures before it decides: which tests are platform-sensitive (bit-identity, BLAS, subprocess, paths), and which
  dependencies lack Windows/macOS builds (the `nlp` extra's conda stack, PyMRM).

## Superseded

The "stays library-only", "refused", "excluded" and "deferred" parts of R-001, R-140, R-221 (Windows refused), R-224 (cold
only), R-287, R-561, R-631, R-709 (LLE out), R-077 (every other unit refused), R-110, R-807, R-809, R-819 (pump refused on
Wilson) are superseded as policy; each stays the behaviour until its package lands. M02 N5–N7 and the "Linux only" line of
the README likewise.

## Affected requirements and migration

No existing acceptance evidence changes. Each new package registers its own assertions. The support matrix, README and
CHANGELOG keep stating the current restrictions until the package that lifts each one merges (`tests/test_readme_current.py`
and the envelope keep them honest).

## Amendment 1 — 2026-11-01: user-feedback packages (MSG, ST, X11)

Source: the tutorial session's feedback batches 1 and 2 (`docs/USER_FEEDBACK.md`), and Frank's direction R-926.

| Package | What it adds | Line | Placement by |
| --- | --- | --- | --- |
| **MSG** student-readable messages | FB-05, with FB-01 (re-run `create`, `exist_ok=True`) and FB-03 (failure on `RunResult`, a useful `not_found`). What, where, why and what to do; the failure kind (input, not supported, numerical, bug); typed codes kept; `explain <code>`; a beginner-mistake corpus in CI. Architect pass first | 0.4, ahead of X04 | Frank (relayed, 2026-11-01) |
| **ST** stream table | FB-06, with FB-02. Post-solve per-stream T, P, molar and mass flow, composition, vapour fraction, h, s, density; an overall energy-balance summary; API, artifact, CLI | 0.4 | default |
| **X11** component data infrastructure | FB-07 and R-926. Identity keys; a record schema (value or correlation, units, validity range, kind measured/fitted/estimated, uncertainty, retrieval provenance); source adapters behind one interface (a bundled open databank, external libraries, user files, user-licensed databanks, web fetchers such as NIST WebBook, PubChem and ThermoML, group-contribution estimation flagged as estimated); regression from data to correlations, later k_ij; consistency checks as evidence; records pinned by hash into revisions and replay; agent operations (search, fetch, fit, validate, register). Architect and specifier passes first; R-706 governs what ships | 0.5, beside X01 | default |
| FB-04 (1) | Two-phase isentropic reference for a vapour turbine outlet (part of L-TH-4). Specifier pass first | 0.4 | default |
| FB-04 (2) | Regime discovery, so stream phases need not be declared (L-TH-1, L-TH-6) | 0.6, with X08 | default |

Acceptance case for the X01 + X11 + X09 + X10 chain: Seider's vinyl chloride process (Ch. 2, route 3) against its Table
2.7 stream table, at the end of the 0.6 line. It needs a basis-independent conversion reactor, which is added to X10's
gaps. Seider is a licensed copy, so only individual numbers with page and table citations enter the repository.

DECISION (orchestrator, 2026-11-01): X11 in the 0.5 line beside X01 → yes. Alternative: 0.4. Reversible by: moving the
row. Reason: X11's records feed X01's property methods, and its liquid-phase use needs X09.

