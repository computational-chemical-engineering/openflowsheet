# F3-WO1: record model (ADR 0061, roadmap 0.5)

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`,
base `main` a283925c. Work only there. Do not spawn sub-agents yourself. Budget about 150k tokens of context: at the
cap, commit what is complete, write where you stopped in `docs/F3_DECISIONS.md`, and end.

## Status of the design

ADR 0061 (`docs/adr/0061-F3-component-data.md`) is **Proposed**: reviewed (`docs/reviews/W1-P1-review.md`, accept
after fixes), fixes applied, plus Amendment 3 (Q2.R9) and W1 P2 review ruling 1 (see the ADR's last three sections).
Frank's acceptance is requested; 0.5 itself is authorized (Decision Desk ofs-s19-start-05). You build on the Proposed
text, as F1 did on ADR 0060: mark the new schema's `description` "DRAFT until ADR 0061 is Accepted". Nothing merges
into `main` before acceptance. You do not re-rule the ADR: where it is ambiguous on a scientific or identity point,
take the reading that changes no existing byte, record it as `DECISION` in `docs/F3_DECISIONS.md` (choice,
alternative, where it lives; one revertible commit), and carry on. Stop only if a choice would change an existing
artifact's identity (see "Identity" below).

## Read (narrowly, `sed -n` ranges)

ADR 0061: Context, D1 to D7, D14, "Alternatives rejected", "Exit tests" (E-F3-3, -4, -13), "New catalogue codes",
the work-order table (row 2b), "Risks and open questions", and the three "applied" sections at the end. Only what D1
to D7 cite from `docs/roadmap/foundation-rulings.md` (Q2, Q9). The F1 precedent for layout and the built-in tables:
`src/openflowsheet/registry/discovery.py` (built-in tables, `tables.sha256` and its generator `--check`),
`docs/F1_DECISIONS.md` (grep it). Canonical JSON: ADR 0002 D3 and its implementation (grep `canonical` in
`src/openflowsheet`). New-code rules: `.codehealth/playbook.md`.

## Deliverables (WO1 only)

- `schemas/record-v2.schema.json` (draft 2020-12, closed objects, D1 to D5). The v1
  `schemas/component-record.schema.json` stays byte-identical.
- `src/openflowsheet/records/{__init__,model,normalize,identity,validate}.py`: the v2 record model, normalization
  and canonicalization (D2, Q9.A3), the identity SHA with the volatile closure (Q9.A1), anchor derivation (D6 with
  Amendment 3: `mol` with nothing phase-tagged -> `ig` + notice `anchor_defaulted`, not in identity; `kg` -> null +
  `anchor_undetermined` and registration refused `amount_basis_unsupported(kg)`), validation (D7).
- `registry/builtin/records.json` (record types, the two forms, the two data sources), with `tables.sha256` and its
  generator updated the way F1 does it.
- New catalogue codes that WO1's paths can return, with catalogue entries (the table "New catalogue codes").
- Tests `tests/test_f3_record_model.py` (and fixtures under `tests/fixtures/records/`): E-F3-3 [gen] over every
  schema leaf of a maximal fixture record, E-F3-4, E-F3-13 synthetic part. Expectations come from the ADR's rules,
  never from running the code.

## Identity

No existing artifact may change identity. Adding a built-in table may change `registry_sha256` (it appears in
`list_capabilities` and `check_admission` results): find every test, snapshot and digest it reaches, and report
which moved and why. Run `scripts/corpus_identity.py --check` (F0) at the end: if it is not PASS, stop and report;
do not re-take anything F0 covers. MCP digest and R4-G3 snapshots: report, do not re-take.

## Acceptance (run and quote)

1. The three exit tests pass; `ruff check`, `ruff format --check`, full `mypy` (repo `.venv`, no arguments).
2. The F1 registry tests and every test touching `registry/` or the catalogue pass
   (`PYTHONPATH=<worktree>/src`, repo `.venv`; no `-n`).
3. `codehealth scan` (`/home/eajfpeters/Code/OpenFlowsheet/.venv-codehealth/bin/codehealth scan --json <scratch>.json`)
   on the new files: no brain function, every new file health >= 9.0.
4. F0 `scripts/corpus_identity.py --check` PASS.

Commit per coherent piece, messages naming `F3-WO1`. Build log `docs/F3_DECISIONS.md` (append-only, in the form of
`docs/F1_DECISIONS.md`). Do not write an evidence manifest (close-out does), never set `reviewed`.

## Report (200 to 300 words)

Commits; what each acceptance item gave (counts, PASS/FAIL); the DECISIONs taken; what moved with `registry_sha256`;
what is left for WO2.
