# F3 design-lane ruling round 1 (build decisions WO1 to WO4)

Design lane, `reviewer`, 2026-11-18. Brief `docs/briefs/F3-rulings-1.md`. Branch `wp/F3` at `db516cdf` (code at
`a4272c16`). Read: `docs/F3_DECISIONS.md` whole, ADR 0061 whole, `records/{rights,lock,resolve}.py`, the write and
registration paths of `store.py`, `stack.py`, the component, note and parameter-set mapping of `importers/legacy.py`,
`legacy_profiles.yaml`, `rights-register.json`, A32's v2 clause, the seven v1 files' `rights` blocks, R-880 and R-715.

**Verdict.** The 43 decisions are sound to build WO5 on after six code changes (B1 to B6), none of which reopens a
work order. Three rulings change what was built: the parameter sets' `sources` entry (two index SHAs move), the corrupt
object on a write, and A32's v2 scan. The rest are kept or confirmed. ADR 0061 is edited in the same commit as this
file (closing section "F3 ruling round 1 applied"); its Status stays Proposed.

## Facts checked (each decides a ruling)

- The import gives one `source_sha256` per source for the components (7) and a second one for each parameter set (9 in
  all), because the sets carry `{version}` without a citation. The register therefore holds two seed rows and two R-880
  rows for `legacy.s10`, against D11's "one whole-source row per legacy source" and "the row `legacy.s10`".
- Each templated profile citation was held against its file: every component's `rights.source` equals the profile's
  citation with the placeholder replaced by its own EOS text for `m01` (5), `s07` (123) and `s10` (3). In `l01` it does
  for 8 of 9: **O2 states "formation enthalpy: zero by definition"** where the citation says "ATcT 1.112". WO4-0's log
  entry and the profile file's comment ("the reference EOS of each fluid" is the only varying part) are wrong for that
  record. The component's own text is whole in its molar mass's note, so nothing is lost.
- R-880 (decision register, 2026-10-29, Frank for the ship decision) ships the whole `benchmarks/s10/records.yaml`,
  components and Wilson block. The register's `decided_by: Frank`, `2026-10-29` is backed.
- `s07`'s H2O states a condition in `rights.notes` that its `redistribution` text does not: attribution to the IAPWS
  (S05 spec §16.3). `rights.notes` is dropped (W1 P1), and the seed reads `redistribution` only, so the condition is in
  neither the v2 record nor the register. No other `rights.notes` text states a condition.
- A32's scan finds a mapping only when it has `elemental_verification`. A v2 `parameter_set` has none, so a tracked
  set with third-party values is never judged, in or out of the fixture directory.
- `StoreStack.adopt` reads the project store before it writes, so a corrupt project object refuses a lock copy at the
  read; only `register` reaches the write protocol with an existing target.

## Rulings

| Decision | Ruling | Change, and where it lands |
| --- | --- | --- |
| WO3-1, WO4-0 | **Keep** one citation per legacy file | A `sources` entry describes the source, and D11 keys a whole-source row on it; 99 entries under 7 ids would need a row per text for every decision on a source, and W1 P1 dropped `rights.notes` for the same reason. The per-component text stays in the record (the `s07` condition "cite the equation of state's source" needs it there). ADR D12 (sentence, new paragraph, table row). Code: B2. |
| WO3-5 | **Change** the set's `sources` entry; keep name = `data_set` | The set carries the file's entry, exactly as its components do: one `source_sha256` per legacy source. The `s10` citation names Kurihara 1993, which is the set's own source and which the set does not cite today. ADR D12, D11. Code: B1. |
| WO4-2 | **Change** | 7 seed rows, one R-880 row, one `s07` row for the IAPWS condition. The `--check` rule and the one-`redistribution`-text refusal are kept. ADR D11, D12 (`rights.notes` row). Code: B1, B5. |
| WO3-2 | **Keep** the drop, add one guard | The labels are not CAS numbers; widening D3 weakens the checksum for every record, a new scheme widens D3 and D9 for three strings, and stripping the suffix puts ortho-hydrogen in normal hydrogen's class. Id, name and the source file keep the distinction. ADR D12 (table row). Code: B3. |
| WO2-1 | **Change**: replace, and say so | A refused write leaves a record that no transport can restore (there is no delete operation), and the writer holds bytes that hash to the name. A silent repair would hide a `bug`-kind condition, so the call reports `store_object_repaired(<sha>)`. Reads and the failed Windows replace stay `store_object_corrupt`. ADR D8, E-F3-8, code table. Code: B4. |
| WO2-7 | **Keep** | The key list says why records are grouped and is order-free; a class index would mean nothing to the caller. ADR D9 now states it, for `search_records`' `resolution.classes` too. |
| WO4-3 | **Keep** | `source_sha256` contains the source id, so the key equals (source id, record). ADR D11: `source_id` in a row is descriptive. |
| WO4-7 | **Change** | Yes, the fixture directory is judged, by its own branch (its records cannot pass the three branches: the maximal fixture must be non-synthetic to carry identifiers, the segment fixture is refused by construction). And the scan must see every v2 record type. Code: B6. No ADR edit (A32 is T08's). |
| fix1-1, fix1-2, fix1-3, fix1-4 | **Confirm** | fix1-2 uses `selfhash.file_sha`, ADR 0060 D3's own file rule. No change. |
| WO2-2 | **Confirm** | It is D13's "a row only for a new volatile block" plus N1. ADR D8 now names the columns and the first-submission rule. |
| WO3-3 | **Keep** | ADR D12's index format now reads `findings: [{code, params}…]`. |
| The rest (WO2-3 to -6, -8, -9; WO3-4, -6, -7; WO4-1, -4, -5, -6; WO1-1 to -14 as reviewed in F3-WO1) | Stand as logged | No contradiction with ADR 0061, ADR 0060, ADR 0063 D2 or Q2, Q7, Q9 found. |

## Code changes for the build lane (in this order; each its own commit)

**B1. One `sources` entry per legacy source (WO3-5, WO4-2).** `legacy._parameter_set` builds the entry `_component`
builds (`version`, the profile's `citation`, `licence_stated` and `url` null). Regenerate the index and the seed rows.
*Acceptance:* the index diff against `a4272c16` changes exactly two `sha256` values (the sets of `s10` and
`s10-verification`) and no component's; `test_wo4_0…` counts one `source_sha256` per source id over components and
sets together, 7; the register has 7 seed rows and one R-880 row; `scripts/records_legacy_index.py --check` is clean;
every legacy record is `embeddable`.

**B2. Pin the profile citations to the files (WO4-0).** A test in `tests/test_f3_legacy.py` with each templated
profile's placeholder phrase: every component's `rights.source` equals the citation with the phrase replaced by that
component's own text, and the departures are exactly `{"l01": {"O2"}}`. Correct the comment in `legacy_profiles.yaml`.
*Acceptance:* passes at head; fails when one word of a profile citation outside the placeholder changes.

**B3. A dropped identifier must be one D3 refuses (WO3-2).** `legacy._identifiers`: the scheme is `cas` or `inchikey`
and the stated value fails `validate`'s reader, else `LegacyImportError`. *Acceptance:* a profile copy with
`dropped_identifiers: {H2: [cas]}` fails the import; the index is unchanged.

**B4. Repair on write (WO2-1).** `RecordStore._write_object` follows D8's new protocol, the in-memory branch too.
`register` returns `created=False` and adds `store_object_repaired(<sha>)` to the findings it returns, not to the
`registrations` row. Catalogue entry (notice) in `messages/catalogue/records.yaml`. *Acceptance:* in
`test_e_f3_8_a_flipped_byte…`, after the flip the three reads refuse; `register` returns `created is False` with the
notice; then the reads succeed and the file hashes to its name; `registrations(sha)` is the one original row with its
findings unchanged; a further `register` returns no notice. The Windows corrupt-target test and `adopt` on a corrupt
project object stay `store_object_corrupt`.

**B5. The `s07` condition row (WO4-2).** Append to `rights-register.json`, after the R-880 row: `source_id`
`legacy.s07`, the seed's `source_sha256`, `record_sha256` null, `permitted`, conditions "cite CoolProp with its MIT
notice and the equation of state's source (R-715); for the H2O record: attribution to the International Association
for the Properties of Water and Steam (S05 spec §16.3)", basis "benchmarks/s07/components.yaml: v1 rights.notes of
H2O; docs/reviews/F3-rulings-1.md", `decided_by` "design lane (reviewer), F3 ruling round 1", date 2026-11-18.
*Acceptance:* `effective` for an `s07` record returns this row; the register test pins it; `--check` is clean.

**B6. A32's v2 clause (WO4-7).** In `tests/test_t08_w2_inventory.py`: (a) the v2 scan takes every mapping with
`record_format: openflowsheet-record-v2` in a tracked YAML or JSON file, whatever its `record_type`; (b) outside
`tests/fixtures/records/` the three branches as built; (c) inside it, `sources` is a non-empty object whose every key
begins `fixture.`, with no `identify`. *Acceptance:* `_a32_v2_problems` gives a line for the imported `s10` parameter
set at `benchmarks/x/sets.json` with an empty register and none with the packaged one; a line for a record at
`tests/fixtures/records/x.json` whose source is `legacy.s07`; none for the three committed fixtures; the tree passes.

**B7. Record the round** in `docs/F3_DECISIONS.md` (append): the commits, the two moved index SHAs, the re-taken
catalogue SHA, the register's nine rows, and the O2 correction to WO4-0's entry.

## Carried into F3-WO5 (acceptance added to its brief)

- **`reserved_namespace(legacy)` by index membership (ADR D11, edited).** Under WO4-0 a legacy `sources` entry is one
  public constant per file, so this refusal is all that stands between a user record and a `permitted` seed row.
  `register_record` and `validate_record`, the user-file adapter included: a record naming a `legacy.` source id is
  refused unless its `record_sha256` is in the committed legacy index. *Acceptance:* the imported `m01` H2 record
  submitted as content registers with its indexed SHA; the same record with one value moved by one ulp is refused
  `reserved_namespace(legacy)`.
- `store_object_repaired` reaches `RecordRegistrationResult.results[].findings` and the audit row.

## Notes (not ruled; no change asked)

- **D5 matching is an existence check.** `lock._matched` does not refuse a set key that matches two bound components
  (two ids bound to one record, or two bound records of one InChIKey), and no key to component map is defined. ADR-F4
  needs that map for the Wilson provider; it should state the rule.
- **WO4-4's uncoded refusals.** A component bound to a parameter set's SHA is a user's mistake, not a caller's bug.
  ADR-F2's validator must refuse it with its own code before `build_lock` is called.
- **A32's vetted-file branch** trusts a self-declared `legacy.file_sha256`. Membership of the record's SHA in the
  legacy index would be exact. Not required now.
- **WO4-5.** Two locked sets sharing an id are indistinguishable in `parameter_set_component_missing`. Stands.

## Not examined

`normalize.py` and `validate.py` (the F3-WO1 review covered them), `legacy_views.py`, the data-lock schema, the
catalogue entries, the concurrency and Windows store tests, the fixture lock. No test was run; the importer was run
once to read the imported records.

## For Frank

No question blocks. For information: B5's row adds no assessment, it carries a condition the v1 file already states;
and the acceptance card needs its one re-pin to the ADR at this commit.
