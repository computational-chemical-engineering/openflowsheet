# ST review — stream table and energy summary (ADR 0068), the single reviewer pass

Reviewer: design lane (`reviewer`), 2026-11-08. Branch `wp/ST` at `6f55fc19` (main `00a508bd` + `wp/MSG` `35403f42` +
WO-1…6), against `docs/design/ST-stream-table.md` (Amendment 5), ADR 0068 (Proposed) and foundation rulings §17
Amendment 5. Brief: `docs/briefs/ST-reviewer.md`. Gate numbers are the engineer's (`docs/ST_DECISIONS.md`). I ran one
read-only script over the 44 served 0.3.0 bundles (route and row quoting, §Notes) and measured the description length.
Nothing else was run.

## Verdict

**Not merge-ready. It becomes merge-ready after M1, with S1–S4 done or explicitly deferred.**
The read-only claim holds as far as I traced it. `stream_table.py` writes nothing and keeps no state. It imports
`verify`, `models`, `thermo` and `run` read-only. The only shared-code edits are additive surface rows, catalogue
entries and the `_run_outcome` factoring. F0 PASS and an empty diff under `verify/thermo/models/run/orchestrator` and
`compiled.py` are the engineer's numbers, and nothing I read contradicts them. The absence discipline is sound: a
member is null iff its object's `absent` map has an entry (`_Record`); quotients are IEEE-safe; an absent input's
reason is copied. The quoted checks are closed honestly: G8 is left failing, as a strict xfail with a guard that pins
the failing set. There is one real defect, and it is E1: the report gives a number where the value is undetermined.

## Must fix

**M1 — E1 is a defect in ST's phase rule, not in the gate. G8 stays as written.**
`T05b:SC-1`'s S2 is a temperature-degenerate stream. At its (n, T, P), every vapour fraction is consistent, so a TP
flash cannot recover the split the solved state carries. R3 (`stream_table.py:384-399`) flashes it anyway. The flash
lists LIQUID alone, so the table reports a vapour fraction of 0 and an Ḣ 2016 W low (the latent heat of the carried
vapour) as plain numbers, with nothing in `absent`. The only signal is `flash_near_phase_boundary`. That breaks
C-2 ("derived from the verified state") and C-3 ("nothing invented"). FB-02 asked for exactly this number, the
vapour fraction. `T05b:SC-3` shows the same error at its units (valve +2016 W, PH flash −2016 W). It passes G8 only
because its envelope cancels.

D4's reason for rejecting the carried lifted split was false, and the engineer is right about that.
`verify_revision` derives the split list from the parsed revision (`verify/certificate.py:765-770`:
`lifted_splits([(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components, staged=…)`). D4's other
reason ("equals the fresh flash within `independent_split`") holds only where that check ran. Where the row is
`not_applicable` for `temperature_degenerate` or `fresh_flash_unresolved`, the verifier did not flash. It read the
carried split (`verify/table.py` `degeneracy`, route ≠ `resolved`; `_phase_enthalpy`, 1527-1552).

**Ruling: option (b), scoped to exactly where the verifier substitutes the carried split.** Add a rule R1′ between R1
and R2:

- **Trigger.** S is the `stream` of a heater-style lifted split (its instance lacks the `vapor`+`liquid` port pair,
  as in `degeneracy`). The certificate also holds an `independent_split` row with subject S, result `not_applicable`
  and a reason in `DEGENERATE_REASONS`. `staged` may be omitted, because stage keys are never flowsheet streams.
- **Phases.** VAPOR takes `n = state[split.vapor]` and LIQUID takes `n = state[split.liquid]`. Both are evaluated at
  `(state[split.temperature], state[split.pressure])`, and each is listed iff its amount is `!= 0.0`.
- **Ḣ.** Use the per-component form summed **from 0.0**, as `_phase_enthalpy` sums it, then `H_V + H_L`. This is
  bitwise the verifier's value; add these streams to G7's bitwise set.
- **Labels.** `phase_source: "carried_lifted_split"`. The schema keeps `phase_source` open, so this is additive.
  `flash_near_phase_boundary` is false, because nothing was flashed; the quoted row stays.
- **A flagged R3 stream with no such split** (the verifier's `unlifted` case) gets no flashed number. Its
  phase-derived quantities are null with `flash_failed(stream, status="temperature_degenerate")`.

Rejected: (a), exempting flagged envelopes from G8. That would loosen a gate around a wrong number. Rejected: reading
every lifted split. It would move the resolved-split streams off the verifier's arithmetic, lose their G7 bitwise
status, and buy nothing, because the flash and the split agree there within the quoted check.

R1′ amends D4, §4.2 and the scope of Q4.R12 (a): the raw flash stays wherever the verifier could flash. ADR 0068 is
still Proposed, so fold the amendment in before Frank's acceptance and register it with the rejected (a). Once R1′ is
in, G8's strict xfail turns into an XPASS: remove the mark and the guard.

## Should fix

**S1 — No gate checks unit closures beyond TH-C1, so SC-3's ±2016 W passed unseen.** Add a per-unit analogue of G8
(G8u) over the corpus. For each unit with a quoted energy row that has a value:
- where `judged_at == "final_state"` and every port stream is G7-bitwise, require `closure == value` bitwise;
- otherwise, at `final_state`, require `|closure − value| ≤ tolerance`;
- at `projection`, record the max ratio; do not bound it, because the stored state was not what was judged.

After M1, SC-1 and SC-3 must pass. Separately, attribute `SYN-001-A02-360-liquid-guess`'s ±2.73e-3 W against
1.01e-3 W. Evaluate the verifier's helper at the stored state for the shared stream. If ST equals it, the gap comes
from the projection: declare it, since `judged_at` already tells the reader. If ST does not equal it, the gap is ST's
raw flash, and that needs a ruling.

**S2 — D3-6. The no-bundle refusal says "Nothing named '<job>' exists", which is false: the job exists.** See the
ruling below.

**S3 — The description needs three edits** (§Description). The worst gap: on a flowsheet with more than 20 streams,
the default view shows 20 of them plus an `$elided` marker, with `truncated: false`. The description never mentions
markers.

**S4 — D1-3: key the route on the bundle's recorded route, not on specification roles.** `_unit_ids`
(`stream_table.py:282-302`) infers `legacy_eo` from a non-`fixed` specification. The authority is
`artifacts/solve-path.json` (`run/bundle.py:199,234`), which is what a rerun follows (R2.5). Use it when present, and
fall back to the role test only without it. Today 44/44 0.3.0 bundles agree (my run), so no output is wrong now.
When they disagree, the failure is an untyped `KeyError` at `_duty`/`_work`, or a silent `energy_balance_undefined`
for a unit without Q or W.

## Rulings

- **E1:** ruled under M1, option (b) scoped.
- **D1-1:** accepted. Amend §4.3 to "summed as the verifier's helper of that form sums it": built-in `sum` (Neumaier
  since 3.12; `requires-python >=3.13`) for `checks.enthalpy_flow`, and a 0.0-loop for `_phase_enthalpy` (R1′).
- **D1-3:** the binder-match mapping is accepted, and commit 1d3c954c stays. The route test is changed by S4.
- **D1-6, D1-7:** accepted as §5 amendments. Ports carry `absent`; phase `x` and `w` are nullable whole; the phase
  fractions are `q`. Fold them into ADR 0068 with M1.
- **D1-10 … D1-14:** accepted as written.
- **D3-6:** add a variant to `not_found` (`messages/catalogue/api_errors.yaml`) after the member variants. The
  refusal gets detail `{job_id, output: "replay_bundle", run_outcome?}`, and the entry gets `output: {type: text,
  optional: true}`. Wording: when `{has: [job_id, output]}`, summary "Job {job_id} wrote no {output!raw} output[:
  its run ended {run_outcome}].", why "The stream table is computed from a solve's replay bundle; this job has none.",
  action "Read the stream table of a solve job that wrote a replay bundle." This is additive. The file is MSG's, so
  make the edit after MSG lands, or accept a one-hunk conflict.
- **D3-7:** accepted. c_5's register column names "ADR 0068" until acceptance assigns an R-id. The link's number is
  not settled either; see §MSG merge.
- **D4-1:** neither spelling. Everywhere else in the catalogue, `gap.capability` is static prose (`<model>` is never
  substituted). Write `energy_balance_undefined`'s as "an energy balance check for this unit's model", and, for
  consistency, `property_not_provided`'s as "this property from the flowsheet's property basis".
- **D5-2:** accepted. Cutting an array at 20 items without `truncated` is projection §11.4's rule, so the CLI must
  resolve every marker; S3 tells agents the same.

## Description (`get_stream_table.md`): approved after these three edits (1287 → 1486 characters, cap 1500)

1. `per unit the duty, work and energy closure;` → `per unit the duty Q and work W (positive into the unit) and the
   closure (Q + W) - (H_out - H_in);`
2. `"depth" is 1 to 12, default 12; an array at the pointer` → `"depth" is 1 to 12, default 12; a part not shown
   (past depth, an array past 20 items, a view over 64 KiB) is a {"$elided": {"pointer"}} marker: read that pointer;
   an array at the pointer`
3. `not_found for a job without a solution (detail names the bundle's files and the run outcome)` → `not_found for an
   unknown job or one without a solution (detail gives the run outcome and any bundle files)`

The MSG precedent for recording the review is commit 8c935831: the engineer, not the reviewer, recorded the
design-lane approval in `REVIEW.json` at the new hash, citing the review. Do the same here, after the edits, citing
this file. I did not edit `REVIEW.json`, and the human review stays open. The edits move the served digest
`6705fb05…`, so c_5 is re-recorded.

## MSG merge into wp/ST (D3-1…D3-5): what breaks when MSG lands on main

1. **MSG must land by a merge commit.** `wp/ST` carries MSG's commits. A squash or rebase of MSG would make
   `git merge main` conflict on every MSG file.
2. **The chain-link numbers are order-dependent.** `wp/X02` has its own `c_4` = (`R-950`, `strip_x02`,
   `0af895a0…`). Whichever of MSG and X02 lands second becomes `c_5`, and ST becomes `c_6`. Every later digest moves.
   G12 must be re-measured at the merge tree as "`without_st` = main's served digest". `eaff4585…` and `6705fb05…`
   are not carried over.
3. **Frank's human review of `explain.md` may move D_4.** Any edit there changes D_4, and with it ST's `without_st`
   target and its served digest.
4. **Register duplicates.** D3-5 appended MSG's `R-942`/`R-943` to ST's register unrenumbered. At the merge, take
   main's renumbered entries and drop ST's copies. Re-derive `HARVEST_SIZE`, `SHIPPED_DATA` and
   `docs/support-matrix.md` (`--emit`). Re-take the `message_entry` fixtures if `catalogue.sha256` moves again.

## Notes

- **Dormant-stream rows are quoted nowhere.** §4.4 drops the `energy_balance.enthalpy.<S>` rows (`not_applicable`,
  `ZERO_FLOW`) because their subject is a stream. 5 of the 44 0.3.0 bundles have them. This is harmless, since
  `dormant: true` says the same, but §4.4 should say the rows are omitted.
- **Untyped exceptions.** An exception from `build` that is not a `StreamTableError` (a `KeyError` on a state
  variable, a provider raise, `bind_revision`) escapes `get_stream_table` untyped. Map it to `internal_error`.
- **`_quote` and a null reason.** `_quote` (`:314`) gives `None` for a row whose `reason` is null, which violates the
  schema. Use `row.get("reason") or ""`.
- **R1 with an empty carried split.** R1 with `V = L = 0.0` on a flowing stream lists no phase and reports
  `H_flow = +0.0` with no `absent` entry. This is unreachable at a verified state; refuse it as `internal_error`.
- **Paging cost.** Every page and every elision fetch recomputes the whole document (`LocalApplication
  .get_stream_table` → `from_bundle`; `assemble.load` once per marker). With more than 20 components, every `n`, `m`,
  `x` and `w` array is cut, so the CLI makes one full build per array. Measure CLI project mode on the largest corpus
  case and record it beside G14. Adding a cache needs a design decision.

## Not established by this review

I did not run the battery, F0, G1–G16 or CI, and I did not re-derive SC-1's 2016 W. I did not attribute A02-360's
2.73e-3 W (S1). I did not check that R1′ closes SC-3's unit closures; I expect it to.

I did not read: the text and CSV formatters, the schema file in full, `test_st_operation.py`, `test_st_cli.py`, the
guide page, the R4-G3 snapshots, or the contents of D3-1…D3-4's conflict resolutions. I did not compare the
certificate's provider hashes against the installation's: a bundle read with a changed provider may differ from its
rows with nothing in the document saying why.
