# S09 design probes (2026-10-26, design lane `specifier`): design-time measurements, NOT evidence

These probes measured the floors and tool behaviours that `docs/derivations/S09-spec.md` cites (§4.3, §5.2, §5.4,
§6.2). They run **no S03 case** and read nothing of this project's results: every column here (D1, T1, S1, A1, D1T)
is a non-registered state, chosen unlike RC1-RC7 so that no number can be compared with the twin or with our solver.
They are not evidence for any S09 assertion; the qualification (WO-S09-2) measures the registered cases.

Run with the BioSTEAM environment's interpreter, from this directory, e.g. `<venv>/bin/python -I floor_probe.py`.
The committed `.log` and `.json` files were reproduced byte for byte after the scripts were made lint-clean.

- `datum_probe.py` / `.log`: SYN-001's pure components with the tool's default datum (§4.2, §4.3).
- `floor_probe.py` / `.log` / `.json`: per rung and probe column, the rule 2 residuals at the registered tolerance and
  at the accuracy rerun's, the rerun movement, the spread across passing rungs, and the outer loop (§5, §6).
- `respec_probe.py` / `.log`: the initializer overwrite of a single specification, and why the re-specification uses
  the stage's attribute setter and not `specify_variables` (§5.2).

Amendment 1 (S09 §18, 2026-10-26), same rules (no S03 case, not evidence); both logs reproduced byte for byte:

- `class_probe.py` / `.log`: every identifier string a per-run check compares exactly (§4.3's thermo classes and methods,
  Q-X10's ladder, §5.4's solver signature) against the tool's objects; no column (§18.1). Run after the erratum: all
  equal. Before it, the PCF entry differed, and no class of the registered spelling existed.
- `rerun_probe.py` / `.log`: on A1 and D1T (imported from `floor_probe.py`), the registered loop at ytol = threshold / 10,
  then the accuracy rerun in the amended form (one evaluation at the final x, tolerance 1e-9) and in the original form
  (the loop again at ytol = threshold); movements in S03 §6 tolerances (§18.4).
