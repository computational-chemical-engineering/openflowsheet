# F3-WO2: store and resolution (ADR 0061, roadmap 0.5)

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`,
head after this brief's commit (WO1 and its fix round 1 done at 8ca21576). Work only there. Do not spawn sub-agents
yourself. Budget about 150k tokens of context: at the cap, commit what is complete, write where you stopped in
`docs/F3_DECISIONS.md`, and end.

## Status

ADR 0061 is Proposed; Frank's acceptance card is pinned to its text at 8ca21576. **Do not edit
`docs/adr/0061-F3-component-data.md`.** Where the ADR is ambiguous, take the reading that changes no existing byte,
record it as `DECISION WO2-<n>` in `docs/F3_DECISIONS.md` (choice, alternative, where it lives; one revertible
commit) and carry on; a proposed ADR edit goes in that log as text for the design lane. Stop only if a choice would
change an existing artifact's identity.

## Read (narrowly, `sed -n` ranges)

ADR 0061: D8 (store), D9 (identity-key resolution), D2 only as WO1 implemented it, Exit tests E-F3-8 and E-F3-9,
"New catalogue codes" (`store_object_corrupt`, `store_path_too_long`, `component_ambiguous`), the work-order table
row 3a, "Risks and open questions", "Review applied" (W1 P1 review items left open for WO2: grep `WO2`). WO1's code:
`src/openflowsheet/records/` (the identity function and normaliser you store by). Build log: `docs/F3_DECISIONS.md`
(grep `WO2` and the notes N1 to N11 left for later WOs; take those that belong to WO2). New-code rules:
`.codehealth/playbook.md`.

## Deliverables (WO2 only)

- `src/openflowsheet/records/{store,stack,resolve}.py`: the content-addressed object store (atomic write, the
  Windows replace semantics, corrupt-object detection, the path-length check), the store stack, and identity-key
  resolution with the ambiguity classes (`source`, `identity`) as D8 and D9 state.
- The `records.sqlite3` schema as D8 states it.
- Catalogue entries for the codes these paths return.
- Tests `tests/test_f3_store.py` (and fixtures): E-F3-8 in full (including two processes registering 200 overlapping
  records concurrently, the simulated Windows `PermissionError` cases, the 167/168 path-length boundary) and E-F3-9
  with synthetic records. The source-checkout part of E-F3-9 (`methanol` across `s07` and `s10`) needs WO3's legacy
  import: write it as a test marked to skip with the reason "needs F3-WO3 legacy import", not as a pass.

## Acceptance (run and quote)

1. `tests/test_f3_store.py` and `tests/test_f3_record_model.py` pass; `ruff check`, `ruff format --check`, full
   `mypy` (repo `.venv`, no arguments).
2. The 62 test files in
   `/tmp/claude-1000/-home-eajfpeters-Code-OpenFlowsheet/10ed1d55-8773-442e-9840-53568b103799/scratchpad/f3-tests.txt`
   plus the new file, once at the end on an unchanged tree (`PYTHONPATH=<worktree>/src`, repo `.venv`, no `-n`; do
   not commit while it runs; at 8ca21576: 1923 passed, 0 failed).
3. `codehealth scan` (`/home/eajfpeters/Code/OpenFlowsheet/.venv-codehealth/bin/codehealth scan --json
   <scratch>.json`) on `records/`: no brain function, every file health >= 9.0.
4. F0 `scripts/corpus_identity.py --check` PASS.

Commits name `F3-WO2`. Do not write an evidence manifest, never set `reviewed`.

## Report (200 to 300 words)

Commits; acceptance results with counts; the DECISIONs; anything that moved a registry or catalogue SHA and what was
re-taken; what is left for WO3.
