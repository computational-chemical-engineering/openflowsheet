# M01 specification — work in progress (halted for budget, 2026-10-06)

**Not a specification.** The specifier's state at the halt, recorded by the session from its final report. Measured
values are **unregistered** probes; tentative decisions are **not decided**. Resume: a fresh `specifier` with
`docs/briefs/M01-specification.md` plus this note. `benchmarks/m01/reactor-probe.json` holds **FAILED** solves at the
nominal point: do not use its numbers. The probe environments (props venv, reactor venv, a fresh clone of the reactor
at `6089593`) were in the session scratchpad and will not survive; recreate them.

## Established (measured, unregistered)

1. An mpmath PR (Ωa = 0.45724, Ωb = 0.07780, κ of 1976, k_ij = 0) with the T08 parameter set reproduces
   `c1-idaes.json`'s separator values: vapour φ to ~1e-15, liquid φ_NH₃ to 3.5e-14, β to 4.7e-12. Both NH₃ cubics at
   268.15 K, 100 bar have a single real root.
2. **The dossier §6 is wrong on one point:** at `6089593` the reactor's density is ideal gas (the PR code in
   `gas_mixture_correlations.molar_density` is commented out); its enthalpy is ideal-gas DIPPR-107 c_p plus
   ΔH_f(NH₃) = −46.12 kJ/mol.
3. The reactor's database holds only H₂, N₂, NH₃; Ar and CH₄ need rows through the `database` config field
   (P0_Ar = P0_CH4 = 0). Five species with zero inerts match the three-species run to 1.1e-6. Cold start at 5 % inerts
   failed for every dt_init 1e-6…1e-1; a warm-start continuation in inert fraction 0→5 % converged (placeholder Ar/CH₄
   rows).
4. The kinetics evaluate their φ correlations at the **sum of reactive partial pressures**, not the total pressure,
   when inerts are present.
5. Grid study, case G2 (no membrane): NH₃ out converges slowly — error at `num_z = 100` ≈ +3.2 % (−3.7 K on T_out);
   at 1600 ≈ 0.1 % (0.13 K), ~7 s. Element-balance defect floor ≈ 2.2e-4 (H), 5.5e-5 (N), grid-independent. Ergun
   ΔP ≈ 640 Pa at 80 bar (ΔP/P ≈ 8e-5).
6. G2's T_in = 623 K lies outside the kinetics' data domain (643–733 K). Cold start fails (lost state) whenever the
   inlet carries real NH₃ (y = 0.03) at 623–673 K, 80–100 bar, every dt_init tried; with the trace NH₃ (1e-9) it
   converges.

## Tentative decisions on brief §6 (not decided)

- PR provider properties `lnphi_<c>`, `h_<c>` (partial molar enthalpies) with derivatives in T, P, n_<c>.
- Root choice by the pseudo-fluid θ = a/(bRT) against θ_c, plus v against v_c ≈ 3.95 b; pure-NH₃ phase by minimum
  Gibbs energy; the two-phase flash a monotone 1D bisection in the vapour NH₃ flow.
- Reference convention `PR-C1-ref-v1` (formation datum), added to the reaction-consistent set without editing SYN-001.
- k_ij = 0 with the sensitivity stated (ChemSep has no H₂–NH₃ pair).
- Sources: T_c, P_c, ω from the reference-EOS papers (via `chemicals` 'HEOS'); c_p from Poling (**rights question for
  Frank**); ΔH_f from ATcT 1.112.
- Pressure: zero-ΔP convention via an implicit booster, p_ret_out = P, refusal above ΔP/P = 1e-2.
- Outlet projected by least-squares extent, inerts exact; duty computed by the process provider, the reactor-side
  mismatch reported; the reactor keeps its own kinetics and thermo.
- W22 can claim pure-NH₃ validation against CoolProp/Gao; mixture VLE data identified, not transcribed: Michels 1950
  (Physica 16:831), Larson & Black 1925.
- The C1 loop units go to M02.

## Resume at

1. The nominal reactor point: a start strategy for an inlet carrying NH₃ (finding 6).
2. Then the generator `m01_reference.py`, `components.yaml`, ADR 0026/0027, register R-154 onward, the spec.
