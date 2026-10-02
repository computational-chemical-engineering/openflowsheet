# ADR 0024 — Compatible warm starts are opted into by policy, chosen from the revision lineage's latest VERIFIED state, checked like every candidate, and recorded inside the bundle; the application contract is unchanged

**Status:** **Accepted, 2026-10-02**, with T08's tested evidence (`evidence/T08/67c66d98587f23bd7dfe8da28a8facccc92da21e/manifest.json`). Frank's decisions: F2 "build first" (2026-09-29), which this ADR answers; B50 amended twice to the carried agent surface (R-134, 2026-10-01; R-144, the package version, 2026-10-01). Proposed 2026-09-29, taking effect when committed with its specification. Register R-124.
**Date:** 2026-09-29
**Author:** design lane (`specifier`), T08 build-first pass. Brief `docs/briefs/T08-build-first-spec.md`.
**Normative text:** `docs/derivations/T08-build-first-spec.md` Part B (§B1–§B5) and assertions T08.B40–B51.
**Amends (additively):**
- K03 §10.1 (source 2 on the revision path, where it was "recorded absent");
- the revision path's use of `SolvePolicy.initializer_chain` (an empty chain keeps today's behaviour);
- `solve-path.json` (one optional member, a rerun input with no schema, T07 ruling round 2 F1.2);
- `run.identity.r0_projection` (one branch);
- the application policy registry (`T08-warm-v1`).

**Reverses:** nothing. ADR 0019 is **not** amended. No frozen schema changes.
**Affected requirements:** V13 (e) via T08.A71; D01/D06 (initialization); D20 and blueprint §8.3 (new fields classified; replay from the bundle alone).
**Affected packages:** T08 (builds it), T07 (runner, rerun, identity: new branches only), M03 (sweeps, the natural consumer; the explicit form is deferred to it).

## Context

Blueprint §7.4 lists compatible warm starts as the second initialization source, and §14.3 bullet 3 names them. The T08 release spec reads V13 (e) accordingly (R-119): K02's warm-start cache does not count. The blueprint also says warm-start history is an "opt-in input with hashes" (line 253) and is "transferred through an explicit state mapping" (line 189). Frank's F2 (2026-09-29): build it in T08. T03 §5.1 built its opening checks for this source.

## Decision

- **D1. Opt-in by policy.**
  - `T08-warm-v1` is `T06-revision-v2` with `initializer_chain = ("compatible_warm_start", "traversal-G0-v1")`, and is offered.
  - Every existing policy keeps `initializer_chain = ()` and today's behaviour exactly.
  - A `user_start` (source 1, internal harnesses) wins, and the chain is not consulted.
- **D2. Selection `store-latest-verified-lineage-v1`.**
  - The candidate is the ended solve job with the highest ordinal, other than the current one, whose revision is the target or an ancestor of it, whose bundle holds `solution-state.json`, and whose certificate is `VERIFIED`.
  - The application layer performs the lookup, and the orchestrator never reads the store.
  - Absent is recorded, not failed.
- **D3. Compatibility and checks.**
  - Compatibility is equality of the candidate's `variable_ids` set with the target's `spec.variable_ids` (the explicit state mapping is the identity on ids).
  - The checks run in the order integrity, compatibility, bounds, evaluation, opening:
    - **integrity:** T07 F1.4's consistency;
    - **bounds:** projection, logged, not a rejection;
    - **evaluation:** every unit `ok`;
    - **opening:** T03 §5.1's `check_opening`.
  - Any failure is `initializer_rejected` with `warm_start_rejected(<check>)`, and the next source follows. The run never fails because of the warm start.
  - The candidate supplies only `x₀`. Nothing overwrites a specification, bound, tolerance or check policy.
- **D4. Records.**
  - **Trace:** existing event kinds only, with messages `compatible_warm_start(present|absent)` and `warm_start_rejected(<check>)`.
  - **Provenance:** `branch_provenance[0].initializer_source = "compatible_warm_start"`.
  - **Bundle:** a `warm_start` member of `solve-path.json` (spec §B2's table: `record`, `selection`, `status`, `reason`, `source_job_id`, `source_revision_id`, `candidate`, `projections`). It is written iff the policy names the source and no `user_start` was given.
  - **R0:** status, reason, selection, the candidate's ids and the projected ids. Values are R1/R2 under ADR 0007 D2, digests are shape-only, and job and revision ids are provenance.
- **D5. Replay.** A warm-started run reproduces from its bundle alone: the rerun takes the candidate from `solve-path.json`, makes no lookup, re-runs the checks and writes the same record.
- **D6. The contract.** Unchanged. The warm start is reached through `solve(revision_id, "T08-warm-v1")` or `submit_job` with that `policy_id`, on every transport.

## Alternatives considered

- **An explicit, request-named source in v0.1.** Deferred, not rejected. It needs a `solve_body` member (`job.schema.json`, `additionalProperties: false`), which the MCP `submit_job` tool exposes, so T08.A49's surface would move, needing an ADR 0019 amendment and a V17 re-run. See "Deferred" below.
- **A new bundle file `warm-start.json`.** Rejected: `artifact_ref.kind` is a producer-closed enum in an MCP-exposed schema, so a new kind is a surface change. `solve-path.json` already records how a solve was set up and has no schema.
- **Content-addressing the source outside the bundle.** Rejected: a bundle must replay alone, including in a fresh environment (T08.A45).
- **Filtering the lookup by compatibility.** Rejected: an incompatible latest state would then never be seen, and a topology edit would give a silent cold start instead of a typed rejection.
- **Falling back to a cold start after an accepted warm start fails.** Rejected as a new recovery edge. The policy's existing edges, including ADR 0015's traversal restart, already apply.
- **Overwriting fixed coordinates with the target's specified values.** Rejected: the specification rows enforce the problem already, and the overwrite would be an unlogged start edit that serves no check.
- **Default-on warm starts.** Rejected: the blueprint makes history an opt-in input, and default-on would make repeated solves in one project depend on the store's history.
- **K02's warm-start cache.** Not this mechanism (R-119).

## Deferred: the explicit form (ADR 0019 amendment text, for v0.2)

> *ADR 0019 Amendment 3 (proposed for v0.2).* `job.schema.json#/$defs/solve_body` gains the optional member `warm_start: {"job_id": <job id>}`. When it is present, the named job's `solution-state.json` is the source-2 candidate (`selection = "explicit-v1"`), with ADR 0024's checks and records unchanged. A named job that does not exist, or has no solution state, is `invalid_request(warm_start.job_id)` at semantic admission. The member enters `request_sha256`. MCP, HTTP and CLI gain it through the shared schema. T08.A49's schema digest moves, and V17 is re-established per F5.

## Consequences

- V13 (e) becomes decidable (T08.A71 on B40–B51).
- Sweeps (M03) get warm starts by naming a policy. The explicit form waits for v0.2.
- A warm-started solve on a multi-root flowsheet may reach a different certified root than a cold one. That is a change of method (the start), recorded in `branch_provenance` and the bundle, and never a change of problem.

## Migration

None. Existing bundles have no `warm_start` member, so the new R0 branch is inert and every registered key is byte-identical (B49, T08.B26). No store migration is needed: the lookup reads existing tables (`jobs.ordinal`, `revisions.parent_revision`, `artifacts`).

## Acceptance evidence

- B40–B49 pass in `./scripts/check.sh` on x86-64 and aarch64.
- B50: T08.A49's digests unchanged.
- `verdict` judges B51 (T08.A71) at the RC.
- A design-lane `reviewer` pass on replay identity and the chain.
- `review.numerical` and `review.process_model` are not set by this ADR.

## Accepted (2026-10-02)

Recorded by the build lane (brief `docs/briefs/T08-close.md`, item 8) with T08's tested evidence at `C` = `67c66d9`: B40–B50 pass in the T08 manifest (B50 as amended by Frank, R-134 and R-144), and `verdict` judged B51 / T08.A71 met (`docs/reviews/T08-verdicts.md`, V13 (e)).
