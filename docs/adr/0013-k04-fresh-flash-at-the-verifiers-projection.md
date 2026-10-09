# ADR 0013 — K04: fresh-flash checks judged at the verifier's own Newton projection, an admissible phase reading, and unresolved splits (T04 F9, F10; T05b D9 (1))

**Status:** Accepted 2026-09-25 — T05b's manifest `evidence/T05b/ba9a27b422834138daeff98481072c65db8b3744/manifest.json` is `tested` (64 of 64: B00–B36 and X00–X26; the cross-platform items on CI run 36169942463, x86-64 and aarch64), after the design-lane review `docs/reviews/T05b-review.md` (full review, re-review of W9, reviews of W10 and W10 (6) (b); every must-fix closed) and the ruling rounds `docs/briefs/T05b-rulings.md`. Agent acceptance is numerical and procedural: `review.numerical` and `review.process_model` remain `pending`.  
**Amended 2026-09-25 (ruling round, `docs/briefs/T05b-rulings.md` §4, Q-S1, Q-S2, Q-S5):** D2's order is the provider's decision first, D2 replacing only a two-phase answer (spec §5.2; R-060 amended); D1's guard 4 reads stream flows (K04 §4.6's predicate), not every `molar_flow`-kind column, and guard 5 counts a row that cannot be evaluated at `x̃` as not passed (spec §5.1); D6's "T05b §13's W0.9 rule" becomes spec X26 as amended — `b` recorded and never thresholded, every registered comparison's realized deviation `≤ 1/10` of its allowance, NP-GC in scope (R-063); X21's floor-ratio tolerance is `max(1e-6, 4 ulp(T)/w)` against the closed form of the reference's 20-digit fields (spec §7). No decision of D1–D5 changes; the reference file does not move.  
**Amended 2026-09-27 (Amendment 2, below; T07 design note ruling round 5, review M1):** D1's guards 1 and 5 and D3's `τ_flow` read the *routing tolerance* ρ_k = max(τ_k(policy), τ_k(registered)), not the policy's τ. No registered result, identity or policy hash moves; only certificates under a policy that tightens change.  
**Amended 2026-10-09 (Amendment 3, below; M02 WO-8 rulings, design note §14.2 B15; R-257):** the verifier's `pr-c1-v1` forms of D2 (the admissible reading at τ_dew), D3 (no unresolved routing: the band is half-open) and the K04 §4.7 checks; fresh provider by the revision's basis. No tolerance, kind, category or required check is added; `check_policy_sha256` and every SYN-001 certificate are unchanged.  
**Date:** 2026-09-25  
**Author:** design lane (`specifier`); brief `docs/briefs/T05b-F9.md` (`0ca04cc`)  
**Directive:** Frank, 2026-09-25: *"Fold F9 into T05b"*, under his standing steers *"as little limitations as possible"* and *"robustness … if a method cannot solve a hard case and the solver then switches to another method this is also fine"*. SYN-001's identity must not move (his condition on D12 of ADR 0012, same day).  
**Normative text:** `docs/derivations/K04-F9-spec.md` §5; machine-readable expectations `benchmarks/k04f9/reference_values.yaml` from `docs/derivations/scripts/k04f9_reference.py`  
**Amends:** K04 §4.4 and §4.7 (where and with which phase rule a fresh flash is evaluated; the flash-outlet clause for SYN-001's legacy set), §8.2's statements (none added), §3.2 (independence, unchanged in kind); ADR 0012 D7 (a second substitution class beside temperature-degenerate) and D9 (1) (closed); T04 §4.8 item 7, §14, §15 Q8 (answered), §17 F9 and F10 (closed), A32 (its 5e-4 W half) and A33; T05b §9, §12.6 (INJ-B2, INJ-B2p), §13 (W0.9's rule), §17, B13, B16, B18, B26.  
**Reverses:** R-057 (1) (near-pure EO certification in F9's band a registered limitation). **Amends:** R-016 (4), R-054 (a second substitution class; its "watch for: a session widening the window" is answered by this explicit decision, not by a wider window).  
**Affected requirements:** D14 and A08/A09 (what a certificate certifies at a state converged to its row tolerance; blueprint §8.1's independent balance evaluators), D20 and ADR 0007 D2.4 (no identity or policy hash moves; one R0 record added to an open object), V12 (the unit library's EO cases certified without a registered limitation).  
**Affected packages:** K04 (the verifier: `verify/certificate.py`, `verify/checks.py`, `verify/table.py`, a new `verify/projection.py`; its schema fixtures regenerate for the new `transformations` key); T04 (A32, A33 re-registered; its fixtures regenerate); T05b (B13, B16, B18, B26 re-registered; W0.9's rule); K05 (identity unchanged); T06 (EO ensembles are certified without F9's false alarms).

## Context

K04's fresh-flash checks — the independent split (K04 §4.7), every energy balance that reads a stream's enthalpy from a fresh flash of its own `(n, T, P)` (§4.4), and the declared-port checks built on the same enthalpy — were argued from floors at *deeply converged* states. An equation-oriented Newton stops at its *row tolerance*, and at a lifted stream the fresh flash then disagrees with the state by more than the check's tolerance although every row is inside its own. Measured this pass on the implementation (spec §4):

1. **The A02 family** (T04 §9.3; 179 converged states): 15 `FAILED` and 9 near threshold on S3's independent split and the heater and flash balances, the worst at 27.28× its threshold — T04 F9's counts, reproduced to the digit by the twin.
2. **DZ-3 and DZ-10** (T05b B16, B26): `FAILED` on `independent_split.U-PHF.S1.total` (2.93 τ) and on `energy_balance.U-PHF` and the envelope (1.31 τ_E). The energy failure is a second mechanism: the PH flash's *liquid product*, saturated at the root, is 2.125e-8 past its bubble point at Newton's stop, and its fresh flash forms a vapour worth 6.247e4 W per unit of that excess.
3. **NP-G** (T05b B13): `VERIFIED` today by luck. After any correction toward its root its fresh flash is roundoff-dominated: the feed's band is 4.12 µK wide, so one ulp of `T` (5.68e-14 K) moves the fresh flash's vapour flow by 0.89 τ_flow, and one ulp of saturation excess in its liquid product moves that product's fresh-flash enthalpy by 0.21 τ_E.

The first two are *convergence-level* (the state sits at its row tolerance); the third is *resolution-level* (the fresh flash cannot resolve the state at double precision even at the root).

## Decision

### D1. The verifier's Newton projection — where the fresh-flash categories are judged

When `x_final` passes every residual row under the certificate's policy and the regularity screen reports `NO_RANK_LOSS_DETECTED`, the verifier computes **one Newton step of the matrix it has just screened**: `x̃ = x_final + S_x (−Ĵ⁻¹ F̂)`, with `Ĵ` and `F̂` the scaled target Jacobian and residual of K04 §7.1 at `x_final` (T04 §4.8's bound declaration, T05b §9.3's zero-flow forms included) and the screen's own factorization. Every molar-flow column that is exactly `+0.0` at `x_final` is `+0.0` in `x̃`; columns a zero-flow form removed keep `x_final`'s values. `x̃` is accepted iff every flow is `≥ 0`, every flowing stream's `(T, P)` is in the provider's domain, and every compiled row (and zero-flow label) at `x̃` passes its tolerance. **The categories `energy_balance`, `phase_admissibility` and `independent_split` — and the routing that selects among their forms (ADR 0012 D7, D3 below) — are evaluated at `x̃`.** Residual rows, alias certificates, material balances, specifications, bounds and domain, the derivative witness, the regularity screen, the solution-error bound, `target_state_sha256`, `phase_branch` and `branch_found` stay at `x_final`, the certified state. When a precondition fails, every category is evaluated at `x_final`, as today. The certificate records which, in `transformations.projection` (D5).

The step removes the first-order error the row tolerance allows and leaves the second-order one: on the twin's A02 family the S3 values fall from ≤ 27.28 to ≤ 2.107e-5 of their thresholds; the implementation measures 2.092e-5. `‖x̃ − x_final‖` is the first-order solution error K04 §7.4 already discloses as `b`.

### D2. The fresh flash's phase decision uses K03 §8.2's admissibility tolerance

The verifier's enthalpy of a flowing stream from a fresh flash of `(n, T, P)` (`checks.enthalpy_flow`, one function shared by both check engines) reads the stream as **liquid when its bubble excess `Σ z_i K_i − 1 ≤ ε_adm`, else as vapour when its dew excess `Σ z_i/K_i − 1 ≤ ε_adm`, else from the provider's two-phase flash**, with `ε_adm = 1e-12`, the single-phase admissibility tolerance K03 §8.2 already registers and K04 §4.7 already applies. Where the provider's own decision (`≤ 1`) agrees, the value is bitwise unchanged. The rule removes the saturated-product kink of item 2 at any state within `ε_adm` of saturation — every product and every copy of one at `x̃` — and nothing more: a stream `1e-7` past its bubble point is still flashed, and the split the flash finds is the energy check's to judge (INJ-F10's liquid, 0.384 past its bubble point, fails by 3.8e7 τ_E). *(Ruled 2026-09-25: the provider decides first, and the two `ε_adm` tests replace only its two-phase answer, in `admissibility_checks`' arithmetic — the literal order would read a stream the provider calls vapour, with a bubble excess in `(0, ε_adm]`, as liquid; spec §5.2.)*

### D3. Unresolved two-phase splits are judged like temperature-degenerate ones

A flowing lifted split that is not temperature-degenerate (ADR 0012 D7 keeps precedence) is **unresolved** when its stored branch is two-phase, its temperature lies inside its feed's saturation band `[T_b, T_d]` (the verifier's own bisection, `verify/saturation.py`), and the fresh flash's resolution floor reaches the routing threshold:

    N · ulp(T) / (w · τ_flow) ≥ 1/10,      w = T_d − T_b,  N = Σ n_feed,

the vapour flow's mean sensitivity to temperature across the band (`N/w`) times the spacing of doubles at `T`, against `τ_flow` with ADR 0007 D2.4's margin of 10. No new constant is registered: `τ_flow` is the policy's, 10 is D2.4's, `ulp` is IEEE 754's. An unresolved split is judged by D7's substitution: its streams' enthalpies from the stored split (products in their phases), qualification `enthalpy of <S> from the state's split: fresh flash unresolved (ADR 0013 D3)`; `independent_split.<U>.<S>` `not_applicable` with reason `fresh_flash_unresolved`; its admissibility the branch's own check (the two-phase closure), unchanged. NP-G is unresolved (ratio 0.8896, 8.9× over the threshold); NP-3 is resolved (0.01712, 5.8× under); every other registered split is resolved by ≥ 3.7e4× or degenerate.

### D4. K04 §4.7's flash-outlet clause (T04 F10)

For **revision-built flowsheets** the clause is implemented (`verify/table.py` runs admissibility and the independent split on every lifted split, the TP flash's included). For **SYN-001's legacy set** (`verify/checks.py`, used by `verify` and `verify_bound`) it is **discharged by §4.4**, not added: a wrong flash branch fails the flash and envelope balances through the fresh flash of S5 (and S7) — registered as INJ-F10, the once-through flash forced all-liquid, `FAILED` by −38 338.069 446 744 W on both — and adding five check ids to the nominal SYN-001 certificate would move SYN-001's R0 identity, which Frank's condition forbids. Spec §12 Q1 leaves the implementation open to Frank at a later identity re-registration.

### D5. Records, identity and policy

- **`transformations.projection`** (an R0 object in an open schema object, ADR 0010 D9's precedent): `{judged_at: "projection" | "final_state", reason: "" | "residual_not_passed" | "regularity_<STATUS>" | "linear_solve_failed" | "projection_outside_domain" | "projection_rows_not_passed", categories: ["energy_balance", "phase_admissibility", "independent_split"]}`. No float is recorded; `b` (already recorded) bounds the step. The nominal certificate gains the key; `SolutionCertificate`, `CheckResult` and every schema are unchanged.
- **No tolerance, kind, category or required-check entry changes**: `check_policy_sha256` stays `21c44e10…`; `CheckResult.tolerance` stays a registered constant (ADR 0007's `exact_fields`); `numerical_policy_id` stays.
- **Identity**: the K05 identity document (`622463f5…`; minus `t05` `b364bb3d…`; `t05` `ddbd0f71…`), the structural hash `4ce030ca…`, T02's floats `9a8a5baf…` and `thermo/syn001.py` do not move — measured with the rule prototyped around the verifier (spec §7).
- **`run_checks` stays unprojected**: it is the primitive a partial checkpoint's `CheckReport` uses (K04 §8.3), and a partial state is not a converged one.

### D6. Registered expectations that move, each with its reason (spec §10)

T04 A32's 5e-4 W half (its two energy balances no longer near threshold at `x̃`), T04 A33 (A02-355 from 358 K is `VERIFIED`, promised; F9's raw values stay registered through `run_checks` at `x_final`), T05b B13 (NP-G's independent split `not_applicable`), B16 and B26 (DZ-3, DZ-10 `VERIFIED`; the strict xfails retire), B18 (INJ-B2's state — every compiled row inside its tolerance, 2 τ_T from SC-1's root — is re-registered as **PRJ-B2, `VERIFIED`**: it was F9's false alarm registered as a false success; the window's outer side keeps an end-to-end test in the new **INJ-B2′** at 2e-5 K, `FAILED`), INJ-B2p's value, T05b §13's W0.9 rule. New: INJ-B2′, INJ-F10, NP-GC, PRJ-B2.

## Alternatives considered

- **First-order propagated tolerances (T04 Q8's default).** Rejected. (i) `CheckResult.tolerance` would become a computed, state-dependent float, which ADR 0007 lists among `exact_fields`; reclassifying it is a new numerical policy id, a frozen literal (`numerical_policy_id`) on every certificate. (ii) It widens tolerances where the fresh flash is still informative: measured over the A02 family, the independent split's tolerance grows by 11–208 τ_flow and the energy balances' by 8.8–174 τ_E, so a 2e-3 W duty error at A02-365 (T04 A32) would pass the flash balance. (iii) It leaves 4–7 family states inside D2.4's band (their verdicts not promised). (iv) Its block view needs a second machinery for the saturated-product kink and for copies of products through a splitter, which depend on rows outside the lifted block. (v) T04's formula assumes the linear rows exact, which a verifier may not assume of a solver.
- **A solver-side polish to roundoff after `CONVERGED`.** Rejected. It adds iterations and events to every converged EO solve, moving the R0 records of T02–T05 and SYN-001's identity document; it leaves the verifier inconsistent with the declared tolerances for any state not produced by the polished solver (a replayed or supplied state, a PTC stop); and it cannot reach NP-G's resolution floor, which remains at the exact root. Frank's robustness steer allows a recorded method switch; it does not require one where the defect is the verifier's.
- **Both (a) and (b).** Rejected for (a)'s reasons.
- **Evaluating every non-residual category at `x̃`.** Rejected: a specification check at `x̃` is identically its own row there, so a specification off by 0.9 τ would read 0; material balances are sums of linear rows that Newton leaves exact, so moving them changes nothing registered (T04 F3's envelope at a linearly convergent stop stays with T04's polish).
- **A first-order correction of the check values (`value − ∇value · Ĵ⁻¹F̂`).** Rejected: the fresh flash of a saturated product is not differentiable there (the kink), and the correction would need the flash's derivatives; D1 evaluates the checks, it does not extrapolate them.
- **Projecting without keeping exact zeros.** Rejected, measured: at SYN-001's nominal root the step moves S3's zero vapour flows by ~1e-30 and turns `phase_admissibility.S3.bubble` into `.closure`, moving SYN-001's identity; the exact step is zero on those columns (spec §5.1).
- **Widening ADR 0012 D7's degeneracy window (`δ ≤ W`).** Rejected: `.saturation`'s tolerance would become a computed float (ADR 0007's `exact_fields`), and a band-containment window says nothing about a two-phase split whose band is narrow but whose temperature is far from its ends. D3's criterion is a resolution floor, and D7's window is untouched.
- **Letting NP-G's independent split pass at its floor (D1 + D2 without D3).** Rejected: measured 0.44 τ_flow at the projection against a floor of 0.89 τ_flow — a check that sits at its own floor measures roundoff, and its verdict would be a platform lottery.
- **Implementing F10's clause in the legacy set.** Deferred to Frank (spec §12 Q1): it moves SYN-001's identity document.

## Consequences

- C1. `verify/projection.py` (new): the projection, its guards and its refusal codes; `verify/certificate.py`: `_certify` and `verify_revision` compute the screen before the fresh-flash categories and pass `x̃` to them; `verify/checks.py`: D2 in `enthalpy_flow`; `verify/table.py`: D3 in `degeneracy` and `_split_checks`; `verify/saturation.py`: the band width alongside `δ`.
- C2. The schema fixtures that carry a certificate (K04's, T04's) are regenerated by their generators for `transformations.projection`; nothing else in them moves beyond ADR 0007's floors.
- C3. Tests: T04 A32 (5e-4 half) and A33, T05b B13, B16, B18, B26, and the T05 W1.d pairing harness are amended as spec §10 states; the strict xfails of B16 and B26 retire.
- C4. Register: R-059 (D1), R-060 (D2), R-061 (D3), R-062 (D4); R-016, R-054 and R-057 carry amendment lines.
- C5. Handed on: whether a certificate should record the projection's step as a float (a new ADR 0007 path; spec §12 Q5); F10 in the legacy set (Q1).

## Migration

No schema changes. Every stored certificate keeps its meaning; a certificate issued after this ADR carries `transformations.projection`, a key older certificates lack (K05 replay of an archived pre-ADR bundle reports it as an R0 difference of the certificate artifact, as ADR 0010 D9's `declaration` key did; no registered bundle is archived outside the regenerated fixtures). No registered identity moves (D5). The registered expectations of D6 change with the reasons in spec §10; no other registered value moves.

## Acceptance evidence

- `evidence/T05b/<commit>/manifest.json` `tested` with X00–X26 of `docs/derivations/K04-F9-spec.md`.
- `k04f9_reference.py --check` passes (25 claims) and the committed YAML's SHA-256 equals the specification's header; `--emit` twice is byte-identical.
- The gate green on x86-64 and aarch64 with the K05 identity comparison unchanged in every key.

---

## Amendment 2 (2026-09-27) — a tightened tolerance is compared, never routed on

**Author:** design lane (`specifier`), T07 design note `docs/design/T07-jobs-and-bindings.md`,
ruling round 5, finding M1 of `docs/reviews/T07-review.md`.

### Context

D1 and D3 read "the certificate's policy" in two places that *route*: they decide which checks
exist and at which state they are judged, not whether a check passes.
- **D3's `τ_flow`.** It decides whether a split is unresolved. An unresolved split's
  `independent_split.<U>.<S>` is `not_applicable`, and its energy balances read the stored split.
- **D1's guards 1 and 5.** They decide whether the fresh-flash categories are judged at `x̃` or at
  `x_final`.

Before T07 the only policies were the registered one and loosened ones, and neither exposed the
problem. T07's `submit_job` lets a caller *tighten* (design note §5.3, step 5). A tighter `τ_flow`
raises D3's ratio `N · ulp(T)/(w · τ_flow)`, and a split then crosses 1/10 and is routed out.
Measured at `b36a018` (44 certifying corpus revisions):
- `τ_flow` × 1e-6 deletes checks in 24 of 44 revisions, and every one of them reads `RELAXED`
  with no failing check (SYN-001-nominal 147 → 144; SYN-001-T06-NET03 246 → 234);
- tightening every kind by 1e-6 also moves the projection in 15.

A caller could thus remove the independent flash, the check that catches a wrong-branch split
(K04 §4.7), by asking for a *stricter* certificate.

### Decision

1. **Where D1 or D3 reads a tolerance to route, it reads ρ_k = max(τ_k(policy), τ_k(registered))**
   of the kind in question:
   - D3's criterion becomes `N · ulp(T) / (w · ρ_flow) ≥ 1/10`;
   - guard 1 becomes "every `residual` row and zero-flow label row at `x_final` satisfies
     `|value| ≤ ρ_k` of its kind";
   - guard 5 becomes the same at `x̃`.

   A compiled row's kind is its declared `row_kinds` entry, and a label row's kind is
   `temperature`.
2. **The policy's own τ enters a certificate only as the right-hand side of each check's
   `|value| ≤ τ`.** ADR 0012 D7's degeneracy test already reads the registered `τ_T` and is
   unchanged.
3. **Consequence.** Under a policy that only tightens, the certificate equals the registered
   policy's in every check id, its order, every value (bitwise), `transformations.projection`,
   `target_state_sha256` and the regularity evidence. It differs only in each check's `tolerance`,
   `result` and `near_threshold`, and in what `grade` derives from them.

   So every check passing under the tightened policy implies every check passing under the
   registered one. A check below the fresh flash's resolution is evaluated and may fail on roundoff:
   measured, SYN-001-once-through's restored `.total` reads 3.4250e-14 against τ' = 3.1e-14. The
   check fails; it does not vanish.
4. **Loosened policies** get ρ = their own value, so they are routed exactly as before.

### Alternatives rejected

- **The registered τ for every routing read.** For tightening it is equivalent, but it moves
  loosened-policy certificates. K04 INJ-4's loosened policy passes guard 1 today, and it would not.
- **A floor on tightening.** The resolution floor is a property of the solved state, which is
  unknown when the policy is supplied. A fixed floor still lets a split whose ratio sits just under
  1/10 be routed out.
- **An unresolvable tightened check reported `unsupported`.** This withdraws evidence the verifier
  can compute, and turns a correct `FAILED` into `UNVERIFIED`.

### Affected requirements

- D14 and A08/A09: a certificate's evidence cannot be reduced by its caller.
- T07 I3 (design note §10.5) and gate G12.
- Nothing in D5's policy statement changes: no tolerance, kind, category or required check.

### Migration

- **At the registered policy nothing moves.** `max(τ, τ)` is `τ`. Measured: the SHA-256 of each of
  the 44 corpus certificates is equal with and without the rule. So the K05 identity document, its
  `t07` key and `check_policy_sha256` `21c44e10…` are unchanged.
- **Loosened policies** are unchanged by construction.
- **A bundle recorded under a policy that tightens,** before the rule, re-runs to a certificate with
  more checks. Replay reports that difference, and it is correct. No such bundle is registered.
- **Code:**
  - `verify/checks.py`: `routing_tolerances`;
  - `verify/table.py`: `degeneracy`;
  - `verify/certificate.py`: `_project`;
  - `verify/projection.py`: guards 1 and 5.

### Acceptance evidence

- T07 gate G12 as amended (design note, ruling round 5, G12.1–G12.10) passes. On five revisions,
  the tightened certificate has the registered check ids, values and projection, at factors down to
  1e-12. Against `b36a018`, G12.3 fails on each of the five.
- The unit test of `routing_tolerances` passes.
- G1: the K05 identity comparison is unchanged in every key.
- The K04, T04 and T05b suites pass unchanged, including INJ-4 and B13 (NP-G unresolved at the
  registered τ).

---

## Amendment 3 (2026-10-09) — the verifier's `pr-c1-v1` forms

**Author:** design lane (`architect`), M02 WO-8 rulings. **Normative text:** `docs/design/M02-pymrm-adapter.md`
§14.2 B15. **Register:** R-257.

### Context

On the revision path the verifier was SYN-001-shaped in five ways:
- `verify_revision` built `Syn001Provider()` whatever the revision's basis;
- `stream_of` read three components;
- `enthalpy_flow` and the declared-port check read per-component `h_<c>`;
- the split checks and D2 read `lnK`;
- D3's band is `lnK`-based.

`pr-c1-v1` has a mixture `h`, ln φ, a pure-NH₃ liquid and a half-open band.

### Decision

1. **Fresh provider.** The verifier builds its fresh provider from the revision's basis (`view.basis.provider_id`)
   through a table of its own; it never calls the binder's constructor. Streams are read with the view's components.
2. **D2 for `pr-c1-v1`.** A TWO_PHASE fresh flash with liquid NH₃ ≤ τ_dew · n_tot (τ_dew = 1e-10, R-230; ADR 0001
   D6's normalized-composition tolerance) is read as VAPOR at the stream's own state. Otherwise the stream's enthalpy
   is the sum over the flash's phases of `sum(n) · h`.
3. **D3 and ADR 0012 D7 for `pr-c1-v1`.** No routing. A stream that carries light gas has a half-open band (M01 §7
   rule 4), so it is never degenerate, and with `w = ∞` the floor is 0.
4. **K04 §4.7 for a `pr-c1-v1` split.**
   - **VAPOR branch:** `.dew` is one-sided, with value `l_NH₃ / n_tot` from a fresh flash of the feed, against τ_dew.
   - **TWO_PHASE:** `.closure` is `|g / g_T|` in kelvin against τ_T, where `g = ln y_NH₃ + ln φ^V_NH₃ − ln φ^L_NH₃`
     is taken on the state's own phases. It is the first-order distance of the vapour from its dew temperature; a
     pure liquid has no bubble point.
   - **LIQUID branch:** `unsupported` (`pr_liquid_regime_unsupported`).
   - **Independent split:** K04's formula.
5. **Declared ports.** A declared vapour port is judged by the same one-sided τ_dew test on a fresh flash of the
   stream; a declared liquid port is `unsupported`.
6. **Liquid-side check.** The flash gains `material_balance.<U>.liquid.<i>` = `n_L,i` against τ_flow for each
   vapour-only component.

### Alternatives rejected

- A closure `|y − y*| ≤ 1e-10`: a tolerance outside the check policy, and 500 to 16 000 times tighter than the
  equilibrium row's own tolerance allows.
- Generalizing SYN-001's functions in place: that touches arithmetic whose bitwise pairing W1.d protects.
- The K-distance declared-port form for `pr-c1-v1`: it cannot see condensation below `l/n ≈ 1.5e-9`.

### Consequences

- No tolerance, kind, category or required check changes, so `check_policy_sha256` stays `21c44e10…`.
- SYN-001's certificates are unchanged: the 50 T07 corpus certificates are byte-identical (M02 G2).
- The new module `verify/pr_c1.py` joins the independence test's scanned files (R-016).

### Acceptance evidence

M02 G2 and G7 (j), (k), as amended by the design note's §14.2.
