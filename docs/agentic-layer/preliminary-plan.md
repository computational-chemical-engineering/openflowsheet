# Agentic design layer: preliminary plan

Status: **brainstorm / preliminary plan**, 2026-11-02 (orchestrator, from Frank's request). Not a design and not a
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

## 8. Questions for Frank (later; nothing is blocked)

1. **Where it lives:** its own repository (for example `OpenFlowsheet-Designer`), or inside OpenFlowsheet? The default
   is its own repository: it is a user of the tool, as the tutorial is. This preliminary plan sits in OpenFlowsheet's docs
   until then.
2. **Users:** students learning design, practitioners, or autonomous agents comparing routes? It changes how much the
   layer explains and when it asks the human.
3. **Sources beyond Seider:** Douglas, Smith, Turton, Towler and Sinnott? Which do you have access to?
4. **Human gates:** at every level, only at final selection, or configurable?
5. **Name and licence:** the default is Apache-2.0, matching the core.

## 9. Risks

- **Conflicting heuristics.** Textbooks disagree. The record model must hold conflicts and show them, not resolve them
  silently.
- **LLM overconfidence in design judgement.** Mitigated by tool-backed numbers, the critic agent, and checklists with
  measured coverage.
- **Benchmark leakage.** Famous cases (HDA, vinyl chloride) are in model training data, so a "reproduction" may be
  recall. Mitigations: hold out less-known cases, perturb problem statements, and judge the reasoning trail as well as
  the answer.
- **Small corpus for ML.** Start deterministic; ML only where the corpus supports it.
- **Copyright** of textbook heuristics and paper data: the rules in §2.7.
