# Display units

Every number OpenFlowsheet stores, hashes or computes with is in SI. A reader may ask for some
numbers in other units — degrees Celsius, bar, kW, kmol/h — and gets them **beside** the SI
values, never instead of them. The SI value stays in the document and is the one to compute with;
the display value is for reading (ADR 0075).

## Asking for display units

Two operations take the optional request member `display_units`: `get_stream_table` (the stream
table and energy summary) and `get_job_result` (the explanation of a failed run). The value is a
comma-separated list: a preset first, then `kind=unit` items, each overriding the preset for its
kind.

| Transport | Example |
| --- | --- |
| Python | `app.get_stream_table(job_id, display_units="eng")` |
| CLI | `openflowsheet streams --project DIR --job JOB --display-units "eng,pressure=barg"` |
| HTTP | `GET /v1/jobs/{job_id}/stream-table?display_units=eng` (percent-encoded) |
| MCP | the tool argument `display_units` of `get_stream_table` and `get_job_result` |
| Web shell | the **units** control in the header (SI, eng, eng with gauge pressure) |

A converted number gains a `display` item, `{"value": 25.0, "unit": "degC"}`; the response's root
echoes the preference as `display_units: {units, ambient_pressure}`. A display value that is not a
finite number is `null` with the reason `display_out_of_range`. A malformed preference is refused
`invalid_request` (`display_units_invalid`); a unit the table does not have is refused
`unsupported` (`display_unit_unsupported`). Without `display_units` every response is exactly
what it was before display units existed.

## Presets

| Preset | Units |
| --- | --- |
| `si` | none: SI throughout (the response still echoes the preference) |
| `eng` | `temperature=degC`, `temperature_difference=degC`, `pressure=bar`, `molar_flow=kmol/h`, `mass_flow=kg/h`, `heat_rate=kW`, `power=kW`, `enthalpy_flow=kW`, `molar_enthalpy=kJ/mol`, `specific_enthalpy=kJ/kg`, `specific_entropy=kJ/(kg K)` |

## Output units

`SI = a·u + b`, with `a` and `b` exact. A number converts by its declared kind, never by its unit
symbol: `temperature=degC` never touches a temperature difference, and `heat_rate`, `power` and
`enthalpy_flow` are three kinds although all are watts. The SI unit of each kind is the identity
and is not listed.

| Kind | Unit | `a` | `b` | Direction |
| --- | --- | --- | --- | --- |
| `temperature` | `degC` | 1 | 5463/20 | input and output |
| `temperature` | `degF` | 5/9 | 45967/180 | input and output |
| `temperature_difference` | `degC` | 1 | 0 | input and output |
| `temperature_difference` | `degF` | 5/9 | 0 | input and output |
| `pressure` | `kPa` | 1000 | 0 | input and output |
| `pressure` | `MPa` | 1000000 | 0 | input and output |
| `pressure` | `bar` | 100000 | 0 | input and output |
| `pressure` | `atm` | 101325 | 0 | input and output |
| `pressure` | `psi` | 8896443230521/1290320000 | 0 | input and output |
| `pressure` | `barg` | 100000 | ambient (declared) | output |
| `pressure` | `psig` | 8896443230521/1290320000 | ambient (declared) | output |
| `molar_flow` | `kmol/s` | 1000 | 0 | input and output |
| `molar_flow` | `mmol/s` | 1/1000 | 0 | input and output |
| `molar_flow` | `mol/h` | 1/3600 | 0 | input and output |
| `molar_flow` | `kmol/h` | 5/18 | 0 | input and output |
| `mass_flow` | `g/s` | 1/1000 | 0 | output |
| `mass_flow` | `kg/h` | 1/3600 | 0 | output |
| `heat_rate` | `kW` | 1000 | 0 | input and output |
| `heat_rate` | `MW` | 1000000 | 0 | input and output |
| `power` | `kW` | 1000 | 0 | input and output |
| `power` | `MW` | 1000000 | 0 | input and output |
| `enthalpy_flow` | `kW` | 1000 | 0 | output |
| `enthalpy_flow` | `MW` | 1000000 | 0 | output |
| `molar_enthalpy` | `kJ/mol` | 1000 | 0 | output |
| `specific_enthalpy` | `kJ/kg` | 1000 | 0 | output |
| `molar_entropy` | `kJ/(mol K)` | 1000 | 0 | output |
| `specific_entropy` | `kJ/(kg K)` | 1000 | 0 | output |
| `dimensionless` | `%` | 1/100 | 0 | input and output |
| `mole_fraction` | `%` | 1/100 | 0 | input and output |
| `mass_fraction` | `%` | 1/100 | 0 | output |

## Gauge pressure and the ambient pressure

`barg` and `psig` are display units only: `p_gauge = p_absolute − p_ambient`, with the ambient
pressure the project declares. It is never assumed — a gauge unit in a project without a declared
ambient is refused `invalid_request` (`ambient_pressure_undeclared`). An operator declares it:

```
openflowsheet project ambient --project DIR --pressure 1.01325 --unit bar
openflowsheet project ambient --project DIR --clear
```

The value is converted to Pa (`Pa`, `kPa`, `MPa`, `bar`, `atm` or `psi`; a gauge unit is
refused), stored in `project-policy.json` as `ambient_pressure` and audited as `project_ambient`.
`get_project` reports it. It belongs to no revision, run, bundle, certificate, cache key or replay:
two projects that differ only in their ambient produce byte-identical runs. Declaring it changes the
project policy's `policy_sha256`, which jobs record as provenance.

## Input units

Inputs are unchanged by display units (ADR 0016): a revision or a change may give a quantity in
these units, converted to SI when it is validated. Gauge pressures are **not** accepted as inputs
(L-X04-1).

| Kind | Units accepted besides SI |
| --- | --- |
| `temperature`, `temperature_difference` | `degC`, `degF` |
| `pressure` | `kPa`, `MPa`, `bar`, `atm`, `psi` |
| `heat_rate`, `power` | `kW`, `MW` |
| `molar_flow` | `kmol/s`, `mmol/s`, `mol/h`, `kmol/h`; and the mass-basis `kg/s`, `g/s`, `kg/h` |
| `dimensionless`, `mole_fraction` | `%` (fractions only) |

## What stays SI

- Every stored or hashed document: revisions, bundles and every bundle member, artifacts,
  validation reports, job documents and the audit log (L-X04-2).
- Inside a converted response, the SI members themselves, the stream table's check quotes
  (`checks[].value`, `tolerance`: verification evidence), and run-failure `params`.
- The web shell's as-solved state table on the streams screen (L-X04-2).
- Every number without a display kind or row: the stream table's `S_flow`, `V_flow`, `rho`, `v`
  and `molar_mass`, and message numbers without a quantity kind (L-X04-3).

A display value is never an input to anything: no run, cache key, certificate, label, replay or
comparison reads one, and no request that starts or changes work accepts `display_units`.
