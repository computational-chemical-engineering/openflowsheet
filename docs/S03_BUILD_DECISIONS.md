# S03 — build decisions (two independent column references)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`
Each work order keeps its own section; the authority is `docs/derivations/S03-spec.md`.

## WO-S03-1 (build lane `opus-engineer`, 2026-10-24; branch `wp/S03-ours`)

- DECISION: where S11 lives → one helper `cascade.property_method_refusal(unit, provider)` in S01's `models/syn001/cascade.py`, called as the first statement of both `cascade.validate` (S01's separate entry point, §9 "Where it applies") and `column.validate`, ahead of R1 and of the misuse `ValueError` checks; the same cause `unsupported(column_property_method:<provider_id>)` from both. Alternative: two copies, or a column-only check with the cascade left open. Reversible by: deleting the two calls and the helper.
- DECISION: A04's provider set → `pr_c1`, `pr_lib`, `iapws95` and also `coolprop_heos` (S07; it is in `thermo/`, implements `describe()`, and builds without CoolProp because `describe()` is computed from constants), plus the two spies; none needed external data, so none is listed as unbuildable. Each real provider is wrapped in a counting delegate that forwards its own `describe()`, so its evaluation count is asserted 0 like the spies'. Alternative: the three providers §11 names only. Reversible by: dropping the `coolprop_heos` entry in `tests/test_s03_s11_refusal.py`.
- DECISION: S11 test file → `tests/test_s03_s11_refusal.py` (A04, A05, the cascade entry point, S11-before-R1), separate from WO-S03-4's gate test `tests/test_s03_references.py`. Alternative: fold into the gate test. Reversible by: moving the tests.
