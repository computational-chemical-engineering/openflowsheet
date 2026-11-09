# ADR 0075 — X04: units at the boundary — display conversion, display preferences, the project ambient pressure

**Status:** **Accepted (Frank Peters, 2026-11-09).** Proposed 2026-11-09.
- Frank's answers on the decision board, 2026-11-09 (`docs/roadmap/decisions.md`): ADR 0075 accepted; FQ1, FQ2 and FQ3
  **default**; FQ4 **the alternative** — human text shows `°C` and `°F`, machine members keep `degC` and `degF` (D7.7).
- It takes effect on `main` when X04's manifest is `tested` with the `reviewer` pass done; X04 is built on `wp/X04`.
  Register entries R-1010 (surface link c_8) and R-1011…R-1016 (D1–D10) are Accepted with it.
**Author:** design lane (`specifier`). **Brief:** `docs/briefs/X04-specifier.md`.
**Normative text:** this ADR (D1–D11) and `docs/derivations/X04-test-specification.md` (assertions A1–A40, work orders
WO-1–WO-5). **Reference:** `docs/derivations/scripts/x04_reference.json`, emitted by
`docs/derivations/scripts/x04_reference.py` (`--check`: 17 claims, byte-identical re-emission).
**Amends (each additive):**
- ADR 0019 D1, as **ADR 0019 Amendment 17**: `JobControl.get_job_result` and `Inspection.get_stream_table` gain the
  keyword `display_units: str | None = None`; their request schemas gain the optional member `display_units`; their
  responses gain optional display members (D7); `application-results.schema.json#/$defs/project_summary` gains the
  required, nullable member `ambient_pressure` (D6); `#/$defs/explanation`'s `numbers` item gains the optional member
  `display`. On acceptance a pointer paragraph is added to ADR 0019 in the form of Amendment 4. Amendment 14 stays
  reserved for X05's Q-F3; 15 and 16 are X02's and OPT's.
- `schemas/project-policy.schema.json` (`project-policy-v1`): the optional member `ambient_pressure` (D6).
- `schemas/stream-table.schema.json` (ADR 0068, `stream-table-v1`): the optional members `display` (stream, substream,
  phase, port, unit, overall) and `display_units` (root). These objects are open, so every v1 validator already
  accepts them; the schema states them for readers.
- MSG design note §4.5 "X04 slot" (ADR 0058): filled as that note planned — `RenderContext.display_units` is set and
  each `numbers` item may carry `display: {value, unit}`; the SI `value` and `unit` stay.
- `docs/interfaces-frozen.md`: a paragraph for this ADR (the build lane, with the commit that lands WO-3).
- *(Note, design lane, 2026-11-09; X04 D-21/D-22.)* `schemas/message-catalogue.schema.json` (ADR 0058,
  `openflowsheet-messages-v1`): the param `type` enum gains `display_unit`, a display unit whose rendered text is
  `units.display.text_unit` of its value (`degF` → `°F`, D7.7); its `!raw` rendering and the param value itself keep
  the D2 spelling. Every existing catalogue stays valid, and MSG's catalogue table (`docs/design/MSG-messages.md`)
  lists the type. `explain`'s `params[].type` is an unconstrained string in
  `application-results.schema.json#/$defs/message_entry`, so no response schema moves. `display_out_of_range` declares
  its `unit` param with this type, so the core catalogue's `sha256` moves, and the two `message_entry` round-trip
  fixtures carry the new value (that member only). The Consequences bullets "No stored datum, fixture or digest moves"
  and "The MSG slot is filled without changing MSG's interfaces" are read with this note. Nothing in a run, bundle,
  manifest or store moves (F0 unchanged).

**Does not amend:** ADR 0001 D1 (internal SI; D1.3's temperature/difference rule is applied, not changed); ADR 0016
D1–D9 (input conversion, its table, its arithmetic, its refusals); `schemas/units.json` (no kind is added); the
`Application` protocol; any run, bundle, manifest, certificate, replay, cache, store-row or audit schema or writer; the
closed 15-code `ApiError` enum and `API_EXIT_CODES`; ADR 0068's stream-table values and its `sha256` rule.
**Builds on:** ADR 0056 row 7; ADR 0057 rules C1, C3, C4, C5 and "X04 works at the boundary only"; ADR 0058 (the
catalogue, `RenderContext`, the `numbers` model); ADR 0068 (the stream table); R-077, R-924, R-925, R-927.
**Affected requirements:** D08 (the units contract), blueprint §4.2 ("SI internally … display units are conversion
metadata"), ADR 0057 C4.
**Affected packages:** X04 (new code: `units/display.py`; application, messages, CLI, web shell wiring), MSG (the slot),
ST (display members, CLI renderings), K06/T07 (`project-policy.json`, `get_project`).

## Context

- **Inputs already convert.** ADR 0016 converts a specification or instance-parameter value written in one of its 22
  rows (19 by scale or offset, 3 on the mass basis) to SI exactly at validation and binding: `SI = RN(a·D(v) + b)`.
  Gauge pressures (`barg`, `psig`) are refused there (ADR 0016 D8) because the revision carries no ambient pressure.
- **Outputs do not convert.** Nothing in `src/` converts an SI value for display. MSG left the slot
  `RenderContext.display_units` (always `None`) and planned `numbers[].display`. ST returns SI only (ADR 0068, ST C-4).
- **Measured for this ADR** (`x04_reference.py`): reading the SI double as its exact binary value turns 298.15 K into
  24.99999999999998 °C; reading it as its shortest decimal `D(X)` (ADR 0016's reading) and rounding once fixes the
  terminating rows but still shows a user's 25 °F as 24.99999999999998 °F, 25 kmol/h as 25.000000000000004 kmol/h
  and 12.34 psi as 12.339999999999998 psi: `RN(q)` alone misses 63 of the 400 registered round trips (degF, psi,
  psig, mol/h, kmol/h — the rows whose scale is not a terminating decimal). D3's preimage step closes all 400.

## Decisions

### D1. Scope: two boundaries, nothing stored

1. X04 converts in exactly two places (ADR 0057 C4). **Dispatch:** a request's `display_units` string is parsed into
   a resolved preference (D5); no input number is converted by X04 — input conversion stays ADR 0016's. **Projection:**
   when a response carrying SI numbers for a reader is produced — the stream table (`get_stream_table`) and run-failure
   explanations (`get_job_result`) — each number whose kind the preference names gains a display value beside it (D7).
2. **Always SI, never converted:** every stored or hashed document — revisions as written, bundles and every bundle
   member (solution state, certificate, run manifest, failure bundle, trace), artifacts served by `get_artifact` and
   `artifact_bytes`, validation reports (DIM-01's conversion records included), job documents, the audit log — and,
   inside converted responses, the SI members themselves, the stream table's check quotes (`checks[].value`,
   `tolerance`: verification evidence), `RunFailure.params`, and every number without a display kind (D4.3).
3. A display value is never an input to anything: no run, cache key, certificate, label, replay or comparison reads
   one. No request that starts or changes work admits `display_units` (their schemas are closed; A32).

### D2. Display kinds and the output table

1. **Display kinds** are the kinds of `schemas/units.json` and five kinds named by ADR 0062 D1 (Proposed) that the
   stream table already carries: `specific_enthalpy` (J/kg), `specific_entropy` (J/(kg K)), `molar_entropy`
   (J/(mol K)), `enthalpy_flow` (W), `mass_fraction` (1), with ADR 0062's SI units and dimensions. X04 does not
   register them as Quantity kinds (that is F2's); it uses their names so that F2 landing them changes nothing here
   (claim C10).
2. **The output table** (`display-conversion-v1`), `SI = a·u + b`, `a > 0` and `b` exact rationals; the SI unit of each
   kind is the identity and is not a row:

| Kind | Unit | `a` | `b` | Direction |
| --- | --- | --- | --- | --- |
| `temperature` | `degC`, `degF` | 1, 5/9 | 5463/20, 45967/180 | input and output |
| `temperature_difference` | `degC`, `degF` | 1, 5/9 | 0 | input and output |
| `pressure` | `kPa`, `MPa`, `bar`, `atm`, `psi` | 10³, 10⁶, 10⁵, 101325, 8896443230521/1290320000 | 0 | input and output |
| `pressure` | `barg`, `psig` | 10⁵, 8896443230521/1290320000 | `D(P_amb)`, the project's ambient (D6) | output only |
| `molar_flow` | `kmol/s`, `mmol/s`, `mol/h`, `kmol/h` | 10³, 1/10³, 1/3600, 5/18 | 0 | input and output |
| `mass_flow` | `g/s`, `kg/h` | 1/10³, 1/3600 | 0 | output (ADR 0016's mass-basis factors) |
| `heat_rate`, `power`, `enthalpy_flow` | `kW`, `MW` | 10³, 10⁶ | 0 | input and output (`enthalpy_flow`: output) |
| `molar_enthalpy` | `kJ/mol` | 10³ | 0 | output |
| `specific_enthalpy` | `kJ/kg` | 10³ | 0 | output |
| `molar_entropy` | `kJ/(mol K)` | 10³ | 0 | output |
| `specific_entropy` | `kJ/(kg K)` | 10³ | 0 | output |
| `dimensionless`, `mole_fraction`, `mass_fraction` | `%` | 1/100 | 0 | input and output (`mass_fraction`: output) |

3. **One registry, two directions.** On ADR 0016's kinds the output rows are exactly ADR 0016 D3's non-mass rows plus
   the two gauge rows, with equal `a` and `b`; the `mass_flow` rows have ADR 0016's mass-row factors. The generator
   reads ADR 0016's table from `benchmarks/t06/reference_values.yaml` and refuses to emit otherwise (claims C03, C04).
   A unit added later is added to both directions together, with a known answer, by register entry (FQ1).
4. Unit strings are matched exactly (case-sensitive ASCII, ADR 0016 D3); aliases (`°C`, `C`, `bara`, `psia`) are not
   rows (ADR 0016 Q14 stands). `molar_mass`, `molar_heat_capacity` and `molar_volume` have no rows in 0.4.

### D3. The arithmetic: `display-conversion-v1`

For an SI binary64 `X` of a display kind shown in unit `u` of D2 (`D(·)` the shortest decimal that rounds to its
argument — CPython's `repr` — read as an exact rational; `RN` one round-to-nearest-even to binary64):

1. `q = (D(X) − b)/a` exactly, and `v0 = RN(q)`. If `RN(q)` is not finite, the value has **no display value**: the
   item is `{value: null, unit: u, reason: {code: "display_out_of_range", params: {kind, unit}}}` (D7).
2. If `RN(b) = X`, the display value is `+0.0`. Otherwise, for `p = 1, 2, …, 17`, let `c_p` be `v0` rounded to `p`
   significant decimal digits (half-even, on `v0`'s exact binary value — `float(format(v0, f".{p}g"))`); the first
   `c_p` with `RN(a·D(c_p) + b) = X` is the display value.
3. If no `p` qualifies, the display value is `v0`.

A zero display value is `+0.0`. The computation is exact rational arithmetic and correctly rounded conversions, so it is
platform-independent and has no tolerance. An implementation may not substitute a binary64 chain (`x − 273.15`,
`x / 1e5`, `x * 3.6`); A3 and A4 refuse one row by row.

**What it guarantees** (each executable):
- G1. A step-2 value converts back: the row's own arithmetic `RN(a·D(c) + b)` — ADR 0016's, where the row is an input
  row — maps it to `X` bit for bit (C05, A3).
- G2. Values users type read back as typed: on the 400 registered round trips (input → SI by ADR 0016 → display) the
  display value is the input bit for bit (C07, A4); on the seeded sample of 50 350 inputs, every input of at most 10
  significant digits in `[1e-4, 1e6)` round-trips on every row (C08). Failures from 11 digits on are recorded per row
  and digit count in the reference (offset and gauge rows first, because `b` adds digits).
- G3. The display error is bounded by `X`'s own resolution: `|display − q| ≤ ulp(X)/a + ulp(display)/2`. *Proof:* the
  reals `u` with `RN(a·u + b) = X` form an interval `I` of width at most `ulp(X)/a` that contains `q` (because `D(X)`
  rounds to `X`); a step-2 value `c` has `D(c) ∈ I` and `|c − D(c)| ≤ ulp(c)/2`; the zero step has `0 ∈ I`; a fallback
  is within `ulp(v0)/2` of `q`. C09 checks it on every registered state and every sampled SI double.
- G4. On every registered state whose step-2 value has at most 15 digits (44 states), that value is the shortest
  displayable decimal of `I`, found independently by enumerating `I` (C06). This is checked, not claimed in general:
  step 2 tries one candidate per digit count.

**What it does not guarantee.** Step 2 is not exhaustive: for an arbitrary SI double (a solver's output) it falls back
to `v0` in 15.2 % of the sampled non-gauge cases (1706 of 11 200), and in 491 of those a longer displayable decimal that
converts back exists (recorded per row). A fallback value is `RN(q)`, within half an ulp of the exact conversion; it
does not convert back. Display values are for reading; an agent computes with the SI value beside them.

### D4. Kinds decide; temperature and differences; absolute and gauge

1. **A number converts only by its declared kind,** never by its SI unit symbol: `temperature` and
   `temperature_difference` share `K`; `heat_rate`, `power` and `enthalpy_flow` share `W`. A preference for
   `temperature=degC` never touches a `temperature_difference` (registered pairs DS01/DS02, DS07/DS08; C15).
2. **Every output number of kind `pressure` is an absolute pressure.** Gauge rows apply to kind `pressure` only. In 0.4
   the pressure sites are the stream table's stream `P` and six MSG catalogue params, all absolute
   (`phase_regime_mismatch.pressure`, `isentropic_state_two_phase.pressure`, `pressure_fall.p_spec`, `.p_inlet`,
   `pressure_rise.p_spec`, `.p_inlet`). A pressure difference is never emitted under kind `pressure`: A19 and A24 fail on
   an unclassified pressure site, so a future pressure-drop number cannot receive a gauge offset silently.
3. **No kind, no conversion.** A number whose kind is `null` or absent, or whose kind has no row for the preference, is
   shown in SI with its SI unit. In 0.4 this covers MSG `out_of_domain`'s `value`, `low`, `high` (kind `null`), and the
   stream table's `S_flow` (W/K), `V_flow` (m³/s), `rho` (kg/m³), `v` (m³/mol) and `components[].molar_mass` (L-X04-3).
4. **`%` on `dimensionless` reaches fractions only.** The 0.4 output sites of kind `dimensionless` are the stream
   table's four phase and vapour fractions (ADR 0016 D3 restricts the input row to fractions for the same reason); A24
   keeps any other `dimensionless` site from appearing unclassified.

### D5. Preferences: per request; the grammar; presets

1. **Where they live.** A preference is the request member `display_units` (a string, 1–1024 characters) of the
   operations that return converted numbers (D8). There is no session state and, in 0.4, no project default (FQ3). The
   web shell keeps the viewer's choice in browser storage and sends it with each request; the CLI takes
   `--display-units`. **Precedence:** the request's member, else SI.
2. **Grammar.** `display_units := item ("," item)*`; `item := preset | kind "=" unit`; presets `si` and `eng`. The text
   is split on `,`; each item, and each side of its first `=`, is stripped of leading and trailing U+0020; nothing else
   is normalized. Items are read left to right:
   - a preset is admitted only as the first item; it sets the map to its entries;
   - `kind` must be a display kind (D2.1), named at most once among the explicit items;
   - `unit` must be the kind's SI unit (the kind is then removed from the map) or a row of D2 for that kind;
   - after the last item, if the map holds a gauge unit, the project's ambient pressure must be declared (D6).
3. **Presets.** `si` = {}. `eng` = {temperature: degC, temperature_difference: degC, pressure: bar, molar_flow: kmol/h,
   mass_flow: kg/h, heat_rate: kW, power: kW, enthalpy_flow: kW, molar_enthalpy: kJ/mol, specific_enthalpy: kJ/kg,
   specific_entropy: kJ/(kg K)} (FQ2). No preset holds a gauge unit (C11), so `eng` works in every project.
4. **Resolution.** The resolved preference is the map (kind → non-SI unit) and the ambient pressure iff a gauge unit is
   in the map. Its canonical text is the map's `kind=unit` pairs sorted by kind and joined by `,`; `si` resolves to the
   empty map. The 24 registered cases PU01–PU24 fix every rule (C14).

### D6. The ambient pressure: declared per project

1. **Where.** `project-policy.json` gains the optional member `ambient_pressure`, a finite binary64 > 0, in Pa. It sits
   beside `executor`, the policy file's other non-authority setting, and changes the same way: through an audited
   operator command. It is absent until declared, and every existing policy file stays byte-identical, with an
   unchanged `policy_sha256` (A11).
2. **Declaring.** `openflowsheet project ambient --project DIR --pressure VALUE --unit UNIT` converts `VALUE UNIT` to Pa
   by ADR 0016's arithmetic on a `pressure` row (`Pa`, `kPa`, `MPa`, `bar`, `atm`, `psi`; a gauge unit is refused) and
   writes it; `--clear` removes it. Each change is audited as operation `project_ambient`. A nonfinite, non-positive or
   unconvertible value is refused, coded `ambient_pressure_invalid(<value|unit>)`, and the file is left unchanged.
   The library function is `application.authz.set_ambient_pressure(directory, pressure: float | None)`, as `grant`.
3. **Reading.** `get_project` returns `ambient_pressure: {value, unit: "Pa"} | null` on every transport.
4. **Use.** Only gauge display rows read it (`b = D(P_amb)`). It is never assumed: a preference with a gauge unit in a
   project without a declared ambient is refused, `invalid_request`, `ambient_pressure_undeclared(pressure):
   "<unit>"`. A response without a gauge unit does not depend on it (PU08, A14).
5. **Outside identity.** It is not in any revision, binding, run, bundle, certificate, cache key or replay. Two projects
   that differ only in their ambient produce byte-identical runs (A13). Declaring or clearing it changes
   `policy_sha256`, which revision, job and audit rows record as the policy in force, as an `executor` change does;
   that is provenance, not run identity.

### D7. The machine-readable form

1. **The display item** is `{value: number, unit: string}`, or `{value: null, unit, reason: {code:
   "display_out_of_range", params: {kind, unit}}}`. The unit string is the D2 spelling (`degC`, `kJ/(mol K)`), which is
   also the spelling ADR 0016 accepts as input. Agents read display values from these items, never from text.
2. **Messages** (MSG §4.5). Each explanation `numbers` item whose `kind` is in the resolved map gains `display`; its SI
   `value`, `unit` and `kind` are unchanged. Rendered text (summary, cause, where, why, action) shows a converted
   quantity as `format_number(display.value) + " " + text_unit(display.unit)` (MSG's normative format; D7.7,
   FQ4); an out-of-range display
   and the `!raw` conversion show the SI text. Explanations in a response are rendered with `RenderContext(display_units
   = <the resolved DisplayUnits>)`, which implements `Mapping[str, str]` (MSG's slot type) and carries the ambient.
3. **The stream table.** Each open object holding a converted number — stream (`T`, `P`), substream, phase, port, unit,
   overall — gains `display`, an object whose members mirror that object's converted members: a number member maps to a
   display item, an array member (`n`, `m`, `x`, `w`) to an array of the same length holding a display item or `null`
   where the SI element is `null`. A member is absent from `display` when its value is `null`, its kind is not in the
   map, or it has no display kind; an object with no converted member has no `display` member (never an empty object).
   The kinds of every stream-table member are fixed by the test specification's site
   table (§4). The root gains `display_units: {units: {kind: unit}, ambient_pressure: {value, unit: "Pa"} | null}`.
   Nothing else changes: the document with every `display` and the root `display_units` removed is byte-identical to the
   document returned without `display_units` (A22). The `Projection`'s `sha256` is the displayed document's own
   `document_sha256`, constant across its pages (ADR 0068's rule, unchanged).
4. **The job result.** `job_result` gains the root member `display_units` (as above) when the request had one; every
   explanation it holds (`run_result.failure.explanation`, the `error` documents') is rendered under the preference.
5. **Echo rule.** The `display_units` member is present iff the request carried `display_units` (`si` included), so a
   reader can see that its preference arrived and what it resolved to.
6. **CLI renderings** of the stream table (`openflowsheet streams --display-units TEXT`): `json` is the displayed
   document; `text` replaces the header line `SI units` by `display units:       <canonical text>` and, iff a gauge
   unit is used, `ambient pressure:    <{:.6g}> Pa`; every row label names its display unit in its text spelling
   (`T [°C]`, D7.7), energy-table headers carry `[unit]` (text spelling) when any energy kind is converted, values
   are `{:.6g}` of the display value; `csv` replaces a column's unit suffix by the display unit's suffix (rule: `/` →
   `_`; `(`, `)`, spaces dropped; `%` → `pct`; claim C12 shows the rule gives ST's 13 SI suffixes exactly) and
   appends `_pct` to a fraction column (`x_<c>_pct`), values `repr(display value)`. With `si`, or without the flag,
   `text` and `csv` are byte-identical to ST's; `json` with `si` adds only the root echo (D7.5).
7. **Text spelling (FQ4, Frank, 2026-11-09).** Machine members keep the D2 spelling (`degC`, `degF`): the display
   item's `unit` (D7.1), the `display_units` echo and its canonical text (the CLI `text` header's `display units:` line
   included), request parsing (ADR 0016's input spelling), schemas, catalogue `params` (a reason's `{kind, unit}`
   included), and CSV column suffixes (`T_degC`, D7.6). Human text shows `°C` and `°F`: message rendered text (D7.2),
   the CLI `text` rendering's row labels and energy headers (`T [°C]`), the web shell's labels (column headings,
   displayed values, the units control), and the guide's description of rendered output. One mapping,
   `units.display.text_unit` (`degC` → `°C`, `degF` → `°F`, every other unit unchanged), serves every human-text site;
   the web shell carries it as `textUnit` (`apps/web/js/units.js`), held equal to it by a test.
   `temperature_difference` maps the same way (its kind, not its spelling, distinguishes it). The mapping changes no
   number, identity or machine member.

### D8. Operations and transports (ADR 0019 Amendment 17)

`get_stream_table(job_id, *, pointer="", depth=12, cursor=None, limit=50, display_units=None)` and
`get_job_result(job_id, *, display_units=None)`; request schemas gain `display_units: {type: string, minLength: 1,
maxLength: 1024}`. HTTP: the query parameter `display_units` (percent-encoded); MCP: the tool argument of the same name
(the two tool descriptions gain one sentence each, through the descriptions' review procedure); CLI: `streams
--display-units`, and `api` with the member in the request. C1 holds: one row per capability, every transport. No other
operation changes: `validate`, `commit_change`, `solve`, `reproduce`, `submit_job` and every other request schema stays
closed against `display_units` (A32).

### D9. Codes and catalogue entries (MSG C3)

| Code | Raised as | Message head | Kind |
| --- | --- | --- | --- |
| `display_units_invalid` | `invalid_request`, pointer `/display_units` | `display_units_invalid(<0-based item index>): "<item>"` | input |
| `display_unit_unsupported` | `unsupported`, reason | `display_unit_unsupported(<kind>): "<unit>"` | not_supported |
| `ambient_pressure_undeclared` | `invalid_request`, pointer `/display_units` | `ambient_pressure_undeclared(pressure): "<unit>"` | input |
| `ambient_pressure_invalid` | coded `StoreError` (operator command, exit 2) | `ambient_pressure_invalid(<value\|unit>)` | input |
| `display_out_of_range` | a display item's `reason` | (structured `{code, params: {kind, unit}}`) | notice |

The user's text is JSON-quoted after `": "`, so MSG's legacy grammar reads exactly one code and never mistakes an item
for one (claim C13); args hold no parenthesis or comma. Every code gets a complete catalogue entry with what, where,
why, what to do and an example. Limitations (support envelope, synced into `limitations.yaml`): **L-X04-1** gauge
pressures are not accepted as inputs (D10); **L-X04-2** stored and hashed documents, raw artifacts, check quotes and
the web shell's as-solved state table stay SI (D1.2); **L-X04-3** numbers without a display kind or row stay SI (D4.3).

### D10. Inputs in 0.4: unchanged

ADR 0016 D3 and D8 stand: no input row is added, and gauge inputs stay refused with their existing codes (so T05's
re-pointed `barg-pin` mutation keeps `specification_unit_unsupported`). The contained form of a gauge input exists —
convert at commit (dispatch) against the project's declared ambient, store the absolute SI value, record the ambient
used in the change record — and is L-X04-1's planned remedy, not built in 0.4 (FQ1). R-077's lift is delivered for
outputs; its input half is FQ1.

### D11. Identity

A display preference never reaches a run (D1.3, D8). With `display_units` absent, every response is byte-identical to
today's. With it present, the SI content of every response is byte-identical to the response without it (A20, A22).
Reads write nothing but audit rows (A34). F0 (`scripts/corpus_identity.py --check`, M1–M9) stays PASS unchanged:
X04 edits no file F0 hashes (A35).

## Alternatives rejected

- **Converting the documents** (a stream table in °C, a converted `numbers.value`). Rejected: the machine form would
  depend on a preference; agents and tests would need to know which unit a number is in. SI stays; display sits beside.
- **Keying the preference by SI unit symbol** (`K → degC`). Rejected: it converts temperature differences with an offset
  and cannot tell `heat_rate` from `power` (ADR 0001 D1.3).
- **Reading `X` as its exact binary value.** Rejected: 298.15 K → 24.99999999999998 °C (DS01). `D(X)` is ADR 0016's
  reading, in the other direction.
- **`RN(q)` alone** (no step 2). Rejected: misses 63 of 400 registered round trips — 25 °F, 30 psig, 25 kmol/h read
  back with a tail (DS10, DS24, the round-trip table).
- **The exhaustive preimage** (enumerate the interval of reals converting to `X`, pick the shortest displayable
  decimal). Rejected for 0.4: about forty lines of interval arithmetic, binade edges and tie rules for every
  implementation, against a difference confined, on the sample, to display values of 15 or more digits and to
  fallbacks (491 of 11 200 sampled doubles fall back where it would not). It is kept as the generator's independent
  check (C06, C16).
- **Session preferences.** Rejected: no transport has sessions; it would add server state to a stateless contract.
- **A project default for display units** — deferred (FQ3): convenient, but it makes every reader's default output
  depend on project state; additive later as a fallback below the request member.
- **The ambient per request.** Rejected: ADR 0057 C4 places it per project, and two readers of one project would see
  different gauge values for one stream.
- **An assumed ambient (101325 Pa).** Rejected, as in ADR 0016: a fact about the site that nobody stated.
- **A new project file for the ambient.** Rejected: `project-policy.json` already holds non-authority settings
  (`executor`), with audit, validation and atomic writes; a second file would duplicate all three.
- **Client-side conversion in the web shell** (a JavaScript copy of the arithmetic). Rejected: two implementations of
  one exact rule, and C1 forbids a capability on one transport only.
- **A general `convert` operation.** Not needed in 0.4: the converted numbers come with the documents that hold them.
- **Registering the five ADR 0062 kinds in `schemas/units.json` now.** Rejected: the kind table is F2's core
  structure; 0.4 packages fix no core structure (ADR 0057).
- **Gauge display at every `pressure` number with a runtime site registry.** Rejected as unnecessary: no 0.4 output
  emits a pressure difference under kind `pressure`; a test keeps it so (D4.2).

## Consequences and migration impact

- No stored datum, fixture or digest moves. Existing request documents are valid; existing responses are unchanged when
  `display_units` is absent. Existing `project-policy.json` files are byte-identical. Schemas widen additively; their
  round-trip fixtures gain cases with display members (A11, A22, A33).
- The MSG slot is filled without changing MSG's interfaces: `RenderContext.display_units` keeps its type.
- Register on acceptance: D3 (rejected: binary reading, `RN(q)` alone, exhaustive preimage), D5 (per request; rejected:
  sessions, project default), D6 (ambient in the policy file; rejected: per request, assumed), D10 (inputs unchanged),
  and a note on R-077 that its output half is delivered.

## Acceptance evidence

`evidence/X04/<commit>/manifest.json` with status `tested`, recording A1–A40 of the test specification, each with its
test id and result; `python docs/derivations/scripts/x04_reference.py --check` (17 claims PASS, JSON byte-identical);
F0 PASS on the branch and on `main` after the merge; CI green on both architectures; the `reviewer` pass over WO-1–WO-4.

## Frank questions (value judgments; each has a default so work proceeds)

- **FQ1. Widen inputs in 0.4?** Gauge inputs by commit-time conversion against the project ambient (D10), and further
  rows in both directions (`t/h`, `lb/h`, `kJ/h`, `mbar`, aliases such as `°C`). *Default: no — 0.4 ships the output
  side; each widening is an additive, separately registered change.*
- **FQ2. The `eng` preset's contents and name.** *Default: as D5.3, named `eng`; molar entropy stays J/(mol K) (about
  10–300 in that unit), specific entropy becomes kJ/(kg K) (steam-table practice).*
- **FQ3. A project default for display units?** *Default: not in 0.4.*
- **FQ4. Text spelling.** Human text shows `degC` (the spelling a user types) rather than `°C`. *Default: `degC`
  everywhere, one spelling for input, machine output and text.*

**Answers — Frank, 2026-11-09 (decision board).** FQ1, FQ2, FQ3: the defaults. **FQ4: the alternative — `°C` in human
text.** Machine members keep the D2 spelling; human text shows `°C` and `°F`. The rule is D7.7; it amends D7.2 and D7.6
(the text spellings they name) and nothing else.

## Open questions that need a fact (with defaults)

- **OQ1.** Is ADR 0019 Amendment 17 still free when WO-3 lands? *Measure:* `grep -rn "Amendment 17" docs/adr`.
  *Default:* 17; if taken, the next free number, with no other change.
- **OQ2.** Is ST on `main` when WO-4 starts? *Settled during this pass:* `wp/ST` merged at `a053690d` (2026-11-09),
  with `stream_table.py`, `stream_table_format.py` and `stream-table.schema.json` identical to the versions this ADR
  cites. WO-4 need not wait.
- **OQ3.** Does a run-time failure deliver a pressure or entropy number to `get_job_result` (A20)? MSG WO-5a says P2's
  and P5's detail lines are delivered. *Measure:* A20's job. *Default:* a valve revision whose outlet pressure is above
  its inlet (`pressure_rise`); if no registered route delivers a number, A20 stays failing and the build lane escalates.

## Findings for other packages

- MSG's catalogue spells the molar-entropy SI unit `J/(mol*K)` (`refusals.yaml:72–73`); ADR 0062 D1 registers
  `J/(mol K)` as the only spelling. X04 is unaffected (it keys by kind and leaves SI strings as produced), but the two
  should agree when F2 lands. Not changed here.

## What this ADR does not establish

- Nothing about input conversion beyond restating that ADR 0016 is unchanged; no new input unit, no gauge input.
- No physical claim: display conversion is exact arithmetic on values that were verified (or not) in SI; a display
  value carries the verification status of its SI value and nothing more.
- No shortest-representation guarantee outside the registered states (G4), and no "converts back" guarantee for a
  fallback (D3).
- Nothing about units in the revision editor, in validation reports or in raw artifacts; nothing about kinds the
  0.4 outputs do not carry (volumetric flow, density, entropy flow have no kind).
- The sample measurements (G2, D3's fallback rates) describe the registered seeded sample and its stated domain only.
