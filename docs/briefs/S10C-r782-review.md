# S10-C brief: focused `reviewer` pass on R-782 (K03 Newton core: absent-component release at every step)

Branch `wp/S10C`, worktree `.claude/worktrees/s10c`, head `1bc65b86`. Range `b3151d65..1bc65b86` (WO-R1 `f9122cc7`, WO-R2
`e88f72a9`, run log `1bc65b86`). The design is `docs/derivations/S10C-absent-component.md` (architect, `b3151d65`) with the
K03 §5.3 amendment, the R-064 amendment note and R-782; the build log is `docs/S10C_DECISIONS.md` under "R-782
(absent-component release)". The rest of S10-C was reviewed already (`docs/reviews/S10C-review.md`).

## Why

C-MW failed on aarch64: a component absent from every inlet has free flows at exactly +0.0 whose exact Newton step is 0;
roundoff of non-negative sign lifted them to ~1e-15 and they then capped every step (R-064 released them only at
`α_max = 0`). R-782 applies R-064's release, with unchanged exactness conditions, on every step where the released set
meets the step direction. The note's §4.4 theorem says every solve with no such step is bitwise identical.

## What was run (local x86-64)

- Detector (observation-only plugin): `DETECTOR acting_tests=12 acting_iterations=180 released_calls=384` — exactly
  §4.6's 12 tests.
- G-R1 5/5 new tests ((i) and (v) fail on the old code); G-R4: the only new failures at step 1 were A93 ×3 and T07
  record_k[THM-09-4] (plus `test_m07_journey` A21 refusing an uncommitted `newton.py`, gone once committed); full suite
  13225 passed (the 12 failures are `t01_structural`, which fails whenever its file runs alone).
- `S10C-IDENTITY PASS n=858 changed=[]`; `S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL`.
- G-R2 C-MW: 320/320 ulp-perturbed solves and 4/4 OpenBLAS kernels CONVERGED in 9, worst A41 1.29e-7; absent flows +0.0.
- G-R5: A93 uncapped SUCCESS in 245/279/424 calls, capped at 100 → 100/100; T07 THM-09/4 94 records uncapped, 24 capped.
- G-R6: S02+S08 median −1.2 %. G-R7 (local): 13 nominal + 13 holdout starts moved, exactly §4.6's table; 5 F-BUDGET →
  SUCCESS; no regression.
- Running now: CI on `wp/S10C` (G-R3) and a dispatch on scratch `wp/S10C-diag2` (s10c_diag + T06 ensemble on both
  architectures, the CI half of G-R7).

## Look hardest at

- The implementation against §4.1–§4.4: are the exactness conditions literally unchanged (opening and iterate exactly on
  the bound, rows `F == 0.0` exactly, square set)? Does the acting predicate match the theorem's premises? Could the rule
  ever freeze a component that must leave its bound, or hide T02 §6.3.3's disappearance (R-064's rejected alternative)?
- Is the inertness proof sound, and is the detector a faithful witness of "where it acts"?
- The re-pinned witnesses (A93 capped/uncapped, T07 94 + capped leg): does each still test what it was registered for,
  with no tolerance, budget constant or recorded run edited?
- PTC is out of scope (§7 Q1): is that boundary enforced in code?

## Deliverable

`docs/reviews/S10C-r782-review.md`, findings by severity with exact text where anything changes; errata as a dated note in
the design note with register entries after R-782. A docs-only commit on wp/S10C (include this brief). Do not push; do not
set `reviewed`. Report in at most 20 lines.
