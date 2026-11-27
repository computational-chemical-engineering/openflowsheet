# LINE06 X06-WO4b: finish in-band administration (ADR 0078 D5), continuing X06-WO4

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. The task, facts,
acceptance, stops and report form are those of `docs/briefs/LINE06-X06-WO4.md` (read it); this order finishes it.
Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06`, branch `wp/X06`, head `ac15a44a` (clean).
Another engineer works on F2 in `.claude/worktrees/f2`; leave it alone. Budget about 150k context.

## Where to start

`docs/X06_DECISIONS.md`, section "Where WO4 stopped (next engineer: start here)" (line ~416), and decisions WO4-1 to
WO4-7 above it. WO4 committed the code (`a84e9b14`) and the CLI audit fixture (`a9038f7b`). Open, in its order: the
`test_t07_w5e_application_results` `$defs`, snapshot and fixtures (3 failing); the served-digest re-pin
(`X06_SERVED_SHA256`, `without_x06`, m07a_rc link c_12's `D_12`), the support envelope; conformance on six clients;
`tests/test_x06_administration.py` with E-X06-16 to E-X06-21 (including a test that CLI audit rows equal the
`4ca7ce3c` fixture); then the full surface suites, `test_x06_*`, MSG and doc-page tests, the bundle gate and F0.

## Standing STOP (do not resolve)

R-088 Q26 findings from WO4: `grant_capability` `limits/default_wall_time_s`, `limits/max_wall_time_s`,
`limits/max_active_jobs`, and `set_ambient_pressure` `value`. Leave them unpinned; `test_t07_q26.py` stays red on
exactly these (report the test's printed findings verbatim). Any further Q26 finding is a new STOP item.

## Also

WO4's description texts `get_policy.md`, `grant_capability.md`, `revoke_capability.md`, `set_ambient_pressure.md`:
leave unreviewed, list them. Report in 200-300 words per the WO4 brief.
