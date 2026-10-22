# S06 — column specifications by purity, recovery and stage temperature (SYN-001): rows, DOF, refusals, solve path and test specification

Design lane (`specifier`), 2026-10-22. Package **S06** (work item C11, `docs/CLOUD_WORK.md:37`; Frank's answer to
Q-S02-2, `docs/FRANK_QUESTIONS.md:11`), brief `docs/briefs/C11-column-inverse-specs.md`. Base: S02
(`docs/derivations/S02-spec.md` with Amendments 1–3, §17–§19), whose rulings this document does not reopen. Reference
generator `docs/derivations/scripts/s06_reference.py` (mpmath, 50 digits; `--check` re-derives 3110 claims and
byte-compares `s06_reference.json`; about 3 minutes on four cores). Decisions: `docs/C11_DECISIONS.md`;
register R-601 to R-607; Frank questions Q-S06-1, Q-S06-2.

## 0. Authority and scope

Normative for S06. It composes with S02 and everything S02 composes with (ADR 0001, 0005, 0008 D1–D3, 0010 D2–D3,
0012 D1, 0018, 0044 as narrowed by R-550). **It changes no frozen interface and no ADR**, and no ADR is written
(ADR 0046 stays free): every row it adds is of an existing row kind (`temperature`, `molar_flow`, `molar_flow_squared`);
its one new column is of the existing kind `molar_flow`; every inverse slot row is of ADR 0010 D2's written form
`variable − parameter`, so edge 3 continues it unchanged; `solve_region`, the phase contract, the policy `s01-default-v1`
(S02's target policy) and S02 §18.2's easy endpoint are called unchanged. §16 records the two formulations rejected
because each would have needed an ADR. Provider: SYN-001 only.

**What it establishes.** Three inverse end specifications on S02's column (§1); their rows (§2); the DOF and admissible
sets (§3); the stage band and the phase rule (§4); typed refusals before evaluation (§5); how S02's solve path carries
them (§6–§7), including the report when a target is not reached (§7.3) and the multiplicity-warning rule (§7.4);
acceptance (§8); eight registered cases, four matched sets, two unreachable sets and fifteen refusal probes (§9);
assertions S06.A01–A16 (§10); work orders (§12) and the manifest check list (§13).

**What it does not establish** is §14. Read it before citing anything here.

## 1. Kinds and conventions (normative)

S02 §1 holds unchanged. An end specification may now be one of three **inverse kinds**, each with one attribute:

| Kind | Attribute | Value | Specified quantity `q` at the end's product |
| --- | --- | --- | --- |
| `purity` | `component` c ∈ `spec.components` | x* ∈ (0, 1) | mole fraction of c: `n_c / P` |
| `recovery` | `component` c | r* ∈ (0, 1) | fraction of the inlets' c leaving in that product: `n_c / F_c` |
| `temperature` | `stage` s ∈ 1..N | T* (K) | `T_s` (with a total condenser, s = 1 means `T_c`) |

- **Products** (S02 §1.7). The condenser end's product is the distillate: `v_1` (partial or `none` condenser) or `d`
  (total). The reboiler end's product is the bottoms `l_N`. `n_c` is the product's component-c flow column and `P` its
  total column (`V_1`, `D` or `L_N`). A `none` end carries no specification (S02 §5 S2), so a stripper's top vapour or an
  absorber's bottom liquid is never specified directly.
- **Feed totals.** `F_c = Σ_k n_{k,c}` over the present inlets in `ColumnSpec.inlets()` order and `F = Σ_c F_c`, summed in
  binary64 in that order (the same values S02 §5 S5 uses).
- **The slot.** An inverse kind occupies its end's slot (S02 §2.1) exactly as a ratio, rate or duty does: the end's slot
  row is replaced by the inverse row of §2 and the end's duty is a free column fixed by its energy row. A `temperature`
  specification at either end may name any stage; the end only says which S02 slot it replaces.
- **Names.** `EndSpecification` gains `component: str | None = None` and `stage: int | None = None`. `END_KINDS` gains the
  three kinds at both ends. `NOT_OFFERED` becomes `("mole_fraction", "reflux_rate", "boilup_rate",
  "distillate_to_feed_ratio")`: `mole_fraction` is not an alias of `purity` (one id per row; DECISION 2).

## 2. Rows (normative)

All rows are division-free and every inverse slot row is `variable − parameter` (ADR 0010 D2's applicability), so the
continuation parameter, its `p⁰` and its λ-levels are computed by `orchestrator/homotopy.py` as they are for S02's
rate and duty slots.

| Kind | Rows replacing the end's slot row | Row kind | New column | Pinned parameters (id) |
| --- | --- | --- | --- | --- |
| `temperature` | `T_s − T*` | temperature | — | `T*` at the slot's parameter id |
| `recovery` | `n_c − ν*` | molar_flow | — | `ν* = fl(r*·F_c)` at the slot's parameter id |
| `purity` | slot `u − π*`; definition `F·n_c − u·P` | molar_flow; molar_flow_squared | `u` (molar_flow) | `π* = fl(x*·F)` at the slot's parameter id; `F` at `<U>.stage.<j>.purity_reference*` |

- **Ids.** Slot rows keep S02's id `<U>:stage:<j>:spec:<kind>` (j the end's stage). The purity column is
  `<U>.stage.<j>.purity_flow` and its definition row `<U>:stage:<j>:spec:purity_definition`. The slot parameter is named
  by S02's existing rule for a `variable − parameter` slot (`column_solve._parameter(variable)`), with `variable` = `T_s`
  (or `T_c`), `n_c`, or `u`.
- **Why `u`.** The purity is `n_c/P`, which no column holds. A `dimensionless` purity column would need a `dimensionless`
  slot row, which S02 §17 item 5 says needs its own ruling and, through K04's tolerance table, an ADR. The scaled purity
  `u = F·x_c` is a molar flow (`0 < u < F` at every state with positive flows, so the `molar_flow` lower bound 0 never
  binds), the definition row is bilinear like S01's equilibrium rows and of their kind, and the slot row is `u − π*`.
  Because `F` is a constant of the declaration, a path linear in `π` is linear in the purity.
- **Why `ν*`.** `F_c` is a sum of pinned inlet values, so `r* = n_c/F_c` is equivalent to `n_c = r*·F_c`. Writing the row
  against the inlet columns (`n_c − r*·Σ n_{k,c}`) would put several columns in the row and disqualify it from edge 3
  (`homotopy.continuation_parameter`). The record keeps `r*` (and `x*`) beside the pinned `ν*` (`π*`).
- **Derived parameters.** `F`, `ν*` and `π*` are formed once, in binary64, from the specification and the inlets'
  pinned values, so they are bit-identical across architectures (sums and one product). They enter
  `constants_sha256` like every pinned input.

## 3. DOF and admissible sets

**Count.** Columns = rows = S02 §3's count `+ n_purity`, the number of `purity` ends (each adds `u` and its definition
row). After fixing every inlet, every `P_j*` and every intermediate `Q_j*`, the column still has one degree of freedom
per non-`none` end, taken by its slot row (S02 §3).

**Admissible sets.** One specification per non-`none` end, from S02 §2.1's kinds plus §1's three, except the sets §5
refuses (S02's S3; I5's redundant sets; I6's infeasible splits). Each registered set is regular at its registered root
(generator `σ_min` claims, §9). **No admissibility claim is made for an unregistered set**, nor for a registered set at
another state; whether a set is regular depends on the state (that is what makes these specifications inverse).

## 4. The stage band and the phase rule

**Saturation temperatures (closed form).** SYN-001's `ln K_i(T, P) = ln(P_ref/P) + (L_i/R)(1/T_b,i − 1/T) +
V_i(P − P_ref)/(R T)` vanishes at

    T_sat,i(P) = (L_i − V_i (P − P_ref)) / (L_i / T_b,i + R ln(P_ref / P)),

and `∂ ln K_i/∂T = (L_i − V_i(P − P_ref))/(R T²) > 0` on the domain, so `K_i > 1 ⇔ T > T_sat,i(P)`.

**Ordering.** `ln K_A − ln K_B = (1/R)(L_A/T_b,A − L_B/T_b,B + (L_B − L_A)/T) = (1/R)(5000/T − 5.2083…)`, positive for
`T < 960 K`; `ln K_B − ln K_C = (1/R)(5000/T − 4.1666…)`, positive for `T < 1200 K` (the `V_i` are equal and cancel).
So `K_A > K_B > K_C` on the whole domain and `T_sat,A(P) < T_sat,B(P) < T_sat,C(P)` at every P.

**The band.** A two-phase stage holds every component present in some inlet (S02 §18.2's M-matrix argument, which holds
at any all-two-phase state with positive stage flows, roots included). Then `Σ_i x_i K_i = 1` with all `x_i > 0`
needs `K_lightest > 1 > K_heaviest` among the present components, so its temperature lies in the **open band**
`(T_sat,lightest(P_s*), T_sat,heaviest(P_s*))`. Every temperature inside is the bubble point of some composition, so
the band is exactly the set of temperatures a two-phase stage at `P_s*` can have. A total condenser's `T_c` is a bubble
temperature at `P_1*` and has the same band.

**Phase rule (S02 §4.2 extended).** At a regular root:
1. a partial end stage under `purity` or `recovery` is `TWO_PHASE`. *Derivation:* if it is `VAPOR` (condenser) or
   `LIQUID` (reboiler), its `T` and its free duty appear only in its energy row, so the Jacobian is singular (S02 §4.2's
   argument); if it emits no product of the other phase, the product is empty and the row is `−ν* ≠ 0` (recovery) or
   `0 = u·0` with `u` free (purity).
2. a partial end stage under a `temperature` specification of another stage is `TWO_PHASE`, by the same argument.
3. the stage a `temperature` specification names is `TWO_PHASE` **by scope** (DECISION 5): a single-phase specified
   stage (a superheating partial condenser, a reboiler that does not boil) can be regular, but S06 does not offer it.

## 5. Refusals (validation, before any evaluation)

S02 §5 holds, with S2 narrowed: a kind in the new `NOT_OFFERED` is `unsupported(specification:<kind>)`; the three inverse
kinds pass S2 at either end. S4 and S5 apply to direct kinds only. After S10, in this order, all `INVALID_SPECIFICATION`:

| Id | Condition | Code |
| --- | --- | --- |
| I1 | `purity`/`recovery` without a `component` in `spec.components`; `temperature` without a `stage` in 1..N; an attribute on a direct kind | `invalid_spec(<kind>:<end>)` |
| I2 | value not finite; `purity`/`recovery` value outside the open interval (0, 1) | `invalid_spec(<kind>:<end>)` |
| I3 | `purity`/`recovery` of a component with `F_c = 0` | `infeasible_spec(absent_component:<end>)` |
| I4 | `temperature` T* not strictly inside §4's band at `P_s*` over the components with `F_c > 0` | `infeasible_spec(temperature_outside_band:<s>)` |
| I5 | two `temperature` specifications naming one stage; or the specifications linear in the product split (below) linearly dependent | `invalid_spec(redundant_specification)` |
| I6 | no product split satisfies the specifications linear in it | `infeasible_spec(mass_balance)` |

**The product split (I5, I6).** Every S02 column has two outlets, top `t` and bottom `F − t` (component vectors), and at
any root whose stages are two-phase every present component leaves in both with positive flow (§4's M-matrix argument;
`d = (1 − φ)·v_2` with `0 < φ < 1`). Rates, purities and recoveries are linear in `t`:

| Specification | Row `a·t = b` |
| --- | --- |
| `distillate_rate` D* | `Σ t = D*` |
| `bottoms_rate` B* | `Σ t = F − B*` |
| condenser `purity` x* of c | `t_c − x*·Σ t = 0` |
| reboiler `purity` x* of c | `x*·Σ t − t_c = x*·F − F_c` |
| condenser `recovery` r* of c | `t_c = r*·F_c` |
| reboiler `recovery` r* of c | `t_c = (1 − r*)·F_c` |

I5 refuses when these rows have rank below their count (S02's S3 is the case `(D, B)`; others are recovery of one
component at both ends, and purity of one component at both ends with equal values). I6 refuses when no `t` with
`0 < t_c < F_c` for every present c (and `t_c = 0` for absent ones) satisfies them. Both are decided **exactly**, in
rational arithmetic on the binary64 inputs (`fractions.Fraction`): solve the rows for `t = t⁰ + N·s`; with no free
direction test the point, with one intersect the open intervals per coordinate, with two (one row) test
`Σ min(0, a_c F_c) < b < Σ max(0, a_c F_c)`. The test is necessary for a root, not sufficient: a split that passes may
still be unreachable for this column (finite stages, energy), and then §7.3 applies.

**Why these and not more.** I4 and I6 are the brief's "temperature outside the stage's band" and "purity above the
separation the column can reach" in the form that can be decided without solving: the band and the mass balance bound
every column with these inlets. A tighter bound (finite stages, total reflux) is not offered: it is not exact for
temperature-dependent `K` and would refuse targets some column could reach.

## 6. The easy endpoint (S02 §18.2, unchanged)

`s02-bubble-point-v1` runs as S02 §18.2 states. An inverse end takes the CMO stage ratio of step 1 (no override), and a
total condenser under an inverse condenser specification takes `φ⁰ = 1/2`, exactly as a duty end does. At `x⁰`:
- the purity column takes `u⁰ = fl(F·n_c⁰ / P⁰)` (§2's definition row then holds to one rounding);
- every continued slot's `p⁰` is its variable at `x⁰` (S02 §7.5): `T_s⁰`, `n_c⁰`, or `u⁰` for an inverse slot.

So `x⁰` is a root of `H(·, 0)` to the tolerance S02 §18.2 shows (generator claim, worst row `< 1e-30`, §9).

## 7. Solve path

### 7.1 Path

S02 §7 with §18 and §19, unchanged: validate (§5 here after S02's), initialize, construct `x⁰`, run the target from `x⁰`,
and on edge 3's triggers (ADR 0010 D3 with ADR 0044 as narrowed by R-550) run one recovery from the failed solve's item-0
opening. **The continued parameters are every replaced slot**, now including each inverse slot. The λ-path is
`p(λ) = p* + (1 − λ)(p⁰ − p*)` for every continued parameter at once; for `purity` and `recovery` this is linear in
`x` and `r` because `F` and `F_c` are constants. Ratio slots stay at their targets (S02 §7.5).

### 7.2 Measured reachability (generator, straight path, 16 equal λ-steps)

Every registered case J1–J8 and every matched set reaches λ = 1 with every stage two-phase, `L, V > 1e-3` mol/s, the
state in the domain and `0 < φ < 1` at each step, and its root is regular (§9). Two sets with a known regular root do
not, and are registered as typed failures (§7.3, A11) and non-claims (§14):

- **U1** (M2's column; condenser `temperature` of `T_c`, reboiler `recovery` of C, both at M2's root values). M2's root
  is a regular root of this set (`σ_min` 0.000300416), but the endpoint is ill-conditioned (`σ_min` 9.37613e-6 at `x⁰`:
  the endpoint's bottoms recovery of C is already 0.999557…, where the recovery row is nearly insensitive to every
  column) and the corrector fails at the first step of 16 and of 64 (`ref.unreached.U1.path_fails`).
- **U2** (M2's column; condenser `recovery` of A at M2's root value, reboiler `bottoms_rate` 0.55). M2's root is a
  regular root (`σ_min` 0.000775871), but on the straight path the total condenser's reflux fraction `φ` turns negative
  (measured at 30 digits on the original J2, recovery 0.97: `φ = 0.116` at λ = 1/16, `−0.112` at 2/16, back above 0
  only near 10/16). The implementation's `r ≥ 0` bound forbids that region, so the path is cut.

Candidates replaced before registration (scratch measurements): J2 was first (recovery A 0.97, B 0.55), which is U2's
behaviour, and is now (0.9, 0.7); J4 was first purities (0.85, 0.50), whose path failed at step 10 — it is
mass-balance infeasible (`t_A ≥ 0.85·0.4 > F_A`) and is registered as I6's probe; the matched set (recovery A,
recovery C) on M1 has `σ_min < 1e-4` at M1's root (bottoms recovery of C 0.9991) and was replaced by (recovery A,
recovery B).

### 7.3 A target that is not reached (rule: an unsupported capability is a result)

When the outcome is not `CONVERGED` and the set has an inverse specification, `ColumnSolution` carries, per inverse
end, an `UnreachedSpecification` with: `code = "inverse_specification_not_reached(<kind>:<end>)"`, `end`, `kind`, the
attribute, `target` (x*, r* or T* as given), `lambda_reached` and `value`:
- edge 3 ran: `lambda_reached` is the last accepted λ of its homotopy as the exact dyadic string ADR 0010 records
  (`"0"` when none beyond the start was accepted), and `value` is the specified quantity at that λ's state, computed
  in binary64 as `n_c / P` (purity), `n_c / F_c` (recovery) or `T_s` (temperature) from that state's columns;
- edge 3 did not run (a non-trigger outcome): `lambda_reached` and `value` are `None`.

The tuple is empty on a `CONVERGED` answer. It is a report, **never an infeasibility claim**: U1 has a regular root the
path does not reach. The outcome and `cause` are the region's, unchanged. Where the λ state comes from (the recovery's
partial checkpoint, ADR 0010 D2) is the engineer's to find and log; if it is not available the fields are `None` and
the build log says why.

### 7.4 Multiplicity warning

C8's rule is unchanged: `multiple_steady_states_possible(duty_only)` is emitted when every end's specification is a
`duty`. A set with an inverse specification is not duty-only and gets no warning. No new warning code (DECISION 8,
Q-S06-1): no registered S06 set shows a second root, and S06 makes no uniqueness claim for any set (§14).

### 7.5 Records

S02 §18.2's records, plus per inverse slot: kind, attribute, the user's value, the pinned parameter (`T*`, `ν*`, `π*`),
`F` or `F_c` as formed, `q⁰` and `p⁰`; and the `unreached` tuple.

## 8. Acceptance of a returned state

S02 §8 (with §17–§19), plus:
1. every §2 row within its kind tolerance (`u`'s definition row within `EQUILIBRIUM_TOLERANCE`, 9.3e-8 (mol/s)²);
2. every partial end stage under `purity`, `recovery`, or a `temperature` of another stage is `TWO_PHASE` (§4 items
   1–2); a failure is a defect (`report_defect`), as in S02;
3. the stage a `temperature` specification names is `TWO_PHASE`; a `CONVERGED` state where it is not is answered
   `CAPABILITY_UNAVAILABLE` `unsupported(temperature_specification_on_single_phase_stage:<s>)` (DECISION 5), not a defect
   and never a success;
4. at the returned state the specified quantity meets its target within the bound the rows imply:
   `|T_s − T*| ≤ 1e-6 K`; `|n_c/F_c − r*| ≤ τ_mf/F_c + 2⁻⁵²`; `|n_c/P − x*| ≤ (τ_mf + τ_eq/P)/F + 2⁻⁵²`, with
   `τ_mf = 3.1e-8` mol/s and `τ_eq = 9.3e-8` (mol/s)² (S01's kind tolerances).

## 9. Registered cases (values in `s06_reference.json`)

Bases are S02's (§9 there): feed `z = (0.3, 0.4, 0.3)` mol/s, `P_j* = 1.00 + 0.01(j − 1)` bar, adiabatic intermediate
stages. Components A, B, C are indices 0, 1, 2.

| Case | Base | Condenser | Reboiler | Why it is in the list | Sanity values at the root |
| --- | --- | --- | --- | --- | --- |
| J1 | M1 | purity A 0.85 | BR 1.5 | partial-condenser purity (the `u` column) with a ratio partner held at the endpoint | `T_1 = 330.535928…`, `T_N = 373.769517…` K; top 0.3364874… mol/s; `Q_1 = -21184.427…`, `Q_N = 31772.046…` W; `σ_min` 0.0316393 |
| J2 | M2 | recovery A 0.9 | B 0.7 | total-condenser recovery on `d_A`, continued together with a rate slot | `T_1 = 322.5365…`, `T_N = 371.132598…` K; top 0.3… mol/s; `Q_1 = -29668.62…`, `Q_N = 31324.017…` W; `σ_min` 0.00181862 |
| J3 | M1 | RR 2 | temperature stage 6, 368 K | an interior stage's temperature taking the reboiler's slot | `T_1 = 335.510772…`, `T_N = 375.694266…` K; top 0.3850481… mol/s; `Q_1 = -22233.333…`, `Q_N = 34350.269…` W; `σ_min` 0.0139298 |
| J4 | M1 | purity A 0.82 | purity C 0.46 | two inverse slots continued at once (dual composition) | `T_1 = 332.261763…`, `T_N = 373.974724…` K; top 0.3483964… mol/s; `Q_1 = -18538.263…`, `Q_N = 29507.242…` W; `σ_min` 0.00167549 |
| J5 | M3 | — | temperature stage 5, 395 K | a stripper whose reboiler duty is replaced by its own stage's temperature | `T_1 = 359.314565…`, `T_N = 395.0…` K; top 0.755417… mol/s; `Q_1 = 0.0…`, `Q_N = 28372.104…` W; `σ_min` 0.0544981 |
| J6 | M2 | temperature stage 1 (`T_c`), 330 K | B 0.55 | the total condenser's `T_c` as a specification | `T_1 = 330.0…`, `T_N = 377.395237…` K; top 0.45… mol/s; `Q_1 = -26021.567…`, `Q_N = 27628.235…` W; `σ_min` 0.00136069 |
| J7 | M4 | recovery A 0.9 | — | an absorber's (refluxed, no reboiler) distillate recovery | `T_1 = 356.518963…`, `T_N = 374.724145…` K; top 0.612904… mol/s; `Q_1 = -14843.542…`, `Q_N = 0.0…` W; `σ_min` 0.00790602 |
| J8 | M2 | RR 1.5 | recovery C 0.99 | a bottoms recovery near total, reached from the endpoint | `T_1 = 330.402211…`, `T_N = 378.50383…` K; top 0.4640406… mol/s; `Q_1 = -32518.692…`, `Q_N = 34136.886…` W; `σ_min` 0.000610732 |
| V-sets | M1 ×4 | (purity A, BR), (RR, temperature 6), (purity A, purity C), (recovery A, recovery B) | | **matched**: each inverse value is the S02 root's own (25 digits from `s02_reference.json`), so each set must return S02's registered root. A wrong index, sign or product in an inverse row moves the root by O(1) | deviation from S02's root ≤ 1.0e-23 (scaled) |
| U1 | M2 | temperature `T_c` at M2's | recovery C at M2's | §7.2: a regular root the path does not reach (ill-conditioned endpoint) | `ref.unreached.U1` |
| U2 | M2 | recovery A at M2's | B 0.55 | §7.2: a regular root the path does not reach (`φ < 0` on the path) | `ref.unreached.U2` |

Every flowing case is checked in the generator: the endpoint is S02 §18.2's and two-phase; `x⁰` is a root of `H(·, 0)`
(worst row `< 1e-30`); every path step and the root lie in the domain with `L, V > 1e-3` on every stage; the root is
regular (`σ_min > 1e-4`), closes component and energy balances (S02's bounds), satisfies S02's division-free rows below
1e-38, and meets its inverse targets and the implementation's row form below 1e-30.

**Refusal probes** (`ref.refusals`; each violates exactly one rule): I1 ×2 (component index 3; stage 8 of 7), I2 ×3
(purity 1; recovery 0; temperature NaN), I3 (feed (0.5, 0.5, 0), recovery of C), I4 ×2 (stage 6 at 405 K; stage 1 at
315 K, with the band at those pressures in `ref.band`), I5 ×3 (recovery of A at both ends; temperature of stage 4 at both
ends; purity of B 0.4 at both ends), I6 ×3 (purities (0.85, 0.50) — J4's first candidate; condenser purity A 0.9 with
reboiler recovery B 0.1; the dyadic feed (0.25, 0.5, 0.25) with D* = 0.125 and reboiler recovery A 0.5, which forces a
pure-A distillate exactly on the boundary) and one pass (the same with recovery `0.5 + 2⁻²⁰`, just inside). The generator
decides each probe with its own exact test and claims the expected code; it claims every J, V and U set passes I1–I6.
For U1 and U2 it claims the regular root, the straight path's failure in 16 and in 64 steps, and records the step and
the reason (`newton`: the corrector failed; `state`: its root left the domain, the two-phase region or `0 < φ < 1`).

## 10. Assertions

`ref` = `s06_reference.json`; `s02ref` = `s02_reference.json`. **State tolerance** is S02 §10's (flows
`1e-6·|ref| + 3.1e-7` mol/s, T 1e-4 K, Q 1e-2 W, ratios rel 1e-6), plus `u` as a flow.
- *Above the floor:* the `newton_refined` promise is `τ_kind`, 10× under these tolerances (ADR 0018 D2); S02 measured
  deviations ≤ 8.5e-3 of a tolerance on its path (S02 §18.5). The derived parameters `ν*`, `π*` differ from the
  generator's exact products by ≤ 1 ulp, which moves the root by O(1e-16) relative.
- *Below the smallest error worth catching:* the matched V-sets turn every index, sign or product error in an inverse
  row into an O(1) root shift (J-cases' roots differ from S02's by kelvins, §9); a dropped Poynting term moves T by
  1e-3 K (S02).
- *Needs a fact:* WO-2 records the maximum measured deviation over J1–J8 and the V-sets. Above 1/10 of a tolerance,
  this section is amended (S02 §10's rule).

| Id | Assertion | Expected | Tolerance |
| --- | --- | --- | --- |
| A01 | Columns = rows for J1–J8 and the V-sets; `u` and its definition row present exactly on `purity` ends; row ids unique | `ref.cases.*.dof`, `ref.matched.*.dof` | exact |
| A02 | Every `ref.refusals` probe gives its code before any evaluation (provider and `solve_region` stubbed to raise); `mole_fraction` at either end is `unsupported(specification:mole_fraction)`; every J, V and U set passes validation | `ref.refusals.*.expected` | exact |
| A03 | The band: the implementation's `T_sat,i(P)` at `P = 1.00 … 1.06` bar | `ref.band` | 1e-9 K abs (floor: a few roundings of T ≈ 400 K, ≤ 1e-12 K) |
| A04 | Rows at the dyadic trial state `ref.trial_rows.state` (feed (0.25, 0.5, 0.25), F = 1, on M1's structure; two declarations: condenser purity of B 0.75 with reboiler recovery of C 0.5, and the same condenser with reboiler temperature of stage 6 at 360.5 K; both pass §5; other columns arbitrary): the purity definition, purity slot, recovery slot and temperature slot residuals | `ref.trial_rows` (−3/64, −1/4, 1/16, 3/4) | exact (floor 0: dyadic operands, generator-claimed short). A permuted component gives one of `…_other_components` (claimed distinct), a wrong stage `temperature_slot_other_stage`, a flipped sign the negative |
| A05 | §6 on J1–J8 and the V-sets: `x⁰` (S02's endpoint at the CMO end ratio), `u⁰`, every continued slot id and `p⁰` (inverse slots: `T_s⁰`, `n_c⁰`, `u⁰`), every non-continued target row within its kind tolerance at `x⁰` | `ref.cases.*.bubble_point`, `.continued`; `ref.matched.*.continued` | state tolerance; `p⁰`: T 1e-4 K, flows rel 1e-6; ids exact |
| A06 | J1–J8 through `solve_column`: `CONVERGED`, all stages `TWO_PHASE`, root, products, `spec_values`, and §8 item 4 | `ref.cases.*.target`, `.spec_values`, `.inverse_values` | state tolerance; §8.4's bounds |
| A07 | The V-sets through `solve_column` return S02's registered root | `s02ref.cases.M1.target` | state tolerance |
| A08 | Overall component and energy closure, and §8 items 1–4, at every converged J and V answer | 0; pass | `n_rows·τ_kind`; as §8 |
| A09 | Compiled Jacobian vs central differences at `x⁰` and the root of J1 (`u`, definition row), J2 (recovery on `d`), J6 (`T_c` slot); step `h_j = 1e-6·max(D_x(j), |x_j|)` (R-516) | agree | 1e-6 scaled. Floor needs a fact: WO-2 measures it for the new rows and records it; it must be ≤ 1e-8 (S02's A10 rule) |
| A10 | Edge 3 carries the inverse slots: forced from `x⁰` on J1, J4 and J6 (S02 A13b's harness), the continuation's `parameter_ids` are exactly the replaced slots including each inverse slot's parameter, `p⁰` equals A05's, every λ < 1 level differs from the target only at those ids, λ dyadic, and the recovery is `CONVERGED` at `ref.cases.*.target` | as stated | `p⁰` as A05; root state tolerance; rest exact |
| A11 | U1 and U2 through `solve_column`, each: **either** `CONVERGED` at `s02ref.cases.M2.target` passing §8, **or** a non-`CONVERGED` outcome whose `unreached` holds one entry per inverse end with its code, and, where `lambda_reached` is not `None`, `value` equal **bit for bit** to the quantity recomputed by §7.3's formula from the state of that λ. Never an unaccepted `CONVERGED`, never an empty `unreached` on a failure. The branch taken is recorded | as stated | exact; root state tolerance |
| A12 | Warnings: `column_warnings` is `()` for J1–J8, the V-sets, U1 and U2; S02/C8's duty-only cases still carry `multiple_steady_states_possible(duty_only)` | as stated | exact |
| A13 | Records (§7.5): for J1, J2, J3 the recorded `x*`/`r*`/`T*`, `ν*`/`π*` equal `fl(r*·F_c)`/`fl(x*·F)` with `F`, `F_c` summed in `inlets()` order; `q⁰`, `p⁰` as A05 | as stated | exact for the binary64 formation; `q⁰`, `p⁰` as A05 |
| A14 | Phase scope (§8 item 3): J5 with its target state forced so that stage 5 is single-phase at a `CONVERGED` result (a stubbed region result) is answered `unsupported(temperature_specification_on_single_phase_stage:5)`; J1 with stage 1 `VAPOR` in a stubbed `CONVERGED` result is a defect | as stated | exact |
| A15 | J1 and J6 solved twice: identical `state_sha256` and records | — | exact |
| A16 | S02's A01–A22 (with §17–§19) and S01's suite still pass on `wp/C11` | S02, S01 suites | as registered |

## 11. Generator

`s06_reference.py` imports nothing from `openflowsheet`. It imports `s02_reference.py` (itself independent of `src/`)
for SYN-001's closed forms, the generator's column formulation (8 unknowns per equilibrium stage, quotient equilibrium
rows, the total condenser reduced to `(φ, T_c, Q_c)`), S02 §6's initializer, S02 §18.2's endpoint (stop 1e-42 K), its
Newton (complex-step derivatives, tolerance 1e-40) and its state and closure checks. What it adds differs from the
implementation's formulation: inverse slot rows in **quotient form** (`n_c/P − x*`, `n_c/F_c − r*`, `(T_s − T*)/100`),
no `u` column, the straight path in 16 equal λ-steps, and an exact rational refusal test of its own. It shares with the
implementation SYN-001, S02's endpoint definition and §5's rules, and nothing else. Each J, V and U set runs in its own
worker process; results and claims are assembled in a fixed order, so the JSON is byte-reproducible. Every number in §9
and §10 is a generator claim or an emitted value; `--check` refuses to emit when a claim fails.

## 12. Work orders (`opus-engineer`, about 120k context each)

**WO-1: specification, rows, refusals** (`models/syn001/column.py`).
- `EndSpecification.component`/`.stage`; `END_KINDS`, `NOT_OFFERED` as §1; I1–I6 after S10 (the split test exact, in
  `fractions.Fraction`; the band from §4's closed form in binary64).
- Declared rows of §2: the inverse slot rows, `u` and its definition row, the pinned `F`, `ν*`, `π*`, `T*`; `slot_column`
  for inverse kinds (`T_s`/`T_c`, `n_c`, `u`); `spec_values` gains the three quantities; the count of §3.
- Closes A01–A04, A12, A13 (formation part). Logs every naming choice in `docs/C11_DECISIONS.md`.

**WO-2: solve path, acceptance, report** (`models/syn001/column_solve.py`).
- `slots`/`continuation`: inverse slots replaced and continued (`CONTINUED_KIND` gains `temperature → T`,
  `recovery → N`, `purity → U`); `_initial_state` sets `u⁰`; §8 items 1–4; §7.3's `UnreachedSpecification`; §7.5's records.
- Closes A05–A11, A13–A16; records the deviation measurement, A09's floor and A11's branch; runs `s06_reference.py
  --check`; writes `evidence/S06/<commit>/manifest.json` (template fields filled with actual values only).

## 13. Evidence manifest check list

- `status: tested` requires a passing test for each of A01–A16, citing its id.
- `s06_reference.py --check` passes at the manifest commit (3110 claims; JSON byte-identical), and
  `s02_reference.py --check` still passes.
- `ruff check`, `ruff format --check` and mypy clean; `scripts/gate.sh` before merge.
- The deviation measurement, A09's floor and A11's branch are recorded with their commit.
- §14 listed verbatim as limitations. `reviewed` is set only by the `reviewer`.

## 14. What this does not establish

- **Synthetic data only.** SYN-001 is ideal, three-component, azeotrope-free, with composition-independent `K`. Nothing
  here validates an inverse specification against real chemistry, plant data or another simulator. Real-chemistry
  columns need a liquid-capable property method (out of scope).
- **No independent column reference.** J1–J8 are matched against this generator, which shares SYN-001, S02's endpoint
  and §5's rules with the implementation; the V-sets are matched against S02's registered M1 root, the same lineage. The
  independent references of X31 are S03's.
- **No feasibility decision beyond §5.** I4 and I6 are necessary conditions. A target that passes them may be
  unreachable for this column (finite stages, energy), and an unreached target (§7.3) is not evidence of infeasibility:
  U1 and U2 have regular roots the path from S02's endpoint does not reach.
- **No convergence claim beyond the registered paths.** S02's endpoint is ill-conditioned when it already holds the
  specified component almost entirely in one product (U1), and a straight path from it can cross an unphysical region
  (U2: negative reflux at a total condenser whose `φ` is free). Only J1–J8's and the V-sets' straight paths are
  measured; Q-S06-2.
- **No uniqueness or root-selection claim** for any set, inverse or not; no multiplicity study of inverse sets (§7.4).
- **No admissibility claim** for an unregistered set or a registered set at another state; no single-phase specified
  stage (§4 item 3).
- **No flowsheet binding.** `F`, `F_c`, `ν*` and `π*` are formed from the column's own pinned inlets; a column bound
  into a flowsheet (MODEL_BUILDERS, out of scope) whose feed is a solved stream needs a ruling on these rows first.
- **No rate-based, inside-out or sensitivity results**; no side draws, pump-arounds or efficiencies (S02 §14).

## 15. Open questions (each with a default)

1. *Needs a fact.* Does `solve_column` reach J1–J8 and the V-sets (adaptive λ, ADR 0044's trigger)? **Default:** yes, as
   the generator's straight path does; a set that does not is recorded, §9 is amended and the set stays registered with
   A11's two-branch form (S02 §15.3's rule; never dropped).
2. *Needs a fact.* A11's branch on U1 and U2. **Default:** the typed branch (the generator's straight path fails); the
   record says which. A `CONVERGED` branch is a success of the implementation's adaptive path, recorded, not a defect.
3. *Needs a fact.* A09's floor for the new rows. **Default:** ≤ 1e-8 (same magnitudes as S02's rows); else amend §10 with
   the measured floor.
4. *Needs a fact.* Is the recovery's partial checkpoint state reachable from `ColumnSolution` (§7.3)? **Default:** yes
   (ADR 0010 D2 records it); else the fields are `None`, the build log says why, and A11 asserts the code only.
5. *Needs the user's preference.* Multiplicity warning for inverse sets (Q-S06-1). **Default:** none.
6. *Needs the user's preference.* A second easy endpoint for near-total targets (Q-S06-2). **Default:** not in S06.
7. *Needs a fact (later package).* Flowsheet binding of `F`, `F_c`, `ν*`, `π*` (§14). **Default:** S06's standalone column
   only; the binding package rules first.

## 16. Decisions and findings

DECISION lines: `docs/C11_DECISIONS.md`; register R-601 to R-607.

**Finding (not acted on).** Two cleaner formulations of the purity row each need an ADR: (a) a `dimensionless` purity
column with a `dimensionless` slot row `ξ − x*` — a row of that kind needs its own ruling and, through K04's tolerance
table, an ADR (S02 §17 item 5; R-043's warning about `check_policy_sha256`); (b) the ratio row `n_c − x*·P` (S02's
reflux-ratio form) continued from `p⁰ = n_c⁰/P⁰` — ADR 0010 D2 admits only `variable − parameter` rows and
`homotopy.level_values` reads `p⁰` from one column. S06 needs neither: §2's `u` gives the same path within the existing
rules. If a later package wants ratio-form continuation generally, that is an ADR 0010 amendment for the design lane.

## 17. Amendment 1 (2026-10-23, design lane `reviewer`): review rulings

Review `docs/reviews/S06-review.md`; questions Q-S06-WO1-1 and Q-S06-WO2-1 (`docs/C11_DECISIONS.md`); register R-608 to
R-610. Each item replaces or adds to the text it names. No frozen interface, row, row kind, tolerance, policy or identity
moves, so no ADR is written. Frank's answers stand: Q-S06-1 (no multiplicity warning, §7.4) and Q-S06-2 (no second
endpoint; the high-purity endpoint failure stays a typed result and a §14 item).

### 17.1 The I3 probe (Q-S06-WO1-1; R-608) — replaces §9's "I3 (feed (0.5, 0.5, 0), recovery of C)"

The registered probe was above its bubble point at M1's feed state (Σ z_i K_i ≈ 1.10 at 340 K, 1.04 bar), so S01's R5
answered first. **The probe becomes feed (0, 0.5, 0.5) mol/s with reboiler `recovery` of A (index 0) 0.9**, condenser
`reflux_ratio` 2, at M1's feed state (340 K, 1.04 bar, declared `LIQUID`); expected code unchanged,
`infeasible_spec(absent_component:reboiler)`. *Why it is admissible, without a computation:* with `K_A > K_B > K_C > 0`
(§4), `0.5 K_B + 0.5 K_C < 0.3 K_A + 0.4 K_B + 0.3 K_C` because `0.3 K_A > 0.1 K_B + 0.2 K_C`; the right side is M1's
own feed, which is an admissible liquid at that state (S02's registered M1). It violates I3 only: RR passes S4; A is
declared, 0.9 ∈ (0, 1).

Rule for every refusal probe: **it is at its base's inlet state and passes S01's R5 and S02's S1–S10 there**; the
generator does not model R5, so A02's test is where that is checked (a probe that R5 answers fails A02).

Work order (build lane): change the probe's row in `s06_reference.py`, re-emit `s06_reference.json`, record `--check`'s
new claim count and the JSON's SHA-256 in `docs/C11_DECISIONS.md`; remove the strict xfail on `I3-absent`; delete the
unregistered 320 K companion test or keep it as unregistered.

### 17.2 §10 "needs a fact" answered (Q-S06-WO2-1; R-609)

Measured on `solve_column`'s path at `32aac25` (worst column / its state tolerance): **J8 0.182** (`stage.6.m.A`; next
`stage.5.m.A` 0.164); V-reflux_ratio+temperature 0.017; V-purity+purity 0.014; J4 0.010; every other set < 0.01. J8 is
above §10's 1/10 margin. *Reason:* conditioning, not a defect. J8's root has the smallest registered `σ_min`
(0.000610732; J1–J7 ≥ 0.00136), and its A flows on stages 5–6 are of order 1e-4 mol/s, where the state tolerance is its
absolute part 3.1e-7 mol/s. The `newton_refined` promise `τ_kind` bounds residuals; a residual within `τ_kind` moves the
state by up to about `τ_kind/σ_min` along the near-singular direction, so "10× under the tolerance" (§10, *Above the
floor*) holds for well-conditioned roots and is not implied at J8's. **The state tolerance is unchanged** and A06 passes
(≤ 1).

The manifest's deviation check becomes: every set ≤ 1/10, **except J8 ≤ 1/4** (a ceiling about 1.4× the measured value,
for cross-architecture differences in Newton's stopping point). A set above its ceiling amends §10 again (S02 §10's rule).

### 17.3 §8 item 3 is decided after the defect clauses (R-610) — replaces §8 item 3's second sentence

A `CONVERGED` state is first checked against S02 §8 (with its §17–§19) and items 1, 2 and 4 here. **A failure of any of
them is a defect (`AcceptanceDefectError`), whatever the regime of the specified stage.** Only a state with no defect
whose `temperature`-specified stage is not `TWO_PHASE` is answered `CAPABILITY_UNAVAILABLE`
`unsupported(temperature_specification_on_single_phase_stage:<s>)`. Never a success either way. A genuine single-phase
root passes every defect clause (item 2 skips the specified end stage; S01 §8 asks admissibility of a single-phase stage,
not two phases), so the order changes only the answer on a state that is both defective and out of scope. That state is
an implementation fault, and reporting it as a scope limit hides it.

A14 changes with it: the unsupported probe stubs `acceptance_failures` to `()` (or uses a state that passes it); a third
probe — J5's stubbed non-root state with stage 5 `LIQUID` — must raise `AcceptanceDefectError`.

### 17.4 Assertions strengthened (clauses added; no id, value or tolerance moves)

- **A04** gains: on M2's structure (total condenser) with condenser `purity` of A 0.75 and reboiler `bottoms_rate` 0.55, at
  a state whose columns are distinct dyadic values, the purity definition row equals `F·d_A − u·D` exactly (computed in
  the test from the dyadic operands) and differs from `F·v_1,A − u·V_1` and `F·r_A − u·Σ r`. A purity at a total
  condenser is offered (§1) and no J or V case declares one.
- **A05** gains: each V-set's `x⁰` is within the state tolerance of its twin's `ref.cases.<twin>.bubble_point`
  (V-(purity A, BR) ↔ J1, V-(RR, temperature 6) ↔ J3, V-(purity A, purity C) and V-(recovery A, recovery B) ↔ J4,
  `u` excluded for the last), because §6's endpoint reads no inverse target. Measured at `6053c73`: the V-sets' `x⁰`
  equal their twins' bit for bit on every common column; the worst deviation from the twin's reference is 1.8e-5 of a tolerance.
- **A11** gains: at the λ state, each continued slot's column equals `p(λ) = p* + (1 − λ)(p⁰ − p*)` within its slot
  row's kind tolerance. The test's rebuild of the λ state mirrors `lambda_state` and cannot catch a wrong source by
  itself. Measured at `6053c73`: U1 0.0 and U2 1.1e-16 at every continued slot.
