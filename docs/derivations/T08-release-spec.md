# T08 — v0.1 release specification: gate criteria, the supported envelope, the V19 real-chemistry dossier, and the release candidate

**Package:** T08 (plan v1.2 §4.3 row T08, lane Design / Build: "v0.1 release evidence, supported envelope and v0.2 real-chemistry selection" — acceptance "Gate V11–V20; selected chemistry/data/kinetics/property/reference dossier; reproducible release candidate").
**Author:** design lane (`specifier`), 2026-09-29, on `wp/T08` at `0b37f2b`. Brief `docs/briefs/T08-specification.md`; factual ledger `docs/t08-gate-ledger.md`.
**Status:** Proposed. Binding on the build lane and on the `verdict` agent once committed. A defect found in it is amended here, with the amendment dated and stated, never worked around downstream.
**Requirements served:** D04 and A10 (the release-time refresh ADR 0006 assigns to T08), D17 (every release gate judged, none substituted), D20 (a reproducible release candidate); gates V11–V20 (the frozen evidence-manifest schema takes D/A ids only, so the V-gates travel in `limitations` and in `docs/requirements.yaml`, T04's precedent).
**Reference generator:** `docs/derivations/scripts/t08_reference.py` → `benchmarks/t08/reference_values.yaml` (`--check` re-derives every claim of §10 and requires the committed YAML byte for byte).
**ADR drafts:** `docs/adr/0021-v0.1-release-policy.md` and `docs/adr/0022-v0.2-real-chemistry-selection.md`, both Proposed. Register text: §16.

---

## 0. The answer, in one paragraph

On existing evidence, **V16 and V17 are MET** by earlier verdicts and need only a re-check at the release candidate; **V11, V12, V15 and V20 are likely MET** once T08 adds four small items (a migration probe, a ledger fix, a typed message fix, the ensemble re-run at the release candidate); **V18 needs T08 work** (the [A10] refresh on both architectures, a recovery-edge inventory, data provenance); **V19 needs T08 work and Frank** (his choice of chemistry and three rights statements); and **two gates carry a clause that is not met and cannot be met by bookkeeping**: V14's *qualified PTC* (T04's registered comparison shows PTC improves no basin, and the criterion is not re-read after the result) and V13's *warm starts* (blueprint §14.3 names them; T03 recorded that none exists in v0.1). Whether v0.1 is tagged with those two clauses recorded FAIL, or waits until they are built, is Frank's decision; the recommended default is to tag with them recorded FAIL under ADR 0021. The recommended real chemistry is the **ammonia synthesis loop built on the group's own PyMRM reactor model** (found on this machine, MIT-licensed PyMRM, experimental data in hand), with the **methanol synthesis loop** as runner-up. The three record defects D1–D3 found by probing `main` block the **release candidate**, not a gate verdict, and D1 is folded into V20's invalid-structure clause.

---

## 1. Authority, scope, and what is out of scope

**Authority.** Blueprint v3.1 (SHA-256 `66f574b0…`, matching the plan header) §14.3 is the content of v0.1 acceptance; plan v1.2 §5.1 is the gate ledger, whose V-rows summarise §14.3's bullets one for one (V11 = bullet 1 … V19 = bullet 9; V20 = §13.4's proposed v0.1 gates). **Where a plan row omits a clause of its blueprint bullet, the blueprint clause counts** (CLAUDE.md: preserve v3.1 and record the conflict; §14 FD1 records it). Frozen interfaces (`docs/interfaces-frozen.md`) and ADRs 0001–0020 are respected; nothing here changes a frozen signature or schema. Where this document concludes a frozen item should change, it says so as a finding (§14) and does not change it.

**In scope.** (a) Judging criteria for V11–V20 (§4); (b) the supported envelope of v0.1 as a registrable, machine-checked statement (§5); (c) the V19 dossier criteria and the candidate assessment (§7); (d) the definition of the reproducible release candidate (§8); (e) numbered assertions (§9); (f) ADR drafts 0021, 0022 and register text (§16); (g) the build-lane work order (§15). Also the classification of T07's hand-ons and of the three record defects the coordinator reported (§6).

**Out of scope.** M01–M07 implementation; the web shell (M06; `design/web-shell-brief`); publishing, tagging, data acquisition that costs money or needs rights (all Frank's); any change to a registered tolerance, identity key or result except the substitution-only re-registrations §6.2 names and Frank approves (F4).

---

## 2. What this specification establishes

1. For each gate V11–V20: its clauses, the evidence a verdict must judge, what T08 must add, the verdict rule, and an expectation on existing evidence (§4, summary table §4.0).
2. The principle that **every gate is judged at the release-candidate commit**: an earlier package's pass is evidence about its own commit and transfers to the RC only through the RC job's re-run of its registered assertions (§3.3; register R-121).
3. The v0.1 supported envelope: its axes, its unsupported capabilities with the typed outcome of each, its registered limitations with evidence, and a completeness check that fails when any manifest limitation is left unclassified (§5).
4. A closed form for the verifier's alias-pressure-shift limit, which bounds the envelope by variable position and pressure (§5.4).
5. The classification of D1–D3 and of T07's hand-ons: gate-blocking, RC-blocking, or v0.2 backlog (§6).
6. The V19 dossier's required contents, a scored selection rubric with a preregistered tie-break, an assessment of five candidates, and the ranking's sensitivity to every unmeasured score (§7).
7. The definition of the release candidate, the RC job, and the line between what T08 may do and what is Frank's (§8).
8. Forty-one numbered assertions (§9), each with expected value, tolerance and argument. **T08 registers no new numerical tolerance**: every float comparison it asks for uses a tolerance already registered, with its argument, by K04/ADR 0007, T02 §6.4, T06 §9.4 or ADR 0018.

---

## 3. The evidence base and the rules of judgement

### 3.1 Cited manifests (generator-checked, T08.A01)

| Package | Manifest (`evidence/<pkg>/<commit>/manifest.json`) | Status | Checks | Gates it serves |
| --- | --- | --- | --- | --- |
| K02 | `1baaf03…` | reviewed | 19 pass, 1 unsupported, 1 n/a | V13 (§6.4 warm-start *cache*, not §7.4 warm starts) |
| K03 | `c806f83…` | reviewed | 15 pass, 1 unsupported (`K03.initializer_chain`), 1 n/a | V13 |
| K04 | `bf3d9ee…` | reviewed | 7 pass, 1 unsupported, 1 n/a | V18, V20 |
| K05 | `b0a7fe7…` | reviewed | 7 pass, 1 unsupported (`K05.clean_environment_replay_from_a_fresh_checkout`) | RC (§8) |
| K06 | `cda68cd…` | reviewed | 6 pass, 1 unsupported, 1 n/a | V11 |
| P03 | `449cf3d…` | reviewed | 14 pass, 2 unsupported, 2 n/a | V18 |
| T01 | `00a71f4…` | tested | 26 pass | V11, V13 |
| T02 | `b68585f…` | tested | 37 pass | V13, V14, V15 |
| T03 | `6ac24be…` | tested | 27 pass | V15 |
| T04 | `53cd23b…` | tested | 34 pass | V14 |
| T05 | `91ac010…` | tested | 31 pass | V12 |
| T05b | `ba9a27b…` | tested | 64 pass | V12 |
| T06 | `ebec629…` | tested | 96 pass, 4 n/a | V11, V15, V16, V18, V20 |
| T07 | `5f3d3ea…` | tested | 107 pass | V11, V17 |

`reviewed` on P00–K06 records Frank's 2026-09-23 sign-off with its stated qualification (register R-017); T01–T07 are `tested`, review pending. The verdicts already on file: `docs/reviews/T06-verdicts.md` (V16 comparison clause MET; V20 robustness MET on run 2; no false verification MET on run 2; run 1's FAIL stands) and `docs/reviews/T07-verdicts.md` (V17 MET on `v17-c2`, 25/30; `v17-c1` 19/30 stands).

### 3.2 Registered values the release candidate must reproduce (generator-checked)

| Value | SHA-256 | Registered in |
| --- | --- | --- |
| `requirements.lock` | `ead4edf1ea3577287a7576d56a9e5db550e5a5be459dd634b10806fdc655b9c4` | T07 manifest `inputs.environment_lock_hash` |
| K05 identity document minus `t07` (R-149) | `24af004ab5718e559bd3d40716d66e21d9b19043a26777a39a0da84c6fbdcb8e` | `tests/test_t07_identity.py` (`K05_MINUS_T07_SHA256_R149`) *(amended 2026-10-02, Amendment R5 1; amended 2026-10-02, Amendment R6 1)* |
| Structural hash (R-149) | `ed6d11f3beb78c6f1debc481c6e525ce3ccb120bd30cdfd07e470f728e082e90` | `tests/test_t07_identity.py` (`STRUCTURAL_SHA256_R149`) *(amended 2026-10-02, Amendment R5 1; amended 2026-10-02, Amendment R6 1)* |
| `t07` key (§6.2's D1–D3, then R-148, then R-149) | `887a2e622676dbfaff0a8ebfc309414f0e74150ace8327887b4a9ec15e498a38` | `tests/test_t08_w1_identity_substitution.py` (`T07_KEY_SHA256_R149`) *(added 2026-10-02, Amendment R5 1; amended 2026-10-02, Amendment R6 1)* |
| V17 `v17-c2` served tool descriptions | `6d13e13d660521c1a39dc245d5237c974a4273b0c3eeadb02d44538ba2669a4d` | every `v17-c2` `run.json` |
| Served tool descriptions at the RC (R-133's carried surface) | `171dd768efcfb24f65d79d83a4f157dcfd1436935bf5106a247b84f3040e4d14` | `tests/test_t08_w2_surface_digest.py` *(added 2026-10-01, Amendment R3 2)* |
| T06 nominal starts | `3a7bd49c66493744753d1eac554101317c931e0ef51d9154d6f7cab3124fef82` | `benchmarks/registry.yaml` `ensemble.starts_sha256` |
| T06 ensemble gate | N = 440, S_min = 418, classes `ref-x86-64`, `ci-aarch64` | `benchmarks/registry.yaml` `ensemble.gate` |

The complete identity document to reproduce is the committed `evidence/T07/5f3d3ea…/artifacts/k05-identity.json`, except the keys re-registered under §6.2 (including R-148 and R-149). At `C` the whole document is `174977ccf18d0dbf57fa429cb2522921cc98d0d5b693382ec973c86fd714c225`; with the pre-rename self-hashes it is R-148's `28dd8bf7f15f7750b0c646f609037dc84afd6f465b0bc3b5fac459c14299f0a5`, and with v1 recorded as well it is `7f32b1431226d11fd7b5b89f467525ca72648d6d7596df82d5d64b27d1ddf7e5`. *(amended 2026-10-02, Amendment R5 1; amended 2026-10-02, Amendment R6 1)*

### 3.3 Rules of judgement

- **Vocabulary.** The ledger takes `PASS`, `FAIL`, `BLOCKED` (`schemas/requirements-ledger.schema.json`); the brief's MET / NOT MET are `PASS` / `FAIL`. `BLOCKED` is used **only** when the missing input is outside both lanes' authority (Frank's decision, a rights statement, external access). Evidence the lanes were to produce and did not is `FAIL`, never `BLOCKED`. A gate whose clauses are all met with registered limitations is `PASS`, and its limitations travel by envelope id (§5) into the verdict, the gate report and the release notes.
- **Clause-wise.** A gate is `PASS` iff every clause is met. A `FAIL` names the clause. A gate is never reworded to pass, and no clause leaves the denominator (plan §1.1).
- **At the RC commit.** A verdict judges the RC commit. Package manifests are evidence about their own commits; they count for the RC through the RC job (§8.2), which re-runs every registered assertion (the full gate on both architectures) and the campaigns named in §4. A campaign result that no longer holds at the RC is `FAIL` at the RC and the earlier record stands as history (R-087's precedent).
- **No new tolerance.** A verdict may not change a tolerance, a mapping, a setting or a classification rule. T08 adds none.
- **Numerical verification, empirical validation, optimality evidence** stay distinct in every verdict and in the release notes. Nothing in v0.1 is empirically validated: SYN-001 is synthetic.

---

## 4. Gate criteria

### 4.0 Summary

| Gate | Clauses (blueprint §14.3 / §13.4) | Existing evidence | Expectation | T08 adds | Frank |
| --- | --- | --- | --- | --- | --- |
| **V11** | semantic diff; immutable drafts; task-specific validation; units and component/reference checks; real migration if applicable | K06, T01, T06 (A43, A55–A57, A67–A74), T07 (`diff_revisions`, `preview_change`) | likely PASS | the migration probe (T08.A35); D1 (T08.A10) | — |
| **V12** | the §14.3 unit list; per-model definition of done | T05, T05b | likely PASS | ledger evidence list (T08.A02) | — |
| **V13** | DM/SCC/BTF with block statistics; safeguarded recycle and coupled EO; scales before iteration; model initialization; **warm starts** | T01, T02, K03; T03 spec: warm starts across runs absent in v0.1 | **FAIL on the warm-start clause** | nothing unless F2 says build | **F2** |
| **V14** | typed homotopy; **one PTC family qualified by §7.5** with tested SER; three bounded recovery edges | T04 (PTC experimental, §8.3), T02, ADR 0015 | **FAIL on the qualified-PTC clause** | nothing unless F1 says build | **F1** |
| **V15** | phase disappearance/reappearance with frozen attempts; cross-unit spec promotion without nested SM; multiple roots with honest branch reporting | T02, T03, T06 (ADV-05, THM-09 census) | likely PASS | re-run at RC (T08.A41) | — |
| **V16** | ≥ 30 distinct cases; eight shared comparisons; ≥ 2 by both tools where feasible; registered ensemble | T06 verdict 1: 8/8 by both, 16/16 AGREE | PASS (carried) | our side at RC (T08.A48) | — |
| **V17** | local/HTTP/MCP; ten tasks; ≥ 80 %; zero unauthorized actions and false verification | T07 verdict: 25/30 on `v17-c2` | PASS (carried) | surface identity and scripted transports at RC (T08.A49) | F5 only if the surface changed |
| **V18** | dependency/data provenance incl. the binary inventory; final target-Jacobian regularity; qualified energy checks; no enabled recovery edge without a direct failure test | P03, K04, T06 (A32, A33, A37–A46), T02/T04 edges | needs T08 work | T08.A30–A34 | — |
| **V19** | real chemistry selected and specified for v0.2 with data and comparison feasibility established | OpenIDAES-450 audit; the group's ammonia model (found locally) | needs T08 work + Frank | T08.A60–A65, the dossier | **F3** |
| **V20** | nominal fixtures pass; invalid structural cases rejected for the right reason; no false `VERIFIED` in the adversarial suite; ≥ 95 % over the registered ensemble | T06 verdicts 2 and 3a (run 2: S = 434/440 on both classes) | likely PASS | ensemble at RC (T08.A46); T08.A47; D1 (T08.A10) | — |

### 4.1 V11 — semantic diff, drafts, task validation, units/references, migration

*Clauses* (blueprint §14.3 bullet 1): (a) semantic diff; (b) immutable drafts; (c) task-specific validation; (d) units and component/reference checks; (e) a real migration fixture if applicable.
*Evidence to judge:* (a) T07's `diff_revisions` / `semantic_diff` `$def` and its tests; (b)–(c) K06's content-addressed revisions, draft vs ready, optimistic conflict, idempotent commit, and T01's structural validation (STR-01…06; R-022's DRAFT/INVALID rule); (d) T06 A43, A55–A57, A67–A74 (DIM-01, COMP-03, ADR 0016), THM-05 (`reference_convention_not_reaction_consistent`); K06's `unsupported` structural-over-specification check is superseded by T01 A09 (the verdict cites the superseding test). (e) **Applicable**: v0.0.0 was tagged (`9a4391f`) and every schema that changed afterwards did so under an ADR that states its migration impact (ADR 0009, 0005, 0010, 0012, 0015, 0018: an old policy is refused, never reinterpreted). The clause is met iff the RC does what those ADRs say on a *real* v0.0.0-emitted instance: T08.A35.
*T08 adds:* T08.A35; T08.A10 (D1 is also a validation-message defect, judged under V20).
*Verdict rule:* PASS iff (a)–(d) each have a passing test node at the RC and T08.A35 passes.

### 4.2 V12 — required unit library with per-model definition of done

*Clauses* (bullet 2): network units, heater/cooler, TP/PH flash, component separator, conversion reactor, simple valve and liquid pump, one two-stream exchanger; each with its definition of done (plan T05 row: contract, limiting/failure tests, balance and derivative evidence, at least one coupled case per family).
*Evidence:* T05 A00–A30 and T05b B00–B36/X00–X26; `MODEL_BUILDERS` lists twelve models (feed, sink, adiabatic mixer, TP heater, TP flash, splitter, PH flash, valve, liquid pump, conversion reactor, component separator, heat exchanger). A cooler is the TP heater with negative duty (ADR 0001 sign convention).
*T08 adds:* `docs/requirements.yaml` V12 `evidence` lists T05 and T05b (it is `[]` today; T08.A02).
*Verdict rule:* PASS iff every listed model has, at the RC, a passing contract test, a limiting/failure test, a balance test, a derivative test, and appears in at least one registered coupled case. A model whose DoD item is `unsupported` in a manifest is a limitation of that model, listed in the envelope, not a pass.

### 4.3 V13 — structure, recycle and EO, scaling, initialization, warm starts

*Clauses* (bullet 3): (a) DM/SCC/BTF diagnostics with block statistics and canonical tie-breaks; (b) a safeguarded recycle solve and a coupled EO block, with EO/tear agreement; (c) physical scales before iteration, fixed within an attempt (D06); (d) model initialization — the local model initializers and upstream propagation of §7.4, every candidate checked, rejections recorded; (e) **compatible warm starts** (§7.4's second source: a prior run's state offered as an initial candidate for a compatible problem, checked like every other candidate).
*Reading of (e), decided here.* §14.3's "model initialization and warm starts" sits in the solver-kernel bullet and names §7.4's sources. K02's **warm-start cache** (§6.4, D10: property-level hints that are never an exact answer) is a different mechanism and does **not** satisfy (e). The plan's V13 text ("scaling and initialization") omits "warm starts" and "block statistics"; the blueprint clause counts (§1; FD1).
*Evidence:* (a) T01; (b) T02 (A13–A15, A32, A34); (c) K03, T02; (d) K03 §10.1 and its `unsupported` `K03.initializer_chain`, T02/T05 traversal initializers, T06 F4's sequential restart; the verdict must find, for each §7.4 source, either a passing test or a recorded absence (an absent source silently skipped fails (d)). (e) T03 spec §5.1 (the opening checks are ready for "a compatible warm start, K03 §10.1 source 2, absent in v0.1") and §13 ("none exists in v0.1"); K03 §10.1 ("recorded absent").
*Expectation:* (a)–(d) met; (e) judged at the RC on T08 build-first B40–B51 (R-124); F2 answered *build* *(amended 2026-09-29, T08 build-first §E.1)*. T08.A71.
*Options (F2):* (i) tag v0.1 with V13 FAIL on (e), warm starts owned by M03 (sweeps are where they pay); (ii) build them in T08: an `architect` design note (explicit source — a named prior bundle's `solution-state.json` — or automatic from the store; how the source enters the RunManifest and replay identity; whether the frozen `Application.solve` needs a sibling operation, which is an ADR 0019 amendment), then one build increment and a `reviewer` pass: about one week, and it touches replay identity; (iii) hold the tag. *Recommended default:* (i).

### 4.4 V14 — homotopy, qualified PTC/SER, three bounded recovery edges

*Clauses* (bullet 4): (a) one typed homotopy; (b) **one PTC family qualified by §7.5 with tested SER control**; (c) three tested recovery edges with budgets, rollback and unchanged target semantics.
*Criterion for (b), fixed here.* A family is qualified for V14 iff **all** hold: (b1) T04 §8.1's criterion, **unchanged**: route (a) holds and, on the registered comparison, the set of starts from which PTC reaches the registered root is not contained in damped Newton's, under the same contract, tolerances and budgets; (b2) the comparison case — its starts, criterion and budgets — was committed before any PTC result on it existed (git order is the evidence); (b3) the family is selectable, by a registered policy, on a flowsheet inside the v0.1 envelope (§5): a family no supported flowsheet can select is not a v0.1 capability; (b4) SER tested (T04 A19–A22).
*Why not re-read.* Blueprint §7.5 lists route (a) — a physical derivation — as acceptable, and T04 §8.2 shows route (a) holds. But T04 registered, before running the comparison, that the family qualifies only if it also improves a tested basin (blueprint §15's risk row: "improves no tested basin → keep it experimental"), and the plan says "if no useful qualified family passes, retain PTC as experimental and record the v0.1 gate as incomplete". Reading route (a) alone as sufficient now, after the comparison came out 18/18 for both methods, is a criterion changed after the result. Rejected (R-118).
*Evidence:* (a) T04 A02–A12; (b) T04 §8.3: 18/18 both, PTC 1.9–8.8× costlier → (b1) fails; (b) PTC-R1: T08 build-first spec Part A *(amended 2026-09-29, T08 build-first §E.2)*; (c) T04 §5.5's table (edges 1–2 from T02, edge 3 here), plus ADR 0015's sequential restart.
*Expectation:* (b) judged at the RC on T08 build-first B20–B25 against §A4's resolution of T04 §8.4 (R-123); outcome not known; F1 answered *build*; (a) and (c) met *(amended 2026-09-29, T08 build-first §E.2)*. T08.A70.
*What qualification would cost (F1).* T04 §8.4 preregistered **PTC-R1** (Uppal–Ray–Poore exothermic CSTR, `Da = 0.072`, `B = 8`, `β = 0.3`, `Le = 1`, 21 × 21 starts) with its owner "the first package that registers a reactor with holdup". Run as a bare two-variable residual through T04's generic core it would take about a day, but it fails (b3): no supported flowsheet can select it. Meeting (b3) needs a kinetic CSTR with holdup as a unit model, its mass-mapping derivation (route a), the preregistered comparison, and review: about one to two weeks, outcome not known in advance. A NET-07-based qualification would need a new preregistration (T04 did not register one) and mappings for the exchanger and PH flash: similar cost.
*Options (F1):* (i) tag v0.1 with V14 FAIL on (b), PTC experimental and selectable by explicit policy only, PTC-R1's owner assigned at v0.2 planning (FD6); (ii) build the CSTR-with-holdup route in T08; (iii) hold the tag. *Recommended default:* (i) — the homotopy and all three edges are delivered, and T04 showed that on the registered flowsheets PTC cannot help by structure.

### 4.5 V15 — frozen phases, EO cross-unit specification, multiple roots

*Clauses* (bullet 5): (a) phase disappearance/reappearance under frozen attempts with restart tests (A01); (b) cross-unit specification promotion to EO without nested SM loops (A02; plan T02 A02 test: capability error if a region unit lacks EO derivatives); (c) a multiple-root example with honest branch reporting (D11: no uniqueness or dynamic-stability overclaim).
*Evidence:* (a) T03 (A00–A26); (b) T02; (c) T03's root fingerprint and branch provenance, T06 ADV-05 (A15) and THM-09's branch census (A31); T06 spec §15's "no uniqueness claim".
*Verdict rule:* PASS iff each clause has passing test nodes at the RC (T08.A41) and no certificate or report states uniqueness or dynamic stability.

### 4.6 V16 — corpus, comparisons, ensemble

*Clauses* (bullet 6 and plan §5.1): ≥ 30 distinct correctness/diagnostic cases; eight shared-model comparisons across DWSIM and IDAES; ≥ 2 by both where feasible; the registered §13.4 ensemble.
*Evidence:* T06 verdict 1 (8 of 8 by ≥ 1 tool, 8 of 8 by both, 16/16 AGREE, positive controls DISAGREE); T06 A01 (49 cases, distinctness by mechanism as registered); the ensemble registration (22 × 20).
*T08 adds:* T08.A48 (our side re-solved at the RC equals its committed records; the tool side is not re-run — tool versions and inputs are unchanged, and T06 A48's fingerprints stand). The IDAES near-sharp-ε disclosure travels (envelope limitation L16).
*Verdict rule:* PASS iff T06 verdict 1 stands and T08.A48 passes.

### 4.7 V17 — the agent binding

*Evidence:* T07 verdict (G17 and V17 MET on `v17-c2`, pinned configuration, MCP-only agent evidence). Its §8 limitations travel verbatim (envelope L12).
*T08 adds:* T08.A49: the agent-facing surface at the RC — the served tool descriptions' digest equals R-133's carried surface `171dd768…` (which differs from `v17-c2`'s `6d13e13d…` in exactly `validate.md` and `commit_change.md`), and the operations table's request/response schemas equal `v17-c2`'s — and G16-b's ten scripted reference solutions pass 40/40 over Python, CLI, HTTP and MCP at the RC.
*Verdict rule:* PASS (carried from `c7bbc98`, across R-133's recorded change) iff T08.A49 passes. If the surface differs from R-133's carried surface, V17 is `BLOCKED` pending a new decision of Frank's (F5; a new campaign is billed subscription time). *(amended 2026-10-01, Amendment R3 2)*

### 4.8 V18 — distribution/data gates, rank evidence, energy checks, recovery edges

*Clauses* (bullet 8, [A08/A09/A10]): (a) dependency and data provenance gates including the binary inventory; (b) final target-Jacobian regularity diagnostics; (c) qualified energy checks; (d) no enabled recovery edge without a direct failure test.
*Evidence and T08 work:* (a) P03's audit and ADR 0006; T07's server-extra licence inventory (G19); **T08.A30–A32** — ADR 0006 D5.4's refresh is due because the aarch64 wheel was never audited (ADR 0006 "does not establish") and the default install's other compiled distributions (numpy, scipy and their vendored libraries; the server extra's compiled wheels) have never been inventoried at object level. (b)–(c) K04, T06 A32, A33, A37–A46, re-run at the RC, and **T08.A34** over every certificate the RC job emits. (d) **T08.A33**, the recovery-edge inventory (§5.6).
*Verdict rule:* PASS iff T08.A30–A34 pass. An object in a required closure whose licence is restrictive, GPL-family other than the LGPL Frank allowed (ADR 0006 Q1), or unresolved, and which no ADR dispositions, is FAIL — and goes to Frank as a blueprint §15 reading, as ADR 0006 Q1 did.

### 4.9 V19 — the real-chemistry dossier

*Clause* (bullet 9): "real-chemistry reference journey selected and specified for v0.2 with data and comparison feasibility established"; plan §4.4: "a scored dossier: available validated reactor/kinetics, property coverage, data rights, independent simulator case, computational cost, and a continuous design decision affected by reactor fidelity. Prefer a model Frank's group can actually provide."
*Verdict rule:* PASS iff (i) Frank's selection recorded in ADR 0022 *(amended 2026-10-02, Amendment R7 2)*; (ii) the dossier for the selection has every item of §7.1 (T08.A60); (iii) H1–H6 are all `met` for the selection (§7.2) — `needs_frank` resolved by Frank's statements, `needs_fact` by measurement; (iv) T08.A61–A63 pass; (v) the rights table has no unknown (T08.A64). `BLOCKED` while the selection or a rights statement is outstanding; `FAIL` if the selected chemistry fails a hard criterion after measurement.

### 4.10 V20 — nominal robustness, invalid structure, adversarial suite

*Clauses* (§13.4): (a) all fixed nominal correctness fixtures pass; (b) every injected invalid structural case is rejected for the right reason, **naming the revision's own objects** (§7.7: "return actionable unmatched objects"); (c) no false `VERIFIED` in the adversarial suite; (d) ≥ 95 % verified success over the registered ensemble (20+ cases × 20 starts), with per-case rates and uncertainty.
*Evidence:* T06 verdicts 2 and 3a (run 2; run 1's FAIL stands); T06 A04–A08, A16, A19, A20.
*T08 adds:* **T08.A46** — the registered gate re-run at the RC on `ref-x86-64` and `ci-aarch64` with the registered starts and the unchanged classifier; **T08.A47** — the adversarial and invalid-structure suite at the RC; **T08.A10** — D1.
*Verdict rule:* PASS iff T08.A10, A46 and A47 pass. The one-sided 95 % Clopper–Pearson lower bound is reported, never gated (Frank, T06 Q7). At the gate's threshold S = 418 of 440 it is **0.92937011597863969609**; at run 2's S = 434 it was 0.97326390295610562038 (generator-checked). Both assume independent starts, which clustered starts are not (plan §6.2).

---

## 5. The supported envelope of v0.1

### 5.1 Form

The envelope is a machine-readable file, `benchmarks/t08/support_envelope.yaml`, rendered to the human-readable `docs/support-matrix.md` (the file plan §1.2 names and blueprint §2.2 requires per release) by `scripts/t08_support_matrix.py`, whose `--check` enforces T08.A20–A23. Top-level keys: `envelope_id: v0.1-envelope-1`, `release`, `axes`, `unsupported`, `limitations`, `harvest`. **Unlisted is unsupported** (blueprint §2.2), and every row carries evidence by test node, manifest check id, or ADR/spec section.

### 5.2 Supported (the `axes`)

| Axis | v0.1 statement | Source of truth the check compares with |
| --- | --- | --- |
| Property model | SYN-001 only: ideal vapour, incompressible ideal liquid, VLE; reference convention `SYN-001-ref-v1` (a formation datum, ADR 0011 D2); no critical region, no extra phase | `thermo/` providers = {`syn001`} |
| Components | exactly the three pseudo-components {A, B, C}, declared in any of the six orders and mapped onto the provider's order at binding (T06 A59–A61, R-076); a proper subset, an extra, an unknown or a repeated component is refused `components_unsupported` (U01) — a mixture without one of them is declared with all three and that component's flows exactly zero (ADR 0001 D3); `synthetic: true`; no real identity *(amended 2026-10-01, review 2 Ruling 2)* | provider component set; `canonical_components` |
| Domain | 280–440 K, 50–200 kPa (the provider's predicate) | provider domain |
| Unit models | the thirteen of `MODEL_BUILDERS` (§4.2), each with its registered limitations *(amended 2026-09-29, T08 build-first §E.4)* | `MODEL_BUILDERS` |
| Topologies | acyclic; recycles (single, nested, high-gain) by tear with safeguarded Anderson and restart, or merged to EO; EO regions; cross-unit specifications promoted to EO; exact zero-flow streams and components (ADR 0001 D3; `ZERO_FLOW` regime) | T02, T05b |
| Specifications | the pins `list_models` publishes per model, in the units of ADR 0016's table (one exact spelling each) | `list_models` / `revision_binding.pin_encodings` |
| Solve policies | the four of B27 (`T06-revision-v2`, `T04-W12`, `T08-ptc-v1`, `T08-warm-v1`); PTC selectable by explicit policy only and **experimental**; compatible warm starts by explicit policy only (R-124) *(amended 2026-09-29, T08 build-first §E.4)* | the application's offered list |
| Globalization and recovery | damped Newton (`newton`, `newton_refined`), Anderson recycle, specification continuation via edge 3, sequential restart (ADR 0015); the edge inventory of §5.6; PTC offered as `T08-ptc-v1` (experimental unless V14 (b) passes) *(amended 2026-09-29, T08 build-first §E.4)* | T08.A33 |
| Verification | the four-word certificate; residual accuracy at registered tolerances, not solution accuracy (ADR 0007 F3); the [A08] screen; energy checks qualified as sharing the provider ([A09]) | K04, T06 |
| Reproducibility | R0 structural identity on Linux x86-64 and aarch64; floats within `K04-numerical-policy-v1`; bitwise agreement reported, never promised (ADR 0007 F1) | CI identity job |
| Interfaces | Python (`LocalApplication`), CLI, HTTP (`/v1`), MCP over stdio; the twenty operations of `OPERATIONS`; authority from the credential only (ADR 0019) | `OPERATIONS` |
| Platforms | Linux x86-64 and aarch64, Python 3.13, the lock `ead4edf1…` | CI matrix |

### 5.3 Unsupported, and how each fails (`unsupported`, T08.A22)

Each row names the typed outcome and a test node that demonstrates it; a row whose outcome the build lane cannot demonstrate is a finding (rule 5), not a row.

| Id | Capability | Typed outcome (to be confirmed by the node) |
| --- | --- | --- |
| U01 | real components, or a component set that is not exactly a permutation of {A, B, C} *(amended 2026-10-01, review 2 Ruling 2)* | `validate` INVALID with `COMP-03`; binder `components_unsupported` (T06 A08, A60) |
| U02 | any property method other than SYN-001 | typed refusal at validation or binding |
| U03 | a state outside 280–440 K or 50–200 kPa | `INITIALIZATION_FAILED` at the start (T06 A62); `invalid_trial_state` inside a solve |
| U04 | a model id not in `MODEL_BUILDERS` | typed binder refusal |
| U05 | `validate(task="optimization")`; any study — optimization, parametric sensitivities, sweeps, parameter estimation | `validate` with `task: optimization` ends with ADR 0019's error `unsupported`, detail `task_unsupported(optimization)`, before any analysis; no v0.1 path returns `READY_FOR_OPTIMIZATION` (the value stays in the frozen enum, unused); the other studies have no operation among the twenty of `OPERATIONS`; no optimality claim anywhere *(amended 2026-10-01, review 2 Ruling 1)* |
| U06 | dynamics, time-varying specifications as a solve | not representable (ADR 0008 D1); schema refusal |
| U07 | PTC on a flowsheet whose `holdup_balance` rows lack a registered mapping entry *(amended 2026-09-29, T08 build-first §E.4, §A2)* | `PTC_MAPPING_INVALID` with `ptc_mapping_invalid(<row>, missing)`; PTC is offered as `T08-ptc-v1` on flowsheets whose every `holdup_balance` row has a registered mapping entry (`tp_heater`, `tp_flash`, `kinetic_cstr`); T05 §12.4's refusal for T05 models unchanged |
| U08 | resume, branches, in-band policy administration, MCP over HTTP, further solve policies | `unsupported` (R-110) |
| U09 | second-order derivatives through the property callback | `unsupported`, never zeros (K01) |
| U10 | gauge pressure, unregistered unit spellings | typed refusal (T06 A68) |
| U11 | a region needing EO derivatives a unit lacks | `CAPABILITY_UNAVAILABLE` (T02) |
| U12 | a specification pairing other than one freed column per promoted target | `plan_refused(UNSUPPORTED_RANK_STRUCTURE)` → `unsupported` (T07 rf6) |
| U13 | mode-B artifacts (container, installer, wheelhouse); container replay | not provided (ADR 0006 D1, Q3 default; ADR 0007 F5): a statement, with the clean-environment replay of §8 as what *is* provided |
| U14 | external benchmark (CRAFTS/OpenIDAES-450) comparisons | not run in v0.1 (M06/W27) |

### 5.4 The alias-pressure-shift limit, in closed form

ADR 0014 D5 (T06 spec §8.2) shifts pressure column `j` — its 0-based position in `variable_ids` — by `s_j = 997 (j + 1)` Pa: up if the provider admits `P + s_j`, else down if it admits `P − s_j`, else the alias certificate is `unsupported(pressure_shift_outside_domain)` and the verdict `UNVERIFIED`. On SYN-001's inclusive domain [5e4, 2e5] Pa:

  **the column is certifiable iff 997 (j + 1) ≤ max(200 000 − P, P − 50 000).**

Sanity values (exact integers, generator-checked): first unsupported position **100** at P = 100 kPa; **75** at 125 kPa (the worst pressure); **130** at 180 kPa (`j = 19` shifts up, `j = 20` down); **150** at either domain edge. NET-11's registered column (`S4.P = 1.8e5`, shifted to 204 925 Pa, hence `j = 24`) now goes down, as T06 A39 registers. The rule is monotone in `j`. This replaces T06 Q25's "from roughly 20 streams on" (FD10): the stream count at which position 75 is reached depends on the flowsheet's layout, and the envelope states the position rule, not a stream count. T08.A24 checks the implementation at the threshold states.

### 5.5 Registered limitations (`limitations`), the seed list

The build lane completes this list from the harvest (§5.7); the rows below are the ones this specification already knows. Class E rows appear in the support matrix and the release notes.

| Id | Limitation (user-facing) | Evidence |
| --- | --- | --- |
| L01 | PTC is experimental: selectable by explicit policy only; no qualified family (V14 clause b) | T04 spec §8; ADR 0010 |
| L02 | A zero-duty lifted flash whose root lies exactly on its dew or bubble point is `UNVERIFIED`, `RANK_DEFICIENT`; nearby two-phase-attempt stops are caught `FAILED(false_success_detected)` | T05b §17, §18 Q9; T06 A07, A92 |
| L03 | The alias-pressure-shift limit of §5.4 | ADR 0014 D5; T06 §8.2, Q25 |
| L04 | A saturation-closure failure inside the rows' own window is `FAILED`, where `UNVERIFIED(label_not_demonstrated)` would be exact (conservative) | T06 Q24 |
| L05 | `VERIFIED` certifies residuals at registered tolerances; the solution-error bound is recorded, not promised | ADR 0007 F3 |
| L06 | Energy checks share the property provider with the solver ([A09]) | K04; T06 A33 |
| L07 | Bitwise float reproduction is reported, never promised; per-start ensemble outcomes differ across architectures | ADR 0007 F1; T06 A35 |
| L08 | Property-call counts are within-platform diagnostics; `newton_refined` can exhaust the property budget where `newton` finishes | ADR 0007 D5; ADR 0018 D4′ |
| L09 | The robustness claim is the nominal profile only; the stress profiles were not run | T06 §6.7 |
| L10 | The initializer chain is partial (blueprint §7.4, K03 §10.1): GUESS-role specifications are not bound by the revision binder (such revisions run on `legacy_eo`), the SYN-001 tear path has its registered initializer only, and the one fallback between initializer sources is `T08-warm-v1`'s compatible warm start → traversal (opt-in; L-WS-1, L-WS-2) *(amended 2026-10-01, review 2 Ruling 3)* | T03 spec §13; K03 §10.1; T07 S-G; ADR 0024 |
| L11 | Cancellation: `verify` has no cooperative checkpoint; a region's events are lost on interrupt | T07 W4b |
| L12 | Agent evidence: one pinned model and configuration, MCP only, not out of sample (CP lower bound 0.681); T09 0/6, T10 1/3; INJ-4 never exposed | T07 verdict §7–§8 |
| L13 | `worker.log` readable through `get_artifact` | T07 W6e-Q2 |
| L14 | The v0.1 rank rule: exactly one freed column per promoted target | T02 §7.1; T07 rf6 |
| L15 | Linux x86-64 and aarch64 only; Python 3.13; the one lock | CI; K05 |
| L16 | IDAES agreement holds at the registered near-sharp SmoothVLE ε only | T06 A83 |
| L17 | Reference environment DWSIM runs on .NET 8, end of life 2026-11-10 | `docs/reference-environments.md` |
| L-CSTR-1 | The kinetic CSTR's rate law and coolant model are synthetic (the Frank-Kamenetskii `γ → ∞` form and a coolant capacity rate); no Arrhenius or physical-conductance claim is made | T08 build-first spec §A1.1, §A1.3; ADR 0023 |
| L-CSTR-2 | An adiabatic, dormant kinetic CSTR's outlet temperature is a singularity (T05 §4.7 (a)); v0.1 does not certify an EO solve in which it appears | T08 build-first spec §A1.4; T05 §4.7 (a); ADR 0023 |
| L-CSTR-3 | The kinetic CSTR's causal evaluator is a local model initializer (the isothermal state at `T_init`), not a steady state | T08 build-first spec §A1.4; ADR 0023 |
| L-WS-1 | Warm-start compatibility is exact id-set identity; a topology edit is a typed rejection to the next source, not a partial or adapted match | T08 build-first spec Part B; ADR 0024; R-124 |
| L-WS-2 | The warm-start source is chosen automatically (the lineage's latest VERIFIED state) under an opt-in policy only; no request-named source exists in v0.1 (v0.2, M03) | T08 build-first spec §I; ADR 0024; R-124 |

*(L-CSTR-1..3, L-WS-1..2 added 2026-09-29, T08 build-first §E.5.)*

| L22 | Scope of the solver evidence: tear selection is greedy (minimality not claimed); behaviour finer than the registered basin margins and trajectories below a residual of 1e-6 are not established; several stated rules are exercised only by synthetic fixtures | T02 spec §12; T03 spec §13 |
| L36 | No performance claim at size: costs are within-platform measurements on registered cases of at most tens of variables; compiles per plan run and the regularity screen's cost at size are not measured | T02 spec §12; T03 spec §13; T06 spec §15 |
| L37 | `verify` is not safe to run concurrently in threads of one process: the regularity screen seeds and restores numpy's global generator around `onenormest` (T06 §8.1, R-069), so concurrent calls can move the estimate, `rcond₁`, the bound and a regularity verdict near its threshold; jobs run in separate processes and are unaffected | T06 spec §16 (Q27) |
| L38 | Structural analysis is generic: validation's STR checks and `inspect_structure` report structural rank and the DM/BTF partition only; numerical rank, conditioning and feasibility are judged by the certificate's regularity screen at a converged state (blueprint D05) | T01 spec |
| L39 | The structural-zero release (recovery edge E5) leaves no trace record: a trace does not show that it ran | `docs/recovery-edges.yaml` E5 |
| L41 | A bundle written by an installed package (wheel or sdist, not the source checkout) carries no dependency-set identity: the package ships no lock file, so its `lock_sha256` is empty and every replay of it is `inspected_archived_results` / `NOT_RUN` ("the dependency set is unknown …"); replayable bundles are written from the source checkout at the lock `ead4edf1…` *(added 2026-10-01, Amendment R3 5)* | T08.A19; ADR 0007 D4 |

*(L22 replaced, L36–L39 added 2026-10-01, review 2 Ruling 4; rows L18–L21, L23–L35 stand as filed in `benchmarks/t08/support_envelope.yaml`'s `limitations` list, which this spec's seed does not carry.)*

### 5.6 The recovery-edge inventory (V18 clause d; T08.A33)

A **recovery edge** is any path that, on a detected failure or insufficiency of one method, runs a different method or a re-initialization within the same solve or verification, without changing fixed physics or specifications ("a fallback may change the method, never the problem"). Each row: trigger, precondition, maximum count, the injected failure and its test node, the evidence that `model_version`, `constants_sha256` and the specifications are unchanged, and `enabled` ∈ {default, policy-only, library-only, absent} (`library-only`: no application-offered policy and no `MODEL_BUILDERS` unit reaches the edge, pinned by a test that fails when one does; such a row meets every clause an enabled row meets). Evidence is one of: **(i) `identity_compared`** — a test compares the edge's instance with the failed or target one in `model_version`, `constants_sha256` and specifications (T04 §5.4), or, for an edge acting inside one call on a caller-owned problem, shows every evaluation before and after the edge made on the same problem object with equal pinned values; **(ii) `verified_certificate`** — a test in which the edge demonstrably fires (its label or provenance asserted) ends `VERIFIED` by `verify_revision`/`verify_bound` against the bound revision; it shows the reported state is a root of the unchanged problem, not that every intermediate instance was unchanged; **(iii) `guard`** — the edge's path passes an identity guard before the new instance is used, and a test injects a change of each field the row claims (`model_version` and `constants_sha256`; specification values enter through `constants_sha256`) and sees it refused. A cross-binder fallback is held to the problem, not to `model_version`: its guard is `legacy_admission`'s C0–C5 (T07 ruling round 7). *(amended 2026-10-01, review 2 Ruling 6)* The inventory is `docs/recovery-edges.yaml`: it spells policy literals that the T05b/T06 literal guards forbid in registered cases, fixtures and references, which it is not. *(amended 2026-10-01, review 2 Ruling 12)* Seed, to be completed by a code audit:

| Edge | Source |
| --- | --- |
| E1 Anderson restart/damping on stagnation | T02 §5.6; A13–A15 |
| E2 stalled recycle → EO merge | T02 §4.4; A32 |
| E3a EO globalization failure → specification continuation | T04 §5; HOM-04, HOM-05 |
| E3b EO failure on a revision region → sequential restart | ADR 0015; T06 A63, A64 |
| E4 bounded phase-attempt restart | ADR 0005; T03 |
| E5 structural-zero release (where Newton would end `BOUND_BLOCKED`) | K03 §5.3 as amended by T05b |
| E6 PH kernel temperature route → band route | T05b §5 |
| E7 phase-contract v2 TP fallback and the recorded fallback chain | ADR 0012 D4 |
| E8 terminal Newton refinement | ADR 0018; T06 A88 |
| E9 initializer candidate rejected → next source | K03 §10.1 |
| E10 verifier: fresh-flash check at `x_final` when the projection is refused | ADR 0013 D1; T06 Q24 |
| E11 `validate()` revision-binder fallback | ADR 0020 F5 |
| E12 PTC core (policy-only, experimental) | T04 |
| E13 outcome fallback `revision_eo` → `legacy_eo` (**absent**: not built, T07 F6) | T07 D-Q3 |

The executable half of T08.A33 is a bijection: every fallback label, `eo_recovery` value, `restart`/`acceleration`/`homotopy_step` event producer and `fallbacks` entry the code can emit maps to exactly one row, and every enabled row has a passing direct test. The build lane chooses the mechanism (for example a registry constant of fallback labels that the emitting sites use); the acceptance test is that adding a label without a row fails, and deleting a row whose label is still emitted fails.

### 5.7 Completeness: the harvest (T08.A21)

`harvest` lists every `limitations[]` entry and every non-`pass` check of every manifest under `evidence/` (today 18 manifests; P00–K06 carry 87 limitations, T01–T07 carry 145), each keyed by manifest path, index and the SHA-256 of its text, and classified exactly once: **E** (user-facing; points to one or more L-rows of §5.5 or U-rows of §5.3), **S** (superseded or closed; points to the closing test node or passing manifest check, or to a document only when the closing fact is that document's existence and it did not exist when the item was written — a status inside a document that already existed is closed by a test asserting it), **P** (provenance or process note needing no closure; stays in its manifest), **B** (an open defect or follow-up not closed in v0.1; points to a backlog id of §6.3). A compound item takes the first applicable class in the order E, B, S, P; its pointers name a row for every user-facing part, and an E item may also carry the backlog ids of its B parts. A defect handed on is never P: it is S when closed, E when a user can reach it, else B. *(amended 2026-10-01, review 2 Ruling 4)* The check fails on an unmapped item, a dangling pointer, or a changed text hash. The build lane drafts the classification; the design-lane `reviewer` checks it (a misfiled E-as-P hides a limitation).

---

## 6. Record defects, T07's hand-ons, and the backlog

### 6.1 Classification

"Blocks RC" means the release candidate cannot be declared until the item is closed (§8.1); it does not change a gate verdict judged on registered evidence, because the registered assertions never reached these paths — which is itself why each gets a registered assertion now.

| Item | Found by | Classification | Why | Work, assertion |
| --- | --- | --- | --- | --- |
| **D1** STR-03's message names the SYN-001 binder's internal id `U-HEAT` instead of the revision's instance id (`application/validation.py:385`) | probe of `main` at `5c1f8ac` | **Blocks V20 clause (b)** (and V11 (c)) | §13.4 "rejected for the right reason"; §7.7 "actionable unmatched objects": an id the caller never wrote is not actionable | W1.2; T08.A10 |
| **D2** `verify/failure.py:188` reads `getattr(result, "plan")`, absent on the region result view: every region failure bundle has empty-string `replay_identity`; revision-path certificates have empty `policy_id`/`plan_id` | probe | **Blocks the RC**; design-lane review required (replay identity) | blueprint §8.1 (a certificate includes policy hashes), §8.2 (a bundle includes replay identity); an empty string reads as a value — rule 5 | W1.4; T08.A11, A13; F4 |
| **D3** failure bundles report `property_calls` 0 where the trace meter says 202 (e.g. `SYN-001-A02-352-vapor-guess-410`, `HOMOTOPY_STALLED`); cause not isolated; hypothesis: the region result's counters omit the executor's meter (`orchestrator/executor.py:883`) | probe | **Blocks the RC**; cause isolated before any fix | §8.2 budgets; a false zero is the accidental zero rule 3 forbids | W1.3; T08.A12, A13 |
| Unmapped `orchestrator/rank.py::UnsupportedRankStructureError` (raised by `eliminate_alias_rows` at solve and verify; not mapped by `solve_route`) | T07 review 2 | **Blocks the RC if reachable** from a public operation; else backlog with the probe as evidence | an `internal_error` for a typed condition | W1.5; T08.A14 |
| R4-O2 (the verifier's own failed property call), R4-O1 (Unicode noncharacters) | T07 → design lane | **Blocks the RC if** either yields an untyped end or a wrong verdict; else backlog B7 | rule 5 | W1.5; T08.A14 |
| A89's exact refinement count failed once on aarch64 and passed on re-run (`d1c4ee5`, CI 36440983702) | T07 CI | **Blocks the RC** (CI must be deterministic); a T06 spec amendment by the design lane after measurement | ADR 0018 fires on an adaptive floating-point decision; blueprint §8.3 excludes those from any cross-platform bitwise promise, and ADR 0007 D2.5 measured same-class runners differing in the last bits | W1.6; T08.A15 *(discharged 2026-10-01: T08.A15 met, 21 of 21; T06 A89 amended, Amendment R3 6)* |
| Run records lack the lock hash (T07 verdict §7.6; T06 P3) | T07, T06 | **Blocks the RC's own campaigns** (not retroactive) | a new record must be attributable | W1.7; T08.A16 |
| R-088 Q24 | T06 | backlog B1; envelope L04 | conservative: can only make a certificate stricter | — |
| R-088 Q25 | T06 | backlog B2 (a K04 amendment before M01's larger flowsheets); envelope L03 | typed and conservative; §5.4 gives the exact limit | — |
| T05b §18 Q9 | T05b | backlog B3 (K04 follow-up); envelope L02 | typed `UNVERIFIED`, never a false `VERIFIED` | — |
| S-R5 (a name for tighten-only policies) | T07 | backlog B4 | naming | — |
| S-G (GUESS roles on the revision binder) | T07 | backlog B5, with warm starts if F2 (ii) | initializer chain; envelope L10 | — |
| F6 (`revision_eo` → `legacy_eo` fallback) | T07 | backlog B6; inventory row E13 `absent` | no registered case needs it (D-Q3 count 0); an unbuilt edge is not an untested one | — |
| V17 generality; W4b limits; `worker.log` | T07 | envelope L11–L13 | limitations of scope, all recorded | — |

### 6.2 Identity re-registration (D2, D3)

The D2 and D3 fixes change bytes in certificates and failure bundles, and any identity key that contains them moves (the `t07` key is the expected one). The brief's constraint is that registered keys stay as registered. A move is admissible only as a **substitution**: with the fix's new values replaced by the old ones (empty strings; the wrong counter), the identity document must reproduce the registered one byte for byte, and the diff between the old and new documents must consist only of the fields the fix names (T08.A13, ADR 0017 D3's precedent). ADR 0017's identity move was approved by Frank; this one goes to him as F4 with the default "approve a substitution-only move". Any other moved byte stops the work and comes back to the design lane.

ADR 0025 D1.2's recording switch is a second substitution of this kind (R-148). The substituted field is `numerical_policy_id`, v2 for v1, at its two sources, together with the hashes that cover it. The proof is `tests/t08_v2_substitution.py`. *(added 2026-10-02, Amendment R5 1)*

The rename of the import package to `openflowsheet` is a third (R-149). The substituted values are the two self-hashes whose modules name the package — the SYN-001 provider's `implementation_sha256` and the T06 generator's `generator_sha256` — together with the hashes that cover them. The proof is `tests/t08_rename_substitution.py`. *(added 2026-10-02, Amendment R6 1)*

### 6.3 v0.2 backlog (from T08)

B1 R-088 Q24; B2 R-088 Q25 (the ordinal among pressure columns, a reversal of ADR 0014 D5's rejected alternative, needs its own decision); B3 T05b Q9; B4 S-R5; B5 S-G (and warm starts, if not built in T08); B6 F6; B7 R4-O1, R4-O2 if not RC-blocking; B8 PTC-R1 qualification (owner assigned at v0.2 planning, FD6); B9 the full OpenIDAES-450 numerical cross-check (a plan amendment by ADR after v0.1, per the audit).

B10 handed-on follow-ups, unreachable or harmless in v0.1: a `CONVERGED` result without `x_final` yields a schema-refused certificate (T03 review §8; refuse the input, or a nullable `regularity` by ADR); K02 `TPFlash.evaluate` does not apply R-007 to a declared inlet phase (T05 §20 F7); `CheckPolicy.sha256` covers the tolerance table only, not §7's thresholds and the required-check list (K04-F9 F4; a K04 revision, an identity change); T05b re-review N-W5 (augment's recursion) and N-W6 (the release acts only at `α_max = 0`). B11 a trace record for the structural-zero release, recovery edge E5 (an identity change if the record enters R0). *(B10, B11 added 2026-10-01, review 2 Ruling 9)*

B12 a verified dependency-set identity for installed packages (envelope L41): the wheel carries the lock, and `environment()` records its hash only after checking every locked distribution's installed version against it, else empty — an ADR 0007 D4/D6 amendment, because it changes what `lock_sha256` attests. *(added 2026-10-01, Amendment R3 5)*

**M06 contract asks (v0.2/M06 only; each needs an ADR 0019 amendment before it is built):** M06-1 `inspect_structure` returns the validation structural report when no route binds; M06-2 a specification → residual-rows map; M06-3 `NewtonResult.blocked_by` in failure-bundle observations; M06-4 a `list_audit` operation; M06-5 operations with their rights in `get_project`.

---

## 7. V19 — the real-chemistry dossier

### 7.1 Required contents (for the selected chemistry; T08.A60)

1. **Chemistry**: reactions, stoichiometry, reversibility, heat of reaction and its source.
2. **Component set**: ComponentRecords with identifiers, molar mass, elemental composition and `rights` (the schema already requires `rights`).
3. **Loop topology** for the v0.2 journey (fixed topology), with every unit not in v0.1's library flagged (a recycle compressor is the likely one).
4. **Reactor**: the PyMRM model — repository, commit, PyMRM version, equations reference, boundary mapping sketch (inlet `(n, T, P)` → outlet), DOF, reference-state compatibility with ADR 0011's formation datum, and the measured cost of one solve.
5. **Kinetics**: rate law, parameters, source, the comparison with experimental data and its domain.
6. **Nonideal property route** (W22 "needed"): method, parameters and sources, domain, conformance reference (an independent implementation and experimental data), and what the route must supply to the provider contract (fugacity coefficients, enthalpy departures, phase split).
7. **Reference route**: independent tool(s), a representability table in T06's form (`idaes_representability.py`), smoke evidence (T08.A62, A63), version pins; independent reactor data where it exists.
8. **Rights table**: every code and data item — source, licence or permission, scope, distribution mode (A or C by reference), attribution (T08.A64).
9. **The continuous design decision** that reactor fidelity moves, with the argument why.
10. **Computational cost** at design-loop resolution.
11. **What M01 pins** (reactor version, property route) and its known invalid requests.
12. **What the dossier does not establish.**

### 7.2 Selection rubric (preregistered here, before any candidate is measured)

**Hard criteria** (each `met`, `needs_fact`, `needs_frank` or `fails`; a candidate with a `fails` is not selectable; a candidate is selectable *now* only when all six are `met`):

- **H1 reactor route** — a steady PyMRM reactor model for the chemistry runs, or can be written from published equations with no new science.
- **H2 kinetics** — a published rate law with parameters, compared with experimental data.
- **H3 needed nonideal route** — the loop's conditions need one, and a method and parameter source are identified.
- **H4 independent reference** — an acquired tool (IDAES 2.13 or DWSIM) represents the loop skeleton with the selected method, or a published independent case exists. *("the selected method" read for C1 by Amendment R3 8 (a), 2026-10-01)*
- **H5 rights** — every code and data item has known rights compatible with modes A/C.
- **H6 scope** — steady-state VLE inside blueprint §2.2's v0.2 envelope (no electrolytes, solids, LLE or columns needed for the loop).

**Scored criteria**, 0/1/2, unweighted:

| Id | Criterion | Anchors |
| --- | --- | --- |
| S1 | Frank's group can provide the reactor model (plan: "prefer") | 2 found and runnable in the group's code; 1 named but not found; 0 none |
| S2 | reactor–separator–recycle native to the chemistry (blueprint §2.3) | 2 recycle with purge is how the process runs; 1 recycle needs a separation outside v0.2's units; 0 no recycle |
| S3 | a continuous design decision moved by reactor fidelity | 2 qualitatively; 1 quantitatively; 0 not at all |
| S4 | independent simulator case | 2 a published case of the same chemistry exists in an acquired tool; 1 representable but must be built; 0 none |
| S5 | reactor validation data | 2 experimental, at hand, machine-readable; 1 in the literature; 0 none |
| S6 | M01 size | 2 ≤ 5 components, 1 reaction, one nonideal method; 1 ≤ 7 components or 2 independent reactions or two methods; 0 larger |
| S7 | cost of one reactor solve at design-loop resolution | 2 seconds; 1 minutes; 0 hours |
| S8 | reuse beyond v0.2 (W27 overlap; v0.3 columns) | 2 both; 1 one; 0 neither |

**Ranking:** selectable candidates by total, ties broken by S1, then S2, then S4, then id. **Provisional** scores (resting on an unmeasured fact) are marked; the generator reports, for each, whether moving it over 0…2 changes the top choice.

### 7.3 Candidate assessment

Facts marked *measured* were read on 2026-09-29 from a local copy of the OpenIDAES-450 release (`openidaes450-demo-2026-09-26`, in another session's scratchpad — not durable, FD9) and from this machine's PyMRM install and the group repository; they are not registered until W3.1 re-measures them into the repository.

**C1 — Ammonia synthesis loop on the group's PyMRM model.** *Measured:* the group repository `computational-chemical-engineering/ammonia_synthesis_reactor` (a local checkout on the development machine) is a packed-bed (membrane) reactor model for N₂ + 3H₂ ⇌ 2NH₃ with a 2D axisymmetric solver and a 1D counterpart, both built on `pymrm` (installed: `pymrm` 2.1.20, MIT, maintained by E.A.J.F. Peters); a kinetics class with adsorption constants for H₂ and NH₃ and fugacity coefficients; a property database with `Tc`, `Pc`, `ω`, heat-capacity and transport coefficients; an experimental dataset (`data/inputs/ammonia_synthesis_data_rossetti_et_al.csv`: outlet NH₃ against GHSV at 50–100 bar, 370–460 °C and H₂/N₂ of 1.5 and 3, 18 conditions); regression tests; **no licence file**. The loop — reactor, cooler, high-pressure flash condensing NH₃, purge, recycle — is SYN-001's flash–recycle–purge journey with a real reactor. The flash needs a nonideal route (H₂ and N₂ are supercritical; Raoult's law is meaningless for them): a cubic EOS (PR or SRK), whose pure-component parameters the group database already carries. The elemental balance (N, H) becomes meaningful for the first time (SYN-001: `NOT_APPLICABLE`). *Continuous decision:* the reactor inlet temperature — an equilibrium reactor favours ever-lower temperature for an exothermic reaction, a kinetic reactor gives an interior optimum, so fidelity changes the decision qualitatively; alternative: the purge fraction. *Hard:* H1 `needs_fact` (run the regression test in a pinned environment; confirm a no-membrane configuration or write a plain packed bed from the same kinetics); H2 `needs_frank` (which published rate law, and the group's comparison with the data); H3 `met`; H4 `needs_fact` (no OpenIDAES case — build a PR loop skeleton in IDAES; IDAES's modular cubic EOS and a custom rate expression are the expected route); H5 `needs_frank` (the repository has no licence; the dataset's provenance; the property database's sources); H6 `met`. *Scores:* S1 2, S2 2, S3 2, S4 1, S5 2, S6 2, S7 1 (provisional), S8 0 → **12**. *Cost to M01:* a PR provider (cubic root selection is new phase logic), an out-of-process PyMRM adapter, likely a compressor or a zero-ΔP loop convention, inerts (Ar/CH₄) for a meaningful purge.

**C2 — Methanol synthesis loop.** *Measured:* OpenIDAES `blind_synthesized_methanol_recycle` (native IDAES; mixers, compressor, heaters, **StoichiometricReactor**, turbine, flash, purge separator; components CH₄, CO, H₂, CH₃OH; `thermo_params_vapor` ideal gas and `thermo_params_VLE` ideal/ideal with SmoothVLE) exists with its residual check passing; also single-pass and two-bed cases, and `variant_methanol_water_nrtl_partial_condensation` (activity-coefficient NRTL, ideal vapour). So the independent case covers the loop *skeleton* at ideal properties and fixed conversion — not the kinetics and not the nonideal route. Rights: MIT plus the first author's data-use permission (e-mail to Frank, 2026-09-26). *Hard:* H1 `met` (a PyMRM packed bed can be written from published equations), H2 `needs_fact` (name the rate law and its validation), H3–H6 `met`. *Scores:* S1 0 (provisional: no group model found), S2 2, S3 2, S4 2, S5 1, S6 1 (CO/CO₂/H₂/H₂O/CH₃OH, two independent reactions, gas EOS plus liquid nonideality), S7 1 (provisional), S8 2 → **11**.

**C3 — Ethylene glycol by EO hydration.** *Measured:* OpenIDAES `official_idaes_eg_{stoichiometric,cstr,pfr}_flowsheet` are once-through, liquid-only ideal, one reaction (EO + H₂O → EG) with sulfuric acid as a component; no separation, no recycle. The fidelity story is strong (DEG selectivity against back-mixing), NRTL is the cheapest nonideal route, but the recycle needs water removal outside v0.1's units and the IDAES case covers no selectivity. *Scores:* S1 0 (provisional), S2 1, S3 2, S4 2, S5 1, S6 2, S7 2 (provisional), S8 1 → **11**; H2 and H6 `needs_fact`.

**C4 — HDA loop.** IDAES HDA cases exist (flash with recycle; ideal VLE; stoichiometric reactor). The homogeneous gas-phase reactor gains little from PyMRM, and whether the journey *needs* a nonideal route is doubtful (H3 `needs_fact`). **10**.

**C5 — Steam methane reforming.** IDAES equilibrium/Gibbs cases only; no native recycle; ideal gas adequate at reformer conditions (H3 `needs_fact`). **5**.

### 7.4 Ranking, recommendation, and what would change it

Generator ranking: **C1 (12), C2 (11), C3 (11), C4 (10), C5 (5)**; C2 over C3 by the tie-break on S2.

- **Recommended: C1, the ammonia synthesis loop.** It is the only candidate for which a group reactor model was found; it runs on the group's own MIT-licensed PyMRM, and the experimental data it is meant to reproduce are in hand; its loop is SYN-001's journey with a real reactor; it needs exactly one nonideal route, and a necessary one; its design decision changes qualitatively with reactor fidelity. Its costs: no published independent loop case (the reference must be built in IDAES and checked for representability), a cubic EOS with root selection, a probable compressor, and three statements only Frank can give (H2's rate-law provenance, H5's code licence and data provenance).
- **Runner-up: C2, the methanol synthesis loop.** Its independent IDAES loop cases already exist and are rights-cleared, it overlaps OpenIDAES for W27, and its methanol–water NRTL case feeds v0.3's columns. It loses on the model the group can provide, and its IDAES cases reference neither the kinetics nor the nonideal route, so the scientific comparison would still have to be built.
- **Sensitivity (generator-checked).** No single provisional score moves the top choice. What moves it: a hard criterion failing for C1 (H1 or H5 — then C2 is first), or Frank naming a group model for another candidate (that candidate's S1 → 2 puts C2, C3 or C4 first).

### 7.5 What can be verified offline now, and what needs Frank

*Offline, no cost:* running the group's regression test and timing the 1D model (T08.A61); IDAES smoke of a PR flash at a loop state and of the loop skeleton (T08.A62, A63; `scripts/build-reference-envs.sh`); re-acquiring OpenIDAES-450 into hash-referenced evidence artifacts and re-measuring §7.3's facts (W3.1); rerunning `blind_synthesized_methanol_recycle` under idaes-pse 2.13 with the version difference recorded (for the runner-up).
*Frank:* the selection (F3); whether a group model exists for another candidate; the licence of the group's reactor code as a dependency used by reference (not vendored); the provenance and permitted use of the Rossetti et al. dataset and of the property database's coefficients; any data purchase or outward request.

---

## 8. The release candidate

### 8.1 Definition

A **release candidate** is a commit `C` on `wp/T08` such that:

1. **Tree.** `src/`, `schemas/`, `benchmarks/`, `requirements.lock` (sha256 `ead4edf1…`, T08.A40) and `pyproject.toml` are as they will be released, with version **`0.1.0rc1`**. The lock is not edited in T08: a changed lock changes every registered bundle's replay mode to `inspected_archived_results` (ADR 0007 D4), which would silently retire the registered replay evidence (FD4).
2. **RC blockers closed.** D1–D3, the typed-ends sweep, A89, the record fields (§6.1) — T08.A10–A16; review 2's rule-5 defects — U05 (T08.A22's U05 node) and the CLI rerun (T08.A17); the design-lane review of the MCP tool descriptions (T08.A18). *(amended 2026-10-01, review 2 Ruling 13)*
3. **Envelope.** `support_envelope.yaml` and `docs/support-matrix.md` pass T08.A20–A24; the recovery-edge inventory passes T08.A33.
4. **RC job** (§8.2) completed at `C`, its records committed (small text under `evidence/T08/<C>/rc/`, large files under `evidence/T08/<C>/artifacts/` by hash), T08.A19, A30, A34, A41–A49 passing *(amended 2026-10-01, Amendment R3 5; amended 2026-10-02, Amendment R7 1)*.
5. **Documents.** A draft `CHANGELOG.md` section for v0.1.0 (ADR 0021 D4), `docs/reviews/T08-verdicts.md` (T08.A03), `scripts/v0_1_gate.py` (T08.A50), and `evidence/T08/<C>/manifest.json` with `status: tested`.
6. **Nothing outward.** No tag, no publication, no data acquisition needing rights.

### 8.2 The RC job

| Step | What | Assertion |
| --- | --- | --- |
| 1 | `scripts/check.sh` on `ubuntu-latest` and `ubuntu-24.04-arm` | T08.A41 |
| 2 | The identity job: equal documents on both, equal to the registered one except §6.2's substitutions; unchanged under a trial version string `0.1.0` | T08.A42 |
| 3 | Build sdist and wheel twice from `C` with `SOURCE_DATE_EPOCH` = `C`'s commit time; inspect contents | T08.A43 |
| 4 | Clean install on fresh runners of both architectures, outside the source tree, dependencies at the lock's versions, the RC wheel `--no-deps`; CasADi's installed files against the audited per-file hashes; smoke solve; the installed package's lock lookup and its bundle's replay *(amended 2026-10-01, Amendment R3 5)* | T08.A44, A19 |
| 5 | Write the RC bundle set on CI x86-64 from the source checkout; replay it on a fresh x86-64 runner and on aarch64 | T08.A45 |
| 6 | The registered ensemble on `ref-x86-64` (local) and `ci-aarch64` (dispatch), and on each class the same-class replay of its first starts and retained failures (T06 A34) *(amended 2026-10-01, Amendment R3 1)* | T08.A46 |
| 7 | The adversarial, invalid-structure and reference subsets, reported explicitly | T08.A47, A48 |
| 8 | The agent surface digest and G16-b over four transports | T08.A49 |
| 9 | The [A10] inventory on both architectures | T08.A30 |
| 10 | Certificates emitted by steps 4–7: regularity evidence and [A09] qualification present | T08.A34 |
| 11 | `scripts/v0_1_gate.py` | T08.A50 |

The clean-environment replay of step 5 discharges ADR 0007 F5's "clean-container replay … becomes a named acceptance item of K06 or T08" in its clean-environment sense, and supersedes K05's `unsupported` check (harvest class S). A container stays unsupported: building one the project publishes is mode B (ADR 0006 Q3 default: no mode-B artifact before v0.2).

### 8.3 What T08 may do, and what is Frank's

*T08 may:* set `0.1.0rc1`; build sdist and wheel locally and in CI (not published); dispatch CI, including the ensemble (existing practice since T06); push `wp/T08` and merge it with `status: tested` (standing authorization of 2026-09-17); write the CHANGELOG draft.
*Frank's:* the dispositions F1 and F2; the selection F3; the identity re-registration F4; a new agent campaign F5 (only if the surface changed); human review sign-off of T01–T08, if he chooses to give it (R-017's qualified form); the version bump to `0.1.0` and the tag, on a commit whose distribution sources (`src/`, `schemas/`, `benchmarks/`, `requirements.lock`, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`, `NOTICE`) equal the RC's except the version value (checked by `v0_1_gate.py`; Amendment R3 4); every publication (GitHub release, repository visibility; no PyPI, plan §2). If the tagged tree differs from the RC's in those paths, the RC job is re-run. *(amended 2026-10-01, Amendment R3 4)*

---

## 9. Assertion catalogue

Tolerance column: **exact** means equality of integers, strings, hashes or sets; no roundoff enters, and the smallest error worth catching is one character or one count. Where a float is compared, the tolerance is a registered one, cited with its argument; T08 registers none.

| ID | Subject and state(s) | Expected | Tolerance and why | Judged by |
| --- | --- | --- | --- | --- |
| T08.A00 | `t08_reference.py --check` | every claim passes; committed YAML equals the regenerated bytes; this table's ids equal the generator's catalogue, unique and sorted; one summary row per gate | exact | generator |
| T08.A01 | The fourteen cited manifests (§3.1) | one manifest per package, commit prefix, status and check tallies as quoted | exact | generator |
| T08.A02 | `docs/requirements.yaml` V11–V20 | `evidence` lists at least the §3.1 manifests of each gate's "gates it serves" and `evidence/T08/<C>/manifest.json` for V18–V20; `verdict` set only to the value in `docs/reviews/T08-verdicts.md` (a test compares them) | exact | test |
| T08.A03 | `docs/reviews/T08-verdicts.md` | the one verdict table of Amendment R3 §R3.3 — headers `Gate`, `Verdict`, `Failing clauses`, `Travelling limitations`, `Basis`; ten rows `V11`…`V20` in order, each judged at `C` against §4; each FAIL naming its failing clauses as `Vnn (x)`, each BLOCKED naming its blocked clauses and the missing input, each PASS `—` there; travelling L-ids in their own column; every verdict word equal to `docs/requirements.yaml`'s *(amended 2026-10-01, Amendment R3 3)* | exact (presence and pattern) | verdict |
| T08.A10 | D1. States: (i) the registered `SYN-001-conflicting-heater-spec` (STR-03; heater instance id `heater`); (ii) the same revision with the heater instance renamed `h-2` and its two specifications re-pointed | (i) `INVALID`, check STR-03 `FAIL`, `STRUCTURAL_OVER_SPECIFICATION`, excess 1, implicated exactly `[SPEC-heater-outlet-T, SPEC-heater-duty, heater]` (registered, T01 A09 — unchanged), and the STR-03 message names `heater` and contains no `U-HEAT`; (ii) the same with `h-2`, and neither `U-HEAT` nor `heater` in the message | exact. (ii) catches a fix that hard-codes `heater`; (i)'s registered fields catch a fix that moves the registered case | test |
| T08.A11 | D2. States: (a) a region failure bundle (NET-02 edge-off, `BOUND_BLOCKED`, T06 A63); (b) a revision-path `VERIFIED` certificate (a registered revision that binds on `revision_eo`, e.g. T05's C1); (c) a tear-path failure bundle (`SYN-001-capped-budget`, control) | every `replay_identity` field and the certificate's `policy_id`, `plan_id` non-empty **and equal to** the identifiers of the plan and policy the run actually used, read from the run's own records (its trace and its `SolvePolicy`); (c) unchanged | exact. Equality to the run's own ids, not non-emptiness, so junk cannot pass | test |
| T08.A12 | D3. States: (a) `SYN-001-A02-352-vapor-guess-410` (`HOMOTOPY_STALLED`; trace meter 202); (b) a region failure without homotopy (NET-02 edge-off); (c) `SYN-001-capped-budget` (control; cap 20) | every failure-bundle counter equals the same run's trace meter (the probe read 202 for (a)); (c) equals `max_property_calls` = 20 | exact integers within one run (counts are within-platform, ADR 0007 D5, so the comparison is bundle against its own trace, never against a number from another machine). Each state has a nonzero meter, so an accidental 0 fails | test |
| T08.A13 | Identity after W1.3/W1.4 | with the fixes' new values replaced by the old, the identity document equals the registered `k05-identity.json` byte for byte; the old→new diff touches only the fields D2/D3 name | exact | test |
| T08.A14 | Typed-ends sweep: a revision reaching `eliminate_alias_rows`' rank error; a verifier whose own property call fails; U+FFFE/U+FDD0 in a document string | each public operation ends typed (`unsupported`, `invalid_request` or a typed failure); `internal_error` count 0; a path no public operation reaches is recorded with its reachability argument, not counted as a pass | exact | test |
| T08.A15 | T06 A89's case (THM-09 start 2 under `T06-revision-v2`) repeated 20 times on the aarch64 class, and once on `ref-x86-64` | every repetition ends with T06 A89's registered outcome — `CONVERGED`, `VERIFIED`, S3's worst ratio ≤ 0.1; refinement counts recorded. If any repetition misses it, a defect, escalated; if all meet it, the design lane amends A89 to the outcome with the count reported | registered: S3's allowances (T02 §6.4) and A89's 0.1 (T06 Amendment 4) | ci |
| T08.A16 | Every campaign record the RC job writes (ensemble, G16-b, bundle set) | carries `commit` (40 hex = `C`), `tree_clean: true`, the lock's sha256, the registered machine class | exact | test |
| T08.A17 | CLI `replay --rerun` on (a) a revision-built bundle, (b) a K05 bundle whose `run_id` is no registered case | (a) reruns the recorded route, `MATCH`, exit 0; (b) `NOT_RUN`, reason `rerun_unsupported(no_revision_document)`, nothing rerun, exit 1 | exact | test |
| T08.A18 | `src/process_runtime/application/bindings/descriptions/REVIEW.json` | for each of the 17 operations both reviews (`design-lane`, `human`) are `reviewed`, with `reviewed_by` and `reviewed_at` set, at the recorded hash, which equals the served text's | exact | test |
| T08.A19 | The lock lookup. States: (a) the source checkout at `C`; (b) the RC wheel installed (`--no-deps`, dependencies at the lock's versions) into a virtual environment inside a scratch directory that also holds an unrelated file named `requirements.lock`; (c) a `SYN-001-nominal` bundle written by (b)'s CLI, replayed by (b) and by (a) | (a) `RunManifest` `lock_sha256` = `ead4edf1…`; (b) `lock_sha256` = `""` — the stray file is not read; (c) both replays `inspected_archived_results`, verdict `NOT_RUN`, the reason naming the dependency set unknown (on both sides from (b); on the archive's side from (a)); never `MATCH`; no exception *(added 2026-10-01, Amendment R3 5)* | exact. (a) catches a fix that empties the hash everywhere; (b) the parent-directory walk; (c) a silent `MATCH` | ci |
| T08.A20 | `support_envelope.yaml` against the code | operations = the 20 of `OPERATIONS`; models = the 13 of `MODEL_BUILDERS` *(amended 2026-09-29, T08 build-first §E.4)*; policies = the offered list; unit spellings = ADR 0016's table; providers = {`syn001`}; components = {A, B, C} | exact set equality | test |
| T08.A21 | The harvest (§5.7) over P00–T07's manifests (§5.7; `HARVEST_PACKAGES`); T08's own manifest, written after `C`, is the next harvest's *(amended 2026-10-06, Amendment R8 2)* | every limitation and non-pass check classified exactly once (E/S/P/B), every pointer resolves, every text hash current | exact | test |
| T08.A22 | Every `unsupported` row | names a typed outcome and a test node that exists and passes at `C` | exact | test |
| T08.A23 | `docs/support-matrix.md` | regenerates byte for byte from the YAML | exact | test |
| T08.A24 | The alias rule in the verifier. States: P = 100 kPa, `j` = 99 and 100; P = 180 kPa, `j` = 19, 20, 129, 130 (pressure columns placed at those positions in a constructed declaration) | up, unsupported; up, down, down, unsupported (§5.4) | exact integers | test |
| T08.A30 | [A10] refresh: `scripts/p03_binary_inventory.py`, generalized, over every compiled distribution of the default install and the `server` extra at the lock's versions, on the x86-64 and aarch64 wheels | per object: path, sha256, `DT_NEEDED`, notice attribution; the METIS closure unreachable from every project path on both; every restrictive, non-LGPL GPL-family or unresolved object either already dispositioned by ADR 0006 D4 or listed as a new finding; zero undispositioned objects in a required closure | exact (the inventory must name ≥ the compiled distributions of the lock: casadi, numpy, scipy, and the server extra's compiled wheels, so an empty inventory fails) | ci |
| T08.A31 | Mode A hygiene | no file of a CasADi tree tracked by git (ADR 0006 D5.5); the RC wheel contains none; `LICENSE` and `NOTICE` in sdist and wheel; README's CasADi LGPL statement present | exact | test |
| T08.A32 | Data provenance | every ComponentRecord the RC ships has `rights` populated and `synthetic: true`; no third-party data in sdist or wheel; the envelope states that the reference-tool data and OpenIDAES-450 are not distributed | exact | test |
| T08.A33 | The recovery-edge inventory (§5.6) | the bijection holds; every `default`, `policy-only` or `library-only` row has a direct injected-failure test that passes at `C` and unchanged-physics evidence of a kind §5.6 admits; every `library-only` row's unreachability test passes *(amended 2026-10-01, review 2 Ruling 6)* | exact | test |
| T08.A34 | Every certificate the RC job emits | carries the [A08] regularity evidence of the final unregularized Jacobian and the [A09] shared-provider qualification on exactly the prefixed energy checks (T06 A33's rule); violations 0 | exact | ci |
| T08.A35 | The `SYN-001-nominal` bundle written by the CLI at tag `v0.0.0` (a worktree at `9a4391f`, its own lock) | the RC's `replay` returns a typed report (`inspected_archived_results` with `NOT_RUN`, or a typed refusal naming the schema version) and `inspect` renders it; no unhandled exception | exact (pattern) | test |
| T08.A40 | `requirements.lock` at `C` | sha256 `ead4edf1…`, equal to T07's `environment_lock_hash` | exact | generator |
| T08.A41 | `scripts/check.sh` at `C` | green on `ubuntu-latest` and `ubuntu-24.04-arm` (run id recorded) | exact | ci |
| T08.A42 | The identity document at `C` | equal on both architectures; equal to `k05-identity.json` except §6.2's substitutions; unchanged when the version string is `0.1.0` | exact | ci |
| T08.A43 | sdist and wheel built twice | contents limited to `process_runtime/**`, the runtime data the package needs, `LICENSE`, `NOTICE`, metadata; `Requires-Dist` pins equal `pyproject.toml`'s; the two builds' unpacked contents identical file by file (zip bytes reported) | exact | ci |
| T08.A44 | Clean install outside the tree, both architectures | installed distributions at the lock's versions; CasADi's installed files equal the audited per-file hashes (x86-64: P03; aarch64: T08.A30); `process-runtime` CLI solves `SYN-001-nominal` to `CONVERGED` and `VERIFIED` with the registered certificate's verdict and checks | exact for versions, hashes, verdict and check ids; state within `K04-numerical-policy-v1` (ADR 0007 D2: the registered floors, argued there) | ci |
| T08.A45 | The RC bundle set, written on CI x86-64 from the source checkout at `C`: (i) K05's registered SYN-001 runs — the 5 `variants` of `benchmarks/syn001/reference_values.yaml`, each by the CLI's `solve <case_id>`; (ii) T07 G8's revision bundles — `ELIGIBLE` of `tests/test_t07_w3a_revision_runs.py` under the `default` policy, as its `runs` fixture writes them | `N_b` = 5 + `len(ELIGIBLE)` enumerated at `C`, recorded per set (5 + 47 = 52 at the build lane's dev run, `69e8e03`); every bundle records `numerical_policy_id` = `T08-numerical-policy-v2` and `MATCH`es under it in `exact_replay` or `compatible_reproduction` on a fresh x86-64 runner and on aarch64; `inspected_archived_results` counts as a failure; near-threshold flags listed; on each of the two replay runners the controls of ADR 0025 A14 hold (C1 and C2 `MISMATCH` naming the mutated path, C3 `MATCH`, each re-sealed with `integrity_ok` true). T06 A34 is not in this set (it writes no bundle); it is carried by T08.A46 *(amended 2026-10-01, Amendment R3 1; amended 2026-10-02, Amendment R4)* | R0 exact; floats and classes `T08-numerical-policy-v2` (ADR 0025 §5); controls exact (verdict and path) | ci |
| T08.A46 | The registered ensemble (`T06-ens-v1`, starts `3a7bd49c…`, `T06-revision-v2`, classifier unchanged) at `C` | on each of `ref-x86-64` and `ci-aarch64`: S ≥ 418 of 440, 0 `F-CRASH`, 0 unexplained `F-OTHER-ROOT`; CP bound reported; run 1, run 2 and the holdout untouched; and T06 A34 at `C` in its registered form — on each class, the RC run's first start of every case and every retained failure replayed on the same class, `MATCH` on every field; no cross-class replay of ensemble starts is asserted (L07) *(amended 2026-10-01, Amendment R3 1)* | registered: S3's allowances (T02 §6.4), the 60 s ceiling, the §7.2 classes; the replay `K04-numerical-policy-v1` (T06 A34) | ci |
| T08.A47 | The corpus at `C` | T06 A02–A08, A16, A19, A20 green; no `VERIFIED` outside S3 in the RC ensemble records (worst ratio reported); STR-01…06 rejected with their registered reasons | registered (T06 §7, §8) | ci |
| T08.A48 | Our side of REF-01…REF-08 at `C` | T06 A47 and A50 (b) pass | registered: §9.4's tolerance / 10 (T06) | ci |
| T08.A49 | The agent surface at `C` | the served tool descriptions' digest equals `171dd768…` (R-133's carried surface), and serving `v17-c2`'s `validate.md` and `commit_change.md` in place of the served two reproduces `v17-c2`'s `6d13e13d…`; the operations' request/response schemas equal `c7bbc98`'s; G16-b 40/40 clean over Python, CLI, HTTP, MCP, scored against `t07_reference_t08.json` *(amended 2026-10-01, Amendment R3 2)* | exact | ci |
| T08.A50 | `scripts/v0_1_gate.py` | prints each gate's verdict and travelling L-ids from the ledger and `T08-verdicts.md`, reading clauses only from `Failing clauses` and L-ids only from `Travelling limitations` (Amendment R3 §R3.3; a clause id or envelope id in another cell, a missing or reordered column, or a gate row out of order is an error); exit 0 iff every gate is PASS or a FAIL whose clause ADR 0021 D3 lists with Frank's acceptance; exit ≠ 0 on any BLOCKED; never prints FAIL as PASS; checks that a tag candidate's `src/`, `schemas/`, `benchmarks/`, `requirements.lock`, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE` and `NOTICE` equal `C`'s, except one occurrence of the version value in each of `pyproject.toml` and `src/process_runtime/__init__.py` *(amended 2026-10-01, Amendment R3 3, 4)* | exact | test |
| T08.A60 | The dossier (§7.1) for the selected chemistry | all twelve items present with status and evidence | exact (presence) | verdict |
| T08.A61 | The selected PyMRM reactor (C1: the group's release `ammonia_synthesis_reactor` `main` @ `6089593464fc9bc2c0a0cb58e30ad5433ece6332`) in a pinned environment separate from the default install | (i) its regression reference — the group's pytest suite at that commit — run: 0 failed; every skip is one of the suite's own guards on an input the release does not ship, named by `file:line` and missing input, and counted *not reproduced*, never passed; at `6089593`: 72 collected, 69 passed, 3 skipped (`tests/test_cp_closure.py:57`, `tests/test_paper_pipeline.py:115`, `:127`); (ii) one non-isothermal 1D solve of a case of the group's own case table converges under the group's own acceptance checks (its convergence certificate and element balance), wall time recorded; (iii) PyMRM version recorded. No solved field is compared with a published result (M01's) *(amended 2026-10-01, Amendment R3 8)* | each test's own assertion tolerance as the group's suite states it (e.g. `rtol = 1e-12`, `tests/test_1d_models.py:41`); no tolerance of ours | ci |
| T08.A62 | The nonideal route in the independent tool (C1: PR in IDAES 2.13) at two states: a two-phase separator state and a single-phase reactor-inlet state | phase split and K-values returned and recorded; no comparison claimed | exact (presence) | ci |
| T08.A63 | Representability of the loop skeleton in the independent tool | T06-style table (unit, method, reaction form: Y/N with reason); the skeleton with an equilibrium or stoichiometric reactor built headless and solved once; versions recorded | exact (presence) | ci |
| T08.A64 | The rights table | every code and data item has source, licence or permission, scope, mode; no `unknown` | exact | verdict |
| T08.A65 | The dossier arithmetic | totals, ranking C1 > C2 > C3 > C4 > C5, tie-break, sensitivity rows as §7.4 states | exact | generator |
| T08.A70 | V14 clause (b) | judged by §4.4's criterion as resolved in T08 build-first §A4; PASS needs B20–B25 *(amended 2026-09-29, T08 build-first §E.3)* | exact (criterion) | verdict |
| T08.A71 | V13 clause (e) | judged by §4.3's reading; FAIL unless a test shows a solve opening from a compatible warm start, the trace recording its source, the opening checks applied, and an incompatible one rejected to the next source, on B40–B51 *(amended 2026-09-29, T08 build-first §E.3)* | exact (criterion) | verdict |

---

## 10. Reference generator and executable self-claims

`docs/derivations/scripts/t08_reference.py` (mpmath at 40 digits; exact integers and rationals; reads committed files as data, imports nothing from `process_runtime` or `benchmarks`) emits `benchmarks/t08/reference_values.yaml`. `--check` re-derives, and refuses to pass when any of these stops being true:

1. §3.1's manifests: one per package, commit prefix, status, tallies (T08.A01); §5.7's harvest size (18 manifests of P00–T07; 87 and 145 limitations).
2. §3.2's digests occur in the files that register them; the lock's bytes hash to `ead4edf1…` and equal T07's `environment_lock_hash`; the starts file's bytes and the registry's `ensemble.gate` are as quoted (T08.A40).
3. The Clopper–Pearson bounds of §4.10 and T07's 0.681 are roots of `I_p(x, n − x + 1) = 0.05` to 1e-30, and agree with the values earlier verdicts recorded.
4. §5.4's closed form agrees with the rule at `j_max` and `j_max + 1` for five pressures, is monotone to `j` = 400, has its worst case 74 at 125 kPa and its best 149 at the edges, and places NET-11's column at `j` = 24, shifted down.
5. The dossier's criteria are complete per candidate, scores are in {0, 1, 2}, the ranking and tie-break give C1 then C2, only an S1 of another candidate moves the top, and without C1 the top is C2 (T08.A65).
6. §9's table and the generator's catalogue agree in both directions, ids unique and sorted; §4.0 has one row per gate in order (T08.A00).

---

## 11. What this specification does not establish

- **No gate verdict.** It states criteria and expectations; the `verdict` agent judges at the RC. "Likely PASS" is a forecast.
- **No validation.** Nothing in v0.1 is empirically validated. The V19 dossier establishes *feasibility* of a real-chemistry journey; it validates nothing, and the group's published comparison of its kinetics with data is the group's evidence, cited, not re-judged here.
- **No new tolerance and no new numerical claim** about the solver. The two closed forms (Clopper–Pearson, the alias limit) restate registered rules.
- **Not the chemistry choice.** §7 ranks; Frank chooses (F3). The C1 facts come from a local repository without a licence; nothing here asserts rights on the group's behalf.
- **Not a legal reading** of any licence the [A10] refresh finds; new findings go to Frank as ADR 0006 Q1 did.
- **Not a review.** It does not set `reviewed` on any package, and it does not replace the design-lane review that D2, D3, the typed-ends sweep and the edge inventory need.
- **Not a promise that the RC job passes.** In particular the ensemble re-run at `C` (T08.A46) can fail after T07's changes; if it does, V20 is FAIL at the RC and a remedy is a new registration (R-087's rule), not a re-score.

---

## 12. Open questions with recommended defaults

| # | Question | Label | Recommended default |
| --- | --- | --- | --- |
| Q1 | Does a wheel installed outside the source tree work? `application/types.py:57–60` resolves `SCHEMA_DIR` from the source tree | **needs a fact** — T08.A44's first run | Assume not: W4.2 packages the runtime data (schemas and any YAML read at run time) into the package without changing content, `$id`s or any identity-bearing byte (T08.A42 checks) |
| Q2 | Which identity keys do the D2/D3 fixes move? | needs a fact — W1.3/W1.4 measurement | Only `t07`, by substitution (T08.A13); anything else stops the work |
| Q3 | Is `rank.py`'s `UnsupportedRankStructureError` reachable from a public operation? | needs a fact — the probe of W1.5 | Treat as reachable (map to a typed end) unless the probe shows otherwise |
| Q4 | Does A89's outcome hold on every aarch64 repetition? | needs a fact — T08.A15 | Yes; amend A89 to the outcome with the count reported |
| Q5 | Is the application's default policy content-equal to `T06-revision-v2` (except `policy_id`)? | needs a fact — a canonical diff | Assume not; the envelope's robustness line names `T06-revision-v2` only |
| Q6 | The C1 model's one-solve cost and a no-membrane configuration | needs a fact — T08.A61 | S7 = 1; if the 1D model cannot run without a membrane, M01 writes a plain packed bed in PyMRM from the same kinetics |
| Q7 | Can IDAES 2.13 represent a PR ammonia loop with a custom rate law? | needs a fact — T08.A63 | Yes (modular cubic EOS and a custom rate expression); if not, DWSIM, noting .NET 8's end of life |
| Q8 | Backfill G00–G06 verdicts in `docs/requirements.yaml` (null although v0.0.0 was tagged with all seven met)? | needs the user's preference (bookkeeping) | Yes, from `scripts/v0_0_gate.py`'s output, in W1.1 |
| Q9 | Pull any backlog item (B1–B3, M06 asks) into T08? | needs the user's preference | None; each is typed and conservative today |
| Q10 | Tag on the RC commit, or on a later version-bump commit? | needs the user's preference | A version-bump commit whose code trees and lock equal the RC's (T08.A50 checks), as v0.0.0 was |

---

## 13. FOR FRANK

- **F1 — V14's qualified-PTC clause.** Not met: T04's registered comparison has PTC and Newton converging from the same 18/18 starts, and the criterion is not re-read after the result. *Options:* (i) tag v0.1 with V14 FAIL on that clause under ADR 0021, PTC experimental, qualification owned by a v0.2 package with a holdup reactor; (ii) build a kinetic CSTR with holdup and run the preregistered PTC-R1 comparison in T08 (one to two weeks, outcome unknown); (iii) hold the tag. **Default: (i).**
- **F2 — V13's warm-start clause.** Blueprint §14.3 names warm starts; T03 recorded none in v0.1. *Options:* (i) tag with V13 FAIL on that clause, warm starts owned by M03; (ii) build them in T08 (architect design, one increment, review; about a week; touches replay identity); (iii) hold. Your "fewest limitations" points to (ii). **Default: (i).**
- **F3 — V19's chemistry.** Recommended: the **ammonia synthesis loop on the group's PyMRM model** (C1); runner-up the **methanol loop** (C2). Needed from you either way: the choice; whether the group has a model for another candidate; for C1, the licence of the reactor code as a dependency used by reference, which published rate law it implements and where it was compared with data, and the permitted use of the Rossetti et al. dataset and the property database. **Default: C1, subject to those statements; C2 if any of them is negative.**
- **F4 — Identity re-registration.** The D2/D3 fixes will move the `t07` identity key by substitution only (empty ids and a zero counter replaced by the true values), proven byte for byte. **Default: approve.**
- **F5 — V17 at the RC.** Carry V17 from `c7bbc98` if the agent-facing surface is unchanged (T08.A49); otherwise a new campaign (about USD 10 of subscription estimate, one hour). **Default: carry; ask again only if the surface changed.**
- **F6 — Release mechanics.** T08 stops at the RC and a draft CHANGELOG. Your steps: optional sign-off of T01–T08 in R-017's form, the `0.1.0` commit, the tag, and every publication decision (no PyPI, plan §2). **Default: as stated.**

---

## 14. Findings (recorded, not acted on here)

- **FD1.** Plan §5.1's V-rows are summaries of blueprint §14.3 and drop clauses: V13 omits "block statistics", "safeguarded" and **"warm starts"**; V11 omits "immutable". The verdict reads the blueprint (§1). The plan text is not changed; if Frank prefers the plan's narrower reading, that is an ADR against blueprint §14.3.
- **FD2.** `docs/requirements.yaml`: G00–G06 verdicts are `null` though v0.0.0 was tagged "all seven gates met"; V12–V17 `evidence` lists are empty or incomplete (Q8, T08.A02).
- **FD3.** `docs/support-matrix.md` (plan §1.2; blueprint §2.2, "each release publishes a support matrix") has never existed (§5).
- **FD4.** ADR 0006 Q4's default — hash-pinned `requirements.lock` — was never implemented, and implementing it now by editing the lock would change the lock hash and demote every registered bundle to `inspected_archived_results` (ADR 0007 D4). T08 enforces "the audited bytes are the installed bytes" in the clean-install job instead (T08.A44). Recommended as a register entry against Q4 (R-121).
- **FD5.** `SCHEMA_DIR` is resolved from the source tree (`application/types.py:57–60`); a wheel installed elsewhere probably cannot find the schemas (Q1).
- **FD6.** T04 §8.4 names PTC-R1's owner as "the first package that registers a reactor with holdup". v0.2's PyMRM reactor is an external steady model with no flowsheet holdup, so no planned package owns it; the owner is assigned at v0.2 planning (ADR 0021 D3).
- **FD7.** `docs/progress.md` says "No package is `reviewed`"; P00–K06 are `reviewed` with Frank's 2026-09-23 sign-off. Stale sentence.
- **FD8.** `docs/T08_STATE.md` lists "the project licence before any release artifact" as Frank's; closed 2026-09-23 (`LICENSE`, `NOTICE`).
- **FD9.** The OpenIDAES-450 copy measured in §7.3 lives in another session's scratchpad; re-acquire it into hash-referenced evidence (W3.1).
- **FD10.** T06 Q25's "from roughly 20 streams on" understates the pressure dependence; §5.4's closed form replaces it.

---

## 15. Build-lane work order

Phases run in order; items inside a phase are independent. Every item touching residuals, derivatives, phase logic, certificates or replay identity gets a design-lane `reviewer` pass before merge (marked **R**).

**Phase 1 — independent of Frank's answers (start now).**

| Item | What | Assertions |
| --- | --- | --- |
| W1.0 | Commit this spec, the generator and YAML, ADR 0021/0022 drafts; add a test running `t08_reference.py --check` | T08.A00, A01, A40, A65 |
| W1.1 | Ledger: V11–V20 evidence lists; G00–G06 backfill (Q8); `docs/T08_STATE.md` | T08.A02 |
| W1.2 | D1: report the revision's instance ids in structural messages and `implicated` | T08.A10 |
| W1.3 | D3: isolate the cause first (test the executor-meter hypothesis on the three states), then fix — **R** | T08.A12 |
| W1.4 | D2: carry plan/policy/revision ids through the region result view into bundles and certificates — **R** | T08.A11 |
| W1.5 | Typed-ends sweep (`rank.py` error, R4-O2, R4-O1) — **R** for the verifier path | T08.A14 |
| W1.6 | A89: 20 aarch64 repetitions plus one local; then the design lane amends T06 A89 | T08.A15 |
| W1.7 | Campaign records: commit, `tree_clean`, lock hash, machine class | T08.A16 |
| W1.8 | Identity substitution proof after W1.3/W1.4; hold for F4 | T08.A13 |

**Phase 2 — envelope and distribution.**

| Item | What | Assertions |
| --- | --- | --- |
| W2.1 | `support_envelope.yaml`, `scripts/t08_support_matrix.py --check`, `docs/support-matrix.md`; unsupported rows with typed-outcome nodes | T08.A20, A22, A23 |
| W2.2 | The harvest and its classification — **R** (the classification) | T08.A21 |
| W2.3 | The alias-rule threshold test | T08.A24 |
| W2.4 | Recovery-edge inventory and bijection — **R** | T08.A33 |
| W2.5 | [A10] refresh on both architectures, default install and server extra; mode A hygiene; data provenance | T08.A30–A32 |
| W2.6 | The v0.0.0 bundle probe (worktree at the tag) | T08.A35 |

**Phase 3 — V19 facts (parallel to phase 2; no Frank dependency until assembly).**

| Item | What | Assertions |
| --- | --- | --- |
| W3.1 | Re-acquire OpenIDAES-450 (release `openidaes450-demo-2026-09-26`, 220 433 394 bytes) under `evidence/T08/artifacts/` by hash; re-measure §7.3's facts for C2–C5 into a committed table | (supports T08.A60) |
| W3.2 | C1: run the group's regression test in a pinned environment; time the 1D model; test a no-membrane configuration (Q6) | T08.A61 |
| W3.3 | IDAES 2.13: PR flash at two ammonia loop states; the loop skeleton with an equilibrium reactor; representability table (Q7). For C2: rerun `blind_synthesized_methanol_recycle` under 2.13 and record the version difference | T08.A62, A63 |
| W3.4 | Draft `docs/v02-real-chemistry-dossier.md` (§7.1's twelve items, statuses, evidence); the design lane finalizes scores and ADR 0022 after Frank's F3 | T08.A60, A64 |

**Phase 4 — the release candidate (after phases 1–2 merge on `wp/T08`; after F1/F2 if either says build).**

| Item | What | Assertions |
| --- | --- | --- |
| W4.1 | Version `0.1.0rc1`; CHANGELOG draft per ADR 0021 D4 | — |
| W4.2 | Package the runtime data (Q1); sdist and wheel; content reproducibility | T08.A43 |
| W4.3 | CI: clean-install and bundle-set replay jobs on both architectures | T08.A44, A45 |
| W4.4 | The RC job (§8.2) at `C`: check, identity, ensemble (local `ref-x86-64` and CI `ci-aarch64`), corpus, references, agent surface, inventories, certificate audit | T08.A34, A41, A42, A46–A49 |
| W4.5 | `scripts/v0_1_gate.py` | T08.A50 |

**Phase 5 — judgement and close (design lane, then build lane).**

| Item | What |
| --- | --- |
| W5.1 | `verdict` judges V11–V20 at `C` against §4 → `docs/reviews/T08-verdicts.md` (T08.A03, A60, A64, A70, A71) |
| W5.2 | `reviewer` on everything marked **R** |
| W5.3 | `evidence/T08/<C>/manifest.json` (`requirements: [D04, A10, D17, D20]`; one check per `T08.Axx`; limitations: the E-rows and every FAIL clause); merge `wp/T08` |
| W5.4 | Hand to Frank: F1–F6 answered or at defaults, the RC, the draft CHANGELOG, the gate report |

---

## 16. Register entries (text; applied by the build lane when this spec and the ADRs are committed)

**R-117 — v0.1 is tagged only on a release candidate whose every gate has a verdict; a FAIL is released only by named clause with Frank's acceptance.** Date 2026-09-29. Decided by: design lane (proposed); the release rule's acceptance is Frank's. Normative text: ADR 0021 D1–D2; T08 spec §3.3, §8. *Decision:* a release candidate is the commit of §8.1; each gate is judged there (PASS/FAIL/BLOCKED); `BLOCKED` blocks the tag; a FAIL clause may be released only if ADR 0021 D3 lists it with Frank's acceptance, and then it is printed FAIL everywhere. *Rejected:* tagging on package-level passes without an RC re-run (earlier passes describe earlier commits); a "PASS with waiver" status (a reworded FAIL). *Watch for:* a gate report that prints a released FAIL as PASS; a tag whose code trees differ from the RC's.

**R-118 — V14's qualified-PTC clause is judged by T04 §8.1's criterion unchanged, plus selectability on a supported flowsheet; it is FAIL on existing evidence.** Date 2026-09-29. Normative: T08 spec §4.4; ADR 0021 D3. *Decision:* qualification needs T04 §8.1's criterion on a case registered before its PTC results, and a family selectable by a registered policy on a flowsheet inside the envelope. *Rejected:* reading blueprint §7.5 route (a) alone as sufficient after the comparison came out equal (a criterion changed after the result); qualifying on PTC-R1 run as a bare residual (not a capability any supported flowsheet can select); removing the clause from v0.1. *Watch for:* a later "route (a) suffices" argument without a new, pre-result registration.

**R-119 — V13 is judged by blueprint §14.3 bullet 3, including warm starts across runs; K02's warm-start cache does not satisfy it.** Date 2026-09-29. Normative: T08 spec §4.3; FD1. *Decision:* where a plan §5.1 row omits a clause of its §14.3 bullet, the blueprint clause counts; §14.3's "warm starts" are §7.4's compatible warm starts. *Rejected:* the plan's shorter text as the criterion (the plan summarises the blueprint and does not override it); K02's §6.4 property-level cache as the warm start (a different mechanism). *Watch for:* V13 closed by citing the property cache.

**R-120 — v0.2 real chemistry (pending Frank): recommended the ammonia synthesis loop on the group's PyMRM model; runner-up the methanol loop.** Date 2026-09-29. Normative: ADR 0022 (Proposed); T08 spec §7. *Decision (proposed):* the rubric of §7.2, preregistered before measurement; C1 first on S1/S5/S6 and a necessary nonideal route. *Rejected:* C2 as first (independent cases exist but reference neither kinetics nor the nonideal route; no group model); C3 (no native recycle; the IDAES case has no selectivity); C4, C5 (a nonideal route not clearly needed; little PyMRM value). *Watch for:* a selection made without H5's rights statements; the ranking recomputed with changed anchors rather than changed facts.

**R-121 — Release evidence is re-measured at the RC; T08 adds no tolerance; the lock is not edited in T08.** Date 2026-09-29. Normative: T08 spec §3.3, §8.1 (1), FD4. *Decision:* every gate is judged at the RC through the RC job; float comparisons reuse registered tolerances; `requirements.lock` stays `ead4edf1…`, and "the audited bytes are the installed bytes" (ADR 0006 Q4) is enforced by comparing installed CasADi files with the audited per-file hashes in the clean-install job. *Rejected:* citing T06's and T07's campaign passes without a re-run at the RC; adding hashes to the lock (changes the lock hash and demotes every registered bundle to `inspected_archived_results`). *Watch for:* a lock edit bundled into an unrelated change.

**R-122 — D1 blocks V20's invalid-structure clause; D2, D3, the typed-ends sweep, A89 and the record fields block the RC, not a gate verdict; M06's contract asks are v0.2 backlog behind ADR 0019 amendments.** Date 2026-09-29. Normative: T08 spec §6. *Decision:* as the table of §6.1; D2/D3 identity moves only by proven substitution with Frank's approval (F4). *Rejected:* classifying D2/D3 as V18/V20 failures (the registered assertions never reached these paths, and the verdicts on them stand); deferring D2/D3 to v0.2 (a release whose failure bundles carry empty replay identity breaks blueprint §8.2). *Watch for:* an identity key moved by more than the named fields.

---

## Amendment (T08 build-first spec Amendment 1, Stop 1) — 2026-09-29

**Author:** design lane (`specifier`). **Authority.** This amendment restates one clause of T08.A49 and of the V17 row of §2. Everything else stands.

- **T08.A49's G16-b clause** reads: "G16-b 40/40 clean over Python, CLI, HTTP and MCP, **scored against `docs/derivations/scripts/t07_reference_t08.json`** (T07 V17 spec Amendment T08-1)". The descriptions digest `6d13e13d…` and the request/response schemas of `c7bbc98` are unchanged as criteria.
- **Why.** Frank's F5 (2026-09-29) rules one more model in `list_models` and two more policies in `get_project` content-only, and keeps V17's carry. V17's T10-C3 had registered the offered set. Its oracle for reference runs from T08 on is the four-policy set `{T04-W12, T06-revision-v2, T08-ptc-v1, T08-warm-v1}`, while v17-c1 and v17-c2 keep their references and are not re-scored.
- **The carried verdict's wording** is registered in the build-first spec, Amendment 1 §Am1.3.

---

## Amendment R2 (2026-10-01, transcribed by the build lane from `docs/reviews/T08-review-2.md`, design-lane rulings)

**Author:** design lane (`reviewer`), `docs/reviews/T08-review-2.md`; transcribed verbatim into this spec by the build lane (brief `docs/briefs/T08-review-2-fixes-b.md`). The rulings below are binding; this section records each ruling's amended text, marked with its ruling number. The body markers `*(amended 2026-10-01, review 2 Ruling n)*` point back here. Do not rewrite history: amendment text plus markers only.

**Ruling 1 (U05 — a rule-5 defect, fixed in code).** §5.3, row U05, replaced:
> | U05 | `validate(task="optimization")`; any study — optimization, parametric sensitivities, sweeps, parameter estimation | `validate` with `task: optimization` ends with ADR 0019's error `unsupported`, detail `task_unsupported(optimization)`, before any analysis; no v0.1 path returns `READY_FOR_OPTIMIZATION` (the value stays in the frozen enum, unused); the other studies have no operation among the twenty of `OPERATIONS`; no optimality claim anywhere |

The envelope YAML gets the same U05 row, with the new node `tests/test_t08_w2_unsupported.py::test_u05_validate_for_optimization_is_unsupported` and `doc:docs/blueprint-v3.1.md` as evidence. The YAML header's U05 build-lane note is deleted.

**Ruling 2 (§5.2 Components — amend the spec to match the code).** §5.2, the Components row, replaced:
> | Components | exactly the three pseudo-components {A, B, C}, declared in any of the six orders and mapped onto the provider's order at binding (T06 A59–A61, R-076); a proper subset, an extra, an unknown or a repeated component is refused `components_unsupported` (U01) — a mixture without one of them is declared with all three and that component's flows exactly zero (ADR 0001 D3); `synthetic: true`; no real identity | provider component set; `canonical_components` |

U01's capability cell becomes: "real components, or a component set that is not exactly a permutation of {A, B, C}". The envelope's `components.statement` gains the zero-flow sentence, and the YAML header's components note is deleted.

**Ruling 3 (L10 — confirmed with one correction).** §5.5 and the YAML, L10 replaced:
> | L10 | The initializer chain is partial (blueprint §7.4, K03 §10.1): GUESS-role specifications are not bound by the revision binder (such revisions run on `legacy_eo`), the SYN-001 tear path has its registered initializer only, and the one fallback between initializer sources is `T08-warm-v1`'s compatible warm start → traversal (opt-in; L-WS-1, L-WS-2) | T03 spec §13; K03 §10.1; T07 S-G; ADR 0024 |

**Ruling 4 (Harvest rules — accepted, tightened; L22 split; new rows added).** §5.7, the sentence from "classified exactly once" up to "The check fails", replaced:
> classified exactly once: **E** (user-facing; points to one or more L-rows of §5.5 or U-rows of §5.3), **S** (superseded or closed; points to the closing test node or passing manifest check, or to a document only when the closing fact is that document's existence and it did not exist when the item was written — a status inside a document that already existed is closed by a test asserting it), **P** (provenance or process note needing no closure; stays in its manifest), **B** (an open defect or follow-up not closed in v0.1; points to a backlog id of §6.3). A compound item takes the first applicable class in the order E, B, S, P; its pointers name a row for every user-facing part, and an E item may also carry the backlog ids of its B parts. A defect handed on is never P: it is S when closed, E when a user can reach it, else B.

A21's code then accepts B ids among an E item's pointers. Rows L18–L35 are accepted. L22 replaced, and L36–L39 added (spec §5.5 and the YAML):
> | L22 | Scope of the solver evidence: tear selection is greedy (minimality not claimed); behaviour finer than the registered basin margins and trajectories below a residual of 1e-6 are not established; several stated rules are exercised only by synthetic fixtures | T02 spec §12; T03 spec §13 |
> | L36 | No performance claim at size: costs are within-platform measurements on registered cases of at most tens of variables; compiles per plan run and the regularity screen's cost at size are not measured | T02 spec §12; T03 spec §13; T06 spec §15 |
> | L37 | `verify` is not safe to run concurrently in threads of one process: the regularity screen seeds and restores numpy's global generator around `onenormest` (T06 §8.1, R-069), so concurrent calls can move the estimate, `rcond₁`, the bound and a regularity verdict near its threshold; jobs run in separate processes and are unaffected | T06 spec §16 (Q27) |
> | L38 | Structural analysis is generic: validation's STR checks and `inspect_structure` report structural rank and the DM/BTF partition only; numerical rank, conditioning and feasibility are judged by the certificate's regularity screen at a converged state (blueprint D05) | T01 spec |
> | L39 | The structural-zero release (recovery edge E5) leaves no trace record: a trace does not show that it ran | `docs/recovery-edges.yaml` E5 |

**Ruling 6 (Kinds of evidence — all three count, each under a condition).** §5.6, the sentence "Each row: … `enabled` ∈ {default, policy-only, absent}." replaced:
> Each row: trigger, precondition, maximum count, the injected failure and its test node, the evidence that `model_version`, `constants_sha256` and the specifications are unchanged, and `enabled` ∈ {default, policy-only, library-only, absent} (`library-only`: no application-offered policy and no `MODEL_BUILDERS` unit reaches the edge, pinned by a test that fails when one does; such a row meets every clause an enabled row meets). Evidence is one of: **(i) `identity_compared`** — a test compares the edge's instance with the failed or target one in `model_version`, `constants_sha256` and specifications (T04 §5.4), or, for an edge acting inside one call on a caller-owned problem, shows every evaluation before and after the edge made on the same problem object with equal pinned values; **(ii) `verified_certificate`** — a test in which the edge demonstrably fires (its label or provenance asserted) ends `VERIFIED` by `verify_revision`/`verify_bound` against the bound revision; it shows the reported state is a root of the unchanged problem, not that every intermediate instance was unchanged; **(iii) `guard`** — the edge's path passes an identity guard before the new instance is used, and a test injects a change of each field the row claims (`model_version` and `constants_sha256`; specification values enter through `constants_sha256`) and sees it refused. A cross-binder fallback is held to the problem, not to `model_version`: its guard is `legacy_admission`'s C0–C5 (T07 ruling round 7).

§9, the T08.A33 row's criterion replaced: "the bijection holds; every `default`, `policy-only` or `library-only` row has a direct injected-failure test that passes at `C` and unchanged-physics evidence of a kind §5.6 admits; every `library-only` row's unreachability test passes".

**Ruling 9 (E5 without a label — acceptable for v0.1; recorded as L39; the label backlogged).** §6.3, appended:
> B10 handed-on follow-ups, unreachable or harmless in v0.1: a `CONVERGED` result without `x_final` yields a schema-refused certificate (T03 review §8; refuse the input, or a nullable `regularity` by ADR); K02 `TPFlash.evaluate` does not apply R-007 to a declared inlet phase (T05 §20 F7); `CheckPolicy.sha256` covers the tolerance table only, not §7's thresholds and the required-check list (K04-F9 F4; a K04 revision, an identity change); T05b re-review N-W5 (augment's recursion) and N-W6 (the release acts only at `α_max = 0`). B11 a trace record for the structural-zero release, recovery edge E5 (an identity change if the record enters R0).

**Ruling 11 (CLI `replay --rerun` — a rule-5 defect, fixed before the RC; reverses T07 D-Q6 for the CLI).** New assertion, §9:
> | T08.A17 | CLI `replay --rerun` on (a) a revision-built bundle, (b) a K05 bundle whose `run_id` is no registered case | (a) reruns the recorded route, `MATCH`, exit 0; (b) `NOT_RUN`, reason `rerun_unsupported(no_revision_document)`, nothing rerun, exit 1 | exact | test |

Register entry (`R-131` here): "CLI `replay --rerun` follows `reproduce_bundle`; the fallback to SYN-001-nominal is removed. Rejected: keeping it (T07 design note §12.3, §17 D-Q6), because it compares an unknown or revision-built run with another problem's rerun. Decided by design lane, T08 review 2, 2026-10-01."

**Ruling 12 (Inventory location — `docs/recovery-edges.yaml` stands; no ADR).** §5.6, appended to the first paragraph: "The inventory is `docs/recovery-edges.yaml`: it spells policy literals that the T05b/T06 literal guards forbid in registered cases, fixtures and references, which it is not."

**Ruling 13 (T07 L3 — the design-lane text review blocks the RC; it is not a limitation).** New assertion, §9:
> | T08.A18 | `src/process_runtime/application/bindings/descriptions/REVIEW.json` | for each of the 17 operations both reviews (`design-lane`, `human`) are `reviewed`, with `reviewed_by` and `reviewed_at` set, at the recorded hash, which equals the served text's | exact | test |

The node is `tests/test_t08_w2_description_reviews.py::test_every_description_is_reviewed_by_both_lanes`; it stays red until the review is recorded (no xfail). Harvest T07 `limitations[2]` and `[3]` are S → that node. §8.1 item 2 replaced: "**RC blockers closed.** D1–D3, the typed-ends sweep, A89, the record fields (§6.1) — T08.A10–A16; review 2's rule-5 defects — U05 (T08.A22's U05 node) and the CLI rerun (T08.A17); the design-lane review of the MCP tool descriptions (T08.A18)."

---

## Amendment R3 (2026-10-01) — eight rulings before the release candidate

**Author:** design lane (`specifier`); brief `docs/briefs/T08-amendment-R3.md` with its addendum. **Authority.** Where this specification was wrong or silent it is amended here and in place (markers *(amended 2026-10-01, Amendment R3 n)*); where another authority document needed a change, it is appended there, dated: T06 spec **Amendment T08-1** (A89), ADR 0006 **Amendment 2** (D4 on aarch64), ADR 0021 **proposed revision 2** (D2.4), ADR 0022 **proposed revision 1** (pin, property method). No tolerance, identity key, registered result, schema or frozen interface changes. Every number quoted below is re-derived by `t08_reference.py --check` (§R3.10).

### R3 1 — T08.A45's bundle set; T06 A34 carried by T08.A46

*Decision.* The engineer's readings are confirmed: "K05's registered SYN-001 runs" are the 5 `variants` of `benchmarks/syn001/reference_values.yaml`, each written by the CLI's `solve <case_id>`; "T07 G8's revision bundles" are `ELIGIBLE` of `tests/test_t07_w3a_revision_runs.py` under `default` (47 at `69e8e03`; the RC enumerates, it does not hard-code). **T06 A34 leaves A45**: it is a record replay on the same machine class that writes no bundle, and per-start outcomes are not promised across architectures (L07; ADR 0007 F1), so naming it in a cross-architecture bundle replay was this document's error. It is carried to `C` **in its registered form by T08.A46**: on each class, the RC run's first start of every case and every retained failure, replayed on the same class, `MATCH` on every field.
*Rejected.* Bundles for T06's starts with a cross-architecture `MATCH` required (asserts what L07 disclaims); the same "reported, not asserted" (satisfiable by anything); leaving A45 failing (a document defect is amended, not carried — rule 6).
*Text.* §9 T08.A45, T08.A46; §8.2 step 6.

### R3 2 — T08.A49's descriptions digest

*Decision.* A49 requires `171dd768…`, the surface R-133 carries (Frank), as R-134 did for B50, and in addition the decomposition — serving `v17-c2`'s `validate.md` and `commit_change.md` in place of the served two reproduces `6d13e13d…` — so the carry stays bound to exactly N1 and N2. `6d13e13d…` stays registered as `v17-c2`'s (§3.2, historical). Amendment 1's "the descriptions digest `6d13e13d…` … unchanged as criteria" is superseded for the digest; its G16-b clause is carried into A49's row.
*Rejected.* A49 left on `6d13e13d…` (fails at `C` on a change Frank accepted); read as met without amendment (a criterion re-read after the result — R-134's rejected alternative).
*Text.* §3.2 (new row); §4.7; §9 T08.A49.

### R3 3 — the verdict document's table (§R3.3)

*Decision.* `docs/reviews/T08-verdicts.md` carries exactly one table with a `Verdict` header, in this form:

```
**Release candidate:** `<C, 40 hex>`   **Judged:** <YYYY-MM-DD>   **By:** design lane (`verdict`)

| Gate | Verdict | Failing clauses | Travelling limitations | Basis |
| --- | --- | --- | --- | --- |
| V11 | PASS | — | L.., L.. | §V11; <evidence at C> |
| V14 | FAIL | V14 (b) | L01, … | §V14; <evidence at C> |
| V19 | BLOCKED | V19 (i): Frank's F3; V19 (v): <rights statement> | — | §V19; … |
```

1. Exactly these five headers, in this order; ten rows `V11` … `V20` in order; gate ids bare (no bold).
2. `Verdict` is a bare `PASS`, `FAIL` or `BLOCKED`, equal to `docs/requirements.yaml`'s.
3. `Failing clauses`: FAIL — the failing clauses, comma-separated, as `Vnn (x)` with §4's clause labels (`V13 (e)`, `V14 (b)`, `V19 (iii)`), at least one; BLOCKED — each blocked clause as `Vnn (x): <missing input>`, separated by `;`; PASS — `—`.
4. `Travelling limitations`: the envelope `limitations` ids that travel with the gate (`L01`, `L-WS-1`), comma-separated, each present in `benchmarks/t08/support_envelope.yaml`; `—` if none. U-ids are not listed here.
5. `Basis`: the pointer to the gate's section and the evidence at `C`; it contains no `Vnn (x)` and no envelope id.
6. Below the table, one section per gate (`## V11` …): each clause judged met / not met / blocked with its evidence at `C`, and what the verdict does not establish. Tables there have no `Verdict` header and no first cell that is a bare gate id.

`scripts/v0_1_gate.py` reads clauses only from `Failing clauses` and ids only from `Travelling limitations`; a clause or envelope id in another cell, a PASS with a failing-clause entry, a missing or reordered column, a gate out of order, or an unknown id is an error, exit ≠ 0 (T08.A50's test covers each).
*Rejected.* Reading ids "anywhere in the row" (the script today): a FAIL whose basis cites a met clause would be refused as unaccepted, and an id cited as not applicable would travel. Free prose: not checkable (rule 4).
*Text.* §9 T08.A03, T08.A50.

### R3 4 — ADR 0021 D2.4's tree check

*Decision.* Confirmed with one correction. `pyproject.toml` is in the check (its pins are what the wheel requires), and in it and in `src/process_runtime/__init__.py` the only allowed difference is one occurrence of the version value (`0.1.0rc1` → the tag's). **Corrected:** every other input of the sdist or wheel is in the check, with no difference allowed — `MANIFEST.in`, `README.md` (the wheel's long description, and T08.A31's LGPL statement), `LICENSE`, `NOTICE`. The list: `src/`, `schemas/`, `benchmarks/`, `requirements.lock`, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`, `NOTICE`. Everything else may differ — `CHANGELOG.md`, `docs/`, `evidence/`, `tests/` (including the two `tests/fixtures/schemas/application_results/project_summary/` fixtures carrying the version in `server.package_version`). A change to a checked path after `C` makes a new RC (`0.1.0rc2`), not a tag.
*Rejected.* The three trees and the lock only (a changed notice, README or packaging rule would reach the released artifacts untested by T08.A31/A43); comparing rebuilt artifacts byte for byte (needs a build at the tag and a version-normalizing diff of names and METADATA, for no more coverage than the source list).
*Text.* ADR 0021 proposed revision 2; §8.3; §9 T08.A50.

### R3 5 — an installed wheel has no `requirements.lock`

*Decision.* **A registered limitation for v0.1 (L41); no lock hash in the wheel; ADR 0007 is not amended.** Today's behaviour is ADR 0007 D4's: an empty lock hash on either side is `inspected_archived_results` / `NOT_RUN`, with the reason named. **A defect found while ruling (rule 5):** `run/manifest.py` `_repository_lock` walks every parent directory of the module, so an installed package beneath any directory holding a file named `requirements.lock` (a user's project; some Python tools use that name for their own lock) records that file's hash as the project's lock — a false dependency-set identity, and an `exact_replay` between two such installs. The lookup is confined to the source checkout the module lives in (the directory holding `pyproject.toml` with `[project].name = "process-runtime"` and `src/process_runtime/`); anywhere else `lock_sha256` is `""`. T08.A19 (new, RC job step 4) pins the three states. Backlog B12 holds the verified alternative.
*Rejected.* Shipping `requirements.lock` in the wheel and recording its hash: the hash would attest an environment nothing checked (`pyproject.toml` pins five direct dependencies; the transitive ones float), so two installs with different transitive versions would replay `exact_replay` — a false `MATCH` path; making it honest needs a per-distribution check at manifest time, an identity-bearing change at the RC (B12, an ADR 0007 amendment). Embedding only the hash: the same objection.
*Text.* §5.5 L41; §6.3 B12; §8.1 item 4; §8.2 step 4; §9 T08.A19.

### R3 6 — T06 A89

*Decision.* T08.A15 is met, 21 of 21: 20 on `ci-aarch64` (CI 36868221999, `3b4a613`) and 1 on `ref-x86-64` (`8128e17`), each `CONVERGED`, `VERIFIED`, `SUCCESS`, S3's worst ratio `2.166302692785393e-05`, one refinement accepted at `S3.T` (`benchmarks/t08/a89/`). §12 Q4's default applies: **A89 is amended to its outcome** — `CONVERGED`, `VERIFIED`, `SUCCESS`, S3's worst ratio ≤ 0.1 — asserted on every machine class and every run; the refinement clause (exactly one fired at `S3.T` or `S4.T`, kept, chord `ρ_max` > 1 before) is asserted only on the registered `ref-x86-64` CPU model and recorded, not asserted, elsewhere. The one recorded miss (CI 36440983702 at `d1c4ee5`, aarch64: zero refinements fired, the outcome clauses passing) is exactly what the amendment admits: ADR 0018 fires on a floating-point decision (the chord ratio against 1), which blueprint §8.3 and ADR 0007 F1 exclude from any cross-platform promise, and CI runners of one label vary.
*Rejected.* The exact count on every class (a flaky assertion of a promise the project does not make; §6.1 requires a deterministic CI); no count anywhere (the reference host would no longer catch a refinement path that silently stopped firing).
*Text.* T06 spec Amendment T08-1.

### R3 7 — ADR 0006 D4 on aarch64

*Decision.* ADR 0006 Amendment 2 adds the aarch64 wheel's two unresolved CasADi objects (`libgfortran-8de1544a.so.5.0.0`, 5 413 232 bytes; `libgomp-7eb2fb8b.so.1.0.0`, 1 194 968 bytes) to D4 with their x86-64 counterparts' defaults; records that D4's `libquadmath`, `libmvec` and `libspral.a` are absent from the aarch64 wheel and its three adaptor/IPC objects present; and states that Amendment 1 (R-135) covers numpy's and scipy's aarch64 `libgfortran` copies, whose declared licence is the one Frank ruled on. No disposition, mode or default changes; modes A and C are unaffected (neither object is loaded or in a required closure; T08.A30 aarch64 PASS).
*Rejected.* Dispositioning the two by analogy as GPL-3.0-with-GCC-exception (D4's rule: a term is read from a shipped notice or recorded unresolved; CasADi's copies ship none); leaving them only in the A30 record (mode B reads ADR 0006, which says the aarch64 wheel is unaudited).
*Text.* ADR 0006 Amendment 2.

### R3 8 — V19: H4, T08.A61, the pin, H2

**(a) H4.** *Decision.* For C1, "the selected method" is **Peng–Robinson with H₂, N₂, Ar and CH₄ declared vapour-only** (the liquid is NH₃ alone; IDAES's `HC_PR` convention). IDAES 2.13 represents the skeleton with it (`c1-idaes.json`: both flash states and the loop skeleton `optimal`; separator K_NH₃ 0.0615), so **H4 is `met`**. M01's provider and its reference use the same convention, so v0.2's comparison is like for like; dissolved light gases are a v0.2 limitation the dossier states (the purge is the inerts' only exit; NH₃ product purity and dissolved-gas losses are not represented; their effect on the inlet-temperature decision is not measured). Cubic root selection per phase stays an M01 derivation item; trivial-solution avoidance for a multicomponent liquid is not needed in v0.2. ADR 0022 D4 is revised accordingly. H4's text is unchanged — the method is the dossier's item 6, which must state the limitation — so no criterion moves after a result. *Rejected.* Full PR VLE with every component in both phases: no acquired tool represents it (IDAES ends on the trivial solution or unbounded), so H4 would stay `needs_fact` and M01 would take on trivial-solution avoidance with no independent reference to check it against.

**(b, c) T08.A61.** *Decision.* A61's "own regression reference" is the group's pytest suite at the pinned commit, and "the group's regression tolerance" is each test's own. **69 passed, 0 failed, 3 skipped by the suite's own guards on inputs the release does not ship meets A61**, with the three counted *not reproduced*. A published 4TU result need not be re-run for A61: its use awaits Frank's rights statement (dossier item 8) while the deposit is in curation, and a solved-case comparison with published results is validation evidence M01 owns, not selection feasibility. H1 is `met` on this reading (`c1-reactor.json`). *Rejected.* Requiring the 4TU comparison now (V19 would wait on data whose use is not yet permitted, for evidence §7.2 does not ask of a selection); counting a skip as a pass.

**(d) The pin.** *Decision.* `main` @ `6089593464fc9bc2c0a0cb58e30ad5433ece6332`, the commit measured. Tag `v1.1.0` is `d78fbfb`, which differs in `CITATION.cff`, `README.md` and `src/reactor/archive.py` and was not run; the Zenodo concept DOI is cited for attribution. *Rejected.* `d78fbfb` (evidence is about its own commit, R-121; if M01 prefers the tag, it re-runs A61 there — about 20 s).

**(e) H2 and dossier item 5.** *Decision.* **H2 reads `met`**: Rossetti et al. 2006 is a published rate law with parameters, compared with experimental data (Gargiulo et al. 2025 §3.1; the release's own validation), whichever K_NH₃ transcription is right. **Item 5 reads `met` only with the discrepancy named in the item**, and item 11 lists the K_NH₃ enthalpy term among what M01 pins, read from Rossetti et al. 2006 itself; `c1-provenance.json` keeps `discrepancy` until Frank's check is recorded. *Rejected.* H2 `needs_frank` (the open question is which number the group's code should carry — a pin — not whether a validated law exists); item 5 `met` without naming the discrepancy (a silent pass).

*Text.* §7.2 H4 (marker); §9 T08.A61; ADR 0022 proposed revision 1.

### R3 9 — What this amendment does not establish

- No gate verdict. V19 stays `BLOCKED` while F3 and H5's statements are outstanding.
- No validation of the C1 reactor or property route: A61 reproduces the group's tests and one solve; A62/A63 compare nothing.
- Not that the vapour-only convention is adequate for v0.2's design decision (unmeasured; stated as a limitation).
- Not any licence term of the aarch64 toolchain-runtime objects (they stay unresolved) and not that the aarch64 wheel's notice set equals the x86-64 one beyond T08.A30's per-object attribution.
- Not that an installed package reproduces anything (L41).
- No new tolerance.

### R3 10 — Generator

`t08_reference.py --check` additionally re-derives, from committed records: the RC surface digest in its registering test (R3 2); the 5 K05 variants (R3 1); both A89 records — case, commit, repetition counts, every repetition's outcome, verdict, class, refinement and ratio `2.166302692785393e-05` (R3 6); the two aarch64 objects' bytes, hashes, category, closure and load flags, the three x86-64 D4 objects absent on aarch64, the aarch64 unresolved set, and Amendment 1's aarch64 copies (R3 7); C1's pin, tag and tag-to-pin files, suite counts and skip guards, PyMRM version, the converged solve with its element balance, the two H4 representability rows, the vapour-only states, the full-VLE trivial solutions and the open K_NH₃ discrepancy (R3 8); T08.A19 in the catalogue. It emits them under `amendment_r3`.

### R3 11 — Build-lane work

| Item | What | Assertions |
| --- | --- | --- |
| R3-W1 | `scripts/t08_rc.py`: drop the open T06 A34 set from `bundles-write`/`bundles-replay`, record per-set counts; `rc-ensemble`: the same-class replay of the RC run's first starts and retained failures on each class | T08.A45, A46 |
| R3-W2 | `scripts/v0_1_gate.py` and its test: column-wise reading (§R3.3), the corrected tree list | T08.A50 |
| R3-W3 | `run/manifest.py` lock lookup confined to the checkout — **R** (replay identity); the clean-install job adds T08.A19's three states; envelope L41, matrix regenerated | T08.A19, A20–A23 |
| R3-W4 | T06 A89's test: outcome clauses on every host; the refinement clause only when the host's CPU model equals `ref-x86-64`'s registered one, else recorded (`record_property`) | T06 A89 (T08-1) |
| R3-W5 | The [A10] inventory script attributes the two aarch64 objects to `ADR 0006 Amendment 2` | T08.A30 |
| R3-W6 | The dossier: item 6's method and its limitation, H1/H2/H4 `met`, item 5's named discrepancy, item 11's K_NH₃ pin, A61's reading, the pin | T08.A60, A61 |
| R3-W7 | Apply R-136…R-143 below and the register index (next free R-144) | — |

### R3 12 — Register entries (text)

**R-136 — T08.A45 is the bundle set the RC writes (K05's 5 variants, T07 G8's `ELIGIBLE`); T06 A34 is carried to the RC in its registered same-class form by T08.A46.** Date 2026-10-01. Decided by: design lane (T08 spec Amendment R3 1). *Rejected:* cross-architecture `MATCH` of ensemble starts (L07 disclaims it); leaving A45 failing on a document defect. *Watch for:* a cross-class replay of ensemble starts asserted anywhere; G8's count hard-coded instead of enumerated.

**R-137 — T08.A49's descriptions digest is R-133's carried surface `171dd768…`, bound to the N1/N2 decomposition.** Date 2026-10-01. Decided by: design lane, consistent with Frank's R-133 and R-134 (Amendment R3 2). *Rejected:* A49 on `6d13e13d…`; reading it met without amendment. *Watch for:* a further description change carried under R-133.

**R-138 — The verdict document has one five-column verdict table; the gate script reads clauses and limitation ids by column only.** Date 2026-10-01. Decided by: design lane (Amendment R3 3). *Rejected:* ids read anywhere in a row; free prose. *Watch for:* a clause id or envelope id in `Basis`; a bold gate id.

**R-139 — ADR 0021 D2.4 compares every input of the sdist and wheel — `src/`, `schemas/`, `benchmarks/`, `requirements.lock`, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`, `NOTICE` — allowing only the version value in `pyproject.toml` and `__init__.py`.** Date 2026-10-01. Decided by: design lane (Amendment R3 4; ADR 0021 proposed revision 2). *Rejected:* three trees and the lock only; rebuilt-artifact comparison. *Watch for:* a README or notice edit between the RC and the tag without a new RC.

**R-140 — v0.1 ships no lock in the wheel; an installed package's bundles replay `NOT_RUN` (L41); the lock lookup is confined to the source checkout.** Date 2026-10-01. Decided by: design lane (Amendment R3 5). *Rejected:* packaging the lock or its hash (attests an unchecked environment and opens a false `exact_replay`). *Watch for:* `lock_sha256` read from any file outside the checkout; B12 implemented without an ADR 0007 amendment.

**R-141 — T06 A89 asserts its outcome on every class and its refinement count only on the `ref-x86-64` CPU model.** Date 2026-10-01. Decided by: design lane (Amendment R3 6; T06 spec Amendment T08-1) on T08.A15's 21 of 21. *Rejected:* the exact count everywhere; no count anywhere. *Watch for:* another adaptive floating-point decision asserted exactly across classes.

**R-142 — ADR 0006 D4 lists the aarch64 wheel's two unresolved toolchain-runtime objects; Amendment 1 covers numpy's and scipy's aarch64 `libgfortran`.** Date 2026-10-01. Decided by: design lane (Amendment R3 7; ADR 0006 Amendment 2). *Rejected:* dispositioning CasADi's copies by analogy. *Watch for:* a mode-B artifact for aarch64 without these items resolved.

**R-143 — V19 for C1: H4 met with PR and the light gases vapour-only; A61 is the group's suite (69 passed, 3 data-guarded skips not reproduced) and one converged solve; the pin is `6089593`; H2 met while the K_NH₃ transcription stays an M01 pin item.** Date 2026-10-01. Decided by: design lane (Amendment R3 8; ADR 0022 proposed revision 1, pending Frank's F3). *Rejected:* full PR VLE as H4's method; the 4TU comparison inside A61; the tag commit `d78fbfb` as the pin; H2 `needs_frank`. *Watch for:* dissolved-gas effects claimed in v0.2 without a full-VLE route; item 5 reported without its discrepancy.

## Amendment R4 (2026-10-02) — T08.A45 under ADR 0025

### R4 1 — The comparison policy of T08.A45

*Decision.* T08.A45 is judged under `T08-numerical-policy-v2` (ADR 0025, Proposed). Every bundle of the set must record that id; a bundle recording another id fails the row (`a45.every_bundle_records_the_current_policy`). A `K04-numerical-policy-v1` bundle is compared under v1 (R-147) and an unknown id is refused (`inspected_archived_results` / `NOT_RUN`); neither satisfies the row. *(amended 2026-10-02, Amendment R5 2)* The row gains ADR 0025 A14's positive controls, so that "every bundle `MATCH`" cannot be met by a comparator that compares nothing. The row as amended is in §9.

*Why.* At `C` = `814e151` the aarch64 replay gave 31 `MATCH` / 21 `MISMATCH` under the v1 comparator (`docs/t08-rc-record.md` F2). That comparator compares, against ADR 0007's own rules: a float-derived `certificate_id` and `level_constants_sha256` for value; certificate limitation values and solution-state variables with a zero floor; messages that embed floats byte for byte; and LU pivot-path diagnostics as if they were reproducible (`docs/reviews/T08-verdicts.md` G1). ADR 0025 decides each rule from ADR 0007's principles and its noise models, not from the 21.

*The `814e151` result stands.* A45 is FAIL at `814e151`. Its bundles record `K04-numerical-policy-v1`, and they are not re-judged under v2.

*Rejected.*
- Editing `K04-numerical-policy-v1` in place.
- A cross-architecture-only policy (ADR 0007 D2.5).
- Re-reading the row as met at `814e151`.

*Text.* §9 T08.A45.

### R4 2 — What this amendment does not establish

That A45 passes at the next `C`; that is for the RC job and the verdict lane. Nothing else in this specification changes.

### R4 3 — Register entry

R-146 (text in ADR 0025 §15).

## Amendment R5 (2026-10-02) — identity values and A45's refusal text after R-147 and R-148

**Author:** design lane (`reviewer`), `docs/reviews/T08-review-3.md` §C Rulings 1 and 2; transcribed verbatim into this spec by the build lane (brief `docs/briefs/T08-review-3-fixes.md`). The body markers *(amended 2026-10-02, Amendment R5 n)* and *(added 2026-10-02, Amendment R5 n)* point back here.

### R5 1 — §3.2's identity values

*Decision.* ADR 0025 D1.2 makes every run manifest and certificate name `T08-numerical-policy-v2`, and
`RunManifest.structural_sha256` covers that field. The K05 identity values therefore move by that substitution
only (Frank, 2026-10-02, R-148). In §3.2, the rows "K05 identity document minus `t07`" and "Structural hash" are
replaced, and one row is added:

| Value | SHA-256 | Registered in |
| --- | --- | --- |
| K05 identity document minus `t07` (R-148) | `29246e053ad126034c1aeef0f396ffe1d9f4dffcf5128f226720280bd1b656e5` | `tests/test_t07_identity.py` (`K05_MINUS_T07_SHA256_V2`) |
| Structural hash (R-148) | `e62a59a6b3634afd8f43eae399129a2d64bafb6e8ba90ad5fe0c9c1a9c5ad238` | `tests/test_t07_identity.py` (`STRUCTURAL_SHA256_V2`) |
| `t07` key (§6.2's D1–D3, then R-148) | `a96f17eda025168ea184584bd8f0fd2bed6d940ecf8356a6b7ee6f9663348e4b` | `tests/test_t08_w1_identity_substitution.py` (`T07_KEY_SHA256_V2`) |

The values T07 registered stay the registered values *with v1 recorded*: minus `t07` `9a7b4e6d…`, structural
`915c97e8…`, `t07` key `422aa7a5…` and whole document `7f32b143…`. `tests/t08_v2_substitution.py::record_v1`
reproduces them byte for byte, and those tests are part of these rows' evidence.

The sentence under §3.2's table becomes: "The complete identity document to reproduce is the committed
`evidence/T07/5f3d3ea…/artifacts/k05-identity.json`, except the keys re-registered under §6.2 (including R-148).
At `C` the whole document is `28dd8bf7f15f7750b0c646f609037dc84afd6f465b0bc3b5fac459c14299f0a5`; with v1 recorded
it is `7f32b1431226d11fd7b5b89f467525ca72648d6d7596df82d5d64b27d1ddf7e5`."

§6.2 gains a final paragraph: "ADR 0025 D1.2's recording switch is a second substitution of this kind (R-148). The
substituted field is `numerical_policy_id`, v2 for v1, at its two sources, together with the hashes that cover it.
The proof is `tests/t08_v2_substitution.py`." T08.A42 and §8.2 step 2 keep the words "except §6.2's
substitutions", which now include R-148.

*Rejected.* Keeping the v1 values as what `C` must reproduce: A42 would fail at every `C` that records v2.
Deleting them: that loses the substitution's anchor.

*Generator* (review 3, Ruling 1). `t08_reference.py --check` finds each new value in its new `registered_in` source; requires the minus-`t07` and `t07`-key values to equal `scripts/t08_rc.py`'s `K05_MINUS_T07_SHA256` and `T07_KEY_SHA256`, read from the script; finds each moved entry's `registered_v1` value in its source (`9a7b4e6d…` in `tests/test_t07_identity.py`, `915c97e8…` in `evidence/T07/5f3d3ea…/manifest.json`, `422aa7a5…` in `tests/test_t08_w1_identity_substitution.py`); and finds both values of each pair in `docs/decision-register.md` under `## R-148`.

### R5 2 — A45's refusal text

In R4 1, "a bundle recording another id is refused at replay (`inspected_archived_results` / `NOT_RUN`, ADR 0025
D1.3), and that counts as a failure" becomes: "a bundle recording another id fails the row
(`a45.every_bundle_records_the_current_policy`). A `K04-numerical-policy-v1` bundle is compared under v1 (R-147)
and an unknown id is refused (`inspected_archived_results` / `NOT_RUN`); neither satisfies the row." §9's A45 row
is unchanged.

## Amendment R6 (2026-10-02) — identity values after R-149

**Author:** transcribed by the build lane, mirroring R5 1 for R-149 (Frank 2026-10-02). No new decision: R5 1's form, applied to the values R-149 approved. The body markers *(amended 2026-10-02, Amendment R6 1)* and *(added 2026-10-02, Amendment R6 1)* point back here.

### R6 1 — §3.2's identity values

*Decision.* The import package is renamed `process_runtime` → `openflowsheet` (R-149). The SYN-001 provider's
`implementation_sha256` hashes its own source, which names the package, and enters `model_version`; the K05 identity
values therefore move by that substitution only (Frank, 2026-10-02, R-149). In §3.2, the three identity rows are
replaced:

| Value | SHA-256 | Registered in |
| --- | --- | --- |
| K05 identity document minus `t07` (R-149) | `24af004ab5718e559bd3d40716d66e21d9b19043a26777a39a0da84c6fbdcb8e` | `tests/test_t07_identity.py` (`K05_MINUS_T07_SHA256_R149`) |
| Structural hash (R-149) | `ed6d11f3beb78c6f1debc481c6e525ce3ccb120bd30cdfd07e470f728e082e90` | `tests/test_t07_identity.py` (`STRUCTURAL_SHA256_R149`) |
| `t07` key (§6.2's D1–D3, then R-148, then R-149) | `887a2e622676dbfaff0a8ebfc309414f0e74150ace8327887b4a9ec15e498a38` | `tests/test_t08_w1_identity_substitution.py` (`T07_KEY_SHA256_R149`) |

R5 1's values stay the values reproduced *before the rename*: minus `t07` `29246e05…`, structural `e62a59a6…`,
`t07` key `a96f17ed…` and whole document `28dd8bf7…`. `tests/t08_rename_substitution.py::record_process_runtime`
reproduces them byte for byte, and with `record_v1` as well T07's v1 values; those tests are part of these rows'
evidence.

The sentence under §3.2's table becomes: "The complete identity document to reproduce is the committed
`evidence/T07/5f3d3ea…/artifacts/k05-identity.json`, except the keys re-registered under §6.2 (including R-148 and
R-149). At `C` the whole document is `174977ccf18d0dbf57fa429cb2522921cc98d0d5b693382ec973c86fd714c225`; with the
pre-rename self-hashes it is R-148's `28dd8bf7f15f7750b0c646f609037dc84afd6f465b0bc3b5fac459c14299f0a5`, and with v1
recorded as well it is `7f32b1431226d11fd7b5b89f467525ca72648d6d7596df82d5d64b27d1ddf7e5`."

§6.2 gains a final paragraph: "The rename of the import package to `openflowsheet` is a third (R-149). The
substituted values are the two self-hashes whose modules name the package — the SYN-001 provider's
`implementation_sha256` and the T06 generator's `generator_sha256` — together with the hashes that cover them. The
proof is `tests/t08_rename_substitution.py`." T08.A42 and §8.2 step 2 keep the words "except §6.2's substitutions",
which now include R-149.

*Rejected.* As R5 1: keeping R-148's values as what `C` must reproduce (A42 would fail at every `C` after the
rename); deleting them (that loses the substitution's anchor).

*Generator.* As R5 1 (b)–(d), for R-149: `t08_reference.py --check` finds each new value in its new `registered_in`
source and requires the minus-`t07` and `t07`-key values to equal `scripts/t08_rc.py`'s constants; finds each moved
entry's pre-rename value (R5 1's) in its source (`29246e05…` and `e62a59a6…` in `tests/test_t07_identity.py`,
`a96f17ed…` in `tests/test_t08_w1_identity_substitution.py`); finds both values of each R-149 pair in
`docs/decision-register.md` under `## R-149`; and keeps R5 1 (c)–(d) on the pre-rename value and the v1 value,
under `## R-148`.

## Amendment R7 (2026-10-02) — after the verdicts at `C` = `67c66d9`

**Author:** transcribed by the build lane from the verdict findings of `docs/reviews/T08-verdicts.md` (`f22f3cf`), brief `docs/briefs/T08-close.md`. The body markers *(amended 2026-10-02, Amendment R7 n)* point back here.

### R7 1 — where the RC records are committed (§8.1 item 4)

*Transcribed by the build lane from verdict finding G6.* §8.1 item 4 put the RC job's small text records under `benchmarks/t08/rc/`. `benchmarks/` is one of the trees ADR 0021 D2.4 (R3 4) requires the tag commit to share with `C`, and the records are written after `C`, so committing them there would make every tag candidate differ from its `C`. §8.1 item 4 therefore reads "small text under `evidence/T08/<C>/rc/`, large files under `evidence/T08/<C>/artifacts/` by hash": the per-commit evidence directory, next to the manifest, outside the D2.4 trees. Every record of 1 MB or less that the RC record cites by sha256 is committed there at its path relative to `evidence/T08/<C>/artifacts/rc/`, and `evidence/T08/<C>/rc/records.json` lists every cited record with its sha256, size and whether it is committed; a larger record stays git-ignored under `artifacts/` and is referenced by its hash only (at `67c66d9`: the two ensemble run files, 2.4 MB each). `tests/test_t08_rc_records.py` requires every sha256 of the RC record's per-step table to be listed there and every committed file to hash to it. Nothing else in §8.1 changes; no record is regenerated.

### R7 2 — V19 clause (i) (§4.9)

*Transcribed by the build lane from verdict finding G4.* §4.9 (i) read "Frank's selection is recorded (ADR 0022 accepted)", while ADR 0022's own Status line, written with it, makes the ADR Accepted *when* Frank records the choice there *and* V19 is `PASS`. Read literally the pair is circular: V19 could pass only after the ADR was Accepted, and the ADR could be Accepted only after V19 passed. Clause (i) therefore reads "Frank's selection recorded in ADR 0022" — the verdict's reading 1 at `C` = `67c66d9` (`docs/reviews/T08-verdicts.md`, `f22f3cf`) and the order Frank set in R-145: the choice recorded, then V19 `PASS`, then Accepted. ADR 0022 is marked Accepted with that `PASS` (2026-10-02), pointing at the dossier's "Frank's statements, 2026-10-02". Nothing else in §4.9 changes.

## Amendment R8 (2026-10-06) — after the close-out review

**Author:** transcribed by the build lane from the design lane's close-out review `docs/reviews/T08-closeout-review.md`
(2026-10-06), which confirmed Amendments R6 1, R7 1, R7 2 and the close-out decisions Q1 (B24) and Q2 (A21) with no
must-fix item. v0.1.0 and v0.1.1 are unaffected. The body marker *(amended 2026-10-06, Amendment R8 n)* points back here.

### R8 1 — the RC records over 1 MB (review finding F1)

*Decision.* R7 1's 1 MB limit left the two per-start ensemble records behind V20 (d)'s S = 434 —
`ensemble/rc-ref-x86-64.json` (2 366 257 bytes) and `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.json`
(2 365 831 bytes) — only on the RC host and in expiring CI artifacts. They are committed gzip-compressed beside their
paths (`<path>.gz`, `gzip -9 -n`, about 120 KB each); `rc/records.json` is unchanged (its sha256 and size are of the
uncompressed bytes, and `committed: false` keeps saying the raw file is not in the tree). `tests/test_t08_rc_records.py`
decompresses each and checks size and sha256. *Rejected:* a durable store named by hash outside the repository (the
private archive or a release asset) — it splits the evidence from the record that cites it.

### R8 2 — T08.A21's row text (review finding F2, erratum)

§9's A21 row said "over every `evidence/**/manifest.json`", which the code (`1305f87`) and §5.7's count ("today 18
manifests") do not do; it now reads "over P00–T07's manifests (§5.7; `HARVEST_PACKAGES`); T08's own manifest, written
after `C`, is the next harvest's". No denominator moved: `C`'s tree has 18 manifests, none under `evidence/T08/`.

### R8 3 — R6's authorship and lettering (review notes N1, N2)

R6 1's edits to §3.2, `reference_values.yaml` and `t08_reference.py` are design-lane edits under R-149's "Watch for";
`docs/reviews/T08-closeout-review.md` item 1 is their design-lane confirmation. R6's "As R5 1 (b)–(d)" refers to the
lettering of Ruling 1 in `docs/reviews/T08-review-3.md`.

### R8 4 — T08's own limitations hand on to v0.2 (review finding F3)

T08's manifest (`evidence/T08/67c66d9…/manifest.json`: 58 limitations, 16 without an L/U row id, and the non-pass
A70 and B23) is classified by no harvest. It is an input to v0.2's support-envelope harvest (`docs/V02_STATE.md`).
