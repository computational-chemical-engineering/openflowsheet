# S19 design-lane ruling round 2 (batched, 2026-11-20)

You are the design lane for OpenFlowsheet's S19 code-health campaign. Rule on five open items. Do not spawn
sub-agents yourself. Worktree: `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/s19` (branch `wp/S19`,
read-only for you except the output file below). Standing rules: `docs/S19_RULES.md`. Do not read
`docs/S19_DECISIONS.md` whole: use the line ranges given.

Context: behaviour stays bitwise identical in S19 unless a design-lane ruling says otherwise (Frank, 2026-11-14,
ADR 0076). G-END (end criterion): repo debt <= 1900 (now ~2140 after two queued lanes), health >= 9.0, no file below
health 7.0, brain 0, arch 0/0. Each item has a default that stands if you find no reason to change it.

## Items

(v) **the G-END-critical one.** `src/openflowsheet/studies/nlp/verification.py` health 6.1 (debt 49.8, 840 NLOC) is
the only file in the repo below 7.0. `verify_candidate` (line 248, debt 33.7, 147 NLOC) carries the file. Earlier:
S19_DECISIONS.md lines 2536-2545 (engineer: twin early returns would drop string literals under rule 15; phases need
>= 9 locals) and 2556-2563 (ruling R-W3-G3-5 (b): leave it; revisit only with a design-lane behaviour change, after a
test pins `assessment_not_evaluable` and `phase_rows_not_evaluable` texts and the stop record). The other functions:
`_regimes` :742 5.0, `_kkt` :934 4.1, `_assessment` :470 3.0. Question: what is the cheapest admissible path to
health >= 7.0 for this file? Consider (A) a pure-structure path without merging the twins (state the phases and
whether a parameter object over them would be cohesive under S19_RULES), (B) pinning tests then a merge of the twin
returns, stating exactly which observable output may change and whether that is a verifier behaviour change needing
an ADR, (C) lifting the file through the smaller functions only (compute whether that can reach 7.0; the health
rule is in the common brief's "Health" section, `/home/eajfpeters/Code/OpenFlowsheet/.git/codehealth/briefs/S19-W3-common.md`).
Default: (A) if feasible. Output: the chosen path as a work order an Opus engineer can run (targets, invariants,
pinning tests to add first, acceptance), at most 40 lines.

(i) W5-S1 text: admitting new `.py` modules in an admitted tier-1 directory and added plan files
(`docs/reviews/S19-R-W5-N-close.md`, its item 4c). Default: the tool's rule stands. W5 is complete; rule only whether
the text needs amending for the record.

(ii) `revision_binding.MODEL_BUILDERS` (S19_DECISIONS.md 3888-3896, `docs/reviews/S19-R-W4-RC-N6.md`): keep as the
W27 binder-protocol attribute, strike it from I-19's list in ADR 0076, state the protocol in `reading_for`'s
docstring. Default: kept.

(iii) cascade_solve's 87-line duplication with column_compile/acceptance/solve.py (S19_DECISIONS.md 3705-3709): an
interface step with a plan (shared helper, literal moves), ~+1.0 health. Models are tier S1. Rule: do it in S19 (and
then as which mode and with which invariants) or leave it. Default: an interface step after the current lanes merge.

(iv) Batch P post-K commit 43dccc21 (S19_DECISIONS.md 4518-4526): four generator-only fixtures committed after a
write-once K. Rule: acceptable as recorded, or re-close K. Default: acceptable, flagged at the S19 -> main review.

## Output

Write `docs/reviews/S19-design-round-2.md` (one section per item: ruling, reason, and for (v) and (iii) the work
order). Do not commit. Report in at most 25 lines: each ruling in one or two lines.
