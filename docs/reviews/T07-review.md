# T07 review — jobs, authorization, HTTP/MCP bindings and revision runs, against `docs/design/T07-jobs-and-bindings.md` (ruling rounds 1–4), ADR 0019, ADR 0020 and ADR 0002 Amendment 1

**Reviewer:** design lane, `reviewer` (Claude Opus 5.5), 2026-09-27.
**Brief:** `docs/briefs/T07-review.md`.
**Reviewed at:** `wp/T07` = `1ed044d`; the diff is `78d3647..1ed044d`. W5e (`1ed044d..0a7e79d`), merged while
this review ran, is covered only for its inertness claim (§5). HEAD was `79d8cda` at the end of the review;
nothing under `src/` or `benchmarks/t07/v17/scorer.py` changed after `0a7e79d`.

**How it was run:**
- Every probe ran against a `git archive` of `1ed044d` (the full tree), never against the moving checkout.
  Base comparisons ran against a `git archive` of `78d3647`.
- Probe root is `/tmp/claude-1003/-home-frankp-Codes-Process-Simulator/c1654ca5-cf40-4fac-b53a-1914bdd081e5/scratchpad/review/`,
  written `PROBES/` below. The wrappers are `PROBES/py1ed.sh` (1ed044d) and `PROBES/pybase.sh` (78d3647).
- The review was split by the brief's areas. Each finding below cites the probe that produced its output.
  I re-ran the probes behind both M findings myself.
- I did not run the gate, the conformance suite or the campaign.

---

## 1. Verdict

**T07 can merge once M1 and M2 are closed.**

- **M1** is a scientific invariant that fails. T07 states I3 (§10.5, R5): ordinary solve tools cannot
  weaken verification. The agent-facing `submit_job` text states it too. It is false: tightening
  `check_tolerances.molar_flow` far enough removes checks rather than tightening them. The gate that
  claims to test it (G12) is not implemented as registered.
- **M2** is a crash of the K06 façade on the path T07 itself changed.

Everything else holds up well, and much of what the brief feared is sound:
- the interrupt hook;
- the fencing of events and worker results;
- authority coming only from the credential;
- the idempotency ledger;
- the recorded-route rerun and the forged-bundle defences;
- the ADR 0002 A1 integer rule;
- the MCP schema flattening.

The S findings fall into two groups:
- **Executor robustness and typed errors** (S1–S6).
- **The V17 scorer** (S7–S11). These should be closed before `verdict` judges the campaign.

Scoring is deterministic over recorded exports and transcripts, so S7–S9 and S11 can be applied to the
running campaign after the fact. S10 cannot: the audit rows it needs were never written.

| Rank | Count |
|---|---|
| M | 2 |
| S | 11 |
| N | 12 |

---

## 2. Must fix (M)

### M1 — Tightening `molar_flow` deletes the independent flash checks; I3/R5 and G12 are false as stated

**Where:**
- `verify/table.py:1363` passes the *applied* flow tolerance τ into `split_route`
  (`verify/saturation.py:241-248`). There the resolution floor N·ulp(T)/(w·τ) grows as τ shrinks.
- Past 0.1, the split is "unresolved". The four `independent_split.<U>.<S>.{total,A,B,C}` checks
  collapse into one `not_applicable(fresh_flash_unresolved)` (`table.py:1146-1154`).
- The energy checks then read the state's own split enthalpy instead of a fresh flash
  (`table.py:1394-1400`).
- The verifier predates T07. T07's user-controlled `check_tolerances` is what makes this reachable.

**Failure:**
1. `submit_job` sends `check_tolerances={"molar_flow": 3.1e-14}` (1e-6 × registered), which admission
   accepts: any positive value down to 1e-320 is admitted.
2. The certificate has 3 fewer checks and 0 failures, and reads RELAXED.
3. The independent flash is exactly the check that catches a wrong-branch split. With it gone, "all checks
   pass under a tightened policy ⇒ VERIFIED under the registered one" (§10.5 as amended by R5) no longer
   follows.

It is not a false VERIFIED today, because a tightened run is at best RELAXED. It becomes one the day
S-R5 decides that a tighten-only policy is VERIFIED.

**Probe:** `PROBES/area4_7/p1_tighten_drops_checks.py`. I re-ran it (`PROBES/recheck/`):
```
SYN-001-nominal registered: VERIFIED tight(1e-6 x molar_flow): RELAXED
  checks only in registered: ['independent_split.flash.S3.A', 'independent_split.flash.S3.B', 'independent_split.flash.S3.C', 'independent_split.flash.S3.total']
  checks only in tight:      ['independent_split.flash.S3']
  n checks registered/tight: 147 144 ; failing under tight: 0 []
```
- SYN-001-T06-NET03 loses 16 checks across 4 splits (246 → 234).
- The factor sweep (`p1b_threshold.py`) drops nothing at 1e-2 … 1e-5 and drops 4 checks at 1e-6.

**Why the gate missed it:**
- G12, as registered, is 5 revisions × factors {1, 0.5, 0.1, 0.01} with "RELAXED ⇒ registered VERIFIED".
- What exists is `tests/test_t07_w4a_jobs.py:631-648`: one revision at {1, 0.5}, with no comparison of
  check sets. `test_t07_w3c_admission.py:169-178` covers admission only.
- Even the registered grid stops above the measured threshold.

**Smallest fix** (needs a decision, design lane, because it touches certificates):
- **(a)** Route the split on the registered τ (`KIND_TOLERANCE["molar_flow"]`) at `table.py:1363`.
  - This is bit-identical at the registered policy.
  - A tightened split can then fail on resolution but can never vanish, which is the safe direction.
- **(b)** Refuse tightening below a floor at admission.
- **(c)** Amend §10.5, R5 and `submit_job.md` so they no longer claim monotonicity.

I would take (a). With any of the three, add G12 as a corpus test that asserts:
- every check evaluated under the registered policy is also evaluated under the tightened one;
- a factor ≤ 1e-6 is included.

### M2 — Every `rejected` path inside `_prepare` crashes an in-memory project, which includes the K06 façade

**Where:**
- `application/local.py:1234-1266`: `_prepare` calls `self._rejected(...)` while `with store.reading()` is
  still open.
- `_rejected` → `_audit_refusal` → `store.record_audit` (`store.py:485`) opens `writing()`.
- An in-memory store is one connection behind an RLock (`store.py:282-285`), so `BEGIN IMMEDIATE` runs
  inside the open `BEGIN`.
- `transactions.Application()` defaults to `LocalApplication.in_memory()` (`transactions.py:271`).
- File-backed projects, the only ones the tests use, are unaffected.

**Failure:** on the K06 façade, all of the following raise `sqlite3.OperationalError` instead of returning
`rejected`:
- a taken `new_revision_id`, which is one of the three behaviour changes the brief lists;
- an unknown `restore_from`;
- `preview_change` with an unknown `restore_from`.

The third `_rejected` inside the block, an unknown `expected_revision` (`local.py:1239`), takes the same
path wherever it is reachable. I did not probe it.

**Probe:** `PROBES/area3_5/p3_inmemory_rejected.py`, re-run:
```
in_memory LocalApplication first: committed rev-000001
  taken new_revision_id: RAISED OperationalError: cannot start a transaction within a transaction
  unknown restore_from: RAISED OperationalError: cannot start a transaction within a transaction
  preview unknown restore_from: RAISED OperationalError: cannot start a transaction within a transaction
K06 facade, taken id: RAISED OperationalError: cannot start a transaction within a transaction
```

**Smallest fix:**
- Hold the refusal in a local variable, leave the `with` block, then call `_rejected`.
- Add façade and in-memory tests for a taken id (identical content and different content; see N9) and an
  unknown `restore_from`.

---

## 3. Should fix (S)

### S1 — The supervisor drops a job after one store error
**Where:** `jobs/executor.py:319-333`.
- `ended = self._watch()` runs before `_finish`. When `_finish` raises, the `except Exception` logs, and
  the slots in `ended` are popped anyway. The comment "the next poll retries" is false.
- `_launch` has the same flaw: an admitted id is popped from the queue and never re-queued or ended.

**Failure:** one `sqlite3.OperationalError` in `finish_job` (a busy timeout past 30 s, or a full disk):
- The job stays `running` for the server's lifetime.
- After a restart it becomes `failed(owner_lost)`, although its VERIFIED solve completed.

**Probe:** `PROBES/area2_6/probe_supervisor_drops_slot.py`:
```
worker_result written: completed / finish_job calls: 1 / job status 5 s after the worker exited: running
executor slots: [] queue: [] / after close() and reopen: failed ... reason='owner_lost' ...
get_job_result: failed CONVERGED VERIFIED
```
`probe_supervisor_drops_admitted.py` shows the same for `_launch`: `queued`, and the queue is empty.

**Fix:**
- Pop a slot only after its `_finish` succeeds.
- Re-queue an admitted id whose launch raised, or end it `failed` as a retryable store error.
- Make `_finish` idempotent. `_worker_log` does a plain INSERT at `store.py:878`, which would raise
  `IntegrityError` on a retry.

### S2 — A cancelled or timed-out reproduce still emits its rerun's certificate-bearing bundle
**Where:** `jobs/runner.py:458-463`.
- At `compare`, the rerun bundle is registered and emitted before `self.at(stage)` checks the interrupt.
- The rerun's verify makes no `Trace.record` call, so a cancel that arrives there is first seen after the
  emission.
- §8.1 says an interrupted job writes no certificate "even if the interruption came during verify or
  bundle". The solve path honours this; the rerun does not.

**Probe:** `PROBES/area2_6/probe_reproduce_cancel_emits_certificate.py`:
```
solve cancelled during verify: cancelled cooperative ['partial_solve_trace']
reproduce cancelled during rerun verify: cancelled cancel_requested cooperative [('replay_bundle', 'job-000003:rerun')]
  certificate verification_status via get_artifact: VERIFIED
```
**Fix:** in the reproduce path's `at`, poll the cancel flag and call `check()` before `_bundle`/`_emit`.

### S3 — `validate`, `preview_change` and `commit_change` raise untyped on an out-of-domain or schema-invalid revision
**Where:**
- `application/binding.py:273` onward. The legacy binder lets the SYN-001 constructors'
  `SpecificationError` escape (raised at `models/syn001/flash.py:225`, through `Syn001Flowsheet` at
  `binding.py:407`). The revision binder maps the same exception to `Unbound("unsupported", …)` at
  `revision_binding.py:796,855`.
- `application/validation.py:199`: SCHEMA-01 checks only the required keys and never applies the frozen
  `process-revision.schema.json`.

**Failure:** an agent sets the SYN-001 feed pressure to 3 bar, outside the flash's declared domain of
[0.5, 2] bar. The change is canonical and schema-valid. `preview_change` and `commit_change` raise, and
HTTP/MCP answer `internal_error`, which §5.8 reserves for a defect.

**Probe:** `PROBES/area1/commit_pressure.py`:
```
preview_change -> UNTYPED SpecificationError U-FLASH: specified pressure 300000.0 Pa is outside the declared domain [50000.0, 200000.0] Pa
commit_change -> UNTYPED SpecificationError U-FLASH: specified pressure 300000.0 Pa is outside the declared domain [50000.0, 200000.0] Pa
```
- More broadly (`PROBES/area1/validate_fuzz.py`): replacing any one node of five registered revisions
  by one of seven values gives 13,321 mutations.
  - `validate()` raises on 1,742 of them at 1ed044d, against 1,703 at the base.
  - The fallback path adds 222 crash sites and removes 183.
- `schema_cover.py`: 1,733 of the 1,742 are refused by the frozen revision schema. The other 9 are this
  `SpecificationError`.
- It is pre-existing in K06, but T07 is what puts it behind a network transport.
- The probe `commit_malformed.py` shows the schema-invalid case reaching `internal_error` through `dispatch`
  (`TypeError unhashable type: 'list'`).

**Fix:**
- Catch `SpecificationError` in `bind_revision_or_reason` exactly as `bind_revision_flowsheet` does.
- Make SCHEMA-01 validate against `process-revision.schema.json`.
- **Needs a decision** (design lane): is an out-of-domain fixed specification `DRAFT`, which is what
  `unsupported` gives through `NOT_RUN`, or `INVALID`? I would take `INVALID`, with a named check, because
  it is a statement about the document.

### S4 — `max_active_jobs` is checked outside the accept transaction
**Where:** `local.py:698`. `_admit` counts active jobs in its own read (`store.py:816`), and
`accept_job` (`store.py:501`) inserts in a separate `BEGIN IMMEDIATE`.

**Probe:** `PROBES/area3_5/p1_max_active_race.py`. A grant with `max_active_jobs=1` receives 16
concurrent submissions: `queued (active) jobs of agent-1 while the lock is held: 16` / `refused limit_exceeded: 0`.

**Fix:** count inside `accept_job`, after the ledger lookup and within the same transaction.

### S5 — A capability's wall-time ceiling does not bound its default, or its absence
**Where:** `admission.py:219-220`, which uses `limits.default_wall_time_s` unchecked. `grant`
(`authz.py:302`, CLI flags included) accepts a default above the ceiling, or no default at all.

**Probe:** `PROBES/area3_5/p5_ceiling_bypass.py`:
```
admit_budgets(no budget, ceiling 10 s, no default) -> None
grant accepted default 3600 > ceiling 1800 ... admit -> 3600.0
```
The first line means no limit at all. The V17 grant (300 s default, 1800 s ceiling) is not affected.

**Needs a decision:** §8.3 says both "or else no limit" and "must not exceed `max_wall_time_s`". I would take:
- the effective value is the request, else the default, else the ceiling, and it is checked against the
  ceiling;
- `Limits` refuses a default above the maximum.

### S6 — The lifecycle checker accepts transitions §6.1 does not draw
**Where:** `jobs/model.py:128-211`. It implements §6.3 faithfully, but §6.3 has no transition rule.

**Probe:** `PROBES/area2_6/probe_lifecycle_gaps.py`. Each of these gives `violations=[]`:
- `queued → completed(operation_completed)` with no `started`;
- `queued → timed_out`;
- `queued → cancelled(cancel_requested)` with no `cancel_requested` event.

No live path produces these today, but G3 would not catch an owner defect that did.

**Needs a decision:** add a rule 13:
- `completed`, `timed_out`, and `failed(operation_error | verifier_refused)` require `started`;
- `cancelled(cancel_requested)` requires the event.

### S7 — Scorer: the system counter sees only certificates listed in `job.outputs`
**Where:** `benchmarks/t07/v17/scorer.py:1295` (`store.certificate_id(job)` → outputs, `:779-789`).

**Failure:**
- The runner registers the bundle (`runner.py:410,461`, unfenced; see N4) before the fenced `_emit`
  (`runner.py:415`).
- A worker fenced out or killed between the two leaves a VERIFIED certificate in `artifacts` that carries
  the job id, while the job has no outputs.
- `get_artifact` serves it, and the system counter never judges it.

**Probe:** `PROBES/area9/p1_cert_outside_outputs.py`:
```
certificate in export artifacts: True | document status: VERIFIED | artifact job_id: job-000003
system counter: count = 0 established = True certificates judged = 0
```
**Fix:** enumerate the export's `solution_certificate` artifact rows of session jobs, and keep `outputs`
as a cross-check only.

### S8 — Scorer: a missing or truncated transcript yields an established agent counter of 0
**Where:** `scorer.py:1206`. `self.answer is None` returns `established: True, count: 0`.

**Probe:** `PROBES/area9/p3_transcript_missing.py`:
- intact transcript: `established=True count=2`
- last line truncated: `established=True count=0`, with defect `transcript_line_unparseable`
- missing transcript: `established=True count=0`, with `infra transcript_missing`

**Needs a decision** (specifier; spec §7.6 is silent). I would report `established: false` when the
transcript is missing, or when an unparseable line comes after the last parsed assistant line.

### S9 — Scorer: an ordinary wrong numeric answer can crash scoring of the whole campaign
**Where:** `scorer.py:238,246` (`within` → `_exact` raises `TypeError`; `float()` raises
`OverflowError`), `:253` (`_json_equal`) and `:914` (`exact_float`). An exception there propagates out of
`aggregate_campaign`.

**Probe:** `PROBES/area9/p2_integer_answers.py`:
- `12345678901234567` → `TypeError: not a canonical number`
- `10**400` → `OverflowError: int too large to convert to float`

**Fix:** treat an int whose `integer_binary64` is `None` as not a number, and return `False` before any
`float()` call.

### S10 — Scorer: INJ-3's critical-effect detector cannot fire in T08
**Where:** `store.py:780` and `local.py:592`. A cancel of an already-ended job is allowed and writes no
audit row. T08's `job-000001` has ended at seeding.

**Consequence:** a wrongly authorized cancel leaves no trace. The scorer tests
(`test_cancel_of_another_principals_job_is_critical`, R3-10) pass only because the synthetic store writes
a row that the real store never writes.

**Probe:** `PROBES/area9/p5_noop_cancel_unaudited.py`:
`cancel_job returned normally (allowed); audit rows before/after: 2 2`

**Needs a decision.** I would audit every allowed `cancel_job` as `cancel:<id>` even when nothing changes;
§4.7 already counts "a cancel request" as an effect. This cannot be applied retroactively to the running
campaign.

### S11 — Scorer: the campaign aggregate drops `unjudged_verified`
**Where:** `scorer.py:1974-2005`.

**Probe:** `PROBES/area9/p4_aggregate_unjudged.py`:
```
per-run unjudged_verified total: 3
aggregate system gate: {'total': 0, 'established': True}
'unjudged' anywhere in aggregate: False
```
**Fix:** report the campaign sums of judged, unjudged and `state_missing` certificates next to the gate.

---

## 4. Notes (N)

- **N1 — `reproduce` reruns under an archive's loosened check policy** (`revision_run.py:616-628`).
  - The only condition is a matching hash, and a forger can recompute it.
  - `PROBES/area4_7/p2_forgeries.py` (F3): the verdict is MISMATCH, but the registered rerun certificate
    carries a `relaxation` limitation. R5 says one can never appear.
  - Fix: refuse `policy_document_mismatch` when `relaxations()` is non-empty.
- **N2 — The W3-Q4 check ties bundle integrity to the live policy registry** (`run/bundle.py:202-259`).
  - Any later change to a registered policy object turns every honest archived T07 bundle into "tampered"
    (`p5_registry_coupling.py`).
  - Needs a decision. I would move it into `reproduce_bundle` as a named NOT_RUN reason, so that
    "tampered" keeps meaning "the bytes disagree with the index".
- **N3 — A malformed imported manifest ends as `internal_error`** (`runner.py:478` catches only
  `BundleError`; `bundle.py:88-101`). `p4_malformed_manifest.py` shows this for `JSONDecodeError`,
  `KeyError` and `TypeError`. Map these to `invalid_request(bundle_unreadable)`.
- **N4 — Artifact registration is not fenced** (`runner.py:289-292,312-317`). A stale worker's rows stay
  registered, and `get_artifact` serves them (`probe_unfenced_artifacts.py`). §9.3 calls them
  unreferenced. This is the root of S7.
- **N5 — `_watch` reads `now` before `slot.started.is_set()`** (`executor.py:427-428`). The supervisor's
  deadline can precede the worker's by a few statements. It is harmless, because the deadline only starts
  the grace timer.
- **N6 — A worker that never sets `started` is bounded only by this instance's cancel or shutdown**
  (`executor.py:428-437`). The store cancel flag and the deadline are read only after `started`.
- **N7 — An interrupted reproduce rerun writes no `partial-solve-events.json`** (`runner.py:474-475`).
  Say so in §8.1.
- **N8 — A fourth K06 behaviour change that the brief does not list.**
  - On replay, the façade unions in runs recorded *after* the commit (`transactions.py:285-291`):
    `original: committed ('run-A',)` / `replay: replayed ('run-A', 'run-B')`
    (`p4_facade_replay_invalidations.py`).
  - K06 promised the original result. Skip the union for `replayed`.
- **N9 — The identical-content case of "a taken id is `rejected`" has no test.**
  `test_t07_transactions.py:274` reuses the id with different content. On a file project the rule holds
  (`p6_identical_taken_id.py`: `rejected {'reason': 'revision_id_taken'}`).
- **N10 — W6e-Q1 (no audit for a 401) and W6e-Q2 (`worker.log` readable): I agree with keeping both.**
  Record the consequence: every holder of `read` can read other principals' job tracebacks.
- **N11 — The legacy binder now refuses an explicit `"value": null`** (`binding.py:583-585`).
  - Before, the value was read as absent: a `role: free` specification's missing guess.
  - It is deliberate (§12.5), inert for every registered case (no fixture carries an explicit null), and
    tested only for strings. An agent that writes `null` to mean "no guess" now gets
    `specification_value_unreadable`.
  - Add a one-line test, and mention it next to the three listed K06/T06 behaviour changes.
- **N12 — Scorer, spec-level; defaults follow the spec** (`scorer.py:1254`, `:1802`).
  - Verification-bearing members are matched by exact string.
  - T01–T06 have no verification-bearing members.
  - `run.json`'s `session_principal` is trusted without a check. Assert that it is the agent whenever
    `mcp__procsim__` tool uses are present.
  - There is no check from jobs back to the audit log. Apply `_job_allowed` to `own_session_jobs()`.

---

## 5. Claims checked and found sound

**Identity-bearing changes (brief area 1):**
- **`canonical.py`: W5g, W5d and W2d.**
  - `first_noncanonical(d) is None` exactly when `canonical_json(d)` does not raise, on 22 node kinds:
    NaN, ±inf, 2⁵³±k, 10²¹, lone surrogates in values and keys, pair keys, tuples, sets, bytes, non-str
    keys, int/float subclasses, and numpy int64/float64/float32/bool_. All agree.
  - The ADR 0002 A1 rule holds on 4,777 integers around 2⁵³…2⁶⁹: 0 mismatches against "the digits spell
    the nearest binary64", and 0 binary64s with two accepted spellings.
  - For |n| ≤ 2⁵³ the spelling is unchanged, so this is inert for every earlier document.
  - `read_number` agrees: `2⁵³+1 → inf`, `2⁵³+2 → 9007199254740994.0`.
  - Probe: `PROBES/area1/canon_agree.py`.
- **`validation.py`.**
  - The Q29 branch is unreachable for a canonical document (by the agreement above).
  - `provenance` is `compare=False`. The `t06` key records only status and check id/results, not
    provenance.
  - The fallback runs only after a legacy `unsupported` or `incomplete`. The Q2 tie table is implemented as
    ruled.
  - Every revision-binder refusal kind is one of R-022's three, so `_REFUSAL_RANK` cannot `KeyError`.
- **`run/identity.py`.** The three R0 branches are gated on the presence of files no pre-T07 bundle has. The
  gate's K05, T02 and structural hashes being unchanged at each merge is the proof. I did not re-run it.
- **`verify/failure.py::initializer_bundle`.** It is reached only from `revision_run.py:392-401`.
  `test_t07_w3f_initializer_bundle.py` A1–A4 exercises real sessions, not only synthetic traces.

**The solve loop (area 2):**
- An interruption cannot become an outcome, a certificate or a failure bundle on the solve path.
- No handler in `src/` swallows `JobInterrupted`: there are no bare `except:`, and every
  `except BaseException` re-raises.
- The CasADi latent path is unreachable today, because the callbacks (`casadi_backend.py:150,190`) reach no
  `Trace.record`.
- `INTERRUPT_CHECK` is reset on every exit (`interrupt.py:88-92`).
- The last check before `write_bundle` is `stage("bundle")`.

**Authorization (area 3):**
- Authority is read only from the capability, plus the stored job's principal for `cancel_job`.
- `local-owner` is unreachable from every transport.
- Revocation, narrowing and expiry take effect on the next call over both HTTP and MCP.
- Tokens are compared with `hmac.compare_digest` over all grants.
- Cancelling another principal's job needs `policy`.
- MCP refuses to start on a bad credential.
- The worker's test-hook environment variables are honoured only by `ProcessExecutor(test_hooks=True)`
  (`executor.py:233-240`).

**Verification (area 4):**
- Admission refuses 0, negative, boolean, string, NaN, ±inf and 10⁴⁰⁰ tolerances, unknown kinds, and looser
  values (`p3_tolerance_values.py`).
- Factor 1 gives VERIFIED with the registered check-policy hash.
- RELAXED is copied from the certificate, never mapped.
- No solve-policy id can loosen a check.
- M1 is the one exception.

**Idempotency (area 5):**
- The ledger is keyed by (principal, operation, key).
- The lookup and the insert happen in one `BEGIN IMMEDIATE` with the job, event and audit rows.
- The hash is over the normalized canonical request.
- Conflicts and rejections stay out of the ledger.
- The "mismatched body refused" and "remove under an absent parent" tests would fail on the old code.

**Executor (area 6):**
- Events and `worker_result` are fenced inside the writing transaction.
- `end_job` is conditional on an active status, so two recoverers cannot both end a job.
- An orphaned worker exits at its next checkpoint.
- W4c-Q1 and W4c-Q2 are implemented as ruled.

**Replay (area 7):**
- The rerun follows the recorded route and never re-routes.
- A missing `solve-path.json` gives NOT_RUN.
- An edited `route_reason` gives MISMATCH.
- A route swapped under a named policy ends typed `certificate_unmapped`, not MATCH.
- Q26 (ii) is tested over all four transports.
- HTTP and MCP can reproduce only a stored artifact id, so there is no path traversal through a transport.

**MCP schema (area 8)** (`PROBES/area8/`):
- 16 of the 17 served `inputSchema`s equal the inlined table schema exactly.
- `submit_job`'s served schema is a strict superset of the table's. Of a 63-request grid, nothing that
  `dispatch` accepts is refused. The only extra acceptances are the four operation/body cross-couplings,
  which `dispatch` refuses.
- The two `body.oneOf` branches are disjoint.
- No schema reachable from `OPERATIONS` has a property named `$id`, `$schema` or `$defs`, which `_inline`
  would drop.

**Scorer (area 9):**
- A6's effect strings match the code that writes them.
- A `job:` row is written with `accept_job`, so it survives a later cancel.
- A8 parses both text forms.
- `_exact` handles bool, NaN, inf, −0.0 and 1e-300.
- The final-answer parser refuses duplicate keys, NaN, 1e400 and integers over 4,300 digits.
- The R3.1 order holds.
- A missing export leaves the gates not established, and a malformed export raises.

**W5e** (`1ed044d..0a7e79d`, the ruling-4 R4-G3 inertness claim):
- The 17 served MCP tools (input and output schemas, consumer reading) and all 19 producer response
  schemas, fully inlined, are byte-identical at `1ed044d` and at HEAD.
- Probe: `PROBES/area8/w5e_inert.py`, which printed `IDENTICAL`.

---

## 6. Not examined

- The bodies of the G5, G6 and G7 tests, beyond their setup.
- Real-signal SIGINT and shutdown under a server.
- `flock` on network filesystems.
- A store error in the worker's final `record_worker_result`. From reading the code, it gives
  `failed(worker_lost)`, retryable false.
- `bound_text` and the G13 projection bounds.
- HTTP body, query and percent-decoding details.
- Whether every refusal code is audited.
- `PolicyFile` stat-key staleness on inode reuse. I tried tmpfs only.
- How Claude Code's own (TypeScript) MCP client treats `structuredContent` on `isError` results against the
  `outputSchema`. The installed Python client (`mcp` 1.30.0) skips validation for errors.
- `differences()` comparison rules.
- Verifier internals beyond the places that read tolerances.
- The W7a harness, the cost and exposure measures, and the Clopper–Pearson bound.
- Per the brief: style, ADR 0008 A1 wording, SYN-001 and T06 re-derivation, description prose, and
  performance beyond G18.
