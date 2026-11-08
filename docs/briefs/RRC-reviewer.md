# Reviewer brief: RRC — revision-region continuation (0.4), the single review pass

Status: brief, 2026-11-08. Design `docs/design/RRC-revision-region-continuation.md` and ADR 0072 (Proposed), both on
main (`1566da46`). Branch `wp/RRC`, worktree `.claude/worktrees/rrc` (head `dc205d90` + WO-6 docs in progress). Build
log `docs/RRC_DECISIONS.md` (D-1…D-27), handoff `docs/RRC_HANDOFF.md`. No manifest yet (needs CI on both legs).

## The question

Does `wp/RRC` implement the design so that revision continuation is a real, recorded, replayable edge 3 that changes
no registered record and no non-edge-3 plan, and only rescues what it claims — and what are the rulings on the batched
D-items?

## What was measured (engineers' numbers)

- G1: F0 PASS M1–M9 after every WO; the four edge-3 test files (`test_t04_homotopy.py`, `test_t04_edge3.py`,
  `test_t06_f4_edge3.py`, `test_t06_f4_restart.py`) have an empty diff vs main; targeted batteries 284/626/333 passed;
  numerical-policy bytes unchanged; only the three widened schema files' hashes move (solve-policy, attempt-context,
  solution-certificate); served `get_project.solve_policies` digest `74e41d71…` → `94c6ae7c…` (D-1 offer); MCP tool
  list `455d01eb…` unchanged; the four offered policies' hashes unchanged.
- WO-3: G2 (a)–(f) on NET-02 from N1 (λ = 0, 1/4, 3/4, 1; (e) checked at 1/4 and 3/4 since 1/2 is not visited); G3
  rollback/halving/stall bracket 1/1024; G6 refusals record one `initializer_rejected` event then the restart runs
  unchanged; F1 (M1-recycle reflux/boil-up) 4.4e-13 scaled; F2 (NET-03) 1.95e-14.
- WO-4: nearest-VERIFIED-ancestor lookup, `solve-path.json` member, replay from the bundle alone (4 bundles MATCH with
  the store/binder patched to fail if called); G8 local x86 only.
- WO-5: candidate table committed before any run (`cba5e8e2`); 10 candidates × 3 policies all reported, 3 identical
  repeats; G4 N1: control `BOUND_BLOCKED` → `RRC-revision-v1` CONVERGED/VERIFIED, 1.96e-9 scaled from the restart's
  root, 0.0109 of T06's allowance vs the closed form; G5 C3 (M1-recycle split 0.2 → 0.9): `BOUND_BLOCKED` → VERIFIED,
  A29 balance 2.7e-10 of tolerance → L-COL-9 and L21 narrowed; G7 C3 MATCH; G10 0.12–0.63 s per recovery.

## Rule on each

1. **D-11** (most important): a parameter key's family is its text before the first `.`, which decides which edits are
   continuable (the operating-value allowlist, design §5.4, Frank's FQ4 default). Sound and complete? Any parameter a
   user could edit that would be continued although it changes structure, stoichiometry or a model constant?
2. D-5 (`initializer_source` per §5.8, not §5.5), D-6, D-7 (no `initializer_accepted` event on a passed opening), D-8
   (the `_external_opening` extraction is structure-only), D-10, D-12…D-15, D-16 (draft register id R-RRC-6).
3. The opening-hash point: the opening hash covers the free columns, so on a source that pins columns it will not equal
   the source's `full_state_sha256`; no registered case pins a column (all sources all-`TWO_PHASE`). Is G2(f)'s wording
   right, or must it be amended before a pinned-column case is ever registered?
4. Inertness: does any non-edge-3 path, or any run under the existing four policies, change behaviour or bytes?
5. The candidate procedure (D-17…D-26, incl. the YAML-syntax amend before the first run, D-26) — does it meet the
   design's pre-registration intent? D-27 (comment wording in `cases.yaml`).
6. What must happen for `tested` (CI both legs incl. G8 on C3; manifest), and the merge order vs `wp/OPT` (both touch
   `orchestrator/executor.py`; OPT adds `RegionResult.final_system`).

## Least sure of

That no existing plan changes (G1 rests on F0 and targeted batteries, not yet a full gate); the family rule's coverage;
the replay member's completeness for a bundle replayed on another machine.

## Deliverable

`docs/reviews/RRC-review.md`: verdict, must-fix, should-fix, one ruling per item, amendment text where needed, what the
review did not establish. Commit on **main** (docs-only, named path, message `docs: RRC review`, with the session's
Co-Authored-By / Claude-Session lines). Do not edit `wp/RRC`. Never set `reviewed`. Report ≤ 30 lines.

## Machine-load rule

TRS2: `uptime` first; targeted tests only, one at a time, `OMP_NUM_THREADS=1`; a full gate is running — no other.

## Out of scope

OPT, X02, MSG; arclength/fold following; K04's witness policy; style.
