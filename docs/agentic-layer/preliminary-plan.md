# Agentic design layer: preliminary plan

Status: **preliminary plan**, 2026-11-02 (orchestrator, from Frank's request; Frank's answers in §8). Not a design and not a
decision. A design pass (architect) and the literature survey (A0) come first when budget allows.

Frank, verbatim: "Next to OpenFlowsheet that is the tool, I would like to design an agentic layer. It should use
heuristics, maybe initially taken for text books like Seider, and later refine it by performing designs documented in
literature, see if these designs can be reproduced / improved, if the all important questions are considered. … I
assume many skills need to be defined, maybe specific agents? Maybe some AI or ML tools needs to be created to help by
design decisions, following systematic design methodologies etc. In the plan you might want to include a literature
search on methodology etc."

## 1. What the layer is

A **process-design assistant built on top of OpenFlowsheet**. Working name: *OpenFlowsheet Designer*.

- **Input:** a design problem: product, capacity, purity, available feeds and prices, site and utility data, and
  constraints such as safety, emissions and budget.
- **Output:** a ranked set of candidate flowsheets. Each comes with a design dossier:
  - every decision taken, the heuristic or method behind it, its source and the alternatives rejected;
  - the simulation and costing evidence from OpenFlowsheet runs;
  - the design questions that were checked, and those still open.

OpenFlowsheet stays the *tool*: simulation, verification, costing and optimisation. The layer is the *designer*:
methodology, heuristics, judgement and bookkeeping. The layer uses only OpenFlowsheet's public contract (Python and
MCP), as any outside user does. Its needs flow back as feature requests, as the tutorial session's do.

## 2. Principles

1. **Methodology-led, not free-form.** Agents follow a registered systematic procedure, such as Douglas's hierarchical
   levels or Seider's synthesis steps. Free-form LLM ideas enter only as tagged alternatives inside that frame.
2. **Heuristics are data, not prompts.** Each heuristic is a versioned record. It holds:
   - its statement, paraphrased, with a page citation;
   - applicability conditions, where possible as checkable predicates (for example, "relative volatility < 1.1");
   - the recommended action and its rationale;
   - its source and a confidence value;
   - known exceptions.

   Prompts refer to records; records are not buried in prompts.
3. **Every number comes from a tool.** No quantitative claim comes from LLM recall. Shortcut estimates, simulations and
   costs come from tool runs and carry their run ids, which mirrors OpenFlowsheet's evidence classes.
4. **Every decision is traceable.** A *design decision record* is like an ADR for the plant. It gives the question, the
   options, the choice, the rule or evidence, and what would change the choice.
5. **"Were all the important questions asked?" is a checklist with coverage.** Each level has a registered list of
   design questions: raw-material purity, by-products, recycle and purge, azeotropes, heat integration, safety, start-up,
   waste. A critic agent checks coverage before a level closes.
6. **Learning is evidence-based.** A heuristic's confidence changes only when reproducing a literature design confirms
   or contradicts it. Each such change is recorded with that case.
7. **Rights.** Textbook heuristics are facts, restated in the project's own words with a citation. Licensed texts such as
   Seider are never copied at length; long tables are not transcribed (the existing rule for the Seider copies). The
   paper corpus follows R-706 and R-926: metadata and our own extractions only, with the PDFs kept in Zotero.

## 3. Architecture sketch

The layer is a **Claude Code plugin**, later possibly an Agent SDK application, with four parts.

### 3.1 Knowledge base (an MCP server)

- **Heuristics:** the records described in principle 2.
- **Design-question checklists:** one per methodology level.
- **Methodology definitions:** levels, steps, entry and exit conditions.
- **Shortcut correlations and rules of thumb:** Fenske–Underwood–Gilliland, Kremser, rough reactor sizing, cost
  exponents. Wherever OpenFlowsheet gains a capability (X12 costing, X14 pinch), the layer calls OpenFlowsheet instead of
  keeping its own copy.
- **Case corpus:** literature designs, extracted into a common form (§5).

### 3.2 Design dossier (state)

One file tree per design project, versioned:
- the problem statement;
- the current level in the methodology;
- the alternatives tree, mapped onto OpenFlowsheet's branches (X06);
- the decision records;
- the open questions;
- per alternative, the evidence: run ids, costs and certificates.

A design can then be resumed, reviewed or replayed.

### 3.3 Agents: few roles, many skills

Most expertise lives in **skills**: instructions plus scripts per methodology step. Only roles that need their own
context or an independent view become **agents**:

| Agent | Role |
|---|---|
| `design-lead` | Runs the methodology, keeps the dossier, chooses which skill to apply, and asks the human at decision gates |
| `design-critic` | Independent: checks question coverage, heuristic applicability and the evidence behind each decision; argues the alternative |
| `case-extractor` | Turns a literature design (paper or textbook case) into a corpus entry: problem, flowsheet (SFILES), key numbers, decisions as stated by the authors |
| `reproducer` | Given a corpus entry's problem only, runs the layer, compares against the authors' design, and reports what matched, differed or improved, and why |

Specialist knowledge areas are skills used by `design-lead`, not separate agents, at first:
- reaction and chemistry;
- separation synthesis;
- heat integration;
- economics;
- safety;
- sustainability.

A specialist area may become an agent later if its context grows large.

### 3.4 Skills: first list, following the methodology

- **Level 1, batch or continuous:** `level1-batch-vs-continuous`.
- **Level 2, input–output structure:** `level2-input-output` (purge, by-product recovery, economic potential EP2;
  needs only stoichiometry and prices).
- **Level 3, reactors and recycle:** `level3-recycle-reactor` (reactor type, excess reactant, recycle and purge,
  equilibrium limits; EP3).
- **Level 4, separation system:**
  - `level4-vapour-recovery`;
  - `level4-liquid-separation` (method selection from property ratios; distillation sequencing heuristics);
  - `azeotrope-analysis` (residue curve maps, distillation boundaries).
- **Level 5, heat integration:** `level5-heat-integration` (pinch targets, utilities).
- **Cross-cutting:**
  - `economic-evaluation`;
  - `safety-screen` (inherent-safety questions, hazard checklist);
  - `sustainability-screen`;
  - `design-report`;
  - `literature-case-extraction`;
  - `heuristic-update`.

### 3.5 AI and ML tools (later, data-dependent)

- **Applicability checker.** Evaluates a heuristic's predicates on simulated properties. It is mostly deterministic, not
  ML.
- **Separation-method selector.** Based on thermodynamic insight: pure-component property ratios lead to feasible
  methods.
- **Flowsheet suggestion and completion** from a graph representation (SFILES), trained on the case corpus. It proposes
  structures; it never decides alone.
- **Superstructure generator** feeding OpenFlowsheet's MINLP synthesis (X24) once that exists.
- **Surrogates and Bayesian optimisation** for screening many alternatives cheaply. Final candidates are always solved
  rigorously.
- **Heuristic refinement:** learning applicability boundaries and confidence values from reproduction outcomes.
- **Multi-criteria ranking under uncertainty:** cost, safety, sustainability, robustness.

Built in this order, because ML needs data: the deterministic tools first, then the case corpus, then the learned tools.

## 4. Literature survey (A0, first step)

The work runs through the `zotero` session: references and PDFs go there, with no local .bib. Its output is
`docs/agentic-layer/methodology-review.md`. Proposed strands, with anchor works to be confirmed by the survey:

- **Hierarchical and heuristic conceptual design.**
  - Douglas, *Conceptual Design of Chemical Processes* (1988);
  - Seider, Seader, Lewin and Widagdo, *Product and Process Design Principles* (3rd ed. 2009, 4th ed. 2017;
    Zotero `seider2009product`, `seider2017product`);
  - Smith, *Chemical Process Design and Integration*;
  - Turton et al., *Analysis, Synthesis and Design of Chemical Processes*;
  - Towler and Sinnott, *Chemical Engineering Design*;
  - Siirola's work on strategic or hierarchical synthesis.
- **Systematic and optimisation-based synthesis.**
  - Biegler, Grossmann and Westerberg, *Systematic Methods of Chemical Process Design* (1997);
  - superstructure and MINLP synthesis (Grossmann and co-workers);
  - phenomena-based synthesis and intensification (Gani and co-workers).
- **Separation synthesis.**
  - Doherty and Malone, *Conceptual Design of Distillation Systems* (2001);
  - thermodynamic-insight methods (Jaksland, Gani and Lien, 1995);
  - distillation-sequencing heuristics.
- **Heat integration:** pinch analysis (Linnhoff et al.) and HEN synthesis.
- **Safety and sustainability in early design:** inherent safety (Kletz); indices for early-stage safety and
  environmental assessment.
- **AI for process design.**
  - Expert systems of the 1980s–90s (what failed, and why);
  - graph and string flowsheet representations (SFILES 2.0, Schweidtmann's group);
  - ML flowsheet completion;
  - reinforcement learning for flowsheet synthesis;
  - LLM agents in chemical engineering, 2023–2026.

  The survey must establish the state of the art and the evaluation practice. Names here are leads, not citations.
- **Design-rationale capture:** IBIS and QOC-style decision records, and how design knowledge is formalised in
  ontologies such as OntoCAPE.

Questions the survey must answer:
- Which methodology should be the backbone?
- How have heuristic systems been evaluated?
- Which public design case collections exist for a benchmark corpus?
- What did earlier AI design tools get wrong?

## 5. Benchmark: reproduce and improve literature designs

- **Corpus.** Textbook cases (Seider's vinyl chloride and others; Douglas's HDA; Turton's cases) and published design
  papers. Each entry holds the problem as posed, the authors' flowsheet in SFILES, the key numbers with page citations,
  and the authors' stated decisions.
- **Blind runs.** The `reproducer` sees only the problem.
- **Metrics:**
  - structural match (graph distance between flowsheets);
  - objective (economic potential or cost) against the authors' value;
  - feasibility (an OpenFlowsheet certificate);
  - question coverage (recall of the design questions the authors or an expert addressed);
  - traceability: every decision has a record.
- **"Improved"** means a better objective under the same constraints, with verified simulations and the reason stated.
  An expert review (Frank) confirms it before it counts.
- **Honesty rules from OpenFlowsheet carry over.** Self-generated designs are not validation. Failures stay recorded.
  The corpus does not get easier to pass.

## 6. Dependencies on the OpenFlowsheet roadmap

| Layer phase | Needs from OpenFlowsheet (ADR 0057) |
| --- | --- |
| Levels 1–2, economic potential | Nothing; stoichiometry and prices only. Can start now |
| Level 3, reactors and recycle | X11 components, F4/F5 thermo, X13 reactors, X06 branches, OPT |
| Level 4, separations | F5 multiphase, X08 liquid–liquid, X09, X10; azeotrope tools |
| Level 5, heat integration and costing | X12 costing, X14 pinch, X17 transport properties |
| Synthesis, ML suggestion | X24 MINLP; a rich corpus |
| Agent use throughout | MSG messages, ST stream tables, MCP over HTTP (X06) |

The layer can therefore start well before OpenFlowsheet is complete. Its early levels and the literature corpus do not
wait for the roadmap, and its needs sharpen the roadmap's priorities.

## 7. Phases (provisional)

| Phase | Content | Lane |
| --- | --- | --- |
| A0 | Literature survey and methodology review (§4) | `zotero` session plus a research agent; Frank reads |
| A1 | Design of the knowledge representation: heuristic record, checklist, methodology, dossier and decision-record schemas; plugin structure | architect, one pass; reviewer |
| A2 | Heuristic extraction from Seider (then Douglas, Smith, Turton), paraphrased and cited, with predicates; double-checked by a second agent | build lane (Sonnet) with specifier checks on predicates |
| A3 | Levels 1–3 skills plus `design-lead` and `design-critic`; first benchmark: Seider's vinyl chloride and Douglas's HDA at levels 1–3 | build lane |
| A4 | Case corpus and the `case-extractor` / `reproducer` loop; first 10–20 cases | build lane; Frank reviews |
| A5 | Levels 4–5 skills, as OpenFlowsheet 0.6 and 0.8 land | build lane |
| A6 | ML tools trained on the corpus; heuristic refinement | architect, then build lane |
| A7 | Safety, sustainability, uncertainty-aware ranking; a full design report | design and build lanes |

## 8. Frank's answers (2026-11-02)

Frank, verbatim: "It should be part of OpenFlowsheet. It should in the end become co-creation. When an agent finds that
OpenFlowsheet misses functionality it extends it. Approval is configurable. It is for all 3: students, practitioners, or
autonomous agents comparing routes? The last route is specifically relevant."

- **Where it lives:** inside OpenFlowsheet, as a layer of its own (for example `src/openflowsheet/designer/`, with its
  agents and skills under the repository's plugin directory). It still uses only the public contract internally, so the
  boundary stays testable.
- **Co-creation (end state).** When the layer finds missing functionality, an agent extends OpenFlowsheet. See §8.1.
- **Approval:** configurable per project and per gate (each level, final selection, extensions), from fully supervised
  to autonomous.
- **Users:** students, practitioners and autonomous agents. **The priority is autonomous route comparison**, so A3's
  first benchmark is choosing between Seider's vinyl chloride routes. The explanation depth for students and
  practitioners is a presentation setting over the same dossier.

### 8.1 The co-creation loop (sketch)

1. **Gap detection.** A design step needs a capability OpenFlowsheet refuses, such as a unit, a property method, a
   correlation or a cost model. The typed refusal (MSG) names the missing capability.
2. **Gap record.** The layer writes a typed feature request into the dossier and the repository's feedback log, with the
   design context that needs it.
3. **Extension.** An extension agent builds it through the F1 registry (X01: one registration point per provider and
   unit), following the repository's two-lane rules:
   - scientific content (equations, data, phase logic) gets a design-lane pass;
   - the build lane implements with tests;
   - gates and CI run as for any package.
4. **Evidence class.** Until a `reviewer` pass and the configured approval accept it, the extension is
   **`contributed, unreviewed`**. Every design result that uses it carries that flag. An agent never certifies its own
   extension (CLAUDE.md: never set `reviewed` on your own work).
5. **Merge.** On approval it becomes an ordinary registered extension, with its own manifest. The design that needed it
   is re-run on the merged version.

Approval settings may skip human sign-off; they never skip tests, gates, the flag or the independent review. The
scientific-conduct rules are not configurable.

## 9. Textbooks (requested sources)

Frank asked which textbooks the layer should draw on. In priority order:

| # | Book | Why |
| --- | --- | --- |
| 1 | Seider, Seader, Lewin, Widagdo, *Product and Process Design Principles* (3rd/4th ed.) | Already in Zotero. Synthesis steps, heuristics, route comparison, the vinyl chloride case, costing |
| 2 | Douglas, *Conceptual Design of Chemical Processes* (1988) | The hierarchical decision procedure, the methodology backbone; economic potential by level; HDA case |
| 3 | Smith, *Chemical Process Design and Integration* (2nd ed., 2016) | The onion model; reactor and separation choice; distillation sequencing; heat integration |
| 4 | Couper, Penney, Fair, Walas, *Chemical Process Equipment: Selection and Design* (3rd ed.) | The standard rules-of-thumb collection for equipment selection |
| 5 | Turton et al., *Analysis, Synthesis and Design of Chemical Processes* (5th ed.) | Worked plant cases, costing, troubleshooting; benchmark cases |
| 6 | Biegler, Grossmann, Westerberg, *Systematic Methods of Chemical Process Design* (1997) | Optimisation-based synthesis, the counterpart to heuristics; superstructures |
| 7 | Doherty and Malone, *Conceptual Design of Distillation Systems* (2001) | Azeotropic and nonideal separations, residue curve maps, feasibility |
| 8 | Towler and Sinnott, *Chemical Engineering Design* (2nd or 3rd ed.) | Equipment design, costing, safety and layout |
| 9 | Kemp, *Pinch Analysis and Process Integration* (2nd ed., 2007) | Heat-integration practice |
| 10 | CCPS, *Guidelines for Inherently Safer Chemical Processes* (3rd ed., 2020), or Kletz and Amyotte, *Process Plants: A Handbook for Inherently Safer Design* | Safety questions at the conceptual stage |
| 11 | Levenspiel, *Chemical Reaction Engineering* (3rd ed.) | Reactor-type selection |

Numbers 2–4 matter most after Seider: Douglas for the method, Smith for its systematic alternatives, and Couper and
Walas for the rules of thumb. Recent review papers on AI for process design come from the A0 survey, not from textbooks.

**In Zotero (2026-11-02):** collection *projects / OpenFlowsheet design layer* (`J27U2G9V`). The keys are
`seider2009product`, `seider2017product`, `douglas1988conceptual`, `smith2016chemical`, `couper2012chemical`,
`turton2018analysis`, `biegler1997systematic`, `doherty2001conceptual`, `towler2022chemical` (3rd ed.),
`kemp2007pinch`, `center2020guidelines` (3rd ed., 2020), `kletz2010process` and `levenspiel1999chemical`.

PDF status (2026-11-04):
- **Present:** Seider (both editions), Levenspiel, Smith, Couper (an OCR'd scan), Turton, Towler, Kemp, CCPS (3rd ed.),
  and Douglas (split to one book page per PDF page and re-OCR'd: 97.5 % dictionary words; PDF page labels match the
  printed page numbers).
- **Still needed:** Biegler/Grossmann/Westerberg, Doherty and Malone, and Kletz and Amyotte.

The missing ones are tagged `ofs:pdf-needed`. The PDFs stay in Zotero storage only; this repository gets citations,
plus short page-cited excerpts on request.

## 10. Questions still open (nothing is blocked)

- Licence and name of the layer: the default is the core's Apache-2.0, under the OpenFlowsheet name.

## 11. Risks

- **Conflicting heuristics.** Textbooks disagree. The record model must hold conflicts and show them, not resolve them
  silently.
- **LLM overconfidence in design judgement.** Mitigated by tool-backed numbers, the critic agent, and checklists with
  measured coverage.
- **Benchmark leakage.** Famous cases (HDA, vinyl chloride) are in model training data, so a "reproduction" may be
  recall. Mitigations: hold out less-known cases, perturb problem statements, and judge the reasoning trail as well as
  the answer.
- **Small corpus for ML.** Start deterministic; ML only where the corpus supports it.
- **Copyright** of textbook heuristics and paper data: the rules in §2.7.
