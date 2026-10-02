# T08 verdict — V13 (e), compatible warm starts (T08.A71 on T08.B40–B51)

**Lane:** design (`verdict`). **Date:** 2026-10-01. **Judged at:** `wp/T08` @ `a6165b0` (working tree clean).
**Brief:** `docs/briefs/T08-verdict-V13e.md`.
**Criterion as registered:**
- T08 release spec §4.3 clause (e) and the T08.A71 row: "FAIL unless a test shows a solve opening from a compatible warm start, the trace recording its source, the opening checks applied, and an incompatible one rejected to the next source, on B40–B51".
- Build-first spec Part B (§B1–§B5). §B5 says what judges A71.
- Rows §C.1 T08.B40–B50, with B41, B42, B46 and B50 replaced by §Am1.C (rulings §Am1.4 and §Am1.5).
- ADR 0024 and R-124.

The criterion was read before the evidence and was not re-read after it. This is an agent verdict, numerical and procedural only. It is not scientific review, and it does not set `reviewed` on anything.

## Verdict

| Row | Result | One line |
| --- | --- | --- |
| T08.B40 absent | **MET** | Fresh project: the member reads `absent` and the trace records `compatible_warm_start(absent)` with no accept or reject event. The state is equal to the `default` run's (parsed JSON, including `state_sha256`), and the verdict (`CONVERGED`/`VERIFIED`) and check ids are equal. |
| T08.B41 accepted | **MET** | The trace records `candidate(present)` then `initializer_accepted`, before `attempt_opened`, and `branch_provenance[0].initializer_source = compatible_warm_start`. The first `attempt_opened` `state_sha256` and signature equal a same-process `user_start` opening of the candidate, with no `projected(` event. The run ends `CONVERGED`/`VERIFIED`, and `source_job_id` is the source job. |
| T08.B42 never changes the problem | **MET** | Warm and cold runs have equal `revision.json`, `constants_sha256`, `model_version`, `check_policy_sha256`, check ids and verdict. The plans are equal under N, and each `plan_id` ends `-<policy>-execution`. The final states agree to ≤ 1e-9 relative, and both are within T02 §6.4's allowance of P01's high-recycle root. |
| T08.B43 incompatible | **MET** | The rename gives `warm_start_rejected(compatibility)`, then `traversal-G0-v1`. Every artifact equals the `default` run's except the policy id, the events, the member and `solve-policy.json`. The event-kind sequence is equal once the initializer events are dropped. |
| T08.B44 integrity | **MET** | The tampered stored state gives `warm_start_rejected(integrity)`, then `traversal-G0-v1`. The run ends `CONVERGED`/`VERIFIED`. |
| T08.B45 evaluation | **MET** | A constructed candidate with `S2.T = 450 K` is rejected with `warm_start_rejected(evaluation)`, then the traversal runs. The run ends `CONVERGED`. |
| T08.B46 projection | **MET** | The candidate is accepted with `projections == [["S7.n.A", -1e-12, 0.0]]`. `S7.n.A` is asserted not to be lifted by §6.2. The opening coordinate is `0.0` (asserted not `-0.0`). |
| T08.B47 replay | **MET** | Rerun bundles B41, B43 and B44 in a fresh project. Each gives `MATCH`, the rerun `warm_start` record is exactly equal and `r0_projection` is equal. The store-lookup spy saw 0 calls, and is shown live by 1 call on a normal warm solve. |
| T08.B48 selection | **MET** | The later eligible ordinal is chosen over the earlier one. A later `FAILED`-verdict run and a later out-of-lineage `VERIFIED` run both hold a solution state and are not chosen. The ancestor case is also covered. |
| T08.B49 byte identity | **MET** | `default` runs carry no member, no R0 branch and no initializer events. Every other offered policy has an empty chain, and the member is gated on the chain (`executor.py:669`). The R0 branch is inert when the member is removed. The registered-bundle and `t07` identity clauses rest on suite tests that were green in CI at `d43bf2c` and were not rerun here. |
| T08.B50 agent surface | **NOT MET at `a6165b0`** | The served descriptions digest is `171dd768…`, not the registered `6d13e13d…`; a passing test asserts the inequality. This is R-133's recorded departure, and R-133 says "criteria unchanged". The other four clauses hold (see §3). |
| **T08.B51 = V13 (e), T08.A71** | **NOT MET at `a6165b0`, as registered** | A71's four named elements are MET: B41 (opening and source), B41 (checks), B43 (rejection to the next source). B40–B49 are MET. The single failure is B50's digest clause. It was not caused by the warm-start work, and it is cleared by a design-lane amendment, not by new code (§5). |

**Decision.** Record V13 (e) **NOT MET at `a6165b0`** on T08.B50's descriptions-digest clause alone. Record the warm-start capability (A71's four elements and B40–B49) **MET** on the evidence below. The blocker is not a warm-start defect. It is a surface-identity clause that a later, separately decided change has made literally false. No warm-start re-run or new measurement is needed to clear it. What is needed is an explicit amendment of B50, recorded the way R-133 was.

## 1. What was run, and provenance

| Evidence | Produced by | Command / environment | Independent expectation? | Class |
| --- | --- | --- | --- | --- |
| `tests/test_t08_w4_warm_starts.py` | this verdict, at `a6165b0` | `PATH=.venv/bin:$PATH python -m pytest -q tests/test_t08_w4_warm_starts.py -rA`. Local x86_64 Linux, Python 3.13.5. **17 passed in 5.81 s**, exit 0. | B42 only: P01's high-recycle root (`benchmarks/syn001/reference_values.yaml`, SYN-001 §5) within T02 §6.4's allowance. Everything else is exact differential (warm vs `default`, warm vs `user_start`), spec-defined typed outcomes, or reproducibility. | tested. Numerical verification only in B42. |
| Schemas, description texts, references since `c7bbc98` | this verdict | `git diff --stat c7bbc98 HEAD -- schemas/` gives 0 lines. `t07_reference.json` and `t07_reference_c2.json` give 0 lines. Description `.md` files: only `2b50231` (T08 D-1, N1/N2: `validate.md`, `commit_change.md`). W4's range `bb4fc1a~1..ff79cbe` touches no `bindings/` and no `schemas/`. | git bytes | regression (identity) |
| Served descriptions digest | `tests/test_t08_w2_surface_digest.py` (`5d1abe0`) | asserts served `171dd768…` ≠ `6d13e13d…`; the served files differ from `v17-c2`'s in exactly the two texts; serving `v17-c2`'s two texts reproduces `6d13e13d…` | registered `v17-c2` per-file hashes (description review table, hashed at `d43bf2c`) | regression (identity). Not run here; read. |
| CI | GitHub Actions | Run `36595205458` is **success** at `2fa4232`, which contains every W4 commit (`ff79cbe`, `16dc9e8`, `843d145`). The later completed run `36851384496` at `d43bf2c` is **failure**: ubuntu-latest 5 failed / 6593 passed, arm 1 failed, default-install 1 failed. The failures seen are 4 × `test_t08_ptc_r1_diagnostic::test_the_rerun_reproduces_the_committed_record` and `test_t08_w2_description_reviews::test_every_description_is_reviewed_by_both_lanes`. None of them is a W4, surface-digest, V17-reference or identity test. The runs at `dde3221` and `a6165b0` were **in progress** when this was judged. | — | CI record |
| Design-lane review | `docs/reviews/T08-review.md` §3 item 6, S4 (fixed `16dc9e8`), N4 | read | — | reviewed (code) |
| Engineer's counts: cold 5 steps / 14 residual / 201 property calls, warm 3 / 8 / 112; warm vs cold 8.0e-15 relative | W4 engineer | not stated with a command; not asserted by any test; not re-measured here | none | **pins nothing.** No row uses them. B42's bound is the test's 1e-9, not 8.0e-15. |

**Correction to the brief.** The brief says "CI green on `wp/T08` (run on the verdict commit `2fa4232` and later)". CI was green at `2fa4232` only. Every completed run after it failed, on tests unrelated to warm starts (listed above). The W4-relevant tests did not fail in any of those runs.

**Like with like.**
- **B41.** The reference opening runs through `execute_plan` on a plan from `plan_revision(binding(warm revision.json), T08_WARM_V1)`. It runs in the same process, on the same revision and under the same policy, as §Am1.C permits. It is a differential against the registered entry path, not an oracle.
- **B42.** Warm and cold runs are in the same process and project, on the same revision. Like with like.
- **B45 and B46.** These use a candidate built from an `execute_plan` run of `SYN-001-nominal` under `T06-revision-v2`, not a store document. §B5 prescribes this.
- **B47.** The test accepts `exact_replay` or `compatible_reproduction`, a mode that depends on the environment (ADR 0007 D4). The record equality it asserts is exact in both modes. The fresh project means a lookup, had one happened, would have found nothing, and the record would then read `absent`. So the record equality and the spy are independent proofs that the candidate came from the bundle.
- **Engineer's counts.** Their measurement boundary is not stated: for example, whether the evaluation check's own residual evaluation is counted, as §B2 says it should be metered. They are not comparable evidence.

## 2. Rows B40–B49: reasoning where it is not immediate

- **B41 and "the opening checks applied" (A71).** §B5 assigns this element to B41, and the amended B41 row is fully asserted. The trace record that the checks passed is `initializer_accepted`. In the code it is emitted only inside the warm branch of attempt 0, immediately after `check_opening` returns no refusal (`region.py:1932–1968`). The five §B2 checks have the following evidence:
  - `integrity`: falsified by B44.
  - `compatibility`: falsified by B43.
  - `bounds`, projection rather than rejection: shown by B46.
  - `evaluation`: falsified by B45.
  - `opening` (T03 §5.1's six checks): **reviewed, not falsified by any test**. See finding F1. The registered row does not ask for that case, so B41 stands MET.
- **B42.** The P01 comparison is the one external oracle in this set. It covers the streams S2, S3, S4, S6 and S7 (n, T, P), both duties, `S4.N` and `S5.N`. It does not cover S1 (a fixed feed) or S5's component flows, although the helper's docstring names S1 and S5. The row does not enumerate columns.
- **B43.** The comparison maps both policy ids to one placeholder, which is equivalent to N on these files. It skips `solve-policy.json` entirely instead of comparing it under N. The equivalent statement is asserted on `as_document()`: the documents differ only in `policy_id` and `initializer_chain`. It is not asserted on the bundle bytes. The comparison is stricter than the row in one respect: the final state is compared exactly, not within ADR 0007 D2.
- **B48.** The test discriminates. Both excluded runs have higher ordinals than the chosen one and both hold a solution state, so if either exclusion were broken, that run would be selected.
- **B49.** Only `default` runs are exercised. For `T04-W12` and `T08-ptc-v1` the claim rests on two things: a test that their chains are empty, and the gate `if user_start is None and WARM_START_SOURCE in policy.initializer_chain` (`executor.py:668–669`). That is tested plus reviewed, not tested for each policy.

## 3. Row B50: clause by clause (§Am1.C text)

| Clause | At `a6165b0` |
| --- | --- |
| T08.A49's descriptions digest `6d13e13d…` unchanged | **not met.** The served digest is `171dd768efcfb24f…`, asserted by a test. The cause is N1/N2 (`2b50231`) under R-133. R-133's normative line says "criteria unchanged; this entry records the departure", and its *Watch for* names "T08.A49/B50 read as passing on `6d13e13d…` at the RC without this entry". |
| request/response schemas of `c7bbc98` unchanged | met (`schemas/` diff empty). The served input schemas are unchanged per the restore test. |
| content differences are exactly `syn001.kinetic_cstr` in `list_models` and the two T08 policies | met. Four-policy set: `test_t07_w5a_inspection.py`, `test_t07_b3_policies.py`. Thirteen builders: `test_t05_w1b_revision.py:78`. |
| G16-b 40/40 against `t07_reference_t08.json` | met in CI at `d43bf2c` (`test_t07_v17_reference.py`, not among the failures). Not rerun here. CI at `a6165b0` was in progress, after `local.py` changed in D-5. |
| `t07_reference.json`, `t07_reference_c2.json` byte-unchanged | met (git diff empty since `c7bbc98`) |

The failure is not the warm-start work's. The restore test shows that everything served apart from N1/N2's two texts reproduces `6d13e13d…`, and git shows that W4 touched neither texts nor schemas. Attribution does not amend a row, though. The row as registered names a digest that is not served at the judged commit. It is also worth knowing that at `2fa4232`, where W4 landed, no CI test asserted the served digest equal to `6d13e13d…`. The only check was `test_t07_w7a_harness`, which compares a record with the harness's own value. The engineer's "B50 digest `6d13e13d…`" therefore had no CI provenance at the time. The first test of the served digest is `5d1abe0`'s, and it asserts `171dd768…`.

## 4. Alternatives considered and rejected

1. **B50 MET under R-133.** Rejected. R-133 decides V17's carry, not V13 (e)'s B50. It states that the criteria are unchanged, and it warns against exactly this reading. A verdict cannot amend a registered row (CLAUDE.md: a failed gate stays failed, and reversing takes a new recorded decision).
2. **Judge B50 at `d43bf2c` or `2fa4232`, where the served texts still gave `6d13e13d…`.** Rejected. The brief names HEAD, and A71 is "judged at the RC", which will be at or after HEAD. A verdict on an older commit does not describe what is tagged. The fact is recorded instead: at `d43bf2c` the digest clause held. This is inferred from the restore test and the review's per-file table hashed at that commit, and it shows the failure is not W4's.
3. **INSUFFICIENT EVIDENCE for B51.** Rejected. The failing quantity is measured, and a passing test asserts it. Nothing is missing.
4. **NOT MET on F1, because the `opening` check is never shown refusing a warm candidate.** Rejected as a verdict. §B5 operationalizes "the opening checks applied" through B41's row, and that row is met. The gap is recorded as F1 instead of being silently absorbed.
5. **Treat the engineer's 3/8/112 vs 5/14/201 as evidence for (e).** Rejected. (e) requires no speed-up, the numbers are unpinned and their boundary is unstated, and one case is not optimality evidence.
6. **K02's §6.4 warm-start cache as (e).** Already rejected by R-119. Not relied on.

## 5. What would change the verdict

- **To MET, with no new measurement.** Two things are needed:
  - A design-lane amendment of T08.B50's digest clause, recorded in the register with R-133 cited. For example: "the served digest is R-133's `171dd768…`, and serving `v17-c2`'s two texts in place of N1/N2 reproduces `6d13e13d…`", which `tests/test_t08_w2_surface_digest.py` already asserts. R-133 is Frank's entry and explicitly kept the criteria, so the amendment should be put in front of him.
  - A **completed** green CI run at the judged commit, covering the W4 file, the surface-digest, V17-reference (G16-b) and identity tests.

  B50 and B51 then become MET on this evidence.
- **Re-judge at the RC commit `C` regardless.** A71 is judged at the RC. Any of the following at `C` returns V13 (e) to NOT MET on substance:
  - a red W4 test;
  - G16-b below 40/40;
  - a further surface change not covered by R-133 or the amendment;
  - a change to `executor._warm_start`, the warm branch of `region.py`, `revision_run`'s member writing or replay, or `run.identity.r0_projection` without the W4 file re-run.
- **A falsifying test for F1 that fails.** Suppose `check_opening` is forced to refuse on the warm path, and the run then does not record `warm_start_rejected(opening:<check>)` and fall through to the traversal. B41's "checks applied" and §B2 would then be contradicted, and B41 would be reopened.

## 6. What this verdict does not establish

- **No efficiency or optimality evidence.** It does not show that warm starts reduce work. One unpinned case was reported, and nothing measured it here.
- **No empirical validation or real chemistry.** The only fixture is SYN-001: one revision delta (recycle 0.5 → 0.95), one incompatible edit (an instance rename), and constructed candidates for B45 and B46. B42's agreement with P01 is numerical verification on a synthetic case.
- **No coverage of these paths:**
  - warm starts on `legacy_eo` (review N4: cold, no member; D2 narrowed to the revision route);
  - the explicit request-named source (v0.2, L-WS-2);
  - GUESS roles (source 1 on the contract path, S-G);
  - partial or adapted compatibility (L-WS-1, exact id-set identity only);
  - selection under concurrent jobs with the process executor.
- **Not that the `opening` check's refusal is wired.** That is reviewed, not tested (F1).
- **No portability claim.** The W4 file ran here on x86_64 only. CI on ubuntu-latest and arm was green at `2fa4232` only, and B47 accepts `compatible_reproduction`.
- **Nothing on V13 (a)–(d), V14 or any other gate.** No human numerical or process-modelling sign-off is claimed or implied.

## 7. Findings (recorded, not acted on)

- **F1. The `opening` check (T03 §5.1) on the warm path is not falsified by any test.** A mutation that removed the `check_opening` call at `region.py:1940` would pass all 17 W4 tests. The S4 tests monkeypatch `_solve_region` and bypass the call. The review's D3 note says bounds are flows ≥ 0, which `project_bounds` already enforces, so a refusal may be unreachable from a candidate that passed the earlier checks. The smallest closing test therefore injects the fault: monkeypatch `check_opening`, as imported in `region.py`, to return a refusal on the warm path, then assert:
  - the record `rejected` / `opening:<check>`;
  - the trace `warm_start_rejected(opening:<check>)`;
  - `traversal-G0-v1` follows;
  - the run ends `CONVERGED`.
- **F2. B50's digest clause ties V13 (e) to the whole surface's digest**, which unrelated changes can move. The property it protects for (e) is that the warm-start work left the surface unchanged. The restore test and the W4 range's empty `bindings/`/`schemas/` diff state that property more precisely. This is the basis for the §5 amendment.
- **F3.** The brief's CI statement is inaccurate (§1).
- **F4.** B42's P01 helper says it covers S1 and S5, but it compares neither S1 nor S5's component flows (§2).

## 8. Limitations that must travel with this decision (manifest and release report)

- V13 (e) is **NOT MET at `a6165b0`**, solely on T08.B50's descriptions-digest clause: R-133's departure, `171dd768…` ≠ `6d13e13d…`. A71's four elements and B40–B49 are MET.
- Evidence classes:
  - B40–B49 are *tested*. Only B42's comparison against P01 is numerical verification against an independent expectation.
  - The rest are exact differential, reproducibility or regression checks.
  - B50 is regression identity.
  - There is no empirical validation and no optimality evidence.
- F1: the `opening` check's wiring on the warm path is reviewed, not tested.
- Envelope limitations L-WS-1, L-WS-2 and L10. Review N4: warm starts on the revision route only.
- This is a pre-RC verdict. It must be re-confirmed at `C` with a completed CI run.
- CI provenance: green at `2fa4232`. Completed runs since then are red on unrelated tests. HEAD's run was in progress when this was judged.
