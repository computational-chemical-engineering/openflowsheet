# v0.2 — decisions and gate runs (append-only)

Grep, don't read whole. Newest at the bottom.

## 2026-10-06 — start

- Frank switched to his TU/e account; "Go ahead according to your recommendations. For K_NH3 use the code's value";
  "You can use multiple agents at a time, but limit it to 4 max."
- R-152: K_NH₃ = the code's value (7000 cal/mol); the Rossetti 2006 check not made.
- R-153: order M01 design first, M06 alongside, `0.2.0a1` after M02.
- Web-shell design inputs (`5211ada`, `94a59ff`, README, `b876a2b` of the archive's `design/web-shell-brief`) copied as
  files onto public `main`; scanned for addresses, home paths and secrets (none; one link to a private artifact kept).

## 2026-10-06 — milestone 0

- `67029fa` ci.yml pinned by SHA (44 `uses:`; inputs checked against the new majors; test). check.sh on main
  (`67029fa`): 6879 passed, 31 skipped, PASSED.
- `d006997` T08 close-out review (all five confirmed, no must-fix) → T08 spec Amendment R8. DECISION (R8 1, the
  review's recommendation): the two 2.4 MB ensemble records committed as `.gz` beside their paths; rejected: an
  external store by hash. Reversible by reverting `d006997`.
- Stale worktrees (public-line, showcase, the CI agent's) are clean; removing them was refused by the permission
  classifier — left for Frank.
- Frank: the Claude Design web-shell design was not revised after 2026-09-29; the imported prototype is final input.

## 2026-10-06 — halt

- M06 architect done (`wp/M06` `44098b0`, `03f3f13`). Corrections from it: the project is Apache-2.0 (the brief said
  MIT); D1–D3 already fixed by T08 Phase 1; the command is `serve-http`.
- Specifier (M01) and engineer (M06 WO-4…6) both hit the account session limit, were resumed, then halted at
  Frank's request ("The task requires too many tokens. Try to get it to a save state and then halt.").
- M06 WIP `f8fa5e5` on `wp/M06-build` (untested). WO-4 partial: `resources.py` (`PACKAGED` + `web`, `REPOSITORY_PATHS`
  web→apps/web, `DIRECTORIES`), `_data/web` symlink, pyproject globs, `apps/web/index.html`, `favicon.svg`. Known
  breakage: `tests/test_t08_w4_package_data.py` (assumes packaged path = repo path). Engineer's next steps: fix that
  test via `repository_path()`; `bindings/web.py` with security headers as `/ui`-scoped middleware (not a mount
  wrapper: 404/405 would lack the CSP); `serve-http --ui` (exit 1 if web files missing); import rule in
  `tests/test_t07_w6a_http.py`; serving tests; then WO-5, WO-6. `actions/setup-node` v7.0.0 =
  `820762786026740c76f36085b0efc47a31fe5020`. Planned: G1 equality as `xfail(strict=True)` until WO-3/9/10.
- Frank (2026-10-06), M06 F2: the W27 agent campaign uses the most recent model available at campaign time ("This
  should be 5.5 (or preferably the most recent version)"), pinned by exact ID and recorded; the design note's default
  (V17 `v17-c2`'s `claude-sonnet-5`, for comparability) is overridden; the loss of direct comparability is stated.
  Development agents are unaffected (frontmatter aliases `opus`/`sonnet`/`haiku` resolve to the latest; the API saw
  `claude-opus-5-5`).
