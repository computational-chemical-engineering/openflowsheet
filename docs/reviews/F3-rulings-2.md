# F3 design-lane ruling round 2 (fix round 3: F3-3-1 to F3-3-4, the E-F3-8 store fix, the manifest form)

Design lane, `reviewer`, 2026-11-18. Brief `docs/briefs/F3-rulings-2.md`. Branch `wp/F3` at `c946bfec` (code at
`05ccf880`, manifest at `db59c345`). Read: `docs/F3_DECISIONS.md` from "F3 fix round 3" to the end,
`docs/briefs/F3-fix3.md`, the commits `7aa1adef`, `b2399a2a`, `3a43dd75`, `fdb730b3`, `records/store.py` (opening,
connections, `_writing`, every write), the six cached readers and their callers, `tests/test_t07_interrupt.py` (the
§8.1 lint), the Q26 docstring and allowance, ADR 0061 D7 and its closing sections, the manifest at `05ccf880`, the
evidence-manifest schema, and the CI evidence file of run 44283813577 (the E-F3-8 traceback).

**Verdict.** All four decisions are kept. The E-F3-8 fix is correct and complete for the first opening. The manifest
form is acceptable and no schema change or ADR is owed. Five build-lane changes follow (C1 to C5). None reopens a
decision. They add a deterministic test of the WAL retry, extend the §8.1 lint to the `finally` form F3-3-3 relies on,
keep the original exception when SQLite has already ended a transaction, cite the Q26 exception, and move the manifest
with the one schema rule it misses. ADR 0061 gains one clarification row (the Q26 exception, R-1058) in a closing
section. The section is titled "F3 ruling round 2 applied: fix round 3" because the heading "F3 ruling round 2
applied" already holds the rulings of F3 review 2.

## Facts checked (each decides a ruling)

- **The WAL switch.** `PRAGMA journal_mode = WAL` on a database in rollback mode opens a read transaction (a SHARED
  lock) and, when page 1 is not yet version 2, upgrades it to a write transaction. SQLite does not call the busy
  handler on an upgrade from a held read lock. This is its documented deadlock rule (`sqlite3_busy_handler`: "If
  SQLite determines that invoking the busy handler could result in a deadlock, it will go ahead and return
  SQLITE_BUSY"). Of two processes opening one new store at once, the one that loses the RESERVED race therefore gets
  `SQLITE_BUSY` at once, while the winner waits for EXCLUSIVE inside the busy handler. The log has the cause and the
  fix right. Its mechanism sentence ("takes an exclusive lock without calling SQLite's busy handler") is imprecise:
  the unguarded step is the read-to-write upgrade (C1 corrects the docstring). This account comes from SQLite's
  documentation and its btree/pager code as I know them. C1's test (i) is the falsifier. The CI traceback runs
  `register` → `_write_object` → `_open` → `_open_directory`, the first opening.
- **Only SQLITE_BUSY is retried.** `error.sqlite_errorcode` is the *extended* code (CPython takes it from
  `sqlite3_extended_errcode`), and only plain `SQLITE_BUSY` (5) is retried. The upgrade failure is plain BUSY. In this
  path the extended BUSY codes (RECOVERY, SNAPSHOT, TIMEOUT) appear only after SQLite's own busy handler has run, so
  re-raising them is right. Any other error re-raises unchanged.
- **The deadline.** It is checked after every failed attempt, and nothing is retried after it. One attempt's read-lock
  acquisition can itself wait in the busy handler for up to `busy_timeout`, so the worst case is about
  2 × `BUSY_TIMEOUT_S`. That is acceptable (note).
- **A database already in WAL** finds version 2 on its read, opens the WAL and takes no write lock, so it answers at
  once. C1's test (iii) pins this.
- **The other first-opening statements.** The pragmas `busy_timeout` and `synchronous` take no lock. `_create`'s
  `BEGIN IMMEDIATE` starts from no transaction, so its wait calls the busy handler. `CREATE TABLE IF NOT EXISTS` and
  `INSERT OR IGNORE` make a second opener's `_create` idempotent, and in WAL its COMMIT takes no further lock. Every
  later write is inside `_writing`'s `BEGIN IMMEDIATE` (`store.py` 332, 400, 479, 511), and no deferred
  read-then-write transaction exists. T07's `ProjectStore.create` switches to WAL only in an empty directory it has
  just made (one creator), not on a lazy first opening, so it does not have the same exposure.
- **The test of record is probabilistic.** `test_e_f3_8_two_processes_register_200_overlapping_records` failed on x86
  CI only. The 8-process harness behind "56/160 before, 0/160 after" is not in the repository, so a revert of
  `fdb730b3` would most likely pass locally. → C1.
- **F3-3-3: every exit of `_writing`, old (`except BaseException: ROLLBACK; raise`) against new (`try/finally` with
  `completed`).** Normal exit: COMMIT in both. `Exception`, `KeyboardInterrupt`, `JobInterrupted`: ROLLBACK, then the
  same exception, in both. `GeneratorExit` (close at the yield): ROLLBACK, then propagation, in both. An exception
  inside ROLLBACK: the new error, chained to the original, in both. An exception inside COMMIT: COMMIT is outside the
  `try` in both, so there is no ROLLBACK in either. An asynchronous interrupt after the body and before COMMIT has the
  same window in both. The two are the same function.
- **A shared defect of both forms.** When the body's exception comes after SQLite has already ended the transaction
  (SQLITE_FULL, IOERR and NOMEM can roll back automatically, as does a body that ran ROLLBACK), both forms run
  ROLLBACK, which raises `cannot rollback - no transaction is active` with the original only as `__context__`. The
  caller then sees the wrong error, against the docstring's "the exception propagates unchanged". → C3.
- **The §8.1 lint sees only `except` handlers.** A `finally` holding `return`, `break` or `continue` discards the
  exception in flight (a `JobInterrupted` included), and `broad_handlers` cannot see it. An AST scan of `src/` at
  `c946bfec` finds no such `finally`. → C2.
- **G20.** The six readers are nullary and read only package data:
  - `record_schema` (a dict, read by `strip_empty` and `_target`, never written);
  - `_validator`;
  - `repository_rows`, a tuple of dicts whose members are all `str` or `None` (`check_row`), so `{**row, ...}` is a
    full copy, and `Effective` carries `str | None`;
  - `profiles`, frozen `Profile`s whose provenance rows `_File.provenance` copies into new lists and dicts;
  - `committed_index`, iterated, while `_held` returns new projections;
  - `legacy_shas`, a frozenset.

  No cached object reaches a response by identity.
- **Q26.** D7 fixes the input `{id, stoichiometry: {component key: ν}}`, and the scan finds exactly one map at that
  path and no array. Each earlier exception to R-088 Q26 is recorded in an authority document: M02's design note §14
  B2, ADR 0070, and ADR 0071 with Amendment 16. ADR 0061 names the form but not the exception.
- **`local.py`.** The 49 duplicated lines are the `Records` protocol's signatures (ADR 0019 Amendment 8, frozen),
  restated by the facade and by `RecordsService` (ratio 0.119 against 0.10). No file in `src/` carries an allow-file
  line.
- **Manifest schema.** `checks[].result` admits `pass`, `fail`, `unsupported` and `not_applicable`. `review` is closed
  to `numerical` and `process_model`, both free strings, and M02 and M04 carry a design-lane pointer as `"pending
  (design-lane review: ...)"`. On `requirements` the schema says: "empty is allowed only when the package maps to no
  D/A requirement, which must then be stated in limitations". F1's manifest states it. F3's does not.

## Rulings

| # | Question | Ruling | Lands in |
| --- | --- | --- | --- |
| 1 | F3-3-1, G20's six `@cache` readers | **Accept.** All six stay listed. None is keyed on an input, none holds job, request, project or store state, and no cached object reaches a response by identity. Their justifications state what is cached, keyed on what, and why it holds no external state. | none |
| 2 | F3-3-2, Q26 and `reactions/*/stoichiometry` | **Accept** the allowance by full path in `ALLOWED_BY_PATH`. **ADR 0061 owns the exception** as a clarification of D7 against R-088 Q26 (closing section, R-1058, this commit). The test implements and cites it, as M02, X02 and OPT do. | ADR 0061, register (this commit); test citation C4 |
| 3 | F3-3-3, the `try/finally` rollback | **Accept.** It is the same function on every exit (see the facts above). A `finally` without control flow cannot swallow, so it meets §8.1's intent rather than defeating it. Do not extend the directory allowance to `records/`. Guard the form instead (C2) and keep the original exception (C3). | `tests/test_t07_interrupt.py` (C2), `records/store.py` (C3) |
| 4 | F3-3-4, the `local.py` duplication | **Leave it.** An allow-file line would blind the detector to a real copy in the facade, and it would be the first in `src/`. A mixin moves the restatement without removing it. This is accepted debt, recorded here. | none |
| 5 | E-F3-8 fix `fdb730b3` | **Sound.** The cause agrees with SQLite's busy rule, only plain BUSY is retried, the deadline is honoured (worst case about 2 × 30 s), a WAL database pays one read, and no other first-opening statement is exposed. Add a deterministic test and correct the docstring's mechanism (C1). | `tests/test_f3_store.py`, `store.py` docstring |
| 6 | Manifest at `db59c345` | **Acceptable, no schema change and no ADR.** CI pending as a limitation with status `implemented` is X10c's form. A check either ran or is not yet a check. The design-lane records are not sign-offs and rightly sit outside `review` (M02's parenthetical form is also valid). One defect: `requirements` is empty without the stated reason (C5). | the next manifest (C5) |

## Build-lane changes (in this order, one commit each, the message naming "F3 rulings2 Cn")

**C1 (should fix): a deterministic E-F3-8 test.** Add three tests to `tests/test_f3_store.py`, all on a file store:
1. `test_e_f3_8_the_wal_switch_waits_for_a_writer`:
   - set-up: create `<root>/records/` and the database `<root>/records/<DATABASE_NAME>` holding one table (rollback
     journal); a second connection (`isolation_level=None`, `check_same_thread=False`) takes `BEGIN IMMEDIATE`, and a
     `threading.Timer(0.3, …)` rolls it back;
   - expected: the store's first `register` succeeds after at least 0.25 s, and `PRAGMA journal_mode` reads `wal`.
2. `test_e_f3_8_the_wal_switch_gives_up_at_the_deadline`:
   - set-up: as test 1, but the holder keeps its lock for the whole call, and `BUSY_TIMEOUT_S` is monkeypatched to 0.3
     in `openflowsheet.records.store`;
   - expected: the first operation raises `sqlite3.OperationalError` with `sqlite_errorcode == sqlite3.SQLITE_BUSY`
     after at least 0.3 s and less than 5 s.
3. `test_e_f3_8_a_wal_database_is_not_retried`:
   - set-up: a store already opened (in WAL), a holder taking `BEGIN IMMEDIATE`, and `BUSY_TIMEOUT_S` patched to 2;
   - expected: `_journal_mode_wal` on a new connection to the database returns `wal` in less than 0.5 s.

In the same commit, `_journal_mode_wal`'s docstring states the mechanism: the switch upgrades the read lock it holds
to a write lock, and SQLite returns `SQLITE_BUSY` on that upgrade rather than call the busy handler, to avoid
deadlock.
*Acceptance:*
- The three pass.
- With `_journal_mode_wal`'s body reduced locally (not committed) to the bare pragma, tests 1 and 2 fail at once with
  `database is locked`.
- The three, run 20 times in a loop, pass 20 of 20.

**C2 (should fix): the §8.1 lint covers `finally`.** Add `test_no_finally_exits` to `tests/test_t07_interrupt.py`. It
fails on any `try … finally` in `src/` (`ast.Try` and `ast.TryStar`) whose `finally` body holds:
- a `return`;
- or a `break` or `continue` that is not inside a loop which is itself inside that `finally` body.

Nested `def`, `class` and `lambda` bodies are skipped. `test_lint_detects` gains five cases:

| Case | Flagged |
| --- | --- |
| `return` in a `finally`, inside a `def` | yes |
| `break` in a `finally`, inside an outer `for` | yes |
| a `for` with `break`, wholly inside the `finally` | no |
| a nested `def` with `return`, inside the `finally` | no |
| `cleanup()` in the `finally` | no |

`test_no_broad_except`'s docstring names the `finally` form (`records/store.py` `_writing`) as the cleanup that may
stand outside `application/`.
*Acceptance:*
- Both tests pass, with 0 hits in `src/`.
- Adding `return` to `_writing`'s `finally` locally (not committed) makes `test_no_finally_exits` fail.

**C3 (should fix): keep the original exception.** In `records/store.py` `_writing`, change the condition to
`if not completed and connection.in_transaction:` before `ROLLBACK`. Add a test to `tests/test_f3_store.py`,
parametrized over `file` and `memory`: inside `store._writing()` the body executes `ROLLBACK` and then raises
`ValueError`; the `ValueError` propagates (not `sqlite3.OperationalError`), and a following `register` succeeds.
*Acceptance:*
- The test fails before the change (`cannot rollback - no transaction is active`) and passes after it.
- `tests/test_f3_store.py` and `tests/test_t07_interrupt.py` pass.

**C4 (should fix): cite the Q26 exception.** In `tests/test_t07_q26.py`, the F3 docstring paragraph and the comment
above `ALLOWED_BY_PATH` cite "ADR 0061, section 'F3 ruling round 2 applied: fix round 3'; R-1058" beside D7.
*Acceptance:*
- `tests/test_t07_q26.py` passes.
- `grep -c R-1058 tests/test_t07_q26.py` is at least 1.

**C5 (must fix): the manifest move.** The manifest moves to the commit of C1 to C4, with status `implemented`, in the
fix round 3 form:
- **Requirements line.** `limitations` gains the line the schema's `requirements` rule demands, in F1's form
  ("Requirements empty: F3 maps to no D/A requirement; …"). Check it against the plan's F3 row before writing it.
- **Open-items line.** The line on the open DECISIONs points to this file instead of listing them.
- **Artifacts.** `artifacts` re-hashes ADR 0061, which this commit changes.
- **Harvest.** The harvest rows and `HARVEST_SIZE` move as in fix round 3.
- **Decisions log.** `docs/F3_DECISIONS.md` gains a "Ruling round 2 applied" entry.
- **When `tested` is set.** `commands` names the CI run ID and the commit that CI ran, because the manifest commit
  sits on top of `commit`.

*Acceptance:*
- `tests/test_evidence_manifests.py`, `tests/test_t08_w2_support_envelope.py` and `tests/test_m07a_harvest.py` pass.
- `scripts/t08_support_matrix.py --check` is clean.

## Notes (not ruled; no change asked)

- **Retry pacing.** The retry sleeps a fixed 5 ms with no jitter. Many openers in lockstep could in principle keep
  colliding until the deadline (measured: 0 of 160). Jitter is optional.
- **COMMIT outside the `try`.** A failed COMMIT is not rolled back, in either form. That is harmless today: the file
  connection closes, and the in-memory store has one connection and no deferred constraint (no `REFERENCES`). If a
  deferred constraint is ever added, move COMMIT inside the `try`, under C3's guard.
- **Mutable caches.** The cached containers of F3-3-1 are mutable (dicts, and dicts inside a tuple), so "nothing
  reaches a response" rests on caller discipline. Returning `MappingProxyType` would be a hardening, not a
  requirement.
- **Two rollback forms.** T07's `application/store.py` keeps `except BaseException: ROLLBACK; raise`, so the repository
  holds two forms of one idiom. Both are correct, and neither must change.
- **The duplication detector.** A detector that counts signature-only windows of a protocol facade as duplication is a
  question about the tool (cce-code-health), not about F3.

## Not examined

- `REVIEW.json`.
- The A21/A50 harvest arithmetic beyond the counts the log states.
- The codehealth debt figures.
- The race harness (not committed).
- The result of CI run 44322172910.
- ADR 0061 beyond D7 and its closing sections.
- `legacy.py` beyond the cached readers and their callers.

## For Frank

Nothing new. `REVIEW.json`'s human sign-off on the five MCP descriptions still waits for him, as before.
