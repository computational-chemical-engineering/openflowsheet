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

## WO-2 (revision host: held system, decision map, certify, regimes, bounds)

- D-8. DECISION: where the converged attempt's system is taken → `_solve_region`'s converged branch, from the
  attempt's own `rows`, `free`, `labels` and signature; `held` = every non-free column at the end state's value (the
  attempt writes only its free columns and re-pins its pinned ones at `+0.0`, so these are the values
  `_region_problem` held). The executor clears `final_system` when its property meter turns a converged region into
  `BUDGET_EXHAUSTED`. Alternative: snapshot `_region_problem`'s base vector (same values, more plumbing). Reversible
  by: `bcdcc83d`.
- D-9. DECISION: how `certify` keeps the `RouteRun` and still writes the session's bundle → `write_revision_bundle`
  factored out of `run_revision_session` (pure extraction, same calls in the same order); the host runs `solve_route`
  then `write_revision_bundle`. Bundle sink = `Callable[[candidate document], (directory, run_id)]`, called once per
  certify; `bundle_ref` = the directory. Test: every artifact byte-identical to `run_revision_session`'s for the same
  document, manifest equal but for `started_at`, `elapsed_seconds`, `manifest_sha256`. Alternative: a result callback
  on `run_revision_session`. Reversible by: `26423cfe` and the host's `certify`.
- D-10. DECISION: how G3's "byte-identical with `system=None`" is measured → `scripts/opt_m03_dump.py` gains
  `sensitivity/e01-th-c1/<mode>` (E01's `revision_sensitivity_host` on TH-C1 at A30's two pins, three state outputs,
  modes forward/adjoint/both); M03's sensitivities were already in the dump (readiness Q3, V5). Base re-taken from a
  `git archive 6e58d8b8` copy. Reversible by: dropping the function.
- D-11. DECISION: certify outcomes the design leaves open → candidate refused by the binder: `SPECIFICATION_REFUSED`
  (`<kind>(<detail>)`), no bundle; `RunUnsupportedError`: `UNSUPPORTED`; `VerifierError`: `CERTIFICATE_NOT_VERIFIED`,
  message `verifier_refused: …` (neither writes a bundle, as `run_revision_session`); converged but not `VERIFIED`:
  `CERTIFICATE_NOT_VERIFIED`; a parameter not in the map: `DecisionRefusedError`; a binding that does not hold a written
  decision bitwise: `ValueError` (defect, §4.2.2 guarantees it). Alternative: let `VerifierError` propagate as SYN-001's
  `verify` does. Reversible by: `certify`.
- D-12. DECISION (escalated with F2): margins on providers whose closure judges a single-phase branch by another test →
  `None` (Q4′ refuses `REGIME_MARGIN_UNSUPPORTED`) on `pr-c1-v1` (closure: `classify`) and on a composition-dependent
  K (closure, VAPOR: incipient-liquid ΣW), `tp_margin` elsewhere. Alternative: `tp_margin` everywhere, as §4.2.4
  reads literally. Reversible by: `8f7f34b5`.
- D-13. DECISION: probe semantics → a probe at each finite box end; each probe moves ≤ 1 parameter and nothing
  structural (ids, `configuration_sha256`, label, `row_units`, the parameter id set); across the probes exactly one
  parameter is named, and at every probe it holds the written value bitwise — so an end at the base value (which moves
  nothing) is admitted. No end off the base value → `DECISION_NOT_CONTINUOUS(<spec>): no probe moved a parameter`.
  Every decision is checked; refusals in request order. Alternative: every probe must move exactly one parameter
  (refuses a box ending at the base value). Reversible by: `decision_map`'s body.
- D-14. DECISION: the twin of a held-system sensitivity → the host's cached base twin when the requested parameters
  include every decision (one function, the map admits no other change), else one compiled from the point's own spec;
  Q0′ guards both bitwise. Alternative: always compile from the point. Reversible by: `twin_factory` in `sensitivity`.
- D-15. DECISION: the held path of `evaluate_sensitivity` → Q0′ still compares the full problem; Q1, Q2, the solves,
  Q3 and the outputs run on the system's rows then labels over its free columns; label rows scaled by K03's temperature
  nominal (as the region); an output's coefficient on a held column contributes nothing (a constant). `HeldSystem` is
  imported under `TYPE_CHECKING` (no import cycle). Reversible by: `72482de9`.

### WO-2 facts (design §7, measured 2026-11-07, TRS2)

- **F1 holds.** On TH-R1, TH-C1, TH-V1, M1, M1-recycle, J1, C-MW (default policy, `newton_refined`, one attempt each)
  and a duty-specified `syn001.ph_flash` held LIQUID (4 held vapour columns): the compiled residual selected by the held
  system at the certified state equals the converged attempt's last Newton residual **bitwise** (0 differing entries);
  `RouteRun.state` = region state. TH-R1 has 1 alias row (outside the system); the others none. No corpus flowsheet
  re-opens its region (every one converges in attempt 0), so the multi-attempt case is exercised only by construction.
- **F2 holds** (for ideal-K providers). The closure judges a single-phase branch by `_admissible` whatever the split's
  closure type (`converged` and the trial screen both call it; the PH closure is asked only *after* it flags a trial).
  At the LIQUID PH flash `1 − _admissible value` = `tp_margin` = 0.7381838288171423, bitwise. On `pr-c1-v1` and a
  composition-dependent K the closure's test is another one, for TP- and PH-type splits alike → D-12.
- **F4 (for WO-5).** Thermal `vapor_liquid` ports carry `<S>.sat.V`, `<S>.sat.L` (molar_flow) and rows
  `<U>:sat-T:<port>`, `<U>:sat-split:<port>` (TH-R1: S3–S6; TH-V1: S2–S4; TH-C1: S4, S5): wet ports are held by V, L ≥ 0
  as designed. Declared liquid/vapour ports have no saturation block in the state; their row must come from
  `models/thermal/rows.py` `saturation_temperature_row` (a `RowBuilder`) in the functional program — WO-5 to confirm.
  The thermal cases have no lifted splits (signature `()`).

### Gates (WO-2, 2026-11-07, TRS2, worktree `wp/OPT`)

- G1: `scripts/corpus_identity.py --check` at `8f7f34b5`: **F0 PASS** — M1 50/50, M2 61/61, M3 61/61, M4 61/61,
  M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35.
- G2/G3 bit-identity: `scripts/opt_m03_dump.py` (22 entries, default env) base `6e58d8b8` vs `72482de9` (sensitivity
  held path in): **`cmp` identical** (sha256 `6e028e8d…`); also identical after `bcdcc83d` alone.
- G4, G5, G6: `tests/test_opt_revision_host.py` — 21 passed. G6 numbers (worst over outputs × parameters):
  TH-C1 (B.T_spec, P.P_spec; S4.T, S2.T, S4.sat.V) |fwd − CD|/|CD| 2.6e-8, |fwd − adj|/max 4.7e-16; M1
  (U-FEED1.T_spec, reflux ratio; S02.stage.4.T) 1.7e-8, 1.9e-16; PH flash LIQUID (U-PHF.Q_spec; S3.T) 5.2e-11,
  1.3e-16, Q4/Q4′ pass, status QUALIFIED. Tolerance 1e-5 / 1e-10 (E01 A30).
- G5's "probe changes `configuration_sha256` or two parameters" uses a test double over the real binder: no v1
  specification value can change the configuration (it is the revision minus every pinned value).
- Regression, default env: `tests/test_opt_host.py tests/test_opt_revision_host.py tests/test_m03_*.py
  tests/test_e01_*.py tests/test_t07_w3a_revision_runs.py tests/test_t05_w12*.py tests/test_m05_*.py` — 1070 passed,
  1 skipped. Audited env (m05's `.venv-nlp`): `test_m03_nlp_greybox.py test_e01_b_nlp.py test_e01_integration.py` —
  22 passed. No existing test edited.
- G17 (record): cold certify wall time TH-R1 1.7 s, M1 1.0 s, C-MW 6.3 s.
