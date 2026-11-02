# Specifier brief: amendment 1 to the foundation rulings (roadmap stage 4b)

Status: brief, 2026-11-02. You amend `docs/roadmap/foundation-rulings.md` in place, adding a dated "Amendment 1" changelog
section at its end. The final architect pass comes after you and consumes the amended rulings.

## The question

Fix the scientific findings that the independent review (`docs/roadmap/review-roadmap.md`) raised against the rulings.
Each fix must leave the ruling freezable, with falsifiable assertions.

## Findings assigned to you

They are listed by id; read each one in `review-roadmap.md` §2, where each states the problem and a proposed fix. You may
adopt the reviewer's fix or rule differently, with the reason.

- **S3:** reactivation of a stream whose `ĥ` is a zero-flow label (formation enthalpy offsets). Consumers would evaluate
  the label before the fixing Newton step and leave the property domain. Rule on the label value, the reactivation rule,
  or both.
- **S4:** a value rule for the outputs of inactive phases, and the continuity of the phase-appearance indicator.
- **S9:** the Q3 NaCl worked example is wrong: the intersection is the dissolution reaction, not {0}. Group molar masses
  are not defined. Correct the example and define them.
- **S10:** Q6.R5's strict moment inequalities reject monodisperse polymer feeds through floating-point rounding. Give a
  tolerant, still falsifiable form.
- **N5:** PrISMa's adsorbed phase fits neither Q4's families nor Q8's criterion. Give it a home.
- **N6:** Q2.R2 refuses a liquid-only method for a component anchored as an ideal gas. Reconcile this with R-924 (admit
  with declared limits), for example through a declared anchor conversion.
- **N7:** Q4.R3's thresholded lexicographic ordering is not transitive for three or more liquids. Make the ordering a
  total order.
- **N8:** Q5.R4's `near_critical` test (`λ_min(B) < τ_spin`) also fires on the spinodal far from any critical point.
  Separate the two cases.
- **N10:** conserved holdups. Confirm or correct the review's reading that they are the carried amounts (Q3 groups and Q6
  partition classes); a dynamics foundation (F7) builds on it.

Any other finding you notice while doing this that touches a ruling: list it, do not fix it.

## Read

- `docs/roadmap/review-roadmap.md`: §2, the items above only, plus §3(a).
- `docs/roadmap/foundation-rulings.md`: the rulings affected.
- `docs/roadmap/target-architecture.md`, narrowly, where a ruling refers to it.

## Constraints

Unchanged from `docs/roadmap/brief-specifier-foundation-questions.md`:
- released numbers stay;
- `nTP-v1` stays byte-identical;
- D09, D10 and D14 hold;
- R-924 applies.

Settled since then (`docs/roadmap/decisions.md`):
- mass-specific `ĥ`;
- water is the default first liquid key;
- the v2 core is frozen at the end of design wave W1.

## Deliverable

- The amended `docs/roadmap/foundation-rulings.md`, keeping its structure. Do not exceed about 800 lines in total.
- A closing section, "Amendment 1 (2026-11-02)", listing each finding with:
  - what changed;
  - which assertions were added or changed;
  - any edit the architect must make to `target-architecture.md`.

Do not commit; the orchestrator commits. Write no production code. Do not start subagents. Never send personal identifiers
(names, e-mail addresses) to external services. Never read, stat or touch anything under `~/.config/procsim/`. Do not read
`/home/frankp/s10-papers/`, `~/.cache/seider3/` or `~/.cache/seider4/`. Do not fetch from the web; cite literature by
author, year and section only.

## Out of scope

- The architect's findings: M1, M2, S1, S2, S5–S8, S11, N1–N4, N9, N11, N12 and U1–U4.
- Release lines.
