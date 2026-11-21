# X07a-WO5: pywin32 (Frank's ruling) and the Windows clusters

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x07a`, branch `wp/X07a`,
head a60d1b54 (not yet pushed; push it with your first push). Work only there. Do not spawn sub-agents yourself.
Budget about 150k tokens of context: at the cap, commit what is complete, rewrite the Position section of
`docs/X07a_DECISIONS.md`, push, and end.

Authorization, push rules and the scientific-conduct limits are those of `docs/briefs/X07a-WO1.md` (read its "Scope",
"Stop and report instead of choosing" and "Acceptance"); they bind unchanged. Never push, merge into or rebase
`main`; never tag. You may push `wp/X07a` to run CI. Stage named paths only; never `git add -A`, not even on one
directory (WO4 did; do not repeat it).

Read `docs/X07a_DECISIONS.md` first (Position, D-23 to D-27, the Windows classification). ADR 0007 Amendment 3 is now
accepted (D-27, R-1062).

## 1. pywin32 (Frank, Decision Desk ofs-x07a-pywin32-licence, option A, verified; register R-1063 is reserved for it)

The action Frank signed, verbatim: "allow pywin32 (PSF-2.0, compiled) in the G19 licence policy as a Windows-only
dependency of the server extra, and pin it with a Windows marker in the lock, on wp/X07a".

- G19 (`scripts/t07_licence_inventory.py`): pywin32 312 declares `PSF` (Q-1, run 44615939688), not the `PSF-2.0`
  already in `ALLOWED`. Make pywin32's declared term pass as Frank's ruling allows it, and no other distribution
  with that term (an entry scoped to pywin32, justified with R-1063 in its text, beats a new open licence family).
- The lock: pin `pywin32==312` with a Windows environment marker in the lock that installs the server extra on
  Windows. Find which lock that is and how CI installs from it.
- **Stop and report instead of choosing** if the pin goes in `requirements.lock`: its bytes are the recorded
  `lock_sha256` (`src/openflowsheet/run/lock.py`, ADR 0007 Amendment 2, ADR 0069). Before committing such an edit,
  measure on this workstation: does F0 (`scripts/corpus_identity.py --check`) still PASS 9/9, does any committed
  fixture, registered expectation or test pin the lock's SHA-256, and does ADR 0069 D3's verified-lock check still
  pass on Linux with pywin32 absent? If any of these changes, do not commit the lock edit: write what changes, with
  numbers, in `docs/X07a_DECISIONS.md` as Q-12 and continue with part 2.
- Add register entry `## R-1063 ` in `docs/decision-register.md` (form of R-1062 at the file's end: table, Decision,
  Rejected = option B "keep pywin32 refused; declare the server extra a Windows platform limit"). Close Q-1 in the
  decisions file. Acceptance: `t07_licence_inventory.py` passes on the Windows leg (cite the run), its tests pass
  locally, and `test_t07_server_extra.py` passes on Linux.

## 2. Windows clusters

Continue the classification in `docs/X07a_DECISIONS.md` (run 44670029066: 116 failed beyond the WinError 123 fix;
clusters: path separators, CRLF, WinError 32, signal 2, 37 `test_m02_experiments.py` children ending
`environment_unavailable`, M05 host keys, the unread set). First read the windows-latest leg of 44683830734 (head
51f7fcae) if it has finished, else of 44681408041. Per cluster: portability bug (fix, Linux bitwise unchanged, F0
PASS) or platform limit (row with run id). Largest clusters first. Also confirm L5 and rows L6 to L10 on the macOS
leg of 44683830734.

Each fix is its own commit naming X07a. Run the tests a change touches and F0 locally before pushing; read CI with
`gh run view --log-failed`, never whole logs.

## Report (200 to 300 words)

Commits; part 1's outcome (or Q-12 with its numbers); Windows failed/errored counts per run read and what is left
with its class; macOS confirmation; any stop condition hit. Detail goes into `docs/X07a_DECISIONS.md`.
