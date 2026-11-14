# S19 ruling A11 (ADR 0076 I-14): cut the messages <-> registry cycle, initialization unchanged

Design lane (`architect`, Fable 5.2), 2026-11-14. Measured at `wp/S19` tip 5c6547f0. Binds the W4 step I-14.
Authorities: ADR 0076 I-14 and FQ-B (accepted), ADR 0060 D8, `S19-architecture.md` section 2 (cycle 2), `S19_RULES.md`.
The implementer needs this file, ADR 0076 "Migration" rules 1 to 5 and `S19_RULES.md`. No production code here.

**Scope.** Cut edges 2 and 3 of cycle 2 (1.1) and move `yaml_load` to a leaf, with every entry point rendering the
same text in the same order. The catalogue gets two slots filled from above: `set_before_freeze` (the registry, at
its import) and `set_audit_probe` (the audit, in `enable()`); `application.errors`, `application.jobs.worker` and
`tests/conftest.py` import the registry. One observable change, accepted by FQ-B: a process that never imported the
registry freezes the core catalogue alone. Out of scope: the registry build and discovery, catalogue data and message
texts, `Auditor`'s behaviour, `Catalogue`'s constructor signature, and the I-9 move that this step follows.

## 1. Facts

### 1.1 The cycle (codehealth arch, depth 4: 4 nodes, 6 edges)

| # | edge | where | kind | fate |
|---|---|---|---|---|
| 1 | `messages.audit -> messages.catalogue` | audit.py:29 (`Auditor.observe`), :42 (`Auditor.code`): `CATALOGUE` | lazy | stays (down) |
| 2 | `messages.catalogue -> messages.audit` | catalogue.py:274, read of `audit.auditor is not None` at :276 (`_load`) | lazy | **cut** |
| 3 | `messages.catalogue -> registry` | catalogue.py:345, call at :347 (`_frozen_entries`); the layer violation | lazy | **cut** |
| 4 | `registry -> messages.catalogue` | registry/__init__.py:784, `catalogue.register` passed at :792 | lazy | stays, becomes top-level |
| 5 | `registry -> registry.discovery` | registry/__init__.py:53 | top | stays |
| 6 | `registry.discovery -> messages.catalogue` | discovery.py:52 (TYPE_CHECKING), :290, :299 (`_yaml_load`), :310 | lazy | stays; :299 retargets |

Two corrections to `S19-architecture.md` lines 177-182: moving `_yaml_load` does not remove edge 6 (discovery still
imports `Catalogue`), it removes a private-name import; and catalogue.py:274 takes no validator from `audit`, it reads
the audit switch to decide whether a load validates the packaged core.

### 1.2 When the process catalogue is frozen today

`CATALOGUE = Catalogue(registry_first=True)` (catalogue.py:387, the only such construction anywhere). Each lookup on
it, while not frozen, imports the registry and calls `before_catalogue_freeze()`; that builds the process registry,
whose build registers extension catalogues through `catalogue.register`; then the lookup loads and sets `_frozen`.

| entry point | registry imported | registry built | catalogue frozen |
|---|---|---|---|
| CLI (`application.cli:main`) | at import, cli.py:60 | cli.py:1115, before the handler | first render in a handler |
| HTTP, MCP servers (cli.py:639-649, serving.py:28, :91) | at import, via local.py:148 | `LocalApplication.create/open/in_memory`, local.py:299, :342 | first rendered error or `explain` |
| jobs worker child (`jobs/worker.py`) | only by the lazy hook | at its first lookup, if any | only when an `ApplicationError`, `StoreError`, `SolveFailedError` or `Failure` is formatted as text (for example `_LOG.exception` in `_run`); else never |
| pytest (`import openflowsheet` alone imports neither package) | when a collected module imports `application.local`, `cli`, `capabilities` or the registry | first lookup or first `LocalApplication` | measured, full collection (20368 tests): during collection, from binding_common.py:47 via audit.py:32, registry already imported |
| F1 discovery (`default_registry`, `Registry.build`) | yes | itself | not by the build: `CatalogueCheck` uses throw-away `Catalogue()` instances (discovery.py:292, :313, not `registry_first`); a process-catalogue lookup on the building thread raises (registry/__init__.py:804) |

**Renders before the merge today: none.** No text is ever rendered from a core-only catalogue while an extension
catalogue is installed; the one exception raises `RuntimeError("catalogue lookup during registry build")` instead.

### 1.3 Probe (`python -I`, worktree `src` first on `sys.path`) and constraints

- After `import M` the registry is in `sys.modules` for `registry` and `application.local|serving|cli|capabilities`,
  and not for `openflowsheet`, `messages.*`, `application.types|contract|store|operations|binding_common|stream_table|
  revision_run`, `application.jobs.*`, `application.bindings.*`, `verify.failure`, `run.session`. The registry does
  not import `messages.catalogue` at import today.
- Lookup sites outside `messages`: production `application/types.py:286, :1305, :1332`, `contract.py:70`,
  `store.py:127, :136`, `operations.py:660`, `local.py`, `cli.py`; audit-only (tests) `verify/failure.py:187-191`,
  `binding_common.py:46`, `stream_table.py:113`, `revision_run.py:194`, `store.py:118`, `contract.py:80-96`.
- **G20** (`tests/test_t07_global_state.py`, counter `"global": 3` at :145) fails on a new `global` statement,
  `@cache`, `threading.local(` or `ContextVar(`. A step may not edit tests and an allowlist entry cannot precede its
  hit, so the slots are written without a `global` statement.
- Tests assign `audit.auditor` directly (test_msg_engine.py:52-57 autouse, test_st_core.py:896), so the catalogue must
  read the switch live. 0 tests or scripts patch `registry.before_catalogue_freeze`; the patches of `_registered` and
  `_process_registry` (test_f1_discovery.py:259, :749) still reach the installed function through its module globals.
- `scripts/s16_recall.py:254` calls `CATALOGUE._frozen_entries()`: the name stays. `_yaml_load` has one importer
  outside catalogue.py (discovery.py:299). No touched file is an F0 M9 path or listed in `registry/builtin/*.json`.
  Scratch catalogues inside a build must never run the hook (it would raise).

## 2. The ruling

### 2.1 Invariants (what "unchanged" means)

- **INV-1** Where `openflowsheet.registry` finished importing before a lookup on a not yet frozen `registry_first`
  catalogue, the lookup calls the registry's `before_catalogue_freeze` at today's point (before `_load()`, outside
  the lock, on every lookup until one succeeds; exceptions propagate). **INV-2** Only such a catalogue runs the hook.
- **INV-3** A load with `validate_core=None` validates exactly when texts were given or `audit.auditor is not None` at
  that moment, in every process where `audit.enable()` has run or the switch was never set. **INV-4** No message
  text, code set, entry order, `CATALOGUE.sha256()`, registry snapshot, MCP digest or F0 measure changes.

### 2.2 Cut of edge 3: the before-freeze hook

`messages/catalogue.py` (imports `Callable` from `collections.abc`):
```python
def _core_alone() -> None:
    """No hook installed: this process never imported the registry; the core freezes alone (ADR 0076 I-14)."""
def _audit_off() -> bool:
    return False
@dataclass
class _Hooks:  # process wiring set by the layers above, never job data
    before_freeze: Callable[[], None] = _core_alone
    audit_on: Callable[[], bool] = _audit_off
_HOOKS: Final[_Hooks] = _Hooks()
def set_before_freeze(hook: Callable[[], None]) -> None:   # public, beside register(); last install wins
    _HOOKS.before_freeze = hook
def set_audit_probe(probe: Callable[[], bool]) -> None:    # public, beside register()
    _HOOKS.audit_on = probe
```
- `_frozen_entries`: lines 345-347 (the import and the call) become the one call `_HOOKS.before_freeze()`. The
  condition `self._registry_first and not self._frozen` and all else are untouched; the constructor keeps
  `registry_first`. The module docstring says the first lookup runs the hook the registry installed.
- The holder carries a comment: process-global by design, wiring set at import (or by the tests' audit switch), the
  same for every job; G20's patterns do not see it. Its spelling is free (a plain class if mypy objects to assigning
  a `Callable` field); the two setters, the defaults and the call sites are binding.
- `registry/__init__.py`: top-level `from openflowsheet.messages import catalogue`; the lazy import at :784 is deleted
  (:792 unchanged); the module's last statement is `catalogue.set_before_freeze(before_catalogue_freeze)`. `__all__`
  is unchanged; docstring lines 27-29 say the hook is installed at import.
- Installers (FQ-B): `application/errors.py` and `application/jobs/worker.py` each gain a top-level
  `import openflowsheet.registry  # noqa: F401`, commented "ADR 0076 I-14: importing the registry installs the
  catalogue's before-freeze hook" (`import openflowsheet.registry as _registry` if the public-API tier counts the
  bound name). Top-level in the worker on purpose: the registry prints nothing at import, and test B1 needs it.

### 2.3 Cut of edge 2 (the audit probe) and cut 3 (`yaml_load`)

- catalogue.py `_load`: lines 274-276 become `validate = self._core_texts is not None or _HOOKS.audit_on()`, under
  the unchanged `if validate is None:`. Same short-circuit order; the probe is pure.
- audit.py: a module function `_on() -> bool` returning `auditor is not None`; `enable()` gains, before its `if`,
  `from openflowsheet.messages import catalogue  # noqa: PLC0415` and `catalogue.set_audit_probe(_on)`. Its two
  `global auditor` lines are unchanged (G20 entry `occurrences: 2` holds); `disable()` and `Auditor` are unchanged.
- New leaf `src/openflowsheet/messages/yaml_io.py`: public `yaml_load(text: str) -> Any`, the body of `_yaml_load`
  verbatim. catalogue.py imports the module (`from openflowsheet.messages import template, yaml_io`), calls
  `yaml_io.yaml_load(text)` at :284 and deletes `_yaml_load` (no re-export: nothing else imports it). discovery.py:299
  and :304 use `from openflowsheet.messages.yaml_io import yaml_load`, still lazy. `messages/__init__.py`'s docstring
  lists `yaml_io`.

### 2.4 Why each entry point renders the same text in the same order

The installed object is the registry's own function, called from the same statement, so under INV-1 the sequence
(hook, build if not built, register extension documents, load, freeze, render) is today's. **CLI, HTTP, MCP:** `cli`
and `local` import the registry at import and build it at start (cli.py:1115, local.py:299, :342). **Worker child:**
spawning imports `application.jobs.worker`, whose new import installs the hook before `_run`; the build still happens
at the first lookup, if any, inside the job's log redirection. **pytest:** conftest imports the registry (W1), so
INV-1 holds for any subset, order or xdist worker (the audit makes hook modules look codes up, which production never
does). **F1 discovery:** unchanged; the building thread reaches the same function; scratch catalogues skip the hook.

### 2.5 What may change (complete list)

1. **Library-only freeze (FQ-B, accepted).** A first lookup in a process without the registry imported (only
   `openflowsheet.messages.*`, or an `application` module that does not reach `application.errors`) neither imports
   nor builds the registry. With no extension catalogue installed the entries are today's. With one, its codes are
   absent in that process and a later `default_registry()` raises `RuntimeError("the message catalogue is frozen:
   register before first use")`. `scripts/msg_catalogue.py` is such a process.
2. **Import timing, no result.** Importing the registry imports `messages.catalogue`, `.template`, `.yaml_io` (+4.9 ms
   on 206 ms; no YAML read, no PyYAML). `application.errors` and `jobs.worker` import the registry (+12 ms after
   `application.types`, +7 ms after `jobs.runner`). `audit.enable()` imports `messages.catalogue`; a catalogue load no
   longer imports `messages.audit`. ADR 0060 D8's "registry imports messages only inside the build" is superseded by
   ADR 0076's amendment of D8.
3. **Two traps, 0 instances today.** A patch of `registry.before_catalogue_freeze` no longer reaches the catalogue.
   `audit.auditor` assigned directly in a process that never called `audit.enable()` no longer turns core validation
   on (conftest calls `enable()`; test_msg_engine.py validates the packaged core).

### 2.6 Rejected

- `sys.modules.get(...)` in the catalogue (the same coupling, hidden from the tool); a module variable with `global`
  (G20 fails inside the step); the hook on `CATALOGUE` only (the audit probe must reach every instance).
- `audit` importing `catalogue` at import: every G3 hook module would import the catalogue and the template grammar
  (+29 ms cold), against test_package_imports.py:43. A flag set by `enable()`/`disable()`: wrong under the tests that
  assign the switch. Injecting the catalogue into `Auditor`: a default `audit.Auditor()` must reach `CATALOGUE` itself.
- A lazy registry import at each render site (not checkable statically); dropping `registry_first` (breaks INV-2,
  changes an unlisted signature); the composition-root install with a typed error (ADR 0076: raises in `__str__`).

### 2.7 Reconciliation with ADR 0076

Consistent with I-14 and FQ-B on the slot, its home, the three installers and the library-only behaviour. Two gaps,
closed with the least change, for the orchestrator to record in `S19_DECISIONS.md`:
1. The ADR says I-14 removes cycle 2. Measured on a copy of the tip: the hook cut alone gives 6 violations, 4 cycles,
   10 edges (the cycle shrinks to `audit <-> catalogue`). It goes only with the audit cut, which needs one more public
   name: the plan's `added` has three names (`set_before_freeze`, `set_audit_probe`, `yaml_load`), not the row's two.
2. The ADR places all four tests after the step. Its (a) and (b) hold at the base too and are written first; (c) and
   (d) pin 2.5 item 1, fail at the base by design, and stay after.

## 3. Work order (one engineer; interface mode; 8 source files)

Precondition: I-9 has landed (`application/errors.py` holds `ApiError`, `ApplicationError`, `api_error`,
`SolveFailedError`) and the W4 tool pin is in place. Fresh-interpreter scripts run `sys.executable -I -c`; their
first lines put the fake-site directories and the repository `src` at the front of `sys.path`.

- **W0, measure (no commit).** `codehealth arch --depth 4 --edges`; greps for patches of `before_catalogue_freeze`,
  importers of `_yaml_load`, constructions with `registry_first`, `auditor` assignments inside `-c` scripts; the
  probe of 1.3 for every module with a lookup site.
- **W1, tests before (outside the gate; pass at the base and at the head).** New `tests/test_s19_i14_freeze_order.py`,
  using `tests/f1_harness.py` and a copy of the slurry-with-peek fixture (test_f1_discovery.py:430-455):
  - B1, parametrized over `openflowsheet.registry`, `.application.errors`, `.application.jobs.worker`,
    `.application.cli`, `.application.local`, `.application.serving`: import the module; `CATALOGUE.entry` of a core
    code is not `None`; then `CATALOGUE.entry("slurry.slurry_refused").namespace == "slurry"`,
    `default_registry().closed`, and the peek saw `["catalogue lookup during registry build"]` (ADR test (b) and more).
  - B2 (ADR test (a)): `str(api_error(<code>, "probe"))` from `application.errors` as the first lookup; its last line
    is `"<code>: probe"`; then the slurry entry is present.
  - B3, three tests on `"jsonschema" in sys.modules` after `Catalogue().keys()`: false without the audit; true after
    `audit.enable()`; with the audit enabled and `audit.auditor = None` false, and true for a new `Catalogue()` once
    the switch is restored (measured at the tip: False; True; False then True).
  - `tests/conftest.py` `pytest_configure`: `import openflowsheet.registry` before `audit.enable()`, commented "ADR
    0076 I-14: the test process installs the catalogue's before-freeze hook, as every entry point does".
- **W2, plan commit.** `.codehealth/interface/I-14.toml`: `id`, `approved_by`, `reason`; `added` = catalogue.py:
  `set_before_freeze`, `set_audit_probe`; yaml_io.py: `yaml_load`; `new_files` = `messages/yaml_io.py`; no `callers`.
- **W3, the step (one commit, gated against W2).** Exactly 2.2 and 2.3 in `messages/catalogue.py`, `messages/audit.py`,
  `messages/yaml_io.py` (new), `messages/__init__.py` (docstring), `registry/__init__.py`, `registry/discovery.py`,
  `application/errors.py`, `application/jobs/worker.py`. Nothing else.
- **W4, tests after (outside the gate), in the same test file:**
  - A1 (ADR (c)): import only `openflowsheet.messages.render`; a core lookup succeeds; `"openflowsheet.registry" not
    in sys.modules`; `catalogue.register(<slurry document>, namespace="slurry")` raises the frozen `RuntimeError`.
  - A2 (ADR (d)): after A1's lookup, with the slurry site on the path, `default_registry()` raises `RuntimeError`
    matching "the message catalogue is frozen". A3: the same with no extension on the path:
    `default_registry().closed`, and `CATALOGUE.keys()` is unchanged by it.
  - A4: `import openflowsheet.registry` puts `openflowsheet.messages.catalogue` in `sys.modules` and neither
    `.render` nor `.audit`; after `Catalogue().keys()`, `.audit` is still absent.
  - The comment at test_package_imports.py:46-47 says the registry imports `messages.catalogue` at import (I-14).
- **Orchestrator afterwards:** drop the adoption comment line `messages.catalogue -> registry` (config.toml:174).

**Expected `codehealth arch --depth 4`.** Tip 5c6547f0: 309 files, 7 violations, 4 cycles (largest 4 nodes), 14 cycle
edges. The same tree with W3 applied (simulated): 310 files, **6 violations, 3 cycles (largest 3 nodes), 8 edges**. At
the real base the totals differ by the W4 steps before it; W3's delta is exactly -1 violation (`messages.catalogue ->
registry`), -1 cycle, -6 cycle edges, +1 file, and no remaining cycle names a `messages` or `registry` module.

**STOP (report, change nothing to fit):** `application/errors.py` absent; a W1 test fails at the base; the arch delta
differs; G20 reports a hit; an existing test needs an edit other than the two named; the public-API tier reports
anything beyond the three names and the new file; W0 finds a patch of `before_catalogue_freeze`, a second importer of
`_yaml_load` or a second `registry_first` construction; any golden text, the MCP digest or F0 moves.

## 4. Verification gates

| gate | measured how | pass |
|---|---|---|
| G1 arch | `codehealth arch --depth 4 --edges` at base and head | delta -1 / -1 / -6, +1 file; cycle 2 absent; `messages/catalogue.py` imports neither `openflowsheet.registry` nor `messages.audit` |
| G2 before-tests | W1's file at the base and at the head | 10 of 10 at both (6 + 1 + 3) |
| G3 suite | the gate's test tier at the head | 0 failures; passed = base count; MSG-G3 findings empty; G20 counters unchanged |
| G4 patches | `python3 .claude/skills/s19-refactor/patch_noop.py .` | 0 flagged; total unchanged |
| G5 identity | `scripts/corpus_identity.py --check`; `scripts/registry_builtin.py --check`; MCP digest; `CATALOGUE.sha256()` at base and head | PASS; clean; equal; equal |
| G6 after-tests | W4's tests at the head; A1, A2, A4 also at the base | 4 of 4 at the head; A1, A2, A4 fail at the base |
| G7 coverage (record) | probe of 1.3 at the head | the modules with a production lookup site and no registry at import, listed in the engineer's report |

## 5. Risks and open questions (each with a default; work proceeds on the default)

- **Q1 (preference: a public name).** `set_audit_probe` is a third public name, beyond the ADR row (2.7). Default: use
  it and record the decision; revisit by a rename in a later interface step.
- **Q2 (preference: scope).** The conftest import. Default: add it. Without it a single-file run may freeze the core
  alone; no result differs unless an extension catalogue is installed in the test environment.
- **Q3 (fact: I-9's import graph).** Which `application` modules with a production lookup site (`store`, `operations`,
  the successors of `types`) reach `application.errors` at import. Experiment: G7. Default: record the list and add no
  fourth installer (such a site falls under 2.5 item 1); otherwise the same one-line import in each listed module.
- **Q4 (fact: G20's reach).** The holder is process-global state G20's patterns cannot see. Default: accept with the
  comment of 2.2 (wiring, the same for every job); the I-14 `reviewer` pass reads it.
- **Q5 (fact: tooling).** mypy on the holder's `Callable` fields; the public-API tier on the bound import name; a
  test-impact map built before the step is stale. Defaults: the fallbacks of 2.2; gate W3 on the full suite.
- **Q6 (preference).** `registry_first` stays a constructor parameter. Default: keep; removal is a later interface step.
- **R1.** A lookup while another thread is still importing the registry would freeze the core alone; not reachable
  from an entry point. The two traps of 2.5 item 3 stay open; A4 and B3 pin the supported paths. Default: accept.
