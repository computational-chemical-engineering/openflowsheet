# F3-WO3: legacy import (ADR 0061, roadmap 0.5)

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`,
head after this brief's commit (WO1 + fix round 1 at 8ca21576, WO2 at 1dfbfb5b). Work only there. Do not spawn
sub-agents yourself. Budget about 150k tokens of context: at the cap, commit what is complete, write where you
stopped in `docs/F3_DECISIONS.md`, and end.

## Status

ADR 0061 is Proposed; Frank's acceptance card is pinned to its text at 8ca21576. **Do not edit
`docs/adr/0061-F3-component-data.md`.** Ambiguity: take the reading that changes no existing byte, record it as
`DECISION WO3-<n>` in `docs/F3_DECISIONS.md` (choice, alternative, where it lives; proposed ADR text for the design
lane if any; one revertible commit) and carry on. Stop and report if a choice would change an existing artifact's
identity.

**The seven legacy YAML files and the legacy loaders are read, never edited** (ADR 0061 "Does not amend"; F0's M9
set). `pr_c1.load_records()`, `pr_lib.load_records()`, `wilson_ig.load_records(path)` and
`selectable_bases()` stay byte-for-byte as they are.

## Read (narrowly, `sed -n` ranges)

ADR 0061: Context (the seven files and the three loaders), D6 (legacy anchors, Amendment 3: 127 records anchor `ig`),
D12 (importers, the provenance table as the W1 P1 review confirmed it with four identity-bearing changes), Exit tests
E-F3-1, -2, -6, -13 (legacy part), the work-order row 4a, "Risks and open questions", the "applied" sections.
`docs/reviews/W1-P1-review.md` ruling 1 (the D12 table). Build log `docs/F3_DECISIONS.md`: grep `WO3`, N9 and the
WO2 decisions on the legacy store (WO2-9: an in-memory store filled once from a loader). WO1/WO2 code in
`src/openflowsheet/records/`. New-code rules: `.codehealth/playbook.md`.

## Deliverables (WO3 only)

- `src/openflowsheet/records/importers/legacy.py`, `records/legacy_profiles.yaml`, `records/legacy_index.json`
  (committed; generated), `records/legacy_views.py` (`c1_records`, `library_records`, `wilson_records` views over
  imported records), `scripts/records_legacy_index.py` with `--check` (the generator pattern of
  `scripts/registry_builtin.py`).
- The catalogue entry for `legacy_record_drift` and any other code these paths return.
- Tests `tests/test_f3_legacy.py`: E-F3-1 (field by field, floats by `struct.pack("<d")` bytes, including `sha256`,
  domains and Wilson Λ), E-F3-2 (all 147 molar masses bitwise, file order), E-F3-6 (the committed index of 149 SHAs
  reproduced; one-ulp change in a temporary copy changes exactly that file's record SHAs; an unprofiled v1 file fails
  `--check`), E-F3-13 legacy part (anchors as D12 states). Unskip WO2's methanol test (E-F3-9 source-checkout part).
  Expectations come from the legacy files and loaders, never from the importer's output.
- N9 (cache the `if` validator before the bulk import) if it belongs here.

## Acceptance (run and quote)

1. `tests/test_f3_legacy.py`, `test_f3_store.py`, `test_f3_record_model.py` pass (methanol case no longer skipped);
   `scripts/records_legacy_index.py --check` clean; `ruff check`, `ruff format --check`, full `mypy`.
2. The 62 test files in
   `/tmp/claude-1000/-home-eajfpeters-Code-OpenFlowsheet/10ed1d55-8773-442e-9840-53568b103799/scratchpad/f3-tests.txt`
   plus the three F3 files, once at the end on an unchanged tree (`PYTHONPATH=<worktree>/src`, repo `.venv`, no
   `-n`; do not commit while it runs; at 1dfbfb5b: 1949 passed, 0 failed).
3. `codehealth scan` on `records/`: no brain function, every new file health >= 9.0.
4. F0 `scripts/corpus_identity.py --check` PASS; `git diff 8ca21576 HEAD -- docs/adr` empty.

Commits name `F3-WO3`. Do not write an evidence manifest, never set `reviewed`.

## Report (200 to 300 words)

Commits; acceptance results with counts; the DECISIONs; the index SHA count and anything that moved a registry or
catalogue SHA; what is left for WO4 and WO5.
