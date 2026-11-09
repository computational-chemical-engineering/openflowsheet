# X04 test specification — units at the boundary

**Authority.** ADR 0075 (Proposed, 2026-11-09) is the decision; this document registers its states, assertions A1–A40
and work orders WO-1–WO-5. Design lane (`specifier`); brief `docs/briefs/X04-specifier.md`.
**Reference.** `docs/derivations/scripts/x04_reference.json` (`x04-reference-v1`), emitted by
`docs/derivations/scripts/x04_reference.py`. The generator imports nothing from `openflowsheet`; it reads
`schemas/units.json` and ADR 0016's table in `benchmarks/t06/reference_values.yaml` (`closed_form.unit_conversion_v2`)
only to check consistency. `--check` re-derives 17 claims (C01–C17) and confirms the committed JSON is byte-identical
to a fresh `--emit`; the script refuses to emit when a claim fails. Run time about 12 s.
**Scope.** Display conversion (`display-conversion-v1`), the preference grammar, the project ambient pressure, and
their wiring into `get_stream_table`, `get_job_result`, MSG explanations, the CLI and the web shell. Input conversion
(ADR 0016) is out of scope except where A2 and A4 use it as the other direction of a shared row.

## 1. What this establishes, and what it does not

**Establishes:** for every registered state, the exact display value an implementation must return; that the
registered round trips of user-typed values are exact; that display members never change the SI content, the identity
or the stored state of anything; that refusals are typed and catalogued; that every transport carries the preference
identically.

**Does not establish:** any physical or numerical property of the SI values themselves (they are verified, or not, by
the solve and the certificate, unchanged); shortest representation outside the registered states (ADR 0075 G4), or
"converts back" for a fallback (ADR 0075 D3 says what is and is not guaranteed); anything about inputs beyond ADR 0016;
anything outside the sampled domain of C08 (decimals of at most 10 significant digits, magnitude in `[1e-4, 1e6)`).
The sample counts are measurements on one seeded sample, not bounds.

## 2. Tolerances

Every assertion is exact: bit-for-bit for binary64 values (including the sign of zero), byte-for-byte for documents
and renderings. The display function is exact rational arithmetic followed by correctly rounded conversions (CPython's
`float(Fraction)` is correctly rounded integer division; `format(x, ".pg")` and `repr` are correctly rounded), so its
result is platform-independent and the roundoff floor of any comparison is zero. Measured: an independent
integer-arithmetic rounding (`rn`) equals `float(Fraction)` on all 869 101 roundings the generator performs (C02). A
binary64 chain (`x − 273.15`, `x / 1e5`) differs from the rule by at least one ulp on registered states (DS01: the
binary reading gives 24.99999999999998 °C), so a zero tolerance is above the floor and below the smallest error worth
catching. No finite difference is involved anywhere in X04.

## 3. Registered states (all in the reference JSON)

- **Rows** (30) and **display kinds** (18): ADR 0075 D2. Each row carries `a`, `b` (rationals as `p/q`; gauge `b` is
  `"ambient"`), its direction and its CSV suffix.
- **Display states DS01–DS51.** Each has `si_value`, kind, unit, ambient, the exact `q = (D(X) − b)/a`, the expected
  `display_value` (repr, or `null`), the method (`preimage` with its digit count, `fallback`, `out_of_range`) and
  `converts_back_to_si`. Why each is there:

| States | Why registered |
| --- | --- |
| DS01, DS02 | one X (298.15 K) under `temperature` → 25.0 degC and `temperature_difference` → 298.15 degC: a dropped kind or offset changes one |
| DS03 | 273.15 K → 0.0 degC: registered because it vanishes (+0.0) |
| DS04–DS06 | −40 °C = −40 °F crossing; 300 K → 80.33 degF |
| DS07, DS08 | 310 K → 558.0 (difference, degF) and 98.33 (temperature, degF) |
| DS09 | 10 K difference → 10.0 degC |
| DS10, DS24, DS25 | a user's 25 degF, 30 psig, 1 kmol/h read back as typed (for DS10 and DS24, `RN(q)` alone gives 24.99999999999998 and 30.000000000000004) |
| DS11–DS14 | 101325 Pa in bar 1.01325, atm 1.0, kPa 101.325, psi 14.695948775513449 (a 17-digit result) |
| DS15–DS19, DS21 | gauge: 0.0 barg and 0.0 psig at the ambient (vanish); 0.06325 barg at a 95000 Pa ambient (the ambient is read); 2.0; −0.51325 and −0.91325 (below ambient) |
| DS20, DS22, DS23, DS48–DS50 | the MSG numbers of A16–A17: 0.1 bar, 5.0 MPa, 30.0 bar, 48.98675 barg, 28.98675 barg, 0.14680317968321518 kJ/(mol K) |
| DS26–DS31 | flows: 1 mol/s → 3.6 kmol/h, 3600.0 mol/h, 0.001 kmol/s, 1000.0 mmol/s; 1 kg/s → 3600.0 kg/h, 1000.0 g/s |
| DS32–DS38 | a negative duty −16.1446 kW (sign), −0.0161446 MW, 2627.3451 kW, 47.33 kJ/mol, 749.161585 kJ/kg, 0.1397797844964916 kJ/(mol K), 2.10865845 kJ/(kg K) |
| DS39–DS41 | 25.0 % (mole and mass fraction), 91.2345 % (dimensionless) |
| DS42, DS43 | zero flow and zero duty → +0.0: registered because they vanish |
| DS44 | 5e-324 Pa → 0.0 MPa: a nonzero SI value whose display underflows (fallback), registered because it vanishes |
| DS45–DS47 | 1e305 mol/s → `null` in mol/h (out of range) but 3.6e+305 in kmol/h; the largest double → `null` in kg/h |
| DS51 | a seeded molar flow, 87.03649384684813 mol/s, whose display falls back to `v0` = 313.3313778486533 kmol/h; no binary64 converts back (C16) |

- **Round trips** (400): ADR 0016's 19 non-mass rows and the two gauge rows (at ambients 101325 and 95000 Pa), each
  with the inputs 25, −40, 0.01, 12.34, 1.5, 100, 0.001, 0.1, 75.1, 26.85, 1.01325, 14.6959, 3600, 0.5, 1, 2, 30, 0
  whose SI value is admissible (temperature and pressure > 0). Each records `si_value`, `display_value` and
  `plain_rounding` (`RN(q)`); 63 of them have `plain_rounding ≠ input`.
- **Preferences PU01–PU24** (ADR 0075 D5): text, ambient, the expected resolution `{units, ambient_pressure}` or the
  refusal `{api_error, reason, message}` (schema refusals: `{api_error, reason: "schema", pointer}`).
- **Ambient declarations AD01–AD13** (D6.2): value, unit, the expected Pa (repr) or `refused:value` /
  `refused:unit`. AD03: 14.6959 psi → 101324.66370467292 Pa; AD10: 1e304 MPa overflows → `refused:value`.
- **Sample** (seed 20261109): per row, 1–17 significant digits × 100 inputs in `[1e-4, 1e6)` (50 350 drawn in all) and
  400 SI doubles; records round-trip failures by digit count for the rule and for `RN(q)`, fallbacks, fallbacks for
  which a longer displayable preimage exists, and bound violations (zero).

## 4. The stream-table site table (ADR 0075 D7.3)

| Object | Member | Kind | Note |
| --- | --- | --- | --- |
| stream | `T` | `temperature` | `null` when dormant: no display |
| stream | `P` | `pressure` | absolute; gauge rows apply |
| substream, phase | `n[]`, `n_total` | `molar_flow` | |
| substream, phase | `m[]`, `m_total` | `mass_flow` | |
| substream, phase | `x[]` | `mole_fraction` | substream `x` may be `null` as a whole (R0) |
| substream, phase | `w[]` | `mass_fraction` | as `x` |
| substream, phase | `H_flow` | `enthalpy_flow` | |
| substream, phase | `h` / `h_mass` | `molar_enthalpy` / `specific_enthalpy` | |
| substream, phase | `s` / `s_mass` | `molar_entropy` / `specific_entropy` | |
| substream | `vapor_fraction_molar`, `vapor_fraction_mass` | `dimensionless` | |
| phase | `phase_fraction_molar`, `phase_fraction_mass` | `dimensionless` | |
| phase | `v` | `molar_volume` | no rows in 0.4: never displayed |
| substream, phase | `S_flow`, `V_flow`, `rho` | none | L-X04-3 |
| port | `H_flow` | `enthalpy_flow` | |
| unit | `H_in`, `H_out` | `enthalpy_flow` | |
| unit, overall | `Q`, `closure` | `heat_rate` | `closure` is the duty that would close the balance |
| unit, overall | `W` | `power` | |
| overall | `H_feeds`, `H_products` | `enthalpy_flow` | |
| root `components[]` | `molar_mass` | `molar_mass` | closed object; never displayed |
| quote (closed) | `index`, `value`, `tolerance` | none | verification evidence stays SI |
| phase_id (closed) | `ordinal` | none | identity integer, as a quote's index |
| entry (closed) | numbers in `params` | none | |

## 5. Assertions

Each assertion names its work order, its expected value or pattern, and why it catches what it is there to catch. The
tolerance of every one is exact (§2).

### U — display core (WO-1, `tests/test_x04_display_core.py`)

- **A1. Table.** `units.display.DISPLAY_ROWS`, in order, equals the reference `rows` in `(kind, unit, a, b,
  csv_suffix)`; `DISPLAY_KINDS` equals `display_kinds` in `(si_unit, dimension)`; `DISPLAY_CONVERSION_ID ==
  "display-conversion-v1"`. *Catches* a mistyped constant, a dropped or added row, a gauge row without its marker.
- **A2. One registry.** For each `(kind, unit)` in both `units.CONVERSION_ROWS` (rule ≠ `mass_to_molar`) and
  `DISPLAY_ROWS`, `a` and `b` are equal; on ADR 0016's kinds the display rows absent from `CONVERSION_ROWS` are exactly
  `(pressure, barg)` and `(pressure, psig)`; `DISPLAY_ROWS[(mass_flow, g/s)].a` and `[(mass_flow, kg/h)].a` equal the
  `a` of `CONVERSION_ROWS[(molar_flow, g/s)]` and `[(molar_flow, kg/h)]`. *Catches* the two directions drifting
  apart, the failure mode a second table invites.
- **A3. Display states.** For DS01–DS51, `display_item(X, kind, DisplayUnits)` with the state's unit and ambient
  returns `{value: v, unit}` with `repr(v) ==` the reference `display_value` and `math.copysign(1, v) == 1` when
  `v == 0`, or, for DS45 and DS47, `{value: None, unit, reason: {code: "display_out_of_range", params: {kind,
  unit}}}`. Where `converts_back_to_si` is true, `row_to_si(v, kind, unit, ambient)` returns X bit for bit. Spot
  values: DS01 25.0, DS02 298.15, DS03 0.0, DS05 −40.0, DS08 98.33, DS10 25.0, DS14 14.695948775513449, DS17 0.06325,
  DS19 −0.51325, DS25 1.0, DS44 0.0, DS46 3.6e+305, DS51 313.3313778486533. *Catches* a binary reading (DS01), a
  missing step 2 (DS10, DS25), a missing zero step or −0.0 (DS03, DS15), an assumed ambient (DS17), a swapped kind
  (DS02, DS07/DS08), an overflow that raises or returns `inf` (DS45).
- **A4. Round trips.** For each of the 400 registered round trips: the input direction — `units.convert_input_value`
  for ADR 0016 rows (targets: `state.T` for `temperature`; `parameters.split_fraction` for `dimensionless %`;
  component `"A"` for `molar_flow` rows; `required_kind` passed directly otherwise), and `row_to_si` for the gauge
  rows — returns the reference `si_value`; `display_item` of that SI value returns the input, bit for bit. This
  includes the 63 trips whose `plain_rounding` differs. *Catches* `RN(q)` alone, a step 2 that tries the wrong
  candidate, and a disagreement between ADR 0016's implementation and X04's reference.
- **A5. Sample reproduction.** The test loads `docs/derivations/scripts/x04_reference.py` by path, wraps its
  `display` function to record every call and result, and runs its `sampled()` (the seeded draws, about 62 000
  displays). On every recorded call, `display_item` returns the recorded value bit for bit (`None` for
  `out_of_range`), and the `sample` section that run produces equals the committed reference's. *Catches* any other
  algorithm — an exhaustive preimage search would change `fallbacks` — that registered states alone might not
  separate.
- **A6. Grammar.** For PU01–PU24, `parse_display_units(text, ambient_pressure)` returns a `DisplayUnits` whose
  `as_document()` is `{units, ambient_pressure: {value, unit: "Pa"} | null}` matching the reference (the reference
  writes the ambient as a repr string), or raises `DisplayUnitsError` with `api_error`, `reason` and `message` equal
  to the reference; PU16 is refused by the request schema through `dispatch` (`invalid_request`, pointer
  `/display_units`). `DisplayUnits.canonical()` of PU01 is `enthalpy_flow=kW,heat_rate=kW,mass_flow=kg/h,
  molar_enthalpy=kJ/mol,molar_flow=kmol/h,power=kW,pressure=bar,specific_enthalpy=kJ/kg,
  specific_entropy=kJ/(kg K),temperature=degC,temperature_difference=degC`, and of PU02 the empty string.
  *Catches* every grammar rule separately (one PU case per rule) and a message an MSG parser would misread (C13).
- **A7. Kinds decide.** With `parse_display_units("temperature=degC")`, `display_item(298.15,
  "temperature_difference", …)` and `display_item(298.15, None, …)` return `None`; with `"heat_rate=kW"`,
  `display_item(1000.0, "power", …)` returns `None`. *Catches* conversion keyed by SI unit symbol (ADR 0075 D4.1).
- **A8. Generator.** `python docs/derivations/scripts/x04_reference.py --check` exits 0 with 17 `PASS` lines and
  `x04_reference.json is byte-identical to --emit`; `ruff check` and `ruff format --check` pass on the script.

### P — project ambient (WO-2, `tests/test_x04_ambient.py`)

- **A9. Declare, read, clear.** For AD01–AD05, `openflowsheet project ambient --project D --pressure V --unit U` exits
  0, `project-policy.json` holds `ambient_pressure` equal to the reference Pa (AD03: 101324.66370467292), an audit row
  `project_ambient` with outcome `allowed` is added, and `get_project().ambient_pressure == {"value": <Pa>, "unit":
  "Pa"}`; `--clear` removes the member and `get_project` returns `null`. The library call
  `authz.set_ambient_pressure` gives the same file bytes.
- **A10. Declaration refusals.** For AD06–AD13 the command exits 2; the coded error's machine text (`args[0]`, shown
  on stderr's `Details:` line by MSG's CLI rendering) is `ambient_pressure_invalid(value)` or
  `ambient_pressure_invalid(unit)` as the reference says; `project-policy.json` is byte-identical to before and no
  `project_ambient` row with outcome `allowed` is added. The library call raises the same coded error. *Catches* a
  defaulted, clipped or gauge-interpreted ambient.
- **A11. Policy bytes.** A project initialised by the X04 code, never declaring, has a `project-policy.json`
  byte-identical to one initialised by the pre-X04 code with the same project id and the same `policy_sha256`; every
  existing policy fixture loads and re-serializes byte-identically. *Catches* a `null` member written by default.
- **A12. `get_project` on every transport.** `ambient_pressure` is present (null or the object) through Python
  `dispatch`, CLI `api get_project`, HTTP `GET /v1/project` and MCP `get_project`, identical; the response validates
  against `project_summary`.
- **A13. Not in run identity.** One revision solved by `submit_job` in three projects — ambient undeclared, 101325 Pa,
  95000 Pa — gives byte-identical bundle members, the same `certificate_id`, `state_sha256` and run cache keys.
- **A14. Not in non-gauge displays.** In the projects of A13, `get_stream_table(job, display_units="eng")` documents are
  byte-identical (PU08: no ambient echo); with `"eng,pressure=barg"` (101325 vs 95000 Pa) the two documents differ
  only in the stream `display.P` items and the root `display_units.ambient_pressure`.

### M — messages and `get_job_result` (WO-3, `tests/test_x04_messages.py`)

- **A15. No preference, no change.** With `RenderContext(display_units=None)` every catalogue example and every MSG
  corpus explanation is byte-identical to MSG's (its existing tests pass unchanged); no `numbers` item has `display`.
- **A16. Entropy and pressure.** The MSG detail `s* = 139.7797844964916 lies past the saturated VAPOR entropy
  146.80317968321518 at 10000.0 Pa` (code `isentropic_state_two_phase`, as in `tests/test_msg_engine.py`), rendered
  with `display_units="molar_entropy=kJ/(mol K),pressure=bar"`: `numbers` `s_star`, `s_saturated`, `pressure` carry
  `display` `{0.1397797844964916, "kJ/(mol K)"}` (DS37), `{0.14680317968321518, "kJ/(mol K)"}` (DS50), `{0.1, "bar"}`
  (DS20), and keep `value`, `unit`, `kind` (139.7797844964916, `J/(mol*K)`, `molar_entropy`; …; 10000.0, `Pa`,
  `pressure`); `why` contains `0.1398 kJ/(mol K)`, `0.1468 kJ/(mol K)` and `0.1000 bar` (MSG's `format_number`) and
  does not contain `139.8` or `10000 Pa`.
- **A17. Gauge in a message.** The detail `P_spec = 5000000.0 Pa is above the inlet's 3000000.0 Pa` (`pressure_rise`,
  turbine) with `display_units="pressure=barg"` and ambient 101325 Pa: `p_spec.display = {48.98675, "barg"}` (DS48),
  `p_inlet.display = {28.98675, "barg"}` (DS49); `summary` contains `(48.99 barg against 28.99 barg)`; `action`
  contains `of 28.99 barg`; the same render without an ambient is impossible (the preference is refused first, A6
  PU07).
- **A18. No kind, no conversion.** The detail `out_of_domain: temperature 200.0 K outside [273.16, 1273.15] K` with
  `display_units="eng"`: no `numbers` item has `display`; `why` contains `200.0 K`. *Catches* conversion by unit
  symbol on a kind-less number.
- **A19. Pressure sites in the catalogue are absolute.** The set of `(code, param)` whose declaration has
  `quantity_kind: pressure`, or whose example params give it a quantity of kind `pressure`, is exactly
  {`phase_regime_mismatch.pressure`, `isentropic_state_two_phase.pressure`, `pressure_fall.p_spec`,
  `pressure_fall.p_inlet`, `pressure_rise.p_spec`, `pressure_rise.p_inlet`}. A new pressure param fails this test until
  it is classified absolute (ADR 0075 D4.2) or given another kind.
- **A20. `get_job_result` end to end.** A project job whose run fails with a pressure or entropy number delivered by the
  sidecar (OQ3's default: a valve revision with its outlet pressure above its inlet, `pressure_rise`): with
  `display_units="pressure=bar"` the result has root `display_units = {units: {pressure: "bar"}, ambient_pressure:
  null}`, every pressure item of `run_result.failure.explanation.numbers` has the display item `display_item` gives,
  and the text fields show it; removing `display` members and the root echo gives a document equal to the
  no-preference result except in the explanation text fields (`summary`, `cause`, `where`, `why`, `action`). If no
  registered route delivers such a number, this assertion fails and is escalated, never skipped.

### S — stream table (WO-4, `tests/test_x04_stream_table.py`)

The jobs are those ST's tests already solve: the SYN-001 nominal job and the water job of ST design note O7, at least.

- **A21. No preference, no change.** Without `display_units`, `get_stream_table` returns ST's document byte for byte
  (canonical JSON and `sha256`); no `display` or `display_units` member exists. ST's own tests pass unchanged.
- **A22. Strip invariance.** For each `D` in {`eng`; `eng,pressure=barg` with ambient 101325; `si`;
  `mole_fraction=%,mass_fraction=%,dimensionless=%`; `molar_entropy=kJ/(mol K),specific_entropy=kJ/(kg K)`}, the
  displayed document with every `display` member and the root `display_units` removed is byte-identical (canonical
  JSON) to the document without `display_units`. *Catches* any change to an SI member.
- **A23. Coverage and values.** For each `D` of A22, walking the document with §4's site table: every number at a site
  whose kind is in the resolved map has a `display` entry equal to `display_item(X, kind, units)`; array displays have
  the SI array's length with `null` exactly where the SI element is `null`; no other member has a display entry (none
  for `S_flow`, `V_flow`, `rho`, `v`, quotes, entries, `components[].molar_mass`, or any `null` SI value).
- **A24. Site table complete.** Every number-typed property (or array of numbers) of every object in
  `stream-table.schema.json` is a key of the implementation's site table, and the table equals §4. *Catches* a new ST
  member that would otherwise escape classification (and a pressure difference under kind `pressure`).
- **A25. Echo.** The root `display_units` is `{units: <resolved map>, ambient_pressure: {value: 101325.0, unit: "Pa"}
  | null}` (null unless a gauge unit is used), present iff the request had `display_units`; with `si` it is
  `{units: {}, ambient_pressure: null}` and A22 still holds.
- **A26. Gauge through the operation.** With ambients 101325 and 95000 Pa and `display_units="pressure=barg"`, every
  stream's `display.P` equals the generator's `display(P, "pressure", "barg", ambient)` (the test loads the
  generator by path), and the two documents' `P` displays differ for every stream with a non-null `P`; with no ambient
  the call is refused `invalid_request`, message `ambient_pressure_undeclared(pressure): "barg"`, pointer
  `/display_units`.
- **A27. Paging.** With `display_units="eng"`, paging `/streams` with `cursor` and `limit=1` gives the same `sha256` on
  every page, equal to `document_sha256` of the full displayed document; the CLI's assembled document equals the
  unpaged one.
- **A28. CLI text.** `openflowsheet streams --project D --job J --display-units eng`: the header line `SI units` is
  replaced by `display units:       ` followed by PU01's canonical text; the rows are labelled `T [degC]`, `P [bar]`,
  `n [kmol/h]`, `m [kg/h]`, `h [kJ/mol]`, `h [kJ/kg]`, `s [J/(mol K)]`, `s [kJ/(kg K)]`, `rho [kg/m3]`, `H [kW]`; the
  energy headers are `H_in [kW]`, `H_out [kW]`, `Q [kW]`, `W [kW]`, `closure [kW]`; each value is `{:.6g}` of its
  display value (of the SI value where there is none). With `--display-units eng,pressure=barg` and ambient 101325 the
  next header line is `ambient pressure:    101325 Pa` and `P [barg]`. Without the flag, and with `si`, the output is
  byte-identical to ST's.
- **A29. CLI csv.** With `--display-units eng`: the columns `T_degC`, `P_bar`, `n_total_kmol_h`, `m_total_kg_h`,
  `h_kJ_mol`, `h_kJ_kg`, `s_J_molK`, `s_kJ_kgK`, `H_flow_kW` and `n_<c>_kmol_h` replace their SI names; the others are
  unchanged; with `mole_fraction=%,dimensionless=%` the columns `x_<c>_pct`, `phase_fraction_molar_pct`,
  `vapor_fraction_molar_pct`, `vapor_fraction_mass_pct`; cells are `repr` of the display value. Without the flag, and
  with `si`, byte-identical to ST's.
- **A30. CLI json.** `--format json --display-units eng` prints `canonical_json` of the displayed document and a
  newline, byte-identical to the Python result's canonical JSON.

### T — transports and schemas (WO-3 for `get_job_result`, WO-4 for `get_stream_table`)

- **A31. Parity.** For both operations and `display_units` ∈ {`eng`; `eng,pressure=barg` with ambient; `temp=degC`;
  `temperature=celsius`; `eng,pressure=barg` without ambient}: Python `dispatch`, CLI (`api`, and `streams` for the
  stream table), HTTP (the query parameter, percent-encoded) and MCP give identical canonical response documents, or
  identical `ApiError` (code, message, pointer) with the HTTP status of `API_ERROR_HTTP_STATUS`.
- **A32. Closed elsewhere.** A request to any other operation (`validate`, `commit_change`, `solve`, `reproduce`,
  `submit_job`, `get_job`, `list_jobs`, `wait_job`, `cancel_job`, `get_project`, `get_revision`, `get_artifact`,
  `explain`, …) with an added `display_units` member is refused `invalid_request` by its schema on Python `dispatch`
  and HTTP; among MCP tool input schemas only `get_stream_table` and `get_job_result` name `display_units`.
- **A33. Schemas and fixtures.** Both request schemas declare `display_units: {type: string, minLength: 1, maxLength:
  1024}`; every response produced in A14–A30 validates against its operation's response schema; round-trip fixtures
  are added for `job_result` with `display_units`, `project_summary` with `ambient_pressure`, an `explanation` with a
  `display` item, a `stream-table-v1` document with display members, and a `project-policy` with `ambient_pressure`.

### I — identity

- **A34. Reads write nothing.** Around a sequence of `get_stream_table` and `get_job_result` calls with each `D` of
  A22, every file under the project directory other than `project.sqlite3*` is byte-identical, and the database's rows
  other than the audit log are identical.
- **A35. F0.** `scripts/corpus_identity.py --check` passes on the X04 branch with no change to its expectations, and on
  `main` after the merge.

### C — catalogue and limitations

- **A36. Codes.** `display_units_invalid`, `display_unit_unsupported`, `ambient_pressure_undeclared`,
  `ambient_pressure_invalid` and `display_out_of_range` have complete entries (MSG lint clean); every refusal raised in
  A6, A10, A26 and A31 renders strictly with its entry, and `explain <code>` returns it on every transport.
- **A37. Limitations.** L-X04-1, L-X04-2 and L-X04-3 are rows of `benchmarks/t08/support_envelope.yaml` whose
  evidence names existing tests (A6 PU20 and ADR 0016's `barg-pin` for L-X04-1; A21, A23 for L-X04-2; A18, A23 for
  L-X04-3), and are synced into `limitations.yaml`; `explain L-X04-1` works.

### W — web shell and documentation (WO-5)

- **A38. Web shell.** A units control (SI, `eng`, and a gauge option enabled only when `get_project.ambient_pressure`
  is not null) is stored per viewer in browser storage, every access wrapped in `try/catch`, and is sent as
  `display_units` by the streams screen's stream-table section and the failure screen. A converted value is shown with
  the display unit in its column heading or text and the SI value and unit in its `title`; the as-solved state table
  stays SI and is labelled so. The browser smoke test, with `eng`, finds one known stream's `T` cell showing the
  display value of the stream-table document (`fmt` of `display.T.value`) and `degC` in the heading.
- **A39. The web shell never converts.** A static scan of `apps/web/js` finds none of the conversion constants
  `273.15`, `459.67`, `5463`, `45967`, `3600`, `101325`, `0.45359237`, `9.80665` (outside comments); every displayed
  converted number comes from a `display` item.
- **A40. Documentation.** `docs-site/guide/units.md` exists, states the input table (ADR 0016), the output table (every
  unit of ADR 0075 D2 appears), the presets, the ambient command and what stays SI; a test checks that every row of the
  reference `rows` is named on the page.

## 6. Work orders

Branch `wp/X04` from `main` (ST is on `main` since `a053690d`). Two engineers of about 150k context each, in parallel
worktrees: engineer A takes WO-1–WO-3, engineer B WO-4 and WO-5; B consumes WO-1's module, so A lands WO-1 first. Each WO is one or more commits naming X04; the `reviewer`
pass covers WO-1–WO-4. The build lane decides nothing scientific: a question about values, kinds, rounding, sites or
refusals stops the work order and goes to the design lane.

- **WO-1 Display core (A, ~35k).** New `src/openflowsheet/units/display.py`: `DISPLAY_CONVERSION_ID`, `DISPLAY_KINDS`
  (units.json kinds plus the five of ADR 0075 D2.1), `DISPLAY_ROWS`, `PRESETS`, `GAUGE_ROWS`; `row_to_si(value, kind,
  unit, ambient_pressure=None)` (`RN(a·D(v) + b)`); `display_item(x, kind, units) -> dict | None` (D3 exactly: zero
  step, `p = 1…17`, fallback, out of range); `DisplayUnits` (frozen, `Mapping[str, str]`, `ambient_pressure`,
  `as_document()`, `canonical()`); `DisplayUnitsError(api_error, reason, message)`; `parse_display_units(text,
  ambient_pressure)`. Re-export from `openflowsheet.units`. Tests A1–A8. No other module changes.
- **WO-2 Ambient (A, ~30k).** `ProjectPolicy.ambient_pressure: float | None = None` (omitted from the document when
  `None`), `schemas/project-policy.schema.json` (optional number, `exclusiveMinimum: 0`), `authz.set_ambient_pressure`,
  CLI `project ambient` (`--pressure --unit | --clear`), audit `project_ambient`, coded `ambient_pressure_invalid`;
  `ProjectSummary.ambient_pressure` and `project_summary` schema member (required, nullable). Tests A9–A14 (A14 after
  WO-4).
- **WO-3 Messages and `get_job_result` (A, ~55k).** `RenderContext.display_units` set from the request;
  `messages/render.py`: `_numbers` adds `display`, `_format` renders quantities from it (not under `!raw`);
  `application-results` `explanation.numbers` item gains `display`; `JobControl.get_job_result(job_id, *,
  display_units=None)`, its OPERATIONS row and decode, the `job_result` root echo; `bindings/descriptions/
  get_job_result.md`; catalogue entries for the five codes (D9); ADR 0019 Amendment 17's pointer paragraph and the
  `interfaces-frozen.md` paragraph. Tests A15–A20, A31–A33 (job result), A36.
- **WO-4 Stream table and CLI (B, ~50k; after WO-1).** `application/stream_table.py`: the §4 site table and the
  display members (D7.3), the root echo; `Inspection.get_stream_table(…, display_units=None)`, row, decode,
  `bindings/descriptions/get_stream_table.md`; `stream-table.schema.json` states `display` and `display_units`;
  `stream_table_format.py`: header lines, labels, CSV suffix rule (`csv_suffix` from WO-1's module), values; CLI
  `streams --display-units`. Tests A21–A30, A31–A34 (stream table), A35.
- **WO-5 Web shell, limitations, docs, evidence (B, ~45k).** Web-shell units control and the two screens (A38, A39);
  L-X04-1–3 in `benchmarks/t08/support_envelope.yaml` and `scripts/msg_catalogue.py sync-limitations` (A37);
  `docs-site/guide/units.md` (A40); `evidence/X04/<commit>/manifest.json` recording A1–A40 with test ids, the
  generator `--check`, F0 and CI.

## 7. Open questions

Carried from ADR 0075, each with its default: **FQ1** input widening (default: none in 0.4), **FQ2** the `eng` preset
(default: D5.3), **FQ3** a project default (default: none), **FQ4** text spelling (default: `degC`) — *need Frank's
preference*. **OQ1** the amendment number (default 17), **OQ2** ST on `main` (settled: merged at `a053690d`), **OQ3** a run-time
route delivering a quantity number to A20 (default: `pressure_rise` on a valve revision) — *need a fact*, measured as
stated in the ADR.
