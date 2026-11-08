# WIT handoff (branch wp/WIT, worktree .claude/worktrees/wit, from main 9c495450)

Status: implemented; STOPPED on one unlisted move (WIT_DECISIONS E-1). No manifest (orchestrator decides after review).

## Done (commits on wp/WIT)
- 94d59123 core: `checks.py` escalate_column / Escalation / witness_classes / component_column; derivative_witness
  escalation (class 5); verify_revision passes classes 1-2 unstenciled, 3-4 one_sided; _issue/_certify pass components.
- 28c889f5 system tests (tests/test_wit_system.py, tests/wit_support.py spy); analytic tests in tests/test_wit_witness.py.
- 25d2cb04 moves M-1 (OQ-5 test -> test_wit_a10_..., 340/345 K) and M-2 (G7(c) delta 1e-4 -> WIT.A09).
- a7f55241 M-3: x10_inventory --record (only c1.reactor_surrogate x pr-c1-v1 moved, --check PASS 150 pairs);
  L-X10-1 removed from support_envelope.yaml, its 2 X10 harvest items E -> S; support-matrix.md re-emitted (--check 0).
- a163ec9a M-5: S11 rulings OQ-5 / S11D_DECISIONS cross-reference to ADR 0073 (Proposed).
- docs/WIT_DECISIONS.md D-1..D-4 (+ E-1).

## Gates (TRS2)
- F0 corpus_identity --check PASS: M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35 (at 94d59123).
- WIT.A01-A14 tests pass (19). Sweep of every witness/verify_revision/envelope test + test_k04*: 2717 passed,
  17 skipped, 1 FAILED = E-1 (test_g7c_the_near_dew_window_edges_...[0.00053-UNVERIFIED]).
- ruff, ruff format, mypy (303 files) clean. Full gate NOT run (brief).

## Open / next
1. E-1: design-lane ruling (add M-6 or not). If M-6: amend the 5.3e-4 case, the c1.tp_flash manifest sentence
   (flash.py:343-349) and the two G7(c) docstrings in one commit; re-run F0 (manifest text may enter M9/identity).
2. D-1 for the reviewer: A2's limitation reuses reason "pr_c1_zero_flow_columns" (ADR 0073 D5 literal).
3. M-4 (wp/OPT D-42, D-82 (a), G24 (c) relabelled start): on the OPT merge after ADR 0073 acceptance, a γ-φ held
   single-phase split certifies (vapour held: derivative_witness_partial; liquid held: nothing). Not touched here.
4. reviewer pass on 94d59123 (numerics-adjacent: witness), then full gate before merge; CI both arches.
