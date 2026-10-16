# Design-lane ruling: M04 input box vs reactor v3 (blocks WO-11), plus small readings

Branch `wp/M04` @ `c8f7e5d` (main with M02 merged), worktree `.claude/worktrees/m04`. Spec `docs/derivations/M04-spec.md`
(§3.1 inputs and scaling l.60; N4 l.~813; WO-11 row l.795; Amendment 1 §A1.6 l.984). Build log
`docs/design/M04-build-decisions.md` (E15 l.105, E16 l.113, E22 l.142, E23 l.151).

## Facts (measured, nothing run)
- WO-11 binds reactor v3 (`benchmarks/m02/c1-loop-real.json` names `pymrm-6089593-g2-nz800-s123-v3`; A33 runs on that loop).
  v3's hard domain (R-315, rung V5): T [653.15, 693.15] K, P [9, 11] MPa, H₂/N₂ [2.5, 3.5], inerts (y_Ar + y_CH₄)
  [0.035, 0.2], per-tube flow [0.003573, 0.014294] mol/s; outside → `out_of_domain`.
- §3.1's box has y_Ar ∈ [0.01, 0.03], y_CH₄ ∈ [0.01, 0.04] → inert sum down to 0.02. Of the 632 requests in
  `benchmarks/m04/plan-it1.json`, 115 have inerts < 0.035 (29 training, 19 calibration, 67 test, 0 gradient; lowest
  0.02255). All other bounds hold (H₂/N₂ ≤ 3.0, P ≤ 10 MPa, F ∈ [0.0057, 0.0086], T = the box). `prepare(v3, "it1")`
  refuses `plan_invalid`; `prepare(v2, "it1")` admits it.
- M02 D84: 653.15 K, high-P, 2 %-inert corners fail the reactor's start (S1) — on v2 too, where v2 and v3 agree bitwise —
  so binding v2 would likely give INSUFFICIENT_EVIDENCE (`plan_incomplete`).
- M02 D87: the loop's reactor inlet at 653.15 K has H₂/N₂ = 3.000008 (just above the box's 3.0); inerts 0.040–0.045.
- Engineer's recommendation: register a new box by amendment (new P_ref id, regenerated plan files) with an inert floor
  ≥ 0.035 (e.g. y_Ar [0.015, 0.03], y_CH₄ [0.02, 0.04]) and r widened slightly above 3.0; run WO-11 on v3.
  Alternative: bind v2 for iteration 1.

## Decide
1. The box (N4): bounds, id, what is regenerated, which assertions/registered values change (A31–A33 and any fixture tied
   to §3.1), and the iteration-1 cost (Amendment 1: pre-warm with 16 parallel jobs).
2. E15 (does A27 mean a project bound to the rough parent?), E16 (unresolved manifest → fail, not `not_applicable`),
   E22 (test-only backend injection), E23 (stale A19 environment fingerprint; its hash is the W27 resolver entry R-302 —
   re-take or record as erratum).

## Deliverable
Spec amendment section + register entries (next free after R-318; check main, wp/M04, wp/M05, wp/V02-alpha-gate),
committed on `wp/M04` (doc only, named paths, no push). Report ≤ 250 words: rulings one line each, the WO that implements.
