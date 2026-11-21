# F3-WO1 review (record model), design lane

Reviewer pass over `git diff a283925c..wp/F3` (head 44bc850f) against ADR 0061 (Proposed) D1 to D7, D14, the exit
tests E-F3-3, -4, -13 and the three "applied" sections. Advice and rulings only. Brief: `docs/briefs/F3-WO1-review.md`.

**Verdict: fix first.** The canonical-JSON core, the volatile closure, NFC, signed zero, set sorting and the
defaulted-`ig` rule are implemented as D2 and Amendment 3 state, and the tests draw their expectations from the ADR.
Four defects let a record obtain a SHA that it should not have, or lose one it has. All four are small, and all four
are cheaper to repair now than after WO2 (store) and WO3 (149 pinned SHAs) build on them.

Evidence: each must-fix was confirmed with a falsifier script on the WO1 head (repo `.venv`, `PYTHONPATH=src`); the
quoted SHA prefixes are from those runs. No test suite was re-run (orchestrator: 1882 passed, 0 failed).

## Must fix

**M1. A derived anchor is exempt from the stated-anchor rule, so a registered record's own normal form is refused.**
`records/normalize.py:67-70`, `records/validate.py:126-127, 236-246`. Component with `charge: 1`, `formation` in `ig`
only, no `anchor_phase`: `identify` derives `aq` (D6 step 1), no error, SHA `ceeef0cce0…`. `identify` on that outcome's
`record` (anchor now stated `aq`) gives `anchor_phase_invalid(M, aq)` and no SHA. A stored object then fails
`validate_record`, and an export followed by an import (E-F3-12) is refused. Amendment 3's principle (a stated and a
derived anchor are one record) means validity must be a function of the normalised record. Fix: apply `_anchor_errors`
to every non-null anchor and drop `anchor_derived` (steps 2 to 5 satisfy the rule by construction; only step 1 can
fail). D6's sentence becomes "The anchor, stated or derived, must be ...". A charged component with formation data and
none in `aq` is then refused at first submission. Add the property test: for every accepted record,
`identify(outcome.record)` has no error and the same SHA.

**M2. Every closed pattern admits a trailing newline, so a non-token is hashed and D6 misreads it.**
`schemas/record-v2.schema.json` (11 patterns ending in `$`; Python `re` lets `$` match before a final `\n`) and
`records/validate.py:44-47` (`.match` with `$`). Accepted with a SHA: `id: "M\n"` (`331daff8de…`), a source id
`"s\n"`, InChIKey and CAS with `\n`. Worst case: `formation: [{phase: "l\n", ...}]` is accepted, `is_phase` does not
know the token, and the record is anchored `ig` with `anchor_defaulted` (`bc00da3611…`) although it carries liquid
formation data. A YAML block scalar (`phase: |`) produces exactly this. Fix: an end anchor that cannot match before a
newline (`$(?!\n)` is valid in ECMA 262 and in Python), and `fullmatch` for the three regexes in `validate.py`. Test:
for every schema leaf with a `pattern`, the fixture value plus `"\n"` is refused. The descriptor schema has the same
exposure (outside WO1; a code-health item).

**M3. Step 2a removes map entries and undescribed members, so malformed content is accepted under another content's
SHA.** `records/normalize.py:119-136, 154-167` (`members.get(key, other)` with every non-required key removable).
`elements: {H: null, O: 1}` is accepted as `{O: 1}` (`df8663563c…`); `validity: {T: []}` is accepted as no validity;
`colour: null` and `sources: {..., ghost: null}` give the base SHA `d7b5af5c2d…`. Decision WO1-4 says such a member
"is refused at step 6 anyway"; it is not, because step 6 never sees it. This contradicts D2's "never silently
dropped". **Ruling (design lane):** "optional member" in step 2a means a member the schema names in `properties` and
does not list as `required`. Entries of a map (`additionalProperties`) and members the schema does not describe stay
in place for step 6. Fix: keep `key` when `key not in members`. ADR D2 step 2a gets that one clause.

**M4. `legacy.file_fields` is required and nullable, so one content has two SHAs.**
`schemas/record-v2.schema.json:164-165` (WO1-3). `file_fields: null` gives `ac16b0a881…`, `file_fields: {}` gives
`20f69dfb12…`. It is the only required member with two empty spellings (checked over every `required` list). D1 does
not make it required. Fix: remove `file_fields` (and `position`, for symmetry) from `$defs/legacy/required`, before WO3
pins the legacy index.

## Should fix

**S1. Inner sets are normalised after the outer sets are deduplicated.** `records/normalize.py:262-267`. Two entries
with one key that differ only in the order of `provenance.origin` are canonically identical after step 4, yet the
record is refused `record_schema_invalid(/entries/1)`; the single-entry record has SHA `5ce1bf228f…`. No SHA is wrong
(a tie in the key is always refused or removed), but the ADR's "only canonically identical elements are removed" is
not met. Fix: run the `quantities` loop (provenance sets) before the `_SET_KEYS` loop.

**S2. YAML drops a repeated key silently; JSON refuses it.** `records/normalize.py:102-106`. A YAML record with
`name:` twice is accepted with the last value (`fa1339648b…`). JSON text behind a BOM does not start with `{`, takes
the YAML path, and its repeated key is accepted too (`192c410ffe…`). Fix: a `SafeLoader` subclass that refuses a
repeated mapping key, and strip a leading BOM before the `{` test.

**S3. Step 1 raises on three inputs instead of refusing.** `records/normalize.py:86-99`. Bytes that are not UTF-8
raise `UnicodeDecodeError` (the decode is outside the `try`); a recursive YAML alias (`a: &x [*x]`) and deeply nested
JSON raise `RecursionError`. D2 step 1 gives `record_schema_invalid`. WO5 puts this path behind `register_record` on
four transports. Fix: decode inside the `try`, catch `RecursionError` around parse and `first_noncanonical`.

**S4 (needs a decision; my ruling below). WO1-10 makes the step 3 anchor depend on property ids.**
`records/normalize.py:370-375`. Entries tagged `s:alpha` and `s:beta` anchor `s:alpha` (`4451c5f06c…`); adding one
more entry on `s:beta` with property `user.aa` re-anchors to `s:beta` (`2ce819954d…`), although the set of tagged
phases did not change. D6 step 3 says "record order", which a set does not have (E-F3-4), so the ADR needs a sentence
either way. **Ruling:** among `s:` forms, step 3 takes the form whose token has the smallest canonical-JSON bytes, so
the anchor is a function of the set of tagged phases. Formation keeps record order (step 2). No legacy record is
expected to reach this branch; settle it before user records are registered.

**S5. Test gaps (question 2).**
- `tests/test_f3_record_model.py:403-420, 479`: the oracle transcribes D6 independently for steps 1, 2, 4 and 5. For
  step 3 the entries are named `user.p0`, `user.p1`, ... in list order, so record order and sorted order coincide: the
  300 records cannot tell WO1-10 from a record-order implementation that would break E-F3-4. The generator asserts
  anchors and notices, never errors, so M1 is invisible to it. Add shuffled property names, and a test that permuting
  entries leaves the SHA when the anchor comes from step 3.
- `:242-250`: E-F3-4 says "every set-valued array"; `transitions` is not permuted (the fixture has one). A probe shows
  the code is right; the test does not pin it.
- `:286`: the 2a list is 13 hand-picked members. Derive it from the schema with the test's own walker, as E-F3-3 does,
  and add "no required member admits `null`, `[]` or `{}` in two spellings" (it would have caught M4).
- No test closes the keyword set that `normalize._applicable` interprets (`$ref`, `allOf`, `if`, `anyOf`, `oneOf`,
  `properties`, `additionalProperties`, `prefixItems`, `items`, `required`). A later `patternProperties` or
  `dependentRequired` would change what 2a strips, and so SHAs, with no failing test. Add a whitelist test.
- E-F3-3 itself is sound: the leaf set comes from the test's own schema walker, the coverage assertion closes it, and
  every reached leaf is mutated. Limits to state in the docstring: leaves are values, not map keys; patterns merge
  across record types; the SHA is `normalize` plus `record_sha256`, since two fixtures are refused by design.

**S6. `docs/interfaces-frozen.md` §2 has no F3 paragraph** (F1 wrote its own while Proposed, line 106). It must state:
`record-v2.schema.json` added (draft); `extension-descriptor.schema.json` widened by three `$defs` under ADR 0060
erratum F-5 (ADR 0061's own "Amends" list does not name this file); `schemas/registry.json` plus one name.

**S7. The component fixture carries real water constants under an invented citation and licence.**
`tests/fixtures/records/component-maximal.json`: `synthetic: false`, CAS 7732-18-5, 647.096 K, −285830 J/mol, 69.95
J/(mol K), "Fixture handbook of water data", `CC-BY-4.0`. With WO1-15 it is the first tracked non-synthetic record
that A32 does not judge. Replace the numbers by plainly fictitious ones (the identifiers may stay; the tests need
their checksums, not the data).

**S8. `parameter_set.components[].match.inchikey` has no pattern** (`$defs/set_component`): `{inchikey: "x"}` is
accepted. Give it D3's InChIKey pattern.

## Notes

- N1 (WO2). `anchor_defaulted` belongs to a submission, not to a record: the stated and the defaulted `ig` share a SHA,
  and re-validating a stored object never yields the notice. The store must keep findings from registration and say
  which submission wins when both forms are registered.
- N2. `record_sha256` is exported and hashes any mapping, normalised or not; `RecordOutcome.record` is a mutable
  `dict` in a frozen dataclass. WO2 should hash and write the same bytes in one place.
- N3. An extension `record_type` can be registered, but its records cannot carry a payload: the root's
  `unevaluatedProperties` refuses every member with `record_schema_invalid("")`, and `payload_schema` is never read.
  State it (a `not_supported` refusal is clearer), and note that step 2a will need the extension's schema.
- N4. `volatile: {mirror_url: null}` is refused while `null` is tolerated elsewhere. Harmless to identity.
- N5 (WO3, X11). WO1-8's formula reader refuses `Na+`, `Ca(OH)2` and `D2O` as `formula_elements_invalid`. Ions are in
  D3's scope (`charge`, `aq`); rule on a charge suffix before a fetcher meets one.
- N6 (D10). An entry names a form id without a version, and `_forms` takes the highest registered one. The data lock
  must pin the form descriptor, or a form 2.0.0 re-reads old coefficients.
- N7 (E-F3-12 docs). YAML 1.1 scalars: `1e5` is a string (refused), `010` is 8, `1:30` is 90.
- N8. WO1-9 pointers address the normalised record, whose entry order is not the submitter's.
- N9. `Draft202012Validator(schema["if"])` is built per node in `_applicable`. Fine for 149 records; cache it by
  schema identity before a bulk importer.
- N10. WO1-1 (flat layout) agrees with the ADR's wording. Consequence to record in D1: envelope member names are
  reserved against every payload, now and for later envelope members.
- N11. `registry_sha256` will move again with the WO1-11 ruling below, and at WO3 and WO5 when the data sources gain
  modules. Batch the re-takes.

## Rulings

**WO1-11: accept, with three changes.**
1. `record_type.payload_schema` gains a required `sha256` (the schema file's LF-normalised bytes, D4's file rule),
   written by `scripts/registry_builtin.py`, checked by `--check` and at registration (`extension_invalid` on a
   mismatch). Today the built-ins have empty `modules`, so `self_sha256` is `sha256("[]")` and the descriptor holds
   only a pointer: an edit of `$defs/component` changes what step 2a strips, hence record SHAs, without moving
   `descriptor_sha256` or `registry_sha256`. ADR 0060 D9 states that for a `record_type` "the descriptor hash is the
   whole content"; the hash makes that true.
2. `payload_schema: null` is for a preview type only. A non-built-in `record_type` with `null` is `preview`, not
   `core` (`tests/test_f1_registry_core.py` `CORE_PAYLOADS` registers one as `core` today).
3. `data_source` = `{record_types, formats}` is accepted as the core envelope; give `formats` `minItems: 1`. X11 adds
   optional members only. `correlation_form` is D4's payload as written: accepted.
On acceptance ADR 0061 gets a three-row payload table (D1, D4, D12) as the frozen field list.

**WO1-15: accept the skip, narrowed; and yes, A32 needs a v2 clause with WO4.**
`tests/test_t08_w2_inventory.py:575-579` skips any mapping that has a `record_format` key, whatever its value and
wherever the file is, so a v1 record with a stray key, or real data committed as v2 anywhere, escapes A32 from now
until WO4. Change: skip only `record_format == "openflowsheet-record-v2"`, and assert that every such mapping is in
`tests/fixtures/records/`. The clause WO4 adds: every tracked v2 record outside that directory passes `identify`, and
is `synthetic: true`, or carries a `legacy.file_sha256` equal to a vetted v1 file's hash, or has each of its
`sources` covered by a permitting rights-register row.

## Questions 1, 4 and 5 in one line each

1. Identity: D2 steps 2 to 5 and 7, Q9.A1 and A3 and Amendment 3 hold except M1 to M4 (S1, S4 are normal-form defects
   without a wrong SHA).
4. Existing identity: every move is expected. `tables.sha256` is the generator's check digest and includes the
   descriptor schema's bytes; `registry_sha256` moves by the seven descriptors (D10's formula; `core.json` and
   `legacy.json` are untouched, and `stability` is not hashed); extensions of the three kinds become `core` as erratum
   F-5 says. No stale copy of the old hashes outside history (`docs/reviews/F1-design-followup.md`, the F1 evidence
   manifest). The v1 record schema and `application-results` are untouched. The one frozen file changed beyond ADR
   0061's list is `extension-descriptor.schema.json`, covered by ADR 0060 F-5 (S6).
5. Other DECISIONs: WO1-3 (M4), WO1-4 (M3) and WO1-10 (S4) need the changes above; the rest stand.

## Not examined

F0, the MCP digest and the R4-G3 snapshots (engineer's report, not re-run); the regenerated `docs-site` pages;
`component-segment.json` beyond its reach of the schema leaves; ruff, mypy and codehealth results; D12's legacy
mapping (WO3).
