# S10 brief: Amendment 6, pre-register VAL-2's aggregation before anything is computed (design lane, `specifier`)

Branch `wp/S10`, worktree `.claude/worktrees/s10`. The spec is `docs/derivations/S10-spec.md` (Amendments 1–5, §14–§18,
R-711…R-724). §9.6 registers VAL-2 (l.936): isothermal binaries of Kurihara, Minoura, Takeda and Kojima, *J. Chem.
Eng. Data* 40 (1995) 679–684; computed: bubble P and y at the measured x and T; band AAD(ΔP/P) ≤ 3 %, AAD(y_i) ≤
0.015. §17 A4-3/A4-4 say what happens when the data arrive (the `uncertainty` string's VAL-2 sentence, a lineage step, a
`verdict`, an updated manifest) and §18 A5-4 names the work order WO-S10-8.

## 1. The question

§9.6 does not say how VAL-2's AAD is aggregated, and the data are now in hand. Fix it **now, before any model value is
computed on these data**, so that WO-S10-8 has nothing to choose and the verdict has nothing to interpret.

## 2. Facts

- **The data:** two binaries in two tables on journal p. 680. Table 2: methanol (1) + water (2); Table 3: ethanol (1)
  + water (2); each at 323.15, 328.15 and 333.15 K. Columns as printed: P/kPa (3 decimals), x1, y1 (4 decimals), plus
  γ columns not transcribed. No pure-component rows.
- **Rows:** methanol+water 14 / 20 / 18 (323.15 / 328.15 / 333.15 K); ethanol+water 37 / 34 / 36. 159 in all.
- **Double entry done (§9.4's rule):** two independent agents, one from the 300 dpi page image only (no text layer).
  The two files are byte-identical (SHA-256 `e1290279…98090bb`). Format: `system,table,row,T_K,P_kPa,x1,y1`, values
  exactly as printed, `table` = 2 or 3, `row` counted within each (system, T) block in print order (left, middle,
  right column groups). Files: `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/val2-{A,B}/kurihara1995_binaries.csv`.
  Notes from the image-only entry: ethanol+water P is not monotone near the azeotrope (x1 ≈ 0.9), as printed.
- The paper's own pressure measurement: the still's pressure is set via the bubble point of water and water's vapour
  pressure data (the paper's experimental section). Its stated accuracies are in the paper; read them from
  `/home/frankp/s10-papers/7a8a5e74-je00019a033.pdf` (copyrighted: never commit it, never quote prose; numbers only).
- The model: `wilson-ig-v1` (constant Λ fitted at 101.3 kPa from the 1993 isobaric data, ideal-gas vapour, the
  project's Antoine fits, valid range 290–410 K). 323–333 K lies inside that range.
- VAL-1's procedure and report are the pattern: `scripts/s10_validation.py`, `benchmarks/s10/validation/`,
  `docs/s10-validation-report.md`, and the VAL-1 verdict in `docs/reviews/S10-validation-verdicts.md` ("within" read
  as the maximum where a band says "within").

## 3. What to rule

1. **Aggregation of each band:** pooled over all 159 points, per binary, or per (binary, T) block, and whether every
   unit must pass or the pooled value decides. Say which y enters "AAD(y_i)" for a binary (y1; y2 = 1 − y1 gives the
   same absolute deviation).
2. **ΔP/P's denominator:** measured or computed P.
3. **The bubble-point computation:** the provider call at (T, x) that returns P and y, and the convergence/refusal
   handling. A point the method refuses or fails on counts how?
4. **Which points enter:** all 159, or a stated exclusion rule decided now (for example none).
5. **The committed files:** paths and names for the transcription and the two entries (following
   `benchmarks/s10/vle/kurihara1993_binaries{,.A,.B}.csv`), and the rights row (as RC-05, unresolved; repository only).
6. **The test and report:** what `test_a51_…` and `test_a53_…` (`tests/test_s10_validation.py` l.91, l.140, now
   skipped) assert, and the VAL-2 verdict strings in the report.
7. **WO-S10-8's steps,** in the form of WO-S10-7a in §18: the transcription commit, the computation, the tests, the
   `uncertainty` sentence's exact template (A4-3) with the lineage step, the `verdict` pass, the manifest. Leave the
   result-dependent sentence as a template with slots.

## 4. Constraints

- **Compute nothing on the 1995 data.** No model value, no AAD, no glance. The point of this amendment is that it is
  fixed blind. You may read the paper for its stated accuracies and table layout.
- The bands do not move (R-708). Validation is not verification.

## 5. Deliverable

Amendment 6 as §19 of the spec, with register entries after R-724. A docs-only commit on wp/S10 naming S10 (stage named
paths, include this brief). Do not push and do not set `reviewed`. Report in at most 15 lines.
