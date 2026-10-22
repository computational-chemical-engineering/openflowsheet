# S05 (IAPWS-95, `iapws95-v1`) — design-lane review and ruling round

**Reviewer:** design lane (`reviewer`), 2026-10-22, branch `wp/C10` at `7a7e346`. **Brief:** `docs/briefs/S05-review.md`.
**Register:** R-595…R-599. **Spec amendment:** `docs/derivations/S05-IAPWS95-spec.md` §14 (dated 2026-10-22).
**Adversarial tests:** `tests/test_s05_review_adversarial.py` (3 controls pass; 5 strict xfails are the F1 failures).

## Verdict

**Not ready for `tested`.** The formulation, the jet, the Maxwell and Tsat solves, the refusals and the cache are
sound. However, the density solver can answer `ok` with an O(10–100 %) wrong density on about 1 % of states (F1), and
A22 passes over two such answers on its own grid. After WO-S05-3 (below), the manifest can be re-taken at `tested`. The
five strict xfails act as the acceptance test: they turn into XPASS failures when the fix lands. This review does not set
`reviewed`. Rights (C10-Q1) and the supercritical label (C10-Q2) remain Frank's.

Counts: **1 must-fix, 3 should-fix, 5 notes**; 8 rulings.

## Findings

**F1 — must fix.** `src/openflowsheet/thermo/iapws95.py:675-697` (`_bracketed_density`) together with `:120-122`
(`_converged`). The solver accepts a bisection midpoint as converged.
- *Mechanism.* At the best double ρ, the Newton correction can be smaller than half an ulp of ρ while the residual is
  not zero (liquid: ρ(∂p/∂ρ)/p ≈ 1e4). Then `new == rho`, and `rho` is the bracket end that was just set, so
  `low < new < high` fails and the safeguard bisects to `0.5*(low+high)`. The far end of the bracket never moved during
  one-sided Newton convergence, so the midpoint is far from the root. The step is large, and the previous step was
  ≤ √ε. The stagnation clause, `previous <= FLOOR_ONSET and step >= previous`, then returns the midpoint.
- *Failure scenarios (measured).*
  - 700 K, 1e8 Pa, VAPOR (on A22's grid) answers `ok` with ρ = 480.66 kg/m³ against the true root 651.77. h is off by
    +2947 J/mol and cp by +107 %.
  - 750 K, 1e8 Pa, VAPOR is also wrong.
  - 599.79 K, 1e8 Pa, LIQUID gives ρ = 720.86 against 791.75, and h is off by +222 J/mol.
  - On a 180 T × 61 P grid, 99 of 10 980 answers have a root residual > 1e-13 in density units (80 of them > 1e-3).
    97 are LIQUID below T_c, spread over 10³–10⁸ Pa.
  - The registered §5.2 states happen to miss the condition, so A05/A06 pass.
- *Minimal correction (R-595).*
  1. A Newton correction with |Δρ| ≤ 4ε·ρ, including one that rounds to zero, is convergence. Test it **before** the
     bracket safeguard.
  2. The stagnation clause applies only to a Newton step that stayed inside the bracket, never to a bisection step, and
     the stalled step must itself be ≤ √ε.
  3. Apply the same `_converged` change in `_metastable_density`, `_saturation` and `_tsat`. These are not wrong today:
     on a dense check, the Maxwell density residual is ≤ 1.7e-14 over 404 T, and p_σ(Tsat(P)) = P to 1e-12 over 300 P.
     The clause is unbounded in all of them, however.

**F2 — should fix (verification).** `tests/test_s05_envelope.py:120-122` (A22) asserts only `ok`, (∂v/∂P)_T < 0 and
cp > 0. A wrong root on the stable branch satisfies all three, and A22 passed over F1's 700 K and 750 K answers.
- Z cannot witness the root any more: at a solved root, Z ≡ Pv/(RT) by R-596.
- *Correction.* At every A22 answer, also assert |p(M/v, T) − P| / (ρ(∂p/∂ρ)_T) ≤ 1e-12, with p and ∂p/∂ρ from
  `phi_jet` (the helper `root_residual` in the adversarial file). The measured floor is ≤ 5e-16, and a 1e-9 density
  error is still caught.

**F3 — should fix (rights statement).** `scripts/s05_evidence_manifest.py:88-100`. The manifest limitations say the
file is unpackaged and the tables are uncompared. They never say that the IAPWS terms of use are **unread** (iapws.org
refused, 2026-10-22) and that the rights row is `unresolved`. Ruling 8 gives the text.

**F4 — should fix (spec/data consistency).** `docs/derivations/scripts/s05_crosscheck.py:51` has `sat_Tsat: "2e-7"`,
while spec §6.2 and `C10_DECISIONS.md` say 1e-7.
- With 1e-7, C11's 10× margin would fail: iapws's worst is 1.03e-8, and 10 × 1.03e-8 = 1.03e-7.
- The code value is the right one. §14 amends the text to 2e-7, with that derivation.
- A09 still holds the implementation at 1e-9.

**Notes.**
- **N1.** `_tsat_bounds` (`:664-670`) raises `RuntimeError` instead of returning a typed refusal. It is reachable only
  by starving Newton, and A30 clears the cache correctly (`test_s05_envelope.py:332-339`).
- **N2 (performance).**
  - `_pressure` evaluates the full order-3 jet, including the bivariate non-analytic jet, at every Newton iteration,
    where only φʳ_δ and φʳ_δδ are needed.
  - `_tsat` runs a full Maxwell solve per iterate and fills the LRU cache with iterate temperatures.
  - Neither is a correctness issue.
- **N3.** A04's `ttt` at `R6_647`: the provider and CoolProp deviate from the 50-digit reference by the same 6.8e-13.
  That points at the reference's numerical third derivative, or at a cancellation that both double evaluations share.
  It sits 15× under the bound.
- **N4.** `flash` answers `ok` without solving the density, so a flash answer does not guarantee that `evaluate_phase`
  converges at the same state. It is acceptable because the flash reports only a label and outlets.
- **N5.** `_domain_violation` also refuses a negative or non-finite flow as `out_of_domain`, which §4.5 row 4 does not
  list. It is additive and recorded in §14.

**Verified sound** (with the evidence):
- The Maxwell Newton: its Jacobian was re-derived, J = [[K′, −K″], [K′/δ′, −K″/δ″]], det = K′K″(1/δ′ − 1/δ″), and it
  matches `:607-610`.
- The jet arithmetic: A03/A04 are checked against an independent mp.diff reference. The provider's third-partial floor is
  ≤ 6.8e-13.
- The δ = 1 zero jet.
- Refusal precedence (§4.5).
- The exact-double-T `lru_cache`: it does no quantization, it is a pure function of T, and A23 is bitwise.
- Generator independence: `s05_reference.py` imports only the standard library and mpmath, and nothing from `src/`.
- A17's floor under the amended stencils (R-597): ≤ 5.7e-13 at NC, ≤ 2.8e-13 at the corners, and ≤ 1.3e-14 at the band
  probes.

**Not examined:**
- the inside of `s05_reference.py`'s claims (not re-derived), and `--check` was not re-run;
- `s05_crosscheck.py` beyond its bounds;
- A25–A27 and the T08/T07 edits;
- the mutation plugin's mechanics;
- mypy.

## Rulings

1. **Q-floor (Newton rule)** — accepted, with conditions (R-595). The √ε-onset stagnation test is an acceptable
   operational reading of "residuals at their floor". It must, however, only accept a *Newton* step, the stalled step
   must be ≤ √ε, and a correction that rounds to zero counts as converged. No Σ|terms| floor estimate is required: the
   guard is F2's root-residual check.
2. **p_σ from the vapour side** — accepted (R-596), and §3.5 is amended. At the Maxwell root both sides are p_σ. The
   liquid side carries a conditioning of (ρ/p)(∂p/∂ρ) ≈ 3e6 at T_t (measured 5.4e-8 against ≤ 1.6e-14 for the vapour).
3. **Z = P/(ρR_sT) at a solved root** — accepted (R-596), and §3.1 is amended.
   - On the branch, P/(ρ(T, P)R_sT) and 1 + δφʳ_δ(T, ρ(T, P)) are the same function, so the jet's partials are its
     partials.
   - The quotient avoids the O(1) cancellation when Z ≪ 1.
   - Consequence: Z does not witness the root, which is why F2 is needed.
4. **A17 / Q-6** — FD_TOL = 1e-10 stands (R-597). No derivation shows it wrong. What was wrong is the *stencil* at three
   classes of state, which §6.3's truncation argument ("away from the box") never covered.
   - (a) **NC.** Truncation is (h³/3)|f‴| and measured 1.25e-9 at h = 1e-6·x. A 10× margin needs
     h ≤ 1e-6·x·(1e-11/1.25e-9)^{1/3} = 2e-7·x. Use h = 1e-7·x (measured 5.7e-13).
   - (b) **Box edges.** Use the inward one-sided second-order stencil:
     |s(−3f₀ + 4f₁ − f₂) − 2h f′| ≤ FD_TOL·max(|f₀|, |f₁|, |f₂|, s_f), with f_k = f(x + k s h) and s pointing into the
     box. Truncation is (2/3)h³|f‴| and roundoff is 4× the central stencil's (measured ≤ 2.8e-13).
   - (c) **Band probes.** h_P = (ε_σ/4)·P and h_T = (ε_σ/4)/|d ln p_σ/dT| (from the provider's own Psat slope;
     2.4e-8·T at 450 K), so every stencil point stays in the answered set (measured ≤ 1.3e-14). Detection power for h(T)
     is about 2e-4 relative.
   - All 21 xfails become ordinary cases, and none is dropped.
5. **A29 m5** — restated (R-598). As written, m5 is an equivalent mutant *by design*: p_σ on (647.0 K, T_c) lies inside
   the box (§4.3). That is evidence the edge is invisible outside the box, not a test gap.
   - New m5: "T_c replaced by 647.0 K in step 2": in `_rule`, `if temperature >= T_C:` → `if temperature > T_SIGMA_MAX:`,
     caught by A15. This was verified: the `NC_liquid` control is refused `phase_not_stable`.
6. **Q-5** — A04 stays at 1e-11·max(|ref|, 1) (R-598). The measured floor is ≤ 6.8e-13, and CoolProp's `d3alphar`
   agrees with the reference to the same 6.8e-13, so 10× that, 6.8e-12, is ≤ 1e-11.
   - Admitting third partials in the generator (via CoolProp's agreement, already in `s05_crosscheck.json`) is a
     design-lane follow-up. It does not block `tested`.
7. **Q-6** — answered by ruling 4.
8. **Rights (C10-Q1)** stays Frank's (R-599). The manifest must state, as a limitation, that:
   - "the IAPWS terms of use for R6-95 were not read (iapws.org refused, 2026-10-22); the rights row is `unresolved`";
   - "`benchmarks/s05/iapws95_coefficients.json` is unpackaged (A26), so `iapws95-v1` runs only from a source checkout";
   - "Tables 6–8 are not compared";
   - "ADR 0045 remains Proposed";
   - "no `released` status and no wheel carrying the coefficients until C10-Q1 is answered";
   - "`reviewed` would cover numerics only, not rights".

## Fix work order WO-S05-3 (build lane, `opus-engineer`, ~80k context)

1. **R-595.** Change `_converged` and `_bracketed_density` as in F1: a zero-rounded or ≤ 4ε correction is converged
   before the safeguard, and stagnation applies only to Newton steps ≤ √ε. Apply the same rule in `_metastable_density`,
   `_saturation` and `_tsat`. Remove the 5 strict xfails in `tests/test_s05_review_adversarial.py`.
2. **F2.** Add the root residual to A22 at every answer, and add a dense grid of 180 T × 61 P (the review's grid) with
   the same check. Show the check fails on the unfixed commit.
3. **R-597.** Change A17's stencils as in ruling 4. Delete `FD_UNREACHABLE` and `BAND_FD_UNREACHABLE`, so that no case
   is dropped.
4. **R-598.** Change m5 in `scripts/s05_mutations.py` and its xfail. S05.A29 then has to pass 8/8.
5. **R-599.** Add the manifest rights limitation (F3). Re-take `evidence/S05/<fix commit>/manifest.json`, then harvest.
   Run the S05 tests, `s05_reference.py --check` and ruff/mypy. Run `scripts/gate.sh` before the merge.
6. Log each choice in `docs/C10_DECISIONS.md`. Commit each item separately.

Acceptance: the five xfails XPASS→removed, A17 has no xfail, A29 passes 8/8, and A22 carries the root residual. The
`reviewer` checks only the WO-S05-3 diff (F1's rule). It is not a second full pass.
