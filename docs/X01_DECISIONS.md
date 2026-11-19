# X01 build decisions (append-only)

Build-lane choices for X01 rest (roadmap.md:52; target-architecture.md:899-901) that the brief and ADR 0060 leave open.
Each line: `DECISION: <question> -> <choice>. Alternative: <x>. Reversible by: <how>.` Batched for the package's one
design-lane ruling round (CLAUDE.md, agent budget). Nothing here changes the registry's behaviour, a schema, the
built-in tables, `builtin-sha256.txt`, a catalogue entry's identity or `MODEL_BASES`.

## X01-WO1, part A: plugin-author documentation and an example plugin (2026-11-19)

Brief: `docs/briefs/X01-WO1.md` (card ofs-05-widen, option B). Files: `docs-site/guide/plugins.md`, `mkdocs.yml` (one
nav line), `examples/plugins/demo/`, `examples/README.md`, `tests/test_x01_example_plugin.py`.

- **DECISION A-1: where the plugin-author guide lives -> `docs-site/guide/plugins.md`, in the published user guide
  ("Plugins (extensions)", after Interfaces).** The docs tree has a user-guide location (`mkdocs.yml` nav, built
  strictly on every push by `site.yml`), and plugin authors are readers of the site. Alternative: `docs/plugins/README.md`
  (repository-only, unpublished). Reversible by: moving the page and dropping the nav line.
- **DECISION A-2: which kind the example registers -> one `message_entries` descriptor (`demo.messages`, code
  `demo.feed_too_wet`).** It is the only kind whose plugin payload has a schema in 0.5 (`PAYLOAD_DEFS`), so the only one
  a plugin registers as `core`, and the only one with an observable effect (`explain` resolves the code). Any other kind
  would be registered `preview` with an unchecked payload, and a unit model or method would suggest a usability 0.5 does
  not have. Alternative: a `functional_contributor` (preview, never passed to E01). Reversible by: editing `package()`
  and the guide's snippets (the snippet test pins both).
- **DECISION A-3: `implementation.modules` of a payload-only descriptor -> lists the catalogue file
  (`openflowsheet_demo_plugin/messages.yaml`).** D2 calls `modules` "code and data files"; listing the YAML makes an edit
  of the catalogue move `self_sha256`. With `modules: []` an edited catalogue would leave every hash unchanged. The guide
  tells authors to list data read through `importlib.resources`. Alternative: `[]`, as the F1 tests' fake catalogues
  do. Reversible by: editing the example; ADR 0060 could state the rule (question Q-1 below).
- **DECISION A-4: how the test installs the example offline -> from the example's own `pyproject.toml`
  (`tomllib`): a `.dist-info` with `METADATA` and the declared `entry_points.txt`, and a copy of `src/` packages, in a
  temporary directory on `sys.path`;** discovery is the real `discovery.entry_points(path=...)`. The test venv has no
  setuptools, so `pip install --no-build-isolation` cannot run there, and build isolation needs the network. Checked once
  by hand with the system Python 3.13.5 and setuptools 78.1.1 (`pip install --no-deps --no-build-isolation --no-index
  --target`): the wheel installs the same `entry_points.txt` (`demo = openflowsheet_demo_plugin:package`), `__init__.py`
  and `messages.yaml`, and `openflowsheet capabilities --prefix demo.` and `explain demo.feed_too_wet` work against that
  install. Alternative: a real pip build in the test, skipped without setuptools. Reversible by: replacing `_install`.
- **DECISION A-5: how a doc snippet is "run by a test or marked illustrative" -> an HTML comment marker before every
  fenced block: `file <path>` (verbatim part of that file), `cli` (each `$ openflowsheet` line runs with the example
  installed and exits 0), `python` (runs) or `illustrative` (the prose also says so).** The test fails on a block without
  a marker. Applied to the guide and to `examples/plugins/demo/README.md`. Alternative: doctest-style execution of every
  block. Reversible by: dropping the markers and the test.
- **DECISION A-6: the example's `dependencies` -> `["openflowsheet"]`, unpinned.** A real plugin names the host; an
  editable source checkout satisfies it. The callable imports nothing from it. Alternative: no dependencies. Reversible
  by: one line in `examples/plugins/demo/pyproject.toml`.

## Open rows

- **B (blocked, record only): `pr-lib-v1` and `syn001.cascade` become selectable.** Not unblocked by F1 (ADR 0060 risk
  1, :549-552). Default in force: both stay registered, listed and not selectable; `pr-lib-v1` becomes usable through v2
  (F4, ADR 0063), the cascade through `std.*` (F6, ADR 0065). F2, F4 and F6 are Proposed, with no branch. Today's
  refusals: the binder's `model_unsupported` (`application/revision_binding.py:664`, hint at :387-391) from
  `MODEL_BASES` (`application/model_signatures.py:848`); the registry's `factory_unavailable` for `pr-lib-v1`
  (`selectable: false` in `legacy.json`). No code changed. The guide's "Selectability" section states the limit.
  Needs: F4 and F6 accepted and built, or Frank's preference to reverse ADR 0050 D10 / R-615 (risk 1).
- **C (design lane, record only): ADR 0052's amendment for extension `functional_contributor` descriptors reaching
  E01** (ADR 0067 D11, :212-216). An ADR, not build work; open for the design lane. Until it lands the guide says an
  extension contributor is listed and never passed to the assessment.

## Questions for the design lane (batched)

- **Q-1. Should ADR 0060 D2 require `modules` to list data files a descriptor reads (A-3)?** As written, a
  `message_entries` descriptor with `modules: []` registers, and its catalogue can change with no hash moving. Default:
  the guide recommends listing them; no registry change.
- **Q-2. Quarantine visibility.** No operation returns the snapshot's `quarantined` rows in 0.5 (`list_capabilities`
  lists registered descriptors only); a plugin author sees a quarantine only through `default_registry().snapshot()` or
  the log (only `extension_load_failed` is logged). Default: the guide documents the Python route.
- **Q-3. `explain` on an extension code prints a `Docs:` link into the core site's message pages**
  (`.../messages/refusals/#demo.feed_too_wet`), an anchor that does not exist for extension codes. Default: unchanged;
  a fix belongs to MSG's renderer.
