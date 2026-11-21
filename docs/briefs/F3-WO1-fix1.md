# F3-WO1 fix round 1 (from the design-lane review)

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`,
head 75ec382c. Work only there. Do not spawn sub-agents yourself. Budget about 150k tokens of context: at the cap,
commit what is complete, write where you stopped in `docs/F3_DECISIONS.md`, and end.

## Input

`docs/reviews/F3-WO1-review.md` (171 lines; read it whole). It is the design-lane ruling for this round: implement
its fixes as written, do not re-rule them. Background as needed: `docs/briefs/F3-WO1.md` (the work order),
`docs/F3_DECISIONS.md` (WO1-1 to WO1-15), ADR 0061 D1 to D7 by `sed -n` range.

## Do

1. Must fix M1 to M4, each with a test that fails on the WO1 head and passes after (the reviewer's falsifiers are the
   starting point). M1 includes the idempotence test: the normalised record of any accepted record is accepted with
   the same SHA and anchor.
2. Should fix S1 to S8 as the review gives them, including S4 with the reviewer's ruling (smallest phase token),
   S6 (the F3 paragraph in `docs/interfaces-frozen.md` §2, in the form of F1's paragraph, marked Proposed), and S7
   (the fixture: values plainly synthetic, or the real source cited; no invented citation for real constants).
3. The two rulings: WO1-11 with its three changes (`payload_schema.sha256` required; `payload_schema: null` only for
   preview types; `data_source.formats` `minItems: 1`), WO1-15 narrowed to `record_format ==
   "openflowsheet-record-v2"` under `tests/fixtures/records/`. Note in `docs/F3_DECISIONS.md` that A32 needs a v2
   clause in WO4.
4. Notes in the review: apply where a one-line change; else list them in `docs/F3_DECISIONS.md` for a later WO.

Each change that moves a SHA (fixture, registry, catalogue): re-take only what the move explains and say so in the
commit message. No existing pre-F3 artifact may change identity.

## Acceptance (run and quote)

1. `tests/test_f3_record_model.py` and the new tests pass; `ruff check`, `ruff format --check`, full `mypy`.
2. The test files listed in
   `/tmp/claude-1000/-home-eajfpeters-Code-OpenFlowsheet/10ed1d55-8773-442e-9840-53568b103799/scratchpad/f3-tests.txt`
   (62 files; at the WO1 head 1882 passed, 0 failed) plus any new test file: run them once at the end
   (`PYTHONPATH=<worktree>/src`, repo `.venv`, no `-n`, log to your scratchpad, quote the summary line).
3. `codehealth scan` on `records/`: no brain function, every file health >= 9.0.
4. F0 `scripts/corpus_identity.py --check` PASS.

Commits name `F3-WO1 fix1` and the finding (M1, S4, ...). Append to `docs/F3_DECISIONS.md`.

## Report (200 to 300 words)

Per finding: commit and test; what moved and was re-taken; acceptance results; anything not done and why.
