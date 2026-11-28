# LINE06 F2-WO2b: register F2's served-surface move (the F1/F3/X04 pattern)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it first).
Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f2`, branch `wp/F2` (head `88cc22b8`, WO1 and WO2
done). Another engineer works on X06 in `.claude/worktrees/x06`; leave it alone. Small order: budget about 100k.

## The task

WO1's 14 quantity kinds (ADR 0062 D1, `schemas/units.json`) moved the served interface, and nothing registered the
move. At `ed5fb6c0` and at `88cc22b8`, 16 tests fail: 5 in `tests/test_t07_w5e_application_results.py` (`list_models`
digest `854fab33…` vs the snapshot `12d88245…`) and 11 in `tests/test_t08_w2_surface_digest.py` (served tool list
`9a4b4eb3…` vs the registered `f7ec3c94…`). Register the move the way earlier packages did. The pattern is in the
docstring of `tests/test_t08_w2_surface_digest.py` (lines 1-95; X04 at ~67, F1 at ~74, F3 at ~78) and in
`tests/f3_schema_support.py` (`without_f3`) / `tests/x04_schema_support.py`: a new `tests/f2_schema_support.py` with
`without_f2` that removes exactly F2's additions (here: the new kind values inside served schemas, not tools), a new
`F2_SERVED_SHA256` pin, a decomposition test proving `without_f2(served) == F3's served digest`, the docstring
paragraph for F2 (ADR 0062 D1, the ADR 0019 pointer comes in WO6), and the `list_models` snapshot handled the same way
(find what `list_models` serves that carries the kind enum; decompose its move to the old snapshot likewise if the
earlier packages did so for it, else re-take the snapshot with a test that proves the difference is exactly F2's kinds).

## Facts established

- F2-WO1 log `docs/F2_DECISIONS.md` WO1-1 to WO1-9; WO2 log WO2-1 to WO2-8. F0 on wp/F2 PASS, M1 50/50, M2-M5 61/61, M6
  85/85, M7 52/52, M8 105/105, M9 42/42; it must stay so.
- ADR 0078 D6 (X06, on wp/X06): whichever of F2 and X06 merges second decomposes its digest onto the first's. Keep
  `without_f2` composable with the existing `without_*` helpers.
- No change to `src/` is expected. If the only way to pass is a `src/` change, stop and report.

## Acceptance (report each)

1. The 16 tests pass, and the new decomposition tests pass; name them with counts.
2. `tests/test_t07_*.py`, `tests/test_t08_w2_*.py`, `tests/test_f*_*.py`, `tests/test_x0*_*.py`, `tests/test_msg_*.py`: counts,
   0 failed.
3. ruff check, ruff format --check, mypy on the touched files clean.
4. F0 PASS with the counts above.

## How

Commit named paths on wp/F2, message `F2-WO2b: ...`; log any DECISION in `docs/F2_DECISIONS.md`. No push, no merge.

## Report (at most 200 words)

Per acceptance item: pass/fail and the number; the new pins (first 8 hex); commits.
