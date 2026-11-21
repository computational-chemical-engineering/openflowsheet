# REL050-R: reviewer pass on the 0.5.0 release machinery, with the WF-4 ruling

Design lane, `reviewer`, 2026-11-21. RP §13 (3), line note `docs/briefs/REL050-line-0.5.md` §8 Q-D1. Read at
`wp/REL050` HEAD `6c3956c2` (code at `71a7328e`). Scope: `git diff 84c66547 HEAD -- scripts/release_*.py
scripts/v0_2_gate.py scripts/t08_rc.py scripts/m07a_rc.py scripts/wheel_data_check.py release/
docs/derivations/release-procedure.md`, `tests/test_rel_wheel_f1_f3.py`, and the Q-B3 test in
`tests/test_rel_release_gate.py`. Judged against RP and the line note's D-5. Earlier package reviews were read, not
redone. Status words: this document reviews; it sets nothing `reviewed` and edits no code, line file or note.

## Verdict

**Merge after fixes F-1 to F-3.** F-1 and F-2 are the WF-4 ruling and its consequence in the line file. F-3 is a
hang that should be a failure. Everything else in scope is sound (see "Sound").

## Ruling 1: WF-4 (adopt the engineer's proposal, amended)

D-5's WF-4 contradicts ADR 0061 D8, which the line note does not override: only the `m01` and `s10` legacy files are
package data, and a file that is not available contributes no records. The code does what D8 says
(`records/importers/legacy.py` `available_bytes`). WF-4 as written cannot pass on a correct wheel, so it is
restated. The engineer's form is adopted with three amendments: (i) each side is compared with the index's own
`(id, sha256)` pairs, not only counted, so a record that both sides return wrongly in the same way cannot pass;
(ii) the package-data set is the one T08.A43 already computes, not a second reading of `pyproject.toml`'s globs;
(iii) the page loop is bounded. Measured on the run record at `71a7328e` (`f1f3-installed.json`,
`f1f3-checkout.json`): the checkout's sorted pairs equal the index's 149, and the installed side's equal the 9 of
`m01` and `s10`. The restated WF-4 passes on that run, and D-5's other clauses are unchanged.

Replacement text for D-5's WF-4 bullet (exact):

> - **WF-4** `f3.legacy_records`: on each side, `search_records(limit=200)` followed through `next_cursor` to the end,
>   in at most ⌈N/200⌉ + 1 pages (otherwise the check fails by name), gives only items whose `store` is `legacy`, and
>   their sorted `(id, record_sha256)` list equals the sorted `(id, sha256)` list of the index records over that
>   side's files. The script reads both from `src/openflowsheet/records/legacy_index.json` at C, not through the code
>   under test. The checkout's files are every entry of `files`, with N records. The installed side's files are the
>   entries whose `path` P is package data at C: `openflowsheet/_data/P` is a key of `scripts/t08_dist.py`'s
>   `expected_package_files` at C (the files that `pyproject.toml`'s `[tool.setuptools.package-data]` patterns match
>   from the package directory, `_data/` links followed; T08.A43, inside WF-1, holds the wheel equal to that set).
>   They hold N_pkg records. The script asserts N ≥ 1 and N_pkg ≥ 1. The sides differ by ADR 0061 D8: only the `m01`
>   and `s10` component files are package data, and a file that is not available contributes no records. Measured at
>   `71a7328e`: N = 149 (9 + 5 + 1 + 123 + 4 + 4 + 3); package data `benchmarks/m01/components.yaml` and
>   `benchmarks/s10/records.yaml`, N_pkg = 9 (5 + 4); each side equals its index list.

D-5's WF-5 changes with it, and only in these places:
- The findings line holds N, N_pkg and the package-data paths, in place of N alone.
- Control (d) is "an installed probe document with one item dropped (WF-4)".
- Two controls are added, each of which must fail WF-4:
  - (e) the installed `openflowsheet/_data/benchmarks/m01/components.yaml` is deleted. The installed side then lists
    4 records against N_pkg = 9. This control proves that the expected list does not follow the installed package.
  - (f) a checkout probe document with one item dropped. The sides are no longer compared with each other, so the
    checkout side needs its own control.

`expected_package_files` is imported inside the host-side function, not at module level, so that the probe stays
stdlib-only (module docstring).

**Does this change `rc_items`? Yes, but only the `assertion` string of `WHEEL-F1-F3`; the command is unchanged.**
The brief expected no change. But `release/lines/0.5.json`'s item states the old WF-4 ("the legacy (id,
record_sha256) pairs equal and as many as legacy_index.json's records"). That text is evidence-bearing:
`scripts/release_rc.py:450` writes it into the item's RC record, and `scripts/release_evidence_manifest.py:766`
writes it into the release manifest. `rc_items` is already in `changed`, so RP.L03 and RP.L04 are unaffected. The
edit lands before K3, so A-3 (a new C) does not apply. Replacement `assertion` (exact):

> F1's registry and F3's legacy record store answer from the installed wheel as from C: registry_sha256 equal; the
> legacy (id, record_sha256) pairs equal legacy_index.json's, all of them in the checkout and those of its
> package-data files in the wheel (ADR 0061 D8) (0.5 ships package data beyond 0.4.0's, RP 3.6 item 4; WF-1 to WF-5
> of docs/briefs/REL050-line-0.5.md)

## Ruling 2: controls (a) and (b) on a scratch copy, not on a built wheel

**Sufficient** for what D-5's controls are for: showing that the check fails when an installed package lacks the
file. The deletion is real: `copytree` follows the `_data/` links, so no link back to the repository remains. The
probe imports from the copy (the fixture asserts `module_file`). No repository fallback exists from that location:
`legacy._checkout_root()` needs `<root>/src/openflowsheet`, and control (b) records `FileNotFoundError`, which shows
that no fallback was taken. An installed wheel is a plain tree under `site-packages`, read through the same
`importlib.resources` paths.

The copy also carries files that a wheel omits, so it models deletions only. It is not evidence that the wheel passes
WF-3 or WF-4. That evidence is the item's own run at C: WF-1 builds the wheel, and WF-2 runs the probe in a fresh
venv with `-I`. Condition: keep the `module_file` assertion, and build control (e) the same way as (a) and (b).

## Fixes (each with its acceptance check)

- **F-1 (must fix): apply Ruling 1** to the note's D-5 (WF-4, WF-5), to `scripts/wheel_data_check.py`
  (`f1f3_findings`, `run_f1f3_checks`, the docstring, the findings) and to `tests/test_rel_wheel_f1_f3.py`.
  Acceptance:
  - The strict xfail `test_an_intact_installed_copy_passes_wf4` becomes a plain test, and it passes with 9 against
    the index's 9.
  - Controls (a) to (f) each fail their check.
  - A new pin test asserts that the derived package-data legacy paths at C are exactly `benchmarks/m01/components.yaml`
    and `benchmarks/s10/records.yaml`, with N_pkg == 9, beside `N == 149`.
  - `pytest tests/test_rel_wheel_f1_f3.py` passes with no xfail.
  - `python scripts/wheel_data_check.py --commit <HEAD> --f1-f3 --out <dir>` on `ref-x86-64` prints
    `wheel data check (F1, F3): PASS` and exits 0, and its findings show N = 149 and N_pkg = 9.
- **F-2 (must fix): replace `WHEEL-F1-F3`'s `assertion`** in `release/lines/0.5.json` with the text above, and change
  nothing else. Acceptance: the line note §7 loader command prints `RP.L01-L11: PASS` at the new HEAD, and
  `tests/test_rel_release_gate.py` passes. A JSON diff against `71a7328e` shows only that string changed.
- **F-3 (should fix): bound the page loop** in `probe_f1f3`, which is `wheel_data_check.py:293` `while True`. `_run`
  has no timeout, so a `next_cursor` that never ends hangs step 17 instead of failing it. Stop after ⌈N/200⌉ + 1
  pages, or a fixed bound of 100, and record `records.error` = `pagination did not end`. Acceptance: a test that
  monkeypatches `LocalApplication.in_memory` with a fake whose cursor never ends gets `records.error` set and
  `legacy_records` false. The test finishes in under 10 s.

## Notes (no action required)

- `f1f3_findings` `site_packages` checks only that the path contains the substring `site-packages`. `-I` and a fresh
  venv make this enough at the run. A stricter form is "`module_file` is under `<work>/wheelvenv`".
- Pages: at C one page holds all 149 records, so the cursor path is not exercised by the run. Amendment (i) catches a
  page that repeats or drops a record.
- X07a's release-script changes (`git show <rev>:<path> --`, `as_posix`, a44 without an A30 summary off Linux) are on
  `wp/X07a`, not in HEAD's range (X07a is unmerged). I read them there. They are no-ops on Linux (`as_posix` equals
  `str` on POSIX, and `--` only ends the revision list). They need nothing beyond X07a's own review when they enter
  K3's range.

## Sound (examined)

- **R-912's grammar.** `v0_2_gate.LIMITATION` `\bL(?:\d{2}|-[A-Z][A-Z0-9]*-\d+)\b` is a superset of the old
  pattern. `test_r912_*` holds the released verdict documents byte-identical and reads `L-X04-1`.
- **A-12.** The general §4.4 and RP.S14 row order `(1,c_n)`, `(2,c_n)`…`(2,c_1)`, `(3,None)` is the order
  `m07a_rc.chain` builds.
- **A-13.** P6, the §7.1 `--old-host` text, §12 and §14 are as §17.6 states them.
- **Links c_9 and c_10.** The strip functions, pins and digests `e2c44b6b…` and `f7ec3c94…` decompose onto D_8
  (`test_f1s_…`, `test_f3s_…`).
- **`t08_rc.py` import moves (S19).** Every `from openflowsheet… import` in `scripts/*.py` resolves at HEAD (750
  checked). The only exceptions are three `studies.nlp.greybox` imports that need the nlp environment, and they are
  out of scope.
- **`release/acceptances.md`.** The lapsed rows were moved to History unedited.
- **Line file.** The `changed` set, packages and required ADRs match D-6. The new item's command and its place in
  `rc_items` are as D-5 states.
- **Q-B3 test.** It is sound and checks exactly RP.S10's substring hazard on every `gate` line file. Phrases repeated
  in package text are left to RP.S10 at the cut.
- **Clean tree.** `wheel_data_check.py` checks only HEAD == C. The RC job's `release_rc_local.py` refuses a dirty tree.
- **Tests run here.** `pytest tests/test_rel_wheel_f1_f3.py tests/test_rel_release_gate.py
  tests/test_m07a_surface_chain.py tests/test_m07_v0_2_gate.py tests/test_t08_w2_surface_digest.py`: 281 passed,
  1 xfailed (the WF-4 strict xfail).

## Not examined

- The content of `release/rc-trees/84c66547….json` (1884 lines of tool output).
- RP sections outside the diff.
- `release_gate.py` and `release_rc.py` beyond the `assertion` path, because they are unchanged in range.
- `CHANGELOG.md` `## v0.5.0`, which is not written yet.
- I did not run the item itself (`--f1-f3` end to end). The WF-4 evidence above is the engineer's run record, re-read.
