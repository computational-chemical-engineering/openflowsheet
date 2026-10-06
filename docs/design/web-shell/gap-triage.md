# Web-shell data gaps G1–G11: triage

Build lane, 2026-09-29. The Claude Design prototype (`Workbench.dc.html`) was built from the
brief's prose excerpt (`../web-shell-design-brief.md` §6). It tags eleven places where that
excerpt did not give a screen what it needs. This note checks each gap against the full records.

**Evidence used.**
- *At `78d3647`:* the complete records emitted for NET-02, its edge-off control (`T05b-v2`),
  STR-03 and SYN-001-nominal, from the showcase extraction. They are not committed. They are the
  same record kinds a run bundle holds, so the JSON paths below apply to any bundle.
- *On `main` at `5c1f8ac`* (T07 merged 2026-09-28), through `LocalApplication`:
  - NET-02 committed (`rev-000001`) and solved (`job-000001`): `CONVERGED`, `VERIFIED`, state
    `1cf23ff0…`, the same root as at `78d3647`;
  - `validate()` and `inspect_structure` run on NET-02 and STR-03;
  - one failing solve, `SYN-001-A02-352-vapor-guess-410`, which ends `HOMOTOPY_STALLED`.

**Classes.**
- **A** — the record holds the data; the gap comes from the brief's excerpt.
- **A (main)** — reachable on `main` through T07, but absent at `78d3647`.
- **B** — the data exists inside the code but is in no record or operation.
- **C** — the data is absent or ill-defined, and needs a design-lane answer.

**Summary.**
- Most of the eleven gaps are brief artefacts, or were closed by T07 after the brief was written.
- Three gaps come from defects in the emitted records (D1–D3). All three are build-lane work.
- Five requests are made of the application contract.
- Five questions are for the design lane.

## Triage

| Gap | Class | Evidence | Action |
| --- | --- | --- | --- |
| **G1** Identity | A (main); B at `78d3647` | **Revisions:** `list_revisions` gives `revision_id, parent_revision, content_sha256, principal_id, created_at`. **Jobs:** `Job` gives `job_id, principal_id, created_at, started_at, ended_at`; `RunResult.run_id = run-<job_id>` (`run-job-000001`). **Run manifest:** `started_at`, `elapsed_seconds` (0.207 s). The certificate has `certificate_id`. The validation report's `provenance` is now `{produced_by, timestamp}` (T07 R3; at `78d3647` it did not match the schema). Certificates carry no time, by ADR 0007: time is telemetry and excluded from identity. **Note:** `commit_change` assigns `rev-NNNNNN` and replaces the document's own `revision_id` (`SYN-001-T06-NET02-r1` → `rev-000001`). | M06: the header shows `revision_id`, `content_sha256[:12]` and `run_id`. No ask. |
| **G2** Excess | A — the gap's claim is wrong | **STR-03 report:** `structural_counts` = `{equations 50, free_variables 47, matched 47, unmatched 3}`. **STR-04:** "2 certified redundant rows" (`U-FLASH:FLASH-P:inlet`, `U-SPLIT:SPLIT-P:recycle`). **STR-03 message:** "Over-specified by k means that k more equations are declared than the variables can absorb after certified redundancy". So 50 − 47 = 3 unmatched rows = 2 redundant + 1 excess. `unmatched` = (rows − rank) + (cols − rank) (`graph/analysis.py:180-185`). **Other cases:** nominal has 49/47/2 with 2 redundant rows and excess 0. NET-02 on `main` has 48/47/1 with 1 redundant row. | M06: split `unmatched` into redundant + excess. The structured source is `inspect_structure` (`excess`, `certificates`). Design Q1. |
| **G3** Candidates, links | A (truncation); B (links) | **Truncation:** the record lists all 9 candidates. `implicated_objects` = `[SPEC-heater-outlet-T, SPEC-heater-duty, heater]`. **Row ids:** they exist in `StructuralReport.candidate_specification_rows` (10 rows; `SPEC-flash-T` → `FLASH-T:vapor` and `FLASH-T:liquid`) and in `unit_degrees_of_freedom[]`. But three things are missing on `main`: (i) `inspect_structure(STR-03)` returns only `{not_run_reason: "unsupported(specification_unconsumed(SPEC-heater-duty)); …", hint: null}`, because no solve route binds an over-specified revision; (ii) the map from specification id to row id (`binding.structural_inputs`'s third return) is in no record; (iii) no operation renders an equation row. | Ask 1 and Ask 2; design Q2. |
| **G4** Per-case reports | NET-02: B at `78d3647`, fixed on `main`. STR-03: A. The U- claim is wrong. | **NET-02 at `78d3647`:** `validate` gave `DRAFT` with counts null ("flash temperature" not declared; the legacy binder cannot read a PH flash). **NET-02 on `main`** (T07 §12.4 fallback): `READY_FOR_SIMULATION`, 48/47/47/1; STR-05 gives 21 blocks, torn at S6. **STR-03 topology:** its revision document has the 7 instances `feed … purge` and the connections S1–S7 (`get_revision`). **Prefixes:** NET-02 does use `U-` ids (`U-FEED … U-SINK-P`). **Real defect D1:** STR-03's message names the over-specified unit `U-HEAT`. That is the registered SYN-001 binder's internal id (`models/syn001/flowsheet.py:54`); the revision calls the unit `heater`. `unit_degrees_of_freedom` carries both ids. | D1 (build lane) |
| **G5** Trace detail | A mostly; B (bound); C (time) | **Count:** 27 = the brief's 25 + two `attempt_opened` (seq 2 and 9); the prototype's assumption is right. **Every event** carries `residual_inf_unscaled`, `merit`, cumulative `counters`, `state_sha256` and `signature`. **Trial and step events** add `alpha`, `step_inf_scaled`, `trial_status` and `rejection_reason` (`armijo`, seq 12–13). **`linear_solve`** adds `linear{residual_normalized, u_diag_min/max_abs, nnz_L/U}`. **Attempt 1:** signature `[[U-HEAT,TWO_PHASE],[U-PHF,TWO_PHASE]]`; its opening is in certificate `branch_provenance[1]` (`eo_recovery_start`, `traversal-G0-pass8-v1`). **Recovery-off trace:** exists (control, 11 events). The contract refuses its policy: "solve policy 'T05b-v2' is registered but not offered in v0.1". **Bound hit:** `NewtonResult.blocked_by` holds the variable ids (`numerics/newton.py:593-596`) and reaches no record. **No per-event time.** | Ask 3; design Q3. M06: build the failure screen on a failure the contract can reach (see G8). |
| **G6** Certificate | A; allowance is C | **Checks:** all 144 carry `id, category, subject, value, tolerance, reference, near_threshold`. By category: residual 48, bounds_and_domain 38, material_balance 22, specification 13, independent_split 8, phase_admissibility 6, energy_balance 5, alias_certificate 2, derivative_witness 2. **`limitations[]`** names check, value and threshold for 3 entries, e.g. `residual.U-MIX:MIX-energy` −4.42e-4 against 1.01e-3 W. **Near-threshold band:** tol/10 < \|v\| ≤ 10·tol (ADR 0007 D2.4, `verify/__init__.py:100,180`); the margin is not in the record. **Scaled error bound:** it has no tolerance by design. The schema calls it "recorded evidence and never a check", and `statements[0]` says what it claims. **Allowance:** "43 coordinates, worst 1.86e-2 of its allowance" was computed by the extraction script, against `benchmarks/t06/reference_values.yaml` with T02 §6.4 allowances. No record or operation compares a run with a registered root. | M06: static text for the band and the bound. Design Q4. |
| **G7** Value provenance | A (main); the vapour-fraction claim is wrong | **Full precision:** `solution-state.json`, a bundle member on `main`, holds 47 binary64 values; `state_sha256` equals the certificate's target. **Row links:** `structural-report.canonical_matching` maps each variable to its matched row (`U-HEAT.Q` → `U-HEAT:HEAT-duty`). That is a canonical assignment under the recorded tie-break rules, not "the" equation. **Residuals:** certificate `residual.<row_id>` gives the raw SI `value` and the row scale `reference` at the final state, so scaled = value/reference. Per iteration, only the ∞-norm is recorded. **S3 split:** `phase_branch["U-HEAT:S3"]` gives it per component; the totals are 0.570044 and 36.4137 mol/s (V/F = 0.015415). **S4 and S5** are single-phase by declaration (ports `vapor` and `liquid`, `phase_capability` vapor and liquid), so their vapour fractions are 1 and 0 by definition, not computed. S1, S2, S6 and S7 are declared liquid, and the `phase_admissibility` checks pass. | M06 only |
| **G8** Failure bundle | A mostly; defect D2 | **State hash:** `best_checkpoint.state_sha256` = `601e85f0…`. **"Verified for":** `verification_scope: "unverified"`, `label: "partial"`. **Suggested actions:** `[{report_defect, requires_permission: true}]`. There is one action per outcome (`OUTCOME_ACTIONS`), so no ranking exists. **Control policy:** `T05b-v2` (the `plan_built` message). **D2:** on `main`, `replay_identity` is all `""` in every region bundle, including the `HOMOTOPY_STALLED` bundle the contract produced. `bundle_for` reads `getattr(result, "plan")`, and `_RegionView` has no such field. The run manifest beside it holds the identity (`T04-W12`, `plan_id`, `model_version`, `constants_sha256`). The revision-path certificate also has `policy_id` and `plan_id` equal to `""`. **Richer failure example:** the contract-reachable A02-352 bundle carries `inferred_causes` `phase_boundary_on_path(U-HEAT)` (hypothesis) and `supply_initial_guess`. | D2 (build lane, design-lane review). M06: take identity from the manifest until D2 is fixed. |
| **G9** Permissions | A (main) | **Rights:** `get_project` gives `principal_id`, `capability_id`, `rights` (six) and `limits`. The right each operation needs is `OPERATIONS` (T07 design §4.3), which no operation serves. **Agent history** (screen 8) needs the audit table (principal, capability, operation, outcome, `request_sha256`, effect) and the commit ledger (idempotency key). Neither has a read operation. | Ask 4 and Ask 5 |
| **G10** Unit results | A — the gap's claim is mostly wrong | **Absent quantities:** NET-02 has no pump, compressor or reactor, so it has no work and no extents. **MIX:** adiabatic, with no duty variable; its result is `energy_balance.U-MIX` (−5.8e-11 W). **SPLIT:** `r = 0.95` is a declared parameter (`instances[U-SPLIT].parameters.split_fraction`), checked by `specification.U-SPLIT.ratio.{A,B,C}`. **Duties:** HEAT.Q = 31487.641739605908 W and PHF.Q = 20000 W, from `solution-state` on `main`. At `78d3647` no record held them; the extraction read the in-memory state. | M06: build the unit panel from the `list_models` signature and the state; show "not applicable", never a blank. |
| **G11** Per-attempt counters | A; defect D3; C (time) | **Per attempt:** events carry cumulative counters, so an attempt's counters are the `attempt_closed` values minus the `attempt_opened` values. Attempt 0: 54 property / 2 residual / 2 Jacobian / 2 factorizations. Attempt 1: 135 / 7 / 4 / 4. 148 property calls fall between the attempts (the recovery initializer) and belong to neither. **Run 2:** the bundle has call counts, but **D3**: `observations.counters.property_calls` is 0, while its trace says 202. It is 0 again on `main`'s A02-352 bundle, against 108 residual calls. **Wall time:** only the run total (manifest, job times). | D3 (build lane); design Q3 |

## Requests for T07

T07 is closed (merged, `tested`). The Inspection result shapes are frozen by ADR 0019 A1. So each
ask below needs an ADR 0019 amendment and is then build-lane work, scheduled with M06 or T08.

1. **`inspect_structure` for a revision that has no route.** Beside `not_run_reason`, return the
   structural report `validate()` already analysed (`validation._analysed`), labelled
   `validation_structural_report`.
   - *Why:* STR-03's candidate rows and per-unit degrees of freedom are its diagnosis. Today the
     only copy is prose in a check message.
2. **A map from specification to rows,** `{spec_id: [row_id, …]}`, in the `inspect_structure`
   envelope, not inside `structural_report`, so that `structural_sha256` and R0 stay unchanged.
   - *Why:* a candidate specification has to link to its equation rows (G3).
3. **`blocked_by` in the record** (this is solver and verify work more than T07). Put
   `NewtonResult.blocked_by` into `failure-bundle.observations`, which is an open object, and, if
   the design lane agrees, into `implicated_sources`.
   - *Why:* a `BOUND_BLOCKED` screen has to name the variable on its bound.
   - Failure bundles are hashed replay artifacts, so this needs a design-lane review.
4. **Read the audit table and the commit ledger:** `list_audit(principal?, operation?, cursor,
   limit)`, returning the audit rows plus, for commits, `expected_revision`, `idempotency_key`
   and the revision produced.
   - *Why:* screen 8 (agent history) has no source today.
   - Which right it needs is design Q5.
5. **The right each operation needs,** in `get_project`, as `operations: [{name, right}]`.
   - *Why:* the UI can then disable actions without keeping its own copy of the `OPERATIONS`
     table.
   - Optional: the table is static in design §4.3.

**Record defects** (build lane, not contract asks; D2 and D3 touch replay-identity artifacts, so
they need design-lane review):
- **D1** — the STR-03 message should print `instance_id`, not the binder's `unit_id`
  (`validation.py:385` ← `graph/report.py` `implicated_from`).
- **D2** — fill `replay_identity` in region and K03 failure bundles, and `policy_id` / `plan_id`
  in revision-path certificates.
- **D3** — the failure bundle's `property_calls` and `requested_evaluations` read 0 for region
  results. The cause is not isolated. The hypothesis is that `RegionResult.counters` excludes
  the executor's provider meter (`orchestrator/executor.py:883`).

## Questions for the design lane

- **Q1 (G2).** Should the validation report carry a structured redundant and excess count? That is
  a frozen-schema change.
  - *Default:* no. `inspect_structure` is the structured source; the report keeps its messages.
- **Q2 (G3).** What is an "equation view"? Blueprint §12 wants equations one step from every
  number, and no operation serves a row. What does a row carry: owning instance, kind, declared
  incidence, row scale, a readable form?
  - *Default:* row id, instance, incidence and scale from existing data, with no symbolic text
    until the design lane specifies it.
- **Q3 (G5, G11).** May per-event or per-attempt wall time be recorded as telemetry? It would have
  to stay outside identity (ADR 0007), and the solve-event schema is closed.
  - *Default:* no. The UI shows the run total only.
- **Q4 (G6).** Should a run carry a comparison with a registered reference root, and under which
  allowance policy (T02 §6.4)? Or does that belong on the corpus page only?
  - *Default:* the corpus page only. Run records stay free of benchmark data.
- **Q5 (G9).** Which right reads the audit: `read`, or `policy`? The audit exposes other
  principals' request hashes and refusals.
  - *Default:* `policy` for other principals' rows, `read` for one's own.
