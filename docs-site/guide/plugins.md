# Plugins (extensions)

A **plugin** is a separately installed Python distribution that adds entries to OpenFlowsheet's
**extension registry**: message codes, and declarations of unit models, property methods, record
types and the other kinds the registry knows. The registry lists everything it holds, built-in
or installed, through the `list_capabilities` operation, and checks unit and method pairs through
`check_admission`. The rules are those of
[ADR 0060](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/adr/0060-F1-extension-registry.md)
(D2 the descriptor, D7 discovery and trust, D9 the evidence flags); this page states them for a
plugin author.

**What a plugin can do in this release.** An installed plugin is discovered, validated and
listed. Its message entries become part of the message catalogue: `explain` resolves them and a
descriptor's `limitations` may name them. Its other descriptors are listed and take part in
`check_admission`, with the stability `core` for the kinds that have a payload schema and
`preview` for the rest (see [Kinds](#kinds-in-this-release)). A plugin **cannot** add a unit model or a property
method that a revision binds on or a solve uses: the binder reads its own table of models and
bases, not the registry (see [Selectability](#selectability) below). A plugin's
`functional_contributor` is listed but never passed to the cost and LCA assessment.

## The example plugin

The repository ships a minimal plugin in
[`examples/plugins/demo/`](https://github.com/computational-chemical-engineering/openflowsheet/tree/main/examples/plugins/demo).
It registers one descriptor, a message catalogue with one code, `demo.feed_too_wet`, and
`tests/test_x01_example_plugin.py` discovers it through the same entry-point discovery an
installed plugin goes through. Its layout (illustrative):

<!-- snippet: illustrative -->
```text
examples/plugins/demo/
├── pyproject.toml
└── src/openflowsheet_demo_plugin/
    ├── __init__.py        # package(): the extension package document
    └── messages.yaml      # the message catalogue
```

Install it next to OpenFlowsheet (illustrative; any installer that reads `pyproject.toml` works):

<!-- snippet: illustrative -->
```console
$ pip install ./examples/plugins/demo
```

## The entry point

A plugin declares one entry point in the group **`openflowsheet.extensions`**. The entry point's
name is the plugin's **namespace**, `^[a-z][a-z0-9_]*$`; its value names a zero-argument callable.
From the example's `pyproject.toml`:

<!-- snippet: file examples/plugins/demo/pyproject.toml -->
```toml
[project.entry-points."openflowsheet.extensions"]
demo = "openflowsheet_demo_plugin:package"

[tool.setuptools.package-data]
openflowsheet_demo_plugin = ["messages.yaml"]
```

The package data line ships `messages.yaml` in the wheel; without it the catalogue is missing
after installation and the package is quarantined.

The callable returns the **extension package document**
`{package_format: "openflowsheet-extension-package-v1", namespace, descriptors: [...]}`. It must
import only the standard library and `openflowsheet.registry`: the registry calls it while it is
being built, and implementations are imported only when a factory is resolved. The example's:

<!-- snippet: file examples/plugins/demo/src/openflowsheet_demo_plugin/__init__.py -->
```python
def package() -> dict[str, Any]:
    """The extension package document: one `message_entries` descriptor naming the catalogue
    `messages.yaml` in this package, read through `importlib.resources`."""
    return {
        "package_format": "openflowsheet-extension-package-v1",
        "namespace": NAMESPACE,
        "descriptors": [
            {
                "descriptor_format": "openflowsheet-extension-v1",
                "kind": "message_entries",
                "id": "demo.messages",
                "version": "0.1.0",
                "title": "Demo plugin messages",
                "status": "tested",
                "requires": [],
                "provides": [],
                "limitations": [],
                "platforms": ["any"],
                "pip_extra": None,
                "data_rights": None,
                "implementation": {
                    "modules": ["openflowsheet_demo_plugin/messages.yaml"],
                    "factory": None,
                },
                "payload": {
                    "catalogue": {"package": "openflowsheet_demo_plugin", "path": "messages.yaml"}
                },
            }
        ],
    }
```

## The descriptor

Every descriptor is a closed object (schema `schemas/extension-descriptor.schema.json`); an
unknown member, a missing one or a wrong type quarantines the package.

| Field | What you declare |
| --- | --- |
| `descriptor_format` | `openflowsheet-extension-v1` |
| `kind` | one of the registry's kinds (see [Kinds](#kinds-in-this-release)) |
| `id` | `<namespace>.<name>`, letters, digits, `_`, `-` and `.` separators, at most 128 characters |
| `version` | `MAJOR.MINOR.PATCH`, compared numerically; (kind, id, version) is unique, several versions of one id may coexist |
| `title` | a plain noun phrase, 1 to 80 characters |
| `status` | `declared`, `implemented`, `tested`, `reviewed` or `released`: your evidence claim (see [Trust](#trust-and-the-evidence-flags)) |
| `requires`, `provides` | capability tokens (`<space>:<name>[:<level>]`); `requires` is a list of clauses, each a list of alternative tokens, and every clause must hold |
| `limitations` | `{code, params}` pairs; `code` is a core message code or one of your own catalogue's |
| `platforms` | `["any"]` or a subset of `linux-x86_64`, `linux-aarch64`, `windows-x86_64`, `macos-x86_64`, `macos-arm64` |
| `pip_extra` | the extra of your distribution whose requirements the implementation needs, or `null` |
| `data_rights` | `null`, or your statement on data the plugin ships: `{source, licence_stated}` |
| `implementation` | `{modules, factory}`: the files that make up the extension, relative to the import root, and the callable that constructs it: `{module, attribute, key}`, or `null` when nothing is constructed |
| `payload` | the kind's content, validated by the kind's payload schema where one exists |

**`data_rights` is your statement, not the project's assessment.** It records where the data came
from and the licence its source states, for example (illustrative):

<!-- snippet: illustrative -->
```json
{"source": "Smith and Jones (2019), Table 3", "licence_stated": "CC-BY-4.0"}
```

The project's own judgement of data rights lives in its rights register, not in your descriptor.

**`modules` is hashed.** The registry hashes every file named in `modules` (line endings
normalised) into the descriptor's `self_sha256`, so a change to the code or data of a plugin
changes its identity. List every code and data file the extension consists of, including data
read through `importlib.resources`; the example lists `messages.yaml`. A path that does not
resolve to a regular file quarantines the package (`self_hash_unavailable`). With `modules: []`
nothing is hashed, so zip imports and namespace packages work, but then no file of the extension
enters its identity. The entry-point module need not be listed: the descriptor hash covers what
`package()` returns, and the example lists only the data file. (A `record_type` payload schema
file is read from the import root too, so it needs a regular file on disk.)

The registry adds computed fields to each registered descriptor: `self_sha256`,
`descriptor_sha256`, `origin`, `distribution`, `distribution_version`, `entry_point`,
`effective_status`, `evidence_class` and `stability`. You never declare them.

## Message entries

A `message_entries` descriptor's payload names a YAML document in the message catalogue's format,
read through `importlib.resources`: `{"catalogue": {"package": <your package>, "path": <file>}}`.
Its `namespace` is your namespace and every code starts with `<namespace>.`; a code can never
replace a core code. The example's catalogue:

<!-- snippet: file examples/plugins/demo/src/openflowsheet_demo_plugin/messages.yaml -->
```yaml
catalogue: openflowsheet-messages-v1
namespace: demo
entries:
  - code: demo.feed_too_wet
    family: refusal
    kind: input
    complete: false
    title: Feed too wet for the demo dryer
    summary: The demo dryer refuses a feed whose water fraction is above its limit.
```

The catalogue is validated before anything is registered: a document that fails the catalogue's
schema, names another namespace or a code outside it, or cannot be read, quarantines the package
with [`extension_invalid`](../messages/refusals.md#extension_invalid). Once registered, its codes
resolve like core ones:

<!-- snippet: cli -->
```console
$ openflowsheet explain demo.feed_too_wet
```

## Kinds in this release

Four kinds have a payload schema for plugins in this release: `message_entries`, `record_type`,
`correlation_form` and `data_source` (ADR 0061 installs the last three). A plugin descriptor of
one of them is registered as `core`, with one exception: a `record_type` whose payload has
`payload_schema: null` is `preview`; a `record_type` naming a `payload_schema` (`{package, path,
sha256}`) is `core`, and a `sha256` that is wrong, or names a file that cannot be read, quarantines
the package with [`extension_invalid`](../messages/refusals.md#extension_invalid) at
`/payload/payload_schema/sha256`. Registered `record_type` and `correlation_form` descriptors are
read by record validation. Every other kind is accepted with a payload checked only to be an
object, registered with the stability `preview`, and flagged
[`preview_kind`](../messages/notices.md#preview_kind) wherever it is used. That includes
`unit_model`, `property_method` and `connection_definition` (their plugin form is the v2 form,
not yet specified) and `functional_contributor` (listed, never passed to the assessment).

## Discovery, namespaces and quarantine

The registry is built once per process, at the start of a `LocalApplication` or at the first
message lookup, from the built-in tables and then from every distribution on the path that
declares an `openflowsheet.extensions` entry point, in the order of (distribution name, entry
point name). Installation order never matters.

**Namespaces.** Your namespace is your entry point's name and the first segment of every id and
code you register. Reserved: `openflowsheet`, `core`, `std`, `legacy`, `x`, `user`, and the first
segment of every built-in id (`syn001`, `c1`, `thermal`, `cost`, `lca`, `derived`, `pr-lib-v1`,
`component`, `assay`, `parameter_set`, ...).

**Quarantine.** A package is registered whole or not at all. A package with a problem is
quarantined with one typed reason, and the build continues: one plugin never stops the program
or another plugin.

| Problem | Code |
| --- | --- |
| two distributions declare the same namespace (both are quarantined; the same distribution name and version seen twice is not a conflict, two versions of one distribution quarantine both) | [`namespace_conflict`](../messages/refusals.md#namespace_conflict) |
| the namespace is reserved | [`reserved_namespace`](../messages/refusals.md#reserved_namespace) |
| the entry point does not import, or its callable raises | [`extension_load_failed`](../messages/refusals.md#extension_load_failed) |
| the document fails the schema, its `namespace` differs from the entry point's name, an id lacks the namespace prefix, one (kind, id, version) appears twice, a catalogue fails, a `record_type`'s `payload_schema.sha256` does not match its file, or a limitation code is unknown | [`extension_invalid`](../messages/refusals.md#extension_invalid) |
| a token names an unknown space, an unknown capability in a fixed space, or a malformed name | [`capability_unknown`](../messages/refusals.md#capability_unknown) |
| a token is reserved: any `legacy:` token, or an `x:` token provided outside your namespace | [`reserved_capability`](../messages/refusals.md#reserved_capability) |
| a file in `modules` cannot be read | [`self_hash_unavailable`](../messages/refusals.md#self_hash_unavailable) |

The reason of a quarantine is recorded in the registry's snapshot; no operation returns it in this
release. From Python:

<!-- snippet: python -->
```python
from openflowsheet.registry import default_registry

print(default_registry().snapshot()["quarantined"])
```

## Trust and the evidence flags

**Installing a distribution is the trust boundary.** Whoever can install a package into the
Python environment can already run code there, so every installed entry point is loaded. Trust in
the *results* is a matter of evidence, and it is flagged rather than enforced:

- A plugin's `status` counts up to `tested`. A declared `reviewed` or `released` counts only with a
  project attestation for exactly that id, version and pair of hashes; attestations cannot be
  recorded in this release, so every plugin descriptor has `effective_status` at most `tested`
  and `evidence_class` `unreviewed`.
- Every `unreviewed` descriptor that a result uses carries the notice
  [`extension_unreviewed`](../messages/notices.md#extension_unreviewed), and every `preview` one
  [`preview_kind`](../messages/notices.md#preview_kind). In this release only `check_admission`
  reports carry the notices; `list_capabilities` items carry the same facts as the fields
  `evidence_class` and `stability`.
- Evidence never moves an identity: `status` and the flags enter no hash.

## Listing installed plugins

`list_capabilities` pages the registry, built-in and installed alike, sorted by kind, id and
version, filtered by kind and id prefix. It is one operation on every transport: Python
(`LocalApplication.list_capabilities`), the CLI, HTTP (`GET /v1/capabilities`) and the MCP tool
`list_capabilities`. From the command line, without a project:

<!-- snippet: cli -->
```console
$ openflowsheet capabilities --prefix demo.
```

For the example this prints one item, `demo.messages`, with `entry_point` `demo`, `distribution`
`openflowsheet-demo-plugin`, `origin` `installed`, `effective_status` `tested`, `evidence_class`
`unreviewed` and `stability` `core`. `openflowsheet admission --unit U --method M` checks a pair
the same way (`check_admission`).

`openflowsheet explain` prints a `Docs:` link into the core site's message pages; for a plugin
code that link does not resolve (tracked under MSG).

## Selectability

Registering is not selecting. In this release a revision binds a unit model only on the property
bases the binder's own table lists for it, and only the built-in selectable bases can be chosen.
Two built-in descriptors show the limit: the property method `pr-lib-v1` and the unit model
`syn001.cascade` are registered and listed, but neither can be selected
([`factory_unavailable`](../messages/refusals.md#factory_unavailable) from the registry,
[`model_unsupported`](../messages/refusals.md#model_unsupported) from the binder). A plugin's unit
models and property methods are in the same position. They become usable through the v2 property
method and unit model forms, which are not yet specified; until then a plugin contributes message
codes and declarations, not new numerics.
