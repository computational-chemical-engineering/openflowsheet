# v0.2 — campaign state

Position, not history. Rewritten in place. Read after `CLAUDE.md` and `docs/progress.md`. History:
`docs/V02_DECISIONS.md` (append-only).

| | |
| --- | --- |
| Objective | Plan v1.2 §4.4: M01–M07, the scientific reactor replacement; release gate W21–W27; release `0.2.0` |
| Chemistry | C1, the ammonia synthesis loop (ADR 0022, R-120); `docs/v02-real-chemistry-dossier.md`; reactor `ammonia_synthesis_reactor` `main` @ `6089593` (MIT) |
| Order | R-153: M01 design first; M06 built alongside; M03 when the critical path allows; pre-release `0.2.0a1` after M02 `tested`; `0.2.0` after M07 |
| Concurrency | At most 4 agents at a time (Frank, 2026-10-06) |
| Repository | Public `origin` only (R-150); pre-push guard installed; pushing to `origin` authorised (Frank, 2026-10-08) |

## Packages

| ID | Lead | Depends | Gate | Status |
| --- | --- | --- | --- | --- |
| M01 | Design | T08 | W22, W21 (part) | **resumed 2026-10-08** (specifier running). Was halted 2026-10-06: no specification yet; WIP note `docs/derivations/M01-spec-WIP.md` (`daea823` on `wp/M01`: measured findings, tentative decisions, where to resume — incl. a dossier §6 error: the reactor uses ideal-gas density). Resume: a fresh `specifier` with the brief and that WIP note, on `wp/M01` |
| M02 | Build | M01 | W21 | not started |
| M03 | Design | T08 | W24 (part) | spec done on `wp/M03` (`17cec07`: A01–A42, ADR 0031/0032, R-180…191); build WO-0…3 running; WO-6 [A10] Ipopt audit next; N1 licences asked of Frank |
| M04 | Design | M02 | W23 | not started |
| M05 | Design | M03, M04 | W24 | not started |
| M06 | Build | T08 | W26, W27 | design done on `wp/M06` (`44098b0`, `03f3f13`: `docs/design/M06-web-shell.md`, ADR 0030 + ADR 0019 Amendment 3 Proposed, R-170…R-175). **WO-4…6 halted for budget**: untested WIP `f8fa5e5` on `wp/M06-build` (WO-4 partial, WO-5/6 not started; next steps in `docs/V02_DECISIONS.md`, "halt") (worktree `.claude/worktrees/agent-af89210400852f3dd`). Resume: opus-engineer on WO-4…6 from that branch; WO-1…3 on `wp/M06-contract` (Amendment 3 approved 2026-10-08) |
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

- **M03 N1:** accept the licences of an optional, non-default `nlp` extra (cyipopt + Ipopt + PyNumero ASL: EPL-2.0,
  CeCILL-C, the ASL notice, Apache-2.0 METIS 5, BSD, GCC runtime), once the [A10] audit lists exactly what is loaded.
  Default: accept for the optional extra; without it W24's M03 optimizer part stays BLOCKED.

Otherwise nothing open. Answered 2026-10-08: Amendment 3 approved; W27 spend (45 runs, USD 15–45) approved; pushing to
`origin` authorised. Earlier: F2 agent model = most recent, pinned by ID; F3 fonts system; F4 scenario = run comparison;
F5 education mode deferred.

## Next action

**Resumed 2026-10-08 (Frank: "start working to get to v0.2.0", max 4 agents).** Running: `specifier` M01 on `wp/M01`
(worktree `.claude/worktrees/agent-a94d84cd26a293bc0`); M06 WO-4…6 **done** on `wp/M06-build` (`5d0261a`, gate green);
M06 WO-14 **done** on `wp/M06-w27` (`e268ed8`); `specifier` M06 WO-15 on `wp/M06-w27` (worktree `m06-w27`); M06 WO-1…3 **done** on `wp/M06-contract` and merged into `wp/M06-build` (R-192, R-193);
`opus-engineer` M03 WO-6 Ipopt audit on `wp/M03-audit` (worktree `m03-audit`); `opus-engineer` M03 WO-0…3 on `wp/M03` (worktree `m03`). Next free slot: M01 build if its spec is done (critical path), else M06 WO-7 (fixtures) → WO-8…12 on
`wp/M06-build`.
In worktrees run the gate with `PYTHONPATH=$PWD/src PATH=<main>/.venv/bin:$PATH ./scripts/check.sh`. Push `main` at milestones (authorised).
