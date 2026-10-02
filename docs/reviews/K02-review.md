# K02 review — the six SYN-001 unit models, the TP-state kernel and the flowsheet

**Reviewer:** Fable 5.1, 2026-09-20 (the single Fable review pass for K02)
**Against:** `docs/briefs/K02-unit-models-review.md`; diff `1660051..b26f7e3` on `main`
**Authorities read:** derivation SYN-001 §2–§9, ADR 0001 D3–D6, ADR 0008 D3.3/D3.5/D4.1/D4.3/D4.4,
P02 spec §2.4–§2.6, `docs/K02_DECISIONS.md`, the four K02 test modules, the evidence manifest.
**What I ran:** the K02 suites and the whole suite (1003 pass) against an unmodified tree; the same
suites against one mutant on a scratch copy of `src` (finding M1); numerical probes of the label,
the mixer admissibility bound, the heater's regime check, and the lifted system at its trivial
root. No production file was modified. No `review.*` manifest field was set.

**Verdict.** The numerics that were measured are right: the row orientation, the D4.3 values, the
duties, the tear residual, the recycle invariance and the affine tear relation all check out, and
the P02-to-ADR-0008 sign reversal was applied consistently (balance rows negated, algebraic rows
unchanged). Three things must change before this is done: one verification gap that a
one-line mutation of the heater's equilibrium row walks straight through (M1), one identity
defect in the flowsheet label (M2), and one admissibility criterion that is sound at the
registered throughput but returns a wrong `ok` answer away from it (M3). None of the three makes
a registered number wrong; the first makes a claim of coverage false, the second breaks a
normative rule, the third leaves the unit's one defensive check defeatable.

---

## 1. Must-fix

### M1. The heater's lifted equilibrium and split rows are never checked at a two-phase state

`src/process_runtime/models/syn001/tp_state.py:360` (`_equilibrium_row`, used by the heater's
`HEAT-equilibrium` and by nothing else — the flash has its own copy at `flash.py:578`).

Every test that evaluates the heater's rows against a reference uses the **nominal** variant,
where the heater outlet is `LIQUID`: `tests/test_k02_heater_flash.py:635` and
`tests/test_k02_flowsheet.py:426` both set `S3.vap.* = 0`, `S3.V = 0`. At that state
`v_i L − K_i l_i V ≡ 0` for *any* `K_i`, any sign, any factor. The row's only non-trivial
exercise is its Jacobian sparsity.

**Measured.** Replacing the row body with `v_i L − l_i V` (K dropped) on a scratch copy of `src`
passes the three K02 suites (184/184) and the whole suite (**1003/1003**). Opus's 22-mutation
sweep of M2 did not include this row, and no test could have caught it.

**Minimal correction.** Parametrise `test_the_assembled_rows_vanish_at_the_reference_solution`
over all five variants, populating the lifted split from the reference's own
`heater_outlet_vapor_fraction`, `heater_outlet_x`, `heater_outlet_y` (registered for the three
variants whose heater outlet is two-phase — the derivation §6 calls them β_h, x_h, y_h). That
one change checks the heater's equilibrium rows at β_h = 0.1014 where they are informative,
checks the negative-duty variant's rows, and checks the `V = 0` and `L = 0` flash outlets in the
assembled system. Add a heater analogue of
`test_the_equilibrium_row_has_the_sign_its_statement_declares` (its sign is otherwise invisible).

### M2. The flowsheet label carries pinned inputs, so `model_version` changes with `r`

`src/process_runtime/models/syn001/flowsheet.py:182–184`.

ADR 0008 D4.1: "`model_version` identifies equation structure and backend form only"; its test is
"two instances compiled from the same structure with different fresh-feed values share
`model_version`". K02 passes that test for the feed flows (measured: equal) and fails it for
`split_fraction`, `flash_temperature`, `heater_temperature`, which are pinned inputs exactly like
the feed flows and already reach `constants_sha256` (the test at `test_k02_flowsheet.py:614`
proves it, then asserts only on the digest half and lets the label half differ).

**Measured.** `model_version` at r = 0.5 ≠ `model_version` at r = 0.95 with identical structure.
Consequences: D4.1's "re-binding without recompilation" is defeated for the three parameters a
user changes most; and the 64-character cap (ADR 0002 D2.3) is blown by ordinary values —
`split_fraction=0.123, flash_temperature=360.25` raises `SpecificationError` from `label`
(65 characters). The registered variants fit at 60–61 characters, which is why nothing failed.

**Minimal correction.** Remove `-r…-Tf…-Th…` from the label. Change the assertion at
`test_k02_flowsheet.py:614` to `first.model_version == second.model_version`. The "a human should
not have to open the constants to know the variant" argument belongs to a run label or a case id,
not to the identity of the function. What stays in the label is decision 3 (below).

### M3. The mixer's admissibility bound is extensive; away from the registered throughput it admits a two-phase inlet and reports `ok`

`src/process_runtime/models/syn001/mixer.py:98` and `:508`.

The criterion `|H_true − H_liq| ≤ 1.01e-3 W` bounds the *energy-row* error at the registered
scale (3 mol/s). The number the mixer *reports* is `T_out`, and the error it accepts on that
number is `1.01e-3 W / (c_p Σn)`:

- at the nominal state, Σn = 4.639 mol/s, that is **2.18e-6 K — twice the registered 1e-6 K
  temperature tolerance**, so even at scale the bound is a factor two looser on T than D6 allows;
- at Σn = 6e-8 mol/s (two equimolar inlets of 1e-8 mol/s at 360 K and 300 K; the hot one is
  45 % vapour, β = 0.4536, latent 3.8e-4 W < bound) the mixer returns **`ok`, `LIQUID`,
  `T_out = 330.0 K`**; the adiabatic answer with that latent heat accounted for is ~394 K.
  A wrong number, status `ok`, at an input inside the declared T and P domain (the manifest
  declares no throughput floor).

This is the answer to the brief's question: at the registered throughput the check is not
relaxed — but it is an *extensive* bound on an *intensive* question, so it becomes relaxed
exactly where nobody measured. It is also not "on the quantity that can produce a wrong number",
as the docstring claims: that quantity is `T_out`.

**Minimal correction.** Anchor the bound on the number the unit reports, using only registered
constants: admit a stream as liquid when the temperature shift its ignored latent heat would
produce is below D6's temperature tolerance,

    |H_true − H_liq|  ≤  1e-6 K × dH_out/dT,      dH_out/dT = Σ_k Σ_i n_{k,i} ∂h_i^L/∂T,

where `dH_out/dT` is the slope `_close_energy` already asks the provider for. Nominal: bound
4.6e-4 W, recycle misses by 6e-13 W (passes by nine orders); the 347.45 K feed (29.4 W) is
refused; the 1e-8 mol/s case (bound 6e-12 W) is refused. Keep the 347.45 K anti-drift test; add
the small-throughput case as its counterpart. Apply the same criterion to the outlet check.

---

## 2. Should-fix

### S1. The heater and the mixer disagree about what "liquid" means at a bubble point

`heater.py:422` gates the inlet on the provider's *label*; `mixer.py:508` gates on enthalpy.
**Measured:** the registered nominal recycle (the stream the mixer admits, `TWO_PHASE` with
β = 1.3e-17) fed to a heater declared `inlet_phase="LIQUID"` returns `unsupported`. No registered
variant reaches this (S2 is subcooled in all five), but K03's controller will evaluate the heater
on iterates, and the r → 1 limit walks S2 onto its bubble point (derivation §7 finding 5). Use one
criterion (M3's) for every declared-regime check, in one function in `tp_state.py`.

### S2. The bracket claim is stated more generally than it holds

`mixer.py:7–13`. `Hdot_out(T) − Σ Hdot_in = Σ_k Σ_i n_{k,i}[h_i^L(T,P) − h_i^L(T_k,P)]` requires
`h_mix = Σ n_i h_i(T,P)` — **ideal mixing**, no excess enthalpy — not only `∂h_i^L/∂T > 0`. With
an exothermic heat of mixing the closure root lies above `max T_in` and the bracket fails. The
runtime guard reports that as `not_converged` (no wrong number), so this is a docstring and
manifest-limitation correction: "ideal-mixing provider whose liquid enthalpy increases with T".
SYN-001 satisfies it (derivation §2: no excess enthalpy). T05 will not necessarily.

### S3. State the lifted form's trivial roots and its boundary singularity in the manifests and the K03 handoff

`docs/K02_DECISIONS.md` names the spurious root as "V = L = 0". That is only a root for a dormant
stream. The roots K03 inherits are `V = 0` (all liquid) and `L = 0` (all vapour), and **both are
exact roots of every lifted row at every flowing feed**, whatever the feed's actual phase state.
**Measured** at the once-through variant (true outlet β_h = 0.1014): all 14 heater rows are
`0.0` at the all-liquid root, with a duty of 15 000 W against the registered 23 237.85 W. The
same holds for the flash's `S4`/`S5` rows.

The Jacobian of the 8×8 lifted block at `V = 0` is block-triangular with
`det = L³ (1 − Σ_i x_i K_i)`; at `L = 0`, `det = V³ (1 − Σ_i y_i / K_i)`. So the trivial root
is regular exactly when the single-phase state is stable, and **singular on the bubble/dew
surface**, where it coalesces with the two-phase root. That is the fact K03's phase-attempt
controller needs: the stability test (Σ z K > 1 / Σ z/K > 1) is not a heuristic but the sign of
that determinant. Put one limitation sentence in `heater.yaml`/`flash.yaml`'s Python manifests
and correct the decisions-log wording.

### S4. Six row builders exist in two to four copies

`_equilibrium_row` (`tp_state.py:360`, `flash.py:578`), `_total_row` (`tp_state.py:398`,
`flash.py:610`), `_specification_row` (`heater.py:490`, `flash.py:598`, `feed.py:299` as
`_difference`), `_balance_row`/`_inflow_minus_outflow` (`flash.py:559`, `mixer.py:588`,
`heater.py:467`), `_duty_row` (`heater.py:516`, `flash.py:625`), `_difference_row`/`_copy_row`
(`mixer.py:626`, `splitter.py:344`). M1 hid behind exactly this: the flash's copy was tested at
a two-phase state, the heater's copy was not, and they are different functions. One
`models/syn001/rows.py`, each builder tested once.

### S5. `traverse` trusts the guess's T and P

`flowsheet.py:221`. The docstring says the tear is three variables because the recycle's T and P
are the flash specification, but `traverse` uses whatever T and P the caller's `StreamState`
carries. A K03 Newton that passes a guess at the wrong T is evaluating a different map. Refuse
(typed `error`) a recycle whose `temperature != flash_temperature` or `pressure != pressure`.

### S6. One test bounds every row with the loosest tolerance

`test_k02_flowsheet.py:426` bounds mol/s, K, Pa and (mol/s)² rows by 1.01e-3 W. A 1e-4 mol/s
error in a component-balance row passes. Use the registered per-dimension tolerances
(3.1e-8 mol/s, 1e-6 K, 1e-2 Pa; the equilibrium rows by 3.1e-8 × throughput as the heater/flash
test already does).

### S7. The energy tolerance is misprinted as 1.001e-3 W in three places

It is `1e-5 + 1e-8 × 1e5 = 1.01e-3 W`. Code and test *expressions* are right; the strings are
wrong in `evidence/K02/…/manifest.json:57,99,140` (`expected` fields), the brief §2, and the
docstring at `tests/test_k02_mixer.py:407`. Regenerate the manifest strings from the constant.

---

## 3. Observations

- **The `R(s t*) = (1 − r)(1 − s) t*` derivation is correct.** Checked: the flash of
  `F + s r L* x` at (T_f, P) is satisfied by `(V*, y, L*[(1 − r) + s r], x)`, which is the RR
  root by uniqueness (§5.1) provided the feed is two-phase — true for the three 360 K variants
  since `V* > 0` and `L(s) > 0` for `s ≥ 0, r < 1`. At 310 K it reduces to `r(1 − s)` per
  component and at 420 K to `0 = 0`, so it is a **four**-variant check (the manifest's "every
  variant" overstates by one, harmlessly). The mixer admits the ray because `s t*` is saturated
  liquid at the flash state for every `s`. Two things follow that K03 should know: the SYN-001
  tear map is *affine on that ray*, so a Newton tear solve from any in-domain point on it
  converges in one step; and off-ray in-domain starts exist only at compositions heavier than
  `x` (`Σ z K(T_f) ≤ 1`).
- **Orientation:** every balance row is the negation of P02's; `Vdef`, `Ldef`, `eq_i`, `tspec`,
  `pspec` unchanged; D4.3's `+0.5` and `−0.5` are exact through `compile/reference.py`. Correct.
- **The pressure count is right and the redundancy is two:** rank 7 on 9 rows when
  `P_feed = P_spec`. One redundancy is `FLASH-P`'s inlet clause against the upstream zero-drop
  chain; the other is loop closure (`S6.P` equals both the mixer outlet and the splitter inlet).
  The second is inherent to any zero-drop recycle loop with pressure-copy rows. The first is a
  property of the *declared* `FLASH-P` statement and generalises badly: with nonzero drops it
  becomes an inconsistency, not a redundancy. That is a P01 manifest question for a later ADR.
- **`tested` for the six manifests is right**; `implemented` for D08 and D10 is right, and the
  ledger's reasoning (the other half of the minimum evidence is M01's/M02's) is the honest one.
- **`compile/reference.py` is what it says:** values only, no backend, and its docstring is
  honest that it is a plumbing witness. The `residuals / free_variables / ad` derivative entry
  is the right way to say "rows exist and CasADi differentiates them".
- **What the tests do not verify** beyond M1: the mixer's rows at any variant but nominal (the
  flowsheet assembled-rows test is nominal-only — M1's parametrisation fixes this too); the
  mixer closure at a pressure other than P_r (the `v_i (P − P_r)` term cancels per mole in
  SYN-001 because all `v_i` are equal, so nothing would show; a provider with distinct `v_i`
  would exercise the pressure argument of the bracket); the heater's `pressure_drop ≠ 0` path.
- Double TP flashes of S3 (heater outlet, flash inlet) are absorbed by the exact cache
  (warm pass reached the provider 0 times). Not a performance concern at this scale.

---

## 4. Verdicts

| Item | Verdict | Reasoning |
| --- | --- | --- |
| **Decision 1** — mixer admissibility on enthalpy vs the registered energy tolerance | **change** (M3) | Not a relaxed check at the registered throughput; an extensive bound on an intensive question, defeatable at small throughput and already 2× looser than the T tolerance on the number reported. Anchor on `1e-6 K × dH_out/dT`; every constant stays registered. |
| **Decision 2** — lift the heater's two-phase outlet | **accept**, with S3 and M1 | Right trade: the residual stays a closed-form function of `x` (blueprint §5.1) and the flash already uses the same form, so the heater adds no new kind of difficulty for K03 — only the same trivial roots and the same boundary singularity, which must be documented (S3) and whose rows must actually be tested (M1). |
| **Decision 3** — provider identity through the label | **change + needs an ADR** | Remove `r/Tf/Th` (M2; no ADR, it is a D4.1 violation as written). The provider's `id` and two hashes may stay in the label as an interim carrier — a provider *is* part of the function's form — but D4.1 as written assigns "physical constants" to `constants_sha256`, so amend D4.1 (one paragraph) to say provider identity reaches `model_version`; and prefer, when K01 is next opened, folding a `PropertyBlock` identity into the structure digest so the label stops carrying hex. |
| **Decision 4** — causal sensitivities stay `unavailable` | **accept** | No interface returns one; declaring `analytic` would name a capability no caller can reach (blueprint §5.2). Not too conservative. |
| **Finding 1** — registered tear initializer outside the mixer's domain | **amend the derivation (my call)** | An initializer at which `R` is *undefined* is a non-start, not a hard start; §7.4 homotopy cannot damp from nowhere. Amend derivation §9: keep `r F_i` for the analytic linear recycle (§8, no mixer) and register for the SYN-001 flowsheet `t⁰ = G(0)` — one traversal from a dormant recycle, i.e. `r × liquid of the TP flash of F at (T_f, P)`, which is `(1 − r) t*`, in-domain for every `r`. Record the caveat that SYN-001's tear is affine along that ray (one Newton step), so K03's tear evidence must include an off-ray start and the STA/NUM cases. I will apply the amendment in a separate Fable commit; this review does not edit the derivation. |
| **Finding 2** — pressure network over-determined by two | **accept** (K02); K03 needs a registered rule | A unit cannot see the flowsheet; eliding is not its call. K03's structural analysis must have a *registered* policy for consistent-redundant rows (rank-revealing detection, drop with a certificate naming the dropped row, refuse inconsistency). Note the `FLASH-P` inlet clause as a P01 manifest issue for a later ADR. |
| **Finding 3** — saturated-recycle classification reaching K03 | **accept, nothing in code now**; S3 for the handoff | In the EO system `S6` has no lifted split — its phase is fixed by declaration (`LIQUID` block) — so the label ambiguity exists only on the evaluator path and in whatever the controller does with provider flashes. The controller's real hazard is a *lifted* stream on its bubble/dew surface, where the lifted Jacobian is singular (S3). Say that in the handoff; the mixer's remedy was never meant to transfer. |

---

## 5. What this review does not establish

- Human numerical or process-modeling sign-off. `review.numerical` and `review.process_model`
  remain `pending` and are not an agent's to set.
- Anything about the caches or the provider's own tests beyond reading `thermo/syn001.py`: the
  brief put them earlier in the package and I did not re-run their sweeps.
- The CasADi adapter's internals, the canonicalization (ADR 0002) or the schema machinery.
- Opus's 65 mutation results: I ran one mutant of my own (M1), not the sweeps.
- Field-by-field agreement of the six Python manifests with P01's YAML: relied on
  `tests/test_k02_unit_models.py`, which I read but did not independently re-derive.
- `ruff`, `ruff format`, `mypy`: I ran `pytest` only.
- The 20-digit reference values themselves (mine, from P01) — used as given.
