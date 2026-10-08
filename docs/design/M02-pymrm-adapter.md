# M02 — The PyMRM execution adapter, experiment records, frozen model versions and promotion, and the PR units: design note

**Status:** Proposed, design lane (`architect`), 2026-10-08, on `wp/M02`; ruling rounds §14 (2026-10-08), §14.1
(2026-10-08) and §14.2 (2026-10-09, WO-8); written against M01 Amendment 1
(`1e8aecd`) and checked against `wp/M01` @ `4142471` (WO-7/WO-8: the stage grammar and check order as Amendment 1
states; M01.A49's binder clause, which this note supersedes in G8 (e)). **Brief:** `docs/briefs/M02-design.md`. **Plan row (v1.2 §4.4, binding):** M02 — execution adapter,
experiment artifacts, timeout/cache/noise controls, frozen model versions and promotion; acceptance: reproducible
reactor result, failed experiment retained, model replacement diff and invalidation, incompatible pressure boundary
rejected; lanes Build / Design; gate W21 (M02's half). **Decisions:** ADR 0033 (external-model execution and
experiment records), ADR 0034 (external models in a flowsheet solve), ADR 0035 (model replacement and promotion);
register R-220 to R-233. **Inherits:** M01 spec §7, §8 (incl. §8.14–§8.15), §9.9, §10, Q-F4, Q-F5; ADR 0026, ADR 0027
with Amendment 1; ADR 0019, 0020, 0024, 0007.

Everything a work order needs is in this note. Where it says "as SYN-001's X does", the implementer follows that
existing pattern; where a number appears, it is registered here and nowhere else.

---

## 0. Decisions at a glance

| # | Question | Decision | Rejected alternative (and why) | Where |
| --- | --- | --- | --- | --- |
| D1 | Where the reactor runs | A **fresh grandchild subprocess per experiment attempt**, started synchronously by the job worker, in a pinned venv built from a hash-pinned lock and a `git archive` export | A separately managed experiment job (needs job-to-job scheduling, deadlocks at `max_workers = 1`, and still needs a grandchild because the reactor's numpy/scipy pins differ from ours); a persistent per-job child (state carried between experiments, harder kill semantics; revisit only on measured start-up cost, R-224); in-process import (pin conflict, a native crash kills the worker) | ADR 0033 D1, §2 |
| D2 | Kill chain and isolation | Three layers: adapter-owned cooperative/timeout kill (SIGTERM, 2 s, SIGKILL); **executor forced kill becomes a process-group kill** (the worker makes itself group leader; amends ADR 0020 D3); child lifeline (stdin EOF) and self-deadline. Profile `external-subprocess-v1`, stated as *not a sandbox*. Linux registered, macOS best effort, Windows refused | Kill by pid only (orphans the grandchild on a forced kill); `PR_SET_PDEATHSIG` alone (Linux-only, thread-scoped); a job-per-experiment scheduler (D1) | ADR 0033 D2, §2.3 |
| D3 | Experiment identity | **Process-level**: SHA-256 of {model id, variant id and variant SHA-256, provider identity, N_tubes, sweep ratio, components, exact binary64 n, T, P, environment fingerprint SHA-256}. Never quantized | Tube-level key (would share entries across (k n, k N_tubes) but puts the boundary's provider calls outside the identity and splits one consumer-visible fact over two records) | ADR 0033 D4, §3.2 |
| D4 | Records | One schema file `experiment.schema.json`: `request`, `result`, `attempt`, `coupling`. Every request that reaches the runner is retained: a deterministic outcome is a write-once `result`; every execution is an `attempt`. No fabricated outputs | Records only for `ok` (violates blueprint §9.1); mutable result files | ADR 0033 D5, §3 |
| D5 | Cache | Exact, per project, keyed by D3; serves **deterministic outcomes only** (every boundary status incl. refusals and `not_converged`), never a transient failure; a per-key `flock` makes a duplicate execution impossible within a project; cache bypass is a measurement mode whose repeat is compared bitwise (a determinism monitor) | Caching only `ok` (re-runs known refusals at 25–45 s each, §14 B6); caching timeouts (a machine-load fact, not an input fact); a global lock (serializes unrelated experiments) | ADR 0033 D6, §5.3 |
| D6 | Retry and timeout | Bounded, transient-only: one retry after `crashed`, `protocol_error`, `spawn_failed`; none after `timed_out`, `environment_*`, `cancelled`. Per-attempt timeout 120 s (2.7 × the slowest measured evaluation, 44.9 s; §14 B6), re-registered from the Q-F4/Q-F5 sweep | Retrying timeouts (doubles a known-expensive cost silently); unbounded retry | ADR 0033 D7, §5.2 |
| D7 | Noise and accuracy | Each variant declares its accuracy contract: precision floor ε_eval = 10⁻⁶ relative (the registered path-independence bound; measured 1.6 × 10⁻⁸) and the design grid's discretization estimate (DX-01). Every result carries both. Cold S1–S3 only: **no warm start of the reactor**, so a result is a function of its request | Warm-starting S2 from a neighbour's fields (makes a result depend on history at the 10⁻⁸ level, which an exact cache cannot key; revisit on measured cost, R-224) | ADR 0033 D8, §5.4 |
| D8 | How the reactor enters a flowsheet | **Extent-fixed embedding with an outer coupling.** The unit's compiled rows take the conversion X̂ and temperature rise ΔT̂ as pinned parameters (rows exist: `extent_row`, `offset_row`); the existing revision EO solve runs unchanged; an outer Broyden iteration on w = (X̂, ΔT̂) evaluates the reactor once per iteration at the inner solution's reactor inlet. Converged iff \|ξ_E − X̂ n_N₂,in\| ≤ 10⁻⁵ n_tot,in and \|T_E − T_in − ΔT̂\| ≤ 10⁻² K. Route `revision_coupled` | The reactor inside Newton with a finite-difference Jacobian (8 × 25–45 s per Jacobian, FD is a test oracle by plan §4.2, noise/h); a tear on the full reactor inlet (7 coordinates instead of 2); the SYN-001 tear path (refuses revision flowsheets, R-045); leaving the loop to the agent or to M05 (truth checks and frozen versions need it now) | ADR 0034 D1–D4, §4 |
| D9 | Frozen versions | A revision pins an external model by **variant id and variant SHA-256** (`model.version`, `model.artifact_ref`), enforced by the binder; variants are immutable, append-only package data with a pinned registry; the environment fingerprint is established once per attempt (handshake) and every experiment in the attempt must report it | Trusting `model.version` strings (today nothing checks them); re-reading the environment per call without freezing | ADR 0034 D5, ADR 0035 D1, §6.1 |
| D10 | Promotion | **A commit that changes an instance's model reference is a promotion**: checked against blueprint §5.3's facets whenever the old or new model is variant-backed; rejected `model_replacement_incompatible` with the report; on success the report is an artifact hashed into the new revision's provenance; invalidation is the existing `invalidations` (runs of the expected revision), generalized to every evidence-producing operation; experiment records are never invalidated | A separate `promote_model` method (bypassable through `commit_change`, more contract); flagging old records as invalidated (evidence is immutable) | ADR 0035, §6 |
| D11 | Reproducibility class | A coupled run that used an out-of-process variant is **R3**; its bundle gains `external-coupling.json`, which embeds every request, result and variant used; `reproduce` replays **from the record** (the external results substituted after the recomputed requests are checked) and says so in `reasons`; an in-process variant (the stand-in) is re-evaluated on replay and compared. A live rerun in the pinned environment is an evidence script, never the default | Rerunning the reactor on replay (not possible "from the bundle alone", ADR 0024 D5; needs the environment) | ADR 0034 D6, §7 |
| D12 | Standalone experiments | Job operation `experiment` (one request per job), right `execute`; batch sampling is M04's | Only experiments inside solves (M04 would have no producer) | ADR 0033 D9, §3.5 |
| D13 | PR units | `c1.feed_source`, `c1.product_sink`, `c1.stream_splitter`, `c1.adiabatic_mixer` (vapour outlet), `c1.tp_heater` (vapour outlet), `c1.tp_flash` (§7 split: VAPOR / TWO_PHASE / ZERO_FLOW, the NH₃ equilibrium row in R-008's form); a feed with no light gas is refused typed (LIQUID regime deferred); dew-band tolerance τ_dew = 10⁻¹⁰ n_tot | A general two-phase heater and mixer (the C1 loop never needs them; one split unit is the risk worth carrying); the full pure-NH₃ LIQUID/saturation route now (needs ADR 0012's band route for a case the loop never visits) | R-230, §8 |
| D14 | Binding | C1 revisions bind on `pr-c1-v1` when `component_set.record_source` names the C1 records; every other revision binds exactly as today. `c1.reactor` **and** `c1.reactor_standin` enter `MODEL_BUILDERS`; the stand-in is listed synthetic (supersedes M01.A49's binder clause, as R-199 allows) | Not binding the stand-in (the default gate would have no coupled-route coverage without PyMRM) | ADR 0034 D8–D9, R-231 |
| D15 | Q-F5 | The real variant's hard domain gains the per-tube flow bound F_ret_in ∈ [0.5, 2] × 0.007146961299302104 mol/s (Amendment 1's default), as a variant field the `Boundary` reads; the stand-in is unaffected; widened only on measured acceptance | A module-level bound (would refuse M01's registered stand-in states, whose per-tube flow is 140 × nominal) | ADR 0034 D10, R-232 |
| D16 | v0.2 gate for `0.2.0a1` | `v0.2-alpha-gate-v1`: the v0.1 release gate unchanged, plus W21 and W22 judged `met`; the alpha claims nothing of W23–W27 beyond verdicts already `met` | — (a value judgement: Needs Frank, §12) | §10.4 |

---

## 1. Problem and scope

M02 makes the group's 1D ammonia reactor (pin `6089593`, M01 §8) an **external model** that the application can
(a) evaluate as a recorded experiment, (b) embed in a flowsheet solve without putting a 25–45 s, derivative-free call
inside Newton, (c) freeze and replace under rules, and (d) replay. It also delivers the Peng–Robinson unit models of
M01 §7 so that a C1 ammonia loop can be bound and solved at all.

**In scope.** The adapter (environment builder, child runner, launcher, kill chain); variants (frozen external-model
identities); experiment request/result/attempt records, the exact cache, retry, timeouts; the `experiment` job
operation; the extent-fixed embedding and the outer coupling route; frozen identities per attempt; the replacement
check and promotion; R3 replay; the C1 binding and the PR units; the C1 loop test case; re-measurement of M01.A41–A48
(adapter halves), Q-F4 and Q-F5 through the adapter; the v0.2 alpha gate proposal.

**Out of scope.** Surrogates, conformal UQ, `ModelEvidence` and `SurrogateManifest` (M04); trust-region and
optimization over the reactor, sensitivities through it (M05); the M07 journey and its loop design; the reactor's
physics, F-R3 and the pin; the web shell; W27. Also explicitly not done here: warm-starting the reactor, a persistent
reactor server, the PR LIQUID regime and pure-NH₃ saturation route, Windows support for external execution,
cross-host experiment sharing.

---

## 2. Architecture

### 2.1 Layers and where each concern lives

```
  application  ── job body `experiment`  ── job body `solve` (route revision_coupled)
                         │                           │
                         │                 orchestrator/coupling.py  (outer Broyden on w; §4)
                         │                           │  one request per external unit per iteration
                         ▼                           ▼
  adapters/experiments/runner.py   ExperimentRunner: request → key → flock → cache? → evaluate → records
                         │
                         ▼
  models/c1/boundary.py  Boundary.evaluate  (M01: checks 1–5, then the evaluation, then 7–10)
                         │  ExternalEvaluation(tube) -> TubeOutlet | NotAccepted | ExecutionFailure
          ┌──────────────┴──────────────┐
  InProcessBackend (stand-in)    OutOfProcessBackend ── adapters/external/launcher.py ── child process
                                                         (pinned venv)  adapters/pymrm/child.py
```

- **The process boundary is the evaluation seam M01 built** (`ExternalEvaluation`, boundary.py:164). The child
  receives one `TubeInlet` and returns one raw `TubeOutlet` or `NotAccepted(stage)`. Everything process-side —
  mapping, checks, projection, Q by `pr-c1-v1`, the envelope — stays in the worker, in the project's environment.
- **The experiment is the boundary evaluation of one process inlet** (D3): its record holds the request, the boundary
  envelope (`ReactorResult.as_document()`), and the tube-level exchange as evidence.
- **The flowsheet never calls the reactor.** The compiled unit is analytic (pinned X̂, ΔT̂); only the coupling
  driver calls the runner (§4).

### 2.2 Module layout (blueprint §15: `adapters/` for PyMRM and experiments)

| Module | Content | Runs in |
| --- | --- | --- |
| `src/openflowsheet/adapters/variants.py` + `adapters/variants/*.json` + `adapters/variants/registry.json` | variant documents, loader, SHA-256 pinning | worker |
| `src/openflowsheet/adapters/external/launcher.py` | spawn, scrubbed environment, lifeline, timeout, kill escalation, reap, protocol validation, logs | worker |
| `src/openflowsheet/adapters/external/protocol.py` | protocol version, exit codes, file names (mirrored as literals in the child; a test asserts equality) | worker |
| `src/openflowsheet/adapters/experiments/{request,store,runner,backends}.py` | request and key, store (files + artifact rows + per-key flock), runner (cache, retry, records), backends | worker |
| `src/openflowsheet/adapters/pymrm/child.py` | the reactor runner: imports **only** stdlib, numpy, scipy, pymrm and the pinned `reactor` package; F-R1 subclass; S1–S3; acceptance; fingerprint; handshake | reactor venv |
| `src/openflowsheet/adapters/pymrm/env.py` (+ `reactor-env.lock`) | `python -m openflowsheet.adapters.pymrm.env build|verify` | developer machine |
| `src/openflowsheet/models/c1/reactor.py` | `C1Reactor`, the embedded unit (both model ids) | worker |
| `src/openflowsheet/models/c1/units/` and `models/c1/blocks.py` | the PR units and their `PropertyBlock`s over `pr-c1-v1` | worker |
| `src/openflowsheet/orchestrator/coupling.py` | the outer coupling driver and its record | worker |
| `src/openflowsheet/application/replacement.py` | the §5.3 replacement check | server |
| `tests/support/synthetic_child.py` | a test child with failure hooks, run by the project's own interpreter | tests only |

`child.py` ships in the wheel but no module of `openflowsheet` imports it; a static test (AST scan) asserts that, and
that `child.py` imports nothing outside {stdlib, numpy, scipy, pymrm, reactor}. The project's runtime dependencies do
not change (M01.A35 holds).

### 2.3 The process boundary and the kill chain (D1, D2)

**One experiment attempt = one child process.**

1. **Spawn.** `subprocess.Popen([env_python, "-I", child_path], stdin=PIPE, stdout=<attempt>/child.stdout,
   stderr=<attempt>/child.stderr, cwd=<attempt dir>, env=<scrubbed>, close_fds=True)`. `-I` (isolated mode) ignores
   `PYTHONPATH`, user site and the script's directory, so nothing from this repository leaks into the child; the
   child inserts the export directory itself and verifies `reactor.__file__` lies inside it (the T08 precedent).
   Logs go to files, never to pipes (no pipe-buffer deadlock). The child stays in the **worker's process group**
   (no `start_new_session`).
2. **Scrubbed environment** (an allowlist, not inheritance): `PATH=/usr/bin:/bin`, `LANG=C.UTF-8`, `HOME=<attempt
   dir>`, `TMPDIR=<attempt dir>`, `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=
   NUMBA_NUM_THREADS=1`, `NUMBA_CACHE_DIR=<env root>/numba-cache`, `OFS_PROTOCOL=1`. Every value is recorded in the
   fingerprint. A user's `NUMBA_*`, `OMP_*` or `PYTHON*` never reaches the child.
3. **Request.** The adapter writes one JSON line to stdin — `{protocol: 1, request_sha256, tube_inlet, configuration,
   deadline_s, expected: {commit, export_tree_sha256, lock_sha256, merged_database_sha256, runner_sha256}}` — and
   **keeps stdin open** for the whole attempt: it is the lifeline. Floats are written with `repr` (exact round trip);
   non-finite numbers are refused before spawn.
4. **Child.** Reads the line; starts a lifeline thread that blocks on `stdin.read()` and calls `os._exit(70)` on EOF,
   and calls `os._exit(71)` when `deadline_s + 30` s have passed since start (`threading.Timer`); verifies the
   environment (exit 72 on mismatch, with a one-line reason on stderr); computes; writes `result.json` atomically
   (write `result.json.tmp`, `fsync`, `rename`); exits 0. `result.json` = `{protocol: 1, request_sha256, fingerprint,
   outcome: "outlet" | "not_accepted", tube_outlet | stage, diagnostics, timing: {startup_s, solve_s}}`.
5. **Wait.** The adapter polls `Popen.wait(timeout=0.2)` in a loop. Between polls it calls the job's cooperative
   check (the `INTERRUPT_CHECK` ContextVar of ADR 0020 D3) and its own attempt deadline (`timeout_s`).
6. **Termination (layer L1, adapter-owned).** On a cooperative interrupt or a timeout: `SIGTERM` to the child,
   wait 2.0 s (`kill_grace_s`), `SIGKILL`, `wait()` (reap). The attempt record is written (`cancelled` or
   `timed_out`), then the interrupt is re-raised (cooperative) or an `ExecutionFailure("timed_out")` returned.
7. **Forced kill (layer L2, executor-owned).** `worker.main` calls `os.setpgid(0, 0)` as its first statement, so the
   worker leads its own process group and every child it spawns is in it. The supervisor's forced kill
   (`executor.py:360` and `:512`, today `slot.process.kill()`) becomes `_kill_tree(slot.process)`: if
   `process.is_alive()`, `os.killpg(process.pid, SIGKILL)`, falling back to `process.kill()` on `ProcessLookupError`
   or a non-POSIX platform. The pid cannot be reused while the worker is unreaped, so the group id is valid. This is
   ADR 0020 D3's "kill", widened from the worker to the worker's process group (ADR 0033 D2).
8. **Parent death (layer L3, child-owned).** If the worker dies by any other means (OOM killer, a `kill -9` of the
   worker pid alone, `owner_lost`), the kernel closes the stdin pipe and the lifeline exits the child; the
   self-deadline is the backstop if the pipe were somehow held open.
9. **Exit mapping.** Exit 0 with a valid `result.json` whose `request_sha256` matches → `TubeOutlet` or
   `NotAccepted(stage)`. Exit 0 without a valid file, or with a mismatched hash → `protocol_error`. Exit 70/71 →
   `lifeline_lost` / `self_deadline` (only seen when the adapter itself survived, i.e. never in practice; recorded as
   `protocol_error`). Exit 72 → `environment_mismatch`. A signal or any other code → `crashed` (the code recorded).
   `FileNotFoundError`/`PermissionError` on spawn → `spawn_failed`. The environment directory absent →
   `environment_unavailable` (no spawn).

**Isolation profile `external-subprocess-v1`** (blueprint §11.3: profiles state their actual guarantees). *Provides:*
a separate interpreter and dependency set built from a hash-pinned lock; a separate address space (a native crash
becomes a typed `crashed`); an environment allowlist; a private working directory per attempt; one thread; a wall-clock
limit with TERM→KILL escalation; termination on cooperative cancel, on a forced kill of the worker, and on the worker's
death; output read only from one validated file; code identity verified (commit, export tree, runner, lock, merged
database). *Does not provide:* filesystem confinement (the child runs as the user and can read and write what the user
can), network isolation, memory or CPU quotas beyond the thread pin, syscall filtering, or any protection against
malicious code in the pinned repository — trust rests on provenance (a pinned commit of a named group's MIT
repository), not on confinement. **It is not a sandbox.** *Platforms:* Linux registered (the two CI architectures of
ADR 0007 D3.3); macOS best effort (same mechanisms; CPU model from `sysctl`); Windows refused before spawn,
`environment_unavailable`, message `external_execution_unsupported_platform`.

### 2.4 The reactor environment (built from pins, never vendored)

`python -m openflowsheet.adapters.pymrm.env build --variant pymrm-6089593-g2-nz800-s123-v1 [--source <clone>]`:

1. Clone or fetch the group's repository (URL in the variant) into a scratch directory, or use `--source`; check out
   `6089593464fc9bc2c0a0cb58e30ad5433ece6332`; refuse unless `git status --porcelain` is empty and `HEAD` equals the
   pin (the probe's clean-clone check).
2. `git archive` the commit into `<env root>/<env id>/export/`; compute `export_tree_sha256` = SHA-256 of the
   canonical JSON list of `[relative path, file SHA-256]` sorted by path; write it to `export/EXPORT_TREE_SHA256`.
3. Build the merged species database exactly as `reactor_probe.py:merged_database(clone_db, overlay, "N2")` does
   (overlay `benchmarks/m01/reactor-overlay.json`, its SHA-256 checked against the variant) into
   `<env>/merged-database.json`; record its SHA-256.
4. Create the venv with the interpreter the variant names (CPython 3.13.5; another 3.13.x is accepted only with
   `--allow-python-mismatch`, and the fingerprint then differs, so M01.A47 (a) does not apply); `pip install
   --require-hashes --no-deps -r reactor-env.lock`. The lock is generated once by the build lane from the probe's
   venv (`pip freeze` → hashes), so it pins exactly pymrm 2.5.0, numpy 2.5.3, scipy 1.18.1, numba 0.68.0,
   pandas 3.0.6 and their dependencies. The reactor package is **not** installed; the child imports it from the
   export.
5. `chmod -R a-w` the export, the database and the venv's site-packages; write `env-manifest.json` = `{variant_id,
   commit, export_tree_sha256, merged_database_sha256, lock_sha256, python, packages (pip freeze), licence_notice_sha256,
   created_at}` (`created_at` is outside every hash).

`verify` recomputes 2–5 and exits non-zero on any difference. Location: `$OPENFLOWSHEET_EXTERNAL_ROOT`, default
`$XDG_CACHE_HOME/openflowsheet/external` (`~/.cache/openflowsheet/external`); `<env id>` = `pymrm-6089593-<first 12
hex of lock_sha256>`. The application never builds an environment itself; a missing one is `environment_unavailable`
with the build command in the message.

**Handshake (once per job, per variant).** The first external call of a job runs the child with `--handshake`: it
verifies the full export tree hash, the merged database hash, `importlib.metadata` versions against the lock, and
returns the **environment fingerprint** `{python, implementation, platform, machine, cpu_model, cpu_flags_sha256,
packages, thread_env, env_allowlist, export_tree_sha256, merged_database_sha256, lock_sha256, runner_sha256}`.
`fingerprint_sha256` = `document_sha256` of it. The job caches it for its lifetime (the attempt's frozen identity,
§6.1). Every later child reports the cheap part (python, packages, cpu_model, thread_env, runner_sha256, and the
`EXPORT_TREE_SHA256` marker) and must match.

---

## 3. Records and schemas

### 3.1 Variants (`schemas/model-variant.schema.json`, new)

A variant is the frozen identity of one external model configuration. Its SHA-256 (`document_sha256`, ADR 0002) is
what a revision pins (`instances[i].model.artifact_ref`); its id is `instances[i].model.version`.

```
{ schema_version: "model-variant-v1",
  model_id: "c1.reactor", variant_id: "pymrm-6089593-g2-nz800-s123-v1", synthetic: false,
  evaluation: { kind: "out_of_process",
    reactor: { repository, commit: "6089593464fc…", model_class: "MembraneReactor1D",
               licence: "MIT", licence_notice_sha256, used_by_reference: true },
    environment: { python: "3.13.5", lock_sha256, env_id },
    runner_sha256,                        # SHA-256 of adapters/pymrm/child.py
    overlay_sha256, configuration: {geometry_case: "G2 — GHSV sweep_1000", num_z: 800, sweep_ratio: 1.0,
                     permeance_prefactors: 0, coolant: "pure N2, 1 bar", backflow: [0, 1-1e-4, 1e-4, 0, 0]},
    profile: { id: "M01-S123-v1", S1: {...}, S2: {...}, S3: {rtol: 1e-12, atol_factor: 0.1, dt_init: 1.0,
               max_steps: 400, target: "1e-6*(num_z/100)^2"}, acceptance: [...] } },
  boundary: { provider: "pr-c1-v1", reference_convention: "PR-C1-ref-v1",
    pressure_convention: "zero_drop", eps_P: 1e-3, projection: "lsq_extent_v1", defect_limit: 1e-6,
    duty: "process_side", per_tube_scaling: true,
    hard_domain: { T_K: [573.15, 773.15], P_Pa: [5e6, 1.5e7], H2_N2: [1, 4], inert_max: 0.2,
                   tube_flow_mol_s: [0.003573480649651052, 0.014293922598604208] },   # [0.5, 2] x F_nom
    data_domain: { T_K: [643.15, 733.15], P_Pa: [5e6, 1e7], H2_N2: [1.5, 3] } },
  accuracy: { precision_floor_rel: 1e-6, measured_path_independence_rel: 1.56e-8,
              discretization_estimate: <copied from reference_values.yaml derived_from_measured> },
  execution: { timeout_s: 120, max_retries: 1, kill_grace_s: 2.0 },
  coupling: { tau_xi_rel: 1e-5, tau_T_K: 1e-2, max_outer: 15, method: "broyden_good_v1",
              scales: {X: 0.1, dT_K: 10.0}, initial: {X: 0.15, dT_K: 80.0},
              bounds: {X: [0.0, 0.95], dT_K: [-50.0, 250.0]} } }
```

The stand-in's variant `standin-x025-v1` has `model_id: "c1.reactor_standin"`, `synthetic: true`, `evaluation: {kind:
"in_process", module: "openflowsheet.models.c1.reactor_standin", conversion_N2: 0.25}`, the **same** `boundary` block
except `hard_domain.tube_flow_mol_s: null`, `accuracy: {precision_floor_rel: 0.0, measured_path_independence_rel:
0.0, discretization_estimate: null}`, `execution: {timeout_s: null, max_retries: 0, kill_grace_s: null}` and the same
`coupling` block.

**Registry.** `adapters/variants/registry.json` maps `variant_id → sha256`. A test recomputes every document's hash and
compares it, checks `runner_sha256` against `child.py`, `overlay_sha256` against the overlay file, and
`accuracy.discretization_estimate` against `reference_values.yaml`. **Variants are append-only:** a changed child,
overlay, profile, grid or lock is a *new* variant id; an existing document is never edited (the registry test fails
on an edit). The old variant stays loadable so old revisions keep binding.

### 3.2 Experiment request and identity (`schemas/experiment.schema.json` `$defs/request`)

```
{ schema_version: "experiment-request-v1", experiment_key,
  model: {id, version (variant id), artifact_ref (variant sha256)},
  boundary: {provider_id: "pr-c1-v1", provider_identity_sha256, n_tubes, sweep_ratio},
  inputs: {components: ["H2","N2","NH3","Ar","CH4"], n: [5 × binary64], T, P},
  environment_fingerprint_sha256 }
```

`experiment_key = document_sha256(request without experiment_key)`. Floats are canonical by ADR 0002 (`repr`, exact).
`provider_identity_sha256` is `document_sha256` of `pr-c1-v1`'s `describe()` (implementation and data hashes). For an
in-process variant, `environment_fingerprint_sha256` is `document_sha256` of `{boundary module artifact hash, stand-in
module artifact hash, openflowsheet version}`. Not in the identity (they are context, in the result): requesting job,
purpose, timestamps, timeout, cache mode.

Consequences, by design: a one-ulp difference in any input is a different experiment (M01.A36's rule, extended);
(k n, k N_tubes) is a different key although the tube sees the same inlet (the cost of process-level identity,
accepted: N_tubes is fixed per design, so the sharing would almost never occur); a different machine is a different
key (CPU model is in the fingerprint), so cache entries never cross machines, while records do.

### 3.3 Result and attempt (`$defs/result`, `$defs/attempt`)

```
attempt: { schema_version: "experiment-attempt-v1", experiment_key, attempt: <int from 1>, job_id,
  execution: { kind: "in_process" | "out_of_process",
    status: "completed" | "not_executed" | "timed_out" | "crashed" | "protocol_error" | "spawn_failed"
            | "environment_unavailable" | "environment_mismatch" | "environment_changed" | "cancelled",
    exit_code, signal, message,
    tube_inlet (as sent) | null, tube_outlet (raw, as received) | null, stage | null,
    diagnostics (child's: stages, u_ret_min, min_axial_flow, dP, coolant heat, inlet-face loss, wall per stage),
    fingerprint | null, logs: {stdout_sha256, stderr_sha256, relpaths},
    timing: {wall_s, startup_s, solve_s} },          # timing excluded from every identity
  repeat_of: <attempt int> | null, repeat_bitwise_equal: bool | null }

result: { schema_version: "experiment-result-v1", experiment_key, request_sha256,
  outcome_class: "deterministic",
  envelope: <ReactorResult.as_document()>,           # M01 §8.12: status, code, outlet, xi, Q, ..., identity
  accuracy: <the variant's accuracy block>,
  produced_by: {job_id, attempt},
  provenance: {variant_id, variant_sha256, reactor rights block | null, fingerprint_sha256},
  provider_calls: <int>,                              # the experiment's own, unmetered (R-233)
  determinism_findings: [ {attempt, differing_fields} ] }
```

**Deterministic vs transient** (the rule the cache and retry read):

| Execution status | Envelope | Class | Cached | Retried |
| --- | --- | --- | --- | --- |
| `completed` | any boundary status: `ok`, `unsupported` (incl. `pressure_drop_exceeds_convention`), `not_converged` (incl. `reactor_not_accepted(<stage>)`, `element_balance_defect`), `error` `stream_enthalpy_refused` | deterministic | yes | no |
| `not_executed` | a boundary refusal before the evaluation (checks 1–5) or `ZERO_FLOW` | deterministic | yes | no |
| `crashed`, `protocol_error`, `spawn_failed` | `error`, `external_<status>` | transient | never | once (`max_retries`) |
| `timed_out` | `error`, `external_timed_out` | transient | never | no |
| `environment_unavailable`, `environment_mismatch`, `environment_changed` | `error`, `external_<status>` | transient | never | no |
| `cancelled` | — (the interrupt propagates) | transient | never | no |

Determinism is a stated invariant of the child (and the reason `not_converged` is cacheable): **the child's
computation is a pure function of the request** — every iteration limit is a count, never a wall clock; timing is
telemetry only. A43 measured it; the bypass mode keeps measuring it (§5.3).

**Retention.** Every attempt is written before its result is used; a deterministic result is written once and never
overwritten; nothing is deleted by M02. A transient failure leaves attempts and no result: the record of the failure
*is* the retained failed experiment (blueprint §9.1), and it never carries outlet values.

### 3.4 Storage

Files under `<project>/experiments/<key[0:2]>/<key>/`: `request.json`, `result.json` (iff deterministic),
`attempts/<n>.json`, `attempts/<n>/child.{stdout,stderr}`, `attempts/<n>/result.json` (the child's raw file).
Writes are atomic (`store.atomic_write_bytes`). Each file written by a job gets a row in the existing `artifacts`
table (`job_id`, `kind` ∈ {`experiment_request`, `experiment_result`, `experiment_attempt`}, `name` = key, `relpath`
relative to the project). A **cache hit** adds a row for the consuming job whose `parent_artifact_id` is the producing
row: call accounting (executions vs hits per job) is a query, with no new table and no store migration
(`t07-store-v1` unchanged). The in-memory application keeps the same layout in a `tempfile.TemporaryDirectory` owned by
the application object.

**Concurrency.** `experiments/locks/<key>.lock`, `fcntl.flock(LOCK_EX | LOCK_NB)` retried every 0.2 s with the
cooperative check between tries; after acquiring, the cache is re-read. The kernel drops the lock when its holder dies,
so there is no stale-claim state. Two jobs on one key: exactly one executes. (Network filesystems with unreliable
`flock` are a stated limitation, §11.)

### 3.5 The `experiment` job operation (ADR 0019 Amendment 4, carried by ADR 0033 D9)

`job_request.operation` gains `"experiment"` with body `$defs/experiment_body`:
`{model: {id, version, artifact_ref}, inlet: {components, n, T, P}, n_tubes, cache: "use" | "bypass" (default
"use")}` — SI only (mol/s, K, Pa), no Quantity conversion. Right `execute`. Admission: ADR 0020 D6's canonical-form
check; schema; the variant resolves and its SHA-256 equals `artifact_ref` (else `invalid_request`, pointer
`/body/model/artifact_ref`); components equal the variant's. The body carries model inputs, not a solver state, so
ADR 0020 D7 is untouched. The job ends `completed` whatever the experiment's outcome (a failed experiment is a result);
`failed(operation_error)` only for a defect. Outputs: the request, the result or the attempts, as `artifact_ref`s
(new kinds `experiment_request`, `experiment_result`, `experiment_attempt`). `get_job_result` on an experiment job
returns the `result` document, or the last `attempt` document when the outcome is transient
(`oneOf` widening of its response). Idempotency as ADR 0019 D3: the same key and body returns the same job; a new key
with the same body is a cache hit, no execution.

### 3.6 Schema changes (all additive; ADR 0033–0035)

| File | Change |
| --- | --- |
| `schemas/experiment.schema.json` | **new**: `$defs` `request`, `result`, `attempt`, `coupling` (§7.1), `experiment_body` |
| `schemas/model-variant.schema.json` | **new** (§3.1) |
| `schemas/model-replacement.schema.json` | **new** (§6.2) |
| `schemas/job.schema.json` | `operation` + `"experiment"` and its `oneOf` branch; `artifact_ref.kind` + `experiment_request`, `experiment_result`, `experiment_attempt`, `external_coupling`, `model_replacement_report` |
| `schemas/run-result.schema.json` | `solve_path` + `"revision_coupled"` |
| `schemas/solve-event.schema.json` | `outcome` + `"COUPLING_NOT_CONVERGED"` |
| `schemas/api-error.schema.json` | `code` + `"model_replacement_incompatible"`; `detail` doc names `report` |
| `schemas/transaction-result.schema.json` | `invalidations` description widened (text only, §6.3) |
| `schemas/job.schema.json` `$defs/job_result` | (as built, §14 B5) `get_job_result` `$ref`s `job_result`, so the widening is an optional `experiment` member and branch there; `application-results.schema.json` is unchanged |
| unchanged | `model-manifest` (Q-N5's default holds), `run-manifest` (`reproducibility_class` already has R3, `artifacts` is an open map), `solution-certificate` (checks use category `residual`, `limitations` items are open), `replay-report` (`reasons` is open), `solve-policy`, `process-revision`, `change-set` |

**ADR 0007 D2.3 (every float classified).** The new float fields are classified in a **separate addendum table**
`numerical_policy_external` in `benchmarks/k04/reference_values.yaml`, read by K04 A32 in addition to the existing
table, so the existing `numerical_policy` id and content — and with them every certificate's `numerical_policy_id` —
do not move: request inputs → *exact* (copied values); result and attempt external outputs → **R3 recorded external**
(compared exactly against the record on replay-from-record; within `precision_floor_rel` on a live rerun); coupling
iterates, residuals and inlets → R1/R2 under the existing floors; timings → excluded. If A32 scans only K03/K04 schemas
today, the addendum is still written and A32 is extended to read it.

**Fixtures.** One valid fixture per new or changed `$def`, **emitted by a real run** (stand-in and synthetic child in
the default gate; one real-reactor fixture committed from the opt-in run), one invalid per `$def` with a required
member removed (`scripts/t07_schema_fixtures.py`'s pattern).

---

## 4. The reactor in a flowsheet solve (D8)

### 4.1 The embedded unit `C1Reactor` (both `c1.reactor` and `c1.reactor_standin`)

Unit `U`, components (H₂, N₂, NH₃, Ar, CH₄), ν = (−3, −1, 2, 0, 0). Owned variables: outlet n (5), T_out, P_out, ξ
(`U.extent`), Q (the duty, `duty_id(U)`). Parameters (pinned inputs, in `constants_sha256`): `U.nu.<i>` and the two
**coupling parameters** `U.coupling.X` (dimensionless) and `U.coupling.dT` (K). N_tubes is **not** a parameter of the
inner problem (no row depends on it); it is a builder-read instance pin carried in the unit's configuration for the
experiment request.

| Row id (as the stand-in declares) | Builder (`models/rows.py`) | Form | Kind |
| --- | --- | --- | --- |
| `C1RX-mole.<i>` (5) | `reaction_balance_row` | n_in,i + ν_i ξ − n_out,i | `molar_flow` |
| `C1RX-extent` | `extent_row(extent, "U.coupling.X", n_N₂,in, "U.nu.N2")` | ξ − X̂ n_N₂,in / 1 | `molar_flow` |
| `C1RX-temperature` | `offset_row(T_out, T_in, "U.coupling.dT")` | T_out − T_in − ΔT̂ | `temperature` |
| `C1RX-pressure` | `balance_row((P_in,), (P_out,))` | P_in − P_out | `pressure` |
| `C1RX-duty` | `energy_row(inlet keys, outlet keys, source=Q)` over vapour enthalpy-flow blocks of `pr-c1-v1` | Q + Ḣ_in − Ḣ_out | `heat_rate` |

Accumulation declarations as `reactor_standin.EQUATIONS`. Outlet port declared vapour (no lifted split); the verifier's
fresh flash (ADR 0013) checks it. Causal `evaluate`: n_out = n_in + ν X̂ n_N₂,in, T_out = T_in + ΔT̂, P_out = P_in,
Q = Ḣ_out − Ḣ_in by the provider; formed in the rows' arithmetic order so the traversal start satisfies the rows to the
last bit. A dormant inlet gives ξ = 0 exactly (dormancy form as T05b §7.6 for units without a split). **The unit never
calls the external model.**

Manifest: `derivatives` = `[{output: "residuals", with_respect_to: ["free_variables"], method: "analytic", notes:
"the embedded rows at pinned coupling parameters (ADR 0034); exact for those rows"}, {output: "outlet.state",
with_respect_to: ["inlet.state"], method: "unavailable", notes: "the external map; no sensitivity through this unit
(ADR 0034 D4)"}]`; `execution_class` `experiment_provider` (`c1.reactor`) or `explicit_reduced` (stand-in);
`evaluation_cost_class` `expensive` / `cheap`; validity and limitations from the variant (§10's estimate, `extrapolated`
results, F-R2, F-R3; the stand-in's `SYNTHETIC:` first limitation, M01.A49).

### 4.2 The coupling problem

Per external unit j (instance-id order), w_j = (X̂_j, ΔT̂_j). Given w, the inner EO solve gives the state x(w) and the
unit's inlet s_j(w) = (n_in, T_in, P_in), read **exactly** from x(w). The experiment E_j(s_j) returns (when `ok`)
ξ_E and T_E (the projected extent and the outlet temperature of M01 §8.9). Define

- F_j(w) = (ξ_E / n_N₂,in, T_E − T_in) — division only here, on a flowing inlet; for a `ZERO_FLOW` result
  F_j = (X̂_j, 0);
- residual r_j = F_j(w) − w_j;
- convergence measure ρ = max_j max( |ξ_E − X̂_j n_N₂,in| / (τ_ξ n_tot,in), |T_E − T_in − ΔT̂_j| / τ_T ), with
  **τ_ξ = 10⁻⁵** (relative to the unit's inlet total flow) and **τ_T = 10⁻² K** (variant `coupling` block).

**Converged iff ρ ≤ 1** at an iterate whose inner solve converged; the final state is that inner solution, and the
experiments that judged it were evaluated **at that state's inlets** (an a-posteriori check, never extrapolated).

**Why these tolerances (first principles).** Within one environment the reactor map is deterministic (A43), so the
iteration sees no noise; the floor matters for the *verdict's* stability across environments, where results agree only
within ε_eval = 10⁻⁶ relative (A47 (b)). Propagated through the projection, δξ ≤ ε_eval Σ_{H₂,N₂,NH₃}|ν_i| n_raw,i /
14 ≈ 1.7 × 10⁻⁷ n_tot,in at the nominal point, and δT ≤ ε_eval T_E ≈ 7.6 × 10⁻⁴ K. τ_ξ and τ_T sit 59 × and 13 ×
above, outside ADR 0007 D2.4's near-threshold band [1/10, 10]. On the other side, the design grid's bias is 1.4–1.9 %
in ξ (≈ 5.6 × 10⁻⁴ n_tot,in) and 1.2–1.7 K in T_out: τ_ξ and τ_T are 56 × and 120 × below it, so coupling error is
negligible against model error and iterating tighter buys nothing. τ_ξ also satisfies M01 §10.5's "above 10⁻⁷ × the
reactor's throughput". At every converged check the record reports the floor ratios (τ_ξ n_tot,in / δξ_k and
τ_T / δT_k computed from that iterate); a ratio below 10 sets `near_threshold: true` on the certificate's coupling
check and adds a limitation — the report blueprint §5.2 requires instead of a silent tolerance below the accuracy floor.

### 4.3 The iteration (`broyden_good_v1`)

Scaled coordinates u = D w, D = diag(1/0.1, 1/10 K) per unit; r̂ = D r. B is 2m × 2m, dense.

```
u0 = D w0      (w0 = the instance pins coupling_initial.X / coupling_initial.dT if given, else the variant's initial)
B  = -I
k = 0; best = None
loop:
    inner = solve_inner(u_k)          # k = 0: the route's initializer chain (traversal-G0-v1, or ADR 0024's
                                      # warm start under T08-warm-v1); k ≥ 1: user_start = x(u_{k-1}), recorded
    if inner fails: backtrack (below); continue
    for each unit j: E_j = runner.run(request(s_j(u_k)))     # one experiment per unit per iteration
        if E_j transient after retries: end EVALUATION_ERROR("external_<status>(<unit>)")
        if E_j deterministic refusal:   backtrack; continue
    r̂_k, ρ_k = ...
    if ρ_k <= 1: end CONVERGED at k
    if k == max_outer - 1: end COUPLING_NOT_CONVERGED (reason "max_outer")
    if best is not None and ρ_k > ρ_best: B = -I; u_k, r̂_k = u_best, r̂_best   # reset to substitution from best
    else: best = k
    if k > 0 and not reset: B += ((r̂_k - r̂_{k-1}) - B Δu) Δuᵀ / (Δuᵀ Δu)     # Δu = u_k - u_{k-1}
    Δu = solve(B, -r̂_k);  u_{k+1} = clip(u_k + Δu, D·bounds)
    k += 1
backtrack: u ← u_prev + ½ (u - u_prev), at most 3 times per iteration (inner solves; an experiment only at the
           accepted point); then end COUPLING_NOT_CONVERGED (reason "inner_failed" or "external_refused(<code>)").
```

The first step from B = −I is successive substitution (u₁ = D F(w₀)). `max_outer` = 15 counts outer iterations
(each one experiment per unit, retries excluded); backtracks do not count. A second reset in a row ends
`COUPLING_NOT_CONVERGED` (reason `no_decrease`). The dense 2m × 2m solve is `numpy.linalg.solve`; a singular B ends
`COUPLING_NOT_CONVERGED` (reason `broyden_singular`).

**Expected behaviour on the C1 loop.** With no feed–effluent exchanger, ΔT̂ does not reach the reactor inlet (the
preheater fixes T_in), so ∂F/∂ΔT̂ = 0 and the problem is effectively scalar in X̂, with a positive gain below one
(more conversion → less recycle → longer residence). Substitution converges linearly; Broyden in a handful of
iterations. The stand-in's F is constant ((0.25, 0)), so it converges at k = 1 with two experiments.

### 4.4 Route, outcomes, certificate, interruption

- **Route.** `select_route(document)` returns `revision_coupled` when `bind_revision_flowsheet` binds and at least one
  instance's model is variant-backed; `revision_eo` otherwise (unchanged). Admission as `revision_eo`. The inner plan
  is `plan_revision`'s, unchanged; the effective solve policy is the route's registered default (`T06-revision-v2`)
  or the named one; the coupling parameters come from the frozen variant, so the solve-policy schema does not change.
- **Outcomes.** `CONVERGED`; `COUPLING_NOT_CONVERGED` (new, with reason); `EVALUATION_ERROR` with message
  `external_<status>(<unit>)` for an external failure; an inner failure at k = 0 passes its own outcome through.
- **Certificate.** K04 verifies the final inner state as for `revision_eo`. The coupling driver supplies two
  `checks` per external unit: `{id: "EXT-COUPLING:<unit>:xi", category: "residual", subject: <unit>, value: |ξ_E −
  X̂ n_N₂,in| / n_tot,in, tolerance: 1e-5, result, scope: "evaluated", near_threshold, independence_qualification:
  "external model, R3"}` and `…:T` (K, tolerance 1e-2). The check also asserts that the experiment's request inputs
  equal the certified state's inlet bitwise (else `fail`). `limitations` gains `{kind: "external_model", unit,
  variant_id, synthetic, reproducibility: "R3" | "R1", discretization_estimate}`; `derivative_provenance` records
  `unavailable` for the external map. No certificate on any non-`CONVERGED` outcome (failure bundle, which embeds the
  coupling record).
- **Interruption.** A cancelled or timed-out coupled job emits `partial_solve_trace` (ADR 0020 D3) **plus** the
  experiment artifacts already written — retained facts, not solve artifacts — and nothing else.
- **Budgets.** Wall time as ADR 0020 D3. `max_property_calls` meters the inner solves only; the boundary's provider
  calls inside an experiment are unmetered and recorded in the experiment (R-233) — otherwise a cache hit would change
  the solve's count and break ADR 0007 D5.1's determinism of `BUDGET_EXHAUSTED`.
- **Progress.** One job `progress` event per outer iteration (`completed` = k + 1, `total` = `max_outer`) and one
  `output` event per experiment artifact.
- **Sensitivities.** M03's sensitivity entry points refuse a run on the `revision_coupled` route
  (`PARAMETER_NOT_DIFFERENTIABLE`, detail `external_map_unavailable`): a sensitivity of the inner problem at pinned w
  would silently treat the reactor as fixed-conversion. (M03's C3 already refuses EO-path revision flowsheets; this
  makes the reason explicit if that changes.)

### 4.5 Performance

Per outer iteration: one inner build and solve (the inner `ProblemSpec` is re-compiled per iteration because X̂, ΔT̂
are constants of it; the C1 loop is ≈ 80 variables, so compile plus solve is expected well under 1 s — measured in
G12, and worth optimizing only if it exceeds 20 % of an iteration) and one experiment (25–45 s cold at num_z = 800, as measured, §14 B6;
0 s on a cache hit). Expected 4–8 iterations on the real loop → about 2–6 minutes. Records are a few KB each. The
child's start-up (interpreter, imports, numba JIT) is measured separately (`timing.startup_s`); if it exceeds 30 % of
`wall_s` at the design grid, a persistent per-job child is reconsidered by an ADR amendment (R-224).

---

## 5. Failure, timeout, cache and noise

### 5.1 The evaluation seam gains one variant

`ExternalEvaluation.__call__(tube) -> TubeOutlet | NotAccepted | ExecutionFailure`, with `@dataclass(frozen=True)
class ExecutionFailure: kind: str; message: str`. `Boundary.evaluate`, at check 6, maps it to `refused("error",
f"external_{kind}", message)`. Checks 1–5 and 7–10 and every M01 assertion are unchanged (the stand-in never returns
it). The runner sees the failure object itself and classifies it transient.

### 5.2 Timeout and retry

Per attempt, `timeout_s` from the variant (120 s for the design-grid variant). After G11's sweep the build lane
re-registers it as max(120, 3 × the slowest accepted point's `wall_s`), rounded up to 10 s, **as a new variant only
if it changes** (§3.1's append-only rule). The job's wall time is enforced by ADR 0020's machinery and reaches the
child through layers L1–L2. Retries: §3.3's table; each retry is a new attempt of the same experiment, inside the same
flock.

### 5.3 Cache bypass as a determinism monitor

`cache: "bypass"` (experiment jobs only; never in a coupled solve) executes even when a result exists, writes the new
attempt with `repeat_of` and `repeat_bitwise_equal`, and **never overwrites** the result. A deterministic repeat that
differs in any bit of `tube_outlet` appends to the result's `determinism_findings` (an append to a findings list is
the one permitted update of a result file; it is recorded as a new artifact row) — a finding for the design lane, not
an error. M01.A43's adapter half is two bypassed runs.

### 5.4 Noise, accuracy, and why the reactor is not warm-started

The reactor is noise-free within one fingerprint (bitwise, A43) and agrees within ε_eval = 10⁻⁶ across fingerprints
(A47 (b)). The variant's `accuracy` block carries both numbers and the discretization estimate (DX-01, the bias of
the design grid; an estimate, not a bound), copied into every result. Consumers read them: the coupling (§4.2), M04's
finite differences (M01 §10.5: ≈ 1.6 × 10⁻⁸/h relative noise), M07's truth checks (limited by the bias). There is no
forcing policy (blueprint §5.2's option): the S3 profile is fixed and already polishes to the path-independence
level. Warm-starting S2 from a neighbour would cut cost but make a result depend on its predecessor at the 10⁻⁸ level,
which an exact cache keyed on the request cannot represent, and which Q-F4 has not measured outside the nominal point.

---

## 6. Freezing and promotion

### 6.1 Frozen model versions

1. **In the revision.** For a variant-backed model, `instances[i].model.version` is the variant id and
   `.artifact_ref` its SHA-256. The binder resolves the variant and refuses `Unbound("unsupported",
   "model_variant_mismatch(<instance>)")` when the id is unknown or the hash differs (API: `revision_unsupported`).
   `InstanceView` gains `model_version` and `model_artifact_ref` (internal type). Native models keep today's behaviour
   (`model.version` unchecked), so no v0.1 revision changes.
2. **In the package.** Variants are append-only and registry-pinned (§3.1). Changing the child, overlay, profile,
   grid, lock or timeout makes a new variant, which a revision reaches only by promotion.
3. **In an attempt.** The first external call of a job performs the handshake and freezes `{variant_sha256,
   fingerprint_sha256}` per unit for the job. Every request is built with that fingerprint; a child reporting
   another ends the attempt `EVALUATION_ERROR("external_environment_changed(<unit>)")`. Within one process nothing
   else can change mid-attempt (native models are code in the worker).

### 6.2 The replacement check (blueprint §5.3) and its report

Applies when a change set alters any of `instances[i].model.{id, version, artifact_ref}` and the old or the new model
is variant-backed (native-to-native changes keep v0.1 behaviour; R-228's watch-for). It runs in `commit_change` and
`preview_change`, after the edit is applied and before commit, against the old and new manifests and variants:

| Facet | Passes iff |
| --- | --- |
| `resolvable` | the new model is in `MODEL_BUILDERS` and, if variant-backed, its variant resolves with the stated hash |
| `ports` | same port names; per port equal kind, direction, multiplicity, state definition, component mapping; new phase capabilities ⊇ old |
| `components` | `validity.components` equal as ordered tuples |
| `conserved_quantities` | equal multiset of (accumulation kind, holdup quantity, dimension) over declared equations |
| `reference_states` | equal `property_provider` and `reference_convention` |
| `boundary_condition` | equal variant `boundary` blocks, excluding `hard_domain` and `data_domain` (compared under `validity`); for a non-variant side, equal declared equation ids with equal dependencies, accumulation kind, dimension and conditional class |
| `degrees_of_freedom` | the new revision binds, is `STRUCTURALLY_CLOSED`, and the instance contributes the same numbers of rows and owned variables |
| `derivatives` | every (output, wrt) the old model declares with an EO-capable method is declared by the new one with an EO-capable method |
| `validity` | the new declared domain (T, P intervals, phases, and the variant hard domain) contains the old one |

`synthetic` is reported, not judged (real → stand-in is allowed; a revision bound to a synthetic model can carry no
W21 or M07 claim, R-199). Report (`schemas/model-replacement.schema.json`): `{schema_version, instance_id, from: {id,
version, artifact_ref, synthetic}, to: {…}, facets: [{facet, result: "pass" | "fail" | "not_applicable", detail}],
compatible}`. Any `fail` → the transaction is `rejected`, `error.code = "model_replacement_incompatible"`,
`error.detail.report` = the report; `preview_change` returns the same outcome without committing. On commit the
report is stored as an artifact (kind `model_replacement_report`, `job_id` null) and its SHA-256 is written to the new
revision's `provenance.artifact_hashes["model_replacement:<instance>"]` (provenance is outside the content hash, so
identity semantics do not move).

**"Incompatible pressure boundary rejected"** is met at both levels: a replacement whose variant declares another
pressure convention or ε_P fails `boundary_condition` (G9), and an evaluation whose |ΔP|/P_in exceeds ε_P is refused
`pressure_drop_exceeds_convention` by the boundary and retained as a deterministic experiment (stand-in through the
runner, G4; the real reactor's ΔP ramp is a measurement, G11 (c) — inside the hard domain with Q-F5's flow bound the
convention is expected never to bind, which is the design's intent).

### 6.3 Invalidation

The contract already invalidates at every commit: `TransactionResult.invalidations` lists `run-<job_id>` for every solve
job of the expected revision (`local.py:444`). M02 generalizes the rule, not the mechanism: `EVIDENCE_OPERATIONS`
maps each evidence-producing job operation to its prefix (`solve → run-`); the list is every job of a registered
operation whose request names the expected revision, in acceptance order. M03–M05 register their operations (e.g. a
study or optimization job) when they add them; M02 registers none besides `solve`. **Experiment records are never
invalidated**: they are facts about a variant, not about a revision, and a rollback to the earlier model reuses them
through the cache. The `invalidations` description in `transaction-result.schema.json` is widened to say so.
`diff_revisions` shows the change as `changed: instances.<i>.model.*` and, once M06's ADR 0019 Amendment 3 is on
`main`, as an `elements` entry for the instance; M02 adds nothing to `semantic_diff`.

---

## 7. Replay

### 7.1 The bundle member `external-coupling.json` (`$defs/coupling`)

A revision bundle on the `revision_coupled` route holds ADR 0020 D4's files for the **final** inner solve, plus
`external-coupling.json` (an amendment of D4's file list, ADR 0034 D6): `{schema_version, route, variants: {unit:
<full variant document>}, frozen: {unit: {variant_sha256, fingerprint_sha256, fingerprint}}, coupling_block, iterations:
[{k, w, u, inner: {outcome, iterations, start, constants_sha256, state_sha256}, units: {unit: {inlet: {n, T, P},
request: <request doc>, result: <result doc> | null, attempts: [<attempt doc>], cache_hit, xi_E, T_E, n_N2_in,
n_tot_in, r_xi, r_T, floor_ratio_xi, floor_ratio_T}}, rho, step: {kind, du, B}}], outcome, reason}`. The documents are
embedded, so the bundle stands alone. R0 fields: ids, variant hashes, request keys, `k`, step kinds, outcome; floats
per §3.6.

### 7.2 `reproduce` of a coupled run

1. Integrity as today, plus `external-coupling.json` against its schema and each embedded request's key against its
   content.
2. Mode as ADR 0007 D4, decided by the **in-repo** environment.
3. Re-run the coupling with a **recorded backend**: at iteration k, unit j, recompute the request; its identity
   fields (model, variant, provider, n_tubes, fingerprint) must equal the record's exactly and its inputs must agree
   within ADR 0007 D2 (bitwise is observed, not required); then serve the recorded result. A mismatch is `MISMATCH`
   naming `external_request(k, unit)`. For an **in-process** variant (the stand-in) the backend re-evaluates instead
   and compares the envelope (R1/R2).
4. Compare everything else as for `revision_eo`. `reasons` gains `external_results_replayed_from_record(<count>)`;
   `recorded_environment` gains the frozen fingerprints. A **live rerun** (calling the reactor again) is the
   evidence script of G12, never `reproduce`.

`RunManifest.reproducibility_class` is `R3` iff any variant used is out-of-process; else as today.

---

## 8. The PR units (M01 §7)

All on `pr-c1-v1`, `PR-C1-ref-v1`, `T05b-phase-contract-v2`; components (H₂, N₂, NH₃, Ar, CH₄); nTP-v1 streams;
`REGISTERED_NOMINALS` scales unchanged (flow 3 mol/s, T 100 K, P 10⁵ Pa, heat 10⁵ W) — G7 (f) measures their
adequacy on the C1 loop. Each manifest names the provider and convention, lists the §7 limitations, and is `tested`
at M02's end, never `reviewed`.

| Model id | Rows and phase handling |
| --- | --- |
| `c1.feed_source`, `c1.product_sink`, `c1.stream_splitter` | The SYN-001 unit classes are reused under these ids **iff** their rows and manifests contain no SYN-001 constant (the implementer checks and records it in the WO's commit message); otherwise thin C1 classes with the same rows. The sink accepts vapour or liquid; the splitter copies T and P and splits by a pinned fraction |
| `c1.adiabatic_mixer` | Material rows per component; pressure rows exactly as SYN-001's `adiabatic_mixer` writes them (reused unchanged); energy row Σ Ḣ_in − Ḣ_out = 0 with vapour enthalpy blocks. Outlet port `vapor`; regime lattice {VAPOR, ZERO_FLOW}; admissibility: the provider's flash of the outlet is VAPOR, or TWO_PHASE with liquid NH₃ ≤ τ_dew n_tot; otherwise the causal evaluate refuses `vapour_phase_inadmissible` and, at a converged state, the certificate's declared-port check fails (§14.2 B16: there is no solve-time screen and no phase-inadmissible outcome), never a silent vapour |
| `c1.tp_heater` | Material rows, T and P specification rows, duty energy row, vapour blocks; outlet `vapor`, lattice {VAPOR, ZERO_FLOW}, the mixer's admissibility. A cooler into the two-phase region is modelled as `c1.tp_flash` |
| `c1.tp_flash` | *Superseded in its rows and its regime handling by §14.2 B11–B14: the equilibrium row in R-008's pairwise form (kind molar_flow_squared), the light-gas liquid flows as zero rows in the equilibrium family, pinned in TWO_PHASE, and the dew band applied in the kernel. The original text follows for the record.* The §7 split. Variables: n_V (5), **n_L,NH₃ only** (the liquid's light-gas flows are structural zeros, not variables), T and P per outlet, Q. TWO_PHASE rows: n_in,i − n_V,i = 0 (H₂, N₂, Ar, CH₄); n_in,NH₃ − n_V,NH₃ − n_L,NH₃ = 0; **E = n_V,NH₃ · exp(ln φ^V_NH₃(T, P, n_V)) − (Σ_i n_V,i) · exp(ln φ^L_NH₃(T, P)) = 0** (kind `molar_flow`; blocks: the vapour ln φ block and the pure-liquid ln φ block of `pr-c1-v1`, derivatives per M01 §4.6); T and P rows per outlet; Q + Ḣ_in − Ḣ_V − Ḣ_L = 0. VAPOR rows: the equilibrium row replaced by n_L,NH₃ = 0. ZERO_FLOW: ADR 0012 D4 (c). Screen (ADR 0005 D3): VAPOR iff the provider's flash of (n_in, T, P) is VAPOR or TWO_PHASE with l_NH₃ ≤ τ_dew n_tot; TWO_PHASE iff n_V,NH₃ ≥ 0 and n_L,NH₃ ≥ 0 at the solution. A feed with no light gas flowing is refused `unsupported`, `pure_nh3_flash_unsupported` (LIQUID regime and the pure-NH₃ saturation point deferred, R-230) |

Lifted-split registry, zero-flow forms and dormancy forms are registered exactly as T05b registered SYN-001's
(`splits.lifted_splits`, `zero_flow_forms`, `dormancy_forms`; `check_agreement` must pass, generalized per
`SplitRule.vapour_only` by §14.2 B13); the flash's split is TP-type. **τ_dew = 10⁻¹⁰** (relative to the split's n_tot): the fresh flash of a vapour at its own dew point returns
liquid of order ε n_tot (M01 F4) and y*'s bisection error is ≲ 10⁻¹⁴ n_tot, so 10⁻¹⁰ is ≥ 10⁴ above both and
physically nothing. Every unit's verifier path is ADR 0013's fresh flash by `pr-c1-v1`, in the forms of §14.2 B15. Mixing `pr-c1-v1` and SYN-001
streams stays `REFERENCE_MISMATCH` (ADR 0001 D5.2).

**Binding (D14).** `bind_revision_flowsheet` reads `component_set.record_source`: the C1 records' path
(`benchmarks/m01/components.yaml`, the string M01's records loader names) binds with `PropertyMeter(PrC1Provider())`,
the C1 components and the C1 molecular weights; **any other value binds exactly as today** (SYN-001), so every
existing revision is untouched. The canonical-components mapping and `MOLECULAR_WEIGHTS` become per-provider tables.

**The registered tests of M01 §7** (G7): one test per rule — (1) the lattice and LIQUID's exclusion with light gas;
(2) the rows, including the structural zeros and E's division-free form; (3) the admissibility screens at the dew band;
(4) no temperature degeneracy for light-gas feeds (the band route is never taken); (5) ZERO_FLOW; (6) the verifier's
fresh flash on a vapour product at its own dew point.

### 8.1 The C1 loop test case `C1-LOOP-M02-v1`

`benchmarks/m02/c1-loop-standin.json` and `…-real.json` (identical except the reactor instance's model): makeup feed
1.0 mol/s, y = (0.74625, 0.24875, 0, 0.002, 0.003) (H₂/N₂ = 3, inerts 0.5 %), 300 K, 10⁷ Pa → `c1.adiabatic_mixer`
(with the recycle) → `c1.tp_heater` to 673.15 K → reactor (N_tubes = 1000) → `c1.tp_flash` at 253.15 K, 10⁷ Pa
(liquid → `c1.product_sink` "NH3"; vapour →) `c1.stream_splitter` purge fraction 0.02 (→ `c1.product_sink` "purge";
rest → mixer). P = 10⁷ Pa throughout (zero pressure drop everywhere). *Rationale:* reactor inlet near M01's nominal
(y_NH₃ ≈ y*(253 K) ≈ 2–3 %, H₂/N₂ ≈ 3, inerts ≈ 4–7 %), per-tube flow ≈ 0.6 × F_nom with the stand-in and ≈ 1 ×
F_nom expected with the real reactor (loop flow ≈ 7 mol/s at X ≈ 0.16). *Feasibility is a fact to measure:* if, at
the converged state, a reactor inlet leaves the hard domain (including Q-F5's flow bound) or the data domain's
pressure, the build lane records the state and escalates to the design lane; it does not adjust the case.

---

## 9. Work orders (dependency order)

Lane per CLAUDE.md: build lane implements; the design lane reviews every WO marked **R** (residuals, derivatives,
phase logic, scaling, certificates or replay identity). "Opus" = `opus-engineer`/`opus-implementer`; "bounded" =
`sonnet-implementer` from this note alone.

| WO | Owner | Content | Depends | Acceptance |
| --- | --- | --- | --- | --- |
| **WO-1** | bounded | Schemas of §3.6 (three new files, additive edits), `numerical_policy_external` addendum and A32's read of it, `docs/interfaces-frozen.md` rows. Invalid fixtures now; valid fixtures are emitted in WO-4/6/10/11 | — | G1 (a), (c); existing schema tests green |
| **WO-2** | Opus | Variants: schema instances for `standin-x025-v1` and `pymrm-6089593-g2-nz800-s123-v1`, registry, loader, pin test; `Boundary.hard_domain` (a `HardDomain` dataclass defaulting to M01's constants, `tube_flow` `None`) with the per-tube flow check inside check 5; `ExecutionFailure` in the seam | WO-1 | G2; G6 (b); M01.A25–A32, A49 (label), A50–A52 green unchanged; flow-bound tests with a `Boundary` built from the real variant's hard domain and the stand-in evaluation |
| **WO-3** | Opus, **R** | Launcher and kill chain (§2.3); `worker.main` `setpgid`; executor `_kill_tree`; `tests/support/synthetic_child.py` with hooks `ok`, `sleep(s)`, `abort`, `ignore_sigterm`, `bad_json`, `wrong_hash`, `exit(code)`, `fingerprint(alt)`, `nondeterministic` | WO-2 | G3 entire; every ADR 0020 test green |
| **WO-4** | Opus | Experiment request/key, store, per-key flock, runner (cache, retry, bypass, records, artifact rows, unmetered provider), in-process backend (stand-in), out-of-process backend (launcher); emits the valid `request`/`result`/`attempt` fixtures | WO-3 | G4 entire |
| **WO-5** | Opus | Reactor environment builder (`env.py`, lock from the probe venv) and `child.py` (derived from `reactor_probe.py`'s `merged_database`, `build`, `reactor_class`, `strategy`, `outlet`; `NotAccepted` stages `S1`, `S2`, `S3`, `certificate`, `backflow`, `nonpositive_flow`; handshake; fingerprint); evidence-only switches `s2_dt_init` and `backflow_alt` reachable from the evidence script, never from a variant or the application. Tests marked `pymrm`, deselected in `scripts/check.sh` (as M03's `nlp`) | WO-3 | G10 (a)–(h) run once and recorded; the AST import test (default gate) |
| **WO-6** | Opus | `experiment` job operation (§3.5): schema branch, admission, body, outputs, events, `get_job_result`; emits the valid `experiment_body` fixture | WO-4 | G5 entire |
| **WO-7** | Opus, **R** | C1 binding by `record_source`; per-provider components and molecular weights; `InstanceView.model_version/artifact_ref`; `model_variant_mismatch` | WO-2 | G2 (T07 corpus and SYN-001 identities byte-identical); G6 (a) |
| **WO-8** | Opus, **R** | PR units (§8), blocks over `pr-c1-v1`, lifted-split / zero-flow / dormancy registrations, manifests, the six §7 tests; as amended by §14.2, in items WO-8.1–WO-8.5 | WO-7 | G7 (a)–(e), (g)–(k); G2 as amended (G7 (f) moves to WO-9) |
| **WO-9** | Opus, **R** | `C1Reactor` (§4.1) and the two `MODEL_BUILDERS` entries (pins `n_tubes`, optional `coupling_initial.X`, `coupling_initial.dT`); envelope `unit_models` lists `c1.reactor` and, as synthetic, `c1.reactor_standin`; M01.A49's binder clause replaced by G8 (e); the reactor's `MODEL_CHECKS` / `REACTING_MODELS` entries, its duty row on §14.2 B17's vapour blocks | WO-8 | inner solve of `C1-LOOP-M02-v1` at fixed w converges from `traversal-G0-v1` and verifies; G7 (f) |
| **WO-10** | Opus, **R** | Coupling driver (§4.2–4.4), route `revision_coupled`, outcomes, certificate checks and limitations, `external-coupling.json`, R3 class, recorded backend for `reproduce` (§7.2); emits the valid `coupling` fixture | WO-4, WO-9 | G8 entire |
| **WO-11** | Opus, **R** | Replacement check and promotion (§6.2–6.3): `application/replacement.py`, commit/preview integration, api-error code, report artifact and provenance hash, `EVIDENCE_OPERATIONS`; emits the report fixture | WO-9 | G9 entire |
| **WO-12** | Opus (runs) | Opt-in evidence with the real reactor: G10, G11 (Q-F4 17 points, Q-F5 flow points, ΔP ramp, timing), G12 (real loop: solve, replay, live rerun); records under `benchmarks/m02/` with `judged: false`; timeout re-registration per §5.2 | WO-5, WO-10, WO-11 | G10–G12 numbers recorded; any inside-domain failure handled by §10.3's rule |
| **WO-13** | bounded | Evidence manifest `evidence/M02/<commit>/manifest.json`; `docs/support-matrix.md` row for `external-subprocess-v1`; pointer paragraphs added to ADR 0019 (Amendment 4 → ADR 0033 D9, ADR 0034 D7, ADR 0035 D4), ADR 0020 (→ ADR 0033 D2, ADR 0034 D6), ADR 0027 (→ ADR 0034 D10) at merge time; `docs/progress.md` | all | manifest `status: tested` iff G1–G12 pass |

M04 can begin against records once WO-4 and WO-6 are merged (the stand-in produces schema-valid records) and against
real data once WO-5 is; the session decides whether to branch M04 early.

---

## 10. Verification gates

Each gate is decided by a recorded number or an exact assertion. "Default gate" = `./scripts/check.sh`; "opt-in" = the
`pymrm`-marked tests and the evidence scripts, run in the reactor environment and recorded in the manifest.

### 10.1 Default gate

- **G1 Schemas.** (a) Every new or changed `$def` has one valid fixture emitted by a real run and one invalid fixture,
  and both round-trip. (b) The 50-revision T07 corpus's structural and validation reports are byte-identical to the
  merge base. (c) With M02's enum values and branches removed, every operation's fully resolved response schema equals
  the pre-M02 snapshot (R4-G3's method).
- **G2 Inertness.** SYN-001's structural hash, the K05 identity document and the T06 corpus values bit for bit;
  M01.A25–A33, A50–A52 unchanged; the `numerical_policy` id unchanged; no existing test edited except M01.A49's binder
  clause (replaced by G8 (e), with this note and R-231 cited in the diff), D12's, and §14.2 B13's four registry
  tests (restricted to their `syn001.` keys, literals unchanged, the full sets re-pinned by M02 tests). *(§14.2:)*
  also (i) `view.components` equals SYN-001's basis components at every T07 corpus revision; (ii) the 50 T07 corpus
  certificates byte-identical (SHA-256 of each canonical document) before and after WO-8.3 and WO-8.4; (iii)
  `SPLITS_REPR_SHA256` and the T05b reference file unchanged.
- **G3 Kill chain** (Linux; synthetic child). (a) Cooperative cancel while the child sleeps 60 s: the child pid is gone
  ≤ 3.0 s after the cancel is set; attempt `cancelled`; job `cancelled`. (b) `timeout_s = 1` on a 60 s child:
  `timed_out` recorded within 3.5 s of spawn; no retry. (c) A child ignoring SIGTERM is gone ≤ 2.5 s after the TERM.
  (d) Executor forced kill (`grace_s` = 0.5, worker ignoring the cooperative check by a test hook): worker and child
  pids gone ≤ 1.0 s after the kill. (e) The worker SIGKILLed alone by pid: the child exits (code 70) ≤ 2.0 s later.
  (f) Self-deadline: `deadline_s` = 1 and the child's margin set to 1 s through a test-hook environment variable
  (production margin 30 s), lifeline held: exit 71 ≤ 3 s after spawn. (g) `abort` → `crashed` (signal recorded), retried once, two attempts,
  no result. (h) After the test module, no process in the test's process group survives.
- **G4 Records and cache** (stand-in; synthetic child). (a) Same request twice: one execution, one cache hit, result
  files byte-identical, the hit recorded as a child artifact row. (b) T_in + 1 ulp: a different key, two executions.
  (c) (2n, 2 N_tubes): a different key (documented consequence). (d) After a `crashed` + retry `crashed`, a third
  request executes again (transient never cached). (e) Perturbation d with defect_rel 2 × 10⁻⁶ → result
  `not_converged`, `element_balance_defect`, no outlet values, served from cache on repeat. (f) y_NH₃ = 10⁻¹⁰ →
  result with execution `not_executed`, `nh3_below_trace`. (g) Reported ΔP 20 000 Pa at 10⁷ Pa →
  `pressure_drop_exceeds_convention` retained. (h) Bypass repeat: `repeat_bitwise_equal: true`; with the
  `nondeterministic` child: one determinism finding, the first result unchanged. (i) `max_workers = 2`, two jobs on one
  key: exactly one `completed` attempt in total.
- **G5 Experiment job.** `ok`, refusal and transient cases all end `completed` with the outputs of §3.5; idempotent
  resubmit returns `replayed = true` with no new attempt; a new key with the same body is a hit with no new attempt;
  a mismatched `artifact_ref` is `invalid_request` at admission.
- **G6 Frozen identity.** (a) A revision whose `c1.reactor` `artifact_ref` differs from the registry by one hex digit →
  the binder's `Unbound` `model_variant_mismatch(<instance>)`; through `solve`, admission refuses at T07 §5.3 step 2
  `revision_not_ready`, STR-01..05 `NOT_RUN` naming the cause (§14.2 B18; not `revision_unsupported`). (b) The variant pin test (§3.1). (c) A
  coupled solve whose (synthetic out-of-process) child reports a different fingerprint at k = 1 → `EVALUATION_ERROR`,
  `external_environment_changed(<unit>)`, no certificate.
- **G7 PR units.** (a) The flash at M01's registered TWO_PHASE states F1 and F11 (as feeds, at their T and P): the EO
  solve's vapour fraction and y*_NH₃ agree with `pr-c1-v1.flash` within 10⁻⁹ relative; material closure ≤ 10⁻¹² n_tot;
  energy closure ≤ 10⁻⁹ |Ḣ_in|. (b) A VAPOR feed (V1 at 673.15 K): regime VAPOR, n_L,NH₃ = 0 exactly. (c) A feed at its
  own dew point: VAPOR admissible by τ_dew; the verifier `VERIFIED`. (d) ZERO_FLOW feed: ADR 0012 D4 (c) forms, Q = +0.0.
  (e) Pure NH₃ feed → `pure_nh3_flash_unsupported`; mixer/heater outlet forced two-phase → typed inadmissible
  (§14.2 B16: the heater to 253.15 K, 10⁷ Pa with y_NH₃ = 0.15 refused `vapour_phase_inadmissible` by its evaluate,
  the traversal's outcome recorded; a constructed converged state with that outlet → `phase_admissibility.<U>.outlet`
  `fail`, certificate `FAILED`).
  (f) Scaling: at the stand-in loop's solution, the scaled Jacobian's `rcond_1` ≥ 10 × τ_ill (recorded); if not, a
  C1 nominal set is proposed to the design lane — not chosen by the build lane. *(Measured at WO-9, §14.2.)*
  (b), (c) as extended and (g)–(k): §14.2 "Gates as amended".
- **G8 Coupled route with the stand-in.** On `C1-LOOP-M02-v1` (stand-in): (a) `CONVERGED` at k = 1 with exactly two
  experiments; certificate `VERIFIED`; both coupling checks `pass`, the ξ check's value ≤ 10⁻¹² (roundoff of the
  per-tube mapping and the projection) and the T check's exactly 0.0; (b) flowsheet element balance
  (makeup in = NH₃ product + purge, for H, N, Ar, C) ≤ 10⁻¹⁰ × the makeup's element flow; (c) the final state agrees
  within 10⁻⁸ relative with an **independent** sequential-substitution solve of the same loop written in test support
  from `pr-c1-v1.flash` and the closed-form stand-in (no EO machinery); (d) `reproduce` → `MATCH`, the stand-in
  re-evaluated; (e) the stand-in binds via `MODEL_BUILDERS`, its manifest and every `ok` identity say synthetic, and
  the envelope lists it as synthetic only; (f) driver-level, with the inner solve and the experiments stubbed by
  an affine map F(w) = w* + G (w − w*): G = diag(0.5, 0) and G = diag(1.8, 0) (non-contractive) both converge, the
  second within 2·2 + 1 = 5 iterations (Gay's finite termination of Broyden's method on affine maps); F(w) = w + (1, 0)
  (no fixed point) ends `COUPLING_NOT_CONVERGED` with a failure bundle embedding the record and no certificate;
  end-to-end, a test-only in-process variant with ξ = (0.15 + 2 (y_inert,in − 0.05)) n_N₂,in and T_out = T_in + 80 K +
  1000 K × (y_NH₃,in − 0.02) converges on `C1-LOOP-M02-v1` with ρ ≤ 1 in ≤ 15 iterations and needs more than two; (g) a cancel at k = 1 leaves `partial_solve_trace` plus the experiment artifacts only.
- **G9 Promotion.** On a project with `C1-LOOP-M02-v1` (stand-in) solved once: (a) a commit replacing the reactor
  with `c1.reactor` @ the real variant → `committed`, every facet `pass`, `invalidations == ["run-<that job>"]`,
  `diff.changed` contains the instance's `model.id`, `model.version` and `model.artifact_ref` paths (and the
  `elements` entry when M06's amendment is on `main`), the report artifact's SHA-256 in the new revision's provenance;
  (b) a test-only variant with `pressure_convention: "outlet_specified"` → `rejected`, `model_replacement_incompatible`,
  `boundary_condition` `fail`; (c) one with a narrower T domain → `validity` `fail`; one with a renamed port →
  `ports` `fail`; (d) `preview_change` returns (a)–(c)'s outcomes and commits nothing; (e) a rollback commit to the
  stand-in, then a coupled solve: both experiments are cache hits (no new attempt).

### 10.2 Opt-in, real reactor (WO-12; recorded in the manifest, never in the default gate)

- **G10 Adapter halves of M01.A41–A48** (§8.15): (a) A41: S1–S3 accepted at num_z 800 for T_in 653.15, 673.15, 693.15 K.
  (b) A42: `s2_dt_init` 10⁻⁶ vs 10⁻¹ at the nominal point: max relative difference over n_out and T_out ≤ 10⁻⁶
  (record the value; 1.56 × 10⁻⁸ expected). (c) A43: two bypassed runs bitwise equal. (d) A44: `backflow_alt` bitwise
  equal; u_ret_min > 0. (e) A45: element defect ≤ 10⁻⁷ in every accepted run. (f) A46: |ΔP|/P_in ≤ 10⁻³ in every run.
  (g) A47 (a): the evaluation with `pinned.F_ret_in_mol_s`, `pinned.y_in`, T_in, p_ret_out = P_in returns
  `pinned.outlet_n_mol_s` and `pinned.T_out_K` bitwise **when** the environment block (python, the four packages, the
  platform string, one thread) equals the record's; equal block and unequal bits → a finding naming both CPU models,
  and (h) decides. (h) A47 (b): through the full boundary at N_tubes = 1 with n = `pinned.inlet_n_mol_s`, each of the
  five flows and T_out within 10⁻⁶ relative. (i) A48: every `ok` result's `discretization_estimate` equals
  `reference_values.yaml` → `derived_from_measured.discretization_estimate`.
- **G11 Coverage and timing.** (a) Q-F4: the 17 points of §8.15 (16 corners + centre), num_z 800: each ends `ok` or a
  typed refusal; record status, code, stage, wall time, A45/A46 values. (b) Q-F5: the centre point at 0.25, 0.5, 2 and
  4 × F_nom (the 0.25/4 points run through the evaluation directly, since the variant refuses them): record acceptance.
  (c) ΔP ramp: nominal composition, 673.15 K, 5 × 10⁶ Pa, per-tube flow 0.5–16 × F_nom (doubling), evaluation direct:
  record |ΔP|/P_in and the smallest multiple at which it exceeds ε_P, if any. (d) Timing: `startup_s` and `solve_s` at
  the nominal point, five repeats; record the start-up share.
- **G12 Real loop.** `C1-LOOP-M02-v1` with `c1.reactor`: `CONVERGED` in ≤ 15 outer iterations with ρ ≤ 1; certificate
  `VERIFIED`; floor ratios ≥ 10; the reactor inlet inside the hard domain and Q-F5's bound; `reproduce` → `MATCH`
  (replayed from record) on the same machine and, if a second registered architecture is available, there too
  (`compatible_reproduction`); a live rerun in the same environment reproduces every experiment bitwise
  (`repeat_bitwise_equal`) or, with another fingerprint, within 10⁻⁶. Record iterations, wall time, per-iteration
  compile+inner time.

### 10.3 Rules that act on the numbers

- A Q-F4 or Q-F5 point **inside** the hard domain that is not accepted: the variant's hard domain is narrowed to exclude
  the failing region by a **new variant** (append-only) and a register entry; the failing point becomes a registered
  refusal test (Q-F4's default). A narrowing that would exclude M01's nominal point stops the WO and goes to the design
  lane.
- Q-F5's bound is widened (new variant) only if both 0.25 × and 4 × are accepted, to [0.25, 4] × F_nom.
- G7 (f) below threshold, G8 (c) above 10⁻⁸, or G12 not converging: the build lane stops and reports to the design lane.

### 10.4 W21 and the `0.2.0a1` gate

W21 ("PyMRM boundary/accuracy/execution and provenance") is judged by the `verdict` agent from: boundary — M01's
assertions plus G4 (e)–(g), G9 (b); accuracy — G10 (b), (e), (f), (i), §4.2's floor argument with G12's recorded
ratios, the discretization estimate in every result; execution — G3, G4, G5, G11 (d), the isolation-profile
statement; provenance — G6, G10 (g)/(h), G12's replay, the records' rights and fingerprints. **Proposed gate
`v0.2-alpha-gate-v1`:** the v0.1 release gate unchanged (no relaxation) except its served-surface row, which on the
v0.2 line pins v0.2's own surface (§14 B1) + M01 and M02 manifests `tested` + W21 and
W22 verdicts `met`; the release notes state that reactor execution needs the separately built environment, is
Linux-only, and is R3; the alpha claims nothing of W23–W27 beyond verdicts already `met` (M06's W26/W27 if judged).
Frank decides (§12, N3).

---

## 11. Risks

| # | Risk | Kind | Mitigation / default |
| --- | --- | --- | --- |
| K1 | The PR flash's integration with the phase-attempt machinery (lifted-split registry, screens, verifier) is the largest build item and may meet SYN-001-shaped code | fact (build) | One split unit only (D13); WO-8 reviewed by the design lane; G7 |
| K2 | Reading `record_source` perturbs SYN-001 identities | fact | Every non-C1 value binds as today; G2 byte-identity |
| K3 | Child start-up (imports, numba JIT) is a large share of an evaluation (measured 1.8 s of 25–45 s, §14 B6: retired) | fact | Measured G11 (d); > 30 % → persistent child by ADR amendment (R-224) |
| K4 | Broyden fails on a strongly coupled loop | fact | Safeguards (§4.3); G8 (f), G12; M05's trust region does its own outer loop anyway |
| K5 | A freshly built env is not bitwise equal to the probe's (A47 (a)) | fact | The finding procedure; (b) decides (R-200) |
| K6 | Q-F4 corners fail → narrower domain → smaller design space for M05/M07 | fact | §10.3's rule; M07 informed |
| K7 | `flock` unreliable on network filesystems | fact | Stated limitation; projects on local disks |
| K8 | The worker's own process group changes terminal-signal behaviour | fact | Workers already ignore SIGINT; G3 and all ADR 0020 tests |
| K9 | K04 A32's float scan may not see new schemas, or may see them and fail | fact | The addendum table (§3.6) |
| K10 | M06's `elements` not on `main` when M02 merges | fact | G9 (a) asserts the coarse diff; `elements` when present |
| K11 | The traversal initializer fails on the C1 loop's first inner solve | fact | WO-9's acceptance; escalate (the design lane would register a C1 initializer) |
| K12 | `C1-LOOP-M02-v1`'s real state leaves the domains | fact | §8.1's escalation, no silent adjustment |
| K13 | `REGISTERED_NOMINALS` (SYN-001's) scale the C1 loop poorly | fact | G7 (f) |
| K14 | G7 (a)'s 10⁻⁹ relative is tighter than E's row tolerance permits (at F1, \|E\| = 9.3 × 10⁻⁸ (mol/s)² allows Δy ≈ 1.6 × 10⁻⁶, 2.6 × 10⁻⁵ relative); it holds only through Newton's terminal quadratic step (§14.2 B11) | fact | Measure; on failure stop and report. The remedy to propose is ADR 0018's `newton_refined` core, never a looser gate |
| K15 | The τ_dew checks on saturated copies (the flash's vapour, the splitter's outlets, the mixer's recycle inlet) are judged at ADR 0013's projection; at `x_final` they can fail at row-tolerance states (F9's mechanism) | fact | G7 (j) and G8 record `judged_at`; a refused projection at a C1 root goes to the design lane; τ_dew is not widened |
| K16 | FD Jacobian witnesses disagree with B17's convention at exactly dormant PR columns, by design | fact | Tests exclude those columns and assert the convention |
| K17 | A PR split's LIQUID regime is square but unsupported (`pr_liquid_regime_unsupported` → `UNVERIFIED`) | preference (N5, already Frank's) | Stays deferred with N5 |
| K18 | The C1 flash's TWO_PHASE Jacobian is singular at the dew point (its determinant ∝ L, as R-008's form is for SYN-001); a feed just past the band, l/n ∈ (10⁻¹⁰, ~10⁻⁸], may end `ACTIVE_SET_CYCLING` or `UNVERIFIED` | fact | G7 (c) records outcome, `rcond_1` and verdict at δ = 10⁻⁸, 10⁻⁷, 10⁻⁵ (l/n ≈ 6 × 10⁻¹⁰, 6 × 10⁻⁹, 6 × 10⁻⁷); a failure there is stated as a limitation by the design lane, not fixed by widening τ_dew |

## 12. Needs Frank (each with the default the work proceeds on)

- **N1 (preference — security posture).** `external-subprocess-v1` runs the group's pinned code with the user's
  privileges and no confinement. DECISION: accept for v0.2 local use, stated as "not a sandbox" in the support
  matrix and release notes. Alternative: a container or user-namespace profile. Reversible by: a new isolation profile
  id; records already name theirs.
- **N2 (preference — CI cost).** DECISION: no CI job for the reactor environment in M02; the opt-in evidence runs
  locally and is recorded. Alternative: a `workflow_dispatch` job building the env (network, ≈ minutes). Reversible
  by: adding the job; the tests are already marked.
- **N3 (preference — what an alpha claims).** DECISION: `v0.2-alpha-gate-v1` as §10.4. Alternative: wait for M05 before
  any 0.2 pre-release. Reversible by: not dispatching `release.yml`.
- **N4 (preference — release content).** DECISION: `c1.reactor_standin` is bound and shipped, listed synthetic only.
  Alternative: bind it only under a test flag (the default gate would then need a test-only registry hook).
  Reversible by: removing its `MODEL_BUILDERS` entry.
- **N5 (preference — scope against M01 §7).** DECISION: the PR LIQUID regime and pure-NH₃ saturation route are
  deferred; such feeds are refused typed. Alternative: implement them in M02 (ADR 0012's band route for C1).
  Reversible by: a later WO; nothing in the loop depends on it.
- **N6 (preference — cost vs reproducibility).** DECISION: no warm start of the reactor. Alternative: S2 from a
  neighbour's fields (cheaper loop iterations, history-dependent results). Reversible by: a new variant with a warm
  profile whose requests carry the warm source in their identity.
- **Informed, not asked:** the additive contract changes (ADR 0019 Amendment 4 via ADR 0033–0035), as Amendments 1 and 3
  were; the ADR 0020 D3 widening (group kill).

## 13. What M02 does not establish

- Not that the reactor is right: every real-reactor number is the group's model at the pin (regression), with its
  discretization bias (1.0–1.4 % NH₃) and findings F-R2, F-R3. Not grid convergence beyond M01 §10.
- Not bitwise reproduction across machines; only within one fingerprint, and ≤ 10⁻⁶ across.
- Not a sandbox. Not Windows. Not concurrency safety across hosts or on network filesystems.
- Not sensitivities or derivatives through the reactor (M04/M05), and not optimization.
- Not the PR LIQUID regime, pure-NH₃ flashes, two-phase heaters or mixers.
- Not the convergence of coupled loops in general: the outer iteration is tested on the C1 loop and synthetic maps.
- Not that the stand-in certifies anything: its numbers certify code paths only (R-199).
- Not M07's loop design: `C1-LOOP-M02-v1` is a test case.

---

## 14. Rulings on the build (as built), 2026-10-08

The build lane finished WO-1a, WO-2, WO-3 and WO-4 (`wp/M02` @ `02403d1`, gate green, 7178 passed; G3 met with worst
cases 2.10 s / 3.0, 2.003 s / 2.5, 2.07 s / 3.0; G4 (a)–(i) met). Its log is `docs/design/M02-build-decisions.md`
(D1–D13). Its D2, D3, D5, D6 and D9 are ratified as built: they place things, they do not change semantics. Four
questions came back. Each ruling below is normative and amends the sections it names.

**B1 (Q1) — The served MCP surface moves; R-192's pattern applies (R-234).** Every additive edit to an existing schema
that a tool's `outputSchema` or `inputSchema` inlines moves the served tool-list digest. That is a consequence of
transport parity (R-096), not a defect. M02 follows R-192 exactly:
- `scripts/t08_rc.py`'s A49 constant (`R133_DESCRIPTIONS_SHA256`) is a 0.1 release record and is **not edited**. On a
  v0.2 tree it reports the move, which is correct. R-133, R-134 and R-137 stay the record of the 0.1 surface.
- `tests/test_t08_w2_surface_digest.py` gains a decomposition test bound to M02's additions alone: served digest with
  M02's enum values, branches, members and `$defs` stripped = **the base's registered digest at merge time** (R-192's
  `6c4375b4…` if M06's Amendment 3 is on `main` by then, else R-133's `171dd768…`); and the served descriptions
  (texts) are byte-identical to the base's, so T08.A18 is not reopened. `8de83946…` (measured on
  `wp/M02-wo1b-proposed`, without M06) is evidence for the decomposition, not a pin. M02's served digest is
  registered beside the earlier ones at the merge commit, on the combined tree.
- **What the v0.2 gate pins:** the served digest at the release commit, registered with an unbroken decomposition chain
  back to R-133's `171dd768…`, one entry per surface change (R-192: M06; R-234: M02; later packages add theirs).
  `v0.2-alpha-gate-v1`'s surface row is that pin, replacing the 0.1 line's A49 constant on the v0.2 line; the 0.1 A49
  check is kept and its "moved" report is expected, not a failure of the v0.2 gate. §10.4 is amended accordingly.
- WO-1b is un-parked: cherry-pick `631b1c7` onto `wp/M02` with this decomposition test and B2's allowance.

**B2 (Q2) — `experiment`'s inlet is a model input, allowed by name (R-235).** ADR 0020 D7 forbids an operation to
accept a solver state or matrix from outside, because such a value could reach a certified result without being
re-derived. An experiment's inlet is the definition of the experiment: its record is identified by exactly those
numbers, nothing is certified about any other state, and the orchestrator never reads it. It is allowed **by name and
only there**: `test_t07_q26_no_external_state`'s allowed members gain `("submit_job", "body/inlet/n", "array")`, and its
pinned scalar inventory gains `T`, `P` and `n_tubes` (under `body/inlet` and `body`). The scan stays strict everywhere
else. A companion test proves the property that makes the allowance safe: no path from the `experiment` body reaches a
solver start, a warm start or a coupling iterate (the body is read by `adapters/experiments` only, and the coupling
driver builds its requests from its own inner solutions, §4.3). The rejected alternative, a reference to a stream of
an existing run instead of numbers, would make M04's sampled inlets impossible. ADR 0020 D7's "the first operation
that accepts one must add a W14 path test" does not apply, because the inlet is not a state, but the companion test is
its analogue.

**B3 (Q3) — Handshake failures: confirmed, with one amendment (R-236).** Confirmed as built (log D7, D8): a request whose
handshake measured no fingerprint is keyed on `document_sha256({measured: false, variant_sha256, env_id, status})`, its
outcome is transient and never cached, and the failed handshake attempts are retained (under `experiments/handshakes/`
and as attempts of that key). A crashed handshake is retried before the key is built, so a successful retry's measured
fingerprint is the one in the key. The unmeasured preimage can never equal a measured fingerprint's. **Amendment:** the
handshake and the evaluation have **separate** retry budgets, each `max_retries` (1). The handshake belongs to the job
and the evaluation to the experiment, so an experiment does not lose its retry because the job's handshake needed one.
A job keeps its handshake outcome, success or failure, for its lifetime and does not handshake again (no repeated
handshake per experiment), consistent with §6.1's frozen fingerprint. §3.3's table is read with this.

**B4 (Q4) — The store gets an injected artifact sink, and no upward import (R-237).** `adapters` sits below `application`
(blueprint §15; `tests/test_package_imports.py`). The lazy import of `application.store` is replaced:
- `adapters/experiments/store.py` declares a protocol `ArtifactSink.record(*, job_id, kind, name, relpath, sha256,
  size_bytes, parent_artifact_id) -> str` (returns the artifact id).
- The application constructs the runner with a sink that writes rows into its `artifacts` table, inside the store's
  transaction discipline. Tests and the in-memory path pass a list-backed sink.
- `atomic_write_bytes` moves down to a lower-level module (`openflowsheet/_files.py`) and stays re-exported from
  `application.store`, so its existing callers do not change.
- `test_package_imports` forbids any import, lazy or not, from `openflowsheet.adapters` into
  `openflowsheet.application` (an AST scan of function bodies too).

The lazy import was rejected because it hides a layering cycle from the import-time check, and the store could not be
tested without an application.

**B5 — The note's premises the build corrected.** The `get_job_result` widening lives in `job.schema.json#/$defs/job_result`
(§3.6 amended; log D3). `numerical_policy_external` lives in `benchmarks/m02/numerical_policy_external.yaml`, because the
K04 file is byte-pinned (log D2; §3.6's intent, an addendum that leaves the policy id unmoved, holds). The real variant
is created in WO-5 with the files it names (log D5). The in-process variant schema admits the stand-in's test-only
perturbation fields, which no registered variant uses (log D6).

### 14.1 Second round, 2026-10-08 (`wp/M02` @ `2e63211`: WO-1b, WO-5, WO-6 done; G5 and G10 met, A47 (a) bitwise; build log D14–D26)

**B6 (D22) — The measured cost stands, and so does the certificate (R-250).** One design-grid evaluation costs **25–45 s**
(start-up 1.8 s, S1–S3 ≈ 10 s, the group's KPI-drift certificate 12–35 s), not the ≈ 9 s this note assumed: the probe's
`wall_s` left the certificate out. The certificate is `certify_convergence_1d` at the pin: 20 implicit steps at
`dt_max` = 10⁶ s on the S3-polished reactor, so each step runs Newton at S3's tolerances (rtol 10⁻¹²). It requires every
scalar KPI to drift ≤ 10⁻³ relative. **It is not made cheaper, and it cannot be with an equal claim:**
- It is part of ADR 0027 D6's acceptance.
- The child extracts the outlet *after* the march, so the march produces the registered outlet bits (M01.A47 (a)).
- Fewer steps, or the group's looser tolerance inside the march, would weaken the claim; the loose tolerance would make
  the march vacuous (its Newton exits at the first iterate, M01 §8.7) and would also move the outlet.
- Neither caching (it is not JIT) nor a persistent child (start-up is 4–7 % of a call, far under R-224's 30 % trigger)
  touches it.

Whether it adds a claim beyond S3 is a specifier question. G11 records its `kpi_drift_rel_max` at every point, and if
the drift stays ≤ 10⁻⁶ wherever S3 is accepted, the specifier may be asked to rule. Until then it stays.

Consequences:
- **Timeout.** 120 s stands now (2.7 × the 44.9 s worst, which was the evidence-only A42 start). §5.2's rule applies after
  G11 over registered requests only: max(120, 3 × the slowest accepted point), as a new variant if it changes. A 41 s
  sweep point therefore raises it.
- **Cost statements.** §4.5 and §0 are amended to 25–45 s per evaluation and about 2–6 min per coupled solve. A job's
  handshake costs ≈ 1.9 s, once.
- **G12.** The real-loop job runs with `wall_time_s` = 3600. That covers 15 iterations × (1 + 3 backtracks) × 45 s with
  margin. The measured wall time is recorded, not gated.
- **M04 (its decision, R-240…).** Iteration 1's 632 experiments cost ≈ 4.4–7.9 h serially. The architecture lets experiments
  with **distinct keys run concurrently without changing a bit**: one single-threaded child per experiment, per-key
  locks only. So `max_workers` > 1, or an M04 batch operation that runs children concurrently, divides the wall time by
  the worker count. Workers must not exceed physical cores, or the timeout must be scaled, because load is what turns
  slow calls into `timed_out`.

**B7 (D24) — `job_result.experiment` may be `null` (R-252).** Confirmed, with the condition that makes it checkable: `null`
iff the job wrote no experiment artifact. That is possible only for a job that ended `cancelled`, `timed_out` or `failed`
before its first attempt. A `completed` experiment job always has a result or an attempt. A test asserts both
directions. G1 (c) and R-234 hold as the build recorded.

**B8 (D23) — Confirmed.** R-237's list-backed sink means the runner used with no application (library use, unit tests).
Every experiment job, including the in-memory application's, records through `ArtifactTableSink`, so that
§3.5's outputs resolve through `get_artifact`.

**B9 (D18) — An exception inside the model is a registered stage, not a crash (R-251).** Under §3.3's purity invariant
the child's computation is a function of its request, so a Python exception raised by the model on a given inlet
recurs on every attempt. Retrying it costs another 25–45 s, and leaving it uncached repeats it in every coupled
iteration and M04 sample. M02 registers the stage **`model_exception`** (M01 §8.12 / ADR 0027 A1.2 allow M02 to add
stages):
- **Window.** From constructing the first reactor object for the request through the outlet's extraction, i.e. S1,
  S2, S3, the certificate and `outlet`.
- **Covered.** Any `Exception` raised in that window, except `MemoryError`, `OSError` and their subclasses. It is
  returned as `not_accepted` with stage `model_exception`, so `not_converged`, `reactor_not_accepted(model_exception)`:
  deterministic, cached, not retried, and a deterministic refusal for the coupling driver (backtrack, §4.3).
- **Recorded.** The attempt's diagnostics hold the exception's qualified type name, its message's first line
  (≤ 512 characters), and the SHA-256 of the formatted traceback (the full text is in `child.stderr`).
- **Everything else stays `crashed`** (transient, one retry): an exception outside the window, `MemoryError`, `OSError`,
  a signal, a non-zero exit.

If this classification were ever wrong, the bypass repeat (§5.3) would expose it as a determinism finding. Test: a
synthetic-child hook that raises `ValueError` inside the window gives a cached `reactor_not_accepted(model_exception)`
with no second attempt; one that raises `MemoryError` gives `crashed`, retried once.

**B10 (D14) — Confirmed.** A later experiment in a job whose handshake failed writes one attempt recording the frozen
failure and executes nothing (R-236; §3.3 retention). The attempt has the frozen status, `exit_code: null`,
`timing.wall_s` 0, and the relpaths of the original handshake's logs, so it is distinguishable from an execution without
a new status value.

### 14.2 Third round, 2026-10-09 (`wp/M02` @ `6a46cdd`: WO-8 stopped before code; build log D30, D27, D33)

WO-8 stopped before any code because §8 and M01 §7 meet SYN-001-shaped phase machinery and verifier code in six
places (D30 F1–F6). A seventh is this round's own finding (B11), and it decides the others: as M01 §7 wrote it, the
flash's equilibrium row does not hold on the VAPOR branch. Each ruling below is normative. It amends §8, §9 (WO-8),
§10.1 (G2, G6 (a), G7), §11, and M01 spec §7 rule 2, as it says. Register R-254 to R-259. ADR 0012 and ADR 0013
each carry an amendment; ADR 0026 records the change to its normative §7 (Amendment 2).

**The invariant of the round: no SYN-001 path changes.** Every generalization below is a branch that no SYN-001
registration takes: an empty `vapour_only`, a provider id other than `pr-c1-v1`, a basis other than C1. Where a
SYN-001 function would need an edit, the PR form is written beside it instead. G2 as amended below is the proof.

**B11 (this round's finding) — The NH₃ equilibrium row is written in R-008's pairwise form (R-254).**

*The defect.* On a single-phase branch the region drops a split's equilibrium rows. It may do so because, in R-008's
form `v_i L − K_i l_i V`, they vanish identically there (`LiftedSplit.dropped`: "the rows a pinned phase satisfies
identically"). The verifier relies on the same identity: its residual checks and its regularity matrix are the
whole declaration's rows at `x_final` (K04 §4.1, §7.1), regime-dropped rows included. M01 §7's
`E = v_NH₃ φ^V − V φ^L` is not zero on the VAPOR branch. It equals `V (y φ^V − φ^L) < 0` for every subsaturated
vapour, so every VAPOR-branch certificate would fail `residual.<U>:C1FL-equilibrium:NH3` by O(1) mol/s. Above NH₃'s
T_c,EOS (G7 (b), 673.15 K) the pure-liquid root does not exist, so the row cannot even be evaluated.

*Ruling.* The row is

    E = L · v_NH₃ · exp(λ^V) − V · l_NH₃ · exp(λ^L) = 0,     kind molar_flow_squared

with these definitions:
- λ^V = ln φ^V_NH₃ of the vapour product's `(n, T, P)` (block `<vapor>:lnphi_NH3:V`);
- λ^L = ln φ^L_NH₃ of the liquid product's `(n, T, P)`, pure NH₃ (M01 §5.2; block `<liquid>:lnphi_NH3:L`);
- V and L are the products' total columns `<vapor>.N` and `<liquid>.N`;
- the tolerance is K04's 9.3e-8 (mol/s)² and the reference is 9.

This is R-008's `v_i L − K_i l_i V` with `K_NH₃ = φ^L/φ^V`, multiplied through by φ^V. It is the form that D13 and
R-230 already named. On TWO_PHASE (`L = l_NH₃ > 0`, `V > 0`), `E = L V (y φ^V − φ^L)`: the root set of M01's row,
so no value M01 registered moves. On VAPOR (`L = l = 0`) and LIQUID (`V = v = 0`) it is exactly `0.0` in floating
point, provided both blocks return finite values at the dormant side (B17).

*Rejected.*
- M01's form: it fails the identity above.
- Keeping M01's row and removing regime-dropped rows from the verifier's residual set: that changes K04 §4.1 for
  every flowsheet and moves SYN-001's certificate.
- `l_NH₃ · (v φ^V − V φ^L)`: equivalent on TWO_PHASE, but it does not read L, so check (e) would need a third form.

**B12 (F1) — The liquid's light-gas flows are columns fixed by zero rows and pinned in TWO_PHASE (R-254).**

`models.assemble` allocates all five liquid flows; it is frozen and is not changed. The C1 flash authors these rows,
with the equilibrium family in component order:

| Row id | Kind | Equation |
| --- | --- | --- |
| `<U>:C1FL-mole:<c>`, all five c | molar_flow | `n_in,c − v_c − l_c = 0` (M01 §7 rule 2, literally) |
| `<U>:C1FL-equilibrium:NH3` | molar_flow_squared | E of B11 |
| `<U>:C1FL-equilibrium:<i>`, i ∈ {H2, N2, Ar, CH4} | molar_flow | `l_i = 0`; reads exactly `<liquid>.n.<i>` |
| `<U>:Ndef:vapor`, `<U>:Ndef:liquid` | molar_flow | `V − Σ_c v_c = 0`, `L − Σ_c l_c = 0` (all five, as SYN-001's flash) |
| `<U>:C1FL-T:<port>`, `<U>:C1FL-P:<port>` | temperature, pressure | exactly SYN-001's `FLASH-T` / `FLASH-P` pattern (both products and the inlet pressure) |
| `<U>:C1FL-duty` | heat_rate | `Q − (Ḣ_V + Ḣ_L − Ḣ_in) = 0`; blocks `<vapor>:Hdot:V`, `<liquid>:Hdot:L`, `<inlet>:Hdot:V` |

The unit owns the variables `<vapor>.N`, `<liquid>.N` and `<U>.Q`. Its ports are `inlet` (vapor), `vapor` (vapor),
`liquid` (liquid) and `duty`.

M01 §7 rule 2 says the light-gas liquid flows are "not variables". The region makes that true with a
`VapourOnlyForm` (B13):
- in TWO_PHASE, the four light-gas liquid columns are pinned at `+0.0` and their zero rows are dropped;
- VAPOR and ZERO_FLOW already pin them;
- LIQUID leaves them to the mole rows (`l_i = n_in,i`), which are zero for the only admissible LIQUID feed, pure NH₃.

*Why pin them and not leave the rows alone.* With free columns, the factorization's roundoff gives `Δl_i ≠ 0` at
`l_i = 0`, and two things follow:
- A positive residue reaches the liquid blocks, which the provider refuses (`light_gas_in_liquid`). Halving the step
  cannot remove that refusal.
- A nonzero `l_i` survives to `x_final`. That defeats the projection's exact-zero rule (ADR 0013 D1), and its
  guard 4 can then refuse the projection.

Pinned, every iterate and `x_final` carry bitwise `+0.0` (G7 (g)).

*Rejected.*
- Rows alone (D30's default): the roundoff above.
- An edit to `assemble`: it is frozen.
- Leaving `l_i` out of the mole rows and out of Ldef: the columns become singletons, which is exact, but LIQUID
  becomes structurally singular and check (d) needs a special case.

**B13 (F2) — `check_agreement` per `SplitRule.vapour_only`; SYN-001's checks run verbatim (R-255).**

- **The rule.** `SplitRule` gains `vapour_only: tuple[str, ...] = ()`, and
  `SPLIT_RULES["c1.tp_flash"] = SplitRule("products", "C1FL-equilibrium", "TP", "C1FL-mole", None,
  vapour_only=("H2", "N2", "Ar", "CH4"))`. With E of kind molar_flow_squared, checks (a), (c), (d), (f) and (g)
  hold for the C1 flash unchanged. Only two checks need a branch:
  - **(b)**, when `vapour_only` is non-empty: the descriptor's rows for the components *not* in `vapour_only` equal
    the unit's molar_flow_squared rows, in `equation_ids` order. Each vapour-only component's row is a row the unit
    authored, of kind molar_flow. The failure code is `lifted_split_rows_disagree(<U>)`, as today.
  - **(e)**, when `vapour_only` is non-empty: the other rows are checked as today. Each vapour-only row reads exactly
    `{<liquid>.n.<i>}`, else `lifted_split_equilibrium_disagrees(<U>, <row>)`.
- **The code shape.** Each check is written `if rule.vapour_only:` with the new branch, and `else:` with today's
  statements unedited. SYN-001's rules have an empty `vapour_only`, so they run today's statements.
- **The form.** `VapourOnlyForm(unit, columns, rows)` is a frozen dataclass in `region.py`, beside `ZeroFlowForm`, so
  `LiftedSplit` and its registered repr digest do not move.
  - It is built by `splits.vapour_only_forms(instances, splits, components)`: the split's liquid flows of the
    vapour-only components, and their equilibrium rows, both in component order.
  - `_pinned` and `_dropped` (region.py:717, :727) add the form's columns and rows **iff the regime is TWO_PHASE**.
  - The executor builds the forms beside `zero_flow_forms` (executor.py:1069) and passes them to `solve_region`.
    `orchestrator/revision.py:380` passes them to `check_agreement`.
  - New check **(h)**, run when `check_agreement` is given `vapour_only` (a new optional argument, as `forms` and
    `dormancy` are; `orchestrator/revision.py` always passes it):
    - every split whose rule declares `vapour_only` has exactly one form, and no other unit has one;
    - each form's columns are spec columns and are exactly that split's liquid flows of its vapour-only components;
    - each of its rows is its unit's row and reads exactly its column.

    The failure code is `vapour_only_form_disagrees(<U>, …)`; a missing form reads `…: no form`.
- **The dormancy registry.** `DORMANCY_RULES[("c1.adiabatic_mixer", None)] = (DormancyRule("outlet", "inlet",
  "C1MIX-energy", None, "VAPOR"),)`. `dormancy_forms` reads a `declared_phase` of `"LIQUID"` or `"VAPOR"` as the
  literal; today it reads only `"LIQUID"` that way, and SYN-001's values are unaffected. The verifier's own
  transcriptions gain the same entries: `DORMANT_OUTLETS` the C1 mixer, and `PRODUCT_MOLE_ROWS` `"c1.tp_flash":
  "C1FL-mole"`.
- **Tests that pin a registry as a literal.** Four tests do:
  - `test_t05_w1a_splits::test_registry_holds_one_rule_per_lifting_model`;
  - `test_t05b_zero_flow::test_the_registry_names_each_models_zero_flow_ids`;
  - `test_t05b_dormancy::test_b23_the_registry_is_the_registered_one`;
  - `test_t05_table_independence::test_the_verifiers_dormant_outlets_are_the_solvers_as_data`.

  Each is restricted to its `syn001.` keys, with its expected literal or reference unchanged. A new M02 test pins
  each registry's full key set and its `c1.` entries exactly. Together the two pin everything the original pinned,
  plus the additions, so no check is narrowed. The T05b reference file is not edited.

*Rejected.*
- A second registry for the C1 rules: two naming sites per lookup, for the sole benefit of leaving four tests untouched.
- Recognizing PR splits by a new quantity kind: that would be a check-policy change.

**B14 (F3) — On the solve side, a `pr-c1-v1` split is classified by M01 §7 rule 3 with τ_dew (R-256).**

There is one solver-side function, `models/c1/phase.py::classify(provider, context, n, T, P) -> (regime, value,
result)`:
- It runs the provider's TP flash of `(n, T, P)` and returns the result. Callers handle a non-`ok` status exactly as
  they do today: the kernel raises `_KernelRefusedError`; admissibility raises `VerifierError`, which the screen
  already converts to `invalid_trial_state`.
- ZERO_FLOW → `(ZERO_FLOW, 0.0)`; VAPOR → `(VAPOR, 0.0)`; LIQUID → `(LIQUID, n_light / n_tot)`.
- TWO_PHASE → value `l_NH₃ / n_tot`, with `l_NH₃` = the result's liquid NH₃ flow and `n_tot = sum(n)`. The answer is
  VAPOR iff value ≤ τ_dew, else TWO_PHASE.

The region dispatches on `provider.describe().provider_id == pr_c1.PROVIDER_ID`. `describe` is uncounted
(`PropertyMeter.describe`), so no SYN-001 count moves. Every other provider id runs today's code.
- **`_kernel`** takes its regime from `classify` at the split's feed, T and P. A VAPOR answer reached through the band
  returns `_pin(VAPOR)`'s values instead of the flash's ulp-sized liquid: vapour = feed bitwise, liquid `+0.0`,
  `V = float(sum(feed))`, `L = 0.0`.
  - Without this, a feed at its own dew point opens TWO_PHASE with `L ≈ ε n`. There the TWO_PHASE Jacobian is
    singular, because the dew point is where the two branches bifurcate, and the attempt cannot converge. G7 (c) is
    this case.
- **`_admissible`**:
  - TWO_PHASE and ZERO_FLOW: as today.
  - VAPOR: admissible iff `classify(feed, T_split, P_split)` is VAPOR, with the value above.
  - LIQUID: admissible iff no light gas flows in the feed (every light-gas flow is exactly `0.0`) and `classify` is
    LIQUID; the value is `n_light / n_tot`.
  - `epsilon` (`SolvePolicy.admissibility_epsilon`) is not read for `pr-c1-v1`. τ_dew belongs to the provider's phase
    convention (R-230), not to the solve policy, and a policy field would change a frozen schema and every policy
    hash.

**τ_dew = 1e-10 lives in `models/c1/__init__.py` as `TAU_DEW`.** It equals ADR 0001 D6's normalized-composition
tolerance, which is the registered resolution of a mole fraction; `l_NH₃ / n_tot` is a mole fraction.

*Rejected.*
- Dispatch by unit model: the rule belongs to the provider's convention, so a later heater-style PR split would need
  a second entry.
- A provider protocol method: the protocol is frozen.
- The region importing the verifier's implementation: SYN-001's region does import `k_values` from the verifier,
  but for PR the solver and the verifier keep separate implementations (R-016). A test compares them as data
  (G7 (k)).

**B15 (F4) — The verifier's `pr-c1-v1` forms. No new tolerance, kind or category; `check_policy_sha256` is unchanged
(R-257).**

*Selection.* `verify_revision` builds its fresh provider from `view.basis.provider_id` through a table the verifier
owns: SYN-001's id → `Syn001Provider`, `"pr-c1-v1"` → `PrC1Provider`, any other id → `VerifierError
provider_unknown(<id>)`. It never calls the binder's `basis_provider`. Each revision-path site below branches on
`view.basis.provider_id`, and for SYN-001 it runs today's line.

The PR forms live in a new module, `verify/pr_c1.py`. It imports only ids, views, `thermo` types, `verify`
primitives and `models.c1.TAU_DEW`, and it joins the files `test_t05_table_independence` scans.

1. **Stream reading.** `checks.stream_of(state, stream, components=COMPONENTS)` gains the keyword. Every
   revision-path caller passes `view.components`: `revision_checks`, `bounds_checks` (new keyword), `Unit.one_sided`
   (a new `Unit.components` field), the declared-port loop, `revision_phase_branch` (new keyword), and projection
   guard 4 (through `project(..., components=)`). At SYN-001 revisions `view.components == ("A", "B", "C")`, which
   G2 asserts.
2. **Fresh-flash enthalpy** (K04 §4.4, ADR 0013 D2), in `pr_c1.enthalpy_flow`:
   - a dormant stream is `0.0`;
   - otherwise flash the stream's own `(n, T, P)`;
   - a TWO_PHASE answer with `l_NH₃ / n_tot ≤ τ_dew` is read as VAPOR at the stream's own state (D2's analogue;
     M01 §7 rule 6);
   - otherwise each non-dormant outlet contributes `sum(outlet.n) * h`, with h from `evaluate_phase` in its phase,
     vapour then liquid, accumulated from `0.0`.
3. **Degeneracy and unresolved routing** (ADR 0012 D7, ADR 0013 D3): none for PR, and `revision_checks` takes an
   empty `Degeneracy()`.
   - A stream that carries light gas has a half-open band (M01 §7 rule 4), so it is never degenerate. D3's floor
     `N ulp(T)/(w τ_flow)` with `w = ∞` is 0, so it is never unresolved.
   - A pure-NH₃ stream within τ_T of T_sat(P) is read in its fresh flash's stable phase. That reading is
     conservative: a wrong reading fails an energy check and never passes one. It is a stated limitation.
4. **Split admissibility and the independent split** (K04 §4.7), in `pr_c1.split_checks`:
   - **Dormant**: as today.
   - **VAPOR branch** (`Σ l = 0 < Σ v`): `phase_admissibility.<U>.<S>.dew`, one-sided.
     - Value: `l_NH₃ / n_tot` of a fresh flash of the split's feed at the split's `(T, P)`, by the verifier's own
       copy of B14's rule; `0.0` for a VAPOR answer.
     - Pass iff value ≤ τ_dew; tolerance τ_dew; reference 1.0.
     - Near threshold iff τ/10 < value ≤ 10 τ (ADR 0007 D2.4).
   - **TWO_PHASE**: `phase_admissibility.<U>.<S>.closure`, two-sided against `tolerances["temperature"]`, reference 100.
     - Value: `|g / g_T|` in kelvin, where `g = ln(v_NH₃ / Σv) + ln φ^V_NH₃(v, T, P) − ln φ^L_NH₃(T, P)` and `g_T` is
       its T-derivative.
     - Both come from fresh `evaluate_phase` calls on the state's own phases (VAPOR on the stored v, LIQUID on the
       stored l) with `derivatives=("T",)`.
     - It is the first-order distance of the vapour from its own NH₃ dew temperature at fixed `(v, P)`. The pure
       liquid has no bubble point to compare (M01 §7 rule 4), so this is SYN-001's `max(|T − T_b|, |T − T_d|)` with
       the T_b half vacuous.
     - `unsupported` with `closure_nonpositive_phase` (as today), `closure_<status>` on a provider refusal, or
       `closure_degenerate` if `g_T == 0.0`.
   - **LIQUID branch** (`Σ v = 0 < Σ l`): `phase_admissibility.<U>.<S>.bubble` is `unsupported`, reason
     `pr_liquid_regime_unsupported` (N5).
   - **Independent split**: SYN-001's formula (`independent_split.<U>.<S>.total` and `.<c>` against τ_flow, from a
     fresh flash of the feed). It is written again in `pr_c1.py` rather than by editing `_split_checks`.
5. **Declared ports**, in `pr_c1.declared_port_checks`, with the same iteration and ids as `_declared_port_checks`:
   - A declared VAPOR port: value `l_NH₃ / n_tot` of a fresh flash of the stream's own `(n, T, P)`, one-sided against
     τ_dew as in item 4.
   - A declared LIQUID port: `unsupported`, reason `pr_declared_liquid_unsupported`. No C1 entry declares one; the
     flash's liquid product is judged by its split's checks.
   - Dormant and unlifted streams: as today.
   - *Why not SYN-001's kelvin distance:* it cannot see condensation below `l/n ≈ 1.5e-9`. A latent heat of
     2.3e4 J/mol over `c_p ≈ 35` J/(mol K) makes `l/n = 1e-9` a 7e-7 K distance, which is under τ_T. The units'
     admissibility (§8) is the band, and the certificate judges what the units claimed.
6. **`MODEL_CHECKS`**: every rule below is an existing SYN-001 function, reused unchanged.

   | Model | Material | Energy | Specification | `declared_ports` |
   | --- | --- | --- | --- | --- |
   | `c1.feed_source` | — | — | `_feed_specification` | — |
   | `c1.product_sink` | — | — | — | — |
   | `c1.stream_splitter` | SYN-001 splitter's | SYN-001 splitter's | SYN-001 splitter's | — |
   | `c1.adiabatic_mixer` | `_mixer_material` | `_mixer_energy` | — | `(("inlet", True), ("outlet", False))` |
   | `c1.tp_heater` | `_pump_material` (plain `in − out`; nothing is lifted) | `_heater_energy` | `_heater_specification` | `(("inlet", False), ("outlet", False))` |
   | `c1.tp_flash` | `_flash_material`, then `material_balance.<U>.liquid.<i>` = `l_i`, two-sided τ_flow, for each vapour-only i (the verifier's own reading of R-143) | `_flash_energy` | `_flash_specification` | `(("inlet", False),)` |

   The envelope sets gain the C1 ids: `FEED_MODELS` gains `c1.feed_source`, `PRODUCT_MODELS` gains `c1.product_sink`,
   and `EXTERNAL_DUTY_MODELS` gains `c1.tp_heater` and `c1.tp_flash`. The reactor's entries are WO-9's.
7. **Qualification.** Every PR admissibility check appends to `qualification(provider)` the text `"; pr-c1-v1 form
   (M01 §7; design note §14.2 B15): <dew band, liquid NH3 fraction of a fresh TP flash | first-order distance in K
   from the vapour's NH3 dew point>"`.

*The tolerances are all registered already.*
- τ_dew: R-230, equal to ADR 0001 D6's 1e-10, and at least 1e4 above both the flash's O(ε) dew-point liquid and y*'s
  bisection error.
- The K04 policy's τ_T, τ_flow and τ_E.

Nothing new is registered, and F4 needs no specifier.

*Rejected.*
- D30's closure `|y_NH₃ − y*| ≤ 1e-10`. It is a tolerance outside the check policy. It is also 500 to 16 000 times
  tighter than E's own row tolerance allows: `|E| = 9.3e-8` (mol/s)² permits `Δy ≈ 5e-8` at the loop's flash
  (L ≈ 0.4, V ≈ 7 mol/s) and `1.6e-6` at F1 (L ≈ 0.11). So it would fail at states every residual row passes.
- A closure by bisection for the exact dew temperature: it would put a new iterative routine in the verifier, and
  the first-order distance differs from the exact one by a second-order amount, far below τ_T.
- Editing `_split_checks`, `_declared_port_checks` and `enthalpy_flow` into provider-generic functions: that touches
  SYN-001's arithmetic, whose bitwise pairing (W1.d) is protected by leaving it alone.

**B16 (F5) — Non-lifted vapour outlets are refused by the causal evaluate and judged by the certificate. There is no
solve-time screen and no new outcome (R-256).**

This is SYN-001's existing pattern for its declared-liquid outlets: R-007 at the causal evaluate, and K04's
declared-port check at the solution.
- **Mixer and heater.** `c1.adiabatic_mixer.evaluate` and `c1.tp_heater.evaluate` classify each flowing inlet and the
  outlet with `models/c1/phase.py`. Anything but VAPOR returns `unsupported`, with the message `vapour_phase_inadmissible:
  <port> <stream>: liquid NH3 fraction <value:.3g> > 1e-10`, or `…: LIQUID` for a pure-NH₃ liquid. The traversal
  initializer handles that `unsupported` the way it already handles SYN-001's mixer; the test records which outcome
  that is.
- **The EO solve.** A solve that converges with such an outlet is `CONVERGED` with a `FAILED` certificate naming
  `phase_admissibility.<U>.<port>`. §8's "the existing phase-inadmissible outcome" is withdrawn: no such outcome
  exists, and adding one is a frozen-schema change for a case the loop never visits.
- **The flash.** `evaluate` refuses a feed with no light gas flowing (`unsupported`, `pure_nh3_flash_unsupported`).
  Otherwise it returns the provider's split, classified by B14: a VAPOR answer reached through the band reports
  vapour = feed and liquid `+0.0`.

*Rejected.*
- A region screen of non-lifted outlets with a typed closure: it needs a new outcome literal, and the certificate
  already types the failure.
- Lifting them: two-phase heaters and mixers are rejected by R-230.

**B17 (F6) — At exact dormancy a PR block evaluates nothing that depends on composition; a vapour block takes the
ideal-gas limit (R-258).**

`Ḣ_V = Σ n_j h^ig_j(T) + D(n, T, P)`, where `D = n_tot h^dep` is positively homogeneous of degree one and nonlinear in
n. So `Ḣ_V` is not differentiable at `n = 0`. No Jacobian there is *the* derivative, and the frozen pairing of
residual and Jacobian can only be met by a registered convention. "Exact dormancy" means every flow of the block's
stream is `+0.0` or `−0.0`. The convention:

| Block (ids named after the stream, R-008) | At exact dormancy |
| --- | --- |
| Vapour enthalpy flow `<S>:Hdot:V` | Value `0.0`. `∂/∂n_j = pr_c1.h_ig(T, j)`, M01 §4.5's closed form, read directly because the provider exposes no per-component property. `∂/∂T = ∂/∂P = 0.0`, which is exact because `Ḣ(0, T, P) ≡ 0`. |
| Vapour `<S>:lnphi_NH3:V` | Value `0.0` and every derivative `0.0` (the ideal gas). |
| Liquid enthalpy flow `<S>:Hdot:L` and liquid `<S>:lnphi_NH3:L` | Pure NH₃ is composition-free, so ADR 0001 D3.1 does not forbid evaluating it. Call the provider at the probe `(0, 0, 1.0, 0, 0)` at `(T, P)` in LIQUID; if it answers `no_liquid_root`, call it in VAPOR (the pure fluid's only root). The enthalpy flow's value is `0.0`, with `∂Ḣ/∂n_j = h(probe)` for every j. The ln φ value and its T and P derivatives come from the probe; its n-derivatives are `0.0`. |

*Flowing streams.*
- `Ḣ = sum(n) · h`, with `∂Ḣ/∂n_j = h + sum(n) · ∂h/∂n_j`, `∂Ḣ/∂T = sum(n) · ∂h/∂T`, and the same for P.
- ln φ and its derivatives come from the provider.
- A flowing liquid with no liquid root, or one carrying light gas, gets the provider's refusal, which is an invalid
  trial; the fallback above never applies to it.
- Each block asserts at construction that its provider's id is `pr-c1-v1`.

*Why this convention.*
- It is always defined. The pure-component directional derivative `h_j(T, P)` does not exist for NH₃ as a vapour at
  the loop's 253–300 K and 1e7 Pa.
- It is composition-free and exact in the ideal-gas limit.
- It affects only Newton's direction from an exactly dormant iterate and the dormant columns of a regularity matrix,
  never a converged value.
- The liquid fallback is what lets E and the duty row be evaluated on the VAPOR branch above T_c,EOS (G7 (b)).

*Rejected.*
- Refusing a Jacobian at dormancy: a dormant feed's flows are live columns of the downstream energy rows, so G7 (d)
  and every dormant non-lifted vapour stream would become unsolvable.
- A probe at an equimolar composition: arbitrary, and the metastability guard can refuse it.
- Zero flow-derivatives: Newton would ignore the enthalpy carried by flow re-entering a dormant stream.

*Consequence.* A finite-difference Jacobian witness differs from the convention at exactly dormant PR columns by
design. Tests exclude those columns from FD comparisons and assert the convention there instead.

**B18 (D27) — Confirmed as built.** The binder refuses a mismatched pin with `Unbound`,
`model_variant_mismatch(<instance>)`, exactly as G6 (a) says. A revision that cannot be bound cannot be validated
READY, so `solve` admission refuses at T07 §5.3 step 2 with `revision_not_ready`, and STR-01..05 are `NOT_RUN`
naming the cause. G6 (a)'s "`revision_unsupported`" is corrected to this.

*Rejected:* surfacing the binder's refusal as step 3's `revision_unsupported`. That reorders T07's frozen admission
steps for one cause.

**B19 (D33) — `variant_id` in `env-manifest.json` is provenance only (R-259).** The environment is a function of
the lock alone (`env_id`). The child is not part of it; the child's identity is the variant's `runner_sha256`.
- `env verify --variant X` compares `env_id`, the lock hash, the interpreter and the installed distributions against
  X's pins. It reports the manifest's `variant_id` as information and never as a difference.
- `env build --variant X` on an existing directory whose `env_id` equals X's and which verifies is a successful
  no-op. A different `env_id` is refused, as today.
- The field keeps its name, so existing manifests stay valid.
- `test_the_environment_verifies_against_its_pins` moves to v2, and a new test verifies one built environment
  against both v1 and v2.

*Rejected:* one environment per variant, which would mean an identical 85-distribution venv rebuilt for every
runner change.

**WO-8 as amended (each item lead-lane Opus, design-lane review of the whole after WO-8.5):**

| Item | Content | Acceptance |
| --- | --- | --- |
| WO-8.1 | `models/c1/__init__.py` `TAU_DEW`; `models/c1/blocks.py`: the four block kinds of B17 with their ids; `models/c1/phase.py` `classify` (B14) | Unit tests: values equal the provider's at V1, V2, L1 and F1's phases (`Ḣ == sum(n) * h` bitwise); flowing Jacobians match central FD (step 1e-6 relative) within 1e-7 relative of each entry's magnitude; every dormancy value of B17 asserted bitwise (including at 673.15 K, 1e7 Pa, where the liquid probe falls back to VAPOR); a flowing liquid without a liquid root is refused; `classify` on F1–F14 equals the provider's phase except F4 (VAPOR by the band); G7 (h) |
| WO-8.2 | Units and manifests: `c1.feed_source`, `c1.product_sink`, `c1.stream_splitter` (the reuse check recorded in the commit), `c1.adiabatic_mixer`, `c1.tp_heater`, `c1.tp_flash` with B12's rows; causal evaluates with B16's refusals; `MODEL_BUILDERS` entries | Each unit square in a minimal flowsheet; G7 (e)'s causal halves; the flash's evaluate at F1, F4 and F11 |
| WO-8.3 | `SplitRule.vapour_only`, `SPLIT_RULES` entry, `VapourOnlyForm` and its plumbing, `check_agreement` (b), (e), (h), the dormancy registry, the region's `_kernel` / `_admissible` dispatch (B13, B14); the four registry tests restricted and the M02 full-set tests added | G2 as amended; G7 (g), (i); agreement passes on every G7 flowsheet |
| WO-8.4 | Verifier (B15): `verify/pr_c1.py`, the fresh-provider table, the dispatch sites, `stream_of` components, `MODEL_CHECKS` and envelope entries, the `zero_flow.py` registries, independence-test coverage | G2 (T07 corpus certificates byte-identical); G7 (j), (k) |
| WO-8.5 | The six registered tests of M01 §7 (§8) and G7 (a)–(e) | G7 as amended, except (f), which moves to WO-9 (it needs the loop's reactor) |

WO-8's acceptance becomes: G7 (a)–(e) and (g)–(k), and G2 as amended. WO-9 adds G7 (f) to its own acceptance and
gives the C1 reactor's entries in `MODEL_CHECKS` and `REACTING_MODELS`, with its duty row on B17's vapour blocks.

**Gates as amended** (also written into §10.1):
- **G2** gains four checks:
  - (i) at every T07 corpus revision, `view.components` equals SYN-001's basis components;
  - (ii) the 50 T07 corpus certificates are byte-identical, by the SHA-256 of each canonical document, before and
    after WO-8.3 and WO-8.4;
  - (iii) the descriptors' repr digest (`SPLITS_REPR_SHA256`) and the T05b reference file are unchanged;
  - (iv) the only existing tests edited are B13's four, with their literals unchanged, and D12's.
- **G6 (a)** reads as B18.
- **G7** gains:
  - **(g)** At every Newton iterate of every G7 solve, and at `x_final`, the four light-gas liquid columns are bitwise
    `+0.0`, and `material_balance.<U>.liquid.<i>` is `0.0`.
  - **(h)** B17's dormancy values, asserted on the compiled blocks.
  - **(i)** `check_agreement` raises its specific code on each of five mutated C1 flashes:
    - a zero row removed;
    - a zero row that also reads `v_i`;
    - E authored with kind molar_flow;
    - no `VapourOnlyForm` supplied;
    - a form naming the NH₃ column.
  - **(j)** Every C1 certificate carries `check_policy_sha256` `21c44e10…`, and its `transformations.projection.judged_at`
    is recorded. On constructed states each PR form fails on its far side:
    - `.dew` and the declared vapour port fail at `l/n = 1e-8`;
    - `.closure` fails with T moved 1e-4 K off a TWO_PHASE root (value ≈ 1e-4), and passes at the root with
      `|value| ≤ τ_T / 10`.
  - **(k)** The solver's and the verifier's copies of the band rule agree, as data, on F1–F14 and on F4's feed with
    NH₃ multiplied by `1 + δ`, δ chosen to put `l/n_tot` at 0.5 τ_dew and at 2 τ_dew (δ ≈ 8.1e-10 and 3.2e-9; at F4,
    `l/n_tot ≈ 0.0616 δ`).
  - **(b)** additionally: every `C1FL-equilibrium` row is exactly `0.0` at the root, and the certificate is `VERIFIED`.
  - **(c)** additionally: the kernel opens VAPOR, `.dew` ≤ τ_dew/10, and the certificate is `VERIFIED`. Record the
    outcome, `rcond_1` and the verdict for F4's feed with NH₃ multiplied by `1 + δ`, for δ = 1e-8, 1e-7 and 1e-5
    (`l/n_tot ≈ 6e-10`, 6e-9 and 6e-7; risk K18).

**Left for a specifier — one optional ratification, nothing blocking.** (S1) Ratify M01 spec §7 Amendment 3, which
restates rule 2's row in R-008's form (B11) and how the light-gas liquid flows are realized (B12). *Default: proceed.*
The TWO_PHASE root set is unchanged, and no closed form, provider behaviour, registered state or M01 assertion
moves. Nothing in F4 needs one: every tolerance it uses is already registered (B15).

**Risks added to §11:** K14 to K18.
