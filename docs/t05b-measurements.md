# T05b measurements (append-only)

Build-lane measurements for T05b (spec `docs/derivations/T05b-limitations-spec.md` §20). Each
entry: the date, the commit it was measured at, the command, and the number. Entries are
appended, never rewritten; a later measurement that supersedes one says so. Commands run from
the repository root with `PYTHONPATH=src:.` and the project venv.

---

## 2026-09-25 — W0 at `b8c6442` (+ `89450ff`, a lint-only change to the reference generator)

### Gate at the base (before anything)

`./scripts/check.sh` at `b8c6442`: **pytest 2548 passed**, mypy clean, but **ruff check (7) and
ruff format failed** on `docs/derivations/scripts/t05b_reference.py` (6 × E501, 1 × B008; format).
Commit `89450ff` formats it, shortens one docstring and moves `heater_rows`' `mpf(0)` default into
the body. Its output is unchanged: `python docs/derivations/scripts/t05b_reference.py --check
--emit <tmp>` → `454 claims passed`, `sha256 35c4e6dbffee9165739292d6d0b0d00b8090c4219df091512151c9a0dce509ba`
before and after (the committed YAML's), 80 s.

### W0.1 — inertness baseline

| Quantity | Command | Value |
| --- | --- | --- |
| gate count | `./scripts/check.sh` | 2548 passed |
| `thermo/syn001.py` SHA-256 | `sha256sum src/process_runtime/thermo/syn001.py` | `75c9d5bad4f1cb3c8aa28b97d529777949434ebf911c0d9e11568b1e69ddd6ce` |
| K05 identity document (whole file) | `python scripts/k05_structural_identity.py --out x.json; sha256sum x.json` | `622463f5fbc8716f1196bc971633877e2d218e1c9744e3d4ad7d49608be0415b` |
| … minus `t05` | `d = json.load(x); d.pop("t05"); sha256(json.dumps(d, indent=1, sort_keys=True) + "\n")` | `b364bb3dc881402fd6e7982532b19f06dba60e5c6b01e70d1aab861bae030b5a` |
| … its `t05` key | `sha256(json.dumps(d["t05"], sort_keys=True))` | `ddbd0f7135ee5310a1ce65865fab69b69cafe542851a038086941740360687a3` |
| `structural_sha256` | the document's field | `4ce030cab1e4b4a2402897f480e5194961a1dbe9b8705316ddd4776cbd2d0082` |
| `policy_sha256` (SYN-001 run) | the document's field | `051a894cc707714bfb3efa52b7a860603b4c082cef326dcc33bce1b96c4aa654` |
| K04 `check_policy_sha256` | `CheckPolicy().sha256` | `21c44e105a1b78428047258af3030b8502957aab5d27f0389c2f143bcb3cf390` |
| B02 baseline (every registered `ph_state` call, bitwise) | `python scripts/t05b_ph_baseline.py --emit` → `tests/fixtures/t05b/ph_state_baseline.json` | `3390d7c8f789ad8b9802df85d0b04ec87808009f5876d883e010298df18fb83a` |

The baseline records 30 kernel calls: the 17 made while evaluating T05's registered unit cases of
the PH flash, the valve and the reactor (PHF-1…7, PHF-F1, F2; VLV-1…5; RX-3, RX-5, RX-F5 — PHF-F3,
F4, Z0, Z1, VLV-Z, F1 and the other RX cases do not reach the kernel), the 8 direct calls of T05
W0.4 (`PH_TYPE`), and the traversals of C1 (2 calls), C2 (0: its reactor is in outlet-temperature
mode), C3 (2) and C3X (1). Answers: 26 `bracket`, 1 `saturation` (PHF-6), 3 `out_of_domain`
(PHF-F1, PHF-F2, RX-F5). The unit answers of all 31 registered unit cases of the three models are
in the file too.

Pre-change outcomes under `T05-W13` (`tests/t05b_support.py` builds the revisions of spec §12.3;
`plan_revision` → `execute_plan` → `verify_revision` when converged):

| Case | Outcome | First message line |
| --- | --- | --- |
| SC-1 (T05 A30's P3) | `ACTIVE_SET_CYCLING` | `active_set_cycling(U-VLV:LIQUID; phase_wall(patience, U-VLV:VAPOR->LIQUID))` |
| SC-2 (T05 A30's P4) | `BOUND_BLOCKED` | `a component sits on its lower bound and the Newton direction points out of the feasible set; no trial can be taken along it` |
| SC-3 | `ACTIVE_SET_CYCLING` | `active_set_cycling(U-VLV:LIQUID,U-PHF:LIQUID; phase_wall(patience, U-VLV:VAPOR->LIQUID, U-PHF:VAPOR->LIQUID))` |
| SC-4 | `INITIALIZATION_FAILED` | `initializer_failed(U-PHF2): inadmissible_phase(inlet, VAPOR)` (spec B11's pre-change value: confirmed) |

### W0.2 — §5.3's row ratios at every registered call

Every `ok` call of the B02 baseline (27 of 30; the other 3 are the registered `out_of_domain`
refusals), rows evaluated from the provider's `lnK` and `h` at the answer's `(T, P)`, divided by
`τ_flow = 3.1e-8`, `τ_eq = 9.3e-8`, `τ_E = 1.01e-3`. Worst: **material 7.16e-9, equilibrium
4.06e-8 (PHF-1), energy 1.37e-7 (VLV-5)**; the saturation route (PHF-6) is exactly 0 on all three.
All ≤ 1e-3 by at least four decades, so §5.3 accepts every registered temperature-route answer
and B02 is expected to hold bitwise.

### W0.3 — how the traversal's closure split can reach `initial_state` (spec §18 Q6)

`initial_state` (`orchestrator/revision.py:87`) reads `flowsheet.traverse(...)`'s
`FlowsheetPass.evaluations: Mapping[str, UnitEvaluation]` (`models/revision_flowsheet.py:383`),
filled by `unit.evaluate(...)` (`:512`). `UnitEvaluation` (`models/__init__.py:316`) carries no
split and no route; the kernel's `PHState` is returned only by the models' test-facing
`evaluate_with_closure` (valve, PH flash) and `evaluate_with_split` (reactor), which the
traversal does not call. `UnitEvaluation` is not in `docs/interfaces-frozen.md` or the plan's
frozen list (T05 F6 added `work`, `extent`, `transferred_duty` to it), so an optional field
(`None` for K02 units) is the route without a frozen-type change — as spec Q6 expects. One
consequence to note for W6: setting it means editing `valve.py`, `ph_flash.py` and
`conversion_reactor.py`, whose own file SHA-256 is each manifest's
`implementation_artifact.artifact_hash`. That hash is not in the flowsheet label (R-047) and does
not occur in the K05 identity document (`grep artifact_hash x.json`: absent), so no identity is
expected to move; W6 must confirm it.

### W0.4 — committed records with a `branch_found` item for a split with `V = L = 0`

Scan of every committed `*.json`/`*.yaml` under `tests/fixtures`, `benchmarks` and `evidence`
(126 files) for `branch_found` keys and for split records (`vapor_total`, `liquid_total`):
18 `branch_found` items in 6 files; 3 split records (the three `solution_certificate` fixtures),
none with `V = L = 0`. **One finding against the letter of W0.4:** `evidence/T05/91ac010…/manifest.json`
(T05's A28 value, lines 3304, 3352, 3396, 3437) records `branch_found` `[[U-VLV, TWO_PHASE]]` and
`[[U-PHF, TWO_PHASE]]` for the two dormant mini-flowsheets — splits with `V = L = 0`. These are
exactly the "T05-era test record of a dormant split (A28's)" spec §8 and ADR 0012 D6 already name
as comparing `DISTINCT` with a new one; they are evidence of a retired assertion, not a registered
fingerprint that any test compares. No fixture, benchmark or other manifest has one (T03's
`root_fingerprint_branch_found` entries are PHS cases with flowing feeds). Reported to the design
lane; nothing depends on it before W4.

### W0.8 — the verdict with a `not_applicable` `independent_split` on a flowing split

`verify/certificate.py::grade` (`:200`) decides the status from `fail` checks in
`FAILING_CATEGORIES`, `unsupported` checks in `REQUIRED_CATEGORIES`, the regularity status, the
derivative flag and the policy; a `not_applicable` check enters none of these, whatever its
reason and whether its stream flows. The revision table emits the dormant case through
`verify.dormant(...)` (`table.py:998`), which takes a `reason` argument (default `ZERO_FLOW`).
So a flowing, degenerate split reported `not_applicable` with reason `temperature_degenerate`
is accepted exactly as a dormant one is; no change to the verdict logic is needed.

## 2026-09-25 — W0.5 with W1's two band implementations (before W2)

### W0.5 — `δ` at the registered states W1.d and C1–C3 evaluate (B14)

Script: `python scripts/t05b_degeneracy_margins.py` (W1.d's `shaped_revision` solved by `test_t05_w1d_verifier._solve`,
its root and `initial_state` `x⁰`; C1–C3 solved by `test_t05_coupled.solve`), `δ` of every
flowing stream at its own `(n, T, P)` and of every lifted split's feed at the split's `(T, P)`,
by `models/syn001/saturation_band.degeneracy_distance` and by `verify/saturation.degeneracy_distance`.

| State | Items | Minimum `δ` (K) | Where |
| --- | --- | --- | --- |
| W1.d root (SYN-001 nominal) | 7 streams, 2 splits | 17.529061 | `split:U-FLASH` |
| W1.d `x⁰` | 7 streams, 2 splits | 16.284804 | `split:U-FLASH` |
| C1 root | 6 streams, 3 splits | 20.379882 | `S5` |
| C2 root | 5 streams, 1 split | 30.237185 | `S4` |
| C3 root | 8 streams, 1 split | 18.406042 | `split:U-PHF` |

Every value ≥ 1 K (overall minimum **16.28 K**, at the non-root `x⁰`); every value at the roots
equals `ref.degeneracy_at_registered_states_K` to its six decimals; the two layers agree
bitwise at all 41 items (max |difference| 0).

## 2026-09-25 — W2: the kernel's acceptance and band route (spec §5)

### Inertness (W0.2's prediction, B02)

- `python scripts/t05b_ph_baseline.py --check` → `matches a live run`: all 30 registered calls
  and 31 unit answers bitwise the W0.1 baseline (`3390d7c8…`), messages included.
- K05 identity document regenerated: byte-identical to W0.1's (`622463f5…`; minus `t05`
  `b364bb3d…`; `t05` key `ddbd0f71…`; structural `4ce030ca…`; `check_policy_sha256` `21c44e10…`).
- SC-1…SC-4 under `T05-W13`: the W0.1 outcomes, unchanged (the contract is W6's).
- Cost on a registered call: +1 provider call (the §5.3 `lnK` evaluation at the answer); PHF-1's
  kernel call is 156 calls (53 flashes, 102 `h`, 1 `lnK`). Property-call counts are recorded,
  never compared (ADR 0007), and the identity above does not move.

### B01 — the 40-state grid (`tests/test_t05b_kernel.py`)

All 40 `ok`; routes: 21 `bracket`, 19 `band`, **identical state for state to the twin's 53-bit
emulation** (`ref.kernel_grid.*.measured_53_bit.route`). Worst errors against the 40-digit
reference (tolerances `T` 1e-6 K, `V` 1e-7 mol/s, `q` 1e-6):

| Route | `|T − T*|` (K) | `|V − V*|` (mol/s) | `|q − q*|` |
| --- | --- | --- | --- |
| taken (both) | 3.94e-13 | 2.39e-8 | 1.20e-8 |
| band only | 4.91e-14 | 4.04e-16 | 6.41e-16 |

(the twin's emulated floors: 3.94e-13 / 2.39e-8 / 1.20e-8 and 5.69e-14 / 5.51e-16 / 7.52e-16).
Worst ratio to tolerance: `V` 0.24 (bracket route at NPK-A-1e-7-0.7, inside the acceptance's own
bound `τ_E / min Δh = 4.04e-8`). Band-route `F` evaluations 47–56 (budget 64).

### B03, B04 — the provider doubles

- JUMP: `not_converged`, `ph_ill_conditioned`, no temperature, no split; both routes close on
  the jump at 360.0 K with energy rows **6.74e5 `τ_E`** (the twin: 680 W, 6.7e5 `τ_E`); 109
  evaluations (53 bracket + 56 band).
- BIASED: `ok`, route `band`, `|T − T_PHF-1| = 1.5e-14 K`, worst flow error 1.9e-16 mol/s.

### W0.6 — the band route's cost, and the budget the region meters

Counting provider over the 19 band-route grid states (script: the band route run alone on a
call-counting wrapper of SYN-001): at most **3 088 provider calls** for one band route
(NPK-C-1e-9-0.3: 2 978 `lnK`, 110 `h`, 56 `F` evaluations), 3 214 for the whole kernel call
(with the temperature route's 53 flashes and its `h` calls) — inside the spec's ~3 500 estimate
and a third of the region's default cap. The region meters **`SolvePolicy.max_property_calls`**
(default `trace.REGISTERED_MAX_PROPERTY_CALLS = 10 000`) through the executor's meter
(`orchestrator/executor.py:700`); `budget.REGISTERED_MAX_PROPERTY_CALLS = 20 000` is referenced
by no code path (only its definition). No registered case runs the band route inside a region.

## 2026-09-25 — W3: R-007 admits a temperature-degenerate stream (spec §10)

`tp_state.single_phase_admissible` runs the unit layer's degeneracy test
(`saturation_band.degeneracy_distance`) only on its refusal path (gap `> 1e-6 K`); a degenerate
stream is admitted and its reported gap is `δ`. A band search the provider refuses leaves the
refusal standing. The verifier's declared-port check is unchanged in form (it reads W4's
enthalpy map).

### Inertness

Protocol after the change (`scripts/k05_structural_identity.py`, `scripts/t02_identity.py`):
`thermo/syn001.py` `75c9d5ba…`; K05 identity document `622463f5…` whole, `b364bb3d…` minus
`t05`; structural `4ce030ca…`; `CheckPolicy().sha256` `21c44e10…`; T02 floats `9a8a5baf…` — all
W0.1's. Gate: 2680 passed (2666 + 14 new), ruff, format, mypy clean.

### B19 (`tests/test_t05b_r007.py`)

| State | Declared | Verdict | Reported gap (K) | `ref` |
| --- | --- | --- | --- | --- |
| R7-1 (pure B, 360 K exactly) | VAPOR | admitted | `0.0` exactly (the first bisection midpoint of `[280, 440]` is 360 K, where `ln K_B = 0`) | `δ = 0` |
| R7-2 (+2e-6 K) | LIQUID | refused, `inadmissible_phase(inlet, LIQUID)` | TP gap 300 K | refused |
| R7-3 (+5e-7 K) | LIQUID | admitted | `δ` within 1e-12 K of 5e-7 | admitted |
| R7-4 (equimolar, 347.45 K) | LIQUID | refused as registered | TP gap 0.098 K | `δ = 26.82 K` |

Both T05 routes into R-007 (`ph_kernel.port_enthalpy`, `admission.admitted_enthalpy`) carry
the same verdicts. T05's five registered refusals: unit-layer `δ` within 1e-6 K of
`ref.t05_registered_refusals_degeneracy_K` (PHF-F3 and PUMP-F2 14.270304 K, PUMP-F1 72.558818,
SEP-F2 29.270304, HX-F4 24.270304) and still refused; T05 A07–A12 pass unchanged.

## 2026-09-25 — W4: the verifier (spec §9.1–§9.3) and `branch_found`'s `ZERO_FLOW` arm (§8)

Implemented: `roots.branch_found` reports `ZERO_FLOW` for `V = L = 0` (ADR 0012 D6, every
literal); `region._admissible` admits a `ZERO_FLOW` branch iff its feed is exactly dormant, else
`inadmissible(<stream>, zero_flow)` (§7.3's rule under v1). The table (`verify/table.py`) judges a
flowing split whose feed is temperature-degenerate at the split's `(T, P)` by its stored split
(`.saturation`, `independent_split` `not_applicable` `temperature_degenerate`, the enthalpy map and
the qualification notes), and a degenerate stream outside any split in its declared phase (§9.2;
`vapor_liquid` → `unsupported`, `temperature_degenerate_unlifted(<S>)`). `verify/zero_flow.py`
reduces a `ZERO_FLOW` split's rows and columns (§7.2) for the regularity screen and adds the
`residual.<U>:zero-flow-label` check. Nothing in the orchestrator's split registry or regime set
changed (W6/W7).

### Inertness (B14, W0.4)

- Protocol: `thermo/syn001.py` `75c9d5ba…`; K05 identity document `622463f5…` whole (so the `t05`
  key, C1–C3's certificates' R0, is unchanged), `b364bb3d…` minus `t05`; structural `4ce030ca…`;
  `CheckPolicy().sha256` `21c44e10…`; T02 floats `9a8a5baf…`. W1.d's legacy/general bitwise
  pairing (`test_t05_w1d_verifier.py`) passes unchanged at its root and `x⁰`.
- `table.degeneracy(...)` is empty at W1.d's root and `x⁰` and at C1–C3's roots; the verifier's
  minimum `δ` there: 17.529061 K (W1.d root = `ref` SYN-001-nominal), 16.284804 (`x⁰`), 20.379882
  (C1), 30.237185 (C2), 18.406042 (C3) — each root equal to `ref.degeneracy_at_registered_states_K`
  to its six decimals.
- W0.4 (no committed record with a `branch_found` item for `V = L = 0` except T05's A28 evidence at
  `91ac010`) is unchanged: this chunk commits no record.
- Gate: 2699 passed (2680 − 10 retired A28 tests + 29 new), ruff, format, mypy clean.

### B15, the `T05-W13` half (`tests/test_t05_dormant_outlet.py`, T05 A28 retired)

| Case | Outcome | Attempts | `branch_found` | Certificate | Regularity | `rcond₁` (ref) | label residual |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DZ-1 (valve) | `CONVERGED`, 0 Jacobian calls | `[[U-VLV, TWO_PHASE]]`, 0 iterations | `ZERO_FLOW` | `VERIFIED` | `NO_RANK_LOSS_DETECTED`, 10 | within 5e-7 of 0.250000 | `0.0` |
| DZ-2 (PH flash) | same | `[[U-PHF, TWO_PHASE]]`, 0 iterations | `ZERO_FLOW` | `VERIFIED` | `NO_RANK_LOSS_DETECTED`, 10 | within 5e-7 of 0.111111 | `0.0` |

The reduced row and column sets equal `ref.dormant_cases.DZ-*.zero_flow_form` (modulo the test's
feed id `U-FEED-0`); the full form keeps T05's structure (18 × 18, rank 15, exactly the three
equilibrium rows zero). Every compiled residual `== 0.0`; nothing fails.

### B18 at SC-1's root (`tests/test_t05b_verifier.py`)

Judged by `verify_revision(..., state=<injected>)` with a stand-in `CONVERGED` claim carrying
SC-1's real `SolvePlan` (SC-1 has no converged v1 solve; W6's v2 solve replaces the stand-in).

| State | Verdict | Checks (value; tolerance) |
| --- | --- | --- |
| SC-1 root (control) | `VERIFIED`, `rcond₁` 5.4797e-3 | `.saturation` `0.0`; `energy_balance.U-VLV` `0.0` |
| INJ-B1 (all liquid) | `FAILED`, `false_success_detected` | `energy_balance.U-VLV` `+2016.0` W (`2e6 τ_E`); `.saturation` `0.0` passes; also `residual.U-VLV:VLV-energy` `2016.0` (the compiled row reads the lifted split) |
| INJ-B2 (+2e-6 K) | `FAILED`, `false_success_detected` | fresh flash: `independent_split.U-VLV.S2.total` `−1.9328` mol/s, `energy_balance.U-VLV` `−57 984.0004` W; every compiled row passes (`VLV-energy` `−4.0000e-4` W, `VLV-equilibrium:B` `−7.2322e-9`) |
| INJ-B2p (+5e-7 K) | `VERIFIED` | `.saturation` `4.99999999e-7` K; `energy_balance.U-VLV` `−9.99999993e-5` W |

§9.2 (a saturated pure-B vapour feed declared `vapor` into a PH flash, `Q = 2 000 W`, converged
under v1): `VERIFIED`, with `S1` read as vapour (72 000 W) where the fresh flash says liquid
(12 000 W) — the 60 000 W latent heat. Cost: the verifier now runs its band test (two bisections,
≤ 200 `lnK` each, ~55 in practice) at every flowing stream and split feed of a revision
certificate.

## 2026-09-25 — W5: the phase-contract literal (spec §6.6; ADR 0012 C1; Frank's approval)

`schemas/solve-policy.schema.json` `phase_contract`: `const` → `enum ["T03-phase-contract-v1",
"T05b-phase-contract-v2"]`; `SolvePolicy.phase_contract: PhaseContract` (a two-value `Literal`,
default v1); notes in `docs/interfaces-frozen.md` §2 and `schemas/README.md`.

### B06 (`tests/test_t05b_literal.py`) and R-015

- The schema accepts both literals and refuses `T03-phase-contract-v2`, `T02-interim`, `""`,
  `null`, `1` and absence; the default is v1.
- Fixtures: `scripts/k03_schema_fixtures.py --write` and `scripts/t04_schema_fixtures.py --write`
  rewrite both policy fixtures byte-identically (`syn001_k03.json`, `t04_ptc.json`, both v1). The
  K03 generator also rewrote `solve_event/valid/syn001_off_b_restart_trace.json` with different
  **property counters only** (the OFF-B total 521 → 729 `property_calls`): W3's degeneracy test
  on R-007's refusal path costs about 104 `lnK` calls per refusal, and OFF-B's trials meet two.
  Those counters are `UNREPRODUCIBLE_COUNTS`, which R-015's comparison forgives
  (`test_k03_schemas.py`), so the committed file was left as it was, not re-baselined.
- No code constructs a policy with a `phase_contract` keyword (AST scan of `src`, `scripts`,
  `benchmarks`, `tests`), and no committed fixture or benchmark document spells v2.
- Protocol unchanged (SYN-001's policy document is still v1): `622463f5…` / `b364bb3d…` /
  `4ce030ca…` / `21c44e10…` / `9a8a5baf…`, `thermo/syn001.py` `75c9d5ba…`. Gate 2711 passed.

## 2026-09-25 — W6: the R-007 pre-screen (build lane; T05b W3's cost)

`saturation_band.outside_the_degeneracy_window`: before `degeneracy_distance`'s two bisections on
R-007's refusal path, `g(T − 2τ_T; 0) > 0` (bubble point below `T − 2τ`) or `g(T + 2τ_T; 1) < 0`
(dew point above `T + 2τ`) refuses at once; anything else — including a provider refusal at
`T ∓ 2τ` — decides nothing and the band test runs as before. Argument (docstring): a computed
`δ ≤ τ` needs the exact band end within `τ + 1e-13 K` of `T`, where `|g(T ∓ 2τ)| ≥ 0.0155 K⁻¹ ·
(τ − 1e-13 K) ≈ 1.5e-8`, seven decades above `g`'s rounding; so a `True` never contradicts the
band test. Measured equivalence, HEAD (`923c784`) against the working tree, every result tuple
compared bitwise (verdict, enthalpy, gap, status, message):

| Population | R-007 calls | on the refusal path | admitted degenerate | mismatches | `lnK` calls before → after |
| --- | --- | --- | --- | --- | --- |
| the whole gate (`pytest tests/` with a comparing plugin; W3's and B19's tests, T05 A07–A12, K02, OFF-B, T05b) | 35 540 | 171 | 14 | **0** | 15 945 → 293 |
| sweep: 70 compositions (pure B, A, C; an equimolar ternary; an A–B binary; traces 1e-14…1e-5 mol/s of A and/or C in B and of B in A/C) × 3 pressures × band ends and mid-band ± {0, 0.25…3, 5, 10, 100, 1e4, 1e6} τ, each ±1 ulp, plus the domain edges, × both phases | 126 420 | 74 277 | 10 091 | **0** | 7 849 355 → 2 645 158 |

On the sweep 50 216 of the 64 186 refusals are decided by the pre-screen alone (the rest lie
within `2τ` of a band end or at a domain edge and run the band test). OFF-B (the K03 fixture's
restart solve): `CONVERGED`, 2 attempts, final state and event sequence bitwise identical
(state sha256 `ea0a1129…`); **property calls 729 → 523** (521 before W3). The committed OFF-B
trace fixture still records 521 — `property_calls` and `requested_evaluations` are the only
differing fields, which R-015's comparison forgives (`UNREPRODUCIBLE_COUNTS`); not re-baselined.
Protocol unchanged (`622463f5…` / `b364bb3d…` / `4ce030ca…` / `21c44e10…` / `9a8a5baf…`,
`thermo/syn001.py` `75c9d5ba…`). Gate 2762.

## 2026-09-25 — W6: the contract under v2 (spec §6.2–§6.5), D5's seeding, B18's real claim

Commits `7e2fc07` (D5), `6379514` (v2), `fd222ea` (record grammar), `923c784` (B18). Policy
`T05b-v2` = `T05-W13` with `phase_contract = T05b-phase-contract-v2` (`tests/t05b_support.py`,
the one construction B06 exempts). Tests: `tests/test_t05b_seeding.py`, `tests/test_t05b_contract.py`.

### Inertness

- D5: on C1, C2, C3 every heater-style split of the seeded start equals the TP re-flash bit for bit
  (C3X refuses before any split, as before); every coupled traversal closure is a bracket route.
- B07: C1, C2, C3, C3X under `T05b-v2` give v1's R0 projection (plan, events, certificate,
  structural report, message), v1's attempt records (kinds and messages) and v1's **whole** root
  fingerprint (state digests included, so the same root bit for bit) — the policy's identity aside
  (`policy_id` and the plan ids that embed it are the only differing fields).
- Protocol after each chunk: `thermo/syn001.py` `75c9d5ba…`; K05 identity document `622463f5…`
  whole, `b364bb3d…` minus `t05`; structural `4ce030ca…`; `CheckPolicy().sha256` `21c44e10…`;
  T02 floats `9a8a5baf…`; `t05b_ph_baseline.py --check` matches (B02).
- Gate: 2724 (D5) → 2759 (v2) → 2762 (pre-screen), ruff, format, mypy clean.

### The T05b cases under `T05b-v2`

| Case | Outcome | Attempts (signature: iterations) | Verdict | Regularity dim, `rcond₁` | solution-error bound (scaled) | Records |
| --- | --- | --- | --- | --- | --- | --- |
| SC-1 | `CONVERGED` | `[U-VLV TWO_PHASE]`: 0 | `VERIFIED` | 18, 5.480e-3 | 8.6e-16 | none |
| SC-2 | `CONVERGED` | `[U-PHF TWO_PHASE]`: 0 | `VERIFIED` | 18, 1.475e-2 | 0.0 | none |
| SC-3 | `CONVERGED` | `[U-VLV TWO_PHASE, U-PHF LIQUID]`: 2; `[…, U-PHF TWO_PHASE]`: 1 | `VERIFIED` | 31, 1.390e-3 | 2.6e-15 | `phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE))` — KS-1's primary answer, no fallback |
| SC-4 | `CONVERGED` | `[U-PHF1 TWO_PHASE, U-PHF2 TWO_PHASE]`: 0 | `VERIFIED` | 37, 2.988e-3 | 1.1e-15 | none |
| NP-1 | `CONVERGED` | `[U-PHF TWO_PHASE]`: 0 | `VERIFIED` (degenerate) | 18, 1.567e-2 | 2.1e-16 | `closure_route(U-PHF, band)` |
| NP-2 | `CONVERGED` | `[U-PHF TWO_PHASE]`: 0 | `VERIFIED` (degenerate) | 18, 1.078e-2 | 1.3e-15 | `closure_route(U-PHF, band)` |
| NP-3 | `CONVERGED` | `[U-PHF TWO_PHASE]`: 0 | `VERIFIED` (fresh flash) | 18, 1.567e-2 | 3.8e-10 | none |
| NP-G | `CONVERGED` | `[U-PHF TWO_PHASE]`: 0 | `VERIFIED` (fresh flash; B13 regression value) | 18, 1.567e-2 | **7.0e-8** | none |

Every state is within spec §13's EO allowances of `ref`. Under `T05-W13` SC-1 and SC-3 still end
`ACTIVE_SET_CYCLING` and SC-2 `BOUND_BLOCKED` (never `VERIFIED`; W0.1's outcomes). KS-1, KS-2,
KS-3 (B20 (b)): `TWO_PHASE` at 360 K, `β = 0.016933…` (record `""`); `TWO_PHASE`, band route
(`fallback(U-VLV, ph-band)`); `LIQUID` from the TP flash (`fallback(U-VLV, tp)`); the TP flash
alone reports `VAPOR`, `VAPOR`, `LIQUID`. **For W0.9:** NP-G's recorded solution-error bound is
7.0e-8, above §13's `1e-8` rule; it starts (and ends, at iteration 0) on the traversal's bracket
answer. Every other case here is ≤ 3.8e-10.

B18 now judges its injections against SC-1's real v2 solve: SC-1 root `VERIFIED`; INJ-B1 `FAILED`
with exactly {`residual.U-VLV:VLV-energy`, `energy_balance.U-VLV`, `energy_balance.envelope`} at
+2 016 W; INJ-B2 `FAILED` (−1.9328 mol/s, −57 984.0004 W); INJ-B2p `VERIFIED` — unchanged from W4.

## 2026-09-25 — W7b's W0.10 and W0.11 (before any W7b code, base `10c17c7`)

Protocol at the base: `thermo/syn001.py` `75c9d5ba…`; K05 identity document `622463f5…` whole,
`b364bb3d…` minus `t05`; structural `4ce030ca…`; `CheckPolicy().sha256` `21c44e10…`; T02 floats
`9a8a5baf…`; `t05b_ph_baseline.py --check` matches; B07 4 passed. The DZ-6…DZ-12 revisions are
`tests/t05b_support.py`'s `dz6` … `dz12` (spec §12.8–§12.9).

### W0.10 — no committed record has an active dormancy form (B30 (b))

- **Every state in a committed record** (`git ls-files tests/fixtures benchmarks evidence`, 127
  JSON/YAML files; every mapping keyed `<S>.n.<c>`, 59 of them): the only mappings with a stream
  whose every flow is exactly zero are 17 in `benchmarks/t05b/reference_values.yaml` — the DZ
  cases' own roots, starts and end states. Signature pairs whose unit is `<U>.<port>`: 7, all in
  the same file (`dormant_non_lifted_cases`, `zero_flow_conflicts`: the registered items).
- **Every committed revision with a dormancy-form model** (its outlets per spec §7.6, the
  exchanger's by its pinned specification): SYN-001's 17 cases — `mixer.outlet`, inlets `S1`
  (specified `(1,1,1)`) and the recycle; C1 `U-PUMP.outlet` (inlet `S1`, `(1,1,1)`); C2
  `U-MIX.outlet` (`S1` `(2,1,0)` and the recycle); C3 and C3X `U-HX.cold_outlet` (`S1`, `(1,1,1)`;
  the hot side is temperature-specified, no form) and `U-MIX.outlet` (two internal streams). A
  mixer's trigger needs every inlet dormant, so a specified flowing feed on any inlet rules it out.
- **Registered roots:** T05's coupled-case streams (`benchmarks/t05/reference_values.yaml`) give
  every trigger total `> 0` (smallest: C2's recycle `S4`, 2.143 mol/s total); T05b's
  `registered_dormancy_trigger_flows_mol_per_s` lists 7 triggers, every total `≥ 1.0`.
- **Registered runs** (C1, C2, C3, C3X, SC-4 under `T05-W13` and `T05b-v2`; attempt 0's opening,
  every attempt's end state, the final state): no trigger stream is dormant anywhere. Smallest
  trigger totals: C1 3.0 (`S1`), C2 1.375 (`S4` at the opening), C3 1.138 (`S6` at the opening),
  SC-4 1.0 (`S3`, v2) / 2.0 (v1); C3X ends `INITIALIZATION_FAILED` before any attempt (both).
- SYN-001's own flowsheet (T02–T04) runs `T03-phase-contract-v1` and SYN-001's legacy check set,
  neither of which reads a form (spec §7.10, §9 preamble); its mixer has a specified flowing feed.

Result: the premise of spec §7.9's identity statement holds on every committed record; nothing
needs re-registration.

### W0.11 — the read checks

- **(a)** `RevisionFlowsheet.traverse` (`models/revision_flowsheet.py:510`) evaluates each unit on
  `tuple(value[s] for s in wiring.streams[port])`, and `InstanceView.wiring` is
  `Wiring(dict(self.ports))` — the ports in R1 connection order. The K02 mixer's dormant label is
  `connected[0].temperature` (`models/syn001/mixer.py:423`). So `connected[0]` is the first inlet in
  connection order, §7.6's label source.
- **(b) Finding (the letter of W0.11 (b) holds only for the twin's declaration order).** At DZ-9
  T01's certificate and K03's alias elimination agree, but *which* redundant pressure row they
  remove follows the order the instances are declared in: feeds before the mixer (the twin's
  order) → both remove `U-MIX:MIX-pressure:1` (as registered); the mixer before its feeds
  (`t05b_support.revision`'s default order) → both remove `U-FEED-1:FEED-P`. `dz9()` therefore
  declares its feeds first. The zero-flow form is square either way (16 rows, 15 columns, one
  alias out).
- **(c)** `certificate.grade` (`:205`) reads `fail` in `FAILING_CATEGORIES`, `unsupported` in
  `REQUIRED_CATEGORIES`, the regularity status and the derivative flag; a `not_applicable` check
  enters none of them (as W0.8). **Finding:** the table already reports all three exchanger
  one-sided checks `not_applicable`, reason `ZERO_FLOW`, whenever either inlet is dormant
  (`Unit.one_sided`, `verify/table.py:234`, T05 §4.3's rule) — measured at DZ-7 and DZ-8 before
  any change. So F8's premise ("the verifier judged `hot_end` and `cold_end`") does not hold in
  this code; what §9.3 changes is that `heat_flow` is judged at a dormant side.
- **(d)** `_region_problem`'s `labels` are `(row id, T_out, T_label)` triples of the attempt's
  system — any row id, any two columns — and a swapped row is a compiled row left out of `rows`;
  the item `(<U>.<port>, ZERO_FLOW)` is an `AttemptSignature` pair (`str`, `PhaseSignature`) and
  fits the attempt-context and checkpoint schemas (unit: any non-empty string). No frozen type,
  schema or Newton-core contract changes. One property of the core, recorded: Newton screens a
  trial only when the frozen signature is non-empty (`newton.py:450`, `signature and …`), so on a
  flowsheet with no lifted split an attempt *without* items is not screened; §7.8 (iv) 1's closure
  agreement is what catches a trigger that became dormant there.

Pre-change outcomes (base code; the regression values the new code is compared against): DZ-6,
DZ-7, DZ-8, DZ-9 `CONVERGED` at iteration 0 (no Jacobian call) in the declared form, signature
`[]`, under both literals, certificate `UNVERIFIED`, `RANK_DEFICIENT` at dimension 11 / 21 / 21 /
15 (spec §7.6's last bullet); DZ-10, DZ-11 and DZ-12 `LINEAR_SOLVE_FAILED` (`SuperLU: Factor is
exactly singular`) under both.

## 2026-09-25 — W7b: dormant non-lifted outlets (spec §7.6–§7.10, §9.3)

Commits `ad2f2ad` (registry, `check_agreement` (g)), `408daea` (verifier), `f6802ed` (region),
`9c85948` (items read by their key in the lattice and the cause grammar).
Tests: `tests/test_t05b_dormancy.py` (56: 55 pass, 1 `xfail(strict)`); in
`tests/test_t05_table_independence.py` one new test (the two tables as data) and three injected
imports. Probe: the scratchpad's `w7b_probe.py` (every DZ case under
both literals, with the numbers below).

### Inertness

- Protocol after each of the four chunks (tags `c1`…`c4`): `thermo/syn001.py`
  `75c9d5ba…`; K05 identity document `622463f5fbc8716f…` whole, `b364bb3d…` minus `t05`;
  structural `4ce030ca…`; `CheckPolicy().sha256` `21c44e10…`; T02 floats `9a8a5baf…`;
  `t05b_ph_baseline.py --check` matches; B07 4 passed. Unchanged throughout.
- W0.10 (above) and B30 (a): C1, C2, C3, C3X, SC-1…SC-4, NP-1…NP-3, NP-G, DZ-1…DZ-5 under
  `T05b-v2` carry no item in any attempt signature or provenance item.
- Gate `./scripts/check.sh` at `9c85948`: ruff, format, mypy clean; **2864 passed, 2 xfailed** (base
  2808 + 1: 56 new tests pass, B26 is the new xfail beside B16). The first gate run (at `f6802ed`)
  failed one K03 test, `test_the_attempt_budget_is_a_typed_outcome`: the first `adjacent`/`_changes`
  aligned entries by name, and that test's synthetic signatures carry distinct unit ids; `9c85948`
  reads an item by its key (`<U>.<port>`) and judges unit entries exactly as before.

### The DZ cases (`T05b-v2`; `T05-W13` in the last column)

| Case | Outcome | Attempts (signature: core iterations) | Verdict, regularity dim, `rcond₁` | v1 |
| --- | --- | --- | --- | --- |
| DZ-6 | `CONVERGED`, 0 Jacobian calls | `[U-PUMP.outlet ZERO_FLOW]`: 0 | `VERIFIED`, 11, 0.24996 | `CONVERGED` in `[]`, `VERIFIED`, 11 |
| DZ-7 | `CONVERGED`, 0 Jacobian calls | `[U-HX.hot_outlet ZERO_FLOW]`: 0 | `VERIFIED`, 21, 0.11537 | same, `VERIFIED` |
| DZ-8 | `CONVERGED`, 0 Jacobian calls | `[U-HX.cold_outlet ZERO_FLOW]`: 0 | `VERIFIED`, 21, 0.23083 | same, `VERIFIED` |
| DZ-9 | `CONVERGED`, 0 Jacobian calls | `[U-MIX.outlet ZERO_FLOW]`: 0 | `VERIFIED`, 15, 0.25000 | same, `VERIFIED` |
| DZ-10 | `CONVERGED` | `[U-PHF TWO_PHASE, U-PUMP.outlet ZERO_FLOW]`: 2 | **`FAILED`** (below), 34, 0.013055 | `LINEAR_SOLVE_FAILED` |
| DZ-12 | `CONVERGED` | `[U-PHF LIQUID, U-HX.hot_outlet ZERO_FLOW]`: 0 → `[U-PHF TWO_PHASE]`: 1 | `VERIFIED`, 34, 0.0067204 | `LINEAR_SOLVE_FAILED` |
| DZ-11 | `SPECIFICATION_CONFLICT`, `zero_flow_conflict(U-HX:HX-energy-hot)` | `[U-HX.hot_outlet ZERO_FLOW]`: 1 | — (swapped row −1 000.0 W) | `LINEAR_SOLVE_FAILED` |

Every `rcond₁` equals the twin's (`ref…zero_flow_form.rcond1_scaled`: 0.249956, 0.115367, 0.231,
0.250000, 0.0131; DZ-12's root 0.00672) to its printed digits. DZ-6…DZ-9's roots are the
traversal starts bit for bit (`ref…root`, every column `==`); DZ-12's final state is within
2.3e-13 of `ref…DZ-12.root` (largest: `S4.T`); DZ-11's end state equals `ref…end_state` exactly
(`S4.T = 303.3333333333333`, `U-HX.Q = 1000.0`). DZ-12: attempt 0's `LIQUID` branch inadmissible
with `Σ x K = 3.4243620737585667` (`ref` 3.42436207376); attempt 1 opens with
`phase_update(inadmissible(S1, all_liquid))`, 34 rows, and converges in 1 iteration (regression
value); with the outlet reset disabled the same attempt ends `LINEAR_SOLVE_FAILED` (negative
control for F7). Without the swapped-row test DZ-11 closes `CONVERGED` at `U-HX.Q = 1000.0`
(negative control for F6). Before W7b (base code) DZ-6…DZ-9 were `CONVERGED` and `UNVERIFIED`
(`RANK_DEFICIENT`) under both literals.

**B26 — stop-and-report.** DZ-10 under v2 converges in one attempt (2 Newton iterations), the
item present throughout and named by no cause, `S4` and `S5` exactly dormant, `S5.T = S4.T`
exactly, `S4.T` 8.10e-7 K above PHF-1's `T` (inside §13's 1e-5 K). Its certificate is `FAILED` on
the PH flash's fresh-flash checks only: `energy_balance.U-PHF` and `energy_balance.envelope`
−1.3272e-3 W (τ_E 1.01e-3: 1.3 τ), `independent_split.U-PHF.S1.total` −9.087e-8 mol/s (τ 3.1e-8:
2.9 τ), `.A` −3.28e-8, `.B` −3.61e-8. Every residual, the label row (0.0) and the regularity
screen (34, `NO_RANK_LOSS_DETECTED`) pass. These are DZ-3's (B16) numbers to the digit — DZ-10
solves the same PHF-1 subsystem — and the same T04 F9 mechanism: Newton stops at its row
tolerances (the equilibrium rows at ~0.2 τ_eq), not at roundoff, and the fresh flash at that
temperature misses the stored split and duty by more than K04's tolerances. Not the zero-flow
form. `test_b26_dz10_verified` is `xfail(strict=True)`; `test_b26_dz10_what_the_certificate_fails_on`
pins the numbers.

### B29

- INJ-B4 (DZ-11's end state, with the `CONVERGED` claim of a region whose swapped-row test is
  disabled): `FAILED`, `false_success_detected`; failing, in order: `residual.U-HX:HX-energy-hot`
  −1 000.0 W, `energy_balance.U-HX.hot` −1 000.0 W, `energy_balance.envelope` −1 000.0 W;
  `residual.U-HX:zero-flow-label:hot` passes at 0.0. (The table names the exchanger's balances
  per side; spec B29's `energy_balance.U-HX` is `energy_balance.U-HX.hot` here.)
- INJ-B5 (DZ-9's root, `S3.T = 310 K`): `FAILED`; `residual.U-MIX:zero-flow-label` −20.0 K; every
  compiled residual exactly 0.0 (`ref…compiled_rows_max`); regularity `NO_RANK_LOSS_DETECTED`.

## 2026-09-25 — F9 W0: the K04-F9 rule measured on the implementation (spec §14 W0, Q2)

Commits `ae6c27d` (W1 `verify/projection.py`), `e8b6df0` (W2 wiring), `9912a67` (W3 D2),
`8fad720` (W4 D3), `91a0049` (W5 tests), `c9866d6` (W6 fixtures); measured at `c9866d6`. The
spec's *measured* section (`benchmarks/k04f9/reference_values.yaml` `measured`) was the prototype
around the verifier at `ddbe446`; every number below is the implementation's. **No difference
beyond ADR 0007's floors** (Q2 answered yes); two assertions could not be met as written (last
subsection).

### Inertness and identity (X17–X19)

- W1 (the projection computed nowhere yet, the screen moved before the check set) was proved inert:
  gate 2879 passed + 2 xfailed (2864 + 15 new), `k04_schema_fixtures.py` and
  `t04_schema_fixtures.py` byte-identical, K05 run-manifest artifact hashes equal to the base
  tree's (`solution-certificate.json` `bf76b9c8…` both).
- Protocol after each of W1–W6 (scratchpad `f9_protocol.sh`): `thermo/syn001.py` `75c9d5ba…`;
  K05 identity document `622463f5fbc8716f…` whole, `b364bb3d…` minus `t05`, `t05` key
  `ddbd0f71…`; structural `4ce030ca…`; `CheckPolicy().sha256` `21c44e10…`; T02 floats
  `9a8a5baf…`; `t05b_ph_baseline.py --check` matches; B07 passes. **Unchanged throughout.**
- W6 fixture diff (old → regenerated; X17): ids, results, `near_threshold` flags, statuses and
  limitation kinds unchanged in all three certificates; besides `transformations.projection` only
  fresh-flash values move — SYN-001 nominal `energy_balance.mixer` −3.6e-12 → −7.3e-12 W,
  `.heater` 0 → 3.6e-12 W; the trivial root's heater and flash balances −8237.850393069453 →
  −8237.850393068577 W (1.1e-13 relative: INJ-2 projects onto itself); HOM-01's S3 split and
  heater/flash balances from ≤ 5.6e-5 to ≤ 7.2e-7 of their tolerances.

### X00

`python docs/derivations/scripts/k04f9_reference.py --check` → `25 claims passed` (exit 0);
`--emit` twice → `73be8df910d13425273f1ef2ad87d4771e4e1c92e66bd128e69231b98a13e3b7` both, equal
to the committed YAML.

### The A02 family through `verify_bound` (X04, X25; `tests/test_k04f9_family.py`)

| Quantity | Implementation | Spec (prototype / twin) |
| --- | --- | --- |
| runs / converged | 180 / 179 | 180 / 179 |
| raw S3 classes at `x_final` | 155 clear, 9 near, 15 fail; worst 27.2797 (352 K from 360 K) | 155/9/15, 27.28 |
| verdicts | 179 `VERIFIED`, all `judged_at = projection` | 179 |
| worst S3 value at `x̃` | 2.0916e-5 (`independent_split.S3.total`, 352 K from 360 K) | 2.0916e-5 / 2.107e-5 |
| `near_threshold` flags | 29 on 15 states, all on residual rows | 29 / 15 |
| `‖F̂(x_final)‖∞` max; rows at `x̃` over tolerance max | 9.7046e-9; 3.0143e-7 | 9.705e-9; 3.0143e-7 |
| X25 worst agreement with the twin | 355 K from 320 K: 9.78e-7 against ref 7.08e-9 — 9.7 % of the 1e-5 allowance; every other state ≤ 4.6 % | — |
| A02-355 from 358 K (X05) | `VERIFIED`, no flag; largest S3 value at `x̃` 7.31e-7 (twin 2.82e-9; inside §7's double floor 2.2e-6) | no flag |
| A32 at 5e-4 W (X06) | `VERIFIED`; flash −2.5466e-10 W, envelope −7.276e-12 W | −2.5e-10, −7.3e-12 |
| wall time | 44.6 s alone; 52 s with A11's runs (now shared, `test_t04_edge3.family_run`) | — |

### T05b cases and the new states (X07–X15, X26; `tests/test_k04f9_t05b.py` and the T05b files)

| Case | Implementation | Spec *measured* |
| --- | --- | --- |
| DZ-3 | `VERIFIED` at `x̃`; worst fresh-flash ratio 2.22e-6 (`.closure`); energy 1.8e-12 W, split 9.8e-15 mol/s; flags PHF-equilibrium A/B/C 0.1729/0.1966/0.1189 τ_eq; dim 33, `rcond₁` 0.0130549; `b` 3.679e-8. At `x_final` (evidence): split −9.087e-8 mol/s, energy −1.3272e-3 W | as measured |
| DZ-10 | as DZ-3, dim 34 | as DZ-3 |
| NP-G | `VERIFIED`; `independent_split.U-PHF.S1` `not_applicable(fresh_flash_unresolved)`; closure 1.1e-6 of tolerance; U-PHF 1.8e-12 W, envelope 0.0; floor ratio within 1e-6 of the exact closed form (0.889558); PHF-duty flag 0.400; `b` 6.978e-8 | as measured |
| NP-3 | resolved (floor within 1e-6 of 0.0171216); worst value at `x̃` 2.391e-3 τ_flow (split total) | 2.391e-3 |
| NP-GC | `VERIFIED`; U-PHF 1.8e-12 W, U-SPLIT 0.0, envelope 3.6e-12 W; S4, S5 6.7e-9 mol/s from ref; dim 28, `rcond₁` 0.0089; `b` **1.212e-7** | ≤ 3.7e-12 W |
| PRJ-B2 | `VERIFIED`; `.saturation` 5.68e-14 K; balances −1.8e-12 W; VLV-energy row −4.000000008e-4 W (8e-13 W from ref), flagged | 5.68e-14 K |
| INJ-B2p | `VERIFIED`; `.saturation` 0.0; balance 3.6e-12 W | 3.6e-12 W |
| INJ-B2′ | `FAILED` at `x_final` (`residual_not_passed`); energy −57984.004 W, split total and B −1.9328 mol/s (≤ 4e-17 relative of ref); energy row −4.0000000008e-3 W; equilibrium B −7.2322e-8, passes (4.2e-10 relative) | as measured |
| INJ-F10 | `FAILED` at `x̃`; failing set exactly {flash, envelope}: −38338.06944674447 W (2.4e-14 relative), −38338.06944674354 W (3e-16); worst residual 8.7e-7 τ; `rcond₁` 1.8508e-3 | −38 338.069 446 744 W |
| `b` (X26) | SC-1…4, NP-1, NP-2, DZ-12 ≤ 2.6e-15; NP-3 3.84e-10; DZ-1, 2, 4–9 exactly 0; DZ-3/10 3.679e-8; NP-G 6.978e-8; NP-GC 1.212e-7 | ≤ 3.84e-10 others |
| X03 | every exact zero held; largest discarded step 3.7e-33 mol/s (SC-1), 0.0 on the DZ roots; fresh-flash ids equal the unprojected ids (INJ-2 keeps `.bubble`) | — |

### The suite's refusal log (scratchpad `f9_w0_plugin.py` around `certificate.project`; full suite at `c9866d6`)

394 projections computed: 377 `projection`, 17 `final_state`/`residual_not_passed` (K04
injections 6, T04 A32 ±2e-3 2, `test_t05_w12_injections` 3, W1.d `x⁰` 1, T05b INJ-B1, INJ-B3, INJ-B4,
INJ-B5, INJ-B2′), **0 other refusals**. Largest discarded exact-zero step 2.87e-22 mol/s (spec
2.87e-22); rows at `x̃` ≤ 4.50e-6 of their tolerances (K04 A16's relaxed-policy twin; spec 4.5e-6).

### Could not be met as written (stop-and-report, `xfail(strict=True)`)

- **X26 at NP-GC**: `b = 1.212e-7 > 1e-7` (§10.6's rule); NP-GC has a registered state comparison
  (X11), and its S4/S5 lie 6.7e-9 mol/s from ref, 46× inside the 3.1e-7 allowance the rule
  protects. `tests/test_k04f9_t05b.py`.
- **X21 at NP-1**: the floor ratio from binary64 band ends is 171130.3 against the exact 171213
  (4.8e-4 relative) — a 2.14e-11 K band is 377 doubles wide at 360 K, a quantization §7's argument
  (2 ulp(T)/w ≤ 2.8e-8, NP-G's) does not cover. NP-1 is degenerate (D7 precedence), so its floor
  decides nothing; every route, all 51 entries, is as registered. `tests/test_k04f9_rules.py`.
- Not a failure, recorded: the registered floor ratios are printed to six digits, which alone
  departs from the closed form by up to 4.2e-6 relative (SYN-001-UL-C3:S4); X21 therefore compares
  with the closed form of the registered 20-digit `T`, `N`, `T_b`, `T_d` (and checks the printed
  digits as that value rounded).

### Gate

`./scripts/check.sh` at `c9866d6`: ruff, format, mypy clean; **2992 passed, 2 xfailed** (the two
above; B16's and B26's strict xfails retired), 157 s.

---

## 2026-09-25 — W8: limitation texts, T05's retired A28–A30, the `t05b` identity key, W0.7, W0.9

Base `385fdc9` (F9 merged). Protocol at the base (scratchpad `w8_protocol.sh`): `thermo/syn001.py`
`75c9d5ba…`; K05 identity document `622463f5fbc8716f…` (minus `t05` `b364bb3dc881402f…`, `t05`
key `ddbd0f7135ee5310…`); structural `4ce030ca…`; `CheckPolicy().sha256` `21c44e10…`; T02 floats
`9a8a5baf…`; `t05b_ph_baseline.py --check` matches. After the manifest texts (`d0fe494`) and the
generator's retirement (`3771502`): identical (manifests are not in the label, R-047).

### B22 — the `t05b` key (`scripts/t05b_identity.py`, `tests/test_t05b_identity.py`)

`python scripts/k05_structural_identity.py --out identity.json` with the `t05b` key:

| Digest (hash convention of `f9_protocol.sh`) | Value |
| --- | --- |
| whole document (`sha256sum identity.json`) | `1b4f44f5acbee5942b9858af17c52466bade5414424bdc6f2283da3c56e58314` |
| minus `t05b` | `622463f5fbc8716f…` — the base's whole document, unchanged |
| minus `t05`, `t05b` | `b364bb3dc881402f…` — T05's W0.1 and spec B21's, unchanged |
| `t05` key (`json.dumps(sort_keys=True)`) | `ddbd0f7135ee5310…`, unchanged (B30 (d)) |
| `t05b` key (same convention) | `b1b4f6c8e8db7a9c4cb490c360f44fc46d0541c5ca611f2915bb5cef9bf58276` |
| `structural_sha256` | `4ce030ca…`, unchanged |

The key carries, under `T05b-v2`: the full R0 projection (plan R0, outcome, events, solver
counters, structural report, certificate, fingerprint through T03's projection, typed message
line) of SC-1…SC-4, NP-1…NP-3, DZ-1…DZ-10 and DZ-12 — every one `CONVERGED`, `VERIFIED`,
`NO_RANK_LOSS_DETECTED`, message `""`; DZ-11 and DZ-2C as `SPECIFICATION_CONFLICT` with
`zero_flow_conflict(U-HX:HX-energy-hot)` / `zero_flow_conflict(U-PHF:PHF-duty)`; NP-G's outcome
`CONVERGED` only. DZ-3, DZ-10, DZ-11, DZ-2C and DZ-12 start from their registered `ref` starts
(the region solve with a trace; the certificate on the region's final state). Floats-free; the
only 64-hex strings sit under `constants_sha256`, `model_version` and `variable_ids_sha256`
(declared inputs); the same twice in one process; 1.7 s for the whole key.

Near-threshold flags carried in the key's certificates (ADR 0007 D2.4 band `[τ/10, 10τ]`): NP-2
one (the degenerate `.saturation` check, `δ = 1.59e-7 K` against `τ_T = 1e-6 K`, 0.159 τ); DZ-3
and DZ-10 three each (`PHF-equilibrium` A/B/C at 0.173/0.197/0.119 τ_eq, K04-F9 X07/X08); every
other case none. B22 lists these cases for the full projection; the flags are R0 fields of the
projection, so the CI pair compares them exactly — the smallest margin to the band's edge is DZ-3's
and DZ-10's `PHF-equilibrium:C`, 0.119 against 0.1.

### W0.7 — F9's band on the implementation (spec §20, Q5; after ADR 0013)

At `cd44057` (no `src/` logic change since `385fdc9`), scratchpad `w8_w07.py`: NP-G, and NP-G's
flowsheet (feed 300 K, `P_r`, liquid → `U-PHF`, `Q = 30 000 W`, `φ = 0.3`) with `(0, 2, ε)` (heavy
trace C) and `(ε, 2, 0)` (light trace A), `ε` from `3e-8` to `1e-6` as the spec asks and three
points beyond to find the resolved side; each through `plan_revision` → `execute_plan` →
`verify_revision` under `T05b-v2`. Route is ADR 0013 D3's `split_route` of `U-PHF` at the
verifier's projection (`degenerate` → the stored split, spec §9.1; `unresolved` → the independent
split `not_applicable(fresh_flash_unresolved)`; `resolved` → the fresh flash's own checks);
floor = `N ulp(T) / (w τ_flow)`, unresolved at `≥ 0.1`. "duty flag": `residual.U-PHF:PHF-duty`
near threshold (D2.4 band), never failing.

| trace (mol/s) | heavy C: route, floor/τ_flow, band, verdict, b | light A: same |
| --- | --- | --- |
| 3e-08 | degenerate, 4.45, 8.25e-07 K, `VERIFIED`, b 5.61e-08, duty flag | degenerate, 5.71, 6.43e-07 K, `VERIFIED`, b 1.07e-07, duty flag |
| 5e-08 | unresolved, 2.67, 1.37e-06 K, `VERIFIED`, b 8.67e-08, duty flag | degenerate, 3.42, 1.07e-06 K, `VERIFIED`, b 1.07e-15 |
| 7e-08 | unresolved, 1.91, 1.92e-06 K, `VERIFIED`, b 1.49e-15 | degenerate, 2.45, 1.5e-06 K, `VERIFIED`, b 8.73e-08, duty flag |
| 1e-07 | unresolved, 1.33, 2.75e-06 K, `VERIFIED`, b 9.85e-08, duty flag | unresolved, 1.71, 2.14e-06 K, `VERIFIED`, b 1.02e-07, duty flag |
| 1.5e-07 | unresolved, 0.89, 4.12e-06 K, `VERIFIED`, b 6.98e-08, duty flag | unresolved, 1.14, 3.21e-06 K, `VERIFIED`, b 2.91e-08, duty flag |
| 2e-07 | unresolved, 0.667, 5.5e-06 K, `VERIFIED`, b 4.3e-10 | unresolved, 0.856, 4.28e-06 K, `VERIFIED`, b 5.67e-08, duty flag |
| 3e-07 | unresolved, 0.445, 8.25e-06 K, `VERIFIED`, b 6.47e-08, duty flag | unresolved, 0.571, 6.43e-06 K, `VERIFIED`, b 1.9e-08, duty flag |
| 4e-07 | unresolved, 0.334, 1.1e-05 K, `VERIFIED`, b 4.79e-08, duty flag | unresolved, 0.428, 8.57e-06 K, `VERIFIED`, b 3.48e-08, duty flag |
| 5e-07 | unresolved, 0.267, 1.37e-05 K, `VERIFIED`, b 1.52e-09 | unresolved, 0.342, 1.07e-05 K, `VERIFIED`, b 1.93e-08, duty flag |
| 7e-07 | unresolved, 0.191, 1.92e-05 K, `VERIFIED`, b 2.82e-09 | unresolved, 0.245, 1.5e-05 K, `VERIFIED`, b 1.19e-08 |
| 1e-06 | unresolved, 0.133, 2.75e-05 K, `VERIFIED`, b 1.7e-08 | unresolved, 0.171, 2.14e-05 K, `VERIFIED`, b 4.86e-09 |
| 1.5e-06 | resolved, 0.089, 4.12e-05 K, `VERIFIED`, b 8.67e-11 | unresolved, 0.114, 3.21e-05 K, `VERIFIED`, b 5.71e-09 |
| 2e-06 | resolved, 0.0667, 5.5e-05 K, `VERIFIED`, b 8.89e-10 | resolved, 0.0856, 4.28e-05 K, `VERIFIED`, b 1.88e-09 |
| 3e-06 | resolved, 0.0445, 8.25e-05 K, `VERIFIED`, b 4.52e-09 | resolved, 0.0571, 6.43e-05 K, `VERIFIED`, b 2.08e-09 |

NP-G (= heavy C `1.5e-7`): `CONVERGED`, `VERIFIED` at the projection, unresolved (floor 0.8896),
`b` 6.978e-8, duty flag. **Every one of the 29 solves is `CONVERGED` in one attempt and `VERIFIED`
with no failing check** — the spec's emulated `FAILED` band (T04 F9's mechanism, §17) no longer
exists on the implementation after ADR 0013. On the implementation F9's former band is D3's
unresolved band: heavy trace `5e-8 … ~1.3e-6` mol/s, light trace `1e-7 … ~1.7e-6` mol/s (floor ∝
1/ε crossing 0.1), below it the degenerate window (heavy ≤ 3e-8, light ≤ 7e-8). The spec's Q5
default (the band ending near 4e-7 mol/s, emulated for the fresh flash's `FAILED` verdicts) is
superseded by these ends of the unresolved routing.

Recorded, not a rule departure (the sweep states have no registered state comparison, so §10.6's
`b ≤ 1e-7` does not govern them): `b` reaches 1.07e-7 (light A `3e-8`) and 1.02e-7 (light A
`1e-7`), above 1e-7, and 9.85e-8 (heavy C `1e-7`) — the same order as NP-GC's 1.212e-7 (F9 W0's
stop-and-report). These states stop at their row tolerance (the duty flag), as NP-G does.

### W0.9 — K04's recorded solution-error bound on every T05b EO case (rule: K04-F9 §10.6, X26)

At `cd44057`, scratchpad `w8_w09.py` (the certificates `tests/test_k04f9_t05b.py` X26 reads):

| Case | `b` | Rule `b ≤ 1e-7` (cases with a registered state comparison) |
| --- | --- | --- |
| SC-1, SC-2, SC-3, SC-4 | 8.568e-16, 0.0, 2.563e-15, 1.051e-15 | meet |
| NP-1, NP-2, NP-3 | 2.130e-16, 1.306e-15, 3.840e-10 | meet |
| NP-G | 6.978e-8 | not governed (no state comparison registered); below 1e-7 |
| DZ-1, DZ-2, DZ-4…DZ-9 | 0.0 each | meet |
| DZ-3, DZ-10 | 3.679e-8 each | meet |
| DZ-12 | 3.255e-15 | meet |
| NP-GC (K04-F9's case, X11/X26) | **1.212e-7** | **outside** — F9 W0's stop-and-report, unchanged (strict xfail in `test_k04f9_t05b.py`) |

Every T05b EO case meets the amended rule; the one case outside it is K04-F9's NP-GC, already with
the design lane. All 20 certificates `VERIFIED`. No rule was changed.

### B30 (d) — a check-id baseline for the T05b cases

No baseline existed before W8 (W7b's note). Pinned now: `tests/fixtures/t05b/check_ids.json`,
emitted from the `t05b` key (scratchpad `w8_check_ids.py`) — each of the 18 full-projection cases'
certificate check ids in certificate order, 1 330 ids in all; a self-generated regression
baseline. `tests/test_t05b_identity.py::test_b30d_…` compares the live key with it. T05's
registered cases stay covered by the `t05` key (`ddbd0f71…`, unchanged) and SYN-001's by the
document minus `t05`, `t05b` (`b364bb3d…`, unchanged).

## CI pair at `85d4c96` (T05b W0–W8 + F9)

`check (ubuntu-latest)`, `check (ubuntu-24.04-arm)`, `identity`: success; `structural_sha256`
`4ce030ca…` on both; the identity comparator (every key, `t05b` with its near-threshold flags
included) equal across platforms. The run before (`e4e4990`) failed on aarch64 only: X26 pinned
DZ-12's roundoff-set bound (3.255e-15 x86-64 vs 3.309e-15 aarch64) to 1e-3 relative; the test now
pins only truncation-set bounds and holds roundoff-set ones below 1e-12 (`85d4c96`).

## 2026-09-25 — W9.1: the ruling round's test-only re-registrations (base `51201d2`)

### X26 as amended (Q-S1, R-063; `tests/test_k04f9_t05b.py`)

The realized deviation of each registered comparison over its allowance (T02 §6.4: `3.1e-7 mol/s`,
`1e-5 K`, `0.1 Pa`, `1e-2 W`), the largest per case, and `b` (recorded, never thresholded).
Scratchpad `w9a_x26_ratios.py`:

| Case | Ratio | At | `b` |
| --- | --- | --- | --- |
| SC-1 | 2.37e-10 | `S2.liq.B` | 8.568e-16 |
| SC-2 | 0.0 | — | 0.0 |
| SC-3 | 2.37e-10 | `S2.liq.B` | 2.563e-15 |
| SC-4 | 1.52e-9 | `S6.T` | 1.051e-15 |
| NP-1 | 1.96e-9 | `S3.T` | 2.130e-16 |
| NP-2 | 1.56e-9 | `S3.T` | 1.306e-15 |
| NP-3 | 2.39e-4 | `S3.n.B` | 3.840e-10 |
| DZ-3 | **0.0810** | `S4.T` | 3.679e-8 |
| DZ-10 | **0.0810** | `S4.T` | 3.679e-8 |
| DZ-12 | 2.43e-8 | `S4.T` | 3.255e-15 |
| NP-GC | **0.0217** | `S5.n.B` | 1.212e-7 |

Every ratio `≤ 1/10`; NP-GC's strict xfail, `B_ALLOWANCE` and the NP-G companion test are gone.
NP-G's `b` (6.978e-8) stays recorded only. B31 (b)–(c) join the population with W9.3.

### X21 as amended (Q-S2; `tests/test_k04f9_rules.py`)

Tolerance `max(1e-6, 4 ulp(T)/w)` against the closed form of `ref`'s 20-digit fields; the printed
six digits checked as that closed form rounded half-even. All 51 entries pass, no xfail. NP-1:
tolerance 1.0615e-2, relative error **4.85e-4** (22× inside). Every other entry with `w > 0`:
≤ 1.34e-8.

### B24's mixer-first DZ-9, B29's `.cold`, X02's extent

- DZ-9 declared mixer first under `T05b-v2`: `CONVERGED` at iteration 0, `VERIFIED`, dimension 15,
  `S3.T == 330.0`; the plan eliminates exactly `U-FEED-1:FEED-P` (the second feed's, *regression*);
  the attempt's rows are `ref…zero_flow_form`'s with `U-MIX:MIX-pressure:1` restored, minus it.
  (B24's "rows equal to `ref…zero_flow_form` minus the plan's `eliminated_rows`" read so: `ref`'s
  list is already the feeds-first form minus `MIX-pressure:1`, and dimension 15 fixes the reading.)
- INJ-B4: `energy_balance.U-HX.cold` passes; the failing set as before.
- X02: an extent `U-RX.xi` (kind `molar_flow`) stepping from `1e-9` to `−1e-8` at `x̃` is issued
  at the projection; a mutant treating it as a stream flow is killed.

### Q-S7 — the K05 `run_manifest` fixture

Regenerated by `scripts/k05_schema_fixtures.py --write` in its own commit (`7f1b006`); only
`run_manifest/valid/syn001_nominal.json` differed. Certificate hash `f0206d1f…` → `8fba5cf9…`; file
`92bf411d…` → `bc6bb8ce…`; `manifest_sha256`, `started_at`, `elapsed_seconds` moved as provenance.
`tests/test_k05_schemas.py::test_the_manifest_fixtures_certificate_hash_is_the_emitted_one`
passes; it fails on a one-byte edit of the fixture's certificate hash and on the pre-regeneration
fixture (scratchpad `w9a_qs7_mutant.py`). **Scope (build-lane DECISION):** exact where the running
platform (`Environment.identity()`: architecture, OS, Python, BLAS vendor) is the fixture's; on
another platform the test skips with that reason, because ADR 0007 Context 2 measured converged
floats one to three ulps apart between x86-64 and aarch64 and blueprint §8.3 promises no bitwise
float equality across platforms. So the aarch64 CI runner skips it.

## 2026-09-25 — W9.2: the screen at an empty signature (Q-S4 (6))

- First form (the core's predicate compared an empty frozen signature everywhere): not inert —
  4 K03 tear tests failed (`test_k03_tear.py`, 84 trials `()` vs the flash's signature), because
  those tests call `solve_newton` with the default `signature=()` meaning "no frozen signature".
- Final form: `newton.another_signature(frozen, reported, compare_empty=…)`; the region passes
  `compare_empty=bool(dormancy)` to its Newton, PTC and homotopy-corrector calls. Probe (scratchpad
  `w9a_sig_plugin.py`, whole suite): trials where the new predicate differs from the old one —
  **0** in every pre-existing test; all 106 in `tests/test_t05b_empty_signature.py`. Suite 3034
  passed. Protocol identical to base (`t05b` `b1b4f6c8…`, `t05` `ddbd0f71…`, whole `1b4f44f5…`,
  minus `t05b` `622463f5…`, minus both `b364bb3d…`, structural `4ce030ca…`, `CheckPolicy`
  `21c44e10…`, T02 floats `9a8a5baf…`, `ph_state` baseline matches).
- (a) Newton and PTC stubs: `phase_update_required` at an empty frozen signature with
  `compare_empty`; without it, the full step is taken as before. (b) The flowing-pump region's
  trial evaluation at `S1.n = +0.0` reports `((U-PUMP.outlet, ZERO_FLOW),)`, at a flowing trial `()`.
- End to end, DZ-6 from its root with `S1.n = S2.n = (1,1,1)`: attempt 0 (`()`, 2 iterations)
  closes `phase_wall(patience, U-PUMP.outlet:LIQUID->ZERO_FLOW)`, attempt 1 runs the form,
  `CONVERGED`, `S2.T == 330.0`. Before W9.2 (keyword forced off, *measured*): attempt 0 converged
  in 1 iteration in the declared form and the closure's agreement restarted it,
  `inadmissible(S2, dormant)`.

## 2026-09-25 — W9.3: the opening fixed point (Q-S9, review M1/N1; spec §7.8 (ii), B31)

- Before (at `906ef0a`, scratchpad `w9a_ch_probe.py`): CH-UP, CH-DZ12, CH-3, CH-UP/PHF2-first
  raised `RuntimeError: defect: U-PHF2 opens attempt 1 in ZERO_FLOW with its feed flowing`;
  CH-DOWN and CH-DOWN/PHF2-first `… in VAPOR with its feed dormant`; CH-DORMANT/PHF2-first
  `… opens attempt 0 in VAPOR with its feed dormant`. CH-DORMANT (declared first) converged.
- After: every case typed and `CONVERGED`. CH-UP, CH-DZ12, CH-3: 2 attempts, the second opened
  `…; fallback(U-PHF2, tp)` (CH-3: `fallback(U-PHF3, tp), fallback(U-PHF2, tp)`), the downstream
  flashes `VAPOR` (*regression*); realized deviation from the closed form 2.43e-8 of the allowance
  (at `S4.T`). CH-DOWN: `phase_disappeared(U-PHF, vapor, S2.n.C)` then `LIQUID`/`ZERO_FLOW`,
  `VERIFIED`, ratio 0.0. CH-DORMANT (both orders): one attempt, 1 iteration, `VERIFIED`, records
  `projected(S1, two_phase, ZERO_FLOW)`, `projected(S2, all_vapor, ZERO_FLOW)`. Order variants
  equal their declared-first cases (outcome, verdict, final regimes, state within allowances).
- **B31 (b)'s `VERIFIED` not met — strict xfail, reported.** CH-UP, CH-DZ12, CH-3 certify
  `UNVERIFIED`, regularity `RANK_DEFICIENT`: the closed-form root puts each `Q = 0`, `ΔP = 0` flash
  fed a saturated vapour exactly on its dew point (`L = 0`, `Σ y/K = 1`), where the declared
  lifted form is singular (the equilibrium rows admit `δl_i = y_i/K_i δL`, balanced by `δT` in the
  energy row). CH-UP: rank 30 of 31, σ_min 8.1e-17, right null vector on `S4.T`, `S5.T` and the
  `v→l` transfer, left null vector on `U-PHF2:PHF-equilibrium:{A,B,C}`; CH-DZ12 the same at
  `U-PHF2` (σ_min 7.3e-18); CH-3 rank loss 2 (`U-PHF2`, `U-PHF3`). No check fails; `b` 17.3 / 22.5 /
  33.7 (recorded only).
- Inertness (scratchpad `w9a_settle_plugin.py`, whole suite before the new tests): 181 openings
  through `_settle`; each equals the pre-W9.3 opening (attempt 0: unchanged; restart: the old
  at-most-once reset, no regime change) except in B27's negative control, which disables the reset
  by design. Gate 3068 passed + 3 xfailed. Protocol identical to base (`t05b` `b1b4f6c8…`, `t05`
  `ddbd0f71…`, whole `1b4f44f5…`, minus `t05b` `622463f5…`, minus both `b364bb3d…`, structural
  `4ce030ca…`, `CheckPolicy` `21c44e10…`, T02 floats `9a8a5baf…`, `ph_state` baseline matches);
  B07, B21, B30 pass unchanged.

## 2026-09-25 — W9.4: both product temperatures at openings (Q-S11 (a); spec §6.2 step 3, B33 (a))

- Change: a PH closure's answer sets every temperature column of the split's streams
  (`splits.split_temperatures`: heater style the outlet's; products style the vapour product's,
  then the liquid product's) to the closure's `T`. Before (mutant with the old vapour-only
  answer, scratchpad `w9b_mut4_plugin.py`): the liquid product kept the trial's value at every
  such opening — SC-3 `365.08 K` against the closure's `360 K`; DZ-12, CH-UP, CH-DZ12, CH-3,
  CH-UP/PHF2-first `400 K` against `352.0050359821734 K`. After: equal bitwise in all six
  (`tests/test_t05b_near_pure_restarts.py`, B33 (a)); the mutant fails all six.
- What moved: SC-3's attempt 1 now opens at KS-1's root and closes at iteration 0 (was 1):
  `SC3_ITERATIONS` `(2, 1) → (2, 0)`; its key entry loses the attempt-1 Jacobian, linear solve
  and accepted step (21 → 18 events; counters `jacobian_calls` 3 → 2, `factorizations` 3 → 2,
  `residual_calls` 9 → 8). DZ-12's opening moved (`S3.T` 400 K → 352.005 K) but its key entry
  did not: attempt 1 still converges in one iteration, and the key is floats-free. Review S3's
  P2 (`test_s3_p2_leaving_zero_flow_the_root_and_certificate`): `S4.n.B` moved by one ulp
  (`0.14524811561710257 → …255`) from `S2.n.B`; its bitwise comparison became the allowance
  comparison `S4.T` already had. Every other test unchanged.
- **The `t05b` key, re-registered (reason: Q-S11 (a), SC-3's attempt-1 records):** key
  `4f29500e31139133cd2304d848390665ec9c298d55a2a952321df3da11e89c54` (was `b1b4f6c8…`); whole
  document `91fac60822ddcebe1a34205fbfca54ab391dba833ef9b2e91671c4efba5cdf06` (was `1b4f44f5…`);
  minus `t05b` `622463f5…` and minus `t05`, `t05b` `b364bb3d…` (unchanged); `t05` `ddbd0f71…`,
  structural `4ce030ca…`, `CheckPolicy` `21c44e10…`, T02 floats `9a8a5baf…`, SYN-001 identity
  `75c9d5ba…` unchanged; `ph_state` baseline matches. The CI pair is not re-run here.
- Gate: 3074 passed + 3 xfailed (3068 + 6 new).

## 2026-09-25 — W9.5: K03 §5.3's structural-zero release (Q-S11 (b), R-064; B33 (b)–(d))

- Change: `newton._bound_aware_step` — when `α_max = 0`, the largest released set `Z*`
  (`newton._released`: components on their bound at the opening and the iterate, closed rows
  `F == 0.0` exactly with every nonzero entry in the set, counted by a maximum matching and
  re-checked) gets `d := 0` and `α_max` is recomputed; a blocker outside `Z*` still blocks with
  the original `blocked_by`. The Newton core only (the PTC core keeps `_bound_aware_alpha`).
- Inertness (scratchpad `w9b_release_plugin.py`, whole suite before the new tests): 235 calls
  (every `α_max = 0` in the suite's Newton attempts); 233 release nothing (bitwise the old
  path); **2 act, both the one case B33 (d) names**: SC-2 under `T05-W13` and T05 A30's P4 (the
  same revision), `Z*` = 4 columns, `α_max` 0 → 1. Protocol identical to W9.4 (SYN-001
  `75c9d5ba…`, whole identity `91fac608…`, minus `t05b` `622463f5…`, minus both `b364bb3d…`,
  `t05` `ddbd0f71…`, `t05b` `4f29500e…`, structural `4ce030ca…`, `CheckPolicy` `21c44e10…`, T02
  floats `9a8a5baf…`, `ph_state` baseline matches); K03 BND-01/BND-02, T02's nominal
  `BOUND_BLOCKED` on `S3.vap.B`, T03 PHS-04 unchanged (gate).
- **SC-2's v1 outcome (B33 (d)):** `BOUND_BLOCKED` → **`ACTIVE_SET_CYCLING`** (`VAPOR` attempt
  now 2 iterations, `PHASE_UPDATE_REQUIRED`, then `active_set_cycling(U-PHF:LIQUID;
  phase_wall(patience, U-PHF:VAPOR->LIQUID))`); no certificate, **not `VERIFIED`**. T05 A30's P4
  moves the same way. Both regression pins re-registered with this reason; T05's evidence at
  `91ac010` keeps the old value for its commit.
- B33 (b), NP from the liquid-form start (region solve, `solve_from_v2`; region-side provider
  calls counted as review P5, the compiled residual's excluded):

  | case | W9.4 alone (release off) | W9.5 | attempts' iterations | region-side calls | `ph_state` calls |
  | --- | --- | --- | --- | --- | --- |
  | NP-1 | `CONVERGED` `VERIFIED` | `CONVERGED` `VERIFIED` | 2, 1 | 12 598 | 4 |
  | NP-2 | `BOUND_BLOCKED` (iteration 0) | `CONVERGED` `VERIFIED` | 2, 1 | 15 534 (18 588 before) | 5 |
  | NP-3 | `CONVERGED` `VERIFIED` | `CONVERGED` `VERIFIED` | 2, 2 | 569 | 4 |
  | NP-G | `CONVERGED` `VERIFIED` | `CONVERGED` `VERIFIED` | 2, 1 | 543 | 4 |

  NP-2 releases `Z*` of 3 columns (absent A). Attempt 1 opens
  `phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE)[; fallback(U-PHF, ph-band)])`, the
  band item at NP-1 and NP-2. `|T − ref|`: NP-1 1.7e-12 K, NP-2 4.6e-8 K, NP-3 2.4e-12 K, NP-G
  4.6e-8 K (allowance 1e-5 K). NP-1 still spends 12 598 region-side calls (W9.6's subject).
- Gate: 3082 passed + 3 xfailed.

## 2026-09-25 — W9.6: the screen by band-end enthalpies (Q-S10, R-053; spec §6.2, B32)

- Change: a flagged PH-type trial's regime comes from `region._band_regime` — (s1) the target
  outside `[Ḣ_TP(T_min), Ḣ_TP(T_max)]` gives the TP flash's regime; (s2) `H_split` against
  `H_0 = Ḣ^L(n, T(0))`, `H_1 = Ḣ^V(n, T(1))` with a `τ_E` margin; (s3) otherwise the full closure,
  kept per attempt by exact inputs (`ClosureMemo`) and reused by an opening at the same state.
  The candidate check accepts a differing regime only when the PH closure refused and its TP
  fallback (`tp`) answered (the sanctioned difference).
- Inertness (scratchpad `w9b_band_plugin.py`, whole suite): 85 flagged PH-type trials, every one
  (s2) `TWO_PHASE` equal to `ph_state`'s answer at the same `(n, P, H)`; no (s1), no (s3), no
  sanctioned difference. Protocol identical to W9.5 (whole identity `91fac608…`, `t05b`
  `4f29500e…`, minus `t05b` `622463f5…`, minus both `b364bb3d…`, `t05` `ddbd0f71…`, structural
  `4ce030ca…`, `CheckPolicy` `21c44e10…`, T02 floats `9a8a5baf…`, SYN-001 `75c9d5ba…`, `ph_state`
  baseline matches); B07 and SC-3's records unchanged (gate).
- B32 (a) (`tests/test_t05b_band_screen.py`): KS-1, KS-2 by (s2) `TWO_PHASE`, KS-3 by (s1) (TP
  `LIQUID`, `fallback(U-VLV, tp)`), each equal to the contract kernel's; on all eight §12.1
  compositions × 15 points the regime equals `ph_state`'s, (s1) exactly at the two domain-end
  points (`ph_outside_domain`), (s3) exactly at the four `± τ_E/2` points.
- Provider calls, NP from the liquid-form start (B32 (b); `ph_state` calls in brackets):

  | case | region-side, before (W9.5) | region-side, after | `execute_plan` metered, before | after |
  | --- | --- | --- | --- | --- |
  | NP-1 | 12 598 (4) | 3 369 (1) | `BUDGET_EXHAUSTED` (9 610 metered; 9 967 region-side) | `CONVERGED`, 3 419 |
  | NP-2 | 15 534 (5) | 3 511 (1) | `BUDGET_EXHAUSTED` (10 000; 9 966) | `CONVERGED`, 3 565 |
  | NP-3 | 569 (4) | 485 (1) | `CONVERGED`, 631 | `CONVERGED`, 547 |
  | NP-G | 543 (4) | 480 (1) | `CONVERGED`, 593 | `CONVERGED`, 530 |

  Region-side: `solve_from_v2` with the region's provider wrapped (review P5's method, the
  compiled residual excluded); metered: `PlanResult.counters.property_calls` under the default
  `max_property_calls = 10 000`. The one `ph_state` left is the restart opening's.
- Gate: 3099 passed + 3 xfailed.

## 2026-09-25 — W10: the Q-S9 addendum and the re-review's changes (Q-S12…Q-S14; B31, B34–B36)

- Protocol after every commit (W10.1–W10.5), identical to W9.6: SYN-001 `75c9d5ba…`, K05 whole
  `91fac608…`, minus `t05b` `622463f5…`, minus both `b364bb3d…`, `t05` `ddbd0f71…`, `t05b`
  `4f29500e…`, structural `4ce030ca…`, `CheckPolicy` `21c44e10…`, T02 floats `9a8a5baf…`,
  `ph_state` baseline matches.
- W10.1 (test-only). B31 (b)'s verdict: CH-UP, CH-DZ12, CH-3, CH-UP/PHF2-first `UNVERIFIED`,
  `RANK_DEFICIENT`, rank loss 1, 1, 2, 1, no check `fail`/`unsupported`. B31 (i): CH-UP-DP,
  CH-DZ12-DP, CH-3-DP `CONVERGED`, `VERIFIED`, `NO_RANK_LOSS_DETECTED`, (b)'s attempt records,
  iterations `[2, 1]` each, downstream flashes `VAPOR`; `S4.P = S5.P = 90 000` (CH-3-DP
  `S6.P = S7.P = 80 000`; CH-DZ12-DP `S7.P = S8.P = 90 000`); largest closed-form ratio 1.87e-8
  (`S4.T`, i.e. 1.9e-13 K). The `t05b` twin pin `7870bbc9…` → `cf1a8606…` (the claim count is the
  only existing line of the re-emission that moved).
- W10.2 (B34, option A). The sweep: 120 runs, 16 starts refused (`duty_into_dormant_stream` at
  `U-PHF2`), 104 solved in ~5 s, none raises, both orders agree; 80 `CONVERGED`, 12
  `ACTIVE_SET_CYCLING`, 6 `SPECIFICATION_CONFLICT`, 4 `STAGNATION`, 2 `BOUND_BLOCKED` (the design
  lane's figures). With the pre-ruling `region.py` the sweep raises P11's `RuntimeError`.
- W10.3 (B35). Census (whole suite, 3119 tests, scratchpad `w10_b35_census.py`): 424 homotopy
  corrector calls, 99 reached `_released` (`α_max = 0`), 0 non-empty with either the call's start
  or the attempt's `x⁰`, 0 differing.
- W10.4 (B36). The leaving flash at CH-UP's opening: `(S2.n, S2.T = 352.00504 K, S4.P)` →
  `VAPOR`; at the split's own 300 K → `LIQUID` (the control). What moved, before → after:

  | record | before | after |
  | --- | --- | --- |
  | B31 attempt-1 iterations, CH-UP, CH-3, CH-UP/PHF2-first, CH-UP-DP, CH-3-DP | 1 | 0 |
  | B31 attempt-1 iterations, CH-DZ12, CH-DZ12-DP | 1 | 1 |
  | B31 largest closed-form ratio (all leaving cases but DZ12's) | 1.87e-8 (`S4.T`) | 8.19e-9 (`S3.N`) |
  | B34 sweep `(Q2, Q_s, Q_t) = (0, 0, 115 000)`, both orders | `ACTIVE_SET_CYCLING` (4 attempts) | `CONVERGED` (3 attempts) |
  | B34 sweep `(0, 0, 90 000)`, both orders | `CONVERGED`, 3 attempts (2, 2, 7) | `CONVERGED`, 2 attempts (2, 5) |
  | B34 sweep `(0, 0, 125 000)`, both orders | `CONVERGED` (2, 2, 2) | `CONVERGED` (2, 1, 3) |
  | B34 counts | 80/12/6/4/2 | 82/10/6/4/2 |

  Outcomes, signatures, reasons and messages of B31 unchanged. The B34 moves are outside B36 (c)'s
  list: stop-and-report (strict xfail on the registered counts, the measured counts pinned).
  Gate: 3126 passed + 1 xfailed.
- W10.5. `syn001.ph_flash` states §16's dew-point sentence; A01 re-run: ok, no departures.

## 2026-09-25 — W10 (6): Q-S15's changes (B34 (a) re-registered, B36 (c) completed and (d))

- Protocol after every commit (W10.6a–c), identical to W10: SYN-001 `75c9d5ba…`, K05 whole
  `91fac608…`, minus `t05b` `622463f5…`, minus both `b364bb3d…`, `t05` `ddbd0f71…`, `t05b`
  `4f29500e…`, structural `4ce030ca…`, `CheckPolicy` `21c44e10…`, T02 floats `9a8a5baf…`,
  `ph_state` baseline matches, B07 passes.
- W10.6a (test-only). B34 (a)'s counts pinned as re-registered, 82/10/6/4/2 (the strict xfail
  and its "as measured" twin removed). B36 (c)'s list, completed by Q-S15 (1): the B34 sweep's
  leaving runs (`Q2 = 0`, `Q_s = 0`, both orders, 8 runs) as tabled under W10.4. The certificate
  tally over the 82 `CONVERGED` runs: 66 `VERIFIED`, 10 `UNVERIFIED` (6 `RANK_DEFICIENT`,
  4 `ILL_CONDITIONED`), 6 `FAILED` = `(0, {90, 115, 125} kW, 30 kW)` × both orders, each
  `false_success_detected`; the non-`VERIFIED` set is exactly `Q2 = 0`, `Q_t` ∈ {30, 90} kW;
  both orders agree on every verification status.
- W10.6b (B36 (d)). The screen's leaving report of a PH-type split at its feed's `T`
  (`temperature_id(split.stream)`); `at_candidate`'s `tp` exemption excludes an attempt regime
  `ZERO_FLOW`. (i) At B36 (a)'s state as a trial (`U-PHF` `TWO_PHASE`, `U-PHF2` `ZERO_FLOW`,
  `S4.T = S5.T = 300 K`): reported `U-PHF2` `VAPOR` = the leaving answer; the pre-ruling reading
  (own `T`) `LIQUID`. (ii) Reported regime stubbed `LIQUID`: `RuntimeError` "defect: the kernel
  reports U-PHF2 VAPOR at the candidate the screen reported LIQUID"; reported `VAPOR` opens
  `VAPOR` with `fallback(U-PHF2, tp)`. With the pre-change `region.py` both (i) and (ii) fail.
  (iii) Protocol unchanged (above); B31's records and B34 (a)'s counts and tally unchanged; the
  guard, now raising on any leaving disagreement, never fires in the suite. Gate: 3135 passed,
  0 xfailed.
- W10.6c. `syn001.ph_flash`'s dew-point sentence replaced by §16's Q-S15 (1) text (checked equal
  to the spec's quoted string); A01 re-run: ok, no departures, 43 configurations, 0 schema
  errors, citations unchanged (§5.1-§5.3 and §6.6 once each in the three PH-type manifests).
  Gate: 3135 passed, 0 xfailed.
