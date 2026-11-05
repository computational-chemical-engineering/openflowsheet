# Specifier brief: the anchor of a record with no formation data and nothing phase-tagged (Amendment 3)

Status: brief, 2026-11-05. Referred by the W1 P1 review (`docs/reviews/W1-P1-review.md` ruling 2, lines 195–206); gates
ADR-F4 (deadline: before ADR-F4 is Accepted; P2 designs F4 next). Amend `docs/roadmap/foundation-rulings.md` in place and
add "Amendment 3 (2026-11-05)" at its end, in the form of §13/§14.

## The question

Q2.R2 as amended in §14 derives the anchor phase from the record. ADR 0061 D6 (lines 170–180) implements it in four
steps; step 4 is a gap: a record with no formation data and no phase-tagged entry (legacy `syn001`, `s05`, `s07` — the
synthetic set, the IAPWS-95 water record, the CoolProp records) gets `null` plus `anchor_undetermined(<component>)`.
Rule what the anchor is in that case — `null` (the build default) or `ig` for a `mol`-basis record with a notice
`anchor_defaulted(<component>)` (failing as `anchor_unavailable` where a method cannot evaluate the ideal-gas state), or
something else — as a numbered clause with falsifiable assertions.

## The trade-off (from the review)

- For null: records exactly what the record says; fails loudly; revertible by one regeneration of the legacy index
  before any released v2 document pins these SHAs.
- Against null: Q2.R4's component datum never reaches s05 or s07, so no CoolProp or IAPWS-95 water record is usable on
  `ELEMENTAL-ref-v1`; a wheel ships only the m01 and s10 component files.
- **The deciding fact:** whether a delegating composition over the legacy IAPWS-95 and CoolProp providers can evaluate the
  ideal-gas state at (T° = 298.15 K, P° = 1e5 Pa). Establish it from the code (`src/openflowsheet/thermo/`, the IAPWS-95
  and CoolProp providers; read narrowly) and state it with `file:line`. Do not run solves; a closed-form check or a
  single provider call in a scratch script is fine.

## Read narrowly

`foundation-rulings.md` Q2 (lines 147–240) and §14; ADR 0061 D6 (lines 165–200), D12 (the provenance table) and risk 2;
`docs/reviews/W1-P1-review.md` lines 195–206; `docs/roadmap/target-architecture.md` §2.3.6 (lines ~380–395).

## Constraints

Released numbers stay; `nTP-v1` byte-identical; R-924 (admit with declared limits); the anchor is a function of the
record only (Amendment 2, A1-b) — no method may enter it. Any value enters record SHAs (F3 identity), so say exactly what
the legacy importer writes for each of the three record files.

## Deliverable

The amended rulings file with "Amendment 3": the clause, assertions (and which exit, F3 or F4, each joins), the exact
edit ADR 0061 D6 step 4 and its legacy index need, and "Not established". Report ≤ 20 lines. Do not commit; do not edit
the ADRs or `target-architecture.md`; no production code; no subagents; never touch `~/.config/procsim/` or
`.claude/worktrees/`; no web fetches.
