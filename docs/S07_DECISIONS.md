# S07 build decisions

Build-lane choices the specification left to the engineer. Each is isolated and revertible.

## WO-S07-1a (spec §17.6)

- **B-1 (step 6): the CoolProp helper is a module beside `conftest.py`, `tests/s07_coolprop_support.py`
  (`require_coolprop()`),** following `tests/m06_browser_support.py`, not a `conftest.py` function.
  Rejected: `conftest.py`, which every test imports and which already carries unrelated helpers.
  Reversible by moving the function and its two constants.
- **B-2 (A43): the CI flag is set in the `Run checks` step's `env:` map,** not in the run script, so
  the YAML assertion reads it literally (§17.5 A43 allows step or job).
