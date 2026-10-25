# S10 — verdicts on evidence (reference comparisons: IDAES S10.A40–A44, DWSIM S10.A45)

**Lane:** design (`verdict`), package S10, after WO-S10-4b and WO-S10-5b. **Date:** 2026-10-25. **Branch:** `wp/S10` at
`ca0aa5b7`. **Authority:** `docs/derivations/S10-spec.md` (SHA-256 `2079ea6c…b3bd`): §8, §8.1, §8.2, the assertion rows
of §7.5 for A40–A45, and §16 (Amendment 3: A3-1 to A3-8; register R-716 to R-719). Frank's answers: Q-F5 and Q-F6 in
`docs/FRANK_QUESTIONS.md`, section S10. The form follows `docs/reviews/S03-verdicts.md` (on `wp/S03`, `05e94fab`).

**Standing.** These are agent verdicts, numerical and procedural. They are not scientific review. Human numerical and
process-modeling sign-off is recorded separately, and nothing here claims it. This document does not set `reviewed`, and
it does not replace the package's single `reviewer` pass. No S10 manifest exists yet (`evidence/S10/` holds only
`artifacts/`). No tool was run for this verdict; §0 lists what was run.

## The verdicts

| # | Criterion (as registered) | Verdict |
| --- | --- | --- |
| 1 | **S10.A40.** IDAES readbacks (P^sat at three sites, γ, γ_bubble, h^L, h^V at the four RB points) match the generator to 1e-10 relative, before any flash | **MET.** 68 rows, worst 2.86e-15 relative (RB-T360-x1, P^sat of H2O). The τ mapping equals the generator's `idaes_mapping` exactly. A transposed τ would move ln γ by 0.150 at the RB points |
| 2 | **S10.A41.** IDAES at I1–I14, each state at its selected attempt (A3-2); tolerances of §8.1, unchanged | **MET for 13 states: 13 `AGREE`, 0 `DISAGREE`.** **I3 is `NOT_COMPARABLE(no_optimal_attempt)`.** That is final for S10 (A3-2 item 5), and it is not a pass. Worst compared quantity: I9 β, 0.00985 of its tolerance. I6 is LIQUID and I7 is VAPOR, as ours |
| 3 | **S10.A42.** (a) The smoothing prediction is ≤ τ/10 (β, x, y) and ≤ 0.1 of the tolerance (K, h) at every rung. (b) At each selected two-phase attempt, \|T_eq − T\| × each sensitivity is ≤ 0.1 of its tolerance | **MET.** (a) Worst 7.75e-9 (I13, β/x/y; bound 1e-8), 0.012 τ_K (I9), 3.8e-4 τ_h (I13). The generator's `--real --check` passes (160 claims). (b) Worst 0.00986 (I9) |
| 4 | **S10.A43.** Tool-only checks before any comparison: (a) rung dependence, (b) setting dependence; each ≤ 0.1, phase identities equal | **MET.** (a) Worst 0.00985 (I9, β, 1e-6 against 1e-4) over 19 pairs. I6 and I7 identities are equal. (b) 18 attempts converged in both runs: ratio exactly 0, at the same iterate and iteration count. **(a) does not apply at I2, I11 or I13**, which each converged at one rung only |
| 5 | **S10.A44.** IDAES's bubble and dew equations reference the γ that A3-3 reads: four exact string patterns | **MET, on Pyomo's verbose rendering.** All four patterns hold there. **ESC-7 is ruled: the verdict stands** (§1.5). On the plain `str()` rendering, pattern 1 fails because of how that rendering works, not because of the equation |
| 6 | **S10.A45** (amended by A3-6). DWSIM: the readbacks (qualification); two-phase states gated at g ≤ 1e-8; I6 and I7 compared on the phase identity | **MET as amended.** γ readback: 126 rows, worst 4.93e-16 against 1e-9. **All 12 two-phase states are `NOT_COMPARABLE(reference_accuracy: dwsim_flash_floor(g))`**, with g from 3.27e-8 (I14) to 2.07e-6 (I10). I6 (LIQUID) and I7 (VAPOR) are `AGREE` on the phase identity. **DWSIM provides no two-phase numerical verification** |
| 7 | **ESC-8.** The spec expected I11 `NOT_COMPARABLE`, but it converges at 1e-4/MA27 | **Carried, and ruled immaterial to the rule.** A3-2's rule selects I11 mechanically, and it is `AGREE` (0.00049). Q-F5's answer covers it a fortiori (§1.6). The spec's factual statements about I11 are errata (finding F1) |
| 8 | **B-62.** DWSIM `inputs.json` was regenerated, so `qualification.json`'s `inputs_sha256` names the earlier file | **Provenance holds, by git audit.** The record set does not prove it on its own (§2.3, finding F3) |

**Evidence classes.**
- Rows 1–4 and the I6/I7 rows of 6 are **numerical verification by an independent implementation** (D19): the same
  equations and the same parameters, run in different code with a different solution algorithm.
- Row 5 is a procedural check on how the tool's equations are read.
- The A45 readbacks are qualification of the mapping. They are not a flash comparison.
- None of this is **empirical validation**, which is WO-S10-6 (§9.6). None of it is **optimality evidence**.
- Package status for these items: implemented and tested (230 S10 tests pass). Not reviewed, not released.

## 0. The evidence judged, and its provenance

| Record | Produced by, where | SHA-256 |
| --- | --- | --- |
| IDAES `inputs.json` | `scripts/s10_idaes_comparison.py --write-inputs` (WO-S10-4b) | `92aa171f…70f1` |
| IDAES `qualification.json` | `spikes/references/s10_qualify_idaes.py` in `.venv-idaes`: idaes-pse 2.13.0, Pyomo 6.10.1, Ipopt 3.13.2, Python 3.13.5. Environment fingerprint matches `docs/reference-environments.md` §3. Package source SHA-256 `8b0ab128…d588`. Committed at `dcf6ea19` **before** `comparison.json` held any difference (checked: at `dcf6ea19` the comparison is still WO-S10-4's, with statuses only and no rows) | `aecd2279…da1b` |
| IDAES `comparison.json` | `scripts/s10_idaes_comparison.py --write`, `d3b3ec85` | provenance block names the five inputs above and `records.yaml` `74dc4e54…`, `reference_values_real.yaml` `52e46110…`, `s10_reference.py` `c4dd73ff…`. All five recomputed: they match |
| DWSIM `inputs.json` | `--write-inputs`, first at `ae9aab8c` (`28676a25…`), regenerated at `6c812ff4` (B-62) | `0dc64095…51e4` |
| DWSIM `qualification.json` | `spikes/references/s10_qualify_dwsim.py`: DWSIM 9.0.5.0, .NET 8.0.31, pythonnet 3.1.0; fingerprint matches. `f3388de2`, unchanged since, like the tool script | `e4d09073…e28f` |
| DWSIM `comparison.json` | `scripts/s10_dwsim_comparison.py --write`, `6c812ff4` (WO-S10-5b) | provenance block matches the files on disk |
| The expectation | `docs/derivations/scripts/s10_reference.py --real`: mpmath at 50 digits, design lane. It is independent of `openflowsheet` and of both tools | `reference_values_real.yaml` `52e46110…` |

**What I ran on `ca0aa5b7`.**
- Both comparison scripts with `--check`: "inputs.json recomputes identically; comparison.json recomputes identically",
  for both tools.
- Both generators: `s10_reference.py --check` gives 113 claims and `--real --check` gives 160 claims, and both match.
- `pytest` on the five S10 test files: **230 passed**.
- **An independent recomputation from the raw records.** It used my own scripts, which import nothing of the build
  lane's comparison code, and it recomputed:
  - the attempt order and options;
  - the A3-2 selection;
  - every A41 row against the YAML;
  - A42 (b);
  - A43 (a) and (b);
  - A44 on both renderings;
  - A40 traced to the raw readbacks;
  - the run-R reproduction against `e63f98c2`'s record (SHA-256 `a77c10fe…`, identical: 67 attempts, 0 differences,
    53 with quantities, 0 differences);
  - DWSIM's g from DWSIM's own (x, y, β), with my own Wilson and P^sat code. That code reproduces IDAES's readback γ to
    2.3e-16 and P^sat to 2.1e-15.
- Every recomputed label, ratio and g equals the record's.

**Independence of the expectation from the thing judged.**
- A41 compares IDAES with the generator's closed forms, not with the provider. The provider is tied to the generator by
  A34 (worst 0.059 of tolerance).
- A41 therefore verifies the generator's closed-form flash against IDAES. Through A34 it also verifies the provider.
- The IDAES side is IDAES's own Pyomo expressions, solved by Ipopt as a smooth-flash NLP. Ours is a closed-form flash
  in mpmath. The two codes share no source, no algorithm and no arithmetic.
- They share, by design: the parameters (`records.yaml`), the model equations, and a mapping built from our
  coefficients. So an error in the model or in the parameters passes both sides (spec §0 item 2).

## 1. IDAES (A40–A44)

### 1.1 Criteria as registered

- **Settings.** ε_1 = ε_2 ∈ (1e-4, 1e-5, 1e-6) K. Ipopt `tol` = 1e-10, `constr_viol_tol` = 1e-9 (A3-1),
  `max_iter` = 3000. MA27 first, then MUMPS only after a non-converged MA27 attempt. The package's own initializer runs
  with IDAES defaults and no per-state tuning.
- **Converged** means Pyomo optimal termination and "EXIT: Optimal Solution Found.".
- **Selection.** Each state is taken at its first converged attempt, in the order (ε, then solver). A state with none is
  `NOT_COMPARABLE(no_optimal_attempt)`.
- **A43 before any comparison.** Either check can only give `NOT_COMPARABLE`.
- **Tolerances.** 1e-7 absolute (β, x_i, y_i); 1e-7 relative (K_i); 0.05 J/mol (h^L, h^V). The phase identity is
  exact at I6 and I7, by B-36's rule.

**Checked against the records.**
- Every attempt of run A3 carries exactly these final-solve options (54 of 54).
- Every attempt's (z, T) equals the registered state exactly.
- ε_1 = ε_2 = the rung at every selected attempt.
- At the selected attempts: worst unscaled violation 2.33e-10 ≤ 1e-9, worst scaled error 6.1e-12 ≤ 1e-10.
- The per-state order (ε outer; MA27, then MUMPS only after a non-converged MA27) holds. The tool walks the states in
  lexicographic id order (I1, I10, I11, …, I2, …). That is immaterial: each attempt builds a fresh `ConcreteModel`, and
  the only global it sets, the initializer's linear solver, is set anew per attempt (finding F4).

### 1.2 Per state

| State | Mixture, z | T (K) | Selected (ε/solver) | Converged rungs | Verdict | Worst quantity: \|Δ\|/tol | A42 (b) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| I1 | MeOH–H2O 0.1 | 365.51 | 1e-4/MA27 | all three | **AGREE** | β 1.3e-5 | 1.3e-5 |
| I2 | MeOH–H2O 0.3 | 357.42 | 1e-6/MA27 | 1e-6 only | **AGREE** | K_CH3OH 3.1e-8 | 0 (shift below ulp(T)) |
| I3 | MeOH–H2O 0.5 | 351.27 | none | none | **NOT_COMPARABLE(no_optimal_attempt)** | — | — |
| I4 | MeOH–H2O 0.7 | 345.66 | 1e-4/MA27 | all three (1e-6 by MUMPS) | **AGREE** | β 2.0e-4 | 2.0e-4 |
| I5 | MeOH–H2O 0.9 | 340.29 | 1e-4/MA27 | all three | **AGREE** | β 8.0e-4 | 8.0e-4 |
| I6 | MeOH–H2O 0.4, subcooled | 343.62 | 1e-5/MA27 | 1e-5, 1e-6 | **AGREE** (LIQUID; β = 3.5e-13) | identity | — |
| I7 | MeOH–H2O 0.4, superheated | 366.56 | 1e-4/MA27 | all three | **AGREE** (VAPOR; 1 − β = 4.7e-11) | identity | — |
| I8 | EtOH–H2O 0.2 | 360.93 | 1e-4/MA27 | all three | **AGREE** | K_C2H5OH 1.7e-4 | 1.7e-4 |
| I9 | EtOH–H2O 0.6 | 352.86 | 1e-4/MA27 | all three | **AGREE** | β 9.85e-3 | 9.86e-3 |
| I10 | EtOH–H2O 0.4 | 356.02 | 1e-4/MA27 | all three | **AGREE** | K_C2H5OH 1.07e-3 | 1.07e-3 |
| I11 | ternary (0.2, 0.3, 0.5) | 353.34 | 1e-4/MA27 | 1e-4 only | **AGREE** | K_C2H5OH 4.9e-4 | 4.9e-4 |
| I12 | ternary (0.4, 0.2, 0.4) | 350.09 | 1e-4/MA27 | all three (1e-6 by MUMPS) | **AGREE** | β 3.1e-4 | 3.1e-4 |
| I13 | ternary (0.1, 0.6, 0.3) | 351.15 | 1e-4/MA27 | 1e-4 only | **AGREE** | β 8.0e-3 | 8.0e-3 |
| I14 | MeOH–EtOH 0.5 | 344.84 | 1e-4/MA27 | all three | **AGREE** | β 3.5e-5 | 3.4e-5 |

**I3 in the record.** All six attempts (three rungs, both solvers) end the same way. The initializer raises "Cannot load
a SolverResults object with bad status", and the final solve ends "Restoration Failed!" at an unscaled violation of 1.0.
That is far from the floor, so it is not the A3-1 effect. Under A3-2's closure this is a capability result of IDAES 2.13
from this start, and it is final.

**Coverage after I3.**
- Methanol–water is compared at four of its five mid-band compositions (I1, I2, I4, I5), and its phase identity at I6
  and I7.
- Ethanol–water at all three (I8–I10).
- The ternary at all three (I11–I13).
- Methanol–ethanol at its one state (I14).

### 1.3 The differences are the smoothing, and nothing else (my check; not a registered criterion)

- At every two-phase state, IDAES's T_eq − T equals the smooth max/min prediction ε²/(4 d_b) − ε²/(4 d_d^I). Here d_b
  is the distance to the generator's bubble and d_d^I the distance to its `idaes_dew_T`.
  - The ratio is 0.9995–1.0011 over the ten states with a resolvable shift.
  - I2's predicted 6.2e-15 K is below ulp(T), and IDAES's shift there is exactly 0.
- Each state's worst A41 ratio equals its A42 (b) value |T_eq − T| × sensitivity to two or three digits: I9 0.009853
  against 0.009858, I13 0.008039 against 0.008036, I10 0.001067 against 0.001065.
- So the residual differences are the predicted artefact of IDAES's smooth flash. The agreement of the equations
  themselves is tighter than the table shows.
- IDAES's T_bub equals the generator's bubble temperature to within one ulp (5.7e-14 K) at every selected two-phase
  state.

### 1.4 A43, and A3-1's premise checked

- **(b) is exactly 0.** At the 18 attempts that converged under both `constr_viol_tol` values, the two runs give the same
  iterate after the same number of iterations. Changing the unscaled stop moved no answer that was already optimal.
- **The newly converged attempts.** There are 14 attempts that end optimal only under 1e-9: I4, I8, I9 and I10 at each
  rung, I2 at 1e-6, and I11 at 1e-4. I compared each one's run-R iterate (loaded although not converged) with its run-A3
  optimum.
  - They differ by at most **3.1e-7 of the tolerance** (I9 at 1e-6).
  - The floor stalls had reached the answer, and only the stop test refused it.
  - That is A3-1's premise ("whether an attempt passes depends on where the root falls between representable T_bub"),
    now measured.
- **(a) has no reach at I2, I11 and I13.** A3-4 anticipated I13 only. For these three states the evidence on smoothing
  is A42 (worst 0.0080 of tolerance, I13) and §1.3's exact match of the T_eq shift.

### 1.5 A44 and ESC-7: the verdict stands on the verbose rendering

**Facts.**
- In the verbose rendering, the bubble equation names `activity_coeff_comp_bubble`, `A_bubble`, `Gij_coeff_bubble` and
  `_p_sat_bubbleT`, with their bodies in `mole_frac_comp` (the feed z). It does not name `activity_coeff_comp`.
- The dew equation names `activity_coeff_comp` (the state block's variable) and `_p_sat_dewT`. It does not name
  `activity_coeff_comp_dew`.
- In the plain rendering, the bubble equation contains only `mole_frac_comp`: γ(z) is there, inlined, and no γ
  variable appears. The dew equation contains `activity_coeff_comp`.

**Why the verdict stands.**
1. A3-4 fixes the four patterns and an exact match. It does not fix the rendering. Pattern 1 asks for a *name*, so it
   presupposes a rendering that shows named Expressions by name. Plain `str()` inlines them, so on it pattern 1 fails
   for every IDAES version that keeps the named Expression. That includes 2.13.0, whose bubble equation does use it
   (package source ll. 1828, 1893).
   Reading A44 on the plain rendering would make it unsatisfiable by construction. It would test nothing.
2. On the verbose rendering, all four patterns keep the power A3-4 wants.
   - A bubble equation switched to the γ variable would show `activity_coeff_comp[` and fail pattern 2.
   - A dew equation switched to γ(z) would show `activity_coeff_comp_dew[` and fail pattern 4.
3. The reading A44 guards is also established by the numbers, at a margin it does not need.
   - IDAES's T_bub equals the generator's γ(z) bubble temperature to 1 ulp.
   - IDAES's T_dew equals the generator's `idaes_dew_T` (γ at the flash liquid) to ≤ 7.7e-10 K at every two-phase state.
   - At I7, T_dew equals the true dew exactly (difference 0.0). At I6 it equals the γ(z) dew to 1.1e-12 K.
   - Under the other reading, the dew would move by up to 1.9 K (A3-3's table).
   - These are envelope temperatures. They classify nothing (A3-3 item 3), and they are cited only as corroboration.
4. **Timing.** B-42 was chosen after pattern 1 was seen to fail on the plain text, but in the blind commit `dcf6ea19`,
   before any A41 difference existed. It changes no equation, no compared quantity and no tolerance.

**Limitation that travels.** A44 holds on Pyomo 6.10.1's `expression_to_string(expr, verbose=True)`. A later Pyomo
that changes that rendering could break the match without any change in IDAES. The spec should name the rendering
(finding F2).

### 1.6 ESC-8: I11, and Q-F5

**The record.**
- At 1e-4 with MA27, I11's initializer completes in both runs.
- In run R, the final solve stalls after 9 iterations ("Search Direction is becoming Too Small"). Its unscaled violation
  is 1.89e-10 at `eq_temperature_bubble`: a floor stall that A3-1's list of stalls omits.
- In run A3, it is optimal at iteration 0, and its run-R iterate is identical to the optimum (ratio 0).
- At 1e-5 and 1e-6, the initializer fails with both solvers.

**The ruling.** A3-2's rule selects I11 at 1e-4/MA27. Nothing was chosen, and I11 is `AGREE`.

**Q-F5.** Frank accepted IDAES coverage *without I3 and I11* ("Yes, enough"). The actual coverage lacks only I3, which
is a strict superset of what he accepted, so his answer covers it a fortiori. No new question for Frank arises.

**Errata.** These statements in the spec and register are now false and should be corrected by the design lane:
- A3-2 "Rejected", third bullet: "It fails in every attempt at I3 and I11".
- A3-10 Q-F5's premise.
- A3-8's "Expected" list.
- R-717's "IDAES's initializer failures (I3, I11)".

The rule they serve is unaffected (finding F1).

### 1.7 Alternatives rejected

- **Count I3 as a pass, or drop it from the denominator.** It is `NOT_COMPARABLE`: no reference value exists. It stays
  listed as one of 14 states, with its six attempt records.
- **Add a path variant for I3** (warm start, ε continuation, another initializer). A3-2 rejected and closed this. The
  failure is known now, so any variant would be chosen for it.
- **Judge A44 on the plain rendering and record it `NOT MET`.** Rejected in §1.5: that reading makes the assertion
  unsatisfiable without testing anything.
- **Judge A44 on the rule functions' source text.** That is a third rendering, and it is weaker. It shows what the
  package writes, not the expression Pyomo hands to Ipopt.
- **Require A43 (a) for I2, I11 and I13 by a further run.** The ladder is closed (A3-2). A42 and §1.3 carry the
  smoothing evidence for these states.
- **Compare all states at one common rung.** No rung converges at every state. A3-2 rejected the "most states" rung,
  because it would discard converged states.

### 1.8 What would change these verdicts

- A harness defect found in the tool record: an attempt whose path is not A3-2's. The run would then be repeated and
  disclosed (A3-2 closure), and A41 reopens for the affected states.
- A failure of `s10_idaes_comparison.py --check`, of the generator's `--real --check`, or of a change to `records.yaml`.
  Any of these reopens A40–A43.
- A different IDAES, Pyomo or Ipopt version, or a changed environment fingerprint. That is a new comparison, not this
  one. A44 must pass first (R-718).
- A reviewer finding that B-36, B-42 or B-43 misreads the spec. B-43 leaves K out of A43 for components absent from
  the feed. That would reopen A41's I6/I7 rows, A44 or A43 respectively.

## 2. DWSIM (A45)

### 2.1 Criteria as registered (§8.2 as amended by A3-6)

- **Qualification.** The γ readback at each state's (T, x) matches ours to 1e-9 relative, before the flash. B-51 takes
  the feed z and the two RB compositions.
- **Gate.** At a two-phase state, g = max(DWSIM's own equilibrium residual, its balance residual), from DWSIM's x, y and
  β with the closed forms. If g > 1e-8, every A41 quantity is `NOT_COMPARABLE(reference_accuracy: dwsim_flash_floor(g))`.
  The differences stay as unclassified diagnostics.
- **I6 and I7.** The phase identity, by B-36's rule.
- **Settings.** B-50 to B-53 are ratified. Nothing is rerun.

### 2.2 Per state

- **Qualification passes.**
  - The applied A_ij equal the rule exactly. The effective Λ matches `records.yaml` to 3.4e-16.
  - γ: 126 rows, worst 4.93e-16 (I8, CH3OH). My own Wilson code gives 4.8e-16.
  - Informative rows, with no tolerance registered: P^sat 1.1e-14, Δh_vap 4.8e-16, c_p^ig 5.9e-16.
  - DWSIM's h^ig is off by 0.026 J/mol, from its 10-step quadrature (ESC-52).
- **All 28 attempts converge.** The two rungs give bit-identical flash outputs at all 14 states (rechecked). The
  registered tolerance never acted.

| State | g = max(eq, balance) | Equilibrium residual | Balance residual | Status | Unclassified diagnostic (max \|Δ\|/tol) |
| --- | --- | --- | --- | --- | --- |
| I1 | 4.87e-7 | 4.87e-7 | 5.1e-9 | NOT_COMPARABLE(dwsim_flash_floor) | 6.2 |
| I2 | 8.66e-7 | 8.66e-7 | 2.1e-8 | NOT_COMPARABLE | 13.2 |
| I3 | 6.42e-7 | 6.42e-7 | 1.7e-8 | NOT_COMPARABLE | 10.6 |
| I4 | 1.92e-7 | 1.92e-7 | 4.5e-9 | NOT_COMPARABLE | 3.7 |
| I5 | 6.69e-8 | 6.69e-8 | 2.4e-10 | NOT_COMPARABLE | 1.5 |
| I6 | — | — | — | **AGREE** (LIQUID, β = 0) | — |
| I7 | — | — | — | **AGREE** (VAPOR, β = 1) | — |
| I8 | 1.92e-6 | 1.92e-6 | 2.1e-8 | NOT_COMPARABLE | 38.3 |
| I9 | 2.81e-7 | 2.81e-7 | 1.7e-9 | NOT_COMPARABLE | 13.7 |
| I10 | 2.07e-6 | 2.07e-6 | 2.3e-8 | NOT_COMPARABLE | 66.9 |
| I11 | 9.08e-7 | 9.08e-7 | 1.1e-8 | NOT_COMPARABLE | 21.9 |
| I12 | 4.38e-7 | 4.38e-7 | 5.7e-9 | NOT_COMPARABLE | 8.3 |
| I13 | 1.09e-7 | 1.09e-7 | 4.6e-10 | NOT_COMPARABLE | 6.8 |
| I14 | 3.27e-8 | 3.27e-8 | 1.1e-9 | NOT_COMPARABLE | 4.3 |

**How to read this table.**
- The least g is 3.3 times the gate (I14), so no classification is marginal.
- The diagnostics are **not** `DISAGREE`, and they must never be cited as one. Their size and order follow g, as a
  convergence floor would, while γ, Λ and P^sat agree to ≤ 1.1e-14.
- They are equally **not** evidence of agreement.
- §8.2 pre-registered this outcome as "a result, not a failure of S10".

### 2.3 B-62: does provenance hold?

**Yes, by audit of the git history. The record set does not prove it on its own.**
- `qualification.json` records `inputs_sha256` = `28676a25…`. That is the SHA-256 of `inputs.json` as committed at
  `ae9aab8c`, the harness commit, made before the tool ran. `qualification.json` was committed at `f3388de2`.
- `inputs.json` at `6c812ff4` (now `0dc64095…`) differs from that file in **one line**: the recorded SHA-256 of
  `reference_values_real.yaml`, `fa7c43f7…` → `52e46110…`. Amendment 3 added keys to that YAML.
- The states, records, settings and ladder are byte-identical. The I-states in the current `inputs.json` equal the
  current YAML's (n, T, P) exactly.
- `qualification.json` and the tool script are unchanged since `f3388de2`.
- So the DWSIM run was made on today's registered states, with today's inputs apart from that one hash line.

**What is missing.** A reader who recomputes `sha256(inputs.json)` today gets a mismatch with `qualification.json`.
Neither `s10_dwsim_comparison.py` nor its test checks that link. The explanation must travel with the record (finding F3,
§4).

### 2.4 Alternatives rejected

- **Compare h at the two-phase states** (ESC-51's proposal). A3-6 rejected it: DWSIM's floors (A·r·Δh, plus 0.026 J/mol
  of quadrature) can take the whole h tolerance at I10. An `AGREE` there would be weak evidence that a later package
  could cite as strong. The diagnostics show h within 0.05 J/mol everywhere. That is recorded, and it classifies
  nothing.
- **Compare at τ without the gate.** That would count DWSIM's hard-coded |ΔV| < 1e-6 stop as a model difference, and
  give 12 spurious `DISAGREE`s.
- **An Inside-Out rerun** (`UseIOFlash`). A comparison exists, so any new setting would be chosen after seeing DWSIM
  against our values. Frank answered Q-F6 "No".
- **Treat the γ readback as an A45 agreement.** It verifies the model functions, not the flash. It is qualification.

### 2.5 What would change this verdict

- A DWSIM rerun at a different setting. That is a new, pre-registered package on new states (A3-6, Q-F6), not a
  revision of this verdict.
- A defect in B-54's residual: g computed from something other than DWSIM's own x, y and β. My independent
  recomputation reproduces every g, so this is not expected.
- A changed DWSIM tree or .NET runtime fingerprint. .NET 8 support ends on 2026-11-10.

## 3. Separate findings (on documents this verdict does not change)

- **F1. Spec and register errata about I11** (§1.6): A3-2 "Rejected", A3-8 "Expected", A3-10 Q-F5, and R-717. A3-1's
  list of floor stalls also omits I11 at 1e-4/MA27. None of this changes a rule or a selection. It belongs to the design
  lane's next amendment.
- **F2. A44 should name its rendering**: Pyomo `expression_to_string(expr, verbose=True)`. Until it does, this verdict
  reads A44 on that rendering.
- **F3. The DWSIM record set is not self-certifying after B-62.** The manifest should cite both `inputs.json` hashes
  (`28676a25…` at `ae9aab8c`, `0dc64095…` at `6c812ff4`) and state the one-line difference. A future harness could
  record, beside `inputs_sha256`, the commit of the inputs it read.
- **F4. Lexicographic state order in the IDAES tool.** It is immaterial (§1.1), and recorded here so that nobody
  rediscovers it as a defect.
- **F5. D19's minimum evidence for S10** ("matched-model inputs, independence disclosure and verdicts").
  - The matched inputs are recorded (the `mapping` block, A40, the DWSIM `wilson_mapping_check`).
  - The verdicts are this document.
  - The independence disclosure is spread across spec §0 item 2, §8 and A3-9. §0 above states it in one place: shared
    parameters, equations and coefficient mapping; separate code, algorithm and arithmetic.
  - The manifest should point to it.
- **F6. I3 has no independent reference from either tool.** IDAES cannot start it, and DWSIM is gated at every
  two-phase state. Methanol–water at z_M = 0.5 rests on the closed-form verification (§7) alone.

## 4. What these verdicts do not establish, and the limitations that travel

**Not established.**
- **Validation.** Agreement with IDAES is numerical verification of the same equations with the same parameters. It says
  nothing about how well Wilson + ideal gas + the fitted P^sat describe methanol, ethanol or water. That is WO-S10-6
  (§9.6), judged separately.
- **Correctness of the model or of the parameters.** An error shared through `records.yaml`, the mapping, or the model
  form passes every check here (spec §0 item 2).
- **Agreement with DWSIM's flash at 1e-7.** No two-phase DWSIM quantity is compared. DWSIM verifies the model
  functions (to 1e-14) and two phase labels.
- **Any IDAES statement about I3**, or about states outside I1–I14, or about pressures other than 101 325 Pa.
- **Portability.** One platform (x86-64 Linux), one environment per tool, each pinned by fingerprint.
- **Rung independence at I2, I11 and I13.**
- **Anything about IDAES versions other than 2.13.0 with Pyomo 6.10.1.**

**Limitations that must travel into the manifest and the release report.**
1. IDAES: 13 of 14 states compared, all `AGREE`. I3 is `NOT_COMPARABLE(no_optimal_attempt)` under a closed ladder.
2. DWSIM: 0 of 12 two-phase states compared (`dwsim_flash_floor`, g ≥ 3.3e-8), and 2 of 2 phase identities `AGREE`.
   The two-phase diagnostics are neither agreement nor disagreement.
3. The worst IDAES agreement is 0.00985 of tolerance. It is IDAES's own ε smoothing, matched to its prediction.
4. A44 is read on Pyomo's verbose rendering (ESC-7).
5. A43 (a) does not cover I2, I11 and I13.
6. DWSIM's `qualification.json` names the pre-B-62 `inputs.json` (`28676a25…`, `ae9aab8c`). The one-line difference is
   stated in §2.3.
7. These are agent verdicts. No scientific review, and no human numerical or process-modeling sign-off, is claimed.
