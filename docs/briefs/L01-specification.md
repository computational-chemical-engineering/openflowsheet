# L01 — component-library gaps for the OpenIDAES-450 development half (design lane, `specifier`)

New scope (Frank, 2026-10-22). Branch `wp/L01`, from `wp/C-merge` (main + C2 + C1 + C3; C2's split is needed).

## The question
Write a short ADR (use case, affected requirements, acceptance evidence) and a specification for adding **Water
first**, then the next most-blocking components, to OpenFlowsheet's component library **using existing property
methods only**, judged on the **development half** of OpenIDAES-450 only. If a component needs a new property method
(e.g. IAPWS-95, an activity-coefficient or electrolyte model, a liquid PR regime not yet supported), record that and
stop that component.

## Rules that bind (Frank)
- Development half only: `benchmarks/m06/openidaes450/split.json#/development/case_ids` (225). Never read, cite or
  count held-out rows (C2 registration `docs/derivations/C2-OpenIDAES-450-split-registration.md` SPLIT-R08…R11).
  The all-450 files (`coverage.json`, `case_facts.json`) must be filtered to development ids before any count.
- Disclosure: the build lane printed an all-450 top-8 unavailable-component list on 2026-10-21 (C2 registration,
  disclosure bullet). Do not use it; the development counts below replace it.

## Facts with anchors
- Development-half tally (build lane, 2026-10-21, from `coverage.json` rows filtered to development ids): classes
  UNIT_UNAVAILABLE 184, NOT_STEADY_STATE 32, COMPONENT_UNAVAILABLE 9. Unavailable components by case count: H2O 139
  (+ `water` 9, same CAS), CO2 38, NaCl 29, O2 16, benzene 15, toluene 14, ions (Cl⁻, Na⁺; never available, W27-R15).
  Cases blocked only by component/route reasons: water/H2O 7, benzene 2, toluene 2, ethylene glycol 2, ethylene
  oxide 1, sulfuric acid 1, methanol 1.
- Availability rules: `docs/derivations/M06-W27-registration.md` §5.5 W27-R15/R16 (CAS identity; available iff a
  non-synthetic component record of some snapshot route has that CAS) and §5.6 W27-R18…R20 (method equality; a route
  must admit each component in every phase kind the case's package declares; `pr-c1-v1` → `cubic_pr`).
- Existing routes: SYN-001 (synthetic, matches nothing) and PR C1 `src/openflowsheet/thermo/pr_c1.py` (vapour-only;
  records `benchmarks/m01/components.yaml`, five records H2, N2, NH3, Ar, CH4, ~110 lines each with cited T_c, P_c, ω,
  c_p, ΔH_f; mirrored in `src/openflowsheet/_data/benchmarks/m01/components.yaml`; `RECORDS_PATH` `pr_c1.py:67`).
  Decision context: ADR 0026 (PR vapour-only route), ADR 0022 / dossier for sources (`chemicals`/`thermo`,
  NASA TM-4513 for c_p).
- **Identity risk:** the C1 records and provider data are hashed into committed v0.2 records (journey, M02/M05
  dumps, W27 snapshots). Editing `benchmarks/m01/components.yaml` would move them. Decide whether new components go
  into a new component file/route id rather than the C1 one, and say what identity moves.
- Coverage re-take tool: `python -m benchmarks.m06.w27.coverage --snapshot <json> --out <path>`
  (`benchmarks/m06/w27/coverage.py:592-611`; `snapshot.build_snapshot()` reads the installed registry). The re-take
  report must be over development ids only.
- Register numbering: **R-520…R-529**; ADR number: next free after S01's (S01 took none) → **0043**.

## Deliverable (exit test)
1. ADR 0043 (Proposed) + `docs/derivations/L01-spec.md`: per candidate component in development-blocking order —
   available via an existing method (which route, which phases), or `needs new method: <name>` and stopped; record
   format and cited sources per value; identity consequences; numbered assertions `L01.A01…` with independent
   expectations (e.g. cited-source values, CAS check digits, PR pure-component checks against a published reference
   point); the coverage re-take procedure over development ids and how the change is reported (before/after counts).
2. Work orders for `opus-engineer` (~120k context each).
3. Register entries R-520…; DECISION lines in `docs/L01_DECISIONS.md`; Frank questions in `docs/FRANK_QUESTIONS.md`.

## Out of scope
New property methods; held-out data; changing W27's registration or committed records; units (UNIT_UNAVAILABLE).

## Agent rules
Context cap ~120k; at the cap commit, write a ≤ 30-line handoff `docs/briefs/L01-handoff.md`, stop. Report ≤ 150 words.
