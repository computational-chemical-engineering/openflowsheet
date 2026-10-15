# V02 alpha — verdicts on V11–V20, W21 and W22 for `0.2.0a1`

**Release candidate:** `6fec82232e1c47308a5e1d67338058f352992800`   **Judged:** 2026-10-15   **By:** design lane (`verdict`)

| Gate | Verdict | Failing clauses | Travelling limitations | Basis |
| --- | --- | --- | --- | --- |
| V11 | PASS | — | L38 | T08 §4.1 with MR-10; at C_α¹: K06, T01, T06 and T07 nodes, T08.A35, T08.A10 and M07a.A42 green in step 1 (CI 38772065394, both architectures) |
| V12 | PASS | — | L02, L26, L27, L28, L29, L30, L-CSTR-1, L-CSTR-2, L-CSTR-3 | T08 §4.2, denominator unchanged (spec §5.1); at C_α¹: T05, T05b and build-first B10–B19 nodes green in step 1 on both architectures; coupled cases SYN-001, T05 C1–C3, PTC-R1 |
| V13 | BLOCKED | V13 (e): Frank's V17 carry in ADR 0028, which names B50's surface, is pending | L10, L22, L23, L24, L36, L38, L43, L-WS-1, L-WS-2 | T08 §4.3, T08.A71 and MR-7; at C_α¹: T01, T02, K03 and B40–B49 nodes green in step 1; B50's counterpart: content by M07a.A51, digest and schemas by the chain (step 8), under a carry not yet recorded |
| V14 | FAIL | V14 (b) | L01, L08, L20, L21, L43 | T08 §4.4; T08-verdict-V14b.md (PTC-R1: the saddle clause fails on both registered platforms), unchanged at C_α¹; Frank's D3 acceptance for 0.2.0a1 pending; homotopy and edges: T04, T02 and T08.A33 nodes green in step 1 |
| V15 | PASS | — | L02, L14, L19, L20, L33 | T08 §4.5; at C_α¹: T02, T03 and T06 (ADV-05, THM-09) nodes green in step 1 on both architectures; the certificate schema fixes both claims to NOT_ASSESSED, as all five step-12 certificates carry |
| V16 | PASS | — | L16, L17, L18, L32 | T08 §4.6; T06 verdict 1 stands (8 of 8 by both tools, 16/16 AGREE); T08.A48 passes at C_α¹ on ref-x86-64, ci-x86-64 and ci-aarch64 (step 7) |
| V17 | BLOCKED | V17 (a): Frank's V17 carry in ADR 0028 is pending | L11, L12, L13 | T08 §4.7 with MR-1, MR-2 and MR-6; M07a.A37 at C_α¹ on three hosts: served digest 383b4e2c… decomposes to 6c4375b4… and 171dd768…, and to 6d13e13d… with v17-c2's texts; G16-b 40 of 40 |
| V18 | PASS | — | L03, L05, L06, L15, L19, L25, L34, L37, L39, L40, L41 | T08 §4.8 with MR-11 and MR-12; at C_α¹: T08.A30 PASS on three hosts, no undispositioned object in a required closure, no new extra; T08.A31–A33 nodes green; T08.A34 0 violations on every audited set, step 12's five coupled-route certificates included |
| V19 | PASS | — | — | T08 §4.9; ADR 0022 Accepted with Frank's selection (R-145); the dossier at C_α¹ with H1–H6 met; the benchmarks/t08/v19 records byte-identical to those at 67c66d9; the A60–A64 record tests green in step 1 |
| V20 | PASS | — | L04, L07, L09, L31, L32, L38 | T08 §4.10; at C_α¹: T08.A46 S = 434 of 440 on ref-x86-64 and on ci-aarch64, no crash, no other-root, same-class replay 28/28; T08.A47 12/12 on three hosts; T08.A10 node green |
| W21 | BLOCKED | W21 (c): Frank's acceptance of M02 N1 in ADR 0028 is pending | L05, L06, L07, L15, L19, L20 | spec §6.1; step 1: M01 stand-in and M02 G3–G9 nodes green on both architectures; step 12 on ref-x86-64: G10v3 and G11v3 met, G12 CONVERGED and VERIFIED, reproduce MATCH, live rerun bitwise |
| W22 | PASS | — | L42 | spec §6.2; step 1: M01.A05–A22, A34, A37 and M02 G7, G8 nodes green; step 11: crosscheck byte-equal on recomputation, IDAES re-run numbers identical; step 12: G12 VERIFIED on the route |

## Read this first

**The twelve.** Eight PASS (V11, V12, V15, V16, V18, V19, V20, W22), one FAIL (V14 on clause (b), as
expected), and three BLOCKED (V13, V17, W21), each on one input that only Frank can give. No clause that the lanes were
to produce is missing or failing. No YES is possible from this document: D2.2 (spec §7.3 item 4) refuses a `BLOCKED`
claimed gate, so V13, V17 and W21 must be re-judged after Frank records his answers (finding A2 on how the date rule
interacts with that).

**What differs from v0.1's verdicts at `67c66d9`** (`docs/reviews/T08-verdicts.md`):

- **V13: PASS → BLOCKED on V13 (e).** At v0.1, B50's digest and schema clauses were met by T08.A49 directly. The
  v0.2 surface moved (R-192, R-234), so B50's counterpart is MR-7: "digest and schemas by the chain, *under the same
  carry (MR-2)*". ADR 0028's `V17 carry` row names "V17, and T08.B50's surface". That carry is `pending`.
- **V17: PASS → BLOCKED on V17 (a).** T08 §4.7: a surface different from R-133's carried surface makes V17 `BLOCKED`
  pending Frank. The chain holds; the carry is not recorded (MR-2; M07a.A61's stated expectation).
- **W21 and W22** were not judged at v0.1.
- The other eight V rows keep v0.1's verdicts, re-judged on C_α¹'s own RC job.

**C_α⁰ (`e0e198e`).** Superseded by Amendment 2 (R-349). Its step-10 audit failed (5 violations in step 12's
coupled-route certificates), which was V18 (c); R-346 wrote no verdict there. That failure stands as history. R-345
fixed the defect, and at C_α¹ the same audit finds 0 violations in 77 certificates.

**The precondition (§6.3: M07a's manifest `tested`).** The manifest at C_α¹ is `implemented`: 37 pass, 0 fail, 6
unsupported. I judge the precondition **met in substance**. The six are A52 (two nodes: the gate table that
`v0_2_gate.py --markdown` prints, and the pending markers) and A60–A64 (this document and the ledger it feeds). Each is
an output of this verdict, and spec §9.2 step 5 orders the `## v0.2.0a1` section and the ledger after it. Every
assertion that produces evidence for a clause (A00–A51, A53, including the RC steps A30–A44) passes. The spec's own
text is inconsistent on this point (finding A4).

**Standing.** This is an agent verdict, numerical and procedural only. It is not scientific review and not a
process-model sign-off. It sets no `reviewed`. Human sign-off (R-017's form) is Frank's and is not claimed. It moves no
tolerance, band or classification rule.

**Criteria, read before the evidence and not re-read after it:** V02 alpha release spec §4–§6, §8 and §18
(Amendment 2), with Amendment 1's markers; T08 release spec §3.3 and §4 with its amendments; T08 build-first B40–B51
with Amendments 3 and 4 (V13 (e)); ADR 0028 D1–D7 and its two tables as they stand (all four cells `pending`);
ADR 0022's status and revision 1 (V19 (i)); M02 design note §10 G3–G12 with §14.5–§14.7 (W21); M01 spec §9 and §11
(W22). The blueprint's SHA-256 `66f574b0…` equals the plan header's; recomputed here.

## Evidence and provenance

| Evidence | Produced by, where | Independent expectation | Class |
| --- | --- | --- | --- |
| RC record `docs/v02-alpha-rc-record.md` (`682389b`) | build lane: local `ref-x86-64` worktree at C_α¹ (clean, one script, threads pinned); CI dispatch 38772065394 and push 38772054427, both `success`, head C_α¹ (checked here in `artifacts/ci-run-*.json`) | none: the record reports and judges nothing | record |
| The 61 records it hashes | as above | **recomputed here: 61 of 61 sha256 equal the record** (59 committed under `evidence/M07a/6fec822…/rc/`, the two ensemble run files in the RC worktree's `artifacts/rc/`) | provenance |
| Step 1: `check (ubuntu-latest)` 8507 passed, 100 skipped; `check (ubuntu-24.04-arm)` 8479 passed, 98 skipped | CI 38772065394 on the public repository | the tests' own expectations | tested (CI) |
| Skipped nodes in step 1 | not listed: the CI logs print totals only | static scan here: in the V-clause test files (K, P, T series) the skip sites new since `67c66d9` are exactly nine, all in `test_t06_w31_runs`, `test_t07_evidence_manifest`, `test_t08_evidence_manifest`, `test_t08_ptc_r1_case` and `test_t08_w4_v0_1_gate`: guards on the archived pre-0.1.0 history (`require_archived_history`, R-150) or on a manifest's presence. None guards a node an RC clause rests on; the PTC-R1 git-order nodes bear only on V14 (b), which fails regardless. M01 and M02 tests have no skip site that fires on Linux with the server extra. | inference, stated as such (finding A7) |
| The local gate at C_α¹ (8574 passed, 33 skipped; B-AM2-6) | a session's report, no record file | none | **pins nothing**; the verdicts use CI |
| Steps 2–10 records (`t08-rc-v1`) | as listed in the RC record; each carries `commit` = C_α¹, `tree_clean = true`, the lock `ead4edf1…` and a registered `machine_class` (M07a.A43) | registered values: R-149 identity digests; D_0 `171dd768…`, D_1 `6c4375b4…`, D_2 `383b4e2c…` (R-319), `6d13e13d…` (R-137); `S_min` 418; A34's rule and T06 A33's set (unchanged by Amendment 2) | ci, tested, record |
| Step 11 (`step11/rc-step11.json`) | local, pinned cross-check and IDAES environments (freezes hashed) | `external_crosscheck.py --check` recomputes the committed record and compares bytes; the IDAES re-run's numbers against the committed `benchmarks/m01/idaes-conformance.json`. The re-run's sha256 `7e1d41dd…` equals the one in M01's manifest | ci-equivalent re-run; validation inputs |
| Step 12 (`step12/rc-step12.json` and its eight records) | local `ref-x86-64`, reactor environment built from C_α¹'s lock and verified, one thread, shared host | M01's bounds and the probe record (G10), the design lane's G11v3 and G12 criteria; G12's own certificate | numerical verification against the registered records; a regression of the group's model |
| Step 12's five kept certificates | committed under `rc/step12/certificates/` (B-AM2-9) | checked here: the bundle's sha256 `faa8e4da…` equals `g12-real-loop-v3.json`'s `certificate_sha256`; the live and replay copies are byte-identical to it (B-AM2-10) | provenance |
| M01 (`3c80392`) and M02 (`ba90619`) manifests, `tested` | build lane at their own commits, both ancestors of C_α¹ (checked here) | as stated per check | evidence about other commits; counted only through the RC job (spec §4 rule 3) |
| Frank's statements and answers (R-145, R-149, ADR 0022, the dossier's 2026-10-02 statements; ADR 0028's four `pending` cells) | recorded by the lanes from Frank's answers | none: they are the authority's decisions | decisions |

---

## V11 — PASS

| Clause | Judgement | Evidence at C_α¹ |
| --- | --- | --- |
| (a) semantic diff | met | T07 `diff_revisions` / `semantic_diff` nodes in step 1, both architectures |
| (b) immutable drafts | met | K06 revision, draft/ready, conflict and idempotent-commit nodes in step 1 |
| (c) task-specific validation | met | T01 STR-01…06 and R-022's DRAFT/INVALID nodes in step 1 |
| (d) units and component/reference checks | met | T06 A43, A55–A57, A67–A74 and THM-05 nodes in step 1; K06's structural check superseded by T01 A09 |
| (e) a real migration fixture | met | T08.A35 (the v0.0.0 bundle) in step 1; MR-10's counterpart M07a.A42: the `SYN-001-nominal` bundle written at tag `v0.1.1` gets a typed report from C_α¹'s `replay`, `inspect` renders it (step 1; manifest `pass`) |

T08.A10 (D1) is green in step 1. **Does not establish:** migration of arbitrary old documents, only the two real
bundles; structural checks are generic (L38).

## V12 — PASS

Every model of §14.3's list has, at C_α¹, passing contract, limiting/failure, balance and derivative nodes in step 1 on
both architectures, and appears in a registered coupled case (SYN-001, T05 C1–C3, PTC-R1). The C1 models are W21's and
W22's evidence, not V12's (spec §5.1); they enter the envelope's `unit_models` axis. **Does not establish:** the
listed model limitations; any C1 model's definition of done under V12.

## V13 — BLOCKED on V13 (e)

| Clause | Judgement | Evidence at C_α¹ |
| --- | --- | --- |
| (a) DM/SCC/BTF with block statistics | met | T01 nodes in step 1 |
| (b) safeguarded recycle and coupled EO | met | T02 A13–A15, A32, A34 nodes in step 1; E1/E2 library-level (L43) |
| (c) scales before iteration | met | K03, T02 nodes in step 1 |
| (d) model initialization | met | as v0.1: each §7.4 source has a passing node or a recorded absence (K03 §10.1; L10) |
| (e) compatible warm starts | **blocked** | B40–B49 nodes green in step 1 (T08.A71's four elements: B41's opening and source, B41's checks, B43's rejection to the next source). B50's counterpart (MR-7): content differences exactly B50's three entries plus the register-named v0.2 additions, M07a.A51 `pass`; digest and schemas by the chain, M07a.A37 on three hosts; G16-b 40/40; `t07_reference.json` and `t07_reference_c2.json` unchanged since `c7bbc98` (`git diff` empty, checked here). **Missing:** the carry under which MR-7 places the digest and schemas, ADR 0028's `V17 carry` row ("V17, and T08.B50's surface"): `pending`. |

**Why it differs from v0.1 (PASS).** At `67c66d9` B50's surface clauses were met by T08.A49's digests equalling R-133's.
They no longer equal them, by design, and the counterpart MR-7 that replaces them names the carry as part of itself.
The missing input is Frank's decision, so the clause is `BLOCKED`, not `FAIL` (T08 §3.3). The spec's own expectation
list (M07a.A61) names only V17 here (finding A3). One answer unblocks V13 and V17 together.

**Does not establish:** that the v0.2 surface is acceptable for agents (Frank's carry decides that); warm starts beyond
exact id-set compatibility (L-WS-1, L-WS-2).

## V14 — FAIL on V14 (b)

- **(a) typed homotopy: met.** T04 A02–A12 nodes in step 1.
- **(b) one PTC family qualified by §7.5: not met.** T08-verdict-V14b.md: on PTC-R1, the saddle clause fails on both
  registered platforms, so (b1) fails. Nothing after `67c66d9` preregisters a new family or new SER settings, so the
  result still holds at C_α¹. The PTC-R1 git-order nodes skip in CI (archived history); they bear on (b2), and (b1)
  fails regardless.
- **(c) three bounded recovery edges: met.** T02 and T04 nodes and T08.A33 in step 1; E1 and E2 are library-level (L43).

Same verdict as v0.1. ADR 0021's acceptance (2026-09-29) is not read (ADR 0028 D2). Releasable only if ADR 0028's D3
table records Frank's acceptance dated on or after 2026-10-15; today it reads `pending`. **Does not establish:** that
PTC can never qualify; PTC stays experimental (L01).

## V15 — PASS

- **(a) frozen phase attempts with restart: met.** T03 A00–A26 nodes in step 1.
- **(b) cross-unit promotion to EO without nested SM: met.** T02 nodes in step 1.
- **(c) multiple roots with honest branch reporting: met.** T03 fingerprint and provenance nodes; T06 ADV-05 and
  THM-09 nodes in step 1.

The certificate schema fixes `uniqueness` and `dynamic_stability` to `NOT_ASSESSED`; all five step-12 certificates
carry both (checked here). **Does not establish:** root completeness, uniqueness or stability (L19).

## V16 — PASS

T06 verdict 1 stands (8 of 8 by both tools, 16/16 AGREE, positive controls DISAGREE). T08.A48 (our side re-solved
equals its committed records) passes 12/12 on ref-x86-64, ci-x86-64 and ci-aarch64 (step 7). The tool side is not
re-run (T08 §4.6). **Does not establish:** IDAES agreement beyond the near-sharp ε (L16); the tools' environments
beyond their pins (L17).

## V17 — BLOCKED on V17 (a)

- **(a) a surface to which Frank has carried `v17-c2`'s evidence, and M07a.A37's chain holds: blocked.** The chain
  holds on three hosts: `d(T(C_α¹))` = `383b4e2c…` = D_2 (R-319); stripping c_2 gives `6c4375b4…` = D_1; stripping c_1
  from that gives `171dd768…` = D_0 (R-133); serving `v17-c2`'s two texts gives `6d13e13d…` (R-137); the 17 tools and
  their description files are as registered; the negative controls are in the test. **Missing:** Frank's `V17 carry`
  answer in ADR 0028, `pending`.
- **(b) G16-b 40 of 40 over Python, CLI, HTTP and MCP: met** on three hosts.

**Why it differs from v0.1 (PASS).** T08 §4.7, as amended by R3 2: the surface at C_α¹ differs from R-133's, so V17 is
`BLOCKED` pending a new decision of Frank's; MR-2. **Does not establish:** agent behaviour on the v0.2 surface; no agent
was run (L12).

## V18 — PASS

- **(a) dependency and data provenance, binary inventory: met.** T08.A30 `PASS` on ref-x86-64 (381 objects, closure
  150), ci-x86-64 (381, 150) and ci-aarch64 (308, 147), no undispositioned finding in a required closure, METIS not
  reached. T08.A31 and A32 nodes in step 1, A31's checks in step 3 (8/8). MR-12: C_α¹ declares the extras `dev` and
  `server`, as `v0.1.1` does (checked here), so no new extra needs an audit.
- **(b) final target-Jacobian regularity, (c) qualified energy checks: met.** K04 and T06 A32, A33, A37–A46 nodes in
  step 1. T08.A34 (MR-11) finds 0 violations in every audited set: 77 locally (72 plus step 12's five, bound by hash),
  72 on each CI `rc-steps` host, 1 in each clean install, 49 in the bundle set. The ensemble's certificates are held to
  T06 A33 inside step 6 (A33 0 on both hosts).
- **(d) no enabled recovery edge without a direct failure test: met.** T08.A33 in step 1.

Same as v0.1. C_α⁰'s failure on (c) is history (R-346); the defect R-345 removed does not recur. **Does not
establish:** the certificates step 5's replays re-emit (T08 B13); the certificates' locality (L19); the provider
shared with the energy checks (L06).

## V19 — PASS

- **(i) Frank's selection recorded in ADR 0022: met.** Accepted 2026-10-02 with revision 1 (R-145).
- **(ii) every §7.1 item: met.** The dossier at C_α¹ has items 1–12. Its edits since `67c66d9` record Frank's
  statements of 2026-10-02 and R-152's K_NH₃ note; no status moved away from `met`.
- **(iii) H1–H6 `met`: met.** The status column reads `met` for all six at C_α¹ (read here).
- **(iv) T08.A61–A63: met.** The record tests in step 1; `benchmarks/t08/v19/` is byte-identical between `67c66d9`
  and C_α¹ (`git diff` empty, here).
- **(v) no unknown in the rights table: met.** T08.A64 in step 1. The rows reading `needs_fact` for M01 state their
  source, licence, scope and mode, as v0.1 judged.

Same as v0.1. **Does not establish:** any comparison with data; the dossier is a feasibility record.

## V20 — PASS

- **(a) nominal fixtures, (b) invalid structure rejected naming the revision's objects, (c) no false `VERIFIED`: met.**
  T08.A47 12/12 on three hosts (T06 A02–A08, A16, A19, A20, A47, A50; 165 nodes, none failed, missing or skipped);
  nothing verified outside S3 (worst success ratio 0.0968); T08.A10 node in step 1.
- **(d) ≥ 95 % over the registered ensemble: met.** T08.A46: N = 440, S = 434 on ref-x86-64 (F-BUDGET 3,
  F-FALSE-SUCCESS-CAUGHT 3) and on ci-aarch64 (4, 2), against S ≥ 418; no F-CRASH or F-OTHER-ROOT; same-class replay
  28 of 28 `MATCH`. The one-sided 95 % Clopper–Pearson lower bound, 0.973264, is reported, never gated, and assumes
  independent starts, which clustered starts are not.

Same as v0.1. **Does not establish:** robustness beyond the nominal profile (L09); out-of-sample performance for
`T06-revision-v2` (L32).

---

## W21 — BLOCKED on W21 (c)

Judged by spec §6.1 as ADR 0028 D7 reads it. Every number below is the group's model at the pin, run through the
adapter: numerical verification against registered records, not empirical validation.

**(a) Port mapping: met.**
- M01.A25–A32 and A49–A51 (stand-in path) and M02 G4 (e)–(g), G8 (a)–(e), G9 (b) nodes in step 1 on both
  architectures.
- M01.A52's record half: mapping 1 ulp against 2 (node in step 1).
- G10 (h) at step 12: the full boundary at N_tubes = 1, max relative difference 1.43 × 10⁻⁸ against 10⁻⁶.

**(b) Accuracy contract: met.**
- The registered v3 variant declares `precision_floor_rel` 10⁻⁶ and the design grid's discretization estimate
  (num_z 800). G10 (i): every `ok` result's estimate equals the reference, 3 of 3.
- G10 (b) 1.56 × 10⁻⁸ (≤ 10⁻⁶); G10 (e) 3.84 × 10⁻⁸ (≤ 10⁻⁷; the adapter's figure, equal to the v2/v3 records; the
  spec's table quotes M01's probe half, 2.98 × 10⁻⁸, finding A10); G10 (f) 5.06 × 10⁻⁵ (≤ 10⁻³).
- G12's floor ratios 65.3 (ξ) and 13.3 (T) against ≥ 10. T's margin is 1.33×.
- M01.A48's record half (the grid study) in step 1.

**(c) Out-of-process execution policy: blocked.**
- G3 (a)–(h) in step 1 on Linux (both architectures); G4 (a)–(i) and G5 in step 1: met.
- The support matrix (`docs/support-matrix.md`, external model execution row) states the profile
  `external-subprocess-v1`, "not a sandbox", Linux registered, macOS best effort, Windows refused before spawn: met.
- **Missing:** M02 N1 accepted by Frank in ADR 0028's decisions table, which §6.1 makes a precondition of the clause,
  "not a default". The cell reads `pending`. The input is Frank's, so the clause is `BLOCKED`.

**(d) Timeout: met.**
- G3 (b) in step 1: `timed_out` within 3.5 s under `timeout_s = 1`, no retry.
- The per-attempt timeout in force at C_α¹ is the registered v3 variant's 450 s, from §5.2's rule as amended by
  §14.5 D4 (D104, D111).
- G11 (d) at step 12: `startup_s` 1.78–1.91 s, `solve_s` 27.8–28.1 s over five repeats (start-up share 6.1 %). No step-12
  attempt came near the timeout; G12's slowest experiment took 41.6 s.
- The G11v3-4 rule recomputed at step 12 under that run's load would give 270 s for V5. This is recorded, not a
  re-registration (finding A9).

**(e) Provenance: met.**
- G6 (a)–(c) in step 1.
- The six items of blueprint §9.1 in every experiment result record step 12 writes. G10 calls the backend directly and
  writes none. G12's four results and their attempts sit in its coupling record. `reproduce` returned `MATCH` from that
  record, which it cannot do unless the record passes `coupling_record_problem`'s check against
  `experiment.schema.json#/$defs/coupling`. That check `$ref`s `result` and `attempt`, whose required members carry the
  boundary, the variant id, sha256 and reactor, the discretization estimate, the stage, the element defects and the
  timing. G11's results, written by the same `ExperimentRunner` to scratch stores, were not audited one by one. Their
  presence rests on that single writer path, schema-checked by G5's node in step 1 and by G12's record in step 12
  (inference, finding A6).
- G10 (g): M01.A47 (a) bitwise, environment block equal.
- G12's `reproduce`: `MATCH`, floats bitwise, 4 external results replayed from the record.
- The reactor commit in the v3 variant and in the built environment is `6089593464fc9bc2c0a0cb58e30ad5433ece6332`,
  ADR 0022's pin.
- Rights: T08.A64 in step 1. The wheel's package data list holds the reactor lock and no other file of the group's;
  T08.A32's node in step 1 refuses any third-party data or non-package Python in the sdist or wheel.

**(f) Parent-model validation, read as ADR 0028 D7: met.**
- **(f1)** G10 (g): A47 (a) bitwise at step 12.
- **(f2)** T08.A61: the group's suite at `6089593`, 69 passed, 0 failed, 3 skips counted not reproduced. This is a
  record re-checked in step 1, measured at T08 on one host. It is the pin the variant names.
- **(f3)** The grid study and DX-01 estimate (M01.A48's record half), path independence (G10 (b)) and the estimate
  carried in every `ok` result (G10 (i)).
- **(f4)** Stated here, and to be stated in the notes:
  1. the group's published comparison with experimental data (Gargiulo et al. 2025 §3.1, of Rossetti et al. 2006's
     rate law; dossier H2, R-143) is the group's evidence;
  2. this project has compared no reactor result with data;
  3. the numbers are the group's model at the pin, a regression;
  4. their discretization bias is 1.0–1.4 % in NH₃ (M02 §13).

  The notes are written after this verdict (§9.2 step 5). The current draft states items 1–3 and lacks item 4 (finding
  A5). The re-judgement W21 needs anyway checks the merged section. If it lacks item 4, (f4) is not met there.

The stronger reading of (f), that this project compares reactor results with data, is not the default (F-α4) and is
not applied.

**W21 does not establish:**
- that the reactor is right: every real-reactor number is the group's model at the pin, a regression, with F-R2, F-R3
  and its discretization bias;
- bitwise reproduction across machines, or any run on aarch64, which is not measured (Q1). The alpha envelope has no
  limitation row saying so (finding A1);
- a sandbox, Windows support, or concurrency across hosts or on network filesystems;
- sensitivities through the reactor, or optimization;
- the convergence of coupled loops in general (one real loop, two edges);
- that the stand-in certifies anything about the reactor (R-199);
- timings under any other load: step 12 shared its host with other work.

## W22 — PASS

**(a) Numerical verification: met.** M01.A05–A22 in step 1, against closed forms from `m01_reference.py`, independent
of the implementation (tolerances 10⁻⁹–10⁻¹⁴). M01.A34 (`--check`, 88 claims) in step 1.

**(b) Conformance with an independent implementation of the same method: met.**
- M01.A37 in step 1: `pr-c1-v1` against the committed IDAES 2.13 record.
- Step 11: the IDAES re-run's numbers equal `benchmarks/m01/idaes-conformance.json`'s. The one differing member is
  `inputs.reference_values_yaml_sha256`, listed, with M01's manifest giving the reason (Amendment 1 changed that file
  outside `closed_form`).
- The re-run file is byte-identical to M01's own re-run (`7e1d41dd…`).

**(c) Empirical validation of pure-component behaviour against the reference equations of state: met.** Step 11's
`external_crosscheck.py --check` recomputes the record at C_α¹ and finds it byte-equal ("matches"). The values,
re-read here from the record:

| Assertion | Measured | Band | Band ÷ measured |
| --- | --- | --- | --- |
| M01.A38, max \|P_sat,PR/P_sat,ref − 1\| | 0.012675 (240 K) | 0.02 | 1.58 |
| M01.A39, max \|Δ ln φ^L\|, NH₃ | 0.040096 (250 K, 25 MPa) | 0.05 | 1.25 |
| M01.A40, max \|Δ ln φ^V\| | 0.042371 (CH₄, 268.15 K) | 0.05 | 1.18 |

These are validation bands (R-160), not numerical tolerances. The ratios are quoted, not turned into confidence. The
reference is CoolProp 8.0.0's equations of state, themselves correlations of data, not raw measurements.

**(d) Sufficient for the selected chemistry: met.** G7 (a)–(e) and G8 (a)–(c) in step 1. G12 at step 12: the C1 loop
binds every property evaluation to `pr-c1-v1` and ends `VERIFIED`.

The gaps the route leaves, stated:
- the LIQUID regime and pure-NH₃ flashes are deferred and refused typed (M02 N5);
- dissolved light gases are not represented (R-143);
- k_ij = 0: k_H2–NH3 = 0.1 would move y* by −3.1 % (R-157);
- there is no mixture VLE validation (R-160);
- PR's saturated-liquid volume is 11–30 % high and its enthalpy of vaporization 2–5 % high (M01 §11). No v0.2 loop
  decision uses either.

**W22 does not establish:** mixture VLE; the effect of k_ij beyond R-157's statement; the near-critical region;
liquid-density fitness; any claim outside the five C1 components and M01's registered domain.

---

## Alternatives considered and rejected

1. **V17 PASS (carried), because the chain holds and the carry is the expected default.** Rejected. T08 §4.7, MR-2
   and M07a.A61 make the carry Frank's recorded answer, and a default is not an answer. ADR 0028 even requires it to
   be dated on or after this verdict.
2. **V13 PASS, treating the carry as V17's business only.** Rejected. MR-7's counterpart text reads "under the same
   carry (MR-2)"; ADR 0028's carry row names "T08.B50's surface"; T08.B51 makes B50 part of V13 (e). At `814e151`,
   B50 alone made V13 FAIL, so B50 is load-bearing in V13.
3. **W21 PASS, reading N1 as a gate precondition only (§7.3 item 11), not as part of clause (c).** Rejected. §6.1 lists
   it under (c) as "a precondition, not a default", and §6 says a clause is met only when every listed item holds.
4. **W21 FAIL on (f), because the draft notes lack the fourth statement.** Rejected. The notes are written after this
   verdict (§9.2 step 5), and the verdict's half of (f4) is met here. The defect is named (A5) and is checked at the
   re-judgement W21 needs anyway.
5. **W21 FAIL, or no PASS anywhere, because the envelope lacks a Q1 row.** Rejected as a clause verdict. §6 defines a
   gate's PASS by its clauses, and §4 rule 4 governs the envelope and the notes. Recorded as finding A1, which must be
   resolved before a tag is proposed.
6. **No verdict, because M07a's manifest is `implemented`.** Rejected. The six unsupported assertions are this
   verdict's outputs or come after it, and every clause input passes (Read this first).
7. **W21 (e) not met for want of a record-by-record audit of G11's scratch results.** Rejected. Field presence is
   structural, and the single writer path is schema-checked at step 1 and, on the real variant, at step 12. Stated as
   inference (A6).
8. **V18 not PASS because step 5's replays re-emit certificates that nobody audits (B13).** Rejected. This is v0.1's
   accepted scope, a recorded limitation. The 49 bundles were audited when written.
9. **V14 PASS on route (a) alone.** Rejected (R-118; T08 §4.4 "Why not re-read").
10. **Reading the W22 band ratios as a confidence statement.** Rejected (spec §6.2).

## What would change these verdicts

- **Frank records `V17 carry` as `accepted, <date>`.** V13 (e) and V17 (a) are re-judged at the same C_α¹. They are
  expected to be met if M07a.A37 and A51 still hold. Choosing the new campaign instead puts V17, and B50's surface
  half of V13 (e), on that campaign's evidence.
- **Frank records M02 N1.** If accepted: W21 (c) re-judged, with (f4)'s notes half checked at the same time. If
  declined: W21 (c) is not met and W21 is FAIL, which is releasable only through ADR 0028's D3 table.
- **Frank chooses an N3 alternative.** The specification is amended first, and the claimed set changes.
- **Frank's D3 acceptance of V14 (b).** It changes no verdict word. It only makes the FAIL releasable.
- **Any change to a D2.4 path** (src/, schemas/, benchmarks/, the lock, `pyproject.toml` …). This means a new
  candidate, and every row is re-judged on its RC job. Finding A1's fix touches `benchmarks/`.
- **A new preregistered PTC family or SER settings, committed before any result, that passes (b1)–(b4).** It reopens
  V14 (b).
- **A measured aarch64 reactor run (Q1).** It removes a W21 does-not-establish item; it changes no clause.

## What these verdicts do not establish

- **No empirical validation of the reactor, and none of v0.1's synthetic chemistry.** W22 (c) is empirical
  validation of pure-component PR behaviour against reference equations of state, inside R-160's bands, and nothing
  more.
- **No optimality evidence of any kind.**
- **Portability of W21.** It rests on one machine (ref-x86-64), one environment, one thread, under shared load. The V
  rows rest on both architectures.
- **Agent behaviour on the v0.2 surface** (V17, V13 (e)).
- **Scientific or process-model review** of anything. Human sign-off is recorded separately and is not claimed.
- **Releasability.** This document gives the verdict words. The tag needs §7.3's twelve items, Frank's four answers
  and his dispatch.

## Limitations that must travel into the manifest and the release report

- The envelope ids in the table, per gate.
- Not in the envelope as limitation rows, and to be carried by this verdict and the notes until the envelope carries
  them (A1, A8):
  - W21's evidence is ref-x86-64 only; the reactor was never run on aarch64 (Q1);
  - real-reactor runs are opt-in, R3 and from one machine;
  - `external-subprocess-v1` is not a sandbox. This is stated in the `external_execution` axis, not as a row;
  - W21 (f4)'s four statements;
  - W22's N5 refusal and PR's liquid-volume and enthalpy-of-vaporization bias.
- V14 (b) FAIL, PTC experimental (L01), with ADR 0028's D3 acceptance still to be recorded.
- V13, V17 and W21 are BLOCKED on Frank's answers. No tag may be proposed on this document.

## Findings

- **A1 (must be resolved before a tag is proposed; the design lane's call).** Spec §4 rule 4 and Q1's default ("the
  envelope and the notes say so") are not met at C_α¹. The alpha envelope has no limitation row for the unmeasured
  aarch64 reactor run. Its `platforms` axis and L15 say "Linux x86-64 and aarch64" without excepting the reactor
  path. The harvest classes M02's `limitations[1]` ("real-reactor runs … one machine") as P, although a user on
  aarch64 can reach it. The envelope is a D2.4 path, so the remedy is a re-cut or an amendment. M07a.A50 cannot catch
  this, because the classification is itself the recorded judgement.
- **A2 (blocks a YES; needs an amendment by the `specifier`).** BLOCKED rows need a re-judgement after Frank answers
  (D2.2, M07a.A61). Table T6 requires each answer to be dated on or after the verdict's Judged date. A re-judgement
  that reads the answers has a Judged date no earlier than theirs, so only an answer and a re-judgement on the same
  calendar day satisfy both rules.
- **A3.** M07a.A61's expectation ("V17 `BLOCKED` unless Frank's carry is recorded") omits V13 (e), which MR-7 places
  under the same carry.
- **A4.** §9.2 step 4 and §18.5 action 6 make `tested` conditional on A00–A53 passing. §9.2 step 5 writes A52's
  section after the verdict, so A52 (c) cannot pass first. Read here in substance.
- **A5.** The draft `## v0.2.0a1` section (`CHANGELOG.md` at `70c526e`) has two defects:
  - it lacks W21 (f4)'s item 4, the discretization bias of 1.0–1.4 % in NH₃;
  - its "Rights" bullet says the 4TU dataset's use awaits Frank's statement, whereas the dossier at C_α¹ records his
    statement of 2026-10-02 that it may be used and referenced. Spec §6.1's F-α4 paragraph carries the same stale
    sentence.

  A52's tests check neither.
- **A6.** No step-12 record audits G11's experiment results for §9.1's six items. A later RC could keep and check them,
  as R-348 did for certificates.
- **A7.** Step 1's skips rose from 11/8 to 100/98, mostly because CI runs on the public repository without the
  archived history (R-150). The CI logs give no skip reasons. Running `pytest -rs` would make the skip set a record
  rather than this verdict's inference.
- **A8.** Two of W22 (d)'s five stated gaps (M02 N5; PR's liquid-volume and enthalpy-of-vaporization bias) have no
  envelope row.
- **A9.** At step 12 the G11v3-4 timeout rule gives 270 s for V5 under that run's load. The registered value is 450 s
  (D104, heavier load). The registered value governs. The rule's dependence on host load is §14.5 D4's, recorded and
  not corrected.
- **A10.** Spec §6.1's W21 (b) table quotes M01's probe half for G10 (e) (2.98 × 10⁻⁸). The adapter's figure at step 12
  is 3.84 × 10⁻⁸. Both are within 10⁻⁷, so the verdict is unaffected.
- **Build-lane choices noted:** B-AM2-6 (C_α¹ on its own branch, reachable from this one), B-AM2-9 (certificate paths
  without the ignored segment) and B-AM2-10 (byte-identical bundle, live and replay certificates; multiset hash tests).
  None affects a verdict.
