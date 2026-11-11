# RP — the standing release procedure

**Authority.** Design lane (`specifier`), ADR 0055 WO-R1 (brief `docs/briefs/REL-WO-R1-specifier.md`). This is the
normative text that ADR 0055 D1.1 names (R-915). ADR 0055 is its policy. From 0.4.0 on, this text replaces the
per-release specification, the per-release policy ADR and the per-release `scripts/v0_N_gate.py`.
**Folds in.** V03 spec (`docs/derivations/V03-release-spec.md`) §2–§7 and §10.1; the alpha spec
(`docs/derivations/V02-alpha-release-spec.md`) §8.2 steps 1–12 as M07 spec §8 reads them (with [A6], [A7]); and the
register entries R-460, R-875, R-902, R-903, R-906, R-907, R-909, R-911, R-913 and R-914, each written into the step it
governs (§14).
**Scope of this version.** ADR 0055 D1, D3 and D4, as Frank answered on 2026-10-31 ("1–3 now, 4 later
(Recommended)"). **D2, the evidence-fingerprint carry (R-916, R-917, WO-R5), is deferred.** RP describes no carry.
Where ADR 0055 places a D2 step, RP says that every claimed gate is judged and names D2 as a later amendment. The same
holds for the `strace` parts of WO-R4 and WO-R6, for REL.A11–A16 and A21, and for the `gate_row:` scope term.
**Machine-readable companions.** `release/lines/release-line-v1.schema.json` (the line-file shape),
`release/lines/0.3.json`, `release/lines/0.4.json` and `release/acceptances.md`, all written with this text.
**Changes.** RP changes only by an amendment section (§17) recorded in the register. It is never rewritten for a
release.

## 1. Authority and scope

1. RP governs every release cut from 0.4.0 on, pre-releases included. Post-releases stay under R-922 (§7.5).
2. The 0.1, 0.2 and 0.3 lines keep their scripts, registries, tests and records. Their behaviour does not change by a
   byte (REL.A04). `release/lines/0.3.json` transcribes the 0.3 gate set so that 0.4 can inherit from it. It never
   gates a 0.3 version (§3.5).
3. RP changes no gate's criteria or tolerances, no 0.3.0 record, and not `CLAUDE.md`.
4. **Precedence.** For a release from 0.4.0 on:
   - RP holds the procedure, the RC steps and the standing assertions;
   - the line file holds the values: the claim set, the clause grammar, the paths, the packages, the ADRs, the items
     and the phrases;
   - the criteria documents that a line file names hold the criteria;
   - `release/acceptances.md` holds Frank's standing answers.

   Where a line file and RP disagree on procedure, RP wins, and the disagreement is a defect of the line file.

## 2. What RP establishes, and what it does not

### 2.1 What it establishes

1. The line-file format `release-line-v1`, its inheritance rule and its loader checks RP.L01–RP.L11 (§3).
2. The rules of judgement, the clause criteria carried, and the criteria that RP itself restates: X31, the V17 carry,
   W25 at J, and W26 as a function of whether W27 is claimed (§4).
3. K3, C, the RC job's standing steps 1–16, step 17 over the line's items, and step 18's place in the acyclic order
   (§5, §6, §9).
4. The version pin, the working form, the version as build provenance, and what happens after the tag (§7).
5. The exact definitions behind the standing acceptances: scope terms, fingerprints, the standing rule, dates and the
   lapse report (§8).
6. The release notes (§10), the standing assertion catalogue RP.S01–RP.S22 with each one's 0.3.0 counterpart (§11),
   the stops (§12), and the lanes per release (§13).
7. The coverage table of REL.A18 (§14).

### 2.2 What it does not establish

- That any gate passes at 0.4.0, or that 0.4.0 claims what 0.3.0 claimed. 0.4's claim set is seeded from 0.3.0's.
  The 0.4.0 cut revisits it (§3.6).
- Any carry of a verdict. With D2 deferred, every claimed gate is judged at every release. `gates[*]` (T, R, criteria,
  documents) is seeded for the verdict agent's brief and for D2's later use. No fingerprint Φ is computed and no row
  is carried.
- That the seeded `gates[*]` are minimal. T(g) is seeded at package-prefix granularity from 0.3.0's Basis column, a
  superset (§3.3). A superset makes a later carry less likely, never dishonest. Narrowing it is D2's work.
- That the seeded acceptance fingerprints are evidence of anything except byte equality of their scopes. A standing
  row is Frank's answer bound to what he answered. It is not a review.
- That the commands of the rc items `E01-A48` and `WHEEL-DATA` exist. They are WO-R6's to provide (§3.6). Until they
  do, those items fail, visibly.
- That the line-file format suits a patch line (`0.4.1`) or a gate family that does not exist yet. Each needs an
  amendment.
- Numerical verification, empirical validation or optimality evidence of any kind. RP is procedure.

## 3. The line file (`release-line-v1`)

### 3.1 Fields

`release/lines/<major>.<minor>.json` is one JSON object. `release/lines/release-line-v1.schema.json` (JSON Schema
2020-12) fixes its shape. It lives outside the D2.4 paths and outside `schemas/` (a frozen interface directory).

| Field | Holds |
| --- | --- |
| `format` | `release-line-v1` |
| `line` | `<major>.<minor>`, equal to the file name's stem |
| `role` | `gate` for a line that the generic gate gates; `inheritance` for a transcription that is only inherited |
| `inherits` | the previous line, for example `"0.3"`; `null` only for the root of a chain |
| `changed` | the names of the fields that differ from the inherited line's (§3.2) |
| `_comment` | free text, a list of strings; never compared |
| `gate_set` | every `GateSet` field of `scripts/v0_2_gate.py`, with `policy_adr` renamed `acceptances` |
| `changelog_what_it_is_not` | the registered phrases of the notes (§10), in order |
| `gates` | per claimed gate: `tests` T(g), `rc` R(g), `criteria`, `documents` (§3.3); required for `role` `gate` |
| `rc_items` | the line's package items run at step 17 (§3.3, §6.7); required for `role` `gate` |

`gate_set` holds exactly these 18 fields: `name`, `covers`, `claimed`, `not_claimed`, `clause`, `acceptances`,
`verdict_document`, `rc_record`, `rc_steps`, `rc_last_step`, `evidence_package`, `packages`, `envelope_id`,
`required_adrs`, `frank_items`, `rejudge_waits`, `links_item`, `specification_texts`. Patterns (`covers`, `clause`)
are the strings of the `re.Pattern`s. Tuples are JSON arrays. `None` is `null`.

**The release package (D1.5).** The release of `X.Y.Z` has the evidence package `REL` followed by the codes of
X, Y and Z (ADR 0074 D2). A number below 10 is its digit. A number of k ≥ 2 digits is the k-th lower-case letter
followed by its digits. So 0.4.0 is `REL040`, 0.10.0 is `REL0b100`, and 11.0.0 is `RELb1100`. Its pre-releases and
post-releases carry the same id (ADR 0074 D2). It gives these defaults: branch `wp/REL040`, release manifest
`evidence/REL040/<C>/manifest.json`, verdicts `docs/reviews/REL040-verdicts.md`, RC record `docs/REL040-rc-record.md`,
build log `docs/REL040_RC_DECISIONS.md`. D1.2's top-level `evidence_package` is the `gate_set` field of that name. It
is not repeated (one value, one place; Q-3). The id is admitted by ADR 0074 D1, one additive alternative of the manifest's
`work_package` pattern (components up to 9 999). RP's own package manifest is filed as `S15` (C-22). Amendments A-7 (§17.1) and A-9 (§17.2).

### 3.2 Inheritance and `changed` (REL.A01)

The **compared fields** are the 18 `gate_set.<name>` fields, `gates`, `rc_items` and `changelog_what_it_is_not`.
`format`, `line`, `role`, `inherits`, `changed` and `_comment` are never compared. Two values are equal if and only if
their parsed JSON values are equal: lists element by element in order, and objects key by key. A field absent from one
file and present in the other differs.

For a line file L with `inherits` P:
- a compared field that differs between L and P and is not named in L's `changed` refuses with exit 2 and
  `line <L>: field <f> differs from <P> and is not in changed` (REL.A01);
- a name in L's `changed` whose field is equal in L and P refuses with exit 2 and
  `line <L>: field <f> is in changed but equals <P>'s` (RP.L04). So `changed` is exact in both directions.

A silent edit to the claim set, a clause grammar, a phrase or an item therefore cannot pass. Who may write which field
is §13's rule (R-921).

### 3.3 `gates[*]` and `rc_items`

**`gates[g]`** for each claimed gate g:
- `tests`: T(g), repository-relative globs of test files (pytest modules, and `tests/web/*.test.mjs` where node
  evidence applies). The glob grammar is §8.2's (P1).
- `rc`: R(g), `[step, check]` pairs. `step` is an RC step number. `check` is a check id of that step's records, or a
  prefix followed by one trailing `*`, or `*` alone (every check of the step). For step 17, `check` is an `rc_items`
  id (§6.7).
- `criteria`: paths of the documents that define g's criteria.
- `documents`: paths whose content is g's evidence and is not re-run at C, such as a package verdict document. A path
  may name a directory.

With D2 deferred these four lists do two things. They give the verdict agent's brief its inputs (§4.7). They are
checked for well-formedness (RP.L05–RP.L07). They are not compared between releases, and nothing carries on them.

**`rc_items[i]`**, run in order at step 17:
- `id`: unique, `^[A-Z0-9][A-Za-z0-9-]*$`;
- `assertion`: what the item carries, naming its package assertion;
- `script`: the file that owns the item's code. It is the package's own, never a per-release RC script
  (`scripts/v0N_rc.py`);
- `where`: `local:<environment>` with environment `project`, `coolprop`, `reactor`, `nlp` or `lca` (§6.7), or
  `ci:<job>` for a `ci.yml` job of the `release_rc` dispatch;
- `command`: for a `local:` item only, the argv run from the repository root at C (§6.7).

`where` and the rule that the wrapper writes the record (§6.7) make D1.2's list precise. D1.2 lists no `where`, and
D1.3 has a wrapper write each item's record (Q-4, Q-5).

### 3.4 The loader's checks (RP.L01–RP.L11)

`scripts/release_gate.py` (WO-R2) loads a line file and refuses with exit 2 and the stated reason when any check
fails. Each check has a control: a copy of the committed file with one change, which must be refused.

- **RP.L01.** `format` is `release-line-v1`, and the file validates against the schema. Control: `policy_adr` in
  place of `acceptances`.
- **RP.L02.** `line` equals the file name's stem, and the `inherits` chain ends at `null` with no cycle. Control:
  `inherits` naming the file's own line.
- **RP.L03.** REL.A01 (§3.2). Control: one `gate_set` field edited with `changed` unchanged.
- **RP.L04.** A name in `changed` whose field is equal is refused (§3.2). Control: `gate_set.packages` added to
  `changed`.
- **RP.L05.** At C, every `tests` glob matches a tracked file, and every `criteria` and `documents` path exists.
  Control: `tests/test_zz_*.py` added to a gate's `tests`.
- **RP.L06.** For `role` `gate`, the keys of `gates` equal `claimed` as a set. Control: the `X31` entry removed.
- **RP.L07.** Each `rc` pair's step is in `rc_steps`; a step-17 pair names an `rc_items` id, and no other pair does.
  Control: `[17, "NO-SUCH-ITEM"]`.
- **RP.L08.** `rc_items` ids are unique, and each `script` exists at C. Control: a duplicated id.
- **RP.L09.** `g (a)` fullmatches `clause` for every claimed g and for no not-claimed g. Control: `W27` added to the
  clause's alternation.
- **RP.L10.** Every `frank_items` entry has exactly one row in the decisions table of `acceptances`; `links_item` and
  every `rejudge_waits` item are in `frank_items`; every `rejudge_waits` gate is claimed. Control: `rejudge_waits`
  gains `["W27", "M02 N1"]`.
- **RP.L11** (amendment A-10, §17.3; ADR 0074 O-3, 2026-11-09). For `role` `gate`, `gate_set.evidence_package`
  equals ADR 0074 D2's id of `<line>.0`. Control: `0.4.json` with `REL050`.

RP.L05 and RP.L08 are checked at C (the commit is read with `git`), because the files they name are the candidate's.
RP.L08 fails today, on purpose: `scripts/wheel_data_check.py`, the script of item `WHEEL-DATA`, does not exist at
`main` = `1fcdbb1b`. So the 0.4 line file fails RP.L08 until WO-R6 provides it. The failure is the visible result that
§12 requires, not a defect of the line file. Amendment A-8 (§17.1): RP.L08 now passes, because
`scripts/wheel_data_check.py` exists (`bd672ff7`).

**Measured on the committed files** (design lane, 2026-11-06, at `main` = `1fcdbb1b` with this text on disk):
- the two line files validate against the schema;
- ten schema controls are each rejected: a missing `rc_items` under `role` `gate`, a `local:` item without `command`,
  a `ci:` item with one, an unknown `changed` name, `policy_adr`, an inner `*` in a check pattern, a `..` path, a
  malformed `clause`, `role` `gate` with `inherits` `null`, and a root with `changed` non-empty;
- `0.4.json`'s `changed` equals the computed set of differing fields (RP.L03, RP.L04);
- every `tests` glob of `0.4.json` matches at least one tracked file, and every `criteria` and `documents` path exists
  (RP.L05). The first run of this check found W26's document `benchmarks/m06/w27/coverage.json` missing. That path is
  a misprint carried from V03 §3.5 (§4.6). The line file now names the committed record;
- RP.L06, RP.L07, RP.L09 and RP.L10 hold, and RP.L08 fails only on `WHEEL-DATA`.

### 3.5 Gate resolution, and the 0.3 transcription (REL.A02, REL.A05)

`release.yml` resolves the gate for version `M.m.p…` this way:
1. if `release/lines/M.m.json` exists **and its `role` is `gate`**, it runs
   `scripts/release_gate.py --line M.m --rc <rc>`;
2. otherwise, if `scripts/vM_m_gate.py` exists, it runs that script;
3. otherwise it refuses with `no release gate for the M.m line`.

The `role` condition in item 1 is RP's. ADR 0055 D1.3 says "if the line file exists". But WO-R1 must also write
`release/lines/0.3.json`, and REL.A05 expects `0.3.0` to resolve to the legacy script. Read literally, D1.3 would send
0.3.0 (and 0.3.0.postN, R-922) to the generic gate. The `role` field keeps both statements true (finding F-1, §16).

`release/lines/0.3.json` has `role` `inheritance`, `inherits` `null` and `changed` `[]`. Its `gate_set` equals
`scripts/v0_3_gate.py` `GATE_SETS[0]` field by field, with `acceptances` = `docs/adr/0053-v0.3.0-release-policy.md`
(REL.A02; measured equal on 2026-11-06 by importing `v0_3_gate`). Its `changelog_what_it_is_not` is
`benchmarks/v03/registration.json`'s, the 17 phrases of V03 §8. It has no `gates` and no `rc_items`: 0.3.0 predates
them. `scripts/release_gate.py --line 0.3 --rc a3e508e3` still runs, in dated mode, for REL.A03's equivalence test.
`release.yml` never resolves to it.

### 3.6 The 0.4 line: what is seeded, and what 0.4.0's cut must revisit

`release/lines/0.4.json` has `role` `gate` and `inherits` `"0.3"`. Its `changed` is exactly the 13 compared fields
that differ from 0.3: `changelog_what_it_is_not`, `gate_set.acceptances`, `gate_set.covers`, `gate_set.envelope_id`,
`gate_set.evidence_package`, `gate_set.frank_items`, `gate_set.name`, `gate_set.rc_record`, `gate_set.required_adrs`,
`gate_set.specification_texts`, `gate_set.verdict_document`, `gates` and `rc_items`.

**Seeded (unchanged from 0.3):** `claimed` (V11–V20, W21–W26, X31), `not_claimed` (W27), `clause`, `rc_steps` (1–17),
`rc_last_step` (18), `packages` (the twenty of 0.3.0), `rejudge_waits`, `links_item`.

**Seeded (changed, each a consequence of RP or ADR 0055, not a new claim):**
- `name` `v0.4-gate-v1`; `covers` `0\.4\.0(?:(?:b|rc)[1-9][0-9]*)?` (0.3's pattern at 0.4);
- `acceptances` `release/acceptances.md`; `verdict_document`, `rc_record`, `evidence_package` from D1.5;
- `envelope_id` `v0.4-envelope-1`; `specification_texts` `["the standing release procedure", "§6"]`;
- `required_adrs`: 0.3's 25 plus `0055`, the policy of RP, as 0.3.0 required its own policy ADR 0053 (Q-12);
- `frank_items`: 0.3's four plus `coolprop and lca licences`, the row ADR 0055 N-7 seeds (§8.1);
- phrase 15 `no W27 claim in 0.3.0` becomes `no W27 claim in 0.4.0`. The phrase names the release that does not
  claim W27, so the version follows the release. No other phrase changes (Q-14);
- `gates[*]`: T(g) at package-prefix granularity, R(g), criteria and documents, each read from the Basis column of
  `docs/reviews/V03-verdicts.md` (§3.3). For example, V11's Basis "K06, T01, T06 and T07 nodes, T08.A10, T08.A35 and
  M07a.A42 green in step 1" gives T = `tests/test_{k06,t01,t06,t07,t08,m07a}_*.py` and R = `[1, "*"]`. The design
  review of WO-R1 compares each entry with its Basis cell (ADR 0055 §6);
- `rc_items`: V03's 17a–17e, each with a standing owner, plus `PTC-R1` under N-2 (§6.7):
  `E01-A48` (17a), `S07-F8` (17b, CI's `rc-coolprop`, D4.5), `MR12-coolprop` and `MR12-lca` (17c), `E01-G5-lca` and
  `E01-G6-nlp` (17d), `WHEEL-DATA` (17e's V03.A17 and A19), `PTC-R1`. 17e's wheel build (T08.A43) is not an item:
  step 3 builds and checks the wheel at C on CI.

**What 0.4.0's cut must revisit** (a `specifier` pass, D5 (1), when any of these changes; otherwise it stands):
1. The claim set. 0.4 may add gates for what it ships (MSG, ST, X04, X05, …). Each new gate needs criteria in an RP
   amendment (D1.4), a `gates` entry, a clause grammar that parses it, and Frank's re-dated `Claim set` row.
2. `packages` and `required_adrs`: the packages and ADRs 0.4.0's claims rest on.
3. The phrases: what 0.4 adds that it is not.
4. `rc_items`:
   - `E01-A48` needs `scripts/e01_evidence_manifest.py --a48-release-check`, which exits 0 if and only if
     `a48_release_check()` returns `pass` (WO-R6);
   - `WHEEL-DATA` needs `scripts/wheel_data_check.py --commit <C>`. It moves V03.A17's ship-set and E01-data
     inspection and V03.A19's fresh-venv probe out of `scripts/v03_rc.py` (WO-R6). If 0.4 ships no package data
     beyond 0.3.0's, the item is kept as it is;
   - `PTC-R1` stays only if WO-R4's dispatch shows it finishing within 360 minutes on both legs (N-2). Otherwise the
     item and V14's `[17, "PTC-R1"]` pair are removed, by a design-lane edit listed in `changed`;
   - MR-12 for any extra new since 0.3.0 (V03 §9.3's rule, "new since the previous release");
   - V03.A12 (c)'s S11 identity at a version cut (R-910) and V03.A24's R-845 watch (the relative class's worst at
     most 0.1 of its bound): 0.3.0 judged them as V03 assertions, not as release steps. They recur at 0.4.0 only as
     items that the revisit adds. The class ratios themselves are recorded at every release (RP.S15).
5. `gates[*]` of every changed gate, and the R(g) pairs, once WO-R6 fixes the standing records' check ids (§6.1).

### 3.7 The per-release delta (D1.4)

A release's delta is its line file (complete, with `inherits` and `changed`) plus one block in `docs/RELEASING.md` of
at most 40 lines. The block states the version, C, what `changed` lists and why, the new gates and items, and Frank's
new answers. There is no per-release specification, policy ADR or gate script (R-915's watch: a `scripts/v0_4_gate.py`
or a release spec under `docs/derivations/`). A release needs an ADR only if it departs from RP or ADR 0055. A new gate
needs an RP amendment that states its criteria.

## 4. Judgement

### 4.1 Rules

T08 §3.3 applies unchanged:
- the vocabulary is `PASS`, `FAIL` and `BLOCKED`, and `BLOCKED` is used only when the missing input is outside both
  lanes' authority;
- judgement is clause-wise, and a `FAIL` names its clause;
- every gate is judged at C;
- no new tolerance is introduced;
- numerical verification, empirical validation and optimality are kept distinct.

The alpha spec's §4 additions apply with these readings:
1. **Acceptances.** A `FAIL` is releasable only if each failing clause has a standing row in `release/acceptances.md`
   at C (§8.3). This replaces alpha §4 rule 1, ADR 0042 D2 and ADR 0053 D2's date rule for standing rows (ADR 0055
   D3.4, R-918). `BLOCKED` blocks the tag.
2. **Moved records have counterparts**, at least as strict (alpha §4 rule 2).
3. **Evidence about another commit reaches C only through the RC job** or a registered evidence carry: the journey
   (R-337, R-453), V17 (R-457, R-462) and W27 (M07 §9). These are the only evidence carries. RP adds none.
4. **Unmeasured is stated, never omitted.** An aspect the RC does not measure is a limitation row of the envelope and
   is named in the notes.

### 4.2 Clause criteria carried

- V11–V20, W21 and W22: alpha spec §5–§6, with T08 §4.
- W23–W25: M07 §7.3.
- W26: M07 §7.3, with (a) as §4.6 states.
- X31: §4.3.

The verdict agent applies them at C, with C's records. A clause is judged only on evidence at C, or on evidence carried
to C by a registered carry (§4.1 item 3).

### 4.3 X31 — "Four matched column cases, invalid specs/phases, two independent references where available"

From V03 §3.2, unchanged:
- **X31 (a).** RC1–RC4 (S02's M1–M4 at `P_r`) solve, and their registered matches hold. Evidence: S02's manifest; the
  S03/S09 A10 (i) byte-identity and (ii) live-solve classifications in step 1's default gate.
- **X31 (b).** Invalid specifications and phase cases are refused with their registered typed outcomes. Evidence:
  S02's invalid-spec tests; S08's phases clause (R-736); S08b; S10c's column cases, all in step 1.
- **X31 (c).** PASS if and only if S09's three-tool outcome is "met with two references" (4 of 4 at row 5). Any other
  registered outcome is FAIL (c), stated in its registered words. Evidence: `docs/reviews/S09-verdicts.md` verdict 3;
  S03 §17.5; S09 §8.1–§8.3.

The recorded outcome is "met where available, 3 of 4". RC4, the refluxed absorber, has one reference (BioSTEAM). So
X31 is FAIL (c) and releasable only by a standing `X31 (c)` row. This reading is pre-registered: the verdict agent
applies it and does not choose it. A verdict that writes "met with two references" is wrong (R-643's watch item).

### 4.4 The V17 carry

`v17-c2`'s evidence carries to C if and only if step 8 (`scripts/m07a_rc.py surface`) passes at C with `LINKS`
unchanged. "Unchanged" means that a `V17 carry` row stands at C (§8.3): its scope `extract:links +
extract:served_digest` (§8.2 (E3), (E4)) reproduces at C, and it names the register entry of every link (M07 O3,
R-457). Write `LINKS` at C, in its order, as c_1 … c_n. Link c_k has a register entry, a strip function s_k and a
registered digest D_k, and D_0 is R-133's. The served digest must equal the last link's registered digest, D_n. The
chain's rows must be exactly these n + 2, in this order: `(1,c_n)`, then `(2,c_k)` for k = n, n−1, …, 1, then
`(3,None)`. Each is judged as alpha spec §5.3 items 1–3 state, and each passes.
`test_m07a_a37_the_chain_holds_on_the_served_list` pins the instance that `LINKS` holds.
- At 0.3.0, n = 3: c_1 R-192, c_2 R-234 and c_3 R-295; D_3 = `455d01eb…e125`; the rows were
  `[(1,c_3),(2,c_3),(2,c_2),(2,c_1),(3,None)]`.
- At 0.4.0, n = 8: c_4 R-934, c_5 R-950, c_6 R-960, c_7 R-1000 and c_8 R-1010 follow c_3; D_8 = `6be1c002…ba57`; the
  rows are `[(1,c_8),(2,c_8),(2,c_7),(2,c_6),(2,c_5),(2,c_4),(2,c_3),(2,c_2),(2,c_1),(3,None)]`.

If the digest differs, the RC stops (§12). A new link then needs a register entry, a strip function, a registered
digest, and Frank's `V17 carry` row replaced, or else a new V17 campaign. The release-time edit is not improvised.
(Amendment A-12, §17.5.)

### 4.5 W25: the journey at J

M07 §4.6's carry from an earlier release's K fails whenever `carry.journey_files` holds a changed file, and it holds
`src/openflowsheet/**`. So step 15 re-runs the journey at the journey commit J, under M07 §4–§6 and the registration's
budgets unchanged. J is K3 plus the records re-taken under §7.1 (R-458, R-1008). The R-908 pattern applies: `carry.journey_files`
holds `benchmarks/m05/**`, so a journey recorded at K3 itself would not carry past those records. R3 carries M05's REAL
record only if `carry.r3_files` are byte-equal between M05's run commit and J. Otherwise R3 re-runs M05's study at J.
The record is committed in C's tree, carried from J to C by `--carry-journey J --rc C`, and passes `check` and `replay`
at C. Honest outcomes (`BUDGET_EXHAUSTED`, `INCOMPLETE`) are recorded as M07 §5 states. Their verdict is the agent's.

The journey at J runs on the host of §7.1's re-takes, and step 15 replays it at C on that host. Its R1 experiments and
its R3 re-run are bound to that host's platform string through the reactor's fingerprint, as M05's REAL record is.
0.3.0's journey at `2d945b5d` was recorded on kernel `6.12.111` and does not replay on another kernel (S-6).

### 4.6 W26 as a function of whether W27 is claimed (R-903)

**While W27 is not claimed** (it is in `not_claimed`; 0.3 and the seeded 0.4), W26 (a) judges these at C:
- G1–G13 as M07 reads them: `tests/test_m06_*.py` with `OPENFLOWSHEET_REQUIRE_BROWSER=1`, `node --test`, and G12 by
  step 1 and CI;
- G15's registered content: the twenty scorer states W27-S01…S20 (M06-W27 registration §14.3, and §21.7 for S19 and
  S20), run through the production harness and scorer. The non-`CANDIDATE` states are scored against the registered
  rows of the committed coverage record, and the `CANDIDATE` states against W27-A13's synthetic row. The committed
  record is `benchmarks/m06/openidaes450/coverage.json` (`registration.COVERAGE_JSON`). V03 §3.5 printed it as
  `benchmarks/m06/w27/coverage.json`, a path that does not exist. The meaning is unchanged;
- W27-A23 and W27-A79b on stub runs through the real harness;
- the committed record's G14, and the in-process refusal test.

These are the 25 test nodes of step 16's check (c) (§6.6). W26 (a) does not judge G14 on this build, the preflight
check P3, or the stub campaign rehearsal: W27 registration versions 1 and 2 refuse this build (ADR 0050 D9, W27-R63).
Step 16 runs the dry run unchanged and asserts that refusal exactly. W26 (a) is PASS if and only if RP.S19 holds. W26
(b) is unchanged. W26's row carries the travelling limitation `G14 not judged at <version>: W27 registration v1
refuses this build (ADR 0050 D9, W27-R63); W27 not claimed`. A W26 row that reads "M06 G1–G15 met" is wrong.

**When a line claims W27** (a campaign under a registration that classifies the build), W26 (a) is M06 G1–G15 as
M07 §7.3 reads them, under that registration. Step 16's checks (c) and (d) are then replaced by the W27 items that an
RP amendment states for that line. RP does not state them now, because no line claims W27.

### 4.7 The verdict document and the verdict agent's brief

The `verdict` agent writes `gate_set.verdict_document` at C, in the alpha §6.3 form: the header names C once, there is
one `Judged` line, and the table has one row per claimed gate in `claimed` order (verdict, failing clauses or `—`,
travelling limitations, basis). Every clause parses under the line's grammar. Its brief carries:
- C, K3 and the line file;
- for each claimed g, `gates[g].criteria` and `gates[g].documents`, the step records that `gates[g].rc` names, and
  step 1's junit outcomes for the files of `gates[g].tests`;
- the RC record and the release manifest's state, with each step's summary line and record path;
- step 8's chain rows and step 15's carry lines;
- for W21 (e): step 12's experiment record, the files under `step12/experiments/` and step 12's own runs file (§6.4);
- the previous release's verdict document, for comparison only.

It returns one row per claimed gate. It judges nothing that §4 pre-registers differently. With D2 deferred, every row
is judged. The header's `**By:**` names the `verdict` agent, never `carry`.

## 5. K3 and the candidate C

### 5.1 K3 and C

- **K3** is the cut commit on `main` that declares the version and pins the envelope (§7.1).
- **C** is K3 plus exactly two kinds of D2.4 change (`v0_1_gate.TREES`: `src/`, `schemas/`, `benchmarks/`,
  `requirements.lock`, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`, `NOTICE`): the records re-taken
  under §7.1, whose commit is J (§4.5, R-908, R-1008), and J's journey record under `benchmarks/m07/journey/<J>/`. Any other commit
  between K3 and C changes no D2.4 path, and none holds anything the RC job writes. At 0.3.0, J = `2d945b5d`, and
  `git diff --name-only 2d945b5d a3e508e3` over the D2.4 paths lists only `benchmarks/m07/journey/2d945b5d…/` files.
- After C, commits outside the D2.4 paths add the RC records, `release/rc-trees/<C>.json` (R-151, written with
  `scripts/release_gate.py --line <l> --rc <C> --write-tree-record`), the lapse report (§8.5), the verdicts, the
  ledger (`docs/requirements.yaml`), the release manifest and `CHANGELOG.md`'s `## v<version>`.
- C is merged into `main` with a merge commit, never squashed. From K3 until Frank's dispatch, `main` takes no D2.4
  change (RELEASING "Pre-releases" step 2).
- The line file and its inherited chain are byte-equal at C and at the candidate. The gate refuses with exit 2
  otherwise, and a change after C needs a new C (amendment A-3, §17.1). The check belongs to standing mode: the dated
  path is the legacy gate unchanged (REL.A03), and 0.3.0's C holds no line file.

### 5.2 The release manifest is not harvested (R-911)

The release manifest `evidence/<pkg>/<C>/manifest.json` is written after C. Classifying its items would change
`benchmarks/t08/support_envelope.yaml`, a D2.4 path. So `scripts/t08_support_matrix.py` `HARVEST_EXCLUDED` names
`evidence/<pkg>/` for the release being cut, with the trailing slash (so `evidence/S13a/` stays harvested when
`<pkg>` is `S13`). The next envelope's package removes the exclusion and harvests the manifest. The manifest carries
this limitation verbatim, with `<pkg>` and `<envelope_id>` filled in:
`Not harvested into <envelope_id>. This manifest is written after C, and classifying its items would change
benchmarks/t08/support_envelope.yaml, a D2.4 path. scripts/t08_support_matrix.py excludes evidence/<pkg>/, as R-485
and R-911 excluded M07's and S13's manifests from their releases' harvests; the next envelope's package harvests it.`

At 0.3.0 the tuple was `("evidence/S13/",)`. At 0.4.0 it is `("evidence/REL040/",)` once S13's manifest is harvested
by the 0.4 envelope's package. Whether that package harvests S13's manifest before K3₀.₄ is a fact the cut reads from
the tree. Each tuple member must be `evidence/<pkg>/` for a release package whose manifest is not yet harvested (R-911's
watch item).

### 5.3 Preconditions at K3

- (P1) Every package in `gate_set.packages` has a `tested` or `reviewed` manifest at an ancestor of K3.
- (P2) WO-R1 to WO-R4 and WO-R6 are merged, after the full gate and CI on both architectures (ADR 0055 §6).
- (P3) Every `required_adrs` entry is Accepted, or its acceptance route (§9.1) is stated with a condition that can hold
  before step 18.
- (P4) RP.L01–RP.L11 hold for the line file at K3, with RP.L05 and RP.L08 read at K3.
- (P5) The open questions of §15 that the cut depends on are answered, or their defaults stand.
- (P6) The host that takes §7.1's re-takes, and runs steps 6, 11, 14 and 15, is a member of T06's `ref-x86-64`:
  `t08_rc.machine_class()` prints `ref-x86-64` there. A host joins the class only by R-1020's proof
  (`docs/reviews/HOSTMOVE-ruling.md` §7). Otherwise step 6's `a46.registered_class` fails at C, and F0 does not judge
  M4 there (amendment A-13, §17.6).

## 6. The RC job

### 6.1 The steps

Each step runs at C unless stated. Gate column: the claimed gates whose seeded `gates[*].rc` name the step. A step
whose gates are all unclaimed is left out of `rc_steps` by the line file and is not run. The record check ids below are
0.3.0's. WO-R6 keeps them, so that R(g) and REL.A20 read the same ids. A changed id is a line-file change.

1. **CI's push run at C** (D4.1, D4.3; was the alpha's `check.sh` at C). Record `step1/rc-step1.json` (§6.2). Gates:
   every claimed gate whose evidence is the default gate. RP.S11, RP.S15.
2. **Identity** (T08.A42): the R-149 values, unchanged under the trial version `0.1.0`. Local `ref-x86-64`, CI
   `rc-steps` on both legs; G05's cross-architecture check is the `identity` job of the push run at C. Checks
   `a42.minus_t07_registered`, `a42.t07_key_substituted`, `a42.unchanged_under_trial_version`. RP.S11.
3. **sdist and wheel twice** (T08.A43): `Version` equals the version in METADATA and the file names. CI `dist`. Record
   format `t08-a43-dist-v1`, checks `a43.*` and `a31.*`. RP.S11.
4. **Clean install and the packaged lock** (T08.A44; X05.A21, A22 (b), A25; T08.A19 retired by ADR 0069 D7.2). CI
   `clean-install` on both legs. Checks `a44.*`, `x05.*`.
   RP.S11.
5. **The RC bundle set** (T08.A45). CI `bundle-set` writes; `bundle-replay` replays on both legs. Checks `a45.*`,
   `a14.c1`–`c3`. RP.S11.
6. **The registered ensemble and T06 A34's same-class replay** (T08.A46, A47 S3). Local `ref-x86-64`; CI aarch64
   `rc-ensemble`. Checks `a46.*`, `a47.no_verified_outside_s3`, `a34.ensemble_certificates`. Gates: V20. RP.S11.
7. **Adversarial, invalid-structure and reference subsets** (T08.A47, A48). Local; CI `rc-steps` on both legs. Checks
   `a47.T06.*`, `a48.T06.*`. Gates: V16, V20. RP.S11.
8. **The surface chain and G16-b 40 of 40** (alpha §5.3; §4.4 here). Local; CI `rc-steps` on both legs. Checks
   `a37.*`, `a16.g16b_records_attributable`. Gates: V13, V17. RP.S11, RP.S14.
9. **The [A10] inventory** (T08.A30; MR-12) over the default install and `server`. Its workload imports every module
   except the registered `nlp`-extra modules, which must fail on cyipopt or pyomo and are recorded (M07 §24.1 [A7],
   R-478). A failing A30 fails CI's `rc-steps` job (R-479). Local; CI `rc-steps` on both legs. Gates: V18. RP.S11.
10. **Certificates** (T08.A34; MR-11) of the steps that emit them, with step 12's as kept (alpha §8.2 step 10, R-348).
    Where they were emitted. Checks `a34.certificates_audited`, `a34.violations`. Gates: V15, V18. RP.S11.
11. **W22's external records**: `external_crosscheck.py --check`; the IDAES conformance re-run. Local `ref-x86-64`, in
    their pinned environments. Checks `a40.*`. Gates: W22. RP.S11.
12. **W21's reactor evidence**: M02 G10 (a)–(i), G11 (a)–(d) and G12, with G11's experiment results kept and audited
    (§6.4). Local `ref-x86-64`, in the reactor environment built from C's lock, on one thread. Checks `a41.*` and
    `r375.audit`. Gates: V15, W21, W22. RP.S11, RP.S21.
13. **W23**: M04's committed records re-checked: `m04_reference.py --check`, `m04_schema_fixtures.py`, and
    `tests/test_m04_*.py tests/test_evidence_manifests.py`. Local. Checks `a60.w23.*`. Gates: W23. RP.S11.
14. **W24**: M03's nlp tier A35–A42 and M05 G1–G10, G12 and G13, in the audited nlp environment, in a clean worktree at
    C, with the nlp selection of §6.5. Checks `a60.w24.*`. Gates: W24. RP.S11, RP.S20.
15. **W25**: the journey at J carried to C; `check` and `replay` at C (§4.5). Checks `a21.carry_journey`, `a21.check`,
    `a21.replay`. Gates: W25. RP.S12. `a21.replay` carries `host_platform` and `record_platform` in the same way as
    §6.5's `a60.w24.m05_g10_real_replay`, read from the `S0` coupling record of the M05 record that the journey's R3
    used: `benchmarks/m07/journey/<J>/m05/` for a re-run, `benchmarks/m05/records/` for a carried record.
16. **W26** (§4.6, §6.6). Local `ref-x86-64`; the browser leg is CI x86-64's `check` in the push run at C. Checks
    `a60.w26.*`. Gates: W26. RP.S11, RP.S19.
17. **The line's `rc_items`** (§6.7). Gates: as `gates[*].rc` names them. RP.S13.
18. **The gate**: `scripts/release_gate.py --line <l> --rc <C>`. It is not required in the RC record. It runs only at
    §9.2 step 6. Its output goes to the build log. RP.S08 (R), RP.S16 (b), RP.S18 (b).

**How the steps run.** Steps 2–10 run `scripts/t08_rc.py`'s subcommands unchanged, with step 8 as `m07a_rc.py
surface`, as the alpha did (alpha §8.2 "How the steps run"). The local steps run through `scripts/release_rc.py`
(WO-R6), which replaces `scripts/v03_rc.py` and the RC runner `tools/run_local.sh`. With D2 deferred, no step runs
under `strace`. Each record carries `commit` = C, `tree_clean` true, the lock's SHA-256 and the machine class (alpha
§8.3).

### 6.2 Step 1: the push run at C (D4.1, D4.3, R-376, R-476)

"CI green at C on both architectures" is one completed `ci.yml` run whose `event` is `push` and whose `head_sha` is C.
If there are several, it is the one with the greatest run id, at its latest attempt. No step re-runs CI at C to obtain
it. GitHub starts a push run only for a pushed head, so C is pushed on its own, as the head of a branch ref
(`git push origin <C>:refs/heads/rc/<C7>` if it would otherwise be pushed beneath later commits; amendment A-4,
§17.1). The record lists every `ci.yml` run at C with its event, attempt and conclusion (`runs_at_c`), so that a retry
is visible to the verdict; when no push run at C exists, `s1.push_run` names that remedy. Its record `step1/rc-step1.json` (format `t08-rc-v1`, step `ci-push-run`) holds exactly these checks:
- `s1.push_run`: such a run exists and is completed. Its run id is recorded;
- `s1.check.x86_64` and `s1.check.aarch64`: the `check` job concluded `success` on `ubuntu-latest` and on
  `ubuntu-24.04-arm`;
- `s1.junit`: the artifacts `junit-x86_64` and `junit-aarch64` (D4.4) are present. The SHA-256 of each junit file and
  each job log is recorded.

Step 1 is `fail`, never skipped, if no such run exists or a leg is not green (REL.A17). Each leg's skips, read from its
junit, are written beside the RC records as R-376 requires (`step1-skips/`), and the verdict audits them. While the
verdict document is absent at C, the tests that judge it skip by R-476's predicate, each naming the document. Step 18
runs for YES only at a candidate where those tests pass with 0 skipped.

### 6.3 Steps 2–11

As §6.1 states. The constants they compare against (the lock, the K05 identity, the trial version, the bundle sets,
the ensemble) are the registered ones at C. A step whose constant must change at a release changes it by a register
entry before K3, never at C.

### 6.4 Step 12 keeps and audits G11's experiment results (R-909, R-375, R-480)

Alpha §6.1 W21 (e) covers every experiment result record that step 12 writes. G11 writes one at each boundary point.
Under M02 variant v3 that is 105 per run and 210 over its two runs, and none at its 16 direct points per run.
**Step 12 keeps those records in its own first run and audits them:**
1. G11 runs with `--d78` set to the registered extract and without `--previous-runs` (M07 §24.3, R-480), through a
   store-keeping wrapper that keeps each point's store. 0.2.0's `g11keep.py.txt` and `g11collect.py.txt`
   (`evidence/M07/ce993651…/tools/`) are promoted by WO-R6 into a tracked script, which closes R-909's open item A3-3.
   Until they are, they are copied unchanged, and any change is recorded with its diff in the build log.
2. One record per run is collected: `step12/experiments/g11-experiments-run1.json` and `…-run2.json` (gzip beside the
   path over 1 MB).
3. The audit is given **step 12's own runs file**, `step12/g11-coverage-v3.runs.json`:
   `python scripts/m07_g11_experiments_audit.py --variant-file benchmarks/m02/variant-v3-provisional.json --runs
   <rc>/step12/g11-coverage-v3.runs.json --out <rc>/step12/experiments/g11-experiments-audit.json`.
4. The record `step12/experiments/rc-step12-experiments.json` (step `g11-keep-and-audit`, format `t08-rc-v1`) holds
   exactly one check, `r375.audit`. It passes if and only if the audit exits 0 and its line reads exactly
   `G11 experiments audit: 2 runs, 210 boundary points, 210 results, 210 attempts, 0 without a result, 32 direct
   points (no records); 6 items + schema: 0 problems; context (job_id): <j> findings: PASS`, with j recorded and not
   judged. The counts are those of G11's registered coverage under variant v3. A change of that registration changes
   them, by an RP amendment.

Step 12's archived inputs (amendment A-5, §17.1) are `benchmarks/m02/g10-adapter-halves-v3.json` (SHA-256
`c6a520e08433791cdea48821b981dd661a606e86bf99c740ff6bd26c86022586`) and `benchmarks/m02/g11-coverage-v3.json`
(`fa1b02544f00a1ce02a203dc8cccc9d7bc5e35122a79cfe1506e355bb9729a90`) at `bd446abab1bcc26b286ae4a287d1de131d87ceac`.
A failed read, or a hash that differs, stops the RC (§12).

V03.A34's checks (a) `r375.g11_rerun` and (b) `r375.same_computation`, the re-run at C compared with step 12's own
runs file, are the remedy for a step 12 that did not keep the records (0.3.0). They are not part of the standing step
(R-909 item 3). If a step 12 at C keeps nothing, the remedy is applied as V03 §4 states it, and the verdict says so.

### 6.5 Step 14's nlp selection (R-907)

The nlp check (`scripts/m03_nlp_check.sh`) is given the modules that `grep -l 'mark.nlp' tests/test_*.py` lists at C,
not `tests/`. The record `step14/rc-step14.json` carries that list, and holds:
- `a60.w24.nlp_tier_and_inventory` `pass`: the check over those modules exits 0, and the inventory `--check` exits 0
  for both workloads;
- `a60.w24.nlp_selection` `pass`: in the audited nlp environment, `pytest --collect-only -q -m nlp` lists the same set
  of node ids over those modules as over `tests/`. The set's size n is recorded and n ≥ 1. The run over the modules
  exits 0. The exit status of the collection over `tests/` is not judged, because modules that import packages the
  audited environment lacks (at 0.3.0 the three `tests/test_s10_*.py` that import `mpmath`) fail to import there.

0.3.0 measured n = 190 over 13 modules. That number is a record of 0.3.0, not a standing expectation (Q-6).

`a60.w24.m05_g10_real_replay` also carries `host_platform`, the runner's `platform.platform()`, and `record_platform`,
the `frozen.reactor.fingerprint.platform` of the committed REAL record's `S0` coupling record at C. When that record
cannot be read, `record_platform` is `null` and the check carries the reason. Neither field is judged, and the pass
rule is unchanged. The fields make §12's host-mismatch stop checkable.

### 6.6 Step 16 (R-903)

While W27 is not claimed, `step16/rc-step16.json` (step `w26-web-shell`) holds exactly four checks, each `pass`:
- (a) `a60.w26.m06_tests`: `OPENFLOWSHEET_REQUIRE_BROWSER=1 pytest -q -rs -p no:cacheprovider
  --junitxml=<rc>/step16/m06-tests.junit.xml tests/test_m06_*.py` exits 0, and the junit has 0 failures and 0 errors;
- (b) `a60.w26.web_unit_tests`: `node --test` exits 0;
- (c) `a60.w26.g15_registered_states`: (a)'s junit has 0 skipped, and each of these 25 testcases appears exactly once
  with no `failure`, `error` or `skipped` child:
  - from `tests.test_m06_w27_scorer`: `test_the_twenty_states_are_registered`, `test_candidate_states[W27-S11]` to
    `[W27-S16]`, and `test_harness_states[W27-S01]` to `[W27-S10]` and `[W27-S17]` to `[W27-S20]`;
  - from `tests.test_m06_w27_harness`: `test_a23_run_record` and `test_a79b_an_unpinned_attempt_through_the_harness`;
  - from `tests.test_m06_w27_coverage`: `test_s11_the_v2_snapshot_refuses_this_build` and
    `test_committed_coverage_json_is_g14_and_this_builds_classification`;
- (d) `a60.w26.w27_v1_refusal`: `python -m benchmarks.m06.w27.dryrun --out evidence/M06/W27/artifacts/dry-run/<C7>`
  (C's first seven hex digits) exits 1, its last non-empty output line is exactly
  `benchmarks.m06.w27.snapshot.SnapshotUnsupportedError: registry_snapshot: unsupported(provider 'iapws95-v1': no
  registered records and phases, W27-R63)` (one line, wrapped here), and `<out>/summary.json` does not exist.

(c) and (d) are judged on the local `ref-x86-64` run, where the pinned archive and `mcp` are present, not on CI. The
pinned W27 archive is supplied to the runner by `--w27-artifacts`; without it, (c) fails (amendment A-6, §17.1). The
refusal in (d) is the check's expected outcome, not an `unsupported` result. A dry run that exits 0, fails otherwise,
or writes a `summary.json` fails (d) and stops the RC (§12).

### 6.7 Step 17: the line's items

`scripts/release_rc.py` (WO-R6) runs each `rc_items` entry in order.
- **`local:<environment>` items** run `command` from the repository root at C. The environments are:
  - `project`: the repository's venv from C's `requirements.lock`;
  - `coolprop`: a venv with `requirements.lock`, then `requirements-coolprop.lock` with `--no-deps --require-hashes`,
    then the package with `--no-deps -e`;
  - `reactor`: built from C's lock, as step 12's;
  - `nlp`: the audited nlp environment that `scripts/m03_nlp_check.sh` uses;
  - `lca`: `scripts/build-lca-env.sh`.

  `python` as `argv[0]` is that environment's interpreter. An argv element `$NAME` is replaced by the runner's value
  for `C` (C's full id), `RC_OUT` (the RC output directory), `NLP_PREFIX` or `NLP_CACHE`. An unset name makes the item
  `unsupported`.
- **`ci:<job>` items** are that job of the `release_rc` dispatch at C. The item passes if and only if the job concluded
  `success` on every leg it runs on. Its artifacts are fetched into the item's directory.

**The record.** The wrapper writes `step17/rc-step17-<id>.json` (format `t08-rc-v1`, step `<id>`). It holds exactly
one check, whose id is `<id>`. The check is `pass` if and only if a local command exited 0, or a CI job succeeded on
every leg. The record carries the argv or the job name, the exit status or the conclusions, the SHA-256 of the
captured output, and the path and SHA-256 of any record the command wrote itself. An `unsupported` result is not a
pass. The RC record has one row per item under step 17.

**`S07-F8` (17b, R-906; D4.5).** CI's `rc-coolprop` job installs `requirements-coolprop.lock` after the main lock
(`--no-deps --require-hashes`), sets `OPENFLOWSHEET_REQUIRE_COOLPROP=1`, and runs every S07 and S11 test module that
imports CoolProp. The pytest exit status is 0. On x86-64 nothing is skipped. On aarch64 exactly one skip is allowed,
S07's `test_a31a_the_digests_own_machine_is_bitwise`, matched by its reason `A31a holds on x86_64 only; this machine
is aarch64 (A31b)`; `test_a31b_cross_architecture` passes on both legs. Any other skip, or that skip on x86-64, fails
the item. The local cross-check is dropped: the criterion is classed by architecture, not by machine (D4.5).

### 6.8 Step 18 and the acyclic order (R-913, R-914)

**R-914, standing.** A release manifest never judges the gate that reads it. An assertion whose condition is decided
by a step that reads the release manifest (the tag gate, its ADR item) is written in two parts: the manifest judges what
holds before that step, and the step's own output, recorded in the build log, judges the rest. An ADR whose acceptance
condition includes the release manifest being `tested` has a manifest check over its other conditions. That check
allows the status Proposed or Accepted, and a guard fails it when the ADR is marked Accepted while another check of the
manifest does not pass. It is marked Accepted after the manifest and before the gate. §9.2 is that order.

### 6.9 Records and the RC record

As alpha §8.3, with R7 1 and R8 1:
- small text records go under `evidence/<pkg>/<C>/rc/`, and large ones under `evidence/<pkg>/<C>/artifacts/` by hash.
  Records over 1 MB are committed gzip-compressed beside their paths;
- `rc/records.json` (format `m07a-rc-records-v1`) lists every cited record with its SHA-256, its size and whether it
  is committed;
- the RC record (`gate_set.rc_record`) names C once and has one per-step table `Step | Assertion | Where | Result (as
  the record says) | Record | sha256`, with at least one passed row per step of `rc_steps`, and one row per item under
  step 17. The `Result` cells use Ruling 3's status words.

### 6.10 CI: one run per commit, and the `release_rc` dispatch (D4)

- `ci.yml`'s `check` writes junit for pytest (`--junitxml`) and for node (`--test-reporter=junit`) on both legs and
  uploads them as `junit-<arch>` (D4.4).
- The dispatch input `release_rc` runs the RC jobs only: `rc-steps`, `rc-coolprop`, `rc-ensemble`, `dist`,
  `clean-install`, `bundle-set`, `bundle-replay`, and `ptc-r1` while the `PTC-R1` item stands (N-2). `check` gains
  `if: ${{ !(github.event_name == 'workflow_dispatch' && inputs.release_rc) }}`, so the dispatch never re-runs the
  suite (D4.2). The `release_rc` dispatch at C is the one with the greatest run id, at its latest attempt (amendment
  A-4, §17.1). The RC runner's `ci` and `items` refuse any other run, and the manifest reads exactly that dispatch and
  §6.2's push run and refuses any other. `rc-ensemble` carries step 6's aarch64 leg (0.3.0's RC record, row 6). ADR 0055 D4.2's list omits it
  (finding F-4). `release-audit` is D2's and is not added while D2 is deferred.
- `rc` and `rc_alpha` stay as they are, for the legacy lines.
- **Local runs at C** cover only what CI cannot run: steps 11, 12 and 14, the `local:` items (the reactor, nlp, lca
  and coolprop environments), step 15, step 16's (c) and (d), and the `ref-x86-64` legs of steps 2 and 6–10. Those legs
  are on a registered machine class that CI does not provide, and the alpha's steps name them ("three hosts"), so they
  are criteria, not duplicates.
- **The local full gate before a merge into `main` is kept** (`CLAUDE.md`; N-3's default stands). It runs in the
  background beside CI, and it is the only run of the archived-history tests (F-B of ADR 0055). Records-only commits
  after C get their CI push run automatically. Nothing else re-runs locally.
- `release.yml` is unchanged apart from §3.5's resolution. Its `gate` job runs no suite. The dry run stays.

## 7. Version, pin and working form (R-875, R-460, R-902, R-458)

### 7.1 At K3

- The version is written into the version-carrying files: `pyproject.toml`, `src/openflowsheet/__init__.py`, the two
  `project_summary` fixtures (`tests/fixtures/schemas/application_results/project_summary/*/*.json`) and
  `tests/test_m06_w27_coverage.py`. `README.md`'s status names the release (RELEASING "Per release" step 1).
- `benchmarks/t08/support_envelope.yaml` is pinned with `envelope_id: <gate_set.envelope_id>` and
  `release: <version>`. Its header comment gains one line in the pattern of the earlier ones.
- The records bound to a version or to the RC host are re-taken at K3, from a clean worktree at K3, on the host that
  runs steps 11, 14 and 15, and are committed together as J (§4.5). The clean worktree is a new one, made for the
  cut's re-takes by `git worktree add --detach <path> <K3>`. Before the first re-take starts, `git status --porcelain
  --ignored` in it prints nothing, and the build log records that check. A worktree that has held an earlier run, an
  install or a build is not clean, even when `git status --porcelain` prints nothing. Each re-take is written outside
  the repository and proved by a committed tool, and it replaces the committed files only after its proof prints
  `PASS`. The proofs' summary lines go into J's commit message and the build log.
  - The five in-process G10 records (TR-E2, TR-E2-FAR, TR-E2-FD, LOOP-R, LOOP-S), digest-only, proved with
    `scripts/m05_retake_diff.py --digest-only --old-version <the committed records' version> --old-host <h>` (R-458,
    R-1020), where h is the committed environment sidecars' `machine`. The proof must print `PASS` with `platform=0`
    and `other=0`.
  - M05's REAL record `benchmarks/m05/records/trust-region-study-real.*`, written by `scripts/m05_wo9_real.py
    --retake-into <dir>` in the audited nlp environment with `OMP_NUM_THREADS=1`. It is proved with
    `scripts/m05_retake_diff.py --digest-only <committed stem> <dir>/trust-region-study-real --old-platform <p>
    --old-host <h>`, where p is the committed `S0` coupling record's `frozen.reactor.fingerprint.platform`, and h is as
    above. The proof must print `PASS` with `version=0`, `other=0` and `environment` `equal` or `host`. Its `platform`
    count is the number of coupling records when the host's platform string differs from p, and 0 when it is equal
    (R-1008).
  - M01's IDAES conformance record `benchmarks/m01/idaes-conformance.json`, written by
    `benchmarks/m01/idaes_conformance.py --out <dir>/idaes-conformance.json` in the pinned IDAES environment. It is
    proved with `scripts/m01_idaes_retake_diff.py <committed> <dir>/idaes-conformance.json --old-platform <p>`, where p
    is the committed record's `environment.platform`. Only `environment.platform` and `inputs.*_sha256` members may
    differ, and each such input hash must be the SHA-256 of its file at K3 (R-1008).

  The reactor's environment fingerprint (M02 §2.4) holds `platform.platform()`, the kernel release included, and its
  digest is part of every experiment key (ADR 0036 D8). M05's REAL record therefore replays (step 14) only on the
  platform it was taken on. Step 11 compares the IDAES record's `environment` exactly (alpha spec §6.2 W22 (b)). A
  kernel upgrade on the RC host fails steps 11 and 14 until both records are re-taken on it. The reactor's fingerprint
  also holds the host's CPU model, the digest of its CPU flags and the pinned environment's absolute directory
  (`env_allowlist.NUMBA_CACHE_DIR`), and each attempt's cheap fingerprint holds the CPU model. Each M05 record's
  environment sidecar holds the host name, the CPU model and the CPU count. These, with the platform strings, are
  R-1020's host-identity leaves. `--old-host` admits exactly them, each from its committed value to the value the
  running host measures, together with the digests they feed under the one-to-one map. Every other leaf, every number
  included, stays bitwise equal. A move of the RC host to another machine is therefore a re-take at K3 like any other,
  and a re-take whose numbers move with the host stops the cut (§12). After the tag (§7.4), only the five are
  re-taken, because neither of the other two holds the version.
- W27's v1 `coverage.json` is not re-taken: the v1 snapshot refuses this build (§4.6).

### 7.2 A10's pairs

Each release appends its own two pin pairs to `test_a10_the_envelope_must_be_pinned_to_the_alpha`'s loop tuple,
after the earlier releases' pairs, before the pin. For 0.4.0:
`A10_PINS_0_4_0 = (("envelope_id: v0.4-envelope-1\n", "envelope_id: v0.2-envelope-dev\n"), ("release: 0.4.0\n",
"release: 0.2.0.dev0\n"))`. `tests/test_m07_v0_2_gate.py` gains the constant, and `test_a31_b_…` asserts that the tuple
equals `tagged + A10_PINS_0_2_0 + A10_PINS_0_3_0 + A10_PINS_0_4_0`. A pair that matches nothing is a no-op on the
working form.

### 7.3 The version is build provenance (R-902)

A version string identifies its release's D2.4 tree and nothing else (R-460). Every comparison between a committed
record and the live build treats the package version as build provenance, as it treats `git_commit`: it is excluded
from the equality, and rows, summaries and digests stay compared exactly (R-902; W27's `coverage.json` is the
registered case). If a default-gate test fails at K3 only because the version changed, the engineer stops (§12). The
remedy is a register-recorded ruling that classifies the field as provenance, never an edited expectation. Where the
version sits under a derived digest, so that excluding the clear field cannot remove it, the comparison is held at
equal versions by a registered control run, as R-910 did for V03.A12 (c).

### 7.4 After the tag (R-460, R-875)

The first D2.4 change after `v<version>` does three things:
- it sets the next minor's `.dev0` (after `0.4.0`, `0.5.0.dev0`), which sorts after every released version;
- it returns the envelope to the working form `v0.2-envelope-dev`, `release: 0.2.0.dev0`. That is R-563's fixed token,
  so it needs no A10 pair;
- it re-takes the five in-process G10 records (R-458), proved as §7.1 states, with `--old-host` (R-1020).

The next line's file is then written with `inherits` naming this line. A dev version implies the working envelope, and
a version in `RELEASED` must have that release's D2.4 tree (`tests/test_v02_main_version.py`). `release.yml` refuses a
`.devN` version.

### 7.5 Post-releases (R-922)

`X.Y.Z.postN` (N ≥ 1, canonical, not of a pre-release) is gated as a post-release of the released `X.Y.Z`, by the same
gate set and the same C, under R-922's tree rule. Its verdicts and acceptances are not redone. The generic gate admits
it as the legacy gates do (`ReleaseLine.post_releases`). RP changes nothing in R-922.

## 8. Standing acceptances (D3)

### 8.1 The table

`release/acceptances.md` replaces the per-release ADR's two tables (R-918). The gate reads it as it read ADR 0042's
and ADR 0053's: exactly one table with a `Frank's acceptance` column (failure clauses, first cell a clause) and
exactly one with a `Frank's answer` column (decision items, first cell the item). Each is read by column, and each
answer cell by the R-466 cell rule. Each table also has the columns `Scope`, `Fingerprint` and `Accepted at`:
- `Scope` is the text between the cell's outer backticks, read as written. It is never passed through the cell rule's
  `_bare`, which deletes `*` and would turn `benchmarks/s03/**` into a glob that matches nothing;
- `Fingerprint` is 64 lower-case hex digits (§8.2, F1);
- `Accepted at` is the 40-hex commit at which the fingerprint was taken.

The decisions table may hold rows for items that a line's `frank_items` does not name. The gate ignores those, as the
engine does today. Every item in `frank_items` needs exactly one row (RP.L10).

The seed is ADR 0053's six cells verbatim, with `Accepted at` = `a3e508e35fc5451fe56fa7b70941621992d35b50` (D3.6,
R-919), and N-7's row: Frank's acceptance of the coolprop and lca licence decisions (R-624, R-900) on 2026-10-30,
recorded verbatim in V03 spec §11 (N-11). It is one row, as the brief names it (Q-11).

### 8.2 Scope terms and fingerprints (exact)

A scope is one or more terms joined by ` + ` (space, plus, space). Each term has a hash h, written as 64 lower-case hex
digits, or is `unsupported` with a reason. Terms are evaluated at a commit X, which is C for a check and
`Accepted at` for a seed.

**Canonical JSON.** `json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` encoded as UTF-8, after
every list in v, at every depth, is sorted by the UTF-8 bytes of its elements' own canonical JSON (D2.2's rule).

**`paths:<g1>,<g2>,…`** (comma-separated globs, no spaces):
- (P1) The glob grammar: `**` matches any sequence of characters, `/` included. `*` matches any sequence without `/`.
  `?` matches one character other than `/`. Every other character matches itself. A glob matches a path if it matches
  the whole repository-relative path.
- (P2) The entries are those of `git ls-tree -r -z --full-tree X`, one `<mode> SP <type> SP <object> TAB <path>`
  record per tracked file, NUL-terminated. A term selects every entry whose path some glob matches. An entry that two
  globs match is selected once.
- (P3) Each glob must match at least one entry at X. Otherwise the term is `unsupported(paths:<glob> matches no
  tracked file at <X>)`. A scope therefore can never fingerprint an empty selection: deleting every file a glob named
  lapses the row and does not freeze it.
- (P4) h = SHA-256 of the selected records, each written `<mode> <type> <object>\t<path>\n` in UTF-8, sorted by their
  UTF-8 bytes and concatenated. This covers mode, type, blob and path, so additions and deletions count.

The selection is explicit because ADR 0055 D3.2's literal command, `git ls-tree -r <commit> -- <globs>`, does no glob
matching. Measured with git 2.47.3 at `a3e508e3`: `-- 'benchmarks/s03/**'` prints 0 bytes, `-- benchmarks/s03` prints
61 entries, and `:(glob)` magic is refused ("pathspec magic not supported by this command"). Read literally, six of
the seven seeded scopes would hash the empty string forever and never lapse (finding F-2).

**`extract:<name>`.** h = SHA-256 of the canonical JSON of the extractor's value. The extractors are exactly these:
- (E1) `claim_set`: `{"claimed": [...], "not_claimed": [...]}` from the line file that the gate is judging, read in
  the candidate's tree. For the seed at `a3e508e3`, which has no line file, the value is read from
  `release/lines/0.3.json`, whose `gate_set` equals that commit's `GATE_SETS[0]` (REL.A02);
- (E2) `pyproject_extra:<extra>`: the list `project.optional-dependencies.<extra>` of `pyproject.toml` at X, parsed by
  `tomllib`. It is `unsupported` if the extra is absent. It does not depend on `project.version` (REL.A10);
- (E3) `links`: the second argument (`register`) of each `Link(...)` call in the `LINKS` assignment of
  `scripts/m07a_rc.py` at X, read with `ast` and never imported. It is `unsupported` if there is no `LINKS`, or if an
  element is not a `Link` call with a string literal there;
- (E4) `served_digest`: the `found` member of the chain entry with `item` 1 in every step-8 record (format `t08-rc-v1`,
  step `surface-alpha`) that `evidence/<pkg>/<X>/rc/records.json` lists in the candidate's tree. All of them must be
  equal, and the value is that string. It is `unsupported` if there is no such record or the records differ.

**`gate_row:<g>`** is reserved for D2 (Φ(g) at X). While D2 is deferred it is always `unsupported(gate_row needs the
evidence fingerprint, ADR 0055 D2, deferred)`. No seeded row uses it.

**The row's fingerprint** (F1) is the SHA-256 of the ASCII bytes of the term hashes, written in the scope's order and
joined by `\n` (no trailing newline). A row with any `unsupported` term has an `unsupported` fingerprint, which never
equals a recorded one.

**Sanity values at `a3e508e3`** (the seed; `release/acceptances.md` lists every term hash):

| Row | Fingerprint |
| --- | --- |
| V14 (b) | `7506c9086342b8bbe038f9aef651d18e98d3268305937f3c52f4ac999a6f7a77` |
| X31 (c) | `59503316001e10b9c3760e41271d5be31f515cdd99a6581fe6f6e87276611864` |
| Claim set | `f4a3cfbee85d5c3d6fff6df5c1224e6d68fff7a14d88ff59e4017cb77990a881` |
| V17 carry | `367fdf465f7793d9c4224da4617130993a05d1f029b749b593d2f97d6c2d98f6` |
| M02 N1 | `c1b16371d5bd35a668e8ae3b11194ab41459cbf6ce165662dfdbd0015fff9cf4` |
| M03 N1 | `8eafbfef5ec2f333e341659182d4d824852c11b6bc4532914a9879715956a430` |
| coolprop and lca licences | `0bb1c6342c455070cc02bf754274efb4d7fcf8f9180bafefcdbd7783e78b2ce7` |

An independent recomputation with shell tools gives the same values for M02 N1, X31 (c) and V17 carry. For example:

```sh
C=a3e508e35fc5451fe56fa7b70941621992d35b50
h=$(git ls-tree -r --full-tree $C | grep -P '\tsrc/openflowsheet/adapters/external/' | LC_ALL=C sort | sha256sum)
printf %s "${h%% *}" | sha256sum      # c1b16371…9cf4, M02 N1's fingerprint (term hash 1027b7c1…8811)
a=$(printf %s '["R-192","R-234","R-295"]' | sha256sum); b=$(printf %s '"455d01eb…e125"' | sha256sum)
printf '%s\n%s' "${a%% *}" "${b%% *}" | sha256sum   # 367fdf46…98f6 with the full digest in place of 455d01eb…e125
```

Controls measured with the reference implementation:
- an unmatched glob is refused (P3);
- the V14 (b) term differs between `a3e508e3` and `main` = `1fcdbb1b`, because `src/` changed. That is a positive
  control: the hash is not a constant;
- the other four `paths:` terms, the three `pyproject_extra` terms and `links` are equal at the two commits.

### 8.3 The standing rule

A row **stands** at C if and only if:
- (a) its answer cell passes the cell rule, starting `accepted, YYYY-MM-DD`;
- (b) its scope, evaluated at C (§8.2), has a fingerprint equal to `Fingerprint`;
- (c) for a failure-clause row, its gate's row at C fails on a set of clauses that is a subset of the clauses with
  standing rows;
- (d) its scope, evaluated at `Accepted at`, has a fingerprint equal to `Fingerprint` (amendment A-2, §17.1). If it
  does not, the row is `unsupported (not reproduced at <Accepted at>)` and counts as absent, whatever (b) gives.

A row that fails (b) is **lapsed**. It counts as absent, and the gate's report names the differing terms. For a
`paths:` term the report also names the differing paths, and for an `unsupported` term its reason. A clause that fails
at C with no standing row gives NO (`not accepted`). So a new failure always needs Frank's dated answer. A changed
claim set lapses `Claim set`, so a new claim always needs it too. A row for a clause that no longer fails is reported
`not used` and is inert. Each `frank_items` entry needs a standing row, or the gate gives NO for it.

### 8.4 Dates and replacement

- A standing row's date may precede the verdict's `Judged` date. Its fingerprint does the work the date did (D3.4).
- A **new or replacing** row carries the fingerprint and commit at the C it answers, and is dated:
  - for a failure clause, on or after the verdict's `Judged` date. With a re-judgement, Table T7's bound also applies
    (R-371);
  - for a decision item, on or after the date of the lapse report that showed the lapse at C (§8.5).
- A replaced row moves, unedited, to the history list at the end of `release/acceptances.md`, with the date and the C
  at which it lapsed. Nothing else edits a row. Answer cells are Frank's words, verbatim.

### 8.5 The lapse report, the gate's report, and Frank's message

- **The lapse report.** After the RC records are committed and before the verdict, the build lane runs
  `scripts/release_gate.py --line <l> --rc <C> --lapses` (WO-R3). It writes one line per row of `release/acceptances.md`
  whose item or clause the line can use: `stands`, `lapsed (<terms>)` or `unsupported (<reason>)`. Its first line is
  `acceptance lapses at C = <C>, <YYYY-MM-DD>`, the run date in UTC. It is committed as
  `evidence/<pkg>/<C>/acceptance-lapses.txt`. That first line's date is D3.4's report date (Q-8). ADR 0055 calls this
  the carry report. With D2 deferred, no carry report exists, and this is its acceptance half (finding F-6).
- **The gate's report** lists every standing row it used, as
  `standing acceptance <item>: accepted <date> at <commit>, scope unchanged`, and every lapsed row with its reason.
- **Frank's messages** are in plain words, batched, and at most two per release. The first, before the verdict,
  asks for the lapsed decision items and any claim-set change, so that no row is `BLOCKED` on them (D3.4). The second,
  after `Judged`, asks for every failing clause without a standing row, lapsed ones included. A failure-clause row must
  be dated on or after `Judged` (§8.4), so it cannot be asked earlier. At 0.4.0 this puts V14 (b) in the second
  message (finding F-8). When either message would be empty it is not sent. Money is asked in the first message if any
  is needed. The standing rows listed in the gate's report and in the notes are enough at dispatch (N-6's default
  stands).

## 9. ADRs and the release manifest

### 9.1 ADR acceptance route

Item 12 requires every `required_adrs` entry to be Accepted at the candidate. An ADR that is still Proposed at K3 is
marked Accepted by the build lane only on its own stated condition. The build lane checks each condition against the
files cited, records one check per ADR in the release manifest, and then edits the status line to `**Accepted,
<date>**`, citing the evidence and "marked by the build lane". An unmet condition is a stop (§12), not a choice. An
ADR whose condition includes the release manifest is handled as R-914 states (§6.8).

### 9.2 The order after C

Each step reads only what an earlier step wrote:
1. The RC records, the RC record, `rc/records.json` and `release/rc-trees/<C>.json` are committed.
2. The lapse report (§8.5) is committed. Frank is asked once for the lapsed decision items and any claim-set change.
   His answers become rows dated on or after the report.
3. The `verdict` agent writes the verdict document. The build lane writes the ledger from it. Frank is asked for any
   new failing clause, and his answers become rows dated on or after `Judged`.
4. The release manifest is generated `tested` at a clean commit G. It judges every standing assertion (§11) except the
   parts that step 18 decides, and every manifest-conditioned ADR on its other conditions (§6.8). It is committed
   alone, as H1.
5. ADRs conditioned on the manifest are marked Accepted on it (H2). If there are none, H2 = H1.
6. Step 18 runs at H2: `PYTHONPATH=src .venv/bin/python scripts/release_gate.py --line <l> --rc <C>`, with the
   candidate at HEAD = H2. It must exit 0, and its last line must be exactly `v<version> tag may be proposed: YES`.
   Its output goes to `evidence/<pkg>/<C>/artifacts/step18-H2.log`, which git ignores.
7. The build log `docs/<pkg>_RC_DECISIONS.md` records H2, the command, the exit status, the log's SHA-256, the last
   line and RP.S08's grammar summary (commit H3). H3 touches only the build log and `docs/progress.md`, so step 6's YES
   holds at H3. The manifest is not regenerated. If a stop forces a regeneration, steps 4–7 are repeated after it, and
   the build log says why.
8. The dry run, then Frank's dispatch, with `rc` = C. The tag, the dispatch and the PyPI approval are Frank's (ADR 0021
   D5).

## 10. Release notes

`CHANGELOG.md`'s `## v<version>` section has a "What it is not" list. It holds:
- every phrase of the line's `changelog_what_it_is_not`, verbatim, each exactly once;
- one line per accepted failure clause in force at C, generated from the standing rows the gate used:
  `- <clause> FAIL, accepted by Frank <YYYY-MM-DD> (release/acceptances.md)`, with the row's acceptance date (D3.5).

The section also lists what each package new since the previous release added, with its manifest. The gate's
`--markdown` table (alpha §7.5) gives the per-gate verdicts.

## 11. Standing assertions (RP.S01–RP.S22)

`scripts/release_evidence_manifest.py` (WO-R6) decides these for every release, plus one check per `rc_items` entry.
Gate column: **D** is the default gate, **R** is the RC records at C, and **CI** is the push run at C. Every assertion
compares strings, bytes, sets, counts or exit codes. None introduces a tolerance. RP.S15 cites the registered
architecture classes of the default gate's own tests, unchanged. "0.3.0" names the counterpart in S13's manifest and
whether the standing form equals it (§11.2).

### 11.1 Catalogue

- **RP.S01** (D). The line file passes RP.L01–RP.L11, and `scripts/release_gate.py`'s loader refuses each RP.L
  control. 0.3.0: V03.A01. Changed form.
- **RP.S02** (D). `gate_set_of` over the line's version table T-V(M.m). Covered: `M.m.0`, `M.m.0b1`, `M.m.0rc1`,
  `M.m.0rc12`. Not covered: `M.m.0a1`, `M.m.0b0`, `M.m.0rc0`, `M.m.0rc01`, `M.m.0.dev0`, `M.m.0.post1`, `M.m.1`,
  `M.m`, `M.m0.0`, `(M+1).m.0`, `M.m.0 ` (trailing space), and, for m ≥ 1, `M.(m-1).0` and `M.(m-1).0rc1`. Each
  number is written in decimal (`M.m0.0` for 0.3 is `0.30.0`). A post-release form is admitted only by R-922's separate
  rule (§7.5), never by `covers`. For 0.3 the table is Table T-V3 exactly, 4 covered and 13 not, and the 0.3 and 0.4
  `covers` patterns classify their tables correctly (measured 2026-11-06). 0.3.0: V03.A02. Same form.
- **RP.S03** (D). The legacy lines are unchanged: their tests pass with node ids unchanged (REL.A04), and their entries
  equal their registrations. 0.3.0: V03.A03. Same form.
- **RP.S04** (D). `test_a10_…`'s loop tuple is `tagged` plus every release's pin pairs in release order (§7.2). A
  control with two pairs swapped fails `test_a31_b_…`. 0.3.0: V03.A04. Same form.
- **RP.S05** (D). The clause grammar: under the line's `clause`, `g (a)` parses for every claimed g, while `g (a)` for
  every not-claimed g and `<first claimed> (A)` do not. Under the inherited line's grammar, `g (a)` does not parse for
  any g claimed only by this line. 0.3.0: V03.A05. Changed form (generated from the line, not a fixed list).
- **RP.S06** (D). Decision items 1–12 with the line's values: one YES fixture, and for each item one NO fixture that
  flips only it, each with its reason. Item 13 (D2) does not exist while D2 is deferred. 0.3.0: V03.A06. Same form.
- **RP.S07** (D). The standing acceptances (REL.A06–A10). A failing clause without a standing row gives NO; with a
  standing row, YES; with a lapsed row, NO; with a row re-dated per §8.4, YES; dated one day early, NO. A verdict
  document with a row for a not-claimed gate exits 2. 0.3.0: V03.A07. Changed form.
- **RP.S08** (D, R). The gate's output grammar. The first line is `<line name> gates (<gate set>) at C = <C>;
  candidate <ref>`. One row per gate follows, the claimed in order and then each not-claimed gate as `not claimed
  (<gate set>)`. The last line is `v<version> tag may be proposed: YES` or `… NO (k reasons)`. D: the gate's tests,
  which the manifest judges. R: step 18's own output, recorded in the build log, which the manifest does not judge
  (R-914). 0.3.0: V03.A08. Same form.
- **RP.S09** (R). At K3 and C, the version-carrying files read the version, and the envelope reads
  `<envelope_id>`/`<version>` (§7.1). 0.3.0: V03.A09. Same form.
- **RP.S10** (R). `CHANGELOG.md`'s `## v<version>` holds each registered phrase verbatim, once, and one line per
  accepted failure clause in force, in §10's form. 0.3.0: V03.A16 and A18. Changed form (the failure lines are new,
  D3.5).
- **RP.S11** (R). Every step of `rc_steps` other than 15 and 17 passes at C, and the RC record has a passed row for
  each step of `rc_steps`. 0.3.0: V03.A20. Same form.
- **RP.S12** (R). Step 15: J's journey record is in C, `--carry-journey J --rc C` reports carried, and `check` and
  `replay` (bitwise) pass at C. 0.3.0: V03.A21. Same form.
- **RP.S13** (R). Every `rc_items` entry passes at C (§6.7). An `unsupported` result is not a pass. 0.3.0: V03.A22.
  Changed form (one record per item).
- **RP.S14** (R). Step 8: with `LINKS` at C written c_1 … c_n in its order, the served digest equals D_n, the last
  link's registered digest, and the chain's rows are exactly `(1,c_n)`, `(2,c_n)`, `(2,c_{n−1})`, …, `(2,c_1)`,
  `(3,None)`, each passing (§4.4, amendment A-12). Otherwise the RC stops. 0.3.0: V03.A23. Same form.
- **RP.S15** (CI). Step 1's record (§6.2) passes: the push run at C is green on both legs, and junit is present. The
  step-1 row records the class ratios that the default gate's tests print (S07 A31, R-627; S11 thermal, R-843, R-845).
  0.3.0: V03.A24. Changed form (the push run, not a dispatch's `check`; REL.A17).
- **RP.S16** (R). Item 12 in two parts. (a) The manifest: the gate's `adr_problems` at the commit the generator runs at
  returns no problem other than "ADR <n> is not Accepted" for a manifest-conditioned ADR whose status line starts
  `Status: Proposed`. (b) Step 18: every required ADR Accepted, shown by its YES line in the build log. 0.3.0: V03.A25.
  Same form.
- **RP.S17** (R). The verdict document (§4.7): the header names C once and has one `Judged` line; there is one row per
  claimed gate, in order; every clause parses. `release/acceptances.md` passes the cell rule and the standing rule
  (§8.3). The ledger's verdicts are written from the verdict document. 0.3.0: V03.A26. Changed form (standing table).
- **RP.S18** (R). The release manifest, in two parts. (a) As its own check: `tested`, listing RP.S01–RP.S22 and the
  item checks with commands run. That is, every other check passes and commands were run. (b) At §9.2 step 6: step
  18's last line is YES, recorded in the build log with the log's SHA-256. 0.3.0: V03.A27. Changed form (its rule (a)
  quantifies over the catalogue, whose changed-form members cannot pass on 0.3.0's records; amendment A-1, §17.1).
- **RP.S19** (R). Step 16 as §6.6 states it, while W27 is not claimed: 4 of 4 checks pass; the 25 nodes; exit 1 and
  the exact line. 0.3.0: V03.A32. Same form.
- **RP.S20** (R). Step 14's selection as §6.5 states it: equal sets, and n ≥ 1 recorded. 0.3.0: V03.A33. Changed form
  (0.3.0 required n = 190).
- **RP.S21** (R). Step 12's experiment record as §6.4 states it: exactly one check, `r375.audit`, with the line.
  0.3.0: V03.A34. Changed form (0.3.0's record had the re-run checks (a) and (b)).
- **RP.S22** (D). `HARVEST_EXCLUDED` holds `evidence/<pkg>/` for the release being cut (§5.2). C's tree holds no file
  under it, every excluded manifest is `evidence/<pkg>/<40 hex>/manifest.json`, and a manifest of a package whose id
  merely starts with `<pkg>` is still harvested. 0.3.0: the test of V03 §10.5 item 3. Same form.

**Falsifiability.** Each D assertion has a control that flips one input (RP.S04's swap, RP.S05's negatives, RP.S06's
twelve NO fixtures, RP.S07's dates and lapses, RP.S22's prefix). So a constant answer cannot meet it. RP.S19 (c) names
its nodes and requires 0 skipped, and (d) passes only on the registered refusal. RP.S20's n ≥ 1 excludes an empty
selection that compares equal to an empty collection. RP.S21's counts exclude an empty audit.

### 11.2 REL.A20's comparison

REL.A20 runs `release_evidence_manifest.py` over 0.3.0's committed records and requires each standing assertion to
have S13's status. That is defined only where the standing form equals 0.3.0's. So:
- RP.S02–S04, S06, S08, S09, S11, S12, S14, S16, S19 and S22 ("same form") must each have exactly the status that
  S13's manifest gives its counterpart (`pass` for every one);
- RP.S01, S05, S07, S10, S13, S15, S17, S18, S20 and S21 ("changed form") are excluded from REL.A20's equality. Each is
  decided on 0.3.0's records anyway, and the manifest records its status and the reason for the exclusion. Its own
  acceptance is elsewhere: RP.S01 by RP.L01–L10 and REL.A01–A02; RP.S05 by RP.L09; RP.S07 by REL.A06–A10; RP.S15 by
  REL.A17; RP.S10, S13, S17, S20 and S21 by their fixtures in WO-R6's tests (a record that meets the standing form,
  and one control per changed rule); RP.S18 by the generator's fixtures (every other check passes, giving `pass`; one
  check fails, giving `fail`; zero commands, giving `fail`);
- RP.S18 keeps the part that can be compared (amendment A-1, §17.1): over 0.3.0's records, REL.A20 also requires that
  RP.S18's `not_pass` is a subset of the changed-form assertions, and that commands were run.

The exclusion narrows no denominator: an assertion whose expected form changed has no S13 status to equal. It is named
here, so that it cannot be dropped quietly (finding F-7).

## 12. Stops (the engineer reports and does not choose)

The engineer stops on any of these. Nothing is edited, re-run or re-taken to pass. The records are committed as they
are, and the reasons are reported:
- RP.L01–RP.L11 fail for the line file at K3 or at C.
- RP.S14 fails (step 8's digest or chain).
- Step 9's import workload fails on a module that the registration does not name.
- A default-gate test fails at K3 only because of the version string (§7.3).
- An ADR condition in §9.1 is unmet.
- The journey's R1 needs more than its registered budget.
- Any step's or item's result reads `unsupported`. Step 16 (d)'s registered refusal is its expected outcome, not an
  `unsupported` result.
- Step 16 (d) sees anything but the registered refusal: an exit 0, another error, or a `summary.json`.
- Step 12's audit (`r375.audit`) fails, or the keeping wrapper differs from its last recorded form without its diff in
  the build log.
- §9.2 step 4's manifest is not `tested`. Then no ADR is marked Accepted, and step 18 is not run for YES.
- Step 18 at §9.2 step 6 ends in anything but YES, or H2 to H3 touches a file other than the build log and
  `docs/progress.md`.
- A §7.1 re-take proof does not print `PASS`. The re-take is not committed, and the cut stops before J.
- Step 11, 14 or 15 fails at C while the host's platform differs from the compared record's: step 11's
  `differing_members` holds `environment.platform`, or a step 14 or 15 check's `host_platform` differs from its
  `record_platform`. C's records are committed as they are. The remedy is a new J from the same K3 on this host (§7.1's
  re-takes and the journey) and a new C. A comparison or replay that sets the platform aside is never the remedy
  (R-1008).
- (P6) does not hold at K3: the RC host is not a member of `ref-x86-64`. The cut stops before J (R-1020).

A lapsed acceptance is not a stop. It is reported in the lapse report and asked in Frank's message (§8.5).

## 13. Lanes and Frank's attention per release (D5, R-921)

- **Build lane:** the line-file fields `covers`, `envelope_id`, `packages`, `required_adrs`, `evidence_package` and the
  document paths; the RC jobs and records; the lapse report; the manifest; `CHANGELOG.md`; the RELEASING block. D5's
  "`version`/`covers`" is `covers`: the line file has no separate version field.
- **Design lane, at most three passes per release:**
  - (1) a `specifier` pass, only if the claim set, a gate's criteria (an RP amendment), an `rc_items` entry or the
    phrases change. These fields are design-lane fields. A build-lane edit to `claimed`, `clause`,
    `changelog_what_it_is_not` or `rc_items` without a `specifier` pass is R-921's watch item;
  - (2) one `verdict` pass over all claimed gates. With D2 deferred, every row is judged;
  - (3) one `reviewer` pass, only if the release changes release machinery (`scripts/release_*.py`, RP).
- **Frank:** at most two batched messages in plain words (§8.5). The tag, the dispatch and the PyPI approval stay
  his.

## 14. Coverage table (REL.A18)

One row per register entry that RP writes into a step, with the RP section that holds it. REL.A18 requires the first
ten rows. A section cell lists one or more `§n` or `§n.m` references, and each must name a heading of this document
that exists.

| Register id | What it governs here | RP section |
| --- | --- | --- |
| R-460 | after a tag: `.dev0`, working envelope, a version names only its release's tree | §7.4, §7.3 |
| R-875 | the pin `v<M>.<m>-envelope-1`, the token after the tag, each release's two A10 pairs | §7.1, §7.2, §7.4 |
| R-902 | a version string is build provenance in every committed-versus-live comparison | §7.3 |
| R-903 | W26 (a) as a function of whether W27 is claimed; the dry run's refusal asserted exactly | §4.6, §6.6 |
| R-906 | `S07-F8`'s one aarch64 skip, by reason, and none on x86-64 | §6.7 |
| R-907 | step 14's nlp selection over the `mark.nlp` modules; no node lost | §6.5 |
| R-909 | step 12 keeps G11's results in its first run and audits them against its own runs file | §6.4 |
| R-911 | the release manifest is excluded from its release's harvest | §5.2 |
| R-913 | the order after C: manifest, then ADRs, then step 18, then the build log | §9.2 |
| R-914 | a release manifest never judges the gate that reads it; split assertions; the guard | §6.8, §9.2 |
| R-915 | one standing procedure, one line file per line, no per-release spec or script | §1, §3.7 |
| R-918 | acceptances stand by scope fingerprint; lapse; re-dating | §8.3, §8.4 |
| R-919 | the seeded table at `a3e508e3`; V14 (b) asked once more at 0.4.0 | §8.1 |
| R-920 | one CI run per commit; step 1 is the push run; `release_rc`; the local merge gate kept | §6.2, §6.10 |
| R-921 | who writes which line-file field; at most three design-lane passes | §13 |
| R-922 | post-releases | §7.5 |
| R-151 | the tree record `release/rc-trees/<C>.json` | §5.1 |
| R-376 | step 1's skips recorded and audited | §6.2 |
| R-458 | the G10 re-take at K3 and after the tag | §7.1, §7.4 |
| R-476 | the verdict-document tests skip at C while it is absent | §6.2 |
| R-478 | step 9's workload and the registered nlp-extra modules | §6.1 |
| R-480 | G11's `--d78` extract, without `--previous-runs` | §6.4 |
| R-1008 | records bound to the RC host re-taken at K3 on that host and committed in J; their proofs; the host-mismatch stop | §7.1, §4.5, §5.1, §12 |
| R-1020 | a move of the RC host: host-identity leaves admitted by `--old-host` in §7.1's proofs; the RC host a member of `ref-x86-64` before K3 | §7.1, §7.4, §5.3, §12 |

R-916 and R-917 (D2) are not covered: they are deferred, and §8.2 reserves `gate_row:` for them.

## 15. Open questions, each with a default

Work proceeds on each default. Each is cheap to revisit.

- **Q-1 (needs the design lane, an ADR note): gate resolution with `release/lines/0.3.json` present.** Default: §3.5's
  `role` field. Alternative: resolve the legacy script first, then the line file. That also satisfies REL.A05, but it
  inverts D1.3's stated order.
- **Q-2 (preference): is `changed` exact in both directions?** Default: yes, a listed field that is equal is refused
  (RP.L04). Alternative: warn only.
- **Q-3 (preference): D1.2's top-level `evidence_package`.** Default: the `gate_set` field, not repeated.
- **Q-4 (preference): who writes an item's record?** Default: the wrapper, with one check per item (§6.7), which
  reconciles D1.2 ("writes a record") with D1.3 ("a wrapper that runs each command into a record").
- **Q-5 (preference): `rc_items[*].where`, to allow CI items.** Default: yes, as D4.5 makes 17b a CI job.
- **Q-6 (preference): step 14's count.** Default: n ≥ 1, recorded. Alternative: the line file registers n, and a
  change is a line edit.
- **Q-7 (fact, already settled by R-909 item 3): step 12's standing record.** Default: one check, `r375.audit`.
- **Q-8 (preference): the lapse report's form and place** (§8.5). Default: as stated, written by WO-R3.
- **Q-9 (preference): commit the design lane's reference implementation of §8.2?** Default: no. The brief allows no
  code, so WO-R3's implementation and REL.A19 are the executable check, and the per-term hashes in
  `release/acceptances.md` are the independent expectation. Alternative: commit it as
  `release/tools/scope_fingerprint_ref.py` with `--check`.
- **Q-10 (preference): are extractor lists sorted?** Default: yes, D2.2's rule, so a reorder that changes nothing does
  not lapse a row. A reorder of `claimed` is still a `changed` field (§3.2).
- **Q-11 (Frank's preference): the licence row as one row or two.** Default: one row (the brief, N-7). Alternative: one
  row per extra, so that a change to the lca lock asks only about lca.
- **Q-12 (needs the design lane): `0055` in 0.4's `required_adrs`.** Default: yes. Its acceptance condition must first
  be restated for D2's deferral (finding F-3). Otherwise item 12 refuses at 0.4.0.
- **Q-13 (needs a fact, WO-R4's dispatch): `PTC-R1` as an item.** Default: kept if it finishes within 360 minutes on
  both legs. Either way, V14 (b)'s scope is the path fallback until D2.
- **Q-14 (preference): phrase 15's version.** Default: `no W27 claim in 0.4.0`.
- **Q-15 (preference): R(g) check patterns with a trailing `*`.** Default: allowed, because 0.3.0's Basis cites steps,
  not check ids.

Nothing here needs Frank before 0.4.0's cut except Q-11, which has a default, and the answers that §8.5 asks for at
the cut.

## 16. Findings against ADR 0055 (for the design lane; not acted on here)

- **F-1 (D1.3 and REL.A05).** "If the line file exists, run the generic gate", together with the mandated
  `release/lines/0.3.json`, sends 0.3.0 and its post-releases to the generic gate. REL.A05 and REL.A04 expect the
  legacy script. RP §3.5 resolves this with `role`. An ADR note should say so.
- **F-2 (D3.2).** `git ls-tree -r <commit> -- <globs>` does no glob matching (git 2.47.3: 0 bytes for
  `benchmarks/s03/**`), and the engine's `_bare` deletes `*`. Six of the seven seeded scopes would hash a constant and
  never lapse. RP §8.2 defines the selection and refuses an empty glob (P3). An ADR note should cite §8.2.
- **F-3 (Status).** ADR 0055 becomes Accepted when REL.A01–A21 hold. With D2 deferred, REL.A11–A16 and A21 belong to
  WO-R5. The condition needs restating before 0.4.0 if `0055` is required (Q-12).
- **F-4 (D4.2).** The `release_rc` job list omits `rc-ensemble`, which carried step 6's aarch64 leg at 0.3.0. RP §6.10
  includes it. WO-R4 should add it.
- **F-5 (D1.2 and D1.3).** These disagree on who writes an item's record. RP §6.7: the wrapper does.
- **F-6 (D3.4).** A decision item's date is bound to "the committed carry report", which is a D2 artefact. RP §8.5
  binds it to the lapse report.
- **F-7 (REL.A20).** "Each standing assertion has S13's status" is undefined for assertions whose form changed. RP
  §11.2 defines the comparison.
- **F-8 (§6 item 5 and D3.4).** §6 item 5 asks Frank for V14 (b) before the verdict. D3.4 requires a failure-clause row
  to be dated on or after `Judged`. RP follows D3.4: V14 (b) is in the message after `Judged` (§8.5).

## 17. Amendments

An amendment is a new section here, recorded in the register, that states what changes, why, the affected
sections and assertions, and the evidence. It updates §14 when it moves a register entry. D2's adoption will be one
(Φ, the carry, item 13, `gate_row:`, `release-audit`, `strace`).

### 17.1 Amendments A-1 to A-8 (RP review, 2026-11-06; R-942 to R-949)

The design lane's review of WO-R2–R4 and WO-R6 (`docs/reviews/RP-review.md`, "§17 amendment block") states these
amendments. They are pasted verbatim. Each has its register line: A-1 is R-942, A-2 R-943, A-3 R-944, A-4 R-945, A-5
R-946, A-6 R-947, A-7 R-948 and A-8 R-949. The sections each amends carry the change and point here. The evidence is
the review's (M-1, M-2, S-1 to S-5, S-7, rulings 3 to 7) and WO-R7's tests (`docs/RP_DECISIONS.md`, C-23 on).

- **A-1 (§11.2, REL.A20; Q-C5).** Move RP.S18 from the same-form list to the changed-form list. REL.A20 also
  requires, over 0.3.0's records, that RP.S18's `not_pass` is a subset of the changed-form assertions, and that
  commands were run. RP.S18's own acceptance is the generator's fixtures: every other check passes, giving `pass`;
  one check fails, giving `fail`; zero commands, giving `fail`.
- **A-2 (§8.3; Q-B4).** Add a condition (d). The scope, evaluated at `Accepted at`, has a fingerprint equal to
  `Fingerprint`. If it does not, the row is `unsupported (not reproduced at <Accepted at>)` and counts as absent.
- **A-3 (§5.1).** The line file and its inherited chain are byte-equal at C and at the candidate. The gate refuses
  with exit 2 otherwise, and a change after C needs a new C.
- **A-4 (§6.2, §6.10).** C is pushed on its own, as the head of a branch ref (`git push origin <C>:refs/heads/rc/<C7>`
  if it would otherwise be pushed beneath later commits). The `release_rc` dispatch at C is the one with the greatest
  run id, at its latest attempt. Step 1's record lists every `ci.yml` run at C with its event, attempt and conclusion.
  The manifest reads exactly those two runs and refuses any other.
- **A-5 (§6.4; Q-C3).** Step 12's archived inputs are `benchmarks/m02/g10-adapter-halves-v3.json` and
  `g11-coverage-v3.json` at `bd446abab1bcc26b286ae4a287d1de131d87ceac`, registered by their SHA-256. A failed read, or
  a hash that differs, stops the RC (§12).
- **A-6 (§6.6; Q-C4).** The pinned W27 archive is supplied to the runner by `--w27-artifacts`. Without it, (c) fails.
- **A-7 (§3.1, D1.5; Q-C6).** The release package id is admitted by the schema ADR of ruling 4. RP's own package
  manifest is filed as `S15`.
- **A-8 (status).** These are notes, not changes. RP.L08 now passes: `scripts/wheel_data_check.py` exists
  (`bd672ff7`). Q-13 is measured, so PTC-R1 stays. F-4 is done in `ci.yml`. The standing-mode reason suffixes `D3`
  and `D4` are the engine's labels (Q-B3).

### 17.2 Amendment A-9 (ADR 0074, 2026-11-08)

- **A-9 (§3.1, D1.5; RP review ruling 4, N-4).** D1.5's mapping is ADR 0074 D2, and its admission is ADR 0074 D1.
  In D1.5, the sentence "The release of `X.Y.Z` has the evidence package `REL` followed by the version's digits
  (0.4.0: `REL040`)." is replaced by: "The release of `X.Y.Z` has the evidence package `REL` followed by the codes of
  X, Y and Z (ADR 0074 D2). A number below 10 is its digit. A number of k ≥ 2 digits is the k-th lower-case letter
  followed by its digits. So 0.4.0 is `REL040`, 0.10.0 is `REL0b100`, and 11.0.0 is `RELb1100`. Its pre-releases and
  post-releases carry the same id." The sentence "The id `REL` plus digits is admitted by the schema ADR of the RP
  review's ruling 4, which widens the manifest's `work_package` pattern; until it is applied, `t08.problems` refuses
  `evidence/REL040/<C>/manifest.json` (Q-C6)." is replaced by: "The id is admitted by ADR 0074 D1, one additive
  alternative of the manifest's `work_package` pattern (components up to 9 999)." D1.5's closing reference becomes
  "Amendments A-7 (§17.1) and A-9 (§17.2)." Nothing else in RP changes. Every default that D1.5 names for 0.4.0 is
  unchanged.

### 17.3 Amendment A-10 (ADR 0074 O-3, 2026-11-09)

- **A-10 (§3.4; ADR 0074 O-3, its default).** A loader check is added after RP.L10, pasted from ADR 0074 O-3:
  "**RP.L11**: for `role` `gate`, `gate_set.evidence_package` equals ADR 0074 D2's id of `<line>.0`. Control:
  `0.4.json` with `REL050`." Why: a line file that inherits another without changing `evidence_package` keeps the
  inherited id (a 0.5 line inheriting 0.4 would keep `REL040`); RP.L03 does not refuse an equal field, so that
  release would share 0.4.0's evidence directory and harvest exclusion. The ranges "RP.L01–RP.L10" of §2 item 1, §3.4's
  heading, §5 (P4), RP.S01 and §12 read "RP.L01–RP.L11"; §3.4's measured record of 2026-11-06 is unchanged.
  `scripts/release_gate.py` implements it with its own encoder of D2 (`release_package_id`), not the manifest
  schema's pattern. Evidence: `tests/test_rel_release_gate.py` `test_l11_*` (the control refused, `REL040` passing,
  D2's examples, the refusals of a segment without an id). It cannot bite before a second `gate` line: the 0.4 line's
  id is D2's.

### 17.4 Amendment A-11 (REL040 S-6 ruling, 2026-11-09)

- **A-11 (§4.5, §5.1, §6.1, §6.5, §7.1, §12, §14; R-1008; `docs/reviews/REL040-s6-ruling.md`).** Records bound to
  the RC host are re-taken at K3 on that host and committed in J. Nothing else in RP changes.
  1. §7.1's third bullet ("The five in-process G10 records are re-taken, …") is replaced by:
     "- The records bound to a version or to the RC host are re-taken at K3, from a clean worktree at K3, on the host
     that runs steps 11, 14 and 15, and are committed together as J (§4.5). Each re-take is written outside the
     repository and proved by a committed tool, and it replaces the committed files only after its proof prints
     `PASS`. The proofs' summary lines go into J's commit message and the build log.
     - The five in-process G10 records (TR-E2, TR-E2-FAR, TR-E2-FD, LOOP-R, LOOP-S), digest-only, proved with
       `scripts/m05_retake_diff.py --digest-only --old-version <the committed records' version>` (R-458).
     - M05's REAL record `benchmarks/m05/records/trust-region-study-real.*`, written by `scripts/m05_wo9_real.py
       --retake-into <dir>` in the audited nlp environment with `OMP_NUM_THREADS=1`. It is proved with
       `scripts/m05_retake_diff.py --digest-only <committed stem> <dir>/trust-region-study-real --old-platform <p>`,
       where p is the committed `S0` coupling record's `frozen.reactor.fingerprint.platform`. The proof must print
       `PASS` with `version=0`, `other=0` and `environment=equal`. Its `platform` count is the number of coupling
       records when the host's platform string differs from p, and 0 when it is equal (R-1008).
     - M01's IDAES conformance record `benchmarks/m01/idaes-conformance.json`, written by
       `benchmarks/m01/idaes_conformance.py --out <dir>/idaes-conformance.json` in the pinned IDAES environment. It is
       proved with `scripts/m01_idaes_retake_diff.py <committed> <dir>/idaes-conformance.json --old-platform <p>`,
       where p is the committed record's `environment.platform`. Only `environment.platform` and `inputs.*_sha256`
       members may differ, and each such input hash must be the SHA-256 of its file at K3 (R-1008).

     The reactor's environment fingerprint (M02 §2.4) holds `platform.platform()`, the kernel release included, and
     its digest is part of every experiment key (ADR 0036 D8). M05's REAL record therefore replays (step 14) only on
     the platform it was taken on. Step 11 compares the IDAES record's `environment` exactly (alpha spec §6.2 W22 (b)).
     A kernel upgrade on the RC host fails steps 11 and 14 until both records are re-taken on it. After the tag
     (§7.4), only the five are re-taken, because neither of the other two holds the version."
  2. §4.5: "J is K3 plus the re-taken G10 records (R-458, §7.1)." becomes "J is K3 plus the records re-taken under
     §7.1 (R-458, R-1008)." §4.5 gains a last paragraph: "The journey at J runs on the host of §7.1's re-takes, and
     step 15 replays it at C on that host. Its R1 experiments and its R3 re-run are bound to that host's platform
     string through the reactor's fingerprint, as M05's REAL record is. 0.3.0's journey at `2d945b5d` was recorded on
     kernel `6.12.111` and does not replay on another kernel (S-6)."
  3. §5.1, C's bullet: "the re-taken G10 records, whose commit is J (§4.5, R-908)" becomes "the records re-taken
     under §7.1, whose commit is J (§4.5, R-908, R-1008)".
  4. §6.5 gains a last paragraph: "`a60.w24.m05_g10_real_replay` also carries `host_platform`, the runner's
     `platform.platform()`, and `record_platform`, the `frozen.reactor.fingerprint.platform` of the committed REAL
     record's `S0` coupling record at C. When that record cannot be read, `record_platform` is `null` and the check
     carries the reason. Neither field is judged, and the pass rule is unchanged. The fields make §12's host-mismatch
     stop checkable." §6.1 step 15 gains: "`a21.replay` carries `host_platform` and `record_platform` in the same way,
     read from the `S0` coupling record of the M05 record that the journey's R3 used: `benchmarks/m07/journey/<J>/m05/`
     for a re-run, `benchmarks/m05/records/` for a carried record."
  5. §12 gains two stops:
     "- A §7.1 re-take proof does not print `PASS`. The re-take is not committed, and the cut stops before J.
     - Step 11, 14 or 15 fails at C while the host's platform differs from the compared record's: step 11's
       `differing_members` holds `environment.platform`, or a step 14 or 15 check's `host_platform` differs from its
       `record_platform`. C's records are committed as they are. The remedy is a new J from the same K3 on this host
       (§7.1's re-takes and the journey) and a new C. A comparison or replay that sets the platform aside is never
       the remedy (R-1008)."
  6. §14 gains the row: "| R-1008 | records bound to the RC host re-taken at K3 on that host and committed in J; their
     proofs; the host-mismatch stop | §7.1, §4.5, §5.1, §12 |".
  7. (S-6 confirmation round, 2026-11-09.) §7.1's re-take bullet gains the definition of the clean worktree: a new
     `git worktree add --detach <path> <K3>`, in which `git status --porcelain --ignored` is empty before the first
     re-take, recorded in the build log. Why: at WO-6 a reused worktree held a git-ignored
     `src/openflowsheet.egg-info`. With `PYTHONPATH=src` it added `openflowsheet` to the REAL re-take's environment
     sidecar (17 → 18 distributions), and the proof failed. From a fresh worktree the sidecar was equal.

  Why: at S-6 (`9743871e`), steps 11, 14 and 15 failed only because the workstation's kernel moved from `6.12.111`
  to `6.12.113` at its 2026-11-06 reboot. The REAL record (taken 2026-10-16) and the IDAES record (2026-10-08) both
  bind the kernel string, and RP re-took neither.

### 17.5 Amendment A-12 (REL040 verdict F-3, 2026-11-10)

- **A-12 (§4.4, §11.1 RP.S14; R-1009; `docs/reviews/REL040-verdicts.md` F-3, F-4, F-5).** §4.4 and RP.S14 are
  restated for a chain of n links. Nothing else in RP changes.
  1. §4.4's paragraph is replaced by the text that §4.4 now holds. It defines "`LINKS` unchanged" as a standing
     `V17 carry` row (§8.3), writes `LINKS` at C as c_1 … c_n, and requires the served digest to equal D_n. It
     requires the rows `(1,c_n)`, `(2,c_n)` … `(2,c_1)`, `(3,None)`, each passing, and gives 0.3.0's chain (n = 3)
     and 0.4.0's (n = 8) as instances. Its last three sentences are unchanged.
  2. RP.S14 reads: "Step 8: with `LINKS` at C written c_1 … c_n in its order, the served digest equals D_n, the last
     link's registered digest, and the chain's rows are exactly `(1,c_n)`, `(2,c_n)`, `(2,c_{n−1})`, …, `(2,c_1)`,
     `(3,None)`, each passing (§4.4, amendment A-12). Otherwise the RC stops."
  3. Unchanged: the chain itself (alpha spec §5.3 items 1–3, `m07a_rc.chain`); §8.2's extractors (E3) and (E4);
     §12's stop; and how the release manifest decides RP.S14 (`Spec("S14", steps=(8,))`, from step 8's record).
     RP.S14 stays same-form (§11.2). Over 0.3.0's records n = 3, and there the general form is V03.A23's literal
     one, so REL.A20's equality is unchanged. §14 gains no row, because R-1009 is RP's own amendment, as R-942 to
     R-949 and R-1007 are. No verdict changes. The verdict document already read RP.S14 in this form, and V13 and
     V17 are BLOCKED under either reading (F-3).

  Why: §4.4 and RP.S14 named 0.3.0's chain literally (three links, D_3, five rows). At C = `84c66547`, `LINKS` holds
  eight links: R-192, R-234, R-295, R-934 (MSG), R-950 (X02), R-960 (OPT), R-1000 (ST) and R-1010 (X04). Each was
  added by its package with a register entry, a strip function and a registered digest. Step 8 passed at C on three
  hosts: `rc/surface/rc-alpha-surface.json` (ref-x86-64) and `rc/ci/rc-steps-ubuntu-latest/` and
  `rc/ci/rc-steps-ubuntu-24.04-arm/` (CI), each with 13 of 13 checks. The chain has ten rows `(1,c_8)`, `(2,c_8)` …
  `(2,c_1)`, `(3,None)` (R-137), each passing. The served digest is
  `6be1c002592524126617af8dd65d331513f4a96355f5381dba020ad561a2ba57` = D_8. Read literally, the old text would fail
  RP.S14 on a passing step 8, or read "unchanged" against 0.3.0's list. The general form is what step 8, the test
  and the verdict already apply. Evidence: those records;
  `tests/test_m07a_surface_chain.py::test_m07a_a37_the_chain_holds_on_the_served_list`, which pins the n = 8
  instance; and `tests/test_rel_evidence_manifest.py::test_the_catalogue_is_rp_s01_to_s22_with_their_forms`, which
  checks that RP.S14 parses and stays same-form.

- **F-4 and F-5: rulings for 0.4.0, not RP changes.** The orchestrator's default holds. The evidence gives no reason
  to overrule it.
  1. **F-4 (L-WS-2).** For 0.4.0, `benchmarks/t08/support_envelope.yaml` stays as it is at C. It is a D2.4 path.
     After C only commits outside D2.4 are admitted (§5.1), and the envelope is pinned at K3 (§7.1). An edit
     therefore means a new K3, J and C and the RC job again. L-WS-2 ("no request-named source exists in v0.1")
     understates 0.4.0, but it claims no capability that 0.4.0 lacks. `CHANGELOG.md`'s `## v0.4.0` carries one
     sentence: 0.4.0 adds an explicit warm-start source, `solve_body.warm_start` (ADR 0070, `explicit-v1`), which
     L-WS-2's text predates. The sentence neither says nor implies that V13 (e) covers that source. Its evidence is
     X02's manifest (`evidence/X02/d26bcd38…/`); the verdict's V13 section says it is not V13 (e)'s. The first
     change after the tag (0.5.0.dev0, the working envelope of R-460) restates L-WS-2 for the explicit source and
     keeps the id.
  2. **F-5 (the limitation grammar).** For 0.4.0, no gate tool changes after C. `v0_2_gate.LIMITATION` stays
     `\bL(?:\d{2}|-[A-Z]+-\d+)\b`. Step 18 runs the engine as it stands at H2 (§9.2 step 6), so a change after C
     changes what judges C. R-912 rejected "widen now" at 0.3.0 on exactly that ground, and the ground holds
     unchanged. Widening gains one table cell, V11's travelling column, and no evidence: the verdict's findings
     change no verdict. L-X04-1, L-X04-2 and L-X04-3 travel by text in three places: the verdict's V11 prose, the
     envelope at C, and `CHANGELOG.md`'s `## v0.4.0` under V11, where each is named with its envelope text at C.
     L-S11-1 to L-S11-3 and L-E01-1 travel as they did at 0.3.0 (R-912). R-912's "the next release's gate adopts"
     reached neither §3.6 nor the 0.4 line before C. It moves to the first change after 0.4.0's tag, with R-912's
     pattern `\bL(?:\d{2}|-[A-Z][A-Z0-9]*-\d+)\b` and R-912's tests, extended so that `L-X04-1` matches. R-1009
     amends R-912's timing only.
  3. Open for the first change after the tag, each with a default:
     - *Where the widened pattern lives* (design lane, no fact needed). Default: R-912's form, the engine's
       constant widened. It is a superset, and R-912's tests require 0.2's outputs to stay byte-identical (REL.A04).
       Alternative: a line-file field, which is a `release-line-v1` schema change.
     - *L-WS-2's restated text* (build lane, from ADR 0070 D1). Default: the automatic source under an opt-in policy
       and the explicit source by `solve_body.warm_start`, with the remaining limitation stated in L-WS-1's terms.
       It is reviewed in that package's single reviewer pass.

  **Does not establish.** A-12 establishes no V17 carry, which needs Frank's replacing row (verdict F-1), and it
  makes V13 and V17 neither PASS nor FAIL. It says nothing of the chain's content beyond what step 8 checks, and
  nothing of the explicit warm-start source beyond X02's manifest. It changes neither alpha spec §5.3 nor
  `scripts/m07a_rc.py`.

### 17.6 Amendment A-13 (HOSTMOVE ruling, 2026-11-11)

- **A-13 (§5.3, §7.1, §7.4, §12, §14; R-1020; `docs/reviews/HOSTMOVE-ruling.md`).** A move of the RC host to
  another machine is a re-take with proof. A host joins T06's reference class only by proof. Nothing else in RP
  changes.
  1. §7.1, the five's sub-bullet: "proved with `scripts/m05_retake_diff.py --digest-only --old-version <the
     committed records' version>` (R-458)" becomes "proved with `scripts/m05_retake_diff.py --digest-only
     --old-version <the committed records' version> --old-host <h>` (R-458, R-1020), where h is the committed
     environment sidecars' `machine`. The proof must print `PASS` with `platform=0` and `other=0`."
  2. §7.1, REAL's sub-bullet: "`--old-platform <p>`" becomes "`--old-platform <p> --old-host <h>`", with "and h is as above" added to the sentence that defines p, and
     "with `version=0`, `other=0` and `environment=equal`" becomes "with `version=0`, `other=0` and `environment`
     `equal` or `host`".
  3. §7.1's paragraph after the bullets gains, after its fourth sentence: "The reactor's fingerprint also holds the
     host's CPU model, the digest of its CPU flags and the pinned environment's absolute directory
     (`env_allowlist.NUMBA_CACHE_DIR`), and each attempt's cheap fingerprint holds the CPU model. Each M05 record's
     environment sidecar holds the host name, the CPU model and the CPU count. These, with the platform strings, are
     R-1020's host-identity leaves. `--old-host` admits exactly them, each from its committed value to the value the
     running host measures, together with the digests they feed under the one-to-one map. Every other leaf, every
     number included, stays bitwise equal. A move of the RC host to another machine is therefore a re-take at K3
     like any other, and a re-take whose numbers move with the host stops the cut (§12)."
  4. §7.4's third bullet: "it re-takes the five in-process G10 records (R-458)." becomes "it re-takes the five
     in-process G10 records (R-458), proved as §7.1 states, with `--old-host` (R-1020)."
  5. §5.3 gains: "(P6) The host that takes §7.1's re-takes, and runs steps 6, 11, 14 and 15, is a member of T06's
     `ref-x86-64`: `t08_rc.machine_class()` prints `ref-x86-64` there. A host joins the class only by R-1020's
     proof (`docs/reviews/HOSTMOVE-ruling.md` §7). Otherwise step 6's `a46.registered_class` fails at C, and F0
     does not judge M4 there."
  6. §12 gains: "- (P6) does not hold at K3: the RC host is not a member of `ref-x86-64`. The cut stops before J (R-1020)."
  7. §14 gains the row: "| R-1020 | a move of the RC host: host-identity leaves admitted by `--old-host` in §7.1's
     proofs; the RC host a member of `ref-x86-64` before K3 | §7.1, §7.4, §5.3, §12 |".

  Unchanged: R-1008's IDAES proof and §6.5's inventory rule. The inventory tool's comparator changes by R-1020
  (WO-H3), not by RP.

  Why: development moved permanently from SMM-TRS2 to SMM-TR09 on 2026-11-10 (Frank). The five in-process records
  failed their after-tag proof on TR09 only in the sidecar's host name, CPU model and CPU count, with `other=0`.
  REAL holds the CPU model, the CPU flags and the environment path in 76 fingerprint leaves, which R-1008's proof
  holds equal. T06's reference class names TRS2's CPU model, so on TR09 step 6 fails and F0 stops judging M4.
