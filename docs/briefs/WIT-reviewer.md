# Reviewer brief: WIT — the derivative witness at small and dormant flows, the single review pass

Status: brief, 2026-11-08. Spec `docs/derivations/K04-certificate-spec.md` §4.8.1–§4.8.9 (+ §18 findings 9–11), ADR
0073 (Proposed), reference `docs/derivations/scripts/wit_reference.py` + `.json` (WIT.A01–A14), all on main
(`5b9eb0f6`). Branch `wp/WIT`, worktree `.claude/worktrees/wit`, head `c32e3e4b`. Log `docs/WIT_DECISIONS.md` (D-1…D-4),
handoff `docs/WIT_HANDOFF.md`. No manifest yet (to be filed under `evidence/K04/`).

## The question

Does `wp/WIT` implement the spec so that the witness stays an independent check of the AD Jacobian (never reading it),
changes no certificate that passes today, and turns only today's spurious failures into honest verdicts — and what is
the ruling on E-1?

## Measured (engineer's numbers)

A01–A14 all pass on TRS2: surrogate (`benchmarks/m04/c1-surrogate.json`) VERIFIED with `[near_threshold,
surrogate_model]`, on-pattern 3.900405e-08, escalated max 4.28e-10; G7(c) δ=1e-4 on-pattern 4.98e-11 still UNVERIFIED
(ill-conditioned); GP-C3 340/345/354 K bitwise unchanged, 365/375/385 K VERIFIED with `S4.liq.<c>` declared; A06/A07
no escalation of passing columns, escalation residual-only; A13 F0 PASS; A14 ADV-06 bitwise. Sweep of witness,
verify_revision, envelope and `test_k04*`: 2717 passed, 1 failed (E-1). Moves: M-1, M-2, M-3 (X10 inventory: only
`c1.reactor_surrogate × pr-c1-v1`; L-X10-1 removed, harvest E→S), M-5; M-4 (OPT D-42/D-82) waits for the OPT merge.

## Rule on each

1. **E-1:** `test_m02_wo8_g7.py::test_g7c_the_near_dew_window_edges_as_the_manifest_states_them[0.00053-UNVERIFIED]`
   now VERIFIES: the escalation resolves `S3.n.NH3`, so the two-phase edge moves from the witness edge δ = 5.48e-4 to
   the regularity screen's absolute limit (δ 1e-4…2.4e-4 UNVERIFIED ill-conditioned; 2.6e-4…5.7e-4 VERIFIED with only
   `derivative_witness_partial`). `c1.tp_flash`'s manifest text (`src/openflowsheet/models/c1/flash.py:343-349`) and
   two G7(c) docstrings state the old edge. Is the new verdict correct (an honest VERIFIED), and should it be adopted as
   M-6 (test case + manifest sentence in one commit)? Does that manifest text enter any registered identity (F0, model
   manifest digests, `model_version`)? If it does, say exactly what moves — that becomes Frank's decision.
2. Independence and soundness of the escalation (halved steps, fourth-order stencil, agreement within 1e-8 = τ/10,
   k ≤ 8; never reads the AD Jacobian); can it ever declare agreement on a wrong Jacobian entry (e.g. a kink, a
   discontinuity, round-off plateau)?
3. The dormant-vapour forward set (affinity premise beyond GP-C3's heater — the spec's Q-WIT-4) and the dormant-liquid
   declaration (D-1 reuses reason `pr_c1_zero_flow_columns`).
4. D-2, D-3, D-4; the no-move claim for every passing certificate (A13/A14 + the spec's argument).

## Deliverable

`docs/reviews/WIT-review.md`: verdict, must-fix, should-fix, one ruling per item, what the review did not establish.
Commit on **main** (docs-only, named path, message `docs: WIT review`, with the session's Co-Authored-By /
Claude-Session lines). Do not edit `wp/WIT`. Never set `reviewed`. Do not spawn sub-agents. Report ≤ 30 lines.

## Machine-load rule

TRS2: `uptime` first; targeted tests only, one at a time, `OMP_NUM_THREADS=1`; no full gate.

## Out of scope

OPT, RRC, X02; the regularity screen's thresholds; tolerances; style.
