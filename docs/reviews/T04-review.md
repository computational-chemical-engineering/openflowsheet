# T04 review — the specification continuation, recovery edge 3, the residence-time PTC family and K04 on the bound declaration, against `docs/derivations/T04-globalization-spec.md` and ADR 0010

**Reviewer:** design lane, `reviewer` (Claude Opus 5.5), 2026-09-24. Plan §1.3: the design lane
reviews every build-lane package that touches residuals, derivatives, phase logic, scaling,
certificates or replay identity; this one touches all six.
**Brief:** `docs/briefs/T04-implementation-review.md`.
**Reviewed at:** `wp/T04` = `ecc88d5`; build-lane commits `4ad432f..26aeb0c` (the specification and
design commits in that range are the design lane's and were read, not reviewed). Run here: the full
gate, **1892 passed** (78 s; ruff, format and mypy clean); the T04 suite alone, 265 passed in 40.2 s,
of which `test_a11_the_family_scan` is **19.1 s**; the committed reference's SHA-256 **`146406e6…`**,
equal to the specification's header; `t04_reference.py --check`, **149 checks passed**. The evidence
manifest and the T04 identity script (W11) were being written concurrently and were not reviewed.
**Environment:** x86-64 Linux 6.12.86, the repository's `.venv`. No CI artefact was examined.
**Measured:** every finding marked *measured* comes from a probe run against `ecc88d5` in this
session, built from the tests' own helpers (`test_t04_edge3`, `test_t04_ptc_region`,
`test_t04_certificate`, `benchmarks/t04/basin.py`); each probe (P1–P6) is described where it is used
so that it can be re-run. Nothing is marked measured that was only read.
**Amendments made in this commit:** none. The specification, ADR 0010 and the register are left to
the `specifier`; the amendments this review recommends are listed in §7.

---

## 1. Verdict

**The globalization is implemented as specified, and the registered trajectories are the twin's.**
The homotopy (`orchestrator/homotopy.py`) is a clean, generic controller: λ is an exact `Fraction`
everywhere, `p(λ)` is formed in exact rationals and rounded once, λ = 1 is the target instance and is
never re-bound, a rejection rolls back to the last accepted corrector result and never keeps a
corrector's end state, and the stall's hypothesis comes from §4.6's table. Edge 3
(`executor._eo_recovery`, `recovery.py`) checks §5.2's preconditions in order, fires at most once by
construction (it is never called on its own recovery), opens from the failed item 0's in-memory
opening, and continues the provenance densely. The PTC core (`numerics/ptc.py`) follows §7.3–§7.5
line by line: the stop test before anything and before any SER update; SER on accepted iterates only,
with Δτ_used; one trial at K03 §5.3's `α_max` through Newton's own bound functions; retries ended by
`retries_max` or τ_min; the reset per attempt; the polish's four-way acceptance. The contract hooks
are the two frozensets and one budget set of ADR 0010 D6 and nothing else. The ablation tests have
teeth (Δτ_used, rejected residuals, reset, γ clip, σ sign each move a registered count), the
bit-identity tests are bit-identity tests (A02's hex comparison, A18's `array_equal`), and the four
xfail retirements assert exactly the amended bounds (§5.3). The mapping validator runs V1→V4 in the
ruled order and refuses silence.

**It is not done.** One thing is wrong where the tests do not look:

1. **A Jacobian evaluation that fails is a zero matrix on the region path, and the PTC core turns it
   into a globalization failure, a false `CONVERGED`, or a crash** (M1). `_region_problem.jacobian`
   ignores the compiled Jacobian's `status`. *Measured:*
   - At the polish (OFF-B, r = 0.95) it gives `rejected:linear_solve_failed` and `CONVERGED` at the
     unpolished stop, where the design lane's ruling F15(h) says `EVALUATION_ERROR`. K04 then returns
     **`FAILED`, `false_success_detected = true`** on `material_balance.envelope.C` — the certificate
     the polish exists to prevent (R-033).
   - At a pseudo-step on the nominal region it gives eleven `linear_solve_failed` retries and
     `PTC_STALLED` — an edge-3 trigger, where §5.1 says an evaluation defect is not one.
   - At a pseudo-step on the A02 region it **kills the interpreter**: `M̂/Δτ` alone has structural
     rank 8 of 42, and SuperLU under ADR 0004's `relax = 1` segfaults on it (S5).

   The brief hands this on as "a Jacobian that raises … is uncaught (as in Newton)". That premise is
   false: on the region path nothing raises.

The should-fix items are all on paths no registered case reaches, or they are verification gaps:

- The identity guard takes the caller's `solve_plan=` as the result's identity, so
  `declaration_unidentified` can be bypassed with one argument (S1, measured).
- `verify_bound`'s `revision` is not tied to its `binding`. A mismatched pair produces a false
  `FAILED` with `false_success_detected = true` on a correct root (S2, measured).
- A21 is tested on the four named runs only, not on "every registered SYN-001 PTC run". The identity
  holds on the 18 basin runs with a 32× margin (S3, measured).
- A11's second half — the attempts and counts of the 170 runs that converge — is asserted by the
  specification and registered nowhere (S4).
- `solve_linear` segfaults, under the registered SuperLU options, on a structurally singular matrix
  it could refuse in O(nnz) (S5, measured). M1 is its only known route in.

**The brief's §5 questions are ruled in §5.** Decisions 1, 2, 5, 13 and 15 are sound. Decision 14 is
amended by S1 and S2. Q2: yes, with four conditions. Q3: keep the scan in the gate.

**Not examined:** the evidence manifest script and the T04 identity script (both in progress);
`t04_reference.py` beyond its `--check` exit and the committed SHA; the registry prose, the two new
revision documents beyond `test_t04_registry`'s own checks, schema JSON layout beyond the new
fields' patterns, fixture regeneration; the CI pair (A26's cross-platform half is therefore
unreviewed — Q2 states what it must show); the build lane's "path identity" dump of 100 runs (the
claim is recorded, not re-measured); the Anderson core; K05 replay beyond the one note N4.

---

## 2. Must-fix

### M1 — A failed region Jacobian is a zero matrix; the PTC core turns it into `PTC_STALLED` (an edge-3 trigger), into `CONVERGED` at an unpolished stop, or into a segfault

**Where.** `src/process_runtime/orchestrator/region.py:387-393` builds the region's Jacobian from
`compiled.jacobian(...)`'s `data/indices/indptr` without reading `result.status`. The casadi backend
returns a failed evaluation as `status = "error"` or `"invalid_trial_state"` with empty data and an
all-zero `indptr` (`compile/casadi_backend.py:507-519`), so the region core receives a structurally
valid **zero** matrix. `numerics/ptc.py:360` (a pseudo-step) and `numerics/ptc.py:662` (the polish)
factor it, the pseudo-step as `M̂/Δτ` alone. The Newton core does the same at
`numerics/newton.py:301`.

**Measured (P1).** A compiled-problem wrapper returns `status = "error"` for chosen Jacobian calls,
exactly as the backend does when a block raises, and is passed as `solve(..., compiled=…)` from
`test_t04_ptc_region`:

```
r = 0.95 initializer, clean:        CONVERGED [39], 40 Jacobian calls, polish accepted
J1  the polish's Jacobian (call 40): CONVERGED, polish rejected:linear_solve_failed
J2  pseudo-step 4's Jacobian:        PTC_STALLED at 4 — 11 × linear_solve_failed;
                                     eo_recovery_due(PTC_STALLED) = True
J3  OFF-B, the polish's Jacobian:    CONVERGED [(PHASE_UPDATE_REQUIRED, 4), (CONVERGED, 26)],
                                     polish rejected:linear_solve_failed
    verify(flowsheet, result):       FAILED, false_success_detected = True,
                                     failing {material_balance.envelope.C}
```

**Measured (P1b), end to end through the plan executor.** `SYN-001-A02-360` under `eo_core = ptc`
(clean: `CONVERGED`), with `executor.compile_problem` wrapped so that every Jacobian after the
second fails. The third factorization is pseudo-step 2's `M̂/Δτ` over a zero Jacobian: 42 × 42, 29
nonzeros, 25 empty columns, 34 empty rows, structural rank 8. **The process dies with SIGSEGV** in
`splu` (`linear.py:127` ← `ptc.py:395`). The dumped matrix reproduces the crash in isolation (S5).
So the edge-3 misrouting that J2 shows on the nominal region is not even reached on the region
edge 3 serves.

**Why it is must-fix.** §7.5 as ruled (F15 h) is explicit: "an evaluation of the polish returns
`error` (the Jacobian or residual at `x_c`, or the trial) … ends the attempt `EVALUATION_ERROR`". The
Jacobian half of that sentence is not implemented. There are three consequences:

- **At the polish:** the one failure the polish was registered to prevent — a `CONVERGED` solve
  whose certificate is `FAILED` with `false_success_detected`.
- **At a pseudo-step:** either a crash (A02 region) or an evaluation defect turned into the PTC
  core's failure-to-advance (nominal region). §5.1 makes that outcome an edge-3 trigger, and §5.1's
  own exclusion list says a defect is not one.
- **`CLAUDE.md`'s rule:** "No placeholder success paths".

The brief hands the polish case on, but on a false premise: nothing raises, the failure is absorbed
silently.

**Reachability, measured (P4).** On SYN-001's provider a property-budget refusal does not land in
the Jacobian. In the r = 0.95 plan run under PTC the cap was placed at six points: midway between
accepted pseudo-steps 10/11, 20/21 and 30/31, and at exactly, one past and two past step 10's call
count. Every refusal arrived in a residual or in the mass matrix, and the core ended
`EVALUATION_ERROR` with no `linear_solve_failed` rejection. The inference is that the compiled
Jacobian makes no metered provider call at an already evaluated state. M1 is therefore reachable
only by a derivative that fails where the value did not. No registered path does that; T05's
providers and any opaque evaluator can.

**Correction.**
1. `_region_problem.jacobian` refuses a non-`ok` result by raising a typed
   `JacobianUnavailableError(status, message)`, defined beside `MassUnavailableError`.
2. `solve_ptc` catches it at the pseudo-step (`ptc.py:360`): `EVALUATION_ERROR`, exactly as
   `MassUnavailableError` is handled on the next lines.
3. `_polish` catches it (`ptc.py:662`): `EVALUATION_ERROR` with `x_c` kept, the `stopped` pair
   recorded, and a `trial` event `polish(rejected:error)`, so that the record has one shape for
   both of F15(h)'s cases.
4. **The Newton half is the same line.** Leaving `newton.py:301` alone after step 1 would crash the
   Newton region path on the same input. `solve_newton` catches the error too and ends
   `EVALUATION_ERROR` (K03 §5.5).
5. This changes no registered path: no registered Jacobian evaluation fails. Prove it by the
   build lane's 100-run hex dump before and after, as for the PTC integration.

For a non-`error`, non-`ok` status (`invalid_trial_state`) at an *accepted* iterate, whose residual
evaluated `ok`, use the same `EVALUATION_ERROR` (a derivative defect). The specification says
nothing finer, and §7 amendment 1 asks the specifier to say it.

**Tests that catch it.** P1 and P1b as tests:
- J1 → `EVALUATION_ERROR` with `polish == "rejected:error"`.
- J2 → `EVALUATION_ERROR` at pseudo-step 4 with no `linear_solve_failed` rejection.
- J3 → no `CONVERGED` result exists to certify.
- P1b → `EVALUATION_ERROR` with `eo_recovery is None`. Run it in a subprocess until S5 lands, so
  that a regression fails the test instead of killing pytest.
- A Newton twin of J2: the region Newton core with one failing Jacobian → `EVALUATION_ERROR`.

---

## 3. Should-fix

### S1 — The identity guard accepts the caller's `solve_plan=` as the result's identity

`src/process_runtime/verify/certificate.py:375-377` builds the identity sources as `[result's plan,
caller's solve_plan]` and refuses `declaration_unidentified` only when the fingerprint and both of
those are absent. With `solve_plan=` passed, a result that carries neither a fingerprint nor a plan
is judged. Because the state hash is compared only when a fingerprint exists (`:394`), its state is
taken unchecked. *Measured (P2)*, on `SYN-001-A02-360`'s binding and document:

- G1a: a `SimpleNamespace(outcome="CONVERGED", state=…)` → refused `declaration_unidentified`. This
  is A31(iv) as tested.
- G1b: the same object with `solve_plan=` the region plan → a **`VERIFIED` certificate**.
- G1c: the same with `S3.T` moved by 0.5 K → a certificate **`FAILED`, `false_success_detected =
  true`** on eleven checks, about an object that is not a solve result.

§4.8 item 1 says the identity is read "from the result's `root_fingerprint` … and from its
`SolvePlan`". The caller's plan is §4.2's alias comparison input, not the result's identity. Every
real `CONVERGED` result carries a fingerprint (tear, region and merge paths, read), so this is
latent. Still, A31(iv) is registered as a refusal, and a registered refusal should not depend on
which keyword the caller used.

*Correction:* refuse `declaration_unidentified` unless the result itself (the fingerprint, or
`getattr(source, "plan")`) identifies the declaration. Then compare the caller's `solve_plan` as an
additional claim, as now.

*Test:* A31(iv) repeated with `solve_plan=` (G1b) raises `declaration_unidentified`.

### S2 — `verify_bound`'s revision document is not tied to its binding

`verify_bound(binding, revision, result)` (`certificate.py:452`) reads every specification value and
`r` from `revision` (`_revision_values`, `:567`) and the declaration from `binding`, and nothing
checks that the binding was built from that revision. *Measured (P2, G2):* A02-360's binding, A02-365's
document and A02-360's own converged result → **`FAILED`, `false_success_detected = true`**, failing
`specification.U-FLASH.Q`. That is a false alarm on a correct root: the defect class §4.8 was written
to close ("neither result says anything about the problem that was solved"). The same pairing with
A02-360's own document gives `VERIFIED` (G2′). A mismatched pair can only produce a false `FAILED`,
never a false `VERIFIED`, because the residual checks use the binding's parameters. That is why this
is S and not M.

*Correction (minimal):* record on `Binding` the canonical SHA-256 of the revision document it was
bound from, and refuse in `verify_bound` when the document handed in differs. Alternatively drop the
`binding` argument and bind inside `verify_bound`, so the two cannot disagree. The refusal is a new
`VerifierError` message (`declaration_mismatch(revision)` is the natural form). §4.8 item 1 lists
the grammar, so the `specifier` adds it (§7 amendment 3).

*Test:* G2 raises.

### S3 — A21 is tested on four of the registered SYN-001 PTC runs

A21: "on every accepted pseudo-step of every registered SYN-001 PTC run". `tests/test_t04_ptc_region.py:711`
parametrizes over `NAMED_RUNS` (four runs). The 18 admitted basin starts under PTC (A23) and PHS-05
under PTC (A24) are registered PTC runs too, and they are not checked. *Measured (P3):* `identity_defects`
over the 18 basin PTC runs covers **3 954 row-steps; worst defect / A21 bound = 3.09e-2**. The
identity holds, so this is a narrowed test, not a defect. *Correction:* extend the A21 test to the
basin comparison's PTC runs (`BasinComparison.admitted[*].runs["ptc"].result`, already computed by
`test_t04_basin`'s fixture) and to PTC-P5.

### S4 — A11's "attempts and counts" half is registered nowhere, so it is not tested

A11: "every other run's outcome, attempts and counts equal T03's block twin (`t03` family scan where
it overlaps)". `benchmarks/t04/reference_values.yaml` `policy_simulation.a02_family_scan` carries
only `targets_K`, `guesses_K`, `runs` and `contract_failures`. T03's `family_scan` carries only
failure lists. `test_a11_the_family_scan` (`tests/test_t04_edge3.py:604`) therefore asserts only
`CONVERGED` with no recovery for the 170 other runs. A regression that changed the contract's
attempt signatures or Newton counts on any of them would pass. §9.3 states the twins agree "on all
180 runs — outcomes, attempts, counts", so the generator has the numbers.

*Correction:* this one is owned by the design lane. Either emit per-run `(outcome, attempt
signatures, attempt iterations)` for the 170 runs in `a02_family_scan` and re-emit the reference
(a SHA change in the specification's header), or strike "attempts and counts" from A11. The build
lane then asserts what is registered. Until one of the two happens, the manifest's A11 entry should
say it checks outcomes only.

### S5 — `solve_linear` can kill the process on a structurally singular matrix

`src/process_runtime/numerics/linear.py:127` calls `splu` under ADR 0004's `SUPERLU_OPTIONS`, and
catches `RuntimeError` as `exactly_singular`. *Measured (P1c):* on the 42 × 42, 29-nonzero matrix of
P1b, whose structural rank is 8, `splu` **segfaults** (SciPy 1.15.3; every one of five runs, in
process and in fresh subprocesses). The same matrix under SuperLU's defaults raises `RuntimeError`. Removing the one
option `relax = 1` also gives `RuntimeError`; removing `panel_size`, `diag_pivot_thresh`,
`permc_spec` or `options` does not. With unit values on the same pattern it raises too, so pivoting
takes part. An all-zero 42 × 42 matrix and an 8 × 8 identity block embedded in 42 × 42 both raise
cleanly.

The only known route in is M1's zero Jacobian: every regular region Jacobian is structurally
nonsingular by T02's analysis, and so is `M̂/Δτ + Ĵ_σ` on top of it. A solver must still never take
its host down. Changing `relax` is an ADR 0004 matter, because it may move last bits.

*Correction:* refuse before factorizing. If `scipy.sparse.csgraph.structural_rank(csc) < n`, raise
`LinearSolveFailedError("exactly_singular", "structurally singular: rank r of n")`. The check is
O(nnz·√n), and on every structurally nonsingular matrix the factorization path is unchanged, so it
is bit-inert on every registered path. Record it in ADR 0004's notes. The design lane decides
separately whether `relax = 1` should stay.

*Test:* regenerate P1b's matrix (pseudo-step 2 of `SYN-001-A02-360` under PTC with a zero Jacobian)
→ `LinearSolveFailedError`, run in a subprocess.

---

## 4. Notes (no change required, or a wording amendment recommended in §7)

- **N1 — Decision 1: a homotopy item's `iterations` counts every corrector.** *Measured (P6):*
  HOM-03's item has `iterations = 30`. The four accepted correctors ran 4 of them; the 17 λ-trials
  (13 rejected) ran 30. This is a count of Newton work done, consistent with the `attempt_closed`
  event and with §5.3's cost estimate. The accepted λ-path is already on `continuation.lambda_levels`
  and `rejected_trials`. Sound (§5.1). Because it is an R0 count, §4.7 should say it (§7
  amendment 2).
- **N2 — Decision 5 at its edge.** When the recovery's easy endpoint fails, the recovery reports
  `state = x⁰` (the opening; `homotopy.py:closed(at=None)`), while the step's checkpoint is the
  failed solve's last accepted iterate (`executor.py:563`), a different state. Both are right: the
  state is where the recovery ended, the checkpoint the step's last accepted iterate. A bundle
  consumer must read the checkpoint, not the state. Unreachable on every registered case (the easy
  endpoint converges at iteration 0 on all of them, `test_the_opening_is_a_root_of_the_easy_endpoint_on_every_case`).
  Decision 2's path (a stall with `lambda_reached = 0`, checkpoint `"0"`) has no test. It is cheap
  with a stub corrector on `continue_specification`: a corrector that converges only at λ = 0 gives
  nine rejections (1/4 … 1/1024) and a `"0"`/`partial` checkpoint.
- **N3 — Edge 3 after edge 2, when it becomes supported.** Today it is always `unsupported` (a
  merged recycle region has no promoted row; tested). If a later package supports it,
  `_eo_recovery` would open from the *region's* attempt-0 opening (the merge's best iterate) but
  take `initializer_source` from the dense list's item 0, the loop's Anderson attempt, and
  `recovered_provenance` would accept that. "Item 0" has two meanings there, and §5.3 must choose
  one before the path is enabled.
- **N4 — A01's replay clause is carried by the schema alone.** `run/replay.py` never validates a
  recorded policy against `solve-policy.schema.json`. "A replay under a policy without
  `globalization` is refused before anything runs" therefore holds only for a caller that validates
  first; `test_a01_a_policy_without_globalization_is_refused` tests the schema. This is the T03
  review's unprobed ADR 0005 C2 gap, in the same shape. Hand both to K05.
- **N5 — Private imports across the numerics layer.** `ptc.py` imports `_bound_aware_alpha`,
  `_scale_matrix` and `_trial_point` from `newton.py`. Sharing them is right (§7.3: "the same two
  functions Newton calls, not a copy"), but they are now a shared K03 §5.3 layer. Make them public
  in `newton.py`, or move them to a small `numerics/bounds.py`.
- **N6 — Performance.** Nothing matters at 42 × 42.
  - Recompiling per λ-level (6 ms, W0.1) is right here. At plant size, re-bind instead (ADR 0008
    D4.1; §15 Q3's own rule is "< 1 s").
  - `verify()` compiles the declaration twice (`_guard`, then `Syn001TearProblem`).
  - `_eo_recovery` compiles the full declaration again for its structural pattern
    (`executor.py:521`).
  - The PTC core's retries refactor `J + M/Δτ` from scratch, as §7.3 says. A factorization reuse
    across retries is not available for a shifted matrix without an eigen-decomposition, and is
    not worth it.
- **N7 — Floats in R0 strings, inherited.** A PTC or corrector `EVALUATION_ERROR` carries the
  provider's or the backend's message (for example `H_S3_vapor: temperature 219.87… K outside …`)
  into `solve_closed.message` and a terminal item's `cause`, as Newton's already does. T04 adds no
  new float-bearing grammar; its own strings (`homotopy_stalled(…)`, `ptc_mapping_invalid(…)`,
  `polish(…)`, the PTC stall message) are float-free (read). The inherited class belongs with T03
  review S4 in ADR 0007.
- **N8 — `continuation_lambda`'s pattern admits λ > 1** (`"5/4"`, `"2"`) and non-reduced
  fractions. The controller cannot form one, and the `if/then` still forces `partial`. Tighten when
  the schema is next touched.
- **N9 — Decision 15, measured (P5).** At HOM-01's recovered state the guard's
  `state_sha256(state_vector(spec, x), ids)` equals the compiled residual's `state_sha256` and the
  fingerprint's `full_state_sha256`. §4.8's wording ("`residual(x_final).state_sha256`") and the
  implementation (no residual call, which A31(i)'s zero-call spy requires) describe the same hash.
  Add P5 as a one-line test, so the equivalence is pinned rather than coincidental.
- **N10 — The cause helper keeps F11's normalization.** `tests/test_t04_ptc_region.py:736-745`
  (`same_cause`) still accepts a wall cause truncated to its trigger and accepts `""` for a terminal
  item. F11 says the normalization was removed. It is dead today, because the reference carries the
  full grammar and A24 adds the strict terminal comparison. Remove it, so that a future reference
  abbreviation fails rather than passes.
- **N11 — Handed on by the brief, confirmed.**
  - PHS-05's base revision (`benchmarks/syn001/cases/SYN-001-A02-355-dew-guess.yaml:400`) gives
    the 355 K duty's provenance as the `T_heater=360K` sweep row. The value (24 681.106 068 625 242
    W) is HOM-01's registered `Q_spec`; only the citation is wrong. Fix it at the next touch.
  - F9 goes to K04 (§17 F9, Q8).

---

## 5. Rulings

### 5.1 Brief §5

- **Q1 — Decisions 1, 2, 5 and 13–15.**
  - **1 (iterations = every corrector's, accepted and rejected): sound.** It is the work count
    (N1), and the λ-path lives on `continuation`. §4.7 should state it (§7 amendment 2).
  - **2 (a checkpoint at λ "0"): sound.** The easy endpoint is an accepted level of a modified
    problem, which is §4.4's first bullet; the checkpoint is `partial`/`unverified`, and K04
    refuses it as `continuation_level(0)`. It needs a test (N2).
  - **5 (the step's checkpoint is the recovery's, else the failed solve's): sound.** It is the
    step's last accepted iterate either way; see N2 for the one state/checkpoint split.
  - **13 (the guard before the absent-state path; `continuation_level` before the outcome check):
    sound.** The first stops an UNVERIFIED certificate being labelled with a declaration the solve
    did not solve. The second makes the refusal name what the state is, which is A03's wording.
  - **14 (identity sources): amend.** The result's fingerprint and the result's plan identify the
    solve. The caller's `solve_plan` is compared but is not an identity source (S1). The
    revision document must be tied to the binding (S2). "For a plan result, the last step with a
    solve result" is right: the executor stops at the first non-converged step, so the last
    detail-carrying step is the one that produced the plan's state. *Measured (P2, G3):* HOM-01's
    whole `PlanResult` handed to `verify_bound` gives `VERIFIED`, and HOM-03's is refused
    `continuation_level(23/256)`.
  - **15 (the state hash without a residual call): sound**, measured equal (N9).
- **Q2 — Is A26's cross-platform half served by adding T04's R0 fields to the K05 identity
  document? Yes.** It is what A26 says: "`scripts/k05_structural_identity.py` includes them". It is
  served under four conditions, which the manifest must show:
  1. The document covers at least A26's five runs: HOM-01, HOM-04, PTC-S1, PTC-S5 and OFF-B under
     PTC. The draft also adds HOM-03, HOM-U and PHS-05 under PTC; keep them.
  2. It carries §10's R0 fields: outcomes and core outcomes, λ and Δλ strings, counts, rejection
     reasons in order, `homotopy_level`, `corrector_*`, `eo_recovery*`, the provenance
     `continuation` block, `checkpoint.continuation_lambda`, and the polish verdict.
  3. It excludes the R1/R2 floats (`pseudo_step`, `pseudo_step_next`, `ser_ratio`, a PTC `alpha`
     below 1) and every digest whose preimage holds a solved float. That means
     `level_constants_sha256` (its preimage holds `p⁰`) as well as the state digests. The draft
     says it does.
  4. A26 is `pass` only after the CI pair has run on the T04 commit and the `identity` job has
     compared the two documents. The manifest cites that run (id and artefact hashes). A local
     run makes the claim `not run`, not `pass`.

  Optional, not required by A26: emit the R1/R2 floats through a `--floats-out` file compared under
  ADR 0007 D2, as T02 A34 did.
- **Q3 — Gate runtime 38 s → 78 s; the family scan is 19.1 s of it (measured). Keep it in the
  gate.** A11 is the only evidence of the edge's reach and honesty over a family. A slow tier that
  runs less often is where such evidence goes stale, and 78 s is not a gate anyone skips. If the time
  must come down, reduce cost rather than coverage:
  - The 18 guesses of a target share one declaration identity (the guess is an orphaned parameter,
    T03 Q2), so they could share one compiled problem. Not measured.
  - Parallelize the suite.

  This is a development-loop preference, so it is Frank's to overrule (§6).

### 5.2 Brief §3 decisions not asked in Q1

3 (corrector events stamped, pairing among unstamped events): accepted. The only in-tree consumers
of `attempt_closed` pairing are `bundle_for` (filtered) and K03/T02/T03 manifest scripts that never
run a homotopy (grep). 4 (item 0's in-memory opening): accepted, and pinned by
`last["opening_state_sha256"] == items[0]["opening_state_sha256"]`. 6 (`stalled_at =
easy_endpoint`): accepted. 7 (in-memory revisions, oracle duties ≤ 7.6e-11 W): accepted; 7.6e-11 W
is seven decades below τ_E and about 3e-15 relative to the duty, eight decades inside the smallest
registered decision margin (1.3e-6, §9.10). 8–11: accepted (8 by W0.1;
9–11 by rulings g, i and F15). 12 (the `tau_start`/`sign` seams): accepted; they are keyword-only,
documented as ablation seams, and never passed on the production path (`region._ptc_attempt`,
read). 16–19: accepted.

### 5.3 Brief §4 ("least sure")

- **The executor's edge-3 insertion.**
  - The trigger set is §5.1's exactly, compared with the reference's constants. `BUDGET_EXHAUSTED`
    triggers only for `newton_iterations` or `ptc_steps`, and a meter refusal overrides every
    budget to `property_calls` before the edge is considered (`executor.py:640-643`).
  - The preconditions run in §5.2's order: policy, trigger, continuation parameter (else
    `unsupported`), then count, which is structural.
  - The contract state is fresh (a new `_solve_region`), and the property cap is the one plan cap.
  - The dense continuation after a merged region is unreachable in v0.1 (N3).
  - The one defect on this path is M1's misrouting of a Jacobian failure into the trigger set.
- **The PTC core's stop, polish and SER bookkeeping.** These match §7 on reading, and the tests
  pin them:
  - The stop test comes before the SER update.
  - The ratio is formed from φ(x_k) and φ(x_{k+1}) of accepted iterates only, with Δτ_used
    (`tau_try`) — pinned by A20's two PTC-S2 ablations.
  - The reset is per `solve_ptc` call, and the region calls it once per attempt without
    `tau_start` — pinned by A25's first-trial check and PTC-S5's ablation.
  - Patience comes after an accepted step, in Newton's order (`newton.py:487`).
  - The polish is excluded from the count.

  The gap is M1's polish Jacobian.
- **The verifier's identity guard.** Two caller paths reach a judgment the guard should have
  refused or made impossible: S1 (`solve_plan=` as identity) and S2 (a mismatched revision). The
  `state=` override skips only the hash, as designed. No path certifies a solve against the wrong
  *declaration*: model_version and constants are compared against every claimed identity, and all
  real results carry a fingerprint.
- **The xfail retirements assert exactly the amended bounds, nothing looser.**
  - A19 φ: `max(1e-12 |φ|, 1e-15)`.
  - A15: `1e-12 + 10 (θ/Δτ) ‖F̂_σ(x*)‖∞`, with the root's own scaled residual measured and
    required to be < 1e-14.
  - A17: the simple modes real to 1e-9 and equal to the closed form to 1e-9; the pair members
    within 1e-6 of −1/θ, the pair's mean within 1e-9.
  - A21: `1e-9 max(|F_k|, |F_{k+1}|, tol) + 1e-13 (1 + θ/Δτ_used)`, with Δτ_used the accepted
    trial's.

  Each is the §12 text. A21 also keeps a stricter four-ulp check beside it. The only narrowing is
  S3's scope, not a bound.

---

## 6. FOR FRANK

Nothing here needs Frank's decision to proceed. One preference is his to overrule:

- **Q3, the family scan in the gate (+19 s, gate 78 s).** Ruled "keep". The alternative is a slower
  tier run less often, which trades regression evidence for local turnaround. Reversible by a pytest
  marker.

---

## 7. What the fixes must not do; amendments recommended to the `specifier`

**The fixes.**
- **M1 must stay numerically inert on every registered path.** Every K03, T02, T03 and T04
  trajectory must be bit-identical before and after; rerun the build lane's 100-run hex dump. The
  Newton half changes a failed Jacobian's outcome from `LINEAR_SOLVE_FAILED` to `EVALUATION_ERROR`
  on no registered path. Record it in K03's notes when it lands.
- **M1 must not fold the polish's Jacobian failure into a polish rejection.** F15(h) separates a
  non-`ok` trial (a rejected polish, `x_c` stands, `CONVERGED`) from an `error` (a defect).
- **S1 must not remove the caller's `solve_plan` comparison.** It remains §4.2's alias check and an
  extra identity claim; it just stops being sufficient on its own.
- **S4 must not be discharged by weakening the manifest's A11 entry silently.** Either the
  reference gains the numbers or the assertion's text changes, by the design lane, recorded.
- **S5 must not change SuperLU's options in the same commit.** The structural refusal is inert;
  changing `relax` is not known to be, and is ADR 0004's decision.
- **M1 must not rely on S5.** Refusing a failed Jacobian where it is evaluated is the correction;
  S5 is defence in depth.

**Amendments recommended (design lane; not made here).**
1. §7.3/§7.5: "a Jacobian evaluation at an accepted iterate or at `x_c` that is not `ok` ends the
   attempt `EVALUATION_ERROR`" (M1). K03 §5.5 gets the same sentence for Newton.
2. §4.7/§10: the homotopy provenance item's `iterations` is the sum of every corrector's accepted
   Newton iterations, rejected λ-trials included (N1).
3. §4.8 item 1: the result's own fingerprint or plan identifies the solve, and a caller-supplied
   plan is compared but does not identify it (S1). Add a revision-identity refusal with its message
   (S2).
4. A11 and §9.3: register the 170 runs' attempts and counts, or strike them from A11 (S4).
5. §5.3: before edge 3 after edge 2 is supported, say which "item 0" a merged region's recovery
   opens from (N3).
6. ADR 0004 (its owner, not T04's specification): record the structural-rank refusal (S5), and
   decide separately whether `relax = 1` stays, given P1c.
