# S10 build decisions

Build-lane choices the specification (`docs/derivations/S10-spec.md`, ADR 0047) left to the engineer. One line
each; each is isolated and revertible. Measurements go in the run log below.

## WO-S10-1 (spec §5.1-§5.3, §7.5 A01-A11, A23, A24-A28)

- DECISION B-1: what `flash()` does before WO-S10-2 → refused `unsupported`, message `flash_not_implemented: …`, no outlets, while `describe().flashes` already says `("TP",)` (A01 requires §5.2's value). Alternative: omit `flash` (breaks `isinstance(…, PropertyProvider)`) or declare `flashes=()` until WO-2 (fails A01). Reversible by: WO-S10-2 replaces the method and its test `test_the_flash_is_refused_until_wo_s10_2` (`647ce9a9`).
- DECISION B-2: loader cases §5.1 does not name → a parameter value that is not a finite number is `record_structure`; a Λ entry naming an unknown component is `record_lambda`; a P domain with lower bound ≤ 0 is `record_domain` (ln P); component keys required = ComponentRecord's required keys + `synthetic`, allowed = ComponentRecord's properties; Λ entry keys `i, j, value` (+ `provenance`). Alternative: no check (a crash or `math domain error` later). Reversible by: editing `_parameter`, `_lambda`, `_bounds` in `thermo/wilson_ig.py` (`647ce9a9`).
- DECISION B-3: where the U02 library-only text lives before S10 has a manifest generator → `U02_LIBRARY_ONLY` in `tests/test_s10_provider.py`, with a test that it and every harvested S10 U02 note name `` `wilson-ig-v1` `` and library-only. Alternative: a stub `scripts/s10_evidence_manifest.py` now. Reversible by: the manifest generator takes the string over and the test reads it from there, as S07's does (`9211297d`).
- DECISION B-4: ∂ln φ_i^L/∂n_j → the general projection (G_ij − Σ_k x_k G_ik)/n_tot of spec §3.6, not the shortcut (G_ij + 1)/n_tot (equal by ID-ROW). Alternative: the shortcut. Reversible by: one line in `evaluate_phase` (`647ce9a9`).
- DECISION B-5: `implementation_sha256` → hashed once per instance in `__init__`, no module-level `@cache`, so the T07 global-state allowlist is unchanged and the provider holds no process state. Alternative: `@cache` + allowlist entry (the `pr-c1-v1` pattern). Reversible by: moving the hash to a cached module function (`647ce9a9`).
- DECISION B-6: the S10 family's shape in `benchmarks/registry.yaml` → SYN-001-T06's keys plus `provider`, `status`, `records_sha256`, `cases_directory: null` with a reason, `budgets: null` with a reason; no cases (library-only). Alternative: no family until S10-C. Reversible by: deleting the family and its test (`77aaf55f`).
- DECISION B-7: θ₀ → the literal `0.29815` (spec §2), not `298.15 / 1000.0`. Alternative: the quotient. Reversible by: one constant (`647ce9a9`).

## WO-S10-2 (spec §4, §5.4-§5.5, §7.5 A12-A22, A23 flash half)

- DECISION B-1 superseded: `flash()` is the TP flash of spec §5.4; the refusal and its test are gone (`f23e1927`).
- DECISION B-8: how S10.A20 patches "the two-phase cap" alone → two module constants, `SS_MAX` (liquid trial) and `SS_MAX_TWO_PHASE`, both 1000, one registered value (§5.6 "per loop"), read at call time. Alternative: one `SS_MAX` for both loops (A20's F3 case could not reach step 4). Reversible by: merging the names and patching both in A20 (`f23e1927`).
- DECISION B-9: Rachford–Rice details §5.4 4a leaves open → start β = 0.5 (always inside the bracket, which spans (<0, >1)); a Newton step when it lands strictly inside the bracket and moves β, the midpoint otherwise and whenever two Newton steps have not halved the bracket (so the bracket halves at least every three iterations and the loop provably ends); the returned β is the last one evaluated when the bracket is ≤ 4 ulp(β) or f(β) = 0. Alternative: rtsafe's step-size stop (does not close the bracket from both sides as §5.4 requires). Reversible by: `_rachford_rice` (`f23e1927`).
- DECISION B-10: the liquid trial carries ln W = ln z_i − ln K_i(w), the logarithm of the spec's W'_i = z_i/K_i(w), and forms W = exp(ln W) for w; step s and tm_L use ln W directly. Alternative: divide, then take logs (an extra rounding in every step). Reversible by: `_Search.liquid_trial` (`f23e1927`).
- DECISION B-11: what a `not_converged` flash carries beyond §5.4 → no outlets, `vapor_fraction` None, `k_values` {} (spec), and `iterations` = the iterations actually taken (step 3's cap: SS_MAX; step 4: step-3 count + step-4 count), blueprint §6.4; the reason text follows the code (`… reached its cap of N iterations (last step R > 1e-13)`; `no Rachford-Rice bracket (K_max = R, K_min = R …)`; `vapour fraction R outside (0, 1)`). Note: `FlashResult`'s docstring says not_converged "carries what it reached"; the spec's "no outlets" is followed. Alternative: iterations 0. Reversible by: `_flash_not_converged` (`f23e1927`).
- DECISION B-12: `stability(…, "VAPOR")` at the liquid-trial cap → UNKNOWN, `tm` both None, `trial_composition` None, `iterations` SS_MAX, `residual` the last step (§5.5 names only the label and reason). Alternative: report the unconverged tm (not a minimum, so not a distance the label could rest on). Reversible by: `stability` (`f23e1927`).
- DECISION B-13: `stability()` with a phase other than LIQUID/VAPOR → UNKNOWN, reason `unsupported_phase: …`, checked before length, domain and dormancy (§5.5 "reports and never raises"). Alternative: raise, or fall through to a trial. Reversible by: `stability` (`f23e1927`).
- DECISION B-14: `FlashResult.achieved_accuracy` → the default `"exact-double"`, as every provider's flash (`pr-c1-v1`'s Newton flash included); spec §5.4 is silent. Alternative: a new accuracy string for an SS result converged to δ_K (would need a convention the cache understands). Reversible by: one field in `flash` (`f23e1927`). For the reviewer.
- DECISION B-15: ln γ (eq. 3.8) factored out of `_wilson` as `_ln_gamma`, so the flash's K-values skip the O(N³) G matrix. Inert: `evaluate_phase` bit-identical at E1-E6, both phases, every value and derivative (hex dump before and after). Alternative: a second transcription of eq. 3.8. Reversible by: reverting `c7a72e95`.

## WO-S10-2b (review findings 1-3; spec §14 Amendment 1 E-1, E-2; R-711)

- DECISION B-16: what the E-1 test asserts → with n_VA = 5e-324 (n_tot unchanged, so z bitwise equal), `flash` and both `stability()` reports equal the n_VA = 0.0 results bitwise (single phase: the outlet is the feed itself, subnormal included); cases: the review's two reproducers at F3 (both LIQUID) and F5 with the subnormal (a split, VA outlets 0.0). Alternative: assert only "no raise, typed result". Reversible by: `test_e1_*` (`7a3d26f4`).
- DECISION B-17: the E-2 sample → 12 literal states plus the review's reproducer: offsets +2e-5, −5e-5, +1e-4 in x_VB from F12, temperatures at 1/5…4/5 of the band where both trial distances are below −EPS_TPD (found offline by bisection on `stability()`); the test first asserts both labels UNSTABLE, so every state reaches step 4. "Fugacity equality ≤ 1e-10" is read as |ln x_i + ln φ_i^L(x) − ln y_i − ln φ_i^V(y)| ≤ 1e-10 at the outlets, through `evaluate_phase`. No count of ok vs not_converged is asserted (it depends on rounding). Alternative: compute the sample at test time. Reversible by: `NEAR_AZEOTROPE` (`23a2c289`).
- DECISION B-18: finding 3's check → both phases, all 10 queries: the spread of ln w_i + ln φ_i^trial(w) − ln z_i − ln φ_i^phase(z) ≤ 1e-12 and each term within 1e-12 of −ln(1 − tm) (the review's −ln ΣW). Alternative: the spread alone. Reversible by: the block in `test_a21_stability_queries` (`300eb941`).

## WO-S10-3 (spec §9.1-§9.5, §9.7; A30-A34)

- DECISION B-19: Q-N7, the `iapws95-v1` route to p_σ → `openflowsheet.thermo.iapws95._saturation(T).pressure`, the module's own Maxwell solve (private name), at T = 290, 320, 350, 380, 410 K. Alternative: the spec default, two TP evaluations bracketing p_σ (an interval, not a value). Reversible by: `XCHECK_T` and `compute()` in `s10_saturation_points.py` (`b3744f09`).
- DECISION B-20: how `--check` gets the NASA-7 data without Cantera → `benchmarks/s10/nasa7-low.json` holds the file's own decimal literals (a1..a7, low range), written by `s10_records.py --extract-nasa`, which checks nasa_gas.yaml's SHA-256 `4de6199d…` and the species' composition and ranges. Alternative: read nasa_gas.yaml at every `--check` (needs Cantera). Reversible by: `extract_nasa` (`a8411958`).
- DECISION B-21: where the fit claims and fit quality go → `benchmarks/s10/fit-report.json` beside `records.yaml`, both regenerated by `--check`. Alternative: YAML comments in the records. Reversible by: `build()` (`a8411958`).
- DECISION B-22: storage → b_k the binary64 nearest the exact decimal a_{k+1}·1000^k; Δ_fH the binary64 nearest the 50-digit value; molar mass the binary64 nearest the CIAAW 2021 conventional decimal sum (H 1.008, C 12.011, O 15.999; Q-N6 default, TM-4513 not read); `data_set: S10-wilson-ig-real-v1` (the spec names none); no `identifiers`. Alternative: Δ_fH rounded to 0.01 J/mol. Reversible by: `ideal_gas`, `records_text` (`a8411958`).
- DECISION B-23: the data's second component → x2 = 1 − x1 and y2 = 1 − y1, exact in decimal (the paper prints only x1, y1); every printed value enters as its decimal string. Alternative: none sensible. Reversible by: `binary_data` (`a8411958`).
- DECISION B-24 (**escalated**, ESC-2): the pressure of the fit data → 101.3 kPa, as Table II's caption prints it (the authors corrected their temperatures to 101.3 kPa); §9.4 recalled 101.325 kPa. Measured on transcription A: with 101 325 Pa, Λ moves by at most 2.8e-3 relative (methanol+ethanol) and 3.9e-4 (the water binaries); AAD(T) moves ≤ 0.001 K. Alternative: 101.325 kPa. Reversible by: `P_TABLE` (`a8411958`).
- DECISION B-25: the §9.4 grid scan → binary64 over the 181 × 181 grid, its best point re-evaluated at 50 digits for the claim Φ_grid ≥ Φ* − 1e-12. Alternative: the scan at 50 digits (~1000× slower, same answer at this margin). Reversible by: `grid_scan` (`a8411958`).
- DECISION B-26: the Gauss–Newton step → the minimum-norm least-squares solution of J Δ = −r (eigenvectors of JᵀJ above 1e-40 of the largest eigenvalue). At θ = 0, where §9.4 starts, the two columns of J are identical (∂ ln γ_i/∂θ_12 = ∂ ln γ_i/∂θ_21 = x_j²), so the normal equations are singular for every binary. A GN fixed point still has Jᵀr = 0. Alternative: Levenberg–Marquardt, or another start (both depart further from §9.4). Reversible by: `gn_step` (`a8411958`).
- DECISION B-27: "‖Δθ‖ < 1e-30" → the norm of the step taken (after halving). At 50 digits the full step floors near 1e-28 on the water binaries and the halving loop then shrinks it below 1e-30. Alternative: the full step's norm (unreachable at 50 digits on transcription A). Reversible by: `gauss_newton` (`a8411958`).
- DECISION B-28: transcription format (orchestrator's instruction) → `system,table,row,T_K,x1,y1`, γ columns left out, P not a column (B-24); `row` counts down Table II's left half, then its right half (the order of increasing x1 within each system). Reversible by: re-ordering the file; the fit does not depend on the order (`0d81a6a6`).
- DECISION B-29: the azeotrope comparison (§9.4, fit quality) → the model's x1 where y1 = x1 at the bubble point (bisection on x1 ∈ [0.5, 0.99]) against the linear interpolation of y1 − x1 across its sign change in Table II; Table IV (the paper's graphical azeotrope, x1 = 0.893, 351.33 K) is not transcribed. Reversible by: `azeotrope` (`a8411958`).

- DECISION B-30: I6 and I7's temperatures → the bubble (dew) temperature rounded to 0.01 K, then −5 K (+5 K), rounded again to 0.01 K. Alternative: unrounded T_bub − 5. Reversible by: `build_real` (`57b5255b`).
- DECISION B-31: "IDAES's approximate envelope, dew with γ(z)" → Σ_i z_i P / (γ_i(z) P_i^sat(T)) = 1; bubble with γ(z) is the true bubble. The smoothing claim uses d_b to the true bubble and d_d to this approximate dew, |∂q/∂T| = max over β, x_i, y_i by a 50-digit central difference (h = 1e-12 K). Alternative: d_d to the true dew (larger, less conservative). Reversible by: `idaes_dew_t`, `build_real` (`57b5255b`).

### WO-S10-3 remainder (spec §15 A2-5)

- DECISION B-32: where the I-states' §7.3 flash expectations live in `reference_values_real.yaml` → the synthetic layout, `closed_form.flash` (per I-state: `state`, `phase_signature`, `stability`, the outputs), `tolerances.tm`, `tolerances.flash.per_state`, `measured.{binary64_floor_flash, classification_margins, ss_iterations_max}`, written by `flash_record()`, now shared by the synthetic F-states and the I-states (factored out inertly: `--check` 113 claims, byte-identical, `cbf7bbbb`); `closed_form.i_states` keeps the IDAES-oriented entries unchanged. Alternative: fold the flash fields into `i_states`. Reversible by: `build_real` (`d48f45f0`).
- DECISION B-33: the I-states' classification margin → `MARGIN-<I>`: both trial distances more than 10 TOL_TM from 0 and from −EPS_TPD, §7.3's stated rule, for all 14 I-states (the synthetic `MARGIN-*` bound of 1e-4 was set for its chosen clear states); plus `DOM-<I>`. Measured: least margin 0.0209 (I13), so the 1e-4 bound would hold as well. Alternative: 1e-4. Reversible by: one bound in `build_real` (`d48f45f0`).
- DECISION B-34: the tests once the records exist → the committed records' and real section's absence fails A30, A31, A33, A34 instead of skipping; provider A01 asserts that the default records are the real ones with §9.5's uncertainty string; the `UNAVAILABLE` test runs on an absent `--vle` path with `--out-dir`. §9.5's string "not yet validated (S10 spec §9.6)" was already in `records_text` (`a8411958`), so no generator change. Alternative: keep the skips. Reversible by: the test helpers (`3e6986ee`, `d48f45f0`).

### Escalations (WO-S10-3), for the design-lane ruling round

**Ruled (2026-10-25):** spec §15 (Amendment 2), register R-712–R-715. ESC-1 → A2-1 (Gauss–Newton from the best point of
a step-0.005 grid, B-25/B-26/B-27 ratified); ESC-2 → A2-2 (101.3 kPa as printed, B-24 confirmed); ESC-3 → A2-3 (mid-band
rule on min(T_dew, IDAES dew); I10 is z_E = 0.4); RC-03 → A2-4. The remainder is listed in §15 A2-5.

- **ESC-1. The methanol+ethanol Λ fit fails its claim (§11: a fit that fails its claim).** On transcription A, §9.4's Gauss–Newton from θ = 0 does not converge in 200 iterations. The iterate is drawn to the line θ_12 = −θ_21 (Λ_12Λ_21 = 1), on which JᵀJ is singular, and crawls towards (−0.15638, 0.15638), Φ = 4.56431e-4, which is not a minimum. The minimum is θ* = (0.492781, −0.404717), Φ* = 4.353490e-4, Λ = (0.6109248362, 1.49887856): GN started at (0.485, −0.40) converges in 20 iterations, JᵀJ eigenvalues 1.1e-3 and 8.7. **The step-0.05 grid cannot certify this binary either:** the valley is narrower than the grid; the grid minimum is 4.60171e-4 at (−0.15, 0.15), above both stationary values, so the "no Φ below Φ* − 1e-12" claim would pass at the wrong point too. A step-0.005 grid finds 4.35878e-4 at (0.485, −0.40). The two water binaries are well posed: GN converges in 24 and 32 iterations and both grids' minima lie above Φ* (ethanol+water 0.0122811 vs 0.0122794; methanol+water 0.0097278 (0.05) and 0.0094327 (0.005) vs 0.0094319). The system is nearly ideal (γ 0.958-1.018 in the paper, whose own NRTL parameters for it are zero), so Wilson's two parameters are weakly determined. Options: (a) multi-start GN from the local minima of a step-0.005 grid, with the global claim on that grid (unchanged results for the water binaries); (b) Λ_ME = Λ_EM = 1, as the paper treats it; (c) the spec as written (no records). Build-lane default if asked: (a). Needs: a §9.4 amendment. No records are committed until the ruling and transcription B.
- **ESC-3. Three registered I-states fail §8.1's generator claim (§11: a registered state that seems wrong).** On the provisional records (transcription A, ESC-1's minimum for methanol+ethanol), mid-band at 101 325 Pa: I9 (ethanol+water, z_E = 0.6) band 1.87 K, 0.93 K inside the true envelope but 0.28 K from IDAES's approximate dew (which lies 0.66 K below the true dew); I10 (z_E = 0.85) sits 0.03 from the model azeotrope (x_az = 0.881), band 0.007 K, so the 0.01 K rounding lands outside (LIQUID); I13 (ternary (0.1, 0.6, 0.3)) band 1.26 K, 0.43 K from the approximate dew. The other eleven hold; the smoothing claim holds at every rung (worst 8.0e-9 at eps = 1e-4, I13; ≤ 8.0e-11 at 1e-5). These depend on Λ only weakly, so the final records will very likely fail the same way. Options: move I9/I13's T to the middle of [T_bub, approximate dew]; replace I10 by a z away from the azeotrope (e.g. z_E = 0.4); or drop the IDAES-envelope margin for those states. Needs: a §8.1 amendment.

- **ESC-2.** B-24 (101.3 vs 101.325 kPa); it changes Λ in the third or fourth digit.
- **Q-N1 settled for the 1993 paper:** Kurihara, Nakamichi, Kojima, J. Chem. Eng. Data 38 (1993) 446-449 exists as recalled, with Table II (three binaries, isobaric) and Table V (the ternary, VAL-1). Departures from §9.4's recollection: the pressure is printed as 101.3 kPa (ESC-2), and methanol+ethanol has 11 points (x1 = 0.074-0.935), fewer than the substitution rule's 15 (the rule does not apply: the paper is the recalled one). The 1995 paper (VAL-2) is not yet available (WO-S10-6).
- **Q-N6 not settled:** TM-4513 was not read; molar masses take the CIAAW 2021 default and S10-RC-08 stays unresolved.

## WO-S10-4 (spec §8.1, §15 A2-3; A40-A42)

- DECISION B-35: how the tool reads its inputs → `benchmarks/s10/idaes/inputs.json`, written by `scripts/s10_idaes_comparison.py --write-inputs`: the record values of `records.yaml` verbatim (with its SHA-256), the I-states' `n`, `T`, `P` only, the RB points and the ladder; the IDAES environment has no YAML reader. The tool computes §8.1's mapping itself; the comparison checks it against the generator's `idaes_mapping` (max |Δτ| 0, coefficients ≤ 2.2e-16 relative). §8.1 asks no blindness; the tool still reads no expected value and imports nothing of `openflowsheet` (S03's form). Alternative: install PyYAML into the reference environment. Reversible by: `inputs()` and `main()` of the tool (`6965df12`).
- DECISION B-36: the phase identity of IDAES at I6, I7 (§8.1 "exact") → LIQUID if |β| ≤ 1e-7, VAPOR if |β − 1| ≤ 1e-7, else TWO_PHASE (A41's β tolerance; the smooth flash has no phase label). Not yet applied: no rung is selected (ESC-5). Alternative: the sign of flow_mol_phase. Reversible by: `phase_identity()` in the comparison script (`6965df12`).
- DECISION B-37: what the comparison holds when no rung is selected → no difference to our values is computed; states optimal somewhere are `NO_SELECTED_RUNG`, states optimal nowhere `NOT_COMPARABLE` (§8.1). Computing deltas before the ruling on ESC-4/ESC-5 would make any amended ladder non-blind (the S03 lesson). Alternative: compare each state at its first optimal rung now. Reversible by: `a41()` (`6965df12`).
- DECISION B-38: replacing the three Wagner sites → subclass the package's parameter and state-block data; `_pressure_sat_comp` is rebuilt with spec (3.3) at T_eq, and the bubble and dew P^sat Expressions are `set_value` with (3.3) at T_bubble and T_dew after the package builds them. The package's Wagner parameters exist as mutable placeholders only so that its Expressions construct; the inspection finds no active constraint referencing them (0 references). Alternative: copy the package's 400-line bubble/dew methods. Reversible by: `define_package()` (`6965df12`).
- DECISION B-39: the readback method (A40) → `calculate_variable_from_constraint` on the package's own constraints (Gij, A, B, γ, P^sat, phase-component and phase enthalpies), both phase compositions = x and T = T_eq = T_bubble = T_dew fixed at the point; the bubble/dew P^sat and γ Expressions read at the same point. Residual of the solved constraints ≤ 2.5e-16. Alternative: a converged flash at the point (then the readback is no longer "before any flash"). Reversible by: `readback()` (`6965df12`).
- DECISION B-40: an initializer that raises → recorded, and the final solve still runs from where it stopped. Measured: no attempt whose initializer raised ended optimal, so stopping instead changes no outcome. Alternative: end the attempt at the initializer. Reversible by: `attempt()` (`6965df12`).
- DECISION B-41: the liquid c_p unit → declared in J/kmol/K^(k+1) as the package's BTX example, values 1000 × the J/mol values; the package's `pyunits.convert` gives J/mol. Fixed by readback: h^L agrees to 1e-15. The initializer's linear solver is the attempt's (`idaes.cfg.ipopt.options.linear_solver`, T06's form), its other options IDAES defaults. Alternative: declare J/mol. Reversible by: `define_package()`, `attempt()` (`6965df12`).

### Escalations (WO-S10-4), for the design-lane ruling round

**Ruled (2026-10-25):** spec §16 (Amendment 3), register R-716–R-719. ESC-4 → A3-1 (`constr_viol_tol` = 1e-9; the
floor is one binary64 step of T_bub, 2.1-2.3e-10 Pa); ESC-5 → A3-2 (each state at its first converged attempt in the
registered order; the ladder is closed), with the tool-only checks of A3-4 (S10.A43, A44); ESC-6 → A3-3 (IDAES's dew
takes γ at the flash liquid; the I-states do not move; the claims use IDAES's dew; generator 160 claims). B-36 is
ratified, B-37 superseded, B-40 and B-41's initializer solver endorsed (A3-5). DWSIM's ESC-50 to ESC-52 → A3-6
(R-719). Next: WO-S10-4b (§16 A3-8).

- **ESC-4. The registered constr_viol_tol = 1e-10 sits at the binary64 floor (§11: a registered constant that seems wrong).** constr_viol_tol is on the unscaled constraints; the binding row in every near-converged attempt is `eq_temperature_bubble` (Σ z_i γ_i P_i^sat − P, in Pa; ulp(101 325) = 1.5e-11). I4, I8, I9, I10 (every rung, both solvers) and I2 (1e-6, MA27) stall at an unscaled violation of 0.80–2.87e-10 with a scaled NLP error of 2.5–4.8e-12, ending "Solved To Acceptable Level" or "Search Direction is becoming Too Small". §8.1's floor argument ("10⁻¹⁰ on scaled residuals") does not hold for this option. T06's ruling M6 (a) set 1e-9 for the same reason. **The choice I would make:** constr_viol_tol = 1e-9 with tol = 1e-10 unchanged, all rungs rerun (1e-9 Pa is 1e-14 relative in the bubble equation). Not run: it is outside the registered ladder.
- **ESC-5. No rung has every I-state optimal, and §8.1 does not say which rung the others use (spec gap).** Under the registered ladder: I1, I5, I7, I12, I14 optimal at all three rungs; I13 at 1e-4 only; I6 at 1e-5 and 1e-6 only; I2, I3, I4, I8, I9, I10, I11 at none. The package's own initializer raises (local infeasibility or restoration failure in its step solves) at I2, I3, I11 at every rung, I6 at 1e-4, I13 at 1e-5 and 1e-6, and I4, I12 at 1e-6 with MA27; I3 and I11 fail far from feasibility at every attempt, so ESC-4 does not rescue them. Even with ESC-4, I6 and I13 share no rung. **The choice I would make:** each state at the first rung at which it ends optimal (A42 holds at every rung: worst predicted 8.47e-9 at 1e-4), states optimal nowhere `NOT_COMPARABLE`. Alternative: the rung with the most optimal states, the rest `NOT_COMPARABLE`.
- **ESC-6. §8's reading of the package's dew temperature is wrong for IDAES 2.13.0 (a contradicting measurement).** `eq_temperature_dew` divides by `activity_coeff_comp`, the γ of the flash's own liquid (x at T_eq); the γ(z) Expression `activity_coeff_comp_dew` is built and unused (the dew equation is in the inspection record). So B-31's T_dew^γ(z), used by §15 A2-3's mid-band rule, its 0.5 K margin and A42's prediction, is not IDAES's envelope. Measured at the seven optimal states: IDAES's T_dew − T_dew^γ(z) from −0.0046 K (I14) to +0.79 K (I12); with IDAES's own envelope the predicted smoothing is at most 7.74e-9 at 1e-4 (I13, generator 8.47e-9) and every measured |T_eq − T|·|∂q/∂T| ≤ 8.0e-10. No measured claim fails; for a vapour-only state IDAES's dew is exact. Needs: the §8 text and B-31 amended, and a ruling on whether A2-3's rule and A42's prediction should use IDAES's dew.

## WO-S10-4b (spec §16 A3-8; A41-A44)

Commits: `dcf6ea19` (qualification record: runs R and A3, reproduction, selection, A43; no A41 difference computed),
`d3b3ec85` (comparison record), `444beea3` (tests). Each choice below is isolated and revertible.

- DECISION B-42: the "text" A44's four patterns are matched in (A3-4 says "the bubble text contains
  `activity_coeff_comp_bubble[`", exactly) → Pyomo's verbose rendering, `expression_to_string(expr, verbose=True)`, of
  both envelope equations (`inspection.envelope_equations`); the plain `str()` renderings are recorded beside it
  (`plain_str`). Reason: `str()` inlines a named Expression's body, so the bubble equation shows γ(z) as the Wilson
  formula in `mole_frac_comp` and never names `activity_coeff_comp_bubble`; pattern 1 fails on it although the equation
  is the one A3-3 reads. The verbose rendering names every named Expression with its body in braces; the four patterns
  hold on it, and the plain dew text equals the one WO-S10-4 recorded. Escalated as ESC-7. Alternative: the plain
  rendering (A44 then fails on pattern 1), or the rule functions' source text. Reversible by: `inspect()` in the tool
  script, a tool run (19 s) and `--write`.
- DECISION B-43: which A41 quantities A43 compares at a component absent from the feed → x_i and y_i, but no K_i, as
  A41 itself compares no K_i where ours is null; absence read from the attempt's own `z` (z_i = 0). The tool's K of an
  absent component is y/x of two ~1e-21 numbers (its relative change across rungs reaches 2.5e-4 at I6). Alternative:
  include it (then A43 would measure noise). Reversible by: `dependence()` in the tool script.
- DECISION B-44: A43 at I6 and I7 → the phase identity alone (A41's quantity there), ratio recorded as null; the
  states compared by identity are passed in `inputs.json` `a43.compared_by_phase_identity` (from the YAML's phase, as a
  list of ids, not the phases). Alternative: also β, x, y, K, h of the smooth flash's absent phase. Reversible by: the
  same function.
- DECISION B-45: A42 (a) for K and h at the finer rungs → the YAML's 1e-4 value times (ε/1e-4)², the scaling of the
  prediction formula and of `measured.smoothing_predicted`; the generator carries K and h at 1e-4 only. Alternative:
  1e-4's value at every rung (an upper bound). Reversible by: `a42()` in the comparison script.
- DECISION B-46: where selection, reproduction and A43 are computed → in the tool script, on its in-memory records
  (stdlib only), written to `qualification.json` and committed before `comparison.json` exists; the comparison script
  copies them and the tests recompute them. The WO-S10-4 record is read from a file extracted with
  `git show e63f98c2:benchmarks/s10/idaes/qualification.json` (`--reproduce-against`). Alternative: a post-processing
  mode of the comparison script. Reversible by: moving the functions.

### Escalations (WO-S10-4b), for the design-lane ruling round

- **ESC-7. A44's patterns presume a rendering in which named Expressions appear by name (spec gap).** See B-42. The
  equations themselves match A3-3's reading in both renderings: the plain bubble text shows γ as the Wilson formula in
  `mole_frac_comp` (z), and the dew text names `activity_coeff_comp` (a variable). Needed: confirm the verbose rendering
  as A44's text, or name another.
- **ESC-8. I11 is not a state whose initializer fails in every attempt (a contradicting fact; the rule is unaffected).**
  A3-2 ("Rejected") and A3-10 Q-F5 say IDAES's initializer fails at every I11 attempt, and §16 expects I11
  `NOT_COMPARABLE`. The WO-S10-4 record, reproduced exactly, has I11 at 1e-4 with MA27: initializer `completed`, final
  solve "Search Direction is becoming Too Small" after 9 iterations at 1.89e-10 (`eq_temperature_bubble`), a floor
  stall A3-1's list omits. Under 1e-9 it ends optimal at iteration 0. A3-2's rule selects it; nothing was chosen. Q-F5's
  premise changes: only I3 has no optimal attempt. Needed: note it in the verdict.

## Run log

- 2026-10-25, WO-S10-1. `tests/test_s10_provider.py`: 88 passed. Per group: A01 2, A02 21 (19 malformed copies covering
  all five codes, bitwise handover, code coverage), A03 1, A04 12, A05 12, A04/A05 worst 1, A06 1 (102 zeros), A07 1,
  A08 12, A10 12, A11 2, A23 2, A24 1, A25 1 (113 claims, 11.6 s), A26 1, A27 3, A28 1, type and flash refusal 2.
- Worst agreement over A04/A05 (every non-identity entry, E1-E6, both phases): 0.069 of the tolerance, at
  E4.LIQUID ∂h/∂n_VB: 6.9 × 10⁻¹⁴ relative, the spec's measured floor (FLOOR-E 6.93 × 10⁻¹⁴). E3's structural zeros
  come out exactly 0.0.
- Mutations re-run on the implementation (ratio of the worst entry to its tolerance): M09 unprojected 2.8 × 10¹⁴,
  M01 Λ transposed 1.9 × 10¹², M14 R = 8.314 1.9 × 10⁸ (the spec's 1.9 × 10⁸), θ₀ = 0 2.0 × 10¹².
- Registry and provider-registry tests (T08 envelope, unsupported, inventory; T07 global state; requirements ledger;
  S05/S07 registration; registry readers; document hashes): 590 passed, 11 skipped, 6 failed = T08's C3 harvest
  check only (`wilson-ig-v1: S10 has no U02 item in the harvest`), expected until S10's manifest is harvested, as for
  S05 and S07. ruff, ruff format and mypy clean on the touched files.

- 2026-10-25, WO-S10-2. `tests/test_s10_flash.py`: 86 passed. Per group: A12 13, A13 7, A14/A15 6 (5 states + worst),
  A15 absent components 5, A16 5, A17 14, A18 1, A19 7, message rule 1, A20 3, Rachford–Rice vs the analytic binary
  root 4, A21 12 (10 queries, both labels, flash = stability distances bitwise), A22 7 (6 + unknown phase), A23 1.
  `tests/test_s10_provider.py`: 87 passed (B-1's test removed).
- Agreement: worst two-phase output 0.034 of its §7.3 tolerance (F10 K_VA; F3 0.032, F4 0.026, F8 0.027, F5 0.004);
  worst trial distance 1.78 × 10⁻¹⁴ (F2 tm_V, = FLOOR-TM), every other ≤ 2.4 × 10⁻¹⁵; worst component balance
  5.6 × 10⁻¹⁷ n_tot; fugacity residuals 3.9-9.4 × 10⁻¹⁴.
- Iterations: liquid trial F2 40, F3/F8/F10/F11 39, F5 28, F4 21, F6b 1; two-phase F3 39, F4 28, F5 28, F8 23, F10 17
  (spec SS-CAP: at most 40 and 39). Labels: F1, F6a, F7, F12 LIQUID; F2, F6b, F11 VAPOR; F3, F4, F5, F8, F10 TWO_PHASE;
  F9 ZERO_FLOW. stability(): F1 L stable / V unstable, F2 L unstable / V stable, F3 both unstable, F7 L stable / V
  unstable, F11 L unstable / V stable, as the YAML.
- Mutation MF01 (K at y) re-run on the implementation: F3's β moves 1.27 × 10⁹× its tolerance (spec 1.3 × 10⁹×).
- Registry tests (T08 envelope, unsupported, inventory; T07 global state; requirements ledger; S05 envelope; S07
  registration; T04/T06 registries; document hashes) with both S10 files: 539 passed, 11 skipped, 6 failed = T08 C3's
  harvest check only, as in WO-S10-1. ruff, ruff format and mypy clean on the touched files.

- 2026-10-25, WO-S10-2b. E-1 (`_Search.flowing` on z) inert: `flash` and `stability()` (both phases) hex-identical
  before and after on F1-F12 and 70 near-azeotrope states (5 offsets × 14 temperatures), 252 results. The E-1 test
  fails 3 of 3 on the old code. Finding 3 margins: spread 7.8 × 10⁻¹⁴, constant 4.0 × 10⁻¹⁴ (bound 1e-12); mutation
  trial_composition = z fails 10 of 10, unnormalised vapour-trial W fails 5 of 5. E-2: 9 ok (worst ln-fugacity
  residual 1.0 × 10⁻¹³, balance 1.1 × 10⁻¹⁶ n_tot), 4 not_converged (the reproducer, 1027 iterations, among them);
  mutation DELTA_K = 1e-9 fails 13 of 13. `tests/test_s10_flash.py` 102 passed (86 + 3 E-1 + 13 E-2),
  `tests/test_s10_provider.py` 87 passed. ruff, ruff format, mypy clean on the touched files.

- 2026-10-25, WO-S10-3. Saturation points: 61 × 3, CoolProp 8.0.0 (`ae81610e`), EOS keys deReuck-BOOK-1993, Schroeder-JPCRD-2014, Wagner-JPCRD-2002; water vs `iapws95-v1` worst 3.5e-11 relative (290-410 K). Vapour-pressure fit (290-410 K, no narrowing): worst |Δ ln P| CH3OH 1.60e-4, C2H5OH 5.63e-5, H2O 9.25e-5. Δ_fH from the polynomials: −200938.85, −234948.66, −241824.62 J/mol. Transcription A: 11 / 20 / 18 rows, (T, x1, y1) multiset equal to the PDF text layer. **Provisional, transcription A, not committed:** methanol+ethanol fails §9.4 (ESC-1); with GN from (0.485, −0.40): Φ* 4.35349e-4, Λ (0.6109248362, 1.49887856), AAD T 0.025 K, y 0.0013. ethanol+water: 24 iterations, Φ* 0.0122794, grid min 0.0122811, Λ (0.1649874985, 0.8615311153), AAD T 0.049 K (max 0.35), y 0.0054 (max 0.016). methanol+water: 32 iterations, Φ* 0.0094319, grid min 0.0097278, Λ (0.3674022637, 1.134238098), AAD T 0.141 K, y 0.0041. Model azeotrope x_E 0.8814 at 351.320 K; the data's sign change interpolates to 0.900 (rows 16-17). Real section on those records: RE floors ≤ 5.7e-15; ESC-3. Tests: `tests/test_s10_records.py` 14 passed, 4 skipped (A30, A33, A34 pass on the provisional files); `test_s10_provider.py` unchanged; `s10_reference.py --check` 113 claims, matches.

- 2026-10-25, WO-S10-3 remainder. `s10_records.py --emit` (18 s): 25 claims hold, `--check` matches. Stored Λ, iterations
  and AAD equal §15 A2-1's table: ME 0.6109248362 / 1.49887856 (19 it., Φ* 4.35348996646e-4, grid margin 5.29e-7), EW
  0.1649874985 / 0.8615311153 (21, margin 1.76e-6), MW 0.3674022637 / 1.134238098 (28, margin 8.34e-7); ME's θ = 0 run
  stops at the cap (Φ 4.6126e-4), its second minimum Φ 4.564308503e-4. `s10_reference.py --real` (27 s): I-state T,
  bubble, dew and IDAES dew equal A2-3's table; 155 claims (88 + DOM 14, SS 12, BETA 12, BAL 12, MARGIN 14, FLOOR-TM,
  FLOOR-LNK, SS-CAP). Floors: tm 2.78e-15 (TOL_TM/10 = 1e-13), ln K 3.22e-15; SS 60 (liquid trial) and 67 (two-phase)
  iterations; A 1.02-5.52 (I14-I10), ρ ≤ 0.65; β tolerances 2.7e-12 (I1) to 5.5e-11 (I13); least classification margin
  0.0209 (I13). A34 flash half: worst 0.059 of tolerance (I2 K_CH3OH). Mutations against A34's two-phase checks:
  Λ_MW changed in its 10th digit 138× (I9 K_CH3OH), Λ_EW transposed 4.8e11×. Tests: `test_s10_records.py` 21,
  `test_s10_provider.py` 87, `test_s10_flash.py` 102, `test_requirements_ledger.py` 15, all passed, none skipped;
  `s10_reference.py --check` 113 claims, matches. ruff, ruff format, mypy clean on the touched tests.
- 2026-10-25, WO-S10-4. IDAES 2.13.0, extensions 3.4.2, fingerprint matches `docs/reference-environments.md` §3; Ipopt 3.13.2. Build: DOF 0, 38 active constraints, 0 Wagner references. A40: 68 readback rows (P^sat at three sites, γ and γ_bubble, h^L, h^V at four RB points), worst 2.86e-15 relative (RB-T360-x1 P^sat H2O); τ as the generator's `idaes_mapping` exactly; untransposed τ moves ln γ by 0.150 at the RB points. Ladder (67 attempts, 9 s): optimal per state {I1, I5, I7, I12, I14: all rungs; I13: 1e-4; I6: 1e-5, 1e-6; I2, I3, I4, I8, I9, I10, I11: none}; selected rung none (ESC-4, ESC-5). A42: predicted ≤ 8.47e-9 / 8.47e-11 / 8.47e-13 at the three rungs; measured |T_eq − T|·|∂q/∂T| ≤ 8.0e-10. Reproduction: a second full run is bit-identical apart from wall times and Ipopt log hashes. Tests: `tests/test_s10_idaes.py` 8 passed; `s10_idaes_comparison.py --check` both documents identical; ruff, ruff format clean.
- 2026-10-25, WO-S10-4b. Harness defects fixed (raw variables from `m.fs.state[0]`; null for an unvalued variable): no
  attempt records an error in either run. Run R (constr_viol_tol 1e-10) reproduces the WO-S10-4 record (sha256
  a77c10fe…) exactly: 67 attempts' solve fields, and quantities and constraint residuals at the 53 that recorded them.
  Three tool runs (19 s each) agree apart from timings. Run A3 (1e-9): 54 attempts; the 14 floor stalls of run R all end
  optimal (I4, I8, I9, I10 at every rung, I2 at 1e-6 MA27, I11 at 1e-4 MA27), final unscaled violation 4.37e-11 to
  2.33e-10. Selection: I3 `NOT_COMPARABLE(no_optimal_attempt)`; I2 1e-6/ma27, I6 1e-5/ma27, the rest 1e-4/ma27.
  A43: rung dependence ≤ 0.00985 (I9, β), setting dependence 0 exactly at all 18 attempts optimal in both runs (same
  iterate), I6/I7 identities equal; no state fails. A44: the four patterns hold (B-42). A41 (13 states): largest
  |Δ|/tol 0.00985 (I9 β); then I13 0.0080 (β), I10 0.0011 (K_C2H5OH); I2 3.1e-8; I6 LIQUID, I7 VAPOR as ours. A42 (a)
  at 1e-4: 7.75e-9 (I13), 0.012 τ_K, 3.8e-4 τ_h; (b) ≤ 0.00986 of the tolerance. A40: 2.86e-15. Generators: 113 and
  160 claims hold; `s10_idaes_comparison.py --check` identical. `tests/test_s10_idaes.py` 11 passed; S10 tests 229
  passed, 1 failed: `test_s10_dwsim.py::test_a45_comparison_recomputes` (DWSIM `inputs.json` records the real YAML's
  pre-Amendment-3 hash; WO-S10-5b's, not touched here).

## Where WO-S10-2b stopped

Complete: review findings 2 and 3 fixed, finding 1 recorded by E-2 with its outcome test; the stop rule is S10-C's.
B-16…B-18 are test-design choices for the next ruling round.

## Where WO-S10-3 stopped

Complete (2026-10-25): every item of §9.1-§9.5, §9.7 and §15 A2-5. `records.yaml` and `fit-report.json` emitted
(25 claims, `--check` matches; Λ as §15 A2-1), `reference_values_real.yaml` emitted (155 claims, `--real --check`
matches; I-states as §15 A2-3, with §7.3's flash tolerances), RC-03 per A2-4, tests for A30-A34 all running. Open:
the S10 `reviewer` pass over the fit and the generator extension (§11), WO-S10-4 (IDAES) and WO-S10-6 (validation);
RC-05 and RC-08 stay unresolved (Q-F3, Q-N6).

## Where WO-S10-4 stopped

Done (2026-10-25): the harness (`6965df12`) and the records with tests for A40-A42 (`bedd6c86`). A40 holds (2.9e-15
against 1e-10). A41 is blocked by ESC-4 and ESC-5: no rung is selected, so `comparison.json` holds no difference to our
values (B-37). Once the design lane rules: change the registered ladder in `LADDER` (comparison script) and the tool's
selection if needed, run `.venv-idaes/bin/python spikes/references/s10_qualify_idaes.py` (9 s), then
`python scripts/s10_idaes_comparison.py --write-inputs && --write`, rerun `tests/test_s10_idaes.py`, and hand the records
to `verdict`. ESC-6 needs a ruling but blocks nothing.

## Where WO-S10-4b stopped

Done (2026-10-25): A3-8 items 1-6 (`dcf6ea19`, `d3b3ec85`, `444beea3`). Next: hand `qualification.json` and
`comparison.json` to `verdict` for A41, with ESC-7 and ESC-8 for the design lane. Not pushed, not merged.

## Double-entry check of the 1993 fit data (orchestrator, 2026-10-25)

- Transcription A (WO-S10-3, worktree s10) and transcription B (independent `sonnet-implementer`, worktree s10-txb,
  commit 6abc6af7 on wp/S10-txb, never saw A): `diff` empty, 49 rows (methanol+ethanol 11, methanol+water 20,
  ethanol+water 18), Table II, T in K, as printed.
- Both agents leaned on the PDF's OCR text layer, so an OCR misread could be common to both. Independent check: page 1
  rendered at 300 dpi (`pdftoppm -r 300`, the scan's native resolution) and all 49 (x1, y1, T) rows read off the image
  by the orchestrator: every value matches. The final `benchmarks/s10/vle/kurihara1993_binaries.csv` is A, byte for
  byte; A and B are kept for the audit trail. The paper itself is not in the repository.

## WO-S10-5 (spec §8.2, §15 A2-3; A45)

DWSIM 9.0.5 can express the model: its `WilsonModel.vb` (tag v9.0.5) has Λ_ij = (V_j/V_i)·exp(−A_ij/(1.9872 T)), A in
cal/mol, V = MW/ρ_L(298.15 K) from `GetArguments`, and ln γ_i = 1 − ln S_i − Σ_k x_k Λ_ki/S_k, our (3.8) with the same
indexing. The harness (`ae9aab8c`) fixed every mapping and setting before the tool ran on a registered state.

- DECISION B-50: settings §8.2 does not name, which the model needs (`SETTINGS` in `scripts/s10_dwsim_comparison.py`) →
  liquid density eq. 1 at 1e12 kg/m3 (v = 0 of §3.3: kills DWSIM's P/ρ_L in the Ideal-mode liquid enthalpy, ≤ 1e-8
  J/mol, and the Poynting factor); `LiquidFugacity_UsePoyntingCorrectionFactor` off (DWSIM default on); enthalpy mode
  `Ideal` (default `LeeKesler`; `Excess` would add DWSIM's h^E from its T-dependent Λ, which the model does not have);
  vapour fugacity `Ideal` (the default, set explicitly); `AutoEstimateMissingNRTLUNIQUACParameters` off before any
  stream exists (default on: setting a stream runs a UNIFAC estimation through Ipopt, whose `libIpopt39.so` does not
  load in this environment, and the .NET finalizer then aborts the process); flash `ForceEquilibriumCalculationType`
  `VLE` (the Wilson liquid cannot split, §4.1) and `FailSafeCalculationMode` 3 (the default 1 silently replaces a failed
  flash by a Raoult's-law flash). Placeholders T_c 1000 K, P_c 1e7 Pa, ω 0, NBP 350 K (unused on the equation paths).
  Escalated as ESC-50. Alternative: DWSIM defaults (then h^L carries P v ≈ 3-4 J/mol and K a Poynting factor ≈ 7e-4).
  Reversible by: `SETTINGS` and a rerun (4 s).
- DECISION B-51: the compositions of §8.2's γ readback "at the state's (T, x)" → the feed z and §8.1's two RB
  compositions, at each state's T (A_ij is per state). 126 rows. Alternative: z only. Reversible by: `READBACK_X`.
- DECISION B-52: PT-flash iteration limits (§8.2 registers tolerances only) → 1000 external and internal, T06's values.
  Alternative: DWSIM's 100. No attempt reached either (most iterations 34). Reversible by: `SETTINGS`.
- DECISION B-53: the ladder's selection rule (§8.2 gives the rungs only) → §8.1's: the first rung at which every
  I-state converges, for all; converged = no exception from the direct flash, no solver error, stream calculated.
  Alternative: per-state first rung (same result here: all converge at both). Reversible by: `LADDER`, `ladder()`.
- DECISION B-54: a diagnostic in `comparison.json`, `dwsim_self_consistency` per two-phase state: DWSIM's own
  equilibrium residual |ln K_i − ln(γ_i(x) P_i^sat/P)| at its own (x, y), with the generator's closed forms (which the
  readbacks show DWSIM evaluates identically), and its balance and Rachford–Rice residuals. Not a difference to our
  values; it separates a model difference from a convergence floor. Alternative: leave it out. Reversible by:
  `self_consistency()` (`f3388de2`).

### Escalations (WO-S10-5), for the design-lane ruling round

- **ESC-50. B-50's settings are outside §8.2's text (spec gap).** Each one expresses a property of `wilson-ig-v1`
  (v = 0, no Poynting, h^E = 0, one liquid) or stops DWSIM substituting another model; none is a convergence knob.
  **The choice made:** B-50, committed before the run. Needs: ratification, or the setting to use instead.
- **ESC-51. The registered flash ladder does not control DWSIM's convergence; DWSIM's PT flash stops at a hard-coded
  |ΔV| < 1e-6 (a registered setting that seems ineffective; a contradicting measurement).** `NestedLoops.vb`
  (`ConvergeVF`, v9.0.5) exits on `Math.Abs(e3) < 0.000001` before testing `Abs(F) < etol`; the tolerance setting
  reaches only the second test. Measured: both rungs give bit-identical outputs and iteration counts at all 14 states.
  At the 12 two-phase states |Δβ| 1.5e-7 (I5) to 2.4e-6 (I10), |Δx|, |Δy| up to 1.5e-6, K up to 6.7e-6 relative (I10
  K_C2H5OH, 67× the tolerance); 0 of 12 within §8.1's 1e-7. DWSIM's own equilibrium residual (B-54) is 3.3e-8 (I14) to
  2.1e-6 (I10), the same size and ordering as the differences, and its balance residual 2.4e-10 to 2.3e-8: the
  differences are DWSIM's convergence floor, not a model difference (γ, Λ, P^sat agree to ≤ 1.1e-14). h^L and h^V are
  within 0.05 J/mol at every state (worst 0.012), I6 LIQUID and I7 VAPOR as ours. Not tried: the Inside-Out flash
  (`UseIOFlash`) or any other setting outside the ladder. **The choice I would make:** record β, x, y, K at the
  two-phase states as `NOT_COMPARABLE` (tool floor ≈ 1e-6 above the 1e-7 tolerance, shown by B-54), h and the phase
  identities as compared. Needs: the `verdict`'s reading of A45, or a ruling to rerun with a pre-registered
  Inside-Out flash.
- **ESC-52 (for the record). DWSIM's ideal-gas enthalpy is a 10-step midpoint integral of c_p** (`AUX_INT_CPDTi`),
  so its h^ig differs from (3.2) by up to 0.026 J/mol (I7 CH3OH, ΔT = 68 K), 52 % of §8.1's 0.05 J/mol tolerance.
  `tests/test_s10_dwsim.py` reproduces DWSIM's sum to ≤ 1e-9 J/mol. No compared h exceeds the tolerance.

### Run log (WO-S10-5)

- 2026-10-25. DWSIM 9.0.5.0, .NET 8.0.31, pythonnet 3.1.0, fingerprint matches `docs/reference-environments.md` §3.
  Harness smoke tests on dummy Λ and dummy states only (scratchpad, not recorded). Registered run (4 s): mapping —
  applied A equals the rule exactly, effective Λ vs records 3.4e-16; γ gate 126 rows, worst 4.93e-16 (I8 CH3OH at
  z); informative P^sat 1.1e-14, Δh_vap 4.8e-16 (J/kmol fixed), c_p^ig 5.9e-16, h^ig 0.026 J/mol (ESC-52), φ^L 1.1e-14.
  Ladder: 28 attempts, all converged, rung 1e-10 selected, iterations 0-34. A45 table: see ESC-51. Reproduction: a
  second run is identical apart from wall times. `tests/test_s10_dwsim.py` 9 passed; a mutation (one γ by 1e-8, one A by
  1e-9) fails 3 of 9. `s10_dwsim_comparison.py --check` both documents identical. ruff, ruff format clean.

## Where WO-S10-5 stopped

Done (2026-10-25): harness (`ae9aab8c`), records and tests (`f3388de2`). Next: the `verdict` on A45 from
`benchmarks/s10/dwsim/{qualification,comparison}.json`, with ESC-50 and ESC-51 in the ruling round. A rerun after a
ruling: edit `SETTINGS`/`LADDER`, `python scripts/s10_dwsim_comparison.py --write-inputs`, `.venv-dwsim/bin/python
spikes/references/s10_qualify_dwsim.py` (4 s), `--write`, `tests/test_s10_dwsim.py`. .NET 8 support ends 2026-11-10.

## WO-S10-5b (spec §16 A3-6, A3-8; A45)

- DECISION B-60: A45's classification by A3-6 in `s10_dwsim_comparison.py` → at each two-phase state g = max(DWSIM's
  equilibrium residual, balance residual) from B-54; g > `DWSIM_FLOOR_GATE` = 0.1 × 1e-7 = 1e-8 makes the state
  `NOT_COMPARABLE`, reason `reference_accuracy: dwsim_flash_floor(<g>)`, h^L and h^V included. The differences stay in
  `comparison.json` as `diagnostic_rows` (no `within`). I6 and I7 stay on the phase identity (B-36's rule). Alternative:
  none (A3-6 states it). Reversible by: the `g > DWSIM_FLOOR_GATE` branch in `a45()`.
- DECISION B-61: B-50 (with B-51 to B-53) is recorded as ratified, as A3-6 rules; no setting changed, no tool rerun, no
  tool record edited. `comparison.json` is regenerated from the committed records.
- Test: `test_a45_comparison_recomputes` asserts all 14 states (12 NOT_COMPARABLE with g recomputed from the record and
  > 1e-8; I6, I7 compared on phase identity).
- DECISION B-62: `inputs.json` regenerated by `--write-inputs`. Amendment 3 (`42c04c66`) edited
  `reference_values_real.yaml`, so the SHA-256 that `inputs.json` records for it was stale and `--check` failed before
  this work order. Only that one hash changes (the states are identical). The tool's own record is untouched, so
  `qualification.json`'s `inputs_sha256` is the hash of the earlier `inputs.json`; the run's states are the same.
  Alternative: leave `inputs.json` stale (`--check` fails). Reversible by: `git checkout` of `inputs.json`.

## Double-entry check of the VAL-1 ternary data (orchestrator, 2026-10-25)

- Table V of Kurihara, Nakamichi and Kojima (1993), methanol + ethanol + water at 101.3 kPa, 38 rows, T in K.
  Transcription A (wp/s10-ta 21bb2e73): OCR text layer checked row by row against the 300 dpi image; one OCR error
  corrected (row 8 T 351.78, OCR 361.78). Transcription B (wp/s10-tb 3ea5675b): read from 300 dpi image crops only, no
  OCR, never saw A. `diff` empty. Final `benchmarks/s10/vle/kurihara1993_ternary.csv` = A byte for byte; A and B kept.
  Held out from every fit (VAL-1, §9.6); its bands were fixed before transcription.

## WO-S10-6 (spec §9.6; A50–A53: VAL-1 and VAL-3; VAL-2 pending)

The spec §11 names neither the script nor the report path; B-70 fixes them. Result (the bands are untouched, R-708):
VAL-1 within band (AAD(T) 0.2097 K, AAD(y) 0.00565 / 0.00544, max |Δy| 0.0210 / 0.0210 for CH3OH / C2H5OH);
VAL-3 **not validated within band**: CH3OH Δh max 5.72 % (band 5 %); every other VAL-3 cell is inside its band.
`docs/s10-validation-report.md` and `benchmarks/s10/validation/report.json` hold the numbers. The records' `uncertainty`
string is not changed (it waits for the verdict on the bands and VAL-2).

- B-70. DECISION: where do the script and the report live? → `scripts/s10_validation.py` (`--emit-eos`, `--write`,
  `--check`); `benchmarks/s10/validation/{val3-eos.json,report.json}` and the generated `docs/s10-validation-report.md`.
  The CoolProp output is committed (`val3-eos.json`, written by `--emit-eos` in `~/.cache/of-rca-6fec822/venv-xcheck`,
  CoolProp 8.0.0), so `--check` and the tests never need CoolProp. Alternative: one script that needs CoolProp.
  Reversible by: moving the files.
- B-71. DECISION: VAL-3's temperature grid and the statistic the band applies to → 11 points, equally spaced from 300 K
  to T_b(101 325 Pa) of CoolProp (the ends included); the band is applied to the **maximum** absolute relative
  deviation over the grid (the stricter reading of "within"). The mean (signed) is reported beside it. Under the mean
  reading CH3OH Δh (mean +4.0 %) would be inside 5 %. Alternative: the mean, or a different grid. Reversible by:
  `VAL3_POINTS` and the `max(...)` in `val3()`, then `--emit-eos` and `--write`. **Open for the `verdict` agent:** the
  reading of "within 5 %".
- B-72. DECISION: Δh and c_p^0L as the provider reports them → Δh_i = h^ig − h^L of the pure component through
  `evaluate_phase` at 101 325 Pa (§9.6 states the registered states stay there); c_p^0L = the T-derivative of the pure
  liquid `h`. EOS side: ΔH_vap = HMOLAR(Q=1) − HMOLAR(Q=0), c_p = CPMOLAR(Q=0), both at the saturation T. Alternative:
  the provider's internal `_pure` quantities. Reversible by: `val3()`.
- B-73. DECISION: VAL-1's `y_i` and the bubble solve → the bubble T by bisection on Σ x_i K_i = 1 over [300, 400] K
  with K_i = exp(lnphi_i) from `evaluate_phase` (no new model code); y_i = x_i K_i/Σ. The table has y1, y2 only, so
  y_H2O is 1 − y1 − y2. The band is **judged on the two measured fractions**; water's closure AAD (0.00599) and max
  (0.0308) are reported and would also be inside the bands. Alternative: judging all three. Reversible by: the
  `checks` dict in `val1()`.
- B-74. DECISION: tests → `tests/test_s10_validation.py` requires the report to be the script's output, the bands to
  equal §9.6's, and each verdict to follow from the raw points; it does not require a band to be met. The VAL-2
  assertions (A51 and the VAL-2 part of A53) are skipped with "VAL-2 data not yet supplied". Reversible by: editing.

## WO-S10-7 (close-out: review-final S-1 to S-3, the manifest, the ledger, the harvest)

S-1 (spec §17 A4-3, R-721): the records' `uncertainty` is A4-3's string, held as `UNCERTAINTY` in
`s10_records.py`. Cascade: `records.yaml` `74dc4e54…` → `d4a39730…` (the `uncertainty` line only), `fit-report.json`
the `records_sha256` line only; `reference_values_real.yaml` `52e46110…` → `2e9d5130…` (its `records_sha256` only);
IDAES `inputs.json` `92aa171f…` → `8d6c881d…`, DWSIM `0dc64095…` → `e9428f4b…` (the two hash lines each); both
`comparison.json` change only in `provenance`. Neither `qualification.json` touched. Every `--check` reproduces (25,
113, 160 claims; both comparisons; the validation report). The lineage test rebuilds IDAES's `92aa171f…` and, with
B-62's real-section hash `fa7c43f7…` (`ae9aab8c`), DWSIM's `28676a25…`, so the manifest cites one hash per tool.

- B-80. DECISION: A4-3 step 5's `commit` field cannot name the commit that carries it → the A4-3 commit writes
  "recorded by the next commit (S10_DECISIONS B-80)", and the next commit replaces it with the A4-3 commit's hash,
  changing nothing else. The lineage file is a JSON object: `steps` (the list A4-3 names, exactly its seven keys) and
  `dwsim_inputs_b62` (B-62's real-section hash, which A4-3 step 6 says the file records). Alternative: name the parent
  commit, or leave the field out. Reversible by: editing `records-lineage.json`.
- B-81. DECISION: where the manifest carries A4-4's validation block → the frozen manifest schema
  (`schemas/evidence-manifest.schema.json`, top level `additionalProperties: false`) has no field for it, so the block
  is the value of a check `S10.validation` (`{"validation": <A4-4's block verbatim>, ...}`) with result
  `not_applicable` and kept out of `status`; a limitation repeats it in one line. The generator refuses the block
  unless `validation/report.json` carries the verdicts it states. Alternative: a schema change (an ADR), or one check
  per VAL id with `pass`/`fail` (would read as verification). Reversible by: `validation_check()` in
  `scripts/s10_evidence_manifest.py` and a regeneration. **For the design lane** at the next ruling round.
- B-82. DECISION: the test count → the manifest reports the count measured at C_m in A4-4's form ("N passed, 2
  skipped (VAL-2)"); N is 240, not A4-4's 237, because WO-S10-7 adds the lineage test (A4-3 step 6) and the two
  blindness tests (S-3). The generator requires every skip to be VAL-2's. Alternative: none. Reversible by: no action.
- B-83. DECISION: the manifest lists `requirements: ["D08"]` only (the brief's ledger entry). §8's comparisons are
  D19-shaped, but D19's row is not edited here; a limitation says so. Alternative: list D19 and add S10 to D19's row.
  Reversible by: `requirements` in the generator, and the ledger.
- **MEASURED (manifest):** `evidence/S10/c4f3751e208c540076d2dd8109d673769745a0dc/manifest.json`, generated from a clean
  tree at `c4f3751e`: `status: tested`, 48 of 51 checks pass (A01-A08, A10-A28, A30-A34, A40-A45; tests "240 passed, 2
  skipped (VAL-2)"; generators 113/160/25 claims; both comparisons; the validation report; ruff; format; the reference
  record); `S10.validation` `not_applicable` (A4-4's block verbatim, B-81); `S10.gate`, `S10.ci` `unsupported`. Review
  fields `pending`. A first manifest at `c8892a26` was dropped unpushed (wording of two limitations; regenerated, as
  S07's B-41).
- B-84. DECISION (harvest classes, build-lane draft for design-lane review): limitations[0], [1], [3], [4], [5], [7],
  [9], [22], [24], [25], [27] and checks[S10.validation] -> E to U02 (`wilson-ig-v1` library-only: its scope, its
  validation status, the undetermined methanol-ethanol Lambda); [2], [6], [8], [10]-[21], [23], [26], [28]-[33] and
  checks[S10.gate], checks[S10.ci] -> P (scope statements, rights process, tool-qualification and measurement records,
  provenance, process). Alternative: the rights items [6], [12], [26], [30] -> E to L40. Reversible by: editing those
  harvest entries' class and `to`, then `t08_support_matrix.py --emit`.
- **MEASURED (HARVEST_SIZE):** `matrix.harvest_items()` = (51, 647, 82), was (50, 613, 79). `--emit` regenerated
  `docs/support-matrix.md`; `--check`: 0 problems. T08 C3 (`wilson-ig-v1: S10 has no U02 item in the harvest`) passes.
- HG line: `S10 HG c4f3751e208c540076d2dd8109d673769745a0dc..HEAD: PASS (37 appended; HARVEST_SIZE (50, 613, 79) -> (51, 647, 82))`.
  Measured at `870518e2` by S05's `check_harvest` (R-617) adapted to S10 (a scratch script, not committed).
- **OPEN (design lane), found by WO-S10-7:** `tests/test_t08_w2_inventory.py::test_a32_every_component_record_is_synthetic_or_a_vetted_real_record_with_rights`
  fails on `benchmarks/s10/records.yaml` (`synthetic: false` since WO-S10-3, `3e6986ee`): T08.A32 admits a real
  records file only through `VETTED_RECORD_FILES`, and "adding a file takes a design-lane amendment that names its
  vetting" (M01 spec §3.5, R-158; L01 spec §12.4, R-529). The failure predates WO-S10-7 and is not caused by A4-3.
  Not resolved here: which file vets `records.yaml` and with which retrieval predicate is a design-lane choice.
  Default the build lane would propose: vet by `s10_records.py --check` reproducing the records from the committed
  inputs plus `nasa7-low.json`'s retrieval hash, with the rights condition read from `docs/s10-rights-check.md`.
- **CI (run 40180210113, head `ba5968e8`):** check (x86-64) failure, 1 failed of 15 257 (T08.A32 above); default-install
  failure, 1 failed (T08.A32); check (aarch64) failure, 2 failed: T08.A32 and
  `tests/test_s10_records.py::test_saturation_check_never_passes_without_coolprop`. The second is
  `s10_saturation_points.py --check` with CoolProp installed: "water cross-check worst 3.542e-11;
  saturation-points.json DIFFERS" on aarch64. The check byte-compares CoolProp output written on x86-64, and CoolProp
  is not bit-identical across architectures (S07 spec §20, R-627). It predates WO-S10-7 (WO-S10-3). **OPEN (design
  lane):** whether that check compares within a tolerance off x86-64, or is run on x86-64 only. Not changed here (a
  tolerance is the design lane's).
- B-85 (orchestrator, after CI run 40187246167): `tests/test_s10_records.py::_coolprop_800` (added in `304b4b4b`)
  imported `CoolProp.__version__`, which S05.A28 (`test_a28_no_test_imports_the_cross_check_or_its_libraries`) forbids
  in any test; all three CI jobs failed on that one test. The version is now read from the distribution metadata
  (`importlib.metadata.version("CoolProp")`) without importing it. Test hygiene only; no assertion changed. Locally:
  S10 records + S05 envelope + T08 W2 288 passed, 1 skipped (no CoolProp); 269 passed, 1 skipped with CoolProp 8.0.0.

## WO-S10-7a (the manifest with D19, the ledger, the harvest; spec §18 A5-3)

- **MEASURED (manifest):** `evidence/S10/f974cc8782761f23cef5c66ba976fee7fa46ec98/manifest.json`, generated from a clean
  tree at `f974cc87`: `status: tested`, 53 of 56 checks pass (A54-A58 added; tests "244 passed, 2 skipped (VAL-2)");
  `S10.validation` `not_applicable`, `S10.gate`, `S10.ci` `unsupported`; `requirements: ["D08", "D19"]`. A first
  manifest at `1fbd7c53` was dropped unpushed (`S10.ruff` failed on a docstring line of the generator, E501).
- B-86. DECISION (harvest classes of the new manifest, build-lane draft for design-lane review): the 33 limitations and 3
  checks whose text equals the `c4f3751e` manifest's keep B-84's class and `to`. The 8 new limitations are P: the seven
  §18 A5-7 items (limitations[27]-[33]: rights verdict, Lambda vetting, stored fit, aarch64 floor, water's constants,
  D19 not met, M01/L01) and the reworded B-83 item (limitations[36]), all scope statements, rights process or measurement
  records under B-84's P description. Alternative: [28] (the Lambda are not vetted by T08.A32) -> E to U02. Reversible by:
  editing those entries' class and `to`, then `t08_support_matrix.py --emit`.
- **MEASURED (HARVEST_SIZE):** `matrix.harvest_items()` = (52, 688, 85), was (51, 647, 82). Pinned in
  `tests/test_m07a_harvest.py`. `--emit` regenerated `docs/support-matrix.md`; `--check`: 0 problems.
- B-87 (orchestrator, WO-S10-7a items 4-5): item 5 done (`records-vetting.json` in the rights check's per-file map,
  RC-07, repository only). Item 4's reword of the support-envelope note that cites B-83 is **not** applied to the
  existing entry (`support_envelope.yaml`, manifest `c4f3751e…`, `limitations[29]`): HG(b) (S05 IAPWS-95 spec, R-617)
  says the harvest only appends, so an earlier entry's note is not rewritten. That entry stays true of the manifest it
  harvests. The corrected wording is carried by the entries WO-S10-7a appended for the manifest at `f974cc87`
  (`limitations[36]`: "requirements lists D08 and D19 …"; and the A5-7 D19 scope line). Alternative: edit the old note
  and accept an HG(b) exception. Reversible by: editing that one note.

## WO-S10-8 (spec §19 A6-10; VAL-2, A51 and A53)

- B-88 (step 1, the transcription; spec §19 A6-1, A6-6): Kurihara, Minoura, Takeda and Kojima (1995), Tables 2
  (methanol + water) and 3 (ethanol + water), P, x1, y1 at 323.15, 328.15 and 333.15 K, 159 rows. Entry A (an
  opus-engineer agent): the PDF text layer as a draft, every P, x1 and y1 re-read against 300 dpi page crops, no
  discrepancy. Entry B (an independent opus-engineer agent): the 300 dpi page image only, no text layer; every value read
  twice, row counts confirmed by a pixel line profile. The two files are byte-identical, SHA-256
  `e129027986fa9c15ebf8e00d5fa040497708cb0c7a9d483263eefe2ba98090bb`, 7504 bytes, 160 lines. Copied unchanged to
  `benchmarks/s10/vle/kurihara1995_binaries.csv` (= entry A), `.A.csv` and `.B.csv`; all three hash to it. Both entries
  note, as printed and not as reading doubts, that ethanol + water's P is not monotone in x1 near the azeotrope
  (x1 about 0.9): 323.15 K rows 26-28, 328.15 K rows 29-30, 333.15 K rows 25-26; and y1 0.6688 then 0.6682 at 333.15 K
  rows 12-13. `docs/s10-rights-check.md` updated as A6-6 (RC-06, files checked, per-file map, `report.json` row); the
  paper's notice read from its first page (1995 ACS, article code 0021-9568/95/1740-0679$09.00/0; no reuse statement
  in the paper). No script or test changed. Nothing computed on the 1995 data.
- **MEASURED (step 2, x86-64, Python 3.13.5):** `s10_validation.py --write` printed `VAL-1 within band; VAL-2 within
  band; VAL-3 not validated within band`. methanol + water (52): AAD_P 0.01086763935 (1.087 %), AAD_y 0.004754833453,
  max |r| 0.02670, max |dy1| 0.01703, within band. ethanol + water (107): AAD_P 0.00289894189 (0.2899 %), AAD_y
  0.004075153801, max |r| 0.02124, max |dy1| 0.01543, within band. Pooled (not judged): 0.5505 %, 0.004297. Below the
  records' 30 kPa bound: measured 1 (methanol + water) + 39 (ethanol + water) = 40 of 159; computed 1 + 39 = 40. No
  refusal, no non-finite value; C1-C5 hold. Worst A51.2-A51.5: set S (126 states) P over P_eval 6.7e-16, y 2.2e-16;
  closed form P 1.1e-15, y 4.4e-16; bubble condition 8.9e-16 at 47 in-domain states; swapped-Lambda change at least
  1.5e-4. Set R (42 states) 7.8e-16, 2.2e-16; 8.9e-16, 2.2e-16; 8.9e-16 at 14 states; at least 2.8e-3. S reproduces
  A6-3's floors (none exceeds them). `pytest tests/test_s10_validation.py`: 11 passed, 0 skipped. `--check`: OK.
  `report.json`'s convention, records, VAL-1 and VAL-3 objects are byte-identical to `d42fcf08`'s (compared by
  `json.dumps`), and the Markdown diff is the VAL-2 section only. Observation, not a change: A6-1 expected the water-rich
  end of every isotherm below the domain; for methanol + water only one printed point (of 52) is, as Table 2 has few
  water-rich points. `s10_evidence_manifest.py`'s `validation_check` still requires a PENDING VAL-2 and now refuses;
  that is step 5's edit.
- B-89 (step 2, format and structure only; no number depends on it): (a) the per-isotherm table prints T as the
  stored float's repr (`323.15`), which A6-7's template leaves unformatted; (b) `bubble_p(provider, n, t, p_eval)` takes
  the lnphi names from `provider.describe().components`, so the one function serves set S's synthetic records and the
  real ones; (c) the refusal is carried by `Val2RefusedError` (ruff N818) and turned into A6-3's `SystemExit` message in
  `val2()`. Alternative for (a): `f"{T:.2f}"`, identical output for these three T. Reversible by: editing
  `_markdown_val2` / `bubble_p`.
- **Step 4 (spec §19 A6-9, A4-3 steps 1-4), MEASURED:** `UNCERTAINTY`'s VAL-2 sentence is A6-9's, slots from the
  committed `report.json`'s `"VAL-2"` (verdict `within band`, both binaries `within band`; 1.09 %, 0.0048; 0.29 %,
  0.0041; 1 + 39 = 40 below the domain), equal to the verdict's values (`S10-validation-verdict-val2.md`). Cascade:
  `records.yaml` `d4a39730…` → `033e10b3…` (the `uncertainty` line only); `fit-report.json` `0031b510…` → `fef462e7…`
  (its `records_sha256` line); `reference_values_real.yaml` `2e9d5130…` → `3ccb4180…` (its `records_sha256`); IDAES
  `inputs.json` `8d6c881d…` → `d5677286…`, DWSIM `e9428f4b…` → `771d2f22…` (two hash lines each); IDAES
  `comparison.json` `67d26532…` → `f606e2c6…`, DWSIM `a808cd09…` → `872f3688…` (three hash lines each);
  `records-vetting.json` `7deac2a4…` → `f6a19d20…` (its `records_sha256` line; `--emit --nasa-yaml` with Cantera
  3.2.0's file `4de6199d…` from `~/.cache/of-rc-c899c85/venv-xcheck`). Neither `qualification.json` changed
  (`aecd2279…`, `e4d09073…`). Restricted diff: with every 64-hex string masked, the only changed lines besides
  `uncertainty` are `inputs.json`/`records.yaml`/`reference_values_real.yaml`/`sha256`/`records_sha256` hash lines.
  Lineage step 2 appended (authority `S10 spec §19 A6-9`, `commit` written by the next commit, B-80). Checks:
  `s10_validation.py`, `s10_records.py` (25 claims), `s10_reference.py --real` (160 claims), both comparisons,
  `s10_records_vetting.py --nasa-yaml` (12 controls) `--check` all pass; `tests/test_s10_records.py
  tests/test_s10_provider.py` 113 passed, 0 skipped; ruff check and format clean.
- **Step 5, MEASURED (manifest):** `evidence/S10/f6f27c3f8aca7cb360287e531cd03e2033c32e16/manifest.json`, generated from a
  clean tree at `f6f27c3f` (the generator commit): `status: tested`, 53 of 56 checks pass (tests "248 passed, 0
  skipped"); `S10.validation` `not_applicable` with A6-9's block (checked equal to the spec's text with the slots
  filled), both verdict documents cited by path and SHA-256 (`37750062…`, `c0abc483…`); `S10.gate`, `S10.ci`
  `unsupported`; `requirements: ["D08", "D19"]`; review fields `pending`. Limitations 47 (was 41): the six §19 A6-13
  items and A6-9's validation sentence added, the old validation sentence gone. D08, D19 and the S10 package entry of
  `docs/requirements.yaml` cite it. B-90 (step 5, generator form only): the two validation verdict documents are the
  list `verdict_documents` (was the object `verdict_document`), and `validation_check` also refuses unless the
  block's AAD values equal the report's under A6-9's formats. Alternative: keep the old key for the first file and add
  a second key. Reversible by: `validation_check()` and a regeneration.
- **OPEN (design lane), observations from step 5, not changed:** (a) §19 A6-13's first item ("Any VAL-2 result.
  Nothing has been computed on the 1995 data.") is harvested verbatim into the manifest that reports VAL-2's result, as
  A6-10 orders (`limitations[34]`); A2-6 and A3-9 carry "(as written at Amendment N)" in their names, A6-13 is named
  "§19 A6-13" as A6-10 says. (b) the generator's rights limitation still reads "RC-05 and RC-06 (the 1993 paper's
  Tables II and V)"; RC-06 now also covers the 1995 paper (B-88). A6-10 lists no edit to it.
