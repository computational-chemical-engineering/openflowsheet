# WIT build decisions (K04 §4.8.1–§4.8.9, ADR 0073 Proposed)

Build lane, branch `wp/WIT`. Each entry: the question, the choice, the rejected alternative, how to reverse it.
The normative text is the spec; nothing here changes a tolerance, a check meaning or a frozen field.

## D-1 — the A2 limitation's `reason`

- **Question.** Class 2 (a dormant Wilson liquid side) is listed in `derivative_witness_partial` "in R-281's record
  and R-345's form" (ADR 0073 D3), and "no field, limitation kind, reason or policy entry is added" (D5). R-281's
  record carries `reason: "pr_c1_zero_flow_columns"`.
- **Choice.** The literal reading: the same record, `{"columns": [...], "reason": "pr_c1_zero_flow_columns"}`, on
  a Wilson certificate too (`certificate.py` `_issue`, unchanged). Carried by the first `WIT:` commit (no line
  changed; `witness_skipped_columns` lists classes 1 and 2).
- **Rejected.** A new reason string (for example `gamma_phi_dormant_liquid_columns`): it contradicts D5 and would
  need an ADR amendment. It reads better on a Wilson certificate. **For the reviewer.**
- **Reverse by.** One conditional in `_issue` choosing the reason by basis, plus an ADR 0073 amendment.

## D-2 — observing the escalation without a record

- **Question.** WIT.A04/A07–A09 need k*, the admissible levels and the escalated set; §4.8.3 (g) forbids a record.
- **Choice.** `escalate_column` and its result `Escalation` (admissible levels, e_k, k*, D̂_k*) are public;
  `derivative_witness(..., escalations=dict)` fills the dict when given (default `None`, never by a certificate
  caller). Tests observe a certificate's witness through `tests/wit_support.py::spy` (a monkeypatch of
  `checks.derivative_witness` and `certificate.witness_classes`).
- **Rejected.** A test-only reimplementation of the trigger (would test itself, not the witness).
- **Reverse by.** Dropping the keyword; nothing in a certificate reads it.

## D-3 — class 1 computed inside `witness_classes`

- **Question.** R-281's set was computed in `verify_revision` as `view.streams × view.components` with value 0.0;
  §4.8.2 / WIT.A12 want one function returning one class per column.
- **Choice.** `witness_classes(columns, state, components, basis=, streams=, splits=)` computes all five classes over
  the certificate's variable columns; `verify_revision` passes classes 1–2 as `unstenciled`, 3–4 as `one_sided`.
  The class-1 set equals the old set on every variable column, which is all the witness and
  `witness_skipped_columns` read (F0 PASS confirms on the corpus). The old code raised `KeyError` for a stream flow
  missing from `x_final`; the new one does not read it.
- **Reverse by.** Restoring the inline set in `verify_revision` (one hunk).

## D-4 — NaN in the escalation

- **Choice.** The trigger compares the column's maxima with `>` (a NaN row is dropped by `max`, as the registered
  path has always done); resolution requires `|D̂_k − D̂_k−1| ≤ ε_res` on *every* row (`all(...)`), so a NaN row
  never resolves a column. Not a spec question; recorded because it is a choice the spec does not state.

## E-1 — ESCALATED: an unlisted move (G7(c)'s TWO_PHASE window edge), stopped per §4.8.6 rule 6

- **Fact.** `tests/test_m02_wo8_g7.py::test_g7c_the_near_dew_window_edges_as_the_manifest_states_them[0.00053-UNVERIFIED]`
  fails: F4 × (1 + 5.3e-4) is now `VERIFIED`. The edge it pins (δ = 5.48e-4, "where the liquid NH3 flow reaches one
  witness step") was the witness's; the escalation now resolves `S3.n.NH3` there, so the TWO_PHASE edge is the
  regularity screen's absolute limit. Measured verdicts (TRS2): δ = 1e-4, 2e-4, 2.4e-4 UNVERIFIED (ILL_CONDITIONED
  absolute; witness pass); δ = 2.6e-4, 3e-4, 4e-4, 5.3e-4, 5.7e-4 VERIFIED (NO_RANK_LOSS_DETECTED; limitation
  `derivative_witness_partial` only, R-281's zero flows). Not in F0 (F0 PASS).
- **Also stale.** `c1.tp_flash`'s manifest text (`src/openflowsheet/models/c1/flash.py:343-349`, R-282 as amended)
  states the TWO_PHASE edge at L/n_tot = 3.4e-5 (δ = 5.5e-4) set by the witness step; the docstring of
  `test_g7c_as_amended_by_r282` and `test_g7c_the_manifest_states_the_window_at_the_measured_state` repeat it.
- **Not done.** Neither the test nor the manifest text is amended (spec §4.8.6: "If any other test's expectation
  changes at implementation, this document is wrong. Stop and report it").
- **Would need.** A design-lane ruling adding this as M-6 to §4.8.6 (edge now ≈ 2.5e-4 on both sides, set by
  ‖J⁻¹‖₁ ≤ τ_min/(n ε)); then the parametrisation (5.3e-4 → a δ below 2.4e-4) and the manifest sentence change
  in one isolated commit, and whether the manifest text change moves any identity (check F0 M9 / manifest hashes).

## D-5 — F-1 (review must-fix): the flat rule in `escalate_column`

- **Spec.** §4.8.3 (c) gains the review's sentence (a flat level cannot be `k*` or `k* − 1` when a coarser stencil
  of that row was not flat); derivation item 2 states the exception; WIT.A15 (W4) added; A01 49 → 56 claims.
- **Choices the sentence leaves to the build lane.** (i) "Coarser stencil" = a *complete* one: the registered pair
  when both points were evaluated (passed as `escalate_column(..., registered=points)`), or an earlier admissible
  level; a refused or partial stencil does not count. (ii) Flat = the values compare equal with `==` (−0.0 equals
  0.0; a NaN is never equal, so a NaN row is never flat — it already cannot resolve, D-4). (iii) `e_k` is still
  recorded for a barred level (diagnostic); `Escalation.barred[k]` exposes the rule to tests.
- **Generator.** `wit_reference.py` mirrors the rule in its 50-digit `escalation()` (claim per W1/W2 column: no
  level barred, so A02/A04's `k*` are unchanged) and adds W4 in binary64: without the rule 7 of 9 configurations
  resolve with `D̂(R4′) = 0.0` (k* = 3–5), with it none resolves.
- **Failing first.** A15 before the fix: 7 failed, 2 passed (the two that never resolved); after: 9 passed.
- **Re-measured under the rule (TRS2).** A08 unchanged: k* = (NH3 4, N2 5, Ar 3, CH4 3, H2 2, S2.NH3 1), escalated
  ≤ 4.276e-10, on-pattern 3.900405e-08, VERIFIED. A09 unchanged: k* = 5, e_5 = 8.9e-16, on 4.98e-11, UNVERIFIED
  (absolute). E-1 window unchanged: δ = 1e-4, 2e-4, 2.4e-4 UNVERIFIED; 2.6e-4, 3e-4, 4e-4, 5.3e-4, 5.7e-4 VERIFIED;
  no level barred anywhere.
- **Reverse by.** Reverting the F-1 commit.

## D-6 — F-2: a `ZERO_FLOW` split has no class 2 or 4

- **Choice.** `witness_classes` skips a split whose `feed` tuple is all exactly 0.0 in `state` (`-0.0` counts as
  0.0); its sides fall to class 5, where `x_j = 0` is not escalated, so §4.8.8's "stays unsupported" holds. A feed
  column absent from `state` is not taken as 0.0 (the split is then classified as before; every measured feed is a
  variable, e.g. G7's `S1.n.<c>`). §4.8.2's dormant definition gains the matching sentence.
- **Tests.** `test_a12_a_zero_flow_split_falls_to_class_5_on_a_gamma_phi_basis` (0.0 and −0.0; fails before the
  fix, 2 of 2) and the counter-case with a positive feed (classes 2 and 4 kept). WIT system tests 6 passed.
- **Rejected.** Rewording §4.8.8 to accept the case unmeasured (the review's alternative).
- **Reverse by.** Reverting the F-2 commit.

## D-7 — F-3: tests for §4.8.3 (d)'s unresolved refusal and (f)'s order rule

- `test_d_an_escalated_registered_refusal_that_never_resolves_keeps_its_refusal`: W2's residual at n_A = 1e-9,
  all nine levels inadmissible; both checks `unsupported`, `witness_stencil_invalid_trial_state(S1.n.A)`.
- `test_f_a_resolved_refusal_does_not_end_the_witness_a_later_final_refusal_does`: W2 with `S1.T`'s forward point
  refused; `S1.n.A` resolves (k* = 6) and both checks name `S1.T`. Tests only; no code change.
