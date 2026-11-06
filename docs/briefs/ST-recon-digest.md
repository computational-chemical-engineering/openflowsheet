# ST recon digest (stream table and energy summary)

Status: read-only recon, 2026-11-06, main checkout. No ST design note exists yet (`find docs -iname '*ST-*'` is empty).
Sources: ADR 0056 Am. 1 (`docs/adr/0056-capability-extension-plan.md:83`), `docs/USER_FEEDBACK.md:27` (FB-06), `:15`
(FB-02), `docs/roadmap/roadmap.md:36`, `docs/V02_STATE.md:127`. The ST constraints quoted in the brief are not located in
any file here.

## 1. Operations table and existing views

- `src/openflowsheet/application/operations.py:293` `OPERATIONS: Final[Mapping[str, Operation]]`, one `_row(...)` per
  operation. `_row` at `:260`: `_row(name, right, request_schema, response_schema, http, *, decode, encode=_document,
  mcp_tool=None, transports=ALL_TRANSPORTS)`. `Operation` dataclass at `:94`. `ALL_TRANSPORTS` `:75`. `dispatch` `:544`.
  `project_response` `:536`.
- Rows, in table order:
  - Application: `validate`, `commit_change`, `solve`, `reproduce`.
  - JobControl (`application/contract.py:126`): `submit_job`, `get_job`, `list_jobs`, `list_job_events`, `wait_job`,
    `cancel_job`, `get_job_result` (`{operation, run_result, replay_report, error}` of an ended job; `local.py:767`).
  - Inspection (`contract.py:150`, all `read`): `get_project`, `list_models`, `list_revisions`, `get_revision` (pointer
    projection of the revision), `diff_revisions`, `inspect_structure` (structure index), `preview_change`, `get_artifact`
    (registered artifact projected by pointer; bundle members as `<bundle id>/<file>`, `local.py:1297`), `list_audit`
    (ADR 0019 Am. 3; no MCP), `artifact_bytes` (raw export; no MCP).
- **Existing per-stream derived quantities or result view: none.** Closest: `get_artifact` on
  `<bundle>/solution-state.json` (raw solved variables, nothing derived); `get_job_result` (`RunResult.outputs` are
  artifact refs only); `inspect_structure` (index, no values).
- Transports read the one table: CLI `api` command `application/cli.py:525` and `_dispatch` use at `:299-303`; HTTP
  `bindings/http.py:83` `HTTP_OPERATIONS`, `:424` one route per row; MCP `bindings/mcp.py:81` `TOOL_OPERATIONS`, `:197`
  `list_tools`, `:207` `call_tool`; web `bindings/web.py`; Python `LocalApplication` (`application/local.py:155`).
- Adding a row touches: `_row` entry; `authz.OPERATION_RIGHTS` (pinned by a test); request/response schema (packaged in
  `src/openflowsheet/_data/schemas/`, e.g. `application-results.schema.json` `$defs`); `LocalApplication` method and the
  protocol method; for MCP `application/bindings/descriptions/<name>.md` (`tests/test_t07_w6c_descriptions.py`).

## 2. Solved-state storage, RunResult, run artifacts

- Writer: `src/openflowsheet/run/solution_state.py:42` `document(variable_ids, vector) -> dict` (keys `schema_version`
  `solution-state-v1`, `state_sha256`, `variable_ids`, `variables`). `NAME` `:36`. `inconsistencies(state, certificate)`
  `:71`. Schema `_data/schemas/solution-state.schema.json`.
- Only revision producer: `src/openflowsheet/application/revision_run.py:858-861`:
  ```
  state = solution_state.document(spec.variable_ids, state_vector(spec, result.state))
  if state["state_sha256"] != result.certificate.target_state_sha256: raise SolutionStateMismatchError(...)
  artifacts[solution_state.NAME] = state
  ```
  Written only when a certificate exists (any verdict); else `failure-bundle.json` (`:866`). Coupled runs:
  `application/coupled_run.py:712`.
- Readers: `run/bundle.py:142-175` (`_cross_check_solution_state`), `run/identity.py:151-153` (R0 keeps only
  `variable_ids`), `run/compare.py:624-683`, `orchestrator/warm_start.py:63,115`, `application/store.py:1087-1110`
  (warm-start lookup by kind), `application/local.py:1310,1447` (docs).
- `RunResult`: `src/openflowsheet/application/types.py:1142`. Fields: `job_id, run_id, revision_id,
  revision_content_sha256, policy_id, policy_sha256, check_policy_sha256, job_status, outcome, verification_status,
  structural_sha256, outputs: tuple[ArtifactRef,...], error, solve_path`. Built at `application/local.py:1002-1018`
  (`outputs=job.outputs`). `ArtifactRef` `types.py:862` (`kind, artifact_id, sha256, size_bytes, name`; `known` `:872`).
  `JobResult` `types.py:1240`.
- Enumeration: the caller builds the artifact dict in `application/revision_run.py:841-899` (names such as
  `solution-certificate.json`, `solution-state.json`, `solve-events.json`, `revision.json`, `execution-plan.json`).
  `run/bundle.py:53` `write_bundle(directory, manifest, artifacts)` writes `run-manifest.json` and `artifacts/`; the
  manifest index is built from the bytes written. Each name maps to a kind by `application/jobs/model.py` `ARTIFACT_FILE_NAMES`
  (~`:110-130`). Registration: `application/jobs/runner.py:315` `bundle_rows`; `application/store.py:999`
  `register_artifacts`; `store.py:1028` `artifacts_of_kind`.
- `RunManifest`: `src/openflowsheet/run/manifest.py:221`. `artifacts` is in `NON_STRUCTURAL` (`:66`), so not in
  `structural_sha256`. `artifact_r0_sha256` = `r0_sha256(r0_projection(written))` (`revision_run.py`, near the manifest
  build). `r0_projection` (`run/identity.py:59`) reads named keys only, so a new file name is outside R0 unless added there.
- Artifact kinds: `application/jobs/model.py:51` `ArtifactKind` Literal, `:81` `ARTIFACT_KINDS`. Includes
  `solution_state`, `solution_certificate`, `solve_trace`, `execution_plan`, `replay_bundle`, `worker_log`, `external_coupling`,
  `model_evidence` and others. Consumers keep unknown kinds (J5). A new kind is an additive Literal change.

## 3. Derived quantities per stream today

No stream-table function exists. Derived values exist only inside the verifier.

- Provider protocol (frozen), `src/openflowsheet/thermo/__init__.py:210` `PropertyProvider`:
  - `describe() -> PropertyCapabilities`
  - `evaluate_phase(request: PropertyRequest, context: EvaluationContext) -> PropertyResult` (`PropertyRequest` `:133`:
    `state: StreamState, phase: Phase, properties, derivatives=()`; `PropertyResult` `:150`)
  - `flash(request: FlashRequest, context) -> FlashResult` (`FlashRequest` `:174`; `FlashResult` `:183`: `status,
    phase_signature, vapor_fraction` (molar, None if undefined), `vapor`, `liquid`, `k_values`, ...)
  - `StreamState` `:105` (`n` in component order, `temperature`, `pressure`, `is_dormant`). `Phase` `:58`.
    `EvaluationContext` at `compiled.py:39`.
- Verifier helpers, each `(provider, stream, context)`:
  - `src/openflowsheet/verify/checks.py:326` `enthalpy_flow(provider, stream: StreamState, context) -> float`: fresh
    `provider.flash(FlashRequest(state=stream), context)`; dormant gives 0.0; phase choice by `_admissible_phase`
    (`checks.py:675`, bubble/dew test).
  - `verify/forms.py:95` `enthalpy_flow(provider, stream, phase: Phase, context)`: `n_tot·h` by `evaluate_phase`.
  - `verify/pr_c1.py:159` `enthalpy_flow(provider, stream, context, components)`.
  - `verify/table.py:1527` `_phase_enthalpy(provider, context, flows, T, P, phase, what)`: `Σ n_i h_i^phase`.
    `table.py:1555` `_producer_phases(view)`.
  - `verify/thermal.py:132` `saturated_enthalpy(provider, state, stream, context, components)`:
    `V·h^V_sat(P) + L·h^L_sat(P)`. `thermal.py:150` `enthalpy_map(view, state, provider, context) -> (dict, dict)`.
    `thermal.py:108` `_saturated_phases`, `:121` `saturated_streams(view)`.
  - `checks.py:628` `k_values(provider, T, P, context)`. `verify/zero_flow.py:216` `dormant_outlets(view, state)`.
- Callers: `verify/table.py:1686` `revision_checks(view, splits, state, *, provider, context, tolerances, judged_at, owners)`
  (fills `enthalpy[stream]` at `:1639-1669`, `:1796-1809`). `verify/certificate.py:681` `verify_revision(binding, revision,
  result, *, policy, state, solve_plan, external)` calls it at `:808`.
- Providers for a basis: `application/revision_binding.py:1880` `basis_provider(basis)`, `:1917` `provider_for(basis)`
  (bind-time preconditions). Fixed verifier context `revision_binding.py:139` `_CONTEXT`.
- Name collision: `verify/projection.py` is the Newton projection (ADR 0013 D1), not a stream projection.
- Vapour fraction: not in the state. Molar `vapor_fraction` comes from `flash`. Saturated streams carry
  `SaturatedStreamState.vapor_fraction` (`models/thermal/state.py:28`, beta = V/n) and split ids `vapor_id`/`liquid_id`
  (`:40-48`). The client-side quality is `js/model/certificate.js:60-69`.
- Entropy and density: `s` is declared only by `iapws95` (`thermo/iapws95.py:128`) and `wilson-ig-v2`
  (`thermo/wilson_ig_v2.py:66`). No provider declares density. `v` is molar volume (`thermo/pr_c1.py:521`, `z·R·T/P`).
  Density would be `M_mix / v`.
- Molar masses: `models/revision_flowsheet.py:99` `MOLECULAR_WEIGHTS` (placeholder A/B/C); `ComponentBasis` `:103`
  (`molecular_weights` `:121`); `component_basis(document)` `:212`. Component records carry `molar_mass`
  (`:169`). Mass flow and mass fractions are not stored anywhere; ST computes them.

## 4. Phase labels and saturation in the solution state

- `solution-state.json` holds numbers only, keyed by variable id: `<S>.n.<C>`, `<S>.T`, `<S>.P`, `<S>.sat.V`, `<S>.sat.L`,
  `<U>.Q` (`models/__init__.py:101-114`; `models/thermal/state.py:40-48`). No phase label is stored.
- Phase labels live in the certificate: `phase_branch` (`verify/certificate.py:342`; `_phase_branch` `:1420`: per stream
  `ZERO_FLOW` or `FLOWING`, plus `S3_split`). Revision form: `verify/table.py:1905` `revision_phase_branch`.
- Vocabularies (`docs/roadmap/00-core-inventory.md` §1b, lines 44-61, re-checked):
  - `thermo/__init__.py:58` `Phase = Literal["LIQUID","VAPOR"]`
  - `compiled.py:27` `PhaseSignature` (adds `TWO_PHASE`, `ZERO_FLOW`)
  - `models/__init__.py:81` `PhaseCapability = Literal["liquid","vapor","vapor_liquid"]`
  - `orchestrator/region.py:161` `Regime` (`TWO_PHASE, LIQUID, VAPOR, ZERO_FLOW`)
  - `models/thermal/kernel.py:66` `Regime` (`LIQUID, VAPOR, SATURATED`)
  - `orchestrator/trace.py:99` `AttemptSignature`; `thermo/__init__.py:54` `PropertyStatus`
- Saturation: carried split `sat.V`, `sat.L` (mol/s) with `vapor_fraction` in [0,1] (`models/thermal/state.py:28-37`).
  Declared regime `SATURATED` (`kernel.py:66`); `application/thermal_binding.py:9-12` maps `vapor_liquid` to it.

## 5. Existing energy and enthalpy balance checks

- `verify/checks.py:383` `energy_checks(provider, state, context, tolerances=None)`: per-unit `energy_balance.<U>`
  (`:413`), dormant `energy_balance.enthalpy.<S>` (`:401`). Flowsheet envelope rows `:431-436`
  (`heater_duty + flash_duty - (S4 + S7 - S1)`), registered as a documented blind spot.
- `verify/table.py` per-unit energy rows: `_mixer_energy` `:406`, `_heater_energy` `:454`, `_flash_energy` `:503`,
  `_splitter_energy` `:546`, `_through_energy` `:615`, `_pump_energy` `:678`, `_reactor_energy` `:777`,
  `_cstr_energy` `:827`, `_separator_energy` `:884`, `_exchanger_energy` `:915`. Each returns
  `unit.check("energy_balance", ..., "heat_rate", reads=...)`.
- Overall: `verify/table.py:1220` `_envelope_energy(view, state, enthalpy, tolerances, note, degenerate)`:
  `(Σ Q_ext + Σ W) − (Σ Ḣ(products) − Σ Ḣ(feeds))`, id `energy_balance.envelope`, `subject="flowsheet"` (`:1250`),
  called from `revision_checks` at `:1857`.
- Thermal units: `verify/thermal.py:440` `_through_energy`, `:473` `_mixer_energy`, `:511` `_flash_energy`, `:550`
  `_machine_energy`. Column: `verify/column.py:197` (inlets, duties, distillate, bottoms).
- Per-stream Ḣ sits in `Unit.enthalpy` (`verify/table.py:170` `Unit`) and `enthalpy_map` (`thermal.py:150`). Output
  is `CheckResult`s in the certificate; there is no summary object.

## 6. ADR 0019 amendment numbering, and ADR 0058 as the pattern

- `docs/adr/0019-application-contract-v1.md` has Amendments 1 (`:105`), 2 (`:134`), 3 (`:160`), 4 (`:218`). No
  Amendment 5 is in this file, although ADR 0037 (`0037-m04-surrogate-unit-promotion-and-rollback.md:58`) cites
  "ADR 0019 Amendment 5". That is a gap in the record.
- Claimed by later ADRs (grep `Amendment [6-9]|Amendment 1[0-2]` in `docs/adr/`):
  6 = ADR 0058 (`explain`, `RunResult.failure`; `0058:8`); 7 = ADR 0060 (`list_capabilities`, `check_admission`; `0060:9`);
  8 = ADR 0061 (protocol `Records`; `0061:10`); 9 = ADR 0062 (`0062:268`); 10 = ADR 0065 (`0065:25`); 11 = ADR 0066
  (`submit_run`; `0066:19`); 12 = ADR 0067 (`ReplayReport`; `0067:23`). ADRs 0063 and 0064 claim none. The next free
  number is 13 if ST changes `Inspection`. That choice is a design-lane decision.
- ADR 0058 status (`0058:3`): Accepted 2026-11-05; takes effect on `main` when MSG is `tested` and reviewed. No `wp/MSG`
  branch and no `docs/MSG_DECISIONS.md` exist. `explain` is not in `src/` (grep finds no `"explain"`).
- Pattern (ADR 0058 D7, `0058:62-69`): `Inspection` gains a method; one `OPERATIONS` row (right `read`, all four
  transports, HTTP `GET /v1/explain/{code}`, MCP tool `explain` with reviewed description); CLI convenience; new frozen
  result-type names (`:82`); a schema `$defs` widened additively; served MCP digest re-recorded (`:85-87`).
- Files named by MSG WO-7 (`docs/design/MSG-messages.md:1309-1319`): `application/contract.py`, `application/local.py`,
  `application/operations.py`, `application/bindings/descriptions/explain.md`, `application/cli.py`,
  `_data/schemas/application-results.schema.json` (`$defs`) and fixtures, `docs/interfaces-frozen.md`. WO-6 touches
  `application/types.py`. WO-10 is web-shell display (`design/MSG-messages.md:1330-1333`).
- Gate rules: `docs/briefs/MSG-build-WO3-6.md:14-24` (MSG-G0 identity, MSG-G7 CLI goldens, MSG-G10 surface snapshots
  and MCP digest equal to pre-MSG when `failure` and `explain` are removed).
- Frozen-interface record: `docs/interfaces-frozen.md` §1 (`:6-39`); Amendment paragraphs at `:36` (Am. 3), `:80`, `:82`.

## 7. Web shell: stream results today

- Yes, a streams screen: `src/openflowsheet/_data/web/js/screens/streams.js` (route `#/job/{jid}/streams`, `:29-30`),
  registered in `js/main.js:27,39`, linked from `js/screens/common.js:210`.
- Reads bundle members `revision.json`, `solution-state.json`, `solution-certificate.json`, `failure-bundle.json`
  (`streams.js:35-39`) and `list_models` (`:41`). Model `js/model/streams.js:34` `streamTable(revision, columns,
  variables)`: a join of connections, `inspect_structure` columns and state variables, no unit conversion (`:1-8`).
  Shows `n.<C>`, `T`, `P` only (`streams.js:111-116`). No h, s, density, quality or mass flow.
- Quality shown only for certificate `phase_branch` split entries: `js/screens/certificate.js:115-118`,
  `js/model/certificate.js:60-69`.
- State diff: `js/model/compare.js:73` `stateTable`; `js/screens/equation.js:65` reads `solution-state.json`.
- Web tests: `tests/test_m06_browser_smoke.py`, `tests/test_m06_wo4_serving.py`, `tests/test_m06_static_scan.py`.

## 8. Tests that pin the table or transport parity

- `tests/test_t07_w5a_operations.py`: `:132` `test_every_protocol_method_is_exactly_one_row`, `:146`
  `test_the_table_is_section_4_3s`, `:164` request-schema check, `:183` transport wait cap, `:381`
  `test_every_operation_succeeds_through_dispatch_and_meets_its_response_schema`, `:475` (G11), `:551` (G13).
- `tests/test_t07_conformance.py:620` `test_g14_every_transport_equals_dispatch` (transport parity), `:660`
  `test_every_carried_operation_succeeds_at_least_once`.
- `tests/test_t07_w5b_cli.py:327` `test_every_cli_operation_through_api_equals_dispatch`.
- `tests/test_t07_w6a_http.py` (HTTP; `:103` binding imports only the dispatch surface), `tests/test_t07_w6b_mcp.py`,
  `tests/test_t07_w6c_descriptions.py` (one description per MCP tool).
- `tests/test_t08_w2_surface_digest.py`: `:140` `test_the_served_digest_is_registered`. A new MCP tool moves this digest.
  `tests/test_t08_w2_description_reviews.py`.
- Also: `tests/test_t07_w5e_application_results.py`, `tests/test_t07_types.py`, `tests/test_m06_http_contract.py`,
  `tests/test_m06_wo3_list_audit.py`, `tests/test_m02_schemas.py`, `tests/test_doc_pages.py`,
  `tests/data/t07_global_state_allowlist.json`.
- How run: `scripts/gate.sh` (one summary line, log to file) calls `scripts/check.sh` (pytest). Per the MSG brief:
  `PYTHONPATH=$PWD/src PATH=<repo>/.venv/bin:$PATH ./scripts/gate.sh` (`docs/briefs/MSG-build-WO3-6.md:25`).
- Identity gates: MSG-G0 (`docs/design/MSG-messages.md:1345`) and F0 (corpus identity; `wp/F0` merged per `git log`).

## 9. Governing documents

- `CLAUDE.md`: authority is `docs/blueprint-v3.1.md` and `docs/implementation-plan.md` (§2.1 frozen interfaces, §2.2
  frozen schemas); read `docs/decision-register.md` before changing a covered decision; departures need an ADR; a task
  with no catching test is design-lane; no relaxed checks; `wp/<ID>` branches.
- `docs/adr/0056-capability-extension-plan.md:83` (ST row), Amendment 1 (`:76`), Amendment 2 (`:95`, real-simulator scope).
- `docs/USER_FEEDBACK.md:27` (FB-06 asks: T, P, molar and mass flow, composition, vapour fraction, h, s, density; overall
  energy balance; via API, artifact and CLI).
- `docs/roadmap/roadmap.md:36` (ST row), `:88` (X16 depends on ST). `docs/V02_STATE.md:127,137`.
- `docs/roadmap/00-core-inventory.md` §1, §3, §8, §9 (primary map). `docs/interfaces-frozen.md` §1-§2 (change rule).
- `docs/design/MSG-messages.md` and `docs/adr/0058-messages-and-code-catalogue.md` (transport pattern).
- `docs/adr/0013-*` (verifier fresh-flash and admissibility, cited at `checks.py:326`); `docs/adr/0051-*` (declared regimes).

## 10. Not found

- No ST design note; the ST constraints text is not in any file here.
- No `explain` operation, `wp/MSG` branch, `docs/MSG_DECISIONS.md` or `docs/MSG_HANDOFF.md`.
- No function in `src/` returning h, s, density, mass flow, mass fractions, quality or a per-stream table. Nearest are
  the verifier helpers in section 3.
- No `ADR 0019 Amendment 5` text in ADR 0019.
- No provider declares `density`; `solution-state.json` has no per-stream phase label.
- Not searched in depth: `graph/report.py` (its `r0_projection` at `:190` is a different function), `adapters/`,
  `assessment/` (may read stream flows), `studies/`.
- Not read, by instruction: `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider{3,4}/`, `.claude/worktrees/`.
- Not checked: whether `application-results.schema.json` has a stream or state result type; test coverage of
  `solution_state.inconsistencies`.
