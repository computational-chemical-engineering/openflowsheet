# Reviewer brief: X05 — replay from the wheel (0.4), the single review pass

Status: brief, 2026-11-07. Normative: ADR 0069 (`docs/adr/0069-X05-replay-from-the-wheel.md`, Proposed; amends ADR
0007 D4/D6), independent reference `docs/derivations/scripts/x05_reference.py` + `benchmarks/x05/reference_values.json`.
Branch `wp/X05`, worktree `.claude/worktrees/x05`, head `82030102` (base main `004d7faa`, before RP merged). Build log
`docs/X05_DECISIONS.md` (D-1…D-8), manifest `evidence/X05/42c84f1d…/manifest.json` (status `tested`, 27 pass,
4 unsupported).

## The question

Does `wp/X05` implement ADR 0069 so that an installed package records `lock_sha256` only for a verified environment —
never a false `exact_replay` — while every checkout behaviour and F0 stay unchanged; and is `tested` supported?

## What was measured (engineer's numbers)

- X05.A01–A20 (wheel side), A22 (a), A23, A24, A25 static half + local plain `pip install` (`ead4edf1…`, no findings):
  PASS. A22 (a): a clean environment outside the tree with the built wheel replays all 52 F0 bundles
  `exact_replay`/`MATCH` = M7's values (9 s).
- Unsupported (need a CI dispatch of `dist`/`clean-install`): A20's sdist byte check, A21, A22 (b), A25's CI half,
  Q-N2. **The orchestrator dispatched once: run 42391223708 at `82030102`** (in progress at brief time — read its
  outcome with `gh run view 42391223708 --json jobs`, at most every 10 minutes; GitHub's rate limit was hit today).
- F0 PASS M1–M9. Full gate at `42c84f1d` PASS 14934 passed. `x05_reference.py --check` PASS; support matrix 0 problems.
- Push CI 42372143366 failed (T08.A32 sdist data-rights test refused the packaged lock) → fixed `42c84f1d` (D-8: A32
  admits `_data/requirements.lock` by exact path, as it admits the reactor lock); 42379232642 green both legs.
- Q-F1 pins (four transitive runtime members) isolated in `a58ef5a5`; M01.A35's exact dependency list gains them (D-1).

## Rule on each

1. Correctness of D2's check against the reference: does any path record the hash without verification (R-140's
   watch item), or read a lock from outside the package/checkout? The symlink (D1) in sdist and wheel.
2. D-8 (T08.A32 admits the packaged lock by exact path) — acceptable?
3. Is `tested` supported with four checks unsupported pending the dispatch? If the dispatch is green, record how the
   manifest is re-taken; if not, what fails.
4. D-1, D-2, D-6 (`clean-install` timeout 30 → 45 min; new `f0-replay` subcommand), D-7 (register lines unnumbered,
   to be numbered above R-949 — RP now holds R-942…R-949 on main; X02 takes R-950).
5. The merge with main: `wp/X05` predates RP's merge; the RP release-procedure step-4 line (`a19.*` → `x05.*`) is
   now due — say what the fix round must change in RP's text/line files.

## Deliverable

`docs/reviews/X05-review.md`: verdict, must-fix, should-fix, one ruling per item, what the review did not establish.
Commit on **main** (docs-only, named path, message `docs: X05 review`, the session's Co-Authored-By / Claude-Session
lines). Do not edit `wp/X05`. Never set `reviewed`. Report ≤ 30 lines.

## Machine-load rule

TRS2 (the user's): whole machine ≤ ~36 busy cores of 48; `uptime` first; targeted tests only, one at a time; no full
gate (X02's engineer runs one).

## Out of scope

X02, MSG, ST; F8's data locks; style.
