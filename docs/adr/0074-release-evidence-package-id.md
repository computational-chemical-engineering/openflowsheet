# ADR 0074 — The release evidence package id: `REL` and a length-marked version code, admitted by one additive `work_package` alternative

**Status:** **Accepted, 2026-11-08** — its condition holds: D1 was applied alone in `51c9e7f5` (with RID.A01–A11 in
`tests/test_evidence_manifests.py`), and that file passes (488 passed) with every committed manifest unchanged. Marked by
the build lane (package S15a). A-9 is pasted as RP §17.2 and the register entry is R-970. (Proposed 2026-11-08, design
lane.)

Condition as proposed:
- It becomes **Accepted** when the build lane has applied D1 alone, in one isolated commit together with the acceptance
  test RID.A01–RID.A12 (§6), and has recorded that `tests/test_evidence_manifests.py` passes with every committed
  manifest unchanged. The build lane marks it, as for ADR 0059. No answer of Frank's is needed: O-1 and O-2 (§8) are
  defaults that cost nothing to revisit until a version component first reaches 10.
- It is due before 0.4.0's K3 (RP review K-1). 0.4.0's id `REL040` does not change, so nothing else waits on it.
- On acceptance, one docs-only commit adds the register entry (§9, unnumbered) and pastes amendment A-9 (§5) verbatim
  into `docs/derivations/release-procedure.md` as §17.2, with D1.5 edited as A-9 states.

**Author:** design lane (`specifier`). **Brief:** `docs/briefs/REL-id-specifier.md`.
**Serves:** `docs/reviews/RP-review.md` ruling 4, must-fix K-1 and note N-4; RP amendment A-7 (R-948).
**Change rule served:** plan §2.2 / `docs/interfaces-frozen.md` header: a widening of a frozen schema needs a design-lane
ADR. Precedent: ADR 0059 (R-938), whose D3 this ADR follows (one closed alternative, no generic pattern).
**Amends:** RP D1.5, by A-9. **Does not amend:** ADR 0055 (out of scope, see O-4), RP's other steps, the line-file
schema, the ledger and model-manifest schemas, any committed manifest, line file, test or script.

## 1. Context (measured on `main` = `7be54945`)

- `schemas/evidence-manifest.schema.json:23` (ADR 0059 D1, Accepted):
  `^(?:[PKTMSR][0-9]{2}[a-z]?|F[0-9]|X[0-9]{2}[a-z]?|TX|MSG|ST|OPT|RRC|PrISMa)$`.
  `tests/test_evidence_manifests.py:73-85` is ADR 0059's additivity check; `test_manifest_path_matches_contents`
  (`:107`) requires the directory `evidence/<work_package>/` to equal the field. `jsonschema` applies `pattern` with
  Python's `re.search`, in which `\d` matches every Unicode decimal digit; the pattern therefore spells `[0-9]`.
- RP D1.5 (`docs/derivations/release-procedure.md:93-99`) and ADR 0055 D1 item 5
  (`docs/adr/0055-standing-release-procedure.md:98-101`): "the evidence package of
  release X.Y.Z is `REL` followed by the version's digits (0.4.0 → `REL040`)". The harvest tuple at 0.4.0 is
  `("evidence/REL040/",)` (RP §5.2, `:393`). A-7 (`:1102`) defers admission to "the schema ADR of ruling 4".
- N-4: plain concatenation is not injective once a component reaches 10. 1.10.0 and 11.0.0 both give `REL1100`;
  0.1.10 and 0.11.0 both give `REL0110`; 1.1.10, 1.11.0 and 11.1.0 all give `REL1110`.
- `release/lines/0.4.json` writes `gate_set.evidence_package` = `REL040` by hand (with `verdict_document`
  `docs/reviews/REL040-verdicts.md`, `rc_record` `docs/REL040-rc-record.md`). `0.3.json` writes `S13`. Nothing derives
  the id from the version, and no loader check (RP.L01–RP.L10) binds it to the line (O-3).
- `release/lines/release-line-v1.schema.json:229-232` constrains `evidence_package` to `^[A-Z][A-Za-z0-9]*$`. Any id
  with a separator (`-`, `_`, `.`) would need that schema widened as well.
- `REL040` is used literally in `tests/test_rel_standing_acceptances.py`, `tests/test_rel_rc_local.py` and the
  `scripts/release_rc.py` docstring. None of them changes under this ADR.
- The release manifest enters the ledger only as a path in a requirement's `evidence` list, a free string
  (`docs/requirements.yaml:929` cites S13's). The release package is not an implementing package in `packages`, whose
  `package_id` stays `^[PKTMSR][0-9]{2}$` (ADR 0059 D2).
- 0.3.0's release evidence is `S13` (harvested). RP's own package manifest is `S15` (C-22). Neither moves.

## 2. Decision

**D1. The pattern.** `schemas/evidence-manifest.schema.json` `properties.work_package.pattern` becomes exactly

```
^(?:[PKTMSR][0-9]{2}[a-z]?|F[0-9]|X[0-9]{2}[a-z]?|TX|MSG|ST|OPT|RRC|PrISMa|REL(?:[0-9]|b[1-9][0-9]|c[1-9][0-9]{2}|d[1-9][0-9]{3}){3})$
```

That is ADR 0059 D1's string with the one alternative `|REL(?:[0-9]|b[1-9][0-9]|c[1-9][0-9]{2}|d[1-9][0-9]{3}){3}`
inserted before the closing `)$`. It contains no backslash, so it is written into the JSON file unescaped. Nothing
else in the schema changes and the schema's version does not move (ADR 0054 and ADR 0059 precedent).

**D2. The mapping.** For a release whose canonical PEP 440 version has the release segment X.Y.Z (exactly three
non-negative integers), the release evidence package id is

  `REL` + code(X) + code(Y) + code(Z),

where code(n) is n's single decimal digit if n < 10, and otherwise **the k-th lower-case letter followed by n's k
decimal digits** (no leading zeros), k ≥ 2: `b` for 10–99, `c` for 100–999, `d` for 1 000–9 999, `e` for
10 000–99 999, and so on to `z` (k ≤ 26). The letter states how many digits follow. A one-digit number would take `a`;
it is written bare instead, which is what keeps D1.5's ids.

Examples: 0.4.0 → `REL040`; 0.10.0 → `REL0b100`; 1.10.0 → `REL1b100`; 11.0.0 → `RELb1100`; 0.4.10 → `REL04b10`;
2027.1.0 → `RELd202710`. §6 RID.A04 is the registered table.

The id covers the whole release:
- A pre-release of X.Y.Z (`0.4.0b1`, `0.4.0rc1`) carries X.Y.Z's id. The line's single `gate_set.evidence_package`
  serves every version that `covers` admits (RP §3.1, RP.S02). Its manifests differ by C.
- A post-release `X.Y.Z.postN` carries X.Y.Z's id. It is gated by the same gate set and the same C (RP §7.5, R-922).
- A `.devN` version is never released (RP §7.4) and has no id.
- A version whose release segment does not have exactly three components has no id. An implementation of D2 refuses
  it and names the version. It never pads, truncates or wraps a component.

**D3. The range, and what happens beyond it.** D1 admits components 0–9 999 (markers `b`, `c`, `d`). For a component
≥ 10 000, D2 still defines the id (with `e` or a later letter), and D1 refuses it. That release's manifest then fails
`test_manifest_validates` and `t08.problems`. This is the unsupported result, and it is visible. The remedy is to
amend D1 by one alternative per letter (for example `e[1-9][0-9]{4}`), as ADR 0059 D3 has it. The fix is never a
different id. D2 itself never changes.

**D4. One id per release, never reused, nothing renamed.** Ids from 0.4.0 on are D2's. `S13` (0.3.0), `M07`/`M07a`
(the 0.2 line) and `S15` (RP) stay as filed. No directory, branch, document or line-file field is renamed, because
`REL040` is D2's id for 0.4.0. No other schema changes: the line-file schema already admits every D2 id (RID.A10), and
the ledger and model-manifest `package_id` patterns stay `^[PKTMSR][0-9]{2}$` (ADR 0059 D2).

### 2.1 Why D2 satisfies N-4 (each point is executed by §6)

1. **Prefix-free, hence injective.** A component's first character fixes its code's length: a digit gives 1, the k-th
   letter gives k + 1. An id therefore decodes in one left-to-right pass into exactly three numbers, and two
   different versions cannot share an id. For the same reason no id is a proper prefix of another (RID.A08).
2. **Order-preserving under code-point order.** Take n < m. With the same digit count, the two codes have the same
   first character, and decimal strings without leading zeros compare as numbers. With fewer digits, n's first
   character is smaller: digits (U+0030–0039) sort below lower-case letters (U+0061–007A), and `b` < `c` < `d`. Since
   the code is prefix-free, comparing two ids as strings compares (X, Y, Z) lexicographically. So Python's `sorted`,
   and `ls` in the C locale, list releases in version order (RID.A08). Example: 0.9.9 `REL099` < 0.10.0 `REL0b100` <
   1.0.0 `REL100`.
3. **D1.5 is kept where it was defined.** With X, Y, Z all below 10, the id is `REL` and the three digits. Every id with
   a component ≥ 10 contains a letter. `REL` followed by four or more digits is therefore never an id, and D1 refuses
   it. That covers every colliding plain form of N-4, including `REL1100`, `REL0110` and `REL1110` (RID.A05, RID.A09).
4. **Alphanumeric, with case-unique ids.** An id begins with `R` and holds only digits and the markers `b`–`d`, so
   the line-file schema admits it (RID.A10). Markers are lower-case and fixed by length, so no two ids differ only in
   letter case. That makes the ids safe as directory and file names on a case-insensitive file system (RID.A08).
5. **Disjoint from every other family.** Every string that the REL alternative admits begins with `REL`. ADR 0059's
   alternatives admit `R` only when a digit follows it (`R[0-9]{2}`), and `RRC`. So the widening admits only new
   strings and reclassifies none (RID.A03).

## 3. What this establishes, and what it does not

**Establishes:** the release package id for every three-component release segment; D1's exact pattern; that D1 is
additive and disjoint; and that the id is injective, order-preserving and prefix-free and keeps `REL040`. Each claim
holds over the finite sets of §6, and §2.1 proves it for all versions.

**Does not establish:**
- That a line file names the right id. `evidence_package` is written by hand. An inheriting line file that forgets to
  change it keeps its parent's id, and RP.L03 does not refuse an equal field (O-3).
- That a patch line (`0.4.1` → `REL041`) is a release package under RP. D2 assigns the id so that it never needs
  revisiting, but RP §2.2 still requires an amendment for patch lines.
- That a trailing newline is refused. Under Python's `re.search`, `$` also matches before a final `\n`, so `REL040\n`
  passes the pattern, and so do `S13\n` and every other alternative's ids (measured). This is pre-existing and shared,
  and `test_manifest_path_matches_contents` makes it unreachable for a committed manifest. See O-5.
- Any validation, verification or review evidence. An id is bookkeeping.

## 4. Rejected alternatives

- *Ruling 4's `|REL[0-9]{3,}` with plain digits.* It is not injective (N-4). It also admits the colliding forms, so a
  release filed under `REL1100` could belong to either of two versions.
- *Fixed-width zero-padded components* (two digits each: 0.4.0 → `REL000400`). This renames `REL040` and every default
  built on it (line file, RP D1.5, the §5.2 harvest tuple, two test modules). It still has a bound (the width), and
  every id is longer.
- *A separator* (`REL0-4-0`, `REL0_4_0`, `REL0.4.0`). The line-file schema refuses it, so a second schema would have to
  be widened. A dot also reads like RP's assertion ids (`REL.A01`). And either `REL040` changes, or 0.4.0 becomes the
  one id without a separator.
- *An all-digit width prefix* (`REL` + w + components padded to w digits: 1.10.0 → `REL2011000`). It keeps `REL040`
  and stays numeric. But it is not order-preserving: 0.10.0 sorts after 1.0.0. It also admits non-canonical second ids,
  such as `REL2000400` for 0.4.0, unless the pattern carries a long cross-component alternation.
- *An id per release line* (`REL04`). The line's patch releases would collide with its `.0`, and `REL040` changes.
- *A generic pattern* (`REL[0-9a-z]+`). ADR 0059 D3 rejects it: a closed pattern is the only check that a manifest
  names a real package.
- *An S-id per release.* R-948 rejected it: picking ids does not scale.

## 5. Amendment A-9 to RP (paste verbatim as §17.2 on acceptance)

> ### 17.2 Amendment A-9 (ADR 0074, 2026-11-08)
>
> - **A-9 (§3.1, D1.5; RP review ruling 4, N-4).** D1.5's mapping is ADR 0074 D2, and its admission is ADR 0074 D1.
>   In D1.5, the sentence "The release of `X.Y.Z` has the evidence package `REL` followed by the version's digits
>   (0.4.0: `REL040`)." is replaced by: "The release of `X.Y.Z` has the evidence package `REL` followed by the codes of
>   X, Y and Z (ADR 0074 D2). A number below 10 is its digit. A number of k ≥ 2 digits is the k-th lower-case letter
>   followed by its digits. So 0.4.0 is `REL040`, 0.10.0 is `REL0b100`, and 11.0.0 is `RELb1100`. Its pre-releases and
>   post-releases carry the same id." The sentence "The id `REL` plus digits is admitted by the schema ADR of the RP
>   review's ruling 4, which widens the manifest's `work_package` pattern; until it is applied, `t08.problems` refuses
>   `evidence/REL040/<C>/manifest.json` (Q-C6)." is replaced by: "The id is admitted by ADR 0074 D1, one additive
>   alternative of the manifest's `work_package` pattern (components up to 9 999)." D1.5's closing reference becomes
>   "Amendments A-7 (§17.1) and A-9 (§17.2)." Nothing else in RP changes. Every default that D1.5 names for 0.4.0 is
>   unchanged.

## 6. Acceptance evidence (the build lane records it)

All checks go in `tests/test_evidence_manifests.py`, next to `test_work_package_pattern_widening_is_additive`, which
stays unchanged. "Accepted" means `re.search(p, s) is not None`, with `p` read from the committed schema, never from a
hand copy. That is the semantics `jsonschema` uses. The test writes its own `rel_id` from D2's text, as the
expectation. Every check is exact, because membership and string equality are boolean. No floating-point quantity
is involved, so no roundoff floor applies. Each count is an exact integer from a closed form given with it.

- **RID.A01 (one alternative, alone).** The committed pattern equals ADR 0059 D1's string (as a literal in the test)
  with `|REL(?:[0-9]|b[1-9][0-9]|c[1-9][0-9]{2}|d[1-9][0-9]{3}){3}` inserted before the final `)$`. Catches an
  incidental edit to another alternative.
- **RID.A02 (additive).** `test_work_package_pattern_widening_is_additive` passes unchanged: all 6 × 100 × 27 = 16 200
  old ids, ADR 0059's 10 admitted ids and its 12 refused strings.
- **RID.A03 (disjoint).** ADR 0059 D1's literal pattern refuses every id of RID.A04 and RID.A08. So no previously
  admitted string acquires a second reading.
- **RID.A04 (registered ids).** For each row, `rel_id(v)` equals the id and the pattern accepts it. The rows are in
  version order, and the ids are in code-point order:

  | version | id | why it is here |
  | --- | --- | --- |
  | 0.0.0 | `REL000` | lower end |
  | 0.1.10 | `REL01b10` | plain form `REL0110` collides with 0.11.0 |
  | 0.4.0 | `REL040` | RP D1.5 and `release/lines/0.4.json`, unchanged |
  | 0.4.1 | `REL041` | a patch version (§3) |
  | 0.5.0 | `REL050` | next line |
  | 0.9.9 | `REL099` | last all-digit id before a marker |
  | 0.10.0 | `REL0b100` | first marker, in the middle position |
  | 0.11.0 | `REL0b110` | the other half of `REL0110` |
  | 0.99.0 | `REL0b990` | top of `b` |
  | 0.100.0 | `REL0c1000` | first `c` |
  | 1.0.0 | `REL100` | after 0.100.0 in both orders |
  | 1.1.10 | `REL11b10` | `REL1110` collision, 1 of 3 |
  | 1.10.0 | `REL1b100` | N-4's first |
  | 1.11.0 | `REL1b110` | `REL1110` collision, 2 of 3 |
  | 9.9.9 | `REL999` | top all-digit id |
  | 10.10.10 | `RELb10b10b10` | a marker in every position |
  | 11.0.0 | `RELb1100` | N-4's second |
  | 11.1.0 | `RELb1110` | `REL1110` collision, 3 of 3 |
  | 2027.1.0 | `RELd202710` | a calendar-year major |
  | 9999.9999.9999 | `RELd9999d9999d9999` | top of D1's range |

- **RID.A05 (refused, each for a stated reason).** The pattern refuses all 32 of these:
  `REL` (no component); `REL04` (two); `REL0400` (four); `REL1100`, `REL0110`, `REL1110`, `REL0100` (plain forms
  with a component ≥ 10, N-4); `REL01000` (five digits); `REL0b010` (leading zero after a marker); `REL0b5` (`b` with
  one digit); `REL0b1000` (`b` with three digits); `REL0c100` (`c` takes `100`, leaving two components);
  `REL0c0100` (leading zero); `REL0a40` (`a` is never a marker); `REL0B100` (upper-case marker); `REL0b10b10b10`
  (four components); `REL0e100000` and `RELe1000000` (0.10000.0 and 10000.0.0, beyond D1's range, D3); `rel040`,
  `Rel040` (case); `REL040a` (suffix letter); `REL-040`, `REL_040`, `REL.040`, `REL0.4.0` (separators); `REL.A01`
  (RP's assertion id); `REL040 `, ` REL040` (whitespace); `RELL040`, `RE040` (prefix typos); `REL` + U+0660 U+0664
  U+0660 (Arabic-Indic digits, which `\d` would admit); `REL04` + U+00B9 (superscript one).
- **RID.A06 (exact language on a window).** Over every string s of length 0 to 5 on the 15-letter alphabet
  `0123456789abcde`, that is Σ 15^L = 813 616 strings, the pattern accepts `REL`+s if and only if s is
  code(X)code(Y)code(Z) for some version. Exactly 28 000 are accepted: 10³ all-digit ids, plus 3 × 90 × 10² ids with
  one `b` component. No length-4 string is accepted. The window holds every plain four-digit form, every `b` code in
  each position, and `a` and `e` as non-markers. Measured on TRS2: 1.7 s, all accepted strings as expected.
- **RID.A07 (range, every marker, every position).** For x in 0…10 099 and v in {(x,0,0), (0,x,0), (0,0,x)}, the
  pattern accepts `rel_id(v)` if and only if x ≤ 9 999. That is 30 300 checks: 30 000 accepted and 300 refused. It
  exercises `c` and `d` exhaustively and D3's boundary on both sides.
- **RID.A08 (injective, prefix-free, case-unique, order-preserving).** Take S = {0, 1, 2, 9, 10, 11, 99, 100, 101,
  999, 1000, 1001, 9999}: both sides of each marker boundary, D1's top value, and repeats so that a permuted component
  shows. Over the 13³ = 2 197 versions of S³ in version order:
  - the ids are pairwise distinct (2 197);
  - their lower-cased forms are pairwise distinct (2 197);
  - no id is a proper prefix of its successor in sorted order;
  - `sorted(ids) == ids`.
- **RID.A09 (N-4 settled, both halves).** Over S³:
  - for each of the 13³ − 4³ = 2 133 versions with a component ≥ 10, the plain form `REL` + concatenated digits is
    refused;
  - for each of the 4³ = 64 versions with every component in {0, 1, 2, 9}, the plain form equals `rel_id(v)`.
  Neither half can hold by accident: the first fails for `REL[0-9]{3,}`, and the second fails for any encoding that
  renames `REL040`.
- **RID.A10 (no second schema).** The `gate_set.evidence_package` pattern of `release/lines/release-line-v1.schema.json`
  (read from the file) admits every id of RID.A08.
- **RID.A11 (through the validator).** With `Draft202012Validator` on the committed schema's
  `properties.work_package`, `REL040` and `RELb1100` are valid and `REL1100` is invalid.
- **RID.A12 (committed manifests, isolation).** `tests/test_evidence_manifests.py` passes. The pass count is recorded,
  as ADR 0059 recorded 410, and every committed manifest is byte-unchanged. The commit touches exactly
  `schemas/evidence-manifest.schema.json` and `tests/test_evidence_manifests.py`.

A01–A11 were run once by the design lane as a scratch probe, at `7be54945` with D1's string, and all of them held. The
build lane's test is the executable record of these claims. The probe is not committed.

## 7. Migration impact

None. No committed manifest, directory, branch, line file, test or document changes, because 0.4.0's id is `REL040`
under both D1.5 and D2. Applying D1 lifts `t08.problems`' refusal of `evidence/REL040/<C>/manifest.json` (Q-C6, K-1).
`HARVEST_SIZE` does not move, because no REL manifest exists yet. The first marked id appears at 0.10.0 or 10.0.0.

## 8. Open questions (each with a default; none blocks acceptance)

- **O-1 (Frank's preference, cosmetic): the marker style.** Default: lower-case length letters, as D2 states.
  Changing the style costs nothing until a component first reaches 10, because no marked id exists before then. After
  that, a change means renaming that release.
- **O-2 (preference): D1's range.** Default: up to 9 999 per component (`d`), which admits a calendar-year major such as
  2027. Widening it is one alternative per letter (D3).
- **O-3 (scope, design lane): bind `evidence_package` to the line.** A 0.5 line file that inherits 0.4 without
  changing `evidence_package` keeps `REL040`. RP.L03 does not refuse an equal field, and no check refuses this. The
  0.5.0 release would then share 0.4.0's directory and harvest exclusion. Default: an RP amendment adds
  **RP.L11**: "for `role` `gate`, `gate_set.evidence_package` equals ADR 0074 D2's id of `<line>.0`. Control: `0.4.json`
  with `REL050`." The build lane implements it in `scripts/release_gate.py` with its own encoder. It is due before the
  0.5 line file is written, and it is outside this ADR's isolated commit. It cannot bite before then: the only `gate`
  line is 0.4, whose id is D2's.
- **O-4 (scope): ADR 0055 D1 item 5** carries the same plain-digits wording. RP is the normative text (ADR 0055's
  header), so A-9 governs. Default: when K-2 marks ADR 0055 Accepted, the marker adds the pointer "the mapping is ADR
  0074 D2 (RP A-9)". This ADR does not edit ADR 0055.
- **O-5 (needs a fact; recommended no change): a trailing `\n`.** A string with a trailing newline passes every
  alternative under `re.search` (§3). Refusing it narrows all alternatives at once, so it needs its own ADR. The fact
  that would justify that ADR is a committed manifest whose `work_package` contains a newline. None exists, and the
  directory-equality test rules one out.

## 9. Register entry (draft, unnumbered)

**R-??? — The release evidence package id is `REL` and a length-marked code of X.Y.Z, admitted by one additive
`work_package` alternative (ADR 0074; RP amendment A-9).**
- *Decision.* A component below 10 is its digit. A component of k ≥ 2 digits is the k-th lower-case letter followed by
  its digits. Examples: 0.4.0 `REL040`, 1.10.0 `REL1b100`, 11.0.0 `RELb1100`. Pre-releases and post-releases share
  the id. The pattern gains `REL(?:[0-9]|b[1-9][0-9]|c[1-9][0-9]{2}|d[1-9][0-9]{3}){3}`, so components up to 9 999 are
  admitted. Beyond that, D1 is amended by one alternative per letter. `S13`, `S15` and `REL040` stay.
- *Rejected.* Ruling 4's `REL[0-9]{3,}` with plain digits (N-4: 1.10.0 and 11.0.0 collide); zero-padded fixed width
  (renames `REL040`); a separator (the line-file schema refuses it, so a second widening); an all-digit width prefix
  (not order-preserving, and admits non-canonical second ids); a generic pattern (ADR 0059 D3).
- *Evidence.* RID.A01–RID.A12; the scratch probe at `7be54945` (A06: 813 616 strings, 28 000 accepted).
- *Watch for.* An inherited `evidence_package` (O-3, RP.L11). An id written with plain digits for a component ≥ 10.
  `\d` in place of `[0-9]`.
