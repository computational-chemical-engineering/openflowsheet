# Brief — T08: apply Amendment 1, register PTC-R1 (W3, `C_case`), extend D1

**To:** `opus-engineer` (build lane). **From:** the session, 2026-09-29. **Branch:** `wp/T08`, HEAD after
`C_A1` = `30243f9`.
**Design (binding):** `docs/derivations/T08-build-first-spec.md` — **Amendment 1** (§Am1.0–§Am1.J, from line
≈ 578; its §Am1.C rows replace §C.1's rows of the same id), and for W3 §A4.2, §A4.5, §A4.6, §A2 and B20/B21.
ADR 0023 with its Amendment 1. `C_reg` = `9f5f29d`, `C_A1` = `30243f9`.

## Items, in this order, one commit each (messages start `T08 …:`)

1. **Register** (message `T08: register R-126, R-127`): add §Am1.J's R-A1a and R-A1b to
   `docs/decision-register.md` as **R-126** and **R-127**, in the format of R-116…R-125 (read R-125's section),
   and update the "next free" paragraph if it names R numbers (it names ADR numbers; 0025 stays next).
2. **§Am1.I item 2** — W2 tests follow Q1/Q2 (`tests/t08_cstr_support.py`, `tests/test_t08_kinetic_cstr.py`).
3. **§Am1.I item 3 — W3, the registration commit `C_case`.** `benchmarks/t08/ptc_r1/revision.json`,
   `case.json` (per B20 and §A4.6 as amended: the four policies' `policy_sha256`, the revision's
   `content_sha256`, the start digest `0262bebc…`, the YAML's sha256, `C_reg` and `C_A1`), the two benchmark
   policies `T08-PTC-R1-newton` / `T08-PTC-R1-ptc` (not offered), `T08-ptc-v1` in code, and the harness
   `benchmarks/t08/ptc_r1/compare.py` per §A4.5 (recording the final C flows and any C-column blocker per run).
   Tests: B13–B15 on the bound revision, the B20 ancestry test, B26. **The harness is committed NOT RUN.**
   Message: `T08 W3 (C_case): register PTC-R1 …`, and include in the body: "This commit is C_case. No PTC-R1
   result exists at or before it."
4. **§Am1.I item 4** — offer `T08-ptc-v1`, switch G16-b's reference runs to
   `docs/derivations/scripts/t07_reference_t08.json`, update the `project_summary` fixture by the two policies
   only. This should turn the 5 known red tests green; if not, report, don't bend.
5. **§Am1.I item 5** — W4 tests B41, B42, B46 as §Am1.C.
6. **§Am1.I item 6** — Q-P1-1: pass `plan=` for the initializer failure bundle; the pinned digests
   `e07f19c5…`, `6eeb7757…` move by substitution only (test shows empty ids reproduce them); re-run the
   substitution proof and T08.A13.
7. **D1 extension (Frank, 2026-09-29):** STR-04 and STR-05 messages use the revision's instance ids, like
   STR-03 (`validation.py`; see commit `d8941b8` for the STR-03 pattern and `tests/t08_d1_substitution.py`).
   The pinned `tests/fixtures/t07/cli-existing-commands.json` (and any other pinned digest) moves by that
   substitution only — prove it the way `d8941b8` did (reverse substitution reproduces the old digest).
   Registered StructuralReport fields stay as registered, as in `d8941b8`.

## Forbidden — stop and report instead

- **No PTC run on the PTC-R1 flowsheet from any start, and no Newton run from any registered start** — not
  before `C_case`, and **not after it either in this increment**: W5 (the 882 comparison runs) waits for the
  design-lane review and Frank's go-ahead. Unit tests at the roots and the §A5 off-grid states are allowed. Do
  not create any `benchmarks/t08/ptc_r1/results-*` file.
- No edit to the specs, ADRs, YAMLs, generators or `requirements.lock`; no schema, MCP tool or description change.
- Identity: K05 minus-`t07` `9a7b4e6d…`, T02 floats `9a8a5baf…`, structural `915c97e8…`, `t07` `11bcb148…`,
  keys `t02`…`t06`, whole document `3ed2911b…` — byte-equal (`measure_identity` in
  `scripts/t07_evidence_manifest.py`). Any moved byte beyond the named substitutions: stop.
- If the amendment is wrong or under-determined, stop and report with file:line.

## Working rules

Work in this checkout; nobody else edits it. Commit messages end with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`. Stage named paths only. Never set
`reviewed`. `.venv/bin/python`; quote the path (it has a space). Budget: the user is near a weekly usage limit —
targeted tests while developing, the full `PATH=.venv/bin:$PATH ./scripts/check.sh` once at the end.

## Report

Commits per item (mark `C_case`'s hash), gate results with numbers (B13–B15, B17, B18, B20, B26, B41, B42, B46,
A13), `check.sh` counts (expected: green), the digests that moved by substitution, isolated decisions, and any
question you stopped on.
