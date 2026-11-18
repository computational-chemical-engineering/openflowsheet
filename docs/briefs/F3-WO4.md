# F3-WO4: data lock and rights (ADR 0061, roadmap 0.5)

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`,
head after this brief's commit (WO1 + fix1 at 8ca21576, WO2 at 1dfbfb5b, WO3 at 9e41f012). Work only there. Do not
spawn sub-agents yourself. Budget about 150k tokens of context: at the cap, commit what is complete, write where you
stopped in `docs/F3_DECISIONS.md`, and end.

## Status

ADR 0061 is Proposed; Frank's acceptance card is pinned to its text at 8ca21576. **Do not edit
`docs/adr/0061-F3-component-data.md`.** Ambiguity: take the reading that changes no existing byte, record it as
`DECISION WO4-<n>` in `docs/F3_DECISIONS.md` (choice, alternative, where it lives; proposed ADR text for the design
lane) and carry on. The legacy YAML files, the legacy loaders and `thermo/` stay untouched.

## First commit: the orchestrator's default for WO3-1 (DECISION, for the design-lane round)

WO3-1 (`docs/F3_DECISIONS.md`): D12 read literally gives each legacy component its own `rights.source` as citation,
99 distinct `source_sha256` over 7 sources, while D11 seeds one whole-source rights row per legacy source. Default
taken by the orchestrator: **one citation per legacy file**, fixed per profile in `legacy_profiles.yaml`; each
component's `rights.source` text goes to the `note` of its molar-mass entry (the reasoning of the W1 P1 review for
`rights.notes` applies). Implement it in `records/importers/legacy.py` and the profiles, regenerate
`records/legacy_index.json` with `scripts/records_legacy_index.py`, adapt the WO3 tests whose expectation is the
source count, and log it as `DECISION WO4-0` with the alternative (D12 literal, rights rows per component) and the
proposed D12 text. Then 7 legacy sources plus the two parameter-set sources give the seed rows (state the count).

## Read (narrowly, `sed -n` ranges)

ADR 0061: D10 (data lock, with W1 P2 ruling 1: per-method `data_sha256`, the replaced sentence and risk 8), D11
(rights register, Q9.R3, R-706, R-926; the four precedence rows; `assess_rights` and the agent grant), Exit tests
E-F3-5 and E-F3-7, "New catalogue codes", work-order row 4b, the "applied" sections. Orchestrator decision of
2026-11-05 on finding 19 (`docs/roadmap/decisions.md`, grep `Finding 19`): whole-source rights rows keyed by
`source_sha256`, `legacy.` reserved for the importer, "latest" = insertion order. `docs/F3_DECISIONS.md`: grep
`WO4`, `A32`, WO1-15 (A32 needs a v2 clause here), WO3-5. Code in `src/openflowsheet/records/`.

## Deliverables (WO4 only)

- `schemas/data-lock.schema.json` (mark "DRAFT until ADR 0061 is Accepted"); `records/lock.py`, `records/rights.py`;
  `records/rights-register.json` (seed rows).
- T08.A32's v2 clause (WO1-15 narrowed the skip to `record_format == "openflowsheet-record-v2"` under
  `tests/fixtures/records/`; with the rights register, state what A32 checks for v2 records).
- Catalogue entries for the codes these paths return (`data_unavailable`, `parameter_set_component_missing`, ...).
- Tests `tests/test_f3_lock_rights.py`: E-F3-5 and E-F3-7 in full, the committed fixture lock and
  `tests/fixtures/records/data-lock-sha256.txt`. Expectations from the ADR, never from running the code.
  `assess_rights` itself is an operation (WO5): test the register's rule here; the "forbidden for the default agent
  grant" case may be a skip with the reason "needs F3-WO5 operations" if the grant machinery is WO5's.

## Acceptance (run and quote)

1. The four F3 test files pass; `scripts/records_legacy_index.py --check` clean; `ruff check`, `ruff format
   --check`, full `mypy`.
2. The 62 files in
   `/tmp/claude-1000/-home-eajfpeters-Code-OpenFlowsheet/10ed1d55-8773-442e-9840-53568b103799/scratchpad/f3-tests.txt`
   plus the four F3 files, once at the end on an unchanged tree (`PYTHONPATH=<worktree>/src`, repo `.venv`, no `-n`;
   do not commit while it runs; at 9e41f012: 1985 passed, 0 failed).
3. `codehealth scan` on `records/`: no brain function, every new file health >= 9.0; `codehealth arch` 0 violations.
4. F0 `scripts/corpus_identity.py --check` PASS; `git diff 8ca21576 HEAD -- docs/adr` empty.

Commits name `F3-WO4`. No evidence manifest, never `reviewed`.

## Report (200 to 300 words)

Commits; acceptance results with counts; the DECISIONs (WO4-0 first); seed-row count; what moved; what is left for
WO5.
