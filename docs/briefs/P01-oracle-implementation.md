You are Opus 5, second model on work package **P01** (lead: Fable 5.1, who wrote the specification you implement and will verify your result). Read `CLAUDE.md`, `docs/progress.md`, `docs/implementation-plan.md` §1.3, §2.1–2.2, §3, §4.1 row P01, §7, and blueprint §4.1–4.4, §6.2 before changing anything. Then read, in full, the Fable-authored P01 documents on this branch:

- `docs/adr/0001-state-units-zero-flow.md` (binding semantics: units, `kind`, state definition `nTP-v1`, zero flow, signs, reference conventions)
- `docs/derivations/SYN-001.md` (derivation; §5 oracle algebra; §7 variant table; §9 tolerances/scales/initializer)
- `docs/derivations/SYN-001-oracle-spec.md` (the interface, algorithms, registry entries, and required tests you must implement exactly)
- `docs/interfaces-frozen.md` (frozen names; do not create Protocol classes yet)
- `benchmarks/syn001/reference_values.yaml` (Fable's independent 20-digit reference values; never regenerate it from your oracle; do not edit it — if you believe a value is wrong, write the evidence in `docs/progress.md` under "Handoff and escalation notes" and keep the failing test failing)

You are in an isolated git worktree branched from `wp/P01`. Run `git status`, `git log --oneline -5`, `git branch --show-current` first; rename your branch to `wp/P01-opus` (`git branch -m wp/P01-opus`). All commits go there with messages starting `P01:` and ending with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Never merge, never touch main or wp/P01.

Environment: use the repository's `.venv` recipe (`make venv` or `python3 -m venv .venv && .venv/bin/pip install -r requirements.lock && .venv/bin/pip install -e .[dev]`; see `docs/baseline-report.md`). All checks must pass with `scripts/check.sh` (ruff, ruff format, mypy strict on src, pytest). Do not add dependencies. Do not use placeholder success paths; unimplemented behavior raises or returns an explicit unsupported result.

## Deliverables

### A. Oracle (`benchmarks/syn001/oracle.py`)
Implement exactly the public interface and normative algorithms in `SYN-001-oracle-spec.md` §1–§2. Make `benchmarks/` and `benchmarks/syn001/` importable packages (`__init__.py`) and add `pythonpath = ["."]` to the pytest config if needed; also add `benchmarks` to the mypy/ruff scope so it is type-checked strictly. The module must not import `process_runtime` (spec §5; test K enforces it). Keep it pure Python + `math`; annotate fully.

### B. Registry and fixture inputs
- `benchmarks/registry.yaml`: register the family and every case in spec §3 with the listed fields (fresh feed, T_feed, T_heater, T_flash, P, r, tolerances from derivation §9, scales, registered initializer, oracle callable path, reference path, independence statement, budgets, expected outcome/class). Include `schema_version: 1` and a top-level `blueprint_sha256` equal to the value in `docs/requirements.yaml`.
- `benchmarks/syn001/cases/<case_id>.yaml`: one ProcessRevision document per registered flowsheet case (the five oracle variants plus the conflicting-spec case), validated against the ProcessRevision schema (D below). The revision describes: component set (A, B, C via ComponentRecord references), model instances `feed`, `mixer`, `heater`, `flash`, `splitter`, `vapor_product`, `purge` with parameter bindings, connections S1–S7 as named in derivation §4, and specifications (fresh feed flows/T/P, heater outlet T = 350 K, flash T and P, split fraction r; for the conflicting case additionally a heater duty specification). The `capped-budget` case reuses the nominal revision and differs only in a `solve_policy_overrides: {max_property_calls: 20}` field in the registry, not in the revision.
- `benchmarks/syn001/components.yaml`: the three ComponentRecords (synthetic, `elemental_composition: null`, provenance "plan v1.1 §3.1, synthetic", rights: `synthetic; no restrictions`).

### C. Tests
`tests/test_syn001_oracle.py` and `tests/test_syn001_reference_values.py` implementing every item A–L of spec §4, with the tolerances stated there. Parametrize over the reference YAML rather than retyping numbers. Test IDs must be stable (used in the evidence manifest). A test that fails against Fable's reference values is reported, not weakened.

### D. P01 schemas and round-trip fixtures (`schemas/`, `tests/fixtures/schemas/`, `tests/test_schemas_p01.py`)
JSON Schema draft 2020-12 for: `Quantity`, `ComponentRecord`, `Specification`, `ModelManifest`, `ProcessRevision`, `ValidationReport`. Field requirements come from blueprint §4.1 (table) and ADR 0001:
- `Quantity`: `value` (finite number; reject NaN/Inf via `type: number` plus a runtime check in the round-trip test), `unit` (SI string), `dimension` (7-integer array in the ADR 0001 D1.2 order), `kind` (enum from ADR 0001 D1.3), `meaning` (string), `role` (`fixed | free | decision | derived`), optional `bounds {lower, upper}`, `nominal`, `display_unit`, `uncertainty_ref`. Add a `schemas/units.json` table mapping the kinds to dimensions used by validation, plus a small `process_runtime.units` helper `dimension_of(kind)` and `check_quantity(dict)` (pure functions; this is the only code in `src/` for P01) with tests for the temperature/temperature_difference rule (D1.3) and −0.0 normalization (D1.5).
- `ComponentRecord`: `id`, `name`, `molecular_weight` (Quantity, kind `molar_mass`; add that kind), `elemental_composition` (object or `null`, with `elemental_verification: NOT_APPLICABLE` required when null), `parameters` (map of name → Quantity with `provenance`), `rights` {`source`, `redistribution`, `notes`}.
- `Specification`: `id`, `target` (object path), `value` or `bounds`, `unit`, `tolerance`, `role` (`fixed | free | decision`), `provenance`.
- `ModelManifest`: `id`, `version`, `ports` (name, kind `material|energy|signal`, direction, multiplicity, component mapping, state definition `nTP-v1`, phase capabilities), `mathematics` (equations list or evaluator reference), `derivatives` (declared per output: `analytic|ad|implicit|finite_difference|unavailable`), `initialization`, `validity` (domain), `implementation_artifact`, `execution_requirements`.
- `ProcessRevision`: `schema_version`, `revision_id`, `parent_revision` (nullable), `content_hash` (optional in P01; fixtures omit it — canonical hashing is ADR 0002/K01; never write a fake hash), `component_set`, `instances`, `connections`, `specifications`, `provenance` (actor, operation, timestamp outside the hashed content).
- `ValidationReport`: `revision_id`, `task` (`simulation|optimization`), `status` (`DRAFT | READY_FOR_SIMULATION | READY_FOR_OPTIMIZATION | INVALID`), `checks[]` (id, stage from blueprint §4.3, result, message, implicated_objects), `structural_counts` (free variables, equations, matched, unmatched; may be null in P01 with a stated reason).
Round-trip test: load each fixture YAML → validate → dump to JSON → reload → validate → deep-equal. Include one deliberately invalid fixture per schema (e.g. NaN value, unknown kind, temperature + temperature addition, missing elemental_verification) that must be rejected, and assert the rejection reason. Fixtures for `ProcessRevision` are the SYN-001 case files from B.

### E. Ledger and progress
- `docs/requirements.yaml`: set P01 package status to `implemented` (Fable sets `tested` after verification); add test node IDs to D08 and A04 `tests` lists (status of the requirements stays `planned` — a package test is not requirement closure).
- `docs/progress.md`: under "Handoff and escalation notes", record any ambiguity you had to resolve and every scientific question you could not (Opus does not resolve scientific ambiguity by choosing). Do not change the "Next executable action" line; Fable does.

### F. Report
Final message to Fable: branch, commit hashes, file list, exact `scripts/check.sh` output (test counts, ruff/mypy results), the oracle's printed nominal values (q, L, V, x, y, Q_heater, Q_flash) and the phase states of all five variants, every test that fails (with the assertion text), and any spec item you could not implement and why. Do not write an evidence manifest for P01; Fable writes it.
