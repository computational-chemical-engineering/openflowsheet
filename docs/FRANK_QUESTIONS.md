# Questions for Frank

Questions only Frank can answer (scope, value judgments). Each carries the default that unattended work proceeds on.

## C2 — OpenIDAES-450 development / held-out split (2026-10-21)

- **C2-Q1. What should a release gate score on the held-out half?**
  The split says the held-out half is scored only at release gates. It does not say *what* is scored.
  - **Default:** the coverage classification of every held-out case (free), shown next to the development half with
    the gap.
  - An agent campaign on held-out cases (spend) happens only when a release registration asks for one. It draws its
    own seeded sample from the held-out half.
  - Reference: `docs/derivations/C2-OpenIDAES-450-split-registration.md` §11 Q-1.

- **C2-Q2. Should 17 more cases count as development?**
  Your rule made W27's 45 cases (and its 3 canaries) development. Another 17 cases are named in committed specs,
  tests and reviews: registered test states, stubs, the W27 verdict. Their content has been read and discussed.
  - **Default:** yes, they are development. That gives 65 exposed cases, 225 development and 224 held-out.
  - Saying no means a new (v2) draw before any held-out score is reported.
  - Reference: registration SPLIT-R04, R-488.

## C1 — ADR 0008 Amendment 2 (transient readiness at 0.2.0), 2026-10-21

- **Q-B1. Are the holdup units added after Amendment 1 rigid vessels?** Amendment 1's Q-A1 covered the five SYN-001 holdup units. Since then the project has added the C1 heater, the C1 flash, the three C1 reactor ids (external, stand-in, surrogate) and the SYN-001 kinetic CSTR. For each of these, is it a fixed-volume vessel, so that a later dynamic version uses the same energy row as the steady one? **Default: yes.** No file changes. If a liquid-full CSTR is later pressure-driven, it falls under the index-2 case (U–H.7), which the transient package must handle or refuse.
- **Q-B2. Should "co-simulated" external models ever be allowed?** In co-simulation the external program steps itself through time and keeps its own hidden state between calls (FMI co-simulation style). This conflicts with ADR 0008 D2.3 (states live in `x`) and with the exact experiment cache. **Default: no.** The transient package admits external models only as quasi-steady maps or in model-exchange form, where the states are exposed (ADR 0008 A2, X11). Allowing co-simulation later takes an ADR that revises D2.3.

## S01 (2026-10-21)

- **Q-S01-1.** In S01, a cascade where some stages carry no flow while others do (for example, a single liquid side feed at
  the bottom stage with nothing entering from above) is not claimed to converge. S01 promises only that the solver reports a
  typed failure or a checked root, never a false success (`docs/derivations/S01-spec.md` §4.7, A19). Is that acceptable for
  S01, with the capability left to a later package if a column case needs it? **Default: yes.**
