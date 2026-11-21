# F3 design-lane ruling round 2 (fix round 3 decisions F3-3-1 to F3-3-4, and the E-F3-8 store fix)

Design lane, `reviewer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`, head
db59c345 (fix round 3 done, pushed; CI 44322172910 running). Do not spawn sub-agents yourself. Do not edit production
code or tests. Budget about 120k tokens.

## Context

Read `CLAUDE.md`, then `docs/F3_DECISIONS.md` from line 682 ("F3 fix round 3") to the end, and the brief it answered,
`docs/briefs/F3-fix3.md`. The build lane fixed six CI failures of run 44283813577 and logged four revertible
choices for this round. Already ruled and not to be re-ruled: `docs/reviews/F3-rulings-1.md`, the F3 review 2
(`docs/briefs/F3-review-2.md` and its outcome in the log). `REVIEW.json` waits for Frank: do not touch it.

## Questions

1. **F3-3-1 (7aa1adef):** six `@cache` nullary readers of package data put on the G20 allowlist. Rule: accept, or
   name which caches must go (the G20 rule's intent: no cache keyed on inputs, nothing cached reaching a response).
2. **F3-3-2 (b2399a2a):** Q26 allows `validate_record`'s `reactions/*/stoichiometry` map by full path, citing ADR 0061
   D7. Rule: accept, or the change (and whether ADR 0061 or the Q26 test owns the allowance).
3. **F3-3-3 (3a43dd75):** the record store's rollback as `try/finally` with a completion flag instead of `except
   BaseException: ROLLBACK; raise`. Rule: is it the same function on every exit (normal, `Exception`, interrupt,
   `GeneratorExit`, an exception inside COMMIT itself), and is a `try/finally` that defeats the lint acceptable, or
   should the test's allowance be extended instead.
4. **F3-3-4:** the `local.py` duplication smell (protocol signatures restated by the implementation) left, not
   suppressed. Rule: leave, allow-file line, or mixin.
5. **E-F3-8 store fix (fdb730b3), review, not a choice:** `_journal_mode_wal` retries `PRAGMA journal_mode = WAL` on
   `SQLITE_BUSY` until `BUSY_TIMEOUT_S`. Check the cause stated in the log against SQLite's documented behaviour, that
   only SQLITE_BUSY is retried, that the deadline is honoured, that a database already in WAL pays nothing, and that
   no other first-opening statement (schema creation, other pragmas) has the same unguarded lock. Measured: race
   harness 56/160 openings failed before, 0/160 after; the test 50/50 in a loop, 50/50 under load.
6. **Manifest at db59c345:** CI-pending and the review records moved to limitations because the schema rejects
   `pending` and `design_lane`/`human` review members. Rule: acceptable form, or a schema change owed (an ADR).

Check claims against the code (`src/openflowsheet/records/store.py`, `tests/` for G20, Q26, no_broad_except, the
manifest at `evidence/F3/05ccf880*/manifest.json`).

## Output

1. `docs/reviews/F3-rulings-2.md`: one row per question (accept / change, with the exact change and the file it lands
   in), then the numbered build-lane changes, each with its acceptance test.
2. ADR text edits only where a ruling requires one, in one commit, with a closing section "F3 ruling round 2 applied".
3. Commit your files alone (stage by name; do not push). Report back in 200 to 300 words: the commit sha, the
   numbered build-lane changes, and any question that must go to Frank.
