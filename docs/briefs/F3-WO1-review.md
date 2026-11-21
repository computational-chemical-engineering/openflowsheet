# Review brief: F3-WO1 (record model), design lane

Independent `reviewer` pass over F3-WO1 before WO2 and WO3 build on it. Advice and rulings only: do not edit
production code or tests. Do not spawn sub-agents yourself. Write the review to `docs/reviews/F3-WO1-review.md` in
the worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3` (branch `wp/F3`) and commit that file alone.

## What to review

The diff `git diff a283925c..wp/F3` (main to the WO1 head; 35 files, about 4900 lines): `schemas/record-v2.schema.json`
and the core payload schemas, `src/openflowsheet/records/{__init__,model,normalize,identity,validate}.py`,
`src/openflowsheet/registry/builtin/records.json` and `tables.sha256`, `tests/test_f3_record_model.py` and
`tests/fixtures/records/`, the adapted F1 tests and re-taken fixtures. Build log: `docs/F3_DECISIONS.md` (WO1-1 to
WO1-15). Brief the engineer worked from: `docs/briefs/F3-WO1.md`.

Design authority: `docs/adr/0061-F3-component-data.md` (Proposed; Frank's acceptance requested): D1 to D7, D14,
Exit tests E-F3-3, -4, -13, "New catalogue codes", and the three "applied" sections at the end (W1 P1 review,
Amendment 3 = foundation rulings Q2.R9, W1 P2 ruling 1). Cite `docs/roadmap/foundation-rulings.md` Q2 and Q9 only
where D1 to D7 point at them.

## Questions, in priority order

1. **Identity.** Does the identity SHA implement D2 and Q9.A1/A3 exactly: the volatile closure, canonicalization
   (field order, `-0.0`, set-valued arrays, NFC, absent/null/empty equivalence, ordered solid formation forms), and
   the anchor kept out of or in identity as D6 and Amendment 3 say (`anchor_defaulted` not in identity; a defaulted
   `ig` and a stated `ig` give one SHA)? Any content with two SHAs, or two contents with one SHA, is a must-fix.
2. **Test independence.** Do E-F3-3, -4, -13 take their expectations from the ADR's rules rather than from the code
   (the D6 oracle in the 300-record generator in particular)? Does E-F3-3 truly exercise every non-volatile leaf?
3. **Rulings the engineer asked for:** WO1-11 (`record_type` payload `{payload_schema}`, `data_source` payload
   `{record_types, formats}`: the ADR freezes no field list) and WO1-15 (T08.A32's component-record scan skips
   mappings that carry `record_format`; does A32 need a v2 clause when WO4's rights register lands?). Rule on each:
   accept, or the change to make.
4. **Existing identity.** `registry_sha256` moved (E-F1-5 constant f251447d -> ee9e6b9d, 7 new descriptors);
   `tables.sha256` changed for core and legacy only because the descriptor schema's bytes changed (`core.json` and
   `legacy.json` byte-identical); four F1 tests adapted (payload schema now installed); two `message_entry` fixtures
   re-taken for the new catalogue SHA. Is every move expected by ADR 0060/0061, and is any frozen interface
   (`docs/interfaces-frozen.md`) changed beyond what ADR 0061 lists? F0 (`scripts/corpus_identity.py --check`) PASS,
   M1 to M9 equal; MCP digest and R4-G3 snapshots unmoved (engineer's report).
5. The other DECISIONs (WO1-1 to WO1-14) only where one contradicts the ADR.

## Output

The review file: verdict (merge-ready for the package / fix first), findings ranked must-fix, should-fix, note, each
with file:line, a concrete failure scenario and the fix; the two rulings. Your report back: 200 to 300 words, the
verdict, the must-fix list, the rulings.
