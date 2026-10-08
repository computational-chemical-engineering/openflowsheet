# M06 — The diagnostic web shell (W26) and the external agent benchmark (W27): design note

**Status:** Proposed, design lane (`architect`), 2026-10-06, on `wp/M06` from `main` `67029fa`.
**Brief:** `docs/briefs/M06-design.md`. **Plan row (v1.2 §4.4, binding):** M06, lane Build lead / Design
second, gates W26 and W27. **Authority:** blueprint v3.1 §11.4, §12, §14.4 (SHA-256 `66f574b0…` verified
against the plan header); ADR 0019/0020 (the frozen contract), ADR 0006 (distribution rights), R-019 (no layer
parses ids), R-149 (schema `$id` move deferred), R-153 (M06 off the critical path).
**Companion records written with this note:** `docs/adr/0030-diagnostic-web-shell.md` (Proposed), ADR 0019
Amendment 3 (Proposed, appended to `docs/adr/0019-application-contract-v1.md`), register R-170…R-175.

This note stands alone: an implementer who has seen neither the brief nor the conversation builds from §5–§12.

---

## 0. Decisions at a glance

| # | Question | Decision |
| --- | --- | --- |
| 1 | Front end | Hand-written ES modules, no framework, no build step, no npm, no third-party code or assets shipped. Rendering through a 2-function in-house DOM builder that can only create text nodes (§5.1). |
| 2 | Where the source lives | `apps/web/` (blueprint §15), shipped as package data through the symlink `src/openflowsheet/_data/web → ../../../apps/web` (the `_data/schemas` pattern). |
| 3 | Serving | `openflowsheet serve-http --ui`: the unchanged HTTP binding plus a static mount at `/ui/` on the same origin (`bindings/web.py`). Off by default. No CORS. Strict CSP. |
| 4 | Browser auth | The existing bearer token, typed into a login form, kept in `sessionStorage` (opt-in `localStorage`), sent only in the `Authorization` header. Never a cookie, never in a URL the app builds. |
| 5 | Data access | Only `OPERATIONS` rows, through one `fetch` call site; route table generated from `OPERATIONS` and checked. Immutable records read through the raw export with a SHA-256 check; projections reassembled by a specified expander. |
| 6 | Testing | (a) Python: contract tests of every operation the UI calls, static scans; (b) Node's built-in test runner (test-time tool only, no `package.json`) on pure view-model and view functions against fixtures captured from real responses; (c) a headless-Chromium smoke test with a request log. |
| 7 | Contract asks (ADR 0019 Amendment 3) | Ask 1 **adopt**; Ask 2 **adopt, widened** to a row/column index; Ask 3 **defer**; Ask 4 **adopt** as `list_audit` (Python, CLI, HTTP; not MCP); Ask 5 **reject**; new Ask 6 **adopt**: element-level detail in `diff_revisions`. |
| 8 | Defects D1–D3 | **Already fixed on `main`** by T08 Phase 1 and verified live at `67029fa` (§3). No M06 work; a UI-level regression check only. |
| 9 | Q1–Q5 | Q1 no; Q2 the row index of §6.5, no symbolic text; Q3 no (it would make bundles irreproducible); Q4 no; Q5 own rows `read`, other principals' rows `read`+`policy`. |
| 10 | "Scenario view" | Defined as the run comparison (two finished solves, any revisions or policies), differences displayed, never judged (§6.7). |
| 11 | Fonts | System font stacks naming IBM Plex first; no vendored font files (keeps NOTICE's "no third-party binaries" true). |
| 12 | W27 | Tier 0 (no spend): provenance, artifact-access report and deterministic coverage classification of all 450 cases, against 450 and the 82-split. Tier 1 (Frank's spend): a registered 45-run stratified agent campaign at M07 on the v0.2 candidate, est. USD 15–45. Full 450 runs est. USD 150–450 is the expensive alternative. |

---

## 1. Problem and scope

**Build** the project's first browser client: a diagnostic workbench that lets a person inspect revisions,
validation and degrees of freedom, solve runs and their traces, certificates, failure bundles, streams and
units, equation rows, revision and run comparisons, and the history of what each principal (agent) did — every
byte of it obtained through the public application contract. Widen the contract minimally where a W26 view has
no source. Adapt the OpenIDAES-450 benchmark (CRAFTS) as an external agent benchmark with exact provenance,
coverage and disclosure of what is inaccessible.

**W26 minimum** (blueprint §14.4 + plan row): inspection, traces, revision comparison, agent history, equation
view, scenario view, all through the public contract.

**In scope:** the nine-screen wish list of `docs/design/web-shell-design-brief.md` §5 *minus* education mode;
read operations; `validate`; `submit_job` (solve) and `cancel_job`; the contract amendment of §4; W27 Tier 0,
the harness and scorer, and the campaign under Frank's spend decision.

**Out of scope (explicit):** any editing of revisions (`commit_change`, `preview_change` are not called by the
UI); a drawing canvas or editor; education mode (deferred, F5); SFILES/topology adapters (no comparison needs
one, plan row default); SSP/FMI/DEXPI/CAPE-OPEN; hosting the shell beyond loopback; TLS; changes to the solver,
verifier or any hashed replay artifact (Ask 3 is deferred for this reason); a project/corpus dashboard (Q4);
numerical cross-checking of OpenIDAES-450 (needs a plan amendment, audit note); the schema `$id` move (R-149,
its own change, §12 R6); unit conversion in the browser.

---

## 2. Constraints and invariants

1. **Contract only.** The browser issues HTTP requests to exactly two kinds of path: `/ui/…` static files and
   the `(verb, path)` of a row of `OPERATIONS` whose transports include `http`. No other endpoint is added for
   the UI. No store read outside an operation. No operation is re-implemented in the browser (§5.6 lists the
   client-side derivations that are permitted; anything else needs a design decision).
2. **Identity does not move.** R0, `structural_sha256`, every run/replay bundle byte, the `t07` identity key,
   the K05 identity and every registered digest stay bit-identical. M06 touches no hashed artifact. The two
   contract additions that touch code near the structural layer (§4.1) are refactors proved inert on the
   50-revision T07 corpus (gate G3).
   *As built (M06 review F3b):* one registered digest does move — the served MCP tool list, `171dd768…` →
   `6c4375b4…`, because `diff_revisions`' served `outputSchema` carries A3.2's `elements` (R-192; the
   decomposition test `tests/test_t08_w2_surface_digest.py` recovers `171dd768…` with that member removed).
   Every other digest and every hashed artifact is unchanged.
3. **Frozen contract changes by amendment only** (ADR 0019 Amendment 3, additive). Store schema stays
   `t07-store-v1` (no table, column or index is added).
4. **Licence.** The project is **Apache-2.0** (`LICENSE`, `pyproject.toml`, `NOTICE`). M06 ships no third-party
   code, font or image; every file under `apps/web/` is project-authored. `NOTICE`'s "This project distributes no
   third-party binaries" stays true. The prototype (`docs/design/web-shell/Workbench.dc.html`, `support.js`) is a
   visual reference only: no markup or code is copied from it; its token values (README table) are design data.
5. **No network at run time beyond the serving origin**; no CDN; no absolute `http(s)://` URL in `apps/web/` other than the SVG namespace name `http://www.w3.org/2000/svg` (an identifier, never fetched).
6. **Gate stays green:** `./scripts/check.sh` (ruff, ruff format, mypy strict, pytest) plus the new Node step;
   UI tests run in CI without a GUI.
7. **Design system:** light and dark; status always glyph + word + tone; green only for VERIFIED, PASS, MATCH;
   tabular numerals; SI units in headers, never converted; full precision on demand; keyboard navigable.
8. **Precision.** JSON numbers are binary64 on both sides; the UI never rounds a value it compares; displayed
   rounding is a view setting with the full value always one action away (§5.5).

---

## 3. Corrections to the inputs (verified at `67029fa`)

| Claim | Where | Fact | Evidence |
| --- | --- | --- | --- |
| D1–D3 "remain; the recon confirmed them present" | brief §7, recon | **False.** All three were fixed in T08 Phase 1 (W1.2 D1, W1.3 D3, W1.4 D2; Q-P1-1 filled the initializer bundle's identity; D1's rule extended to STR-04/05 by Frank), `docs/T08_DECISIONS.md` 2026-09-29. | Live probe through `LocalApplication` at `67029fa`: STR-03 (`SYN-001-conflicting-heater-spec`) message reads `over-specified units ['heater']`; the A02-352 `HOMOTOPY_STALLED` bundle has `replay_identity.policy_id = "T04-W12"`, a full `plan_id`, and `observations.counters.property_calls = 2104`. Tests `tests/test_t08_w1_d1_instance_ids.py`, `…_d2_replay_identity.py`, `…_d3_counters.py`, `…_identity_substitution.py`. |
| "The project is MIT" | brief §4 | **False.** Apache-2.0. MIT is the OpenIDAES-450 repository's licence. | `LICENSE`, `pyproject.toml` `license = "Apache-2.0"`, `NOTICE`. |
| Agent history "has no source today" | gap triage G9 | **Half true.** Effects are reachable: `list_revisions` (principal, parent, time), `list_jobs` (`Job.request` holds revision, policy and idempotency key). Missing: refusals, commit idempotency keys, capability ids, cancels, policy events. | `job.schema.json` requires `request`; `revision_summary` has `principal_id`. |
| Projection = `document`, `$ref`, `overflow` | recon §4 | Envelope is `subject_id, pointer, sha256, value, truncated, next_cursor`; elisions are `{"$elided": {"pointer", "members"|"items"}}`; nested arrays keep 20 items. | `application/projection.py` docstring; probe. |
| Page = `items, cursor, count, remaining` | recon §4 | `items, next_cursor`. | probe of `list_revisions`. |
| `RevisionSummary` carries validation status and last run | recon §4 | It carries neither (`content_sha256, created_at, head, parent_revision, principal_id, revision_id, title`). | `application-results.schema.json#/$defs/revision_summary`. |
| CLI `openflowsheet serve` | recon §2 | The command is `serve-http` (and `serve-mcp`). | `application/cli.py`. |
| `diff_revisions` shows "added unit, changed specification" | design brief §5.7 | It recurses into objects but compares **arrays atomically**, so any change inside `instances`, `connections` or `specifications` reports only that top-level name. Hence Ask 6. | `transactions.semantic_diff`; probe: NET-02 vs STR-03 → `changed: ["connections","instances","specifications"]`. |

---

## 4. The contract amendment (ADR 0019 Amendment 3) — decisions on the asks

The normative text is the amendment appended to ADR 0019; this section is its rationale and full detail.

### 4.1 Asks 1 and 2 — `inspect_structure` gains a row/column index; an unroutable revision returns its analysis

**Why.** The validation/DOF screen of an over-specified revision (STR-03) needs the candidate rows and per-unit
degrees of freedom, which today exist only as prose in a check message (Ask 1). Every diagnostic must reach its
equation rows (blueprint §12), which needs a row's owning instance, its role, the specification it carries, its
incidence and the units involved (Ask 2, widened). The data exists in the traced `Declaration`
(`graph/trace.py:345`: `rows[row_id].columns`, `.kind`, `.unit`, `.specification_id`, `.is_specification_row`;
`column_kinds`) and the `ProcessGraph` (`instance_ids`, `column_owners`, `connections[].state_columns`). It is
put in the `inspect_structure` **envelope**, beside `structural_report`, never inside it, so
`structural_sha256` and R0 cannot move. `inspect_structure` is in no identity key (its docstring).

**Document after the amendment.** Routed branch:

```
{ "solve_path", "route_reason", "structural_report",          # unchanged
  "rows":    [RowEntry, …]     in Declaration.row_ids order,
  "columns": [ColumnEntry, …]  in Declaration.column_ids order }
```

Unroutable branch:

```
{ "not_run_reason", "hint",                                    # unchanged
  "validation_structural_report": StructuralReport document | null,
  "rows": [RowEntry, …] | null, "columns": [ColumnEntry, …] | null }
```

`RowEntry` — all members always present:

| member | value |
| --- | --- |
| `row_id` | the row id |
| `unit_id` | `TracedRow.unit` (the authoring unit as the binder named it), or null |
| `instance_id` | `graph.instance_ids[unit_id]`, or null when absent |
| `role` | `"specification"` iff `TracedRow.is_specification_row`, else `"model"` (the same predicate `unit_degrees_of_freedom` uses) |
| `specification_id` | the revision specification this row realises: on `legacy_eo` `binding.specification_ids.get(row_id)`; on `revision_eo` the revision binder's attribution of assembler-authored specification rows (see the implementation note below); null when none |
| `kind` | `TracedRow.kind` (a `QuantityKind` string), or null |
| `si_unit` | `models.revision_flowsheet.si_unit(kind)` when `kind` is known to it, else null (no exception) |
| `columns` | `TracedRow.columns` in declaration order (the row's incidence) |

`ColumnEntry`:

| member | value |
| --- | --- |
| `column_id` | the column id |
| `kind`, `si_unit` | `Declaration.column_kinds[column_id]` and its SI unit (null when unknown) |
| `owner_unit`, `owner_instance` | `graph.column_owners.get(column_id)` and its instance id (null when absent) |
| `connection` | the `stream_id` of the graph connection whose `state_columns` contain it, else null (lifted and unit-owned columns are null) |
| `coordinate`, `component` | for a connection whose revision `state_definition` is `nTP-v1` and whose `state_columns` has length `N_c + 2` (N_c = components in the binder's component order): position `i < N_c` → `("n", component_i)`, `N_c` → `("T", null)`, `N_c+1` → `("P", null)` (ADR 0001 D1.1's `(n, T, P)` order). Otherwise both null. |

**No member is derived by parsing an id** (R-019). The positional rule lives in one Python function; a test (not
product code) confirms, on the whole corpus, that it agrees with the binders' naming.

**Implementation note (binding on the implementer).** The index is built from the *same* `Declaration` and
`ProcessGraph` objects that produced the report in that call: replace the single `analyse(...)` call in
`route_analysis` (routed branch) and in `validation._analysed` (unroutable branch) by its two documented halves,
`trace_declaration(...)` then `analyse_declaration(...)` (`graph/analysis.py:59–91`, which is exactly
`analyse`'s body), keeping every argument identical — in particular `route_analysis` keeps passing
`specification_ids={}` on `revision_eo`, so the report is unchanged. For the `revision_eo` `specification_id`
column, use the revision binder's own record of which specification each assembler-authored row realises. If the
revision binder holds no such record (`RevisionBinding` has no `specification_ids` field today), **add one
computed where the binder builds those rows** and use it only for the index — never pass it to
`analyse_declaration` on `revision_eo`. If that is not possible without touching the declaration or its order,
stop and escalate; do not set the member from id text.

**Unroutable branch.** `validation_structural_report` is the report `validate()` already analysed for this
document (`_analysed(document)[0]`), its document form, or null when no structural stage ran; `rows`/`columns`
come from that analysis's declaration and graph. `validate()`'s output must stay byte-identical (gate G3).

### 4.2 Ask 6 (new) — `diff_revisions` gains element-level detail

**Why.** W26 requires revision comparison, and the current diff reports "instances changed" for any change
inside any instance (§3). A finer comparison computed in the browser would be a second diff with its own rule
for excluded descriptive members — exactly the divergence principle 3 of the design brief forbids. So the
contract gets it, for every client (MCP agents included).

**Change.** `application-results.schema.json#/$defs/semantic_diff` gains the **required** member `elements`.
`added`, `removed`, `changed` keep their exact current values. `transaction-result.schema.json`'s inline `diff`
is **not** changed: `commit_change` and `preview_change` results are unchanged, and ledger replays stay valid.

```
elements: [ { "member": "instances" | "connections" | "specifications",
              "id": <string> | null,
              "change": "added" | "removed" | "changed",
              "paths": [ [token, …], … ] } ]
```

Rule (`transactions.element_diff(before, after)`, called by `diff_revisions` only):
- For each `member` in the order instances, connections, specifications: if in both revisions every item is an
  object with a string `id` and the ids are unique within each revision, pair items by `id`. An id only in
  `after` → `added`; only in `before` → `removed`; in both with non-equal items → `changed`, with `paths` =
  every path the `semantic_diff` walk reports inside the item (keys added, keys removed, values changed; objects
  recursed by key, every other value compared atomically), each path an array of keys from the item's root,
  sorted by code-point order of the keys. `added`/`removed` have `paths: []`.
- If ids are absent or not unique in either revision, and the member differs, emit one entry
  `{member, id: null, change: "changed", paths: []}`.
- A member whose items differ only in order produces no entry (the coarse `changed` still names it; the UI
  says "order changed only").
- Order: by member as above, then by `id` in code-point order.
- `CONTENT_HASH_EXCLUDED` is top-level only and these members are content, so no exclusion applies inside items.

### 4.3 Ask 4 — `list_audit` (agent history)

**Why.** "What the agent was allowed to do" is visible only in refusals, and a commit's idempotency key only in
the ledger. Both have no read operation. Effects alone are reachable (§3), refusals are not, and the supervisor
persona needs them.

**Operation.** A ninth `Inspection` method:

```
def list_audit(self, *, principal_id: str | None = None, operation: str | None = None,
               order: Literal["ascending", "descending"] = "ascending",
               cursor: str | None = None, limit: int = 50) -> Page[AuditRecord]
```

| item | value |
| --- | --- |
| `OPERATIONS` row | name `list_audit`, right `read`, HTTP `GET /v1/audit` (all members in the query), transports `("python", "cli", "http")`, no MCP tool, no description file |
| request schema | `principal_id`: `job.schema.json#/$defs/id` or null; `operation`: string 1–128 or null; `order`: enum; `cursor`: `CURSOR`; `limit`: `_limit(MAX_PAGE)` (1–200). A string enum, not a boolean, because the HTTP binding converts only numeric query values (`bindings/http.py` `_query_value`). |
| response schema | `application-results.schema.json#/$defs/audit_page` = `{items: [audit_record], next_cursor: string|null}`, closed |
| `audit_record` | closed, all required: `seq` (integer ≥ 1), `at` (timestamp), `principal_id`, `capability_id`, `operation` (string), `outcome` (`allowed`/`refused`), `code` (string|null), `request_sha256` (sha256|null), `effect` (string|null, as stored: `<kind>:<id>`), `idempotency_key` (string|null) |
| `idempotency_key` | for an `allowed` row, the ledger's key where `ledger.principal_id = audit.principal_id AND ledger.operation = audit.operation AND ledger.request_sha256 = audit.request_sha256`; else null. **Precondition (test it first):** for `commit_change` and `submit_job` the hashed request includes the key (two requests differing only in the key hash differently), so the join is unique. If not, stop and escalate. |
| authorization | `authorize(capability, "list_audit", target_principal=principal_id)`. Required rights: `read`, plus `policy` when `target_principal != capability.principal_id` (so `principal_id` omitted = all principals = `policy`). This is `cancel_job`'s rule exactly; `authz.authorize` reads `target_principal` for these two operations. A refusal is audited like any other. |
| order and cursor | by `seq`. Cursor = `base64url(canonical_json({"order": o, "seq": s}))` unpadded, `s` the last `seq` returned; next page is `seq > s` (ascending) or `seq < s` (descending). A cursor whose `order` differs from the request's is `invalid_request` at `/cursor`. |
| store | one read-only query (LEFT JOIN of `audit` with `ledger`), no new table, column or index; the ledger primary key's prefix `(principal_id, operation)` bounds the join. |

**Not on MCP** in M06: no agent task needs it, and an MCP tool needs a reviewed description (gate G15). Adding
it later is one transport entry plus a description and its review.

### 4.4 Ask 3 — `blocked_by` in failure bundles: **deferred**

It writes into `failure-bundle.json`, a hashed replay artifact, and is solver/verifier record work the brief
puts out of M06's scope. The UI shows the closing message and says "blocked variable: not recorded". Backlog
entry for a solver-records package (default: v0.3 planning).

### 4.5 Ask 5 — operation rights in `get_project`: **rejected**

The UI and the server ship in one wheel; the UI's route table (with each operation's right) is generated from
`OPERATIONS` and checked by a test (§5.3), so it cannot drift. An MCP agent learns a missing right from the
`forbidden` error's `required` detail. The UI only *disables* controls by right; the server still decides, and
the UI does not replicate `cancel_job`'s extra rule (it shows the server's refusal).

---

## 5. Architecture

### 5.1 Front end: no-build ES modules

**Decision.** Plain JavaScript ES modules loaded by the browser as written; plain CSS with custom properties;
no framework, no transpiler, no bundler, no `package.json`, no vendored library.

**Rejected, with reasons.**
- *A JS toolchain (npm + Vite/TypeScript/React).* Either the built output is committed (reviewers cannot see
  that it matches its source; two sources of truth) or the wheel/sdist build needs Node (a `pip install` from
  sdist would then need Node). It adds hundreds of transitive packages to the supply chain and licence
  inventory of an Apache-2.0 project whose NOTICE promises no third-party binaries. The UI is read-mostly
  tables over JSON — the benefit of a reactive framework is small.
- *A small vendored library (Preact+htm, lit-html, Alpine).* No build, but an opaque minified file to inventory,
  update and audit; its benefit (diffing re-render) is not needed when each navigation re-renders one screen.

**The rendering API (`apps/web/js/h.js`).** `h(tag, props, ...children)` returns a plain tree
`{t, p, c}` (strings become text leaves); `mount(tree, parent)` turns it into DOM. `mount` creates text with
`document.createTextNode(sanitize(text))` and sets only whitelisted attributes (`class, id, title, href, role,
aria-*, data-*, tabindex, type, value, disabled, colspan, rowspan, scope, for, name, checked, selected`, and SVG
`viewBox, x, y, x1, y1, x2, y2, width, height, d, rx, points, transform, text-anchor, marker-end, refX, refY,
markerWidth, markerHeight, orient`; SVG elements `svg, g, defs, marker, path, rect, line, polyline, text`
created in the SVG namespace). `href` must
start with `#`. Event handlers (`props.on = {click|change|input|keydown|submit}`) are allowed only on `button,
a, input, select, textarea, form, summary`; anything else throws. There is no way to set `innerHTML`,
`style`, `src`, or an `on*` attribute. Because `view()` functions return plain trees, they run in Node.

**Module layout.** `apps/web/`: `index.html`, `favicon.svg`, `css/tokens.css`, `css/app.css`,
`js/main.js` (boot), `js/api.js` (the only network code), `js/routes.js` (generated), `js/router.js`,
`js/auth.js`, `js/h.js`, `js/text.js`, `js/model/*.js` (pure derivations: no `document`, `window`, `fetch`),
`js/screens/*.js` (each exports `async load(params, api)` and pure `view(data)`). File extension `.js` only.
`index.html` has no inline script or style.

### 5.2 Packaging and serving

- Source of truth `apps/web/`; symlink `src/openflowsheet/_data/web → ../../../apps/web`; `pyproject.toml`
  package-data globs per directory (`_data/web/*.html`, `_data/web/*.svg`, `_data/web/css/*.css`,
  `_data/web/js/*.js`, `_data/web/js/model/*.js`, `_data/web/js/screens/*.js`); `openflowsheet.resources`
  registers them; `scripts/t08_dist.py` (T08.A43) then proves the wheel's and sdist's bytes equal the commit's.
- `src/openflowsheet/application/bindings/web.py`, under the bindings' import rule (T07 design note §11.6 (2): contract,
  types, operations, projection, plus `bindings.http`, `openflowsheet.resources` (stdlib-only), the standard
  library, starlette and uvicorn; never `local` or `authz`):

```
create_web_app(owner) -> Starlette:
    app = http.create_app(owner)                       # the API, unchanged
    app.router.routes += [Mount("/ui", app=_Headers(StaticFiles(directory=STATIC, html=True))),
                          Route("/", 307 redirect to "/ui/", methods=["GET"])]
    return app
STATIC = Path(as_file(packaged("web"))).resolve()      # follow_symlink=False
```

- `mimetypes.add_type` at import for `.js` → `text/javascript`, `.css` → `text/css`, `.svg` → `image/svg+xml`,
  `.html` → `text/html` (system tables differ; a module script served as `text/plain` does not run).
- `_Headers` adds to every `/ui` response: `Content-Security-Policy: default-src 'none'; script-src 'self';
  style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none';
  frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
  `Cache-Control: no-cache`, `Cross-Origin-Opener-Policy: same-origin`, `Cross-Origin-Resource-Policy:
  same-origin`. API responses are unchanged.
- CLI: `serve-http` gains `--ui` (default off; help: "also serve the diagnostic web shell at /ui/ — static files
  only; every data request needs a bearer token"). With `--ui` it calls `web.serve(...)` (same signature and
  loopback/`--allow-remote` rules as `http.serve`) and prints `openflowsheet: web shell at
  http://<host>:<port>/ui/` on stderr. Missing package data refuses the start with exit 1 and a message.
  Without `--ui`, behaviour is byte-identical to today.
- Assets are versioned by the package version; no fingerprinted names; `no-cache` + ETag revalidation.

### 5.3 The route table and the single network call site

`scripts/m06_web_routes.py --write|--check` generates `apps/web/js/routes.js` from `HTTP_OPERATIONS`:
`export const ROUTES = Object.freeze({<name>: {verb, path, right, path_params: [...], members: [...]}})`, keys
sorted, with a header line naming the generator. A test runs `--check`. `api.js` is the only file containing
`fetch(` (exactly once); it builds every URL from `ROUTES`:

- path parameters: `encodeURIComponent(String(value))` (an artifact id's `/` travels as `%2F`);
- `GET`: remaining non-null members as query text (numbers via `String`); `POST`: remaining non-null members as
  a JSON body with `Content-Type: application/json` (the UI never sends a non-finite number);
- options `{method, headers: {Authorization: "Bearer " + token}, cache: "no-store", credentials: "omit",
  redirect: "error", signal}`;
- 401 → clear the stored token, show the login screen with the server's message; other non-2xx → throw the
  `ApiError` document; a domain result (INVALID report, failed job) is not an error.

`api.raw(artifact_id, expected_sha256)` calls `artifact_bytes` and returns the bytes plus `digest`:
`"match"`/`"mismatch"` from `crypto.subtle.digest("SHA-256")` against the registered `sha256` of the bundle
listing, or `"unchecked"` when `crypto.subtle` is unavailable (an insecure context, i.e. `--allow-remote` over
plain HTTP). A mismatch shows a bad-tone banner above the record.

### 5.4 Reading whole documents: raw export for records, the expander for projections

- **Bundle members and other artifact files** (certificate, solve events, solution state, structural report,
  failure bundle, manifests, execution plan, revision as solved) are read whole through `artifact_bytes`
  (`GET /v1/artifacts/{id}/raw`) and parsed with `JSON.parse`. One request, exact bytes, digest-checked.
- **Revisions, structure, bundle listings** have no raw form and are reassembled from projections by
  `api.readWhole(name, args)`:

```
readWhole(name, args):                       # budget: 500 requests per document, else a visible error
  first = page(name, args, "")               # depth 12, limit 200; follows next_cursor for an array target
  sha = first.sha256                         # every later response must carry the same sha256, else error
  return expand(first.value, "")
expand(node, at):
  if isMarker(node, at):                     # {"$elided": {"pointer": at, "members"|"items": n}}, sole key
      v = page(name, args, at).value
      if deepEqual(v, node): return node     # literal content shaped like a marker: keep it, do not loop
      return expand(v, at)
  if array and last item m is {"$elided": {"pointer": at, "items": n}}:   # a nested array cut at 20
      return expand(page(name, args, at).value, at)                       # refetch the whole array
  if array: map expand(item, at + "/" + i)
  if object: map expand(value, at + "/" + escape(key))                    # RFC 6901 escaping
  else: node
```

A `truncated: true` view is complete at the depth it shows (projection contract), so its markers expand like
any other. Strings in projections arrive bounded by the server (T07 design note §10.4).

**Caching.** Within a page session, results of `get_revision`, `inspect_structure`, `diff_revisions`,
`get_artifact`, `artifact_bytes`, `list_models` and `validate` are cached by `(name, canonical args)`;
`get_job_result` once the job is terminal. Nothing else is cached.

**Live jobs.** For a non-terminal job the run screen loops `wait_job(job_id, after_sequence=last, timeout_s=20)`
(one outstanding call per view; `AbortController` on navigation), appends job events, and loads the result once
the job is terminal (`completed|failed|cancelled|timed_out`).

### 5.5 Text, numbers, status

- `sanitize(s)` replaces the code points of `projection.FORBIDDEN_RANGES` with U+FFFD. The JS table is a literal
  block between `// BEGIN FORBIDDEN_RANGES` and `// END FORBIDDEN_RANGES` markers; a Python test asserts it
  equals `projection.FORBIDDEN_RANGES`. Applied by `mount` to every text node; no length cut (long ids use CSS
  ellipsis with a `title`).
- `fmt(x, mode)`: null/undefined → `—`; integer → `String(x)`; otherwise mode `short` → `x.toPrecision(6)` with
  trailing mantissa zeros and the `+` of the exponent removed; mode `full` → `String(x)` (shortest round-trip,
  identical to Python's `repr`). Every numeric cell carries `title = String(x)`; copy uses the full value; a
  global toggle switches all tables to `full`. No locale formatting, no grouping. Numeric cells right-aligned,
  `font-variant-numeric: tabular-nums`.
- Units: SI strings from the server (`si_unit` of the index); headers only; **no conversion** anywhere in the UI.
  Revision values are shown as written, labelled "as written".
- Status pills (glyph + word + tone): ok ✓ `VERIFIED, PASS, MATCH`; info ◐ `CONVERGED, READY_FOR_SIMULATION,
  queued, running, completed, allowed`; warn ! `RELAXED, UNVERIFIED, DRAFT, near_threshold, cancelled,
  timed_out`; none – `NOT_RUN`, null; bad ✕ `FAILED, INVALID, MISMATCH, FAIL, failed, refused` **and every label
  not listed** (the typed failures are an open list).
- Tokens: `css/tokens.css` holds the README table for light and dark (`prefers-color-scheme`, overridden by
  `html[data-theme]` set from a toggle remembered in `localStorage`, wrapped in try/catch). Measured: every token
  text colour has ≥ 4.5:1 contrast on `bg`, `surface`, `sunken` and `select` in both themes, and every pill
  fg/bg ≥ 5.69:1, **except `ink-3` on `select` in light (4.39:1)**: selected rows therefore set
  `--ink-3: var(--ink-2)`. Font stacks: sans `"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", Roboto,
  sans-serif`; mono `"IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono",
  monospace` (Plex used only if installed locally).
- Product name in the UI: **OpenFlowsheet** (never the design brief's working name).

### 5.6 Client-side derivations: the permitted list

These are display arithmetic over recorded values, each with the exact rule; nothing else is computed in the
browser.

1. **Per-attempt counters** = an `attempt_closed` event's `counters` minus the matching `attempt_opened`'s,
   matched by `(step_index ?? null, attempt)`; `attempt_closed` events with non-null `homotopy_level` are
   correctors, not attempts (the rule of `verify/failure.py`); counters not attributed to any attempt =
   final event's counters − Σ attempt deltas, shown as "outside attempts".
2. **Scaled residual** = certificate check `value / reference` for `category == "residual"`, the row being the
   check's `subject`.
3. **Vapour fraction** of a `phase_branch` entry = `vapor_total / (vapor_total + liquid_total)`; component
   columns of `liquid`/`vapor` arrays are labelled in the revision's component-set order.
4. **Run comparison differences** (§6.7): Δ = b − a and `|Δ| / max(|a|, |b|)` (0 when both are 0).
5. **Flowsheet layout** (§6.1).
6. **Joins and inversions of server indexes**: the row matched to a column (`canonical_matching`), rows
   incident on a column (inverse of `rows[].columns`), the job list of a revision (filter of `list_jobs` items by
   `request.body.revision_id`), a revision's expected revision in history (= its `parent_revision`, exact
   because `commit_change` requires `expected_revision == head`).
7. Filtering, sorting and client paging of loaded lists.

Prohibited in the browser: unit conversion; any validation, DOF, matching or redundancy computation; any
verification judgement (pass/fail, near-threshold, agreement); diffing documents; replicating authorization
beyond greying a control for a missing right.

---

## 6. Screens → operations

Routes are hash routes; `?k=v` after the route path is parsed with `URLSearchParams`; the key `token` is
reserved for boot (stored, then removed with `history.replaceState`).

| Route | Screen | Operations (in call order) |
| --- | --- | --- |
| `#/login` | Token entry | `get_project` (verifies the token) |
| `#/` | Project: header, revision list, recent jobs | `get_project`, `list_revisions` (all pages, ≤ 50 pages), `list_jobs` (first page) |
| `#/rev/{rid}` | Revision overview | `get_revision` (readWhole), `validate(rid,"simulation")`, `list_jobs` (pages, filtered), `list_models` |
| `#/rev/{rid}/validation` | Validation and DOF | `validate`, `inspect_structure` (readWhole) |
| `#/rev/{rid}/row/{row}` | Equation view (structure only) | `inspect_structure` |
| `#/job/{jid}` | Run: summary, attempts, trace, bundle files | `get_job`, `list_job_events`, `wait_job` (live), `get_job_result`, `get_artifact` (bundle listing, readWhole), `artifact_bytes` (solve-events, run-manifest, execution-plan, solve-path) |
| `#/job/{jid}/certificate` | Certificate | `artifact_bytes` (solution-certificate) |
| `#/job/{jid}/failure` | Failure bundle | `artifact_bytes` (failure-bundle) |
| `#/job/{jid}/streams` | Streams and units | `artifact_bytes` (revision, solution-state, structural-report, certificate), `inspect_structure`, `list_models` |
| `#/job/{jid}/row/{row}` | Equation view at a run's state | as streams |
| `#/job/{jid}/file/{name}` | JSON tree of any bundle member + download | `artifact_bytes` |
| `#/compare/rev/{a}/{b}` | Revision comparison | `diff_revisions`, `get_revision` ×2 |
| `#/compare/run/{j1}/{j2}` | Scenario view (run comparison) | per job: `get_job_result`, `get_artifact` (listing), `artifact_bytes` (run-manifest, solution-state, solve-events, certificate or failure-bundle) |
| `#/history` | Agent history | `list_audit` (descending; principal filter), then per row as linked: `list_revisions`/`get_revision`, `diff_revisions`, `validate`, `get_job`, `get_job_result` |
| actions | Solve; Cancel | `submit_job`; `cancel_job` |

The UI-used operation set is exactly these **17**: `get_project, list_models, list_revisions, get_revision,
diff_revisions, inspect_structure, validate, list_jobs, get_job, list_job_events, wait_job, get_job_result,
submit_job, cancel_job, get_artifact, artifact_bytes, list_audit`.

### 6.1 Revision overview
Header: title, `revision_id`, `content_sha256[:12]`, parent, principal, `created_at`. Validation pill and
`structural_counts`. Runs of this revision (time, job, policy, outcome pill, verification pill). Flowsheet as
inline SVG. Tables: instances (`id`, `model`, `semantic_role`, parameters on expand), connections (`id`, from
`instance.port` → to `instance.port`, `state_definition`), specifications (as written). **Solve** button
(disabled without `execute`): a dialog with the policies of `get_project.solve_policies` (default
`default_policy_id`); the idempotency key `ui-solve-<32 lowercase hex from crypto.getRandomValues>` is drawn when
the dialog opens and reused on retry; body exactly
`{"operation":"solve","idempotency_key":K,"body":{"revision_id":R,"policy_id":P}}`; then navigate to the job.

**Layout (`model/layout.js`).** Nodes = instances; edges = connections `from.instance → to.instance`.
(1) Back edges: DFS from sources (no incoming edges) in instance order, outgoing edges in connection order; an
edge to a node on the DFS stack is a back edge (recycle). (2) Layer = longest path from sources over forward
edges. (3) Within a layer: initial order = instance order, then one barycentre pass left→right on predecessor
positions, ties by instance order. (4) x = 160·layer, y = 90·index; boxes 120×44 with the instance id and model
id; forward edges as elbows, back edges as arcs below the diagram labelled by connection id. NET-02 must give
layers FEED 0, MIX 1, HEAT 2, PHF 3, SINK-V 4, SPLIT 4, SINK-P 5, and back edge S6.

### 6.2 Validation and degrees of freedom
Ordered checks (id, stage, PASS/FAIL/NOT_RUN pill, message, `implicated_objects` linked to instances and
specifications). Structural counts. From the routed `structural_report` — or, unroutable, the
`validation_structural_report` with the `not_run_reason` and `hint` above it: `excess`, `deficit`, certified
redundant rows (`certificates`, each row linked), candidate specifications and candidate rows (linked to the
equation view), the `unit_degrees_of_freedom` table (instance, columns, model rank, DOF, specifications,
over-specified pill, local excess), BTF summary (`block_count`, sizes, `largest_block_fraction`), tear, and
`unsupported` entries. No arithmetic beyond display (Q1).

### 6.3 Run and trace
Summary: job id, `run_id`, revision link, policy, `solve_path`, outcome and verification pills, created/started/
ended times, `elapsed_seconds` (run manifest). Attempts (§5.6 rule 1): attempt, phase signature, outcome,
iterations, counter deltas; recovery path from certificate `branch_provenance` when a certificate exists
(`opening_source`, `initializer_source`, `cause`, `decision`). Trace table: `sequence, kind, attempt, iteration,
residual_inf_unscaled, merit, alpha, step_inf_scaled, trial_status, rejection_reason, linear.residual_normalized,
outcome, state_sha256[:12]` (absent members `—`), filters by kind and attempt, 500 rows per client page.
Execution-plan summary (`plan_id`, `policy_id`, steps). Bundle files (name, kind, size, sha256, digest status,
JSON view, download through `fetch` → Blob → object URL). Live: job events and progress. **Cancel** for
non-terminal jobs (disabled without `execute`).

### 6.4 Certificate and failure bundle
Certificate: status pill; checks grouped by category then result with counts; each check row: id, subject
(linked to the equation view when it is a row), value, tolerance, reference, scaled (residual only), result
pill, near-threshold pill; limitations; regularity (key members); `solution_error_bound_scaled` with the
certificate's own `statements` as the explanation (no tolerance is invented for it); `branch_provenance`;
`phase_branch` (rule 3); `transformations`; static explanatory text: "near-threshold means tol/10 < |v| ≤ 10·tol
(ADR 0007 D2.4)" — the flag itself is read from each check, never computed.
Failure bundle: outcome pill and taxonomy; observations vs inferred causes (each cause shows its `kind`, e.g.
"hypothesis"); implicated sources (linked); attempt tree; replay identity (all four members); best checkpoint
(`state_sha256`, `verification_scope`, label); check report; suggested actions (action, preconditions,
`requires_permission`). Every empty section reads "none recorded".

### 6.5 Equation view (Q2)
For row R (from `inspect_structure` of the revision; at a run, the run's revision): `row_id`, instance, unit,
role, `specification_id` (linked), residual kind and SI unit; incidence: each column with kind, SI unit, owner
instance, connection/coordinate/component, and — at a run — its value from `solution-state.json`; the column
matched to R (`canonical_matching` inverse) highlighted; R's BTF block (index, size, `depends_on`); redundancy
certificates containing R; whether R is a candidate specification row; the owning unit's DOF row; at a run, the
certificate check whose `subject` is R (value with unit, reference, scaled, tolerance, result, near-threshold).
No symbolic text.
**Consistency guard:** at a run with a `solution-state.json`, the equation index is used only if `inspect_structure`'s
`structural_report.model_version` equals the bundle's `structural-report.json` `model_version`; otherwise the
equation links are disabled with the notice "this run used a different equation structure than the server's
current analysis of its revision".
From any value in the streams, units, certificate or trace screens, a "rows" link opens the rows incident on
that column with the matched row first.

### 6.6 Streams and units
Stream table: one row per graph connection (the `connection` of the column index), columns per component
`n` (mol/s from `si_unit`), `T`, `P`, ordered by the revision's connections; a connection id the revision does
not contain is shown under the binder's id with a note. Columns with null coordinate are listed per owner
instance in the unit panels, never dropped. Unit panels from the `list_models` signature of each instance's
model: ports, pins, `required`, `zero`; a quantity the model does not have reads "not applicable", never blank.
Phase splits (`phase_branch`, rule 3). Every value links to its rows (§6.5). A bundle without `solution-state.json` (a failed run) shows "no solution state recorded for this run" and the failure bundle's best-checkpoint identity instead of values.

### 6.7 Revision comparison and the scenario view
**Revision comparison:** pick two revisions (default: a revision and its parent). Show the contract's coarse
`added/removed/changed` and its `elements`; for each changed element, the before/after values of each `paths`
entry read from the two revision documents by id and path tokens (no comparison computed). Coarse `changed`
members with no element entries read "order changed only".
**Scenario view (definition, R-174):** a scenario in v0.2 is one revision solved under one policy; the scenario
view compares two finished solves (any revisions, any policies): outcome, verification, `solve_path`, policy,
`structural_sha256` (equal or not), `model_version` (equal: "same equation structure"; else "different
structure — variables compared by id only"), elapsed seconds, final counters, certificate summary (status,
check count, limitations), and the state table: union of variable ids, a, b, Δ, relative difference (rule 4),
sorted by relative difference descending. Banner: "Differences are displayed, not judged: no registered
comparison or allowance is applied." No AGREE/MATCH vocabulary on this screen.

### 6.8 Agent history
Principal selector (own principal by default; "all principals" and others need `policy`, greyed otherwise).
Table (descending): time, principal, capability, operation, outcome pill (+ code), effect (linked: `revision:` →
revision, `job:` and `cancel:` → job, other kinds as text), idempotency key. Commit row detail: expected
revision (= parent, §5.6 rule 6), the element diff from the parent, and the revision's validation labelled
"validated now by server <package_version>" (the ledger's commit-time report is not exposed; §12). Job row
detail: request (revision, policy, key), status, outcome and verification. Refusal rows show the code. The
screen never claims to show what an agent *said*; it shows what the project recorded.

---

## 7. Security model (local-first)

- **Exposed by default:** nothing new; `--ui` is off. With `--ui`: on `127.0.0.1:8765` (loopback default,
  unchanged) the static files are public to local processes; they contain no project data. Every data request
  needs a bearer token; no CORS headers (a cross-origin script cannot read responses, and preflighted requests
  are refused as before).
- **No ambient authority.** The token is never a cookie, so CSRF and DNS rebinding gain nothing: a rebinding
  page is same-origin but has no token. Hence no Host-header check (it would add a non-`ApiError` response
  shape for no gain).
- **XSS.** Untrusted text (revision ids, titles, descriptions, messages that echo them, case text) reaches the
  DOM only as text nodes, after `sanitize`. The CSP forbids inline script and style and any foreign origin; so a
  sink that slipped in still could not run injected script or exfiltrate the token.
- **Token handling.** Login form (`type=password`, `autocomplete=off`); stored under
  `openflowsheet.token` in `sessionStorage`, also in `localStorage` only if "remember on this browser" is ticked;
  "Sign out" clears both. Never logged to the console, never placed in a URL the app builds (accepted once from
  the boot fragment, then stripped).
- **`--allow-remote`:** unchanged warning (no TLS); additionally the page is an insecure context, so digests show
  "unchecked".

---

## 8. Testing strategy (what W26's evidence is)

**Layer A — Python (pytest, in `check.sh`).**
1. Contract tests over HTTP (`starlette.testclient`/httpx `ASGITransport`, as `tests/test_t07_w6a_http.py`) of
   each of the 17 operations on the fixture project, every response validated against its response schema.
2. Amendment tests (WO-1…WO-3, §10).
3. Static scans of `apps/web/` (`tests/test_m06_static_scan.py`): `fetch(` occurs exactly once, in
   `js/api.js`; zero occurrences of `XMLHttpRequest, WebSocket, EventSource, sendBeacon, innerHTML, outerHTML,
   insertAdjacentHTML, document.write, eval(, new Function, import(` and of `http://`/`https://` except the SVG namespace name (in `js/h.js` and `favicon.svg` only); `js/model/*.js`
   reference none of `document, window, fetch, localStorage, sessionStorage`; `index.html` has no inline
   `<script>` body or `style=`; the UI call set (every `call("…"`, `readWhole("…"`, `raw(` in `js/`) equals the
   17-name list; every name is a key of `ROUTES`; `m06_web_routes.py --check` passes; the JS
   `FORBIDDEN_RANGES` block equals Python's; no `OPERATIONS` path starts with `/ui`.
4. Serving tests: headers on `/ui/` and `/ui/js/main.js` (exact CSP string), content types, `/` → 307
   `/ui/`, API responses byte-identical with and without `--ui`, start refused without package data.
5. Fixture validity (`tests/test_m06_fixtures_valid.py`): every captured response validates against its
   operation's response schema and every captured bundle member against its record schema — so fixtures cannot
   silently drift from the contract.
6. Browser smoke (`tests/test_m06_browser_smoke.py`, marker `browser`): builds the fixture project in a tmp
   directory, serves `create_web_app` with uvicorn on a free loopback port in a thread, wrapped (in the test
   only) by an ASGI recorder of `(method, raw_path, query)`; for each route of §6 runs
   `<browser> --headless=new --disable-gpu --user-data-dir=<tmp> --virtual-time-budget=20000 --dump-dom
   "http://127.0.0.1:<port>/ui/#<route>?token=<token>"` with `supervisor-c`'s token (the fragment never reaches the server); asserts `data-ofs-ready="1"` on `<html>`, no
   `#ofs-fatal`, the route's marker texts, and on the recorder: every path is `/ui/…` or an `OPERATIONS` route,
   and `prt_` occurs in no path or query. Browser binary: `OPENFLOWSHEET_BROWSER`, else the first of
   `chromium, chromium-browser, google-chrome` on `PATH`; skipped with a visible reason when none is found,
   **failed** when `OPENFLOWSHEET_REQUIRE_BROWSER=1`. The app sets `data-ofs-ready` to `"0"` at navigation start
   and `"1"` when the screen's `load` resolved and mounted; `window` `error`/`unhandledrejection` render
   `<pre id="ofs-fatal">` and set `data-ofs-error="1"`.

**Layer B — Node built-in runner (`node --test "tests/web/*.test.mjs"` — a quoted glob, which Node ≥ 22 expands; a bare directory argument does not work), no npm.** `tests/web/*.test.mjs` import
`apps/web/js/{h,text,api,model/*,screens/*}.js` directly. `api.js` is tested with an injected fake transport
(the module exports `httpTransport(url, init)`, whose body is the one `fetch(` call, and `createApi(transport = httpTransport, tokenStore)`; tests pass a fake transport). View tests call
`view(data)` on fixtures from `tests/web/fixtures/` and assert on the plain tree (text present, pills carry glyph
and word, link targets, numbers in short and full mode). Node ≥ 22, which loads `.js` files with ES-module syntax without a `package.json` (module syntax detection); CI pins 22, the reference host has 24. No `package.json` is added.
`check.sh` gains a step: run `node --test "tests/web/*.test.mjs"` if `node` is on `PATH`; if `OPENFLOWSHEET_SKIP_WEB_TESTS=1`
print `SKIPPED (explicit)`; if `node` is missing or older than 22 and no skip is set, **fail** with "install Node ≥ 22 (a
test-time tool only) or set OPENFLOWSHEET_SKIP_WEB_TESTS=1". CI never sets the skip.

**Layer C — CI.** `check` job (both architectures): `actions/setup-node` pinned by commit SHA (as the other
actions, `67029fa`), `node-version: 22`; x86-64 leg also sets `OPENFLOWSHEET_REQUIRE_BROWSER=1` (Chrome is on
the GitHub Ubuntu image; `OPENFLOWSHEET_BROWSER=$(command -v google-chrome || command -v chromium)`). `dist`
job: the wheel holds every `apps/web` file (T08.A43 extended) and a clean install answers `GET /ui/` 200 under
`serve-http --ui`.

**Fixtures (`scripts/m06_web_fixtures.py --write`).** A directory project built through the contract with the
inline executor: grants `agent-a` (read, draft, execute), `viewer-b` (read), `supervisor-c` (read, policy). As
`agent-a`: commit `SYN-001-T06-NET02` (rev-000001) and solve with `default` (job-000001); commit the same with
`instances[U-SPLIT].parameters.split_fraction.value` 0.95 → 0.90 (rev-000002), solve (job-000002); commit
`SYN-001-conflicting-heater-spec` (rev-000003, INVALID); commit `SYN-001-A02-352-vapor-guess-410` (rev-000004),
solve (job-000003, HOMOTOPY_STALLED); commit NET-02 with title `<img src=x onerror=alert(1)>` + U+202E +
`evil` and the same description treatment (rev-000005). As `viewer-b`: `submit_job` (refused, `forbidden`) and
`list_audit` with no principal (refused, `forbidden`). Then capture, through `dispatch` as the right caller,
every response the routes of §6 request, and the raw bytes of every bundle member they read. Committed once
(regression fixtures, not validation); `build_fixture_project(path)` is importable for the smoke test.
Timestamps are not normalised; tests never assert on them.

---

## 9. W27 — the external agent benchmark (OpenIDAES-450 / CRAFTS)

**Inputs.** Audit `study/openidaes450:docs/openidaes450-audit.md`: repository
`Galigeigei-Z/CRAFTS-Multi-agent-for-Equation-oriented-PSE` at `13ca57e`; archive `OpenIDAES-450-demo.tar.gz`,
220 433 394 bytes, release `openidaes450-demo-2026-09-26`; MIT; data-use permission from the first author to
Frank (2026-09-26) including subsets and publishing comparisons; attribution: cite arXiv:2608.01369 and
acknowledge IDAES and upstream projects (`demo/openidaes450/THIRD_PARTY_NOTICES.md`). 450 cases; own residual
check 425 pass / 24 fail / 1 absent; `splits/full82.json` 82 cases (WaterTAP 41, IDAES 20, PrOMMiS 20,
DISPATCHES 1), whose binding to the manuscript's score run is "not independently verified".
**Archive size.** The pinned archive is the live release asset, 220 802 919 bytes, SHA-256 `6d42c02f…4526`;
the audit's 220 433 394 was an earlier upload (the asset was re-created after the audited commit), disclosed in
`provenance.json` (`size_disclosure`). The audit recorded no hash; "same data" rests on the counts reproducing.
**Governing rules.** Blueprint §11.4: adapted subsets report coverage and never inherit the original headline
score; report completion, false verification, unauthorized actions, semantic error rate and cost separately.

**Tier 0 — no spend (M06 exit).**
1. *Provenance* `benchmarks/m06/openidaes450/provenance.json`: paper id, repository URL, full commit SHA of
   `13ca57e`, release tag, archive URL, SHA-256 and size, licence text hash, permission record (date, holder,
   quoted sentence; the e-mail stays with Frank), attribution text, acquisition time. The archive is not
   committed (git-ignored under `evidence/M06/**/artifacts/`), referenced by hash.
2. *Artifact-access report* `access_report.json` (450 rows: case id, family, model type, files present and
   missing among the per-case set the audit lists, parse errors, residual-check flag, in-full82) and a list of
   **inaccessible assets**: anything the CRAFTS paper's agent results depend on that is not in the release (the
   fine-tuned agent models, their prompts and scoring harness, the score-run binding of the 82-split) — each
   checked and recorded as present/absent with where it was looked for.
3. *Coverage classification* `coverage.json` against the OpenFlowsheet version and model registry at the time
   (`list_models` document SHA-256 recorded): each case gets a class by precedence
   `ARTIFACT_INCOMPLETE` > `NOT_STEADY_STATE_SIMULATION` (dynamic, grid/design optimisation, dispatch) >
   `UNIT_UNAVAILABLE(<class>)` > `COMPONENT_UNAVAILABLE(<name>)` > `PROPERTY_ROUTE_UNAVAILABLE(<model>)` >
   `CANDIDATE`, with every applicable reason recorded. Summary tables against the 450 and the 82. The maps
   (IDAES unit class → OpenFlowsheet model, component availability, property-route availability) are semantic
   judgements and are authored by the design lane (WO-15), not by the classifier's implementer.
4. *Report* `docs/m06-w27-coverage.md`, generated. Tier 0 is re-run at M07 against the v0.2 candidate.

**Tier 1 — the registered campaign (Frank's spend decision, F1).** Registration by the `specifier` before any
run (WO-15): stratified sample of 45 distinct cases, all `CANDIDATE` cases first (expected few at v0.2), the rest
proportional to family with at least one per family of ≥ 4 cases (largest remainder), seeded; k = 1. Agent
configuration as V17 `v17-c2` (effort high, `--max-turns 60`, 1800 s wall, USD 5 guard,
MCP tools only, operator isolation, pinned Claude Code version) except the model: by Frank's answer to F2
(2026-10-06) the most recent model at campaign time, pinned by exact ID and recorded, not `v17-c2`'s
`claude-sonnet-5`; direct comparability with `v17-c2` is lost and stated. Prompt
template: the case's description, specification, topology, unit and property configuration, enveloped as
untrusted data, with the instruction to build it through the tools or report a typed limitation, and a
structured final answer `{status: built|limitation, revision_id, job_id, limitation, claims}`. Harness: the V17
harness (`benchmarks/t07/v17/harness.py`) reused through a W27 module, with V17's open finding fixed (each
`run.json` records the lock hash and the interpreter environment). Scoring per run:
`CORRECT_BUILD | CORRECT_LIMITATION | WRONG_LIMITATION | WRONG_BUILD | AGENT_FALSE_VERIFICATION |
SYSTEM_FALSE_VERIFICATION | INFRASTRUCTURE_FAILURE`; agent false verification = a built/solved/verified claim for
a non-`CANDIDATE` case, or for a job without a VERIFIED certificate, or (CANDIDATE cases) stream values outside
the registered tolerance of `streams.csv`; unauthorized effects from `list_audit` and the store export. Reported:
counts, coverage against 450 and 82, one-sided 95 % Clopper–Pearson bounds for zero terms (0/45 → 6.4 %), cost.
**System false verification must be 0** (a non-zero count is a defect report); the agent terms are reported,
not gated, unless the registration says otherwise.

**Cost estimate** (basis: V17 `v17-c2` USD 9.65 / 30 runs = 0.32 per run, `v17-c1` 15.64 / 29 = 0.54, 80 s
mean wall; OpenIDAES prompts are longer and the registry larger, so 1–2× per run; subscription list-price
estimates, not billed figures):

| Option | Runs | USD (estimate) | Wall (sequential) |
| --- | --- | --- | --- |
| Tier 0 only | 0 | 0 | ~1 h compute |
| Canaries | 3 | 1–3 | ~10 min |
| **Tier 1 default** | 45 | 15–45 | 1.5–3 h |
| Tier 1 cheap | 15 | 5–15 | 0.5–1 h |
| Full | 450 | 150–450 | 15–30 h |

**When.** Tier 0 now (expect almost every case non-`CANDIDATE` at 0.1.x: SYN-001 components only); re-run and
campaign at M07 on the v0.2 candidate, so coverage reflects v0.2's domain. M06 does not wait for M01.
**Claims allowed:** "adaptation attempted; k of 450 (j of 82) cases are representable candidates for
OpenFlowsheet <version>; the rest are classified with reasons; inaccessible assets: …; campaign results with
their bounds." **Not claimed:** any headline score, any comparison with CRAFTS' success rates, numerical
agreement with IDAES outputs.

---

## 10. Work orders (dependency order)

Lane: all build lane unless marked. "Bounded" = suitable for `sonnet-implementer` from this note, with an
`opus-engineer` review before merge; "Opus" = `opus-engineer`. Each WO is one or a few commits naming M06.

**WO-1 (Opus) — `inspect_structure` row/column index and unroutable analysis (Asks 1, 2).**
Files: new `application/structure_index.py` (pure: declaration, graph, binding, revision → `rows`, `columns`);
`application/revision_run.py` (`route_analysis` split into trace + analyse, `route_structure`);
`application/validation.py` (`_analysed` exposes its declaration and graph); revision binder attribution if
needed (§4.1). Tests `tests/test_m06_wo1_structure_index.py`. Acceptance: G3, G4; T07 fixtures that pin
`inspect_structure` documents move **by addition only** (test: dropping the new members restores the old
document byte for byte), each named in the commit message.

**WO-2 (Bounded) — `diff_revisions` elements (Ask 6).** `application/transactions.py` (`element_diff`),
`SemanticDiff` gains `elements` emitted only by `diff_revisions`, `application-results.schema.json`,
`scripts/t07_schema_fixtures.py` (valid fixture from a real response, invalid one without `elements`), R4-G3
snapshot re-taken for `diff_revisions` only (with `elements` removed it equals the old snapshot). Acceptance: G5.

**WO-3 (Opus) — `list_audit` (Ask 4).** `application/contract.py` (Inspection), `types.py` (`AuditRecord`),
`operations.py` (row), `authz.py` (`OPERATION_RIGHTS`, the `target_principal` rule), `store.py` (query),
`local.py` (method), schema `$defs` `audit_record`, `audit_page`, `docs/interfaces-frozen.md` §1–2, conformance
scenario (`tests/test_t07_conformance.py`: Python, CLI, HTTP; MCP excluded by transport). First test: the
key-in-hash precondition. Acceptance: G6.

**WO-4 (Bounded) — serving.** `apps/web/index.html` (shell, no inline code), `favicon.svg`, the `_data/web`
symlink, package data, `resources.PACKAGED`, `bindings/web.py`, `serve-http --ui`, import-rule test extended to
`web.py`. Tests `tests/test_m06_wo4_serving.py`. Acceptance: G8 (headers), G10.

**WO-5 (Bounded) — JS foundation and test wiring.** `scripts/m06_web_routes.py` → `js/routes.js`; `js/h.js`,
`js/text.js`, `css/tokens.css` (README tokens, selected-row rule), `css/app.css` skeleton; `tests/web/` with
tests for `h`, `sanitize`, `fmt`, pills; `check.sh` Node step; CI `setup-node`; `tests/test_m06_static_scan.py`;
contrast test (WCAG relative luminance from `tokens.css`; pairs of §5.5). Acceptance: G1 (static), G9.

**WO-6 (Opus) — `api.js`, router, auth, shell frame.** `createApi`, `call`, `raw` with digest, `readWhole`
(§5.4, including the literal-marker guard, nested-array refetch, array paging, sha256 consistency, 500-request
budget), long-poll, cache; `router.js`, `auth.js`, `main.js` (readiness and fatal markers), header (project,
principal, rights, server version), theme toggle, error panel. Node tests with a fake transport for every
expander branch. Acceptance: G7 (api rows).

**WO-7 (Bounded; after WO-1…3) — fixtures.** `scripts/m06_web_fixtures.py` per §8, `tests/web/fixtures/`,
`tests/test_m06_fixtures_valid.py`, a fixtures README listing each file and the numbers of G7 as measured.

**WO-8 (Opus) — view models.** `js/model/attempts.js, trace.js, streams.js, structure.js, certificate.js,
compare.js, history.js, layout.js` with Node tests on fixtures. Acceptance: G7 numeric rows.

**WO-9 (Bounded) — screens A.** Project, revision overview (with layout SVG and Solve), validation/DOF,
certificate, failure bundle, streams and units — `view` + `load`, Node view tests. Acceptance: G7 view rows.

**WO-10 (Bounded) — screens B.** Run and trace (live job, Cancel), equation view, revision comparison, scenario
view, agent history, bundle-file JSON view. Acceptance: G5, G6, G7 view rows.

**WO-11 (Opus) — security and browser gates.** XSS fixture assertions, browser smoke with request recorder,
CI browser wiring, final static-scan list. Acceptance: G1 (dynamic), G8, G11.

**WO-12 (Bounded) — documentation.** `docs/web-shell.md` (start, grant a token, `--ui`, screens, what each
screen does not claim), README section, CHANGELOG, `docs/support-matrix.md` rows.

**WO-13 (session + design lane) — W26 evidence and review.** `evidence/M06/<commit>/manifest.json` with one check
per W26 row (G1–G12); `reviewer` pass against this note; on its outcome ADR 0030 and ADR 0019 Amendment 3
move to Accepted.

**WO-14 (Bounded) — W27 acquisition, provenance, access report.** `scripts/m06_w27_acquire.py`
(download, verify size/SHA-256, extract to the ignored artifacts directory), `provenance.json`,
`access_report.json`, inaccessible-asset list. Acceptance: G13.

**WO-15 (design lane: `specifier`) — W27 registration.** `docs/derivations/M06-W27-registration.md`: the three
maps, class precedence, the sample (seed, strata), prompt template and footer, final-answer schema, scoring
rules and tolerances, claims and non-claims, pre-registered before any run.

**WO-16 (Opus) — W27 classifier, coverage, harness, scorer.** `benchmarks/m06/openidaes450/` (classify,
coverage, report generator), W27 harness module over the V17 harness (lock-hash fix), scorer, preflight; a dry
run with a stub session (no model call). Acceptance: G14, G15.

**WO-17 (session; Frank's spend) — canaries, campaign, verdict.** 3 canaries, then the registered campaign;
`verdict` agent judges W27. Acceptance: G16.

Parallelism: WO-1…3 and WO-4…6 are independent; WO-7 needs WO-1…3; WO-8…11 need WO-7; W27's WO-14 can start now,
WO-15 in parallel, WO-16 after both, WO-17 after Frank.

---

## 11. Verification gates

| Gate | Invariant | Measured how | Pass |
| --- | --- | --- | --- |
| **G1** contract only | the browser touches only static files and `OPERATIONS` routes | static scan (§8 A3) + smoke recorder (§8 A6) | `fetch(` count = 1; forbidden-token counts = 0; UI call set = the 17 names; recorder: 100 % of requests static or `OPERATIONS`-matched, 0 occurrences of `prt_` in paths or queries |
| **G2** contract tests | every UI-used operation answers schema-valid over HTTP | §8 A1 on the fixture project | 17/17 operations, 0 schema failures |
| **G3** identity | nothing hashed moves | for all 50 T07-corpus revisions: canonical SHA-256 of `route_analysis(route).as_document()` and of `validate(doc,"simulation")` equal snapshots taken at `67029fa`; `scripts/t07_identity.py` check; CI `identity` job | 50/50 and 50/50 equal; identity script and CI job pass unchanged |
| **G4** index | rows/columns describe the declaration | NET-02 (`SYN-001-T06-NET02`) and the corpus | NET-02: 48 rows, 47 columns; Σ len(row.columns) = `structural_report.nnz`; every row's columns ⊆ column ids; row `U-HEAT:HEAT-duty` has `instance_id` `U-HEAT` and is the `canonical_matching` row of `U-HEAT.Q`; every row listed in any `unit_degrees_of_freedom[].specification_rows` has role `specification`; every nTP-v1 connection has N_c + 2 columns with coordinates; corpus: positional coordinates agree with binder naming on 50/50. STR-03: unroutable branch with non-null `validation_structural_report` whose `excess` = 1 and whose `candidate_specifications` equal the 9 ids of the STR-03 message, in order |
| **G5** diff elements | element detail is exact and additive | fixture pair rev-000001 → rev-000002 | coarse `changed` = `["instances"]`, `elements` = `[{"member":"instances","id":"U-SPLIT","change":"changed","paths":[["parameters","split_fraction","value"]]}]`; `added/removed/changed` of every corpus pair equal to the pre-amendment function's output |
| **G6** audit | history is complete and authorized | WO-3 tests + fixture | own rows with `read`: allowed; others/all without `policy`: `forbidden` and audited; with `policy`: allowed; 100 % of allowed `commit_change` and `submit_job` rows carry their key; limit-1 walk reproduces the full sequence; descending = reverse of ascending; mismatched-order cursor → `invalid_request` |
| **G7** views on real data | the screens show the records exactly | Node tests on fixtures | NET-02 run: 27 trace events; 2 attempts; attempt 0 BOUND_BLOCKED with deltas property 54, residual 2, jacobian 2, factorizations 2; attempt 1 CONVERGED 135/7/4/4; totals 338/9/6/6; certificate VERIFIED, 144 checks, 3 near-threshold limitations; `U-HEAT.Q` shows `31487.6` short and `31487.641739605908` full; A02-352: HOMOTOPY_STALLED, replay identity `policy_id` `T04-W12` (non-empty, D2 regression), `property_calls` 2104 (D3 regression), inferred cause labelled "hypothesis"; NET-02 layout layers as §6.1; every status pill node contains glyph and word |
| **G8** security | no script injection; strict headers | serving tests + smoke | exact CSP string on every `/ui` response; rev-000005's title renders as text with U+FFFD for U+202E, no `<img` in the dumped DOM, no fatal marker |
| **G9** contrast/theme | legibility in both themes | contrast test over `tokens.css` | every used fg/bg pair ≥ 4.5:1 in light and dark; (`ink-3`, `select`) never used (selected-row override present) |
| **G10** packaging | the wheel serves the shell | `t08_dist` extension; `dist` job | every `apps/web` file in wheel and sdist with equal bytes; clean install `serve-http --ui` → `GET /ui/` 200, `/ui/js/main.js` `text/javascript` |
| **G11** smoke | every screen renders in a real browser | §8 A6 | all §6 routes: ready marker 1, no fatal, marker texts present |
| **G12** gate | the repository gate | `./scripts/check.sh`, CI | green, both architectures; Node step ran (not skipped) in CI |
| **G13** W27 provenance/access | exact provenance; disclosure | WO-14 script `--check` | archive size and SHA-256 match `provenance.json` (220 802 919 bytes; the audit's 220 433 394 was an earlier upload, disclosed there); 450 rows; residual-check split 425/24/1 and full82 = 82 (41/20/20/1) reproduce the audit; every inaccessible asset listed with where it was sought |
| **G14** W27 coverage | every case classified | WO-16 | 450/450 rows with a class; every non-`CANDIDATE` row has ≥ 1 reason; summaries against 450 and 82 sum correctly; `list_models` SHA-256 and the registry-snapshot SHA-256 (components and property routes, which `list_models` does not name; WO-15 F2) recorded |
| **G15** W27 harness | ready to run, nothing spent | dry run with a stub session | preflight passes; `run.json` carries commit, tree-clean, lock hash, interpreter environment, model id, Claude Code version; scorer classifies the stub runs as registered |
| **G16** W27 campaign (if approved) | attempted, honest | `verdict` on the campaign record | all registered runs recorded (infrastructure failures counted); system false verification 0; unauthorized effects 0; agent terms and cost reported with bounds |

M06 reaches `tested` on G1–G15; G16 is W27 evidence for M07's gate when Frank approves the spend.

---

## 12. Risks and open questions

Each item says whether it needs a **fact** or **Frank's preference**, and the default that applies until answered.

| # | Item | Kind | Default |
| --- | --- | --- | --- |
| F1 | W27 spend: none, 15, 45 or 450 agent runs | preference (money) | 45-run Tier 1 at M07 on the v0.2 candidate, est. USD 15–45; nothing is run before Frank says so |
| F2 | W27 agent model/configuration | preference | V17 `v17-c2` configuration, for comparability |
| F3 | Fonts: system stacks vs vendored IBM Plex | preference (taste/licence) | system stacks; vendoring Plex needs a NOTICE change and an ADR 0006 amendment (OFL-1.1, reserved font name "Plex", files unmodified) |
| F4 | "Scenario view" = run comparison | preference (scope) | as §6.7; revisit when the IR gains a scenario object |
| F5 | Education mode | preference (scope) | deferred beyond M06 |
| R1 | `--dump-dom` with `--virtual-time-budget` may be flaky for fetch-driven pages | fact (partly measured: on the reference host, Chromium `--headless=new --virtual-time-budget=20000 --dump-dom` rendered a module-script page that made two sequential `fetch` calls around a 300 ms timer and set `data-ofs-ready="1"`; Node 24 and Node 20.19 ran a typeless-ESM test, but only Node ≥ 22 expands the test glob) | use it; if the smoke test fails spuriously in 2 of 10 consecutive CI runs, switch to Playwright as a CI-only, pinned dependency (build-lane decision, logged) |
| R2 | The audit/ledger join relies on the key being inside the hashed request | fact | WO-3's first test; if false, stop and escalate (an explicit ledger column would be a store-schema migration) |
| R3 | The revision binder may lack a specification attribution for its rows | fact | add it where the rows are built, used only by the index (§4.1); escalate if it would touch the declaration |
| R4 | M01 edits binders and route selection concurrently | fact (merge) | WO-1 keeps its diff to `route_structure`, `_analysed` and the new module; re-run G3/G4 after rebasing on M01 |
| R5 | The OpenIDAES archive may have moved or changed | fact | verify size and SHA-256; on mismatch record it and use the audited commit's tree |
| R6 | Schema `$id` move (R-149) "with M01's or M06's first schema change" | fact (sequencing) | not bundled into M06; a separate session-owned commit before whichever of M01/M06 merges first; M06's schema edits rebase onto it |
| R7 | Agent history shows validation recomputed now, not the commit-time report the agent received (the ledger holds it, unexposed) | accepted limitation | labelled in the UI; exposing ledger results is a later ask |
| R8 | JS has no linter or type checker (no npm) | accepted | syntax and imports are exercised by Node importing every module; style rule: ES2022 modules, `const`/`let`, named exports only, 2-space indent |
| R9 | Large traces or documents | fact (scale) | client paging of 500 trace rows; expander budget 500 requests; raw export for records; revisit with M01/M02 bundle sizes |

---

## 13. What M06 does not establish

- No usability, workflow or accessibility study with users; accessibility is limited to the stated checks
  (glyph+word status, keyboard-reachable controls by construction, contrast); no screen-reader audit.
- No security assessment beyond the local, single-user threat model of §7; no TLS; no multi-user hosting.
- The agent history shows what the project recorded, not what an agent claimed; it does not judge agents.
- The scenario view displays differences; it is not a registered comparison and makes no agreement claim (Q4).
- W27 produces coverage, access and (if approved) campaign evidence; no OpenIDAES-450 headline score, no
  comparison with CRAFTS' reported results, no numerical agreement with IDAES, no empirical validation.
- `blocked_by` (Ask 3), operation rights in `get_project` (Ask 5), per-event timing (Q3) and run-level
  reference comparison (Q4) are not provided.
