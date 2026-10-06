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
| M01 | Design | T08 | W22, W21 (part) | **halted for budget 2026-10-06**: no specification written yet; only an exploratory reactor probe `b25c7e2` on `wp/M01` (`benchmarks/m01/`). Resume: a fresh `specifier` with `docs/briefs/M01-specification.md`, on `wp/M01` |
| M02 | Build | M01 | W21 | not started |
| M03 | Design | T08 | W24 (part) | not started |
| M04 | Design | M02 | W23 | not started |
| M05 | Design | M03, M04 | W24 | not started |
| M06 | Build | T08 | W26, W27 | design done on `wp/M06` (`44098b0`, `03f3f13`: `docs/design/M06-web-shell.md`, ADR 0030 + ADR 0019 Amendment 3 Proposed, R-170…R-175). **WO-4…6 halted for budget**: untested WIP `f8fa5e5` on `wp/M06-build` (WO-4 partial, WO-5/6 not started; next steps in `docs/V02_DECISIONS.md`, "halt") (worktree `.claude/worktrees/agent-af89210400852f3dd`). Resume: opus-engineer on WO-4…6 from that branch; WO-1…3 wait for Frank's approval of Amendment 3 |
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

## Needs Frank

- Approve ADR 0019 Amendment 3 (additive contract widening: structure index + unroutable analysis, element-level `diff_revisions`, `list_audit`); default: build it on the branch, merge only after approval.
- M06 F1 W27 spend [45 runs at M07, USD 15–45]; F2 agent model [`v17-c2` config]; F3 fonts [system]; F4 scenario = run comparison [yes]; F5 education mode [deferred].

## Next action

**Halted 2026-10-06 at Frank's request (token budget).** Resume only when Frank says so (he plans to continue on his Max x20 account once its budget resets). Then: (1) check that the
two halt commits landed (`git log -1 wp/M01`, `git log -1 wp/M06-build`); if not, commit the worktrees' files as WIP;
(2) M01: a fresh `specifier` (the old agent's context is large) with the brief and the WIP note; (3) M06: WO-4…6 on
`wp/M06-build`, then check.sh. At most 4 agents. Nothing is pushed: `main` is ahead of `origin/main` by local
commits (`git log origin/main..main`); pushing needs Frank's OK. Stale clean worktrees for Frank to remove:
`.claude/worktrees/{public-line,showcase,agent-a3fc35fa5df8ef915,agent-a0e7122a21d569dd7}`.
