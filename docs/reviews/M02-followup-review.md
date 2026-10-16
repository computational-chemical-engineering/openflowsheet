# M02 follow-up: review of build log D133–D135 and the ruling on D134

**Lane:** design lane (`reviewer`). **Date:** 2026-10-16. **Branch:** `wp/M02-followup`, `git diff origin/main...HEAD`
(39e6b0c D133, 768690f D134, b6f51d8 D135). **Read against:** `docs/reviews/M02-closeout.md` C1 and §2; R-341, R-343;
V02 alpha `benchmarks/t08/support_envelope.yaml` at `origin/wp/V02-alpha-gate` (R-370). **Register:** R-390. Nothing here
sets `reviewed` or changes a manifest status.

**Verdict: merge.** No must-fix. S1 and S2 are corrections to the stated rationale (comment and build log), not to code.
Neither blocks the merge. Fold them into the next commit that touches `boundary.py`, or into a short follow-up.

**D134 ruling: confirmed (R-390).** The relative slack 4·2⁻⁵² on the inert floor stays as built. Its rationale is
corrected below (S1, S2).

## Findings

**S1, should-fix: the error budget for the slack is miscounted.** `src/openflowsheet/models/c1/boundary.py:78-83`;
build log D134.
- *What the text omits.* It counts 7 half-ulps (u = 2⁻⁵³). It leaves out the rounding of the slack product itself,
  `(inert_min·n_tot)·(1−s)`.
- *n_tot is overcounted for Python floats.* "Four additions" holds only when `n` holds `np.float64`. On Python ≥ 3.12,
  `sum()` over exact `float`s is Neumaier-compensated, about one rounding. Checked on 3.13.5: `sum([0.1]*10) == 1.0`,
  but the same sum over `np.float64` elements is not.
- *The correct worst case* (naive sum) is 8 roundings: the inert sum, n_tot (4), the product, the slack product, and
  inert_min's representation. The representation term is < u in general and 0.857 u for 0.035. The total is just under
  8 u, against a slack of 8 u. The bound therefore holds rigorously for any inert_min, for positive normal inputs:
  - first order: the margin is u − (representation error) > 0;
  - second order: the factor is (1+u)⁷(1−8u) = 1 − u − 35u² + …, which favours acceptance.

  With compensated summation the total is about 4.9 u.
- *The guarantee to state:*
  - exact ratio ≥ inert_min ⇒ accepted;
  - exact ratio < inert_min·(1 − 8·2⁻⁵²) ⇒ refused;
  - in between, rounding decides.
- *Independent check.* 10⁵ minimal admissible states, where n_CH4 is the smallest double whose exact ratio meets the
  floor. Floors 0.035, 0.036, 1/3 and 0.050024…; n_tot from 10⁻⁶ to 10⁶. The code refused 0 with `float` elements and 0
  with `np.float64` elements. The exact comparison refused 11.1 %.
- *Fix.* Restate the budget and the guarantee as above. Also say that the slack applies to every `inert_min > 0`, not
  only to v3's (only v3 declares a floor today).

**S2, should-fix: one claim in the same comment is measured, not proved.** `boundary.py:81-82` says the design
composition is accepted "at every flow scaling instead of by rounding".
- *What the bound does not cover.* A decimal composition built as `n_i = y_i·n_tot` carries its own construction
  rounding: up to ≈ 4 u in the ratio (y_i's representation plus the product, on both sides). The bound in S1 does not
  cover that.
- *Worst case:* 4 u + 4.9 u exceeds the effective allowance of about 7 u.
- *What was measured:* 2×10⁵ plus 4003 scalings, with the largest computed shortfall 1.59·2⁻⁵² (3.2 u), so a 2.2×
  margin observed.
- *Fix.* Say "at every tested scaling".
- *Not adopted: widening to 8·2⁻⁵².* That would prove the claim for compositions built this way. I do not recommend it:
  the domain should not absorb input-encoding error that has never been observed, and the 1e-12 discrimination holds at
  either value.

**N1, note: D134 changes no registered domain claim beyond how the face is decided.**
- *Registered claims.*
  - ADR 0027's floor value is unchanged.
  - M04 box v2's 0.036 lies 2.9 % inside it.
  - L48's "y_inert ≥ 0.035" stands at its own resolution.
  - The G11v3 and G12v3 records contain no "inert fraction below" refusal.
- *Exact path* (CLAUDE.md). The slack scales the threshold of a boolean domain test only. No state coordinate, cache key
  or written float moves, and NaN is still refused, because the `not (… >= …)` form is kept.
- *Replay.* A pre-D134 archive refused on the face would now reproduce differently. None is committed.
- *G11 generator.* `benchmarks/m02/g11_coverage_v3.py:241` `below_floor` keeps the exact comparison, so it is stricter
  than the code by the slack. Its samples stay inside the code's domain and the record is unchanged. It must take the
  slack if it is ever used as an oracle.

**N2, note: rewriting the pin is legitimate.** `tests/test_m02_variants.py:289`.
- *Why.* The old pin fixed the exact-comparison semantics that this ruled decision replaces.
- *Exact inputs.* The new inputs are exact dyadics: the only rounding is the final product, ≈ 2⁻¹⁰³. So the pin fixes
  the slack itself: 0.5·2⁻⁵² short is accepted, 6·2⁻⁵² short is refused.
- *Relative, not absolute.* `test_c1_the_slack_is_four_ulp_of_one` and the scaling tests at 10⁻³ and 10⁵
  (`tests/test_m02_wo12b_v3.py:255-277`) tell a relative slack from an absolute one. This is not a relaxed check.
- *Gap.* No test asserts that the `inert_max` ceiling stays exact.

**N3, note: D133 implements R-341 exactly.** `coupled_run.py:303-345`, `revision_run.py:1122-1126,1162-1163`.
- *The guard.*
  - Both sides are checked, and the arguments are keyword-only and required.
  - The rerun's digest is taken before `_constants_for_shape`.
  - The archived digest is `document_sha256` of the record as read (`coupling`, l.1073, not mutated).
  - When the guard fails, the digest is not replaced.
- *The negative control falsifies the defect* (`tests/test_m02_wo10_coupled.py:723`).
  - The intact bundle gives a bitwise `MATCH` with `bitwise_floats` true, so there is no false positive.
  - The tampered bundle, re-written so that it verifies, gives `MISMATCH` with the guard's own message. Without the guard
    the shape replacement would hide it.

**N4, note: D135 is consistent with R-343, but the alpha merge will conflict textually.**
- *Consistency checked.* I compared the parsed YAML:
  - L44, L45, L46 and L48 have the same ids and texts as the alpha's;
  - the harvest sha256 values are equal;
  - [1]→L44, [2]→L45, [3]→L48, [5]→L46, [6]→L44 are class E, and [0] and [4] are P, as R-343 rules.
- *Where the merge will conflict:*
  - L44 and L46 lack the alpha's spec pointers (justified: that spec is not on main);
  - the note tag is R-343 here and R-370 there, on [1], [2], [3] and [6];
  - [5] is E→L46 here and P on the alpha, and the alpha's P contradicts R-343;
  - the `HARVEST_E` line differs.
- *How to resolve it:*
  - take the alpha's evidence for L44 and L46;
  - take this branch's [5];
  - use one tag, the same in both the generator and the YAML;
  - take L47 and U15 from the alpha;
  - then run `t08_support_matrix.py --check` and compare the generator's output with the YAML.
- *Until then,* main has a gap at L47.

**N5, note on allocation and one pre-existing hazard.**
- *R-390 may collide.* `docs/V02_STATE.md` lists "R-390+" as M07's range. Start M07 at R-391.
- *Pre-existing hazard:* `StreamState.total_flow` (`thermo/__init__.py:120`) rounds differently for `float` and
  `np.float64` elements. If a path ever changes the element type, replay identity breaks. This is out of scope here and
  is recorded under R-390's "Watch for".

**Not examined:** the rest of `reproduce_bundle`; `docs/support-matrix.md` beyond its counts; the M02 manifest
generator outside the harvest; the alpha's L47 and U15. I did not run the gate. I ran one script: the adversarial
check in S1.
