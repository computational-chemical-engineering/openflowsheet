# ADR 0076 review (reviewer, 2026-11-14, read-only, at 9016d957)

Verdict: direction sound; not ready for Frank. Must-amend: I-10, I-14, I-15, I-19. Amend: I-2, I-7, I-8, I-11, I-12.
Accept: I-1 (consider the name `numerics.solve_record`: trace.py also holds SolvePlan, RecyclePolicy, HomotopyPolicy
at :289-667), I-3, I-4 (callers conftest.py:126,140, test_m02_wo14.py:175, t08_v2_substitution.py:77, 4 scripts),
I-5, I-6, I-9 (add an assertion on the recorded caller module; audit.py:27 accepts any openflowsheet frame), I-13,
I-16, I-17, I-18.

- I-2: the solver's KIND_TOLERANCE in models.lifted escapes the forbid rule (verify imports models.lifted for
  LiftedSplit, verify/checks.py:54, column.py:80). Own leaf, listed in the forbid rule. (Applied to lane a's A4 as
  `models.lifted_tolerance`, orchestrator 2026-11-14.)
- I-7: I-19's retarget of `Refusal` edits built-in contributor implementation sets (cost/operating.py:26,
  cost/index.py:30, lca/brightway.py:44, lca/tables.py:35): core.json self-hash, `registry/builtin/tables.sha256`
  (E-F1-5) and the served `registry_sha256` change. Not stated.
- I-8: split names not listed (B8 "fixed by the engineer"); derive the list from committed plans. CoolProp split is W5.
- I-10 (must): revision_run.py:381 is inside `route_structure` (inspect_structure, local.py:1539; "in no identity
  key"), not the run entry; its caller holds no ValidationReport. Fix: move `route_structure` above validation (pure
  move, about 66 references), no signature change; Q-F3 drops.
- I-11: the K06 facade carries behaviour (`record_run`, invalidation union transactions.py:167-184, `commit(ChangeSet)`;
  test_k06_application.py:50, test_t07_transactions.py:320,559, test_t07_w3b_validation.py:467). List removed
  behaviour and the tests ported or deleted.
- I-12: dispatch already routes through the facade (`getattr(app, operation.method)`, operations.py:792); keep
  OPERATIONS on the facade, services internal; name the split modules of types, store, revision_run.
- I-14 (must): Q-F2 is false (measured in a fresh interpreter: `str(api_error(...))` from application.contract freezes
  the catalogue and imports the registry today; under I-14 it would raise inside `__str__`; application.jobs.worker
  does not import the registry). Install the hook from application.errors and the worker; fresh-interpreter tests.
- I-15 (must): region imports VerifierError at region.py:817, 842, 879, 1700 too; the screen at :1711 catches only
  VerifierError; admissibility_value (:824) and the converged path (:1453) feed `except VerifierError` in
  trust_region/parent.py:317 and nlp/revision_host.py:453; a None loses `result.status` (checks.py:647). Fix: a
  solver-owned refusal exception, a solver copy of the 5-line K evaluation, a forced-refusal test per path.
- I-19 (must): frozen M9 modules column_unit.py:47,90 and coolprop_heos.py:73 import moved names; keep exactly those
  re-exports until W5 and say so. `sizing/__init__` re-exporting `core` is package API, not a shim (dropping it
  touches registry-hashed cost/contributor.py:45, lca/impact.py:39).

Cross-cutting: affected identities (F0 M9 in W5, the built-in registry hash, ADR 0060 D3) belong under Affected
requirements with the regeneration route (`scripts/registry_builtin.py`); 25 fault-injection patches
(`monkeypatch.setattr`) can become silent no-ops under I-4, I-10, I-12 (conftest WO-5a bundle count reported, never
asserted, conftest.py:116-143); doc sweeps leave records alone (ADRs, design history, manifests, decision logs);
refusals.yaml:1378 is gate-frozen, edited outside the gate; name the application-layers entries for I-3, I-4, I-9,
I-10, I-12. Not examined: I-5 closure, I-13 test privates, B1-B8 boundaries, A5 bitwise claim.

For Frank: (1) no shims versus frozen identity (F0 M9 and the registry hash change once in W5 under one ruling, or
some re-exports stay permanently); (2) I-14, a library process that has not imported the registry (hook installed
by application.errors and the worker; or a typed error, a silent freeze, a declared layer exception); (3) I-11,
deleting the public K06 facade and its `record_run` behaviour (ADR 0019 D1).
