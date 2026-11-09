# X04 build decisions (engineer A: WO-1–WO-3; engineer B: WO-4, D-6 on)

Build-lane choices the spec (ADR 0075, `docs/derivations/X04-test-specification.md`) leaves open. Each is isolated
and revertible; none changes a number, an identity or a frozen interface. For the design lane's single ruling round:
**all twelve ruled** in `docs/reviews/X04-review.md` (2026-11-09), D-7 changed.

## D-1. A33's round-trip fixtures live in the X04 test modules, not in F0's M8 fixture directories

*Question.* A33 asks for round-trip fixtures (`job_result` with `display_units`, `project_summary` with
`ambient_pressure`, an `explanation` with a `display` item, `project-policy` with `ambient_pressure`). F0's M8
(`scripts/corpus_identity.py`) registers every collected node of the schema round-trip tests; a new fixture file
under `tests/fixtures/schemas/**` adds a node, which M8 reports as "measured, not registered" — F0 FAIL, against A35
("F0 passes with no change to its expectations").
*Choice.* The cases are round-tripped in `tests/test_x04_ambient.py` and `tests/test_x04_messages.py` (schema
validation, `from_document`/`as_document` identity), with no new file under `tests/fixtures/schemas/`.
*Alternative.* Add the fixture files and re-record M8 (an F0 expectation change: design-lane call).
*Reversible by:* moving the cases into fixture files and re-recording M8.
*Ruled (design lane, 2026-11-09, `docs/reviews/X04-review.md`):* **Keep.** A35 (F0 unchanged) outranks A33's "fixture files". The manifest records A33's fixtures as the in-module round-trip cases.

## D-2. A13 "byte-identical bundle members" excludes the run manifest's wall-clock members

*Question.* Two solves of one revision differ, in any one project, in the run manifest's `started_at`,
`elapsed_seconds` and `manifest_sha256` (measured: the only differing members of `run-manifest.json` between an
undeclared and a 95000 Pa project), and so in the `replay_bundle`/`run_manifest` output hashes over them.
*Choice.* A13 compares every other bundle file byte for byte, the run manifest with those three members removed
(asserted present), and the whole `run_result` document with those two output hashes removed. Solution state,
certificate, structural hash, cache keys and `artifact_r0_sha256` are all compared.
*Alternative.* A fixed clock for the three solves (not available through `LocalApplication.solve`).
*Reversible by:* editing `WALL_CLOCK` in `tests/test_x04_ambient.py`.
*Ruled (design lane, 2026-11-09, `docs/reviews/X04-review.md`):* **Keep.** Sound, not narrowed: the three members are asserted present; every other manifest member, every bundle file and the certificate are compared.

## D-3. The M06 web fixture's three recorded `get_project` bodies gain `"ambient_pressure": null`

*Question.* ADR 0075 D6.3 makes `project_summary.ambient_pressure` required (nullable). The committed web-shell
fixture `tests/web/fixtures/w26/exchanges.json` records three `get_project` answers without it, so
`tests/test_m06_fixtures_valid.py` fails. Its generator (`scripts/m06_web_fixtures.py --write`) does not normalise
times: a rewrite would change every timestamp.
*Choice.* A surgical edit: `"ambient_pressure": null` inserted into the three bodies — exactly what today's server
answers for that undeclared project. Nothing else in the file changes.
*Alternative.* Re-record the fixture (`--write`), or make the member optional (contradicts D6.3).
*Reversible by:* reverting the commit that carries it.
*Ruled (design lane, 2026-11-09, `docs/reviews/X04-review.md`):* **Keep.** The edit is exactly the server's answer for an undeclared project.

## D-4. `project_summary.required` lists `ambient_pressure` last

*Question.* `scripts/t07_schema_fixtures.py` names each `$def`'s invalid fixture after the first entry of its
`required` list; listing the new member first renames `missing_capability_id.json`, which
`scripts/s13_evidence_manifest.py` (release version check) names.
*Choice.* `ambient_pressure` is appended to `required` (order has no meaning in JSON Schema); the invalid fixture keeps
its name and gains the member in its body.
*Reversible by:* reordering the list and updating the S13/release version-file path.
*Ruled (design lane, 2026-11-09, `docs/reviews/X04-review.md`):* **Keep.**

## D-5. An `unsupported` display refusal carries its message head as `reason`

*Question.* ADR 0075 D9 raises `display_unit_unsupported` as "`unsupported`, reason" without fixing the `reason`
member's text. The bare code (`reason: "display_unit_unsupported"`) is what MSG reads first (§4.4 candidate order:
`detail.reason` before the message), and without its args it cannot fill the entry's required `kind`: the explanation
falls back to the outer `unsupported` entry and fails A36's strict rendering.
*Choice.* `reason` is the message head, `display_unit_unsupported(<kind>): "<unit>"` — the repo's precedent for a
reason with args (`surrogate_not_promoted(<id>)`, `local.py`). It renders strictly with its entry (A36 test).
*Alternative.* No `reason` member (the message alone renders the same), or the bare code with a renderer change.
*Reversible by:* `LocalApplication._display_units` (one line) and A36's `reason` assertion.
*Ruled (design lane, 2026-11-09, `docs/reviews/X04-review.md`):* **Keep.** The bare code cannot fill `kind`. The repo precedent is `surrogate_not_promoted(<id>)`, and it renders strictly (A36).

## D-6. The stream-table site table also lists the phase id's `ordinal` (never displayed)

*Question.* A24 asks that every number-typed property of every object of `stream-table.schema.json` be a key of the
implementation's site table, and that the table equal §4. The closed `phase_id` has `ordinal` (`integer`), which §4
does not list, while §4 does list the quote's `index` (also `integer`).
*Choice.* `stream_table.SITES` has `phase_id: {ordinal: None}` — an identity integer, never displayed, as `index` is;
A24's test asserts `SITES == §4 ∪ {phase_id.ordinal: None}`. No display changes.
*Alternative.* Count only `number`-typed properties (then §4's `index` is not one), or amend §4.
*Reversible by:* one entry in `SITES` and A24's expected table.
*Ruled (design lane, 2026-11-09, `docs/reviews/X04-review.md`):* **Keep.** Spec §4 is amended per N3.

## D-7. `get_stream_table.md`: the display sentence fits the 1500-character bound by trimming wording

*Question.* The description was 1486 characters; T07 §11.3's bound (`tests/test_t07_w6c_descriptions.py`) is 1500, so
WO-4's one sentence cannot be added without shortening the reviewed text.
*Choice.* One sentence added (`Optional display_units ("eng", "pressure=bar") adds "display" values in those units
beside the SI ones.`) and the existing text trimmed without dropping a fact: "computed" dropped, "the duty" → "duty",
"(positive into the unit)" → "(positive inward)", "the flowsheet's overall closure" → "the overall closure", the
absent-map sentence folded ("null, its typed reason (see explain) in its object's "absent" map"), "two calls
return" → "equal calls give", "(detail gives the run outcome and any bundle files)" → "(detail: run outcome, bundle
files)", "the property basis is not installed here" → "its property basis is not installed". 1499 characters;
REVIEW.json records the new hash with both reviews pending — the reviewers see the whole changed text.
*Alternative.* Raise the bound (a T07 §11.3 change), or a shorter sentence without an example.
*Reversible by:* the description file and its REVIEW.json entry.
*Ruled (design lane, 2026-11-09, `docs/reviews/X04-review.md`):* **Change:** use the review's text. The trims dropped no fact, but the display sentence omits ADR D3's "compute with SI". Applied: `get_stream_table.md` is the review's text (1500 characters), design-lane review recorded.

## D-8. `streams DIR --display-units` (a bundle directory) resolves the preference without an ambient

*Question.* D7.6 gives `streams --display-units`; a bundle directory has no project, so no declared ambient.
*Choice.* The preference is resolved with `parse_display_units(text, None)` and applied with
`stream_table.displayed`, so the display members equal the project mode's (A31-style test); a gauge unit is refused
`invalid_request`, `ambient_pressure_undeclared(pressure): "<unit>"`, pointer `/display_units`, exit 2+index as `api`.
No audit row (no project).
*Alternative.* Refuse the flag with a bundle directory (usage error, exit 2), or add an `--ambient-pressure` option.
*Reversible by:* `cli._bundle_display_units` and its call in `command_streams`.
*Ruled (design lane, 2026-11-09, `docs/reviews/X04-review.md`):* **Keep,** with S4.

## D-9. An out-of-range display value prints as an absent value

*Question.* D7.6 says values are `{:.6g}` of the display value; an out-of-range item has `value: null`.
*Choice.* `text` prints `-` with a footnote mark whose line is the reason, `display_out_of_range(kind=…, unit=…)`
(ST's footnote mechanism for typed reasons); `csv` prints an empty cell (ST's absent cell). The label or column still
names the display unit. No registered stream reaches this (A23 jobs); a test edits a document to hold one.
*Alternative.* Print the SI value under the display-unit label (wrong unit), or fall back to SI for the whole row.
*Reversible by:* `stream_table_format._shown` / `_x_cell`.
*Ruled (design lane, 2026-11-09, `docs/reviews/X04-review.md`):* **Keep.** `-` with a footnote (text) and an empty cell (csv) are ST's absent forms; a value under the wrong unit would be worse.

## D-10. Text labels without an SI unit gain `[unit]`; energy headers name every unit once one is converted

*Question.* D7.6: "every row label names its display unit (`T [degC]`), energy-table headers carry `[unit]` when any
energy kind is converted". The SI rows `vf molar`, `vf mass` and `x[<c>]` have no bracket; the energy table mixes
three kinds.
*Choice.* A converted row without a bracket gains one: `vf molar [%]`, `x[<c>] [%]`. When any of `enthalpy_flow`,
`heat_rate`, `power` is converted, every energy header carries its unit, the SI ones `[W]` (`H_in [W] … Q [MW] …`).
Unconverted labels are ST's.
*Alternative.* Bracket only the converted energy headers.
*Reversible by:* `stream_table_format._label` and the header block of `to_text`.
*Ruled (design lane, 2026-11-09, `docs/reviews/X04-review.md`):* **Keep.**

## D-11. The stream-table schema states `display` per object with `propertyNames`, the item shape once

*Question.* ADR 0075 amends `stream-table.schema.json` with optional `display` members on six objects; WO-3's rule is
inline shapes, no new `$def` (a `$def` adds a T07 fixture and moves F0 M8).
*Choice.* Each object's `display` is `{type: object, minProperties: 1, propertyNames: {enum: <its converted members>},
additionalProperties: <item or array of item|null>}`; the item shape is written once, in the stream's `display`, and
the other five reference it by pointer (`#/$defs/stream/properties/display/additionalProperties`) — no new `$def`.
The item is WO-3's (`{value: number, unit}` or `{value: null, unit, reason: display_out_of_range}`). The root gains
`display_units` as `job_result`'s. So a display entry for `rho` or an empty `display` is refused (A33 test).
*Alternative.* Six inline copies of the item, or an open `display` map.
*Reversible by:* the schema edit (one commit).
*Ruled (design lane, 2026-11-09, `docs/reviews/X04-review.md`):* **Keep.** Its `propertyNames` enums match `SITES` exactly; the item `oneOf` is loose (array or scalar for any member), which is harmless.

## D-12. A13 also leaves out the bundle's and the manifest's `size_bytes` (a flaky comparison, found in WO-4)

*Question.* `test_a13_the_ambient_is_not_in_run_identity` failed 3 of 4 runs at `df59a3df` (before WO-4): the run
results differed in `size_bytes` by one byte (2335 vs 2336, 54307 vs 54308). D-2 drops the `sha256` of the
`replay_bundle` and `run_manifest` outputs because they cover the manifest's wall-clock members; their sizes cover the
same members, and `elapsed_seconds`'s digit count varies from run to run. Every bundle file is still compared byte
for byte (the manifest without its three wall-clock members).
*Choice.* The test deletes `size_bytes` beside `sha256` for those two outputs. 4 of 4 passes after.
*Alternative.* A fixed clock (not available through `LocalApplication.solve`, as D-2 says).
*Reversible by:* the one line in `tests/test_x04_ambient.py`.
*Ruled (design lane, 2026-11-09, `docs/reviews/X04-review.md`):* **Keep.** Sizes cover the same wall-clock members as D-2's hashes. A fixed clock seam would be cleaner later; it is not needed here.

## D-13. A40's page is `docs-site/guide/display-units.md`, not `guide/units.md`

*Question.* A40 names `docs-site/guide/units.md`, but that path is the generated "Unit catalogue" (unit operations,
`scripts/doc_pages.py` `PAGE`, checked by `tests/test_doc_pages.py`).
*Choice.* A new hand-written page `docs-site/guide/display-units.md` ("Display units", in `mkdocs.yml` after the
stream table); A40's test reads it. *Alternative.* Rename the unit catalogue (moves a generated page and its links).
*Reversible by:* moving the page and the test's path (commit `X04 WO-5: docs-site/guide/display-units.md`).

## D-14. The web shell's SI choice sends no `display_units`; a gauge choice without an ambient falls back to SI

*Question.* A38 says the choice "is sent as `display_units`"; for SI that could be `"si"` (adds the root echo) or no
member. A stored gauge choice can meet a project without an ambient.
*Choice.* SI sends no member, so the SI screens read exactly the pre-X04 documents (the M06 fixtures and smoke routes
stay valid); a gauge choice is disabled without a declared ambient and, if stored, resolves to SI there (never
assumed, ADR 0075 D6.4). *Alternative.* Send `"si"` (every fixture re-recorded); fall back to `eng`.
*Reversible by:* `apps/web/js/units.js` (`displayRequest`, `effectiveUnits`).

## D-15. `apps/web/js/routes.js` was stale on `wp/X04` (found in WO-5)

*Fact, not a choice.* `scripts/m06_web_routes.py --check` failed since WO-3/WO-4 added `display_units` to the two
request schemas (the route table's `members`); `tests/test_m06_static_scan.py` was outside the targeted battery.
Regenerated (`--write`), `--check` clean.
