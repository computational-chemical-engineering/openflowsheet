# Brief — T07 review: job lifecycle, authorization, HTTP/MCP bindings, revision runs

**To:** `reviewer` (design lane). **From:** build lane, 2026-09-27. **Branch:** `wp/T07` at `1ed044d`
(base `main` at `78d3647`). **Deliverable:** `docs/reviews/T07-review.md`, with findings ranked
M (must fix before merge) / S (should) / N (note). For each finding give the file:line, the failure
scenario, and the smallest fix. Write no production code and do not commit. The build lane fixes, then
writes the evidence manifest.

## 1. What was built against what

- **Design:** `docs/design/T07-jobs-and-bindings.md`, the architect's note plus ruling rounds 1–4 at
  its end, amended in place where marked.
- **ADRs:** 0019 (application contract v1, approved by Frank; Amendment 1 is Proposed and held — see
  §5), 0020 (job execution and revision runs, amended), and 0002 Amendment 1 (integer canonicity).
- **V17 specification:** `docs/derivations/T07-v17-tasks-spec.md`, with its twin
  `docs/derivations/scripts/t07_reference.py` and ruling round 3.
- **Build-lane decisions and their reasons:** `docs/T07_DECISIONS.md`, append-only. Several entries
  say "for the reviewer".
- **Measurements:** `docs/t07-measurements.md`.
- **Diff:** `git diff 78d3647..1ed044d`: 200 files, 52 of them under `src/` (~11k lines). Main new
  modules under `src/process_runtime/application/`: `store.py`, `authz.py`, `local.py`, `contract.py`,
  `types.py`, `operations.py`, `projection.py`, `admission.py`, `policies.py`, `revision_run.py`,
  `serving.py`, `jobs/{model,runner,executor,worker,interrupt}.py`, `bindings/{http,mcp}.py` and
  `bindings/descriptions/`. Changed existing modules: `canonical.py`, `validation.py`,
  `orchestrator/trace.py` (the interrupt hook), `run/{bundle,identity,session,solution_state}.py`,
  `verify/failure.py`, `units/__init__.py`, `revision_binding.py` (ModelSignature).

## 2. What was run, with numbers

- **Gate:** `./scripts/check.sh` green at `1ed044d`, 5929 passed. Identity equals the W0.1 baseline
  at every merge: K05 `9a7b4e6d…`, T02 floats `9a8a5baf…`, structural `915c97e8…`, keys `t02`…`t06`.
- **Duplicate jobs (G4):** 2 processes × 25 threads with one key give 1 job and 49 replayed; a
  mismatched body gives 409; the same `job_id` survives a restart.
- **Cancellation (G5):** cooperative cancel takes 0.108 s, forced 0.610 s.
- **Determinism:** G6 and G7 (inline vs process, parallel vs serial) are byte-equal.
- **Overhead (G18):** job overhead 0.501 s; the interrupt hook costs 0.1–0.35 % of a solve.
- **Global state (G20):** clean. G19: licences clean.
- **Authorization and bounding:** G11 is 1280 cells by dispatch plus 2352 injection decisions. G13
  checks more than 5000 bounded strings.
- **Transport conformance (G14):** 193 steps × 3 transport pairs, 0 disagreements.
- **V17 reference runs (G16-b):** 40/40 clean.
- **ADR 0002 A1:** J10–J17 pass, and 44 of them fail on the base rule.
- **Revision runs (G8):** 47 bundles, all passing `verify_bundle` and rerunning to MATCH. G9 holds;
  28 `validate()` results moved DRAFT → READY, none of them in any key.
- **V17 agent campaign:** running now (30 sessions, pinned `claude-sonnet-5`). It is evidence for
  `verdict`, not for you.

## 3. Where the build lane is least sure — look hardest here

1. **Identity-bearing changes:**
   - `canonical.py`: W2d (Q29 entry refusal), W5d (lone surrogates), W5g (ADR 0002 A1).
   - `validation.py`: W3b (F5 fallback, R3 provenance), W3f (tie by kind).
   - `run/identity.py`: the r0 branches for `execution-plan.json`, `solve-path.json` and
     `solution-state.json`.
   - `verify/failure.py::initializer_bundle`.

   Is every "inert for registered results" claim actually proved by a test that would fail?
2. **The solve loop:** the `INTERRUPT_CHECK` hook in `Trace.record` and `JobInterrupted(BaseException)`.
   Can an interruption become a numerical outcome, a certificate or a failure bundle? The known latent
   path is CasADi turning a callback's BaseException into a RuntimeError (decisions log, W4b). The
   known limitation is that a region's own events are lost on interrupt.
3. **Authorization (§10):**
   - Is authority taken only from the credential?
   - `local-owner` is reserved.
   - Cancelling another principal's job needs `policy`.
   - Revocation takes effect on the next call.
   - HTTP 401 for a revoked token is not audited (W6e-Q1).
   - `worker.log` is readable through `get_artifact` (W6e-Q2, kept).
   - MCP refuses to start on a bad credential.
4. **"Ordinary solve tools cannot weaken verification":** check_tolerances only tighten, and a tightened
   check gives RELAXED (R5). Is there any path that loosens?
5. **Idempotency:**
   - The ledger scope is (principal, operation, key) plus the request hash.
   - The K06 façade changed behaviour in three ways: a mismatched body is refused; a taken revision id
     with identical content is now `rejected`; `remove` under an absent parent is a no-op.
6. **Process executor:**
   - Fencing, orphan recovery (`owner_lost`), `worker_lost`.
   - The supervisor does not signal at the deadline (W4c-Q1, amended in §8.2).
7. **Replay:**
   - `reproduce`'s rerun follows the recorded route.
   - The `solve-path.json` tamper check (W3-Q4).
   - The forged bundle (Q26 ii) over every transport.
8. **The MCP inputSchema flattening** (`body.oneOf`) and the consumer-reading `outputSchema` (J5).
   Does the published schema stay faithful to what `dispatch` enforces?
9. **The V17 scorer** (`benchmarks/t07/v17/scorer.py`). The gate is "zero false verification", so a
   scorer that under-counts is the worst defect this package could ship. Check the agent and system
   counters, the effects predicate, the corrected assumptions A6/A8, and `_exact`.

## 4. Do not spend time on

Style and formatting (ruff and mypy are clean). The ADR 0008 A1 wording itself. Re-deriving SYN-001 or
T06 results. The tool descriptions' prose quality (a separate design-lane text review plus Frank's
human review). Performance beyond G18.

## 5. Context

- **Held:** ADR 0019 Amendment 1, a tenth frozen schema `application-results` (W5e, branch
  `wp/T07-w5e`), is held for Frank's approval and is not merged. Review it only if time permits.
- **Open items with defaults, not blocking:** R4-O1, R4-O2, R4-O3; S-R5; S-G; F6 (a fallback that is
  not needed); R-088 Q24/Q25 (a K04 amendment).
- **Human review:** pending (Frank). Never set `reviewed` yourself.
