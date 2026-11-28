# LINE06 F2-WO3: surface link c_11, then variable ids and layout (ADR 0062 D7, D8)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it first,
including the rule on the surface suites). Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f2`, branch
`wp/F2` (head `7b2a995c`, WO1, WO2, WO2b done). Another engineer works on X06 in `.claude/worktrees/x06`; leave it
alone. Budget about 150k context: at the cap, commit what is complete, write where you stopped in
`docs/F2_DECISIONS.md`, and end.

## The task

**First commit: F2's surface-chain link c_11.** `tests/test_m07a_surface_chain.py` fails 18 tests at `7b2a995c`
because F2's kind enum moved the served surface (registered by WO2b: `F2_SERVED_SHA256` = `9a4b4eb3…`,
`SNAPSHOT_F2["list_models"]` = `854fab33…`, `tests/f2_schema_support.py` `without_f2`). Add link c_11 to
`scripts/m07a_rc.py` exactly in the pattern of c_4 to c_10 (its docstring lines ~36-80): decision **R-1072** (written,
reserved, in `docs/decision-register.md` on main), ADR 0062 D1, ADR 0019 Amendment 9 (pointer comes in WO6);
`strip_f2`, `D_11` = `F2_SERVED_SHA256`; decomposition onto c_10 (F3). WO2b's notes are in `docs/F2_DECISIONS.md`
(WO2b).

**Then WO3** as ADR 0062 states it (`docs/adr/0062-F2-material-model.md`): work-order row 3 (line ~359):
`src/openflowsheet/material/{vid,layout}.py` and `tests/f2/vid_parse.py`; the design is D7 (lines 185-195: variable
ids, the core grammar) and D8 (lines 196-213: the material layout, `layout.state(x, c)`, `solution-state-v2`'s layout
part). D6 (phase ids, lines 165-184) is built by WO1 (`material/phase_id.py`, its parser test-only).

## Facts established

- WO1, WO2, WO2b logs: `docs/F2_DECISIONS.md`. F0 on wp/F2: PASS, M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8
  105/105, M9 42/42; must stay so (row 3: "Identity: no").
- Design questions batched for F2's ruling round (do not settle; take the default that changes no existing byte):
  WO1-4, WO1-1, WO1-9, M = 1 for kg, WO2-1, WO2-7.
- E-F2-6 requires that the `src/` code path contains no id parsing: a test asserts `vid_parse` is not importable
  from `src/`.

## Acceptance (report each)

1. `tests/test_m07a_surface_chain.py`: 0 failed (count) after the c_11 commit.
2. E-F2-5 (line ~325, the variable-id part; WO1 did the phase-id part) and E-F2-6 (line ~328): test names, counts;
   E-F2-5's 10^4 generated structures with adversarial ids.
3. `tests/test_f*_*.py`, `tests/test_t07_*.py`, `tests/test_t08_w2_*.py`, `tests/test_m07a_surface_chain.py`,
   `tests/test_package_imports.py`, the schema tests: counts, 0 failed. ruff check, ruff format --check, `mypy src`
   clean.
4. F0 PASS with the counts above.

## How

Commit named paths on wp/F2, messages `F2-WO3: ...`; DECISIONs in `docs/F2_DECISIONS.md`. Long runs through
`/home/eajfpeters/Code/OpenFlowsheet/.claude/skills/line06/run.sh <name> <command>`. No push, no merge.

## Stops (report rather than choose)

The ADR contradicts the code; a change moves F0 or a v1 byte; a test passes only by relaxing a check; the chain link
needs a change outside `scripts/m07a_rc.py` and tests.

## Report (200-300 words)

Per acceptance item: pass/fail and the number; DECISIONs (one line each); commits; anything left for WO4.
