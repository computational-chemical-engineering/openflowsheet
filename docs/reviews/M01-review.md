# M01 review: the C1 property route `pr-c1-v1`, its flash, the five records, the reaction-consistent registry, and the reactor boundary with its synthetic stand-in. Reviewed against `docs/derivations/M01-spec.md` (ADR 0026, ADR 0027)

**Reviewer:** design lane, `reviewer` (Claude Opus 5.5), 2026-10-08. Plan §1.3 requires a design-lane review here
because M01 touches derivatives, phase logic and reference states.
**Reviewed at:** `wp/M01` = `c2cf045` (diff `main...wp/M01`). The production code has not changed since the
manifest's commit `6c81683`. The later commits `7e0eb67`, `cec8a01` and `c2cf045` touch only T08 tests, the
envelope, the manifest and the register.
**Design reviewed against:**
- spec §3–§9, §17 and §19 (Amendment 1);
- ADR 0026 and ADR 0027 with their Amendment 1;
- R-154…R-169, R-195…R-200 and R-217;
- T08 release spec §5.7, the harvest rules.

**Run here:** I did not run the gate. I ran eight probes against this tree, using the repository's `.venv` with
`src/` from the worktree on `sys.path`. Each probe's scripts lived only in the session scratchpad. §5 describes
each one so it can be re-run. A finding marked *measured* comes from one of these probes.
**Not examined:**
- the internals of `m01_reference.py`; I relied on A34 and on A37's independent IDAES agreement;
- `reactor_probe.py`, the probe environment and §10's refinement analysis;
- the DIPPR fit of the overlay rows;
- the internals of `idaes_conformance.py` and `external_crosscheck.py`;
- M02's design (out of scope by the brief).

---

## 1. Verdict

**Matches, with one must-fix.**

The provider transcribes §4 correctly. I checked by hand:
- the implicit root derivatives;
- F_A, F_B and F_Z;
- every chain-rule term of ln φ and h.

The derivatives are checked independently at 10⁻⁹ against 50-digit numbers, and the values at 10⁻¹² against the
generator and against IDAES 2.13. The root and phase rules are implemented as §5.2 states them. The y*-flash is
sound: the trivial solution exists only at the excluded endpoint y = 1.

The boundary implements §8.12 as amended, with one hole in the check order (finding 3). The stand-in is labelled
everywhere A49 requires.

**The must-fix is one misclassified harvest row** (finding 1). It is cheap. It is also exactly the misfile that T08
§5.7 gives the reviewer to catch.

Three should-fixes concern behaviour that no registered state or loop state reaches:
- the cubic solver returns non-roots in a window about 10⁻¹⁴ wide around a double root (finding 2);
- the boundary accepts invalid dormant inlets (finding 3);
- the claim that Q-N4's choice can be undone by one revert is false (finding 4).

None of them changes a decision of ADR 0026 or ADR 0027.

## 2. Findings (most severe first)

### F1 — must-fix — The harvest row for the manifest's `limitations[3]` is class P; it is user-facing (class E)

**Evidence.**
- `benchmarks/t08/support_envelope.yaml:2454` classes the M01 manifest's `limitations[3]` as P. That item reads:
  "W22 is validated for pure-component behaviour only (A38-A40, spec §11); there is no mixture VLE validation, and
  k_ij = 0."
- The row's `note` describes a different item: "pr-c1-v1 bound by no model at M01; M02 lists its limitations with
  its units".
- The envelope's `property_model` axis now lists `providers: [pr-c1-v1, syn001]`. The list is derived from the
  shipped modules: `scripts/t08_support_matrix.py:110` collects every `openflowsheet.thermo.*` module that has a
  `PROVIDER_ID`.
- So `PrC1Provider` is shipped, importable and advertised.

The rendered `docs/support-matrix.md` makes the gap visible:
- it prints "Components: `A`, `B`, `C`; provider `pr-c1-v1, syn001`" next to "Domain: T in [280, 440] K";
- it states nowhere that `pr-c1-v1` has no mixture VLE validation and uses k_ij = 0.

T08 §5.7 defines E as "user-facing" and gives the `reviewer` the job of catching an E filed as P.

**Fix.**
- Add an L-row (the next free id after L41) stating:
  - `pr-c1-v1`'s components and domain (200–1000 K, 10⁴–3 × 10⁷ Pa);
  - that it is validated for pure-component behaviour only, within spec §11's bands;
  - that it has no mixture VLE validation;
  - that k_ij = 0, with the stated effect (±3 % on the separator's vapour NH₃ per 0.1 in k_H₂–NH₃);
  - that no model binds it yet.

  Its evidence is A38–A40 and spec §11/§17.
- Re-class `limitations[3]` as E pointing at that row, and correct its `note`.
- Re-render the support matrix; the M01 tally becomes 1 E and 6 P.

If the design lane would rather hold that an unbound provider is not user-facing, the envelope must stop listing it
on the axis. T08.A20 holds the axis to the shipped code, so that is not available. E is the only consistent class.

### F2 — should-fix — `admissible_roots` can return values that are not roots near a double root, and the provider reports them as `ok` (*measured*, P3, P7)

**Evidence.** `pr_c1.py:373-408`.
- The branch is chosen by the sign of the discriminant computed from (c2, c1, c0).
- The trigonometric candidates are then polished by 8 Newton steps.
- Nothing checks that Newton converged.

Near Δ = 0 the trigonometric form puts two candidates at the cubic's local extremum. Newton started at a near-zero
slope jumps away and has not converged after 8 steps.

Pure NH₃ at 400 K and P = 10 025 791.149338482 Pa:
- **True roots (mpmath):** 0.486253 is the only real one; the other two are a complex pair, 0.222075 ± 2.8 × 10⁻⁸ i.
- **Returned:** (0.069921, 0.486253, 0.556360). The residuals are −9.6 × 10⁻³, 0 and 7.8 × 10⁻³.
- **`evaluate_phase(LIQUID)`:** answers `ok` with Z = 0.06992, h = −66 543 J/mol and ln φ_NH₃ = 3.362. The answer
  should be `unsupported`, `no_liquid_root`.
- **At P = 10 025 791.149338447 Pa:** two distinct "roots" come back, (0.22208, 0.48625). The first is the real part
  of the complex pair. Amendment 1's "two admissible roots treated as three" rule then labels it a liquid.

**Scope.**
- The window is about 30 ulp of P wide (≈ 6 × 10⁻¹⁵ relative) at each spinodal crossing.
- A 20 000-state random scan over the whole domain (pure NH₃ and mixtures, P2) found a worst root error of
  4.4 × 10⁻¹⁵, no empty result and no count mismatch with mpmath.
- So the defect is confined to near-double roots.
- No registered state, and no flash bisection in 1 788 random TWO_PHASE solves (P4), comes near one.

**Why should-fix and not must-fix:** it is unreachable in the loop. But it is a silent wrong `ok`, and metastable
liquid evaluations (allowed, state L2) are the path that leads there.

**Fix.**
1. Keep a candidate only if Newton converged: the last step is ≤ a few ulp of z, or |f(z)| ≤ c·u·Σ|terms|. Drop
   duplicates.
2. If the three-root branch leaves fewer than three converged roots, take the isolated (well-conditioned) root,
   deflate to a quadratic and solve it with the stable formula. A negative discriminant then means one root.
3. Add the 400 K state above as a regression test (LIQUID → `no_liquid_root`).
4. Correct R-197's rationale: the measured two-root cases are unconverged iterates, not a split double root.

The rule itself stays.

### F3 — should-fix — The boundary answers `ok`, `ZERO_FLOW` for inlets outside nTP-v1's state space (*measured*, P8)

**Evidence.**
- `boundary.py:356` tests `inlet.is_dormant`, which is `sum(n) == 0.0` (`thermo/__init__.py:123-130`).
- That test comes before anything checks the inlet's flows or its T and P. The only such check is the provider's
  flash, at step 3.

Measured with the stand-in:

| Inlet | Result |
| --- | --- |
| n = (0.5, −0.5, 0, 0, 0) at 673.15 K, 10⁷ Pa | `ok`, `ZERO_FLOW`, outlet all zero. This violates the reactor's own component rows for H₂ and N₂ (§8.2). |
| n = 0 with T = NaN | `ok`, T_out = NaN, `extrapolated` |
| n = 0 with T = 50 K, P = −1 Pa | `ok` |

`pr-c1-v1` refuses all three, because it checks the domain before dormancy (A50). The spec's check order (§8.12,
Amendment 1: (1) component set, (2) dormant) created the gap.

**Fix.**
- **Spec:** insert a step between (1) and (2): finite, non-negative flows and finite T and P, else `out_of_domain`.
  This is a one-line amendment to §8.12 (design lane).
- **Code:** a three-line check in `Boundary.evaluate`, plus one test.

The dormant labels themselves stay free (ADR 0001 D3.1), within finiteness.

### F4 — should-fix — Q-N4's choice cannot be undone by reverting `1621d65`

**Evidence.** The message of commit `1621d65` says: "Isolated so that Frank declining Q-N4 is a revert of this
commit."

The loader was added later (`52fdca9`). It reads through `packaged(RECORDS_PATH)` (`pr_c1.py:166-169`). With the
entry gone from `PACKAGED`, `packaged()` raises `KeyError` (`resources.py:42-47`). So reverting `1621d65` disables
`pr-c1-v1` altogether.

The spec's fallback for a declined Q-N4 is "the provider reads the records from a user-supplied path". That code does
not exist.

**Fix.** Choose one:
- state the true reversal path where the claim is relied on (progress / R-158 / Q-N4): a revert plus a loader change;
- or give the loader a path-based entry now (`parse_records(Path.read_bytes())` already exists), so that the revert
  stays isolated.

### F5 — should-fix (documentation) — The flash can miss a genuine crossing near T_c,EOS; the declared limitation should state the measured region (*measured*, P5, P6)

**Evidence.**
- I sampled 497 random states that end on the `no_liquid` route while pure liquid NH₃ is stable (200–405.5 K,
  10⁶–3 × 10⁷ Pa).
- In 5 of them h(y) ≥ 0 on the vapour branch between two samples. The largest excursion was 0.0047.
- All five lie at 373–398 K and 1.05–1.24 × 10⁷ Pa, with the crossing at y = 0.80–0.99.
- In each, the crossing sits just before the vapour branch ends, where the largest root jumps from Z ≈ 0.35 to the
  liquid branch at Z ≈ 0.21.

Example (P6): T = 393.0590 K, P = 1.0675 × 10⁷ Pa, IDAES light-gas proportions.
- h ≥ 0 on y ∈ [0.9558, 0.9676]; the samples 61/64 and 62/64 straddle that interval.
- A feed of 50 mol/s NH₃ with 0.835 mol/s light gas comes back VAPOR (`no_liquid`).
- The convention's answer is TWO_PHASE with y* ≈ 0.9558.

This contradicts ADR 0026 D2's "y* is the smallest root on (0, 1)". The limitation is declared in §17 and in
`describe().numerical_limitations`, but not where it applies.

**No effect on the loop:** at y* ≈ 0.95, a feed with NH₃ ≲ 20 % is undersaturated, and the answer is VAPOR either
way.

**Fix.**
- Minimum: quantify the region in §17 and in the `describe()` text.
- Optional (design lane): between consecutive samples, detect the switch of the largest root to the liquid branch.
  Bisect for the switch point and evaluate h on its vapour side; if h ≥ 0 there, that bracket holds the root.

The 1 788 TWO_PHASE solves of P4 all close the equilibrium row at ≤ 10⁻⁹ on the provider's own evaluations. The
bisection never converged onto a branch jump.

### F6 — note — A22's 1 ulp is a proven bound, reached at a rounding tie; exact closure costs nothing (*measured*, P1)

- **Measured.** At F11, vapour NH₃ 0.021869063076813314 + liquid 0.14313093692318668 = the feed (0.165) − 1 ulp.
  F1, F5 and F13 close exactly.
- **Why 1 ulp.** |fl(v + fl(n − v)) − n| ≤ ulp(n)/2 + ulp(n)/2. The bound is reached when the subtraction ties.
  The tolerance is a proof, not a margin.
- **Optional (spec §5.4 step 7).** Set the vapour's NH₃ to v′ = fl(n − l), with l = fl(n − v). Sterbenz makes one of
  the two subtractions exact in either regime, so v′ + l = n exactly. A22 could then be asserted bitwise. v′ differs
  from v by at most 1 ulp, far inside A15's 10⁻¹¹.

### F7 — note — A45's measured value and wording

- §9.9 says "measured ≤ 2.7 × 10⁻⁸ at 800" and "37 times" (spec lines 811–812). Both hold only at the nominal T_in.
- The 693.15 K neighbour gives 2.98 × 10⁻⁸, which is 33.6× below the refusal threshold. The manifest's A45 check
  measures exactly that.
- The manifest's own `limitations[4]` still says 2.66 × 10⁻⁸.

Correct both in the next revision.

**For M02:** §8.15 asserts A45 on "every accepted adapter run". Between 10⁻⁷ and 10⁻⁶ the boundary accepts a result
that A45 fails. If a Q-F4 corner lands in that band, the sweep "fails" A45 while its result is `ok`. Name the runs A45
applies to: A41's three points.

### F8 — note — The boundary's behaviour enters no identity

- `reactor_standin._artifact_hash` hashes `reactor_standin.py` only (`reactor_standin.py:188-190`).
- `boundary.py` holds every refusal, the projection, the check order and the envelope, and it enters no model
  identity.
- This follows ADR 0008's pattern for shared kernels, so it is consistent.
- For M02's real reactor, though, the boundary *is* most of the unit's behaviour. M02 should put `boundary.py`'s hash
  into the reactor's identity, or record why it does not.
- Separately, `Boundary` does not validate `n_tubes`; only `ReactorStandin` calls `require_positive`. M02 constructs
  `Boundary` directly, so give `Boundary` a `__post_init__`.

### F9 — note — Verification quality

- **A12.** Its homogeneity rows (Z, v, h and ln φ) hold by construction of the projection (`pr_c1.py:759-770`), so
  they pin the projection's algebra, not the derivatives. Gibbs–Duhem and symmetry are the substantive identities,
  and A10 (an independent 50-digit check at 10⁻⁹) is the real derivative test.
- **A10's coverage.** No derivative is checked at a three-root state, and none at a pure-NH₃ vapour's n-derivatives
  (light gases at infinite dilution). These run the same code path, so the risk is low. M02's mixers will exercise
  them.

### F10 — note — Smaller items

- **`components.yaml` header (lines 7–8).** It names `components_crosscheck.py` and `components-crosscheck.json`; the
  files are `external_crosscheck.py` and `external-crosscheck.json`. Fixing the comment moves `data_sha256` and every
  "made from the committed records" check, so defer it to the next record revision.
- **The manifest's `requirements: ["D08"]`.** This is acceptable: plan line 303 maps D08 to M01, and W21/W22
  (plan lines 350–351) cannot match the frozen `[DA]nn` pattern. Every v0.2 package will hit this. The design lane
  should decide before M07 how v0.2 manifests carry W-ids: a schema ADR, or a fixed limitation formula.
- **R-217's filter.** `key[0].split("/")[1][0] in "PKT"` selects v0.1 by the package directory's first letter. It
  works today but is fragile; an explicit list of the 18 v0.1 manifest paths would pin it.

## 3. Rulings on the "least sure" items

| Item | Ruling |
| --- | --- |
| A22 at exactly 1 ulp against 1 ulp | **Accepted.** The bound is proven and reached at a tie (F6). No margin is needed for a proof; exact closure is optional. |
| A45 2.98 × 10⁻⁸ against 10⁻⁷ | **Accepted.** It is a committed record constant that the gate never recomputes, so a 3.4× margin cannot flake. Correct the §9.9 wording and `limitations[4]` (F7). |
| A52 mapping 1 ulp against 2 | **Accepted.** It is deterministic on a fixed record and fixed code. Note that 2 ulp is not a general bound for a 5-term sum; it is a regression value of this input. |
| A38–A40 at 1.18–1.58× inside their bands | **Accepted as validation statements.** They are deterministic (model against CoolProp), not tolerances. The bands are round numbers set with the measurements in view, so the W22 verdict must read them as the stated model error, not as margins passed. |
| Harvest `limitations[0]` (W-ids) | P: correct. |
| Harvest `limitations[1]` (adapter halves to M02) | P: correct. It is a planned M02 acceptance under R-200, not a defect handed on, and the plan carries it. |
| Harvest `limitations[2]` (stand-in synthetic, unbound) | P: correct. U04 refuses the stand-in; nothing user-reachable. |
| Harvest `limitations[3]` (no mixture VLE, k_ij = 0) | **E, not P (F1, must-fix).** |
| Harvest `limitations[4]`, `[5]` | P: correct. Fix the number in `[4]` at the next manifest (F7). |
| Harvest `checks[46]` (A47 `not_applicable`) | P: correct, as `[1]`. |
| The A33 reading | **Accepted.** The frozen-path changes are the axis and L40, which the spec ordered, plus the seven harvest rows, which T08.A21's completeness rule requires. No registered value moves. The manifest's A33 note predates the harvest rows (they came in `cec8a01`, after `6c81683`), so it is accurate for its commit. |
| `requirements: ["D08"]` | **Accepted** (F10). The W-id question goes to the design lane before M07. |
| Q-N4: records as package data | **The default is acceptable.** Frank's decision is still open. The reversibility claim is false (F4). |
| Phase logic: θ against θ_c via T_c,EOS; v against v_c,EOS | **Sound and correctly implemented.** For pure NH₃, θ is monotone in T. PR-06's spinodal straddle makes the v_c rule exact wherever there is one root. |
| Two admissible roots treated as three | **The rule stands. R-197's rationale needs correcting (F2):** the two-root cases actually observed are unconverged Newton iterates. |
| The y*-flash (fixed samples, then bisection) | **Sound.** The trivial solution sits only at y = 1, which is excluded. On the dense branch h′(1) = 1 (Gibbs–Duhem), so no false bracket appears next to 1. Where pure NH₃ has three roots and its liquid is stable, h(1⁻) > 0 guarantees a crossing. The one gap is F5, which is declared but not quantified. It is clearly better than the feed-split bisection it replaced (F5's trap). |
| Refusal semantics and check order (§8.12, BD-06) | **The provider's order is sound** (A50). **The boundary's inlet-phase-before-hard-domain order is sound:** BD-06's argument holds, because T_c,EOS = 405.55 K < 573.15 K. One step is missing before dormancy (F3). |
| Rights and sources | **Acceptable** under ADR 0006: a handful of published constants per component, with citations; NASA TM-4513 is a U.S. Government work; ATcT and HEOS are reference-EOS constants quoted, not extracted; no grant is relied on. k_ij = 0 has its sensitivity stated (§4.2), and the describe() text carries it. |

## 4. ADR 0026 and ADR 0027

**ADR 0026 may move to Accepted.**
- Its condition is met: the manifest is `tested` with WO-1–WO-4, and this review passes the provider.
- D1–D6 are implemented as decided and verified independently.
- F2 is a defect in the root solver's robustness, and F5 is a declared limitation; neither touches a decision. Fix F2
  before M02's units consume the provider (they will evaluate metastable liquids). Quantify F5 in §17.
- F1 (must-fix) concerns the envelope, not the ADR. It must be fixed before M01 merges.

**ADR 0027 still needs:**
1. M02's adapter halves of A41–A48, including A47 (a) bitwise at the evaluation and (b) 10⁻⁶ through the boundary;
2. a `reviewer` pass on M02's adapter against §8;
3. the §8.12 amendment of F3 (a state-space check before dormancy), preferably made before M02 builds on the check
   order;
4. M02's binding of the stand-in recorded as superseding A49's "not bound" clause under R-199 (the known follow-on);
5. M02's choice on the boundary's identity (F8).

## 5. Probes (re-runnable; scripts were in the session scratchpad)

| Probe | What it did |
| --- | --- |
| P1 | Flashed F1, F5, F11 and F13. Printed (v + l − n)/ulp(n) for NH₃: F11 gives −1; F1, F5 and F13 give 0. |
| P2 | 20 000 random (T, P, y) states over the domain (a third of them pure NH₃). Compared `admissible_roots` with mpmath `polyroots` at 40 digits. Worst error 4.4 × 10⁻¹⁵, no empty result, no count mismatch. |
| P3 | For three compositions and T ∈ {220, …, 400} K: bisected the P at which the root count changes, then evaluated ±60 ulp around it. Polished values with residual up to 1.3 × 10⁻², and two-root returns at 400 K. |
| P4 | 6 000 random flashes (T 200–405.5 K, P 10⁵–3 × 10⁷ Pa). For each TWO_PHASE result, checked ln y* + ln φ^V − ln φ^L with the provider's own `evaluate_phase`. All 1 788 are ≤ 10⁻⁹, and no evaluation was refused. |
| P5 | 4 000 random flashes at NH₃ = 50 mol/s. For `no_liquid` results with pure liquid stable, scanned h on 4 000 points: 5 of 497 have max h ≥ 0. |
| P6 | A fine scan (2 × 10⁴ points) of h at F12 (max −5 × 10⁻⁵ at y → 1: no crossing, as registered) and at one P5 state (a genuine continuous crossing at y = 0.9558; a branch jump at y ≈ 0.9676). |
| P7 | P3's 400 K state, against mpmath, with `evaluate_phase(LIQUID)` and `flash` at four pressures. |
| P8 | `ReactorStandin.evaluate` on the three invalid dormant inlets of F3. |
