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
