# ADR 0060 — F1: one extension registry, computed admission, `list_capabilities` and `check_admission`

**Status:** **Proposed, 2026-11-05.** Design wave W1, pass P1 (ADR 0057, R-928). Takes effect when Accepted after the W1
reviewer pass over ADRs 0060 and 0061; built in 0.5 on `wp/F1`.
**Author:** design lane (`architect`). **Brief:** `docs/roadmap/brief-architect-W1-P1.md`.
**Refines:** `docs/roadmap/target-architecture.md` §3 F1, §2.4.2, §2.6 C2, §2.7.3. Departures from the note are marked
**[departure]** with their reason.
**Amends:**
- ADR 0019 D1, as **ADR 0019 Amendment 7**: `Inspection` gains `list_capabilities` and `check_admission` (D11). On
  acceptance a pointer paragraph is added to ADR 0019 in the form of Amendment 4.
- `docs/interfaces-frozen.md`: §1 (`Inspection` gains two methods); §2 (schemas added: `extension-descriptor`,
  `registry-snapshot`; `application-results` widened additively); new frozen result-type names `CapabilityDescriptor`,
  `CapabilityPage`, `AdmissionReport`.
- `docs/design/MSG-messages.md` §4.11, in the part it leaves to F1: when extensions call `catalogue.register` (D8).

**Does not amend:** `MODEL_BASES`, `MODEL_BUILDERS`, `MODEL_SIGNATURES`, `SELECTABLE_BASES` (W27-R63 `bases-v1` keeps
reading them); `FRESH_PROVIDERS` and `fresh_provider` (the verifier's own table, R-016, B15); ADR 0050 (D1, D10); ADR 0052
(E01 keeps `register_contributor`); ADR 0058 (the `register()` slot is used as specified); any frozen legacy module (S1,
F0 M9: the 35 files are read, never edited).

---

## Context (what exists)

There is no registry. Providers are constructed by id in two places (the binder's `basis_provider`; the verifier's
`fresh_provider` over `FRESH_PROVIDERS`). Units are bound through `MODEL_BUILDERS`; which provider a unit binds on is the
frozen map `MODEL_BASES` (`application/revision_binding.py:1613`; 30 model ids, 54 (unit, provider) pairs over 5
provider ids). `syn001.cascade` exists but is refused by the binder; `pr-lib-v1` and `wilson-ig-v1` are providers that
no basis selects (ADR 0050 D10, R-615). E01 has `register_contributor(name, factory)`; MSG has
`messages.catalogue.register(document, *, namespace)`, refused after the first lookup freezes the catalogue.

F1 adds one registration point for every kind of extension, a pure admission function, the discovery operations of rule
C2, and the snapshot the environment record needs (§2.7.3). It moves no identity byte.

---

## Decisions

### D1. Kinds

A **kind** is a fixed category of extension with its own payload schema. The kind list is closed and frozen at W1's end;
adding a kind is an additive ADR amendment.

The note's 21 kinds plus one **[departure]**: `correlation_form`. ADR 0061 record entries name a correlation by form id;
the id is identity-bearing and must resolve to a declared variable set, coefficient set and result kind, so that an
entry can be validated and later evaluated by F4 and fitted by X11. No listed kind is a pure function of
(coefficients, T); `property_source` is a provider of vocabulary items, not a formula.

| Kind | Payload owner | Payload stability at the end of W1 | Built-ins in 0.5 | Registration hook / token name source |
| --- | --- | --- | --- | --- |
| `property_method` | this ADR (legacy form); ADR-F4 (v2 form) | legacy form **core**; v2 form per ADR-F4 (method slots `preview` to the end of 0.6, R-929) | 7 legacy providers (D6) | — |
| `property_source` | ADR-F4 | per ADR-F4 | — | — |
| `unit_model` | this ADR (legacy form); ADR-F6 (v2 form) | legacy form **core**; v2 per ADR-F6 | 31 legacy units (D6) | — |
| `connection_definition` | this ADR (`nTP-v1` legacy form); ADR-F2 | legacy form **core**; v2 per ADR-F2 | `nTP-v1` | names of the `conn` space |
| `attribute_kind` | ADR-F2 | per ADR-F2 | — | `attr` space |
| `derived_quantity` | ADR-F2 | per ADR-F2 | — | `derived` space |
| `kinetics_kind` | ADR-F2 | per ADR-F2 | — | `kinetics` space |
| `stability_trial_set` | ADR-F5 | per ADR-F5 | — | `trial_set` space |
| `phase_family` | ADR-F2 (vocabulary), ADR-F5 (semantics) | per ADR-F2 | — | `phase` space |
| `discrete_coordinate` | ADR-F5 | per ADR-F5 | — | — |
| `record_type` | ADR 0061 | **core** | `component`, `parameter_set` (core), `assay` (preview) | ADR 0061 store validates by it |
| `correlation_form` | ADR 0061 | **core** (evaluator field `preview` until ADR-F4) | 2 forms (ADR 0061 D4) | ADR 0061 validates entries by it |
| `data_source` | ADR 0061 (envelope); X11 rest (fetchers) | **core** | `legacy-yaml`, `user-file` | — |
| `record_generator` | X11 rest | `preview` | — | — |
| `solver_route` | ADR-F7 | per ADR-F7 | — | — |
| `run_kind` | ADR-F7 | per ADR-F7 | — | — |
| `functional_contributor` | this ADR (lists ADR 0052's contributors) | built-ins **core**; extension descriptors `preview` in 0.5 (registered and listed, never passed to E01; risk 4) | `cost`, `lca`, `derived` | none: E01 registers its own three; the registry never calls `register_contributor` |
| `exchange_format` | X15 / X23 | `preview` | — | — |
| `revision_section` | ADR-F2 | per ADR-F2 | — | — |
| `semantic_role` | ADR-F6 (over ADR 0054's vocabulary) | per ADR-F6 | — | — |
| `equipment_class` | ADR-F6 / X12 | `preview` | — | — |
| `message_entries` | this ADR (uses ADR 0058 §4.11) | **core** | — (the core catalogue is not an extension) | `messages.catalogue.register` |

"Per ADR-Fn" means: `preview` until that ADR is Accepted, then what it states. An ADR of W1 freezes its payloads at W1's
end except the slots R-929 keeps `preview` to the end of 0.6. A descriptor of a kind whose payload is `preview` is
registered and listed, and every admission report and run report that uses it carries the notice
`preview_kind(<kind>, <id>)` (D9).

### D2. The descriptor (`schemas/extension-descriptor.schema.json`, draft 2020-12, closed objects)

| Field | Type | Rule |
| --- | --- | --- |
| `descriptor_format` | const `openflowsheet-extension-v1` | bumped only by an incompatible envelope change |
| `kind` | enum (D1, 22 values) | |
| `id` | string, `^[A-Za-z][A-Za-z0-9_-]*(\.[A-Za-z0-9][A-Za-z0-9_-]*)*$`, ≤ 128 | no `: / @ # ~ [ ] ( )` (rule C1). An entry-point extension's ids start with `<namespace>.` (D7) |
| `version` | `^(0\|[1-9][0-9]*)\.(0\|[1-9][0-9]*)\.(0\|[1-9][0-9]*)$` | compared numerically as (major, minor, patch). (kind, id, version) is unique; several versions of one id may coexist |
| `title` | string, 1–80 | plain noun phrase |
| `status` | enum `declared`, `implemented`, `tested`, `reviewed`, `released` | an evidence field: excluded from every hash (D10) |
| `requires` | array of clauses; a clause is a non-empty array of tokens | conjunctive normal form (D4) |
| `provides` | array of tokens | D4 |
| `limitations` | array of `{code, params}`; `code` a catalogued code, `params` an object of strings and numbers | typed limitations (R-924). `code` is validated, without a catalogue lookup, against the core catalogue's keys plus the codes of the package's own pre-validated `message_entries` document (D7), since a lookup during build raises (D8) |
| `platforms` | `["any"]` or a non-empty subset of `linux-x86_64`, `linux-aarch64`, `windows-x86_64`, `macos-x86_64`, `macos-arm64` | declarative; never consulted by admission (D5) |
| `pip_extra` | string or null | the extra that installs the implementation's optional dependencies |
| `data_rights` | null or `{source, licence_stated}` (strings) | the author's statement for data the extension ships; the project's assessment lives in ADR 0061's rights register |
| `implementation` | `{modules: [path…], factory: null \| {module, attribute, key: string \| null}}` | `modules`: POSIX paths relative to the import root (`openflowsheet/thermo/pr_c1.py`), code and data files, unique; may be empty only for a descriptor whose payload is all its content. `factory`: resolved lazily (D7); `key` indexes a mapping attribute (`MODEL_BUILDERS[key]`) |
| `contributed_by` | absent or `{actor, session: string \| null, date: YYYY-MM-DD}` | written by the agentic layer for an extension it contributed (D9) |
| `payload` | object | validated by the kind's payload schema; a `preview` kind's payload need only be an object |

**Normalisation before hashing and comparison:** a token's level `:0` is dropped (`s:n:0` → `s:n`, D4); each clause's tokens are sorted (UTF-8 byte order) and deduplicated;
clauses are deduplicated and sorted by their token tuples; `provides` keeps, per (space, name), the highest level and is
sorted; `implementation.modules` is sorted; `limitations` are sorted by canonical JSON. `descriptor_sha256` =
`document_sha256(normalised descriptor without status)` (`openflowsheet.canonical`, ADR 0002 D3).

The registry adds computed fields to a *registered* descriptor (never declared): `self_sha256` (D3), `descriptor_sha256`,
`origin`, `distribution`, `distribution_version`, `entry_point`, `effective_status`, `evidence_class` (D9), `stability`
(from D1; for `functional_contributor` it also depends on the origin).

### D3. Self-hash

```
lf(b)          = b.replace(b"\r\n", b"\n")
file_sha(p)    = sha256(lf(bytes of <import root>/p)).hexdigest()
self_sha256    = sha256(canonical_json([[p, file_sha(p)] for p in modules sorted by UTF-8 bytes])).hexdigest()
```

An empty set hashes `[]`. The import root of a built-in is the directory containing the `openflowsheet` package; of an
entry-point extension, the directory containing its top-level package (from `importlib.util.find_spec`). A path that
does not resolve to a regular file quarantines the package (`self_hash_unavailable(<id>, <path>)`); zip imports and
namespace packages are therefore unsupported in 0.5.

This is §2.3.3's `implementation_sha256` rule made exact: **a v2 method's `implementation_sha256` =
`sha256(canonical_json([descriptor_sha256, self_sha256])).hexdigest()`**, so F4 does not define a second formula. The
descriptor term is needed because a v2 method's descriptor carries behaviour (record fields, phase models, vocabulary and
derivative orders, domain rules; note §2.3.3): an edit to the payload alone must move every exact cache key, and a
payload-only descriptor's `self_sha256` is always `sha256("[]")`. Legacy providers keep their own single-file
`implementation_sha256` in `describe()`; neither value replaces it.

**Completeness of `modules`.** For each v2 built-in, `scripts/registry_builtin.py --check` (D6) asserts that `modules`
contains the intra-package import closure of the factory module, computed by F0's AST import scan. An edit to an
undeclared helper module then cannot leave `implementation_sha256` unchanged.

### D4. Capability tokens and requirements

A **token** is `<space>:<name>` or `<space>:<name>:<level>`, `^[a-z_]+:[A-Za-z0-9][A-Za-z0-9_.+-]*(:(0|[1-9][0-9]*))?$`.
An absent level is 0, and normalisation drops a stated `:0` (D2), so equal tokens have one spelling. A required token `s:n:L` is **satisfied** by a provision set P iff P holds `s:n:L′` with L′ ≥ L (so a
method giving `vocab:h:2` satisfies a requirement `vocab:h:1`).

`requires` is a conjunction of clauses; a clause is satisfied iff one of its tokens is. An empty `requires` is satisfied.

Spaces are a closed table, frozen at W1's end (additions by ADR amendment):

| Space | Names come from | Who may provide |
| --- | --- | --- |
| `conn` | ids of registered `connection_definition` descriptors | methods (they support the definition) and the definition itself |
| `phase` | ids of `phase_family` descriptors | any |
| `vocab` | F4's vocabulary registry (a validator ADR-F4 installs) | any |
| `flash` | a static table owned by ADR-F2/F5 (`TP` today) | any |
| `attr`, `derived`, `kinetics`, `trial_set` | ids of the kinds of D1 | any |
| `convention` | the convention list of `interfaces-frozen.md` §3 plus ADR-F4 additions (a static table) | any |
| `legacy` | the 7 legacy provider ids (static, frozen) | **built-in legacy descriptors only** |
| `x` | `x:<namespace>.<name>`: extension-to-extension contracts | only descriptors of extension `<namespace>` |

**Static and registry-derived spaces.** `vocab`, `flash`, `convention` and `legacy` are **static**: their names come
from a fixed table or validator. A token whose space is unknown, or whose name is not in a static space's source, is
`capability_unknown(<token>)`. `conn`, `phase`, `attr`, `derived`, `kinetics`, `trial_set` and `x` are
**registry-derived**: their names are ids of registered descriptors (or, for `x`, names a descriptor of that namespace
provides). A name in a registry-derived space is checked by grammar only. An unregistered one is never satisfied (even
when some descriptor provides it), so no extension can claim a capability F2–F7 have not defined, and every admission
whose unit, method or definition names one carries the notice `capability_unresolved(<token>)`, admitted or refused. So
a disjunction such as `conn:nTP-v1 | conn:acme.slurry` stays usable when `acme` is not installed, and a broken package
quarantines only itself.

A non-built-in descriptor naming a `legacy:` token in `requires` or `provides` (no binder can run an extension unit on a
v1 provider: `MODEL_BUILDERS` is closed), or providing an `x:` token outside its namespace, is
`reserved_capability(<token>)`. `capability_unknown` and `reserved_capability` quarantine the extension's package at
build (D7); a built-in failing either is a bug and fails the build.

### D5. The admission function

`admit(unit, method, definition) -> Admission{admitted, refusal: {code, params} | null, notices: [...]}` is a pure,
deterministic function of three registered descriptors. It reads no platform, file, clock or environment, so the
admission set is identical on every platform (R0). The steps, in order, stop at the first refusal:

```
0. unit.payload.bindable is false                      -> model_unsupported(<unit id>)            (existing binder code)
1. P_m = provides(method), P_d = provides(definition)
   "conn:<definition id>" not satisfied by P_m         -> capability_missing(<unit>, <method>, conn:<definition id>)
2. for clause in normalised unit.requires:
       no token t of clause satisfied by S(t)          -> capability_missing(<unit>, <method>, <render(clause)>)
       where S(t) = P_d if t is a conn: token, else P_m ∪ P_d
3. for clause in normalised method.requires:
       no token of clause satisfied by P_d             -> capability_missing(<unit>, <method>, <render(clause)>)
4. admitted; notices = sorted(evidence notices of unit, method, definition)   (D9)
```

`capability_unresolved` notices (D4) are attached to the result whether it is admitted or refused. A `conn:` token in a
unit's `requires` names a definition the unit accepts, so only the definition can satisfy it: a method provides `conn:`
tokens for every definition it supports, and admitting against P_m would admit a unit on a definition it does not accept
(W1 P1 review, finding 1).

`render(clause)` is the token for a one-token clause, else the tokens joined by `|` (`legacy:syn001|legacy:wilson-ig-v2`).
A unit declares the definitions its material side accepts with a `conn:` clause in `requires`; P_d always contains
`conn:<definition id>`. `capability_missing` has kind `not_supported`; its third parameter, `params.capability`, is the
missing token, and that is what R-931's agentic layer reads. `gap.capability` is the entry's fixed text: MSG keeps
static gaps (ADR 0058 entry field `gap`). (Erratum, F1 review: W4a-13.)

`admission_matrix(registry, definition)` returns every (unit, method) verdict over the registered `unit_model` ×
`property_method` descriptors, sorted by (unit id, unit version, method id, method version): the input of §2.4.3's
coverage matrix (built by F6).

Admission does not check platforms, component coverage, parameters or anything a revision supplies. Factory resolution
checks platforms (`platform_unsupported(<id>, <platform>)`) and optional dependencies (`dependency_missing(<id>,
<extra>)`); validation checks the rest.

### D6. Legacy registration, without a byte edit

**Built-in tables are generated data.** `scripts/registry_builtin.py --write | --check` writes
`src/openflowsheet/registry/builtin/legacy.json` (package data). `--check` regenerates in memory and fails with the
differing pointers; it prints one summary line. The registry reads the JSON at build; it never imports
`application.revision_binding`, a provider module or CoolProp to register them.

**Legacy property methods** (7; `version` `1.0.0`; `status` `released`; `platforms` `["any"]`; `pip_extra` from
`pyproject.toml` for CoolProp, else null): `syn001`, `pr-c1-v1`, `pr-lib-v1`, `iapws95-v1`, `coolprop-heos-v1`,
`wilson-ig-v1`, `wilson-ig-v2`. `provides` = `["conn:nTP-v1", "legacy:<id>"]`; `requires` = `[]`. Payload (closed):

| Field | Source the generator reads |
| --- | --- |
| `legacy_provider_id` | the module's `PROVIDER_ID` |
| `phases`, `flashes`, `properties`, `reference_convention` (string, or `"per_component"` for CoolProp) | a constructed provider's `describe()` (CoolProp: one per fluid; the table records the fluid → convention map) |
| `per_component` (erratum, F1 review: W2-2) | null, or for CoolProp a map fluid to `{reference_convention, properties, derivative_inputs}`; the top-level lists are those every fluid declares, in describe order |
| `derivative_inputs` | the module's declared inputs (`DERIVATIVE_INPUTS`, or `describe().derivative_order` keys) |
| `bases` | `selectable_bases()` entries with this provider id: `{record_source, components}` (127 bases in all) |
| `selectable` | whether `bases` is non-empty (false for `pr-lib-v1`, `wilson-ig-v1`) |
| `verifier_fresh` | membership in `FRESH_PROVIDERS` |
| `factory` (in `implementation`) | `openflowsheet.application.revision_binding:basis_provider` |

**Legacy units** (31; version `1.0.0`; status `released`). The generator enumerates them from `list_models` (30 entries:
the `MODEL_BUILDERS` keys with their `MODEL_SIGNATURES` entries) plus `syn001.cascade`, which has no signature; it does
not read `MODEL_BASES`. Payload `{family: syn001|c1|thermal, bindable, signature}`: `signature` is the unit's
`list_models` entry verbatim (ADR 0019 Amendment 2 shape), which is C2's parameter and port schema; `signature` is
`null` iff `bindable` is false, which holds only for `syn001.cascade`. `implementation.factory` =
`openflowsheet.application.revision_binding:MODEL_BUILDERS` with `key` = the model id (`factory: null` for the cascade).

**`requires` of a legacy unit** = `[["conn:nTP-v1"], <legacy clause>]`, with the legacy clause written by the generator
from this **family table**, a transcription of the design notes it cites. The generator must not read `MODEL_BASES`, so
the comparison in E-F1-1 is independent:

| Family rule (source) | Units | Legacy clause |
| --- | --- | --- |
| SYN-001 basis only (R-288, design note §14.4 D3) | `syn001.liquid_pump`, `conversion_reactor`, `component_separator`, `heat_exchanger`, `kinetic_cstr` | `legacy:syn001` |
| C1 basis only (R-288) | the 9 `c1.*` ids | `legacy:pr-c1-v1` |
| routing on every basis but C1's (S11 §4.4, ADR 0050 D3) | `syn001.feed_source`, `product_sink`, `stream_splitter` | `legacy:syn001 \| legacy:iapws95-v1 \| legacy:coolprop-heos-v1 \| legacy:wilson-ig-v2` |
| γ–φ faces (units design §4.5, §4.7) | `syn001.tp_heater`, `tp_flash`, `ph_flash`, `valve`, `adiabatic_mixer` | `legacy:syn001 \| legacy:wilson-ig-v2` |
| column (S11 §4.7, §9 I1) | `syn001.column` | `legacy:syn001 \| legacy:wilson-ig-v2` |
| pure-fluid thermal (units design §4.7 I1b) | `thermal.heater`, `valve`, `mixer`, `flash`, `pump` | `legacy:iapws95-v1 \| legacy:coolprop-heos-v1` |
| vapour machines (L-GP-2) | `thermal.compressor`, `thermal.turbine` | `legacy:iapws95-v1 \| legacy:coolprop-heos-v1 \| legacy:wilson-ig-v2` |
| not bindable (`revision_binding.py:1819`) | `syn001.cascade` | none (`bindable: false`) |

**`connection_definition` `nTP-v1`**: `provides ["conn:nTP-v1"]`, `requires []`, payload `{legacy: true,
state_definition: "nTP-v1"}`, `implementation.modules []`.

**Implementation sets.** Legacy provider: its module plus the modules F0's M9 scan attributes to it
(`coolprop-heos-v1` + `thermo/_coolprop_heos_fluids.py`; `wilson-ig-v2` + `thermo/wilson_ig.py`). Legacy unit: the files
F0 attributes to that model id (R-940, from its manifest); for an id F0 attributes none to (expected:
`c1.reactor_surrogate`), `openflowsheet/models/c1/reactor.py`, the model it is the surrogate of (R-301), recorded in the
build-decisions log. `syn001.cascade`: `modules: []` (`models/syn001/cascade.py` is not in M9, and the unit is not
bindable). E01 contributors: every `*.py` under the directory of the module defining the contributor factory. M9's paths
carry the `src/` prefix (`src/openflowsheet/thermo/pr_c1.py`); `modules` paths are relative to the import root and do
not (`openflowsheet/thermo/pr_c1.py`); E-F1-4 strips the prefix before comparing.

**Why legacy admission is an allow-list by design.** `MODEL_BASES` records decisions no surface rule reproduces (C1's
routing namesakes; the column refused on C1 because it is vapour-only; Wilson admitted to five γ–φ units only). A rule
derived from declared surfaces would also admit a new method to a closed legacy family, which R-929's retirement rule
forbids. The reserved `legacy` space makes "closed to new bases" an enforced property: no extension can provide a
`legacy:` token. The computed part of admission serves v2 (`std.*` against v2 methods), where F4 and F6 supply the
tokens.

### D7. Discovery, ordering, trust

Two sources, in this order: the **built-in tables** (`openflowsheet/registry/builtin/*.json`: `legacy.json` from D6;
`records.json` from ADR 0061; `core.json` for `functional_contributor`), and the entry-point group
**`openflowsheet.extensions`**.

**Entry-point contract.** The entry point's name is the extension's **namespace**
(`^[a-z][a-z0-9_]*$`). Its value names a zero-argument callable returning an *extension package document*
`{package_format: "openflowsheet-extension-package-v1", namespace, descriptors: [descriptor…]}`. The callable must import
only the standard library and `openflowsheet.registry`; implementations are imported only when a factory is resolved.
Every descriptor id starts with `<namespace>.`. A `message_entries` payload is `{catalogue: {package, path}}`, a YAML
document in MSG's format (ADR 0058) read through `importlib.resources`.

**Reserved namespaces:** the first segment of every built-in id (`syn001`, `c1`, `thermal`, …) and `openflowsheet`,
`core`, `std`, `legacy`, `x`, `user`. Using one is `reserved_namespace(<namespace>)`.

**Order.** Entry points are processed sorted by (normalised distribution name, entry-point name), UTF-8 byte order.
Registered descriptors iterate sorted by (kind, id, version key). Nothing depends on installation order or
`importlib.metadata`'s order.

**Quarantine, per package and atomic.** A package is registered whole or not at all. It is quarantined, with one typed
reason recorded in the snapshot (never fatal), when: its namespace is reserved; two distributions declare the same
namespace (both quarantined, `namespace_conflict(<namespace>)`; one distribution seen twice on `sys.path`, the same
normalised name and version, is deduplicated first and is not a conflict); the entry point fails
to load or its callable raises (`extension_load_failed(<entry point>)`; the exception class goes to the log, not the
code); its document fails the schema (`extension_invalid(<entry point>, <JSON pointer>)`); a token in a static space is
unknown, or a token is reserved (D4); a self-hash path is missing (D3); a message catalogue fails MSG's schema or
namespace rule (pre-validated, so registration in D8 cannot fail). Token validation reads only the package itself and
the static tables (names in registry-derived spaces are checked by grammar, D4), so one package's quarantine never
quarantines another.

**Trust (R6).** Installing a distribution into the Python environment is the code-execution trust boundary: whoever can
install can already run code. Every installed entry point is therefore loaded. Project-level governance acts on
*evidence*, not on loading: an extension without an attestation is `unreviewed`, and every result that uses it says so
(D9). The approval operation that records an attestation in a project (the `install` right, R6) belongs to the agentic
layer's approval settings and is not built in 0.5; until it exists, every non-built-in extension is `unreviewed`.

### D8. Build and closing

`openflowsheet.registry.default_registry()` builds the process registry once, under a lock, then **closes** it:
`register` afterwards raises `RuntimeError("registry_closed")`. Tests build independent instances with
`Registry.build(builtin_tables=…, entry_points=…, catalogue_register=…)`; the process registry is
never mutated by a test.

Build steps: (1) load and validate built-ins (a built-in failure raises); (2) discover, load and validate entry-point
packages (D7); (3) compute self-hashes; (4) register each `message_entries` catalogue with
`messages.catalogue.register(document, namespace=<namespace>)`, sorted by id; (5) compute the snapshot (D10); (6) close.
Extension `functional_contributor` descriptors are registered and listed only; nothing passes them to E01 in 0.5
(D1, risk 4).

**Ordering against MSG's freeze.** MSG freezes its catalogue at the first lookup. `messages/catalogue.py` (a 0.4 module,
not identity-bearing) gains one call: the first lookup calls `openflowsheet.registry.default_registry()` before it
freezes, so extension entries are present whatever the call order. `registry` imports `messages` only inside the build;
a catalogue lookup made on the building thread raises `RuntimeError("catalogue lookup during registry build")`.
`LocalApplication.create/open/in_memory`, `cli.main` and the HTTP and MCP servers also call `default_registry()` at
start.

**Extensions used.** A run's *extensions used* (D9) are derived from its documents, not from a recorder: the unit ids
and versions of its revision, the data lock's methods, its connection definitions, the record types it reads and the
contributors its assessment document names, each looked up in the registry snapshot (D10). A schema_version 1
revision's unit references resolve to the legacy descriptor's version (1.0.0); `model.version` is never a registry
version (erratum, F1 review: W3-12). v2 revisions carry registry versions (ADR-F2). A recorder alone could lose
the flag: it misses a factory result cached across runs, a worker thread that does not inherit the context, and a
concurrent run if the context were process-global. **Usage recorder (cross-check).** `registry.resolve(kind, id,
version=None)` (highest version when `None`) and factory resolution append (kind, id, version) to the active
`registry.usage()` context, a `ContextVar` that the run's executor copies into its workers; F8 compares its set with the
derived one.

### D9. Evidence class and the flag

- `origin` ∈ {`builtin`, `installed`, `contributed`}: `contributed` iff `contributed_by` is present, whatever the
  distribution; else `builtin` for the openflowsheet distribution, `installed` otherwise.
- `effective_status`: a built-in's declared `status` (the repository's lane rules govern it: agents never claim
  `reviewed` or `released` on their own work). A non-built-in's declared `reviewed` or `released` counts only with an
  attestation matching (id, version, `descriptor_sha256`, `self_sha256`); otherwise it is capped at `tested`. A code
  change moves the self-hash and a payload change moves the descriptor hash, so an attestation never outlives the code
  or the descriptor it reviewed (for a `correlation_form` or `record_type`, whose `modules` are empty, the descriptor
  hash is the whole content).
- `evidence_class` ∈ {`core` (built-in, effective status ≥ `reviewed`), `reviewed` (non-built-in with attestation),
  `unreviewed` (otherwise)}. R-931's "`contributed, unreviewed`" is `unreviewed` with origin `contributed`.
- **Flag:** the notice `extension_unreviewed(<id>, <origin>)` for every `unreviewed` descriptor a result used, and
  `preview_kind(<kind>, <id>)` for every `preview`-kind descriptor.
- **Propagation.** In 0.5: `list_capabilities` items and `check_admission` notices. From F8: `RunManifest.environment`
  carries the snapshot (D10); the run's extensions used are a structural member of `RunManifest` (ADR 0067 D2); the
  run's evidence report, not the certificate, carries the notices (ADR 0067 D6).
  **Evidence never moves an identity** (the rule Q9.R3 states for rights): `status`, attestations, `evidence_class` and
  the notices enter no `descriptor_sha256`, `registry_sha256`, `content_hash`, `constants_sha256`, `r0_sha256`,
  `state_sha256`, cache key or certificate check result. ADR-F8 places the notices outside the R0 projection.

### D10. Snapshot and `registry_sha256`

`registry_sha256 = sha256(canonical_json([[kind, id, version, descriptor_sha256, self_sha256] for every registered
descriptor, sorted by (kind, id, version key)]))`: the identity of what is loaded. It excludes evidence fields,
distribution versions and quarantine records, so it is identical across runs and platforms for the same code and
descriptors, and a review never moves it.

The **snapshot document** (`schemas/registry-snapshot.schema.json`): `{snapshot_format:
"openflowsheet-registry-snapshot-v1", registry_sha256, extensions: [{kind, id, version, self_sha256, descriptor_sha256,
origin, distribution, distribution_version, entry_point, status, effective_status, evidence_class, stability}…] sorted,
quarantined: [{distribution, distribution_version, entry_point, code, params}…] sorted}`. It is §2.7.3's registry
snapshot; F8 records it in `Environment` (non-structural).

### D11. Operations (ADR 0019 Amendment 7; rule C1: one row each, four transports)

| Operation | Right | HTTP | Request | Response |
| --- | --- | --- | --- | --- |
| `list_capabilities` | `read` | `GET /v1/capabilities?kind=&id_prefix=&cursor=&limit=` | `{kind?: [kind…], id_prefix?: string, cursor?: string, limit?: 1–200 (default 50)}` | `CapabilityPage {registry_sha256, items: [CapabilityDescriptor], next_cursor: string \| null}` |
| `check_admission` | `read` | `POST /v1/admission/check` | `{pair: {unit, method, definition?, unit_version?, method_version?}}` or `{revision: <ProcessRevision document>}` | `AdmissionReport` |

`CapabilityDescriptor` = the registered descriptor (declared and computed fields of D2). The cursor is the base64url of
the last item's (kind, id, version). MCP tools `list_capabilities` and `check_admission` with reviewed descriptions; CLI
through `openflowsheet api`, plus convenience commands `openflowsheet capabilities [--kind K] [--prefix P]` and
`openflowsheet admission --unit U --method M [--definition D] | --revision FILE`. Ids travel in query parameters and
bodies, never in URL paths.

`AdmissionReport {registry_sha256, admitted, pairs: [{instance: string \| null, unit, unit_version, method,
method_version, definition, admitted, refusal: {code, params} \| null, notices}], notices}`. Defaults: `definition` is
the unit's single `conn:` requirement when it has exactly one, else required (`invalid_request`); versions default to
the highest registered. An unknown id is `not_found` with `detail.suggestions`.

The **draft form** in 0.5 accepts a v1 revision: for each unit instance, the pair (instance model id, the provider id
`component_basis(document)` selects, `nTP-v1`); `admitted` is the conjunction. A v2 document is refused
`revision_unsupported` until ADR-F2's validator lands; F2 then adds its checks (anchors, basis compatibility, solid roles,
grids, thermal coordinate, legacy closure) to the same report.

### D12. Core at the end of W1, and what stays `preview`

**Core (frozen):** the envelope (D2) and its normalisation and hash; the id and version grammars; the self-hash (D3);
the token grammar, the space table and satisfaction (D4); the admission algorithm, its refusal codes and
`admission_matrix` (D5); the legacy payloads and the reserved `legacy` space (D6); discovery, namespace, ordering,
quarantine and trust rules (D7); build and closing (D8); evidence rules and the flag (D9); snapshot and
`registry_sha256` (D10); the two operations and their result shapes (D11); the payloads marked core in D1.
**Preview:** the payloads D1 assigns to later ADRs until those are Accepted, the kinds owned by X packages, and extension
`functional_contributor` descriptors (D1).

**Admission scope.** The frozen core is the token grammar, satisfaction and D5 for **single-side units**: one unit-level
`requires` evaluated against one method. In note §2.3.8 a unit evaluates each side with its own method set, and a stream
may carry `mixed` and `solid` substreams; ADR-F6 may add per-side `requires` and per-side admission **additively**, and a
single-side unit keeps D5's verdict unchanged.

---

## Alternatives rejected

- **Derive legacy admission from declared surfaces** (phases, properties, flashes). It cannot reproduce `MODEL_BASES`
  without special cases, and it would let new methods into closed legacy families (R-929).
- **Read `MODEL_BASES` to build the legacy tokens.** Makes E-F1-1 circular; the family table is an independent
  transcription.
- **A Python table of built-ins importing the binder.** Pulls the application layer and CasADi-heavy imports into
  registry build; generated JSON with `--check` is cheap and shows every change as a diff.
- **First-wins on conflicting extensions.** The result would depend on installation order. Both are quarantined.
- **Per-project enable lists that gate loading.** Loading is code execution, already granted by installation; a gate on
  loading protects nothing and makes one process's registry depend on which project it opened first. Governance is by
  evidence class instead (D9).
- **Self-declared `self_sha256`.** Authors would have to update it on every edit; the registry computes it.
- **Evidence status inside `registry_sha256`.** A review would move every environment hash; evidence is an assessment,
  like rights.
- **Free-form capability strings.** A typo would silently never be admitted; closed spaces make it a typed refusal.
- **Platform-aware admission.** The admission set would differ across platforms and break R0; platforms are checked at
  factory resolution.

---

## Migration proof

1. **No byte edit.** F0 (`scripts/corpus_identity.py --check`) passes on every work order; M9's 35 files are unchanged.
   The only edit outside new modules is the one-line pre-freeze call in `messages/catalogue.py`, which is not
   identity-bearing.
2. **Admission equals `MODEL_BASES`.** E-F1-1 below, as sets, over all 31 × 7 legacy pairs.
3. **Listings agree with the frozen contract.** Each legacy unit's `signature` equals its `list_models` entry; each
   legacy method's payload equals a constructed provider's `describe()` on the listed fields; `verifier_fresh` equals
   `FRESH_PROVIDERS`; `bases` equals `selectable_bases()` (E-F1-3).
4. **Self-hashes cover exactly the frozen set.** The union of legacy implementation sets equals F0's M9 set (E-F1-4).
5. **Existing schemas and digests.** `application-results` is widened additively; R4-G3 snapshots of existing
  operations and M8's round-trips are unchanged; the served MCP digest moves only by the two tools (re-taken and
  recorded, as ADR 0058 did).

---

## Exit tests (each falsifiable; F0 PASS is implied on every one)

- **E-F1-1 Legacy admission.** Universe, pinned: the registered legacy unit ids equal `set(MODEL_BASES)` ∪
  {`syn001.cascade`}, the registered legacy method ids equal the seven of D6, and ⋃`MODEL_BASES.values()` ⊆ those seven.
  Over 31 units × 7 methods, definition `nTP-v1`, the admitted set equals
  `{(u, m) : m ∈ MODEL_BASES.get(u, ∅)}` exactly: **54 admitted, 163 refused** (156 `capability_missing` naming the
  legacy clause; 7 `model_unsupported(syn001.cascade)`). Mutation controls: dropping `legacy:wilson-ig-v2` from
  `syn001.tp_flash`'s clause fails the test naming that pair; a test extension providing `legacy:syn001` is quarantined
  `reserved_capability(legacy:syn001)` and the admitted set is unchanged.
- **E-F1-2 No leakage.** A test method providing every registered non-`legacy` token is admitted to none of the 31; a
  test extension unit requiring `legacy:pr-c1-v1` is quarantined `reserved_capability(legacy:pr-c1-v1)`.
- **E-F1-3 Payload faithfulness.** As migration proof item 3; for CoolProp, all 123 fluids.
- **E-F1-4 Self-hash.** The union of the implementation sets of the 7 legacy methods and the 31 legacy units (the E01
  contributors excluded), with `src/` prefixed, = F0 M9 set (35 paths, listed on failure); every self-hash
  recomputes; a CRLF copy of one module in a temporary import root gives the same self-hash.
- **E-F1-5 Determinism.** `registry_sha256` of the built-in registry is identical in two fresh processes with
  `PYTHONHASHSEED=0` and `=random`, and equals the committed constant in `tests/fixtures/registry/builtin-sha256.txt` on
  every CI leg (Linux x86_64 and aarch64 now; the X07a legs when they exist, recorded `pending` until then).
- **E-F1-6 Discovery.** Fake distributions presented in three permutations give byte-identical snapshots; a duplicated
  namespace quarantines both (`namespace_conflict`), and one distribution seen twice on `sys.path` does not; a reserved
  namespace, a raising callable, a schema violation, an unknown token in a static space and a missing self-hash file
  each quarantine exactly their package with the stated code, and the build completes; a unit requiring
  `conn:nTP-v1 | conn:acme.slurry` without `acme` installed is registered and admitted on `nTP-v1` with the notice
  `capability_unresolved(conn:acme.slurry)`.
- **E-F1-7 Closing and MSG.** `register` after build raises; an extension's message entries resolve through `explain`;
  a catalogue lookup made before any explicit build still sees them; a lookup during build raises.
- **E-F1-8 Evidence non-interference.** Changing a descriptor's `status`, or adding an attestation, leaves
  `descriptor_sha256`, `registry_sha256` and every admission verdict unchanged and changes only `evidence_class` and the
  notices.
- **E-F1-9 Token semantics [gen].** 10⁴ random descriptor triples: `admit` equals a brute-force evaluation of D5;
  raising a provided level never turns an admission into a refusal; normalisation is idempotent. Fixed counterexample:
  definitions A and B, method M providing `conn:A` and `conn:B`, unit U requiring `[["conn:A"]]`: `admit(U, M, B)` is
  refused `capability_missing(U, M, conn:A)`.
- **E-F1-10 Operations.** Three requests per operation return identical canonical documents on python, CLI, HTTP and
  MCP; every new code has a catalogue entry (MSG G1/G2 pass); MCP digest re-taken; R4-G3 snapshots of existing
  operations unchanged.
- **E-F1-11 Draft admission.** For each of F0's M1 revisions (50), every instance is admitted; replacing one instance's
  model with one `MODEL_BASES` does not admit on that basis gives `capability_missing` from `check_admission` on all
  50, and `model_unsupported` from the binder, for the same instance, on the 38 revisions the binder reads as far as its
  model check. On the other 12 the binder refuses before its model check; that refusal is pinned and unchanged by the
  replacement. (Erratum, F1 review: the miscount "49" and W4b-4.)
- **E-F1-12 Contributors.** A dummy extension `functional_contributor` is registered and listed (`stability`
  `preview`); E01's `_REGISTERED` is unchanged; E01's assessment identity tests and F0 pass.

---

## New catalogue codes (ADR 0058 C3; each gets an entry in the WO that first emits it)

| Code | Family | Kind |
| --- | --- | --- |
| `capability_missing(<unit>, <method>, <capability>)` | refusal | `not_supported` (the missing token is `params.capability`; `gap.capability` is fixed text) |
| `capability_unknown(<token>)`, `reserved_capability(<token>)`, `reserved_namespace(<namespace>)`, `namespace_conflict(<namespace>)`, `extension_invalid(<entry point>, <pointer>)`, `extension_load_failed(<entry point>)`, `self_hash_unavailable(<id>, <path>)` | refusal | `input` |
| `platform_unsupported(<id>, <platform>)`, `dependency_missing(<id>, <extra>)` | refusal | `not_supported` |
| `factory_unavailable(<kind>, <id>)` (erratum, F1 review: W3-10): a null factory, or a legacy method with `selectable: false` | refusal | `not_supported` |
| `extension_unreviewed(<id>, <origin>)`, `preview_kind(<kind>, <id>)`, `capability_unresolved(<token>)` | notice | `notice` |
| `registry_closed` | refusal | `bug` |

`model_unsupported` exists. If X07a has already catalogued `platform_unsupported`, F1 reuses it with its params.

---

## Work orders (dependency order; "identity: no" means F0 must pass unchanged)

| WO | Content and files | Acceptance | Identity | Lane |
| --- | --- | --- | --- | --- |
| **F1-WO1** Registry core | new `src/openflowsheet/registry/{__init__,descriptor,tokens,capability,selfhash,snapshot}.py`; `schemas/extension-descriptor.schema.json`, `schemas/registry-snapshot.schema.json` (draft until Accepted); `tests/test_f1_registry_core.py` | E-F1-5 (on synthetic built-ins), E-F1-8, E-F1-9 | no | Opus |
| **F1-WO2** Legacy built-ins | `scripts/registry_builtin.py`; `src/openflowsheet/registry/builtin/legacy.json`; `registry/legacy.py`; tests | E-F1-1…4; `--check` clean | no | Opus |
| **F1-WO3** Discovery and integration (needs MSG merged) | `registry/discovery.py`; the pre-freeze call in `messages/catalogue.py`; E01 contributors listed (not passed to E01); extensions used and the usage recorder; fake-distribution test harness | E-F1-6, -7, -12 | no | Opus |
| **F1-WO4a** Operations, pair form | `application/contract.py` (Inspection), `operations.py` rows, `authz.py` rights, `local.py`, CLI conveniences, `application-results` `$defs`, catalogue YAML for D-codes, MCP digest and R4-G3 re-take, ADR 0019 Amendment 7 pointer, `interfaces-frozen.md` | E-F1-10 | no | Sonnet (pattern: ADR 0058 D7) |
| **F1-WO4b** Draft form | `check_admission` on a v1 document | E-F1-11 | no | Opus |
| **F1-WO5** Close-out | committed `builtin-sha256.txt`; CI job for E-F1-5 on both legs; evidence manifest; full gate | all E-F1 green; CI both legs | no | Sonnet |

**What each unblocks.** WO1: F2–F7 can register descriptors of their kinds; ADR 0061's WO1 (record types, forms).
WO2: the F1 exit's core proof; X01 rest can list the legacy surface. WO3: X01 rest's plugin path (entry points,
message entries, plugin-author documentation and an example plugin); the agentic layer's extension flag. WO4: rule C2
discovery for agents. X01 rest's "`pr-lib-v1` and `syn001.cascade` become selectable" is **not** unblocked by F1 alone
(risk 1).

---

## Risks and open questions (each with a default; work proceeds on the default)

1. **`pr-lib-v1` / `syn001.cascade` selectability (X01 rest).** Making `pr-lib-v1` a v1 basis reverses ADR 0050 D10 and
   R-615 and adds a base to a closed family (R-929). *Needs:* Frank's preference. *Default:* both stay registered,
   listed and not selectable; `pr-lib-v1` becomes usable through v2 (an F4 delegating composition), the cascade through
   `std.*` (F6). Reversible by a new decision and an additive `MODEL_BASES` change with new references.
2. **Plugins in-process (R6).** *Needs:* preference. *Default:* D7 (installation is trust; evidence flags govern). An
   out-of-process host would make those runs R3.
3. **MSG merge timing.** WO3 and WO4a need ADR 0058 on `main`. *Needs:* fact. *Default:* WO1, WO2 and ADR 0061's WOs
   proceed first.
4. **Extension contributors and E01.** E01 accepts only `cost`, `lca` and `derived` (`CONTRIBUTOR_ORDER`,
   `assessment/program.py:69`; `register_contributor` raises `ValueError` for any other name and overwrites the built-in
   for one of these, `:173-177`), so F1 cannot pass an extension contributor to E01 without amending ADR 0052.
   *Decided* (orchestrator, on the W1 P1 review's preference, `docs/roadmap/decisions.md` 2026-11-05): extension
   contributors are `preview` in 0.5, registered and listed only. They reach E01 only by an ADR 0052 amendment
   (namespaced names, run only when the assessment document names them, the assessment report carrying the flag), in
   ADR-F8 or X01 rest.
5. **`c1.reactor_surrogate`'s implementation set.** *Needs:* fact (F0's attribution). *Default:* D6's fallback.
6. **Attestation store and approval operation.** *Needs:* the agentic layer's approval design. *Default:* not in 0.5;
   every non-built-in is `unreviewed`.
7. **Windows and macOS.** E-F1-5 on those legs waits for X07a. *Default:* recorded `pending`; LF normalisation makes the
   hash independent of checkout line endings.

---

## Edits `target-architecture.md` needs (the orchestrator applies them)

1. §3 F1 scope: add `correlation_form` to the kinds list, with ADR 0061 as owner.
2. §3 F1: "Iteration is sorted by id, with a snapshot hash" → "Iteration is sorted by (kind, id, version); the snapshot's
   `registry_sha256` covers ids, versions, descriptor and self-hashes, and excludes evidence (ADR 0060 D10)".
3. §3 F1 exit: "admission over the legacy pairs equals `MODEL_BASES` exactly, as sets" → add "(31 × 7 pairs, 54
   admitted)".
4. §3 F1 "X01 rest": "`pr-lib-v1` and `syn001.cascade` become selectable" → "… through v2 (F4, F6); a v1 basis for
   `pr-lib-v1` would reverse ADR 0050 D10 and needs its own decision (ADR 0060 risk 1)".
5. §2.4.2: "Legacy families keep the frozen `MODEL_BASES`" → add "expressed as reserved `legacy:` tokens only built-ins
   may provide (ADR 0060 D6)".
6. §2.3.3: "Its `implementation_sha256` is the SHA over …" → "… is `sha256(canonical_json([descriptor_sha256,
   self_sha256]))` of its F1 descriptor (ADR 0060 D3)".
7. §2.7.3 and §2.7.7: the snapshot is ADR 0060 D10's; evidence classes never move an identity (D9).
8. §8: add a row "`Inspection` (ADR 0019): `list_capabilities`, `check_admission` — ADR 0060, Amendment 7 — 0.5".
9. §4: add the soft edge MSG → F1 (WO3, WO4a).

---

## Review applied (W1 P1 review, `docs/reviews/W1-P1-review.md`, 2026-11-05)

Status stays Proposed. Choices on findings 2 and 12 follow `docs/roadmap/decisions.md` (2026-11-05, the reviewer's
preference).

| Finding | Edit |
| --- | --- |
| 1 | D5 step 2: a `conn:` token is satisfied by P_d only, every other token by P_m ∪ P_d; E-F1-9 gains the fixed counterexample. |
| 2 | D1 `functional_contributor` row: extensions `preview` in 0.5, listed, never passed to E01; D8 step 6 and `contributor_register` deleted; E-F1-12 restated; risk 4 rewritten; F1-WO3 content. |
| 3 | D3: v2 `implementation_sha256` = `sha256(canonical_json([descriptor_sha256, self_sha256]))`; D9 attestation matches (id, version, `descriptor_sha256`, `self_sha256`); target-architecture edit 6. |
| 4, 5 | ADR 0061 (not this ADR). |
| 6 | E-F1-1 pins the universe (unit ids, method ids, ⋃`MODEL_BASES.values()`); D6 enumerates units from `list_models` (30) plus the cascade. |
| 7 | D6: `signature: null` iff `bindable: false`; cascade `modules: []`; M9's `src/` prefix stated; E-F1-4 over 7 methods and 31 units, E01 contributors excluded. |
| 8 | D4: static spaces strict, registry-derived spaces checked by grammar with notice `capability_unresolved`; D7 fixpoint and D8 step "token fixpoint" deleted; E-F1-6; code table. |
| 9 | D4: a non-built-in naming a `legacy:` token in `requires` or `provides` is `reserved_capability`; E-F1-2 extended to units. |
| 10 | D8: extensions used derived from the run's documents; recorder kept as a `ContextVar` cross-check; D9 propagation. |
| 11 | D2 `limitations`: validated against core catalogue keys plus the package's pre-validated message document, no lookup. |
| 12 | D12: core admission is for single-side units; ADR-F6 may add per-side `requires` additively. |
| 13 | D3: `registry_builtin.py --check` asserts `modules` contains the factory module's intra-package import closure. |
| N2 | D4 level grammar `(0\|[1-9][0-9]*)`; D2 normalisation drops `:0`. |
| N3 | D7: `namespace_conflict(<namespace>)` replaces `extension_conflict`; a distribution seen twice on `sys.path` is deduplicated; code table; E-F1-6. |

**Not applied:** notes N1 (`builtin-sha256.txt` `--write/--check`), N4 (exact-case module paths) and N5 (frozen or zip
builds): the review lists no exact edit for them, and the brief limited this pass to findings 1–21, the rulings, N2,
N3 and N6. They remain open for F1-WO1/WO5.

## W1 P3 review applied (`docs/reviews/W1-P3-review.md`, 2026-11-06)

Status stays Proposed. Cross-ADR edit from the W1 P3 review's consolidated list.

| Finding | Edit |
| --- | --- |
| S2, departure 6 | D9 propagation: extensions used are a structural `RunManifest` member (ADR 0067 D2); the evidence report, not the certificate, carries the notices (ADR 0067 D6). |

Not applied: none of the edits for this ADR.

## Errata (F1 review, 2026-11-11)

Status stays Proposed. The F1 review (`docs/reviews/F1-review.md`, MF-1 and the rulings) records departures of the build
on `wp/F1` from frozen core text (R-941) that the design lane has ruled on. The text above is edited in place; no core
decision changes beyond what the rulings say, and no code moves.

| Ruling | Edit |
| --- | --- |
| W2-2 | D6: the legacy payload gains `per_component`: null, or for CoolProp a map fluid to `{reference_convention, properties, derivative_inputs}`; the top-level lists are those every fluid declares, in describe order. |
| W4a-13 | D5 and the code table: `gap.capability` is the entry's fixed text; the agent reads the missing token in `params.capability`. |
| W3-10 (and W2-5) | Code table: `factory_unavailable(<kind>, <id>)`, refusal, `not_supported`, for a null factory and for a legacy method with `selectable: false`. D6's factory stays `basis_provider`. |
| "49" and W4b-4 | E-F1-11: 50 revisions; `capability_missing` on all 50, `model_unsupported` for the same instance on 38, the other 12 refused first by the binder, pinned and unchanged. |
| W3-12 | D8: a schema_version 1 revision's unit references resolve to the legacy descriptor's version (1.0.0); `model.version` is never a registry version. |

**Not applied here:** D4's convention source (ruling W1-8) waits for the design lane's `interfaces-frozen.md` §3 note
that ADR 0047 C1 requires; F1 then adds the two conventions (SF-5) and D4's source cell reads "§3 (six conventions)".
