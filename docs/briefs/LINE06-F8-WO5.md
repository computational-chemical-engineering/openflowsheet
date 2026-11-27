# LINE06 F8-WO5: per-platform reference records (ADR 0067 work order 5)

Build lane, `sonnet-implementer`; an `opus-engineer` reviews the diff afterwards. **Do not spawn sub-agents
yourself.** Rules: `docs/LINE06_RULES.md`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f8`, branch
`wp/F8`, head `369150d3` (clean; WO1 to WO3 done). Logs and scripts under `/home/eajfpeters/.cache/line06/f8-wo5/`
only; wait on log lines, not `kill -0`. Tests: `PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH
PYTHONPATH=src`; F0 with `--log /home/eajfpeters/.cache/line06/f8-wo5/f0-detail.log`. Log every choice as
`DECISION F8-WO5-<n>` (n from 1) in `docs/F8_DECISIONS.md`. Do not touch `.claude/worktrees/f2` or `x06`. Budget about
150k: at the cap, commit what is complete, write where you stopped, and end.

## The task

ADR 0067 D7 as amended (read `docs/adr/0067-F8-identity-replay-evidence.md` section "D7", about line 152, as it stands
at `369150d3`: errata E-D7-1 to 5 are folded in, DECISION F8-WO5-0) and exit E-F8-8. Build `src/openflowsheet/run/
platform_refs.py`, the catalogue entry `platform_reference_used`, and `tests/test_f8_platform_refs.py`. No production
caller is wired in this WO (no reference case has a per-platform record today; the only consumer is the test). Nothing
on the v1 or v2 replay path changes.

## Specification

1. **Platform ids.** `PLATFORM_IDS: dict[tuple[str, str], str]` mapping `(platform.machine(), platform.system())` to
   `linux-x86_64` (x86_64, Linux), `linux-aarch64` (aarch64, Linux), `macos-arm64` (arm64, Darwin), `windows-x86_64`
   (AMD64, Windows). `REFERENCE_PLATFORM = "linux-x86_64"`. `current_platform() -> str | None` (None when unmapped).
   `registered_platform_ids()` derives from `run.replay.REGISTERED_PLATFORMS` (`run/replay.py:61`) through the map; do
   not copy the set.
2. **Layout.** A case is a reference record file `<dir>/<case>.json`. A per-platform record is
   `<dir>/<case>.<platform-id>.json` beside it. `platform_record_path(case_path, platform_id)`.
3. **Per-platform record document** (a plain JSON object, closed):
   `{"platform_reference_format": "openflowsheet-platform-reference-v1", "case": "<case>", "platform": "<id>",
   "reference_platform": "linux-x86_64", "reference_sha256": "<sha256 of the reference record's canonical JSON>",
   "departures": [{"path": str, "reference_value": float, "platform_value": float, "bound": float, "ratio": float,
   "near_threshold": bool}, ...], "artifacts": <the record, same shape as the reference record's>,
   "self_sha256": "<hex>"}`. `self_sha256` is SHA-256 of `openflowsheet.canonical.canonical_json` of the document
   without `self_sha256` (canonical JSON, so line endings do not matter, ADR 0060 D3). `departures` is non-empty and
   sorted by `path`; `ratio = |platform_value - reference_value| / bound` and is > 1 (a per-platform record exists only
   where a float exceeds the policy). The reference record's own shape is `{"artifacts": {...}, ...}`; R0 is
   `run.identity.r0_projection(record["artifacts"])` (`run/identity.py:65`). If the existing reference-shaped records
   you can find carry their artifacts under another key, log a DECISION and keep one accessor function.
4. **Loader and validation.** `load_platform_record(path)` validates the above and raises `ValueError` naming the rule
   for: wrong format, `platform` not registered, `platform == REFERENCE_PLATFORM`, an unregistered platform (E-D7-3),
   a bad `self_sha256`, empty or unsorted `departures`, a `ratio` <= 1 or not equal to the formula (to 1e-12 relative).
5. **Selection.** `select_reference(case_path, platform_id) -> (artifacts, used: str | None)`: the per-platform
   record's `artifacts` if `<case>.<platform_id>.json` exists, else the reference record's, with `used` the platform id
   only in the first case. `compare_to_reference(case_path, emitted_artifacts, platform_id, *, policy_id,
   variable_kinds=None) -> (differences: list[str], notices: list[Coded])` calls `run.compare.differences(emitted,
   selected, policy_id=..., variable_kinds=...)` and, when a per-platform record was used, adds the notice
   `platform_reference_used(<platform-id>)` (the `Coded` type WO3 uses in `run/replay_v2.py`, see `coded_reason` l.99).
6. **Invariant.** `invariant_problems(case_path) -> list[str]`: for each per-platform record of the case, (a) it loads
   (4), (b) its `reference_sha256` equals the reference record's, (c) its `r0_projection` equals the reference's
   (canonical-JSON equality). `all_cases(roots)` finds every `*.<platform-id>.json` with a known id under the given
   roots; the test sweeps `tests/fixtures`, `benchmarks`, `corpus` (those that exist) and asserts no problem (today it
   finds none: assert and print the count, and say so in the report).
7. **Catalogue.** `platform_reference_used` in `src/openflowsheet/messages/catalogue/replay.yaml`, class `notice`,
   one parameter (the platform id), full entry with `complete: true` following the four WO3 entries there (DECISION
   F8-WO3-10). Then `scripts/doc_pages.py` and the catalogue digest re-pin of the two `message_entry` fixtures in
   `tests/test_t07_w5e_application_results.py`, logged old -> new. Any other served-digest move is a STOP.

## Acceptance (judged on these alone)

`tests/test_f8_platform_refs.py`, tests named after the exit:
1. **E-F8-8 selection:** with a synthetic case in `tmp_path` (a reference record from a WO2 factory bundle's artifacts,
   `tests/f8_bundle_v2_support.py`, and a per-platform record for `linux-aarch64` with one float moved beyond the
   policy), `compare_to_reference(..., "linux-aarch64")` returns no differences and the notice; for `linux-x86_64` it
   uses the reference, returns the moved float as a difference, and no notice.
2. **E-F8-8 fake platform:** monkeypatch `REGISTERED_PLATFORMS` (and the map if needed) to register a fake platform;
   a beyond-policy float compared against the reference fails, against its own record passes and reports
   `platform_reference_used(<fake>)`.
3. **E-F8-8 invariant:** the sweep over the repository finds no problem; on synthetic cases, a per-platform record whose
   R0 differs (an id or a counter changed) is reported; a stale `reference_sha256` is reported.
4. **Refusals:** each rule of spec 4 has a test (unregistered platform, reference platform, bad self-hash, ratio <= 1).
5. **Mutation controls:** name one per test group that makes it fail (for example: `select_reference` ignoring the
   platform record; the invariant skipping R0).
6. F0 PASS (M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42); `tests/test_f8_*.py`,
   `tests/test_x07a_*.py`, `tests/test_k05_replay.py`, the MSG suites, `tests/test_t07_*`, `tests/test_t08_w2_*`,
   `tests/test_m07a_surface_chain.py` pass except the three known `tests/test_v03_semantic_roles.py` reds (F2's). ruff,
   ruff format --check, mypy src clean.

Commit named paths only, never `git add -A`; do not push. No background job of yours may run when you report. Report
in 200-300 words: commits, test counts per file, the F0 line, the re-pin (old -> new), DECISIONs, anything left over.
