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
- **D-21 — `pinned_program`'s memo (§5.5 "memoising the packaged scripts' hashes") is a module `@functools.cache`.**
  T07 G20 lists every such process-global: entry added to `tests/data/t07_global_state_allowlist.json` (immutable
  package files, one entry per packaged child script: today `child.py` alone, after the review's ruling 1) and the
  pinned per-pattern count 35 → 36 (unchanged by the retirement). Alternative: no memo (hash two files
  per backend). Reversible by: drop the decorator and both edits.

## WO-5 (the warm reactor)

- **D-22 — G5's second inlet sequence.** The note's two sequences are one: `g12-real-loop-v3.json` `calls[*]` and
  `trust-region-study-real.coupling/S0.json` iterations carry the same four experiment keys (`47f845db…`,
  `1b515243…`, `8ff4aa23…`, `7128da88…`; both are the v3 loop cold from (0.15, 80 K)). → The second sequence is the
  same study's `cand-C1-P1.json` (v3, 4 iterations, T_in = 653.15 K, distinct keys, recorded outlets), so G5 still
  measures 8 distinct inlets. Alternative: the 4 inlets twice, or a `poll-preheater` candidate. Reversible by:
  `SEQUENCES` in `benchmarks/x02/g5_warm_reactor.py`. A control recomputes v3's request (inputs and key) at every
  inlet, so each is the recorded one bit for bit.
- **D-23 — `WarmReactor` overrides `_window` as well as `outlet`.** A cold call passes straight through to the
  base's `_window`; a warm one runs `_warm_window`. This reuses the base `evaluate` whole (its `model_exception`
  window, the four acceptance clauses) for both chains instead of copying it; the note's "on the cold path `outlet`
  is the only override" holds in effect (a pure delegation), and G5a proves the cold outlet bitwise v3's.
  Alternative: copy `evaluate`'s post-processing into `evaluate_w`. Reversible by: `child_warm.py` (a new
  `runner_sha256`, so a new provisional variant).
- **D-24 — A non-finite warm outlet falls back** (`fallback_from: "nonfinite"`): D7's "any refusal", and the cold
  path refuses there too. Alternative: let `nonfinite_screen` refuse it without fallback.
- **D-25 — `diagnostics.start`.** `warm_stages` is a copy of the warm chain's stage records (plus its
  `model_exception` record on a fallback from one); on a warm `outlet` it duplicates `stages`. `start` is null on a
  cold request; `profile_sha256` is null on every non-`outlet` answer.
- **D-26 — A base that fails the pin.** Run as a script: exit 72 before the request is read (the launcher tolerates
  the broken pipe). Imported (tests): `BaseMismatchError`, never `os._exit`.
- **D-27 — G5b's metric, concretely.** ξ is taken twice, as N₂ consumed and as NH₃ made / 2 (per tube, from the
  tube inlet the child saw); the max covers both. n_tot = Σ|n_out|. Walls are the child-measured
  `execution.timing.wall_s`.
- **D-28 — G5d's `job_id = (i)`** is resolved as `declared_coupled_start` resolves it (`job_coupling_start` +
  `external_starts` over the project's store), with `run_revision_session` + `LiveExperiments` as g12 drives the
  route, minus the job wrapper.
- **D-29 — Stopped before registration (escalated, not decided).** G5 at commit `69c4a24d`
  (`evidence/X02/69c4a24d…/g5abc-*.json`): (a) the cold variant's `tube_outlet` is bitwise v3's recorded one at all
  8 inlets (inputs equal v3's recorded requests; keys differ only by the environment fingerprint). (b) every warm
  call accepted, `used` 8/8, no fallback; rel max **1.92e-7** (g12 k = 0, ξ by N₂), 1.05e-7 (P1 k = 0), the other
  six ≤ 8.9e-8 — the note's "pass with a manifest note" band, but registering `max(measured, 1.56e-8)` = 1.92e-7
  against `precision_floor_rel` 1e-6 breaks I3's "at least one decade below". (c) warm/cold wall 1.53, 2.03, 1.85,
  4.60 (g12) and 2.93, 0.84, 0.37, 0.93 (P1); totals 287 vs 133 s and 383 vs 420 s, i.e. **21 % slower overall**,
  not 10–15 % faster: S1 is gone, but the warm chain ran round 2 at 6 of 8 inlets (cold 4 of 8) and its
  certificates ran longer, which outweighs S1's ~6 s (measured under ~22 load from other users, two workers).
  The variant is not registered and G5d is not run; both wait for the design lane (§6 stopping rule spirit, Q1).

## WO-6 (close-out after the review)

- **D-30 — G5d on v3 (S-2) gets its own script, `benchmarks/x02/g5d_v3_loops.py`.** Ruling 1 retires
  `g5_warm_reactor.py` (it imports the warm child), so the v3 runs need a script that does not. It keeps the retired
  script's run helpers (`_run`, `_bound`, `pinned`, `Counted`) verbatim, runs (i) cold, (ii) restart from (i), (iii)
  the neighbour SPEC-S3-T 673.15 → 675.15 K (the handoff's edit) cold and warm from (i), all on v3 with cold
  experiments, and evaluates §7 G5 (d)'s criteria beside the measurement (exit 1 if any fails). Job ids 21–24 and a
  fresh store, so nothing is a cache hit from G5e. Alternative: run the retired script's `loops` from `005d206f`
  with v3 substituted (not reproducible from a commit). Reversible by: deleting the script and its record.
- **D-31 — Where the G5d record lives.** `evidence/X02/<C>/g5d-v3.json` with its own `index.json`, where C is the
  commit the script ran at; beside `evidence/X02/69c4a24d…/` rather than inside it, whose index pins the commit
  69c4a24d it was measured at. Alternative: add it to that index with a second commit field.

- **D-32 — G5d (iii) fails "warm takes fewer outer iterations" (escalated, not decided).** `evidence/X02/dcb499ee…/
  g5d-v3.json`, v3, cold experiments, neighbour SPEC-S3-T 673.15 → 675.15 K. (i) cold VERIFIED, 4 outer, w =
  (0.168388, 78.670 K), 193.7 s; (ii) restart VERIFIED, 1 outer, w₀ bitwise, 1 call, 24.7 s; (iii) cold VERIFIED 4
  outer (181.5 s), warm from (i) VERIFIED **4** outer (222.7 s); Δû 3.76e-4 ≤ bound 1.64e-3 (holds); the edit moves
  û by 0.137 = 83.7 bounds. Trajectories: cold (0.15, 80) → (0.1629, 79.75) → (0.1696, 75.96) → (0.1672, 77.30);
  warm (0.1684, 78.67) → (0.1675, 77.14) → (0.1673, 77.25) → (0.1672, 77.30): the warm start begins about 2× closer
  and stays closer, but meets the tolerance at the same k (B₀ = −I, D3, carries no curvature from the source). §7
  G5 (d) says "If not, escalate: a premise has failed" — Part A's neighbour claim ("restarts near its fixed point")
  holds for distance, not for iteration count. ADR 0070 Acceptance evidence and Consequences bullet 1 are left
  unamended until a ruling. Default I would take: record (iii) as measured, qualify Consequences bullet 1 to "a
  neighbouring revision starts near its fixed point; on the real loop it took as many outer iterations as cold (G5d
  (iii))", and not gate on iteration count.
  *Ruling (design lane, main `c054530b`, 2026-11-07):* the criterion stays in the note and the manifest as **failed**
  (not removed, not relaxed); the premise (an outer start near a neighbour's fixed point saves outer iterations) is
  recorded false for this edit; ADR 0070 withdraws the neighbour-speedup claim; the package's claims rest on (ii) and
  identity, as D-29 did for the warm reactor. Rejected: dropping the criterion from the gate (narrows a gate after it
  failed); holding X02 for a new design. Reversible by Frank's X02 Q7. Carried out in WO-7: note §7 G5 (d)(iii) A-10,
  ADR 0070 Consequences bullet 1 and Acceptance evidence (status stays Proposed), manifest check
  `G5d_iii_iterations` with result `fail`.

## Tokens for MSG's catalogue (§5.9; `wp/MSG` not merged)

| Token | Family / kind | Emitted at |
| --- | --- | --- |
| `warm_start_source_missing(<job>)` | api_error message / `input` | `application/admission.py` `admit_warm_start` (A1) |
| `warm_start_unit_unknown(<unit>)` | api_error message / `input` | `application/admission.py` `admit_warm_start` (A2) |
| `warm_start_rejected(coupling_integrity\|coupling_compatibility\|coupling_opening\|external_integrity\|external_compatibility)` | notice | trace `initializer_rejected` only (`application/coupled_run.py` `solve_coupled`, `_rejected`); the `solve-path.json` `warm_start.coupling` / `.external` records carry the bare check name (review S-1); `route` is a record reason only (no trace event) |
| `coupling_warm_start(present\|absent)` | notice | trace `initializer_candidate` (`application/coupled_run.py` `solve_coupled`) |
