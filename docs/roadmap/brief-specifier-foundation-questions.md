# Specifier brief — the nine foundation questions (roadmap stage 3)

Status: brief, 2026-11-02. The deliverable is `docs/roadmap/foundation-rulings.md`.

## The question

Rule on the nine questions in `docs/roadmap/target-architecture.md` §6, lines 764–842. Each question fixes a scientific
semantic that a foundation package (F2–F5) builds on. For each one, return a ruling the architect can freeze into the v2
revision grammar and the thermo face.

## Why this needs the specifier

These are scientific semantics, which belong to the design lane by the rules in CLAUDE.md:
- the state coordinate and its zero-flow rule;
- the enthalpy reference;
- the species basis for electrolytes;
- phase identity;
- the stability test, and what a certificate may claim;
- attribute and amount bases;
- the boundary between equilibrium solids and solid substreams;
- the record identity and evidence classes.

A wrong ruling here would be frozen into the v2 revision grammar, the replay identity and every unit built after it. Frank
(R-927): "What is important is to have a very well designed implementation … So what is important is to have a very good
plan." No feature is wanted early at the cost of the design.

## Read first, narrowly

- `docs/roadmap/target-architecture.md`: §6 in full (the questions and their defaults), §2.1 (the material model), §2.2
  (the phase framework), §2.3 (the property and data layer), §3's F2–F5 entries.
- `docs/roadmap/00-core-inventory.md` §1 (stream state, the four phase vocabularies, FlashResult), §2 (components) and §3
  (providers).
- These ADRs, at their decision sections only:
  - `docs/adr/0001-state-units-zero-flow.md` (D2.1 `nTP-v1`, D3 zero flow);
  - `docs/adr/0005-phase-attempt-contract.md` (the phase lattice);
  - `docs/adr/0011-unit-models-ph-closure-and-reaction-datum.md` (the PH closure, the reaction datum);
  - `docs/adr/0012-saturation-band-ph-contract-zero-flow.md`;
  - `docs/adr/0051-s11-thermal-units-on-the-new-bases.md` D1 (declared regimes);
  - `docs/adr/0007-reproducibility-certificate-policy.md` (what a certificate claims).
- `docs/decision-register.md`: R-706 (data rights), R-839 (one declared phase per stream), and R-923–R-927 at the end.

## Constraints

- **Released numbers stay.** Every released case keeps its numbers. `nTP-v1` stays available byte for byte; a ruling
  must not force a released case onto a new coordinate.
- **Certificates (D14).** A certificate verifies against a pinned model and policy. Stability claims must be honest
  about local search (blueprint D09: critical and unsupported regions return typed limitations).
- **No unnecessary restrictions (R-924).** Admit the capability with declared limits rather than exclude it.
- **Exact caches.** Residual and Jacobian describe the same function at the same state; exact caches key on exact
  canonical inputs.
- **Data rights.** R-706 governs shipped data; user-fetched and user-licensed data stay in the project (R-926).

## Already decided, not open

- The full scope, including electrolytes, solids, polymers, petroleum assays, rate-based columns, transient work, MINLP
  and CAPE-OPEN: R-927 and ADR 0056 with its amendments.
- Foundations F0–F8 as the structure of the plan. If a ruling breaks a foundation's premise, say so explicitly; do not
  silently re-plan.

## Deliverable

Write `docs/roadmap/foundation-rulings.md`, at most about 600 lines. For each question Q1–Q9:
1. the ruling, stated so it can be frozen;
2. the rejected alternatives, each with its reason;
3. the derivation or argument, with limiting cases such as zero flow, a pure fluid at saturation, the critical region, a
   binary at VLLE and a phase appearing or disappearing;
4. numbered falsifiable assertions the foundation's tests must meet, with tolerances where they are numerical;
5. its effect on the note: what in `target-architecture.md` changes, by section.

End with a short section listing the edits to the note, where any ruling departs from the note's default.

Write only that file and do not commit; the orchestrator commits. Write no production code. Do not start subagents. Never
send personal identifiers (names, e-mail addresses) to external services. Never read, stat or touch anything under
`~/.config/procsim/`. Do not read `/home/frankp/s10-papers/`, `~/.cache/seider3/` or `~/.cache/seider4/`. Cite
literature by author, year and equation or section only; do not fetch it. If a ruling needs a reference value that is not
in the repository, state the assumption and mark it for the `zotero` session.

## Out of scope

- Choosing correlations, parameter sets or specific electrolyte models.
- Per-package specifications.
- Release lines.
- Software structure, which is the architect's except where a semantic forces it.
