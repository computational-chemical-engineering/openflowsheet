# S10 brief: final `reviewer` pass (WO-S10-3 to WO-S10-6) and batched rulings

Branch `wp/S10`, worktree `.claude/worktrees/s10`, head at writing ≥ `0ff14c78`. WO-S10-1 and WO-S10-2 were reviewed in
`docs/reviews/S10-review-wo1-wo2.md`. This pass covers the rest.

## 1. What was built against

`docs/derivations/S10-spec.md` with:
- Amendment 1 (§14, R-711);
- Amendment 2 (§15, R-712…R-715);
- Amendment 3 (§16, R-716…R-719).

ADR 0047 is Proposed.

## 2. What is under review

| Work order | Content |
| --- | --- |
| WO-S10-3 | `docs/derivations/scripts/s10_saturation_points.py`, `s10_records.py` (fit), `benchmarks/s10/records.yaml`, `fit-report.json`, `saturation-points.json`, `nasa7-low.json`, `docs/s10-rights-check.md`, and the generator's real section (`s10_reference.py --real`, `benchmarks/s10/reference_values_real.yaml`). Tests: `tests/test_s10_records.py` |
| WO-S10-4/4b | `spikes/references/s10_qualify_idaes.py`, `scripts/s10_idaes_comparison.py`, `benchmarks/s10/idaes/` |
| WO-S10-5/5b | `spikes/references/s10_qualify_dwsim.py`, `scripts/s10_dwsim_comparison.py`, `benchmarks/s10/dwsim/` |
| WO-S10-6 | `scripts/s10_validation.py`, `benchmarks/s10/validation/`, `docs/s10-validation-report.md` |

The data are double-entered and image-checked: `benchmarks/s10/vle/kurihara1993_binaries.csv` (49 rows) and
`kurihara1993_ternary.csv` (38 rows). The record of that check is in `docs/S10_DECISIONS.md`.

## 3. Results so far

- All S10 tests: 237 passed, 2 skipped. The skips are VAL-2, whose data have not been supplied.
- Verdicts:
  - `docs/reviews/S10-reference-verdicts.md`: A40–A45 met. IDAES gives 13 AGREE (worst 0.00985 of tolerance) and
    I3 NOT_COMPARABLE. DWSIM's two-phase states are NOT_COMPARABLE at its flash floor; its γ readback is 4.9e-16.
  - `docs/reviews/S10-validation-verdicts.md`: VAL-1 within band; VAL-2 insufficient evidence; VAL-3 misses on
    methanol Δh, +5.72 % against 5 %, which is the ideal-gas vapour. "Within" is ruled as the maximum.

## 4. Rulings wanted, batched

1. **The I11 errata** carried by the verdict (ESC-8). The statements in §16 A3-2, A3-8, A3-10 and R-717 say I11 is
   NOT_COMPARABLE, but it converges and AGREEs. Write the errata text.
2. **The records' `uncertainty` string** (§9.5). It still reads "not yet validated". Editing it changes the records
   hash that six records cite. Rule how the validation status is recorded: edit and re-emit with the hash cascade, or
   record the status elsewhere. Give the exact text.
3. **Can S10 close as `tested` with VAL-2 pending?** The answer must be consistent with CLAUDE.md, which says to
   distinguish numerical verification from empirical validation. The 1995 paper may arrive later. If S10 can close,
   say what the manifest says about VAL-2.
4. **Build decisions not yet reviewed:**
   - WO-S10-3: B-19…B-34;
   - WO-S10-4: B-35…B-46;
   - WO-S10-5: B-50…B-54 (B-50 ratified in §16);
   - WO-S10-5b: B-60…B-62;
   - WO-S10-6: B-70…B-74.
   The verdict has already ruled B-70, B-73 and B-62.
5. **The general review:**
   - the fit code against §15 A2-1;
   - the generator's real section;
   - whether the harnesses' blindness is enforced;
   - whether each test verifies what it claims;
   - whether the rights table matches C12's standard;
   - whether any shipped path (`PACKAGED`) could pick up S10 data. It must not before Frank's Q-F3 decision.

## 5. Where I am least sure

- The second local minimum for methanol + ethanol (§15 A2-1): is the single-start procedure robust for future data,
  or does it only work for this data set?
- The DWSIM settings set before its run (B-50), even though they were ratified.

## 6. Not worth your time

Re-deriving the tolerances, which the specifier owns. The transcriptions, which were checked twice and against the
image.

## 7. Deliverable

- `docs/reviews/S10-review-final.md`, with findings by severity and a ruling on each §4 item, giving exact text where a
  spec, test or record changes.
- Spec errata as §17 (Amendment 4) if needed, with register entries after R-719.
- A docs-only commit on wp/S10. Do not push and do not set `reviewed`. Report in at most 25 lines.
