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

## Where WO-S10-2b stopped

Complete: review findings 2 and 3 fixed, finding 1 recorded by E-2 with its outcome test; the stop rule is S10-C's.
B-16…B-18 are test-design choices for the next ruling round.
