# Specifier brief: Amendment 5 — the stream table's semantics (SQ-ST-1…6) and SQ-F6-5

Status: brief, 2026-11-06. One short specifier round. Seven questions, each with the designer's default; the build
proceeds on the defaults until ruled. ADR 0068 and ADR 0065 are Proposed; design against them as written.

## Deliverable

"Amendment 5 (2026-11-06)" at the end of `docs/roadmap/foundation-rulings.md`, in the form of §16 (Amendment 4): per item
a numbered clause (new or amended rule), falsifiable assertions with the exit or gate that gains them, the exact edit
each ADR/design note needs, and "Not established". Clauses may also be inserted in place as Amendment 4 did.

## Items

**A. The stream table (ST, 0.4; legacy providers, v1 states).** Read `docs/design/ST-stream-table.md` §4.2 phase rule
(123–150), §4.3 property calls and formulas (151–177), §4.5 energy summary (187–207), §11 gates (351–402), §13 questions
(426–end); `docs/adr/0068-stream-table.md` (specifier questions at 208–213). The rulings that bear on it:
`docs/roadmap/foundation-rulings.md` Q1.R4 (zero flow; Q1 at 31–184), Q2 (reference conventions; 185–360), Q4 (phase
labels; 451–558). The tutorial user's request (FB-06, FB-02, `docs/USER_FEEDBACK.md` lines 15, 27) was "vapour
fraction / steam quality", h, s, density per stream.
1. **SQ-ST-1** Vapour fraction on both bases (`vapor_fraction_molar`, `vapor_fraction_mass`) over the VAPOR family; no
   member named "quality"; 0 or 1 outside the dome, not undefined. Say also how the v2 FLUID family (Q4.R6, Q4.R9:
   `character`) will extend it — additively.
2. **SQ-ST-2** A dormant stream's `T` is `null` with `zero_flow` (Q1.R4), not the stored label.
3. **SQ-ST-3** Undeclared, unsplit streams take a raw TP flash, without the verifier's ε_adm or τ_dew snap — and what
   the table reports when that flash disagrees with the verifier's phase decision near a boundary (the architect's
   riskiest point).
4. **SQ-ST-4** A saturated (R1) phase is evaluated at `(T_sat(P), P)`, the verifier's choice, not at the stored T.
5. **SQ-ST-5** Density only from a provider's molar volume `v`, no ideal-gas fallback; the per-component property form is
   accepted for `h` only (ideal-solution additivity), never for `s` or `v`.
6. **SQ-ST-6** A phase is listed iff its amount is `!= 0.0`.

**B. SQ-F6-5** (W1 P3 review M4): routing of two or more active FLUID phases at a unit with a `vapor` port.
`docs/adr/0065-F6-unit-model-framework.md` D9 (~230–245) and the question (542–544); review finding M4
(`docs/reviews/W1-P3-review.md` 85–100); Q4.R9 (Amendment 4, §16). Default: phases whose `character` is `vapour_like`
go to `vapor`, the rest over `light_to_heavy` by density; a unit with `vapor: null` routes them all by density. Note that
O-11 (Frank's open preference: the identification rule behind `character`) then has a numerical consequence here too.

## Constraints

Released numbers stay; no F0 measure (M1–M9) may move; R-924 (admit with declared limits; absent values carry a typed
reason and a catalogued code); every tolerance you fix names the measurement that would amend it (rule 6), as §11's
O-rows. Adopt earlier rulings; amend them only explicitly.

## Rules

Report ≤ 20 lines: per item the ruling in one line and whether it differs from the default; the edits the ADRs/design
note need (count); "Not established". Do not commit; no git state changes (other agents work concurrently); do not edit
the ADRs, the design note or `target-architecture.md`; no production code; no subagents; nothing under
`.claude/worktrees/`; never read, stat or touch `~/.config/procsim/`; do not read `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`; no web fetches.
