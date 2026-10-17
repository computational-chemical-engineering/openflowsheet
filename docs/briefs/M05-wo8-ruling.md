# Design-lane ruling round: M05 after WO-8 (F-15, G9, S47–S52)

`wp/M05` @ 04454d7 (worktree `.claude/worktrees/m05`). Design note `docs/design/M05-trust-region.md` (gates G5–G10 ~l.822–829,
TRF config / D-table, rulings §16–§19, register through R-389). Build log `docs/design/M05-build-decisions.md` S45–S52
(l.429–460). Diagnosis: **`docs/design/M05-F15-diagnosis.md`** (read it in full; 99 lines). Handoff `docs/briefs/M05-wo8-handoff.md`.
Script `scripts/m05_wo8_runs.py` (3–4 s per run, nlp env `m05/.venv-nlp`). Never move a tolerance or limit on the outcome
alone; say what independent reason justifies any change.

**Measured at WO-8:** G10 PASS (3 replays, 0 diffs). G5 FAIL: TR-E2 `TRF_MAX_ITERATIONS` (30), θ_recheck 4.01e-4, T* 673.6673 K
vs T_ref 673.6434 K. G6 FAIL on `TRF_CONVERGED` only (θ 4.37e-4; fd_check pass at 2⁻¹⁴; |T*_FD − T*_E2| 1.1e-5 K). G9 FAIL:
LOOP-R converged, θ 1.14e-7, DECISION_STABLE, |T* − 653.15| = 1.067e-6 K vs 1e-6 K (5.3e-8 scaled ≈ Ipopt's interior distance
from the bound). G7 partial (no store-bijection check yet). G8 not run.

**Diagnosis summary (F-15):** affine basis has no T-curvature → first solve jumps to the box corner (693.15 K, 20 K from the
optimum); every step is the full radius, θ = C·Δ² (C 0.27→0.775); TRF's radius rules hold θ near minimum_feasibility 1e-4
(halve above, ×2.5 below), so 30 iterations are spent travelling; termination at ≤ 1e-5 is luck (k = 28 nearly accepted
θ 1.03e-5 at 0.66 K off). Refuted: criticality step (none in Pyomo 6.10.1), θ scaling mismatch, solver floor, FD noise.
Scratch 150-iteration run: TR-E2 exits k = 35, θ 9.72e-6, T 673.596 K; TR-E2-FD θ 4.09e-6.

**Rule on:**
1. **F-15 / G5 / G6:** what changes — the start (basis with curvature, a different x₀), the iteration budget, the
   convergence criterion (step test meaningless when every step equals the radius; rely on stage-B P2?), the clash
   between the 1e-4 radius band and the 1e-5 termination — and the restated G5/G6 criteria with numbers. Note the k = 28
   near-false-convergence: whatever you choose must not accept a point 0.66 K off as converged.
2. **G9:** the 1e-6 K bound-distance tolerance vs the interior-point distance from the bound.
3. **S51** (blocks committing TR-E2's record): a parent holder charges budget at admission even when the request is a
   store hit (`cold_used` 48 ≠ 31 + 16). **S50:** the FD check's 21 cold requests belong to no run/budget.
4. **S52 / G8:** stage A needs `SurrogateTruth` (§6.4), the promoted-surrogate link basis (§6.6) and stage A's P2 reference —
   none implemented. Is that a missing work order (state it), or is G8 re-scoped?
5. **S47, S49:** confirm or reverse (assumption blocks; G9's "constant basis" read as R-277's affine basis).

Write **§20** of the design note with the new WO items and restated gate criteria; register entries **R-400…R-409** (check `docs/decision-register.md` and origin/main for collisions). No production code. Commit on wp/M05,
named paths, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` /
`Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`, push. Report ≤ 300 words: one line per ruling,
the build work orders, anything that needs Frank (in plain words).
