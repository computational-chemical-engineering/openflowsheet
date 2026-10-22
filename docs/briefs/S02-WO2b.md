# S02 WO-2b — bubble-point endpoint, ADR 0044 trigger, tests (build lane, `opus-engineer`, ~100k)

Branch `wp/S02`. The task list is spec §18.7 "WO-2b" items 1–4 (`docs/derivations/S02-spec.md`, §18; definitions
§18.1–§18.6; open items §18.8) and ADR 0044 (Proposed, `docs/adr/0044-*.md`). WO-G is done (`5098069`, `cdaaf71`):
reference keys `cases.*.bubble_point*`, `variants.*.*.bubble_point` (six regular sets, not five — logged as a WO-G
ambiguity for the reviewer), `variants.M2.duty+duty.second_root`; new reference SHA-256 `9a6d262a…`. The §18.2
identity claim is open (Q-S02-WOG-1, `docs/S02_DECISIONS.md`) — not your concern; do not change the generator.

Known integration rules: B06 (`tests/test_t05b_literal.py`) — reuse a registered policy or add a named exemption the
registered way; never evade. ADR 0044's call-site change touches `orchestrator/recovery.py`, `executor.py`,
`cascade_solve.py` (S01, on `main`) — S01's suites must stay green.

## Exit test
§18.7 item 4: `pytest tests/test_s02_* tests/test_s01_* tests/test_t04_* tests/test_t03_*` green (no new xfail;
WO-2's strict xfails flip or are deleted with the replacement named in `docs/S02_DECISIONS.md`); ruff/format/mypy clean;
sweep counts and deviations recorded in `docs/S02_DECISIONS.md`.
