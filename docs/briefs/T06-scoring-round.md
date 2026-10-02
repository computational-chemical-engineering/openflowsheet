# Brief — T06 scoring-run ruling round (gate FAIL on run 1)

**To:** `specifier` (design lane; consult the `architect` if a solver/scaling redesign is needed — say
so). **From:** build lane, 2026-09-26. **Branch:** `wp/T06` (HEAD `f6b3510`).
**Deliverable:** rulings as dated spec amendments / ADR text (register for undoable choices; twin
re-emitted if a registered value changes, `--check`, new SHA), a ruling list in §3 here with each
build-lane change and its acceptance test. No code; do not commit. **Constraint:** a failed gate stays
failed — nothing may be relaxed to pass; a remedy must make the solver or the verifier right, or the
registration honest, with the reason stated. Frank's steers: fewest limitations; robustness with
recorded fallbacks.

## 1. Run 1 (local x86-64; `docs/T06_DECISIONS.md` last entries; run file and diagnosis scripts in the
scratchpad `…/scratchpad/scoring/`, `scoring/diag/` — commands below reproduce each start bit for bit)

S = 431/440 (first 367, rescued 64); SUCCESS 431, F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 2, F-OTHER-ROOT 4;
gate **FAIL** on "no unexplained F-OTHER-ROOT"; A32 passes; A33 reports 137 failures (not a gate term).

## 2. The diagnosis (measured by the build lane; reproduce with
`PYTHONPATH=src:.:tests:$SCR .venv/bin/python $SCR/cert.py <CASE> <start>` and `$SCR/budget2.py`)

1. **THM-09's four F-OTHER-ROOT (starts 1, 2, 5, 10) are the registered root stopped early**, not a
   second root and not a verifier miss: only S3.T/S4.T and the split move; ΔT = −1.005e-5, −3.447e-5,
   −1.010e-5, −1.429e-5 K against the 1e-5 K allowance; S3/S4.n.B 0.22–0.74 of 3.1e-7; regime
   TWO_PHASE/TWO_PHASE as at the root; the certificate's own bound covers it (b 2.9e-7…1.0e-6 scaled,
   2.9e-5…1.0e-4 K). **Mechanism:** pure B's row `PHF-equilibrium:B = V·L·(1 − K_B)`; at start 1
   `lnK_B = −2.798e-7`, row 1.863e-8 = 0.20 of its 9.3e-8 tolerance, so the tolerance admits ≈ ±5e-5 K
   (rcond₁ 1.4e-3). SUCCESS vs F-OTHER-ROOT is where Newton stops (SUCCESS starts 6, 19 at 0.37/0.97 of
   the allowance). **Concern:** judged at x_final with ADR 0013's projection off, start 1 would be
   `FAILED` (`energy_balance.U-PHF` 1016 W; `independent_split.B` 0.0339 mol/s) — `VERIFIED` rests on
   the D1 projection landing within 1.84e-11 K of T_sat. Rule: the remedy (e.g. the row's scaling /
   form for a single flowing component so Newton pins T to its allowance; a polish; the allowance's
   derivation at a degenerate split; or the classification), and whether the projection's rescue of a
   1 kW x_final imbalance is sound (ADR 0013 D1's preconditions).
2. **F-FALSE-SUCCESS-CAUGHT (THM-09 starts 3, 18): the verifier worked** — converged to the trivial
   V→0 root (pure-B liquid at 365.08 K, 5.08 K superheated); failed energy −60 000 W, independent split
   −2.0 mol/s; projection refused (`projection_outside_domain`). **Side defect:**
   `phase_admissibility.<U>.<S>.closure = Σ(v/V) − Σ(l/L)` is identically 0 (`verify/checks.py:648`
   normalises the flows) — vacuous whenever V > 0. Rule the correct check.
3. **F-BUDGET (THM-08 starts 3, 12; THM-09 start 4): cost, not divergence** — VAPOR-opened valve starts
   (A85's TP re-split); the 10 000 calls go to the phase controller's band route (nested
   `bracketed_root` over `band_temperature` bisections; 109 `band_temperature` calls at THM-08/3) and
   the residual-time phase screen's `band_temperature`; with the cap raised all three converge to
   SUCCESS via the restart (10 134, 10 093, 12 524 calls). **Separate defect:** recorded
   `counters.property_calls` (6943, 6902, 9250) under-report the meter's 10 000 (suspected
   `orchestrator/trace.py:720` sampling). Rule: the band route's cost remedy (e.g. a cheaper bracket,
   caching, Q-S10's band-end screen reuse), the counter fix, and whether any budget change is allowed
   before re-scoring (budgets were registered before scoring — §6.2).
4. **A33 (137 failures):** every missing `independence_qualifications` id is a prefixed check with
   `not_applicable` status (200 ZERO_FLOW, 94 `temperature_degenerate` splits); the certificate
   qualifies only checks that consulted the provider (`verify/certificate.py:1186`). A33's wording is
   broader than the certificate's rule. Rule the wording (or the certificate).
5. NET-11 reports "roots 2" from a branch-label artefact (start 16 labels U-HEAT TWO_PHASE with
   S4.V = 6.3e-11 mol/s, 3.9e-11 scaled from start 0) — rule the report's root clustering.

## 3. Rulings (the design lane fills this in)

*Filled 2026-09-26 by the design lane (`specifier`). Normative text: `docs/derivations/T06-corpus-spec.md` "Amendment 4" and every passage marked **(A4)**; `docs/adr/0018-newton-terminal-refinement.md` (new, **pending Frank's approval of one enum widening**); ADR 0014 Amendment 4; register R-085 … R-087 (R-080 annotated); twin re-emitted (347 claims, `e97f61ce4a7d13c3cd22edccb2fba637dbebf59fd990fd64ad32ccde970cd2d4`, 89 080 bytes, additive). The `architect` was not consulted: the solver remedy is one bounded termination step, which this round prototyped and measured. Measurements are this host's, `f01ed8d`, scratch prototypes around the committed code, not committed; the 440-start ensemble was not re-run.*

**Run 1's FAIL stands** (R-087). Nothing below re-judges it. Nothing that scores a start changes: N, `S_min`, the starts, S1–S4, the failure classes, §7.2's explanation route, the budgets, the ceiling. Remedies change the solver or the verifier, and run 2 re-scores all 440 starts.

### 3.1 Rulings

1. **THM-09's four `F-OTHER-ROOT`s: the solver is made to deliver the accuracy S3 registers; S3 does not move.** The row `V·L·(1 − K_B)` admits `|T − T_sat| ≤ 5.0167e-5 K` = 5.02 allowances at the root (twin, reproducing start 1's row 1.863e-8 = 0.2003 τ_eq from the closed form). S3's `10 τ_kind` assumed quadratic overshoot, which `T06-revision-v1` never promised (K04 F3). **Remedy:** ADR 0018, `globalization.eo_core = "newton_refined"`. At a `CONVERGED` exit at `k ≥ 1`, when the chord correction from the kept factorization exceeds `τ_kind` (S3's allowance / 10) on any column, the attempt takes one more Newton iteration. The result is kept only if it reaches `τ_kind`, and the outcome never changes. The revision path moves to `T06-revision-v2` = v1 + that value. *Measured:* the four become SUCCESS at 1.8e-6…2.2e-5 of the allowance; the K05 identity document is byte-identical. **ADR 0013 D1's rescue is sound:** its preconditions held, the step is the first-order error `b` discloses, and the 1 016 W is `V·Δh_vap,B`, the pure-component flash's jump at `T_sat`, not a bookkeeping error; D1 did refuse the trivial root (starts 3, 18). **Rejected:** a wider S3, a `b`-based allowance, a wider §7.2 route (all post hoc), the row's form or scaling, the rule under existing policies.
2. **The correct two-phase check is the saturation closure** (spec §8.8, ADR 0014 D13, R-086): `max(|T − T_b(l, P)|, |T − T_d(v, P)|)` against `τ_T`, from the verifier's own `band_ends`, same id, judged where ADR 0013 D1 judges `phase_admissibility`. The old `Σ(y − x)` was ≤ 2.2e-16 on all 660 suite evaluations. The new one is ≤ 9.8e-10 K at 577 judged states, 3.34 K at NET-11/16. It moves exactly four registered expectations (T05b B34 (a), B16, B26; one T04 fixture) and no identity key.
3. **No budget change before re-scoring. A cost remedy is admitted only if result-inert. The recorded counter must equal the meter.** An exact memo saves nothing (0 repeated inputs among 175/175/168 wrapped calls), so the three stay `F-BUDGET` unless W21 finds an inert remedy (Q23). `counters.property_calls` must equal the meter's charge, and `max_property_calls` exactly at exhaustion (A93).
4. **A33's wording changes, not the certificate.** The qualified ids are the prefixed checks whose result is `pass` or `fail` (§8.4 (A4), R-080 annotated). This matched on nine certificates, `FAILED`, `ZERO_FLOW` and degenerate ones included.
5. **NET-11's "roots 2" is a finding, not a clustering artefact; the census stays.** Start 16's certificate claims `U-HEAT TWO_PHASE` with `V = 6.3e-11 mol/s` at a liquid 3.34 K below its bubble point, a false label. Ruling 2's closure fails that certificate (→ `F-FALSE-SUCCESS-CAUGHT`). The solver-side conversion (T03 §4.10's "TWO_PHASE always admissible") is Q22: not in T06.

### 3.2 Build-lane checklist, in order (each its own commit; spec §17 (A4) holds the table)

| # | Chunk | Acceptance |
| --- | --- | --- |
| 1 | **W17** — commit the re-emitted twin (already in the working tree: `benchmarks/t06/reference_values.yaml`, `docs/derivations/scripts/t06_reference.py`) and move its pins: `benchmarks/registry.yaml` (two `reference_sha256`), `tests/test_t06_w4_registry.py` (`TWIN_SHA256`), `benchmarks/t06/references/comparison.json`'s recorded twin hash (by its generator) | `--check` 347 of 347; two `--emit` byte-identical to `e97f61ce…`; the YAML's diff additive; every comparison verdict unchanged |
| 2 | **W19** — §8.8's closure in `verify/table.py` and `verify/checks.py`; A91; A92's four re-registrations with their measured values, plus an erratum line in the T05b spec pointing to §8.8 | A91 (a)–(d); A92: suite green except exactly the four, re-registered; K05 identity document byte-identical. Anything else moving is a stop-and-report |
| 3 | **W20** — the revision path records `property_calls` from the meter; R-015 regeneration | A93: 10 000 at THM-08/3, THM-08/12, THM-09/4; fixture diffs limited to `property_calls`, `requested_evaluations` |
| 4 | **W22** — A33 (A4) in the harness and the corpus test | A33 (A4)'s corpus test passes; a unit test with a constructed certificate fails it both ways (an evaluated prefixed check without an entry; an entry on a `not_applicable` check); run 2's report shows 0 A33 failures (run 1's records do not store the check lists, so they are not re-classified) |
| 5 | **W18** — ADR 0018: the enum value (schema, `GlobalizationPolicy`), the D2–D5 hook, factor kept for the chord, `region.py` enabling it under `newton_refined`, `T06-revision-v2`, the registry's ensemble policy, `interfaces-frozen.md` §2's note; T06's v1-registered tests and A02's revision-built cases re-run under v2; W9's `t06` key regenerated (policy ids only). **One isolated commit for the widening**, so a "no" from Frank reverts cleanly | A86–A89; A87 (a) every registered expectation and the K05 identity document byte-identical, (b) R0-equal and bit-identical where the rule does not fire. A T06 expectation failing under v2 is a stop-and-report |
| 6 | **W21** (optional) — attribute the three `F-BUDGET` starts' ~3 000 calls per `ph_state`; land an inert remedy or record "none" | A94 |
| 7 | **W23 — run 2** — the full 440-start campaign under `T06-revision-v2` on `ref-x86-64` and `ci-aarch64`, after items 1–5 and **Frank's yes on ADR 0018**; report with A90's refinement counts | A90, A95; §7.3's gate unchanged. Anything unpredicted — an `F-OTHER-ROOT`, a start that fails after a reverted or abandoned refinement, a `FAILED` label other than NET-11/16's — comes back to the design lane |

### 3.3 For Frank

- **ADR 0018's enum widening** (`solve-policy` `globalization.eo_core` += `newton_refined`) is a frozen-schema change: approve or decline (Q19). Precedents: ADR 0012 D4 and ADR 0015 D1. Default: build and prove it now, and hold run 2 for his answer. A "no" leaves THM-09's mechanism in place, and the gate term fails again. The remaining remedies all relax a registered criterion, and only he can authorize them.
- **T07 default** (Q20): recommend `newton_refined` as the application default, as the restart became.
- **Closed packages' registrations move by the closure fix**: T05b B34 (a) (4 `UNVERIFIED` → `FAILED`, each a false two-phase label caught), B16/B26 (x_final lists), one T04 fixture. This is a verifier tightening with measured evidence; no identity key moves. It is noted here because T05b is closed.
