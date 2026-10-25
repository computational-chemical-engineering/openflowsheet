# Questions for Frank

Questions only Frank can answer (scope, value judgments). Each carries the default that unattended work proceeds on.

## Answers — Frank, 2026-10-22: "accept all recommendations"

Recommendations as put to Frank (session, 2026-10-22); each answer below is now the decision.
- **C2-Q1:** default; coverage classification of the held-out half at every release gate; agent campaigns only when a release registration asks, sampled from the held-out half; any OpenIDAES agent-score claim comes from the held-out half.
- **C2-Q2:** yes — the 17 exposed cases are development (65 exposed, 225 development, 224 held-out).
- **Q-B1:** yes (rigid vessels). **Q-B2:** no co-simulation; a later ADR revising D2.3 is required to allow it.
- **Q-S01-1, Q-S02-1, Q-S02-3:** defaults. **Q-S02-2:** defaults, and purity / recovery / stage-temperature specifications are the next column package.
- **Q-S02-3 follow-up (ADR 0044):** no objection, on condition that ADR 0044's acceptance shows every other unit's results unchanged (bit-identical at the old configuration) by the new recovery path.
- **Q-S02-4:** no selection rule; both states registered and disclosed; add a "multiple steady states possible" warning to every duty-only column specification (new build item).
- **D1-Q1:** no objection.
- **L01-Q1:** a small separate design-lane package (W27 Amendment 3: one route per method relaxed; `Co`/`CO` case clash fixed), applied to the next release's W27 registration; v0.2's W27 stays unchanged.
- **L01-Q2:** accepted (already built).
- **L01-Q3:** IAPWS-95 is the next property method, as a planned v0.3 addition with its own ADR (design lane first), not as benchmark tuning.
- **L01-Q4:** no release ships the nine `pr-lib-v1` records until a per-source rights check (JANAF/NIST, NASA via Cantera, Cantera, CoolProp, `chemicals`, ATcT citation) and an attribution file exist and the design lane amends T08.A32; then they may ship.

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
  CoolProp cross-checks) have no vetted rights row yet. A32 checks every non-synthetic record in the repository, not
  only packaged ones, so L01 also needs a design-lane amendment of T08.A32; until then `wp/L01` fails A32 and is not
  merged. **Default:** nothing from L01 is released until a rights review vets the nine records and the design lane
  amends A32; shipping them is a distribution decision for you.

## C10 — IAPWS-95 (S05), 2026-10-22

**Answers — Frank, 2026-10-23:** C10-Q1 "Yes, as described" (build from the CoolProp-transcribed coefficients, `iapws` as comparison only; nothing ships until a person reads IAPWS's terms and checks Tables 6–8). C10-Q2 "Always 'vapour'" (T ≥ T_c is VAPOR). The S06 answers (Q-S06-1 no new warning; Q-S06-2 typed failure) are recorded on `wp/C11`.

**Ship decision — Frank, 2026-10-23:** "Yes, ship with attribution" — after the workstation Tables check (385 comparisons, 0 mismatches, `af04961e`) and the IAPWS terms quoted ("Publication in whole or in part is allowed in all countries provided that attribution is given to the International Association for the Properties of Water and Steam"). S05 may ship in a release with an IAPWS attribution in NOTICE; this answers ADR 0045's release condition and supersedes R-594's hold (the packaging/binding work order is design-lane, WO-S05-5).

**F-4 (D2, R-615) — open, for the `pr-lib-v1` clean-up package only:** dropping CAS RNs removes W27's identity key, and the shipped m01 file carries five. Not needed until that package starts.

- **C10-Q1. May the IAPWS-95 coefficients ship?** This session could not read IAPWS's terms or the R6-95(2018) tables: iapws.org was refused by the proxy. **Default:** the tests and the provider may be built from the coefficients transcribed from CoolProp (MIT) and checked against `iapws` (GPL-3, used only as a comparison). Nothing ships in a wheel until a person reads the release's terms and confirms the generator's values against Tables 6–8.
- **C10-Q2. How should a supercritical fluid (T ≥ T_c) be labelled?** **Default:** VAPOR. The alternative is to label by density (LIQUID iff ρ > ρ_c). Either label flips somewhere on a 24 MPa boiler path.

## S06 (C11) — column inverse specifications (design lane `specifier`, 2026-10-22)

- **Q-S06-1. Should a column with a purity, recovery or temperature specification carry a "multiple steady
  states possible" warning, as duty-only columns do (C8)?** No registered S06 set shows a second root, and S06
  claims no uniqueness for any set (`docs/derivations/S06-spec.md` §7.4, §14). Warning on every inverse set would
  make the warning say "no uniqueness claim", which is true of every column. **Default:** no new warning; C8's
  duty-only rule unchanged. A later measured second root under an inverse set adds a warning code for that class.
  **Answer (Frank, 2026-10-23):** "No warning for now."
- **Q-S06-2. Is a high-purity endpoint failure acceptable as a typed result for now?** S06 reuses S02's
  bubble-point endpoint unchanged. When the endpoint already sits near total recovery of the specified component
  (U1: bottoms recovery of C 0.9996 at the endpoint), the endpoint is ill-conditioned and the continuation fails at
  its first step, although a regular root exists (M2's); and a total condenser whose reflux fraction is free can see
  the straight path cross negative reflux (U2). The answer is then `inverse_specification_not_reached`,
  typed and checkable, never a false success. Fixing it needs a second easy endpoint for inverse specifications
  (a new algorithm and its own measurements). **Default:** yes, typed result and a §14 limitation; a follow-on
  package only if you want such inverse specifications to solve unattended.
  **Answer (Frank, 2026-10-23):** "Yes, typed failure."

## S07 — CoolProp pure-fluid provider (design lane `specifier`, 2026-10-23)

**Answers — Frank, 2026-10-23:** Q-S07-1 "Yes, they wait" (cryogenic liquids → S07b). **Fluid scope: "Broad list now"** — asked whether S07 starts with the nine S04 fluids and adds more later, or includes many more CoolProp fluids now; Frank chose the broad list. The spec is amended accordingly (S07 Amendment 1).

- **Q-S07-1. May the very cold liquids wait for a later package?** The new CoolProp provider answers each of the
  nine fluids only above the temperature where the fluid would freeze at the provider's top pressure (100 MPa; 80 MPa
  for oxygen). That keeps every answer out of the solid region, and it keeps the answered range a simple
  temperature–pressure rectangle. The price: liquid nitrogen at 77 K, liquid argon at 87 K, liquefied natural gas at
  112 K and liquid hydrogen at 20 K are refused as out of range. Gases and vapours of all nine fluids are answered,
  and so are liquid water, CO2, ethane, propane and liquid oxygen at 90 K. Answering the cold liquids needs a freezing-line check at run time, which is a
  separate package (S07b). **Default:** yes, they wait (`docs/derivations/S07-spec.md` §6.2, R-620).

- Q-A1-1 and Q-A1-3: defaults taken by the session (2026-10-23), reversible; Frank may object.

## S03 — two independent column references (2026-10-24)

- **Q-S03-4** (one-phase sections: converge instead of a typed failure?) — **Frank: "Yes, plan a package"** (2026-10-24).
  Not part of S03: a later package teaches the phase logic to handle all-liquid or all-vapour column sections. Queued.
- **Q-S03-5** (which of S06's specs S03 checks against the tools) — **Frank: "All three"** (2026-10-24): purity,
  recovery and temperature, not purity only. The S03 spec is amended to add the recovery and temperature cases.
- **Q-A2-4** (if no tool can model a column type, what then?) — **Frank: "Plan a 3rd tool"** (2026-10-24). After
  WO-S03-2b, IDAES models the stripper (RC3 family) but not the refluxed absorber (RC4 family, 500 iterations at every
  path position); DWSIM models neither. A later package brings in a third reference tool (candidates: COCO/ChemSep)
  for the column cases with fewer than two references: RC4 (none), RC3 and RC7 (IDAES only). Queued as S09
  (provisional). S03 itself closes with the gap recorded.

## S10 — liquid-capable mixture property method (2026-10-25)

All four answered with the recommended default (Frank, 2026-10-25):
- **Q-F1** first mixtures → **methanol, ethanol, water** (incl. the ethanol–water azeotrope).
- **Q-F2** flowsheets or library → **library only for now** (like S05/S07; flowsheet use with the binding package).
- **Q-F3** ship fitted data → **decide after the rights check** (repository-only until then; come back to Frank).
- **Q-F4** two liquid phases soon → **no** (Wilson only; would-split mixtures refused with a clear message).
- **Q-F5** (IDAES coverage without the states its initializer cannot start) — **Frank: "Yes, enough"** (2026-10-25).
  Note: the premise named I3 and I11; WO-S10-4b's record shows I11 does converge at 1e-4/MA27 (ESC-8), so only I3
  drops out of the IDAES comparison.
- **Q-F6** (try DWSIM's Inside-Out flash on new states in a later package?) — **Frank: "No"** (2026-10-25). DWSIM stays
  a check on model expression, enthalpies' readbacks and phase labels; IDAES is the numerical reference.
- **Q-S09-1** (which third column reference tool should S09 plan for: BioSTEAM, ChemSep-LITE under Wine, or both?) —
  **Frank: "BioSTEAM first (Rec.)"** (2026-10-25). Survey and feasibility spike: `docs/briefs/S09-third-reference-tool.md`.
