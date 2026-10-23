# S07 brief: rule on A31 (cross-architecture) after aarch64 missed the pre-registered bound

Design lane (`specifier`). Branch `wp/S07`, worktree `.claude/worktrees/s07`, head `95f8f9a5`.

## 1. The question

aarch64 is not bit-identical to x86-64, and it misses Q-1's pre-registered bound. What bound, or bounds, does A31
use instead, and on what derivation? The answer must let a build-lane engineer finish A31 without choosing anything.

## 2. Why it needs the design lane

Spec §11 Q-1 (S07-spec.md l.467–476) says: "If the measured worst exceeds 1e-12, nothing is loosened: the build lane
stops and the design lane amends." §16.11 (l.1065) sets tier B's stop line at 1e-10 under the same rule. Both were
crossed. The premise behind them is that ulp-level jet differences are amplified by κ_ρ ≤ 100. That premise is false
near the critical point, and possibly also for tier A away from it.

## 3. Measured facts (CI run 39979785654, head 95f8f9a5)

- x86-64: "S07 A31 (x86_64): bit-identical". The digest `benchmarks/s07/platform_digest.json` was generated on x86-64.
- aarch64: "not bitwise, FAILS; worst 2.243e-08 (R22 a10.T_sigma_max.LIQUID.cp)". The ratio is
  |Δ| / max(|x|, s_f), with s_f being A17's scale.
- Worst per quantity on aarch64, all 123 fluids, both tiers mixed:

| quantity | worst | quantity | worst | quantity | worst |
|---|---|---|---|---|---|
| a10.LIQUID.cp | 2.24e-8 | a10.VAPOR.cp | 2.17e-8 | a10.VAPOR.v | 6.41e-10 |
| a10.LIQUID.v | 5.07e-10 | a10.dT (dPσ/dT) | 4.96e-10 | a10.VAPOR.Z | 1.91e-10 |
| a10.LIQUID.Z | 1.23e-10 | a10.VAPOR.h | 1.18e-10 | a10.LIQUID.h | 9.50e-11 |
| a10.VAPOR.s | 7.93e-11 | a10.LIQUID.s | 6.29e-11 | a10.Psat | 1.61e-11 |
| tp.s | 1.84e-11 | sat.dT | 1.41e-11 | tp.h | 1.22e-11 |
| tp.cp | 5.54e-12 | tp.dT.cp | 5.45e-12 | tp.dP.cp | 4.29e-12 |
| tp.dT.v | 3.47e-12 | tp.dP.Z | 2.67e-12 | tp.dP.v | 2.33e-12 |
| tp.dP.h, tp.dT.Z | 1.98e-12 | tp.dP.s | 1.95e-12 | sat.Psat | 1.59e-12 |
| tp.dT.h, tp.dT.s | 1.53e-12 | tsat.dP | 1.26e-12 | lnφ (R22) | 1.07e-12 |
| band.cp | 9.32e-13 | band.h | 6.10e-13 | a12.16.s | 4.03e-13 |
| phi.slot | 3.88e-13 | band.s | 2.66e-13 | tp.v | 8.49e-14 |
| tp.Z | 2.33e-14 | tsat.Tsat | 3.12e-15 | a12.0.u | 4.86e-15 |

- The CI log printed only the first 20 failures (`scripts/s07_platform_digest.py` l.302 truncates at `[:20]`). They are
  in H2O and CO2 (tier A):
  - H2O `tp.L_corner`: dT.cp 5.45e-12, dT.v 3.47e-12, dP.cp 1.45e-12;
  - H2O `sat.sat_hi.dT` 1.41e-11; CO2 1.26e-11;
  - H2O `a10.T_sigma_max`: LIQUID cp 1.63e-9, v 3.16e-11, Z 6.4e-12, h 7.8e-12, s 5.7e-12; VAPOR cp 1.45e-9,
    v 3.85e-11, Z 1.0e-11, h 1.0e-11, s 7.6e-12; dT 1.41e-11;
  - CO2 `a10.T_sigma_max`: LIQUID v 2.43e-11, h 8.0e-12, s 6.1e-12.
  - Which tier the tp.s 1.84e-11 and tp.h 1.22e-11 worsts belong to is not in the log.
- T_σ,max = T_c(1 − 2e-4), so θ = 2e-4 there. `sat_hi` is the top of the saturation registered states.
- All other aarch64 tests pass: 14635, including A45–A50.

## 4. Constraints and what is already decided

- Bit-identity stays the target (R-622). The digest stays an x86-64 regression fixture, not validation.
- No reference assertion may change verdict between architectures. A05/A08–A10 compare with 1e-8. A ruled A31 bound
  that is at or above a reference tolerance must say why that verdict cannot flip, or exclude that answer from A31
  with a stated reason.
- Precedent for near-critical bounds: R-626 re-set G3 (A47) for θ_min ≤ θ < 1e-2 to densities 3e-8 (≈ 2√ε, R-595's
  floor clause) and p_σ 1e-10, from a derivation rather than a measurement.
- CoolProp 8.0.0 is a pinned wheel per architecture; the wheel SHA-256s are in `requirements-coolprop.lock`. Our
  Python code is the same on both architectures.
- Settled and not open: the fluid list, tiers, θ_min, T_σ,max, the near-critical fallback, the jet-only use of CoolProp.

## 5. What is open (rule on each)

1. The A31 bound for the near-critical answers: A10 at T_σ,max, `sat_hi`, and any band or near-critical-box answer
   with θ < 1e-2. Should it be derived from the local conditioning (for example κ computed per state, or G3's θ
   rule), and is cp handled separately from v, Z, h, s and dPσ/dT?
2. The A31 bound for the remaining tier-A answers. The measured values are 1.4–5.5e-12 at H2O's L corner, against
   1e-12. Is the "few ulp" jet premise wrong (for example from libm differences in exp/log/pow), and what bound
   follows?
3. Tier B: does 1e-10 stand outside the near-critical class? The measured worst there is 1.84e-11, below it.
4. The A31 verdict wording and what ADR 0046's status line states.
5. Whether `--report` must list every failure. Recommended: yes, all failures go to a JSON artifact, and the log shows
   counts per class plus the top 20.

## 6. How it will be verified

The build lane implements the ruling in `tests/test_s07_registration.py` (A31) and `scripts/s07_platform_digest.py`,
pushes, and reads the aarch64 job once. If any answer exceeds the ruled bound, the build lane stops again; nothing is
loosened. x86-64 must stay bit-identical.

## 7. Deliverable

- A spec amendment: a new §20 in `docs/derivations/S07-spec.md`, with a pointer from §11 Q-1 and §16.11. It contains
  the derivation, a bound per answer class, a mechanical rule for which answers fall in which class, and the verdict
  text.
- A register entry R-627 in `docs/decision-register.md`, with the rejected alternative.
- Commit it on `wp/S07`, docs-only. Report in at most 30 lines.

## 8. Out of scope

Changing the solver, the fallback, T_σ,max, or any reference tolerance; the T08 C3 failures in "Run checks", which
clear after the harvest; the manifest; the full gate.
