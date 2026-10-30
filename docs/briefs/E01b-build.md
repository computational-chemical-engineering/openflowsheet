# E01b brief: build the Seider-difference corrections (build lane, one engineer)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/e01b`, branch `wp/E01b` (head `99bc4315`, on `wp/E01`
`84d71df8`). Your work order is **`docs/derivations/E01-design.md` §10.6** (commits C1–C7, files §10.6.2, what moves and by
how much §10.6.3, acceptance commands §10.6.4), ruled in §10.1–§10.5 and §10.7 (R-890…R-894). Open questions §10.8: work
on the defaults. The Frank-approved patch for the five matching ranges is `docs/briefs/E01b-QA1.patch`.

- Do **C1–C6** and test once after C6 (§10.6.4). **C7** (the five new `verified: true` flags) is **not committed**: write it
  as `docs/briefs/QA1b.patch` (git diff format, applying cleanly on your C6) — Frank approves it later.
- **Stop rule (§10.6.3):** any number that moves and is not listed there → stop, commit what is complete, write the
  question at the end of `docs/E01B_DECISIONS.md`, end. Never widen a tolerance or edit an expectation to make a test pass.
- Q-B6: A15 needs the scratch IDAES 2.13.0 environment; re-create it from the pinned wheel (hash in §10.8) under
  `/home/frankp/.cache/idaes-2.13`; if impossible, stop and report (A15 is not skipped).
- Do not merge `main` or `wp/E01` into this branch (the orchestrator does that).

## Rules
- Each choice §10 leaves open: a `DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.` line in
  `docs/E01B_DECISIONS.md` (a new dated section "E01b"), one isolated commit.
- Tests you touch, then the §10.6.4 commands, then `scripts/s11_identity.py` → expect `S11-IDENTITY PASS` (cost lives outside
  every registered numerical path). Not the full gate (the orchestrator runs it once per batch). Pytest with a private temp
  dir: `TMPDIR=/home/frankp/.cache/e01b-tmp PYTEST_ADDOPTS="--basetemp=/home/frankp/.cache/e01b-tmp/pt"`,
  `PYTHONPATH=$PWD/src:$PWD`, `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python`. Never `/tmp` directly.
- The Seider 4th-ed. text at `/home/frankp/.cache/seider4/` is a Wiley evaluation copy: never copy it into the repository;
  individual numbers with page/table citations only.
- Stage named paths; never `git add -A`. Commit messages name E01b. Do not push. Do not start subagents. Do not send names,
  e-mail addresses or other personal identifiers to any external service (pip downloads of pinned wheels are fine).
- Context cap ~150k: commit, write a ≤40-line handoff at the end of `docs/E01B_DECISIONS.md`, end.
- Report in at most 20 lines: commits, tests with counts, every moved number versus §10.6.3, A48 count, any stop.
