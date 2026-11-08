# Architect brief: RRC — revision-region continuation (0.4)

Status: brief, 2026-11-08. Roadmap `docs/roadmap/roadmap.md:42` ("RRC: revision-region continuation · nothing ·
architect"); ADR 0057:33 (0.4 set). No design, ADR, register entry or acceptance criteria exist yet. Origin: Frank's
Q30 (`docs/FRANK_QUESTIONS.md:238-239`, 2026-10-27: "Plan for it at the appropriate time" → a follow-on package after
S11; removes L-COL-9), register R-827, `docs/derivations/S11-design.md` §10.8. One architect pass, then build, then one
reviewer pass.

## The question

How does a **revision-built region** get recovery edge 3 (continuation) when its Newton solve fails, so that L-COL-9
("in a flowsheet a column region has no edge-3 continuation (no revision region has one)") is lifted for the regions
where a continuation is well defined — and what are the work orders and gates?

## Why it needs the architect

Edge 3 is solver architecture with registered identity: every revision plan, its recorded attempts and recovery
provenance, certificates and replay depend on it. Several continuation forms were rejected on measurement or principle
(below); the design must pick a form that is not one of them, or show why a rejection no longer applies.

## Current state (recon digest, anchors on main `ec7e90b7`)

- **Edge 3 today is specification continuation only** (ADR 0010, R-030, R-031): `orchestrator/homotopy.py:74`
  `continuation_parameter(*, specification_rows, target_variables, spec, structural_pattern) -> Continuation | None`
  qualifies only *promoted* rows of form `v − p` with a one-column pattern; `:222` `continue_specification(*, correct,
  x0, continuation, policy, trace, attempt, signature, variable_ids, counters)` is natural-parameter continuation
  (Δλ doubles on accept, halves on reject, rollback, `HOMOTOPY_STALLED` below Δλ_min); it never changes the active set
  (header lines 1–20). `correct` is a generic callable. `region.py:2636` `_homotopy(...)` runs it inside
  `solve_region` (`:1763`); `RecoveryStart` `:438`.
- **Revision regions have no specification rows** (`orchestrator/revision.py:400-405`), so `continuation_parameter`
  returns `None`. The edge-3 dispatcher `orchestrator/executor.py:871` `_eo_recovery(...)`: ~896–920, if
  `continuation is None` under `homotopy_or_sequential_restart` it calls `_sequential_restart` (`:968`, one region
  solve from `traversal-G0-pass8-v1`, ADR 0015, R-075); otherwise records `eo_recovery="unsupported"`,
  `eo_recovery_unsupported="no_continuation_parameter"` (ADR 0044:54-55). Giving revision regions specification rows
  "would change every revision plan and send the executor down the promoted-specification path (`executor.py:670`)"
  (S11 §10.8).
- Plan/execute: `revision.py:354` `plan_revision` (one `solve_eo` step per row-authoring unit); `executor.py:215`
  `execute_plan` stops at the first non-converged step; outcome codes `orchestrator/trace.py` ~30–60
  (`HOMOTOPY_STALLED`, `PTC_STALLED`, `BOUND_BLOCKED`, …), `EoRecoveryUnsupported` ~90; `GlobalizationPolicy`
  `:622-636` (`eo_recovery: homotopy | none | homotopy_or_sequential_restart`), `HomotopyPolicy` `:539`.
- Standalone units with their own continuation: `models/syn001/column_solve.py:1185` `continuation(spec, profile)`,
  `:1050` `lambda_state`; `cascade_solve.py:635`. In a flowsheet the column unit's `evaluate` keeps S02's standalone
  path (S08 Stage B included), so the traversal start is the standalone answer (L-COL-9 text).
- Recovery edges `docs/recovery-edges.yaml:133-180` (E3a, E3b; continuation-parameter precondition `:138-139`,
  `:166-171`). Support matrix L20 (folds not followed), L21 (continuation only for promoted specs), L24 (arclength not
  implemented), L-COL-9.

## Already tried and rejected (do not re-propose without new evidence)

- Recycle-closure continuation (ADR 0010:103: the SYN-001 recycle is benign); global Newton homotopy F − (1 − λ)F(x⁰)
  (ADR 0010:104: λ < 1 problems are not physical); per-level full phase-contract solve (ADR 0010:106: a path crossing a
  phase boundary stalls with a diagnosed `HOMOTOPY_STALLED`; arclength deferred); edge 3 from the failed end state
  (ADR 0010:108, rejected on measurement); orchestrator-side offset (R-030).
- Split-fraction or tear-connection continuation (ADR 0015 alternatives; `docs/design/T06-F4-recovery.md` §4 row (a):
  split-fraction covers only splitter-closed loops — misses C2's separator-top recycle, NET-03's flash-liquid loop,
  NET-06's thermal loop; tear-connection level identity contradicts ADR 0010 D2 and ADR 0008 D1).
- Warm-start chaining in sweeps (R-183, ADR 0031 D5: "following a branch is continuation's job"). X02 measured that a
  neighbouring-revision warm start was no faster on the real loop (D-32: 4 = 4 outer iterations).
- Pseudo-arclength / fold following: deferred by the blueprint (`blueprint-v3.1.md:289`) and T04 spec (`:34`).

## Constraints and invariants

- F0 corpus identity (`scripts/corpus_identity.py --check`, M1–M9) must pass: every existing revision plan, attempt
  record, bundle, certificate and replay that does **not** reach edge 3 stays bit-identical; the 35 M9-frozen files are
  not edited. Where a recorded run did reach edge 3 and recorded `unsupported(no_continuation_parameter)` or a
  sequential restart, state exactly which records move and how they are re-registered (or that none move).
- The homotopy never changes the active set (ADR 0010); λ-level identity (ADR 0010 D2, ADR 0008 D1) holds.
- Typed outcomes, no placeholder success paths; certificates judged as today. Residual and Jacobian describe the same
  function at the same state.
- Machine: TRS2, 48 cores, ≤ ~36 busy; CI on x86-64 and aarch64.

## Genuinely open — decide these

1. The continuation form for a revision region (what is λ, what moves, why it is not a rejected form) and the class
   of regions it covers (which corpus revisions; which stay `unsupported`, with which typed reason).
2. How it plugs into `_eo_recovery` / `solve_region` without changing non-edge-3 plans; order relative to the ADR 0015
   sequential restart.
3. Recording and replay of an edge-3 path on the revision route (attempt records, provenance, policy members), and the
   ADR/register changes (amend ADR 0010/0015/0044? new ADR 0072).
4. Which support-matrix limitations are lifted (L-COL-9, L21) and the test that proves each lift on a registered
   revision that fails without edge 3 and converges with it.

## How it will be verified

Gates the build lane can run: a registered revision region that fails Newton from its traversal start and converges
via the new edge 3 (failing-first), with a certificate as an ordinary run's; λ-path identity and rollback; typed
refusal for uncovered regions; F0; T04/T06 edge-3 tests (`tests/test_t04_homotopy.py`, `test_t04_edge3.py`,
`test_t06_f4_edge3.py`, `test_t06_f4_restart.py`) unchanged; replay MATCH of an edge-3 bundle; both CI legs.

## Deliverable

`docs/design/RRC-revision-region-continuation.md` (work orders ≤ ~150k context each, numbered gates) and
`docs/adr/0072-RRC-revision-region-continuation.md` (Proposed; register lines drafted unnumbered). Frank questions in
plain words with defaults. Commit on **main** (docs-only, named paths, message `docs: RRC design + ADR 0072`, with the
session's Co-Authored-By / Claude-Session lines). Report ≤ 30 lines.

## Machine-load rule

TRS2: `uptime` first; at most single small probes (`OMP_NUM_THREADS=1`); no full gate.

## Out of scope

Arclength / fold following (unless you show it is the only sound form — then say so and stop), OPT, X02, X12, style.
