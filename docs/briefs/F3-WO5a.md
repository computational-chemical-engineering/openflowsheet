# F3-WO5a: reaction consistency and the user-file importer (ADR 0061, roadmap 0.5)

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`,
head after this brief's commit (WO1 to WO4 and ruling round 1 B1-B7 at 270b6534). Work only there. Do not spawn
sub-agents yourself. Budget about 150k tokens of context: at the cap, commit what is complete, write where you stopped
in `docs/F3_DECISIONS.md`, and end.

## Status

ADR 0061 is Proposed; Frank's acceptance card is pinned to its text at 5d085f05. **Do not edit
`docs/adr/0061-F3-component-data.md`.** Ambiguity: take the reading that changes no existing byte, record it as
`DECISION WO5a-<n>` in `docs/F3_DECISIONS.md` (choice, alternative, where it lives; proposed ADR text for the design
lane) and carry on. The legacy YAML files, the legacy loaders and `thermo/` stay untouched. WO5 is split: this order
(WO5a) builds the two library modules; WO5b builds the five operations on four transports, `assess_rights`, the
`LocalApplication` wiring, the `legacy-yaml` and `user-file` descriptors' implementation sets (WO3-6) and the
`reserved_namespace(legacy)` refusal. Do none of WO5b's items here.

## Read (narrowly, `sed -n` ranges)

ADR 0061: D7 (validation, the "Reaction consistency (Q7.A3)" paragraph and the one after it), D12 (the "User-file
adapter" paragraph, the mapping table, "The profile's citation"), D13 (only to see what `register_record` will pass
in), Exit tests E-F3-10 and E-F3-12, "New catalogue codes", the work-order row 6, the "applied" sections at the end.
`docs/F3_DECISIONS.md`: grep `WO1-14`, `WO3-6`, `Left for`, `user-file`. Code: `src/openflowsheet/records/`
(`importers/legacy.py` holds D12's mapping; `validate.py`, `model.py`, `identity.py`); the catalogue
`src/openflowsheet/messages/catalogue/records.yaml`.

## Deliverables (WO5a only)

1. `src/openflowsheet/records/reactions.py`: D7's Q7.A3 check. Input reactions `{id, stoichiometry: {component key:
   ν}}` and a component-key -> record map; every number converted exactly to `Fraction`; element balance, charge
   balance (refusals `reaction_element_imbalance(<reaction>, <element>)`, `reaction_charge_imbalance(<reaction>)`),
   `reaction_element_unchecked(<reaction>, <component>)` for `elements: null`, and the notice
   `molar_mass_inconsistent(<reaction>)` by the exact inequality |Σ ν M| ≤ 4ε Σ |ν M|, ε = 2⁻⁵². A public function F2's
   validator can call; returns coded findings in the form `validate.py` already uses. This is numerics-adjacent: a
   design-lane review reads it before merge, so keep it small and state the arithmetic in the docstring.
2. `src/openflowsheet/records/importers/user_file.py`: the `user-file` 1.0.0 adapter as a library function (no
   operation): formats `record-v2-json`, `record-v2-yaml` (one record or a list), `component-record-v1-yaml`. A v1 file
   reuses D12's legacy mapping where a parameter name is in it (share `legacy.py`'s mapping functions; the legacy index
   must not move: `scripts/records_legacy_index.py --check` clean), else `user.<name>` constant entries; provenance from
   `defaults {origin, derivation, source_id, source_version, citation}`, required for a v1 file (else
   `provenance_invalid` per entry); `volatile = {retrieved_at, local_path (if given), adapter_version}` with
   `retrieved_at` passed in by the caller (so tests are deterministic). Output the records and their findings, ready
   for `register_record` (WO5b) to validate and store.
3. Catalogue entries for every code these paths return that has none yet (the four reaction codes; check
   `provenance_invalid` is already there). `molar_mass_inconsistent` is a notice with an explicit override of MSG's
   `*_inconsistent` -> bug rule, `review: false` (code table). Re-take the catalogue sha256 in the two `message_entry`
   fixtures and regenerate `docs-site/messages/*.md` (`scripts/doc_pages.py`), as WO4 and B4 did.
4. Tests `tests/test_f3_reactions.py` (E-F3-10 in full, including the 10³ generated balanced reactions over `m01`,
   `l01` and `s10` records and the (1 + 1e-9) scaling; mark it as the ADR's `[gen]` tests are marked elsewhere in the
   F3 files) and `tests/test_f3_user_file.py` (E-F3-12 at the library level: v2 round-trip to the same SHA; `m01`'s
   YAML copy with `defaults` gives entries equal to the legacy import's except provenance and `sources`; without
   `defaults` every entry `provenance_invalid`). Expectations from the ADR, never from running the code; the measured
   ratios in E-F3-10 (6.4e-18, 3.6e-17, 7.8e-6) are assertions to check, not values to copy from output. If a measured
   ratio departs from the ADR's, stop that item, record it as a DECISION with the number and leave the test failing
   rather than relaxing it.

## Acceptance (run and quote)

1. The six F3 test files pass; `scripts/records_legacy_index.py --check` clean; `ruff check`, `ruff format --check`,
   full `mypy`.
2. The battery: the 62 files in `/home/eajfpeters/Code/OpenFlowsheet/.git/codehealth/briefs/F3-battery.txt` plus
   `tests/test_f3_*.py`, once at the end on an unchanged tree (`PYTHONPATH=<worktree>/src`, repo `.venv`, no `-n`; do
   not commit while it runs; at 270b6534: 2010 passed, 0 failed).
3. `codehealth scan` on `records/`: no brain function, every new file health >= 9.0; `codehealth arch` 0 violations.
4. F0 `scripts/corpus_identity.py --check` PASS; `git diff 5d085f05 HEAD -- docs/adr` empty.

Commits name `F3-WO5a`. No evidence manifest, never `reviewed`. Append an `## F3-WO5a` entry to `docs/F3_DECISIONS.md`
in the form of the WO3 and WO4 entries (files, commits, DECISIONs, Moved, Left for WO5b).

## Report (200 to 300 words)

Commits; acceptance results with counts; the DECISIONs; the measured E-F3-10 ratios; what moved; what is left for WO5b.
