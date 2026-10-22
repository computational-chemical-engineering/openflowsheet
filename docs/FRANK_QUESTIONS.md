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

## L01 — component-library gaps, development half (2026-10-22)

- **L01-Q1. Who changes W27 so that it can measure the new water route, and when?**
  W27 accepts only one route per property method. It also refuses CO, because the archive's `Co` (cobalt) looks like
  `CO` when case is ignored. L01 may not change W27.
  - **Default:** a small, separate design-lane package (W27 Amendment 3) does both fixes. L01 builds the records and
    the provider now, and waits to plug the route in.
  - Reference: `docs/derivations/L01-spec.md` §8 F-1, F-2; R-526.
- **L01-Q2. Build it, knowing that it unblocks no development case?**
  Water, CO2, O2, ethane and propane can be added as gases with the existing Peng–Robinson method. But every
  development case they would help is also missing a unit (compressor, reformer), and most water cases need steam
  tables (IAPWS-95) instead. The projected number of runnable development cases stays at 0.
  - **Default:** yes, records and provider only (two work orders), because they change nothing already committed and
    the reformer cases will need them.
  - Reference: spec §0, §6.3; R-527.
- **L01-Q3. Which new property method comes next?**
  - **Default:** IAPWS-95 (steam tables). It sits behind most water cases: it is the only method in 8 development cases
    and appears beside other methods in 16 more. It is not started without your go-ahead.
  - Reference: spec §3, §10 Q-3.

## L01 — component records (build lane, 2026-10-22)

- **L01-Q4. May the new `pr-lib-v1` component records ship in the wheel?** T08.A32
  (`tests/test_t08_w2_inventory.py:459`) allows only synthetic records or the vetted M01 records with a rights
  statement in the distribution. L01's nine records (values from chemicals/ATcT, Cantera `nasa_gas.yaml`, JANAF,
  CoolProp cross-checks) have no vetted rights row yet. **Default:** they stay in the repository only
  (`benchmarks/l01/`), not in the package data, until a rights review adds them to the inventory; T08.A32 is not
  amended. Shipping them is a distribution decision for you.
