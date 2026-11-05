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
