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

## WO-3 (request schema, formulation, static readiness, probe, `validate` lift)

- D-16. DECISION: the platform-aware probe → `audited_solver(platform_id=None)` also requires
  `running_platform()` = `<sys.platform>-<platform.machine()>` in `AUDITED_PLATFORMS = ("linux-x86_64",)`; the
  platform's problem is appended last, so M03's detail on linux x86-64 is unchanged byte for byte, and elsewhere the
  detail (the report reason's, §2.7) names the platform. The API refusal is `unsupported`, message
  `nlp_solver_unavailable` (bare, as §4.11 and ADR 0071's catalogue list it), pointer `/task`: one text on every
  platform, so the CLI pin (`tests/fixtures/t07/cli-existing-commands.json`) holds on both CI legs. (A first cut named
  the platform in the message; the pins made it architecture-dependent.) Alternative:
  `nlp_solver_unavailable(<platform>)`. Reversible by: `dbed6c58` and the message commit.
- D-17. DECISION: the new codes' places → `READINESS_ORDER` follows §4.5's table: REVISION_MISMATCH, REVISION_UNBOUND,
  OPTIMIZATION_ROUTE_UNAVAILABLE first; DECISION_UNIT_NOT_INTERNAL, DECISION_NOT_CONTINUOUS after UNKNOWN_DECISION;
  TOO_MANY_STARTS after START_OUTSIDE_BOUNDS; REGIME_MARGIN_UNDEFINED after ASSESSMENT_OBJECTIVE_UNSCALED. M03's
  relative order kept (tested). START_NOT_CERTIFIED and PHASE_REGIME_CHANGED are start/report reasons (WO-4/WO-5).
  `optimization-report.schema.json` `$defs/reason` enumerates codes; it is **not** extended here (no report with a new
  code exists before WO-4; the schema edit is Amendment 16's, WO-4/WO-6). Reversible by: `dbed6c58`.
- D-18. DECISION (escalated): static assessment checks → statically only "an `assessment:<id>` named with
  `assessment: null`" (`ASSESSMENT_OUTPUT_UNKNOWN`). Whether the program publishes an output and whether a decision is a
  θ (`ASSESSMENT_PARAMETER_STRUCTURAL`/`_DECISION`) need the program, which E01 plans at a solved state
  (`AssessmentProgram.build(view, host_spec, spec, state)`); they move to the first certified start (where §4.5 takes
  the binding's scales anyway). In `validate` those three checks PASS with the message "an assessment is given; … judged
  at the first certified start". Consequence: G18's "one test per static reason" has no failing static case for the two
  `ASSESSMENT_PARAMETER_*` codes. Alternative: plan the program at the unsolved initial guess (a planning state that is
  not a solution), or NOT_RUN (no request with an assessment could ever be `READY_FOR_OPTIMIZATION`). Reversible by:
  `request.py` `static_readiness` and `validation.ASSESSMENT_AT_START`.
- D-19. DECISION: the application `validate` member → `LocalApplication.validate(revision_id, task)` keeps its
  signature; the `optimization` member, the served `validate` input schema, the decode and `descriptions/validate.md`
  change together with OPT's surface link (WO-6, §4.13 `strip_opt`). Reason: `test_t07_w5a_operations.py` holds a
  method's parameters equal to its served schema's properties, and `test_m07a_surface_chain.py` pins D_3 — adding the
  member in WO-3 moves the served digest, which is WO-6's. Until then the application refuses in §4.11's order:
  no audited solver → `unsupported nlp_solver_unavailable(<platform>)`; with one → `invalid_request` at
  `/optimization`. The library path `validation.validate(doc, "optimization", optimization=, solver_probe=)` is complete.
  The CLI `validate --request` goes with the member (WO-6). The `ApplicationProtocol` (`contract.py:69`) is unchanged.
  Alternative: move the digest now. Reversible by: WO-6 adds the member.
- D-20. DECISION: the report shape → after the revision's own checks, `OPT.REQUEST_SCHEMA` (stage `schema`) and one
  check per static code, always all present: FAIL (details joined, subjects implicated), NOT_RUN (with why), else PASS
  (what it established). Stage `capability` for REVISION_UNBOUND, OPTIMIZATION_ROUTE_UNAVAILABLE, the three assessment
  codes, HESSIAN_UNAVAILABLE and NLP_SOLVER_UNAVAILABLE; `structural_analysis` for the rest. A revision not
  `READY_FOR_SIMULATION`: request schema still judged, every other OPT check NOT_RUN, status DRAFT/INVALID as the
  revision's. Alternative: failing checks only. Reversible by: `validation._validate_optimization`.
- D-21. DECISION: request rules and starts → `request_problems`: canonical (ADR 0002) first, then the schema's errors,
  then: distinct decision specification ids, each explicit start one value per decision, distinct constraint ids, every
  expression names ≥ 1 variable, no quadratic pair twice. Start 0 = the base binding's parameters at the mapped ids
  (internal units by construction; D-13 makes them the written values). A decision with no finite box end is not
  probed (BOUNDS_UNDECLARED; continuity NOT_RUN); START_OUTSIDE_BOUNDS is judged only on a bounded box (M03's rule).
  Zero starts is TOO_MANY_STARTS (§4.3 "1…32, else"). Objective: coefficient `(s·c)/scale`; text unchanged when
  minimised at scale 1, else `(t)/scale` / `-(t)/scale` / `-(t)`, the scale in its canonical JSON spelling.
  `request_sha256` = canonical SHA-256 of the request as given (no defaults filled). Route: `select_route`; `NoRoute` →
  REVISION_UNBOUND(`<binder code>`), `legacy_eo`/`revision_coupled` → OPTIMIZATION_ROUTE_UNAVAILABLE (subject = route);
  either makes the revision-dependent checks NOT_RUN. Reversible by: `bcd043ec`.
- D-22. DECISION: `revision_sha256`, the request schema's `sha256` name → an OPT addendum in `ADDENDA`
  (`benchmarks/opt/numerical_policy_external.yaml`, id `OPT-numerical-policy-external-v1`, schemas
  `[optimization-request.schema.json]`, `exact_sha256: []` — the name keeps M05's addendum's class), E01's ESC-A1
  precedent. v2 bytes unchanged (`scripts/t08_numerical_policy.py --check`: equals, sha256 `6b449911…d707c`).
  Alternative: rename the field. Reversible by: the addendum commit.
- AMENDED_TESTS (ADR 0071; U05/R-129's refusal and its pins, design §4.11):
  `tests/test_t08_w2_unsupported.py::test_u05_validate_for_optimization_is_unsupported`,
  `tests/test_m03_nlp_formulation.py::test_a33_validate_for_optimization_is_still_r129s_unsupported` (both skip where an
  audited solver is installed), `tests/test_t07_w3b_validation.py::test_r3_every_corpus_report_validates[optimization]`,
  `tests/test_t07_w5b_cli.py::test_the_pins_moved_by_d1s_str05_substitution_u05_and_v2_recording_only` and the pin file
  `tests/fixtures/t07/cli-existing-commands.json` (U05's message only), `tests/test_t08_rename_substitution.py::
  test_the_cli_pins_moved_by_the_rename_only` (reverses OPT's message first, `opt_reversed_cli_text`; the pre-rename
  hash is unchanged); D-22: `tests/test_m05_study_record.py::test_the_m05_addendum_is_audited_after_m02s_and_its_
  partition_holds` (`ADDENDA` + `opt`).
- Stale until WO-6: `descriptions/validate.md` still says `task_unsupported(optimization)` (the surface link's text).
- Open for WO-6/WO-7: `benchmarks/t08/support_envelope.yaml` U05's outcome text still states the v0.1 refusal; not
  edited here (a release document; its evidence test node still exists).

### Gates (WO-3, 2026-11-07, TRS2, worktree `wp/OPT`)

- G1: `scripts/corpus_identity.py --check` at `d5533e09`: **F0 PASS** — M1 50/50, M2 61/61, M3 61/61, M4 61/61,
  M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35.
- G18 + G11 (default env): `tests/test_opt_request.py` — 42 passed: schema is draft 2020-12 and registered; 2 valid
  fixtures round-trip, 8 invalid refused at the expected pointer; Halton k = 1…4 (2-D) within 1 ulp of (1/2, 1/3),
  (1/4, 2/3), (3/4, 1/9), (1/8, 4/9); one failing case per static reason (12, each alone) plus NLP_SOLVER_UNAVAILABLE and
  the real `revision_coupled` route (`benchmarks/m02/c1-loop-real.json`); validate READY/INVALID/DRAFT/missing request;
  platform `linux-aarch64`/`darwin-arm64` → unavailable naming it, API `unsupported nlp_solver_unavailable`; a fresh
  interpreter running `validate` and `static_readiness` loads neither `pyomo` nor `cyipopt`. Not covered: a failing
  static `ASSESSMENT_PARAMETER_*` case (D-18).
- Regression, default env (`tests/test_opt_*.py test_m03_*.py test_e01_*.py test_t07_*.py test_t08_*.py
  test_k01_schemas.py test_package_imports.py test_m07a_*.py test_adr_0002_canonicalization.py test_m04_schemas.py
  test_rel_*.py`): 3593 passed, 31 skipped, 10 failed before D-16's bare message and D-22 — 6 pins of U05's old text,
  3 numerical-policy audits (`revision_sha256` unclassified), 2 `test_rel_rc_local` (HEAD moved by a commit during the
  run). After the fixes, the 10 failing files: 536 passed + rename 25 passed, 0 failed. Served surface digest unmoved
  (`test_m07a_surface_chain.py`, `test_t08_w2_surface_digest.py` pass).
- Audited env (m05's `.venv-nlp`, `m03_nlp_check.sh`): 18 passed (the script runs the `nlp`-marked tests only; WO-3's
  tests are default-env tests).

## WO-4 (formulation and gray box on the revision host, verification, records, benchmarks)

- D-23. DECISION: `FullSpaceNlp` on a held system (lifts D-7) → `restricted` iff the system holds columns or has
  label rows; then `variable_ids` = the free columns in spec order, `split` returns the full state vector (held columns
  at their certified values, index arrays built once), the equality rows are the system's rows (region order) then its
  labels (`x[out] − x[src]`, constant `+1/−1` Jacobian, scaled by K03's temperature nominal), Jacobian columns and an
  assessment block's columns restricted to the primal; bounds from the host's `bounds(point)` where the host has one
  (§4.2.3), else M03's `_bounds`. An unrestricted system (SYN-001; every corpus revision but a held PH split) takes
  M03's code path unchanged. Alternative: one code path for both (column selection by an identity index changes no
  value but re-canonicalises the CSC; G2 would have to prove it). Reversible by: the WO-4 formulation commit.
- D-24. DECISION: the formulation of a report refused statically (no `NlpFormulation`: the map or start 0 is missing)
  → decisions under the map's parameter ids where it was found, else the specification ids; start 0 = the
  specifications' `value`s as the revision writes them when every decision's has one, then explicit and Halton; with
  no start at all `starts: [[]]` (the schema needs ≥ 1; nothing ran). `model` has `None` fields before the start
  phase. Alternative: refuse to report (§4.5 asks for an `UNSUPPORTED` report). Reversible by:
  `revision._request_formulation_record`. **For the reviewer:** the `[[]]` corner (UNKNOWN_DECISION with only start 0).
- D-25. DECISION: V2/V4/V5 on the revision host → `verify_candidate(..., held=)` (`solve_start` passes the start's
  system iff the point carries an attempt signature; SYN-001's is `None`, so M03 is untouched — G2): V2's `TAU_GROSS`
  norm runs over the free columns, held columns must equal the re-solve's exactly (`held_changed`); V4 also fails when
  the re-solve's signature differs from the start's, listing `PHASE_REGIME_CHANGED(<unit>)` per differing item's unit
  in `phase_regime_changed`; an expression naming a decision is valued at `{state, decisions}` and its V5 derivative is
  direct (as an assessment output's `∂G/∂d`). Alternative: a separate revision verifier. Reversible by: the WO-4
  verification commit.
- D-26. DECISION: a request with an `assessment` → `optimize_revision` raises `NotImplementedError` (E01's binding at
  the first certified start, D-18, is not built in this WO-4 slice; the job is WO-6, so no surface reaches it yet).
  Open WO-4 item. Reversible by: building the binding.
- D-27. DECISION: record details (§4.8 leaves open) → JSON members hashed by `document_sha256`, bundle files by file
  SHA-256, all in the manifest's `members`; manifest `environment = {solver: report.solver.environment}`; only
  certifies that reach `solve_route` write a bundle (D-11); `optimizer.json` writes a non-finite float as its `repr`;
  the report's `limits.max_iter`/`max_wall_time` are the request's; the start record gains §4.13's `start_record`,
  `resolve_record` (relative paths), `held_signature`, `candidate_revision_sha256`; the candidate `change_set`,
  `candidate_revision_sha256`, `resolve_record`. `phase_bounds_active`/`regime_note` are WO-5's. Reversible by:
  `revision._Record`, `_start_record`, `_candidate_members`.
- D-28. DECISION: where `START_NOT_CERTIFIED` and `PHASE_REGIME_CHANGED` live → in details, not codes: a start not run
  is `SOLVER_FAILED` with detail `…; START_NOT_CERTIFIED(<k>, <code>): <why>`; none passing → one
  `SIMULATION_NOT_READY` per start, detail `START_NOT_CERTIFIED(<k>, <code>): …`, subject `start <k>`; a regime change
  → `NOT_VERIFIED` (failing V4) with V4's `phase_regime_changed`. The report schema's reason enums gain the static
  codes (REVISION_MISMATCH, REVISION_UNBOUND, OPTIMIZATION_ROUTE_UNAVAILABLE, DECISION_UNIT_NOT_INTERNAL,
  DECISION_NOT_CONTINUOUS, TOO_MANY_STARTS, REGIME_MARGIN_UNDEFINED; D-17's follow-through) and the additive
  `revision`, start and candidate members (§4.13). Alternative: new top-level codes. Reversible by: the schema commit.
- D-29. DECISION: the analytic flowsheets → generated once from the T05 templates (C1's `U-PHF` `syn001.ph_flash` and
  `U-HEAT` `syn001.tp_heater`, C3's `U-SPLIT` with `split_fraction` as a `parameters.split_fraction` specification),
  committed as JSON; constants, requests and mpmath expectations owned by `benchmarks/opt/analytic.py` (`--check`).
  Every pressure drop is 0 (P = 1e5 Pa). Bubble point of the equimolar feed 347.4412 K; every start ≥ 11.4 K below it,
  every interior optimum ≥ 23 % of its box from either end (asserted by the script). Reversible by: the files.
- D-30. DECISION (escalated): §4.13's report members vs the numerical-policy partition → the report is a v2-domain
  schema whose bytes are frozen, and `optimization_sha256`, `solve_policy_sha256`, `revision_sha256`,
  `candidate_revision_sha256` are not v2 names (`t08_numerical_policy.py --check`: "(d) unclassified"). Following
  E01's precedent, the `revision` member is a `$ref` to `optimization-request.schema.json#/$defs/report_revision`
  (OPT's addendum classifies `optimization_sha256`, `solve_policy_sha256`; `revision_sha256` keeps its earlier class);
  the flat `candidate_revision_sha256` members of `$defs/start`/`$defs/candidate` are **dropped** — the candidate
  document's SHA-256 is its record member's (`starts/<k>/candidate-revision.json` in the manifest). For the design
  lane: keep it so, or carry the hash in a `$ref`'d object. Alternative: list the names in v2 (moves v2's bytes,
  forbidden). Reversible by: the D-30 commit.

### Gates (WO-4, 2026-11-07, TRS2, worktree `wp/OPT`)

- G7 OPT-A1 (1 start): `KKT_POINT_VERIFIED`, Ipopt 0 in 8 iterations; Q = 9000.00000009091 vs Q* = 9000 (mpmath),
  rel 1.0e-11 (≤ 1e-7); λ = 0.03 vs λ* = 0.03 (≤ 1e-4 rel); V5 stationarity residual 0.0.
- G8 OPT-A2 (3 starts, all `KKT_POINT_VERIFIED`, distinct 1, 12–13 iterations): r = 0.3000000000394735 vs 0.3
  (3.9e-11 ≤ 1e-6); Q = 2700.0000004461704 vs 2700 (rel 1.7e-10 ≤ 1e-6); f = 0.3600000000090909 vs 0.36 (9.1e-12
  ≤ 1e-8); V5 residual 1.15e-10. OPT-A2b (outlet T decision, TP split): all 3 verified, distinct 1; r err 5.7e-11,
  T = 330.0000000010101, duty at the certified candidate 2700.0000006032 (rel 2.2e-10), f err 9.1e-12; residual ≤ 2.9e-10.
- G9 OPT-N1: `NOT_VERIFIED` (Ipopt 0, Q = 16500.0000001 liquid-held), V4 `PHASE_REGIME_CHANGED(U-PHF)`. Route
  refusals (A02 corpus legacy_eo; `c1-loop-real` revision_coupled): `UNSUPPORTED OPTIMIZATION_ROUTE_UNAVAILABLE`.
- G2: `scripts/opt_m03_dump.py` base `cd1a5cfa` vs WO-4 (`f2f4ef5e`…): **identical**, default env 22 entries (sha
  `6e028e8d…`), audited env 25 entries (`8cfe7c7b…`). G1 F0 PASS (M1 50/50 … M9 35/35). Policy `--check` equals v2.
- Tests: default env `test_opt_*.py test_m03_*.py test_e01_*.py test_k01_schemas.py test_m05_study_record.py
  test_t08_w4_package_data.py` 754 passed, 1 skipped (before D-30: 2 policy failures, fixed: 341 passed on those
  files); audited env (`m03_nlp_check.sh`) 26 passed (OPT 4 + M03/E01 22).
- Not done in WO-4 (next engineer): G17 performance record (TH-R1, M1, C-MW requests), F5 (C-MW L-BFGS), D-26
  assessment binding, the "multiple output blocks" Pyomo abstraction (phase rows are WO-5's; one block today).

## WO-4b (finish WO-4: assessment binding, record test, output blocks, G17/F5)

- D-31. DECISION: §4.4's "multiple output blocks" → `formulation.OutputBlock` (name, Pyomo component name, ids,
  scales, admissibility nominals, `values(z)`, `jacobian(z)` over the primal); `FullSpaceNlp.output_blocks` in order
  (E01's assessment block today, WO-5's phase rows next), `output_ids`/`output_scales`/`admissibility_nominals` their
  concatenation (`_add_block` refuses a repeated id); `output_values`/`output_jacobian` pass one block through
  unchanged and stack several (`np.concatenate`, `sp.vstack` CSC), counting one call per gray-box call;
  `greybox.build_model` adds each block's `≥ 0` rows as its own component (`assessment_admissibility` unchanged).
  Inert: G2 base `c6755d86` vs this commit identical in both envs (default `6e028e8d…`, audited `8cfe7c7b…`, the WO-4
  hashes); OPT-A1/A2/A2b/N1 reports (wall times blanked) identical base vs head (`8e986126…`).
  Alternative: one gray box per block (Pyomo would see several external models; the Ipopt problem changes).
  Reversible by: the D-31 commit.
- D-32. DECISION (supersedes D-26): E01's binding on the revision host → `revision._bind_assessment` after every
  start's certify + Q3: at the first start that passes, `AssessmentProgram.build(view_of(host.bound_flowsheet(point)),
  point.spec, load_assessment(request.assessment), state)` (regime by the rule there, default contributors) and
  `AssessmentBinding.at(program, named outputs, state)` (scales `max(|y|, 1)` there). A start where the program cannot be
  planned (`Refusal`) or a named output cannot be evaluated does not pass (`START_NOT_CERTIFIED(<k>, <code>)`; the next
  passing start is tried). Program-wide checks (`ASSESSMENT_PARAMETER_STRUCTURAL`/`_DECISION`, `ASSESSMENT_OUTPUT_
  UNKNOWN`/`_UNAVAILABLE`; M03's closure functions) → `UNSUPPORTED` with those reasons, no Ipopt import; per-start
  checks (`ASSESSMENT_REGIME_INADMISSIBLE`, `ASSESSMENT_OBJECTIVE_UNSCALED`) fail each passing start they find, the
  planning start included. A request whose expressions name no `assessment:<id>` is not bound (its assessment unused).
  The report's `formulation.assessment` is E01's `assessment_record` (closure at the planning start, candidate's active
  rows). `request_problems` needs no change: `load_assessment` checks only canonical form and schema, both already the
  request's. Alternative: plan the program at every start (scales would differ per start; E01 fixes one per
  formulation). Reversible by: the D-32 commit.
- D-33. DECISION: the assessment benchmark of WO-4b → **OPT-C0** = OPT-A1 with `assessment:opex.total` (one LPS heating
  utility, 8 USD/GJ, 8000 h/yr, U_heating 800) scaled by α·Q_s, α = 8e-9·8000·3600 = 0.2304 USD/(W·yr) by hand in
  `analytic.py`, so Q*, λ* are A1's and opex* = α·Q* = 2073.6. Bound-active (the area-floor admissibility row of the
  exchanger would bind an interior A2-type case at Q ≈ 2700 W). The interior cost case (golden section, G19) and LCA
  (G20) stay WO-7's. Reversible by: the files.
- AUDITED-ENV record test (§4.8): `test_the_record_holds_every_starts_files_by_hash` on OPT-A2's record.

### Gates (WO-4b, 2026-11-07, TRS2)

- OPT-C0 (audited env): `KKT_POINT_VERIFIED`, 7 iterations; Q = 9000.000000090908 vs Q* = 9000 (rel 1.0e-11 ≤ 1e-7);
  λ = 0.03 vs 0.03; opex(V6, float path) = 2073.6000000209456 = α·Q exactly (rel 0.0 ≤ 1e-9), vs opex* 2073.6 rel
  1.0e-11; V7 pass; binding scale α·10500 = 2419.2. Refusals (default env): `assessment:tac` → `UNSUPPORTED
  ASSESSMENT_OUTPUT_UNAVAILABLE`; `assessment:opex.NOPE` → `ASSESSMENT_OUTPUT_UNKNOWN`; scale 1 → `SIMULATION_NOT_READY`
  `START_NOT_CERTIFIED(0, ASSESSMENT_OBJECTIVE_UNSCALED)`.
- D-34. DECISION: G17's requests → `benchmarks/opt/requests/perf/{TH-R1,M1,C-MW}.json`, generated and checked by
  `benchmarks/opt/performance.py --write/--check` (quadratic trackings, boxes certified at both ends to keep the base
  regime, starts: revision + one explicit). TH-R1: `SPEC-H-Q` ∈ [15, 35] kW, `SPEC-D-Q` ∈ [−5, 5] kW, min
  ((S5.n.H2O − 0.5)/0.05)² + (Q_D/5000)²; M1: feed T ∈ [320, 348] K, min ((S-DISTILLATE.n.B − 0.06)/0.005)²; C-MW: feed
  T ∈ [335, 348.6156] K, min ((COL.stage.20.Q − 38500)/1000)². Reversible by: the files.

### G17 / F5 (2026-11-07, TRS2, audited env, one process, `OMP_NUM_THREADS=1`; at `079b32b4` + the D-32 edits)

| case/start | Ipopt | it | certify s | twin s | Ipopt s | verify s | res/jac/prop calls | eval errors | n (free+dec) | result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TH-R1 s0 | 0 | 16 | 2.65 | 0.40 | 1.87 | 3.07 | 22/19/540 | 0 | 40 (38+2) | VERIFIED, H.Q* 26882.99 W |
| TH-R1 s1 | 0 | 25 | 2.45 | 0.12 | 4.62 | 1.99 | 131/28/1683 | 0 | 40 | VERIFIED, same point |
| M1 s0 | 0 | 8 | 1.32 | 0.02 | 0.16 | 1.30 | 32/11/1188 | 0 | 119 (118+1) | VERIFIED, T* 332.6915 K |
| M1 s1 | 0 | 8 | 1.27 | 0.02 | 0.09 | 1.32 | 9/11/682 | 0 | 119 | VERIFIED, same point |
| C-MW s0 | −2 | 46 | 8.10 | 0.06 | 16.08 | 7.28 | 7032/49/102987 | 6984 | 298 (297+1) | SOLVER_FAILED (restoration) |
| C-MW s1 | 0 | 61 | 7.82 | 0.08 | 7.49 | 7.01 | 5690/64/31922 | 5625 | 298 | NOT_VERIFIED, T 341.284 K |

Totals: TH-R1 18.3 s, M1 5.9 s, C-MW 54.4 s ("verify" also holds report/record writing for the last start).
- **F5**: L-BFGS converges on C-MW (297 columns) in 61 iterations, 7.5 s Ipopt; no start near 500 iterations or 120 s
  → keep the default `max_iter` 500.
- **Escalated (design lane, with WO-5):** (1) C-MW's feed has exactly zero C2H5OH; Ipopt's trial points drive the
  column's ethanol flows negative and the twin raises `DomainError … component flows ['C2H5OH'] are not finite and
  non-negative` (stages s1, s18, s19, feed enthalpy) on ~99 % of residual calls — the flows bounded `None` by §4.2.3's
  "unbounded where exactly zero at the point" rule (`zero_at_start_pinned_by_regime`) are not pinned by any row, so
  Ipopt moves them; start 0's restoration failure follows. (2) All 19 held TWO_PHASE stages of C-MW have a `null`
  PH-split margin: V4 fails and V5 is refused `REGIME_MARGIN_UNSUPPORTED` ×19, so no C-MW start can verify whatever
  Ipopt does (M1 passes the same checks). Default until ruled: recorded, no change (both touch §4.2.3 bounds or §4.7
  margins, i.e. numerics).
- Final WO-4b gates at `f6caf578`: G1 F0 PASS (M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52,
  M8 105/105, M9 35/35); G2 vs `c6755d86` identical in both envs; `analytic.py --check`, `performance.py --check`,
  policy `--check` pass; default env (`test_opt_*.py test_m03_*.py test_e01_*.py test_k01_schemas.py
  test_m05_study_record.py test_t08_w4_package_data.py`) 765 passed, 1 skipped; audited env on every `nlp`-marked file
  196 passed (a bare `m03_nlp_check.sh` with no file list errors collecting `test_s10_*` — no mpmath in that env; not
  OPT's).

## WO-5 (phase admissibility rows, Q4 held mode, OPT-A3, G9 rerun)

- D-35. DECISION: §4.7's open details → rows in `studies/nlp/phase.py`, one functional `ProblemSpec` (label
  `OPT-PHASE-ROWS`, the host spec's variables and parameters) per start, cached on the point's handle. Row ids name the
  expression's form (ADR 0002 D2.7: one label, so the id must): `phase.<unit>.bubble` (held LIQUID), `.dew` (VAPOR),
  `phase.<stream>.subcooled` / `.superheated` (declared ports). The split row reads the host's own `LnKBlock` fed by
  the split's `(T, P)` (feed flows in component order, as `tp_margin`); each row is `a/nominal` (molar_flow N0 = 3 mol/s,
  K03's registered nominal; ports 1 K), gray-box scale 1, Pyomo component `phase_admissibility`. A declared port is a
  spec `PhaseFlowBlock` `PF_<S>_liquid|vapor`; its `T_sat(P)` is `SaturatedFlowBlock` (the block `sat-T` reads)
  restricted to `Tsat` (`PortSaturationBlock`, input P), provider and context the host's; the report's `unit` for a
  port row is its **stream** (the declaration is the stream's: every reader declares the same block). V3 evaluates
  the rows on the float reference path (`row_values`), V5 by the chain rule from the rows' twin (`phase:<id>` terms,
  as `assessment:` ones); V4 exempts a split whose row is in V3's active set (|slack| ≤ TAU_ACTIVE) and records
  `phase_bounds_active: {units, rows}` in its detail; the revision candidate carries `phase_bounds_active` (always,
  possibly `[]`) and `regime_note` (§4.6's words) when it or the assessment's `regime_bounds_active` is non-empty;
  Q4's held mode records `held: [units]` in Q4's detail. Alternative: per-unit row ids without the form (two
  expressions under one id). Reversible by: `e8311348`.
- D-36. DECISION: which held regimes are `REGIME_MARGIN_UNDEFINED` → a held LIQUID/VAPOR split without a margin
  (D-12: `pr-c1-v1`, composition-dependent K) or without a `LnKBlock` fed by its `(T, P)`, and a declared port whose
  `T_sat` raises `DomainError` at the start's P; each fails its start `START_NOT_CERTIFIED(<k>,
  REGIME_MARGIN_UNDEFINED): REGIME_MARGIN_UNDEFINED(<unit>); …` (D-28's detail pattern). Alternative: build the
  ideal bubble/dew row anyway (not the closure's test there, F2). Reversible by: `phase_rows`'s `undefined`.
- D-37. **ESCALATED (premise false):** G10 expects OPT-A3 `KKT_POINT_VERIFIED` at the bubble point, but V1's cold
  re-solve there is `CERTIFICATE_NOT_VERIFIED`: K04's regularity check on the target system (after alias elimination,
  equilibrium rows included) is `ILL_CONDITIONED` — the trivial V = 0 branch and the two-phase branch meet at the
  bubble point, so rcond ∝ distance. Measured on OPT-A1's flowsheet (Q* = 14232.35459443206 W), cert status by
  Q* − ΔQ: ΔQ 1 W rcond 2.27e-6 VERIFIED; 0.1 W 2.27e-7 VERIFIED; 0.01 W 2.27e-8 ILL_CONDITIONED; … 2.7e-7 W
  6.1e-13; 0 RANK_DEFICIENT; −1e-3 W (TWO_PHASE) ILL_CONDITIONED. Ipopt's optimum (Q* − 2.7e-7 W, |T − T_b| = 9e-10 K)
  is therefore `NOT_VERIFIED` (V1 fail). A lifted split's row is "active" (|a/N0| ≤ 1e-6) only within ~1e-2 W of Q*,
  where the certificate already fails, so V4's exemption and Q4's held mode cannot be reached by a lifted split as
  the gates stand (thermal port rows have no such bifurcation; not exercised at an active port). Options for the
  design lane: (a) V1 at a candidate with an active split row judges regularity on the held-regime system (regular:
  the converged attempt's Newton system) — a K04/V1 policy change; (b) G10 expects `NOT_VERIFIED` with a typed boundary
  reason; (c) certify a point stepped back into the interior (moves T ≥ 3e-5 K, breaks G10's 1e-6 K). Default until
  ruled: no numerics change; G10's Ipopt part is a passing test, G10-as-designed is `xfail(strict=True)`. Commit
  `247e2ea5`.
- D-38. DECISION: a converged but UNVERIFIED re-solve on a revision host → V2–V5 `not_evaluated`
  (`resolve_not_certified`) after V1 `fail`, instead of `verification raised ValueError … no held system` (pre-WO-5
  defect, seen on OPT-A3). SYN-001 (no held system) unchanged. Alternative: take regimes from an uncertified point.
  Reversible by: `01b9650c`.

### Gates (WO-5, 2026-11-07, TRS2, worktree `wp/OPT`)

- G2: `scripts/opt_m03_dump.py` base `2dcb5772` vs WO-5 tree: **identical**, default env (`6e028e8d…`) and audited
  env `--nlp` (`8cfe7c7b…`), the WO-4 hashes. G1 F0 PASS (M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85,
  M7 52/52, M8 105/105, M9 35/35). Policy `--check` equals v2; `analytic.py --check`, `performance.py --check` pass;
  mypy: the 3 pre-existing `benchmarks/opt` errors only.
- OPT reports vs base (wall times blanked): **not byte-identical, by design** — every LIQUID-held split adds a phase
  row to the NLP. OPT-A1: Q bitwise unchanged (9000.00000009091), differences = the row's value/gradient/slack and
  Ipopt's final complementarity/dual infeasibility; OPT-A2 r 0.30000000004620614 (err 4.6e-11 ≤ 1e-6), Q
  2700.000000506764 (rel 1.9e-10 ≤ 1e-6); A2b r err 6.2e-11, T 330.0000000010101; C0 Q 9000.00000009091 (rel 1.0e-11),
  opex 2073.600000020946. All within G7/G8 (tests pass); phase rows inactive (slack 0.387 at A1's optimum).
- G9 rerun: OPT-N1 → `INFEASIBLE_REPORTED` (Ipopt 2, Infeasible_Problem_Detected). G10: Ipopt 0 in 7 iterations,
  Q = 14232.354594159335 vs Q* 14232.35459443206 (|T − T_b| 9.1e-10 K ≤ 1e-6) — passes; status `NOT_VERIFIED`, V1 fail
  (D-37) — **G10 FAILS as designed** (xfail strict).
- Tests: default env `test_opt_*.py test_m03_*.py test_e01_*.py test_k01_schemas.py test_m05_study_record.py
  test_t08_w4_package_data.py` at `247e2ea5`: 773 passed, 1 skipped; of them `test_opt_phase_rows.py` 8 (row vs
  mpmath K-table 1e-12, twin = float path bitwise, Jacobian vs central differences, TH-C1/TH-V1 port rows vs the
  kernel's T_sat, M1 none, undefined, second block, Q4 held mode, REGIME_MARGIN_UNDEFINED start refusal). Audited env
  (`m03_nlp_check.sh`: `test_opt_benchmarks_nlp.py test_m03_nlp_greybox.py test_e01_b_nlp.py test_e01_integration.py`)
  29 passed, 1 xfailed.
- G17 rerun (record; audited env, one process): TH-R1 VERIFIED, H.Q* 26882.98570346 W, 10/10 iterations (WO-4b 16/25;
  4 port rows `phase.S{1,2,7,8}.subcooled`, inactive), total 11.6 s; M1 VERIFIED T* 332.69149 K, 8/8 it, no rows, 6.4 s;
  C-MW unchanged: s0 Ipopt −2 (46 it), s1 Ipopt 0 (61 it), res/jac/prop calls 7032/49/102987 and 5690/64/31922 as
  WO-4b, 54.5 s.
- **C-MW (open item (2), measured):** WO-5 does not let C-MW's 19 TWO_PHASE stages pass. TWO_PHASE gets no row ("held by
  V, L ≥ 0"), and nothing undefined, but V4 still judges every split's margin and Q4′ every PH split's: margins are
  `null` (D-12, composition-dependent K), so both starts fail V4 (19 inside τ_regime) and V5 (`REGIME_MARGIN_UNSUPPORTED`
  ×19). Start 1 passes V1, V2, V3, V6 — the null margins are its only failing cause. Item (1) unchanged: the
  ethanol `DomainError` on ~99 % of residual calls (zero-at-start flows unbounded, §4.2.3) — for the reviewer.

## WO-5b (amendment A-2 zero subsystem, A-3 closure margins; design §9.2, §9.3)

- F7 (fact, measured before coding, default env): C-MW certified at T_feed ∈ {348.6156, 338, 335, 342} K — held
  system 297 rows/297 free, |Z| = |R| = 63 at every T (Z = every C2H5OH flow, all `+0.0`, none `−0.0`; R = 19 `mix`,
  19 `mole`, 19 `eq`, 3 `n`, `FEED-n`, `bal`, `split` ethanol rows), (Z, R) identical as id sets across the four
  solves; every cold re-solve keeps the ethanol flows `== 0.0`. **Premise holds.**
- F8 (fact, read): `_pr_admissible` (`orchestrator/region.py`) admits VAPOR iff `classify` says VAPOR (value: the
  classifier's) and LIQUID iff the light-gas flow is exactly 0 and `classify` says LIQUID (value n_light/n_tot) — not
  "admissible iff value ≤ 1 + ε". So `admissibility_value` returns `None` on `pr-c1-v1` → held single-phase splits
  there stay `REGIME_MARGIN_UNDEFINED` (design default).
- D-39. DECISION: A-2's open details → R from the compiled problem's Jacobian at the point (all free columns) and
  the host's cached twin `∂F/∂d` over every decision of the map; a non-`ok` Jacobian at a certified point raises
  (defect). Z = ∅ → no evaluation at all (inert by construction). The start record's `zero_subsystem` and V4's
  `zero_subsystem` detail (`start`, `resolve` statuses, |Z|, |R|, `columns_changed`, `rows_changed`, `codes`) appear
  only where either side is non-empty, so a Z = ∅ report keeps its bytes (G23 (c)). Alternative: always emit the
  members (moves every report). Reversible by: `051e3397`.
- D-40. DECISION: A-3's open details → `admissibility_value(provider, context, split, regime, state)` beside
  `_admissible` (ε passed as 0, the flag ignored; `None` for `pr-c1-v1` or on `VerifierError`/`BandError`/
  `ValueError`/`ArithmeticError`); TWO_PHASE margin `fsum` of each side's `molar_flow` columns, min over N0 =
  `REGISTERED_NOMINALS["molar_flow"]`; the guard identity evaluates each candidate row alone on the float reference
  path (`row_values` of a one-row program) — an empty feed or a row that raises is unguarded; `CLOSURE_IDENTITY =
  1e-10` in `phase.py`; `PhaseRow.feed` (not in `as_document`); `regimes_unguarded` only where non-empty (start
  record and candidate, as D-39); V4 detail `phase_row_not_closure_test`; ZERO_FLOW unchanged (margin `None`, V4
  as before). Alternative: `regimes_unguarded: []` always (moves every report). Reversible by: `7b1f7242`.
- D-41. Fact (A-2 beyond C-MW): TH-R1's flash holds Z = {`S5.sat.L`, `S6.sat.V`}, R = {`D:sat-fix:vapor`,
  `D:sat-fix:liquid`} (|Z| = |R| = 2; held system 38 → 36). The rule applies as written; G4's TH-R1 test updated.
  OPT-A1/A2/A2b: Z = ∅ at their starts (G23 (c)).
- D-42. **ESCALATED (fact; G24 (c) premise partly false):** on `wilson-ig-v2` K04's certificate is `UNVERIFIED` at
  every single-phase held split measured — GP-C3's heater held LIQUID (340, 345 K) and VAPOR (365–385 K): the
  derivative witness's stencil steps the held, exactly-zero side negative (`witness_stencil_invalid_trial_state(
  S4.liq.CH3OH)` / `S4.vap.CH3OH`, plus `derivative_limitation`). A γ–φ unguarded split is therefore admitted by A-3
  but can never be an OPT start today (`START_NOT_CERTIFIED`); no corpus flowsheet has a γ–φ single-phase held split
  (GP-C1/C2/C3 are TWO_PHASE, GP-M1 none). G24 (c) is tested on GP-C3 at 385 K with the converged point relabelled
  `CONVERGED` (the rule on the converged state: unguarded, margin = 1 − ΣW bitwise, start record names it). For the
  design lane: whether K04's witness stencil should respect held zero sides is a K04 question outside OPT.
- D-43. DECISION: V4's closure-identity clause (A-3) judges a guarded split only where the re-solve keeps its held
  regime; a split the re-solve finds in another regime is already `regime_changed`/`PHASE_REGIME_CHANGED`, and its
  bubble/dew row is not that regime's test. Measured: OPT-N1's infeasible end point re-solves U-PHF TWO_PHASE, and the
  clause as first built added a spurious `phase_row_not_closure_test(U-PHF)`. Alternative: judge every guarded split
  (the design's literal words). Reversible by: `90161fd0`.
- D-44. Fact (gate tooling): `scripts/opt_m03_dump.py --nlp` run without `PYTHONNOUSERSITE=1
  PYOMO_CONFIG_DIR=<m05>/.venv-nlp/share/pyomo` (as `m03_nlp_check.sh` sets them) loads `~/.pyomo/lib`'s unaudited
  PyNumero, and M03's probe then reports NLP-1, NLP-INF and E01-TAC `UNSUPPORTED` — so the WO-4/WO-5 G2 `--nlp` hash
  `8cfe7c7b…` compared unsupported reports. With the audited variables set the reports solve (`KKT_POINT_VERIFIED`,
  `INFEASIBLE_REPORTED`) and G2 `--nlp` is `b6bbafdb…`, identical base vs WO-5b. `optimize_revision` does not refuse
  the unaudited library (OPT reports solve either way) — for the reviewer: should OPT's probe match M03's?

### Gates (WO-5b, 2026-11-08, TRS2, worktree `wp/OPT`; A-2 `051e3397`, A-3 `7b1f7242`, D-43 `90161fd0`)

- Merge of `origin/main` (`32023fa5`, X05): no conflicts; `t08_support_matrix.py --emit` unchanged; HARVEST_SIZE
  (72, 964, 126) from main; `test_m07a_harvest.py` 5 passed; F0 PASS.
- **G1** F0 at `7b1f7242`: PASS (M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105,
  M9 35/35).
- **G2** vs `32023fa5` (pre-WO-5b head): default env **identical** at `051e3397` and `7b1f7242` (`6e028e8d…`);
  audited env `--nlp` identical at `051e3397` (unaudited PyNumero, `8cfe7c7b…`) and at `7b1f7242` with the audited
  variables (`b6bbafdb…`, D-44).
- **G23** (a) C-MW: |Z| = |R| = 63, J[R, ¬Z ∪ d] == 0.0 entrywise, J_RZ full rank, reduced residual = the converged
  attempt's on the kept rows bitwise; (b) dy/dd of `COL.stage.20.Q`, `S-DISTILLATE.n.CH3OH`, `S-BOTTOMS.n.H2O`
  reduced vs unreduced within 1e-10 rel (dense solve; dx_Z/dd ≤ 1e-12·max|dx| through the unreduced one);
  (c) OPT-A1/A2/A2b/A3/C0/N1 reports (wall times blanked) at `051e3397` **byte-identical** to `826cc4c4` and
  `32023fa5` (`scripts/opt_report_dump.py`; unaudited PyNumero) and to `826cc4c4` with the audited variables
  (`149a1808…`); static Z = ∅ at OPT-A1/A2/A2b starts; (d) C-MW with `SPEC-S-IN1-n-C2H5OH` ∈ [0, 0.1] as a decision →
  `unresolved`, |Z| 63, |R| 62, Z bounded `[0, ∞)` `zero_at_start_unresolved`. PASS.
- **G24** (a) OPT-A1/A2/A2b closure margin vs `tp_margin` ≤ 1e-12 (rows guarded); (b) C-MW 19 TWO_PHASE margins =
  min(Σv, Σl)/3 bitwise, min 0.18893 ≥ τ_regime, no single-phase split; (c) GP-C3 at 385 K (wilson-ig-v2) H VAPOR:
  unguarded, margin = 1 − ΣW bitwise, start record `regimes_unguarded: ["H"]` (on the relabelled point, D-42);
  (d) +1e-9 on the closure value → unguarded. PASS.
- **G22** (audited env, the G17 C-MW request): **PASS** — both starts `KKT_POINT_VERIFIED`, Ipopt 0, V1–V6 pass;
  s0 (348.6156 K) 10 it, s1 (338 K) 9 it, both → T_feed 341.28364084891 K (objective −2.3e-13: Q_reb = 38.5 kW
  reached); `evaluation_errors` 0 on both (was ~99 % `DomainError`); zero subsystem `held` 63/63; the 19 TWO_PHASE
  margins ≥ τ_regime at both starts (min 0.188929, 0.189054).
- **G7/G8/C0/G9/G10** (audited, `m03_nlp_check.sh`: OPT nlp + M03/E01 nlp tests at `7b1f7242`): 29 passed, 1 xfailed
  (G10, D-37 unchanged); OPT nlp alone at `90161fd0`: 7 passed, 1 xfailed. A1/A2/A2b/C0 candidates bitwise as WO-5
  (A1 Q 9000.00000009091; A2 r 0.30000000004620614, Q 2700.000000506764; A2b T 330.0000000010101; C0 objective 0.9000000000090911).
  OPT reports at `90161fd0` vs `051e3397` differ in one member: OPT-N1's re-solve split (TWO_PHASE) margin
  0.016949 (`tp_margin`) → 0.025760 (min phase flow / N0), by A-3. **G9**: OPT-N1 `INFEASIBLE_REPORTED`.
- **G17** rerun (record; audited env): TH-R1 VERIFIED 10/11 it, 15.5 s (zero subsystem 2/2 held, D-41); M1 VERIFIED
  8/8 it, 8.5 s; **C-MW VERIFIED** 10/9 it, res/jac/prop 11/13/2257 and 15/12/2379 (WO-5: 7032/49/102987 and
  5690/64/31922, Ipopt −2/0), 28.1 s (WO-5 54.5 s).
- Default env battery at `7b1f7242` (`test_opt_*.py test_m03_*.py test_e01_*.py test_k01_schemas.py
  test_m05_study_record.py test_t08_w4_package_data.py`): 790 passed, 1 skipped; mypy and ruff clean on touched files.

## WO-5c (amendment A-1, the phase-boundary form; design §9.1; D-44 follow-ups)

- **F6** (fact, measured before coding, default env): OPT-A3's candidate Q̂ = 14232.354594159335 W re-solves `CONVERGED`,
  certificate `UNVERIFIED` with the one limitation `rank_limitation(ILL_CONDITIONED, relative)` (rcond₁ 6.19e-13, dim
  18); every other check passes — residual 18, material 8, energy 2 (+1 `not_applicable` S2), specification 9, bounds
  13 (+1 n/a S2), phase_admissibility 2, independent_split 4, derivative_witness 2 — the same pattern as the `VERIFIED`
  point Q* − 1 W; `grade` with `NO_RANK_LOSS_DETECTED` → `VERIFIED`. **Premise holds; G10 proceeds.**
- D-45. DECISION: V5's sensitivity at a boundary point → Q1′ (M03's "certificate `VERIFIED` for the same state") also
  passes on `CertificateEvidence.basis = phase_boundary_form` with the certificate `UNVERIFIED`; the basis is recorded
  in Q1′'s detail only when not `certificate` (M03's bytes unchanged, G2). Only `RevisionNlpHost.sensitivity` sets it,
  after V1 admitted the point. The design names V5 on the held system but not Q1′ (it would refuse every boundary
  point `ROOT_NOT_VERIFIED`). Alternative: no study-level certificate (`not_applicable`, weaker). Reversible by:
  `16fb2d3f`. **For the reviewer.**
- D-46. DECISION (D-44 gap): `optimize_revision` checks `greybox.environment_problems()` after the starts and before
  any Ipopt call, exactly where and as M03's `optimize` does → `UNSUPPORTED(NLP_SOLVER_UNAVAILABLE)` with M03's words.
  Not in the static probe: that would import Pyomo there (G11's fresh-interpreter test forbids it). Reversible by:
  `1d909ef9`.
- D-47. DECISION: V1's detail on a revision host always carries `basis` (`certificate`, `phase_boundary_form`, or
  `null`); a non-`VERIFIED` re-solve is always judged on (e1)–(e6) and a failure records `phase_boundary_form: {clause,
  reason[, boundary_form]}` (first failing clause). SYN-001's V1 unchanged. `claims.numerical_verification` is present
  only with a candidate; the candidate's `certificate_basis` always (schema: both optional, the candidate definition is
  M03's too). Reversible by: `9a78d67e`.
- D-48. DECISION: the certificate's target and zero-flow tuple are rebuilt in `boundary.py` as `verify_revision` builds
  them (fresh provider's P domain, `parse_revision`, the private `_staged_splits` imported, not edited); B's row and
  column ids by `assemble_target`'s own rules (checked against the matrix shape). G10a pins the rebuild byte for byte at
  five states. Alternative: a public helper factored out of `verify_revision` (edits K04 code). Reversible by: `9a78d67e`.
- D-49. DECISION: details A-1 leaves open → (e1) "converged" is the route run's outcome `CONVERGED` with a state and a
  spec; A in `region_splits` order (RegionResult carries no split list), regime from the row kind; (e6) also fails when
  the host's check policy hash differs from the certificate's `check_policy_sha256` (the certificate's own policy).
  Reversible by: `9a78d67e`.
- D-50. FACT/for the design lane (G10d): the gate's "0 < a/N0 ≤ 1e-7" and "|T − T_d| ≤ 1e-6 K" are inconsistent at the
  loose end — d(a/N0)/dT ≈ Σ y_i/K_i · ∂lnK_i/∂T ≈ 0.026/K at T_d, so a/N0 = 1e-7 is ΔT ≈ 3.9e-6 K. The test bisects to
  a/N0 ≤ 1e-9 (inside the gate's bound). G10b applies its 5 % rcond₁/ΔQ test at Q̂ too (the text is ambiguous).

### Gates (WO-5c, 2026-11-08, TRS2, worktree `wp/OPT`; D-45 `16fb2d3f`, A-1 `9a78d67e`, OPT-A3v `9373e15b`, D-46 `1d909ef9`)

- **G10** (audited env): **PASS**, `xfail` removed — OPT-A3 `KKT_POINT_VERIFIED`, Q 14232.354594159335 (|Q − Q*|/Q*
  1.9e-11), V1 basis `phase_boundary_form`, target `ILL_CONDITIONED` rcond₁ 6.19e-13, B `NO_RANK_LOSS_DETECTED` rcond₁
  0.04347 (dim 14), bundle certificate `UNVERIFIED` (one `rank_limitation`), `phase_bounds_active` U-PHF slack 2.43e-11,
  λ 0.3739709049025754 vs λ* 0.373970904895325103 (closed form = numeric μ* to 30 digits; rel 1.9e-11); V5 pass,
  stationarity 0.0; claims `numerical_verification: phase_boundary_form`; OPT-A1 `certificate`.
- **G10a** PASS: B(A = ∅) screen = certificate `regularity` byte for byte at OPT-A1's V1 state, OPT-A3's Q̂, TH-R1, M1,
  C-MW certified starts. **G10b** PASS: cert rcond₁/ΔQ = 2.27e-6/W at ΔQ 1, 0.1, 0.01, 1e-3 W and Q̂ (2.73e-7 W; status
  VERIFIED, VERIFIED, ILL, ILL, ILL); B rcond₁ 0.0434739 at all five; Q1′ pass on basis `phase_boundary_form` at Q̂.
  **G10c** PASS: (i) Q* + 1e-3 W TWO_PHASE → e2; (ii) non-registered policy → e6 (`RELAXED`, B clean); (iii) no rows →
  e3, point stays unadmitted; (iv) AST: nothing under `verify/`, `orchestrator/` imports `boundary`. **G10d** PASS
  (OPT-A3v): 29 bisection steps on [−20000, −4000] W → Q_v −7718.908756971359 W (closed form −7718.908764457, recorded),
  a/N0 7.07e-10, T − T_d 2.5e-8 K, certificate `ILL_CONDITIONED` rcond₁ 5.3e-12, e1–e6 hold with A = {U-PHF} VAPOR
  (S3 pinned, `Ndef:liquid` dropped), B rcond₁ 0.02847.
- **G7/G8/C0/G9** (audited, `m03_nlp_check.sh`: OPT nlp + M03/E01 nlp tests at `1d909ef9`): **30 passed, 0 xfailed**
  (WO-5b: 29 + 1 xfailed). A1 Q 9000.00000009091 (rel 1.0e-11), λ 0.03; G9 OPT-N1 `INFEASIBLE_REPORTED`.
- **G1** F0 at `1d909ef9`: PASS (M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35).
- **G2 re-take (D-44)**: `scripts/opt_m03_dump.py` on the original base `ad971d32` (temporary worktree, removed) and on
  `1d909ef9`. Audited env (`OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=<m05>/.venv-nlp/share/pyomo`,
  `--nlp`): both `b6bbafdb0c83b0148e7a3d324b81ad93e6935e6731833cd325f162e6ec8b9324`, **identical**; reports solved —
  NLP-1 and E01-TAC `KKT_POINT_VERIFIED` (3/3 starts), NLP-INF `INFEASIBLE_REPORTED` (3/3). Default env: both
  `6e028e8ddaa13948e4be80444f50a41af13ef8f250c3d96f72d3fcee6fa7bbe0`, identical.
- Default env (`test_opt_*.py test_m03_schemas.py test_m03_nlp_isolation.py test_m03_nlp_status.py
  test_t08_w4_package_data.py test_e01_b_studies.py test_m05_study_record.py` at the A-1 tree): 446 passed;
  `test_opt_revision_optimize.py` at `1d909ef9` 16 passed; M03 sensitivity core/syn001/reference 61 passed at D-45.
  ruff clean; mypy: the 3 pre-existing `benchmarks/opt`/test errors only. `analytic.py --check` current.

## WO-6 (the `optimize` job, records stored, replay, surfaces, surface link; design §4.8–§4.13)

- Merge of `origin/main` (X10) into `wp/OPT` at `33a59d4d`: clean, no harvest conflict; `t08_support_matrix.py --emit`
  changed nothing; `HARVEST_SIZE` stays main's (74, 977, 126); `test_m07a_harvest.py` + `test_x10_inventory.py`
  10 passed; F0 PASS (M1 50/50 … M9 35/35).
- D-51. DECISION: surface-chain numbering → OPT's link is `c_4` (main holds c_1–c_3 at `33a59d4d`). `wp/MSG` and
  `wp/X02` each also claim `c_4`; by §4.13 / X02 review ruling 4, **OPT renumbers to the next free index and
  re-measures its digest on the merged tree if MSG or X02 merges into `main` first**. Reversible by: renumbering.
- D-52. DECISION: Ipopt interruption (§4.10) → `greybox._Iterations.interrupt` calls the job's check once per
  iteration; a `JobInterrupted` is kept (`stopped`), the callback returns `False` (Ipopt `User_Requested_Stop`) and
  `solve_start` re-raises it after Ipopt returns (an exception raised through Ipopt's C callback would not reach the
  job). Caught by name (`except JobInterrupted`), so `test_t07_interrupt.py`'s lint holds. `interrupt=None` (M03,
  every library caller without a check) is the old callback. `optimize_revision` passes its `check`. Reversible by:
  the library-hooks commit.
- D-53. DECISION: per-start `max_wall_time` (§4.10) → `optimize_revision(wall_time_remaining=)`; the job's is its
  `wall_time_s` budget minus the time since the body began (an over-estimate by the executor's start-up only: the
  job's own check, also in every Ipopt iteration, is what ends it `timed_out`). Capped below at 1e-3 s (Ipopt needs
  > 0). The cap enters `optimizer.json`'s `options` only when the budget binds, i.e. on a job that times out; G12 runs
  without a binding budget. Reversible by: `revision._start_options`.
- D-54. DECISION: the `record` stage boundary → inside `optimize_revision`, before the report and manifest are
  written (`progress("record")` after `check()`), so an interruption at `record` leaves neither (§4.10 "no report and
  no manifest"). Reversible by: `revision.optimize_revision.finish`.
- D-55. DECISION: the job's resolve stage → revision `not_found` → `failed(not_found)` (as `solve`); the solver probe
  again (`failed(unsupported nlp_solver_unavailable)`, the "extra vanished" case); `request_problems` →
  `failed(invalid_request)` at `/body/request<pointer>` (the schema `$ref` already validated the form at admission;
  this is the canonical/semantic rest, `retryable: false`); the policies by `resolve_policies` on `revision_eo`
  (OPT's only route) with the body's solve members (`OptimizeBody.solve_body()`), refusals as `solve`'s. A route that
  does not bind is the report's (`UNSUPPORTED`, REVISION_UNBOUND/OPTIMIZATION_ROUTE_UNAVAILABLE), not a failure. D-46's
  unaudited-stack refusal stays a report (`completed`, `UNSUPPORTED(NLP_SOLVER_UNAVAILABLE)`). Reversible by:
  `runner._Body.optimize`.
- D-56. DECISION: `EffectiveBudgets.max_property_calls` of an `optimize` job → the body's value as requested (the
  budget is each production solve's, through its policy); admission does not resolve the policy (§4.10 "everything
  else is decided in the body"). Reversible by: `local._admit`.
- D-57. DECISION: record artifacts → every file `<job_id>:optimization/<path>`; each complete bundle under
  `starts/<k>/` (`start`, `resolve`) by `bundle_rows` (kind `replay_bundle`, members `<bundle id>/<file>`); a bundle
  without its manifest (interrupted) is not registered; the base revision copy `revision-document.json` is kind
  `revision_document`; the six new kinds have fixed file names in `ARTIFACT_FILE_NAMES`. The answer
  `job_result.optimization` is read from the `optimization_report` output (as `reproduce`'s report), not duplicated in
  `worker_result`. Reversible by: `runner._Body._optimization_record`, `local._result`.
- D-58. DECISION (escalated, for the reviewer): T07 Q26 "no external state" (`tests/test_t07_q26.py`) finds 8 numeric
  containers under `submit_job` `body/request` (explicit starts, expression `linear` maps, assessment coefficient
  arrays/maps) and will find the same under `validate`'s `optimization`. They are the problem's definition and
  decision-space starts (model inputs, R-235's class), not solver state. Default: pin them by full path in the test's
  model-input allow-list (as R-235's `body/inlet/n`), with the scalar inventory extended likewise; not yet done.
  Alternative: drop numeric starts from the job body (moves the request schema, which is frozen as WO-3's).
- D-59. DECISION: `validate`'s member and the link's register entry → `LocalApplication.validate(revision_id, task,
  optimization=None)` and the operation's optional member; the `Application` Protocol in `contract.py` (verbatim
  from `interfaces-frozen.md` §1) is not edited: an added optional keyword keeps the method a structural match, and
  Amendment 16 lives in ADR 0071 (as 5–15 live in theirs). Register number R-960, provisional (R-950 X02's, R-951…
  X05's). Reversible by: `49b2b50c`, `2669896b`.
- D-60. DECISION: R4-G3's test resolver (`test_t07_w5e_application_results._resolved`) met a cycle:
  `optimization-request.schema.json#/$defs/optimize_body/properties/request` `$ref`s its own document's root, whose
  `$defs` hold the body again. A cyclic `$ref` met inside a `$defs` member now becomes a `$comment` naming it; one
  elsewhere still raises. Only inputs that raised before take the branch (no earlier snapshot moved). The MCP binding
  never descends into `$defs` and serves the schema unchanged. Alternative: move `optimize_body` into
  `job.schema.json#/$defs` (departs from design §4.10's location). Reversible by: `224f3154`.
- D-61. FACT: the two description texts changed (design §4.12) void their T08.A18 reviews: `REVIEW.json` holds the new
  hashes with both reviews pending, so `tests/test_t08_w2_description_reviews.py::test_every_description_is_reviewed_by_both_lanes`
  is red (4 open: `validate`, `submit_job` × design lane, Frank) until the reviewer and Frank review them (no agent
  marks them). `validate.md` said the optimization task is refused, false since WO-3.
- D-62. DECISION: replay details (§4.9, `studies/nlp/replay.py`) → (a) the policies are read from the first start
  bundle's `solve-policy.json`/`check-policy.json` and must hash to the manifest identity's; (b) the mode is
  `exact_replay` iff every bundle reproduction is, `inspected_archived_results` if any is (verdict `NOT_RUN`), else
  `compatible_reproduction`; (c) `recorded_environment` is the manifest's `environment`, `current_environment`
  `{"run": environment()}`; (d) identity failures are listed under `tampered` as `optimization-manifest.json#/<member>`;
  (e) the start phase is re-run on a host without a sink (no bundle written) and the solver probe answers available
  (replay solves no NLP); (f) `verdict_changed_near_threshold` carries the bundles' entries only: the verification
  document's active-set flip near a threshold (§4.9's 1e-9 rule) is NOT yet implemented — a flip is a plain
  difference (`MISMATCH`). Reversible by: `6d30efa0`.
- D-63. DECISION (for the reviewer): G12's mask → wall-clock members only, and all of them: each start's
  `wall_time_s` in the report; each bundle's `run-manifest.json` `started_at`, `elapsed_seconds` and the
  `manifest_sha256` over them (measured: the only members of the 6 run manifests that differ between the library and
  the inline job); those files' SHA-256 under the record manifest's `members`. Every other byte of the record is
  compared as it is (inline and spawned worker). The design says "byte for byte"; two library runs differ in the same
  members, so no record can meet it unmasked. Alternative: make `run_revision_session` write no clock into the
  bundle (moves the run-bundle format). Reversible by: `a2020a14` (the test's `_masked`).
- D-64. DECISION: §4.9's dispatch details → `LocalApplication.reproduce` imports a record (no `manifest.json`, an
  `optimization-manifest.json` naming the format) as `import-<n>:bundle`, kind `replay_bundle`, with one member, its
  manifest (`optimization_manifest`; `record_rows`), so `get_artifact` shows the record's manifest; the `reproduce`
  job dispatches on the copy's format to `replay_optimization(stage=self.at)` (stages as `reproduce_bundle`'s); the
  re-run bundles are registered as artifacts `<job>:rerun/starts/<k>/<start|resolve>`, not outputs: the report is
  the job's one output. CLI `replay DIR [--rerun]` dispatches likewise. Reversible by: `0e0c8ea3`.
- D-65. DECISION: CLI `optimize` → exit 0 iff the report is `KKT_POINT_VERIFIED` (as `solve` exits 0 iff
  `VERIFIED`), 1 for any other report (`UNSUPPORTED` included); a request with problems prints an `invalid_request`
  error document (pointer `/request<pointer>`) and exits its §5.8 code, as `validate` prints a refusal; no record is
  written then. Reversible by: `1001f877`.
- D-66. FACT (G14): at a cancellation inside start 1's Ipopt the record holds every start's `start` bundle and start
  0's `resolve` bundle (registered as artifacts); start 0's `optimizer.json`, `candidate-revision.json` and
  `verification.json` are written with the report (`revision.optimize_revision`, `record.start_members`), so an
  interrupted job has none of them. G14's "start-0 files" are therefore its two bundles. The design's "per-start
  files already written stay" holds; writing the per-start members as each start ends would be a change of
  `optimize_revision`, not made here.
- D-67. FACT (G16): "R0 content" of a certificate is taken as `run.identity.r0_projection(...)["certificate"]`
  (status, false-success flag, check ids, results and near-threshold flags, regularity status and dimension,
  limitation kinds), the projection a run's `artifact_r0_sha256` hashes.
- AMENDED_TESTS (WO-6): `tests/test_t07_adr0008_jobs.py::test_c_each_operation_has_exactly_one_request_branch`
  (the `optimize` branch, additive) and `::test_c_an_operation_outside_the_enum_is_refused` (its `optimize` example is
  now an operation; replaced by `optimise`).

### Gates (WO-6 part 1, 2026-11-08, TRS2, worktree `wp/OPT`)

- G1 F0 after the main merge (`33a59d4d`): PASS (M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85,
  M7 52/52, M8 105/105, M9 35/35).
- G2 at the library-hooks tree (audited env, `--nlp`): `b6bbafdb0c83b0148e7a3d324b81ad93e6935e6731833cd325f162e6ec8b9324`,
  identical to WO-5c's.
- Audited env `m03_nlp_check.sh -- test_opt_benchmarks_nlp.py test_opt_boundary.py`: 8 passed (G7/G8/G9/G10 with the
  interrupt hook in the callback).
- Default env: `test_t07_adr0008_jobs.py test_opt_revision_optimize.py test_opt_request.py test_t07_interrupt.py
  test_m04_study_job.py test_package_imports.py` 118 passed, 1 failed (`test_a42_…`, surface decomposition: needs
  `without_opt`); `test_opt_job.py` 2 passed. Surface-chain/digest/Q26 tests fail until part 2 (handoff).

### Gates (WO-6b, 2026-11-08, TRS2)

- Default env: `test_m07a_surface_chain.py test_t08_w2_surface_digest.py test_t07_w5e_application_results.py
  test_m04_study_job.py test_t07_q26.py test_t07_w6b_mcp.py test_t07_w6c_descriptions.py test_t07_w5a_operations.py
  test_opt_job.py` 172 passed; `test_t08_w2_description_reviews.py` 1 failed (D-61, by design); HTTP/CLI/Q26/global
  state 65 passed; `test_opt_request.py` + operations + descriptions 137 passed; `test_opt_replay.py` 4 passed.
- Audited env (`m03_nlp_check.sh -- tests/test_opt_replay_nlp.py`, thread pins 1): 5 passed (G13 x86 half).
- Surface link c_4: served `3fb06cad02649f1d8489c73551583f496ad38ae8c7109d29ae68166f5998c8a5`, stripped = D_3
  `455d01eb…`.

### Gates (WO-6c, 2026-11-08, TRS2; at `adab74c4`)

- G1 F0 (`scripts/corpus_identity.py --check`): PASS (M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85,
  M7 52/52, M8 105/105, M9 35/35).
- G2 (audited env, `--nlp`, `OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=<m05>/.venv-nlp/share/pyomo`):
  `b6bbafdb0c83b0148e7a3d324b81ad93e6935e6731833cd325f162e6ec8b9324`, identical to WO-5c's and WO-6 part 1's; reports
  solved: NLP-1 and E01-TAC `KKT_POINT_VERIFIED`, NLP-INF `INFEASIBLE_REPORTED`. Protocol fact: setting
  `OPENBLAS_NUM_THREADS`/`MKL_NUM_THREADS` as well changes the dump (the report's `solver.environment.thread_variables`
  records them: 6 members, `31532673…`, the same at `c85c8736`, `de18aca2` and `adab74c4`), so G2 sets
  `OMP_NUM_THREADS` only, as before.
- Audited env (`m03_nlp_check.sh -- test_opt_benchmarks_nlp.py test_opt_boundary.py test_opt_replay_nlp.py
  test_opt_job_nlp.py`, thread pins 1): 19 passed — G7–G10 (8), G13 x86 half (5), G12 inline + spawned, G14 cancel +
  budget, G16 OPT-A2 + OPT-A3 (6).
- Default env: `test_opt_replay.py` 6 passed (G13 fixture, `reproduce` and CLI dispatch); `test_opt_cli.py` 3 passed
  (G11 CLI half); CLI/jobs/reproduce/import/surface files (20 files) 314 passed, 1 skipped; support-envelope files
  343 passed, 1 skipped; `t08_support_matrix.py --check` 0 problems.
- Default env `test_opt_*.py` + description/application-result/MCP/description-text files: 269 passed, 1 failed
  (`test_every_description_is_reviewed_by_both_lanes`, D-61, by design), 19 deselected (`nlp`).

## WO-7 (cost and LCA gates, user docs, evidence manifest; design §5, §6 G19–G21, §9.6)

- D-68. DECISION: §4.9's near-threshold rule (closes D-62 f) → `replay.verification_differences`: an active-set flip
  (a member of `verification.json`'s `active_set` in one document only) is near when the flipped member's slack in
  the document holding it satisfies ‖s| − τ_active| ≤ 1e-9·τ_active and, for a declared constraint's side, the other
  document's `slacks` entry does too (a bound's slack is in one document only). If every flip is near, the entries
  that depend on the active set alone (`active_set`, `kkt`, V3's `active_set`, every V5 entry) and, for a start that
  flipped near, its classification — with the report's status and reasons when only such starts moved — are listed
  under `verdict_changed_near_threshold`; the verdict is then `MATCH` if nothing else differs (ADR 0007 D2.4's
  analogue). Any other difference, or any far flip, stays a difference (`MISMATCH`). Tests
  `tests/test_opt_replay.py::test_s49_*` (4). Alternative: a flip near threshold still `MISMATCH`, only labelled.
  Reversible by: the D-68 commit.
- D-69. DECISION: G19/G20's cases (design §6 leaves the decision, box and assessment open) → `benchmarks/opt/cost_lca.py`
  writes `requests/OPT-C.json`, `requests/OPT-L.json` and `cost_lca.json`. **OPT-C**: TH-C1 under P1's assessment
  document (E01's TAC program, every item costed), decision `SPEC-P-P` (pump outlet P) in [8.5e5, 1.6e6] Pa, scale
  1e6, min TAC/1e5, starts explicit 1.0e6 and 1.4e6 (`include_revision: false`: the revision's 3 MPa is outside the box
  and in another regime, T `units:1`). In the box every item but B is on its size floor and B on pressure piece "1"
  (asserted at every evaluated state), so TAC is smooth with an interior minimum (no bound case needed). **OPT-L**: TH-C1
  under P4 (P1 + E01's LCA fragment, `test-background-v1`, `climate_change_test` = IPCC AR6 GWP100 factors), decision
  `SPEC-B-T` in [640, 720] K, scale 100, min GWP rate/0.01 s.t. (−T.W − P.W)/1e4 ≥ 1.56 (declared scaled, as the schema
  says). Expectations: golden section (to 1 Pa; TAC's binary64 noise limits it near 0.2 Pa, measured) and bisection
  (to 1e-7 K) over certified `revision_eo` re-solves (`bind_route` + `solve_route`, `VERIFIED` required), TAC by
  cost_hand's forms on sizes computed from the state (E01 §4.4.1 Underwood areas, §4.4.5 head from P1's recorded
  inlet volume, §4.7 chain/opex, §9.2.7 η_m), GWP by lca_hand's unit scores and convention. Self-check: on P1's own
  state the hand chain reproduces P1's sizes (worst 9.5e-16) and `opex.total` (4.0e-16). The audited env has no
  mpmath: its test calls `cost_lca.py --at` in an interpreter that has it (`OPENFLOWSHEET_HAND_PYTHON`, else the main
  checkout's `.venv`). Reversible by: the G19/G20 commit.
- D-70. DECISION + FACT (for the reviewer): OPT-L starts at 650 K (infeasible side, W = 15411 W < W_min). Measured
  (audited env): from the feasible side Ipopt crawls to `max_iter` 500 (`SOLVER_FAILED`, V5 fails at the point it
  stopped) — revision start 673.15 K (decision 673.15 → 672.92 K in 500 iterations, inf_du stuck at 2.56e-4,
  mu 1.8e-6 from iteration 5, complementarity 4.2e-2), and likewise with objective scale 1e-3, decision scale 10 and
  a start at 661 K; from 650 K it reaches `KKT_POINT_VERIFIED` in 181 iterations. G19 (no active user constraint)
  converges in 11. The crawl is the optimiser's robustness on a near-linear objective whose constraint must become
  active from the interior (monotone mu with L-BFGS); not a correctness defect (nothing is verified that should not
  be), but a declared limitation and a question for the design lane (e.g. `mu_strategy adaptive`, which moves Ipopt
  options frozen since M03). Alternative: keep the revision start beside 650 K (status still verified, start 0
  `SOLVER_FAILED` in the reasons). Reversible by: the request's `starts`.

### Gates (WO-7 part 1, 2026-11-08, TRS2)

- G19 (audited env, `tests/test_opt_cost_lca_nlp.py`): `KKT_POINT_VERIFIED`, both starts verified (11 iterations each),
  active set empty, V7 pass; P* = 1159042.151276523 Pa vs golden section d_gs = 1159042.380571553 Pa: |Δ| 0.23 Pa
  ≤ 10 Pa (1e-5·scale); V6 TAC 116859.136761127 vs hand at the certified candidate 116859.13676112708 USD/yr (rel 6e-16
  ≤ 1e-9).
- G20 (same): `KKT_POINT_VERIFIED` (181 iterations), active set [W-net-min], λ = 0.2859 > 0, V7 pass;
  T* = 660.4145192357499 K vs bisection root 660.4145192354918 K: |Δ| 2.6e-10 K ≤ 1e-4 K (1e-6·scale); V6 GWP rate
  0.024254495503279832 vs hand 0.024254495503279832 kg CO2-eq/s (rel 0 ≤ 1e-9); hand slope +5.19e-6 kg/s/K.
- Default env: `tests/test_opt_cost_lca.py` 5 passed; `cost_lca.py --check` current; `tests/test_opt_replay.py`
  10 passed (D-68).
