# REL050-L1: the 0.5 line file, design-lane fields

**Status:** draft for the 0.5.0 cut, 2026-11-21. **Lane:** design (`specifier`), RP §13 (1), one pass.
**Brief:** `<git-common-dir>/codehealth/briefs/REL050-L1-line-file.md`. **File:** `release/lines/0.5.json` (draft).
**Authority:** RP (`docs/derivations/release-procedure.md`) §3.1 to §3.7, §6.1, §6.7, §10, §13 and amendments A-3,
A-10, A-11, A-13; ADR 0055; R-1065 (ADR 0057 Amendment 1, the 0.5 scope); R-1062 (ADR 0007 Amendment 3); R-1063;
R-1068. Nothing here amends RP, an ADR or a frozen interface. No production code, no gate script (RP §3.7).

## 1. Scope

The 0.5 line file: `format` `release-line-v1`, `line` `"0.5"`, `role` `gate`, `inherits` `"0.4"`. This note fixes the
design-lane fields (`claimed`, `not_claimed`, `clause`, `gates[*]` criteria, `rc_items`, `changelog_what_it_is_not`)
and proposes the build-lane fields, which the build lane owns (RP §13) and may change before K3 without a design
pass. It ends with the loader's check (RP.L01 to RP.L11) on the draft.

## 2. What the line file establishes

| Field | 0.5 | Against 0.4 | Lane |
| --- | --- | --- | --- |
| `claimed`, `not_claimed`, `clause` | V11 to V20, W21 to W26, X31; W27; 0.4's grammar | equal | design (D-1) |
| `gates[*]` | 0.4's seventeen entries, byte for byte | equal | design (D-2) |
| `rc_items` | 0.4's eight, plus `WHEEL-F1-F3` before `PTC-R1` | changed | design (D-5) |
| `changelog_what_it_is_not` | 22 phrases | changed | design (D-4) |
| `rc_steps`, `rc_last_step` | 1 to 17; 18 | equal | design |
| `acceptances`, `frank_items`, `rejudge_waits`, `links_item`, `specification_texts` | 0.4's | equal | carried |
| `name`, `covers`, `envelope_id`, `evidence_package`, `verdict_document`, `rc_record` | `v0.5-gate-v1`; `0\.5\.0(?:(?:b\|rc)[1-9][0-9]*)?`; `v0.5-envelope-1`; `REL050`; `docs/reviews/REL050-verdicts.md`; `docs/REL050-rc-record.md` | changed | build (proposed, D-6) |
| `packages` | 0.4's twenty plus F1, F3, X01, X07a | changed | build (proposed, D-6) |
| `required_adrs` | 0.4's 26 plus 0007, 0057, 0060, 0061, 0076, 0077 | changed | build (proposed, D-6) |

## 3. `changed`, exactly (RP §3.2)

Ten names, each a compared field that differs from 0.4 and none that is equal (measured, §7):

1. `changelog_what_it_is_not`: phrase 3 of 0.4 ("Linux only") is replaced by three platform phrases, phrase 15 names
   0.5.0, and three phrases are added for what F1, F3 and X01 do not do (D-4).
2. `gate_set.covers`: 0.4's pattern at 0.5 (RP §3.6's rule).
3. `gate_set.envelope_id`: `v0.5-envelope-1`, the envelope K3 pins (§7.1).
4. `gate_set.evidence_package`: `REL050`, ADR 0074 D2's id of 0.5.0; RP.L11 refuses anything else.
5. `gate_set.name`: `v0.5-gate-v1`.
6. `gate_set.packages`: the four packages of the 0.5 scope join, so P1 (§5.3) and step 18's item 5 check their
   manifests (D-6).
7. `gate_set.rc_record`: `docs/REL050-rc-record.md` (D1.5 default).
8. `gate_set.required_adrs`: the ADRs accepted since 0.4.0's C on which 0.5's content rests (D-6).
9. `gate_set.verdict_document`: `docs/reviews/REL050-verdicts.md` (D1.5 default).
10. `rc_items`: `WHEEL-F1-F3` added (D-5).

## 4. What is carried, and why

- **`acceptances`** stays `release/acceptances.md`: one standing table (R-918). Its rows lapse or stand by their
  scopes at C (§8.3); the line file does not touch them.
- **`frank_items`, `rejudge_waits`, `links_item`** stay: the same five decision items, the same waits (V13 and V17 on
  `V17 carry`, W21 on `M02 N1`, W24 on `M03 N1`). No item is added: pywin32's licence is Frank's package decision
  R-1063 (card `ofs-x07a-pywin32-licence`, `VERIFIED`), it is not an extra, and no extra is new since 0.4.0
  (`project.optional-dependencies` is equal at `84c66547`, `d29f1a50`, `wp/X07a` and `wp/X01`, measured).
- **`specification_texts`** stays (`the standing release procedure`, `§6`).
- **`rc_steps` 1 to 17, `rc_last_step` 18**: every step has a claimed gate, so none is left out (§6.1).
- **The eight 0.4 items**, unchanged: `E01-A48`, `MR12-lca`, `E01-G5-lca`, `E01-G6-nlp` (E01's data and the lca extra
  are unchanged); `S07-F8` and `MR12-coolprop` (the coolprop extra and lock are unchanged; `rc-coolprop` stays a
  `release_rc` job on `wp/X07a`); `WHEEL-DATA` (V03's ship set and E01's data still ship); `PTC-R1` (Q-13 measured
  within 360 minutes at 0.4.0; `ptc-r1` stays a `release_rc` job on `wp/X07a`).
- **RC step 14** (M05's REAL replay, failing since the TRS2 to TR09 move) needs no line-file change. The REAL record is
  a §7.1 re-take at K3 on the RC host (A-11, A-13, with `--old-host`), committed in J; W24's R(g) `[14, "*"]` is
  unchanged. If its proof does not print `PASS`, §12 stops the cut before J. SMM-TR09 is in `ref-x86-64` (R-1020), so
  P6 can hold.

## 5. Decisions

**D-1. The claim set is 0.4's.** `claimed` V11 to V20, W21 to W26, X31; `not_claimed` W27; the clause unchanged.
Why: R-1065's scope (X07a, F1, F3, X01's plugin docs) brings no registered gate criteria, and a new gate needs an RP
amendment that states them (§3.7), a `gates` entry, a clause that parses it and Frank's re-dated `Claim set` row.
0.4.0 is the precedent: MSG, ST, X04, X05, X02, OPT, RRC and F0 shipped under 0.3's claim set, each evidenced by its
own manifest and by step 1, and listed in the notes with that manifest (§10). Consequence: `Claim set`'s scope
(`extract:claim_set`, E1) is unchanged, so the row stands and Frank is not asked about the claim set unless he takes
Q-F2's alternative. Rejected: a gate for X07a (it would need criteria for the Windows and macOS legs at C, which RP
§6.2 does not read; Q-F2) and a gate for the roadmap line acceptance (D-3).

**D-2. No gate criterion changes; `gates[*]` is 0.4's.** No RP amendment is proposed. Criterion documents that
changed since 0.4.0 keep their paths, so the entries stand; the verdict reads them at C. One such change is
material for the verdict: W23's `docs/derivations/M04-spec.md` gains Amendment 4 on `wp/X07a` (R-1068: A36's
application half on A17; §6.2's ties erratum; "A36's status unchanged"). T(g) is not extended to `tests/test_f1_*`,
`test_f3_*`, `test_x07a_*` or `test_x01_*`: no claimed gate's criteria name those packages, and step 1 (`[1, "*"]`)
already runs them on the Linux legs. Every step-17 pair is unchanged; `WHEEL-F1-F3` is judged by RP.S13, as
`WHEEL-DATA` is.

**D-3. The roadmap's 0.5 line acceptance is not a release gate**, as 0.4's was not (its own clause was moved by Frank
on decision board `rel04-line-acceptance`). Its state at `d29f1a50`, for Frank (Q-F1):
- "ADR-F1 to ADR-F8 Accepted" (kept in 0.5 by Amendment 1): **not met**. 0060 (F1) and 0061 (F3) are Accepted; 0062
  (F2), 0063 (F4), 0064 (F5), 0065 (F6), 0066 (F7) and 0067 (F8) are Proposed.
- "0.3.0 bundles replay everywhere": met only in the X07a ruling's R1.4 reading. On the registered Linux pair, F0 M7
  replays the 52 bundles to their registered verdicts; on macOS and Windows a Linux bundle is
  `inspected_archived_results` / `NOT_RUN` with `integrity_ok` (R-1062), which F0 M7 judges as that platform's
  expected verdict. They are inspected there, not reproduced. Phrase 4 says so.
- The v2-revision clause ("a v2 revision with store-pinned records solves on the legacy route on all three OSes")
  moved to 0.6 with F2 and F8 (Amendment 1). 0.5 claims nothing about v2 revisions: phrase 20.

**D-4. The phrases.** 22, in this order. Unchanged phrases keep 0.4's text; the changed and new ones, with sources:

| # | Phrase | Source |
| --- | --- | --- |
| 3 | the release is judged on Linux only, not on Windows or macOS | RP §6.2 and `scripts/release_rc.py` `LEGS` (step 1 reads the two Linux `check` legs); steps 2 to 17 run on `ref-x86-64` or the Linux CI legs |
| 4 | bundles reproduce across platforms only between Linux x86-64 and aarch64 | ADR 0007 D3.3 and Amendment 3 (R-1062) |
| 5 | the nlp and reactor environments and the coolprop extra are Linux only, and Windows refuses external models | the envelope's Platforms row on `wp/X07a`; ADR 0033 D2 |
| 17 | no W27 claim in 0.5.0 | Q-14's rule: the version follows the release |
| 20 | no v2 revision documents | Amendment 1 (the v2-revision clause moved to 0.6) |
| 21 | no solve reads the component record store | ADR 0061, Migration proof item 4 ("Nothing in v1 reads the store"); only v1 revisions exist in 0.5 |
| 22 | a plugin adds no unit model or property method that a solve uses | `docs-site/guide/plugins.md` on `wp/X01` ("What a plugin can do in this release", "Selectability") |

What 0.5 may say about Windows and macOS (the brief's question): that Windows x86-64 and macOS arm64 run the CI suite
with X07a's registered platform limits, cited in the notes under X07a with its manifest and that manifest's CI run, and
that a bundle made there replays exactly on the same platform identity (R-1062). It may not say that they are judged at
C, that bundles reproduce across operating systems, or that the nlp, reactor or coolprop environments or external
models work there. Phrases 3 to 5 are chosen to stay true whatever the Windows and macOS legs show at C and whether or
not X07a merges: a phrase is in the line file, and a line-file change after C needs a new C (A-3).

Each phrase must occur exactly once in `CHANGELOG.md`'s `## v0.5.0` section, package text included (RP.S10 counts
substrings: `section.count(phrase) == 1`). The X07a, F3 and X01 entries must therefore paraphrase, not repeat, phrases
3 to 5 and 20 to 22. No phrase is a substring of another (measured, §7).

**D-5. `WHEEL-F1-F3`, a new item.** RP §3.6 item 4 keeps `WHEEL-DATA` as it is only if a release ships no package data
beyond the previous one's. 0.5 does: F1's `registry/builtin/{core,legacy,records}.json` and `tables.sha256`, F3's
`records/{legacy_index.json,legacy_profiles.yaml,rights-register.json}`, and five schemas under `_data/schemas`.
Step 3 (T08.A43) already proves the wheel holds every declared package-data file byte-equal to C. Nothing proves the
installed package uses them. Step 4 solves and replays from the wheel, but the legacy record store is filled at its
first access (`records/stack.py` `LegacyStore`) and the registry is built by `default_registry()` on demand, and
neither a v1 solve nor a replay calls them (the binder reads its own table, ADR 0060 D6 and the plugin guide's
"Selectability"; "Nothing in v1 reads the store", ADR 0061's migration proof). A runtime file read from a repository
path, or left undeclared, would ship broken and pass every step. The item closes that, and only that.

`{"id": "WHEEL-F1-F3", "script": "scripts/wheel_data_check.py", "where": "local:project", "command": ["python",
"scripts/wheel_data_check.py", "--commit", "$C", "--f1-f3"]}`. The script is `WHEEL-DATA`'s standing owner (§3.3),
whose A19 probe already runs in a fresh venv from the wheel; `--f1-f3` does not exist yet. Until the build lane adds
it, the command exits 2 (an unrecognised argument) and the item fails at step 17, visibly (RP.S13). Assertions, all
exact (digests and ids compared as strings, counts as integers; there is no floating point, so no tolerance):

- **WF-1** `wheel.built`: as `WHEEL-DATA`'s: `scripts/t08_dist.py --commit C` exits 0 and its record passes.
- **WF-2** `f1f3.probes`: the probe runs in a fresh venv (`requirements.lock`, then the wheel `--no-deps`), with `-I`
  from an empty directory, and once in the checkout at C (A19's `--in-checkout` pattern); both exit 0, and both find no
  entry point in group `openflowsheet.extensions` (otherwise the check fails with the names: WF-3 compares built-in
  registries only).
- **WF-3** `f1.registry_sha256`: `list_capabilities()` through the Python binding (`LocalApplication.in_memory()`, as
  `tests/test_f3_operations.py` builds it) returns a capability page in both, and the two `registry_sha256` are equal
  64-hex strings. Sanity value, measured in the checkout at `d29f1a50`: `fc0af96b7ba9b7259ce3c1336cf408f41c1805259859a788c4804502c5c7bcee`.
  It is not the expectation (S19 W5 may re-register it, ADR 0077); the checkout at C is.
- **WF-4** `f3.legacy_records`: `search_records(limit=200)` followed through `next_cursor` to the end gives, in both,
  items whose `store` is `legacy`; the sorted `(id, record_sha256)` lists are equal; and their length N equals the
  number of `records` entries over `files` in `src/openflowsheet/records/legacy_index.json` at C, read by the script
  from that file, not through the code under test, with N ≥ 1 asserted. Measured at `d29f1a50`: one page, 149 items,
  149 distinct SHAs, and 9 + 5 + 1 + 123 + 4 + 4 + 3 = 149 index records.
- **WF-5** record and controls: one line per check, the findings as one JSON line (the two digests, N, the wheel's
  SHA-256), last line `wheel data check (F1, F3): PASS|FAIL`; exit 0 if and only if WF-1 to WF-4 pass, 1 otherwise,
  2 when the checkout is not at C. The script's tests carry four controls, each of which must fail its check: (a)
  `openflowsheet/registry/builtin/core.json` deleted from the installed package (WF-3: the call raises or the digest
  differs); (b) the installed `openflowsheet/records/legacy_index.json` deleted (WF-4); (c) a probe document whose
  digest is replaced by another 64-hex value (WF-3); (d) a probe document with one item dropped (WF-4's count).

What `WHEEL-F1-F3` does not establish: that F1's admission or F3's records are right (their manifests and reviews
carry that); anything on Windows or macOS; any plugin-discovery path (WF-2 requires none installed).

**D-6. Build-lane fields, proposed.** `name` `v0.5-gate-v1`; `covers` `0\.5\.0(?:(?:b|rc)[1-9][0-9]*)?`;
`envelope_id` `v0.5-envelope-1`; `evidence_package` `REL050`; `verdict_document` `docs/reviews/REL050-verdicts.md`;
`rc_record` `docs/REL050-rc-record.md`; `acceptances` `release/acceptances.md` (unchanged).
- `packages`: 0.4's twenty plus `F1` (`evidence/F1/a423093f…`, `tested`), `F3` (`evidence/F3/6c82b535…`, `tested`),
  `X07a` (`evidence/X07a/9773c361…` on `wp/X07a`, `implemented`, CI check `fail`) and `X01`
  (`evidence/X01/a0e4c546…` on `wp/X01`, `tested`). P1 holds only once X07a's and X01's manifests are `tested` at an
  ancestor of K3. If X07a does not merge before K3, the build lane removes it here and Frank is told: R-1065 names it.
- `required_adrs`: 0.4's 26 plus, each Accepted since 0.4.0's C:
  - 0060 (F1) and 0061 (F3): the two foundations 0.5 ships;
  - 0076 (S19 interfaces, on `main` since `a88655a2`): the Python names step 1's nodes and the bindings use;
  - 0077 (S19 W5 identity re-registration, batch N on `main`): it amends F0's registered M9 values and the built-in
    registry identity that WF-3 compares;
  - 0007 (Amendment 3, R-1062, on `wp/X07a`): the replay statement of the envelope and of phrase 4;
  - 0057 (Amendment 1, R-1065, on `wp/REL050`): the scope, and phrases 20 to 22.
  All six status lines start `Status: Accepted` at `d29f1a50` (step 18's item 7 rule, measured). 0058 and 0068 to
  0075 (accepted before 0.4.0's C) are not added: 0.4.0 did not require them, and they are not new (Q-B1).

## 6. Not established

- No verdict on any gate; the `verdict` pass does that at C. No lapse decided: §8.5's report at C does.
- Nothing about the Windows and macOS legs at C. Step 1 records the push run's overall `conclusion` in `s1.push_run`
  but judges the Linux `check` legs only.
- The 0.5 line acceptance is not judged by the release (D-3); its ADR clause is unmet at `d29f1a50`.
- P1 is not checked here (X07a and X01 are not merged). RP.L05 and RP.L08 were read at the worktree's HEAD and at
  `d29f1a50`, not at K3 or C; P4 re-reads them at K3, the gate at C.
- The WHEEL-F1-F3 sanity values are measurements at `d29f1a50`, not expectations.

## 7. The loader's check on the draft

There is no loader-only mode on the command line (`release_gate.py --help`: `--line` and `--rc` are required, and every
mode runs past the loader). The loader is `release_gate.load_line` (RP.L01 to L04, L06, L07, L08's ids, L09 to L11)
plus `release_gate.tree_problems` (RP.L05, L08's scripts, at a commit's tracked paths). Measured 2026-11-21 in the
worktree (`wp/REL050`, base `c4a91a75`), with `PYTHONPATH=src`, the venv's Python and the scratch driver that calls
those two functions on `release/lines/0.5.json`:
- `load_line("0.5")`: PASS. `tree_problems` at the worktree's HEAD and at `d29f1a50`: PASS.
- Controls, each refused by its own check (the control's field also put in or taken out of `changed`, so that RP.L03
  and RP.L04 do not refuse first): RP.L01 `policy_adr`; RP.L02 `inherits` `0.5`; RP.L03 `W27` added to `claimed`,
  and `rc_items` dropped from `changed`; RP.L04 `gate_set.claimed` in `changed`; RP.L06 `X31` removed; RP.L07
  `[17, "NO-SUCH-ITEM"]`; RP.L08 a duplicated id; RP.L09 `W27` in the clause; RP.L10 `["W27", "M02 N1"]`; RP.L11
  `REL040`. All eleven refused.
- `changed` equals the computed set of differing compared fields (ten). 22 phrases, distinct, none a substring of
  another.
- `required_adrs` Accepted (v0_2_gate's `adr_problems`): PASS at `d29f1a50`; at the worktree's HEAD, 0061 fails
  because `wp/REL050` does not hold F3's acceptance yet (it holds `c4a91a75`). Merging `main` into the branch clears it.
- `tests/test_rel_release_gate.py`, `test_rel040_ledger.py`, `test_rel_ci_release_rc.py`, `test_rel_evidence_manifest.py`
  with the draft on disk: 107 passed.

The build lane's command at K3 (P4), until a loader mode exists, with `<K3>` the full id:

    PYTHONPATH=src .venv/bin/python -c "import subprocess, sys; sys.path[:0] = ['scripts', 'src']; import release_gate as rg; \
    read = lambda p: subprocess.run(['git', 'show', f'<K3>:{p}', '--'], capture_output=True).stdout or None; \
    line = rg.load_line('0.5', read); \
    paths = subprocess.run(['git', 'ls-tree', '-r', '--name-only', '<K3>'], capture_output=True, text=True).stdout.splitlines(); \
    found = rg.tree_problems(line, paths); print('\n'.join(found) or 'RP.L01-L11: PASS'); sys.exit(1 if found else 0)"

A `LineError` traceback is the refusal, with its reason.

## 8. Open questions, each with a default

- **Q-F1 (Frank's preference): the line acceptance's "ADR-F1 to ADR-F8 Accepted".** Default (recommended): move the
  clause to 0.6 with F2 and F8, by Frank's amendment of ADR 0057 D6 and `roadmap.md`, as `rel04-line-acceptance` moved
  it from 0.4. Why: F4 to F6 are built in 0.6 against the same v2 records (R-1065's reason), and accepting their ADRs
  now gains 0.5's users nothing. Alternatives: hold 0.5 until 0062 to 0067 are accepted (each a card after its W1
  review); release with the clause recorded as unmet in the notes. The line file is the same under all three.
- **Q-F2 (Frank's preference): should the release judge the Windows and macOS legs at C?** Default: no; they are
  X07a's package evidence, and phrase 3 says the release is judged on Linux. Alternative: an RP amendment to §6.2
  (step 1 reads four `check` legs) and a change to `release_rc.py` `LEGS` and its record ids, reviewed; that adds a
  stop on any Windows or macOS failure at C and a `Claim set`-level change for Frank.
- **Q-D1 (design lane, orchestrator): RP §13 (3)'s `reviewer` pass.** Default: yes, one pass scoped to
  `git diff 84c66547 <K3> -- scripts/release_*.py scripts/v0_2_gate.py scripts/t08_rc.py scripts/m07a_rc.py
  scripts/wheel_data_check.py release/ docs/derivations/release-procedure.md`, which holds R-912's grammar, A-12,
  A-13, X07a's `git show ... --` and `as_posix` changes, links c_9 and c_10, and `--f1-f3`. Earlier package reviews
  (V04-after, X07a) are read, not redone.
- **Q-B1 (build lane): 0.4-era packages and ADRs** (MSG, ST, X04, X05, X02, OPT, RRC, F0; ADRs 0058, 0068 to 0075).
  Default: not added (0.4.0's precedent; their evidence was judged at 0.4.0's C). Adding them changes no design field.
- **Q-B2 (needs a fact): `--f1-f3` with its four controls before K3.** Default: the build lane implements D-5 as a
  work order before K3. If it is not done, step 17 fails and §12 stops the cut; dropping the item instead is a
  design-lane edit of `rc_items`, recorded in the verdict as not established.
- **Q-B3 (preference): a standing phrase test.** Default: the build lane adds to `tests/test_rel_release_gate.py` a
  test that no phrase of any `gate` line file is a substring of another, so RP.S10's count cannot fail at the cut for
  that reason.

## 9. For Frank's message 1 (RP §8.5, §9.2 step 2)

The claim set is unchanged, so its row stands. Expected in the batch, the lapse report deciding: Q-F1; Q-F2; and the
rows whose scopes moved since 0.4.0, predicted from the scopes at `d29f1a50`: `V17 carry` (`LINKS` gained c_9, R-1030,
F1, and c_10, R-1051, F3), `V14 (b)` (`src/openflowsheet/**` changed), `M02 N1` (`adapters/external/` changed), and
`M03 N1` if its audit files move at the TR09 cut. `X31 (c)` and `coolprop and lca licences` are predicted to stand.
