# LINE06 X06-WO5: close-out (ADR 0078 work order 5)

Build lane, `sonnet-implementer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it
first). Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06`, branch `wp/X06`, head `af8a6c32`
(clean; WO1 to WO4b done). Another engineer works on F2 in `.claude/worktrees/f2`; leave it alone. Logs and scripts
under `/home/eajfpeters/.cache/line06/x06wo5/` only. To wait on a job started by `run.sh`, wait on its log line.
Budget about 150k context. Write no production code under `src/` (item 7 is test/script code only).

## The task (ADR 0078 `docs/adr/0078-X06-application-capabilities.md`, work-order row 5, line ~392)

1. `docs/interfaces-frozen.md`: one paragraph for X06 in the form of the X04 paragraph (line ~104): what is additive
   (D1 MCP over streamable HTTP; D2 branches; D4 project solve policies; D5 in-band administration), the new
   operations, the new optional schema members and `$defs`, the new catalogue codes (ADR "New catalogue codes",
   line ~377), the served digest `X06_SERVED_SHA256` = `d0f0c8b7…` (take the full value from
   `tests/test_t08_w2_surface_digest.py`), chain link c_12 (R-1073), `without_x06` giving F3's `f7ec3c94…`, the store
   schema id unchanged, F0 unchanged. Facts only from the ADR and `docs/X06_DECISIONS.md`; no claim you cannot point to.
2. ADR 0019 (`docs/adr/0019-*.md`): a section "Amendment 18 (Proposed; X06) — pointer to ADR 0078" in the form of
   Amendment 17 (line ~330), status words "Proposed" (the orchestrator sets Accepted at the merge card).
3. User guide `docs-site/guide/interfaces.md` (add sections; follow the page's style): MCP over HTTP client
   configuration with the bearer header (`serve-http`, its warning); branches and promotion; project solve policies
   (`register_solve_policy`, `get_solve_policy`, the `user.` prefix, immutability); the administration switch
   `openflowsheet project administration on|off`, its default off, and the refusal on a non-loopback server; D3's
   sentence (job resume deferred to F7 D14, 0.8). Then run the doc-page check (`python scripts/doc_pages.py --check`
   or as `tests/test_doc_pages*.py` does) and fix only what your text broke.
4. `CHANGELOG.md` under "## Unreleased": an X06 entry (Added: the four capabilities; one line each).
5. `evidence/X06/<head commit>/manifest.json` in the form of `evidence/F3/*/manifest.json`: status `tested`, the
   commands actually run with their results, and these honest entries: E-X06-13's `optimize` half `not run` (no
   `nlp` extra on this host); `test_t07_q26_no_external_state` **failing** on four members pending a design-lane
   ruling (`set_ambient_pressure` `value`; `grant_capability` `limits/max_wall_time_s`, `limits/max_active_jobs`,
   `limits/default_wall_time_s`); `test_every_description_is_reviewed_by_both_lanes` **failing** by design (11 texts,
   22 open reviews) until the reviews are recorded. Never an angle-bracket placeholder as a value. Validate it the
   way the F3 manifest was validated (grep `docs/F3_DECISIONS.md` for "manifest").
6. E-X06-23: show the store schema id is still `t07-store-v1`, and list `git diff --stat main...HEAD -- schemas/`
   in `docs/X06_DECISIONS.md`, each changed schema file with the ADR member or `$def` that justifies it; any file
   without one is a STOP. E-X06-24: the catalogue check test (ADR 0058 C3) passes.
7. Test isolation fix: `scripts/t07_schema_fixtures.py:182` `_pin_threads` leaves thread pins in `os.environ`, so
   `tests/test_x06_solve_policies.py::test_q7_a_lowered_budget_run_verifies_and_reproduces` fails when it runs after
   the w5e fixtures test in one process (it replays `exact_replay` instead of `compatible_reproduction`). Make the
   caller in the w5e test restore `os.environ` afterwards (pytest `monkeypatch` or save/restore), without changing
   any generated fixture byte. Check: `pytest tests/test_t07_w5e_application_results.py
   tests/test_x06_solve_policies.py` in one process: 0 failed; `git status` shows no fixture changed.

## Acceptance (report each)

1. Items 1 to 7 done; the manifest validates.
2. Surface suites (`tests/test_x06_*.py`, `tests/test_t07_*.py`, `tests/test_t08_w2_*.py`,
   `tests/test_m07a_surface_chain.py`, `tests/test_msg_*.py`, doc-page tests) in **one** process after your last
   commit: failures exactly the two named in item 5, nothing else.
3. F0 (`scripts/corpus_identity.py --check`) PASS: M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42.
4. ruff check, ruff format --check clean.

## Stops

A schema file without a justifying ADR member; any src change needed; F0 moving; a test that passes only by
relaxing a check.

## How and report

Commit named paths on wp/X06, messages `X06-WO5: ...`; DECISIONs in `docs/X06_DECISIONS.md`. Long runs through
`/home/eajfpeters/Code/OpenFlowsheet/.claude/skills/line06/run.sh <name> <command>`. No push. Report in 200-300
words: per item done or not, the numbers, commits.
