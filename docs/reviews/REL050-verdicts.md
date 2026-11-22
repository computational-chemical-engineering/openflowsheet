# REL050: verdicts on V11–V20, W21–W26 and X31 for `0.5.0`

**Release candidate:** `0a800e69f200e52dae7e5f3d2d56810bc8f10e27`   **Judged:** 2026-11-22   **By:** design lane (`verdict` agent)

*RP §4.7 and §9.2 step 3 (`docs/derivations/release-procedure.md`). Line `0.5` (`release/lines/0.5.json`, gate set
`v0.5-gate-v1`, claim set and `gates[*]` 0.4's unchanged), K3 = `8aaed3f2`, J = `3caa928c`, host SMM-TR09
(`ref-x86-64`; RP amendment A-13). Seventeen claimed gates, judged at C on C's records and on the two registered
carries that reach C: the journey from J, and V17 by Frank's `V17 carry` row of 2026-11-22. W27 is not claimed and has
no row. With D2 deferred every row is judged here. `docs/reviews/REL040-verdicts.md` was read for its form only; no
verdict is carried from it. In what follows C is `0a800e69` and `<C>` in a path is its full id.*

| Gate | Verdict | Failing clauses | Travelling limitations | Basis |
| --- | --- | --- | --- | --- |
| V11 | PASS | — | L38, L-X04-1, L-X04-2, L-X04-3 | T08 §4.1 with MR-10; K06, T01, T06 and T07 nodes, T08.A10, T08.A35 and M07a.A42 green in step 1 on both Linux legs (push run 45019680845: x86-64 21066 passed, aarch64 21034 passed, no failure; skips audited below, none a clause input) |
| V12 | PASS | — | L02, L26, L27, L28, L29, L30, L-CSTR-1, L-CSTR-2, L-CSTR-3 | T08 §4.2, denominator unchanged (alpha §5.1; units added since 0.1 are not in it); T05, T05b and build-first B10–B19 nodes green in step 1 on both Linux legs, none skipped |
| V13 | PASS | — | L10, L22, L23, L24, L36, L38, L43, L-WS-1, L-WS-2 | T08 §4.3 and T08.A71 with MR-7; T01, T02, K03 and B40–B49 nodes green in step 1; B50's counterpart: content by M07a.A51 green in step 1, digest and schemas by step 8's chain on three hosts through ten registered links, under the carry MR-7 names: Frank's `V17 carry` row (release/acceptances.md, accepted 2026-11-22 at C, "V17, and T08.B50's surface" across all ten registers; stands at C, fingerprint 9f4fb274…6615 recomputed here) |
| V14 | FAIL | V14 (b) | L01, L08, L20, L21, L43, L-COL-10 | T08 §4.4 with T08-verdict-V14b.md; measured at C: step 17's PTC-R1 item ran the registered comparison (case cfa994fe…) on both CI legs of dispatch 45019811148; PTC ends at the saddle (MID) from 149 of 441 starts on ci-aarch64 (a registered platform) and on ci-x86-64, recounted here from the raw records; typed homotopy and the three recovery edges: T04, T02 and T08.A33 nodes green in step 1; the standing acceptance row lapsed at C (src changed), so Frank's second message asks for it |
| V15 | PASS | — | L02, L14, L19, L20, L33, L-COL-5 | T08 §4.5; T02, T03 and T06 (ADV-05, THM-09) nodes green in step 1 on both Linux legs; the five kept step-12 certificates read uniqueness and dynamic stability NOT_ASSESSED (read here); step 10 audited 77 certificates, 0 violations |
| V16 | PASS | — | L16, L17, L18, L32 | T08 §4.6; T06 verdict 1 stands (`docs/reviews/T06-verdicts.md` unchanged since 0.4.0's candidate, git diff empty); T08.A48 (T06.A47 9 nodes, T06.A50 17 nodes) passed at step 7 on ref-x86-64, ci-x86-64 and ci-aarch64, none skipped |
| V17 | PASS | — | L11, L12, L13 | T08 §4.7 with MR-1, MR-2 and MR-6, and RP §4.4 (amendment A-12); Frank's `V17 carry` of v17-c2's agent evidence across R-192, R-234, R-295, R-934, R-950, R-960, R-1000, R-1010, R-1030 and R-1051 (release/acceptances.md, accepted 2026-11-22 at C; stands at C, fingerprint 9f4fb274…6615 recomputed here); step 8 on three hosts, chain rows exactly (1,c_10), (2,c_10) … (2,c_1), (3,None): served digest f7ec3c94…d467 equals the last registered link's (R-1051), each strip in turn gives e2c44b6b…, 6be1c002…, 553b7612…, 3fdc797a…, f51b69bf…, eaff4585…, 455d01eb…, 383b4e2c…, 6c4375b4… and 171dd768…, and with v17-c2's texts 6d13e13d…; tools and description files as registered; G16-b 40 of 40 clean on three hosts |
| V18 | PASS | — | L03, L05, L06, L15, L19, L25, L34, L37, L39, L40, L41 | T08 §4.8 with MR-11 and MR-12; T08.A30 PASS on three hosts (353 modules walked, 348 imported, the five nlp-extra modules refused as registered; required closures 150, 150, 147; nothing undispositioned; METIS not reached); no extra new or changed since 0.4.0 (pyproject optional-dependencies identical, checked here), their licence rows stand (coolprop and lca licences, M03 N1); step 17's MR12-coolprop and MR12-lca items pass; T08.A34 0 violations over 77 certificates (step 10, and on every CI leg); X05 lock checks pass on both legs (step 4); T08.A31–A33 nodes green |
| V19 | PASS | — | — | T08 §4.9; ADR 0022 Accepted with Frank's selection (R-145); `docs/v02-real-chemistry-dossier.md` and `benchmarks/t08/v19/` unchanged since 0.4.0's candidate (git diff empty, checked here); the A60–A64 nodes green in step 1 |
| V20 | PASS | — | L04, L07, L09, L31, L32, L38 | T08 §4.10; T08.A46 S = 437 of 440 on ref-x86-64 and ci-aarch64 (gate 418), the other 3 F-FALSE-SUCCESS-CAUGHT, same-class replay 25 of 25; T08.A47 12 of 12 on three hosts, worst success ratio 0.0968; T08.A10 node green |
| W21 | PASS | — | L05, L06, L07, L15, L19, L20, L44, L45, L46, L48 | alpha §6.1 (ADR 0028 D7) with RP §6.4; step 12 at C: G10v3, G11v3 and G12 met, reproduce MATCH; G11's 210 experiment results kept under rc/step12/experiments/ and audited against step 12's own runs file, 0 problems; reactor pin 6089593… as ADR 0022; support matrix states the profile, not a sandbox, Linux registered, Windows refused; M02 N1 stands at C (Frank's row of 2026-11-22); the four reactor statements are stated here and registered at C in the envelope row that travels with this gate |
| W22 | PASS | — | L42, L47 | alpha §6.2; step 1: M01.A05–A22, A34, A37 and M02 G7, G8 nodes green on both Linux legs; step 11: cross-check recomputes ("external-crosscheck.json matches": 0.012675, 0.040096, 0.042371 against M01.A38–A40's 0.02, 0.05, 0.05), IDAES re-run equal to the committed record (add9557a…, no differing member); step 12: G12 VERIFIED on the route |
| W23 | PASS | — | L49 | M07 §7.3 and M04 §15 (Amendment 4 read: it changes neither §15's table nor its condition); step 13 at C: `m04_reference.py --check` 11943 claims passed, schema fixtures exit 0, 281 M04 nodes passed, none skipped; manifest nodes 649 passed, 19 archived-history skips; M04 and manifest nodes green in step 1 |
| W24 | PASS | — | L19, L44, L46, L48, L49 | M07 §7.3 and RP §6.5; step 14 at C in the audited nlp environment: nlp tier 213 passed, selection equal to the whole-tree collection (213 = 213), inventory exit 0; M03 and M05 tiers 711 passed, 2 skipped (the default-install answers); M05 REAL replay differences 0 with host platform equal to record platform; M03 reference byte-identical; M03 N1 stands at C |
| W25 | PASS | — | L44, L45, L46, L48, L49 | M07 §5 on the journey of J = 3caa928c (RP §4.5): step 15 at C carried, check ACCEPT, replay bitwise on the recording host's platform; refined at 653.1500351610193 K at the lower bound, TC-1 holds; R1 36 of 60 cold, R3 48 of 400 cold, none exhausted |
| W26 | PASS | — | L-WEB-1, L-WEB-2, L-WEB-3, L-WEB-4 | M07 §7.3 with its first clause as RP §4.6 states it (RP.S19): step 16 4 of 4 (668 M06 nodes passed with the browser required, 0 skipped; node 105 of 105; the 25 named nodes once each, passed; the dry run's exact W27-R63 refusal, exit 1, no summary file); CI x86-64 exports the browser requirement and skips no browser node. G14 not judged at 0.5.0: W27 registration v1 refuses this build (ADR 0050 D9, W27-R63); W27 not claimed |
| X31 | FAIL | X31 (c) | L-COL-1, L-COL-2, L-COL-3, L-COL-4, L-COL-5, L-COL-6, L-COL-7, L-COL-8, L-COL-9, L-COL-10 | RP §4.3 as pre-registered; RC1–RC4 and their registered matches, and the invalid-specification and phase refusals, green in step 1 on both Linux legs; S09 verdict 3 unchanged: "met where available, 3 of 4" (RC4, the refluxed absorber, has one reference, BioSTEAM), which RP §4.3 registers as the failure of the reference clause; the standing acceptance row stands at C |

## Read this first

**The seventeen.** Fifteen PASS (V11, V12, V13, V15, V16, V17, V18, V19, V20, W21, W22, W23, W24, W25, W26). Two
FAIL: V14 on clause (b) and X31 on clause (c). None BLOCKED. 15 + 2 + 0 = 17.

**What blocks the tag today.** No row is BLOCKED. X31 (c) has a standing row at C (2026-10-30, fingerprint
recomputed here), so X31's FAIL is releasable (RP §4.1 item 1). V14 (b) has **no** standing row at C: its row of
2026-11-10 lapsed by its `paths:` scope, because `src/openflowsheet/**` changed. V14's FAIL is therefore not releasable
until Frank's second message brings a new `V14 (b)` row, dated on or after 2026-11-22 and carrying the fingerprint at C
(finding F-1). Until then step 18 gives NO for V14. The other step-18 inputs this verdict names are F-2 (the notes must
carry W21's four statements) and the release manifest, which does not exist yet (§9.2 step 4) and was not waited for.

**Against 0.4.0** (`docs/reviews/REL040-verdicts.md`, C = `84c66547`; comparison only):
- The verdict words are the same: fifteen PASS, V14 FAIL (b), X31 FAIL (c). Here no row was ever BLOCKED: Frank's first
  message, answered before this verdict, already replaced the `V17 carry` and `M02 N1` rows.
- V13 and V17: the chain now has ten links (c_9 R-1030, F1's two tools; c_10 R-1051, F3's five tools). Frank carried
  `v17-c2`'s evidence across all ten; no agent has driven any tool those two links add (F-5).
- V14 (b): the comparison was re-run at C (step 17's PTC-R1 item) and gives 0.4.0's counts exactly.
- W23: M04 spec Amendment 4 (R-1068) is new criterion material; it changes neither §15's table nor its condition
  (W23 section).
- W21 (c): the `M02 N1` row lapsed (the launcher changed) and was replaced by Frank's row of 2026-11-22.
- The RC host is SMM-TR09, not SMM-TRS2 (A-13). Steps 14 and 15 compare against records re-taken on TR09's kernel.

**Standing.** This is an agent verdict, numerical and procedural only. It is not scientific review, and it is not the
human numerical and process-modeling sign-off, which is recorded separately and which no agent may claim. It sets no
manifest to `reviewed`. It moves no tolerance, band or classification rule.

**Criteria, read before the evidence:** RP §4.1–§4.7, §6.4–§6.6, §8.2–§8.5 and A-13; alpha spec §5.1, §5.3, §5.4 and
§6.1–§6.3; T08 §3.3 and §4.1–§4.10; M07 §5 (W25's table) and §7.3; M04 §15 and §21 (Amendment 4); M01.A38–A40. The
criterion documents unchanged since 0.4.0's candidate (git diff empty): the alpha spec, T08, V03, M01 and M07 specs.
RP changed by A-12 and A-13 only; S03 by one line-number reference; M04 by Amendment 4.

## Frank's answers each row waits on (`release/acceptances.md` at `1432f628`, lapse report of 2026-11-22)

| Item or clause | State at C | Rows that wait on it | When it is asked |
| --- | --- | --- | --- |
| `V14 (b)` | **lapsed** (`paths:src/openflowsheet/**,benchmarks/t08/ptc_r1/**,docs/reviews/T08-verdict-V14b.md`: 264 changed paths since 0.4.0's candidate; fingerprint at C `82469c086226671b8b0b39ed5603ef141112dd0f9fc405a8a77bd58f9ec92c40`, recomputed here, against the row's `1abcb2af…75d0`, which still reproduces at its `Accepted at` `84c66547`: lapsed, not unsupported) | V14 FAIL: not releasable until a new row | second message, after `Judged` (RP §8.4, §8.5); the new row dated on or after 2026-11-22, Accepted at C |
| `V17 carry` | **replaced** 2026-11-22 (`6cfe0fc4`): names all ten links; Accepted at C; stands at C, `9f4fb274…6615` (recomputed here, equal at C and at `Accepted at`) | V13 (e) and V17 (a): met | first message, answered before this verdict |
| `M02 N1` | **replaced** 2026-11-22 (`6cfe0fc4`): Accepted at C; stands at C, `7de4c931…4680` (recomputed here) | W21 (c): met | first message, answered before this verdict |
| `X31 (c)` | stands (`59503316…1864`, recomputed here, equal at C and at `a3e508e3`) | X31 FAIL, releasable | not asked |
| `M03 N1` | stands (`8eafbfef…a430`, recomputed here) | W24 (a): met | not asked |
| `coolprop and lca licences` | stands (`0bb1c634…2ce7`, recomputed here) | V18 (MR-12): met | not asked |
| `Claim set` | stands (`f4a3cfbe…a881`, recomputed here) | the claim set judged here | not asked |

**Provenance of the two new rows** (read, not witnessed). `M02 N1`: Decision Desk card `ofs-rel050-m02-n1`, choice A,
VERIFIED by `decision_desk_verify.py` (decisions log, 2026-11-22). `V17 carry`: Frank's plain-word answer in the REL050
session, "Carry for 0.5, campaign in 0.6 (Recommended)", given after the orchestrator reported that the signed card
`ofs-rel050-v17-carry` (choice B, a new campaign at C) needed a registered campaign and a new candidate; the card is
marked superseded. This verdict reads the rows as RP §8.3 directs: the cell rule, the fingerprint at C and at
`Accepted at`. It did not witness the answers.

## Evidence and provenance

| Evidence | Produced by, where | Independent expectation | Class |
| --- | --- | --- | --- |
| RC record `docs/REL050-rc-record.md` | build lane: local `ref-x86-64` (SMM-TR09, Linux 6.12.86+deb13-amd64, 16 cores) from a detached worktree at C, `--porcelain --ignored` empty at start; three `release_rc.py local` invocations, then `ci`, `step1` and `items --ci-run 45019811148` with gh 2.103.3 on PATH (the host's 2.46.0 lacks `--json attempt`; the record states the user's approval) | none: it reports and judges nothing | record |
| The 126 records it cites (`rc/records.json`) | as above; 6 gzip-compressed | **recomputed here: 126 of 126 SHA-256 and byte counts equal** (gzip ones decompressed); the RC record's 123 distinct 64-hex tokens are all in `records.json` | provenance |
| The 53 `t08-rc-v1` records | the records themselves | checked here: every one has `provenance.commit` = C and `tree_clean` true; every check reads `pass`; every record but the bundle index (whose format has no `passed` member) reads `passed: true` | provenance |
| Step 1: x86-64 21066 passed, 118 skipped, 222 deselected, 3 xfailed; aarch64 21034, 118, 222, 3 | CI push run 45019680845, `check` on the two Linux legs, hash-pinned logs. The macOS and Windows legs were green and are not read (RP §6.2; message 1 kept that) | summary lines grepped here; no failure; the 222 deselected are the `nlp` and `pymrm` markers (`addopts`), run at steps 14 and 12; the 3 xfails are `test_msg_corpus` strict pending items | tested (CI) |
| Step 1's skip set | `step1-skips/x86_64.txt`, `aarch64.txt` (121 junit lines each) | classified here (skip audit below); 121 = 118 + 3 on each leg | record |
| Steps 2–10 | local and CI legs | registered values: R-149's identity digests; D_0 … D_10 and R-137's digest with `LINKS` read at C; S_min 418; A34's rule | identity verification, tested |
| Step 11 | local, the IDAES and cross-check environments | IDAES's own numbers (an independent implementation); reference equations of state (for NH₃, CoolProp 8.0.0, Gao-JPCRD-2020) for M01.A38–A40's bands | conformance; empirical validation of pure-component behaviour (W22 (c) only) |
| Step 12 | local, reactor environment built from C's lock (`032a050c…`), one thread | M01/M02 registered bounds; the group's model at the pin | numerical verification of the adapter; regression of the group's model |
| Steps 13–16 | local; steps 14 and 15 in m05's audited nlp environment, in a clean nlp worktree at C | generator `--check`s, schema fixtures, committed records (step 14's REAL record and step 15's journey taken at J on this host) | numerical verification; replay (determinism) |
| Re-take proofs at K3 (RP §7.1 with A-13) | build lane, committed at J; decisions log 2026-11-22 | the proofs' own pass rules: the five G10 records `platform=0 other=0 environment=equal`; REAL `version=0 other=0 environment=host` (SMM-TRS2 to SMM-TR09); IDAES `platform=1 inputs=0 other=0`; **read here from the log, not re-run** | provenance: links J's records to 0.4.0's numbers |
| Step 17's nine items | `items --ci-run 45019811148` with `local`'s own step-17 argv; CI `rc-coolprop` and `ptc-r1` | per item; PTC-R1 against T08's registered comparison | tested; comparison measurement |
| Orchestrator's local full gate at C | `GATE PASS 0a800e69: 21077 passed, 107 skipped, 222 deselected, 3 xfailed` | none beyond the suite | tested (local; quoted from the brief, its log not read here; gates nothing) |
| Packages' manifests | build lane at their own commits | checked here: each of the 24 packages of `gate_set.packages` (F1, F3, M01–M06, S01–S12, S08b, S10c, X01, X07a) has a `tested` manifest at an ancestor of C | evidence about other commits (RP §4.1 item 3) |
| Required ADRs | `docs/adr/` at C | read here: all 32 of `required_adrs` have status Accepted at C | decisions |
| Acceptance fingerprints | `release_gate.py --lapses` (the committed report) and the build lane's re-run after the two new rows | **recomputed here with independent code** from RP §8.2's definitions (`git ls-tree -r -z --full-tree`, `ast` on `LINKS`, the step-8 records): all seven rows, at C and at `Accepted at`; six stand, V14 (b) lapsed (table above) | provenance |

**What pins nothing.** Wall times (the journey 4556 s, G12's solve 169 s) gate nothing. A record that recomputes to the
same bytes shows determinism, not correctness: steps 14 and 15 compare against records taken at J on the same host the
same day, and their link to 0.4.0's numbers is the re-take proofs (`other=0` in every one), not the replay. Step 17's
PTC-R1 item passes when the comparison runs to completion (N-2); its pass is not V14's measurement, the class counts
are. The journey's comparison with 0.4.0's record (109 of 10794 leaves differ, all walls, digests, the commit and R3's
M05 record reference; every number bitwise equal) is provenance, not a W25 criterion; 38 of those differences
(R0/R1 `run_sha256` digests) have an input the build lane did not trace and infers to be the source change.

## V11: PASS

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) semantic diff | met | T07 `diff_revisions`/`semantic_diff` nodes in step 1, both Linux legs |
| (b) immutable drafts | met | K06 content-addressed revisions, draft vs ready, conflict, idempotent commit nodes |
| (c) task-specific validation | met | T01 STR-01…06 and R-022's DRAFT/INVALID rule nodes |
| (d) units and component/reference checks | met | T06 A43, A55–A57, A67–A74, THM-05 nodes; T01 A09 |
| (e) real migration | met | T08.A35 (a v0.0.0 bundle) and, under MR-10, M07a.A42 (the `v0.1.1` CLI bundle) green in step 1 |

The `test_t06_*`, `test_t07_*` and `test_t08_*` skips in step 1 are archived pre-0.1.0 history, platform-bound fixtures
or PTC diagnostics (skip audit); none is a node of (a)–(e). **Travelling:** L38, and X04's three display-unit rows
L-X04-1 to L-X04-3, which bear on (d)'s ground and now parse under the widened limitation grammar (0.4.0's F-5,
resolved). **Does not establish:** gauge-pressure input (refused by design); migration of instances emitted by versions
after `v0.1.1` beyond what step 5's 52 bundles replay.

## V12: PASS

Every model of §14.3's list has, at C, passing contract, limiting/failure, balance and derivative nodes and a coupled
case (T05, T05b, build-first B10–B19), green in step 1 on both Linux legs; no `test_t05*` node is skipped. The
denominator is T08 §4.2's list; the units added since are not in it and are not judged here. **Does not establish:**
anything about units outside the list.

## V13: PASS

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) DM/SCC/BTF | met | T01 nodes in step 1 |
| (b) safeguarded recycle and coupled EO | met | T02 A13–A15, A32, A34 nodes; E1/E2 library-level (L43) |
| (c) scales before iteration | met | K03 and T02 nodes |
| (d) model initialization | met | K03 §10.1's recorded sources and absences (L10) |
| (e) compatible warm starts | met | B40–B49 nodes green in step 1. B50's counterpart (MR-7): content by M07a.A51 (`tests/test_t08_b50_surface_content.py`, in neither skip file), digest and schemas by the chain (step 8, 15 of 15 on three hosts; V17). The carry MR-7 names is Frank's `V17 carry` row of 2026-11-22 ("V17, and T08.B50's surface" across R-192 … R-1051), which stands at C |

**Does not establish:** that agents behave correctly on the 0.5 surface (Frank's carry accepts `v17-c2`'s evidence for
it and measures nothing); warm starts beyond exact id-set compatibility (L-WS-1, L-WS-2; L-WS-2 now names the explicit
source, 0.4.0's F-4 resolved).

## V14: FAIL on V14 (b)

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) one typed homotopy | met | T04 A02–A12 nodes in step 1, both Linux legs |
| (b) one PTC family qualified by §7.5 with tested SER | **not met** | (b1)'s saddle clause fails, measured at C: step 17's `PTC-R1` item (`step17/rc-step17-PTC-R1.json`) ran T08's registered comparison (case `cfa994fe…`) on both legs of dispatch 45019811148, results at commit C. Recounted here from the raw records (`results-ci-aarch64.json.gz`, `results-ci-x86-64.json.gz`), 441 starts per arm: Newton LOW/MID/HIGH/FAIL 113/161/166/1, PTC 182/149/109/1 on both legs. PTC ends `MID` from 149 starts on `ci-aarch64`, a registered platform; `ci-x86-64` (reported only) gives the same. These are T08-verdict-V14b.md's counts, whose verdict is FAIL on the saddle clause |
| (c) three recovery edges | met | T04 §5.5's edges, T02 and T08.A33 nodes in step 1 |

A FAIL cannot be manufactured by a report: 149 `MID` ends falsify "never `MID`" whatever the other starts do. The two
files of `benchmarks/t08/ptc_r1/` that changed since 0.4.0 (`compare.py`, `diagnose.py`) changed import paths only
(S19's refactor); the case hash is unchanged. Skips: `test_t08_ptc_r1_diagnostic` (6, x86-64 only, no committed
ci-x86-64 results) and `test_t08_ptc_r1_case` (2, both legs, pre-0.1.0 history); neither can change a FAIL.
**Acceptance.** The standing `V14 (b)` row lapsed at C (table above); the FAIL is not releasable until Frank's new row
(F-1). **Does not establish:** that PTC is useless elsewhere; any other PTC family.

## V15: PASS

(a) T03 A00–A26, (b) T02 (A02's capability error), (c) T03's root fingerprint and branch provenance, T06 ADV-05 (A15)
and THM-09 (A31), all green in step 1 on both Linux legs. No certificate states uniqueness or dynamic stability: the
five kept step-12 certificates (`step12/certificates/…/solution-certificate.json`) read `NOT_ASSESSED` for both (read
here), and step 10 (`certificates-ref-x86-64.json`) audited 77 certificates under A34 with 0 violations, as did every CI
leg. **Does not establish:** root completeness, uniqueness or stability (L19); any column multiplicity claim (L-COL-5).

## V16: PASS

T06 verdict 1 stands (`docs/reviews/T06-verdicts.md` unchanged since 0.4.0's candidate). T08.A48 at step 7
(`corpus-ref-x86-64.json` and both CI legs' copies, 12 of 12 each): T06.A47 (9 nodes) and T06.A50 (17 nodes) passed on
`ref-x86-64`, `ci-x86-64` and `ci-aarch64`, none skipped. The tool side is not re-run (T08 §4.6). **Does not
establish:** agreement beyond the registered near-sharp ε (L16); DWSIM's environment past .NET 8's end of life,
2026-11-10, which has now passed (L17).

## V17: PASS

- **(a) met.** The chain holds at C on three hosts (`surface/rc-alpha-surface.json` and both CI legs' copies, 15 of 15
  checks each, `first_failure` null). `LINKS` at C, read here with `ast`, is c_1 … c_10 = R-192, R-234, R-295, R-934,
  R-950, R-960, R-1000, R-1010, R-1030, R-1051; the chain rows are exactly the n + 2 = 12 of RP §4.4 in its order. The
  served digest `f7ec3c94…d467` equals D_10 (R-1051); s_10 gives D_9 `e2c44b6b…` (R-1030), then D_8 `6be1c002…`, D_7
  `553b7612…`, D_6 `3fdc797a…`, D_5 `f51b69bf…`, D_4 `eaff4585…`, D_3 `455d01eb…`, D_2 `383b4e2c…`, D_1 `6c4375b4…`
  and D_0 `171dd768…` (R-133); with `v17-c2`'s two texts, `6d13e13d…` (R-137). Tools and description files as
  registered (`a37.item4`, no problems). c_9 and c_10 each have a register entry (R-1030, R-1051), a strip function
  (`without_f1`, `without_f3`) and a registered digest. **The carry.** Frank's `V17 carry` row of 2026-11-22 names all
  ten registers, stands at C and at its `Accepted at` (`9f4fb274…6615`, recomputed here), and its scope
  (`extract:links + extract:served_digest`) binds both the ten links and `f7ec3c94…`. With it `LINKS` is unchanged in
  RP §4.4's sense and step 8 passes, so `v17-c2`'s evidence carries to C, and alpha §5.3's four conditions hold for
  both new links. Rejected: reading the new links as content-only additions that keep the carry without a row; c_9 and
  c_10 add seven tools.
- **(b) met.** G16-b 40 of 40 clean over Python, CLI, HTTP and MCP on three hosts; records attributable (`a16`).

**Evidence classes.** The chain is identity verification against registered digests. The agent evidence is
`v17-c2`'s, measured on the R-137 surface; it reaches 0.5.0 by Frank's decision of 2026-11-22. **Does not
establish:** agent behaviour on the 0.5 surface. No agent has driven F1's `list_capabilities` and `check_admission`
or F3's five `Records` tools, nor the 0.4 additions (F-5). The follow-up is a registered campaign `v17-c3` for 0.6
(decisions log).

## V18: PASS

(a) T08.A30 PASS on `ref-x86-64`, `ci-x86-64` and `ci-aarch64` (`a30/t08-a30-x86_64.json` and the CI copies): the
workload walked 353 modules and imported 348, the five nlp-extra modules refused as registered (MR-12: their closure is
`docs/m03-ipopt-audit.md`'s; the five are 0.4.0's three after S19 split `trust_region.projection` into three); 381, 381
and 308 objects; required closures 150, 150, 147; no undispositioned object, METIS not reached. MR-12:
`pyproject.toml`'s optional dependencies at C equal 0.4.0's (checked here; 0.5 adds package data only), so no extra is
new; the `nlp`, `coolprop` and `lca` licence rows stand at C, and step 17's MR12-coolprop and MR12-lca items pass. X05's
lock checks pass on both legs (step 4). (b)–(c) T06 A32, A33, A37–A46 nodes in step 1; T08.A34 0 violations over 77
certificates locally and on every CI leg (step 10). (d) T08.A33 node. **Does not establish:** closures beyond the
audits (the nlp audit is linux x86-64 only); a licence opinion.

## V19: PASS

(i) ADR 0022 Accepted with Frank's selection (R-145); (ii)–(v) the dossier and `benchmarks/t08/v19/` are unchanged since
0.4.0's candidate (empty git diff `84c66547..C`, checked here), and T08.A60–A64 nodes are green in step 1. The one
`test_t08_w1_ledger` skip (`[V19]`, "not in A02") is the parametrization in which the T08 manifest is not expected in
A02, as at earlier releases. **Does not establish:** any comparison of the selected chemistry with data by this project.

## V20: PASS

(a)–(c) T08.A47 at step 7: T06.A02–A08, A16, A19, A20, 12 of 12 on three hosts, none skipped; T08.A10 node in step 1.
(d) T08.A46 at step 6 (`ensemble/rc-ensemble-ref-x86-64.json`, `ci/rc-ensemble-ubuntu-24.04-arm/rc-ensemble-ci-aarch64.json`)
with the registered starts and classifier: S = 437 of 440 on `ref-x86-64` and on `ci-aarch64` (gate 418), the other 3
`F-FALSE-SUCCESS-CAUGHT`; `a46.registered_class` passes on `ref-x86-64` (A-13's P6 holds for SMM-TR09); no `VERIFIED`
outside S3 (worst success ratio 0.0968); A33 0 failures; same-class replay 25 of 25 MATCH on each class. The one-sided
95 % Clopper–Pearson lower bound at 437 of 440 is 0.98247 (computed here with scipy; the same call gives T08's
registered 0.97326 at 434 and 0.92937 at 418); it is reported, never gated, and assumes independent starts, which
clustered starts are not.

## Skip audit (step 1, R-376)

| Reason (file) | x86-64 | aarch64 | Clause input? |
| --- | --- | --- | --- |
| archived pre-0.1.0 history (R-150): `test_evidence_manifests` (19), `test_t07_evidence_manifest` (28), `test_t08_evidence_manifest` (13), `test_t06_w31_runs` (2), `test_t08_ptc_r1_case` (2), `test_t08_w4_v0_1_gate` (2) | 66 | 66 | No (v0.1 history; 66 as at 0.4.0) |
| W27 pinned archive absent (`test_m06_w27_coverage` 2, `_harness` 8, `_scorer` 16) | 26 | 26 | Covered: step 16 ran `tests/test_m06_*.py` with the archive present, 668 passed, none skipped; the 25 named nodes once each |
| `test_c2_openidaes450_split` (archive absent) | 1 | 1 | No (W27 not claimed) |
| strict xfails reported as junit skips: `test_msg_corpus` pending items | 3 | 3 | No (in no gate's tests; the 3 xfailed of the summary) |
| PTC-R1 diagnostics, no ci-x86-64 results (`test_t08_ptc_r1_diagnostic`) | 6 | 0 | No: V14's clause (b) fails regardless, measured at step 17 |
| M04 platform-bound: `test_m04_prewarm` (x86-64); `test_m04_quadratic`, `test_m04_schemas` (aarch64) | 1 | 2 | Covered: step 13 ran every `test_m04_*` node on `ref-x86-64`, 281 passed, none skipped |
| platform-bound fixtures: `test_k05_schemas`, `test_t06_w28_records` | 2 | 2 | No (as at 0.4.0) |
| aarch64 only: `test_k01_backend_dependency`, `test_t06_w13_f6` (2, states found on ref-x86-64; run on x86-64), `test_m06_browser_smoke` (collection) | 0 | 4 | No; the browser node runs on x86-64 (W26 (b)) |
| aarch64 only: S07's A31a | 0 | 1 | No clause of the seventeen |
| `test_e01_b_brightway` (collection, `bw2data` absent) | 1 | 1 | No clause of the seventeen; step 17's E01-G5-lca item ran it in its environment, pass |
| setuptools-Python artifact checks: `test_s05_envelope`, `test_s07_registration` | 2 | 2 | No clause of the seventeen |
| `test_l01_records` (retrieval re-run not possible) | 1 | 1 | No (`pr-lib-v1` is library-only) |
| `test_t08_w1_ledger` (`[V19]`, "not in A02") | 1 | 1 | No |
| coolprop extra installed, so the refusal path is unobservable: `test_st_cli`, `test_st_core`, `test_st_operation` | 3 | 3 | No clause of the seventeen (ST is not a claimed gate) |
| **new since 0.4.0:** F0's state hashes are judged on `ref-x86-64` only: `test_s19_i15_admissibility_refusal` (5), `test_s19_w5_gate` (1), `test_s19_w5_identity` (2) | 8 | 8 | No: no claimed gate's tests name `test_s19_*`; F0 identity is not a clause of the seventeen |
| **Total junit lines** | **121** | **121** | = 118 + 3 on each leg |

No clause judged here rests on a node skipped at every place it could run. The other steps' junit skips: step 12 skips
one node (`test_a47a_the_nominal_outlet_is_the_probes_bitwise`, "another environment block: M01.A47 (b) decides"); its
record reads `A47_a_bitwise` true with a different environment block, and (b) 1.43 × 10⁻⁸ against 10⁻⁶ decides, as
alpha §6.1 allows. Step 13 skips the same 19 archived-history nodes of `test_evidence_manifests` as step 1 (0.4.0's step
13 skipped none of its 578 manifest nodes; the TR09 clone lacks the archived objects, for example `b44dea0e`, checked
here; F-4); none is an M04 node. Step 14 skips 2 (the default-install answers, unobservable with Pyomo installed).

## W21: PASS

Judged by alpha §6.1 as ADR 0028 D7 reads it, with RP §6.4. Every reactor number is the group's model at the pin, a
regression. Step-12 values were read from C's records (`step12/rc-step12.json`, 6 of 6; `step12/experiments/rc-step12-experiments.json`, 1 of 1).

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) port mapping | met | M02 G4, G8, G9 nodes in step 1 on both Linux legs; step 12's M02 tests with the reactor, 573 nodes, 0 failures, 1 skip (above); G10 (h) via M01.A47 (b): 1.43 × 10⁻⁸ against 10⁻⁶ |
| (b) accuracy contract | met | G10 (b) A42 1.56 × 10⁻⁸ (10⁻⁶); (e) A45 3.84 × 10⁻⁸ (10⁻⁷); (f) A46 5.06 × 10⁻⁵ (10⁻³); A48 estimates equal the reference on all three; G12 floor ratios 13.3 (T) and 65.3 (ξ) against ≥ 10 |
| (c) out-of-process execution policy | met | G3–G5 nodes in step 1; `docs/support-matrix.md` at C: `external-subprocess-v1`, "not a sandbox", "Linux is registered; macOS best effort; Windows is refused before spawn" (read here); `M02 N1` stands at C (Frank's row of 2026-11-22, fingerprint recomputed here) |
| (d) timeout | met | G3 (b) node in step 1; the registered variant's `timeout_s` 600; G12 `CONVERGED` in 4 outer iterations; G11v3 met (`G11v3-4_selected` V5, two runs of 121 points, all equal) |
| (e) provenance | met | G6 nodes in step 1; **G11's experiment results kept and audited at C** (RP §6.4): `r375.audit` pass, its line exactly "G11 experiments audit: 2 runs, 210 boundary points, 210 results, 210 attempts, 0 without a result, 32 direct points (no records); 6 items + schema: 0 problems; context (job_id): 420 findings: PASS" (420 recorded, not judged), audited against step 12's own runs file; the two runs and the audit committed and hash-equal; G10 (g) A47 (a) bitwise; G12 `reproduce` MATCH with bitwise floats; reactor commit `6089593464fc…` = ADR 0022's pin (`env_manifest.commit`); T08.A31, A32 and A64 nodes in step 1 |
| (f) parent-model validation | met | (f1) G10 (g): A47 (a) bitwise. (f2) T08.A61 node in step 1. (f3) A48's grid estimates, G10 (b), G10 (i). (f4) **stated here:** the group's published comparison with experimental data (Gargiulo et al. 2025 §3.1, of Rossetti et al. 2006's rate law) is the group's evidence; this project has compared no reactor result with data; the numbers are the group's model at the pin, a regression; their discretization bias is 1.0–1.4 % in NH₃ (M02 §13). The notes' half: the same four statements are envelope row L46 at C (read here), which this row carries by id into the gate's table and so into the notes (RP §10). No `## v0.5.0` section exists at C; see F-2 |

**Why (f) is met although the notes are not yet written.** Rejected: FAIL (f) because C has no `## v0.5.0` section;
RP §9.2 places the notes after the verdict, and the four statements are registered at C in L46, which travels with this
row. Rejected: met on the verdict's half alone; that would leave the notes unbound. The condition is explicit: if the
tag candidate's `## v0.5.0` section carries neither L46 (in W21's row of the gate's table) nor the four statements,
(f4) is not met and W21 must be judged again.

**W21 does not establish:** that the reactor is right (L46); any aarch64 run or cross-machine reproduction (L44, L15);
a sandbox, Windows support, or concurrency across hosts (L45); sensitivities or optimization through the reactor;
coupled-loop convergence beyond one loop, two edges and G11's corners and centre (L48); that the stand-in certifies
anything about the reactor (R-199); timings under other load.

## W22: PASS

(a) numerical verification: M01.A05–A22 against closed forms and M01.A34 (`--check`) in step 1, both Linux legs. (b)
conformance with an independent implementation: M01.A37 in step 1; step 11's IDAES re-run equals the committed
`benchmarks/m01/idaes-conformance.json` byte for byte (`add9557a…`, `differing_members` []). That record was re-taken at
J on this host; its proof (`IDAES-RETAKE PASS differing=environment.platform platform=1 inputs=0 other=0`) and the diff
against 0.4.0's candidate (read here: one line, `environment.platform`, kernel 6.12.113 to 6.12.86) show IDAES's
numbers unchanged. (c) empirical validation of pure-component behaviour against reference equations of state: step 11's
`external_crosscheck.py --check` exits 0 ("external-crosscheck.json matches"); the record, unchanged since 0.4.0's
candidate, holds |ΔP_sat/P_sat| 0.012675 against M01.A38's 0.02 (ratio 1.58), liquid NH₃ |Δ ln φ| 0.040096 against
A39's 0.05 (1.25) and light-gas |Δ ln φ| 0.042371 against A40's 0.05 (1.18), read here at C. These are R-160's
validation bands, not tolerances; this verdict does not turn them into a confidence statement. (d) sufficiency: G7, G8
nodes in step 1; G12 binds every evaluation to `pr-c1-v1` and ends `VERIFIED` (step 12). **Does not establish:**
mixture VLE; k_ij effects beyond R-157; the near-critical region; liquid-density fitness (L47); anything outside M01's
domain.

## W23: PASS

(a)–(g), M04 §15's rows in order, met on numerical verification as M04 §15 states: step 13 at C
(`step13/rc-step13.json`, 3 of 3): `m04_reference.py --check` "11943 claims passed", `m04_schema_fixtures.py` exit 0,
the tests 949 nodes, 0 failures, 0 errors, 19 skipped (junit `1c8dd782…`): all 281 M04 nodes passed, none skipped; the
19 skips are archived-history nodes of `test_evidence_manifests` (skip audit). M04 and manifest nodes are green in step
1, its three platform-bound M04 skips covered by step 13. The real verdict `NOT_PROMOTABLE` (`band_not_finite`) is
recorded and read by the journey's R2; a PROMOTABLE real verdict is not part of W23 (M04 N6).

**Amendment 4** (M04 §21, R-1068, X07a ruling D1, 2026-11-21; line note D-2) is read here as criterion material. It
corrects §6.2's "ties with probability zero" (ties do not weaken the coverage guarantee), stops asserting the stand-in's
verdicts (they are fit roundoff, every coverage decision near threshold, ADR 0036 D8) and asserts their vanishing
instead, and moves A36's application half onto A17's smooth parent. §15's table and its condition (A01–A30, A34, A35
`tested`; A31–A32 recorded) are unchanged; A36 is outside that list; a test that needs a verdict now takes it from A17,
whose margins are registered and generator-asserted. The amendment was registered by the design lane before K3; this
verdict introduces no tolerance and narrows no denominator. **Does not establish:** a promotable surrogate of the real
reactor (L49); anything about the stand-in's coverage verdicts, which no test asserts any more.

## W24: PASS

| Clause | Judgement | Evidence at C (step 14, `step14/rc-step14.json`, 5 of 5) |
| --- | --- | --- |
| (a) M03's NLP with final parent checks | met | nlp tier 213 nodes passed, 0 skipped; the selection equals the whole-tree collection, 213 = 213 (RP.S20); inventory check exit 0; `M03 N1` stands at C |
| (b)–(e) TRF composition, TR-E2, FD truth accuracy and real-reactor accounting, parent checks and refinement | met | M03 and M05 tiers 713 nodes, 711 passed, 2 skipped (the default-install answers, unobservable with Pyomo installed); `REPLAY PASS REAL differences=0` with host platform = record platform (`Linux-6.12.86+deb13-amd64-x86_64-with-glibc2.41`) |
| (f) constraints kept as constraints | met | the same tiers; the REAL record's content |
| (g) costs reported | met | the truth-ledger identity nodes in the tiers above; `m03_reference.py --check` byte-identical |

The REAL record compared at C was re-taken at J on this host; its proof reads `version=0 platform=4 other=0
environment=host` (SMM-TRS2 to SMM-TR09), which A-13 admits, so no number moved from 0.4.0's record. **Does not
establish:** global optimality; any run outside the audited linux x86-64 nlp environment (L44); a promotable surrogate
(L49).

## W25: PASS

M07 §5's (a)–(h) on the journey record of J = `3caa928c`, committed at `benchmarks/m07/journey/3caa928c…/` and carried
to C by step 15 (`step15/rc-step15.json`, 3 of 3: "RC step 15: the journey at 3caa928c carried"; `check: ACCEPT`;
`replay: bitwise`; host platform = record platform). Read here from the record's report: (a) R0 `INDIFFERENT`, R1
`DECIDED` 653.15 K, R2 `SURROGATE_NOT_PROMOTABLE` with M04's reasons verbatim (`band_not_finite`) and no surrogate
evaluation, R3 `DECISION_STABLE` (M05 study re-run at J); (b) P01 `FE_CHANGED`, P13 `FE_UNCHANGED`, each with its six
numbers; (c) the decision `refined` at T = 653.1500351610193 K, `BOUND_LOWER`, with the bound phrase on R1, R3 and the
journey; (f) TC-1 `TC1_HOLDS` (best verified grid point 653.15 K); (g) cold experiments R1 36 of 60, R3 48 of 400,
journey 88 of 460, none exhausted. (b), (d), (e) and (h) are asserted by `check` (M07 A10–A26, A61).

**The journey's first attempt.** The build lane's first run at J (decisions log, 2026-11-22) used a line that put the
nlp test tools on `PYTHONPATH`. It ended exit 3, `INSUFFICIENT_EVIDENCE`, R1 and R3
`UNSUPPORTED(reactor_environment_unavailable)`, because the reactor environment's `env.verify` then read the test tools'
pytest 8.3.5 and iniconfig 2.3.0 ahead of its pinned 9.1.1 and 2.3.1. The committed record is the second run, with
`PYTHONPATH=src`, the line 0.3.0's and 0.4.0's journeys used; the cause was measured before the re-run and logged as a
DECISION with its alternative. This verdict judges the committed record. The first attempt is not W25 evidence: its
outcome described the invocation, not the host, whose pinned reactor environment verifies under the releases' line.
It was not a re-run to pass. RP does not register the journey's invocation line (F-3).

**Evidence class:** numerical verification of a workflow over the group's model; the decision is a parent evaluation,
not an optimality certificate. **Does not establish:** the objective beyond the lower bound of the reactor's registered
domain (stated in the record); replay on another kernel or host (RP §4.5, L44); validation against data (L46).

## W26: PASS

(a) as RP §4.6 states it while W27 is not claimed (RP.S19): step 16 (`step16/rc-step16.json`), 4 of 4:
`a60.w26.m06_tests` with `OPENFLOWSHEET_REQUIRE_BROWSER=1`, 668 nodes passed, 0 failures, 0 errors, 0 skipped (33
browser nodes among them); `node --test` 105 of 105, 0 skipped; `a60.w26.g15_registered_states`, the 25 named nodes
once each, all passed, 0 skipped; `a60.w26.w27_v1_refusal`, exit 1, last line exactly
`benchmarks.m06.w27.snapshot.SnapshotUnsupportedError: registry_snapshot: unsupported(provider 'iapws95-v1': no
registered records and phases, W27-R63)`, no `summary.json`. (b) CI x86-64's `check` exports
`OPENFLOWSHEET_REQUIRE_BROWSER=1` (read in the job log) and skips no browser node (the only browser skip is aarch64's
collection skip). `benchmarks/m06/openidaes450/coverage.json` is unchanged since 0.4.0's candidate. **Travelling
limitation (RP §4.6), verbatim:** `G14 not judged at 0.5.0: W27 registration v1 refuses this build (ADR 0050 D9,
W27-R63); W27 not claimed`. A reading of "M06 G1–G15 met" is rejected (RP §4.6). **Does not establish:** G14 or the
W27 preflight on this build; usability or accessibility beyond headless Chromium (L-WEB-3).

## X31: FAIL on X31 (c)

Judged by RP §4.3, which pre-registers (c)'s reading. It is applied here, not chosen.

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) RC1–RC4 solve and their registered matches hold | met | S02's M1–M4 at `P_r`, S03/S09's A10 (i) byte-identity and (ii) live-solve classifications, in step 1 on both Linux legs (no S02, S03 or S09 module in either skip file); S02 `1810dde8`, S03 `930aad1b`, S09 `4d4df087` manifests `tested` at ancestors of C |
| (b) invalid specifications and phase cases refused with their registered typed outcomes | met | S02's invalid-specification tests, S08's phases clause (R-736), S08b, S10c's column cases, in step 1 on both Linux legs, none skipped; S08 `6d7d1a6d`, S08b `acbd1266`, S10c `8f38f963` manifests `tested` at ancestors |
| (c) S09's three-tool outcome "met with two references" | **not met** | `docs/reviews/S09-verdicts.md` verdict 3, unchanged since 0.4.0's candidate (git diff empty, with `benchmarks/s03/` and `benchmarks/s09/`): **"MET WHERE AVAILABLE, 3 of 4"** (target 4). RC4, the refluxed absorber, has one reference (BioSTEAM). RP §4.3: any outcome other than "met with two references" is FAIL (c), stated in its registered words |

Releasable by the standing `X31 (c)` row (stands at C; fingerprint recomputed here). S03's spec changed by one
line-number reference only. **Does not establish:** "met with two references" (R-643's watch item); validation of any
column against data (L-COL-8); a reference for RC4 beyond BioSTEAM.

## Findings (step-18 inputs and design-lane items; none changes a verdict above)

- **F-1 (Frank's second message; step-18 input).** V14 (b) fails at C without a standing row. The replacing row must
  keep the lapsed row's scope (`paths:src/openflowsheet/**,benchmarks/t08/ptc_r1/**,docs/reviews/T08-verdict-V14b.md`),
  carry its fingerprint at C (recomputed here as `82469c086226671b8b0b39ed5603ef141112dd0f9fc405a8a77bd58f9ec92c40`; the
  gate's own `Scopes.evaluate` is the authority), name C as `Accepted at`, and be dated on or after 2026-11-22 (this
  verdict's `Judged`). Without it step 18 gives NO for V14.
- **F-2 (notes; step-18 input).** No line phrase carries alpha §6.1 (f4)'s four reactor statements, so the gate will not
  catch their absence. The `## v0.5.0` section must carry L46, by the gate's table (W21's row lists it) or by the four
  statements. W21's PASS rests on this; if the tag candidate's notes lack it, W21 must be judged again.
- **F-3 (design lane; RP text).** RP §4.5 and §6.1 do not register the journey's invocation line. At J, a line with the
  nlp test tools on `PYTHONPATH` gives `INSUFFICIENT_EVIDENCE` through the reactor environment's own verify step, and
  `PYTHONPATH=src` gives the committed record. The build lane chose the latter as a logged DECISION, on precedent. A
  later cut should not have to choose: RP (or the runner) should name the line, and step 15 should refuse a run under
  any other.
- **F-4 (observation).** Step 13's 19 archived-history skips are new at the RC (0.4.0's step 13 ran 578 manifest nodes,
  none skipped). The TR09 clone does not hold the pre-0.1.0 objects (checked here for `b44dea0e`); step 1 on CI skips the
  same 19, as at 0.4.0. No W23 input. The host-move ruling's inventory could list it.
- **F-5 (notes).** V17's carry now spans ten links; c_9 and c_10 add F1's two and F3's five tools, which no agent has
  driven. L12 does not say so. The notes should state that the agent evidence is `v17-c2`'s on the R-137 surface,
  carried by Frank's decision across ten links, with no agent run on 0.5's surface; the 0.6 follow-up (`v17-c3`, tasks
  that drive F1's and F3's tools) is logged and is not part of this verdict.
- **F-6 (closed at C).** 0.4.0's F-4 (L-WS-2's text) and F-5 (the limitation grammar) are resolved at C: L-WS-2 names
  the explicit source, and the widened pattern lets V11 carry L-X04-1 to L-X04-3 by id, as it does here.

## Alternatives considered and rejected

1. **V14 PASS or BLOCKED because its acceptance lapsed.** Rejected: the clause fails on measurement at C; an acceptance
   decides releasability, never the verdict word. The missing row is Frank's, but it is a FAIL's acceptance, not a
   clause's missing input (RP §4.1 item 1).
2. **V14 judged from step 17's PTC-R1 item `pass`.** Rejected: the item asserts that the comparison runs to completion
   (N-2). The class counts, recounted here from the raw records, are the measurement.
3. **X31 written "met with two references".** Rejected by RP §4.3 (R-643).
4. **V13 and V17 BLOCKED on the signed card `ofs-rel050-v17-carry` (choice B, a new campaign at C).** Rejected: RP §8.3
   reads the row in `release/acceptances.md`, not the card. The row records Frank's later plain-word answer, which the
   orchestrator obtained after reporting that B needed a registered campaign and a new candidate, and it stands at C by
   its fingerprint. If that answer were not Frank's, the carry would be missing and V13 (e) and V17 (a) would be
   BLOCKED ("What would change").
5. **V17 carried across c_9 and c_10 without a row, as content-only additions.** Rejected: the two links add seven
   tools; RP §4.4 needs Frank's row naming them, which exists.
6. **W21 FAIL on (f), or met on the verdict's half only.** Rejected for the reasons in W21's section; the condition
   travels as F-2.
7. **W23 FAIL or BLOCKED because Amendment 4 narrowed what the stand-in asserts.** Rejected: §15's table and condition
   are unchanged; the amendment is a registered design-lane ruling made before K3 that applies ADR 0036 D8 as written;
   it moves A36 onto a parent with registered margins and removes assertions about a near-threshold roundoff outcome.
   This verdict introduces no tolerance and narrows no denominator.
8. **W25 judged on the journey's first attempt, or the second run treated as a re-run to pass.** Rejected both ways in
   W25's section: the first attempt's outcome came from the invocation; the cause was measured and logged before the
   re-run; the line is the earlier releases'.
9. **W26 "M06 G1–G15 met".** Rejected by RP §4.6.
10. **Treating the S19 F0 skips, the step-13 archived-history skips, the 3 `test_msg_corpus` junit skips or the
    orchestrator's 107 local skips as clause inputs.** Rejected: audited above; none is a node of a claimed gate's
    clause, and the local gate is a different install that gates nothing here.

## What would change these verdicts

- Frank's dated `V14 (b)` row as F-1 states: V14 stays FAIL, releasable. No row: V14's FAIL is not releasable and the
  tag is not proposed.
- The tag candidate's notes without L46 or the four statements: W21 judged again (F-2).
- Evidence that the `V17 carry` row does not record Frank's answer: V13 (e) and V17 (a) lose their carry and are
  BLOCKED until a carry or a campaign. A V17 campaign at a later candidate: V17 judged on its record.
- Any record at C whose bytes differ from `rc/records.json`, any step re-run at C with another result, or a new C:
  every row judged again.
- A re-take proof found not to hold (the log lines quoted under W22, W24 and the evidence table were read, not re-run):
  the rows that rest on the re-taken records (W22 (b), W24, W25) judged again.
- An RP amendment that changes §4.3, §4.4 or §4.6, a registered journey line other than `PYTHONPATH=src` (F-3), or a
  design-lane finding that Amendment 4 touched a §15 assertion: the affected rows judged again under it.

## What this does not establish

- Agent behaviour on the 0.5.0 surface: no agent ran on it (L12); V17 is PASS on Frank's carry, which measures nothing
  on it. F1's and F3's seven tools have never been driven by an agent.
- Empirical validation of anything beyond W22 (c)'s pure-component bands. The reactor's validation is the group's,
  cited (L46); SYN-001 and its columns are synthetic (L18, L-COL-8).
- Optimality: the journey's decision sits at the lower bound of the reactor's registered domain; no global optimality.
- Portability: the reactor, the journey, steps 6, 11–16 and W24's environment are measured on one Linux x86-64 host,
  SMM-TR09; steps 14 and 15 replay only on its kernel (RP §4.5). Step 1 reads the two Linux legs; the macOS and
  Windows legs were green in the push run and are judged by no clause here.
- The capabilities 0.5.0 adds that no claimed gate covers (X07a, F1, F3, X01's plugin docs): their tests run in step 1,
  F1's and F3's wheel data at step 17 (`WHEEL-F1-F3`, judged by RP.S13 at the manifest), but no verdict here is about
  them; their limitations travel in the envelope and the notes, not in a row of this table.
- That J's re-take proofs are correct: they were read from the decisions log, not re-run here.
- Human numerical and process-modeling sign-off, which is recorded separately and is not claimed here.

**Limitations that travel with these verdicts** into the manifest, the gate's report and the notes: each row's
travelling ids; W26's G14 sentence verbatim; the two FAILs with their acceptance lines (V14 (b) once Frank's row
exists); the four reactor statements (L46, F-2); the V17 carry's scope as F-5 states it; Linux only, one host for the
reactor and the journey; and the journey's invocation line (F-3).
