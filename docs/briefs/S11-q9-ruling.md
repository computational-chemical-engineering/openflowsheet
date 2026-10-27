# S11 brief: Q9 — the column's stage splits in a flowsheet region, and three smaller track-B escalations (design lane, `architect`)

Worktree `.claude/worktrees/s11` (branch `wp/S11`, head `05d517b9`: first pass `S11-design.md` with §9 amendment, units
design `S11-units-design.md`). Track B's work is on `wp/S11-b` (worktree `.claude/worktrees/s11-b`, head `845faa48`); read
its `docs/S11B_DECISIONS.md` (80 lines: decisions, the Q9 spike trace, the handoff) — the facts below are from it.

## 1. The question

Rule **Q9** of `S11-design.md` §7 (default was "if no: escalate to the design lane with the trace; no ad-hoc region surgery"):
how do `syn001.column`'s stage splits reach the region solver when the column is one instance `UCOL` in a flowsheet region?
Give the rule precisely enough that WO-B3 has nothing to choose, with its identity argument (every registered solve —
flowsheets and the standalone column — stays bit-identical; `scripts/s11_identity.py`, `S11-IDENTITY PASS n=54497 changed=[]`).

## 2. The facts (track B's spike, A29 on M1: `feed_source → column → 2 product_sinks`, `S01_DEFAULT_V1`)

1. `bind_revision_flowsheet` binds M1 square. `plan_revision` raises `lifted_split_unregistered(syn001.column)` at
   `orchestrator/splits.check_agreement` (splits.py:470): the column's 7 × 3 `CAS-equilibrium` rows are `molar_flow_squared`
   and no descriptor names them — the staged-split plumbing §4.7.5 assigns to B3 (expected).
2. **The Q9 answer is no.** Every region map keys a split by `split.unit`. The standalone solve's region has
   `units = signature_units = (S02.stage.1 … S02.stage.N)` (`models/syn001/column_solve.py:416-423`). A flowsheet region is
   built by `execution.build_region` (`orchestrator/execution.py:404-437`) from flowsheet instances: rows by
   `declaration.rows[row].unit` (the authoring instance `UCOL`), columns by `graph.column_owner`,
   `signature_units = _lifted_units(...) = (UCOL,)`. The region solve keeps only
   `active_splits = [split for split in splits if split.unit in set(region.units)]` (`orchestrator/region.py:1876`), so
   every stage split `UCOL.stage.j` would be dropped silently: the equilibrium rows solved with no phase policy, and the
   attempt signature carrying `UCOL` instead of its stages.
3. `check_agreement` keys the `molar_flow_squared` rows by authoring instance (splits.py:463-466) and compares them to one
   descriptor's equilibrium rows (its checks (a)/(b)); a column's squared rows are N stages' rows plus the purity and
   recovery definition rows (`molar_flow_squared`, not equilibrium rows).
4. Track B's candidate shapes (not chosen): `region.units`/`signature_units` gaining `stage_unit(U, j)` for a column
   instance; or the filter at region.py:1876 resolving a pseudo-unit to its instance by the `stage_unit` prefix; plus a rule
   for check_agreement (a)/(b).

Also relevant: the units design's C6 and D6 spikes (`S11-units-design.md`) test whether the region backtracks on a block's
`invalid_trial_state` and carries the five Wilson units; if your ruling touches the same region code, say how they interact.

## 3. Three smaller escalations from track B (rule each)

- **End specifications:** B reads the column's end specs from instance parameters `condenser.<kind>[.<attr>]`,
  `reboiler.<kind>[.<attr>]` (one function `column_unit.end_entries`; a `role: fixed` specification targeting
  `parameters.<end>.<kind>…` lands there too). The first pass wanted revision *pins*, which needs a `condenser.*`/`reboiler.*`
  target path in `revision_flowsheet._PATH_KINDS` and routing in `_read` (track A's file), and a non-stream quantity in
  `PinColumn` (`revision_binding.py`). Keep parameters, or pins (and then which WO/track does it)?
- **`_PARAMETER_KINDS`:** the column's parameters are absent, so only "SI unit of the declared kind" is checked. Which WO adds
  them?
- **`models/rows.py` ownership:** B1 put a new `scaled_sum_definition_row` there (`test_k02_unit_models` forbids row builders
  in unit modules); rows.py is in neither track's §5 list. Accept or move.

## 4. Constraints

No ad-hoc region surgery: the rule must be general (any future staged unit), stated once, with the identity argument. No change
to a registered result. Frank: as few limitations as possible; batch then test once (no extra gates). Register from **R-822**
(R-813…R-821 are the units design). Prefer a minimal change to `region.py`/`splits.py`/`execution.py`; say which track owns
each file touched (track A is building A1–A4 on `wp/S11-a` now; track B resumes on `wp/S11-b` after merging `wp/S11`).

## 5. Deliverable

A dated amendment section (§10) in `docs/derivations/S11-design.md`: the Q9 rule, the check_agreement rule, the three smaller
rulings, the revised WO-B3 (and any other WO it touches) with acceptance tests; register entries from R-822; a docs-only
commit on `wp/S11` including this brief. Do not push. Report in at most 15 lines.
