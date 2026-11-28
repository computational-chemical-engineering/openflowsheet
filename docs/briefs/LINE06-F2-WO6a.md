# LINE06 F2-WO6a: lowering, raising, `solution-state-v2` (ADR 0062 work order 6, first half)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it first,
including the surface-suite rule). Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f2`, branch
`wp/F2` (head `f4c5cd7a`: WO1 to WO5 done). Another engineer works on X06 in `.claude/worktrees/x06`; leave it alone.
Budget about 150k context: at the cap, commit what is complete, write where you stopped in `docs/F2_DECISIONS.md`,
and end. Logs and scripts under `/home/eajfpeters/.cache/line06/f2wo6a/` only (never a scratchpad). To wait on a job
started by `run.sh`, wait on its log line, not on `kill -0` (the PID is in another session; F2-WO5 measured this).

ADR 0062's work order 6 is split by the orchestrator (DECISION in `docs/LINE06_DECISIONS.md`): **WO6a** (this) is
the library half; **WO6b** is the application dispatch (Amendment 9 operations and run submission), the run half of
E-F2-3, the ADR 0019 Amendment 9 pointer and `interfaces-frozen.md`.

## The task

ADR 0062 (`docs/adr/0062-F2-material-model.md`) D12 (line ~268: v1-expressible criterion, the field map, refusals
`construct_unavailable(<construct>, <foundation>)`, the `property_methods.default` check against ADR 0050 D1) and D8
(line ~196: `solution-state-v2`; lowered and legacy runs keep writing `solution-state-v1` unchanged; R0 via
`run/identity.py` `r0_projection` extended for `solution-state-v2` documents only):
1. `src/openflowsheet/revision_v2/lower.py` (lowering) and `revision_v2/raise_v1.py` (raising; test and tooling only).
2. `src/openflowsheet/run/solution_state.py`: a v2 writer beside v1 (v1 writer byte-for-byte untouched).
3. `src/openflowsheet/run/identity.py`: `r0_projection` for `solution-state-v2` only (`material_layout`,
   `state_points`); v1 projection untouched.
4. Note for WO6b: the v1 reader entry is `models/revision_flowsheet.py:384 parse_revision`; its callers include
   `application/revision_binding.py:547`, `application/binding.py:995`, `application/stream_table.py:263`,
   `verify/certificate.py:444`, `studies/nlp/boundary.py:115`; schema validation of revisions is
   `application/validation.py:413 _first_schema_error`; `application/capabilities.py:274-280` refuses non-1 versions.
   Do not change these here. Write a short table of every dispatch site WO6b must touch (file:line, what it does
   with a v2 document today) into `docs/F2_DECISIONS.md` under "WO6b dispatch map".

## Facts established

- At `f4c5cd7a`: battery 5609 passed, 28 skipped, 3 xfailed, 0 failed; F0 PASS M1 50/50, M2-M5 61/61, M6 85/85,
  M7 52/52, M8 105/105, M9 42/42. These must hold (ADR 0062 D8: a lowered run is a v1 run in every artifact).
- WO4's `revision_v2/{parse,validate,canonical}.py`, `content_hash` over the normalised document (WO4-3); fixtures
  under `tests/fixtures/schemas/v2/` (`legacy_only` is the v1-expressible one). WO1-WO5 decisions in
  `docs/F2_DECISIONS.md`.

## Acceptance (report each)

1. E-F2-3, library half: every corpus v1 revision raises and lowers back to a document with the same `content_hash`
   (count them; name where the corpus list comes from); each non-expressible construct of D12's list is refused with
   the catalogued `construct_unavailable` naming it (one test per construct).
2. E-F2-10: `solution-state-v2` round-trip and schema; `solution-state-v1` bytes unchanged (M4 in F0).
3. Battery (the WO5 brief's suites plus the new tests): 0 failed after your last commit; ruff, ruff format --check,
   `mypy src` clean.
4. F0 PASS with the counts above, at your last commit.

## Stops (report rather than choose)

A v1 byte, hash, R0 or F0 count moving; the ADR contradicting the code; a construct D12 does not classify; a test
that passes only by relaxing a check.

## Report (200-300 words)

Per acceptance item: pass/fail and the numbers; DECISIONs (one line each); commits; the WO6b dispatch map's row count.
