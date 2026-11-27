# Reviewer brief: F8 (identity, replay and evidence v2), WO1 to WO3 and WO5 for the 0.6 line

Status: brief, 2026-11-27. Design lane, the package's single `reviewer` pass (LINE06 rules: one per package before its
merge), with the F8 ruling batch folded in. **Do not spawn sub-agents yourself.** Reading and running tests only; no
code edits. Rules: `docs/LINE06_RULES.md`.

## What to review

Branch `wp/F8` at `5406f812`, worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f8` (read and run tests
there; do not commit there). wp/F8 branched from wp/F2 at `df796cc2`, so F8's own diff is
`git diff df796cc2..5406f812` (24 commits, 46 files, +5236/-61); F2's part is reviewed separately
(`docs/reviews/F2-review.md`). Against: `docs/adr/0067-F8-identity-replay-evidence.md` D1 to D7, D9, exits E-F8-1 to
-6, -8, -10 (E-F8-7 and -9 are not in this line), "New catalogue codes", the work-order table; ADR 0019 Amendment 12
(new pointer paragraph). Build decisions: `docs/F8_DECISIONS.md` (all entries). Evidence:
`evidence/F8/32981fb3f62f0324edc2c9f311c8c4dbe9dad768/manifest.json`. Others work in `.claude/worktrees/f2` and `x06`;
leave them alone. Logs only under `/home/eajfpeters/.cache/line06/f8rev/`.

## Measured (by the build lane, judged by the orchestrator)

At every WO: F0 PASS (M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42). `tests/test_f8_*`: 122
passed at `32981fb3` (bundle_v2 21, manifest_v2 34, platform_refs 29, replay_v2 38); `test_k05_replay` 30;
`test_x07a_*` 18; MSG 186 passed, 3 xfailed. E-F8-1: 52 committed 0.3.0 bundles give `ReplayReport`s byte-identical to
the pre-F8 reports computed at `ddac950f`. Catalogue digest `4ca46ea4...` -> `bbdcfb51...` (WO5's notice). Known red
on this head: `tests/test_adr_0002_a1_integers.py::test_j16_...`, inherited from wp/F2 and fixed there (`6913c4a0`,
DECISION F2-J16); it clears when wp/F2 is merged into wp/F8. Also known: the three `tests/test_v03_semantic_roles.py`
reds (F2's). ADR 0067 D7 was amended before WO5 by folding the X07a ruling's errata E-D7-1 to 5 (`369150d3`, DECISION
F8-WO5-0): check that the fold matches `docs/X07a-platform-ruling.md` section 5.2 word for word in substance.

## The ruling batch (rule on each: keep / change, with the exact change)

1. **F8-WO1-1:** D2's and D5's member shapes in a new `schemas/bundle-v2.schema.json` (l.16).
2. **F8-WO3-1 (l.221, l.233):** D5 step 7 is met as written for the factory's bundles, and the served stack has no
   consumer until v2-compiled runs exist: accept this reading, or require WO6 to add a rerun that reads the served
   stack.
3. **F8-WO3-2 to WO3-10** (l.234 to l.262): `extension_use_undeclared` in `differences` not `reasons`; unknown
   `bundle_format` checked first; "changed built-in"; a plain `Rerun` does not match; `edited_registry`; reasons in
   D5's step order; the default local store is an empty project; `ReplayMode.forced_replay` refused in
   `__post_init__`; the four codes in a new `catalogue/replay.yaml`, all `refusal`.
4. **F8-WO5-1 to 4 and the Opus review's R1 to R4** (l.302 onward), and its two leftovers (l.360): `select_reference`
   does not re-check `reference_sha256` at selection; no check that a departure's values are those at its `path` in
   the two records. Must either be closed before merge?
5. **F8-CO-1 to 4:** the Amendment 12 text; `not_applicable` used for the out-of-scope exits (the schema has no
   `not_in_scope`); the harvest rows and `HARVEST_SIZE` (109, 1180, 150), to be recomputed at the F2-into-F8 merge.

## Where to look hardest

D5 replay: does every reason and mode follow D5's step order and ADR 0007 D4; can any v1 bundle reach the v2 path or
vice versa (E-F8-1, E-F8-10)? D4 rights: can a `unknown` or `refused` record ever be embedded; does re-assessing a
source move any identity (E-F8-3)? D3 integrity: does the check cover `records/` and both new documents (E-F8-2)? D7:
the registered-platform restriction (E-D7-3) and the R0 invariant. Test strength: would each exit's test fail on the
mutation it claims (the decisions file lists the controls run)?

## Deliverable

`docs/reviews/F8-review.md`: verdict; findings M (must-fix) / S (should-fix) / N (notes) with file:line and a stated
fix; a ruling on each batch item; a numbered fix-round work order for the build lane (one Opus engineer). Commit on
**main** (`/home/eajfpeters/Code/OpenFlowsheet`, docs only, named path, message `LINE06: F8 review`, trailers
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_015Acof1nLKMy3Lsg6MpcJUZ`). Report at most 25 lines, including whether anything needs
the user (any ruling that changes an Accepted ADR decision does; ADR 0067 is still Proposed).
