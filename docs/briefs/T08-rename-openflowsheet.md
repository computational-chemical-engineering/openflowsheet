# Brief — rename the project to OpenFlowsheet (before v0.1)

**To:** `opus-engineer` (build lane). **From:** the session, 2026-10-02. **Branch:** `wp/T08`.
**Decision (Frank, 2026-10-02):** the project is **OpenFlowsheet**. Full rename before v0.1: product name
**OpenFlowsheet**, distribution **`openflowsheet`** (PyPI name verified free 2026-10-02), import package
**`openflowsheet`** (was the provisional `process_runtime`), console script **`openflowsheet`** (was `process-runtime`).
Not in scope: schema `$id` URLs (stay as they are for v0.1; a v0.2 ADR moves them — add backlog item to the release
spec's §6.3 list via the envelope/backlog files only if a test-checked list requires it, else note it in the report);
the GitHub repository name (Frank renames it); historical records.

## Do

1. **Measure first** (before any edit), and record in your report: the K05 identity (`measure_identity`: whole
   `28dd8bf7…`, t07 `a96f17ed…`, minus-t07 `29246e05…`, structural `e62a59a6…`, T02 floats `9a8a5baf…`), the served MCP
   tool list digest (`dbc18fe3…`), the descriptions digest (`171dd768…`), and grep where the strings `process_runtime`,
   `process-runtime`, `clearsheet`, `ClearSheet` occur by category: source, tests, scripts, schemas, docs, evidence /
   historical records, fixtures, CI.
2. **Find what the rename would move that is registered**: does any identity document, run manifest, certificate,
   bundle, fixture or the MCP surface embed the package/distribution/module name (e.g. a recorded `package` field,
   `server.name`, a module path in a plan id or `model_version`, the CLI name in a description)? **If renaming would move
   a registered identity value, a frozen schema byte, the MCP tool list or the descriptions digest — stop and report
   what and why before renaming**; Frank decides (as for R-148) whether that is a substitution-only move.
3. If step 2 is clear (or once the session tells you how to handle what it found): `git mv src/process_runtime
   src/openflowsheet`; update imports everywhere (src, tests, scripts, benchmarks, CI), `pyproject.toml` (name,
   description, scripts, package data), `MANIFEST.in`, `resources.py`, the `_data` symlinks, mypy/ruff config, the
   README, `NOTICE`, `CHANGELOG.md`, `docs/support-matrix.md` generator inputs as needed, `CLAUDE.md`-adjacent docs that
   describe how to run things (`docs/progress.md` "Start here" commands, not history). Keep a backward-compatibility
   shim? **No** — v0.1 is the first release; no `process_runtime` alias.
4. **Do not edit history:** `evidence/**`, `docs/reviews/**`, `docs/design-history/**`, `docs/decision-register.md`
   past entries, append-only logs (`docs/*_DECISIONS.md`), committed run records (`benchmarks/**/runs/**`,
   `benchmarks/t08/ptc_r1/results-*`, `diagnostic-*`), RC records, `tests/fixtures/t08/v0.0.0-*`. Where a test reads a
   historical record that names `process_runtime`, the test adapts, the record does not.
5. Add register entry **R-149** (format of R-144…R-148): Frank's choice, the scope, the rejected alternatives
   (ClearSheet — several commercial "ClearSheet" products and a spreadsheet connotation; FlowSheet — generic term,
   GitHub org taken; ProcessSim — confusable with Fives ProSim; Certainflow — more distinctive but narrower), the
   deferred schema `$id` move. Next free R-150.
6. Verify: `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh` (threads 1) fully green; reinstall the editable package
   (`.venv/bin/pip install -e . --no-deps`) if needed and say so; identity values unchanged; MCP tool list and
   descriptions digests unchanged; `scripts/t08_dist.py` builds `openflowsheet-0.1.0rc1` sdist and wheel; the CLI
   `openflowsheet solve SYN-001-nominal` works.

## Rules

`requirements.lock` must not change (the project itself is not in it — confirm). Commit in a few coherent commits
(`T08 rename: …`), messages ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`; stage named paths (a `git mv` of the
package is fine; never `git add -A`). Work in this checkout; nobody else edits it. Budget: the user is near a weekly
usage limit — use scripted edits (sed / a small Python rewrite) and verify with grep, not file-by-file reading.

## Report

The step-1 measurements; step-2 findings; commits; remaining occurrences of the old names and why each stays;
`check.sh` counts; the identity and surface digests after.
