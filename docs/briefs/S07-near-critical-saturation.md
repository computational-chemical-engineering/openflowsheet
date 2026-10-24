# S07 — near-critical saturation solve (architect design question)

**Question.** Design a generic, provably-terminating saturation (Maxwell) solve for the S07 CoolProp-HEOS provider
that converges for every admitted fluid at every T it must answer, from T_lo up to T_c (θ = 1 − T/T_c down to at least
1e-6, or a justified θ_min below which a typed refusal is returned), and say whether S05 (`iapws95.py`, same algorithm)
needs the same change. Deliver a design note with a work order and verification gates. No production code.

**Why the architect.** The project's saturation algorithm (S05 §3.5, reused by S07) fails near the critical point for
58 of 123 fluids, including tier-A O2 and H2 — a latent gap in a merged-pattern algorithm, not a local bug. Choices touch
phase logic, the strip (T_σ,max, T_c) semantics, identity (S05's registered values must stay bit-identical at the old
configuration if S05 changes), and both providers.

**Current state.** `src/openflowsheet/thermo/coolprop_heos.py:587-626` `_solve_saturation`: two-variable Newton in
(δ', δ'') on F1 = p/(ρ_red R T) and F2 = g/(RT) (liquid − vapour), seeded by CoolProp's saturation ancillaries
(`pS`, `rhoL`, `rhoV`; decision B-19 uses the EOS T_c in the ancillary's θ), `MAX_ITERATIONS`, returns None if an iterate
leaves ρ' > ρ_c > ρ'' > 0. S05's version: `src/openflowsheet/thermo/iapws95.py:599` `_saturation`, `:640` `_tsat`.
Spec: `docs/derivations/S07-spec.md` §6 (domain, T_σ,max = T_c(1 − 2e-4) row at ~l.262; the strip rule, `_rule`), §16
(Amendment 1: 123 fluids, tier A = 9 cross-checked, tier B = 114 self-consistent only), §17–§18 (R-624, R-625).

**Measured (WO-S07-2b, `docs/S07_DECISIONS.md` l.191–245, Q-B4; scan script `wo2b_near_critical.py` there):**
- 49 of 2626 tier-B cases fail, all `saturation_not_converged`, in 10 fluids: Cyclopentane (from θ = 2e-3),
  R1234ze_Z (1e-3), R134a (5e-4), MDM, MM, R14 (2e-4) at and above T_σ,max; Ethanol, Neon, R114 at θ = 1e-4 strip
  controls; Fluorine at θ = 3.8e-5.
- Cause: near T_c the ancillary seed error is comparable to ρ' − ρ''. R134a at T_σ,max: seed ρ' 5272 vs 5500, ρ'' 4594 vs
  4520 mol/m³ (CoolProp QT flash), width 980; the first Newton step lands at (4278, 4523), outside the bracket.
- Scan θ ∈ {3e-2 … 1e-6}: 58/123 fail at some θ ≥ 1e-6, incl. O2 (θ ≤ 1e-5), H2 (θ = 1e-6).
- Low-pressure side fine (Psat(T_lo) down to 2.65e-6 Pa, Q-A1-5).
- **Tried and rejected:** bracket-preserving step halving — never changes a converged root (bitwise) but rescues none: the
  iteration stalls, or the seed itself is outside ρ' > ρ_c > ρ''.
- Other open items to fold in if cheap: F-6 (A17 floor above 1e-11 for R22 5.6e-11 and PropyleneGlycol); B-15 (bounds
  read relative-or-absolute) — only if your design touches them.

**Constraints.** CoolProp used only as a Helmholtz evaluator at (T, ρ) (ADR 0046); no CoolProp flash on the exact path.
Residual and Jacobian describe the same function at the same state; exact caches key on exact inputs. Where the solve
converges today, the new solve must give the same root bitwise or the design must state and justify the change (S05's
registered records, `s05_reference.json`, the S05 manifest, and S07's tier-A tests are the bit-identity anchors). No
per-fluid tolerances, no silent fluid drops; an unanswerable state is a typed refusal. Pure Python + mpmath for references.

**Settled, not open.** 123-fluid scope (Frank: broad list now); cryogenic liquids wait (S07b); library-only; the T–P box
rule. Option (a) "exclude the 10" is acceptable to the project only if a generic fix is unreasonable — say so with evidence.

**Open.** The algorithm (e.g. continuation in θ from a converged root, critical-scaling seeds ρ' − ρ'' ∝ θ^β fitted
per fluid, symmetric/antisymmetric variables, a ρ_c-anchored bracket for the strip, or a bisection-safeguarded scheme);
θ_min and the strip semantics; whether S05 adopts it (and how S05's identity is proved unchanged).

**Verification.** The scan over 123 fluids × θ grid to 1e-6 all converge (or typed refusal below θ_min); S07 A01–A34 and
tier-B tests; S05 tests and `s05_reference.py --check` bit-identical; mpmath 50-digit roots at near-critical states for a
few fluids as independent expectations.

**Deliverable.** `docs/design/S07-near-critical-saturation.md` (or the repo's design-note directory) on branch wp/S07:
algorithm, termination argument, identity plan, θ_min, the work order(s) ≤ ~100k context, verification gates.
**Out of scope.** Mixtures, cryogenic liquids, binding.
