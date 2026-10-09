# M02 review: the PyMRM execution adapter, experiment records, the `revision_coupled` route and its replay, v3's child, and the replacement check. Reviewed against `docs/design/M02-pymrm-adapter.md` (§4, §7, §14–§14.7; ADR 0033–0035, ADR 0027 Am. 2–4)

**Reviewer:** design lane, `reviewer` (Claude Opus 5.5), 2026-10-09. The package's single review and its last ruling
batch (brief `docs/briefs/M02-review.md`).
**Reviewed at:** `wp/M02` = `f4e8c56` (range `950bd78..f4e8c56`).
**Design reviewed against:** note §4.2–§4.4, §7.2, §14.5 D5/D8/D9/D10, §14.6 E1–E3, §14.7 F2; R-305, R-307, R-308,
R-311, R-312, R-315, R-316; ADR 0007 D2.2–D2.4; ADR 0025.
**Run here:** nothing beyond one interpreter check of `max` with NaN operands (F7). The gate numbers are the brief's.
**Read:** `orchestrator/coupling.py` (all), `application/coupled_run.py` (the floors, both experiment sources, the
certificate evidence, `solve_coupled`), the coupled branch of `revision_run.reproduce_bundle` and
`_constants_for_shape`, `adapters/pymrm/child.py` (§14.6/§14.7 paths), the boundary's hard domain and projection,
`replacement._validity`, `verify/failure.coupling_bundle`, `tests/test_m02_wo14.py` (RP-1…RP-3),
`tests/test_m02_wo10_driver.py` (list), the synthetic child's closed form, build log D53, D90–D94, D100–D115.
**Not examined:** WO-1…9's already-reviewed pieces (runner, store, launcher, env build), the C1 unit models
(`models/c1/*` other than the boundary), M01's flash, the job/HTTP/MCP surface, the evidence scripts' internals,
performance (§4.5).

---

## 1. Verdict

**Sound in the numerics; not yet `tested`. Three must-fix items, all in replay and verification, none in the solve.**

- The coupling driver implements §4.3 as amended by R-305 exactly: the 2n window, the base-relative secant update on the
  actual (clipped or halved) step, a reset from the best iterate, and `no_decrease` on a second reset in a row. Its
  convergence claim is honest. ρ is formed at an iterate whose inner solve converged, from experiments whose request
  inputs are the certified inlet bit for bit (`coupled_run._inputs_equal`). X̂ and ΔT̂ reach the inner model as the same
  floats the residual reads. The certificate re-forms both terms from the record against the certified state. The
  floors are computed as §4.2 states (D53's projected outlet moves them by ≤ 10⁻⁶ relative; ratified).
- The v3 child follows R-311 → R-316 and R-312 as written (§3, item 2).
- The replay is where M02 falls short. A cross-platform reproduce of any coupled bundle cannot be MATCH, for two
  reasons (F1, F2), and the build log's claim that G12 escapes the second of them is wrong (F1).

**WO-13 may mark the manifest `tested` once F1–F3 are done.** That means:
- RP-2 passes with no xfail;
- f5 runs end to end;
- the float-classification test covers `experiment.schema.json`;
- the gate is green, with the G2 dump and the MCP tool-list digest unmoved.

Nothing here sets `reviewed`.

---

## 2. Findings (most severe first)

### F1 — must-fix — The coupling record's floats are unclassified (ADR 0007 D2.3), so a cross-platform reproduce of a coupled run MISMATCHes

**Where.** `orchestrator/coupling.py:244-254` and `:319-331` (`rho`, `r_xi`, `r_T`, `floor_ratio_*`, `xi_E`, `T_E`,
`n_N2_in`, `n_tot_in`, `step.du`, `step.B`). The re-evaluated stand-in envelope is compared at
`coupled_run.py:404-411`. `run/compare.py:407-408` gives every unregistered name `NO_FLOOR`. A32
(`tests/test_k04_schemas.py:31-35`) enumerates only the three K04 schemas, so nothing caught the gap.

**Why it is a defect.** D2.3: "A new recorded float is added to this table by the package that records it … in the same
change — never discovered at comparison time." D93 discovered three such floats at comparison time.

**Failure scenario, beyond D93's last-bit seam.** The build log says G12 "would avoid (b)". It would not, cross-platform:
- The final iterate's `r_xi = ξ_E/n_N₂ − X̂` is a cancellation. Its size is ≈ ρ τ_ξ n_tot/n_N₂ ≈ 0.29 × 10⁻⁵ / 0.2
  ≈ 1.5 × 10⁻⁵, while each term is ≈ 0.2.
- An inner-state difference of 10⁻¹³ relative (ordinary between architectures) moves `r_xi` by ≈ 2 × 10⁻¹⁴.
- That is 1.3 × 10⁻⁹ relative, above the 10⁻⁹ tolerance, so the record compares MISMATCH.
- `step.B` is built from differences of r̂, and `step.du` from differences of iterates. Both lose relative accuracy the
  same way as the run converges.

**Minimal correction** (ruling R-317 in §3):
- Classify every float of `$defs/coupling`, and of the envelope fields a re-evaluation compares, by D2.2's rule: the
  floor is the threshold the quantity registers.
- Extend A32, or add an M02 twin, over `experiment.schema.json`.

### F2 — must-fix — In a replay, the EXT-COUPLING checks compare the recorded request with the rerun's inlet

**Where.** `coupled_run.py:620` (`_inputs_equal(entry["request"], inlet)`). The entry's request is the recorded one,
because `RecordedExperiments.evaluate` returns `answer_of(recorded, …)` (`coupled_run.py:412`).

**Failure scenario.** Any rerun whose inner solve moves the reactor inlet in its last bits sees:
- `_inputs_equal` false, so both checks fail;
- `verification_status` VERIFIED → FAILED;
- `false_success_detected` true.

This is a false alarm in the reproduction, not in the run. It covers every cross-platform reproduce, real reactor or
stand-in.

**Minimal correction** (R-317). The check compares the certified inlet with the inputs of the request the answer is
attributed to:
- **Live:** the request sent, bit for bit. This is unchanged.
- **Replay:** the request `RecordedExperiments` recomputes at the rerun's inlet, which is bitwise equal by construction.
  `RecordedExperiments` already holds that request within the archive's policy of the recorded one, raising
  `ReplayDivergenceError` otherwise, and that comparison is the replay's guarantee.

Carry it on `ExternalAnswer`, a non-record field, and read it in `coupling_evidence`. The rerun record keeps embedding
the recorded (served) documents. Do not write a request into the record that was never sent.

### F3 — must-fix (small) — f5's acceptance is not tested end to end

**Where.** The note's §14.5 table (l.1857) gives f5's expectation as "`COUPLING_NOT_CONVERGED`, failure bundle, no
certificate". `tests/test_m02_wo10_driver.py:226` asserts the driver's (outcome, reason) only. No test anywhere runs
`COUPLING_NOT_CONVERGED` through `revision_run`. The only end-to-end failure test is EVALUATION_ERROR
(`test_m02_wo10_coupled.py:395`).

**What is untested.** `TAXONOMY["COUPLING_NOT_CONVERGED"]`, the action mapping, the run-result outcome enum and the
bundle's `outer_iterations`.

**Correction.** One test with a test-only stand-in variant whose coupling block has `max_outer: 1`. Its initial X̂ of 0.15
is not the stand-in's 0.25, so k = 0 ends `max_outer`. Assert:
- the outcome and reason;
- no `solution-certificate.json`;
- the failure bundle's taxonomy, reason and `outer_iterations` = 1;
- the record valid against `$defs/coupling`.

### F4 — should-fix — No default-gate coupled solve has an external map that depends on w

**Where.** The stand-in and the synthetic child are both ξ = 0.25 n_N₂, T_out = T_in
(`tests/support/synthetic_child.py:10,71`). Every default-gate coupled flowsheet therefore converges at k = 1 with an
exactly zero residual.

**What only the opt-in G12 exercises.** Secant updates across real inner solves, the warm-start chain, backtracks on a
real inner failure, and the record and replay of a multi-step run with nonzero ρ. That zero residual is also why RP-2's
seam showed "exact 0 against 2 × 10⁻¹²".

**Correction.** Add a synthetic hook with a w-dependent closed form, for example ξ = X(T_in) n_N₂ with a gain in (0, 1)
through the loop. Run the loop end to end against an independent expectation (the replica driven by the same closed
form) and use it as RP-2's second case.

### F5 — should-fix — `coupling_bundle` drops the inner failure's diagnosis on `inner_failed`

**Where.** `verify/failure.py:472` `coupling_bundle`. Its docstring says "Every inner solve it judges converged"; the
attempt tree is `()`.

**Failure scenario.** A k ≥ 1 trial fails its inner solve four times, the step plus three halvings, and the run ends
`COUPLING_NOT_CONVERGED(inner_failed)`. The bundle records that the inner solve failed but not why.

**Correction.** When the reason is `inner_failed`, embed the last failed inner run's outcome and attempt tree under
`observations`, and fix the docstring.

### F6 — note — RP-2's strict xfail fails on its first assert, whatever the cause

`test_m02_wo14.py:229-233` asserts `verdict == "MATCH"` first, so a regression in D8 items 1–3 would still xfail. F1 and
F2 make the xfail go away. Until then, any interim xfail must assert the exact difference set.

### F7 — note — ρ's aggregation is not NaN-safe

**Where.** `coupling.py:253` `max(term_xi, term_t)` and `:387` `max(rho, …)`. Python's `max` drops a NaN in second
position (checked: `max(0.0, nan) == 0.0`), so a NaN term reads as ρ = 0 → CONVERGED.

**Why it is only a note.** It is unreachable today:
- the parent screens non-finite outlets (`backends.py:233-245`);
- the child nulls them (`child.py:270`);
- `_check` fails `nan <= tol`.

**Correction.** Treat a non-finite term as ρ = ∞, one line.

### F8 — note — The child's δ is not the boundary's defect (an answer to "least sure" item 2)

**Where.** `child.py:796-801` takes the element defect between the model's inlet and outlet faces. The boundary
(`boundary.py:270-285`, `DEFECT_LIMIT` 10⁻⁶) judges the raw outlet against the *requested* inlet.

**Why it is safe.** They are different quantities by design, and the difference is fail-safe:
- δ only triggers round 2;
- certificate₁/₂ decide acceptance;
- the boundary refuses independently.

If the inlet face ever departed from the request by more than 10⁻⁶ relative, the result would be an
`element_balance_defect` refusal, never a false `ok`. Measured projection defects are ≤ 1.7 × 10⁻⁹ (D78). The rest of
R-316 is as written: a NaN δ₁ triggers round 2, a non-converged round 2 is `S3`, and certificate₂ decides.

### F9 — note — D8 item 4 (D2.4 on the outer verdict) is implemented strictly, and EXT-COUPLING's flag is not D2.4's band

**Strict replay.** A replay holds the outer control flow R0 with no near-threshold path: a flip asks for an unrecorded
experiment and raises `ReplayDivergenceError`. That is safe, since it never produces a false MATCH.

**A different flag.** EXT-COUPLING's `near_threshold` is ADR 0034 D3's floor-ratio criterion (`coupled_run.py:600`), not
D2.4's q/τ ∈ [0.1, 10]. Under D2.4's band, G12's ρ = 0.29 would be flagged.

D3's criterion is the right one. The noise in ρ is ε_eval-driven, ≈ 0.017 τ, so the verdict is stable. But neither the
note nor ADR 0034 says D3 replaces D2.4 for these checks. WO-13's ADR 0034 pointer paragraph should say so in one
sentence, and should say that the outer verdict is held strictly in replay.

### F10 — note — Smaller items

- **"Outer iterations" has two meanings.** D114 reports G12 as "3 outer iterations" (final k). The code counts accepted
  iterates (`CouplingRun.outer_iterations`, the bundle's `outer_iterations`, `max_outer`), which is 4. The manifest
  should use the code's meaning.
- **v3's inert floor of 0.035 sits just above a measured S1 failure** (D105: 0.03 at 653.15 K / 11 MPa / 2.5). G11
  samples only corners and the centre. The loop's minimum request is 1.116 × the floor (D115). An in-domain S1 failure
  ends in a refusal and then an honest `COUPLING_NOT_CONVERGED`, never a false success. State it as a manifest
  limitation.
- **G8 (c)'s oracle shares `thermo.pr_c1` with the code under test.** It is independent in flowsheet structure, not in
  thermodynamics; M01 covers the latter. Say so where G8 (c) is cited as independent.
- **Self-generated outputs (item 5).** None is asserted as correctness:
  - G10/G11 records are judged against M01's bounds and the probe record;
  - G8 (f) is judged against the design lane's table through the replica;
  - G12 is judged by its certificate, with its record a regression fixture.

---

## 3. Rulings (the batched open items)

| Item | Ruling | Implementing change |
| --- | --- | --- |
| **RP-2 (a)** | **Ratify the engineer's proposal, constrained (R-317).** The check reads the inputs of the request the answer is attributed to: live, the sent request, bitwise; replay, the request recomputed at the rerun's inlet. The record keeps the served documents. | F2 |
| **RP-2 (b)** | **Reverse "ρ absolute 10⁻⁹".** It is an invented floor, which D2.2 rejects. Floors are the registered thresholds (R-317): `rho` → 1; `r_xi` → the record's `coupling_block.tau_xi_rel` (stricter than its exact threshold τ_ξ n_tot/n_N₂); `r_T` → `tau_T_K`; envelope `defect_rel` → 10⁻⁶ (ADR 0027 D3); `defect` → the flow kind's floor; `step.B` and `step.du` are reported, not compared (D2.2 comparability window: secant quantities; their R0 consequences, step kind and k, stay compared); every other new float is relative, with flows at the flow kind's floor. Scope the floors to the coupled record, like D8's shape rule; do not edit the frozen v2 policy file in a way that moves a pinned digest or any pre-M02 comparison. Recorded as **ADR 0034 Amendment 1**, written by WO-13 from this table. | F1; RP-2 un-xfailed; RP-2′ on F4's loop |
| **D94** | **Keep (R-318).** Every `constants_sha256` in a coupled bundle digests a w that Broyden computed in floating point, so by D8's own reason it is compared for shape. D8 item 2 (`final_constants`, recomputed with the *current* build at the recorded w) keeps the R0 guard on the final digest, including against a build that changed the constants. | none |
| **AC-1** | **Ratify D91's reading:** AC-1 is D9's acceptance (the guard's refusal, no coercion, the G8 records unchanged). | WO-13 adds that one line to §14.5 D9 |
| **f5 end to end** | **Required.** | F3 |
| D100, D101, D102 | Ratified. These are evidence-script mechanics, with the raw runs hash-referenced. | — |
| D105 | Ratified as a finding. | F10 limitation |
| D110, D111 | Ratified. `inert_min` is checked only when it is > 0, so v1, v2 and the stand-in are unchanged by construction. | — |
| **D112** | **Ratified.** Since `c1.reactor`'s manifest validity *is* the variant's T/P box, the stand-in → v3 transition narrows it, and the facet saying so is accurate. | — |
| D113, D114, D115 | Ratified. | F10 naming |
| D53 | Ratified (floor on the projected outlet). | — |
| `benchmarks/m02/c1-reactor.json` | **Leave on v2.** It is a registered corpus case, v2 is frozen and bindable, and re-pointing it moves the G2 dump. A v3 single-reactor case, if wanted, gets a new case id. | none |
| R-310 | **Confirmed in WO-13's scope** (§14.5 WO table l.1992: "As §9, plus D10"). | WO-13 |

---

## 4. What the build may not claim

- Cross-platform reproduction of a coupled run (until F1 and F2 land). The bitwise same-machine MATCH of G8 (d) and G12
  stands.
- Default-gate coverage of a multi-step Broyden run through the application (until F4).
