# Design-lane ruling (small, before WO-8): M05 S40, `fd_check` floats, R-003 vs application jobs

`wp/M05` @ a5927b4 (worktree `.claude/worktrees/m05`). Design note `docs/design/M05-trust-region.md` (rulings §16–§18,
WO table l.806–830, WO-8 l.821); numerical-policy addendum (M05's ADDENDA in `docs/derivations/scripts/t08_numerical_policy.py`
or the addendum file it reads — grep `coupling_record_sha256`); build log `docs/design/M05-build-decisions.md` (S40 l.349,
the `fd_check` float gap l.375, S44 l.~410–425). WO-8 commits records; these three questions decide whether those records
pass the float-classification and replay-identity tests, so they are ruled now, not in the end-of-package review.

1. **S40.** `ParentSolve.as_document` adds `coupling_record_sha256`; the engineer classified it `exact_sha256`. Measured:
   two runs of the same tree give different coupling-record hashes (6 + 1 values in the S44 dump) because the coupling
   records carry wall times; all other fields are identical. Decide the classification (exact / identity-excluded /
   hash of a wall-time-free projection), and what replay identity of an M05 record means for it.
2. **`fd_check` floats** (`w0`, `selected_eta`, `candidates[].*`, `half_steps`): no float rule covers them, so a committed
   record carrying `fd_check` fails `test_every_float_of_every_record_is_classified`. Give each its class under the
   M05 numerical-policy addendum (S11's scheme).
3. **R-003 vs jobs.** `tests/test_m05_isolation.py:91` (`test_no_route_or_compile_path_reaches_the_projection`, R-003,
   R-261) forbids any module outside `studies/trust_region/` from importing the projection; S44 therefore injects
   application services into `C1Parent` instead of moving it. Consequence found: no `application` job can run the
   trust-region study. Does WO-8 or M07 (journey R3, `docs/derivations/M07-spec.md` on `wp/M07`, J8) need a job entry?
   If yes, say how it may be reached without breaking R-003's intent (no second model/backend).

Rules: rule, don't code. Write a short **§19** of the design note and register entries **R-383…R-389**
(`docs/decision-register.md`). Commit on wp/M05, named paths, trailer
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` / `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`,
push. Report ≤ 200 words: one line per ruling and the build action.
