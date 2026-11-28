# LINE06 F8-WO3: replay of a v2 bundle (ADR 0067 work order 3)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f8`, branch `wp/F8`, head `886113ea` (clean; WO1, WO1b, WO2
done). Logs and scripts under `/home/eajfpeters/.cache/line06/f8-wo3/` only; wait on log lines, not `kill -0`. Tests:
`PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=src`; F0 with
`--log /home/eajfpeters/.cache/line06/f8-wo3/f0-detail.log`. Log every choice as `DECISION F8-WO3-<n>` in
`docs/F8_DECISIONS.md`. An engineer works in `.claude/worktrees/f2`; do not touch it. Budget about 150k: at the cap,
commit what is complete, write where you stopped, and end.

## The task

ADR 0067 (`docs/adr/0067-F8-identity-replay-evidence.md`) work order 3: the one dispatch line in `run/replay.py`,
`run/replay_v2.py` implementing D5's seven steps in order (line ~95), the usage cross-check (step 7), the Python
`ReplayReport`/`ReplayMode` members of Amendment 12 (`registry_comparison`, `data_availability`; `forced_replay`
stays refused, WO1-6; their schema shapes exist since WO1b), the new catalogue codes it emits (ADR 0067 "New catalogue
codes", ADR 0058 C3: full entries, `complete: true`, then `scripts/doc_pages.py` and the catalogue digest re-pin of
the two `message_entry` fixtures in `tests/test_t07_w5e_application_results.py`, logged old -> new), and a re-record
tool for registered v2 cases (test or `scripts/` tooling, not a served operation). Read D1, D2, D5, D9, "Exit
tests", and `docs/F8_DECISIONS.md` (WO1 to WO2; note WO2-6: the v1 `read_manifest` raises `TypeError` on a v2
manifest, so dispatch on `bundle_format` before calling it).

## Facts established

- The only v2 bundles in 0.6 are the WO2 factory's (`tests/f8_bundle_v2_support.py` `record_v2`; GP-C1, TH-C1).
  No production run writes one; nothing on the v1 path may change (E-F8-1, E-F8-10).
- `run/bundle_v2.py` has `read_manifest`, `verify_bundle`, `records_index`; the D11 rights functions and the record
  store are in `records/`; `Registry.snapshot`, `extensions_used`, `usage()` in `registry/__init__.py` (l.625, l.681,
  l.824).
- Premise to check first and log: D5 step 7 reruns "the recorded documents with embedded records served before the
  store". The factory's recorded revision is a v1 document, whose binder reads the legacy YAML files, not the
  store. State in a DECISION how the rerun consumes (or provably does not need) the embedded records, and how
  E-F8-4's "with the record embedded, the replay runs and matches" is then shown. If D5 cannot be met as written
  for these bundles, do not invent a semantics: build steps 1 to 6 and the rest of 7, log `STOP F8-WO3-<n>` with the
  measured facts, and report.

## Acceptance (judged on these alone)

Tests in `tests/test_f8_replay_v2.py`, one or more per exit, named after it:
1. **E-F8-1:** every committed 0.3.0 bundle replays with the same mode, verdict and reasons and a `ReplayReport`
   byte-identical to the pre-F8 report (compute the pre-F8 reports at `ddac950f` or from the committed expectations;
   state which).
2. **E-F8-4:** a referenced record absent from the store gives `inspected_archived_results` / `NOT_RUN` with
   `data_unavailable(<sha>)`; two absent, both listed, sorted; embedded, the replay runs and matches.
3. **E-F8-5:** changed `self_sha256` of a used non-built-in extension -> `extension_changed`, `NOT_RUN`; of a used
   built-in -> `compatible_reproduction` with reason `extension_changed`, rerun and compared; a changed unused one
   changes neither mode nor verdict and is counted in `unused_differences`; the recorded snapshot equals ADR 0060
   D10's document. (A test-only registry is fine; say how the changes are made.)
4. **E-F8-6:** for every factory bundle the usage set is a subset of `extensions_used`; a test-only hidden `resolve`
   makes the replay `MISMATCH` with `extension_use_undeclared`.
5. Plus: an unknown `bundle_format` -> `bundle_format_unsupported(<value>)`. F0 PASS (M1 50/50, M2-M5 61/61, M6
   85/85, M7 52/52, M8 105/105, M9 42/42); `tests/test_f8_*.py`, `tests/test_k05_replay.py`, the MSG suites, the
   surface suites (`tests/test_t07_*`, `tests/test_t08_w2_*`, `tests/test_m07a_surface_chain.py`) pass except the
   three known `tests/test_v03_semantic_roles.py` reds (F2's). A served-digest move other than the catalogue digest
   re-pin is a STOP. ruff, ruff format --check, mypy src clean. Mutation controls: name at least one per exit that
   fails the matching test.

Commit named paths only, never `git add -A`; do not push. Make sure no background job of yours runs before you
report. Report in 200-300 words: commits, test counts per file, the F0 line, the step-7 premise DECISION, re-pins,
anything left over.
