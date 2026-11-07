# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md` (§4.1 host, §4.2 revision host, §4.3–4.5, §4.11, §5 WOs, §6 gates);
ADR 0071 (Proposed). Build decisions, facts and gate numbers: `docs/OPT_DECISIONS.md` (D-1…D-22).

## Done

- **WO-1** — `studies/nlp/host.py` (`NlpHost`, `Syn001NlpHost`, …); M03 takes a host. G2 tool `scripts/opt_m03_dump.py`.
- **WO-2** — `RegionResult.final_system`; `write_revision_bundle`; `SensitivityHost.system`; `studies/nlp/revision_host.py`
  (`decision_map`, `RevisionNlpHost`: certify, held system, regimes, sensitivity, twin cache, bounds).
- **WO-3** — `schemas/optimization-request.schema.json` (+ registry, README, fixtures `tests/fixtures/schemas/
  optimization_request/`, numerical-policy addendum `benchmarks/opt/`); `studies/nlp/request.py` (`request_problems`,
  `OptimizationRequest`, Halton, `request_starts`, `request_formulation`, `static_readiness`); `closure.py` platform-aware
  `audited_solver`, OPT codes in `READINESS_ORDER`; `validation.validate(doc, "optimization", optimization=,
  solver_probe=)`; `LocalApplication.validate` refuses in §4.11's order. Tests `tests/test_opt_request.py`. G1 F0 PASS.

## Next

- **WO-4** (§4.4, §4.6, §4.8, §4.12 Python): build `NlpFormulation` via `static_readiness(...).formulation` (decision
  names already translated to parameter ids — `FullSpaceNlp` must accept parameter ids in expressions and M03's
  `UNKNOWN_VARIABLE` must not flag them on the revision host); assessment binding at the first passing start (D-18:
  also the program-level `ASSESSMENT_OUTPUT_UNKNOWN`/`ASSESSMENT_PARAMETER_*` checks there); extend
  `optimization-report.schema.json` `$defs/reason` enum with the new codes when the first report carries one (D-17);
  `FullSpaceNlp` must lift D-7's refusal of held columns/labels; `optimize_revision`; benchmarks `benchmarks/opt/`.
- **WO-6** owes (D-19): `optimization` member on `LocalApplication.validate`, `OPERATIONS["validate"]` input schema +
  decode, `descriptions/validate.md` (still says `task_unsupported(optimization)`), CLI `validate --request`;
  `benchmarks/t08/support_envelope.yaml` U05 text.
- Open for the design lane (OPT's reviewer pass): D-12 (no margin on pr-c1 / composition-dependent K); D-18 (static
  assessment checks deferred to the first certified start).

## How to run

- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial).
- Audited nlp env: `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05; scripts/m03_nlp_check.sh --no-inventory
  $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>` (runs `nlp`-marked tests only).
- G1: `PYTHONPATH=src .venv/bin/python scripts/corpus_identity.py --check`. Policy: `scripts/t08_numerical_policy.py
  --check`. No full gate until WO-7. TRS2 ≤ ~36 busy cores (`uptime` first).

## Anchors

- `studies/nlp/request.py` `static_readiness`, `request_formulation`; `application/validation.py`
  `_validate_optimization`; `application/local.py` `validate`; `studies/nlp/closure.py` `audited_solver`.
- `studies/nlp/revision_host.py` `decision_map`, `RevisionNlpHost.certify`, `.bounds`.
