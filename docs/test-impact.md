# Test-impact selection (S16)

`scripts/test_impact.py` runs, for a change, only the tests the change can affect. It is an
**inner-loop aid**: a refactor step runs its selection in minutes instead of the full suite's hour.
It is never a merge gate. CI on both architectures stays the merge condition into `main`, with F0
(`scripts/corpus_identity.py --check`) after the merge (CLAUDE.md, "Gate by risk"; R-1040).

## Install

The tools live in their own venv, so the main `.venv` and the release identity stay unchanged
(`requirements.lock`'s hash is what run manifests record, R-140):

```sh
python3.13 -m venv .venv-testmap
.venv-testmap/bin/python -m pip install -r requirements.lock
.venv-testmap/bin/python -m pip install --no-deps --require-hashes -r requirements-coolprop.lock
.venv-testmap/bin/python -m pip install --no-deps -e .
.venv-testmap/bin/python -m pip install --no-deps --require-hashes -r requirements-testmap.lock
```

`requirements-testmap.lock` pins coverage, pytest-cov, pytest-xdist (and execnet) and pytest-timeout. `build` puts
two files into this venv's site-packages: `ofs_testmap_runtime.py` (a copy of
`scripts/test_impact_runtime.py`) and `ofs_testmap.pth`, which imports it at every start-up. The
runtime does nothing unless a build is active; nothing is written into the repository.

## Build a map

```sh
.venv-testmap/bin/python scripts/test_impact.py build --base <sha> --workers 12
```

`build` checks the base out into a scratch worktree, runs the default-marker suite there (pytest's
default selection, as `scripts/check.sh` runs it) under coverage, and writes the map to
`~/.cache/openflowsheet/testmap/<sha>/` (`map.sqlite`, `meta.json`, `build.log`), keyed by the base
commit and its tree hash. `--out DIR` puts it elsewhere; never commit a map. One summary line comes
back: tests and outcomes, pytest's exit code, wall time, map size.

The map records, per test:

- the lines of `src/`, `scripts/`, `benchmarks/` and `tests/` it executes, its subprocesses included
  (98 test files spawn the CLI; each child starts coverage itself and inherits the test's context
  through its parent process);
- every repository file it, or a Python subprocess of it, opens for reading (an audit hook on
  "open"): the message catalogues, `schemas/*.json`, the MCP description files, benchmark data and
  fixtures;
- the class-, module- and session-scoped fixtures it uses. Work done while such a fixture is set up
  is recorded under the fixture and counts for every test that uses it.

Work at import or collection time is recorded under the collection context. To keep it there and not
in whichever test imports a module first, the build imports all of `openflowsheet` and `benchmarks`
at the end of collection and snapshots the state of every repository module then (its globals, the
contents of its module- and class-level dicts, lists and sets, and the attributes of its module-level
instances). Before each test it restores that state, drops repository modules a previous test
imported, and clears every `functools` cache of the repository. Each test so starts as it would in a
fresh process after collection, and work a memo or cache would otherwise have done once, for the
first test, is attributed to every test that needs it. At a9e733e4, 5 of 20284 tests fail under the
build and pass without it (docs/S16_DECISIONS.md, B-6); their map is that of the failing run.

`--workers N` runs the build under pytest-xdist; the context of a test is per worker process, so
attribution does not change (measured: docs/S16_DECISIONS.md). One test file has node ids that
differ between processes and runs in a second, serial call (`XDIST_SERIAL`). A build with extra
pytest arguments (`build -- tests/test_x.py`) is a partial map, which `select` refuses.

## Select and run

```sh
.venv-testmap/bin/python scripts/test_impact.py select --base <sha>
.venv-testmap/bin/python scripts/test_impact.py run --base <sha> [--workers 12] [-- PYTEST-ARGS]
.venv-testmap/bin/python scripts/test_impact.py select --base <sha> --lines src/x.py:120-134
```

`select` compares the working tree with the base (staged, unstaged and untracked files) and prints
the selected test files, one per line, on stdout, with the count or the fallback reason on stderr.
Every selected node id is widened to its whole file: a module-scoped fixture or cache makes a file's
later tests depend on lines only its first test records, and some files' tests depend on an earlier
test's state (S16 B-11). `select --nodes` prints the node ids before widening. Exit 0 is a
selection, exit 3 means "run the full suite", anything else is an error. `select` needs only the
standard library, so the main `.venv` can run it too.

`run` runs the selection (whole test files through an `@file`, without shell splitting) or, on a fallback,
the full default-marker suite, and prints one line: selected count, fallback yes or no, pytest's
counts, wall time; the full log goes to `$TMPDIR/test-impact-<sha>.log` (or `--log`). `--workers N`
runs it under pytest-xdist and, like `build`, keeps the `XDIST_SERIAL` files out of the xdist call:
they run in a second, serial call, on a fallback and whenever the selection holds them (B-12).
`-n` after `--` is refused for that reason. The line sums both calls' counts; the exit code is
nonzero when either call fails (a call that collected nothing, exit 5, counts only if both did).
`--workers` needs pytest-xdist, which only the test-map venv has. `--repo DIR` (before the
subcommand) selects in another checkout.

`select --lines PATH:START-END` lists the tests that execute those lines at the map's base, for a
refactor loop's "the target must be covered" check and for mutant checks.

### How a change maps to tests

- A changed `.py` line maps through line coverage at the base's line numbers: the tests that
  executed the statement holding it. A line the change adds or rewrites selects every test that
  executed any line of the enclosing function's body (the base's function of the same qualified
  name).
- A new function or method (undecorated, in a module or a class without bases, with a name that
  occurs nowhere in the base's tree as a whole word) selects nothing by itself: only changed code
  can call it, and that code selects its own tests. This is what makes an extract-function step
  cheap. A new def whose name the base mentions anywhere (an import, an assignment, a local, a
  method of another class, a `getattr` literal) may shadow or override it and falls back (B-13).
- A blank or comment-only line selects nothing.
- A changed test module selects all of its own tests (the file) plus its lines' normal mapping.
- A non-`.py` file maps through the open record: the tests that opened it.
- `docs/` selects nothing, except a docs file a test opens.

One map serves a campaign of refactor steps while the base stays an ancestor of `HEAD` and every
changed file is one the map has seen.

## Fallbacks to the full suite

`select` falls back, and says why, when:

- a `conftest.py`, a `tests/*_support.py`, anything under `tests/support/`, `pytest.ini`, `tox.ini`,
  `setup.cfg` or the pytest section of `pyproject.toml` changed;
- a file under `tests/` that is not a test module changed (data, fixtures, helpers);
- a file was added or deleted anywhere but `docs/`, or changed type or mode;
- import-time code changed: a module- or class-level statement, a `def` or `class` header, a
  decorator, a test module's module-level code;
- a changed line, or a file a test opened, ran or was read at import or collection time in the
  pytest process (every test may depend on it);
- the base is not an ancestor of `HEAD`;
- the map is missing, is a partial run, or is not of the base (commit and tree hash);
- a changed file the map has never seen (a `.py` file nothing executed and nothing opened, a data
  file nothing opened);
- a changed `.py` file does not parse.

## Limitations

- Selection is an inner-loop aid only. CI on both architectures stays the merge gate.
- The open record sees only Python-level opens. Files read by a non-Python child (git, bash, node)
  are invisible to it; a file only such a child reads is "never seen" and falls back, but a file
  read both ways maps only to its Python readers.
- Coverage and the open record follow Python subprocesses of the test-map venv's interpreter. A
  child run by another interpreter, or killed before it exits, is not recorded.
- Work done in a fixture's teardown counts for the test during whose teardown it ran.
- State the restore does not reach (an attribute of an object held deeper than a module-level
  instance, a class attribute rebound by a test, state outside the repository's modules) can still
  attribute shared work to the first test that does it.
- A new def is found by code that enumerates a namespace (`vars(module)`, `dir()`,
  `inspect.getmembers`) without naming it; that code is not selected. At a9e733e4 three tests do so
  (`test_st_core.py::test_c8…`, mutable module state; `test_s11_thermal_verifier.py`, which patches
  every callable of `kernel`; `test_t07_w5a_operations.py`, public methods of `Protocol` classes,
  which have bases and are never fresh); none changes its verdict for a new, uncalled function.
- A change that only moves lines (a comment, a blank line) selects nothing, although line numbers in
  tracebacks and warnings move.
- `node --test` (the web shell's tests in `tests/web/`) is not mapped: a change under `tests/web/`
  falls back as a file under `tests/` that is not a test module, and a change to `apps/` that only
  the Node tests read is "never seen".
