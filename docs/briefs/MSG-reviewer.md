# Reviewer brief: MSG — messages and the code catalogue (0.4), the single review pass

Status: brief, 2026-11-06. Package MSG, ADR 0058 (Accepted, ADR 0019 Am. 6), design note `docs/design/MSG-messages.md`
(the architect pass), build briefs `docs/briefs/MSG-build-WO0-2.md`, `MSG-build-WO3-6.md`, `MSG-build-WO9-10.md`.
Branch `wp/MSG`, worktree `.claude/worktrees/msg`, head `8d955cd7` (29 commits over main; main merged in at `b1a82351`).
Build-decisions log `docs/MSG_DECISIONS.md` (in the worktree), handoff `docs/MSG_HANDOFF.md`, manifest
`evidence/MSG/b1a82351…/manifest.json` (status `implemented`).

## The question

Does `wp/MSG` implement ADR 0058 and the design note correctly, and what are the rulings on the batched questions below,
so the package can become `tested` and merge? Deliver must-fix / should-fix findings and one ruling per question.

## What was run (engineer's numbers; re-run what you doubt)

- MSG-G4 0 violations; G5 clean; G6 23 passed + 11 strict xfails; G7 16 passed (only the U05 record moved); G8: the ten
  corpus cases that run on all four transports return one identical document on each.
- MSG-G0: (a) 0 diff, (b) 0/562, (d) 0 hits in 442 stores; **(c) prints FAIL 156/109**: the 57 baseline replays are
  unchanged; all 156 differing keys are F0's 52 v0.3.0 replay fixtures, which postdate the WO-0 baseline (D9-10).
- F0 `scripts/corpus_identity.py --check` PASS (M1 50/50 … M9 35/35).
- Full suite at `b1a82351`: 1 failed (`test_t08_w2_description_reviews`: `explain.md` reviews not recorded — D7-8, by
  design until the design lane and Frank record them), 15065 passed. A wall-time budget test fails only under host load
  (327.95 s vs 300 at load ~78; 250.2 s alone) — not MSG's; budgets are never changed.
- Gate changes flagged by the build lane: D7-7 (`m07a_rc` §5.3 item 4), D7-10 (five pins after WO-7/8), `HARVEST_SIZE`
  68,939,120 → 69,943,122 (six harvest items, class P), D0-7 (an MSG-G0 (b) defect fixed).

## Batched questions (rule each; the engineer's default in brackets)

1. **WO-5 redesign under the F0 freeze.** WO-5 (the diagnostic sidecar giving C01/C02/C11 their numbers: `value`,
   `saturated_vapour`, `pressure`; `s_star`, `s_saturated`; `p_spec`/`p_inlet`) must edit
   `src/openflowsheet/models/thermal/{flash,heater,machines,mixer,valve}.py`, which F0 M9 freezes byte-for-byte
   (R-940, `docs/reviews/F0-review.md`). Parked; the number assertions are strict xfails. Rule the route: (a) a sidecar
   outside the frozen files (e.g. recomputing the numbers from public outputs in a new module); (b) a registered
   exception/amendment to M9 that admits edits proved output-identical by M1–M8; (c) defer the numbers to the F6 v2
   unit models (ADR 0065), shipping MSG without them; or another. If it needs the architect, say so with the question.
2. **D9-2.** Should §4.4 rule 2 parse the first non-PASS check's message for a DRAFT report and add a failing check's
   `implicated_objects` as elements (C06–C08, C10 strict xfails; "degc" in C08's text; `model_unsupported` for C10)?
   [yes to both; rendering only].
3. **D9-10.** Does F0 replace MSG-G0 (a)–(c), as the note's §7 says, with MSG-G0 keeping (d)? [yes]. If not, how is the
   (c) baseline re-taken?
4. **D7-7, D7-10, `HARVEST_SIZE`**: accept the gate changes or not.
5. **D_4**: the register entry carrying `D_4 = 1ca06b37…` and Frank's carry naming c_4 (`MSG_DECISIONS.md` ~line 229).
6. **`explain.md`** (the MCP `explain` tool description, D7-8): the design-lane review of its text; Frank's review is
   separate and is a merge blocker (`docs/FRANK_QUESTIONS.md`).
7. **D3-4, D4-1, D6-3** (members query, stubs for three new codes, CLI failure text): confirm or rule.
8. **The prose of the seven new catalogue entries** (WO-9, `3842f686`): revision_not_ready, unsupported, DIM-01,
   out_of_domain, pressure_rise, task_unsupported, model_unsupported.
9. **A5-a** (`docs/roadmap/foundation-rulings.md` §17): `verify.table.blocked_check` records
   `temperature_degenerate_unlifted(<S>)` as a string, not a code with params (`src/openflowsheet/verify/table.py:310–319`).
   Is a typed catalogue code for it in MSG's scope, or the verifier's (ADR 0013) later?

## Least sure of

The WO-5 route (1); whether the corpus (`tests/fixtures/msg/corpus.yaml`, `tests/test_msg_corpus.py`) verifies anything
beyond self-consistency — its expectations are emitted output (§3.6 "record the actually emitted code"); the D7-10 pins.

## Deliverable

`docs/reviews/MSG-review.md`: verdict (merge-ready after fixes or not), must-fix (M*), should-fix (S*), one ruling per
question above as `Q<n>: ruling — reason`, and what the review did not establish. Commit it on **main** (docs-only;
named path; message `docs: MSG review`; end with the session's Co-Authored-By / Claude-Session lines given in your
prompt). Do not edit `wp/MSG`. Never set `reviewed` in a manifest. Report ≤ 30 lines.

## Out of scope

The ST and RP packages; F1–F8 designs (frozen core, R-941); wall-time budgets; style and formatting.
