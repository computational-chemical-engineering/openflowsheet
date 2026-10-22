# C9 — build decisions (W27 rules for the next release)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`
- DECISION: where version 2's rules live → a new document `docs/derivations/W27-registration-v2.md` + `registration_v2.json` + its generator, v0.2's files untouched (R-570). Alternative: Amendment 5 inside `M06-W27-registration.md`. Reversible by: folding the text into the next release's registration copy.
- DECISION: numbering → own prefix W27v2-R/A and GC-V2. Alternative: continue W27-R69/A83 (C3 is renaming A80…A82 concurrently). Reversible by: a renumbering table in the document.
- DECISION: serving rule → serving routes only, min (unit-reason count, provider id); no-serve detail = every route's mismatch by provider id joined `;` (R-571). Alternative: first serving route in snapshot order; union of models. Reversible by: a version 3 rule; states A03–A07 show the difference.
- DECISION: refusal (d) → keep routes_per_revision = 1; replace "two routes of one method" by "duplicate provider id"; keep (e) (R-571). Alternative: drop (d) entirely. Reversible by: restoring the shared-method item (mutant `shared_method_refused`).
- DECISION: Co/CO → keep case folding; a case-only collision passes only by a reviewed `case_distinct` entry keyed to the CAS RN; `Co` distinct from 630-08-0, still `unidentified` (R-572). Alternative: case-sensitive formula/id match; alias `Co` → 7440-48-4. Reversible by: deleting the entry or adding an alias in a later version.
- DECISION: a route with no models (pr-lib-v1) → admitted; it judges every non-junction unit `no_model` (R-573). Alternative: refuse it. Reversible by: a refusal item (f).
- DECISION: version switch → explicit `registration_version`, default 1; version 2 has no default output path and refuses the committed `coverage.json` (R-570, R-574). Alternative: default 2 at the next release cut. Reversible by: the next release's registration flipping the default.
- DECISION: ADR → none (0045 unused): a benchmark-registration change, no blueprint/plan departure, no frozen interface. Alternative: ADR 0045. Reversible by: writing it if a reviewer finds a departure.
- DECISION: Frank questions → none; §9 Q-1 (re-report v0.2 under v2) proceeds on its default "no". Alternative: escalate Q-1. Reversible by: appending it to FRANK_QUESTIONS.md.

WO-C9-1 (build lane, `opus-engineer`, commits 9fb2426, d5da151):
- DECISION: W27v2-R04's per-route test and R06's per-route detail → version 1's `_route_detail` called on a one-route view `{"routes": [route]}`, over the method's routes sorted by provider id. Alternative: a new per-route helper shared by both versions (edits a version 1 body). Reversible by: extracting the helper once version 1 may change.
- DECISION: version 2's `classify_case`/`_route_reasons` → new `_classify_case_v2`/`_route_reasons_v2` that repeat version 1's prelude and row form verbatim; version 1 bodies untouched, dispatch is the first statement. Alternative: factor the shared prelude out of version 1. Reversible by: that refactor, proved by A20 and the v1 hash baseline.
- DECISION: R06's join `;` and R05's order (unit-reason count, provider id) → coded from the rule text, as version 1 codes its rules; `registration_v2.json#/rules` is not read. Alternative: read `rules.route_detail_join`/`serving_route_order`. Reversible by: reading them.
- DECISION: R05's count → reasons of kind `UNIT_UNAVAILABLE` from `_unit_reasons` (one per unit key, not per unit). Alternative: count unavailable unit rows. Reversible by: changing the key in `_units_v2`; no registered state separates them.
- DECISION: CLI "without `--out`" → `--out` default `None`, version 1 resolves it to `COVERAGE_JSON`; the refusal compares `Path.resolve()` of both. Alternative: a sentinel default. Reversible by: restoring the default.
- DECISION: a `bool` registration version → `ValueError` (W27v2-R01 accepts only 1 or 2). Alternative: accept `True` as 1. Reversible by: dropping the `isinstance` check.
- DECISION: three W27v2-R08 refusal tests beyond §5.2 (exact spelling despite `case_distinct`; an entry covers only its CAS RNs; no duplicates in (c)), read off the rule text. They catch a mutant the 17 states miss (`case_distinct` exempting a spelling wholesale). Alternative: states only. Reversible by: deleting the test; design lane may register them as states.
- DECISION: W27v2-A18 → checked by `git diff main -- tests/test_m06_w27_coverage.py` (empty) in the manifest, not as a test (CI clones may lack `main`). Alternative: a test shelling out to git. Reversible by: adding it.
- DECISION: WO-C9-1's `evidence/C9/<commit>/manifest.json` → not committed. `schemas/evidence-manifest.schema.json` (frozen, §2.2) admits only `^[PKTMSR][0-9]{2}[a-z]?$` work packages and `[DA]nn` requirements, so `tests/test_evidence_manifests.py` fails on it, and `docs/CLOUD_WORK.md:57` says C-items have no manifest (they merge on the read full gate and CI, recorded in the merge commit). The acceptance record is below instead. Alternative: file it under a plan id (none is assigned to C9) or amend the schema (an ADR). Reversible by: writing the manifest once C9 takes a plan id.

WO-C9-1 acceptance at e3f3ca844ccbf1107ad1363df55161a2595ae81c (status: tested; review pending; full gate not run here, the caller runs it):
- `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_c9_w27_v2.py` → exit 0
- `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_m06_w27_campaign_records.py tests/test_m06_w27_coverage.py tests/test_m06_w27_harness.py tests/test_m06_w27_registration.py tests/test_m06_w27_scorer.py tests/test_c2_openidaes450_split.py tests/test_c9_w27_v2.py` → exit 0
- `.venv/bin/python docs/derivations/scripts/w27_registration_v2.py --check` → exit 0
- `.venv/bin/python -c "from benchmarks.m06.w27 import coverage,facts,registration;import json,sys;c=json.loads(registration.COVERAGE_JSON.read_bytes());sys.exit(registration.dump(coverage.coverage_document(facts.load_facts(),c['snapshot']))!=registration.COVERAGE_JSON.read_bytes())"` → exit 0
- `git diff main -- tests/test_m06_w27_coverage.py` → exit 0
- `.venv/bin/ruff check .` → exit 0
- `.venv/bin/ruff format --check .` → exit 0
- `.venv/bin/mypy` → exit 0
- W27v2-A18: pass — tests/test_m06_w27_coverage.py unmodified against main, and green {"diff_bytes": 0}
- W27v2-A19: pass — the 17 states of section 5.2 through the production classifier (test_a19_registered_state) {"states": 17}
- W27v2-A20: pass — version 2 on the development cases (filtered to split.json#/development first) at the committed snapshot equals every committed row, whole
- W27v2-A21: pass — coverage_document version 2 for H2 at S2: schema, registration_version, registration_v2_sha256, units_judged_on, version 1 members kept
- W27v2-A22: pass — CLI --registration-version 2 with no --out, the committed coverage.json, or a relative path to it: exit 2 naming SPLIT-R10, coverage.json bytes unchanged, no snapshot built and nothing classified
- C9.GEN: pass — w27_registration_v2.py --check
- C9.V1-BYTES: pass — version 1 byte-identity: coverage_document at the committed snapshot equals coverage.json's bytes; every registered state under the v1 and v1+lib tables gives the same SHA-256 before (f578dc7) and after (9fb2426) the change {"state_hash_file_sha256_before": "1776953a8beed8a2d5666d012e58d70e024da78bf34157619301133d8e97e213", "state_hash_file_sha256_after": "1776953a8beed8a2d5666d012e58d70e024da78bf34157619301133d8e97e213"}
- C9.TESTS: pass — test counts {"new_file": {"passed": 31}, "touched_tests": {"passed": 194, "skipped": 26}}
- C9.LINT: pass — ruff check, ruff format --check, mypy
