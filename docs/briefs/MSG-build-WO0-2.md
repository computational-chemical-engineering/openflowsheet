# Build brief: MSG work orders WO-0, WO-1, WO-2 (0.4)

Status: brief, 2026-11-05. The spec is the design note `docs/design/MSG-messages.md` (architect pass, `0c78cf11`); ADR
0058 is **Proposed** (Frank's acceptance gates the merge into `main`, not this work). Branch `wp/MSG`, worktree
`.claude/worktrees/msg`. Decisions log: `docs/MSG_DECISIONS.md` (create; append-only).

## Scope

Exactly WO-0, WO-1 and WO-2 of the note §6 (lines 1222–1257), in that order, with their files and *Accept* lists. Read:
§2 (constraints, invariants I1–I8), §3.1–3.3, §4.1–4.6, §4.11, §4.13, §5 (identity analysis), §6 WO-0…WO-2, §7 rows
MSG-G0…G4 and Performance, §9 (build choices left to you). Read other sections only when a WO points at them. Do not
start WO-3 or later: they carry ADR 0058's contract changes.

## Rules

- **The identity gate first.** WO-0's baseline is recorded at the branch point before any MSG code; MSG-G0 must PASS
  after WO-2 (it touches identity hooks in `verify/failure.py`, `contract.py`, `binding.py`). If MSG-G0 fails, stop and
  report: no change to a released number, hash, bundle byte or replay verdict is acceptable. F0 (a general corpus
  identity gate) is being built concurrently on `wp/F0`; do not touch its files, and do not wait for it.
- A build choice the note leaves open (§9): decide it, make it an isolated commit where you can, log it in
  `docs/MSG_DECISIONS.md` (question, options, choice, reason, commit). A choice that would change numerics, identity or
  a frozen interface: stop and report instead.
- No relaxed checks, no removed cases, no narrowed denominators. The stub entries' `review: true` count is reported, not
  hidden.
- Run the tests you touch. At the end run the full gate once in the background and wait for its notification
  (`PYTHONPATH=$PWD/src PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH ./scripts/gate.sh` in the worktree); read
  the log only on failure, by `grep`/`tail`.
- Commit on `wp/MSG` only, staging named paths, messages starting `MSG WO-<n>:`. Do not push, do not merge.
- Context cap about 150k tokens: if you approach it, commit what is complete, write `docs/MSG_HANDOFF.md` (≤ 40 lines:
  done, next, open), and stop. Ending after WO-1 with a clean handoff is acceptable.
- Never read, stat or touch `~/.config/procsim/`. Do not start subagents.

## Report (≤ 30 lines)

Commits per WO; each *Accept* item pass/fail; MSG-G0…G4 results with their summary lines; catalogue counts (full entries,
stubs, `review: true`); performance numbers (cold load, render median); build choices logged; anything the note got
wrong.
