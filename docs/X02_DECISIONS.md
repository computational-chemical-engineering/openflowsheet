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

## WO-3 (outer start)

- **D-9 — The inner members when no x₀ source was declared.** An iterate-only declaration under a policy whose chain
  is empty records `{status: absent, reason: not_declared}` (§5.7) with `selection: explicit-v1` (the declaration's
  form; no selection rule ran) and no candidate. On `legacy_eo` an iterate-only declaration records the whole member
  `rejected` (`route`) the same way (§5.2 "the whole member"). A declared `job_id` whose k = 0 inner solve never
  consulted it (a k = 0 plan refusal, structural, so a cold run refuses too) records `absent` with reason `null`.
  Alternative: the lineage `selection`. Reversible by: the `warm is None` block in `run_revision_session`.
- **D-10 — G3 (c)/(d) "byte-identical to J_c's".** J_c ran its experiments live (`cache_hit: false`); every later
  cold coupling in that project is served them from the store (`cache_hit: true`), so no later run can be byte-equal
  to J_c itself. The reference is J_c′, a second cold run under the same cache state; the (c)/(d) records are
  byte-equal to it, and their evaluation counts equal J_c's. Alternative: separate projects (wall times in the
  attempts then differ). Test-only; `tests/test_x02_wo3_outer_start.py`.
- **D-11 — G3 (c) needs a loop whose inner solve fails in the bounds.** The note's premise "start from (0.95, −50)"
  does not hold for the registered stand-in loop: a 12-point grid over the bounds (X ∈ {0, 0.5, 0.95} × ΔT ∈ {−50, 0,
  100, 250}, all four corners included) opens every time (3–4 inner iterations). G3 (c) takes the loop with its H₂
  make-up lowered 0.74625 → 0.725 mol/s: X = 0.95 then needs more H₂ than the loop holds (inner fails), while
  `coupling.initial` (0.15, 80) and the fixed point X = 0.25 do not (cold VERIFIED, 2 outer iterations). The test
  proves both inner outcomes first, without the feature. **For the reviewer** (premise check). Test-only.
- **D-12 — Trace messages (§5.9).** On the job's trace (the one the inner solves extend), existing event kinds:
  `initializer_candidate` `coupling_warm_start(present|absent)` (absent iff the record is `absent` at resolution),
  then `initializer_rejected` `warm_start_rejected(coupling_…)` before the cold coupling's events. The bundle's
  `solve-events.json` is the final inner run's trace and is unchanged, so no identity moves.
- **D-13 — Integrity is the note's three checks** (schema `#/$defs/coupling`, `outcome == CONVERGED`, last `w` 2·n
  finite numbers), not also `coupling_record_problem`'s per-request key recomputation (the request keys play no part
  in w₀). Alternative: add it (stricter, a few ms). Reversible by: `job_coupling_start`.
- **Observation (not a choice), for the reviewer.** `couple` opens at u = w₀/scales (§5.4), so `iterations[0].w` is
  fl(fl(w₀/s)·s): a declared iterate can move by an ulp (0.95 → 0.9499999999999998 at s = 0.1). A job source's w is
  itself u·s and round-trips bitwise (G3 (a) measured). Keeping u = w₀/s as the note states.
- **D-14 — The outer start's `initializer_rejected` producer joins row E9 of `docs/recovery-edges.yaml`.** The note
  (§5.9) puts `warm_start_rejected(coupling_…)` on `initializer_rejected` events; T08 A33's bijection requires every
  producer of that kind in a row. It is E9's edge (a start rejected → the next source, here `coupling.initial`), so
  the label `event:initializer_rejected@openflowsheet.application.coupled_run.solve_coupled` is added to E9 with
  G3 (c)/(d) as failure and unchanged-physics tests. Alternative: a new row E14. **For the reviewer** (the inventory
  is a T08 release-spec artifact).

## WO-4 (external plumbing)

- **D-15 — Where a missing or mismatched exported profile is caught.** In `OutOfProcessBackend` (`_exported`), so the
  `protocol_error` is the attempt's own execution status (retried once, as every `protocol_error`), and its
  envelope a refusal; the runner then reads the checked file, stores it and sets `result.profile_sha256`, re-checking
  the hash (a change in between is an internal error). The note places the check "in the runner"; status, record and
  result are the same. Reversible by: `_exported` / `ExperimentRunner._export`.
- **D-16 — `external` statuses the note leaves open.** A source record that fails the coupling integrity check makes
  each start-capable unit `rejected` (`external_integrity`); no coupling record is `absent` (`no_profile`). `units`
  lists every external unit of the target (a cold-only one `absent`, `variant_cold_only`); the member is written iff
  ≥ 1 is start-capable. Checks in order: capability, source entry/hash, variant (`external_compatibility`), store
  bytes (`profile_unavailable` / `external_integrity`). Reversible by: `external_starts`.
- **D-17 — The chain after a rejected opening** restarts from the accepted k = 0 profiles (the rejected opening ran no
  experiment, so this is inert; written out so it stays so).
- **D-18 — Trace.** A rejected k = 0 child start records `initializer_rejected` `warm_start_rejected(external_…)` from
  the same producer (E9, D-14).
- **D-19 — G0 key recomputation is a CI test** (`tests/test_x02_g0_experiment_keys.py`), not a script: 163 recorded
  requests (`benchmarks/m05/records` 115, `benchmarks/m07/journey` 48), 0 differences. `benchmarks/m02/` holds no
  request document (its g10 records carry result keys only).
- **D-20 — `Experiments.evaluate(…, start=None)`.** Implementers must accept the keyword (mypy holds the protocol):
  `benchmarks/m02/g12_real_loop.py`'s `TimedExperiments` now forwards it. `solve_coupled` passes `start` only when one
  is set, so a test double without it still runs every cold variant.

## Tokens for MSG's catalogue (§5.9; `wp/MSG` not merged)

| Token | Family / kind | Emitted at |
| --- | --- | --- |
| `warm_start_source_missing(<job>)` | api_error message / `input` | `application/admission.py` `admit_warm_start` (A1) |
| `warm_start_unit_unknown(<unit>)` | api_error message / `input` | `application/admission.py` `admit_warm_start` (A2) |
| `warm_start_rejected(coupling_integrity\|coupling_compatibility\|coupling_opening\|route\|external_integrity\|external_compatibility)` | notice | `solve-path.json` `warm_start.coupling` / `.external`; trace `initializer_rejected` (`application/coupled_run.py` `solve_coupled`) |
| `coupling_warm_start(present\|absent)` | notice | trace `initializer_candidate` (`application/coupled_run.py` `solve_coupled`) |
