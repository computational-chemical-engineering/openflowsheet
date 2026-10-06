# v0.2 — campaign state

Position, not history. Rewritten in place. Read after `CLAUDE.md` and `docs/progress.md`. History:
`docs/V02_DECISIONS.md` (append-only).

| | |
| --- | --- |
| Objective | Plan v1.2 §4.4: M01–M07, the scientific reactor replacement; release gate W21–W27; release `0.2.0` |
| Chemistry | C1, the ammonia synthesis loop (ADR 0022, R-120); `docs/v02-real-chemistry-dossier.md`; reactor `ammonia_synthesis_reactor` `main` @ `6089593` (MIT) |
| Order | R-153: M01 design first; M06 built alongside; M03 when the critical path allows; pre-release `0.2.0a1` after M02 `tested`; `0.2.0` after M07 |
| Concurrency | At most 4 agents at a time (Frank, 2026-10-06) |
| Repository | Public `origin` only (R-150); pre-push guard installed; pushes to `origin` with Frank's OK |

## Packages

| ID | Lead | Depends | Gate | Status |
| --- | --- | --- | --- | --- |
| M01 | Design | T08 | W22, W21 (part) | `specifier` writing `docs/derivations/M01-spec.md` on `wp/M01` (brief `docs/briefs/M01-specification.md`; ADR 0026+, R-154+) |
| M02 | Build | M01 | W21 | not started |
| M03 | Design | T08 | W24 (part) | not started |
| M04 | Design | M02 | W23 | not started |
| M05 | Design | M03, M04 | W24 | not started |
| M06 | Build | T08 | W26, W27 | `architect` writing `docs/design/M06-web-shell.md` on `wp/M06` (brief `docs/briefs/M06-design.md`; ADR 0030+, R-170+ to avoid collisions) |
| M07 | Design | M05, M06 | W25, W21–W27 | not started |

## Milestone 0 (housekeeping)

- [x] Web-shell design inputs ported from `design/web-shell-brief` (pre-0.1.0 base, cannot be pushed) onto `main`
- [x] Frank's K_NH₃ decision (R-152), the order (R-153), the dossier statement
- [x] `ci.yml` actions pinned by SHA (`67029fa`; 44 lines; inputs checked against the new majors; test added)
- [x] T08 close-out review (`docs/reviews/T08-closeout-review.md`): all five confirmed, no must-fix; F1/F2/N1/N2/N5 applied as T08 spec Amendment R8
- [ ] **F3 hand-on:** T08's own manifest (58 limitations, 16 without L/U id; A70, B23) is an input to v0.2's support-envelope harvest
- [ ] Schema `$id` move (deferred to v0.2 by ADR; R-149) — with M01's or M06's first schema change

## Open inputs (M01, dossier `needs_fact`)

PR parameter set (T_c, P_c, ω, c_p, ΔH_f per value from open, cited sources: `chemicals`/`thermo`, cross-checked
with CoolProp or Cantera; group database a cross-check only); a cited k_ij source; high-pressure NH₃–H₂–N₂ VLE data;
the loop's pressure-drop convention (ADR 0022 D2); whether the reactor keeps its own fugacity correlations or takes
PR's. K_NH₃ settled (R-152: the code's 7000 cal/mol).

## Next action

Wait for the specifier (M01), the architect (M06) and the close-out reviewer; then the session reviews each, commits, and plans M01's build. Stale worktrees `.claude/worktrees/{public-line,showcase,agent-a3fc35fa5df8ef915}` are clean; removal needs Frank (permission).
