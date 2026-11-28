# LINE06-R-REV: reviewer pass on the 0.6.0 release machinery (RP §13 (3))

Design lane, `reviewer`, 2026-11-28. Read at `wp/REL060` HEAD `4862f5ab` (code at `2b42556e`). Scope:
`git diff 43f0b7f5..2b42556e -- scripts tests release`: `scripts/release_rc.py junit-cases` (item `F2-THREE-OS`,
`tests/test_rel_junit_cases.py`), `scripts/wheel_data_check.py --f2` (item `WHEEL-F2`, `tests/test_rel_wheel_f2.py`),
and `release/lines/0.6.json`'s two items against `docs/briefs/REL060-line-0.6.md` D-3 (TO-1 to TO-6) and D-5 (WV-1
to WV-6), with R-WV-1 to R-WV-4 of `docs/REL060_DECISIONS.md`. Status words: this document reviews; it sets nothing
`reviewed` and edits no code, line file or note.

## Verdict

**Merge after fix F-1.** One clause of WV-5 can pass while false. F-2 and F-3 should be fixed before the RC; F-3
needs a design-lane decision. Everything else in scope is sound (see "Sound").

## Fixes (each with its acceptance check)

- **F-1 (must fix): WV-5's "the base's v2 is admitted" is not checked.** `_admission`
  (`scripts/wheel_data_check.py:567`) records `{"admitted": type(report).__name__}`, and `f2_findings` (`:654`)
  requires only that the key is `admitted`. `check_admission(revision=...)` does not raise for every non-admission:
  `capabilities.admission_report` returns an `AdmissionReport` with `admitted = all(pair.admitted ...)`
  (`application/capabilities.py:379-381`). A base v2 whose report says `admitted: false` passes `f2.refusal`, so
  D-5's guard "the refusal is not the probe failing everywhere" is vacuous. Control (e)
  (`tests/test_rel_wheel_f2.py:252`) has the same blind spot: it asserts `"AdmissionReport"`, not admission.
  Correction: record `{"admitted": bool(report.admitted)}` and require `== {"admitted": True}` for the base's v2.
  Acceptance: control (e) asserts `{"admitted": True}`; a new edit `refusal.v2 = {"admitted": False}` fails exactly
  `refusal`; `pytest tests/test_rel_wheel_f2.py` passes. Measured here at `4862f5ab` (project venv, `PYTHONPATH=src`):
  the base's v2 and control (e)'s N both give `admitted True`, 7 of 7 pairs, so the item's passing run stays PASS.
- **F-2 (should fix): TO-2's step-1 comparison skips silently and is tested only against an imitation.**
  `release_rc.py:347-348` compares only when `s1.junit.files["junit-<leg>"]["pytest.xml"]` is found; any key mismatch
  is a skip, i.e. a pass. Today the keys agree (read: `step1_checks` writes `junit-x86_64` / `junit-aarch64` keyed by
  `path.name`), but the fixture `_step1` (`tests/test_rel_junit_cases.py:52`) is hand-written, R-TO's live read used
  a step-1 record holding the run id only, so the RC is the first live use. Correction: build the test's step-1 record
  with `release_rc.step1_checks(...)`, and add `compared_with_step1: [legs]` to `legs.junit`. Acceptance: a test
  asserts `compared_with_step1 == ["x86_64", "aarch64"]` on the passing fixture, and the existing hash-mismatch test
  still fails exactly `legs.junit`.
- **F-3 (should fix, needs a decision): the run case's count is not pinned.** TO-3 to TO-5 hold for any non-empty
  set equal on all legs; the count case pins `len(RUNS) == 56` (`tests/test_f2_amendment9.py:81-84`), not how many
  parametrised cases ran. A deselection uniform over the legs (a marker deselected in `check.sh`, a collection hook)
  leaves, say, 10 run cases on every leg and the item passes, while D-3 states the item reads all 56. Recommended:
  an exact count in argv (`--case <file>::<test>=56`, `=1` for the count case), checked in `legs.cases` and recorded,
  a `changed`-visible line-file field (D-3 already measured 56 + 1 on all four legs). Alternative: accept D-3 as
  written, relying on four-leg equality. I would pin.

## Notes (no action required)

- N-1: TO-1's `status == completed` clause has no control (no fixture with a run in progress); control (d) asserts
  membership (`in`), though only `legs.cases` fails. Cheap to tighten.
- N-2: `f2_inputs` (`wheel_data_check.py:468`) does not assert that `openflowsheet` is imported from `ROOT/src`, as
  the checkout probe does (`:586`). The item is safe (`local:project` sets `PYTHONPATH=src:ROOT`); a hand run in a
  worktree with main's editable venv builds the inputs from another tree.
- N-3: the last line is `junit cases (<id>): PASS (<path>)` (`t08_rc.finish`), not TO-6's literal; the same form as
  every `release_rc.py` step, and the item is judged by exit code.
- N-4: reused directories. With a reused `--out`, a stale `f2-installed.json` feeds WV-3 to WV-5 when the install
  fails this time (the item still fails through `f2.probes`). A second `junit-cases` into the same `<rc>` may hit
  `gh run download` refusing existing files (not verified here) and report the legs `absent`. The item command uses a
  temporary directory and a fresh `<rc>`.
- N-5: a `gh` failure or malformed junit XML ends in a traceback, exit 1, no record. Fails safe, as step 1 does.

## Rulings on the engineer's readings

R-WV-1 (`f2.inputs` as its own check, required for exit 0), R-WV-2 (`git show C:`), R-WV-3 (threads checked, not
only set), R-WV-4 (one manifest, 64-hex values, other exceptions fail WV-5): adopted, all stricter than D-5 without a
new value. R-TO's strict readings (TO-1 without `conclusion`, duplicates kept, every leg in `same_set`): adopted.

## Sound (examined)

- `junit_matches`: classname `F` with `/` as `.` and `.py` dropped; name `T` or `T[` prefix (no `T_extra` match);
  failure, error and skipped children all caught (xfail is `skipped`); `legs.cases` fails per leg and case.
- `legs.same_set`: every leg required, sorted lists compared, and the digest of the `\n`-joined UTF-8 names recorded.
- Exit codes: 2 off C (head check precedes the subcommand), on a malformed `--case`, on empty or repeated legs; 0 iff
  every check passes, else 1, in both scripts.
- The line file: both argvs parse against the built argparse; `$C` and `$RC_OUT` are runner values; leg names equal
  `ci.yml:199`'s expression (`Windows-X64`, `macOS-ARM64`); both case ids are module-level in
  `tests/test_f2_amendment9.py`, and the parametrisation and the count test read the same `RUNS`.
- WV-3: a fresh in-memory project per document; v2 and v1 compared on r0 and the whole `artifacts` index. WV-4: the
  registry read with `git show` at C, 64-hex required, never through the code under test (test `both versions
  answer wrongly alike` fails exactly `r0_registered`). WV-2: `-I` from an empty directory, `site-packages` required,
  the checkout side's import from `src/` enforced.
- Controls (a) to (e) fail for the stated reason: (a) v1 runs on the same copy, so the deleted schema is the only
  difference; (b) names `component:CH3OH`; (c), (d) are edits of a passing pair; (e) also fails `f2.inputs`.
- Digests are of the right bytes: downloaded junit files, canonical documents, canonical `artifacts` index, the
  installed wheel file.
- Nothing outside `scripts/`, `tests/`, `release/lines/0.6.json` and `docs/` changed; no `src/` or `ci.yml` edit.

## Not examined

`t08_dist.py` (WV-1, unchanged precedent); the real WHEEL-F2 run log at `bb4ee987` and the push run's artifacts (the
orchestrator's facts were taken as given); how the installed side resolves `record_source` from package data (the
real run passed); `exact()` beyond enums and floats.
