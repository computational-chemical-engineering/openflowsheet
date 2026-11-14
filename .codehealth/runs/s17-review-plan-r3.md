# S17 plan review R3 (reviewer, 2026-11-14): approve-with-changes
Checks agree: closures 73/31 at e3a36046; arch 24->22 nodes, 83->79 edges (R3 alone); every patch target's reader
stays in the binder; AST scan of tests/, scripts/, benchmarks/, examples/, docs-site/: no reference to the 107 moved
names. Changes:
1. Seed model_builders with `_c1_reactor_surrogate_of` (revision_binding.py:1422-1447): the surrogate's real builder;
   the binder's `partial(...)` at :2159 imports it from model_builders. Re-run split_closure.py, recount.
2. model_signatures directly after thermal_binding in the layer order (not after jobs.model) and in
   engine-not-persistence `from`; re-measure arch (same counts expected).
3. Module docstrings for both new files (model_signatures holds Builder and Configuration so plugins never import
   model_builders; model_builders imports model_signatures at top, plugins lazily).
4. Section headers copied into model_signatures mislabel (:514 "builder helpers", :689, :875, :1208): reword there.
Defaults agreed (no thermal-only re-exports; model_builders in engine-not-persistence). Docstring follow-up recorded
as a decision and landed before R4: `_syn001_column` (:1121-1122) and `_thermal_builder` (:1558) become false (lazy
import justified by a cycle that no longer exists); also refusals.yaml:1378 and models/revision_flowsheet.py:19.
Risks: test_t07_w5a_inspection.py:133 setattr goes dead once D19 points a reader at model_builders (switch to
setitem then); run test_s11_thermal_binding and test_s11_column_unit in isolation once; the two comment pointers above.
