# WO-C9-1 — W27 classifier, registration version 2 behind a version switch (build lane)

**Lane:** build (`opus-engineer`), about 100k context. **Branch:** `wp/C9`, in its own worktree. The design lane reviews
the work before merge. **Normative text:** `docs/derivations/W27-registration-v2.md`: W27v2-R01, R04…R09, the states in
§5.2, and the assertions W27v2-A18…A22. **Data:** `benchmarks/m06/openidaes450/registration_v2.json`, written by
`docs/derivations/scripts/w27_registration_v2.py`. Read it as data; never re-derive it, and never import the generator.

## Hard constraints
- Version 1 output stays byte-identical. Leave the bodies of the existing version 1 functions alone: dispatch at their
  top, before any version 1 statement runs. Do not touch `tests/test_m06_w27_coverage.py` (W27v2-A18), any committed
  W27 record, `registration.json`, the version 1 document or its generator.
- Held-out discipline (C2 SPLIT-R08…R10). New tests filter `case_facts.json` and `coverage.json` to
  `split.json#/development` **before** classifying anything. They never print rows or counts. No version 2 record is
  written to a committed path.
- Production code reads no table from the generator or from this brief. Every table comes from `registration_v2.json`.

## Changes
1. **`benchmarks/m06/w27/registration.py`.** Add `REGISTRATION_V2_JSON`, a cached `load_v2()`,
   `provider_methods(version: int = 1)` (version 2 returns `load_v2()["tables"]["provider_methods"]`, and the
   no-argument call is unchanged), and `case_distinct()`.
2. **`benchmarks/m06/w27/coverage.py`.** Add a keyword-only `registration_version: int = 1` to `check_snapshot`,
   `classify_case`, `classify` and `coverage_document`. Version 2 is implemented in new functions:
   - (a)–(e) of W27v2-R07, with W27v2-R08's spelling rule and the message forms of §4;
   - W27v2-R04's serving set, and W27v2-R05's choice: the minimum of (number of `UNIT_UNAVAILABLE` reasons, provider
     id) over the serving routes only;
   - W27v2-R06's joined detail.

   Any version other than 1 or 2 raises `ValueError`.
3. **The version 2 record (W27v2-R09).** Its `schema` is `w27-coverage-v2`. It adds `registration_version: 2` and
   `registration_v2_sha256`, and keeps every version 1 member.
4. **CLI.** Add `--registration-version {1,2}`, default 1. Version 2 without `--out`, or with an `--out` that resolves to
   `registration.COVERAGE_JSON`, exits 2 with a message naming `SPLIT-R10`. It does this before building a snapshot or
   classifying anything.
5. **Tests, in a new `tests/test_c9_w27_v2.py`.**
   - **W27v2-A19:** parametrise over `#/states`. The provider table for each state: `v1` is
     `registration.provider_methods(1)`, `v2` is `provider_methods(2)`, and `v1+lib` is version 1's table plus
     `pr-lib-v1 → cubic_pr`, each with `#/test_provider_methods` added. Compare the refusal string exactly, or
     `class`, `units_judged_on` and the ordered `[kind, subject, detail]` triples.
   - **W27v2-A20:** development rows at the committed snapshot. Each row equals the committed row, compared whole.
   - **W27v2-A21:** the members of the version 2 record.
   - **W27v2-A22:** both CLI refusals, with `coverage.json`'s bytes unchanged.
   - The generator: `python docs/derivations/scripts/w27_registration_v2.py --check` exits 0.
6. **Out of scope:**
   - the `pr-lib-v1` snapshot line (W27v2-R03, A23), which belongs to WO-L01-3;
   - S04's re-take;
   - making version 2 the default, which is the next release's registration's call.

## Acceptance
Run the touched tests, `ruff check .`, `ruff format --check .` and mypy on `benchmarks/`, then `scripts/gate.sh`
before the merge. Write the manifest `evidence/C9/<commit>/manifest.json` with `status: tested`, the commands
actually run, and the counts of passed and new tests. Log every open choice in `docs/C9_DECISIONS.md` as a
`DECISION:` line. A disagreement with the registration is a finding for the design lane. Do not make a local change
for it.
