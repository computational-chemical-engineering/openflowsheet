# S09 brief: Amendment 1, rulings after WO-S09-2 stopped (design lane, `specifier`)

Branch `wp/S09`, worktree `.claude/worktrees/s09`, head `c2589694`. Authority: `docs/derivations/S09-spec.md` (R-740…R-747).
WO-S09-2's harness and tool-free tests are committed (`080290c8`); its log is `docs/S09_BUILD_DECISIONS.md` (read the
WO-S09-2 section). No qualification record is committed; no comparison with any of this project's values has been made.
**Do not open** `benchmarks/s03/references/results/`, `comparison.json`, `s03_reference.json` or any column result of
ours: the qualification is still blind.

## 1. The question

Rule on the four items below so that WO-S09-2 can make its recorded run with nothing to choose.

## 2. Items

1. **Registered string contradicts the tool (rule 6 stop).** §4.3 row 7 and `s09_reference.py:523` require the PCF class
   name `MockPoyntingCorrectionFactors`; thermosteam 0.54.2 spells it `MockPoyintingCorrectionFactors`
   (`equilibrium/poyinting_correction_factors.py:51`), and no class with the registered spelling exists, so rule 2c
   `property_mapping(thermo_classes)` fails on every case. Proposed: an erratum to that string in the generator and
   `s09_cases.json`; the harness needs no change. Rule it (and check the other registered class names against the tool
   the same way).
2. **19 or 20 pairs.** `s09_cases.json` registers 19 pairs; spec §3 and §12 say 20. Which is right, and the erratum.
3. **Check B2 cannot fire on R3.** R3's solver never advances the tool's iteration counter (`iter`); B3 and B4 still catch
   R3's bad states; fsolve's `nfev` is recorded. Rule whether B2 is restated for R3 (for example on `nfev`) or recorded
   as inapplicable, before the run.
4. **Thin margins under §6.6 for RC6 and RC7.** In scratch development runs (disclosed in the log; the PCF string swapped
   in memory; no reference values seen), RC6 and RC7 come out "thin margin" (0.263 and 0.197) because L2(c)'s rerun runs at
   ytol equal to rule 2d's threshold. Under §6.6 they would be reported but not classified, and RC7 is a gap case. Rule
   whether this is the intended consequence or a defect of the L2(c) rerun's registered tolerance, and fix the text
   **from first principles, not from those scratch numbers** — the qualification has not yet been run and must not be
   tuned. If you change a registered tolerance, give the derivation and say explicitly that it does not depend on any
   scratch value.

## 3. Constraints

The levels, ladder, property-mapping rule and blindness rulings of R-740…R-747 stand. Never loosen a check to pass.

## 4. Deliverable

Amendment 1 as a new section of the spec, the generator and `s09_cases.json` updated with `--check` passing, register
entries after R-747, a docs-only commit on wp/S09 (include this brief). Do not push. Report in at most 15 lines.
