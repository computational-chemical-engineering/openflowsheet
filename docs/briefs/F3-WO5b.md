# F3-WO5b: the `Records` operations on four transports (ADR 0061 D13, roadmap 0.5)

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`,
head after this brief's commit (WO5a at 02889a00). Work only there. Do not spawn sub-agents yourself. Budget about
150k tokens of context: this order is large, so work in the commit order below; at the cap, commit what is complete,
write where you stopped (the next commit of the list) in `docs/F3_DECISIONS.md`, and end. A fresh engineer continues.

## Status

ADR 0061 is Proposed; Frank's acceptance card is pinned to its text at 5d085f05. **Do not edit
`docs/adr/0061-F3-component-data.md`.** Ambiguity: take the reading that changes no existing byte, record it as
`DECISION WO5b-<n>` in `docs/F3_DECISIONS.md` (choice, alternative, where it lives; proposed ADR text for the design
lane) and carry on. Stop an item (record it, carry on with the next) only where a choice would change an existing
operation's response, a frozen interface other than the one D13 adds, or F0. The legacy YAML files, the legacy loaders
and `thermo/` stay untouched.

## The pattern to follow

F1-WO4a added two `Inspection` operations on every transport (ADR 0060 D11, ADR 0019 Amendment 7): commits on `main`
`git log --oneline --grep F1-WO4a main` (catalogue ca6cde69, operations b53f34f6, pointer 1327cc41), its build log
`docs/F1_DECISIONS.md` (grep `W4a-`), the snapshot `SNAPSHOT_F1` in `tests/test_t07_w5e_application_results.py`, the
surface digest decomposition in `tests/test_t08_w2_surface_digest.py` and `tests/test_f1_operations.py`. Do the same
for the new protocol `Records` (ADR 0019 Amendment 8): a new protocol, not rows on an existing one.

## Read (narrowly, `sed -n` ranges)

ADR 0061: D8 (store, registrations), D9 (resolution), D11 (rights register, effective assessment, `reserved_namespace`,
the WO4-0 ruling row at the end), D12 (user-file adapter), D13 (the operation table and `assess_rights`' request
validation), D14, Exit tests E-F3-5 (its grant clause, skipped in WO4) and E-F3-11, "New catalogue codes", work-order
row 6, the "applied" sections. `docs/F3_DECISIONS.md`: every "Left for WO5", "Left for later work orders" (WO5 items)
and "Left for WO5b" paragraph, and WO3-6. Code: `src/openflowsheet/records/`, `src/openflowsheet/application/`
(`contract.py`, `operations.py`, `authz.py`, `local.py`), the CLI, HTTP and MCP modules F1-WO4a touched.

## Deliverables, in commit order

1. **Wiring.** `LocalApplication` (`create`, `open`, `in_memory`) holds the record stack: the project store
   (`RecordStore.in_memory()` for `in_memory()`), `LegacyStore(legacy.available_records)`, the project rights register
   (table `rights`, append-only, insertion sequence) over the repository register.
2. **Protocol `Records`** in `application/contract.py`, the five rows in `operations.py`, rights in `authz.py`
   (`search_records`, `get_record`, `validate_record`: `read`; `register_record`: `draft`; `assess_rights`: `policy`,
   not in the default agent grant), `application-results` `$defs` for `RecordPage`, `RecordView`,
   `RecordRegistrationResult`, `RecordValidationReport`, `RightsAssessmentResult`; request schemas as D13 states.
   Behaviour per D13 and the leftovers:
   - `register_record`: `{record}` or `{file: {format, content}, defaults?}` through
     `records.importers.user_file` with `retrieved_at` = now and `local_path`; idempotent by content; one audit row;
     the mapping of `RecordStoreError`; a record naming a `legacy.` source (in `sources`, or a user file's
     `defaults.source_id`) is `reserved_namespace(legacy)` unless its `record_sha256` is in the committed legacy index
     (then it is copied into the project store, D11 and the WO4-0 ruling row).
   - `search_records` and `get_record`: `effective_rights` (D11's precedence) per item; `resolve`'s `None` is
     `not_found`, or `data_unavailable` for a `sha256:` key (WO2); an unknown SHA is `not_found`.
   - `validate_record`: D7 plus `reactions.check_reactions` when `reactions` is given; the request schema screens the
     inputs WO5a-3 treats as a `ValueError` and `defaults`' shape, so no `ValueError` reaches a transport.
   - `assess_rights`: D13's request validation list exactly (one audit row per call; "latest" = insertion sequence).
3. **Transports.** CLI `openflowsheet records search|get|register|validate|rights`, HTTP routes as D13's table, MCP
   tools named after the operations with reviewed descriptions. Re-take the MCP served digest and add a surface link
   in the F1 form (the earlier digest must be recovered exactly with F3's additions removed); R4-G3 snapshots of
   existing operations unchanged (a `SNAPSHOT_F3` for the new ones).
4. **Descriptors (WO3-6).** The `legacy-yaml` and `user-file` descriptors' implementation sets (module
   `openflowsheet.records.importers.user_file` for the adapter). This moves `records.json`, `tables.sha256` and
   `registry_sha256`: record each old -> new value in the build log; if F0 fails because of it, stop this item and
   record it.
5. **Catalogue** entries for every new code these paths return (`reserved_namespace` is ADR 0060's; reuse it), the
   two `message_entry` fixtures' catalogue sha256 re-taken, `docs-site/messages/*.md` regenerated.
6. **Docs.** The ADR 0019 Amendment 8 pointer paragraph in the form of Amendment 7 (marked Proposed with ADR 0061),
   `docs/interfaces-frozen.md` rows, as F1-WO4a did.
7. **Tests** `tests/test_f3_operations.py`: E-F3-11 in full (each of the five returns identical canonical documents on
   python, CLI, HTTP and MCP; every new code has a catalogue entry); E-F3-5's grant clause unskipped
   (`assess_rights` forbidden for the default agent grant); `reserved_namespace(legacy)` on `register_record` both
   ways (an indexed legacy record is copied, a forged `legacy.` source is refused, including through a user file's
   `defaults`); D13's `assess_rights` list item by item. Expectations from the ADR, never from running the code.
8. The `## F3-WO5b` entry in `docs/F3_DECISIONS.md` (files, commits, DECISIONs, Moved, Left for WO7).

## Acceptance (run and quote)

1. The F3 test files pass (`tests/test_f3_*.py`); `scripts/records_legacy_index.py --check` clean; `ruff check`,
   `ruff format --check`, full `mypy`.
2. The battery: the 62 files in `/home/eajfpeters/Code/OpenFlowsheet/.git/codehealth/briefs/F3-battery.txt` plus the
   `tests/test_f3_*.py` files not already in it (do not list `test_f3_record_model.py` twice), plus the T07/T08
   surface, conformance and authz files you touched, once at the end on an unchanged tree (`PYTHONPATH=<worktree>/src`,
   repo `.venv`, no `-n`; do not commit while it runs; at 02889a00 WO5a reported 2192 passed, 0 failed, with `test_f3_record_model.py`'s 130 tests counted twice; quote
   your own count and the files' count).
3. `codehealth scan` on `records/` and `application/`: no brain function, every new file health >= 9.0;
   `codehealth arch` 0 violations, 0 cycles.
4. F0 `scripts/corpus_identity.py --check` PASS; `git diff 5d085f05 HEAD -- docs/adr` shows only the ADR 0019
   Amendment 8 paragraph.

Commits name `F3-WO5b`. No evidence manifest, never `reviewed`.

## Report (200 to 300 words)

Commits; acceptance results with counts; the DECISIONs; every digest, snapshot and SHA that moved (old -> new); what
is left for WO7 (close-out) or for a continuation of this order.
