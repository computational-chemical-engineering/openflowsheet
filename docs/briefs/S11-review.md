# S11 brief: the package's single `reviewer` pass (design lane)

Branch `wp/S11`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/s11`, head `8d2ee175`; merge base with main
`8c34ecb0` (main merged in at `c7c099dd`). **Read only in that worktree — the full gate is running there and checks
`git status`.** Write the review to
`/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/S11-review.md`; the
orchestrator commits it as `docs/reviews/S11-review.md`. Give exact text for any design-note erratum or register entry (next
free id after R-842 on this branch; R-850+ are E01's on another branch — use R-843…R-849).

## What S11 is

The binding package (Frank: "I want the binding package"; pure-fluid and Wilson units included in S11 by his answer):
- Design: `docs/derivations/S11-design.md` (ADR 0050; §9 and §10 amendments — §10 is the Q9 stage-split ruling) and
  `docs/derivations/S11-units-design.md` (ADR 0051). Batched build rulings: `docs/reviews/S11-rulings.md` (R-830…R-842).
- Build logs: `docs/S11A_DECISIONS.md` (registry, routing, verifier forms, W27 v3, envelope, I1/I1b/I2),
  `S11B_DECISIONS.md` (column in flowsheets, staged splits, column verifier), `S11C_DECISIONS.md` (pure-fluid kernel,
  `thermal.*` units, machines), `S11D_DECISIONS.md` (Wilson γ–φ faces, `wilson-ig-v2`, Wilson flowsheets).
- Manifest `evidence/S11/01e72ca4…/manifest.json`: tested 123/126 (G8, gate, CI unsupported).

## Measured

- `S11-IDENTITY PASS n=54494 changed=[]` (whole-suite decision digests vs `8c34ecb0`); `S08-IDENTITY PASS n=52
  changed=[S02.P1] p1_stage_a=EQUAL`; `S10C-IDENTITY PASS n=858 changed=[]`. `AMENDED_TESTS`: only R-841's three tests.
- S11 tests 1034 passed; column in a flowsheet equals `solve_column` exactly (|Δ| = 0) on 13 cases + recycle; Wilson column
  certificates VERIFIED with the forward five-point witness (R-831; |Z| 63/63/34, one-sided worst ≤ 6.2e-10); pure-fluid
  flowsheets (Rankine, refrigeration, recycle, valve→drum) energy closure ≤ 1.4e-10 W; W27 v3 S4 225/225 rows classify.
- Full gate running now; CI 40610610012 at `8d2ee175`: x86-64 and default-install green; **aarch64 one failure:**
  `test_the_reference_regenerates_byte_for_byte` — `docs/derivations/scripts/s11_thermal_reference.py --check` (CoolProp 8.0.0
  PropsSI values) is not byte-identical on aarch64. Precedent: **R-723** (S10's saturation check: bitwise on x86-64; elsewhere
  pressures within 1e-10 relative, R-627 class T). Rule the S11 equivalent (exact text; which quantities, which classes).

## Look hardest at

1. The Q9 stage-split rule as built (split key vs owner; `splits.region_splits`; `region.py`'s two-line change): identity
   argument sound? Any route where a stage split could be dropped or mis-owned?
2. Two-phase pure-fluid streams (ADR 0051 D1): the carried split, the saturation rows, the closures; `phase_regime_mismatch`
   refusal; the C3-1 kernel fix (R-833).
3. Wilson v2: bitwise forwarding of v1, `provider_id` relabel (R-840), the additive-vapour isentropic block, refusal of the
   pump (no liquid volume).
4. The verifier: the forward-stencil witness (R-831), the column checks (B4: specification checks in linear form, stage
   checks evaluating standalone equations), `gamma_phi_units`, `thermal` checks; **O-C6-1**: the thermal pump's dormant case
   certifies UNVERIFIED/`RANK_DEFICIENT` because `DORMANT_OUTLETS` has no `thermal.*` entries (build default: leave the
   verifier, pin the measured values) — rule it.
5. Registry/admission: 30 models, `_UNADMITTED` texts, R-561 reclassification of S02's 12 U04 harvest items (orchestrator
   default), T08.A32 clause (vi) (R-830), `v2_binder()` restriction (R-837 extension).
6. Tests amended outside §8.3 (each logged): are any weakened?

## Not in scope

E01 (another branch); style; re-running the suite.

## Deliverable

The review file: findings by severity (must-fix before merge / should-fix / note), each with exact text where anything
changes, and a ruling on the aarch64 byte check and on O-C6-1. Report in at most 20 lines.
