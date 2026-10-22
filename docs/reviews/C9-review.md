# C9 review: WO-C9-1, the W27 classifier for registration version 2

**Reviewer:** design lane (`reviewer`), 2026-10-22. **Commits:** 9fb2426, d5da151, e3f3ca8, 12062a4 on `wp/C9`.
**Against:** `docs/briefs/C9-WO-1-classifier-v2.md`; `docs/derivations/W27-registration-v2.md` W27v2-R01, R04…R10,
§5.2; C2 SPLIT-R08…R11; R-570…R-574.
**Run:** `pytest -q tests/test_c9_w27_v2.py tests/test_m06_w27_coverage.py tests/test_c2_openidaes450_split.py`
gave 112 passed and 2 skipped. A scratch mutant was run in memory (see S1). No production code was edited.

## Verdict

**Changes requested: one must-fix, one should-fix.** The classifier is sound. Version 1 is untouched, and R04…R09
are coded as written. The new CLI path is where the held-out discipline fails. Merge once M1 and S1 are fixed, the
full gate has been read, and CI is green on both architectures.

## Must fix

**M1. The version 2 CLI prints summary counts that include held-out cases, and it writes held-out rows to any path.**
The code is `benchmarks/m06/w27/coverage.py:908-914` and `:928-929`. It breaks SPLIT-R08 and SPLIT-R10 (b), and the
ruling is **R-580**.

*Scenario.* WO-L01-3 lands the `pr-lib-v1` snapshot line. A development session then runs
`--registration-version 2 --snapshot S2.json --out /tmp/v2.json` to see what changed. Stdout prints `all 450` and
`full 82` class counts for a snapshot that has never been scored. Subtracting the development rows gives the held-out
class counts outside a release gate, and they are reported mixed with the development half rather than separately
(SPLIT-R08). `/tmp/v2.json`, or a tracked path with no `heldout` segment, then holds held-out rows that a development
agent can open, which is an exposure under SPLIT-R11. R-574 says such a record "goes under a `heldout/` path", but
nothing enforces it.

*Minimal fix.* Version 1 stays as it is. Under version 2:
1. Before any snapshot is built or any case classified, refuse with exit 2 when the resolved `--out` has no directory
   segment named `heldout`. The message names `SPLIT-R10`.
2. Print only the output path, the snapshot SHA-256 and G14's pass or fail. Print no `summary` line.

*Tests.*
- Add a non-`heldout` `tmp_path` target to A22's parametrisation (exit 2, nothing written).
- In `test_cli_writes_v2_to_another_path_and_v1_to_its_default`, assert that the version 2 run's stdout contains
  neither `all 450` nor `full 82`.

## Should fix

**S1. Nothing pins W27v2-R06's "sorted by provider id".** The sort is at `coverage.py:707-710`, and the gap is in
`tests/test_c9_w27_v2.py`. A07 runs on S2, whose routes are already in provider-id order (`pr-c1-v1`, then
`pr-lib-v1`). I tried a mutant that joins the details in snapshot order: all 17 states still pass, and so do
A20/A21, which have one route or a serving route. On S2r with H2-VL the mutant gives
`route_mismatch:pr-lib-v1:…;route_mismatch:pr-c1-v1:…`.

*Fix.* Add a test that runs H2-VL at S2r under version 2 and expects A07's triple. That expectation reads directly
off R06's text. The design lane may later register it as a state.

## Notes

- **N1 (needs a decision; the release registration, C2 §11 Q-1).** W27v2-R09 keeps version 1's `summary`. A
  whole-archive record therefore stores `all_450.cases_with_reason`, a frequency of blocking reasons over a set that
  contains held-out cases, which SPLIT-R09 forbids recording. A (c) refusal on a whole-archive run also prints the
  archive spellings of held-out cases. The code is faithful to R09, so this is not WO-1's to change. My lean: a
  release-gate record summarises each half separately, with class counts only for the held-out half, and a (c) item
  that only held-out cases trigger is named by `sha256(spelling)[:12]`. Settle this before the first release-gate run
  under version 2.
- **N2.** `registration.provider_methods(True)` returns version 1's table and `provider_methods(2.0)` returns version
  2's (`registration.py:83-89`), while `coverage._version` rejects a bool. Nothing is harmed, because every caller
  passes an int literal. The function could reuse the same check.
- **N3 (architecture).** `_classify_case_v2` and `_route_reasons_v2` repeat about 70 lines of version 1. The
  constraint that leaves version 1's bodies untouched forces this, and the repeat is logged. Fold the two together
  when version 2 becomes the default.
- **N4.** There is no evidence manifest. That is consistent with `docs/CLOUD_WORK.md:57` (C-items have none) and
  with the acceptance record in `docs/C9_DECISIONS.md`. The full gate has not run yet.

## Checked and sound

1. **Version 1 byte-identity.** In all four public functions the dispatch is the first statement. The only lines
   removed from version 1 are docstrings, signatures and the CLI's `--out` default, which resolves to the same path.
   `tests/test_m06_w27_coverage.py` is unmodified, and its lines 832-848 pin the reproduction of `coverage.json`.
2. **R04…R09.**
   - R04: the serving set uses version 1's per-route test on a one-route view.
   - R05: the minimum of (`UNIT_UNAVAILABLE` count, provider id) is taken over the serving routes only. Null is
     returned for no package, for several groups, and when no route serves.
   - R06: `no_route:<m>` when the method has no route.
   - R07: (a) to (e) in order; (c) is a sorted set; (d) refuses duplicate provider ids and no longer refuses routes
     that share a method.
   - R08: both clauses hold, with `case_distinct` keyed by the exact spelling.
   - R09: the members are right.
3. **Held-out discipline in the tests.** A20 filters to `split.json#/development` before classifying. A failure names
   development ids only. The CLI tests use synthetic H2 or patch `load_facts`. The generator's `--check` filters to
   development first.
4. **The A19 harness** compares refusal strings exactly, and otherwise compares the class, `units_judged_on` and the
   ordered triples. The d5da151 tests catch a mutant that exempts a spelling wholesale through `case_distinct`.

**Not examined:** the generator's internals (67b12ec, design lane), `_unit_reasons` and `_component_reasons` beyond
how version 2 reuses them, ruff, mypy, the full gate and CI.
