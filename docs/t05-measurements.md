# T05 — W0 measurements (append-only log)

Spec `docs/derivations/T05-unit-models-spec.md` §22. Each W0 item records the command and the
number it produced. Position lives in `docs/T05_STATE.md`; this file is history, grepped rather
than read whole.

## W0.1 — inertness baseline, before any T05 edit (2026-09-25, `wp/T05` at `107dd32`)

`wp/T05` differs from `main` at `279b2eb` only in documents, the twin and its YAML (no `src/`,
`tests/` or `scripts/` change), so these are `main`'s values.

| Item (ADR 0011 D3) | Value | How measured |
| --- | --- | --- |
| Gate | green, **1915 passed** | `PATH=.venv/bin:$PATH ./scripts/check.sh` |
| K05 `structural_sha256` (CI pair) | `4ce030cab1e4b4a2402897f480e5194961a1dbe9b8705316ddd4776cbd2d0082` on `ubuntu-latest` and `ubuntu-24.04-arm` | CI run 36064597228 (merge of `wp/T04`), job `identity`: "G05: R0 structural identity equal across 2 platforms" |
| K05 `structural_sha256` (local x86-64) | `4ce030cab1e4b4a2402897f480e5194961a1dbe9b8705316ddd4776cbd2d0082` | `PYTHONPATH=. .venv/bin/python scripts/k05_structural_identity.py --out identity.json` |
| Whole identity document (local) | sha256 `b364bb3dc881402fd6e7982532b19f06dba60e5c6b01e70d1aab861bae030b5a`; keys `artifact_r0_sha256, certificate, check_policy_sha256, constants_sha256, events, model_version, outcome, plan, plan_id, policy_sha256, solver_counters, structural, structural_sha256, t02, t03, t04, verification_status` | same file, `sha256sum` |
| K04 `check_policy_sha256` | `21c44e105a1b78428047258af3030b8502957aab5d27f0389c2f143bcb3cf390` | `CheckPolicy().sha256` |
| `thermo/syn001.py` | `75c9d5bad4f1cb3c8aa28b97d529777949434ebf911c0d9e11568b1e69ddd6ce`, equal to `git show 279b2eb:…` | `sha256sum` |
| `syn001_lifted_splits(("A","B","C"))` | sha256 of `repr` `fc36484e7a89f0e844a0f2e1148ef89052bdd97aaa7a63538685bc505a11e17a` (U-HEAT on S3; U-FLASH S3 → S4/S5) | `hashlib.sha256(repr(...).encode())` |
| Committed fixtures | 78 files under `tests/fixtures/`, tree sha256 `1303efa7b372ff699a2b233f4c48fd24ee9a171db6c8f0f5f64f30e1e2e0f0d1` (path + NUL + bytes + NUL, sorted) | R-015's generators are compared against them inside the gate |
| Reference YAML | `af4a543f8dab3d95c32764117be00afbc9e8d49478998e8538a1daf359385a6a`, equal to the spec header | `sha256sum benchmarks/t05/reference_values.yaml` |

A23 is judged against this table. The T05 additions to the identity document (A24) must go under
a new key, so that `structural_sha256` and the existing keys stay comparable.

## W0.3 — implementation row and Jacobian floors at the trial states (U1, merged `65c1d4c`)

Worst error ÷ tolerance over J1/J2 (spec §14 requires ≤ 1e-2, i.e. ≥ 100× margin). `scripts/t05_floors.py`;
harness `tests/t05_trial_states.py`.

| Model | Rows | Jacobian | Twin's 53-bit floor (rows / Jacobian, relative) |
| --- | --- | --- | --- |
| ph_flash | 3.04e-4 | 5.45e-5 | 3.04e-16 / 5.45e-16 |
| valve | 4.81e-4 | 1.12e-4 | 5.97e-16 / 1.12e-15 |
| pump | 5.15e-5 | 1.29e-5 | 5.15e-17 / 1.29e-16 |

The pump's registered cancelling partial ∂(PUMP-work)/∂S1.T is exactly 0.0. Negative control: PH-flash
J2 with the wrong inlet regime fails by 4.4e11 row tolerances. Separator and exchanger rows
(dev check by U2, not committed): worst 3.7e-17 relative — the harness measurement is pending (W6 agent).

## W0.4 — PH kernel T floor, |T* − T_ref| (K)

PHF-1 9.83e-14, PHF-2 7e-17, PHF-5 1.95e-14, PHF-7 2.11e-14, VLV-2 2.11e-14, VLV-5 1.78e-14 (twin
3.91e-14). Against 1e-6 K: ≥ 10⁷ margin. RX-5 pending (reactor). Plain bisection, about 53 evaluations of 200.

After merging U1 and U2 (`65c1d4c`): gate 2038 green; K05 identity document sha `b364bb3d…`,
byte-identical to W0.1.

## W0.3 / W0.4 — reactor, separator, exchanger (U3, merged)

Worst error ÷ tolerance at J1/J2 (≤ 1e-2 required): reactor rows 5.49e-4 (RX-equilibrium:A, J1),
Jacobian 1.09e-4; separator 3.1e-5 / 1.45e-5; exchanger 4.09e-5 / 1.46e-5 — each equal to the
twin's 53-bit floor. Kernel |T* − T_ref|: RX-5 4.12e-14 K (54 evaluations), RX-3 0 K (9), equal to the
twin's. After the merge: gate 2076 green; identity document sha `b364bb3d…` unchanged.

## W1.a step 0 — T02 floats baseline on the unedited tree (2026-09-25, `wp/T05` at `c9d4504`)

Protocol P (viii)'s reference (design note §7), taken before any W1 edit, on the build-lane
machine (x86-64).

| Item | Value | How measured |
| --- | --- | --- |
| `t02_identity.py --floats-out` | sha256 `9a8a5baf14e4f04f5d852a0998f7914f7bdcc81c056787e117a09980e25a2fb2` (12241 bytes) | `PYTHONPATH=. .venv/bin/python scripts/t02_identity.py --floats-out t02-floats.json`, then `sha256sum`; the same bytes with the worktree's `src` first on `PYTHONPATH` |
| Gate at the base | green, **2038 passed** | `./scripts/check.sh` |
| P (i), (iii)–(vii) at the base | all equal to W0.1: `75c9d5ba…`, `4ce030ca…`, `21c44e10…`, `fc36484e…`, fixture tree `1303efa7…` (78 files), identity document `b364bb3d…` | as W0.1 |

Protocol P's item (ii) counts from this base, `2038 + k`: the note's `1915` predates U1's and U2's merge.

## W1.a, W1.b — inertness protocol P (2026-09-25)

Measured at the end of each chunk, before its commit, on the step-0 machine. (i) `sha256sum`;
(ii) `./scripts/check.sh` and `git diff --stat c9d4504 -- tests/` plus `git status`; (iii), (vii)
`scripts/k05_structural_identity.py --out`; (iv) `CheckPolicy().sha256`; (v)
`sha256(repr(syn001_lifted_splits(("A","B","C"))))`; (vi) sha256 over the sorted files under
`tests/fixtures/`, each as path + NUL + bytes + NUL; (viii) `scripts/t02_identity.py --floats-out`.

| Item | W1.a (`8dad06d`) | W1.b (`290f8d7`) |
| --- | --- | --- |
| (i) `thermo/syn001.py` | `75c9d5ba…` | `75c9d5ba…` |
| (ii) gate; tests diff | green, 2054 = 2038 + 16; one added file | green, 2091 = 2054 + 37; two added files (`test_t05_w1b_revision.py`, helper `t05_syn001_shaped.py`) |
| (iii) `structural_sha256` | `4ce030ca…` | `4ce030ca…` |
| (iv) `check_policy_sha256` | `21c44e10…` | `21c44e10…` |
| (v) splits `repr` | `fc36484e…` | `fc36484e…` |
| (vi) fixture tree | `1303efa7…` (78 files); R-015 comparisons pass in the gate | same |
| (vii) identity document | `b364bb3d…` | `b364bb3d…` |
| (viii) T02 floats | `9a8a5baf…`, byte-equal to step 0 | byte-equal to step 0 |

Design Q-F answered (W1.b): the traversal's second pass is **bitwise** equal to
`Syn001Flowsheet.traverse(initial_recycle())` on every stream S1–S7, and pass 1's `G(S6)` from a
dormant recycle labelled 300 K is bitwise the registered initializer, which the legacy pass
computes from a 360 K label. The K02 units read no dormant inlet's temperature label.
The shaped revision's label is `FSR1-e66050b104fc-syn001-75c9d5bad4f1-44f894ff62f9` (50 characters).

## W10 — A06 rows at the causal solutions

Each model's rows (unit-level assembly through the trial-state harness, compiled by K01) at the
twin's registered causal solution, every coordinate the double its 20-digit string rounds to;
`|row| / τ_kind` with K04's `KIND_TOLERANCE` (`tests/test_t05_limits.py`). §14 argues a floor of
`≤ 2e-10 W`, `≤ 1e-14 mol/s`.

| Model | Cases | Worst ratio | Row, case | `|row|` |
| --- | --- | --- | --- | --- |
| ph_flash | PHF-1, 5, 6 | 9.55e-9 | PHF-equilibrium:A, PHF-1 | 8.9e-16 mol²/s² |
| valve | VLV-2, 5 | 5.94e-8 | VLV-energy, VLV-5 | 6.0e-11 W |
| liquid_pump | PUMP-1 | 5.76e-9 | PUMP-energy | 5.8e-12 W |
| conversion_reactor | RX-3, 4, 5 | 9.55e-9 | RX-equilibrium:A, RX-5 | 8.9e-16 mol²/s² |
| component_separator | SEP-2 | 1.34e-9 | SEP-mole:A | 4.2e-17 mol/s |
| heat_exchanger | HX-1, 4 | 0 | every row exactly 0.0 | — |

Largest energy row 6.0e-11 W (VLV-5, whose lifted inlet reads VLV-2's registered split at the
double of VLV-2's 20-digit `T`), inside §14's argued 2e-10 W; margin to `τ` ≥ 1.7×10⁷. PHF-6
(saturation route) is exactly 0.0 in every row.

## W1.c — protocol P (2026-09-25)

Measured at the end of the chunk, before its commit, on the step-0 machine, from base `03e31fa`
with the worktree's `src` first on `PYTHONPATH`; the commands are W1.a/W1.b's.

| Item | W1.c |
| --- | --- |
| (i) `thermo/syn001.py` | `75c9d5bad4f1cb3c…` |
| (ii) gate; tests diff | green, **2141 = 2129 + 12**; one added file (`test_t05_w1c_executor.py`), no test edited |
| (iii) `structural_sha256` | `4ce030cab1e4b4a2…` |
| (iv) `check_policy_sha256` | `21c44e105a1b7842…` |
| (v) splits `repr` | `fc36484e7a89f0e8…` |
| (vi) fixture tree | `1303efa7b372ff69…` (78 files); R-015 comparisons pass in the gate |
| (vii) identity document | `b364bb3dc881402fd6e7982532b19f06dba60e5c6b01e70d1aab861bae030b5a` (mandatory; equal) |
| (viii) T02 floats | `9a8a5baf14e4f04f5d852a0998f7914f7bdcc81c056787e117a09980e25a2fb2`, 12241 bytes, byte-equal to step 0 (mandatory) |

(vii) and (viii) run `execute_plan` on every registered SYN-001 plan (T02's `auto`, `eo`,
`anderson` and both A02 cases; K05's runs), so the dispatch of §2.3 is inert on the legacy path.

**The shaped revision through the general path** (`test_t05_w1c_executor.py`):

- `initial_state(shaped)` is **bitwise** `Syn001TearProblem(sf).reconstruct(sf.initial_recycle())`
  on all 47 variables, in the same order.
- `plan_revision` → one `solve_eo` step, schema-valid, region
  `U-FEED, U-MIX, U-HEAT, U-FLASH, U-SPLIT`, `signature_units = (U-HEAT, U-FLASH)`; the shaped
  descriptors `==` `syn001_lifted_splits`; §3.3 (a)–(e) hold; `resolve_mass` maps every holdup row.
- `execute_plan` → `CONVERGED` in 3 Newton iterations (attempt 0), 116 property calls, 5 residual
  and 4 Jacobian evaluations; `branch_found = [[U-HEAT, LIQUID], [U-FLASH, TWO_PHASE]]`, item 0's
  `initializer_source = traversal-G0-v1`. Worst deviation from P01's nominal
  (`reference_values.yaml`) per kind, against T02 §6.4's allowance: flows `2.2e-16 mol/s`
  (`S5.n.B`; allowance 3.1e-7), temperatures `0 K`, pressures `0 Pa`, duties `7.3e-12 W`
  (`U-FLASH.Q`; allowance 1e-2).
- Feed at 400 K → `INITIALIZATION_FAILED`, one `initializer_rejected` before any attempt, message
  `initializer_failed(U-MIX): inlet 0 is not admissible as a liquid: …` (R-038).

## W11 — rows at the coupled reference states (2026-09-25)

Each case revision `benchmarks/t05/cases/SYN-001-UL-*.yaml`, bound by `bind_revision_flowsheet`,
assembled, compiled by K01's CasADi adapter and evaluated (the `t05_trial_states` path) at
`ref.coupled_cases.<case>` converted to doubles; every column of the spec has a reference value
(stream `n, T, P`; lifted `vap`/`liq` and `V`, `L` as sums; flash-product `N` as sums; `Q`, `W`,
`xi` from `duty_W`, `work_W`, `extent_mol_per_s`). Ratio = `|row| / KIND_TOLERANCE[kind]`
(`verify.checks`, K04). Test: `tests/test_t05_w11_cases.py::test_every_row_vanishes_at_the_reference_state`.

| Case | Rows × columns | Worst ratio | Row |
| --- | --- | --- | --- |
| C1 | 51 × 51 | 8.36e-9 | `U-PHF:PHF-equilibrium:A` |
| C2 | 37 × 36 | 1.43e-8 | `U-RX:Ldef` |
| C3 | 45 × 44 | 1.43e-8 | `U-MIX:MIX-mole:C` |
| C3X | 45 × 44 | 1.43e-8 | `U-PHF:PHF-equilibrium:A` |

`1.43e-8 = 4.4e-16 / 3.1e-8`: one rounding unit on a `molar_flow` row, the double conversion of
the 20-digit reference. C3X is included because its rows have a solution (spec §11.4). Negative
control: C3 with the splitter's `recycle`/`purge` ports swapped gives `1.28e7`
(`U-SPLIT:SPLIT-recycle:C`). All four are `STRUCTURALLY_CLOSED` (excess = deficit = 0); C2 and C3
carry one row more than columns, in T01's over-determined block: the pressure rows around the
recycle (C2: 5 rows — `FEED-P`, the mixer's two `MIX-pressure`, `RX-pressure`, `SEP-P:top` — over
`S1.P`–`S4.P`; C3: 6 over 5), redundant around the loop as in SYN-001's 49 over 47.

## Q-A / Q-C probe (2026-09-25, after W11)

`plan_revision` + `execute_plan` on the four case files: C1, C2, C3 `CONVERGED` from
`traversal-G0-v1` (design Q-A holds). C3X: `INITIALIZATION_FAILED`,
`initializer_failed(U-HX): temperature_cross(cold_end)` (Q-C holds) — after fixing `initial_state`'s
check order (a refused pass tears a prefix), commit above. Accuracy against the twin, certificates
and W0.6/W0.7 are W13's.

## W1.d — protocol P (2026-09-25)

Measured at the end of the chunk on the step-0 machine, from base `d0e2542` (HEAD `15aed94`),
with the worktree's `src` first on `PYTHONPATH`; the commands are W1.c's.

| Item | W1.d |
| --- | --- |
| (i) `thermo/syn001.py` | `75c9d5bad4f1cb3c…` |
| (ii) gate; tests diff | green, **2293 = 2285 + 8**; one added file (`test_t05_w1d_verifier.py`), no test edited |
| (iii) `structural_sha256` | `4ce030cab1e4b4a2…` |
| (iv) `check_policy_sha256` | `21c44e105a1b7842…` |
| (v) splits `repr` | `fc36484e7a89f0e8…` |
| (vi) fixture tree | `1303efa7b372ff69…` (78 files); R-015 comparisons pass in the gate |
| (vii) identity document | `b364bb3dc881402fd6e7982532b19f06dba60e5c6b01e70d1aab861bae030b5a` (equal; carries SYN-001 certificates, so it proves the `_certify` → `_issue` extraction) |
| (viii) T02 floats | `9a8a5baf14e4f04f5d852a0998f7914f7bdcc81c056787e117a09980e25a2fb2`, 12241 bytes, byte-equal to step 0 |

**The shaped revision through `verify_revision`** (`test_t05_w1d_verifier.py`):

- The W1.c solve → `VERIFIED`, 146 checks, ids pinned: 49 residual rows, 4 alias, 22 material,
  4 energy, 13 specification, 38 bounds, 10 admissibility / independent split (U-HEAT's `S3.bubble`,
  U-FLASH's `S3.closure`, each with `total` and three components), 4 declared-phase ports
  (`U-MIX.inlet.S1`, `U-MIX.inlet.S6`, `U-MIX.outlet`, `U-HEAT.inlet`, each exactly `0.0 K`), 2
  derivative witness.
- Cross-validation: 42 legacy ↔ general pairs, **bitwise equal** at the root and at `x⁰`. At `x⁰`
  15 of them are nonzero (flash, splitter, ratio and envelope balances; mixer, flash and envelope
  energy — e.g. legacy `energy_balance.splitter` is 2458.79 W there). The legacy
  `energy_balance.splitter` has no general counterpart (§4.3's table gives the splitter no energy
  row).
- Component sums: on CPython 3.13.5 `sum()` of floats is Neumaier-compensated. At `x⁰`
  `sum(S3.liq.*) = 3.7937936767848512`, left-to-right accumulation `3.7937936767848517`, so
  `material_balance.total.S3.L` is `0.0` legacy and `-4.44e-16` accumulated; the table sums a
  stream's components with `sum()` (commit `15aed94`, reversible), every other sum left to right.
- Once-through shaped revision, S3 forced all-liquid, duties ±8237.85 W → `FAILED`,
  `false_success_detected`; failing exactly `energy_balance.U-HEAT`, `energy_balance.U-FLASH`,
  `phase_admissibility.U-HEAT.S3.bubble`, `independent_split.U-HEAT.S3.{total,A,B,C}`; the four
  values equal the legacy set's at the same state to the bit; the envelope passes.

## W13 — coupled solves (2026-09-25, base `66b4270`)

Design note §2.1 steps 1–3 on the case files (`bind_revision_flowsheet` → `plan_revision` →
`execute_plan`, policy `T05-W13` with no tolerance or scale overrides, as W1.c), compared column by
column with `ref.coupled_cases.<case>` at its registered precision (`Decimal`). The YAML-to-column
mapping is the table in `tests/test_t05_coupled.py`'s docstring; it covers every solver column and
every registered stream coordinate, lifted split, duty, work and extent. Worst `|x − x_ref|` per
kind (§11.5 allowance in brackets); counts are the plan's `Counters` (the traversal start's
property calls are outside the metered window, design Q-H).

| Case | Outcome | Newton its | flows [3.1e-7] | T [1e-5 K] | P [0.1 Pa] | duty/work [1e-2 W] | residual / Jacobian / factorizations / property calls |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | `CONVERGED`, 1 attempt | 0 | 3.42e-15 (`S6.N`) | 2.43e-14 (`S2.T`) | 0 | 7.28e-12 (`U-HEAT.Q`) | 1 / 0 / 0 / 14 |
| C2 | `CONVERGED`, 1 attempt | 2 | 5.27e-16 (`S3.L`) | 1.16e-14 (`S2.T`) | 0 | 9.09e-13 (`U-RX.Q`) | 3 / 2 / 2 / 47 |
| C3 | `CONVERGED`, 1 attempt | 3 | 4.64e-11 (`S5.n.B`) | 3.60e-8 (`S3.T`) | 0 | 3.30e-7 (`U-HX.Q`) | 4 / 3 / 3 / 91 |

C1's start is the causal solution (acyclic, one traversal pass): the first residual meets the
tolerance and no Jacobian is formed. C3 is the only case stopped at tolerance rather than at
roundoff; its worst deviations are still 280× (T) and 3e4× (duty) inside §11.5. Signatures equal
`ref.coupled_cases.<case>.signatures`; A26's `branch_found` (the region result's
`root_fingerprint`) is exactly `[[U-HEAT, LIQUID], [U-VLV, TWO_PHASE], [U-PHF, TWO_PHASE]]`,
`[[U-RX, LIQUID]]`, `[[U-PHF, TWO_PHASE]]`. A20's first branch stays in
`test_t05_c3x_initializer.py`. W0.6/W0.7 (the certificate's solution-error bound) are not recorded
here: they read the certificates, which wait for the T05 verifier-table entries.

## W0.9 / Q-B — T01's copy rows, and the aliases at `x_final` (2026-09-25)

`plan_revision`'s `StructuralReport` on each case: `STRUCTURALLY_CLOSED`,
`uncertified_affine_rows = ()`, no conflicts. T01 certifies (removes from the closure count; still
evaluated) only a row that closes a cycle of copies; every other copy row is a tree edge of the
copy forest and an ordinary matched row. Every copy-shaped row:

| Case | Certified (`equals`, `m_e`) | Retained (matched) |
| --- | --- | --- |
| C1 (51 × 51) | none | `HEAT-pressure`, `PHF-T`, `PHF-pressure:{vapor,liquid}` |
| C2 (37 × 36) | `U-SEP:SEP-P:top` = `+MIX-pressure:1 − RX-pressure`, `m_e = 0` | `MIX-pressure:{0,1}`, `RX-pressure`, `SEP-T:{top,bottom}`, `SEP-P:bottom` |
| C3 (45 × 44) | `U-SPLIT:SPLIT-P:recycle` = `+MIX-pressure:1 − PHF-pressure:liquid`, `m_e = 0` | `HX-pressure:{hot,cold}`, `MIX-pressure:{0,1}`, `PHF-T`, `PHF-pressure:{vapor,liquid}`, `SPLIT-T:{recycle,purge}`, `SPLIT-P:purge` |

So Q10's expectation ("T01 eliminates the new copy rows as aliases") holds only where a copy row
closes a pressure loop: one T05 row (`SEP-P:top`, C2) and one K02 row (`SPLIT-P:recycle`, C3) are
certified; `PHF-T`, `SEP-T`, `HX-pressure` and the rest are retained as ordinary rows — none
uncertified, none conflicting. "Without changing results": the certified row stays a residual and
the solves meet §11.5 (W13 above). T01's canonical matching leaves exactly the certified row
unmatched.

Q-B: at each converged `x_final`, `BoundDeclaration(spec, compile_problem(spec), x_final)`'s
eliminated rows equal the region plan's `solve_plan.eliminated_rows` document for document (row,
`equals`, `constant_mismatch`, tolerance), and both equal T01's certificates — C1 `[]`, C2
`[SEP-P:top]`, C3 `[SPLIT-P:recycle]`. `verify_revision(..., solve_plan=...)` does not raise the
alias-mismatch refusal on any of the three (run only to see that; its T05 check content is not
recorded here). Tests: `tests/test_t05_coupled.py::test_t01_classifies_the_copy_rows`,
`::test_the_certified_aliases_at_x_final_are_the_plans`.

## W0.8 (spec Q4) — an EO solve with a dormant PH-type outlet (2026-09-25)

Two mini-revisions cut from C1's case file (its instances, connection templates and specification
entries, re-targeted): **valve** — `U-FEED` → `S1` (`liquid`) → `U-VLV` → `S2`
(`vapor_liquid`, lifted) → `U-SINK-L`, feed `(0, 0, 0)` at 330 K and `P_r`, `SPEC-valve-P` on
`S2.P` = `9e4 Pa` (VLV-Z's inputs); **PH flash** — `U-FEED` → `S1` → `U-PHF` → `S2` (vapour) /
`S3` (liquid) → sinks, the same dormant feed, `SPEC-phf-Q` = 0 W (PHF-Z0's inputs). Both bind,
18 × 18, `STRUCTURALLY_CLOSED`, one `solve_eo` step; `plan_revision` → `execute_plan` with
policy `T05-W13`:

| | valve | PH flash |
| --- | --- | --- |
| outcome, message | `CONVERGED`, `""` | `CONVERGED`, `""` |
| events | `plan_built, region_opened, attempt_opened, attempt_closed, region_closed, solve_closed` | same |
| iterations; residual / Jacobian calls | 0; 1 / 0 | 0; 1 / 0 |
| root state | all flows 0, `S2.T = 330 K` (label), `S2.P = 9e4` | all flows 0, `S2.T = S3.T = 330 K`, `U-PHF.Q = 0` |
| attempt signature = `branch_found` | `[[U-VLV, TWO_PHASE]]` | `[[U-PHF, TWO_PHASE]]` |
| K04 screen at the root (`screen(target_jacobian(BoundDeclaration(...)))`) | `RANK_DEFICIENT`, SVD rank 15 of 18, `σ_min = 3.7e-17` | `RANK_DEFICIENT`, rank 15 of 18, `σ_min = 5.6e-18` |
| zero Jacobian rows | `VLV-equilibrium:{A,B,C}` | `PHF-equilibrium:{A,B,C}` |
| null space (columns) | `S2.T` and the lifted `S2.vap/liq/V/L` directions | `S2.T`, `S3.T`, `S2.n`, `S3.n`, `S2.N`, `S3.N` directions |

**The spec's expectation (a typed solver failure on the rank path) is not what happens.** The
traversal start is already the exact root (the causal evaluators return the dormant labels), so
the first residual meets the tolerance and the solver returns `CONVERGED` without forming a
Jacobian: the rank path is never reached. The certificate path would not issue `VERIFIED`:
`grade` turns any regularity status other than `NO_RANK_LOSS_DETECTED` into a `rank_limitation`
and at best `UNVERIFIED` (the verifier table was not called here). Two further facts for the
design lane: (1) the rank loss is 3, not §4.7's one — at zero flow the three equilibrium rows of
the lifted/flash outlet have identically zero gradients (the attempt ran their `TWO_PHASE` form;
whether another form is regular there was not measured); (2) the attempt signature and the root
fingerprint call a zero-flow outlet `TWO_PHASE`, not `ZERO_FLOW`. Not pinned in a test (only a
typed failure would have been pinned; a success is not). Reproduce: build the two documents as
above from `SYN-001-UL-C1.yaml`, then the calls in the table.

## W12 — checks at the twin states (2026-09-25)

The six T05 entries of `verify.table.MODEL_CHECKS`; each case's twin state (`ref.coupled_cases`,
as doubles) solved by `solve_region(..., state=<twin>, initializer_source="user_guess")` over the
region `plan_revision` plans (converges in 0 iterations, state moved ≤ 3.6e-15), then
`verify_revision(..., state=<twin>)` (`tests/test_t05_w12_table.py`). Ratios are `|value|/τ` for a
two-sided check and `value/τ` (signed) for a one-sided one (`bounds_and_domain.<U>.*`, `.bubble`,
`.dew`); the generic nonnegativity and domain checks are excluded (their tolerance is a bound).

| Case | Checks | Verdict | Worst two-sided (any) | Worst §12.2 table check | Worst residual row | Worst one-sided | Near threshold |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 160 | `VERIFIED` | 2.36e-4 `derivative_witness.on_pattern` | 1.01e-7 `energy_balance.U-PHF` | 8.36e-9 `U-PHF:PHF-equilibrium:A` | −8.0e6 `bounds_and_domain.U-VLV.direction` | none |
| C2 | 116 | `VERIFIED` | 2.36e-4 `derivative_witness.on_pattern` | 1.43e-8 `material_balance.U-MIX.A` | 1.43e-8 `U-RX:Ldef` | −6.4e11 `phase_admissibility.U-RX.S3.bubble` | none |
| C3 | 139 | `VERIFIED` | 2.38e-4 `derivative_witness.on_pattern` | 6.45e-8 `independent_split.U-PHF.S3.total` | 1.43e-8 `U-MIX:MIX-mole:C` | −8.1e6 `bounds_and_domain.U-HX.heat_flow` | none |

Solution-error bounds recorded (scaled): C1 5.0e-15, C2 3.9e-15, C3 2.6e-15 — at the twin's
states, not W13's solves.

- **A20, second branch.** C3X's twin state solved the same way → `CONVERGED`; the certificate, at
  the solve's final state and at the twin's, is `FAILED`, `false_success_detected`, failing exactly
  `bounds_and_domain.U-HX.cold_end` with value `10.0` (exact in doubles: `−(290 − 300)`).
- **A22** (`tests/test_t05_w12_injections.py`, mini-revisions feed → unit → sinks), against
  `ref.injections`: INJ-T1 `phase_admissibility.U-VLV.S2.bubble` 0.38651240922981045 (ref
  0.38651240922981119863); `energy_balance.U-VLV` −38581.847479409065 W (ref gap
  38581.847479409153988, a magnitude; §12.2's `Ḣ(in) − Ḣ(out)` is negative);
  `independent_split.U-VLV.S2.total` −1.3690112427403234 (ref gap 1.3690112427403260808); also
  failing, unregistered: `.A/.B/.C` and `energy_balance.envelope` (the same stream pair, the same
  value). INJ-T2 `bounds_and_domain.U-HX.hot_end` +5.0 K, the only failure. INJ-T3
  `material_balance.U-RX.A/.B` −0.29999999999999993 / +0.30000000000000004, with
  `material_balance.envelope.A/.B` and the compiled `RX-mole:A/B` rows (the declaration carries the
  revision's `ν`). INJ-T4 `energy_balance.U-PUMP.work_relation` −4.800000000000001 W, with the
  compiled `PUMP-work` row (the same relation). Each fails by ≥ 4.7e3 τ.
- **A27** (`tests/test_t05_w12_discovery.py`): PTC over each case's region ends
  `PTC_MAPPING_INVALID` naming `U-PHF:PHF-mole:A` (C1), `U-RX:RX-mole:A` (C2),
  `U-HX:HX-mole-hot:A` (C3) — design note §5's rows — with no attempt, no event and no residual or
  Jacobian call, on the region solve and end to end through `execute_plan`.

## W13b — certificates, W0.5–W0.7 (2026-09-25, base `a565670`)

The certificates of the **actual** coupled solves (W13's `test_t05_coupled.solve`, policy
`T05-W13`), issued by design note §2.1 step 4, `verify_revision(binding, document, run,
solve_plan=plan.steps[-1].solve_plan)`, at `run.state` (`tests/test_t05_certificates.py`). W12
judged the twin's states; these are the solver's.

**A21.** All three `VERIFIED`, no limitation, `false_success_detected` false, every check `pass`,
none `near_threshold`, none `not_applicable`; the §12.2 ids equal W12's pinned `TABLE_IDS`, the
residual ids are the declaration's `equation_ids` in order, the alias ids `identity`/`satisfied`
per eliminated row, the witness ids `on_pattern`/`off_pattern`. [A09] on every energy,
admissibility and independent-split check and on nothing else; ADR 0011 D2's note on
`energy_balance.U-RX` and C2's `energy_balance.envelope`.

| Case | Checks | residual | alias | material | energy | spec | bounds | admiss. | indep. split | witness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 160 | 51 | 0 | 27 | 6 | 12 | 44 | 6 | 12 | 2 |
| C2 | 116 | 37 | 2 | 17 | 4 | 15 | 28 | 7 | 4 | 2 |
| C3 | 139 | 45 | 2 | 20 | 5 | 15 | 37 | 9 | 4 | 2 |

**W0.6 (Q6)** — K04 §7.4's recorded `solution_error_bound_scaled` = `‖Ĵ⁻¹‖₁ ‖F̂‖∞` (onenormest of
the inverse in brackets), required `≤ 1e-8` by §11.5:

| Case | bound | `‖Ĵ⁻¹‖₁` est. | margin to `1e-8` |
| --- | --- | --- | --- |
| C1 | 8.08e-14 | 58.1 | 1.2e5× |
| C2 | 3.88e-15 | 26.2 | 2.6e6× |
| C3 | 3.18e-9 | 16.6 | 3.1× |

C3 is the one case stopped at tolerance rather than at roundoff (W13: 3 Newton iterations; its
worst residual is `U-PHF:PHF-duty` at 1.9e-2 τ), so its bound is set by the stopping residual,
not by conditioning; `‖Ĵ⁻¹‖₁` is small on all three. §11.5's allowances stand.

**W0.7 (Q5, F9)** — every check's ratio: `|value|/τ` two-sided, `value/τ` signed one-sided
(`bounds_and_domain.<U>.*`, `.bubble`, `.dew`); the generic nonnegativity/domain checks are left
out (their tolerance is a bound; worst `domain` value/bound 0.82, C1 `S3` and C3 `S4`). Worst per
category:

| Category | C1 | C2 | C3 |
| --- | --- | --- | --- |
| residual | 1.38e-7 `U-PHF:PHF-duty` | 1.43e-8 `U-RX:Ldef` | 1.89e-2 `U-PHF:PHF-duty` |
| alias_certificate | — | 0 | 0 |
| material_balance | 3.58e-9 `U-VLV.lifted_split.B` | 7.16e-9 `envelope.A` | 1.43e-8 `U-MIX.C` |
| energy_balance | 1.53e-7 `U-PHF` | 6.30e-9 `U-RX` | 1.60e-2 `U-MIX` |
| specification | 0 | 0 | 1.79e-9 `U-SPLIT.ratio.A` |
| bounds (one-sided) | −8.0e6 `U-PUMP.direction` | — | −8.13e6 `U-HX.heat_flow` |
| phase_admissibility (two-sided) | 0 `U-VLV.S4.closure` | 8.84e-10 `U-MIX.outlet` | 1.19e-2 `U-HX.hot_inlet` |
| phase_admissibility (one-sided) | −2.29e11 `U-HEAT.S3.bubble` | −6.42e11 `U-RX.S3.bubble` | — |
| independent_split | 0 | 0 | 6.26e-3 `U-PHF.S3.total` |
| derivative_witness | 2.36e-4 `on_pattern` | 2.36e-4 `on_pattern` | 2.85e-4 `on_pattern` |

**Within F9's near-threshold band (`τ/10 < ratio ≤ 10τ`): none**, in any case, by the ratio and by
the `near_threshold` flag. The lifted-stream checks F9 concerns: C1's `U-VLV.S4` and `U-PHF.S4`
closure and independent split are exactly 0 (the start is the causal solution and no Newton step
is taken, so the lifted split is the fresh flash's own); C2's `U-RX.S3` independent split 0; C3's
`U-PHF.S3.total` 6.26e-3 (value −1.94e-10 mol/s), 16× below the band's lower edge. F9's mechanism
is not active on these three solves.

**W0.5** — derivative witness at `δ = 1e-5` (`FD_RELATIVE_STEP`), tolerance `1e-7` scaled, at the
converged states: `on_pattern` C1 2.3646862246096134e-11, C2 2.3646862246096134e-11 (the same
double), C3 2.8473112756444152e-11; `off_pattern` 0.0 in all three. Margin ≥ 3 500×; the spec's
twin floor at the trial states is `≤ 3.2e-11` (§14).

**A24.** `scripts/t05_identity.py` (`tests/test_t05_identity.py`), key `t05` of
`scripts/k05_structural_identity.py`: C1–C3 `CONVERGED` with their `VERIFIED` certificate
projections; C3X `INITIALIZATION_FAILED`, no certificate, fingerprint `None`. Local x86-64: the
document minus `t05` (same `json.dumps(indent=1, sort_keys=True) + "\n"`) hashes to
`b364bb3dc881402fd6e7982532b19f06dba60e5c6b01e70d1aab861bae030b5a` (unchanged);
`structural_sha256` `4ce030cab1e4b4a2…` (unchanged); the whole document
`8987721de8c4181bced3cd327c5be933ffaf677daad75cc42916689df82d03dd`. `t05` holds no float at any
depth, and two runs in one process are equal. The float-looking strings in it are exactly the
plan's declared `column_scales`, `row_scales` and `bounds` (kept by `execution_plan_r0` as
shortest decimals, ADR 0009 D1, as in `t02`) and the fingerprint's registered `delta_scaled_inf`
`"0.0001"` (as in `t03`); the fingerprint keeps `constants_sha256` and `variable_ids_sha256`
(identities of constants and ids, kept by T03's projection). Cross-platform equality awaits the CI
pair at merge.

Gate: `./scripts/check.sh` green, **2417 = 2404 + 13** (12 in `test_t05_certificates.py`, 1 in
`test_t05_identity.py`); no `src/` change.

## CI pair (A23 iii, A24) — run 36080722051 on `wp/T05` (commit "T05 decisions: W13b merged")

`check (ubuntu-latest)`, `check (ubuntu-24.04-arm)`, `identity`: success. `structural_sha256` =
`4ce030cab1e4b4a2402897f480e5194961a1dbe9b8705316ddd4776cbd2d0082` on both; "G05: R0 structural
identity equal across 2 platforms" — the comparator covers every key, `t05` included.

## Ruling round — build-lane fixes, part B (verifier, binding, identity; 2026-09-25)

Rulings `docs/briefs/T05-rulings.md` §4; the rows above are the records of their own chunks and are
not rewritten.

**Q-R3 — `energy_balance.U-SPLIT`** (`verify/table.py` `_splitter_energy`, the legacy's
`flows["S5"] - flows["S6"] - flows["S7"]` operation for operation, [A09]-qualified).

| State | legacy `energy_balance.splitter` | general `energy_balance.U-SPLIT` |
| --- | --- | --- |
| shaped root | `0.0` | `0.0` (bitwise) |
| shaped `x⁰` | `2458.786396165273` W | the same double (bitwise); `fail` |
| C3 solved state | — | `−1.8189894035458565e-12` W, τ `1.01e-3`, `pass`, not near threshold |

W1.d's cross-validation now pairs 43 ids and asserts (d) coverage at both states against the
whole general certificate (at `x⁰`, `verify_revision(..., state=x⁰)`): no legacy id is unpaired,
and the 95 legacy ids present under the same id (residual rows, aliases, generic bounds,
`energy_balance.enthalpy.<S>`) are bitwise equal too; a failing control withdraws the splitter
pair and gets `["energy_balance.splitter"]`. Pinned lists: shaped 146 → **147**; C3 139 → **140**
(energy 5 → 6; W12's twin-state list and A21 share `TABLE_IDS`). C1 160 and C2 116 unchanged (no
splitter). A20 (C3X's second branch, both states: exactly `{bounds_and_domain.U-HX.cold_end}`),
A21 (C1–C3 `VERIFIED`, none near threshold) and A22 pass unchanged. Protocol P: `75c9d5ba…`,
`4ce030ca…`, `21c44e10…`, `fc36484e…`, fixture tree `1303efa7…` (78), T02 floats `9a8a5baf…`
— all unchanged; identity document minus `t05` `b364bb3d…` (unchanged); whole document
`8987721d…` → `e117373de061637f3616c89eb35aeb2567f3e89c6724cc34c079fdda1ad020b9` (C3's
certificate gains the check).

**Q-R4 — A28** (`tests/test_t05_dormant_outlet.py`; W0.8's two mini-flowsheets built with
`t05_w12_support.mini_revision`, policy `T05-W13`, through `verify_revision`). Both valve and PH
flash: (1) `CONVERGED`, attempt iterations `[0]`, 0 Jacobian calls; (2) every flow column `0.0`,
outlet `T = 330.0`, `U-PHF.Q = 0.0`; (3) the target's all-zero rows are exactly
`<U>:{VLV,PHF}-equilibrium:{A,B,C}`, screen `RANK_DEFICIENT`, rank 15 of 18; (4) certificate
`UNVERIFIED`, limitations `[rank_limitation {status: RANK_DEFICIENT}]`, no `fail` (results only
`pass` and `not_applicable`), `false_success_detected` false — **the ruling's argued outcome,
measured**; (5) `branch_found` `[[U, TWO_PHASE]]`, `phase_branch` `ZERO_FLOW` for every stream.
**Found on the way:** before the structural refusal in `regularity._factorize` (commit "T05 review:
K04's screen and bound refuse…"), `verify_revision` on these flowsheets segfaulted in
`solution_error_bound`'s `splu` in 4 of 5 pytest runs (7 of 8 probe runs); the PH flash's dumped
target segfaults pure SciPy 1.15.3 on the first call. After: 8 of 8 clean; protocol P unchanged.

**Q-R5 / N4 — the `t05` key's `message`** (`scripts/t05_identity.py`): per case
`run.message.splitlines()[0] if run.message else ""` — C1, C2, C3 `""`; C3X
`initializer_failed(U-HX): temperature_cross(cold_end)`. `floats_in(t05) == []`, equal twice in one
process. Identity document minus `t05`: `b364bb3dc881402fd6e7982532b19f06dba60e5c6b01e70d1aab861bae030b5a`
(unchanged); whole document (local x86-64, `k05_structural_identity.py --out`):
`622463f5fbc8716f1196bc971633877e2d218e1c9744e3d4ad7d49608be0415b` (measured, not registered;
after Q-R3's check and this key). Cross-platform equality: the CI pair at merge.

**Q-R6 — W0.6 on the exact `‖Ĵ⁻¹‖₁`** (`test_a21_w0_6_the_solution_error_bound`: dense inverse of
`target_jacobian(BoundDeclaration(...), x_final)`, `n ≤ 64`; judged `exact × ‖F̂‖∞ ≤ 1e-8`; the
certificate keeps K04's `onenormest`, asserted never above the exact product):

| Case | n | `‖F̂‖∞` | `‖Ĵ⁻¹‖₁` est. | `‖Ĵ⁻¹‖₁` exact | est./exact | bound (exact) | margin to `1e-8` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 51 | 1.392e-15 | 58.07 | 58.07 | 1.0000 | 8.081e-14 | 1.24e5× |
| C2 | 36 | 1.480e-16 | 26.21 | 26.21 | 1.0000 | 3.880e-15 | 2.58e6× |
| C3 | 44 | 1.913e-10 | 16.63 | 17.76 | 0.9367 | 3.396e-9 | 2.94× |

**Review S1 — note §1.3 R4's converse** (`bind_revision_flowsheet`, after the port check). P1's
three revisions (feed `S1` `vapor_liquid` `(1, 1, 1)`, 360 K, `1.8e5 Pa` → C1's `U-VLV`, C1's
`U-PHF`, C2's `U-SEP`) each return `Unbound("unsupported",
"port_phase_unsupported(U-FEED-0.outlet)")` (before: `RevisionBinding`, then `KeyError` in
`plan_revision`). Label and `configuration_sha256` of C1, C2, C3, C3X and the SYN-001-shaped
revision measured with the binding module as of `3086da3` and as changed: identical (C1
`15e9b77d…`, C2 `7ce1dd35…`, C3 = C3X `af16266d…`, shaped `e66050b1…`). Protocol P unchanged
(whole document `622463f5…`). W1.c's `lifted_split_unregistered` defect guard is now reached with
a rule present at binding and withdrawn at planning; without it the binding refuses first
(`port_phase_unsupported(U-HEAT.outlet)`, asserted).
