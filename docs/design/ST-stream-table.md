# ST — stream table and energy summary (design note)

**Status:** design, 2026-11-06, design lane (`architect`), one pass. Package ST (ADR 0056 Amendment 1; FB-06, FB-02).
**Decision record:** `docs/adr/0068-stream-table.md` (Proposed; ADR 0019 Amendment 13). This note is the normative
detail the ADR points at. **Inputs:** `docs/briefs/ST-architect.md`, `docs/briefs/ST-recon-digest.md`.

## 1. Problem and scope

A tutorial user needed ~25 lines of internal API (`Iapws95Provider`, `EvaluationContext`, `PropertyRequest`, the phase
chosen by hand) to check H(S5) − H(S1) on a Rankine cycle, and could not find a stream's steam quality (FB-06, FB-02).
Nothing in `src/` returns a derived per-stream value today; only the verifier computes enthalpy flows, inside its checks.

**In scope.** (1) One `Inspection` operation, `get_stream_table(job_id)`, on Python, CLI, HTTP and MCP, computed on read
from the job's run bundle. (2) The document format `stream-table-v1` and its schema. (3) The CLI convenience
`openflowsheet streams` (a job in a project, or a bundle directory; text, JSON or CSV). (4) Catalogue entries for ST's
seven codes. (5) Docs and the MCP tool description.

**Out of scope.** v2 projections through the thermo face (F4; §8 says how this extends); X04's unit conversion; X16's
PFD reports; the web shell (§12 O3); MSG's catalogue internals; dynamic runs (ADR 0066); any change to solving,
verification, providers, models, bundles, manifests, certificates, caches or replay.

## 2. Constraints and invariants

- **C-1 Identity.** F0 (`scripts/corpus_identity.py --check`, M1–M9) stays PASS. ST modifies no file under
  `src/openflowsheet/{verify,thermo,models,run,orchestrator}/` nor `compiled.py` (read-only imports only) and writes
  nothing into a bundle, manifest, certificate, store row or cache. Its tests live outside `M8_FUNCTIONS`, and it adds
  no case to `tests/test_t07_types.py`'s `ROUND_TRIPS`.
- **C-2 Rule C5 and the 0.4 constraints** (`target-architecture.md` §2.6). The values are derived after the solve from
  the verified state, which is the bundle's `solution-state.json`, whose `state_sha256` is the certificate's
  `target_state_sha256`. They come through the legacy providers until F4, are given per phase and per substream, and
  never enter certificate identity. Phases are keyed by Q4.R1's triple (family an open vocabulary), substreams by id,
  and never by a rendered string. A convention id goes with every h and s. The schema grows only additively.
- **C-3 R-924 / MSG C3.** A value that cannot be given is `null` with a typed reason `{code, params}`. Every code has a
  catalogue entry, and nothing is invented: there is no ideal-gas density fallback and no entropy from h.
- **C-4 SI only** (X04 is boundary-only): K, Pa, mol/s, kg/s, kg/mol, J/mol, J/kg, J/(mol K), J/(kg K), m³/mol, kg/m³,
  m³/s, W, W/K. **C-5 Signs:** Q and W are positive into the unit (ADR 0001 D4.1, the verifier's convention; a pump has
  W > 0, a turbine W < 0), and the closure is `(Q + W) − (Ḣ_out − Ḣ_in)`, the verifier's residual sign.
- **C-6 Determinism.** The document is a pure function of (bundle members, provider code and data, package version):
  on one machine two calls give identical canonical bytes. Cross-platform last-ulp differences are allowed, since the
  document is not identity.
- **C-7 Contract** (ADR 0019 and its amendments). One `OPERATIONS` row with right `read` and declared schemas, on all four
  transports (C1). Documents come back as `Projection`s. The closed 15-code `ApiError` enum and `API_EXIT_CODES` are
  unchanged.
- **C-8 No process-global state** (T07 G20). A fresh provider for each call; no cache, no memo, no module-level mutable
  state.
- **C-9 Dormancy** in v1 is `StreamState.is_dormant` (Σn == 0.0), the verifier's own test (ADR 0001 D3.1). It is
  reported as Q1.R4 prescribes: extensive values exactly `+0.0`; T and every intensive `null` with `zero_flow`; P
  reported.

## 3. Decisions (alternatives rejected, with reasons)

**D1 — An operation computed on read; no run artifact.** `get_stream_table` reads `revision.json`,
`solution-state.json`, `solution-certificate.json` and `run-manifest.json` from the job's bundle and computes the
document; nothing is stored. *Rejected: a bundle member written at solve time.* It edits the run path
(`revision_run.py`) and adds a manifest index entry to every new bundle (an M3/M7 and replay-comparison risk). It spends
provider calls on every solve, which studies and optimisation run by the thousand, couples a report failure to a run,
cannot serve 0.3.0 bundles, and freezes values at the solve version's provider (one that later gains `v` would never
fill old tables). *Rejected: both*, which is two sources of truth with no good answer to which is authoritative. The
user's "artifact" is the `stream-table-v1` document format, written to a file by the CLI (§6.3) and not registered in
the store. Its reproducibility comes from the header: provider id, implementation and data hashes, convention,
phase-rule id and package version.

**D2 — The response is a `Projection`; the default depth is 12.** ADR 0019 §4.1 requires every Inspection document to
come back as a bounded `Projection` (`get_artifact`'s pattern: pointer, depth, cursor, limit, size cap 64 KiB).
`LocalApplication._project` bounds the Python result as well. The table is nested 10 deep
(stream → substream → phase → absent → params), so this operation's `depth` defaults to `MAX_DEPTH` (12), not 4. With
4, the default answer would elide every substream. A table above the size cap is read by paging `/streams` (§6.3).
*Rejected:* a typed full-document response, which breaks §4.1's bound and lets the size grow with the flowsheet on MCP;
and a flattened record layout, which still elides phase ids at depth 4 and loses per-substream grouping.

**D3 — ST makes its own provider calls and does not reuse the verifier's helpers.** The helpers (`checks.enthalpy_flow`,
`forms.enthalpy_flow`, `pr_c1.enthalpy_flow`, `thermal.saturated_enthalpy`, `table._phase_enthalpy`) return only a
scalar Ḣ. They also embed verification-tolerance snaps (ε_adm, τ_dew), which are devices for reaching a verdict, not
the semantics of a report, and they differ by basis form. Refactoring them to return decompositions would edit
`verify/`: an M5 numerics risk, and a breach of "never change numerics while changing structure". ST instead issues
**the same provider calls with the same arithmetic order** as the verifier wherever the two decide the same phases
(§4.3), and test G7 proves bitwise equality there. ST imports from `verify` only constants and one function:
`verify.table.{FEED_MODELS, PRODUCT_MODELS, EXTERNAL_DUTY_MODELS, STAGED_DUTY_MODELS, WORK_MODELS}` and
`verify.column.duty`.

**D4 — The phase rule `st-phase-rule-v1`** (§4.2), in this order: dormant; carried saturated split; declared port
phase; fresh TP flash at the stream's own (n, T, P) without a snap. *Rejected:* the verifier's per-form snaps (D3), and
the carried lifted split of legacy flash and heater outlets. That split needs the binding's `LiftedSplit` list, which
`revision.json` does not carry, and at a verified state it equals the fresh flash to within the verifier's own
`independent_split` check, which the table quotes.
*Amended from the ST review, 2026-11-08 (M1, rule R1′):* the first reason was false — `verify_revision` derives the
split list from the parsed revision (`verify/certificate.py:765-770`, `lifted_splits` over `view.instances`) — and the
second holds only where that check ran. Where the `independent_split` row is `not_applicable` for
`temperature_degenerate` or `fresh_flash_unresolved`, the verifier did not flash: it read the carried split. There
R1′ (§4.2) reads it too. Everywhere else the carried lifted split stays rejected, because it would move the
resolved-split streams off the verifier's arithmetic and lose their G7 bitwise status for nothing.

**D5 — Energy: ST's figures at the stored state, beside the verifier's rows quoted verbatim** (§4.5). ST never
re-judges. The certificate's energy rows were judged at the projection x̃ (ADR 0013 D1) when
`transformations.projection.judged_at == "projection"`, so ST reports `judged_at` and the reader knows when the two
are bitwise comparable.

**D6 — Absence is a value with a reason.** Each object carries an `absent` map, quantity name → `{code, params}`. A
quantity is `null` **iff** it has an entry. A derived quantity copies the reason of its first absent input.

**D7 — The CLI** `openflowsheet streams` (§6.3) takes either `--project DIR --job JOB_ID` (the operation, paged
through) or a bundle directory (`inspect`/`replay`'s local pattern, through the same core function). This is one
capability, not a CLI-only one (C1).

**D8 — Seven new codes** (§6.4), registered in MSG's catalogue. No new `ApiError` code.

## 4. The computation (`src/openflowsheet/application/stream_table.py`)

### 4.1 Inputs and entry points

`build(revision, state_doc, certificate, manifest, *, provider, source) -> dict` is pure: no store and no files.
`from_bundle(directory) -> dict` reads the four members of a bundle directory, resolves the provider (below) and calls
`build`. `LocalApplication.get_stream_table` resolves the job's bundle members from the store and calls `build`.

- `view = parse_revision(revision)`, `basis = component_basis(revision)`, `components = view.components` (provider
  order, for every provider call). Output order: `declared = view.input_mapping.declared_components or
  view.components`; every output array is built **by component id**, never by position. `M_c =
  basis.molecular_weights[c]` (kg/mol).
- `state = state_doc["variables"]` (id → float). Precondition: `run.solution_state.inconsistencies(state_doc,
  certificate) == ()`, else `internal_error` with the reasons in `detail`.
- Provider: `application.revision_binding.provider_for(basis)`, a new instance per call (C-8). An `Unbound` is refused
  `unsupported` with message `basis_unavailable(<id>)` and its hint (the existing code). Context: the verifier's own
  (`verify_revision`), `EvaluationContext(model_version=certificate["model_version"],
  constants_sha256=certificate["constants_sha256"], phase_signature=None)`.
- `declared_phase[S]`: `verify.forms.declared_phases(view)`'s logic reimplemented, i.e. the producer's outlet port's
  `instance.phases[port]` (`"LIQUID"`, `"VAPOR"` or `None`). `judged_at =
  certificate.get("transformations", {}).get("projection", {}).get("judged_at")`, or `null` for older certificates.

### 4.2 Phase rule `st-phase-rule-v1` (per stream S; v1 has one substream, id `mixed`, kind `mixed`)

Let `st = StreamState(n=(state[flow_id(S,c)] for c in components), T=state[temperature_id(S)],
P=state[pressure_id(S)])`.

- **R0 dormant** (`st.is_dormant`). `phase_source: "zero_flow"`, `phases: []`, and
  `n_total = m_total = H_flow = S_flow = V_flow = +0.0`. The arrays `n` and `m` are `+0.0` (a stored −0.0 normalised;
  on every stream, not only R0, ADR 0001 D1.5 — D1-10, from the ST review, 2026-11-08),
  and no provider call is made (Q1.R11); `T`, `x`, `w`, `h`, `h_mass`, `s`, `s_mass`, `rho` and both vapour fractions
  are `null`, with `zero_flow(stream=S)`.
- **R1 carried split.** Both `vapor_id(S)` and `liquid_id(S)` are in `state` (thermal saturated streams, ADR 0051 D1).
  It requires `len(components) == 1`; otherwise the result is `internal_error`. `phase_source: "carried_split"`. With
  V = `state[vapor_id(S)]` and L = `state[liquid_id(S)]`, the phases are VAPOR with n = (V,) and LIQUID with
  n = (L,). The properties are evaluated at **(T_sat(P), P)**. T_sat is the provider's `Tsat` from
  `evaluate_phase(PropertyRequest(StreamState((1.0,), T_lo, P), "LIQUID", ("Tsat",)))`, where `T_lo =
  provider.describe().domain["T"][0]`; this is the verifier's `_saturation_temperature`. Each phase request uses the
  state `StreamState((1.0,), T_sat, P)` with the phase's family; the per-mole values do not depend on the amount, which
  is what the verifier's `_properties` assumes. The stream's `T` is the stored T. A `Tsat` status other than `"ok"`
  nulls every property-derived quantity of the substream and its phases with `property_evaluation_failed(stream=S,
  phase=LIQUID, property=Tsat, status=…)`; amounts, compositions and fractions are still given (Q1.R12). A non-finite
  `Tsat` blocks them alike, with `value_not_finite(subject=S, quantity=Tsat)` (D1-12, from the ST review, 2026-11-08).
- **R1′ carried lifted split** (from the ST review, 2026-11-08, M1). *Trigger:* S is the `stream` of a heater-style
  lifted split (its instance lacks the `vapor` + `liquid` port pair, as in the verifier's `degeneracy`), from
  `lifted_splits([(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components)`, the list
  `verify_revision` derives (`staged` omitted: stage keys are never flowsheet streams); and the certificate holds that
  split's **own** row, id `independent_split.<U>.<S>` with U the split's unit as the certificate names it (`unit_ids`),
  built as the verifier builds it and never parsed, with result `not_applicable` and a reason in
  {`temperature_degenerate`, `fresh_flash_unresolved`} (design-lane confirmations, 2026-11-08: a row of another split
  on S, such as a products-style split's on the drum's inlet, does not trigger R1′; see §4.4).
  *Phases:* VAPOR with n = `state[split.vapor]` and LIQUID with n = `state[split.liquid]`,
  both at `(state[split.temperature], state[split.pressure])`, each listed iff its amount is `!= 0.0`. *Ḣ:* the
  per-component form summed **from 0.0**, as `_phase_enthalpy` sums it, then `H_V + H_L` (a mixture-`h` provider's
  phase gives `n_p,tot·h`, as `gamma_phi_units._phase_flow`); bitwise the verifier's value, so these streams are in
  G7's bitwise set. `phase_source: "carried_lifted_split"`; `flash_near_phase_boundary` is false, because nothing was
  flashed; the quoted row stays.
- **R2 declared.** `declared_phase[S]` is not `None`. `phase_source: "declared"`; one phase of that family,
  n = `st.n`, at (T, P).
- **Unlifted** (design-lane confirmations, 2026-11-08). A stream the verifier left unlifted, that is S such that some
  certificate row's `reason` equals `temperature_degenerate_unlifted(<S>)` exactly (`verify.table.blocked_check`,
  T05b spec §9.2), is not flashed: `phases: []`, `phase_source: "flash"`, `flash_near_phase_boundary: false`, and its
  phase-derived quantities are null with `flash_failed(stream=S, status="temperature_degenerate")`. Only undeclared
  streams are unlifted, so this follows R2. It is unreachable while the binder admits `vapor_liquid` only on a
  heater-style `outlet` port (`instance_contract`, R4's converse); it is kept so that the path is never silent.
- **R3 flash.** In every other case, `provider.flash(FlashRequest(state=st), context)`, and `phase_source: "flash"`.
  If the status is not `"ok"`, then `phases: []`, and every phase-derived quantity (`h`, `h_mass`, `s`, `s_mass`,
  `rho`, `H_flow`, `S_flow`, `V_flow`, the vapour fractions) is `null` with `flash_failed(stream=S, status=…)`.
  `n`, `m`, `x`, `w`, `T` and `P` are still given. If the status is `"ok"`, the phases are VAPOR from `result.vapor`
  and LIQUID from `result.liquid`, each with its outlet `n` in provider order, at the stream's (T, P). There is **no
  snap**. The substream's `flash_near_phase_boundary` is true iff two or more phases are listed and min_p |n_p,tot|/N_P
  ≤ τ_β = 1e-8 (Q4.R12 (b) (i)); it is false for R0–R2. Q4.R12 (b) (ii) (a quoted degeneracy `independent_split`
  row) is withdrawn (design-lane confirmations, 2026-11-08): a heater-style split's own such row decides the stream by
  R1′, and a products-style split's, which can reach R3 on the drum's inlet, judges the inlet's composition at the
  drum's (T, P), not the inlet's state, which the verifier flashes like any other.
- **Listing.** A phase is listed iff it exists and its total amount is `!= 0.0` (either sign, never clamped; ids never
  renumbered; Q4.R11), ordered VAPOR, LIQUID (registered family order VAPOR, LIQUID, FLUID, SOLID; within a family by
  ordinal). Its id is `{family, qualifier: null, ordinal: 1}`.

### 4.3 Property calls and formulas (per listed phase p with amounts n_p in provider order)

- **h (required).** Call `evaluate_phase(PropertyRequest(state_p, family, ("h",)), context)` alone, exactly as the
  verifier does. If `"h"` is in `values` (mixture form): `n_p,tot = sum(n_p)` (Python `sum`, provider order) and
  `H_p = n_p,tot * values["h"]`. Else, if every `f"h_{c}"` is present (SYN-001's ideal-solution form):
  `H_p = Σ_c n_p,c * values[f"h_{c}"]` in provider order, summed as the verifier's helper of that form sums it (D1-1,
  from the ST review, 2026-11-08): built-in `sum` (Neumaier-compensated since Python 3.12; `requires-python >=3.13`)
  as `checks.enthalpy_flow`, and a 0.0-loop as `_phase_enthalpy` for R1′. Else `property_not_provided`. In both forms
  `h_p = H_p / n_p,tot`; for R1, `n_p,tot` is V or L.
- **s, v (optional).** Requested only if declared in `describe().properties`, each in its **own** call
  `(…, ("s",))` / `(…, ("v",))`; otherwise `property_not_provided(provider, property)`. Only the mixture key is
  accepted. A per-component `s_c` or `v_c` gives `property_not_provided`, because such a key does not say whether it
  holds a pure-component or a partial molar value, and summed pure-component values drop the entropy of mixing (s) or
  the excess volume (v) (Q2.R11). Then `S_p = n_p,tot * s_p` and `V_p = n_p,tot * v_p` (m³/s).
- A status other than `"ok"` gives `property_evaluation_failed(stream, phase=<family>, property, status)`. A
  non-finite result gives `value_not_finite(stream, quantity)`.
- **Mass and composition.** `m_p,c = M_c * n_p,c`; `m_p,tot = Σ_c m_p,c` (provider order); `x_p,c = n_p,c / n_p,tot`;
  `w_p,c = m_p,c / m_p,tot`.
- **Phase intensives.** `h_mass_p = H_p / m_p,tot`; `s_mass_p = S_p / m_p,tot`; `rho_p = m_p,tot / V_p`;
  `phase_fraction_molar = n_p,tot / N_P`; `phase_fraction_mass = m_p,tot / M_P`, with N_P = Σ_p n_p,tot and M_P = Σ_p
  m_p,tot over the listed phases from 0.0 in listing order (Q4.R10).
- **Substream totals.** `n_tot = sum(st.n)`, `m_tot = Σ_c M_c n_c`. `H_flow = Σ_p H_p`, accumulated from `0.0` over
  the listed phases in order, which is the verifier's `total += …` for R3 and `V·h_V + L·h_L` for R1 (VAPOR first). For
  R1 that reads `0.0 + V*h_V + L*h_L`, which is bitwise `V*h_V + L*h_L` since `0.0 + a == a`. `S_flow` and `V_flow`
  are accumulated the same way. Then `h = H_flow/n_tot`, `h_mass = H_flow/m_tot`, `s = S_flow/n_tot`,
  `s_mass = S_flow/m_tot`, and `rho = m_tot/V_flow`.
- **Vapour fractions.** `vapor_fraction_molar = (Σ_{p in the vapour group} n_p,tot)/N_P` and `vapor_fraction_mass = (Σ
  m_p,tot)/M_P`, accumulated from 0.0 (v1: the vapour group is VAPOR); exactly 0.0 with no VAPOR listed and 1.0 with
  VAPOR alone, in [0, 1] when no listed amount is negative, bitwise the VAPOR `phase_fraction_molar`; null only for R0,
  a failed flash or a non-finite quotient (Q4.R10).
- **Quotients.** Every division in §4.3 is an IEEE division: a non-finite result (for example a zero mass after
  underflow) is null with `value_not_finite(subject, quantity)`, never an exception (Q4.R11 (c)).
- **Order of output arrays.** Each array follows the substream's `components` (= `declared`), filled by id.

### 4.4 Quoted checks

Each stream carries `checks`: every certificate row with `category` in {`phase_admissibility`, `independent_split`} and
`subject == S`, in certificate order. Each unit carries the rows with `category == "energy_balance"` and `subject == U`;
the overall section carries the row `id == "energy_balance.envelope"`. A quote is `{index, id, result, scope, value,
tolerance, reason, near_threshold}`, where `index` is the row's position in the certificate's `checks` array, so the
full row is at `get_artifact("<bundle>/solution-certificate.json", pointer="/checks/<index>")`.
A products-style split's rows have the drum's inlet as subject (`LiftedSplit.stream`), so they are quoted on the inlet,
but they judge the inlet's composition at the drum's (T, P) and do not enter the inlet's phase rule (§4.2; design-lane
confirmations, 2026-11-08).

### 4.5 Energy summary (computed at the stored state)

- `units`: every instance in declaration order **except** models in `FEED_MODELS ∪ PRODUCT_MODELS`.
  - `ports`: for each `port` in `instance.ports` order, `{port, direction, streams, H_flow}`, with
    `H_flow = Σ H_flow(S)` from 0.0 in stream order.
  - `H_in`, `H_out`: the sums of the port `H_flow`s by direction, in port order.
  - `Q`: for a model in `EXTERNAL_DUTY_MODELS`, `state[duty_id(U)]`; in `STAGED_DUTY_MODELS`,
    `verify.column.duty(instance, state, view.components)`; otherwise `0.0`. A heat exchanger's internal `<U>.Q` is
    not external and is visible through `ports`.
  - `W`: for a model in `WORK_MODELS`, `state[work_id(U)]`; otherwise `0.0`.
  - `closure = (Q + W) − (H_out − H_in)`, computed **iff** the unit has at least one quoted energy row (the verifier has
    an energy form for its model). Otherwise it is null, with `energy_balance_undefined(unit, model)`, even when a
    stream Ḣ is also absent (D1-13, from the ST review, 2026-11-08). An absent stream Ḣ makes `H_in`, `H_out` and `closure` null, with
    `stream_enthalpy_absent(subject=U, streams=[…])`; the port's `H_flow` carries the same entry in its own `absent`
    (D1-6).
- `overall`: `feeds` lists the outlet-port streams of `FEED_MODELS` instances, and `products` the inlet-port streams of
  `PRODUCT_MODELS` instances (declaration order, port order, stream order: the verifier's `_feeds` and `_products`).
  `Q = Σ` over instances (one loop; EXTERNAL → `state[duty_id]`, STAGED → `column.duty`), `W = Σ` over WORK
  instances, `H_feeds` and `H_products` accumulated from 0.0, and
  `closure = (Q + W) − (H_products − H_feeds)`. That is `_envelope_energy`'s arithmetic, in the same order. A
  closed loop has empty lists and a closure of `Q + W`.
- `convention` (the provider's), `judged_at`, and `verification_status` (the certificate's) sit beside them: `energy`
  holds `{convention, units, overall}`, and `judged_at` and `verification_status` sit at the document root, §5's
  layout (D1-11, from the ST review, 2026-11-08).

## 5. The document `stream-table-v1` (`_data/schemas/stream-table.schema.json`)

JSON Schema 2020-12 under the repository's `$id` base. *Open* objects are header, stream, substream, phase, unit and
overall: they have no `additionalProperties: false`, so a v1 validator accepts v2 additions. *Closed* objects are the
phase id, the absent entry and the check quote. A non-additive change requires `stream-table-v2`. `q` means
`number | null`.

```
root: {schema_version: "stream-table-v1",
  source: {job_id: str|null, bundle_id: str|null, run_id: str|null, revision_id: str},
  state_sha256: str, certificate_id: str, verification_status: str, judged_at: str|null,
  basis: {provider_id, implementation_sha256, data_sha256, convention, record_source},      # all str
  evaluator: {phase_rule: "st-phase-rule-v1", package_version: str},
  components: [{id: str, molar_mass: number}],                                             # declared order
  streams: [stream], energy: {convention: str, units: [unit], overall: overall}}
stream: {id, from: str|null, to: str|null, T: q, P: number, dormant: bool,
  substreams: [substream], checks: [quote], absent: {name: entry}}
substream: {id: "mixed", kind: "mixed", components: [str], convention: str,
  phase_source: str  (registered: zero_flow | carried_split | carried_lifted_split | declared | flash; open),
  flash_near_phase_boundary: bool,
  n: [number], m: [number], x: [q]|null, w: [q]|null, n_total, m_total: number,
  H_flow, S_flow, V_flow, h, h_mass, s, s_mass, rho, vapor_fraction_molar, vapor_fraction_mass: q,
  phases: [phase], absent: {name: entry}}
phase: {id: {family: str ^[A-Z][A-Z0-9_]*$, qualifier: str|null ^[A-Za-z0-9_.:-]+$, ordinal: int>=1},
  n, m: [number], x, w: [q]|null, n_total, m_total: number, phase_fraction_molar, phase_fraction_mass: q,
  H_flow, S_flow, V_flow, h, h_mass, s, s_mass, v, rho: q, absent: {name: entry}}
entry: {code: str, params: {str: str|number|[str]}}
# D1-6, D1-7 (from the ST review, 2026-11-08): a port carries `absent` (null iff absent holds); a phase's `x` and `w` are given or null
# whole, and its fractions are `q` (Q4.R11 (c), Q4.A14 (d): an underflowed phase mass).
quote: {index: int, id, result, scope: str, value, tolerance: q, reason: str, near_threshold: bool}
unit: {id, model: str, ports: [{port, direction: "inlet"|"outlet", streams: [str], H_flow: q,
  absent: {name: entry}}],
  H_in, H_out: q, Q, W: number, closure: q, checks: [quote], absent: {name: entry}}
overall: {feeds, products: [str], Q, W: number, H_feeds, H_products, closure: q, checks: [quote],
  absent: {name: entry}}
```

`x`/`w` are `null` (one absent entry each) for R0. The `convention` on a substream applies to every `h`, `h_mass`, `s`,
`s_mass`, `H_flow` and `S_flow` in it and in its phases (C5: "with each h and s"). Test-level invariant, which the
schema cannot express: a quantity is `null` iff it is a key of its object's `absent`; arrays are null as a whole.

## 6. Surfaces

### 6.1 Operation (ADR 0019 Amendment 13)

`Inspection.get_stream_table(job_id: str, *, pointer: str = "", depth: int = 12, cursor: str | None = None, limit:
int = 50) -> Projection`. Its `OPERATIONS` row comes **immediately after `get_artifact`**:
`_row("get_stream_table", "read", _object({"job_id": ID}, VIEW_MEMBERS), _result("projection"),
("GET", "/v1/jobs/{job_id}/stream-table"), decode=_members("job_id", *_VIEW))`. It is on all transports; the MCP tool
`get_stream_table` uses `bindings/descriptions/get_stream_table.md`. `authz.OPERATION_RIGHTS["get_stream_table"] =
"read"`, and `read` covers every principal's job (as with `get_artifact`). The `Projection` has
`subject_id = "stream-table:<job_id>"` and `sha256 = canonical.document_sha256(document)`.

**Refusals**, all existing codes: an unknown job is `not_found`; a job not yet ended is `not_ready`; no
`replay_bundle` output, or a missing member, is `not_found` with MSG's member detail (`bundle_id, member, members,
job_id, run_outcome`), the same helper as `get_artifact`; an unavailable basis is `unsupported` with
`basis_unavailable(<id>)`; an inconsistent bundle is `internal_error`.

### 6.2 Python

The method above. `application.stream_table.from_bundle(directory)` is a documented library helper (not contract) for
bundle directories; 0.3.0 bundles included. A directory's `source` has `job_id` and `bundle_id` null, and its
`not_found` detail uses MSG's member fields (`bundle_id, member, members, job_id, run_outcome`) with nulls for what a
directory lacks (D1-14, from the ST review, 2026-11-08). With the bundle's `solve-path.json`, the recorded route keys the units (S4).

### 6.3 CLI

`openflowsheet streams (--project DIR --job JOB_ID | BUNDLE_DIR) [--format text|json|csv] [--output PATH]`. Default
`text`; `--output` writes the file and prints nothing else. Exit codes come from the existing `API_EXIT_CODES`, by
`ApiError` code.

- **Project mode (paging).** Call `get_stream_table(job_id)`. If `truncated`, page `pointer="/streams"` with `cursor`
  until `next_cursor is None`, fetch `pointer="/energy"`, and assemble. Every page must carry the same `sha256`, else
  `internal_error`.
- **json.** `canonical_json` of the full document, followed by a newline.
- **csv.** RFC 4180, one row per (stream, substream, phase-or-total), in document order with the total first. Columns:
  `stream,substream,phase_family,phase_qualifier,phase_ordinal,T_K,P_Pa,n_total_mol_s,m_total_kg_s,
  phase_fraction_molar,vapor_fraction_molar,vapor_fraction_mass,h_J_mol,h_J_kg,s_J_molK,s_J_kgK,v_m3_mol,rho_kg_m3,
  H_flow_W,S_flow_W_K,V_flow_m3_s`, then `n_<c>_mol_s` and `x_<c>` for each component in `components` order. A total
  row has empty phase columns; a phase row has empty vapour-fraction columns and repeats the stream's `T` and `P`.
  Floats use `repr(float)`; an absent value is an empty cell.
- **text.** A header (job, run, revision, basis, convention, verification status, `judged_at`, `SI units`), then stream
  blocks of up to 6 columns: a label column 18 wide, value columns 14 wide, right-aligned. Rows: `T [K]`, `P [Pa]`,
  `n [mol/s]`, `m [kg/s]`, `x[<c>]`…, `vf molar`, `vf mass`, `h [J/mol]`, `h [J/kg]`, `s [J/(mol K)]`,
  `s [J/(kg K)]`, `rho [kg/m3]`, `H [W]`, `phases` (families joined by `+`, rendered `VAPOR` and `LIQUID` per Q4.R7;
  `FAMILY(q).k` is reserved for v2). Values use `{:.6g}`; an absent value is `-` with a footnote mark `*n`. Then the
  energy table, one row per unit (`unit, model, H_in, H_out, Q, W, closure, verifier`, the last being the quoted rows'
  results), then `overall`, then the footnotes, one per distinct (code, params), as `*n code(param=value, …)`. When
  the status is not `VERIFIED`, the first line is `WARNING: verification_status is <s>`.

### 6.4 Catalogue codes (MSG C3; complete entries, with an example each)

| code | params | family / kind |
| --- | --- | --- |
| `zero_flow` (reuse the entry if MSG has one; add `stream`) | `stream` | notice / notice |
| `property_not_provided` | `provider`, `property` | refusal / not_supported; gap `{limitation: null, capability: "this property from the flowsheet's property basis"}` (D4-1, from the ST review, 2026-11-08) |
| `property_evaluation_failed` | `stream`, `phase`, `property`, `status` | refusal / numerical |
| `flash_failed` | `stream`, `status` | refusal / numerical |
| `value_not_finite` | `subject`, `quantity` | refusal / numerical |
| `stream_enthalpy_absent` | `subject`, `streams` (list) | notice / notice; `see_also` the four above |
| `energy_balance_undefined` | `unit`, `model` | refusal / not_supported; gap `{limitation: null, capability: "an energy balance check for this unit's model"}` (D4-1, from the ST review, 2026-11-08) |

## 7. Identity and migration

- **No identity measure can move.** No revision, compile, run, bundle, manifest, certificate, cache key or replay
  path is touched, so M1–M7 and M9 cannot change. M8 cannot either: no fixture goes under an `M8_FUNCTIONS` collector
  and no `ROUND_TRIPS` case is added. F0 is still run as the proof (G13). **0.3.0 bundles and stores:** nothing new is
  stored, so a 0.3.0 job is served by the same path as a 0.4 one; `judged_at` is null when the certificate predates it.
- **Moves, all additive.** One `OPERATIONS` row; `OPERATION_RIGHTS` +1; `schemas/registry.json` +1 entry; a new schema
  file. The served MCP tool list moves by one tool: without `get_stream_table` it equals main's digest at ST's branch
  point. There is one new R4-G3 response snapshot, and `docs/interfaces-frozen.md` gains a paragraph. Every existing
  schema is byte-identical.

## 8. How v2 extends this (additively, no new operation)

`substreams[].method` is added, and the header `basis` stays for v1 documents. Every h and s is on the flowsheet
convention (Q2.R1, R6); per-method subtotals become attribution members. `phase_source: "state_point"` reads the phases
from the solved state point's phase set (Q4/Q5) instead of re-flashing. FLUID phases gain `character`, read from the
state point; the vapour fractions count Q4.R13's vapour group (VAPOR and `vapour_like` FLUID) over all listed phases, a
SOLID phase included by default (Q4.R10, O-20); `flash_near_phase_boundary` is false for `state_point`, whose own flags
are added beside it (Q4.R12 (e)). The `solid` and `nonconventional` substream kinds arrive with their attributes, and
dormancy becomes per substream (Q1.R4). `h_mass` is read from the state's ĥ (Q1.R1). The `entropy_datum` notice (Q2.R10)
attaches through a sibling `notices` map. Dynamic runs add `time_s` as a request and header member (F7). `build` gains a
v2 branch keyed on the revision's definition; the operation, the transports and every v1 member stay as they are.

## 9. Files

**New:** `src/openflowsheet/application/stream_table.py`; `_data/schemas/stream-table.schema.json`;
`application/bindings/descriptions/get_stream_table.md`; `tests/test_st_{core,schema,cli,operation}.py`;
`tests/fixtures/st/{valid,invalid}/*.json`; `docs-site/guide/stream-table.md`. **Edited, shared with MSG's build**
(merge hazard): `application/{contract,local,operations,authz,cli}.py`, `_data/schemas/registry.json`,
`messages/catalogue/{notices,refusals}.yaml`, `tests/test_t08_w2_surface_digest.py` (both re-record the digest), the
R4-G3 snapshot files, the §4.3 table `test_the_table_is_section_4_3s` compares against, `docs/interfaces-frozen.md`,
`docs/adr/0019-application-contract-v1.md` (pointer paragraph), `mkdocs.yml`, `docs/decision-register.md`,
`docs/progress.md`. **Edited, not MSG's:** the conformance and transport tests' request fixtures (a `get_stream_table`
request on an ended job). **Rule:** WO-1 touches only new files and may start now; WO-2 onward starts after `wp/MSG`
merges into `main` (merge `main` into `wp/ST` first).

## 10. Work orders (`wp/ST`; identity "no" for all, proven by G13)

| WO | Content and files | Acceptance | Who |
| --- | --- | --- | --- |
| 1 | Core: `application/stream_table.py` (`build`, `from_bundle`, §4), `tests/test_st_core.py` | G1–G10, G14, G16 at core level; no `verify/thermo/models/run` diff | Opus |
| 2 | Schema (§5) + `tests/test_st_schema.py` + fixtures (valid: one per basis from WO-1 output; invalid: a rendered phase key, null without `absent`, missing `convention`, `family` lower-case, extra member in a phase id); registry entry | every WO-1 corpus document validates; each invalid fixture rejected; F0 PASS | Sonnet |
| 3 | Operation (§6.1): contract, local, operations, authz (+pin test), HTTP, MCP; `tests/test_st_operation.py`; transport and conformance fixtures; digest and R4-G3 re-record; interfaces-frozen paragraph | G11, G12, G13 | Opus |
| 4 | Catalogue entries (§6.4) | G15; MSG's lint (G4) on the entries | Sonnet drafts, Opus checks |
| 5 | CLI `streams` (§6.3) + `tests/test_st_cli.py` (goldens for TH-C1 in all three formats, project and directory modes equal, paging assembly with a forced `limit=1`) | goldens; exit codes; json output equals the operation's document | Sonnet |
| 6 | Docs: guide page (the FB-06 recipe becomes one call), CLI reference, MCP description, ADR 0019 pointer paragraph, `mkdocs.yml` | `test_doc_pages.py`; description reviewed in ST's reviewer pass | Sonnet |
| 7 | Evidence manifest, full gate, F0, CI on both architectures, reviewer | §11 all; manifest `status: tested` | Opus |

## 11. Verification gates

The corpus is F0's RC bundle set plus TH-C1 (`benchmarks/s11/thermal/TH-C1.json`) plus one solved revision per basis
(SYN-001, pr-c1-v1, iapws95-v1, wilson-ig-v2, and coolprop-heos-v1 where the extra is installed; where it is not, the
`basis_unavailable` refusal is asserted instead).

- **G1 Rankine energy (TH-C1, IAPWS-95; F→P→B→T→C→K, S1…S5).** For P, B, T and C, `|closure_U| ≤` the tolerance of
  its quoted energy row. `|(H(S5) − H(S1)) − (Q_B + Q_C + W_P + W_T)| ≤` the envelope row's tolerance. Signs:
  `W_P > 0`, `W_T < 0`, `Q_B > 0`, `Q_C < 0`. Record max |closure|/tol.
- **G2 lever rule (S4, R1).** `x_lever = (h4 − h_L)/(h_V − h_L)`, where `h4 = (H(S3) + W_T)/n4` and `h_L`, `h_V` are
  evaluated **by the test directly** with `Iapws95Provider` at `(T_sat(P4), P4)`. Require
  `|vf_molar(S4) − x_lever| ≤ 10·tol_T/(n4·(h_V − h_L)) + 1e-12` (`tol_T` from the turbine row) and `|vf_mass −
  vf_molar| ≤ 8ε·vf_molar` (worst case 3ε, §17 argument 9). S5 (`outlet_vapor_fraction 0`): `vf_molar = V5/(0.0 + V5 +
  L5)` bitwise, and `|h(S5) − h_L(P5)| ≤ (|V5|(h_V − h_L) + |V5 + L5 − n5|·|h_L|)/n5 + 8ε|h_L|` (the bounds checks admit
  |V5| up to τ_flow; record |V5|/n5).
- **G3 saturation reference.** `build` on TH-C1's revision with S4 overwritten to `P = 932203.564 Pa`,
  `V = L = 0.5 mol/s` and `n = 1.0`, against IAPWS-95 R6-95(2018) Table 8 at 450 K, relative error ≤ 1e-7:
  h′ 749.161585 and h″ 2774.41078 kJ/kg; s′ 2.10865845 and s″ 6.60921221 kJ/(kg K); ρ′ 890.341250 and
  ρ″ 4.81200360 kg/m³. `vf_molar == 0.5` exactly. O6 governs the source of these values. S4's stored T is kept and `|T −
  450 K| > 100 K` asserted (Q1.A15 (a)).
- **G4 limiting cases.** A dormant stream: `n_total`, `m_total`, `H_flow`, `S_flow` and `V_flow` `== +0.0` (sign
  checked), `T` null with `zero_flow`, `P` present, `phases == []`. A single-phase stream: vapour fraction exactly 0.0
  or 1.0. On SYN-001 (all M = 0.1 kg/mol): `|w_c − x_c| ≤ 8ε·x_c` (worst case 4ε). Q1.A14; Q4.A13 (b), (f); Q4.A14 (d).
- **G5 absence.** Over every corpus document: null ⇔ an `absent` key; every code is a catalogue key; no NaN or inf;
  canonical JSON succeeds. Q2.A13.
- **G6 consistency.** `|Σx − 1|` and `|Σw − 1| ≤ 1e-12`. The substream `H_flow` equals the sum of its phases' bitwise.
  R3 phases sum to the stream's `n_c` within `1e-12·n_total`; R1 `V + L` equals `n` within `1e-9·n`.
  `0 ≤ vf ≤ 1` exactly where no listed amount is negative, otherwise within Σ|negative amounts|/N_P of [0, 1] (Q4.R10,
  R11; Q4.A13 (a), (d)). On SYN-001 R3 two-phase streams: the Rachford–Rice residual `|Σ z_i(K_i−1)/(1+β(K_i−1))| ≤
  1e-10`, and `y_i = K_i x_i` to 1e-9 relative, with K from the provider's `lnK` at (T, P). This catches a swap of the
  VAPOR and LIQUID outlets.
- **G7 verifier equivalence (bitwise), same state and context.** In the test only, call the verifier helper of the basis
  form: R1 `thermal.saturated_enthalpy`; R1′ `table._phase_enthalpy` (V) + (L) at the split's `(T, P)` (the ST
  review, 2026-11-08); R2 on DECLARED_MIXTURE and GAMMA_PHI forms `forms.enthalpy_flow`; R3
  single-phase flashes `checks.enthalpy_flow` (SYN) and `pr_c1.enthalpy_flow` (PR). ST's `H_flow` must equal the
  helper's result bitwise for every such stream; the other cases are counted and reported. Q1.A15 (c); Q4.A14 (a)–(c).
- **G8 envelope agreement.** Where `judged_at == "final_state"` and every envelope stream is G7-bitwise,
  `overall.closure ==` the quoted value bitwise. Otherwise `|overall.closure − value| ≤ tolerance`, and the max ratio
  is recorded. A failure is escalated, never loosened.
- **G9 determinism.** Two in-process calls, and two fresh processes, give identical canonical bytes and
  `Projection.sha256`.
- **G10 0.3.0 bundles.** Every bundle under `tests/fixtures/f0/v0.3.0-bundles/**` that has the four members gives a
  schema-valid document satisfying G5 and G6. Any other bundle is refused `not_found` naming the missing member;
  report both counts.
- **G11 transports.** `test_g14_every_transport_equals_dispatch`, `test_every_cli_operation_through_api_equals_dispatch`
  and `test_every_operation_succeeds_through_dispatch_and_meets_its_response_schema` all pass with the new row. Each
  refusal of §6.1 is asserted on every transport.
- **G12 surfaces.** The MCP digest without the new tool equals the pre-ST digest, and the new digest is recorded. Every
  existing R4-G3 snapshot and `API_EXIT_CODES` are unchanged. `git diff main -- src/openflowsheet/_data/schemas/` shows
  only `registry.json` and the new file.
- **G13 identity.** `scripts/corpus_identity.py --check` PASS after WO-1, WO-3 and at merge. `git diff main --stat --
  src/openflowsheet/{verify,thermo,models,run,orchestrator} src/openflowsheet/compiled.py` is empty.
- **G14 performance.** `get_stream_table` takes ≤ 0.5 s on TH-C1 and ≤ 2 s on the largest corpus case (reference
  machine), recorded. If exceeded, report; no cache may be added without a design decision.
- **G15 C3.** MSG's runtime audit passes over the whole suite with ST's emissions.
- **G16 The report's decision near a phase boundary.** Q4.A15 (a)–(e); the counts of (e) recorded in the manifest.

## 12. Risks and open questions (each with a default)

- **O1 (fact)** Does a `schemas/registry.json` entry move F0 or an environment hash? *Default:* add it; F0 after WO-3
  decides. On failure, move the schema to `application-results.schema.json#/$defs/stream_table` in one logged commit.
- **O2 (fact)** Does a contract test pin every view operation's default depth at 4? *Default:* 12. If one does, keep 4,
  document `depth=12` in the description and guide, and log it.
- **O3 (preference)** Web-shell display. *Default:* later (X16 or a follow-up); the streams screen keeps n, T, P.
- **O4 (preference)** CSV in scope. *Default:* yes (FB-06 asked for an artifact; about 40 lines).
- **O5 (fact)** Is TH-C1's S4 R1? Its specification (η 0.85, 10 kPa) makes it wet. *Default:* assert it. If not, G2
  takes the first registered thermal case with an R1 stream, else a test-local variant with a lower boiler T.
- **O6 (fact) — resolved 2026-11-06 (orchestrator).** The G3 constants agree with the committed S05 reference
  `docs/derivations/scripts/s05_reference.json` `/saturation/450` (mpmath, independent of production code; registered
  against R6-95(2018) Table 8 to 9 figures by `docs/derivations/S05-IAPWS95-spec.md:660`): ρ′ 890.34124976, ρ″
  4.81200360, h′ 13496.3467 J/mol = 749.1616 kJ/kg. G3 reads its expectations from that file (molar values, converted
  with M = 0.018015268 kg/mol), not from literals. If the provider differs by more than 1e-7 relative, stop and report;
  never adjust the expectations.
- **O7 (preference)** `from_bundle` public. *Default:* yes, documented as a library helper outside the frozen contract.
- **O8 (fact)** Coupled runs. *Default:* served when the four members exist; an external unit has no energy row, so its
  closure is `energy_balance_undefined`.
- **Riskiest point.** Near a phase boundary, R3's raw flash can decide differently from the verifier's snapped
  decision, so ST's Ḣ and vapour fraction may differ slightly from what was judged. A second hazard is the two
  provider value shapes (`h` against `h_<c>`). Mitigations: the quoted checks, `judged_at`, and G6–G8. Ruled by Q4.R12
  (Amendment 5): the raw flash stays; `flash_near_phase_boundary` and the quoted `independent_split` rows mark where the
  verifier may have decided otherwise; G16. *Scope of Q4.R12 (a), from the ST review, 2026-11-08:* the raw flash stays
  wherever the verifier could flash. Where it could not, R1′ reads the carried lifted split (a heater-style split's own
  degeneracy `independent_split` row), or the table gives no number (a stream the verifier left unlifted); design-lane
  confirmations, 2026-11-08. *Rejected:* (a) exempting a flagged envelope from G8, which would loosen a gate
  around a wrong number (`T05b:SC-1`'s S2 was 2016 W low with a vapour fraction of 0); and reading every lifted split.

## 13. Specifier questions (scientific semantics; the default applies until ruled)

**SQ-ST-1** Vapour fraction on both bases (`vapor_fraction_molar`, `vapor_fraction_mass`) over the VAPOR family; no
member named "quality"; 0 or 1 outside the dome, not undefined. **SQ-ST-2** A dormant stream's `T` is `null`
(`zero_flow`, Q1.R4), not the stored label. **SQ-ST-3** Undeclared, unsplit streams take R3's raw TP flash, with no
ε_adm or τ_dew snap. **SQ-ST-4** An R1 phase is evaluated at `(T_sat(P), P)` (the verifier's choice), not at the
stored T. **SQ-ST-5** Density only from a provider's `v`, with no ideal-gas fallback; the per-component property form
is accepted for `h` only (ideal-solution additivity), never for `s` or `v`. **SQ-ST-6** A phase is listed iff its
amount is `!= 0.0`; a saturated liquid with V = 0 shows one phase, and its vapour fraction is still defined (0.0). Ruled
2026-11-06 (foundation rulings Amendment 5): SQ-ST-1 Q4.R10, SQ-ST-2 Q1.R11, SQ-ST-3 Q4.R12, SQ-ST-4 Q1.R12, SQ-ST-5
Q2.R11, SQ-ST-6 Q4.R11.

## Amendment — design-lane confirmations (2026-11-08)

Ruled in `docs/reviews/ST-review.md` §Design-lane confirmations (rulings 3 and 5). A products-style split's
`independent_split.<U>.<S>` row has the drum's inlet as subject but says nothing about the inlet's own Ḣ, and the
verifier's `unlifted` streams carry no `independent_split` row. Replaced text, verbatim:

- §4.2 R1′ trigger: "and the certificate holds an `independent_split` row with subject S, result `not_applicable` and
  a reason in {`temperature_degenerate`, `fresh_flash_unresolved`}." Now: that split's own row,
  `independent_split.<U>.<S>`.
- §4.2 R1′, last sentence: "**A flagged stream that reaches R3 with no such split** (the verifier's `unlifted` case)
  is not flashed: `phases: []`, and its phase-derived quantities are null with `flash_failed(stream=S,
  status="temperature_degenerate")`." Now: the **Unlifted** bullet after R2, keyed on the reason
  `temperature_degenerate_unlifted(<S>)`.
- §4.2 R3: "Q4.R12 (b) (ii) (a quoted degeneracy `independent_split` row) no longer reaches a flash: since the ST
  review (2026-11-08), R1′ decides every such stream." Now: (b) (ii) withdrawn, with the reason.
- §12 Riskiest point: "Where it could not (a degeneracy `independent_split` row), R1′ reads the carried lifted split,
  or gives no number." Now: R1′ for a heater-style split's own row; no number for an unlifted stream.
- §4.4: one sentence added (a products-style split's rows are quoted on the inlet and do not enter its phase rule).

No served document, G7, G8 or G8u result moves (the review's §Design-lane confirmations, F3 and Acceptance).
