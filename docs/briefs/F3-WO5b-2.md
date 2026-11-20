# F3-WO5b part 2: finish the `Records` operations (continuation of `docs/briefs/F3-WO5b.md`)

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`,
head after this brief's commit (part 1 at 880249b2). Work only there. Do not spawn sub-agents yourself. Budget about
150k tokens of context: at the cap, commit what is complete, write where you stopped in `docs/F3_DECISIONS.md`, and end.

`docs/briefs/F3-WO5b.md` is the work order and binds you in full (status, pattern, deliverables, acceptance, report),
with these changes:
- ADR 0061 is **Accepted** (R-1050). Do not edit it at all; its status line differs from 5d085f05 by design. Register
  entries you add take R-1051 onward (F3 holds R-1050 to R-1059). Head ADR 0019 Amendment 8 "Accepted 2026-11-18 with
  ADR 0061, Frank Peters; proposed 2026-11-05; F3", in the form of Amendment 7.
- Start from `docs/F3_DECISIONS.md` line 444 onward (`## F3-WO5b ... part 1`): decisions WO5b-1 to 6 (do not reopen
  them; they go to the design lane) and "Where it stopped". Do the remaining items in that order: the surface tests,
  CLI, descriptors (WO3-6), catalogue, Amendment 8 pointer and `interfaces-frozen.md`, `tests/test_f3_operations.py`,
  the acceptance runs, the build-log entry (part 2).
- Surface tests (57 red at 880249b2): fix each by taking the planned move the F1-WO4a pattern takes (request corpora,
  `SNAPSHOT_F3`, MCP digest with an F3 surface link, the support envelope), never by relaxing a check, dropping a case
  or narrowing a set. The earlier digest and each earlier snapshot must be recovered exactly with F3's additions
  stripped. Explain the two `tests/test_f1_operations.py` failures before changing anything they cover; if either is
  not a planned move, record it as a DECISION and stop that item.
- `test_every_description_is_reviewed_by_both_lanes` stays red with both reviews pending (as F1-WO4a); state it in the
  report as expected-red, with the five tool names.

Report: 200 to 300 words, as the work order asks, naming every digest, snapshot and SHA moved (old -> new).
