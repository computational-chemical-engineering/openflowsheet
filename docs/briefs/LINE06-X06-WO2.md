# LINE06 X06-WO2: branches (ADR 0078 D2)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it first; note
the rule that every work order runs `tests/test_t07_*.py` and `tests/test_t08_w2_*.py` and registers any served-digest
move itself). Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06`, branch `wp/X06` (head `203f7e97`,
WO1 done). Another engineer works on F2 in `.claude/worktrees/f2`; leave it alone. Budget about 150k context: at the
cap, commit what is complete, write where you stopped in `docs/X06_DECISIONS.md`, and end.

## The task

Build X06-WO2 as ADR 0078 states it (`docs/adr/0078-X06-application-capabilities.md`): D2 (lines 98-137: branches as
named rows of the store's existing `refs` table, `application/store.py:90`; the optional ChangeSet member `branch`,
outside the request hash when absent or `"head"`; `list_branches`, `create_branch`, `delete_branch`; promotion by the
existing `restore_from`; D2.6's store rules) and work-order row 2 (line 384), in its stated order: **first commit the
E-X06-7 golden list taken at `aa5822ac`** (the main commit before X06, so the list proves old requests hash as
before), then the code: `store.py`, `revision_service.py`, `transaction_types.py` (`Change.branch`),
`schemas/change-set.schema.json`, `schemas/application-results.schema.json` (`branch`, `branch_page`,
`branch_result`), `contract.py` (`Branches`), `operations.py`, `authz.OPERATION_RIGHTS`, `branch_service.py`,
`local.py`, the three description files and the `branch` sentence in `commit_change.md` and `preview_change.md`,
`.codehealth/config.toml` layers, catalogue entries, `tests/x06_schema_support.py` (`without_x06`) and the digest pin
`X06_SERVED_SHA256` (D6, lines 237-247), and the new operations as steps of the conformance scenario (all six
clients). WO1's note: change E-X06-2's digest check from `F3_SERVED_SHA256` to `X06_SERVED_SHA256`.

## Facts established

- X06-WO1 (log `docs/X06_DECISIONS.md` WO1-1 to WO1-8): `/mcp` served on `serve-http`; conformance has six clients
  (36 passed); 2501 passed in its battery; F0 at its head being re-checked by the orchestrator (main: M1 50/50, M2-M5
  61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42; must stay so: branches change no record, identity or store schema,
  `t07-store-v1`).
- ADR 0078 is Proposed (card `ofs-x06-accept-adr0078`, pinned to `dcbab9b7`): **do not edit the ADR**; log any
  divergence as a DECISION instead and report it.
- ADR Q8: F2 is being built on wp/F2 and will move the served list (F2-WO2b registers F2's move now; F2-WO6 touches
  the revision dispatch later). Build X06 on main's digest (F3's); the second branch to merge decomposes onto the
  first's. Keep `without_x06` composable with the other `without_*` helpers.

## Acceptance (report each)

1. E-X06-6 to E-X06-10 and E-X06-22 (ADR "Exit tests", lines 311-330 and 366): test names, counts; E-X06-8's 20
   trials per race in threads and two processes.
2. `tests/test_t07_*.py` (with the conformance scenario's new steps on six clients), `tests/test_t08_w2_*.py`,
   `tests/test_x06_*.py`, the MSG and doc-page tests: counts, 0 failed.
3. ruff check, ruff format --check, mypy clean.
4. F0 PASS with the counts above.

## How

Commit named paths on wp/X06, messages `X06-WO2: ...`. Long runs through
`/home/eajfpeters/Code/OpenFlowsheet/.claude/skills/line06/run.sh <name> <command>`. No push, no merge.

## Stops (report rather than choose)

A change to a stored record, a run identity, the store schema or an existing request hash; the ADR contradicts the
code; a test passes only by relaxing a check.

## Report (200-300 words)

Per acceptance item: pass/fail and the number; DECISIONs (one line each); commits; anything for WO3.
