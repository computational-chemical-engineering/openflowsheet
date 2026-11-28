# LINE06 F2-WO1: quantity kinds and provider-level types (ADR 0062 D1, D2, D6 grammar part)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it first).
Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f2`, branch `wp/F2` (from main `d00f659a`). Budget
about 150k context: at the cap, commit what is complete, write where you stopped in `docs/F2_DECISIONS.md`, and end.

## The task

Build F2's first work order as ADR 0062 states it (`docs/adr/0062-F2-material-model.md`, row 1 of "Work orders"):
the new quantity kinds in `schemas/units.json` (D1, lines 34-61); the provider-level types in a new package
`src/openflowsheet/material/` (`__init__.py`, `state.py`, `phase_id.py`), re-exported from `openflowsheet.thermo`
(D2, lines 62-90: `EvaluationState` and its round trip with `StreamState`, `PhaseId`; the two widened annotations
`PropertyRequest.state` and `PropertyRequest.phase`, `thermo/__init__.py:133`); the D2 cache keys in
`src/openflowsheet/thermo/cache.py` (the `StreamState` key byte-unchanged, M6); `phase_id.py` rendering and parsing
the D6 grammar (lines 165-184) for the phase-id part of E-F2-5; and ADR 0061's `kg` / `segment_mol` gate lifted
(`src/openflowsheet/records/model.py:30` table, `records/validate.py:135`; ADR 0061 E-F3-13, line 579-583, and Q2.A10
(b): `kg` records register instead of being refused `amount_basis_unsupported(kg)`), with the F3 tests' `kg` branches
updated to the new expectation (`tests/test_f3_record_model.py`, `tests/test_f3_legacy.py` where they assert the
refusal).

## Facts established

- P1 (orchestrator, 2026-11-26): every existing file and symbol WO1 names resolves on main: `StreamState`
  `thermo/__init__.py:105`, `Phase = Literal["LIQUID", "VAPOR"]` `:58`, `PropertyRequest` `:133`, `thermo/cache.py`,
  `schemas/units.json`; `material/` does not exist yet. `ComponentBasis` is `models/revision_flowsheet.py:104`.
- F0 on main `d00f659a`: PASS, M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9
  42/42. WO1 changes no identity (ADR row 1: "Identity: no"); F0 must stay exactly this.
- ADR 0062 is Proposed; build on its text as written (it was reviewed in W1 P2, fixes applied, lines 393-413). Where
  it is silent, take the reading that changes no existing byte and log a `DECISION` (format: `docs/F3_DECISIONS.md`).
- `schemas/` is frozen by plan §2.2 except through an ADR: ADR 0062 is that ADR, so adding kinds is in scope; adding
  a schema file or kind needs the registrations F3-WO1 needed (see `docs/F3_DECISIONS.md` WO1-2: `schemas/registry.json`,
  the numerical-policy addendum, `tests/test_package_imports.py` `LAYERS`, `.codehealth/config.toml` layer order).

## Acceptance (report each)

1. E-F2-1 (ADR line 317): over every stream of every corpus run, `EvaluationState.from_stream_state(s)
   .to_stream_state()` equals `s` bitwise (each float by `struct.pack('<d')`). Name the test and the count of streams.
2. The phase-id part of E-F2-5 (render then parse is the identity on generated structures, no v2 id equals a legacy
   id), with its count.
3. Q2.A10 (b) and E-F3-13's `kg` branches: the updated tests pass.
4. The tests you touched and `tests/test_f3_*.py`, `tests/test_f1_*.py`, `tests/test_package_imports.py` pass; ruff
   check, ruff format --check and mypy on the touched files clean.
5. F0: `PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=src python scripts/corpus_identity.py
   --check` prints PASS with the counts above, unchanged.

## How

Commit named paths on wp/F2 with messages `F2-WO1: ...`; start `docs/F2_DECISIONS.md` (append-only, like
`docs/F3_DECISIONS.md`). Long runs through `/home/eajfpeters/Code/OpenFlowsheet/.claude/skills/line06/run.sh <name>
<command>` (one summary line). No push, no merge, no manifest (WO7 does that).

## Stops (report rather than choose)

The ADR text contradicts the code; a change would move F0 or any existing byte of a v1 path; a test can only pass by
relaxing a check; a scientific question (unit semantics, kinds) the ADR does not answer.

## Report (200-300 words)

Per acceptance item: pass/fail and the number. The DECISIONs taken (one line each). Commits (short sha). Anything left
for WO2.
