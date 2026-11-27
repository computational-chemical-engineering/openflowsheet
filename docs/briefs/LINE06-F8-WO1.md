# LINE06 F8-WO1: manifest v2 and schemas (ADR 0067 work order 1)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f8`, branch `wp/F8` (new), branched from `wp/F2` at `df796cc2`
(F2-WO1 to WO6b done; F2-WO6c, a lowering fix, runs on wp/F2 meanwhile and does not touch `run/`). Logs and scripts
under `/home/eajfpeters/.cache/line06/f8-wo1/` only; wait on log lines, not `kill -0`. For tests and F0 in this
worktree: `PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=src`. Create `docs/F8_DECISIONS.md`
(the package's append-only build-decisions log, same shape as `docs/F2_DECISIONS.md`) and log every open choice there
as `DECISION F8-WO1-<n>`. Budget about 150k: at the cap, commit what is complete, write where you stopped in the log,
and end.

## The task

Build ADR 0067 work order 1 (`docs/adr/0067-F8-identity-replay-evidence.md`, section "Work orders", row 1): the
`RunManifest` v2 members of D2 (line ~54) in a new `run/manifest_v2.py`; the optional members in
`schemas/run-manifest.schema.json` (D2) and `schemas/replay-report.schema.json` (D5, line ~95, `ReplayReport`
Amendment 12: `registry_comparison` and the other D5 members; `forced_replay` reserved and refused
`construct_unavailable(forced_replay, TX)`, D8); new schemas `schemas/records-index.schema.json` (D3, line ~81) and
`schemas/run-evidence.schema.json` (D6, line ~128, the envelope only); the artifact kinds of D3 in
`schemas/job.schema.json`; `bundle_format` added to `NON_STRUCTURAL` (`src/openflowsheet/run/manifest.py:65`). The
member classes are D9's (line ~194). Read D1, D2, D3, D5, D6 (envelope), D8 (reservation only), D9, D12 and "Exit
tests" (line ~245). Closed objects stay closed; every new member is optional.

## Facts established (premise check P8, `docs/LINE06_DECISIONS.md`)

- Exist: `run/manifest.py` (`NON_STRUCTURAL`, `verify_bundle`), `run/bundle.py`, `run/replay.py` (`ReplayReport`),
  `run/identity.py`; schemas `run-manifest`, `replay-report`, `data-lock`, `registry-snapshot`, `job`;
  `registry/snapshot.py` (`snapshot_document`, `registry_sha256`), `Registry.extensions_used`
  (`registry/__init__.py:681`), `usage()` (l.824); `records/rights.py` `embeddable` (l.215).
- Absent by design: `run/manifest_v2.py`, the two new schemas, the F8 catalogue codes (add, per ADR 0058 C3, only the
  ones WO1 itself raises; the rest come with WO2/WO3).
- `job_operation: run`, `run_kind`, `documents` belong to ADR 0066 (0.8): define `run_kind` and `documents` as
  optional schema members only; nothing in 0.6 fills them.
- In 0.6 no production run writes a v2 manifest (v2-compiled runs come with F6/WO6, 0.7). WO1 adds no writer path to
  any existing run; WO2's test-only factory will be the first writer.
- `extensions_used` is top level and structural (D2's departure from ADR 0060 D9); `environment.registry` is
  non-structural.

## Acceptance (judged on these alone)

1. **E-F8-10:** every v1-path manifest and artifact is byte-identical to pre-F8: F0
   (`python scripts/corpus_identity.py --check`) PASS on all nine checks (M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52,
   M8 105/105, M9 42/42), and WO6b's `tests/test_f2_amendment9.py` passes.
2. **E-F8-2 schema part:** new tests in `tests/test_f8_manifest_v2.py`: a v2 manifest with every D2 member validates
   against `run-manifest.schema.json`; its `structural_sha256` covers `data_lock_sha256`, `extensions_used`, `run_kind`,
   `documents` and not `bundle_format` or `environment.registry` (mutate each, assert move or no move); a v1 manifest's
   `structural_sha256` is unchanged; `records-index` and `run-evidence` documents validate and reject an unknown member;
   a replay report with `forced_replay` is refused `construct_unavailable(forced_replay, TX)`; the new artifact kinds
   are accepted in `job.schema.json`.
3. The tests that touch `run/` and `schemas/` pass (name the files and counts), plus any schema round-trip or
   generator `--check` the repo runs over `schemas/` (find them; a served digest that moves is a STOP: commit nothing
   further and report). ruff, ruff format --check, mypy src clean.

Commit named paths only, never `git add -A`; do not push. Make sure no background job of yours runs before you
report. Report in 200-300 words: commits, acceptance results with real numbers, DECISIONs, anything left over.
