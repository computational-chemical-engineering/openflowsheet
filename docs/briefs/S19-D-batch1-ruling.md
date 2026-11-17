# S19 design batch 1: ruling (R-W3-G5-7 component order, R-W3-G5-8 NaN in the derivative witness)

**Authority and scope.** Design lane (`specifier`), 2026-11-17, at `db937be1` on `wp/S19`. Answers brief
`S19-D-batch1` (`.git/codehealth/briefs/`). Both questions are pre-existing; S19 stays bitwise identical, so
nothing here changes code in S19. Paths are under `src/openflowsheet/` unless written otherwise. Consistent with
M02 design note §14.2 B15, K04 spec §4.8 / §4.8.3 (Amendment WIT, ADR 0073), T06 spec §8.2 / ADR 0014 D5. No
frozen interface changes. Numbers marked *measured* come from a scratchpad probe at `db937be1`. They describe
today's defect and are not expectations. Tests Q2.A1 to Q2.A6 below are the executable form.

## Q1 (R-W3-G5-7): component order on the revision path. Finding: (a), guaranteed by construction

1. *Reach.* `split_checks.degeneracy` (and through it `_degenerate_streams`, `_split_enthalpies`,
   `_phase_enthalpy`), `_split_checks` and `_declared_port_checks` (and `_declared_phase`) have one production
   caller, `verify/table.py:revision_checks`, on its SYN branch only. γ–φ returns at `table.py:131` (its
   `degeneracy` is its own, `gamma_phi_units.py:167`, called at `:403`). Mixture returns at `:217`, PR at `:232`,
   and SYN reaches `:152`, `:234` and `:245`. `forms.form_of` maps only `"syn001"` to SYN (`verify/forms.py:55-59`).
2. *View order.* `parse_revision` sets `components = canonical_components(declared, basis)`
   (`models/revision_flowsheet.py:472-473`), which accepts a permutation and returns `basis.components`
   (`:432`). The only basis with id `syn001` is `SYN001_BASIS` (`:142`), whose components are `_COMPONENTS = ("A","B","C")` (`:93`).
3. *Provider order.* `verify_revision` builds the provider with `fresh_provider(component_basis(revision))`
   (`verify/certificate.py:419-423`). That call refuses with `basis_mismatch` unless
   `describe().components == basis.components` (`:370-374`). It also refuses a view whose basis id differs (`:453`).
4. *Verifier order.* `verify/checks.py:69` `COMPONENTS = ("A","B","C")` is a literal. Tests tie `_COMPONENTS`
   to the provider (`tests/test_t06_w1b_order.py:110`) and pin the corpus views (`tests/test_m02_wo8_verifier.py:307`).
   **No test ties `verify.checks.COMPONENTS` to either.** That is the one unexecuted link.

**Ruling.** `view.components == provider.describe().components == verify.checks.COMPONENTS` holds on every
production path into these functions, so the pairings are correct and there is no latent bug. No behaviour change.
One conformance note: B15 item 1 says every revision-path caller passes `view.components`, but
`_declared_phase` (`split_checks.py:241`), `_degenerate_streams` (`:605`) and `_split_enthalpies` (`:567`) read
the default order, and `_phase_enthalpy` pairs flows with `provider.describe().components` (`:388`). Under the
invariant this has no consequence. **Required (test only, may land in S19):** add
`tests/test_s19_syn_form_component_order.py`:
- **Q1.A1:** every `b` in `selectable_bases()` with `forms.form_of(b.provider_id) == forms.SYN` has
  `b.components == verify.checks.COMPONENTS` and `fresh_provider(b).describe().components == verify.checks.COMPONENTS`.
  Exact tuple equality. *Measured:* 127 bases, one SYN (`syn001`, `("A","B","C")`).
- **Q1.A2 (negative control, so A1 is not vacuous):** with `monkeypatch.setitem(forms._FORMS, "wilson-ig-v2",
  forms.SYN)`, the A1 predicate is false (`("CH3OH","C2H5OH","H2O")`).
**Optional hygiene (default: the next package that edits `split_checks.py`):** pass `components` into these
four sites. It is bitwise identical at SYN-001, and F0 (`scripts/corpus_identity.py --check`) proves it.

## Q2 (R-W3-G5-8): NaN in the derivative witness. Finding: (a) no on any registered path; (b) not excluded

*(a)* `derivative_witness` differences `tear.compiled = compile_problem(spec)` (`verify/certificate.py:424`), a
`CasadiCompiledProblem` (`compile/casadi_backend.py:641`), the only `EvaluationResult` producer in `src/`. Its
residual returns `invalid_trial_state` with `values=None` for any non-finite entry (`:458-476`), and its Jacobian
does the same (`:528`). So a stencil point is refused by `_stencil` (`verify/checks.py:1035`) and the witness
emits `witness_stencil_invalid_trial_state(<col>)`. No registered certificate is affected.
*(b) It cannot be excluded at the witness.* (i) The `CompiledProblem` protocol (`compiled.py:168`) carries no
finiteness contract, so the guarantee belongs to one backend. (ii) The witness's own arithmetic overflows from
finite `ok` values. *Measured* on WIT's W0 double (`tests/test_wit_witness.py`, `smooth_case("0.3","2","5","600")`):
with no injection, on 2.3646862246096134e-09 and off 0.0. NaN in on-pattern row R3 at x+h·e(S1.T) gives **pass**,
on 8.251954675131401e-12, because the column's term is silently dropped. NaN in off-pattern row R1 at the same
point gives **pass**. R3 = ±1e308 at x±h·e(S1.T) gives `fail` with value inf, which serializes to `null` in an
evaluated check and breaks K04 A30. NaN in R1 at x+h·e(S1.n.A) with components (A, B) gives **pass, not escalated**.
A NaN AD entry (R3, S1.T) in an `ok` Jacobian gives **pass**.

**Ruling: fail closed as a refusal, not as a failed value.** A non-finite term means the witness has no
difference for that column, which is what T06 §8.2 / ADR 0014 D5 already make `unsupported`. Rejected
alternative: `evaluated(value=inf)`. It breaks A30, puts inf into `witness_max_diff` (`certificate.py:1188`),
and with NaN instead of inf the outer fold (`checks.py:1245-1246`) would drop it again. The change, after S19:
1. `_discrepancies` returns `None` when any term it folds (`|D̂_ij|` off-pattern, `|Ĵ_ij − D̂_ij|` on-pattern)
   fails `math.isfinite`. Otherwise its result stays bitwise as today.
2. At both call sites (`checks.py:1327`, `:1349`), `_column_witness` maps `None` to `refusal = "non_finite"` and
   `on = off = 0.0`. `_not_a_pass` then triggers §4.8.3 escalation for class-5 component columns with x_j > 0.
   A resolved estimate replaces the refusal. An unresolved one keeps it ("a refusal included"), and
   `derivative_witness` emits both checks `unsupported` with reason **`witness_stencil_non_finite(<column id>)`**
   through its existing line. Verdict: `UNVERIFIED` with `unsupported_check` and `derivative_limitation`
   (`verify/verdict.py:233-265`). That is the same word a failed witness gets.
3. Amend K04 §4.8 in the same commit (rule 6). Add: "A differenced column whose scaled difference or comparison
   term is not finite has no difference: it is refused as `non_finite`, as a stencil point that is not `ok`."
   Then extend the first trigger of §4.8.3 (a) with "or a term of its registered difference is not finite".
**Falsifying tests** (extend `tests/test_wit_witness.py`, using its `tear` double, W0, injection keyed on exact
equality with `base[j] + s·h` computed as `_stencil` does). Every assertion is exact: string, membership, scope,
or bitwise float. No tolerance applies, because the change is control flow on a non-finite term and nothing is
approximated.
- **Q2.A1** NaN at R3 at x+h·e(S1.T), `components=()`: both checks `unsupported`, reason `witness_stencil_non_finite(S1.T)`. Fails today (pass).
- **Q2.A2** NaN at R1 at x+h·e(S1.T): same as A1. Fails today (pass).
- **Q2.A3** R3 = +1e308 / −1e308 at x±h·e(S1.T): same as A1. Fails today (`fail`, value inf).
- **Q2.A4** NaN at R1 at x+h·e(S1.n.A), `components=("A","B")`: `"S1.n.A" in escalations`, its `scaled` is not
  None, and both checks pass. Fails today (`escalations == {}`). *Measured:* `escalate_column` on this double resolves at level 3, on 5.76e-11, off 0.0.
- **Q2.A5** NaN AD entry (R3, S1.T), `components=()`: as A1. Fails today (pass).
- **Q2.A6 (no-op):** with no injection, on is bitwise 2.3646862246096134e-09 and off is 0.0. Every existing
  `test_wit_witness.py` test passes unedited, and F0 passes on `main` after the merge.

*(c) Other folds.* No other max-from-0.0 fold in `verify/` or `run/` has this exposure. `run/` has no
`max(` at all. `checks.py:1245-1246` folds `_discrepancies`' outputs, which are never NaN. They can be inf,
which `max` keeps in either order, and after the change they are never non-finite. `projection.py:242` folds
a step that is checked finite at `:147`. `surrogate.py:131` and `thermal.py:219` read final-state coordinates.
A non-finite coordinate there makes §4.1's residual raise (`checks.py:140-141`), so no certificate is issued.
`saturation.py:176/196` read bisection roots clamped inside the domain. `_level_gap` (`checks.py:1138`)
resolves through `all(<=)`, which no NaN satisfies.

## What this ruling does not establish

It does not establish that the PR, mixture or γ–φ forms pair components correctly; their modules were audited only
as far as their dispatch. It does not establish that any certificate ever carried a non-finite witness term (by (a),
none did). The Q2 tests run against a synthetic double: they are regression fixtures of the guard and validate no
certificate. The witness's tolerances (K04 §4.8) and the escalation's numerics were not re-examined.

## Open questions (each has a default, so work can proceed)

- **OQ-1** *needs the user's preference:* land Q2 inside S19, since it is bitwise identical on every registered
  certificate, or after S19? **Default: after S19 closes**, as one commit: the code, the K04 §4.8 amendment,
  Q2.A1 to Q2.A6, and F0.
- **OQ-2** *needs the user's preference:* Q1's hygiene now or at the next touch? **Default: at the next touch.**
  The Q1.A1 and Q1.A2 test lands in S19 as a test-only commit.
