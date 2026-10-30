# V03 brief: the single `reviewer` pass before the 0.3.0 candidate (design lane)

Read-only review of two branches; write the review to
`/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/V03-review.md` (the
orchestrator commits it as `docs/reviews/V03-review.md`). Exact text for any change; register ids from **R-900**.

## A. `wp/V03` (worktree `.claude/worktrees/v03`, head `0efa6645`; base `main` merged at `912504d9`)
Design: ADR 0053 (+ Amendment 1), ADR 0054, `docs/derivations/V03-release-spec.md` (+ Amendment 1). Build log
`docs/V03_DECISIONS.md` (DECISION lines, run log, open questions 1–3). Work orders WO-1…WO-4:
- WO-1 `scripts/v0_3_gate.py` on `v0_2_gate.py`'s engine — v0.2 output byte-identical over 18 runs (diff -r clean); A10's pairs.
- WO-2 Wilson data as package data (Frank: params + points); binder/verifier pass the packaged path; `wilson_ig.py` untouched
  (R-883); T08.A32/S10.A28 amendments (D-2/D-3).
- WO-3 ADR 0054 roles (enum + Table R; nine cases regenerated; A28–A31; A31 binder outcomes equal 80/80); three
  `test_t07_w5c_signatures` pins re-pinned because they hash `revision_sha256` (`8c6ddb8a`) — check that only that field
  moved; MR-12 v03; new CI job `rc-coolprop`.
- WO-4 ADR flips 0046–0049 Accepted (0050–0052 at C), S07 F-1 transcribed, CHANGELOG draft, envelope U02/L40/L-S11-3,
  attribution page, RELEASING.
Measured: `S11-IDENTITY PASS n=54494 changed=[]`; touched modules 1070 passed; v0.3 gate tests 67 + Wilson ship 25.
Rule the open questions Q1–Q3 in `docs/V03_DECISIONS.md` (Q3: spec §9.3 cites R-870 for the `lca` licence decision).

## B. `wp/E01b` (worktree `.claude/worktrees/e01b`, head `23bfb0cf`; gate PASS 14551 passed; CI running)
Corrections to E01's cost set after checking against Seider et al.: ruling B `docs/derivations/E01-design.md` §10 (4th ed.,
R-890…R-894) and its Amendment 1 §10.10 (3rd ed., R-895…R-899: six IDAES corrections incl. pump/motor CE 394 → 500,
fixed-head α2 0.9228, tower platform 300.9; the exchanger-intercept rule; compressors on consumed power R-890). Build log
`docs/E01B_DECISIONS.md` (sections "E01b", "build 2", "build 3"; the orchestrator's A44 ruling). Measured: A15 vs IDAES
worst 1.02e-14; A49 3rd-ed. consistency, four deliberate corruptions each fail; nothing moved outside §10.10.7's list; C7
(five `verified` flags) approved by Frank and committed `92afd75b`; A48 at 0. Manifest `evidence/S12b/1fd29546…`.
Look hardest at: the exchanger-intercept rule (keeping IDAES where the 3rd ed.'s printed equation is on CE 394 but its
example uses IDAES's value); the CE 500 relabel of pump/motor (Q-B11); R-890's motor efficiency coupling with capital vs
energy; the P2/P3 floors.

## Not in scope
The docs site (build-lane documentation); re-running suites; style.

## Deliverable
Findings by severity (must-fix before the candidate / should-fix / note), with exact text where anything changes, and a
ruling on V03's Q1–Q3. Do not start subagents. Do not send personal identifiers to any external service. The Seider texts
under `/home/frankp/.cache/seider{3,4}/` are licensed copies: read, never copy into the repository. Context cap ~200k.
Report in at most 20 lines.
