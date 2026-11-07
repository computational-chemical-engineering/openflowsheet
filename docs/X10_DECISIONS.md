# X10 inventory — build decisions

Package: X10 inventory (release 0.4; roadmap line 41; ADR 0056 row 9, R-925). Build lane. Branch `wp/X10`.
Deliverable: a measured inventory of which unit model × property basis pairs the revision path refuses today —
`scripts/x10_inventory.py`, `benchmarks/x10/inventory.json`, `docs/X10-inventory.md`, `tests/test_x10_inventory.py`.
Not a judgement of what should be built (that is X10 gaps, 0.6, on F6).

Each choice below lives in one named constant or table of `scripts/x10_inventory.py`; reversing it is an edit there
and `--record` in both environments.

## The axes (measured, not chosen)

- Models: `MODEL_BUILDERS` (`src/openflowsheet/application/revision_binding.py:1642`), 30 models: 13 `syn001.*`
  plus `syn001.column`, 9 `c1.*`, 7 `thermal.*`. Admission table `MODEL_BASES` (`:1613`); refusal hints
  `_basis_refusal` / `_UNADMITTED` (`:1716`, `:1739`); library-only `_LIBRARY_ONLY_HINTS` (`:1818`, `syn001.cascade`).
- Bases: `SELECTABLE_BASES` → `selectable_bases()` (`src/openflowsheet/models/revision_flowsheet.py:230`), 127 bases on
  5 providers: `syn001`, `pr-c1-v1`, `iapws95-v1`, `wilson-ig-v2`, and `coolprop-heos-v1` (123 fluids). Selection by
  `record_source`: `component_basis` (`:212`).
- Scanned providers outside the axis: `pr-lib-v1` (its records path selects `syn001`) and `wilson-ig-v1` (its records
  path selects `wilson-ig-v2`): library-only, measured by `component_basis`.

## Decisions

- **D-1 (choice): one CoolProp fluid stands for the provider.** `COOLPROP_FLUID = "R134a"` (TH-C2's). `MODEL_BASES`
  and `_basis_refusal` key on the provider id only, so admission is the same for all 123 fluids by construction.
  Alternative: all 123 bases (3 690 pairs). Reversible by `COOLPROP_FLUID` / `probe_bases`.
- **D-2 (choice): which revision probes a pair.** Native first: the registered revisions on that basis holding the
  model (T07's G8 corpus, M02's C1 corpus, `benchmarks/s11/{gp,thermal,flowsheets}`, T08's `ptc_r1`), smallest
  first, at most `MAX_TRIES = 3`, until one is VERIFIED. Then, where `CONSTRUCTED` registers one, a constructed
  revision (donor + stated feed state and outlet pressures). Otherwise a rebased revision: the model's smallest
  registered revision moved onto the basis (component set; flows spread evenly; routing models swapped for the
  basis' namesakes; the model under test first, so a refusal names it — a refusal naming another model would be
  `unclassified`; none is). Eight constructed probes, states stated in the table's comments: `thermal.compressor`
  on IAPWS-95 and `syn001.stream_splitter` on Wilson (no registered revision); `c1.stream_splitter` on C1 (its only
  revisions route `revision_coupled`); `thermal.turbine` on Wilson (GP-M2 registers INITIALIZATION_FAILED, S11.A81);
  five on CoolProp. Two states were corrected once each against the models' declared limits, not tuned to pass:
  the R134a ORC turbine outlet declared `vapor` (a dry expansion contradicts TH-C1's `vapor_liquid`:
  `isentropic_state_single_phase(T)`), and the Wilson turbine from 395 K to 1.25 bar (400 K → 1.2 bar first gave
  `isentropic_state_two_phase`, then a derivative-witness probe past the records' 400 K bound). Both attempts stay
  in the inventory where they are the native ones (GP-M2's failure is recorded beside the constructed success).
- **D-3 (choice): the CoolProp column in two environments.** The shared `.venv` has no `coolprop` extra (F0 D20) and
  CI installs it (`ci.yml:110`). Each CoolProp pair carries `coolprop_extra_absent` and `coolprop_extra_present`;
  `--record` re-measures the current one and keeps the other, `--check` compares the current one. The present one was
  measured with CoolProp 8.0.0 installed from `requirements-coolprop.lock` (hash-pinned) into a scratch `--target`
  directory on `PYTHONPATH`; the shared environment is unchanged. Alternative: absent only (CI's `--check` would
  then compare nothing on CoolProp, or fail).
- **D-4 (choice): coupled routes are bound, not solved.** `c1.reactor` and `c1.reactor_standin` bind on
  `revision_coupled`, which needs the external unit's experiments (the pymrm environment or a recorded backend).
  Class `bound_not_solved`. No pair took `legacy_eo`.
- **D-5 (choice): the test checks the whole matrix.** Full `--check` measured 28 s idle, 38–48 s at load ~30 on TRS2;
  a pinned 8-model subset took 23 s (the corpus load dominates), so a subset saves little. Reversible by passing
  `--pairs` in `tests/test_x10_inventory.py`.
- **D-6: classes.** `solved_verified`, `solved_not_verified`, `solve_failed`, `bound_not_solved`,
  `refused_admission` (`model_unsupported(<model>)` from R-288's pass), `refused_basis` (`basis_unavailable` /
  `basis_premises_unmet`, S11 design §4.3), `refused_other`, `error` (an untyped exception), `unclassified`. A
  pair's class is its last attempt's.
- **D-7: register readings are labelled as such.** `REASON_REFERENCES` (by the `_UNADMITTED` reason the hint
  carries) and `LIFTED` ("lifted by S10-C/S11?": R-631/R-760, S11 units design §4.5/§4.7, R-819) are read from the
  register, not measured; the table says "not stated" where the register is silent.

## Findings to carry (not decided here)

- `c1.reactor_surrogate` on its registered revision (M04's `c1-surrogate.json`): CONVERGED, UNVERIFIED,
  `derivative_witness.on_pattern: fail`. Recorded, not diagnosed.
- The register's "column on nonideal bases limited" (R-631) is lifted for Wilson today: `syn001.column` on
  `wilson-ig-v2` binds and solves VERIFIED (C-EW). It stays refused on `pr-c1-v1` and the pure fluids.
- Both pumps stay refused on Wilson (R-819): `model_unsupported`, hint "wilson-ig-v2 has no liquid volume".
