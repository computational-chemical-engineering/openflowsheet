# Stream table and energy summary

After a solve, the **stream table** lists every stream of the flowsheet — temperature, pressure,
molar and mass flows, composition, vapour fractions and, per phase, enthalpy, entropy and density —
and the **energy summary** lists each unit's duty, work and energy balance and the flowsheet's
overall balance. It is computed from the run's bundle each time it is asked for, with the property
basis the run used, and is stored nowhere: it adds nothing to the run and changes none of its
identities. All values are in SI units.

## Getting it

| Transport | Call |
| --- | --- |
| Python | `app.get_stream_table(job_id)` — a `Projection` whose `value` is the document |
| CLI | `openflowsheet streams --project <dir> --job <job_id> [--format text\|json\|csv] [--output FILE]` |
| CLI, a bundle directory | `openflowsheet streams <bundle dir>` |
| HTTP | `GET /v1/jobs/{job_id}/stream-table` |
| MCP | the tool `get_stream_table` |

The job must have ended and written a replay bundle with a solution. A run that did not converge
has no solution state, and the request is refused `not_found`, naming the files the bundle does
hold and the run's outcome. A property basis that is not installed (CoolProp, for example) is
refused `unsupported` with what to install.

## A Rankine energy check in one call

Checking a cycle's energy balance used to take a property provider, an evaluation context and a
phase chosen by hand for each stream. With the table it is one call:

```python
from openflowsheet.application.local import LocalApplication

with LocalApplication.open("plant") as app:
    table = app.get_stream_table("job-000001").value

for stream in table["streams"]:
    mixed = stream["substreams"][0]
    print(stream["id"], stream["T"], stream["P"], mixed["vapor_fraction_molar"], mixed["H_flow"])

overall = table["energy"]["overall"]
print(overall["H_products"] - overall["H_feeds"], overall["Q"] + overall["W"], overall["closure"])
for unit in table["energy"]["units"]:
    print(unit["id"], unit["model"], unit["Q"], unit["W"], unit["closure"])
```

`closure` is `(Q + W) − (H_out − H_in)`, the verifier's sign, with duty and work counted positive
into the unit; next to it, each unit and the overall balance quote the certificate's own energy
check, with its tolerance and result.

## What the document holds

The document (`stream-table-v1`, schema `stream-table.schema.json`) has a header — the job, run,
revision, the state and certificate it was computed from, `verification_status`, `judged_at` and
the property basis with its reference convention — then `components`, `streams` and `energy`.

- **A stream** has `T`, `P`, its two ends, `dormant`, the checks the certificate holds for it, and
  one substream (`mixed` in this version).
- **The substream** has the flows `n` (mol/s) and `m` (kg/s) per component and in total, the mole
  and mass fractions `x` and `w`, the enthalpy, entropy and volume flows, `h`, `s` per mole and per
  kilogram, the density `rho`, the two vapour fractions, and its phases.
- **A phase** is identified by its family (`VAPOR`, `LIQUID`) and carries its own amounts,
  fractions and properties, including the molar volume `v`.
- **The vapour fractions** `vapor_fraction_molar` and `vapor_fraction_mass` are the vapour's share
  of the stream on a mole and on a mass basis; they are 0 or 1 for a single-phase stream. There is
  no member called "quality".
- `phase_source` says where the phases came from: `declared` (the stream's declared phase),
  `carried_split` (the vapour and liquid the solution carries), `flash` (an equilibrium flash at
  the stored temperature and pressure) or `zero_flow`. A flashed stream close to a phase boundary
  has `flash_near_phase_boundary` true: there the solve's verifier may have decided the phases
  differently.

Enthalpy and entropy are on the basis's reference convention, named in every substream
(`convention`); values from different bases are not comparable.

## Absent values

A value that cannot be given is `null`, and its object's `absent` map says why, with a message
code: a dormant stream has no temperature (`zero_flow`); a basis may not provide a property
(`property_not_provided`, for example the density of the Wilson basis's ideal-gas vapour); a property call or
a flash may fail (`property_evaluation_failed`, `flash_failed`); a value may not be finite
(`value_not_finite`); an energy total needs every stream's enthalpy flow
(`stream_enthalpy_absent`); and a unit model whose energy balance the certificate does not check
has no balance (`energy_balance_undefined`). Each code is explained in [Notices](../messages/notices.md)
and [Refusals](../messages/refusals.md), and by `openflowsheet explain <code>`. The text form shows
an absent value as `-` with a footnote, the CSV form as an empty cell.

## Reading it safely

The table describes the solution the run stored; it is not a verification. Read
`verification_status` (and `judged_at`, the state the verifier judged) before relying on the
numbers: the text form starts with a warning when the status is not `VERIFIED`.

Over HTTP and MCP the document arrives as a projection: the default `depth` (12) holds a whole
stream, and `pointer="/streams"` with `limit` and `cursor` pages the streams of a large flowsheet.
The CLI pages and assembles the document for you.
