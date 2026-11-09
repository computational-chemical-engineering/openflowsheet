# OpenFlowsheet roadmap, 0.4 to 1.0

Status: **Accepted**, 2026-11-02 (Frank, stage 5, "Accept as is"). Recorded by ADR 0057. The design behind
it is `docs/roadmap/target-architecture.md` ("the note"); the scientific rulings are `docs/roadmap/foundation-rulings.md`.
This page is for Frank and for an agent about to start a package.

## How to read it

- **Foundations** (F0–F8) are the shared structures every feature stands on, built first and in order, so that no
  feature fixes a structure a later one would have to break. **Packages** are the features.
- Design pass: *architect* (software design), *specifier* (scientific semantics and test cases), or *none* (the build
  lane starts straight away). Lines are provisional except MSG before X04 (Frank). Every package keeps its own ADR,
  evidence manifest and reviewer pass.

## The foundations

- **F0 Corpus identity gate.** Proves released numbers, hashes and replays unchanged and no frozen file edited.
- **F1 Extension registry.** One place where extensions register; admission is computed from what they declare.
- **F2 Material model and revision schema v2.** Streams described as amounts, specific enthalpy and pressure; solids,
  attributes, electrolyte bases; energy and signal connections; reaction sets; the new revision document.
- **F3 Component data.** Content-addressed component records with provenance and rights, pinned by hash.
- **F4 Property methods.** Methods composed from records, one enthalpy reference per flowsheet, methods chosen per
  unit side and substream, and one thermo interface that units call.
- **F5 Phase equilibrium.** N-phase flash, stability tests, phases discovered rather than declared.
- **F6 Unit framework v2.** Generic `std.*` units for every method, a coverage matrix in CI, templates, user equations.
- **F7 Problem layer v2.** Dynamics (holdups, controller states, events), objectives and run kinds.
- **F8 Identity and replay v2.** Data locks in bundles, rights-aware replay, decision records for adaptive solvers.

## Packages by release line

Format: **package**: what it delivers · needs first · design pass.

### 0.4: boundary work, the gate and the design wave

- **MSG**: messages saying what, where, why and what to do; `explain <code>` · nothing · architect.
- **ST**: stream table and energy summary · nothing (soft: X04) · none, within the note's ST constraints.
- **X04**: units of measure at the boundary (°C, bar, kmol/h) · MSG · none.
- **X05**: an installed package replays its own bundles · nothing · none.
- **X02**: declared warm starts for external and coupled units · nothing · architect.
- **OPT**: the optimiser on revision flowsheets · nothing · architect.
- **X10 inventory**: measure which unit × property-basis pairs are refused today · nothing · none.
- **RRC**: revision-region continuation · nothing · architect.
- **F0**: the corpus identity gate, plus line-ending rules for hashed files · nothing · none.
- **W1**: design wave for all foundations (below) · rulings done · specifier, then architect.
- Release procedure (ADR 0055 parts 1–3) also runs in 0.4; it is outside this roadmap.
- *Line acceptance:* F0 green; the v2 core schema frozen. *(Amended 2026-11-09, Frank, decision board `rel04-line-acceptance`: "ADR-F1 to ADR-F8 Accepted" moved to 0.5; ADRs 0060–0067 stay Proposed.)*

### 0.5: platforms, registry, data and the new schema

- **X07a**: Windows and macOS CI legs and a platform layer (paths, processes, locks) · nothing · none.
- **F1**: the extension registry · F0 · architect (W1).
- **X01 rest**: library-only providers and units become selectable; plugin docs · F1 · none.
- **F3**: component records and store · F1, rulings · architect (W1).
- **F2**: material model and revision schema v2 · F1, rulings · architect (W1).
- **F8**: identity and replay v2 · F2, F3 · architect (W1).
- **X06**: MCP over HTTP, branches, job resume, further solve policies · nothing · architect.
- *Line acceptance:* ADR-F1 to ADR-F8 Accepted (moved from 0.4, Frank 2026-11-09); a v2 revision with store-pinned
  records solves on the legacy route on all three OSes; 0.3.0 bundles replay everywhere.

### 0.6: multiphase core and generic units

- **F4**: property methods and thermo interface · F2, F3 · architect (W1).
- **F5**: phase equilibrium, including regime discovery (FB-04 part 2) · F4 · architect (W1).
- **F6**: unit framework v2 and the `std.*` seed · F5 · architect (W1).
- **X10 gaps**: every physically meaningful unit × basis pair built or refused with a reason · F6 · none.
- **X09**: PR liquid regime, pure-ammonia flash, wider reactor box · F6 · specifier.
- **X08**: decanter and extraction (LLE, VLLE) · F6 · specifier.
- **X17**: viscosity, conductivity, diffusivity · F4 · specifier.
- **X11 rest**: data fetchers, regression, estimation flagged as estimated · F3, F4 · specifier.
- **PrISMa**: adsorption isotherms as an equilibrium phase · F5 · specifier.
- *Line acceptance:* Seider's vinyl chloride process against its Table 2.7; the textbook turbine with no declared
  phases; a VLLE decanter; a complete coverage matrix; `std.*` proved equivalent to the legacy units; the preview parts
  of the v2 schema frozen.

### 0.7: dynamics

- **F7**: problem layer v2 · F6 · architect (W1).
- **TX**: transient simulation with controllers and co-simulation · F7, F8 · architect and specifier.
- **X13**: Gibbs and kinetic reactors · F6 · specifier.
- **X07b**: optimisation and reactor environments on three OSes · X07a, F8 · none.
- *Line acceptance:* a flash drum with a phase-change event and a PI level loop; a co-simulated unit; a Gibbs reactor;
  the integrator agrees with IDAS on the registered set.

### 0.8: design toolkit

- **X12**: sizing, costing, utilities, profitability · F6 · specifier.
- **X14**: rigorous exchangers, pinch targets · F6, X17 · architect.
- **X16**: PFD editor and reports · ST, F6 · architect.
- **X15**: CAPE-OPEN thermo and units (Windows) · X07a, F6 · architect.
- **X22**: rate-based columns · X17, F6 · specifier, then architect.
- **X21**: petroleum assays · F5, F6, X09 · specifier.
- *Line acceptance:* a costed flowsheet with utilities and a steam-heated exchanger, shown as a PFD; a rate-based
  absorber; an assay-based preheat train.

### 0.9: batch, relief, synthesis, electrolytes

- **X25**: batch recipes · TX · architect.
- **X26**: relief, blowdown, relief sizing · TX · specifier.
- **X24**: superstructure (MINLP) synthesis, then HEN synthesis for X14 · OPT, F7, F8, X06 · architect.
- **X18**: electrolytes · X13 · specifier.
- *Line acceptance:* a batch recipe; a relief scenario with blowdown; a small synthesis whose answer matches full
  enumeration; an electrolyte case.

### 1.0: solids, polymers, P&ID

- **X19**: solids with particle size distributions · F6 · specifier, then architect.
- **X20**: polymers · X13 · specifier.
- **X23**: P&ID drawing and DEXPI exchange · X16 · architect.
- *Line acceptance:* a solids train with a PSD; a polymerisation; a DEXPI round trip.

## Design waves

- **W1, during 0.4.** A short specifier pass rules on the five open items (the conserved-basis boundary, the enthalpy
  anchor, EOS phase families, two dynamic-holdup questions). Then architect passes P1 (F1, F3), P2 (F2, F4, F5) and P3
  (F6, F7, F8), with one reviewer pass per ADR set. The v2 core schema freezes when W1 ends.
- **After W1, one line ahead:** during 0.5 the 0.6 packages are designed, during 0.6 the 0.7 packages, and so on.
- At most two design agents at a time; one design pass and one reviewer pass per package.

## Gates

- **F0, the corpus identity gate,** before every foundation merge and on every CI leg once X07a exists: revision hashes,
  model versions, run fingerprints, state vectors, certificates, cache keys, 0.3.0 replays, schema round trips, and
  the bytes of every frozen legacy module. A failure blocks the merge.
- **Foundation exits.** Numbered exit tests per foundation (note §3), most taken from the rulings' assertions.
- **Coverage matrix** (from F6). Every admitted unit × method pair must reach `VERIFIED` in CI; every refused pair
  must name the missing capability.
- **Equivalence** (F6). `std.*` must match the legacy units on the same physical quantities, first on the old state
  variables, then on the new ones.
- **Freeze points.** The v2 core at the end of W1; the method, phase-assertion and template slots at the end of 0.6.
- **Package gates:** the integrator against IDAS (TX), LOA against enumeration (X24), F6 scaling, F4 batching.
- **Always:** the full gate before a merge to `main`, and CI green on both architectures (CLAUDE.md).

## Decisions already taken

Mass-specific enthalpy on streams; water as the default first key for ordering liquids; a legacy unit family takes no
new v2 work once `std.*` matches it everywhere, while old revisions keep running it; the freeze points above; FB-04
part 1 dropped (F5 and `std.turbine` solve the turbine; MSG explains the limitation meanwhile); MSG in 0.4 ahead of X04;
the full scope (R-927).

## What would change the plan

- **A specifier ruling that departs from a proposed default** on one of the five open items. Each one changes one
  foundation ADR, not the order.
- **CasADi too slow at 10 000–100 000 variables** (the F6 scaling test). An architect pass on the expression layer
  follows, recorded as an ADR; rate-based columns and dynamics could slip.
- **The optimisation stack missing on Windows or macOS** (X07a). OPT and X24 would move behind X07b, or a pip-only
  route would be added.
- **Frank prefers the design toolkit before dynamics.** Swap 0.7 and 0.8; nothing breaks.
- **A package design finds a structure the sketches missed.** An additive ADR if possible; otherwise a new decision
  before the freeze point it touches.
- **Foundations taking longer than expected.** Only packages that fix no core structure may move earlier.
