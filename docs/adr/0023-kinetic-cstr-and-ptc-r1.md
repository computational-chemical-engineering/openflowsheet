# ADR 0023 — A vapour-phase kinetic CSTR runs T04's preregistered PTC-R1 exactly, PTC is offered by explicit policy, and T04 §8.4's open points are resolved before any result

**Status:** **Accepted, 2026-10-02**, with its Amendment 1, with T08's tested evidence (`evidence/T08/67c66d98587f23bd7dfe8da28a8facccc92da21e/manifest.json`). Frank's decisions: F1 "build first" (2026-09-29), which this ADR answers; V14 (b) FAIL on PTC-R1 accepted for v0.1 with PTC experimental (ADR 0021 D3, 2026-09-29). The V14 (b) verdict it enabled is `verdict`'s: FAIL on the saddle clause (B23), printed FAIL. Proposed 2026-09-29, taking effect when committed with its specification. Register R-123, R-126.
**Date:** 2026-09-29
**Author:** design lane (`specifier`), T08 build-first pass. Brief `docs/briefs/T08-build-first-spec.md`.
**Normative text:** `docs/derivations/T08-build-first-spec.md` Part A (§A1–§A5) and assertions T08.B00–B27. Reference values: `benchmarks/t08/build_first_reference.yaml`, from `docs/derivations/scripts/t08_build_first_reference.py`.
**Amends (additively):**
- the unit library (a thirteenth model);
- T04's mapping registry (one model-id entry; `T04-residence-time-v1` is otherwise unchanged);
- the application policy registry (`T08-ptc-v1`);
- T08 release spec §5.2 and §5.3 (U07 replaced), and T08.A20's count.

**Reverses:** nothing registered. T04 §8.1's criterion, T04 §7.7's constants and T04 §8.3's verdict on the flash/heater family stand.
**Affected requirements:** D07 and A03 (PTC qualification, via V14 (b)), V12 (the unit library, one more model with its definition of done), D20 (new identities only, no moved ones).
**Affected packages:** T08 (builds it), T04 (its §8.4 case gains its owner), T05 (§13.2's accumulation table gains a row), M01 (its reactor inherits F2's kind constraint, see Consequences).

## Context

T04 §8.3 found that PTC improves no tested basin on SYN-001 (18/18 for both methods), and it preregistered PTC-R1 (§8.4), the Uppal–Ray–Poore exothermic CSTR with three steady states, as the case that could reopen qualification. R-118 fixes V14 (b)'s criterion: T04 §8.1 unchanged, the case committed before its results, the family selectable on a supported flowsheet, and SER tested. Frank's F1 (2026-09-29): build the holdup-CSTR route in T08 before tagging.

## Decision

- **D1. The model.** `syn001.kinetic_cstr` is specified in §A1:
  - rows `CSTR-mole` and `CSTR-duty` are `holdup_balance`; `CSTR-cooling` and `CSTR-pressure` are `algebraic`;
  - the rate law is the synthetic `r = Da exp((T − T_ref)/T_s) n_out,k`, substituted into the mole rows;
  - cooling is `Q = F_c c_c (T_c − T)`;
  - the outlet is a declared single phase, with the total-enthalpy energy row of ADR 0011 D2;
  - every pin uses an existing quantity kind;
  - the causal evaluator is the isothermal local initializer;
  - zero flow is as §A1.4.
- **D2. The realization.** PTC-R1 is run on the vapour reaction `B → A` (`Δh_r = L_A − L_B = −5000 J/mol`, ADR 0011 D2) with §A1.5's values. They give Da = 0.072, B = 8, β = 0.3 and Le = 1 exactly, and the dimensional steps equal PTC-R1's (generator-checked).
- **D3. Route (a).** `T04-residence-time-v1` gains the entry `syn001.kinetic_cstr → {CSTR-mole: component_moles, CSTR-duty: enthalpy_content}` with one declared-phase outflow. θ remains the policy's pseudo-time unit, and nothing else in T04 §6–§7 changes.
- **D4. The offered policy.** `T08-ptc-v1` is `T06-revision-v2` with `globalization.eo_core = "ptc"` only, and is added to `APPLICATION_POLICIES`. No automatic path selects PTC. U07 is replaced by the mapping-coverage row of §A2. `ptc.status` stays `"experimental"`. A qualified value comes, if ever, by an amendment after the verdict and never on the comparison's policies.
- **D5. The comparison, resolved now** (spec §A4.1):
  - the registered root is either stable steady state;
  - "reaches" means `CONVERGED` within 2e-3 (dimensionless ∞-norm) of it;
  - the arms are `T06-revision-v2` with `eo_recovery = "none"` and `eo_core ∈ {newton, ptc}`, at registered constants and budgets, with no property or wall-time budget;
  - the starts are the 441 of §A4.2;
  - the saddle clause covers all 441 starts;
  - the mechanism is B03/B14;
  - both registered platforms must pass;
  - the git order is `C_reg → C_case → C_res` (§A4.6).

## Alternatives considered

- **A liquid-phase CSTR with synthetic formation data** (`SYN-001-ref-v2`). Rejected: an edit to SYN-001's data moves every identity (ADR 0011's own rejection), and a second provider leaves the v0.1 envelope. The vapour reaction needs neither.
- **New quantity kinds** (`time`, `rate_constant`, `thermal_conductance`). Rejected for v0.1: the kind enum is referenced by MCP-exposed schemas, so T08.A49's surface would move (finding F2). The Damköhler pin and the coolant capacity rate express the same physics in existing kinds.
- **An owned extent variable with an algebraic rate row.** Rejected: it makes the linearly implicit iteration differ from PTC-R1's after the first step. The preregistered case would then not be the one run.
- **A lifted two-phase outlet.** Rejected: it adds a phase-selecting unit and signature logic that PTC-R1 does not have, for no gain in this case.
- **A causal evaluator that solves the steady state.** Rejected: three roots have no unique causal answer, and any selection rule would be arbitrary. The isothermal initializer is §7.4's local model initializer.
- **Reading "the registered root" as any root, or per root.** Rejected (spec §A4.1): "any root" contradicts the saddle clause, and "per root" scores two methods reaching different stable roots as an improvement for both.
- **`newton_refined` as the comparator.** Not needed: its refinement acts only after `CONVERGED` and cannot change a class (ADR 0018 D4). `newton` is T04 §8.3's comparator.
- **Running PTC-R1 as a bare two-variable residual.** Rejected by R-118 (not selectable on a supported flowsheet).

## Consequences

- One more model in `MODEL_BUILDERS`, with its definition of done (B10–B19) and a coupled case (the PTC-R1 flowsheet).
- One more offered policy. `list_models` and `get_project` change in content, and no schema changes.
- V14 (b) becomes decidable at the RC. If it fails it stays FAIL (R-118), and ADR 0021's proposed revision returns the tag question to Frank.
- M01's reactor meets finding F2 (no time or conductance kind). The recommended course is to batch any new kinds into one ADR with v0.2's contract changes.

## Migration

None. No schema, frozen interface, stored hash or registered result changes. Every existing run is byte-identical (B26), because no registered flowsheet contains the model and no registered run uses `T08-ptc-v1`.

## Acceptance evidence

- `t08_build_first_reference.py --check` passes (B00–B09).
- B10–B19 and B24–B27 pass in `./scripts/check.sh` on x86-64 and aarch64.
- B20: the ancestry `C_reg → C_case → C_res`, with the manifest's attestation.
- B21: the 882 runs on both platforms.
- `verdict` judges B22 and B23 (V14 (b1)) at the RC.
- A design-lane `reviewer` pass on the model, the mapping entry and the harness before `C_res`.
- `review.numerical` and `review.process_model` are not set by this ADR.

## Amendment 1 — 2026-09-29 (T08 build-first spec Amendment 1, Q1)

**D2, amended.** The realization binds on `(A, B, C)`, because the binder admits only a permutation of SYN-001's three components (ADR 0014 D9, R-076). C is an inert trace of `2⁻¹⁰` mol/s taken from A's feed, `n = (0.4990234375, 0.5, 0.0009765625)` mol/s with `ν_C = 0`. `n_tot = 1`, so Da, B, β and Le are unchanged exactly, and the trace's mode `−1/θ` factors out of the pencil (B28).

C is not carried at exactly zero. At zero its columns sit on their lower bound, where the factorization's roundoff of either sign (measured up to 2.3e-16 mol/s at the spec's §A5 states) makes PTC steps `bound_blocked` and truncates both arms' steps after a drift. Those runs would not be PTC-R1's.

**D5, amended.** The starts' digest is `0262bebcb9c5af890d770663d1e5a7cd059159bf0eb6f58bd40c04641c49a17c`, and the git order is `C_reg → C_A1 → C_case → C_res`, with `C_A1` the commit that lands the amendment. The dimensionless case, the starts' `(x₁, x₂)`, the classes, the criterion, the arms and the budgets are unchanged.

**Acceptance evidence, added.** B28 in `--check`; B21's trace clause (final `S1.n.C`, `S2.n.C` within 1e-10 mol/s of `2⁻¹⁰`, and no C-column blocker in any run); B20 with `C_A1`.

## Accepted (2026-10-02)

Recorded by the build lane (brief `docs/briefs/T08-close.md`, item 8) with T08's tested evidence at `C` = `67c66d9`: B00–B19, B21, B22, B24–B28 pass in the T08 manifest; B20 passes with the manifest's §A4.6 attestation (the clause `docs/reviews/T08-verdict-V14b.md` found outstanding) and its disclosures; B23 is FAIL, V14 (b)'s saddle clause, accepted by Frank in ADR 0021 D3 (2026-09-29). Accepting this ADR accepts the model, the mapping and the case as built; it does not turn V14 (b) into a pass. B24's test (`tests/test_t08_b24_ptc_job.py`) was written at T08 close.
