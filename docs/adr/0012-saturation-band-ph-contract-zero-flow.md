# ADR 0012 — T05b: the saturation band, a PH-closure phase contract with a zero-flow regime, and temperature-degenerate streams

**Status:** Accepted 2026-09-25 — T05b's manifest `evidence/T05b/ba9a27b422834138daeff98481072c65db8b3744/manifest.json` is `tested` (64 of 64: B00–B36 and X00–X26; the cross-platform items on CI run 36169942463, x86-64 and aarch64), after the design-lane review `docs/reviews/T05b-review.md` (full review, re-review of W9, reviews of W10 and W10 (6) (b); every must-fix closed) and the ruling rounds `docs/briefs/T05b-rulings.md`. Agent acceptance is numerical and procedural: `review.numerical` and `review.process_model` remain `pending`.  
**Amended 2026-09-25 (second design pass):** D12 (a zero-flow form for dormant non-lifted outlets — Frank's answer to spec §18 Q2), D4 (c)'s swapped-row test, D7's rulings on the build lane's W4 questions; D9 (2) reversed by D12. Spec §7.6–§7.10, B23–B30; register R-058.  
**Amended 2026-09-25 (F9 pass):** D7 gains a second substitution class (unresolved two-phase splits) and D9 (1) is closed, both by ADR 0013 (`docs/derivations/K04-F9-spec.md`).  
**Amended 2026-09-25 (ruling round, `docs/briefs/T05b-rulings.md` §4; the implementation review `docs/reviews/T05b-review.md` M1, S1, S2):** D4 (a) — an opening writes the closure's temperature to *every* product's temperature column, and the screen of a flagged PH-type trial decides its regime from the band's end enthalpies with a `τ_E` margin, asking the full closure only inside it (spec §6.2; exact wherever the closure answers `ok`); D4 (c) and D12 — every opening (attempt 0 and every restart) is brought to agree with exact dormancy by one fixed point over every lifted split's `ZERO_FLOW` membership, the items and the outlet resets, with a typed `ACTIVE_SET_CYCLING` (`opening_not_settled(<id>)`) if it does not settle, and the screen runs at an empty signature too (spec §7.4, §7.8 (ii)–(iii); R-065); D7 — a dormant exchanger side's terminal checks carry K04's reason `ZERO_FLOW`; D9 (1)'s band measured with no `FAILED` state (W0.7); and, for the near-pure restarts this ADR's directive covers, K03 §5.3 releases an absent component's structural zeros before declaring `BOUND_BLOCKED` (R-064). Acceptance gains B31–B33. Registered records that move: the `t05b` key's SC-3 and DZ-12 entries (both products' temperatures at their restart openings), re-registered with that reason.  
**Amended 2026-10-09 (M02 WO-8 rulings, `docs/design/M02-pymrm-adapter.md` §14.2 B12–B14, B16, B17; R-254–R-256, R-258):** `pr-c1-v1` splits under v2. Their kernel is the TP flash classified by M01 §7 rule 3 with τ_dew. A split may declare vapour-only components, whose liquid flows a TWO_PHASE attempt pins. They have no degenerate or unresolved routing. Non-lifted PR outlets are not screened. A PR block has a dormancy convention. See the Amendment section at the end. No SYN-001 registration, identity or registered value moves.  
**Date:** 2026-09-25  
**Author:** design lane (`specifier`); brief `docs/briefs/T05b-limitations.md` (`de64cc8`)  
**Directive:** Frank, 2026-09-25, answering T05 spec §19 Q11 and Q12: *"I want the software to have as little limitations as possible. So, yes: the PH solver should be able handle near-pure feeds, and EO solves can handle a single flowing component that is partly vaporised."* The build lane put T05 §4.7 (a) (a dormant PH-type outlet) in the same scope because its remedy is the same ADR 0005 change. **Design steer**, Frank, 2026-09-25: *"The important thing for me is robustness, if a method cannot solve a hard case and the solver then switches to another method this is also fine.."* — a primary method with a typed, recorded fallback chain is preferred to a single method that refuses a hard case; each switch is an event in the trace, deterministic, and never a relaxed check; the certificate stays independent (R-016). D10 states the chain.  
**Normative text:** `docs/derivations/T05b-limitations-spec.md` §4–§11; machine-readable expectations `benchmarks/t05b/reference_values.yaml` from `docs/derivations/scripts/t05b_reference.py`  
**Amends:** ADR 0005 D1 (a second rule-set literal), D2 (the lattice gains `ZERO_FLOW`; under v2 the signature gains items `[<U>.<port>, ZERO_FLOW]` after the signature units' regimes, D12), D3–D4 ("the kernel" of a PH-type split); ADR 0011 D1 (the PH kernel's acceptance and a second route); T05 spec §4.4, §4.7, §5.1, §15 A28–A30, §18, §19; T02 §6.2 (no start projection of a PH-type split under the new literal); T03 §8.2 (the `branch_found` arm for `V = L = 0`); T03 §4.10 (the branch word `dormant`); K04 §4.4 and §4.7 (the stored split of a temperature-degenerate stream; the regularity matrix of a zero-flow root, lifted or not; the exchanger's terminal checks at a dormant side); T05 §4.7 (a) (the non-lifted outlets of its table).  
**Reverses:** R-049 (the near-pure class a registered limitation), R-050 (both EO limitations) and, by D12, R-057 (2) (dormant non-lifted outlets a registered limitation). **Amends:** R-007, R-016 (4), R-029, R-053 (the swapped-row test).  
**Affected requirements:** V12 (the unit library's PH flash, valve and reactor now cover near-pure and single-component feeds and dormant outlets; by D12 the pump, the exchanger and the K02 mixer cover dormant outlets too); D09 and A01 (frozen attempts: a regime set that includes `ZERO_FLOW`); D11 and V15 (branch provenance of a dormant split); A08/A09 and blueprint §8.1 (what a certificate reads for a stream whose phase fractions its temperature does not determine); D20 and blueprint §8.3 (no registered identity moves; one new R0 literal value).  
**Affected packages:** T05 (its kernel, three models' limitations, A28–A30 retired); T03/ADR 0005 (the contract's second literal); K04 (the revision verifier table only; SYN-001's legacy set untouched); K05 (the identity document gains a `t05b` key); T06 (generators may now emit these states); T08 (real high-purity streams).

## Context

T05 registered three limitations, each measured:

1. **Near-pure PH (R-049).** The PH kernel bisects on temperature. For a feed whose flowing components are all traces but one, the two-phase band is 2.1e-11 K wide at a trace of 1e-12 mol/s, a few hundred doubles, while it carries the whole latent heat (60 000 W for 2 mol/s of B). The provider's Rachford–Rice, with its absolute tolerance of 1e-14, resolves the vapour fraction there only to about 2 %. No double of `T` meets a target inside the jump except by coincidence; every target but mid-jump was `ph_ill_conditioned` (|f| 2.6e-2 to 1.2e2 W).
2. **One flowing component on the EO path (R-050 (b)).** The EO rows are regular there (the reduced determinant is proportional to `V L ∂lnK/∂T Δh > 0`; the twin's scaled `rcond₁` at P3's and P4's roots is 5.5e-3 and 1.5e-2), but the region never reaches the state: ADR 0005's screen, closure conversions and T02 §6.2's start projection take a split's regime from the provider's TP flash, which says `LIQUID` at `T_sat` and `VAPOR` one ulp above. Measured: P3 `ACTIVE_SET_CYCLING`, P4 `BOUND_BLOCKED`. With the start seeded from the unit's own split and not re-projected, both converge at once and their certificates fail only on K04's fresh flash (`energy_balance` by exactly `β n Δh` = 2 016 W and 30 000 W; `independent_split` by `β n`), because `(n, T_sat, P)` does not determine a pure stream's enthalpy (*measured*, this pass).
3. **Dormant PH-type outlet (R-050 (a)).** At zero flow the lifted equilibrium rows vanish identically (three zero rows, rank 15 of 18) and the outlet temperature has no row; `UNVERIFIED` from the traversal start, and a typed failure from any start whose inlet label moves.

All three are one fact seen three ways: **a PH-type outlet is determined by `(n, H, P)`; its temperature is a poor coordinate** — undefined at zero flow, degenerate for one component, ill-conditioned near purity. The fixes put the vapour fraction and the enthalpy where the temperature was.

## Decision

### D1. One primitive: the saturation band

For a flowing `(n, P)` the **temperature form of Rachford–Rice**, `g(T; β) = Σ_{n_i>0} z_i (K_i(T) − 1)/(1 + β(K_i(T) − 1))`, is increasing in `T` for every `β ∈ [0, 1]`, so it defines `T(β)` by bisection; the band's ends are the bubble and dew temperatures `T_b = T(0)`, `T_d = T(1)`; the split at `β` is `v_i = n_i β K_i / D_i`, `l_i = n_i (1 − β)/D_i`, `D_i = 1 + β(K_i − 1)`, both nonnegative by construction; its enthalpy `H(β)` is strictly increasing (spec §4). It is built in the unit layer on the provider's `lnK` and `h` only; `thermo/syn001.py` is untouched. The verifier has its own implementation (R-016). For one flowing component `T(β) ≡ T_sat`, the band is a point, and the saturation route of T05 §4.4 is its closed form.

### D2. The PH kernel: acceptance on the closure's rows, and a band route (reverses R-049)

T05 §4.4 steps 1–4 and the saturation route are unchanged. **Step 5 accepts an answer iff it satisfies the PH closure's own rows at K04's registered tolerances** — every component's material row (`τ_flow`), every division-free equilibrium row `v_i L − K_i l_i V` (`9.3e-8 (mol/s)²`) and the energy row (`τ_E`), each evaluated by the kernel from the provider's `lnK` and `h` at the answer. When the temperature route's answer fails that test and at least two components flow, the kernel runs the **band route**: bisection on `β ∈ [0, 1]` of `H(β) − H*` (spec §5.2: sign oracle outside the domain, width floor `2⁻⁶⁰`, at most 64 evaluations of `H`, each `T(β)` at most 200), whose answer passes the same test. `ph_ill_conditioned` remains the code when no route's answer passes. `ok` now means: the returned state is a root of the closure's EO rows (T05 §4.3) within K04's tolerances, from a route that bracketed it; spec §5.3 states what that bounds. On every registered T05 case the temperature route's answer passes (to be measured, W0.2), so every registered output is bitwise unchanged.

### D3. PH-type and TP-type splits

A lifted split is **PH-type** when its unit's energy row fixes its temperature — `syn001.valve`, `syn001.ph_flash`, `syn001.conversion_reactor` with `energy_specification = duty` — and **TP-type** otherwise (`syn001.tp_heater`, `syn001.tp_flash`, the reactor with `outlet_temperature`). The split registry (R-046) declares it per model, by configuration for the reactor.

### D4. The phase contract `T05b-phase-contract-v2` (reverses R-050)

A second rule-set literal, as ADR 0005 D1 requires of a changed rule set. Under `"T05b-phase-contract-v2"`, and only under it:

- **(a) The kernel of a PH-type split is its PH closure.** Wherever ADR 0005 D3–D4 or T02 §6.3 asks "the kernel" for a regime or a split — a flagged trial, a closure conversion, a restart opening — a PH-type split is answered by `ph_state(n_feed, P, H_split)`, where `H_split` is the split's own enthalpy at that state; the opening takes the answer's split **and temperature**. TP-type splits keep the provider's TP flash. On SYN-001 a liquid-form trial inside the domain always has less enthalpy than any vapour-form state (`max h^L < min h^V`, generator-checked), so a PH-type unit leaving a single phase is always reported in the adjacent `TWO_PHASE`: the far restart that cycled P3 cannot occur (spec §6.3).
- **(b) A PH-type split is not re-projected at the start.** T02 §6.2's projection applies to TP-type splits only; a PH-type split opens with the split its unit's causal closure produced (D5), in the regime of its branch.
- **(c) `ZERO_FLOW` is a regime of every lifted split.** Selected exactly when the split's feed flows are all `+0.0` (ADR 0001 D3.1). It pins every lifted flow of the split at `+0.0`; drops its equilibrium rows, its split rows (`<U>:split:<c>`, or the mole rows of a products-style split) and its total definitions; and, for a PH-type split, replaces the unit's energy row by the **label row** `<U>:zero-flow-label`: `T_out − T_label = 0` (kind temperature; `T_label` the unit's inlet temperature, T05 §4.7 (a)'s label). The label row is a row of the attempt's system and of the verifier's zero-flow form, never of the compiled declaration, so no `model_version` moves. The lattice becomes `LIQUID — TWO_PHASE — VAPOR` with `ZERO_FLOW` adjacent to each. The screen checks, for every lifted split at every trial, that exact dormancy of its feed agrees with `ZERO_FLOW`; a disagreement is a phase-rejected trial (ADR 0005 D3's mechanism). A split leaving `ZERO_FLOW` takes the TP kernel's regime and split at its feed's `(n, T, P)` (the zero-flow state carries no enthalpy). Closure: a `ZERO_FLOW` branch is admissible iff its feed is exactly dormant; *(second pass)* then every row a zero-flow form swapped out must hold at the final state (K03 §5.2's per-row test), else the region closes `SPECIFICATION_CONFLICT` with `zero_flow_conflict(<row id>)` — the PH flash's and the duty-mode reactor's energy rows equal `Q_spec` at dormancy, and without the test a nonzero `Q_spec` converged the zero-flow form to a state that violates a declared row (spec §7.8, finding F6).
- **(d) `"T03-phase-contract-v1"` is kept verbatim.** Every registered policy names v1 and runs exactly the rules it ran; the new cases name v2. On C1–C3 the two literals give identical runs (spec B07; *measured* this pass: C1–C3 consult the kernel only at T02 §6.2, where the start already equals the kernel's split bit for bit).

Schema: `solve-policy.phase_contract` widens from `const "T03-phase-contract-v1"` to `enum ["T03-phase-contract-v1", "T05b-phase-contract-v2"]` — **a frozen-schema change** (interfaces-frozen §2).

### D5. The traversal start seeds a PH-type split from its unit's closure

`initial_state` sets a heater-style PH-type split from the split its unit's causal closure returned, as its own docstring states ("re-split … by the same kernel the unit used"), instead of re-flashing the outlet by TP. On the bracket route the two are the same function of the same inputs, so every registered start is bitwise unchanged; on the saturation and band routes the TP re-flash lost the vapour fraction. The initializer id `traversal-G0-v1` does not change: this is the implementation meeting its stated behaviour.

### D6. `branch_found` reports `ZERO_FLOW` for a split with `V = L = 0` (amends R-029)

K03 §8.2's arms become `V = L = 0` → `ZERO_FLOW`, `V = 0 < L` → `LIQUID`, `L = 0 < V` → `VAPOR`, else `TWO_PHASE`. The fingerprint describes the state (R-029's own principle), and a dormant split's state is dormancy. The `solution-certificate` schema already admits `ZERO_FLOW` in `branch_found`; the fingerprint literal `T03-root-fingerprint-v1` is unchanged because no registered fingerprint carries a split with `V = L = 0` (W0.4 proves it on every committed record). *(Second pass, W0.4 measured: no fixture, benchmark reference or identity key has one; T05's evidence manifest at `91ac010` records four in retired A28's measured value, which stays as it was and is compared by nothing — spec §8, §16.)* A pre-T05b record of a dormant split (T05 A28's test runs only) compares `DISTINCT` with a new one; stated, not hidden.

### D7. The verifier: temperature-degenerate streams and zero-flow roots (amends R-016 (4) narrowly)

- **Temperature-degenerate.** A flowing split (its feed at the split's `T`, `P`) or a flowing stream is temperature-degenerate iff its bubble and dew temperatures both lie in the domain and within `τ_T = 1e-6 K` of its temperature. Its phase fractions are then not a function of its `(n, T, P)` at the registered temperature resolution, and **the fresh flash cannot recompute what the state carries**. For such a split the verifier takes each of its streams' enthalpy from the stored split (heater style: `Σ v_i h_i^V + Σ l_i h_i^L`; products: each product in its assigned phase), replaces the branch's admissibility check by `phase_admissibility.<U>.<S>.saturation` (the degeneracy distance, against `τ_T`), and reports `independent_split.<U>.<S>` `not_applicable` with reason `temperature_degenerate`. A degenerate stream outside any split is evaluated in its single declared phase (`unsupported`, reason `temperature_degenerate_unlifted(<S>)`, if it has none — unreachable after the T05 S1 ruling). Every energy check that reads such an enthalpy says so in its `independence_qualification`. Everywhere else — every registered state, by at least 17.5 K (generator-checked) — K04 §4.4 and §4.7 are unchanged.
- **Zero-flow roots.** At a root with a `ZERO_FLOW` branch, the regularity matrix is the zero-flow form of D4 (c) (with the label row), and `residual.<U>:zero-flow-label` is checked at `τ_T`. The branch's admissibility and independent split stay `not_applicable` (`ZERO_FLOW`), as today.
- *(Second pass, answering W4.)* A degenerate stream outside any split carries the qualification `enthalpy of <S> in its declared phase <PHASE>: temperature-degenerate (ADR 0012 D7)`. The zero-flow reduction of a lifted split needs its feed exactly dormant as well as `V = L = 0`; a split with a flowing feed and `V = L = 0` is judged as a flowing split (and fails its split rows). INJ-B1 fails exactly the compiled `VLV-energy` row and the two energy balances, 2 016 W each. At a root with a dormant non-lifted outlet (D12) the regularity matrix reduces it too and `residual.<U>:zero-flow-label[:<side>]` is checked; at a dormant exchanger side the terminal-difference checks are `not_applicable` (reason `zero_flow` — *ruled 2026-09-25: `ZERO_FLOW`, K04's existing reason*), `Q ≥ 0` still judged.
- No check category, quantity kind, tolerance or required-check entry is added, so `check_policy_sha256` does not move. SYN-001's legacy check set is untouched; the revision table's K02 entries stay bitwise paired with it (W1.d).

### D8. R-007 admits a temperature-degenerate stream in either single phase (amends R-007)

In `single_phase_admissible` (unit layer), a stream refused by R-007's enthalpy gap is admitted when it is temperature-degenerate, and the reported gap is its degeneracy distance. The verifier's declared-port check keeps its form and reads D7's enthalpy map, which already carries a degenerate stream's assigned or declared phase. The refusal path is the only one that changes, so every admitted registered state is bitwise unchanged, and every registered refusal (five T05 cases, SYN-001's 347.45 K state) is non-degenerate by at least 14 K and stays refused (generator-checked). The causal side cannot tell which phase a degenerate stream was assigned upstream, so it admits both; the certificate decides (spec §11).

### D9. What stays a limitation, stated minimally

1. *(Closed 2026-09-25 by ADR 0013 — the verifier's projection, the admissible phase reading and the unresolved-split routing; R-057 (1) reversed.)* **Near-pure EO certification in F9's band.** Between the degeneracy window and the fresh flash's own resolution — for 2 mol/s of B at `P_r`, traces of roughly `5e-8` to `4e-7` mol/s (twin emulation; W0.7 measures the implementation) — the fresh flash is used and misses by up to a few `τ` (*emulated*: 4.2 `τ_E`, 2.2 `τ_flow` at NP-G). The solve converges and the state is right; the certificate may be `FAILED` by T04 F9's mechanism. It closes with T04 Q8's K04 follow-up, which is out of T05b's scope (brief §8).
2. **Dormant non-lifted energy-determined outlets** — *no longer a limitation; reversed by D12 (second pass)*: covered, without touching `signature_units`. What remains: a model outside SYN-001's library with such an outlet and no registered form (typed `RANK_DEFICIENT`, `UNVERIFIED`); a `SPECIFICATION_CONFLICT` is not searched past (spec §17).
3. **The traversal reads a lifted degenerate inlet by `(n, T, P)`** (T05 §5.2 (3)). A downstream unit's start then misplaces that stream's latent heat; the EO solve corrects it (SC-3 is registered on exactly that start). A start, not a result.

### D10. Robustness: the fallback chain, its triggers and its records

Every switch below is a deterministic function of the state and the declaration, is recorded in the solve's trace (or, for the verifier, in the certificate's R0 check list), carries no measured float in its R0 string, and never loosens a tolerance.

| Level | Primary | Fallback, in order | Trigger | Recorded as |
| --- | --- | --- | --- | --- |
| Causal PH closure (D2) | saturation route when exactly one component flows (structural, not a switch); temperature route otherwise | band route; then the typed failure `ph_ill_conditioned` / `ph_not_converged` | the temperature route's answer fails the closure-rows acceptance and ≥ 2 components flow | `PHState.route`, carried on the unit's evaluation; when the traversal start of a region used it: an `initializer_candidate` event `closure_route(<unit>, band)` followed by `initializer_accepted` (T02 §6.2's pair, existing kinds) |
| Kernel of a PH-type split at a contract decision (D4 (a), v2) | the PH closure at the split's own enthalpy | the provider's TP flash; then the existing refusal handling (invalid trial, or `EVALUATION_ERROR`) | the PH closure returns a typed failure; or the split leaves `ZERO_FLOW` (no enthalpy to classify) | on the `attempt_opened` it determines: `phase_update(<cause>; fallback(<unit>, tp)[, …])`; `fallback(<unit>, ph-band)` when the PH closure answered through its band route |
| Region (T04 edge 3, unchanged) | the contract's attempts | the homotopy recovery from the failed solve's start, once; then the typed outcome | `EO_RECOVERY_TRIGGERS` (`ACTIVE_SET_CYCLING`, `ATTEMPTS_EXHAUSTED`, …) | `region_closed.eo_recovery = taken` or `unsupported` (existing) |
| Verifier (D7) — a substitution of what is evaluated, not a solver fallback | the fresh flash of `(n, T, P)` | the stored split's judgement | the exact degeneracy test | the check ids `phase_admissibility.<U>.<S>.saturation`, `independent_split.<U>.<S>` `not_applicable` (`temperature_degenerate`), the energy checks' qualification |
| Form of a dormancy-form outlet (D12, v2) — a form selection | the declared form while its trigger streams flow | the zero-flow form; then, if the swapped row fails at closure, `SPECIFICATION_CONFLICT` | exact dormancy of the trigger streams; the closure's swapped-row test | the signature item `[<U>.<port>, ZERO_FLOW]`; `phase_wall(…, <U>.<port>:<from>-><to>)` when the screen reports it; `zero_flow_conflict(<row id>)` |

The verifier's substitution is not a relaxation: the check it replaces measures a quantity `(n, T, P)` does not determine, and what replaces it detects both failure modes that check existed for, at the same registered tolerances (INJ-B1: a wrong vapour fraction fails the energy balance by 2 016 W; INJ-B2: a temperature 2e-6 K off saturation leaves the window and fails the fresh flash by `10³ τ`). A verifier fallback that loosened a tolerance — the only way to close D9 (1) inside T05b — is excluded by the steer itself; that band stays T04 Q8's.

### D11. Identity

Every registered result stays as registered: SYN-001 bit-identical (identity document minus `t05` and `t05b`: `b364bb3d…`, structural `4ce030ca…`, policy `21c44e10…`); T02–T04 fixtures; T05's unit cases, C1–C3X and the `t05` identity (`ddbd0f71…`) — *also after D12*, which adds no signature item at any registered state (spec §7.9, B30); K04's `check_policy_sha256`; T05's reference file (`af4a543f…`). T05 A28–A30 are retired and replaced (spec §16). The K05 identity document gains a `t05b` key.

### D12. Dormant non-lifted outlets: a zero-flow form carried by signature items (second pass; reverses R-057 (2))

Frank, 2026-09-25, answering spec §18 Q2: *include* the dormant pump, exchanger and K02 mixer outlets in T05b, accepting a re-registration of C1–C3's `t05` identity with its reason recorded; SYN-001's identity must not move.

- **Which.** A registry keyed by model id (the exchanger's also by its `specification`) declares each **dormancy-form outlet** — an outlet of a unit with no lifted split whose temperature no declared row reads at dormancy: the pump's `outlet`; the K02 mixer's `outlet` (every inlet dormant); an exchanger side's outlet unless the specification is that side's outlet temperature (then `HX-spec` reads it and it needs nothing). For each: its trigger port, swapped row (`PUMP-energy`, `MIX-energy`, `HX-energy-hot|cold`), label row `<U>:zero-flow-label[:hot|cold]` = `T_out − T_label` with the causal evaluator's label (the inlet's temperature; the mixer's first inlet in connection order). Every other dormant outlet temperature of SYN-001's library has a row or is a lifted PH-type split's (generator-checked coverage).
- **The form.** Selected exactly when every stream of the trigger port is exactly dormant (no threshold): the swapped row leaves, the label row enters, nothing is pinned; square and regular (the swapped row's gradient lies in the span of the retained rows at dormancy; generator-checked, one rank per form). The label row is never compiled (D4 (c)'s rule): no `model_version`, T01 report, plan or `signature_units` moves; the K02 mixer's rows are untouched (R-038).
- **How an attempt carries it.** Not as a regime of a signature unit and not as a regime-free per-call switch: the attempt signature (ADR 0005 D2's list) is followed by one item `[<U>.<port>, ZERO_FLOW]` per active form, in declaration order. The regime machinery applies to the items unchanged — adjacency (absent ↔ present), the cycle rule, the budget, the screen (dormancy agreement per trial), the closure (agreement both ways, branch words `zero_flow` and `dormant`, then D4 (c)'s swapped-row test), `active_phases`, `branch_provenance`, `jacobian_pattern`. Items are recomputed at every opening after its lifted splits are set, and an outlet whose item changes has its flows set to its mole balance (exactly zero on entering; on leaving the reset keeps the first Jacobian regular — generator-checked).
- **Under v1** nothing changes in the solver; the verifier's reduction is chosen from the state (D7), so a v1 root at a dormant non-lifted outlet can be `VERIFIED`.
- **Identity.** No registered state has an active form (generator-checked at C1, C2, C3, C3X, SC-4; W0.10 on every committed record), so no registered identity moves and the re-registration Frank accepted is not used.
- **Frozen interfaces.** No schema changes: a signature item is a `[string, regime]` pair every schema already validates. The documented meaning of the pair's first element ("unit id") widens to `<U>.<port>` under the v2 literal; this ADR records it, `docs/interfaces-frozen.md` §2's T05b paragraph states it when W7b lands, and the schema `description` strings are not edited (spec §18 Q7: the default, open to Frank's reading of the freeze).

## Alternatives considered

- **The band route as the only two-phase route.** Rejected: it changes the last bits of every registered two-phase causal answer and, through the starts, can change C1–C3's iteration records (`t05` identity) for no accuracy gain on wide mixtures.
- **A conditioning criterion, or routing "effectively pure" feeds by a trace threshold.** Rejected again (R-049): the first refuses correct answers on an uncalibrated threshold; the second quantizes the state on the exact path.
- **Energy-only acceptance, as T05.** Rejected: it trusts the provider's flash beyond what the kernel verifies. The BIASED double (a flash whose vapour fraction is 1e-5 off) meets energy at a temperature 2.2e-4 K wrong; the equilibrium rows refuse it by 84 × `τ_eq` (*twin*).
- **A TP classification with a tolerance band around `T_sat`.** Rejected: it helps only one component, needs a threshold, and still reports `VAPOR` from a liquid-form trial of a narrow multi-component band. The PH classification is exact and predicts the root's regime.
- **Keeping the TP kernel and only seeding the start.** Rejected: it works only when the start is already in the root's regime; SC-3 opens `LIQUID` and needs the adjacent restart.
- **Amending `T03-phase-contract-v1` in place.** Rejected: ADR 0005 D1 promises that a changed rule set is a new value, and a replay under a policy that never declared the new rules must be refused, not run.
- **The stored split's enthalpy for every PH-type or every two-phase split.** Rejected: it reverses R-016 (4) broadly and loses INJ-T1's registered fresh-flash energy failure.
- **Falling back to the stored split whenever the fresh flash disagrees.** Rejected: at wide mixtures it resolves T04 F9 as a side effect, which is out of scope and a K04 decision.
- **A wider degeneracy window.** Rejected: no registered tolerance gives one; `τ_T` is the resolution a temperature is registered at.
- **A compiled label row.** Rejected: it adds a row to every flowsheet with a PH-type unit (`model_version`, C1/C3 identity) and makes T01 see a non-square declaration.
- **Holding the dormant temperature at its opening value.** Rejected: the label goes stale when the inlet label moves (DZ-3).
- **Bumping the fingerprint literal.** Rejected: it moves the R0 identity of every certificate, SYN-001's included.
- **A zero-flow regime for non-lifted units now.** Deferred (D9 (2)): it changes the signature units and identity of C1–C3. *Superseded by D12 on Frank's answer;* the alternatives D12 rejected:
- **Making the non-lifted units signature units** (always present, with their declared phase while flowing). Rejected: it changes the plan and every attempt signature of every flowsheet containing a pump, exchanger or K02 mixer — C1–C3's `t05` key and every T02–T04 key through the K02 mixers of their revision-built SYN-001 flowsheets — for no information a flowing unit's absent item does not already give; and an exchanger has two outlets under one unit id.
- **A regime-free switch, evaluated per residual call from the state.** Rejected: an attempt's equations would change inside the attempt, breaking ADR 0005 D2 (frozen attempts), the residual/Jacobian pairing identity (it includes the phase signature, `interfaces-frozen.md` §1) and the cycle rule (two different systems under one signature).
- **Keying items by the dormant stream id, or by bare unit id.** Rejected: a stream id is a different namespace from the pair's documented unit id, and a bare unit id cannot tell an exchanger's hot-only form from its both-sides form (a false `ACTIVE_SET_CYCLING` on the second).
- **Letting the certificate catch a zero-flow conflict.** Rejected: the region would report `CONVERGED` on a state that violates a declared row by the full duty (a false success, CLAUDE.md's first rule); the verifier still catches it independently (INJ-B4).
- **Judging a dormant exchanger side's terminal differences.** Rejected: its temperature is a label, not a point of a profile; DZ-7's label 290 K would fail a correct dormant root by 10 K.

## Consequences

- C1. **Frozen-schema change:** `schemas/solve-policy.schema.json` `phase_contract` → `enum` of the two literals; `SolvePolicy.phase_contract: Literal[v1, v2]`, default v1. `docs/interfaces-frozen.md` §2 and `schemas/README.md` list it under T05b with this ADR's number when the schema lands (done at W5). No other schema changes (`ZERO_FLOW` is already in every phase enum; `SPECIFICATION_CONFLICT` is an existing outcome). *(D12.)* One documented meaning widens with no validation change: a signature pair's first element may be `<U>.<port>` (spec §18 Q7).
- C2. **Retired:** T05 A28, A29, A30 and their tests, replaced by B15, B01 and B08–B09 respectively (spec §16). T05's evidence generator marks them `retired by ADR 0012` rather than re-measuring them.
- C3. **Manifests:** the `validity.limitations` of `syn001.ph_flash`, `syn001.valve` and `syn001.conversion_reactor` drop the near-pure and single-component EO statements and the dormant statement; *(D12)* `syn001.liquid_pump` and `syn001.heat_exchanger` drop their dormant-inlet EO statement; the K02 mixer's manifest has none and stays byte-identical.
- C4. **Register:** R-052 to R-058; R-049, R-050 and R-057 (2) marked reversed; R-007, R-016, R-029, R-053 carry an amendment line.
- C5. **Handed on:** T04 Q8 (F9) now also gates near-pure EO certification in D9 (1)'s band (scheduled by Frank right after T05b). *(D12)* Whether T04's edge 3 should take `SPECIFICATION_CONFLICT` as a trigger (a T04 question; not proposed).

## Migration

One schema widens (C1): every existing `SolvePolicy` document stays valid and means what it meant; a v2 policy is refused by code that predates it, as D1 of ADR 0005 intends. **The build lane reports C1 to Frank before implementing it (brief §4); every other chunk of the work order is independent of it and proceeds first.** No stored document changes meaning except a dormant split's `branch_found` (D6), which no registered record contains (T05's retired A28 evidence excepted, spec §8). D12 changes no stored document: no registered state has an active form (W0.10). Retired assertions are replaced, not re-pinned.

## Acceptance evidence

- `evidence/T05b/<commit>/manifest.json` `tested`: B00–B30 of the specification *(and B31–B33, ruling round 2026-09-25)*, in particular B01 (near-pure grid), B02 (registered kernel outputs bitwise), B07 (v2 ≡ v1 on C1–C3), B08–B11 (single component), B12–B13 (near-pure EO and the residual limitation's evidence), B15–B17 (dormant), B18 (injections), B19 (R-007), B20 (every switch recorded), B21 (bit identity); *(D12)* B23–B27 (dormant non-lifted outlets), B28–B29 (zero-flow conflicts and their injections), B30 (the amendment inert on every registered result).
- `t05b_reference.py --check` passes and the committed reference file's SHA-256 matches the specification's header; `t05_reference.py --check` still passes with T05's file unchanged.
- The gate green on x86-64 and aarch64 with the K05 identity comparison including `t05b`, every other key unchanged.

---

## Amendment (2026-10-09, M02 WO-8): `pr-c1-v1` splits under `T05b-phase-contract-v2`

**Author:** design lane (`architect`), M02. **Normative text:** `docs/design/M02-pymrm-adapter.md` §14.2 B11–B17,
and M01 spec §7 with its Amendment 3. **Register:** R-254 to R-256, R-258.

### Context

M02's Peng–Robinson flash (`c1.tp_flash`) is the first lifted split on a provider whose liquid is a pure component
(R-143). There, SYN-001's machinery fails in four places. Dropped equilibrium rows must hold on the branch that
drops them, which M01 §7's first row did not. The liquid's light-gas flows are columns, since `assemble` allocates
every flow of every stream. The admissibility check reads `lnK`, which `pr-c1-v1` lacks. And the saturation band has
no lower end.

### Decision

- **A1 (D4 (a), "the kernel", for a TP-type `pr-c1-v1` split).** The kernel is the provider's TP flash, classified by
  M01 §7 rule 3: TWO_PHASE with `l_NH₃ ≤ τ_dew n_tot` (τ_dew = 1e-10, R-230) is VAPOR, with the split pinned as a
  VAPOR restart pins it. ADR 0005 D3's screen and the closure conversions read the same classification, not K03
  §8.2's `Σ y/K` at `admissibility_epsilon`. The region dispatches on the provider id, and every other provider runs
  the unchanged rules.
- **A2 (D4, attempt construction).** A split rule may declare `vapour_only` components. In a TWO_PHASE attempt, their
  liquid flows are pinned at `+0.0` and their zero rows `n_L,i = 0` (equilibrium-family rows) are dropped; this
  realizes M01 §7 rule 2's "not variables". VAPOR and ZERO_FLOW already pin them, and LIQUID leaves them to the mole
  rows. The form, `VapourOnlyForm`, sits beside the split's descriptor, as `ZeroFlowForm` does, so `LiftedSplit`'s
  registered digest does not move.
- **A3 (D7).** A `pr-c1-v1` stream that carries light gas is never temperature-degenerate, because its band is
  half-open (M01 §7 rule 4). It is never unresolved in ADR 0013 D3's sense either, since `w = ∞` makes the floor 0.
  Its routing is therefore empty.
- **A4 (D12).** The dormancy-form registry gains `c1.adiabatic_mixer`'s outlet, whose declared phase is VAPOR.
- **A5 (scope).** PR outlets that are not lifted (the mixer's, the heater's) are not screened during a solve. Their
  units' causal evaluates refuse them, and the certificate's declared-port check judges them at the solution, as
  SYN-001's declared-liquid outlets are judged. No outcome is added.
- **A6 (residual and Jacobian at dormancy).** At exact dormancy a PR vapour block takes the ideal-gas limit
  (`∂Ḣ/∂n_j = h^ig_j(T)`, `ln φ = 0`). A pure-NH₃ liquid block takes the provider at a unit probe, falling back to
  the pure fluid's vapour root where no liquid root exists. This is a registered convention at a point where no
  derivative exists.

### Alternatives rejected

- A `pr-c1-v1` admissibility in SolvePolicy: a frozen-schema change for a property of the provider's convention.
- Leaving the light-gas liquid columns free under their zero rows: roundoff makes them nonzero, which reaches the
  liquid blocks and defeats ADR 0013's exact-zero projection.
- A solve outcome for an inadmissible non-lifted outlet: a frozen-schema change, while the certificate already types
  the failure.

### Consequences

- No schema, literal, policy hash or SYN-001 record changes.
- The region gains a provider-id dispatch in `_kernel` and `_admissible` and a TWO_PHASE term in `_pinned` and
  `_dropped`. Each is a branch that SYN-001's provider and rules never take; M02's G2 proves it.

### Acceptance evidence

M02 gates G2 and G7 as amended by the design note's §14.2, recorded in `evidence/M02/<commit>/manifest.json`.
