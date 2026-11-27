# LINE06 F8 close-out (ADR 0067 WO1 to WO3 and WO5 for the 0.6 line)

Build lane, `sonnet-implementer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f8`, branch `wp/F8`, head `a4b0ede1` (clean; WO1 to WO3, WO5
and its review done and judged). Logs under `/home/eajfpeters/.cache/line06/f8-co/` only. Tests:
`PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=src`. Log every choice in `docs/F8_DECISIONS.md`
as `DECISION F8-CO-<n>`. Read-only references in `.claude/worktrees/f2` (never edit there). Budget about 100k.

## The task (three items, one commit each; no change under `src/` or `tests/`)

1. **ADR 0019 Amendment 12 pointer paragraph** (left over since WO1b, `docs/F8_DECISIONS.md` l.153 and l.298). Add
   `## Amendment 12 (Proposed 2026-11-27; F8) — pointer to ADR 0067` to `docs/adr/0019-*.md`, in numeric order
   among the existing amendments, in the style of Amendment 13 (same file) and of F2's Amendment 9
   (`.claude/worktrees/f2/docs/adr/0019-*.md` line 286, read-only). Content: one line "decided in ADR 0067 D2, D5";
   bullets for what changed in ADR 0019 D1's surface as built: `ReplayReport` optional members
   `registry_comparison`, `data_availability` (and `forced_replay` reserved, refused `construct_unavailable(forced_replay,
   TX)` until WO7), `ReplayMode` value `forced_replay` refused in `ReplayReport.__post_init__` (DECISION F8-WO3-9); the
   schemas touched by WO1/WO1b (`replay-report`, `run-manifest`, `records-index`, `run-evidence`; read
   `git log --stat 4c7d3d6a..a4b0ede1 -- schemas/` to list them exactly); the new catalogue codes built in this line
   (`catalogue/replay.yaml`: read it) ; "Unchanged": every v1 manifest, bundle and replay report (E-F8-1, E-F8-10).
   State every fact from the code or the decisions file, not from memory.
2. **Evidence manifest** `evidence/F8/<full head sha after item 1>/manifest.json`, `status: tested`, in the field set of
   `.claude/worktrees/f2/evidence/F2/fb75c409d6aa4ef171b1dfa9a2572836ccf27f28/manifest.json` (read-only; copy its
   field set). One row per exit in this line's scope: E-F8-1, -2, -3, -4, -5, -6, -8, -10, naming the test files and
   test ids that carry each (`grep -n "E-F8-" tests/`, and the gate entries in `docs/F8_DECISIONS.md`). E-F8-7 (WO4,
   0.7) and E-F8-9 (WO7, TX) as rows with status `not_in_scope` and the reason (ADR 0067 line note, R-1070). Every
   command in it must be one you ran at the head the manifest names, with its real pass count. No angle-bracket
   values; never `reviewed`.
3. **Gate:** `tests/test_f8_*.py`, `tests/test_k05_replay.py`, `tests/test_x07a_*.py`, `tests/test_t07_w5e_*.py`,
   `tests/test_msg_*.py`, `tests/test_doc_pages.py`, and every test that reads ADR or evidence files
   (`grep -ln "evidence/\|docs/adr" tests/*.py`, run those); then F0:
   `python scripts/corpus_identity.py --check --log ~/.cache/line06/f8-co/f0-detail.log` (must print `F0 PASS`, M1
   50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42). ruff format --check clean.

## Acceptance (judged on these alone)

Items 1 and 2 committed (named paths only, never `git add -A`; do not push); the gate passes; F0 PASS; the manifest
holds only commands you ran at its head with their counts. No background job of yours running when you report.
Report in 200-300 words: commits, test counts per file, the F0 line, the manifest path, anything left over.
