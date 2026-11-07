# X02 — Declared warm starts for external and coupled units: design note

Status: design note (design lane, `architect`), 2026-11-07. Package X02, roadmap 0.4 (ADR 0056 row 2, ADR 0057). Brief
`docs/briefs/X02-architect.md`. The normative decisions are in **ADR 0070** (Proposed), which carries ADR 0019
Amendment 15. Paths are under `src/openflowsheet/` unless stated otherwise. The note stands alone. Every number in it
comes from a record named beside it.

## 1. Problem and scope

A run of a coupled flowsheet (route `revision_coupled`: an extent-fixed reactor embedding, with an outer Broyden
iteration on w = (X̂, ΔT̂) per external unit and an external child per experiment) always starts cold today, at three
levels:

| Level | What starts | Today | Registered as |
| --- | --- | --- | --- |
| outer | the coupling iterate w₀ | the variant's `coupling.initial` (0.15, 80 K) | R-287 (`coupling_initial.*` refused) |
| inner | the flowsheet state x₀ at k = 0 | `traversal-G0-v1`, or ADR 0024's lineage candidate under `T08-warm-v1` | ADR 0024 |
| external | the child's own solve (reactor tube profile) | cold S1 (trace inlet) → S2 → S3, every call | R-224, ADR 0033 D7, M02 N6 |

X02 lets a run **declare** a start at each level, from a previous converged run or a user iterate. The certificate
judges only the converged answer (§2 I3 makes "only" precise). Every identity that can hold a start-dependent result
states whether a start was used. Nothing that runs cold changes by one bit.

**In scope.**
- **Part A.** An explicit start for the coupled route: w₀ and x₀ from a named previous solve job, or w₀ from a user
  iterate. Its experiments stay cold.
- **Part B.** A warm-chained reactor variant: each experiment after the first starts from the converged tube profile
  of the unit's previous experiment in the run, and the first starts from the declared source's final profile. The
  experiment key carries the start.
- **Part C** (a defect fix found in this pass). `T08-warm-v1` on the coupled route does not record the k = 0 inner warm
  start in the bundle (§3.3).
- ADR 0024's deferred explicit form (`warm_start.job_id`), on `revision_eo` as well, because it is the same code.

**Out of scope.** F6–F8 builds; OPT; RRC; X05; dynamic initial conditions (ADR 0066 D5). Also out of scope:
- study integration (M03 sweeps, the M05 trust-region study passing an incumbent's job id);
- starts on the `experiment` operation;
- changing what `T08-warm-v1` does on the coupled route (Q2);
- a persistent child;
- carrying the Broyden matrix;
- re-checking warm experiments cold;
- cache lookups that ignore the start (§8 R5);
- platforms other than Linux (X07).

## 2. Constraints and invariants

- **I1 — Cold bit-identity.** For every request without `warm_start`, under every registered policy and on every
  registered variant (v1–v3, the stand-in), the following stay byte-identical:
  - every experiment request and `experiment_key`;
  - every attempt and result document;
  - the coupling record (`external-coupling.json`);
  - `solve-path.json`, the solution state and the certificate;
  - the R0 projection and every replay verdict.

  F0 (`scripts/corpus_identity.py --check`, M1–M9) passes unchanged. Every existing test keeps its node id and its
  expectations, with two registered exceptions: the Q26 scalar inventory (I7) and the surface digest chain (§5.1).
- **I2 — Exact caches stay exact.** A result made from a start is never served for a request without that start, and
  a cold result is never served for a warm request. The start's member appears in a key only when a start was used.
  The thermo caches (`thermo/cache.py:175-215` exact, `:270-290` approximate guesses) are untouched.
- **I3 — The certificate judges the converged answer.** Let V = F(x_K, w_K, A(inlet_K)): the verdict as a function of
  the final inner state, the final iterate and the external answer at the final inlet (`coupled_run.py:796-851`:
  EXT-COUPLING:<unit>:xi and :T, the bitwise inlet attribution, the floor ratios).
  - No input of F may come from the start, the iterate history or the source run.
  - Under Part A, A is a cold evaluation, a pure function of its request, so V is exactly start-independent given the
    final state.
  - Under Part B, A is warm. Its distance from the cold answer at the same inlet is bounded by the variant's registered
    `measured_path_independence_rel`, which must sit at least one decade below its `precision_floor_rel` (gate G5).
    *Amended (X02 review, 2026-11-07, A-3):* the band 1e-7 < max ≤ 1e-6 in G5b is struck: it contradicts this rule. G5b passes iff
    max ≤ `precision_floor_rel`/10; otherwise the variant is not registered. Raising the floor is a separate
    decision: the EXT-COUPLING floors scale with it.
    The EXT-COUPLING floor ratios already carry that floor.
  - The start may change *which* converged point is reached: within the coupling tolerance (Part A), or which steady
    state where a model has several (§8 R2). It never changes what is accepted as converged.
- **I4 — Replay from the bundle alone** (ADR 0024 D5). A warm run reruns from its recorded start. The rerun makes no
  store lookup and writes the same record. ADR 0007 D4's mode rules are unchanged.
- **I5 — Frozen core.**
  - No item that ADR 0060–0067 lists as core changes.
  - The K03 interface `SolvePolicy` and `schemas/solve-policy.schema.json` are unchanged.
  - Contract schemas change only through ADR 0019 Amendment 15 (ADR 0070), and only by optional members.
  - Amendment 14 is left to X05 (its Q-F3), so X02 takes 15.
- **I6 — Variant immutability.** `adapters/pymrm/child.py` is pinned by `runner_sha256`
  `0d2c345f1d414c457e047f698b9e6a3235701b91c4990ef2300d4375f753d893` in variants v1–v3. Its bytes never change.
- **I7 — Q26 / ADR 0020 D7.** No operation accepts a state from outside except at a registered full path, with a
  W14-path test showing that the state is only ever a start. X02 registers one path: `body/warm_start/coupling/*/{X,
  dT_K}` on `submit_job` (solve).
- **I8 — The run never fails because of a start** (ADR 0024 D3's principle). A start is checked before it is accepted.
  Failing a check is recorded, and the next source follows. Nothing falls back after acceptance at the flowsheet
  level. The one bounded exception is the child's own fallback (D7), which keeps a warm request from refusing where a
  cold one would not.
  *Amended (X02 review, 2026-11-07, A-5):* The run never fails because of a start that fails a check. A start
  that passes its checks is the run's start: from (0, −50) the stand-in ends `COUPLING_NOT_CONVERGED`
  (`external_refused(nh3_below_trace)` at k = 0), where the cold run verifies (G6). That is recorded, not a fallback
  case (D3).
- **I9 — Scientific conduct.** No placeholder paths:
  - an unsupported start is a recorded `absent` or `rejected` with a reason, never a silent cold start;
  - correctness fixtures have analytic or independent expectations (the synthetic warm child, §7 G4);
  - self-generated outputs are regression fixtures only.

## 3. Measured facts that decide the design

### 3.1 Where a reactor call spends its time

Source: 48 v3 experiments, `benchmarks/m07/journey/2d945b5…/m05/trust-region-study-real.experiments.json`, attempt
diagnostics. Medians:

| Stage | Median wall (s) | Share |
| --- | --- | --- |
| whole call | 48.2 (min 15.1, max 88.5) | 1 |
| start-up (interpreter, imports) | 1.8 | 0.04 |
| S1 (cold trace inlet; 38 steps) | 5.4 | 0.11 |
| S2 (true inlet from S1; 30 steps) | 3.3 | 0.07 |
| S3 polish (12 steps) | 1.5 | 0.03 |
| KPI-drift certificate | 29.4 | 0.37 |

A child-level warm start can remove S1 (11 %) and shorten S2. The certificate dominates and must run whatever the
start was. Expected gain: **about 11–15 % per call.**

*Amended (X02 review, 2026-11-07, A-1):* *Measured (G5c, `evidence/X02/69c4a24d…/`):* the gain did not materialise. At 8
inlets the warm chain took 287 s against 133 s (g12) and 383 s against 420 s (cand-C1-P1): about 21 % slower
overall, with per-inlet ratios from 0.37 to 4.60. S1 was saved, but the KPI-drift certificate's round 2 ran at 6 of
8 warm inlets against 4 of 8 cold. The certificate's cost is not independent of the start.

### 3.2 Where a coupled run spends its calls

`benchmarks/m02/g12-real-loop-v3.json` (`c1-loop-real.json`, v3, cold from (0.15, 80 K)):

- 4 outer iterations (k = 0…3), each with one call: 59.6, 23.4, 58.2 and 20.7 s, 162 s in all;
- final w = (0.168388, 78.670 K), ρ = 0.292;
- final r_ξ = −4.40e-6, r_T = 2.92e-3 K;
- floor ratios 65 (ξ) and 13 (T).

An outer start at a nearby converged w removes whole calls. A same-revision restart converges at k = 0 (one call, or
none on an exact-inlet cache hit). *Amended (X02 review, 2026-11-07, A-2):* **The outer start (Part A) is the lever:** G5e on v3
restarted in 1 outer iteration and 1 call (24.9 s) against 4 iterations cold (174.9 s). The child start (Part B) gave
no gain (§3.1).

### 3.3 Code facts

- **`T08-warm-v1` on `revision_coupled` loses its record.**
  - `solve_coupled` (`application/coupled_run.py:662-700`) consumes the candidate in the k = 0 inner solve only.
  - `run_revision_session` writes `solve_path["warm_start"]` from `result.run.warm_start` (`revision_run.py:837-839`).
    `result.run` is the *final* inner run, which ran with a `user_start` and so carries no record whenever K ≥ 1
    (ADR 0024 D4: written "iff … no user_start was given").
  - The k = 0 inner label is `"route_initializer"` even when the candidate was accepted (`coupled_run.py:682`).
  - So a coupled `T08-warm-v1` bundle does not disclose its start, and its rerun (`revision_run.py:1111`) starts k = 0
    cold. This breaks ADR 0024 D4/D5.
- **The child is chosen by a fixed path.** `pinned_program` (`adapters/experiments/backends.py:225-230`) hard-codes
  `pymrm/child.py`. `child.py` checks `profile == PROFILE` and hashes its own `__file__` as `runner_sha256`
  (`child.py:441`, `:908`).
- **Closed and open schema members.**
  - `model-variant.schema.json` is closed, but `evaluation.profile` and `evaluation.configuration` are open,
    child-defined objects. A start capability therefore needs no variant-schema change.
  - `experiment.schema.json` closes `request`, `result`, `coupling_unit` and `coupling`.
  - `job.schema.json#/$defs/solve_body` is closed (`revision_id`, `policy_id`).
  - `solve-policy.schema.json` is closed, and `SolvePolicy.from_document` requires every member.
- **The coupling loop.** `couple` (`orchestrator/coupling.py:286-…`) starts at `block.initial` (`:316`) with B = −I.
  An inner failure at k = 0 returns at once, with no experiment run (`:362-366`). Units are in unit-id order
  (`coupled_run.py:118-121`).
- **Replay of external calls.** `RecordedExperiments` (`coupled_run.py:509-…`) recomputes each request at the rerun's
  inlet. It requires every member except `inputs` and the key to equal the record's exactly, and serves out-of-process
  results from the record without running a child.
- **The child's state.** The child's state is `cpT` of shape (num_z, 2, 7): two sides, five concentrations, p and T.
  S2 is built from S1's `c`, `p` and `T` (`child.py:753-759`), and num_z = 800 in v3.

## 4. Decisions

### D1 — A start is declared in the solve request, not in the revision and not in the policy

The request gains `warm_start: {job_id?, coupling?}` (ADR 0019 Amendment 15). `job_id` names a previous solve job of
the project; `coupling` is a user iterate `{<unit>: {X, dT_K}}`. The policy keeps deciding *how* to solve, and the
request says *where to start*. Under any policy, an explicit declaration is its own opt-in.

Rejected:
- **`coupling_initial.X | .dT` as revision parameters.** R-287's refusal is kept. A start is method, not problem: as a
  parameter it would move `content_hash` and `constants_sha256`, so two revisions that differ only in their start would
  be two problems. It would also need an optional `ModelSignature` member on the frozen `list_models` surface.
- **An instance-level `initialization_hint`.** ADR 0002 D4.2 already excludes hints from the hash. But it changes two
  frozen grammars (the v1 `process-revision` instance and the v2 instance row of ADR 0062), makes a start part of the
  stored problem, and no hint has a consumer today.
- **A new policy with a `SolvePolicy.warm_scope` member.** It is a K03 schema change. A policy cannot carry a user
  iterate, and the source is an input, not a method.
- **Lineage selection only** (`T08-warm-v1` extended). It cannot name a source or take a user iterate, and it would
  change a registered policy's behaviour (Q2).

**Reconciling R-287 and ADR 0020 D7.**
- R-287 calls a start point "solver state (ADR 0020 D7)". That is right: D7's Q26 classes a start as a state.
- D7 does not forbid accepting a state. It requires the first operation that accepts one to add a W14-path test
  (`docs/adr/0020-job-execution-and-revision-runs.md:126-129`). X02 is that operation.
- The iterate enters by a registered full path (I7) and is never trusted: it is checked, and the certificate judges the
  converged answer.
- `job_id` names a state inside the project, which the integrity check (F1.4) guards. It is not a D7 case.

### D2 — Sources and their precedence

| Start | 1st | 2nd | 3rd | 4th |
| --- | --- | --- | --- | --- |
| x₀ (inner, k = 0) | internal `user_start` (harness only) | `warm_start.job_id`'s solution state (`explicit-v1`); when declared, it replaces the lineage lookup | lineage under `T08-warm-v1` (`store-latest-verified-lineage-v1`), only when no job is declared | `traversal-G0-v1` |
| w₀ (outer) | `warm_start.coupling` | `warm_start.job_id`'s final coupling iterate | the variant's `coupling.initial` | — |
| child, k = 0 | `warm_start.job_id`'s final experiment profile (same variant, start-capable) | cold | — | — |
| child, k ≥ 1 | the unit's most recent `ok` experiment in this run (start-capable variant) | cold | — | — |

*Amended (X02 review, 2026-11-07, A-4):* x₀ row: a declared `job_id` replaces the lineage lookup. If it is rejected,
`traversal-G0-v1` follows (D-7).

**Explicit sources.**
- An explicit job may be any solve job of the project that has a `solution_state` artifact, whatever its certificate
  status. The start is only a start, and the new certificate is independent (I3).
- Lineage selection keeps ADR 0024 D2's VERIFIED filter: it is a heuristic for choosing a good start, not a safety
  rule.
- One job supplies x₀, w₀ and the k = 0 profiles, so the three are coherent.

### D3 — The outer start: checked, projected, opened, then never abandoned

The checks run in this order:

1. **integrity** — job sources only. The source bundle's `external-coupling.json` validates against
   `experiment.schema.json#/$defs/coupling`, has `outcome == "CONVERGED"`, and its last iterate's `w` has 2·n finite
   entries. A missing file is `absent` (`no_coupling_record`), not a rejection.
2. **compatibility** — the source's unit-id set, or the iterate's keys, equal the bound route's external unit set.
3. **bounds** — each coordinate is clipped into the target block's `bounds` (c1: X ∈ [0, 0.95], ΔT ∈ [−50, 250] K).
   Each clip is logged, and it is not a rejection.
4. **opening** — the k = 0 inner solve at w₀ converges. If it does not, w₀ is rejected and the coupling restarts at the
   variant's `coupling.initial`. No experiment has run at that point (`coupling.py:362-366`), so a rejection costs one
   inner solve.

Once accepted, w₀ is the run's start. A later `COUPLING_NOT_CONVERGED` or a k = 0 external refusal ends the run as it
would end a cold one, with the warm record in its failure bundle. The Broyden matrix starts at −I.

Rejected:
- **Falling back to cold after acceptance.** It is ADR 0024's rejected recovery edge: it doubles the worst-case cost
  and gives one run two paths.
- **Running the k = 0 experiment inside the opening check.** It would need the rejected iteration's experiments in the
  replay queue, a schema member on the coupling record and a second replay path.
- **Carrying B.** It is more state to record and check, and it holds only near the source's w.

### D4 — The child-level start is a variant property

A **start-capable variant** declares `evaluation.profile.start` (an open, child-defined object, so the variant schema
does not change). For such a variant, the coupled route always chains starts inside a run (D2, last two rows).
Choosing that variant in the revision *is* the declaration. That is M02 N6's stated reversal: "a new variant with a
warm profile whose requests carry the warm source in their identity".

Decisions:
- v1–v3 and the stand-in are not start-capable, and they run exactly as today.
- The new variant is `pymrm-6089593-g2-nz800-s123w-v1`. Its runner is a new script, `adapters/pymrm/child_warm.py`
  (D7), selected by `runner_sha256` (D10).

*Amended (X02 review, 2026-11-07, A-8):* *Outcome:* `…-s123w-v1` was built and measured (G5, `69c4a24d`) and is
not registered: G5b fails I3, and G5c shows no gain. Its runner, tests, variant and campaign script left the package
at WO-6. The Part B plumbing (§5.5) stays with no start-capable variant registered, and the synthetic child (G4)
tests it in CI. A future start-capable runner needs a new design and its own G5. Candidates: seeding S3, a larger
warm S2 `dt_init` (F4), a cheaper certificate.

Rejected:
- **Editing `child.py`.** It moves v1–v3 (I6).
- **A full copy of `child.py`.** That duplicates 957 lines of frozen code.
- **A per-solve opt-in for chaining.** It would need a policy or request member for what is a property of the
  evaluation profile, which already lives in the variant (S1–S3 are there).

### D5 — Experiment identity: the start, content-addressed, only when used

A warm request gains `start: {"kind": "profile", "profile_sha256": <64 hex>}` before its key is computed
(`adapters/experiments/request.py:60-94`).

- `REQUEST_VERSION` stays `experiment-request-v1`, so a cold request is byte-identical.
- The key covers the profile's content, not where the profile came from: the child is a pure function of (request,
  profile bytes). This is ADR 0067 D10's rule for co-simulation, "the exact cache keys on the child snapshot's SHA",
  applied to an input snapshot.

Rejected:
- **The source experiment's key in the identity.** It would key on history rather than content, so equal profiles
  from two chains would miss each other.
- **A version bump.** It moves every key, which breaks I1.
- **Lookups that ignore the start** (serving a cold, or same-inlet, result for a warm request). Allowed by I2's
  direction, but an optimisation with an unmeasured yield and a second lookup path (§8 R5).

### D6 — Profiles live in a content-addressed store; bundles carry hashes

- **The profile store.** `experiments/profiles/<sha[0:2]>/<sha>.json` holds each exported profile once. It is
  byte-equal if rewritten, never deleted, and holds no artifact row: like an attempt's working directory, it is a file
  that a registered record refers to by hash.
- **The result.** A start-capable variant's result gains `profile_sha256` (optional, Amendment 15).
- **Bundles.** The coupling record already embeds the requests and results, so it carries every hash. It carries no
  profile bytes: an out-of-process replay serves recorded results and never runs a child (`RecordedExperiments`).

Rejected:
- **Profiles inside the result document.** About 110 KB per result, embedded again in each coupling record entry.
- **A new artifact kind.** `artifact_ref.kind` is a producer-closed enum on the MCP surface (ADR 0024 alternatives).
- **Profiles inside bundles.** No consumer reads them there.

### D7 — The warm child: S1 skipped, S2 seeded, everything that accepts unchanged, cold chain as fallback

Given a start profile, the child does the following:

- **S1** does not run.
- **S2** is built at the true inlet from the profile's `c`, `p` and `T`, exactly as the cold S2 is built from S1's
  fields. It uses S2's `dt_init` and acceptance.
- **S3, round 2, the KPI-drift certificate and the four acceptance criteria** are unchanged.
- **On any refusal of the warm chain** (S2, S3, `certificate`, `backflow`, `nonpositive_flow`) **or a
  `model_exception` inside it**, the child runs the cold chain in the same attempt and answers with its outcome,
  recording `start.used = false` and `fallback_from`.
- **After every `outlet` answer**, warm or cold, it exports the converged profile.

Without a start, the child runs the base child's code unchanged, so its outlet is bitwise v3's (gate G5a).

Rejected:
- **Seeding S3 directly.** It would save another 3.3 s, but robustness from a neighbouring inlet at `dt_init = 1.0` is
  unmeasured, and a failure costs more.
- **Answering `not_accepted` and letting the coupling fail.** That breaks I8.
- **A cold retry in the runner.** Attempts are for transients (R-224), not for deterministic refusals.

### D8 — The certificate: the same function, plus disclosure

The checks are not changed. When the final iterate's experiment for a unit carried a start, the `external_model`
limitation's detail for that unit gains `start: {profile_sha256}` and `path_independence_rel` (the variant's
registered value). A cold certificate is unchanged byte for byte.

Rejected: **a cold re-evaluation at the final inlet.** It costs one full call (20–60 s, §3.2) and so cancels Part B.
The registered path independence (G5) bounds the effect at least two decades below the tolerance (1e-5 ≫ 1e-7).

### D9 — Records and replay

- **Records.** The `warm_start` member of `solve-path.json` keeps ADR 0024's members. It gains two optional
  sub-records: `coupling` (outer start) and `external` (k = 0 child starts).
- **R0.** R0 projects statuses, reasons, selections and unit ids, never values, digests or provenance ids (ADR 0024
  D4).
- **Replay.** The rerun takes every start from the record, re-runs the checks and must write the same record. Chained
  starts at k ≥ 1 are recomputed from the recorded results' `profile_sha256`.
- **Part C.** The coupled route records the k = 0 inner warm start of the coupling that counted, whatever its K, and
  labels that inner solve `compatible_warm_start`.

### D10 — The child program is selected by the variant's `runner_sha256`

`pinned_program(variant)` returns the packaged child script whose bytes hash to `variant.evaluation["runner_sha256"]`,
among `pymrm/child.py` and `pymrm/child_warm.py`. If neither matches, it returns `child.py`, so that a mismatch
surfaces as today (handshake `environment_mismatch`). For v1–v3 this selects the same file as today. The variant
already pins its runner by hash, so the selection adds no new identity.

*Amended (X02 review, 2026-11-07, A-9):* Kept: the selection is among the packaged scripts, today `child.py` alone.

## 5. Design in detail

### 5.1 Contract (ADR 0019 Amendment 15) and admission

**`schemas/job.schema.json#/$defs/solve_body`** gains the optional member:

```json
"warm_start": {
  "type": "object", "additionalProperties": false, "minProperties": 1,
  "properties": {
    "job_id": {"type": "string", "minLength": 1},
    "coupling": {
      "type": "object", "minProperties": 1,
      "propertyNames": {"pattern": "^[A-Za-z0-9][A-Za-z0-9_.:-]*$"},
      "additionalProperties": {
        "type": "object", "additionalProperties": false, "required": ["X", "dT_K"],
        "properties": {"X": {"type": "number"}, "dT_K": {"type": "number"}}
      }
    }
  },
  "description": "ADR 0070 (ADR 0019 Amendment 15): a declared start, never a constraint. `job_id` names a solve job of this project whose solution state (and, on the coupled route, final coupling iterate and external profiles) seeds the start; `coupling` declares the outer iterate per coupled unit. The certificate judges the converged answer."
}
```

**`schemas/experiment.schema.json`** gains two optional members:
- `$defs/request.properties.start` = `{"type": "object", "additionalProperties": false, "required": ["kind",
  "profile_sha256"], "properties": {"kind": {"const": "profile"}, "profile_sha256": {"$ref": "#/$defs/sha256"}}}`;
- `$defs/result.properties.profile_sha256` = `{"$ref": "#/$defs/sha256"}`.

Nothing else in any schema changes.

**The surface.** The `submit_job` schema digest moves, so the surface chain gains one link. Follow the pattern of the
last registered link (`tests/test_m07a_surface_chain.py`, `scripts/m07a_rc.py`, the ADR 0019 Amendment 13 / ST link),
with a register entry. No tool *description* text changes (§8 F2). V17 is re-established at the next RC under the
release procedure.

**Q26.** `tests/test_t07_q26.py` pins the two new scalar paths by full path, `submit_job` `body/warm_start/coupling/*/X`
and `.../dT_K`, beside M02's experiment-inlet exception, citing ADR 0070. Its other assertions are unchanged.
`tests/test_m02_experiment_body_isolation.py` is unchanged and must pass: the `experiment` body still reaches no start.

**Semantic admission** (where `solve_body` is admitted today). Each failure is `ApiError invalid_request`; no job is
created.

| # | Condition | `detail.pointer` | message |
| --- | --- | --- | --- |
| A1 | `job_id` is not a job of this project, is not a `solve` job, or has no `solution_state` artifact | `/body/warm_start/job_id` | `warm_start_source_missing(<job_id>)` |
| A2 | a `coupling` key is not an instance id of the revision | `/body/warm_start/coupling/<key>` | `warm_start_unit_unknown(<key>)` |

`request_sha256` includes the member when it is present, so idempotency behaves as for any other member. A request
without `warm_start` is unchanged.

### 5.2 Resolving the declared sources (application layer, `application/jobs/runner.py`)

The runner resolves sources after `bind_route` (`runner.py:514`), next to the lineage lookup (`:528-533`). It produces
the following:

- **`candidate: WarmStartCandidate | None`** (x₀).
  - With `job_id`: the job's `solution-state.json`, parsed as `warm_start_candidate` parses it (`:210-230`), with
    `selection = EXPLICIT = "explicit-v1"`.
  - Otherwise: today's lineage lookup, only when the policy's chain names `compatible_warm_start`.
- **`coupled_start: CoupledStart | None`** — only on `revision_coupled` and only when `warm_start` is present. It is
  defined in `application/coupled_run.py`:

  ```python
  @dataclass(frozen=True)
  class CoupledStart:
      source: Literal["iterate", "job"] | None      # where w0 came from (None: neither declared)
      declared: Mapping[str, tuple[float, float]] | None   # w0 before projection, by unit id
      record: Mapping[str, Any]                     # the `coupling` sub-record so far (integrity/absent)
      profiles: Mapping[str, ExternalSource]        # k = 0 child starts, by unit id (job sources only)
  ```

  - With `coupling`: `declared` is the iterate itself.
  - Otherwise, with `job_id`, `declared` is the source bundle's `external-coupling.json`, which is the sibling of its
    `solution-state.json`. Take `iterations[-1].w`, the flat list in the source's unit order. That order is
    `sorted(record["variants"])`, because `external_units` sorts by unit id; map the list onto those unit ids.
  - The integrity check runs here. Compatibility, bounds and opening need the binding, so they run in
    `solve_coupled`.
- **`ExternalSource(status, reason, source_experiment_key, profile_sha256)`**, per unit of the source's last iterate.
  It is `accepted` iff all of the following hold:
  - that entry's `result.profile_sha256` is present;
  - its `request.model.artifact_ref` equals the target unit's variant sha256;
  - the target variant is start-capable;
  - the profile store holds the bytes, and their sha256 equals the recorded hash.

  Otherwise the status is `absent`, with reason `no_profile` (the source result has none), `variant_cold_only` or
  `profile_unavailable`. On a variant mismatch, or bytes whose hash differs, it is `rejected` with reason
  `external_compatibility|external_integrity` (trace: `warm_start_rejected(<check>)`, A-7).

**On other routes.**
- On `revision_eo`, a `coupling` member yields a `coupling` sub-record `rejected` with
  `warm_start_rejected(coupling_compatibility)`, and the run proceeds without it.
- On `legacy_eo`, the whole `warm_start` member is recorded `rejected` with `warm_start_rejected(route)`, and the
  solve runs as without it.

*Amended (X02 review, 2026-11-07, A-7):* The `reason` members of the `coupling` and `external` sub-records are bare check names.
`warm_start_rejected(<check>)` is the trace message only.

### 5.3 The inner start (x₀)

`execute_plan` consults the candidate when `user_start is None and (WARM_START_SOURCE in policy.initializer_chain or
(warm_start is not None and warm_start.selection == EXPLICIT))` (`orchestrator/executor.py:713`). That is the one
changed line. ADR 0024's checks, records and `initializer_source = "compatible_warm_start"` are unchanged.
`WarmStartRecord` takes `selection = "explicit-v1"` from the candidate, as today.

### 5.4 The outer start (w₀): `solve_coupled` and `couple`

**`couple`** (`orchestrator/coupling.py:286`) gains the keyword `initial: Mapping[str, tuple[float, float]] | None =
None`.
- When it is `None`, `u` starts from `block.initial` exactly as now.
- Otherwise `u = [X, dT for unit in units] / scales`, the values already projected.

**`solve_coupled`** gains the keyword `coupled_start: CoupledStart | None = None`. With `None` nothing differs; that
is every existing caller. Otherwise it does the following:

1. If the integrity record is not `accepted`, it skips to the cold coupling and keeps the record.
2. It checks compatibility: `set(declared) == {u.unit_id for u in units}`. A failure is `rejected` with
   `warm_start_rejected(coupling_compatibility)`, then the cold coupling.
3. It applies the bounds: it clips each coordinate into `block.bounds_X` and `block.bounds_dT` and logs
   `[unit, "X"|"dT_K", from, to]`.
4. It runs `couple(…, initial=w0)`. If the result is the k = 0 inner failure — `len(run.iterations) == 1`, an empty
   `iterations[0]["units"]` and an `inner.outcome != "CONVERGED"` — w₀ is `rejected` with
   `warm_start_rejected(coupling_opening)`. The trace keeps that inner solve's events, and `couple(…, initial=None)`
   runs. Otherwise w₀ is `accepted`.

`on_iteration(0, …)` may fire twice. Progress events sit outside every identity (ADR 0020 D8).

**The inner label.** In `solve_inner`, the label is `"compatible_warm_start"` when `start is None` and the inner run's
`warm_start` record has status `accepted`. Otherwise it is as today.

**The k = 0 inner record** (Part C). `CoupledSolve` gains `initial_warm: WarmStartRecord | None`, the record of the
k = 0 inner run of the coupling that counted. `_solve_coupled` (`revision_run.py:679-776`) passes it on the `RouteRun`.
For `revision_coupled`, `run_revision_session` writes `solve_path["warm_start"]` from it rather than from
`result.run.warm_start`. It writes it iff the policy names the source, or `warm_start` was declared.

### 5.5 The external start (Part B plumbing)

**Capability.** `start_capable(variant) = variant.kind == "out_of_process" and isinstance(
variant.evaluation["profile"].get("start"), Mapping)`, in `adapters/experiments/runner.py`.

**The request.** `build_request(…, start: str | None = None)` adds `request["start"] = {"kind": "profile",
"profile_sha256": start}` before the key when `start` is set. `ExperimentRunner.request` and `.run` gain the same
keyword and pass it through. `run` asserts `start is None or start_capable(variant)`.

**The backend.** `Backend.evaluate(…, start: bytes | None = None)`.
- `InProcessBackend` asserts `None`.
- `OutOfProcessBackend` writes the bytes as `start.json` in the attempt directory before `launch`, and adds
  `"start_profile_sha256": sha256(bytes)` to the child request (`_request`, `backends.py:293-301`).
- When `start is None` the child request is unchanged.

**Byte-identity of the start.** The runner reads the bytes from the profile store by hash and checks them. A mismatch
there means the store is damaged, so it is an `internal_error`; it can only happen for a hash the run has already
accepted.

**Export.** After an attempt whose execution is `completed` with an `outlet`, on a start-capable variant:

1. The runner reads `attempts/<n>/profile.json`.
2. It checks `sha256(bytes) == diagnostics["profile_sha256"]`.
3. It writes the bytes to the profile store (`ExperimentStore.write_profile(bytes) -> sha`, atomic and write-once; a
   present file must be byte-equal).
4. It sets `result["profile_sha256"]` in `_result` (`runner.py:486-…`).

A missing or mismatched file is `protocol_error` (an attempt status that already exists), and the result carries no
hash. `ExperimentStore.profile(sha) -> bytes | None` reads the store back.

**The answer.** `ExternalAnswer` gains `profile_sha256: str | None`, taken from the result. `answer_of` reads it.
`RecordedExperiments` serves it from the recorded result.

**Chaining** lives in `solve_coupled`'s `evaluate` closure, in the application layer; the orchestrator does not change
for Part B. The closure keeps `last: dict[str, str]`, which starts at the accepted k = 0 sources
(`coupled_start.profiles`). For each call `evaluate(unit_id, inlet)`:

```
start = last.get(unit_id) if start_capable(variant(unit_id)) else None
answer = experiments.evaluate(unit, variant, inlet, start=start)
if answer.status == "ok" and answer.profile_sha256 is not None: last[unit_id] = answer.profile_sha256
```

- "Most recent `ok`" follows evaluation order, so live runs and replays chain identically.
- `Experiments.evaluate` (`coupled_run.py:390`) gains `start: str | None = None`. `LiveExperiments` passes it to
  `runner.run`. `RecordedExperiments` passes it to `build_request` when it recomputes the request, so `_identity`
  compares `start` exactly and a different chain is `ReplayDivergenceError`.

**The program.** `pinned_program` selects the script by hash (D10), memoising the packaged scripts' hashes.

### 5.6 The warm child `adapters/pymrm/child_warm.py` (variant `pymrm-6089593-g2-nz800-s123w-v1`)

*Amended (X02 review, 2026-11-07, A-8):* *Outcome:* `…-s123w-v1` was built and measured (G5, `69c4a24d`) and is
not registered: G5b fails I3, and G5c shows no gain. Its runner, tests, variant and campaign script left the package
at WO-6. The Part B plumbing (§5.5) stays with no start-capable variant registered, and the synthetic child (G4)
tests it in CI. A future start-capable runner needs a new design and its own G5. Candidates: seeding S3, a larger
warm S2 `dt_init` (F4), a cheaper certificate.

**How it loads the base child.**
- It is self-contained except for one load. It reads the base child by path, `Path(__file__).with_name("child.py")`.
- It checks that file's sha256 against the literal `BASE_CHILD_SHA256 =
  "0d2c345f1d414c457e047f698b9e6a3235701b91c4990ef2300d4375f753d893"`. A mismatch is `MismatchError`, exit 72.
- It executes the file with `importlib.util.spec_from_file_location("ofs_pymrm_child_base", …)`. The base's
  `__main__` block does not run.
- Its own `runner_sha256` is the sha256 of `child_warm.py`. That pins the literal, and so pins `child.py` transitively.
- It imports only the standard library besides the loaded base. The child AST test widens to accept this one
  by-path load, and the protocol-literal test covers this file too.

**What it reuses** from the base: `Environment`, `MismatchError`, `_exit`, `_lifeline`, `_write`, `nonfinite_screen`,
`model_exception`, `certificate_passed`, `flows_positive`, `after_s3`, `steady_state_target`, `SPECIES`,
`CONFIGURATION`, the protocol literals, and `Reactor`, which it subclasses.

**What it defines:**

- **`PROFILE_W`.** This is the base `PROFILE` with `id = "M01-S123W-v1"` and the member
  `"start": {"kind": "profile", "format": "tube-profile-v1", "file": "start.json", "replaces": ["S1"], "S2": "built at
  the true inlet from the start's c, p, T; dt_init and acceptance as S2", "fallback": "the S1-S3 chain of M01-S123-v2,
  in the same attempt, on any refusal or model_exception of the warm chain", "export": "profile.json after every outlet
  answer"}`. The variant's `evaluation.profile` equals `PROFILE_W` exactly, and `_configuration_w` compares against it.
- **`main_w`.** It is the base `main` (`child.py:893-941`) with three changes: the runner hash is its own; it calls
  `_configuration_w`; and it reads `start_profile_sha256` from the request.
  - When the request has a start, it reads `start.json` from the working directory and checks
    `sha256(bytes) == start_profile_sha256`; a mismatch is `MismatchError`, exit 72.
  - It parses the profile and checks `format == "tube-profile-v1"`, `shape == [num_z, 2, 7]`, all values finite and
    `len(cpT) == num_z*14`. Any failure is `MismatchError`, exit 72. That would be a runner defect, not a model outcome.
- **`WarmReactor(Reactor)`:**
  - It overrides `outlet(self, model, *args)` only to remember `model` (a read-only reference), then returns
    `super().outlet(model, *args)`. On the cold path this is the only override. Its outlet is therefore bitwise the
    base child's (G5a).
  - `evaluate_w(tube, s2_dt_init, backflow, start_cpT | None)`:
    - With `None` it calls `super().evaluate(…)`.
    - Otherwise it runs `_warm_window`: the base `_window` from "S2" on (`child.py:752-805`), with `second =
      model(config=config2, c=…, p=…, T=…)` built from `start_cpT` reshaped to `(num_z, 2, 7)`, exactly as the base
      slices `first.cpT`. The post-processing is the base `evaluate`'s (`child.py:713-725`).
    - When the result is not `outlet`, or a covered `model_exception` occurred, it records the warm stages and calls
      `super().evaluate(…)` (the cold chain).
    - `diagnostics["start"]` is `{"profile_sha256", "used": bool, "fallback_from": <stage>|null, "warm_stages": {…}}`.
      On a cold request it is `null`.
  - The evidence switches (`OFS_EVIDENCE_S2_DT_INIT`, `…_BACKFLOW_ALT`) apply to the warm S2 as to the cold S2.
- **Export.** After an `outlet` answer, it writes `profile.json` in the working directory:
  - the document is `{"format": "tube-profile-v1", "shape": [num_z, 2, 7], "cpT": <remembered model's cpT, row-major
    float list>}`;
  - the bytes are `json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")`;
  - it sets `diagnostics["profile_sha256"]` to the sha256 of those bytes.
  - It writes the file before `result.json`, and only when the answer is `outlet` after `nonfinite_screen`.
  - On any other answer it writes no file, and `profile_sha256` is null.
- **The variant document** is v3's with these changes:
  - `variant_id` is the new id;
  - `evaluation.profile` is `PROFILE_W`;
  - `evaluation.runner_sha256` is `child_warm.py`'s hash;
  - `accuracy.measured_path_independence_rel` is set from G5b.

  The environment (`env_id pymrm-6089593-032a050c6cf3`) is v3's. It is first committed as
  `benchmarks/x02/variant-s123w-provisional.json`, following the `benchmarks/m02/variant-v3-provisional.json`
  precedent, and registered in `adapters/variants/registry.json` only after G5 passes.

### 5.7 Records

**`solve-path.json` → `warm_start`.** ADR 0024's members are unchanged, and `selection` may be `explicit-v1`. Two
optional members are added, each present only in the case stated:

```
"coupling": {              # iff revision_coupled (or a declared `coupling` elsewhere) and warm_start declared
  "record": "coupling-start-v1",
  "source": "iterate" | "job" | null,
  "status": "accepted" | "rejected" | "absent",
  "reason": null | "no_coupling_record" | "not_declared"
            | "coupling_integrity" | "coupling_compatibility" | "coupling_opening" | "route",
  "declared": {"<unit>": {"X": x, "dT_K": t}} | null,
  "projections": [["<unit>", "X" | "dT_K", from, to], ...]
},
"external": {              # iff revision_coupled, a job source declared, and ≥ 1 start-capable unit
  "record": "external-start-v1",
  "units": {"<unit>": {"status": ..., "reason": ..., "source_experiment_key": key | null,
                       "profile_sha256": sha | null}}
}
```

When a start is declared but no x₀ source is (an iterate only, under a policy whose chain is empty), the inner members
read `status: "absent", reason: "not_declared"`. The member is written iff the policy names the source or `warm_start`
was declared.

*Amended (X02 review, 2026-11-07, A-7):* The `reason` members of the `coupling` and `external` sub-records are bare check names.
`warm_start_rejected(<check>)` is the trace message only.

**`external-coupling.json`.** No schema change.
- `iterations[0].w` is the w₀ used.
- `inner.start` may be `"compatible_warm_start"` (a free string).
- Each entry's `request` carries `start` when the experiment was warm.
- When w₀ was rejected at opening, the record is the cold coupling's alone.

**The certificate.** See D8. `run/identity.py` projects only `limitation_kinds`, so R0 does not change for a
certificate.

**R0** (`run/identity.py:128-149`). Inside `projection["warm_start"]`, iff the member is present:
- `coupling`: `{source, status, reason, units: sorted(declared or []), projected: [[unit, coord], ...]}`;
- `external`: `{unit: {status, reason}}`.

No value, digest, experiment key or job id enters R0. Bundles without the members project exactly as today.

### 5.8 Replay (ADR 0024 D5, extended)

`_recorded_warm_start` (`revision_run.py:981-986`) becomes `_recorded_starts(recorded) -> (candidate, coupled_start)`.
- The candidate is as today.
- `coupled_start` is rebuilt from `coupling.declared`, `coupling.source` and the integrity outcome, and its `profiles`
  from `external.units`. Store presence is not rechecked: an `accepted` hash is taken as recorded, and replay serves
  out-of-process results without bytes.
- The rerun re-runs compatibility, bounds and opening, and must reach the same statuses. Any difference shows in the
  R0 comparison as a `MISMATCH`.
- Chained hashes come from the recorded results through `RecordedExperiments`.
- No store lookup happens anywhere on the rerun path (`reproduce_bundle`, `revision_run.py:1090-1112`).

### 5.9 Messages and the MSG catalogue

These are new code-shaped tokens. MSG's G2 scan finds them at their emission sites. If `wp/MSG` has merged when the
work order runs, add the entries; otherwise list them in the package build-decisions log for MSG to absorb.

| Token | Family / kind | Where |
| --- | --- | --- |
| `warm_start_source_missing(<job>)` | api_error detail / `input` | A1 |
| `warm_start_unit_unknown(<unit>)` | api_error detail / `input` | A2 |
| `warm_start_rejected(coupling_integrity\|coupling_compatibility\|coupling_opening\|route\|external_integrity\|external_compatibility)` | notice | trace `initializer_rejected` events only; records carry the bare check name (A-7) |
| `coupling_warm_start(present\|absent)` | notice | trace message (existing event kinds only, as ADR 0024 D4) |

*Amended (X02 review, 2026-11-07, A-7):* The `reason` members of the `coupling` and `external` sub-records are bare check names.
`warm_start_rejected(<check>)` is the trace message only.

`parameter_unsupported(<U>.coupling_initial.X | .dT)` keeps its bytes (`tests/test_m02_wo9_reactor.py:386-398`). Its
catalogue entry may add an `action` naming `warm_start.coupling`, through MSG's `when` mechanism (MSG's call).

### 5.10 Performance

- **Part A** adds at most one inner solve (a rejected opening) and one JSON read of the source bundle. It saves whole
  calls, and the real loop's calls take 20–60 s each (§3.2).
- **Part B** writes about 110 KB per experiment twice: the attempt directory and the profile store, 800 × 14 floats as
  shortest-repr JSON. It passes one file to the child and skips S1, saving about 5.4 s of 48 s per warm call.
- **Fallback.** The child's fallback costs at most one extra cold chain: worst case about 140 s, inside the 450 s
  timeout.
- **Replay** reads no profile bytes.

## 6. Work orders

All work orders are build lane (Opus). Each runs on `wp/X02` and targets about 150 k context. The touched tests run
locally after each one. `scripts/gate.sh` and F0 run before the merge. One `reviewer` pass covers the whole package
before the merge (it touches identity, replay and the certificate). Each work order lands as isolated commits.

| WO | Content | Depends | Acceptance |
| --- | --- | --- | --- |
| **WO-1** Part C | §5.4's `initial_warm` and the label; `revision_run` writes the k = 0 inner record for `revision_coupled` | — | G1; F0 PASS; `tests/test_t08_w4_warm_starts.py` and `tests/test_m02_wo10_coupled.py` unchanged |
| **WO-2** Contract and inner explicit start | Amendment 15 schemas (both files, §5.1); admission A1–A2; §5.2's x₀ resolution; §5.3's one line; R0 unchanged for x₀ (`selection` already projected); surface-chain link with its register entry; Q26 full-path pins; the W14-path test (§7 G6) | WO-1 | G2, G6; schema round-trip fixtures pass; experiment-body isolation test unchanged |
| **WO-3** Outer start | `CoupledStart`; integrity at resolution; compatibility, bounds and opening in `solve_coupled`; `couple(initial=)`; the `coupling` sub-record and its R0; replay §5.8 (coupling part); trace messages | WO-2 | G3 on the stand-in (`benchmarks/m02/c1-loop-standin.json`) in CI |
| **WO-4** External plumbing | §5.5 complete; `ExperimentStore` profile store; result `profile_sha256`; the `external` sub-record and its R0; replay chaining; D8 disclosure; `pinned_program` by hash; synthetic warm child `tests/support/synthetic_warm_child.py` and its variant (§7 G4) | WO-3 | G4 in CI; G0's key recomputation |
| **WO-5** The warm reactor | `child_warm.py` (§5.6) with unit tests that need no environment (hash literal = v3's `runner_sha256`, profile round-trip, AST and literal tests); provisional variant; the workstation campaign G5a–e (Opus analyses the numbers); registration of `…-s123w-v1` with the measured value | WO-4 | G5; numbers in `evidence/X02/<C>/` |
| **WO-6** Close | MSG entries (§5.9); register entries (ADR 0070 drafts); `docs/progress.md`; manifest `status: tested`; `reviewer` pass; full gate and F0 | WO-5 | G0 full; reviewer findings resolved |

*Amended (X02 review, 2026-11-07, A-8):* *Outcome:* `…-s123w-v1` was built and measured (G5, `69c4a24d`) and is
not registered: G5b fails I3, and G5c shows no gain. Its runner, tests, variant and campaign script left the package
at WO-6. The Part B plumbing (§5.5) stays with no start-capable variant registered, and the synthetic child (G4)
tests it in CI. A future start-capable runner needs a new design and its own G5. Candidates: seeding S3, a larger
warm S2 `dt_init` (F4), a cheaper certificate.

**Stopping rules.**
- If F0 or any cold test moves in WO-1–WO-4, stop: I1 is broken, and the commit is wrong until shown otherwise.
- If G5b exceeds 1e-6, stop WO-5 and escalate to the design lane. v4 is not registered. Parts A and C still ship.

## 7. Verification gates

The configurations are:
- **CI** (both architectures): the stand-in loop and the synthetic warm child.
- **Workstation:** the reactor environment `pymrm-6089593-032a050c6cf3`, present on this host.

"Bitwise" means equal canonical bytes. Every gate has a control that fails without the feature, so that a gate cannot
pass vacuously.

**G0 — Cold identity** (every WO touching code; in full at WO-6).
- F0 `--check` PASS (M1–M9) and `scripts/gate.sh` PASS.
- Each of these is unchanged by node id and expectation:
  - `tests/test_m02_wo9_reactor.py` (`:386-398` refusal, `:442` cold w₀);
  - `tests/test_m02_wo10_coupled.py`;
  - `tests/test_m02_pymrm_child.py`;
  - `tests/test_m02_experiments.py`;
  - `tests/test_t06_w6_injection.py`;
  - `tests/test_t08_w4_warm_starts.py`;
  - `tests/test_m02_experiment_body_isolation.py`.
- A script recomputes `experiment_key` for every recorded request under `benchmarks/m02/`, `benchmarks/m05/records/`
  and `benchmarks/m07/journey/`, and finds 0 differences.
- `pinned_program` returns `child.py` for v1, v2 and v3.

**G1 — Part C** (stand-in, CI).
- A cold run of the stand-in loop gives job J₀.
- A `T08-warm-v1` run of the same revision gives J₁. Its lineage candidate is J₀, so the gate does not depend on K.
- J₁'s `solve-path.json` has `warm_start.status == "accepted"`, and its `iterations[0].inner.start ==
  "compatible_warm_start"`.
- Reproducing J₁ gives `MATCH`.
- Control: the rerun with the record's member deleted is not `MATCH`, or reports the record difference.

**G2 — Explicit x₀** (`revision_eo`, CI, on T08's B40 corpus case).
- `warm_start.job_id` = a VERIFIED job, under the `default` policy. The bundle's `selection` is `"explicit-v1"`,
  `status` is `"accepted"`, and the run converges and verifies. Replay gives `MATCH`.
- The same with a non-VERIFIED source that has a solution state: accepted.
- A1 fires for an unknown id, for a `reproduce` job and for a solve job without a solution state (3 cases, each
  `invalid_request` with the pointer and message of §5.1).
- With a tampered `solution-state.json` (one value changed, hash kept): `rejected` with
  `warm_start_rejected(integrity)`, and the run's solution state and certificate are R0-equal to a cold run's.

**G3 — Outer start** (stand-in, CI). J_c is the cold run of the stand-in loop.

| Case | Expected | How it is measured |
| --- | --- | --- |
| (a) same revision, `job_id = J_c` | VERIFIED; 1 outer iteration (k = 0); final w equal to J_c's bitwise; experiments evaluated ≤ 1 | the coupling record; report whether k = 0 was a cache hit |
| (b) iterate = J_c's w + (0.01, +5 K) | VERIFIED; the Δû bound below holds | the bound formula |
| (c) iterate with an infeasible inner at k = 0 (the test first proves the inner solve at that w fails; start from (0.95, −50)) | `coupling.status == "rejected"`, reason `…(coupling_opening)`; 0 experiments at the rejected w₀; `external-coupling.json` byte-identical to J_c's | the experiment records and the bytes |
| (d) iterate naming a non-external instance | admitted; `rejected` `…(coupling_compatibility)`; coupling record byte-identical to J_c's | the bytes |
| (e) replay of (a), (b) and (c) | `MATCH`; the record reproduced | `reproduce` |
| (f) forged bundle: `solve-path.json`'s `coupling.declared` edited, hashes recomputed | not `MATCH` | `reproduce(rerun=true)` |

*Amended (X02 review, 2026-11-07, A-6):* the registered stand-in opens everywhere in its bounds (D-11). (c) uses that loop with H₂
make-up 0.725 mol/s, from (0.95, −50), and first proves the inner outcomes. The byte reference for (c) and (d) is a
second cold run under the same cache state (D-10).

**The Δû bound** (G3b, G5d). Use scaled coordinates: û = (X/scale_X, ΔT/scale_dT) and r̂ = (r_ξ/scale_X,
r_T/scale_dT), at each run's final iterate (recorded per unit). Let B_c be the cold run's last non-null Broyden matrix
(`step.B`), or −I if it converged at k = 0. Then the gate is

‖û_w − û_c‖_∞ ≤ 2 · ‖B_c⁻¹‖_∞ · (‖r̂_w‖_∞ + ‖r̂_c‖_∞).

For the real loop (§3.2) this gives about |ΔX| ≤ 3.6e-4 and |ΔΔT| ≤ 0.036 K.

**G4 — External plumbing** (synthetic warm child, CI).
- **The child.** `synthetic_warm_child.py` speaks the protocol. Its model is a damped fixed-point iteration
  x ← x + ½(f(inlet) − x) on a 16-vector, with f analytic. It stops at ‖Δx‖_∞ ≤ 1e-12 from zeros (cold) or from
  `start.json` (warm), exports the vector as `tube-profile-v1` with shape [16, 1, 1], and answers an outlet derived from
  x. A test-environment switch forces the warm chain to refuse.
- **Expected:**
  - (a) k = 0 has no `start` and k ≥ 1 carry `start.profile_sha256` equal to the previous ok result's
    `profile_sha256`. The k = 0 key equals a cold request's key computed independently.
  - (b) Warm and cold outlets each match f's analytic value within 1e-11.
  - (c) A cold request at an inlet where a warm result exists is a cache miss, and vice versa (keys differ); then each
    repeat is a hit.
  - (d) The forced refusal gives `start.used == false`, `fallback_from` set, and an outlet bitwise equal to the cold
    run's.
  - (e) Replay gives `MATCH`. Replay of a bundle whose second request's `start.profile_sha256` was edited gives
    `ReplayDivergenceError` → `MISMATCH`.
  - (f) The certificate's `external_model` detail carries `start` iff the final request did, and the cold certificate
    is byte-identical to that of a build without X02 (G0).

**G5 — The warm reactor** (workstation). The inlets I₁…I₈ are the four inlets of `g12-real-loop-v3.json` `calls[*]`
and the four of `benchmarks/m05/records/trust-region-study-real.coupling/S0.json` iterations.
- **(a) Cold equals v3.** At I₁…I₈, the new variant without a start gives a `tube_outlet` bitwise equal to v3's
  recorded `tube_outlet`. If a recorded v3 value differs, rerun v3 live at that inlet and compare with that. A
  difference from live v3 fails the gate.
- **(b) Path independence.** In each sequence, warm k from the variant's cold profile at k − 1, and warm k = 0 from
  the cold profile at k = 3 (the farthest start).
  - The metric is rel = max over ξ, T_out, and every outlet flow with |n| > 1e-12·n_tot, of |a_w − a_c|/|a_c|.
  - Max ≤ 1e-7: pass. Register `measured_path_independence_rel = max(measured, 1.56e-8)` and keep
    `precision_floor_rel = 1e-6`.
  - ~~1e-7 < max ≤ 1e-6: pass with a manifest note.~~
  - ~~Max > 1e-6: fail and escalate.~~
  - *Amended (X02 review, 2026-11-07, A-3):* strike the band 1e-7 < max ≤ 1e-6, which contradicts I3. Pass iff max ≤
    `precision_floor_rel`/10; otherwise the variant is not registered. Raising the floor is a separate decision: the
    EXT-COUPLING floors scale with it.
  - Every warm call must be accepted, with `start.used == true` at at least 7 of 8 inlets. Each fallback is listed.
- **(c) Timing.** Report wall_warm/wall_cold per inlet (expected 0.85–0.90). Report only; no gate.
- **(d) Real loop**, `c1-loop-real.json` pinned to the new variant (`benchmarks/x02/c1-loop-real-s123w.json`):
  - (i) cold: VERIFIED, with iterates reported against g12;
  - (ii) `job_id` = (i), same revision: VERIFIED, 1 outer iteration, w₀ = w_final bitwise, at most 1 call;
  - (iii) neighbour: one parameter edit chosen by the engineer (e.g. a feed temperature + 2 K), logged, that moves w by
    more than 10× the Δû bound. Cold and warm (`job_id` = (i)) are both VERIFIED, the Δû bound holds, and the warm
    run takes fewer outer iterations than the cold one. If not, escalate: a premise has failed. Wall times reported.
- **(e) Part A on v3.** (d)(ii) with `c1-loop-real.json` (v3): VERIFIED, 1 outer iteration, all experiments cold
  (no `start` member).

**G6 — Contract and Q26** (CI).
- The surface chain passes with the new link and its register entry.
- The Q26 test pins exactly the two new scalar paths.
- **W14-path cases:**
  - an iterate far from the solution — at the bounds corner (0, −50) and at (0.95, 250) — yields either a VERIFIED
    certificate whose EXT-COUPLING checks pass at the converged state, or an unconverged or rejected outcome; never
    VERIFIED with a failing check;
  - the forged-bundle cases of G3f and G4e.
- Every transport (Python, CLI, HTTP, MCP) accepts `warm_start` with one request each, and gives `invalid_request` for
  A1.

## 8. Risks and open questions

Each item names what it needs and the default the build takes. The build proceeds on the defaults, and each one is
revisable by a revert of its isolated commit.

| # | Question | Needs | Default |
| --- | --- | --- | --- |
| Q1 | Build the warm reactor variant (WO-5)? It gives about 11–15 % per call, about 6 % end to end on top of Part A (§3), for a new runner, a variant and a workstation campaign | Frank's preference | **Yes.** R-924, R-925 and R-927 lift "external models start cold every call" as policy. WO-5 is last and separable. *Outcome (A-8):* built and measured (G5, `69c4a24d`), not registered: G5b fails I3, G5c shows no gain (§4 D4). |
| Q2 | Should `T08-warm-v1` on the coupled route also take w₀ (and k = 0 profiles) from its lineage candidate, giving coherent warm starts without naming a job? | Frank's preference | **No.** A registered policy keeps its behaviour. Name the job, or add a new policy later (it needs a K03 member, D1). |
| Q3 | Starts on the `experiment` operation? | Frank's preference | **No.** An experiment is a reference evaluation; history there defeats its purpose. |
| Q4 | Study integration (M05 trust region, M03 sweeps passing the incumbent's job id) | scope call | **Out of X02.** It belongs to a follow-up in the study package. The interface (D1) is ready. |
| Q5 | Accept ADR 0070, including ADR 0019 Amendment 15? | Frank, as for earlier contract amendments | **Build on Proposed.** Acceptance at the package review, batched with the other 0.4 Frank items. |
| Q6 | Variant id `pymrm-6089593-g2-nz800-s123w-v1` (a public name in `list_models`) | Frank's taste | **That id.** It is a registry entry, renamable before release. *Outcome (A-8):* not registered, so the id is not public. |
| F1 | Does the k = 0 inner solve at (x*, w*) return x* bitwise, so that a same-revision rerun needs 0 calls? | fact (G3a, G5d(ii) report it) | No reliance: the gates allow ≤ 1 call. |
| F2 | Does a schema-only surface change need Frank's description review (R-134, R-144 pattern)? | fact, from the surface-chain test's rules | No description text changes. If the chain demands a review, park it as a batched Frank item and continue. |
| F3 | Does the G2 reactor have several steady states in its hard domain, so that a warm chain could follow another branch? | fact (G5b at 8 inlets; M01 records) | A declared limitation in ADR 0070 and the `external_model` detail. G5b catches a branch switch at the registered inlets. |
| F4 | Would a larger warm S2 `dt_init` save more? | fact (`OFS_EVIDENCE_S2_DT_INIT` exists) | Keep 1e-6, the minimal departure. G5c may report one alternative as evidence only. |
| R1 | Profile store growth: about 110 KB per warm-capable experiment, never deleted | fact | Accept, as for attempt directories. Pruning is a store-lifecycle question outside X02. |
| R2 | A warm-started run can reach another certified answer than a cold one (another fixed point within tolerance; another steady state) | inherent | Disclosed: the bundle records the start, the certificate discloses warm evidence, and ADR 0024's "change of method, never of problem" applies. |
| R3 | `couple`'s k = 0 failure shape is detected structurally (§5.4 step 4) | fact | A unit test pins the shape. If `couple` changes, that test fails first. |
| R4 | `launch` and the child must handle `start.json` written before the launch | fact | The backend writes it before `launch`. The synthetic child (G4) proves the path in CI. |
| R5 | Cold-first or same-inlet lookups could save the k = 0 call on reruns of chained runs | fact (how often the inlet bits repeat) | Not built. Revisit with F1's measurement. |
