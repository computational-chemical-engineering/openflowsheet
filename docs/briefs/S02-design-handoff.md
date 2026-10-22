# S02 design (pre-solve and edge 3) — handoff (`architect`, 2026-10-22)

Branch `wp/S02` (not pushed). Commit `d4f5a5d` (plus the evidence line below, if it landed): spec Amendment 2
(`docs/derivations/S02-spec.md` §18), ADR 0044 (Proposed), register R-546 to R-549, `docs/S02_DECISIONS.md` rulings,
FRANK_QUESTIONS Q-S02-3 follow-up and Q-S02-4.

Design: §7.3's Newton pre-solve is replaced by a constructed easy endpoint `s02-bubble-point-v1` (bubble-point sweeps at
fixed CMO stage ratios, ratio ends at their specified ratios); the target path is unchanged; ADR 0044 makes
`LINEAR_SOLVE_FAILED` an edge-3 trigger when the failed solve ran ≥ 2 attempts. V-M2 `(duty, duty)` has a second regular
root `R2`, registered and asserted (A07, A21).

Measured (scratch on `47eb3aa`): every registered case and admissible variant converges to `ref.target` (≤ 8.5e-3 of the
state tolerance) except V-M2 `(duty, duty)` → `R2`; P1 → `HOMOTOPY_STALLED` (A12's typed branch).

Next executable actions, in order:
1. WO-G (design lane `specifier`): generator keys `bubble_point`, `bubble_point_continued`, variants' `bubble_point`,
   `variants.M2.duty+duty.second_root` (§18.7); additive re-emission; new `REFERENCE_SHA256`.
2. WO-2b (build lane): §18.7 items 1–4 — can start now except A05, A07's `R2`, A13's `p⁰`, A21 (need WO-G).
3. WO-3 as amended (A14 per §18.6).

Pending fact: the full suite with ADR 0044's predicate patched in (scratch snapshot of `47eb3aa`, `pytest tests`,
`test_t07_evidence_manifest.py` uncollectable outside git). If its result is not in `docs/S02_DECISIONS.md` ("ADR 0044
suite"), WO-2b's full gate is the measurement; a moved registered outcome goes into ADR 0044 C2 before acceptance.

Scratch code (not committed): `bp.py` (sweeps), `adr44.py` (target with the predicate), `perturb.py` (A14),
`sigma.py` (R2's σ_min) under the design session's scratchpad `s02-design/`.
