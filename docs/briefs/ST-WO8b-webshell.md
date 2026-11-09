# Build brief: ST WO-8b — the three red tests, and the stream table in the web shell (Frank's O3)

Status: brief, 2026-11-08. **Do not spawn sub-agents yourself.** Branch `wp/ST`, worktree
`/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/st`, head `9da2e022` (WO-8a done: ruling 5, R-942/943 clean-up,
main merged at `ef69961d`). Log `docs/ST_DECISIONS.md` (8b-1, 8b-2, …), handoff `docs/ST_HANDOFF.md`. Import path:
run with `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` and `PYTHONPATH=src`; confirm `openflowsheet.__file__`
is the worktree's copy. Merge rule: CI green on both architectures; no local full gate.

## Part 1 — the three tests red since `e1a05916` (one commit each, follow the precedent exactly)

1. `tests/test_t08_w2_support_envelope.py::test_a20_the_axes_equal_the_code`: the envelope's operation axis lacks
   `get_stream_table` (22 → 23). Find how the last package that added an operation (OPT's `optimize`, MSG's
   `explain`, or an earlier one — `git log -S` on `benchmarks/t08/support_envelope.yaml`) admitted it to the
   envelope, and do the same for `get_stream_table`, then `t08_support_matrix.py --emit` / `--check`. If the precedent
   needed a design-lane act (an ADR/ruling) that ST lacks, stop and report.
2. The two ADR 0025 A1 tests (`tests/test_t08_adr0025.py`): ST's schema introduces `data_sha256` and
   `implementation_sha256`, unclassified (ADR 0025 D2.3: never defaulted). Precedent: per-package addenda in
   `scripts/t08_numerical_policy.py` `ADDENDA` (M04 `2a4370aa`, M05 `c6c229e8`, E01 `b474ef71`, OPT `d5533e09`). Read
   what each ST field hashes (code and design note). A digest of bytes/text/code is exact (`exact_sha256`); a digest of
   floating-point state is a float digest. Classify in an ST addendum with the reason in one line each, logged as a
   decision. If either field hashes floating-point values, or is ambiguous, stop and report (design lane).

## Part 2 — the stream table in the web shell (O3; build lane leads the web shell)

3. Frank's O3 (2026-11-08): show ST's table in the web shell now. Today `apps/web/js/screens/streams.js`
   (`#/job/{jid}/streams`, M06 note §6.6) shows n, T, P per stream from the bundle. Add the stream table the way the
   shell shows other operation results: call `get_stream_table` through the shell's API client over HTTP (check the
   HTTP route and `authz` rights exist; ST added the operation on all four bindings), render per stream the columns
   the operation returns (phase fractions, per-phase flows, enthalpy flow, `phase_source`, the boundary flag), SI units
   as the column names say (no conversion, as the screen does), paging as the operation pages (`truncated`/`cursor`),
   and a plain-language notice where a stream has no number (`flash_failed`, with the reason). Keep the existing n/T/P
   view intact. Follow the existing screens' patterns (`h`, `table`, `section`, `common.js`); no new dependency.
4. Tests the shell already has: `tests/test_m06_static_scan.py`, `test_m06_contrast.py`, `test_m06_http_contract.py`,
   `test_m06_fixtures_valid.py`; add a browser-smoke case in `tests/test_m06_browser_smoke.py`'s pattern for the new
   section (it runs in CI where the browser exists; locally it may skip — say so). A fixture for the operation's reply
   if the shell's tests use fixtures (`m06_browser_support.py`).
5. Docs: the web-shell guide page that describes the streams screen (find it under `docs-site/`) gains the table, in
   the guide's style. CHANGELOG line under 0.4 with ST's entry.

## Finish

Targeted tests (one run at a time, `OMP_NUM_THREADS=1`): `tests/test_st*`, `tests/test_m06_*`, `tests/test_t08*.py`,
`tests/test_m07a_harvest.py tests/test_evidence_manifests.py`; `scripts/corpus_identity.py --check` PASS; `ruff
check`, `ruff format --check`, `mypy` clean; `node --check` / the repo's JS lint if one exists. Push `wp/ST`. No
manifest, no merge into main.

## Rules

No relaxed checks, no edited gates, no wall-time budget changes; never set `reviewed`; record no human review. Named
paths only (never `git add -A`); trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. TRS2 shared: `uptime` first, targeted tests
only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`;
nothing in other worktrees. Context cap ~150k: commit, update `docs/ST_HANDOFF.md` (≤ 40 lines), stop.

## Report (≤ 20 lines)

Commits and head; the precedent followed for 1 and 2 and the classification; the screen change (files) and what it
shows; tests (incl. whether the browser smoke ran); F0 line.
