# X07a-WO4: macOS rows, the manifest move, and the Windows leg

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x07a`, branch `wp/X07a`,
head 2d914b7d. Work only there. Do not spawn sub-agents yourself. Budget about 150k tokens of context: at the cap,
commit what is complete, rewrite the Position section of `docs/X07a_DECISIONS.md`, and end.

Authorization, push rules and the scientific-conduct limits are those of `docs/briefs/X07a-WO1.md` (read its "Scope",
"Stop and report instead of choosing" and "Acceptance"); they bind unchanged. Never push, merge into or rebase
`main`; never tag. You may push `wp/X07a` to run CI.

## The spec

Unchanged from WO3: `docs/X07a-platform-ruling.md` sections 4 (R1, R2, rules P1 to P5), 5.1 and 6 (C1 to C6, A1 to
A12, stop conditions). Read `docs/X07a_DECISIONS.md` first, its Position section above all: it is where WO3 stopped.
Do not reopen D-1 to D-22, Q-1 to Q-10, or the open reviewer items (D-20, D-22/Q-4, Q-10): they wait for the
design-lane reviewer round. Amendment 3 stays proposed; `REGISTERED_PLATFORMS` stays unchanged.

## Order

1. **macOS rows.** The six Q-3 candidates named in Position (`test_m02_schemas.py::test_g1a_*` standin_loop.json,
   `test_t05b_candidate_answers.py::test_b34a`, `test_t06_w30_holdout.py` and `test_t06_w6_a85.py`
   `test_a85b[NET-02/03]`, `test_m01_provider.py::test_f2[10025791.149338447]`, `test_m02_wo10_coupled.py::test_rp2b`):
   classify each under P1 to P5 and give each one platform-limit row with its run id, or fix it if it is a
   portability bug (Linux bitwise unchanged, F0 PASS). Then the three other-class failures
   (`test_t07_w7a_harness.py::test_token_placement`, `test_v02a_r347`, `test_p03_a30_workload.py::test_s9_5`): bug
   (fix) or limit (row). L5 is untested on the leg: confirm it from run 44681408041 (head 2d914b7d, running at
   briefing).
2. **The manifest move** (A11 second bullet): limitations naming Amendment 3 as proposed and the two unregistered
   platforms; the T08 harvest rows it needs (`scripts/t08_support_matrix.py --check` gives their sha256); A6's logged
   `lock_sha256` per leg.
3. **Windows.** Read the windows-latest leg of 44670029066 (head 9773c361, still running at briefing) and of
   44681408041. Continue WO2's classification: path separators, CRLF, WinError 32, signal 2, the
   `test_m02_experiments.py` child ending `environment_unavailable`, then X02 external, V17 reference, M05 host keys.
   Portability bug (fix, Linux bitwise unchanged) or platform limit (row with run id). Same rules as WO2.
4. The `codehealth` CI job failed on 44670029066: read why. If it is a finding on this branch's code, fix it; if it is
   the job itself, record it in `docs/X07a_DECISIONS.md` and leave it.

Each fix is its own commit naming X07a. Run the tests a change touches and F0 (`scripts/corpus_identity.py --check`)
locally before pushing; read CI with `gh run view --log-failed`, never whole logs.

## Report (200 to 300 words)

Commits; per macOS item its class and row or fix; manifest state; Windows: failed count per run and what is left with
its class; the codehealth job; any stop condition hit. Detail goes into `docs/X07a_DECISIONS.md`, not the report.
