# Brief — T08 review: kinetic CSTR, PTC-R1 registration and harness, warm starts, record fixes

**To:** `reviewer` (design lane). **From:** build lane, 2026-09-29. **Branch:** `wp/T08` at `f9a7f66`
(the pre-build base is `16e56af`). **Deliverable:** `docs/reviews/T08-review.md`, findings ranked M (must fix
before W5 / merge) / S (should) / N (note), each with file:line, the failure scenario and the smallest fix.
Write no production code; do not commit.

**Timing.** This review runs **before** the PTC-R1 comparison (W5) exists — deliberately, so the harness and
the arms are judged before any result (preregistration, spec §A4.6). Nothing has run on the PTC-R1 flowsheet
from any registered start.

**Budget.** Frank is near his weekly usage limit; this is the one review pass for this work. Concentrate on §3.

## 1. Built against

- `docs/derivations/T08-build-first-spec.md` Parts A and B **with Amendment 1** (from line ≈ 578; §Am1.C rows
  replace §C.1's rows of the same id). ADR 0023 (+ Amendment 1) kinetic CSTR / PTC-R1; ADR 0024 warm starts.
- `docs/derivations/T08-release-spec.md` §6 (record defects D1–D3, identity substitution) and §9 (T08.A10–A16).
- Engineer decisions with reasons: `docs/T08_DECISIONS.md` (entries of 2026-09-29: W2, W4, Phase 1, Amendment 1).
- Code diff: `git diff 16e56af..f9a7f66 -- src benchmarks` (24 files, +3040/−516). Main pieces:
  `models/syn001/kinetic_cstr.py` (new, 703 lines), `models/rows.py`, `orchestrator/mass.py` (D2: rule takes the
  declared phase), `verify/table.py` (D3/D4: cooling relation, reacting/external-duty membership),
  `orchestrator/warm_start.py` (new), `orchestrator/executor.py`, `orchestrator/region.py`,
  `application/{store,revision_run,policies,revision_binding}.py`, `application/jobs/runner.py`,
  `run/identity.py` (the `r0_projection` branch), `verify/failure.py` (D2/D3 bundles, initializer bundle plan),
  `application/validation.py` (D1), `benchmarks/t08/ptc_r1/{revision.json,case.json,compare.py}`,
  `benchmarks/t07/v17/{reference,scorer}.py`.

## 2. What was run, with numbers

- `./scripts/check.sh` green at `f9a7f66`: 6477 passed.
- Identity (`measure_identity`): K05 whole `3ed2911b…`, minus-`t07` `9a7b4e6d…`, `t07` `11bcb148…`, structural
  `915c97e8…`, T02 floats `9a8a5baf…`, keys `t02`…`t06` unchanged; `requirements.lock` unchanged.
- CSTR (B10–B19): rows at the roots ≤ 1.78e-15 mol/s, 1.82e-12 W; Jacobian vs YAML 3.65e-15; FD 2.51e-10; `M`
  2.2e-16; pencil 2.4e-14; PTC/Newton single steps at the off-grid states vs YAML 1.06e-13; MID determinant sign
  flips at 4.15865 s.
- Warm starts (target recycle 0.95): cold 5 steps / 201 property calls, warm 3 / 112; states agree 8.0e-15;
  B40–B49 pass; replay MATCH with 0 store lookups during rerun.
- D3 cause: property calls were metered into the plan trace, never into `RegionResult.counters` (NET-02 0 → 202;
  A02-352 0 → 2104). D2: plan/policy ids now in bundles and certificates. `t07` key unmoved; bundle-level diffs
  confined to the named fields (`tests/test_t08_w1_identity_substitution.py`).
- `C_reg` `9f5f29d` → `C_A1` `30243f9` → `C_case` `c337fa1`; B20 ancestry test passes; G16-b 40/40 against
  `t07_reference_t08.json`.

## 3. Look hardest here

1. **The PTC-R1 harness and arms before they run** (`benchmarks/t08/ptc_r1/compare.py`, `case.json`, the two
   arm policies in `application/policies.py`): does it make exactly §A4.5's calls; does it classify per §A4.3/§A4.4
   as amended; can any run end untyped or be mis-classed; is the C trace handled per §Am1.1/B21/B28.
2. **Three open points the build lane found — give a recommended ruling for each** (the design lane will
   amend the spec if needed; after `C_case` a change to the arms means a re-registration, so say whether it does):
   - **P-budget.** §A4.1 (spec :201) and YAML `max_property_calls: null` say "no property budget", but the arms
     are defined as `T06-revision-v2` with only `eo_core`/`eo_recovery` changed (§A4.5, R-123), and that policy
     carries `max_property_calls = 10000`, which `execute_plan` enforces. Registered as defined (with the cap).
     Measured: 2 property calls per residual, 4 per Jacobian at LOW; one PTC attempt ≤ ≈ 5200. Which reading
     governs, and is the registration valid as committed?
   - **P-trace.** YAML `criterion.trace_component` says the C flows end "within 1e-12 mol/s" of 2⁻¹⁰; §Am1.C B21
     says 1e-10. The harness records the raw deviation.
   - **P-STR04.** D1's instance-id rule (Frank: extend to STR-04/STR-05). STR-04's FAIL messages name row ids
     (`U-FLASH:FLASH-P:inlet`) and binder parameter ids (`U-FLASH.T_spec`, `application/binding.py:750`); D1 gives
     no rule for rows/parameters. Recommend one.
3. **The CSTR residual and derivatives** (`kinetic_cstr.py`, `rows.py`): same function at the same state for
   residual and Jacobian; zero-flow and domain behaviour; the realization of PTC-R1 (§A1.5 + Am1.1).
4. **`mass.py` D2** (the rule now takes the declared phase; §A3.1 said nothing else changes): is the mapping for
   the existing flash/heater family byte-unchanged, and is the CSTR's `M` right (route a, §A3)?
5. **Verifier additions** (`verify/table.py`, D3/D4): the cooling relation under `energy_balance`, the CSTR in
   `EXTERNAL_DUTY_MODELS` / `REACTING_MODELS` with ξ = the recomputed rate. Can the verifier now pass something
   wrong, or share anything with the solver (R-016)?
6. **Warm starts** (`warm_start.py`, `executor.py`, `region.py`, `store.py`, `revision_run.py`, `identity.py`):
   can a candidate change the problem (spec, bound, tolerance, check policy); is every rejection typed and the
   run never failed by it; does a rerun use only the bundle; is the `r0_projection` branch inert for every
   existing bundle; engineer narrowings D2/D3 of the W4 entry.
7. **Replay-identity fixes** (Phase 1 W1.3/W1.4, Q-P1-1): are the substitution proofs real tests that would fail;
   do the counters now equal the trace meter on every reachable path.

## 4. Do not spend time on

Style (ruff/mypy clean); re-deriving PTC-R1 or SYN-001; the release-spec phases 2–5; the V19 ammonia work; the
MCP description prose.

## 5. Context

- A side branch `wp/T08-d1-str05` (`18ccc00`) extends D1 to STR-05 and moves the `t07` key by substitution only
  (`11bcb148…` → `422aa7a5…`); held for Frank's approval. Out of scope unless time permits.
- Human review is Frank's; never set `reviewed`.
