# F3 ruling round 1: build-lane changes B1 to B7

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`,
head after this brief's commit (ruling round at 5d085f05). Work only there. Do not spawn sub-agents yourself. Budget
about 150k tokens: at the cap, commit what is complete, write where you stopped in `docs/F3_DECISIONS.md`, end.

## Input

`docs/reviews/F3-rulings-1.md` (the design-lane rulings; read it whole): implement B1 to B7 as written, each with the
acceptance test the review gives, one commit per item naming `F3 rulings-1 B<n>`. Background as needed:
`docs/F3_DECISIONS.md`, ADR 0061's closing section "F3 ruling round 1 applied". **Do not edit
`docs/adr/0061-F3-component-data.md`**: Frank's acceptance card is re-pinned to its text at 5d085f05. If an item
cannot be built as ruled without an ADR change, stop on that item, write the problem in `docs/F3_DECISIONS.md`, and
do the rest.

Index or catalogue SHAs that move: only what the item explains (B1: exactly two index SHAs; B4: the catalogue SHA in
the two `message_entry` fixtures); regenerate with the committed generators and say so in the commit message. The
legacy YAML files, legacy loaders and `thermo/` stay untouched.

## Acceptance (run and quote)

1. The four F3 test files pass with the new tests; `scripts/records_legacy_index.py --check` clean; `ruff check`,
   `ruff format --check`, full `mypy`.
2. The 62 files in
   `/tmp/claude-1000/-home-eajfpeters-Code-OpenFlowsheet/10ed1d55-8773-442e-9840-53568b103799/scratchpad/f3-tests.txt`
   plus the four F3 files, once at the end on an unchanged tree (`PYTHONPATH=<worktree>/src`, repo `.venv`, no `-n`;
   do not commit while it runs; at a4272c16: 2002 passed, 0 failed).
3. `codehealth scan` on `records/`: no brain function, every file health >= 9.0; `codehealth arch` 0 violations.
4. F0 `scripts/corpus_identity.py --check` PASS; `git diff 5d085f05 HEAD -- docs/adr` empty.

## Report (150 to 250 words)

Per item: commit, test, what moved; acceptance results with counts; anything not done and why.
