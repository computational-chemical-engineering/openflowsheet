# E01 brief: track A's escalations ESC-A2…ESC-A5 (design lane, `architect`)

Worktree `.claude/worktrees/e01` (branch `wp/E01`, head `ff7a62a7`). Design `docs/derivations/E01-design.md` (your first pass;
ADR 0052; R-850…R-862). Build log `docs/E01A_DECISIONS.md` — read its end: the facts (IDAES-PSE 2.13.0 wheel pinned and
hashed, SSLW coverage, CE 500 = 2006), ESC-A1 (done: E01 addendum `benchmarks/e01/numerical_policy_external.yaml` in
`ADDENDA`), and **ESC-A2…ESC-A5 with the engineer's proposals**. WO-A1 and WO-A2 are done; **WO-A3 (SSLW set file) is
blocked on ESC-A3.** The unpacked IDAES wheel is under the session scratchpad (path in the log).

## 1. The question

Rule each escalation precisely enough that WO-A3, A4, A5 and track B have nothing left to choose:
- **ESC-A2:** §4.11's additive `assessment_sha256`/`regime_sha256` properties in `study.schema.json` and
  `optimization-report.schema.json` fail T08's v2 numerical-policy audit, because an addendum cannot classify names in schemas
  it does not own. Proposal: a `classifies_in` key on the E01 addendum (an auditor change in `scripts/t08_numerical_policy.py`).
- **ESC-A3:** IDAES 2.13.0 `SSLW.py` does not fit §4.5.1's cost forms: exchanger 1.1 oversize factor, size-dependent material
  factor, polynomial pressure factor; vessel shell thickness an input (default 1.25 in), not computed from pressure;
  platforms/ladders/trays additive, not multiplicative; pump and motor on CE 394, not 500; no exchanger size range stated.
  Proposal: extend the set-file grammar (details in the log). Decide the grammar (or the forms), how each SSLW feature is
  represented faithfully (transcription, not re-derivation), the validity ranges where IDAES states none (a stated
  limitation, or a range from the primary source Seider et al. if the note allows citing it), and the index base per item.
- **ESC-A4:** `kinetic_cstr` has no volume parameter (proposal: refused `SIZING_INPUT_MISSING`); a dormant liquid with a
  declared liquid molar volume has no molar mass for ρ_L (proposal: the vapour member is refused).
- **ESC-A5:** no registered column basis other than SYN-001 offers a molar volume, so P3's shell/trays and P2's drum are refused
  and A12 cannot run on a registered case. Options: a column case on a basis with molar volume, or a ruling that ideal-gas RT/P
  counts as the provider's `v` for vapour sizing (say for which bases and phases, and how that is stated in the report).
  Remember Frank: as few limitations as possible.

## 2. Constraints

Post-solve functionals only; no change under `compile/`; nothing registered moves; independent expectations only (B4's
hand transcription from the pinned IDAES source, scripts not importing `openflowsheet`). IDAES is BSD: transcribe with
`source_line` per number. Register from the next free id after R-862. Batch, then test once.

## 3. Deliverable

A dated amendment section in `docs/derivations/E01-design.md` (the four rulings, the set-file grammar, revised WO-A3/A4/A5 and
any track-B item affected, with acceptance tests); register entries; a docs-only commit on `wp/E01` including this brief. Do
not push. Report in at most 15 lines.
