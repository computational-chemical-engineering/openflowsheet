# S02 ruling round 1 — three WO-1 questions before WO-2 (design lane, `specifier`, small pass)

Branch `wp/S02`, worktree `/home/user/ofs-s02`. WO-1 is done (`b78f349`, `5cad63d`). WO-2 cannot build M1/M2/M4
until Q1 and Q2 are ruled; both touch scaling or a frozen interface (CLAUDE.md agent budget: stop for a ruling).

## The questions (full text: `docs/S02_DECISIONS.md:35-37`)
1. **Q-S02-WO1-1 — φ's kind.** Spec §0 (`docs/derivations/S02-spec.md:12`) and §2.2 (:70, :83) say `φ` is of an
   existing kind `dimensionless`. But `QuantityKind` (`src/openflowsheet/compile/spec.py:31`) has only `molar_flow |
   molar_flow_squared | temperature | pressure | heat_rate`, and `REGISTERED_NOMINALS`
   (`src/openflowsheet/numerics/scaling.py:41`; SYN-001 §9; `benchmarks/registry.yaml` `scales`) has no
   `dimensionless`, so `Scaling.from_kinds` refuses M2's `<U>.stage.1.phi`. Engineer's default: add `dimensionless`
   as a column kind with nominal 1 (no row kind; `KIND_TOLERANCE` unchanged). Rule: is that a frozen-interface /
   registered-table change (check `docs/interfaces-frozen.md`), does `registry.yaml` carry it, does it need an ADR
   (next free 0044), or should φ be reformulated (e.g. a molar_flow column such as reflux flow) so no kind is added?
2. **Q-S02-WO1-2 — the constant stage-1 label.** §2.3 (:85-) labels stage 1's `ZERO_FLOW` by the constant `T_1⁰`
   when there is no `top` inlet (M1, M4). The frozen `ZeroFlowForm.label = (row, T_out, T_label)`
   (`src/openflowsheet/orchestrator/region.py:227`) must name a column (`splits.py:560-566` refuses a non-column).
   Options: (a) a pinned column `<U>.stage.1.T0` with row `T0 − T_1⁰*` (additive; §3's DOF count and `ref.dof` gain
   one column and row per such column); (b) a constant label (frozen interface, ADR). Engineer's default (a).
3. **Q-S02-WO1-3 — accumulation of the total condenser's rows** (ADR 0008 D3.5): implemented `COL-tc-bal`
   `holdup_balance N_i`, `COL-tc-energy` `holdup_balance U`, other S02 rows `algebraic`. Confirm or correct.

## Exit test
A dated "Amendment 1" section in `docs/derivations/S02-spec.md` with the three rulings and their reasons; if the
DOF count or registered values move, update `docs/derivations/scripts/s02_reference.py` and its JSON so `--check`
passes; register entries **R-536…R-539**; an ADR 0044 only if a frozen interface or registered table changes.
Commit (`S02 (ruling 1):` prefix, the two trailer lines). Report ≤ 100 words.

## Out of scope
Other spec changes; implementation.
