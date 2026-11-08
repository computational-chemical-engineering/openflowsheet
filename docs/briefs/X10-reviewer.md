# Reviewer brief: X10 inventory (0.4), the single review pass

Status: brief, 2026-11-07. Roadmap: "X10 inventory: measure which unit × property-basis pairs are refused today ·
nothing · none" (ADR 0056 row 9). Branch `wp/X10`, worktree `.claude/worktrees/x10`, head `c45e8e08`. No `src/` change.
Build log `docs/X10_DECISIONS.md` (D-1…D-7), table `docs/X10-inventory.md`, data `benchmarks/x10/inventory.json`,
generator `scripts/x10_inventory.py` (`--check`), test `tests/test_x10_inventory.py`, manifest
`evidence/X10/18d34648…/manifest.json` (`tested`, 6 limitations harvested as class P).

## The question

Is the inventory a faithful measurement — every admitted model × selectable basis pair probed, each outcome classified
correctly and reproducibly — and are its two open classifications right?

## Measured (engineer's numbers)

30 models (`MODEL_BUILDERS`, `revision_binding.py:1642`) × 5 selectable providers (`selectable_bases()`,
`revision_flowsheet.py:230`) = 150 pairs; CoolProp's 123 fluids represented by R134a (D-1: admission keys on provider
id). Off CoolProp (120): 41 VERIFIED, 1 UNVERIFIED, 2 bound-not-solved (coupled reactors, no experiments, D-4), 76
refused, 0 errors. CoolProp (30): 10 VERIFIED with the extra (CoolProp 8.0.0 from the pinned lock in a scratch dir,
D-3), else `basis_unavailable`; 20 refused. Pumps still refused on Wilson (R-819); `syn001.column` on Wilson VERIFIED
(R-631 lifted for Wilson); turbine GP-M2 fails initialization as registered, a constructed case solves.
`--check` PASS both envs; test 3 passed 37.7 s; F0 PASS; support matrix 0 problems. Full gate: run by the orchestrator.

## Rule on each

1. **`c1.reactor_surrogate` on M04's `benchmarks/m04/c1-surrogate.json`:** the probe (`scripts/x10_inventory.py:456-459`,
   `resolve_policy(DEFAULT_POLICY_ID, …)` + `solve_route`) gives CONVERGED, **UNVERIFIED**
   (`derivative_witness.on_pattern: fail`), while `tests/test_m04_wo7_surrogate_unit.py:605-620` gets VERIFIED with
   M02's `POLICY` (`tests/m02_wo8_support.py`) via `plan_revision`/`verify_revision`. Is the user-path result a defect,
   a policy difference a user meets (then a user-facing limitation, class E, not P), or a probe error? Orchestrator's
   default: class E plus a follow-up item to diagnose, unless you find the probe wrong.
2. **D-2:** eight probe flowsheets use states the engineer constructed (two corrected once against declared limits).
   Are they inside each model's declared domain, and does any refusal/failure in the table come from a bad probe state
   rather than the pair?
3. **D-1** (one CoolProp fluid stands for 123), **D-4** (coupled reactors not solved), **D-5** (whole-matrix test),
   and the class-P harvest of all 6 limitations.
4. Reproducibility: is the hashed part of `inventory.json` free of wall times, paths and environment-dependent text?

## Deliverable

`docs/reviews/X10-review.md`: verdict, must-fix, should-fix, one ruling per item, what the review did not establish.
Commit on **main** (docs-only, named path, message `docs: X10 review`, with the session's Co-Authored-By /
Claude-Session lines from your prompt). Do not edit `wp/X10`. Never set `reviewed`. Report ≤ 30 lines.

## Machine-load rule

TRS2: `uptime` first; targeted runs only (a single probe, `OMP_NUM_THREADS=1`); no full gate (one is running).

## Out of scope

X10 gaps (building the missing pairs), OPT, X02, style.
