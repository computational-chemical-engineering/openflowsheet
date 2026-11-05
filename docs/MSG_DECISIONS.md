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
