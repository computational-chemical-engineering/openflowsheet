# T08 review — kinetic CSTR, PTC-R1 registration and harness, warm starts, record fixes

**Reviewer:** design lane (`reviewer`), 2026-09-29. **Branch:** `wp/T08` at `9777e53`; code under review
`16e56af..f9a7f66`. **Brief:** `docs/briefs/T08-review.md`. **Built against:** T08 build-first spec Parts A–B
with Amendment 1, release spec §6/§9, ADR 0023/0024, `docs/T08_DECISIONS.md` (2026-09-29 entries).

**Timing.** This review precedes W5: no PTC-R1 result exists and none was produced here.

## Verdict

**Sound. There are no must-fix (M) findings.** The harness makes §A4.5's calls, the same ones T06's `_run_revision`
makes (`benchmarks/t06/ensemble.py:560–608`). It classifies per §A4.3 on `run.outcome` and the region's final
state, which are §A1.5's `x₁`, `x₂`. It catches every non-typed end as a counted crash. It records what B21 needs
for the C trace. `revision.json` realizes §A1.5 as amended: the feed is `(0.4990234375, 0.5, 2⁻¹⁰)`, with Da
0.072, `T_ref = T_c` = 360 K, `T_s` = 3.125 K, `F_c c_c` = 0.3·100, ΔP = 0, ν = (1, −1, 0), key B, and a vapour
outlet and inlet. The arms are `T06-revision-v2` with only `eo_core` and `eo_recovery` changed (tested). `case.json`
recomputes. The YAML at `C_case` is byte-identical to `C_A1`'s (`98b3a43e…`).

- **The CSTR's residual and Jacobian are the same function.** Both come from one symbolic expression
  (`rows.py` `kinetic_balance_row`, `cooling_row`), and B12 and B15 compare them against the design lane's
  independent YAML.
- **`mass.py` D2 leaves the flash and heater family unchanged.** Their `outflows` ignore the new argument, and
  `syn001_residence_time` builds `phases = {}`. The CSTR's one `PhaseOutflow` uses the declared `Phase` literal
  (`"VAPOR"`), which is consistent with the heater's.
- **The verifier's CSTR entries share no code with the solver** (R-016). They use the rate recomputed in Python
  binary64, fresh enthalpies, and a cooling relation that reads no enthalpy. A wrong-sign ν, or a rate formed
  at the inlet temperature, would fail `material_balance.U-CSTR.*` at a converged state.
- **Warm starts cannot change the problem.** The candidate reaches only `x₀`. The region is the whole
  declaration (`plan_revision` makes one region over every authoring unit), so no candidate value is ever
  read as a fixed input. Bounds, tolerances and the check policy come from the target.
- **The identity fixes are real tests.** A11 compares against the run's own ids. A12 compares against the
  trace meter, with a nonzero meter. A13 checks the registered key twice, and confines the bundle-level diff to
  the named fields.

Seven S and seven N findings follow. The three rulings are in §3.

**Probe run (disclosed for the manifest).** One run per arm went through `compare.run_start` from the **LOW root**
(row `[99, 99, …]`, not a registered start). Both ended `CONVERGED` at pseudo-step/iteration 0, class `LOW`, at
distance 3.1e-15, `VERIFIED`, with 2 property calls and no bound blocks. This exercises the record path
end to end (bind, plan, execute, attempts, blocks, counters, `c_final`, classify, verify) and reveals no basin
information. §A4.6 forbids PTC-R1 runs before `C_case` only; this ran after it. No run started from a registered
start, and `--run` was not invoked.

**Not examined:** the V17 reference/scorer changes and `t07_reference_t08.json`, the generator scripts, the
release-spec phases 2–5, V19, MCP prose, the `wp/T08-d1-str05` side branch, `runner.py`'s interruption paths, and
the B40–B49 test bodies beyond B41, B42 and B46 as amended.

## 1. Findings

### S — should fix

**S1 — A typed end with no single `solve_eo` step is recorded as a crash with `outcome: None`.**
`benchmarks/t08/ptc_r1/compare.py:324–339`. `(step,) = [...]` runs before `out.update(outcome=run.outcome, …)`.
- *Scenario:* any `PlanResult` without exactly one `solve_eo` step, for example a plan that ends before its
  region. The harness then records `crash: "ValueError: …"`. The typed outcome and counters are lost, and B21's
  "every run ends typed" is failed spuriously.
- *Fix:* record `outcome`, `message` and `counters` from `run` immediately after `execute_plan` returns. Then
  destructure.

**S2 — B21's facts omit what the P-budget ruling and the C-blocker clause need.** `compare.py:260–282`,
`:327–333`, `:407–421`.
- (a) A PTC polish rejected `bound_blocked` is kept with `columns: None`. `runs_with_c_blockers` excludes it, so
  the summary cannot show that no bound block names a C column. It is physically near-impossible, since nothing
  sits on a bound at a converged state, but that is exactly what B21 checks.
- (b) `RegionResult.budget` is not recorded. A `BUDGET_EXHAUSTED` run is then told apart only by inference: the
  `ptc_steps` budget, or `property_calls == 10000`.
- (c) The attempt count is recorded per run but not summarized.
- *Fix (recording only):* record `detail.budget`. Add these to `b21`:
  - `runs_with_unattributed_bound_blocks`;
  - `budget_exhausted` split by `budget`;
  - `max_attempts_per_run`;
  - `max_property_calls_per_run`.

  Do it **before W5**: a recording gap cannot be closed after the 2 × 882 runs without re-running them.

**S3 — `--run` has no preconditions against a dirty tree or an overwrite.** `compare.py:480–501`.
- *Scenario:* `_run` writes `results-<machine>.json` unconditionally and only records `tree_clean`. A second
  invocation silently replaces a first result before it is committed, and a run from a modified tree is not
  attributable to its commit. R-118 ("nothing is re-read after the result") then rests on discipline alone.
- *Fix:* refuse unless `provenance()["tree_clean"]`, and refuse when `results-<machine>.json` already exists,
  as `_write_case` refuses to rewrite.

**S4 — A warm opening that ends before any attempt, other than by the opening check, ends the run with the
warm start recorded `accepted`.** `src/process_runtime/orchestrator/executor.py:762`; `region.py:1642–1648`
(`_KernelRefusedError` → `EVALUATION_ERROR`, no attempts); `region.py:1794–1800` (§7.8 (ii) `_settle` refusal,
no attempts).
- *Scenario:* a candidate passes `integrity`, `compatibility` and `evaluation`, but §6.2's kernel refuses at
  its state, or the opening's zero-flow fixed point does not settle. `_warm_start` treats only
  `INITIALIZATION_FAILED` with no attempts as a rejection. The step therefore ends `EVALUATION_ERROR` or the
  settle refusal's outcome, with `warm_start.status = "accepted"` and no `initializer_accepted` event.
- This contradicts §B2: "the run never fails because of the warm start", and the next source follows. The
  record also contradicts the trace. The end is typed, and reaching it needs a kernel/residual disagreement, so
  this is S rather than M.
- *Fix:* in `_warm_start`, treat any result with `not result.attempts` and outcome ≠ `BUDGET_EXHAUSTED` as
  `rejected(f"opening:{result.outcome}")` and fall through to the traversal. Test it with a monkeypatched
  kernel refusal.
- *Timing:* the arms never enter `_warm_start` (`initializer_chain == ()`). Land it after `C_res`, or record that
  argument with the commit if it lands before.

**S5 — P-budget, made checkable: B21 needs a defect clause.** This is a specification item for the design lane;
see §3.1. Without it, a run that did exhaust the cap would be scored `FAIL` and would count *against* the arm.

**S6 — P-trace: record the erratum before W5.** This is a specification item; see §3.2.

**S7 — `region_bundle` still reports the false zero when called without `step_index`.**
`src/process_runtime/verify/failure.py:301`. The one caller passes it (`revision_run.py:470`), so this is not
reachable today. A future caller would reintroduce D3.
- *Fix:* make `step_index` keyword-required. Alternatively, refuse a plan trace without it.

### N — notes

- **N1 — `case.json` pins the harness by path only, and pins no solver code.** At the verdict, B20 should
  examine `git diff c337fa1 <C_res> -- benchmarks/t08/ptc_r1/compare.py src/`.
  - Harness edits made before W5 are admissible without re-registration when they are recording-only, because
    no result exists yet.
  - Any `src/` change after `C_case` needs a stated inertness argument for the arms.
  - Since `C_case`, `src/` has changed only in `f9a7f66` (failure-bundle ids) and `c3fb13e` (offering
    `T08-ptc-v1`). Neither touches a solve.
- **N2 — The harness's certificates carry empty `policy_id`/`plan_id`.** It calls `verify_revision` directly, as
  T06 did. D2 fills the ids only in `solve_route`. This is harmless for classification, and the verdict should
  not read it as a D2 regression.
- **N3 — `rate_exponent_overflow` bounds `exp`, not the rate.** `kinetic_cstr.py:352–358`.
  - *Scenario:* `damkohler = 1e300` with `(T_max − T_ref)/T_s = 533` passes construction. `evaluate` then forms
    `scaled = inf`, `key_out = 0` and `rate = inf·0 = NaN`. The non-key outflows are `NaN`, and `NaN < 0.0` is
    false, so they pass the exhaustion check. The EO row gives `inf`.
  - §A1.2 promises "typed, never inf/nan".
  - *Fix:* refuse when `Da · exp((T_max − T_ref)/T_s)` is not finite. This is outside PTC-R1's parameters.
- **N4 — Under `T08-warm-v1` on `legacy_eo`, the solve is cold and writes no `warm_start` member.** §B2 says the
  member is written iff the chain names the source. This is W4 engineer narrowing D2; record it as a spec
  erratum.
- **N5 — Two parts of the substitution proof simulate the old code by monkeypatching.** The region-bundle and
  certificate confinement tests in `tests/test_t08_w1_identity_substitution.py` do this. The byte-level proofs
  against real old bytes exist for:
  - the identity key;
  - the initializer bundles (`test_t07_w3f…`, reverse substitution to `e07f19c5…`/`6eeb7757…`);
  - the regenerated T04 fixture (its git diff is counters only).

  Together these are adequate.
- **N6 — D3's counters are the step's meter.** They equal the run's meter only while the failing step is the
  plan's only metered one. That holds on every current route (revision: one region; `legacy_eo`: feed + one
  region). A multi-step plan would diverge. Pin it with a test if such plans arrive.
- **N7 — Results JSON is non-strict on `NaN`.** `json.dumps(..., indent=1)` writes `NaN` if a failed run's state
  or distance is non-finite (`compare.py:498`). Use `allow_nan=False` with an explicit `null`, or accept the
  output as Python-readable only.

## 2. Answers to the brief's §3

1. **Harness and arms.**
   - The calls are exactly §A4.5's, plus a pass-through shim on `region.solve_newton`. The region calls that
     through its module global (`region.py:2108`), and the PTC core and its polish never call it.
   - Classification is correct and tested at ±1.9e-3 and 2.1e-3 of each root.
   - No run can end untyped without being counted, but a typed end can be miscounted as a crash (S1).
   - The C trace is recorded per §Am1.1/B21: `c_final` from the region's final iterate and the blockers' columns,
     with the gap in S2 (a).
   - B28 is the generator's and is out of the harness's scope.
2. **Open points.** See §3.
3. **CSTR.**
   - The rows form the rate in the evaluator's order. The evaluator's isothermal initializer is §A1.4's.
   - Dormant inlet: `T_init = T_c` and `Q = 0` when `F_c c_c > 0`.
   - The domain is checked before `exp`. On the EO path the provider block meets the domain first, as ruled in
     Am1.2.
   - Beyond N3, nothing is wrong.
4. **`mass.py` D2.** Byte-unchanged for the heater and flash family. The CSTR's `M` is route (a)'s, and B13
   checks it to 1e-13 against the YAML, so a wrong-phase enthalpy (≈ L_i off) would fail.
5. **Verifier.** It cannot pass a wrong rate law or sign: `r` is recomputed from the outlet state and the
   revision's pins. `EXTERNAL_DUTY_MODELS` makes the envelope energy balance read `Q`. Nothing is shared with the
   solver.
6. **Warm starts.**
   - The problem is unchanged (see Verdict).
   - Every rejection is typed and falls through, except the pre-attempt path in S4.
   - A rerun reads only the bundle (`reproduce_bundle` → `_recorded_warm_start`, no store).
   - The `r0_projection` branch is keyed on a member that no pre-T08 bundle has, so it is inert (keys measured
     unchanged).
   - The W4 narrowings are sound as recorded:
     - D2: revision route only (N4).
     - D3: bounds are flows ≥ 0, which are the region's only lower bounds (`region.py:843`). Integrity is checks
       1–3, and the evaluation cost is metered inside the step's bracket, so failure bundles count it.
7. **Replay identity.** The proofs would fail on a stray moved byte (N5 on their construction). The counters
   equal the meter on every reachable path (N6, S7).

## 3. Recommended rulings

### 3.1 P-budget — the arm definition governs, and the registration stands as committed

**Ruling.** Two texts disagree:
- §A4.1's row and §A4.5 define each arm as "`T06-revision-v2` with `eo_core` set and `eo_recovery = "none"`".
  That is the definitional clause, and `case.json` hashes it (`c75e3532…`, `11be2aee…`).
- "No property budget" in §A4.1 and the YAML's `max_property_calls: null` (`build_first_reference.yaml:876`)
  state an intent: no budget may constrain the comparison.

The two agree iff the 10 000 cap, which is plan-wide (`executor.py:1043`), cannot bind. It cannot:
- The region opens at most one attempt. The CSTR is single-phase by declaration and has no lifted split, so
  `decide` has no conversion to restart into (`phase_contract.py:475–482`).
- One PTC attempt is bounded by 200 pseudo-steps × (one Jacobian + one mass evaluation + ≤ 11 trial residuals),
  plus the polish. At the measured 4 and 2 property calls per Jacobian and residual, that is ≈ 5 200 plus the
  mass evaluations, well under 10 000 unless one mass evaluation cost more than about 20 calls.
- One Newton attempt is ≤ 50 × (4 + 21 × 2) = 2 300.

**Amend §A4.1's text, not the arms.** Replace "no property budget" with: "the property budget is
`T06-revision-v2`'s 10 000, which cannot bind on this case (≤ one attempt per run; bound above)". Add to B21:
"no run ends `BUDGET_EXHAUSTED` with `budget = property_calls`, and every run opens exactly one attempt; either
is a defect that blocks the verdict (`BLOCKED`), never a `FAIL` class". S2 records both facts.

**Rejected alternative:** lift the cap in the arms. That changes both `policy_sha256` values, and the arms would
no longer be `T06-revision-v2` with only the core changed.

**Re-registration: no.** `case.json`, the arms and the YAML are unchanged. The amendment is spec text plus a
defect clause, written before any result.

### 3.2 P-trace — B21's 1e-10 governs; record the YAML's 1e-12 as an erratum, and do not regenerate the YAML before `C_res`

**Ruling.** §Am1.C's B21 row is the normative assertion: amended rows replace §C.1's, and B21 carries the
tolerance's derivation, "≥ 400 × the worst accumulation … 2.3e-16 mol/s per step over 5 × 200 steps". The YAML's
`criterion.trace_component` (`build_first_reference.yaml:880–882`) is prose emitted by the generator
(`t08_build_first_reference.py:1062`), and it mis-transcribes that row.

Record the erratum now, in a short Amendment 2 or a dated note in the spec: "B21's C-trace tolerance is 1e-10
mol/s; the YAML's 1e-12 is a generator transcription error, superseded; the generator is corrected after
`C_res`". The verdict judges at 1e-10 and reports the raw maximum deviation. The harness already records it.

**Do not regenerate the YAML before `C_res`.** Its sha256 is in `case.json`, so `--run` would refuse and a new
registration would follow for no gain.

**Re-registration: no.**

### 3.3 P-STR04 — D1's rule for row and parameter ids

**Rule.** A validation message names only ids that the revision's author wrote or that the model's published
contract defines:
- instance, connection and specification ids;
- port names;
- a model's declared equation ids and declared pin names.

A binder-internal unit id is replaced by its revision instance id wherever it occurs. This uses D1's map
(`report.unit_degrees_of_freedom`: `unit_id → instance_id`) and one shared helper for STR-03, -04 and -05:
- **Row ids** `<unit>:<equation>[:<port>]` become `<instance>:<equation>[:<port>]`. The equation id and the
  port are the model's contract.
- **Parameter ids** `<unit>.<parameter>` become `<instance>.<parameter>` when the parameter is a declared pin.
- **A binder-internal parameter the revision never names** (SYN-001's `T_spec` in the
  `SPECIFICATION_CONFLICT` refusal, `application/binding.py:750`) is named by the specification ids that set
  it. The refusal already names both, so the parameter token becomes `<instance>.<parameter>` and nothing is
  added.

**Test.** Use T08.A10's pattern (ii): rename the instance, and assert that no `U-…` binder id and not the old
instance id appears in any STR-0x message.

**Approval.** The move is substitution-only, proven the way STR-05's is: reverse the substitution and reproduce
the old bytes. If any registered identity document holds an STR-04 FAIL message, the move needs Frank's
approval like the held STR-05 branch (his F4 covered D2/D3 only). Bundle both into one approval.

**Re-registration of PTC-R1: no.** Validation messages are not part of the case.

## 4. Whether W5 may run

**Yes, on Frank's go-ahead; nothing blocks it.** Before W5, land S1–S3 (harness recording and preconditions, one
commit) and the spec text for S5/S6 (§3.1–§3.2). This is not because they would change a class. A recording gap
or an overwrite cannot be repaired after the 2 × 882 runs without re-running them.

None of this needs a re-registration:
- the harness is pinned by path, and no result exists;
- `case.json`, the arms, the starts and the YAML stay as committed at `C_case`.

S4 and S7 do not touch the arms and may land after `C_res`. If they land before, note the inertness argument with
the commit (N1). The manifest must record this review's root-start probe (above) and must not set `reviewed` on
the build lane's behalf.
