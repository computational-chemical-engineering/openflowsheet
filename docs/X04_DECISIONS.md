# X04 build decisions (engineer A: WO-1–WO-3)

Build-lane choices the spec (ADR 0075, `docs/derivations/X04-test-specification.md`) leaves open. Each is isolated
and revertible; none changes a number, an identity or a frozen interface. For the design lane's single ruling round.

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

## D-2. A13 "byte-identical bundle members" excludes the run manifest's wall-clock members

*Question.* Two solves of one revision differ, in any one project, in the run manifest's `started_at`,
`elapsed_seconds` and `manifest_sha256` (measured: the only differing members of `run-manifest.json` between an
undeclared and a 95000 Pa project), and so in the `replay_bundle`/`run_manifest` output hashes over them.
*Choice.* A13 compares every other bundle file byte for byte, the run manifest with those three members removed
(asserted present), and the whole `run_result` document with those two output hashes removed. Solution state,
certificate, structural hash, cache keys and `artifact_r0_sha256` are all compared.
*Alternative.* A fixed clock for the three solves (not available through `LocalApplication.solve`).
*Reversible by:* editing `WALL_CLOCK` in `tests/test_x04_ambient.py`.

## D-3. The M06 web fixture's three recorded `get_project` bodies gain `"ambient_pressure": null`

*Question.* ADR 0075 D6.3 makes `project_summary.ambient_pressure` required (nullable). The committed web-shell
fixture `tests/web/fixtures/w26/exchanges.json` records three `get_project` answers without it, so
`tests/test_m06_fixtures_valid.py` fails. Its generator (`scripts/m06_web_fixtures.py --write`) does not normalise
times: a rewrite would change every timestamp.
*Choice.* A surgical edit: `"ambient_pressure": null` inserted into the three bodies — exactly what today's server
answers for that undeclared project. Nothing else in the file changes.
*Alternative.* Re-record the fixture (`--write`), or make the member optional (contradicts D6.3).
*Reversible by:* reverting the commit that carries it.

## D-4. `project_summary.required` lists `ambient_pressure` last

*Question.* `scripts/t07_schema_fixtures.py` names each `$def`'s invalid fixture after the first entry of its
`required` list; listing the new member first renames `missing_capability_id.json`, which
`scripts/s13_evidence_manifest.py` (release version check) names.
*Choice.* `ambient_pressure` is appended to `required` (order has no meaning in JSON Schema); the invalid fixture keeps
its name and gains the member in its body.
*Reversible by:* reordering the list and updating the S13/release version-file path.
