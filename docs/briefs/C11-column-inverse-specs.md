# C11 — column specifications by purity, recovery and stage temperature (design lane `specifier`, then build)

Branch `wp/C11` from `main` `00759c6` (S01, S02, C8 merged). Source: `docs/CLOUD_WORK.md` C11; Frank's answer
Q-S02-2 (`docs/FRANK_QUESTIONS.md:11`): "purity / recovery / stage-temperature specifications are the next column
package." Package id: an S-letter id (R-565 / D1 Q6) — propose **S06** with a DECISION line. Register numbering:
**R-601…R-610**. ADR number if needed: **0046**.

## The question
Specify inverse column specifications on the S02 MESH column: product mole-fraction (purity), component recovery, and
stage temperature, as end specifications replacing a ratio/rate/duty at the condenser or reboiler slot; their rows, DOF
accounting, admissible combinations and refusals (infeasible targets, e.g. purity above the separation the column can
reach; temperature outside the stage's bubble/dew band), how the S02 solve path (bubble-point easy endpoint
`s02-bubble-point-v1`, §18; continuation over replaced slots; ADR 0044's edge 3) carries a slot whose specification is
inverse (continuation from the endpoint's own value of the target quantity to its specified value is the natural
default), the multiplicity warning rule (C8's `multiple_steady_states_possible(duty_only)`; does any inverse spec need
one), and numbered assertions with independent expectations from an independent generator.

## Facts with anchors
- S02 spec `docs/derivations/S02-spec.md`: §2 rows (`ratio_row`, `fraction_row`, `bubble_row` in
  `src/openflowsheet/models/rows.py`), §3 DOF and admissible sets (:91-), "not offered" list (:115), refusals S1/S2
  (:172-173), §7/§18 solve path, §19 review amendment, non-claims (:341). Code `src/openflowsheet/models/syn001/column.py`
  (spec, validation, `column_warnings`), `column_solve.py` (`solve_column`, slots, continuation). Reference generator
  `docs/derivations/scripts/s02_reference.py` (mpmath; registered cases M1–M4, variants).
- Provider: SYN-001 only (ideal, 3 components, T 280–440 K, P 0.5–2 bar). Real chemistry needs a liquid method (S05
  IAPWS-95 is pure water only); out of scope here.

## Exit test (design step)
`docs/derivations/S06-spec.md` (rows, DOF, admissible sets, refusals, solve-path extension, assertions `S06.A01…` with
independent expectations from `docs/derivations/scripts/s06_reference.py` `--check`, work orders ~120k each for
`opus-engineer`, manifest check list, non-claims), register entries, ADR 0046 only if a frozen interface changes,
`DECISION:` lines in `docs/C11_DECISIONS.md`, Frank questions in `docs/FRANK_QUESTIONS.md`.

## Out of scope
Rate-based models; inside-out; new property methods; binding the column into flowsheets (MODEL_BUILDERS).

## Agent rules
Context cap ~120k; at the cap commit, write a ≤ 30-line handoff `docs/briefs/C11-handoff.md`, stop. Report ≤ 150 words.
