# One W27 question before the first canary — design lane (`specifier`), short pass

Branch `wp/M07-w27` @ `1219636` (pushed), worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m07-w27`.
Registration `docs/derivations/M06-W27-registration.md` §23 (Amendment 4, R-467…471; R-471: the pinning attempt runs
without `--model`; P6 11 states, P7 6 states), W27-A23 (l.709: `run.json` carries … model id, effort, Claude Code version …),
scorer `pin_mismatch(model)`; M07 spec M07.A51. Build log `docs/design/M07-build-decisions.md` entry WO-17a.

## The question
How does a canary attempt run without `--model` record its model, so that the scorer, A23, P6/P7 and M07.A51 agree?

## What the engineer did (`b71d86c`, isolated hunk `_unpinned`)
For an unpinned attempt, `run.json#/model` stays null and the `init` message's model is recorded as
`run.json#/pinned/model`. Without that, the unchanged scorer check `pin_mismatch(model)` fails every unpinned canary,
contradicting the registered P6/P7 states. Consequence found: A23 requires a non-empty `model`, so A23 cannot hold for an
unpinned attempt (affects M07.A51, which reads A23 over the campaign's records). Also: the registration has no value for K
in A76's fixture; the test uses `"f"*40`.

## Deliverable
Rule (accept the engineer's form with A23/A51 restated for unpinned attempts, or e.g. record the observed id in `model` with
a separate `requested_model: null`), register entry (next free above R-471 unused on `origin/main`, `origin/wp/M07`, here),
the restated assertion text, and the exact build change if any. Amendment 4 addendum, dated, before any W27 run. Docs and
generator only (+ regenerate `registration.json` and P2 pins if its members change). Commit, push. ≤ 120-word report.
Keep context under ~60k.
