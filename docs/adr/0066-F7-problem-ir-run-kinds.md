# ADR 0066 — F7: problem IR v2 (`DynamicSpec`, holdups, events), run kinds and `submit_run`

**Status:** **Proposed, 2026-11-05.** Design wave W1, pass P3 (ADR 0057, R-928). Takes effect when Accepted after the W1
P3 reviewer pass over ADRs 0065–0067; built in 0.7 on `wp/F7`, before TX, which builds on it. The core (D17) freezes at
the end of W1. **Author:** design lane (`architect`). **Brief:** `docs/roadmap/brief-architect-W1-P3.md`. **Refines:**
`target-architecture.md` §2.5, §2.6 C6, §3 F7, §8 (accumulation kinds, `ValidationReport`, `CompiledProblemMetadata`,
checkpoints, jobs). Departures are marked **[departure]**. **Note edits:** `docs/roadmap/W1-P3-note-edits.md`. **Adopts
verbatim** (foundation rulings; this ADR is their authority once Accepted): Q1.R7, Q1.R8, Q1.R9, Q1.R10 and Q1.A10,
Q1.A11, Q1.A12, Q1.A13; Q5.R11 and Q5.A13 (Amendment 4, 2026-11-05); O-10's tolerances (drain defect ≤ 1e-8·m₀,
trajectory error 1e-10 relative) as defaults, amended if a measured margin falls below 10×; R-930 (`state_rate`).
**Amends** (each additive; every steady `model_version`, metadata document and digest unchanged):
- ADR 0008: D3 gains the kind `state_rate` (**reverses C10's rejection**, R-930); A1.1 U1/U1b become a check on
  registered holdup kinds, still never an enthalpy (rulings §10 item 8; U–H.8 stays out, Q-A5, A2-a); C7 and C8 made
  concrete (D4, D5; C7 with a change of location, **[departure]**); X8's map is D4's `differential_map`.
- ADR 0003 (and `interfaces-frozen.md` §1): `CompiledProblemMetadata` gains a nullable `differential_map`; methods and
  `EvaluationContext` unchanged (ADR 0008 D1).
- ADR 0060 D1: a 23rd kind `holdup_kind` (built-in only; D3); payloads of `run_kind` and `solver_route` (D10); the
  discrete coordinate `discrete_state` (D5).
- ADR 0019 D1 as **Amendment 11**: the `submit_run` operation, `ValidationReport` tasks, the job operation `run`; ADR
  0020: job request and result branches, artifact kinds, progress detail (D11, D12).

---

## Context

There is no time anywhere today: `ProblemSpec` → `CompiledProblem` (ADR 0003; `residual(x, context)`,
`jacobian(x, context)`, CSC, SuperLU), rows carry `accumulation ∈ {algebraic, zero_holdup_balance, holdup_balance,
absent}` (ADR 0008 D3, `compiled-problem-metadata.schema.json` `row_accumulation`), and `model_version` hashes the
structure document v1 (variable, equation, parameter ids, row accumulation). ADR 0008 Amendment 1 fixed what a dynamic
form must look like (U–H.1–U–H.8: conservative holdup columns `N_i`, `U`; constant 0/1 mass matrix from a row→column
map X8; dynamic variants as separate models, X4′; C10 rejected non-conservation differential rows pending a control
ADR, which R-930 now gives). Jobs (ADR 0020, ADR 0008 J1–J6): closed operation discriminator (`solve`, `reproduce`,
`experiment`, `surrogate_study`), outputs as a streamed list, consumers ignore unknown kinds. `ValidationReport.task ∈
{simulation, optimization}`. ADR 0065 gives units' dynamic contributions their slots and `compiled-problem-structure-v2`.
TX (0.7) owns the integrator: a DASSL/IDA-style BDF step loop, modified Newton with SuperLU, events on the step
interpolant, IDAS as cross-check (note §2.5.4). This ADR is the IR and the run-level contract that TX fills.

## Decisions

### D1. Unchanged base

`ProblemSpec`, `CompiledProblem` and `EvaluationContext` are unchanged. Every new form references a `ProblemSpec`: a
`DynamicSpec` (D4), a functional program (D9), a run kind's documents (D10). The residual a dynamic problem compiles is
the steady residual `F(x)` of all its rows; time enters only through the integrator's use of the `differential_map`.

### D2. Differential states (Q1.R7, R9; R-930)

Three kinds, each a column differentiated in exactly one row with coefficient 1:
- **(a) material holdups** of a control volume: one column per carried amount index and per carried extensive
  attribute of the definition the volume holds (ADR 0062 D3's carried-index order, stream fields `h`, `P` excluded),
  vids `<U>#<cv>~N[...]`, `~A[...]`, and one energy holdup `<U>#<cv>~U` (ADR 0065 D4). Never true species of a group
  basis, equilibrium-phase amounts or derived intensives; fast reactions and phase equilibria add no balance term.
  Per substream for dormancy (Q8.R6).
- **(b) rate states** `<U>~r[<name>]`: rows of kind `state_rate` (`ds/dt = +F_row`, s not conserved): controller
  integrals, filters, transmitter lags. Never in the ledger (D15). A PI integral row is written `F = sp − pv` (the
  gains act in the output row), so at `ṡ = 0` it is ADR 0065 D10's steady tracking row bitwise.
- **(c) non-material holdups** `<U>#<cv>~K[<kind>]` of a registered holdup kind (Q1.R9): the conserved quantity (U_w,
  L = Iω), never its intensive (T_w, ω); capacity positive (`holdup_capacity_nonpositive(<unit>, <holdup>)`); a wall
  energy has a unit-local datum declared in the manifest (`datum: {T_ref}` on the volume's `non_material` entry of
  ADR 0065 D2's `control_volumes`) and scale capacity × s_T.

### D3. Accumulation and holdup kinds (ADR 0008 D3 and A1.1, amended)

`accumulation` gains `{kind: "state_rate", state: {symbol, quantity_kind, dimension}}` with D3.2's dimension rule
(row = state dimension with time exponent lowered by one) and D3.3's orientation. It appears only in v2 manifests
(`model-manifest-v2`); the v1 `model-manifest.schema.json` is unchanged. `RowAccumulation` (code literal) and the
metadata schema's accumulation enum gain `state_rate`; no existing row carries it. PTC's mass pattern reads
`holdup_balance` only, so a `state_rate` row never gets a PTC mass entry (R-930's watch, E-F7-3).

`holdup_balance.holdup` gains a required `kind` in v2 manifests: an id of the new F1 kind **`holdup_kind`**, built-in
only (an extension id cannot match; a new kind needs an amendment of this ADR), payload `{material: bool, quantity_kind,
dimension, datum: "convention" | "unit_local"}`. Seeds: `amount`, `attribute`, `internal_energy` (material);
`wall_energy` (J, unit-local datum), `angular_momentum` (kg m² s⁻¹) (non-material). **U1/U1b amended:** for v1
manifests both keep their assertions verbatim (`U…` or `N…_i`, never an enthalpy); for v2 manifests both assert that
every `holdup_balance` row names a registered holdup kind. No seeded kind is an enthalpy, and U–H.8's isobaric
free-volume vessel (an `H` holdup) needs an ADR that adds its kind and states how U1 tells it apart (Q-A5, A2-a).

### D4. `DynamicSpec` and the `differential_map` (`src/openflowsheet/dynamic/spec.py`)

```python
@dataclass(frozen=True)
class DifferentialPair: row: str; column: str; kind: Literal["holdup", "rate_state"]; holdup_kind: str | None
@dataclass(frozen=True)
class DynamicSpec:
    problem: ProblemSpec                       # F(x): every row, steady form
    differential_map: tuple[DifferentialPair, ...]   # in problem.equation_ids order; non-empty
    discrete_states: tuple[DiscreteState, ...]; events: tuple[Event, ...]
    time_inputs: tuple[TimeInput, ...]; initial_condition: InitialCondition
    holdups: tuple[HoldupDecl, ...]           # control volumes: columns, substreams, zero-holdup form or None
```

`HoldupDecl` is built from ADR 0065 D2's `control_volumes`; a wall's `datum` is declared there.

Validity (typed, `differential_map_invalid(<reason>)`, a bug class): the map is a bijection between, on one side, every
`state_rate` row and every `holdup_balance` row of a dynamic-variant unit, and on the other its columns; a
`holdup_balance` row pairs with a holdup column whose holdup kind and dimension equal the row's declaration; a
`state_rate` row with an `r` column; no other row or column appears. A `holdup_balance` row of a steady unit inside a
dynamic problem is refused `holdup_column_missing(<row>)` unless the scenario declares that instance quasi-steady
(`quasi_steady`, D5), in which case the row stays algebraic (ADR 0008 X8's no-default rule). **The dynamic residual** is
`G(x, ẋ) = F(x) − M ẋ` with `M[r, c] = 1.0` iff `(r, c)` is in the map, else 0: M is a constant 0/1 selection and is
never assembled with thermodynamics (U–H.4). At `ẋ = +0.0`, `G = F` bitwise. The integrator forms its corrector `F(x) −
M(c x + ψ)` and Jacobian `∂F/∂x − c M` from the frozen `residual`/`jacobian` and the map: no change to
`CompiledProblem`.

`CompiledProblemMetadata.differential_map: tuple[DifferentialPair, ...] | None = None` (last field). It is `None` for
every steady problem; `metadata_to_document` (`serialize.py:43`, an explicit field map, not `asdict`) writes the key
only when it is not `None`, so every steady metadata document is byte-identical; the schema gains the optional member.
The metadata's map is the one set from `DynamicSpec` at compile, and the integrator reads it (an assertion checks the
two copies are equal). The default `None` (steady) is a recorded exception to K01's no-default rule
(`compiled.py:78–82`): `None` means steady, and dynamic problems are always v2-compiled. Dynamic problems are always
v2-compiled, and the map is a member of their structure document v2 (ADR 0065 D3). **[departure]** The note says the map
"is not a member of ADR 0002 D2's structure document": true of v1, which no dynamic problem uses; for v2 the pairing is
structure (two DAEs with equal rows and columns but different pairings are different functions), so it is hashed, and
absent, not empty, for steady problems (ADR 0008 X8).

### D5. Discrete states, events, time inputs, initial conditions (ADR 0008 C7, C8 made concrete)

- **Discrete state** `{id, owner, domain: {values: [int…]} | {real: true}, initial}`. Integer-valued ones are F1
  `discrete_state` coordinates of the attempt signature (ADR 0064 D3; R0); their adjacency is declared by the owner (a
  segment index: successor only; a controller regime: ADR 0065 D10's). Real-valued ones are pinned inputs `z[name]`
  (ADR 0065 D4), never R0. Both are constant between events and assigned only by event actions. The variable set is
  constant over a run; discrete states select active rows (ADR 0005 D2 generalised), so `model_version` never changes
  within a run.
- **Event** `{id, function: {program: <functional program SHA>, output: <id>}, direction: rising | falling | either,
  priority: int, actions: [{assign: <state id>, value: int | <expression SHA>} | {empty: <cv>} | {set: <pid>, value}]}`.
  Generated events: one drain event per (material control volume, substream) with function = held mass Σ M_c N_c,
  direction falling, action `empty` (Q1.R8); one time event per time-input breakpoint. Simultaneous events, their order,
  conflicts and cascades follow Q1.R10 (τ_ev = 10 τ_loc; ascending (priority, id); action values on the pre-group
  state; one re-initialisation per group; `simultaneous_event_conflict`, `event_chattering`). The sequence of (event
  id, assignments) is R0 (F8). F7 registers a D2.2 floor (ADR 0007) for every quantity kind an event function may have
  (D2.3); an event function of a kind without one is `event_floor_unregistered`.
- **Time input** `{target: {instance, parameter} | {specification: <id>}, trajectory: {kind: piecewise_constant |
  piecewise_linear, times: [...], values: [...]}}`, applied as pinned-input updates through the parametric twin (no
  recompile; ADR 0008 X9); a parameter bound by a signal and a time input is refused `parameter_binding_conflict`.
- **Where time inputs live [departure].** ADR 0008 C7/X7 planned a `schedule` branch on `Specification`. Time inputs,
  scenario events and the horizon live instead in a **dynamic scenario** document
  (`schemas/dynamic-scenario.schema.json`: `{scenario_format: "openflowsheet-dynamic-scenario-v1", revision:
  <content_hash>, t0, t_end, initial_condition, inputs: [TimeInput…], events: [Event…], record: "every_step" |
  {interval_s}, quasi_steady: [instance…], variants?: {<instance>: <unit id>}}`) that the `transient` run kind takes
  beside the revision. An instance's dynamic variant: the binder takes the unique registered manifest whose `variant_of`
  is the instance's model and whose `modes` contain `dynamic`; several candidates are refused
  `dynamic_variant_ambiguous(<instance>)` unless `variants` names one. Reason: a scenario is not the model; one steady
  revision keeps one `content_hash` across every disturbance study, and a replay identifies the scenario by its own SHA
  (F8 `documents`).
- **Initial condition** `{kind: "steady_at_t0"}` (the dynamic model's steady state at t0, solved by the steady route
  with `state_rate` rows as algebraic `F = 0`) or `{kind: "specified", values: [{vid, value}]}` followed by consistent
  initialisation.

### D6. Consistent re-initialisation and holdup dormancy (Q1.R8, adopted)

Re-initialisation holds the differential columns fixed (except those an action assigns) and solves the algebraic rows
for the algebraic columns by Newton on the row/column selection of the compiled residual and Jacobian, under the
attempt contract (regime and form openings as in a steady solve); then `ẋ` follows from the differential rows. Dormancy:
`empty(<cv>)` sets every held amount, attribute and (when the whole volume is dormant) the energy holdup to `+0.0` and
books the removed content as `drain_defect(<cv>)` in the ledger (D15); while dormant every balance source of the volume
is `+0.0`, and one its zero-holdup form (ADR 0065 D7) does not route to a non-material holdup is refused at the event
`dormant_holdup_source(<unit>, <term>)`; intensives of the contents are null (`holdup_empty`) and rows that lose rank
in them take the form's labels; outlets are dormant. Leaving: at the event opening where an inflow starts, before any
state point of the volume is evaluated, the contents take the flowing inflows' composition and the energy seed
`e_seed = Σ Ḣ_in / Σ ṁ_in` summed in the unit's inlet order (one inlet: its `h` bitwise). A unit without a zero-holdup
form reaching dormancy ends the run `holdup_dormancy_unsupported(<unit>)`, keeping its trajectory.

### D7. Index and rank (note §2.5.3; N1)

At `DynamicSpec` build: with A the algebraic rows and Z the algebraic columns (everything not in the map), a maximum
matching on the declared Jacobian pattern of (A, Z) (`graph/matching.py`'s Dulmage–Mendelsohn). `|A| = |Z|` and a
perfect matching: structural index ≤ 1, accepted. Otherwise refused `dae_index_unsupported(<unmatched rows>)`. At every
consistent (re-)initialisation: the 1-norm reciprocal condition estimate of the scaled ∂g/∂z (policy scales; SuperLU
with ADR 0004 options); below τ_idx = K04's τ_ill = 1e-8 the run
carries the typed limitation `dae_index_near_singular` (not a refusal), with D2.4's near-threshold band (Q5.R11): for
example a vessel full of a liquid whose scaled expansivity and compressibility are both small; an ordinary liquid,
PR's included, is regular (Q5.A13 (e)). The structural matching is re-run per opening's active row set (cached per
signature): a zero-holdup form or a regime opening that leaves (A, Z) structurally deficient is refused
`dae_index_unsupported` at that event.

### D8. Non-material holdups and transfers (Q1.R9, adopted)

A unit declares `transfers: [{id, into: <row>, from: <row>, expression}]`; the row builder adds `+term` to `into` and
`−term` to `from` through one call, so a transfer sits in exactly two rows with opposite signs by construction.
Non-material holdups enter the ledger and never go dormant with the material.

### D9. Functional programs (E01 D2's compilation, generalised)

`schemas/functional-program.schema.json`: `{program_format: "openflowsheet-functional-v1", outputs: [{id, role:
objective | constraint | event | report, quantity_kind, expression: <expression document SHA> | {builtin: <id>}}],
parameters_from: [{document_kind, sha256}]}`. Compiled as a functional `ProblemSpec` evaluated by the parametric twin
(value, ∂/∂x, ∂/∂p from one graph), never inside a `CompiledProblem`; parameters may come from a non-revision document
(X12). Event functions, OPT objectives and constraints, report quantities and recipe conditions are programs.

### D10. Run kinds and solver routes (F1 payloads)

`run_kind` payload: `{problem_form: steady | dynamic | nlp | minlp | post_solve | acquisition, inputs: [{role,
document_kind, required}], solver_routes: [<solver_route id>…] (first is the default), result_schema: <$id>,
reproducibility_class: R1 | R2 | R3, validation_task: <task> | null, job_operation: "solve" | "run",
partial_artifacts: [<artifact kind>…], checkpoint_schema: <$id> | null, package: <id>}`. `solver_route` payload:
`{problem_form, certificate_class: steady | trajectory | optimization | none, decision_records: bool}` (its code is the
descriptor's factory). A descriptor with `status: declared` is listed and refused `run_kind_unavailable(<kind>,
<package>)` / `solver_route_unavailable(<route>, <package>)`, never run.

| Run kind | Inputs | Form | Routes | Task | Status in 0.7 |
| --- | --- | --- | --- | --- | --- |
| `simulation` | revision | steady | `steady-eo`, `steady-legacy`, `steady-coupled` | simulation | implemented (`job_operation: solve`) |
| `optimization` | revision (+ economics document) | nlp | `nlp-ipopt` | optimization | implemented iff OPT is on `main`, else declared (OPT) |
| `transient` | revision, dynamic scenario | dynamic | `dae-bdf` | transient | declared → TX |
| `synthesis` | superstructure | minlp | `loa` | synthesis | declared → X24 |
| `batch` | revision, recipe | dynamic | `dae-bdf` | batch | declared → X25 |
| `analysis` | revision, run (solved) | post_solve | `pinch` | analysis | declared → X14 |
| `study` | study document | steady | `steady-eo` | simulation | declared → unassigned (risk 3) |
| `acquisition` | acquisition request | acquisition | — | null | declared → X11 rest (R3) |

Route ids `steady-eo`, `steady-legacy`, `steady-coupled` are today's `SolvePath` values `revision_eo`, `legacy_eo`,
`revision_coupled`; `RunResult.solve_path` is unchanged.

### D11. `submit_run`, the job operation `run`, validation tasks (Amendment 11; ADR 0020)

- **OPERATIONS row `submit_run`** (right `execute`, all four transports): request `{run_kind: {id, version?}, documents:
  {<role>: {revision_id} | {artifact_id} | {sha256}}, policy_id, options: {…}, resume_from: <artifact_ref> | null,
  idempotency_key}`; response the `Job`. The kind's `inputs` and options schema validate the request; an unbuilt kind
  is `ApiError unsupported` with `detail.code = run_kind_unavailable` (a refusal at submission, ADR 0019).
- A kind with `job_operation: solve` (only `simulation`) creates exactly the job `submit_job({operation: "solve", …})`
  creates, so its artifacts are byte-identical to `solve`'s (E-F7-8). Every other kind creates a job with the new
  operation `run`: `job.schema.json` `operation` enum gains `run` and `job_request.oneOf` the branch `run_body` (the
  request above); `job_result` gains `{run_kind: [id, version], result: <artifact_ref>, verification_status | null}`.
  `Application.solve` is unchanged.
- **Validation.** `ValidationReport.task` enum gains `transient`, `synthesis`, `batch`, `analysis`; `ValidationStatus`
  gains `READY_FOR_TRANSIENT`, `READY_FOR_SYNTHESIS`, `READY_FOR_BATCH`, `READY_FOR_ANALYSIS`. An extension run kind
  declares one of the seeded tasks as its `validation_task`, so no extension ever widens the enum. `validate(revision,
  task)` for a task whose kinds are all unbuilt is `ApiError unsupported` with `run_kind_unavailable`.

### D12. Progress and partial artifacts (C6; ADR 0008 J2, J5, J6)

`job.schema.json` `$defs/progress` gains three optional members `time_s`, `time_end_s` (numbers) and `segment`
(integer), all nullable, for dynamic kinds; operation-neutral counts stay. Partial artifacts are ordinary `output`
events appended as they close (J2): trajectory chunks, checkpoints, incumbents. Artifact kinds added (producers closed,
consumers open, J5): `run_result`, `dynamic_scenario`, `trajectory_manifest`, `trajectory_chunk`, `run_checkpoint`,
`conservation_ledger`, `incumbent`.

### D13. The chunked trajectory artifact (`schemas/trajectory-manifest.schema.json`)

Manifest `{trajectory_format: "openflowsheet-trajectory-v1", run_id, model_version, variable_ids_sha256 (document SHA
of the id list), variable_count n, fields: ["t", "x"] | ["t", "x", "xdot"], encoding: "ieee754-be-v1",
rows_per_chunk, chunks: [{index, t_first, t_last, rows, sha256, size_bytes}], complete: bool}`. Chunk file
`trajectory/chunk-<index, 6 digits>.bin`: accepted steps in order, each row the fields in order, every float in ADR
0002's `ieee754-be-v1` vector encoding, signed zeros normalised to `+0.0` first (as `state_sha256` does, ADR 0008 D2); `rows_per_chunk = max(1,
⌊8 388 608 / (8·(1 + n·k))⌋)` with k vector fields; `sha256` of the file bytes. Each chunk is emitted as an output event
when it closes; the manifest is written at the end and, with `complete: false`, at every checkpoint. The reader checks
size and SHA of every chunk before decoding (`trajectory_chunk_corrupt(<index>)`; a missing chunk of a complete
manifest: `trajectory_incomplete(<index>)`). Floats are R1/R2; chunk and row counts are recorded, not reproducible.

### D14. Per-kind checkpoints (ADR 0008 J4; X06)

`schemas/run-checkpoint.schema.json`: `{checkpoint_format: "openflowsheet-run-checkpoint-v1", run_kind: [id, version],
route: [id, version], inputs_sha256 (document SHA of {role: sha}), model_version, extensions_used_sha256 (ADR 0067),
body_schema: <$id>, body: {…}, trajectory_upto_chunk: int | null, job_sequence}`. The body is the kind's (TX defines
the transient body: t, x, BDF history, order, h, discrete states, pending events, ledger partials). Resume is a new job
(J6) with `resume_from`; any differing envelope field refuses `checkpoint_incompatible(<field>)`. K03's solver
`Checkpoint` schema is unchanged.

### D15. The conservation ledger (`schemas/conservation-ledger.schema.json`)

Per holdup column (material and non-material, never `state_rate`): `{column, holdup_kind, initial, final,
net_inflow, sources, removals: [{event_seq, amount}], closure}` with `closure = initial + net_inflow + sources −
Σ removals − final`; integrals are the integrator's own discrete fluxes (BDF conserves linear invariants step by step,
U–H.4). The column list and the (event_seq, column) pairs of removals are R0; the floats are R1/R2.

### D16. What 0.7 builds, and what is only reserved

F7 builds: D3, D4 (types, map, metadata member), D5 (IR, generated events, scenario schema), D6 and D8 (as IR and as the
reference integrator's behaviour), D7, D9 (envelope; E01 programs are one producer), D10 (registries, seeds, typed
refusals), D11, D12, D13 (writer, reader), D14 (envelope), D15 (schema). For its exits only, a **test-only reference
integrator** (`tests/f7/reference_integrator.py`: fixed-order BDF1 with step halving, event location by Illinois on the
linear interpolant to τ_loc = 1e-14 (|t| + |h|) (Q1.R10), Newton corrector on `∂F/∂x − (1/h) M`) runs the probes.
**[departure]** Q1.A11/A12 need an integrator, and the owned BDF is TX's (which depends on F7); TX re-runs Q1.A11, A12
and A13 on its BDF as part of its acceptance and re-measures O-10. Reserved for TX: the production integrator,
`forced_replay` (ADR 0067), the transient checkpoint body, co-simulation exchange, delays (`delay_unsupported`).
Reserved for X24, X25, X14, X11 rest: their kinds' routes and result schemas.

### D17. Core at the end of W1, and preview

**Core (frozen):** D2's three kinds and holdup layout; D3's `state_rate` object, `holdup_kind` kind and seeds, U1/U1b;
D4's types, residual form, map validity and metadata member; D5's discrete-state, event, time-input and
initial-condition objects and the scenario envelope; D7's criteria; D10's payload envelopes and seed ids; D11's
operation, job branch and task enum; D12–D15's envelopes. **Preview** (to the end of 0.7): `options` schemas per kind,
the transient checkpoint body, real-valued discrete states, `xdot` in trajectories.

## Alternatives rejected

- *A second modelling language for dynamics; IDAS as the only integrator; time in `EvaluationContext`* — the note's
  rejections (D02, D20, ADR 0008 D1), unchanged.
- *`M(x)ẋ` with M = ∂holdup/∂x over stream columns.* Conserves only to truncation error (U–H.4).
- *A `schedule` member on `Specification` (ADR 0008 X7).* Couples scenarios to model identity (D5).
- *One OPERATIONS row per run kind.* Splits the contract per feature (U3).
- *Trajectory chunks as JSON.* 1e4 variables × 1e3 steps is ~250 MB of text and re-parsing changes nothing the binary
  encoding does not already pin; ADR 0002's vector encoding is the project's float identity encoding.

## Migration proof

F0 PASS. No steady problem carries a map, so every metadata document, structure document v1 and `model_version` is
unchanged; v1 manifests and their U1/U1b assertions are unchanged; `solve` keeps its job and artifacts; schemas only
gain optional members and enum values (ADR 0002 D7.1: additive; migration report: no instance migrated).

## Exit tests (F0 PASS implied on each)

- **E-F7-1** Q1.A10 (probe tank on MEA–CO2–H2O: three group holdups and one energy holdup; partition classes; moments).
- **E-F7-2** The probe tank's dynamic residual at `ẋ = +0.0`, evaluated at the steady variant's solution, equals the
  *steady variant's* residual bitwise on every shared row (G(x, +0) = F(x) holds by construction and is not the test).
- **E-F7-3** A probe PI integral is a `state_rate` column; M's stored entries are exactly 1.0 on the map and nowhere
  else; it is absent from the ledger; PTC's mass pattern gives its row no entry.
- **E-F7-4** Index: an index-1 probe is accepted; Q5.A13 (a)–(f): (f) α ≡ κ ≡ 0 refused `dae_index_unsupported`
  naming the volume row; (c), (d) carry `dae_index_near_singular`; (e) (thermally expanding, κ ≡ 0) and a
  `cubic.pr-v1` liquid are regular.
- **E-F7-5** Q1.A11 (a)–(c) with the reference integrator; O-10 measured and logged (defect, T error, margins).
- **E-F7-6** Q1.A12 with its mutation control.
- **E-F7-7** U1/U1b: v1 assertions unchanged; a v2 `holdup_balance` naming an unregistered or enthalpy kind is refused.
- **E-F7-8** Run kinds: each declared kind refused `run_kind_unavailable` at `submit_run` and at `validate`;
  `submit_run(simulation)` on 10 corpus revisions gives `r0_sha256`, `state_sha256` and certificate bytes equal to
  `solve`'s; the `run` job branch passes ADR 0008 J1–J3, J5 tests; an old client ignores the new kinds and events.
- **E-F7-9** Trajectory: a probe run's chunks round-trip bitwise; a flipped byte gives `trajectory_chunk_corrupt`;
  chunks arrive as output events before the job ends.
- **E-F7-10** Checkpoint envelope round-trip; resume with a changed input, model or extension set refused
  `checkpoint_incompatible(<field>)`.
- **E-F7-11** Events: simultaneous events apply in (priority, id) order; integer discrete states appear in the attempt
  signature; `model_version` is constant across events; a time input changes `constants_sha256` per segment with zero
  recompiles (compile counter).
- **E-F7-12** Migration: every corpus metadata document byte-identical; `differential_map` absent for every steady
  problem.
- **E-F7-13** Adding an event program to a probe leaves the main problem's `model_version` unchanged.
- **E-F7-14** Q1.A13 with the reference integrator (simultaneous events, their order, conflicts and cascades).

## New catalogue codes (ADR 0058 C3)

`differential_map_invalid` (bug), `holdup_column_missing`, `dae_index_unsupported`, `dae_index_near_singular`
(limitation), `holdup_dormancy_unsupported`, `dormant_holdup_source`, `holdup_capacity_nonpositive`, `holdup_empty`
(null reason), `drain_defect` (ledger notice), `run_kind_unavailable`, `solver_route_unavailable`,
`trajectory_chunk_corrupt`, `trajectory_incomplete`, `checkpoint_incompatible`, `simultaneous_event_conflict`,
`event_chattering`, `event_floor_unregistered`.

## Work orders (`wp/F7`, 0.7; after ADR 0065's F6-WO1–WO4 are on `main`)

| # | WO | Content and files | Acceptance | Identity | Lane |
| --- | --- | --- | --- | --- | --- |
| 1 | **F7-WO1** Kinds and metadata | `state_rate` in `RowAccumulation`, metadata schema; `holdup_kind` kind and seeds; U1/U1b v2 branch; `compiled.py` field, `serialize.py` conditional key | E-F7-7, E-F7-12 (check first that no `asdict` of the metadata exists) | no (proved by F0) | Opus |
| 2 | **F7-WO2** IR | `dynamic/{spec,events,inputs,functional}.py`; scenario and functional-program schemas; the D2.2 floor per event-function kind (`event_floor_unregistered`) | E-F7-11, E-F7-13 | no | Opus |
| 3 | **F7-WO3** Index and rank | `dynamic/index.py` | E-F7-4 (Q5.A13) | no | Opus |
| 4 | **F7-WO4** Probes, ledger, reference integrator | test-only probe units; `tests/f7/reference_integrator.py`; ledger schema and writer | E-F7-1, -2, -3, -5, -6, -14 (Q1.A13) | no | Opus |
| 5 | **F7-WO5** Run kinds and `submit_run` | `runs/{registry,submit}.py`; seed descriptors; job and validation schemas; OPERATIONS row; Amendment 11 text | E-F7-8 | no | Opus (dispatch); Sonnet (schemas, fixtures) |
| 6 | **F7-WO6** Trajectory and checkpoint | `dynamic/{trajectory,checkpoint}.py`; schemas | E-F7-9, -10 | no | Sonnet, Opus review |
| 7 | Close-out | catalogue entries, evidence manifest, full gate, CI both legs | all | no | Sonnet |

**Unblocks.** WO1–WO4: TX (integrator on the IR, dynamic `std.*` variants, controllers' `state_rate`), X26 (walls,
events with hysteresis). WO5: X24 (route registry, `submit_run`), X14 (`analysis`), X11 rest (`acquisition`), X06
(resume via D14). WO6: X06, TX's partial artifacts. X25 waits on TX.

## Risks and open questions (each with a default)

1. **Reference-integrator exits** (fact: TX's re-run). *Default:* F7 exits on the reference integrator; TX may not
   exit unless Q1.A11, A12 and A13 also pass on its BDF (TX re-runs them).
2. **A2-a: the vented tank (U–H.8) is not admitted** (Frank's scope call before X25, `docs/FRANK_QUESTIONS.md`).
   *Default:* refused until an ADR adds its holdup kind; Q1.R8's drain is reachable only by evacuating a rigid vessel.
3. **`study` has no owning package** (preference: Frank). *Default:* declared and refused; the agentic layer's route
   comparison (R-931) is the likely owner.
4. **OPT's run records** (fact: OPT's design). *Default:* `optimization` keeps OPT's own job path until OPT adopts
   `job_operation: run`; F7 only lists it.

## Specifier questions (batched for the round after P3)

- **SQ-F7-1** *Ruled (Amendment 4): Q5.R11.* τ_idx for `dae_index_near_singular` on the scaled ∂g/∂z. *Default:*
  the K04 regularity check's `ILL_CONDITIONED` threshold, applied to the scaled ∂g/∂z at each (re-)initialisation.
- **SQ-F7-2** *Ruled (Amendment 4): Q1.R10.* Simultaneous events: the tolerance τ_ev and the application order.
  *Default:* τ_ev = the integrator's event-location tolerance (TX registers it); (priority, id) order; one
  re-initialisation after the group.

## W1 P3 review applied (`docs/reviews/W1-P3-review.md`, 2026-11-06)

Status stays Proposed.

| Finding | Edit |
| --- | --- |
| Header | Adopts Q1.R10, Q1.A13, Q5.R11, Q5.A13 verbatim. |
| M2 | D2 (c) and D4: `HoldupDecl` built from ADR 0065 D2's `control_volumes`; a wall's `datum` declared there. |
| N2 | D4: the metadata's map set from `DynamicSpec` at compile, read by the integrator, equality asserted; `None` default recorded as an exception to K01's rule. |
| 0066-1 | D5: simultaneous events, order, conflicts and cascades per Q1.R10. |
| S5 | D5: scenario gains `quasi_steady` and `variants?`; the variant selection rule, `dynamic_variant_ambiguous`. |
| 0066-2 | D7: τ_idx = τ_ill = 1e-8 with D2.4's band (Q5.R11); the PR-liquid example corrected. |
| N3 | D7: structural matching re-run per opening's active row set (applied; the review marks it optional). |
| 0066-3 | D16: τ_loc = 1e-14 (\|t\| + \|h\|); D5: D2.2 floor per event-function kind; codes; SQ-F7-1, -2 ruled. |
| M6 | E-F7-4 replaced (Q5.A13 (a)–(f)). |
| N4 | E-F7-2 compares against the steady variant's residual on the shared rows at the steady solution. |
| S8 | F7-WO2 (D2.2 floors), F7-WO3 (Q5.A13), F7-WO4 (Q1.A13, new E-F7-14). |
| Risk 1 | TX re-runs Q1.A11, A12 and A13 on its BDF (D16 and risk 1). |

Not applied: none of the edits for this ADR. Q1.A13 enters as a new exit E-F7-14 (F7-WO4), Q5.A13 through E-F7-4
(F7-WO3).
