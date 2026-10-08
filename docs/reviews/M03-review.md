# M03 review — sensitivities, sweeps, estimation and the general NLP gray-box adapter

Design lane, `reviewer`, 2026-10-08. Read-only, at `wp/M03` HEAD `e9de5ee`
(`git diff main...wp/M03`). The work was reviewed against these sources:
- `docs/derivations/M03-studies-spec.md` A01–A48, with §16 (Amendment 1);
- ADRs 0031 and 0032, with their amendments;
- R-180…R-191, R-210…R-215 and R-218;
- `docs/m03-ipopt-audit.md`.

Nothing was built or run for this review. The numbers quoted as measured are the build lane's
(default gate 7047 passed / 31 skipped / 17 deselected; `nlp` gate 17 passed), or they were read
from committed fixtures.

## Verdict

**The numerics are sound, and so is the architecture. One must-fix lies in the verification
harness, not in the method.**

What is sound:
- The twin and its bitwise guard.
- The scaled forward and adjoint systems on one factorization.
- Q0–Q4′, with Amendment 1's Q2′.
- The sweep semantics.
- The estimator and its identifiability rule.
- The full-space formulation.
- The V1–V6 verifier.
- The status function (A47).

I checked the algebra line by line:
- `Ŝ = −Ĉ Ĵ⁻¹ F̂_p`;
- `Ŝ_adj = Λ̂ᵀ F̂_p` with `Ĵᵀ Λ̂ = −Ĉᵀ`;
- the unscaled `S = S_y Ŝ S_p⁻¹`;
- `J̃ = W^½ J S_θ`, read from `Ŝ` with output scale σ;
- `∂f/∂θ = Ŝ/s_θ`;
- the prediction gradient `Ŝ_v σ_v / s_θ`;
- the V5 rows in scaled decision coordinates, with the bound rows `±e_j`.

All of them are consistent with spec §2, §3.6, §7.4 and §8.5.

The must-fix is F1. The default gate compares the emitted study fixtures **byte for byte**. Those
fixtures contain:
- `state_sha256` digests;
- converged floats;
- FIT-U's arbitrary final `r` and its roundoff singular value.

That comparison breaks ADR 0008 D2.1, which says no test may pin a digest value. It also contradicts
Amendment 1 §7.4, which says nothing may be derived from an undetermined parameter's final iterate.
It will fail on the registered CI pair. The repository has met this before: `run/compare.py` and
`tests/test_k03_schemas.py` record both the measurement and the earlier retreat from byte
comparison.

## Findings

### F1 — must-fix: byte-exact fixture comparison pins digests, ulps and FIT-U's arbitrary iterate

**Where.**
- `tests/test_m03_schemas.py:112-129` is in the default gate: `read_text() == serialize(document)`
  for every study fixture.
- `tests/test_m03_nlp_greybox.py:433-441` compares the `nlp` fixtures exactly, masking only
  `wall_time_s`.
- `tests/test_m03_nlp_greybox.py:444-453` compares `nlp-measurements.json` byte for byte.

**Evidence.**
1. The study fixtures carry 13 distinct `state_sha256` values, plus `full_state_sha256` inside the
   root fingerprints. ADR 0008 D2.1 says that "no test may pin a digest value".
2. `run/compare.py`'s header records the 2026-09-21/22 measurement. On the same commit and lock,
   x86-64 and aarch64 differ by 1–3 ulps in converged floats, and the difference enters at SuperLU.
   Two `ubuntu-latest` runners also disagreed. `tests/test_k03_schemas.py:107-110` gave up byte
   comparison for exactly this reason. `ci.yml` runs the default gate on `ubuntu-latest` **and**
   `ubuntu-24.04-arm`. The 7047-pass figure comes from one machine.
3. `estimation_report/valid/fit_u_unidentifiable.json`, which the same test compares exactly, pins
   these values:

   | Value in the fixture | What it is |
   | --- | --- |
   | `final_iterate` of r = 0.9690555399030523 | arbitrary along the null direction (§7.4, Amendment 1) |
   | σ₂ = 3.855e-11 | roundoff |
   | null-direction component −1.31e-14 | roundoff |
   | U-HEAT.Q `null_projection_relative` 0.99747 | class (iii): registered only as a range |
   | S4.N projection 6.3e-15 | roundoff |
   | `nfev` = 26 | path counter |
   | `state_sha256` of the state at r̂ | digest of an arbitrary state |

   On a different BLAS or another architecture, trf's path along a gradient made of roundoff can end
   anywhere in [0.50, 0.97]. A27 and A28 were amended precisely so that nothing depends on these
   values. The fixture test reintroduces that dependence.
4. Spec §3.7 claims bitwise reproducibility *on one platform*. The test's docstring cites that claim,
   but the gate runs on two platforms.

**Fix.** Use the established rule: compare with `openflowsheet.run.compare.differences` under the
current policy, `CURRENT_POLICY_ID`. Under that rule:
- structure is compared exactly;
- float-derived digests are compared for shape only;
- floats are compared within the policy;
- `wall_time_s` is volatile, as in R-015's applied note for `VOLATILE_FIELDS`.

The FIT-U values in item 3 must also leave the value comparison:
- the undetermined `final_iterate` is checked only to lie inside its bounds;
- σ_min and the off-axis null components are checked against A27's bounds;
- the class (iii) projection is checked against the registered range;
- the path counters are recorded and not compared.

One gap remains. Scaled sensitivities that are roundoff zeros (around 1e-15) need an absolute floor.
Use §4.7's `τ_abs = 1e-11`. If v2's policy data cannot express that floor, the design lane registers
it in one line. Apply the same rule to the `nlp` fixtures and to the Q-F2 record: compare the record
for structure and margin, not for bytes.

**Acceptance.** The default gate is green on both CI runners before the manifest says `tested`.

### F2 — should-fix: the report does not record the thread configuration its numbers depend on

**Where.**
- `closure.solver_record`, `closure.py:598`;
- the schema's `solver`, which has `additionalProperties: false`;
- `greybox.optimize`.

**Evidence.**
- Audit §9, WO-8 item 5: with 48 OpenMP threads, NLP-1's r moves by 1 ulp, and NLP-INF takes 498
  iterations against 597.
- `OMP_NUM_THREADS=1` makes runs identical. `OPENBLAS_NUM_THREADS=1` does not.
- Only `scripts/m03_nlp_check.sh` sets it. The test checks `os.environ`, not the report.
- ADR 0007 D6 says a differing thread count is a differing environment, that it must be recorded,
  and that it moves replay to `compatible_reproduction` at best.

**Fix.** Add an environment record to `solver`:
- `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS` and `MKL_NUM_THREADS` as set;
- the effective `omp_get_max_threads()` of the NLP stack's `libomp`, read through `ctypes` from the
  mapped object;
- the `libpynumero_ASL` path and SHA-256 that were actually used.

The `nlp` tests then assert the recorded effective count is 1. Do this before ADR 0032 is accepted:
the schema freezes with it, and adding the field later would be a schema change. Enforcement is a
separate question, ruled under Q2 below.

### F3 — note: A40's "sum" is not a budget anything enforces

See ruling Q1.

**Where.** `test_m03_nlp_greybox.py:281-282` asserts the NLP-1 sum of iterations and wall times
against one run's limits.

**Fix.**
- Keep the per-start assertions. They already cover both reports.
- Relabel the NLP-1 sum as a cost regression, or drop it.
- The design lane amends A40's wording.

### F4 — note (matters only if N1 is declined): the NLP capability is not gated by the extra or by N1

**Evidence.**
- `audited_solver()` (`closure.py:161`) tests only that `pyomo` and `cyipopt` can be imported.
  `greybox.environment_problems()` tests the ASL hash and the mapped objects.
- `scripts/build-m03-ipopt-env.sh` installs from `nlp-pip.lock`, not from the extra.
- So reverting `91537b0` alone leaves `optimize()` solving in the audited environment.
- `e9de5ee`'s inventory records `nlp_extra_declared: true`, so after a revert the inventory's
  `--check` fails until it is re-taken. The commit message says so; it is not silent.

**Fix.** Add one constant, `NLP_LICENCES_ACCEPTED`, citing N1, and have `audited_solver()` check it.
Set it in the same commit as the extra, so that a decline is still one revert, plus re-taking the
inventory.

### F5 — note: the twin guard proves identity at p₀ only, and the NLP evaluates the twin elsewhere

Q0′ compares the twin with the base at the base's own pinned values (`sensitivity.py:588`). Suppose a
row builder reaches a pinned value by closure rather than through `parameters`. It would build a
bitwise-identical twin at p₀ with a wrong `F_p`. The guard cannot see that, and the NLP evaluates the
twin at d ≠ d₀ on every iteration.

Three things cover this today:
- the FD oracle, A09 (five parameters at P1 and P3);
- the closed form, A05;
- V1/V2, at the end of an NLP solve.

**Fix.** One cheap direct test would close the gap for future hosts. Build the twin at P1 with r
symbolic, evaluate it at `(x*_P2, r = 0.95)`, and require it to equal P2's base residual and
Jacobian bitwise. `test_m03_twin.py:176` checks only `constants_sha256` at the moved input.

### F6 — note (performance, M05-relevant)

**Evidence.**
- `FullSpaceNlp.equality_jacobian` (`formulation.py:321`) calls `twin.jacobian_x` and
  `twin.jacobian_p` as two CasADi Functions (`casadi_backend.py:731`). Each one runs every property
  callback.
- Each sensitivity request recompiles the tear problem and the twin.

At SYN-001 this is immaterial: 0.06–0.08 s per start, and 1.7 s per report, mostly readiness and
verification.

**Fix.** Use one Function for `[F_x F_p]`, which halves the property calls per Jacobian. Cache the
twin per (spec, parameter subset) when M05 needs the speed.

### F7 — note: rule 2's wording when nothing was refuted

In `greybox.py:398-430`, the adapter can raise after Ipopt returns status 0 or 1, either in
`_by_primal_id` or in `verify_candidate`. The start is then `NOT_VERIFIED` with no V outcome, which
is exactly what the literal rule order says. The detail names the exception.

**Fix.** The spec should say "claimed a solution that was not verified" rather than "refuted". No code
change is needed.

### F8 — note

1. `closure.optimize` (`closure.py:681`) catches only `ImportError` from the adapter import. A
   different error raised while importing Pyomo would escape `optimize()`, contrary to §8.7's "never
   raises". Catching `Exception` there and returning `NLP_SOLVER_UNAVAILABLE` closes it.
2. `formulation_record` records the first verified start's regimes as "declared". V4 correctly uses
   each start's own regimes. If two starts ever differ in regime, the formulation block misstates
   them.
3. Q0 is structurally vacuous in `syn001_sensitivity` (`syn001.py:163`), because the context comes
   from the same tear problem. Q1′ matches the certificate by state hash only. Q1 still catches a
   foreign state, because every pinned input enters a row. A20 tests Q0 at the core, where it is
   meaningful.
4. `tp_margin` assumes K does not depend on composition, which is the ideal bubble/dew test. That
   holds for SYN-001 and for spec §3.4's scope. A non-ideal host needs a new margin definition (ADR
   0031 C3).

## Rulings

**Q1 — A40's "sum".**
- The §8.4 budget is **per Ipopt run, for every run**. `max_iter` and `max_wall_time` are options of
  one Ipopt invocation, Ipopt enforces them per start, and §8.6's `limits` records them as such.
- A multistart total is not a budget M03 declares or enforces. As an assertion it would hold for
  NLP-1 (54) only by accident and fail for NLP-INF (597).
- A40 therefore reads: every start, of every report, records its status, iterations, counters and wall
  time, each within §8.4's per-run limits. Sums are recorded cost, not a gate.
- The build's per-start loop over both reports is the A40 evidence. The NLP-1 sum is a regression
  observation (F3).
- The design lane amends A40's sentence. No tolerance changes.

**Q2 — Threading.**
- **Record: yes** (F2). Under ADR 0007 D6 the thread count is part of the environment identity.
- **Enforce: no, not in M03.** ADR 0007 D6 deliberately leaves "single-threaded is a product
  requirement" undecided. An adapter that silently overrides the user's OpenMP setting would decide it.
  Instead, `docs/reference-environments.md` states that 1 thread is the recommended and measured
  setting: bitwise reproducible, and 1.7 s against 3.2–3.9 s. The check script keeps setting it.
  This **needs a decision** if Frank wants it to be a product rule. My lean is to record it, not
  enforce it.
- **Replay identity** requires the recorded count. A report produced at a different count is
  `compatible_reproduction` at best. Optimization reports are not in an M03 replay bundle, so no
  replay mechanics are owed now.
- The `nlp` fixtures and measurements are valid evidence only under `OMP_NUM_THREADS=1` on the
  audited host. Once F1 is fixed they are compared under the policy, not bytewise.

**Q3 — Build-lane choices.** All seven are accepted.
1. **Required `evaluations.evaluation_errors`.** Accepted. The design lane adds it to the field list in
   §8.6.
2. **`ParametricTwin.block_calls()`.** Accepted. It is additive on a new object and moves no frozen
   interface.
3. **Masking only `wall_time_s`.** Accepted as the volatile set. The comparison around it must be F1's
   policy comparison.
4. **The hash-locked `--target` pytest directory.** Accepted. It keeps the audited environment equal
   to its locks.
5. **Refusing on the ASL SHA-256, METIS-closure objects and HSL objects.** Accepted: these are audit
   §9 items 2 and 4. Pinning only the ASL is proportionate, because it is the one object Pyomo's search
   path can substitute from outside the environment. Item 3 of the Q2 ruling records which ASL was
   used.
6. **Locating CasADi with `find_spec`.** Accepted. `find_spec` on a top-level package does not execute
   it, so ADR 0003 D5.7 holds.
7. **Adapter exceptions recorded on the start.** Accepted. This is spec §8.5 rule 4. `BaseException`
   (an interrupt) still propagates, which is correct.

**Q4 — Vocabulary and precedence.** Sound as built.

Sensitivities:
- `RefusalCode` and `QUALIFICATIONS` carry `UNSUPPORTED_RANK_STRUCTURE`, `LINEAR_SOLVE_FAILED` and
  Q2′, in §3.5's order. Refusals are sorted stably by that order.

Optimization report:
- `classify_starts` implements rules 1–4 and `K > NV > IR > SF` as one pure function, with no
  third-party import.
- The candidate is non-null only under `KKT_POINT_VERIFIED`, and `local_stationarity` is true exactly
  then.
- The reasons are one per non-verified start, in start order, and the readiness reasons follow §8.7's
  order.
- The adapter computes no status of its own.

**Q5 — Does anything silently depend on the extra?**
- **No default-path code depends on it.** The G6 test is a subset check, so the default gate stays
  green with `91537b0` reverted.
- Two items are coupled but not silent:
  - `e9de5ee`'s inventory and audit text record the extra, so they must be re-taken after a revert
    (the commit message says so);
  - the reverse dependence is missing — the capability does not depend on the extra (F4).

## ADR 0031 and ADR 0032

**ADR 0031: may move to Accepted** when all three hold:
1. F1 is fixed;
2. the default gate is green on both registered CI runners;
3. the manifest records A01–A30, A42 and A43–A46 as `tested`.

D1–D7 and Amendment 1 are implemented as written. I found no must-fix in WO-1 to WO-5, WO-2a or
WO-5a.

**ADR 0032: may move to Accepted** when all four hold:
1. F1 is fixed;
2. F2 is done before the schema freezes;
3. A40 is amended per Q1;
4. Frank's N1 answer is recorded, as D5's own acceptance evidence requires.

If N1 is declined:
- revert `91537b0`;
- re-take the inventory;
- apply F4's gate;
- record A35–A40 as `BLOCKED`;
- accept D5/D6 on A31–A34, A41 and A47, and keep D1–D4 Proposed, mirroring the ADR's
  audit-failure clause.

## Not examined

- The [A10] licence analysis (G1–G5) beyond its §9 findings.
- `scripts/m03_ipopt_inventory.py`, the build script and the conda locks.
- The reference generator `m03_reference.py`. A42's `--check` is relied on.
- The schema files in full.
- The FD-oracle helper in `tests/m03_support.py`.
- The register text of R-180…R-215.

Nothing was executed.
