# S16 review: is test-impact selection fit to be S17's `tests` gate? (wp/S16 at 40270b62)

Reviewer: independent read, 2026-11-13. Labels: [code] = read in code, [measured] = probed against the real map at
a9e733e4 (read-only, probe script `scratchpad/s16rev/probe.py`), [estimate] = reasoning not checked by a run.
Nothing in the worktree was edited, and no suite was run.

## Verdict

Fit after named fixes. Paths and fallbacks are mostly conservative, and B-11 is correct for state of module
scope. But (1) as S17 wires it today, every fallback fails the tier, so the gate cannot pass a step that falls
back, and (2) three selection rules lose tests on exactly the edits a refactor campaign makes. Each fix is small.

## Blocking for S17 use

**X1. Neither a fallback nor a missing map can pass S17's tier** [code + measured]. Needs a decision.
- S17 runs `test_impact.py run --base {step base}` in `<main>/.venv` (s17 `docs/code-health.md:60,64`).
- Maps are keyed by the base's sha (`test_impact.py:549`). Without a map built at each accepted step, every step
  falls back with "no map" (`:176-177`).
- The fallback runs the full suite serially, because `.venv` lacks pytest-xdist (pip freeze diff: `.venv` has no
  xdist, timeout, coverage or execnet). Serial runs took 4570 to 5252 s, more than the tier's 3600 s timeout
  (`code-health.md:71`), so the tier exits 124.
- `run -- -n N`, as `docs/test-impact.md:68` suggests, puts `tests/test_t07_w2d_noncanonical.py` into an xdist
  session on any fallback, or whenever that file is selected. B-4 shows xdist then aborts. `run` (`:722-741`)
  does not split `XDIST_SERIAL` the way `build` (`:670-674`) does.
- The gate fails closed, so this is not unsound. But it fails on every step that touches a module-level line
  (imports, def headers), and that invites bypassing it.
- Fix: in `run`, split `XDIST_SERIAL` when `-n` is given. Run the tier in `.venv-testmap` with `-n 12`; a full
  fallback is then about 13 min. Choose a map lifecycle. I would build a map for each accepted step in the
  background and fall back to the xdist full suite until it is ready. The alternative, one fixed campaign base,
  is sound but accumulates diffs, so it falls back for good after the first module-level step.

## Should fix (selection rules; each loses tests on a refactor-shaped edit)

**S1. `_fresh_definition` checks only def/class names, not other bindings** (`test_impact.py:422,428`)
[measured].
- Probe: append `def state_sha256(...)` to `numerics/newton.py`, which imports `state_sha256` and calls it
  from `digest()`.
- The rule selects only the 59 tests that opened the file. 2392 tests in 213 files execute the shadowed call,
  so 206 files are missed.
- Imports, assignments and `for`/`with`/`except` targets are all ignored. So are names that code reaches
  reflectively (`getattr` dispatch, `dir()`). A method added to a base-less mixin can also override a sibling
  base in the MRO.
- Mitigation [estimate]: S17's mypy tier (`no-redef`; it covers src and benchmarks only) and ruff F811 catch
  most module-level shadowing. Nothing catches it in `scripts/` or `tests/`.
- Fix: refuse "fresh" when the base binds the name anywhere in that scope (an `ast.walk` of Store, import
  aliases and arguments at that level).

**S2. Duplicate qualnames: `_new_line` takes the first base function with that name** (`:527-533`)
[measured].
- `application/projection.py` defines `project.render` twice (if/else, lines 282 and 292).
- Probe: insert one line in the second `render`. It selects the first `render`'s 272 tests in 42 files. Of the
  26 files that execute the second `render`, 9 are missed.
- Property setters and `@overload` implementations follow the same path. In this repo the overload stubs keep
  `...` on the signature line, which runs at collection, so they fall back by accident [measured on
  `units.convert_input_value`].
- Fix: take the union over every base function with that qualname. Better: pick the one whose range the diff
  maps onto.

**S3. A pure deletion of a statement that has no line event selects nothing** (`:501-509`) [measured].
- Probe: delete `nonlocal running` at `numerics/newton.py:301`. Only the 59 file-openers are selected; 2392
  tests execute `evaluate`.
- Probe: delete `global auditor` (`messages/audit.py:57`). It selects 57 openers and does not fall back,
  although `enable()` runs at collection.
- The same holds for docstrings and for local annotations without a value.
- Ruff F823/F841 catch most of these [estimate].
- Fix: map an old-side line inside a function the way `_new_line` does: every test of the base function's body.
  At minimum, do this for `Global`, `Nonlocal` and `Expr(Constant)`.

**S4. `docs/` blind spots** (`:465-466`, `:560-562`, `SOURCE_DIRS :40`) [code + measured].
- An added or deleted docs file selects nothing. Example: `tests/test_t02_identity.py:51` unpacks
  `docs/adr` glob `0007-*.md` into a 1-tuple, so a second 0007 file breaks it and nothing is selected.
- There are 94 `docs/**/*.py` files. Coverage never sees them, and an in-process import of one is dropped as an
  import (`runtime:98-99`).
- Measured: `docs/derivations/scripts/c2_openidaes450_split.py` is imported by all 40 tests of
  `test_c2_openidaes450_split.py`, but only 3 contexts record it. It is covered today only because one of those
  3 is in that file and whole-file widening picks the rest up.
- Fix: add `docs` to `SOURCE_DIRS` and send `docs/*.py` through `_python_rule`. Make an added or deleted docs
  file fall back, or select the readers of its directory.

**S5. Tests the map does not describe** [measured + code].
- (a) The 5 tests that failed in the build have truncated line sets but are selected only by their lines. Fix:
  always add files whose `outcome` is not passed or skipped.
- (b) Fixtures used through `request.getfixturevalue` are never linked, because the runtime computes the list
  before the call (`runtime:314-321`). One orphan context exists: `fixture:tests/test_s10c_band_point.py::real`.
  I found no src line exclusive to it today [measured]. Fix: read `item.funcargs` in the `finally`.
- (c) The map holds 20284 tests, against 20285 in the serial baseline (20175 + 107 + 3), and the build never
  compares the map with `--collect-only` [measured counts; cause unknown]. A test absent from the map whose
  coverage was also lost is never selected.

**S6. Recall sample (Q4)** [code + measured].
- The metric is right: `s16_recall.py:325-327` counts a new full-suite failure, ERRORs included, as missed when
  it is outside the selection, and a fallback as complete.
- The sample is weak for S17. 6 of the 17 cases fell back, not 5. Four have 0 failures (stream-table, store-page
  and both refactors). That leaves 9 cases that measure recall, all single-token mutations of an `if`.
- A failing test necessarily executes a mutated condition, so those cases mostly confirm that coverage records
  executed lines.
- None exercises S1 to S4, cross-file state, or killed children.
- B-11's claim that the refactor cases' selected runs now pass has not been re-run [estimate].
- Fix: add about 6 seeded refactor slips (extract with shadowing, an insertion in a duplicate-named function, a
  `nonlocal` deletion, moved cache state, a reordered side effect, a docs add) and re-run both refactor cases with
  whole files.

## Q1 path by path

| path | status | reason |
| --- | --- | --- |
| module-level state | caught in the build | the runtime restore (`runtime:244-268`) |
| class-level state | mixed | contents are restored; rebinding is not (`:256` skips mappingproxy) |
| state the restore does not reach | missed | subclasses of dict/list/set such as defaultdict (`:207`), containers held by instance attributes, closures, linecache, third-party and on-disk caches |
| concrete instances in src | none found | grep found no class rebinding and no defaultdict cache. `CATALOGUE` restores through attribute rebinding [code] |
| module-scoped fixtures and caches held by pytest | caught | B-11 whole files (the g12 `_Runs` case) |
| session/package-scoped fixtures | setup caught | `fixture:` contexts (B-3) |
| lazy or stateful session fixture values | missed | none exist today: `tests/conftest.py` has only read-only dicts plus two wrappers, and there is no other conftest [code] |
| spawn subprocesses and job workers | caught | the .pth boot, context read from the parent's ctx file at boot |
| long-lived child processes | caught | attributed to the fixture or test that started them |
| SIGKILLed workers (`executor.py:105`) | lost | atexit never runs; documented |
| other interpreters (git, node, bash) | lost | documented |
| threads | caught | contexts are global; work between tests lands in `""` and falls back |
| import-time code and collection | fall back | B-5 and the `""` rule. One-line defs and overload stubs also fall back by accident |
| data files | mostly caught | through the open record (data-mcp-description: 0 missed). Not seen: `stat`, `glob` or `ls-files` listings, non-Python readers, imports of `docs/*.py` (S4) |
| lru_cache | caught | module-level and class members are cleared. Not cleared: caches inside containers or closures |
| xdist map against a serial run | equivalent | B-6, 5 of 1101 line sets differ, all in conftest and lock |
| collection-time code | falls back | |

## B-11 (Q2)

- Correct for its stated cause, state of module scope. It also fixes the m06 order dependence within a file.
- The residual it names (session fixture setup reaching other files) is in fact covered by B-3.
- The real residual is work done inside a test against a shared session or package object, and restore gaps
  that cross files. No instance exists today. A guard test listing the allowed session fixtures of
  `tests/conftest.py` would keep it that way.

## Fallback rules (Q3)

- `_fallback_rule`, `_open_rule(required=True)`, the `""` rule and import-time detection are conservative.
- pyproject.toml always falls back in practice, because it is opened at collection [measured].
- Not conservative where they must be: S1 to S4 above.

## Note

- `runtime:42` sets `_stdlib` to the venv's own `lib/python3.13` (platstdlib), which is a prefix of
  site-packages [measured]. Every pytest and third-party frame is therefore skipped as stdlib, and `_internal`
  (`:43`) never matches.
- The effect is safe, more recording and more fallbacks, but the description in B-7 is inaccurate.
- The runtime has no automated test (`tests/test_s16_test_impact.py` uses synthetic maps). Add one toy-repo
  build in the test-map venv that pins subprocess attribution, cache clearing, fixture linking and the open
  filters.

Not examined: subprocess-based test files beyond 3 spot checks (cwd and PYTHONPATH), the 4108 s build log, and
the browser test's asset path.
