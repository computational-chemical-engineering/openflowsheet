# REL060-L1 (LINE06-L1): the 0.6 line file, design-lane fields

**Status:** final for the 0.6.0 cut, 2026-11-28. **Lane:** design (`specifier`), RP §13 (1), one pass.
**Brief:** `docs/briefs/LINE06-L1.md`. **File:** `release/lines/0.6.json` (the LINE06-L0 draft, finalised; no DRAFT
marker). **Authority:** RP (`docs/derivations/release-procedure.md`) §3.1 to §3.7, §6.1, §6.2, §6.7, §10, §13 and
amendments A-3, A-10, A-13, A-14; ADR 0055; R-1070 (ADR 0057 Amendment 3, the 0.6 scope; cards `ofs-line06-rest`,
`ofs-line06-adr-clause`); ADR 0062, 0067 (on `wp/F8` `d3846b8d`), 0078. Nothing here amends RP, an ADR or a frozen
interface. No production code and no gate script (RP §3.7). Precedent: `docs/briefs/REL050-line-0.5.md` (REL050-L1).

## 1. Scope

The 0.6 line file: `format` `release-line-v1`, `line` `"0.6"`, `role` `gate`, `inherits` `"0.5"`. This note fixes the
design-lane fields (`claimed`, `not_claimed`, `clause`, `gates[*]` criteria, `rc_items`, `changelog_what_it_is_not`,
`rc_steps`), checks the build-lane fields the L0 draft proposed (they stay proposals the build lane owns, RP §13),
answers LINE06-L0's three questions (`docs/briefs/LINE06-line-0.6.md` §2) and ends with the loader's check (§7).

## 2. What the line file establishes

| Field | 0.6 | Against 0.5 | Lane |
| --- | --- | --- | --- |
| `claimed`, `not_claimed`, `clause` | V11 to V20, W21 to W26, X31; W27; 0.5's grammar | equal | design (D-1) |
| `gates[*]` | 0.5's seventeen entries, byte for byte | equal | design (D-2) |
| `rc_items` | 0.5's nine, plus `WHEEL-F2` and `F2-THREE-OS` before `PTC-R1` | changed | design (D-3, D-5) |
| `changelog_what_it_is_not` | 26 phrases | changed | design (D-4) |
| `rc_steps`, `rc_last_step` | 1 to 17; 18 | equal | design |
| `acceptances`, `frank_items`, `rejudge_waits`, `links_item`, `specification_texts` | 0.5's | equal | carried |
| `name`, `covers`, `envelope_id`, `evidence_package`, `verdict_document`, `rc_record` | `v0.6-gate-v1`; `0\.6\.0(?:(?:b\|rc)[1-9][0-9]*)?`; `v0.6-envelope-1`; `REL060`; `docs/reviews/REL060-verdicts.md`; `docs/REL060-rc-record.md` | changed | build (proposed, D-7) |
| `packages` | 0.5's 25 plus F2, F8, X06 | changed | build (proposed, D-7) |
| `required_adrs` | 0.5's 32 plus 0019, 0062, 0067, 0078 | changed | build (proposed, D-7; 0019 is this pass's correction) |

The file keeps 0.5's layout (compact arrays), so `diff release/lines/0.5.json release/lines/0.6.json` shows exactly
the changes. Layout is not compared (RP §3.2: parsed JSON values).

## 3. `changed`, exactly (RP §3.2)

Ten names, each a compared field that differs from 0.5 and none that is equal (measured, §7). They are 0.5's ten names.

1. `changelog_what_it_is_not`: phrase 3 restated for the one F2 check on Windows and macOS, phrase 17 names 0.6.0,
   phrase 20 replaced, four phrases added (D-4).
2. `gate_set.covers`: 0.5.0's pattern at 0.6 (RP §3.6's rule); 0.6.0 and its b/rc pre-releases.
3. `gate_set.envelope_id`: `v0.6-envelope-1`, the envelope K3 pins (§7.1); `main` carries `v0.2-envelope-dev` until then.
4. `gate_set.evidence_package`: `REL060`, ADR 0074 D2's id of 0.6.0; RP.L11 (A-14) refuses anything else.
5. `gate_set.name`: `v0.6-gate-v1`.
6. `gate_set.packages`: F2, F8 and X06 join, so P1 (§5.3) and step 18's item 5 check their manifests.
7. `gate_set.rc_record`: `docs/REL060-rc-record.md` (D1.5 default).
8. `gate_set.required_adrs`: the ADRs accepted since 0.5.1's C' on which 0.6's content rests (D-7).
9. `gate_set.verdict_document`: `docs/reviews/REL060-verdicts.md` (D1.5 default).
10. `rc_items`: `WHEEL-F2` and `F2-THREE-OS` added (D-3, D-5).

## 4. What is carried, and why

- **`acceptances`**, **`frank_items`**, **`rejudge_waits`**, **`links_item`**, **`specification_texts`**: 0.5's. No
  decision item is added: no extra and no lock changed since `v0.5.1` (`git diff v0.5.1 HEAD -- pyproject.toml
  requirements*.lock` shows only the version line; `wp/F8` changes neither), so no MR-12 item and no licence row. The
  five items stand or lapse by their scopes at C (§8.3); the prediction is in §9.
- **`rc_steps` 1 to 17, `rc_last_step` 18**: the claim set is unchanged, so every step still has a claimed gate.
- **0.5's nine items**, unchanged: `E01-A48`, `MR12-lca`, `E01-G5-lca`, `E01-G6-nlp` (E01's data and the lca extra are
  unchanged); `S07-F8`, `MR12-coolprop` (coolprop extra and lock unchanged); `WHEEL-DATA` (the ship set still ships);
  `WHEEL-F1-F3` (F1's registry and F3's legacy store still ship; F2's `registry/builtin/material.json` is in the
  built-in registry, so WF-3's `registry_sha256` comparison now also covers it); `PTC-R1`.
- **What 0.5.1 taught (RC step 14, M05's REAL replay after the TRS2 to TR09 move)**: nothing for the line file. W24's
  R(g) `[14, "*"]` stands. 0.5.1 re-took the REAL record at K3' on TR09 with `--old-host SMM-TR09` and
  `--old-platform Linux-6.12.86+deb13-amd64-x86_64-with-glibc2.41` (proof `version=0 platform=0 other=0
  environment=equal host=0`, `docs/REL051_DECISIONS.md` lines 49 to 54), and W24 passed with host platform = record
  platform (`docs/reviews/REL051-verdicts.md`, W24 row). 0.6.0 repeats the §7.1 re-take at its K3 on the same host; a
  kernel or glibc update since moves only `platform`, which `--old-platform` admits. "The real dispatch waits for
  main's push-run CI" is procedure (the `rel050` skill), not a line field.

## 5. Decisions

**D-1. The claim set is 0.5's.** R-1070's scope (F2, F8 WO1 to WO3 and WO5, X06) brings no registered gate criteria,
and a new gate needs an RP amendment stating them (§3.7), a `gates` entry, a clause that parses it and the user's
re-dated `Claim set` row. 0.4.0 and 0.5.0 are the precedent: their new packages shipped under the inherited claim set,
each evidenced by its manifest and by step 1, and listed in the notes with that manifest (§10). `Claim set`'s scope
(`extract:claim_set`, E1) is unchanged, so its row stands. The line acceptance is not made a gate (D-3).

**D-2. No gate criterion changes; `gates[*]` is 0.5's.** No RP amendment is proposed. Every `criteria` and
`documents` path of every gate is unchanged from `v0.5.1` on `main` (`43f0b7f5`) and on `wp/F8` (`d3846b8d`), measured
with `git diff --stat v0.5.1 <ref> -- <the 20 paths>`: empty. T(g) is not extended to `tests/test_f2_*`,
`test_f8_*` or `test_x06_*`: no claimed gate's criteria name those packages, and step 1 (`[1, "*"]`) runs them on the
Linux legs. The surface suites that V11, V13 and V17 already glob (`test_t07_*`, `test_t08_*`, `test_m07a_*`) carry
F2's c_11, X06's c_12 and F8's c_13 chain links. No step-17 pair is added to any gate: `WHEEL-F2` and `F2-THREE-OS` are
judged by RP.S13, as `WHEEL-DATA` and `WHEEL-F1-F3` are.

**D-3. L0 question 2, the line clause: an `rc_items` entry, `F2-THREE-OS`, not a gate.** The clause (R-1070, card
`ofs-line06-adr-clause`) is "a v2 revision with store-pinned records solves on the legacy route on all three OSes".

*Which CI job and test produce the evidence.* `ci.yml`'s `check` job runs `./scripts/check.sh`, the whole pytest
suite, on four legs (`ubuntu-latest`, `ubuntu-24.04-arm`, `windows-latest`, `macos-latest`) in every push run, and
uploads each leg's junit as `junit-x86_64`, `junit-aarch64`, `junit-Windows-X64`, `junit-macOS-ARM64` (the artifact
name expression of its "Junit (RP §6.2)" step). The test is `tests/test_f2_amendment9.py`
`test_e_f2_3_raised_run_writes_the_v1_bundle`, E-F2-3's run half: each of F0's 56 run revisions (47 `g8`, 9 basis
cases), raised to v2 (each component pinned by its legacy record's SHA-256 in F3's index, so "store-pinned") and
submitted as F0 submits it, writes its v1 run's bundle: `run_id`, `artifact_r0_sha256` (also equal to F0's registered
M3), the artifact index, the state hashes and `solution-state.json` bytes equal to the v1 run's on that leg. Beside it,
`test_e_f2_3_run_set_is_47_g8_and_9_basis_cases` pins the count at 56. **Measured** (junit of run 46041020889, `wp/F2`
at `80cdcfb3`, the run that cleared F2's merge): on each of the four legs 57 cases matched (56 + 1), all passed, 0
skipped, and the sorted case names have the same SHA-256 on every leg,
`0afd81d3cb38ea0b5e05c8726ca3f5930765ee551d7db5c97879275419a69807`. So every CI leg already runs the case: the build
lane adds no CI job (the state file's L3 is a reader, below, not CI work).

*Why an item.* Step 1 (RP §6.2) judges only the two Linux `check` legs, and changing that is an RP amendment and
REL050-L1's Q-F2, which the user left at its default. A gate needs registered criteria, a clause grammar and a
re-dated `Claim set` row, for a roadmap acceptance that 0.4 and 0.5 kept out of the gates (REL050-L1 D-3). An item
reads the evidence the push run at C already holds, costs no CI minute, puts the clause in the RC record at C (not at
some earlier commit), and binds the release through RP.S13. Rejected: a `ci:` item (a dispatch-only job on four
runners that re-runs what the push run ran; RP §6.2 "No step re-runs CI at C"); judging the clause only at L3 (a
regression between L3 and C would ship unseen; Q-L1 keeps it as the alternative).

`{"id": "F2-THREE-OS", "script": "scripts/release_rc.py", "where": "local:project", "command": ["python",
"scripts/release_rc.py", "junit-cases", "--commit", "$C", "--rc", "$RC_OUT", "--id", "F2-THREE-OS", "--legs",
"x86_64,aarch64,Windows-X64,macOS-ARM64", "--case", "<file>::test_e_f2_3_raised_run_writes_the_v1_bundle", "--case",
"<file>::test_e_f2_3_run_set_is_47_g8_and_9_basis_cases"]}` with `<file>` = `tests/test_f2_amendment9.py`. The legs
and cases are argv, so the clause's scope is in the line file and a change to it is a `changed` field. The owner is
the standing RC runner: it already holds §6.2's rule (`push_run`), `gh` access and the junit download (`_gh_junit`);
it is not a per-release script (RP §3.3). `junit-cases` does not exist yet: until the build lane adds it, the command
exits 2 (argparse) and the item fails at step 17, visibly (RP.S13). Its checks, all exact (ids, names and digests
compared as strings, counts as integers; no floating point, so no tolerance):

- **TO-1** `legs.push_run`: the push run at C by RP §6.2's rule exists and is completed, and its run id equals the
  `run_id` of check `s1.push_run` in `<rc>/step1/rc-step1.json` (the run step 1 judged). An absent step-1 record fails.
- **TO-2** `legs.junit`: for each leg L of `--legs`, artifact `junit-L` of that run downloads into
  `<rc>/step17/<id>/junit-L/` and holds `pytest.xml`; an absent artifact or file fails, naming L. Where step 1 recorded
  a file's SHA-256 (`s1.junit`, the Linux legs), the downloaded file's SHA-256 equals it.
- **TO-3** `legs.cases`: for each `--case F::T` and each leg, the matched testcases are those whose `classname` is F
  with `/` read as `.` and `.py` dropped (`tests.test_f2_amendment9`) and whose `name` is T or starts with `T[`. At
  least one matches per case per leg (no accidental zero).
- **TO-4** `legs.passed`: no matched testcase has a `failure`, `error` or `skipped` child.
- **TO-5** `legs.same_set`: the sorted matched names are the same list on every leg; their SHA-256 (the names joined by
  `\n`, UTF-8) is recorded per leg.
- **TO-6** record and controls: `<rc>/step17/<id>/junit-cases.json` (run id, per leg the file SHA-256s, per case the
  count and the names' SHA-256, every check); one line per check, last line `junit cases (<id>): PASS|FAIL`; exit 0
  iff TO-1 to TO-5 pass, 1 otherwise, 2 when the checkout is not at C or the arguments are malformed. Its tests carry
  six controls on fixture junit files, each of which must fail its check: (a) one leg's case `skipped` (TO-4); (b) a
  `failure` child (TO-4); (c) one leg missing one parametrised case (TO-5); (d) a `--case` that matches nothing on any
  leg (TO-3); (e) a leg's artifact absent (TO-2); (f) a run id other than step 1's (TO-1).

What `F2-THREE-OS` does not establish: anything else on Windows or macOS (the rest of those legs is not judged; phrase 3
says so); that a v2 revision pinning a non-legacy record solves (it is refused `construct_unavailable(component:<id>,
F4)`, D-4); replay of any bundle across operating systems (phrase 4 stands).

**D-4. The phrases.** 26, in this order. Unchanged phrases keep 0.5's text. The changed and new ones, with sources:

| # | Phrase | Source |
| --- | --- | --- |
| 3 | the release is judged on Linux only, except that v2 lowering is also judged on Windows and macOS | D-3: step 1 and steps 2 to 16 are Linux; step 17's `F2-THREE-OS` reads E-F2-3 on Windows and macOS. 0.5's text would be false once the item binds |
| 17 | no W27 claim in 0.6.0 | Q-14's rule: the version follows the release |
| 20 | v2 revision documents solve only on the legacy route | ADR 0062 D12 as built (`revision_v2/lower.py`, `application/validation.py` `v2_admission`): a v1-expressible v2 document lowers to its v1 document and runs as the v1 run (D8); any other is refused `construct_unavailable(<construct>, <foundation>)` |
| 21 | no solve reads the component record store | kept unchanged; decided from F2's built behaviour, below |
| 23 | no F4 property methods, F5 phase equilibrium or F6 std.* unit models | R-1070 (F4 to F6 move to 0.7); the refusals name exactly these foundations (`construct_unavailable(..., F4\|F5\|F6)`), so the phrase uses the codes a user meets |
| 24 | no run writes a v2 bundle, and a v2 bundle is inspected, not rerun | `wp/F8` `d3846b8d`: `run/bundle_v2.py` ("In 0.6 nothing in `src/` writes a v2 bundle"; the writer is the test-only factory); `application/revision_replay.py` `V2_RERUN_UNAVAILABLE` (`construct_unavailable(v2 bundle rerun, F8-WO6)`) |
| 25 | no job resume, and no branch merge or rebase | ADR 0078 D3 (resume deferred to F7 D14) and "What this ADR does not establish" |
| 26 | no TLS or OAuth on the HTTP server | ADR 0078 D1.6 (TLS out of scope, a TLS-terminating proxy for remote use; no RFC 9728 OAuth) |

*Does a v2 solve read the record store?* No, measured on `main` `259bda86`. Lowering resolves each pinned record
SHA-256 against the committed legacy index (`revision_v2/lower.py` `legacy_records()` over
`records.importers.legacy.committed_index()`, the package-data file `records/legacy_index.json`), and the lowered v1
document binds as v1 does (its `record_source` file, or a provider's built-in basis). Nothing on the solve path opens
the store: the only `StoreStack` the application builds is `service_core.record_stack`, read only by
`records_service.py` (the record operations); `LegacyStore(available_records)` is constructed only there. A record that
is not a legacy component record is refused at lowering (`component:<id>`, F4), never read from a project's store.
F8's `run/replay_v2.py` reads the store for a v2 bundle's data check (D5 step 6), which is a replay, not a solve, and is
not reached for a rerun in 0.6 (phrase 24). Phrase 21 is therefore still true, and kept verbatim. "Store-pinned" in the
line clause means pinned by store identity (the record SHA-256), not read from the store.

L0 proposed dropping phrase 21; that would delete a true and relevant limit. Rejected. Each phrase must occur exactly
once in `CHANGELOG.md`'s `## v0.6.0` section, package text included (RP.S10 counts substrings), so the F2, F8 and X06
entries paraphrase phrases 3, 20, 21 and 23 to 26. No phrase is a substring of another (measured, §7).

**D-5. L0 question 1: one new item `WHEEL-F2`; F8 needs none; `WHEEL-F1-F3` is not widened.** RP §3.6 item 4 asks
for an item when a release ships package data beyond the previous one's. 0.6 ships, as `_data/schemas/*.schema.json`:
F2's `process-revision-v2`, `specification-v2`, `connection-definition`, `solution-state-v2` (L0 listed "payload
schemas": F2's payload envelopes are F1 descriptors in the new `registry/builtin/material.json`, not schema files);
F8's `bundle-v2`, `records-index`, `run-evidence` (L0 listed `run-manifest` and `replay-report`: they existed and were
widened; `bundle-v2` was missing from L0's list); X06's `solve-policy-results`. Measured by `git ls-tree` of `schemas/`
at `v0.5.1`, `main` and `d3846b8d`. Step 3 (T08.A43) already holds every declared package-data file in the wheel
byte-equal to C, and the schema loader (`schema_check._published`) reads the packaged directory, so presence is
proved. What no step proves is that the installed package *uses* F2's data: step 4 solves SYN-001 by name on the v1
path; `WHEEL-F1-F3` proves the registry (now with `material.json`) and the legacy index load, not the v2 route.

- *F8 needs no item in 0.6:* the only path an installed user reaches is the v1 dispatch (no `bundle_format`, D5 step
  2), which step 4's `f0-replay` runs from the installed wheel over F0's 52 bundles on both Linux legs; v2 bundles are
  written only by a test-only factory and are inspected, never rerun (phrase 24). An item would test a path no user
  can take. F8-WO6 (0.7) brings the first `src/` writer; that line adds the item.
- *X06's schema:* step 3 holds it in the wheel; it is reached through `application-results.schema.json`'s `$ref` by the
  same loader. See D-6 for X06.
- *Not `WHEEL-F1-F3` widened:* a widened item would change what an existing record id meant at 0.5 and its controls;
  a new id keeps one id, one meaning.

`{"id": "WHEEL-F2", "script": "scripts/wheel_data_check.py", "where": "local:project", "command": ["python",
"scripts/wheel_data_check.py", "--commit", "$C", "--f2"]}`. `--f2` does not exist yet; until it does the command exits
2 and the item fails at step 17, visibly. Assertions, all exact (no floating point is compared, so no tolerance):

- **WV-1** `wheel.built`: as WF-1 (`scripts/t08_dist.py --commit C` exits 0 and its record passes).
- **WV-2** `f2.probes`: the probe runs in a fresh venv (`requirements.lock`, then the wheel `--no-deps`) with `-I`
  from an empty directory, importing from `site-packages`, and once in the checkout at C importing from `src/`; both
  with `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS` = 1; both exit 0 and find no entry point in group
  `openflowsheet.extensions` (as WF-2).
- **Inputs** (written by the script in the checkout at C, read by both probes as data): for each R of
  `g8/SYN-001-T06-NET02` and `s11-gp/GP-C1`, the v1 document (`scripts/corpus_identity.py` `revision_document`) and
  its raised v2 document (`revision_v2.raise_v1.raise_v1(v1, models.revision_flowsheet.legacy_providers())`); and N,
  the raised `SYN-001-T06-NET02` with `materials.thermal_coordinate` set to `h_mass`. The script asserts each raised
  document has `schema_version` 2 and N differs from its source only at `/materials/thermal_coordinate`, and records the
  SHA-256 of each document's canonical bytes (sorted keys, separators `,` `:`, UTF-8). *Why these states:* SYN-001's
  record file is not package data and its basis is built in, with no parameter set; GP-C1 is Wilson, its record file
  `benchmarks/s10/records.yaml` is package data, and it carries one parameter set, so D12 (d)'s parameter-set clause
  and a packaged record file are both on the path; N is the state that must be refused, so a lowering that admits
  everything fails.
- **WV-3** `f2.v2_runs_as_v1`: on each side and for each R, in a fresh `LocalApplication.in_memory()` per document:
  `commit_change` of the document's members other than `revision_id` and `parent_revision` (one `Change`, as
  `tests/test_f2_amendment9.py` rows 10 to 12 commit) gives `committed` with validation `READY_FOR_SIMULATION`;
  `solve(<id>, "default")` gives outcome `CONVERGED`; the run manifest, read with `artifact_bytes` of the
  `run_manifest` output, has v2's `artifact_r0_sha256` and `artifacts` (name to SHA-256, `solution-state.json`
  included) equal to v1's on that side (ADR 0062 D8). The application's `outputs` digests are not compared: they cover
  `started_at`, `elapsed_seconds` and `hostname`, and differ between two v1 runs (measured).
- **WV-4** `f2.r0_registered`: on each side, each R's v2 `artifact_r0_sha256` equals F0's registered M3
  (`benchmarks/f0/corpus.json` at C, `measures.M3["<set>/<name>"].artifact_r0_sha256`), read by the script, not through
  the code under test. This is the independent expectation; WV-3's v1 run is the second.
- **WV-5** `f2.refusal`: on each side, `check_admission(revision=N)` raises `ApplicationError` with code
  `revision_unsupported` and `detail.unbound` exactly `unsupported(construct_unavailable(thermal_coordinate:h_mass,
  F6))` (ADR 0062 D12's refusal for `thermal_coordinate:<coordinate>`, rendered as F2 decision WO6b-5 states); and
  `check_admission(revision=<SYN-001-T06-NET02's v2>)` admits, so the refusal is not the probe failing everywhere.
- **WV-6** record and controls: one line per check, the findings as one JSON line (the five document digests, per side
  the r0 values, the artifacts-index digests and the refusal string, the wheel's SHA-256), last line `wheel data check
  (F2): PASS|FAIL`; exit 0 iff WV-1 to WV-5 pass, 1 otherwise, 2 when the checkout is not at C. Its tests carry five
  controls, each of which must fail its check: (a) the installed `openflowsheet/_data/schemas/process-revision-v2.schema.json`
  deleted (WV-3); (b) the installed `openflowsheet/records/legacy_index.json` with one of GP-C1's component record
  SHA-256s altered (WV-3: lowering refuses `component:<id>`); (c) a probe document whose v2 `artifact_r0_sha256` is
  replaced by another 64-hex value (WV-3 and WV-4); (d) a probe document with the refusal string altered (WV-5); (e)
  N built with `thermal_coordinate` `T` (WV-5: it is admitted).

**Sanity values**, measured in the checkout at `43f0b7f5` on SMM-TR09 with the project venv and one thread (the
installed side is not measured; these are not expectations): SYN-001-T06-NET02 v1 and v2 both `READY_FOR_SIMULATION`,
`CONVERGED`, `VERIFIED`, `artifact_r0_sha256` `414fba515c51d5477b25c21a8395616a9c04b2b76bb0365772c7cd4b865a78e7` (=
F0 M3), `solution-state.json` `d9cbaeda9eeb72e9e421b48097e7f2b5342d9cf7ac5dcbee0f0eec4d972fde13`, 3 components, 0
parameter sets; GP-C1 likewise, `6e6ab158c5c1b7a52067bab786a5f3c0bc64c9600995f6be64605ad0d7e56f88` (= F0 M3),
`39a34401946de98339b4668343876d17106fdb1a1d6dc6e344e7f31c0b128307`, 3 components, 1 parameter set; the artifact
indexes of v1, v2 and a second v1 run equal; N refused as WV-5 states (the hint also lists `thermal_coordinate_mismatch`
and seven `unit_coordinate_unsupported`; only `unbound` is asserted). The four solves took 4.6 s.

What `WHEEL-F2` does not establish: that F2's lowering is right (E-F2-3 and F2's manifest and review carry that);
anything on Windows or macOS (D-3 does); any plugin path (WV-2 requires none).

**D-6. L0 question 3: no X06 release item.** ADR 0078's exits (E-X06-1 to E-X06-24) are package tests run in the tree
by step 1; none names an installed wheel or a release, and ADR 0078's "Edits other documents need" names no RP or line
change. The installed path is partly exercised already: step 4's M06 G10 starts `openflowsheet serve-http --ui` from
the installed wheel with the `server` extra, and `application/serving.py` mounts `/mcp` (`mcp_http.mount`) whenever it
builds that application, so a broken import or mount fails step 4. No step of `clean-install` (`ci.yml` lines 717 to
870) sends an MCP request from the wheel, over HTTP or stdio; that gap predates X06 and is Q-D1.

**D-7. Build-lane fields, checked (proposals; the build lane owns them, RP §13).**
- `name`, `covers`, `envelope_id`, `evidence_package`, `verdict_document`, `rc_record`: L0's values are correct (RP
  §3.1 D1.5; RP.L11 with A-14 gives `REL060` for a `covers` admitting 0.6.0 only).
- `packages`: L0's (0.5's 25 plus F2, F8, X06). Measured: `evidence/F2/fb75c409…/manifest.json` and
  `evidence/X06/1a2782d1…/manifest.json` are `tested` on `main`; `evidence/F8/18676313…/manifest.json` is `tested` on
  `wp/F8` `d3846b8d`. No other package's manifest was added since `v0.5.1`.
- `required_adrs`: L0's plus **`0019`** (correction). The ADR files changed since `v0.5.1` are 0019, 0057, 0062, 0067,
  0078 (`git diff --name-only`, `main` and `d3846b8d`). 0019 carries Amendments 9 (F2), 12 (F8) and 18 (X06) as its own
  sections, each Accepted since 0.5.1's C'; 0.5 added 0007 and 0057 on the same ground (an older ADR whose amendment
  accepted since the last C carries the release's content). 0057 is already listed. ADRs that 0062 and 0067 amend
  only inside their own text (0001, 0002, 0020, 0025, 0034) are covered by requiring 0062 and 0067; 0002's status is
  not `Accepted`, so listing it would fail step 18's item 7. `adr_problems` over the 36: PASS at `d3846b8d`; at `main`
  only 0067 fails (Proposed until F8 merges), as 0061 did for 0.5's draft. This rule also makes the line acceptance's
  "ADR 0062, 0067 and 0078 Accepted" (card `ofs-line06-adr-clause`) a release check.

**D-8. What depends on F8's tree (`wp/F8` `d3846b8d`).** `packages` F8 and `required_adrs` 0067 (its manifest and its
Accepted status exist only there); phrase 24 and D-5's F8 paragraph (no `src/` writer, rerun refused); D-5's schema
list (`bundle-v2`, `records-index`, `run-evidence`); §9's `V17 carry` prediction (c_13). If F8's CI forces a change to
its schemas, CLI, the v2 bundle writer or the rerun refusal, the orchestrator reruns D-4's phrase 24, D-5 and D-8 here.
Nothing else in this note reads F8's tree.

## 6. Not established

- No verdict on any gate (the `verdict` pass does that at C); no lapse decided (§8.5's report at C does).
- That anything other than the named E-F2-3 cases passes on Windows or macOS at C.
- That a v2 revision pinning a non-legacy record, or any v2 construct outside D12's v1-expressible set, solves.
- That F8's v2 bundle path works from an installed wheel (no user path reaches it in 0.6), or that `/mcp` answers from
  one (Q-D1).
- That `junit-cases` or `--f2` exists: neither does. The sanity values are measurements at `43f0b7f5` (checkout side)
  and at run 46041020889 (`wp/F2` `80cdcfb3`), not expectations; the expectations are F0's registered M3, the v1 run,
  the ADR's refusal and the push run at C.
- RP.L05 and RP.L08 were read at the worktree's tracked paths, not at K3 or C; P4 re-reads them at K3, the gate at C.

## 7. The loader's check

There is still no loader-only mode on the command line (`release_gate.py`: `--line` and `--rc` are required). The
loader is `release_gate.load_line` (RP.L01 to L04, L06, L07, L08's ids, L09 to L11) plus `release_gate.tree_problems`
(RP.L05, L08's scripts). Measured 2026-11-28 in the worktree (`wp/REL060`, HEAD `43f0b7f5`, the file on disk), with
the scratch driver below (it also recomputes `changed`, the phrase rules and `line_release`):

    PYTHONPATH=src /home/eajfpeters/Code/OpenFlowsheet/.venv/bin/python <driver> [<commit>]
    changed == computed: True 10 ['changelog_what_it_is_not', 'gate_set.covers', 'gate_set.envelope_id', ...]
    phrases 26 distinct True substring pairs []
    line_release 0.6.0 evidence_package REL060
    RP.L01-L11: PASS

The driver reads the line files with `git show <commit>:<path>` (or from disk without a commit) and the tracked paths
with `git ls-tree -r --name-only <commit>`, calls `load_line("0.6", read)` and `tree_problems(line, paths)`, compares
`changed` with the compared fields that differ from 0.5 (`release_gate.COMPARED`), and checks the phrases are distinct
and none is inside another; it exits 1 on any finding. REL050-L1 §7's one-liner, with `0.5` read as `0.6`, is the
build lane's command at K3 (P4). Also measured with the file on disk: `tests/test_rel*.py` (including
`test_no_phrase_of_a_gate_line_is_a_substring_of_another`, which now reads three gate lines): 295 passed.

## 8. Open questions, each with a default

- **Q-L1 (the user's preference; for message 1, informational): judge the line clause at the release.** Default: yes,
  item `F2-THREE-OS`, phrase 3 as restated (D-3). Alternative: judge it once at L3 and keep 0.5's phrase 3 and item
  list; then a regression between L3 and C ships unseen. Either way the claim set is unchanged.
- **Q-B1 (needs a fact, build lane): `release_rc.py junit-cases` (TO-1 to TO-6) and `wheel_data_check.py --f2` (WV-1
  to WV-6), each with its controls, before K3.** Default: one build-lane work order each (the first is the state file's
  L3). Settled by each command's PASS at the worktree head against a real push run and a real wheel. Until then step
  17 fails both items and §12 stops the cut; dropping an item instead is a design-lane edit of `rc_items`.
- **Q-B2 (needs a fact): F8's CI at `d3846b8d`.** Default: F8 ships as at `d3846b8d`. If CI forces a change to what F8
  ships, D-8 lists what is rerun.
- **Q-D1 (design lane): an installed-wheel `/mcp` request.** Default: none in 0.6 (D-6). Alternative: step 4's M06 G10
  also sends `POST /mcp` `tools/list` with a bearer and compares its canonical digest with the registered served
  digest; that is a change to CI's `clean-install` job (T08.A44), not a line field, and would cover stdio's gap too.
- **Q-D2 (preference): `0019` in `required_adrs`.** Default: yes (D-7). Alternative: leave it out; Amendments 9, 12 and
  18 are then required only through 0062, 0067 and 0078.
- **Q-D3 (design lane, orchestrator): RP §13 (3)'s `reviewer` pass.** Default: yes, because `junit-cases` changes
  `scripts/release_rc.py`; one pass scoped to `git diff v0.5.1 <K3> -- scripts/release_*.py scripts/wheel_data_check.py
  release/ docs/derivations/release-procedure.md`, with this note as its specification.

## 9. For the user's message 1 (RP §8.5, §9.2 step 2)

The claim set is unchanged, so its row stands. Expected in the batch, the lapse report deciding, predicted from the
scopes at `43f0b7f5` and `d3846b8d`: `V17 carry` lapses (`LINKS` gains c_11, R-1072, F2; c_12, R-1073, X06; c_13,
R-1076, F8; the served digest moved); `V14 (b)` lapses (`src/openflowsheet/**` changed, 92 files since `v0.5.1`), a
failure clause asked after the verdict as at 0.5.1. Predicted to stand: `M02 N1` (`adapters/external/` unchanged),
`M03 N1` (the `nlp` extra unchanged), `coolprop and lca licences` (extras and locks unchanged), `X31 (c)` (its paths
unchanged). Plus Q-L1, for information: the release now reads one F2 test on Windows and macOS, because the 0.6 line
acceptance the user set requires it.
