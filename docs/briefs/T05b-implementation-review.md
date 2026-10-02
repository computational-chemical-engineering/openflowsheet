# Brief — T05b implementation review (T05b + F9)

**To:** `reviewer` (design lane). **From:** the session (build lane), 2026-09-25.
**Design under review:** `docs/derivations/T05b-limitations-spec.md` (B00–B30) with ADR 0012
(Proposed; D1–D12); `docs/derivations/K04-F9-spec.md` (X00–X26) with ADR 0013 (Proposed); twins
`docs/derivations/scripts/t05b_reference.py` (585 claims, YAML `7870bbc9…`) and `k04f9_reference.py`
(25 claims, `73be8df9…`); register R-052…R-062. Frank's directives are quoted at the top of the
T05b spec (fewest limitations; robustness with recorded fallbacks; F9 folded in; schema widening
approved).
**Implementation:** `wp/T05b`, `1ba973b..HEAD` (build lane; documents in that range are the design
lane's). `git diff --stat 1ba973b..HEAD -- src scripts`: 24 files, +3664/−286.
**Deliverable:** `docs/reviews/T05b-review.md` in the shape of `docs/reviews/T05-review.md` (verdict;
must-fix / should-fix / notes with `file:line` and a falsifiable test; FOR FRANK). Do not edit
`src/`, `tests/` or the design documents; do not commit. Never set `reviewed`.
**Concurrently** a `specifier` rules on `docs/briefs/T05b-rulings.md` (Q-S1…Q-S7); do not re-rule those.

## 1. What was built (where)

| Item | Where |
| --- | --- |
| Saturation band (unit layer) and bisection | `models/syn001/saturation_band.py`, `bisection.py` |
| PH kernel acceptance on the unit's rows; band (β) fallback, route records | `models/syn001/ph_kernel.py`, `tp_state.py` |
| R-007 for degenerate streams + pre-screen | `models/syn001/tp_state.py` (`single_phase_admissible`) |
| Contract v2 (PH-type regimes, TP fallback, seeding), `ZERO_FLOW` regime, dormancy form (D12), swapped-row closure test | `orchestrator/region.py`, `phase_contract.py`, `splits.py`, `revision.py`, `executor.py`, `roots.py`, `trace.py`; `UnitEvaluation.closure` (`models/__init__.py`) |
| Literal v1/v2 | `schemas/solve-policy.schema.json`, `orchestrator/trace.py` |
| Verifier: band twin, degeneracy, zero-flow regularity and label checks, dormancy table, projection (ADR 0013), D2 saturation guard, D3 unresolved band | `verify/saturation.py`, `zero_flow.py`, `projection.py`, `table.py`, `checks.py`, `certificate.py`, `regularity.py` |
| Scripts | `scripts/t05b_ph_baseline.py` (B02 baseline generator), `t05b_degeneracy_margins.py`, `t05b_identity.py` (W8) |

## 2. What was run (numbers in `docs/t05b-measurements.md`)

Gate 2992 + 2 strict xfails (X26 NP-GC, X21 NP-1 — with the specifier). After every chunk:
`thermo/syn001.py` `75c9d5ba…`, K05 identity `622463f5…` (minus `t05` `b364bb3d…`), structural
`4ce030ca…`, check policy `21c44e10…`, T02 floats `9a8a5baf…`, T05 PH baseline bitwise. B07: C1–C3X
equal under v1 and v2. A02 family 179/179 `VERIFIED` under ADR 0013 (15 were false alarms before).
Every registered false success still caught (INJ-B2 re-registered as a correct state PRJ-B2 by the
design lane; INJ-B2′ replaces it). The R-007 pre-screen: 0 decision mismatches over 35 540 gate
calls and a 126 420-call sweep.

## 3. Where the build lane is least sure

1. **`orchestrator/region.py` (+905 lines):** v1 must be literally unchanged (the identity evidence
   says so — check the code paths); the `ZERO_FLOW` regime and dormancy form's openings, outlet reset
   (F7) at a fixed point, closure agreement, swapped-row test; that no path can close `CONVERGED` on a
   state violating a declared row.
2. **R-016 for the new verifier modules** (`projection.py` uses only the verifier's own screened
   matrix/factorization; `saturation.py`, `zero_flow.py` share nothing with the solver) — the AST
   allow-list test exists; check it tests what matters.
3. **The projection (ADR 0013 D1):** that it cannot turn a wrong state into a pass — preconditions,
   exact zeros, which checks are judged at `x̃` and which at `x_final`, the record.
4. **Kernel acceptance and the band route:** residual/Jacobian ↔ evaluator agreement on the band
   route; the fallback records (F1, F2) deterministic and floats-free.
5. **Tests that verify nothing**, and the engineers' logged decisions (`docs/T05_DECISIONS.md` after
   "Frank reverses").

## 4. Do not spend time on

Style; SYN-001 legacy code; the questions in `docs/briefs/T05b-rulings.md`; the evidence manifest
(written after your review).
