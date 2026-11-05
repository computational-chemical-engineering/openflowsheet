# ADR 0058 — Messages: a code catalogue, explanations on read, `RunResult.failure` and `explain`

**Status:** **Proposed, 2026-11-05.** It is accepted when Frank approves it (precedent: ADR 0019 Amendment 3) and MSG's
manifest is `tested` with the reviewer pass done. Until then MSG is built on `wp/MSG` and not merged.
**Author:** design lane (`architect`), MSG design pass.
**Design note:** `docs/design/MSG-messages.md`, the normative detail; section numbers below refer to it.
**Amends:**
- ADR 0019 D1 and D2, as **ADR 0019 Amendment 6**: `Inspection` gains `explain`, and `RunResult` gains `failure`. On
  acceptance a pointer paragraph is added to ADR 0019, in the form of Amendment 4.
- `docs/interfaces-frozen.md`: three new frozen result-type names, one schema added, two schemas widened additively.

**Does not amend:**
- ADR 0019 D5: the `ApiError` shape and its closed 15-code enum are unchanged, and `api-error.schema.json` is
  byte-identical.
- ADR 0025: no artifact text changes.
- ADR 0020 D8 / R-104.
- R-095.
- R-159: its scope is clarified, not changed (D2).
- `API_EXIT_CODES`.

**Builds on:** ADR 0056 Amendment 1 (MSG; FB-01, FB-03, FB-05); ADR 0057 rules C1 and C3; R-931 (the typed gap).

## Context

The tutorial user (FB-05) could not tell from OpenFlowsheet's messages *what* failed, *where*, *why* or *what to do*.
The causes:
- `RunResult.error` is `None` on a non-converged solve.
- The cause sits inside `failure-bundle.json`.
- `not_found: no such artifact` names nothing.
- A re-run `create()` reads as a report of an action (FB-01).

Rule C3 requires a catalogue entry (what, where, why, what to do, kind) for every `ApiError` code and every typed
refusal or limitation code, extensible through F1, with CI failing on an emitted code without an entry. It also makes
`explain <code>` an operation.

The machine texts cannot change:
- ADR 0025 D6 compares artifact `message`/`cause` by template, and a released bundle must still replay `MATCH`.
- The `t07` identity key holds check messages and refusal codes.
- R-159's tests match code prefixes.

The ApiError schema is `additionalProperties: false` at its top level, so a new member breaks every released client
that validates errors.

## Decision

**D1. Two layers.** The *machine layer* is unchanged: codes, `message` strings and existing `detail` members, exactly
as emitted. New machine data is additive (new `detail` members, the `RunResult.failure` member). The *human layer* is
rendered on read from a catalogue, from `(code chain, params, context)`. It is never stored in an artifact, an event,
the job store, the ledger or the audit log, and it is never an input to any hash, identity, fingerprint or cache key.
Rendering is total: it never raises in production.

**D2. Layered rendering; R-159's scope.** A rendering is:
1. a human summary in the user's element ids (what and where);
2. cause, why (with the triggering numbers in SI), what to do, and the binder hint;
3. the kind;
4. the code and its chain;
5. the docs link;
6. the machine text verbatim.

R-159 ("a refusal's message begins with its reason code") governs the machine message only. `str()` of an
`ApplicationError`, a coded `StoreError` or a `SolveFailedError` is a rendering. Its last line is the pre-0058 string,
so an unanchored match on the old text still holds.

**D3. The catalogue.** It is YAML package data validated by the new schema `schemas/message-catalogue.schema.json`,
keyed by code (note §4.2).
- Families: `api_error`, `refusal`, `outcome`, `check`, `status`, `limitation`, `notice`, `job`.
- Exactly five kinds: `input`, `not_supported`, `numerical`, `bug`, `notice`.
- Each entry has parameterised templates in the grammar of §4.2.4 (no code execution), variants, a typed `gap`
  (limitation, capability) for `not_supported` entries, and examples.
- Entries are *complete* or *stubs*. Every emitted code has at least a stub.
- The format id is `openflowsheet-messages-v1`. Its content digest is reported by `explain` and enters nothing else.
- Codes are stable: a released code is deprecated, never removed. Keys with a `.` are reserved for extension
  namespaces, and F1 registers through `messages.catalogue.register(document, namespace=…)`, which can never override
  a core key.
- CI enforces the C3 rule in three layers (note §3.2): exact enumerations of the closed vocabularies; a static scan of
  emission sites; and a runtime audit across the test suite.

**D4. Explanations on errors.** Projection (`project_error`, and `project_response` for an `ApiError` nested in a
response) adds `detail.explanation` to every transported `ApiError` document. Its shape is the new
`application-results.schema.json#/$defs/explanation`: code, family, kind, complete, summary, cause, where, why, action,
hint, elements, numbers, gap, chain and docs. `detail` is already open, so `api-error.schema.json` is unchanged and
0.3 clients accept 0.4 errors. The failure kind is `detail.explanation.kind`; it never uses `detail.kind`, which
`verification_weakening_refused` already uses. `Unbound.kind` (R-022) is unchanged beside it.

**D5. `RunResult.failure`.** `run-result.schema.json` gains the required, nullable member `failure`
(`$defs/run_failure`: outcome, taxonomy, message, code, chain, implicated, suggested_actions, failure_bundle, params,
explanation).
- It is non-null iff the job's outputs include a `failure_bundle`.
- It is derived on read from the stored failure bundle, the revision document and the optional
  `worker_result.run.diagnosis` (D6). It therefore also works on jobs a 0.3 store holds.
- A non-converged solve stays a domain result: `job_status: completed`, `error: null` (R-095).
- Python adds `RunResult.raise_for_outcome()` and `SolveFailedError`, which is not an `ApplicationError`. Neither
  crosses a transport.
- `not_found` for a missing bundle member gains the detail members `bundle_id`, `member`, `members`, `job_id` and
  `run_outcome`. Its message `"no such artifact"` is unchanged.

**D6. The diagnostic sidecar.** A producer may attach `Diagnostic(code, params)` to the failure value it already
returns. The carrier field is `compare=False, hash=False, repr=False` and is never serialized into an artifact or an
event. It is persisted only as `run["diagnosis"]` inside the job store's `worker_result` JSON blob (the store schema
stays `t07-store-v1`).
- 0.4 producers: five thermal-kernel refusals (note §4.6).
- The renderer uses a diagnosis only when its code is in the failure's parsed chain and its element ids agree with
  the chain.

**D7. `explain`.** `Inspection` gains `explain(code) -> MessageEntry`, with one `OPERATIONS` row:
- right `read`, on all four transports;
- HTTP `GET /v1/explain/{code}`;
- MCP tool `explain`, with a reviewed description;
- response `application-results.schema.json#/$defs/message_entry`;
- an unknown code is refused `not_found` with `detail.suggestions`.

The CLI also gets `openflowsheet explain <code>`, a project-free convenience command over the same function. Docs:
one generated page per family, with an anchor per code, under `docs-site/messages/`.

**D8. FB-01.** `LocalApplication.create(directory, *, project_id=None, exist_ok=False)` opens an existing project when
`exist_ok`. It refuses a non-empty non-project directory either way. `StoreError` gains keyword-only `code` and
`params`, and the codes `project_exists`, `directory_not_empty`, `not_a_directory`, `not_a_project` and
`project_id_mismatch` are refusal-family entries. These are Python and CLI only: they never become `ApiError`s.

**D9. CLI.** `API_EXIT_CODES` is unchanged. A machine document goes to stdout and its rendering to stderr. Human-text
commands append explanation lines. An uncaught exception prints the `internal_error` rendering before the traceback
and keeps exit 1.

**Frozen-list changes.**
- New frozen result-type names: `RunFailure`, `MessageEntry`, `Explanation`.
- Schema added: `message-catalogue.schema.json`, also listed in `schemas/registry.json`.
- Schemas widened additively: `run-result` (`failure`) and `application-results` (`explanation`, `message_entry`).
- The served MCP tool list moves by the `explain` tool and by `failure` wherever an `outputSchema` reaches
  run-result. With both removed it equals the pre-0058 digest. The new digest is recorded in MSG's manifest and in
  `tests/test_t08_w2_surface_digest.py`.
- R4-G3's response-schema snapshots are re-taken for the affected operations only. With `failure` removed they equal
  their previous snapshots.

## Alternatives rejected

- **Rewriting producer messages as human text.** It breaks the replay of released bundles (ADR 0025 D6), the `t07`
  key and R-159's tests, and it freezes wording into artifacts.
- **Storing both texts.** Stored prose goes stale, and floats in stored text reopen ADR 0025 D6.
- **A new top-level `ApiError` member.** `additionalProperties: false` makes every released validating client reject
  0.4 errors. It also needs a D5 change.
- **Rendering at `api_error()` creation.** It stores rendered text in job documents and breaks exact assertions on
  in-process errors.
- **The failure cause in `RunResult.error`.** It contradicts R-095, and it conflates "the job failed" with "the solve
  did not converge".
- **An `explain_run(job_id)` operation instead of a member.** It does not fail where the problem is.
- **A new bundle member for the numbers.** `run/replay.py` reports an artifact only the rerun has, so every released
  bundle would `MISMATCH`.
- **A `ContextVar` collector for the numbers.** It can attach another attempt's numbers to the reported failure.
- **A Python-dict catalogue.** F1 would register code where data suffices.
- **A static scan alone, or a runtime audit alone.** Each misses what the other catches.
- **A CLI-only `explain`.** It violates rule C1.
- **One docs page per code.** About 300 churning files, against 8 pages with anchors that give the same reachability.

## Affected requirements and migration impact

- **R-095, R-104, R-022, R-109:** held (D1, D4, D5).
- **R-159:** scope clarified (D2). Tests that anchor on the old `str(ApplicationError)` with `^` are updated, and the
  list is in the WO-3 commit.
- **ADR 0019 D1/D2:** amended (D5, D7).
- **ADR 0025:** untouched.
- **ADR 0057 C1/C3:** implemented.
- **Tests that change:**
  - about 33 exact-`detail` assertions on transported errors, which now compare `detail` without `explanation`;
  - the CLI golden records `validate <CASE> --task optimization` and the second `project init`, plus
    `validate <ROOT>/broken.yaml` only if its failing checks have complete entries;
  - the R4-G3 snapshots and the MCP digest, as above;
  - the schema fixtures, regenerated from real responses (`scripts/t07_schema_fixtures.py`).
- **Users:**
  - transported errors gain `detail.explanation`;
  - the run result gains `failure`;
  - Python exception text becomes layered;
  - the README quickstart uses `exist_ok=True` and `raise_for_outcome()`.
- **No migration of stored data.**

## Acceptance evidence

The design note's gates on `wp/MSG`, recorded in `evidence/MSG/<commit>/manifest.json`:
- **MSG-G0:** identity. Bundle bytes, the K05/`t07` document, the replay of 0.3.0 bundles, and no stored explanation.
  x86-64 locally, and aarch64 in CI.
- **MSG-G1–G4:** C3 coverage and lint.
- **MSG-G5:** generated files current.
- **MSG-G6:** the 12-case beginner corpus on every applicable transport.
- **MSG-G7:** only the named golden records change.
- **MSG-G8:** conformance across transports.
- **MSG-G9:** the README runs twice.
- **MSG-G10:** frozen-surface deltas, exactly as stated above.
- The full `scripts/gate.sh`, CI green on both architectures, and the reviewer pass.
