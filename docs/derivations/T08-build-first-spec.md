# T08 — Build-first specification: the kinetic CSTR that runs PTC-R1 (V14 b), and compatible warm starts (V13 e)

**Package:** T08 (plan v1.2 §4.3 row T08), after Frank's F1 and F2 (2026-09-29: "build first" for both).
**Author:** design lane (`specifier`), 2026-09-29, on `wp/T08` at `fb6b6b3`. Brief `docs/briefs/T08-build-first-spec.md`.
**Status:** Proposed. Binding on the build lane and on `verdict` once committed. A defect found in it is amended here, dated and stated, never worked around downstream.
**Consistent with:** T04 spec §6–§8 (the mapping, the SER core, the criterion and PTC-R1, all unchanged), K03 §5 and §10.1, T03 §5.1 and §8.1, T05 §3–§6 and §12–§13, T07 design §4, §12 and ruling round 2, T08 release spec §4.3–§4.4 and §5, ADR 0001, 0007, 0008, 0010, 0011, 0018, 0019, 0020.
**Reference generator:** `docs/derivations/scripts/t08_build_first_reference.py` → `benchmarks/t08/build_first_reference.yaml` (`--check` re-derives every claim of §C.2 and requires the committed YAML byte for byte). Every number below with more than four digits is in that YAML.
**ADR drafts:** `docs/adr/0023-kinetic-cstr-and-ptc-r1.md` (Part A) and `docs/adr/0024-compatible-warm-starts.md` (Part B), both Proposed. ADR 0021's proposed revision is appended to that file. Register text: §J.

---

## 0. The answer, in one paragraph

**Part A.** A new unit model, `syn001.kinetic_cstr`, runs T04's preregistered PTC-R1 exactly, inside the v0.1 envelope, with no change to SYN-001, to any frozen schema or to T04's mapping. The heat of reaction comes from the **vapour** phase, where ADR 0011 D2's datum gives `Δh_r = Σ ν_i L_i` (reaction `B → A`: −5 000 J/mol); every liquid reaction on SYN-001 is thermoneutral and could not realise `B = 8`. The rate law is the synthetic `γ → ∞` form `r = Da · exp((T − T_ref)/T_s) · n_out,k`, and cooling is a coolant capacity rate `F_c c_c (T_c − T)`, both expressed in quantity kinds that already exist. With the registered values the dimensional rows reduce **exactly** to PTC-R1 (Da = 0.072, B = 8, β = 0.3, Le = 1; generator-checked in rational arithmetic, and the PTC and Newton steps agree to 1e-38 at off-grid states). T04's criterion needed four resolutions before any result: the "registered root" is **either stable steady state**; a state reaches a root when it ends `CONVERGED` within 2e-3 of it; the arms are T06-revision-v2 with only `eo_core` changed and recovery off; the saddle clause covers all 441 starts, because none lies within 4.9e-3 of the separatrix. The outcome is not known and is not computed here. **Part B.** Warm starts are **opted into by a registered policy** (`T08-warm-v1`), not by a request field. That policy looks up the most recent VERIFIED solution state in the revision's lineage, checks it like any other candidate, and falls through to the registered initializer on a typed rejection. It records the candidate inside the bundle (`solve-path.json`), so a rerun needs nothing else. **No frozen schema, no MCP tool, no description and no identity key changes**, so T08.A49's surface is untouched and F5's V17 carry is not affected. GUESS roles (S-G) stay backlog.

## 1. Authority and scope

This note specifies, so that the build lane can implement and `verdict` can judge without further design: (A) the unit model, flowsheet, policy, route-(a) mapping, comparison and expected values that let T04 §8.4's PTC-R1 decide V14 (b) under T08 spec §4.4's criterion (R-118); (B) compatible warm starts (blueprint §7.4 source 2) for V13 (e) under T08.A71. **Out of scope:** the ammonia/PyMRM reactor, the nonideal route, the web shell, D1–D3, the RC mechanics, re-qualifying the flash/heater family, any real-chemistry claim (the CSTR's rate law is synthetic), explicit request-named warm starts (§B3, v0.2), GUESS roles (§B4). No `architect` pass is needed: every software seam named here extends an existing one (the mapping registry, `user_start`, `solve-path.json`, the policy registry).

## 2. What this specification establishes

- A1: the kinetic CSTR's contract, rows, accumulation classes, derivatives, zero-flow semantics, causal evaluator and definition of done.
- A2: the PTC-R1 flowsheet inside the envelope, and the offered policy that selects PTC on it.
- A3: route (a) for the CSTR, reusing T04 §6 unchanged.
- A4: the comparison, with every under-determined point of T04 §8.4 resolved before any result, and the git-order evidence for (b2).
- A5: the closed-form values the build lane reproduces.
- B1–B5: the warm-start source, compatibility, chain position, checks, records, identity classes, contract surface, S-G, and the judging evidence.

---

# Part A — the kinetic CSTR and PTC-R1

## A1. `syn001.kinetic_cstr`

### A1.1 Why this form (derivation of the choices)

1. **The exothermic phase.** ADR 0011 D2 declares `SYN-001-ref-v1` a formation datum. Equal `c_p` and equal `v_i` make **every liquid reaction exactly thermoneutral**. A PTC-R1 with `B = 8` therefore needs the **vapour** phase, where `Δh_r^V = Σ ν_i L_i` is constant. With `ν = (A: +1, B: −1)` it is `L_A − L_B = −5 000 J/mol`, exothermic. The energy row stays in total-enthalpy form, `Q + Ḣ_in − Ḣ_out`, as ADR 0011 D2 requires; a separate `ξ Δh_r` term would count the heat twice. Synthetic formation data (ADR 0011's rejected alternative) is not needed.
2. **Kinds that exist.** Adding a quantity kind changes `quantity.schema.json#/$defs/kind`, which `specification.schema.json` and `application-results.schema.json` reference, and so changes MCP-exposed schemas (T08.A49). The model therefore uses no time or conductance kind:
   - the rate constant and the residence time enter only as their product, the dimensionless **Damköhler number at `T_ref`**;
   - the cooling conductance is a **coolant capacity rate**, `F_c c_c` (a `molar_flow` times a `molar_heat_capacity`), for a coolant that leaves at the reactor temperature (the high-NTU limit).
3. **The rate law** is `r = Da · exp((T − T_ref)/T_s) · n_out,k` in mol/s, first order in the key reactant `k`. This is the Frank-Kamenetskii (`γ → ∞`) form PTC-R1 is written in. It is **synthetic**: no Arrhenius claim is made. Written against the key's holdup `N_k = θ_R n_out,k` it is `k(T) N_k` with `Da = k(T_ref) θ_R`, so the physical residence time `θ_R` is never needed separately.
4. **The rate is substituted, not owned.** An owned extent variable with a nonlinear algebraic row would make each linearly implicit step differ from PTC-R1's after the first step, because the row's residual is second-order nonzero after a step. The substituted form makes the dimensional iteration the preregistered one exactly (§A3.4).
5. **The outlet is single-phase by declaration** (`phase ∈ {vapor, liquid}`), with R-007's admissibility criterion, as K02's heater and mixer and T05's pump do (T05 §3.4). A lifted outlet would add a phase-selecting unit and signature logic that PTC-R1 does not have.

### A1.2 Contract

| Item | Specification |
| --- | --- |
| Model id | `syn001.kinetic_cstr` (module `src/process_runtime/models/syn001/kinetic_cstr.py`, following `conversion_reactor.py`: `MODEL_ID` :104, `PORTS`, declared equations, `contribute()` :509–619, `evaluate()` :623–749) |
| Ports | the conversion reactor's (T05 §6.2): `inlet` (1, material), `outlet` (1, material; **declared single phase**, not lifted), `duty` (energy, inlet, `Q` positive into the unit). They are wired as the conversion reactor's are. |
| Pins | `<U>.nu.<c>` (dimensionless, one per component, finite); `<U>.damkohler` (dimensionless, ≥ 0); `<U>.T_ref` (temperature, in the domain); `<U>.T_scale` (temperature_difference, > 0); `<U>.coolant_flow` (molar_flow, ≥ 0); `<U>.coolant_cp` (molar_heat_capacity, > 0); `<U>.T_coolant` (temperature, in the domain); `<U>.pressure_drop` (pressure, ≥ 0) |
| Configuration | `key_component` (with `ν_k < 0`); `phase ∈ {vapor, liquid}`; `inlet_phase`, as the conversion reactor |
| Owned | `<U>.Q` |
| Provider requirements | `TP` flash, `h`, `T ≥ 1`, `P ≥ 1` (T05 §3.3); `reference_convention` in ADR 0011 D2's reaction-consistent set |

**Construction refusals** (`SpecificationError`; the code is the first message line; T05 §3.5 grammar):
- carried from T05 §6.2: `stoichiometry_not_mass_conserving`, `key_not_reactant`, `reference_convention_not_reaction_consistent(<c>)`;
- new: `damkohler_negative`, `temperature_scale_not_positive`, `coolant_flow_negative`, `coolant_cp_not_positive`, `reference_temperature_outside_domain`, `coolant_temperature_outside_domain`, `pressure_drop_negative`, and `rate_exponent_overflow`, raised when `(T_max − T_ref)/T_s > 700` with `T_max` the provider's upper temperature. The last one guarantees `exp` is finite at every in-domain state; it is 25.6 for PTC-R1.

**Evaluation failures** (typed, never `inf`/`nan`):
- `temperature_outside_domain(outlet)` and `pressure_outside_domain(outlet)` are checked **before** the exponential is formed;
- `reactant_exhausted(<c>)` applies in the causal initializer (§A1.4), as T05 §6.3;
- a declared-phase inadmissible outlet takes K02's existing declared-phase code, whatever the build lane finds it to be (T05 §3.4).

### A1.3 Rows

`r = Da · e(T) · n_out,k`, with `e(T) = exp((T_out − T_ref)/T_s)`. Every enthalpy is the provider's, of the declared phase `φ` at `(T_out, P_out)`.

| Equation | Residual | Rows | Row kind | Accumulation (ADR 0008 D3.5) | Class |
| --- | --- | --- | --- | --- | --- |
| `CSTR-mole` | `n_in,i − n_out,i + ν_i r` | one per component | molar_flow | `holdup_balance`, `N_i`, mol | unconditional |
| `CSTR-duty` | `Q + Ḣ_in − Σ_i n_out,i h_i^φ(T_out, P_out)` | 1 | heat_rate | `holdup_balance`, `U` (the enthalpy content, T04 §6.2), J | unconditional |
| `CSTR-cooling` | `Q − F_c c_c (T_c − T_out)` | 1 | heat_rate | `algebraic` | unconditional |
| `CSTR-pressure` | `P_out − P_in + ΔP` | 1 | pressure | `algebraic` | unconditional |

- **DOF.** There are `n_c + 3` rows and `n_c + 3` unknowns: the outlet flows, `T_out`, `P_out` and `Q`.
- **`Ḣ_in`** is formed from the inlet exactly as the conversion reactor forms it (T05 §6.3 (4)).
- **Manifest statements:**
  - `CSTR-mole`: "n_in,i - n_out,i + nu_i r = 0, r = Da exp((T_out - T_ref)/T_s) n_out,k (synthetic rate law)";
  - `CSTR-duty`: "Q + Hdot_in - Hdot_out = 0 on the provider's formation datum (ADR 0011 D2); the heat of reaction is carried by Hdot".
- **Accumulation table.** T05 §13.2's table gains one row: `syn001.kinetic_cstr` has `holdup_balance` `CSTR-mole`, `CSTR-duty`, and `algebraic` `CSTR-cooling`, `CSTR-pressure`.

### A1.4 Derivatives, causal evaluator, zero flow

**Jacobian** (closed form; `δ` Kronecker):
- `CSTR-mole:i`: `∂/∂n_out,j = −δ_ij + ν_i δ_jk Da e`; `∂/∂T_out = ν_i r/T_s`; `∂/∂n_in,i = 1`.
- `CSTR-duty`: `∂/∂n_out,i = −h_i^φ`; `∂/∂T_out = −Σ n_out,i ∂h_i^φ/∂T`; `∂/∂P_out = −Σ n_out,i ∂h_i^φ/∂P` (zero for the vapour); `∂/∂Q = 1`; the inlet columns are those of `Ḣ_in`.
- `CSTR-cooling`: `∂/∂Q = 1`, `∂/∂T_out = F_c c_c`.
- `CSTR-pressure`: `∂/∂P_out = 1`, `∂/∂P_in = −1`.

The Jacobian's nonzeros at the three roots are in the YAML (`model.at_roots.*.jacobian_nonzeros`).

**Causal evaluator = the local model initializer (blueprint §7.4 source 3).** A kinetic CSTR can have several steady states (PTC-R1 has three), so it has no unique causal answer. `evaluate()` therefore returns the **isothermal state at `T_init`**:
- `n_out,k = n_in,k / (1 + |ν_k| Da e(T_init))` and `n_out,i = n_in,i + ν_i r` (the first negative non-key outlet gives `reactant_exhausted(<c>)`);
- `P_out = P_in − ΔP`, `Q = F_c c_c (T_c − T_init)`;
- `T_init = T_c` for a dormant inlet with `F_c c_c > 0`, and `T_init = T_in` otherwise.

Its mole, cooling and pressure rows hold; its energy row holds only by coincidence. It is `ok`, and `validity.limitations` states "causal evaluation is the isothermal local initializer, not a steady state". This is what `traversal-G0-v1` propagates (`orchestrator/revision.py:84`). **Build-lane check:** list every caller of `UnitModel.evaluate`. If any treats the output as a solved answer rather than a start (the tear path is not reachable for revision flowsheets, T07 §12.1), stop and escalate.

**Zero flow** (ADR 0001 D3; T05 §4.7):
- **Dormant inlet, `F_c c_c > 0`.** Outlet flows are 0, `T_out = T_c` and `Q = 0`. This satisfies every row exactly, and the Jacobian is regular: `T_out` is read by `CSTR-cooling`.
- **`F_c c_c = 0` (adiabatic).** `T_out` is read by no row at zero flow. This is T05 §4.7 (a)'s singularity, carried as a registered limitation: v0.1 does not certify an EO solve in which a dormant adiabatic CSTR's temperature appears.
- **A zero key flow** is regular (`∂CSTR-mole:k/∂n_out,k = −1 − |ν_k| Da e ≠ 0`). The registered starts with `i = 20` begin at `n_B = 0.0` exactly, on the lower bound, which exercises that path.

### A1.5 The realization of PTC-R1

| Quantity | Value | Why |
| --- | --- | --- |
| components | `[A, B]` | the smallest set; `ν = (A: +1, B: −1)`, key `B` |
| feed | `n = (0.5, 0.5)` mol/s, `T_f = 360` K, `P = 100 000` Pa, vapour | A in the feed dilutes B and lowers the dew point: the outlet dew point is at most 345.890 715 K (at `x₁ = 0`), 14.1 K below `T_f` |
| `phase` | `vapor` | §A1.1 (1) |
| `damkohler` | 0.072 | `Da = Da_ref · e^{(T_f − T_ref)/T_s} = 0.072` since `T_ref = T_f` |
| `T_ref`, `T_coolant` | 360 K | `T_ref = T_f` and `T_c = T_f`: the `−β x₂` term measures from the feed temperature |
| `T_scale` | 3.125 K | `B = (−Δh_r) z_B / (c_p T_s) = 5000 · 0.5 / (100 · 3.125) = 8` exactly |
| `coolant_flow`, `coolant_cp` | 0.3 mol/s, 100 J/(mol K) | `β = F_c c_c / (n_tot c_p) = 30/100 = 0.3` exactly; `0.3 × 100 = 30.0` exactly in binary64 |
| `pressure_drop` | 0 Pa | |
| θ (policy `residence_time_s`) | 1 s | T04 §7.7, unchanged |

**The map** is `x₁ = 1 − n_B/0.5`, `x₂ = (T − 360 K)/3.125 K`, with `n_A + n_B = 1` mol/s, `P = 10⁵` Pa and `Q = 30 (360 − T)` W.

**Derivation.**
- With `n_B = 0.5(1 − x₁)`, the key row is `CSTR-mole:B = 0.5 [x₁ − Da (1 − x₁) e^{x₂}]`.
- With the vapour enthalpies `h_i = c_p (T − T_r) + L_i` and `Σ n_i = 1`, `Ḣ_in − Ḣ_out = −312.5 x₂ + 2 500 x₁` W. The first term is `n_tot c_p T_s x₂`. The second is the reaction heat `(L_B − L_A) · 0.5 x₁`.
- `Q = −93.75 x₂`. Dividing the duty row by the energy scale `n_tot c_p T_s = 312.5` W gives `−(1 + β) x₂ + B x₁`.
- The residence-time holdups (§A3) make `M` on the reduced coordinates `θ · diag(1, 1)`, that is `Le = 1`.
- With `θ` the time unit, `M ẋ = −F̃` is exactly `ẋ₁ = −x₁ + Da (1 − x₁) e^{x₂}`, `ẋ₂ = −x₂ + B Da (1 − x₁) e^{x₂} − β x₂`.
- The total-moles direction `n_A + n_B` is a separate linear mode, `θ ṡ = −s`, which every step preserves (B04). The rows `CSTR-cooling` and `CSTR-pressure` are linear and hold after every step from a consistent start.

**Generator-checked (B01, B03, B04).** The identities hold in `Fraction` arithmetic. The dimensional rows vanish at the three mapped roots to 1e-30. At three off-grid states, the dimensional PTC step (Δτ = 0.5, 4, 10⁶ s) and the Newton step, mapped to `(x₁, x₂)`, equal the dimensionless ones to a relative 2.4e-39, with `d n_A + d n_B = 0`, `d P = 0` and `d Q = −30 d T` to 1e-35.

### A1.6 What the verifier adds (T05 §12 pattern)

- **`material_balance.<U>.<c>`:** `n_in,c − n_out,c + ν_c r`, with `r` recomputed by the verifier in binary64 from the state and the pins. It is an independent code path from the compiled row, as the pump's work relation is.
- **`energy_balance.<U>`:** `Q + Ḣ_in − Ḣ_out` from fresh provider enthalpies.
- **`cooling_relation.<U>`:** `Q − F_c c_c (T_c − T)`.
- **The declared-phase admissibility of the outlet** uses the existing mechanism.

The tolerances by kind are K04's registered ones; none is added.

### A1.7 Definition of done (V12 rule, T08 spec §4.2)

- contract: B10;
- limiting and failure: B16, B17, B19;
- balance: B11, B19;
- derivative: B12, B13;
- coupled case: the PTC-R1 flowsheet (§A2), converged and certified in B21.

It appears in `MODEL_BUILDERS` and `MODEL_SIGNATURES` (`application/revision_binding.py:1045`).

## A2. The flowsheet and the policy that selects PTC (b3)

- **Revision.** `feed` (`syn001.feed_source`, stream `S1`, the §A1.5 feed) → `cstr` (`syn001.kinetic_cstr`, outlet `S2`) → `product` (`syn001.product_sink`). The components are `[A, B]` and the provider is SYN-001.
  - The build lane writes it in T06-corpus form at `benchmarks/t08/ptc_r1/revision.json`.
  - It is bound by `bind_revision_flowsheet`, so its route is `revision_eo`.
  - `plan_revision` makes it one `solve_eo` region (`orchestrator/revision.py:351–409`).
- **Offered policy `T08-ptc-v1`.** It is `T06-revision-v2` (`application/policies.py:60`) with exactly one change: `globalization.eo_core = "ptc"`, with `ptc` at `PtcPolicy`'s registered constants (`orchestrator/trace.py:570`; T04 §7.7).
  - It is added to `APPLICATION_POLICIES` (:69).
  - A caller selects it by naming it in `solve_body.policy_id`, so **no automatic path selects PTC** (T04 §7.1 unchanged).
  - Recovery is the default policy's (`homotopy_or_sequential_restart`). Edge 3 still runs Newton (T04 §7.1 as amended).
- **Envelope consequence.** U07 ("PTC under an offered policy → `unsupported`") is replaced by: "PTC is offered as `T08-ptc-v1` on flowsheets whose every `holdup_balance` row has a registered mapping entry (`tp_heater`, `tp_flash`, `kinetic_cstr`). Any other flowsheet ends `PTC_MAPPING_INVALID` with `ptc_mapping_invalid(<row>, missing)`." T05 §12.4's refusal for T05 models is unchanged.
- **`ptc.status`** is the single value `"experimental"` (`trace.py:576`). A V14 (b) PASS is recorded by the verdict and the envelope. Widening `status` and registering a policy that carries a qualified value is a later amendment of ADR 0023. It changes a policy hash, so it is never done to the comparison's policies.

## A3. Route (a) for this family: T04 §6 applied to the CSTR

1. **Mapping.** `orchestrator/mass.py::_registered_rules()` (:357–377) gains one entry: `syn001.kinetic_cstr → {"CSTR-mole": component_moles, "CSTR-duty": enthalpy_content}`. Its outflows are **one** `PhaseOutflow(φ, outlet flow ids, T_out, P_out)`.
   - `M` comes from the existing `RegionMass.entries_at` (:141–187):
     - `CSTR-mole:i`: `θ` on `n_out,i`;
     - `CSTR-duty`: `θ h_i^φ` on `n_out,i`, `θ Σ n ∂h/∂T` on `T_out`, and `θ Σ n ∂h/∂P` on `P_out`.
   - θ is the policy's `residence_time_s`, the pseudo-time unit (T04 §6.5).
   - Nothing else in `mass.py` changes, and V1–V4 apply as they are.
2. **`PTC_ROW_SIGN`** is unchanged: −1 on `CSTR-mole` and `CSTR-duty`, +1 on `CSTR-cooling` and `CSTR-pressure`.
3. **Steady-state equivalence, dimensions and sign** are T04 §6.4, verbatim.
4. **Physical content and time unit.** With a common θ on every holdup row of the unit, `M = (θ/θ_R) M_phys`. The pseudo-dynamics are therefore the physical CSTR's dynamics in time units of θ: same trajectories, same modes and same attraction, whatever `θ_R` is. PTC-R1's dimensionless time unit is θ = 1 s.
5. **Reference invariance** (T04 §6.2), for a reacting unit. A shift `h_i → h_i + c_i` changes the problem unless `Σ ν_i c_i = 0`: it changes the heat of reaction, which is why ADR 0011 D2 requires a formation datum. For a **reaction-consistent** shift, the energy row moves by `Σ c_i F_i` and `M_E` by `Σ c_i M_i`, the same row operation, so the step is invariant. *Generator-checked (B05):* `c = (1000, 1000)` J/mol moves the step by 6e-39, and `c = (0, 1000)` moves the energy row at the LOW root by more than 1 W.
6. **Modes (which attract, and why).** The finite generalized eigenvalues of `(Ĵ_σ, M̂)` at each root are PTC-R1's two physical eigenvalues per θ plus the total-moles mode `−1/θ` (B03).
   - LOW and HIGH attract: every finite mode is negative.
   - MID is a saddle with `s₊ = 0.240 462 382 078 009 5/θ`.
   - A linearly implicit pseudo-step multiplies the unstable component by `1/(1 − s₊ Δτ)`:
     - it **repels** from the saddle for `Δτ < 1/s₊ = 4.158 654 635 948 776 θ`, where the step matrix is singular (the mechanism T04 §8.4 names);
     - it overshoots for `1/s₊ < Δτ < 2/s₊ = 8.317 309 271 897 552 θ`;
     - it **contracts toward the saddle** for `Δτ > 2/s₊`.
   - `τ₀ = θ` is below the singularity. SER's growth can pass `2/s₊` near the saddle, and that is the risk the saddle clause tests.
   - Under the physical dynamics, 119 of the 441 starts go to LOW and 322 to HIGH (B08). This is route (a)'s expectation for small Δτ. It is recorded as a diagnostic and is not a criterion.
7. **Algebraic consistency and index.**
   - `CSTR-cooling` and `CSTR-pressure` are linear and index 1 in `(Q, P_out)`.
   - Unlike T04 §6.6's pinned-temperature duties, `T_out` is a genuine **differential** state. This is the "energy row carrying a genuine differential mode" T04 §8.4 anticipated.
   - The feed's rows are algebraic (§7.2 V1 holds on the region).
8. **Bounded domain handling** is T04 §7.3, unchanged. The flows' lower bounds are 0 (`region.py:843`), and a temperature outside 280–440 K is a typed trial failure.

## A4. The comparison: PTC-R1 as preregistered, with its open points resolved now

### A4.1 What T04 §8.4 fixed, and what this note resolves before any result

| Item | T04 §8.4 | Resolution (normative) | Why |
| --- | --- | --- | --- |
| system, parameters | the dimensionless ODE; Da, B, β, Le | §A1.5's realization, exact | (b2): the preregistered case is the one run |
| starts | 21 × 21 on `[0,1] × [0,8]` | `x₁ = i/20`, `x₂ = 0.4 j`, mapped by §A1.5 (§A4.2) | literal |
| "the registered root" | undefined for three roots | **either stable steady state** (LOW or HIGH) | §8.1 had one root, where "reaches the root" and "reaches a stable root" coincide. The saddle clause shows T04 did not count the saddle as success for PTC, and crediting it to Newton only would be incoherent. The per-root alternative (a start counts if PTC reaches root r and Newton does not reach r) is rejected: it would score two methods reaching *different* stable roots as an improvement for both. |
| "reaches" | not stated | the plan ends `CONVERGED` and the final state lies within `r = 2e-3` (dimensionless ∞-norm) of the root (§A4.3) | a certified-state test that no roundoff can move (§A4.3) |
| damped Newton | "damped Newton" (T04 §8.3 used K03's) | `eo_core = "newton"` (K03 §5: Armijo `c = 1e-4`, 20 halvings, 50 iterations per attempt, merit `scaled_residual_half_norm2`) | T04 §8.3's comparator. `newton_refined`'s refinement acts only after a `CONVERGED` exit and never changes an attempt's outcome (ADR 0018 D4), so it cannot move a class. |
| budgets, tolerances, contract | "the same" | both arms are `T06-revision-v2` with `eo_core` set and `eo_recovery = "none"`; PTC at T04 §7.7's constants; `max_attempts` 5; no property budget, no wall-time limit; region tolerances unchanged; scales are the registered nominals (`numerics/scaling.py:41–46`) | "the comparison is of cores, not of recoveries" (T04 §8.3); the product's own scaling is the only choice that is "the same contract" |
| saddle clause | "never reports the saddle from a start off its stable manifold" | "off" is decided by the physical separatrix: **every** registered start is off it, by at least 4.898e-3 vertically (B08), so the clause reads "PTC ends MID from none of the 441 starts" | the manifold is located to about 1e-9; no start is within 1e-3 of it |
| the mechanism | "registered as the mechanism" | B03 (closed form) and B14 (the implementation's pencil contains `s₊`, and its step determinant changes sign across `Δτ = θ/s₊`) | executable |
| platform | not stated | (b1) and the saddle clause must hold on **each** registered platform (`ref-x86-64`, `ci-aarch64`); per-start class differences between platforms are reported | ADR 0007: classes near a separatrix may differ between platforms, and a v0.1 capability must hold on both |

Every realization value was chosen from §A1.1's constraints (the domain, the dew point, the kinds) with no run of either method. This generator computes no iteration of Newton or PTC from any registered start (§A4.6).

### A4.2 The starts

Start `(i, j)`, `i, j ∈ 0…20` (binary64, exact as written):
- `n_A = (20 + i)/40`, `n_B = (20 − i)/40` (correctly rounded quotients; `n_A + n_B == 1.0` for every `i`);
- `T = 360 + 1.25 j` K; `P = 100 000` Pa; `Q = −37.5 j` W;
- every feed coordinate at its fixed value.

The 441 rows are in the YAML (`starts.rows`), sha256 of their compact JSON `b77df2fe…3603c`. They enter through `execute_plan(user_start=…)` (`orchestrator/executor.py:184`, T06 W6): a start over every `spec.variable_ids`, recorded `user_guess`, with every edge and fallback unchanged. If the binding has a variable §A1.5 does not name, stop and escalate.

### A4.3 Classes and the classification radius

- **Class of a run:**
  - `LOW`, `MID` or `HIGH` when the plan's outcome is `CONVERGED` and `max(|x₁ − x₁*|, |x₂ − x₂*|) ≤ 2e-3` for that root (coordinates by §A1.5's map);
  - otherwise `FAIL`.
- **Why 2e-3.** A state passing the region's stop test has a reduced residual bounded by:
  - `3.1e-8/0.5 = 6.2e-8` on the `x₁` row;
  - `(2 · 1.01e-3 + 5000 · 3.1e-8)/312.5 = 6.96e-6` on the `x₂` row.

  With `‖A⁻¹‖_∞ ≤ 17.47` (at MID), its distance from the root is at most 1.216e-4. The radius is 16 times that bound. The closest roots are 0.4394 apart (LOW–MID), so the radius is below 1/100 of the separation (B09).
- **A `CONVERGED` run within no radius** is impossible on this system, which has three roots. It counts as `FAIL`, and B21 requires the count to be 0; a nonzero count is a defect to investigate, not a class.
- **Certificates.** Every `CONVERGED` run's certificate must be `VERIFIED` (B21). A non-`VERIFIED` one is a defect that blocks the verdict (`BLOCKED`); it is not a basin effect.

### A4.4 The criterion

- **Reached sets.** `S_a = {g : class_a(g) ∈ {LOW, HIGH}}` for each arm `a ∈ {newton, ptc}`.
- **(b1).** V14 (b1) holds on PTC-R1 iff all three of these hold on each registered platform:
  - route (a) holds (§A3; B11–B15 pass);
  - **`S_ptc ⊄ S_newton`**: some start ends in `LOW` or `HIGH` under PTC and in `MID` or `FAIL` under Newton;
  - the saddle clause holds: `class_ptc(g) ≠ MID` for all 441 starts, with the mechanism B14 passing.
- **What is reported but judges nothing:**
  - both 21 × 21 class maps;
  - counts per class;
  - accepted steps per start;
  - agreement of `class_ptc` with the physical label (B08);
  - the cost ratio.

### A4.5 Arms and harness

- **Benchmark policies** (not offered): `T08-PTC-R1-newton` and `T08-PTC-R1-ptc`, each `T06-revision-v2` with `globalization.eo_recovery = "none"` and `eo_core = "newton"` or `"ptc"` respectively.
- **Harness** `benchmarks/t08/ptc_r1/compare.py` makes exactly `benchmarks/t06/ensemble.py:598–648`'s calls for each start and arm: `bind_revision_flowsheet` → `plan_revision` → `execute_plan(user_start=start)` → `verify_revision` if `CONVERGED`.
- **Per run it records:**
  - arm, `(i, j)`, outcome, the attempt outcomes, accepted steps (iterations or pseudo-steps), and the final state (`variable_ids` order);
  - class, certificate verdict and check ids, the property-call meter, and the machine class.
- **Outputs:** `benchmarks/t08/ptc_r1/results-<machine>.json` plus a summary with the maps.

### A4.6 (b2): the git order, and what may not run before it

- **`C_reg`** is the commit that adds this note, the generator and the YAML. It fixes the case, starts, classes, criterion, arms and budgets.
- **`C_case`** is the build lane's registration commit. It adds:
  - `benchmarks/t08/ptc_r1/revision.json`;
  - `case.json`, carrying the four policies' `policy_sha256`, the revision's `content_sha256`, the start digest `b77df2fe…`, the YAML's sha256 and `C_reg`;
  - the harness, not yet run.
- **`C_res`** adds the results.
- **The evidence.** `git merge-base --is-ancestor C_reg C_case` and `C_case` is an ancestor of `C_res`. No commit that is not a descendant of `C_case` contains a PTC-R1 result file. `git log --diff-filter=A -- 'benchmarks/t08/ptc_r1/results-*'` names only descendants of `C_case`.
- **Forbidden before `C_case`**, and attested in the manifest: any PTC run on the PTC-R1 flowsheet from any start, and any Newton run from a registered start. Unit tests at the roots and at the off-grid states of §A5 are not runs of either method and are allowed.

### A4.7 (b3) and (b4)

- **(b3):** B24, with `T08-ptc-v1` through `LocalApplication.submit_job` on the §A2 revision. The PTC core runs (`branch_provenance[0].core == "ptc"`); the outcome is recorded and not asserted.
- **(b4):** T04 A19–A22 re-run at the RC (B25).

### A4.8 How the verdict reads

- **PASS** requires every one of:
  - (b1) on both platforms;
  - (b2): B20;
  - (b3): B24;
  - (b4): B25.

  A PASS reads: "V14 (b) PASS: the residence-time PTC family (`T04-residence-time-v1` + SER, T04 §7.7) qualified on the kinetic-CSTR class, PTC-R1 at `C`; experimental elsewhere (T04 §8.3)".
- **Otherwise FAIL, naming the failing sub-clause.** For example: "(b1) containment: `S_ptc ⊆ S_newton` (|S_ptc| = …, |S_newton| = …)", or "saddle clause: PTC ended MID from starts […]". **It stays FAIL.** Nothing in this note is re-read after the result (R-118).

## A5. Expected values the build lane must reproduce (YAML `closed_form`, `model`)

| Root | `x₁`, `x₂` | `T` (K) | `n_B` (mol/s) | `Q` (W) | eigenvalues per θ |
| --- | --- | --- | --- | --- | --- |
| LOW | 0.170 751 376 007 636 69, 1.050 777 698 508 533 47 | 363.283 680 307 839 17 | 0.414 624 311 996 181 66 | −98.510 409 235 175 01 | −0.920 905 439 106 555 87, −0.218 994 507 722 532 22 |
| MID | 0.242 160 224 879 842 27, 1.490 216 768 491 337 05 | 364.656 927 401 535 43 | 0.378 919 887 560 078 87 | −139.707 822 046 062 85 | −0.922 720 719 133 932 03, +0.240 462 382 078 009 48 |
| HIGH | 0.964 596 072 289 254 03, 5.935 975 829 472 332 49 | 378.549 924 467 101 04 | 0.017 701 963 855 372 99 | −556.497 734 013 031 17 | −20.407 527 052 357 696, −1.421 158 042 437 969 79 |

- **Agreement with T04.** These equal T04's registered `ptc_r1_cstr_preregistered` to its twelve digits and its §8.4 quotation (B02).
- **Registered states for B15** (single steps at off-grid states): `(x₁, x₂) = (0.12, 0.7), (0.33, 2.1), (0.905, 6.3)`, with Δτ ∈ {0.5, 4, 10⁶} s and Newton. The steps are in the YAML.
- **Causal initializer at the feed (B18):** `n_B = 0.5/1.072 = 0.466 417 910 447 761 19`, `T = 360`, `Q = 0`.
- **Liquid variant (B19):** feed, `T_ref` and `T_c` at 300 K, phase liquid, at `P_r`. The root is `T = 300` K and `Q = 0` exactly, with `n_B = 0.466 417 910 447 761 19`. The reaction heat is 0 exactly because ADR 0011 D2 makes liquid reactions thermoneutral. At the vapour LOW root the same term is 426.878 W, so a model that drops it fails B11 by more than 4e10 of B11's tolerance (rule 3).

---

# Part B — compatible warm starts

## B1. Source, compatibility, incompatibility

- **Source (decided): automatic from the project's store, opted into by policy.**
  - Blueprint §4 (line 253): "Warm-start history ... are **opt-in** inputs **with hashes**"; §3 (line 189): "Warm starts are transferred through an **explicit state mapping**."
  - The opt-in is the offered policy `T08-warm-v1` = `T06-revision-v2` with `initializer_chain = ("compatible_warm_start", "traversal-G0-v1")`.
  - Every existing policy has `initializer_chain = ()` and behaves exactly as today.
- **The explicit form**, a request naming a prior job, is **deferred to v0.2**. It needs a member in `job.schema.json#/$defs/solve_body` (`additionalProperties: false`), which the MCP `submit_job` tool exposes, so it changes T08.A49's surface and needs an ADR 0019 amendment and a V17 re-run (§B3, Q-B1).
- **Selection rule `store-latest-verified-lineage-v1`.** The candidate is the solution state of the ended `solve` job with the highest job ordinal (`jobs.ordinal`, `application/store.py`) such that:
  1. the job is not the current job;
  2. its revision is the current revision or an ancestor through `parent_revision`;
  3. its bundle holds a `solution_state` artifact;
  4. its certificate verdict is `VERIFIED`.

  At most one candidate is considered. Under the process executor the selection sees the store as it is when the job starts. The choice is recorded, so replay never repeats the lookup.
- **Compatible** means the candidate's `variable_ids`, as a set, equal the target binding's `spec.variable_ids`: same units, streams, components and lifted splits. The explicit state mapping is the identity on variable ids. The problems may differ in every specification value, pin and parameter; that is the use case (sweeps, revisions).
- **Incompatible** gives a typed rejection and the next source, never a failure of the run.

## B2. Chain position, checks, records, identity

- **Position.**
  - Source 1 (user guess): a `user_start` from an internal harness wins, and the chain is not consulted. On the contract path there is none (S-G).
  - Source 2: `compatible_warm_start`, when the effective policy's chain names it.
  - Source 3: `traversal-G0-v1`, as today.
  - Physical nominals: absent on the revision path, as today.
- **Layering.** The application layer (`jobs/runner.py`, which has the store) performs the lookup and passes an optional `WarmStartCandidate(document, provenance)` through `run_revision_session` and `execute_plan` to `_solve_revision_region` (`executor.py:603`). The orchestrator never reads the store.

**Checks**, in order. The first failure rejects with `initializer_rejected`, message `warm_start_rejected(<check>)` with no float, and the next source follows.

| Check | Holds iff | On failure |
| --- | --- | --- |
| `integrity` | the document is `solution-state-v1`, its ids equal its keys, and its `state_sha256` recomputes (`run.solution_state.inconsistencies`, T07 F1.4) | reject |
| `compatibility` | `set(variable_ids) == set(spec.variable_ids)` | reject |
| `bounds` | every bounded coordinate is at or above its lower bound | **project** to the bound and log the id with from and to (K03 §10.1's rule); not a rejection |
| `evaluation` | the region's residual at the (projected) candidate evaluates `ok` in every unit | reject, `warm_start_rejected(evaluation)` |
| `opening` | T03 §5.1's six opening checks (`phase_contract.py:294` `check_opening`), called directly on the candidate as attempt 0's opening state, with the opening signature chosen as for a `user_start` opening | reject, `warm_start_rejected(opening:<check>)`, in place of `CHECKPOINT_INCOMPATIBLE` for this external source only |

- **On acceptance.** The region opens from the candidate exactly where and as `user_start` enters (`executor.py:628`), with `initializer_source = "compatible_warm_start"` (T03 §8.1; a free string in `solution-certificate.schema.json`). The check's evaluation is metered like any other. The region's iteration 0 evaluates again, and the exact property cache makes that a cache hit where the provider caches.
- **Fixed specifications.** Nothing overwrites them. The candidate supplies only `x₀`, and the target revision's rows, pins, bounds, tolerances and check policy are the problem. This is how "a warm start may change the method, never the problem" holds by construction.
- **No new fallback.** A warm-started solve that fails keeps the recovery edges the policy already has (ADR 0015's sequential restart re-initializes from a traversal). No new edge is added, and T08 §5.6 is unchanged.

**Trace.** No new event kind is added (`trace.py:57–77` already has `initializer_candidate`, `initializer_accepted` and `initializer_rejected`):
- `initializer_candidate` with message `compatible_warm_start(present)` or `compatible_warm_start(absent)`;
- then `initializer_accepted` (`compatible_warm_start`) or `initializer_rejected` (`warm_start_rejected(<check>)`);
- absent means no accept or reject event.

**Bundle record.** A new member `warm_start` of `solve-path.json` (`application/revision_run.py:499–503`), written **iff** the effective policy's chain names the source and no `user_start` was given. No new artifact file and no new artifact kind: `job.schema.json`'s `artifact_ref.kind` enum is MCP-exposed. `solve-path.json` is a rerun input with no schema (T07 ruling round 2, F1.2), and it already records how the solve was set up. The fields:

| Field | Content | Class (ADR 0007 / ADR 0010) |
| --- | --- | --- |
| `record` | `"warm-start-v1"` | R0 |
| `selection` | `"store-latest-verified-lineage-v1"` | R0 |
| `status` | `absent` \| `accepted` \| `rejected` | R0 |
| `reason` | `null` or the check id (with `:<check>` for `opening`) | R0 |
| `source_job_id`, `source_revision_id` | ids or `null` | provenance: copied verbatim by a rerun, shape-compared |
| `candidate` | the candidate document as found (a `solution-state-v1` object), or `null` if absent or unparseable | `variable_ids` R0; values R1/R2 under ADR 0007 D2; `state_sha256` digest, shape only |
| `projections` | `[[variable_id, from, to], …]` | ids R0; floats R1/R2 |

- **R0 projection.** `run.identity.r0_projection` (`run/identity.py:59`) gains one branch: if `solve-path.json` has `warm_start`, `projection["warm_start"] = {status, reason, selection, candidate_variable_ids (sorted list or null), projected_ids}`. No existing bundle has the member, so the branch is inert on every registered key.
- **Identity and replay.**
  - The warm start is reproducible **from the bundle alone**: the candidate is inside it. On rerun (`revision_run.py:651–696`), `solve-path.json`'s `warm_start` supplies the candidate and provenance, **no store lookup is made**, the checks run again, and the rerun writes the same record.
  - The manifest's `artifacts` map already hashes `solve-path.json`, and `artifact_r0_sha256` covers the R0 branch.
  - `request_sha256` is unchanged; the request names no source.
  - `run-manifest.schema.json` is unchanged.

## B3. The contract surface

**Nothing changes on it.**
- `Application.solve(revision_id, policy_id)` is used with `policy_id = "T08-warm-v1"`. MCP, HTTP and CLI reach it through `submit_job` with `solve_body.policy_id`, a free string.
- **Unchanged:**
  - every operation's request and response schema;
  - every description file (none enumerates policy or model ids; `bindings/descriptions/REVIEW.json`);
  - `OPERATIONS`;
  - the artifact kinds.
- **What does change** is content only: `get_project`'s `solve_policies` lists four policies, and `list_models` lists thirteen models, whose pins use existing kinds.
- **V17.** T08.A49's two digests therefore stay equal (B50), and F5's carry condition is met by this work. Whether content-only additions to `get_project` and `list_models` count as "the surface" is F5's to rule (§G).
- **ADR 0019** is not amended.
- **The v0.2 explicit form** would add `warm_start: {job_id}` to `solve_body` (additive), with the same checks and records and `selection = "explicit-v1"`. Its ADR 0019 amendment text is in ADR 0024's "Deferred" section.

## B4. S-G (GUESS roles on the revision path)

- **Recommended: stays backlog (v0.2, B5).**
  - GUESS roles are §7.4 **source 1**, not source 2, so V13 (e) does not need them.
  - `specification.schema.json`'s `role` enum is `fixed | free | decision`, and adding `guess` changes an MCP-exposed schema (`commit_change`), so T08.A49's surface would move.
  - The binder refuses non-`fixed` roles today with `specification_role_unsupported` (`models/revision_flowsheet.py:344`).
- **What v0.2 inherits.** The chain built here already puts source 1 ahead of the warm start, so GUESS roles later plug into it.

## B5. What judges V13 (e)

T08.A71 is judged by:
- B41: the source is used, its trace records the source, and the opening checks are applied;
- B43: an incompatible candidate is rejected to the next source;
- B40, B42 and B44–B49: absent, never changes the problem, integrity, evaluation, projection, replay, selection and identity;
- B50: the surface.

**The registered states:**

- **Source.** `SYN-001-nominal` (T06 corpus) is committed and solved under `default`, giving `VERIFIED`.
- **Target.** A child revision of the source changes only the splitter's recycle fraction from 0.5 to 0.95, the registered high-recycle value, whose unique root is P01's oracle (SYN-001 §5). It is solved under `T08-warm-v1` and, in the same test, under `default`. If the cold `default` run of this target does not end `VERIFIED` on the revision path, the build lane stops and escalates, and this state is amended here. No weaker target is substituted.
- **Incompatible.** A later child revision renames the flash instance, so the variable ids change and the structure is otherwise the same. It is solved under `T08-warm-v1`.
- **Tampered.** The selected source's stored `solution-state.json` has one value altered on disk, and its `state_sha256` is left alone.
- **Evaluation.** A constructed candidate has every id and a consistent `state_sha256`, but one temperature is at 450 K, outside the provider domain.
- **Projection.** A constructed candidate has one flow at `−1e-12` and a consistent hash.
- **Where each is tested.** B40–B44 and B47–B48 run through `LocalApplication`. B45 and B46 pass a constructed `WarmStartCandidate` to `execute_plan`, because the store never holds such a state.
- **Selection.** There are three prior runs:
  - a `FAILED`-verdict run is never selected;
  - a run of a revision outside the lineage is never selected;
  - of two eligible runs, the later ordinal is selected.

---

# C. Assertions, generator

## C.1 Assertion catalogue

**Exact** means equality of integers, strings, sets, ids and class labels. Every float tolerance states its floor and why.

| ID | Subject and state(s) | Expected | Tolerance and why | Judged by |
| --- | --- | --- | --- | --- |
| T08.B00 | `t08_build_first_reference.py --check` | every claim passes; committed YAML equals the regenerated bytes; this table's ids equal the catalogue, unique, sorted | exact | generator |
| T08.B01 | realization identities and SYN-001 records | Da = 9/125, B = 8, β = 3/10, Le = 1 in `Fraction`s; `Σν = 0`; `Δh_r^V = −5000`; `0.3·100 == 30.0` and `n_A + n_B == 1.0` in binary64; exponent at 440 K = 128/5 ≤ 700 | exact | generator |
| T08.B02 | the three roots and their physical eigenvalues | as §A5; equal to T04's registered values within T04's twelve digits, and to T04 §8.4's quotation | 1e-11 (T04 writes twelve significant digits) | generator |
| T08.B03 | dimensional rows at the roots; the pencil; the saddle | rows ≤ 1e-30; finite eigenvalues = physical ∪ {−1/θ} to 1e-25; det(J̃+sM) cubic; `det(M/Δτ + J̃_σ)` at Δτ* ≤ 1e-30 relative with a sign change across ±0.1 %; T04's "4.16", "−0.9227", "0.2405" | mpmath 40 digits; roundoff ~1e-38 | generator |
| T08.B04 | single steps at the three off-grid states, Δτ ∈ {0.5, 4, 10⁶} and Newton | dimensional = dimensionless (relative ≤ 1e-30; measured 2.4e-39); `dn_A + dn_B`, `dP` ≤ 1e-35; `dQ + 30 dT` ≤ 1e-30 | mpmath | generator |
| T08.B05 | reference shift | `c = (1000, 1000)`: step moves ≤ 1e-30 (measured 6.1e-39); `c = (0, 1000)`: energy row at LOW moves > 1 W | mpmath | generator |
| T08.B06 | margins | outlet dew point ≤ 345.890 715 K (at `x₁ = 0`), grid `T ≥ 360` K; physical trajectories `0 ≤ x₂ ≤ 16` ⇒ `T ≤ 410 < 440` K; `P` inside 50–200 kPa | exact bound (the invariant `u = x₂ + B(1 − x₁)`, `u̇ = B − u − βx₂`) plus mpmath dew point | generator |
| T08.B07 | the starts | 441 distinct rows; `T`, `Q` exact as written; digest `b77df2fe138d5c2ce34f4775acfc2dfeddad080f4df3acf6ef2865d9a325603c` | exact | generator |
| T08.B08 | physical geometry | one separatrix crossing per grid column (YAML); every start's forward label equals its side; min vertical distance 4.898e-3 ≥ 1e-3; max `x₂` on trajectories 15.9923 ≤ 16; labels L 119, H 322 | crossings to about 1e-9 (Radau rtol 1e-12), written to 6 digits; the claim needs only 1e-3 | generator |
| T08.B09 | classification radius | 2e-3 ≥ 10 × 1.216e-4 (distance bound) and ≤ 0.4394/100 | exact inequalities on mpmath values | generator |
| T08.B10 | CSTR contract | `list_models` signature (ports, pins with kinds of §A1.2, choices); the 11 construction codes of §A1.2, each raised by one constructed input, first line exact | exact | test |
| T08.B11 | CSTR rows at the three roots (binary64 of the YAML states) | mole rows ≤ 1e-12 mol/s; duty and cooling ≤ 1e-8 W; pressure = 0 exactly | measured binary64 floor 1.78e-15 mol/s and 3.41e-13 W (YAML `model`); margins ≥ 560 and 2.9e4; the smallest defect worth catching (dropped reaction heat, 426.9 W at LOW; a 1 % UA error, ≥ 0.98 W) is ≥ 1e8 × tolerance | test |
| T08.B12 | CSTR Jacobian at the three roots and the three off-grid states | (a) at the roots, entries equal the YAML `jacobian_nonzeros`, row-normalized relative ≤ 1e-12, and no other entry is nonzero; (b) at all six states, central differences with step `1e-6 ×` the column kind's registered nominal agree, row-normalized ≤ 1e-7 | (a) binary64 AD vs a 20-digit reference: floor about 1e-15; (b) measured floor 2.51e-10 on the registered rows (YAML `float64`), margin 400; a dropped `r/T_s` term is 2.3e-2 | test |
| T08.B13 | mapping on the PTC-R1 region | `resolve_mass` returns entries on exactly `CSTR-mole:A`, `CSTR-mole:B`, `CSTR-duty`; `M` nonzeros equal YAML `mass_nonzeros_theta_1s`, relative 1e-13; a region with the CSTR and a T05 model still ends `ptc_mapping_invalid(<T05 row>, missing)` | 1e-13: provider enthalpies about 3e4 J/mol in binary64 | test |
| T08.B14 | implementation pencil at the three roots (scaled `Ĵ_σ`, `M̂`, finite eigenvalues from the dense generalized problem) | equal to the YAML pencil values, relative 1e-9; at MID the determinant sign of `M̂/Δτ + Ĵ_σ` differs between Δτ = 0.99 and 1.01 × 4.158 654 635 948 776 s, and not across [0.5, 0.9] or [1.1, 2] × that | 1e-9: float64 eigen-solve, floor about 1e-13 × condition; the sign is invariant under the positive diagonal scalings | test |
| T08.B15 | implementation's single PTC step (Δτ ∈ {0.5, 4, 10⁶}) and Newton step at the three off-grid states | mapped to `(x₁, x₂)`: equal to the YAML, relative ∞-norm ≤ 1e-8 | 1e-8 ≥ 1e3 × ε × cond (max cond 5 388, YAML); a wrong `M` entry moves a Δτ = 0.5 step by O(1) | test |
| T08.B16 | zero flow | dormant inlet: outlet flows `0.0`, `T = T_c`, `Q = 0.0` exactly, the region converges at iteration 0, Jacobian regular (rank full); with `coolant_flow = 0`: label `T_in`, and T05 §4.7 (a)'s limitation reported | exact | test |
| T08.B17 | out-of-domain `T_out` = 441 K and 1e4 K (EO rows and `evaluate`) | typed `out_of_domain` with `temperature_outside_domain(outlet)`; no `inf` or `nan` anywhere | exact | test |
| T08.B18 | causal evaluator at the PTC-R1 feed | `n_B = 0.466 417 910 447 761 19`, `n_A = 1 − n_B`, `T = 360.0`, `Q = 0.0`, status `ok`, the stated limitation | relative 1e-14 (four ulps) | test |
| T08.B19 | liquid variant (§A5) | converges at iteration 0 from the traversal start; `T = 300.0`, `Q = 0.0` exactly; `VERIFIED`; the vapour realization's `CSTR-duty` at LOW contains 426.878 W of reaction heat (B11) | exact / B11's | test |
| T08.B20 | (b2) git order | `C_reg` is an ancestor of `C_case`, which is an ancestor of `C_res`; no result file outside `C_case`'s descendants; the manifest attests §A4.6's prohibitions; `case.json`'s hashes recompute | exact | verdict |
| T08.B21 | the 882 runs on each platform | every run ends typed; `CONVERGED`-but-unclassified count 0; every `CONVERGED` certificate `VERIFIED`; results and summary committed | exact | ci |
| T08.B22 | V14 (b1) containment | `S_ptc ⊄ S_newton` on each platform, by §A4.4 | exact (sets) | verdict |
| T08.B23 | saddle clause and mechanism | `class_ptc ≠ MID` for all 441 starts on each platform; B14 passes | exact | verdict |
| T08.B24 | (b3) | `T08-ptc-v1` via `submit_job` on the §A2 revision: the job ends typed; `branch_provenance[0].core == "ptc"`; the policy is in `get_project.solve_policies` | exact | test |
| T08.B25 | (b4) | T04 A19–A22 pass at the RC | as T04 | ci |
| T08.B26 | identity | K05 minus-`t07` `9a7b4e6d…`, T02 floats `9a8a5baf…`, structural `915c97e8…`, keys `t02`…`t06` byte-equal; `t07` equal except the D2/D3 substitutions; `requirements.lock` unchanged | exact | ci |
| T08.B27 | envelope | 13 models; offered policies {`T06-revision-v2`, `T04-W12`, `T08-ptc-v1`, `T08-warm-v1`}; U07 replaced by §A2's row; limitations of §E present | exact | test |
| T08.B40 | absent | fresh project, `T08-warm-v1` on `SYN-001-nominal`: `warm_start.status = absent`; the event `compatible_warm_start(absent)`; final state bitwise equal to the same process's `default` run; same verdict and check ids | exact (same process, same inputs) | test |
| T08.B41 | accepted | target under `T08-warm-v1`: `initializer_candidate(present)` then `initializer_accepted`; `branch_provenance[0].initializer_source == "compatible_warm_start"`; the first `attempt_opened` event's `state_sha256` equals the digest of the candidate's values computed the way the trace computes it (same columns, same order), so the region opened at the candidate exactly; `CONVERGED`, `VERIFIED`; `source_job_id` names the source job | exact (two digests from one process are compared; none is pinned, ADR 0008 D2.1) | test |
| T08.B42 | never changes the problem | warm and cold runs of the target: equal `revision.json`, `constants_sha256`, `model_version`, `plan_id`, check ids and verdict; final states equal within ADR 0007 D2 (1e-9 relative); both within S3's allowance of the P01 high-recycle root | registered (ADR 0007 D2; T02 §6.4) | test |
| T08.B43 | incompatible | `initializer_rejected` `warm_start_rejected(compatibility)`, then the traversal start; the run equals the same revision's `default` run except policy id, events and the `warm_start` member | exact | test |
| T08.B44 | integrity | `warm_start_rejected(integrity)`; the next source; the run is not failed by it | exact | test |
| T08.B45 | evaluation | `warm_start_rejected(evaluation)`; the next source | exact | test |
| T08.B46 | projection | accepted; `projections == [[<id>, -1e-12, 0.0]]`; the opening coordinate is `0.0` | exact | test |
| T08.B47 | replay | `reproduce(rerun=true)` of the B41, B43 and B44 bundles in a fresh project: `MATCH`; rerun `warm_start` records equal the originals; the store is not queried during rerun (spy) | R0 exact; floats ADR 0007 D2 | test |
| T08.B48 | selection | §B5's three prior runs: the later eligible ordinal is chosen; `FAILED`-verdict and out-of-lineage runs are never chosen | exact | test |
| T08.B49 | byte identity | every existing policy: no `warm_start` member; `r0_projection` of every registered bundle unchanged; the `t07` identity cases unchanged | exact | test |
| T08.B50 | agent surface | T08.A49's descriptions digest `6d13e13d…` and the request/response schemas of `c7bbc98` unchanged | exact | ci |
| T08.B51 | V13 (e) | judged by T08.A71 on B40–B50 | exact (criterion) | verdict |

## C.2 What `--check` asserts about this note's own numbers

The claims cover:
- the identities (B01);
- the roots against T04's YAML and §8.4's quotation (B02);
- the vanishing rows, the pencil, the singularity and its sign change (B03);
- the step identities and that the three states are off the grid (B04);
- reference invariance, and that an inconsistent shift does change the problem (B05);
- the margins (B06);
- the starts (B07);
- a single crossing per column, 441 labels equal to their side, no start within 1e-3 of the manifold, and the trajectory bound (B08);
- the radius (B09);
- the B11 floor margins, the B12 floor, and B15's condition bound;
- the catalogue against this table (B00).

It runs no Newton or PTC iteration from a registered start.

---

# D. What this specification does not establish

- **Not the outcome.** Nothing here predicts whether PTC-R1 qualifies the family. The physical basin labels are the ODE's, not PTC's, and they are not evidence for either method.
- **Not a qualification beyond PTC-R1's class.** A PASS qualifies the family on the kinetic-CSTR flowsheet class only. The flash/heater family stays experimental on T04 §8.3's evidence, and blueprint §7.5's "limited to its tested envelope" holds.
- **Not chemistry.** The rate law, the Damköhler parameterization and the coolant model are synthetic. The exotherm is SYN-001's vapour `Σ ν_i L_i`, not a real heat of reaction.
- **Not an argument that an unmodelled exotherm can be ignored.** The vapour-only exotherm is a consequence of ADR 0011 D2, and liquid kinetic CSTRs are thermoneutral on SYN-001.
- **Not a stability theorem.** §A3.6 is local, and PTC's discrete behaviour away from the roots is exactly what the comparison measures.
- **Not solution accuracy.** Certificates promise residual accuracy (ADR 0007 F3), as before.
- **For warm starts:** not an explicit source, not a mapping across topology changes (compatibility is id identity), not a fallback after acceptance beyond the existing edges, not faster convergence (no speed claim is registered), not GUESS roles.

# E. Existing expectations that change (applied by the build lane in the commit that lands this note)

1. **T08 release spec §4.3.** "*Expectation:* ... (e) not met" becomes "(e) judged at the RC on T08 build-first B40–B51 (R-124); F2 answered *build*".
2. **T08 release spec §4.4.** "*Expectation:* FAIL on (b)" becomes "(b) judged at the RC on T08 build-first B20–B25 against §A4's resolution of T04 §8.4 (R-123); outcome not known; F1 answered *build*". "*Evidence:*" gains "(b) PTC-R1: T08 build-first spec Part A".
3. **T08.A70's expected value** becomes "judged by §4.4's criterion as resolved in T08 build-first §A4; PASS needs B20–B25"; **T08.A71's** adds "on B40–B51". This is the same table, and the ids are unchanged.
4. **T08 §5.2.** Unit models: "the thirteen of `MODEL_BUILDERS`". Solve policies: the four of B27. Globalization: "PTC offered as `T08-ptc-v1` (experimental unless V14 (b) passes)". **T08.A20:** "models = the 13". **§5.3:** U07 is replaced by §A2's row.
5. **§5.5 limitations** gains:
   - L-CSTR-1: synthetic rate law and coolant model;
   - L-CSTR-2: adiabatic dormant temperature (T05 §4.7 (a));
   - L-CSTR-3: the causal evaluator is an initializer;
   - L-WS-1: warm-start compatibility is id identity, and a topology edit gets a typed rejection;
   - L-WS-2: the source is automatic under an opt-in policy only, with no request-named source (v0.2).
6. **T05 §13.2** gains the kinetic CSTR's row (§A1.3). **T04 §8.4's owner** is T08 (this note); T04 builds nothing for it, as it said.
7. **ADR 0021 D3's table** is emptied by the proposed revision appended to ADR 0021.

# F. Open questions with recommended defaults

| # | Question | Kind | Recommended default |
| --- | --- | --- | --- |
| Q-A1 | Should a kinetic CSTR support several reactions or an Arrhenius law? | Frank's preference | No in v0.1: one reaction, the `γ → ∞` law; more is v0.2 with the ammonia work |
| Q-A2 | If a platform class differs from the other on a near-separatrix start, is V14 (b) judged per platform (as §A4.1 decides) or on `ref-x86-64` only? | Frank's preference | Per platform, both must pass. A difference is reported either way. |
| Q-A3 | After a PASS, widen `ptc.status` and register `T08-ptc-v2` carrying it? | needs a fact (the verdict) | Yes, by an ADR 0023 amendment after the verdict. Never edit the comparison's policies. |
| Q-A4 | Does any caller of `UnitModel.evaluate` treat the result as a solution (§A1.4)? | needs a fact: grep the callers | Assumed none. If one does, stop and escalate before W2 ends. |
| Q-B1 | The explicit, request-named warm start: v0.1 or v0.2? | Frank's preference | v0.2 (M03). It changes T08.A49's surface and needs an ADR 0019 amendment and a V17 re-run. |
| Q-B2 | Candidate pool: VERIFIED only, or any certified verdict? | design; revisit on use | VERIFIED only. A FAILED state is a poor start and a confusing provenance. |
| Q-B3 | Can the lookup read other principals' runs in the project? | needs a fact: T07 §10.1's rights | If `read` on the project covers all its jobs (as T07 §10.1 reads), yes. Otherwise restrict to the caller's jobs and state it in the envelope. |
| Q-B4 | Concurrency: the lookup's snapshot under the process executor | none | Recorded as selected, so replay is exact. No locking. |

# G. FOR FRANK

1. **V14 (b) can now be decided on a case preregistered before T04 ran anything.** The outcome is unknown. If it fails, V14 (b) stays FAIL and ADR 0021's revision sends the tag question back to you (carry as FAIL, or hold). The build costs one model, one registration commit and 882 two-variable runs.
2. **The exotherm lives in the vapour.** SYN-001 makes every liquid reaction thermoneutral (ADR 0011 D2), so the CSTR that realises PTC-R1 is a gas-phase reactor. No SYN-001 data changes.
3. **Warm starts need no contract change.** They are opted into by a new policy and recorded inside the bundle, so T08.A49's surface is untouched. **Please rule under F5 whether two content-only additions (a model in `list_models`, two policies in `get_project`) leave V17's carry intact.** The recommended answer is yes: no schema, description or tool changed.
4. **Q-A2 and Q-B1 are yours;** their defaults are in §F.

# H. Findings (recorded, not acted on here)

- **F1.** T04 §8.4's criterion was under-determined for a three-root case ("the registered root"). §A4.1 resolves it before any result. A future preregistration should state the success set explicitly.
- **F2.** `quantity.schema.json`'s kind enum is referenced by MCP-exposed schemas. Any new quantity kind moves T08.A49 and so V17's carry. This constrained the CSTR's parameterization and will constrain v0.2's reactors: a `time` or `thermal_conductance` kind is worth batching into one ADR with the v0.2 contract changes.
- **F3.** `job.schema.json`'s `artifact_ref.kind` is closed for producers and MCP-exposed. Every new bundle file is therefore an MCP surface change, which is why the warm-start record lives in `solve-path.json`. A v0.2 design may want an extension point there.
- **F4.** `PtcPolicy.status` is single-valued by design (`trace.py:573`). A qualification needs a new value and a new policy hash (Q-A3).

# I. Build-lane work order

- **W1 — land the design documents (`C_reg`).** Commit this note, the generator, the YAML, ADR 0023 and ADR 0024 (Proposed), ADR 0021's proposed revision, §J's register entries and §E's amendments. Gate: `t08_build_first_reference.py --check` and `t08_reference.py --check` pass.
- **W2 — `syn001.kinetic_cstr`** (Opus). It covers the model, the signature and builder, the mapping entry, the verifier checks (§A1.6), and T05 §13.2's row.
  - Gates: B10–B19, B26, and `./scripts/check.sh`.
  - **No PTC run on the PTC-R1 flowsheet, and no Newton run from a registered start.**
- **W3 — registration (`C_case`).** It covers `revision.json`, the four policies in code (`T08-ptc-v1` and `T08-warm-v1` offered; the two comparison policies in `benchmarks/t08/ptc_r1/`), `case.json` with their hashes, and the harness (not run).
  - Gates: B13–B15 on the bound revision, the B20 ancestry test, and B26.
- **W4 — warm starts.** It covers the runner lookup, the `WarmStartCandidate` plumbing, the chain on the revision path, the `solve-path.json` record, the `r0_projection` branch and the rerun path.
  - Gates: B40–B49, B50 and B26.
- **Reviewer** (one pass, design lane): W2–W4 before W5 runs, against this note. The model's residual and derivatives, the mapping, the harness and replay identity are CLAUDE.md review subjects. The review of the harness must be done **before** the comparison exists.
- **W5 — the comparison (`C_res`).** Run the harness on `ref-x86-64` and `ci-aarch64` and commit the results and the summary. Gates: B21 and B24.
- **W6 — envelope and records.** It covers `support_envelope.yaml` and the support matrix (B27), `docs/requirements.yaml`, and the manifest listing every B-assertion with its status and the §A4.6 attestation.
- **Then `verdict`** judges B20, B22, B23 and B51 at the RC, with T08.A70 and T08.A71.

# J. Register entries (text; numbered when committed)

**R-123 — PTC-R1 runs on a vapour-phase kinetic CSTR, exactly, and T04 §8.4's open points are resolved before any result.** Date 2026-09-29. Normative: this note, Part A; ADR 0023.
- *Decision:* PTC-R1 runs on a vapour-phase kinetic CSTR (`B → A`, `Δh_r = Σ ν_i L_i`, the `γ → ∞` synthetic law, a Damköhler pin and a coolant capacity rate), which maps exactly onto PTC-R1. The registered root is either stable steady state. "Reaches" means `CONVERGED` within 2e-3. The arms are T06-revision-v2 with only `eo_core` set and recovery off. The saddle clause covers all 441 starts. Both platforms must pass. PTC is offered as `T08-ptc-v1` by explicit policy.
- *Rejected:*
  - synthetic liquid formation data (it moves every identity, per ADR 0011);
  - new quantity kinds (they move T08.A49);
  - an owned extent variable (the discrete iteration would no longer be PTC-R1's);
  - "any root" (incoherent with the saddle clause);
  - the per-root reading (it scores divergent successes as improvements);
  - `newton_refined` as a separate comparator (it cannot change a class).
- *Watch for:* any re-reading of §A4 after `C_res`; a PTC-R1 result committed before `C_case`; the comparison policies edited after `C_case`.

**R-124 — Compatible warm starts are opted into by policy, chosen from the lineage's latest VERIFIED state, checked like every candidate, and recorded inside the bundle; the contract is unchanged.** Date 2026-09-29. Normative: Part B; ADR 0024.
- *Decision:* `T08-warm-v1` sets `initializer_chain = (compatible_warm_start, traversal-G0-v1)`. Selection is `store-latest-verified-lineage-v1`, and compatibility is id-set identity. The checks are integrity, compatibility, bounds (projection), evaluation and opening, and a failure is a typed rejection with the next source. The record is `solve-path.json`'s `warm_start`, and a rerun uses it with no lookup.
- *Rejected:*
  - a `solve_body` field in v0.1 (it changes the MCP surface and ADR 0019);
  - a new artifact file (a new MCP-exposed kind);
  - content-addressing the source outside the bundle (a bundle must replay alone);
  - a fallback after acceptance (a new recovery edge);
  - K02's warm-start cache (R-119).
- *Watch for:* the lookup run during a rerun; a warm start that overwrites a specification; the member written under a policy that does not name the source.

**R-125 — ADR 0021 D3 is emptied by Frank's F1/F2; a built clause that fails at the RC returns to Frank.** Date 2026-09-29. Normative: ADR 0021 proposed revision 1.
- *Decision:* V13 (e) and V14 (b) are built in T08 and judged at the RC. A FAIL there is carried only if Frank accepts it under D2.3, and otherwise no tag is proposed.
- *Rejected:* keeping D3's pre-answer rows (they no longer reflect Frank's decision); pre-accepting a FAIL (that would be the waiver ADR 0021 rejected).
- *Watch for:* a tag proposed with V14 (b) FAIL and no recorded acceptance.

---

# Amendment 1 — six rulings from the build (2026-09-29)

**Author:** design lane (`specifier`), on `wp/T08` after `14d451b`. Brief: `docs/briefs/T08-build-first-amendment-1.md`.
**Authority.** This amendment is part of this specification. Where it restates a row of §C.1 or a sentence of an earlier section, its text replaces that row or sentence; everything else above stands. The generator reads the §Am1.C table below as the replacement catalogue for the rows it names (`AMENDED_1`, `ADDED_1` in `t08_build_first_reference.py`; B00).
**Preregistration.** `C_reg` = `9f5f29d`. This amendment lands at `C_A1`, before `C_case`, and **no PTC-R1 result exists**. W2 evaluated rows and Jacobians at the three roots and single steps at the three off-grid states of §A5; the design lane, for Q1 below, evaluated the implementation's single-step directions at the same six states with W2's test helpers (`tests/test_t08_kinetic_cstr.py`: `ptc_problem`, `pseudo_step_direction`), and ran no iteration of either method. Both are inside §A4.6's allowance. **This amendment changes the case's dimensional realization** (Q1): a third component at a trace. It changes neither the preregistered dimensionless case, nor the starts' `(x₁, x₂)`, nor the classes, the radius, the criterion, the arms, the budgets or the platforms. §A4.6's argument holds with one more link: `C_reg → C_A1 → C_case → C_res`.

## Am1.0 The rulings

| # | Ruling | Rejected |
| --- | --- | --- |
| Q1 | PTC-R1 binds on `(A, B, C)`, with **C an inert trace of `2⁻¹⁰` mol/s taken from A's feed** — not C at exactly zero. The dynamics, roots, separatrix and labels are unchanged; the starts' `n_A` shifts by `−2⁻¹⁰`, so their digest becomes `0262bebc…` | C = 0 (measured: every C column sits on its bound, where factorization roundoff of either sign meets the bound rule); a PTC-core change (a numerics change on T04's registered path); C fed with `n_tot ≠ 1` (breaks the exact binary64 realization); widening `canonical_components` (ADR 0014 D9, R-076) |
| Q2 | B17 splits: `evaluate` ends `out_of_domain` / `temperature_outside_domain(outlet)`; the EO rows end `invalid_trial_state` with the domain message. The doubled prefix is recorded, not fixed in T08 | a new status (the enum is frozen); asserting the CSTR code on the EO path (the provider block raises first) |
| Stop 1 | Under F5, a **third reference document** `t07_reference_t08.json` (T07 V17 spec Amendment T08-1): v17-c2's with only the offered set changed to `{T04-W12, T06-revision-v2, T08-ptc-v1, T08-warm-v1}`. G16-b is scored against it from T08 on; v17-c1 and v17-c2 keep their bytes and are not re-scored | editing `OFFERED_POLICIES` in place (moves the frozen c1 bytes and c2's registered sha); an offered-but-unlisted policy (a contract that hides what it serves); an oracle read from the live `get_project` (the thing tested) or a superset test (admits invented ids) |
| Q-W4-1 | B41 compares the opening with a `user_start` opening of the same values: the opening is T05b §6.2's projection of the candidate, as for every source | exempting the warm start from §6.2 (a numerics change on the registered path, and two entry paths where §B2 has one) |
| Q-W4-2 | B42 compares the bundles' `execution-plan.json` modulo the policy id and the initializer chain | "equal `plan_id`" (false by construction, `execution.py:776`) |
| Q-P1-1 | Fill it: the initializer failure bundle names the plan, as D2's region bundles do. No R0 projection and no identity key moves; the two pinned document digests move by that substitution only | keeping four empty strings (T08 release spec rule 5: an empty string reads as a value) |

## Am1.1 Q1 — PTC-R1 binds on `(A, B, C)`, with C an inert trace

**Why the binding needs C.** `canonical_components` (`models/revision_flowsheet.py:228`) admits only a permutation of `(A, B, C)` (ADR 0014 D9, R-076), and SYN-001's flash is written for three components. §A1.5's `[A, B]` cannot be bound; §A4.2's stop-and-escalate applies, and this is its answer.

**Why not C at exactly zero (measured).** With `C = 0`, `S1.n.C` and `S2.n.C` are free `molar_flow` columns sitting on their lower bound 0 (`region.py:844`) in every start. Their exact step is zero, but the factorization's is not: SuperLU's pivots mix `CSTR-mole:C` with `CSTR-duty` (W2's own B15 test says so). The design lane measured the directions at §A5's six states:
- at the three off-grid states, `|d n_C|` reaches 2.27e-16 mol/s, **with either sign**: 8 of the 9 PTC steps and all 3 Newton steps have a negative component on a C column;
- at the roots, at most 1.4e-29 mol/s.

T04 §7.3 step 3 makes `α_max = 0` a `bound_blocked` rejection, and the PTC core (`numerics/ptc.py:435`) applies no R-064 release. So with C at zero, 8 of 9 registered off-grid PTC steps would be rejected and their Δτ halved on roundoff, and a roundoff-positive step would lift C off its bound by about 1e-18, after which a roundoff-negative one truncates `α_max` for **both** arms (Newton's R-064 release covers only a component still exactly on its bound). Both arms would then differ from PTC-R1 by arithmetic, not by dynamics: a (b2) failure. The semantics were never the problem: at exactly zero, C is ADR 0001 D3.3's inactive component, the flash sums add an exact `0.0` (`thermo/syn001.py:218–241`), and R-007's admission is bitwise unchanged. The bound is the problem.

**Decision.** `n_C = 2⁻¹⁰ = 0.0009765625` mol/s in the feed, taken from A: `n = (0.4990234375, 0.5, 0.0009765625)`, `ν_C = 0`.
- `n_tot = 1` and `n_B = 0.5` exactly, so `B = 8`, `β = 0.3`, `T_s = 3.125` K and every identity of §A1.5 hold unchanged (B01).
- C's row is `n_in,C − n_out,C`: it vanishes at every consistent state, exactly in binary64 (B28). Since `n_out,C = n_in,C` and the `c_p` are equal, `Ḣ_in − Ḣ_out` is `−312.5 x₂ + 2 500 x₁` as before.
- C's row in `J̃_σ + sM` has one entry, `1 + sθ`, so `det(J̃_σ + sM) = (1 + sθ) det(minor)` (B28): the finite modes are PTC-R1's two, the total-moles mode `−1/θ`, and the trace's `−1/θ`, all decoupled. The exact step on `n_C` is zero.
- The C columns sit `2⁻¹⁰` above their bound, more than 1e12 times the measured roundoff: no rejection, no truncation and no drift can come from them. B21 checks this on every run.

**What the trace touches** (the brief's checklist):

| Item | Effect |
| --- | --- |
| dimensionless case, roots, eigenvalues | none: B02 unchanged; §A5's `x₁, x₂, T, n_B, Q` unchanged; `n_A` shifts by `−2⁻¹⁰` (YAML `closed_form.steady_states.*.n_A_mol_s`) |
| saddle-clause distance, labels | none: 4.898e-3, L 119, H 322 (B08, dimensionless) |
| dew point (§A1.5, B06) | the trace (C is the heaviest, `T_b` 400 K) raises the outlet dew point by 0.158 K, to at most 346.048 738 K at `x₁ = 0`; margin 13.95 K below 360 K |
| R-007 admission | vapour admitted with that margin; at exactly zero it would also have been bitwise unchanged |
| ADR 0001 zero-flow | C flows and is inert; D3.3 no longer applies. S2.n.B at `i = 20` (0.0) stays the only registered column on a bound; its exact step is positive, at least `0.5/(θ/τ_min + 1 + Da e⁸) ≈ 4.9e-5` mol/s at `τ_min = 1e-4` s, so roundoff cannot make it cross |
| B04 total-moles mode | `d n_A + d n_B + d n_C = 0` and `d n_C = 0` (to 1e-35) |
| starts' sha256 | `b77df2fe…` superseded by `0262bebcb9c5af890d770663d1e5a7cd059159bf0eb6f58bd40c04641c49a17c` (only `n_A` changes) |
| B13, B14 | the mapped row set gains `CSTR-mole:C`, and `M` two nonzeros; the pencil gains the second `−1/θ` (the YAML now lists it) |
| B11, B12 | unchanged: the C row is exactly 0.0 at the binary64 roots; the measured floors (1.78e-15 mol/s, 3.41e-13 W, 2.51e-10) are unchanged |
| B15 | `d_x1`, `d_x2` and every dimensional step value unchanged; `d_n_C = 0.0` added to the YAML |
| B18, B19 | `n_A` of the initializer and the liquid root become `1 − 2⁻¹⁰ − n_B`; `n_C = 2⁻¹⁰` |

**Amended text.**
- §A1.5, rows *components* and *feed*: components `[A, B, C]`, `ν = (A: +1, B: −1, C: 0)`, key `B`; feed `n = (0.4990234375, 0.5, 0.0009765625)` mol/s (C a trace of `2⁻¹⁰` taken from A), `T_f = 360` K, `P = 100 000` Pa, vapour. The outlet dew point is at most 346.048 738 K (at `x₁ = 0`), 13.95 K below `T_f`. **The map** gains `n_C = 2⁻¹⁰` and `n_A + n_B + n_C = 1` mol/s.
- §A2, first bullet: "The components are `[A, B, C]`, with C a trace (§A1.5 as amended), and the provider is SYN-001."
- §A4.2: `n_A = (20 + i)/40 − 2⁻¹⁰` (exact in binary64 for every `i`), `n_B = (20 − i)/40`, `n_C = 2⁻¹⁰` at `S2` and `S1`; `n_A + n_B + n_C == 1.0` in binary64 for every `i` (B01). The rows' columns are unchanged, and `n_C` joins `P` under `starts.fixed`. Their sha256 is `0262bebc…a17c`. The escalation sentence stands, against §A1.5 as amended.
- §A4.6: `C_A1` is the commit that adds this amendment and the regenerated YAML. `case.json` carries `C_reg` **and** `C_A1`, the start digest `0262bebc…`, and the YAML's sha256 as committed at `C_A1`. The evidence reads `C_reg → C_A1 → C_case → C_res` (B20).
- ADR 0023 D2 and D5 are amended accordingly (appended there).

## Am1.2 Q2 — B17 on the EO rows

The frozen `evaluation-result` status enum is `ok | invalid_trial_state | unsupported | error` (`schemas/evaluation-result.schema.json`), and its description assigns `invalid_trial_state` to a state that "left a declared domain". B17 named a status that exists only on the evaluator's side; that is a defect of this document, amended here. The evaluator's `out_of_domain` with `temperature_outside_domain(outlet)` stands. On the EO path the provider's enthalpy block (`H_S2_vapor`) meets the domain first, and its message is the domain's, not the CSTR's code. §A1.2's "checked before the exponential is formed" is judged by B17 (c): no returned number is `inf` or `nan` at 1e4 K, where `exp` would overflow. The amended row is in §Am1.C.

**The doubled prefix** (`H_S2_vapor: H_S2_vapor: …`, `compile/casadi_backend.py` and `blocks.py`) is a defect of wording, recorded as finding H-A1-3. It is not fixed in T08: no T08 assertion needs it, and a message change must first be shown to move no pinned fixture or identity case (F4 allows substitution-only moves). B17's pattern uses `re.search`, so a later fix moves no T08 assertion.

## Am1.3 Stop 1 — V17's T10 oracle and the carried surface

§B3 said the `get_project` addition was content-only and left V17 untouched. It missed that V17 registered that content: T10-C3 pins the offered set, and `OFFERED_POLICIES` (`t07_reference.py:97`) feeds both campaign references. Frank's F5 (2026-09-29) rules the additions content-only and keeps the carry.

**Decision.** The T07 V17 spec gains **Amendment T08-1** (appended there, with its text and GC-17). `t07_reference.py --emit-t08` writes `t07_reference_t08.json`: v17-c2's document with exactly `constants.offered_policy_ids` and T10-C3's expected set changed to `{"T04-W12", "T06-revision-v2", "T08-ptc-v1", "T08-warm-v1"}`, plus a `carry` member (GC-17.changes_exactly).
- `t07_reference.json` (v17-c1, `cba24a92…`) and `t07_reference_c2.json` (v17-c2, `23b924b8…`) keep their bytes (GC-16.c1.reference_frozen, GC-17.c2.reference_frozen). v17-c2's 30 runs answered on the old surface and stay scored against the oracle then in force. Nothing is re-scored.
- Reference runs of the carried surface from T08 on (G16-b of T08.A49, `tests/test_t07_v17_reference.py`) are scored against `t07_reference_t08.json`, and `scores.json` records its sha. Runs of v17-c1 and v17-c2, and the scorer's synthetic tests, keep their references (SC-13 unchanged). Preflight P5 is v17-c2's campaign precondition and is not re-run on the T08 surface.
- The response fixture `tests/fixtures/application_results/project_summary/valid/two_revisions_one_job.json` moves by the two added policies only.
- Until `T08-ptc-v1` is offered, G16-b's T10 runs fail against the new oracle. That red is reported, not bent. The recommended order is to offer `T08-ptc-v1` (§A2; its hash is the same whenever it is registered) in the commit that switches G16-b to the new reference.

**§B3, amended.** The bullet "What does change is content only …" reads: "What does change is content only: `get_project`'s `solve_policies` lists four policies and `list_models` lists thirteen models, whose pins use existing kinds. V17 registered one piece of that content, T10-C3's offered set; under F5 the carried surface is judged by reference runs scored against `t07_reference_t08.json` (T07 V17 spec Amendment T08-1)." The bullet "**V17.** … F5's to rule (§G)" reads: "**V17.** T08.A49's two digests stay equal (B50). Frank ruled F5 on 2026-09-29: content-only additions keep V17's carry."

**T08.A49, amended** (appended to the T08 release spec): its G16-b clause reads "G16-b 40/40 clean over Python, CLI, HTTP and MCP, scored against `t07_reference_t08.json`".

**How the carried V17 verdict states it:**

> V17 PASS (carried from `c7bbc98`: v17-c2, 25 of 30, scored against `t07_reference_c2.json` and not re-scored). At `C`, the served descriptions' digest (`6d13e13d…`) and the operations' request and response schemas equal `c7bbc98`'s. The content added under F5 (Frank, 2026-09-29) is `syn001.kinetic_cstr` in `list_models` and `T08-ptc-v1` and `T08-warm-v1` in `get_project.solve_policies`. G16-b passes 40/40 at `C` against `t07_reference_t08.json`, which differs from v17-c2's registration only in the offered set (GC-17). No agent was run on the T08 surface, so the carry covers the surface and the scripted solutions, not agent behaviour with the two new policies.

## Am1.4 Q-W4-1 — B41's opening digest

T05b §6.2 (`region.py:1735–1770`) replaces every lifted split of `x₀` with the kernel's values, whatever the source, and records an `initializer_candidate` event `projected(…)` only for a difference above `1e-12 · max(1, |v|)`. The warm start enters where `user_start` enters (§B2), so it passes through §6.2 too. Measured: the flash split's columns open about 3e-16 relative from the candidate, and the first `attempt_opened` digest is `6533737e…`, where the raw candidate's is `a4ad95ae…` (43 free columns).

**Decision.** B41 compares like with like: the warm opening must equal a `user_start` opening of the candidate's values (same process, same target, same policy), and §6.2 must have recorded no projection. The rejected alternative is exempting this source from §6.2. That is a numerics change on the registered path, it would open lifted splits at values the kernel did not produce, and it would give §B2 two entry paths.

**§B2 "On acceptance", amended.** The first sentence reads: "The region opens from the candidate exactly where and as `user_start` enters (`executor.py:628`), including T05b §6.2's lift of the lifted splits, so the opening state is §6.2's projection of the candidate; `initializer_source = "compatible_warm_start"` (T03 §8.1; a free string in `solution-certificate.schema.json`)."

**B46, by the same cause.** Its `<id>` must be a column §6.2 does not lift, or the opening coordinate is the kernel's value and not `0.0`.

## Am1.5 Q-W4-2 — B42's `plan_id`

`plan_id = f"{label}-{policy.policy_id}-execution"` (`orchestrator/execution.py:776`), and each `solve_plan` inside the plan carries `policy_id`, its own `plan_id`, and the policy's `initializer_chain`. "Never changes the problem" means the same decomposition, not the same policy.

**Decision.** B42 compares the two bundles' `execution-plan.json` under the normalization **N**: every string value has the warm run's policy id replaced by the cold run's (`str.replace`), and every member named `initializer_chain` is removed. Equality must then be exact, and each `plan_id` must end in `-<its policy_id>-execution`. B43's "except policy id" is read with N as well (no change of substance).

## Am1.6 Q-P1-1 — the initializer failure bundle names its plan

**Decision: fill it.** The initializer failure bundle's `replay_identity` carries the executed plan's `constants_sha256`, `model_version`, `plan_id` and `policy_id`: the values the run manifest records, obtained as D2's region bundles obtain them (`solve_route` passes `plan=`, T08 W1.4 `1d26e62`). T07 ruling round 3 Q1 item 3's table said "exactly as `region_bundle`'s on this path (the view has no plan …)". D2 gave `region_bundle` the plan, so the table's own rule now points to the filled values. The table is amended in `docs/design/T07-jobs-and-bindings.md` (appended).

**Identity consequence, from the projection rule.** `r0_projection`'s `failure` branch (`run/identity.py:155–164`) keeps `outcome`, `taxonomy`, `implicated_sources`, the suggested actions and the solver counters, and never `replay_identity`. No bundle's R0 projection moves, so no registered identity key (`t02`…`t07`, K05) moves.

What does move, by the substitution `"" → id` only (F4):
- the two pinned `document_sha256` values of `tests/test_t07_w3f_initializer_bundle.py` (`e07f19c5…` 792 bytes, `6eeb7757…` 766 bytes) and their lengths;
- the run manifests' artifact hash of those two `failure-bundle.json` files (R2, no key).

The build lane proves the move is substitution-only. The amended expected document, with its four ids replaced by `""`, must reproduce the old digests byte for byte, and T08.A13's substitution proof is re-run.

## Am1.C Assertion rows as amended (they replace the rows of §C.1 with the same id; T08.B28 is new)

| ID | Subject and state(s) | Expected | Tolerance and why | Judged by |
| --- | --- | --- | --- | --- |
| T08.B01 | realization identities and SYN-001 records | Da = 9/125, B = 8, β = 3/10, Le = 1 in `Fraction`s with `n_tot = 1` over `(A, B, C)`; `Σν = 0` with `ν_C = 0`; `Δh_r^V = −5000`; in binary64 `0.3·100 == 30.0`, `0.4990234375 + 0.5 + 0.0009765625 == 1.0`, every start's `n_A = fl((20+i)/40) − 2⁻¹⁰` exact and `n_A + n_B + n_C == 1.0`; exponent at 440 K = 128/5 ≤ 700 | exact | generator |
| T08.B03 | dimensional rows at the roots; the pencil; the saddle | rows ≤ 1e-30; finite eigenvalues = physical ∪ {−1/θ, −1/θ} (total moles and the trace) to 1e-25; the `(A, B)` minor's `det(J̃+sM)` cubic; `det(M/Δτ + J̃_σ)` at Δτ* ≤ 1e-30 relative with a sign change across ±0.1 %; T04's "4.16", "−0.9227", "0.2405" | mpmath 40 digits; roundoff ~1e-38 | generator |
| T08.B04 | single steps at the three off-grid states, Δτ ∈ {0.5, 4, 10⁶} and Newton | dimensional = dimensionless (relative ≤ 1e-30; measured 2.4e-39); `dn_A + dn_B + dn_C`, `dn_C`, `dP` ≤ 1e-35; `dQ + 30 dT` ≤ 1e-30 | mpmath | generator |
| T08.B06 | margins | outlet dew point ≤ 346.048 738 K (at `x₁ = 0`, with the trace), grid `T ≥ 360` K, margin 13.95 K > 10 K; physical trajectories `0 ≤ x₂ ≤ 16` ⇒ `T ≤ 410 < 440` K; `P` inside 50–200 kPa | exact bound (the invariant `u = x₂ + B(1 − x₁)`) plus mpmath dew point | generator |
| T08.B07 | the starts | 441 distinct rows; `T`, `Q` exact as written; `n_C = 0.0009765625` and `P` under `starts.fixed`; digest `0262bebcb9c5af890d770663d1e5a7cd059159bf0eb6f58bd40c04641c49a17c` | exact | generator |
| T08.B13 | mapping on the PTC-R1 region | `resolve_mass` returns entries on exactly `CSTR-mole:A`, `CSTR-mole:B`, `CSTR-mole:C`, `CSTR-duty`; the nonzeros of `M` are exactly the YAML `mass_nonzeros_theta_1s` (with `CSTR-mole:C|n_C` = θ and `CSTR-duty|n_C` = θ h_C), each relative 1e-13, and no other entry is nonzero; a region with the CSTR and a T05 model still ends `ptc_mapping_invalid(<T05 row>, missing)` | 1e-13: provider enthalpies about 4e4 J/mol in binary64 (measured 2.2e-16) | test |
| T08.B14 | implementation pencil at the three roots (scaled `Ĵ_σ`, `M̂`, finite eigenvalues from the dense generalized problem) | equal to the YAML `pencil_finite_eigenvalues_per_s` (four values: two physical, −1/θ twice; the test adds none), relative 1e-9; at MID the determinant sign of `M̂/Δτ + Ĵ_σ` differs between Δτ = 0.99 and 1.01 × 4.158 654 635 948 776 s, and not across [0.5, 0.9] or [1.1, 2] × that | 1e-9: float64 eigen-solve, floor about 1e-13 × condition; the −1/θ pair belongs to two decoupled rows, so it is semisimple and perturbs to first order; the sign is invariant under the positive diagonal scalings | test |
| T08.B17 | out-of-domain `T_out` = 441 K and 1e4 K | (a) `evaluate`: `out_of_domain`, code `temperature_outside_domain(outlet)`; (b) the compiled EO residual: status `invalid_trial_state`, and `re.search(r"temperature (\S+) K outside \[280\.0, 440\.0\] K", message)` matches with `float(group(1)) == T_out`; (c) neither is `ok`, and no returned number is `inf` or `nan` | exact | test |
| T08.B18 | causal evaluator at the PTC-R1 feed | `n_B = 0.466 417 910 447 761 19`, `n_A = 0.532 605 527 052 238 805 97` (= 1 − 2⁻¹⁰ − n_B), `n_C = 0.0009765625` exactly, `T = 360.0`, `Q = 0.0`, status `ok`, the stated limitation | relative 1e-14 (four ulps); `n_C` exact | test |
| T08.B20 | (b2) git order | `C_reg` is an ancestor of `C_A1`, `C_A1` of `C_case`, and `C_case` of `C_res`; no result file outside `C_case`'s descendants; the manifest attests §A4.6's prohibitions up to `C_case`; `case.json` carries `C_reg`, `C_A1`, the start digest `0262bebc…`, the YAML's sha256 at `C_A1`, the four policies' `policy_sha256` and the revision's `content_sha256`, and each recomputes | exact | verdict |
| T08.B21 | the 882 runs on each platform | every run ends typed; `CONVERGED`-but-unclassified count 0; every `CONVERGED` certificate `VERIFIED`; every run's final `S1.n.C` and `S2.n.C` within 1e-10 mol/s of 2⁻¹⁰, and no `bound_blocked` rejection or `BOUND_BLOCKED` outcome names a C column; results and summary committed | exact; 1e-10 is ≥ 400 × the worst accumulation of the measured factorization roundoff (2.3e-16 mol/s per step over 5 × 200 steps) and 1e-7 of the trace, which a wrong C term would move by O(r) ≥ 1e-3 | ci |
| T08.B28 | the trace component C (generator) | `n_C = 2⁻¹⁰` taken from A, `n_tot = 1`, `ν_C = 0`; the C row is zero at the roots in mpmath and exactly 0.0 in binary64; `det(J̃_σ + sM) = (1 + sθ) det(minor)` at five `s`, relative ≤ 1e-30 (measured 3.2e-40); `dn_C` ≤ 1e-35 in all twelve off-grid steps; the dew-point shift lies in (0, 1) K (0.158 K); `2⁻¹⁰ ≥ 1e9 · 2⁻⁵² · 3` mol/s and `≥ 1e12 ×` the measured 2.3e-16 mol/s | mpmath / exact | generator |
| T08.B41 | accepted | target under `T08-warm-v1`: `initializer_candidate(present)` then `initializer_accepted`; `branch_provenance[0].initializer_source == "compatible_warm_start"`; the first `attempt_opened` `state_sha256` equals that of the same target region under `T08-warm-v1` opened by `execute_plan(user_start=<the candidate's values>)` in the same process (both may run through `execute_plan`, as B45 does); no `initializer_candidate` event whose message begins `projected(`; `CONVERGED`, `VERIFIED`; `source_job_id` names the source job | exact (digests from one process are compared, none is pinned, ADR 0008 D2.1); §6.2's own 1e-12 threshold, measured 3e-16 | test |
| T08.B42 | never changes the problem | warm and cold runs of the target: equal `revision.json`, `constants_sha256`, `model_version`, check ids and verdict; the bundles' `execution-plan.json` equal under N (§Am1.5), and each `plan_id` ends `-<its policy_id>-execution`; final states equal within ADR 0007 D2 (1e-9 relative); both within S3's allowance of the P01 high-recycle root | registered (ADR 0007 D2; T02 §6.4) | test |
| T08.B46 | projection | accepted; `projections == [[<id>, -1e-12, 0.0]]`, `<id>` a flow column that T05b §6.2 does not lift; the opening coordinate is `0.0` | exact | test |
| T08.B50 | agent surface | T08.A49's descriptions digest `6d13e13d…` and the request/response schemas of `c7bbc98` unchanged; the content differences from `c7bbc98` are exactly `syn001.kinetic_cstr` in `list_models` and `T08-ptc-v1`, `T08-warm-v1` in `get_project.solve_policies`; G16-b 40/40 scored against `t07_reference_t08.json`; `t07_reference.json` and `t07_reference_c2.json` byte-unchanged | exact | ci |

## Am1.G What `--check` now asserts

`t08_build_first_reference.py --check` adds these claims:
- B28's claims;
- B01's three-component and binary64 claims;
- B03's two-mode pencil;
- B04's `dn_C`;
- B06's dew point with the trace;
- B00's amendment rules: the main table and this table are each unique and sorted, this table holds exactly `AMENDED_1 ∪ ADDED_1`, every amended id exists in §C.1, and B28 does not.

The YAML gains `amendments`, `realization.feed_C_mol_s` and `nu_C`, the six-column `jacobian_nonzeros` and `mass_nonzeros_theta_1s`, `n_C` fields, `d_n_C` steps, `trace_mode_factor_max_relative_error`, `dew_point_shift_by_trace_K`, `criterion.trace_component`, and `amended`/`added` marks in the catalogue. `t07_reference.py --check` adds GC-17 (T07 V17 spec Amendment T08-1) and confirms the three JSON files byte for byte.

## Am1.D What this amendment does not establish

- **Not that the implementation keeps C still along the 882 runs.** B28 is exact arithmetic on the registered rows; B21 checks the runs at `C_res`.
- **Not a repair of the bound rule.** Findings H-A1-1 and H-A1-2 describe a PTC and Newton behaviour at exactly-zero columns that the trace avoids here. The flash/heater family's T04 evidence is not re-examined.
- **Not agent evidence for the new policies.** The carried V17 verdict covers the surface and G16-b's scripted solutions. No agent session ran against `t07_reference_t08.json`.
- **Not a statement about other EO out-of-domain messages.** B17 registers the kinetic CSTR's two states.
- **Not a measurement of the identity keys after Q-P1-1.** The "no key moves" argument is from the projection rule; the build lane's re-run of T08.A13 is the measurement.

## Am1.F Findings (recorded, not acted on here)

- **H-A1-1.** The PTC core's bound step (`numerics/ptc.py:435`) applies K03 §5.3's `α_max` without R-064's release, although T04 §7.3 step 3 cites K03 §5.3 "verbatim" and R-064 amended §5.3 on 2026-09-25. So any PTC attempt with a free component exactly on its bound, whose exact step is zero, meets `bound_blocked` rejections on roundoff sign (measured here: 8 of 9 steps). Owner: design lane, after the RC (a T04 amendment with a recount of A19–A22). It is not needed for PTC-R1 after this amendment.
- **H-A1-2.** R-064 releases only components still exactly on their bound. A roundoff-positive step lifts such a component by about 1e-18, and a later roundoff-negative step then sets `α_max < 1`, in Newton and in PTC alike. Same owner as H-A1-1.
- **H-A1-3.** The EO domain message's prefix is doubled (`casadi_backend`/`blocks.py`). Cosmetic; deferred to the v0.2 message batch, after an identity audit.
- **H-A1-4.** A "content-only" claim about the agent surface must be checked against the V17 references' pinned content (`t07_reference*.json`), not only against schemas and descriptions. §B3 checked only schemas and descriptions.

## Am1.O Open questions, each with a recommended default

| # | Question | Kind | Recommended default |
| --- | --- | --- | --- |
| A1-O1 | Do T04's registered PTC runs contain `bound_blocked` rejections on columns whose exact step is zero (H-A1-1)? | needs a fact: grep the registered PTC traces for blockers whose rows are closed | Record only; the design lane takes it up after the RC. PTC-R1 does not depend on it. |
| A1-O2 | Is the trace size right? | design, settled | `2⁻¹⁰`: it is exact, 1e12 above roundoff, and shifts the dew point 0.16 K. Any value in `[2⁻²⁰, 2⁻⁶]` would do; changing it after `C_A1` is a new amendment before `C_case`, never after. |
| A1-O3 | The G16-b red window between W4 and `T08-ptc-v1`'s offering | needs a fact (the commit order) | Offer `T08-ptc-v1` in the commit that switches G16-b to the new reference; report red until then. |

## Am1.I Build-lane work (each item one commit)

1. **`C_A1`.** Commit this amendment, both generators and their outputs (`benchmarks/t08/build_first_reference.yaml`, `docs/derivations/scripts/t07_reference_t08.json`), the appended amendments (T07 V17 spec, T07 design ruling round 3, T08 release spec, ADR 0023), and §Am1.J's register entries. Gate: both `--check`.
2. **W2 tests follow Q1 and Q2.**
   - `t08_cstr_support.py`: the feed and the states get `A = 0.5 − 2⁻¹⁰` and `C = 2⁻¹⁰` at `S1` and `S2`.
   - B13 and B14 read the C entries and the second `−1/θ` from the YAML; drop the hand-built extras.
   - B15 keeps its `|dn_C| ≤ 1e-15` as a roundoff bound.
   - B17 and B18 as §Am1.C.
3. **W3 (`C_case`).** `revision.json` on `(A, B, C)` per §A1.5 as amended, with `nu.C = 0`. `case.json` per B20. The harness records the final `S1.n.C` and `S2.n.C` and any C-column blocker per run (B21).
4. **Offer `T08-ptc-v1`, and switch G16-b's reference runs to `t07_reference_t08.json`.** Update the `project_summary` fixture by the two policies only. Stop 1 gives the details.
5. **W4 tests.** B41, B42 and B46 as §Am1.C.
6. **Q-P1-1.** Pass `plan=` for the initializer failure bundle in `solve_route`. The test's expected literals take the manifest's four ids, and the substitution proof and T08.A13 are re-run (§Am1.6).

Nothing here needs a new `architect` or `reviewer` pass beyond the one §I already plans. The reviewer's W2–W4 pass covers this amendment's model and harness changes.

## Am1.J Register entries (text; numbered when committed)

**R-A1a — PTC-R1 binds on `(A, B, C)` with C an inert `2⁻¹⁰` mol/s trace taken from A; a registered case never carries a free component at exactly zero.** Date 2026-09-29. Normative: this spec, Amendment 1 §Am1.1; ADR 0023 Amendment 1.
- *Decision:* the realization's feed is `(0.4990234375, 0.5, 0.0009765625)` mol/s with `ν_C = 0`. `n_tot = 1`, and every identity and the dimensionless case are unchanged. The starts' digest is `0262bebc…`, and the git order is `C_reg → C_A1 → C_case → C_res`.
- *Rejected:*
  - C at exactly zero (measured: roundoff of either sign on the bound makes 8 of 9 PTC steps `bound_blocked`, and drift truncates both arms);
  - a PTC-core release (a numerics change on T04's path, H-A1-1);
  - C fed with `n_tot ≠ 1` (not exact in binary64);
  - widening `canonical_components` (R-076).
- *Watch for:* the trace "simplified" back to zero; a C column named as a blocker in any comparison run; the trace changed after `C_case`.

**R-A1b — Build-first Amendment 1's other rulings: B17 follows the frozen status enum; the carried V17 surface is scored against a third reference; a warm opening is §6.2's projection; plans are compared modulo the policy; the initializer bundle names its plan.** Date 2026-09-29. Normative: this spec, Amendment 1 §Am1.2–§Am1.6; T07 V17 spec Amendment T08-1; T07 design, amendment to ruling round 3 Q1 item 3.
- *Decision:*
  - B17: EO rows `invalid_trial_state` with the domain message, and `evaluate` `out_of_domain`;
  - `t07_reference_t08.json` is v17-c2's document with only the offered set changed, used by G16-b from T08 on; v17-c1 and v17-c2 are not re-scored;
  - B41 compares with a `user_start` opening, and B42 compares plans under N;
  - the initializer failure bundle's `replay_identity` carries the plan's four ids.
- *Rejected:*
  - a new status value;
  - editing `OFFERED_POLICIES` in place;
  - an unlisted offered policy;
  - an oracle read from `get_project`;
  - exempting warm starts from §6.2;
  - comparing `plan_id` verbatim;
  - keeping empty identity strings.
- *Watch for:* `t07_reference_c2.json` regenerated with T08's set; a V17 verdict that cites G16-b without naming the reference it was scored against; a region opened from a warm start without §6.2's lift.

# Amendment 2 (2026-09-29, transcribed by the build lane from `docs/reviews/T08-review.md` §3.1–§3.2, design-lane rulings)

**Author.** The rulings are the design lane's (`reviewer`, `docs/reviews/T08-review.md` §3.1, §3.2, S5, S6), made on `wp/T08` at `9777e53`, after `C_case` (`c337fa1`) and before any PTC-R1 result. The build lane transcribes them here; the quoted words are the review's and nothing is decided in this amendment that the review did not decide.
**Authority.** This amendment is part of this specification. Where it restates a sentence of §A4.1 or a row of §Am1.C, its text replaces that sentence or adds to that row; everything else above stands.
**Preregistration.** No PTC-R1 result exists. `case.json`, `revision.json`, the arms, the starts and the YAML stay as committed at `C_case`; the review: "**Re-registration: no.** `case.json`, the arms and the YAML are unchanged. The amendment is spec text plus a defect clause, written before any result" (§3.1), and "**Re-registration: no.**" (§3.2).

## Am2.1 P-budget — the arm definition governs (review §3.1)

The review's ruling: "the arm definition governs, and the registration stands as committed". §A4.1's row and §A4.5 define each arm as "`T06-revision-v2` with `eo_core` set and `eo_recovery = "none"`", which `case.json` hashes; "No property budget" in §A4.1 and the YAML's `max_property_calls: null` (`build_first_reference.yaml:876`) "state an intent: no budget may constrain the comparison". The two agree because the plan-wide 10 000 cap (`executor.py:1043`) cannot bind on this case: the region opens at most one attempt (single phase by declaration, no lifted split, so `decide` has no conversion to restart into, `phase_contract.py:475–482`); one PTC attempt is bounded by "≈ 5 200 plus the mass evaluations", one Newton attempt by "≤ 50 × (4 + 21 × 2) = 2 300" (review §3.1, with the derivation).

**§A4.1, amended text.** In the row "budgets, tolerances, contract", "no property budget" is replaced by:

> the property budget is `T06-revision-v2`'s 10 000, which cannot bind on this case (≤ one attempt per run; bound above)

"Amend §A4.1's text, not the arms." **Rejected** (review §3.1): "lift the cap in the arms. That changes both `policy_sha256` values, and the arms would no longer be `T06-revision-v2` with only the core changed."

## Am2.2 B21's defect clause (review §3.1, S5)

T08.B21 (§Am1.C) gains, after "no `bound_blocked` rejection or `BOUND_BLOCKED` outcome names a C column":

> no run ends `BUDGET_EXHAUSTED` with `budget = property_calls`, and every run opens exactly one attempt; either is a defect that blocks the verdict (`BLOCKED`), never a `FAIL` class

The reason (review S5): "Without it, a run that did exhaust the cap would be scored `FAIL` and would count *against* the arm." The harness records both facts (review S2; commit `e3518ef`): each run's `budget` and `attempts`, and in B21's summary `budget_exhausted` split by budget, `max_attempts_per_run` and `max_property_calls_per_run`.

## Am2.3 P-trace erratum — B21's 1e-10 governs (review §3.2, S6)

The review's ruling: "B21's 1e-10 governs; record the YAML's 1e-12 as an erratum, and do not regenerate the YAML before `C_res`". §Am1.C's B21 row is the normative assertion; it carries the tolerance's derivation ("≥ 400 × the worst accumulation … 2.3e-16 mol/s per step over 5 × 200 steps"). The YAML's `criterion.trace_component` (`build_first_reference.yaml:880–882`) is prose emitted by the generator (`docs/derivations/scripts/t08_build_first_reference.py:1062`) and "mis-transcribes that row".

**Erratum** (the review's words):

> B21's C-trace tolerance is 1e-10 mol/s; the YAML's 1e-12 is a generator transcription error, superseded; the generator is corrected after `C_res`

"The verdict judges at 1e-10 and reports the raw maximum deviation. The harness already records it" (B21's `c_final_max_abs_deviation_mol_s`).

**The YAML and the generator are NOT regenerated before `C_res`.** "Its sha256 is in `case.json`, so `--run` would refuse and a new registration would follow for no gain" (review §3.2).

## Am2.D What this amendment does not establish

It changes no arm, start, class, radius, criterion, budget, tolerance or platform, and no byte of `case.json`, `revision.json` or the YAML. It judges nothing: B21–B23 remain the design lane's `verdict` against §A4.4 on W5's results.

## Am2.J Register entry

R-128 in `docs/decision-register.md`.

---

# Amendment 3 (2026-10-01) — B50's descriptions digest, by Frank's decision

**Authority.** Frank, 2026-10-01, answering the V13 (e) verdict (`docs/reviews/T08-verdict-V13e.md`, which found
B40–B49 MET and B50 NOT MET solely on its digest clause): "Amend B50". Recorded by the build lane; register R-134.

**T08.B50 as amended.** The agent surface is the one R-133 carries: the descriptions digest is
`171dd768efcfb24f65d79d83a4f157dcfd1436935bf5106a247b84f3040e4d14`, which differs from v17-c2's `6d13e13d…` in
exactly `validate.md` and `commit_change.md` (the description review's N1 and N2), shown by
`tests/test_t08_w2_surface_digest.py` (restoring the two v17-c2 texts reproduces `6d13e13d…`); the request and
response schemas are unchanged since `c7bbc98`. Every other clause of B50 is unchanged.

**What this does not change.** No other row, criterion or registered value; `6d13e13d…` stays the registered v17-c2
surface (historical). V13 (e) is re-confirmed at the release candidate like every gate.

---

# Amendment 4 (2026-10-01) — B50's content clause excludes the package version, by Frank's decision

**Authority.** Frank, 2026-10-01 ("Amend"), answering the V13 verdict at `C` = `814e151`
(`docs/reviews/T08-verdicts.md`, finding G2): B50's content clause ("the content differences from `c7bbc98` are
exactly `syn001.kinetic_cstr` and the two policies") cannot hold at any release candidate, because release spec §8.1
(1) and §8.3 require `get_project`'s `server.package_version` to change. Register R-144.

**T08.B50 as amended.** The content differences from `c7bbc98` served by `list_models` and `get_project`, **excluding
`server.package_version`**, are exactly `syn001.kinetic_cstr` in `list_models` and `T08-ptc-v1`, `T08-warm-v1` in
`get_project.solve_policies`; a test asserts this equality exactly (no such test existed — finding G2). Every other
clause of B50, as amended by Amendment 3, is unchanged.
