# V03 — verdicts on V11–V20, W21–W26 and X31 for `0.3.0`

**Release candidate:** `a3e508e35fc5451fe56fa7b70941621992d35b50`   **Judged:** 2026-10-30   **By:** design lane (`verdict`)

*WO-7 of the V03 release specification (`docs/derivations/V03-release-spec.md` §10.2, as amended by Amendments 1 and 2).
Seventeen claimed gates, judged at C. W27 is not claimed (`v0.3-gate-v1`) and has no row.*

| Gate | Verdict | Failing clauses | Travelling limitations | Basis |
| --- | --- | --- | --- | --- |
| V11 | PASS | — | L38 | T08 §4.1 with MR-10; at C: K06, T01, T06 and T07 nodes, T08.A10, T08.A35 and M07a.A42 green in step 1 on both architectures (CI dispatch 41108983463: `check.sh: PASSED`, 17856 and 17826 passed, 107 skipped each) |
| V12 | PASS | — | L02, L26, L27, L28, L29, L30, L-CSTR-1, L-CSTR-2, L-CSTR-3 | T08 §4.2, denominator unchanged (alpha spec §5.1; the v0.3 units are not in it); T05, T05b and build-first B10–B19 nodes green in step 1 on both architectures |
| V13 | BLOCKED | V13 (e): Frank's `V17 carry` answer in ADR 0053, pending | L10, L22, L23, L24, L36, L38, L43, L-WS-1, L-WS-2 | T08 §4.3, T08.A71 and MR-7; T01, T02, K03 and B40–B49 nodes green in step 1; B50's counterpart: content by M07a.A51 in step 1, digest and schemas by the chain (step 8, three hosts, LINKS unchanged since 0.2.0); the carry under which MR-7 places them is asked again per release (ADR 0053 D2) |
| V14 | FAIL | V14 (b) | L01, L08, L20, L21, L43, L-COL-10 | T08 §4.4; T08-verdict-V14b.md (PTC-R1: the saddle clause fails on both registered platforms), unchanged at C: no PTC, homotopy, globalization or continuation source changed since 0.2.0's candidate and no PTC family or SER settings preregistered since (checked); Frank's D3 acceptance in ADR 0053 pending; typed homotopy and the three recovery edges: T04, T02 and T08.A33 nodes green in step 1 |
| V15 | PASS | — | L02, L14, L19, L20, L33, L-COL-5 | T08 §4.5; T02, T03 and T06 (ADV-05, THM-09) nodes green in step 1 on both architectures; all five step-12 certificates carry uniqueness and dynamic stability NOT_ASSESSED (checked here) |
| V16 | PASS | — | L16, L17, L18, L32 | T08 §4.6; T06 verdict 1 stands; T08.A48 12 of 12 at C on ref-x86-64, ci-x86-64 and ci-aarch64 (step 7) |
| V17 | BLOCKED | V17 (a): Frank's `V17 carry` answer in ADR 0053, pending | L11, L12, L13 | T08 §4.7 with MR-1, MR-2 and MR-6; V03 spec §3.3 at step 8 on three hosts: served digest 455d01eb…e125 = D_3, chain rows exactly (1,c_3), (2,c_3), (2,c_2), (2,c_1), (3,None), giving 383b4e2c…, 6c4375b4…, 171dd768… and, with v17-c2's texts, 6d13e13d…; 17 tools and files as registered; G16-b 40 of 40 clean |
| V18 | PASS | — | L03, L05, L06, L15, L19, L25, L34, L37, L39, L40, L41 | T08 §4.8 with MR-11, and MR-12 as V03 spec §9.3 restates it for the extras new since 0.2.0; T08.A30 PASS on three hosts (244 modules walked, 241 imported, the three registered nlp-extra modules refused as registered; required closures 150, 150, 147, none undispositioned); step 17c: `coolprop` and `lca` each with its entry and its check passing at C; T08.A34 0 violations on every audited set (step 10); T08.A31–A33 nodes green |
| V19 | PASS | — | — | T08 §4.9; ADR 0022 Accepted with Frank's selection (R-145); `docs/v02-real-chemistry-dossier.md` and `benchmarks/t08/v19/` byte-identical to 0.2.0's candidate (git diff ce993651..C empty, checked here); the A60–A64 record tests green in step 1 |
| V20 | PASS | — | L04, L07, L09, L31, L32, L38 | T08 §4.10; T08.A46 S = 437 of 440 on ref-x86-64 and ci-aarch64 (gate 418), no crash or other-root, same-class replay 25 of 25; T08.A47 12 of 12 on three hosts, worst success ratio 0.0968; T08.A10 node green |
| W21 | FAIL | W21 (e) | L05, L06, L07, L15, L19, L20, L44, L45, L46, L48 | alpha spec §6.1 (ADR 0028 D7); step 12 at C: G10v3, G11v3 and G12 met, reproduce MATCH; but G11's experiment results that step 12 wrote were neither kept nor audited for blueprint §9.1's six items, the evidence 0.2.0's re-judgement rested on (absent at C, owed by the lanes); out-of-process clause also waits on Frank's `M02 N1` answer in ADR 0053, pending |
| W22 | PASS | — | L42, L47 | alpha spec §6.2; step 1: M01.A05–A22, A34, A37 and M02 G7, G8 nodes green on both architectures; step 11: crosscheck recomputes byte-equal, IDAES re-run numbers identical (one input hash differs, as registered); step 12: G12 VERIFIED on the route |
| W23 | PASS | — | L49 | M07 §7.3 and M04 §15: A01–A30, A34, A35 green in step 1; step 13 at C: `m04_reference.py --check` 11943 claims, schema fixtures exit 0, 677 M04 and manifest tests passed, none skipped |
| W24 | BLOCKED | W24 (a): Frank's `M03 N1` answer in ADR 0053, pending | L19, L44, L46, L48, L49 | M07 §7.3; step 14 at C in the audited nlp environment: nlp tier 190 passed over the 13 modules that carry the marker (the same 190 node ids as over the whole test tree, V03.A33), inventory check exit 0 for both workloads, M03 and M05 tiers 640 passed and 2 skipped (the default-install answers), M05's REAL record replays with 0 differences, `m03_reference.py --check` exit 0 |
| W25 | PASS | — | L44, L45, L46, L48, L49 | M07 §5 on the journey record of J = 2d945b5d (V03 spec §3.4, R-908): step 15 at C carried, `check: ACCEPT`, `replay: bitwise`; decision refined at 653.1500351610193 K at the lower bound, TC-1 holds; R1 36 of 60 cold, R3 48 of 400 cold, none exhausted |
| W26 | PASS | — | L-WEB-1, L-WEB-2, L-WEB-3, L-WEB-4 | M07 §7.3 with (a) as V03 spec §3.5 restates it (R-903): V03.A32 4 of 4 at step 16 (662 passed with the browser required, 0 skipped; node 92 of 92; the 25 named nodes once each and clean; the dry run's exact W27-R63 refusal, exit 1, no summary file); (b) the CI x86-64 check exports the browser requirement and skips no browser node. G14 not judged at 0.3.0: W27 registration v1 refuses this build (ADR 0050 D9, W27-R63); W27 not claimed |
| X31 | FAIL | X31 (c) | L-COL-1, L-COL-2, L-COL-3, L-COL-4, L-COL-5, L-COL-6, L-COL-7, L-COL-8, L-COL-9, L-COL-10 | V03 spec §3.2 as pre-registered; RC1–RC4 and their registered matches, and the invalid-specification and phase refusals, green in step 1 on both architectures; S09 verdict 3: "met where available, 3 of 4" (RC4, the refluxed absorber, has one independent reference, BioSTEAM), which §3.2 registers as the failure of the reference clause; Frank's D3 acceptance in ADR 0053 pending |

## Read this first

**The seventeen.** Eleven PASS (V11, V12, V15, V16, V18, V19, V20, W22, W23, W25, W26). Three FAIL: V14 on clause (b)
and X31 on clause (c), both pre-registered and each with its D3 row in ADR 0053; and **W21 on clause (e)**, which is
not pre-registered and has no D3 row. Three BLOCKED (V13, V17, W24), each on one answer only Frank can give. No YES is
possible from this document as it stands: ADR 0053 D2 refuses a `BLOCKED` claimed gate and refuses W21's `FAIL`.

**W21 (e) is the one surprise, and it repeats 0.2.0's.** The alpha spec §6.1, W21 (e), bullet 2, reads: "Every
experiment result record that step 12 writes carries blueprint §9.1's six items, in the fields of
`experiment.schema.json`." At 0.2.0 this verdict's predecessor found exactly this evidence missing (V02 finding F1),
judged W21 `FAIL` on (e), and passed it only after the build lane re-ran G11 at C′ with each point's store kept and
audited 210 results and 210 attempts (`docs/v02-rc-record.md` l.126; `scripts/m07_g11_experiments_audit.py`). V03's
§4 carries "the alpha spec §8.2 steps 1–12, read as in M07 §8" and not that keep-and-audit, so C's step 12 ran G11
through temporary stores again and kept nothing (checked: no `step12/experiments/` in `rc/records.json` or in the RC
worktree's artifacts; `rc-step12.json` has six checks and none is the audit). Evidence the lanes were to produce and
did not is `FAIL`, never `BLOCKED` (T08 §3.3). In the vocabulary of evidence it is *insufficient evidence*: nothing at C
shows a record lacking an item, and nothing at C shows the 210 records carrying them. The registered form has no such
word, so it is written `FAIL`. The repair costs about half an hour of local compute in the reactor environment and no
money; it changes no D2.4 path, so C stands (see W21).

**Against 0.2.0's verdicts** (`docs/reviews/V02-verdicts.md`, C′ = `ce99365`, re-judged 2026-10-20):
- V13, V17 and W24: PASS → BLOCKED. ADR 0053 D2 carries no acceptance from 0.2.0; Frank's `V17 carry` and `M03 N1`
  are asked again for 0.3.0. The evidence each waits behind holds at C.
- W21: PASS → FAIL on (e), for the reason above; (c) waits on `M02 N1` again for the same reason as V13 and V17.
- V14 stays FAIL on (b). X31 is new and FAIL on (c) exactly as V03 §3.2 pre-registers it.
- W26 PASS under §3.5's restated (a) (0.2.0 judged M06 G1–G15; 0.3.0 judges G1–G13 and G15's registered content, not
  G14). W27 is not claimed.
- Every other row keeps 0.2.0's verdict, each re-judged on C's own records.

**Standing.** This is an agent verdict, numerical and procedural only. It is not scientific review and not a
process-model sign-off. It sets no `reviewed`, claims no human sign-off, and moves no tolerance, band or classification
rule. Human sign-off is Frank's and is recorded separately.

**Criteria, read before the evidence:** V03 spec §2–§4, §3.1–§3.5, §7 (A20–A24, A32, A33), §9.3, §10.2, §11 and §12;
the alpha spec §4–§6 with §19 (incl. §19.2 and §19.6), T08 §3.3 and §4; M07 spec §5, §7.3 and §8 [A6], [A7]; M04 spec
§15 (W23); ADR 0053 as it stands (all six cells empty); the register entries R-375, R-450, R-485, R-624, R-900, R-902,
R-903…R-908.

**Precondition.** S13's manifest is written after this document (spec §10, WO-8), as M07's was for 0.2.0. The step
records are the evidence; the twenty packages' manifests are evidence about their own commits and count only through
the RC job (alpha spec §4 rule 3).

## Frank's answers each row waits on (ADR 0053, `docs/adr/0053-v0.3.0-release-policy.md`)

All six cells are empty at C and at `bb51ed75`. Under ADR 0053 D2 and Tables T6/T7 (alpha spec §7.2, §19.2), an answer
counts only if it starts `accepted, YYYY-MM-DD`, dated **on or after the `Judged` date in force**, which is 2026-10-30
here and moves if W21 is judged again (see Sequencing).

| Row (verdict, clause) | ADR 0053 table and item | What a counting answer looks like | What it does |
| --- | --- | --- | --- |
| V13 BLOCKED, clause (e) | decisions, `V17 carry` | `accepted, <date>`, Judged ≤ date ≤ the re-judgement's date | unblocks (e); expected met, since M07a.A37 and A51 hold at C |
| V17 BLOCKED, clause (a) | decisions, `V17 carry` (the same answer) | as above | unblocks (a), as above |
| W24 BLOCKED, clause (a) | decisions, `M03 N1` | as above | unblocks (a), whose evidence (step 14) is otherwise met |
| W21 FAIL, clause (e); clause (c) waits too | decisions, `M02 N1` | as above | unblocks (c) only. W21 stays `FAIL` until (e) is measured and judged again |
| V14 FAIL, clause (b) | D3, row `V14 (b)` | `accepted, <date>`, date ≥ Judged | changes no verdict word; makes the FAIL releasable (D2) |
| X31 FAIL, clause (c) | D3, row `X31 (c)` | `accepted, <date>`, date ≥ Judged | changes no verdict word; makes the FAIL releasable, with the notes' phrase 13 |
| no row (gate item 11) | decisions, `Claim set` | `accepted, <date>`, date ≥ Judged | confirms the claim set judged here (seventeen; W27 not claimed) |

**Sequencing.** §19.2 item 2: a re-judgement may list only gates `BLOCKED` on a registered answer. W21 is `FAIL` on
evidence the lanes owe, so its change after the G11 audit is a **new judgement**, with a new `Judged` date, and every
answer must then be dated on or after it. The cheapest order is 0.2.0's: the audit first, then W21 judged again (new
`Judged`), then Frank's six answers, then one re-judgement line listing V13, V17, W21 and W24.

Choosing an alternative or declining is not an acceptance (alpha spec §7.3 item 11): a new V17 campaign, a declined
`M02 N1` or `M03 N1`, or a different claim set each needs a spec amendment, not a D3 row. **Do not route W21 (e) to the
D3 table:** accepting a missing provenance audit that costs half an hour of free compute is the "PASS with waiver"
ADR 0021 rejects.

## Evidence and provenance

| Evidence | Produced by, where | Independent expectation | Class |
| --- | --- | --- | --- |
| RC record `docs/v03-rc-record.md` (records commit `0caf09a0`) | build lane: local `ref-x86-64`, detached worktree at C clean at start, after the venv, after the W27 archive's links and at end; `tools/run_local.sh`, 65 commands, every exit 0 except the two Amendment 2 registers (step 14's collection over the whole tree, exit 2; step 16's dry run, exit 1); threads pinned. CI dispatch 41108983463 | none: the record reports and judges nothing. Its run ids and conclusions were not re-queried here; the committed job logs name run 41108983463 and commit `a3e508e3…` (read here) | record |
| The 103 records it hashes (`rc/records.json`) | as above; three gzip-compressed | **recomputed here: 103 of 103 SHA-256 and byte counts equal** (gzip ones decompressed); every one of the record's 99 distinct 64-hex tokens is in `records.json` | provenance |
| Provenance of the `t08-rc-v1` records | the records themselves | checked here: all 37 carry `commit` = C and `tree_clean` true; every check reads `pass`; every record but the bundle index (whose format has no `passed` member; 52 entries, all exit 0, as at 0.2.0) reads `passed: true` | provenance |
| C's ancestry and D2.4 | git | checked here: K3 `295a2e65` and J `2d945b5d` are ancestors of C; `git diff --name-only 295a2e65 C` over the D2.4 paths lists only the 36 G10 records under `benchmarks/m05/records/` and the 12 files of `benchmarks/m07/journey/2d945b5d…/` (R-908); src since S13a's pass (`0ce3748a`) differs only in `__version__` | provenance |
| Step 1: x86-64 17856 passed, 107 skipped; aarch64 17826 passed, 107 skipped; 197 deselected each | CI 41108983463 `check` jobs | summary lines and `check.sh: PASSED` grepped here from the hash-pinned job logs | tested (CI) |
| Step 1's skip set (R-376) | `evidence/S13/<C>/step1-skips/ci-x86-64.txt` (69 lines), `ci-aarch64.txt` (73 lines) | classified here (skip audit below); totals 107 and 107 | record |
| Steps 2–10 | as in the RC record | registered values: R-149's identity digests; D_0…D_3 and R-137's digest with LINKS read at C (unchanged since `ce99365`); S_min 418; A34's rule | ci, tested, record |
| Steps 11–17 records `stepNN/rc-stepNN.json` | local; step 12 in the reactor environment from C's lock (`032a050c…`), one thread; step 14 in m05's audited nlp environment under `env -i` in a second clean worktree | per step as cited below; every check `pass`, commit C, tree clean (read here); the junit files re-counted here (step 13 677/0/0/0, step 14 190 and 642 with 2 skips, step 16 662 with 0 skipped, 17b 4174 with 0 skipped, 17d 44 and 27) | numerical verification against registered records; regression of the group's model (12, 15) |
| G11's experiment results at C | written by `g11_coverage_v3.py` into temporary stores, deleted at exit | **none kept**; the committed `step12/g11-coverage-v3.json` holds per-point summaries, not result records (read here); step 12's runs file exists in the RC worktree's artifacts and is not committed | **absent** (W21 (e)) |
| Journey record `benchmarks/m07/journey/2d945b5d…/` | build lane at J, clean worktree, m05 nlp environment, `OMP_NUM_THREADS=1` | step 15 at C: carried, `check: ACCEPT`, `replay: bitwise` (records read here); the record's rungs, pairs, TC-1 and accounting read here | numerical verification of a workflow; record |
| The twenty packages' manifests | build lane at their own commits | checked here: each of M01–M06, S01–S12 (S08b, S10c included) has a `tested` manifest at an ancestor of C | evidence about other commits (rule 3) |
| Required ADRs | `docs/adr/` at C | read here: 22 of the 25 Accepted; 0050, 0051, 0052 Proposed (condition V03.A24, which now holds); 0053, 0054 Proposed (WO-8); 0043 Proposed and not required | decisions |
| ADR 0053's cells and Frank's statements (R-145, R-450) | recorded by the lanes | none: the authority's decisions | decisions |

**What pins nothing.** Step 12's walls, G11's 1755 s and the journey's walls were measured under whatever load the host
carried; they gate nothing. Regenerated self-consistency (a record recomputing to the same bytes) shows determinism, not
correctness. The A12 (c) counterfactual (below) explains a digest difference; it is not a measurement at C.

---

## V11 — PASS

(a) semantic diff, (b) immutable drafts, (c) task-specific validation, (d) units and component/reference checks: met by
the T07, K06, T01 and T06 nodes in step 1 on both architectures. (e) a real migration fixture: met by T08.A35 and MR-10's
counterpart M07a.A42 in step 1. T08.A10 green. Same verdict as 0.2.0. **Does not establish:** migration of arbitrary old
documents; structural checks are generic (L38).

## V12 — PASS

Every model of §14.3's list keeps its contract, limiting/failure, balance and derivative nodes, green in step 1 on both
architectures, and appears in a registered coupled case. The v0.3 models (columns, thermal units, the Wilson and CoolProp
bindings) are not in V12's denominator and are not judged by this row. **Does not establish:** the listed model
limitations; anything about the v0.3 units (their limitation rows travel in the notes).

## V13 — BLOCKED on V13 (e)

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) DM/SCC/BTF | met | T01 nodes in step 1 |
| (b) safeguarded recycle and coupled EO | met | T02 A13–A15, A32, A34 nodes; E1/E2 library-level (L43) |
| (c) scales before iteration | met | K03 and T02 nodes |
| (d) model initialization | met | as at 0.2.0 (K03 §10.1; L10) |
| (e) compatible warm starts | **blocked** | B40–B49 nodes green in step 1. B50's counterpart (MR-7): content by M07a.A51 (`tests/test_t08_b50_surface_content.py`, in neither skip file), digest and schemas by the chain, M07a.A37, 8 of 8 on three hosts. **Missing:** ADR 0053's `V17 carry` row ("V17, and T08.B50's surface"), empty |

**Does not establish:** that the v0.3 surface is acceptable for agents (Frank's carry decides that); warm starts beyond
exact id-set compatibility (L-WS-1, L-WS-2).

## V14 — FAIL on V14 (b)

- (a) typed homotopy: met (T04 A02–A12 in step 1).
- **(b) one PTC family qualified by §7.5: not met.** `T08-verdict-V14b.md`: the saddle clause fails on PTC-R1 on both
  registered platforms. Since 0.2.0's candidate no file under `src/` whose path names PTC, homotopy, globalization or
  continuation changed, and no register entry preregisters a PTC family or SER settings (checked). The PTC-R1 diagnostic
  nodes skip on CI x86-64 (no committed results for that CPU); they bear on (b2), and (b1) fails regardless. A column
  under a PTC policy is refused before any attempt (L-COL-10).
- (c) three bounded recovery edges: met (T02, T04, T08.A33 in step 1). Edge 3's trigger was narrowed under ADR 0044 D1
  (R-550, `orchestrator/recovery.py`); ADR 0044 is Accepted and its nodes are green.

ADR 0042's acceptance for 0.2.0 is not read (ADR 0053 D2). **Does not establish:** that PTC can never qualify (L01).

## V15 — PASS

(a) frozen phase attempts with restart (T03 A00–A26), (b) cross-unit promotion without nested SM (T02), (c) multiple
roots with honest branch reporting (T03, T06 ADV-05, THM-09): met in step 1 on both architectures. The five step-12
certificates carry uniqueness and dynamic stability `NOT_ASSESSED` and regularity `NO_RANK_LOSS_DETECTED` (read here).
**Does not establish:** root completeness, uniqueness or stability (L19); any uniqueness or multiplicity claim for a
column (L-COL-5).

## V16 — PASS

T06 verdict 1 stands; T08.A48 12 of 12 on three hosts at C. The tool side is not re-run (T08 §4.6). **Does not
establish:** IDAES agreement beyond the near-sharp ε (L16); the tools beyond their pins (L17).

## V17 — BLOCKED on V17 (a)

- **(a) blocked.** V03 spec §3.3 holds at C on three hosts: the served digest is D_3 = `455d01eb…e125`; the chain's rows
  are exactly `[(1,c_3),(2,c_3),(2,c_2),(2,c_1),(3,None)]` (read from `surface/rc-alpha-surface.json`), stripping to
  `383b4e2c…`, `6c4375b4…`, `171dd768…` and giving `6d13e13d…` with `v17-c2`'s texts; the 17 tools and description files
  as registered. `scripts/m07a_rc.py` `LINKS` at C is (c_1, R-192), (c_2, R-234), (c_3, R-295), byte-unchanged since
  `ce99365`, and ADR 0053's `V17 carry` default names exactly those three registers. **Missing:** Frank's answer, empty.
- (b) G16-b 40 of 40 over Python, CLI, HTTP and MCP: met on three hosts.

**Does not establish:** agent behaviour on the v0.3 surface; no V17 agent was run (L12).

## V18 — PASS

- **(a) met.** T08.A30 `PASS` on ref-x86-64 (266 objects, closure 150), ci-x86-64 (266, 150), ci-aarch64 (232, 147); no
  undispositioned object in a required closure; METIS not reached. The workload walks 244 modules and imports 241; the
  three refused are exactly {greybox: cyipopt, projection: pyomo, trf: pyomo} on all three hosts (F-3: the v0.3 modules
  import). MR-12 at 0.3.0 is V03 spec §9.3: every extra new since 0.2.0 has an entry whose check passed at C. Step 17c:
  `t07_licence_inventory.py --extra coolprop` pass, `e01_d04_inventory.py --check` pass, and `mr12_extras_v03` pass with
  `["coolprop", "lca"]`. The `nlp` extra keeps its 0.2.0 leg (the v02 measure at the 0.2.0 commit, R-450) and step 14's
  inventory check passes at C.
- (b), (c) met: T08.A34 0 violations over 77 locally (steps 2, 6, 8 and step 12's five), on each CI host, each clean
  install and the bundle set (step 10); T06 A33 0 in step 6.
- (d) met: T08.A33 in step 1.

**Does not establish:** the extras' closures beyond their audits (the `nlp` audit is linux x86-64 only); licence
acceptance by Frank of `coolprop` and `lca` (finding F4); certificate locality (L19).

## V19 — PASS

(i) ADR 0022 Accepted with revision 1; (ii)–(iii) the dossier unchanged since 0.2.0 (git diff empty); (iv) T08.A61–A63
record tests green, `benchmarks/t08/v19/` unchanged; (v) T08.A64 green. **Does not establish:** any comparison with data.

## V20 — PASS

(a)–(c): T08.A47 12 of 12 on three hosts; nothing verified outside S3 (worst success ratio 0.0968); T08.A10 green. (d):
T08.A46 S = 437 of 440 on ref-x86-64 and on ci-aarch64 (F-FALSE-SUCCESS-CAUGHT 3 each, F-BUDGET 0) against 418; no
F-CRASH or F-OTHER-ROOT; same-class replay 25 of 25 `MATCH`. The replay set is 25 here and 28 at 0.2.0 because T06 A34's
set is each case's first start (22) plus every non-`SUCCESS` start (3 here, 6 at 0.2.0); the rule is unchanged
(`t08_rc.a34_replay_set`, read here). **Does not establish:** robustness beyond the nominal profile (L09);
out-of-sample performance (L32).

### Skip audit (step 1, R-376)

| Reason (file) | x86-64 | aarch64 | Clause input? |
| --- | --- | --- | --- |
| archived pre-0.1.0 history (R-150): `conftest.py` (33), `test_t07_evidence_manifest` (28), `test_t08_evidence_manifest` (5) | 66 | 66 | No (v0.1 history; as at 0.2.0) |
| W27 pinned archive absent (`test_m06_w27_coverage` 2, `_harness` 8, `_scorer` 16) | 26 | 26 | Covered: step 16 ran `tests/test_m06_*.py` at C with the archive present, 662 passed, none skipped; the 25 named nodes once each (junit read here) |
| `test_c2_openidaes450_split` (pinned archive absent) | 1 | 1 | No (the OpenIDAES-450 split; W27 is not claimed) |
| PTC-R1 diagnostics, no ci-x86-64 results (`test_t08_ptc_r1_diagnostic`) | 6 | 0 | No: the PTC clause fails regardless |
| M04 platform-bound: `test_m04_prewarm` (x86-64), `test_m04_quadratic`, `test_m04_schemas` (aarch64) | 1 | 2 | Covered: step 13 ran every `test_m04_*` node locally, 677 passed, none skipped |
| platform-bound fixtures: `test_k05_schemas`, `test_t06_w28_records` | 2 | 2 | No (as at 0.2.0) |
| aarch64 only: `test_k01_backend_dependency`, `test_t06_w13_f6` (2), `test_m06_browser_smoke` | 0 | 4 | No; the browser node runs on x86-64 (W26 (b)) |
| aarch64 only: S07's A31a (R-906) | 0 | 1 | Covered: A31b passes on aarch64, and A31a holds on x86-64 (V03.A24) |
| `test_e01_b_brightway` (`bw2data` absent) | 1 | 1 | Covered: step 17d ran E01's `lca` tier in its environment, 44 passed, none skipped |
| built-artifact checks needing a setuptools Python: `test_s05_envelope` (S05 A26/A31 (a)), `test_s07_registration` (S07 A29 (a)) | 2 | 2 | No clause of the seventeen; not measured at C on CI (observation O1) |
| `test_l01_records` (retrieval re-run not possible) | 1 | 1 | No (`pr-lib-v1` is library-only; ADR 0043 not required) |
| `test_t08_w1_ledger` ("not in A02") | 1 | 1 | No |

Totals 107 and 107. No clause judged here rests on a node skipped at every place it could run. Step 1 has no ledger
skips at C: the v0.2 ledger module judges 0.2.0's document, which exists, and no v0.3 ledger module exists, so M07 §8
[A6]'s four skips have nothing to apply to (observation O2).

---

## W21 — FAIL on W21 (e)

Judged by the alpha spec §6.1 as ADR 0028 D7 reads it (V03 spec §3.1: unchanged). Every number is the group's model at
the pin, a regression. Step-12 values were read from C's records.

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) port mapping | met | M01 and M02 G4, G8, G9 nodes in step 1 on both architectures; G10 (h) 1.43 × 10⁻⁸ against 10⁻⁶ |
| (b) accuracy contract | met | G10 (b) 1.56 × 10⁻⁸ (10⁻⁶), (e) 3.84 × 10⁻⁸ (10⁻⁷), (f) 5.06 × 10⁻⁵ (10⁻³); G12 floor ratios 65.3 (ξ) and 13.3 (T) against ≥ 10 |
| (c) out-of-process execution policy | **waits on M02 N1** | G3–G5 nodes in step 1; `docs/support-matrix.md` at C states `external-subprocess-v1`, "not a sandbox", "Linux is registered", "Windows is refused before spawn" (checked). Missing: Frank's `M02 N1` answer in ADR 0053, empty |
| (d) timeout | met | G3 (b) in step 1; the registered variant's timeout governs (R-378); G12 CONVERGED in 4 outer iterations; G11v3 met, `G11v3-4_selected` V5 |
| (e) provenance | **not met** | G6 nodes in step 1; G12's results sit in its coupling record, schema-checked by `reproduce` (`MATCH`, bitwise floats); reactor commit `6089593…` = ADR 0022's pin (`env_manifest.commit`). **G11's experiment results were neither kept nor audited at C** (below) |
| (f) parent-model validation | met (verdict half) | (f1) G10 (g): A47 (a) bitwise; (f2) T08.A61 in step 1; (f3) the grid study, G10 (b), G10 (i); (f4) stated here: the group's published comparison (Gargiulo et al. 2025 §3.1) is the group's evidence; this project compared no reactor result with data; the numbers are a regression of the group's model; discretization bias 1.0–1.4 % in NH₃ (L46). **The notes' half is not readable at C:** the draft `## v0.3.0` carries none of the four statements (finding F3). It is read in the section the candidate carries, at W21's next judgement |

**(e): criterion, and why it is not met.** Alpha spec §6.1 W21 (e) bullet 2: "Every experiment result record that step
12 writes carries blueprint §9.1's six items, in the fields of `experiment.schema.json`." 0.2.0's re-judgement fixed what
that covers: the 105 boundary points per G11 run each write one experiment result (210 over two runs), the 32 direct
evaluations write none, and "the registered denominator is the 210 experiment results" (`docs/reviews/V02-verdicts.md`,
"(e): the criterion, the production"). Step 12 at C ran G11 again (two runs, 121 points each, 1755 s) through the same
frozen script (`benchmarks/m02/g11_coverage_v3.py`, byte-identical to 0.2.0's candidate), whose boundary points write
their results into `tempfile.TemporaryDirectory` stores that are deleted at exit. Nothing at C records them.

Three readings were considered and rejected (alternatives 1–3 below): that the alpha's exemption applies (it was scoped
"at the alpha", R-375); that 0.2.0's audit carries to C (no registered carry; V03 spec §3.1 last paragraph and alpha §4
rule 3); and that field presence is structural (rejected at 0.2.0 as alternative 3). What remains is the plain criterion,
unevidenced at C.

**Why FAIL and not BLOCKED.** (e)'s missing input is evidence the lanes were to produce (T08 §3.3). (c) alone would make
W21 `BLOCKED`; (e) makes it `FAIL` whatever Frank answers.

**The smallest measurement that settles (e).** At C, in the reactor environment built from C's lock:
1. Commit step 12's original G11 runs file (`step12/g11-coverage-v3.runs.json`, present in the RC worktree's artifacts,
   not yet in `records.json`) first, so that the re-run is compared with a record written before it.
2. Re-run step 12's G11 with the command of `tools/run_local.sh` l.94–97 through 0.2.0's `tools/g11keep.py.txt`, which
   keeps each point's store; collect each run's records (`tools/g11collect.py.txt`).
3. Commit the collected records under `evidence/S13/<C>/rc/step12/experiments/` (gzip over 1 MB, listed in
   `records.json`); add the audit's row to the RC record.
4. Run `scripts/m07_g11_experiments_audit.py --variant-file benchmarks/m02/variant-v3-provisional.json --runs <the
   re-run's runs file> run1.json run2.json` and require exit 0 over 210 results and 210 attempts, 0 problems.
5. Check, as 0.2.0's verdict did, that the re-run's per-point `stage`, `accepted`, `child_accepted`, `tube_outlet` and
   `path` equal step 12's runs file over all 242 point-runs, and that the (label, path) multiset of the collected records
   equals it (210 boundary, 32 direct). This closes the audit's own gap (V02 finding F8: it takes the boundary/direct
   split from the records' labels).

No D2.4 path changes, so C stands. Then W21 is judged again in a new judgement with a new `Judged` date, and it is
expected `BLOCKED` on (c) only, if (f4)'s statements are in the notes by then.

**W21 does not establish:** that the reactor is right (L46); any aarch64 run or cross-machine reproduction (L44, L15);
a sandbox (L45); sensitivities or optimization through the reactor; coupled-loop convergence beyond one loop, two edges
and G11's corners and centre (L48); timings under other load.

## W22 — PASS

(a) numerical verification: M01.A05–A22 against closed forms and M01.A34 (`--check`) in step 1. (b) conformance: M01.A37
in step 1; step 11's IDAES re-run numbers equal `benchmarks/m01/idaes-conformance.json`'s (only
`inputs.reference_values_yaml_sha256` differs), re-run file `7e1d41dd…` as at 0.2.0. (c) empirical validation of
pure-component behaviour against reference equations of state: step 11's `external_crosscheck.py --check` recomputes the
record byte-equal, so the ratios stand (0.012675 against 0.02; 0.040096 and 0.042371 against 0.05). These are R-160's
validation bands, not tolerances, and this verdict does not turn them into a confidence statement. (d) sufficiency: G7,
G8 in step 1; G12 binds every evaluation to `pr-c1-v1` and ends `VERIFIED`. **Does not establish:** mixture VLE; k_ij
effects beyond R-157; the near-critical region; liquid-density fitness (L47); anything outside M01's domain.

## W23 — PASS

| Clause (M04 §15 row) | Judgement | Evidence at C |
| --- | --- | --- |
| (a) conservation | met | A13, A26 in the default gate (step 1, both architectures; step 13 locally) |
| (b) domain | met | A03, A14, A15; A31 recorded |
| (c) derivative | met | A12, A17; A31 recorded |
| (d) default UQ | met | A04–A08, A16–A24; A31, A32 recorded |
| (e) insufficient data | met | A07, A11, A20, A21 |
| (f) frozen splits and transforms | met | A01, A02, A23; A32 recorded |
| (g) promotion and rollback | met | A25–A30, A33 |

Step 13 re-checks M04's committed records at C: `m04_reference.py --check` 11943 claims, schema fixtures exit 0, 677
passed with none skipped (junit re-counted here). M04's manifests are `tested` at ancestors of C. Met on numerical
verification as M04 §15 states; the real verdict `NOT_PROMOTABLE` is recorded and by M04 N6 is not a W23 failure.
**Does not establish:** a promotable surrogate of the real reactor (L49); any coverage claim for the real surrogate.

## W24 — BLOCKED on W24 (a)

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) M03's fixed-topology NLP with final parent checks | **blocked** | nlp tier (A35–A42 among them) 190 passed over the 13 modules that carry the marker, the same 190 node ids as over the whole tree (V03.A33, R-907); inventory `--check` exit 0 for both workloads; audited environment (step 14). **Missing:** Frank's `M03 N1` answer in ADR 0053, empty |
| (b) TRF composition | met | M05 G2–G4, G13 in step 14's all-tier run (640 passed, 2 skipped: the two default-install answers, unobservable where Pyomo is installed; read here) |
| (c) TR-E2 with assumptions stated | met | M05 G5 in step 14 |
| (d) FD truth accuracy and real-reactor accounting | met | G6, G7 in step 14; G11's REAL record replays at C with 0 differences (`m05_wo9_real.py --replay`) |
| (e) parent checks and the refinement loop incl. the N6 branch | met | G8, G9 in step 14 |
| (f) constraints kept as constraints, limits stated | met | G7, G11 and the record content |
| (g) costs reported | met | the truth-ledger identities (G7 accounting) |

ADRs 0031, 0032, 0038, 0039 Accepted; M03 (`a35885b`) and M05 manifests `tested` at ancestors. **Does not establish:**
global optimality (the notes' phrase "no global optimality"); any optimization result on aarch64; that the bound-active
REAL decision says anything outside the box; capital sensitivities through E01's optimizer (L-E01-1, in prose: the
gate's limitation grammar cannot carry that id, finding F5).

## W25 — PASS

Judged on the journey record of J = `2d945b5d` (K3 plus the five re-taken G10 records; V03 spec §3.4, R-908), carried to
C by `--carry-journey 2d945b5d --rc C`. Step 15's three checks pass at C: "RC step 15: the journey at 2d945b5d carried",
`check: ACCEPT`, `replay: bitwise` (nlp environment, one thread).

| Clause | Judgement | Evidence (record at J, read here) |
| --- | --- | --- |
| (a) rungs | met | R0 `INDIFFERENT` (18 in-process, budget 0 cold); R1 `DECIDED` 653.15 K; R2 `SURROGATE_NOT_PROMOTABLE`, M04's verdict `NOT_PROMOTABLE` and reasons, 0 evaluations; R3 `DECISION_STABLE`, M05's study re-run at J (its REAL record not carried: `carry_identity_differs`, as §3.4 allows) |
| (b) before/after decisions | met | P01 `FE_CHANGED` (673.15 → 653.15 K), P13 `FE_UNCHANGED`; equality with the reference function by A22 and `check` |
| (c) constraints | met | bound activity `BOUND_LOWER` for R1, R3 and the journey's decision, bound phrase present; A23, A11 |
| (d) discrepancy | met | A20, A15 in the default gate; `check` |
| (e) uncertainty | met | A20, A21; R3's noise floor and indifference set in the record |
| (f) truth checks | met | TC-1 `TC1_HOLDS` (best grid T 653.15 K); the decision is a parent evaluation (A23, A26) |
| (g) compute cost | met | R0 0 cold; R1 36 of 60 cold, 1554 s of 5400; R2 0; R3 48 of 400 cold, 1455 s of 14 400; journey 88 of 460 cold, 3303 s of 21 600; none exhausted |
| (h) honest limits, reproducibility | met | step 15 at C: carried, `check: ACCEPT`, `replay: bitwise`; A10, A11 and the journey-record tests in step 1 |

Against 0.2.0's K record: WO-5 reports 69 differing leaves, all walls, digests, `commit` and R3's `m05_record`, every
other number bitwise equal (`docs/V03_RC_DECISIONS.md`, not re-run here). **Does not establish:** empirical validation;
global optimality; anything outside 653.15–693.15 K, including whether the objective improves below the lower bound
where the decision sits; reproduction on another architecture (R3, L44); the thirteen items of the report's §11.

## W26 — PASS

Judged by M07 §7.3 with (a) as V03 spec §3.5 restates it (Amendment 2, R-903). That reading is pre-registered; it is
applied here, not chosen.

- **(a) met: V03.A32 holds.** `step16/rc-step16.json` (step `w26-web-shell`) has exactly four checks, each `pass`:
  `a60.w26.m06_tests` (`tests/test_m06_*.py` with the browser required: 662 testcases, 0 failures, 0 errors, 0 skipped;
  re-counted here from the junit); `a60.w26.web_unit_tests` (node 92 of 92); `a60.w26.g15_registered_states` (each of the
  25 named testcases present exactly once with no failure, error or skipped child; re-checked here by class and name);
  `a60.w26.w27_v1_refusal` (exit 1; last non-empty line exactly
  `benchmarks.m06.w27.snapshot.SnapshotUnsupportedError: registry_snapshot: unsupported(provider 'iapws95-v1': no
  registered records and phases, W27-R63)`, re-read here from `step16-dryrun.log`; `summary_written` false).
- **(b) met.** The CI x86-64 `check` job exports `OPENFLOWSHEET_REQUIRE_BROWSER=1` (job log l.479, inside the
  `ubuntu-latest` branch of its `if`) and the x86-64 skip file has no browser skip.

**Travelling limitation (V03 spec §3.5), verbatim:** `G14 not judged at 0.3.0: W27 registration v1 refuses this build
(ADR 0050 D9, W27-R63); W27 not claimed`. It is not an envelope id, so it travels in the Basis cell and here, not in the
limitations column (finding F5); the notes' phrase 15 (`no W27 claim in 0.3.0`) covers it. **Does not establish:**
that the W27 harness can run a campaign on this build (G14, P3 and the stub campaign need a coverage of this build,
which registration version 1 refuses to build); the G15 states test the scorer's and harness's logic against 0.2.0's
committed rows, not this build's coverage; usability or accessibility beyond L-WEB-3; anything but the local single-user
security model (L-WEB-2).

## X31 — FAIL on X31 (c)

Judged by V03 spec §3.2, which pre-registers (c)'s reading. It is applied here, not chosen.

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) RC1–RC4 solve and their registered matches hold | met | S02's M1–M4 at `P_r`, and S03/S09's A10 (i) byte-identity and (ii) live-solve classifications, in step 1 on both architectures (no S02, S03, S09 module in either skip file); S02 manifest `1810dde8` `tested` at an ancestor of C |
| (b) invalid specifications and phase cases refused with their registered typed outcomes | met | S02's invalid-specification tests, S08's phases clause (R-736), S08b, S10c's column cases, all in step 1 on both architectures (none skipped); S08 `6d7d1a6d`, S08b `acbd1266`, S10c `2aedd250` and `8f38f963` manifests `tested` at ancestors |
| (c) S09's three-tool outcome "met with two references" | **not met** | `docs/reviews/S09-verdicts.md` verdict 3: **"met where available, 3 of 4"** (target 4). RC1 and RC2: three references; RC3: two (BioSTEAM, IDAES); RC4, the refluxed absorber: one (BioSTEAM; DWSIM and IDAES absent for the reasons S03 records). §3.2: any outcome other than "met with two references" is FAIL (c), stated in its registered words |

The outcome was unreachable by construction at S09 (RC4 can have at most one reference with the qualified tools) and is
releasable only by the D3 row `X31 (c)` (N-5), with the notes' phrase 13 (`X31: one independent reference for the
refluxed absorber`, present in the draft section). **Does not establish:** "met with two references" (R-643's watch
item); validation of any column against data (the SYN-001 columns are synthetic, L-COL-8); a reference for RC4 beyond
BioSTEAM at L2(c).

---

## Alternatives considered and rejected

1. **W21 (e) met because G11's results are not a verdict input (the alpha's reading).** Rejected. The alpha's text is
   "G11's experiment results are not a verdict input *at the alpha*", and R-375 says "At 0.2.0, step 12 keeps G11's
   results". Neither covers 0.3.0. What V03 §3.1 carries is §6.1's plain criterion, which 0.2.0's re-judgement read as
   covering the 210 G11 results. Narrowing it now would reverse that reading without a new decision.
2. **W21 (e) met by carrying 0.2.0's audit, since the producing code is byte-identical** (`g11_coverage_v3.py`, the
   experiments and pymrm adapters, the schema and the variant file are unchanged since `ce99365`; checked). Rejected:
   no registered carry covers it (V03 §3.1: only V17 by §3.3 and W25 by §3.4), and alpha §4 rule 3 admits evidence about
   another commit only through the RC job. The identity is a reason to expect the audit to pass, not the audit.
3. **W21 (e) met because field presence is structural.** Rejected, as at 0.2.0: structure shows the keys exist, not that
   each result carries the pinned variant, reactor commit, estimate and timing values.
4. **W21 `BLOCKED` on (e).** Rejected: the input is the lanes' to produce (T08 §3.3).
5. **W21 (f) not met on the notes' half.** Rejected for this judgement: the notes are drafted before the candidate and
   completed after this verdict (V03 §4: C's later commits hold `CHANGELOG.md` `## v0.3.0`), as at 0.2.0, whose verdict
   read the half at W21's next judgement. It is read there again; absent then, (f) is not met.
6. **V18 (a) not met because the `coolprop` and `lca` licence decisions are not Frank's.** Rejected under V03 §9.3,
   which registers R-624 and R-900 as those extras' decisions for 0.3.0's MR-12. The tension with the alpha's MR-12
   wording is finding F4.
7. **V13 and V17 PASS on ADR 0042's carry, or W24 on R-450.** Rejected: ADR 0053 D2 carries no 0.2.0 acceptance. R-450
   still serves V18 (a)'s `nlp` leg, which is MR-12's and not in `rejudge_waits` (0.2.0's finding F2, unchanged).
8. **W26 (a) on M07's literal "G1–G15".** Rejected: §3.5 pre-registers the restated reading, and N-10 is Frank's.
9. **X31 (c) "met with two references", or (c) met because RC4's single reference is all that exists.** Rejected: §3.2
   and S09 verdict 3. The twin shares SYN-001's closed forms and is not independent.
10. **No verdict because S13's manifest does not exist or because V03.A12 fails.** Rejected: as at 0.2.0, the manifest
    follows the verdict; A12 is a packaging assertion that no criterion of the seventeen names. It matters to the tag
    (gate item 8), not to the rows.
11. **V14 PASS on route (a), or V14 in a re-judgement.** Rejected (R-118; §19.2: V14 cannot be listed).

## What would change these verdicts

- **The G11 keep-and-audit under W21, committed at C and passing**, with the equality checks of step 5 → W21 (e) met in
  a **new judgement** with a new `Judged` date (§19.2 item 2); W21 then stands on (c), provided (f4)'s four statements
  are in the section. A result missing any of the six items → (e) stays not met, now on a record.
- **Frank records `V17 carry` and `M03 N1` as `accepted, <date ≥ Judged>`** → V13 (e), V17 (a) and W24 (a) are
  re-judged; expected met if their evidence still holds.
- **Frank records `M02 N1` accepted** → W21 (c) met at W21's next judgement or re-judgement.
- **A declined `M03 N1`** → W24 (a) not met, and V18 (a)'s `nlp` leg (R-450) is contradicted: V18 then needs a new
  judgement. A declined `M02 N1` or a new V17 campaign → a spec amendment.
- **Frank declining the `coolprop` or `lca` licences, if asked (F4)** → V18 (a) judged again on MR-12's decision leg.
- **Frank's D3 acceptances of V14 (b) and X31 (c)** dated ≥ the `Judged` in force → those FAILs become releasable; no
  word changes.
- **Frank choosing N-10's option 2** → W26 (a) FAIL on G14 and G15, releasable only with a D3 row `W26 (a)`, which needs
  an ADR 0053 amendment.
- **Any change to a D2.4 path** → a new candidate and a new RC job; every row judged again.
- **A record whose bytes no longer match its digest, a skipped node a clause rests on, a served digest other than D_3
  at a later candidate, or a new preregistered PTC family passing (b1)–(b4)** → reopens the clause concerned.

## What these verdicts do not establish

- **No empirical validation** of the reactor, the C1 loop, the journey's decision or any column; W22 (c) is
  pure-component PR against reference equations of state inside R-160's bands, nothing more; X31's references are
  numerical cross-checks between implementations, not data.
- **No optimality evidence**: the journey's and M05's decisions are bound-active at 653.15 K; nothing is claimed below it.
- **No portability** of W21, W24 and W25: one machine (`ref-x86-64`), one thread, R3. W26's harness half: one platform.
- **No agent behaviour on the v0.3 surface** (V17, V13 (e)); no W27 result for 0.3.0.
- **Nothing about the v0.3 packages beyond what their gate items and RC step 17 measured**: their own verdicts and
  manifests are evidence about their commits; the S11 thermal and Wilson bases, the CoolProp provider and E01's cost and
  LCA are judged by no row here except through X31's column cases and step 17's checks.
- **No scientific or process-model review**, and no human sign-off.
- **No releasability**: the tag needs the G11 audit and W21's new judgement, Frank's six answers dated as above, the
  ledger, S13's `tested` manifest (which V03.A12 currently prevents), ADRs 0050–0054 Accepted, the merged notes with
  (f4)'s statements, step 18's YES line, and Frank's dispatch.

## Limitations that must travel into the manifest and the release report

- The envelope ids in the table, per gate (reactor on x86-64 only, opt-in, R3: L44, L15; not a sandbox: L45; W21 (f4)'s
  four statements: L46; PR's liquid bias: L47; G11's corners and centre: L48; no promotable real surrogate: L49; the web
  shell: L-WEB-1…4; reference data and OpenIDAES-450 not distributed: L40; the column rows L-COL-1…10).
- The v0.3 rows the gate's limitation grammar cannot carry in the table (F5): L-S11-1, L-S11-2, L-S11-3 (the S11 bases,
  including the Wilson library constructors' checkout-only refusal, R-883), and L-E01-1 (P2's floored capital rows).
  The thermal and Wilson-unit rows L-TH-1…8 and L-GP-1…3 attach to no claimed gate and travel in the envelope and notes.
- V14 (b) FAIL, PTC experimental (L01), D3 acceptance to be recorded.
- X31 (c) FAIL, "met where available, 3 of 4"; RC4 has one independent reference (BioSTEAM); D3 acceptance to be
  recorded; the notes' phrase 13.
- W21 FAIL on (e) until the G11 audit at C; until then G11's provenance at 0.3.0 is unevidenced.
- W26: `G14 not judged at 0.3.0: W27 registration v1 refuses this build (ADR 0050 D9, W27-R63); W27 not claimed`.
- W24 and W25: no global optimality; the decision is bound-active at the lower bound (no envelope row; the notes' phrase).
- Step 12's and the journey's timings were measured on a possibly shared host and bound nothing.

## Findings

- **F1 (design lane; changes a verdict).** V03 spec §4 carries "the alpha spec §8.2 steps 1–12, read as in M07 §8"
  without R-375's keep-and-audit of G11's results, which 0.2.0's finding F1 found missing from M07 §8 in the same way.
  So C's step 12 again neither kept nor audited G11's results, and W21 (e) cannot be met. Remedy now: the measurement
  under W21, build lane, against R-375's stated checks plus the equality of step 5. Remedy for later releases: register
  the keep-and-audit as a standing part of step 12 (a design-lane amendment), or W21 (e) will fail at every release.
- **F2 (A12 (c); does not enter the rows).** See "V03.A12 (c)" below.
- **F3 (notes).** The draft `## v0.3.0` at C carries §8's seventeen phrases but none of W21 (f4)'s four statements
  (`no reactor result has been compared with experimental data`; `the group's published comparison is the group's
  evidence`; `the group's model at the pin, a regression`; `discretization bias is 1.0–1.4 % in NH₃`; each counted 0
  after whitespace normalization). V03 §8 and V03.A18 do not require them, so nothing in V03's procedure would put them
  there. They must be in the section before W21's next judgement.
- **F4 (MR-12's decision leg).** The alpha's MR-12 asks, for each new extra, "its own [A10] audit and Frank's recorded
  licence decision". V03 §9.3 registers R-624 (design lane, `specifier`; S07 §17.3 records "No question for Frank",
  resting on Frank's R-135 for numpy's GPL-family runtime, with CoolProp MIT) and R-900 (design lane, `reviewer`) as the
  `coolprop` and `lca` decisions. V18 is judged under §9.3, the registered 0.3.0 restatement. If Frank's own acceptance is
  wanted, it costs one line in WO-8's message beside N-4; a decline would reopen V18 (a).
- **F5 (gate grammar).** `v0_2_gate.LIMITATION` (`L(?:\d{2}|-[A-Z]+-\d+)`) does not match envelope ids whose middle
  part holds a digit (`L-S11-1…3`, `L-E01-1`), so those rows cannot appear in the Travelling limitations column, and
  §3.5's W26 limitation is a sentence, not an id. Both travel in prose here. A grammar change is the build lane's,
  under a design-lane ruling; not required by any rule read here.
- **F6 (RC record wording).** Step 8's local cell reads "c_3 (R-295) `455d01eb…`; served `383b4e2c…`". The record says
  otherwise and is right: the served digest is `455d01eb…` (item 1, D_3) and `383b4e2c…` is the digest after stripping
  c_3 (item 2). The cell should be corrected; no result changes.
- **F7 (tag path).** S13's manifest, once committed, is harvested (`HARVEST_EXCLUDED` is empty at C), and the decisions
  log records that an S13 manifest in the tree fails `test_m07a_a50…` and T08.A21. The harvest's classifications live
  in `benchmarks/t08/support_envelope.yaml` (S13a's are there, checked), so classifying any limitation or non-`pass`
  check of S13's manifest would change a D2.4 path and force a new C; even with none, `HARVEST_SIZE` moves (a test
  constant, outside D2.4). 0.2.0 excluded M07's own manifest instead (R-485, `scripts/t08_support_matrix.py`, outside
  D2.4). The same exclusion for `evidence/S13/` needs its own ruling before WO-8.
- **F8 (ADRs).** 0050, 0051 and 0052 are still Proposed at C. Their condition (V03.A24 at C) now holds (CI at C green on
  both architectures with S07 A31 and the S11 thermal classes as registered), so WO-4's route can mark them before
  step 18.

### Observations (not findings)

- **O1** The built-artifact checks S05 A26/A31 (a) and S07 A29 (a) skip on CI for want of a setuptools Python; step 17e's
  A17 covers the ship set and E01's data, not those two contents. No row rests on them.
- **O2** M07 §8 [A6]'s "four ledger skips" do not occur at C (see the skip audit).

## V03.A12 (c): the counterfactual (WO-2's packaging assertion; not one of the seventeen rows)

**Evidence read.** At C, `scripts/s11_identity.py` reports `S11-IDENTITY FAIL n=54494` with 47 family-C digests changed,
all binder calls of `tests/test_m04_wo{7,8,19,20}_*.py`. `git diff 0ce3748a C -- src` (read here) is one line:
`__version__ = "0.3.0.dev0"` → `"0.3.0"`. `adapters/experiments/backends.py` l.174 at C writes
`openflowsheet.__version__` into the in-process environment fingerprint, which enters the bound documents' digests. At C
with only `__version__` set back to `0.3.0.dev0` (orchestrator's run, logs `~/.cache/v03rc-a12-tmp/identity-cf2.log`
and `~/.cache/v03rc-a12-keep/`, last line read here): `S11-IDENTITY FAIL n=54494 changed=[] (C branch shards [1, 3, 7,
11] exited non-zero)`. The shard failures are exactly five tests (read here from the kept logs): `test_package_imports::
test_root_package_exposes_version`, `test_v02_main_version::test_the_envelope_matches_the_version`,
`test_m06_w27_coverage::test_snapshot_of_this_build_is_todays_registry`,
`test_t07_w5e_application_results::test_the_fixtures_are_what_real_responses_emit_today` and
`test_m07_journey::test_a21_the_carry_identity_is_the_determining_files_at_the_anchor_and_j`. Each reads the version or
hashes `src/**`.

**View.** Sufficient as evidence of cause; not sufficient to record V03.A12 as `pass` at C. The counterfactual is a
proper one-variable control: flipping the version alone takes the digest difference from 47 to none, and the five
failures are the tests that should fail when the version is wrong, which shows the edit took effect. Together with the
src diff it establishes that the 47 differences are the version string, build provenance in R-902's sense, and that no
binding outcome differs. But A12 (c) is a default-gate assertion at C, the registered measurement fails at C, and the
counterfactual's tree is not C (its own line also reads `FAIL`). Judging A12 (c) by a counterfactual, or excluding the
version from the identity tool's family-C comparison, changes how an assertion is judged. That is a design-lane
amendment with a register entry, as R-902 and R-904 were for the same class of difference, not a build-lane DECISION.
Until such an entry exists, S13's manifest records V03.A12 `fail` with this explanation and cannot be `tested`, which
blocks gate item 8 and ADRs 0053 and 0054. The cheapest route is a docs-only amendment extending R-902's principle to
`scripts/s11_identity.py` (outside D2.4, so no re-cut): either the counterfactual above as A12 (c)'s measurement at C,
or an excluded fingerprint member with a control and a fresh run at C.

## D3 rows and Frank's items after these rows

**D3 rows Frank must accept (confirmed as expected):**
- `X31 (c)`: release with S09's three-tool outcome "met where available, 3 of 4"; RC4, the refluxed absorber, has one
  independent reference (BioSTEAM). Default: accept (N-5).
- `V14 (b)`: release with PTC experimental; no PTC family qualifies (PTC-R1's saddle clause fails on both registered
  platforms). Default: accept (N-6).
- **Not a D3 row:** W21 (e). It is repaired by measurement, not accepted.

**N-items as they stand:**
- **N-2 (`V17 carry`)**: needed. V13 (e) and V17 (a) wait on it. The evidence at C supports the default: D_3 served,
  chain rows exact, LINKS unchanged, no new link.
- **N-3 (`M02 N1`)**: needed. W21 (c) waits on it. Accepting it does not make W21 releasable while (e) fails.
- **N-4 (`M03 N1`)**: needed. W24 (a) waits on it; it also keeps V18 (a)'s `nlp` leg (R-450) consistent.
- **N-5 (D3 `X31 (c)`)** and **N-6 (D3 `V14 (b)`)**: needed, as above.
- **N-10 (W26)**: this verdict applied option 1 (§3.5), as pre-registered; W26 is PASS on it. Option 2 would make W26
  (a) FAIL on G14 and G15 and needs an ADR 0053 amendment for its D3 row.
- **Timing**: ask after W21's new judgement, so that every answer is dated on or after the `Judged` in force.
