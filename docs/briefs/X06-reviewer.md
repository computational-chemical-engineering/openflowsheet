# Reviewer brief: X06 (application capabilities), WO1 to WO5

Status: brief, 2026-11-27. Design lane, the package's single `reviewer` pass (LINE06 rules: one per package before
its merge), with the X06 ruling batch folded in. **Do not spawn sub-agents yourself.** Reading and running tests
only; no code edits. Rules: `docs/LINE06_RULES.md`.

## What to review

Branch `wp/X06` at `020b7b72`, worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06` (read and run
tests there; do not commit there). Diff: `git diff aa5822ac...020b7b72` (merge base with `main`; 117 files,
+11260/-380). Against: `docs/adr/0078-X06-application-capabilities.md` (D1 to D6, exits E-X06-1 to 24, Q1 to Q10,
and the appended section "X06 ruling round R1 applied"). Build decisions: `docs/X06_DECISIONS.md` (WO1-* to WO5-*,
R1 rulings at line ~201). Evidence: `evidence/X06/a657d29d2b6b38406fb72d901a1eee008dfa80dd/manifest.json`.
Another engineer works in `.claude/worktrees/f2`; leave it alone. Logs only under
`/home/eajfpeters/.cache/line06/x06rev/`.

## Measured (by the build lane, judged by the orchestrator)

Surface suites in one process at `a657d29d`: 3318 passed, 47 skipped, 3 xfailed, 2 failed (the two known red below).
F0 PASS (M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42) at every WO. Bundle gate: 63 bundles,
60 ok, digest `b42b1ec439d1683c` unchanged since `c526de6a`. `X06_SERVED_SHA256` = `d0f0c8b7...` = c_12's `D_12`;
`without_x06` gives F3's `f7ec3c94...`. Not run: E-X06-13's `optimize` half (no `nlp` extra on this host).
**Known red, for you:** `tests/test_t07_q26.py::test_t07_q26_no_external_state` (four members, item 1 below) and
`tests/test_t08_w2_description_reviews.py::test_every_description_is_reviewed_by_both_lanes` (11 texts, item 2).

## The ruling batch (rule on each: keep / change, with the exact change)

1. **R-088 Q26 (STOP from WO4):** `set_ambient_pressure` `value`; `grant_capability` `limits/max_wall_time_s`,
   `limits/max_active_jobs`, `limits/default_wall_time_s`. Admit by full path (precedents R-1058, R-1075: give the
   exact allowlist or scalar-pin entries and the docstring paragraph) or require another shape.
2. **Design-lane review of the 11 description texts** in `src/openflowsheet/application/bindings/descriptions/`:
   `commit_change`, `preview_change`, `create_branch`, `delete_branch`, `list_branches`, `register_solve_policy`,
   `get_solve_policy`, `get_policy`, `grant_capability`, `revoke_capability`, `set_ambient_pressure` (`.md`). Per text:
   approve, or approve with edits (give the exact edited text, at most 1500 characters). Do not edit `REVIEW.json`;
   the fix round records your verdicts at the reviewed hashes.
3. WO3b-1: a 40th pinned scalar `policy/admissibility_epsilon` (the R1 ruling counted 39); R-1075's text says so.
4. WO4b-1: `test_u08_no_operation_administers_policies` removed (D5 reverses it; WO2-9 precedent). Not a relaxed check?
5. WO4b-2: E-X06-16 shown on operator-written policy files (no committed `project-policy.json`).
6. WO1-1 (unused serve functions) and the stateless `tools/call` answered without `initialize` (line ~54).
7. WO2-4 (a commit re-assigns an auto id taken by a concurrent commit on another ref; a commit-path behaviour change)
   and WO2-7 (`commit_change.md` tightened to fit 1500 characters: no fact dropped?).
8. WO5-1: `_pin_threads` callers fixed in three tests (test isolation only; no fixture moved).
9. Found in passing (WO4): `render_error` prints explain's "no message code" text for a message without its code
   prefix; WO2 to WO4 messages carry the prefix. Is that a defect to fix now or a code-health item?

## Where to look hardest

D1 security: bearer per request, no token or `prt_` string in the store, audit, ledger, policy file or a log (E-X06-18);
the remote refusal (E-X06-19); D5's delegation rule (no escalation: a grant or revoke beyond the caller's rights or
limits). D4 identity: R1-1's `user.` bundle check (does every partial forgery still fail?), and that no registered
policy's behaviour or any F0 number moved. D2: concurrency of refs (E-X06-8) and WO2-4. Test strength: would the
tests fail if a token were logged, or if a delegation limit were ignored?

## Deliverable

`docs/reviews/X06-review.md`: verdict; findings M (must-fix) / S (should-fix) / N (notes) with file:line and a stated
fix; a ruling on each batch item; a numbered fix-round work order for the build lane (one Opus engineer). Commit on
**main** (`/home/eajfpeters/Code/OpenFlowsheet`, docs only, named path, message `LINE06: X06 review`, trailers
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_015Acof1nLKMy3Lsg6MpcJUZ`). Report at most 25 lines, including whether anything needs
the user (any ruling that changes an Accepted ADR decision does).
