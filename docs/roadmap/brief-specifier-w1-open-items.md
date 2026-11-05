# Specifier brief: design wave W1, the five open items (Amendment 2 to the foundation rulings)

Status: brief, 2026-11-05. Roadmap §"Design waves" W1, first step (ADR 0057, R-928). You amend
`docs/roadmap/foundation-rulings.md` in place and add a dated "Amendment 2 (2026-11-05)" section at its end, in the form
of Amendment 1 (§13). The architect passes P1 (F1, F3), P2 (F2, F4, F5) and P3 (F6, F7, F8) come after you and adopt
your clauses verbatim into ADR-F2, ADR-F4, ADR-F5 and ADR-F7.

## The question

Rule on the five items the target-architecture note leaves open as entry criteria of foundation ADRs, so that each ADR
can be Accepted and the v2 core grammar can freeze at the end of W1. For each: adopt the proposed default or rule
differently with the reason, as numbered clauses with falsifiable assertions.

## Why it needs the specifier

Each item fixes scientific semantics that the v2 core schema freezes: stream identity at method boundaries, the stored
`ĥ` of every v2 state, phase labels on every EOS path, and the meaning of dynamic states. A wrong call is a frozen-schema
change later. The note states each default and the cost of leaving it open (§6): A1-a refuses an admissible stream at a
boundary, A1-b moves stored `ĥ` when a method is added, S5 churns labels on EOS paths.

## The items (quoted from `docs/roadmap/target-architecture.md` §3; your Amendment 1 raised A1-a and A1-b, §13)

1. **A1-a, gates ADR-F2** (note line ~764). Q3.R5 and Q3.A5 refuse a downstream method whose fast-reaction set lacks the
   producer's salt dissolution (R′ ⊊ R), while Q8's argument admits it. *Proposed default:* the boundary condition is the
   invariant one, b′ = C b with integer C, and m′'s own declaration is valid under Q3.R1. R′ ⊇ R is then sufficient, not
   necessary. A dropped solid candidate is reported as `solid_candidate_dropped(<method>, <phase>)`.
2. **A1-b, gates ADR-F4** (note line ~804). Q2.R2 makes the anchor depend on the flowsheet's method set. Adding an
   ideal-gas-capable method re-anchors an `l` component, so every stored `ĥ` moves; it also sends a record that has only
   Δf h°(l) to the component datum. *Proposed default:* the anchor is a function of the record only (its phase data under
   Q2.R2's order, without the method-set clause). A method that cannot evaluate the component in that anchor is bridged
   (Q2.R8) or refused, so adding a method never re-anchors.
3. **S5, gates ADR-F5** (note line ~823). Under one fluid model (an EOS) every fluid phase comes from the same model. The
   VAPOR/LIQUID split can put two phases in one family or flip a liquid between families near a critical endpoint:
   non-adjacent restarts and label churn in R0. *Proposed default:* methods declaring a single fluid model use one
   interchangeable `FLUID` family, ordered by Q4.R3, with vapour-like or liquid-like as a reported attribute; two-candidate
   legacy points keep Q4.R7's rendering. A phase confined to one component by its own model (X21's free water) takes a
   qualifier on its fluid family, generalising Q8.R7's confinement. This amends Q4.R1 and Q4.R6. Related: your open item
   O-3 (§11) and the note's risk R12 ("if refused, Q4.R6 and O-3 stand and F5 measures the churn"). Phase families are a
   registered vocabulary (note §2.2.2, line ~299), so a new family needs no grammar change — but the rendering does.
4. **Holdup dormancy, gates ADR-F7** (note line ~866). Q1.R4 and Q1.R6 cover streams, not a vessel that drains to exactly
   zero. *Proposed default:* a holdup is dormant iff every held amount is exactly `+0.0`; then U is exactly `+0.0` and T is
   a label; the holdup is re-seeded at the event opening that starts filling, from the inflow's state.
5. **Non-material holdups, gates ADR-F7** (note line ~869). Q1.R7 lists material holdups. *Proposed default:* a unit may
   own further conserved holdups (wall energy, rotor angular momentum) in `holdup_balance` rows; M stays 0/1. Note R-930
   (`state_rate` control rows) is already decided: a PI integral is a `state_rate` state, not a holdup.

## Read (narrowly)

- `docs/roadmap/foundation-rulings.md`: Q1.R4, R6, R7 (lines 41–61) and Q1.A9–A10; Q2.R2, R4, R5, R8 (lines 154–181) and
  the Q2 assertions; Q3.R1, R5 (lines 244–260) and Q3.A5 (line 307); Q4.R1, R3, R6, R7 (lines 316–345) and Q4.A1–A7; Q8
  argument and Q8.R2, R7 (lines 605–662); §11 O-3; §13.
- `docs/roadmap/target-architecture.md`: §2.1.13 and §2.1.6 where the triple is rendered (lines ~175–200); §2.2.2–2.2.3;
  §2.3.6 and §2.3.8 (lines ~380–410); §2.5.2; §3 F2, F4, F5, F7 (lines 755–878); §6 (lines 1018–1047); §9.4 (X21, line
  ~1184) and §9.6 (TX), which the S5 qualifier and the holdup items serve.

## Constraints and settled points (not open)

- Released numbers stay; `nTP-v1` stays byte-identical; D09, D10 and D14 hold; R-924 (admit with declared limits) applies.
- Settled (`docs/roadmap/decisions.md`): mass-specific `ĥ`; water is the default first liquid key; the v2 core grammar is
  frozen at the end of W1, the F4–F6 slots stay `preview` until the end of 0.6; FB-04 part 1 dropped (the turbine is
  solved by F5 and `std.turbine`); R-930 (`state_rate` control rows).
- Your Amendment 1 clauses stand; amend them only where an item above forces it, and say so.
- Keep the document at about 900 lines in total.

## Verification

Each new or changed clause carries at least one numbered assertion a test can falsify (synthetic or closed-form numbers
are fine; say which). Name the foundation exit each assertion joins (F2, F4, F5 or F7 exit in the note §3).

## Deliverable

- The amended `docs/roadmap/foundation-rulings.md`; existing clause numbers kept, new clauses appended.
- "Amendment 2 (2026-11-05)": one table row per item — ruling (default adopted?), clauses, assertions, and the exact edits
  the architect must make to `target-architecture.md` and to the ADR it gates; then "Not established by Amendment 2".
- Any further finding you notice that touches a ruling: list it, do not fix it.
- Report ≤ 30 lines.

Do not commit; the orchestrator commits. Write no production code. Do not start subagents. Do not edit
`target-architecture.md`. Never read, stat or touch anything under `~/.config/procsim/`. Do not read
`/home/frankp/s10-papers/`, `~/.cache/seider3/` or `~/.cache/seider4/`. Do not fetch from the web; cite literature by
author, year and section only.

## Out of scope

- The `heat_direction` verdict (ADR-F6 takes the default; X14's specification confirms it).
- Software design of F1–F8 (the architect passes), release lines, MSG and anything outside the five items.
