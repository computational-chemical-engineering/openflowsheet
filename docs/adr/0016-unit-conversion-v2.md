# ADR 0016 — Input units by recorded conversion: `unit-conversion-v2` (widens ADR 0001 D1.1 and D1.4)

**Status:** Accepted 2026-09-27 — T06's manifest `evidence/T06/ebec629d63e32fb1984b56ad31372c960cd0ae2f/manifest.json` is `tested` (100 checks: 96 pass, 4 not_applicable with reasons; A29/A30 judged on scoring run 2, run 1's FAIL carried), after the design-lane review `docs/reviews/T06-review.md` and verdicts `docs/reviews/T06-verdicts.md`. Frank approved widening ADR 0001 D1 (2026-09-26). Agent acceptance is numerical and procedural: `review.numerical` and `review.process_model` remain `pending`.  
**Date:** 2026-09-26
**Author:** design lane (`specifier`); brief `docs/briefs/T06-amendment-2.md` §1 (its §3 holds the ruling list).
**Normative text:** this ADR (D1–D9) and `docs/derivations/T06-corpus-spec.md` §8.5 as amended by Amendment 2; machine-readable table and known answers `ref.closed_form.unit_conversion_v2` in `benchmarks/t06/reference_values.yaml`, emitted by `docs/derivations/scripts/t06_reference.py`.
**Amends:** ADR 0001 D1.1 (clarified for input documents) and D1.4 (generalized from the mass basis to the table of D3); ADR 0014 D6 as amended by its Amendment 1. **Reverses:** R-077's arithmetic ("one binary64 operation on the binary64 operand") and its unit set ("exactly ADR 0001 D1.3–D1.4, nothing wider"), for the reasons in D2 and *Alternatives*; R-077's readers, records and refusal codes stand.
**Affected requirements:** D08 (the thermodynamic/units contract), V20 (STA-03), A04 (the corpus's metamorphic cases); blueprint §4.2 ("SI internally … display units are conversion metadata"), §4.3 (the `dimensions` stage).
**Affected packages:** P01 (`process_runtime.units`: the function), K06 (`application/binding.py`, `application/validation.py`), T05 (`models/revision_flowsheet.py`: `convert_specification`, `read_parameter`; `tests/test_t05_w11_cases.py`), K04 (`verify/certificate.py::_revision_values`), T06 (W1a's tests, STA-03, the new assertions A67–A74), T07 (storing an SI twin with `display_unit` at commit, unchanged by this ADR).

## Context

ADR 0001 D1.1 stores every internal quantity in unprefixed SI; D1.3–D1.4 convert exactly two kinds of input — a `temperature` in °C and a mass-basis component flow — at validation time, recording the conversion. T06 Amendment 1 implemented those two as `unit-conversion-v1` and refused every other unit, because a wider table widens a frozen rule (spec Q11). Frank decided Q11 on 2026-09-26: specifications **and instance parameters** accept other common units by recorded conversion — at least pressure (kPa, bar, MPa, atm, psi), power and duty (kW, MW), temperature (°C, °F), flow (multiples of mol/s, kmol/h, kg/s, kg/h), fractions (%) — and unknown units stay refused.

Two facts measured for this ADR decide its arithmetic (`t06_reference.py`, claims `units_v2.*`):

- v1 converts the **binary64** operand: `fl(v + 273.15)`, `fl(v / M_c)`. For a factor that is not a power of two this makes two spellings of one quantity bind to different doubles. `−40 °C` binds to 233.14999999999998 K under v1, one ulp from `233.15 K`; C1's pump efficiency written `75.1 %` would bind to 0.7509999999999999 under the same reading, one ulp from the registered `0.751` — so a converted revision would not be its SI twin, and STA-03-style metamorphic identity (A55, A56) would hold only by coincidence.
- Reading the operand as the decimal the user wrote — the shortest decimal that rounds to `v`, which is what `repr` prints and what a YAML/JSON writer emits — and rounding the exact result once, every registered metamorphic pair binds to its SI twin bit for bit (23 of 23 pairs), and every group of spellings of one quantity binds to one double (5 of 5 groups).

## Decision

### D1. Scope

1. **Input documents only.** A revision's specification `value` and an instance parameter Quantity's `value` (with its `bounds` and `nominal`) may be written in a unit of D3's table for the kind their target requires. Each is converted to that kind's SI unit **at validation and at binding** by `unit-conversion-v2`, and the conversion is recorded (D6).
2. **Internal storage is unchanged (ADR 0001 D1.1 stands).** Nothing the runtime stores, compiles, hashes into `constants_sha256`, solves or certifies is in a non-SI unit. `check_quantity` (P01) is unchanged: for an instance parameter it is applied to the parameter's **SI twin** — the Quantity with `value`, `bounds.lower`, `bounds.upper` and `nominal` converted by the same row and `unit` replaced by the SI unit. `ComponentRecord` and every emitted document stay SI-only; `display_unit` stays presentation metadata.
3. A specification's `bounds` and `tolerance` are still read by no v0.1 code. The reader that first needs them converts `bounds` by the row's full map and a tolerance's absolute part by the row's linear part `a` only (a difference carries no offset); that reader's package registers the test.

### D2. The arithmetic

**`SI = RN(a·D(v) + b)`**, where

- `v` is the binary64 value as read, **finite** (else refused, reason `value`);
- `D(v)` is the **shortest decimal string that rounds to `v`** under round-to-nearest-even, the one nearest `v` when several are shortest (Steele–White/Gay; CPython's `repr(float)` implements it on every platform) — read as an exact rational;
- `a > 0` and `b` are **exact rationals** fixed by the unit's definition (D3); for a mass-basis row `a` is divided by `D(M_c)`, the decimal of the component's molecular weight;
- the arithmetic is exact and **RN is one round-to-nearest-even to binary64**; a zero result is `+0.0` (ADR 0001 D1.5); a result outside the finite binary64 range is refused (reason `value`).

The SI unit of each kind is the identity: `v` returned unchanged, no record (as v1's U3). **Unit invariance** follows: two inputs whose decimals denote the same exact quantity bind to the same double, and a converted input binds to its SI twin exactly when the twin's value is the decimal of that quantity. The result is platform-independent: exact rational arithmetic and one IEEE rounding. An implementation computes it as `float(Fraction(repr(v)) * a + b)` (CPython's `int / int` true division is correctly rounded); **it may not substitute a binary64 chain** (`v * 1e-3`, `v / 3.6`, `(v − 32) * 5 / 9 + 273.15`), which `ref.closed_form.unit_conversion_v2.known_answers.rows` refuses row by row (claim `units_v2.every_naive_chain_is_refused_by_a_known_answer`).

**What moves from v1.** STA-03's two conversions (`26.85 degC → 300.0 K`, `0.1 kg/s → 1.0 mol/s`) and A56's control (`86.85 → 360.0`, `84.85 → 358.0`) are unchanged (claim `units_v2.sta03_and_a02_control_unchanged_from_v1`). The v1 known answers chosen *because* the binary64 sum differed from the decimal one move by one ulp to the decimal's value: `−40 degC` 233.14999999999998 → 233.15; `12.34 degC` 285.48999999999995 → 285.49; `0.01 degC` 273.15999999999997 → 273.16; `0.3 kg/s` over the synthetic masses 0.1, 0.2, 0.04401 kg/mol: 2.9999999999999996 → 3.0, 1.4999999999999998 → 1.5, 6.816632583503749 → 6.81663258350375 (`ref.closed_form.unit_conversion_v2.known_answers.v1_known_answers_under_v2`). No registered revision uses any of them.

### D3. The table

Rows are keyed by the **kind the target requires** (`_PATH_KINDS`, `_PARAMETER_KINDS`, unchanged) and the unit string, matched **exactly** (case-sensitive ASCII). "Declared kinds" is what the specification's `kind` (or the parameter Quantity's `kind`) may say.

| Required kind | Unit | `SI =` (exact, then RN) | Declared kinds | Targets |
| --- | --- | --- | --- | --- |
| `temperature` | `degC` | `D(v) + 273.15` | `temperature` | `state.T`, `outlet.T` |
| `temperature` | `degF` | `(D(v) − 32)·5/9 + 273.15` | `temperature` | same |
| `temperature_difference` | `degC` | `D(v)` | `temperature_difference` | none in v0.1 |
| `temperature_difference` | `degF` | `D(v)·5/9` | `temperature_difference` | none in v0.1 |
| `pressure` | `kPa`, `MPa`, `bar`, `atm`, `psi` | `D(v)·10³`, `·10⁶`, `·10⁵`, `·101325`, `·0.45359237·9.80665/0.0254²` | `pressure` | `state.P`, `outlet.P`, `parameters.pressure_drop` |
| `heat_rate` | `kW`, `MW` | `D(v)·10³`, `·10⁶` | `heat_rate` | `duty.Q` |
| `power` | `kW`, `MW` | `D(v)·10³`, `·10⁶` | `power` | none in v0.1 |
| `molar_flow` | `kmol/s`, `mmol/s`, `mol/h`, `kmol/h` | `D(v)·10³`, `/10³`, `/3600`, `·10³/3600` | `molar_flow` | `state.n` with one component |
| `molar_flow` (mass basis) | `kg/s`, `g/s`, `kg/h` | `D(v)/D(M_c)`, `/(10³·D(M_c))`, `/(3600·D(M_c))` | `molar_flow`, `mass_flow` | `state.n` with one component `c` of the component set |
| `dimensionless` | `%` | `D(v)/100` | `dimensionless` | a **fraction**: `parameters.split_fraction`, `.efficiency`, `.conversion.<c>`, `.split.<c>` |
| `mole_fraction` | `%` | `D(v)/100` | `mole_fraction` | none in v0.1 |

Every kind's SI unit (`K`, `Pa`, `W`, `mol/s`, `kg/s`, `1`, …) is the identity row. Pressure units are **absolute**; `psi` is the pound-force per square inch of the 1959 international definitions, 6894.757293168361… Pa exactly (`8896443230521/1290320000` Pa, claim `units_v2.psi_is_the_1959_definition`). `M_c` comes from the one id-keyed molecular-weight table of T06 spec §8.5 (SYN-001's 0.100 kg/mol for A, B and C).

### D4. The steps (`unit-conversion-v2`, in order)

| Step | Condition | Result |
| --- | --- | --- |
| V0 | `v` not finite | refused, reason `value` |
| V1 | the target path has no required kind (neither table names it) | identity iff `unit` is the SI unit of the declared kind; else refused, `unit` (the path is refused elsewhere, as today) |
| V2 | the declared kind is not the required kind, nor `mass_flow` on a one-component `molar_flow` target | refused, `kind` |
| V3 | declared kind = required kind and `unit` is its SI unit | identity, no record |
| V4 | a row of D3 matches (required kind, `unit`), admits the declared kind, and admits the target (a fraction for `%` on `dimensionless`; a component with a molecular weight for a mass row) | D2's value; record (D6) |
| V5 | otherwise | refused, `unit` |

A result out of the binary64 range is refused at V4 with reason `value`. Readers turn reasons into their registered codes: specifications `specification_kind_unsupported(<id>)`, `specification_unit_unsupported(<id>)` and — **new** — `specification_value_unsupported(<id>)`; parameters `parameter_kind_unsupported(<instance>.<name>)`, `parameter_unit_unsupported(<instance>.<name>)` and `parameter_quantity_invalid(<instance>.<name>)` (a nonfinite Quantity value is already a `check_quantity` finding).

### D5. Where it runs

One pure function in `process_runtime.units`, id **`unit-conversion-v2`**; it **replaces** `unit-conversion-v1` (one function, one id; nothing registered needs v1's refusals or its binary reading). Every reader of an input value goes through it:

- **specifications:** the four readers of T06 spec §8.5 — (R1) the legacy binding, (R2) `models/revision_flowsheet.py::_read` (and so `verify_revision`'s `parse_revision`), (R3) `verify/certificate.py::_revision_values`, (R4) `DIM-01` — all through `convert_specification`;
- **instance parameters:** `read_parameter` (R6), which the legacy binding, `_read` and `DIM-01` already share.

**A component reference is judged before a unit.** A specification whose `target.component` is not in the component set is refused for its component by both bindings (the legacy binding `Unbound("conflict", "component_unknown(<id>, <c>)")`, the revision binding its existing `specification_unsupported(<id>)`), whatever its unit, and `DIM-01` does not judge it (`COMP-03` fails it). The unit never changes the diagnosis of a component error.

A parameter pinned both on its instance and by a specification (`_read`'s `specification_conflict`) is compared on the **converted** values, bit for bit.

### D6. Records

Each conversion yields `{source: "specification" | "parameter", input_id, value as written, unit as written, si_value, si_unit, rule, component, molar_mass}` — `input_id` the specification id or `<instance>.<name>`; `rule` one of `degC_to_K`, `degF_to_K`, `mass_to_molar`, `scale`; `component` and `molar_mass` for `mass_to_molar` only. (This replaces v1's `specification_id` field; the record content is otherwise v1's.) Order: specifications in document order, then parameters by instance declaration order and, within an instance, by parameter name in code-point order — so the order is a function of the revision's canonical form (`revision_sha256`), not of a mapping's key order. Records are carried by each binding's `input_mapping.conversions` (with `input_mapping.declared_components`, which is **always** recorded, the canonical order included) and by `DIM-01`'s `PASS` message and implicated ids: message `converted by unit-conversion-v2: ` then `<input_id> <value!r> <unit> -> <si!r> <si unit>` per record (with ` (M_<c> = <M!r> kg/mol)` for `mass_to_molar`), joined by `; `. **The certificate carries none** (it judges the declaration, which is SI by construction; R-035).

### D7. Identity

A converted revision whose conversions return its SI twin's doubles binds to exactly the twin's pins, parameters, label, `configuration_sha256`, `constants_sha256` and `variable_ids`, so its trace and certificate are the twin's byte for byte (A55, A56, A69–A71); `revision_sha256` differs (it hashes the document) and `input_mapping` records the difference. No registered revision uses a non-SI unit, so no registered binding, label, key, trace or certificate moves (the inertness proof of W12).

### D8. What stays refused

Any unit string not in D3 for the target's required kind (`°C`, `C`, `degc`, `kpa`, `mbar`, `hPa`, `mmHg`, `Torr`, `t/h`, `lb/h`, `lbmol/h`, `kJ/h`, `BTU/h`, `ppm`, …); **gauge or suffixed pressures** (`barg`, `psig`, and also `bara`, `psia` — one spelling per unit; gauge needs an ambient pressure the revision does not carry); `%` on a non-fraction (`nu.<c>`, any temperature, pressure or flow); a mass basis on a target without one component of the set; a declared kind the target does not admit; nonfinite and overflowing values. Registered as `ref.closed_form.unit_conversion_v2.known_answers.refusals` (18 cases, claim `units_v2.refusals_as_registered`).

### D9. Migration

1. `tests/test_t05_w11_cases.py::test_a_value_outside_its_si_unit_is_refused` keeps all eight cases and all eight codes; its four unit mutations are re-pointed to units that stay refused — `kPa-drop` → `mmHg-drop`, `percent-split` → `ppm-split`, `bar-pin` → `barg-pin`, `parameter-pin-unit` → `parameter-pin-ppm`, with the same codes — and the four old mutations move to T06 A73 with their new, measured outcomes (the SI twins' bindings, measured 2026-09-26): `kPa` drop `0.0` binds (a record `0.0 kPa -> 0.0 Pa`); `bar` pin `100000.0` binds at `1e10 Pa` (outside the provider's domain, which is the solve's business, not the binding's); `%` split `0.5` and `%` specification `0.5` are refused `Unbound("conflict", "specification_conflict(SPEC-splitter-r, U-SPLIT.split_fraction)")` (the instance and the specification now disagree: 0.005 against 0.5). No case is removed and no check is relaxed: Frank's decision changes what these inputs mean.
2. T06 A57 (a) is re-pointed from `degF` (now converted) to `°C`; A57 (e) is superseded by A73; A58 (v1's known answers) is superseded by A67 when W12 replaces v1, and its test is replaced, not relaxed.
3. `docs/interfaces-frozen.md` §3 gains a note that ADR 0001 D1.1/D1.4 are widened by this ADR (the build lane, with the commit that lands W12). Recommended, text only: `schemas/quantity.schema.json`'s `unit` description cites this ADR for a revision's instance parameters; no schema keyword changes.

## Alternatives considered

- **v1's binary reading, widened** (`RN(a·v + b)` on the binary64 `v`, or a chain of binary64 operations). Rejected: two spellings of one quantity bind to different doubles (−40 °C ≠ 233.15 K; 75.1 % ≠ 0.751), so a converted revision is its SI twin only by coincidence, and each non-power-of-two row needs its own arithmetic argument. A1 rejected the decimal reading as "a second arithmetic for a ≤ 1-ulp difference nothing needs"; the need is now measured (C1's 75.1 %), and v2 has one arithmetic, not two.
- **Keeping v1 beside v2.** Rejected: two functions and two ids for one rule; nothing registered depends on v1's refusals, and its two conversions keep their registered values.
- **Converting at an API boundary only (T07), leaving the bindings SI-only.** Rejected: Frank's Q11 is "in T06", and every binding is callable without an API in front of it.
- **Storing the converted value in the revision (rewrite to the SI twin at binding).** Rejected, as in A1: the binding does not own the revision; an application-layer commit may store the SI twin with `display_unit` (T07).
- **Aliases** (`°C`, `C`, `psia`, `kpa`, `percent`). Rejected for v0.1: every alias is a second spelling to test and a Unicode normalization question; each is an additive row later (Q14).
- **Gauge pressures with an assumed ambient (101325 Pa).** Rejected: an assumption about the site the revision does not state; the pressure-drop parameter is also of kind `pressure`, where an offset would be wrong.
- **`%` on every dimensionless target.** Rejected: a stoichiometric coefficient in percent is not a quantity; the fraction set is registered by name.
- **Converting inside the residual or the provider.** Rejected: ADR 0001 D1.1 and the units layer's own rule ("no implicit unit coercion inside a residual evaluation").

## Consequences

- C1. Frozen interfaces: ADR 0001 D1 (a P01-frozen semantic rule) is widened as D1 states, by Frank's decision. No `Protocol`, schema keyword, quantity kind, `schemas/units.json` entry, tolerance, check-policy byte or `SolveEvent` value changes. The revision binding gains one refusal code, `specification_value_unsupported(<id>)` (a non-frozen vocabulary).
- C2. No registered result moves (D7). W1a's `unit-conversion-v1` code and A58's test are replaced (D9.2).
- C3. T07 inherits: storing an SI twin with `display_unit`; converting `bounds`/`tolerance` when first read (D1.3); presenting results in a declared unit; aliases (Q14).

## Acceptance evidence

T06 spec §13's A67–A74 and the amended A55–A57 in `evidence/T06/<commit>/manifest.json`: A67 (every row's known answer, bit for bit), A68 (the refusals), A69–A71 (metamorphic pairs on the tear path, the revision path and a nonzero pressure drop, byte-identical to their SI twins), A72 (component-before-unit, nonfinite values, `%` on `nu`, conflicts on SI values), A73 (T05's re-pointed test and the four migrated mutations), A74 (`DIM-01`'s message and order). The twin's `--check` passes (340 claims), two `--emit` runs are byte-identical, and `t02`…`t05b` are unchanged by W12.

## What this ADR does not establish

It says nothing about units in results or reports (all SI), about any unit outside D3, about `bounds`/`tolerance` conversion (no v0.1 reader), or about the physical meaning of a pressure written without a gauge/absolute qualifier (every pressure is absolute). The mass basis's component index is not discriminated by SYN-001's equal molecular weights; only the synthetic table of the known answers sees it (claim `units_v2.synthetic_masses_separate_components`).
