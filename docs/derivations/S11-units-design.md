# S11 units design (second pass): the thermal units on the new bases

**Status:** design lane (`architect`), 2026-10-27. Branch `wp/S11` at `3cbd3bd3`. This addendum to
`docs/derivations/S11-design.md` (cited as "first pass §n") stands alone; the brief is not needed to implement it.
**Brief:** `docs/briefs/S11-units-design.md`.
**Decided by Frank (2026-10-27), answering first pass §7 Q2 and Q3:** "Include in S11" for both. His directive is
"as few limitations as possible".
**Records:** ADR 0051 (`docs/adr/0051-s11-thermal-units-on-the-new-bases.md`, Proposed); register R-813…R-821;
first pass §9 (dated amendment).
**Normative for:**
- pure-fluid stream states and how their closures land on the saturation line (ADR 0051);
- the `thermal.*` unit family;
- the γ–φ faces of the five K02/T05 units on Wilson;
- the provider `wilson-ig-v2`;
- the admission rows, verifier forms, zero-flow rules, envelope and W27 rows that go with them;
- tracks C and D, and the integration WO I1b.

---

## 0. The decisions in one screen

1. **Pure-fluid regimes are declared, not discovered.** A connection's `phase_capability` on `iapws95-v1` or
   `coolprop-heos-v1` is the stream's regime:
   - `liquid`: single-phase liquid;
   - `vapor`: single-phase vapour, or supercritical by the provider's label;
   - `vapor_liquid`: **saturated** — T = T_sat(P), with a carried vapour flow, 0 ≤ β ≤ 1 inclusive.

   A closure that lands in another regime is refused `phase_regime_mismatch(<S>)`, and the message names the
   declaration to use. (§4.1, E1)
2. **A saturated stream is `nTP-v1` plus a carried split.**
   - In the EO, its producer authors the columns `<S>.sat.V` and `<S>.sat.L` and the rows T − T_sat(P) = 0 and
     V + L − n = 0. Its enthalpy flow is V·h^V_sat(P) + L·h^L_sat(P). No row ever evaluates a phase property at a
     (T, P) off the saturation line.
   - In the causal traversal it travels as `SaturatedStreamState`, a `StreamState` subclass with `vapor_fraction`.
   - This amends ADR 0001 D2.5 and extends ADR 0012 D7. (§4.1, E2)
3. **Closures land on the line by construction.** A saturated outlet's V is fixed by the unit's energy row (PH), by
   its isentropic block through the work row (PS), or by a vapour-fraction row. (§4.1–§4.4)
4. **Saturated pure-fluid streams are produced only by `thermal.*` units.** `syn001.feed_source` and
   `syn001.stream_splitter` refuse to produce one; `syn001.product_sink` may read one. (§4.1, E3)
5. **A new basis-generic family, `thermal.*`** (`heater`, `valve`, `mixer`, `flash`, `pump`, `compressor`,
   `turbine`), lives in new modules. All seven are admitted on both pure-fluid bases; `compressor` and `turbine`
   also on Wilson, vapour only. (§4.4, E4)
6. **Isentropic machines have no entropy rows and no internal columns.** An isentropic-enthalpy block feeds the work
   row. It solves the PS relation inside itself for a single-phase isentropic state, or in closed form for a
   saturated one. (§4.3, E5)
7. **Wilson: the five K02/T05 units are admitted** — `syn001.tp_heater`, `tp_flash`, `ph_flash`, `valve` and
   `adiabatic_mixer`.
   - Their EO blocks dispatch on the equilibrium form inside `tp_state`'s shared helpers (S10-C's γ–φ blocks).
   - Their manifest's provider fields are taken from the bound provider.
   - SYN-001's code path is textually unchanged. (§4.5, E6)
8. **`wilson-ig-v2` is a new provider module.**
   - It forwards every `wilson-ig-v1` answer bit for bit and adds `s` in closed form from S10's own potential.
   - It replaces v1 as the provider that the Wilson record source selects (WO-D5).
   - v1 stays S10's and S10-C's library provider, and its bytes do not change.
   - The pump stays refused on Wilson, because the method's liquid has no volume. (§4.6, E7)
9. **The verifier forms** (§4.8):
   - a saturated pure stream is read through its carried split and gets a `.saturation` check;
   - a machine's isentropic state is solved by the verifier's own bisection;
   - Wilson lifted splits get a γ–φ form: a fresh TP flash, the provider's `stability()`, and degeneracy routing.
10. **Zero flow.** Single-phase outlets whose temperature is set by the energy row get dormancy rules. Saturated
    outlets are regular at dormancy without one. (§4.9)
11. **W27 v3** gains seven model functions and the `wilson-ig-v2` provider row; snapshot S4 is generated at I1b.
    The envelope gains seven members and the L-TH and L-GP rows. (§4.10)
12. **Identity.** No existing `thermo/` module, schema, `Protocol`, quantity kind, check category or tolerance
    changes, and no registered result moves. (§4.12)

---

## 1. Problem and scope

**Build:**
- the thermal units on `iapws95-v1` and `coolprop-heos-v1`: heater/cooler, pump, compressor, turbine, valve and
  mixer, plus a separator drum (the natural consumer of wet streams);
- the two-phase pure-fluid stream state those units need;
- γ–φ EO faces on Wilson for the K02/T05 heater, TP flash, PH flash, valve and mixer;
- the reachable machines on Wilson: compressor and turbine, by a provider version 2 that adds `s`.

**In scope:**
- ADR 0051;
- `models/thermal/` (kernel, blocks, state, units), `application/thermal_binding.py`, `verify/thermal.py`;
- edits to `models/syn001/{tp_state,heater,flash,ph_flash,valve,mixer,equilibrium_form}.py`;
- `thermo/wilson_ig_v2.py`, `verify/gamma_phi_units.py`;
- the dormancy rules, admission rows, envelope rows and W27 v3 rows that go with them;
- the reference scripts and cases;
- tracks C and D, I1b, and the minimal amendments to the first pass (§5.4).

**Out of scope:**
- NRTL/UNIQUAC/LLE, Helmholtz mixtures, S07b cryogenic liquids, the methanol+ethanol refit, `pr-lib-v1`, reactors,
  side draws and pump-arounds, the GUI;
- regime discovery for pure-fluid streams (Q17);
- wet pure-fluid feeds, and saturated streams through routing models (Q21);
- a γ–φ two-phase PS closure (Wilson machines stay single-phase vapour);
- `syn001.heat_exchanger`, `syn001.component_separator` and `syn001.liquid_pump` on Wilson (Q20; the pump is not
  representable, §4.6);
- any edit to an existing `thermo/` module.

---

## 2. Constraints and invariants

### 2.1 Conventions

- First pass §2.1 applies: SI; Q > 0 into a unit; W > 0 into a unit (ADR 0001 D4.1), so a turbine's W < 0.
- A pure-fluid basis has C = 1 component, `c`. The vapour fraction is β = V/n, defined only for n > 0.
- Row ids are `row_id(<U>, <family>[, <suffix>])`. Row orientation follows ADR 0008 D3.3: inflow − outflow.
- τ_T, τ_flow and τ_E are the registered temperature, molar-flow and energy tolerances (K04/T05b: 1e-6 K,
  3.1e-8 mol/s, 1.01e-3 W).

### 2.2 The fact that decides the pure-fluid design

Both Helmholtz providers answer a phase only on its stable side, or inside a band ε_σ = 1e-6 in ln(P/P_sat(T)) where
both phases are answered. Beyond the band a metastable phase is refused `phase_not_stable`, and the TP flash is
refused `tp_flash_degenerate` inside the band (S05 §4.2; `thermo/iapws95.py` `_rule`; the same in
`thermo/coolprop_heos.py`). In temperature the band is about 3e-5 K wide at 1 atm for water.

Both providers answer `Tsat` with dT_sat/dP and `Psat` with dP_sat/dT, Maxwell-consistent with their own h and s
(the saturated densities come from a Newton solve on Maxwell's conditions). They declare h, s, v, Z, c_p and
`lnphi_<c>` with first derivatives in T and P, offer a TP flash only, and refuse a dormant state `dormant_state`.

### 2.3 What must stay bit-exact, and what may move

**Bit-exact:**
- every first-pass §2.2 item;
- every SYN-001, C1, T02–T05b, S08 and S10-C registered result;
- every `wilson-ig-v1` answer; `wilson-ig-v2`'s h, `lnphi_<c>`, flash and stability, which equal v1's;
- the SYN-001 manifests of the five edited K02/T05 modules, except `implementation_artifact.artifact_hash`;
- W27 v1 and v2 outputs.

**May move, by design:**
- the count and sample tests of §8.3;
- `MODEL_BASES`, `MODEL_BUILDERS`, `MODEL_SIGNATURES` and `MODEL_CHECKS` (seven models added, Wilson rows added);
- the Wilson entry of `SELECTABLE_BASES` (provider `wilson-ig-v2` from D5; the count stays 127);
- `LIBRARY_ONLY_PROVIDERS` (gains `wilson-ig-v1` back);
- the envelope and the support matrix;
- W27 v3 data, which is not yet registered (S4 is generated at I1b).

**By tolerance:** thermal and Wilson flowsheet results across architectures, worst relative deviation recorded
(G8).

### 2.4 Frozen interfaces

- No schema, `Protocol`, quantity kind, check category or `KIND_TOLERANCE` entry changes.
- `StreamState` is unchanged; `SaturatedStreamState` is a subclass in the models layer and is never passed to a
  provider.
- `UnitEvaluation` gains nothing beyond B2's `owned`.
- No target path is added. One parameter name is added to the code table `_PARAMETER_KINDS`:
  `outlet_vapor_fraction` → `dimensionless`.

### 2.5 Parallel and device contract

The first pass §2.4 applies. `coolprop-heos-v1` is `not_thread_safe`, so a binding and a verifier never share an
instance.

---

## 3. Decisions and rejected alternatives

**E1 (R-814). Declared regimes for pure-fluid streams.**

*Rejected: lifted splits with discovered regimes, the SYN-001 way.* The region switches a regime by pinning flows and
dropping rows over **one** compiled function. Every phase block is therefore evaluated at every iterate, in every
regime. A Helmholtz provider refuses a phase beyond ε_σ, and a Newton step taken in a two-phase regime leaves the
saturation line at second order: about 0.1 K for a 10 % pressure step at 1 bar, against a band of 3e-5 K. So the
evaluations fail and Newton crawls. Only two things fix this:
- per-regime block forms: a new split form in `region.py`, `splits.py`, `execution.py` (whose signature-unit
  criterion is a `molar_flow_squared` row) and `verify/` — T05b-scale work, on track B's files;
- a synthetic metastable extension, which is either kinked at the two-phase root or a C¹ function that is not the
  provider's.

Discovery is deferred (Q17).

*Rejected: the K-form row v·L − K·l·V for C = 1.* It equals V·L·(1 − K), which degenerates at either phase boundary,
and it needs both phases at (T, P).

**E2 (R-814). The carried split.**

*Rejected:*
- *a `vapor_fraction` field on `StreamState`.* That is the frozen request type of the provider `Protocol`, and every
  cache and provider would see it.
- *a new state definition (n, H, P).* The whole stack is `nTP-v1`.
- *reading a wet inlet by its (n, T, P)*, the way ADR 0012 D9(3) tolerates for SYN-001's measure-zero case. On pure
  fluids every wet-stream reader would start with its latent heat misplaced, and every PH-type reader would start in
  the wrong regime.

**E3 (R-815). Only `thermal.*` units produce saturated pure-fluid streams.**

*Rejected: teaching the splitter.* Its EO face authors no split, so it would need saturated rows: an amendment to
A2's face, for a rare case. A feed cannot state a vapour fraction through its pins (Q21).

**E4 (R-816). A new family in new modules.**

*Rejected:*
- *generalizing the `syn001.*` units for pure fluids.* Their two-phase form is the lifted split (E1).
- *per-basis namesake families* (`pure.*`, `wilson.*`): the N×M duplication the first pass rejected (its D3).

**E5 (R-817). The isentropic-enthalpy block.**

*Rejected:*
- *a T_s column with an entropy row.* There is no entropy row kind. An enthalpy-scaled row would need a second
  dormancy label for T_s, and the dormancy registry (one label per outlet port) cannot express one.
- *a PS flash in the provider.* The provider modules are frozen, and S05/S07 offer a TP flash only.

The block's inner solve starts from a fixed rule (T_I) and converges to S05's 4ε rule, so it is a function of its
inputs, as the providers' own density roots are. The column black box (first pass D6) was rejected because its value
depended on a warm start.

**E6 (R-818). Wilson by dispatch in the shared helpers.**

*Rejected:*
- *new `wilson.*` model ids.* `SPLIT_RULES`, `DORMANCY_RULES`, `MODEL_CHECKS` and `PH_TYPE_ENERGY_ROWS` are keyed by
  model id, so they would need duplicates in track B's files.
- *a subclass per basis.* Each subclass duplicates a `contribute`.

The first pass's reason for refusing these units on Wilson ("their EO faces read `lnK` and `h_<c>`") is removed by
the dispatch. Its physical-assumption argument (the SYN-001 pump) does not apply to these five units, whose rows are
balances, a specification and equilibrium.

**E7 (R-819). `wilson-ig-v2`.**

*Rejected:*
- *refusing the compressor and turbine.* Frank's directive.
- *computing the entropy in the unit layer from the records.* That bypasses the provider and is a second
  implementation of the method.
- *a v2 with a liquid volume and a Poynting factor.* It changes v1's `lnphi` and h, so it is a different method that
  needs S10's validation again.
- *a second Wilson basis.* It needs two record sources for one file.

**E8 (R-820). Verifier independence.**

- For a pure saturated stream, (n, T, P) does not determine the split (ADR 0012 D7), so the carried split is judged.
- A machine is judged by the verifier's own PS bisection, not by the unit's Newton.
- A Wilson split is judged by the provider's TPD stability search and a fresh TP flash. Neither is the region's
  admissibility code.

**E9 (R-821). Registration in one integration WO after I1 (I1b),** so that tracks C and D stay on disjoint files and
do not change A's or B's WOs.

---

## 4. The design

### 4.1 Pure-fluid stream forms (ADR 0051 D1–D5)

| Declared `phase_capability` | Form | Columns of S | Enthalpy flow Ḣ_S (block, output) | Admissible at a solution |
| --- | --- | --- | --- | --- |
| `liquid` | single-phase LIQUID | n_S, T_S, P_S | n·h^L(T, P): `PF_<S>_liquid.H` | `adm(T, P, LIQUID)` |
| `vapor` | single-phase VAPOR | n_S, T_S, P_S | n·h^V(T, P): `PF_<S>_vapor.H` | `adm(T, P, VAPOR)` |
| `vapor_liquid` | saturated | n_S, T_S, P_S, `<S>.sat.V`, `<S>.sat.L` | V·h^V_sat(P) + L·h^L_sat(P): `PFsat_<S>.H` | \|T − T_sat(P)\| ≤ τ_T; V ≥ 0; L ≥ 0; \|V + L − n\| ≤ τ_flow |

`adm` is the first pass's §4.6 pure-fluid rule, applied unchanged by the evaluate and by the verifier:
- LIQUID iff T < T_c and P ≥ P_sat(T)·(1 − 1e-9);
- VAPOR iff T ≥ T_c or P ≤ P_sat(T)·(1 + 1e-9);
- where `Psat` is refused (T in (T_σ,max, T_c)), the provider's TP-flash label decides.

The unit layer implements it in `models/thermal/kernel.py` `declared_admissible`. A test asserts agreement with the
verifier's copy on a 200-point grid.

**What a saturated outlet's producer authors.** For an outlet port `p` carrying S, unit U writes:
- the columns `<S>.sat.V` and `<S>.sat.L` (kind `molar_flow`);
- the row `row_id(U, "sat-T", p)`: T_S − `PFsat_<S>.Tsat` = 0 (kind `temperature`);
- the row `row_id(U, "sat-split", p)`: V + L − n_S = 0 (kind `molar_flow`);
- the block `PFsat_<S>` with inputs (`<S>.sat.V`, `<S>.sat.L`, P_S) and outputs (`Tsat`, `H`).

One more of U's rows fixes V: its energy row, its work row through the isentropic block, a vapour-fraction row, or
a fixed-β row (`thermal.flash`).

**A reader of S** re-declares `PFsat_<S>` with identical inputs (`assemble` deduplicates by block id) and sums
`PFsat_<S>.H`. A reader of a single-phase S re-declares `PF_<S>_<phase>` with inputs (n_S, T_S, P_S).

**The causal traversal.** `models/thermal/state.py`:

```
@dataclass(frozen=True)
class SaturatedStreamState(StreamState):
    vapor_fraction: float   # β; finite, 0 <= β <= 1; 0.0 for a dormant stream (a label)
```

- A thermal unit returns this class for every saturated outlet, with `temperature` bit-equal to the kernel's
  T_sat(P). It returns `owned = {"<S>.sat.V": β·n, "<S>.sat.L": n − β·n}`, computed in that order, so that
  `sat-split` holds exactly at the EO start.
- A thermal reader of a `vapor_liquid` inlet requires this class, or a dormant plain `StreamState` (a torn guess),
  which reads as β = 0.
- Anything else is the defect `carried_split_missing(<S>)`.
- No unit passes a `SaturatedStreamState` to a provider; the kernel takes floats.

**Producers.** On a pure-fluid basis, a `syn001.feed_source` or `syn001.stream_splitter` outlet declared
`vapor_liquid` is refused at bind with `Unbound("unsupported", "phase_capability_unsupported(<S>)")` and the hint "a
saturated pure-fluid stream is produced by a thermal.* unit (ADR 0051 D4); declare liquid or vapor".
`syn001.product_sink` reads saturated streams; it evaluates nothing.

**Trial states.** A pure-fluid block turns these provider refusals into `DomainError`, which the compiled boundary
reports as `invalid_trial_state`:
- `phase_not_stable`, `near_critical`, `no_saturation`;
- `out_of_domain` (as today).

Any other refusal is a `RuntimeError` (a defect). Rationale: a trial outside the declared regime's region is outside
that regime's domain (blueprint §7.7).

**Supercritical labels.** At P ≥ p_c the provider labels a state LIQUID below T_c and VAPOR above (S05 §4.2, S07).
A declared phase follows the label (L-TH-5).

### 4.2 The pure-fluid kernel (`models/thermal/kernel.py`; procedural; floats in, typed results out)

- `saturation(provider, P) -> Sat | Failure`:
  - T_s = `Tsat(P)`, then h and s of both phases at (T_s, P), each answered on its own root because T_s lies inside
    the band;
  - a refusal of `Tsat` is `no_saturation`.
- `ph_closure(provider, n, P, H) -> Closure(regime, T, beta, route) | Failure`, with n > 0 and h* = H/n:
  1. If `saturation(P)` answers:
     - h^L_sat ≤ h* ≤ h^V_sat: regime SATURATED, T = T_s, β = (h* − h^L_sat)/(h^V_sat − h^L_sat), route
       `saturated`;
     - h* < h^L_sat: regime LIQUID, solving h^L(T, P) = h* on [T_min, T_s];
     - h* > h^V_sat: regime VAPOR, solving on [T_s, T_max].
  2. Otherwise (P outside the saturation range): regime by label, solving n·h(T, P, label(T, P)) = H on
     [T_min, T_max]. A bracket that crosses the near-critical box is refused `near_critical`.
  - The solve is a safeguarded Newton on T (slope n·∂h/∂T > 0), with a bisection step whenever Newton leaves the
    bracket.
  - Convergence is S05's: relative step ≤ 4ε, or the residual floor.
  - At most 100 iterations; past that, `not_converged`. A target outside the bracket is `out_of_domain`.
- `ps_closure(provider, n, P, S)`: the same, with s; the slope ∂s/∂T = c_p/T > 0.
- `declared_state(provider, n, P, target, form, prop) -> Outlet | Mismatch` — the evaluate's routine, with
  prop ∈ {h, s}:
  - *Single-phase form φ:* solve prop^φ(T, P) = target/n on φ's side of T_s, the band edge included. Accept iff a
    root exists and `adm(T, P, φ)` holds.
  - *Saturated form:* accept iff `ph_closure`/`ps_closure` gives SATURATED.
  - Otherwise return `phase_regime_mismatch(<S>)`. The first line is the code. The second line is
    `declared <cap>, closure <regime>[ beta=<β:.6g>]; declare <cap'>`, with cap' = `liquid`, `vapor` or
    `vapor_liquid` for LIQUID, VAPOR and SATURATED.
- `isentropic_state(...)`: §4.3's formulas, procedurally (the evaluate and the traversal start).
- Typed codes (each the first line of a refusal message): `phase_regime_mismatch`, `no_saturation`,
  `isentropic_state_two_phase`, `inadmissible_phase(<port>, <PHASE>)`, `carried_split_missing`, `not_converged`,
  `out_of_domain`, `near_critical`.
  *Erratum 2026-10-27 (R-839):* `isentropic_state_single_phase` is added, for an isentropic state that is
  single-phase where another form was declared: a saturated form with β_s outside [0, 1], or a root outside the
  saturation range whose label is not the declared phase. See `docs/reviews/S11-rulings.md` item 10.

### 4.3 Blocks (`models/thermal/blocks.py`; every block is a `PropertyBlock` with analytic or implicit derivatives)

**`PhaseFlowBlock(provider, component, phase, context, block_id)`** — pure fluid only.
- Inputs (n, T, P); output `H` = n·h^φ(T, P).
- It evaluates the provider at `StreamState((1.0,), T, P)`: h is intensive for a pure fluid, so this is exact and
  avoids `dormant_state`.
- Jacobian: [h, n·∂h/∂T, n·∂h/∂P].
- **Dormant rule (n == 0.0 exactly):** the value is 0.0 and the T and P entries are 0.0. The n entry is h^φ at the
  first point the provider answers, in order:
  1. (T, P);
  2. (T_sat(P), P) on φ's root, if P is in the saturation range;
  3. otherwise `DomainError`.

  This is a convention that fixes Newton's direction off dormancy, never a converged value; S10-C's γ–φ blocks set
  the precedent.

**`SaturatedFlowBlock(provider, component, context, block_id)`**
- Inputs (V, L, P); outputs `Tsat` = T_sat(P) and `H` = V·h^V_s + L·h^L_s, with h^φ_s = h^φ(T_sat(P), P).
- Jacobian:
  - ∂Tsat/∂P = dT_sat/dP (the provider's);
  - ∂H/∂V = h^V_s, ∂H/∂L = h^L_s;
  - ∂H/∂P = V·(dh^V_s/dP) + L·(dh^L_s/dP), with dh^φ_s/dP = (∂h^φ/∂T)·dT_sat/dP + ∂h^φ/∂P, all at (T_sat, P).
- Valid at any P in the saturation range, whatever the iterate's T.

**`IsentropicEnthalpyBlock`** (output `Hs`; `<U>` is the machine; block id `PFs_<U>`). Five variants; the builder
picks one at bind (§4.4):

| Variant | Inputs | s* (target) | Isentropic state at P_O | Hs |
| --- | --- | --- | --- | --- |
| `pure-single/single` | n, T_I, P_I, P_O | s^{φI}(T_I, P_I) | T_s solves s^{φs}(T_s, P_O) = s* | n·h^{φs}(T_s, P_O) |
| `pure-sat/single` | n, P_I, P_O | s^{φI}_sat(P_I), φI = L (pump) or V | as above | as above |
| `pure-single/sat` | n, T_I, P_I, P_O | s^V(T_I, P_I) | β_s = (s* − s^L_sat(P_O))/(s^V_sat(P_O) − s^L_sat(P_O)) | n·[h^L_sat + β_s(h^V_sat − h^L_sat)](P_O) |
| `pure-sat/sat` | n, P_I, P_O | s^V_sat(P_I) | as above | as above |
| `additive-vapour` (Wilson) | n_1…n_C, T_I, P_I, P_O | Σ_j n_j s_j(T_I, P_I) | T_s solves Σ_j n_j [s_j(T_s, P_O) − s_j(T_I, P_I)] = 0 | Σ_j n_j h_j(T_s, P_O) |

Notes on the variants:
- s_j and h_j are the provider's VAPOR s and h at the pure composition e_j (no mixing term; v2 answers s at e_j with
  derivatives in T and P only).
- **The additive premise.** At fixed composition, the phase entropy differs from Σ x_j s_j(T, P) by a function of
  composition alone. This holds for a pure fluid trivially and for an ideal-gas vapour (ideal mixing). The block is
  admitted by identity only for `(wilson-ig-v2, WILSON-IG-ref-v1 | S10-VER-ref-v1)`, phase VAPOR.
- **Inner solve** (single-phase variants): safeguarded Newton on T_s from T_I, bracketed by the domain and by T_s's
  side of T_sat(P_O) when it exists. Convergence by S05's rule, at most 100 iterations.
  - No root on the declared side means `DomainError` at a trial. At a solution this cannot happen, because the
    evaluate refuses first with `isentropic_state_two_phase`.
  - In a saturated variant, β_s ∉ [0, 1] is likewise `DomainError`.
- **Derivatives** (implicit function theorem; F = residual of the inner equation):
  - ∂T_s/∂x = −(∂F/∂x)/(∂F/∂T_s) for x ∈ {T_I, P_I, P_O, n_j}; then ∂Hs/∂x = (∂Hs/∂T_s)·∂T_s/∂x + ∂Hs/∂x|_{T_s}.
  - For C = 1, ∂T_s/∂n = 0 exactly.
  - Saturated variants: β_s and its P_I, P_O derivatives come from the saturated s and h and their dP derivatives
    (as in `SaturatedFlowBlock`); ∂Hs/∂n = the intensive bracket.
  - Test identities (A49): ∂Hs/∂T_I = n·T_s·c_p,I/T_I and ∂Hs/∂P_O = n·v_s for `pure-single/single`.
- **Dormant rule:** value 0.0. For C = 1 the derivatives are evaluated with n = 1 and the n entry is the intensive
  value. For `additive-vapour` at n_tot = 0, T_s and the derivatives are evaluated at the probe n = (1, …, 1) and the
  T, P entries are scaled by 0.0 (S10-C's convention).

**Block ids** satisfy `tp_state._BLOCK_TOKEN`; an unusable stream or unit id is refused, never sanitized. Wilson
streams in machines use `tp_state.single_phase_enthalpy` (§4.5), so a syn001 unit and a machine reading the same
stream share one block.

### 4.4 The `thermal.*` units

**Common to all seven:**
- **Modules:** `models/thermal/{heater,valve,mixer,flash,machines}.py`. `machines.py` holds one class configured as
  pump, compressor or turbine.
- **Model ids:** `thermal.heater`, `thermal.valve`, `thermal.mixer`, `thermal.flash`, `thermal.pump`,
  `thermal.compressor`, `thermal.turbine`. The family name is Q16.
- **Construction:** `unit_id`, `provider`, `components`, `context`, each port's form (LIQUID, VAPOR or SATURATED,
  from the binder), and the specification values.
- **Provider admission by identity** (`models/thermal/__init__.py`; refused at construction with
  `SpecificationError`):
  - `PURE` = {(`iapws95-v1`, `IAPWS95-ref-v1`), (`coolprop-heos-v1`, `COOLPROP-DEF-ref-v1`)};
  - `ADDITIVE_VAPOUR` = {(`wilson-ig-v2`, `WILSON-IG-ref-v1`), (`wilson-ig-v2`, `S10-VER-ref-v1`)}, for
    compressor and turbine only.
- **Manifests:**
  - `property_provider`, `reference_convention` and `validity.domain` (T, P, components) come from `describe()`;
  - `execution_class` is `native_equation`; `status` is `tested` (IMPLEMENTED_VERSION);
  - the residual derivative method is `analytic` for heater, valve, mixer and flash, and `implicit` for the
    machines (both are in `EO_CAPABLE_METHODS`);
  - `artifact_hash` is the module's `file_sha256`.
- **Parameter ids** are formed as the K02/T05 units form theirs. The duty and work columns are
  `models.duty_id(U)` and `models.syn001.pump.work_id(U)`.
- **Row kinds:** mole rows `molar_flow`; pressure rows `pressure`; T rows `temperature`; energy and duty rows
  `heat_rate` (heater, valve, mixer, flash); work and energy rows of the machines take the kinds of the SYN-001
  pump's `PUMP-work` and `PUMP-energy`.
- **Evaluate:** a dormant inlet gives a dormant outlet labelled with the inlet's T (and the outlet P), zero duty or
  work, `ZERO_FLOW` (ADR 0001 D3.4); its form class is `SaturatedStreamState(β = 0.0)` for a saturated port.
  `phase_signature` for a saturated outlet is LIQUID if β = 0.0, VAPOR if β = 1.0, and TWO_PHASE otherwise.

**Inlet enthalpy in the evaluate:**
- single-phase: `adm` must hold, else `inadmissible_phase(inlet, <PHASE>)`; Ḣ = n·h^φ(T, P);
- saturated: |T − T_sat(P)| ≤ τ_T, else `carried_split_inconsistent(<S>)`; Ḣ = n·[h^L_sat + β(h^V_sat − h^L_sat)].

**Bind-time refusals** (`application/thermal_binding.py`). Each is `Unbound("unsupported",
"specification_unsupported(<U>.<what>)")` with the hint shown:

| Model | Combination refused | Hint |
| --- | --- | --- |
| heater | `outlet.T` with outlet `vapor_liquid` | a pure-fluid outlet at a specified temperature is single-phase; specify `outlet_vapor_fraction` or the duty |
| heater | `outlet_vapor_fraction` with outlet `liquid`/`vapor` | declare the outlet `vapor_liquid` |
| heater | not exactly one of `outlet.T`, `duty.Q`, `outlet_vapor_fraction` | the binder's existing missing or conflict codes |
| heater | `outlet_vapor_fraction` ∉ [0, 1] | — |
| flash | a product not declared `vapor_liquid` | a drum's products are saturated (ADR 0051 D4) |
| pump | inlet `vapor`; outlet not `liquid` | — |
| compressor | inlet `liquid`; outlet not `vapor` | — |
| turbine | inlet `liquid`; outlet `liquid` | — |
| turbine | `isentropic_phase = vapor` with outlet `vapor_liquid` | inconsistent: a wet outlet has a wetter isentropic state |
| compressor, turbine on Wilson | any port not `vapor` | no γ–φ two-phase PS closure (L-GP-2) |

**`thermal.heater`** (heater or cooler).
- Ports: `inlet` (1), `outlet` (1), `duty` (energy, inlet).
- Exactly one specification:
  - mode **T**: pin `outlet.T`;
  - mode **duty**: pin `duty.Q`;
  - mode **quality**: parameter `outlet_vapor_fraction` = β_spec.
- Parameter `pressure_drop` ΔP, default 0.
- Rows:
  - `TH-mole:<c>`: n_I,c − n_O,c = 0;
  - `TH-pressure`: P_O − P_I + ΔP = 0;
  - `TH-energy`: Q + Ḣ_I − Ḣ_O = 0;
  - mode T, `TH-T`: T_O − T_spec = 0;
  - mode duty, `TH-duty`: Q − Q_spec = 0;
  - mode quality, `TH-quality`: V_O − β_spec·n_O = 0 (kind `molar_flow`);
  - saturated outlet: `sat-T:outlet`, `sat-split:outlet`.
- Owned: Q; plus `<O>.sat.V` and `<O>.sat.L` for a saturated outlet.
- Evaluate:
  - mode T: the outlet is (n, T_spec, P_I − ΔP); `adm` must hold, else `phase_regime_mismatch(<O>)`; then
    Q = n·h_O − Ḣ_I;
  - mode duty: `declared_state(…, Ḣ_I + Q_spec, form, h)`;
  - mode quality: T = T_sat(P_O), Ḣ_O = n·[h^L_sat + β_spec·Δh_sat], Q = Ḣ_O − Ḣ_I.
- DOF (C = 1): T mode, 4 rows (mole, pressure, energy, T) and 4 unknowns (Q, n_O, T_O, P_O). Quality mode adds V
  and L as unknowns and quality, sat-T and sat-split as rows (6 = 6). Duty mode with a saturated outlet: 6 = 6.

**`thermal.valve`.**
- Ports: `inlet`, `outlet`. Pin `outlet.P`, as `syn001.valve`.
- Rows: `TV-mole:<c>`; `TV-P`: P_O − P_spec = 0; `TV-energy`: Ḣ_I − Ḣ_O = 0; the saturated rows if the outlet is
  saturated.
- Evaluate: `declared_state(n, P_spec, Ḣ_I, form, h)`.
- Bound: P_spec ≤ P_I, else the SYN-001 valve's code.

**`thermal.mixer`.**
- Ports: `inlet` (many), `outlet` (1); adiabatic.
- Rows:
  - `TM-mole:<c>`: Σ_k n_k,c − n_O,c = 0;
  - `TM-pressure:<k>`: P_k − P_O = 0 for every inlet k, as `MIX-pressure`;
  - `TM-energy`: Σ_k Ḣ_k − Ḣ_O = 0;
  - the saturated rows if the outlet is saturated.
- Evaluate: dormant inlets are absent; unequal flowing pressures are refused as the K02 mixer refuses them;
  `declared_state(Σn, P_1, ΣḢ, form, h)`.

**`thermal.flash`** (separator drum).
- Ports: `inlet`, `vapor`, `liquid`, `duty`. Pin `duty.Q`, and parameter `pressure_drop` ΔP, as `syn001.ph_flash`.
- Both products are saturated.
- Rows:
  - `TF-mole:<c>`: n_I − n_Vp − n_Lp = 0;
  - `TF-pressure:vapor` and `TF-pressure:liquid`: P_out − P_I + ΔP = 0;
  - `TF-duty`: Q − Q_spec = 0;
  - `TF-energy`: Q + Ḣ_I − Ḣ_Vp − Ḣ_Lp = 0;
  - `sat-T:vapor`, `sat-T:liquid`, `sat-split:vapor`, `sat-split:liquid`;
  - `sat-fix:vapor`: L_Vp = 0 and `sat-fix:liquid`: V_Lp = 0 (kind `molar_flow`).
- DOF: 11 = 11.
- Evaluate: `ph_closure(n, P_I − ΔP, Ḣ_I + Q_spec)` must give SATURATED, else `phase_regime_mismatch(<inlet>)` with
  "thermal.flash needs a two-phase state at the drum pressure". The vapour product is (β·n, T_s, P,
  `vapor_fraction` = 1.0) with owned V = β·n, L = 0.0; the liquid product is (n − β·n, T_s, P, 0.0) with owned
  V = 0.0, L = n − β·n. β = 0 or 1 gives a dormant product (ADR 0001 D3.4).

**`thermal.pump`, `thermal.compressor`, `thermal.turbine`** (`machines.py`).
- Ports: `inlet`, `outlet`, `work` (energy, inlet). Pin `outlet.P`; parameter `efficiency` η ∈ (0, 1].
- Turbine only: a choice `isentropic_phase` ∈ {`vapor`, `vapor_liquid`}, defaulting to the outlet's form, given as
  `syn001.heat_exchanger` takes `specification`.
  *Erratum 2026-10-27 (R-839):* the choice cannot be stated in a revision, whose parameters are numeric. The form
  follows the outlet, and a parameter `isentropic_phase` is `parameter_unsupported`. Direct construction can state it.
  See `docs/reviews/S11-rulings.md` item 10; OQ-1 to Frank.
- Rows (family F = `TPU` for the pump, `TCO` for the compressor, `TTU` for the turbine):
  - `F-mole:<c>`: n_I,c − n_O,c = 0;
  - `F-P`: P_O − P_spec = 0;
  - `F-work`: pump and compressor η·W − (`PFs_<U>.Hs` − Ḣ_I) = 0, by `models.rows.work_row`; turbine
    W − η·(`PFs_<U>.Hs` − Ḣ_I) = 0, by `models/thermal/rows.py` `expansion_work_row`;
  - `F-energy`: W + Ḣ_I − Ḣ_O = 0;
  - the saturated rows for a saturated turbine outlet.
- Isentropic variant (§4.3):

| Machine | Inlet single-phase | Inlet saturated (β must be the stated value) | Isentropic state |
| --- | --- | --- | --- |
| pump | `pure-single/single` (φI = φs = L) | `pure-sat/single` (β = 0) | LIQUID |
| compressor | `pure-single/single` (V, V); Wilson: `additive-vapour` | `pure-sat/single` (β = 1) | VAPOR |
| turbine | `pure-single/single` or `pure-single/sat` | `pure-sat/single` or `pure-sat/sat` (β = 1) | by `isentropic_phase` |

- Evaluate:
  1. Check the inlet β exactly (`inadmissible_phase(inlet, LIQUID|VAPOR)` otherwise).
  2. Compute the isentropic state; on the wrong side, `isentropic_state_two_phase(<U>)`.
  3. W = n(h_s − h_I)/η (pump, compressor) or η·n(h_s − h_I) (turbine).
  4. Outlet: `declared_state(n, P_spec, Ḣ_I + W, form, h)`; on Wilson the vapour h-inversion, then the provider's
     `stability()` on the outlet, which must be STABLE_WITHIN_TESTED_SCOPE, else `phase_regime_mismatch`.
- Bounds: the pump and compressor need P_spec ≥ P_I and give W ≥ 0; the turbine needs P_spec ≤ P_I and gives W ≤ 0.
  Refusal codes follow the SYN-001 pump's bound codes.
- DOF (C = 1, single-phase outlet): 4 = 4, with unknowns W, n_O, T_O, P_O. A saturated turbine outlet adds V, L and
  two rows.

### 4.5 Wilson: γ–φ faces for the K02/T05 units (track D)

**Shared helpers in `models/syn001/tp_state.py`.** Each helper gets a branch at its top:
`if composition_dependent(provider): <γ–φ>`. The SYN-001 code below the branch is left byte-for-byte.
- `single_phase_enthalpy`: `MixtureEnthalpyFlowBlock(provider, components, phase, context, block_id=
  enthalpy_block_id(stream, phase))`. Same feeding ids; keys `<block>.H`.
- `lift_two_phase_stream`:
  - the K-block is `GammaPhiLnKBlock(..., block_id=lnk_block_id(stream))` with inputs (`*liquid_ids`, T, P), and
    its outputs `lnK_<c>` are the keys the equilibrium rows already read;
  - the vapour and liquid blocks are mixture blocks;
  - row ids, kinds and orders are unchanged.
- `stream_enthalpy_terms(phase=None)`: mixture blocks on the producer's split variables.
- **New `equilibrium_block(provider, components, context, *, block_id, temperature, pressure, liquid)
  -> (block, inputs)`:** `GammaPhiLnKBlock` with (`*liquid`, T, P) for a composition-dependent form, else
  `LnKBlock` with (T, P).

**Unit modules** (each edit isolated; the SYN-001 statements unchanged):
- In heater, flash, ph_flash, valve and mixer: three optional fields, `property_provider: str = PROVIDER_ID`,
  `reference_convention: str = REFERENCE_CONVENTION` and `domain = {"T": (T_MIN, T_MAX), "P": (P_MIN, P_MAX)}`, as
  A2 gives the routing models.
  - `manifest()`, every `UnitEvaluation(provider_id=…, reference_convention=…)` and every `__post_init__` range
    check read them.
  - `validity.domain.components` is the instance's components.
- `flash.py` and `ph_flash.py`: the `LnKBlock(...)` construction and its `block_inputs` entry become
  `equilibrium_block(...)` with the liquid product's flow ids.
- `flash.py` `_inlet_enthalpy`: its own `EnthalpyFlowBlock` copy gains the same branch, with mixture blocks.
- `mixer.py` `_close_energy` and `_liquid_enthalpy`: a branch on `gamma_phi.enthalpy_and_slope`.
- Evaluate paths need no other change: `tp_state`, `ph_state` (band-first) and `single_phase_admissible` already
  dispatch (S10-C).
- `equilibrium_form.ADMITTED` gains (`wilson-ig-v2`, `WILSON-IG-ref-v1`) and (`wilson-ig-v2`, `S10-VER-ref-v1`) →
  `FORM_GAMMA_PHI_IG` (WO-D4). `_SCOPE`'s text is updated to name v2 only if the S10-C identity line still
  reproduces; otherwise it is left and the choice logged.

**Binding (WO-D2, `application/revision_binding.py`).** The five builders pass
`property_provider=d.provider_id, reference_convention=d.reference_convention, domain={"T": d.domain["T"],
"P": d.domain["P"]}`, with d = `provider.describe()`, when `view.basis.provider_id != "syn001"`. Otherwise they pass
nothing, so the SYN-001 construction is identical.

The region's paths for these units already dispatch: `_kernel` (the provider's TP flash), `_ph_closure`
(`_split_enthalpy` → `enthalpy_flow`; `ph_state`), `_gamma_phi_admissible`, and `saturation_band`. WO-D6's first
commit is a spike that proves it (Q18).

### 4.6 `wilson-ig-v2` (`thermo/wilson_ig_v2.py`; new provider id; v1 untouched)

**Notation.** θ = T/1000 K; θ₀ = 0.29815; P₀ = 101 325 Pa; R = 8.31446261815324 J/(mol K). From each record: b₀…b₄
(c_p^ig/R) and the vapour-pressure coefficients b, c, d.
- σ_i(T) = b₀ ln(θ/θ₀) + b₁(θ − θ₀) + b₂(θ² − θ₀²)/2 + b₃(θ³ − θ₀³)/3 + b₄(θ⁴ − θ₀⁴)/4, so that
  dσ_i/dT = (c_p,i^ig/R)/T.
- λ_i(T) = Δh_i/(RT) = T·d ln P_i^sat/dT = −b_i/θ + c_i + 2d_iθ², which is S10's Gibbs–Helmholtz latent heat over
  RT.

**The entropy.** ln φ_i is v1's `lnphi_<c>` at the same state; v1's vapour ln φ ≡ 0. Σ′ skips zero fractions
(0·ln 0 = 0, guarded).
- VAPOR: s/R = Σ_i y_i σ_i − Σ′ y_i ln y_i − ln(P/P₀).
- LIQUID: s/R = Σ_i x_i (σ_i − λ_i − ln φ_i^L) − Σ′ x_i ln x_i − ln(P/P₀).

**Derivation.** S10's potential gives g = Σ x_i [μ_i^ig(T, P₀) + RT ln(x_i φ_i P/P₀)], with h^E = 0 and Λ constant,
and h^L = Σ x_i (h_i^ig − Δh_i). So s = (h − g)/T reduces to the forms above. The entropy datum is
s_i^ig(298.15 K, P₀) = 0 for every component: the records carry no entropy constant, and every S11 use is an entropy
difference at fixed composition (Q22).

**Derivatives:**
- ∂(s/R)/∂T: VAPOR Σ y_i (c_p,i^ig/R)/T; LIQUID Σ x_i [(c_p,i^ig/R)/T − (b_i/θ² + 4d_iθ)/1000 − ∂ ln φ_i^L/∂T],
  with v1's T-derivative. This equals c_p^L/(RT) with first pass §4.3's P2 polynomial (A77).
- ∂(s/R)/∂P: VAPOR −1/P; LIQUID −Σ x_i ∂ ln φ_i^L/∂P − 1/P, which is 0.
- ∂s/∂n_j, projected as v1 projects: R·(a_j − ln x_j − ln(P/P₀) − s/R)/n_tot, with a_j = σ_j − [λ_j if liquid]
  − ln φ_j. This uses Gibbs–Duhem, Σ_i x_i ∂ ln φ_i/∂n_j = 0. It is answered only when every x_k > 0; otherwise a
  request for any n-derivative of s is refused `unsupported` with "derivative_singular: ds/dn_<c> at n_<c> = 0".

**The class.** `WilsonIdealGasProviderV2(records_path=None)` holds `self._v1 = WilsonIdealGasProvider(records_path)`
and reads the parsed records' coefficients through v1's record parser (the same bytes, so `data_sha256` is equal).
- `describe()` is v1's capabilities with:
  - `provider_id = "wilson-ig-v2"`;
  - `implementation_sha256 = sha256(<this module's bytes> + b"\n" + v1.implementation_sha256.encode())`;
  - `properties = v1's + ("s",)`;
  - one sentence added to each of `uncertainty`, `data_provenance` and `numerical_limitations`.

  Every other field is identical.
- `evaluate_phase`:
  - without `"s"`: return v1's result object unchanged;
  - with `"s"`: one v1 call for the other properties plus `lnphi_<c>`, with the requested derivatives; any refusal is
    v1's, returned unchanged; then add s.
- `flash` and `stability`: forward to v1.

The reference conventions keep their ids. ADR 0051 records the added entropy datum; no existing value changes.

**Not added: `v` or `Z`.** The method's liquid g is independent of P: no Poynting, v^E = 0 (S10 §3.4). A declared
v^L = 0 would make a pump compute W = 0 silently, which is the first pass's D3 hazard. The pump on Wilson is refused
with the reason "the wilson-ig liquid has no molar volume (S10 §3.4): pump work ∫v dP is not representable".

**Selection (WO-D5).** The Wilson record source selects `wilson-ig-v2`. D5 touches every site that names the Wilson
provider for selection:
- the first pass's §4.1 registry row;
- the `MODEL_BASES` routing rows, and the column row before I1 writes it;
- the verifier's `fresh_provider` table;
- the P1–P3 precondition key;
- W27 v3's provider rows (`wilson-ig-v2 → activity_coefficient` added; v1's row kept, as v2 keeps `pr-lib-v1`'s);
- the envelope's providers axis and L-S11-3;
- `LIBRARY_ONLY_PROVIDERS` += `"wilson-ig-v1": "S10"`;
- the T08 scanned-providers list.

The gate is A79. **If A79 fails, D5 is reverted:** v2 stays library-only, the Wilson compressor and turbine stay
refused (the reason is already written), and the decision is logged (Q24).

### 4.7 The admission matrix after S11 (this note's rows in bold; the first pass's §4.4 otherwise)

| Model | `syn001` | `pr-c1-v1` | `iapws95-v1` | `coolprop-heos-v1` | Wilson (`wilson-ig-v2` from D5) |
| --- | --- | --- | --- | --- | --- |
| `syn001.tp_heater`, `tp_flash`, `ph_flash`, `valve`, `adiabatic_mixer` | yes | — | — | — | **yes** |
| `syn001.liquid_pump` | yes | — | — | — | — (no liquid volume) |
| `syn001.heat_exchanger`, `component_separator`, `conversion_reactor`, `kinetic_cstr` | yes | — | — | — | — (Q20 / reactors out) |
| **`thermal.heater`, `valve`, `mixer`, `flash`, `pump`** | — | — | **yes** | **yes** | — |
| **`thermal.compressor`, `thermal.turbine`** | — | — | **yes** | **yes** | **yes** (vapour) |
| routing models, `syn001.column`, `c1.*` | first pass §4.4 | | | | |

**Refusal reasons** (A2's `_UNADMITTED`, rewritten at I1b for these pairs):
- a `syn001.*` thermal model on a pure fluid: "use thermal.<namesake> (ADR 0051: pure-fluid streams are
  declared-regime)", with the namesakes tp_heater→heater, valve→valve, adiabatic_mixer→mixer, ph_flash or
  tp_flash→flash, liquid_pump→pump;
- `thermal.heater`, `valve`, `mixer` or `flash` on Wilson: "use syn001.<namesake> (lifted two-phase streams)";
- `thermal.pump` and `syn001.liquid_pump` on Wilson: the no-volume reason;
- any `thermal.*` on SYN-001 or C1: "thermal.* needs a provider with s (SYN-001: none; pr-c1-v1: vapour-only, no s)".

### 4.8 The verifier

**Pure fluids (`verify/thermal.py`; hooked at I1b into the first pass's `DECLARED_MIXTURE` form):**
- **The enthalpy map.**
  - Single-phase streams keep A3's rule: n·h(T, P, declared phase), fresh provider, and the admissibility check
    `phase_admissibility.stream.<S>`.
  - A `vapor_liquid` stream on a pure basis is read from x_final's `<S>.sat.V` and `<S>.sat.L`, as
    V·h^V_sat(P) + L·h^L_sat(P), with the fresh provider at (T_sat(P), P).
    - It is checked by `phase_admissibility.stream.<S>.saturation` (\|T − T_sat(P)\| against τ_T) and
      `phase_admissibility.stream.<S>.fraction` (min(V, L) ≥ −τ_flow, and \|V + L − n\| ≤ τ_flow).
    - Every energy check that reads it carries the qualification `enthalpy of <S> from its carried split (ADR 0051
      D2)`.
    - `independent_split.<S>` is `not_applicable` with reason `temperature_degenerate` (ADR 0012 D7's category and
      reason).
- **`MODEL_CHECKS` entries.** For each `thermal.*` model:
  - `material_balance.<U>[.<c>]` and `energy_balance.<U>`;
  - `specification.<U>.{T,duty,vapor_fraction,P}` as configured;
  - `bounds.<U>.*` (pressure direction, W sign, η range);
  - for the machines, `specification.<U>.isentropic_work`: |η·W − (Ḣ_s − Ḣ_I)| (pump, compressor) or
    |W − η·(Ḣ_s − Ḣ_I)| (turbine) against τ_E.
- **The machines' Ḣ_s** is computed by the verifier's own routine: bisection on T over the declared isentropic side
  (60 halvings, or until the bracket is ≤ 4ε·T) of s^{φs}(T, P_O) − s*. The saturated variants use their closed
  form. It is never the unit kernel's Newton (A66).

**Wilson (`verify/gamma_phi_units.py`; the dispatch at I1b sends `wilson-ig-v2` to `GAMMA_PHI_UNITS`).**
- **Identity with the first pass.** For every stream and unit that `DECLARED_MIXTURE` handles, `GAMMA_PHI_UNITS`
  returns identical checks: the routing models, declared streams and the column's checks (A73).
- **What it adds.** For each `SPLIT_RULES` descriptor, the SYN form's check ids, with these substitutions:
  - *Degeneracy:* temperature-degenerate iff the bubble and dew temperatures of the split's feed at P lie within
    τ_T of T, through `models.syn001.saturation_band`'s dispatching functions. The check carries the
    shared-implementation note that A3 uses.
  - *Independent split:* the fresh provider's TP flash of (n_feed, T, P), against the state's split,
    max_i |Δv_i|, |Δl_i| ≤ τ_flow. A degenerate split is `not_applicable(temperature_degenerate)` and its enthalpy
    comes from the stored split (ADR 0012 D7).
  - *Admissibility:* `provider.stability(state_of_phase, phase)` for each flowing phase of the split must report
    STABLE_WITHIN_TESTED_SCOPE; a TWO_PHASE branch also needs V, L ≥ −τ_flow.
  - *Enthalpy:* Σ over phases of the phase total × mixture h(T, P, phase composition), from the fresh flash
    (stored split if degenerate).

### 4.9 Zero flow and the phase contract

`orchestrator/splits.py` (WO-C6, after B3 merges) gains:
- `_CONFIGURED_BY` entries for every `thermal.*` model, keyed by the unit attribute `dormancy_configuration`.
  Values: `"<spec>:<form>"` for the heater, and `"<form>"` for the others, with form ∈ {LIQUID, VAPOR, SATURATED}.
- `DORMANCY_RULES` entries, each `DormancyRule(outlet, trigger, swapped, side, declared_phase)`:
  - (`thermal.heater`, `duty:LIQUID|duty:VAPOR`) → (`outlet`, `inlet`, `TH-energy`, None, the form);
  - (`thermal.valve`, `LIQUID|VAPOR`) → (`outlet`, `inlet`, `TV-energy`, None, form);
  - (`thermal.mixer`, `LIQUID|VAPOR`) → (`outlet`, `inlet`, `TM-energy`, None, form);
  - (`thermal.pump`, `LIQUID`), (`thermal.compressor`, `VAPOR`), (`thermal.turbine`, `VAPOR`) → (`outlet`,
    `inlet`, `F-energy`, None, form);
  - every other configuration of these models → `()`, present as a key so that `_dormancy_rules` does not raise.
- `thermal.flash` is not in the registry.

Why saturated outlets need no rule: at n = 0, `sat-T` still fixes T. `sat-split` gives V = −L, and the energy or
quality row then gives V·(h^V_s − h^L_s) = Q_spec. So with Q_spec = 0, V = L = 0 and the system is regular. With
Q_spec ≠ 0 the bound V, L ≥ 0 fails, which is the physically right refusal. The work row gives W = 0 at dormancy.

Dormancy forms act only under `T05b-phase-contract-v2` (ADR 0012 D12). Under v1, a dormant single-phase thermal
outlet is typed `RANK_DEFICIENT`, as the SYN-001 pump's is (L-TH-7). *Erratum 2026-10-27 (R-839):* restated. A
solve that must move ends `LINEAR_SOLVE_FAILED` (measured); a converged start certifies `RANK_DEFICIENT`, which is a
fact checked at I1b (`docs/reviews/S11-rulings.md` item 10). *Erratum 2026-10-29 (R-844):* "as the SYN-001
pump's is" does not hold at the certificate. The SYN-001 pump's dormant outlet certifies VERIFIED under either
contract, because the verifier reduces it by its own table. That table has no `thermal.*` outlet, so a converged
dormant single-phase thermal outlet certifies UNVERIFIED, `RANK_DEFICIENT`, under v1 and v2 alike (L-TH-7). The
verifier's thermal entries are a follow-on. Thermal units author no `molar_flow_squared`
row, so they are not signature units and the regime machinery never touches them. Their owned columns enter the EO
start through B2's `UnitEvaluation.owned`.

### 4.10 W27 v3, the envelope and T08 (data at I1b, except D5's rows)

**W27 v3.** `model_functions` gains, each with `offers: []`:
- `thermal.heater` → `heater`;
- `thermal.valve` → `valve`;
- `thermal.mixer` → `mixer`;
- `thermal.flash` → `flash`;
- `thermal.pump` → `pump`;
- `thermal.compressor` → `compressor`;
- `thermal.turbine` → `expander`.

All seven are existing function names in `registration.json` `units.functions`. W27v3-R08 is amended: S4 is
generated at I1b, after D5. Versions 1 and 2 stay byte-identical.

**The envelope:**
- `unit_models.members` gains the seven, to 30 members.
- Limitation rows:
  - **L-TH-1** Pure-fluid stream regimes are declared (liquid, vapor, vapor_liquid = saturated); a closure in another
    regime is refused `phase_regime_mismatch`.
  - **L-TH-2** Saturated pure-fluid streams are produced only by `thermal.*` units; there are no wet feeds, and
    routing models do not carry them.
  - **L-TH-3** `thermal.flash` needs a two-phase state at drum pressure; its products are declared `vapor_liquid`.
  - **L-TH-4** Machine phase rules (§4.4 table); a compressor with a two-phase isentropic state is refused.
  - **L-TH-5** The near-critical box and the supercritical label rule of S05 §4.2 and S07.
  - **L-TH-6** No regime discovery for pure fluids.
  - **L-TH-7** Dormant single-phase thermal outlets need `T05b-phase-contract-v2`.
  - *Erratum 2026-10-27 (R-839):* the envelope's limitation texts change. L-TH-4 and L-TH-5 gain a sentence each, and
    there is a new **L-TH-8**: in a revision a `thermal.mixer` takes inlets of one declared phase (R4). The texts are
    in `docs/reviews/S11-rulings.md` item 10.
  - **L-GP-1** On Wilson, only the five K02/T05 units and the two machines; no pump (no liquid volume); exchanger,
    separator and reactors refused.
  - **L-GP-2** Wilson machines are single-phase vapour, within the records' domain (300–400 K, 30–200 kPa).
  - **L-GP-3** A Wilson TP flash near an azeotrope has an E-2 noise floor (S10 §14); a temperature-degenerate split
    is judged on its stored split.
- U02's text is unchanged. L-S11-1 and L-S11-2 drop "routing models only"; L-S11-3 names `wilson-ig-v2` (D5).

**T08.**
- The providers axis is [`coolprop-heos-v1`, `iapws95-v1`, `pr-c1-v1`, `syn001`, `wilson-ig-v2`].
- `LIBRARY_ONLY_PROVIDERS == {"pr-lib-v1": "S04", "wilson-ig-v1": "S10"}`.
- The scanned providers gain `wilson-ig-v2`.

### 4.11 Performance

- Every pure-fluid block evaluation costs one `Tsat` solve (saturated) or one density root per state (cached by
  exact T in the providers). The isentropic block's inner solve costs at most 100 provider calls, typically 4–6.
- Gates on the workstation (record the numbers; escalate before optimising):
  - Rankine once-through (TH-C1) ≤ 10 s wall;
  - the recycle case TH-R1 ≤ 30 s;
  - the Wilson heater→flash ≤ 10 s.
- Memory: two columns and two rows per saturated stream; no dense blocks larger than C × (C + 4).

### 4.12 The identity statement

- No `thermo/` file that existed before S11 is edited; `wilson_ig_v2.py` is new.
- Every SYN-001, C1 and Wilson revision that binds before C/D binds to the same `ProblemSpec`: G1, family C.
- Every registered solve is byte-identical: the full gate.
- The S08 and S10-C lines reproduce.
- The five edited K02/T05 modules' SYN-001 manifests equal the base's with `implementation_artifact.artifact_hash`
  removed (A67).
- v2's h, `lnphi`, flash and stability equal v1's bit for bit (A75); the column's Wilson results equal the
  pre-switch values bit for bit (A79).
- W27 v1 and v2 are byte-identical.
- The MCP tool-list digest is unchanged: no served schema changes.

---

## 5. Work orders

### 5.1 Rules

- **Branches.** Track C runs on `wp/S11-c` and track D on `wp/S11-d`, each branched from `wp/S11` when its first WO
  starts, in worktrees under `.claude/worktrees/`. They rebase on `wp/S11` before any WO that needs a merged A or B.
  I1b runs on `wp/S11`.
- **Agents.** At most two engineers at a time, including A's and B's. Recommended order: the first free slot takes
  track C (the longer critical path), the second takes track D. Each WO is at most 150k context.
- **Per-commit check:** the touched tests, plus `scripts/s11_identity.py` (in the background, one wait) whenever a
  commit touches the first pass's list or any of `models/syn001/{tp_state,heater,flash,ph_flash,valve,mixer,
  equilibrium_form}.py`. No intermediate full gate.
- **Decision logs:** `docs/S11C_DECISIONS.md` and `docs/S11D_DECISIONS.md`, created by C1 and D1, one
  `DECISION:` line each.
- **Can start before A3 merges** (new files, or files neither A nor B owns): C1, C2, C3, D1, D4.

### 5.2 Track C (pure fluids and the `thermal.*` family)

| WO | Files | Depends on | Acceptance |
| --- | --- | --- | --- |
| **C1** kernel, state, blocks, references | `models/thermal/{__init__,state,kernel,blocks,rows}.py`; `docs/derivations/scripts/s11_thermal_reference.py` (CoolProp 8.0.0 `PropsSI`, HEOS; `--check`, skipped with a reason when CoolProp is absent); `benchmarks/s11/thermal_reference.yaml` (generated in a scratch venv with the `coolprop` extra, committed); `tests/test_s11_thermal_kernel.py`; `docs/S11C_DECISIONS.md` | WO-0 | S11.A42–A49 |
| **C2** heater, valve, mixer, flash | `models/thermal/{heater,valve,mixer,flash}.py`, `tests/test_s11_thermal_units.py` (direct construction) | C1 | S11.A50 (these four), A51, A52, A56, A57, A58 |
| **C3** machines | `models/thermal/machines.py`, the isentropic block variants in `blocks.py`, `tests/test_s11_thermal_machines.py` | C1 | S11.A50 (machines), A53–A55 |
| **C4** binding | `application/thermal_binding.py` (builders and signatures for the seven; the bind refusals of §4.4), `models/revision_flowsheet.py` (`_PARAMETER_KINDS` entry only), `tests/test_s11_thermal_binding.py` (monkeypatched `MODEL_BUILDERS`/`MODEL_BASES`, as `test_m02_wo8_region` does) | C2, C3, A merged | binds for every admitted mode and form; every refusal of §4.4; G1 PASS |
| **C5** verifier | `verify/thermal.py` (`MODEL_CHECKS` functions; the saturated-stream map and checks; the machines' own PS), `tests/test_s11_thermal_verifier.py` (calls the functions directly) | C2, C3, A3 merged | S11.A64–A66 on the C2/C3 states |
| **C6** dormancy and flowsheets | `orchestrator/splits.py` (§4.9 entries only), `benchmarks/s11/thermal/*.json` (TH-C1 Rankine, TH-C2 refrigeration, TH-R1 recycle, TH-V1 valve→drum), `tests/test_s11_thermal_solve.py`. The first commit is a **spike**: TH-V1 alone through the region (Q18) | C4, C5, B3 merged | S11.A59–A63; timings recorded |

### 5.3 Track D (Wilson)

| WO | Files | Depends on | Acceptance |
| --- | --- | --- | --- |
| **D1** γ–φ faces | `models/syn001/{tp_state,heater,flash,ph_flash,valve,mixer}.py` (§4.5), `tests/test_s11_gp_units.py`, `docs/S11D_DECISIONS.md` | WO-0 | S11.A67, A68; G1 PASS; every K02/T05/T05b test unchanged |
| **D2** binding | `application/revision_binding.py` (the five builders' provider kwargs only), `tests/test_s11_gp_binding.py` (monkeypatched `MODEL_BASES`) | D1, A merged | the five bind on Wilson (v1 until D5); G1 PASS |
| **D3** verifier | `verify/gamma_phi_units.py`, `tests/test_s11_gp_verifier.py` | D1, A3 merged | S11.A72–A74 on direct states |
| **D4** `wilson-ig-v2` | `thermo/wilson_ig_v2.py`, `models/syn001/equilibrium_form.py` (`ADMITTED`; `_SCOPE` per §4.5), `docs/derivations/scripts/s11_wilson_entropy_reference.py` (mpmath, 50 digits), `benchmarks/s11/wilson_entropy_reference.yaml`, `tests/test_s11_wilson_v2.py` | WO-0 | S11.A75–A78; S10C-IDENTITY line PASS |
| **D5** select v2 | the §4.6 site list (A's and B's merged files; W27 v3 data and generator; envelope; `tests/test_t08_w2_support_envelope.py` and the S11 tests naming the Wilson provider) | D4; A, B and C4 merged; before I1 | S11.A79; G1 PASS |
| **D6** Wilson flowsheets | `benchmarks/s11/gp/*.json` (GP-C1 heater→TP flash, GP-C2 valve→PH flash, GP-C3 mixer→heater, GP-M1 compressor, GP-M2 turbine refusal), `tests/test_s11_gp_solve.py`. The first commit is a **spike**: GP-C1 alone (Q18) | D2, D3, D5, C3 | S11.A69–A71, A80, A81; timings |

### 5.4 Integration, and the amendments to the first pass's WOs

- **I1b** (on `wp/S11`, after I1, before I2), Opus. It covers:
  - the seven models and Wilson rows in `MODEL_BUILDERS`, `MODEL_SIGNATURES` and `MODEL_BASES`;
  - the routing-producer refusal of §4.1 in the routing builders;
  - `_UNADMITTED` texts (§4.7) with S11.A13's expected strings for those pairs;
  - `MODEL_CHECKS` entries and the two form hooks (`verify/table.py`, `verify/forms.py`);
  - the envelope (§4.10) and `docs/support-matrix.md`;
  - W27 v3 `model_functions` and S4;
  - one bound sample instance per thermal model in the T07/T08 corpora;
  - the count tests of §8.3.

  Acceptance: S11.A82–A86; `t08_support_matrix.py --check`; G1 PASS.
- **Amendments** (minimal; recorded in first pass §9):
  1. **I1** writes `MODEL_BASES["syn001.column"]` with the provider id that the Wilson registry row holds — v2 after
     D5.
  2. **W27v3-R08:** S4 is generated at I1b, not I1. **W27v3-R02:** `wilson-ig-v2 → activity_coefficient` is added
     (D5).
  3. **I2** records G9–G13 beside G1–G8. The single `reviewer` pass covers tracks C and D against this note.
  4. **The first pass's S11.A11 (erratum):** compare the routing manifests with
     `implementation_artifact.artifact_hash` removed. The hash is `file_sha256` of the module
     (`tests/test_k02_unit_models.py:191`), so editing `feed.py`, `sink.py` or `splitter.py` necessarily moves it.
  5. **The per-commit identity trigger list** of first pass §5 gains the seven `models/syn001` files named in §5.1.

---

## 6. Assertions and verification gates

The identity base is `8c34ecb0`, as in the first pass. "Ref" is the committed YAML of the named script; in each
pure-fluid row, the bracketed sanity values (from IAPWS-95 steam tables) bound the reference itself.

### 6.1 Assertions

**Kernel and blocks (C1).**
- **S11.A42 Saturation.** H2O on `iapws95-v1` at P ∈ {1e3, 1e4, 101 325, 1e6, 1e7} Pa: T_s, h^φ_sat and s^φ_sat
  equal the reference within |ΔT| ≤ 2e-6 K and 2e-8 relative. [T_s(101 325 Pa) = 373.1243 K ± 1e-3;
  Δh_vap = 40.65 kJ/mol ± 0.02.] The same at three CoolProp fluids (CO2, R134a, N2) on `coolprop-heos-v1`.
- **S11.A43 PH closure.** H2O on a grid covering:
  - subcooled liquid, β ∈ {0, 0.25, 0.5, 1}, superheated vapour;
  - supercritical (25 MPa, 700 K) and low pressure (1 kPa).

  The regime, T and β equal CoolProp's PH flash within |ΔT| ≤ 1e-5 K and |Δβ| ≤ 1e-7. The same at the three
  CoolProp fluids.
- **S11.A44 PS closure.** The same grid and tolerances, in s.
- **S11.A45 Acceptance.** `declared_state` follows §4.2's table in every cell (3 declarations × 3 regimes), and:
  - β = 0 and β = 1 exactly are accepted as saturated;
  - a declared-liquid state 1e-7 relative to the vapour side in P is refused;
  - `declared_admissible` agrees with A3's verifier rule on a 200-point grid.
- **S11.A46 Jacobians.** Each block's Jacobian against central differences (relative step 1e-6) agrees to ≤ 1e-6
  relative at 20 states per block. The saturated blocks include P within 1e-6 of the range ends.
  *Erratum 2026-10-27 (R-834):* restated. The comparison is scaled, and identities pin the small entries. The two
  near-top states are judged at a fixed 1e-5 above the measured Maxwell floor; the adaptive floor is reverted. See
  `docs/reviews/S11-rulings.md` item 5.
- **S11.A47 Refusal mapping.** `PhaseFlowBlock(LIQUID)` at 1e-3 relative superheat raises `DomainError`, which the
  compiled problem reports as `invalid_trial_state`. An unknown property raises `RuntimeError`.
- **S11.A48 Dormant rule.** At n = 0, the values are 0.0 and the T and P entries are 0.0, and the n entry follows
  §4.3 in each of its three cases.
- **S11.A49 Isentropic identities.** For `pure-single/single`: ∂Hs/∂T_I = n·T_s·c_p,I/T_I and ∂Hs/∂P_O = n·v_s,
  each to 1e-8 relative.

**Units (C2, C3).**
- **S11.A50 DOF and refusals.** Every admitted mode and form gives a square contribution, and every §4.4 refusal
  gives its code and hint.
- **S11.A51 Throttling.** Saturated liquid H2O at 1 MPa (a β = 0 stream) through `thermal.valve` to 0.1 MPa: β
  equals the reference ≤ 1e-7 [0.1528 ± 5e-4], with T = T_sat(0.1 MPa).
- **S11.A52 Heater.**
  - (i) Quality 0 → 1 at 101 325 Pa: Q = n·Δh_vap, ≤ 1e-8 relative to the reference.
  - (ii) T mode, subcooled liquid to superheated vapour: Q against the reference.
  - (iii) Duty mode landing at β = 0.5: β against the reference.
  - (iv) Duty mode declared `liquid` whose closure is SATURATED: `phase_regime_mismatch(<S>)`, and the message names
    `vapor_liquid`.
- **S11.A53 Turbine.** Steam at 3 MPa, 673.15 K → 10 kPa, η = 0.85: β_s, the outlet β and W equal the reference
  ≤ 1e-7 relative [x_s = 0.8366 ± 5e-4; x₂ = 0.9017 ± 5e-4; W = −15.91 kJ/mol ± 0.02].
- **S11.A54 Pump.** Saturated liquid at 10 kPa → 3 MPa, η = 0.75: W and T_O against the reference
  [W = 72.5 J/mol ± 0.3].
- **S11.A55 Compressor.**
  - CO2 at 300 K, 1e5 → 5e5 Pa, η = 0.8: W and T_O against the reference (≤ 1e-7 relative, ≤ 1e-5 K).
  - A dry fluid's saturated vapour, whose isentropic state at P_O is two-phase, gives
    `isentropic_state_two_phase(<U>)`. C3 picks the fluid from the S07 table (for example n-Pentane, 1 → 3 bar)
    and logs it.
- **S11.A56 Mixer.**
  - Superheated vapour and subcooled liquid H2O at equal P make a saturated outlet: β and the energy balance close.
  - A dormant inlet leaves the other inlet's state.
- **S11.A57 Drum.** Wet steam at β = 0.3, 0.5 MPa, ΔP = 0, Q = 0: n_V = β·n and n_L = (1 − β)·n within τ_flow,
  and both products at T_s.
- **S11.A58 Carriage.** A saturated outlet's `vapor_fraction` and owned columns satisfy V = β·n and L = n − V
  bitwise. A heater after a valve reads it, and its duty equals the reference.

**Flowsheets (C6).**
- **S11.A59 TH-C1, Rankine once-through on `iapws95-v1`.** Feed of liquid at 10 kPa, 318.15 K → pump (3 MPa,
  η 0.75) → boiler heater (T mode, 673.15 K, vapour) → turbine (10 kPa, η 0.85, `vapor_liquid`) → condenser heater
  (quality 0) → sink.
  - CONVERGED, VERIFIED.
  - |W_p + W_t + Q_b + Q_c − (Ḣ_sink − Ḣ_feed)| ≤ 5 τ_E.
  - The efficiency (−W_t − W_p)/Q_b equals the reference cycle ≤ 1e-7 relative.
- **S11.A60 TH-C2, refrigeration on `coolprop-heos-v1` R134a.** Vapour at 0.2 MPa, 270 K → compressor (1 MPa,
  η 0.75) → condenser (quality 0) → valve (0.2 MPa) → evaporator (quality 1) → sink. The COP equals the reference
  ≤ 1e-7 relative; VERIFIED.
- **S11.A61 TH-R1, recycle on H2O.**
  - Flowsheet: feed liquid at 0.5 MPa → mixer → heater (duty) → valve (0.2 MPa, `vapor_liquid`) → drum. The drum
    liquid goes → pump (0.5 MPa, liquid) → splitter (0.5) → back to the mixer, and the purge to a sink. The drum
    vapour goes to a sink.
  - CONVERGED, VERIFIED.
  - The flows and T equal the reference script's own sequential-modular solution (CoolProp PH/PS flashes, tear to
    1e-12) within 1e-6 relative and 1e-5 K.
  - C6 fixes the feed and duty so that 0.1 < β < 0.9 at the drum, and logs them.
- **S11.A62 Dormancy.** A splitter fraction of 0 before a `thermal.heater` (duty mode, liquid outlet), under
  `T05b-phase-contract-v2`:
  - with Q_spec = 0: CONVERGED with the label row;
  - with Q_spec = 1 kW: `SPECIFICATION_CONFLICT` `zero_flow_conflict(<U>:TH-energy)`.
- **S11.A63 Mismatch.** A valve declared `liquid` whose closure is SATURATED: the traversal refuses with
  `phase_regime_mismatch(<S>)` and the hint "declare vapor_liquid". With the declaration corrected, it converges.
  *Erratum 2026-10-27 (R-839):* the plan's message carries the first line only. The hint is asserted on the valve's
  own answer. See `docs/reviews/S11-rulings.md` item 10.

**The verifier (C5).**
- **S11.A64** Every A59–A61 certificate is VERIFIED with every check computed. The saturated streams carry passing
  `.saturation` and `.fraction` checks, and the energy checks carry the carried-split qualification.
- **S11.A65 Mutations** at x_final:
  - V += 10 τ_flow with L −= 10 τ_flow on a saturated stream makes the producer's and reader's `energy_balance`
    FAIL;
  - T_S += 2e-6 K makes `.saturation` FAIL;
  - W × (1 + 1e-6) on the TH-C1 turbine makes `specification.<U>.isentropic_work` FAIL (0.016 W ≫ τ_E).
- **S11.A66 Independence.** With `models.thermal.kernel` patched to raise, `verify_revision` still verifies TH-C1.

**Wilson (D1–D3, D6).**
- **S11.A67** D1 identity:
  - G1 PASS;
  - the five modules' SYN-001 manifests equal the base's except `implementation_artifact.artifact_hash`;
  - every K02, T05 and T05b test passes unchanged.
- **S11.A68** On the verification and the real records, each of the five units builds a square contribution with
  `GammaPhiLnKBlock` fed by the liquid flows and mixture enthalpy blocks. A recording provider sees no `lnK` and no
  `h_<c>` request.
  *Erratum 2026-10-27 (R-836):* "square" is restated as SYN-001's ids and counts (33/32 and 16/15 on both bases),
  with the blocks swapped and every row vanishing at the evaluated state. See `docs/reviews/S11-rulings.md` item 7.
- **S11.A69 GP-C1.** A liquid feed with S10 C-MW's composition at 330 K, 101 325 Pa → `tp_heater` (lifted outlet)
  → `tp_flash`.
  - CONVERGED, VERIFIED.
  - The flash products equal the provider's own TP flash at the solved (n, T, P) within τ_flow per component.
  - The energy balances are ≤ τ_E.
- **S11.A70 GP-C2.** Valve → `ph_flash`: the PH flash's T and split equal `ph_state` at the same inputs within
  T05b §5.3's closure tolerances, and |Ḣ_in − Ḣ_out| ≤ τ_E across the valve.
- **S11.A71 GP-C3.** A mixer of two liquids → heater, with the outlet admissibility through
  `single_phase_admissible`; VERIFIED.
- **S11.A72 Limiting case.** VB–VC at their azeotrope at 101 325 Pa (verification records; the azeotrope state
  registered in `benchmarks/s10/reference_values.yaml`), as a `tp_heater` outlet at the azeotropic T: temperature-degenerate, `independent_split` `not_applicable(temperature_degenerate)`,
  and VERIFIED.
- **S11.A73** `GAMMA_PHI_UNITS` and `DECLARED_MIXTURE` give identical checks on A3's Wilson flowsheets and on B4's
  column certificates.
- **S11.A74 Mutation.** Swapping two components' v_i in a Wilson lifted split makes `independent_split` FAIL and
  makes the admissibility or residual checks FAIL.

**`wilson-ig-v2` (D4, D5, D6).**
- **S11.A75 Delegation.** At every state of `benchmarks/s10/reference_values.yaml` and of the S10/S10-C test grids,
  on both record files, v2's h and `lnphi_<c>` (values and derivatives), its flash results and its `stability`
  reports equal v1's (`float.hex`).
- **S11.A76 Closed form.** s equals the 50-digit reference within 1e-13 relative at ≥ 30 states: both phases, both
  record files, one state with a zero mole fraction.
- **S11.A77 Identities.**
  - (i) ∂s/∂T = (∂h/∂T)/T to 1e-10 relative, using v1's h derivative.
  - (ii) ∂s^L/∂P = 0.0, and ∂s^V/∂P = −R/P to 1e-15 relative.
  - (iii) For each pure component at T ∈ {310, 350, 390} K and P = P_i^sat(T): s^V − s^L = (h^V − h^L)/T to 1e-12
    relative (equal Gibbs energies at saturation).
    *Erratum 2026-10-27 (R-836):* restated. The 8 in-domain pairs are judged, the other 10 are refused
    `out_of_domain`, and all six components are covered. See `docs/reviews/S11-rulings.md` item 7.
  - (iv) The isentropic-enthalpy block's Jacobian against central differences, as A46.
- **S11.A78** Any n-derivative of s at a zero mole fraction is refused `derivative_singular`; the T and P
  derivatives are answered.
- **S11.A79 D5.**
  - The Wilson `SELECTABLE_BASES` entry's provider is `wilson-ig-v2`, and the count stays 127.
  - Every Wilson-basis S11 test passes unchanged (first pass A12 Wilson, A16, A29 C-MW/C-EW, A35–A37).
  - The column cases' x_final equal the pre-switch values (`float.hex`).
- **S11.A80 GP-M1, compressor on Wilson vapour** (real records; vapour at 370 K, 40 kPa → 50 kPa, η = 0.8). The
  outlet must stay inside the records' domain (≤ 400 K) with a dew-point margin of at least 5 K at both ends. D6
  checks this and logs it, and may lower P_O, keeping P_O/P_I ≥ 1.1.
  - W equals Σ_j n_j[h_j(T_s, P_O) − h_j(T_I, P_I)]/η, with T_s from the verifier's bisection, within τ_E.
  - The outlet's `stability` is STABLE_WITHIN_TESTED_SCOPE.
- **S11.A81** GP-M2: a turbine whose outlet would be two-phase is refused `phase_regime_mismatch` or
  `isentropic_state_two_phase`. `thermal.pump` on Wilson is refused `model_unsupported(thermal.pump)` with the
  no-volume reason.

**Integration (I1b).**
- **S11.A82 Registries.** `set(MODEL_BASES) == set(MODEL_BUILDERS) == set(MODEL_SIGNATURES)` has 30 members. The
  admission equals §4.7, and every refused pair gives `model_unsupported(<id>)` with its reason.
- **S11.A83 Envelope.** `--check` OK; 30 members; L-TH-1…7 and L-GP-1…3 present; the providers axis and
  `LIBRARY_ONLY_PROVIDERS` as in §4.10.
- **S11.A84 W27 v3.** The seven model functions; `w27_registration_v3.py --check` OK; S4 has 127 routes and the
  Wilson route on `wilson-ig-v2`; v1 and v2 outputs byte-identical.
- **S11.A85** G1 PASS on the final tree, and the S08 and S10-C lines reproduce.
- **S11.A86** Every thermal model has a bound sample instance, as the edge-identity and signature tests require.

### 6.2 Gates (added to the first pass's G1–G8)

| Gate | Criterion |
| --- | --- |
| **G9 kernel and blocks** | S11.A42–A49 |
| **G10 thermal units** | S11.A50–A66, with the §4.11 timings |
| **G11 Wilson units** | S11.A67–A74, A69–A71 timings |
| **G12 `wilson-ig-v2`** | S11.A75–A81 |
| **G13 integration** | S11.A82–A86; then G8 (full `scripts/gate.sh`, CI on both architectures; the thermal and Wilson flowsheet results compared across architectures within 1e-9 relative, worst value recorded) |

---

## 7. Risks and open questions (each with a default)

| Id | Question | Needs | Default |
| --- | --- | --- | --- |
| Q16 | The public family name `thermal.*` | Frank's preference (public name) | **`thermal.*`**; a rename before release is one table and the module paths |
| Q17 | Regime discovery for pure-fluid streams (per-regime block forms in the region) | Frank's preference (scope) | **Not in S11**; declared regimes with a typed mismatch that names the declaration. A follow-on package if wanted |
| Q18 | Does the region backtrack on `invalid_trial_state` from a block during a Newton trial, and do the γ–φ region paths carry the five units? | fact (C6 and D6 spikes) | If not: stop and escalate with the trace. No region surgery inside C or D |
| Q19 | The S07 table holds a dry fluid for A55's refusal | fact (C3) | Use one and log it; if none is admitted, drop that clause of A55 and log it |
| Q20 | `syn001.heat_exchanger` and `component_separator` on Wilson | Frank's preference (scope) | **Refused typed in S11**; the same dispatch makes them a small follow-on |
| Q21 | Wet pure-fluid feeds, and saturated streams through the splitter | Frank's preference (scope) | **Refused typed**; route through a `thermal.*` unit |
| Q22 | Wilson v2's entropy datum, s_i^ig(298.15 K, P₀) = 0 | `reviewer`'s judgement | **Accept**; immaterial to every S11 use (differences at fixed composition) |
| Q23 | A turbine with a superheated outlet and a wet isentropic state | fact per case | The `isentropic_phase` choice; default = the outlet's form. *Closed 2026-10-27 (R-839): not expressible in a revision; typed refusal (L-TH-4); the scope question is OQ-1 of `docs/reviews/S11-rulings.md`* |
| Q24 | D5's bitwise gate (A79) fails | fact (D5) | Revert D5: v2 stays library-only, the Wilson machines stay refused; log |
| Q25 | CoolProp is not installed in `.venv` (checked 2026-10-27) | fact (C1) | Generate the references in a scratch venv with `CoolProp==8.0.0`; commit the YAML; `--check` skips with a reason when it is absent |
| Q26 | `thermal.flash` products must be declared `vapor_liquid` | Frank's preference | **Yes** (one consistent rule: saturated means `vapor_liquid`) |
| Q27 | The §4.11 time gates are exceeded | fact (C6, D6) | Record, then escalate before optimising |

**Risks:**
- D5 is cross-cutting. It is one isolated commit, gated bitwise, with a defined revert (Q24).
- The behaviour of single-phase pure blocks near saturation (backtracking at the ε_σ wall) is measured first in the
  C6 spike.
- I1b carries all the registration churn, after I1. It is one Opus WO and needs no design decision.
- Gate G1's family C runs the suite twice; run it in the background.

---

## 8. Records

### 8.1 ADR 0051 (Proposed)

`docs/adr/0051-s11-thermal-units-on-the-new-bases.md`. It:
- amends ADR 0001 D2.5 and ADR 0050 D1, D3, D5 and D9;
- extends ADR 0012 D7;
- adds a provider beside ADR 0047's, which stays unchanged.

No schema or `Protocol` changes.

### 8.2 The register

R-813…R-821.

### 8.3 Tests reversed on purpose (added to `AMENDED_TESTS` where their keys exist at the base)

- `tests/test_m02_join.py`: the registry table (I1b);
- `tests/test_t08_w2_support_envelope.py:61-80, 335-342`: models, providers, scanned providers and
  `LIBRARY_ONLY_PROVIDERS` (D5, I1b);
- `tests/test_s10_provider.py:688-696` (D5);
- `tests/test_t07_w5c_signatures.py` and `tests/test_t08_w2_edge_identity.py`: the samples (I1b);
- `tests/test_t08_b50_surface_content.py`, if it pins the `list_models` set (I1b);
- the S11 tests of tracks A and B that name the Wilson provider. These are S11's own tests, with no base keys; D5
  edits them.
- *Erratum 2026-10-27 (R-839):* `tests/test_m02_wo8_registries.py`'s dormancy-registry test, restricted to keys outside
  `thermal.` (C6-2; no family-C key).
  *Recorded 2026-10-27 (I1b, rulings item 10 "Records"):* that test is
  `test_the_dormancy_registry_is_syn001s_and_the_c1_mixers_vapour_outlet`; it passes at the base and on the branch, so
  its key needs no `AMENDED_TESTS` entry.

### 8.4 Decisions logs

`docs/S11C_DECISIONS.md` and `docs/S11D_DECISIONS.md`.
