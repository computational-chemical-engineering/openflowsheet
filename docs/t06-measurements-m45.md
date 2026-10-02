# T06 measurements — Phase M, items M4 and M5 (append-only)

Build-lane measurements for T06 (spec `docs/derivations/T06-corpus-spec.md` §17, Phase M), kept
apart from `docs/t06-measurements.md` so parallel M-items do not conflict. Measured at `792c594`
(`wp/T06`), numpy 2.2.4, scipy 1.15.3, x86-64, with `PYTHONPATH=src:.:tests` and the project
venv; no production code was changed. The probes are scratch scripts (the spec asks for none under
`scripts/`); what each does is stated with its numbers so that it can be rebuilt.

---

## M4 — ADV-06's injection hook and the three noise levels (spec §4.4)

### The hook: frozen-interface clean

`bind_revision_flowsheet` (`src/process_runtime/application/revision_binding.py:480`) builds the
binding's provider as `PropertyMeter(Syn001Provider())` (line 498), where `Syn001Provider` is a
**function-local import** (`from process_runtime.thermo.syn001 import Syn001Provider`, line 484),
resolved from the module attribute at call time. Every unit builder captures that provider, so
every compiled property block, the traversal (initializer) and the verifier's compiled residual —
`verify_revision` recompiles `binding.spec` (`verify/certificate.py:607`), whose units hold the
same provider — see whatever it is. The verifier's fresh flashes do **not**: `certificate.py`
binds `Syn001Provider` at module import (line 42) and constructs its own (`fresh =
Syn001Provider()`, lines 666/877/1023).

So the hook is: replace `process_runtime.thermo.syn001.Syn001Provider` with a factory returning
the double **for the duration of the `bind_revision_flowsheet` call only**, then restore it
(W7: `monkeypatch.setattr` in a context around the bind). No `src/` change and no frozen-interface
change (`docs/interfaces-frozen.md`): the double implements the frozen `PropertyProvider`
(`describe`, `evaluate_phase`, `flash`) and sits inside the binding's `PropertyMeter`
(`binding.flowsheet.provider._provider is double` — asserted). Its one fragility: it relies on the
import staying function-local; if a refactor hoists it to module level the patch target becomes
`process_runtime.application.revision_binding.Syn001Provider`. A W7 test should assert the double
was actually bound (the assertion above) so that such a refactor fails loudly instead of silently
testing the clean provider.

The double, as measured (spec §4.4 verbatim; `describe` and `flash` delegate unchanged):

```python
def xi(key):  # §6.3's draw, 2u - 1 (exact in binary64)
    word = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big")
    return 2.0 * ((word >> 11) * 2.0**-53) - 1.0

# evaluate_phase: inner result; if status == "ok", for each value name
#   h_<c>:   value + eta_h * xi(key),   lnK_<c>: value + eta_K * xi(key),   derivatives unchanged
# key = f"T06-ADV-06|{level}|{request.phase}|{name}|" + struct.pack(">5d", *n, T, P).hex()
LEVELS = {"H": (10.0, 1e-3), "M": (1e-5, 1e-11), "L": (1e-10, 1e-15)}  # (eta_h J/mol, eta_K)
```

`output` in the key is the result's value name (`h_A`, `lnK_B`, …), `phase` is `request.phase`
(`LIQUID`/`VAPOR`).

### Run

C1 = `benchmarks/t05/cases/SYN-001-UL-C1.yaml`, bound with the double, then the common path of
`tests/test_t05b_contract.py::solve`: `plan_revision(binding, POLICY_V2)` → `execute_plan` →
`verify_revision` when `CONVERGED` (policy `T05b-v2`, default check policy). Command: the scratch
probe `m4_probe.py [clean L M H]` (`python m4_probe.py`, ~20 s for all four).

| Level | Outcome (typed message) | Verdict | Limitations | Non-`pass` checks | `rcond₁` | `b` | witness max diff | max \|noise\| h / lnK | noisy calls solve / verify (evaluate_phase, flash) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | `CONVERGED`, one attempt (`initial`) | `VERIFIED` | none | none | 3.1538323453930944e-3 | 8.080911650682523e-14 | 2.3646862246096134e-11 | — | — |
| L | `CONVERGED`, one attempt | `VERIFIED` | none | none | 3.1538323453931026e-3 | 8.925974306963035e-14 | 1.5592210855785993e-10 | 9.999e-11 / 9.969e-16 | (283, 115) / (1252, 0) |
| M | `CONVERGED`, one attempt | `UNVERIFIED` | `[derivative_limitation]` | `derivative_witness.on_pattern` `fail`, value 1.793495859841966e-5, tol 1e-7 | 3.1538323458439373e-3 | 2.921597621363532e-09 | 1.793495859841966e-05 | 9.990e-6 / 9.918e-12 | (284, 115) / (1252, 0) |
| H | `INITIALIZATION_FAILED`, `initializer_failed(U-VLV): ph_ill_conditioned` (event `initializer_rejected`) | — (no certificate) | — | — | — | — | — | 9.999 / 9.988e-4 | (3454, 59) / — |

Check census at L and clean: residual 51, material_balance 27, energy_balance 6, specification 12,
bounds_and_domain 44, phase_admissibility 6, independent_split 12, derivative_witness 2 — all
`pass`, none `near_threshold`. At M the same 158 checks, all `pass` except the one witness check
(`derivative_witness`: 1 fail, 1 pass); `false_success_detected` false at every level.

Against the spec's expectations (§4.4, A16–A18):

- **H** (A16): no `VERIFIED` or `RELAXED` — the outcome is a typed initialization failure in the
  valve's PH kernel (10 J/mol of rough enthalpy noise breaks the class's continuity, as the JUMP
  double of T05b §12.2 does). Met.
- **M** (A17): `CONVERGED`, `UNVERIFIED`, every K04 §4.1–§4.7 check `pass`, the witness fails at
  1.79e-5 (spec's scale 6e-5, i.e. 179× the 1e-7 tolerance). Limitations are exactly
  `[derivative_limitation]`. **One difference from A17's wording:** today's certificate carries
  **no `shared_provider` limitation at all** (the clean C1 certificate has none either), so A17's
  "plus the always-present `shared_provider` entries" is met only after D14 (§8.4) is implemented;
  W7's assertion must read the limitation set as `{derivative_limitation} ∪ shared_provider
  entries` and will pass today with the second part empty — the design lane should say whether
  W7 lands before or after D14.
- **L** (A18): `VERIFIED`; witness 1.56e-10 against the predicted ≤ 6e-10 and the tolerance 1e-7.
  Met.
- **The verifier's fresh flashes do not see the noise** (recorded as §4.4 asks): during
  `verify_revision` the double received 1252 `evaluate_phase` calls (the recompiled residual,
  Jacobian and witness stencils) and **0** `flash` calls; the fresh flashes and fresh enthalpies
  go to the certificate module's own clean `Syn001Provider`.

Reproducibility: re-running in the order M, H, L (the first run was clean, L, M, H) gives every
number above bit for bit — the noise is a function of the exact request, independent of call
order and of the property cache.

---

## M5 — `rcond₁` and `b` over 20 numpy global seeds at every issued certificate (spec §8.1, A38)

### Scope and method

The spec names no list of registered certificates, so M5 covers **every certificate the T05, T05b
and K04-F9 tests issue**: `pytest -q -p m5_plugin -p no:cacheprovider tests/test_t05_*.py
tests/test_t05b_*.py tests/test_k04f9_*.py` (1209 passed, 104–109 s; run three times, the
summary counts and spreads identical each time). The scratch plugin replaces
`process_runtime.verify.regularity.onenormest` — the global name both call sites (`screen`,
`solution_error_bound`) resolve at call time — with a wrapper that, at every call, (1) saves
numpy's legacy global state, (2) runs the original estimator on the same operator under
`np.random.seed(s)` for s = 0…19, and once under 20260925 (§8.1's registered seed, W3), (3)
computes the exact `‖Ĵ⁻¹‖₁` from the operator applied to the identity, (4) restores the saved
state and makes the original call, so the test run itself is unchanged. From the caller's frame
it reads `one_norm`, `scaled_residual`, the dimension and `tau_scaled_min`, and records per seed
`rcond₁ = 1/(‖Ĵ‖₁ · est)`, `b = est · ‖F̂‖∞` and the screen's branch (`rcond₁ < τ_ill` →
escalation; `est > τ_min/(n ε)` → `ILL_CONDITIONED` absolute; else `NO_RANK_LOSS_DETECTED`), and
the certificate it belongs to (the nearest `verify`/`verify_revision`/`verify_bound` frame's
revision id; `[state]` = called with a `state` override).

**Why the branch is the whole of the random dependence of the R0 fields.** The estimate enters a
certificate only through `rcond₁`, `b` and the regularity status (`regularity.py:183–211`); `b` is
recorded, never a check (`certificate.py:1004–1011`); the status feeds `grade` and the
projection's refusal (`projection.py:120`). K05's R0 certificate projection
(`run/identity.py:94–110`) holds the verdict, `false_success_detected`, check
ids/results/near-threshold, the regularity status and dimension, and the limitation kinds — none
of which reads `rcond₁` or `b`. So an unchanged branch at every seed means an unchanged R0
certificate at every seed.

### Result

- **460 `onenormest` calls, 258 distinct matrices** (all from `screen`; `solution_error_bound`
  was never reached — the screen's `b` is always present), 337 certificate–matrix pairs; 18
  matrices are reached only through a test helper's direct `_screen` (`k04f9_support`,
  `t05b_support.revision_projection`).
- **No status word changes**: at every matrix the screen's branch is the same for all 20 seeds
  (249 matrices `NO_RANK_LOSS_DETECTED`, 9 escalated for `rcond₁ < τ_ill`). Margins over the 20
  seeds: every `NO_RANK_LOSS` matrix has `rcond₁ ≥ 66 τ_ill` and `est ≤ limit/5.98`; every
  escalated one `rcond₁ ≤ 0.034 τ_ill`. Hence no R0 field changes (argument above).
- **Direct end-to-end check** (scratch `m5_direct.py`: solve C1/C2/C3 once under `T05b-v2`, then
  `verify_revision` 20 times after `np.random.seed(s)`, s = 0…19; K05's R0 projection of each
  certificate): C1 `VERIFIED`, 1 distinct R0 projection, `rcond₁` 3.153832e-3 (1 value), `b`
  8.080912e-14 (1 value); C2 `VERIFIED`, 1 R0 projection, `rcond₁` 5.449931e-3…7.028362e-3
  (2 values), `b` 3.008824e-15…3.880252e-15 (2 values); C3 `VERIFIED`, 1 R0 projection,
  `rcond₁` 1.224535e-2…1.390923e-2 (3 values), `b` 2.990123e-9…3.396415e-9 (3 values) —
  reproducing T05b's recorded C2 3.0e-15…3.9e-15 and C3 3.0e-9…3.4e-9. (C3X is
  `INITIALIZATION_FAILED` from its registered start, as T05 A20 registers.)
- **244 of 258 matrices give one value at all 20 seeds**, equal to the exact `‖Ĵ⁻¹‖₁`
  (zero spread). **14 vary**, all listed below; at every one the maximum over the seeds is the
  exact norm and the minimum at most 2.3× below it.
- **Worst relative spread** (`max/min − 1`, identical for `rcond₁` and `b`, both being
  proportional to `est^∓1`): **1.2903** — `T05b-B34-125000-0-phf2-first` with a state override
  (the B34 candidate-answer sweep, `test_t05b_candidate_answers.py`), `rcond₁`
  3.774070e-3…8.643838e-3. Among the registered cases proper (not sweep or injected states) the
  worst is **C2: 0.2896**.
- **The estimate never exceeds the exact norm**; its lowest ratio is 0.4366 (the B34 row above).
  The status decided with the exact norm equals the recorded one at all 258 matrices (the §8.3
  assertion, on this population).
- **§8.1's seed 20260925 returns the exact norm at all 258 matrices** — inside the 20-seed spread
  (at its top) everywhere, a value one of the 20 seeds also gave everywhere, and the same branch
  everywhere. So W3's A38 comparison is expected to pass at every certificate measured here, each
  seed-varying certificate moving to the top of its spread (largest `b`, smallest `rcond₁`).

### Per family (numbers collapsed to `#` in revision ids except SYN-001's cases; `[state]` = state override)

| family | certificates | matrices | n | seed-varying | worst rel. spread | `rcond₁` over all seeds | `b` over all seeds | status (same at every seed) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| (test helper's direct `_screen`) | — | 18 | 10–47 | 0 | 0 | 1.1613e-03…2.5000e-01 | 0…1.884e-07 | NO_RANK_LOSS_DETECTED |
| `verify:SYN-001 [state]` | 1 | 2 | 47 | 0 | 0 | 1.8508e-03…2.1936e-03 | 7.402e-13…8.940e-13 | NO_RANK_LOSS_DETECTED |
| `verify_bound:FAM##-t#-test` (K04-F9 family) | 179 | 148 | 47 | 0 | 0 | 1.1358e-03…2.5864e-03 | 4.872e-15…7.113e-07 | NO_RANK_LOSS_DETECTED |
| `SYN-001-UL-C1-r1` | 1 | 1 | 51 | 0 | 0 | 3.1538e-03 | 8.081e-14 | NO_RANK_LOSS_DETECTED |
| `SYN-001-UL-C1-r1 [state]` | 1 | 1 | 51 | 0 | 0 | 3.1538e-03 | 5.015e-15 | NO_RANK_LOSS_DETECTED |
| `SYN-001-UL-C2-r1` (and `[state]`, same matrix) | 1 | 1 | 36 | 1 | 0.2896 | 5.4499e-03…7.0284e-03 | 3.009e-15…3.880e-15 | NO_RANK_LOSS_DETECTED |
| `SYN-001-UL-C3-r1` | 1 | 1 | 44 | 1 | 0.1359 | 1.2245e-02…1.3909e-02 | 2.990e-09…3.396e-09 | NO_RANK_LOSS_DETECTED |
| `SYN-001-UL-C3-r1 [state]` | 1 | 1 | 44 | 1 | 0.1359 | 1.2245e-02…1.3909e-02 | 2.314e-15…2.628e-15 | NO_RANK_LOSS_DETECTED |
| `SYN-001-UL-C3X-r1` | 1 | 1 | 44 | 1 | 0.0967 | 1.3050e-02…1.4313e-02 | 1.361e-14…1.493e-14 | NO_RANK_LOSS_DETECTED |
| `SYN-001-UL-C3X-r1 [state]` | 1 | 1 | 44 | 1 | 0.0967 | 1.3050e-02…1.4313e-02 | 2.261e-15…2.480e-15 | NO_RANK_LOSS_DETECTED |
| `SYN-001-nominal-r1` | 1 | 1 | 47 | 0 | 0 | 1.1613e-03 | 2.634e-14 | NO_RANK_LOSS_DETECTED |
| `SYN-001-nominal-r1 [state]` | 1 | 2 | 47 | 0 | 0 | 1.4842e-04…2.1936e-03 | 7.402e-13…7.880e+01 | NO_RANK_LOSS_DETECTED |
| `T05-W#-A#-*` (P#, ph-flash, valve) | 3 | 3 | 10–18 | 0 | 0 | 1.4753e-02…2.5000e-01 | 0…1.465e-08 | NO_RANK_LOSS_DETECTED |
| `T05-W#-INJ-T# [state]` | 4 | 4 | 11–21 | 0 | 0 | 7.3807e-03…1.5723e-01 | 0…1.375e+00 | NO_RANK_LOSS_DETECTED |
| `T05b-B34-<a>-<b>`, `b ≥ 0`, and `-phf2-first` `[state]` (B34 sweep) | 18 | 53 | 23,31 | 8 | 1.2903 | 1.6567e-20…1.1011e-02 | 0…7.219e+03 | per matrix: NO_RANK_LOSS or escalated |
| `T05b-B34-<a>--<b>`, negative `b`, and `-phf2-first` `[state]` (B34 sweep) | 6 | 17 | 31 | 1 | 0.0932 | 1.7380e-04…4.1609e-03 | 1.707e-15…1.838e-07 | NO_RANK_LOSS_DETECTED |
| `T05b-B31-CH*` (the B31 openings `CH-<Q>-<k>x<k>x<k>`, `CH3`, `CH-DZ12`, with `-dp10000` and `-phf2-first` variants) `[state]` | 11 | 11 | 15–47 | 0 | 0 | 8.5026e-21…6.6667e-02 | 0…1.407e+04 | per matrix: NO_RANK_LOSS or escalated |
| `T05b-DZ#` | 8 | 9 | 10–21 | 0 | 0 | 2.0408e-02…2.5000e-01 | 0 | NO_RANK_LOSS_DETECTED |
| `T05b-DZ# [state]` | 7 | 9 | 10–34 | 0 | 0 | 6.7204e-03…2.5000e-01 | 0…4.000e-01 | NO_RANK_LOSS_DETECTED |
| `T05b-NP#`, `NP-G`, `NP-GC` (and `[state]`) | 9 | 9 | 18,28 | 0 | 0 | 8.8959e-03…1.5665e-02 | 2.130e-16…1.212e-07 | NO_RANK_LOSS_DETECTED |
| `T05b-S#-P## [state]` | 2 | 3 | 23,31 | 0 | 0 | 3.4362e-05…1.0194e-02 | 0…9.385e+00 | NO_RANK_LOSS_DETECTED |
| `T05b-SAT-VAPOUR-FEED` | 1 | 1 | 18 | 0 | 0 | 1.1009e-03 | 0 | NO_RANK_LOSS_DETECTED |
| `T05b-SC#` (and `[state]`) | 5 | 8 | 18–37 | 0 | 0 | 1.3905e-03…1.4753e-02 | 0…1.884e-06 | NO_RANK_LOSS_DETECTED |

### The 14 seed-varying matrices (all `NO_RANK_LOSS_DETECTED` at every seed)

| certificate | n | distinct estimates / seeds at exact | est/exact over 20 seeds | `rcond₁` min…max | `b` min…max | rel. spread |
| --- | --- | --- | --- | --- | --- | --- |
| `SYN-001-UL-C2-r1` (plain and `[state]`) | 36 | 2 / 19 | 0.7754…1 | 5.449931e-03…7.028362e-03 | 3.0088e-15…3.8803e-15 | 0.2896 |
| `SYN-001-UL-C3-r1` | 44 | 3 / 5 | 0.8804…1 | 1.224535e-02…1.390923e-02 | 2.9901e-09…3.3964e-09 | 0.1359 |
| `SYN-001-UL-C3-r1 [state]` | 44 | 3 / 5 | 0.8804…1 | 1.224535e-02…1.390923e-02 | 2.3140e-15…2.6284e-15 | 0.1359 |
| `SYN-001-UL-C3X-r1` | 44 | 3 / 5 | 0.9118…1 | 1.305038e-02…1.431257e-02 | 1.3614e-14…1.4931e-14 | 0.0967 |
| `SYN-001-UL-C3X-r1 [state]` | 44 | 3 / 5 | 0.9118…1 | 1.305038e-02…1.431257e-02 | 2.2611e-15…2.4798e-15 | 0.0967 |
| `T05b-B34-125000--3000-phf2-first [state]` | 31 | 3 / 16 | 0.9148…1 | 3.806235e-03…4.160854e-03 | 3.1238e-15…3.4148e-15 | 0.0932 |
| `T05b-B34-125000-0 [state]` (×2) | 31 | 3 / 16 | 0.9155…1 | 3.774070e-03…4.122446e-03 | 3.1529e-15…3.4440e-15 | 0.0923 |
| `T05b-B34-125000-0-phf2-first [state]` (×2) | 31 | 4 / 10 | 0.4366…1 | 3.774070e-03…8.643838e-03 | 1.5037e-15…3.4440e-15 | 1.2903 |
| `T05b-B34-125000-3000 [state]` | 31 | 2 / 16 | 0.9581…1 | 3.259182e-03…3.401711e-03 | 3.3275e-15…3.4731e-15 | 0.0437 |
| `T05b-B34-125000-3000 [state]` | 31 | 2 / 17 | 0.9162…1 | 3.259182e-03…3.557277e-03 | 3.1820e-15…3.4731e-15 | 0.0915 |
| `T05b-B34-125000-3000-phf2-first [state]` | 31 | 2 / 19 | 0.9581…1 | 3.259182e-03…3.401711e-03 | 3.3275e-15…3.4731e-15 | 0.0437 |
| `T05b-B34-125000-3000-phf2-first [state]` | 31 | 4 / 8 | 0.4832…1 | 3.259182e-03…6.744434e-03 | 1.6783e-15…3.4731e-15 | 1.0694 |

("×2": two certificate–matrix pairs whose values agree to the digits shown.) For A38 the spread to compare a W3
value against is each certificate's row here; every other certificate's spread is zero, so after
W3 its `rcond₁` and `b` must be bit-identical to today's.

### Not covered

Certificates issued only by the K04, T02, T03 and T04 tests (SYN-001's tear-path `verify`, the T04
PTC/homotopy certificates, K04's TRI/SQ matrices, which call `screen` directly) — outside the
brief's T05/T05b/K04-F9 population. The same plugin covers them with the file list extended
(`tests/test_k04_*.py tests/test_t0[234]_*.py`).
