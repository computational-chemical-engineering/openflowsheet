# S16 build decisions: test-impact selection

Build lane, branch `wp/S16` from `main` a9e733e4. Frank: full work package, no design pass, one bounded
reviewer pass later. Tool: `scripts/test_impact.py` (+ `scripts/test_impact_runtime.py`), docs
`docs/test-impact.md`, register R-1040, recall driver `scripts/s16_recall.py`. Host SMM-TR09, 16 cores.

## Decisions

- **B-1. R-1040, not R-1033.** F1 reserved R-1030…R-1039 (F1_DECISIONS W4a-11) and the F1 design follow-up
  keeps R-1033…R-1039 free for F1 (`docs/reviews/F1-design-followup.md:119`). S16 takes the first number
  outside any block. Revert: renumber one heading and three mentions.
- **B-2. The build uses the coverage API through its own runtime, not pytest-cov.** The test's node id must
  reach coverage, the open-file record and every subprocess alike. A child finds its context through its
  parent chain (`/proc`, a per-process context file), so a test that scrubs the environment is still
  attributed; the environment variable is the fallback for a re-parented child. pytest-cov stays in the lock
  as the brief asks (ad-hoc `--cov` runs); the build does not load it.
- **B-3. Shared fixtures are contexts of their own.** Work done while a class-, module-, package- or
  session-scoped fixture is set up is recorded as `fixture:<baseid>::<name>` and maps to every test that
  uses the fixture. Without it, a session fixture's simulation counts only for the first test.
- **B-4. pytest-xdist and `XDIST_SERIAL`.** `tests/test_t07_w2d_noncanonical.py` has parameter ids holding
  object addresses (`<…_RepeatedKeys object at 0x…>`), so xdist aborts with "Different tests were
  collected". The test file is not edited (outside S16); a build with workers runs it in a second, serial
  call, and so does the recall driver.
- **B-5. Import-time code falls back.** A changed module- or class-level statement, `def`/`class` header or
  decorator, and any changed line covered in the collection context, falls back to the full suite. Lines a
  function body adds or rewrites select every test of that function (the base's function with the same
  qualified name). A new undecorated function or method with a fresh name (a method only in a class without
  bases) selects nothing by itself. A blank or comment-only line selects nothing.
- **B-6. Each test starts from the post-collection state.** The first equivalence runs (serial against
  `-n 4`, five test files) differed in 37 then 24 (file, test) line sets: a memo, a lazily imported module or
  a cache filled by an earlier test in the same process hid shared work from later tests, which would
  miss tests. The runtime now (a) imports all of `openflowsheet` and `benchmarks` at the end of collection,
  (b) snapshots every repository module's state then and restores it before each test, dropping modules a
  previous test imported, (c) clears every `functools` cache of the repository. After it, 5 line sets of
  1101 differ, all in `tests/conftest.py` (a conftest change falls back anyway) and `run/lock.py`'s
  installed-version lookup; opens and fixtures are identical, outcomes equal (53/53).
  Cost: at a9e733e4, 5 of 20284 tests fail under the build and pass without it:
  `test_m04_wo9_synthetic_loop.py::test_a25…` and `::test_a29…`, `test_x02_wo4_external.py::test_g4e_an_edited_start_diverges`
  and `::test_g4e_replay_of_the_chained_run_matches` (module-scoped state the restore resets), and
  `test_t07_v17_reference.py::test_f6_the_forty_runs_fit_their_budget` (331 s against a 300 s budget under
  coverage). Their map is that of the failing run. Open: re-snapshot after each shared fixture's setup.
- **B-7. Open record filters.** Imports (frozen importlib frames) and pytest's own reads are not recorded;
  directory opens and paths relative to a `dir_fd` (which `shutil.rmtree` uses) are dropped.
- **B-8. tests/ data falls back.** As the brief states, a changed file under `tests/` that is not a test
  module falls back, fixtures and data included; they are not mapped through the open record.

## Measurements

- Map build at a9e733e4, `--workers 12`: 4204 s wall (xdist part 4108 s, serial part 94 s), 20284 tests
  (20170 passed, 109 skipped, 5 failed: B-6), map 25.0 MB (259095 line rows over 24243 distinct bitmaps,
  213793 open rows, 20430 contexts). 1756 files are opened at collection time (their changes fall back).
  The build ran beside the serial baseline below, so its wall time is an upper bound.
- Overhead on two test files: 128 s instrumented against 54 s plain (2.4x).
- Serial baseline at a9e733e4 (`.venv-testmap`, threads 1): 20175 passed, 107 skipped, 3 xfailed, 5252 s
  (beside the build; F1 measured 4570 s on a quiet host).
- xdist on the whole suite: see "Recall", baseline line (the recall driver's base run is the `-n 12` run).

## Recall

Driver: `scripts/s16_recall.py --base a9e733e4 --map ~/.cache/openflowsheet/testmap/a9e733e4… --workers 12`
(17 seeded cases: 10 in `application/`, 4 elsewhere in `src/`, 3 data files; 2 refactors). Results:
pending at the time of this commit; see the next commit.

## T08 harvest and the manifest (stopped, escalated)

`scripts/t08_support_matrix.py` (A21) classifies every `limitations[]` entry and non-pass check of every
`evidence/**/manifest.json` except `evidence/REL040/`; an unclassified item fails `--check` and the
`tests/test_t08_w2_support_envelope.py` family. A S16 manifest with limitations therefore needs harvest
rows in `benchmarks/t08/support_envelope.yaml`, a D2.4 path. Per the brief, the manifest is not committed;
the envelope is untouched. Choice I would make: a harvest commit in F1's form (`B`/`S` classes for the
limitations) by whoever may change D2.4 paths, then the manifest.

## Not done

- (b) history replay: each of ~10 bases needs its own map, 70 min each with 12 workers here: about 12 h,
  and merged commits pass their suite, so recall would be vacuous. Not done.

- **B-9. A per-test timeout in the recall (2026-11-12, orchestrator).** The first recall run hung on case
  `app-owner-instance`: with `owner_instance=None`, `store.start_job` fences on `owner_instance = ?`, which never
  matches NULL, so `executor._run` returns, the job stays queued and `_wait_until_ended` (local.py) waits with
  `math.inf`. One worker spun for 5 h; after it was killed, a second test waited idle for 2 h more. The run was
  stopped. `requirements-testmap.lock` now pins pytest-timeout 2.4.0 and `scripts/s16_recall.py` passes
  `--timeout=900` to every pytest run, the full suite and `test_impact.py run` (slowest baseline test 337 s with 12
  workers). A timed-out test fails, so the hang counts as a detection with the test named. The silent queued job is
  a product weakness, outside S16. Alternative: an external watchdog (it missed the idle wait). Reversible by: this
  commit.
- **B-10. app-owner-instance runs with a 60 s per-test limit and its selected run with `-x` (2026-11-12,
  orchestrator).** Run 2 (B-9 limits) stalled on this case: 669 tests execute the mutated `_context` body
  (`select --lines src/openflowsheet/application/local.py:429-431`), and each that waits for its job sits out the
  limit, up to 14 h at 900 s with 12 workers. At 60 s the full run takes at most about an hour. A slow test cut
  off by the lower limit (16 baseline tests exceed 60 s) can only add a false miss, which is checked by hand; it
  cannot hide a real one. The selected run is serial and only has to fail, so it stops at the first failure.
  Other cases keep 900 s. Reversible by: CASE_TIMEOUT and CASE_RUN_ARGS in scripts/s16_recall.py.
- **B-11. `run` and `select` widen to whole test files (2026-11-13, orchestrator).** Recall run 3 (B-10): 16 of 17
  cases 0 missed; app-owner-instance 60 missed, and both refactor cases' selected runs failed (exit 1) with 0
  failures in the full suite. 46 misses were in `test_t07_g12_no_weakening.py` (10 of its 63 tests selected): its
  `runs` cache solves on first use, so only the first test records the changed line, and the others fail with
  "idempotency key already used". The refactor failure is `test_m06_browser_smoke.py::test_g8...`, which needs an
  earlier test of its file to have solved rev-000005. Both are one cause: a file's tests share module state.
  `Selection.whole_files()` widens every node id to its file; `run` and `select` use it, `select --nodes` prints
  node ids, `select --lines` (coverage strength) stays per test. On run 3's data the widening leaves 14 misses in
  app-owner-instance (103 files), all 60 s timeouts of slow tests in files without a selected test (B-10's false
  misses; checked by running them on the mutated tree without a limit). Residual risk: a session-scoped fixture
  that runs a changed line for tests in another file; none seen in the recall. Alternative: per-fixture
  attribution of setup coverage (does not cover a module-level cache filled inside a test). Reversible by: this
  commit.
- **B-12. `run --workers N` splits `XDIST_SERIAL` as `build` does (2026-11-13, review X1).** With workers, a
  fallback runs the full suite as an xdist call with `--ignore` of each `XDIST_SERIAL` file plus a serial call of
  those files; a selection runs its other files under xdist and its `XDIST_SERIAL` files serially. One summary line
  sums the calls' counts; the exit code is the largest of the calls' codes, where exit 5 (nothing collected) counts
  only when every call has it. `-n`/`--numprocesses` after `--` is refused, because it would put the serial file
  into an xdist session (B-4). The review's serial fallback took 4570 to 5252 s, past S17's 3600 s tier; with
  `--workers 12` in `.venv-testmap` it is the build's xdist time without coverage (estimate about 13 min, not
  measured here: no full-suite runs in this round). The map lifecycle for S17 (a map per accepted step, or one
  campaign base) is S17's choice, not made here. Alternative: rewrite `-n` after `--` into the split. Reversible by:
  this commit.
- **B-13. A new def is fresh only if its name occurs nowhere in the base's tree (2026-11-13, review S1).**
  `_fresh_definition` checked only def and class names, so a new def shadowing an imported or assigned name selected
  nothing (review probe: `def state_sha256` appended to `numerics/newton.py`, which imports and calls it; 206 files
  missed). Now `git grep -w -F` of the name in the base's tree must find nothing; otherwise the new def falls back as
  import-time code. This bounds every binding in every scope (imports, assignments, loop, `with` and `except`
  targets, `global`), sibling-base methods a base-less mixin could override in an MRO, and literal
  `getattr`/`hasattr` access, without walking scopes. Checked on the real map: the probe now falls back
  (`newton.py:928: import-time code changed`). Residual: code that enumerates a namespace without naming the def
  (three tests at a9e733e4, listed in docs/test-impact.md; none is affected by a new, uncalled function).
  Alternative: an AST walk of the bindings of the def's scope (misses other scopes, MROs across files and
  `hasattr`). Reversible by: this commit.
- **B-14. An added line selects the tests of every base function with its qualified name (2026-11-13, review
  S2).** `_new_line` took the first base function of the qualified name, so a line added to the second
  `project.render` (`application/projection.py:292`, the `else` twin of :282) selected the first one's tests. It now
  takes the union of the bodies of all of them. Real map: that insertion selects 51 files, against 42 before (the
  review counted 9 missed files of 26 that execute the second `render`). Alternative: the one base function the
  hunk maps onto (needs a line mapping across the diff; the union is a superset). Reversible by: this commit.
- **B-15. A statement without a line event maps to its function's tests (2026-11-13, review S3).** Coverage never
  records `global`, `nonlocal`, `pass`, a docstring or other constant expression, or an annotation without a value,
  so deleting one selected nothing (only the file's openers). An old-side line whose statement is one of these now
  adds every test of the enclosing base function's body; at module or class level it falls back as before. Real
  map: deleting `nonlocal running` (`numerics/newton.py:301`) selects 234 files (the review counted 2392 tests in
  213 files executing `evaluate`); deleting `global auditor` in `messages/audit.py:57` falls back (`enable()` runs
  at collection), against 26 files before. Alternative: every old-side line maps to its whole function (wider for
  every deletion). Reversible by: this commit.
- **B-16. docs/ is measured, and an added or deleted docs file falls back (2026-11-13, review S4).** Tests glob the
  docs tree (`tests/test_t02_identity.py:51` unpacks `docs/adr/0007-*.md` into a 1-tuple), so an added or deleted
  file under `docs/` now falls back like one anywhere else. `docs` joins `SOURCE_DIRS`, so the build measures the 94
  `docs/**/*.py` files (tests import some in-process: `c2_openidaes450_split.py` by all 40 tests of its test file, of
  which only 3 recorded it as an open), and `select` maps a changed `docs/*.py` through `_python_rule` like source.
  A map records the directories it measured (`meta.source_dirs`); a `.py` change in a directory the map did not
  measure falls back, so the a9e733e4 map (no entry: `src,scripts,benchmarks,tests`) falls back on any `docs/*.py`
  change. A modified non-Python docs file still selects its openers. Real map: `docs/adr/0007-zz-second.md` added
  and a changed `c2_openidaes450_split.py` both fall back. Alternative: select the readers of the added file's
  directory (the open record holds files, not directory listings). Reversible by: this commit.
