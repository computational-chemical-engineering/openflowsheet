# X06 build decisions (append-only)

Build-lane choices for package X06 (application capabilities) that ADR 0078 leaves open. ADR 0078 is Proposed; the
build follows its text as it stands. Where it is silent, the reading taken is the one that changes no existing byte.
Each line: `DECISION`, the choice, the alternative, and where it lives. Each is revertible on its own. Batched for the
package's one design-lane ruling round (CLAUDE.md, agent budget).

## X06-WO1 (MCP over streamable HTTP, D1), 2026-11-26

Files: `src/openflowsheet/application/bindings/{mcp,mcp_http,http}.py`, `application/{serving,cli}.py`,
`messages/catalogue/refusals.yaml` (`origin_refused`) and its generated `docs-site/messages/refusals.md`;
`tests/test_x06_mcp_http.py`, the sixth client (`tests/t07_transport_support.py` `McpHttpClient`,
`tests/test_t07_conformance.py`), the import-graph allowlists (`tests/test_t07_w6{a_http,b_mcp}.py`), and the two
tests that intercepted the CLI's serve call (`tests/test_t07_w5b_cli.py`, `tests/test_m06_wo4_serving.py`).

- **DECISION WO1-1. Composition in `serving`.** `serving.http_application(owner, host, port, ui)` builds what
  `serve-http` serves (REST routes, the shell with `--ui`, `/mcp` through `mcp_http.mount`); `serving.serve_http` runs
  it under `http.run`; the CLI calls `serving.serve_http`. `http.serve` and `web.serve` are unchanged (REST only, REST
  plus shell) and are no longer the CLI's path; the two tests that monkeypatched them to intercept the CLI now patch
  `serving.serve_http` and `http.run`. Alternative: a hook argument on `http.serve`/`web.serve`. Reversible by moving
  the composition back behind those two.
- **DECISION WO1-2. The warning text.** `http.run` gains `warning=NO_TLS_WARNING` (the old text, byte for byte, so
  `http.serve`/`web.serve` print what they printed); `serve-http` passes `serving.HTTP_NO_TLS_WARNING`, the same
  sentence ending "on the REST routes and on /mcp". Alternative: change the one text everywhere.
- **DECISION WO1-3. What the guard is given.** `McpGuard(manager, authenticate, origins=, max_body_bytes=)`: the
  composition passes `owner.authenticated`, `served_origins(host, port, loopback=http.is_loopback(host))` and
  `http.MAX_BODY_BYTES`, so `mcp_http` imports exactly D1.7's list (no `bindings.http`). The bearer grammar is
  repeated; a test holds `mcp_http._BEARER.pattern == http._BEARER.pattern`.
- **DECISION WO1-4. What is audited.** Nothing the guard refuses is audited: 405, 403 and 413 come before the
  credential is read (D1.5's order), and the 401 is not audited on the REST routes either (no principal is known).
  REST audits its 413 because it authenticates first; D1.5 puts the size check first.
- **DECISION WO1-5. The refusal documents.** 405: `invalid_request`, `detail {method, allowed: "POST"}` (REST's
  wrong-method shape) at status 405, `Allow: POST`. 413: `invalid_request`, `detail {pointer: "", limit_bytes}` (REST's
  shape) at 413. 403: `forbidden`, `detail {code: origin_refused, origin}`, the message led by `origin_refused:` because
  the explanation reads its chain from the message (MSG §4.4; as `nlp_solver_unavailable`). 401: REST's two messages,
  `WWW-Authenticate: Bearer`. Each is `project_error`-bounded JSON as REST writes it.
- **DECISION WO1-6. The body is read before the credential.** D1.5 (c) before (d): the guard reads the body whole, up
  to `MAX_BODY_BYTES` (an unauthenticated client can make it buffer at most 1 MiB, as REST does after its check), then
  replays it to the SDK. A client that disconnects mid-body gets no answer. The SDK's own body limit (4 MiB default) is
  left as it is; the guard's comes first.
- **DECISION WO1-7. Served origins are fixed at composition** from `--host` and `--port`. With `--port 0` no browser
  origin matches (fail closed; clients that send no `Origin` are unaffected). Alternative: read the bound port from
  the ASGI scope's `server` per request.
- **DECISION WO1-8. The conformance client.** `McpHttpClient` opens a session per call (`initialize`, then the call):
  the server is stateless, and the SDK client ends its session on any HTTP error status, so the revoked step's 401 is
  read from a recording transport and compared by code and `retryable` (relation `code`, as REST's). `Run` carries the
  client's operation set, which replaces the per-name `SERVED` lookups.

### Q9 measured (`mcp==1.30.0`, stateless JSON mode, past the guard, `tests/test_x06_mcp_http.py`)

Batch (JSON array): 400, JSON-RPC -32602. Accept `text/plain`, or `text/event-stream` only: 406, -32600. Content-Type
`text/plain`: 400, plain text "Invalid Content-Type header". `MCP-Protocol-Version: 1999-01-01`: 400, -32600. Body not
JSON: 400, -32700. Notification: 202, empty body. None of these runs a tool (no refusal audited). A `tools/call`
without `initialize`: 200, runs (stateless: no session requires it). The guard answers `GET`, `DELETE`, `PUT` with 405.
The SDK client negotiates protocol `2025-11-25`; no `Mcp-Session-Id` is sent.

## X06-WO2 (branches, D2), 2026-11-26

- **DECISION WO2-1. E-X06-7's sources.** At `aa5822ac` no JSON file under `tests/fixtures/` validates against
  `change-set.schema.json` (0 of 840), so the ADR's set alone gives an empty list, which E-X06-7 forbids. The golden
  list (`tests/fixtures/x06/change_set_golden.json`, written by `tests/test_x06_change_set_golden.py --write` in a
  detached worktree at `aa5822ac`) takes that set (still empty) plus every `commit_change` and `preview_change` tool
  input recorded in the committed transcripts under `benchmarks/` (V17 c1/c2, OpenIDAES-450): 78 commits and 225
  previews that validate (8 previews do not and are skipped), 303 entries, each normalized as the operation does
  (preview completed by the key `preview`). These are real requests agents sent, which is what the test protects.
  Alternative: synthetic ChangeSet fixtures written now (proves less: they never hashed under the old code in use).
  Reversible by: deleting the transcript source from the module and adding fixtures. ADR divergence, reported.
- **DECISION WO2-2. `ChangeSet` (K06's one-object form) gains `branch` too.** The ADR names only `Change`; without
  it `ChangeSet.from_document` would drop a request's `branch` silently. Its `as_document` goes through
  `Change.as_change_set`, so the omission rule (absent or `"head"`) is one rule. Reversible by removing the field.
- **DECISION WO2-3. Where the branch types and checks live.** `Branch` and `BranchResult` are in
  `transaction_types.py` (contract vocabulary, beside `TransactionResult`; no new layer). `ref_name`,
  `BRANCH_NOT_FOUND` and `BRANCH_NAME_RESERVED` are in `branch_service.py`, which `revision_service` imports (the
  layer order puts `branch_service` below it). `head`'s public spelling is `transaction_types.HEAD_REF`; the store's
  row name stays `store.HEAD`. Alternative: a `branch_types.py` module and layer.
- **DECISION WO2-4. A commit re-assigns an auto id taken by a concurrent commit on another ref.** E-X06-8's "a branch
  commit racing a head commit → both succeed" cannot hold otherwise: both prepare `rev-<next ordinal>` from one
  snapshot, and the second writer found the id taken and returned `rejected revision_id_taken`. `commit_change` now
  prepares again (fresh id, re-validated, outside the lock) when, inside the lock, its ref is still at
  `expected_revision` and only the assigned id was taken; at most `ASSIGNED_ID_ATTEMPTS = 8` times. A caller-named
  id is never re-assigned. Head-only behaviour is unchanged (a taken id there means the head moved: `conflict`, as
  before). Falsifier: with 1 attempt the `mixed` race fails in threads and processes. Escalation item: this is a
  behaviour change of `commit_change` the ADR did not state (it states the outcome).
- **DECISION WO2-5. Preview checks that the branch exists** (`not_found branch_not_found`, audited), and nothing
  else about it (no tip check, as a preview has no head check). Alternative: ignore `branch` in a preview.
- **DECISION WO2-6. Branch writes and their records.** Ledger rows are written only for `created` and `deleted` (as
  `commit_change` ledgers only `committed`); a `conflict` is re-judged on retry. Request hash: `document_sha256` of
  the request as the operation's schema states it (`{name, revision_id, idempotency_key}` /
  `{name, expected_revision, idempotency_key}`). Audit effect `branch:<name>:created|deleted`. Conflicts are not
  audited (as `commit_change`'s). `list_branches`' cursor is `base64url(canonical {"after": <last name>})`, `head`
  standing before every branch. The HTTP `delete_branch` takes `name` from the path only (the body repeating it is
  §11.3's "given more than once").
- **DECISION WO2-7. Description texts.** `commit_change.md` was at its 1500-character bound; the `branch` sentence
  fits by tightening four phrases (no meaning removed; the generated target table untouched; 1499 characters).
  Both changed texts and the three new ones are recorded `pending` in `REVIEW.json`, so
  `test_t08_w2_description_reviews.py` stays red (by its design) until the design lane and the user review the five
  hashes. Pre-X06 copies: `tests/fixtures/x06/pre_x06_descriptions/`.
- **DECISION WO2-8. Surface registration.** `X06_SERVED_SHA256 = 7e8393a5…`; `without_x06` removes the three tools,
  the ChangeSet's `branch` wherever served (also the optimization report's `candidate.change_set` inside
  `get_job_result`'s `outputSchema`, which `$ref`s the ChangeSet) and restores the two texts: the result is F3's
  `f7ec3c94…` exactly. Chain link c_12 (R-1073) in `scripts/m07a_rc.py` onto c_10; R-1073's register entry is on
  `main`, so the c_12 test does not read the register (the c_10 form does); its digests go there at the merge.
- **DECISION WO2-9. The support envelope follows the lifted limitation.** `benchmarks/t08/support_envelope.yaml`:
  U08 no longer names branches (capability, outcome, and its evidence line), and
  `test_u08_a_change_set_naming_a_branch_is_refused_by_its_schema` is removed (its premise is what R-110's lift
  for branches reverses; E-X06-6 tests the name pattern's refusals). The interfaces row lists the three operations
  and reads "thirty-three"; `scripts/t08_support_matrix.py`'s A20 count is 33; `docs/support-matrix.md`
  regenerated. U08 still names MCP over HTTP, which WO1 served: left for WO5 (not this WO's change).
- **DECISION WO2-10. Fixtures.** `scripts/t07_schema_fixtures.py` emits `branch_result`, `branch_page` and `branch`
  from real responses; the two `message_entry` fixtures' catalogue sha256 re-taken for the two new entries (as
  WO1 did for `origin_refused`). R4-G3: `SNAPSHOT_X06` holds the three new rows and the six job rows that embed the
  optimization report's candidate ChangeSet; `without_x06` restores each to its earlier snapshot. The G14 suites
  (CLI, HTTP, MCP) run `x06_schema_support.branches_requests`.

## X06-WO3 (solve policies, D4), 2026-11-27

Files: `orchestrator/policy_validation.py`; `application/{solve_policy_registry,solve_policy_service}.py`;
`admission.py` (`policy_id_refusal`, `resolve_policies(…, project_policies)`), `validation_service.py`,
`job_service.py`, `jobs/runner.py`, `inspection_service.py`, `inspection_types.py`, `contract.py`
(`SolvePolicies`), `operations.py`, `authz.py`, `local.py`, `store.py` (`artifact_in`); two description texts;
`application-results` `$defs`; three catalogue entries; layers; `tests/test_x06_solve_policies.py`.

- **DECISION WO3-1. The registries of D4.3 (d).** `initializer_chain` entries ⊂ {`compatible_warm_start`,
  `traversal-G0-v1`} (the executor reads only the first; the second is the registered initializer, and the two are
  every offered chain's values). `linear_solver` must equal the registered SuperLU document member for member (the
  executor never reads the policy's: any other value would record a solver that did not run). `residual_tolerances`
  and `scales` keys ⊂ the solver's residual kinds (`models.lifted_tolerance.KIND_TOLERANCE`: `heat_rate`,
  `molar_flow`, `molar_flow_squared`, `pressure`, `temperature`; `units.KINDS` lacks `molar_flow_squared`).
  `recycle.policy_id` ∈ {`T02-recycle-policy-v1`}. `recycle.tear_streams` is refused: it names one flowsheet's
  streams, there is no registry, and D4.3 says every open string under `recycle` is checked at registration, never
  at run time. `globalization` has no open string (const, enum, numbers, fraction patterns). Escalation item: the
  `tear_streams` refusal and the exact `linear_solver` match are the strictest readings; both offered-policy copies
  pass (all five, test). Alternative: accept `tear_streams` and leave its run-time check.
- **DECISION WO3-2. `solve_policy_problems` returns `PolicyProblem(pointer, message, code)`**, a NamedTuple (the ADR
  writes `(pointer, message)`): the service needs the `detail.code`; `None` for a schema error (plain
  `invalid_request`). The refusal's pointer is `/policy` + the problem's.
- **DECISION WO3-3. The registry is read only for a `user.` id.** Admission (`validation_service`), the runner's two
  `resolve` stages (`solve`, `optimize`'s solve body) and `get_job_result`'s re-resolution call
  `solve_policy_registry.load` only when the requested id matches D4.1's pattern; an offered, `default` or unknown id
  never reads the store, so a damaged registration cannot change an offered policy's behaviour (test). A damaged one
  (file missing or not hashing to its row) is `internal_error` at admission (audited) and `failed store_error` in the
  runner. Alternative: load on every resolution (the ADR's text is silent on when).
- **DECISION WO3-4. Where things live.** `SolvePolicyRegistration`, `SolvePolicyView` in `inspection_types.py`
  (contract vocabulary, so `contract.py` can name them). `ProjectStore.artifact_in(connection, id)`, a read inside
  the caller's transaction (no schema change). `solve_policy_registry` sits directly above `authz`,
  `solve_policy_service` directly above `service_core` (both added to the `transports-through-operations` list).
- **DECISION WO3-5. Registration records.** Only `registered` is ledgered and audited (effect
  `solve_policy:<id>:registered`), as WO2-6; `exists` and `conflict` are re-judged on a retry (write-once makes the
  answer stable). Request hash `document_sha256({policy, idempotency_key})`. On `conflict`, `policy_sha256` is the
  stored hash, `conflict.expected_sha256` the request's, `actual_sha256` the stored.
- **DECISION WO3-6. Refusals.** `admission.policy_id_refusal` is step 4's judgment, shared by `get_solve_policy`: the
  seven benchmark names and a non-`user.` unknown id keep today's documents byte for byte (fixture); an unregistered
  `user.` id is `not_found`, `detail {code: solve_policy_not_found, policy_id}`, the message led by the code.
  `get_solve_policy("default")` is `not_found` with the unknown-id document (`default` names no policy of its own).
- **DECISION WO3-7. Texts.** `register_solve_policy.md` (1363 characters) and `get_solve_policy.md` (690), recorded
  pending in `REVIEW.json`. `submit_job.md` is unchanged (ids are discovered through `get_project`; the new texts
  name the route). The description-review gate now lists seven texts.
- **DECISION WO3-8. Surface.** `X06_SERVED_SHA256 = 4a80f77f…` (c_12's `D_12`); `without_x06` removes the two tools
  too (`X06_OPERATIONS`) and decomposes onto F3's `f7ec3c94…`; `X06_FILE_SHA256` gains the two files. R4-G3:
  `SNAPSHOT_X06` gains the two rows; no earlier row moved. The support envelope: 35 operations, the `solve_policies`
  axis states project policies (evidence E-X06-12), U08 now names "the benchmark-registered solve policies that are
  not offered"; A20's count 35; `docs/support-matrix.md` regenerated. The conformance scenario gains
  `_solve_policies` (ten steps) and a `user.absent` solve refusal on all six clients.
- **DECISION WO3-9. E-X06-15's pre-X06 fixture** (`tests/fixtures/x06/pre_x06_policy_surface.json`) was taken at
  `aa5822ac` in a detached scratch worktree: `get_project` of project `x06-get-project` and `solve`'s refusals of the
  seven names and `no-such-policy`. The test substitutes `server.package_version` with the running version (equal at
  both commits today), so a release bump does not break it.

### Q7 measured: a path dispatches on the policy's name (STOP, design lane)

E-X06-12 passes: `user.copy` (`T06-revision-v2`'s document, only `policy_id` changed) solves SYN-001-nominal to a
byte-identical `solution-state.json` (equal `state_sha256`), `CONVERGED`/`VERIFIED`; the certificate differs only in
`policy_id` and `plan_id` (which embeds the id); the manifest's `policy_sha256` is `user.copy`'s. **E-X06-13 fails**:
`run.bundle.verify_bundle` → `_cross_check_solve_path` resolves `solve-path.json`'s `policy_requested` **by name**
through `orchestrator.policies.resolve_policy`; `user.copy` resolves to nothing, so the bundle's integrity is
`{ok: false, tampered: [solve-path.json]}` and a fresh project reproduces it `inspected_archived_results`/`NOT_RUN`
(the `T06-revision-v2` bundle: `compatible_reproduction`/`MATCH`). This contradicts the ADR's context ("replay
rebuilds the policy from that file … never by id lookup") for the integrity check. Not fixed here. The choice the
build lane would make: for a `user.` `policy_requested`, the candidate is `SolvePolicy.from_document(solve-policy.json)`
with its `policy_id` equal to the request (the manifest-hash comparison as for the others); every existing bundle is
judged as today. It touches replay identity, so it waits for the design lane. Tests: E-X06-13 is `xfail(strict=True)`
with this reason; `test_q7_the_bundle_check_resolves_the_requested_policy_by_name` pins the cause. E-X06-13's
`optimize` half was not run (no `nlp` extra in this environment).

### R-088 Q26 measured: `register_solve_policy` accepts a numeric map (STOP, design lane)

`tests/test_t07_q26.py::test_t07_q26_no_external_state` fails: its static scan finds
`Finding(operation='register_solve_policy', path=('policy', 'scales'), kind='map')`. D4.5's request carries a whole
solve-policy document, whose `scales` is a map of quantity kind to number; Q26 allows a numeric map only by full path
with a recorded exception (as F3's `validate_record` `reactions/*/stoichiometry`, ADR 0061), and ADR 0078 names none.
Not relaxed here (brief: no test passes by relaxing a check). The choice the build lane would make: allow
`register_solve_policy`'s `policy/scales` by full path, citing ADR 0078 D4.3: its keys are registered kinds, its
values policy constants checked once, the solver reads none of them (`policy.scales` is read nowhere in `src/`), and
nothing from it reaches a solver state; `residual_tolerances` is not flagged (a map of objects). Needs a design-lane
exception recorded as F3's was.

- **DECISION WO3-10. Reachable codes.** `get_solve_policy` of `T02-eo` makes `unsupported` reachable over MCP (stdio
  and HTTP), so the conformance `REACHABLE` table gives all six clients `unsupported`. The CLI's G14 scenario runs
  `solve_policies_requests()` too.

## Design-lane rulings R1 (`architect`, 2026-11-27; brief `docs/briefs/LINE06-X06-R1.md`)

Two stops of X06-WO3: Q7 and R-088 Q26. Both rulings are clarifications of ADR 0078 as Accepted (R-1071): no decision
of the ADR is edited and no user card is needed (F3's form, R-1058). The orchestrator appends the ADR section and the
two register rows at the end of this section; the build lane implements R1-1 and R1-2 in one work order, with the
standing surface suites and F0 (LINE06_RULES).

### R1-1 (Q7): a `user.` request is judged against the bundle's own policy document

**Finding.** The stop is real and the diagnosis right: `run/bundle.py:237` resolves `policy_requested` through the
release's registry, which holds no `user.` id. ADR 0078's context ("never by id lookup") is true of replay
(`revision_replay.py:189-194`) and missed this integrity cross-check (T07 W3-Q4). D4.2 and E-X06-13, as Accepted,
require a project policy's bundle to verify and replay in a fresh project, so the check changes for `user.` ids and
for nothing else.

**Ruling: the proposal is sound, with the precisions below.** The rule in `_cross_check_solve_path` (everything up to
`known`, and the whole non-`user.` branch, unchanged byte for byte):

1. If `requested` is a `str` and `is_project_policy_id(requested)` (D4.1; lazy import from
   `orchestrator.policy_validation`, which `repo-layers` places below `run`), this branch alone judges the request
   and the function returns at its end. `solve-path.json` goes to `tampered` unless all of:
   a. the route is `known` (today's test);
   b. `solve-policy.json` is in the index and in neither `missing` nor `tampered`;
   c. `candidate = SolvePolicy.from_document(read_artifact(directory, "solve-policy.json"))` succeeds; any of
      `ValueError, TypeError, KeyError, AttributeError` counts as failure, judged and never raised (`AttributeError`
      is reachable: `"residual_tolerances": 5` fails at `.items()`);
   d. `candidate.policy_id == requested`;
   e. `policy_sha256(candidate) == manifest.policy_sha256`.
   There is **one candidate**, not two. `solve-policy.json` is the effective policy: `revision_run.py:870` writes
   `policy.as_document()` of the policy after admission step 6's `replace(policy, max_property_calls=...)`, so a
   lowered budget is already in it. The relation "lowered, never raised" needs the project's registered ceiling and
   is not checked.
2. **S1, a build-lane bug fixed in the same work order.** `is_project_policy_id` uses `PROJECT_POLICY_ID.match`, and
   the pattern ends in `$`, which in Python also matches before a trailing newline: `"user.x\n"` passes as a project
   id today (registration, admission, runner, and this new branch). Use `fullmatch`. No released byte moves: the
   string was refused before X06 and is refused after the fix by today's unknown-id path.

**What the check still detects**, against a forger who rewrites artifacts and recomputes the index and both manifest
hashes (`_rewrite`'s model): a request naming another id than the document (`solve-path.json` renamed alone); a
document whose content or id no longer hashes to the manifest's `policy_sha256`; a missing, unindexed or unreadable
document; a malformed or pattern-violating id; an unknown route; a named bundle relabelled `user.` in
`solve-path.json` alone. **What it does not detect, by construction:** a coherent substitution, the document, the
request and the manifest's `policy_sha256` rewritten together (for instance a `T06-revision-v2` bundle relabelled
`user.t06` throughout). A registered name is pinned to its content by the release's registry; a `user.` id is
project-scoped and bound once only within its project (D4.4), so no anchor exists outside the bundle. This is no
regression (no genuine `user.` bundle existed before X06) and no loss of acceptance safety: the verifier reads no
solve policy (D4.2, E-X06-14), and `reproduce` reruns the bundle's own document, so a substituted policy that did not
produce the archived state gives `MISMATCH`, never `MATCH`.

**The project store is deliberately not consulted.** (i) `verify_bundle(directory)` is a function of the bundle and
the release's code; a store lookup would give one bundle different integrity in different projects, against
E-X06-13 ("in a fresh project ... with the same replay verdict"). (ii) One `user.` id legitimately names different
bytes in different projects; a store comparison would call a genuine imported bundle tampered. (iii) `run` is below
`application` in `repo-layers`, and the registry lives in `application`. A difference between a bundle's policy and
the importing project's policy of the same id is information, not tampering; reporting it is outside 0.6 (default:
not reported).

**No existing verdict and no F0 value moves.** The new branch is entered only on a `user.` request. No committed
bundle carries one (`git grep` outside `docs/`: none; the 53 committed `solve-path.json` name `default` or a
registered id), and every release before X06 refused such ids at admission, so no genuine bundle anywhere does.
Measured at `c526de6a` with the script below: 63 committed bundles, 60 `ok`, the other 3 the W26 raw web fixtures
whose artifacts are not committed (`missing`), digest `b42b1ec439d1683c`. Gate: the same three values after the
change.

```python
# from the worktree root, PYTHONPATH=src
import hashlib, json, subprocess; from pathlib import Path
from openflowsheet.run.bundle import verify_bundle
files = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()
dirs = sorted(str(Path(f).parent) for f in files if f.endswith("run-manifest.json"))
docs = {d: verify_bundle(Path(d)).as_document() for d in dirs}
print(len(docs), sum(v["ok"] for v in docs.values()),
      hashlib.sha256(json.dumps(docs, sort_keys=True).encode()).hexdigest()[:16])  # 63 60 b42b1ec439d1683c
```

**Tests** (`tests/test_x06_solve_policies.py` unless named):
- T1 E-X06-13 (solve half): the `xfail` removed; passes as written. Should it still fail for another reason, that is
  a new by-name path: STOP and report, as Q7.
- T2 `test_q7_the_bundle_check_resolves_the_requested_policy_by_name` is replaced by
  `test_q7_a_project_policy_bundle_verifies_on_its_own_document`: `user.copy`'s integrity is
  `{ok: true, missing: [], tampered: [], unexpected: []}` and equals `T06-revision-v2`'s.
- T3 forged `user.` bundles, each built with full re-hash (W3a's `_rewrite`, `intact=False`; import or copy it), each
  `verify_bundle(b).tampered == ("solve-path.json",)`, and for F1 to F3 `reproduce(rerun=True)` `NOT_RUN` with no rerun
  manifest. F1: request `user.other`, document untouched. F2: document `max_attempts + 1`, manifest hash untouched.
  F3: document `policy_id: user.other` with the manifest hash recomputed, request `user.copy`. F4: the
  `T06-revision-v2` bundle with only its request set to `user.copy`. F5: `solve-policy.json` dropped. F6: documents
  `[]`, `{}`, one without `scales`, `"recycle": 5`, `"residual_tolerances": 5` (manifest hash untouched), each judged,
  none raised. F7: requests `"user."`, `"user.-x"`, `"user.x\n"`, `"user." + 65 * "a"`, each coherent (document id and
  manifest hash rewritten to match), so the pattern alone decides. F8: `solve_path: "no_such_route"`.
- T4 `test_q7_limit_a_coherent_relabel_is_not_detected`: the `T06-revision-v2` bundle relabelled `user.t06` in the
  request, the document and the manifest (`policy_id`, `policy_sha256`) verifies `ok`; the docstring cites this
  ruling. It pins the stated limit, so tightening it later is a recorded decision.
- T5 a genuine lowered run: `user.copy` solved with `max_property_calls` one below the document's; the manifest hash
  is the lowered document's, the bundle verifies `ok` and reproduces `MATCH` in a fresh project.
- T6 `is_project_policy_id("user.x\n") is False` (S1). `tests/test_t07_w3a_revision_runs.py`'s W3-Q4 tests pass
  unchanged.
- E-X06-13's `optimize` half runs where the `nlp` extra is installed; until it has run, the evidence manifest records
  it `not run`, never passed.

**S2, recorded only (not X06's).** For a *named* bundle whose `solve-policy.json` is malformed under a coherent index,
W3-Q4 reads only `max_property_calls`, integrity is `ok`, and `revision_replay._recorded_policies` (catching
`ValueError, TypeError, KeyError`) lets `AttributeError` from `"residual_tolerances": 5` escape `reproduce`: a forged
bundle raises instead of giving `NOT_RUN`. Default: not fixed in X06 (outside D4; it touches the named path); the
orchestrator files it for the next code-health batch.

### R1-2 (R-088 Q26): `register_solve_policy`'s `policy/scales` is admitted by full path

**The claim, checked.** `SolvePolicy.scales` is declared, written and read back only in `numerics/solve_record.py`
(lines 678, 717, 752). No solver, verifier or study module reads it: the other `scales` in `src/` are the compiled
problem's row and column scales (from `numerics/scaling.py`'s registered nominals), the NLP closure's, the coupling
block's and the surrogate score's. The offered policies carry `scales: {}` (`orchestrator/policies.py:75, 91`; the
others are `replace`s of `T06-revision-v2`).

**Ruling: grant by full path; do not refuse `scales`.** The grant rests on the map's shape, not on its being unread
today. Its keys are a closed registry (`QUANTITY_KINDS`, checked at registration by D4.3(d), tested by E-X06-11c),
its values strictly positive constants (schema `exclusiveMinimum: 0`), never taken from an iterate (ADR 0001 D3.5).
At most |QUANTITY_KINDS| per-kind constants cannot carry a per-variable state or a matrix; the map has the shape and
key domain of `check_tolerances`, which §13 admits by name. Refusing it is not implementable without an ADR change:
D4.1 keeps `solve-policy.schema.json` unchanged and D4.5 makes the request the whole document, so the static scan would
still find the map (a runtime refusal is invisible to it), and Q6's route to variants (`get_solve_policy`, edit,
`register_solve_policy`) needs every member accepted. If a later package makes the solver read `SolvePolicy.scales`,
the values still only steer the search, and acceptance stays with `CheckPolicy` (D4.2); that package re-examines this
row.

**A second finding the measurement did not reach.** Admitting the map alone leaves the test red at its next
assertion: the request also carries 39 numeric scalars (measured at `c526de6a` with the test's own `_findings()`),
which the pinned scalar-name inventory does not list. The exception has two halves, as OPT's (D-58) had:
- `ALLOWED_BY_PATH` gains `("register_solve_policy", "policy/scales", "map")`.
- `SOLVE_POLICY_PREFIXES = {"register_solve_policy": "policy/"}` and `SOLVE_POLICY_SCALARS`, exactly these 39 paths
  below that prefix, asserted equal as `OPT_REQUEST_SCALARS` is and excluded from the `names` inventory the same way:
  `armijo_c`, `eta_inner`, `linear_residual_threshold`, `max_attempts`, `max_iterations_per_attempt`,
  `max_property_calls`, `phase_wall_patience`, `stagnation_ratio`, `stagnation_window`, `step_halvings_max`;
  `globalization/eo_recovery_max_count`; `globalization/homotopy/` `corrector_max_iterations`, `growth`,
  `max_lambda_trials`; `globalization/ptc/` `gamma_max`, `gamma_min`, `max_steps_per_attempt`, `phi_floor`,
  `residence_time_s`, `retries_max`, `retry_shrink`, `tau_initial_s`, `tau_max_s`, `tau_min_s`; `recycle/` `beta`,
  `beta_substitution`, `beta_substitution_oscillating`, `coefficient_max`, `condition_max`, `depth_max`,
  `max_iterations_per_attempt`, `max_restarts`, `oscillation_window`, `stagnation_ratio`, `stagnation_window`,
  `step_halvings_max`; `residual_tolerances/*/` `absolute`, `relative`, `scale`.
- No untyped member is added and `get_solve_policy` adds no finding (measured).
- The module docstring gains a paragraph in F3's form citing ADR 0078 D4.3(d) and D4.5, the ADR section below and the
  register row.

**Tests.** `tests/test_t07_q26.py`: 6 passed (today 1 failed, 5 passed). E-X06-11c refuses an unregistered key under
`/scales` with `solve_policy_invalid` at that pointer (confirm the walk reaches it; add the case if not).

**Recording.** Within ADR 0078 D4 as written: D4.5 and D4.3(d) already decide that the operation accepts `scales`
keyed by registered kinds; the exception names a consequence. F3's form: an appended ADR section and a register row;
no user card.

### Text the orchestrator applies (not in this commit)

ADR 0078, appended after its last section:

> ## X06 ruling round R1 applied (`docs/X06_DECISIONS.md`, "Design-lane rulings R1", 2026-11-27)
>
> Status stays Accepted (R-1071). Two clarifications, recorded in the decision register; no section above is edited
> and nothing accepted is changed.
>
> | Of | Clarification | Register |
> | --- | --- | --- |
> | D4.2, E-X06-13; T07 W3-Q4 | A bundle whose `solve-path.json` requests a `user.` id (D4.1, matched whole) is judged against its own `solve-policy.json`: the route known; the document indexed, intact and rebuilt; its `policy_id` equal to the request; its `policy_sha256` equal to the manifest's. The project store is never consulted. Every other request is judged as before. A coherent substitution of a `user.` policy is beyond integrity; replay and the certificate stay the guard. | R-Q7 |
> | D4.3(d), D4.5; R-088 Q26 | `register_solve_policy`'s `policy/scales`, a map of registered quantity kind to a positive constant, is the one numeric map R-088 Q26 admits in the `SolvePolicies` requests, by that full path and only there; the request's 39 numeric scalars are pinned by full path (`tests/test_t07_q26.py`). | R-Q26 |

Register rows (R-Q7 and R-Q26 stand for the next two free numbers on `main`): R-Q7 "`verify_bundle` judges a `user.`
request against the bundle's own policy document, never the project store (X06 R1-1)"; R-Q26 "R-088 Q26 admits
`register_solve_policy`'s `policy/scales` map, by full path (X06 R1-2)". Both: decided by the design lane
(`architect`), X06 ruling round R1, clarifying ADR 0078 (Accepted, R-1071); normative text the ADR section above;
evidence this section's measurements; affected package X06.

## X06-WO3b (rulings R1 applied), 2026-11-27

- **DECISION WO3b-1. The 40th scalar.** R1-2 lists 39 numeric scalars below `register_solve_policy`'s `policy/`;
  `_findings()` measures 40, at `c526de6a` and at `313907cd` alike (neither the scanner nor
  `schemas/solve-policy.schema.json` changed between them): the listed 39 and `policy/admissibility_epsilon` (a
  top-level `number`, `exclusiveMinimum: 0`, registered value `1e-12`, read by the region solver's admissibility
  test; a constant, not an iterate). Pinned as the 40th, and the ADR 0078 R1 section's "39" reads "40", both in one
  commit. Alternative: leave the pin at 39, and `test_t07_q26_no_external_state` stays red. Reversible by: reverting
  that commit. For the design lane's single review pass.


## X06-WO4 (in-band administration, D5), 2026-11-27: part 1 (stopped at the context cap)

Commits: `a9038f7b` (E-X06-21 fixture `tests/fixtures/x06/pre_wo4_cli_audit.json`, taken at `4ca7ce3c`), `a84e9b14`
(the code). Files: `policy_types.py` (switch, `GrantResult`, `RevokeResult`, `AmbientPressureResult`),
`schemas/project-policy.schema.json` (`administration`), `authz.py`, `administration_service.py`, `service_core.py`,
`serving.py`, `cli.py`, `contract.py` (`Administration`), `operations.py`, `local.py`, four description texts (pending
in `REVIEW.json`), three `$defs`, six catalogue entries, layers.

- **DECISION WO4-1. The switch's form.** `administration: {in_band: {const: true}}`; off is absence only (a written
  `false` is refused, as an unsorted `rights` list is: one document per policy). Alternative: accept `false` as off.
- **DECISION WO4-2. `change_policy` gains `connection=None`.** D5.5's signature plus one keyword: given, the write
  runs inside the caller's transaction (the in-band service, whose ledger row shares it); absent, it opens
  `store.writing()` (the CLI). `request_sha256=None` means "the updated policy's hash" (the CLI's form, which it cannot
  know before `apply`). The CLI's rows equal the fixture (checked by script; the test is still to write).
- **DECISION WO4-3. Order inside a write.** D5.3's switch, remote and delegation refusals before the ledger lookup;
  `capability_exists`, `capability_not_found`, `revoke_exceeds_caller` inside the transaction after it, so a replay of
  a grant with a fixed `capability_id` is `replayed`, not `capability_exists`. Only effects are audited `allowed` and
  ledgered (as WO3-5); a replay writes nothing.
- **DECISION WO4-4. `set_ambient_pressure`.** `unit` a bounded string judged by `ambient_pressure_pa` (so a gauge or
  unknown unit is `ambient_pressure_invalid(unit)` as on the CLI), Pa when absent; `value: null` with a `unit` is
  `invalid_request` at `/unit` (the CLI's `--clear` takes no unit). Result `$def` named `ambient_pressure_result`.
- **DECISION WO4-5. Messages lead with the code** (`administration_disabled: …`), as WO2/WO3 do: `render_error` reads
  the chain from the message, so a refusal without it renders as its bare API code.
- **DECISION WO4-6. `serving_remote`.** `serve_http(owner: LocalApplication, …)` sets `owner.serving_remote = not
  is_loopback(host)` before composing; `authenticated` views copy the core afterwards and share it. Stdio and
  in-process never set it.
- **DECISION WO4-7. Cross-project comparisons of a grant.** `x06_schema_support.stable_administration` replaces the
  random parts (a `prt_` token, every `token_sha256`, a grant result's `policy_sha256`) by a placeholder; nothing else.

### STOP (R-088 Q26; for the design lane, not pinned)

`test_t07_q26_no_external_state` reports four new numeric request members, as the test prints them: `max_wall_time_s`,
`default_wall_time_s`, `max_active_jobs` (all three under `grant_capability`'s `limits/`) and `value`
(`set_ambient_pressure`). They are a grant's budget ceilings and a display-only declaration, not model inputs.

### Where WO4 stopped (done by X06-WO4b, below)

Green at `a84e9b14`: `test_t07_w5a_operations.py`, `test_t07_authz.py`, `test_t07_w6a_http.py` (admin steps are
`forbidden` on both sides: the principal lacks `policy`), `test_t07_w6b_mcp.py` (21 passed), ruff, format, mypy,
`doc_pages --check`. To do, in order:
1. `tests/test_t07_w5e_application_results.py`: the three new `$defs` in its list, `SNAPSHOT_X06` rows for the four
   tools, response fixtures (`scripts/t07_schema_fixtures.py`) for `grant_result`, `revoke_result`,
   `ambient_pressure_result`.
2. The surface move: re-pin `X06_SERVED_SHA256` (`tests/test_t08_w2_surface_digest.py`, the decomposition test's tool
   list gains the four), `scripts/m07a_rc.py` c_12 (`D_12`, `X06_FILE_SHA256` gains the four texts, the tool-count
   text), the support envelope (`benchmarks/t08/support_envelope.yaml`, 39 operations, A20) and
   `docs/support-matrix.md` (`scripts/t08_support_matrix.py`), the two `message_entry` fixtures' catalogue sha256.
3. Conformance (`tests/test_t07_conformance.py`): switch the project's administration on and run
   `administration_requests()` on all six clients with a principal holding `policy` (or as refusals); the CLI G14
   scenario (`tests/test_t07_w5b_cli.py`).
4. `tests/test_x06_administration.py`: E-X06-16 (switch off: each write `unsupported administration_disabled`, file
   bytes unchanged, one `refused` row; every committed policy fixture round-trips to its `policy_sha256`), E-X06-17
   (case table; 1000 random (caller, request) pairs through `delegation_refusal`), E-X06-18 (token on the next REST,
   MCP stdio and MCP HTTP call; replay `token: null`; no `prt_` in `project.sqlite3`, its WAL, the policy file, logs),
   E-X06-19, E-X06-20 (in-band revoke; 10 concurrent grants plus one CLI grant), E-X06-21 (one `allowed` row per write;
   the CLI fixture).
5. The surface suites, `test_x06_*`, MSG and doc-page tests; the bundle gate (63, 60, `b42b1ec439d1683c`); F0.

## X06-WO4b (WO4 finished), 2026-11-27

Commits: `ad7f28b7` (R4-G3 rows, `$defs`, fixtures), `822d1362` (surface move, support envelope), `a8e2a5bf`
(conformance, CLI G14), `86e31d44` (`tests/test_x06_administration.py`), `6c540e5a` (MSG fix), `81243506` (E501).

- **Surface.** `X06_SERVED_SHA256` = c_12's `D_12` = `d0f0c8b7…` (35 tools; `4a80f77f…` at WO3); `without_x06` still
  gives F3's `f7ec3c94…`. `X06_FILE_SHA256` pins the four texts. R4-G3: `SNAPSHOT_X06` gains the four rows
  (`get_policy` `e3711772…`, `grant_capability` `0cd20320…`, `revoke_capability` `52cdce3f…`, `set_ambient_pressure`
  `5b609610…`); no earlier row moved. Envelope: 39 operations (A20), the `Administration` protocol in the
  interfaces row; `docs/support-matrix.md` regenerated.
- **DECISION WO4b-1. U08 follows the lifted limitation** (WO2-9's precedent): U08 no longer names in-band policy
  administration, and `test_u08_no_operation_administers_policies` goes with it (its premise is what R-110's lift for
  D5 reverses). Alternative: keep the test (it passes: no operation has its five names). Reversible by: reverting
  `822d1362`'s two hunks.
- **DECISION WO4b-2. E-X06-16's "every committed policy fixture".** The repository commits no `project-policy.json`
  (X04 A11 found the same). The test takes the policies the operator commands write (init, two grants, one with
  expiry and note, an ambient declaration): each re-serializes to its bytes and `policy_sha256`, has no
  `administration`, gains that member alone when switched on and its bytes back when off. Alternative: commit policy
  fixture files. Reversible by: adding them to the test.
- **DECISION WO4b-3. Masking a grant's random draws.** `stable_administration` now recognises a grant result as an
  object holding both `capability` and `token` (was: `status` granted/replayed), so the `missing_status` invalid
  fixture is masked too; the fixture generator's `stable`, the conformance `stable` and the CLI test's `clockless`
  apply it first. Inert on every earlier fixture (none has a `token` member; measured: all regenerate `same`).
- **DECISION WO4b-4. Conformance.** The template policy carries the switch; `_administration` runs nine steps after
  `_solve_policies` (read; ambient set and replay; grant, replay with `token` null, `capability_exists`; revoke,
  `capability_not_found`; ambient cleared). The local owner succeeds; the grant clients hold no `policy` and are
  `forbidden` on all nine (as `assess_rights`, F3 WO5b-7). The policy ends as it began.
- **Fix (MSG).** `set_ambient_pressure` put a coded `StoreError`'s `str()` (the layered text) in its ApiError;
  `test_no_handler_turns_a_layered_error_into_a_document_by_str` caught it. Now `args[0]`, the machine message.
- **Found, pre-existing (not fixed).** `tests/test_x06_solve_policies.py::test_q7_a_lowered_budget_run_verifies_and_
  reproduces` fails when run in one process after `tests/test_t07_w5e_application_results.py::test_the_fixtures_are_
  what_real_responses_emit_today`: `t07_schema_fixtures._pin_threads` sets the thread pins in `os.environ` for the
  rest of the process, so the reproduce is `exact_replay`, not `compatible_reproduction`. Reproduced at `4ca7ce3c`
  with those two tests alone (1 failed, 1 passed); passes alone and with `tests/test_x06_*.py` (87 passed). For WO5
  or the reviewer: scope the pins (monkeypatch) in the generator's callers.
- **E-X06-17 generated pairs:** 1000, seed 20261127, 471 granted, 529 refused; `delegation_refusal` is `None` iff
  D5.3's rule holds (asserted both ways).
- **Review gate count.** `test_every_description_is_reviewed_by_both_lanes` pinned 31 MCP operations and so failed on
  the count; it reads 35 now and fails only on the open reviews: 22 items, design-lane and human for each of eleven
  texts (`commit_change`, `preview_change`, `list_branches`, `create_branch`, `delete_branch`, `register_solve_policy`,
  `get_solve_policy`, `get_policy`, `grant_capability`, `revoke_capability`, `set_ambient_pressure`).
- **Final battery at `c2164962`** (logs `~/.cache/line06/x06wo4b/`): surface suites 2375 passed, 28 skipped, 2 failed
  (the Q26 STOP and the review gate); `test_x06_*` + MSG + doc pages 276 passed, 3 xfailed; ruff, format, mypy clean;
  bundle gate 63, 60, `b42b1ec439d1683c`; F0 PASS (M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42).

