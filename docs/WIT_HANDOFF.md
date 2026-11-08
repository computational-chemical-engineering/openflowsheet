# WIT handoff (branch wp/WIT, worktree .claude/worktrees/wit)

Status: review fix round done (review `docs/reviews/WIT-review.md`, main 1476a017). No manifest (orchestrator).
Full gate NOT run (orchestrator runs it before merge). Nothing set `reviewed`.

## Fix round (commits on wp/WIT, after merging origin/main)
- 8a9bb7a8 F-1: §4.8.3 (c) flat rule in `escalate_column` (`registered=` the registered pair; `Escalation.barred`);
  WIT.A15 (W4, 9 configurations) fails first 7/9, passes 9/9; generator mirrors the rule, adds W4 (56 claims).
- ba420ab4 F-2: `witness_classes` skips a split whose feed is all exactly 0.0 (ZERO_FLOW); unit tests.
- 9decd7d4 F-3: tests for §4.8.3 (d) unresolved escalated refusal and (f) order rule.
- 97ef496f F-4: A1 measured on a flash-style split (GP-C1 tp_flash held LIQUID): VERIFIED, fwd vs AD <= 1.32e-10.
- b413a4a9 D-1: ADR 0073 D5 amended; Wilson class-2 record reason `wilson_dormant_liquid_columns`.
- a9fbad5b M-6 part a: G7(c) TWO_PHASE edge (2.4e-4 U / 2.6e-4 V), 5.3e-4 VERIFIED with S3.n.NH3 escalated;
  docstrings, spec §4.8.6 M-6, R-282 note. Decisions D-5..D-10 in docs/WIT_DECISIONS.md.

## Re-measured under the flat rule (TRS2): unchanged
- A08: k* NH3 4, N2 5, Ar 3, CH4 3, H2 2, S2.NH3 1; escalated <= 4.276e-10; on 3.900405e-08; VERIFIED.
- A09: k* = 5, e_5 = 8.9e-16, on 4.98e-11, UNVERIFIED absolute. E-1 window: 1e-4..2.4e-4 U, 2.6e-4..5.7e-4 V.

## Checks at a9fbad5b (TRS2)
- F0 --check PASS: M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35.
- test_wit_*: 31 passed. Sweep (test_k04* + every test file naming derivative_witness/verify_revision/envelope,
  99 files): 3315 passed, 23 skipped. wit_reference --check OK (56). X10 --check PASS (150 pairs). Support matrix
  --check 0 problems. ruff, ruff format, mypy (303 files) clean.

## Open
1. M-6 part b (Frank): `c1.tp_flash` manifest sentence (flash.py:343-349) still states the TWO_PHASE edge at
   L/n_tot 3.4e-5; correcting it moves the artifact hash, F0 M9's flash.py entry and L01.A22's byte pin.
2. Q-WIT-4: a non-affine downstream reader of a dormant vapour product is still unmeasured.
3. M-4 (wp/OPT) after ADR 0073 acceptance; not touched here.
4. Full gate + CI both arches, manifest, then merge (orchestrator).
