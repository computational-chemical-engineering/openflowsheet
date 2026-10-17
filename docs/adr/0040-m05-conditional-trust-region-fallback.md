# ADR 0040 — M05, conditional: if the Pyomo trust-region route cannot be used, a scipy-only reduced-space trust-region model management over certified simulations replaces it, claiming no tested-framework guarantee

**Status:** **Conditional**, Proposed 2026-10-09. **Inactive.** It is activated only by a trigger recorded in
`docs/progress.md` with its evidence. If M05 closes without a trigger it is marked `Withdrawn (not needed)`.
**Author:** design lane (`architect`), M05.
**Normative text:** `docs/design/M05-trust-region.md` §10.
**Register:** R-272.
**Amends:** if activated, ADR 0038 D10 ("no other optimizer is substituted") for the distributed product.
**Affected requirements:** A06, D13, W24 (plan L271: "document the failing composition and implement an ADR-backed
tested alternative before claiming that gate").

## Context

ADR 0038 composes Pyomo 6.10.1's TRF with OpenFlowsheet models. A probe found no obstacle. Three things could still
stop it, and plan L271 requires a ready alternative.

## Decision

**D1. Triggers.** Exactly these:
- **T1.** Frank denies N1 (the `nlp` extra).
- **T2.** A recorded composition failure that the registered remedies cannot fix. Either G4 fails for a structural
  reason, or at least 2 of the 4 in-process configurations (TR-E2, TR-E2-FD, LOOP-S, LOOP-R) end
  `FAILED(trf_aborted…)` after the retry.
  *Ruled 2026-10-09 (R-279):* probe P14's abort, from TRF's default b ≡ 0 (a configuration ADR 0038 D7 rejects),
  and its two mislabelled exits do not count toward T2. A `PROJECTION_IMPLICIT_EF_INPUT` refusal on C1's own
  formulation would.
- **T3.** The TRSP audit extension (G1) fails, and the cyipopt-shim contingency of ADR 0038 D4 also fails to reproduce
  TR-E1 within 1e-8.

**D2. Algorithm.** It uses only scipy and numpy (the project environment). It is reduced-space, first-order-consistent
trust-region model management (Alexandrov, Dennis, Lewis & Torczon 1998), over the scaled decisions u ∈ [−1, 1]^{n_d}.

- **High-fidelity J_hi and g_hi**: from the parent-backed certified coupled solve.
- **Model.**
  - With a promoted surrogate: m_k(u) = J_lo(u) + [J_hi − J_lo](u_k) + [∇J_hi − ∇J_lo](u_k)ᵀ(u − u_k), with J_lo from
    the surrogate-backed certified `revision_eo` solve.
  - Without one: m_k(u) = J_hi(u_k) + ∇J_hiᵀs + ½sᵀB_k s, with B_k by damped BFGS (B₀ = −I in scaled units).
  - Constraints get the same corrections.
- **Gradients.** ∇J_hi by central differences of coupled solves at ±δ_j (reusing the poll points); ∇J_lo by central
  differences of surrogate solves at h = 1e-3 scaled.
- **Subproblem.** `scipy.optimize.minimize(method="SLSQP")` on the box ∩ {‖u − u_k‖_∞ ≤ Δ_k}.
- **Acceptance and radius.** ρ = (J_hi(u_t) − J_hi(u_k)) / (m_k(u_t) − m_k(u_k)). Accept iff ρ ≥ 0.1 and P1 and P3
  pass. If ρ < 0.25, Δ ← ½‖s‖; if ρ > 0.75 with the step at the boundary, Δ ← min(2Δ, 1). Δ₀ = 0.25.
- **Stop** when Δ < δ/2 in scaled units, then apply the parent checks P1–P5.
- **Shared with ADR 0039:** checks, statuses, budgets, accounting and records. Runs are recorded with
  `runs[].stage = "F"` and `claims.trf_theory = "not_applicable"`.

**D3. Claims.**
- **May claim:** an empirical, first-order-consistent model management with parent checks at the decision tolerance,
  and complete accounting.
- **May not claim:** "a tested trust-region framework" (D13), or a convergence guarantee. Its gradients are finite
  differences of tolerance-limited coupled solves, and Alexandrov et al.'s theorem needs exact gradients of a C^{1,1}
  function.
- If activated by T1, W24's statement reads: "trust-region adapter: Pyomo TRF tested in the audited environment but not
  distributed; distributed route: ADR 0040".

**D4. Gates, if activated.**
- **F1.** TR-E2's formulation with the fallback reaches |T* − T_ref| ≤ 0.5 K, with candidate status
  `PARENT_LOCAL_EVIDENCE`.
- **F2.** LOOP-R gives `DECISION_STABLE` with |T* − 653.15 K| ≤ 1e-6 K.
- **F3.** The accounting identities of ADR 0039 D6 hold, with the TRF-specific request identity replaced by:
  coupled solves = 1 per trial plus 2n_d per accepted iterate.

## Alternatives considered

- **No fallback.** Rejected by plan L271.
- **A re-implementation of Yoshio–Biegler's filter TRF over the same Pyomo projection.** Rejected: it keeps every
  dependency of the failed route (T1, T3) while losing the "tested framework" claim.
- **A derivative-free method (pattern search alone).** Rejected as the optimizer: on a 25–45 s truth it costs more
  coupled solves per decimal of precision than a corrected model. It survives as the poll of P5.
- **Bayesian optimization.** Out of scope (brief §11).

## Consequences

If activated, the cost per accepted iteration is 1 + 2n_d coupled solves (12–24+ experiments for n_d = 1), against
ADR 0038's 8 experiments. The REAL budget of ADR 0039 D5 is then likely to bind, and the study reports
`BUDGET_EXHAUSTED` honestly if it does.

## Migration

None.

## Acceptance evidence

F1–F3, only if activated.
