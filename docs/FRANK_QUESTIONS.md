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

## S02 (2026-10-22)

- **Q-S02-1.** S02's total condenser always returns its liquid exactly at the boiling point (saturated). A condenser that
  cools the liquid further (subcooled reflux) and a reboiler that vaporizes everything are not offered; asking for them gives
  an "unsupported" answer. Is that acceptable for S02? **Default: yes** (`docs/derivations/S02-spec.md` §1).
- **Q-S02-2.** The column can be specified by reflux ratio, boil-up ratio, distillate or bottoms rate, or duties. It cannot
  yet be specified by a product purity, a component recovery or a stage temperature (the specifications engineers often
  want, but which need extra checks). Should these wait for a later package? **Default: yes** (§3).
- **Q-S02-3.** The math shows that some phase patterns in a column cannot be solved (for example a fully liquid stage sitting
  on a boiling stage). The current phase-switching logic may try them and then stop with a reported failure — never a false
  answer. Fixing that means changing the shared phase logic, which affects every unit. Should S02 leave it, record the
  measured behaviour, and let S03 decide? **Default: yes** (§4.3, R-533).
- **Q-S02-3, follow-up (Amendment 2, 2026-10-22).** Measured: the column solver does walk into such patterns after an
  overshooting Newton step and then stops with a "singular matrix" failure, although a gentler route (continuation) reaches
  the answer every time. The shared phase logic is left as it is (your default); instead the gentler route is now also tried
  after that particular failure (ADR 0044, which touches the shared recovery rule for every unit). No answer needed unless you
  object.
- **Q-S02-4.** A column specified by its two heat duties can have two different valid steady states (measured: the
  total-condenser case M2 at its own duties has a second one with a much smaller distillate). The solver returns whichever its
  starting point leads to, and S02 records both without choosing. Should a later package add a rule for which steady state a
  duty-specified column returns (for example, "the one reached by continuation from the starting estimate")? **Default: no
  rule now; both states registered and the multiplicity disclosed** (S02 §18.4, R-549).

## D1 ruling round (2026-10-22)

- **D1-Q1.** Your queue rule says a package merges "with a tested manifest where the package has one". D1 reads it as
  follows: the cloud C-items and design-lane ruling rounds carry no manifest and merge on the full gate plus CI on both
  architectures, recorded in the merge message. Anything with plan-level code and claims carries one; L01 is
  renumbered S04 for that, because the manifest schema admits no `L` id and `L01` is also a support-matrix row.
  **No answer needed unless you object** (`docs/reviews/D1-rulings.md` Q6, R-565).
