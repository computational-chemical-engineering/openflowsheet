# OPT — build decisions and facts

Normative: `docs/design/OPT-revision-optimisation.md` (ADR 0071, Proposed), §4, §5 work orders, §6 gates. One line per
choice: `DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.` Measurements carry the command that
produced them. The design-lane ruling round is folded into OPT's single `reviewer` pass.

## WO-1 (NLP host protocol, `Syn001NlpHost`)

- D-1. DECISION: how G2 is measured → `scripts/opt_m03_dump.py ROOT OUT [--nlp]` dumps, keys sorted, floats by `repr`
  and arrays as float64 hex: readiness (NLP-1, NLP-INF, E01 TAC binding) with a test-double probe, `verify_candidate`
  at every start and at NLP-1's reference optimum (A32), the unsupported report, `FullSpaceNlp` at start 0 (document,
  point, bounds, scalings, residual and Jacobian, outputs and their Jacobian at the start and a moved point), and with
  `--nlp` the solved reports of all three. **Masked member: `wall_time_s` only** (one of the ≤ 3 G2 allows). Run once in
  the base tree, once in the changed one, `cmp`. Alternative: `scripts/e01_m03_dump.py` alone (NLP-1/NLP-INF reports
  and the Pyomo model; no E01 binding, no default-env documents) — also run, see G2 below. Reversible by: deleting
  the script (nothing imports it).
- D-2. DECISION: what the §4.1 protocol needs beyond the note's list → `CertifiedPoint.spec` (the bound problem at the
  point; V2's scaling and E01's twin need it, and the revision binding has it) and `CertifiedPoint.handle` (the host's
  own; neither compared nor serialised); `NlpHost.base_spec()` (readiness's `UNKNOWN_DECISION`/`UNKNOWN_VARIABLE`
  read the base problem); `sensitivity(..., mode=)` (Q3 is forward, V5 adjoint); `DecisionRefusedError(ValueError)`
  for values refused before any solve (`with_pinned`'s refusal; M03 records it as `SPECIFICATION_REFUSED`). Every M03
  entry point takes `NlpHost | Syn001Flowsheet` through `as_host`, so no caller or test changes. Alternative: hosts
  only, callers rewritten (G2's "tests unchanged" forbids it). Reversible by: the WO-1 commit.
- D-3. DECISION: the SYN-001 twin → `Syn001NlpHost.twin(ids)` compiles once from the **base** flowsheet and is reused
  at every start (the note's "cached by the host"); `FullSpaceNlp.property_calls()` counts from the problem's own
  construction, as the assessment twin's count already did. M03 compiled one twin per start from the start's pinned
  flowsheet. Inert because decisions are symbolic in the twin: `tests/test_opt_host.py` checks base vs pinned twin
  residual and both Jacobians bitwise at all three NLP-1 starts and a moved point; G2 shows the reports' counters
  unchanged. Alternative: compile per call. Reversible by: dropping the cache in `host.py` (one dict).
- D-4. DECISION: a refused decision in `verify_candidate` → re-raise the host's cause, so SYN-001 still raises
  `with_pinned`'s own `ValueError` (the type name lands in `solve_start`'s note). Alternative: let
  `DecisionRefusedError` through (a changed note text on that path). Reversible by: one `except` clause.
- D-5. DECISION: where a start's point lives → `StartReadiness.point` (in memory, `compare=False`, not in
  `as_document`); `start_closure` takes the start's problem from its point instead of re-pinning the flowsheet; the
  adapter builds `FullSpaceNlp` from it. Alternative: re-certify in the adapter (a second production solve per start).
  Reversible by: the WO-1 commit.
- D-6. DECISION: `verification.declared_regimes(flowsheet, state)` → removed (no caller left; `RegimeRecord.declared()`
  replaces it). Reversible by: restoring the three lines.
- D-7. DECISION: `FullSpaceNlp` on a held system with held columns or label rows → `ValueError` until WO-4 restricts the
  primal (§4.4); SYN-001 has neither. A foreign host with a bare state mapping → `TypeError` (only SYN-001 has M03's
  pinned-flowsheet calling form, `Syn001NlpHost.pinned_system()`). Reversible by: WO-4.

### Gates (WO-1, 2026-11-07, TRS2, worktree `wp/OPT`)

- G2 bit-identity: `scripts/opt_m03_dump.py` base (`ad971d32`) vs WO-1 — default env 19 entries, audited nlp env
  (m05's `.venv-nlp`, `OMP_NUM_THREADS=1`) 22 entries incl. NLP-1 `KKT_POINT_VERIFIED`, NLP-INF `INFEASIBLE_REPORTED`,
  E01 TAC `KKT_POINT_VERIFIED`: **`cmp` identical, both**. `scripts/e01_m03_dump.py` (NLP fixtures + Pyomo component
  list + objective) on a `git archive ad971d32` copy vs WO-1: **identical**.
  Re-run at the WO-1 commit `4b03b8d9`: identical again (base dump sha256 `7b1b526b…` default, `0e423238…` nlp).
- G1: `scripts/corpus_identity.py --check` at `4b03b8d9`: **F0 PASS** — M1 50/50, M2 61/61, M3 61/61, M4 61/61,
  M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35. `studies/` feeds no `implementation_sha256` (M9 untouched).
- G2/G3 tests, default env: `tests/test_opt_host.py tests/test_m03_*.py tests/test_e01_*.py` — 392 passed, 1 skipped
  (`test_e01_b_brightway.py`: no `bw2data` in `.venv`, as before), 22 deselected (`nlp`). Audited env:
  `scripts/m03_nlp_check.sh --no-inventory <m05 .venv-nlp> -- tests/test_m03_nlp_greybox.py tests/test_e01_b_nlp.py
  tests/test_e01_integration.py` — 22 passed. No existing test edited.
- G3's "sensitivity byte-identical with `system=None`" has no subject until WO-2 adds `SensitivityHost.system`;
  WO-1 does not touch `studies/sensitivity.py`.
