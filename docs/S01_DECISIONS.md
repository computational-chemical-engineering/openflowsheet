# S01 — build decisions (countercurrent equilibrium-stage subsystem)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`

- DECISION: S01 provider → SYN-001 only (PR C1 is vapour-only). Alternative: none without a new property method. Reversible by: adding a provider in a later package.
- DECISION: S01 form → a unit-layer cascade (rows, initializer, pre-solve) that calls `solve_region` unchanged. Alternative: its own attempt controller, or N stage units on the traversal path. Reversible by: S02 registering the stage rows as library units.
- DECISION: continuation easy endpoint → the isothermal pre-solve root `x⁰`, an exact root of ADR 0010 D2's `H(·,0)` with `p⁰ = Q(x⁰)`. Alternative: a K-value/CMO model homotopy (not a real flowsheet at λ < 1; needs an ADR). Reversible by: an ADR adding a model homotopy.
- DECISION: split feed → lift `m_j` (C extra columns and rows per stage, DOF-neutral). Alternative: widen `LiftedSplit.feed` to sums (moves its registered digest). Reversible by: an ADR widening `LiftedSplit`.
- DECISION: dormant-stage label → `T_{j−1}` (`T_top` for j = 1). Alternative: the vapour inlet's temperature. Reversible by: amending §4.3 (no registered identity uses it yet).
- DECISION: partial dormancy → not claimed; A19 asserts no false success. Alternative: a structural-dormancy opening rule. Reversible by: a later package adding the rule and an assertion.
- DECISION: inlets → declared single-phase only; two-phase is `unsupported`. Alternative: lifting an inlet split. Reversible by: adding the lifted inlet form.
- DECISION: β̄ clamp → [0.1, 0.9] and CMO floor 0.1·F. Alternative: unclamped (the pre-solve degenerates at β̄ ∈ {0, 1}). Reversible by: changing two constants and re-emitting `ref`.
- DECISION: inlet pressure vs stage pressure → no relation in S01 (enthalpy at the inlet's own state). Alternative: an equality row. Reversible by: S02's feed conventions.
- DECISION: ADR 0043 → not needed (no ADR or frozen interface changes). Alternative: an ADR for the pre-solve. Reversible by: writing it if review disagrees.
- DECISION: dormant inlets of D1, D2 and A19 → C2's `top`/`bottom` states with zero flow (330 K liquid, 380 K vapour, `P_r`). Alternative: equal inlet temperatures (a label taken from the wrong stream would then pass). Reversible by: changing `DORMANT_TOP`/`DORMANT_BOTTOM` and re-emitting `ref`.
- DECISION: A19 expectation → a §4.5 outcome other than a §5 refusal (the generator proves the probe valid), or a `CONVERGED` root passing §8; with signature (`ZERO_FLOW`, `ZERO_FLOW`, `LIQUID`) it must equal `ref.partial_dormancy.target`. Alternative: "no false success" alone. Reversible by: amending the A19 row; partial dormancy stays unclaimed (§14).

### WO-1 build decisions (`opus-engineer`, 2026-10-21)

- DECISION: module → `src/openflowsheet/models/syn001/cascade.py`, `MODEL_ID = "syn001.cascade"`, manifest families `CAS-mix`, `CAS-mole`, `CAS-equilibrium`, `CAS-Ldef`, `CAS-Vdef`, `CAS-energy`, `CAS-P`, `CAS-Q`, `CAS-inlet-{n,T,P}` (`EQUATIONS`, read by ADR 0008 U1). Alternative: `countercurrent.py`. Reversible by: renaming (no registered identity uses it).
- DECISION: column ids → `<U>.stage.<j>.{l,v,m}.<c>` and `<U>.stage.<j>.{L,V,T,P,Q}`; inlet columns are `flow_id`/`temperature_id`/`pressure_id` of the stream `<U>.inlet.<port>`; order: stage 1..N (l, v, m, L, V, T, P, Q), then inlets (top, bottom, sides). Alternative: one stream id per internal stream. Reversible by: the id helpers in `cascade.py`.
- DECISION: row ids → `<U>:stage:<j>:{mix,mole,eq}:<c>`, `<U>:stage:<j>:{Ldef,Vdef,energy,P,Q}`, inlets `<U>:inlet:<port>:{n:<c>,T,P}`, the `ZERO_FLOW` label row `<U>:stage:<j>:label`. Alternative: T05-style family names. Reversible by: the id helpers.
- DECISION: pinned-input ids → `<column id>*` (e.g. `S01.stage.2.Q*`). Alternative: the feed's `n_spec.<c>` style. Reversible by: `_parameter`.
- DECISION: block ids → `lnK_<U>_s<j>`, `H_<U>_s<j>_{vapor,liquid}`, `H_<U>_in_<port>_<phase>`; the unit id and every port must be a CasADi token (`SpecificationError` otherwise, never sanitized). Alternative: hashed block ids. Reversible by: `declared_rows`.
- DECISION: spec object → `CascadeSpec(unit_id, stage_count, pressures, duties, top, bottom, sides)` with `InletState(n, T, P, phase: str)` and `SideFeed(port, stage, state)`; nothing is checked on construction so §5 can refuse it. Alternative: `__post_init__` checks (would raise instead of refusing). Reversible by: adding checks.
- DECISION: §5 order → R1, R2, R3, R4, R6, R5, R7 (R6 before R5: admissibility needs a declared phase); a malformed object (flow-vector length, pressure/duty count ≠ N, non-finite `Q_j*`, duplicate ports) raises `ValueError`, not a §5 refusal. Alternative: refusing those too under an invented code. Reversible by: `validate`.
- DECISION: R3's `<id>` → the offending column id (`<U>.inlet.<port>.T`, `<U>.inlet.<port>.P`, `<U>.stage.<j>.P`). Alternative: the parameter id. Reversible by: `validate`.
- DECISION: regime pins/drops → plain-id `RegimeForm` (pinned, dropped, swapped, label) per stage in WO-1; WO-2 maps them onto `region.LiftedSplit` / `ZeroFlowForm`. Alternative: building the region descriptors now (their `unit` keying is WO-2's call). Reversible by: WO-2 replacing `RegimeForm`.
- DECISION: initializer `K` → the provider's `lnK` at `(T̄, P_j*)`; the `k_values` hook (A02) replaces `K` in step 5 only, `T̄` is always the provider's band temperature. Alternative: a separate Kremser function (would not test the public initializer). Reversible by: dropping the hook.
- DECISION: a `BandError` (bisection budget, provider refusal) in the initializer propagates as an exception; only `band_temperature`'s `below`/`above` is `tbar_outside_domain`. Alternative: a new cause code. Reversible by: catching it in `kremser_initial`.
- DECISION: `declared_problem`'s label → `"syn001.cascade"`, a placeholder for float evaluation only; the compiled label (identity) is WO-2's. Reversible by: WO-2.
- DECISION: §4.6 outcome → derived from the swapped energy rows evaluated by `compile.reference` at the closed-form state (not read off `Q_j*`); the answer carries the `ZERO_FLOW` system's residuals. Alternative: compare `Q_j*` to zero directly. Reversible by: `dormant_answer`.
- DECISION: the `tbar_outside_domain` test stubs `band_temperature` → SYN-001 cannot reach the branch (its band temperature lies in about [298, 428] K over the whole domain: pure A at 0.5 bar, pure C at 2 bar), so the test checks only the mapping of `below`/`above` to the typed failure. Alternative: a shifted test provider. Reversible by: replacing the stub.
- DECISION: WO-1 tests → `tests/test_s01_cascade_wo1.py`, pinned to `s01_reference.json` by its SHA-256 (`4c1a24f6…`). Alternative: no pin. Reversible by: dropping `test_the_reference_is_the_registered_one`.

### Design-lane questions

- QUESTION: §5 has refusals carry `INVALID_SPECIFICATION`, which is not a `SolveOutcome` value, and §4.5 says "no new outcome values". WO-1 returns it as `CascadeFailure.outcome` (a local literal, outside `SolveOutcome`). How must WO-2 surface it — a `SolveOutcome`, an application error, or a raised `SpecificationError`?
- QUESTION: R7 with every inlet dormant has bounds `[0, 0]` and would refuse D2 (`Σ Q* = 50 W`) before §4.6 can answer `SPECIFICATION_CONFLICT` (A14). Implemented: R7 is not applied when every inlet is dormant (`validate` returns `None`; §7.1 then routes to §4.6). Confirm R7's scope.
- QUESTION: R5 cites R-007 admissibility but writes the bubble/dew sum test; the code's R-007 (`tp_state.single_phase_admissible`) is an enthalpy-gap test that also admits within `τ_T = 1e-6 K` and temperature-degenerate streams. Implemented the spec's sum test (`≤ 1` admissible) at the inlet's own `(T, P)`. Which is normative at the boundary?
- QUESTION: §1 has `top` enter as liquid and `bottom` as vapour, but §3/§5 let every inlet declare its phase; a VAPOR `top` or LIQUID `bottom` is accepted (rows and initializer are phase-generic, as in the generator). Should §5 refuse it?
