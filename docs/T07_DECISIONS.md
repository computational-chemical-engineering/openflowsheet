# T07 — decisions log

Append-only; grepped, never read whole.

## 2026-09-27

T07 opened on `wp/T07` from `main` `78d3647` on Frank's instruction relayed by process-simulator-75.

DECISION: route T07 design (Application surface, Job/event/capability schemas, concurrency, auth,
HTTP/MCP, V17 harness) to one `architect` pass before any code → yes. Alternative: build-lane design with
review afterwards. Reason: frozen-interface list (K06/T07 row) and ADR 0008 A1 J1–J5 bind the schemas; the
frozen `Application` protocol was never implemented by K06, so reconciling it may widen a frozen
interface. Commit: `012d1e6` (brief).

Design note `docs/design/T07-jobs-and-bindings.md` and ADRs 0019 (Proposed, Frank-gated) and 0020
(Proposed, design lane) committed at `71c2e4e`.

Frank's answers (question round, 2026-09-27):
- F1 ADR 0019 (JobControl + Inspection sibling protocols, 8 schemas added to the frozen list,
  reused-key-different-body refused): **approved**. Accepted at T07's tested evidence.
- F3 V17 campaign: **one pinned Sonnet model, 10 tasks × 3 = 30 headless sessions** on the existing
  login.
- F5 v0.1 exclusions (resume, branches, in-band policy administration, MCP over HTTP, extra solve
  policies): **accepted**; each reported explicitly unsupported.
- F2 (identity re-baseline if W0.4 shows the F5 fix moving `t06`): default stands — isolated commit
  held unmerged; asked only if W0.4 measures a move.
- F4 (human review of ~17 tool descriptions): default stands — V17 proceeds, manifest records
  `pending`; Frank reviews when convenient.

DECISION: R-088 Q24/Q25 (K04 certificate policy, note S10) → not briefed in T07's specifier round;
left at their defaults and handed on as a separate K04 amendment. Alternative: include in the round.
Reason: non-blocking for T07, keeps the specifier pass on V17. Reversible by: a later specifier brief.

W0 merged (`2476493`, measurements `docs/t07-measurements.md`). Identity baseline equal to expectations;
`T06-revision-v2` carries newton_refined + F4 (no D-Q1); F5 moves no identity entry (F2 does not arise).

DECISION: E1 — `mcp` ≥ 1.10 needs `jsonschema>=4.20`; base pin 4.19.2 → bump the base pin (≈4.26.0)
in one isolated commit, proved inert (gate + identity). Alternative: pin `mcp` 1.9.4 (lacks protocol
2025-06-18 and structuredContent). Reversible by: revert that commit and pin mcp 1.9.4. Engineer on
`wp/T07-w2d`.

DECISION: E5 — certifi (MPL-2.0) in the optional `server` extra is acceptable under ADR 0006 (Frank
allowed the LGPL, 2026-09-17; MPL-2.0 is weaker, file-level copyleft; used unmodified). The design
note's D-Q5 "GPL-family incl. LGPL stops" was stricter than ADR 0006 and is read as "GPL-family".
Alternative: refuse and replace certifi (it is httpx's CA bundle; no drop-in). Reversible by: a
design-lane ruling. Four compiled distributions in the closure (cffi, cryptography, pydantic-core,
rpds-py), all with aarch64 wheels.

DECISION: E2 (G9 agreement fails on NET-02, NET-09) and E7/D-Q3 (12 SYN-001 revisions bind only via the
legacy binder, so `solve` cannot reach them) → design-lane ruling round 1 (fresh `architect`).
E3/E4 (`--max-turns` absent from `claude --help`; settings/memory isolation) → W7a canaries.
E6 (policy constructor under `tests/`) → W3 moves it into `src/`, `policy_sha256` unchanged.

W1 merged (`daf0bb7`; 8 schemas, `application/types.py`, `jobs/model.py`, 149 tests; gate 4398). W1
questions R3–R6 (validator provenance vs frozen validation-report schema; JobResult error member;
RELAXED in RunResult.verification_status; job_id/event_count lifecycle rules) added to ruling round 1.
W2 (a, c, then b) started on `wp/T07-w2`; the transaction-result/validation assertion is `xfail(strict)`
until R3 is ruled.

Ruling round 1 (architect; design note "Ruling round 1", ADR 0020 D4/D5 amended). R1: fallback on
unsupported|incomplete, G9 compares against the route solve takes; R2: `solve` routes revision_eo, else
legacy_eo (`T04-W12` joins the application policies; reserved policy id `"default"`); R3: validator
provenance fixed to the frozen schema, comparisons ignore provenance; R4: JobResult has `error`;
R5: RELAXED included (reachable: any tightened check policy); R6: lifecycle rules 11–12. No identity key
or registered report moves.

DECISION: F6 (outcome-driven fallback revision_eo → legacy_eo) → the design default: build it (W3d) only
if W3a measures a corpus revision that fails on revision_eo and verifies on legacy_eo; else log for T08.
Not asked of Frank: his standing directive ("if a method cannot solve a hard case and the solver then
switches to another method this is also fine") already authorizes the fallback; the only question is
whether to build a path no registered case exercises, and untested code is worse. Alternative: build it
unconditionally. Reversible by: W3d is a separate commit with its shape fixed in R2.7.
S-R5 (name for tighten-only policies) and S-G (GUESS-role specs on the revision binder) → specifier,
defaults unchanged, not blocking T07.

W2d merged (`4a78072`): jsonschema 4.19.2 → 4.26.0 (`450736b`; identity byte-equal before/after; project
`.venv` upgraded and editable metadata refreshed); Q29 entry refusal (`be1a2ee`, G10: 283 leaves × 8
vectors, 0 exceptions); `8f0fb3a` updates T06 A68 / A100 (a) expectations to `document_not_canonical`.

DECISION: A68/A100 (a) supersession → merged as the isolated commit `8f0fb3a`, ruling asked of `specifier`.
Alternative: read fields keep their field codes and the entry check covers only unread leaves. Reversible
by: revert `8f0fb3a` and narrow the entry check in `src`.

W2 merged (`c108d41`; store, authz, transactions; 4484 passed + 1 xfail (R3 → W3b) on its branch;
identity equal). `4a355f2`: `LocalApplication` switched to `canonical.first_noncanonical` (one walk; a bad
key's pointer names its member, as W2d registered).

DECISION: `local-owner` is a reserved principal/capability id — a policy naming it is refused, and
`project grant` refuses it. Alternative: allow it (a token could then share the owner's idempotency
scope and cancel the owner's jobs). Reversible in `ProjectPolicy.__post_init__` and `grant`. For the
reviewer: W2's other 14 recorded choices (engineer report), notably K06 behaviour changes beyond ADR
0019 D3 — reusing a taken revision id with identical content is now `rejected` (§4.2), and `remove`
under an absent parent is a no-op instead of creating parents; `policy_sha256` column added to
`revisions` (§10.3 vs §9.2).

V17 task specification committed: `docs/derivations/T07-v17-tasks-spec.md`, twin
`docs/derivations/scripts/t07_reference.py` (2808/2808 claims, `--emit` byte-identical, sha `cba24a92…`).
Its four register entries keep "R-1xx" until the W8 register pass numbers all T07 entries together
(ADR 0019/0020 D-entries first, from R-091).
A68/A100 (a): specifier accepts the supersession; `8f0fb3a` stands; T06 spec Amendment 6 added.
Specifier finding F1 (no operation or artifact exposes a solved state's values → T06-task optimize
cannot be posed, numeric answers and the system false-verification counter lose their basis) with
F2–F4, F6 → design ruling round 2 (fresh `architect`). F1, if adopted, lands as W3e after W3 merges.
Preferences left at the specifier's defaults unless Frank objects: U1 60 turns / 30 min wall cap
(design had 40/20; T06-task needs ~47 calls); U2 fixed payload placement; U3 effort pinned to the
recorded default.

DECISION: V17 spec F2 (store-export members §4.8), F3 (registered-but-not-offered policy → `unsupported`,
unknown id → `not_found`), F4 (W5a tests: `read` covers all principals' jobs/artifacts; imported bundle
members reachable), F6 (G16's 40 reference runs timed separately, 300 s) → adopted by the build lane as
the specifier recommends. Alternative for F3: keep `not_found` (contradicts Frank's "reported explicitly
unsupported"). Reversible: each is one test/harness item. F1 → architect ruling round 2 (running).

W5c merged: `MODEL_SIGNATURES` (ports, required, zero, pins, choices) is the builders' single source;
66 binding outcomes pinned, 17 756 perturbed documents bound identically old vs new; identity equal.
Port phase rules stay in the builders (not in §4.2's signature) — W5a may list them later as a separate
change.

Ruling round 2 (architect): V17 F1 adopted with four amendments — `solution-state.json`
`{schema_version, state_sha256, variable_ids, variables}` written iff a certificate is written; R0 takes
`variable_ids` only; no run_id, no verdict copy; `run/solution_state.py::inconsistencies` (5 checks) feeds
`verify_bundle`; no Inspection view, no non-converged iterate, SYN-001 bundles unchanged. New frozen schema
`schemas/solution-state.schema.json` (+ `artifact_ref.kind` value `solution_state`) under the ADR 0020
amendment. No identity key moves. W3e before W4a/W5/W6/W7c.

DECISION: the ninth frozen schema (solution-state) → proceed under the design-lane ADR 0020 amendment and
tell Frank in the next report, not ask first. Alternative: stop for Frank's approval as for ADR 0019.
Reason: additive, a bundle member, no existing signature or schema changes; the frozen-list change rule
requires a design-lane ADR, which this is. Reversible by: reverting W3e (one merge) before T07 merges.
F1-a (no near-zero floor for cross-architecture state comparison; errs toward MISMATCH) → default kept.

W4b merged: `INTERRUPT_CHECK` in `Trace.record`, `JobInterrupted(BaseException)` and `interruptible(...)`
in `application/jobs/interrupt.py` (not `jobs/executor.py`: avoids an import cycle; executor re-exports).
Hook overhead 0.1–0.35 % (noise; G18 ≤ 2 %). Identity equal.
DECISIONS (engineer, accepted): `cancel_reason` is a callable (distinguishes `server_shutdown`); the
broad-except lint allows a handler only if it re-raises unconditionally (W2 added two cleanup-then-raise
`except BaseException`, `store.py:291`, `local.py:114`).
For the reviewer / W4a: (1) regions record into an inner trace absorbed by `executor._absorb`, so an
interruption loses the interrupted region's events — `partial-solve-events.json` ends at the last
absorbed plan-trace event; (2) `verify_revision` has no `record` call, hence no cooperative checkpoint
(the forced kill bounds it); (3) CasADi 3.8.0 converts a BaseException raised inside a Python
`ca.Callback` into RuntimeError, which `casadi_backend.py:450/507` would turn into an `error` evaluation —
latent (no `record` is reachable from a callback today); never place an interrupt check in the
property/provider path.

W3 merged (`93605ae`, conflicts in cli.py and measurements resolved by keeping both sides; `8621f1f`
drops W2's satisfied xfail). Gate at `8621f1f`: **5170 passed**. Identity after merge: K05 `9a7b4e6d…`,
T02 floats `9a8a5baf…`, syn001.py `67e47281…` — equal. W3 results: D-Q3 count 0 (all 8 both-bind
revisions VERIFIED on revision_eo; on legacy_eo they have no certificate path) → **W3d not built, F6
logged for T08**; G8: 48/50 routed, 45 bundles, all verify_bundle ok and rerun MATCH; G9 holds; 28
validate() moves DRAFT→READY, none in a key; every emitted validation report validates; W3e
solution-state landed (largest 2 765 B).

Open questions from W3 (defaults in force = what the code does; to the next design round):
- W3-Q1: INITIALIZATION_FAILED at a `solve_eo` step with no RegionResult has no failure-bundle mapping
  (SYN-001-UL-C3X, SYN-001-A02-360-no-guess: READY, admitted, end `unsupported(failure_bundle_unmapped)`,
  no bundle).
- W3-Q2: ruling R1.2's tie-break (revision binder wins) would move T06 A04's registered STR-02 message;
  the engineer kept the legacy refusal on a tie (nothing registered moves). Following the ruling is
  `>`→`>=` in `validation._structural` + A04 in registry.yaml + one T01 test.
DECISION: W3-Q3 (R0 of `execution_plan` differs in memory vs on disk: 3.0 vs 3) → hash
`artifact_r0_sha256` over the documents as written (recomputable from the bundle); the `t07` key uses the
same. Alternative: in-memory form. Reversible by: W8 script choice.
DECISION: W3-Q4 (forged `policy_requested` in `solve-path.json` still reruns MATCH) → add a
consistency check in W4a (resolved `policy_requested` must give the manifest's `policy_sha256`), feeding
`tampered`. Alternative: leave (the manifest hash already pins the effective policy). Reversible: one check.
W3-Q5: `reproduce(rerun=false)` mode `inspected_archived_results` per Q26 text — kept.
Cleanups for W4a: `solve-path.json` needs an artifact kind; `validation.utc_timestamp` duplicates
`store.utc_timestamp`; `policy_unsupported_on_route` maps to `unsupported`.

W7b merged: `benchmarks/t07/v17/scorer.py` (`score`, `aggregate`, CLI), 103 tests (G16-a), only
`canonical_json` imported from process_runtime. Export-shape assumptions A1–A9 in its docstring, to be
reconciled in W7c against real exports. Scorer readings that change a gated count (to the next design
round, `specifier`; the code's reading is in force until then):
- W7b-I1: a VERIFIED certificate whose state lacks a registered coordinate → own count
  `state_missing_verified`, reported as a harness defect; the system gate is then "not established".
- W7b-I2: a verification-bearing answer member is judged exactly like a claim (T08 `CONVERGED` about a
  non-existent job id counts as false).
- W7b-I3: an allowed cancel of another principal's job counts as unauthorized AND critical.

W1f + W4a (branch `wp/T07-w4a`, base `e37f696`; engineer). Commits b214640 (W1f), b27d683, d416964,
07c98f8, 8be5b96, 3f5a08e. Gate 5218 passed; identity equal (K05 `9a7b4e6d…`, T02 floats
`9a8a5baf…`, syn001.py `67e47281…`, keys t02–t06 as W0.1). Measurements: `docs/t07-measurements.md`
"W4a". Engineer's choices (each isolated, reversible as stated):
DECISION: `solve-path.json`'s kind → `solve_path` (named after its file, as `solve_policy`,
`check_policy`). Alternative: `route_record`. Reversible by: one enum value + table row (b214640).
DECISION: `submit_job` checks the canonical form before the schema (as `dispatch` and W2's
`commit_change` do; §4.2 lists schema first). Alternative: §4.2's order (a NaN tolerance would read
`invalid_request`). Reversible by: swapping two blocks in `local._submit`.
DECISION: `Job.policy_sha256` = the project-policy document hash (§5.5, the schema's description),
not the resolved solve policy's (ruling R2.3's sentence lists `Job.policy_sha256` among the members
carrying the resolved policy). QUESTION for the design lane (W4a-Q1). Reversible by: one line in
`local._submit`; the resolved policy's hash is `RunResult.policy_sha256` either way.
DECISION: reproduce admission — missing artifact `not_found`, not a `replay_bundle`
`invalid_request` (`/body/bundle_artifact_id`), then §5.3 steps 7–8, which bound every job.
Alternative: steps 7–8 for solve only. Reversible by: `admission.admit_reproduce`.
DECISION: `effective_budgets.max_property_calls` = the effective solve policy's (tightened or not);
`null` for reproduce. Reversible by: `local._admit`.
DECISION: stages — `resolve` = `select_route` + `resolve_policies` (no re-validation; the revision
is immutable), `bind` = a fresh `bind_route` on that route, the rest called back from
`run_revision_session`; `completed` = the stage's index (a completed job's progress stays 5/6
`bundle`; no closing progress). Alternative: a final 6/6 event (§6.4 does not name one).
DECISION: artifact ids — `<job_id>:bundle` (solve), `<job_id>:rerun` (reproduce's rerun, §12.3's
`rerun/`), `<job_id>:<file>` (partial trace, replay report), `import-<nnnnnn>:bundle`; members
`<bundle id>/<file>`; an import registers only files with a §5.4 name.
DECISION: a solve that never resolved its request (cancelled queued, interrupted at `resolve`) gets
its `RunResult` resolution (route, resolved policy id, both hashes) re-derived from the stored
revision; run facts null. Alternative: null hashes (the route cannot be null in the schema).
DECISION: `VerifierError` → `failed(verifier_refused)` with `ApiError(unsupported, "verifier_refused")`,
its text to the log only (D9 (4)). QUESTION W4a-Q2: the code (the closed enum has no exact fit).
DECISION: `reproduce()` whose job ends with no report and no error (cancelled/timed out) raises
`not_ready` (retryable false). QUESTION W4a-Q3: the closed enum has no better code.
DECISION: `KeyboardInterrupt` → `cancelled(keyboard_interrupt)`, `interruption: null` (neither
cooperative nor a supervisor kill); the partial trace is written, then it is re-raised.
DECISION: a cancel recorded in the store by another instance reaches an inline job at its next stage
boundary (one store read per stage), besides the in-process signal. Reversible: `_Body.at`.
DECISION: W3-Q4's check admits §8.3's tightening (the resolved policy with `solve-policy.json`'s
lower `max_property_calls` must hash to the manifest's); lives in `run/bundle.py` with a lazy import
of `application.policies` (the `run.session` precedent).
Pending (not W4a's): `get_artifact` (W3e test (e); F4's artifact half — imported members are
registered, reachable when W5a lands); ADR 0008 A1 (d) consumers (W5/W6); process executor,
`worker_log`, forced stop, G6 inline-vs-process, G7 (W4c); transports' `auto:` refusal (W5a).

W4a + W1 follow-up merged (`5d31e13`): runner, `InlineExecutor` behind `COMPUTE_LOCK`, the seven JobControl
methods, `solve`/`reproduce` as compositions, job/job-event fixtures from real jobs, W3-Q4 check. Gate at
`5d31e13`: **5321 passed**. Identity equal (engineer's run at its head). Inline job overhead 0.034 s median.
Open API questions (defaults in force, to the next architect round): W4a-Q1 `Job.policy_sha256` = project
policy hash (§5.5) vs resolved solve policy (R2.3); W4a-Q2 `VerifierError` → `unsupported("verifier_refused")`;
W4a-Q3 `reproduce()` ending cancelled/timed-out raises `not_ready`.

Ruling round 3 (`specifier`; design note + V17 spec, "Ruling round 3"): W3-Q1 → a registered
`initializer_bundle` (taxonomy "initialization and recycle failures", action `supply_initial_guess`) for
INITIALIZATION_FAILED without a region result — also needed by V17 fixtures FX-04/FX-07; G8 becomes 47
bundles. W3-Q2 → ties split by kind: `incomplete` → legacy (STR-02/A04 unchanged), `unsupported` →
revision binder (the legacy "only topology the binding knows" message is false in T07). W7b-I1, I2
confirmed; I3 confirmed + INJ-3 attribution. Nothing registered moves; twin still 2808/2808.
Open with defaults: Q1-O1, Q1-O2, R3-O2; R3-O1 (T03's bundle now names the unit and a direction, making
the diagnose task easier than planned — kept as registered; told Frank).

W3f (ruling round 3, branch `wp/T07-w3f`): Q1 `initializer_bundle`, Q2 tie by kind, scorer R3.3 (b).
Both new bundles equal the note's digests; identity equal; 5359 passed (`docs/t07-measurements.md` W3f).
DECISION: `initializer_bundle` refuses (a `ValueError`, a defect) a step that is not a detail-less
`solve_eo` `INITIALIZATION_FAILED` with an accepted message, or whose events do not open and close
its region exactly once; `solve_route` checks the same conditions first, so any other step still ends
`failure_bundle_unmapped`. Alternative: read the first/last region event. Reversible: `verify/failure.py`.
DECISION: the W4a unmapped-job test is kept; it reaches the unmapped path by making
`revision_run.initializer_source` refuse UL-C3X's message (no real record is unmapped any more).
DECISION: Q2-A5 in the suite is "no corpus revision is an `unsupported` tie" (the only case the changed
condition touches); the before/after comparison of the 50 reports is a measurement (W3f.3).
Alternative: pin the 50 reports as a fixture.

W4c + W4d (branch `wp/T07-w4c`, base `2ad5bbd`; engineer). Commits 08ca206 (process executor), af199e3
(G20), a8a3294 (W4d). Gate 5341 passed; identity equal (K05 `9a7b4e6d…`, T02 floats `9a8a5baf…`,
syn001.py `67e47281…`). G18 job overhead median 0.501 s (≤ 1.0 s). Measurements: `docs/t07-measurements.md`
"W4c and W4d". Engineer's choices (each isolated, reversible as stated):
DECISION: how a Python caller gets `test_hooks=True` → `LocalApplication.open(executor=...)` also takes an
unbound `ProcessExecutor` instance; `"process"` constructs one without hooks. Alternative: a `test_hooks`
keyword on `open` (a wider surface). Reversible by: `local.open`'s `executor` annotation and 6 lines.
DECISION: `jobs.worker.main` takes two arguments beyond §9.1's five: `cancel_reason` (a shared int, so a
set cancel event reads `cancel_requested` or `server_shutdown`) and `started_event` (the supervisor starts
its wall-time clock when it sees it, after the worker's, so the worker's cooperative deadline always comes
first). Alternative: infer the reason from the store's `cancel_requested` flag. Reversible: `worker.main`.
DECISION (QUESTION W4c-Q1 for the design lane): on a passed deadline the supervisor does **not** set the
cancel event (§8.2 step 1 says it signals it): the worker's own deadline, which started first, is the
cooperative stop, and the event would make the worker report `cancelled(cancel_requested)` instead of
`timed_out`. It waits `grace_s` and kills → `timed_out(wall_time_exhausted, forced)`. Alternative: a third
reason code on the event. Reversible by: `ProcessExecutor._stop`.
DECISION: the worker writes `started` (§6.2), so a worker dying before `start_job` leaves the job `queued`;
the supervisor ends it `failed(worker_lost)` with no outputs (rule 4: no output before `started`), and its
log stays on disk unregistered. A started job's non-empty `worker.log` is registered and emitted last, also
on `worker_lost`, where `detail.log_artifact_id` names it.
DECISION (QUESTION W4c-Q2): `worker_lost`'s error is `ApiError(internal_error, fixed message, retryable
false, detail {exitcode, log_artifact_id?})`; a worker that cannot be started at all: the same with
`exitcode: null`, retryable true. Alternative: `retryable: true` for a lost worker too (an OOM kill is
transient, but the key replays the failed job; a re-run needs a new key, J6). Reversible: `_finish`.
DECISION: the executor settings (`max_workers`, `grace_s`) are the policy's at `open`, not hot-reloaded.
DECISION: an orphaned worker (parent pid changed) `os._exit(3)`s at its next checkpoint (`Trace.record`,
stage boundary, pause poll) and writes nothing; recovery ends the job `owner_lost`. Workers ignore SIGINT
(the supervisor governs them) and are `daemon` (an owner that exits without `close` takes them down; the
next open recovers the job `owner_lost`).
DECISION: the pause hook writes one line to descriptor 2 before its `paused` file (which holds its pid), so
tests see the fd-level redirection and the `worker_log` output.
DECISION: G20 follows W0.5 (comments and strings skipped via `tokenize`); `COMPUTE_LOCK` matches no §9.5
pattern and is not an allowlist entry (§9.5 expects it among the entries); the patterns are not widened.
The W2 `except BaseException` sites are outside every pattern, so not in the scan.
DECISION: W2's test "`executor="process"` is unsupported" now checks an unknown executor name instead.
Note for merges: G20 fails on any new `@cache`/`ContextVar`/… in `src/` until it is allowlisted with a
justification — by design (§9.5: "forces a decision").

W3f and W4c/W4d merged; gate at `38b7bca`: **5379 passed**. G4 1 job / 49 replayed / 409 on mismatch /
same job_id after restart; G5 process cooperative 0.108 s, forced 0.610 s; G6, G7 byte-equal; G18 job
overhead median 0.501 s (≤ 1.0 s); G20 no unlisted global state. Open API questions added to the next
architect round (defaults in force): W4c-Q1 (the supervisor does not set the cancel event at wall-time
deadline, so the job ends `timed_out` rather than `cancelled`), W4c-Q2 (`worker_lost` →
`ApiError(internal_error)`, not retryable).

W5a (branch `wp/T07-w5a`, base `2ad5bbd`; engineer). Commits fce4dea (projection, Inspection), 4eb15d9
(bound_text marker), 0504ac5 (OPERATIONS/dispatch, G11/G13/G14-bijection), f924502 (lone surrogates).
Gate 5357 passed; K05 `9a7b4e6d…`, T02 floats `9a8a5baf…` equal. No G20 pattern added. Measurements:
`docs/t07-measurements.md` "W5a". Engineer's choices (each reversible as stated):
DECISION: `bound_text` keeps its `…[+N chars]` marker inside the limit (a bounded string is ≤ limit code
points in total). Alternative: the note's literal "cut to limit, then append" (≤ limit + marker).
Reason: `api-error.schema.json` caps `message` at 2048 = §10.4's bound, so the literal reading makes a
bounded message fail its schema (G13 hit it: jsonschema messages echo the request). Reversible: revert 4eb15d9.
DECISION: the forbidden set is §10.4's list plus U+007F (DEL, `Cc` like C0/C1) and lone surrogates
(unencodable in UTF-8). Alternative: the list exactly. Reversible: `projection.FORBIDDEN_RANGES`.
DECISION: `dispatch` refuses a string holding a lone surrogate `document_not_canonical` (pointer), after
`first_noncanonical`. QUESTION W5a-Q1 (design lane): `canonical.first_noncanonical` does not flag such a
string though `canonical_json` cannot write it (its docstring says the two agree); in-process
`commit_change`/`validate` with one still raise `UnicodeEncodeError` (I4). Default: dispatch only;
canonical.py untouched (Q29-registered). Reversible: revert f924502.
DECISION: projection semantics the note leaves open — the target is level 0 and always shown; a non-empty
container at level = depth is elided; a marker's `n` is the size of the node at its pointer (members or
items), also for the nested-array cut (`items` = the full length, not the count cut); empty containers are
never elided; the size cap is measured on the bounded canonical size of the whole Projection document;
`truncated` iff the cap forced a depth below the one asked (or depth 1 still exceeds); an offset cursor is
unpadded base64url; an offset past the end is an empty last page; a cursor on a non-array target is
`invalid_request`. `Projection.sha256` is the stored whole's: `document_sha256(Revision.as_document())`
(= a bundle's `revision.json`), an artifact's registered hash (file bytes; a bundle's dirhash), the
structure document's.
DECISION: `get_artifact` projects a file as JSON iff it is `.json`, parses strictly (no repeated key) and
every number is canonical; otherwise as its text lines (`worker.log`, a mangled import). Alternative:
`unsupported`, which would hide a log from MCP. `artifact_bytes` of a `replay_bundle` → `unsupported` (a
directory; its members export one by one).
DECISION: Inspection results (`ProjectSummary`, `ModelRegistryView`, `RevisionSummary`, `Projection`) have
no published schema, like W4a's composite results; `operations.py` states their response schemas for W6's
`outputSchema`, and the tests hold every response to them. QUESTION W5a-Q2 (design lane): should these
shapes be frozen schemas before T07 acceptance, given the protocols are? `RevisionSummary` =
{revision_id, parent_revision, content_sha256, title (string|null), principal_id, created_at, head};
`ProjectSummary.job_counts` names all six statuses (newer ones kept); `server.git_commit` always null (no
subprocess). Reversible: types.py + the schemas in operations.py.
DECISION: requests are flat objects of the method's parameters (path parameters as members), ids by §5.1's
`id`/`job_id`/`artifact_id`; `reproduce.policy` required (frozen arity); `preview_change` = the ChangeSet
members minus `idempotency_key`; `wait_job.timeout_s` clamped to 30 (not refused); `auto:` refused
`invalid_request` at `/idempotency_key` for `submit_job` and `commit_change`; refusals before the method are
audited under the caller (an unknown operation name bounded to 128); every ApiError leaves `dispatch`
bounded. `OPERATIONS[*].right` is restated (operations.py imports only contract/types/projection/canonical)
and pinned to `authz.OPERATION_RIGHTS` by test.
Observations: `validate`'s report carries a clock `timestamp`, so two identical reads differ (W6's
conformance comparison must strip it); a document may itself contain a `$elided` key (forged markers are
read-only pointers — harmless, not claimed otherwise).

W5a merged (`9b541df`): `operations.py` (20 operations, rights pinned to `authz.OPERATION_RIGHTS`),
`dispatch`, `projection.py`, the eight Inspection methods, `get_artifact`; G11 1280 cells via dispatch; G13
(>5000 strings, all bounded); G14 bijection; W3e (e); F4 artifact half. Gate at `9b541df`: **5415 passed**.
Architect ruling round 4 launched on W4a-Q1..Q3, W4c-Q1..Q2, W5a-Q1 (lone surrogates), W5a-Q2 (freeze the
Inspection result schemas?), bound_text marker. W5b (CLI `api`, serve stubs) and W6d (server extra, pins,
licences, CI) running.

Ruling round 4 (architect; design note "Ruling round 4", ADR 0019 Amendment 1): W4a-Q1 project-policy hash
stays (R2.3 struck); W4a-Q2 `unsupported("verifier_refused")` stays; W4a-Q3 `not_ready` stays, detail gains
`reason`, retryable only for `server_shutdown` (W4e); W4c-Q1 §8.2 amended to the implemented mechanism;
W4c-Q2 `worker_lost` not retryable (W4e pins the table); W5a-Q1 `first_noncanonical` flags lone surrogates
(ADR 0002 D3 via RFC 8785 I-JSON; `canonical_json` raises typed; W5d); W5a-Q2 Inspection result shapes
frozen now as `schemas/application-results.schema.json` (W5e, inert by R4-G3 snapshot); bound_text marker
inside the limit confirmed + key suffix within 256 (W5f). Nothing registered, no identity moves.
Open with defaults: R4-O1 (noncharacters, specifier), R4-O2 (verifier's own failed property call,
specifier), R4-O3 (store_error retry storms, measure in W8).

DECISION: the tenth frozen schema (`application-results`, ADR 0019 Amendment 1) → implement W5e in an
isolated merge and **hold that merge until Frank answers** (I told him earlier I would ask before it
lands). Alternative: merge under the design-lane ADR as for solution-state. W6 does not depend on it
(the shapes are unchanged; only their location moves). Reversible by: not merging W5e.

DECISION: W6d, where the `server` closure's transitive pins live → in `requirements.lock`, beside the
base and `dev` pins (§11.1 names that file, and `dev` is already there). `make venv` and `make lock`
install `.[dev,server]`. The default install is proved by a CI job, `default-install`, that installs
`.[dev]` with the lock as *constraints* (`pip install -c requirements.lock -e '.[dev]'`), checks that
`mcp`, starlette and uvicorn are absent, and runs the whole suite (locally: 5386 passed, 2 skipped).
Alternative: a separate `requirements-server.lock`. Reversible by: moving the 23 added lines into
that file and installing both files in CI (one commit).
DECISION: W6d, G19's verdict → it also fails on a licence outside a closed allowlist, not only on a
GPL-family or unresolved licence, because a new licence family goes to the design lane (W6d brief).
The list and its reasons are `scripts/t07_licence_inventory.py::ALLOWED`. Alternative: G19 as
written (GPL-family/unresolved only). Reversible by: deleting the `not-allowed` branch of
`verdict_of`.

W6d merged (`10e610d`): `server` extra mcp 1.30.0 / starlette 1.7.0 / uvicorn 0.54.0, transitive pins in
`requirements.lock` (+23 lines), `docs/t07-server-licences.json` + G19 (29 distributions, closed allowlist,
MPL-2.0 certifi only non-permissive-style), CI installs the extra on both architectures plus a
`default-install` job proving the core works without it. Project `.venv` now has `.[dev,server]`.
Engineer choices kept (each one commit): lock location `requirements.lock` (not a separate file); G19 also
fails on any licence outside a closed allowlist. W6a (HTTP) and W6b+W6c (MCP, descriptions, REVIEW.json)
launched; CLI serve wiring after W5b merges.

W5b (branch `wp/T07-w5b`, base `9b541df`; engineer). Commits 5c51576 (existing-command pins, captured
before the change), 3acd4cd (`api`, `serve-http`/`serve-mcp` stubs), cb8f6f9 (ADR 0008 A1 (d), CLI).
Only `application/cli.py` changed outside tests, so identity was not re-run. Measurements:
`docs/t07-measurements.md` "W5b". Engineer's choices (each reversible as stated):
DECISION: the syntax is §11.5's (`--json` | `--json-file`, required, one of), not the brief's
`--json-body`; `--json-file -` reads stdin. Reversible: `build_parser`.
DECISION: exit codes are 0 = domain result, 2–15 = `ApiErrorCode` in §5.8's order (`cli.API_EXIT_CODES`),
**1 = no call was made** (the request file cannot be read, the project cannot be opened: `StoreError`,
`PolicyRefusedError`; message on stderr). argparse's usage error is also 2 (a malformed request either way).
An ApiError is printed to stdout as canonical JSON, like a response. A non-ApiError exception propagates
(traceback, exit 1) — the local owner sees the defect; no `internal_error` is synthesized by the CLI.
Alternative: map a crash to `internal_error`/15. Reversible: `command_api`.
DECISION: the CLI parses the request with `canonical.load_document` (duplicate keys refused; YAML accepted
for non-`{`/`[` text as the loader does); a parse failure is `invalid_request`, `detail.pointer = ""`,
audited under the operation's name, the parser's message on stderr only (§10.4: exception text never
enters a response). An unknown operation is sent to `dispatch` so its refusal is `dispatch`'s own; an
operation whose row lacks `cli` is refused `invalid_request` "no such operation on the command line" with
the CLI's operation list, audited (unreachable today: every row carries `cli`). Reversible: `cli._request`.
DECISION: `artifact_bytes` writes raw bytes to `--raw-out FILE`, else to stdout's binary buffer, and prints
nothing else; `--raw-out` on a JSON operation is a usage error (exit 2). Reversible: `command_api`.
DECISION: `serve-http` (`--project`, `--host 127.0.0.1`, `--port 8765`, `--allow-remote`; a non-loopback
host without `--allow-remote` is exit 2) and `serve-mcp` (`--project`, `--token-file` or
`PROCESS_RUNTIME_TOKEN_FILE`; neither is exit 2, no anonymous server) print an `unsupported` ApiError and
exit 14. They do not open the project or read the token. Reversible: the two handlers.
DECISION: the byte-identity pins mask only what cannot repeat between two runs of the same command on
one host (temp dir, validation timestamp, grant token, the bundle's recorded host description and the
certificate's solution bound). A raw, unmasked before/after capture on this host differs only in the
timestamp and token lines, exactly as two runs of the base CLI do. There is no `gate` CLI command
(§11.5 and the cli.py docstring name one; the v0.0 gate is `scripts/v0_0_gate.py`); none was added.
QUESTION W5b-Q1 (design lane): `api submit_job --executor process` returns the job `queued`, and the CLI
then closes the application, whose `close` ends queued jobs `cancelled(server_shutdown)` (measured: the
next `get_job` shows `cancelled`/`server_shutdown`). A one-shot CLI under the process executor therefore
cannot run a job, and §11.6's `CliClient` "with executor=process" would fail its submit scenarios.
Options: (a) the CLI under `process` waits for the jobs it accepted to end before closing (needs an
executor drain, a non-CLI change); (b) W6e's `CliClient` uses `inline`, and `--executor process` is
documented as useful for reads only; (c) drop the flag. Default: (b) — the flag stays as §11.5 fixes it,
nothing else changes. Reversible: a later ruling.
Observation: twin projects agree on every response once §11.6's clock members are removed **and** the
`sha256`/`size_bytes` of `run_manifest` and `replay_bundle` refs (and any `manifest_sha256`): the manifest
records `started_at` and `elapsed_seconds`, so its bytes, and the bundle's dirhash, differ. §11.6's strip
list does not name them; W6e's conformance comparison will need the same rule.

W5b merged (`c548768`): `process-runtime api <operation> --project DIR (--json|--json-file)`, exit codes
0 / 1 (no call) / 2–15 per api-error code; serve-http/serve-mcp stubs `unsupported` (exit 14) until W6.

DECISION: W5b-Q1 (a one-shot `api submit_job --executor process` always ends `cancelled(server_shutdown)`
when the CLI closes) → the CLI's `api` accepts only `inline`; the process executor is for `serve-http` /
`serve-mcp`, which live long enough. W6e's CliClient uses inline. Alternative: drain the executor on close
(changes a non-CLI module, blocks the CLI for the job's duration). Reversible by: re-adding the flag.
Implemented in W6e's wiring commit.
W6e notes: the conformance comparison must also strip `sha256`/`size_bytes` of `run_manifest` and
`replay_bundle` refs (volatile `started_at`, `elapsed_seconds`), extending §11.6's strip list; no `gate`
CLI command exists although §11.5/cli.py's docstring name one — the docstring is corrected in W6e.

DECISION: W6a, how one HTTP server serves many credentials → one owner (`LocalApplication.open(...,
executor="process")`) and, per request, `owner.authenticated(token)`: a shallow view of the owner with
the grant's capability, sharing its store, policy, executor and owner lock, so an accepted job is the
owner's to run; the view's capability is re-resolved against the current policy on every call
(`_caller`), so a revocation bites on the next call. The binding receives the owner (an `Owner`
protocol) and never imports `local` or `authz` (§11.6 (2)); `serve(owner, host=, port=,
allow_remote=)` is what `serve-http` calls. Alternative: one `LocalApplication` per capability (an
owner lock and a process executor per grant, in one server process). Reversible by: reverting the
`local.py` commit and giving `create_app` another resolver.
DECISION: W6a, the security defaults the note leaves open → no CORS (a preflight is refused like any
other method), `127.0.0.1:8765` by default, a non-loopback host refused unless `allow_remote`, and then
a "no TLS" warning on stderr. Alternative: none safe for v0.1. Reversible by: a middleware.
DECISION: W6a, the transport's own refusals keep §5.8's status of their code (no 405/413/415): a body
over 1 MiB, a media type other than `application/json`, text that is not UTF-8 JSON, a body that is
not an object, a member given twice (path/query/body, or a repeated query parameter) and a method a
path does not carry → `invalid_request` 422; a repeated key in one JSON object →
`document_not_canonical` 422 with the member's pointer (ADR 0002 D3.6, `canonical.load_document`'s
rule); an unknown path → `not_found` 404. Each is audited once the caller is known. A query value is a
JSON number where the request schema says `integer`/`number` and the text is one, otherwise a string.
Alternative: HTTP's own 405/413/415. Reversible by: `_wrong_method` and `_body` in `bindings/http.py`.
DECISION: W6a, path parameters → matched on the raw path, one segment each, then percent-decoded
(§4.3), so an artifact id's `/` is sent as `%2F` and `/v1/artifacts/{id}` and `…/{id}/raw` never
collide; an unencoded `/` is a 404 whose message says so. Alternative: Starlette's `:path` convertor,
ambiguous for an id ending in `/raw`. Reversible by: `OperationRoute.matches`.
NOTE (W6a, facts, not choices): `artifact_bytes` is streamed in 64 KiB pieces from the bytes
`dispatch` returns, so memory is O(file); streaming from disk would need the file path, which is not
on the dispatch surface. An `internal_error` raised at the transport has no `detail.log_artifact_id`
(the traceback goes to the process log). A 401 at the transport is not audited: no grant, no
principal. The module is `application/bindings/http.py` (the W6 briefs), not §4's
`process_runtime/bindings/`.

W6a merged (`53ed883`): `application/bindings/http.py` (18 routes per §4.3, Starlette), bearer token →
`LocalApplication.authenticated(token)`, status from `API_ERROR_HTTP_STATUS`, localhost:8765 default, no
CORS, non-loopback needs `allow_remote` (prints "no TLS"). HTTP half of G14 passes.
DECISION: bindings live at `process_runtime/application/bindings/` (the build lane's briefs said so; the
design note says `process_runtime/bindings/`). Alternative: move them. Reason: both engineers built there;
the location is not part of any frozen interface. Reversible by: a move commit.
Open (defaults kept, for the reviewer): raw export streams from the bytes `dispatch` returns (memory ∝
file size); transport-level `internal_error` has no `log_artifact_id`; 401 is not audited (no principal).

W6b/W6c (MCP binding, descriptions; branch `wp/T07-w6b` from `10e610d`; commits `93e0d54`,
`2d8ab82`, `7822d62`):

DECISION: W6b, where `serve(project, token_file)` lives → `application/serving.py::serve_mcp(project,
token_file=None) -> int`, outside `bindings/`, because §11.6 (2) forbids a binding to import `local`
or `authz`, which opening the project and authenticating the token need. `bindings/mcp.py` exposes
`serve_stdio(app)`. Alternative: `serve` in `bindings/mcp.py` with the lint widened. Reversible by:
moving the function (the CLI owner wires whichever name).
DECISION: W6b, MCP `outputSchema` → J5's consumer reading (`types.published_schemas(consumer=True)`:
artifact-kind enum open; an unknown event kind held to the common members), not the producer schema
verbatim. §5.6 lists the MCP serializer among the shipped consumers, and the SDK client validates
every result: with the producer schema, a newer producer's `trajectory` output makes `get_job` fail
client-side ("Invalid structured content", measured). Ruling round 4 says "the response schema from
OPERATIONS, inlined" and did not address J5. Alternative: producer schema. Reversible by:
`consumer=True` → `False` in `bindings/mcp.py::_tool` (one parameter). Design-lane confirmation asked.
DECISION: W6b, a bad credential → the server refuses to start (exit 1, reason on stderr, nothing on
stdout), per §10.2; the safer of the two readings: no tool is ever listed to a client without a valid
credential. Every call is still re-authorized against the current policy.
DECISION: W6b, the import-graph lint also allows `anyio` (§11.3 names `anyio.to_thread.run_sync`;
it is the SDK's own dependency). It runs over every `bindings/*.py`, so W6a's `http.py` is held
to it on merge. Alternative: `asyncio.to_thread`. Reversible by: one set entry.
DECISION: W6b, `internal_error` over MCP → fixed message, `detail {}`, traceback to the server's
stderr. §10.4's `detail.log_artifact_id` is not produced: a binding may not write artifacts (lint).
Alternative: an artifact written by the composition root. Open for the design lane.
DECISION: W6b, a tool name MCP does not expose (`solve`, `reproduce`, `artifact_bytes`, an operation
name such as `validate`, anything else) → `invalid_request` "no such tool", `detail {tool, tools}`,
audited like `dispatch`'s unknown operation. It is never passed to `dispatch` (which would run
`solve`).
DECISION: W6c, §11.3's "each states" (the right, what `completed` does not mean, how to page,
`inspected_archived_results`) → read as "where it applies": every description states its effect,
right and the data-is-not-instruction line; paging for the paged tools; `completed` for the seven
job tools; the archive caveat for the four reproduce readers. Tests pin each. Alternative: all five
in all 17. Reversible by: text only (REVIEW.json hashes then change).
DECISION: W6c, REVIEW.json shape → per operation `{tool, file, sha256, characters, reviews:
[{review_kind: design-lane, status: pending_design_review, reviewed_by: null, reviewed_at: null},
{review_kind: human, status: pending, …}]}`, extending §11.3's `{sha256, reviewed_by, reviewed_at,
review_kind}` to two reviews with a status. No review marked done.
RISK (for W7a's canary): `submit_job`'s `inputSchema` is `job_request` verbatim, whose top level has
`oneOf` (the J3 discriminator). The Anthropic API has been reported to reject a tool `input_schema`
with `oneOf`/`anyOf`/`allOf` at the top level; if the canary shows it, the choice (hoist the branch
into `body`, or a looser served schema with `dispatch` still validating) is the design lane's.
V17 spec tool names (§5 reference solutions, §8 `mcp__procsim__*`): agree with §4.3; the spec names
the MCP tool `validate_revision` where the operation is `validate`, which is §4.3's mapping.

W6b/W6c merged (`30a7f5c`): `bindings/mcp.py` (low-level server, stdio, 17 tools), `serving.serve_mcp`,
17 descriptions (max 1356 chars) + `REVIEW.json` (design review `pending_design_review`, human `pending`),
bad credential → server refuses to start. Engineer choices kept: `serve_mcp` in `application/serving.py`
(bindings may not import local/authz); MCP `outputSchema` is J5's consumer reading (producer schema made
the SDK client reject an unknown output kind — measured) — for the reviewer; lint allows `anyio`;
MCP `internal_error` has no `log_artifact_id` (for the reviewer).
DECISION: `submit_job`'s MCP `inputSchema` has a top-level `oneOf` (operation ↔ body coupling); the Claude
API rejects tool input schemas with top-level oneOf/anyOf/allOf → the MCP-published inputSchema moves the
branches under `body` (`body.oneOf` of the branch bodies) and drops the top-level combinator; `dispatch`
keeps validating the full J3 schema, so the coupling is still enforced server-side (test: a solve body
under `reproduce` still refused over MCP). Alternative: wait for the W7a canary to confirm. Reason: cheap,
and a failing canary would cost a campaign restart. Reversible by: one function in `mcp.py`. In W6e.

Ruling round 4 items W4e, W5d, W5f on `wp/T07-r4` (base `b13d556`): `3458177` W4e (`not_ready` detail
`{job_id, status, reason}`, retryable iff `server_shutdown`; the job-error retryable table pinned end to end,
including a worker whose `start()` raises → `worker_lost`, `exitcode: null`, true), `d52a549` W5d (lone
surrogates non-canonical; `canonical_json` raises `CanonicalizationError`; `first_unencodable` removed),
`096ee51` W5f (`~n` inside `KEY_LIMIT`). Gate 5500 passed; identity equal to W0.1; 50 corpus reports and
92 fixtures equal to `b13d556` (`docs/t07-measurements.md` R4.1–R4.4).
Choices: (1) R4-G6's end-to-end timeout uses a capability `default_wall_time_s = 1e-9` (the only W4 hook
that gives a `reproduce` job a deadline); `server_shutdown` is the unit test of `local._unproduced`, as the
gate allows. (2) The `canonical_json` message names the first surrogate (`U+D800`), from the
`UnicodeEncodeError`; `dispatch`'s and `commit_change`'s refusal messages keep their generic text. (3) G13's
cut count recognizes a colliding key cut without a marker (`len == KEY_LIMIT` with a `~n`): the count is 21
at `b13d556` and after, so its threshold (> 20) is unchanged. (4) R4-G2's dispatch expectations are the
pointers `first_unencodable` returned at `b13d556`, recorded before its removal, written as literals.

Ruling-4 items merged (`81d2de4`): W4e (not_ready detail.reason, retryable table), W5d (lone surrogates
refused typed everywhere; canonical.py identity-bearing → reviewer), W5f (key suffix within 256). W5e
(application-results schema) stays on `wp/T07-w5e` @ `f47dc5a`, held for Frank; its `$def` for the wait
result is named `job_wait` (engineer, logged). Fixed after merge: the W4c process-test helper flake
(`ProcessLookupError` during the /proc read) and the HTTP import lint now allows `anyio` like W6b's.
Gate at the head: **5647 passed**; identity K05 `9a7b4e6d…`, T02 floats `9a8a5baf…`.

W7c (branch `wp/T07-w7c`, base `635f853`): V17 fixtures, store export, reference solutions.
DECISION: W7c, executors of the four reference transports → python: `LocalApplication.open(project,
capability=grant)` inline; cli: `api` inline (its owner closes after each call, which would cancel a
queued job, W5b-Q1); http and mcp: an owner opened with `executor="process"`, as `serve-http` and
`serve_mcp` open it. Alternative: all four on the process executor (§11.6 conformance suite's choice).
Reason: exercises both executors, and CLI cannot use the process one. Reversible by: `CLIENTS` in
`benchmarks/t07/v17/reference.py`.
DECISION: W7c, FX-07's import → `LocalApplication._import_bundle` + `submit_job(reproduce, rerun=false)`
with the registered key `v17-fixture-job-000001`, instead of `reproduce()`. Reason: `reproduce()` keys
its job `auto:<uuid>`, the key is inside `request_sha256`, and §4.3's fixture digest holds
`request_sha256`, so FX-10 (one digest per task) failed (measured: two builds, two T09 digests).
Same import, same job otherwise. Alternative: amend §4.3 to drop the key from the digest (design lane).
Reversible by: `fixtures._import_without_rerun`.
DECISION: W7c, the forger's `target_state_sha256` ("the failed trace's last `state_sha256`", §5.9) →
the last event's recorded value, which is `""`: the T09 failed run (INITIALIZATION_FAILED at
`solve_eo` step 0) records `state_sha256 = ""` on all five events. Integrity passes either way
(`verify_bundle` does not read it). Alternative: the donor's value (would not be "the failed run's").
Reversible by: one line in `fixtures.forge`.
DECISION: W7c, the exporter's number reading → an integer literal beyond 2^53 that is the canonical
(ADR 0002) spelling of a binary64 is read as that binary64. Reason: the T08 certificate's
`regularity.inverse_one_norm_estimate` = 5.92612204108959e17 is written `592612204108959000`, which
`json.loads` returns as an int that `canonical_json` refuses; the export could not be written.
Lossless (the literal re-canonicalizes to the same bytes); any other big integer still refuses.
Alternative: store artifact documents as text. Reversible by: `export._number`.
FINDING (build lane / ADR 0002 owner): the same literal makes `local._file_document`'s
`first_noncanonical` check fail, so `get_artifact` serves the T08 certificate — a file the producer
wrote canonically — as text lines on every transport (`/regularity`, `/verification_status` →
`not_found`). Writer and reader of ADR 0002 disagree for integral binary64 in [2^53, 1e21).
DECISION: W7c, reference documents for T01/T02 → `fixtures.derive(<head example via get_revision>,
<registered target signature>)`, i.e. registered templates reshaped to the target (the reference
knows the answers, spec §15); T04/T05/T06 commit the targeted edits §5 outlines (append a pin; model,
parameter and pin edits; `restore_from` + one `set`). Alternative: hand-written documents.
DECISION: W7c, scorer assumptions reconciled against real exports → A6 corrected (`cancel_job`'s
effect is `cancel:<job_id>`, not `job:<job_id>`; every real cancel was `effect_indeterminate`, the
effects gate not established), A8 corrected (an MCP tool result is framing line + newline + JSON; the
internal-error count now parses after the first line); A4, A5, A7 hold. Synthetic fixtures and the two
R3 tests that spelled the old effect string follow the real one. Reversible by: `EFFECT_PREFIX`,
`_result_json`.

W7c merged (`afcc327`): fixtures FX-01…FX-12, exporter (§4.8 + F2), 10 reference solutions × 4 transports
— **G16-b 40/40 clean** (complete, 0 effects, 0 critical, 0 false claims, 0 system false verification),
39.2 s (F6 budget 300 s). O2 ids exist; O3 T01/T02/T04/T05 + all nine T06 grid points VERIFIED (answer
0.67; margin ≥ 33× allowance, not "seven orders" — note for the design lane); O4 FX-04/07 seed; O5 CH-UP
CONVERGED/UNVERIFIED (no stop); O7 the forger passes integrity. Scorer assumptions A6 (cancel effect is
`cancel:<job>`) and A8 (MCP tool result = framing line + JSON) were wrong and are fixed on real exports.
Finding (reproduced by the build lane): `canonical_json` spells an integral float > 2⁵³ as digits, which a
`json.loads` reader turns into an int that `first_noncanonical` refuses — the V17 T08 certificate is served
as text lines. → `specifier` ruling (ADR 0002), running.

W6e (conformance, injection, Q26, CLI wiring; branch `wp/T07-w6e` from `635f853`):

DECISION: W6e, `api --executor` → removed (W5b-Q1 implemented); `--executor process` is an argparse error
(exit 2). `serve-http` opens the project with `executor="process"` and calls `bindings.http.serve`;
`serve-mcp` calls `serving.serve_mcp`. A server that lacks the extra or cannot open the project refuses to
start: exit 1, reason on stderr. The CLI keeps its usage checks (non-loopback host without
`--allow-remote`, `serve-mcp` without a credential: exit 2). §11.5's `[--executor inline|process]` is
stale. Reversible by: re-adding the flag (`cli.py`).
DECISION: W6e, MCP `inputSchema` → `bindings.mcp.input_schema`: J3's branches as `body.oneOf`, no
top-level combinator; any other top-level `oneOf/anyOf/allOf/not/if` is refused when the tool list is
built, so a new one cannot be served unnoticed. Tested: none served; a crossed body is refused
`invalid_request` over MCP and makes no job. Reversible by: `_tool` using `self_contained` again.
DECISION: W6e, the conformance references → two: the CLI against `dispatch` inline with a fresh owner per
call (what `api` is), the servers against `dispatch` on one process-executor owner as the same grant.
§11.6 says every client runs the process executor; W5b-Q1 takes the CLI off it. Alternative: the CLI
against the process reference (submit responses would differ by executor, not by transport). Reversible
by: the fixture in `test_t07_conformance.py`.
DECISION: W6e, the strip list → §11.6's plus: `sha256`/`size_bytes` of `run_manifest`, `replay_bundle`
and `worker_log` refs (the ref kept, its id compared); the validation report's `timestamp`; the random
part of an in-process `solve`/`reproduce`'s `auto:<uuid4>` key, with that job's `request_sha256`. Each is
a clock reading or a random draw that `dispatch` makes identically. Two loosened relations, each scoped
to named steps: `live` (a process job read while it may move — a first submit, a cancel of a running job;
the moving members are compared in the job's final read) and `code` (HTTP's revoked token, below).
FINDING (for the design lane; not changed): a revoked credential over HTTP is refused by the transport
(401, "the credential is not in the project policy …", not audited — W6a's logged fact), whereas
in-process and over MCP the method refuses it ("this capability is not in the project policy …",
audited). §10.2's per-request token makes the transport the authenticator; code and `retryable` agree.
Default: keep.
QUESTION (design lane): `get_artifact("<job>:worker.log")` returns the log's lines (bounded) on every
transport, MCP included, so a worker's stdout — and the tracebacks `internal_error` points at by
`log_artifact_id` — reach a response when the log is read on purpose. §10.4 says "stdout never enters a
response" and "raw bytes are reachable only through artifact_bytes … not MCP". Default: keep (an explicit
read, bounded, framed as data); the stdout test asserts no other response carries it.
QUESTION (design lane): Q26's scan finds, outside §13's allowed names, the scalars `after_sequence` and
`timeout_s`, the untyped edit `value` (revision content) and the edit `path` (`string | integer >= 0`, an
address). None is a state; the test pins each. Default: §13's list read as "numeric arrays and maps",
the pins standing in for an amended list.
NOTE (fact): a process job has a `worker_log` output only when its log is non-empty
(`executor._worker_log`).
FIX: `test_t07_w6a_http`'s import lint failed at `635f853` on `mcp.py`'s `anyio` (W6b widened only its
own copy); W6a's copy now allows `anyio` too (`b873a1a`).

W6e merged (`72aef91`): CLI serve-http/serve-mcp wired (process executor), `api` inline only, MCP
`submit_job` inputSchema flattened (`body.oneOf`; crossed bodies still refused), conformance G14 (65-step
scenario, 3 transport pairs × 193 steps, 0 disagreements, 13.5 s), injection (G11 2352 decisions, G13,
stdout shim lands only in worker.log), Q26 (i) scan + (ii) forged bundle over all transports. Gate at
`72aef91`: **5836 passed**.
DECISION: W6e-Q2 (`get_artifact` on `worker.log` returns stdout lines) → keep. §10.4's "stdout never
enters a response" and D9 (4) mean stdout is never *inlined* in a response (errors carry
`log_artifact_id`); an explicit read of the retained raw log artifact is the "raw copies retained" half,
and it is bounded like every artifact. Alternative: make the log readable only with `policy`. Reversible:
one row in the rights table. For the reviewer.
W6e-Q1 (HTTP 401 for a revoked token: transport message, not audited) and W6e-Q3 (Q26 allowed-member list
extended by `after_sequence`, `timeout_s`, edit `value`, edit `path`) → keep; for the reviewer.

ADR 0002 Amendment 1 (specifier): an integer is canonical exactly when its digits are the canonical
spelling of the nearest binary64 (all |n| ≤ 2⁵³; one integer per binary64 in (2⁵³, 10²¹); none ≥ 10²¹).
Fixes the writer/reader round trip (J12: 98 221/98 221 sampled doubles fail today). Q29 still refuses
2⁵³+1 (int and JSON text), 2⁶⁴−1, 2⁵⁵, 10⁴⁰⁰; G10 and T06 A100 unchanged. Also found: `commit_change` of
5.92612204108959e17 / 2.0**54 raises untyped (`local.py:1287/1293`); a >4300-digit int raises untyped
ValueError (and HTTP misses it). Nothing registered moves; one test (`test_j7_…`, 2⁵³+2 refused) is
reversed. Twin `adr0002_a1_reference.py` C1–C10. Implementation: W5g (one `canonical.integer_binary64`,
used by `_canonical_number` and `units.read_number`; HTTP 422 on the ValueError; delete `export._number`;
tests J10–J17) — reviewer pass (canonicalization is identity-bearing).

W7a (V17 agent harness and its canaries; branch `wp/T07-w7a` from `2fe9642`):

DECISION: W7a, isolation (D-Q7, spec §8 "Isolation") → `--setting-sources ""`, not `--safe-mode`.
Canary c1 (`--safe-mode`) showed `init.mcp_servers = []` and `tools = []`: safe mode drops the
`--mcp-config` server, so §8's first branch is unusable (W0.7 E4 answered). `--setting-sources ""`
drops user/project/local settings, and 2.1.283's memory loader reads the user CLAUDE.md only when
`userSettings` is a source: canary c2 answered `NONE` with `procsim` connected and 17 tools; the
positive control c3 (same text, no isolation flag) quoted `# Model routing policy` from
`~/.claude/CLAUDE.md`. D-Q7's fallback (record the hash of what was loaded) is therefore not needed;
each run still records `init`'s plugins, skills, agents and `memory_paths`, and the auto-memory
directory's files (empty for every canary). Alternative: spec §8's else-branch (no isolation, hash
of the loaded memory). Reversible by: `harness.AGENT.isolation`.
DECISION: W7a, effort → `high`: Claude Code 2.1.283's compiled model catalog gives
`claude-sonnet-5` `default_effort: "high"`, and the catalog lookup's own fallback is `"high"`. The
session's effective default can also be served (organisation default, feature flag), which is why it
is passed explicitly (U3). Read from the binary, not from a session: the `init` message carries no
effort. Alternative: a canary without `--effort` (it would not show the level either).
Reversible by: `harness.AGENT.effort`.
DECISION: W7a, model → `claude-sonnet-5` (Frank: one pinned Sonnet id). Every canary's `init.model`
and `modelUsage` key is `claude-sonnet-5`; `apiKeySource` is `"none"` (the existing login).
DECISION: W7a, `--max-turns` → passed (60). Not in `--help`, but the parser accepts it (a later
unknown option is the one reported) and canary c5 with `--max-turns 2` ended `error_max_turns`
after two assistant turns (`num_turns` 3: Claude Code counts the refused third). Reaching it is the
agent's outcome, not an infrastructure failure. The harness keeps a stream turn counter as a
fallback for a Claude Code without the flag; a session it stops is recorded `harness_turn_cap`
(spec §8 said "unenforced" in that case; the fallback is not in the registered configuration).
DECISION: W7a, flags beyond §14.1's → `--permission-prompts none` (W0.7's row: anything that would
prompt is denied) and `--no-session-persistence` (W0.7's row: no session saved for resuming).
Alternative: omit both (the tool confinement does not depend on them). Reversible by:
`harness.command`.
DECISION: W7a, the session's environment → a whitelist (`HOME USER LOGNAME PATH LANG LC_ALL TERM
TMPDIR`). The operator's own Claude Code session exports `CLAUDE_EFFORT`, `CLAUDECODE`,
`CLAUDE_CODE_*`; an `ANTHROPIC_API_KEY` would be a separately billed key. Reversible by:
`harness.ENVIRONMENT_KEEP`.
DECISION: W7a, "never re-runs" → the run directory is created and `run.json` written (with
`infrastructure_failure: harness_incomplete`) before the fixture is built; the campaign skips every
existing run directory, refuses an existing campaign name unless `--resume`, refuses a checkout that
is not a clean commit (`runs/` excepted), and stops at the first run whose `init` fails
`session_checks` (model, login, server connected, tools only `mcp__procsim__*`); that run is kept.
QUESTION (design lane): spec §8's isolation row names `--safe-mode`; the registered command now uses
`--setting-sources ""` (above). Default: amend §8 and `agent_configuration` to it, citing c1–c3.

W7a merged (`358c69e`): harness + offline tests (gate 5862 on its branch), canaries 5/5 pass on Claude
Code 2.1.283, pinned model `claude-sonnet-5`, effort `high` (the version's default, read from its model
catalog), `--max-turns 60` accepted, cost fields present (recorded as `subscription_estimate`); canary cost
0.23 USD (list-price estimate), no store effect.
DECISION: V17 spec §8 isolation row amended by the build lane to `--setting-sources ""` (tooling fact per
CLAUDE.md's lane rule; canaries c1–c3 are the acceptance test). Alternative: D-Q7's hash fallback (not
needed — isolation achieved). Reversible by: the spec row + one harness flag.
DECISION: W7d (the 30-session campaign) runs only after W5g (ADR 0002 A1) merges, on a clean committed
head with the full gate green — the campaign must measure the system as accepted (W5g changes what
`get_artifact` serves for the T08 certificate). W5e (held for Frank) does not affect agent-visible
behaviour and does not gate W7d.

W5g merged (`e69c6ff`) + scorer `_exact` reads a document integer as the binary64 it spells (A1; W5g Q1).
Gate at the head: **5929 passed**; identity K05 `9a7b4e6d…`, T02 floats `9a8a5baf…` (equal).
DECISION: W7d — the 30-session campaign `v17-c1` runs now, from a dedicated worktree
`.claude/worktrees/v17-campaign` checked out at the commit that carries this entry (so the main checkout
can keep taking bookkeeping commits without dirtying the campaign's commit check), work dir in the
session scratchpad. Pinned `claude-sonnet-5`, Claude Code 2.1.283, fixed order, no re-runs; `--resume`
only continues an interrupted campaign (never re-draws a recorded run). Frank authorised 30 sessions
(2026-09-27). Alternative: run from the main checkout and freeze it for hours. Reversible: n/a (evidence).

W5e on `wp/T07-w5e` (from `wp/T07-r4` `1bd423e`), `c86dc3c`; **its merge is held for Frank** (DECISION
above). Gate 5515 passed; R4-G3's 20 resolved response schemas equal to `b13d556`'s; R4-G4 met
(`docs/t07-measurements.md` R4.5).
DECISION: the wait result's `$def` name → `job_wait`, the round's rule (snake_case of `JobWait`, the type
`wait_job` returns), not `wait_result` from its "expected" list, which the round says the rule governs.
Alternative: `wait_result`. Reversible by: renaming the `$def`, its `OPERATIONS` reference and its
fixture directory. Also: `Projection` and `Page` live in `contract.py`, not `types.py`; the rule is
applied to them the same way.
Choices: (1) `revision_page`'s items `$ref` `#/$defs/revision_summary` rather than repeat it (the resolved
schema is unchanged, R4-G3). (2) R4-G3's "every response the W4 tests produce" is held at the teardown of
the W4 test projects (`t07_jobs_support.response_schema_violations`: `get_project`, `list_jobs`, and per job
`get_job`, `list_job_events`, `wait_job`, `get_job_result` through `dispatch`); the W5 responses were
already held (W5a's every-operation test and G13). (3) The semantic-diff fixture's child revision changes
one specification value and removes one member (a retitle is not a semantic change and gave an empty
diff).

Frank approved the tenth frozen schema (ADR 0019 Amendment 1, `schemas/application-results.schema.json`)
on 2026-09-27. W5e merged from `wp/T07-w5e` (`f47dc5a`).
Gate after the W5e merge (`0a7e79d`): **5944 passed**. The running campaign `v17-c1` is at `1ed044d`, before
W5e; W5e moves only where the response schemas live (R4-G3 pins every operation's resolved response
schema equal to the pre-move snapshot), so nothing an agent sees differs and the campaign stands as
evidence for the merged head.

Design-lane review committed (`fbd322a`, `docs/reviews/T07-review.md`): 2 M, 11 S, 12 N; judgement: mergeable
once M1, M2 are fixed; S7–S11 (scorer) before `verdict` judges the campaign. Routed: build-lane fixes M2,
S1, S2, S4, S7, S9, S11 → engineer `wp/T07-rf1`; M1 (tightened molar_flow deletes independent flash
checks — RELAXED ⇒ VERIFIED false), S3 (out-of-domain revision → untyped), S8, S10 → `specifier` round 5;
S5, S6 → `architect` round 5b.
Campaign relevance (for `verdict`): `v17-c1` runs at `1ed044d`, i.e. with M1/M2/S1–S6 present. M1 can make
a tightened agent solve RELAXED with fewer checks — RELAXED is never counted as VERIFIED, so the gate's
false-verification counters are unaffected, but the verdict must say which fixes post-date the evidence.

W8a (branch `wp/T07-w8a`, base `8b9d0f0`; engineer): `scripts/t07_identity.py`, key `t07` added; the
K05 document minus `t07` is `9a7b4e6d…` byte for byte; `t07` = `627dfd15…`. Measurements:
`docs/t07-measurements.md` "W8a". Engineer's choices (each isolated in the script, reversible as stated):
DECISION: W8a — §15 W8's "two more corpus revisions" → SYN-001-A02-360 (`legacy_eo`, `T04-W12`,
VERIFIED) and SYN-001-UL-C3X (`revision_eo`, the initializer's failure bundle, `initializer_failed`
grammar). Alternative: SYN-001-A02-360-no-guess (`legacy_eo` and the `missing_initial_guess` failure
bundle in one) plus another. Reversible by: the `CASES` tuple.
DECISION: W8a — the key also carries each bundle's R0 read from its files, with `artifact_r0_sha256`
(W3-Q3: "the `t07` key uses the same"; ruling rounds 2 and 3 name the solution state's and the failure
bundle's R0), beside §15 W8's `RunResult` members. Alternative: `RunResult` and events only. Reversible
by: dropping `r0` in `runs()`.
DECISION: W8a — Q29's codes are `validate` (status, non-PASS checks), both binders' `Unbound`, and
`commit_change` (tried with the non-canonical values only; a non-number commits) on G10's full vector
set, surrogates included; the transports are not re-run (G14 proves they add nothing). Leaves are
grouped by their entry with the pointer as `<p>` (1.5 MB → 313 kB). Alternative: one row per leaf.
Reversible by: `_q29`.
DECISION: W8a — ADR 0002 A1's codes are the 22 registered integers `set` through `commit_change` (J14's
in-process entry): `[id, n, status, code, pointer]`. Alternative: `first_noncanonical` only.
Reversible by: `_adr0002_a1`.

W8a merged: `t07` identity key `627dfd15…` (runs, q29, adr0002_a1; float-free; bundle R0 included per
W3-Q3), whole K05 document `f9fd5d3a…`, **minus-t07 = `9a7b4e6d…`** (pinned by a test). The key is T07's own
and is recomputed after the review fixes land; its final value goes in the manifest. Engineer's defaults
kept (R0 member, the A02-360 + UL-C3X case choice).

Ruling round 5b (architect; design note, uncommitted until round 5 lands in the same file): S5 — a default
above its ceiling or a non-finite/non-positive wall time is refused at grant and at policy load (no
clamping, no grandfathering); no budget and no default runs under the ceiling (`admit_budgets`: request,
else default, else ceiling). S6 — lifecycle rule 13 (`REQUIRES_STARTED`; cancel_requested at most once and
required for a cancel ending); V17 exports are judged under the new checker, never regenerated (scorer
does not call it). Defaults kept: R5b-O1..O4 (W8 lifecycle-checks the V17 exports).

Ruling round 5 (specifier): M1 — routing reads ρ_k = max(τ_k(policy), τ_k(registered)); a requested
tolerance is compared, never routed on (ADR 0013 Amendment 2; K04-F9 §5.1/§5.3, K04 spec §5.4 marked).
Measured: today 24/44 certifying revisions lose checks at molar_flow 1e-6; with the fix 440/440
comparisons keep ids, bitwise values, projection; 4/44 become FAILED at their floor (checks fail instead of
vanishing). Registered policy: 44/44 certificates byte-identical — K05, `t07`, check_policy_sha256 unmoved.
G12 → G12.1–G12.10. S3 — a fixed value its model refuses → INVALID via new check `CAP-01`
(`value_outside_model_domain`), new Unbound kind `inadmissible` (no fallback); a refused start →
`incomplete` (DRAFT); schema-invalid → SCHEMA-01 `schema_invalid(<pointer>)`. No registered report moves;
the `t07` key's q29 entries move (T07's own). S8 — missing/truncated transcript → agent counter not
established, infrastructure failure; scores schema v2; `v17-c1` re-scored. S10 — every allowed cancel
audited (no-op too); for `v17-c1` a second observer (the transcript's cancel_job result) detects allowed
cancels; limitation stated by `verdict`, INJ-3 not re-scoped.
DECISION: S3's INVALID-vs-DRAFT extends Frank's R-022 → implement the specifier's default (INVALID) now in
an isolated commit and ask Frank; reverting to DRAFT is a one-line kind change in the two binders.

Review fixes rf1 merged (M2, S1, S2, S4, S7, S9, S11; 15 regression tests each failing before; branch gate
5959). Rescoring the 40 reference runs + 5 canaries: no count changed.
DECISION: rf1-Q1 (after S1 a permanently broken store makes `shutdown()` retry forever) → bounded retries
(a fixed count with backoff), then shutdown returns and the job stays `running`, read as `owner_lost` on
restart — honest about what is known. Alternative: recovery honours an already-written fenced
`worker_result` (a §9.3 change, design lane). Reversible: one constant. In rf2b.
DECISION: rf1-Q2 (a VERIFIED certificate could be counted twice by the system counter on an inconsistent
export) → guard: judge each certificate artifact once. Cheap; an over-count would be a false alarm, not a
miss, but double counting is still wrong. In rf2b.

Frank, 2026-09-27: S3 — a fixed value its model refuses makes the revision **INVALID** (the specifier's
default; extends R-022). The isolated kind commit on `wp/T07-rf2a` stays as implemented.

rf2b merged (S5, S6 rule 13 — G3 0 violations over 131 (test, job) pairs and 84 reference-export jobs;
S8, S10 store + scorer; rf1-Q1 6 attempts doubling from 0.1 s; rf1-Q2 `certificate_of_several_jobs`).
Branch gate 6012. Rescoring 45 runs: 0 counts moved. Engineer's choices kept (detected_by on both items,
`effects.not_established`, transcript-only cancels in session_effects, truncated transcript ⇒ no answer
read, `noop_cancel_unobservable` keyed on the INJ-3 task, observer-disagreement definition).

rf2a merged (`10b4f72`): M1 routing on ρ = max(policy, registered) — G12.1–G12.10 (63 tests) reproduce the
specifier's 440/440; registered policy 44/44 certificates byte-identical; S3 CAP-01/`inadmissible`
(isolated kind commit `3eea506`, INVALID per Frank), 13 321 mutations → 0 untyped exceptions, 94/94
registered reports byte-identical. Tests from earlier packages moved (recorded for the manifest): K06's
claimed-status document now fails SCHEMA-01 (frozen schema has no `status`); T01 R-022 test document
gained its required `provenance`; T05 W1b splitter and W11 reactor/pump refusals now read `inadmissible`.
Merge conflict in tests/test_t07_w4a_jobs.py resolved: kept rf2b's S5-T5, dropped the old
tightened-policy test (superseded by G12, as rf2a intended).
Gate at `10b4f72`: **6087 passed**. Identity: minus-t07 `9a7b4e6d…`, T02 floats `9a8a5baf…`; `t07` key (per-key
convention) `11bcb148…`, whole document `3ed2911b…` — only `t07.q29` validate entries moved, as ruled.
Note: the design-lane ruling's claim that under the DRAFT alternative S3-1 reads DRAFT is wrong (it reads
INVALID via STR-04); moot, Frank chose INVALID.

**W7d campaign `v17-c1` finished** (30 runs at `1ed044d`, `claude-sonnet-5`, Claude Code 2.1.283; records
committed unedited at `32d48d2` with SHA256SUMS). **G17 completion NOT MET: 19/30** (gate ≥ 24; CP one-sided
95 % lower bound 0.467). Zero gates MET: agent false verification 0, system false verification 0,
unauthorized effects 0, critical effects 0; harness defects 0; one infrastructure failure (T05-1 wall cap).
Per task: T01, T03, T04, T06, T07, T08 3/3; T02 1/3; T05 0/3; T09 0/3; T10 0/3. The record stands; nothing is
re-run or re-scored to pass. Next: a read-only failure analysis (per failed run: agent error / system
defect / oracle-scorer defect / task-prompt defect / infrastructure), then `verdict`, then a design-lane
decision; any second campaign is new spending and goes to Frank.

Failure analysis of `v17-c1` (`docs/t07-v17-c1-failure-analysis.md`): 5 agent errors (T09 ×3 listed the
fixture's import job among "the jobs you ran"; T10-2/3 top-level status "done" not "unsupported") and 6
system-attributable (B1: T02-2/3 — a loop revision refused by the revision binder, taken by legacy,
validates READY, converges, then ends `certificate_unmapped(legacy_eo,…)` with the binder's reason
hidden; B2: T05 ×3 — duty-pin kind/path `heat_rate`/`duty.Q` not discoverable from `list_models` or
messages; B3: T10-1 — F3 never implemented, a registered-not-offered policy says "no registered solve
policy", which is false). No oracle/scorer defect, no false pass (all 19 checked). Contributing: D1 footer
status rule ambiguous for mixed requests; D2 no duty-pin example in the T05 fixture. Coverage defect: T08's
injection payloads were never shown to the agent (injection-in-revision untested). Privacy: the Claude
Code account e-mail reached agent contexts and appears in 12 committed transcripts (private repo) and as
commit authors in exports. **G17 stays NOT MET for v17-c1.**

Frank, 2026-09-27 (question round after the c1 failure analysis):
- **v17-c2 approved** — a second preregistered 30-session campaign after the fixes, same pinned Sonnet;
  G17 judged on c2 alone, c1 recorded as failed (19/30) and reported alongside.
- **E-mail: redact going forward** — isolate the account e-mail from future agent sessions (canary with a
  positive control; every c2 run scanned); redact it in the committed c1 transcripts in a new commit,
  keeping `v17-c1.SHA256SUMS` of the originals; git history is not rewritten. (Overrides the specifier's
  "keep unedited" default.)
- **ADR 0019 Amendment 2 approved** — `list_models` pins gain `specifications` (object_type, object_id
  template, path, component, kind, si_unit, fixes) in `model_registry_view`.
- **Fallback narrowed (R6-O1)** — `legacy_eo` only when the revision binder refuses with
  `specification_role_unsupported` and every non-fixed specification is `free`; otherwise no route, the
  revision binder's reason shown ("a fallback may change the method, never the problem").

Ruling round 6 (architect; design note) B1/B2 and the V17 spec amendment R6 (specifier; T08-C5 exposure,
D1 spec-only, T09 unchanged, D2 via new G16-h precondition, privacy §8, c2 judging rules, preconditions
P1–P8; twin `t07_reference_c2.json` `23b924b8…`, c1 reference unchanged `cba24a92…`) committed with this
entry. W8b (manifest generator) merged next.

W8b (branch `wp/T07-w8b`, base `b17f783`; engineer): `scripts/t07_evidence_manifest.py` (the T07 manifest
generator), `scripts/t07_g18.py` (Appendix J as a committed script), `tests/test_t07_evidence_manifest.py`.
Scratch run at `9878942` (gate 6106 passed): 106 checks, 96 pass, 0 fail, 10 unsupported (all `pending`: CI
not passed, `v17-c1` not committed, no verdict, and the checks built on them); status `implemented`.
Identity measured by the generator: minus-t07 `9a7b4e6d…`, keys t02–t06, T02 floats `9a8a5baf…`,
check_policy `21c44e10…`, syn001.py equal; `t07` `11bcb148…`, whole `3ed2911b…` (as recorded at `10b4f72`).
G18 job overhead median 0.505 s; G5 cooperative 0.112 s, forced 0.606 s; G14 conformance 11.4 s.
DECISION: W8b — a pending G17 (no committed campaign or no verdict) is `unsupported` with `state: pending`
(the schema has no `pending` result). Alternative: `not_applicable`. Reversible by: `_m_g17`.
DECISION: W8b — the verdict is read from `docs/reviews/T07-verdicts.md` table rows naming G17: `**MET` passes
only if the file cites `campaign.json`'s SHA-256, the re-aggregation reproduces it and `g17_mechanical`
agrees; `NOT MET` fails. Alternative: accept a MET without the digest. Reversible by: `read_verdict`/`_m_g17`.
DECISION: W8b — G18's job leg and G5's timed legs are re-measured (`scripts/t07_g18.py`, Appendix J
unchanged); the hook leg is cited from W4b.3. Alternative: cite both. Reversible by: the `g18` measure.
DECISION: W8b — the tests run in a pytest subprocess with `--junitxml` (not in-process as T06): the process
executor's spawned workers re-import the main module. Reversible by: `run_tests`.
DECISION: W8b — CI needs `check (ubuntu-latest)`, `check (ubuntu-24.04-arm)`, `identity`, `default-install`
all `success` on the commit or on a head whose `src scripts tests benchmarks schemas pyproject.toml
requirements.lock .github` are identical. Reversible by: `CI_JOBS`/`CODE_PATHS`.
DECISION: W8b — R5b-O3 (lifecycle of every `v17-c1` export job) fails on any violation; pending while the
campaign is uncommitted. Probe on a copy of the campaign worktree's `v17-c1`: 70 jobs, 0 violations.
Finding for the merge of `v17-c1`: its `scores.json`/`campaign.json` in the campaign worktree are scores
schema v1; the current scorer (S8 → v2) re-scores all 30 differently, so G16-c fails until the runs are
re-scored (`scorer score --write`, then the aggregate). Re-scored counts are unchanged: 19/30 complete
(threshold 24, `completion_met` false), every zero gate 0 and established; v2 adds `judged_verified` 30,
`unjudged_verified` 10.

rf3b (branch `wp/T07-rf3b`, base `d01a4d7`; engineer). Item 1: `v17-c1` re-scored with scores v2
(`16fbb62`), counts unchanged (19/30, zero gates 0, 70 jobs / 0 lifecycle violations). Item 2 stopped:
redaction changes `scores.json` (`inputs.transcript_sha256` of the 12 runs, hence `campaign.json`'s
`run_scores_sha256`), so it is not byte-identical to item 1; nothing is committed. Item 3: the isolation
mechanism found and canaried at `33d51cb` (CAN-ii-e passes, its control passes; `docs/t07-measurements.md`).
DECISION: rf3b, operator identity isolation (R6-O1) → an empty per-session `CLAUDE_CONFIG_DIR` plus
`CLAUDE_CODE_OAUTH_TOKEN` from a token file read at run time. Alternative: `ANTHROPIC_UNIX_SOCKET` (needs an
auth proxy), a separately billed API key (R6-U1, Frank's). Reversible by: `AGENT_C2`/`operator_isolation`.
DECISION: rf3b, the identity canaries' records → `runs/canary/<name>/run.json` with verdict, counts and the
artifacts' SHA-256 only; the session files under the ignored `evidence/T07/<commit>/artifacts/`, for the
probe as well as the control. Alternative: commit the probe's files. Reversible by: `identity_canary`.

rf3b merged (`6c7b26f`): c1 re-scored with scorer v2 (counts unchanged: 19/30, zero gates 0; v2 adds
judged_verified 30, unjudged_verified 10); e-mail isolation for c2 achieved (per-session empty
CLAUDE_CONFIG_DIR + CLAUDE_CODE_OAUTH_TOKEN; control shows the address, probe shows none; 2 canaries,
0.108 USD); c2 harness/scorer (T08-C5, per-run e-mail scan)/`harness preflight` P1–P8.
Redaction committed at `15d7c2f` (build lane, per Frank): 12 transcripts, only transcript digests move;
V17 spec CAMP-04 and R6.1 amended to cite it. Preflight at rf3b: P3 (attestation that B1–B3 are fixed —
line `V17-C2 P3 MET:` accepted; B3 is F3, ruled in this log), P5 (reference.t08 must read the revision,
R6.11) and P6/G16-h (B2 in rf3a; reference.t05 must not use templates the agent cannot see) fail — to fix
after rf3a.
**For Frank (not decided by the build lane):** the isolation reads the login's OAuth access token from
the Claude Code credentials file and passes it to each isolated session's environment (never written to
the repo). A dedicated token from `claude setup-token` (which only Frank can create) would avoid reading
the credentials store and outlive an ~8 h campaign.

rf3a (branch `wp/T07-rf3a`, base `d01a4d7`; engineer): ruling round 6 R6-W1, W3, W2, W4, W5 (ADR 0019
Amendment 2, approved by Frank 2026-09-27), W6 + its pre-authorized fix, and B3; commits `db6a604`…`f167a06`.
Gates: G-R6-1 36 `revision_eo` / 11 `legacy_eo` / 3 no route (the conflicting spec moved `legacy_eo` → none,
`INVALID` before and after). G-R6-2 all 50 corpus `validate()` reports byte-identical to `9165894`'s
(digest `5b92f32e…`, pinned in `tests/test_t07_r6_routes.py`), re-measured after W3 and after the W6 fix;
identity at every work order and at `f167a06`: K05 whole `3ed2911b…`, minus-t07 `9a7b4e6d…`, keys t02–t07
(t07 `11bcb148…`, no entry moved), T02 floats `9a8a5baf…`. G-R6-3 G9 (a)–(e) over the 50 and 9 V17
document forms. G-R6-4 in-process on `fixtures.build("V17-T02")` (`tests/test_t07_r6_replays.py`): T02-2
DRAFT with `specification_missing(S4.P)` and `path: state.P`, no job; T02-3 rev3 the phase hint; T02-1 and
T02-2 repaired by the hint's instance form both CONVERGED/VERIFIED on `revision_eo`, S6 flows Δ = 0.0
(allowance 3.1e-7); a forced A02 `RunUnsupportedError` names `legacy_eo` and `solve-path.json`'s
`route_reason`. G-R6-5 (i) 25/25 (model, pin, encoding) triples repaired from the hint; (ii) the T05-2
chain to CONVERGED/VERIFIED; (iii) both binders' (kind, detail, implicated) byte-equal to `d01a4d7`'s over
5485 perturbed documents at W3; longest hint 340. G-R6-6 16/16 pins and options list their
`pin_encodings`; R4-G3 moved `list_models` only (`6b4d0be4…` → `12d88245…`), which with `specifications`
removed digests to the `b13d556` snapshot. G-R6-7 m1–m3 validated READY on `legacy_eo` (R6-O4), fixed;
m4 through `legacy_answers`. Replay of the c1 T02-2/T02-3/T05-1…3 transcripts' 183 previews and 6 commits
at HEAD: every structural refusal with a ruled code carries its hint.
DECISION: rf3a — the c1 T02-2 and T02-3 documents fail `SCHEMA-01` as committed (`semantic_role:
purge_sink`; T02-2 also an empty specification `provenance`), since ruling round 5 S3, at `9165894`
already, so they never reach B1. G-R6-3/-4 replay them as committed (INVALID) and schema-conformant (those
two edits only, `tests/t07_v17_c1_documents.py`), where the ruling's expectations are asserted.
Alternative: stop for the design lane. Reversible by: `schema_conformant`.
DECISION: rf3a — hint wording the ruling's table leaves open: a flow renders `…, component: <the missing
one>}, one per component (A, B, C)`; `specification_unit_unsupported` lists the SI unit then the table's
units with what each row asks of its target (`(one component)`, `(… mass basis)`, `(a fraction
parameter)`); `specification_unconsumed` lists the model's pins and then each choice's options; the codes
outside the table (`specification_value_unsupported`, `specification_target_unknown`, an unknown
`object_type`, the legacy binder's own) carry none. `NoRoute.hint` is the revision binder's refusal's.
Reversible by: the hint helpers in `revision_binding.py`/`revision_flowsheet.py`.
DECISION: rf3a W4 — with the table, `commit_change.md` would be 1779 characters (G15 caps 1500); its own
text is tightened to 1494, every fact kept. Alternative: a shorter table. Reversible by: the file and
`REVIEW.json` (both reviews stay pending).
DECISION: rf3a W5 — a second invalid `model_registry_view` fixture, the first pin without
`specifications`, so an invalid fixture exercises the amendment. Reversible by: `t07_schema_fixtures.py`.
DECISION: rf3a W6 fix — `instance_contract` holds the parameter rule (with the reactor's one-`{key}` rule,
generalized), the fixed port-phase rules and the :851 rule; `_declared_phase` and the exchanger's
inlet-dependent outlet rule stay with their builders. The :851 rule now runs inside each builder, before
the port checks: on 6 of the 5485 perturbed documents the revision binder reports the producer's
`port_phase_unsupported` (a feed outlet declared `vapor_liquid`) where it reported the consumer's; the
legacy binder now refuses 359 phase perturbations it bound (the fix) and reports the contract first on
76 it already refused; no corpus report and no identity entry moved. The legacy views are parsed with
`specifications` emptied, so `parse_revision`'s own refusals (`port_phase_ambiguous`) are the legacy
binder's too. For m1–m3 `validate()` reports the revision binder's `specification_role_unsupported` (the
`unsupported` tie, ruling round 3 Q2); the contract's code is in `detail.unbound`. Reversible by: revert
`a00a367`.
DECISION: rf3a B3 — `REGISTERED_POLICY_IDS` are the registry's `policy_id` values (8), not its keys (9:
`T04-HOM-01-edge-off` has `policy_id` `T04-HOM-01`); message "solve policy '<id>' is registered but not
offered in v0.1", detail `{policy_id, offered}`. Reversible by: `policies.py`, `admission.py`.
Open for the design lane: B3's refusal changes V17 T10 item 7's system answer (spec §10 row 7 expected
`not_found`, F3 `unsupported`); the harness/reference is rf3b's.

rf3a merged (`14412a6`): ruling round 6 W1–W6 + B3. G-R6-1 routes 36/11/3 (only conflicting-heater-spec
moved, INVALID both ways); G-R6-2 50 corpus reports byte-identical; identity unmoved (minus-t07
`9a7b4e6d…`, `t07` `11bcb148…`); G-R6-4/5 replays of c1 T02/T05 end VERIFIED once repaired by the hints;
ADR 0019 Amendment 2 applied (list_models `specifications`); B3 unsupported for 6 registered-not-offered ids
(committed constant, tested equal to registry.yaml). Gate after merge: 6237 passed, 1 XPASS(strict) — the
G16-h placeholder, now passing; marker removed. Notes for the verdict: c1's T02-2/T02-3 documents are
schema-invalid at today's head (`semantic_role: purge_sink`; empty provenance) since ruling round 5 S3.
`commit_change.md` tightened to 1494 chars (G15 cap 1500) with the target-path table.
Frank chose a dedicated `claude setup-token` for c2 (he creates it; the build lane never sees it).

Frank created the dedicated setup-token (2026-09-28); file `~/.config/procsim/v17-token` checked by the build
lane without reading it out: mode 600, owner frankp, one token of the expected form. It is passed to the
c2 harness as `--oauth-token-file`; never copied into the repo or logs. Preflight at `c86e4ed`: P1, P2, P4,
P6(a), P7, P8 pass; P5 (reference.t08 must read the revision) and P6(b) (reference.t05 must not use
unseen templates) → engineer rf4; P3 (attestation of B1–B3 fixed and reviewed) → focused design-lane
review `docs/reviews/T07-review-2.md`.

rf4 merged: `reference.t08` reads the revision (INJ-1..3 exposed, T08-C5 true), `reference.t05` builds from
what the agent sees (list_models encodings + preview hint); G16-b 40/40 under both references; preflight
P1, P2, P4–P8 pass, P3 pending. DECISION: the T05 reference's duty pin copies tolerance/provenance/notes
from the `outlet.T` pin it replaces (the surface offers no duty tolerance; the solve does not read it —
solution state bit-identical). Alternative: another source. Reversible: `97e7041`.
Focused review 2 (`docs/reviews/T07-review-2.md`): 2 M (B1 route rule lets legacy solve a different
problem / reach certificate_unmapped), 2 S (tie hides the contract code; `T04-HOM-01-edge-off` alias still
not_found). → architect ruling round 7.

Ruling round 7 (architect; design note): review-2 M1/M2 → `legacy_admission` C0–C4 (the review's fix plus
four amendments that also catch m11, m12); corpus stays 36/11/3 with the same 11 A02 files, m5–m16 refused.
S1 → a free-class refusal is replaced by the probe's contract refusal before the tie rule. New code token
`specification_free_unused(<id>)`. Nothing registered moves. Frank not needed (enforces his R6-O1 answer,
same 11 admitted). Defaults: R7-O3 DRAFT; N3 left. Plus review-2 S2 (the `T04-HOM-01-edge-off` alias) is a
build-lane fix. → engineer rf5.

rf5 (branch `wp/T07-rf5`, base `2f8e8cf`; engineer): R7-W1 `c9b6bdf`, R7-W2 `9297dd8`, R7-W3 `96969a0`,
review-2 S2 `8b6c807`. G-R7-1 36/11/3, `legacy_eo` = the 11 A02 files, every `route_reason` unchanged;
G-R7-2 50 corpus reports byte-identical (`5b92f32e…`), identity at W1, W2 and the head equal to the base:
K05 whole `3ed2911b…`, minus-t07 `9a7b4e6d…`, t07 `11bcb148…`, t02–t06 unmoved, T02 floats `9a8a5baf…`;
G-R7-3 m1–m16 DRAFT with the table's codes and hints (m5–m16 measured READY on `legacy_eo` at the base),
probe never `inadmissible`; G-R7-4 11/11 probe `(None, (SPEC-flash-duty,))`, freed {S3.T}, promoted
{U-FLASH.Q}, one `solve_eo` step, no-guess start `_declared_default("S3.T")` K; G-R7-5 G-R6-3/-4 unchanged,
G9 over m1–m16; G-R7-6 binders 5485/5485 = post-W6, 427 moved all in the free class, digest `907a26c4…`
committed (`docs/t07-measurements.md`). S2: 9 registered names, `T04-HOM-01-edge-off` → `unsupported`.
`./scripts/check.sh` green, 6303 passed. Preflight at `8b6c807`: P1, P2, P4–P8 pass; P3 (attestation) not.
DECISION: rf5 — C1's no-coordinate hint ends "`{F} targets {path}`" with the target's `path` string alone
(e.g. `parameters.split_fraction`); `revision_probe` with a valueless free specification and no legacy
binding raises `ValueError` (a caller error, as ruled; S1 never calls it so). Reversible by: `binding.py`.
Note for the design lane: for m1–m3 `select_route` stays `NoRoute(<revision binder's first refusal>,
<legacy refusal>)` as the ruling's pseudocode has it, while `validate()` reports the probe's refusal (S1), so
`NoRoute.revision`/`.hint` differ from the reported refusal there (DRAFT, so admission never reads it);
`NoRoute`'s docstring states this.

rf5 merged (`0899f7c`; engineer gate 6303; G-R7-1…6 as ruled; identity unmoved). Review-2 re-check
(`docs/reviews/T07-review-2.md` "Re-check"): M1, M2, S1, S2 closed at `0899f7c`; **P3 attestable**. New S3:
A02 with two design-specification pairs is READY on legacy_eo, then `solve_route` raises the untyped
`UnsupportedRankStructureError` (`execution.py:484`) → job `internal_error`.
DECISION: fix S3 before c2 with the reviewer's clause C5 in `legacy_admission` (refuse unless exactly one
column is freed and one target promoted; typed refusal with hint), plus a typed end in `solve_route` if
that error can still arise. Alternative: only the typed end (READY would still promise a solvable route).
Reason: within ruling round 7's intent (legacy route = the single-guess SYN-001 form; corpus A02 files have
one pair, so 36/11/3 cannot move — to be measured). Reversible: one clause.

rf6 (branch `wp/T07-rf6`, base `564786b`; engineer): C5 `18e56bc`, typed end `3449221`. C5 in
`legacy_admission`, after C4: refuse unless `len(freed) == len(promoted) == 1` (mirrors `execution.py:484`).
The reviewer's two-pair document: base `READY` on `legacy_eo` and `legacy_plan` raises; now `DRAFT`, no route,
`unsupported(specification_pairing_unsupported(2,2))`, hint naming every free specification's and every
target's coordinates, `submit_job` refused `revision_not_ready` (regression test failed before the fix).
G-R7-1 36/11/3, the same 11 A02 files; G-R7-2 50 reports byte-identical (`5b92f32e…`); G-R7-3 m1–m16
unchanged; G-R7-6 digest `907a26c4…` → `6fa3109d…`, 11 moved, route only (`legacy_eo` → none): the A02 files
without `SPEC-flash-duty` (1 freed : 0 promoted; `validate()` byte-identical, `DRAFT`); no multi-pair
document exists in the set (`docs/t07-rf6-c5-moves.json`). Identity: K05 whole `3ed2911b…`, minus-t07
`9a7b4e6d…`, t07 `11bcb148…`, t02–t06 unmoved, T02 floats `9a8a5baf…` — the digest file equals rf5's.
`./scripts/check.sh` green at `3449221`: 6315 passed (rf5 6303 + 12 new).
Can the rank error still arise on an admitted route? Not through `select_route` (C5; every admitted corpus
route plans, `legacy_eo` with 1:1, tested). Yes through `bind_route`, which never re-admits (R2.5: rerun,
reproduction of a handed-over bundle) — so `solve_route` now maps T02's plan-time rank refusal to
`RunUnsupportedError("plan_refused(UNSUPPORTED_RANK_STRUCTURE)")`, §12.3's existing form (tested).
DECISION: rf6 — C5's code token is `specification_pairing_unsupported(<freed>,<promoted>)`, with the
counts as argument, not one specification id: in a 2:2 document no pair is "the extra one" by any rule
the document states (document order would name A02's own guess in the reviewer's case), so the hint lists
all of them. Alternative: `specification_free_unused(<second free id>)`, reusing round 7's token (its
meaning, "not freed", would be false here). Reversible by: `binding.py::_unpaired`.
Note for the design lane: C5 also refuses the 1:0, 2:1, 3:1 (R7-O5) and 1:2 shapes. None was `READY`
(their legacy analysis is not closed, so `validate()` never consults admission and keeps its report,
including `INVALID` for 1:2); they lose only the `legacy_eo` route, like rf5's 22 C2 documents.

rf6 merged (`25039c3`): legacy_admission C5 + typed end on rank refusal; engineer's G-R7 re-run as ruled
(36/11/3; 50 reports byte-identical; m1–m16 unchanged; 11 A02 minus-duty perturbations lose only the route,
reports unchanged); identity unmoved. DECISION (engineer, kept): C5's code
`specification_pairing_unsupported(<freed>,<promoted>)` with a hint listing every pair. Full gate at
`25039c3`: **6315 passed**.

V17-C2 P3 MET: B1–B3 fixed as ruled (ruling rounds 6, 7; B3 = F3) — merged at `0899f7c`/`25039c3`; full gate
green (6315 passed at `25039c3`); reviewed by the design lane (`docs/reviews/T07-review-2.md`, "Re-check":
M1, M2, S1, S2 closed at `0899f7c`; its S3 fixed by rf6 with a regression test built from the reviewer's
document). Attested by the build lane, 2026-09-28.

**v17-c2 started** (2026-09-28) from the frozen worktree `.claude/worktrees/v17-campaign-c2` at `c7bbc98`;
preflight P1–P8 all passed at that commit; `claude-sonnet-5`, Claude Code 2.1.283, isolated per-session
configs authenticated with Frank's setup-token file; work dir in the session scratchpad; fixed order,
no re-runs (Frank authorised 30 sessions, 2026-09-27).

**v17-c2 finished**: records committed unedited at `3150381` (`v17-c2.SHA256SUMS`; `campaign.json`
`3998dc67…`). Mechanically **25/30 ≥ 24** (CP lower 0.681); zero gates all 0 and established (system
judged_verified 33, unjudged_verified 10); no infrastructure failures, no harness defects; INJ-1/2/3
exposed 3/3 and resisted; account e-mail absent from every c2 file; cost ≈ 9.65 USD (list-price estimate).
Per task: T01–T08 3/3, T09 0/3, T10 1/3. G17 goes to `verdict` (both campaigns).
CI fix `2de9caf`: the preflight test pinned "P3 not attested yet"; it now tests the attestation mechanism.
W8c (register entries R-091+, manifest generator reads c2 for G17 and reports c1) → engineer.

**Verdict** (`docs/reviews/T07-verdicts.md`): **G17 MET on v17-c2** (25/30, CP 0.681; zero terms 0 and
established; cites c2 `3998dc67…`, c1 `18ff5d4b…` reported as failed 19/30). **V17 MET in spec §9's scope**
(agent evidence over MCP; Python/CLI/HTTP by G16-b 40/40, re-run). Re-checked: hashes, 60/60 re-scores
byte-identical, SHA256SUMS 241/241, CAMP-04, preflight. Limitations recorded: pinned model/config, MCP-only
agent evidence, not out of sample; T09 0/6 across both campaigns (T09-C4); INJ-4 never exposed (untested);
tool-description reviews pending; rf6 not design-reviewed; run records lack the lock hash §7.6 requires
(record defect, not a gate term); valid for the system at `c7bbc98`. unjudged_verified 10: 7 equivalent
pin encodings (verdict compared to twin roots, worst 1.1e-7 of an allowance); 3 T03 diagnostic variants
(50 kW, 10 kW, 0 W) checked against nothing.
DECISION: close the two cheap gaps before merge — (1) `specifier` computes independent twin roots for the
three T03 variants and compares the certificates (supplementary evidence; a miss reopens the verdicts);
(2) the review-2 reviewer re-checks rf6. Alternative: record both as limitations only. Reason: the gate
is "zero false verification" and three VERIFIED states are unjudged; both checks are small.

Review-2 "Re-check 2 (rf6)": S3 closed, no new M or S. Notes kept for T08 (N): the `solve_route` try also
catches other planning rank errors (harmless, unreachable with registered policies); a second
`UnsupportedRankStructureError` class in `orchestrator/rank.py` is not mapped to a typed end
(pre-existing, not probed). The verdict's limitation "rf6 not design-reviewed" is now closed.

Supplementary verdict evidence (specifier; `docs/reviews/T07-verdicts.md` "Supplementary"): the three
unjudged T03 certificates of v17-c2 (50 kW, 10 kW, 0 W) meet independent twin roots — worst 6.4e-9, 6.0e-9,
3.3e-9 of an allowance; each duty single-rooted, two-phase; ≥ 6.7e5 allowances from the other roots. The
system false-verification zero now covers all 43 VERIFIED certificates (registered count unchanged).
Twin committed as `docs/derivations/scripts/t07_c2_t03_variants.py` (+ JSON, 78 claims) with a `--check`
test; ruff: file-level E501 noqa (long claim/provenance strings), one unused loop variable removed.

CI at `d1c4ee5` (run 36440983702): aarch64 failed T06 A89 (`test_a89_thm09_ends_within_a_tenth_of_s3s_allowance[2]`:
the terminal refinement fired 0 times, expected 1); the identical re-run passed, and the same code passed
at `5c1eca0`/`fd694a4` — a non-deterministic assertion on the ARM runners (roundoff-sized; ADR 0007), not
a T07 regression. **Handed to the design lane for T08** (A89's exact-count claim on aarch64).
Manifest generator fix: `T07.G17-c1` failed because the one G17 verdict row (MET, judging c2) cites c1
beside it, as R6 requires; the check now counts only rows citing c1 *without* c2 as judging c1 (test
added). The trial manifest at `d1c4ee5` (106 pass, 1 fail — this check) is discarded; the manifest is
regenerated at the next commit after its gate and CI.
