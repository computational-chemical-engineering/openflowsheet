# ADR 0033 — External-model execution and experiment records: a pinned out-of-process child per attempt, a three-layer kill chain, process-level experiment identity, an exact cache of deterministic outcomes

**Status:** Proposed, 2026-10-08. Accepted when M02's evidence manifest is `tested` (design note gates G1–G6, G10,
G11) and the design-lane review of WO-3/WO-4 is recorded.
**Author:** design lane (`architect`), M02.
**Normative text:** `docs/design/M02-pymrm-adapter.md` §2, §3, §5. Register R-220–R-224, R-229, R-233.
**Amends:** ADR 0020 D3 (the forced kill reaches the worker's process group); ADR 0019 (Amendment 4, part 1: the
`experiment` job operation). Pointer paragraphs are added to ADR 0019 and ADR 0020 when M02 merges (WO-13).
**Affected requirements:** W21 (execution, provenance); blueprint §5.1, §5.2, §7.7, §9.1, §11.2, §11.3, §14.4.
**Affected packages:** M02; M04 (trains on the records), M05 (true-model calls and their accounting), M07.
**Companions:** ADR 0027 (the boundary whose `ExternalEvaluation` the adapter implements), ADR 0007 (classes),
ADR 0002 (canonical hashing), ADR 0022/R-143 (the pin, used by reference).

## Context

The group's reactor (pin `6089593`) needs numpy 2.5.3 and scipy 1.18.1, which differ from the project's pins, plus
numba and pymrm, which the project must not depend on. One design-grid solve takes about 9 s and is bitwise repeatable
on one machine (M01.A43). The application runs each job in a fresh worker process that is killed after `grace_s` on
cancel (ADR 0020). No subprocess-based external call exists in `src/`; T08's precedent had no timeout. Blueprint §9.1
requires failed experiments to remain in the dataset with failure labels, §11.2 that a retry not duplicate an expensive
experiment, §11.3 that isolation profiles state their real guarantees.

## Decision

**D1. One child per attempt, inside the job worker.** An external evaluation runs as a fresh subprocess of the job
worker, synchronously, in a venv built by `python -m openflowsheet.adapters.pymrm.env build` from a hash-pinned lock
and a `git archive` export of the pinned commit, with a merged species database from M01's overlay. The child script
(`adapters/pymrm/child.py`) imports only stdlib, numpy, scipy, pymrm and the exported `reactor` package; nothing in
`openflowsheet` imports it. The reactor's code is used by reference and never copied into the repository.

**D2. The kill chain and the isolation profile.** (L1) The adapter polls the child every 0.2 s, calls the job's
cooperative check and its per-attempt deadline, and terminates with SIGTERM, 2.0 s, SIGKILL, then reaps. (L2) The
worker makes itself a process-group leader (`os.setpgid(0, 0)`, its first statement) and the executor's forced kill
becomes `os.killpg(worker_pid, SIGKILL)` while the worker is unreaped, falling back to `Process.kill()`; **this widens
ADR 0020 D3's "kill" from the worker to the worker's process group**. (L3) The child holds its stdin as a lifeline and
exits on EOF, and exits on its own deadline (`deadline_s` + 30 s). Profile **`external-subprocess-v1`**: separate
interpreter and dependencies, separate address space, environment allowlist, private working directory, one thread,
wall-clock limit, termination on cancel, forced kill and parent death, output from one validated file, verified code
identity; **no** filesystem confinement, network isolation, memory or CPU quota, or syscall filtering — not a sandbox;
trust rests on provenance. Linux is registered; macOS best effort; Windows is refused before spawn.

**D3. Variants.** An external model configuration is a **variant**: an immutable document (`model-variant.schema.json`)
naming the reactor commit and rights, the environment lock, the child's SHA-256, the overlay, the configuration and
solver profile, the boundary contract (pressure convention, ε_P, projection, defect limit, provider, hard and data
domains), the accuracy contract, execution limits and the coupling block. Its `document_sha256` is its identity.
Variants are append-only package data with a pinned registry; any change is a new variant. The stand-in is the
in-process variant `standin-x025-v1` (synthetic).

**D4. Experiment identity is process-level.** `experiment_key` = `document_sha256` of {model id, variant id and SHA-256,
provider identity, N_tubes, sweep ratio, components, the exact binary64 inlet n, T, P, the environment fingerprint's
SHA-256}. Nothing is quantized. The fingerprint (interpreter, platform, CPU model and flags hash, package versions,
thread and environment allowlist values, export tree, merged database, lock and child hashes) is measured by a
handshake once per job.

**D5. Records and retention.** `experiment.schema.json` defines `request`, `result` and `attempt`. Every execution writes
an attempt; a **deterministic** outcome — an execution that completed (any boundary status, including refusals and
`not_converged`) or a boundary refusal before execution — writes one result, once, never overwritten. A **transient**
outcome (`timed_out`, `crashed`, `protocol_error`, `spawn_failed`, `environment_*`, `cancelled`) writes attempts only.
Nothing is deleted; no record carries fabricated outlet values. Records live under `<project>/experiments/<key>/` with
rows in the existing `artifacts` table; a cache hit adds a row for the consuming job whose parent is the producing row.
No store table is added.

**D6. The exact cache.** Keyed by D4, per project, serving deterministic results only. A per-key `flock` (non-blocking,
retried every 0.2 s with the cooperative check) guarantees one execution per key per project; the cache is re-read after
the lock is taken. Cache bypass (experiment jobs only) re-executes, records the repeat and whether it is bitwise equal,
and never overwrites; a differing repeat is appended as a determinism finding.

**D7. Retry and timeout.** One retry after `crashed`, `protocol_error` or `spawn_failed`; none after `timed_out`,
`environment_*` or `cancelled`. Per-attempt `timeout_s` from the variant (120 s for the design-grid variant, re-registered
from the coverage sweep as a new variant only if it changes). The job's wall time is ADR 0020's.

**D8. The accuracy contract and no reactor warm start.** Each variant declares `precision_floor_rel` (10⁻⁶, the
registered path-independence bound; measured 1.56 × 10⁻⁸) and the design grid's discretization estimate
(`reference_values.yaml` → `derived_from_measured.discretization_estimate`); every result carries them. The child runs
the cold S1–S3 strategy only; the child's computation is a pure function of its request (every limit a count, never a
wall clock).

**D9. The `experiment` job operation (ADR 0019 Amendment 4, part 1).** `job_request.operation` gains `experiment`
(`$defs/experiment_body`: model reference, SI inlet, N_tubes, cache mode), right `execute`. The job ends `completed`
whatever the experiment's outcome; its outputs are the request and the result or the attempts (new `artifact_ref`
kinds `experiment_request`, `experiment_result`, `experiment_attempt`); `get_job_result` returns the result or the last
attempt (a `oneOf` widening). Idempotency is ADR 0019 D3's.

**D10. The evaluation seam.** `ExternalEvaluation` may return `ExecutionFailure(kind, message)`, which the boundary maps
at its check 6 to `error`, `external_<kind>`. M01's other checks, codes and assertions are unchanged.

**D11. Experiment-internal property calls are unmetered** by the solve's `max_property_calls`; each result records its
own count (a cache hit must not change a solve's deterministic budget, ADR 0007 D5.1).

## Alternatives considered

- **A separately managed experiment job per evaluation.** Rejected: it needs job-to-job scheduling and deadlocks at
  `max_workers = 1`, and the experiment job's own worker would still need a grandchild for the reactor's pins.
- **A persistent per-job reactor server.** Rejected for now: state can carry between experiments and the kill semantics
  are harder. Revisit if the measured start-up share exceeds 30 % (R-224).
- **Importing the reactor in the worker.** Rejected: pin conflicts; a native crash would kill the worker.
- **Kill by pid only / `PR_SET_PDEATHSIG` only.** Rejected: a forced kill would orphan the grandchild; PDEATHSIG is
  Linux-only and tied to the spawning thread.
- **Tube-level identity.** Rejected: it would leave the boundary's provider calls (inlet flash, Q) outside the identity
  and split one consumer-visible fact into two records.
- **Caching only `ok`; caching timeouts.** Rejected: re-running known refusals costs 9 s each; a timeout is a fact
  about load, not about inputs.
- **Warm-starting the reactor from a neighbour.** Rejected for M02: the result would depend on history at the 10⁻⁸ level,
  which an exact cache cannot key (R-224).
- **A new store table for experiments.** Rejected: files plus the existing `artifacts` table and a kernel lock suffice,
  and avoid a store migration.

## Consequences

- The default gate exercises the whole pipeline without PyMRM: the stand-in in process, and a synthetic child of the
  project's own interpreter for every failure path and the kill chain.
- Cache entries never cross machines (the fingerprint is in the key); records do, as R3 evidence.
- ADR 0020's tests must stay green with the process-group change; terminal signals already do not reach workers.
- New schemas: `experiment`, `model-variant`; additive edits to `job`, `application-results`. New floats are classified
  in a separate `numerical_policy_external` table; the existing numerical policy id does not move.

## Migration

None for stores (no table added) or revisions (native models unchanged). Released 0.1.x clients that validate `job`
documents against 0.1 schemas would reject the new operation and artifact kinds (J5: open for consumers).

## Acceptance evidence

Design note G1 (schemas, fixtures from real runs), G3 (kill chain, with stated time bounds), G4 (records and cache),
G5 (experiment job), G6 (b) (variant pins), G10 (M01.A41–A48 adapter halves), G11 (coverage and timing).
