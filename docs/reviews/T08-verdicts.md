# T08 — verdicts on the release gates V11–V20

**Release candidate:** `67c66d98587f23bd7dfe8da28a8facccc92da21e`   **Judged:** 2026-10-02   **By:** design lane (`verdict`)

| Gate | Verdict | Failing clauses | Travelling limitations | Basis |
| --- | --- | --- | --- | --- |
| V11 | PASS | — | L38 | §4.1; at C: K06, T01, T06 and T07 nodes green in CI 37008077757 on both architectures; T08.A35 and T08.A10 nodes green |
| V12 | PASS | — | L02, L26, L27, L28, L29, L30, L-CSTR-1, L-CSTR-2, L-CSTR-3 | §4.2; at C: K01/K02, T05 A01–A21, T05b and build-first B10–B19 nodes green in CI 37008077757 on both architectures; coupled cases SYN-001, T05 C1–C3, PTC-R1 |
| V13 | PASS | — | L10, L22, L23, L24, L36, L38, L-WS-1, L-WS-2 | §4.3 and T08.A71; at C: T01, T02 and K03 nodes green; B40–B49 nodes green in CI 37008077757 and 19 of 19 here; B50 as amended by build-first Amendments 3 and 4 (R-134, R-144): T08.A49 on three hosts, the exact content test green, the two T07 reference files byte-unchanged since c7bbc98 |
| V14 | FAIL | V14 (b) | L01, L08, L20, L21 | §4.4; T08-verdict-V14b.md (PTC-R1: the saddle clause fails on both registered platforms), accepted by Frank on 2026-09-29 in ADR 0021 D3; homotopy and edges: T04 and T02 nodes and T08.A33 green at C |
| V15 | PASS | — | L02, L14, L19, L20, L33 | §4.5; at C: T02, T03 and T06 (ADV-05, THM-09) nodes green on both architectures; the certificate schema fixes both claims to NOT_ASSESSED and all 49 RC bundle certificates carry it |
| V16 | PASS | — | L16, L17, L18, L32 | §4.6; T06 verdict 1 stands (8 of 8 by both tools, 16/16 AGREE); T08.A48 passes at C on ref-x86-64, ci-x86-64 and ci-aarch64 |
| V17 | PASS | — | L11, L12, L13 | §4.7 as amended by R3 2; carried from c7bbc98 under R-133; T08.A49 4/4 at C on ref-x86-64, ci-x86-64 and ci-aarch64 |
| V18 | PASS | — | L03, L05, L06, L15, L19, L25, L34, L37, L39, L40, L41 | §4.8; at C: T08.A30 PASS on three hosts with no undispositioned object in a required closure; T08.A31–A33 nodes green; T08.A34 0 violations on every audited set |
| V19 | PASS | — | — | §4.9 as amended by R3 8; ADR 0022 with Frank's choice recorded (R-145); the dossier with Frank's statements of 2026-10-02; the benchmarks/t08/v19 records, byte-identical at C and at 89dd3ca |
| V20 | PASS | — | L04, L07, L09, L31, L32, L38 | §4.10; at C: T08.A46 S = 434 of 440 on ref-x86-64 and on ci-aarch64, no crash, no other-root, same-class replay 28/28; T08.A47's ten T06 assertions green on three hosts, nothing verified outside S3; T08.A10 node green |

## Read this first

**What changed since the verdicts at `814e151`.** Two rows moved:

- **V13 moved from FAIL to PASS.** At `814e151` it failed only on B50's content clause, because `get_project` serves
  the package version (finding G2). Frank amended B50 on 2026-10-01 to exclude `server.package_version` (build-first
  Amendment 4, R-144). The exact test that the previous verdict asked for now exists
  (`tests/test_t08_b50_surface_content.py`) and is green.
- **V19 moved from BLOCKED to PASS.** Frank's selection is recorded (R-145), and his rights statements of 2026-10-02
  settle the `needs_frank` items. The `k_ij` row now states its source, licence, scope and mode. Two readings this
  needed are set out under V19, with the alternatives rejected there.

V14 (b) is still FAIL, and it is the clause Frank accepted in ADR 0021 D3. The other seven rows are re-confirmed at
the new `C`.

**T08.A45 is MET at `C` under its amended row (R4).** The x86-64 replay is 52 of 52 `exact_replay` `MATCH`, all
bitwise. The aarch64 replay is 52 of 52 `compatible_reproduction` `MATCH`: 18 bitwise and 34 within
`T08-numerical-policy-v2`. Every bundle records v2, and the A14 controls hold on both runners. **A45's FAIL at
`814e151` stands** (R4 1): those bundles recorded v1 and were judged under v1. A45 still feeds no V-gate; it feeds
§8.1 item 4.

**`C` against §8.1.**

- Items 1–4 are met on the record. Steps 1–10 of the RC job all pass, and T08.A19, A30, A34 and A41–A49 all pass.
- Item 4's records clause is met only in substance. The small text records were not committed under
  `benchmarks/t08/rc/` as the clause says, and committing them there after `C` would break D2.4 (finding G6).
- Item 5 is not met yet. There is no `evidence/T08/<C>/manifest.json` with `status: tested`. Under D2 and D1, no tag
  may be proposed until that manifest exists, the ledger carries these verdict words, and D2.4 holds at the tag
  commit.

**Standing.** This is an agent verdict. It is numerical and procedural only, and it is not scientific review or a
process-model sign-off. It sets no `reviewed`. T01–T08 are `tested`. Human sign-off (R-017's form) is Frank's and is
not claimed here.

**Criteria, read before the evidence and not re-read after it:**

- **Release spec.** T08 release spec §3.2, §3.3, §4 (V11–V20), §7.1–§7.2, §8 and §9, with Amendments R2–R6 and the
  in-place markers.
- **V13 (e).** Build-first spec §B5 and rows B40–B51, with §Am1.C, Amendment 3 (R-134) and Amendment 4 (R-144).
- **V14 (b).** Build-first spec §A4 and B20–B25.
- **ADR 0021.** D1–D5, proposed revisions 1 and 2, and the D3 row of 2026-09-29.
- **T08.A45.** ADR 0025 §4–§5, with Frank's answer to Q4 (R-147) and its review-3 correction.
- **V19 (i).** ADR 0022: its status line, its revision 1 and "Frank's choice recorded" (R-145).
- **Blueprint §14.3.** The blueprint's SHA-256 `66f574b0…` matches the plan header; I recomputed it here.

## Evidence and provenance

| Evidence | Produced by, where | Independent expectation | Class |
| --- | --- | --- | --- |
| RC record `docs/t08-rc-record.md` (`51cd5ff`) | build lane: the local `ref-x86-64` worktree at `C`; CI dispatch run 37008077757 at `C` (success); push run 37008077056 (success) | none (the record reports and judges nothing) | record |
| The record files it hashes, under `evidence/T08/<C>/artifacts/rc/` (git-ignored) | as above | **recomputed here: 43 of 43 sha256 equal the record**, including the A45 replay records, both ensemble records and the three A30 summaries | provenance |
| T08.A41: `check (ubuntu-latest)` 6809 passed, 11 skipped; `check (ubuntu-24.04-arm)` 6812 passed, 8 skipped | CI 37008077757 | the tests' own expectations | tested |
| The local `check.sh` figure (6817 passed, 3 skipped) | a session's report, not re-run, with no record file | none | **pins nothing**; the verdicts use CI |
| Skipped nodes | not listed: the CI logs print totals only | the skip counts equal `814e151`'s (11 and 8). The diff `814e151..C` adds no skip, `skipif`, `importorskip` or `xfail` site under `tests/`, so the static scan of the previous verdict stands: every skip is a platform, reference-host or pending-artifact guard, and none guards a V11–V20 clause node | inference, stated as such |
| B40–B49 (`test_t08_w4_warm_starts.py`, 19), B50 content (`test_t08_b50_surface_content.py`, 3), the V19 record tests (`test_t08_w3_v19_records.py`, 12) | **run here** on ref-x86-64 at `89dd3ca`, whose `src/`, `tests/`, `scripts/`, `schemas/` and `benchmarks/` equal `C`'s (`git diff` empty): 34 passed, none skipped | B50: the fixture is checked against the 15 `list_models` and 24 `get_project` results that `v17-c2`'s agents recorded at `c7bbc98` | tested (node level, one host) |
| T08.A42–A44, A19, A46–A49, A30, A34 records | as listed in the RC record; every `t08-rc-v1` record carries `commit = C`, `tree_clean = true` and the lock `ead4edf1…` (T08.A16) | registered values: identity per §3.2 as amended by R6 (minus `t07` `24af004a…`, `t07` key `887a2e62…`, structural `ed6d11f3…`, whole `174977cc…`); digests `171dd768…` and `6d13e13d…`; `S_min = 418`; CP 0.97326390… at S = 434 (generator-checked) | ci, tested |
| T08.A45 replay records | CI `bundle-replay` on both architectures, from the x86-64 `bundle-set` archive | the archived bundles under `T08-numerical-policy-v2` (ADR 0025 §5); the A14 controls are mutations whose expected outcome is fixed by the ADR | ci; judged below |
| Earlier verdicts | `T08-verdict-V13e.md` (`a6165b0`), `T08-verdict-V14b.md` (`b11d7b3`), `T06-verdicts.md`, `T07-verdicts.md` | as stated in each | verdicts (agent) |
| V19 records | `docs/v02-real-chemistry-dossier.md` at `89dd3ca`; `benchmarks/t08/v19/` (identical at `C` and `89dd3ca`) | the group's own suite and acceptance checks (A61); presence only (A62, A63) | feasibility; nothing is compared |
| Frank's statements (R-144, R-145, R-147–R-149, V19 items) | recorded by the build lane from Frank's answers in session (`docs/T08_DECISIONS.md`) | none: they are the authority's decisions, and this verdict relies on their record | decisions |

## T08.A45 at `C`: MET (as amended by R4, R5 2)

**The criterion** is the A45 row as amended:

- every bundle records `T08-numerical-policy-v2`;
- every bundle `MATCH`es under that policy, in `exact_replay` or `compatible_reproduction`, on a fresh x86-64 runner
  and on aarch64;
- `inspected_archived_results` counts as a failure;
- near-threshold flags are listed;
- on each replay runner, ADR 0025 A14's controls hold: C1 and C2 `MISMATCH` naming the mutated path, C3 `MATCH`,
  each re-sealed with `integrity_ok` true.

| Half | Result at `C` | Judgement |
| --- | --- | --- |
| write (CI x86-64, `bundle-set`) | 52 bundles, equal to the enumeration (k05 5, g8 47); every entry exit 0; all 52 manifests and all 49 certificates record v2 (checked here) | met |
| fresh x86-64 replay | 52 `exact_replay`, `MATCH`, `bitwise_floats` true; near-threshold none; C1 `MISMATCH` on `solution-state.json<root>.variables.heater.Q` (moved 1.01e-2 W, 10 × the `heat_rate` τ 1.01e-3); C2 `MISMATCH` on `verification_status`; C3 `MATCH`; all `integrity_ok` | met |
| aarch64 replay | 52 `compatible_reproduction`, `MATCH`: 18 bitwise, 34 within v2; near-threshold none; C1, C2 and C3 as on x86-64 | met |

**Provenance of the standard.**

- **When v2 was adopted.** v2 was adopted after A45 failed at `814e151`, and its classes were decided with the 21
  mismatches known. ADR 0025 §3 states that its rules were fixed from earlier decisions (ADR 0007 D1/D2.2 and
  Context 3, ADR 0010 D7.2, ADR 0018 D2) before they were applied to the 21.
- **Review.** Review 3 found the comparator sound and the v1 path bit-identical, checked by a 5000-case differential
  against `814e151`'s code.
- **What the integrity claim rests on.** The ADR's own statement of order, and the reviewer's check that each class
  traces to an earlier rule. No measurement can establish it.
- **What the rules give up.**
  - The pivot-path diagnostics are now recorded and not compared (D4). C3 is that deliberate blind spot.
  - A digest-form `certificate_id` is compared for shape.
- **What v2 still catches.** A state variable outside its `τ_kind`, a verdict flip, a template change and any R0
  leaf, as C1 and C2 show on both runners.

## V11 — PASS

| Clause | Judgement | Evidence at `C` |
| --- | --- | --- |
| (a) semantic diff | met | T07 `diff_revisions` / `semantic_diff` nodes, green in CI on both architectures |
| (b) immutable drafts | met | K06's content-addressed revisions, draft against ready, optimistic conflict and idempotent commit, green |
| (c) task-specific validation | met | T01 STR-01…06 and R-022's DRAFT/INVALID nodes; T08.A10 (STR-03 names the revision's own instance, with the renamed control); the U05 node (`validate(task="optimization")` is a typed `unsupported`); all green. K06's `unsupported` structural check is superseded by T01 A09 |
| (d) units, component and reference checks | met | T06 A43, A55–A57, A67–A74 (DIM-01, COMP-03, ADR 0016) and THM-05, green |
| (e) a real migration fixture | met | T08.A35: `tests/test_t08_w2_v000_probe.py`, on the committed bundle written at tag `v0.0.0` (`9a4391f`), with no skip site. Today's `replay` returns a typed `inspected_archived_results` / `NOT_RUN` (its lock is not this lock, ADR 0007 D4; under R-147 a known policy is compared, so the refusal is the lock's), and `inspect` renders it |

**Does not establish.**

- That a v0.0.0 bundle can be replayed. No old bundle migrates forward.
- Node-level CI pass lists, which were not recorded.

## V12 — PASS

Thirteen models (`MODEL_BUILDERS`; envelope `unit_models`). There is no committed definition-of-done matrix per
model, so the matrix below is reconstructed from the manifests and the test names. It is unchanged since `814e151`:
the rename and ADR 0025 touch no model's equations. Every node is green in CI at `C` on both architectures.

| Models | Contract | Limiting / failure | Balance | Derivative | Coupled case |
| --- | --- | --- | --- | --- | --- |
| pump, valve, PH flash, conversion reactor, component separator, heat exchanger (T05) | T05 A01, A03 | T05 A06–A12, A14–A16 (Z, F and S cases per model) | T05 A06, A13, A21 | T05 A04, A05 | T05 C1–C3 (A17–A19, A21) |
| feed, sink, adiabatic mixer, TP heater (cooler = negative duty), TP flash, splitter (P01/K02) | the six P01 manifests; T05 A02's ADR 0008 M1–M5 | K02 mixer domain and admissibility, two-phase heater outlet, flash trivial root, dormant streams, splitter at r = 0 | K02 balances and duties; `energy_balance.U-SPLIT` in C3 | K01 SYN-001 conformance against the 20-digit reference; K02 heater and flash blocks | the registered SYN-001 variants |
| kinetic CSTR | B10 | B16, B17 | B11; `material_balance.U-CSTR.*` | B12, B15 | PTC-R1 and B19 |

No model has a definition-of-done item marked `unsupported`. The feed and sink items are degenerate: they have no
balance rows of their own.

**Does not establish.**

- That this matrix was registered. It is this verdict's reading.
- Any model's accuracy against real data.

## V13 — PASS

| Clause | Judgement | Evidence at `C` |
| --- | --- | --- |
| (a) DM/SCC/BTF, block statistics, canonical tie-breaks | met | T01 nodes, green |
| (b) safeguarded recycle and coupled EO, with EO/tear agreement | met | T02 A13–A15, A32, A34, green |
| (c) scales before iteration, fixed within an attempt | met | K03 and T02 nodes, green |
| (d) model initialization, every candidate checked | met | Each §7.4 source has a test or a recorded absence, as at `814e151`. User guess: the A02 family (T04 A11, K04-F9 X04). Compatible warm start: B40–B49. Local initializers and upstream propagation: K03 `SYN-001-tear-init-v2`, the traversal, T05 causal evaluators, B18. Physical nominals and the tear-path guess chain: recorded absent (`K03.initializer_chain`) |
| (e) compatible warm starts | **met** | **B40–B49:** nodes green in CI at `C`, and 19/19 here on `C`'s code. **B50, as amended by Amendments 3 and 4:** see the table below |

**B50's clauses at `C`:**

| Clause | Judgement | Evidence |
| --- | --- | --- |
| descriptions digest `171dd768…`, with the N1/N2 decomposition | met | T08.A49 on three hosts |
| request/response schemas unchanged since `c7bbc98` | met | T08.A49 on three hosts |
| content differences from `c7bbc98`, excluding `server.package_version`, are exactly `syn001.kinetic_cstr` and `T08-ptc-v1`, `T08-warm-v1` | met | `test_t08_b50_surface_content.py`, 3/3, against a `c7bbc98` fixture cross-checked against `v17-c2`'s recorded results |
| G16-b 40/40 | met | T08.A49 |
| `t07_reference.json` and `t07_reference_c2.json` byte-unchanged | met | `git diff c7bbc98 C` empty |

B51 and T08.A71 are therefore met. A71's four elements are B41's opening and source, B41's checks, and B43's
rejection to the next source.

**Why this is not a criterion re-read after the result.** The previous verdict found B50 failing only on the package
version. It named the remedy before any re-judgement: a recorded amendment plus an exact test. Frank made the
amendment (R-144, rejecting the unamended re-reading in its own text), and the test was written afterwards. Its
fixture was made by `c7bbc98`'s own code and is checked against agent transcripts recorded at `c7bbc98`, so the
expectation is independent of today's build.

**Does not establish.**

- **Content beyond a fresh project.** "Exactly" is established on a fresh project, plus the server members across
  `v17-c2`'s 24 recorded `get_project` calls. Members that depend on a project's revisions are not compared.
- **Re-derivation of the fixture.** The fixture's generator can no longer re-derive it (finding G7). The committed
  fixture is unchanged since `a28fde3`, and its transcript cross-check runs.
- **An application path for the Anderson recycle.** The safeguarded Anderson recycle and edges E1 and E2 are
  `library-only`: clause (b) is a tested library capability, not an application path.
- **A request-named warm-start source.** Warm starts are opt-in and automatic only (L-WS-2).

## V14 — FAIL on V14 (b), accepted

| Clause | Judgement | Evidence |
| --- | --- | --- |
| (a) one typed homotopy | met | T04 A02–A12 nodes, green at `C` |
| (b) one PTC family qualified by §7.5 with tested SER | **not met** | `T08-verdict-V14b.md` on `C_res` = `b11d7b3`: on PTC-R1, (b1)'s saddle clause fails, with PTC ending `MID` from 149 of 441 starts on both `ref-x86-64` and `ci-aarch64` (B23). FAIL as registered (R-118). There is no new preregistration and no new result at `C` |
| (c) three tested recovery edges with budgets, rollback and unchanged target semantics | met | E1 and E2 (`library-only`), E3a (`default`) and E3b, each with a direct injected-failure test and §5.6 evidence; T08.A33's bijection node green at `C` |

Frank accepted the FAIL in ADR 0021 D3 (2026-09-29, "One the PTC: 1 and 3"). It is printed FAIL, never "met with
limitations".

**Does not establish.** Anything about PTC beyond PTC-R1, its SER settings and its synthetic CSTR. That E1 and E2 are
reachable from the application in v0.1.

## V15 — PASS

| Clause | Judgement | Evidence at `C` |
| --- | --- | --- |
| (a) phase disappearance and reappearance, frozen attempts, restart | met | T03 A00–A26 nodes, green |
| (b) cross-unit specification promotion to EO, no nested SM | met | T02 nodes (the capability error when a region unit lacks EO derivatives); U11 and U12 typed |
| (c) a multiple-root example with honest branch reporting | met | T03 root fingerprint and branch provenance; T06 ADV-05 (A15) and THM-09's census (A31), green |
| no uniqueness or dynamic-stability statement | met | `solution-certificate.schema.json` fixes `root_fingerprint.claims.uniqueness` and `.dynamic_stability` to `const NOT_ASSESSED`. All 49 certificates of the RC bundle set at `C` carry both as `NOT_ASSESSED` (counted here) |

**Does not establish.** Root completeness. Behaviour finer than the registered basin margins.

## V16 — PASS

- T06 verdict 1 stands: 8 of 8 comparisons by both tools, 16/16 `AGREE`, and the positive controls `DISAGREE`.
- T08.A48 passes at `C` on three hosts (step 7, 12/12; 165 nodes locally, none failed, missing or skipped).
- The tool side was not re-run, as §4.6 provides.

**Does not establish.**

- Validation: the comparisons are code against code on SYN-001.
- IDAES agreement beyond the near-sharp ε.
- That DWSIM's environment survives .NET 8's end of life.

## V17 — PASS (carried)

T08.A49 passes at `C` on all three hosts:

- the served descriptions digest is `171dd768…`;
- serving `v17-c2`'s two texts reproduces `6d13e13d…`;
- the request/response schemas are unchanged since `c7bbc98`;
- G16-b is clean on 40 of 40 runs;
- the records are attributable.

The served descriptions contain no stale package name (searched here).

**Does not establish.**

- **Agent behaviour on the changed `validate` path.** R-133's own limit.
- **Agent behaviour against the renamed server.**
  - The MCP `serverInfo` name changed from `process-runtime` to `openflowsheet` (R-149, Frank).
  - A49 does not compare it. R-149 records the surface as unmoved by its digests.
  - The campaign's tool-name prefix came from the client's configuration (`mcp__procsim__…`), so the tool names
    agents see are unaffected.
- **That served content equals `v17-c2`'s.** Content differs by F5's ruled additions and the package version.
- **Generality** beyond one pinned model and MCP.

## V18 — PASS

| Clause | Judgement | Evidence at `C` |
| --- | --- | --- |
| (a) dependency and data provenance, binary inventory | met | T08.A30 "A30 PASS" on three hosts: `ref-x86-64` (381 objects, closure 150; summary byte-identical to the committed one), `ci-x86-64` (381, 150) and `ci-aarch64` (308, 147; summary byte-identical). METIS is not reached, and no object in a required closure is undispositioned (ADR 0006 D4, Amendments 1 and 2). T08.A31 and A32 nodes green. T08.A44 finds CasADi's installed files equal to the audited per-file hashes on both architectures. The v2 policy file `numerical_policy_v2.yaml` is the project's own data, inside A43's checked contents |
| (b) final target-Jacobian regularity diagnostics | met | T08.A34, 0 violations over: 72 certificates (local, and each CI architecture); 1 + 1 clean-install certificates; the 49 bundle-set certificates (the 3 G8 bundles without one are failure bundles); both ensemble classes |
| (c) qualified energy checks | met | the same audit; K04 and T06 A32, A33, A37–A46 nodes green |
| (d) no enabled recovery edge without a direct failure test | met | T08.A33's bijection and direct-test nodes green; E13 `absent` |

**Does not establish.**

- **That the certificates re-emitted by the step-5 replays were audited.** They were not. On x86-64 they are bitwise
  the audited ones. On aarch64 v2 compared them, including the regularity block, and found no difference beyond its
  classes. That is an inference, not an A34 audit.
- **A legal reading of any licence.** The aarch64 toolchain-runtime objects remain unresolved, outside the closure
  and not loaded (R-142).
- **The public repository's contents.**
  - Clause (a) covers the sdist, the wheel and the default install.
  - The pre-public audit (2026-10-02, `docs/T08_DECISIONS.md`) found the redistribution right of the committed
    IDAES/DWSIM reference outputs unrecorded, and pre-redaction transcripts in history. Frank chose a squashed public
    history.
  - Both are publication matters, Frank's, and outside V18's registered clause.
- **The cause of O2**, the CI x86-64 `files_digest` difference under Python 3.13.15 against 3.13.5.
- **Commit fields in the A30 records.** They carry no `commit` or `tree_clean` field (format `t08-a30-inventory-v1`).

## V19 — PASS

| Clause | Judgement | Evidence |
| --- | --- | --- |
| (i) Frank's selection recorded (ADR 0022 accepted) | met | Frank chose C1 on 2026-09-29 (F3, "Ammonia synthesis is a nice case"). On 2026-10-01 he accepted ADR 0022 with its revision 1 (pin `6089593`, PR with the light gases vapour-only), recorded in the ADR's "Frank's choice recorded" (R-145). ADR 0022's own status line, registered with this specification on 2026-09-29, reads "Accepted when Frank records the choice here and T08's V19 verdict is `PASS`", and R-145 says the same. See reading 1 below |
| (ii) the dossier has every §7.1 item (T08.A60) | met | all twelve items present with a status word and evidence (`test_a60_…` green); the status words are not required to be `met` |
| (iii) H1–H6 `met` | met | H1, H2 and H4 `met` by R3 8. H3 and H6 `met`. **H5:** its `needs_frank` inputs are settled by Frank's statements of 2026-10-02, which is the rule's stated mechanism ("`needs_frank` resolved by Frank's statements"). The group property database becomes a cross-check that enters no certified record; M01 takes Tc, Pc, ω, c_p and ΔH_f from open, cited sources, recorded per value with the primary reference; the 4TU dataset may be used and referenced; the MSc report and the 2D draft may be cited; Ar and CH₄ come for M01 from the same open source. Every remaining item's rights are compatible with modes A/C |
| (iv) T08.A61–A63 pass | met | A61 as R3 8 reads it: `6089593`, 69 passed, 0 failed, 3 data-guarded skips counted not reproduced, one converged non-isothermal 1D solve (`c1-reactor.json`). A62 and A63: both PR flash states and the loop skeleton `optimal` in IDAES 2.13 with the light gases vapour-only (`c1-idaes.json`). Record tests 12/12 here |
| (v) no unknown in the rights table (T08.A64) | met | Every row carries a source, a licence or permission, a scope and a mode; none is unknown (`test_a64_…` green, which also refuses a dash in those four fields). The four `needs_frank` rows are answered by Frank's statements. The `k_ij` row now states, verifiably, that no third-party value is used: `c1-idaes.json` `binary_interaction` is "0 for every pair (no source; stated limitation)", the project's own literal, conveyed nowhere. See reading 2 below |

No hard criterion fails after measurement, and no selection or rights statement is outstanding. By §4.9 the gate is
PASS.

**What V19 is judged on.**

- **The dossier at `89dd3ca`.** It differs from `C`'s only by the appended "Frank's statements, 2026-10-02" section
  (`git diff C..HEAD`: the dossier, the decisions log and the RC record, nothing else).
- **The `benchmarks/t08/v19` records**, byte-identical at `C`.
- **Why that is admissible.** Frank's statements are inputs outside both lanes (§3.3), and D2.4 (R3 4) allows
  `docs/` to differ between `C` and the tag. Judging the dossier as it stood at `C` would give BLOCKED, and would
  require a new `C` for a documents-only change that the release policy explicitly permits.

**Reading 1, clause (i): not a re-reading.**

- **The two texts.** §4.9 (i) reads "Frank's selection is recorded (ADR 0022 accepted)". ADR 0022's status line was
  written with it, before any V19 result, and makes acceptance follow *from* V19 `PASS`. Its acceptance evidence
  lists "V19 `PASS` in `docs/reviews/T08-verdicts.md`".
- **Read literally, the pair has two fixed points**: V19 PASS with the ADR then accepted, or V19 never PASS. Requiring
  the status word first would make the gate unsatisfiable by construction, and no registered text intends that.
- **Frank's sequencing.** Frank, whose decision F3 is, ordered it in R-145: record the choice, V19 PASS, then
  Accepted. Clause (i)'s substance, his selection recorded in ADR 0022, is met.
- **The consequence.** ADR 0022 is to be marked Accepted together with this PASS (finding G4).

**Reading 2, clause (v): which items are rows.**

- **The test.** A64 is: every code and data item has a source, a licence or permission, a scope and a mode, and none
  is `unknown`.
- **The previous verdict.** It found the `k_ij` row with none of the four fields and named two ways out: a source,
  or a design-lane ruling.
- **What the row says now.** It describes the item as the selection's evidence actually uses it: `k_ij` = 0, the
  project's own choice, with no third-party value. That meets A64's four fields truthfully, without either route.
- **What it leaves to M01.** The source M01 later selects is a new data item. Its rights are recorded when it is
  chosen; `ComponentRecord.rights` is required by schema.
- **The named retrieval and cross-check tools.** The same holds for the tools in Frank's statement (`chemicals` /
  `thermo`; CoolProp or Cantera), which no T08 evidence uses or conveys. The data items are the per-value primary
  references M01 records.
- **The precedent.** R3 8 (b, c) drew the same line: work M01 owns is not selection feasibility.
- **What is not covered.** The table should still list those tools for completeness (finding G5). Their absence
  hides no unknown right of an item the selection uses.

**Does not establish.**

- **Validation of the reactor, the kinetics or the property route.** This is feasibility (R3 9). No model number is
  compared with data.
- **The rights of the property values, `k_ij` source and VLE data M01 will choose.** They are constrained by Frank's
  open-and-cited rule, but not yet known item by item. Whether a value compiled in `chemicals`/`thermo` is free of a
  copyrighted compilation is a per-value question for M01, not a legal reading made here.
- **That the vapour-only convention is adequate** for the inlet-temperature decision. It is unmeasured.
- **The K_NH₃ enthalpy term.** Frank's check against Rossetti et al. 2006 is pending. It is an M01 pin item
  (R3 8 (e)).
- **Experimental high-pressure VLE data.** None identified (item 6, `needs_fact`).
- **The three data-guarded tests** of the group's suite, counted not reproduced.
- **Review of the dossier.** It is an unreviewed build-lane draft. Its S7 re-score (1 to 2) is not applied by the
  design lane; §7.4 shows that no single provisional score moves the choice. The C2–C5 facts stay unregistered
  (W3.1 not run).

## V20 — PASS

| Clause | Judgement | Evidence at `C` |
| --- | --- | --- |
| (a) the fixed nominal correctness fixtures pass | met | T08.A47: T06 A02–A08, A16, A19 and A20, 10 of 10, none failed, missing or skipped, on `ref-x86-64`, `ci-x86-64` and `ci-aarch64` |
| (b) invalid structure rejected for the right reason, naming the revision's own objects | met | T08.A10 node (with the renamed-instance control); STR nodes green |
| (c) no false `VERIFIED` in the adversarial suite | met | T06 A16, A19 and A20 inside A47; no `VERIFIED` outside S3 in either RC ensemble record (worst success ratio 0.0968) |
| (d) ≥ 95 % over the registered ensemble | met | T08.A46 on `ref-x86-64`: S = 434 (370 first + 64 rescued), F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3. On `ci-aarch64`: S = 434 (367 + 67), 4 and 2. Both have S ≥ 418, no F-CRASH, no F-OTHER-ROOT, and registered runs untouched. T06 A34's same-class replay is 28/28 `MATCH` on each class under `K04-numerical-policy-v1`, the policy A34 registered (ADR 0025 W5). The CP lower bound 0.973264 is reported on both and never gated |

**Does not establish.**

- **That the starts are independent.** The CP bound assumes they are.
- **Out-of-sample robustness.** Run 2's starts informed `T06-revision-v2`.
- **The stress profiles.**
- **Equal per-start outcomes across architectures.** They are not equal: 370 against 367 first-start successes.

## Alternatives considered and rejected

1. **V13 FAIL on B50's pre-amendment text.**
   - Rejected. Frank's R-144 is a recorded amendment of a defect this lane found before the result (G2). The exact
     test it requires exists, with an independent expectation.
   - The prohibited move was the unamended re-reading. It was not made, and R-144 rejects it in its own text.
2. **V19 not PASS on clause (i) because ADR 0022's status word reads Proposed.**
   - Rejected under reading 1: ADR 0022 and R-145 make acceptance a consequence of V19 PASS.
   - Recorded as finding G4 so that the circularity is amended, not relied on twice.
3. **V19 FAIL on clause (v) because the `k_ij` status reads "`needs_fact` for M01".**
   - Rejected. A64 tests the four fields and "no unknown", and the row meets both with verifiable facts.
   - The previous verdict's "FAIL if still open" meant a row without those fields, which is no longer the case.
4. **V19 FAIL on clause (v) because the tools Frank named for M01 have no row.**
   - Rejected as a failure, kept as finding G5. They are M01's procedure: used in no T08 evidence, conveyed nowhere,
     and with public licences.
   - The rights that matter are those of the values M01 will record, which A64 cannot cover before they exist.
5. **V19 BLOCKED on the K_NH₃ check.** Rejected. R3 8 (e) made it an M01 pin item, and H2 is met regardless.
6. **V19 judged on the dossier as it stood at `C`, giving BLOCKED.** Rejected, for the reason given under "What V19 is
   judged on".
7. **Reading A45's PASS at `C` as reaching back to `814e151`.** Rejected (R4 1, R-146): `814e151` stays FAIL under v1.
8. **Treating `C` as not a release candidate because of §8.1 item 4's records location.**
   - Not decided here: §8.1 is no V-gate rule, and the clause cannot be met at any `C` without breaking D2.4 (G6).
   - The records' integrity is intact (43/43 hashes). G6 needs an amendment and a commit before the tag.
9. **Any gate BLOCKED for an agent-side reason.** Rejected: BLOCKED is reserved for inputs outside both lanes
   (§3.3), and none is missing.

## What would change these verdicts

- **At a later `C′`**, any red node, failing RC step or envelope change re-opens the affected row. In particular:
  - a changed served description, schema or content beyond the package version reopens V17 (BLOCKED, F5) and V13;
  - an undispositioned object in a closure makes V18 FAIL;
  - S < 418 on either class, or a `VERIFIED` outside S3, makes V20 FAIL;
  - a red B40–B50 node makes V13 FAIL.
- **V14 (b).** Only a new family or new SER settings, preregistered before any result (R-118).
- **V19.**
  - Frank withdrawing or qualifying a statement.
  - The 4TU deposit's terms changing on leaving curation.
  - A measurement showing a hard criterion fails, which makes it FAIL by §4.9. Examples: no open, cited source
    obtainable for a property value the route needs (H5); the reactor route failing at M01's pin (H1).
  - M01 finding the vapour-only convention inadequate does not reopen V19. It is M01's own limitation, stated in the
    dossier.
- **A45 at `C′`.** Any `MISMATCH` under v2, a bundle recording another policy, or a control not behaving as
  registered.

## What these verdicts do not establish

- **Empirical validation of anything.** Every V11–V18 and V20 result is numerical verification on synthetic SYN-001
  (L18). V16's comparisons are code against code, and V19 is feasibility. There is **no optimality evidence**
  anywhere in v0.1 (U05).
- **Bitwise reproduction across, or even within, a machine class.**
  - aarch64 is bitwise on 18 of 52 bundles.
  - The CI x86-64 T02 float file changed bytes between `78e92b7` and `C` with `src/` identical (RC record O6).
  - This is ADR 0007 F1's "reported, never promised".
- **Pivot-path reproducibility.** Those diagnostics are not compared under v2 (L07).
- **Portability** beyond Linux x86-64 and aarch64, Python 3.13 and the one lock. The reference host runs Python
  3.13.5 and CI runs 3.13.15.
- **Review.** No package is `reviewed` by this document.
  - Review 3 covered R3-W3 and ADR 0025's W2–W4.
  - No design-lane review of release spec Amendment R6 is on file. The build lane transcribed it, while R-149's
    watch item names the design lane for such text. Its values equal R-149's register entry and A42's records, and
    the identity move is Frank's (§8.3, F4).
- **Node-level CI records.** Clauses resting on "green at `C`" rest on CI totals, the static skip scan, and this
  verdict's local run of 34 nodes.

## Limitations that must travel into the manifest and the release report

- **The FAIL.** V14 (b) is FAIL (accepted by Frank, ADR 0021 D3) and is printed FAIL.
- **Envelope limitations.** Every L-id in the table's `Travelling limitations` column, per gate.
- **A45.**
  - It is met at `C` under `T08-numerical-policy-v2` (ADR 0025, Proposed), which was adopted after A45 failed at
    `814e151` under v1. That FAIL stands.
  - Pivot-path diagnostics are recorded and not compared, and C3 is a deliberate blind spot.
  - On aarch64, 34 of 52 bundles agree within the policy, not bitwise.
- **V13 (e).** Its PASS rests on B50 as amended twice by Frank after it was first found not met: R-134 (the digest)
  and R-144 (the package version). Each amendment was made because the release itself required the change.
- **V19.** Its PASS is a selection's feasibility, not validation, and the dossier's limitations travel with ADR 0022:
  - light gases vapour-only, so dissolved-gas effects are not represented or measured;
  - K_NH₃ pending Frank's check;
  - `k_ij` = 0 in the smoke runs;
  - property values to be chosen by M01 from open, cited sources;
  - no experimental VLE data identified;
  - three group tests not reproduced;
  - the dossier is an unreviewed draft.
- **Proposed ADRs.** ADR 0021, 0022 (Accepted with this PASS, G4), 0023, 0024 and 0025 are Proposed.
- **`library-only` paths.** Clause (b) of V13 and edges E1 and E2 of V14 (c) are `library-only`.
- **A34's coverage.** The audit did not separately cover the certificates re-emitted by the replays.
- **The RC records.** Only their sha256 are committed. The files exist on one host (git-ignored) and as CI artifacts
  with finite retention (G6).

## Findings

**Status of the findings made at `814e151`.**

- **G1** (the cross-architecture comparison): closed by ADR 0025, R-146/R-147, Amendments R4 and R5. W8 closed the
  envelope's `reproducibility` axis and L07 (G1e).
- **G2** (B50 unsatisfiable): closed by R-144 and the exact test.
- **G3** (the gate script cannot see §8.1): closed. The script reads the RC record with review 3's closed vocabulary.
  Two residuals remain:
  - **(a) A failure word in another case.** A Result cell such as "PASS: Failed to upload" still classifies as
    passed: Ruling 3 lists it as a probe but gives no rule that catches it. No such cell exists at `C`.
  - **(b) The `tested` manifest.** With `--rc`, the script does not require §8.1 item 5's manifest. Its YES would
    therefore not show that the manifest exists.

**New at this `C`.** None changes a row. G4–G6 should be settled before a tag is proposed.

- **G4 — V19 (i) and ADR 0022 are circular as written.**
  - Needed: amend §4.9 (i) to read "Frank's selection recorded in ADR 0022 (which becomes Accepted with this
    verdict)".
  - When this PASS is recorded, the build lane marks ADR 0022 Accepted. Its acceptance evidence asks for "Frank's
    choice and statements recorded in this ADR", so the ADR should also point to the dossier's statements section.
- **G5 — the dossier's tables lag Frank's statements.**
  - **The property-database row.** Its scope and mode cells still describe the withdrawn use ("values would enter
    ComponentRecords").
  - **The named tools.** The retrieval and cross-check sources Frank named (`chemicals`/`thermo`; CoolProp or
    Cantera) have no rows.
  - **The item and H statuses.** The item-status table still shows `needs_frank` for items 1, 2 and 8 and for H5.
  - **An inconsistency.** The statements section says "items 6 and 7 stay `needs_fact`", whereas the table has 7
    `met (proposed)` and 11 `needs_fact`.
  - Needed: bring the tables into line, as build-lane documentation, before ADR 0022 cites the dossier and before
    the release notes do.
- **G6 — §8.1 item 4's records location cannot be met with D2.4.**
  - **The conflict.** "Small text under `benchmarks/t08/rc/`" puts records into a path that D2.4 (R3 4) requires the
    tag commit to share with `C`. Records are written after `C`, so they can never be committed there without
    making a new RC.
  - **Today.** Only the records' sha256 are committed (`docs/t08-rc-record.md`). The files live on `ref-x86-64`
    (git-ignored) and in CI artifacts with finite retention.
  - **Needed.** A design-lane amendment naming a tracked location outside the checked paths, for example
    `evidence/T08/<C>/rc/` un-ignored for the small texts. Then commit the records there before the tag.
- **G7 — the rename broke the B50 fixture's generator.**
  - **The fault.** The scripted substitution (`3a1345f`) changed `scripts/t08_b50_surface_fixture.py` to import
    `openflowsheet` inside a `c7bbc98` worktree, whose package is `process_runtime`. Its re-serve (`--check`) path
    now fails its own import guard.
  - **Effect.** B50 is unaffected: the fixture is unchanged since `a28fde3`, and the test checks it against
    `v17-c2`'s transcripts without re-serving.
  - **Needed.** The serve snippet imports the historical package name. Sweep the other scripts that re-serve a
    historical tree for the same defect.
- **G8 — a note for ADR 0021.** Its proposed revision 2 names `src/process_runtime/__init__.py`. The gate script
  checks `src/openflowsheet/__init__.py`, which is correct for the renamed tree. R-149 keeps ADR text unchanged, so a
  dated note in ADR 0021 would stop a later reader from "fixing" the script back.

**Before the gate script prints YES** (build lane, not this document):

- set `docs/requirements.yaml`'s V13 and V19 verdicts to these words (T08.A02/A03);
- regenerate the CHANGELOG gate table;
- write the `tested` T08 manifest at `C`.
