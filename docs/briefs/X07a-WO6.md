# X07a-WO6: the Windows-only pywin32 lock (Frank's ruling) and the Windows remainder

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x07a`, branch `wp/X07a`,
head as you find it (WO5 left 58bdd149 plus this brief). Work only there. Do not spawn sub-agents yourself. Budget
about 150k tokens of context: at the cap, commit what is complete, rewrite the Position section of
`docs/X07a_DECISIONS.md`, push, and end.

Authorization, push rules and the scientific-conduct limits are those of `docs/briefs/X07a-WO1.md` (read its "Scope",
"Stop and report instead of choosing" and "Acceptance"); they bind unchanged. Never push, merge into or rebase
`main`; never tag. You may push `wp/X07a` to run CI. Stage named paths only; never `git add -A`.

Read `docs/X07a_DECISIONS.md` first: Position, Q-12, D-28, D-29, the Windows classification.

## 1. The Windows lock (Frank, Decision Desk ofs-x07a-pywin32-lock, option A, verified 2026-11-20)

The action Frank signed, verbatim: "pin pywin32==312 with its wheel hashes in a separate Windows-only lock
requirements-windows.lock, installed with pip --no-deps --require-hashes on the Windows CI leg (the
requirements-coolprop.lock pattern of R-624); requirements.lock unchanged, on wp/X07a".

- Follow `requirements-coolprop.lock` and R-624 (how it is generated, documented, hashed, installed and tested).
  The wheel hashes come from the wheels themselves (`pip download pywin32==312 --only-binary=:all: --platform ...`
  for the Windows tags CI uses), never typed by hand.
- `requirements.lock` stays byte-identical (sha256 ead4edf1...); check it at the end.
- The Windows CI leg installs the new lock with `pip install --no-deps --require-hashes -r requirements-windows.lock`
  after the main lock. Other legs are unchanged.
- `test_t07_server_extra.py` (red on Windows through pywin32, WO5) and G19 must then pass on Windows; whatever
  test or inventory asserts the set of lock files learns the new one the way it learned the CoolProp lock.
- Amend R-1063 in `docs/decision-register.md` (or add a short follow-up entry in its form) recording the lock half:
  card ofs-x07a-pywin32-lock, option A, options B and C rejected; Q-12 closed in the decisions file.

## 2. The Windows remainder

Read the windows-latest leg of run 44699040945 (head 58bdd149; it tests WO5's fixes) first. Then the ~34 left in
WO5's list (WinError 32, signal 2, c9/s11 generators, msg_corpus, pre_push_guard, s03/s09, the V17 manifest, the
unread rest): portability bug (fix, Linux bitwise unchanged, F0 PASS) or platform limit (row with run id), largest
clusters first. Same rules as WO2 to WO5.

Each fix is its own commit naming X07a. Run the tests a change touches and F0 (`scripts/corpus_identity.py --check`)
locally before pushing; read CI with `gh run view --log-failed`, never whole logs.

## Report (200 to 300 words)

Commits; part 1 with the lock's sha256, the CI run where G19 and t07_server_extra pass on Windows, and
requirements.lock's sha256 at the end; Windows failed/errored counts per run read and what is left with its class;
any stop condition hit. Detail goes into `docs/X07a_DECISIONS.md`.
