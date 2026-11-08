# RRC handoff (build lane; branch `wp/RRC`, worktree `.claude/worktrees/rrc`)

Design: `docs/design/RRC-revision-region-continuation.md` (§7 work orders, §8 gates); ADR 0072 (Proposed).
Decisions: `docs/RRC_DECISIONS.md` (D-1…D-9). Rewritten in place; this is a position, not a diary.

## Done
- **WO-1** `2e3104cf` + `88de116a`: `Continuation.start_values`, `level_values` dispatch, `eo_recovery` Literal,
  `RRC_REVISION_V1` defined but **not offered** (D-1), three schema widenings (FQ1), ADR 0072 C1 byte moves.
  Tests `tests/test_rrc_continuation.py` (11).
- **WO-2** `4875cf32`: `orchestrator/revision_continuation.py` (types, constants, R5/R6/R8/R9a). Tests
  `tests/test_rrc_checks.py` (11).
- **WO-3** `88b31d23` (inert refactor, D-8) + `778b4ecb`: `executor._revision_continuation` (§5.5) with the keyword
  threaded from `execute_plan`; `region.py` `RecoveryStart.reported_signature` + attempt-0 opening check (§5.7).
  Built on `main`, not OPT (the merger resolves OPT's `final_system`). Tests `tests/test_rrc_edge3.py` (16).

## Gates (2026-11-08, at `778b4ecb`)
- G1: battery (rrc ×3, t04_homotopy, t04_edge3, t06_f4 ×6, t08_w4_warm_starts, m04_prewarm, t06_w4_registry,
  t07_b3_policies) 284 passed; four edge-3 files: empty diff vs `origin/main`; F0 PASS M1 50/50, M2–M5 61/61,
  M6 85/85, M7 52/52, M8 105/105, M9 35/35. WO-1's schema/digest table stands (`RRC_DECISIONS.md`).
- N1 (NET-02 split 0.5): CONVERGED, VERIFIED, λ 0, 1/4, 3/4, 1, no rejection; root = restart's ≤ 1e-8 scaled.
  G2 (a)–(f) hold ((f) because NET-02's opening pins no column: free = all 47 variables).
- G3: rejection at 1/4 → 1/8 from the λ = 0 root bitwise; all rejected → HOMOTOPY_STALLED, bracket 1/1024, no cert.
- G6 (b, f–j) + R3 + supplied refusal: one event, then trace = T06-revision-v2's except `plan_id`. (i) = `S3.vap.A`.
- F1 (M1-recycle → reflux 4.0, boil-up 3.0): 4.4e-13 scaled from item 0's root, VERIFIED. F2 (NET-03 feed T
  295 → 300 K): 1.95e-14, VERIFIED.

## Next
- **WO-4**: `application/revision_continuation.py` (selection, `assemble`, §5.4); threading at the warm-start lookup
  site; the `solve-path.json` member (`not_reached` lives there); R0 branch; rerun; G6 (a, c, d, e, k), G7. It must
  also offer the policy (D-1): `APPLICATION_POLICIES` entry, the pins in `test_t07_w3a_revision_runs.py`,
  `test_t07_w5a_inspection.py`, `test_t07_b3_policies.py`, and `test_t08_b50_surface_content.py`
  `V02_ADDITIONS["solve_policies"]` with its register entry. Then WO-5 (G4/G5/G8–G10), WO-6 docs.

## Open for the design lane (batched, one reviewer pass)
- D-1 (offer timing) and the served `get_project.solve_policies` move it implies — not in design §5.11.
- D-5 (§5.5 vs §5.8 on the recovery item's `initializer_source`), D-6 (reason carries the subject), D-7 (no
  `initializer_accepted` on a passed check).
- FQ1 (Frank): the three schema widenings; merge waits for "yes".
