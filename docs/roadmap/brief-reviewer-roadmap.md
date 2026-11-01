# Reviewer brief — roadmap stage 4: independent review of the target architecture and the foundation rulings

Status: brief, 2026-11-02. The deliverable is `docs/roadmap/review-roadmap.md`.

## What is under review

Two committed design documents. Nothing is implemented, so there are no test numbers to check; the review is of the
design itself.

- `docs/roadmap/target-architecture.md` (architect, 901 lines). It contains foundations F0–F8, the dependency graph,
  provisional release lines 0.4–1.0 and nine specifier questions. It was written against
  `docs/roadmap/brief-architect-1-target-architecture.md`, and its source of facts is `docs/roadmap/00-core-inventory.md`.
- `docs/roadmap/foundation-rulings.md` (specifier, 690 lines). It rules on the nine questions; six depart from the note's
  defaults. §12 lists edits to the note that have **not** yet been applied. It was written against
  `docs/roadmap/brief-specifier-foundation-questions.md`.

## The intent the review measures against

Frank (R-927, 2026-11-01): "The aim is a 'real simulator' so all these features need to be on board at some stage,
including electrolytes, solids, polymers, petroleum assays, rate-based columns, P&ID drawing and superstructure (MINLP)
synthesis. The issue is planning. I am not in a hurry to have some features available as soon as possible. What is
important is to have a very well designed implementation, that runs well, is very flexible, can very well be used by
agents etc. So what is important is to have a very good plan."

The scope is in `docs/adr/0056-capability-extension-plan.md`: its base table plus Amendments 1 and 2. Also binding are
R-923–R-927 (end of `docs/decision-register.md`), the blueprint decision table D01–D20 (`docs/blueprint-v3.1.md`, lines
27–46) and the scientific-conduct rules in `CLAUDE.md`.

## What to check

1. **Coverage.** Does every package in ADR 0056 and its amendments map to foundations that actually support it? Packages
   to check: TX, X01–X26, MSG, ST, FB-04, the optimiser and PrISMa. Name any capability that would still have to break a
   foundation later; that is the failure the plan exists to prevent.
2. **Dependency graph and sequence.** Is the graph acyclic and consistent with what each package states it needs? Is any
   release-line placement chosen for speed rather than dependency order?
3. **Migration.** Does each foundation name a proof that keeps released numbers and replay (F0's bit-identity measures)?
   Are the "frozen legacy families plus a parallel `std.*` family, proved by equivalence" and the `nTP-v1` byte-identity
   claims sound?
4. **Scientific soundness of the rulings,** especially the six departures:
   - Q1: mass-specific `(n, ĥ, P)`, T derived, `ĥ` a label at zero flow;
   - Q3: conserved groups checked by exact linear algebra;
   - Q4: phase id triple, key-vector liquid ordering, prefix and count lattice;
   - Q5: TPD trial set, τ_tm = 1e-8, a witness, exact versus local claim levels;
   - Q6: the partition and no-redundancy rule, attributes +0.0 at zero flow;
   - Q9: the volatile set and the two provenance axes.

   Look for hidden assumptions, missing limiting cases, assertions that are not falsifiable, and conflicts with D09, D10
   or D14.
5. **Consistency between the documents.** Where a ruling and the note disagree, which part of the note's design does the
   ruling invalidate beyond its own §12 list?
6. **The architect's three least-certain choices.** Judge each and recommend:
   - (a) the `ĥ` state coordinate, which the specifier turned into a mass-specific one;
   - (b) carrying two unit code paths for a long time;
   - (c) owning the DAE step loop (BDF), and logic-based outer approximation over certified fixed-structure revisions for
     MINLP, instead of reusing IDAS or a monolithic MINLP solver.

   Also: freezing the v2 revision grammar before F3–F6 are built.
7. **Agent use and cross-platform.**
   - Does the application contract give agents uniform discovery, typed refusals and readable messages for every new
     capability?
   - Does any foundation assume POSIX?
8. **Unnecessary complexity.** Name parts that could be simpler without losing a capability in scope.

## Do not spend time on

- Wording or formatting.
- Release-procedure mechanics.
- Choices of specific correlations.
- Relitigating the scope (R-927) or MSG's placement ahead of X04, which Frank decided.

## Deliverable

Write `docs/roadmap/review-roadmap.md`, at most about 400 lines, with these sections:
1. Verdict in one paragraph: sound to finalise / finalise after the listed fixes / needs rework, with the reason.
2. Findings ranked by severity. Each gives where it is (document and section), what is wrong, why it matters, and the fix.
3. Judgements on item 6.
4. Questions for Frank. Include only real value judgements, each with a recommended default.
5. What this review did not establish.

Write only that file and do not commit; the orchestrator commits. Write no production code. Do not start subagents. Never
send personal identifiers (names, e-mail addresses) to external services. Never read, stat or touch anything under
`~/.config/procsim/`. Do not read `/home/frankp/s10-papers/`, `~/.cache/seider3/` or `~/.cache/seider4/`. Read source code
and ADRs narrowly (grep -n, sed -n ranges), only to check a specific claim.
