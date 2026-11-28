# LINE06 F2-WO4: `ProcessRevision` v2 and `Specification` v2 (ADR 0062 D9 to D11)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it first,
including the surface-suite rule). Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f2`, branch `wp/F2`
(head `41177bcf`, WO1 to WO3 done). Another engineer works on X06 in `.claude/worktrees/x06`; leave it alone. Budget
about 150k context: at the cap, commit what is complete, write where you stopped in `docs/F2_DECISIONS.md`, and end.

## The task

Build F2-WO4 as ADR 0062 states it (`docs/adr/0062-F2-material-model.md`), work-order row 4 (line ~360):
`schemas/process-revision-v2.schema.json` and `schemas/specification-v2.schema.json`;
`src/openflowsheet/revision_v2/{__init__,parse,validate,canonical}.py`; fixtures under `tests/fixtures/schemas/v2/`.
Design: D9 (lines 214-225: energy and signal connections, endpoints), D10 (lines 226-235: `Specification` v2), D11
(lines 236-267: `ProcessRevision` v2), the core/preview split of D13 (lines 287-295), and the typed refusals of the
catalogue table "New catalogue codes" (lines 342-349). Also give WO3's layout refusals typed codes (DECISION WO3-6:
today plain `ValueError`) where the catalogue table names them, and extend E-F2-6 to WO4's fixtures. Lowering and the
operations dispatch are WO6, not this order: `revision_v2` parses, validates and canonicalises v2 documents only.

## Facts established

- WO1 to WO3 logs: `docs/F2_DECISIONS.md`. The material package (`material/{state,phase_id,definitions,basis,vid,
  layout}.py`), the conserved bases, connection definitions and built-in templates (`registry/builtin/material.json`)
  exist. Surface: `F2_SERVED_SHA256` 9a4b4eb3…, chain link c_11 (R-1072). F0 on wp/F2: PASS, M1 50/50, M2-M5 61/61, M6
  85/85, M7 52/52, M8 105/105, M9 42/42; must stay so (row 4: "Identity: no"). v1 documents, their schemas and every
  v1 byte stay unchanged; `content_hash` of v1 revisions unchanged (`application/revisions.py:51`).
- A new schema needs the registrations F3-WO1 and F2-WO2 made (`docs/F3_DECISIONS.md` WO1-2; `docs/F2_DECISIONS.md`
  WO2): `schemas/registry.json`, the numerical-policy addendum, package data. If the served surface moves, register
  the move in this order (extend `without_f2`, re-pin `F2_SERVED_SHA256` and c_11's `D_11`, R-1072's evidence row on
  wp/F2).
- Design questions batched for F2's ruling round (do not settle; default = changes no existing byte): WO1-4, WO1-1,
  WO1-9, M = 1 for kg, WO2-1, WO2-7, WO3-6.

## Acceptance (report each)

1. E-F2-2 (line ~319: round trips of all three connection kinds, all three endpoint kinds, `mat-v1` with `mixed` and
   `solid` substreams, a group basis, a classed attribute on a grid, a reaction set, a section; parse, canonical,
   parse is a fixed point; `content_hash` stable under key reordering, moved by any core field change).
2. E-F2-8 (line ~334) and E-F2-9 (line ~336: one fixture per catalogue code, each refused with exactly that code and
   params). Test names and counts.
3. `tests/test_f*_*.py`, `tests/test_t07_*.py`, `tests/test_t08_w2_*.py`, `tests/test_m07a_surface_chain.py`,
   `tests/test_m02_*.py`, `tests/test_m04_*.py`, `tests/test_msg_*.py`, `tests/test_x0*_*.py`, `tests/test_package_imports.py`,
   the schema tests: counts, 0 failed, **run after your last commit**. ruff, ruff format --check, `mypy src` clean.
4. F0 PASS with the counts above, at your last commit.

## How

Commit named paths on wp/F2, messages `F2-WO4: ...`; DECISIONs in `docs/F2_DECISIONS.md`. The fixture part may be
mechanical; keep it in its own commit. Long runs through
`/home/eajfpeters/Code/OpenFlowsheet/.claude/skills/line06/run.sh <name> <command>`. No push, no merge.

## Stops (report rather than choose)

The ADR contradicts the code; a v1 byte, hash or F0 count moves; a test passes only by relaxing a check; a scientific
question D9 to D11 do not answer.

## Report (200-300 words)

Per acceptance item: pass/fail and the number; DECISIONs (one line each); commits; anything left for WO5/WO6.
