# M05's half of gate W24: evidence table for the `verdict` agent

Package M05, branch `wp/M05`, evidence `evidence/M05/cfecb15abcb2d632149e37749a107fa0b3991cc0/manifest.json`
(`status: tested`; numerical and process-model review `pending`). The clauses are design note §11 (claims, as
restated by ADR 0039 and §16–§21). Numbers are the manifest's. Gates G5 to G10 are judged on the committed records
under `benchmarks/m05/records/`; the tests that judge them are in `tests/test_m05_*.py`.

## Claims M05 may make

| Clause | Gates | Evidence (record or test) | Measured |
| --- | --- | --- | --- |
| 1. The pinned Pyomo TRF (6.10.1) composes with OpenFlowsheet models through a projection from the canonical `ProblemSpec` builders, with source maps and equivalence tests, and reproduces Pyomo's own example | G1, G2, G3, G4, G13 | `trsp-inventory-x86_64.json`; `test_m05_trf.py` (G2, G3); `test_m05_projection.py`, `test_m05_c1_projection.py` (G4); `test_m05_isolation.py` (G13) | G1: 31 objects, 31 distinct sha256, none of unknown origin. G2: 3 tests (patched version string and one changed module byte both give `UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNPINNED)`). G3: TR-E1 max abs difference to native 4.4e-16 (logged 2.2e-15), not bitwise. G4: nine states (six SYN-001, C1 at S0 and perturbed, TR-E1), worst ratio to threshold: residual 5.9e-4, Jacobian 7.1e-7, decision columns 4.2e-3. G13: 5 tests |
| 2. On the smooth gray-box example TR-E2 the TRF reaches the independent optimum within the decision tolerance, the candidate passes the parent checks, and the theorem assumptions are stated item by item | G5, G5b | `trust-region-study-tr-e2.json`, `-tr-e2-far.json`; `test_g5_tr_e2`, `test_g5b_tr_e2_far` | TR-E2: `TRF_EXIT_WITHOUT_STEP`, theta_recheck 3.0e-6, T* 673.6508 K, `DECISION_STABLE`. TR-E2-FAR: C1 `TRF_EXIT_UNVERIFIED(radius_limited)` (ratio 0.99997, candidate `NOT_STATIONARY_AT_DELTA`), C2 `TRF_CONVERGED` (ratio 0.0167), T* 673.6542 K, `DECISION_STABLE` |
| 3a. The same adapter runs with FD gradients on a derivative-free truth, with accuracy measured on a known truth | G6 | `trust-region-study-tr-e2-fd.json`; `test_g6_tr_e2_fd` | `TRF_CONVERGED`, theta_recheck 6.3e-8, T* 673.6294 K, 0.0213 K from TR-E2 (limit 0.1 K); `fd_check` `M05-fd-v2` class `truncation_dominated`, passed at eta 2^-14 |
| 3b. It runs with the real out-of-process reactor with complete true-model accounting | G7, G11 | `trust-region-study-real.json` (opt-in, committed), `test_m05_wo8_gates.py::test_g7_accounting` (five synthetic records), `test_m05_wo9_gates.py` | REAL: `DECISION_STABLE`, C1 `TRF_CONVERGED`, T* 653.1500352 K (bound-active), `fd_check` class `clean` at eta 2^-14, study cold 48 of 400, run ledger 32 cold of which 21 are the FD check's (outside the run cap by R-406; cap use 11 of 250), no budget exhausted on any record, store bijection holds on all six |
| 4. Parent-model checks at candidates (targeted check, poll at the decision tolerance against a noise floor) and the fixed-topology refinement loop work, including the N6 branch | G8, G9 | `trust-region-study-loop-s.json`, `-loop-r.json`; `test_g8_*`, `test_g9_loop_r` | LOOP-S: stage A `TRF_CONVERGED`, P2_A judged and passed, T* 653.150022 K, offset to the bound 1.097e-6 scaled (reported, not gated, R-430). LOOP-R (N6 branch): stage A skipped `surrogate_not_promoted`, `TRF_CONVERGED`, T* 653.150001 K, offset 5.3e-8 scaled, at the bound by section 7.4 |
| 5. Hard domains and admissibility are kept as constraints; extrapolation, surrogate-domain, synthetic and FD-gradient limitations are kept as stated limits | G7, G11, record content | The records' `limitations` and the manifest's `limitations` | REAL's limitations: `extrapolated`, `fd_gradient`. `extrapolated` is 12 of 61 reactor requests, reported, not a distance from the data (R-433; the flag flips between solves 3.5e-5 K apart at the data edge). Synthetic records carry `synthetic` |

## Replay and record gates behind the claims

| Gate | Evidence | Measured |
| --- | --- | --- |
| G10 | `tests/test_m05_g10_replay.py` (five in-process replays, `OMP_NUM_THREADS=1`), `scripts/m05_wo9_real.py --replay` | 5 passed; `REPLAY PASS REAL differences=0`. Same machine only; the cross-architecture comparison was not run |
| G12 | `tests/test_m05_study_record.py` (schema, section 8.3 arithmetic and identity on every committed record; every `fd_check` float classified), readiness tests | 210 passed (1 skipped in the nlp environment, passing in the default one); readiness 22 passed; default-install `UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNAVAILABLE)` 2 passed in the default environment |
| Gate | `scripts/gate.sh` at the N2 fix | 9290 passed, 31 skipped; nlp tier 186 passed, 1 skipped |

## What M05 does not claim (section 11), and the facts that bear on it

- Global optimality: every record has `claims.global_optimality: false`.
- Convergence guarantees or a validated plant optimum for the real reactor: REAL's T* is on the lower bound
  (1.76e-6 scaled), every reactor result is extrapolated beyond the kinetics' data domain (R-169), Pyomo 6.10.1 has no
  restoration phase, and A3 holds by finite differences with `noise_ratio` reported, not judged (REAL 0.0388, 0.0299).
- A real-reactor surrogate: none is promotable (M04 L43), so REAL's stage A is skipped.
- Cross-architecture bitwise identity; the end-to-end refinement (W25, M07); distribution of the TRF route before
  Frank's N1 answer on the `nlp` extra's licences.

## Open at this commit

Design-lane review notes N1 (stage-C restart eligibility) and S70's timing mask are not ruled; N2 is fixed (S74); N3
(REAL's coupling records compared under T08 v2's floors) and N4 (the FD check's cold points in `runs[].cold`) are
stated in the manifest.
