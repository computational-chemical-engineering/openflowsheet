# Design-lane ruling: M02 round 8 — no box qualifies (WO-12a′ stopped at G11v3-4)

Branch `wp/M02` @ `d1b8af1`, worktree `.claude/worktrees/m02`. Round 7: `docs/design/M02-pymrm-adapter.md` §14.6
(E1–E5, R-311…R-314; WO rows ~l.2351). Build log `docs/design/M02-build-decisions.md` D80–D87 (l.93–100; **D84**, **D85**,
**D87**). Records: `benchmarks/m02/g11-coverage-v3.json`, `g10-adapter-halves-v3.json` (python for fields, never cat).
ADR 0027 Amendment 3 (`6145b48`, E5 text verbatim).

## Facts
- G10v3 met (all outlets and `defect_round1` bitwise v2's; round 2 ran nowhere). G11v3-1,2,3,5,8,9,10 met; the six
  former `nonpositive_flow` corners now `ok`.
- G11v3-4 not met: V1 19/21, V2 19/21, V3 20/21 (11 MPa, H₂/N₂ 2.5). Every failure is a 653.15 K, high-pressure,
  **2 % inert** corner ending at `S1` (S1 runs before every E1/E2 change; 400 steps). M05's 653.15 and 693.15 K points
  are `ok`. Timeout rule: V3 390 s, V1/V2 420 s.
- Q-E1: loop reactor-inlet inert fraction 4.047 % at 693.15 K; 4.548 % at 653.15 K (the latter converges only with
  v3's child; under v2 it refuses `element_balance_defect`).
- D85: E1 assumed no point has a failed first certificate with δ₁ > 1e-7; there are 2. `corner-T773.15-P5e+06-r4-i0.2`
  was `ok` under D78 (round 2 unconditional) and now ends `certificate`.
- Amendment 3's fourth bullet ("v3's domain is the first of V1–V3") now contradicts D84.

## Decide
1. The shipped box (N7). Session default to evaluate first: keep T_in [653.15, 693.15] K (M05's REAL box) and V3's
   P/H₂N₂ ranges, and narrow composition — raise `inert_min` (the loop runs at 4.0–4.5 %), e.g. registered candidates
   0.03 then 0.035 — since every failure is a 2 % corner. Or another narrowing you can defend. Register the ordered
   candidates and the stop rule as before; say what must be re-measured (only the new corners?).
2. D85: run round 2 after a failed first certificate (D78's ordering) or keep E1 as ruled; effect on G10v3 bitwise.
3. Fix Amendment 3's fourth bullet (write ADR 0027 Amendment 4 yourself, or an erratum — you may edit the ADR).
Frank holds N7; give the default you recommend in one line for him, and whether WO-12b can proceed on it before he
answers (reversible: the variant is append-only).

## Deliverable
§14.7 + register entries (next after R-314; check `wp/M02` and `main`); ADR 0027 text as needed. Commit on `wp/M02`
(doc only, named paths). Another engineer works on `wp/M02-wo14`; don't touch it. Report ≤ 250 words.
