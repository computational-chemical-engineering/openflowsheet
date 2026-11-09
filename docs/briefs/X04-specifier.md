# Specifier brief: X04 — units of measure at the boundary (0.4)

Status: brief, 2026-11-09. Design lane, one specifier pass. **Do not spawn sub-agents yourself.** Reading only; no code.

## 1. The question

What exactly does X04 add so that a user can work in °C, bar, kmol/h (and the other common engineering units) at every
boundary — inputs, outputs, messages, the web shell — while internal state stays ADR 0001's SI? Deliver an ADR plus a
test specification with numbered, falsifiable assertions that an engineer can implement from without deciding anything
scientific.

## 2. Why the design lane

Units are scientific semantics (CLAUDE.md: the design lane leads units/state). Wrong choices here leak into identity
(cache keys, certificates, replay), into gauge/absolute pressure and temperature/temperature-difference arithmetic, and
into every transport. No spec, ADR or brief for X04 exists (recon 2026-11-09).

## 3. Current state (facts, anchors)

- **Inputs are already converted.** ADR 0016 (`unit-conversion-v2`, R-081) converts a specification value or instance
  parameter written in a tabled unit to SI exactly at validation and binding, and records the conversion. Code:
  `src/openflowsheet/units/__init__.py` (docstring :1–22; `_ROWS` :405–431; `convert_input_value` :494–521). The
  table (keyed by (target kind, unit as written), case-sensitive): temperature degC, degF; temperature_difference degC,
  degF (scale only); pressure kPa, MPa, bar, atm, psi; heat_rate and power kW, MW; molar_flow kmol/s, mmol/s, mol/h,
  kmol/h, and kg/s, g/s, kg/h (mass_to_molar, needs the component's molar mass); dimensionless and mole_fraction %.
  Arithmetic `RN(a·D(v) + b)` on the decimal the input denotes (R-081: the binary reading was not unit-invariant).
  Consumers: `application/validation.py:1043–1127` (check DIM-01), `application/binding.py:970`,
  `models/revision_flowsheet.py:696,807`. Tests: `tests/test_t06_w1a_units.py`, `tests/test_t06_w12_units_v2.py`,
  `tests/test_schemas_p01.py`, fixtures `tests/fixtures/schemas/quantity/*`.
- **Register R-077** (`docs/decision-register.md:2028`): only ADR 0001/0016 input units accepted; "Lifted as policy
  (Frank, 2026-11-01; R-925, ADR 0056): package X04. The behaviour below stays until that package lands."
- **ADR 0056 row 7** (`docs/adr/0056-capability-extension-plan.md:33`): "A unit registry for inputs and outputs (°C,
  bar, kmol/h, …) converted at the boundary; internal state stays ADR 0001's SI; display units in the web shell".
- **Target architecture C4** (`docs/roadmap/target-architecture.md` ~:760): "Conversion only in dispatch and in
  projection; internal values stay SI (ADR 0001 D1.1, ADR 0016 D1.2). Display preferences outside identity. A gauge
  pressure needs a declared ambient pressure, per project (R-924)". Constraint on 0.4 packages: "X04 works at the
  boundary only."
- **Slots waiting for X04.** MSG I10 (`docs/design/MSG-messages.md` ~:103): numbers carry SI values and symbols from
  `schemas/units.json`; MSG converts nothing; X04 fills `RenderContext.display_units`
  (`src/openflowsheet/messages/render.py:64–72`, a `Mapping[str, str] | None`, always `None` today; MSG design §4.5,
  Q6 ~:1415). ST C-4 (`docs/design/ST-stream-table.md` ~:35): the stream table is SI only (K, Pa, mol/s, kg/s, J/mol,
  W, …); X04 is boundary-only.
- **Output side today:** no display/output converter anywhere in `src/` (grep `display_unit`, `output_unit`); the only
  mention is a refusal text at `units/__init__.py:305` ("display units belong in display_unit", ADR 0001 D1.1).
  Catalogue: DIM-01 only (`messages/catalogue/checks.yaml:40–51`).
- **Transports:** Python, CLI, HTTP, MCP; the web shell (ST WO-8b added a streams screen showing the stream table).
  Operations are rows in OPERATIONS (C1: no capability on one transport only).

## 4. Constraints and invariants

- Internal state, certificates, cache keys, replay bundles, served-document identity (surface chain, F0 corpus
  identity M1–M9) do not change: a run with display units set is bitwise the run without them. Display preferences are
  outside identity (C4). F0 must stay PASS unchanged.
- Input conversion stays ADR 0016's exact arithmetic; X04 may widen the table only by an explicit decision (say which
  rows, if any, and why).
- Temperature vs temperature difference, absolute vs gauge pressure: gauge only with a declared ambient pressure per
  project (R-924); define how that is declared, where it lives (project, not revision identity?), and what happens
  without it (typed refusal with a catalogue entry).
- MSG: every new code has a catalogue entry (G2); I10's slot is the only rendering hook.
- Frozen interfaces (plan §2.1) and schemas (§2.2) change only additively and only by this ADR.
- Output conversion must not round in a way that a user could mistake for the verified value: state the rule (exact
  rational scale/offset applied to the binary SI value? decimal formatting? significant digits?) and how a converted
  number is labelled (unit symbol always shown).

## 5. Decided, not open

- X04 is in 0.4, after MSG (Frank). Boundary-only (target architecture). Web-shell display units are in scope (ADR 0056
  row 7). Capability over restriction (R-924, R-927): admit with declared limits.

## 6. Genuinely open (decide each, with a default)

1. Where display preferences live and how each transport passes them (per request parameter, per session, per project
   setting, web-shell preference) — and the precedence.
2. Which outputs convert: stream table values, result documents, messages (`RenderContext.display_units`), CLI text
   tables; which stay SI always (machine documents? hashed documents certainly).
3. The output unit table (start from ADR 0016's rows; add e.g. kJ/mol, kJ/kg, kmol/h for flows, kg/h, °C for
   temperature, bar/barg for pressure?) and its kind keying.
4. Gauge pressure: syntax (`barg`?), ambient declaration, refusal when undeclared.
5. Machine-readable form of a converted value (e.g. `{value_si, unit_si, display: {value, unit}}` or a separate view),
   so agents never parse rendered strings.
6. Whether R-077's input side widens in 0.4 or only the output side lands.

## 7. Verification (what the test specification must make executable)

Numbered assertions with exact expected values (rational conversions — give fractions), including: round trip
input→SI→display for each row; temperature difference vs temperature; gauge with and without ambient; identity
invariance (same certificate/cache key/bundle hash with and without display units; F0 PASS); each transport carries the
preference identically; every new code has a catalogue entry; refusal cases.

## 8. Deliverable

- `docs/adr/0075-X04-units-at-the-boundary.md` (Proposed; check the next free ADR number first — 0074 is the last),
  with decisions D1…, affected requirements, migration impact, acceptance evidence, and a "Frank questions" section
  (each with a default) only for value judgments.
- `docs/derivations/X04-test-specification.md` (or a section of the ADR) with numbered assertions A1… and exact values.
- A work order list for the build lane (files, operations, schemas, catalogue entries, tests), sized for one or two
  engineers of about 150k context each.
- Commit on **main** (docs only, named paths, message `docs: X04 units at the boundary — ADR 0075 (Proposed) and test
  specification`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
  https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; `git pull --rebase` if the push is rejected). If you put
  a derivation script under `docs/derivations/scripts/`, it is ruff-linted by CI: run `ruff check` and
  `ruff format --check` on it.

## 9. Out of scope

Internal unit handling, solver scaling, LLE, dynamics, X01 registries beyond what X04's table needs, rewriting ADR 0016's
arithmetic. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`,
`~/.cache/seider4/`. TRS2 shared: `uptime` first; reading only.

## Report (≤ 20 lines)

ADR number and path, the decisions in one line each, the Frank questions with defaults, the work orders, commit sha.
