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
