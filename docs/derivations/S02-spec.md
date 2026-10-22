# S02 — MESH column on SYN-001: conventions, specification sets, refusals, cases and test specification

Design lane (`specifier`), 2026-10-22. Package S02 (plan v1.2 §4.5, `docs/implementation-plan.md:282`; X31 `:357`), brief
`docs/briefs/S02-specification.md`. Base: S01 (`docs/derivations/S01-spec.md` with Amendment 1, §17). Reference generator
`docs/derivations/scripts/s02_reference.py` (mpmath, 50 digits; `--check` re-derives 906 claims and byte-compares
`s02_reference.json`; about 3 minutes). Decisions: `docs/S02_DECISIONS.md`, register R-530 to R-535.

## 0. Authority and scope

Normative for S02. It composes with everything S01 composes with (ADR 0001, 0005, 0008 D3, 0010 D2–D3, 0012 D1–D4, 0018)
and with S01 itself, and reopens none of them. It changes no frozen interface (`docs/interfaces-frozen.md`): the new rows are
additive row builders, the new column `φ` is of an existing kind (`dimensionless`), no row of a new kind is added (so
`region.KIND_TOLERANCE` is unchanged), the phase contract and `solve_region` are called unchanged, and S01's registered policy
`s01-default-v1` is reused (no new v2 policy, so T05b §6.6 gains no further exemption). **No ADR is needed** (DECISION 8).
Provider: SYN-001 only. PR routes are vapour-only (ADR 0026, ADR 0043 Proposed) and cannot form a stage.

**What it establishes.** Column conventions (§1); the rows S02 adds to S01's cascade (§2); the DOF and the admissible
specification sets (§3); which phase signatures a cascade can hold at a regular root, with the structural singularity that
excludes the others (§4); typed refusals (§5); the initializer (§6) and solve path (§7); acceptance (§8); four matched column
cases, one phase case and the spec-set equivalences (§9); assertions S02.A01–A16 (§10); work orders (§12); the manifest check
list (§13).

**What it does not establish** is §14. Read it before citing anything here.

## 1. Conventions (normative)

1. **Stage numbering.** Stages `j = 1..N`, top to bottom, as S01. `N` **counts the condenser and the reboiler** when present
   (the RadFrac convention): the condenser is stage 1, the reboiler stage N. Liquid flows j → j+1, vapour j+1 → j.
2. **Condenser kinds** (`condenser ∈ {none, partial, total}`):
   - `none`: stage 1 is an ordinary S01 stage and the column has a `top` inlet (an absorber or stripper top).
   - `partial`: stage 1 is an S01 equilibrium stage with no `top` inlet. Its vapour `v_1` is the **vapour distillate**; all
     its liquid `l_1` returns to stage 2 as reflux. There is no liquid distillate from a partial condenser.
   - `total`: stage 1 is **not** an equilibrium stage. It condenses `v_2` completely to **saturated liquid at its bubble
     point** at `P_1`, and splits it into reflux `r` (to stage 2) and liquid distillate `d` of the same composition (§2.2).
     Subcooling is not offered (`unsupported(condenser:subcooled)` is not a kind; see Q-S02-1).
3. **Reboiler kinds** (`reboiler ∈ {none, partial}`): `none` — stage N is ordinary and the column has a `bottom` inlet;
   `partial` — stage N is an S01 equilibrium stage (kettle) with no `bottom` inlet, its liquid `l_N` is the bottoms product
   and its vapour `v_N` is the boil-up. A total reboiler (thermosiphon with a vapour product) is `unsupported`.
4. **Feeds.** Side feeds are S01 side feeds: declared single-phase (`LIQUID`/`VAPOR`), one per stage, at a stage that is
   neither the condenser nor the reboiler (§5 S7). Enthalpy at the feed's own `(T, P)` (S01 DECISION 8).
5. **Pressure profile.** One `P_j*` per stage including the condenser, pinned by S01's `P_j − P_j*` rows. It must be
   non-decreasing downward, `P_{j+1}* ≥ P_j*` (vapour flows up; §5 S9). No hydraulics, no pressure-drop correlation.
6. **Signs and units.** SI; `Q_j > 0` into stage j (ADR 0001 D4.1). A condenser duty is negative, a reboiler duty positive.
7. **Products.** `distillate`: `v_1` (vapour) for `partial` or `none`, `d` (liquid at `T_c, P_1`) for `total`. `bottoms`:
   `l_N` (liquid). These are the outlet ports; S01's `top_vapour`/`bottom_liquid` keep their meaning for `none` ends.

## 2. Rows S02 adds (normative)

### 2.1 The specification slot

Every stage of S01 carries one **slot row**, `Q_j − Q_j*`. S02 keeps that at every stage except the condenser and the reboiler,
whose slot row is the column specification. Q_j is then a free column fixed by the energy row. The forms (all division-free):

| End | Specification | Slot row | Kind | Form |
| --- | --- | --- | --- | --- |
| condenser (partial) | `reflux_ratio` RR* > 0 | `L_1 − RR*·V_1` | molar_flow | ratio (not `variable − parameter`) |
| condenser (partial) | `distillate_rate` D* | `V_1 − D*` | molar_flow | `variable − parameter` |
| condenser (any) | `duty` Q_c* < 0 | `Q_1 − Q_c*` | heat_rate | `variable − parameter` |
| condenser (total) | `reflux_ratio` | `Σ_i r_i − RR*·D` | molar_flow | ratio |
| condenser (total) | `distillate_rate` | `D − D*` | molar_flow | `variable − parameter` |
| reboiler (partial) | `boilup_ratio` BR* > 0 | `V_N − BR*·L_N` | molar_flow | ratio |
| reboiler (partial) | `bottoms_rate` B* | `L_N − B*` | molar_flow | `variable − parameter` |
| reboiler (partial) | `duty` Q_r* > 0 | `Q_N − Q_r*` | heat_rate | `variable − parameter` |

The parameters (RR*, BR*, D*, B*, Q*) are pinned inputs (ADR 0008 D1.3), never literals. Ids:
`<U>:stage:<j>:spec:<kind>`; S01's ids are unchanged.

### 2.2 The total-condenser block (stage 1 when `condenser = total`)

Columns (2C + 5): `r_i`, `d_i` (molar_flow), `φ` (dimensionless), `D` (molar_flow), `T_c`, `P_c`, `Q_c`. Rows (2C + 5):

| Row | Expression | Kind |
| --- | --- | --- |
| `bal_i` | `v_i2 − r_i − d_i` | molar_flow |
| `split_i` | `r_i − φ·v_i2` | molar_flow |
| `Ddef` | `D − Σ_i d_i` | molar_flow |
| `bubble` | `Σ_i K_i(T_c, P_c)·v_i2 − V_2` | molar_flow |
| `energy` | `Q_c + Ḣ^V(v_2, T_2) − Ḣ^L(r, T_c, P_c) − Ḣ^L(d, T_c, P_c)` | heat_rate |
| `P` | `P_c − P_1*` | pressure |
| slot | §2.1 | — |

Stage 2's liquid inflow is `r` at `(T_c, P_c)` in place of `l_1`. `bubble` is division-free; it is degenerate when `V_2 = 0`
(every `T_c` satisfies it), which is why §8 requires `V_2 > 0`. `φ` has FD column scale 1.

### 2.3 Absent inlets

A column with a condenser has no `top` inlet; one with a reboiler has no `bottom` inlet. **Absent** means no inlet columns and
rows, not a dormant inlet (`ref.dof` counts only present inlets). S01's ZERO_FLOW label `T_label(1) = T_top` (S01 §4.3) becomes
`T_1⁰` (§6's profile value, a constant) when there is no `top` inlet; a label of `T_2` would make a cycle with stage 2's label.

## 3. DOF and admissible specification sets

**Count.** Columns = rows = `14·n_eq + (C + 2)·n_in + (2C + 5)·[total]`, where `n_eq` is the number of equilibrium stages
(N, or N − 1 with a total condenser) and `n_in` the number of present inlets (generator `ref.dof`: M1 103, M2 100, M3 75,
M4 75). After fixing every inlet's `nTP`, every `P_j*` and every intermediate `Q_j*`, the column has
`[condenser ≠ none] + [reboiler ≠ none]` degrees of freedom, one per end, taken by the slot rows of §2.1.

**Admissible sets.** One specification per non-`none` end, from §2.1's table, with one exclusion:

- `(distillate_rate, bottoms_rate)` is **structurally redundant**. Summing every component balance gives
  `Σ_inlets F − D − B = 0` at every state satisfying the rows, so `V_1 − D*` (or `D − D*`) and `L_N − B*` are linearly
  dependent with the rest: inconsistent if `D* + B* ≠ F`, rank-deficient if equal. The generator shows it at M1's and M2's
  roots with `D* + B* = F` exactly: `σ_min = 2.2e-41` and `9.1e-42` (scaled Jacobian, 40 digits), against `σ_min ≥ 2.4e-3` for
  every other set registered there (`ref.variants`). It is refused (§5 S3), never solved.
- Every other pair is admissible. Each registered pair is regular at its registered root (`ref.variants`, claims). No claim is
  made for unregistered pairs at other states.

**Not offered** (`unsupported(specification:<kind>)`): stage temperature, product purity or mole fraction, component recovery,
reflux or boil-up *rate*, distillate-to-feed ratio. They are inverse specifications whose admissibility depends on the state;
they belong to a later package (Q-S02-2).

## 4. Phases

### 4.1 Per-stage handling

Unchanged from S01 §4: each equilibrium stage is one PH-type `LiftedSplit` with regimes `TWO_PHASE`, `LIQUID`, `VAPOR`,
`ZERO_FLOW`, contract `T05b-phase-contract-v2`, `solve_region` called unchanged. The total condenser is not a split and has
no regime.

### 4.2 End stages under a ratio or rate specification

A partial condenser under `reflux_ratio` that is `LIQUID` has `V_1 = 0`, so its slot row gives `L_1 = 0`; `VAPOR` gives
`L_1 = 0`, so `V_1 = 0`. Either way the stage carries no flow, which is partial dormancy (not claimed, S01 §14). Under
`distillate_rate`, a `VAPOR` condenser has `T_1` in no row but `energy_1`, which also holds the free `Q_1`: the Jacobian is
singular. The reboiler is symmetric. **Hence a regular root has every partial end stage under a ratio or rate specification
`TWO_PHASE`** (§8 item 2). Under a duty specification an end stage may be single-phase.

### 4.3 Singular adjacent pairs (derivation; generator claims)

Take stages j (above) and j+1. Suppose stage j emits no vapour (`LIQUID`) and stage j+1 emits vapour (`TWO_PHASE` or
`VAPOR`). Add a circulation `δ` with composition `c = v_{j+1}/V_{j+1}` to both `l_j` and `v_{j+1}`, and shift `T_j` by
`(Σ c_i h_i^V(T_{j+1}) − Σ c_i h_i^L(T_j, P_j)) / (C_P·L_j)`:

- stage j's balance gains `+δ` in (`v_{j+1}`) and `+δ` out (`l_j`); its pinned `v_j = 0` is untouched;
- stage j+1's balance gains `+δ` in (`l_j`) and `+δ` out (`v_{j+1}`), and `v_{j+1}/V_{j+1}` is unchanged, so its equilibrium
  rows hold to first order (a `VAPOR` stage has none);
- the `T_j` shift makes `energy_j` hold, and `energy_{j+1}` changes by exactly the negative of `energy_j`'s change.

So `δ` is a null vector of the Jacobian **at every state with that signature**, not only at roots: the internal circulation
between the pair is undetermined. The mirror case — stage j emits liquid (`TWO_PHASE` or `LIQUID`) and stage j+1 is `VAPOR` —
has the null vector `c = l_j/L_j` with the shift on `T_{j+1}`. The generator verifies all three probes in
`ref.singular_pairs`, at states built from M1's and M3's roots with the regime's pins applied: `‖Jδ‖∞/‖δ‖∞ ≤ 5.2e-53` and
`σ_min ≤ 4.4e-41`.

**Consequence (the block rule).** A cascade signature can be regular only if it reads `VAPOR^a TWO_PHASE^b LIQUID^c` from top
to bottom (ignoring `ZERO_FLOW` stages). By induction, a `LIQUID` stage forces every stage below it to be `LIQUID`, and a
`VAPOR` stage forces every stage above it to be `VAPOR`. S01's C4 (2P, L, L) and C5 (V, 2P) conform. With §4.2, a column
whose condenser and reboiler are both partial and both under ratio or rate specifications has **every stage two-phase** at a
regular root.

**Finding (not acted on here).** T05b's v2 contract may propose a signature that breaks the block rule: for instance, the
first disappearance at the top of a stripper gives (`LIQUID`, 2P, …). Such an attempt is structurally singular. Whatever it
returns is one of S01 §4.5's typed outcomes, so it is not a false success. But the contract cannot step past it to a block
signature that is regular. Whether to teach the decision function the block rule is a contract question for the design lane
(ADR 0005 D4), recorded as R-533 and Q-S02-3. S02 does not change the contract.

## 5. Refusals (validation, before any evaluation)

S01's R1–R7 apply to the column as written, with R1 and R4 widened by S8 and S7 below and R7 applied only when every slot is
a duty. S02 adds the following, checked in this order after R1–R6, all `INVALID_SPECIFICATION` (validation results, S01 §17.1)
unless marked `CAPABILITY_UNAVAILABLE`:

| Id | Condition | Code |
| --- | --- | --- |
| S1 | `condenser ∉ {none, partial, total}` or `reboiler ∉ {none, partial}` | `unsupported(condenser:<kind>)` / `unsupported(reboiler:<kind>)` (CAPABILITY_UNAVAILABLE) |
| S2 | an end specification missing at a non-`none` end, given at a `none` end, or of a kind not in §2.1 for that end; a kind listed in §3 "not offered" | `invalid_spec(specification:<end>)`; `unsupported(specification:<kind>)` (CAPABILITY_UNAVAILABLE) |
| S3 | `(distillate_rate, bottoms_rate)` | `invalid_spec(redundant_specification)` |
| S4 | a specification value not finite, or RR* ≤ 0, BR* ≤ 0, D* ≤ 0, B* ≤ 0, condenser Q* ≥ 0, reboiler Q* ≤ 0 | `invalid_spec(<kind>:<end>)` |
| S5 | `D* ≥ F` or `B* ≥ F` (F = Σ inlet flows) | `infeasible_spec(<kind>_exceeds_feed)` |
| S6 | a `top` inlet with a condenser, none without one; likewise `bottom` and the reboiler | `invalid_spec(top_inlet)` / `invalid_spec(bottom_inlet)` |
| S7 | a side feed on the condenser or the reboiler stage | `invalid_spec(side_feed_stage:<port>)` |
| S8 | `N < 1 + [condenser ≠ none] + [reboiler ≠ none]` | `invalid_spec(stage_count)` |
| S9 | `P_{j+1}* < P_j*` for some j | `invalid_spec(pressure_profile)` |
| S10 | a condenser or reboiler and every inlet dormant (`F = 0`) | `invalid_spec(no_feed)` |

R5 (the declared phase of a flowing feed fails R-007 admissibility) and R6 (a two-phase feed is `unsupported`) are S02's
**phase refusals** for inlets. The registered R5 probe is a `LIQUID` feed `(0.3, 0.4, 0.3)` at 360 K and 1.03 bar, whose
bubble margin `1 − Σ z_i K_i = −0.306` (generator claim). A run that reaches §4.2's or §4.3's structural singularity is not
refused before evaluation: it ends in a typed S01 §4.5 outcome.

## 6. Initializer `s02-profile-cmo-v1` (analytic)

1. `F_i`, `F`, `z` as in S01 §6. `F > 0` by S10.
2. **Profile.** `T_a = T(β = 0.1)` of `z` at `P_1*` and `T_b = T(β = 0.9)` at `P_N*` (ADR 0012 D1's band temperature).
   Then `T_j⁰ = T_a + (T_b − T_a)(j − 1)/(N − 1)`. Outside the domain → `initialization_failed(s02-profile-cmo-v1,
   profile_outside_domain)`.
3. **CMO totals.** `L_j = L_base + Σ_{liquid inlets at stage ≤ j} n_k,tot` and `V_j = V_base + Σ_{vapour inlets at stage ≥ j}
   n_k,tot`, each floored at `0.1·F`. `L_base = F` if `condenser ≠ none`, else 0; `V_base = F` if `reboiler ≠ none`, else 0.
4. **Flows.** S01 §6 step 5 over the equilibrium stages, with `S_ij = K_i(T_j⁰, P_j*)·V_j/L_j` (stage-wise, not `T̄`). With a
   total condenser, the first row's diagonal is `−(1 + S_i2) + φ⁰·S_i2`, with `φ⁰ = 1/2`. Then `v = S·l`.
5. `T_j = T_j⁰`, `P_j = P_j*`; the total condenser takes `φ = φ⁰` and `T_c = T_1⁰`.
6. `m` comes from the `mix` rows, `L, V` from the definitions, `D` from `Ddef`, `r, d` from `split, bal`, and every `Q` from its
   energy row. Every flow is positive (generator claim).

## 7. Solve path (algorithm)

1. **Validate** (§5).
2. **Initialize** (§6), giving `x_K`.
3. **Profile pre-solve** `s02-profile-presolve-v1`. This is S01 §7.3 with T̄ replaced by the profile, run under the rule of
   S01 §17.10:
   - Every slot row of the form `variable − parameter` (intermediate duties, `distillate_rate`, `bottoms_rate`, end duties)
     on an equilibrium stage is replaced by `T_j − T_j⁰`.
   - On a total condenser, such a slot row is replaced by `Σ r − D` (reflux ratio 1).
   - **Ratio slot rows are kept at their targets.**
   - The pre-solve must end `CONVERGED` with every stage `TWO_PHASE`, else
     `initialization_failed(s02-profile-presolve-v1, <outcome | not_two_phase>)`. Its root is `x⁰`.
   - *Why the profile:* at uniform T and P, S01's isothermal pre-solve puts a partial condenser at the dew point of the
     vapour it receives (`L_1 = 0`) and a partial reboiler at the bubble point of its liquid (`V_N = 0`). Both lie on the
     phase boundary. A strictly increasing profile moves both inside the two-phase region.
4. **Target** from `x⁰` via `solve_region`, `initializer_source = "s02-profile-presolve-v1"`, policy `s01-default-v1`.
5. **Recovery edge 3** (ADR 0010 D3, unchanged) on its trigger outcomes. The continued parameters are exactly the slot rows
   replaced in step 3. Each is of the form `variable − parameter`, as D2 requires, with `p⁰` = the variable at `x⁰`
   (`ref.cases.*.continued`). Ratio rows are not continued: they already hold at `x⁰`, so `x⁰` is an exact root of `H(·, 0)`
   (S01 DECISION 2's argument, unchanged).
6. **Records.** As in S01 §7.7, plus the profile `T⁰`, the continued slot ids with `p⁰`, and the pre-solve slot substitutions.

## 8. Acceptance of a returned state

S01 §8 (as amended by §17.3), plus:

1. every declared S02 row (§2) within its kind tolerance;
2. every partial end stage under a ratio or rate specification is `TWO_PHASE` (§4.2);
3. with a total condenser, `V_2 > 0` and `0 < φ < 1` (§2.2);
4. no adjacent pair of the final signature is singular (§4.3);
5. product ports carry `+0.0` for a pinned zero flow (sign bit; ADR 0001 D3.1).

A `CONVERGED` state that fails any item is a defect (`report_defect`), never a success.

## 9. Registered cases (values in `s02_reference.json`)

Feed `z = (0.3, 0.4, 0.3)` mol/s (F = 1) throughout. Pressures `P_j* = 1.00 + 0.01(j − 1)` bar. Intermediate stages are
adiabatic.

| Case | Configuration | Why it is in the list | Expected (sanity values) |
| --- | --- | --- | --- |
| M1 | N = 7, partial condenser, partial reboiler, liquid feed at stage 4 (340 K, 1.04 bar); RR* = 2, BR* = 1.5 | the nominal two-ratio column. Ratios are never continued, so the pre-solve must carry them | 2P ×7; `T_1 = 332.44537…`, `T_7 = 374.27319…` K; `D = 0.35190842…` mol/s; `Q_1 = −20015.51…`, `Q_7 = 31092.74…` W |
| M2 | N = 7, total condenser, partial reboiler, same feed; RR* = 1.5, B* = 0.55 | the total-condenser block (bubble row, split) and a continued rate slot (`B`, `p⁰ = 0.47181`) | condenser `T_c = 329.81615…` K; 2P ×6; `BR = 1.85270…`; `Q_c = −31412.19…` W |
| M3 | N = 5, no condenser, partial reboiler; liquid `top` (300 K, 1.00 bar); Q_r* = 30 kW | a `none` end with a stage-1 inlet, a duty-specified reboiler, every slot continued | 2P ×5; `T = 362.152 … 398.141` K; `B = 0.199597…` |
| M4 | N = 5, partial condenser, no reboiler; vapour `bottom` (385 K, 1.04 bar); D* = 0.5 | the refluxed absorber: a `none` reboiler and a continued distillate rate | 2P ×5; `RR = 1.22504…`; `Q_1 = −18776.90…` W |
| P1 | M3 at Q_r* = 3 kW | the phase case. The only regular signature is LIQUID ×5 (§4.3): the column is a liquid heater. Closed form: `l_j = top`; `T_j = T_{j−1} − V_m ΔP/C_P` (exactly −1e-3 K per 1 kPa); `T_5 = T_4 + Q_r*/(F C_P)` | `T = (300, 299.999, 299.998, 299.997, 329.996)` K; distillate `+0.0`; bubble margin ≥ 0.43 |
| V-M1 | M1's root under (duty, duty), (RR, B), (D, BR), (RR, duty) | matched spec sets: each must return M1's root. A wrong sign or index in any slot row moves the root | `ref.variants.M1` (`σ_min ≥ 0.0144`) |
| V-M2 | M2's root under (duty, duty), (D, BR) | the total condenser's `duty` and `distillate_rate` slots | `ref.variants.M2` (`σ_min ≥ 2.4e-3`) |
| X-DB | (D, B) at M1's and M2's roots | S3 | refused; generator `σ_min < 1e-40` |
| S-R5 | M1 with the feed at 360 K | an inadmissible declared phase | `inadmissible_inlet(feed, LIQUID)` |

Every flowing case is checked in the generator:
- every pre-solve, path and target stage lies in the domain, with `L, V > 1e-3` mol/s on two-phase stages;
- the pre-solve and target are regular (`σ_min > 1e-4`; targets 0.018 to 0.053);
- the straight specification path from `x⁰` stays two-phase at 16 equal steps (M1–M4);
- the implementation's division-free rows (§2) vanish below 1e-38 at the root;
- overall component and energy closure holds.

M1–M4 are the "four matched column cases" of X31: each is matched against an independent expectation, and M1 and M2 are also
matched across specification sets. S03 owns the two independent references.

## 10. Assertions

`ref` = `s02_reference.json`. **State tolerance** is S01's as amended (R-514): flows `|Δ| ≤ 1e-6·|ref| + 3.1e-7` mol/s,
`|ΔT| ≤ 1e-4` K, `|ΔQ| ≤ 1e-2` W, plus ratios `|Δ| ≤ 1e-6·ref`.
- *Above the floor:* by ADR 0018 D2, the `newton_refined` promise is `τ_kind`, which is 10× under these tolerances.
- *Below the smallest error worth catching:* a dropped Poynting term moves T by 1e-3 K (P1 makes this exact). Swapping RR and
  BR, or the sign of a slot row, moves the root by O(1 K).
- *Needs a fact:* WO-2 records the maximum measured deviation. If it exceeds 1/10 of a tolerance, this section is amended
  (S01 §10's rule).

| Id | Assertion | Expected | Tolerance |
| --- | --- | --- | --- |
| A01 | Column and row counts for M1–M4 (P1 has M3's); row ids unique; per regime, pinned = dropped | `ref.dof` | exact |
| A02 | S1–S10 and S-R5, one registered input each, plus S01 R1–R7 applied to a column | §5 codes | exact |
| A03 | X-DB refused before any evaluation, at both D*/B* splits (`D* + B* = F` and `≠ F`) | `invalid_spec(redundant_specification)` | exact |
| A04 | Initializer on M1–M4: `T_a`, `T_b`, profile, `L_cmo`, `V_cmo`, `l`, `v` | `ref.cases.*.initializer` | T abs 1e-8 K; flows rel 1e-10 (as S01 A03) |
| A05 | Pre-solve root, its slot substitutions and `p⁰` for M1–M4; ratio rows hold at their targets at `x⁰` | `ref.cases.*.presolve`, `.presolve_slots`, `.continued` | state tolerance; slot kinds exact |
| A06 | M1–M4 target root, signature, products and `spec_values` | `ref.cases.*.target`, `.signature`, `.spec_values` | state tolerance; signature exact |
| A07 | V-M1 and V-M2: each set, solved from its own pre-solve, returns A06's root with `same_root = SAME` | `ref.cases.M1/M2.target` | state tolerance |
| A08 | Overall component and energy closure at every converged case | 0 | `n_rows·τ_kind` |
| A09 | Every accepted state passes §8, items 1–5 | pass | kind tolerances |
| A10 | Compiled Jacobian vs central differences at `x_K` and the root of M2 (total condenser, ratio and rate rows) and M1. Step `h_j = 1e-6·max(D_x(j), |x_j|)` (R-516), `D_x(φ) = 1` | agree | 1e-6 scaled. Floor: S01 measured 5.9e-11 with this rule for S01's row kinds. WO-2 measures it for S02's rows and records it; it must be ≤ 1e-8 (needs a fact) |
| A11 | §4.3's circulation vector, mapped to the implementation's columns, annihilates the compiled Jacobian at the three `ref.singular_pairs` probe states. Mapping: `l_j`, `v_{j+1}`, `m_j` (inflow `v_{j+1}`) and `m_{j+1}` (inflow `l_j`) each += `c`; `L_j` and `V_{j+1}` += 1; plus the `T` shift. At M1's all-2P root the same vector is not null: the shift moves a two-phase stage's `T` by about `(h^V − h^L)/(C_P L)` ≈ 280 K per mol/s, and with it its `K` | `‖D_r⁻¹ J δ‖∞ / ‖D_x⁻¹ δ‖∞` | ≤ 1e-9 at the probes; ≥ 1e-3 at the 2P root (an all-zero Jacobian fails here and in A10). Double rounding gives about 1e-13; a dropped `l_j` enthalpy in `energy_{j+1}` gives O(1) |
| A12 | P1: the outcome is `CONVERGED` with signature LIQUID ×5 equal to the closed form (`ref.phase_case.P1`; distillate `+0.0` sign-checked), **or** a typed S01 §4.5 outcome whose attempt records name every attempted signature. Never an unaccepted `CONVERGED` | as stated | state tolerance; signature, outcome exact |
| A13 | Edge 3 forced on M1 and M2 from `x⁰`: dyadic λ, `p⁰ = ref.cases.*.continued`, the ratio rows untouched at every λ, the λ = 1 instance's `(model_version, constants_sha256)` equal to the target's, final `SAME` as A06 | — | `p⁰`: Q abs 1e-2 W, rates rel 1e-6; rest exact |
| A14 | M1 from four perturbed openings (profile ± 5 K, i.e. the pre-solve level as in R-517; `x_K` flows ×0.5, ×2) | `CONVERGED`, `SAME` as A06 | exact |
| A15 | M1 and M2 solved twice: identical final `state_sha256` and records | — | exact |
| A16 | S01's 20 assertions still pass on `wp/S02` (S02 extends S01's code and must not move it) | S01 suite | as registered |

## 11. Generator

`s02_reference.py` imports nothing from `openflowsheet`. Its formulation differs from the implementation's:
- 8 unknowns per equilibrium stage `(l_i, v_i, T, Q)`, mole-fraction (quotient) equilibrium, and ratio specifications as
  quotients;
- the total condenser reduced to `(φ, T_c, Q_c)`;
- its own damped Newton with complex-step derivatives, following §7 as a straight path in 16 equal λ-steps.

It shares SYN-001's closed forms and the definitions of §6 and §7 with the implementation, and nothing else. Every number in
this document is a generator claim (`ref.claims`, 906), except where it is marked as S01's. `--check` refuses to emit when a
claim fails.

## 12. Work orders (`opus-engineer`, about 120k context each)

**WO-1: column spec, rows, initializer** (`models/syn001/column.py`, the name at the engineer's choice, logged).
- `ColumnSpec` with kinds, end specifications, absent inlets, and §5 validation reusing S01's.
- Row builders: the ratio row (`a − p·b`) and the bubble row, each an additive `rows.py` builder. The total-condenser block;
  the slot rows; §2.3's label.
- The §6 initializer.
- Closes A01, A02, A03, A04. If S01's `CascadeSpec` cannot express absent inlets, extend it additively (S01's tests stay green).

**WO-2: compile and solve.**
- §7's pre-solve with slot substitution, the target, edge 3 over the replaced slots only, §8 acceptance, products.
- Closes A05–A10, A13, A15, A16. Records the deviation measurement and A10's floor.

**WO-3: phases, perturbations, evidence.**
- A11's probes on the compiled Jacobian; P1 (A12, recording the outcome and the attempt list); A14.
- Writes `evidence/S02/<commit>/manifest.json`.

## 13. Evidence manifest check list

- `status: tested` requires a passing test for each of A01–A16, citing its id.
- `s02_reference.py --check` passes at the manifest commit (906 claims, JSON byte-identical).
- `ruff check` and `ruff format --check` are clean; `scripts/gate.sh` passes before merge.
- The deviation measurement (§10), A10's measured floor and P1's actual outcome are recorded with their commit.
- §14 is listed verbatim as limitations. `reviewed` is set only by the `reviewer`.

## 14. What this does not establish

- **Synthetic data only.** SYN-001 is an ideal three-component fixture with no azeotropes and composition-independent `K`.
  Nothing here validates a column against real chemistry, plant data or another simulator. The generator's agreement
  validates the transcription of SYN-001 and of §2's rows, not the property model. Real-chemistry columns need a
  liquid-capable property method (out of scope; PR routes are vapour-only).
- **No independent column reference.** M1–M4 are matched against this generator, which shares SYN-001 and §6–§7's
  definitions with the implementation. The two independent references and the perturbation studies of X31 are S03's.
- **No uniqueness or global convergence.** Nothing is claimed beyond the registered states, A14's openings and the straight
  paths the generator followed.
- **No phase-transition robustness.** §4.3 proves which signatures are singular. It does not show that the v2 contract
  reaches a regular block signature: P1's outcome may be a typed failure (A12). Partial dormancy stays unclaimed (S01).
- **No inverse specifications** (purity, recovery, temperature), no subcooled total condenser, no total reboiler, no
  pump-arounds, side draws or side heaters beyond S01's intermediate duties, no hydraulics, no efficiencies.
- **No inside-out, rate-based or sensitivity results.**
- **No admissibility claim for an unregistered specification pair** at a state other than the registered roots.

## 15. Open questions (each with a default)

1. *Needs a fact.* Does the v2 contract reach P1's LIQUID ×5 from the all-2P opening? **Default:** assert A12 as written
   (either branch). The outcome is recorded; a typed failure becomes a §14 limitation and feeds R-533, not a relaxed test.
2. *Needs a fact.* Is A10's floor for the new rows ≤ 1e-8 under R-516's step? **Default:** yes (same magnitudes as S01's rows).
   If not, amend §10 with the measured floor and its derivation.
3. *Needs a fact.* Do V-M1/V-M2 converge from their own pre-solves? The pre-solve differs per set, because ratio rows are
   kept. **Default:** assert A07. If a set fails, record it and amend §9; do not drop the set.
4. *Needs the user's preference.* Saturated-only total condenser; no inverse specifications in S02 (Q-S02-1, Q-S02-2).
   **Default:** yes.
5. *Needs the user's preference.* Teach the phase contract the block rule (Q-S02-3)? **Default:** not in S02. S03 decides
   after P1's measurement.

## 16. Decisions

See `docs/S02_DECISIONS.md` (DECISION lines 2–9) and register R-530 to R-535.
