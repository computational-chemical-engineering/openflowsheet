# M02 reviewer pass (the package's single review; also the last ruling batch)

Branch `wp/M02` @ `f4e8c56`, worktree `.claude/worktrees/m02`. Range `950bd78..f4e8c56` (80 commits; src: 63 files,
+12k lines). Design note `docs/design/M02-pymrm-adapter.md` (rulings §14.1–§14.7; WO table l.700 and the §14.x rows).
Build log `docs/design/M02-build-decisions.md` (one line per D-entry; grep by id). Register R-220…R-237, R-250…R-259,
R-280…R-289, R-303…R-316. ADRs 0027 (Am. 2–4), 0033–0035. Write the review to `docs/reviews/M02-review.md` (pattern:
`docs/reviews/M01-review.md`) and commit it on `wp/M02`.

## What was run (all on this machine; gate = scripts/check.sh via scripts/gate.sh)
- Gate at `ba13ce3` (after WO-14 merge): 8304 passed, 1 xfailed (RP-2). WO-12b gate: 8348 passed, 1 xfailed.
- G2 corpus dump byte-identical throughout (659748576adb9730…); MCP tool-list digest unmoved (383b4e2c…).
- G8 stand-in loop: CONVERGED k = 1, VERIFIED; 62 vars within 3.0e-14 of the independent oracle (`tests/m02_loop_oracle.py`).
- G8 (f) f1–f5 vs an independent Broyden replica (`tests/m02_broyden_replica.py`) to 1e-9.
- G10v3 bitwise vs v2 (8/8 outlets, `defect_round1`); G11v3 two runs identical, V5 21/21, V4 20/21; timeout 450 s.
- G12 under v3: 3 outer iterations, ρ 0.292, VERIFIED, replay MATCH bitwise, live rerun bitwise; G12v3-2 both
  T edges CONVERGED/VERIFIED, inert fraction 0.0455/0.0405 (floor 0.035).

## Where we are least sure (spend the time here)
1. Coupling driver `orchestrator/coupling.py` (Broyden, reset window R-305, clipping at X̂ = 0) and the EXT-COUPLING
   certificate items; whether the floors (§4.2, D53 projected outlet) make the convergence claim honest.
2. v3 child `adapters/pymrm/child.py`: δ after the certificate, round 2 trigger (R-311 → R-316), present-species
   positivity/defect (R-312) — does the residual the boundary judges equal what the child certifies?
3. Replay identity: D8/R-308 shape rule, D94 (extended to all final-digest copies), run class R-307.
4. Replacement facets `application/replacement.py` + `inert_min` in hard-domain checks (R-315).
5. Whether any test asserts a self-generated output as correctness (CLAUDE.md "Scientific conduct").

## Rule on (batched open items; one line each, with the implementing change)
- RP-2 (strict xfail): rerun whose final X̂ moves in last bits → MISMATCH via (a) EXT-COUPLING "request inputs are not
  the certified state's inlet bit for bit", (b) ρ, r_ξ compared to the record's exact 0 at 1e-9 relative, no floor.
  Engineer proposal: check against the request recomputed at the rerun's inlet; τ-scaled floors.
- D94 keep or revert; "AC-1" meaning (engineer read it as D9's acceptance); f5 lacks an end-to-end
  `COUPLING_NOT_CONVERGED` test — required?
- D100–D102, D105, D110–D115 build choices: ratify or reverse. D112 G9 (a1) detail lists `temperature_K`, `pressure_Pa`.
- `benchmarks/m02/c1-reactor.json` still names v2 — re-point or leave?
Also confirm the envelope/docstring items of R-310 are in WO-13's scope.

## Not to spend time on
WO-1…9's already-reviewed pieces unless the later WOs touched them; formatting; the W27 registration.

## Deliverable
Findings ranked (must-fix / should-fix / note), each with file:line and a concrete failure scenario; rulings above;
verdict on whether WO-13 may mark the manifest `tested` once must-fix items are done. Do not set `reviewed` anywhere.
Report ≤ 300 words.
