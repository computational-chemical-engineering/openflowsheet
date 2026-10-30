# E01 review (design lane, `reviewer`) — wp/E01 at de63b9a2 against `docs/derivations/E01-design.md` incl. §9

**Verdict: the core design is sound. Two must-fix items before merge (M1, M2), both small. Four should-fix items and
notes follow.** Assessments as post-solve functionals with held regimes cannot produce a false certificate through the
regime machinery itself. V7, V3 and the dormancy release close every regime path I could construct. The false-certificate
path I did find is outside the regime machinery: derived-ratio denominators (M1). The SSLW transcription, the index
chain (CE 394→500 by IDAES's own ratio, costing_base.py:66, checked against the pinned wheel), the LCA convention, the
Brightway float64 path and the packaging are faithful and well evidenced.

Read: design §0–2, §4.3, §4.6, §4.7, §4.8, §4.9, §4.10, §9.2.2, §9.2.5, §9.2.6; E01B log in full where relevant;
`program.py` (registry, build, `select`, `evaluate`, `_float_rows`); `formulation.assessment_closure`;
`verification.py` (V5 assembly, `_functional`, V7); `index.escalate`; `derived.py` headers; `report.py` status and
denominator logic; `lca/section.py`; the shipped data headers; the git history of the branch for identifiers.
**Not examined:** the seven SSLW forms line by line (I relied on the 1e-14 cross-check against the pinned IDAES), the
sizing families beyond the Underwood mean, `brightway.py` internals, the schemas, the T08 packaging tests, and the
contents of the test bodies beyond their names and the claims in the logs.

## Must fix before merge

**M1. The study path never checks derived-ratio denominators. This allows a false feasibility verdict and a false
`KKT_POINT_VERIFIED`.** Location: `assessment/cost/derived.py:78-81` (`_ratio` divides), `program.evaluate` and
`_float_rows` (only `ZeroDivisionError` raises), and `verification.py` `_assessment` (V3/V6 take `program.evaluate`). The
check that §4.7.5 requires ("a non-positive denominator is an evaluation error") runs only at planning time and in
`report.py:176-179`.
- **Scenario.** A study with the constraint `assessment:derived.ncac ≤ L`, where ncac = ccc/(1 − cc) (§4.7.5's own
  example), starting at cc < 1.
- **What happens.** An Ipopt step or the restoration phase crosses cc > 1. ncac becomes negative, so the constraint is
  "satisfied". V6 evaluates the negative value on the float path and V3 passes. V7 has no derived entries, so it also
  passes. The candidate is reported `KKT_POINT_VERIFIED` with a negative "cost". The same holds for an objective that
  names such a ratio.
- **Minimal correction.**
  - (a) On the float path, a derived output whose denominator is ≤ 0 at (x, d) raises `TwinEvaluationError`
    (`METRIC_UNDEFINED(derived.<id>)`). V3, V5 and V6 then report `not_evaluated`, and the candidate is not verified
    (the existing "not evaluable at x_sim" route).
  - (b) Every ratio gets a single-choice regime entry `derived.<id>.denominator` (kind `domain`) with row
    `den/|den(x₀)| ≥ 0`. It enters the closure like any other entry, so the optimizer is told about the pole.
  - Test: the constraint above, with a start that drives cc past 1. The candidate must not be verified.
- **Erratum §4.7.5** (append): "A ratio's denominator is a regime entry `derived.<id>.denominator` of kind `domain`
  (one choice, row `den/|den(x₀)| ≥ 0`), and on the float path a denominator ≤ 0 is the evaluation error
  `METRIC_UNDEFINED(derived.<id>)` at every state, not only at planning; a study candidate where it occurs is not
  verified (§4.10.3)." Lower priority, same rule: `.per_fu`, `lcox` and the `mass`/`economic` allocation ratios. Their
  denominators are flows, ≥ 0 under M03's bounds, except a flow that is zero at the start, which M03 leaves unbounded.

**M2 (ruling on item 5). `AssessmentProgram.build(contributors=None)` silently builds an empty program, and the report
calls it `COMPLETE`.** Location: `program.py:158-169, 478`. Registration happens only as an import side effect of
`cost/contributor.py`, `cost/derived.py` and `lca/section.py`. Neither `assessment/__init__.py` nor `report.py` imports
these modules.
- **Scenario.** A Python-API user imports only `assessment.program` and `assessment.report`. The document's cost and
  LCA sections are ignored, and the report has no outputs, no refusals and the status `COMPLETE`. This breaks the rule
  "no placeholder success paths".
- **Minimal correction.**
  - `_registered()` imports a fixed table `{"cost": "openflowsheet.assessment.cost.contributor", "lca":
    "openflowsheet.assessment.lca.section", "derived": "openflowsheet.assessment.cost.derived"}`, so the default can
    never be empty.
  - `build` refuses `ASSESSMENT_CONTRIBUTOR_MISSING(<section>)` when the document has a `cost`, `lca` or `derived`
    section and `chosen` lacks its contributor.
  - Test: run in a subprocess that imports only `assessment.program`. The build must yield P1's outputs.

## Should fix

**S1. V5 is vacuous for a small assessment objective (needs a decision).** Location: `verification.py:546-556, 645`.
- M03 scores stationarity in the absolute units of the objective "as declared scaled" (TAU_KKT = 1e-6). Assessment
  outputs in SI span roughly 1e-8 to 1e8: an impact `.rate` in kg/s for a small plant is ≤ 1e-4.
- **Scenario.** The objective `assessment:impact.<m>.rate` is written unscaled. Its scaled gradients are ~1e-6, so
  every point passes V5 and is reported `KKT_POINT_VERIFIED`. The test uses `tac/|tac(x₀)|`, so it never sees this.
- **My choice:** a readiness refusal `ASSESSMENT_OBJECTIVE_UNSCALED` when an objective naming an assessment output has
  |f(x₀)| ∉ [1e-3, 1e3], including f(x₀) = 0. The message tells the user to divide by the binding's recorded scale.
- **Rejected:** silently normalising, because it changes the declared problem. The binding's floor `max(|y|, 1)`
  depends on the unit and cannot serve as the normaliser.

**S2. Sensitivities do not flag an active regime boundary.** Location: `studies/assessment.py` (§4.10.1).
- At x* with an admissibility row at or near zero slack, dy/dp is one branch of a kinked or discontinuous cost. Two
  examples: `units:N → N+1` jumps, and the platform piece at L = 40 ft jumps by ~5 % at D = 10 ft.
- The NLP reports `regime_bounds_active`; the sensitivity reports nothing.
- **Correction:** add the rows with |slack| ≤ TAU_ACTIVE, plus each affected output's smallest slack, as
  `regime_bounds_active` with limitation `REGIME_BOUNDARY_ACTIVE(<row>)` on those outputs.
- **Erratum §4.10.1** (step 6): "Every admissibility row of the program with scaled slack ≤ τ_active at x* is listed
  under `regime_bounds_active`. Each output whose closure contains it carries limitation `REGIME_BOUNDARY_ACTIVE(<row>)`:
  the derivative is one-sided."

**S3. Closure by column overlap combined with V7 over all entries means every regime is held for every objective
(needs a decision).** Location: `formulation.py:376-415`, `verification.py` `_regime_held`.
- **Under-inclusion.** A floor item whose size columns no bound output shares falls outside the closure. The optimizer
  sees capex with slope 0 above S_min, and V7 rejects the candidate afterwards.
- **Over-restriction.** An impact objective is held to the exchanger size regimes, because their rows share Q. V7
  rejects any change of N even outside the closure.
- This is sound (no false certificate) but over-restrictive.
- **My choice:** accept for E01 and register it (R-871 below). The follow-up: each `OutputDef` declares the regime
  entries it read, and both the closure and V7 use that dependency closure.

**S4. A48 has no tripwire.** Eight `primary` ranges ship with `verified: false` (`assessment/cost/sslw-idaes-v1.json`).
They set S_min/S_max, and so the floors and the N splits.
- Today only the manifest's `not run (RC item)` line stands between them and a release.
- **Correction:** add `test_e01_a48_tripwire`. It asserts the count is 8 and that an `a48_release_check()` returns
  `fail` while the count is > 0, following the MR-12/S07 Ruling M pattern. The release specification flips the count.

## Notes

- **N1. Interval label is wrong.** Location: `cost/uncertainty.py:7, 31`. Σ min/max is the box worst case, valid for
  any correlation; it is not the "fully correlated" case. Text: `"linear, first order; each input at its own adverse
  bound (box worst case; conservative for any correlation)"`.
- **N2. Layering.** `program.py:413-418` imports `TAU_FEAS` from `studies.nlp.verification`, so the assessment core
  depends on a study. It is acceptable while `numerics/` is frozen; move it to a shared constants module when that
  opens.
- **N3. Platform pieces.** Piece 1 ends at L = 40 ft, so D in (21, 24] ft with 27 ≤ L < 40 is refused, although
  IDAES's range 2 covers it. The behaviour is conservative; record it in the item's provenance as a §9.2.2 departure.
- **N4. Dormancy.** A dormancy entry has no row, so the optimizer is blind inside the dormant regime. V7 is the only
  guard. In practice M03's regime rows pin those zero flows, so this is acceptable; A36 covers it.
- **N5. `KKT_POINT_VERIFIED` is relative to the held regime.** The status means a KKT point of the held-regime
  problem. When `regime_bounds_active` is non-empty, the report should say so in words.

## Rulings on the orchestrator's decisions (item 4)

- **ESC-B1, agree.** The float64 assembly is checked entry by entry against bw2data's own processed matrices, so the
  check is independent.
- **ESC-B3, agree.**
- **ESC-I1, agree.** An infeasible start's objective is no comparator.
- **ESC-I2, agree.** Same precedent as R-565; no S12 collision.
- **ESC-B2 packaging, agree.**
- **MR-12 tripwire for `lca`, agree.** Same pattern as S07 Ruling M.

## Item 6 (identifier incident): clean

There is no e-mail address, user-agent string or other personal identifier in any committed file at de63b9a2. There is
none in any `+`/`-` line of `git log -p 8d2ee175..de63b9a2` either; only git's author metadata appears, as on `main`.
`docs/E01A_DECISIONS.md:181` records the incident without the address. The shipped series came from FRED with user
agent `OpenFlowsheet-build`. No script under `scripts/e01_*` or `benchmarks/e01` makes a network call.

## Item 3: ruling on the disclosure gap (R-870, needs Frank's confirmation)

The residue is inherent. Every impact is linear in q with the reported coefficients A_fac·a_k. A single exchange, one
ranged θ, or several states of one study (several starts, or a sweep) let a reader solve for the q_k. Only withholding
the impacts themselves would close it, and that would defeat the feature. **My choice:**
- Accept the residue.
- Keep the θ-value withholding, which removes the only direct listing of a score.
- Label every impact computed from a forbidden table.
- Do not redact intervals or σ: that hides nothing that the value and the inventory do not already reveal.

## Register text (next free ids)

## R-868 — E01: a derived ratio's denominator is a `domain` regime entry and an evaluation error at every state
| | |
| --- | --- |
| Date | 2026-10-29 |
| Decided by | design lane (`reviewer`), E01 review M1 |
| Normative text | E01 design §4.7.5 erratum 2026-10-29 |
| Evidence | `assessment/cost/derived.py:78-81`; `report.py:176-179` (the check ran only there and at planning); `verification.py` V3/V6 via `program.evaluate` |
| Affected packages | E01 |

**Decision.** Each derived ratio adds the single-choice entry `derived.<id>.denominator` with the row `den/|den(x₀)| ≥ 0`.
On the float path, `den ≤ 0` raises `METRIC_UNDEFINED(derived.<id>)` at every state, so a study candidate where it
occurs is not verified. **Rejected:** *a check in the report only*, which leaves a negative ratio able to satisfy a
study constraint; *smoothing the denominator.* **Watch for.** A new ratio output, such as `per_fu`, `lcox` or an
allocation, without the entry.

## R-869 — E01: `AssessmentProgram.build` loads its contributors and refuses a section without one
| | |
| --- | --- |
| Date | 2026-10-29 |
| Decided by | design lane (`reviewer`), E01 review M2 (brief item 5) |
| Normative text | E01 design §4.2.2 erratum 2026-10-29 |
| Evidence | `program.py:158-169, 478`; registration only by import side effect |
| Affected packages | E01 |

**Decision.** `_registered()` imports the fixed contributor table. When a document section has no chosen contributor,
`build` returns `ASSESSMENT_CONTRIBUTOR_MISSING(<section>)`. **Rejected:** *registration by import side effect alone*,
because an empty program reports `COMPLETE`. **Watch for.** A fourth contributor added to `CONTRIBUTOR_ORDER` without
an entry in the table.

## R-870 — E01: results computed from a restricted LCA table may reveal its scores; labelled, not redacted
| | |
| --- | --- |
| Date | 2026-10-29 |
| Decided by | design lane (`reviewer`), E01 review item 3 (ESC-B3 residue); **needs Frank's confirmation** |
| Normative text | E01 design §4.8.6 erratum 2026-10-29 |
| Evidence | `docs/E01B_DECISIONS.md:166-169`; impacts are linear in q with the reported coefficients `A_fac·a_k` |
| Affected packages | E01 |

**Decision.** §4.8.6 guarantees that no table, score or θ value of a `redistribution: forbidden` table is written to
a report, bundle, fixture or evidence. Impacts are results of the user's licensed use. Together with the reported
inventory, a single exchange, an interval or several states, they can determine the scores of the activities used,
as any published LCA result can. Every impact that depends on such a table carries limitation
`LCA_RESTRICTED_DATA_DERIVED(<table_id>)`. **Rejected:** *withholding intervals and σ*, which hides nothing the value
reveals; *withholding the impacts*, which defeats the feature; *withholding the inventory*, which is the user's own
foreground. **Watch for.** A new report field that lists per-activity scores or contributions directly.

## R-871 — E01: on day one every regime of the program is held for any assessment objective
| | |
| --- | --- |
| Date | 2026-10-29 |
| Decided by | design lane (`reviewer`), E01 review S3 |
| Normative text | E01 design §4.10.2–§4.10.3 as built (closure by column overlap; V7 over every entry) |
| Evidence | `studies/nlp/formulation.py:376-415`; `verification.py` `_regime_held` |
| Affected packages | E01; the follow-up that adds dependency-declared closures |

**Decision.** Accepted for E01. It is sound, because no candidate is verified across a regime change, but
over-restrictive: an impact objective is held to the capex size regimes. **Rejected for now:** *closure and V7
restricted to the entries a bound output reads*, which needs each `OutputDef` to declare the entries it reads (the
follow-up). **Watch for.** A floor row outside the closure, which shows up as a V7 failure, not a binding row.

## New references
None. Everything relied on is cited in the repo: IDAES 2.13.0 `SSLW.py`/`costing_base.py`, IPCC AR6 WG1 Table 7.15
and AACE 18R-97.
