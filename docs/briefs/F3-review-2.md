# F3 package review and design-lane ruling round 2 (WO5a, WO5b)

Design lane, `reviewer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`, head
after this brief's commit (F3-WO1 to WO5b done at 50e6ca04; WO7 close-out not started). Do not spawn sub-agents
yourself. Do not edit production code or tests. Budget about 250k tokens.

## Status

ADR 0061 is **Accepted** (Frank, Decision Desk `ofs-f3-accept-adr0061`, register R-1050; the text is 5d085f05's plus
its status line), with ADR 0019 Amendment 8. So, unlike round 1:
- A ruling that fills a gap the accepted text leaves open (D13 names no refusal path for `register_record`, for
  example) is recorded as a register entry (`docs/decision-register.md`, R-1052 onward; F3 holds R-1050 to R-1059)
  and may add a clarifying sentence to the ADR in a closing section "F3 ruling round 2 applied", marked as a
  clarification under R-105x.
- A ruling that contradicts or changes the accepted text is NOT applied: write it as a question for Frank (the change,
  the reason, the alternative of keeping the text) in the review file, and rule what the build lane does meanwhile.

## Read

`docs/F3_DECISIONS.md` from the `## F3-WO5a` heading to the end (WO5a-1..9, WO5b-1..9, the "Moved" and "Left for"
paragraphs), and the open item R1-B6 (grep `R1-B6`). ADR 0061 D7 (reaction consistency), D8, D9, D11, D12 (user-file
adapter), D13, D14, E-F3-5, E-F3-10 to E-F3-12, the code table, and the "applied" sections. ADR 0019 Amendment 7 and
8. Already ruled, do not re-rule: the F3-WO1 review and round 1 (`docs/reviews/F3-WO1-review.md`,
`docs/reviews/F3-rulings-1.md`).

## Questions, in priority order

1. **Package review of WO5a and WO5b** against ADR 0061 and Amendment 8: `git diff 270b6534 50e6ca04 --
   src/openflowsheet schemas bindings`, with `records/reactions.py` read in full as numerics (the exact `Fraction`
   evaluation, the 4ε inequality, the element and charge rules, D7's `elements: null` case) and
   `application/records_service.py` for D11's precedence and `reserved_namespace(legacy)` (every path a `legacy.`
   source can enter: `sources`, a user file's `defaults.source_id`, the index copy). Check that tests carry
   ADR-derived expectations (E-F3-10 ratios, E-F3-11 transport identity, E-F3-12), not outputs copied back.
2. **WO5b-1** (a refused record refuses the whole `register_record` call; code by catalogue kind; the record code in
   `detail.reason` and `detail.refusal`) and **WO5b-9** (a refusal's params in `detail`; the engineer recommends
   `reason` = the code with its arguments): one ruling for both, since they fix the refusal shape of a frozen operation.
3. **WO5b-8** (response `$defs` in a new `record-results.schema.json`, R-1032's form) and **WO5b-4** (no-key search
   lists all; cursor encoding), **WO5b-5** (rights shape in responses).
4. **WO5a-1, WO5a-2** (reaction findings keyed by stoichiometry key; `elements: null` leaves a reaction's element
   balance unjudged): check against D7 and against ADR 0062's use (`molar_mass_inconsistent(<S>, <species>)` there,
   `(<reaction>)` here: rule which F2 should adopt, or put it to Frank if it changes accepted text).
5. **R1-B6** (A32's vetted-file branch judges components only, da41b295).
6. The rest (WO5a-3..9, WO5b-2, -3, -6, -7): rule only where one contradicts ADR 0061, ADR 0060, ADR 0019, or the
   foundation rulings Q2, Q7, Q9.
7. **Design-lane review of the five MCP descriptions** (`bindings/descriptions/` for `search_records`, `get_record`,
   `register_record`, `validate_record`, `assess_rights`; `REVIEW.json` and `tests/test_t08_w2_description_reviews.py`
   say what a review records). Do not edit `REVIEW.json`: list per tool accept / change (exact text) in the review
   file; the build lane records your review and Frank's.

F0, battery and gates are the build lane's: at b0580939 F3 tests 282 passed; the 71-file battery 2132 passed, 1
failed (the description-review test, pending by design); F0 PASS; mypy clean; arch 0/0.

## Output

1. `docs/reviews/F3-review-2.md`: findings (numbered, severity, `file:line`, the fix), one row per ruled decision
   (accept / change, the exact change and the file it lands in), the questions for Frank, the five description
   verdicts, then the build-lane changes numbered C1.. with an acceptance test each.
2. Register entries for gap-filling rulings, and the ADR clarification section if any, in one commit with the review
   file (stage by name).
3. Report back: 200 to 300 words with the commit sha, the verdict (sound to close out after C1..Cn, or not), the
   numbered build-lane changes, and the questions for Frank.
