# ADR 0007 — Reproducibility and certificate policy: what this project promises reproduces, and what a certificate claims across a platform change

**Status:** Accepted (K04 default; **amended for `T08-numerical-policy-v2` records by ADR 0025, Amendment 1 below**; pre-allocated by plan §4.1 "Phase-0 ADRs": *0007 reproducibility and certificate policy*; decision register R-A07 and R-016). **F1 and F2 were answered by Frank Peters on 2026-09-22: the recommended default in both cases.** They are closed; the defaults stand as written and no file changed.  
**Date:** 2026-09-22  
**Author:** Fable 5.1 (Fable owns every ADR and the certificate and regularity policy, plan §1.3). Measurements by the Opus session on the registered CI pair and locally; judged here.  
**Affected requirements:** D20 (reproducibility — "structural hashes vs controlled numerical replay": this is the line between them), D14 (a certificate is model verification; this ADR fixes what it claims across machines), A08 (the regularity verdict's reproducibility class), D03 and ADR 0004 (the recorded linear evidence's class), blueprint §8.3 in full  
**Affected packages:** K03 (`tests/reproducibility.py` is the interim implementation of D2 and is replaced by it; K03's fixtures and `test_k03_schemas.py` compare under D2), K04 (the certificate carries `numerical_policy_id`, records near-threshold flags, and is judged by A32/A33 of the K04 specification), K05 (the `RunManifest` pins what D1 needs; replay reports what D4 says), T06 (scoring budgets, D5), every later package that records a float  
**Blueprint authority:** §8.3 (the four classes; "hashes exclude timestamps, job IDs, elapsed time"; "adaptive floating-point decisions are not included in a cross-platform bitwise promise"; "operation-count budgets support deterministic tests"; replay's three reports); §8.1 (the certificate is "a reproducible numerical verification report"); §6.4 (no quantization on the exact path); §13.4 ("report property calls only when their counting semantics align")  
**Companions:** ADR 0008 D2 (`state_sha256` covers exactly `x`; no test pins a digest; D2.5 reserves run and certificate identity to this ADR); ADR 0002 (canonical encoding, `ieee754-be-v1`); ADR 0004 D1 (explicit blocking parameters make the *same* environment reproduce — R1, not R2); `docs/derivations/K04-certificate-spec.md` (§7, §8, §13 A32–A33); `benchmarks/k04/reference_values.yaml` `numerical_policy` (the machine-readable form of D2)  
**Evidence judged:** the CI pair `ubuntu-latest` (x86-64) and `ubuntu-24.04-arm` (aarch64), same commit, same lock file (2026-09-21/22); two `ubuntu-latest` runners on the same tree two minutes apart (2026-09-21); thirteen one-ulp perturbations of the OFF-B start on one machine; six `PYTHONHASHSEED` values. All recorded in `tests/reproducibility.py`'s docstrings and `docs/progress.md` "Reproducibility"; restated in Context.

## Decision in one sentence

**The project promises bit-identity of structure (R0) on the registered platforms and agreement of every floating-point record within one declared numerical policy (R1 and R2, the same policy); it records bitwise agreement of floats when it observes it and never promises it, on any platform, including one machine; and a certificate's verdict is promised identical across platforms only where every thresholded quantity sits outside a registered margin of its threshold, which the certificate records.**

## Context

Blueprint §8.3 gives four classes and two phrases this ADR must make concrete: R1 and R2 both reproduce "within the declared numerical policy", and no document declares one; and R0 promises "identical structural artifacts", without saying which recorded artifacts are structural. Three measurements drew the line, each overturning a classification that had been confident:

1. **Two `ubuntu-latest` runners, same tree, two minutes apart:** one passed and one failed the byte-exact fixture comparison. The converged state differed in the last bits (`state_sha256` `13c05f70…` against `bb50df76…`; residual 1.11e-16 against 2.22e-16). A third runner on the same commit differed *differently*: identical solution, linear residual 8.10e-17 against 1.19e-16. Not hash-seed nondeterminism (six `PYTHONHASHSEED` values identical locally). So "same hardware class" is not "same last bit", and R1 cannot mean bitwise.
2. **x86-64 against aarch64, same commit and lock file:** every `state_sha256` *up the traversal* identical — every property evaluation, every flash iteration, the mixer's inner Newton reproduce bit for bit across instruction sets; the event sequence with kinds, attempts, iterations, signatures, outcomes and messages identical; the unscaled residuals identical; `residual_calls`, `jacobian_calls`, `factorizations` identical; every id, scale, bound, certificate and estimate in the plan identical. Different: the converged `state_sha256`, `merit`, `step_inf_scaled`, `u_diag_*`, `residual_normalized` — one to three ulps, and `residual_normalized` `1.11e-16` against exactly `0.0`. **The non-portability enters at the SuperLU factorization, not in the thermodynamics.**
3. **One ulp on the OFF-B start, thirteen times, one machine:** `property_calls` 476–612, `requested_evaluations` 1067–1385, `cache_hits` 591–776 (13 % spread) while outcome, attempts, iterations, restart and all 27 events are invariant; and nine perturbations give **six distinct** `nnz(L)` sequences, including the 103-against-104 aarch64 reported. Property counts are sums over hundreds of inner iterative solves each free to take one more step; `nnz(L)` is the pattern *after* partial pivoting, a magnitude comparison — "adaptive floating-point decisions" in §8.3's exact words.

A byte-exact comparison was therefore wrong twice: it fails across machines, and it pinned 39 digest values against ADR 0008 D2.1. A universal absolute floor was wrong once: no relative tolerance reconciles `1.11e-16` with `0.0`. The interim rule in `tests/reproducibility.py` — structure exact, floats at 1e-9 relative with the floor taken from the threshold each quantity already registers, digests checked for shape only, the six counts checked for kind only — is what the K03 gate runs today on both architectures. This ADR confirms it, closes its two admitted gaps (an invented `1e-24` fallback floor; classification by list rather than by rule), and says what the certificate and replay do with it.

## Decision

### D1. The reproducibility class of every recorded artifact

Classes are assigned by **rule**, not by enumeration; the enumerations below are the rule applied to the K03 and K04 field sets and are checked complete by K04 A32.

| Class | Rule | K03/K04 fields |
| --- | --- | --- |
| **R0 Structural** — bit-identical on every registered platform | a value determined by the canonical model, the structural policy and integer control flow, with no floating-point comparison on its path | every id and ordering; `model_version`, `constants_sha256`, `content_hash`; the `SolvePlan` entire (partition, eliminated rows with signs and `tolerance`, scales, bounds, `signature_units`, `initializer_chain`, `estimates.inner_dimension`, `estimates.jacobian_nnz` — the compiled pattern is declared, not thresholded); every `SolvePolicy` and check-policy value and hash; the event sequence with `kind`, `attempt`, `iteration`, `signature`, `trial_status`, `rejection_reason`, `outcome`, `message`; `alpha` (an exact power of two); `residual_calls`, `jacobian_calls`, `factorizations`; the attempt tree; the regularity `status`, the certificate `verification_status` and every `result` word — **conditionally**, D2.4 |
| **R1 / R2 Controlled and Equivalent numerical** — agree within D2 | a floating-point value on a path that includes a rounding, a factorization or an iterative inner solve | `residual_inf_unscaled`, `merit`, `step_inf_scaled`, `linear.residual_normalized`, `u_diag_min_abs`, `u_diag_max_abs`, `inner_consistency.eta`, `constant_mismatch`; every certificate `CheckResult.value`; `rcond_1`, `one_norm`, `inverse_one_norm_estimate`, `solution_error_bound_scaled`, the escalation's singular values |
| **Digests of R1/R2 quantities** — never compared for value | a hash whose preimage is in the row above | `state_sha256` on events and checkpoints, `full_state_sha256`, `jacobian_identity.state_sha256`, `target_state_sha256`. Compared for **shape** only (64 lowercase hex, or empty/null where the schema allows). ADR 0008 D2.1: no test may pin a digest value. A digest that moved without a float moving is still caught: the float is compared, and the encoding is `test_adr_0002_canonicalization.py`'s |
| **Recorded, not reproducible** — compared for kind only | an integer count that sums adaptive floating-point decisions | `property_calls`, `requested_evaluations`, `cache_hits`, `nnz_L`, `nnz_U`. Always recorded (ADR 0004 D3.1 requires the fill counts; blueprint §6.4 the cache counters); never asserted across runs; never a scoring instrument (D5) |
| **Excluded from identity** | §8.3's telemetry | timestamps, job ids, elapsed and wall time, hostnames; K05 keeps them out of every hash |

Two consequences of the rule. **`estimates.jacobian_nnz` is R0 within a revision and only within it**: at r = 0 the compiled pattern has 167 entries against 170 at r > 0 because the splitter rows' `r ·` coefficients fold to zero symbolically — a different revision, not a platform effect (*measured*). **The initial `state_sha256`** (the registered initializer through one traversal) was bit-identical across the two architectures; it is still a digest of an R2 quantity and is not promised.

### D2. The declared numerical policy — `K04-numerical-policy-v1`

**D2.1 The rule.** Two recorded floats `q`, `q'` at the same path agree iff

    |q − q'| ≤ max( 1e-9 · max(|q|, |q'|),  floor(path) ),

with `floor(path)` from D2.2. The relative part: the worst measured cross-architecture relative deviation on a quantity of ordinary magnitude is 2.2e-14 (`u_diag_min_abs`), five decades inside 1e-9; a deviation of 1e-9 relative on a converged quantity would mean a different solution, not a different last bit.

**D2.2 The floors are the registered thresholds.** Below the threshold its own quantity registers, a recorded float is not a measurement but the absence of one, and two absences agree. The floor of a path is therefore that threshold, and nothing else:

| Path | Floor | Registered where |
| --- | --- | --- |
| `residual_inf_unscaled` | `τ_kind` of the residual problem's rows (the K03 tear: 3.1e-8 mol/s) | ADR 0001 D6 |
| `merit` | `½ (τ/S)²` (the K03 tear: 5.34e-17) | K03 §5.1 with D6 |
| `step_inf_scaled` | `τ/S` of the problem's kind (1.03e-8) | the scaled tolerance |
| `linear.residual_normalized` | 1e-12 | ADR 0004 D3.2 |
| `inner_consistency.eta` | 1e-10 | K03 §3.4 |
| `constant_mismatch` | 1e-2 Pa | ADR 0001 D6, K03 §7.2 |
| `u_diag_min_abs` | `1e-10 × u_diag_max_abs` | ADR 0004 D3.4's screen ratio |
| `u_diag_max_abs` | 0 (relative only) | — |
| `rcond_1`, `one_norm`, `inverse_one_norm_estimate` | 1e-14 (`n ε` at n = 47) | K04 §7.2 |
| `solution_error_bound_scaled` (recorded evidence, not a check) | 1e-8 | K04 §7.4 |
| `inverse_one_norm_threshold` | exact (policy-derived constant `τ̂_min / (n ε)`) | K04 §7.4 |
| any certificate `CheckResult.value` | that check's own `tolerance` | K04 §5.1 |
| the escalation's singular values | `n ε σ_max` | K04 §7.2 |
| `kappa_2` (T02 `acceleration` events; null on a plain step) | 0 (relative only) — **compared only where the event's `residual_inf_unscaled / S ≥ 1e-4`**; recorded and shape-checked below | ADR 0009 D3 as amended 2026-09-24; T02 review M4 |
| `gamma_inf` (T02 `acceleration` events; null on a plain step) | 0 (relative only) — the same comparability window | ADR 0009 D3 as amended 2026-09-24; T02 review M4 |

**A comparability window is a scope, not a floor** (T02 review, 2026-09-24). A quantity computed from differences of residuals — the columns of an Anderson least squares — carries a cross-platform error of `O(ε ‖x̂‖ ‖Ĵ‖)` absolute whatever the residual's size, so its *relative* agreement degrades as `ε / ‖f̂_k‖∞`: measured on the CI pair, `≤ 3.3e-13` on every accelerated event with `‖f̂_k‖∞ ≥ 1e-4` and up to `1.06e-8` at `‖f̂_k‖∞ = 5.5e-8`. Below the window the quantity is not a measurement the relative rule can be promised on, and D2.4's principle applies: it is reported, not compared. The window is registered beside the path in `numerical_policy` with its provenance; the decisions such a quantity feeds stay R0 with D2.4's near-threshold margin asserted per platform. This is an addition under D2.3, not a reopening: D2.1's formula for every compared float is unchanged. The two rows first registered floors `1.0` and `1e-12` (T02 increment E2); both are withdrawn, and a `kappa_2` floor of `1.0` — on a quantity that is `≥ 1` by definition — was an absolute allowance of one, not a floor.

**D2.3 No unregistered float.** The interim rule's `1e-24` fallback is withdrawn. A float field of any schema must appear in the floor table, in D1's exact list, in D1's count list or in D1's digest list; K04 A32 enumerates the schemas' float fields and fails on one that is unclassified. A new recorded float is added to this table by the package that records it, with its threshold's provenance, in the same change — never discovered at comparison time.

**D2.4 Near-threshold flags, and when a verdict is promised.** A thresholded quantity `q` with threshold `τ` is **near threshold** when `q/τ ∈ [1/10, 10]` (for a lower threshold such as `rcond_1`, when `τ/q` is in that band). The certificate records `near_threshold = true` on that check and lists it under `limitations`. A verdict, a regularity status and a per-check `result` are promised identical across platforms (R0) **only when no quantity they depend on is near threshold**; otherwise the comparison *reports* the flag and a verdict change is a recorded observation, not a mismatch. At the registered SYN-001 states nothing is near threshold: residual floors sit ≥ 7 decades under their tolerances, `rcond_1 ≥ 1.3e-4` sits four decades over `τ_ill`, the solution-error bound four decades under (K04 A33). The margin of 10 is the smallest that makes a one-ulp effect (≤ 3 ulps measured) invisible by five decades and the largest that leaves a registered case with any margin to spare; a case that lands inside it is a case to re-register, not a rule to relax.

**D2.5 R1 and R2 share the policy.** The blueprint gives R1 a narrower environment; it does not give it a tighter policy, and the measurement forbids one: two runners of the same hardware class differed in the last bits. A tighter same-machine rule would be asserting what was measured false. What R1 adds is D6's pins, so that a difference *within* the policy on the same environment is attributable.

**D2.6 The policy is data.** The table above is `benchmarks/k04/reference_values.yaml` `numerical_policy`, emitted by the K04 generator; the comparison code (lifted from `tests/reproducibility.py` into `process_runtime` by K05) reads it from there. A policy change is a new `id`.

### D3. What a certificate claims across a platform change

1. A `SolutionCertificate` is a *reproducible numerical verification report* (blueprint §8.1) in this sense: its R0 fields — verdict, statuses, results, check ids, policy hashes, transformations, branch provenance — are promised identical on every registered platform subject to D2.4; its float fields are promised to agree within D2; its digests identify the state it certified and promise nothing.
2. A certificate **never claims bitwise reproduction** of any floating-point quantity, on any platform, including the one it was produced on. Where a rerun reproduces a float bit for bit, K05 reports it (`bitwise_floats: true`) as an observation.
3. A certificate carries `numerical_policy_id` and the platform identity K05 records (architecture, OS, Python, the lock-file hash, BLAS vendor, thread counts). It does not carry a promise about a platform outside the registered pair (plan §4.2: `ubuntu-latest` x86-64 and `ubuntu-24.04-arm`; Frank's choice of 2026-09-22; not open).
4. `target_state_sha256` and the K03 digests are identity, not evidence: two certificates with different digests may certify the same answer (D1), and a test that compares them for value is wrong by ADR 0008 D2.1.

### D4. What K05's replay reports

Blueprint §8.3 names three reports. They are the **mode** replay ran in, decided by comparing the recorded environment with the current one *before* anything runs; the **verdict** is separate:

| `replay_mode` | Chosen when | What is compared |
| --- | --- | --- |
| `exact_replay` | same lock-file hash, same platform identity, same thread pins | everything under D1: R0 exact, floats within D2, digests by shape, counts by kind; `bitwise_floats` recorded as observed |
| `compatible_reproduction` | same lock-file hash, a different *registered* platform | the same comparison; the mode name says the environment differs |
| `inspected_archived_results` | a dependency, lock or platform outside the registered set is missing or changed, or the rerun was not attempted | no rerun; the archived artifacts are validated for schema, hash integrity and D2.3 completeness only |

`replay_verdict ∈ {MATCH, MISMATCH, NOT_RUN}`: `MATCH` iff every R0 field is identical and every float agrees under D2; any R0 difference is `MISMATCH` whatever the floats do (a structural difference is a defect, never noise); a float outside D2 is `MISMATCH`; `NOT_RUN` for the inspected mode. A verdict-word change with a near-threshold flag present is reported as `MATCH` with `verdict_changed_near_threshold` listed — D2.4 — and is the one case where "match" and "same verdict" part company, by design and visibly. A dependency change therefore never produces a silent pass: it changes the mode to `inspected_archived_results` and the verdict to `NOT_RUN` (G05's "changed dependency fails exact replay").

### D5. Budgets and counters

1. The **property-call cap** stays as registered (`max_property_calls`, 10 000; 20 in `SYN-001-capped-budget`): it is a hard cap enforced at the provider boundary, deterministic by construction, and K03 A15's exact count on exhaustion is correct — a cap that refuses the 21st call reads 20 on every machine.
2. It is **not a reproducibility-graded quantity and not a scoring instrument.** A budget of 500 on a solve whose honest range is 476–612 decides close to arbitrarily (brief §4.3, measured), and blueprint §13.4 already says property calls are within-platform diagnostics unless their counting semantics align — across a one-ulp perturbation they do not align with themselves.
3. The **deterministic budget** for tests and for T06's scoring is the solver counters: `residual_calls` (traversals), `jacobian_calls`, `factorizations`, `newton_iterations`, `attempts` — invariant under the thirteen perturbations and across architectures. Blueprint §8.3's "operation-count budgets support deterministic tests" is read as applying to these and not to counts of adaptive inner work; that is a narrowing of which counts qualify, not a change to the blueprint.
4. Making a solver counter the *registered* budget of the fixture registry requires a `SolvePolicy` field (`max_residual_calls`) — a migration of a K03 schema — and a change to `benchmarks/registry.yaml`'s `budgets`. **Deferred to T06 by default; FOR FRANK F2.**

### D6. Environment pins that make a within-policy difference attributable (K05)

The `RunManifest` records: architecture, OS, Python version, the lock-file hash, the BLAS/LAPACK vendor and version as SciPy reports them, `OPENBLAS_NUM_THREADS`/`OMP_NUM_THREADS`/`MKL_NUM_THREADS` as set, and the SuperLU options by reference to ADR 0004 D1. CI pins every thread variable to 1. A differing thread count is a differing environment: replay in that case is `compatible_reproduction` at best, never `exact_replay`. This ADR does not decide that single-threaded is a product requirement; it decides that the count is recorded and that a change of it changes the mode.

## Alternatives considered

- **Byte-exact document comparison.** Rejected: fails across machines and within a hardware class (Context 1–2), and pinned 39 digests against ADR 0008 D2.1.
- **One universal absolute floor** under the relative tolerance. Rejected: `1.11e-16` against `0.0` (Context 2) is reconciled by no relative tolerance and by an absolute floor only if the floor is a registered threshold; an invented floor is a tolerance without a floor argument.
- **A tighter policy for R1 than for R2.** Rejected: measured false on two same-class runners (D2.5).
- **Promising bitwise reproduction on a pinned single-threaded machine.** Held FOR FRANK (F1); the recommended default rejects it because it would be measured, might fail on a BLAS update, and adds nothing a certificate needs.
- **Treating `nnz(L)`, `nnz(U)` as structural** because they count a pattern. Rejected: six sequences from nine one-ulp perturbations (Context 3); the pattern is post-pivoting.
- **A quantized hash** so that digests reproduce. Rejected by blueprint §6.4 and ADR 0008 D2.6 before it was proposed.
- **Comparing verdicts unconditionally as R0.** Rejected: a quantity at `0.9 τ` on one machine and `1.1 τ` on another is a real possibility with a real last-bit cause; D2.4 makes it visible instead of either hiding it (a float floor at `τ` would call the values equal) or failing on it (a verdict mismatch that nobody can fix).
- **Budgeting on `requested_evaluations`** instead of `property_calls`. Rejected: it moves too (1067–1385).

## Consequences

- `tests/reproducibility.py` is D2's implementation as of this date; its `RELATIVE_TOLERANCE`, `REGISTERED_FLOOR`, `DIGEST_FIELDS` and `UNREPRODUCIBLE_COUNTS` are D2.1, D2.2, D1 row 3 and D1 row 4; `ABSOLUTE_FLOOR` is withdrawn by D2.3 and the module reads the table from `benchmarks/k04/reference_values.yaml` when K04 lands (D2.6). K05 lifts it into `process_runtime` for replay.
- K04's certificate carries `numerical_policy_id`, `near_threshold` flags and the platform identity; K04 A32 and A33 are the executable form of D2.3 and D2.4.
- K05's `RunManifest` carries D6's pins and D1's classification per field; replay reports D4's mode and verdict.
- K03's manifest limitation "every measurement here is from one platform" is discharged for the R0 fields by the CI pair and stays for nothing else (there is no bitwise promise to discharge).
- T06 scores on D5.3's counters and carries F2's migration if Frank confirms the default.

## Acceptance evidence

- **D1/D2 executable:** K04 A31 (round trip under D2), A32 (every float classified), A33 (no registered state near threshold; a constructed one flagged); the existing `test_k03_schemas.py` contract continues to fail on a changed scale, a renamed row, a different elimination, a lost event, a changed solver counter and a changed outcome (brief §7), and continues to pass on both architectures.
- **D3:** the K04 certificate fixture emitted on both CI architectures compares `MATCH` under D2 with identical verdict and statuses (K05 records the comparison; K04 records that both architectures ran the gate).
- **D4:** K05's G05 evidence — a changed lock hash yields `inspected_archived_results`/`NOT_RUN`; the two-platform pair yields `compatible_reproduction`/`MATCH`; the same runner yields `exact_replay` with `bitwise_floats` recorded as observed.
- **D5:** K03 A15 unchanged; the K04 manifest records the thirteen-perturbation spread as the reason `property_calls` is not compared.
- **This ADR's own status:** `implemented` when `tests/reproducibility.py` reads D2 from the reference file and A32 exists; `tested` when A31–A33 pass on both architectures; `reviewed` requires the human sign-off recorded separately and is not set here.

## What this ADR does not establish

- **Bit reproducibility of any float anywhere** (D3.2). It establishes that the project does not claim it.
- **Behaviour on a platform outside the registered pair.** A third platform is out of scope by the brief and by Frank's choice; R2 is defined over the registered set.
- **That the CI pair exercises different BLAS vendors** (plan §4.2 K05 prefers it). Whether `ubuntu-latest` and `ubuntu-24.04-arm` wheels ship different OpenBLAS builds is K05's to record in D6's fields; nothing here assumes it.
- **A scoring policy.** D5 names the deterministic counters; T06 registers the budgets and the campaigns.
- **Replay bundle mechanics** (K05) or the `RunManifest` field set beyond D6's pins.

## Open questions with recommended defaults

### FOR FRANK — all closed 2026-09-22


**F4 and F5 answered by Frank Peters, 2026-09-22: the recommended default in both cases.**
F4 — an unset thread variable is *unknown*, and unknown is never `exact_replay`: an unpinned
machine now gets `compatible_reproduction` with the reason named, and a developer wanting an
exact replay pins the three variables as CI does. F5 — K05 stands `tested` with the
clean-container replay recorded `unsupported`, and that replay becomes a named acceptance item
of K06 or T08; the condition attached to the recommendation, that M3 be fixed first, was met
before the ruling was applied. No file changed as a result of the rulings themselves; F4's
implementation is `Environment.threads_known` and `decide_mode`.



**All three answered by Frank Peters, 2026-09-22: the recommended default in every case.**
F1 — the project reports bitwise agreement and never promises it, on any platform including a
single machine; R0 bit-identity of structure plus D2 agreement for floats is the promise.
F2 — the property-call cap stays the registered budget for v0.0, its classification is
recorded, and `max_residual_calls` arrives by migration at T06 with the first scoring campaign.
F3 — `VERIFIED` certifies residual accuracy at the registered tolerances; the solution-error
bound is recorded and disclosed and is not promised; the absolute-conditioning limit is the
guard. **No file changes as a result of the rulings themselves** — each records an answer
rather than altering a decision, exactly as ADR 0006's Q1 and Q2 were recorded. F3 in
particular is *not* a scientific-requirement change: it declines one. Should a later package
need solution tolerances, that is a new ADR beside blueprint §8.1's acceptance rule, and this
answer is the reason it would need one.


**F1 — The public promise about floating-point reproduction.** D3.2 says the project reports bitwise agreement and never promises it, on any platform including one machine, and promises only R0 bit-identity plus D2 agreement. That is the sentence the README and the release notes will carry, and it is a product promise, not a technical fact. *Recommended default:* D3 as written. *Alternative:* promise bitwise reproduction on a pinned single-threaded environment and add it to the gate — measurable, and liable to fail on the first BLAS update.

**F2 — The registered budget instrument.** D5.4: keep the property-call cap as the registered budget for v0.0 and migrate to `max_residual_calls` at T06 when the first scoring campaign is registered; or migrate now, in K04's window, before any replay bundle stores a policy hash. Changing a preregistered fixture budget is not retroactive today because nothing has been scored (blueprint §13.4), but it is a change to a registered value. *Recommended default:* defer to T06.

### Needs a fact or a preference

| ID | Question | Label | Recommended default |
| --- | --- | --- | --- |
| Q1 | Should D2.4's margin be 10 or a per-quantity margin from its measured spread (3 ulps on values, a factor ~1.3 on `property_calls`, which is not compared)? | needs a fact — a registered case that lands inside the band | 10 for every thresholded quantity; re-argue with the first case that needs it. |
| Q2 | Should CI additionally run one job with threads unpinned, to measure whether thread count moves anything on this problem size? | needs the user's preference (CI cost) | No for v0.0; K05 records the pins, T06's campaigns are where it would matter. |
| Q3 | When a float field is added to a schema, should the ledger test fail until D2.2's table has its floor, or should the schema test? | needs the user's preference | The schema test (K04 A32): it fails in the change that adds the field, not in a later ledger sweep. |

## Amendment 1 (2026-10-02, ADR 0025, Proposed) — `T08-numerical-policy-v2`

ADR 0025 is the new ADR that *Changing this ADR* requires. For records made under `T08-numerical-policy-v2`, D1 and D2.2 are applied as ADR 0025 §5 tabulates them. `K04-numerical-policy-v1` and every result recorded under it are unchanged. The changes:

- **D1, row 3, by construction.** `level_constants_sha256` (already classed so by ADR 0010 D7.2) is a float digest, compared for shape. So is a digest-form `certificate_id`, which is checked for self-consistency.
- **D1, row 4.** `u_diag_min_abs`, `u_diag_max_abs` and the certificate's `u_diagonal_ratio` join `nnz_L` and `nnz_U` as "recorded, not reproducible". They are functions of the same partial-pivoting sequence that Context 3 measured changing under one-ulp perturbations.
- **D1, the `message` entry.** Read under D1's rule rather than its enumeration: a `message` or `cause` is an exact template plus float tokens compared under D2.1.
- **D2.2, new floor rows.** Certificate `limitations[].value` (kind `near_threshold`) is floored at its `threshold`. A solution-state variable is floored at its declared kind's `τ_kind` (ADR 0001 D6). Phase-branch flows are floored at 3.1e-8 mol/s.
- **D2.1's premise.** The 2.2e-14 relative measured on `u_diag_min_abs` is withdrawn as the premise: it was a sample at states whose pivot sequences coincided. The relative 1e-9 stands, on Context 2's 1–3 ulps, on ADR 0009 D3's ≤ 3.3e-13, and on the noise model ε·κ̂ ≤ 3.5e-12 at the T08 RC set.
- **D4.** A bundle recorded under a numerical policy other than the build's own is compared under the policy it records (*corrected 2026-10-02*: Frank's answer to ADR 0025 Q4, R-147, replaced the refusal first written here); only a policy id the build does not know gives `inspected_archived_results` / `NOT_RUN`. A record is never reinterpreted under another policy.

D2.4, D2.5, D3, D5 and D6 are unchanged.

## Changing this ADR

D1's rule and D2's policy bind every package that records or compares a float. A new class, a different relative tolerance, a floor that is not a registered threshold, a bitwise promise, or a change to what replay reports requires a new ADR stating the reason, the measurement that justifies it, and the affected requirements, and a decision-register entry. Adding a float to D2.2's table with its threshold's provenance is an ordinary change made by the package that records it (D2.3) and does not reopen this ADR.
