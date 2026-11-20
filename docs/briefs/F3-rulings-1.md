# F3 design-lane ruling round 1 (build decisions WO1 to WO4)

Design lane, `reviewer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`, head
a4272c16 (F3-WO1 to WO4 done; WO5 operations and close-out not started). Do not spawn sub-agents yourself. Do not
edit production code or tests. Budget about 200k tokens.

## Why now

The build lane logged 43 revertible choices in `docs/F3_DECISIONS.md` (315 lines; read it whole): WO1-1..15,
fix1-1..4, WO2-1..9, WO3-1..7, WO4-0..7. CLAUDE.md batches them into one ruling round per package; this round runs
now, before WO5 builds the application-contract operations on them, because several are identity-bearing. ADR 0061
(`docs/adr/0061-F3-component-data.md`) is Proposed, with Frank's acceptance card pinned to its text at 8ca21576 (the
text has not changed since). This round's ADR edits are the last before the card is re-pinned once.

## Already ruled (do not re-rule)

The F3-WO1 review (`docs/reviews/F3-WO1-review.md`): M1 to M4, S1 to S8, WO1-11 with three changes, WO1-15 narrowed.
Fix round 1 applied them (the ADR section "F3-WO1 review applied").

## Questions, in priority order

1. **WO3-1 / WO4-0 (identity, rights).** D12 read literally gave 99 distinct `source_sha256` over 7 legacy sources,
   clashing with D11's one whole-source rights row per source. The orchestrator's default, implemented as WO4-0: one
   citation per legacy file fixed per profile, each component's `rights.source` as the last line of its molar-mass
   note (all 149 index SHAs moved). Rule: keep, or D12 literal with per-component rights rows, or another form.
2. **WO3-2 (identity).** Three s07 spin-isomer CAS labels (`o`/`p` suffix) fail D3's CAS check and are dropped from
   the import. Rule: drop, keep as another identifier scheme, or widen D3.
3. **WO2-1.** A corrupt existing object is refused (D8's protocol, E-F3-8) against the W1 P1 review's N7 "replace".
4. **WO2-7.** The form of the candidate `class` value in `component_ambiguous`.
5. **WO4-2, WO4-3, WO4-7.** The 11 seed rows (S10's R-880 row once per `source_sha256`), precedence keyed on
   (`source_sha256`, `record_sha256`), and whether A32's v2 clause also judges the fixture directory.
6. **fix1-1..4, WO2-2 (first submission wins, answers N1).** Confirm or change.
7. The rest: rule only where one contradicts ADR 0061, ADR 0060, ADR 0063 D2, or the foundation rulings Q2, Q7, Q9.

Check claims against the code where a ruling depends on them (`src/openflowsheet/records/`, `records/
legacy_index.json`, `records/rights-register.json`, `records/legacy_profiles.yaml`, the tests `tests/test_f3_*.py`).
F0, battery and gates are the build lane's: at a4272c16 the battery gave 2002 passed, 0 failed; F0 PASS.

## Output

1. `docs/reviews/F3-rulings-1.md`: one row per decision you rule (accept / change, with the exact change and the
   file it lands in), then the code changes the build lane must make, numbered, each with its acceptance test.
2. The ADR 0061 text edits your rulings require, applied by you in one commit (design lane owns the ADR), recorded in
   a new closing section "F3 ruling round 1 applied" listing each edit. Status stays Proposed. No edit outside what
   a ruling requires.
3. Commit the two files alone (stage by name). Report back: 200 to 300 words with the ADR commit sha, the numbered
   build-lane changes, and any question that must go to Frank.
