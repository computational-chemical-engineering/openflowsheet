# Brief — T05 implementation review

**To:** `reviewer` (design lane). **From:** the session (build lane), 2026-09-25.
**Design under review:**
- `docs/derivations/T05-unit-models-spec.md` (A00–A27; §12.2 errata of 2026-09-25);
- `docs/adr/0011-unit-models-ph-closure-and-reaction-datum.md` (Proposed);
- `docs/design/T05-generalization.md` (the architect's W0.2 design; work orders W1.a–W1.d, §8);
- reference `benchmarks/t05/reference_values.yaml` (SHA `af4a543f…`), twin `docs/derivations/scripts/t05_reference.py`.

**Implementation:** `wp/T05`, `279b2eb..HEAD` (build lane). `git diff --stat 279b2eb..HEAD -- src scripts`
lists 25 files, +7591/−35. Documents in that range are the design lane's and not under review.
**Deliverable:** `docs/reviews/T05-review.md` in the shape of `docs/reviews/T04-review.md`: a verdict;
must-fix, should-fix and notes, each with a `file:line` anchor and a falsifiable test that would catch
it; a "FOR FRANK" section if anything needs him. Do not commit and do not edit `src/`, `tests/` or the
spec/design documents — the build lane commits your file. Never set `reviewed`.

**Concurrently**, the `specifier` is ruling on six open questions in `docs/briefs/T05-rulings.md`
(kernel mid-jump conditioning; `sum()` vs left-to-right in the general verifier; the missing
splitter energy check; W0.8's dormant-outlet outcome, rank-3 structure and `TWO_PHASE` fingerprint
at zero flow; digests in the `t05` identity key; C3's bound margin). **Do not re-rule those**; you may
note an interaction with them.

## 1. What was built (where)

| Item | Where |
| --- | --- |
| PH kernel (§4.4) | `models/syn001/ph_kernel.py` |
| Six models (§5–§10) | `models/syn001/{ph_flash,valve,pump,conversion_reactor,component_separator,heat_exchanger}.py`, shared `admission.py`; row builders added in `models/rows.py` (`energy_row(sink=)`, `work_row`, `reaction_balance_row`, `extent_row`), `tp_state.stream_enthalpy_terms` |
| F3/F6 | `models/__init__.py` (`manifest_document(package=)`, `UnitEvaluation.work/extent/transferred_duty`) |
| W1.a split registry, mass mapping | `orchestrator/splits.py` (`SPLIT_RULES`, `lifted_splits`, `check_agreement`), `orchestrator/mass.py` (`residence_time`) |
| W1.b revision flowsheet | `models/revision_flowsheet.py` (`parse_revision`, `RevisionFlowsheet`, `traverse`), `application/revision_binding.py` (`MODEL_BUILDERS`, `bind_revision_flowsheet`) |
| W1.c executor | `orchestrator/revision.py` (`initial_state`, `plan_revision`), `orchestrator/executor.py` dispatch, guards in `tear.py`, `run/session.py`; fix `3e8476d` (a refused second traversal) |
| W1.d / W12 verifier | `verify/table.py` (`MODEL_CHECKS`, `revision_checks`), `verify/certificate.py` (`_issue` extraction, `verify_revision`, `verify` guard), `verify/checks.py` (`bounds_checks(streams=)`) |
| W11 cases | `benchmarks/t05/cases/SYN-001-UL-C{1,2,3,3X}.yaml`, `benchmarks/registry.yaml` family `SYN-001-UL` |
| A24 | `scripts/t05_identity.py`, `scripts/k05_structural_identity.py` (`t05` key) |
| Tests | `tests/test_t05_*.py`, helpers `tests/t05_support.py`, `t05_trial_states.py`, `t05_syn001_shaped.py`, `t05_w12_support.py` |

## 2. What was run, with numbers (`docs/t05-measurements.md` has all of them)

- Gate 2417 green (1915 at baseline). After every merge: `thermo/syn001.py` `75c9d5ba…`; K05
  `structural_sha256` `4ce030ca…`; `check_policy_sha256` `21c44e10…`; splits repr `fc36484e…`;
  fixtures `1303efa7…`; identity document `b364bb3d…` (now minus `t05`); T02 floats `9a8a5baf…`.
- Every registered unit case, construction refusal, trial-state row/Jacobian (at the twin's 53-bit
  floors), A06 (≤ 6e-8 τ), A15, A16 (four codes by constructed cases).
- W1: SYN-001-shaped revision — traversal pass 2 and `initial_state` bitwise equal to legacy;
  `CONVERGED` in 3; 146 checks `VERIFIED`; 42 legacy↔general check pairs bitwise at a root and x⁰.
- C1/C2/C3 `CONVERGED` from `traversal-G0-v1`, within §11.5; certificates `VERIFIED`, 160/116/139
  checks, bounds 8.1e-14/3.9e-15/3.2e-9, witness ≤ 2.9e-11. C3X typed `INITIALIZATION_FAILED` at
  U-HX `temperature_cross(cold_end)`; its twin state `FAILED` on exactly `cold_end = +10 K`.
  A22 injections reproduce (≥ 4.7e3 τ). A27 rows as design §5, 0 residual/Jacobian calls.
- CI pair on `wp/T05` at `a4892be`'s parent: see run 36080722051 (identity job compares `t05`).

## 3. Where the build lane is least sure (spend your time here)

1. **R-016 independence of `verify/table.py`** (1195 lines): no path from the table into row
   builders, evaluators, the kernel or `admission.py`; formulas as spec §12.2 with the note's §4.3
   order; one-sided semantics; declared-phase admissibility per port.
2. **The executor dispatch (`executor.py`, `revision.py`)**: that no SYN-001 path changed behaviour
   (the identity evidence says so, but check the code), that `_reject_initializer`'s refactor is
   inert, and `initial_state`'s owned-variable and split filling (`duty` vs `transferred_duty`).
3. **Residual/Jacobian ↔ evaluator agreement** in each model: the rows and the causal evaluator
   describe the same function (CLAUDE.md), especially lifted outlets (valve, reactor, PH flash), the
   pump's isothermal block, the exchanger's `sink`, and the separator's lifted-inlet enthalpy (which
   duplicates `TPFlash._inlet_enthalpy` — note in `docs/T05_DECISIONS.md`).
4. **The revision encoding** (`revision_flowsheet.py`, `revision_binding.py`): R1–R6, no defaults,
   the unit check, pin consumption, `configuration_sha256` coverage (A03's flowsheet half).
5. **Tests that verify nothing**: tests that read expected values from the implementation, or
   compare a function with itself; the engineers' interpretations in `docs/T05_DECISIONS.md`.

## 4. Do not spend time on

Style and formatting (the gate enforces ruff/mypy); the SYN-001 legacy code itself; the six
questions in `docs/briefs/T05-rulings.md`; the evidence manifest (written after your review).
