# S19 review R-W4-RC-N6: `RegionCall` (wp/S19-rc) and the WO-N6 retarget (wp/S19-n6)

Reviewer, 2026-11-20. Read: the three rc commits (ac98d5d8, 859532c2, 21315b02), f8e10957, the call sites, every
`solve_region`/`_solve_region` fake, the gate's literal counter (cce-code-health 34a30bf `gate.py:246-259, 520-540`).
Not rerun: any gate or test. Job 518 (rc, interface mode) is still queued, so lane 1's verdict is conditional on it.

## Lane 1, wp/S19-rc: merge once job 518 passes (fixes 1-3 are docs, outside the lane or in a docs pass)

- (1) Call sites: all 19 `solve_region(` openings in src, tests, scripts and benchmarks now open `RegionCall(`; the
  whitespace-blind diff of every caller is only the wrapping line and one re-wrapped conditional
  (test_t04_ptc_region.py:165-169, same parentheses). Keywords, values and order are unchanged. `RegionCall`'s 21 fields
  carry exactly solve_region's old defaults (`trace=None` included), `kw_only=True`, frozen. No exception moves across
  the `try`: construction raised nothing `_KernelRefusedError` before or after.
- (2) Fakes: the five `solve_region` fakes (test_s02_column_wo2b.py:403, test_s08_reentry.py:302, test_s08_blocks.py:130,
  test_s06_column_wo1.py:368, test_s01_cascade_wo1.py:259) take `*args, **kwargs`, read nothing and raise; the two
  `_solve_region` spies (test_t08_w4_warm_starts.py:599, 648) read `call.warm_start`/`call.state` as before, and
  `solve_region` still reaches `_solve_region` through the module global. "No adapted" is right.
- (3) test_wo4 tests what it tested: the public default of `item0_opening_source` and its keyword-only kind, now on the
  one object that holds it (before, solve_region and `_RegionCall` each held a copy and only one was pinned).
- (4) `literals_removed` is exact: the gate counts str/bytes constants minus docstrings and minus the plan files'
  `__all__` strings, so the dropped keyword's `Literal[...]` and default (`"initializer"` x2, `"eo_recovery_start"` x1)
  are the whole set; `False`/`None` defaults are not counted.
- (5) Docstrings accurate; `solve_region`'s is not stale.

Fixes: 1. (should fix, orchestrator) ADR 0076 has no entry for this public change (`RegionCall` added,
`solve_region` changed); line 75 says the ADR lists every one. Add an addendum like I-20's, citing the card.
2. (docs pass) Stale call forms in test module docstrings: test_t06_f4_edge3.py:5, t05_w12_support.py:5-6,
test_t05_w12_injections.py:7. 3. (note) RegionCall's docstring now holds the solve's outcome rules (PTC, warm start,
recovery); solve_region's own docstring no longer names its outcomes. Acceptable as one place; I would move those three
paragraphs back to solve_region and keep field meanings on RegionCall. 4. (note, pre-existing) test_s01_cascade_wo1.py:262
patches `region.solve_region`, which no caller reads through the module (executor and cascade_solve bind the name): it
intercepted nothing before or after; patch_noop cannot see it. Retarget to `cascade_solve` in a later retarget commit.

## Lane 2, wp/S19-n6: merge

The patch is real: `list_models` reads `inspection_service.MODEL_BUILDERS` (:94), the registry factory resolves
`getattr(model_builders, "MODEL_BUILDERS")` at call time with no cache (registry/__init__.py:640-650), the binder reads
its global at :706. Complete over the table: the only other binding, replacement.py:67, is a membership test. The old
assertion is kept (the refusing tables keep the keys; the expectation is the test's own unpatched import). Note: a path
around the table (`c1_reactor_surrogate_of`, revision_binding.py:708) is not guarded; unreachable from list_models today.

`revision_binding.MODEL_BUILDERS`: not a shim under ADR 0076. Nothing is removed or renamed; the binder imports the
name for its own call site (:706), and WO-N4 already moved the registry factory to `model_builders`, so I-19's reason
for listing it ("the legacy table's factory") is gone. What remains is W27's duck-typed binder protocol
(`SELECTABLE_BASES`, `MODEL_BASES`, `MODEL_BUILDERS`, `LIST_MODELS`, `basis_provider`: snapshot.py:285-293, :153, :235;
fake binders set it, test_m06_w27_coverage.py:554, 686, 790), which also reads historical binders. Keep it as a protocol
attribute; the design lane should strike it from I-19's re-export list with that reason and state the protocol in
`reading_for`'s docstring, since the tool still counts the plain import as a re-export (ADR Q-F1).
