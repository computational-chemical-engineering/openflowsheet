# REL040 — verdicts on V11–V20, W21–W26 and X31 for `0.4.0`

**Release candidate:** `84c665477b512548f38a6335f51648732b1fe5bb`   **Judged:** 2026-11-10   **By:** design lane (`verdict`)

*RP §4.7 and §9.2 step 3 (`docs/derivations/release-procedure.md`). Line `0.4` (`release/lines/0.4.json`, gate set
`v0.4-gate-v1`), K3 = `49a04731`, J = `e0a3d6b7`. Seventeen claimed gates, judged at C on C's records and on the two
registered carries that reach C (the journey from J; no V17 carry, see V17). W27 is not claimed and has no row. With D2
deferred every row is judged here; nothing is carried from `docs/reviews/V03-verdicts.md`, which was read for its form
only.*

| Gate | Verdict | Failing clauses | Travelling limitations | Basis |
| --- | --- | --- | --- | --- |
| V11 | PASS | — | L38 | T08 §4.1 with MR-10; K06, T01, T06 and T07 nodes, T08.A10, T08.A35 and M07a.A42 green in step 1 on both architectures (CI push run 42790953372: x86-64 19772 passed, aarch64 19742 passed, no failure; skips audited below, none a clause input) |
| V12 | PASS | — | L02, L26, L27, L28, L29, L30, L-CSTR-1, L-CSTR-2, L-CSTR-3 | T08 §4.2, denominator unchanged (alpha §5.1; units added since 0.1 are not in it); T05, T05b and build-first B10–B19 nodes green in step 1 on both architectures, none skipped |
| V13 | BLOCKED | V13 (e): Frank's dated `V17 carry` row naming the eight links R-192 to R-1010 (the 2026-10-30 row lapsed at C) | L10, L22, L23, L24, L36, L38, L43, L-WS-1, L-WS-2 | T08 §4.3 and T08.A71 with MR-7; T01, T02, K03 and B40–B49 nodes green in step 1; B50's counterpart: content by M07a.A51 green in step 1, digest and schemas by the chain at step 8 on three hosts, which holds through eight registered links; the carry MR-7 names is absent at C (lapse report: extract links and served digest differ) |
| V14 | FAIL | V14 (b) | L01, L08, L20, L21, L43, L-COL-10 | T08 §4.4 with T08-verdict-V14b.md; measured at C: step 17's PTC-R1 item ran the registered comparison on both CI legs, PTC ends at the saddle (MID) from 149 of 441 starts on ci-aarch64 (a registered platform) and on ci-x86-64, the class counts of the registered FAIL; typed homotopy and the three recovery edges: T04, T02 and T08.A33 nodes green in step 1; the standing acceptance row lapsed at C (src changed), so Frank's second message asks for it |
| V15 | PASS | — | L02, L14, L19, L20, L33, L-COL-5 | T08 §4.5; T02, T03 and T06 (ADV-05, THM-09) nodes green in step 1 on both architectures; the five kept step-12 certificates carry uniqueness and dynamic stability NOT_ASSESSED (read here) |
| V16 | PASS | — | L16, L17, L18, L32 | T08 §4.6; T06 verdict 1 stands (`docs/reviews/T06-verdicts.md` unchanged since 0.3.0's candidate); T08.A48 (T06.A47 9 nodes, T06.A50 17 nodes) passed at step 7 on ref-x86-64, ci-x86-64 and ci-aarch64 |
| V17 | BLOCKED | V17 (a): Frank's dated `V17 carry` row naming the eight links R-192 to R-1010, or a new V17 campaign (the 2026-10-30 row lapsed at C) | L11, L12, L13 | T08 §4.7 with MR-1, MR-2 and MR-6, and RP §4.4; step 8 on three hosts: served digest 6be1c002…ba57 equals the last registered link's (R-1010), each strip in turn gives 553b7612…, 3fdc797a…, f51b69bf…, eaff4585…, 455d01eb…, 383b4e2c…, 6c4375b4… and 171dd768…, and with v17-c2's texts 6d13e13d…; tools and description files as registered; G16-b 40 of 40 clean on three hosts; the carry covers only R-192, R-234 and R-295 and lapsed |
| V18 | PASS | — | L03, L05, L06, L15, L19, L25, L34, L37, L39, L40, L41 | T08 §4.8 with MR-11 and MR-12; T08.A30 PASS on three hosts (267 modules walked, 264 imported, the three nlp-extra modules refused as registered; required closures 150, 150, 147; nothing undispositioned); no extra new since 0.3.0 (pyproject extras identical), their licence rows stand (coolprop and lca licences, M03 N1); step 17 MR12-coolprop and MR12-lca pass; T08.A34 0 violations over 77 certificates (step 10, and on every CI leg); X05 lock checks pass on both legs (step 4); T08.A31–A33 nodes green |
| V19 | PASS | — | — | T08 §4.9; ADR 0022 Accepted with Frank's selection (R-145); `docs/v02-real-chemistry-dossier.md` and `benchmarks/t08/v19/` unchanged since 0.3.0's candidate (git diff empty, checked here); the A60–A64 nodes green in step 1 |
| V20 | PASS | — | L04, L07, L09, L31, L32, L38 | T08 §4.10; T08.A46 S = 437 of 440 on ref-x86-64 and ci-aarch64 (gate 418), the other 3 F-FALSE-SUCCESS-CAUGHT, same-class replay 25 of 25; T08.A47 12 of 12 on three hosts, worst success ratio 0.0968; T08.A10 node green |
| W21 | PASS | — | L05, L06, L07, L15, L19, L20, L44, L45, L46, L48 | alpha §6.1 (ADR 0028 D7) with RP §6.4; step 12 at C: G10v3, G11v3 and G12 met, reproduce MATCH; G11's 210 experiment results kept under rc/step12/experiments/ and audited with step 12's own runs file, 0 problems; reactor pin 6089593… as ADR 0022; support matrix states the profile, not a sandbox, Linux registered, Windows refused; M02 N1 stands at C; the four reactor statements are stated here and registered at C in the envelope row that travels with this gate |
| W22 | PASS | — | L42, L47 | alpha §6.2; step 1: M01.A05–A22, A34, A37 and M02 G7, G8 nodes green on both architectures; step 11: cross-check recomputes byte-equal (ratios 1.58, 1.25, 1.18 of their bands), IDAES re-run identical to the committed record, no differing member; step 12: G12 VERIFIED on the route |
| W23 | PASS | — | L49 | M07 §7.3 and M04 §15; step 13 at C: `m04_reference.py --check` 11943 claims, schema fixtures exit 0, 858 M04 tests passed, none skipped; M04 and manifest nodes green in step 1 |
| W24 | PASS | — | L19, L44, L46, L48, L49 | M07 §7.3 and RP §6.5; step 14 at C in the audited nlp environment: nlp tier 212 passed, selection equal to the whole-tree collection (212 = 212), inventory exit 0; M03 and M05 tiers 679 passed, 2 skipped (the default-install answers); M05 REAL replay differences 0 with host platform equal to record platform; M03 reference byte-identical; M03 N1 stands at C |
| W25 | PASS | — | L44, L45, L46, L48, L49 | M07 §5 on the journey of J = e0a3d6b7 (RP §4.5): step 15 at C carried, check ACCEPT, replay bitwise on the recording host's platform; refined at 653.1500351610193 K at the lower bound, TC-1 holds; R1 36 of 60 cold, R3 48 of 400 cold, none exhausted |
| W26 | PASS | — | L-WEB-1, L-WEB-2, L-WEB-3, L-WEB-4 | M07 §7.3 with its first clause as RP §4.6 states it (RP.S19): step 16 4 of 4 (668 M06 nodes passed with the browser required, 0 skipped; node 105 of 105; the 25 named nodes once each, passed; the dry run's exact W27-R63 refusal, exit 1, no summary file); CI x86-64 exports the browser requirement and skips no browser node. G14 not judged at 0.4.0: W27 registration v1 refuses this build (ADR 0050 D9, W27-R63); W27 not claimed |
| X31 | FAIL | X31 (c) | L-COL-1, L-COL-2, L-COL-3, L-COL-4, L-COL-5, L-COL-6, L-COL-7, L-COL-8, L-COL-9, L-COL-10 | RP §4.3 as pre-registered; RC1–RC4 and their registered matches, and the invalid-specification and phase refusals, green in step 1 on both architectures; S09 verdict 3 unchanged: "met where available, 3 of 4" (RC4, the refluxed absorber, has one reference, BioSTEAM), which RP §4.3 registers as the failure of the reference clause; the standing acceptance row stands at C |

## Read this first

**The seventeen.** Thirteen PASS (V11, V12, V15, V16, V18, V19, V20, W21, W22, W23, W24, W25, W26). Two FAIL: V14 on
clause (b) and X31 on clause (c). Two BLOCKED: V13 on clause (e) and V17 on clause (a), both on one missing input,
Frank's `V17 carry` row for the eight-link surface. 13 + 2 + 2 = 17.

**What blocks the tag today.** BLOCKED blocks the tag (RP §4.1 item 1). V13 and V17 wait on one answer in Frank's first
message. V14 (b) fails with no standing row (its row lapsed by its `paths:` scope); it is releasable only by a new row
dated on or after 2026-11-10, which Frank's second message asks for (RP §8.4, §8.5, finding F-8). X31 (c) fails with a
standing row and is releasable as it stands.

**Against 0.3.0** (`docs/reviews/V03-verdicts.md`, C = `a3e508e3`, re-judged 2026-10-31; comparison only):
- V13 and V17: PASS there after re-judgement, BLOCKED here. The surface moved by five registered links (R-934, R-950,
  R-960, R-1000, R-1010), so the 2026-10-30 carry, written "with no new link at C", lapsed. Same position as 0.3.0's
  first judgement.
- W21: FAIL on (e) at 0.3.0's first judgement, PASS here. Step 12 now keeps and audits G11's 210 experiment results at
  C (RP §6.4), which is exactly what 0.3.0 lacked.
- V14: FAIL on (b) as at 0.3.0; here the comparison was re-run at C (step 17's PTC-R1 item) rather than argued
  unchanged.
- Every other word is unchanged.

**Standing.** This is an agent verdict, numerical and procedural only. It is not scientific review, and it is not the
human numerical and process-modeling sign-off, which is recorded separately and which no agent may claim. It sets no
manifest to `reviewed`. It moves no tolerance, band or classification rule.

**Criteria, read before the evidence:** RP §4.1–§4.7, §6.4–§6.6, §8.3–§8.5; alpha spec §5.1–§5.4 and §6.1–§6.3; T08
§3.3 and §4.1–§4.10; M07 §5 (W25's table) and §7.3. The release manifest does not exist yet (§9.2 step 4) and was not
waited for.

## Frank's answers each row waits on (`release/acceptances.md`, lapse report of 2026-11-10)

| Item or clause | State at C | Rows that wait on it | When it is asked |
| --- | --- | --- | --- |
| `V17 carry` | **lapsed** (`extract:links`, `extract:served_digest`): the row names R-192, R-234, R-295 and digest `455d01eb…e125`; at C the links are eight and the served digest is `6be1c002…ba57` | V13 clause (e) BLOCKED, V17 clause (a) BLOCKED | first message (before this verdict; being asked). A replacing row is dated on or after the lapse report, 2026-11-10, and carries the fingerprint taken at C (RP §8.4) |
| `V14 (b)` | **lapsed** (`paths:src/openflowsheet/**`, 86 changed paths) | V14 FAIL is not releasable without it | second message, after `Judged`; dated on or after 2026-11-10 (RP §8.4, F-8) |
| `X31 (c)` | stands (fingerprint `59503316…1864`, recomputed here with shell tools) | X31 FAIL, releasable | — |
| `M02 N1` | stands (`c1b16371…9cf4`, recomputed here) | W21 (c) met | — |
| `M03 N1` | stands | W24 (a) met | — |
| `coolprop and lca licences` | stands | V18 (MR-12) met | — |
| `Claim set` | stands | the claim set judged here | — |

**Re-judgement.** When Frank's dated `V17 carry` row exists, V13 and V17 may be judged again at the same C under the
line's `rejudge_waits` (alpha §19.2), with one Re-judged line below the header. If he declines the carry, V17 needs
a new V17 campaign, and until then V13 and V17 stay BLOCKED and no tag is proposed. V14's FAIL is not re-judged by
Frank's row; the row makes it releasable.

## Evidence and provenance

| Evidence | Produced by, where | Independent expectation | Class |
| --- | --- | --- | --- |
| RC record `docs/REL040-rc-record.md` (68 rows) | build lane: local `ref-x86-64` (Linux 6.12.113, 48 cores) from a detached worktree at C, `--porcelain --ignored` empty at start; three `release_rc.py local` invocations, then `ci`, `step1`, `items --ci-run 42791067917` | none: it reports and judges nothing | record |
| The 124 records it cites (`rc/records.json`) | as above; 6 gzip-compressed | **recomputed here: 124 of 124 SHA-256 equal** (gzip ones decompressed); the RC record's 121 distinct 64-hex tokens are all in `records.json` | provenance |
| The 52 `t08-rc-v1` records | the records themselves | checked here: every one has `commit` = C and `tree_clean` true; every check reads `pass`; every record but the bundle index (whose format has no `passed` member, as at 0.2.0 and 0.3.0) reads `passed: true` | provenance |
| Step 1: x86-64 19772 passed, 112 skipped, 220 deselected, 3 xfailed; aarch64 19742, 110, 220, 3 | CI push run 42790953372, `check` both legs, hash-pinned logs | summary lines grepped here; no `failed`; the 220 deselected are the `nlp` and `pymrm` markers (`addopts`), run at steps 14 and 12; the 3 xfails are `test_msg_corpus` strict pending items, in no gate's tests | tested (CI) |
| Step 1's skip set | `step1-skips/x86_64.txt` (115 junit lines), `aarch64.txt` (113) | classified here (skip audit below); junit lines = pytest skips + the 3 xfails (112 + 3, 110 + 3) | record |
| Steps 2–10 | local and CI legs | registered values: R-149's identity digests; D_0…D_8 and R-137's digest with `LINKS` read at C; S_min 418; A34's rule | identity verification, tested |
| Step 11 | local, the IDAES and cross-check environments | IDAES 2.13's own numbers (an independent implementation); reference equations of state for the bands | conformance; empirical validation of pure-component behaviour (W22 (c) only) |
| Step 12 | local, reactor environment from C's lock (`032a050c…`), one thread | M01/M02 registered bounds; the group's model at the pin | numerical verification of the adapter; regression of the group's model |
| Steps 13–16 | local; step 14 and 15 in m05's audited nlp environment in a second clean worktree | generator `--check`s, schema fixtures, committed records (step 14's REAL record and step 15's journey were re-taken at J on this host, R-1008) | numerical verification; replay (determinism) |
| Step 17's eight items | `items --ci-run 42791067917` in a new clean worktree at C; CI `rc-coolprop` and `ptc-r1` | per item; PTC-R1 against T08's registered comparison | tested; comparison measurement |
| Orchestrator's local full gate at C | `GATE PASS 84c66547: 16678 passed, 3206 skipped, 220 deselected, 3 xfailed` | none beyond the suite | tested (local; a different install, its skips mostly the CoolProp extra, pre-0.1.0 history and the W27 archive) |
| Packages' manifests | build lane at their own commits | checked here: each of the twenty packages (M01–M06, S01–S12, S08b, S10c) has a `tested` manifest at an ancestor of C | evidence about other commits (RP §4.1 item 3) |
| Required ADRs | `docs/adr/` at C | read here: all 26 of `required_adrs` have status Accepted | decisions |
| Acceptance fingerprints | `release_gate.py --lapses` | recomputed here with `git ls-tree` and `sha256sum` (RP §8.2's shell form): M02 N1 `c1b16371…9cf4` and X31 (c) `59503316…1864` equal their rows; V14 (b) gives `1abcb2af…75d0` against the row's `7506c908…7a77` (lapsed) | provenance |

**What pins nothing.** Wall times (step 12's G12 145.8 s, G11's per-repeat 34–37 s, the journey's 4668 s) were taken
while the host's 1-min load reached 52.84 (09:59–10:09Z, other sessions included); they gate nothing, and a timeout
not reached under load is not weakened by the load. A record that recomputes to the same bytes shows determinism, not
correctness: steps 14 and 15 compare against records re-taken at J on the same host the same day, and their link to
0.3.0's numbers is the re-take proofs (`other=0` in every one), not the replay. The S07 A31 and S11 class ratios that
step 1 records (aarch64 S07 class T worst ratio 5.658e-11 of 1e-10; S11 relative class worst 1.463e-3 of its bound) are
recorded under RP.S15 and judged by no clause of the seventeen.

## V11 — PASS

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) semantic diff | met | T07 `diff_revisions`/`semantic_diff` nodes in step 1, both architectures |
| (b) immutable drafts | met | K06 content-addressed revisions, draft vs ready, conflict, idempotent commit nodes |
| (c) task-specific validation | met | T01 STR-01…06 and R-022's DRAFT/INVALID rule nodes |
| (d) units and component/reference checks | met | T06 A43, A55–A57, A67–A74, THM-05 nodes; T01 A09 (superseding K06's check) |
| (e) real migration | met | T08.A35 (a v0.0.0 bundle) and, under MR-10, M07a.A42 (the `v0.1.1` CLI bundle) green in step 1 |

The `test_t06_*`, `test_t07_*` and `test_t08_*` skips in step 1 are archived pre-0.1.0 history, platform-bound fixtures
or PTC diagnostics (skip audit); none is a node of (a)–(e). **Travelling:** L38. X04's three display-unit rows
(L-X04-1 to L-X04-3) bear on clause (d)'s ground, because 0.4.0 changed how units are shown and refused, but their ids
do not parse under the verdict grammar's limitation pattern, so they travel through the envelope and the notes only
(finding F-5). **Does not establish:** gauge-pressure input (refused by design); migration of instances emitted by versions after
`v0.1.1` beyond what step 5's 52 bundles replay.

## V12 — PASS

Every model of §14.3's list has, at C, passing contract, limiting/failure, balance and derivative nodes and a coupled
case (T05 A00–A30, T05b B00–B36/X00–X26, build-first B10–B19), green in step 1 on both architectures; no `test_t05*`
node is skipped. The denominator is T08 §4.2's list; the thermal, Wilson and column units added since are not in it and
are not judged here. **Does not establish:** anything about units outside the list.

## V13 — BLOCKED on V13 (e)

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) DM/SCC/BTF | met | T01 nodes in step 1 |
| (b) safeguarded recycle and coupled EO | met | T02 A13–A15, A32, A34 nodes; E1/E2 library-level (L43) |
| (c) scales before iteration | met | K03 and T02 nodes |
| (d) model initialization | met | K03 §10.1's recorded sources and absences (L10) |
| (e) compatible warm starts | **blocked** | B40–B49 nodes green in step 1. B50's counterpart (MR-7): content by M07a.A51 (`tests/test_t08_b50_surface_content.py`, in neither skip file), digest and schemas by the chain, step 8, 13 of 13 on three hosts. **Missing:** the carry MR-7 names. Frank's `V17 carry` row ("V17, and T08.B50's surface", across R-192, R-234 and R-295, "with no new link at C") lapsed at C on both its terms |

Why BLOCKED and not FAIL: the missing input is Frank's decision (T08 §3.3), and every part the lanes own holds — the
chain, the register entries, the strip functions and the registered digests of all eight links. **Does not
establish:** that the 0.4 surface is acceptable for agents (Frank's carry decides that); warm starts beyond exact id-set
compatibility (L-WS-1, L-WS-2). X02's explicit warm-start source (ADR 0070) is new capability, not V13 (e)'s evidence
(finding F-4).

## V14 — FAIL on V14 (b)

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) one typed homotopy | met | T04 A02–A12 nodes in step 1, both architectures |
| (b) one PTC family qualified by §7.5 with tested SER | **not met** | (b1)'s saddle clause fails, measured at C: step 17's `PTC-R1` item ran T08's registered comparison (case `cfa994fe…`) on both legs of dispatch 42791067917. On `ci-aarch64`, a registered platform: Newton LOW/MID/HIGH/FAIL 113/161/166/1, PTC 182/149/109/1; PTC ends `MID` from 149 starts and reaches 84 starts Newton does not. `ci-x86-64` (reported only) gives the same counts. These are T08-verdict-V14b.md's counts, whose verdict is FAIL on the saddle clause; `ref-x86-64` was not run at C and is not needed for a FAIL |
| (c) three recovery edges | met | T04 §5.5's edges, T02 and T08.A33 nodes in step 1 |

The counts are read from the harness's report (`step17/PTC-R1/*/results-*.md`, "reported, not judged"); this verdict
did not recompute the per-start sets. A FAIL cannot be manufactured by the report: 149 `MID` ends falsify "never
`MID`" whatever the other starts do. Skips: `test_t08_ptc_r1_diagnostic` (6, x86-64 only, no committed ci-x86-64
results) and `test_t08_ptc_r1_case` B20 git order (2, both legs, pre-0.1.0 history) — neither can change a FAIL.
**Acceptance.** The standing `V14 (b)` row lapsed: its scope holds `src/openflowsheet/**`, which changed. The FAIL is
therefore not releasable at C until Frank's new row, dated on or after 2026-11-10 with the fingerprint at C. **Does not
establish:** that PTC is useless elsewhere; any other PTC family.

## V15 — PASS

(a) T03 A00–A26, (b) T02 (A02's capability error), (c) T03's root fingerprint and branch provenance, T06 ADV-05 (A15)
and THM-09 (A31), all green in step 1 on both architectures. No certificate states uniqueness or dynamic stability: the
five kept step-12 certificates read `NOT_ASSESSED` for both (read here), and step 10 audited 77 certificates under A34
with 0 violations. **Does not establish:** root completeness, uniqueness or stability (L19); any column multiplicity
claim (L-COL-5).

## V16 — PASS

T06 verdict 1 stands (8 of 8 by both tools, 16 of 16 AGREE; `docs/reviews/T06-verdicts.md` unchanged since 0.3.0's
candidate). T08.A48 at step 7: T06.A47 (9 nodes) and T06.A50 (17 nodes) passed on `ref-x86-64`, `ci-x86-64` and
`ci-aarch64`, none skipped. The tool side is not re-run (T08 §4.6). **Does not establish:** agreement beyond the
registered near-sharp ε (L16); DWSIM's environment past .NET 8's end of life, which is today (L17).

## V17 — BLOCKED on V17 (a)

- **(a) blocked.** The chain holds at C on three hosts (`surface/rc-alpha-surface.json` and both CI legs' copies, 13 of
  13 each): the served digest `6be1c002…ba57` equals the registered digest of the last link c_8 (R-1010), and each strip
  applied to the previous strip's output gives, in order, c_7 `553b7612…`, c_6 `3fdc797a…`, c_5 `f51b69bf…`, c_4
  `eaff4585…`, c_3 `455d01eb…e125`, c_2 `383b4e2c…`, c_1 `6c4375b4…` and D_0 `171dd768…`; with `v17-c2`'s two texts,
  `6d13e13d…` (R-137). Tools and description files as registered (`a37.item4`, no problems). `LINKS` at C is the eight
  links (c_1 R-192 … c_8 R-1010), each with its register entry (R-976 for c_4, R-950, R-960, R-1000, R-1010).
  **Missing:** Frank's carry over this surface. RP §4.4: `v17-c2`'s evidence carries to C if and only if step 8 passes
  with `LINKS` unchanged; it changed, so the 2026-10-30 row (three links, "with no new link at C") lapsed. Alpha §5.3:
  a new link needs a register entry, a strip, a registered digest and Frank's carry extended to name it; three of four
  exist, so V17 is BLOCKED. Rejected: reading F5 ("content-only additions keep V17's carry") as covering these links;
  c_6 and c_8 change description texts and c_7 adds a tool, which are not content-only additions.
- **(b) met.** G16-b 40 of 40 clean over Python, CLI, HTTP and MCP on three hosts; records attributable (`a16`).

**Evidence classes.** The chain is identity verification against registered digests. The agent evidence is
`v17-c2`'s, measured on the R-137 surface; it can reach 0.4.0 only by Frank's decision, or by a new campaign. No agent
ran on the 0.4.0 surface (L12). **Does not establish:** agent behaviour on the 0.4 surface, which now carries MSG's
messages, X02's warm-start member, OPT's `optimize`, ST's `get_stream_table` and X04's display units.

## V18 — PASS

(a) T08.A30 PASS on `ref-x86-64`, `ci-x86-64` and `ci-aarch64`: the workload walked 267 modules and imported 264, the
three nlp-extra modules refused as registered (MR-12: their closure is `docs/m03-ipopt-audit.md`'s); 381/381/308 objects;
required closures 150, 150, 147; no undispositioned object, METIS not reached. MR-12: `pyproject.toml`'s extras at C are
identical to 0.3.0's (checked here), so no extra is new since the previous release; the `nlp`, `coolprop` and `lca`
licence rows stand at C, and step 17's MR12-coolprop and MR12-lca items pass. X05's lock checks pass on both legs
(step 4). (b)–(c) T06 A32, A33, A37–A46 nodes in step 1; T08.A34 0 violations over 77 certificates locally and on every
CI leg (step 10). (d) T08.A33 node. **Does not establish:** closures beyond the audits (the nlp audit is linux x86-64
only); a licence opinion.

## V19 — PASS

(i) ADR 0022 Accepted with Frank's selection (R-145); (ii)–(v) the dossier and `benchmarks/t08/v19/` are unchanged since
0.3.0's candidate (empty git diff `a3e508e3..C`, checked here), and T08.A60–A64 nodes are green in step 1. The one
`test_t08_w1_ledger` skip (`[V19]`, "not in A02") is the parametrization in which the T08 manifest is not expected in A02,
as at 0.2.0 and 0.3.0. **Does not establish:** any comparison of the selected chemistry with data by this project
(that is W21 (f4)'s statement).

## V20 — PASS

(a)–(c) T08.A47 at step 7: T06.A02–A08, A16, A19, A20, 12 of 12 on three hosts, none skipped; T08.A10 node in step 1.
(d) T08.A46 at step 6 with the registered starts and classifier: S = 437 of 440 on `ref-x86-64` and on `ci-aarch64`
(gate 418), the other 3 `F-FALSE-SUCCESS-CAUGHT`, no crash or other-root; no `VERIFIED` outside S3 (worst success ratio
0.0968); A33 0 failures; same-class replay 25 of 25 MATCH on each class. The one-sided 95 % Clopper–Pearson lower bound
at 437 of 440 is 0.98247 (computed here with scipy; the same call reproduces T08's registered 0.97326 at 434 and 0.92937
at 418); it is reported, never gated, and assumes independent starts, which clustered starts are not.

## Skip audit (step 1, R-376)

| Reason (file) | x86-64 | aarch64 | Clause input? |
| --- | --- | --- | --- |
| archived pre-0.1.0 history (R-150): `test_evidence_manifests` (19), `test_t07_evidence_manifest` (28), `test_t08_evidence_manifest` (13), `test_t06_w31_runs` (2), `test_t08_ptc_r1_case` (2, B20 git order), `test_t08_w4_v0_1_gate` (2) | 66 | 66 | No (v0.1 history; 66 as at 0.3.0, attributed per junit node here, not per conftest line) |
| W27 pinned archive absent (`test_m06_w27_coverage` 2, `_harness` 8, `_scorer` 16) | 26 | 26 | Covered: step 16 ran `tests/test_m06_*.py` with the archive present, 668 passed, none skipped; the 25 named nodes once each (junit read here) |
| `test_c2_openidaes450_split` (archive absent) | 1 | 1 | No (W27 not claimed) |
| strict xfails reported as junit skips: `test_msg_corpus` pending C01, C08, C10 | 3 | 3 | No (in no gate's tests; the 3 xfailed of the summary) |
| PTC-R1 diagnostics, no ci-x86-64 results (`test_t08_ptc_r1_diagnostic`) | 6 | 0 | No: (b) fails regardless, measured at step 17 |
| M04 platform-bound: `test_m04_prewarm` (x86-64), `test_m04_quadratic`, `test_m04_schemas` | 3 | 2 | Covered: step 13 ran every `test_m04_*` node locally, 858 passed, none skipped |
| platform-bound fixtures: `test_k05_schemas`, `test_t06_w28_records` | 2 | 2 | No (as at 0.2.0 and 0.3.0) |
| aarch64 only: `test_k01_backend_dependency`, `test_t06_w13_f6` (2, states found on ref-x86-64; run on x86-64), `test_m06_browser_smoke` (collection) | 0 | 4 | No; the browser node runs on x86-64 (W26 (b)) |
| aarch64 only: S07's A31a | 0 | 1 | No clause of the seventeen; A31b passes on aarch64 (class ratios recorded above) |
| `test_e01_b_brightway` (collection, `bw2data` absent) | 1 | 1 | No clause of the seventeen; step 17's E01-G5-lca item ran it in its environment, pass |
| setuptools-Python artifact checks: `test_s05_envelope`, `test_s07_registration` | 2 | 2 | No clause of the seventeen; not measured at C on CI (as at 0.3.0) |
| `test_l01_records` (retrieval re-run not possible) | 1 | 1 | No (`pr-lib-v1` is library-only) |
| `test_t08_w1_ledger` (`[V19]`, "not in A02") | 1 | 1 | No |
| coolprop extra installed, so the refusal path is unobservable: `test_st_cli`, `test_st_core`, `test_st_operation` (TH-C2 served) | 3 | 3 | No clause of the seventeen (ST is not a claimed gate) |
| **Total junit lines** | **115** | **113** | = 112 + 3 and 110 + 3 |

No clause judged here rests on a node skipped at every place it could run. The step-12 junit skips one node
(`test_a47a_the_nominal_outlet_is_the_probes_bitwise`, "another environment block: M01.A47 (b) decides"): its record
reads `A47_a_bitwise` true with a different environment block, and (b) 1.43 × 10⁻⁸ against 10⁻⁶ decides, as alpha §6.1
allows. Step 14 skips 2 (the default-install answers, unobservable with Pyomo installed), as at 0.3.0.

## W21 — PASS

Judged by alpha §6.1 as ADR 0028 D7 reads it, with RP §6.4. Every reactor number is the group's model at the pin, a
regression. Step-12 values were read from C's records.

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) port mapping | met | M02 G4, G8, G9 nodes in step 1 on both architectures (M01.A25–A32, A49–A51 among W22's M01 nodes); G10 (h) via M01.A47 (b): 1.43 × 10⁻⁸ against 10⁻⁶ |
| (b) accuracy contract | met | G10 (b) A42 1.56 × 10⁻⁸ (10⁻⁶); (e) A45 3.84 × 10⁻⁸ (10⁻⁷); (f) A46 5.06 × 10⁻⁵ (10⁻³); A48 estimates equal the reference on all three; G12 floor ratios 13.3 (T) and 65.3 (ξ) against ≥ 10 |
| (c) out-of-process execution policy | met | G3–G5 nodes in step 1; `docs/support-matrix.md` at C: `external-subprocess-v1`, "not a sandbox", "Linux is registered; macOS best effort; Windows is refused before spawn" (read here); `M02 N1` stands at C (fingerprint recomputed here) |
| (d) timeout | met | G3 (b) node in step 1; the registered variant's `timeout_s` 600; G11 (d) recorded beside it: `startup_s` 2.05–2.43 s and `solve_s` 31.9–34.7 s over G11v3-5's five repeats; G12 `CONVERGED` in 4 outer iterations, G11v3 met (`G11v3-4_selected` V5) |
| (e) provenance | met | G6 nodes in step 1; **G11's experiment results kept and audited at C** (RP §6.4): `step12/experiments/rc-step12-experiments.json`, `r375.audit` pass, its line exactly "G11 experiments audit: 2 runs, 210 boundary points, 210 results, 210 attempts, 0 without a result, 32 direct points (no records); 6 items + schema: 0 problems; context (job_id): 420 findings: PASS" (j = 420, recorded, not judged), audited against step 12's own runs file; the two runs and the audit committed and hash-equal; G10 (g) A47 (a) bitwise; G12 `reproduce` MATCH with bitwise floats; reactor commit `6089593464fc…` = ADR 0022's pin (`env_manifest.commit`); T08.A31, A32 and A64 nodes in step 1 (rights table; the wheel admits the reactor lock and no third-party code or data) |
| (f) parent-model validation | met | (f1) G10 (g): A47 (a) bitwise. (f2) T08.A61 node in step 1. (f3) A48's grid estimates, G10 (b), G10 (i). (f4) stated here: the group's published comparison with experimental data (Gargiulo et al. 2025 §3.1, of Rossetti et al. 2006's rate law) is the group's evidence; this project has compared no reactor result with data; the numbers are the group's model at the pin, a regression; their discretization bias is 1.0–1.4 % in NH₃ (M02 §13). The notes' half: the same four statements are envelope row L46 at C, which travels with this gate by id into the gate report and the notes (T08 §3.3). No `## v0.4.0` section exists at C (RP places the notes after the verdict); see finding F-2 |

**Why (f) is met although the notes are not yet written.** Rejected: FAIL (f) because C has no `## v0.4.0` section —
the notes are written after the verdict under RP §9.2, and the four statements are registered at C in L46, which
travels with this row. Rejected: met "on the verdict's half" alone, as 0.3.0 first judged it — that would leave the
notes unbound. The condition is explicit: if the tag candidate's `## v0.4.0` section does not carry L46 (or the four
statements), (f4) is not met and W21 must be judged again.

**W21 does not establish:** that the reactor is right (L46); any aarch64 run or cross-machine reproduction (L44, L15);
a sandbox, Windows support, or concurrency across hosts (L45); sensitivities or optimization through the reactor;
coupled-loop convergence beyond one loop, two edges and G11's corners and centre (L48); that the stand-in certifies
anything about the reactor (R-199); timings under other load.

## W22 — PASS

(a) numerical verification: M01.A05–A22 against closed forms and M01.A34 (`--check`) in step 1, both architectures. (b)
conformance with an independent implementation: M01.A37 in step 1; step 11's IDAES re-run equals the committed
`benchmarks/m01/idaes-conformance.json` byte for byte (`76068ff5…`, `differing_members` []). That record was re-taken
at J on this host; its proof (`IDAES-RETAKE PASS … platform=1 inputs=1 other=0`) and the diff against 0.3.0's candidate
(read here: only `environment.platform` and `inputs.reference_values_yaml_sha256`) show IDAES's numbers unchanged
since 0.3.0. (c) empirical validation of pure-component behaviour against reference equations of state: step 11's
`external_crosscheck.py --check` exits 0 ("external-crosscheck.json matches"), so the record's values stand: 0.012675
against 0.02 (ratio 1.58), 0.040096 against 0.05 (1.25), 0.042371 against 0.05 (1.18). These are R-160's validation
bands, not tolerances; this verdict does not turn them into a confidence statement. (d) sufficiency: G7, G8 nodes in
step 1; G12 binds every evaluation to `pr-c1-v1` and ends `VERIFIED` (step 12). **Does not establish:** mixture VLE;
k_ij effects beyond R-157; the near-critical region; liquid-density fitness (L47); anything outside M01's domain.

## W23 — PASS

(a)–(g), M04 §15's rows in order, met on numerical verification as M04 §15 states: step 13 at C, `m04_reference.py
--check` "11943 claims passed", `m04_schema_fixtures.py` exit 0, the M04 tests 858 passed, 0 skipped (junit
`9f199345…`); M04 and manifest nodes green in step 1 (its three platform-bound M04 skips covered by step 13). The real
verdict `NOT_PROMOTABLE` (`band_not_finite`) is recorded and read by the journey's R2; a PROMOTABLE real verdict is not
part of W23 (M04 N6). **Does not establish:** a promotable surrogate of the real reactor (L49).

## W24 — PASS

| Clause | Judgement | Evidence at C (step 14, `step14/rc-step14.json`, 5 of 5) |
| --- | --- | --- |
| (a) M03's NLP with final parent checks | met | nlp tier 212 passed, 0 skipped, over the 17 modules that carry the marker; the selection equals the whole-tree collection, 212 = 212 (RP.S20); inventory check exit 0; `M03 N1` stands at C |
| (b)–(e) TRF composition, TR-E2, FD truth accuracy and real-reactor accounting, parent checks and refinement | met | M03 and M05 tiers 679 passed, 2 skipped (the default-install answers, unobservable with Pyomo installed); `REPLAY PASS REAL differences=0` with host platform = record platform (`Linux-6.12.113+deb13-amd64-x86_64-with-glibc2.41`) |
| (f) constraints kept as constraints | met | the same tiers; the REAL record's content |
| (g) costs reported | met | the truth-ledger identity nodes in the tiers above; `m03_reference.py --check` byte-identical |

The REAL record compared at C was re-taken at J on this host; its re-take proof reads `version=0 platform=4 other=0
environment=equal`, so no number moved from 0.3.0's record (R-1008). **Does not establish:** global optimality; any
run outside the audited linux x86-64 nlp environment (L44); a promotable surrogate (L49).

## W25 — PASS

M07 §5's (a)–(h) on the journey record of J = `e0a3d6b7`, committed at `benchmarks/m07/journey/e0a3d6b7…/` and carried
to C by step 15 (`RC step 15: the journey at e0a3d6b7 carried`; `check: ACCEPT`; `replay: bitwise`; host platform =
record platform). Read here from the record: (a) R0 `INDIFFERENT`, R1 `DECIDED` 653.15 K, R2
`SURROGATE_NOT_PROMOTABLE` with M04's reasons verbatim and no surrogate evaluation, R3 `DECISION_STABLE` (M05 study
re-run at J; record sha256 `550da4af…`); (c) the decision `refined` at T = 653.1500351610193 K, `BOUND_LOWER`, with the
bound phrase on R1, R3 and the journey; (f) TC-1 holds (`best_grid_T` 653.15, nothing missing); (g) cold experiments R1
36 of 60, R3 48 of 400, journey 88 of 460, none exhausted. (b), (d), (e) and (h) are asserted by `check` (M07 A10–A26,
A61). Against 0.3.0's record at `2d945b5d`, 71 of 10794 leaves differ, all walls, digests, the commit and R3's M05
record reference (build log, part 2); every other number is bitwise equal. **Evidence class:** numerical verification of
a workflow over the group's model; the decision is a parent evaluation, not an optimality certificate. **Does not
establish:** the objective beyond the lower bound of the reactor's registered domain (stated in the record); replay on
another kernel or host (RP §4.5, L44); validation against data (L46).

## W26 — PASS

(a) as RP §4.6 states it while W27 is not claimed (RP.S19): step 16, 4 of 4 — `a60.w26.m06_tests` with
`OPENFLOWSHEET_REQUIRE_BROWSER=1`, 668 passed, 0 failures, 0 errors, 0 skipped; `node --test` 105 of 105, 0 skipped;
`a60.w26.g15_registered_states`, the 25 named nodes once each, all passed, 0 skipped; `a60.w26.w27_v1_refusal`, exit 1,
last line exactly `benchmarks.m06.w27.snapshot.SnapshotUnsupportedError: registry_snapshot: unsupported(provider
'iapws95-v1': no registered records and phases, W27-R63)`, no `summary.json`. (b) CI x86-64's `check` exports
`OPENFLOWSHEET_REQUIRE_BROWSER=1` (read in the job log) and skips no browser node (the only browser skip is aarch64's
collection skip). **Travelling limitation (RP §4.6), verbatim:** `G14 not judged at 0.4.0: W27 registration v1 refuses
this build (ADR 0050 D9, W27-R63); W27 not claimed`. A reading of "M06 G1–G15 met" is rejected (RP §4.6).
**Does not establish:** G14 or the W27 preflight on this build; usability or accessibility beyond headless Chromium
(L-WEB-3).

## X31 — FAIL on X31 (c)

Judged by RP §4.3, which pre-registers (c)'s reading. It is applied here, not chosen.

| Clause | Judgement | Evidence at C |
| --- | --- | --- |
| (a) RC1–RC4 solve and their registered matches hold | met | S02's M1–M4 at `P_r`, S03/S09's A10 (i) byte-identity and (ii) live-solve classifications, in step 1 on both architectures (no S02, S03, S09 module in either skip file); S02 `1810dde8`, S03 `930aad1b`, S09 `4d4df087` manifests `tested` at ancestors of C |
| (b) invalid specifications and phase cases refused with their registered typed outcomes | met | S02's invalid-specification tests, S08's phases clause (R-736), S08b, S10c's column cases, in step 1 on both architectures, none skipped; S08 `6d7d1a6d`, S08b `acbd1266`, S10c `8f38f963` manifests `tested` at ancestors |
| (c) S09's three-tool outcome "met with two references" | **not met** | `docs/reviews/S09-verdicts.md` verdict 3, unchanged since 0.3.0's candidate (git diff empty, with `benchmarks/s03/` and `benchmarks/s09/`): **"met where available, 3 of 4"** (target 4). RC4, the refluxed absorber, has one reference (BioSTEAM). RP §4.3: any outcome other than "met with two references" is FAIL (c), stated in its registered words |

Releasable by the standing `X31 (c)` row (stands at C; fingerprint recomputed here), with the notes' phrase 13 (`X31: one
independent reference for the refluxed absorber`). **Does not establish:** "met with two references" (R-643's watch
item); validation of any column against data (L-COL-8); a reference for RC4 beyond BioSTEAM.

## Findings (step-18 inputs and design-lane items; none changes a verdict above)

- **F-1 (Frank's first message).** The replacing `V17 carry` row must name the eight links R-192, R-234, R-295, R-934,
  R-950, R-960, R-1000, R-1010 and the served digest `6be1c002592524126617af8dd65d331513f4a96355f5381dba020ad561a2ba57`,
  cover "V17, and T08.B50's surface" as the lapsed row did, be dated on or after 2026-11-10, and carry the fingerprint of
  its scope at C (`extract:links + extract:served_digest`). Without it V13 and V17 stay BLOCKED and step 18 cannot give
  YES.
- **F-2 (notes, before step 18).** No line phrase carries alpha §6.1 (f4)'s four reactor statements, so the gate will
  not catch their absence. The `## v0.4.0` section must carry L46 (or the four statements, as 0.3.0's notes did). W21's
  PASS rests on this; if the tag candidate's notes lack it, W21 must be judged again.
- **F-3 (RP text, for the design lane before step 4).** RP §4.4 and RP.S14 name 0.3.0's chain literally: rows
  `[(1,c_3),(2,c_3),(2,c_2),(2,c_1),(3,None)]` and D_3 = `455d01eb…e125`. At C the chain has eight links, the rows are
  `(1,c_8)`, `(2,c_8)` … `(2,c_1)`, `(3,None)`, and the served digest is D_8. This verdict reads RP.S14 in its general
  form ("the last link's registered digest", rows as `LINKS` gives them), which is what step 8 and
  `test_m07a_a37_the_chain_holds_on_the_served_list` check; V13 and V17 are BLOCKED under either reading. The release
  manifest's RP.S14 judgement will meet the same text; an RP amendment restating §4.4 for an n-link chain should come
  first, so the manifest is not judged on a sentence written for three links.
- **F-4 (envelope text).** L-WS-2 still reads "no request-named source exists in v0.1 (v0.2, M03)". ADR 0070 (X02)
  realised the explicit source (`explicit-v1`, `solve_body.warm_start`). The row should be restated so the notes do not
  understate 0.4.0, and V13 (e)'s evidence does not cover the explicit source.

- **F-5 (grammar, for the design lane).** The verdict reader's limitation pattern (`v0_2_gate.LIMITATION`,
  `L` + two digits or `L-<LETTERS>-<n>`) does not accept envelope ids whose middle part has a digit: `L-X04-1` to
  `L-X04-3`, `L-S11-1` to `L-S11-3` and `L-E01-1`. They cannot be named in a row's travelling column, so a gate they
  bear on (here V11, for L-X04-1 to L-X04-3) cannot carry them by id. Either the pattern or the ids should change, by
  the design lane; until then these rows reach the notes only through the envelope (MR-4).

## Alternatives considered and rejected

1. **V13 and V17 PASS on the 2026-10-30 `V17 carry` row.** Rejected: the row lapsed on both terms at C (RP §8.3 (b));
   a lapsed row counts as absent; the row's own words are "with no new link at C".
2. **V13 and V17 FAIL.** Rejected: the missing input is Frank's decision, outside both lanes' authority (T08 §3.3);
   everything the lanes own for the chain exists and holds.
3. **V17 carried by F5's "content-only additions keep V17's carry".** Rejected: F5 covers MR-7's `list_models` and
   `solve_policies` content additions. The five new links change schemas, two change description texts, and one adds a
   tool.
4. **V14 BLOCKED or PASS because its acceptance lapsed.** Rejected: the clause fails on measurement at C; an acceptance
   decides releasability, never the verdict word.
5. **V14 judged "unchanged at C" by source comparison, as 0.3.0 did.** Unnecessary: the comparison was run at C.
6. **X31 written "met with two references".** Rejected by RP §4.3 (R-643).
7. **W21 FAIL on (f), or met on the verdict's half only.** Rejected for the reasons in W21's section; the condition
   travels as F-2.
8. **W26 "M06 G1–G15 met".** Rejected by RP §4.6.
9. **Treating the 3 `test_msg_corpus` junit skips, or the orchestrator's 3206 local skips, as clause inputs.** Rejected:
   the first are strict xfails in no gate's tests; the second come from a different install and gate nothing here; the
   clause inputs are CI step 1 and the local steps, audited above.

## What would change these verdicts

- Frank's dated `V17 carry` row as F-1 states: V13 and V17 judged again at the same C (expected PASS if nothing else
  has moved; the re-judgement re-reads nothing but the row). His choice of a new V17 campaign: V17 judged on its record.
- Frank's dated `V14 (b)` row: V14 stays FAIL, releasable.
- The tag candidate's notes without L46 or the four statements: W21 judged again (F-2).
- Any record at C whose bytes differ from `rc/records.json`, any step re-run at C with another result, or a new C:
  every row judged again.
- An RP amendment that changes §4.3, §4.4 or §4.6: the affected rows judged again under it.

## What this does not establish

- Agent behaviour on the 0.4.0 surface: no agent ran on it (L12); V17 is BLOCKED.
- Empirical validation of anything beyond W22 (c)'s pure-component bands. The reactor's validation is the group's,
  cited (L46); SYN-001 and its columns are synthetic (L18, L-COL-8).
- Optimality: the journey's decision sits at the lower bound of the reactor's registered domain; no global optimality.
- Portability: the reactor, the journey, steps 11–16 and W24's environment are measured on one Linux x86-64 host;
  steps 14 and 15 replay only on that kernel (RP §4.5).
- The capabilities 0.4.0 adds that no claimed gate covers (MSG, X02, OPT, ST, X04, and the E01, S05–S11 additions since
  0.3.0): their tests are in step 1 and some in step 17, but no verdict here is about them; their limitations travel in
  the envelope and the notes, not in a row of this table.
- Human numerical and process-modeling sign-off, which is recorded separately and is not claimed here.
