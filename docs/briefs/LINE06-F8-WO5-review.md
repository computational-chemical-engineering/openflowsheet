# LINE06 F8-WO5 Opus review (ADR 0067 build table row 5: "Sonnet, Opus review")

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f8`, branch `wp/F8`, head `dcf4b89f`. Logs under
`/home/eajfpeters/.cache/line06/f8-wo5r/` only. Tests: `PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH
PYTHONPATH=src`. Budget about 100k.

## The task

Review `git diff 369150d3..dcf4b89f` (Sonnet's F8-WO5: `src/openflowsheet/run/platform_refs.py`,
`tests/test_f8_platform_refs.py`, the `platform_reference_used` catalogue entry, the digest re-pin) against the brief
`docs/briefs/LINE06-F8-WO5.md` (on main) and ADR 0067 D7 as amended (`docs/adr/0067-F8-identity-replay-evidence.md`
line ~152) and E-F8-8. Then fix what you find, as commits on wp/F8 (named paths; log `DECISION F8-WO5-R<n>` in
`docs/F8_DECISIONS.md`). Do not change the v1/v2 replay path; a served-digest move is a STOP.

Check in particular:
1. Does each test actually test what its exit name says (a test that passes for the wrong reason is a must-fix)?
   Are the refusals of brief spec 4 complete, and is the ratio formula checked?
2. DECISION F8-WO5-4: "a solver counter change did not move R0 for GP-C1". ADR 0007 D1 lists `residual_calls`,
   `jacobian_calls`, `factorizations` as R0. Establish with a measurement whether `run/identity.py` `r0_projection`
   (l.65, `_solver_counters`) omits a counter it should carry, or whether the engineer changed a counter the projection
   rightly ignores (for example not the last event's). If `r0_projection` is wrong, do NOT fix it (it is replay
   identity): record the measured facts as `FINDING F8-WO5-R<n>` for the design lane and say so in the report.
3. DECISION F8-WO5-3 (tests under `V1_POLICY_ID`): is a v2-policy case reachable with `variable_kinds` from the
   factory bundle? If cheaply, add one; else state why not.
4. `platform_refs.py` quality: `registered_platform_ids()` derived from `REGISTERED_PLATFORMS`, not copied; the
   self-hash uses `canonical_json`; no dead code.

## Acceptance

`tests/test_f8_platform_refs.py` and `tests/test_f8_*.py`, `tests/test_x07a_*.py`, `tests/test_t07_w5e_*` pass;
ruff, ruff format --check, mypy src clean; F0 PASS if you changed anything under `src/`. Commit named paths only; do
not push; no background job of yours running when you report. Report in 200-300 words: findings by severity (must-fix
/ should-fix / note), what you fixed (commits), the answer to point 2 with the numbers, anything left for the F8
reviewer pass.
