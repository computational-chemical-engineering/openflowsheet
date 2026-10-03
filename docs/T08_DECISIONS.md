# T08 — decisions log

Append-only; grepped, never read whole.

## 2026-09-29

T08 opened on `wp/T08` from `main` `16c4fbd`. Gate ledger `docs/t08-gate-ledger.md` (recon, corrected).
Specifier brief `docs/briefs/T08-specification.md`; specification round running.

Peer session process-simulator-75 (web-shell / M06 gap triage, `design/web-shell-brief` `b876a2b`
`docs/design/web-shell/gap-triage.md`) reported record defects on main `5c1f8ac`, added to the T08
specification round:
- D1 `validation.py:385` STR-03 names the SYN-001 binder's `U-HEAT` instead of the instance id.
- D2 `verify/failure.py:188` `bundle_for` reads `getattr(result, "plan")`, absent on the region view →
  empty `replay_identity` in region failure bundles; revision-path certificate policy_id/plan_id empty
  (replay identity; design-lane review).
- D3 failure bundles report `property_calls` 0 where the trace says 202 (hypothesis: executor meter at
  `orchestrator/executor.py:883` not in region counters).
Contract asks for M06 (each an ADR 0019 amendment; v0.2 backlog, not T08): inspect_structure returns the
validation structural report when no route binds; spec→rows map; `NewtonResult.blocked_by` in failure
observations; `list_audit`; operations with rights in get_project. `commit_change` assigning
`rev-NNNNNN` is intended (design §5.2).

## 2026-09-29 — Frank's answers to the specification's F1–F3

- **F1 (V14, qualified PTC) → build first.** Not the default "tag with the clause recorded FAIL": the holdup
  CSTR that qualifies PTC is built before the tag (spec estimate 1–2 weeks). Needs a design-lane pass
  (the holdup model and the PTC mapping are residual/derivation work).
- **F2 (V13, warm starts) → build first** (spec estimate about a week). Design-lane pass needed.
- **F3 (V19) → C1, the ammonia synthesis loop.** Frank: the licences should be fine, it should be MIT.
  Checked 2026-09-29: `pymrm` is MIT; the group repository
  (`gitlab.tue.nl:SMM/research_projects/eajfpeters/ammonia_synthesis_reactor`, local
  `~/Codes/ammonia_synthesis_reactor`) has no LICENSE file and no licence field in `pyproject.toml` or
  README. Taken as Frank's statement that the repository is MIT; asked him to add the LICENSE file so the
  rights table (T08.A64) can cite it. Still open from H2/H5: which published rate law the kinetics class
  implements, and the permitted use of the Rossetti et al. dataset and the property coefficients.
- **F5 (V17)** — Frank did not follow the question; explained. **F4** not yet answered.
- Consequence: ADR 0021's "tag with V13/V14 clauses FAIL" path is not taken; the ADR is revised before
  acceptance. Still paused for budget until Frank says continue.

## 2026-09-29 — F4 approved; the build-first design pass

- **F4 → approved** (Frank): the `t07` identity key may move by substitution only for the D2/D3 fixes
  (spec §6.2, T08.A13). Any other moved byte stops the work.
- Frank: "Do the design-lane and then pause." One `specifier` pass covers both builds (brief
  `docs/briefs/T08-build-first-spec.md`): Part A, the kinetic CSTR with holdup realising T04 §8.4's
  preregistered PTC-R1 for V14 (b); Part B, compatible warm starts for V13 (e). One agent rather than
  specifier + architect, for the budget; the brief lets it name a separate architect pass if it judges one
  necessary. After it reports: commit, relay questions, **pause** for Frank (continue or wait for a reset).

## 2026-09-29 — Frank: "The defaults are good, please continue"

Build-first spec §F/§G answered with the defaults: **F5** yes — one more model in `list_models` and two
policies in `get_project` (content only; no schema, description or tool change) keep V17's carry;
**Q-A2** V14 (b) judged per platform, both must pass; **Q-B1** the request-named warm start is v0.2 (M03);
**Q-A1** one reaction, the γ → ∞ synthetic law. Q-A3/Q-B2/Q-B4 take the spec's defaults (design, not
Frank's). Work resumes: W1 (C_reg) → W2 kinetic CSTR → W3 C_case → W4 warm starts → ask Frank before the
`reviewer` pass and before W5's comparison runs (budget memory).

## 2026-09-29 — W2 landed (`e924d13`…`7467d52`); two design-lane questions

W2 (`opus-engineer`): `syn001.kinetic_cstr`, the 13th of `MODEL_BUILDERS`; B10–B19 and B26 pass
(identity unchanged: whole document `3ed2911b…`, `t07` `11bcb148…`); `check.sh` green, 6405 passed. No PTC or
Newton run from any registered PTC-R1 start. Q-A4: no caller of `UnitModel.evaluate` treats it as an answer
(revision traversal starts, T06 ensemble starts, the tear residual).

Engineer decisions, each its own commit, for the `reviewer`:
- D1 (`b989366`) the key names `damkohler.{key}`; the phase configuration is the outlet's declared phase.
- D2 (`b468d19`) `ModelMassRule.outflows` takes the declared phase as a third argument; `MassMapping.phases`
  filled by `declared_phases()` in `executor._mass_mapping` (§A3.1 said nothing else in `mass.py` changes).
- D3 (`2b115d3`) §A1.6's `cooling_relation.<U>` is issued as `energy_balance.<U>.cooling_relation` (check ids
  must start with a frozen category).
- D4 (`2b115d3`) the CSTR joins `EXTERNAL_DUTY_MODELS` and `REACTING_MODELS`.

Open for the design lane, **before C_case**:
- **Q1** PTC-R1 on `[A, B]` cannot be bound: `canonical_components` (`models/revision_flowsheet.py:221–240`,
  ADR 0014 D9, R-076) requires a permutation of `(A, B, C)`, and the SYN-001 flash (R-007 admission) is
  three-component. Engineer's proposal: amend §A1.5/§A2/§A4.2 to `(A, B, C)` with `C = 0` in the feed and every
  start (`S1.n.C = S2.n.C = 0.0`); B13's row set gains `CSTR-mole:C`, B14 a second `−1/θ` eigenvalue. The
  PTC-R1 dynamics on (A, B, T) are unchanged (steps agree with the YAML to 1e-13).
- **Q2** B17 on the EO rows: the compiled residual reports `invalid_trial_state` (the frozen
  `evaluation-result` schema has no `out_of_domain`); `temperature_outside_domain(outlet)` comes from the
  evaluator only. Proposal: amend B17 to say so. (A doubled message prefix `H_S2_vapor: H_S2_vapor:` in
  `casadi_backend`/`blocks.py` recorded, not fixed.)

DECISION: order while Q1/Q2 wait → W4 (warm starts; independent of Q1) next; the Q1/Q2 amendment by a
fresh, tightly-briefed `specifier` after Frank's OK (budget). Alternative: run the amendment first.
Reversible by: reordering; nothing is committed on either side.

## 2026-09-29 — W4 landed (`bb4fc1a`…`ff79cbe`); check.sh RED on 5 tests; three more design-lane questions

W4 (`opus-engineer`): compatible warm starts. Q-B3: project `read` covers all jobs (`authz.py:65-81`, `:136`;
T07 design :1098), so the lookup reads other principals' runs. Target (recycle 0.95) certifies cold: cold 5
steps / 201 property calls, warm 3 / 112; states agree to 8.0e-15. B40, B43–B49 and B26 pass (identity
unchanged, `3ed2911b…`). **`check.sh` is red on `wp/T08`: 5 failed, 6414 passed** — all from offering
`T08-warm-v1` (Stop 1). Left red deliberately until the design lane rules; not merged.

For the design lane (to go with W2's Q1/Q2, one amendment pass):
- **Stop 1 (B50 / T08.A49 / V17).** T10-C3 (`docs/derivations/T07-v17-tasks-spec.md:746`) and
  `t07_reference.py:97` `OFFERED_POLICIES` pin `offered_policy_ids == {T04-W12, T06-revision-v2}`; G16-b drops
  to 36/40 and fixture `project_summary/valid/two_revisions_one_job.json` pins `solve_policies`. §B3 missed
  this pin. `T08-ptc-v1` will hit the same pin. Options: (a) amend T10-C3/`OFFERED_POLICIES` (Frank's F5
  already rules content additions keep the carry); (b) an unlisted admissible policy (new contract decision);
  (c) other.
- **Q-W4-1 (B41).** T05b §6.2 (`region.py` `current.update(kernel)`) overwrites lifted splits after the
  candidate enters, so the opening differs ~3e-16 relative from the candidate: amend B41 (compare after §6.2)
  or change §6.2 for this source (a numerics change).
- **Q-W4-2 (B42).** `plan_id = f"{label}-{policy_id}-execution"` (`orchestrator/execution.py:776`), so warm
  and cold differ by construction: amend B42 to "equal modulo the policy id".

Engineer decisions for the `reviewer`: D1 (`3097858`) `T08-warm-v1` offered but not in
`benchmarks/registry.yaml`/`REGISTERED_POLICY_IDS` (T06 registry holds exactly its registrations); hash
`32f484a1…` pinned in W4 tests. D2 lookup/record only on `revision_eo`; a plan refused before any region
writes no member (narrows §B2 slightly). D3 the check interpretations (opening after §6.2, bounds = flows ≥ 0,
integrity = `solution_state` checks 1–3, evaluation cost counted, verdict from
`worker_result.run.verification_status`).

## 2026-09-29 — Phase 1 fixes landed (`2476186`…`0c824e0`)

W1.0, W1.2 (D1), W1.3 (D3), W1.4 (D2), W1.5, W1.7, W1.8 done (`opus-engineer`, brief
`docs/briefs/T08-phase1-fixes.md`). `check.sh`: 6439 passed, **5 failed (the known W4/Stop-1 tests only)**,
2 xfailed. **The `t07` key did not move** (`11bcb148…`; whole document `3ed2911b…`): the R0 projection keeps
neither `replay_identity` nor certificate ids. Bundle-level diff old→new: certificates only `/policy_id`,
`/plan_id`; failure bundles only `/replay_identity/*`, `/observations/counters/*` (test
`tests/test_t08_w1_identity_substitution.py`). D3's cause: property calls are metered into the plan trace and
never reached `RegionResult.counters` (plus the pre-solve and the failed first solve before edge 3); (b)
NET-02: 0 → 202. A14 (i): the `rank.py` error is unreachable (405 pressure-only rows over 58 declarations).

Engineer decisions for the `reviewer`: two T07 regression digests re-baselined by the D1 substitution only
(G-R6-2 `5b92f32e…`→`a8b389b2…`, S3-7 `eedea852…`→`0411fe71…`, reverse-substitution kept as the check);
counters are the step meter (initializer_bundle precedent); T04 fixture `t04_hom04_homotopy_stalled.json`
regenerated (counters only); certificate ids filled in `solve_route`, verifier untouched.

Not done: the RC bundle set's campaign record (with the RC job, §8.2); v17 harness `run.json` lock hash;
`scripts/t04_schema_fixtures.py` passes no plan; W1.1 ledger; W1.6 A89 (needs aarch64 CI).

Added to the pending design-lane amendment (with Q1, Q2, Stop 1, Q-W4-1, Q-W4-2):
- **Q-P1-1** the initializer failure bundle keeps an empty `replay_identity` (T07 ruling round 3 Q1 item 3,
  pinned `e07f19c5…`, `6eeb7757…`); spec rule 5 argues for filling it (one line). Default: amend and fill.
- **Q-P1-2** STR-04/STR-05 messages still print binder ids (`U-MIX`…, pinned in
  `tests/fixtures/t07/cli-existing-commands.json`); extend D1's rule to them?
W1.3, W1.4 (replay identity) and W1.5 (verifier path) are **R** — they join the W2–W4 `reviewer` pass.

## 2026-09-29 — Frank: extend D1; run the amendment and the reviewer pass

- **Q-P1-2 → yes** (Frank): D1's rule (instance ids, not binder ids) extends to STR-04 and STR-05 messages.
  The pinned fixture `tests/fixtures/t07/cli-existing-commands.json` moves by that substitution only.
- "Then continue and perform the reviewer pass": the design-lane amendment (Q1, Q2, Stop 1, Q-W4-1, Q-W4-2,
  Q-P1-1) → build lane applies it, D1 extension, W3 (`C_case`) → one `reviewer` pass on W2–W4, W3's harness and
  Phase 1's R items (W1.3, W1.4, W1.5) → **ask Frank before W5's 882 comparison runs**.

## 2026-09-29 — Amendment 1 committed (`C_A1`)

`specifier` ruled the six questions (build-first spec, Amendment 1):
- **Q1** PTC-R1 binds on (A, B, C) with **C a trace of 2⁻¹⁰ mol/s** taken from A's feed (`ν_C = 0`), not C = 0:
  at C = 0 both C columns sit on their bound and roundoff step components (≤ 2.3e-16, mostly negative) would
  make T04 §7.3 reject nearly every PTC pseudo-step (`ptc.py:435` has no R-064 release) — the arms would
  differ by arithmetic, breaking (b2). B, β, T_s, roots, separatrix distance, basin labels unchanged; starts
  digest → `0262bebc…`; new B28 (trace inert); git order `C_reg → C_A1 → C_case → C_res`.
- **Q2** B17 split: `evaluate` → `out_of_domain`; EO rows → `invalid_trial_state` (message by `re.search`).
  Doubled prefix recorded (H-A1-3), not fixed.
- **Stop 1** a third reference `t07_reference_t08.json` (`f946a88f…`, `--emit-t08`) = v17-c2's with only the
  offered set `{T04-W12, T06-revision-v2, T08-ptc-v1, T08-warm-v1}` and a `carry` member (GC-17); G16-b is
  scored against it from T08 on; c1/c2 references (`cba24a92…`, `23b924b8…`) unchanged, not re-scored.
- **Q-W4-1** B41 compares with a `user_start` opening of the candidate's values, plus no `projected(` event.
- **Q-W4-2** B42 compares `execution-plan.json` modulo the policy id and `initializer_chain`.
- **Q-P1-1** fill the initializer bundle's `replay_identity`; only the pinned digests `e07f19c5…`, `6eeb7757…`
  move, by substitution; no identity key moves.
Findings H-A1-1/H-A1-2 (PTC core lacks R-064's release; roundoff drift off a bound) → open A1-O1, v0.2-side.
Checks: build-first `--check` 570/570 (YAML `98b3a43e…`); `t07_reference.py --check` passes; `t08_reference`
126/126. Register text R-A1a/R-A1b to be numbered R-126/R-127 by the build lane.

## 2026-09-29 — Amendment 1 applied; `C_case` = `c337fa1`

Items 1–6 on `wp/T08` (`47b6c5f`…`f9a7f66`): R-126/R-127 registered; W2 tests on the C trace; **`C_case`
`c337fa1143a9…`** (`revision.json` `1a85dfd9…`, `case.json` with C_reg, C_A1, YAML `98b3a43e…`, starts
`0262bebc…`, policies newton `c75e3532…`, ptc `11be2aee…`, `T08-ptc-v1` `aa0f1257…`, `T08-warm-v1` `32f484a1…`;
harness committed not run); `T08-ptc-v1` offered, G16-b 40/40 on `t07_reference_t08.json` (**check.sh green,
6477 passed**); B41/B42/B46 amended tests; Q-P1-1 filled (UL-C3X `e07f19c5…`→`7a3c76f1…`, A02-360-no-guess
`6eeb7757…`→`f2cc8c5a…`, by substitution). Identity unchanged.

Held: **D1 → STR-05** on side branch `wp/T08-d1-str05` (`18ccc00`): moves the **`t07` key** `11bcb148…` →
`422aa7a5…` (whole K05 `3ed2911b…` → `7f32b143…`) by substitution only (38 STR-05 messages; reverse
reproduces). Needs Frank's approval (his F4 covered D2/D3). Open for the design lane, sent to the `reviewer`
for a recommended ruling: P-STR04 (no D1 rule for row/parameter ids), P-budget (spec says no property budget,
arms carry T06-revision-v2's 10000 cap as registered), P-trace (1e-12 in YAML vs 1e-10 in B21).

## 2026-09-29 — review fixes landed; W5 ready

`e3518ef` S1–S3 (harness), `16dc9e8` S4 (warm-start no-attempt end → `rejected(opening:…)`), `21d8c51` S7
(`step_index` keyword-required; None refused on a plan trace), `a1c2a11` Amendment 2 = R-128 (P-budget,
P-trace erratum), `485f944` dispatch-only CI job `ptc-r1` (both machine classes, threads 1, 360 min). check.sh
green at `485f944`: 6484 passed; identity byte-equal. The session added (after the engineer's report, its
questions 1, 2 and review N7): `runs_without_exactly_one_attempt`, `crashes_with_typed_outcome`, strict JSON —
recording-only; `case.json` unchanged. Left: N3, N4 (notes), the YAML's `max_property_calls: null` (review
calls it intent; not declared an erratum). The review's LOW-root probe (one per arm, after C_case, not a
registered start) must be attested in the manifest (W6).

Side branch `wp/T08-d1-str05` head `26f2465` (rebased on `485f944`): D1 → STR-03/04/05 via
`binding.instance_named`. Combined identity move for Frank: **`t07` `11bcb148…` → `422aa7a5…`, whole K05
`3ed2911b…` → `7f32b143…`**, all else unchanged; reverse substitution reproduces. STR-04 moves no registered
identity.

## 2026-09-29 — Frank: run W5 now (with the verdict); approve the t07 key move

- **W5 → "Run it now"**: push `wp/T08`, dispatch the `ptc-r1` CI job on both machine classes, commit the
  results as `C_res`, then one `verdict` pass on V14 (b).
- **t07 key move → approved**: side branch merged (`3054942`); `t07` `11bcb148…` → `422aa7a5…`, whole K05
  `3ed2911b…` → `7f32b143…`, substitution only. From here the registered `t07` value for T08 is `422aa7a5…`.

## 2026-09-29 — Verdict: V14 (b) FAIL on PTC-R1 (the saddle clause)

`docs/reviews/T08-verdict-V14b.md` (`verdict`): **V14 (b1) NOT MET on both registered platforms; V14 (b) FAIL.**
B21 MET (882 typed runs per platform; 880 CONVERGED, all VERIFIED; C trace ≤ 1.07e-16; no bound blocks; one
attempt per run; max property calls 1402). B22 MET (`S_ptc ⊄ S_newton`, the same 84 starts on each platform).
**B23 NOT MET: PTC ends at the saddle (MID) from 149 starts**, all CONVERGED/VERIFIED within 6.54e-11 of it.
B28 MET. B20 INSUFFICIENT EVIDENCE only for the missing W6 manifest attestation (it must disclose the reviewer's
LOW-root probe, the aborted first ref invocation, and the post-C_case `src/` changes, found inert). Classes
re-derived independently on all 2 646 records; platforms agree on every outcome and step count.
Not established: why PTC converges to the saddle (hypothesis: SER step passes 2/s₊ ≈ 8.3 s by step 4, T04 §7.7
settings; step histories not recorded — a diagnostic, not a new criterion). PTC stays experimental. Under ADR 0021
(proposed revision 1, R-125) the tag question returns to Frank: carry V14 (b) FAIL or hold the tag.

## 2026-09-29 — Frank: carry V14 (b) FAIL; run the diagnostic; continue T08

"One the PTC: 1 and 3. Then continue T08." → D3 row added to ADR 0021 (V14 (b) carried as FAIL, PTC
experimental). Diagnostic: step-size (Δτ) and distance-to-MID histories of the 149 PTC saddle runs, as a
separate diagnostic script whose output is not a result of the registered comparison and changes no verdict.
Then T08 continues: V13 (e) verdict, W6 manifest, W1.1 ledger, W1.6 A89, release-spec Phases 2–5; one agent at a
time.

## 2026-09-29 — PTC-R1 saddle diagnostic (`e9c27bd`…`6f8e03e`; not a result, changes no verdict)

233 PTC re-runs (149 MID, 84 controls from `S_ptc \ S_newton`) byte-equal to the committed records. Every MID
run first takes Δτ > 2/s₊ (8.32 s) at step 4 (148) or 5 (1); from there the distance to MID never increases in
145/149. No rejected trials; polish accepted in all. **But the controls cross 2/s₊ too** (48 of 84 at step 4) and
end LOW/HIGH, and the MID runs already approach MID in their first three small-Δτ steps (median distance 3.71 →
1.08; controls 0.91 → 0.39). So the SER growth finishes an approach the early steps began; which of the two selects
MID is open (no registered neighbourhood radius). v0.2 input for any new PTC preregistration.

## 2026-09-29 — Phase 2a: W1.1, W2.1–W2.3 landed; W2.4 not started

`b19c7d7` ledger (T08.A02, V18–V20 manifest clause skipped until W5.3), `b97125c` alias threshold (A24),
`9b62ca2`+`fbd07ed` envelope/support matrix (A20, A22, A23: 20 operations, 13 models, 4 policies, 13 U-rows),
`990d0a2` harvest draft (A21: 18 manifests, 256 items → E 90, S 41, P 123, B 2). check.sh 6567 passed, 3 skipped;
no `src/`/schema/spec change. **W2.4 (T08.A33, recovery-edge inventory) not started** (engineer context limit);
proposed mechanism: `benchmarks/t08/recovery_edges.yaml` rows E1–E13 + `not_an_edge`, bijection with labels read
from code (Literal types and scanned sites listed in the engineer's handoff).

Open for the design lane (to batch with the W2.2/W2.4 review):
- **U05** contradicted by code: `validate(task="optimization")` returns `READY_FOR_OPTIMIZATION`
  (`application/validation.py:293`); U05 withdrawn from the envelope pending a ruling (amend U05, or a rule-5 defect).
- **§5.2 components** "any non-empty subset of {A,B,C}" contradicted by `canonical_components`
  (`models/revision_flowsheet.py:228`, T06 A60): the envelope states "a permutation"; spec :186 needs amending.
- **L10** seed text stale (warm starts exist); restated.
- Harvest rules chosen by the build lane (E→U-row pointers, multi-pointers, S→document pointers); new rows
  L18–L35 (L22 broad).
- W2.4: E5 (structural-zero release) emits no label; E10's refusal codes unmapped; unchanged-physics evidence
  explicit only for E3a — what counts for E1, E3b, E4.
- T07 L3: the design-lane text review of the 17 MCP descriptions is still `pending_design_review` — open before release.

## 2026-09-29 — W2.4 landed (`35f4cee`); T08.A33 fails honestly on 5 rows

`docs/recovery-edges.yaml` E1–E13 + `not_an_edge`; `tests/test_t08_w2_recovery_edges.py`: labels read from code
(Literal types + AST scan), 37 code labels, **bijection holds**; 38 cited nodes pass. **A33 fails on E1, E5, E10,
E11, E12** (enabled, no unchanged-physics evidence) — five red parameters, no xfail; `check.sh` red on exactly
those. DECISION (engineer): inventory in `docs/`, not `benchmarks/t08/`, because three registered literal guards
forbid the refined-core / edge-3 / phase-contract literals in YAML under `benchmarks/` and `tests/fixtures/`.
Reversible by `git mv` + one path constant.

Added to the design-lane batch: (1) evidence for E1/E5/E10/E11/E12 — new identity-comparing tests or an accepted
structural argument (engineer recommends a small identity test per row on a real model); (2) whether a VERIFIED
certificate (its guard refuses changed model_version/constants/revision) and T03 A16's injected-identity guard
count as unchanged-physics evidence (E3b, E4, E6, E7, E8 rest on them); (3) E7: the failure-triggered `tp` has only
a kernel-level test; (4) E1/E2 marked `default` but unreachable by any v0.1 application policy; (5) E5 emits no
trace label; (6) E9 has no K03 counterpart; (7) the CLI `replay --rerun` falls back to SYN-001-nominal for an
unknown run id (`application/cli.py:183`; T07 design §12.3, D-Q6) — a registered limitation, or a rule-5 defect?;
(8) the inventory's location.

## 2026-10-01 — Review 2 (`ce538ef`): M3, S9, N9; 13 rulings

`docs/reviews/T08-review-2.md`. M1 the inventory misses `select_route`'s binder-refusal → `legacy_eo` fallback
(reachable by default; the bijection claim was false). M2 U05: `READY_FOR_OPTIMIZATION` without an optimizer is a
rule-5 placeholder → typed `task_unsupported`. M3 CLI `replay --rerun` compares every revision-built bundle with a
SYN-001-nominal rerun (false MISMATCH) → route through `reproduce_bundle`; reverses T07 D-Q6 by a new register entry.
Rulings: components "exactly a permutation"; harvest rules tightened (handed-on defects never P → B10); one identity
test per edge E1/E5/E7/E10/E12 (no bare structural argument); certificate and guard evidence count with conditions;
E1/E2 `library-only`; E5 unlabeled OK for v0.1 (L39, backlog B11); inventory stays in `docs/`; **T07 L3 blocks the
RC: a separate design-lane review of the 17 MCP descriptions (T08.A18 red until then).**
Build lane: part A (code + tests + inventory, brief `docs/briefs/T08-review-2-fixes-a.md`), part B (spec/envelope/
harvest transcription), then the description review, then the V13 (e) verdict.

## 2026-10-01 — Review 2 part A landed (`46dcf74`…`70811b3`)

U05 refused (`task_unsupported(optimization)`, audited in `validate`; CLI exit 14); CLI `--rerun` through
`reproduce_bundle` (T08.A17); edge identity tests E1, E5, E10, E12 + T03 A16 `constants_sha256`; E1/E2
`library-only` with reachability tests; `route_fallback:legacy_eo` family (M1); **T08.A33 green on every row**;
T08.A18 red as intended (17 descriptions await the design-lane review). check.sh: 6599 passed, 1 failed (A18), 3
skipped. Identity unchanged (`7f32b143…`, `t07` `422aa7a5…`).

Open:
- **E7 (Ruling 7's stop condition hit):** on CH-UP-DP under its default route/policy, the patched `_ph_closure` is
  never called. From B31's own start (traversal at Q=0) the patch fires 3×, records `fallback(…, tp)` and ends typed
  `ACTIVE_SET_CYCLING`. Design lane: accept that start, or E7 evidence `null` (red)? → to the description review pass.
- DECISION (engineer, `dc3de6b`): Ruling 8's reachability test exempts models without an outlet port
  (`{syn001.product_sink}`; it declares `unavailable`). Alternative: drop the exemption. Reversible by reverting
  `dc3de6b`. → confirm in the next design-lane pass.
- S6 not done: the ruling's restriction still leaves 4 false positives (`admission.py:188`, `runner.py:251,336,409`).
  Engineer proposes restricting the fail-closed rule to `orchestrator/`, `numerics/`, `verify/`.
- `commit_change`/`preview_change` with `task == "optimization"` raise U05's error from `_prepare` unaudited
  (`local.py:1310`) — audit it (build lane).
- **`bindings/descriptions/validate.md:1` still advertises `READY_FOR_OPTIMIZATION`** — now false. Fixing it
  changes an MCP description, which moves T08.A49/B50's digest and reopens V17's carry (F5 covered content-only
  additions). Goes with the description review; then to Frank.

## 2026-10-01 — Review 2 part B landed (`bc5d6a5`, `c9b9765`, `cf39cef`) + generator follow-up

Spec Amendment R2, envelope/harvest edits, matrix regenerated, register R-129…R-132 (next free R-133, ADR 0025).
The session made the two generator edits the transcription could not: A21 accepts a backlog id among an E item's
pointers (still requiring one envelope row), and the catalogue gains T08.A17/A18 (YAML `89679712…`).
Next: the design-lane description review (brief `docs/briefs/T08-description-review.md`).

## 2026-10-01 — Description review (`3685517`); Frank keeps V17's carry

Design-lane review: 15 descriptions approved by sha256; **necessary**: `validate.md` (N1, false since U05) and one
sentence of `commit_change.md` (N2, false since T07); optional O1–O4 deferred to v0.2. Rulings: E7 on B31's start
under `T06-revision-v2` (patched vs unpatched, identity compared); Ruling 8's exemption confirmed; S6 both clauses.
**Frank (2026-10-01): "Keep the carry"** — V17 carried across the U05 behaviour change and the two description fixes;
no new campaign; his human review of the two changed files lapses and he re-reviews them (T08.A18 red until then).
Engineer brief `docs/briefs/T08-description-fixes.md`.

## 2026-10-01 — Description fixes landed (`2b50231`…`e2fcc01`)

N1/N2 applied; REVIEW.json: design-lane review of all 17 recorded (2026-10-01), Frank's human review of `validate`
and `commit_change` back to pending. New descriptions digest `171dd768…` registered beside v17-c2's `6d13e13d…`
(test: differs in exactly the two files; restoring them reproduces the old digest). R-133 (V17 carry). S6: 47 kind
arguments scanned, 0 flagged. `_prepare` refuses optimization, audited. Identity unchanged. check.sh 6605 passed, **2
red**: T08.A18 (Frank's two human re-reviews) and **T08.A33[E7]** (Ruling 1's stop condition hit: the region entry
and the full revision solve both contradict its assertions; the full solve under fault injection is VERIFIED with
the failure-triggered `fallback(U-PHF, tp)` — proposed as Ruling 6 `verified_certificate` evidence; asked the
description reviewer for a follow-up ruling). Leftovers: A49/B50 spec rows still name `6d13e13d…` (R-133 records the
departure); gate ledger says Frank reviewed all 17; U05 envelope row lacks the D-5 node; validate.md says 1188
characters (review said 1190, blockquote prefix).

## 2026-10-01 — E7 closed (`499e1c6`); T08.A33 green on every row

E7 test per the description review's addendum: full revision solve, patched `_ph_closure` → 3 calls (U-PHF ×2,
U-PHF2 ×1, feeds flowing), `fallback(U-PHF, tp)` recorded, CONVERGED, VERIFIED, certificate identity equal to the
declaration; unpatched has no `fallback(U-PHF, tp)`. Envelope U05 cites the D-5 node (`b469c9e`); gate ledger
corrected (`94a81ec`). check.sh 6607 passed, **1 red: T08.A18** (Frank's re-review of validate.md and
commit_change.md). Next: V13 (e) verdict.

## 2026-10-01 — V13 (e) verdict: NOT MET at `a6165b0` solely on B50's registered digest

`docs/reviews/T08-verdict-V13e.md`: B40–B49 MET (all four things A71 names shown); **B50 NOT MET** because its row
pins the descriptions digest `6d13e13d…` and the served digest is `171dd768…` after the 2026-10-01 fixes (R-133,
Frank). The verdict will not read B50 as met against R-133's "criteria unchanged". **Needs Frank:** amend B50's
digest clause to `171dd768…` (evidence: the decomposition test — the digests differ in exactly validate.md and
commit_change.md), after which V13 (e) is MET on existing evidence, to re-confirm at the RC. Not established: no
test makes the T03 §5.1 opening check refuse a warm candidate (wiring by review only) — add one; no speed-up test.

CI finding: run 36851384496 (ubuntu-latest) failed 4 diagnostic reproduction cases — GitHub's ci-x86-64 runners
vary CPU model. Fixed: the test claims bit-equality only on the producing CPU model (`ADR 0007 F1`). Runs at
`dde3221` failed only on the then-expected A18/E7.

## 2026-10-01 — Phase 2b landed (`a6fd912`…`3b4a613`); a licence finding for Frank

A30 inventory x86-64: 381 objects (266 distinct) in 8 compiled distributions; required closure 150; CasADi's 232
objects hash-identical to P03; ADR 0006 D4's eight unresolved and D2's METIS carrier re-derived; METIS closure
unreachable. **Finding: `libgfortran` (GPL-3.0-with-GCC-exception, per numpy's and scipy's `LICENSE.txt`) is in the
default install's required closure and is loaded** (numpy → libscipy_openblas64_ → libgfortran); not dispositioned
by ADR 0006 D4 → T08.A30 verdict node red on purpose (`14f1f57`, revertible) → **Frank** (blueprint §15 reading,
as ADR 0006 Q1). Also to confirm: libquadmath (LGPL-2.1-or-later) counted under Q1's "LGPL allowed" (Q1 was asked
about LGPL-3.0). A35 met (v0.0.0 bundle → `inspected_archived_results`/NOT_RUN, inspect renders). A89 local
repetition: CONVERGED, VERIFIED, ratio 2.1663e-5, 1 refinement. Warm-start opening-refusal test added (V13 (e) gap
closed). L40 added (reference-tool data and OpenIDAES-450 not distributed in sdist/wheel). README's stale
"LICENSE deliberately absent" fixed (`1103311`). Dispatched CI 36868221999 (`a30_inventory`, `a89_repeats` on aarch64).

## 2026-10-01 — aarch64 halves committed

A30 aarch64 PASS (308 objects, required closure 147, none undispositioned, METIS unreachable); **two new unresolved
notices in CasADi's aarch64 wheel** (`libgfortran-8de1544a.so.5.0.0`, `libgomp-7eb2fb8b.so.1.0.0`), outside the
required closure — mode-B notice items to list in ADR 0006's D4 at the next amendment (design lane). A89: 20/20 on
aarch64 + 1 on ref-x86-64 meet the registered outcome (count 1 each) → the design lane amends T06 A89 (spec §6.1,
Q4 default) in the Phase 5 pass.

## 2026-10-01 — Phase 3 landed (`7c042a0`, `68dc5b2`, `31bc6ff`); questions for Frank

- **T08.A61 FAILS at the group repo's HEAD `a6ee9ef`**: the regression harness dies (`AttributeError ... c_p`) — the
  harness was not updated after `a8b3a24`'s restructuring; at `306b900` it reproduces the reference bit-identically.
  Non-isothermal 1D solves fail at HEAD (`c5814c5` made `lambda_mem` a function of T; the 1D model still divides by
  it; `Perm_NH3` silently dropped). At `1808d67` one non-isothermal solve converges in 1.416 s (element balance H
  1.06e-2 vs the group's 1e-3). No-membrane (Q6) runs: 0.48 s isothermal, 1.38 s non-isothermal.
- Provenance: rate law Rossetti et al. I&ECR 45 (2006) 4150 (Ru/C, Temkin-type), as transcribed in Gargiulo et al.
  2025 (IJHE 166, 150995, CC BY) Eq. 2/Table 1 and Simpelaar's MSc report; code matches line by line except no λ(q)
  and K_NH3 7000 cal (29 288 J) vs 29 228 J in Gargiulo Table 1. CSV: 19 rows (not 18), unit and Rossetti table/figure
  not determinable from the repo.
- IDAES 2.13: PR with light gases vapour-only gives a sensible separator (K_NH3 0.0615); full PR VLE lands on the
  trivial solution / fails; loop skeleton solves (StoichiometricReactor); custom rate law in a CSTR solves (Q7 yes).
- Dossier `docs/v02-real-chemistry-dossier.md`: needs_frank items 1, 2, 4, 5, 8, 11; C1 re-scores 12 → 13.
- For the design lane: does vapour-only light-gas PR satisfy H4, or must M01 handle dissolved gases (root selection
  then a derivation item)?

## 2026-10-01 — CORRECTION (Frank): Phase 3's C1 reactor audit was of a superseded branch

The local clone `~/Codes/ammonia_synthesis_reactor` is on `gitlab/master` (Feb–Apr 2026, 92 commits), an abandoned
line with **no common ancestor** with the released code. `a6ee9ef` is the tip of that dead branch, not "the latest
commit"; the build lane did not check which line the clone was on. The findings on the regression harness,
`lambda_mem`, the element balance and the 1.4 s timing apply to that branch only and are withdrawn for C1.

Released code (Frank, verified by the session on a fresh clone in the scratchpad, `asr-release`): `main` @
**`6089593`** (tag `v1.1.0`), root commit `d2b0033` "initial public release", 9 commits, **`LICENSE` MIT**
(`pyproject.toml` `license = "MIT"`); public at github.com/computational-chemical-engineering/ammonia_synthesis_reactor;
Zenodo concept DOI 10.5281/zenodo.22811033; dataset DOI 10.4121/e03a6e99-6ddc-4c10-8d92-fb36335cdb43 (4TU, in
curation). Suite: 6 test modules, 72 tests. Frank's re-check against `main`: no `regression_test.py`; `lambda_mem`
evaluated at T at every call site; the element balance is part of the accepted-case criteria (`kpis.json`
`element_balance_ok`); λ(q) omitted deliberately (Weisz–Prater Φ_WP ≤ 0.099, nominal 0.0008; paper Fig. 2);
K_NH3 = 7000 cal (29 288 J) likely correct — Gargiulo Table 1's 29 228 J looks like a transposition (effect 0.35 %
relative at Rossetti Test 1), being checked against Rossetti 2006. Genuine defect on `main` (Frank's, logged for the
group's next version, not patched now because of the DOI/curation): `reactor/paper/validation.py:103`'s
"membrane-free" validation sets `cfg.Perm_NH3` (field removed, `config.py:51`) and `cfg.Nm` (never read), so the
`P0_*` permeances stay live; worst effect 0.26 % on outlet NH₃, no reported number changes.

Action: redo W3.2 on `main` @ `6089593` from a fresh clone (never the old directory), and correct the dossier
(rights: code MIT; dataset DOI) before Phase 5. Lesson: confirm the branch/commit of any external repository and
quote it before auditing.

## 2026-10-01 — Phase 4 landed (`46f4453`…`69e8e03`): RC machinery, no tag

Version `0.1.0rc1` (`pyproject.toml`, `__version__`; two application-results fixtures carry it in
`server.package_version` — the `0.1.0` bump must move them too). Runtime data as package data via
`process_runtime.resources.packaged()` and symlinks under `src/process_runtime/_data/` to the single repo copies
(DECISION, engineer; reversible by reverting `46f4453`): 34 schema files byte-identical, `$id`s unchanged, identity
unchanged. sdist/wheel built twice: wheel bytes identical (`461ed3d0…`), sdist members identical; A43 PASS.
`scripts/v0_1_gate.py` (A50) exits 1 today (no verdicts, no RC). CI dispatch inputs `rc_distribution`, `rc`; jobs
`dist`, `clean-install`, `bundle-set`, `bundle-replay`, `rc-steps`, `rc-ensemble`. Local dev runs (not RC
evidence): install-check 10/10; 52/52 bundles MATCH; identity 3/3; corpus PASS; surface PASS (G16-b 40/40); 122
certificates audited, 0 violations; ensemble S = 434/440. check.sh 6684 passed.
Open for the design lane: **A45** (the T06 A34 set writes no bundles — what stands for it); **A49** still names
`6d13e13d…` (same amendment as B50 under R-134); the T08-verdicts.md table shape the gate script reads; ADR 0021
D2.4's tree check incl. `pyproject.toml`; an installed wheel has no `requirements.lock` so its own bundles replay
NOT_RUN (ADR 0007 D4 question); setuptools pinned only in `t08_dist.py`.

## 2026-10-01 — W3.2 redone on the released reactor code (`1f7bc0d`, `e741dce`)

`main` @ `6089593` (tag `v1.1.0` is on the parent `d78fbfb`; model code identical — only CITATION.cff, README,
`archive.py` differ). Group suite: 72 collected, **69 passed, 3 skipped** (data-dependent guards), 0 failed. One
non-isothermal 1D solve (`G2 — GHSV sweep_1000`): converged, certified, element balance ok, median 11.5 s
(`num_z=100`). No membrane: non-isothermal converged 3.6 s; isothermal fails from cold starts `dt_init` 1e-6 and 1e-3
(the group's acceptance check rejects them), converges at 1e-2 (0.48 s). Superseded measurements dropped (pointer
to `7c042a0`). Dossier corrected: code MIT + Zenodo DOI met; Rossetti CSV met (header on `main` names source, DOI,
unit); still Frank's: property-database sources, 4TU dataset use during curation, citing the MSc report/2D draft,
his K_NH3 check. Design-lane questions added to Amendment R3 item 8 (A61 on a pytest suite with 3 data skips; pin
`6089593` vs tag commit `d78fbfb`; item 5/H2 while K_NH3 is pending).

## 2026-10-01 — Amendment R3 (`8138c16`) applied (`2fc5a28`…`4563112`)

R3 rulings: A45 = K05's 5 variants + G8's eligible revisions (T06 A34 moved to A46 as same-class replay); A49 →
`171dd768…`; `T08-verdicts.md` one table `Gate | Verdict | Failing clauses | Travelling limitations | Basis`; D2.4
tree adds MANIFEST.in, README, LICENSE, NOTICE; L41 (installed wheel records no lock) + **defect fixed: lock search
confined to the checkout** (`_checkout_lock`, T08.A19; identity and all 246 committed lock hashes unchanged); A89
outcome on every class, count only on the ref CPU (T06 Amendment T08-1); ADR 0006 Amendment 2 (aarch64 CasADi
objects; Amendment 1 covers aarch64 numpy/scipy libgfortran); V19: H4 met with PR light gases vapour-only (dissolved
gases a v0.2 limitation; ADR 0022 rev 1), A61 = the group's pytest suite (69 passed, 3 data skips not reproduced), pin
`6089593`, H1/H2 met, K_NH3 an M01 pin item. Register R-136…R-143 (next R-144). check.sh: 1 red expected —
A30[aarch64] until the summary is regenerated (CI 36900345552 dispatched).

## 2026-10-01 — RC at `d2ff647`: F1 (A45 replay not measured); new C follows

RC record `docs/t08-rc-record.md` (`8ddd3d8`): every RC step PASS (A41–A44, A19, A46/A47 S = 434/440 on both
classes with T06 A34 replay 28/28 MATCH, A47/A48 12/12, A49, A30, A34 0 violations) **except A45**: CI `bundle-set`
upload failed on the revision id `T05b:DZ-3` (`:` refused by upload-artifact), so `bundle-replay` was skipped. Fixed
by the session in `dbcbc89` (percent-encoded bundle directories; index keeps names) → a **new C**, and the whole RC
job re-runs there. Noted, not judged: the bundles-write log prints `DomainError … temperature outside [280, 440] K`
tracebacks while the step reports ok; the A30 inventory record carries no commit/tree_clean (not an A16 record per
its row); CI Python 3.13.15 vs local 3.13.5 moves `files_digest` of 8 pure-Python distributions.

## 2026-10-01 — RC at `814e151`: all steps PASS except A45's aarch64 replay (F2)

RC record `660d815`. x86 replay 52/52 exact MATCH; **aarch64 replay 31 MATCH / 21 MISMATCH** in
`compatible_reproduction` under `K04-numerical-policy-v1`'s interim tolerance (1e-9 relative, **0 absolute**):
round-off-scale duties (`U-FLASH.Q` 1.6e-16 vs −4.5e-15), `u_diag_min_abs` 0.0448 vs 0.0732, certificate limitation
values ~1e-7 relative, and derived ids/hashes (`certificate_id` ×19, `level_constants_sha256`, event messages
embedding floats). Everything else PASS. DECISION: no change to the comparison policy now — tightening or loosening
it after seeing the result is a criterion re-read (CLAUDE.md "no relaxed checks"); the `verdict` judges A45 as
registered at this C, and any policy change is a design-lane ADR decided on its own grounds, followed by a new C.

## 2026-10-01 — Verdicts V11–V20 at C = `814e151` (`850f017`); C is not an RC

`docs/reviews/T08-verdicts.md`: V11 PASS, V12 PASS, **V13 FAIL** (V13 (e): B50's amended content clause says the
`get_project` content differs from `c7bbc98` by exactly the CSTR and two policies, but `server.package_version`
moved `0.0.0` → `0.1.0rc1` at W4.1), V14 FAIL (accepted, D3), V15–V18 PASS (V17 carried), **V19 BLOCKED** (Frank's
F3 acceptance of ADR 0022, H5 rights statements, four rights rows; the `k_ij` row is lane work), V20 PASS. **A45 not
met → C fails §8.1 item 4; no tag can be proposed.** Ledger updated (`221ee27`).
Findings on the criteria: **G1** the cross-architecture comparator compares `certificate_id` (a float-state digest
prefix, forbidden by ADR 0007 D1; the only difference in 12 of 21 mismatches), is stricter than D2.2 in three
places, the pivot diagnostic differs 39 % against D2.1's measured 2.2e-14 premise → a design-lane ADR (new policy
id), then a new C. **G2** B50's content clause cannot hold at any RC (the version must change) → an amendment like
R-134 (Frank). **G3** `v0_1_gate.py` never reads §8.1 / the RC record → build-lane fix. R3-W3 (`39d3694`) has no
design-lane review yet.

## 2026-10-01 — Frank: amend B50 (R-144), ADR 0022 choice (R-145), go ahead with G1

B50 Amendment 4 (excludes `server.package_version`); ADR 0022 choice + revision 1 recorded (Accepted when V19 PASS);
G1 design-lane ADR approved ("Go ahead now"): specifier brief `docs/briefs/T08-G1-replay-policy.md` (ADR 0025, a new
policy id, rules decided on ADR 0007's principles, not tuned to F2's 21 mismatches). Then build lane: G1
implementation, G3 (gate script reads the RC record), B50's exact test, the `k_ij` rights row; `reviewer` on R3-W3 + G1;
new C; RC job; verdicts.

## 2026-10-02 — ADR 0025 (`bd12fc3`, Proposed); Frank's Q4

`T08-numerical-policy-v2` (D1 policy recorded per record; D2 digests compared for shape; D3 limitation values floored
at their threshold; D4 LU pivot diagnostics recorded, not compared; D5 solution variables floored at their kind's
acceptance tolerance; D6 numbers in text compared numerically; D7 D2.1's premise restated). Judged after the rules were
fixed, all 21 F2 mismatches would MATCH under v2; A45's FAIL at `814e151` stands. **Frank (2026-10-02): replay an old
record under the policy it records, not refuse** (ADR 0025 "Frank's answer to Q4"; R-147). Next: build lane W1–W8
(brief `docs/briefs/T08-adr0025-build.md`), then G3 + B50 exact test + `k_ij` row, `reviewer` on R3-W3 + W2–W4, new C.

## 2026-10-02 — ADR 0025 W1–W7 on `wp/T08` (`d6721fc`…`7133bdc`); recording v2 held (identity move)

On `wp/T08` (still recording v1): policy file + generator; `differences(policy_id=…)` with v1 path bit-identical
(2250-comparison mutation corpus identical); schemas `const`→`enum`; replay under the recorded policy (Q4); unknown
id refused; call sites pass v1; A1–A15 tests; RC script records policy + A14 controls. MCP surface unchanged (served
tool list `dbc18fe3…` before/after). check.sh 6755 passed, 1 failed — `test_the_gate_table_is_what_the_gate_script_prints`,
already failing at `1e2faef` (CHANGELOG table vs gate output since the verdicts landed).
**Held on `wp/T08-a25-recording`** (`056f850` W3b, `4395df4` W8): recording v2 moves the K05 identity keys because
`RunManifest.structural_sha256` covers `numerical_policy_id` — whole `7f32b143`→`28dd8bf7`, minus-t07
`9a7b4e6d`→`29246e05`, t07 `422aa7a5`→`a96f17ed`, structural `915c97e8`→`e62a59a6`; T02 floats unchanged.
Substitution-only (v1 substituted back → byte-identical). ADR 0025 §11 said nothing would move — wrong. Needs Frank.
For the reviewer: `replay._as_recorded` reads the fresh certificate's policy field as the archive's when the fresh
one names `CURRENT_POLICY_ID` (engineer's choice, `056f850`).

## 2026-10-02 — Frank approves re-registering the K05 identity for v2 recording

Substitution-only move approved (whole, minus-t07, t07, structural; T02 floats unchanged). Engineer brief
`docs/briefs/T08-reregister-and-fixes.md`: merge `wp/T08-a25-recording`, re-register with substitution tests (R-148),
G3 gate script reads the RC record, B50 exact test, `k_ij` rights row, CHANGELOG table.

## 2026-10-02 — v2 recording merged; identity re-registered (R-148); G3, B50 test, k_ij, CHANGELOG

`9ec2543` merge; `b5e11a7` R-148 (whole `28dd8bf7…`, minus-t07 `29246e05…`, t07 `a96f17ed…`, structural `e62a59a6…`,
CLI structural `f9536122…`; substitution tests via `tests/t08_v2_substitution.py::record_v1`); `5aeac9d` G3 (gate
script reads the RC record; status words PASS/success required); `a28fde3` B50 exact test (c7bbc98 surface rebuilt
from that commit's own code; cross-checked against v17-c2 transcripts); `1191ba0` k_ij row; `d7a35c0` CHANGELOG table.
check.sh 6775 passed, 0 failed. Open (to review 3): release spec §3.2 + reference values still carry the v1
identity values; ADR 0025 §11's "nothing registered moves" is wrong; confirm G3's status vocabulary.

## 2026-10-02 — Review 3 (`ec72a90`): code sound; M1 (spec/RC identity values), S1 (gate cell classification), S2 (texts)

v1 path bit-identical on 5000 random comparisons vs `814e151`'s `compare.py`; all 52 `814e151` bundles replay MATCH
under v1 in this build; re-sealed as v2 they MATCH with declared kinds (1627/1627). Rulings: R5 1 (identity values the
RC reproduces), ADR 0025 correction + R5 2, G3 closed vocabulary. DECISION: adopt the reviewer's N5 recommendation
(mark v2's `exact_fields` inert before registering v2) as the design lane's ruling. Alternative: enforce it (a new
comparator rule). Reversible by reverting the N5 commit. Engineer brief `docs/briefs/T08-review-3-fixes.md`; then new C.

## 2026-10-02 — Review 3 fixes landed (`521ad82`…`bb1dd2e`); ADR 0007 text corrected

Release spec Amendment R5 (identity values per R-148; generator 178/178, YAML `45ea712e…`); ADR 0025 correction;
R-146/R-147 entered; gate script closed status vocabulary (814e151 record classifies unchanged); v2 `exact_fields`
documented inert; A14 C2/C3 strengthened. check.sh 6806 passed. The session corrected ADR 0007 Amendment 1's stale
"refused" sentence to R-147. Engineer readings for the final review: `failure` matched as a word or inside an
identifier, not as the start of a longer word (`890411f`); "PASS: Failed to upload" still classifies passed (the
ruling lists no rule for it).

## 2026-10-02 — Frank: the project is named **OpenFlowsheet**; full rename before v0.1

Frank chose OpenFlowsheet (generic, room for future scope) over ClearSheet (several commercial "ClearSheet" products,
spreadsheet connotation) after a PyPI/GitHub/web check (`openflowsheet` free on PyPI, 0 GitHub repos, no web hits).
Scope (Frank): **full rename** — product name, distribution `openflowsheet`, import package `openflowsheet`, CLI
`openflowsheet`, docs; the engineer stops if the MCP surface or a registered identity would move. Schema `$id`s
(`https://github.com/frankp/process-runtime/schemas/…`) stay for v0.1 and move later by ADR (v0.2 backlog). The GitHub
repository rename (`clearsheet` → `openflowsheet`) is Frank's to do; the session updates the remote afterwards.

## 2026-10-02 — Rename held at brief step 2: a registered identity moves (substitution-only)

Measured at `50602a0`: K05 identity whole `28dd8bf7`, minus-t07 `29246e05`, t07 `a96f17ed`, structural `e62a59a6`,
T02 floats `9a8a5baf`; MCP tool list `dbc18fe3`, descriptions `171dd768`. Trial rename (parked, not green, on
`wp/T08-rename` `3a1345f`): MCP digests unchanged; the identity moves because the SYN-001 provider's
`implementation_sha256` is the SHA-256 of `thermo/syn001.py`'s own source (blueprint §6.4), and three import lines
there name the package — `67e472816d4d…` → `4e4c37cc8054…`, hence `model_version`, `plan_id`, `structural_sha256`,
`artifact_r0_sha256`, whole `174977cc`, minus-t07 `24af004a`, t07 `887a2e62`, structural `ed6d11f3`; T02 floats
unchanged. With the old provider hash substituted the identity and floats are byte-identical to `50602a0`'s.
Also moved (check.sh on the trial: 77 failed, 6729 passed): K03/K04/K05/T04 schema fixtures, the T07 CLI byte
fixture, T07 W5c binding signatures (55), W3a legacy plans, W3f bundle table, T06 registered start sets
(`starts-nominal-v1.json`, holdout1: they record the provider hash and `generator_sha256`, the SHA-256 of
`benchmarks/t06/generator.py`, which also imports the package — `509b01fb` → `7f426aa9`). Needs Frank, as R-148 did.

## 2026-10-02 — Frank accepts the rename's identity move (A); pre-public audit queued

Renaming the import package moves the SYN-001 provider's self-hash (`implementation_sha256`, three import lines) and
the T06 generator's self-hash, hence K05 identity (whole `28dd8bf7…`→`174977cc…`, structural `e62a59a6…`→`ed6d11f3…`,
…), ~70 registered fixtures/signatures and the T06 start sets' `generator_sha256`. Substitution-only (old hash
substituted back → byte-identical). MCP surface unchanged. **Frank: accept (A)**, not relative imports. Engineer's
smaller defaults accepted (env vars → `OPENFLOWSHEET_*`, schema prose / lock header / ADRs / specs / spikes stay).
Rename resumed on `wp/T08-rename`; R-149. After it: the pre-public audit (read-only; Frank: yes), then new C.

## 2026-10-02 — Rename to OpenFlowsheet landed on `wp/T08-rename` (R-149); one design-lane amendment open

Steps 3–6 of the brief done: package `src/openflowsheet`, distribution/script `openflowsheet`, MCP server name
`openflowsheet`, env vars `OPENFLOWSHEET_*` (`5018fa3`, revertible), docs, R-149 (`ce3ef7a`…). Re-registered by
substitution only, each with a substitute-back test (`tests/t08_rename_substitution.py`): provider
`67e47281`→`4e4c37cc`, T06 generator `7f426aa9`→`509b01fb` (old→new; the held entry above gave this pair reversed),
K05 whole `28dd8bf7`→`174977cc`, minus-t07 `29246e05`→`24af004a`, t07 `a96f17ed`→`887a2e62`, structural
`e62a59a6`→`ed6d11f3`, CLI structural `f9536122`→`16ae2bd4`, 11 schema fixtures, W5c 55, W3a 38, W3f 2. T06 start sets
untouched (§6.5). MCP tool list `dbc18fe3`, descriptions `171dd768` unchanged; `requirements.lock` unchanged.
`t08_dist.py`: openflowsheet-0.1.0rc1 sdist + wheel, A43 PASS; `openflowsheet solve SYN-001-nominal` CONVERGED/VERIFIED,
structural `16ae2bd4`. **Open (design lane):** `t08_reference.py`'s R5 claims require the release spec §3.2 values to
equal `scripts/t08_rc.py`'s constants, now R-149's — a release-spec amendment like R5 1 (§3.2 rows,
`REGISTERED_DIGESTS` + a pre-rename table, reference YAML regenerated) is needed; until then
`test_a00_generator_check_passes[t08_reference.py]` fails (2 of 178 claims).

## 2026-10-02 — Rename complete (R-149, Amendment R6); pre-public audit; Frank: TU/e author address, squash at release

Rename merged (`5ed30b7`), release spec Amendment R6 (`7003f77`, generator 188/188, YAML `57c40f02…`); check.sh 6817
passed. Pre-public audit (`docs/pre-public-audit.md`, kept out of git — it quotes the address): no secrets in 4 371
blobs; no CasADi/PDF/spreadsheet bytes ever; **blocking: the pre-redaction V17 c1 transcripts (Gmail address) remain
reachable in history and on origin**; 18 blobs > 1 MB; one old V19 record blob with an internal GitLab path; local
username in solver-log paths; the IDAES/DWSIM reference-output redistribution right is not recorded (doc gap).
Frank (2026-10-02): package author e-mail → TU/e (`pyproject.toml`); **public history: squash at release** — one
public "initial public release" commit of the v0.1.0 tree; the full history stays private and keeps evidence hashes.

## 2026-10-02 — RC at `89c3d77` (record `1b4c2fb`): F3 (ruff) — every other step PASS incl. A45 on both architectures

Under ADR 0025, **A45 PASS on both architectures** (x86 52 exact MATCH; aarch64 52 `compatible_reproduction` MATCH; all
record v2; A14 controls as expected). A42 local PASS; A43, A44, A19, A46/A47 (434/440 both), A47/A48, A49, A30, A34 PASS.
**F3:** both CI `check` jobs failed at ruff — `spikes/t03/w0_screen_measurement.py` still imported `process_runtime`
(the rename missed it; a stale local `.ruff_cache` hid it) → `identity` (cross-arch G05) skipped. Fixed by the session
(`7d…` below) with the A30 summaries regenerated after the rename. Lesson: clear `.ruff_cache` before the gate run that
precedes a C. New C follows.

## 2026-10-02 — RC at `78e92b7` (record `d7bfaeb`): every step PASS except the CI `identity` job (F4)

F4: the cross-architecture identity job installed only pyyaml, but `run.compare` imports numpy since ADR 0025 W2, and
the job's `differences()` call lacked the now-required `policy_id`. Fixed (`ci.yml`): numpy at the lock's version, and
`policy_id="K04-numerical-policy-v1"` per ADR 0025 W5 (registered comparisons keep v1 — not a new choice). Reproduced
with that run's artifacts in a minimal venv: G05 equal. All other steps at `78e92b7` PASS (A45 both architectures).
New C follows.

## 2026-10-02 — RC at `67c66d9` (record `51cd5ff`): every step 1–10 PASS

CI dispatch run 37008077757 success (push run success). A41 both architectures; A42 local + both CI + **G05 equal
across 2 platforms**; A43; A44; A19; **A45 52/52 MATCH on both architectures under policy v2**, A14 controls as
expected; A46/A47 S = 434/440 on both classes; A47/A48; A49; A30; A34 0 violations. Gate script: tree equal to C, RC
record steps 1–10 passed; NO only on V13 (e) (verdict still the 814e151 one) and V19 BLOCKED. Next: Frank's V19
statements, then one `verdict` pass V11–V20 at `67c66d9`.

## 2026-10-02 — Frank's V19 statements (items 2–4); item 1 pending his choice

- **4TU dataset** (doi 10.4121/e03a6e99-6ddc-4c10-8d92-fb36335cdb43): **may be used and referenced** (Frank).
- **Simpelaar MSc report and the group's 2D manuscript draft: may be cited** (Frank).
- **Ar/CH₄ PR parameters from IDAES's examples: fine** (Frank), or take them directly from NIST.
- **Property database sources (item 1):** Frank wants later connection to the major open-source thermodynamic data
  sources; the session recommended replacing the group database's undocumented values for M01 with values from an
  open, cited source — awaiting his choice.

## 2026-10-02 — Frank's V19 item 1: open, cited property sources for M01

Frank agreed: M01 takes Tc, Pc, ω, c_p, ΔH_f from open, cited sources, recorded per value with the primary reference in
OpenFlowsheet's own component records; `chemicals`/`thermo` as first retrieval source (single maintainer — used as a
retrieval tool, never a runtime dependency of the certified path), cross-checked against CoolProp or Cantera; the
group database is a cross-check only; the provider interface is source-neutral. Recorded in the dossier
("Frank's statements, 2026-10-02"). V19 now has all its inputs → one `verdict` pass V11–V20 at `67c66d9`.

## 2026-10-02 — Verdicts at C = `67c66d9` (`f22f3cf`): nine PASS, V14 FAIL (accepted); A45 met

V13 and V19 moved to PASS. Gate script NO only because the ledger still holds the old words and the T08 manifest
does not exist. Findings G4–G8 + G3 residuals → close-out brief `docs/briefs/T08-close.md` (ledger, CHANGELOG,
RC records under `evidence/T08/<C>/rc/` — DECISION G6: outside the D2.4 trees (`src/`, `schemas/`, `benchmarks/`, …;
`scripts/` and `evidence/` are not checked), alternative: commit under `benchmarks/t08/rc/` and cut a new C each time,
reversible by moving the files; ADR 0022 Accepted; dossier sync; manifest; ADR 0021/0023/0024/0025 Accepted).

## 2026-10-02 — Merged to main; v0.1.0 bump; gate YES

`wp/T08` merged into `main` (`9bfd9f8`, CI green at `ebe430e`); version bump `a3bc534` (version only in the D2.4 trees;
CHANGELOG header and two version-carrying fixtures). check.sh 6864 passed; `v0_1_gate.py --rc 67c66d9…` on `a3bc534`:
tree equal to C, RC steps 1–10 passed, T08 manifest `tested` → **YES**. Tag and publication are Frank's (ADR 0021 D5).
