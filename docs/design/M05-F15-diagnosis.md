# M05 F-15 diagnosis — TRF's θ sawtooth on C1 TR-E2 (build lane, diagnosis only)

2026-10-16, wp/M05 @ 6a9d29d. No source, limit or tolerance change. Gates G5/G6 stay FAILED.

**Method.** A scratch driver (not committed) imports `scripts/m05_wo8_runs.py`, wraps Pyomo 6.10.1's
`TRFInterface.solveModel` / `updateSurrogateModel` (monkeypatch, pinned files untouched) to log, per TRSP, the
decision before and after, its TR bounds, the step, θ and every EF output's |y − d(w)|, and runs `run_case`. The
wrapped run is inert: TR-E2 gives the same `TRF_MAX_ITERATIONS`, θ_recheck 4.01e-4, T* 673.6673361700024 K as
the build-log S-entry. A second scratch run sets `maximum_iterations = 150` inside `trust_region_method` (scratch
only, to test reachability). d is the scaled decision, T = 673.15 + 20 d K; T_ref = 673.6434 K is d_ref = 0.0247.

## 1. Table (TR-E2, every iteration's trial point; all steps accepted, 0 rejections)

| k | type | d after | d − TR lb | step = Δ_{k−1} | θ (trial) | θ/step² | link share of θ |
|---|---|---|---|---|---|---|---|
| 0 | PMP | 0.999999 (box ub) | — | 1.0 | 5.25e-1 | — | 99 % |
| 1 | θ | 0.749999 | 1.2e-8 | 0.2500 | 1.32e-1 | 2.1 | 15 % |
| 4 | θ | 0.531250 | 2.4e-8 | 0.03125 | 4.54e-4 | 0.46 | 28 % |
| 5 | θ | 0.515625 | 3.3e-8 | 0.01562 | 7.00e-5 | 0.29 | 13 % |
| 6 | f | 0.507812 | 3.0e-8 | 0.00781 | **1.62e-5** | 0.27 | 15 % |
| 7 | f | 0.488281 | 3.3e-8 | 0.01953 | 1.06e-4 | 0.28 | 26 % |
| 8 | θ | 0.439453 | 2.9e-8 | 0.04883 | 7.63e-4 | 0.32 | 47 % |
| 16 | f | 0.309947 | 9.4e-8 | 0.00477 | **1.33e-5** | 0.58 | 86 % |
| 23 | f | 0.123882 | 2.0e-7 | 0.00466 | **1.65e-5** | 0.76 | 97 % |
| 27 | θ | 0.061319 | 4.7e-7 | 0.00727 | 4.10e-5 | 0.775 | 99 % |
| 28 | f | 0.057683 | 5.6e-7 | 0.00364 | **1.03e-5** | 0.776 | 99 % |
| 29 | f | 0.048592 | 6.3e-7 | 0.00909 | 6.43e-5 | 0.778 | 98 % |
| 30 | f | 0.025867 | 8.7e-7 | 0.02273 | 4.01e-4 | 0.777 | 99 % |
| 31* | f | −0.030926 | 2.1e-5 | 0.05679 | 2.49e-3 | 0.772 | 99 % |
| 32* | θ | −0.002530 | ub − d 4e-7 | 0.02840 | 6.19e-4 | 0.768 | 99 % |
| 35* | θ | 0.022310 | ub − d 2.5e-6 | 0.00355 | **9.72e-6** | 0.773 | 100 % |

\* the 150-iteration scratch run (identical to k = 30), which exits `TRF_CONVERGED` after k = 35 at
T = 673.5962 K (|ΔT| = 0.047 K), θ_recheck 9.72e-6. TR-E2-FD: the same d trajectory to 6 digits; θ larger late
(θ/step² 0.85–1.21: the FD gradient error adds a first-order term, ≈ 5.7e-6 at k = 28); with 150 iterations it
also converges after k = 35, θ 4.09e-6, T 673.5962 K. "Link" = `ef_ext_0/1` (the reactor truth); output
`ef_ext_0` alone carries 71 % of θ at k = 11, ≥ 96 % from k = 21, ≥ 98 % from k = 26; at k = 1..8 the 9 block EFs carry 53–87 %.

Σ steps k = 1..30 = 0.974 (mean 0.0325). Objective decreases monotonically: the iterate never passes d_ref
before k = 30.

## 2. Mechanism

1. **The start is a box vertex.** Pyomo's `initializeProblem` solves the PMP with `y = b(w)` over the full
   decision box. With R-277's affine Taylor basis the PMP has no curvature in T, so its optimum is bang-bang:
   d = 1 (693.15 K), 20 K from T_ref. LOOP-R's optimum *is* a vertex (653.15 K), so its PMP lands on it and TRF
   converges in 3 iterations with step ≈ 1e-7 — that is the only reason LOOP-R and TR-E2 differ.
2. **Every TRSP step is the full radius.** With an affine b, r_k = d(w_k) + ∇d(w_k)(w − w_k): the basis cancels,
   and the model is the truth's first-order Taylor expansion. The interior optimum in T exists only through the
   truth's curvature (X ∝ exp(−z_T²)), which r_k drops, so the TRSP is a linear problem in d and its solution
   sits on the TR bound in every iteration (d − lb ≤ 8.7e-7 for k = 1..30, i.e. Ipopt's interior offset; after the overshoot
   at k = 31 it sits on ub). Hence step_k = Δ_{k−1} and θ_trial = C·Δ², C = ½ the truth's curvature along
   the path (0.27 → 0.775; exactly ×6.25 for ×2.5 radius, ×4 for ×0.5).
3. **TRF's radius rules regulate θ to the band around `minimum_feasibility` = 1e-4.** A θ-type step taken while
   θ_prev > 1e-4 sets Δ = γ_c·s = Δ/2 (all 18 θ-steps here); once θ_prev ≤ 1e-4 the switching test
   (Δf ≥ 0.1·θ_prev², i.e. ≥ ~1e-9 against measured Δf ≥ 1.3e-5) makes the step f-type and Δ = max(2.5 s, Δ).
   Pyomo 6.10.1 has no ratio test on f-steps and no criticality step. The cycle is deterministic:
   halve until the first trial θ_L ∈ (2.5e-5, 1e-4], halve once more (trough θ_L/4 ∈ (6.25e-6, 2.5e-5]),
   then ×2.5 until θ > 1e-4. Measured θ_L: 7.0e-5, 6.2e-5, 5.2e-5, 6.6e-5, 4.1e-5 → troughs 1.62e-5, 1.62e-5,
   1.33e-5, 1.65e-5, 1.03e-5 (each exactly θ_L/4).
4. **So Δ ≈ √(1e-4/C) ≈ 0.01–0.02 and the transit of 0.97 takes the whole budget.** At k = 30 the iterate has
   just reached d_ref; 30 iterations are spent travelling, not converging.
5. **Termination is a phase lottery, not stationarity.** The exit needs trial θ ≤ 1e-5 with step ≤ σ = 0.0125.
   Because step = Δ always, the step test is met by a small radius, never by a stationary model, and the θ test
   is met when a trough θ_L/4 ≤ 1e-5, i.e. θ_L ≤ 4e-5 — about a third of cycles (log-uniform phase), *wherever
   the iterate is*. k = 28 missed by 2.6 % at T = 674.30 K (0.66 K from T_ref, above the 0.5 K decision
   tolerance); k = 16's trough was at 679.35 K. Had either landed, the record would read `TRF_CONVERGED` at a
   point that is not the optimum. The 150-iteration "convergence" at 673.596 K is the same lottery, won near
   d_ref, still on the TR bound.

## 3. Hypotheses

| | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| a | θ floor = model mismatch at the reachable radius, radius re-enlarged after accepted steps | **Survives, restated** | θ = C·Δ² to 1 % over 1e-5..2.5e-3; f-steps ×2.5 whenever θ_prev ≤ 1e-4 (12 of 30). Not "basis error": the affine basis cancels in r_k; it is the Taylor remainder of the truth, and the basis acts only through the PMP start |
| b | a compatibility/criticality check keeps enlarging Δ | Refuted as stated | No such step in Pyomo 6.10.1 `TRF.py`; enlargement is the f-type rule (3 above) |
| c | θ measured on different scaling than the termination test | Refuted | θ_logged = θ_recheck = 4.0128e-4 (same expression, same 11 outputs); outputs are O(1) scaled |
| d | Ipopt tolerance / bound handling floor near 1e-5 | Refuted | No floor: k 27→28 θ ratio 3.995 for step ratio 2.0004; 9.72e-6 and 4.09e-6 reached; trial offset from the TR bound ≤ 2.5e-6 |
| e | noise/FD in the truth | Refuted as cause | TR-E2 (analytic) fails identically; FD only shifts θ by ~5e-6 late |
| new | PMP vertex start + full-radius steps (2.1, 2.2) | **Primary** | PMP d = 1; d − lb ≤ 8.7e-7 at every trial; Σ steps 0.974 ≈ distance to d_ref |

## 4. Is 1e-5 reachable?

Yes — there is no floor. θ falls with Δ² and needs Δ ≤ √(1e-5/0.775) = 3.6e-3 (0.072 K) near T_ref, which the
radius lattice reaches at a trough; with 150 iterations both TR-E2 (9.72e-6) and TR-E2-FD (4.09e-6) exit after
k = 35. Within 30 iterations it is not reachable from this start: the run only arrives at d_ref at k = 30.

## 5. What a fix has to address (for the design lane; nothing chosen here)

1. **The start.** The PMP with an affine basis puts x0 at a box vertex for any interior optimum. Either the
   basis must carry curvature in the decision, or TRF must not start from the PMP point (Pyomo 6.10.1 always
   solves the PMP; the pin forbids patching it), or the budget must cover the transit (~L/0.03 iterations).
2. **The step-size test.** With an affine model in the decision the TRSP step equals Δ, so ‖s‖ ≤ σ says nothing
   about stationarity, and `TRF_CONVERGED` can fire mid-transit (shown above: 0.66 K off was 2.6 % away). Any
   convergence claim on C1 needs evidence other than TRF's exit — stage B's P2 — or a model with curvature
   so that interior TRSP solutions exist.
3. **The θ band.** `minimum_feasibility` = 1e-4 with γ_c = 0.5, γ_e = 2.5 fixes the trough in (6e-6, 2.5e-5];
   `feasibility_termination` = 1e-5 sits inside that band, so hitting it is chance. A change of either value is a
   registered-config change (§6.7), not a build-lane choice.
