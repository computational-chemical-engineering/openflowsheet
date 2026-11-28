# LINE06-R-REV: RP §13 (3) reviewer pass on the 0.6 release machinery (reviewer, once)

Do not spawn sub-agents yourself. Budget about 150k context. Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/rel060` (branch `wp/REL060`, HEAD 2b42556e). Read-only except
your review file: write `docs/reviews/REL060-machinery.md` (precedent: `docs/reviews/REL050-R-machinery.md`), commit
it (named path), do not push. Report 200 to 300 words: must-fix / should-fix / note counts and each must-fix in one line.

## What to review

The release machinery changed for 0.6 (`git diff 43f0b7f5..2b42556e -- scripts tests release`):
1. `scripts/release_rc.py` subcommand `junit-cases` (rc item `F2-THREE-OS`), `tests/test_rel_junit_cases.py`;
   specification `docs/briefs/REL060-line-0.6.md` D-3, checks TO-1 to TO-6.
2. `scripts/wheel_data_check.py --f2` (rc item `WHEEL-F2`), `tests/test_rel_wheel_f2.py`; specification D-5, WV-1 to
   WV-6; the engineer's readings R-WV-1 to R-WV-4 in `docs/REL060_DECISIONS.md`.
3. `release/lines/0.6.json` against the note (LINE06-L1, commit 8046530e): that each rc item's argv runs the code as
   built (argument names, case ids, leg names equal to the CI artifact names in `.github/workflows/ci.yml` ~line 199).

The questions: does each check verify what its specification says, or can it pass while the clause it guards is
false (a vacuous match, a skipped comparison, a digest of the wrong bytes, a self-generated expectation)? Do the
controls fail for the stated reason? Are exit codes 0/1/2 as specified? Is anything outside the two scripts touched?

## Facts established

- Tests: `tests/test_rel*.py` 332 passed at 2b42556e (orchestrator run). R-WV real run at bb4ee987: `wheel data check
  (F2): PASS`, r0 equal to F0's registered M3 `414fba51...` (g8/SYN-001-T06-NET02) and `6e6ab158...` (s11-gp/GP-C1),
  checked by the orchestrator in `benchmarks/f0/corpus.json`. R-TO live read of F2's push run 46041020889 through
  `junit_cases_checks` with a synthetic step-1 record (run id only): 57 cases per leg on x86_64, aarch64,
  Windows-X64, macOS-ARM64, all passed, set digest `0afd81d3...` equal; the step-1 hash comparison of TO-2 was not
  exercised live (fixture test only), and is skipped on legs step 1 did not record (Windows, macOS).
- R-TO's strict readings: TO-1 accepts `status == completed` without requiring `conclusion == success` (as specified);
  duplicates kept; every leg required for `same_set`.
- Not your question: F8's merge (CI running), the claim set (L1 settled it, no change).
