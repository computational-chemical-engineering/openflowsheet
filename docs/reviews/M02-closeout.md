# M02 close-out: ADR 0027's acceptance, rulings on build log D130–D132, and the review's must-fix items F1–F3

**Lane:** design lane. **Date:** 2026-10-15. **Branch:** `wp/M02-closeout`, from `main` @ `67cfcff`.
**Read against:** ADR 0027 (Status line, Amendments 1–4); `evidence/M01/6c81683…/manifest.json`;
`evidence/M02/ba90619…/manifest.json`; `docs/design/M02-pymrm-adapter.md` §14.5 D4 and §14.7; `docs/reviews/M02-review.md`
§1–§3; T08 release spec §5.7. **Register:** R-340 to R-344. No manifest status is changed, and nothing here sets `reviewed`.

## 1. ADR 0027: accepted (R-340)

| Condition (Status line, Amendment 4) | Evidence | Met |
| --- | --- | --- |
| M01's manifest `tested` (WO-6, WO-8 stand-in) | `6c81683…` `tested`; stand-in A25–A32, A49–A51; record halves A52 | yes |
| A41–A48 through the adapter (G10v3) | A41 ×3 accepted; A42 1.56e-8 ≤ 1e-6; A43 repeat bitwise; A44 bitwise; A45 3.84e-8 ≤ 1e-7; A46 5.06e-5 ≤ 1e-3; A47 (a) bitwise (environment block equal, also re-run live, D132 (1)); A47 (b) 1.43e-8 ≤ 1e-6; A48 ×3 equal; round 2 ran nowhere; all 8 outlets bitwise v2's | yes |
| G11v3-1 to -12 | opt-in -1, -2, -3, -8, -11, -12 met; -4 selected V5; -5 two runs × 121 points equal; -6, -7, -9, -10 in the passing default-gate selectors | yes |
| G12v3-1, G12v3-2 | CONVERGED, VERIFIED, R3, 4 outer iterations; edges (a)–(c) at 653.15 K and 693.15 K | yes |

Record hashes were re-computed on this branch and equal the manifest's: G10 `8f6048b9…`, G11 `140791db…`, G12
`47dc9f08…`, edges `148ec488…`. The provisional document differs from registered v3 only in `hard_domain`, `timeout_s`
and `variant_id`, which matches §14.5 D4. **Not established:** evidence judged against an independent reference
(`judged: false`); cross-architecture reproduction; W21's verdict; human sign-off.

**C1 — should-fix, needs a decision (M02 follow-up; does not reopen the ADR).** The ADR's own design composition
y = [0.7, 0.235, 0.03, 0.015, 0.02] has y_Ar + y_CH₄ = 0.035, exactly v3's `inert_min`. `boundary.py:390` checks
`n[3] + n[4] >= inert_min * sum(n)` in binary64, so whether the registered v3 accepts the design state turns on rounding:
- With n = y × n_tot, the probe's tube flow and n_tot = 1 pass.
- n_tot = 100 mol/s fails by −4.4e-16 and is refused `out_of_domain`, "inert fraction below 0.035".
- So did 45 % of 2 × 10⁵ sampled scalings.

G10v3 cannot see this because the provisional document has no floor. M04 sidesteps it with its 0.036 box. *I would go
with* a registered few-ulp relative slack on the floor comparison only, with a test at the design composition over
flow scalings. That changes refusals only on the knife-edge. The alternative is to state in v3's document that the
floor face is decided by rounding.

## 2. Rulings on build log D130–D132

- **D130 — ratified, constrained (R-341).** The copy's floats are judged by `rules.coupling` and `record_sha256` for
  shape. **Add the R0 guard:** on reproduce, the archived copy's digest must equal `document_sha256(archived
  external-coupling.json)`, and the rerun's must equal its record's. Today a well-formed wrong digest is replaced
  silently, even on a bitwise rerun. Change: one comparison in `revision_run.py`'s D130 block (≈ l.1131), plus a test
  that a well-formed wrong archived digest gives MISMATCH.
- **D131 label — ratified (R-342).** "Shipped, bound on another basis:" follows R-310 and L42.
- **D131 axis — ratified; "not an L-row" reversed (R-343).** `external_execution` stays an axis. But "not a sandbox"
  is a user-facing limitation, so it needs an L-row (§5.7: E points only at L-rows or U-rows).
- **D132 (1) — ratified (R-344).** The env test runs v3, the variant whose runner is the built child.
- **D132 (2) — ratified (R-344).** The finding stands as the erratum to D114/D115, and the manifest's hashes are
  the files' (re-computed).
- **D132 (3) — generator ratified; all-P harvest reversed (R-343).** M02 `limitations[1]`, `[2]`, `[3]`, `[5]`, `[6]` are
  E; `[0]` and `[4]` stay P. Change (build lane, envelope only, M02's manifest untouched): add L-rows at the next free
  ids, repoint the five harvest entries, re-emit `docs/support-matrix.md`, and pass `scripts/t08_support_matrix.py
  --check` and `tests/test_t08_w2_support_envelope.py`.

## 3. Must-fix items F1–F3: closed on main

| Item | Commit | Read | Targeted run (this branch = main @ `67cfcff`) |
| --- | --- | --- | --- |
| F1 floats classified | `080d197` | `rules.coupling`/`rules.result` floors as R-317 (b): ρ 1, r_ξ `tau_xi_rel`, r_T `tau_T_K`, `defect_rel` 1e-6, flows molar-flow, `du`/`B` shape; A32 twin over `experiment.schema.json` | `test_m02_schemas.py` 23 passed |
| F2 attributed request | `88b3ab4` | `answer_of(…, attributed=)` in replay only; `coupling_evidence` reads it from the accepted iterate's answers; the record keeps the served documents | `test_m02_wo14.py` 14 passed, **no xfail marker**; RP-2 asserts VERIFIED, `false_success_detected` false, MATCH with no differences, `bitwise_floats` false |
| F3 f5 end to end | `908d9a3` | through `revision_run`: outcome, no certificate, failure bundle valid, taxonomy, (`max_outer`, 1), record valid against `$defs/coupling` | `test_m02_wo10_coupled.py` 20 passed; `test_m02_wo10_driver.py` 18 passed |

## 4. Not examined

The full gate (not run, by brief). The opt-in real-reactor tests (records read, not re-run). F4–F10 beyond what the
manifest's limitations restate. Whether R-317 was carried into ADR 0034 as Amendment 1 (R-317's normative-text cell
says WO-13 would do it). `docs/V02_STATE.md`'s M01 row ("ADR 0027 Proposed") is left for the merge, because `main`
has moved.
