# S10-C design: composition-dependent K in the PH kernel and the column (`wilson-ig-v1`)

**Status:** design note, design lane (`architect`), 2026-10-26. **ADR:** `docs/adr/0049-s10c-composition-dependent-k.md`
(Proposed). **Register:** R-760…R-769. **Brief:** `docs/briefs/S10C-flash-and-column.md`. **Branch:** `wp/S10C` from
`main` `ffcb387f`. **Evidence for the measured facts:** `docs/derivations/scripts/s10c_design/measurements.py`, output
`measured.txt` beside it (run from the repository root with `PYTHONPATH=src:.`).

This note stands alone: an implementer who has seen neither the brief nor the conversation can build from it. Where it
says "decided", the build lane does not choose. Where it says "default", the build lane proceeds on the default and logs
it in `docs/S10C_DECISIONS.md`.

---

## 0. The decisions in one screen

1. **Equilibrium forms behind an identity allow-list.** A small unit-layer module resolves a provider to an
   *equilibrium form* by `(provider_id, reference_convention)`: `syn001-lnK-TP` (SYN-001, today's code, untouched) or
   `gamma-phi-ig-v1` (`wilson-ig-v1` under `WILSON-IG-ref-v1` or `S10-VER-ref-v1`). The column admits exactly these two;
   every other provider keeps S11's refusal. The cascade (S01) keeps S11 unchanged. (§4.1)
2. **K is always evaluated at a liquid composition.** For `gamma-phi-ig-v1`, `ln K_i = ln φ_i^L(T, P, x)` from the
   provider's `lnphi_<c>` (its vapour `ln φ` is identically 0, S10 spec (3.10)). Enthalpy flows are `Ḣ = n_tot · h`.
   (§4.2)
3. **One new numerical primitive, the constant-β point** `(T, x)(n, P, β)`: composition successive substitution with an
   exact temperature solve per step. It generalises ADR 0012 D1's `T(β)`, is exact in one step at `β = 0` (bubble),
   is the liquid-trial stationary point at `β = 1` (dew), and never passes `x` through a Rachford–Rice `β` solve, so it
   has no E-2 noise floor. Measured: ≤ 61 iterations at every tested state, ≤ 29 at the 13 E-2 states. (§4.3)
4. **The PH kernel is band-first for this form.** It computes `T_b`, `T_d` first and then solves exactly one of a
   liquid bracket, a vapour bracket or the existing `β`-bisection band route; it never calls the provider's TP flash
   inside the band. Correctness rests on a theorem that holds for the whole γ–φ-IG class (`Ḣ_TP(T)` strictly
   increasing, `T_b`, `T_d` unique) plus acceptance on the closure's own rows, as today. (§4.5, §4.6)
5. **E-2 is remedied in the PH flash, not in the provider.** The provider's TP flash is unchanged. (§4.11)
6. **The column gets a K-block with inputs `(l_1…l_C, T_j, P_j)`** and its dense `∂ln K/∂l` Jacobian from the
   provider's projected composition derivatives; the condenser's block reads `v_2`. A dormant liquid evaluates the
   block at a composition-neutral probe; the rows that read it are identically zero there. Enthalpy blocks are single-
   output mixture blocks (`models/c1/blocks.py`'s flowing formulas). (§4.7)
7. **Initialisation:** the bubble-point sweeps (S02 §18.2) and S08's core sweeps evaluate K at a composition relaxed by
   `ω = 1/2`; undamped, C-EW oscillates (measured: 2000 sweeps, `|ΔT| = 15 K`, `|Δx| = 0.40`); with `ω = 1/2` C-MW converges in 45 and
   C-EW in 62 sweeps. (§4.9)
8. **Scope:** library level only (Frank's Q-F2 default stands). Column specification kinds admitted for the new form:
   `reflux_ratio`, `boilup_ratio`, `distillate_rate`, `bottoms_rate`, `duty`; `purity`, `recovery`, `temperature` are
   refused, typed. Units other than the column are not admitted. (§4.8, §7)
9. **References:** a 50-digit `specifier` generator gives the C-MW/C-EW roots, band points and PH targets (including
   the E-2 states). IDAES as a column reference is optional and deferred (Frank's preference, default deferred). (§6, §7)
10. **SYN-001 is bit-identical**, proved by gate G1 against `ffcb387f` over every registered SYN-001 configuration.

---

## 1. Problem and scope

**Build.** Make the PH kernel (`models/syn001/ph_kernel.py`, `ph_state`) and the SYN-001 column (`column.py`,
`column_solve.py`, `column_blocks.py`) consume `wilson-ig-v1`, whose K depends on composition, with residual and
Jacobian describing the same function, so that the registered column cases C-MW and C-EW (S10 spec §10) solve against
an independent expectation. Replace refusal S11 for this provider, and only for the column.

**In scope.**
- The equilibrium-form layer and its allow-list (§4.1).
- The γ–φ-IG primitives: `ln K` at a liquid, mixture enthalpy flows, the constant-β point, the fixed-T incipient
  liquid (§4.2–§4.4).
- `ph_state`'s band-first route for the new form (§4.5).
- Every consumer of K or `h_<c>` reached from `ph_state` or `solve_column` with the new form: `saturation_band`,
  `tp_state.enthalpy_flow`, `tp_state.single_phase_admissible`, the orchestrator's `_admissible` (region.py:700), the
  column's validation, compiled graph, initialiser, Stage B builder and acceptance (§4.7–§4.10).
- E-2's remedy (§4.11). Registrations and the evidence manifest (WO-5).

**Out of scope** (each stays as it is today):
- flowsheet admission (`SELECTABLE_BASES`, `MODEL_BASES`; Frank's call, R-709, Q-F2);
- the S01 cascade entry point (`cascade.validate`, `solve_cascade`): S11 unchanged;
- every unit other than the column (`PHFlash`, `Valve`, `ConversionReactor`, `LiquidPump`, `KineticCSTR`, the K02
  heater/flash) and their EO faces (`tp_state.lift_two_phase_stream`);
- the verifier (`verify/`), the certificate path, `models/c1/`, `application/`;
- ternary column claims and the methanol + ethanol Λ refit (S10 review S-4); S08b;
- any change to `thermo/` (S10's provider, its TP flash and its registered results stay byte-identical);
- a vapour non-ideality term (Q-N5; §7 Q8).

---

## 2. Constraints and invariants

### 2.1 Mathematics of the form (S10 spec §3, quoted so this note stands alone)

- `ln φ_i^L(T, P, x) = ln γ_i(x) + ln P_i^sat(T) − ln P`; `ln φ_i^V ≡ 0`; hence `K_i(T, P, x) = γ_i(x) P_i^sat(T)/P`,
  a function of the **liquid** composition only.
- Wilson: `S_i = Σ_j x_j Λ_ij`, `ln γ_i = 1 − ln S_i − Σ_k x_k Λ_ki/S_k`. At a pure liquid `x = e_c`, `ln γ_c = 0`
  exactly in binary64 (`S_c = 1.0`, `ln 1.0 = 0.0`, the sum is `1.0`).
- `h^L(T, x) = Σ x_i h_i^0L(T)`, `h^V(T, y) = Σ y_i h_i^ig(T)` (h^E = 0). So `Ḣ = n_tot h` is linear in the flows.
- The provider's composition derivatives are projected: `∂X/∂n_j = (∂X/∂x_j − Σ_k x_k ∂X/∂x_k)/n_tot`. For
  `X = ln φ_i^L` this is `(G_ij + 1)/n_tot`. Evaluated with `n = l` (the stage liquid flows), it **is** `∂ ln K_i/∂l_j`.
- Positivity on both record sets' T domains (measured, `measured.txt` §1): `Δh_i ≥ 35 175 J/mol`, `c_p,i^0L ≥ 61.1`,
  `c_p,i^ig ≥ 32.1 J/(mol K)`, `d ln P_i^sat/dT ≥ 0.024 K⁻¹`. The theorems of §4.6 need these; the `specifier`
  certifies them as generator claims (WO-S).

### 2.2 Conventions

State `nTP-v1`; flows in mol/s, T in K, P in Pa, enthalpy flows in W; component order = the provider's declaration
order (`CH3OH, C2H5OH, H2O` real; `VA, VB, VC` verification). A binary case is the ternary provider with one flow
exactly `+0.0`. Flowing set `F = {i : z_i > 0}` with `z_i = n_i/n_tot` in binary64 (S10 spec §14 E-1). Division-free
equilibrium rows `v_i L − K_i l_i V` (ADR 0001 D3.2). Signed zeros normalised as today.

### 2.3 What must stay bit-exact, and what may move

- **Bit-exact:** every SYN-001 result — T05/T05b PH cases, K02–T04 flowsheets, S01/S02/S03/S06/S08 cascade and column
  configurations — and every result of a provider outside the allow-list (pr-c1-v1 flowsheets included). `thermo/`,
  `compile/`, `numerics/`, `schemas/`, `verify/`, `models/c1/`, `application/` have an empty diff.
- **May move:** the column's refusal *message* for non-admitted providers (its cause code does not move; S03 A04's
  `"SYN-001 only"` assertion is amended, §4.8). Nothing else that exists today.
- **New results** (Wilson) are deterministic and bit-reproducible on one architecture; across architectures they are
  compared by registered tolerances (libm `exp`/`log` may differ by an ulp; S10 Amendment 5 A5-2's practice).

### 2.4 Measured facts the design rests on (`measured.txt`)

| # | Fact | Number |
| --- | --- | --- |
| M-a | Constant-β point (§4.3), real records, 11 feeds × β ∈ {0, 0.1, 0.5, 0.9, 1} | converges everywhere; max 61 iterations, worst rate 0.614 (ethanol z = 0.5, β = 1); last step ≤ 9.95e-14 |
| M-b | Same at the 13 E-2 states (verification records, band 1.4e-8 to 6.2e-7 K wide) | converges everywhere; max 29 iterations, rate ≤ 0.47; every state's T lies inside the computed band |
| M-c | Bubble-point sweeps with K at the previous sweep's x (ω = 1) | C-MW 37 sweeps; **C-EW does not converge** in 2000 (`\|ΔT\| = 15 K`, `\|Δx\| = 0.40`) |
| M-d | Same, x relaxed by ω = 0.5 | C-MW 45, C-EW 62 sweeps to `\|ΔT\| ≤ 1e-9 K`, `\|Δx\| ≤ 1e-12` |
| M-e | C-MW root (scipy, registered definition) | x_D = 0.99413, x_B = 0.00392; feed pinch stages 10–14; min `\|K_i − 1\|` 0.0089 |
| M-f | C-EW root | x_D = 0.81977 below the model azeotrope x_E = 0.88144 at 351.326 K; feed pinch stages 10–17; min `\|K_i − 1\|` 0.022 |
| M-g | Cost | `evaluate_phase` 29–31 μs; one TP flash 1.9 ms (95 SS iterations at a two-phase state) |

M-e and M-f mean the registered column cases never enter the E-2 regime (`|K − 1| ≲ 1e-4`) and do not need the band
route at their ends; the band route is the PH kernel's robustness path, exercised by the E-2 and near-pure PH targets.

### 2.5 Parallel and device contract

None: the code is serial Python, single-threaded per call; providers are thread-safe and stateless. No GPU.

---

## 3. Decisions and rejected alternatives

### D1. An identity allow-list of equilibrium forms replaces S11 for the column (R-760)

**Decided.** `equilibrium_form(provider)` reads `describe()` and returns a form object or `None`:

| `(provider_id, reference_convention)` | Form | Extra checks |
| --- | --- | --- |
| `("syn001", "SYN-001-ref-v1")` | `syn001-lnK-TP` | none (today's S11 pass condition) |
| `("wilson-ig-v1", "WILSON-IG-ref-v1")`, `("wilson-ig-v1", "S10-VER-ref-v1")` | `gamma-phi-ig-v1` | §4.1 capability and vapour-identity checks |
| anything else | `None` | — |

**Rejected.**
- *A capability rule ("declares `∂/∂n`").* `pr-c1-v1` and `pr-lib-v1` declare composition derivatives too; they are
  φ–φ, so a γ–φ K-block would ignore `ln φ^V(y)` and answer silently wrong. Capability cannot see the model class; S11
  chose identity for the same reason.
- *An adapter that makes Wilson offer `lnK` and `h_<c>`.* Every call site not yet migrated probes K at a
  composition-neutral or feed composition; an adapter would make each of them silently wrong. Without the adapter,
  Wilson's refusal of `lnK` (`unknown_property`) and its missing `h_<c>` keys are a **tripwire**: an unmigrated site
  fails loudly. The design keeps the tripwire on purpose (§4.12).

### D2. K at the liquid composition; mixture enthalpy flows (R-761)

**Decided** as §0 item 2. **Rejected:** *a generic φ–φ K-block with vapour inputs `(l, v, T, P)`* — a φ–φ bubble row
and a φ–φ band need incipient-vapour variables that no admitted provider needs; deferred to the first φ–φ liquid
provider. *Per-component enthalpy blocks from pure probes* — exact only because h^E = 0; the mixture block is exact for
any `h`, costs one call, and follows the C1 precedent.

### D3. The constant-β point (R-762)

**Decided** as §4.3. **Rejected:**
- *Nested bisection in T with an inner x-iteration per T* — the same fixed point, ten times the evaluations.
- *Newton on `(T, x)` per β* — fewer evaluations, but needs a globalisation and a fallback; two algorithms where one
  measured algorithm suffices (M-a, M-b).
- *Warm starts across β* — would make `T(β)` depend on the call history; every band point starts cold at `x = z`.

### D4. Band-first PH route for composition-dependent forms (R-763)

**Decided** as §4.5. **Rejected:**
- *Today's order (bracket on the TP flash, band route as fallback).* Inside an E-2 sliver the TP flash at a fixed T
  is intrinsically ill-conditioned (`∂β/∂T ≈ 1e8 K⁻¹`, S10 spec §14), returns `not_converged`, and the kernel surfaces
  it before the band route can run. Its cost is no lower (≈ 50 flashes × 1.9 ms).
- *Today's order with "TP `not_converged` ⇒ band route ⇒ re-bracket on the far side".* Three fallbacks in place of a
  region decision that is a theorem (§4.6).

### D5. E-2 is remedied in the PH flash; the provider's TP flash is unchanged (R-764)

**Decided** as §4.11. **Rejected:** *a conditioning-tied stop in the TP flash* — the floor estimate
`u‖G‖/min|K − 1|` carries an unregistered safety factor and a wrong factor accepts an unconverged split; the stop would
return `ok` with ≈ 1e-6 relative error in β, worse than any other `ok` flash; and it changes `wilson-ig-v1`'s
implementation hash, re-opening S10's evidence and review, for a consumer that no longer needs it.

### D6. The column's K-block, dormant convention and enthalpy blocks (R-765)

**Decided** as §4.7. **Rejected:** *K at the stage's mixed feed `m_j`* (wrong function); *regularising the liquid
(`l + ε`)* (changes the function and quantises the exact path); *refusing at a dormant liquid* (the float evaluator
evaluates every block at every state, including stages whose regime pins `l = 0`, so a refusal would abort valid
VAPOR-regime evaluations).

### D7. Composition relaxation ω = 1/2 in the sweeps (R-766)

**Decided** as §4.9. **Rejected:** *undamped lagged K(x)* (M-c: C-EW oscillates); *a homotopy from Raoult K to Wilson
K* (a block parameter and a new continuation path in the compiled problem, where a one-line damping suffices, M-d).

### D8. Scope of admitted specifications and units (R-767)

**Decided:** §0 item 8. `temperature` needs S06 §4's band (`stage_band`), a SYN-001 closed form that is wrong for a
mixture with an azeotrope (ethanol–water boils below both pure components); `purity` and `recovery` run S06's inverse
machinery, which no registered case exercises for this form. Refusing them is honest and reversible.

### D9. References (R-768)

A 50-digit generator is the independent expectation (S08 WO-G's practice): it shares no code with the column and needs
only S10's closed forms. IDAES `TrayColumn` with S10's matched Wilson inputs is possible but is a separate
qualification with its own ladder; it buys an R01 cross-implementation comparison, which is Frank's call (§7 Q2).

---

## 4. The design

### 4.1 Equilibrium forms (`models/syn001/equilibrium_form.py`, new)

```text
FORM_SYN001 = "syn001-lnK-TP";  FORM_GAMMA_PHI_IG = "gamma-phi-ig-v1"
ADMITTED = {("syn001","SYN-001-ref-v1"): FORM_SYN001,
            ("wilson-ig-v1","WILSON-IG-ref-v1"): FORM_GAMMA_PHI_IG,
            ("wilson-ig-v1","S10-VER-ref-v1"):   FORM_GAMMA_PHI_IG}

equilibrium_form(provider) -> EquilibriumForm | None
admission(unit, provider, context) -> CascadeFailure | None     # the column's S11 replacement
```

- `EquilibriumForm` is a frozen dataclass: `form_id`, `composition_dependent: bool`, `components`, `domain` (the
  provider's `domain["T"]`, `domain["P"]`), `provider_id`, `reference_convention`. No behaviour lives on it; the
  primitives are module functions in §4.2–§4.4 that take the provider.
- `equilibrium_form` reads `describe()` only (metadata). It is called by each dispatching function (§4.12). It returns
  `None` for anything outside `ADMITTED`; **the procedural kernels treat `None` exactly as SYN-001** (today's code
  path), so a non-admitted provider behaves exactly as before S10-C everywhere except the column's admission.
- `admission` (called where `property_method_refusal` is called in `column.validate`, before R1):
  1. `form is None` → `CascadeFailure("CAPABILITY_UNAVAILABLE", "unsupported(column_property_method:<id>)", msg)`,
     no evaluation, `msg` = today's text with the supported scope rewritten as "SYN-001 (provider_id 'syn001',
     reference_convention 'SYN-001-ref-v1') and wilson-ig-v1 (reference conventions 'WILSON-IG-ref-v1',
     'S10-VER-ref-v1')".
  2. `FORM_GAMMA_PHI_IG`: require `phases ⊇ {LIQUID, VAPOR}`, `properties ⊇ {h} ∪ {lnphi_<c>}`, `flashes ∋ "TP"`,
     `derivative_order[name] ≥ 1` for `T`, `P` and every `n_<c>`. Missing → the same cause, message
     `"<id> declares wilson-ig-v1's identity but not its capabilities: missing [<names>]"`, no evaluation.
  3. `FORM_GAMMA_PHI_IG`, the **vapour-identity check**: one `evaluate_phase` of `VAPOR` `lnphi_<c>` with derivatives
     `(T, P, n_<c>…)` at `n = (1.0,)*C`, `T = (T_min + T_max)/2`, `P = (P_min + P_max)/2`. Every value and every
     derivative must be exactly `0.0`; otherwise the same cause, message `"vapour ln phi is not identically zero"`.
     (It turns the allow-list's premise, `ln φ^V ≡ 0`, into a checked fact; it costs one call.)
  4. The specification-kind rule (§4.8) is a separate check after S1–S10, not part of admission.
- The cascade's `property_method_refusal` (cascade.py:397) is **not edited**; `cascade.validate` keeps calling it.

### 4.2 The γ–φ-IG primitives (`models/syn001/gamma_phi.py`, new)

All take `(provider, …, context)`; all raise `BandError(status, message)` (the existing class in `saturation_band`) on
a provider refusal, so callers keep their typed mapping.

- `ln_k(provider, T, P, liquid, context, *, derivatives=()) -> (values, d_T, d_n)`: one `evaluate_phase(LIQUID,
  ("lnphi_<c>"…), derivatives)` at `StreamState(n=liquid, T, P)`; `values[i] = result.values["lnphi_<c_i>"]`.
  `liquid` must be flowing (`sum(liquid) > 0.0`); a dormant liquid is a caller defect (`ValueError`). It may be a
  composition (sums to ≈ 1) or flows; the provider normalises.
- `enthalpy_flow` (mixture): dormant → `("ok", 0.0, "")`, no call (ADR 0001 D3.1); else one `evaluate_phase(phase,
  ("h",))`, value `state.total_flow * result.values["h"]` (`total_flow = sum(n)` in component order, the provider's
  own sum).
- `enthalpy_and_slope(state, phase)` for `single_phase_admissible`: `Ḣ = n_tot h`, `dḢ/dT = n_tot ∂h/∂T` from one call
  with `derivatives=("T",)`.

### 4.3 The constant-β point (`gamma_phi.band_point`)

**Definition.** For flowing `n`, `P`, `β ∈ [0, 1]`: find `T` and a liquid composition `x` with

```text
x_i = z_i / D_i,   D_i = 1 + β (K_i(T, P, x) − 1)      for i ∈ F,   x_i = 0 otherwise
g(T; x) = Σ_{i∈F} z_i (K_i − 1)/D_i = 0
```

At a solution `Σ x_i = 1` (because `Σ z_i(K_i − 1)/D_i = (1 − Σ z_i/D_i)/β` for `β > 0`), the split
`v_i = n_i β K_i/D_i`, `l_i = n_i (1 − β)/D_i` (today's `band_split`) has liquid composition `x`, and the vapour
`y_i = K_i x_i`. `β = 0` is the bubble point (`x = z`, `Σ z_i K_i(T, z) = 1`). `β = 1` is the dew point: `x_i ∝ z_i/K_i`
is the liquid-trial stationary point of S10 §5.4 step 3 and `g = 1 − Σ z_i/K_i = tm*`. One flowing component: `x = e_c`,
`g = 0 ⇔ K_c = 1 ⇔ T = T_sat` for every β.

**Algorithm** (deterministic; every evaluation is `ln_k` at the stated `(T, x)`):

```text
z = n / n_tot (binary64);  F = {i : z_i > 0};  x⁰ = z
if β == 0:   T, pos = Tsolve(x⁰, start = midpoint);  K = K(T, x⁰);  return (T, x⁰, K, pos, 1)
for m = 1 … BETA_SS_MAX:
    T^m, pos = Tsolve(x^{m−1}, start = T^{m−1} or the midpoint for m = 1)
    K^m      = K(T^m, x^{m−1})                         # from Tsolve's returned evaluation
    x̃_i      = z_i / (1 + β (K^m_i − 1)) (i ∈ F), 0 otherwise;   x^m = x̃ / Σ x̃
    s        = max_{i∈F} | ln K_i(T^m, x^m) − ln K^m_i |   # this evaluation is the next Tsolve's start
    if s ≤ DELTA_BETA: return (T^m, x^m, K^m, pos, m)  # K^m: the K that produced x^m (S10 §5.4 4(c))
raise BandError("not_converged", "constant-beta point: no stop in 1000 iterations; last step <s!r>")
```

`Tsolve(x, start)` finds the root of the frozen-x function `g(·; x)` on `[T_min, T_max]`, which is strictly increasing
(each `K_i` increases with T because `d ln P_i^sat/dT > 0`, and each summand increases with `K_i`):

```text
evaluate g, g' at start (g' = Σ z_i K_i ∂lnφ_i/∂T / D_i², from the same call with derivatives=("T",))
lo, hi = T_min, T_max with unknown values; maintain the sign bracket from every evaluation
repeat (budget MAX_TEMPERATURE_EVALUATIONS = 200 evaluations, the existing constant):
    if g == 0: return t
    if the bracket is two adjacent doubles: return the end with the smaller |g|, the lower on a tie
    t' = t − g/g'
    if t' outside the open bracket, or the bracket has not halved over the last two steps: t' = midpoint
    if t' lies beyond a bracket end whose value is unknown: evaluate that end first;
        g(T_min) > 0 → return (T_min, "below");  g(T_max) < 0 → return (T_max, "above")
    if t' == t: t' = the adjacent double towards the root
    evaluate g, g' at t'
budget exhausted → BandError("not_converged", …)
```

- **Positions.** A step that returns `below`/`above` clamps `T^m` to that domain end and the iteration continues; the
  position reported is the **last** step's. `below`/`above` results carry no temperature (today's `BandTemperature`
  contract). At `β = 1` the clamped fixed point is the liquid trial at the domain end, so the sign is exact; at
  intermediate β it is exact for binaries (§4.6) and an assumption otherwise (failure is typed, never wrong: the
  band route's answer is accepted only on the closure rows).
- **Constants** (registered by WO-S with their floors): `DELTA_BETA = 1e-13` (ln K rounding floor 3.55e-15, S10 §5.6:
  28×; measured last steps ≤ 9.95e-14); `BETA_SS_MAX = 1000` (measured ≤ 61: 16×).
- **No E-2 floor.** β is a parameter here, never solved from K, and `|∂ ln x_i/∂ ln K_i| = β K_i/D_i ≤ 1`, so the step
  noise is `≈ ‖G‖u`, not `u‖G‖/min|K − 1|`.
- **Return type.** `saturation_band.BandTemperature` gains one field `liquid: tuple[float, ...] = ()` (default keeps
  every SYN-001 construction unchanged); `k_values` is `K^m` for all C components (an absent component's value is the
  infinite-dilution K from the same evaluation; `band_split` gives it `0.0, 0.0`); `evaluations` counts every
  `evaluate_phase`.

### 4.4 The fixed-T incipient liquid (`gamma_phi.incipient_liquid`)

For the orchestrator's single-phase VAPOR admissibility (§4.10): S10 §5.4 step 3 in the unit layer. `W_i⁰ = y_i/K_i(T,
y)`; `w = W/ΣW`; `W'_i = y_i/K_i(T, w)` for `i ∈ F`; `s = max |ln W' − ln W|`; stop at `s ≤ 1e-13` within 1000
iterations, else `BandError("not_converged")`. Returns `ΣW` (the dew value: `ΣW ≤ 1` ⇔ the vapour is stable) and `w`.

### 4.5 `ph_state` for a composition-dependent form

`ph_state(provider, flows, P, H*, context, max_evaluations)` keeps its signature, its preamble (dormant `ValueError`,
length check) and step 1 (the P-domain refusal, same code and message). Then:

```text
form = equilibrium_form(provider)
if form is None or not form.composition_dependent:  <today's body, unchanged>
```

Otherwise:

**One flowing component.** Today's step 2 with `_ln_k` evaluated by `gamma_phi.ln_k` at `liquid = n` (exact: γ = 1 at a
pure liquid) and enthalpies by the dispatching `enthalpy_flow`. `_saturation_split`'s lever rule is unchanged. A target
below `Ḣ^L(T_sat)` or above `Ḣ^V(T_sat)` goes to the liquid or vapour route below on `[T_min, T_sat]` or
`[T_sat, T_max]`, not to a TP-flash bracket. No sign change of `ln K` on the domain → `T_sat` outside it: the stream is
single-phase on the whole domain, liquid if `ln K_c(T_max) < 0`, vapour if `ln K_c(T_min) > 0`.

**Two or more flowing components** (`b0`, `b1` are `band_point(n, P, 0)` and `band_point(n, P, 1)`; a `BandError`
returns `_surfaced(status, "band end", message)`):

1. **Domain-end enthalpies.** `H_lo = Ḣ_TP(n, T_min)`: `Ḣ^L(n, T_min)` if `b0` is `inside` or `above`; `Ḣ^V(n, T_min)`
   if `b1` is `below`; otherwise (`T_min` inside the band) `tp_state` at `T_min` (the provider's TP flash; a non-`ok`
   status is surfaced as today). `H_hi` symmetrically with `b1` `inside`/`below` → `Ḣ^V(n, T_max)`, `b0` `above` →
   `Ḣ^L(n, T_max)`, else `tp_state` at `T_max`.
2. **Outside the domain.** `H* < H_lo` → `ph_outside_domain(below)`; `H* > H_hi` → `ph_outside_domain(above)`; today's
   codes and message forms.
3. **The region.** `H_b = Ḣ^L(n, T_b)` if `b0` is `inside`, `H_hi` if `above`, `−∞` if `below`. `H_d = Ḣ^V(n, T_d)` if
   `b1` is `inside`, `H_lo` if `below`, `+∞` if `above`.
   - `H* ≤ H_b` → **liquid route**: `bracketed_root` (today's bisection, budget `max_evaluations`) of
     `Ḣ^L(n, T) − H*` on `[T_min, T_b]` (`T_max` when `b0` is `above`). Candidate split: `phase_signature = "LIQUID"`,
     liquid `= n` bitwise, vapour dormant at `(T*, P)`, `vapor_fraction = 0.0`, `enthalpy_flow = Ḣ^L(n, T*)`,
     `k_values = {}`, `iterations = 0`, `message = ""`. Route label `"bracket"`.
   - `H* ≥ H_d` → **vapour route**, symmetric on `[T_d, T_max]` (`T_min` when `b1` is `below`), `vapor_fraction = 1.0`.
     Route `"bracket"`.
   - otherwise → **band route**: today's `_band_route` (bisection on `β ∈ [0, 1]` of `F(β) = H(β) − H*`, its sign
     oracle `−∞`/`+∞` for a `below`/`above` band point, `MAX_BAND_EVALUATIONS = 64`, `BETA_WIDTH_FLOOR = 2⁻⁶⁰`) with
     `band_point` in place of `band_temperature` and `band_split(n, K^m, β)`. Route `"band"`.
4. **Acceptance** on `_closure_rows`, with one change for this form: K is `gamma_phi.ln_k` at
   `(T*, P, candidate.liquid.n)`; when the candidate's liquid is dormant the equilibrium value is `0.0` exactly and no K
   is evaluated (every row `v_i L − K_i l_i V` is `v_i·0 − K_i·0·V`). Material and energy rows unchanged. Accepted →
   `PHState("ok", …)`. Not accepted → `ph_ill_conditioned` with this one route's rows (`_ill_conditioned`).
   There is **no** fallback between routes: the region is decided by §4.6's theorem.
5. `PHState.evaluations` = the chosen route's outer evaluations (as today's routes count them).
6. A single-phase route whose target lies outside `[Ḣ(T_lo), Ḣ(T_hi)]` of its interval refuses
   `ph_outside_domain(below|above)` with today's message forms (this can arise only on the one-component path; on the
   multi-component path step 2 has already refused it).

### 4.6 Why the band-first route is correct (the `specifier` writes the derivation; WO-S)

For a provider of the γ–φ-IG class with `Δh_i > 0`, `c_p,i^0L > 0`, `c_p,i^ig > 0` on the domain (§2.1):

- **T1 (bubble).** `Σ z_i K_i(T, z)` is strictly increasing in T, so `T_b` is unique; below it the liquid is stable
  (`tm_V = 1 − Σ z_i K_i(T, z) > 0`): exactly S10's TP flash step 2 verdict.
- **T2 (dew).** The liquid-trial minimum `tm*(T)` is strictly increasing: by the envelope theorem
  `d tm*/dT = Σ W_i* d ln P_i^sat/dT > 0`. So `T_d` is unique and above it the vapour is stable (S10 step 3's verdict).
- **T3 (monotone enthalpy).** At fixed `(n, P)` along the stable state, `dḢ_TP/dT ≥ n_tot c_p,frozen > 0`. The latent
  part is `T aᵀ (∂²G/∂ξ²)⁻¹ a ≥ 0` with `a = ∂²G/∂ξ∂T`, `ξ` the split, because the two-phase Gibbs energy is strictly
  convex in the split (S10 §4.1). So the PH root is unique, the three regions are ordered by enthalpy, and the region
  decision of §4.5 step 3 is exact. This replaces T05 §4.2's SYN-001 derivation for this class (ADR 0011 D1).
- **T4 (two-phase answers are global).** Any split with `0 < β < 1` satisfying the equilibrium rows is the global
  minimum at `(T, P, n)` (S10 §4.2 item 3), so an accepted band-route answer is *the* answer.
- **T5 (binary band).** For a binary on one side of an azeotrope, `β(T)` is strictly increasing on `[T_b, T_d]`
  (Gibbs–Konovalov: `dβ/dT = −[(1 − β)x′ + βy′]/(y − x) > 0`), so `T(β)` is unique and the band route's `H(β)` is
  monotone. For `C ≥ 3` this is not proved; the band route then converges or ends typed, never wrong (T4 + acceptance).

### 4.7 The column's compiled graph (`models/syn001/gamma_phi_blocks.py`, new)

**`GammaPhiLnKBlock(provider, components, context, *, block_id)`** — the K-block.
- `input_ids = (*(f"n_{c}" for c), "T", "P")`; `output_ids = (f"lnK_{c}" for c)` (so `equilibrium_row` and
  `bubble_row` are reused verbatim); `jacobian_pattern` dense `C × (C + 2)`.
- `values(u)`: `l = u[:C]`. Flowing → `evaluate_phase(LIQUID, lnphi_<c>…)` at `n = l`, outputs the `lnphi` values.
  **Dormant** (`sum(l) == 0.0` after signed-zero normalisation) → the same request at the probe `n = (1.0,)*C`.
- `jacobian(u)`: flowing → derivatives `(n_<c>…, T, P)` at `n = l`; entry `(i, j) = d["lnphi_<c_i>"]["n_<c_j>"]`,
  `(i, C) = …["T"]`, `(i, C+1) = …["P"]`, **bitwise the provider's numbers**. Dormant → the probe's `T`, `P` entries and
  `0.0` (stored) in every `n` column.
- **Why the dormant convention moves nothing.** Every row that reads a K output multiplies it by a liquid flow of the
  same block's input: `v_i L − K_i l_i V` and `Σ K_i v_{2,i} − V_2`. At a dormant input those products are `0·K` and
  their derivatives `l_i ∂K_i/∂(·) = 0`, whatever the block returns; and `l_i ∂ ln K_i/∂l_j = x_i (G_ij + 1)` stays
  bounded as `L → 0`, so the rows are Lipschitz across it. The convention exists only so the float evaluator, which
  evaluates every block at every state (`system_residuals` → `row_values`), never sends a dormant state to the provider.
- Errors as `blocks._unwrap`: `out_of_domain` → `DomainError`, other non-`ok` → `RuntimeError`.

**`MixtureEnthalpyFlowBlock(provider, components, phase, context, *, block_id)`** — one output `"H"`.
- Inputs `(n_<c>…, T, P)`, pattern dense `1 × (C + 2)`.
- Flowing: `H = n_tot h`; `∂H/∂n_j = h + n_tot ∂h/∂n_j`; `∂H/∂T = n_tot ∂h/∂T`; `∂H/∂P = n_tot ∂h/∂P` (as
  `models/c1/blocks.py`).
- Dormant: `H = 0.0`, no evaluation at the dormant state; `∂H/∂n_j = h(T, P, e_j)` from one pure-probe call per
  component (`n = e_j`, the block's phase), `∂H/∂T = ∂H/∂P = 0.0`. Exact here because `Ḣ` is linear in `n`; for any
  provider it is the derivative along each axis.

**Wiring in `column.declared_rows`.** Dispatch once on `equilibrium_form(provider)`:
- SYN-001 → today's `LnKBlock` and `EnthalpyFlowBlock`, byte-identical declarations.
- γ–φ-IG → each equilibrium stage `j`'s `lnk_block` is a `GammaPhiLnKBlock` with `block_inputs = (*(liquid_id(unit,
  j, c) for c), T_j, P_j)`; a total condenser's block reads `(*(vapor_id(unit, 2, c) for c), T_c, P_c)` (the condensate's
  composition is `v_2`'s). Each `enthalpy_block` is a `MixtureEnthalpyFlowBlock` returning the 1-tuple
  `(f"{block_id}.H",)`; energy rows already concatenate key tuples (column.py:1334, 1437–1438), so no row changes.
  Block ids keep today's scheme (`lnk_block_id`, `enthalpy_block_id`).

### 4.8 Validation and refusals (`column.validate`)

- S11 → `admission(unit, provider, context)` (§4.1), same position (before R1).
- **SYN-001 constants on the path.** Every use of `T_MIN`, `T_MAX` (column.py:666, 1102–1103, and any other the WO-1
  inventory finds) reads `form.domain` when the form is γ–φ-IG; the SYN-001 path keeps the constants.
- **Specification kinds.** For γ–φ-IG, an end specification of kind `purity`, `recovery` or `temperature` returns
  `CascadeFailure("CAPABILITY_UNAVAILABLE", "unsupported(column_specification:<kind>:wilson-ig-v1)", <message naming
  the admitted kinds>)` after S1–S10 and before I1. `stage_band` and `saturation_temperature` are never reached.
- `energy_precheck` (R7, duty-only columns) uses the dispatching enthalpy and `form.domain`.
- **Test amendment:** S03 A04 (`tests/test_s03_s11_refusal.py:129`) asserts `"SYN-001 only" in refused.message`; it is
  amended to assert the new scope text. Its cause assertion and the cascade test (`:136`) are unchanged.

### 4.9 Initialisation for the γ–φ-IG form

- **`profile_initial` (S02 §6).** `T_a`, `T_b` from `band_point` at `PROFILE_BETAS = (0.1, 0.9)` (via the dispatching
  `band_temperature`). The Thomas pass evaluates `K_ij = K_i(T_j⁰, P_j, z)`: the total feed composition on every stage.
- **`bubble_point_endpoint` / `sweep_flows` (S02 §18.2).** Let `x̄_j⁰ = l_j/L_j` from the profile's Thomas solution.
  Sweep `m`: `K_ij = K_i(T_j, P_j, x̄_j^{m−1})`; Thomas as today; `T_j` ← the bubble temperature of `l_j^m` (`band_point`
  at β = 0, exact); `x_j^m = l_j^m/L_j^m`; `x̄_j^m = ω x_j^m + (1 − ω) x̄_j^{m−1}` with **`SWEEP_RELAXATION = ω = 0.5`**.
  Stop when `max_j |ΔT_j| ≤ SWEEP_TOLERANCE` (1e-9 K, unchanged) **and** `max_{j,i} |x_ij^m − x̄_ij^{m−1}| ≤
  SWEEP_COMPOSITION_TOLERANCE = 1e-10`; cap `MAX_SWEEPS = 500` (unchanged; measured 45 and 62). The final flows use
  `x̄` at the stop; the condenser's bubble temperature uses `x = v_2/V_2`. The SYN-001 path is unchanged and applies
  neither the relaxation nor the composition stop.
- **Stage B (S08 `column_blocks`).** `_core_flows` uses the same relaxed K over the core's sweeps; `_bubble` is
  `band_point` at β = 0; `_enthalpy` dispatches. Exact zeros on the L-block are unchanged.
- `_initial_state` and any other enthalpy use dispatch through `enthalpy_flow` / `cascade._enthalpy_flow`.
- `cascade._k_values(provider, context, components, T, P, *, liquid=None)` gains the keyword; SYN-001 ignores it (same
  call as today); γ–φ-IG requires it (`ValueError` if `None`).

### 4.10 Acceptance and the phase contract

- **Column §8** (`column_solve`): `_saturation_pairs` (item 6) calls `band_temperature` at β = 0 on `l_j` (exact) and at
  β = 1 on `v_j` (constant-β point); `_admissibility` → `single_phase_admissible` (dispatching). No code change beyond
  the dispatch inside those functions.
- **Orchestrator `_admissible`** (region.py:700, K03 §8.2), the one edit in `orchestrator/`: for γ–φ-IG, `LIQUID` →
  `value = Σ x_i K_i(T, P, x)` with `x` the liquid side's composition (`gamma_phi.ln_k`); `VAPOR` → `value = ΣW` from
  `incipient_liquid(T, P, y)`; admissible iff `value ≤ 1 + ε`; a `BandError` becomes the `VerifierError` the screen
  already converts to `invalid_trial_state`. `ZERO_FLOW`, `TWO_PHASE`, SYN-001 and pr-c1 branches unchanged.
- `_band_regime`, `_split_enthalpy`, `_ph_closure`, `_kernel`: unchanged code; they reach the new form through the
  dispatching `band_temperature`, `enthalpy_flow`, `tp_state` and `ph_state`. The TP-flash fallback (`_kernel`) stays
  the provider's flash.

### 4.11 E-2

- The remedy is the constant-β point (§4.3): β exact, `T` solved, `x` from β. The PH flash reaches the sliver only
  through the band route (§4.5), never through a TP flash at a fixed T inside it.
- The provider's TP flash is unchanged; its `not_converged` with `UNKNOWN` near an azeotrope stays the correct TP
  answer. Remaining exposure, each typed on failure: `ph_state` step 1 calls a TP flash only at a domain end lying
  inside the band; `single_phase_admissible` flashes a single-phase stream at its own T; the orchestrator's TP fallback.

### 4.12 Dispatch points, the tripwire and the SYN-001 path

Dispatch happens **at the top** of existing functions, before any arithmetic, with the SYN-001 body textually unchanged
below it:

| Function | γ–φ-IG branch |
| --- | --- |
| `tp_state.enthalpy_flow` | `gamma_phi.enthalpy_flow` |
| `tp_state.single_phase_admissible` | mixture `Ḣ` and slope; the rest of the body as today |
| `saturation_band.band_temperature` | `gamma_phi.band_point` |
| `saturation_band.outside_the_degeneracy_window` | the β = 0 test only, K at the stream; the β = 1 side returns "not decided" (`False`) |
| `cascade._k_values` | `gamma_phi.ln_k` at `liquid` |
| `ph_kernel.ph_state`, `_closure_rows` | §4.5 |
| `region._admissible` | §4.10 |
| `column.validate`, `declared_rows`, `profile_initial`, `energy_precheck`; `column_solve.sweep_flows`, `bubble_point_endpoint`; `column_blocks._core_flows` | §4.7–§4.9 |

`degeneracy_distance`, `tp_state`, `cascade._enthalpy_flow`, `_band_regime`, `_split_enthalpy` need no branch (they
call dispatching functions).

**The tripwire.** Wilson refuses `lnK` (`unknown_property`) and returns no `h_<c>` key. Any call site this table misses
fails loudly when reached. WO-1 starts by producing the full inventory (`grep` for `"lnK"`, `lnK_`, `h_{`, `T_MIN`,
`T_MAX`, `REFERENCE_CONVENTION`, `syn001_thermo` over the modules reachable from `ph_state` and `solve_column`) as a
table in `docs/S10C_DECISIONS.md`, classified by this section's rules; WO-4's C-MW/C-EW solves prove every reached
site migrated.

**SYN-001 path.** The dispatch adds `describe()` calls and nothing else; every provider call, its order and every
arithmetic operation on the SYN-001 path is unchanged. If any registered test counts `describe()` calls, stop and
escalate (§7 Q7).

### 4.13 Performance

Costs at M-g's 30 μs per call: a band point ≈ 20 SS steps × ≈ 5 evaluations ≈ 3 ms; a two-phase `ph_state` ≈ 2 band
ends + 64 band points ≈ 0.2 s; a single-phase `ph_state` ≈ 10 ms. Column Newton iterations add one K-block and two or
three enthalpy calls per stage (≈ 2 ms per residual-plus-Jacobian at 19 stages). Targets (G9): two-phase `ph_state`
median ≤ 0.3 s; each of C-MW and C-EW ≤ 120 s wall; SYN-001 column suites within +10 % of the merge base. Above a target:
record, do not tune, escalate (§7 Q6).

---

## 5. Work orders

Order: **WO-S ∥ WO-1 → WO-2 → WO-3 → WO-4 → WO-5 → `reviewer`**. WO-2 and WO-3 touch disjoint files and may run in
parallel worktrees (at most two agents at a time). Each WO is ≈ 150k context; an engineer at the cap commits, writes
where it stopped in `docs/S10C_DECISIONS.md` and ends. Every code WO runs G1 and G2 before its last commit.

| WO | Role | Scope | Acceptance |
| --- | --- | --- | --- |
| **WO-S** | `specifier` | `docs/derivations/S10C-spec.md`: T1–T5 written as derivations; the case amendments (C-MW, C-EW to S02's specification set: condenser `reflux_ratio`, reboiler `bottoms_rate` = F − D; feed saturated liquid at the generator's bubble T; the stage-count convention); registered states and tolerances for G3–G7; numbered assertions `S10C.A01…`; the rulings on Q-N5 and on §7 Q4/Q5. `docs/derivations/scripts/s10c_reference.py` (`--check`) → `benchmarks/s10c/reference_values.yaml`: 50-digit C-MW/C-EW roots, band points, PH targets (liquid, vapour, two-phase binary and ternary, near-pure 1e-10, one component, the 13 E-2 states with `H*` from the 50-digit TP split at the state's T, the ideal limit Λ ≡ 1, out-of-domain targets), positivity claims on both record sets. | `--check` byte-identical; the spec's assertions map onto G3–G8 |
| **WO-1** | `opus-engineer` | The call-site inventory (§4.12). `equilibrium_form.py`, `gamma_phi.py` (`ln_k`, mixture enthalpy, `band_point` with `Tsolve`, `incipient_liquid`), `BandTemperature.liquid`, the dispatch in `saturation_band` and `tp_state`. `scripts/s10c_identity.py` (G1). Tests: band-point fixed-point residuals at convergence; the ideal limit (synthetic records with Λ ≡ 1: `T_b`, `T_d` against the closed forms `Σ z_i P_i^sat(T) = P`, `Σ z_i/P_i^sat(T) = 1/P` solved by bisection in the test); one component (`T_sat` from `ln P^sat = ln P`); positions at out-of-domain feeds; `band_point(β = 1)` against the provider's `stability(state, "VAPOR")`: `\|tm\| ≤ 1e-12` at `T_d`. | Tests pass; G1, G2 PASS; ruff, mypy clean |
| **WO-2** | `opus-engineer` | §4.5 in `ph_kernel.py`; `_closure_rows`; `region._admissible` (§4.10). Tests against WO-S's PH targets and E-2 states (G4, G5); mutation M3. | G4, G5, M3; G1, G2 |
| **WO-3** | `opus-engineer` | `gamma_phi_blocks.py`; `declared_rows` dispatch; `validate` (admission, domain constants, specification kinds, `energy_precheck`); the S03 A04 amendment; refusal tests (G8). Block tests (G6); mutations M1, M5. | G6, G8, M1, M5; G1, G2 |
| **WO-4** | `opus-engineer` | §4.9 (profile, relaxed sweeps, Stage B core); §4.10 column acceptance via the dispatch; C-MW and C-EW solves against WO-S's roots (G7); mutations M2, M4; a constructed Stage-B opening on a Wilson specification (exact zeros, mass balance); performance numbers (G9) into `docs/S10C_DECISIONS.md`. | G7, G9, M2, M4; G1, G2 |
| **WO-5** | `sonnet-implementer` | Registrations: `LIBRARY_ONLY_PROVIDERS["wilson-ig-v1"]` **stays**; the U02 rows (`benchmarks/t08/support_envelope.yaml:5622-5866`) that state the column's or the PH kernel's refusal of `wilson-ig-v1` restated as "library-level support (S10-C); flowsheet selection not offered"; the ledger entry (`depends_on: [S10, S08]`); `evidence/S10C/<commit>/manifest.json`; the T08 harvest; `docs/progress.md`. | T08's tests pass; manifest `tested` with the commands actually run |
| **review** | `reviewer` | WO-1…WO-4 against this note and WO-S's spec (residuals, derivatives, phase logic: CLAUDE.md requires it). | No must-fix open; then G10 and merge |

The `specifier` decides scientific content (registered states, tolerances, the case amendments, Q-N5). The build lane
decides nothing in §3–§4; a choice this note leaves open is logged as a `DECISION:` line in `docs/S10C_DECISIONS.md`,
isolated in its own commit, and batched for the review.

---

## 6. Verification gates

| Gate | Invariant | Measured how | Pass criterion | Configurations |
| --- | --- | --- | --- | --- |
| **G1** bit-identity | SYN-001 and non-admitted providers unchanged | `scripts/s10c_identity.py`, modelled on `scripts/s08_identity.py`: digests on `ffcb387f` (a detached worktree) and on the branch, two subprocesses each importing its own tree; per column/cascade configuration S08's fields; per `ph_state` call of the T05/T05b registered cases `PHState` (status, code, `float.hex(T)`, route, evaluations, residual, split flows hex). Then every existing `scripts/*_identity.py` (T02–T07, T05b, K05 structural, S08) as `scripts/gate.sh` runs them | `S10C-IDENTITY PASS n=<N> changed=[]`, every digest equal, no exception; every existing `scripts/*_identity.py` PASSes unchanged | S08's 52 configurations, T05/T05b `ph_state` calls; the older scripts' own sets |
| **G2** structure | frozen paths untouched | `git diff --stat ffcb387f..HEAD` | empty over `src/openflowsheet/{thermo,compile,numerics,verify,application}`, `src/openflowsheet/models/c1`, `schemas`; in `tests/` only new files, the S03 A04 amendment and WO-5's T08 registration counts. *(Amended 2026-10-26, R-795.)* G2 admits, by name, `src/openflowsheet/numerics/newton.py`, `tests/test_t06_w20_counters.py` and `tests/test_t07_interrupt.py` as changed by R-782 (WO-R2 `e88f72a9`), R-786 (WO-R6 `f23985bf`) and R-782 §4.7 item 4 (`fbba9643`). Every other frozen path stays untouched. | — |
| **G3** band point | §4.3 | against WO-S's band points | `\|T − T_ref\| ≤ 1e-9 K`, `max\|x − x_ref\| ≤ 1e-10`, iterations ≤ 100; positions exact; ideal limit to the same tolerances; `\|tm(T_d)\| ≤ 1e-12` | WO-S's registered states |
| **G4** PH kernel | §4.5 | against WO-S's PH targets | `ok`, registered route, `\|T* − T_ref\| ≤ 1e-9 K`, flows within `τ_flow`, rows accepted; out-of-domain targets typed with today's codes | WO-S's targets |
| **G5** E-2 | the remedy works | the 13 `NEAR_AZEOTROPE` states (`tests/test_s10_flash.py:564`), `H*` from WO-S | every one `ok` with route `"band"`, `\|T* − T_ref\| ≤ 1e-10 K`, `\|β* − β_ref\| ≤ 1e-9`, `max\|x − x_ref\|, max\|y − y_ref\| ≤ 1e-9` | verification records, 101 325 Pa |
| **G6** derivatives | residual and Jacobian describe one function | central differences, relative step `1e-6·max(\|u\|, 1)`, on both blocks | max relative error ≤ 1e-6 at every registered C-MW/C-EW stage state, a dilute liquid (x = 1e-8), an absent component, a near-azeotrope liquid; Jacobian entries bitwise the provider's derivatives; dormant convention values exact | as listed |
| **G7** columns | C-MW, C-EW roots | `solve_column` with `wilson-ig-v1` against WO-S's 50-digit roots | `CONVERGED`; §8 acceptance passes (item 6 ≤ 1e-4 K); `\|ΔT_j\| ≤ 1e-7 K`, `\|Δl_ij\|, \|Δv_ij\|, \|ΔD\|, \|ΔB\| ≤ 1e-9 mol/s` (WO-S may set other values from the generator's conditioning; it may not loosen them after a run). Recorded, not gated: Newton iterations and, where the trace carries residual norms, the observed order over the last three iterations | C-MW, C-EW as amended by WO-S |
| **G8** refusals | S11 for every other provider | `validate`/`solve_column` with pr-c1-v1, pr-lib-v1, iapws95-v1, coolprop-heos-v1 (where constructible) and spies: `("s03-spy", "SYN-001-ref-v1")`, `("syn001", "spy-ref")`, `("wilson-ig-v1", "spy-ref")`, `("wilson-ig-v1", "WILSON-IG-ref-v1")` without `lnphi`, and one whose vapour `lnphi` is non-zero | cause `unsupported(column_property_method:<id>)`, zero evaluations except the vapour-identity spy (exactly one); Wilson with `purity`/`recovery`/`temperature` → `unsupported(column_specification:<kind>:wilson-ig-v1)`; `cascade.validate` with Wilson → today's S11 failure | as listed |
| **G9** performance | §4.13 | wall times on the workstation | two-phase `ph_state` median ≤ 0.3 s; C-MW, C-EW ≤ 120 s each; SYN-001 S02/S08 suites ≤ +10 % | recorded in `docs/S10C_DECISIONS.md` |
| **G10** merge | the whole repository | `scripts/gate.sh`; CI | PASS; CI green on x86-64 and aarch64 | before merge |

**Mutations** (each must be detected by the named gate; recorded in the manifest):

| Id | Mutation | Detected by |
| --- | --- | --- |
| M1 | the K-block's `n` columns set to `0.0` | G6 (relative error ≥ 1e-2 at C-MW stages); record the Newton order and iterations of C-MW |
| M2 | the K-block evaluates at the probe `(1,…,1)` instead of `l` | G7 fails on C-MW and C-EW (not `CONVERGED`, or `\|Δx_D\| > 1e-3`) |
| M3 | `ph_state` for γ–φ-IG uses today's TP-flash bracket route | G5: at least one of the 13 states not `ok` or not accepted (if all pass by rounding luck, record it and add the review's 20-state set) |
| M4 | `SWEEP_RELAXATION = 1` | C-EW's endpoint ends `initialization_failed(…, sweeps_exhausted)` |
| M5 | the K-block forwards a dormant liquid to the provider | a counting spy sees a dormant request, or the VAPOR-regime evaluation raises |

---

## 7. Risks and open questions (each with a default)

| Id | Question | Needs | Default |
| --- | --- | --- | --- |
| Q1 | Should `wilson-ig-v1` become selectable in flowsheets (`SELECTABLE_BASES`)? | Frank's preference | **No: library level only** (R-709). A later package adds it with U02 reclassification |
| Q2 | Should S10-C add an IDAES `TrayColumn` comparison of C-MW/C-EW (an R01 cross-implementation comparison)? | Frank's preference (effort) | **Deferred**; the 50-digit generator is the expectation |
| Q3 | Should the S01 cascade and the other units (PH flash, valve, pump) accept `wilson-ig-v1` now? | Frank's preference (scope) | **No**; no registered case drives them. The cascade keeps S11; the units are unchanged |
| Q4 | Do C-MW and C-EW converge in Stage A with the real region solver? Both pinch at the feed (M-e, M-f) | fact (WO-4) | Run as specified, recovery included. If a case does not converge, record the trace, return the typed outcome, and escalate to the design lane; the `specifier` may amend the case (for C-EW, a larger reflux ratio). No tuning by the build lane |
| Q5 | Does the constant-β point converge beyond the measured states (ternary, strongly non-ideal, β near 1)? | fact | Cap 1000, typed failure; no acceleration in S10-C |
| Q6 | Do the performance targets hold? | fact (WO-4) | Record; if exceeded, escalate before optimising (memoised form resolution or warm starts are each a separate decision) |
| Q7 | Does any registered test count `describe()` calls on a SYN-001 path? | fact (WO-1) | Not expected. If one does, stop and escalate; do not change the test |
| Q8 | Q-N5: do S10-C's energy balances need a vapour non-ideality term? | `specifier`'s ruling | **The design does not need one**: it consumes the provider's `h`. A non-ideal vapour would be a new provider version and a new form (K-block with vapour inputs), not a change to this design |
| Q9 | Is ω = 1/2 adequate for S08's Stage B core sweeps? | fact | Use 1/2 everywhere; a failure ends typed (`initialization_failed`) |
| Q10 | Should `purity`, `recovery`, `temperature` specifications be offered for the new form? | Frank's preference (scope) | **No** in S10-C (typed refusal) |

**Limitations to record in the manifest.** The equilibrium tolerance is absolute (9.3e-8 (mol/s)²): the band route's
K, consistent to `DELTA_BETA`, adds `≈ n²·2.5e-14`, so streams above ≈ 1000 mol/s may end `ph_ill_conditioned`
(typed). T5 is proved for binaries only. Stage B for Wilson columns is constructed and tested at the opening level,
not on a registered solve. Wilson results are compared across architectures by tolerance, not bitwise.

---

## 8. Records

- **ADR 0049** (Proposed): amends ADR 0011 D1 (the PH kernel's provider class and its monotonicity argument) and ADR
  0012 D1–D2 (the band primitive and route order) for the composition-dependent form; replaces S03 §9 S11 for the column
  by the allow-list; no frozen interface changes.
- **Register** R-760…R-769 (R-737…R-759 are left for `main`'s next package and S09's R-740…R-752).
- **Build decisions:** `docs/S10C_DECISIONS.md`, one line each, `DECISION: <question> → <choice>. Alternative: <x>.
  Reversible by: <how>.`
