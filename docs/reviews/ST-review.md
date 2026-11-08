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

## Design-lane confirmations (2026-11-08)

Design lane (`specifier`), on `wp/ST` at `6e9ab4d4`; brief `docs/briefs/ST-design-confirmations.md`. Scope: the five
items the fix round left open (`docs/ST_DECISIONS.md`, §Fix round). Read only: note §4 and §12, ADR 0068, this review,
the named functions and the verifier code they mirror; two read-only scans of the 49 certificates under
`tests/fixtures/f0/v0.3.0-bundles` (degeneracy `independent_split` rows; `temperature_degenerate_unlifted(…)`
reasons). Nothing was run.

### The facts the rulings rest on

- **F1 — a products-style split's rows name the drum's inlet.** For a products-style rule `LiftedSplit.stream` is the
  inlet (`orchestrator/splits.py:368-382`), so `phase_admissibility.<U>.<S>.saturation` and
  `independent_split.<U>.<S>` have the inlet as subject; they judge the inlet's composition at the *drum's* (T, P).
  For such a split the verifier's `degeneracy` substitutes only the products' Ḣ, each in its port's phase at its own
  (T, P) (`verify/table.py:1601-1606` `owned` = the products, `:1631-1647`); the inlet goes to the second loop and is
  flashed at its own state by `checks.enthalpy_flow` unless degenerate there (`:1656-1672`). The γ–φ `degeneracy`
  substitutes nothing for a products-style split (`verify/gamma_phi_units.py:190-191`).
- **F2 — only a heater-style outlet may be undeclared.** `instance_contract` (`application/revision_binding.py:632-672`,
  R4's converse, called by every builder and by the legacy binder) refuses `vapor_liquid` on every outlet port but the
  `outlet` port of an outlet-style lifting model. So every undeclared flowing stream outside R1 is a heater-style
  split's stream, a products-style split's products are always declared, and the verifier's `unlifted` set is empty
  (`verify/table.py:1504-1505`: "unreachable after T05's S1 ruling").
- **F3 — the served certificates.** Degeneracy rows: `T05b:SC-1` `independent_split.U-VLV.S2`; `T05b:SC-3`
  `independent_split.U-VLV.S2` and `independent_split.U-PHF.S2`; `T05b:NP-1` and `T05b:SC-2`
  `independent_split.U-PHF.S1` (S1 declared `liquid`). No reason `temperature_degenerate_unlifted(…)` anywhere. All
  four runs are `revision_eo`.

**Consequence.** M1's trigger, "an `independent_split` row with subject S", reads two facts as one: a heater-style
split's *own* row (the verifier read the carried split; R1′ is right) and a products-style split's row on the drum's
inlet (the verifier did not touch the inlet's Ḣ). The brief's item 5 (an undeclared inlet with no heater-style split)
is unreachable by F2. Its reachable neighbour is the real defect: an undeclared drum inlet is, by F2, a heater outlet,
and under M1's trigger a degenerate *drum* row sends it to R1′ through the *heater's* split even where the heater's own
split was resolved and the verifier flashed the stream. No served or corpus case has it (SC-3's S2 carries both rows,
both degenerate), so correcting it moves no output. M1's no-split bullet also named the verifier's `unlifted` case,
whose signal is not an `independent_split` row but the energy rows it blocks: `unsupported`, reason
`temperature_degenerate_unlifted(<S>)` (`verify/table.py:306-320`).

### Rulings

1. **M1-1 — confirmed, for the re-keyed branch of ruling 5.** A stream that gets no number has `phases: []`,
   `phase_source: "flash"`, `flash_near_phase_boundary: false` and `flash_failed(stream=S,
   status="temperature_degenerate")`. That is the shape of R3's failed flash, which every reader already handles;
   `flash_failed` says the split "could not be computed", and its action (declare a phase) is the remedy. The flag
   marks a listed decision that may differ from the verifier's; here none is listed. Rejected: a new `phase_source`
   label (the schema allows it, but a reader could do nothing different with it), and the flag true.
2. **M1-2 — confirmed.** A mixture-`h` R1′ phase gives `n_p,tot·h` with `n_p,tot = sum(n_p)` (=
   `StreamState.total_flow`): bitwise `gamma_phi_units._phase_flow` → `forms.enthalpy_flow` at the same
   `StreamState(n_p, T_split, P_split)`, and `0.0 + H_V + H_L == H_V + H_L`. It is reachable: γ–φ emits
   `independent_split.<U>.<S>` `temperature_degenerate` for a heater-style split and reads the stored split with
   `_phase_flow` (`gamma_phi_units.py:196-204`). Rejected: `property_not_provided`, which withholds a value the
   verifier computed and used. No corpus case reaches the branch; DC-5 tests it.
3. **M1-3 — confirmed, reason corrected.** After ruling 5 a stream with a quoted degeneracy row *can* reach R3: an
   undeclared drum inlet whose heater split was resolved. Q4.R12 (b) (ii) would flag it wrongly, because that row
   judges the inlet's composition at the drum's (T, P) and the verifier flashed the inlet at its own state (F1).
   (b) (ii) stays withdrawn; (b) (i) applies to that inlet as to any R3 stream. The note's "R1′ decides every such
   stream" is amended, and `_near_boundary`'s docstring follows.
4. **S1-1 — confirmed.** `(Q + W) − (H_out − H_in)` is the residual of `energy_balance.<U>` only: the pump's
   `.work_relation` is `η W − ΔḢ^L` and reads no stream Ḣ, and an exchanger's `.hot` and `.cold` each hold the internal
   duty ST does not report as external. Ids match `^[A-Za-z0-9][A-Za-z0-9_-]*$` (`models/revision_flowsheet.py:90`),
   so `id.count(".") == 1` is exact. What G8u then leaves unchecked is under §Not established.
5. **Products-style flash feed — change: R1′ keys on the split's own row, the no-number branch on the verifier's
   `unlifted` reason.** ST reports for that feed what the verifier did: R2 or R3, like any stream. The products-style
   row stays quoted in the inlet's `checks` and neither diverts nor flags it. No degeneracy row is needed. A test case
   is (DC-4), test-local because F2 makes the state unreachable. The change, all in
   `src/openflowsheet/application/stream_table.py`:
   - `_inputs`: replace the subject set `degenerate` by two sets. `lifted` holds the heater-style splits
     (`_heater_style_splits(view)`, built only when a degeneracy row exists) whose **own** row id
     `f"independent_split.{unit_ids[split.unit]}.{split.stream}"` (built as `verify/table.py:1287` builds it, never
     parsed) is among the rows with category `independent_split`, result `not_applicable` and reason in
     `DEGENERATE_REASONS`. `unlifted` holds the streams S of `view.streams` for which some row's `reason` equals
     `f"temperature_degenerate_unlifted({S})"` exactly.
   - `_decide`: R1; R1′ iff `name in inputs.lifted`; R2; ruling 1's no-number output iff `name in inputs.unlifted`;
     R3. Both verifiers' `unlifted` sets hold undeclared streams only, so placing the branch after R2 changes nothing.
     The branch is unreachable today (F2). It is kept, as the verifier keeps its own, so that the path is never silent.
   - `_near_boundary`: docstring only (ruling 3).

   Rejected: (a) the no-split branch for the inlet (M1 as written), which withholds a number the verifier computed;
   (b) the drum's carried split for its inlet, whose phases are the products' at the drum's (T, P); (c) reviving
   (b) (ii) for the inlet (ruling 3).

### Assertions (`tests/test_st_core.py`)

Every comparison is bitwise or exact. Each expectation is the verifier helper's own expression on the same inputs in
the same order, or the same build without the perturbation; no tolerance applies.

- **DC-1** (edits `test_g16_c_a_degeneracy_row_reads_the_carried_lifted_split`): the probe row's id is S's own
  split's, `independent_split.<U>.<S>` with U the unit whose heater-style split carries S. The expectations are
  unchanged: R1′, no flash call, not flagged, phases from the stored split, the row quoted.
- **DC-2** (new, per reason in `DEGENERATE_REASONS`): the same row under another unit's id,
  `independent_split.st-probe.<S>` (the shape of a products-style row on its inlet). Expect `phase_source == "flash"`,
  at least one flash call, `phases`, `H_flow` and `flash_near_phase_boundary` equal to the unflagged build's, and the
  row quoted last in S's `checks`. With DC-1 this shows that the id's unit decides.
- **DC-3** (replaces `test_g16_c_a_degeneracy_row_without_a_split_gives_no_number` and drops its
  `_heater_style_splits` patch): append an `energy_balance` row, result `unsupported`, reason
  `temperature_degenerate_unlifted(<S>)`. Expect ruling 1's output: no flash call; `H_flow`, `S_flow`, `V_flow`, `h`
  and `vapor_fraction_molar` null with `{"code": "flash_failed", "params": {"stream": S, "status":
  "temperature_degenerate"}}`; `n` and `x` given. Control: the reason naming `<S>0` leaves S with phases and a non-null
  `H_flow`, which catches prefix or substring matching.
- **DC-4** (new, item 5): build `T05b:SC-2` with S1's declared phase removed (patch `stream_table._declared_phases`
  so that S1 maps to `None`). Expect `phase_source == "flash"`, phases `[LIQUID]`, `H_flow ==
  checks.enthalpy_flow(provider, StreamState(n_S1, T_S1, P_S1), context)` (G7's R3 comparator), the flag false, and
  `independent_split.U-PHF.S1` in S1's `checks`. Before ruling 5 the same build gave `flash_failed` and a null `H_flow`.
- **DC-5** (new, M1-2): the DC-1 build with a test-local provider that answers `("h",)` with mixture `h` only,
  `h = Σ_c x_c h_c` from `Syn001Provider`'s values for the requested phase (no `h_<c>` key). Use a stored split with
  V ≠ 0 and L ≠ 0, and assert both; set the split columns with `with_state` if the probe's are single-phase. Expect
  two phases, each with `H_p == sum(n_p) * h_p`, and `H_flow == forms.enthalpy_flow(p, StreamState(V, T, P), "VAPOR",
  ctx) + forms.enthalpy_flow(p, StreamState(L, T, P), "LIQUID", ctx)` at the split's (T, P).
- **DC-6** (corpus, in G16 (e)'s record): `unlifted` is empty on every corpus run (F2, executable); the counts of R1′,
  of declared streams carrying a products-style row, and of no-number streams are recorded beside the fix round's (4,
  2, 0). A stream that leaves R1′ is listed with its rows. It is accepted only if its own heater-style row is not a
  degeneracy row, which is the case ruling 5 corrects.

**Acceptance.** The 44 served 0.3.0 documents are byte-identical before and after (`document_sha256` per bundle, as
for S4); by F3 none can move, so if one does, stop and report it. G7 (41 bitwise), G8 (0 failures, max 1.76e-4) and
G8u (max 2.703, 146 whole-unit rows, 11 other rows) are unchanged. DC-1…DC-6 pass. There is no diff under
`verify/`, `thermo/`, `models/`, `run/` or `orchestrator/`.

**Text amended** (marked "design-lane confirmations, 2026-11-08", the replaced text quoted in a dated amendment at the
end of each): ADR 0068 D3 (R1′ and R3); note §4.2 (R1′, R3), §4.4 and §12. The guide and the MCP description are not
affected.

### Findings outside these rulings

- `docs/roadmap/foundation-rulings.md:666-676`, Q4.R12 (b) (ii), has the same imprecision: "a row for the stream … (the
  verifier could not recompute that stream by a fresh flash)". It needs a pointer to ADR 0068 as amended here. It is
  not edited here.
- Frank accepted ADR 0068 on the decision board before this amendment. The amendment moves no output, but he should see
  it.

### Not established by these rulings

- G8u compares no exchanger closure. Its two side rows hold the internal Q, and their sum equals the closure only
  algebraically. On the corpus G8u bounds nothing, because all 52 runs are judged at the projection; its regression
  power there is `test_g8u_the_e1_units_close_within_their_rows` alone. It is not a final-state closure check.
- The no-number branch sees an `unlifted` stream only through an energy row that reads it. A stream that no energy row
  reads would still be flashed; F2 rules that case out today.
- A products-style split's products are R2, summed by built-in `sum`, where the verifier's substitution uses a
  0.0-loop. They are not G7-bitwise, and no syn001 R2 stream is.
- DC-1…DC-6, the battery, F0 and the gates were not run. F1–F3 are read from the code and the 49 fixture certificates.

### Ruling 6 — ADR 0025 D2.3: `data_sha256` and `implementation_sha256` (2026-11-08)

Design lane (`specifier`), on `wp/ST` at `3ba9edc3`; brief `docs/briefs/ST-adr0025-classification.md`; build decision
8b-2 (`docs/ST_DECISIONS.md`). Read only, plus the two read-only computations quoted under "Measured".

6. **Both names are exact digests, listed in `benchmarks/st/numerical_policy_external.yaml`
   (`ST-numerical-policy-external-v1`, schemas `[stream-table.schema.json]`). 8b-2's default is accepted as
   proposed.** `state_sha256` in the same schema keeps v2's float-digest class and is not listed.

   (a) **`implementation_sha256` — exact.** Reason: the preimage is bytes. It is the provider module's source
   (`syn001.py:401`, `pr_lib.py:856`, `pr_c1.py:1028`, `iapws95.py:1041`, `wilson_ig.py:443`). wilson-ig-v2 appends
   a newline and v1's hex digest (`wilson_ig_v2.py:117`). CoolProp's is the canonical JSON of the module's and the
   fluid table's file digests and the pinned version and git-revision strings (`coolprop_heos.py:242`). No preimage
   holds a float, so ADR 0007 D1's digest row (a hash whose preimage holds an R1/R2 quantity) does not apply. The one
   thing that could move these bytes between checkouts, line endings, is pinned LF by `.gitattributes` (ADR 0057 D3,
   F0). Precedent: v2's exact `sha256`, `content_sha256` and `lock_sha256` (digests of bytes), and M05's
   `trf_module_sha256` (pinned module digests).

   (b) **`data_sha256` — exact.** Reason: no preimage holds an R1/R2 float.
   - pr-lib, pr-c1, wilson-ig and iapws95 hash the record or coefficient file's bytes (`pr_lib.py:185`,
     `pr_c1.py:163`, `wilson_ig.py:316`, `iapws95.py:154`). These are `.yaml` and `.json` files, LF-pinned.
     wilson-ig-v2 reports v1's digest unchanged.
   - CoolProp hashes the canonical JSON of three strings, the third being the *registered* fluid-data digest. A library
     whose fluid JSON hashes otherwise is refused (`coolprop_data_mismatch`, `coolprop_heos.py:468`), never re-digested.
   - SYN-001 is the case the brief asks about. Its digest is platform-stable by construction, and nothing in the
     serialisation breaks that:
     - The thirteen values are source literals (`syn001.py:46-54`), with no arithmetic and no libm. CPython converts
       a literal to binary64 with correct rounding, so each literal is one binary64 on every IEEE-754 platform.
     - `hash_named_doubles` (`canonical.py:148`) hashes `encode_doubles`, whose `np.dtype(">f8")` fixes big-endian
       whatever the host's byte order (ADR 0002, `ieee754-be-v1`). It normalises signed zero (none of the values is
       zero) and uses no text formatter; the `%.17g` form was retired at K01 for exactly this portability reason.
     - Names are not hashed. The order is the tuple in `_data_sha256` (`syn001.py:414-421`) over the fixed
       `COMPONENTS`.

   The values are R0, registered rather than solved. They are the same kind of vector that `constants_sha256` hashes
   through the same primitive (`canonical.py:178`), and ADR 0007 D1 lists `constants_sha256` in its R0 row and v2
   classes it exact. That is the precedent. `level_constants_sha256` is a float digest only because its vector
   holds a solved p⁰ (ADR 0010 D7.2, ADR 0025 D2.1); SYN-001's vector holds none.

   **The condition that comes with the class.** A class belongs to a name, not to a provider (ADR 0025 D2.3), so it
   binds every provider. A `describe()` digest may hash only bytes, strings or registered literal doubles. A provider
   whose data would carry a float computed at import or run time (a fitted, solved or libm-derived value) must hash
   its registered inputs instead; the name is never reclassified to accommodate it. All seven current providers meet
   this condition, per the lines cited above.

   **Build lane (not done here).**
   - In `scripts/t08_numerical_policy.py`, `ADDENDA` gains `ROOT / "benchmarks" / "st" /
     "numerical_policy_external.yaml"` after E01's entry. The comment above `ADDENDA` and the module docstring name
     it (ST 8b-2, ruling 6). If `wp/OPT` lands first, ST's entry goes after OPT's. OPT lists no names and the two
     schema sets are disjoint, so either order audits clean.
   - In `tests/test_m05_study_record.py:1094`, the pin becomes `["m02", "m05", "e01", "st"]`, or
     `["m02", "m05", "e01", "opt", "st"]` after OPT. It carries an "Amended on purpose (ST 8b-2, ruling 6)" comment.

   **Acceptance.** `scripts/t08_numerical_policy.py --check` exits 0 and v2 equals its regenerated bytes. Both
   `test_a1_*` tests in `tests/test_t08_adr0025.py` pass, and `test_the_m05_addendum_is_audited_after_m02s_and_
   its_partition_holds` passes with the amended pin.

   **Measured** (x86_64, this worktree, read-only).
   - `--check` was run in-process with `ADDENDA` extended in memory; no build-lane file was edited. Before: exit 1
     ("(d) unclassified sha256 names: ['data_sha256', 'implementation_sha256']"). After: exit 0, with v2 equal to
     its regenerated bytes, sha256 `6b449911f4e692051b08372fefaf0e205e9b2d746362e4fba2c4a9f6e19d707c`, the value
     OPT's `d5533e09` quotes.
   - An independent re-encoding, `hashlib.sha256(struct.pack(">13d", 8.31446261815324, 300.0, 100000.0, 100.0,
     320.0, 360.0, 400.0, 25000.0, 30000.0, 35000.0, 1e-4, 1e-4, 1e-4))`, equals `syn001._data_sha256()`:
     `44f894ff62f9d4c4d755b146cb1486f3ccc09ddba635982eff1caf8c16f95400`. This checks the encoding against a second
     implementation; it is not a pinned fixture.

   **Not established by ruling 6.**
   - Byte-identity of these digests on the second CI architecture. The argument is by construction, and the
     re-encoding ran on one machine.
   - The classification of the stream table's floats (ADR 0007 D2.3). The addendum carries no `rules`, and ADR 0068
     changes no run, bundle, certificate or replay schema (its scope); whether its floats need a table was not
     examined here.
   - Enforcement of the provider condition above. No test checks it. A future provider that broke it would surface
     only as an exact cross-architecture mismatch. Recommended default: no new test now. Add one with the first
     provider whose data is not a file or a literal table.
   - The pytest battery, the A1 tests and CI were not run.
