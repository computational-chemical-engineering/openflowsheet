# LINE06 F2-WO6b: v2 dispatch in the application, run submission (ADR 0062 work order 6, second half)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f2`, branch `wp/F2`, head `f9a415f1` (clean; WO1 to WO6a done).
A design-lane agent (F2-R1) may commit to `docs/F2_DECISIONS.md` on this branch while you work: commit named paths
only, never reset, and if a commit of yours conflicts on that file, rebase-free: re-apply your edit on top. Logs and
scripts under `/home/eajfpeters/.cache/line06/f2wo6b/` only; wait on log lines, not `kill -0`. Budget about 150k:
at the cap, commit what is complete, write where you stopped in `docs/F2_DECISIONS.md`, and end.

## The task

ADR 0062 D12 (line ~268) Amendment 9 and D8 (line ~196), by the **WO6b dispatch map** in `docs/F2_DECISIONS.md`
(~line 424, 14 rows, measured by WO6a): `parse_revision` dispatch on `schema_version` (v1 reader untouched); the six
readers read the lowered document; v2 schema and `revision_v2.validate` in `validation`; `check_admission` admits 2
with F2's checks as notices/refusals; `commit_change`, `preview_change`, `diff_revisions` accept v2 (`ChangeSet`
paths unchanged); `content_hash` = `revision_v2.content_hash` for v2; run submission of v2 (`revision_run`);
`verify_bundle` dispatches on the solution-state version; `LegacyProviders` built in the application (WO6a-1). Then
the ADR 0019 section "Amendment 9 (Proposed; F2) — pointer to ADR 0062" in the form of Amendment 17, and the
`docs/interfaces-frozen.md` paragraph for F2 (D2 types, the v2 schemas, Amendment 9; facts only from the ADR and
`docs/F2_DECISIONS.md`).

Open design questions (F2-R1, running beside you): WO6a-2's lowering criterion and WO6a-3's refused fields. Build on
the current code (`6f81897e`, `90f46174`); a ruling that changes them comes as a later fix.

## Facts established

At `7ce12c23`: battery 5,737 passed, 28 skipped, 3 xfailed, 0 failed; F0 PASS M1 50/50, M2-M5 61/61, M6 85/85,
M7 52/52, M8 105/105, M9 42/42. E-F2-3 library half 59/59. D8: a lowered run is a v1 run in every artifact except the
run manifest's revision reference (v2 `revision_id` and `content_hash`). The served MCP tool list: if an input schema
or description moves, re-pin as F3 did and record the digest (R-1072, chain link c_11); a moved description text
needs both reviews (list it; never mark a review).

## Acceptance (report each)

1. E-F2-3 run half: every corpus v1 revision, raised to v2 and submitted as a run through Amendment 9, gives
   `r0_sha256` and `state_sha256` equal to the corpus run's and a byte-identical `solution-state.json`; the manifest's
   revision reference is the v2 one. Count the runs (say which subset, if not all 59, and why).
2. Each of the 14 map rows: done, with its test.
3. Battery (the WO5 brief's suites plus new tests): 0 failed after your last commit (except a description-review
   gate you name); ruff, ruff format --check, `mypy src` clean.
4. F0 PASS with the counts above.

## Stops

A v1 byte, hash, R0 or F0 count moving; a lowered run's artifact differing from its v1 run's (other than the manifest
reference); the ADR contradicting the code; a test passing only by relaxing a check.

## Report (200-300 words)

Per acceptance item: pass/fail and numbers; DECISIONs; commits; served digest if moved; anything for WO7.
