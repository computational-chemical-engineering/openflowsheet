# ADR 0067 — F8: identity, replay and evidence v2 (data lock in bundles, registry comparison, evidence classes, decision records)

**Status:** **Proposed, 2026-11-05.** Design wave W1, pass P3 (ADR 0057, R-928). Takes effect when Accepted after the W1
P3 reviewer pass over ADRs 0065–0067. Built in 0.5 (bundle, data lock, registry comparison: F8-WO1–WO3), 0.6
(evidence report, per-platform records, v2-compiled wiring: WO4–WO6) and 0.7 with TX (decision records and
`forced_replay`: WO7). The core (D12) freezes at the end of W1.
**Author:** design lane (`architect`). **Brief:** `docs/roadmap/brief-architect-W1-P3.md`.
**Refines:** `target-architecture.md` §2.7, §3 F8, §8 (`RunManifest`, replay manifest, `ReplayMode`). Departures are
marked **[departure]**. **Note edits:** `docs/roadmap/W1-P3-note-edits.md`.
**Adopts verbatim** (foundation rulings; this ADR is their authority once Accepted): Q9.R6, Q9.R7; Q9.A4–A8; the
ADR 0060 D9 rule "evidence never moves an identity".
**Amends** (each additive; every v1 manifest, bundle, replay report and digest unchanged):
- ADR 0007: D1 (classes of the new fields, D9); D4 (`forced_replay`, the registry and data checks, D5, D8).
- ADR 0025: per-platform reference records generalised to every registered platform (D7).
- ADR 0034 D6: R3 replay-from-record covers co-simulated units (D10).
- ADR 0060 D9 **[departure, narrowing]**: evidence notices go to the run's evidence report, not into the certificate (D6).
- ADR 0063 D7 (additive): `MaterialModel` reports the record entries each state point read (D6).
- ADR 0052: **not amended here**; the extension-contributor amendment belongs to X01 rest, under D11's constraints.
- ADR 0019 D1 as **Amendment 12**: `ReplayReport` gains optional members and `ReplayMode` the value `forced_replay`;
  ADR 0020: artifact kinds (D3).

---

## Context

Today (`run/manifest.py`, `run/bundle.py`, `run/replay.py`, `run/identity.py`): a bundle is `run-manifest.json` plus
`artifacts/`, its index built from the bytes written; `structural_sha256` hashes the manifest minus `NON_STRUCTURAL`
(`run_id, started_at, elapsed_seconds, parent_run_id, hostname, environment, artifacts`); `artifact_r0_sha256` hashes
`r0_projection(artifacts)` (no floats); `Environment` records architecture, OS, Python, lock hash, BLAS, threads,
SuperLU options; `ReplayMode ∈ {exact_replay, compatible_reproduction, inspected_archived_results}`, chosen before
anything runs (ADR 0007 D4), verdict `MATCH | MISMATCH | NOT_RUN`; a record under an old numerical policy is compared
under that policy (ADR 0025, Frank's answer). Both `run-manifest.schema.json` and its `environment` are closed objects.
F0 M7 replays the 52 committed 0.3.0 bundles. P1/P2 give: the data lock and `data_lock_sha256` (ADR 0061 D10), the
rights register and its effective assessment (D11), `data_unavailable` (Q9.R7's code), the registry snapshot and
`registry_sha256` (ADR 0060 D10), extensions used derived from the run's documents with a `registry.usage()`
cross-check (D8), evidence classes and notices (D9). ADR 0062 D8/D12: a v2 document in the v1-expressible subset is
lowered and is a v1 run in every artifact.

## Decisions

### D1. Which runs carry v2 records

**v1-path runs** (v1 documents, and v2 documents lowered by ADR 0062 D12) write manifests, bundles and replay reports
exactly as today: no member of this ADR appears in them. **[departure]** The note's "a bundle carries the data lock"
applies to **v2-compiled runs** and to runs of every kind with `job_operation: run` (ADR 0066 D10). Reason: ADR 0062 D8
makes a lowered run a v1 run in every artifact; its records are legacy records re-indexed from the YAML files shipped
in the package (ADR 0061 D12), so its replay still resolves them, and when a store lacks them the lowering step refuses
`data_unavailable(<sha>)` exactly as D5 does.

### D2. `RunManifest` v2 (`run-manifest.schema.json`, optional members; closed objects kept)

| Member | Content | Class |
| --- | --- | --- |
| `bundle_format` | const `"openflowsheet-bundle-v2"`; its presence selects D5's reader | non-structural (added to `NON_STRUCTURAL`) |
| `data_lock_sha256` | ADR 0061 D10's SHA of the run's lock | structural, R0 |
| `extensions_used` | `[[kind, id, version, descriptor_sha256, self_sha256]…]` sorted by (kind, id, version key): ADR 0060 D8's set derived from the documents, built-ins included | structural, R0 |
| `run_kind`, `documents` | `[id, version]` and `{<role>: sha256}` for `run` jobs (ADR 0066 D11) | structural, R0 |
| `environment.registry` | `{registry_sha256, snapshot_sha256}` (the snapshot document of ADR 0060 D10 is an artifact) | non-structural (in `environment`) |

Absent members are not hashed (canonical JSON), so every v1 `structural_sha256` is unchanged. `reproducibility_class`
keeps its rule: R3 for a run with an out-of-process or co-simulated unit, else R1.

### D3. Bundle layout v2 (`run/bundle_v2.py`; `run/bundle.py` untouched)

```
<bundle>/run-manifest.json
<bundle>/artifacts/<v1 artifact files>              # solution-state-v2, certificate, revision, policies, …
<bundle>/artifacts/data-lock.json                   # SHA == data_lock_sha256
<bundle>/artifacts/registry-snapshot.json           # SHA == environment.registry.snapshot_sha256
<bundle>/artifacts/records-index.json
<bundle>/artifacts/records/<record sha>.json        # embedded records, the store's canonical bytes
<bundle>/artifacts/run-evidence.json                # D6
<bundle>/artifacts/decision-records/…, trajectory/… # TX (D8; ADR 0066 D13)
```

The manifest's `artifacts` index covers every file under `artifacts/`, so `verify_bundle`'s integrity check covers
records too. `records-index.json`: `{records: [{sha256, embedded: bool, sources: [{source_id, source_sha256,
assessment, conditions}]}]}` sorted by SHA; the assessments are those in force when the bundle was written, for
audit only. Artifact kinds added to `job.schema.json` (producers closed, consumers open): `data_lock`,
`registry_snapshot`, `records_index`, `record`, `run_evidence`, `decision_record`, `exchange_record`.

### D4. Rights-aware embedding (R-706, R-926, Q9.R3, Q9.R7)

For every record SHA the lock names (`components[].record`, `parameter_sets`): the writer computes ADR 0061 D11's
effective assessment for each source the record carries. The record is **embedded** iff every one is `permitted`
(conditions copied into the index), otherwise **referenced** by SHA only. Generated and fitted records are embedded or
referenced like any other; their input records are not needed, since replay never regenerates (Q9.R5). Rights enter no
hash: re-assessing a source after writing changes no `data_lock_sha256`, `structural_sha256` or `r0_sha256` (Q9.A2).
No network access occurs while writing or replaying a bundle (note §2.7.2).

### D5. Replay of a v2 bundle (`run/replay_v2.py`; one dispatch line in `run/replay.py`)

Steps in this order; reasons accumulate in this order; any reason from steps 2, 5 or 6 makes the mode
`inspected_archived_results` and the verdict `NOT_RUN` (ADR 0007 D4: nothing is rerun):
1. **Integrity:** `verify_bundle`, unchanged.
2. **Format:** no `bundle_format` → the v1 path, unchanged, and its report is returned as today. An unknown value →
   `bundle_format_unsupported(<value>)` (ADR 0002 D7.5).
3. **Numerical policy:** ADR 0025 as answered by Frank, unchanged.
4. **Environment:** ADR 0007 D4's mode from lock, platform and threads, unchanged.
5. **Extensions:** for each `extensions_used` entry the current registry must hold (kind, id, version) with equal
   `descriptor_sha256` and `self_sha256`: else `extension_unavailable(<kind>, <id>, <version>)` or
   `extension_changed(<kind>, <id>, <version>)`. A difference only in descriptors the run did not use changes nothing
   but is reported (`registry_comparison.unused_differences`). Evidence fields (status, attestations) are never compared.
6. **Data:** each lock SHA resolves from `artifacts/records/` (identity rule re-applied to the bytes; a mismatch is
   `store_object_corrupt(<sha>)`) or the local F3 store; each unresolved SHA adds `data_unavailable(<sha>)`, all listed,
   sorted (Q9.R7, Q9.A8).
7. **Rerun and compare:** the recorded documents rerun with embedded records served before the store; comparison as
   ADR 0007 D4 with `run/identity.py`'s v2 R0 projection (ADR 0062 D8's `solution-state-v2` parts; ADR 0066's R0
   ledger and event parts; D8's decision-record R0 parts). The rerun's `registry.usage()` set must be a subset of
   `extensions_used`; an extra entry is `extension_use_undeclared(<kind>, <id>)` and the verdict `MISMATCH` (the
   recorded identity missed a dependency: a defect, never noise).

`ReplayReport` (Amendment 12) gains optional `registry_comparison: {recorded_registry_sha256, current_registry_sha256,
changed: [...], missing: [...], unused_differences: int}`, `data_availability: {embedded: int, from_store: int,
missing: [sha…]}` and (TX) `decision_comparison`. They are absent for v1 bundles, whose reports stay byte-identical.

### D6. Evidence classes (§2.7.7; Q9.R6; ADR 0060 D9)

`run-evidence.json` (`schemas/run-evidence.schema.json`), written for every v2 run:
`{evidence_format: "openflowsheet-run-evidence-v1", verification: {certificate: <artifact name> | null,
verification_status}, validation: {entries: [{component, entry, origin: [...], derivation, source_id, source_version,
record_sha256, uncertainty | null, extrapolated: [{variable, bound}], near_threshold: [{variable, bound}]}]},
optimality: {claim: "none" | "local" | "global", basis: string}, extensions: [{kind, id, version, origin,
effective_status, evidence_class, stability}], notices: [{code, params}]}`. The validation class lists each (component,
entry) the composition read exactly once, judged at the converged state only (trial states never count), with
`near_threshold` within 1e-9 relative of a bound (Q9.R6). `optimality.claim` is `none` for simulation, `local` for OPT
(ADR 0032) and "local per NLP; no global claim" for X24. Notices: `extension_unreviewed(<id>, <origin>)` per unreviewed
descriptor in `extensions_used`, `preview_kind(<kind>, <id>)` per preview-kind descriptor (ADR 0060 D9).

**Outside every identity:** `run-evidence.json`, `registry-snapshot.json`, `records-index.json` and `records/*` are
on an explicit exclusion list of `r0_projection` (records are pinned by `data_lock_sha256` already), never in
`structural_sha256`, never in a certificate check. No data origin changes a verification verdict (D14, Q9.A4).
**[departure, narrowing ADR 0060 D9]** The certificate carries no notices: it is a verification document, and an
evidence-class notice is not a verification claim (D14); keeping the certificate free of them keeps its R0 projection
untouched by review status. The run's report is its `RunResult` plus `run-evidence.json` (an output artifact; no
`RunResult` field changes).

**F4 hook (amends ADR 0063 D7 additively):** `MaterialModel.entries_read(point_id) -> tuple[EntryRead, ...]` with
`EntryRead = (component, entry, record_sha256, validity: {variable: (lo, hi)})`, determined from the composed method's
phase models and the point's active phases at the converged state; the evidence writer judges extrapolation from it.

### D7. Per-platform reference records (ADR 0025's pattern; X07a)

R0 is identical on every registered platform (the platform ids of ADR 0060 D2). A registered reference case holds one
record per reference platform (`linux-x86_64`) and, only where a float exceeds the numerical policy on another
platform, a per-platform record beside it (`<case>.<platform>.json`, unless ADR 0025's existing layout already names
one: then that layout). The comparator uses the current platform's record if one exists, else the reference platform's,
and reports `platform_reference_used(<platform>)`. Invariant (a test over every case): the R0 projections of all
per-platform records of a case are identical; a per-platform record states the float, the policy bound and the
near-threshold flags that make an R0 discrepancy attributable (ADR 0007 D2.4). Self-hashes do not depend on line
endings (ADR 0060 D3).

### D8. Decision records and `forced_replay` (designed here; TX builds)

**Decision record** (`schemas/decision-record.schema.json`; `artifacts/decision-records/part-<i, 4 digits>.json`, at
most 10 000 entries each, an index with each part's SHA): `{decision_format: "openflowsheet-decision-record-v1",
run_id, route: [id, version], entries: [{seq, kind, r0: {…}, numeric: {…}}]}`.

| Entry kind | `r0` | `numeric` | Class |
| --- | --- | --- | --- |
| `step` | — | t, h, order, corrector iterations | numerical record |
| `step_rejected` | reason word | t, h, order | numerical record |
| `event` | event id, assignments (ADR 0066 D5) | located t | R0 sequence; t numerical |
| `segment` | segment index, active specification set id | t | R0 sequence |
| `reinit` | attempt signature after re-initialisation | — | R0 sequence |
| `structure` | structure id (X24 binary vector rendering) | — | R0 sequence |
| `master_iteration`, `seed` | — | values | numerical record |

The run's R0 projection gains the ordered `r0` parts of `event`, `segment`, `reinit` and `structure` entries; step
counts are adaptive and never R0 (D20).

**`forced_replay`** (`ReplayMode` value). Chosen by step 4 in place of `compatible_reproduction` when the bundle holds
decision records (same lock, another registered platform); on `exact_replay` conditions the adaptive rerun stands.
Semantics: the route reruns with the recorded step sizes, orders, seeds and master-iteration choices imposed; inside
each imposed step it re-evaluates event functions, and an event must be detected in the recorded step (else
`forced_replay_divergence(<seq>)`); a corrector that fails on a recorded step is the same divergence. Comparison: R0
sequences identical; trajectory values at the recorded steps, event times and ledger floats within the numerical
policy. Why: adaptive selection turns a 1-ulp platform difference into truncation-level trajectory differences, which
no roundoff policy can judge; imposing the decisions keeps differences at roundoff. Only routes with
`decision_records: true` (ADR 0066 D10) support it. Grazing events near a step boundary: SQ-F8-1.

### D9. Classes of the new fields (ADR 0007 D1, amended)

| Field | Class |
| --- | --- |
| `data_lock_sha256`, `extensions_used`, `run_kind`, `documents`, `differential_map`, structure-v2 `sources` | R0 |
| decision-record `r0` parts; ledger column lists and removal pairs; trajectory `variable_ids_sha256` | R0 |
| trajectory floats, event times, ledger floats, `numeric` parts | R1/R2 (numerical records where adaptive) |
| chunk and row counts, step counts | recorded, not reproducible |
| `bundle_format`, `environment.registry`, evidence report, records index, rights assessments, review status | excluded from identity |

### D10. Co-simulation and out-of-process units (§2.7.5; ADR 0034 D6 generalised; TX builds)

R3. An `exchange-record` artifact holds the communication points, exchanged values and child snapshots where the child
exports them; `reproduce` serves recorded child results after checking request identity exactly and inputs within the
policy (ADR 0034 D6's recorded backend). The certificate lists `not_rechecked(<unit>, <reason>)` checks with outcome
`unsupported` for what it could not re-check. The exact cache keys on the child snapshot's SHA, or is bypassed and the
run records `cache_bypassed(<unit>)`.

### D11. Extension functional contributors: decided for X01 rest

ADR 0052's amendment that lets extension `functional_contributor` descriptors reach E01 belongs to **X01 rest**, not to
this ADR: it changes E01's dispatch (`assessment/program.py:69`, `:173–177`) and its identity, which are E01's. F8 fixes
what that amendment must satisfy: (i) extension contributor names are namespaced (`<namespace>.<name>`) and can never
shadow `cost`, `lca`, `derived`; (ii) one runs only when the assessment document names it; (iii) its descriptor's
`implementation_sha256` enters the assessment's identity and `extensions_used`; (iv) the assessment report carries
`extension_unreviewed` and `preview_kind` as D6 does. Until then they stay `preview`, listed only (ADR 0060 risk 4).

### D12. Core at the end of W1

**Core (frozen):** D1's scope rule; D2's members and classes; D3's layout; D4's embedding rule; D5's step order and
codes; D6's evidence document envelope, exclusion list and the F4 hook signature; D9's classes; D11's constraints.
**Designed, built with TX (core grammar, preview behaviour until TX):** D8's record format and `forced_replay`
semantics; D10.

## Alternatives rejected

- *Embedding all data* (breaks R-706, R-926); *fetching data at replay* (non-deterministic; offline replay fails) —
  the note's.
- *Comparing the whole `registry_sha256` on replay.* Any unrelated installed plugin would force every replay to
  `inspected_archived_results`; only the used set decides what ran.
- *Writing F8 members into v1-path runs.* Breaks ADR 0062 D8's "a lowered run is a v1 run in every artifact" and buys
  nothing: their data is the shipped legacy index.
- *Notices in the certificate* (D6).
- *Step decisions as R0.* A step count sums adaptive float decisions (ADR 0007 D1's "recorded, not reproducible").

## Migration proof

F0 PASS, M7 in particular: the 52 0.3.0 bundles take D5's step 2 to the unchanged v1 path, so mode, verdict, reasons
and report bytes are unchanged (E-F8-1). v1-path runs write no new member (E-F8-10). Schemas gain only optional members
and enum values (ADR 0002 D7.1; migration report: no instance migrated, no stored digest changes).

## Exit tests (F0 PASS implied on each)

- **E-F8-1** Every 0.3.0 bundle replays with the same mode, verdict and reasons, and a `ReplayReport` byte-identical
  to the pre-F8 report.
- **E-F8-2** A v2 bundle round-trips: manifest validates; `data-lock.json` and `registry-snapshot.json` hash to their
  manifest values; the integrity check covers `records/`.
- **E-F8-3** Embedding: a record whose sources are all `permitted` is embedded; `unknown` or `refused` is referenced
  only; re-assessing a source afterwards changes no `data_lock_sha256`, `structural_sha256` or `r0_sha256`.
- **E-F8-4** Q9.A8: with a referenced record absent from the store, replay is `inspected_archived_results` / `NOT_RUN`
  with `data_unavailable(<sha>)`; with two absent, both listed in sorted order; with the record embedded, the replay
  runs and matches.
- **E-F8-5** Registry: a changed `self_sha256` of a used extension gives `extension_changed` and `NOT_RUN`; a changed
  unused one changes neither mode nor verdict and is counted; the recorded snapshot equals ADR 0060 D10's document.
- **E-F8-6** Usage: for every v2 corpus run the usage set ⊆ `extensions_used`; a test-only hidden `resolve` makes the
  replay `MISMATCH` with `extension_use_undeclared`.
- **E-F8-7** Evidence: Q9.A4–A7; changing an extension's review status or attestation changes no structural or R0
  value; mutating `run-evidence.json` changes no `r0_sha256`.
- **E-F8-8** Per-platform records: the comparator picks the platform's record; the R0-equality invariant holds over all
  cases; a fake platform with a beyond-policy float uses its record and reports `platform_reference_used`.
- **E-F8-9** (with TX) `forced_replay`: a transient case replayed under a 1-ulp perturbation of one input (the
  single-machine surrogate for a platform change) keeps an identical R0 decision sequence and floats within policy at
  the recorded steps, while an adaptive rerun under the same perturbation changes its step count (mutation control).
- **E-F8-10** v1-path runs: manifests and artifacts byte-identical to pre-F8 (E-F2-3, M3, M4).

## New catalogue codes (ADR 0058 C3)

`bundle_format_unsupported`, `extension_unavailable`, `extension_changed`, `extension_use_undeclared` (bug),
`platform_reference_used` (notice), `record_referenced` (notice: a record travelled by reference), `forced_replay_divergence`,
`not_rechecked`, `cache_bypassed` (notice). `data_unavailable` reuses ADR 0061's entry.

## Work orders (`wp/F8`; at most two engineers at a time)

| # | WO | Content and files | Acceptance | Identity | Lane |
| --- | --- | --- | --- | --- | --- |
| 1 | **F8-WO1** (0.5) Manifest and schemas | `run/manifest_v2.py`; `run-manifest`, `replay-report` (optional members, `forced_replay` reserved: refused `construct_unavailable(forced_replay, TX)` until WO7), `records-index`, `run-evidence` schemas; `NON_STRUCTURAL` += `bundle_format` | E-F8-10, E-F8-2 (schema part) | no | Opus |
| 2 | **F8-WO2** (0.5) Bundle writer | `run/bundle_v2.py`; embedding via ADR 0061 D11; test-only v2 bundle factory (a corpus case rerun and recorded as v2) | E-F8-2, E-F8-3 | no | Opus |
| 3 | **F8-WO3** (0.5) Replay | dispatch in `run/replay.py`; `run/replay_v2.py`; usage cross-check | E-F8-1, -4, -5, -6 | no | Opus |
| 4 | **F8-WO4** (0.6, after F4-WO4) Evidence | `run/evidence.py`; the F4 hook in `material/model.py` | E-F8-7 | no | Opus |
| 5 | **F8-WO5** (0.6, with X07a) Platform records | `run/platform_refs.py`; invariant test | E-F8-8 | no | Sonnet, Opus review |
| 6 | **F8-WO6** (0.6, after F6-WO4) Wiring | v2-compiled runs write bundle v2 | E-F8-2 on real v2 runs | no | Opus |
| 7 | **F8-WO7** (0.7, in TX) Decision records, `forced_replay`, exchange records | `run/decisions.py`; route hooks | E-F8-9 | no | Opus |

## Risks and open questions (each with a default)

1. **ADR 0063 must carry the F4 hook** (fact: the P3 review). *Default:* this ADR amends ADR 0063 D7 additively; F8-WO4
   waits for F4-WO4.
2. **The certificate without notices** (preference: reviewer). *Default:* D6; reversing it means an optional,
   non-R0 certificate member.
3. **Redistribution** (Frank, R-706). *Default:* reference only unless every source is `permitted`.
4. **Stale assessments in `records-index.json`** (none structural). *Default:* informational; replay re-resolves.
5. **ADR 0025's existing per-platform layout** (fact). *Default:* reuse it if it exists; else D7's naming.
6. **X01 rest owns the ADR 0052 amendment** (preference). *Default:* D11; reversible by moving D11 into an ADR-F8
   amendment before X01 rest starts.

## Specifier questions (batched for the round after P3)

- **SQ-F8-1** Grazing events under `forced_replay`: an event whose function is within τ_g of zero at a recorded step
  boundary. *Default:* τ_g = the integrator's event-location tolerance; such a case is `MATCH` with
  `verdict_changed_near_threshold` semantics (ADR 0007 D2.4), any other step mismatch `forced_replay_divergence`.

---

## W1 P3 build order across ADRs 0065–0067 (and against F1–F5)

| Line | Order (each after the previous on `main`) | Unblocks |
| --- | --- | --- |
| 0.5 | F1 → F3 → F2 → **F8-WO1–WO3** (needs F2-WO4/WO6, F3's store and rights register, F1's snapshot) | v2 bundles mechanics; X07b's records; TX's later decision records |
| 0.6 | F4 → F5 → **F6-WO1–WO3** (may start after F1-WO2, F2-WO3) → **F6-WO4** (needs F4-WO4, F5's contract) → F6-WO5–WO9; **F8-WO4** after F4-WO4; **F8-WO6** after F6-WO4; **F8-WO5** with X07a | X08, X09, X10 gaps, X12, X13, X14 (with X17), X15 (CAPE-OPEN seam), X16, X19, X21, X22 |
| 0.7 | **F7-WO1–WO7** (after F6-WO4) → TX (with **F8-WO7**) | TX → X25, X26; X24 (needs F7, F8, OPT, X06); X06 resume |

The specifier round after P3 batches SQ-F6-1…4, SQ-F7-1…2, SQ-F8-1 with ADR 0063 risk 5 (entropy shift). Only SQ-F6-2
gates a work order's exit (F6-WO5's `h_mass` forms; E-F6-6, E-F6-16); every other question proceeds on its default.
