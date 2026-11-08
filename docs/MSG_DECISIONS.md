# MSG build decisions (append-only)

Build-lane choices for package MSG that `docs/design/MSG-messages.md` leaves open (§9 and elsewhere). Each entry:
question, options, choice, reason, commit. The note's §9 names `docs/design/MSG-build-decisions.md` for this log; the
build brief (`docs/briefs/MSG-build-WO0-2.md`) names this file, and the brief governs.

## WO-0

**D0-1. What "the RC set" of MSG-G0 (b) is.** Options: (i) `tests/test_t08_w4_rc.py`'s cases literally (they write no
bundle: the file tests `scripts/t08_rc.py`'s steps); (ii) the bundle set that `t08_rc.py bundles-write` writes (K05's
registered SYN-001 runs and T07 G8's revision bundles, release spec §8.2 step 5). **Choice: (ii)**, run as a subprocess
of the current checkout. Reason: it is the RC job's bundle set, enumerated by the RC script itself. Commit: WO-0.

**D0-2. The 0.3.0 release bundles for (c).** None is in the repository or the local caches (the RC job's bundle steps
ran in CI). Per note §8 Q12's default: `msg_identity_gate.py write-v030` writes the RC set with tag `v0.3.0`'s own
code (`b8f47a04`), in a detached `git worktree` that is removed afterwards. 52 bundles (k05 + g8), kept under
`evidence/MSG/af35153…/artifacts/v030-rc/` (ignored). The baseline records each bundle's content digest, so a changed
input shows up as a (c) difference. "Each registered replay fixture" is every committed `run-manifest.json` directory
under `tests/` (the m07a and t08 SYN-001 fixtures and the three w26 web fixtures). Commit: WO-0.

**D0-3. C01–C03 before the corpus exists.** WO-9 writes the corpus; (b) needs C01–C03 now. The gate builds them
itself from `examples/rankine-cycle.changeset.json`: C01 boiler-T 973.15 K; C02 = C01 with S4 declared `vapor`; C03
reads `solution-state.json` from C01's bundle. C03 writes no bundle, so (b) records its refusal's `code` and `message`
(I1: both must stay; `detail` may gain members by WO-4). Measured at the branch point: C01
`initializer_failed(T): phase_regime_mismatch(S4)`, C02 `initializer_failed(T): isentropic_state_two_phase(T)`, C03
`not_found: no such artifact`. Commit: WO-0.

**D0-4. (d)'s SQL.** Stricter than the note's three tables: `jobs.worker_result`, `jobs.error`, `jobs.ending`,
`events.document`, `ledger.result` and the text columns of `audit`, each `CAST(col AS TEXT) LIKE '%"explanation"%'`,
over every `project.sqlite3` under the suite's `--basetemp`. `--suite` runs the default suite itself; `--stores DIR`
scans an existing base directory. A run that finds no store fails (d), so an empty scan cannot pass. Commit: WO-0.

**D0-5. The pre-MSG surface record.** The baseline's `surface` holds the served MCP tool-list digest
(`benchmarks/t07/v17/harness.tool_descriptions_sha256`), the SHA-256 of each `OPERATIONS` row's request and response
schema (canonical JSON; the "R4-G3 snapshots"), and the SHA-256 of every `schemas/*.json`. `--check` reports
`surface same|moved` but it does not decide MSG-G0 (MSG-G10 owns it). Commit: WO-0.

**D0-6. Determinism inputs.** Every measuring subprocess runs with the three thread variables at 1 (the run manifest
records them) and `PYTHONHASHSEED=0`. Commit: WO-0.

## WO-1

**D1-1. Module split (§9).** As §4.1, plus `template.py` (the §4.2.4 grammar: parse, placeholder walk, literal and
display forms) and `lint.py` (MSG-G4), so that `catalogue.py` holds data and `render.py` holds resolution. The
`entry_document(code)` of §4.1 is left to WO-7, which defines its schema (`message_entry`). Commit: WO-1.

**D1-2. `]]` inside a segment (note defect).** §4.2.4 makes `]]` a literal, but §4.13.1's own `where` template closes
two nested segments with `]]`. Choice: `]]` closes segments while one is open and is a literal `]` only where none
is open; `[[` is always a literal. Consequence: a literal `]` cannot be written inside a segment. Alternative: change
the worked entry to `] ]` (rejected: the note's text is the spec under test). Commit: WO-1.

**D1-3. Quantity params from legacy text (§4.3 rule 5).** "Or the param declaration fixes it" needs a unit in the
declaration, which §4.2.2's param fields lack. The schema's `param` gains optional `unit` and `quantity_kind` (type
`quantity` only, by use). `quantity_kind` rather than `kind`, so the field cannot be read as the entry's failure kind.
Commit: WO-1.

**D1-4. Kinds and vocabulary files.** `kinds.yaml` and `vocabulary.yaml` are validated against
`$defs/kinds_document` and `$defs/vocabulary_document` of `message-catalogue.schema.json`; the schema's root is the
catalogue document that `register()` takes. Commit: WO-1.

**D1-5. Rendering details the note leaves open.** (a) A field renders from the first matching variant that defines
it, then the base; a candidate that fails (or renders empty) falls to the next, and a failure is a defect: `strict`
raises it, the audit records it (session fails, I9), production continues. (b) The defect record is
`audit.Auditor.defects`, beside `misses`. (c) An outcome entry without `context` uses its `summary` for line 1.
(d) A stub contributes no `where` (§4.4: stubs give summary and kind). (e) Elements: per chain entry outer → inner,
the merged params in insertion order that the entry declares element-typed (this reproduces both §4.13.1's and
§4.13.3's printed order; declaration order would not reproduce §4.13.3's). (f) The minimal rendering (I9) uses the
first chain code, its entry's family and kind when it has one, else the caller's family (`api_error`, `outcome`,
`refusal`) and kind `bug`, with the machine text as summary. (g) `render_error` takes the `ApiError` *document*, so
`messages` imports nothing from `application`. (h) A validation report's first FAIL check id is used as a chain code
directly (a check id does not parse under §4.3's grammar). Commit: WO-1.

**D1-6. Entries needed by WO-1's tests beyond §4.13.** `INITIALIZATION_FAILED` and `initializer_failed` gained an
`examples` item each (the note's YAML has none, but the schema requires one on a complete entry). `L-TH-3` is a stub
(it is `phase_regime_mismatch`'s `see_also`); `L-TH-4` is complete with authored prose (summary, why, action) taken
from the support-matrix row. `unsupported` and `internal_error` are stubs with `args: [reason]` of type `code`, so
§4.3's expansion examples resolve. Commit: WO-1.

## WO-2

**D2-1. G2 scanner details (§9).** Beyond §3.2's list: (a) for `api_error`, `_refuse`, `Failure` and
`RunUnsupportedError` the code is the first *code-shaped* string constant (lower or upper snake with an underscore)
among the first two positional args, because `Failure(status, code, …)` and studies' `_refuse(qualification, code,
…)` put the code second; (b) the string args of a `Literal[...]` assigned to a name ending `Code` (`ApiErrorCode`,
studies' `RefusalCode`) are scanned as a closed set; (c) a plain string constant is scanned when it *begins*
`snake_code(` (not only when it fully matches), so `"task_unsupported(optimization)"` literals are found. Eight
tokens are allow-listed with reasons (`scan-allow.yaml`): three column keys of `invalid_spec(<key>)`, a budget label
and four replay-difference location labels. Commit: WO-2.

**D2-2. G1's "validation check ids" and "limitation ids".** Check ids are the `XXX-NN` literals of
`application/validation.py` (16). Limitation ids are the `limitations` section of `benchmarks/t08/support_envelope.yaml`
(83); the `unsupported` rows `U01..U15` are not limitations and are not enumerated. Commit: WO-2.

**D2-3. Stub wording and kinds (§9; Q10).** Stubs were generated mechanically from the code (a one-off script, not
committed): title = the code in words; summary by family (`Refused: <words>.`, `The request was refused: <words>.`,
`The solve ended <CODE> (<taxonomy class>).`, `Status <S>.`, `The job ended: <words>.`, `Validation check <id> did
not pass.`) — the technical summary §4.12 promises for stubs. Kinds by §4.2.1's tables; `review: true` on every
judgment call: refusal codes matching no row (default `input`), every `*_mismatch` (whether it is internal), every
upper-case study/assessment refusal, and every validation check (the note gives check ids no kind rule; `CAP-01` →
`not_supported`, the others → `input`). `infeasible_spec`'s stub is hand-written: the generated words would fail the
I8 lint. Commit: WO-2.

**D2-4. `sync-limitations` keeps a complete entry's summary (note conflict).** §4.2.9 regenerates `summary` from the
matrix text, but a complete entry's summary is jargon-linted and the matrix text is not jargon-free (L-TH-4's carries
backticks and a snake_case code). Choice: the generated summary applies to stubs only; a complete entry keeps its
authored summary. Generated text is escaped for the template grammar (braces and brackets doubled). Commit: WO-2.

**D2-5. G3 hooks and the session verdict.** Hooks: `api_error()` (the code, the message, a string `detail.reason`),
`bundle_for()` (the outcome and `result.message`), `Unbound.__post_init__` (`detail`; the caller is frame 2, past the
generated `__init__`) and `RunUnsupportedError.__init__` (its code text). Each costs one `audit.auditor is not None`
check when the audit is off. `pytest_sessionfinish` turns a passing session into a failing one when there is any miss
or rendering defect; `pytest_terminal_summary` lists them. Commit: WO-2.

## WO-0 record (measured)

`--record` at `37a521f9` (WO-0's commit, no MSG code), in a detached worktree, with `--suite`:
`MSG-G0 PASS: a 0 diff; b 0/562 diff (108 bundles); c 0/57 diff; d 0 hit(s) in 414 stores; surface same`
(self-check). (a) `t07` identity SHA-256 `54ca564b…57d1`. (b) 559 member digests of 54 bundles (52 RC + C01 + C02;
the printed `n_bundles` counts each bundle's `artifacts/` directory separately — kept as recorded, so the field
compares like with like) and C03 `not_found: no such artifact`. (c) 57 replays: 52 v0.3.0 RC bundles
`exact_replay MATCH bitwise`, 1 fixture `compatible_reproduction MATCH bitwise`, 4 fixtures
`inspected_archived_results NOT_RUN`. (d) 414 stores, 0 hits. MCP digest `455d01eb…e125`. The suite run inside the
record: 14838 passed, 3206 skipped, 1 failed — `test_t07_v17_reference.py::test_f6_the_forty_runs_fit_their_budget`
(418 s > 300 s), a wall-clock budget missed under load (two full suites ran at once); not an MSG matter.

**D2-6. The cold-load budget (§7 Performance: ≤ 200 ms).** With 363 entries the load measured 430–500 ms: the
jsonschema pass over the core files cost ~100 ms plus the jsonschema import. Choice: a production load skips the
schema pass over the package's own files; it runs whenever texts are given, under the test-suite audit (so every
suite run validates the shipped catalogue), and in `test_the_packaged_catalogue_is_schema_valid`; an extension's
document is always validated by `register()`. Measured after (fresh process, machine load average ~50 on 48
cores, 3 runs): cold load 100–119 ms (plus 90–106 ms for importing the modules), render median 0.16–0.20 ms
(1000 renders of §4.13.1). Alternative: validate always and exceed the budget. Reversible by: `validate_core=True`
as the default. Commit: this one.

**D0-7. MSG-G0 (b) defect found and fixed (`993cc42a`).** The check at `793b74d4` failed (b) on `run-manifest.json`
in all 54 bundles and passed on the other 505 members. C01 written twice at one commit differs in exactly
`started_at`, `elapsed_seconds` and `manifest_sha256` (which covers the first two), so the first baseline's self-check
could not see it. (b) now digests the run manifest without those three (`run-manifest.json#stable`); every artifact
and every other manifest member is still compared. The baseline's (a)–(c) were re-recorded at `37a521f9` with the
fixed script (self-check PASS, 559 digests, 57 replays); its (d) is the first record's (unaffected). `--parts` lets a
run judge a subset; a subset run says so in its summary line. Control: the baseline with (a) altered → `MSG-G0 FAIL:
parts a only: a 1 diff`, exit 1.

## Gate results at the end of WO-2

- MSG-G0 at `993cc42a` (code = `793b74d4`): `MSG-G0 PASS: parts abc only: a 0 diff; b 0/562 diff (108 bundles); c 0/57
  diff; surface moved: schema_files/message-catalogue.schema.json, schema_files/registry.json`. (d) at `793b74d4`
  (full suite inside the check): `d 0 hit(s) in 414 stores`. MCP digest and every operation schema unchanged.
- `scripts/gate.sh` at `793b74d4`: ruff, format, mypy, node clean; pytest 14902 passed, 3206 skipped, 2 failed — both
  wall-clock budgets under machine load (load average 50–57 on 48 cores, two full suites at once):
  `test_t07_conformance.py::test_the_budget_of_the_scenario_runs` (123.0 s > 120; passes when rerun alone) and
  `test_t07_v17_reference.py::test_f6_the_forty_runs_fit_their_budget` (480 s > 300; 343 s alone; it also failed at
  the branch point, 418 s, with no MSG code). MSG-G3: no miss, no defect.

## WO-3

**D3-1. Which surface `.explanation` renders.** `ApiError.explanation` returns the carried
`detail.explanation` when the error was projected, else renders with surface null (the transported
document's); `ApplicationError.explanation` and `__str__` render surface `python` from the machine
document (any carried explanation ignored). Alternative: one surface for both. Commit: `251b98b4`.

**D3-2. Nested `ApiError` locations.** `operations.error_locations(name)` walks each response
schema (`$ref` resolved, `allOf/anyOf/oneOf`, `if/then/else`, `properties`, `items`,
`prefixItems`, `additionalProperties`, `patternProperties`; `*` for an array item or map member)
and records where `api-error.schema.json` is referenced; cached per operation. Measured: 10
operations, 11 locations (`error`, `job.error`, `run_result.error`, `items[*].error`,
`events[*].error`). The test pins that table (read off the schemas by hand) and projects a fixture
error at each. `project_error` and the nested attach are idempotent (an error that carries an
explanation keeps it), because bindings project errors `dispatch` already projected. Commit:
`251b98b4`.

**D3-3. CLI text.** Refusal stderr renders surface `cli` from the *projected* error (the message
as bounded). The top-level handler's `Details:` is `<ExceptionType>: <str>`, then the traceback.
The `validate` explanation line goes after the check's `implicated:` line. No check entry is
complete yet, so the golden `broken.yaml` record is unchanged (the test forces one complete).
Commit: `251b98b4`.

**D3-4. FB-03(b) members query.** Reuses `ProjectStore.artifact_children(bundle_id)` (already
the registered `<bundle id>/<file>` rows, by parent); no new store query. `job_id` is added only
when the bundle id ends `:bundle`/`:rerun` *and* that job exists (an import's
`import-<n>:bundle` names no job). The pre-MSG detail of this refusal has no `operation` member
(the note's §4.13.3 HTTP example shows one; `_refuse` keeps `operation` for the audit only) — the
detail stays as it was plus the new members. Commit: `251b98b4`.

**D3-5. `str()`-conversion check.** `tests/test_msg_surfaces.py` scans `src/` by AST for an
`except` of `ApplicationError`, `StoreError` or `SolveFailedError` whose body uses `str(e)`,
`repr(e)` or `{e}` outside a `print(..., file=sys.stderr)`. Finds none; a control file is flagged.
Commit: `251b98b4`.

## WO-4

**D4-1. Stubs for the three new codes.** `not_a_directory`, `not_a_project`,
`project_id_mismatch` are stubs (`complete: false`, `review: true`) with a technical summary that
names the directory; `not_a_project`'s keeps the words "is not a project", so the existing
`match="not a project"` checks hold. Their action is the kind's default, which reads oddly for a
directory: for WO-9 / the design lane to complete. Commit: `69802e70`.

**D4-2. `exist_ok` id check.** `project_id_mismatch` reads the existing id through
`ProjectStore.open(...).project_id` (closed at once) before `LocalApplication.open`, so a refusal
takes no owner lock. Its machine message is `project_id_mismatch: <directory>`; params add
`project_id` and `existing`. Commit: `69802e70`.

**D4-3. CLI surface for coded store errors.** Every CLI site that printed `str(StoreError)` now
prints `StoreError.text("cli")` (`_human_text`); identical to `str()` for an uncoded error.
Golden: the refused `project init` stderr only; `msg_reversed` in the pins hash test restores
T07's one-liner, and `PINS_T07_SHA256` holds. Commit: `69802e70`.

## WO-6

**D6-1. `RunFailure` details and fallbacks.** `Details:` is `<message> — <artifact id>`, the
outcome when the bundle has no message. An unreadable bundle: outcome from the run facts,
taxonomy from `verify.failure.TAXONOMY` (empty string if the outcome has none), `message: null`,
chain `[outcome]`, empty lists. `params` are `messages.render.explain_failure`'s merged params
(context ids included). Commit: `d8a2be92`.

**D6-2. `SolveFailedError` without a failure** (a job that did not complete): `args[0]` is
`<job_status>: job <id>`, text the job-status entry's (family `job`). Commit: `d8a2be92`.

**D6-3. CLI failure text.** `api` prints each non-null `failure` found anywhere in the response
from its carried (surface-null) explanation; `solve`/`inspect` render the bundle's failure with
surface `cli` and no project context (no revision or job ids), `Details:` naming the bundle file
path. The `solve` `note` line is skipped when the status is null. Commit: `d8a2be92`.

**D6-4. MSG-G10 decomposition and the surface chain.** `tests/msg_schema_support.without_msg`
removes `failure` from run-result-shaped objects and the `run_failure`/`explanation` `$defs` (an
emptied `$defs` is dropped: run-result had none). Composed into every existing R4-G3/MCP
decomposition (M02, M04, A3.2, v17-c2 chains). `scripts/m07a_rc.py` gains link c_4 (R-934,
`strip_msg`, `D_4 = b083ffe1…`) as its docstring prescribes for an MCP-visible change. Open for
the design lane: the register entry carrying `D_4`, and Frank's carry naming c_4. WO-7 extends
`without_msg` (the `explain` tool, `message_entry`) and re-registers `D_4`. Commit: `d8a2be92`.

**D3-6. Exact-`detail` assertions on transported errors.** They compare `machine_detail(doc)`
(`tests/msg_support.py`: the detail without `explanation`, which must be present and explain the
document's code). Nine sites in five files (`test_t07_w5b_cli`, `test_t07_w5d_surrogates` (one,
parametrized ×9), `test_adr_0002_a1_integers`, `test_t07_w5a_operations` (3), `test_t07_w6a_http`
(2)); the note's ~33 counted direct calls too, whose documents are unchanged. The pins-hash tests
(`test_t07_w5b_cli`, `test_t08_rename_substitution`) reverse MSG's two records first
(`msg_reversed`: U05's stdout without `detail.explanation`, its stderr empty; the refused
`project init`'s stderr T07's one-liner); both registered hashes hold. G20: `error_locations`'
`@cache` allowlisted (pure function of the static table and schemas). Commit: this one.

**D6-5. The W26 web fixtures (`tests/web/fixtures/w26/exchanges.json`).** M06's validity test
holds each recorded response to today's schema, so the three `get_job_result` records needed
`run_result.failure`. A full `m06_web_fixtures.py --write` re-take also moves unrelated values
since M06 (12 `policy_sha256`, `models`, `package_version`, thread variables, clocks), so only
MSG's members were taken from a fresh generation (same project, same ids; every raw member but
the three run manifests byte-identical): the 3 `failure` members and the 2 refusals'
`detail.explanation`. Nothing written by hand. Alternative: the full re-take (WO-10's, with the
shell's display). Commit: this one.

## Gate results at the end of WO-3, WO-4, WO-6 (code = `4324953f`)

- MSG-G0 `--check --suite`: `MSG-G0 PASS: a 0 diff; b 0/562 diff (108 bundles); c 0/57 diff; d 0
  hit(s) in 429 stores; surface moved: mcp_tools_sha256, schema_files/application-results.schema.json,
  schema_files/message-catalogue.schema.json, schema_files/registry.json`.
- `scripts/gate.sh`: ruff, format, mypy, node clean; pytest 14959 passed, 3206 skipped, 3 failed,
  all wall-clock limits under load (load average 57–61 on 48 cores, two full suites at once):
  `test_t07_conformance::test_the_budget_of_the_scenario_runs` 131.7 s > 120 (alone: 216.6 s;
  paired A/B run at the same moment, pre-MSG `37a521f9` 54.1 s vs MSG 48.8 s, both pass);
  `test_t07_v17_reference::test_f6_the_forty_runs_fit_their_budget` 360.3 s > 300 (alone 324.9 s;
  it failed at the branch point too, 418 s); `test_m02_kill_chain::test_g3e_a_worker_killed_alone_
  leaves_its_child_to_its_lifeline` 2.015 s > 2.0 (alone: passes, 12 s run). No budget changed.
- MSG-G3 over the gate's suite: no miss, no defect. WO-6 converse: 675 run results read back, 55
  with a failure, `failure` non-null iff a `failure_bundle` output in every one.
- MSG-G7: golden diff = the U05 record (stdout `detail.explanation`, stderr) and the refused
  `project init` stderr; all 17 exit codes unchanged. MSG-G10: 7 R4-G3 snapshots and the MCP digest
  moved; with `without_msg` all equal their pre-MSG values (`455d01eb…` for MCP).

## WO-7

**D7-1. Where `entry_document` lives.** `messages.render.entry_document(code)` and
`suggestions(code)` (the note's `messages.entry_document`): `messages/__init__.py` imports nothing
so that `messages.diagnostic` stays cheap, and the examples need `render_code`. `Catalogue.sha256()`
is now computed once (the catalogue is frozen at the first lookup), which took one `entry_document`
from 13 ms to 0.65 ms. Commit: `6a5435ad`.

**D7-2. `suggestions` when nothing is close.** The detail is always `{code, suggestions}`, with
`suggestions` a list, possibly empty (the note's shape). The engine counts `[]` as present, so the
`not_found` `code` variant rendered "Did you mean ?". Options: (i) split the catalogue variant on
`not_equals: {suggestions: []}` — "Did you mean <list>?" — with a second variant, "Check the code's
spelling against the docs' Messages section; no message code is close to it."; (ii) treat an empty
list as absent in the engine (changes §4.2.4's presence rule for every list param). **(i).**
Commit: `6a5435ad`.

**D7-3. A detail member named `code`.** `api_error(code, message, /, *, retryable, **detail)` and
`LocalApplication._refuse(code, message, /, *, …)` are positional-only in `code` and `message`
(no caller passed them by keyword; AST scan), so `explain`'s refusal can carry `detail.code`.
Alternative: rename the member (the note names it `code`). Commit: `6a5435ad`.

**D7-4. `message_entry` schema details.** As §4.9, closed and all required: the five templates
`string | null` (the catalogue requires `summary`, so it is never null in practice); `params` items
closed `{name, type, label, optional}`; `catalogue.id` a `const`, `catalogue.sha256` 64 hex;
`examples` `$ref` `explanation`. The valid fixture is `explain("phase_regime_mismatch")`; it carries
the catalogue digest, so **every catalogue edit needs `scripts/t07_schema_fixtures.py --write`**.
Commit: `6a5435ad`.

**D7-5. `openflowsheet explain` text.** `messages.text.format_entry`: `<code>: <title>`, then the
layered text's 11-column fields `Kind`, `Summary`, `Note` (stubs: §4.12's sentence), `Context`,
`Where`, `Why`, `Do`, `Params` (`name (type[, optional])`), `Gap`, `See`, `Status` (deprecated),
`Docs`; then each example's layered text under `Example:`, indented 2. An unknown code: the layered
`not_found` text on stderr, stdout empty; with `--json`, the projected `ApiError` document on stdout
as well (`_print_refusal(document=…)`); exit 6. Commit: `6a5435ad`.

**D7-6. The method's own checks.** `LocalApplication.explain` refuses a non-string `code`
`invalid_request` at `/code`; length and pattern are the request schema's (dispatch). The
`not_found` refusal is audited through `_refuse`. Commit: `6a5435ad`.

**D7-7. Gate change: `m07a_rc` §5.3 item 4** (flagged). The item held the served descriptions to
exactly `v17-c2`'s 17 tools; ADR 0058 D7 adds `explain`. It now pins `explain.md` as c_4's
addition (`MSG_FILE_SHA256`), held equal to `REVIEW.json`'s recorded hash by a new test, with a
one-byte control. Nothing else in the item moved. Own commit: `a34f1735`.

**D7-8. The `explain` description's reviews.** `REVIEW.json` records `explain.md` with both reviews
pending (`pending_design_review`, `pending`). `tests/test_t08_w2_description_reviews.py` is red
by design until the design lane and Frank record them (no xfail): **a merge blocker for MSG.**

**D7-9. MSG-G10 re-registration.** `without_msg` also drops `$defs/message_entry` and every served
tool named in `MSG_OPERATIONS` (`explain`). R4-G3: `SNAPSHOT_MSG_EXPLAIN` = `a4fcafe7…` (new row,
no pre-MSG value). Served MCP digest `D_4` = `1ca06b37…` (was `b083ffe1…` at WO-6), in
`tests/test_t08_w2_surface_digest.py` and `scripts/m07a_rc.py` c_4; minus MSG it is M04's
`455d01eb…`. The count pins (17 → 18 MCP tools, 21 → 22 operations, 19 → 20 routes, Inspection
9 → 10) and the transport scenarios (HTTP, MCP, CLI, G11, G13) gained `explain`. The generated
operations page and the web route table were regenerated. Commit: `6a5435ad`.

## WO-8

**D8-1. Page form.** One `## \`code\`: title` section per code, in key order, opened by the
explicit anchor; prose fields as a list, Markdown-escaped (`<`, `>`, `&`) outside code spans; each
example as a `text` block of its layered text. An empty family (`notice` today) says "No code is in
this family yet." Commit: `30ef6dde`.

**D8-2. "A link to the support-matrix row".** Support-matrix rows have no anchors, and each
limitation id is itself a catalogue entry synced from the matrix. The gap links its limitation's
section on `messages/limitations.md` and the support matrix document. Commit: `30ef6dde`.

**D8-3. "Every docs URL the corpus produces resolves".** The corpus is WO-9's. `tests/
test_msg_docs.py` checks every entry's `docs`, every rendered example's and every one recorded in
the committed fixtures (W26 exchanges, the schema fixtures), with `docs_url_problems` for the
corpus test to reuse. **A catalogue edit also needs `scripts/doc_pages.py`** (the pages are
generated; `--check` fails otherwise). Commit: `30ef6dde`.

**D7-10. What the full gate found after WO-7/WO-8** (`30ef6dde`). Five pins the targeted runs had
not reached: `test_m02_schemas` G1c and `test_m04_study_job` A42 (pre-MSG snapshots: the `explain`
row is skipped, as in R4-G3's MSG-G10 test); `test_t07_conformance`'s every-carried-operation
check (the scenario now calls `explain` once); and T08.A20 — the working envelope
`benchmarks/t08/support_envelope.yaml` lists every operation with its transports, so its
interfaces axis gains `explain: [python, cli, http, mcp]` and "twenty-two operations", and
`docs/support-matrix.md` is regenerated (`t08_support_matrix.py --emit`). The envelope change is
ADR 0058 D7's consequence, not a new decision; the design lane may want it named in the register
entry. `scripts/t08_support_matrix.py check_a20`'s pinned count moves 21 → 22 with its reason (a
gate change, flagged). Commits: `f0f17ad8` (tests), `631a9f3f` (envelope, matrix, A20 count).

## Gate results at the end of WO-7, WO-8 (code = `30ef6dde`, then `631a9f3f`)

- `scripts/gate.sh` at `30ef6dde`: ruff, format, mypy, node (92) clean; pytest 14994 passed, 3206
  skipped, 10 failed (2 h 58 min; load average ~61 on 48 cores). Nine fixed by `f0f17ad8` and
  `631a9f3f` (D7-10; the touched files re-run: 1177 + 76 passed). Left:
  `test_t08_w2_description_reviews` (red by design until `explain.md`'s two reviews, D7-8) and
  `test_t07_v17_reference::test_f6_the_forty_runs_fit_their_budget` 589.5 s > 300 (alone: 420.7 s,
  load 61; it failed at the branch point too, 418 s). `test_t07_conformance::
  test_the_budget_of_the_scenario_runs` failed once in a targeted run, 129.0 s > 120; alone it
  passes (scenario 118.2 s). No budget changed.
- MSG-G0 `--check` (no `--suite`): `a 0 diff; b 0/562 diff (108 bundles); c 0/57 diff`; (d) not
  measured in this run (WO-7/WO-8 are identity: no; last measured at `4324953f`: 0 hits in 429
  stores). Surface moved as expected: `mcp_tools_sha256`, `operations/explain/*`,
  `application-results.schema.json`.
- MSG-G5: `doc_pages.py --check` up to date; `msg_catalogue.py sync-limitations --check` clean.
- MSG-G7: no CLI golden record changed (the 17 records and exit codes; `explain` is a new command).
- MSG-G8: `explain` equal on Python, CLI, HTTP and MCP for all 366 keys and for the refusal.
- MSG-G10: R4-G3 and the MCP digest equal their pre-MSG values with `without_msg`
  (`455d01eb…`); new values `SNAPSHOT_MSG_EXPLAIN` `a4fcafe7…`, `D_4` `1ca06b37…`.

## WO-9

**D9-1. WO-5 is parked (orchestrator, 2026-11-06): what waits on it is a strict xfail.** WO-5 must
edit `models/thermal/{flash,heater,machines,mixer,valve}.py`, which F0 freezes (M9, R-940). Every
corpus fact that only the sidecar can supply is a `pending` item of its case, run by
`test_g6_pending_holds` as `xfail(strict=True, raises=AssertionError, reason="MSG WO-5 parked:
thermal modules frozen by F0 M9 (R-940)")`: C01's `value`, `saturated_vapour`, `pressure` (10 kPa,
`value > saturated_vapour`) and its `phase_capability` action token (the action naming it is the
`has: [landed]` variant, and `landed` is a P1 param); C02's `s_star`, `s_saturated`, `pressure`
(`s_star < s_saturated`) and its element S4 (P2's `outlet`). **Beyond the brief, flagged:** C11's
`p_spec` (5 MPa) and `p_inlet` (3 MPa, the pump's outlet; `thermal.heater`'s `pressure_drop`
defaults to 0) come from P5 (`machines.py`), so they are pending for the same reason. C09's bounds
are conditional in §7 ("if `detail_pattern` extracts them"); the provider text is P4's, so no
pattern is written and nothing is asserted. Everything else of C01/C02/C11 is asserted now.
Commit: `184479d8`.

**D9-2. C06, C07, C08 and C10 record the codes emitted, and their implicated ids are pending
(design lane).** Measured (§3.6, Q8): all four are refused at admission `revision_not_ready`.
C06 (`pump-T` on the pump's `outlet.T`), C07 (`turbine-P` removed) and C10 (`thermal.boiler`)
validate DRAFT: every structural check is `NOT_RUN` and the specific code sits only in those
checks' messages (`specification_unconsumed(pump-T)`, `specification_missing(S4.P)`,
`model_unsupported(thermal.boiler)`). §4.4 rule 2 reads the first `FAIL` check only, so the chain
is `[revision_not_ready]`, with no elements. C08 (`"degc"`) validates INVALID; rule 2 gives
`[revision_not_ready, DIM-01]` from the check's id alone, without its message
(`specification_unit_unsupported(boiler-T)`) or `implicated_objects`; and "degc" is in no machine
message at all. No machine message was changed (I1). Pending, as strict xfails: C06 `pump-T`,
C07 `S4`, C08 `boiler-T` and "degc" in the summary, C10 `model_unsupported`/`not_supported`/
`gap.capability` and the instance B. **Design-lane question:** extend §4.4 rule 2 to (a) parse the
first non-PASS check's message when no check FAILs (DRAFT), and (b) add a failing check's
`implicated_objects` as elements and parse its message for the inner code? My default would be
both: it is renderer-only (no machine message, no bundle, no identity), and it turns C06/C07/C10
into their specific codes. C08's unit text would still need the revision context (the spec's
unit) — a separate question. Commit: `184479d8`.

**D9-3. "In the summary text" = line 1 and its cause.** With an outcome first in the chain, line 1
is the outcome's `context` and the explained entry's `summary` is `cause` (§4.4), so C01's S4 is
in the cause line. The corpus checks element ids and `in_summary` texts in `summary + cause`.

**D9-4. Transports.** `solve` is Python/CLI only, so a refused solve travels as `submit_job`
(`operation: solve`); a run failure as `get_job_result`; C03 as `get_artifact`; C12 as `validate`.
Documents are compared after removing the validation report's `provenance.timestamp`, a clock
reading each call makes afresh (as `test_t07_conformance.py` strips it). The transported
explanation's code, kind, chain, summary, cause, why, action and elements equal the Python one.

**D9-5. Texts.** `text.python` is `str()` of the exception the Python API raises (a run failure's
`raise_for_outcome()`); `text.cli` is the stderr of `openflowsheet api <operation>` for a
transported case and of `project init` for C04/C05. The test's directory is written `<tmp>`.
`--msg-update` (a conftest option) rewrites the YAML in its own layout.

**D9-6. Complete entries written.** `revision_not_ready`, `unsupported` (api_error), `DIM-01`
(check; `review: true` kept, its kind was not reviewed), `out_of_domain`, `pressure_rise`,
`task_unsupported`, and `model_unsupported` (C10's expected code, on §4.2.6's list; reached only
when D9-2 is decided). `unsupported`'s gap is `{limitation: null, capability: null}`: the reason's
own entry carries the typed gap, and `unsupported` is never the explained code when its reason has
an entry. `pressure_rise` takes the legacy arg as `machine` (`pressure_rise(turbine)`) and `unit`
from the outer `initializer_failed(T)`. The rest of §4.2.6's normative list (the other api_errors,
the outcomes and statuses, `pressure_fall`, `isentropic_state_single_phase`, …) is not WO-9's and
stays stub. The prose is the build lane's draft for the reviewer pass. Commit: `3842f686`.

**D9-7. MSG-G7 / Q7: the U05 CLI pin re-taken.** `validate <CASE> --task optimization` is the only
record that moved (stdout's `detail.explanation`, stderr's layered text; exit 14 unchanged);
`msg_reversed` already strips both, so `PINS_T07_SHA256` holds. Commit: `3842f686`.

**D9-8. C09 at 200 K.** The refusal comes from the pump P (the first unit that evaluates a
property of the 200 K feed), not from the feed: the case records P.

## WO-10

**D10-1. Where the explanation shows.** `text.js explained()` renders summary (strong), cause and
"Do: action", tagged `data-ofs-explanation-part`. The error panel shows it under its heading,
above the machine message, HTTP line and detail, which are unchanged. A failed run's
`run_result.failure` shows as a `notice-bad` block (`data-ofs-failure`) in the job screen's
summary and the failure screen's outcome; a job's own `error` adds its explanation under its
existing one-line notice. Docs URLs are not linked: `h.js` allows `#` fragments only. Commit:
`5a68e53c`.

**D9-9. The manifest: status `implemented`, harvested as F0's (F0 D22).** `evidence/MSG/b1a82351…`
is MSG's first manifest. Status is `implemented`, not `tested`: the full suite's one red is
`explain.md`'s pending reviews (D7-8), and MSG-G0 (c) prints FAIL (D9-10). Each of its four
limitations and two non-pass checks is class P (no user-facing support claim), appended to
`benchmarks/t08/support_envelope.yaml`; matrix re-emitted; `HARVEST_SIZE` (68, 939, 120) →
(69, 943, 122) with its reason (a gate change, flagged). Re-take the manifest as `tested` once
D7-8's reviews are recorded and D9-10 is ruled.

**D9-10. MSG-G0 (c) after F0 (design-lane question).** At `0067129c`: `c 156/109 diff`. The
baseline's 57 replays are unchanged; the 156 keys are F0's 52 v0.3.0 bundles
(`tests/fixtures/f0/v0.3.0-bundles`, 3 keys each), registered on main after WO-0's baseline and
absent from it. F0 M7 judges them (52/52). §7 says "after F0 lands, F0 replaces (a)–(c)". Neither
the gate nor the baseline was changed. Default: F0 replaces (a)–(c) (F0 PASS), MSG-G0 keeps (d).

## Gate results at the end of WO-9, WO-10

- `scripts/gate.sh` at `0067129c`: GATE FAIL, 2 failed, 15064 passed, 3206 skipped, 11 xfailed
  (2 h 59 min, load ~78): `test_t08_w2_description_reviews` (D7-8) and f6's budget, 327.95 s >
  300 (alone 250.2 s; budget unchanged); ruff/format: 38 errors in main's
  `docs/derivations/scripts/f6_std_seed_reference.py`, fixed on main (`b9a05e16`) and merged
  (`b1a82351`; ruff, format clean). mypy, node (94) clean.
- Full suite at `b1a82351` (MSG-G0 `--suite`): 1 failed (description reviews), 15065 passed,
  3206 skipped, 11 xfailed (2 h 21 min).
- MSG-G0: a 0 diff; b 0/562 (108 bundles); c see D9-10; d 0 hits in 442 stores. F0
  `corpus_identity.py --check`: PASS, M1 50/50 … M9 35/35.
- MSG-G4 0 violations (15 complete entries); G5 clean; G6 23 passed, 11 strict xfails; G7 16
  passed (U05 record only); G8 the ten transported corpus cases equal on four transports.

## WO-11 (review fixes: WO-5a, rule 2, entry fixes)

**D11-1. S2: a non-finite capture stays text.** `legacy._typed` returns the captured text when `float()` gives `nan`
or `inf`; the patterns WO-5a adds use strict decimal groups (`[-+]?[0-9]+(?:\.[0-9]+)?(?:e[-+]?[0-9]+)?`), so they
cannot capture one anyway. Test with a finite control. Commit `a87881fb`.

**D11-2. WO-5a, the sidecar (review Q1 (a) narrowed; register R-942; note §4.6 amended).** Producer: the traversal
hop `models/revision_flowsheet.py` `traverse`, which builds `Diagnostic(<code at the head of line 1>, {"detail":
lines 2+})` (`None` when there are no detail lines). Line 1's code is read lexically (`[A-Za-z]…` followed by `(`, `:`
or the end), because `models` imports only `messages.diagnostic`. Carriers `FlowsheetPass`, `InitialStateFailure`,
`StepResult` (field `diagnostic`, `compare=hash=repr=False`; reflective test). `run_revision_session` gains
`on_diagnosis` (a callback beside `on_iteration`): called once after the bundle is written, iff a failure bundle was
written and the last step's outcome is the bundle's and carries a sidecar. **Choice:** a callback rather than a field
on `RunManifest` (`run/manifest.py` is identity-central; the carrier rule would apply to its `as_document`) or a
changed return type (two callers). The runner stores `run["diagnosis"]`. `LocalApplication._run_failure` passes the
sidecar only when the bundle was read (without the bundle there is no message to match, and audit mode raises on a
mismatch). `explain_failure` applies the **explained** entry's `detail_pattern` to the sidecar's `detail` (sidecar
params win over the groups) and derives a missing `outlet` stream param as the one connection leaving the `unit`
param's `outlet` port (§4.2.5). `legacy.detail_params` is factored out of `_apply_detail` (behaviour unchanged).
Session scan (`tests/conftest.py`): every bundle written through `write_bundle` (revision and SYN-001 sessions) is
searched for the keys `"diagnosis":` and `"diagnostic":`; the count goes to the terminal summary.

**D11-3. Patterns and units.** Basis confirmed molar: C02's `s_saturated` = 146.80317968321518 J/(mol*K) =
8.14883 kJ/(kg*K) × 18.015268 g/mol, the steam tables' s_g(10 kPa) = 8.1488. Entries: `phase_regime_mismatch`
(`declared`, `landed`, `vapour_fraction`), `isentropic_state_two_phase` (`s_star`, `s_saturated` in J/(mol*K)
`molar_entropy`, `pressure` in Pa, `phase`), `pressure_rise` and `pressure_fall` (`p_spec`, `p_inlet` in Pa; both
`is above|is below|exceeds`, the SYN-001 valve's wording), `out_of_domain` (`what`, `value`, `low`, `high`, units from
the text, quantity kind null since it varies). **Choice:** `isentropic_state_two_phase` gains a variant `equals: {phase: LIQUID}`
whose `why` drops the base's numbers sentence, because that sentence names the saturated-vapour entropy and would be
false for a `LIQUID` (pump) detail (the docs page shows the base, with `<s_star>`); `pressure_fall` stays a stub (WO-12, M1)
with `args: [machine]`, its params and pattern. Display: §4.5's four digits print IAPWS-95's range as "273.2 K to
1273 K" in C09's why; the `numbers` carry the exact 273.16 and 1273.15.

**D11-4. S1 `out_of_domain`.** The IAPWS-95 sentence reads "For example, water's IAPWS-95 method …". A variant with
the numbers ("Here the temperature 200.0 K is outside the method's range of …") replaces it when the pattern matched.
**Choice:** kind `numerical` and an iterate-worded action under the iterative outcomes (`outer:` ACTIVE_SET_CYCLING,
ATTEMPTS_EXHAUSTED, BOUND_BLOCKED, BUDGET_EXHAUSTED, COUPLING_NOT_CONVERGED, EVALUATION_ERROR, HOMOTOPY_STALLED,
INNER_SOLVE_INCONSISTENT, LINEAR_SOLVE_FAILED, LINE_SEARCH_FAILED, PTC_STALLED, RECYCLE_STAGNATION, STAGNATION);
`input` elsewhere (the traversal, admission, a bare provider text). Alternative: `numerical` by default and `input`
under a list of admission codes — rejected, the admission chains are not enumerable from the catalogue.

**D11-5. M2 `pressure_rise`.** Generic title; base `why` stays the turbine's; variant `equals: {machine: valve}` says
a valve throttles. Example and engine test for `pressure_rise(valve)` (both valve wordings).

**D11-6. Corpus.** Lifted: C01 `action` (`phase_capability`, now the case's `action_token`), C02 `numbers` and
`elements` (S4), C11 `numbers`. C09 now records `numbers: [value, low, high]`. New case key `values` (the independent
expectations, review Q1): C11 = the change set's `turbine-P` (5 MPa) and `pump-P` (3 MPa); C02 `pressure` = the change
set's `turbine-P`; C09 = the feed's 200 K and `iapws95.T_MIN`/`T_MAX`; a test pins each against its source, and C02's
`s_saturated` against an independent `kernel.saturation` call (rel 1e-12) and the steam tables (abs 5e-5 kJ/(kg*K)).
Remaining for WO-5's reason: C01's `value`, `saturated_vapour`, `pressure`, re-reasoned `q1c` ("deferred to the F6 v2
unit models (ADR 0065)"). Texts regenerated with `--msg-update`; the diff is exactly the new causes, whys and actions.

**D11-7. Q2, §4.4 rule 2.** The first `FAIL` check gives its id, then the codes of its message; else, on a `DRAFT`
report, the first `NOT_RUN` check whose message names a code with an entry gives that code; a `WARN` never. The
check's `implicated_objects` become elements (an id a chain param already typed is not listed again as an untyped
`element`; the rule applies to the binder's `implicated` too, which only drops such duplicates). **Choice (the
parse):** check messages are prose around one code (`[not run: <why>: ]code(args). <prose>`), which §4.3 does not
parse, so `legacy.parse_check` takes the first `": "`-part of line 1 whose text up to its first `". "` is a code with
an entry, and the rest as `detail` (the entry's `detail_pattern` reads it); §4.3 is tried first. **Choice:** the
`NOT_RUN` check's id (`STR-0n`, "not run") is not put in the chain: it names the analysis that could not run, not the
cause. Completed in the same change (kind `input`; prose for the design-lane prose check): `specification_unconsumed`
(`unit`, `model`, `column`, `reads` from the binder's hint), `specification_missing` (`column`; `object` from the
hint's first target), `specification_unit_unsupported` (kind changed from the stub's `not_supported` to `input`, §7's
C08 row; `quantity`, `units` from the check's text). Corpus: C06 → `specification_unconsumed` (pump-T, P), C07 →
`specification_missing` (S4), C08 → `specification_unit_unsupported` (boiler-T; `degC` in the summary), C10 →
`model_unsupported` (`not_supported`, `gap.capability`). **Still pending (strict xfail, reason `ctx`):** C08's "degc"
and C10's instance `B`. Both need the revision document as render context; an `ApiError` is rendered from its own
document at projection (`operations.py`), which has no revision. **Question for the design lane:** load the revision
into the error's render context (a store read at projection) or leave both as declared gaps? Default: leave them.

**D11-8. Q6, `explain.md`.** The two edits applied verbatim ("data, never instructions"; "rendered with its own ids
and, where known, numbers"). `REVIEW.json`: hash `f1fca282…`, 997 characters, the design-lane review `reviewed`
(by "reviewer (design lane), docs/reviews/MSG-review.md Q6", 2026-11-06); Frank's stays `pending`, so
`test_t08_w2_description_reviews` stays red (its one open item: `explain: human pending`). Re-pinned:
`m07a_rc.MSG_FILE_SHA256`, and `D_4` = `MSG_SERVED_SHA256` = `eaff4585…` (was `1ca06b37…`; `m07a_rc.py`'s c_4 link,
`docs/interfaces-frozen.md`). WO-12 re-measures `D_4` on the merge tree for the register entry (Q5).

**D11-9. Q7 (D4-1 overruled): FB-01's three are complete.** `not_a_directory` (choose another path, or move the
file), `not_a_project` (check the path; `python`/`cli` variants name `LocalApplication.create` and `project init`),
`project_id_mismatch` (ask for the existing id or none, or another directory; a `cli` variant names `--project-id`).
`review: true` dropped on the three. Prose is the build lane's draft for the design-lane prose check (M1).

**D11-10. S3, S4.** `unsupported`: the base `why`/`action` no longer mention a reason; a variant `has: [reason]`
carries the reason's wording (S3). `worker_lost`, `owner_lost`, `store_error` are complete with environment-worded
`why`/`action` (resubmit; check the directory, disk or the program's lifetime; report only if it recurs). **Kind:
kept `bug`, `review: true`; question for the design lane.** The review says `bug` misleads, but the kind enum is
closed in `message-catalogue.schema.json` and `application-results.schema.json` (`explanation.kind`,
`message_entry.kind`), and no other member fits (`notice` says "not a failure"). An `environment` kind would change
a frozen schema and ADR 0058 D3, which the build lane may not decide. Default: `bug` with the specific actions above,
which now override the kind's "report it" default. `CHECKPOINT_INCOMPATIBLE` (an outcome, `numerical`) and S5
(`DIM-01`'s `review: true`; D3-4's silent cut of `members` at 64) are left to WO-12 with M1.

**WO-11 commits.** `a87881fb` (D11-1), `00a63730` (D11-2, D11-3, D11-5, D11-6; with the out_of_domain example
wording of D11-4), `7d8e5981` (D11-4's kind variant), `4503bb2e` (D11-7), `8c935831` (D11-8), `5f272819` (D11-9,
D11-10). Gates at the end of WO-11: see the handoff.

## WO-12 (catalogue completion, MSG-G0 default, c_4 register entry, evidence)

**D12-1. M1: §4.2.6's normative list complete.** 51 entries completed from their producers: 12 `api_error`
(`admission.py`, `local.py`, `authz.py`, `operations.py`, `jobs/runner.py`, `jobs/executor.py`, `bindings/*`), 21
outcomes (`numerics/newton.py`, `ptc.py`, `scaling.py`, `orchestrator/*`, `syn001/column.py`; K03 spec §5, §11.1), 12
statuses (`verify/certificate.py` verdict precedence; `verify/regularity.py`; `validation.py`; `studies/nlp/closure.py`
for READY_FOR_OPTIMIZATION), four job statuses, `isentropic_state_single_phase` (`machines.py`, `blocks.py`,
`kernel.py`, R-839), `pressure_fall` (`syn001/pump.py`, `machines.py` `_bound_code`: pump, compressor). **Choice:**
also the four ending reasons `not_ready`'s chain reaches (`cancel_requested`, `server_shutdown`, `keyboard_interrupt`,
`wall_time_exhausted`): `render_error` explains the innermost entry, so `not_ready` from a reproduce job that ended
(`local.py` `_unproduced`, `detail.reason`) rendered the stub "The job ended: wall time exhausted." Left stubs (not on
the list): `queued`, `running`, `operation_completed`, `operation_error`, `verifier_refused`. Facts the texts state
and the code they rest on: RELAXED is any non-registered check policy, tightened included (`CheckPolicy.is_registered`
is equality); a `completed` solve job need not be CONVERGED (`runner.py` ends every run `completed`); `invalid_request`
and `document_not_canonical` with an empty pointer (the whole body, `bindings/http.py`) use the base summary (variant
`not_equals: {pointer: ""}`); integer counts render `!raw` (`format_number` gives 4 significant digits: `4.000`).
Pinning test `tests/test_msg_coverage.py::test_the_normative_list_is_complete`: 68 codes (api_error, outcomes and
statuses read from `ApiErrorCode`, `TAXONOMY` + CONVERGED and the three status literals; the job statuses, refusals
with FB-01's five, and L-TH-4 listed), each complete and `lint_entry`-clean; the corpus's codes stay
`test_msg_corpus.py`'s. S5: `DIM-01`'s `review: true` dropped. **Pending:** the design-lane prose check of the new
`why`/`action` texts (review M1: one fresh agent, tight brief) — the orchestrator's to launch. Commit `b2fcd26a`.

**D12-2. CHECKPOINT_INCOMPATIBLE → kind `bug`** (review S4). Its failure action is already `report_defect`
(`verify.failure.OUTCOME_ACTIONS`, ADR 0005 D6: no registered path produces it). An override of §4.2.1's class table,
like `UNSUPPORTED_RANK_STRUCTURE`'s; text only. Alternative: `numerical` (the class's). Commit `c82e29a7`.

**D12-3. S5 (D3-4): `members_total`.** A member list cut at `MAX_LISTED_MEMBERS` carries `members_total` (added detail
member, ADR 0058 D1; absent when uncut, so no existing document moves); a `not_found` variant reads it. Alternative:
say so in the docs only — rejected, the variant's "This bundle holds {members}" would stay false for a cut list.
Test with the cap monkeypatched to 2. Commit `265040df`.

**D12-4. M3.** `scripts/msg_identity_gate.py --parts` defaults to `bd`; the summary names F0's `corpus_identity.py
--check` for (a) and (c). Baseline unchanged. Commit `4dff894d`.

**D12-5. M6: R-943.** D_4 measured on the merge tree (`a8267cef`, `origin/main` merged): served 18 tools →
`eaff4585…`; `without_msg` → `455d01eb…` = D_3. `main`'s register ends at R-941, so R-942 and R-943 are free. The c_4
test reads R-943's entry for both digests. Commit `9c76b939`.

## Gate results at the end of WO-12 (code = `9c76b939`)

- `scripts/gate.sh` (load average 73–77 on 48 cores): ruff, format, mypy (254 files), node clean; pytest 31 failed,
  15062 passed, 3207 skipped, 3 xfailed, 1 error (2:13:11). Failures: `test_every_description_is_reviewed_by_both_lanes`
  (`explain: human pending`, Frank's review); `test_m06_browser_smoke` 29 + 1 error (the headless browser went away,
  then broken pipes); `test_g3f_the_self_deadline_exits_71` 3.65 s > 3.0 s. Alone after the gate: 32 passed (111.5 s).
  No budget changed.
- MSG-G0 (`--parts bd`, stores of the gate's suite): PASS, b 0/562 (108 bundles), d 0 hits in 442 stores. F0 PASS:
  M1 50/50, M2–M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35.
- MSG-G3: no miss, no defect. WO-5a scan: 889 bundles, no sidecar key. WO-6: 681 run results, 77 with a failure.
- Performance (fresh process, 3 runs): 366 entries; cold load 120/119/111 ms; import 81/90/92 ms; render_error median
  0.082/0.074/0.071 ms; render_failure median 0.068/0.068/0.064 ms.
- Manifest `evidence/MSG/9c76b939…/manifest.json`: `implemented` (the one non-load failure needs Frank's review).

**D12-6. The WO-12 manifest in the harvest** (as D9-9). Push CI on `334f52a0` (run 42205758891) failed both `check`
legs and `default-install` on three tests: the description review (expected), `test_m07a_a50_the_harvest_size_is_the_
quoted_one` and `test_a21_every_item_is_classified_once_and_resolves` — the new manifest's five limitations and one
non-pass check (MSG.GATE) were unclassified. Each is class P (no user-facing support claim), appended to
`benchmarks/t08/support_envelope.yaml`; matrix re-emitted; `HARVEST_SIZE` (69, 943, 122) → (70, 948, 123).
