# OPT review (design lane, `reviewer`) — `wp/OPT` at 48733e55 against `docs/design/OPT-revision-optimisation.md` incl. §9 and ADR 0071

**Verdict: sound; one numerical must-fix before `tested` (M1, replay's float comparison across architectures), which CI
has since confirmed on aarch64. CI also shows five mechanical or architectural must-fixes (M2–M6, below M1). There are
five should-fix items, and the two D-61 descriptions pass the design-lane review.** Every reported optimum is judged on a certified
re-solve (R-188): `CandidateVerification.passed` needs V1–V5 `pass`, and V1 passes only on a `VERIFIED` certificate or
on the phase-boundary form, whose (e6) is the certificate's own `grade` returning `VERIFIED` with B's regularity. No
ordinary certificate can change: `verify/` and `compile/` have no diff on the branch, the orchestrator gains only an
in-memory `RegionResult.final_system` and a public wrapper (`admissibility_value`) beside `_admissible`, and nothing
under `verify/` or `orchestrator/` imports `studies.nlp.boundary` (G10c iv). I found no path to a false
`KKT_POINT_VERIFIED`. The defects found fail safe; M1 makes a correct record replay as `MISMATCH` on another
architecture.

Read: design §0, §2.3, §4.6–§4.9, §9 in full; ADR 0071 status and acceptance; `docs/OPT_DECISIONS.md` D-12, D-18,
D-24, D-28, D-30, D-32, D-36–D-50, D-58–D-70; `boundary.py` in full; `verification.py` (`verify_candidate`, V2, V4,
`passed`); `revision_host.py` (`certify`, `held_system`, zero subsystem, `regimes`, `phase_boundary`,
`two_phase_margin`); `replay.py` (`replay_optimization`, D-68's rule, `_recomputed_chain`); `verify/certificate.py`
(`grade`, `_screen`, `verify_revision`'s target); `run/compare.py` (v2 float rule); diffs of `region.py`, `executor.py`,
`sensitivity.py`, `operations.py`, `types.py`, `admission.py` (`admit_optimize`), `runner.py` (optimize),
`validation.py` (optimization task), `test_t07_q26.py`; `docs-site/guide/optimisation.md` limitations; the two changed
descriptions. Ran (default env, `OMP_NUM_THREADS=1`, load ≈ 28): two in-process probes, quoted under M1 and S1. No
Ipopt, no audited-env test, no gate.

## Must fix before `tested`

**M1 — replay compares `verification.json` floats with no floor; on aarch64 a correct record will replay `MISMATCH`.**
`replay.verification_differences` (`studies/nlp/replay.py:245`) calls `run.compare.differences(...,
policy_id=CURRENT_POLICY_ID)` without a floor. Under v2 a float whose key is not a registered floor name is compared
at 1e-9 relative, 0.0 absolute (ADR 0007 D2.3). The verification document's floats are ulp-level or derived from
ulp-level quantities: the committed OPT-A2 fixture (`tests/fixtures/opt/replay/OPT-A2/starts/1/verification.json`) has
V2 `scaled_difference_inf` 1.46e-16, `active_set[0].slack` and `slacks.T-min.lower` 1.01e-9, and V5/`kkt`
`stationarity_residual_inf` 1.32e-10. They are recomputed from a cold re-solve on the replaying machine, and ADR 0007's
own measurements show that solves on x86-64 and aarch64 differ in the last bits. Probe: perturbing those members by
≤ 6e-16 absolute gives **5 differences** (`MISMATCH`). G13 passes on x86 because there the re-solve is bitwise
identical. An OPT-A3-type record will be worse: its V4 margin and phase-row value are about 1e-11. Correction, no new
tolerance (amendment text below): floor each float of `verification.json` at the tolerance of the V-check whose verdict
it feeds, as ADR 0007 D2.2 floors `check.value` at its own tolerance. `differences` already takes `floor`, so this can
be done per subtree in `verification_differences`, with no change to a policy file. Add one test: ulp perturbations
give `MATCH`, and a perturbation above the floor gives `MISMATCH`.

**M1 confirmed by CI.** Run 42431066903 at `wp/OPT` `de18aca2`, aarch64 leg. `test_g13_the_committed_record_replays_to_match_without_ipopt`
fails on `starts/2/verification.json` `checks[4].stationarity_residual_inf` and `kkt.stationarity_residual_inf`:
1.3507706064785907e-10 against 1.3507661655864922e-10. That is 4.4e-16 absolute, 3.3e-6 relative, with "no registered
floor, ADR 0007 D2.3". `test_g11_replay_imports_neither_pyomo_nor_cyipopt` fails on aarch64 for the same reason: its
subprocess prints `MISMATCH`. Every other member compared clean, so only the adjoint's least-squares residual moved.
**Ruling on how to compare:** floor the floats in replay, by the tolerance of the check that judges each one, exactly
as the amendment text below says. The KKT residual members are floored at `TAU_KKT` (1e-6), which makes this pair
`MATCH` by a factor of 2e9. Do not register new floor names in `T08-numerical-policy-v2`: its name set and bytes are
frozen, and OPT's addendum classifies no floats. Do not narrow the floor to the KKT members alone. A boundary record's
margins and phase-row values (about 1e-11) are the next members to move.

**M2 — `studies/` imports `application/` (M04's layering rule; `test_m04_study.py:626`, all legs).** Five modules do
it:
- `nlp/greybox.py` imports `application.jobs.interrupt`;
- `nlp/replay.py` imports `application.revision_run`;
- `nlp/request.py` imports `application.binding`, `revision_run` and `types`;
- `nlp/revision.py` imports `application.policies`;
- `nlp/revision_host.py` imports `application.binding`, `policies`, `revision_binding` and `revision_run`.

The rule stands; an exemption would need an ADR, and I would reject it. Fix it by dependency inversion, with no change
of behaviour or bytes. `studies/nlp/host.py` gains a small route protocol (bind, solve, write bundle, reproduce bundle,
resolve policies), and the application layer supplies the implementation where it builds the host, the readiness check
and the replay. `greybox` takes the interruption as the caller's `check` callable, which it already receives, and does
not import the job's exception type. The alternative is to move `revision_host`, `revision` and `replay` under
`application/` (they orchestrate production runs). It is acceptable but moves more files. Either way, record a D-entry
and prove the move inert with G1, G2, G12 and G13 at x86 bytes.

**M3 — policy-literal guards (`test_t05b_literal.py:194`, `test_t06_f4_literals.py:118`, `test_t06_w18_literal.py:73`,
all legs).** The six `solve-policy.json` files under `tests/fixtures/opt/replay/OPT-A2/starts/{0,1,2}/{start,resolve}/artifacts/`
name the policy value the guards forbid. They are archived outputs in R-939's sense: the replay reads the policies from
the start bundle (D-62 a). **Ruling:** register them in the archived-output list (`tests/f0_support.archived_outputs`)
by path and SHA-256, like R-939's 36. Add a register addendum to R-939: "plus the six G13 fixture files of OPT
(ADR 0071), same mechanism". Do not edit the guards and do not strip the fixture.

**M4 — `apps/web/js/routes.js` stale (`test_m06_static_scan.py:166`, all legs).** Regenerate it with
`scripts/m06_web_routes.py --write` and commit the result. It is mechanical.

**M5 — M02's response snapshot (`test_m02_schemas.py:263`, `solve`'s resolved response digest, all legs).** OPT's
additive `job.schema.json` members (the `optimize` enum value and branch, six artifact kinds, the `optimization` result
member) move the resolved `solve` response. Follow M04's precedent (`without_m04`). Strip exactly Amendment 16's
additions in the test (`without_opt`), so the test proves that the rest is unchanged. Do not re-take the snapshot.

**M6 — M03's report bytes on aarch64 changed (`test_m03_schemas.py:135`,
`optimization_report/valid/nlp_1_without_the_extra.json`, aarch64 only).** OPT's `audited_solver(platform_id)` appends
"the platform linux-aarch64 is not audited (…)" to the solver message even when the extra is absent. So the default-env
M03 report that the reference fixture pins now differs on aarch64. That breaks §2.3's bit-exactness of M03's report,
which G2 measured on x86 only. **Ruling:** when the extra is absent, the message stays M03's byte for byte. The
platform clause is added only where the extra is present on an unaudited platform. Do not regenerate the M03 fixture.
Then add the aarch64 default-env leg to G2's evidence. (The `DomainError H_S2_liquid 500 K` in that test's log is
captured stderr from an out-of-domain fixture evaluation, not the failure.)

D-61's red test (`test_every_description_is_reviewed_by_both_lanes`) is expected. My two design-lane verdicts are below,
and Frank's human review remains open. These CI results predate WO-6c and WO-7, so re-run CI after the fix round before
reading any of M2–M6 as still open or closed.

## Should fix

**S1 — a held `ZERO_FLOW` split fails V4 (and Q4) at every candidate.** `RevisionNlpHost.regimes` records a `ZERO_FLOW`
split with margin `None` (by design: "V4's exact-dormancy check"). `_regimes` (`verification.py:707`) then counts
`margin is None` as `inside_tau_regime`. Probe: `_regimes(RegimeRecord((('U-F','ZERO_FLOW'),), (SplitRegime('U-F','S4',
'TP','ZERO_FLOW',None),)), {'U-F':'ZERO_FLOW'})` → `fail ['U-F']`. Q4 treats it the same way (`sensitivity.py:876`
`PHASE_BOUNDARY`, or Q4′ for a PH-type split). The start is admitted (`phase.py:298` skips ZERO_FLOW), so any revision
with a dormant split is `NOT_VERIFIED` at every candidate. This fails safe, but it contradicts §4.7's table and A-3's
"ZERO_FLOW: unchanged; V4's exact-dormancy check". Signature equality (V4's first clause) is that exact check.
Correction: exclude regime `ZERO_FLOW` from V4's margin list and from the splits `RevisionNlpHost.sensitivity` gives Q4.
Leave M03/E01 callers untouched. Test it on a corpus revision with a dormant split. If it is not fixed in 0.4, declare
it (S4).

**S2 — D-18's deferred assessment checks report `PASS`.** In `validate(task="optimization")` with an assessment,
`ASSESSMENT_OUTPUT_UNKNOWN`, `ASSESSMENT_PARAMETER_STRUCTURAL` and `ASSESSMENT_PARAMETER_DECISION` are `PASS` with
"judged at the first certified start". Nothing was judged. The description promises "a check that did not run says
why". Deferring the checks is right (the program needs a solved state), but the result should be `WARN`, as STR-06
("consistency not established …") already does. That keeps `READY_FOR_OPTIMIZATION` and is honest. `NOT_RUN` is not
the right result: by R-022's logic it would withdraw readiness for every assessment request.

**S3 — D-70: keep the declared limitation, but put the failing start back.** Do not change `IPOPT_OPTIONS` in OPT: they
are frozen since M03, and G2's bytes depend on them. A `mu_strategy adaptive` evaluation is a follow-up under a new
options id. Moving OPT-L's only start to 650 K after the feasible-side starts failed, though, removes a case to pass a
gate. Adopt D-70's own alternative: starts {673.15 K, 650 K}. The report stays `KKT_POINT_VERIFIED`, and start 0's
`SOLVER_FAILED` (500 iterations) pins L-OPT-2 in G20's record.

**S4 — declared limitations missing from `guide/optimisation.md` and the manifest:** (a) D-42: a single-phase held
split on a γ–φ provider never certifies today (K04's witness stencil steps the held zero side negative), so such
starts are `START_NOT_CERTIFIED`. The "unguarded" admission is reachable today only for ideal splits with no `LnKBlock`.
(b) `pr-c1-v1` held single-phase splits → `REGIME_MARGIN_UNDEFINED` (F8's default). (c) Thermal-port boundary
candidates fail V1 (A-1 scope). (d) S1, if not fixed.

**S5 — tests of the boundary clauses' failure branches.** No test reaches (e5)'s fail branch or any (e4) branch. Add
these cheap ones: (e5) at OPT-A3's candidate, monkeypatch the boundary split's `pinned(regime)` to return as many
*other* columns (the liquid-side flows). B then keeps the singular direction and must screen rank-limited. (e4) Three
synthetic negatives: |P| ≠ |D|, a pinned column ≠ 0.0, and a dropped row that is alias-eliminated. Without the (e5)
test, a `boundary_form` that deleted too much would pass G10a (A = ∅) and G10c unchanged; only G10b's 1 % rcond pin
would catch it.

## Notes

- N1 (hidden scale). Activity (e3), V3 is |a/N0| ≤ `TAU_ACTIVE` with N0 = 3 mol/s, and a = Σn·(1 − Σ x K). The TWO_PHASE
  margin is min(V, L)/N0 ≥ `TAU_REGIME`. Both are absolute in flow. At Σn ≪ N0 (lab scale), a row counts as "active"
  at a closure margin of up to 3e-6/Σn, and a two-phase split with min(V, L) < 3e-4 mol/s always fails V4. Both effects
  fail safe or are only mislabels (`regime_note` calls an interior point a boundary point). Declare for 0.4. A
  scale-free form (relative to Σn) is a follow-up; it needs a decision, and I would take it with the next E01/OPT
  revision.
- N2 (D-48). The private `_staged_splits` import is acceptable because G10a pins the rebuild byte for byte at five
  states, and the shape check in `certificate_target` catches id drift. If K04 ever moves, a public name is the right
  fix.
- N3 (D-45). Q1′ trusts `CertificateEvidence.basis`, a string. Today only `RevisionNlpHost.sensitivity` sets it, and
  only after `phase_boundary` passed. Passing the `BoundaryVerdict` instead of a string would make that unforgeable.
- N4. `application/local.py:1623` still refuses `task: optimization` in change-sets "as `validate` refuses it". The
  refusal itself is in scope (§4.11 lifts `validate` only), but the comment is now false.
- N5 (cost). Replay re-solves each `resolve/` bundle twice (`reproduce_bundle` and `verify_candidate`'s `certify`) and
  re-runs every start. `boundary_form` densifies the matrix. Both are fine at ≤ 300 columns.
- N6 (D-68). The near band ‖s| − τ| ≤ 1e-15 is narrower than cross-architecture noise for scaled constraint values much
  larger than 1. A genuine near flip there reads `MISMATCH`, which fails safe.

## Rulings

1. **A-1 as built: sound.** B is the certificate's matrix with each boundary split in its regime's own form (rows
   `dropped(regime)` out, columns `pinned(regime)` held), which is the held-regime system the attempt solves. B can
   miss a singularity only if its null vector has support on the pinned incipient flows. Such a direction leaves the
   held regime, which pins them, so for "a KKT point of the held-regime problem" that is the right regularity
   judgement. Any singularity inside the regime survives the deletion: (e5) fails it, and a rank loss caused by a
   split outside A does too. (e6) re-runs every other check through the certificate's own `grade`. D-45 accept (N3).
   D-48 accept (N2). D-49 accept: (e6)'s policy-hash check is stricter than the design. **A-2:** D-39 and D-41 accept.
   The block-triangular argument holds as coded (`_zero_rows` uses exact `!= 0.0` over free columns outside Z and
   ∂F/∂d), and V2 compares held zeros exactly. **A-3:** D-40 and D-43 accept. **Unguarded admission (R-924): sound.** An
   unguarded split has no row, so Ipopt may cross. The cold re-solve then changes signature, or V4's margin
   (the closure's own test, ≥ `TAU_REGIME` > 0) fails. When V4 passes, the omitted inequality is inactive, so the
   verified point is a KKT point with or without it. This fails safe; declare it per S4(a).
2. D-12: superseded by A-3. The code uses `admissibility_value` and does not revert to `tp_margin`. D-42 is correctly a
   declared limitation here: the cause is K04's witness policy, which is out of scope. Queue it with L-X10-1 and
   declare it (S4).
3. D-18 → S2. D-24 accept: an `UNSUPPORTED` report claims nothing. The schema description of
   `formulation.starts` should say that `[[]]` means nothing ran. D-28, D-30 (keep the drop: the manifest member SHA
   is the candidate's hash) and D-32 accept. D-36: narrowed by A-3. D-38 stands. D-46 accept: this answers D-44, since
   the environment check sits where M03's does and the static probe stays import-free.
4. D-58 accept (R-235's class: decision-space starts and problem coefficients, pinned by full path). D-59 accept
   (R-960 provisional, registered on acceptance). D-60 accept (test resolver only). D-63 accept: two library runs
   differ in exactly those members, and every other byte is compared. D-66 accept as fact; writing per-start members
   as each start ends is a follow-up. D-67 accept. The 588 KB text fixture is accepted: it is what makes the
   Ipopt-free aarch64 replay possible.
5. D-61: see below.
6. D-50: amend G10d (text below). G10b's 5 % test at Q̂ too is accepted as the stricter reading. D-62 (a)–(e) accept;
   (f) is closed by D-68. D-68 accept (N6). D-70 → S3.
7. **F2** is answered by A-3: the margin is the closure's own test, confirmed in code. **F3** accept: G12 holds inline
   and spawned under D-63's masks. **No ordinary `solve` certificate changed:** see the verdict. I did not re-run F0;
   the engineers report M1–M9 PASS after every WO.
8. **`implemented` is right.** For `tested`: M1–M6 done, and CI's aarch64 leg reads G13 and G11 `MATCH`. D-61 recorded for both
   lanes, so `test_every_description_is_reviewed_by_both_lanes` is green. G21 full gate PASS at the merge candidate
   (check whether its mypy step reports the 3 `benchmarks/opt` errors; fix them if it does). CI green on both legs.
   Manifest re-taken at that commit with OPT.G21, OPT.G13.aarch64 and OPT.D61 results. S1–S5 done, or S1 declared.
   ADR 0071 moves to Accepted with its register entries.

## D-61 — design-lane description review (exact served text at 48733e55)

Method as T08.A18: each claim checked against `dispatch` behaviour (`operations.py`, `validation.py`, `admission.py`,
`runner.py`, `job.schema.json`, `optimization-request.schema.json#/$defs/optimize_body`).

- **`validate.md` (sha256 `ec0e770d…`, 1341 chars): PASS (design lane).** These claims are true: `optimization` is an
  optional member of `validate_revision`'s input (`$ref` to the request schema) and decoded; the checks are
  `OPT.<CODE>`; the status is `READY_FOR_OPTIMIZATION`; without the audited solver the refusal `unsupported`
  `nlp_solver_unavailable` comes before the revision is read; static readiness binds probes and never solves. "Can be
  submitted as an optimize job" is true, though readiness is not required at admission. The sentence "a check that did
  not run says why" is made fully true by S2. Advisory for the next revision: say that `optimization` is required for
  the optimization task (today the refusal is `invalid_request`).
- **`submit_job.md` (sha256 `123d4e93…`, 1494 chars): PASS (design lane).** These claims are true: the `optimize` body
  is `solve_body`'s members plus `request`, with `policy_id` defaulting to "default"; the result member `optimization`
  is the report, `null` when there is none; the job ends `completed` whatever the report status; a looser tolerance
  ends `verification_weakening_refused` (in the job, not at admission); "a solve's revision must be
  READY_FOR_SIMULATION" correctly no longer covers `optimize`, which is judged in the job. Safety: nothing invites
  reading an optimize job as verified, since the text points at the report's status. Advisory for the next revision:
  `optimize` is also refused `nlp_solver_unavailable`, and a tightened `check_tolerances` makes every start
  `RELAXED`, so no optimize can verify.

Frank's human review of both remains open and is not something this review records.

## Amendment text

**Design §4.9 step (3), M1.** Replace "floats within D2" with: "floats under ADR 0007 D2, each float of
`verification.json` floored at the tolerance of the check whose verdict it feeds (D2.2's principle, as `check.value`):
V2 `scaled_difference_inf` at `TAU_GROSS`; V3 `slacks`, `active_set[].slack`, `constraint_values`, V4 `splits[].margin`
and phase-row values at `TAU_FEAS`; V5 and `kkt` `stationarity_residual_inf`, `objective_gradient_scaled`,
`constraint_gradients_scaled` at `TAU_KKT`, `multipliers` at `TAU_SIGN`, `licq_singular_values` at `TAU_LICQ` times
the largest; V6 `objective` relative only. Outcomes, active sets and classifications stay exact (R0) under the
near-threshold rule. No new tolerance."

**Design §9.5 G10d, D-50.** Replace "0 < a/N0 ≤ 1e-7" with "0 < a/N0 ≤ 1e-9". The bound "|T − T_d| ≤ 1e-6 K" then
follows, because d(a/N0)/dT ≈ 0.026 K⁻¹ at T_d.

## Not established

I did not examine `formulation.py`, `greybox.py` (the Ipopt NLP, gradients, the Hessian policy), `request.py` beyond
"never solves", `closure.classify_starts`, the cost/LCA scripts and the G19/G20 numbers, `performance.py`, the CLI, the
surface link and chain, or the schemas beyond `optimize_body`. I re-derived no mpmath expectation and ran no audited-env
test, gate or F0. M1 was predicted from the comparison rule and then observed in CI run
42431066903 (at `de18aca2`, before WO-6c and WO-7). M2–M6 come from that run's log, which I read only by `grep`. I
re-ran none of them.
