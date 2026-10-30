# E01 brief: the package's single `reviewer` pass (design lane)

Branch `wp/E01`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/e01`, head `de63b9a2` (contains the finished
S11 at `8d2ee175`; S11's review fixes after that are not in it). **Read only in that worktree.** Write the review to
`/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/E01-review.md`; the
orchestrator commits it. Exact text for any erratum or register entry (next free id after R-867; S11 uses R-843/R-844 on its
branch — use R-868 onward).

## What E01 is

Frank: "I want cost estimation and LCA available, because these are input in process optimization studies." Cost and
life-cycle impact as **post-solve functionals** through the parametric twin with exact Jacobians, usable as NLP objectives/
constraints and in sensitivities; Seider/SSLW correlations transcribed from IDAES 2.13.0 (BSD) with source lines; public
cost indices (BLS PPI, Eurostat, FRB — via FRED copies); LCA as unit scores × inventory, Brightway offline as an optional
`lca` extra, IPCC AR6 GWP100 shipped, no ecoinvent/EF data shipped. Manifest id `S12` (alias of E01, per R-565's precedent).
- Design `docs/derivations/E01-design.md` (ADR 0052) with §9 ruling (ESC-A2…A5, R-863…R-867) and dated errata.
- Build logs `docs/E01A_DECISIONS.md`, `docs/E01B_DECISIONS.md` (each choice is a DECISION line with its alternative).
- Manifest `evidence/S12/d87078af…/manifest.json`: tested 68/73 (A48/G10 release-candidate items; G8/gate/CI before merge).

## Measured

- Cost vs an independent hand transcription of SSLW (mpmath, no `openflowsheet` import): worst 2.29e-15 over 87 cases;
  package and transcription vs IDAES itself 1.0e-14; sizing A10–A12 ≤ 1e-12; capital chain on P1 6.7e-16.
- LCA vs Brightway (float64 path): 2.85e-16; test background vs hand solution 1e-27.
- Sensitivities vs re-solved central differences: ≤ 1e-8 (wrapper), V5 ≤ 9.2e-8; forward vs adjoint 6e-16.
- NLP: SYN-001 `tac` objective → KKT_POINT_VERIFIED from 3 starts, V1–V7 pass; P2 integration case verified from 3 starts.
- Identity: M03 NLP fixture dump byte-identical to the S11 base; `S11-IDENTITY PASS n=54494 changed=[]`; nothing under
  `compile/`, `thermo/`, `models/` changed.

## Look hardest at

1. The post-solve functional design: is "never rows of the compiled problem" sound for optimization (V5 chain rule, V7
   regime-change check, held discrete regimes with admissibility rows)? Can a gradient optimizer be misled at a regime edge?
2. Fidelity of the SSLW transcription and §9.2.2's seven deliberate departures; index conversion (CE 394→500); unverified
   Seider ranges (G10/A48) handled honestly?
3. LCA convention `a_k = amount·φ_k/SI(per)`, electricity net; the restricted-data disclosure: θ values withheld (ESC-B3),
   but **an impact's interval or a single-exchange impact can still reveal a restricted unit score** (logged, unruled).
4. Orchestrator rulings: ESC-B1 (float64 path), ESC-B3, ESC-I1 (A33 over feasible starts only), ESC-I2 (S12 alias), ESC-B2
   packaging (top-level `assessment/` with per-file links, NOTICE), MR-12 tripwire pattern for the `lca` extra.
5. Observation: `AssessmentProgram.build(contributors=None)` builds an empty program without refusing unless contributor
   modules were imported — a silent-success risk?
6. The incident logged in E01A: one early request sent Frank's e-mail as a User-Agent to BLS; data now from FRED. Confirm
   no identifier remains in any committed file or script.

## Not in scope

S11 (reviewed separately); style; re-running the suite.

## Deliverable

The review file: findings by severity (must-fix before merge / should-fix / note) with exact text where anything changes,
and a ruling on item 3's disclosure gap and item 5. Report in at most 20 lines.
