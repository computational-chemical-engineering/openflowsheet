# Progress

Session-resumable state for **OpenFlowsheet**, the agent-native open process simulator. Read this after `CLAUDE.md`,
together with `docs/decision-register.md`, the latest `evidence/<package>/*/manifest.json` and any
open ADRs. Authority: `docs/blueprint-v3.1.md` (architecture), `docs/implementation-plan.md` v1.2
(execution).

This file states the **current position**, not the history that produced it. Closed narrative —
the P00, P01 and P02 handoffs, reviews and findings — is in `docs/progress-archive.md`, which is
not read at session start.

Last updated: 6 October 2026.

## Start here

| | |
| --- | --- |
| Branch | `main` (T07 merged 2026-09-28; T06 merged 2026-09-27; T05b merged 2026-09-25; T05 merged 2026-09-25; T04 and T03 merged 2026-09-24). v0.0.0 is tagged at `9a4391f`. `wp/T06-refs` pushed, not merged |
| Name | **OpenFlowsheet** (R-149, 2026-10-02): distribution, import package and console script `openflowsheet`; environment variables `OPENFLOWSHEET_*`. Install `.venv/bin/pip install -e . --no-deps`; run `openflowsheet solve SYN-001-nominal --out ./bundle` (or `python -m openflowsheet.application.cli …`). Records before 2026-10-02 say `process_runtime` / `process-runtime` |
| Gate | `PATH=.venv/bin:$PATH ./scripts/check.sh` — ruff, ruff format, mypy strict, pytest. Last run green, **4245 tests** (3141 before T06) |
| Done | P00–P03 `tested` and merged — **Phase 0 complete**. **K01 `tested`** and reviewed by Fable, findings closed. **K02 `tested`**, reviewed by Fable, all findings closed including the row-shape consolidation. ADR 0001, 0002, 0003, 0006 and 0008 accepted and applied |
| Next | **v0.2 started 2026-10-06** (`docs/V02_STATE.md`, log `docs/V02_DECISIONS.md`). Order R-153: M01's design lane first (specifier), M06 built alongside, pre-release `0.2.0a1` after M02. K_NH₃ pinned to the code's value (R-152). 0.1.1 is released (PyPI, tag `v0.1.1` on `5473b51`). At most 4 agents at a time |
| Not done | No package is `reviewed` — that needs human numerical and process-modeling sign-off, which no agent may claim. Nothing is empirically validated |
| Pushing | You authorised pushing and merging at milestones on 2026-09-17; that is the standing instruction being followed. `main` is current on `origin/main` |

**Environment.** `.venv` from `requirements.lock`. The two backend spikes live in `.venv-casadi`
and `.venv-pyomo`, git-ignored and rebuilt by `scripts/build-backend-envs.sh`;
`docs/backend-environments.md` records what that produces, including the PyNumero ASL library that
a plain `pip install` does not give you.

**Agents.** User-level (`~/.claude/agents/`), named by role since 2026-09-24: `architect` and
`reviewer` (the design lane's design and review agents; they replaced `fable-architect` /
`fable-reviewer`), `opus-engineer`, `sonnet-implementer`, `recon`. Project-level
(`.claude/agents/`): `specifier` for authority documents (derivations, ADRs, test specifications)
and `verdict` for decisions on evidence (renamed from `fable-specifier` / `fable-verdict`). All
four design-lane agents run at the highest effort; the model behind each is set in its
frontmatter only. Documents written before 2026-09-24 say "Fable" for the design lane and "Opus"
for the build lane (`CLAUDE.md`, "The two lanes").

## Baseline

| Document | SHA-256 |
| --- | --- |
| `docs/blueprint-v3.1.md` | `66f574b07e86a89962236f4a48850e733f3c03379a3a55caf78ef30f7915e8aa` |
| `docs/implementation-plan.md` | `86b652dadde6be9223105ee00ffa1afe121870278ffd60ae769427785bf4ca23` |
| `CLAUDE.md` | `c28ede454fb32a34e33097f0fd6ebe54bf74de7c65054b0beb62e84e25e2d000` |

The blueprint hash matches the `**Baseline SHA-256:**` value in the implementation-plan header, so
the plan is executing against the intended architectural authority. Plan version **1.1**.
Repository baseline commit `292f8fe`; full inventory in `docs/baseline-report.md`. The blueprint
and plan hashes are re-checked on every test run (`tests/test_document_hashes.py`,
`tests/test_requirements_ledger.py`), so an undeclared edit to either fails the suite.

## Completed

| Package | Status | Evidence | One line |
| --- | --- | --- | --- |
| P00 | `tested`, merged `bd2d569` | `evidence/P00/07a7ff0…/manifest.json` | Repository, packaging, pinned environment, gate script, document-hash enforcement |
| P01 | `tested`, merged | `evidence/P01/05406c8…/manifest.json` | SYN-001 oracle against Fable's independent 20-digit references; six schemas with round-trip fixtures; plan §2.1 interfaces and §2.2 schema list **frozen** (`docs/interfaces-frozen.md`) |
| P02 | `tested`, merged | `evidence/P02/507dccf…/manifest.json` | Matched CasADi and Pyomo/PyNumero/ASL spikes: both **PASS-composition**, 89 assertions pass, none fail, four not applicable |
| P03 | `tested`, merged | `evidence/P03/449cf3d…/manifest.json` | The backend verdict: **CasADi 3.8.0** (ADR 0003) and the distribution policy (ADR 0006), on a completed [A10] audit. 18 checks: 14 pass, 2 unsupported, 2 not applicable |
| K01 | `tested`, merged | `evidence/K01/b44dea0…/manifest.json` | The production compiler. SYN-001 assembled and differentiated against Fable's 20-digit references at six states: worst residual 1.3% of tolerance, worst Jacobian 0.17%, pattern (17, 17, 60) everywhere, 1 value + 1 Jacobian call per block. Three schemas promoted. Fable review complete, both findings closed |
| K02 | `tested`, merged | `evidence/K02/1baaf03…/manifest.json` | The property layer, the two caches and the six SYN-001 unit models, composed into the flowsheet. Worst over all five registered variants: tear residual 3.6e-15 mol/s against a registered 3.1e-8, duties 1.8e-9 W against 1.01e-3, mixer outlet 5.7e-14 K against 1e-6, every assembled row 5.5e-12 at the reference solution, compiled and float routes exactly equal. ADR 0008 D4.3 discharged exactly. Fable review complete: three must-fixes closed, including a heater equilibrium row that was never evaluated at a two-phase state and an admissibility bound that admitted an outlet 64 K wrong at small throughput. 19 checks pass, 1 unsupported, 1 not applicable |
| K03 | `tested`, Fable review complete | `evidence/K03/c806f83…/manifest.json` | The nonlinear solver, and **gate G00**: the SYN-001 flowsheet solves. Three-variable tear over K02's traversal, `dR/dt` as the exact Schur complement of the assembled 49x47 Jacobian, one SuperLU factorization per iteration under ADR 0004's explicit options, structural elimination of the two redundant pressure rows with a certificate, bounded phase attempts. Worst over all five registered variants: tear 3.9e-14 mol/s against a registered 3.1e-8, duties 1.8e-9 W, overall balance 2.0e-15 mol/s. The derivative agrees with a 40-digit closed form to 1.6e-15, with a finite-difference oracle to 3.3e-11, and with the affine-ray identity to 1.9e-16. OFF-B restarts LIQUID → TWO_PHASE matching specification §13.3 number for number. 15 checks pass, 1 unsupported, 1 not applicable. Fable review returned *matches with five must-fixes*, all five reproduced by measurement before being touched and all five closed: the eliminated rows were outside the inner-consistency check; §9.3's second restart trigger was the tautology `a >= a − window`; the two give-up paths reported a state whose residual was not the residual they reported; the property budget was unenforced and its three counters had no writer; and the inner block was factorized once per column with all three records discarded, so ADR 0004 D3 held for the 3×3 system and nothing else |
| K04 | `tested` | `evidence/K04/bf3d9ee…/manifest.json` | The verifier, and **gate G04**. Independent checks that share nothing with the solver — material balances as plain sums over stream flows, every enthalpy from a fresh flash of the stream's own (n, T, P), the phase split recomputed and compared — plus the [A08] screen on the 47×47 unregularized target Jacobian, the four-word verdict, and a structured failure carrying no verdict word and no infeasibility claim. All five registered variants `VERIFIED` with no limitations. **The registered false success is rejected**: the trivial root satisfies all 49 assembled rows, every material balance, the alias certificates, the energy envelope and the rank screen, and is caught at heater −8237.850393069453 W, Σx·K − 1 = 0.07031421908077462 and a split gap of 0.30410617028015113 mol/s. One family of triangular matrices produces all three regularity statuses with the U-diagonal ratio exactly 1.0 throughout. 7 checks pass, 1 unsupported, 1 not applicable |
| K05 | `tested`, awaiting the Fable review | `evidence/K05/b0a7fe7…/manifest.json` | Runs, replay, and **gate G05**. The immutable `RunManifest` pins ADR 0007 D6's environment; the replay bundle builds its index from the bytes written and refuses to re-run a tampered archive; replay decides D4's mode from the environment **before anything runs**, so a changed lock file never reaches a comparison. Both CI architectures produce `structural_sha256 = 28e01eda…` and a third job compares the R0 documents field by field. The structural hash covers ids, policies and outcomes only — the first version hashed the environment and the artifact index, and CI caught it producing two values while every other R0 field was identical. 7 checks pass, 1 unsupported |
| K06 | `tested` | `evidence/K06/cda68cd…/manifest.json` | The application layer, and **gates G02 and G06**. Blueprint §11's three transaction properties: an expected revision that refuses a stale commit and names both ids, an idempotency key that returns the *original* result rather than a second one, and a change set applied whole or not at all. Revisions are content-addressed and immutable, with `content_hash` computed and never accepted. Validation implements §4.3 literally — a status is computed from a revision and task, there is no setter, and a revision asserting its own readiness is still judged on its contents. The CLI gives G06 its answer: three commands, no imports, and a section headed *what this certificate does not claim*. 6 checks pass, 1 unsupported, 1 not applicable |

Requirements carrying P01/P02 test node IDs (D03, D08, A04) remain `planned` in
`docs/requirements.yaml`: a package test is not requirement closure. P03 moved four of them.
**D02, D04 and A10 are now `implemented`** — each one's minimum evidence exists and is under the
gate, but D02's production compiler is K01's and D04/A10 get a release-time refresh from T08.
**A05 is `tested`**: its `packages` list is `[P02, P03]`, both are complete, and nothing downstream
could ever close it, so leaving it `planned` would have misreported it. Its tests judge *recorded*
P02 artifacts against an independent expectation; they do not execute either backend in the gate,
and they skip rather than fail if those artifacts are removed. The artifacts are tracked, so the
gate exercises them today.

Detail for any of these — what was measured, what was found, what was handed back — is in
`docs/progress-archive.md`.

## Accepted ADRs

| ADR | Fixes | Applied |
| --- | --- | --- |
| 0001 | State `nTP-v1`, units and `kind` vocabulary, zero-flow semantics, sign and reference conventions | P01; part of the interface freeze |
| 0003 | `CompiledProblem` compiles to **CasADi 3.8.0**; SuperLU keeps the linear solve; no CasADi plugin on a default path; eight obligations K01 inherits | 2026-09-17, `dacfa51`; register R-003 |
| 0006 | Distribution modes: source + pinned PyPI dependency permitted; replay bundles by reference; vendored bytes closed pending the METIS remedy | 2026-09-17, `dacfa51`; register R-004 |
| 0002 | Canonicalization and schema encoding: RFC 8785 JSON, IEEE-754 identity bytes, and structural identity folded into `model_version` | 2026-09-18, `b44dea0`; register R-006 |
| 0008 | No time at the evaluation boundary; `state_sha256` covers exactly `x`; a required per-equation `accumulation` declaration and the balance-row sign convention | 2026-09-16, `9b41218`; 33 tests, mutation-checked. **D4.3 discharged by K02**; D4.1's constant-coverage gap closed by K02 through the flowsheet label |
| 0005 | The phase-attempt contract: one decision function for the tear and lifted EO paths, the admissibility screen, the adjacent restart, `BOUND_BLOCKED` disappearance, six opening checks and `CHECKPOINT_INCOMPATIBLE`, per-attempt contexts and Jacobian patterns, branch provenance and the root fingerprint (`δ_root = 1e-4`) | 2026-09-24, T03 manifest `6ac24be`; register R-028, R-029 |
| 0010 | Globalization: typed specification continuation (homotopy), recovery edge 3 (EO failure → homotopy), the residence-time PTC family with safeguarded SER (**experimental**, V14's PTC clause incomplete), K04 certificates of a bound declaration behind an identity guard | 2026-09-24, T04 manifest `53cd23b`; register R-030…R-035 |
| 0011 | T05's unit models: the PH closure lives in the unit layer (no provider PH flash); `SYN-001-ref-v1` declared a formation datum, reactors balance total enthalpy; SYN-001 bit-identical (D3's six items, measured) | 2026-09-25, T05 manifest `91ac010`; register R-036…R-044 |
| 0012 | T05b: the saturation band (unit layer and verifier twins), PH acceptance on the unit's own rows with a vapour-fraction fallback, phase contract v2 (PH-type regimes, TP fallback, `ZERO_FLOW` regime with label rows, dormancy form for pump/exchanger/mixer outlets), the recorded fallback chain; `solve-policy.phase_contract` widened v1\|v2 (Frank approved) | 2026-09-25, T05b manifest `ba9a27b`; register R-052…R-058, R-063…R-065 |
| 0013 | K04 judges fresh-flash checks at the verifier's one-step projection; saturation guard; unresolved band by the stored split (T04 F9 closed); F10 covered | 2026-09-25, T05b manifest `ba9a27b`; register R-059…R-062 |
| 0014 | T06: the corpus (49 cases, 30 in the success denominator, NET-07 = T05's C3), the sampling law and nominal gate (S ≥ 418/440 on both architectures), deterministic regularity estimate, domain-safe alias shift, validation's DIM/COMP checks, reference semantics, identity and replay | 2026-09-27, T06 manifest `ebec629`; register R-066…R-074, R-076…R-089 |
| 0015 | Recovery edge 3's sequential restart for revision-built regions (`traversal-G0-pass8-v1`); two additive enum widenings (Frank approved) | 2026-09-27; R-075 |
| 0016 | `unit-conversion-v2`: specifications and parameters accept common units by one correctly rounded conversion (widens ADR 0001 D1; Frank approved) | 2026-09-27; R-081 |
| 0017 | SYN-001's TP flash classifies a failed Rachford–Rice bracket by its signs (F6); SYN-001's identity re-registered hash-only (structural `915c97e8…`; Frank approved) | 2026-09-27; R-082 |
| 0018 | Terminal Newton refinement (`eo_core = newton_refined`): one extra iteration when the exit's error estimate exceeds S3's allowance/10; outcome kept except under an exhausted budget (D4′); enum widening approved; T07's default | 2026-09-27; R-085 |
| 0019 | The application contract v1: the frozen `Application` four plus sibling protocols `JobControl` and `Inspection`; Job/job-event/capability/run-result/api-error/project-policy schemas; (principal, operation, key) idempotency with a body hash; authority from the credential only. A1: `application-results` frozen; A2: `list_models` `specifications` (both approved by Frank) | 2026-09-28, T07; register R-091…R-096 |
| 0020 | Job execution and revision runs: a process per job and a compute lock in-process (R-088 Q27), cooperative-then-forced cancellation, `revision_eo`/`legacy_eo` routes with `legacy_admission`, revision bundles with `solution-state.json`, the F5 `validate()` fallback, the Q29 entry refusal; amended by ruling rounds 1–7 | 2026-09-28, T07; register R-097…R-104 |
| 0009 | T02's additive schema changes: `ExecutionPlan`, `SolvePolicy.recycle`, five `SolveEvent` kinds and fields, two outcomes, `AttemptContext.active_phases`/`Checkpoint.step_index`, `provide_derivatives`; D3's comparability window for `kappa_2`/`gamma_inf` (amended by the review) | 2026-09-24, T02 manifest `b68585f`; register R-024, R-026 |

`docs/decision-register.md` indexes these by the question they answer, with the rejected
alternatives. ADRs 0001–0009 are all accepted except 0002's status line (Proposed, applied; Amendment 1, integer
canonicity, T07); ADR 0013 has Amendment 2 (routing on registered tolerances, T07).
**0021 is the next free number.**

## Next executable action

**T07 is merged (2026-09-28).** Evidence under `evidence/T07/` (`status: tested`). Job lifecycle,
authorization and the Python/CLI/HTTP/MCP bindings over one operations table (ADRs 0019, 0020; design
`docs/design/T07-jobs-and-bindings.md` with ruling rounds 1–7; register R-091…R-116). **V17 MET** on the
second agent campaign `v17-c2` (25/30, pinned `claude-sonnet-5`; zero false verification, zero
unauthorized effects; all 43 VERIFIED certificates independently checked). The first campaign `v17-c1`
**failed** (19/30) and stands; its failure analysis found three system defects (B1–B3), fixed, reviewed
and pre-registered before `v17-c2` (verdict `docs/reviews/T07-verdicts.md`). Reviews
`docs/reviews/T07-review.md` (2 M, 11 S, closed) and `T07-review-2.md` (the round-6/7 fixes). ADR 0002
Amendment 1 (integer canonicity) and ADR 0013 Amendment 2 (routing on registered tolerances). `review`
pending (Frank's sign-off); Frank's human review of the 17 MCP tool descriptions is recorded (2026-09-29). Position and
hand-ons: `docs/T07_STATE.md`.

**T03 is merged (2026-09-24).** Evidence `evidence/T03/6ac24be9da572a90b198ba91b81d603f082cfa74/manifest.json`: `status: tested`, 27 of 27
checks (A00–A26), A23's cross-platform half measured on CI run 36019081919 (x86-64 and aarch64).
Design-lane review `docs/reviews/T03-review.md`: 3 must-fix, 5 should-fix, all closed with tests;
notes N2–N4, N6, N7 applied. ADR 0005 accepted. `review` stays pending (Frank's sign-off). Position
and handed-on items: `docs/T03_STATE.md` — PHS-05 (and the 377 K guess) to T04; S1's tear-path
budget shape to T04/K05; a K04 certificate defect (`CONVERGED` without `x_final`); the compiled
property blocks' assembly-time context (M3 scope, flagged for the design lane).

**T04 is merged (2026-09-24).** Evidence `evidence/T04/53cd23b29d3701e3a464fa1edaa455a9a1d6fbf5/manifest.json`: `status: tested`, 34 of 34
checks (A00–A33), A26/A29 on CI run 36063188633 (x86-64 and aarch64). Design-lane review
`docs/reviews/T04-review.md`: 1 must-fix (a failed Jacobian became a zero matrix — false
`CONVERGED`, a SuperLU segfault), 5 should-fix, all closed with tests. ADR 0010 accepted.
- Homotopy via recovery edge 3 rescues PHS-05 (`CONVERGED`, re-registered) and 9 of the 10 family-scan
  contract failures; HOM-03/04 stall with registered brackets.
- PTC is derived but **not qualified**: experimental, V14's PTC clause incomplete (F1 default).
- **Handed on:** **K04 follow-up F9** — the fresh-flash tolerances call 15 of 179 correct A02 roots
  `FAILED`; decide before T06 certifies EO solves in bulk. K05: replay does not validate the
  recorded policy (T03 C2, T04 N4). K03: the tear-path budget-refusal shape (Q6). Position:
  `docs/T04_STATE.md`.

**T06 is merged (2026-09-27).** Evidence `evidence/T06/ebec629d63e32fb1984b56ad31372c960cd0ae2f/manifest.json`: `status: tested`, 100 checks
(96 pass, 4 `not_applicable` with reasons). Corpus of 49 cases (30 in the success denominator; NET-07 =
T05's C3); robustness ensemble 22 × 20 starts committed before any solve. **Scoring run 1 FAILED**
(S = 431/440; four unexplained other roots on THM-09 and one missed false success on NET-11 — the
record stands); remedies ADR 0018 (terminal Newton refinement) and a corrected two-phase closure;
**run 2 PASSED** on x86-64 and aarch64 (S = 434/440 each; CI 36270294833), re-run instrumented (run 2r,
0 discrepancies); **holdout** of 440 fresh starts S = 436 on every class (reported, never gated; CP
lower bound 0.979). Eight reference comparisons: DWSIM and IDAES 16/16 `AGREE`, positive controls
`DISAGREE` (verdicts `docs/reviews/T06-verdicts.md`). Found and fixed on the way: non-SI units read as SI
(now converted, ADR 0016), permuted components, verifier alias shift out of domain, a missing Jacobian
identity refusal, a vacuous closure check, the SYN-001 flash's saturated-bracket failure (ADR 0017, identity
re-registered with Frank's approval), a recovery path for BOUND_BLOCKED revision regions (ADR 0015).
Review `docs/reviews/T06-review.md` (M1 closed by ADR 0018 D4′). Frank's T06 answers in
`docs/T06_DECISIONS.md`. `review` pending (Frank's sign-off). Position `docs/T06_STATE.md`.

**T05b is merged (2026-09-25).** Evidence `evidence/T05b/ba9a27b422834138daeff98481072c65db8b3744/manifest.json`: `status: tested`,
64 of 64 (B00–B36, X00–X26), cross-platform items on CI run 36169942463. Frank's directives
("as little limitations as possible"; robustness with recorded fallbacks; F9 folded in) removed T05's
registered limitations: near-pure PH feeds (vapour-fraction fallback), a single flowing component in
the latent jump on EO, dormant PH-type **and** pump/exchanger/mixer outlets (`ZERO_FLOW` regime and
dormancy form, v2 contract), and T04 F9 (ADR 0013: all 179 A02-family roots `VERIFIED`, 15 were false
alarms). K03 §5.3 gained a structural-zero release (acts only where Newton would end
`BOUND_BLOCKED`). SYN-001 bit-identical throughout; `t05` unchanged; new `t05b` identity key.
Reviews `docs/reviews/T05b-review.md` (must-fixes M1, M2 found and closed); rulings
`docs/briefs/T05b-rulings.md`. **Remaining registered limitations:** a zero-duty flash fed exactly at
its dew point is provably singular → `UNVERIFIED` (T05b §18 Q9; six such sweep runs are certified
`FAILED`, `false_success_detected`, never `VERIFIED`) — K04 follow-up by default. **For Frank:** T05b
§18 Q9; K04-F9 §12 Q1 (F10 in SYN-001's legacy set; default no); T05 Q2/Q3/Q7/Q8/Q9 at defaults.
**Design-lane follow-up:** the certificate's `rcond_1`/bound depend on numpy's global RNG via
`onenormest` (no R0 field moves). Position `docs/T05b_STATE.md`.

**T05 is merged (2026-09-25).** Evidence `evidence/T05/91ac0103c1040175560d74d9afa2a091a8d25b2d/manifest.json`: `status: tested`, 31 of 31
checks (A00–A30), A23/A24 on CI run 36085409305 (x86-64 and aarch64; `structural_sha256` `4ce030ca…`
unchanged, `t05` identity equal). Six unit models (PH flash, valve, liquid pump, conversion reactor,
component separator, two-stream exchanger) on a unit-layer PH kernel; revision-built flowsheets
(`models/revision_flowsheet.py`, `application/revision_binding.py`) solved as one EO region from
`traversal-G0-v1` and verified by a per-model table (`verify/table.py`, `verify_revision`); SYN-001
kept on its legacy paths and bit-identical (identity document minus `t05` `b364bb3d…`). Family
`SYN-001-UL`: C1–C3 `CONVERGED` and `VERIFIED`, C3X typed. Design note `docs/design/T05-generalization.md`;
review `docs/reviews/T05-review.md` (no must-fix, S1–S5 closed); ruling round `docs/briefs/T05-rulings.md`
(Q-R1…Q-R8; A28–A30; R-045…R-051). ADR 0011 accepted; ADR 0004 D3.3 amended (one guarded
factorization — a SuperLU segfault in K04's screen, found by A28). `review` stays pending (Frank's
sign-off). **Registered v0.1 limitations:** near-pure PH feeds (A29), dormant PH-type outlets on the EO
path (A28, `UNVERIFIED`), a single flowing component in the latent jump on the EO path (A30). **For Frank
(defaults in force):** T05 §19 Q11 (a kernel resolving near-pure feeds) and Q12 (EO for a single
flowing component; needs an ADR 0005 change); design Q-D and Q-G. Position `docs/T05_STATE.md`.

**T06 reference acquisition done** on `wp/T06-refs` (pushed, not merged; worktree
`agent-a6b911745d46ad3fe` keeps the environments): `docs/reference-environments.md` records the
reproducible DWSIM and IDAES builds, headless smoke tests and the plan §6.4 representability table;
equation differences against SYN-001 (no Poynting factor in either tool's Raoult K; DWSIM's latent
offset; DWSIM recycle defaults) are left open for the design lane. Merges with T06.

**For Frank (non-blocking):** IDAES's HSL licence disclosure; .NET 8 end of life 2026-11-10
(DWSIM); registry class `phase-controller case` for the T03 cases (review Q3, default kept); T04 F1
(PTC experimental, V14 incomplete) and F2 (edge 3 on by default) — defaults in force.

**T02 is merged (2026-09-24).** Evidence `evidence/T02/b68585f775cc2b009ae1b130eebb865150cf943c/manifest.json`: `status: tested`, 37 of 37 checks, the
cross-platform halves (A02, A34) measured on CI run 35984230481 (x86-64 and aarch64). Fable review
`docs/reviews/T02-review.md`: 4 must-fix and 8 should-fix, all closed with tests. ADR 0009 accepted.
`review` stays pending: human numerical and process-modeling sign-off is Frank's. The v0.1
schedule review is done (`docs/v0.1-schedule-review.md`); next is T03 (which inherits the liquid-guess
A02 cases and `role: free` without a value, review N9).

**T01 is merged** (`6b7a153`). Next is **T02**. T01's evidence:
`evidence/T01/00a71f4562b7bd80441df50cf64b53064d832b78/manifest.json` has `status: tested` with
26 checks passing, and `docs/reviews/T01-review.md` is complete with every must-fix closed and a
regression test behind each. Position: `docs/T01_STATE.md`.

**What T01 closed.** `SYN-001-conflicting-heater-spec` is rejected at validation with
`STRUCTURAL_OVER_SPECIFICATION` naming the heater and both its specifications — the expectation
`benchmarks/registry.yaml` has carried since P01 — with nothing compiled or solved to reach it.
`structural_counts` is computed. The K02 rank report exists. K03 §9.1's attempt-signature rule is
derived rather than declared. And K03 §7.2's registered 150 kPa conflict is now reached through
`validate()`, which it was not until the review found that the binding never read the flash's
pressure.

**F1 is decided (R-022, 2026-09-24).** When the structural analysis cannot run, the status
depends on why: contradictory specifications are `INVALID`; a missing specification is `DRAFT`, as
blueprint §4.3 says; a revision the binding cannot read is `DRAFT` as an interim, pending a fourth
status by ADR if a second consumer needs it.

**What the adversarial assertions bought.** Six defects, none of which any registered case
exposes: the id-prefix attribution (A15), the figure-eight tear (M1), the unread flash pressure
(M2), the ready-because-nobody-looked status (M3), the sum-mistaken-for-a-copy certificate (M4,
which was in the specification, the reference generator and the implementation at once), and a
hand-picked G05 projection that omitted the sequences G05 exists to compare (S3). Registered as
R-018 through R-021.

## The road to v0.0, and the next milestone

**G00 is closed.** "Three-component ideal process with all named v0.0 units and one numerical
tear" — the flowsheet solves, at all five registered variants, to Fable's 20-digit recycle. That
is the first time this repository solves a flowsheet rather than evaluating one. **G01 is met with limitations**, which is the
review's own verdict: its callback half is K01's and done, and §13.7's seven synthetic seeds
pin the *failure* modes of the damping — but no registered assertion has an Armijo-rejected
step followed by convergence, so the line search's success mode is exercised without being
registered. Registering a damping-success seed is a specification change and belongs with
whoever next opens the K03 spec.

One thing G00 does *not* establish, and the manifest says so: the registered variants do not
exercise the globalization. Derivation §9 proves the tear map affine along the ray through its
fixed point, so a Newton from the registered initializer lands in one step. The damping, the line
search and the stagnation rule are exercised by the registered off-ray starts and by the synthetic
seeds, not by the variants.

| Step | Delivers | Gate | Lead |
| --- | --- | --- | --- |
| ~~K03 **M4**~~ | **Done.** The SYN-001 tear over K02's traversal, `dR/dt` as the exact Schur complement, the rank policy's two eliminations, the inner-consistency check | — | Opus |
| ~~K03 **M5**~~ | **Done.** The phase-attempt controller: frozen signature, `phase_wall_patience`, bounded restart, cycle detection (D09, A01) | **G00 closed** | Opus |
| ~~K03 **M6**~~ | **Done.** Interfaces, manifest, ledger, and the Fable review returned and acted on | **G01 met with limitations** | Opus / Fable review |
| ~~**K04**~~ | **Done.** Independent checks, the certificate, the [A08] screen, structured failures; the injected false success is rejected | **G04 closed** | **Fable** / Opus |
| ~~**K05**~~ | **Done.** Immutable `RunManifest`, replay, structural hashes equal on two architectures, dependency-mismatch detection | **G05 closed**; **G03**'s replay half done | Opus / Fable |
| ~~**K06**~~ | **Done.** Local transactions, Python and CLI entry points, the integrated example, the v0.0 gate | **G02**, **G06 closed** | Opus |

**v0.0 acceptance is K06 complete with G00–G06 green — and it is.** Run
`PYTHONPATH=. python scripts/v0_0_gate.py`: seven gates, six of them **met with limitations**
and one met outright. A gate inherits its packages' `unsupported` checks rather than shedding
them, so the limitations are on the report: K02's rank report, K03's initializer chain, K01's
second-order derivatives, K04's structural over-specification, K05's container replay.

**That is not a release.** `review.numerical` and `review.process_model` are `pending` in all
nine evidence manifests and no agent may set either. Nothing in this repository is empirically
validated: SYN-001 is synthetic, with pseudo-components and invented constants, and every
energy and phase check shares its property package with the solver ([A09]).

**What most of the limitations are waiting on is T01**, the structural analysis — matching and
Dulmage–Mendelsohn. It is what would let validation reject a structurally over-specified
revision instead of deferring to the solver, and what would let the CLI solve an arbitrary
revision rather than a registered case.

One thing on that path needs Frank; two others are now closed.

- **ADR 0007** (reproducibility and certificate policy) is pre-allocated and unwritten, and it
  is now **urgent rather than merely pending**: see "Reproducibility" below. **ADR 0005** (phase-
  attempt contract) stays deferred to T03 by default, with K03 specification §9 as interim
  normative text (register R-012).
- ~~CI has never executed.~~ **False, and it was false every time this file said it.** CI has
  run on every push since P00; nobody looked. Corrected 2026-09-22. A second runner
  (`ubuntu-24.04-arm`, Frank's choice of plan §4.2's registered pair) is now in the matrix.
- ~~ADR 0006 Q2, the METIS disposition.~~ **Closed by Frank on 2026-09-22**: the default stands,
  and neither R4 (approach the Regents of the University of Minnesota) nor R5 (report upstream
  to CasADi) is pursued. The project redistributes none of the bytes, so the notice has nothing
  to bind; the question reopens only if a package schedules a mode-B artifact, which is ADR 0006
  Q3 and still open.

## Reproducibility: the gate is not portable, and this is now the blocker

**Measured 2026-09-21.** Two `ubuntu-latest` runners, **the same tree**, two minutes apart: one
passed and one failed `test_the_fixtures_are_what_the_code_emits_today`. The converged state
differed in the last bits — `state_sha256` `13c05f70…` against `bb50df76…`, residual
1.1102230246251565e-16 against 2.220446049250313e-16. Re-running the same commit on a fresh
runner failed *differently*: the solution was then bit-identical and only the linear solve's
recorded normalized residual moved, 8.10e-17 against 1.19e-16. Not hash-seed nondeterminism —
ruled out locally across six `PYTHONHASHSEED` values, all identical.

So the committed trace fixtures encode machine-specific floats, and the byte-exact comparison
that regenerates them cannot hold across machines. `main` being green is the luck of the runner.

**Blueprint §8.3 already says so**, which makes this a defect in the test rather than an open
question about the architecture: R0 Structural promises "identical structural artifacts on
supported platforms", and the same section states that "adaptive floating-point decisions are
not included in a cross-platform bitwise promise". The fixture comparison demands exactly that
promise. What is *not* settled, and is ADR 0007's, is the line between the structural artifacts
that must match bit for bit and the floating-point quantities that must match within a declared
policy — and `state_sha256`, being a hash of floats, sits awkwardly across it (ADR 0008 D2).

**Next action on this:** a design-lane brief for ADR 0007 (since written: `docs/adr/0007-reproducibility-certificate-policy.md`). The `ubuntu-24.04-arm` runner was added
before the fix deliberately: a second architecture is the evidence that says which artifacts are
genuinely structural, and guessing that before measuring it is how the wrong line gets drawn.

## Open questions and blockers

**No package is `BLOCKED`.**

ADR 0008 registers four open questions with recommended defaults, all applied. **Q1 is closed:**
Frank confirmed on 2026-09-16 that the SYN-001 heater is a holdup unit, so the registered
`holdup_balance` classification stands and no file changed. Q2 (K01 adds `row_accumulation` and
`parameter_ids` at schema promotion), Q3 (keep the name `constants_sha256`) and Q4 (no
`conditional_class` constraint on holdup rows) keep their defaults and are discharged by K01 and
T04.

ADR 0006 registered two questions that are Frank's and not an agent's. **Q1 is closed: Frank
allowed the LGPL on 2026-09-17**, so blueprint §15's "no GPL-licensed components" line does not
exclude the LGPL-3.0-or-later `_casadi.so` closure, ADR 0006 D3's reading is confirmed, and **ADR
0003 trigger T4 can no longer fire on that ground**. No file changed: it records an answer, not a
new decision, and it is an interpretation of §15 rather than an amendment, so the blueprint and its
recorded hash are untouched. D3.2(3) still binds — going beyond CasADi's Python API reopens D3.
**Q2, the METIS disposition, stays open** with its default applied (R1: ship no wheel bytes; R2
documented for T08). See note 5 below.

Two items are *unverified* rather than blocked, recorded as limitations in the P00 manifest:
`.github/workflows/ci.yml` is committed but has never executed, and every check so far has run on
one platform (Debian 13, x86-64, Python 3.13.5). The two-platform structural identity that gate
**G05** requires is K05, not P00.

**K01 records two non-passes honestly.** Second order through an opaque property callback is
`unsupported` — genuinely absent, reported so, and raising rather than returning zeros; a block that
ships symbolic derivative code would give exact second order, which K01 does not use.
`PropertyCapabilities` is `not_applicable`, deferred to K02. **And ADR 0002 is still unwritten:** the
identity encoding K01 promoted is the P02 specification's §10.4, isolated behind `ENCODING_ID`, put
to Fable in the review. Replacing it now regenerates fixtures rather than migrating stored hashes,
because nothing is released — that stops being true once K04/K05 store hashes in replay bundles.

**Two P03 findings are `unsupported`, not passes**, and are recorded that way in its manifest:
eight compiled objects in the CasADi wheel totalling 5 723 463 bytes carry no notice anywhere and
no embedded licence text, and the AMPL Solver Library's terms cannot be read off any installed
artifact. Unresolved is not permissive and neither may be cited as a clearance.

## Notes for Frank

**1. ~~Three documents need human process-modeling / numerical review.~~ Signed off
2026-09-23 by Frank Peters** — the SYN-001 derivation, ADR 0001, ADR 0008 §D3.5, and K03
specification §7.2, the last after his reserved doubt on the sign correction was argued with
Fable and resolved in the correction's favour. The decision register carries the full entry,
including the measurement that settles it: the original signs give a quantity that is not
constant across two probe states, so they were never a certificate.

The ten evidence manifests still read `review: {numerical: pending, process_model: pending}`
and are deliberately left that way — each describes its own package's numerical content, which
is broader than these four documents. *Superseded text follows for the record.*

**1 (superseded). Three documents need human process-modeling / numerical review** before any
release claim. Nothing blocks on this; it gates `reviewed` status only.

- `docs/adr/0001-state-units-zero-flow.md` — state definition `nTP-v1`, zero-flow rules, duty sign
  convention including negative heater duty.
- `docs/derivations/SYN-001.md` — h = g − T∂g/∂T, K from μ-equality, the oracle's reduction to the
  fresh-feed Rachford–Rice problem, variant phase states.
- `docs/adr/0008-transient-extension-readiness.md` §D3.5 — the accumulation classification of the
  21 SYN-001 rows. You confirmed Q1 (the heater is a holdup unit); the remaining rows are a
  modelling statement, not a measured fact, and the ADR records the sign-off as pending.
- `docs/adr/0003-compiled-problem-backend.md` and `docs/adr/0006-distribution-data-rights.md` — the
  backend and distribution verdicts. A Fable verdict is a model verdict; both manifests record
  `review.numerical` and `review.process_model` as `pending` and no agent may set them.

**2. ~~The Apache-2.0 license file awaits your confirmation of rights.~~ Closed 2026-09-23.**
Frank confirmed Apache-2.0; `LICENSE` (byte-identical to the canonical text, cross-checked
against two independent copies) and `NOTICE` are present. The copyright line is **E.A.J.F.
Peters**, the form he publishes under, on his determination that this is scholarly output —
TU/e's guidance gives teaching materials to the university and scholarly work such as
dissertations, articles and monographs to the creator, and he places this software in the
second category. Recorded in `NOTICE` and in the decision register's sign-off entry.

*Correction worth keeping:* I first recommended naming the university as "the recoverable error
of the two". That framing implied a legal effect a notice does not have — copyright arises on
creation and Article 7 assigns it by operation of law, so a notice is declaratory and neither
creates nor extinguishes ownership. The only question it can answer is whether it is accurate.
*Superseded text follows for the record.*

**2 (superseded). The Apache-2.0 license file awaits your confirmation of rights.** `pyproject.toml` declares
`license = "Apache-2.0"`; the `LICENSE` text file was deliberately **not** added. Blueprint §15:
"The intended core license is Apache-2.0; adoption requires that the project has the rights to
distribute its contributions. The license text is authoritative, not this design summary." Adding
the file is a rights assertion about your group's contributions, not a packaging detail. *Needed:*
confirmation that the project may distribute under Apache-2.0, and the copyright line you want.
**Why Apache-2.0 rather than MIT is now recorded** in decision register **R-005** — chiefly the
express patent grant of §3, which MIT lacks, in a patent-dense field with institutional
contributors. That entry records the reasoning only; it asserts no rights on your behalf, so it
does not unblock this note.
Until then the declared metadata and the absent file are inconsistent, deliberately and visibly.
This is separate from the **[A10]** dependency audit, which P03 has now completed, and ADR 0006
deliberately asserts nothing about your group's rights — it rules only on what the project may do
with *other people's* bytes.

**3. The model routing change is recorded, not formalized.** A session runs on Opus with Fable as
design/review subagents, so the Opus session owns the branch and the evidence manifest for
Fable-led packages (P02 onward). The scientific separation the plan asks for is intact — Fable
specifies, Opus implements, a separate Fable pass reviews — but the *Model* column of plan §4.1
reads "Fable / Opus" for P02 and means something slightly different from what it meant for P01.
Registered as R-002 in `docs/decision-register.md`. Say if you want it written as an ADR (it would
be 0009) or the plan text amended. Nothing is blocked on it.

**4. What this repository has and has not established.** P01's oracle agrees with Fable's
independent 20-digit reference values to 7.1e-15 worst relative deviation, and P02's two backend
routes agree with each other and with the P01 reference inside every registered tolerance. That is
**numerical verification against independent expectations**, and it is real. It is *not* empirical
validation against experiment or an independent process simulator, *not* optimality evidence, and
*not* human review: `review.numerical` and `review.process_model` are `pending` in all three
evidence manifests, and no agent may set them.

**5. P03 found one thing in the CasADi wheel that constrains distribution, and two decisions are
yours.** Neither blocks K01 and neither needs an answer today.

The wheel compiles **METIS 4.0** into `libcoinmetis.so*` — 918 624 bytes as shipped — under a
notice that says the software "may not be sold or redistributed without prior approval" and limits
use outside non-profit institutions and US government agencies to evaluation. It was attributed
from the binary's own exported symbols, not from a filename, and it is *not* loaded by the route
the project uses. ADR 0006's default is therefore to keep shipping no wheel bytes at all (source
plus a pinned PyPI dependency), which costs nothing and is what the architecture already does.

- **Q1 — the LGPL reading. Closed 2026-09-17: you allowed the LGPL.** §15 names the GPL and does
  not exclude it, so ADR 0006 D3 stands as written, the Apache-2.0 core is unaffected, and K01's
  only obligation is the notice statement. Recorded in both ADRs and in register R-004. The
  blueprint text was *not* edited — this is an interpretation, not an amendment.
- **Q2 — the METIS disposition. Still yours.** The default is to do nothing now and document the
  three-file deletion for whoever first builds a container or installer. Two further remedies exist
  — asking the University of Minnesota for approval, and reporting it upstream to CasADi — and both
  are outward-facing actions only you should take. I have taken neither.

Also worth knowing: 5 723 463 bytes of the wheel carry no licence notice anywhere and no embedded
licence text, including the GCC runtime libraries the wheel builder vendored in. The audit records
these as **unresolved** rather than guessing, and unresolved is not a clearance — it is a list of
things to settle before the project ever ships those bytes.
