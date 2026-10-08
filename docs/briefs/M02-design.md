# Brief — M02 design: the PyMRM execution adapter, experiment artifacts, frozen model versions and promotion

**To:** `architect`. **From:** the session (build lane), 2026-10-08. **Branch for the note:** `wp/M02` (from `wp/M01`).

**Plan row (v1.2 §4.4, binding):** *M02 — M01: execution adapter, experiment artifacts,
timeout/cache/noise controls, frozen model versions and promotion.*
- *Acceptance:* reproducible reactor result; failed experiment retained; model replacement diff and invalidation;
  incompatible pressure boundary rejected.
- Lane: Build / Design. Gate: **W21**, "PyMRM boundary/accuracy/execution and provenance" (M01 did the boundary half).
- `0.2.0a1` is proposed after M02 is `tested` (R-153).

## 1. The question

Write M02's design note, with work orders and verification gates, plus the ADR(s) any interface or schema change
needs, so that the build lane can implement six things:
- (a) the out-of-process adapter that runs the pinned group reactor behind M01's `ExternalEvaluation` seam;
- (b) the experiment artifacts: request, result and evidence records, with failed runs retained;
- (c) timeout, cache and noise controls;
- (d) frozen model versions during a solve, and promotion with invalidation;
- (e) the PR unit models M01 §7 specifies for `pr-c1-v1`;
- (f) the registration of the reactor (and the synthetic stand-in) as models a revision can bind.

The note must also say how M02 reproduces M01.A41–A48 *through the adapter*. That reproduction is the acceptance
condition of ADR 0027.

## 2. Why the architect

M02 fixes several things later packages inherit: how an expensive, external, separately-environmented model enters
the application layer (jobs, budgets, cancellation, replay); what an experiment record *is*; and what "promotion
invalidates runs and derivative evidence" means mechanically. M04's surrogates train on M02's experiment records,
M05 calls the true model through it, and M07's journey runs on it.

The plan's §2.2 schema list (ExperimentRequest/Result, ModelEvidence for M01–M04) is part of the frozen interface
set, so adding them is an ADR. The process boundary (subprocess within a job's worker process) touches ADR 0020's
cancellation and kill semantics.

## 3. Current state (facts from recon, 2026-10-08; anchors are on `main` unless marked `wp/M01`)

**M01's hand-off (`wp/M01`: `docs/derivations/M01-spec.md`, ADR 0027 Proposed, ADR 0026 Proposed).** M01's
Amendment 1 is running concurrently. Re-read the spec at the start and again before you finalise. Section and
assertion numbers may move slightly; the structure will not.

- **§7 — the PR units M02 builds.** Phase contract v2 for `pr-c1-v1` units, with regimes
  LIQUID–TWO_PHASE–VAPOR and ZERO_FLOW at each end. TWO_PHASE has one division-free equilibrium row
  `E = n_V,NH₃·φ^V − n_V,tot·φ^L = 0`. LIQUID is admissible only with no light gas. "M02 registers these as tests
  of its units."
- **§8.2 — reactor ports and DOF.** Ports `inlet`, `outlet` (vapour, nTP-v1, five components) and `duty`. The
  rows are:
  - `n_out − n_in − νξ = 0`, with ν = (−3, −1, 2, 0, 0);
  - `ξ − Ξ = 0`;
  - `T_out − Θ = 0`;
  - `P_out − P_in = 0`;
  - `Q − (Ḣ_out − Ḣ_in) = 0`.

  DOF 0. "How M02 embeds them (grey box, tear, surrogate) is M02's."
- **§8.3 — tube mapping.** F_ret_in = n_tot/N_tubes; p_ret_out = P_in; coolant pure N₂ at sweep_ratio × F_ret_in,
  1 bar; outlet = N_tubes × tube outlet.
- **§8.4 — nominal inlet.** F_ret_in = 0.007146961299302104 mol/s; y_in = (0.70, 0.235, 0.03, 0.015, 0.02) for
  (H₂, N₂, NH₃, Ar, CH₄); T_in = 673.15 K; P_in = 10⁷ Pa.
- **§8.5–8.6 — pinned-code issues and overlay.** F-R1: the pinned code hard-codes a 3-species backflow. The adapter
  sets the padded 5-species value after `_init_derived()`, and A44 proves it inert. F-R2: the kinetics use the
  reactive partial-pressure sum for fugacity. The overlay `benchmarks/m01/reactor-overlay.json` adds Ar and CH₄
  rows.
- **§8.7 — start strategy.**
  - S1: cold at y_NH₃ := 10⁻⁹, `DT_INIT_1D = 10⁻⁶`.
  - S2: warm at the true inlet from S1's fields.
  - S3: polish with Newton rtol 10⁻¹², atol 0.1 × target, dt_init 1, ≤ 400 steps, target 10⁻⁶ (num_z/100)².
  - Acceptance: S3 converged; KPI-drift certificate; u_ret > 0 on faces; positive flows; |ΔP|/P_in ≤ ε_P; element
    defect ≤ 10⁻⁶.
  - Otherwise `not_converged` with no outlet.
- **§8.8 — the pressure convention.** P_out = P_in; admissible iff |ΔP|/P_in ≤ 10⁻³, else
  `pressure_drop_exceeds_convention`. The spec names this as M02's "incompatible pressure boundary rejected".
  Measured 4.9 × 10⁻⁵.
- **§8.9–8.12 — outlet and result envelope.** ξ by least squares over H₂, N₂ and NH₃; refuse
  `element_balance_defect` above 10⁻⁶. Q computed via `pr-c1-v1`.
  - Envelope statuses: `ok`, `unsupported`, `out_of_domain`, `not_converged`, `error`.
  - `reactor_not_accepted(<stage>)` → `not_converged` ("M02 (real)").
  - Hard domain (T 573.15–773.15 K, P 5–15 MPa, H₂/N₂ ∈ [1, 4], inerts ≤ 0.2) → `out_of_domain`.
  - Data domain → `ok`, with `domain_status: extrapolated`.
- **§8.13 — the stand-in.** `c1.reactor_standin`, ξ = 0.25·n_N₂,in, synthetic.
- **§8.14 / ADR 0027 D8 — M02's share.** M02 owns: the adapter (environment from pins, the F-R1 subclass, S1–S3,
  timeouts, caching by exact inputs and configuration hash, failed runs retained, frozen versions, promotion), the
  PR units, and re-measuring §10.
- **§9.9 — A41–A48**, from `benchmarks/m01/reactor-probe.json` v2:
  - A41: start accepted at num_z = 800 for T_in ∈ {653.15, 673.15, 693.15} K.
  - A42: path independence 10⁻⁶ (measured 1.6 × 10⁻⁸).
  - A43: bitwise repeatability.
  - A44: backflow override inert.
  - A45: element defects ≤ 10⁻⁷.
  - A46: |ΔP|/P_in ≤ 10⁻³.
  - A47: M02's adapter reproduces the nominal outlet bitwise in the probe environment, and within the
    path-independence bound elsewhere.
  - A48: refinement record with grid sequence and order estimate.
- **§10 — grids.** num_z from 100 to 3200. Design grid 800, about 9 s per solve. The outlet converges at an order of
  only 0.6–0.8; at 800 the outlet NH₃ is about 1.0–1.4 % high.
- **Q-F4 — open.** Does the start strategy cover the hard domain's corners and centre? M02's adapter sweep answers
  it.
- **ADR 0027 acceptance.** M01 `tested`, and M02's adapter reproduces the probe's design-grid values.

**The seam, already in code (`wp/M01`: `src/openflowsheet/models/c1/boundary.py`).**

```python
@dataclass
class NotAccepted:
    stage: str  # :158

class ExternalEvaluation(Protocol):  # :164
    def __call__(self, tube: TubeInlet) -> TubeOutlet | NotAccepted: ...

@dataclass
class Boundary:  # :311
    provider: ...
    n_tubes: float
    identity: ...
    sweep_ratio: float = 1.0
    discretization_estimate: ...

    def evaluate(self, inlet, components, evaluation: ExternalEvaluation, context: EvaluationContext) -> ReactorResult: ...  # :325
```

- `tube_inlet(inlet, n_tubes, sweep_ratio=1.0) -> TubeInlet` (:125).
- `project(n_in, n_raw) -> Projection` (:185).
- `ReactorResult.as_document()` (:232).
- `refused(status, code, message)` (:249).
- Constants: `EPS_PRESSURE = 1e-3`, `DEFECT_LIMIT = 1e-6`.
- `models/c1/reactor_standin.py`: the `ReactorStandin` dataclass with `evaluate`, `ports`, `declared_equations` and
  `manifest()`. It is **not** in `MODEL_BUILDERS`.

**How the reactor is run today.**
- **The probe** (`wp/M01`: `benchmarks/m01/reactor_probe.py`, 553 lines):
  - its own venv (`pip install -e "<clone>[test]"`; pymrm 2.5.0, numpy 2.5.3, scipy 1.18.1, numba 0.68.0, Python
    3.13.5 — numpy and scipy differ from the project's pins, so the reactor must run out of process);
  - a `git archive` export of the clone at `6089593464fc9bc2c0a0cb58e30ad5433ece6332`, with a clean-clone check;
  - `OMP_NUM_THREADS=1` and its siblings;
  - `reactor_class(backflow)` subclasses the pinned 1D class (`reactor.paper.runner._one_d_class`);
  - `strategy(...)` implements S1–S3;
  - design point num_z = 800 accepted, 9.1 s, bitwise repeatable;
  - **no test reads `reactor-probe.json`.**
- **The T08 precedent** (`benchmarks/t08/v19/c1_reactor_run.py`): `_run_worker` calls
  `subprocess.run([sys.executable, __file__, "--worker", tree, case_id, json.dumps(jobs)], capture_output=True,
  text=True, env=_child_env())`. It has **no timeout**. Its worker refuses if the imported `reactor` package is not
  inside the export tree. Its record says `judged: False`.
- The reactor code is used **by reference, never vendored** (ADR 0022; ADR 0027 D5). Its licence is MIT.

**Jobs and execution (main).**
- `LocalApplication.submit_job` (`application/local.py:535`):
  - authorize `execute`, then canonical form, schema, ledger, admission;
  - accept (job, ledger and audit in one transaction), then run the executor;
  - the same key and request returns `replayed = true`.
- `ProcessExecutor` (`application/jobs/executor.py:238`): a fresh process per job (`worker.main`, `jobs/worker.py:69`);
  `max_workers = 1`; cancel waits `grace_s` then calls `Process.kill()`.
- `jobs/runner.py`: `execute(context, job, *, check, cancel, on_stage)` (:546); `_Body.solve()` (:363) and
  `reproduce()` (:488).
- Budgets: `Budgets.wall_time_s` (`types.py:544`); `max_property_calls` (`SolveBody`); `BudgetedProvider`
  (`orchestrator/budget.py:53`).
- ADR 0020:
  - D1: fresh process per job; an orphan ends `failed(owner_lost)`.
  - D3: cooperative checks; a forced kill after `grace_s`; an interrupted solve emits `partial_solve_trace`; wall
    time ends the job `timed_out`; the property budget gives `BUDGET_EXHAUSTED`; no resume in v0.1 (R-110).
- **No subprocess-based external-model call exists in `src/`.** A reactor subprocess would be a grandchild of the job
  worker and needs its own timeout and kill.

**Model identity and replacement (main).**
- `MODEL_BUILDERS` (`application/revision_binding.py:1103`) has 13 entries. Its `Builder` signature is at :111.
- `model_version = "<label>@<structure_sha256>"` (`canonical.py:496`).
- `schemas/model-manifest.schema.json` sets `additionalProperties: false` and requires `id`, `version`, `status`,
  `ports`, `mathematics`, `derivatives`, `initialization`, `validity`, `implementation_artifact` and
  `execution_requirements`. It has no `synthetic` field.
- A model swap shows only as changed `instances[i].model.{version, artifact_ref}` in `diff_revisions`
  (`transactions.py:162`). M06's Amendment 3 adds element-level `elements`.
- **No promotion, frozen-version or invalidation mechanism exists**, and no test exercises a model-version change.
- `RunManifest` (`run/manifest.py:221`) carries `model_version`, `constants_sha256`, `policy_id`, etc.
- The exact property cache `ExactPropertyCache` (`thermo/cache.py:123`, D10) keys on exact canonical inputs; warm
  starts are separate (ADR 0024).

**Schemas.** There are 35 schema files. None of them is for an experiment, model evidence, a study, a surrogate or an
optimization. `ExperimentRequest`, `ExperimentResult` and `ModelEvidence` appear only in plan §2.2 (L106),
`docs/interfaces-frozen.md:47` and `schemas/README.md:63` ("added when the object it describes is actually used").
M03 (on `wp/M03`) is adding a `study` schema only and leaves ExperimentRequest/Result to M04. Settle with that which
of these records M02 needs; M04 will consume them.

**Blueprint text (normative).**
- §5.1 L166, *experiment provider*: "a long-running PyMRM, Peclet, particle, or remote job that yields data and
  numerical evidence asynchronously. It does not run inside every Newton iteration by default."
- §5.2 L183: "External noise and incomplete inner solves set an accuracy floor. The orchestrator may tighten inner
  tolerances using a recorded forcing policy; it must not demand outer residual tolerances below achievable
  evaluation accuracy without reporting the conflict."
- §5.3 L185–189, *replacement contract*: check "ports, components, conserved quantities, reference states,
  boundary-condition meaning, degrees of freedom, derivatives, and validity. Matching the label 'reactor' is
  insufficient." Also: "Promotion creates a new revision and invalidates affected runs and derivative/optimization
  evidence. … During one solve attempt, all model versions are frozen."
- §7.7 L350: "External timeout or noise | Bounded retry or exact compatible cached result; report accuracy/budget
  limits."
- §8.3: reproducibility classes. R3, "recorded external", preserves inputs and artifacts but does not guarantee a
  rerun.
- §9.1 L401–405: PyMRM results "include boundary mapping, version, discretization settings, convergence evidence,
  conserved fluxes, and cost. … Failed experiments remain in the dataset with failure labels; they are not assigned
  fabricated outputs."
- §11.2 L455: "Retrying an idempotent request cannot duplicate an expensive experiment."
- §11.3 L473: "Out-of-process execution alone is not a sandbox; isolation profiles state their actual guarantees."
- §14.4 L588–593, v0.2: "PyMRM adapter with port mapping, accuracy contract, out-of-process execution policy,
  timeout, provenance, and parent-model validation."
- §15 L619: `src/adapters/` for PyMRM and experiments.

## 4. Constraints and invariants

- Existing identities do not move: SYN-001's structural hash, the K05 identity document and the T06 corpus values
  stay bit for bit; the v0.1 surface is unchanged except by ADR.
- Frozen interfaces and schemas (`docs/interfaces-frozen.md`) change only by ADR. Prefer additive widening; the
  application contract was just widened by ADR 0019 Amendment 3, and v0.2's working envelope is
  `v0.2-envelope-dev` (R-193).
- The project's default install gains no dependency on pymrm, numba or the group's code. The reactor runs in its own
  pinned environment, built from pins by a script, from a `git archive` of the pinned commit. It is never vendored,
  and its records carry rights and provenance.
- The default gate (`scripts/check.sh`, about 7300 tests, about 13 min) must not require the reactor environment.
  Reactor-dependent tests are opt-in, deselected rather than skipped, as M03 does for `nlp`; the committed records
  are checked in the default gate.
- Exact caches key on exact canonical inputs; never quantize the state on the exact path. Residual and Jacobian
  describe the same function.
- No placeholder success: every failure is a typed result with no fabricated outlet, and failed experiments are
  retained.
- One design grid solve is about 9 s; a job's wall-time budget, cancellation and kill must reach the grandchild
  process.

## 5. Already decided — do not reopen

- Chemistry C1, the reactor pin `6089593`, K_NH₃ from the code (R-120, R-143, R-152).
- M01's boundary semantics and numbers: ADR 0027 D1–D9, as Amendment 1 leaves them.
  - D1: ports, DOF and N_tubes.
  - D2: zero ΔP, with ε_P = 10⁻³.
  - D3: extent projection.
  - D4: process-side duty.
  - D5: five species by reference, through the F-R1 subclass.
  - D6: start strategy S1/S2/S3.
  - D7: design grid num_z = 800.
  - D9: data domain flagged, not refused.
- The reactor keeps its own kinetics and thermodynamics; the PR route is process-side only.
- The job model: a fresh worker process per job, cooperative cancel then kill, no resume (ADR 0020, R-110).
- Order R-153. M02 `tested` triggers the proposal of `0.2.0a1`, which goes through `release.yml` with Frank's
  dispatch; it needs a v0.2 gate of its own (R-153's watch-for).
- Frank's M01 defaults stand until he answers (Q-F1 inlet heat loss as pinned; Q-N2 keep `6089593` plus the
  subclass and overlay; Q-N3 num_z = 800).

## 6. Genuinely open — decide these

1. **Where the reactor runs.** Inside the job worker, as a grandchild subprocess; or as a separately managed
   experiment job. What the timeout, cancel and kill chain is, and the isolation profile it states (§11.3).
2. **How the reactor enters a flowsheet.**
   - As a unit bound in a revision via `MODEL_BUILDERS` (it is evaluated per call, so not in every Newton iteration
     by default, §5.1), as an experiment-provider step, or both.
   - What a flowsheet solve does with a 9 s, derivative-free external evaluation: a tear on the reactor, an
     extent-fixed embedding, or a surrogate later (M04).
   - What M02 must deliver for M07's loop, and what is left to M04/M05.
3. **The experiment records:** request, result and evidence, with failure labels. Their identity (exact inputs plus
   configuration hash plus environment fingerprint), the exact cache over them, retry and idempotency (§11.2), and
   noise and the accuracy floor (§5.2: the reactor's path-independence bound and the discretization estimate).
4. **Frozen model versions during a solve attempt, and promotion.** What a promotion is (a new revision), what it
   invalidates (runs, derivative and optimization evidence — including M03's sensitivity results, `wp/M03`), how
   the invalidation is recorded and surfaced (`diff_revisions` with M06's `elements`), and the §5.3 replacement
   compatibility check.
5. **Reproducibility class and replay.** R3, "recorded external", versus a rerun in the pinned environment. What a
   replay bundle holds for a reactor-backed run, given that ADR 0024 D5 replays from the bundle alone.
6. **The PR units of M01 §7:** which unit models (separator flash, mixer, heater, …) at a minimum for the C1 loop,
   their registration, and the tests M01 §7 asks M02 to register.
7. **Schema changes, ADR shape and the frozen list:** what M02 adds now and what waits for M04.
8. **How A41–A48 and Q-F4 are re-measured through the adapter,** and what is gated in CI versus run opt-in.
9. **The v0.2 gate needed for `0.2.0a1`:** which W rows apply at M02, without relaxing the v0.1 gate.

## 7. Already tried, measured or rejected

- **The group's default tolerance (residual 1e-3)** leaves 0.45 % path dependence in the outlet; the S3 polish brings
  it to 1.6e-8. Do not accept states at the group tolerance.
- **num_z = 100 (the group's publication grid)** is about 5.5 % high in outlet NH₃. Above 800, the pinned solver's
  state is not accepted.
- **Cold start at the true inlet** fails at 623–673 K and 80–100 bar for every dt_init tried. S1→S2→S3 works at
  653–693 K and 10⁷ Pa; coverage elsewhere is not established (Q-F4).
- **Pyomo/PyNumero as the compile backend** was rejected (R-003); the reactor is not compiled into CasADi.
- **CasADi's bundled Ipopt must never be loaded** (ADR 0006 D1.5). Irrelevant here unless the design touches
  optimization.

## 8. How the answer will be verified

- The gate `./scripts/check.sh`.
- The M01 assertions A41–A48 and the §7 unit tests, reproduced through the adapter.
- The plan's four acceptance items: a reproducible reactor result; a failed experiment retained; a model replacement
  diff with invalidation; an incompatible pressure boundary rejected.
- W21, judged later by a `verdict` agent from your gate table.
- One `reviewer` pass on the finished build, against your note.

## 9. Deliverable

On `wp/M02` (create it from `wp/M01`'s tip):
- `docs/design/M02-pymrm-adapter.md`, with these sections: decisions at a glance; architecture; records and schemas;
  freezing and promotion; failure, timeout, cache and noise; replay; PR units; work orders in dependency order,
  marked Opus or bounded, each with acceptance; verification gates G1…Gn, each decidable from a recorded number;
  risks; and what M02 does not establish.
- ADR(s) under `docs/adr/`: ADR 0033 onward. 0026/0027 are M01's, 0030 M06's, 0031/0032 M03's.
- Decision-register entries R-220 onward (lower numbers are held by M01, M03 and M06).
- A "Needs Frank" section, each item with a default.

Commit. Write no production code.

## 10. Out of scope

Surrogates and conformal UQ (M04); trust-region and optimization over the reactor (M05); the M07 journey; changing
the reactor's own physics, F-R3 (the inlet heat loss) or the pin; the web shell; the W27 campaign.
