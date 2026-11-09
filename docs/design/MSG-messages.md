# MSG — Messages a student understands: one explanation model over a code catalogue

**Package:** MSG (roadmap 0.4, wave 1; ADR 0056 Amendment 1; ADR 0057 rule C3). **Lane:** design (`architect`),
2026-11-05. **Brief:** `docs/briefs/MSG-architect.md`; code map `docs/briefs/MSG-recon-digest.md`.
**Carries:** FB-05, with FB-01 and FB-03 (`docs/USER_FEEDBACK.md`; verbatim in the digest §9).
**Draft ADR:** `docs/adr/0058-messages-and-code-catalogue.md` (*Proposed*). It is needed because `RunResult` gains a
member, `Inspection` gains a method and a schema joins the list (§3.3, §3.4, §3.5). No `ApiError` code and no `ApiError`
member is added.
**Implemented by:** `opus-engineer` from §6's work orders. A `sonnet-implementer` may take the parts §6 marks *(S)*.

---

## 1. Problem and scope

Every surface (Python API, CLI, HTTP, MCP, web shell) must give a failure, refusal, warning or notice in the same
layered form. The form is: a human first line saying **what** and **where** (in the user's element ids), then **why**
(with the numbers that triggered it), then **what to do**, then the failure **kind**, then the stable typed **code**,
and last the machine **details**. Each code has a docs section and an `explain` operation. A corpus of beginner
mistakes is tested in CI. The design also fixes FB-01 (a re-run `create`) and FB-03 (the failure reason is missing
from `RunResult`, and `not_found` says nothing useful).

**In scope (0.4).**
- The catalogue: its data format, its schema, its loader, the extension slot F1 registers into, and a CI rule that
  fails on an emitted code without an entry.
- The legacy-message parser, the renderer and the text formatter.
- `detail.explanation` on every projected `ApiError`.
- `RunResult.failure`, `RunResult.raise_for_outcome()` and the Python-only `SolveFailedError`.
- A useful `not_found` for a missing bundle member.
- The `explain` operation on all four transports, and the CLI `explain` command.
- Generated docs sections, one per code.
- The diagnostic sidecar, which carries the numbers of five thermal-kernel refusals.
- FB-01: `create(..., exist_ok=True)` and coded store refusals.
- The beginner-mistake corpus (12 cases).
- CLI rendering and exit codes, and the web shell's display of the summary and action.

**Out of scope.**
- X04's unit conversion. Numbers are shown in SI, and §4.5 leaves the display slot open.
- ST's stream table and F1's registry design. MSG gives F1 a catalogue to register into (§4.11) and nothing more.
- Translations, and the web shell's visual design.
- A `notices` member on `RunResult`. Certificate-status meanings are reached through the CLI and `explain` (§8 Q5).
- Rewriting the machine message of any producer. It is forbidden here; see §2.
- Complete prose for every code. 0.4 writes complete entries for about 75 codes (§4.2.6), and every other emitted
  code gets a *stub* entry. The catalogue grows after 0.4.

---

## 2. Constraints and invariants

**I1. The machine layer does not move.** Every existing code, every machine `message` string and every existing
`detail` member keeps its exact value at its producer:
- `ApiError.message`;
- `code(detail)` refusal strings;
- solve-event `message`;
- the failure bundle's `observations.message`, `suggested_actions` and `inferred_causes`;
- the certificate's `branch_provenance[].cause`;
- validation check messages;
- `Unbound.detail` and `Unbound.hint`.

The constraint has three sources:
- ADR 0025 D6 compares artifact `message`/`cause` by template.
- The `t07` identity key holds validation check messages and the G10 refusal codes (`scripts/t07_identity.py:24-25`,
  `:283`).
- R-159's tests match the code prefix.

New machine data is **additive only**: new `detail` members (open object) and the new `RunResult.failure` member.

**I2. Rendered text is computed on read and stored nowhere.** Rendered text does not go into an artifact, a bundle
member, a solve event, a job event, the job store, the ledger or the audit log. No identity, hash, cache key or
fingerprint takes it as input. It is a pure function of (catalogue, code chain, params, render context).

**I3. Replay identity.** No bundle gains or loses a member. `run/replay.py:263-265` reports an artifact that only the
rerun has as a difference, so a new member would make every released 0.3.0 bundle `MISMATCH`. No byte of any member
changes. These stay bit-identical:
- revision content hashes;
- `structural_sha256` and `r0_sha256`;
- certificates and `certificate_id`;
- the K05/`t07` identity document;
- property-cache keys.

The proof is gate MSG-G0 (§7) until F0 exists, and F0 after that.

**I4. ADR 0019 D5 / R-095.** One `ApiError{code, message, detail, retryable}` with the closed 15-code enum, unchanged. A
non-converged solve stays a domain result: the job ends `completed`, and `RunResult.error` stays `None`. The failure
reason is a *result* member (`failure`), never an error. `retryable` semantics are unchanged.

**I5. R-159, scope clarified (not changed).** "Every refusal's `message` begins with its reason code" governs the
machine message. A *rendering* starts with the human summary (FB-05 principle 3) and ends with the machine message
verbatim. So a test that matches the code prefix of `ApiError.message`, or that runs an unanchored `re.search` over
`str(exc)`, still passes.

**I6. R-022 and R-109.** `Unbound.kind` (conflict / inadmissible / incomplete / unsupported) stays in
`detail.unbound.kind`. The explanation's `kind` is a coarser, user-facing class beside it and replaces nothing. A
binder hint is carried verbatim as `explanation.hint`.

**I7. R-104 / ADR 0020 D8.** Job events carry no message text and gain no explanation.

**I8. Blueprint §7.7.** No catalogue text says or implies that no solution exists. This is linted (§4.2.7).

**I9. Rendering is total.** In production, `render` never raises. A defective entry, a template error or an unknown
code falls back to the next entry outward. The last resort is a minimal rendering: the code and the machine message.
Under the test-suite audit (§4.2.8) the same defect fails the session.

**I10. Units.** Numbers carry SI values and SI unit symbols from `schemas/units.json`. MSG converts nothing. X04 fills
`RenderContext.display_units` (§4.5).

---

## 3. Decisions on the seven open items

### 3.1 Where the human text lives (open item 1)

**Decision: the text is rendered from the catalogue on read, from `(code chain, params, context)`.**

Producers keep their machine messages byte for byte (I1). Structured params reach the renderer by four routes, in this
order of precedence:
1. **Diagnostic sidecar.** A producer may attach a `Diagnostic(code, params)` to the failure value it already returns
   (§4.6). 0.4 uses this for five thermal-kernel refusals only. The sidecar is never serialized into an artifact; it
   is persisted only as `run["diagnosis"]` in the job store's `worker_result` blob.
2. **`ApiError.detail` members.** Producers of `ApiError`s may add new detail members (open object), e.g. FB-03's
   `members`.
3. **The legacy grammar.** The positional args of `code(a, b)` segments are parsed from the machine text (§4.3) and
   named by the entry's `args`.
4. **The render context.** The revision document (element paths, unit model ids), `revision` and `job`.

A legacy `code(detail)` string maps into this model through the parser (§4.3). The parser is lexical first, then it
resolves against the catalogue. Every existing message is explainable without touching its producer: the numbers
missing from it are simply not shown.

**Rejected.**
- *Rewriting producer messages into human text.* It changes artifact templates, so every released bundle with a failure
  replays `MISMATCH` (ADR 0025 D6). It moves the `t07` key and breaks R-159's prefix tests. It also freezes wording
  into artifacts, so the wording can never improve.
- *Storing both machine and human text.* Stored prose goes stale when the catalogue improves, and floats inside stored
  text re-open ADR 0025's text-with-floats problem.
- *An ambient side channel (a `ContextVar` collector) instead of a sidecar on the value.* It is exact only by luck. A
  run with restarts can record the same `(code, stream)` several times with different numbers, and "the latest record"
  need not be the failure that became the outcome. A cached refusal also does not re-record. Wrong numbers in a message
  are worse than none. A field on the value is exact by construction and survives caching.
- *A new bundle member (`diagnosis.json`).* It violates I3.
- *Re-evaluating properties at render time to obtain numbers.* Rendering must not run physics: it would cost time,
  could fail, and would be non-deterministic across providers.
- *Changing `PropertyResult` to carry params.* It is a frozen interface. Provider text reaches the renderer instead as
  the `detail` text param of the kernel's `_refusal` sidecar (§4.6, producer P4).

### 3.2 The catalogue's form, identity and CI enforcement (open item 2)

**Decision: YAML data files validated by a JSON Schema, loaded by a small Python engine.**

The data files are `src/openflowsheet/messages/catalogue/*.yaml` (package data). The schema is
`schemas/message-catalogue.schema.json`. The engine is `openflowsheet.messages`. PyYAML is already a pinned runtime
dependency (`pyproject.toml:21`).

**Identity.**
- A format id, `openflowsheet-messages-v1`, is bumped only if the entry format changes incompatibly.
- A content digest, SHA-256 of ADR 0002 canonical JSON of the merged entries sorted by `code`, is reported by `explain`
  (`catalogue.sha256`).
- Neither the id nor the digest enters any identity, hash or explanation document. An explanation carries no catalogue
  version, so a wording fix does not churn every golden.
- **Codes are stable.** A released code is never removed or renamed, only marked `deprecated` with `replaced_by`.
  `src/openflowsheet/messages/catalogue/released-codes.txt` (written by `scripts/msg_catalogue.py freeze`) must be a
  subset of the catalogue's keys (gate MSG-G1). 0.4 writes its first version.

**CI enforcement uses three layers, because each one alone has a blind spot.**
- **G1, exact enumerations.** Every member of a closed vocabulary must have an entry:
  - `get_args(ApiErrorCode)`;
  - `verify.failure.TAXONOMY` keys plus `CONVERGED` and every other solve-event outcome in the solve-event schema enum;
  - `VerificationStatus`, `RegularityStatus` and the validation report status literal;
  - the job statuses and `jobs.model.ENDING_REASONS`;
  - every validation check id that `validation.py` can emit;
  - every limitation id of the support matrix source.
- **G2, static scan.** `scripts/msg_catalogue.py scan` AST-scans `src/openflowsheet/**/*.py` for code literals at
  emission sites:
  - the code argument of `api_error(...)`, `_refuse(...)` and `Failure(...)`;
  - the code of `RunUnsupportedError(...)` and of the `StoreError(..., code=...)` keyword;
  - string constants in assignments to names ending `_CODES`;
  - every string constant or f-string head that fully matches `^[a-z][a-z0-9]*(?:_[a-z0-9]+)+\(` (snake_case with at
    least one underscore, then `(`).

  Each found code must be in the catalogue or in `catalogue/scan-allow.yaml`, with a one-line reason per allowed token
  (false positives such as a function-call string). G2 catches codes no test exercises. It misses codes built at run
  time, e.g. `f"{ideal.code}({self.unit_id})"`.
- **G3, runtime audit.** Under pytest, `messages.audit` is enabled and observes every machine text at four hooks:
  `api_error()`, `bundle_for()`, `Unbound` construction, and `RunUnsupportedError` construction. A hook observes only
  when its direct caller's module name starts with `openflowsheet.`, so test-made codes are ignored. Each hook parses
  the text and records any code-shaped token (§4.3) that has no entry. `pytest_sessionfinish` fails the session and
  lists the misses. Production cost is one `is None` check per hook. G3 catches dynamically built codes on every path
  the suite exercises.

**Rejected.**
- *A Python registry (dict literals in a module).* F1 extensions would register executable code where data suffices.
  It is harder to lint, to generate docs from, and later to overlay with a translation.
- *JSON data.* Prose is the content here, and JSON has no multi-line strings and no comments.
- *Hashing the catalogue into each explanation.* It churns every golden on every wording fix, and buys nothing a
  reader needs.
- *A static scan only, or a runtime check only.* See the blind spots above.

### 3.3 Kind and layering fields (open item 3)

**Decision: on errors, the rendered explanation travels as `detail.explanation`, added at projection. On results, it
is a member of the new result members. `api-error.schema.json` is unchanged.**
- The schema already declares `detail` "Open" (`schemas/api-error.schema.json`, `detail.description`).
  `project_error` (`application/operations.py:526`) attaches `detail.explanation` to every top-level error document.
  Projection also attaches it to every `ApiError` document nested in a response, at each location where a response
  schema `$ref`s `api-error.schema.json` (`Job.error`, `RunResult.error`, …).
- The key `kind` is **not** used at the top of `detail`, because `verification_weakening_refused` already uses
  `detail.kind` with another meaning. The failure kind is `detail.explanation.kind`.
- In Python, `ApiError.explanation` and `ApplicationError.explanation` are computed properties: lazily rendered, not
  fields, not in `as_document()`. `ApplicationError.__str__` renders the layered text (§4.5).
- The stored machine document is unchanged, and so is a Python caller's direct `refused.error.as_document()`.
  The explanation is part of the *transported* document, exactly as bounding (§10.4) is.
- **Results.** `RunResult.failure.explanation` (§3.4). Validation reports, certificates and solve events are frozen
  schemas and gain nothing in 0.4. Their codes (check ids, statuses) are explained by `explain`, by the CLI text
  output (§3.7) and by the docs.
- **Warnings and notices** use the same entry shape with `kind: notice`:
  - certificate statuses, regularity statuses and validation statuses (family `status`);
  - `relabel`, `extrapolated`, `anchor_bridged` and `near_threshold` (family `notice`);
  - limitation ids (family `limitation`).

**Rejected.**
- *A new top-level `ApiError` member `explanation` (or `kind`).* It needs an ADR 0019 D5 change. Worse, the schema's
  top level is `additionalProperties: false`, so every released 0.3 client that validates errors
  (`ApiError.from_document`) would reject a 0.4 server's errors.
- *Attaching at creation in `api_error()`.* Rendered text would then be stored in job documents (violates I2) and go
  stale. It would also break about 33 exact-`detail` assertions on direct calls that never leave the process.
- *Only an `explain(code)` lookup, with no instance rendering.* Agents and the web shell would lose the element ids and
  numbers of the actual failure. The web shell would have to reimplement the renderer in JavaScript.

### 3.4 FB-03: the failure on `RunResult`, and a useful `not_found` (open item 4)

**Decision.**
- `RunResult` gains `failure: RunFailure | None`: required in the schema, nullable, and defaulting to `None` in Python
  so that existing constructors keep working. `failure` is non-null **iff** the job's outputs include a
  `failure_bundle` artifact. This mirrors how `verification_status` follows the certificate (`types.py:1160-1166`).
- `RunFailure` is built on read in `_run_result` (`local.py:995-1017`) from three sources:
  - the stored `failure-bundle.json` (`outcome`, `taxonomy`, `observations.message`, `implicated_sources`,
    `suggested_actions`);
  - `worker_result.run["diagnosis"]` when present (§4.6);
  - the revision document.

  It therefore also works on jobs a 0.3 store holds (no numbers there).
- `RunResult.error` keeps its meaning (operational failure, R-095).
- Python only: `RunResult.raise_for_outcome() -> RunResult`.
  - It raises `ApplicationError(self.error)` if `error` is set.
  - Otherwise it raises `SolveFailedError(self)` if `failure` is set or `job_status != "completed"`.
  - Otherwise it returns `self`, so calls chain.
  - `SolveFailedError(Exception)` lives in `application/types.py`. It is **not** an `ApplicationError` (a domain
    outcome is not an `ApiError`), and it renders the failure's layered text.
  - Verification status is separate and documented as such: a `CONVERGED` run whose status is `FAILED` does not raise.
- **`not_found`.** `_artifact_row` (`local.py:1481-1488`) keeps its message `"no such artifact"` and its detail
  members. When `artifact_id` has the form `<bundle id>/<member>` and that bundle has registered members, it adds:
  - `bundle_id`;
  - `member`;
  - `members`: the sorted file names of the registered `<bundle id>/…` artifacts, at most 64;
  - `job_id`, when the bundle id is `<job_id>:bundle` or `<job_id>:rerun`;
  - `run_outcome`: that job's `worker_result.run.outcome`, when the job has one.

  The catalogue's `not_found` variants render FB-03's sentence (§4.13.3).

**Rejected.**
- *Putting the cause into `RunResult.error`.* This contradicts R-095. It would also make "job failed operationally" and
  "solve did not converge" indistinguishable to every existing client.
- *An `explain_run(job_id)` operation instead of a member.* It does not "fail where the problem is" (FB-05
  principle 4): a student would not know to call it.
- *Storing the whole `RunFailure` in the run mapping at job end.* That needs two code paths, because old jobs do not
  have it. Deriving on read is one path and covers 0.3 stores.
- *Overriding `RunResult.__str__` or `__repr__`.* Notebooks and logs depend on the dataclass repr, and
  `raise_for_outcome` gives the same text on demand.

### 3.5 `explain` as an operation, and the docs pages (open item 5)

**Decision.**
- `Inspection` gains `explain(code: str) -> MessageEntry` (ADR 0019 D1 as amended by ADR 0058).
- It gets one `OPERATIONS` row (rule C1):

  | Field | Value |
  | --- | --- |
  | name | `explain` |
  | right | `read` |
  | request | `{code: string, 1..128, pattern ^[A-Za-z0-9][A-Za-z0-9_.-]*$}` |
  | response | `application-results.schema.json#/$defs/message_entry` |
  | HTTP | `GET /v1/explain/{code}` |
  | MCP tool | `explain`, with description file `bindings/descriptions/explain.md` |
  | transports | all four |

- The method reads no project state. It is `messages.entry_document(code)` behind the usual authorization and audit.
- An unknown code is refused `not_found` with detail `{code, suggestions}`. `suggestions` holds up to 5 catalogue keys
  within Levenshtein distance 3, compared case-insensitively, sorted by (distance, key).
- The CLI keeps `openflowsheet api explain --project …` like every operation. It also gets a top-level human command,
  `openflowsheet explain <code> [--json]`, which needs no project. It calls the same `entry_document` function, as
  `validate <CASE>` and `solve <CASE>` are convenience commands beside `api`.
- **Docs.** `scripts/doc_pages.py` (it already generates `guide/units.md` with `--check`) also generates one page per
  family: `docs-site/messages/{api-errors,refusals,outcomes,checks,statuses,limitations,notices,jobs}.md`.
  - Each page has one section per code, opened by an explicit `<a id="<code>"></a>` anchor.
  - The explanation's `docs` URL is `https://computational-chemical-engineering.github.io/openflowsheet/` +
    `messages/<family-slug>/#<code>`. The base is `site_url` in `mkdocs.yml`.
  - One section per code delivers FB-05 principle 7 (reachable from the message). It needs 8 generated files instead
    of about 300.

**Rejected.**
- *A CLI-only `explain`.* It violates rule C1.
- *One generated page per code.* About 300 files churn on every regeneration, and anchors give the same
  reachability.
- *`explain` that renders an instance from caller-supplied params.* Instances already carry their explanation, and a
  caller-supplied rendering is an injection surface for no gain.

### 3.6 The beginner-mistake corpus (open item 6)

**Decision.**
- **Location and form.** `tests/fixtures/msg/corpus.yaml` holds the expected facts. `tests/test_msg_corpus.py` builds
  each situation through the public API, starting from the README's Rankine change set.
- **Size for 0.4.** 12 cases (§7, MSG-G6), covering every mistake FB-05 principle 9 lists plus FB-05 case 2, a bad model
  id, a turbine pressure rise and an unsupported task (C12; since ADR 0071, the default install's missing audited NLP
  solver — ruling `docs/reviews/MSG-catalogue-X02-OPT.md`).
- **What a case asserts:**
  - `code` and `kind` exactly;
  - each named element id present in `explanation.elements` and in the summary text;
  - the `numbers` names (and values, where an independent expectation exists);
  - an action present, containing the case's `action_token` (e.g. `phase_capability`, `exist_ok`, `outcome`);
  - the complete rendered text equal to the stored `expected_text` (exact golden, regenerated only by
    `pytest tests/test_msg_corpus.py --msg-update` and reviewed in the diff);
  - for transported cases, documents equal across the four transports (via `tests/t07_transport_support.py`).
- The tutorial session can add cases in the same YAML format; `docs-site/messages/index.md` documents the format.
- A case records the code the software actually emits. If that code is unspecific (e.g. a bare `invalid_request` with
  no `reason`), the engineer reports it in the build-decisions log and does **not** invent a new machine code, because
  machine messages are under I1.

**Rejected.**
- *Structural asserts only (code and kind).* The point of FB-05 is the wording. An exact golden makes every wording
  change a reviewed diff.
- *Declarative YAML recipes for the setup.* That needs a mini-language for edits and solves. Python setup functions
  keyed by case id are simpler and type-checked.

### 3.7 Exit codes and CLI rendering (open item 7)

**Decision.** `API_EXIT_CODES` (`cli.py:52-55`, 2..16 in enum order) is unchanged, since no code is added. 0 still
means a domain result and 1 still means the call was never made. **Rule: a machine document goes to stdout and the
human rendering to stderr. A human-text command appends its explanation lines to stdout after its existing lines.**

| Command | stdout | stderr | exit |
| --- | --- | --- | --- |
| `api <op>`, refused | ApiError document, projected (now with `detail.explanation`) | layered text | unchanged (2..16) |
| `api <op>`, result with a non-null `failure` (any nesting) | result document | layered text of the failure | 0 |
| `validate`, refused | projected ApiError document | layered text | unchanged |
| `validate`, text report | existing lines. After each FAIL or WARN check whose entry is complete, one more line `        <summary> <action>` (8 spaces) | — | unchanged |
| `solve <CASE>` | existing lines. If a failure bundle exists: a blank line, then the layered failure text. If `verification ≠ VERIFIED`: one line `note              <status summary>` | — | unchanged (0 iff VERIFIED) |
| `inspect` | existing lines. Under `=== failure`, the layered text indented by 2 | — | unchanged |
| `project init`, refused | — | layered text (replaces the old one-liner) | 2 (unchanged) |
| `project init --exist-ok` on an existing project | as on creation: `project …` / `directory …` | — | 0 |
| `explain <code>` | entry text (or the `message_entry` JSON with `--json`) | unknown code: layered text | 0; unknown 6 (`not_found`) |
| any uncaught `Exception` in `main` | — | the `internal_error` layered text (kind bug), then the traceback | 1 (as now) |

- Human text always goes to stderr, whether or not stderr is a terminal: the output is deterministic and testable.
- The golden file `tests/fixtures/t07/cli-existing-commands.json` changes in these records only:
  - `validate <CASE> --task optimization`: stdout gains `detail.explanation`, and stderr gains the text;
  - the second `project init`: stderr;
  - `validate <ROOT>/broken.yaml`: stdout, only if one of its FAIL/WARN check ids has a complete entry.

  Every exit code and every other record stays byte-identical (MSG-G7).
- **Rejected.**
  - *Stripping `explanation` from the CLI's stdout JSON.* The conformance suite compares the CLI's document with the
    other transports'.
  - *TTY-dependent output.* It is not reproducible in tests.
  - *New exit codes per kind.* That is a frozen mapping, and kind is already in the document.

### 3.8 FB-01 (Frank's shape, made precise)

**Decision.**
- `LocalApplication.create(directory, *, project_id=None, exist_ok=False)`. It is implemented as *try to create; on
  the typed refusal `project_exists`, open if `exist_ok`*. This avoids a check-then-act race.
- `StoreError` gains keyword-only `code: str | None = None` and `params: Mapping[str, Any] | None = None`.
  - A coded `StoreError`'s `args[0]` is the machine message `"<code>: <directory>"`, and its `__str__` is the layered
    text.
  - An uncoded `StoreError` (every other existing raise, including `IdempotencyKeyReusedError` and
    `ActiveJobLimitError`) behaves exactly as today.
- Five codes, all kind `input`, family `refusal`:

| Directory state | `exist_ok=False` | `exist_ok=True` |
| --- | --- | --- |
| absent, or empty directory | create | create |
| holds a project (`DATABASE_NAME` present) | refuse `project_exists` | open it (same `capability`/`executor` defaults as `open`) |
| holds a project whose `project_id` ≠ the `project_id` passed | refuse `project_exists` | refuse `project_id_mismatch` |
| non-empty, not a project | refuse `directory_not_empty` | refuse `directory_not_empty` |
| path is a file | refuse `not_a_directory` | refuse `not_a_directory` |

- `ProjectStore.open` on a directory without `DATABASE_NAME` raises the coded `not_a_project` (today an uncoded
  `StoreError`, `store.py:~296`).
- The summaries of `project_exists` and `directory_not_empty` contain the words "is not empty", so existing
  `match="not empty"` tests still pass. They say "directory", as Frank asked.
- The CLI `project init` gains `--exist-ok`.
- The README quickstart becomes `LocalApplication.create("plant", exist_ok=True)`, plus `run.raise_for_outcome()`
  before the solution state is read. A new test runs the quickstart twice in one directory (MSG-G9).

---

## 4. The design in detail

### 4.1 Package layout and dependency direction

```
src/openflowsheet/messages/
  diagnostic.py   Quantity, Diagnostic — stdlib only; the one module the solver path imports
  catalogue.py    load + validate + merge + register(); CATALOGUE (lazy singleton); entry_document(code)
  legacy.py       parse_chain(text) -> Chain (lexical; §4.3)
  render.py       RenderContext, render_error(ApiError,…), render_failure(…), render_code(code, params,…)
                  -> Explanation (dict, schema `explanation`); the template engine (§4.2.4)
  text.py         format_text(explanation, details) -> str (§4.5)
  audit.py        enable() / observe(text) / misses()
  catalogue/      kinds.yaml, vocabulary.yaml, api_errors.yaml, refusals.yaml, outcomes.yaml, checks.yaml,
                  statuses.yaml, limitations.yaml (generated part, §4.2.9), notices.yaml, jobs.yaml,
                  scan-allow.yaml, released-codes.txt
```
- `messages` imports nothing from `application`, `models`, `orchestrator` or `verify`.
- `models/thermal/*`, `models/__init__.py`, `models/revision_flowsheet.py` and `orchestrator/*` import only
  `messages.diagnostic`.
- `application` imports `messages`.
- `verify/failure.py`, `application/contract.py` and `application/binding.py` import only `messages.audit`, for the
  G3 hooks.

### 4.2 The catalogue

#### 4.2.1 Families and kinds

**Families** (one docs page each):

| Family | Codes |
| --- | --- |
| `api_error` | the 15 `ApiErrorCode`s |
| `refusal` | lower-snake typed refusal codes, FB-01's five codes included |
| `outcome` | solve outcomes |
| `check` | validation check ids |
| `status` | verification, regularity and validation statuses |
| `limitation` | support-matrix ids |
| `notice` | non-failure flags |
| `job` | job statuses and ending reasons |

**Kinds** (exactly five, from rule C3). `kinds.yaml` holds, per kind, a `label` and a `default_action`. These texts are
normative:

| kind | label (the `Kind:` line) | default_action |
| --- | --- | --- |
| `input` | Input problem: something in the flowsheet or the request needs to change. | Correct the element named above; `openflowsheet explain <code>` states the rule. |
| `not_supported` | Not supported in this version: a limitation of OpenFlowsheet, not an error in your flowsheet. | See the limitation's docs section for workarounds; support may come in a later version. |
| `numerical` | Numerical failure: the solver did not find the solution; your flowsheet may be correct. | Try another initial guess or solve policy; if the failure persists, report it with the failure bundle. |
| `bug` | Internal error in OpenFlowsheet: please report it. | Report it at https://github.com/computational-chemical-engineering/openflowsheet/issues with the failure bundle or the server log. |
| `notice` | Notice: not a failure. | No action is needed unless the meaning above matters for how you use the result. |

**Kind assignment for `api_error`** (normative): `invalid_request`, `document_not_canonical`, `unauthenticated`,
`forbidden`, `not_found`, `idempotency_key_reused`, `revision_not_ready`, `verification_weakening_refused`,
`budget_exceeds_ceiling`, `limit_exceeded`, `model_replacement_incompatible` → `input`; `not_ready` → `notice`;
`revision_unsupported`, `unsupported` → `not_supported`; `internal_error` → `bug`. For `revision_unsupported`, a variant
maps `detail.unbound.kind` ∈ {conflict, inadmissible, incomplete} → `input`.

**Kind assignment for `outcome`**, by the `TAXONOMY` class:

| `TAXONOMY` class | kind |
| --- | --- |
| structure/specification conflicts | `input` |
| budget/cancellation outcomes | `numerical` |
| initialization and recycle failures | `numerical` |
| rank/linear/globalization failures | `numerical` |
| homotopy/PTC/active-set stalls | `numerical` |
| model domain/conservation/derivative defects | `bug` |

Overrides: `UNSUPPORTED_RANK_STRUCTURE` and `CAPABILITY_UNAVAILABLE` → `not_supported`; `EVALUATION_ERROR` →
`numerical`; `CONVERGED` → `notice`.

**Kind assignment for `status`:**
- `VERIFIED`, `RELAXED`, `UNVERIFIED` and all `RegularityStatus` values → `notice`;
- verification `FAILED` → `numerical`;
- validation statuses: `INVALID` → `input`, the others → `notice`.

**Kind assignment for `refusal` stubs** (rule; any judgment call is flagged `review: true` for the reviewer):

| Code pattern | kind |
| --- | --- |
| `*_unsupported`, `*_not_admitted`, `*_not_accepted`, `syn001_only`, `isentropic_state_*`, `near_critical` | `not_supported` |
| `*_missing`, `*_conflict`, `*_unknown`, `*_unreadable`, `*_duplicate`, `*_invalid`, `*_outside_domain`, `out_of_domain`, `pressure_rise`, `pressure_fall`, `phase_regime_mismatch`, `declaration_mismatch`, FB-01's five | `input` |
| `*_disagree`, `*_disagrees`, `*_inconsistent`, `*_mismatch` (internal), `failure_bundle_unmapped`, `solution_state_mismatch`, `state_mismatch` | `bug` |
| `not_converged`, `*_stalled`, `kernel_refused`, `restart_pass_rejected`, `homotopy_stalled` | `numerical` |

`limitation` → `notice`. `notice` → `notice`. `job`: `completed` → `notice`; `failed`, `cancelled`, `timed_out` and the
ending reasons → `notice`, except `worker_lost`, `owner_lost` and `store_error` → `bug`.

#### 4.2.2 Entry fields (`schemas/message-catalogue.schema.json`, `$defs/entry`, closed)

A catalogue document is `{catalogue: "openflowsheet-messages-v1", namespace: null | <ext id>, entries: [entry…]}`.

| Field | Type | Rule |
| --- | --- | --- |
| `code` | string | `^[A-Za-z][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+)?$`. A `.` is reserved for extension namespaces (§4.11). Unique across the merged catalogue. |
| `family` | enum (8) | §4.2.1 |
| `kind` | enum (5) | §4.2.1 |
| `complete` | bool | `false` = stub tier |
| `title` | string ≤ 80 | plain noun phrase; the docs heading |
| `args` | [param name] | names of the legacy positional args of `code(a, b, …)`, in order |
| `detail_pattern` | regex or null | Python `re` with named groups; applied to the `detail` text param (§4.3), each group a param |
| `params` | map name → `{type, label?, optional?, vocabulary?}` | `type` ∈ {`unit`, `stream`, `port`, `specification`, `revision`, `job`, `artifact`, `bundle`, `directory`, `pointer`, `element`, `code`, `text`, `enum`, `number`, `quantity`, `list`, `display_unit`} (`display_unit`: X04, ADR 0075 D7.7 — a display unit, rendered in its text spelling, `degC` → `°C`). `vocabulary` names a table in `vocabulary.yaml` (for `enum`). Every templated name must be declared here or be a derived/context param (§4.2.5). |
| `summary` | template | **required**. Line 1: what and where. |
| `context` | template | `outcome` entries only: line 1 when this outcome wraps an inner cause (§4.4) |
| `where` | template | optional |
| `why` | template | required if `complete` |
| `action` | template | required if `complete`; else the kind's `default_action` is used |
| `variants` | [{`when`, and any of `summary`, `context`, `where`, `why`, `action`, `kind`}] | first match wins, field by field over the base |
| `gap` | {`limitation`: id or null, `capability`: string or null} | required iff kind is `not_supported` and `complete`; the typed gap R-931's agentic layer reads |
| `see_also` | [code] | each must resolve |
| `examples` | [{`params`: {…}, `chain`?: [code…]}] | ≥ 1 if `complete`; used by lint, docs and `explain` |
| `deprecated`, `replaced_by` | bool, code | only for codes in `released-codes.txt` |
| `review` | bool | the kind assignment awaits design-lane review; CI prints the count, never fails on it |

#### 4.2.3 `when` conditions

A condition is a map with any of these keys. A variant matches when all its keys hold.
- `has: [p…]` — each param is present.
- `equals: {p: v}` — each param equals its value.
- `not_equals: {p: v}` — each param is absent or differs from its value.
- `surface: [python|cli|http|mcp]` — the context's surface is listed. A transported document always renders with
  surface `null`, so a surface variant applies only to Python exception text and to CLI text.
- `outer: [code…]` — one of these codes occurs earlier in the chain.

#### 4.2.4 Template grammar (normative)

- `{name}` renders the param by its type:
  - an element (`unit`, `stream`, `port`, `specification`, `element`, `revision`, `job`, `artifact`, `bundle`,
    `directory`) → `'<id>'`, single-quoted;
  - `quantity` → `<number> <unit>` (§4.5 number format);
  - `number` → §4.5 number format;
  - `enum` → its vocabulary phrase;
  - `code` → the raw code;
  - `list` → items rendered by their type and joined with `, `;
  - `text`, `pointer` → as is.
- `{name!raw}` gives the raw value: no quotes, no phrase.
- `{name!title}` (type `code` only) gives that code's catalogue `title`.
- `[ … ]` is an optional segment. It renders iff every param referenced directly inside it (not in a nested segment) is
  present. Segments nest.
- `{{`, `}}`, `[[` and `]]` are literals.
- Nothing else: no attribute access, no indexing, no format specs, no code.
- An undeclared name is a lint error (MSG-G4). A missing required param at render time falls back per I9.

#### 4.2.5 Derived and context params

When `RenderContext.revision` (the revision document) is present, the renderer derives for each element param `x`:
- for `x` of type `unit`: `x_path` = `instances[i]` and `x_model` = the instance's model id;
- for `x` of type `stream`: `x_path` = `connections[i]`;
- for `x` of type `specification`: `x_path` = `specifications[i]`, and a numeric `x` is read as the index.

`i` is the 0-based position of the element whose `id` equals the value. A derived param that cannot be derived is
absent.

Context params:
- `revision`, `job` and `bundle` when known;
- `operation` for `ApiError`s.

**Chain params merge outer → inner, and inner wins on a name clash.** So `unit` from `initializer_failed(T)` is
available to `phase_regime_mismatch`'s templates.

#### 4.2.6 Tiers and 0.4 coverage

Every code found by G1, G2 or G3 has an entry; anything not listed below may be a stub (`complete: false`, a `summary`,
a `kind` by §4.2.1's rule). **Complete in 0.4 (normative list):**
- all 15 `api_error`;
- every `outcome` (the `TAXONOMY` keys and `CONVERGED`);
- `VERIFIED`, `RELAXED`, `UNVERIFIED`, `FAILED`, the four `RegularityStatus` values and the validation statuses;
- `completed`, `failed`, `cancelled`, `timed_out`;
- refusals: `phase_regime_mismatch`, `isentropic_state_two_phase`, `isentropic_state_single_phase`,
  `initializer_failed`, `out_of_domain`, `pressure_rise`, `pressure_fall`, `model_unsupported`, `task_unsupported`, and
  FB-01's five;
- `L-TH-4`;
- every code the corpus (§7, MSG-G6) emits, check ids included.

That is about 75. The prose of complete entries is drafted by the build lane and judged in the package's `reviewer`
pass, because no test catches a wrong physical claim (CLAUDE.md lane rule).

#### 4.2.7 Lint (MSG-G4)

For every entry:
- schema-valid; key unique; `see_also`, `replaced_by` and `gap.limitation` resolve;
- every template name declared;
- every complete entry has `why`, `action` and `examples`, and each example renders in every variant it can reach
  without error.

For complete entries:
- The rendered example `summary` (or `context`) is ≤ 200 characters.
- **Jargon lint.** Applied to the *literal text* of `summary` and `context` templates, with placeholders and quoted
  segments removed. It finds none of:
  - the words `closure`, `regime`, `initializer`, `initialiser`, `traversal`, `revision_eo`, `kernel`, `tear`,
    `residual`, `Jacobian`, `homotopy`, `PTC`, `taxonomy`, `None`;
  - any snake_case token;
  - any document id `\b[A-Z]\d{2}\b`;
  - any class name `\b[A-Z][a-z]+(Error|Result|Failure)\b`.
- **Infeasibility lint** (I8), on every text of every entry, case-insensitive: none of `infeasib`,
  `no solution exists`, `has no solution`, `cannot be solved`, `impossible`.

#### 4.2.8 Audit (MSG-G3)

`messages.audit.enable()` is called in `tests/conftest.py` `pytest_configure`. A hook calls
`audit.observe(text, caller_module)`. The observer parses with §4.3 and records each code token without an entry,
deduplicated with the first caller seen. `pytest_sessionfinish` sets `session.exitstatus = 1` and writes the misses to
the terminal report if any exist. The suite runs without xdist today; if xdist is ever added, the controller must merge
the workers' miss sets (build choice).

#### 4.2.9 Limitations

`scripts/msg_catalogue.py sync-limitations` imports the row parser of `scripts/t08_support_matrix.py` (the source of
`docs/support-matrix.md`).
- It writes `catalogue/limitations.yaml`, with one entry per id: `family: limitation`, `kind: notice`,
  `complete: false`, `title` = the id, and `summary` = the matrix row's text.
- It preserves any hand-written `why`, `action` and `complete: true` already in the file for that id. Generated fields
  are overwritten; authored fields are kept.
- `sync-limitations --check` fails when the file is out of sync (MSG-G5).

### 4.3 The legacy grammar (`messages.legacy.parse_chain`) — normative

Input is a machine text. Only its first line is parsed into a chain; lines 2 and after form `detail` text.

1. Split the first line on the separator `": "` into segments.
2. A segment is a **code segment** iff it fully matches `^(?P<code>[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*)(?:\((?P<args>[^()]*)\))?$`
   **and** at least one of these holds: `code` contains `_`, or `args` is present, or `code` is a catalogue key.
   `args` split on `,`, and each one is stripped.
3. A segment equal to a `PropertyStatus` literal (`models` `PropertyStatus` values) is a **status** if the *next*
   segment is a code segment. Otherwise rule 2 applies to it.
4. Parse left to right. At the first segment that is neither a code nor a status, stop: that segment and the rest,
   joined by `": "`, are the `detail` text, together with lines 2 and after.
5. **Resolution against the catalogue.** For each code segment with an entry:
   - its args are named by `args`, in order; surplus args are dropped, and missing ones are absent;
   - an arg whose declared type is `code` is **expanded**: its value is appended to the chain as a further code
     segment with no args;
   - `detail_pattern`, if any, is matched (search) against the `detail` text, and its named groups become params of
     the innermost resolved code. A group value that parses as a float becomes a `number`, except where the param is
     declared `quantity`; then the entry gives the unit in a sibling group named `<name>_unit`, or the param
     declaration fixes it.

Examples (each one is a required unit test in WO-1):

| Text | Chain (code[args]) | status | detail |
| --- | --- | --- | --- |
| `initializer_failed(T): phase_regime_mismatch(S4)` | initializer_failed[T], phase_regime_mismatch[S4] | — | — |
| `initializer_failed(traversal-G0-v1): unsupported: phase_regime_mismatch(S4)` | initializer_failed[traversal-G0-v1], phase_regime_mismatch[S4] | unsupported | — |
| `initializer_failed(T): isentropic_state_two_phase(T)` | initializer_failed[T], isentropic_state_two_phase[T] | — | — |
| `task_unsupported(optimization)` | task_unsupported[optimization] | — | — |
| `unsupported(legacy_route_not_admitted)` | unsupported[…], legacy_route_not_admitted (expanded) | — | — |
| `internal_error(solution_state_mismatch)` | internal_error, solution_state_mismatch (expanded) | — | — |
| `out_of_domain: temperature 250.0 K outside [280.0, 440.0] K` | out_of_domain | — | `temperature 250.0 K outside [280.0, 440.0] K` |
| `inadmissible_phase(inlet, VAPOR)` | inadmissible_phase[inlet, VAPOR] | — | — |
| `failure_bundle_unmapped(STAGNATION,x,y)` | failure_bundle_unmapped[STAGNATION, x, y] | — | — |
| `no such artifact` | (empty) | — | `no such artifact` |
| `pressure_rise(turbine)\nP_spec = 2e5 Pa is above the inlet's 1e5 Pa` | pressure_rise[turbine] | — | line 2 |
| `restart_initializer_failed: <msg>` | restart_initializer_failed, then `<msg>` parsed on | — | — |

### 4.4 Resolution and rendering

**Chain for an `ApiError`.** `[error.code]` followed by the parse of the **first** of these candidate texts that
yields at least one code:
1. `detail.unbound.detail`, with `kind` override from `detail.unbound.kind` (§4.2.1), `hint` = `detail.unbound.hint`,
   and `elements` += `detail.unbound.implicated` (type `element`);
2. the id of the first check with result `FAIL` in `detail.report.checks`, when `detail.report` is a validation report;
3. `detail.reason`, when it is a string;
4. `message`.

Params:
- the `detail` members whose names the entries declare;
- the chain args;
- context.

**Chain for a `RunFailure`.** `[bundle.outcome]` followed by the parse of `bundle.observations.message`. Params:
- context: `revision` = `RunResult.revision_id`, `job` = `job_id`, `bundle` = the bundle id, and the revision document;
- chain args;
- `diagnosis.params` — only if `diagnosis.code` is a code of the chain **and** every element-typed param present in
  both the diagnosis and the chain args has equal values. Otherwise the diagnosis is ignored (in audit mode this
  raises, so the corpus catches a mis-threaded sidecar).

**The explained code** is the innermost code of the chain that has an entry. Its entry supplies `kind`, `why`,
`action`, `where`, `gap` and `numbers`.

**Line 1.**
- If the chain's first code is an `outcome` and the explained code is a *different* code: `summary` = the outcome
  entry's rendered `context`, and `cause` = the explained entry's rendered `summary`.
- Otherwise `summary` = the explained entry's `summary`, and `cause` is absent. `ApiError` codes never contribute
  `context`.

**`numbers`.** Every `quantity` and `number` param present on the explained code, in declaration order, at most 8,
each `{name, label, value, unit, kind}`. `unit` is `""` for a bare number; `kind` is the quantity kind or null.

**`elements`.** Every element-typed param present on any chain code, deduplicated by `(type, id)`, outer first, at most
16, each `{type, id, path}`. `path` is the derived document path as a list (`["connections", 3]`) or null.

**Stubs.** A stub entry contributes `summary` and `kind`. `why` is absent. `action` is the kind's `default_action`.
`complete` is `false`.

### 4.5 The explanation document and the text format

**`application-results.schema.json#/$defs/explanation`** (closed; all members required; nullable where marked):

```
code       string            the explained code
family     enum(8)
kind       enum(5)
complete   boolean
summary    string            line 1
cause      string | null
where      string | null
why        string | null
action     string
hint       string | null     binder hint (R-109), verbatim
elements   [{type: string, id: string, path: [string|integer] | null}]
numbers    [{name: string, label: string, value: number, unit: string, kind: string | null}]
gap        {limitation: string | null, capability: string | null} | null
chain      [string]          codes outer → inner, the transport code or the outcome first
docs       string (uri)
```

**Bounding.** `project_error` attaches the explanation **before** bounding and bounds it with everything else
(`TEXT_LIMIT` = 2048 per string).

**Number format** (normative; so that the corpus is stable):
- `v == 0` → `0`;
- `1e-3 ≤ |v| < 1e9` → let `d = 3 − floor(log10|v|)`, and render `round(v, d)` with `max(d, 0)` decimals. Examples:
  2627345.1 → `2627000`, 10000.0 → `10000`, 0.0812345 → `0.08123`, 373.124 → `373.1`;
- otherwise → `format(v, ".4g")`;
- non-finite values are never rendered: producers drop them (§4.6).

**X04 slot.** `RenderContext.display_units: Mapping[kind, unit] | None`, always `None` in MSG. X04 adds an optional
`display: {value, unit}` to each `numbers` item and renders text from it. The SI `value`/`unit` stay.

**Text format** (`messages.text.format_text`; Python `__str__`, CLI stderr, CLI human output). Lines are omitted when
their content is absent. There is no wrapping. A field's continuation lines are indented by 11 spaces.

```
<summary>
  Cause:   <cause>
  Why:     <why>
  Do:      <action>
  Hint:    <hint>
  Kind:    <kinds.yaml label>
  Code:    <code>[, in <outer chain codes joined " → ">] (openflowsheet explain <code>)
  Docs:    <docs>
  Details: <machine details>
```

`<machine details>`:
- `ApiError`: `"<code>: <message>"`, which is exactly the pre-MSG `str(ApplicationError)` (`contract.py:47`). So every
  unanchored `match=` on the old string still matches.
- `RunFailure`: `"<observations.message> — <failure bundle artifact id>"`.
- Coded `StoreError`: its `args[0]`.

### 4.6 The diagnostic sidecar

```python
@dataclass(frozen=True)
class Quantity:            # messages/diagnostic.py
    value: float           # finite, SI
    unit: str              # an SI symbol from schemas/units.json, e.g. "J/mol", "Pa", "J/(mol*K)"
    kind: str              # a quantity-kind id from schemas/units.json, e.g. "molar_enthalpy"

@dataclass(frozen=True)
class Diagnostic:
    code: str
    params: Mapping[str, str | int | bool | float | Quantity]   # non-finite floats dropped at construction
    def as_document(self) -> dict: ...   # {"code", "params"}; Quantity -> {"value","unit","kind"}
```

**Carrier rule.**
- Each carrier gets `diagnostic: Diagnostic | None = field(default=None, compare=False, hash=False, repr=False)`.
- The field travels on the value that carries the failure's message, along the path that message already takes.
- No `as_document`, `asdict` or serializer of a carrier may emit it. Any carrier serialized with `dataclasses.asdict`
  must exclude it explicitly.
- The carriers on the revision initialization path (0.4) are:
  - `Failure` (`models/thermal/kernel.py:95`);
  - `UnitEvaluation` (`models/__init__.py:319`), set by each thermal unit's `_failure` (`valve`, `heater`, `flash`,
    `machines`, `mixer`);
  - `FlowsheetPass` (`models/revision_flowsheet.py:886`), set in `fail(...)` from the failing evaluation;
  - `InitialStateFailure` (`orchestrator/revision.py:93`), set in `_failure(...)`;
  - `StepResult` (`orchestrator/executor.py:728-741`).
- From there it goes on to `application/revision_run.py`. Where `revision_run` builds the failure bundle (`:864`), the
  outcome-defining step's diagnostic becomes `run["diagnosis"] = diagnostic.as_document()` in the worker result
  (`jobs/runner.py` `WorkerResult.run`). It is written only when a failure bundle is written.
- The store schema stays `t07-store-v1`: `worker_result` is a JSON blob.

**Amendment (review `docs/reviews/MSG-review.md` Q1, route (a) narrowed; built as WO-5a).** F0 M9 (R-940) froze
`models/thermal/*`, so in 0.4 the sidecar has **one producer**: the traversal hop
`models/revision_flowsheet.py` (`traverse`, where the failing unit's message is cut to its first line). It builds
`Diagnostic(<the code at the head of line 1>, {"detail": lines 2+})`, in P4's form, from the message text the
unit already returns; no thermal module and no machine text changes (I1). The carriers are `FlowsheetPass`,
`InitialStateFailure` and `StepResult` (not `Failure` or `UnitEvaluation`). `explain_failure` applies the explained
entry's `detail_pattern` to the sidecar's `detail` (sidecar params win over its groups), and derives a missing
`outlet` stream param as the one connection leaving the `unit` param's `outlet` port (§4.2.5). What the detail lines
carry is delivered: P2's `s_star`, `s_saturated`, `pressure`, `phase`; P5's `p_spec`, `p_inlet`; P4's value and
range; P1's `declared`, `landed`, `vapour_fraction`. P1's `property`, `value`, `saturated_liquid`,
`saturated_vapour` and `pressure` are in no text: they are deferred to the F6 v2 unit models (ADR 0065; Q1 (c)),
and the P1–P5 list below describes that later producer set. ADR 0058 D6 and R-936 are unchanged.

**Producers in 0.4** (exhaustive). Units come from the provider's basis; the engineer confirms the basis (molar or
mass) at each site, and MSG-G6's case asserts the unit string.
- **P1.** `Mismatch.failure(stream)` (`kernel.py:543`), code `phase_regime_mismatch`. `Mismatch` gains
  `evidence: Mapping | None` (compare/hash/repr False), set in `declared_state` where the `Mismatch` is built. Params:
  - `stream`;
  - `declared`, `landed`, in the `phase_capability` vocabulary `liquid|vapor|vapor_liquid` (the method's own
    `capability` map);
  - `vapour_fraction` = beta, when present;
  - `property` = the `prop` argument (`h` or `s`);
  - `value` = the target specific value, a `Quantity`;
  - `saturated_liquid` and `saturated_vapour` = `sat.value("LIQUID"|"VAPOR", prop)`, as `Quantity`s;
  - `pressure`, a `Quantity` in Pa.
- **P2.** `isentropic_state` two-phase (`kernel.py:661`), code `isentropic_state_two_phase`. Params: `phase`, `s_star`
  (`Quantity`), `s_saturated` (`Quantity`), `pressure` (`Quantity`). The machine's re-wrap (`machines.py:704`) adds
  `unit` (`self.unit_id`) and, when the machine knows it, `outlet` (the outlet stream id).
- **P3.** `isentropic_state` single-phase (`kernel.py:653`), code `isentropic_state_single_phase`. Params: `pressure`,
  `landed`, `phase`. The machine re-wrap adds `unit`.
- **P4.** `_refusal(status, message)` (`kernel.py:106`). Code = the parsed code. Params: `detail` = the provider message
  (text). `detail_pattern` then extracts numbers per entry.
- **P5.** The machine bound (`machines.py:656-664`), codes `pressure_rise` / `pressure_fall`. Params: `unit`,
  `p_spec` and `p_inlet`, as `Quantity`s in Pa.

The machine message text of each producer stays byte-identical (I1). The legacy SYN-001 tear path
(`InitializerFailedError`) gets no sidecar in 0.4.

### 4.7 Surfaces

- **Python.**
  - `ApplicationError.__str__` → layered text with surface `python`; `args[0]` stays `"<code>: <message>"`.
  - `ApplicationError.explanation` and `ApiError.explanation` are properties.
  - `RunResult.failure`, `raise_for_outcome()` and `SolveFailedError` (§3.4).
  - Coded `StoreError.__str__` (§3.8).
  - **Rule:** no code may turn an `ApplicationError`, coded `StoreError` or `SolveFailedError` into a document through
    `str()`. Existing conversions by `str()` (`admission.py:415`, `local.py:1614`, `projection.py:217`) are of other
    exception classes and stay as they are. WO-3 greps for this and MSG-G0 proves it.
- **Dispatch / projection.**
  - `project_error(error)` → `attach_explanation(error, RenderContext(surface=None))`, then it bounds.
  - `project_response` attaches explanations to the nested `ApiError` documents at the locations §3.3 names.
  - The locations come from the resolved response schemas: a test walks each `OPERATIONS` response schema, collects
    every `$ref` to `api-error.schema.json`, and asserts that a fixture with an error there is projected with
    `detail.explanation`.
  - Every error exit of every binding goes through `project_error`: `http.py` `_error_response`, `_RefusedError` and
    `_internal_error`; `mcp.py` `_error_result`, `_unknown_tool` and the internal-error path; the CLI's printing.
- **HTTP.** Status and body shape are unchanged; `detail.explanation` is the only addition.
- **MCP.**
  - `isError`: unchanged.
  - `structuredContent`: the projected document.
  - The §10.6 text item: unchanged framing, with JSON that now carries `detail.explanation`.
  - The `explain` tool is new.
- **CLI.** §3.7.
- **Web shell.** Wherever it shows an error's `message` today, it shows `detail.explanation.summary`, then `action`,
  then the code. Where it shows a run outcome, it shows `failure.explanation.summary` when `failure` is non-null. No
  other visual change.

### 4.8 `RunFailure` and `RunResult`

`run-result.schema.json` gains the required member `failure` (`{"anyOf": [{"$ref": "#/$defs/run_failure"}, {"type": "null"}]}`).
`$defs/run_failure` is closed and all of its members are required:

```
outcome            string             bundle `outcome`
taxonomy           string             bundle `taxonomy`
message            string | null      bundle `observations.message`, verbatim
code               string             the explained code (§4.4)
chain              [string]
implicated         [string]           bundle `implicated_sources`
suggested_actions  [string]           bundle `suggested_actions[].action`
failure_bundle     string             artifact id of failure-bundle.json
params             object             the merged params (quantities as {value, unit, kind})
explanation        $ref application-results.schema.json#/$defs/explanation
```

- Python `RunFailure` is a frozen dataclass with these fields (`explanation` as a `Mapping`). It has `as_document` and
  `from_document`, and `__str__` = layered text.
- The `RunResult` field is `failure: RunFailure | None = None`, placed after `solve_path`. `__post_init__` adds: a
  non-null `failure` requires a `failure_bundle` output.
- **Converse.** Every result `_run_result` builds has `failure` non-null when such an output exists. A test asserts the
  converse over every solve the suite runs; see WO-6.
- If `failure-bundle.json` cannot be read or parsed, `failure` is built from the outcome alone: `message: null`,
  `chain: [outcome]`, empty lists. It never raises.

### 4.9 `explain`: `application-results.schema.json#/$defs/message_entry` (closed)

```
code, family, kind, complete, title
summary, context, where, why, action      display templates: {p} → <p>, optional brackets removed (string | null)
params      [{name, type, label, optional}]
gap         {limitation, capability} | null
see_also    [string]
examples    [explanation]                 rendered with the entry's example params, surface null
docs        string (uri)
deprecated  boolean;  replaced_by  string | null
catalogue   {id: "openflowsheet-messages-v1", sha256: string}
```

`MessageEntry` (Python, frozen) joins the frozen result-type names (ADR 0058).

### 4.10 FB-01 messages

FB-01's message texts are worked entry 4.13.4. The table of directory states is in §3.8.

### 4.11 The extension slot (what F1 inherits)

`messages.catalogue.register(document: Mapping, *, namespace: str)`:
- validates `document` against `message-catalogue.schema.json`;
- requires `document.namespace == namespace` and every key to start with `namespace + "."`;
- refuses any key already present (core keys can never be overridden);
- refuses registration after the first lookup has frozen the catalogue (raises `RuntimeError`).

F1 decides how and when extensions call it (discovery, ordering, trust). MSG tests the function with an in-test fake
extension. Nothing else about F1 is fixed here.

### 4.12 Docs

- `scripts/doc_pages.py` generates the 8 family pages (§3.5), each section showing:
  - code, title, kind label, the display templates, params, gap (with a link to the support-matrix row), see_also, and
    the rendered examples;
  - stubs say so plainly ("No plain-language explanation is written yet; the summary is the technical one").
- `docs-site/messages/index.md` is hand-written: the layered format, the five kinds, `explain`, the corpus format.
- The `mkdocs.yml` nav gains a *Messages* section.
- `docs-site/guide/limitations.md` links its codes to their sections.
- `docs-site/agents.md` documents `detail.explanation`, `RunResult.failure`, `gap` and `explain`.

### 4.13 Worked entries and their renderings

The numbers are **illustrative**: FB-05's 2627 and 2585 kJ/kg converted with M = 18.015 g/mol, on an assumed molar
basis. The corpus pins the computed values and the basis. The ids are those of FB-03: `rev-000005`, `job-000004`, S4 =
`connections[3]`.

#### 4.13.1 `phase_regime_mismatch` (plus the two entries that frame it)

```yaml
- code: phase_regime_mismatch
  family: refusal
  kind: input
  complete: true
  title: Declared phase does not match the computed state
  args: [stream]
  params:
    stream:           {type: stream, label: stream}
    unit:             {type: unit, optional: true}
    declared:         {type: enum, vocabulary: phase_capability, optional: true, label: declared phase}
    landed:           {type: enum, vocabulary: phase_capability, optional: true, label: computed phase}
    vapour_fraction:  {type: number, optional: true, label: vapour fraction}
    property:         {type: enum, vocabulary: state_property, optional: true}
    value:            {type: quantity, optional: true, label: computed value}
    saturated_liquid: {type: quantity, optional: true, label: saturated-liquid value}
    saturated_vapour: {type: quantity, optional: true, label: saturated-vapour value}
    pressure:         {type: quantity, optional: true, label: pressure}
  summary: "Stream {stream} is not in its declared phase[: it is declared {declared}, but at these conditions it is {landed}]."
  where: "stream {stream}[, an outlet of unit {unit}[ ({unit_model})]]"
  why: "Each stream carries a declared phase, and a unit computes its outlet only in that phase."
  action: "Change the phase declared for {stream} to the one that matches the computed state."
  variants:
    - when: {equals: {landed: vapor}, has: [property, value, saturated_vapour, pressure]}
      why: "At {pressure} the {property} of {stream} is {value}, above the saturated-vapour value {saturated_vapour}, so the stream is vapour, not {declared}."
    - when: {equals: {landed: liquid}, has: [property, value, saturated_liquid, pressure]}
      why: "At {pressure} the {property} of {stream} is {value}, below the saturated-liquid value {saturated_liquid}, so the stream is liquid, not {declared}."
    - when: {equals: {landed: vapor_liquid}, has: [property, value, saturated_liquid, saturated_vapour, pressure]}
      why: "At {pressure} the {property} of {stream} is {value}, between the saturated-liquid value {saturated_liquid} and the saturated-vapour value {saturated_vapour}[ (vapour fraction {vapour_fraction})], so the stream is wet, not {declared}."
    - when: {has: [landed]}
      action: "Declare {stream} as {landed}[: set {stream_path}.phase_capability to \"{landed!raw}\"]. If you expected {declared}, check the specifications that set the conditions upstream of {stream}."
  see_also: [isentropic_state_two_phase, L-TH-3]
  examples:
    - chain: [INITIALIZATION_FAILED, initializer_failed, phase_regime_mismatch]
      params: {stream: S4, unit: T, declared: vapor_liquid, landed: vapor, property: h,
               value: {value: 47330.0, unit: J/mol, kind: molar_enthalpy},
               saturated_vapour: {value: 46570.0, unit: J/mol, kind: molar_enthalpy},
               pressure: {value: 10000.0, unit: Pa, kind: pressure}}

- code: INITIALIZATION_FAILED
  family: outcome
  kind: numerical
  complete: true
  title: The solve could not find a starting point
  params: {unit: {type: unit, optional: true}}
  context: "The solve[ of revision {revision}] stopped before its first iteration[: unit {unit}[ ({unit_model})] could not compute its outlets from the starting values]."
  summary: "The solve[ of revision {revision}] could not find a starting point[ at unit {unit}]."
  why: "Before iterating, OpenFlowsheet computes every unit once, in flow order, from the feeds and the specifications. One unit could not, so there was no starting point."
  action: "Check the specifications of the unit named; if they are right, supply an initial guess for the recycle streams."

- code: initializer_failed
  family: refusal
  kind: numerical
  complete: true
  title: The first pass over the flowsheet stopped at a unit
  args: [unit]
  params: {unit: {type: element, label: unit}}
  summary: "The first pass over the flowsheet could not compute every unit[ (it stopped at {unit})]."
  why: "Before iterating, OpenFlowsheet computes every unit once, in flow order; this pass stopped."
  action: "Read the cause; if none is given, supply an initial guess for the recycle streams."
```

`vocabulary.yaml` excerpt:
- `phase_capability`: `liquid` → "liquid", `vapor` → "vapour", `vapor_liquid` → "wet (vapour + liquid)";
- `state_property`: `h` → "enthalpy", `s` → "entropy".

Note that `initializer_failed`'s param is typed `element`, not `unit`. The legacy tear path puts the initializer id
there (`tear.py:681`), so the typed `unit` comes from the diagnosis or the revision lookup only. The renderer upgrades
an `element` to `unit` when the revision has a unit with that id, which also gives `unit_model`.

**Python** (FB-03's repro, after WO-5 and WO-6):

```
>>> run = app.solve(rev, "default"); run.raise_for_outcome()
SolveFailedError: The solve of revision 'rev-000005' stopped before its first iteration: unit 'T' (thermal.turbine) could not compute its outlets from the starting values.
  Cause:   Stream 'S4' is not in its declared phase: it is declared wet (vapour + liquid), but at these conditions it is vapour.
  Why:     At 10000 Pa the enthalpy of 'S4' is 47330 J/mol, above the saturated-vapour value 46570 J/mol, so the stream is vapour, not wet (vapour + liquid).
  Do:      Declare 'S4' as vapour: set connections[3].phase_capability to "vapor". If you expected wet (vapour + liquid), check the specifications that set the conditions upstream of 'S4'.
  Kind:    Input problem: something in the flowsheet or the request needs to change.
  Code:    phase_regime_mismatch, in INITIALIZATION_FAILED → initializer_failed (openflowsheet explain phase_regime_mismatch)
  Docs:    https://computational-chemical-engineering.github.io/openflowsheet/messages/refusals/#phase_regime_mismatch
  Details: initializer_failed(T): phase_regime_mismatch(S4) — job-000004:bundle/failure-bundle.json
```

**HTTP and MCP.** The run result's `failure` member is the same document on both transports. Over HTTP it arrives in
the 200 body of the operation that returns the run result. Over MCP it is the `structuredContent` of the job-result
tool, with `isError` false: it is a domain result.

```json
"failure": {
  "outcome": "INITIALIZATION_FAILED",
  "taxonomy": "initialization and recycle failures",
  "message": "initializer_failed(T): phase_regime_mismatch(S4)",
  "code": "phase_regime_mismatch",
  "chain": ["INITIALIZATION_FAILED", "initializer_failed", "phase_regime_mismatch"],
  "implicated": ["T"],
  "suggested_actions": ["supply_initial_guess"],
  "failure_bundle": "job-000004:bundle/failure-bundle.json",
  "params": {"stream": "S4", "unit": "T", "declared": "vapor_liquid", "landed": "vapor", "property": "h",
             "value": {"value": 47330.0, "unit": "J/mol", "kind": "molar_enthalpy"}, "...": "..."},
  "explanation": {
    "code": "phase_regime_mismatch", "family": "refusal", "kind": "input", "complete": true,
    "summary": "The solve of revision 'rev-000005' stopped before its first iteration: unit 'T' (thermal.turbine) could not compute its outlets from the starting values.",
    "cause": "Stream 'S4' is not in its declared phase: it is declared wet (vapour + liquid), but at these conditions it is vapour.",
    "where": "stream 'S4', an outlet of unit 'T' (thermal.turbine)",
    "why": "At 10000 Pa the enthalpy of 'S4' is 47330 J/mol, above the saturated-vapour value 46570 J/mol, so the stream is vapour, not wet (vapour + liquid).",
    "action": "Declare 'S4' as vapour: set connections[3].phase_capability to \"vapor\". If you expected ...",
    "hint": null,
    "elements": [{"type": "unit", "id": "T", "path": ["instances", 2]}, {"type": "stream", "id": "S4", "path": ["connections", 3]}],
    "numbers": [{"name": "value", "label": "computed value", "value": 47330.0, "unit": "J/mol", "kind": "molar_enthalpy"},
                {"name": "saturated_vapour", "label": "saturated-vapour value", "value": 46570.0, "unit": "J/mol", "kind": "molar_enthalpy"},
                {"name": "pressure", "label": "pressure", "value": 10000.0, "unit": "Pa", "kind": "pressure"}],
    "gap": null,
    "chain": ["INITIALIZATION_FAILED", "initializer_failed", "phase_regime_mismatch"],
    "docs": "https://computational-chemical-engineering.github.io/openflowsheet/messages/refusals/#phase_regime_mismatch"
  }
}
```

The `implicated` value and the instance index 2 are illustrative.

**CLI.** `openflowsheet api <the solve operation> … --project plant` prints the run result document on stdout and
exits 0. Stderr carries the Python text above without the `SolveFailedError: ` prefix.

#### 4.13.2 `isentropic_state_two_phase` (FB-05 case 2; L-TH-4)

```yaml
- code: isentropic_state_two_phase
  family: refusal
  kind: not_supported
  complete: true
  title: A turbine whose ideal outlet would be wet while its outlet is declared vapour
  args: [unit]
  params:
    unit:        {type: unit}
    outlet:      {type: stream, optional: true}
    phase:       {type: enum, vocabulary: phase, optional: true}
    s_star:      {type: quantity, optional: true, label: ideal (isentropic) outlet entropy}
    s_saturated: {type: quantity, optional: true, label: saturated-vapour entropy}
    pressure:    {type: quantity, optional: true, label: outlet pressure}
  summary: "Unit {unit} needs a case this version does not support: its outlet[ {outlet}] is declared vapour, but its ideal (isentropic) outlet state would be wet."
  why: "This version computes a turbine's ideal outlet in the phase declared for the real outlet.[ Here the ideal outlet entropy {s_star} is below the saturated-vapour entropy {s_saturated} at {pressure}, so the ideal state is two-phase.] This is a limitation of the software (L-TH-4), not an error in your flowsheet."
  action: "Re-declare the outlet[ {outlet}] as wet (\"vapor_liquid\") if it can be wet at your conditions. If that is refused as a phase mismatch, change the operating conditions (for example the turbine inlet temperature or outlet pressure) until the ideal and the real outlet are in the same phase. Support for this case is planned (the std.turbine model)."
  gap: {limitation: L-TH-4, capability: "a vapour turbine outlet with a two-phase isentropic reference"}
  see_also: [phase_regime_mismatch, L-TH-4]
  examples:
    - chain: [INITIALIZATION_FAILED, initializer_failed, isentropic_state_two_phase]
      params: {unit: T, outlet: S4, phase: VAPOR,
               s_star: {value: 140.2, unit: J/(mol*K), kind: molar_entropy},
               s_saturated: {value: 146.3, unit: J/(mol*K), kind: molar_entropy},
               pressure: {value: 10000.0, unit: Pa, kind: pressure}}
```

The action text is a physical claim with no test, so the reviewer judges it (§8 Q4).

Python text, abbreviated:
```
SolveFailedError: The solve of revision 'rev-000006' stopped before its first iteration: unit 'T' (thermal.turbine) could not compute its outlets from the starting values.
  Cause:   Unit 'T' needs a case this version does not support: its outlet 'S4' is declared vapour, but its ideal (isentropic) outlet state would be wet.
  Why:     This version computes a turbine's ideal outlet in the phase declared for the real outlet. Here the ideal outlet entropy 140.2 J/(mol*K) is below ... This is a limitation of the software (L-TH-4), not an error in your flowsheet.
  Do:      Re-declare the outlet 'S4' as wet ("vapor_liquid") if it can be wet at your conditions. ...
  Kind:    Not supported in this version: a limitation of OpenFlowsheet, not an error in your flowsheet.
  Code:    isentropic_state_two_phase, in INITIALIZATION_FAILED → initializer_failed (openflowsheet explain isentropic_state_two_phase)
  Docs:    https://computational-chemical-engineering.github.io/openflowsheet/messages/refusals/#isentropic_state_two_phase
  Details: initializer_failed(T): isentropic_state_two_phase(T) — job-000005:bundle/failure-bundle.json
```

HTTP and MCP carry the same `failure` document shape as 4.13.1, with `"kind": "not_supported"` and
`"gap": {"limitation": "L-TH-4", "capability": "a vapour turbine outlet with a two-phase isentropic reference"}`.

#### 4.13.3 `not_found` (FB-03b)

```yaml
- code: not_found
  family: api_error
  kind: input
  complete: true
  title: The named object does not exist in this project
  params:
    artifact_id: {type: artifact, optional: true}
    revision_id: {type: revision, optional: true}
    job_id:      {type: job, optional: true}
    bundle_id:   {type: bundle, optional: true}
    member:      {type: text, optional: true}
    members:     {type: list, optional: true}
    run_outcome: {type: code, optional: true}
    code:        {type: text, optional: true}
    suggestions: {type: list, optional: true}
  summary: "Nothing named[ {artifact_id}][ {revision_id}][ {job_id}] exists in this project."
  why: "The id is not one this project has recorded."
  action: "Check the id; a job's outputs list the artifact ids it wrote."
  variants:
    - when: {has: [bundle_id, member, members, run_outcome], not_equals: {run_outcome: CONVERGED}}
      summary: "Bundle {bundle_id} has no file '{member!raw}': its run ended {run_outcome} and wrote no solution."
      why: "A run that does not converge writes a failure bundle instead of a solution state and a certificate. This bundle holds {members}."
      action: "Check the run's outcome before reading its results; the run result's failure says why it failed[, and '{bundle_id!raw}/failure-bundle.json' holds the evidence]."
    - when: {has: [bundle_id, member, members]}
      summary: "Bundle {bundle_id} has no file '{member!raw}'."
      why: "This bundle holds {members}."
      action: "Read one of the files the bundle holds."
    - when: {has: [code]}
      summary: "There is no message code '{code!raw}'."
      why: "Codes are case-sensitive and listed in the docs' Messages section."
      action: "[Did you mean {suggestions}?]"
  examples:
    - params: {artifact_id: "job-000004:bundle/solution-state.json", bundle_id: "job-000004:bundle",
               member: solution-state.json, members: [failure-bundle.json, run-manifest.json],
               run_outcome: INITIALIZATION_FAILED, job_id: job-000004}
```

The `members` list renders its items as text, unquoted, joined by `, `. `bundle_id` is an element, so it renders
quoted.

**HTTP**: `GET /v1/artifacts/job-000004%3Abundle%2Fsolution-state.json/raw` → **404**:
```json
{"code":"not_found","message":"no such artifact","retryable":false,
 "detail":{"operation":"artifact_bytes","artifact_id":"job-000004:bundle/solution-state.json",
   "bundle_id":"job-000004:bundle","member":"solution-state.json",
   "members":["failure-bundle.json","run-manifest.json"],"job_id":"job-000004","run_outcome":"INITIALIZATION_FAILED",
   "explanation":{"code":"not_found","family":"api_error","kind":"input","complete":true,
     "summary":"Bundle 'job-000004:bundle' has no file 'solution-state.json': its run ended INITIALIZATION_FAILED and wrote no solution.",
     "cause":null,"where":null,
     "why":"A run that does not converge writes a failure bundle instead of a solution state and a certificate. This bundle holds failure-bundle.json, run-manifest.json.",
     "action":"Check the run's outcome before reading its results; the run result's failure says why it failed, and 'job-000004:bundle/failure-bundle.json' holds the evidence.",
     "hint":null,"elements":[{"type":"artifact","id":"job-000004:bundle/solution-state.json","path":null},
       {"type":"bundle","id":"job-000004:bundle","path":null},{"type":"job","id":"job-000004","path":null}],
     "numbers":[],"gap":null,"chain":["not_found"],
     "docs":"https://computational-chemical-engineering.github.io/openflowsheet/messages/api-errors/#not_found"}}}
```

**MCP**: `artifact_bytes` has no MCP tool. The same refusal arrives from `get_artifact` (same `_artifact_row`) as
`isError: true`, with `structuredContent` = the document above (`operation` is `get_artifact`).

**CLI** (`openflowsheet api artifact_bytes …`): stdout is the document; stderr is the layered text; exit **6**.

**Python** (direct call): `ApplicationError: Bundle 'job-000004:bundle' has no file …`, then the layered lines,
ending `Details: not_found: no such artifact`.

#### 4.13.4 FB-01: `project_exists` and `directory_not_empty`

```yaml
- code: project_exists
  family: refusal
  kind: input
  complete: true
  title: The directory already holds a project
  params: {directory: {type: directory}}
  summary: "Directory {directory} is not empty: it already holds a project, and create() needs a new or empty directory."
  why: "create() makes a new project and never reuses a directory, so a re-run cannot overwrite work silently."
  action: "To use the existing project, open it instead."
  variants:
    - when: {surface: [python]}
      action: "To use the existing project, call LocalApplication.open(\"{directory!raw}\"), or call LocalApplication.create(\"{directory!raw}\", exist_ok=True), which opens it."
    - when: {surface: [cli]}
      summary: "Directory {directory} is not empty: it already holds a project, and project init needs a new or empty directory."
      action: "The project is ready to use: pass --project {directory!raw} to other commands, or run project init with --exist-ok."
  examples: [{params: {directory: plant}}]

- code: directory_not_empty
  family: refusal
  kind: input
  complete: true
  title: The directory holds files that are not a project
  params: {directory: {type: directory}}
  summary: "Directory {directory} is not empty and does not hold a project; a project needs a new or empty directory."
  why: "OpenFlowsheet will not mix a project with other files, and exist_ok=True opens only an existing project."
  action: "Choose a new directory name, or empty this directory first."
  examples: [{params: {directory: notes}}]
```

Python, on the second run of the old quickstart:
```
StoreError: Directory 'plant' is not empty: it already holds a project, and create() needs a new or empty directory.
  Why:     create() makes a new project and never reuses a directory, so a re-run cannot overwrite work silently.
  Do:      To use the existing project, call LocalApplication.open("plant"), or call LocalApplication.create("plant", exist_ok=True), which opens it.
  Kind:    Input problem: something in the flowsheet or the request needs to change.
  Code:    project_exists (openflowsheet explain project_exists)
  Docs:    https://computational-chemical-engineering.github.io/openflowsheet/messages/refusals/#project_exists
  Details: project_exists: plant
```

The CLI (`openflowsheet project init plant`, run twice) prints the `surface: cli` variant on stderr and exits **2**.
HTTP and MCP have no `create`, so these codes never travel there.

---

## 5. Identity analysis

| Object | May it move? | Why it does not / how it is proved |
| --- | --- | --- |
| Bundle members (events, failure bundle, certificate, run manifest, solution state, solve path); member set | **No** | No producer text changes (I1). `diagnostic` fields are compare/hash/repr False and never serialized. No member is added. MSG-G0(b). |
| Revision content hashes | **No** | No document format or canonicalization is touched. Existing tests. |
| `structural_sha256`, `r0_sha256`, run fingerprints | **No** | Derived from unchanged artifacts. MSG-G0(b). |
| Certificates, `certificate_id` | **No** | As above. |
| Property and other cache keys | **No** | Exact caches key on canonical inputs. The new fields are excluded from `__eq__`/`__hash__`. A test asserts `dataclasses.fields` flags on every carrier. |
| K05 identity document and `t07` key | **No** | The script reads unchanged fields only (`scripts/t07_identity.py:24-25`, `:137`, `:227-240`, `:283`). `tests/test_t07_identity.py`'s registered hashes. |
| Replay of released 0.3.0 bundles | **No** | Verdict `MATCH`, and `bitwise_floats` as recorded before MSG. MSG-G0(c). |
| Machine `ApiError.message` and existing `detail` members | **No** | I1. Only *new* detail members are added (FB-03's on `not_found`; `suggestions` on `explain`'s `not_found`). |
| Job store schema id `t07-store-v1` | **No** | `worker_result.run` gains `diagnosis` inside the JSON blob (precedent: `study`). |
| Projected error documents (all transports) | **Yes, additively** | Gain `detail.explanation`. About 33 exact-`detail` assertions change to compare `detail` without `explanation` (WO-3 lists them). Persisted nowhere (MSG-G0(d)). |
| `RunResult` document | **Yes, additively** | Gains `failure` (ADR 0058). |
| Served MCP tool list digest | **Yes** | It moves by exactly two causes: the `explain` tool, and `failure` in any `outputSchema` that `$ref`s run-result. With both removed it equals the pre-MSG digest (MSG-G10). |
| R4-G3 response-schema snapshots | **Yes** | For operations whose response contains a `RunResult`, and for the new `explain`. With `failure` removed they equal the pre-MSG snapshots (MSG-G10). |
| CLI golden file | **Yes, in 2–3 named records** | §3.7. Exit codes are unchanged. |
| `str(ApplicationError)`, coded `str(StoreError)` | **Yes** | Layered text. The last line is the old string, so unanchored matches hold. Anchored ones are updated and listed (WO-3, WO-4). |

---

## 6. Work orders

Each work order is one branch-local commit series on `wp/MSG` and is about 150k context or less. **Identity** says
whether MSG-G0 must be run before the work order counts as done. *(S)* marks work a `sonnet-implementer` may take from
this note.

**WO-0 — Baseline (identity: records it).** Before any MSG code, at the branch point:
- write `scripts/msg_identity_gate.py`, with `--record evidence/MSG/<base>/identity-baseline.json` and `--check <file>`;
- it prints one summary line, and its log goes to a file;
- record the four parts of MSG-G0 and the pre-MSG MCP digest and R4-G3 snapshots.

*Accept:* `--check` against its own baseline prints `MSG-G0 PASS`, and against a deliberately altered member prints
FAIL (a control).

**WO-1 — The engine (identity: no).**
- *Files:* `src/openflowsheet/messages/{__init__,diagnostic,catalogue,legacy,render,text,audit}.py`;
  `catalogue/{kinds,vocabulary}.yaml`; the entries of §4.13 plus `INITIALIZATION_FAILED`, `initializer_failed` and
  `L-TH-4`; `schemas/message-catalogue.schema.json`; `schemas/registry.json`; pyproject package-data;
  `tests/test_msg_engine.py`.
- *Accept:*
  - §4.3's 12 parse examples;
  - §4.13's four entries render exactly the texts printed there from the stated params (Python surface for the text
    format; surface null for documents);
  - the §4.5 number-format examples;
  - G4 lint;
  - totality: every entry × (its examples, empty params, a random 3-code chain over all keys; 500 draws, fixed seed)
    never raises with audit off;
  - `register()`'s four refusals (§4.11);
  - mypy, ruff.

**WO-2 — Coverage: G1, G2, G3 and stubs (identity: yes; hooks in `verify/failure.py`, `contract.py`, `binding.py`).**
- *Files:* `scripts/msg_catalogue.py` (`scan`, `sync-limitations`, `freeze`, `check`); the remaining
  `catalogue/*.yaml` stubs *(S, from the scan output plus §4.2.1's rule table; one-sentence summaries written from the
  emission site)*; `scan-allow.yaml`; `released-codes.txt`; the four audit hooks; `tests/conftest.py` plugin;
  `tests/test_msg_coverage.py`.
- *Accept:*
  - G1 and G2 pass;
  - the full suite with the audit has zero misses;
  - `sync-limitations --check` is clean;
  - the count of `review: true` is printed;
  - MSG-G0 PASS.

**WO-3 — `ApiError` explanations on every surface, plus FB-03(b) (identity: yes).**
- *Files:* `application/types.py` (`ApiError.explanation`); `application/contract.py` (`__str__`, `explanation`);
  `application/operations.py` (`project_error`, nested attach); `bindings/http.py` and `bindings/mcp.py` (every error
  exit projected); `application/cli.py` (stderr text, the top-level handler, `validate` lines); `application/local.py`
  (`_artifact_row`); `application/store.py` (the members query); tests; the golden file's named records re-taken.
- *Accept:*
  - the conformance suite is green, and each new refusal's document is equal across the four transports;
  - the schema-walk test of §4.7;
  - the `str()`-conversion grep finds no new site;
  - a test with an injected defect on each transport yields an `internal_error` document with a `bug`-kind
    explanation;
  - the golden diff touches only §3.7's records;
  - MSG-G0 PASS (including (d)).

**WO-4 — FB-01 (identity: no).**
- *Files:* `application/store.py`, `application/local.py`, `application/cli.py` (`--exist-ok`); `README.md`;
  `tests/test_readme_current.py`; `tests/test_t07_store.py`; the golden file's `project init` record.
- *Accept:*
  - §3.8's matrix, 5 states × 2 `exist_ok` values, gives exactly the stated outcomes and codes;
  - `ProjectStore.open` on a non-project raises `not_a_project`;
  - MSG-G9.

**WO-5 — The diagnostic sidecar (identity: yes, critical).**
- *Files:* `models/thermal/{kernel,machines,valve,heater,flash,mixer}.py`; `models/__init__.py`;
  `models/revision_flowsheet.py`; `orchestrator/{revision,executor}.py`; the path to `application/revision_run.py`
  and `application/jobs/runner.py`.
- *Accept:*
  - MSG-G0 PASS on x86-64, and CI identity green on aarch64;
  - every new field has `compare=False, hash=False, repr=False` (a reflective test);
  - no artifact, event or bundle document anywhere in the suite contains the key `diagnostic` or `diagnosis` (a test
    scans the bundles the suite writes);
  - corpus cases C01 and C02 store a `run.diagnosis` whose code equals the chain's inner code, and in which:
    - `pressure` equals the declared outlet-pressure specification exactly;
    - `saturated_vapour` equals the provider's saturated-vapour value at that pressure from an independent provider
      call, to relative 1e-12;
    - `value > saturated_vapour` for C01, and `s_star < s_saturated` for C02;
    - units and kinds are as the producer states, after the engineer has confirmed the basis.

**WO-6 — `RunResult.failure` (identity: no artifacts; schema yes, per ADR 0058).**
- *Files:* `application/types.py` (`RunFailure`, `RunResult.failure`, `raise_for_outcome`, `SolveFailedError`);
  `application/local.py` (`_run_result`); `schemas/run-result.schema.json`; `schemas/application-results.schema.json`
  (`$defs/explanation`); `scripts/t07_schema_fixtures.py` and the fixtures; the R4-G3 and MCP-digest tests; CLI
  `solve`/`inspect`/`api`; the README outcome check; `docs-site/api/*`.
- *Accept:*
  - FB-03's repro gives `run.failure.code == "phase_regime_mismatch"`, with elements ⊇ {T, S4};
  - `raise_for_outcome` raises `SolveFailedError`, whose first line equals the explanation summary;
  - the converse test over every solve in the suite (an autouse fixture wrapping `_run_result` in `tests/conftest.py`):
    failure non-null iff a `failure_bundle` output exists;
  - a 0.3-shaped job (no `diagnosis`) still yields `failure`, without numbers;
  - MSG-G10.

**WO-7 — The `explain` operation (identity: no; schema yes).**
- *Files:* `application/contract.py` (`Inspection.explain`); `application/local.py`; `application/operations.py`;
  `bindings/descriptions/explain.md`; `application/cli.py` (the `explain` command);
  `application-results.schema.json` (`$defs/message_entry`) and fixtures; `docs/interfaces-frozen.md` (an ADR 0058
  paragraph).
- *Accept:*
  - for every catalogue key, `explain` returns a schema-valid document, equal across the four transports;
  - `explain("phase_regim_mismatch")` → `not_found` with `suggestions[0] == "phase_regime_mismatch"`;
  - CLI exits 0 and 6;
  - MSG-G10.

**WO-8 — Docs pages (identity: no) *(S)*.**
- *Files:* `scripts/doc_pages.py`; `docs-site/messages/*.md`; `mkdocs.yml`; `docs-site/guide/limitations.md`;
  `docs-site/agents.md`.
- *Accept:* MSG-G5, and every `docs` URL the corpus produces resolves to a generated anchor (a test).

**WO-9 — The corpus and the complete entries (identity: no).**
- *Files:* `tests/fixtures/msg/corpus.yaml`; `tests/test_msg_corpus.py`; complete entries for every corpus code
  (prose *(S)* drafts, Opus checks).
- *Accept:* MSG-G6 on both CI architectures; G4 on all complete entries.

**WO-10 — Web shell display (identity: no) *(S)*.**
- *Files:* the web shell's error and outcome display.
- *Accept:* the existing web-shell tests, plus one test that a refused request shows `explanation.summary` and
  `action`, and one that a failed run shows `failure.explanation.summary`.

**Order:** WO-0 → WO-1 → WO-2 → {WO-3, WO-4} → WO-6 → WO-7 → WO-5 → WO-8 → WO-9 → WO-10. Then the full gate
(`scripts/gate.sh`), the manifest and the single `reviewer` pass. WO-5 is placed late on purpose: everything else ships
without numbers, and its identity proof stands alone.

---

## 7. Verification gates

| Gate | Invariant | How measured | Pass |
| --- | --- | --- | --- |
| **MSG-G0** identity | I2, I3 | `scripts/msg_identity_gate.py --check` against WO-0's baseline. **(a)** `scripts/t07_identity.py` document SHA-256. **(b)** SHA-256 of every member of every bundle written by the RC set (`tests/test_t08_w4_rc.py`'s cases) and by corpus C01, C02 and C03, keyed by case and member name. **(c)** `replay --rerun` of each 0.3.0 release bundle and each registered replay fixture: verdict and `bitwise_floats`. **(d)** after the full suite: zero occurrences of the key `explanation` in the `worker_result`, ledger and audit tables of every store the suite leaves (SQL scan). | (a), (b), (c) identical to the baseline; (d) zero. x86-64 locally; CI `identity` job on aarch64. After F0 lands, F0 replaces (a)–(c). |
| **MSG-G1** closed vocabularies | C3 | `tests/test_msg_coverage.py` | Every member listed in §3.2 has an entry; `released-codes.txt` ⊆ keys. |
| **MSG-G2** static scan | C3 | `scripts/msg_catalogue.py scan` (run as a test) | 0 codes without an entry or an allow-list reason. |
| **MSG-G3** runtime audit | C3 | conftest plugin over the default suite | 0 misses. |
| **MSG-G4** lint | §4.2.7, I8 | `tests/test_msg_engine.py` | 0 violations; summaries ≤ 200 characters. |
| **MSG-G5** generated files | docs current | `doc_pages.py --check`, `msg_catalogue.py sync-limitations --check` | Clean. |
| **MSG-G6** corpus | FB-05 principle 9 | `tests/test_msg_corpus.py`, cases C01–C12 below | All assertions of §3.6 hold on every applicable surface. |
| **MSG-G7** CLI golden | §3.7 | `tests/test_t07_w5b_cli.py` | Only the named records differ (diff reviewed); all 17 exit codes unchanged. |
| **MSG-G8** conformance | one envelope | `tests/test_t07_conformance.py` and the corpus's transported cases | Documents equal across Python (dispatched), CLI, HTTP and MCP, `detail.explanation` included. |
| **MSG-G9** README | FB-01 | Execute the README Python block twice in one temp directory, with the change set copied there | Both runs succeed with `CONVERGED VERIFIED`. The second opens the existing project (no new store). |
| **MSG-G10** frozen-surface deltas | ADR 0058 | R4-G3 snapshot test; `tests/test_t08_w2_surface_digest.py` | With `failure` and the `explain` row removed, every snapshot and the MCP digest equal the pre-MSG values; the new values are recorded in the test and in ADR 0058. |
| **Performance** | no regression | `pytest --durations` before and after on the solve-heavy tests; a micro-benchmark | Cold catalogue load ≤ 200 ms; one render ≤ 1 ms (median of 1000); no solve test slower by more than its run-to-run noise (3 repeats). The sidecar is built only on refusal paths. |

**Corpus cases (MSG-G6).** All start from the README Rankine change set unless stated. "Expected code" is what must be
emitted; for C06–C09, WO-9 first records the actually emitted code (§3.6).

| Id | Mistake | Expected code / kind | Asserted elements and numbers | Surfaces |
| --- | --- | --- | --- | --- |
| C01 | boiler T 973.15 K (FB-03 repro) | `phase_regime_mismatch` / input | S4, T; `value`, `saturated_vapour`, `pressure` | Python, CLI, HTTP, MCP |
| C02 | C01 with S4 declared vapour (FB-05 case 2) | `isentropic_state_two_phase` / not_supported; `gap.limitation` L-TH-4 | T (S4 if known); `s_star`, `s_saturated`, `pressure` | all four |
| C03 | read `solution-state.json` after C01 | `not_found` / input; `members`, `run_outcome` | the bundle, the job | all four (MCP via `get_artifact`) |
| C04 | run `create("plant")` twice | `project_exists` / input | directory | Python, CLI |
| C05 | `create(dir, exist_ok=True)` on a non-project directory | `directory_not_empty` / input | directory | Python, CLI |
| C06 | over-specification (one more spec on a fixed unit) | as emitted / input | the implicated ids | all four |
| C07 | under-specification (remove one required spec) | as emitted / input | the implicated ids | all four |
| C08 | unit typo in a spec (`"degc"`) | as emitted / input | the bad unit text in the summary | all four |
| C09 | feed temperature outside the provider's range | `out_of_domain` (or as emitted) / input | T and the bounds, if `detail_pattern` extracts them | all four |
| C10 | unknown model id on an instance | `model_unsupported` / not_supported; `gap.capability` | the instance | all four |
| C11 | turbine outlet pressure above its inlet | `pressure_rise` / input | T; `p_spec`, `p_inlet` | all four |
| C12 | `validate --task optimization` without an audited NLP solver (the probe forced unavailable in the test) | `nlp_solver_unavailable` / not_supported; `gap.limitation` L-OPT-1 | — (`optimise` in the summary; action token `nlp`) | all four |

*C12 amended 2026-11-09 (ADR 0071 R-968; ruling docs/reviews/MSG-catalogue-X02-OPT.md): was `task_unsupported`.*

---

## 8. Risks and open questions

Each item says whether it needs a **fact** or the **user's preference**, and gives a default that lets work proceed.

- **Q1. Approval of ADR 0058** — *preference (Frank)*. ADR 0019 Amendment 3, which added `list_audit` the same way,
  was approved by Frank. *Default:* build WO-0 to WO-10 on `wp/MSG`, and merge to `main` only after ADR 0058 is
  Accepted.
- **Q2. Is the riskiest step inert?** — *fact.* WO-5 adds fields to five solver-path dataclasses. If any of them is
  serialized generically (`asdict`, a `__dict__` dump, `repr` into a document), the sidecar leaks into an artifact and
  breaks I3. *Default:* MSG-G0 decides. On any difference, the field is excluded at that serializer, never by changing
  the artifact. WO-5 is ordered last so that all other work stands without it.
- **Q3. `str()` override safety** — *fact*: does some path turn an `ApplicationError` or coded `StoreError` into a
  stored or transported string through `str()`? The recon found only other exception classes (§4.7). *Default:*
  WO-3's grep plus MSG-G0(a)/(d). If the measured risk is real, fall back to PEP 678 notes
  (`exc.add_note(text)`; `str()` unchanged). The human line then becomes line 2 instead of line 1.
- **Q4. Physical advice in prose** — *fact (review)*. The L-TH-4 action and the `phase_regime_mismatch` "upstream"
  advice are claims no test checks. *Default:* the texts of §4.13, judged in the reviewer pass. A wrong claim is fixed
  in the YAML, which touches no identity.
- **Q5. Certificate-status meanings on `RunResult`** — *preference*. FB-05 principle 8 asks for them. 0.4 delivers
  them through `explain`, the CLI `note` line and the docs. A `RunResult.notices` member would be another frozen-schema
  change. *Default:* none in 0.4; revisit with ST.
- **Q6. Numbers on a molar basis** — *preference (settled by MSG-before-X04)*. A student sees J/mol and Pa until X04.
  *Default:* SI as produced. X04 fills `display_units`.
- **Q7. Validate's text output gains lines** — *preference*. It changes the `broken.yaml` golden record if its checks
  have complete entries. *Default:* yes, with the golden re-taken and the reason stated in the commit.
- **Q8. Corpus codes C06–C09** — *fact*. The exact codes are measured in WO-9. If a code is unspecific, the default is
  to record it as found, report it in the build-decisions log and leave the machine message alone (I1).
- **Q9. README re-run** — *fact*. MSG-G9 assumes `commit_change` with the change set's idempotency key is idempotent
  across the two runs (§5.1). *Default:* if it is not, stop and report it as a contract defect; do not work around it in
  the README.
- **Q10. About 300 stub kinds** — *fact (review)*. *Default:* §4.2.1's rule, with `review: true` on judgment calls,
  which the reviewer checks by sample (all `bug` and all `not_supported` stubs, and 20 others).
- **Q11. The MCP description of `explain`** — *fact (review)*. An MCP tool needs a reviewed description (W6c).
  *Default:* reviewed in the package's reviewer pass; if the review is deferred, ship `explain` without MCP and record
  the gap.
- **Q12. Released 0.3.0 bundles available locally** — *fact*. *Default:* use the release evidence bundles and the
  registered replay fixtures that exist in the repository. If none of the 0.3.0 release bundles is present, regenerate
  the RC set at tag `v0.3.0` in a worktree, record it as the replay baseline, and say so in the manifest.

---

## 9. Build choices left to the engineer

These do not change behaviour as specified, so the engineer chooses them and logs the choices in
`docs/design/MSG-build-decisions.md`:
- the module split inside `messages/`, and the YAML file split per family;
- the SQL of the bundle-members query;
- the exact hop-by-hop route of `diagnostic` from `StepResult` to `WorkerResult.run`, within §4.6's carrier rule;
- the AST-scanner implementation and the allow-list entries, each with its reason;
- stub summary wording;
- test file names beyond those named;
- the `--msg-update` mechanics;
- the Levenshtein implementation (stdlib only).

---

## 10. Proposed decision-register entries (for the orchestrator, on acceptance)

1. Human text is rendered on read from a catalogue and never stored or hashed. Rejected: rewriting producer messages;
   storing both texts.
2. The failure kind travels as `detail.explanation`. Rejected: a new `ApiError` member, because of
   `additionalProperties: false` and 0.3 clients.
3. `RunResult.failure` carries a domain outcome's cause, and `error` keeps its R-095 meaning. Rejected: the cause in
   `error`; an `explain_run` operation.
4. R-159's scope is clarified: it governs machine messages, and renderings begin with the human summary.
5. Numbers travel in a diagnostic sidecar on the failure value, persisted only in `worker_result.run.diagnosis`.
   Rejected: a `ContextVar` collector; a bundle member; render-time property calls.
6. Catalogue codes are stable and the key set only grows; a `.` in a key is reserved for extension namespaces.
