# Reviewer brief: W1 P2 — ADR 0062 (F2), 0063 (F4), 0064 (F5)

Status: brief, 2026-11-05. The single design-lane review of the P2 ADR set (roadmap W1), with any open ruling folded in
(CLAUDE.md "Agent budget"). F2's core freezes at the end of W1; F4/F5 slots stay preview until the end of 0.6 (R-929).

## What to review

- `docs/adr/0062-F2-material-model.md` (359 lines), `docs/adr/0063-F4-property-methods.md` (177),
  `docs/adr/0064-F5-phase-equilibrium.md` (138), all Proposed, written against `docs/roadmap/brief-architect-W1-P2.md`
  (read it: question, inputs with line ranges, items handed to P2, constraints).
- They must fit P1: `docs/adr/0060-F1-extension-registry.md`, `docs/adr/0061-F3-component-data.md` (both reviewed,
  `docs/reviews/W1-P1-review.md`, fixes applied) and adopt the rulings verbatim: `docs/roadmap/foundation-rulings.md`
  Q1–Q8 and Amendments 2–3 (§14 table 1012–1040, §15 from 1041).

## The architect's summary (orientation, not evidence)

F2: `EvaluationState` per substream (n, T, P, sorted attributes), `StreamState` conversion by reference copy (bitwise);
two-level connection definitions (registered templates nTP-v1, mat-v1, heat-v1, work-v1, signal-v1; instances in the
revision, instance SHA excludes the local id); qualifier spelling `cid | cid,form | model=mid`, phase sets joined by `+`;
`solution-state-v2` = v1 + layout + signatures; in 0.5 a v1-expressible v2 revision is lowered to a v1 document and runs
the untouched v1 path, proved by a corpus round trip with equal `r0_sha256`. F4: `ig` anchor via φ° (IAPWS-95,
CoolProp), ideal-gas vapour (Wilson), PR-C1's own ideal-gas function or PR-C1 refused on the elemental convention; shifts
added to Ḣ in fixed component order; `implementation_sha256` = ADR 0060's formula; `data_sha256` narrowed per method
(edits ADR 0061 D10); c_ref, ΔT_ref as optional `SolvePolicy.scales`; one CasADi callback per method, `cubic.pr-v1`
vectorised kernel. F5: stage-wise phase addition driven by stability, Newton on ln n at fixed phase set; `F5-trials-v1`,
`F5-phase-contract-v3`; FB-04 by a flash at each opening; A2-c both representations allowed, lower G wins, a method may
declare `confined_exclusive` (caps stability claims at `local`). Departures: `PropertyCapabilities`, `FlashResult`,
`FlashRequest` not widened (`adapters/experiments/request.py:43` hashes `asdict(PropertyCapabilities)`); grids inside
substreams; definition SHA in the fingerprint only for v2-compiled runs. ADR 0019 Amendment 9 (existing operations accept
v2 documents). Riskiest: F5 decision equivalence (E-F5-2 if T05b is not exactly the count lattice); PR-C1's ideal-gas
function may not be separable; CasADi callback overhead vs the batching exit (E-F4-7).

## Look hardest at

- **Completeness for the build lane:** ADRs 0063 and 0064 are short. Can every work order be built without a further
  design decision? Name each missing decision.
- **The freeze:** is ADR-F2's core (D1–D12) complete and unambiguous enough to freeze at W1's end — id grammar
  injectivity (S6, the [gen] test), qualifier spelling vs Q4.R1/R8, connection-definition identity, `solution-state-v2`?
- **Identity:** the v1-lowering route and its `r0_sha256` proof; `data_sha256` narrowing vs cache keys and the data
  lock; anything that moves an F0 measure (M1–M9).
- **Rulings adopted verbatim:** every §14/§15 row's ADR obligations present (Q3.R5/A5/A6, Q2.R2/R4/R8/R9/A9–A11, Q4.R1–R8,
  Q5.R3/R8/A10, A3-a's assertion).
- **Numerics:** F5's flash/stability design (convergence, trivial-solution handling, τ_tm band) and F4's scale rule (S7).

## Rulings wanted

1. ADR 0063 D2's narrowing of ADR 0061 D10 (`data_sha256` per method): accept or reject; give the exact ADR 0061 edit.
2. Any departure from the note or rulings you find: accept (with reason) or require a fix.

## Deliverable

`docs/reviews/W1-P2-review.md`: findings ranked must-fix / should-fix / note, each with ADR section and failure scenario;
rulings; verdict per ADR (accept after listed fixes / revise / reject) with exact edits. Do not edit ADRs. Report ≤ 30
lines. Do not commit, no code, no subagents, nothing under `.claude/worktrees/` or `~/.config/procsim/`.
