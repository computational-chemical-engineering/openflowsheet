# S02 — MESH column on SYN-001: conventions, specification sets, refusals, cases and test specification

Design lane (`specifier`), 2026-10-22. Package S02 (plan v1.2 §4.5, `docs/implementation-plan.md:282`; X31 `:357`), brief
`docs/briefs/S02-specification.md`. Base: S01 (`docs/derivations/S01-spec.md` with Amendment 1, §17). Reference generator
`docs/derivations/scripts/s02_reference.py` (mpmath, 50 digits; `--check` re-derives 1074 claims (906 before §18.7 WO-G, 1064 before §19) and byte-compares
`s02_reference.json`; about 3 minutes). Decisions: `docs/S02_DECISIONS.md`, register R-530 to R-535. **Amended 2026-10-22
by §17** (Amendment 1, ruling round 1 on WO-1's questions; R-536 to R-539): §0, §2.2, §2.3, §10, §12; **and by §18**
(Amendment 2: §7.3 replaced by the bubble-point easy endpoint, ADR 0044, A05–A07, A13, A14, A20–A22; R-546 to R-549). **And by §19** (Amendment 3, review rulings: ADR 0044 D1 narrowed, A14's shift clause, WO-G's stop;
R-550 to R-554).

## 0. Authority and scope

Normative for S02. It composes with everything S01 composes with (ADR 0001, 0005, 0008 D3, 0010 D2–D3, 0012 D1–D4, 0018)
and with S01 itself, and reopens none of them. It changes no frozen interface (`docs/interfaces-frozen.md`): the new rows are
additive row builders, the new column `φ` is of ADR 0001's existing quantity kind `dimensionless` (the scaling table carries
it as a column-only kind with nominal 1, §17 item 1), no row of a new kind is added (so
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
(every `T_c` satisfies it), which is why §8 requires `V_2 > 0`. `φ` has FD column scale 1, its registered nominal
(§17 item 1).

### 2.3 Absent inlets

A column with a condenser has no `top` inlet; one with a reboiler has no `bottom` inlet. **Absent** means no inlet columns and
rows, not a dormant inlet (`ref.dof` counts only present inlets). S01's ZERO_FLOW label `T_label(1) = T_top` (S01 §4.3) becomes
the temperature column of the first present inlet in `ColumnSpec.inlets()` order when there is no `top` inlet (§17 item 2,
replacing the constant `T_1⁰`, which the frozen `ZeroFlowForm` cannot carry); a label of `T_2` would make a cycle with stage 2's
label.

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
- Closes A05–A10, A13, A15, A16 and §17's A17–A19 (with §17's code changes). Records the deviation measurement and A10's floor.

**WO-3: phases, perturbations, evidence.**
- A11's probes on the compiled Jacobian; P1 (A12, recording the outcome and the attempt list); A14.
- Writes `evidence/S02/<commit>/manifest.json`.

## 13. Evidence manifest check list

- `status: tested` requires a passing test for each of A01–A16, citing its id.
- `s02_reference.py --check` passes at the manifest commit (1074 claims since §19 item 2, 1064 since §18.7 WO-G; JSON byte-identical).
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

See `docs/S02_DECISIONS.md` (DECISION lines 2–9; RULING lines of ruling round 1) and register R-530 to R-539.

## 17. Amendment 1 (2026-10-22, design lane `specifier`): ruling round 1 on WO-1's questions

Brief `docs/briefs/S02-ruling-1.md`; questions Q-S02-WO1-1 to Q-S02-WO1-3 (`docs/S02_DECISIONS.md`); register R-536 to R-539.
Each item replaces the text it names. **No count, root, registered value or generator claim moves:** `ref.dof` stays M1 103,
M2 100, M3 75, M4 75, and `s02_reference.json` is not re-emitted (`--check` passes unchanged at this amendment's commit). No
frozen interface, schema, row kind, tolerance, policy or identity moves, so no ADR is written and ADR 0044 stays free (R-539).

1. **`φ`'s kind is `dimensionless`, a column-only scaling kind with nominal 1 (Q-S02-WO1-1, R-536).**
   - *Finding.* §0's "existing kind" was half right. `dimensionless` is an existing ADR 0001 D1.3 quantity kind
     (`schemas/quantity.schema.json`, `units`), but not a scaling kind: `compile.spec.QuantityKind` and
     `numerics.scaling.REGISTERED_NOMINALS` lack it, so `Scaling.from_kinds` refuses M2's `<U>.stage.1.phi` (WO-1, measured).
   - *Ruling.* `QuantityKind` gains `"dimensionless"` and `REGISTERED_NOMINALS` gains `"dimensionless": 1.0`. It is a
     **column kind only**: `Scaling.from_kinds` refuses a *row* declared `dimensionless` with `ScaleUnavailableError` naming
     the row, so `region.KIND_TOLERANCE`, K04's tolerance table and every `check_policy_sha256` stay as they are, and "no row
     kind" is executed rather than asserted in prose. `SCALE_PROVENANCE` is unchanged; the new entry's comment cites this item.
   - *Why 1.* A pure number's unit is 1, and §2.2 and A10 already fix `D_x(φ) = 1`. `φ` needs no bound of its own: at any
     state where the rows hold, `r_i = φ·v_i2 ≥ 0` and `d_i = (1 − φ)·v_i2 ≥ 0` with `V_2 > 0` (§8) give `φ ∈ [0, 1]`, and
     `r`, `d` carry the `molar_flow` lower bound 0 in `solve_region`. It gets none.
   - *Why not reformulate.* Replacing `φ` by the reflux total `R` (molar_flow), with rows `r_i·V_2 − R·v_i2` of kind
     `molar_flow_squared`, avoids the new entry but changes C rows' form and kind, every registered M2 and V-M2 Jacobian
     claim and WO-1's builders, to save one table entry. The `φ` form is linear in `r` and bilinear in `(φ, v)`: the simpler.
   - *Frozen or registered?* Neither. `docs/interfaces-frozen.md` freezes the three protocols, the schema list, ADR 0001
     D1–D5 and ADR 0008 D1–D3; `QuantityKind` and the nominal table are not on it, and ADR 0001's kind list does not grow.
     No registered value moves. SYN-001 §9 and `benchmarks/registry.yaml` `scales` hold the SYN-001 families' physical
     nominals (no family has a pure-number column), and **`registry.yaml` does not carry the entry**: S02's registered
     numbers live in `s02_reference.json`, which already carries A10's `D_x(φ) = 1`. No hash reads the nominal table, and no
     existing problem declares a `dimensionless` column, so every existing `Scaling` is unchanged entry by entry. R-043's
     warning is against a kind that moves `check_policy_sha256`; a column-only kind cannot (R-536).

2. **Stage 1's `ZERO_FLOW` label without a `top` inlet is the first present inlet's temperature (Q-S02-WO1-2, R-537).**
   Replaces §2.3's `T_1⁰`.
   - *Ruling.* Neither option (a) nor (b). Without a `top` inlet, `label_source(spec, 1)` is
     `temperature_id(inlet_stream(U, spec.inlets()[0].port))`: the temperature column of the first present inlet in
     `ColumnSpec.inlets()` order (`top`, `bottom`, then the side feeds in declaration order). With a `top` inlet that is
     `T_top`, so S01 §4.3 is unchanged. M1's stage-1 label is the `feed` inlet's temperature and M4's the `bottom` inlet's.
     `ProfileLabel` is withdrawn; `label_source` always returns a column id, and `ColumnRegimeForm.label` maps onto the
     frozen `ZeroFlowForm.label` unchanged.
   - *Existence.* Every column that passes §5 with a partial condenser has a present inlet: with `reboiler = none`, S6
     requires `bottom`; with a reboiler, S10 refuses `F = 0`, which includes the column with no present inlet. The one input
     that would reach a label without a column is refused `invalid_spec(no_feed)` before any form is built (A18).
   - *No cycle.* An inlet's temperature column is fixed by its own inlet row and is no split's temperature, so the chain
     `T_j → T_{j−1} → … → T_1 → T_inlet` ends.
   - *Why not (a)*, a pinned column `T0` with row `T0 − T_1⁰*`. It adds a column and a row to every partial-condenser
     declaration for a regime the spec never claims (partial dormancy, S01 §14), moves §3's count and `ref.dof` (M1 104,
     M4 76), and makes a compiled parameter the output of §6's band-temperature solve, so `constants_sha256` would depend on
     an iterative libm computation whose last bit may differ between the two CI architectures. `ZeroFlowForm` keeps its label
     row out of the compiled declaration for this reason (its docstring; T05b spec §7.2).
   - *Why not (b)*, a constant label. `ZeroFlowForm.label` and `splits.check_agreement` name a column (T05b spec §7.2,
     ADR 0012 D4 (c)); widening them takes an ADR for a regime S02 does not claim.
   - *What the value is.* A label pins an unclaimed regime's otherwise free temperature to a finite, cycle-free column so the
     attempt's system is square and the attempt ends typed. It carries no physics, and nothing in `s02_reference.json` reads
     it.

3. **The total condenser's accumulation is confirmed (Q-S02-WO1-3, R-538).** The reflux drum holds liquid, so its two
   conservation rows are `holdup_balance` (ADR 0008 D3.1): `COL-tc-bal` accumulates `N_i` (mol; row mol/s) and
   `COL-tc-energy` accumulates `U` (J; row W), which meets D3.2's dimension rule. Both are written `Σ in − Σ out + sources`
   (D3.3): `v_i2 − r_i − d_i`, and `Q_c + Ḣ^V(v_2, T_2) − Ḣ^L(r) − Ḣ^L(d)` with `Q_c` positive into the drum. Not
   `zero_holdup_balance`: a drum is a vessel, not a junction. `COL-tc-split` (a constitutive split of one liquid, not a
   balance), `COL-tc-Ddef` (a definition), `COL-tc-bubble` (an equilibrium condition), `COL-tc-P` and the slot rows
   `COL-reflux-ratio`, `COL-boilup-ratio`, `COL-distillate-rate`, `COL-bottoms-rate`, `COL-duty` (specifications) are
   `algebraic`. S01's `CAS-*` declarations are unchanged. A root cannot see a row's overall sign (it is invariant under
   `F_row → −F_row`); the relative signs inside each row are fixed by A06's root (a wrong one moves `Q_c` by `O(Ḣ)`), and the
   overall sign, which PTC's `M` reads (D3.4–D3.5), by A19.

4. **Assertions added** (§10's conventions; WO-2 closes them).

| Id | Assertion | Expected | Tolerance |
| --- | --- | --- | --- |
| A17 | `φ`'s kind and scale. On M2, `variable_kinds[<U>.stage.1.phi] == "dimensionless"`; `Scaling.from_spec` builds for M2 and for V-M2's two sets, with `column[phi] == 1.0` and every other entry equal to `REGISTERED_NOMINALS` of its declared kind; `REGISTERED_NOMINALS` is K03's five entries, unchanged, plus `"dimensionless": 1.0` (`test_k03_scaling`'s literal extended, not loosened); `"dimensionless"` is a key of neither `KIND_TOLERANCE` nor K04's tolerance table, and the `check_policy_sha256` values existing tests pin still pass; a `ProblemSpec` declaring one row `dimensionless` raises `ScaleUnavailableError` naming that row; WO-1's strict xfail `test_a01_phi_is_declared_dimensionless` becomes a plain pass | as stated | exact |
| A18 | Stage-1 label. The stage-1 `ZERO_FLOW` label is `(label_row_id(U, 1), T_1, T_feed)` on M1 and `(…, T_bottom)` on M4; M3's is `T_top`; M2's stage-2 label is `T_c`; `label_source` returns a column id of the declaration for every stage of M1–M4; the zero-flow-form agreement check (`splits.py`, the `zero_flow_form_disagrees` branch) accepts every stage's form of M1–M4; on M1 at `x_K` with stage 1 `ZERO_FLOW` and every other stage `TWO_PHASE`, the attempt's system is square and its label row's residual is `T_1 − T_feed` (one IEEE subtraction); a partial-condenser, partial-reboiler column with no inlet is refused `invalid_spec(no_feed)` before any form is built | as stated | exact |
| A19 | Condenser accumulation and sign. M2's compiled `row_accumulation` is `holdup_balance` on exactly the `COL-tc-bal` and `COL-tc-energy` rows among the `COL-*` rows and `algebraic` on the rest (`CAS-*` rows as S01 declares). At the trial state `v_2 = (0.5, 0.375, 0.25)`, `r = (0.125, 0.0625, 0.03125)`, `d = (0.25, 0.0625, 0.03125)` mol/s, `COL-tc-bal` is `(+0.125, +0.25, +0.1875)` mol/s. At `Q_c = 1000` W with `v_2 = r = d = 0` (any `T_2`, `T_c` in the band, `P_c = P_1*`), `COL-tc-energy` is `+1000.0` W | as stated | exact |

*Tolerances.* A17 and A18 are structural, plus one correctly rounded subtraction that the expectation repeats: floor 0. A19's
operands are dyadic with at most five significant bits, so every difference is exact in binary64 (floor 0); a dropped `r` or
`d`, a flipped sign or a permuted component index changes some entry by at least 0.03125 mol/s, because the three expected
entries are distinct and nonzero. The duty case is `Q_c` plus products of zero flows with finite enthalpies, each `±0`, so
it is `Q_c` exactly; a flipped row sign gives `−1000`. A non-finite value there is a zero-flow defect (ADR 0001 D3), not a
tolerance question.

5. **What this amendment does not establish.** The stage-1 label value is not a claim about a dormant condenser's
   temperature; partial dormancy stays unclaimed (S01 §14, §14 here). The `dimensionless` nominal is registered for `φ` only
   as a column scale; no row kind, tolerance or certificate bound exists for it, and a later package that needs a
   dimensionless *row* needs its own ruling (and, through K04's table, an ADR). No open question is added.

6. **Code changes WO-2 makes** (not made here): `compile/spec.py` (`QuantityKind`), `numerics/scaling.py` (the entry and
   the column-only refusal), `models/syn001/column.py` (declare `φ`'s kind; `label_source`; withdraw `ProfileLabel`),
   and the tests of A17–A19, with `tests/test_k03_scaling.py`'s literal extended. They touch scaling and phase-form code,
   so the package's `reviewer` pass covers them (CLAUDE.md, lane rule).

## 18. Amendment 2 (2026-10-22, design lane `architect`): the easy endpoint by bubble-point sweeps; edge 3 after a restart into a singular signature

Brief `docs/briefs/S02-design-presolve.md`; questions Q-S02-WO2-1 to Q-S02-WO2-3 (`docs/S02_DECISIONS.md`); register R-546 to
R-549; **ADR 0044 (Proposed)** amends ADR 0010 D3's trigger set. Replaces §7.3, §7.6's pre-solve records and §10's A05, A06,
A07, A13, A14 as stated below; adds A20–A22. §6 (the initializer, A04) is unchanged. §0's "No ADR is needed"
(R-535, R-539) is superseded in exactly one respect: ADR 0044 (§18.3); rows, kinds, schemas and policies stay as §0 says. Scratch measurements:
`scratchpad/s02-design/` of the design session (not committed); every number below was measured on `47eb3aa`'s code.

### 18.1 Finding

1. **The Newton pre-solve has no basin around `x_K`.** §6's `x_K` solves the component balances at CMO stage ratios but not the
   bubble condition: `Σ_i K_ij x_ij ≠ 1` on every stage (0.72–0.88 on M1's stages 1–3). TP projection of `x_K` at the profile
   therefore opens single-phase stages (M1 `V,V,V,2P×4`, rank 90 of 91 because stage 1 VAPOR under RR is §4.2's singularity;
   M3 `2P,L,L,L,L`), and an unprojected all-2P opening (PH-type, measured) is driven by the bounded Newton step to
   `BOUND_BLOCKED` within 3 iterations (M1: `T_1` 351 → 373 K, the wrong way; the root has 344.7 K). No opening rule for
   the *same Newton problem* fixes this: the problem is a coupled TP column whose iterates leave the two-phase region.
2. **The target walks into singular signatures after a globalization failure.** From any easy endpoint, a full Newton step
   that crosses a flow bound ends attempt 0 `BOUND_BLOCKED`; the contract reads it as a disappearance and restarts in a
   signature that §4.2 or §4.3 proves singular (M1 from `ref…presolve`: `(L,L,2P×5)`, rank 94 of 95; M2 from §18.2's endpoint:
   `(2P×5,V)`, a bottoms-rate reboiler with no liquid). The terminal outcome is then `LINEAR_SOLVE_FAILED`, which ADR 0010 D3
   excludes, so edge 3 never runs — although forced edge 3 reaches `ref.target` every time (10 of 10 cases and variants).
   Which outcome ends the walk depends on the opening's last bits: V-M2 `(D, BR)` ends `LINEAR_SOLVE_FAILED` from the
   endpoint stopped at 1e-12 K and `ACTIVE_SET_CYCLING` (a trigger) from the same endpoint stopped at 1e-9 K.
3. **Multiplicity.** V-M2 `(duty, duty)` has a second regular root `R2` at M2's duties: `D = 0.274431`, `φ = 0.775456`,
   `T_c = 321.583 K` (M2: 0.45, 0.6, 329.816 K), all six stages two-phase, scaled `σ_min` (implementation's scaling) 2.1e-4
   against 1.7e-4 at M2's root. The solve path of §18.2 returns `R2` (plain Newton, 5 iterations). Which root a `(duty, duty)`
   column returns depends on the easy endpoint (with every stage ratio ×2, it returns M2's root via edge 3).

### 18.2 Decision A — §7.3 is replaced: the easy endpoint `s02-bubble-point-v1` (constructed, not solved)

The pre-solve's only job (S01 DECISION 2, ADR 0010 D2) is an all-two-phase state `x⁰` that satisfies **every target row except
the continued `variable − parameter` slot rows**. With composition-independent `K` (SYN-001), such a state is constructed by
bubble-point sweeps at fixed stage ratios (Wang–Henke's inner loop without its energy step): component balances are linear for
fixed `S_ij = K_ij ρ_j`, and the bubble condition fixes `T_j`. Energy is activated last, by the duties' continuation (§7.5) or
directly by the target's Newton (§7.4) — the blueprint's staged activation and continuation (`blueprint-v3.1.md:600`).

**Algorithm** (normative; `j` over equilibrium stages, `i` over components; all inputs from §6, which is unchanged):

1. **Stage ratios.** `ρ_j = V_j^cmo / L_j^cmo` (§6 step 3, floors included). Overrides by the end specification:
   partial condenser under `reflux_ratio` RR*: `ρ_1 = 1/RR*`; partial reboiler under `boilup_ratio` BR*: `ρ_N = BR*`; total
   condenser: `φ = RR*/(1 + RR*)` under `reflux_ratio`, else `φ = φ⁰ = 1/2` (§7.3's former `Σ r − D` substitute, kept).
2. **Start.** `T_j^(0) = T_j⁰`, §6's profile (A04's values; plus `profile_shift` for A14).
3. **Sweep** `k = 1 … 500`:
   a. `K_ij = K_i(T_j^(k−1), P_j*)` (the rows' `LnKBlock` values, `cascade._k_values`).
   b. Per component, the tridiagonal of §6 step 4 with `S_ij = K_ij ρ_j` (total condenser: first diagonal
      `−(1 + S_i2) + φ S_i2`), solved by `thomas`; `l_ij` its solution, `v_ij = S_ij l_ij`.
   c. `T_j^(k)` = the bubble temperature of `l_j` at `P_j*`: `saturation_band.band_temperature(provider, l_j, P_j*, β = 0)`
      (ADR 0012 D1's bisection; at β = 0 its function is `Σ l_ij (K_ij − 1)`). A position other than `inside` ends
      `initialization_failed(s02-bubble-point-v1, bubble_point_outside_domain)`.
   d. Stop when `max_j |T_j^(k) − T_j^(k−1)| ≤ 1e-9 K`. After sweep 500 without stopping:
      `initialization_failed(s02-bubble-point-v1, sweeps_exhausted)`.
4. **Final flows.** Steps 3a–3b once more at the stopped `T^(k)`, so the balances hold to rounding at the returned `T`.
5. **State `x⁰`.** §6 steps 5–6 (`_initial_state`) with `T_j = T_j^(k)`; at a total condenser `φ` from step 1 and
   `T_c` = the bubble temperature of `v_2` at `P_1*` (step 3c's call); `L, V, D` as sums, `m` from `mix`, every `Q` from its
   energy row. `p⁰` of each continued slot = its variable at `x⁰` (§7.5, unchanged).

**Why it is an exact easy endpoint.** With `v_ij = K_ij ρ_j l_ij`: `V_j = ρ_j L_j s_j`, `s_j = Σ_i K_ij x_ij`, so the
equilibrium row is `v_ij L_j − K_ij l_ij V_j = K_ij ρ_j l_ij L_j (1 − s_j)`, zero at the bubble temperature; a ratio end has
`L_1 − RR*·V_1 = L_1 (1 − s_1)` and `V_N − BR*·L_N = BR* L_N (s_N − 1)`, zero likewise; balances, `mix`, definitions, the
total condenser's bubble, split and balance rows and every energy row hold by construction. The residual left is
`O(|ΔT_last| · ∂s/∂T)`: measured worst row over all ten cases ≤ 1.3e-11 (W, an energy row), under every kind tolerance.
**Two-phase by construction:** the tridiagonal's matrix is a nonsingular column-diagonally-dominant irreducible M-matrix up to
sign (S01 §6's argument; the total condenser's diagonal `1 + (1 − φ)S_i2` keeps it), so `l_ij > 0` and `v_ij > 0` for every
component present in some inlet, on every stage; the target's PH-type splits open `TWO_PHASE` unprojected (T05b §6.4).

**Measured** (scratch, `47eb3aa`): sweeps to 1e-9 K: M1 25, M2 21, M3 30, M4 39, V-M1 21–26, V-M2 21–27; start `±5 K` reaches
the same fixed point within 4e-13 K; stage ratios ×0.5 / ×2 converge in 15–96 sweeps. Cost: under 0.1 s per case.

**Withdrawn:** the Newton pre-solve `s02-profile-presolve-v1`, its policy object and `COL-presolve-T` leave the solve path.
`ref.cases.*.presolve` (the profile root) stays registered as a **second easy endpoint** for A06b/A13b (it is a root of
`H(·,0)` too). `initializer_source` of the target is `s02-bubble-point-v1`. No new `SolvePolicy`: T05b B06 is untouched.

**Records (replaces §7.6's pre-solve items):** `x_K`'s and `x⁰`'s `state_sha256`, the sweep count, the last
`max |ΔT|`, `ρ` per stage and `φ`, the continued slot ids with `p⁰`.

**Rejected.** (a) *An opening rule for the Newton pre-solve* (two-phase opening signature, band projection at the profile):
measured, the unprojected all-2P opening still ends `BOUND_BLOCKED` on M1; the profile pins `T_j` where `x_K`'s stage feeds are
single-phase. (b) *More pre-solve attempts* (default `max_attempts`): M1 still `LINEAR_SOLVE_FAILED`; with PH-type also,
`ACTIVE_SET_CYCLING`. (c) *Continuation inside the pre-solve* from the bubble-point state to the linear profile: reaches the
registered `x⁰` but runs the homotopy as a primary method through edge 3's recovery API (records would claim a recovery that
never failed) and ends farther from the target (M1 profile root `T_2 = 354.7 K`, target 341.0 K). (d) *A spec-consistent CMO*
(D from the RR/BR balance): would start closer, but needs a latent-heat closure for duty ends and was not needed (§18.5).

### 18.3 Decision B — edge 3 runs after `LINEAR_SOLVE_FAILED` in a restart (ADR 0044); the contract does not learn the block rule

**Answer to Q-S02-WO2-2 and Q-S02-3.** ADR 0010 D3 excluded `LINEAR_SOLVE_FAILED` because a rank-deficient system is not
helped by continuation. That holds for the signature the homotopy runs in — item 0's opening. A `LINEAR_SOLVE_FAILED` that ends
an attempt **opened by a contract restart** (attempt index ≥ 1) belongs to a signature the contract chose after a
globalization failure of attempt 0; it says nothing about item 0's signature, which edge 3 re-enters. It is the same conversion
of a globalization failure into a restart that made D3 include `ACTIVE_SET_CYCLING` and `ATTEMPTS_EXHAUSTED`. ADR 0044 adds:
*`LINEAR_SOLVE_FAILED` is a trigger iff the failed region solve ran more than one attempt.* Nothing else changes (count 1,
item-0 opening, frozen signature, records, `HOMOTOPY_STALLED` if the physics really changed phase — P1 measures exactly that).

**Not the block rule in the contract.** (1) It would not cover the measured cases: M2's, V-M1 `(RR, B)`'s and `(D, BR)`'s
restarts are §4.2's end-stage singularity under a rate or ratio specification, not a §4.3 pair. (2) It is cascade structure; a
model-specific screen inside ADR 0005 D4's single decision function is what R-533 already declined. (3) A generic numerical
rank screen on proposed restarts would rewrite the terminal outcome to the proposing attempt's, hiding the singular attempt;
ADR 0044 keeps the honest terminal record and only widens when recovery runs.

### 18.4 Decision C — A07's comparison (Q-S02-WO2-3) and the second root

- `same_root` is a within-problem identity (T03 §8.3): across specification sets the constants and rows differ and
  `NOT_COMPARABLE` is the correct answer. **A07 compares each set's root to `ref.cases.<case>.target` by the state
  tolerance**; `same_root = SAME` is asserted only between runs of one problem (A13, A14).
- V-M2 `(duty, duty)` returns `R2` (§18.1 item 3). §15.3's rule applies: not dropped, §9 amended — the generator registers
  `R2` (WO-G), A07 asserts `R2` for that set and A21 asserts the multiplicity. §14 gains: *a `(duty, duty)` column may have
  several regular roots; which one is returned depends on the easy endpoint; no root-selection claim is made.*

### 18.5 Measured outcomes (scratch, `47eb3aa` + ADR 0044's trigger; deviation = worst column / its state tolerance)

| Case | from §18.2's `x⁰` | path | deviation | from `ref…presolve` (A06b) |
| --- | --- | --- | --- | --- |
| M1 | CONVERGED 2P×7 | attempt 0 `BOUND_BLOCKED` → `ACTIVE_SET_CYCLING` → edge 3 | 3.0e-6 | edge 3 after `LINEAR_SOLVE_FAILED` (ADR 0044), 2.4e-8 |
| M2 | CONVERGED 2P×6 | `BOUND_BLOCKED` → `(2P×5,V)` `LINEAR_SOLVE_FAILED` → edge 3 (ADR 0044) | 1.7e-7 | plain, 1.1e-6 |
| M3 | CONVERGED 2P×5 | plain, 4 iterations | 8.5e-3 | edge 3 after `ACTIVE_SET_CYCLING`, 4.0e-8 |
| M4 | CONVERGED 2P×5 | plain, 6 iterations | 4.9e-6 | plain, 7.5e-3 |
| V-M1 duty+duty / RR+duty | CONVERGED | edge 3 after `ACTIVE_SET_CYCLING` | 2.3e-8 / 4.4e-7 | — |
| V-M1 RR+B / D+BR | CONVERGED | edge 3 after `LINEAR_SOLVE_FAILED` (ADR 0044) | 1.0e-6 / 3.4e-7 | — |
| V-M2 D+BR | CONVERGED | edge 3 (`ACTIVE_SET_CYCLING` at the 1e-9 K stop; `LINEAR_SOLVE_FAILED` at 1e-12 K) | 5.6e-8 | — |
| V-M2 duty+duty | CONVERGED at `R2` | plain, 5 iterations | `R2` (§18.1) | — |
| P1 | `HOMOTOPY_STALLED` (`homotopy_stalled(BOUND_BLOCKED)`) | `2P×5 BOUND_BLOCKED` → `(2P,L,2P,2P,2P)` `LINE_SEARCH_FAILED` → `ACTIVE_SET_CYCLING` → edge 3 | A12's typed branch | — |

Without ADR 0044: M2, V-M1 `(RR, B)`, `(D, BR)` end `LINEAR_SOLVE_FAILED` from §18.2's `x⁰`, and M1 from the profile root.
A14's perturbations on M1: start ±5 K → identical `x⁰`; ratios ×0.5 → 1.1e-3, ×2 → 2.0e-5 (both edge 3). Over all ten
cases the ratio perturbations converge to `ref` (largest 0.16, V-M1 duty+duty ×0.5), except V-M2 duty+duty ×0.5 → `R2`.
Every deviation under 1/10 of a tolerance on the registered (unperturbed) path: no §10 amendment.

### 18.6 Assertions (replacing or adding to §10; tolerances as §10 unless stated)

| Id | Assertion | Expected | Tolerance |
| --- | --- | --- | --- |
| A05 | §18.2 on M1–M4 and the five admissible variants: `x⁰`, `ρ`, `φ`; every target row except the continued slots within its kind tolerance at `x⁰`; every stage `L, V > 0`; continued slot ids and `p⁰`; sweep count ≤ 500 (recorded, not asserted exactly: libm may move a last bit across architectures) | `ref.cases.*.bubble_point`, `.bubble_point_continued`; `ref.variants.*.*.bubble_point` | state tolerance; `p⁰` Q abs 1e-2 W, rates rel 1e-6; ids exact |
| A06 | M1–M4 through `solve_column`: outcome, signature 2P×n, products, `spec_values`, root | `ref.cases.*.target`, `.signature`, `.spec_values` | state tolerance; signature exact |
| A06b | Steps 4–5 from the registered profile endpoint `ref.cases.*.presolve` (WO-2's tests; M1's strict xfail flips under ADR 0044) | `ref.cases.*.target` | state tolerance |
| A07 | V-M1 ×4 and V-M2 `(D, BR)` through `solve_column` return `ref.cases.<case>.target`; V-M2 `(duty, duty)` returns `R2`. No cross-set `same_root` | `ref.cases.*.target`; `ref.variants.M2.duty+duty.second_root` | state tolerance |
| A13 | Edge 3 on `solve_column`'s own path (M1 after `ACTIVE_SET_CYCLING`, M2 after `LINEAR_SOLVE_FAILED`, no forcing): dyadic λ, `p⁰ = ref.cases.*.bubble_point_continued`, ratio rows untouched at every λ, λ = 1 identity equal to the target's, final `SAME` as a second run | — | `p⁰` as A05; rest exact |
| A13b | WO-2's forced edge 3 from `ref.cases.*.presolve` (unchanged, `p⁰ = ref.cases.*.continued`) | — | as §10 A13 |
| A14 | M1 from four perturbed endpoints: sweep start `T⁰ ± 5 K` (`x⁰` equal to A05's within 1e-8 K and the same final `state_sha256`); every stage ratio not held by a ratio specification ×0.5 and ×2 (`x⁰` differs; target `CONVERGED`, deviation within the state tolerance, `same_root = SAME` with A06's run) | as stated | as stated |
| A20 | ADR 0044's trigger. `eo_recovery_due` table: every D3 trigger unchanged; `LINEAR_SOLVE_FAILED` due iff the failed solve ran ≥ 2 attempts; every other non-trigger never due. On M2's path: `recovered_from.outcome == "LINEAR_SOLVE_FAILED"`, `len(recovered_from.attempts) ≥ 2`, recovery `CONVERGED`. The full gate shows no registered outcome outside S02 moved (§18.8 item 1) | as stated | exact |
| A21 | Multiplicity: V-M2 `(duty, duty)`'s returned root equals `R2`, differs from M2's root by more than 5 K in `T_c` and by more than 0.1 mol/s in `D`, and both are regular (generator `σ_min` claims) | `ref.variants.M2.duty+duty.second_root` | state tolerance |
| A22 | Typed construction failures, before any region solve: with `band_temperature` stubbed to answer `below` at one stage, M1 ends `initialization_failed(s02-bubble-point-v1, bubble_point_outside_domain)`; with `max_sweeps = 1`, `initialization_failed(s02-bubble-point-v1, sweeps_exhausted)`; neither calls `solve_region` (stubbed to raise) | as stated | exact |

A12 is unchanged; its measured branch is the typed one (`HOMOTOPY_STALLED`, attempt records naming `2P×5` and
`(2P,L,2P,2P,2P)`), recorded in WO-3's manifest; `(2P,L,2P,2P,2P)` breaks §4.3's block rule and feeds R-533.

### 18.7 Work orders

**WO-G (design lane `specifier`; generator, additive re-emission).** `s02_reference.py` gains §18.2 at 50 digits
(`rr_temperature(·, 0, P)` for the bubble temperature, its own `thomas`; stop at `max|ΔT| ≤ 1e-30 K`): keys
`cases.*.bubble_point` (per stage `T, l, v, Q, L, V`; `ρ`, `φ`, `T_c`, sweeps), `cases.*.bubble_point_continued`,
`variants.<case>.<set>.bubble_point` for the five admissible sets, and `variants.M2.duty+duty.second_root` (Newton in the
generator's formulation seeded with §18.1's six-digit `R2`; claims: root, regular `σ_min > 1e-4`, all 2P with `L, V > 1e-3`,
`|T_c − T_c(M2)| > 5 K`). Claims: every `x⁰` two-phase, the §18.2 identity (every non-continued row `< 1e-40`), the ±5 K start
reaches the same fixed point. Existing keys and values stay byte-identical; `claim_count` grows; `--check` passes; the new
SHA-256 goes into `tests/test_s02_column_wo1.py::REFERENCE_SHA256`.

**WO-2b (build lane, `opus-engineer`, ~100k).** Depends on ADR 0044's text (this commit) and, for A05/A07's `R2`/A13's
`p⁰`/A21/A22, on WO-G; everything else can start now.
1. `models/syn001/column_solve.py`: `bubble_point_endpoint(spec, provider, initial, *, profile_shift=0.0,
   ratio_scale=1.0, max_sweeps=500)` → `BubblePointEndpoint(state, rho, phi, sweeps, last_delta)` or `CascadeFailure` (§18.2);
   `solve_column` uses it in place of the Newton pre-solve; `opening=` is withdrawn, `profile_shift`/`ratio_scale` are the A14
   hooks. `PRESOLVE_ID = "s02-bubble-point-v1"`; `PRESOLVE_POLICY`, `presolve_rows`' use in the path and the TP closure
   variant go (keep `slots`/`continuation`). `ColumnSolution` drops `presolve`/`presolve_summary` for the §18.2 records.
2. ADR 0044's trigger: `orchestrator/recovery.py` `eo_recovery_due(outcome, budget, attempts)`; the three call sites
   (`executor.py:864`, `cascade_solve.py:691`, `column_solve.py:746`) pass `len(result.attempts)`; the stubs in
   `tests/test_s01_cascade_wo3.py:125` and `tests/test_s02_column_wo2.py:475,559` take the third argument (§18.8 item 1).
3. Tests: A05–A07, A06b, A13, A13b, A14, A20–A22 (§18.6); WO-2's strict xfails flip to plain passes or are deleted with their
   replacement named in the build log; the A05 profile-root tests stay as A06b's precondition.
4. Acceptance: `pytest tests/test_s02_* tests/test_s01_* tests/test_t04_* tests/test_t03_*` green; ruff/format/mypy clean;
   the full gate before merge (CLAUDE.md). Records the measured sweep counts and deviations in `docs/S02_DECISIONS.md`.

**WO-3** is unchanged except A14 (now §18.6's) and the manifest listing ADR 0044 and R-546 to R-549.

### 18.8 Open questions (each with a default)

1. *Fact, measured.* ADR 0044 moves no registered outcome outside S01/S02 (full suite on a patched snapshot; ADR 0044 C2).
   It moves five S01/S02 tests: A06 M1 from `x⁰` (strict xfail → pass, intended) and four forced-edge-3 tests whose
   `eo_recovery_due` stub takes two arguments (WO-2b gives the stubs the third). **Default** for any later mover: re-register
   in ADR 0044 C2, never relax.
2. *Needs a fact.* Bit-identity of `x⁰` across x86-64/aarch64 (libm `exp`/`log` in `K`): **Default:** A05 by tolerance,
   A15 within one machine; K05's identity comparison covers the target's final state as before.
3. *Needs a fact.* Convergence of the sweeps beyond SYN-001's registered columns (wide-boiling, many stages, non-ideal `K`):
   **Default:** not claimed (§18.9); `sweeps_exhausted` is the typed outcome; a later package with composition-dependent `K`
   needs its own easy endpoint.
4. *Needs the user's preference.* Root selection for `(duty, duty)` columns (§18.1 item 3). **Default:** no selection rule;
   register `R2`, disclose in §14. A later package may add a continuation-first path if a root-selection requirement appears.

### 18.9 What this does not establish

The sweeps' convergence is measured on the ten registered columns only; no contraction proof is offered. `x⁰` is not a
physical column (duties free, CMO stage ratios). ADR 0044 is `Proposed` until S02's manifest is `tested` and the reviewer has
read it. Uniqueness: §14, now with §18.1 item 3's counterexample.

### 18.10 Decisions

- DECISION: S02 easy endpoint → bubble-point sweeps at fixed CMO stage ratios (`s02-bubble-point-v1`, §18.2), replacing the
  Newton profile pre-solve. Alternative: an opening rule or more attempts for the Newton pre-solve (measured failing on M1).
  Reversible by: restoring §7.3 and the `s02-profile-presolve-v1` policy object (the profile root stays registered).
- DECISION: `LINEAR_SOLVE_FAILED` after a restart → edge-3 trigger (ADR 0044). Alternative: teach the contract the block rule
  (does not cover §4.2's end-stage singularity; model structure in ADR 0005 D4). Reversible by: withdrawing ADR 0044 (one
  predicate in `recovery.py`).
- DECISION: A07's comparison → state tolerance against `ref.target`; `same_root` only within one problem. Alternative:
  `same_root` across sets (T03 §8.3 says `NOT_COMPARABLE`). Reversible by: a T03 amendment defining cross-set comparison.
- DECISION: V-M2 `(duty, duty)` → register the second root `R2` and assert it. Alternative: drop the set (§15.3 forbids) or
  tune the endpoint until it returns M2's root (fragile). Reversible by: a root-selection rule in a later package.

## 19. Amendment 3 (2026-10-22, design lane `reviewer`): review rulings

Review `docs/reviews/S02-review.md`; register R-550 to R-554. Each item replaces the text it names. No row, kind, root
or registered value moves. The generator's re-emission (item 2) changes only `sweeps` at the generator's stop, the claim
list (appended) and the JSON SHA-256.

1. **ADR 0044 D1, narrowed (R-550).** §18.3's predicate and §18.6 A20 now read: *`LINEAR_SOLVE_FAILED` is a trigger iff the
   failed region solve ran two or more attempts **and its attempt 0 ended in a core globalization failure*** (solver
   outcome `LINE_SEARCH_FAILED`, `STAGNATION`, `BOUND_BLOCKED`, `PTC_STALLED`, or `BUDGET_EXHAUSTED` of a core budget).
   *Why:* §18.3's argument holds only when item 0's signature was left for a globalization reason. A restart after a
   `CONVERGED` attempt 0 is a physical correction; item 0's signature is known wrong there, and ADR 0010 D3's rank
   reason applies (`tests/test_t05b_dormancy.py:720` shows such a solve). Measured: attempt 0 is `BOUND_BLOCKED` on every
   S02 path that relies on the ADR, so no S02 result moves. A20's table gains `(CONVERGED, LINEAR_SOLVE_FAILED)` → not
   due and `(BOUND_BLOCKED, LINEAR_SOLVE_FAILED)` → due. ADR 0044 stays `Proposed` until the conditions in R-550 hold.
2. **§18.7 WO-G's stop is 1e-42 K, and the §18.2 identity claim is `< 1e-40` (Q-S02-WOG-1, R-551).** *Derivation:* the
   non-continued rows at the stop are `O(|ΔT_last|·∂s/∂T·L)`, about `1e-3·|ΔT_last|`. At the old 1e-30 K stop they are
   1.1e-33 to 8.4e-33 (measured, WO-G), so a `< 1e-40` claim was wrong for that stop. At 1e-42 K they are ≤ 8.1e-45
   (measured). 50 digits resolve `T` to about 4e-48 K, which leaves six orders of margin. The emitted 25-digit values do
   not change. The claim goes on all ten endpoints.
3. **A14's shift clause (Q-S02-WO2b-1, R-552)** replaces §18.6's: *sweep start `T⁰ ± 5 K`: `x⁰` within 1e-8 K of A05's,
   target `CONVERGED`, deviation within the state tolerance, `same_root = SAME` with A06's run.* The "same final
   `state_sha256`" clause and §18.5's "identical `x⁰`" are withdrawn. *Derivation:* the sweep is a contraction with
   last-sweep factor `c ≤ 0.54` (M1 0.18; WO-G). The stopped iterate therefore lies within `c/(1−c)·1e-9 K ≤ 1.2e-9 K`
   of the fixed point, on a side and at bits that depend on the start, so two starts agree within `2.4e-9 K < 1e-8 K`
   but not bit for bit. Newton from openings that differ in the last bits ends with different last bits. Bit identity
   holds only where it can be derived: the same input twice (A15, A13).
4. **Six variant sets (R-553).** §18.6 A05's and §18.7's "five admissible variants" read **six**: V-M1 ×4 and V-M2
   `(D, BR)`, `(duty, duty)`. The last is A07's `R2` endpoint, and A05 covers all ten endpoints.
5. **R-533 / Q-S02-3 (R-554).** §15.5's default is confirmed: S02 does not teach the contract the block rule. P1's
   measured outcome (`HOMOTOPY_STALLED`; attempt 1 `(2P, L, 2P, 2P, 2P)` breaks §4.3's rule) is the fact R-533 was
   waiting for, and it goes to S03. §14's "no phase-transition robustness" stands.
6. **§4.3 / §8 item 4.** Singular pairs are judged on **literally adjacent** equilibrium stages. A `ZERO_FLOW` stage in
   between pins `l_j = v_{j+2} = 0` and carries no circulation. "Ignoring `ZERO_FLOW`" applies only to reading the block
   rule, and dormancy stays unclaimed.

**Work orders:** `docs/reviews/S02-review.md`, "Build-lane fix work order", items 1–4. **Does not establish:** anything
beyond §14 and §18.9. The acceptance conditions in R-550 are not yet met.

## 20. Amendment 4 (2026-10-25, design lane `architect`, S08): pointer, effective when `wp/S08` merges

Normative text: `docs/derivations/S08-design.md`. ADR 0048 (Proposed). Register R-728 to R-731.

- **§7 gains step 7, the block re-entry.** After steps 1–6 end typed, or converge onto a near-trivial split, the column solves
  from block-conforming openings `V^a 2P^b L^c` built from its sources (S08-design §5.1–§5.7). Steps 1–6 are unchanged.
- **§8 gains item 6.** Every `TWO_PHASE` stage lies within 1e-4 K of its liquid's bubble and its vapour's dew temperature
  (S08-design §5.5).
- **A12, for P1, asserts the `CONVERGED` branch** (L×5, the closed form). The measured typed branch of §18.5 is asserted as
  `reentry.stage_a` (S08-design §6.1).
- **§4.3's finding** stands. The contract still does not learn the block rule.
