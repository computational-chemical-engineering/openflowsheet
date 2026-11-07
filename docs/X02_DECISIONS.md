# X02 build decisions (build lane)

Choices the design note (`docs/design/X02-warm-starts.md`) and ADR 0070 leave open, each isolated and revertible.
Format: question → choice; alternative; reversible by; commit. Batched for the package's one ruling round.

## WO-1 (Part C)

- **D-1 — Where the k = 0 record is captured.** → In `solve_coupled`'s `solve_inner` closure, on every call with
  `start is None` (only k = 0 calls it so; a plan refusal there sets `None`), so WO-3's restart (`couple` twice) keeps
  the record of the coupling that counted without further code. Alternative: a hook in `couple`. Reversible by:
  revert `30b921a3`.

## WO-2 (contract, explicit x₀)

- **D-2 — Admission order of A1/A2.** → Step 6a: after the policies (steps 4–6), before the budgets (7–8): the
  request's own members first, then the caller's limits. A1 before A2. Alternative: before step 4. Reversible by: move
  the block in `admit_solve`.
- **D-3 — Register number of the surface link.** → `R-950`, provisional (ADR 0070 numbers register entries on
  acceptance; R-942…R-949 are held by `wp/MSG`/`wp/RP`). **Merge hazard:** `wp/MSG` carries its own link `c_4`
  (R-943, `without_msg`, `eaff4585…`). Whichever merges second re-chains as `c_5` with the combined tree's digest and
  re-takes the R4-G3 snapshots of the job operations. Commit `fe563df4`.
- **D-4 — `profile_sha256` classified in `benchmarks/m02/numerical_policy_external.yaml`.** → `exact_sha256` gains it
  (the schema member forces a classification, `tests/test_m02_schemas.py` G1). The list is audit-only; the run time
  reads `rules` only, so no comparison moves. Commit `fe563df4`.
- **D-5 — The explicit source on the legacy route.** → `solve-path.json`'s `warm_start` is the x₀ record
  `{selection: explicit-v1, status: rejected, reason: route}`, written by `run_revision_session`; no trace event (the
  legacy trace is untouched, so its events stay byte-equal to the cold run's). The `coupling` sub-record's
  `warm_start_rejected(route)` is WO-3's.
- **D-6 — An explicit source missing at run time** (admitted, then gone). → A candidate with no document, so the
  `integrity` check rejects it (recorded), never a silent cold start. Not reachable today (artifacts are not deleted).
- **D-7 — An explicit source replaces the lineage lookup** (§5.2 "Otherwise"): one candidate; when it is rejected the
  traversal follows, not the lineage. Taken as the note states it; listed because ADR 0024 D3 says "the next source
  follows".
- **D-8 — `warm_start.coupling` between WO-2 and WO-3.** → Admitted by the schema and A2, not yet read: the outer
  start, its `coupling` sub-record (including `revision_eo`'s `rejected(coupling_compatibility)` and the
  `absent`/`not_declared` x₀ member of an iterate-only declaration) and the iterate's W14-path test land with WO-3.
  Branch-internal state only; nothing merges before WO-6.

## Tokens for MSG's catalogue (§5.9; `wp/MSG` not merged)

| Token | Family / kind | Emitted at |
| --- | --- | --- |
| `warm_start_source_missing(<job>)` | api_error message / `input` | `application/admission.py` `admit_warm_start` (A1) |
| `warm_start_unit_unknown(<unit>)` | api_error message / `input` | `application/admission.py` `admit_warm_start` (A2) |
