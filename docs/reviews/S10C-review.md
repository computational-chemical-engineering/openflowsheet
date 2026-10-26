# S10-C: independent review (design lane, `reviewer`), 2026-10-26

Branch `wp/S10C`, range `ffcb387f..bd4f4fc7` without the merge of `main` (WO-1 to WO-4). Brief
`docs/briefs/S10C-review.md`. Built against `docs/derivations/S10C-design.md` (`b348e9b4`), ADR 0049 (Proposed),
`docs/derivations/S10C-spec.md` (WO-S) and `benchmarks/s10c/reference_values.yaml`. Build log `docs/S10C_DECISIONS.md`.

**What was read.** The design note §0–§4, §6 and §7. The spec §0–§6. The whole production diff (11 files, +1537/−58):
`equilibrium_form`, `gamma_phi`, `gamma_phi_blocks`, and the dispatch in `saturation_band`, `tp_state`, `cascade`,
`ph_kernel`, `region`, `column`, `column_solve` and `column_blocks`. Today's `_band_route`, `_saturation_split`,
`property_method_refusal` and `region._admissible`. The G4, G6, A36 and G7 tests in full. The other test modules by name
and setup. G1's header.

**What was run.** `git diff --stat` over G2's frozen paths, which is empty (only the S03 A04 amendment under `tests/`
outside the new files). Two probes, not committed, computing P1–P3 of S10's two record sets over 150–1200 K
(finding F2). No test suite was run; the build log's 2612 passes, G1 and G9 are not repeated here.

## Verdict

**Sound numerics and a clean SYN-001 isolation, with one must-fix in the verification.** The constant-β point, the
band-first PH route, the K and enthalpy blocks, the dispatch and the ω = 1/2 sweeps implement the design. The residual
and the Jacobian describe one function at every flowing state. A non-admitted provider reaches today's code at every
dispatch site. The must-fix: G3, the constant-β point's registered gate, has no test against its registered references
(F1). Counts: must-fix 1, should-fix 1 (with a decision), errata 3 (written as spec Amendment 1, §11, R-777…R-781),
notes 5.

## Findings

**F1 — must fix. G3 (S10C.A01–A06) and A60/A61 have no test.** No test reads `ref.band_points` (35 registered
points), `iterations_expected`, `ref.theorems.T2` or the narrowed copy's registered positions. The only band-point
reference any test reads is `BP-R01`, in `tests/test_s10c_region.py:30`, for the admissibility screen.
`tests/test_s10c_band_point.py` predates WO-S, which merged after WO-1. It checks independent but different things: the
Λ ≡ 1 limit by bisection, one component, the fixed point, `stability()` at the dew point, and positions against the
provider's verdicts. A02 cannot be observed at all, because `BandTemperature` carries no iteration count, so R-776's
"the registered band points assert ≤ 100 iterations, so a slower contraction shows" is not wired. A60 (`--check`) and
A61 (records SHA-256) are neither tests nor commands in WO-5's list.
*Scenario:* the risk is narrower than the gap. WO-1's fixed-point test re-evaluates K at the returned `(T, x)` at 60
states, so it already catches any answer that is not a fixed point to 1e-12, MB1–MB3 included. Today these still pass:
a contraction slowed to 500 iterations (A02, R-776's watch); a different fixed point of a ternary, which A01's
comparison with the 50-digit point would catch and the fixed-point test cannot; a wrong infinite-dilution `k_values`
entry off F; a changed position at the registered narrowed states; and the T2 states' `tm_star`. *Minimal correction:*
add one parametrised test over `ref.band_points`, covering A01 (position; T, x and every component's K), A03, A04
(`BP-I01.closed_forms`), A05 (vanishing tm at each inside β = 1 point, and `tm_star` at the two T2 states) and A06. Count
`_Point.temperature` calls with a spy for A02 (Amendment 1 E3: no production field is added). Make A61 a test. Make A60
a manifest command, or a slow-marked test. The manifest cannot claim G3 until these exist.

**F2 — should fix, needs a decision. T1–T5's premises belong to a record file, but admission goes by a name.**
`equilibrium_form.ADMITTED` keys on `(provider_id, reference_convention)`. `wilson_ig.load_records` accepts any file
declaring `WILSON-IG-ref-v1` or `S10-VER-ref-v1`, and the tests themselves build Λ ≡ 1 and narrowed copies that way.
Neither the loader nor `admission` checks P1–P3. *Scenario:* the real records' parameters with the T domain widened past
750 K. My probe puts water's `c_p^0L` at ≤ 0 above 750 K and methanol's above 875 K, so P2 fails. `Ḣ^L(T)` is then not
monotone, the liquid route's bisection (`ph_kernel._single_phase_route`) returns one of several roots, and the closure
rows accept it: a single phase satisfies material and equilibrium by construction. If P1 failed, the region decision
itself could be wrong. Both committed sets satisfy P1–P3 with wide margins on their domains (spec §2.1). *Done here:*
the scope statement (Amendment 1 E4). *Open:* whether to add an admission-time P1–P3 check now. I would defer it to the
package that makes the provider selectable in flowsheets (design Q1). S10-C is library-level, and a check needs either
the generator's closed-form minima or a grid, which is a design choice of its own. Default recorded in R-781.

**F3 — erratum (done, R-778). F-W3-1 is right, and ADR 0049 D6 over-claims in the same way.** The rows' values and
their chain-rule entries are probe-independent. The direct entries `−K_i V` (equilibrium) and `K_i` (total condenser's
bubble row at `V_2 = 0`) read the probe. The rows are Lipschitz but not differentiable at `L = 0`, and the one-sided
limits depend on the approach direction. No converged value moves. The text is Amendment 1 E2.

**F4 — erratum (done, R-777). W1-3 is ratified, and it has a fourth reorder that is not logged.** Besides (a)–(c), the
"t' beyond an unknown end → evaluate that end" rule is applied before the midpoint rule
(`gamma_phi.py:308–314`). In the note's order it is dead too, because the open-bracket test has already moved t'
inside. The text is Amendment 1 E1, with the budget argument: at most three evaluations per halving, ≈ 156 worst case
against 200.

**F5 — note. The "Not reached" branch is reachable at ulp level** (`ph_kernel.py`, `_region_route`, after
`_band_route`). `big_f(1.0)` builds the vapour as `n_i·1·K_i/K_i` (`band_split`), which is not `n` bitwise. `H(1)` can
therefore differ from `h_d` by ulps, and a target within ulps below `h_d` makes `_band_route` return `None`. The answer
is still a typed `ph_ill_conditioned`. Reword the comment to "not expected"; no code change.

**F6 — note. G1 does not see the flowsheet paths.** These are K02–T04 units through `tp_state.enthalpy_flow`,
`single_phase_admissible` and `region._admissible`, and pr-c1-v1 flowsheets. The `tests/test_t0{2,5,5b,6,7,8}*identity*`
tests hold them. They last ran in the full suite at `a15452e6`, before WO-2 edited `region.py` and `ph_kernel.py`. They
belong in G10's full gate, and the manifest should cite them as the identity evidence for those paths.

**F7 — note. Private names cross modules.** `cascade.py` imports `gamma_phi._ln_k`, and `gamma_phi_blocks` imports
`blocks._unwrap`. This is harmless, but a public `ln_k_of(components, …)` would keep `gamma_phi`'s surface honest.

**F8 — note. The flowing set comes from different places.** `_band_first` takes it from `n > 0`; `band_point` takes it
from `z > 0` (E-1). They differ only for `n_i < 2⁻¹⁰⁷⁵ n_tot`. That stream then takes the multi-component path with a
one-component band (`T_b = T_d = T_sat`), which the band route handles. No change.

**F9 — note. A44's detection differs from its wording** (Amendment 1 E3). M2 converges by Newton and is refused by
S08's item 6 (`AcceptanceDefectError`). The test asserts "not an accepted `CONVERGED` answer within A41", which is the
intent. The mutated root's `x_D` is never compared, so the spec's predicted 0.074 offset is not measured. That is
acceptable.

## Rulings on the brief's §3

1. **Build decisions.** All are accepted as built: W1-1…W1-7, W2-1…W2-7, W3-1…W3-4 and W4-1…W4-8.
   - **W1-3** is ratified with erratum E1 (R-777). The reorder is required for the rules to fire at all. The roots and
     the stop rule are unchanged, and the cost falls from a maximum of 1205 to 234 evaluations.
   - **W2-4:** see F5.
   - **W3-2** (`is_dormant` rather than `sum == 0`) is the stricter and correct reading. A mixed-sign input goes to the
     provider, which refuses negative flows (`out_of_domain` → `DomainError`).
   - **W4-1:** see F7.
   - **W4-3(a)** (final flows at `x̄^m`) is within `(1 − ω)·1e-10` of `x^m` and is right.
   - **W4-7** is a build-lane fixture, consistent with ADR 0049 C4 ("Stage B … at the opening level only"). It must
     not be cited as a registered case.
2. **F-W3-1.** Erratum E2 (R-778). It replaces design §4.7's paragraph and ADR 0049 D6's clause. No code change.
3. **F-W3-2.** Erratum E3 (R-779). The YAML governs and the build followed it. An FD check of the VAPOR H-block at a
   liquid composition tests the same function's Jacobian.
4. **F-W4-2.** Acceptable for merge; no change before it (R-780). G9's limit is met: +6.6 % by median and +8.6 % by
   mean against +10 %. The cost is metadata calls, not arithmetic, and G1 proves the path is inert. Memoising the form
   is design Q6's separate decision. If a later package adds dispatch points, memoise by provider object, and prove it
   inert with G1. Re-measure G9 only if WO-5 touches a dispatched path; it should not.
5. **F-W4-1.** Acceptable (R-780), as OQ-2 ruled. Newton lands bounds at `+0.0` and discards outward roundoff on
   structural zeros (`numerics/newton.py`, §5.3, R-064), so the absent flows are inward roundoff, ≥ 0, 13 decades below
   the flow tolerance. A41 compares them against that tolerance. A downstream consumer sees `x ≈ 1e-18` rather than
   an exact binary, which no registered check distinguishes.

## General review (brief §4)

- **Residual and Jacobian.** They describe one function at every flowing state. The K-block's entries are bitwise the
  provider's projected derivatives (A31). FD agrees to 3.8e-8 under the registered stencils (A30), including the
  condenser's `v_2` input. Closed forms agree to 3.1e-15. The full graph converges at order 2.19 and 2.03, and M1
  (n columns zeroed) drops that to 0.34. At an exactly dormant liquid, see F3. The mixture H-block's dormant Jacobian
  `h(T, P, e_j)` is the limit of `h + n_tot ∂h/∂n_j = h_j` (h^E = 0), so it is continuous there.
- **The band-first route.** `_region_route` implements §4.5 steps 1–6 as written: the domain-end enthalpies by band
  position, step 2's refusals, step 3's region by enthalpy, one route, acceptance with K at the candidate's liquid, and
  no fallback. Its preconditions hold except on record files outside the certified sets (F2). Every route lies inside
  the theorem's cover. The TP flash at a domain end inside the band is the provider's answer, typed on failure. For
  C ≥ 3 the band route is either accepted (T4 plus T3's uniqueness make it *the* answer) or ends typed. The one-component
  path's `T_sat` rests on P1 alone.
- **SYN-001 and the allow-list.** At every dispatch site a `False`/`None` resolution falls through to the pre-existing
  body, textually unchanged; the added `describe()` calls are metadata only (Q7: no test counts them). The
  column's refusal keeps S11's cause string `unsupported(column_property_method:<id>)`; only the message changes, as
  §2.3 allows. The cascade keeps S11 (A55). G1's blind spots are listed in F6. `BandTemperature`'s new defaulted field
  changes its `repr`, and the older identity tests passed with it at `a15452e6`.
- **Tests.** G4–G8 read the YAML or closed forms and recompute closure rows independently (A13). The mutations hit
  their paths: M2 patches `column.GammaPhiLnKBlock`, the name `declared_rows` resolves. M4 patches the module constant
  that `relaxed_compositions` reads at call time, which covers Stages A and B. The gap is G3 (F1).
- **ω = 1/2.** SYN-001 is untouched: `compositions is None` makes `change = 0.0`, so the stop test is today's, and
  `_k_values` ignores `liquid`. G1 at `17c19fe6` covers S02 and S08's endpoints. The stop rule is sound. It measures the
  fixed-point residual `|x^m − x̄^{m−1}|`, not the damped step, so damping cannot make it stop early. It also needs
  `|ΔT| ≤ 1e-9 K`, and the final flows use `x̄^m`.

## Not examined

The generator and its 50-digit values, and the design's measurement scripts (brief §5). G1's digest code beyond its
header. The bodies of `test_s10c_forms.py`, `test_s10c_refusals.py`, `test_s10c_region.py` and the Stage B test. The
compile layer's chain rule for block inputs (frozen; evidenced here by the observed order). `column_blocks._build`
outside the diff. Cross-architecture behaviour (CI).

## Before merge

F1 fixed and run. WO-5. The full gate (G10), including the older identity tests (F6). CI green on both architectures.
`reviewed` is not set by this review.
