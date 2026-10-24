# S10 review (WO-S10-1 and WO-S10-2: the provider `wilson-ig-v1`, the TP flash and `stability()`)

**Reviewer:** design lane (`reviewer`), 2026-10-25. **Reviewed:** `wp/S10` at `b415ccd7` (code head `83841192`),
range `main...wp/S10`: `src/openflowsheet/thermo/wilson_ig.py`, `thermo/stability.py`, `tests/test_s10_provider.py`,
`tests/test_s10_flash.py`, `docs/S10_DECISIONS.md` B-1…B-15. **Against:** `docs/derivations/S10-spec.md` §3–§5,
§7.3, §7.5; ADR 0047; R-700…R-710. **Errata:** spec §14 (Amendment 1), register R-711.

## Verdict

**The search is the §4 theorem's search, and it is implemented correctly. Residuals and derivatives describe the
same function.** The closed-form vapour trial, then one liquid-trial SS, then the two-phase SS, is a complete global
test within the model. Its edge cases are handled as §4.2 says: absent components, a pure fluid, the 1e-10 band and
dormant states. The label claims no more than its scope. Nothing here is a must-fix. Before `tested`, the build lane
should do findings 2 and 3, which are small. Finding 1 is a real limitation near azeotropes. It fails honestly
(`not_converged`, UNKNOWN), and Amendment 1 records it. The algorithm change belongs in S10-C (needs a decision; my
recommendation is below).

**What I re-ran** (scripts in the session scratchpad; none are committed):
- `test_s10_provider.py` and `test_s10_flash.py`: 173 passed (87 + 86), as reported.
- **Independent global check of the flash.** 3,900 random states over the verification domain in three runs:
  - 1,500 with the verification Λ;
  - 1,200 more with the verification Λ, half of them chosen inside the two-phase region;
  - 1,200 with stiff Λ (0.05–0.95), half of them chosen inside the two-phase region.

  Every run includes 15 % of states with one component absent and 5 % pure. Each result was checked by brute force on a 200-division simplex grid, with ln γ
  re-implemented from eq. 3.8 in numpy:
  - LIQUID: min D_V ≥ −1e-9;
  - VAPOR: min D_L ≥ −1e-9;
  - TWO_PHASE: fugacity equality ≤ 1e-11 through the independent ln γ, β ∈ (0, 1), and both surfaces above the
    common tangent plane;
  - `stability()` labels consistent with the flash.

  Result: **0 exceptions, 0 violations, 1,211 two-phase states.** The most iterations taken were 98 with the
  verification Λ and 422 with the stiff Λ.
- **Central-difference check of every `evaluate_phase` derivative.** 300 random states, both phases, stiff Λ, with
  one-sided steps at x_j = 0. Worst relative miss 2.0e-6, at a one-sided n-derivative. That is FD truncation; no
  entry disagrees.
- **Rachford–Rice fuzz:** 200,000 cases with the root pinned within ulps of a pole (z_i down to 1e-320). No exception,
  and β is always strictly inside the open bracket. B-9's termination argument holds.

## Findings, most severe first

1. **Near an azeotrope, the two-phase SS cannot reach δ_K** (`wilson_ig.py:884–918`; spec §5.6 δ_K row and §7.3's
   A·δ_K bound). **Should fix; needs a decision.**
   - **Why.** β is fixed by Σ z_i(K_i − 1), a cancelling sum over Σ z_i(K_i − 1)². A rounding of u in ln K therefore
     moves β by about u/|K − 1|², and x by about u/|K − 1|. The SS step then has a noise floor of about
     u·‖G‖/min|K_i − 1|. That passes 1e-13 once |K_i − 1| ≲ 1e-4.
   - **Reproducer.** Verification records, n = (0.0, 1.675339164407079, 0.324660835592921), T = 350.0397494670053 K,
     P = 101325 Pa. The result is `not_converged` after 1027 iterations. The step falls at ρ ≈ 0.5 to about 1e-11,
     then wanders between 1e-11 and 3e-11 for 970 iterations while β wobbles by 5e-7.
   - **How common.** Composition offsets 2e-5 to 1e-4 from the VB–VC azeotrope, five temperatures each inside the
     two-phase sliver (6e-9 to 1.5e-7 K wide): 7 of 20 are `not_converged`. The converged ones stopped on a noise
     dip, so their ln K error is about 1e-11, not A·δ_K. Their β has about 1e-6 relative error. That is the β
     conditioning itself (dβ/dT ≈ 1e8 K⁻¹ there), so x and y are still good.
   - **What holds.** The contract: never a wrong split, never a wrong label.
   - **What does not.** The δ_K floor of 3.55e-15 is a fact of the registered states, not of the method.
   - **Decision.** (a) Document it now and fix it in S10-C, or (b) change the stop rule now. **I recommend (a).** S10 is
     TP-only and library-only, and R-709 already gives S10-C an `architect` pass. S10-C's PH flash will search inside
     exactly this sliver, so it must fix this. The candidates are a stop tied to the conditioning (a floor estimate
     from min|K_i − 1| and ‖G‖, or stagnation detection, with the stated accuracy following it) or an iteration that
     does not pass x through β.
   - **Now.** Amendment 1 E-2 records the limitation. The build lane adds a test: a near-azeotrope set, about a dozen
     states like the reproducer, must each come back either `ok` with a valid split (fugacity equality ≤ 1e-10,
     0 < β < 1, balance ≤ 1e-13 n_tot) or `not_converged` with UNKNOWN and no outlets. Never `ok` with an invalid
     split. This assertion does not depend on which way the noise falls, so it holds on both architectures.

2. **A subnormal flow crashes the flash and `stability()`** (`wilson_ig.py:837–838`). **Should fix.**
   - **Cause.** F is built from n_i > 0, but ln z_i is taken of z_i = n_i/n_tot, which underflows to 0.0 when
     n_i < 2⁻¹⁰⁷⁵ n_tot.
   - **Reproducer.** n = (5e-324, 1.0, 1.0) or (5e-324, 0.0, 2.0) at F3's T and P. `flash`,
     `stability(…, "LIQUID")` and `stability(…, "VAPOR")` all raise `ValueError: math domain error`. §5.5 says
     `stability()` "reports and never raises", and every other path of `flash` returns a typed result.
   - **Fix.** One line: `flowing` = {i : z_i > 0}, per Amendment 1 E-1. Test both reproducers.
   - **Effect.** A single-phase result still returns the feed bitwise. In a split, the component's outlets are 0.0,
     an imbalance below 2.5e-324 n_tot.

3. **`StabilityReport.trial_composition` is not pinned** (`tests/test_s10_flash.py:418–420`). **Should fix (test
   only).**
   - **Gap.** A21 checks only that it sums to 1 and is positive, and A23 checks only that it permutes. Returning z,
     or the unnormalised W, would pass.
   - **Fix.** Check stationarity against `evaluate_phase`, which is independent of the search code:
     - as LIQUID: ln y_i − ln z_i − ln φ_i^L(z) is the same for every i;
     - as VAPOR: ln w_i + ln φ_i^L(w) − ln z_i is the same for every i, and equals −ln ΣW, so tm = 1 − ΣW to
       second order.

     Use a tolerance of about 1e-12.

4. **The iteration claims are facts of the verification set** (spec §5.6 SS_MAX row, claims SS-*). **Note.**
   - With the stiff Λ, the flash took up to 422 iterations, against at most 40 at the registered states.
   - Real ethanol–water Λ lies between the two.
   - WO-S10-3 should re-measure ρ and the iteration counts on the real records before §5.6's "10× margin" is claimed
     for real data.

5. **Extreme Λ overflows `math.exp`** (`_Search.ln_k`, `_normalised`, and `stability`'s weights). **Note.**
   - `record_lambda` accepts any finite Λ > 0. Λ_ij ≲ 1e-300 makes ln γ^∞ > 690, and `exp` raises `OverflowError`
     instead of returning a typed result.
   - Physical records cannot reach this.
   - Optional: bound Λ in the loader, for example [1e-6, 1e6], as a `record_lambda` refusal.

6. **The band edge is pinned by the constant, not by a state** (A17). **Note; no action.** F8 and F10 sit at −1e-8,
   which is 100 ε from the edge, so a state alone would accept any ε in (3e-11, 1e-8). The value is pinned anyway:
   `report.epsilon == 1e-10` is asserted, and the flash, `_label` and the report all read the one `EPS_TPD`.

**Not found:**
- no residual/derivative mismatch;
- no circular assertion: every expected value comes from the 50-digit generator, and A21's "flash = stability
  bitwise" is the intended one-search property;
- no departure from §5.3–§5.5's order of checks;
- no frozen-interface change.

## Rulings on the build decisions

| Decision | Ruling |
| --- | --- |
| B-4 (general projection) | **Accepted.** It is the same function as the shortcut (ID-ROW), it is independent of the extension off the simplex, and it gives homogeneity to rounding. FD agrees. |
| B-8 (two cap names) | **Accepted.** One registered value "per loop". It is needed so that A20 reaches step 4. |
| B-9 (Rachford–Rice) | **Accepted.** Reasons: β = 0.5 is always inside the bracket; the bracket halves at least every three evaluations (checked in the code: the midpoint after two non-halving Newton steps resets `reference`); it closes from both sides; the fuzz above passed. |
| B-10 (carry ln W) | **Accepted.** It is mathematically the spec's iteration with one rounding fewer. The reference values are polished fixed points, so no bit pattern depended on the literal form. |
| B-11 (`not_converged` has no outlets) | **Accepted.** §5.4 governs, and `iapws95`'s flash does the same. "Carries what it reached" is met by `iterations` and by the last step in the message. Do not edit the frozen docstring. |
| B-12, B-13 | **Accepted.** An unconverged tm is not a minimum, so a label cannot rest on it. An unknown phase is reported, not raised. |
| B-14 (`achieved_accuracy` = `"exact-double"`) | **Accepted for S10, with a note.** It is the only policy the cache ranks, and every iterative provider uses it. A new string would only make the cache miss. Finding 1 shows that near azeotropes the result does not achieve A·δ_K. Giving `achieved_accuracy` a meaning for iterative results is a project-level question for the design lane, not S10's. |
| B-15 (`_ln_gamma` factored out) | **Accepted.** It is proved inert by the E1–E6 hex dump. It also makes the flash's K and `evaluate_phase`'s ln φ^L literally one function. |
| B-1…B-3, B-5…B-7 | No objection. B-7's literal 0.29815 is the spec's θ₀. |

## Not examined

- the generator's 50-digit reference values (the specifier's);
- the registry and harvest tests, and the T08 C3 failures, which are expected until a manifest exists;
- `benchmarks/registry.yaml`'s S10 family beyond A27;
- formatting;
- WO-S10-3 onward: real records, IDAES, DWSIM and validation;
- aarch64: nothing in the S10 code depends on the architecture except the expected last-bit differences that the
  §7.3 tolerances absorb, and finding 1's suggested test is written to be architecture-independent.
