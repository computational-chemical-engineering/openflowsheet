# REL051: verdicts on V11–V20, W21–W26 and X31 for `0.5.1`

**Release candidate:** `ee934680d94879032b34ae8649baa31ff5a210c8`   **Judged:** 2026-11-23   **By:** design lane (`verdict` agent)

*RP §4.7 and §9.2 step 3 (`docs/derivations/release-procedure.md`). Line `0.5` (`release/lines/0.5.json` at C', gate
set `v0.5-gate-v1`; claim set, `clause` and `gates[*]` 0.5.0's unchanged; `covers` widened to 0.5.1, `packages` + X32,
`evidence_package` REL051 by RP amendment A-14, envelope `v0.5-envelope-2`), K3' = `8f7ce045`, J' = `6cf18bb1`, host
SMM-TR09 (`ref-x86-64`). Seventeen claimed gates, judged at C' on C''s records and on the two registered carries that
reach C': the journey from J', and V17 by the user's `V17 carry` row. W27 is not claimed and has no row. With D2
deferred every row is judged here. Baseline: `docs/reviews/REL050-verdicts.md` (C = `0a800e69`, judged 2026-11-22);
each of its rows was re-judged on C''s evidence, none carried unchecked. In what follows C' is `ee934680` and `<C'>`
in a path is its full id. For 0.5.1 the user's answers in the session chat replace Decision Desk cards (REL051 state).*

| Gate | Verdict | Failing clauses | Travelling limitations | Basis |
| --- | --- | --- | --- | --- |
| V11 | PASS | — | L38, L-X04-1, L-X04-2, L-X04-3 | T08 §4.1 with MR-10; K06, T01, T06 and T07 nodes, T08.A10, T08.A35 and M07a.A42 green in step 1 on both Linux legs (push run 45204749193 at attempt 2: x86-64 21113 passed, aarch64 21083 passed, no failure); X32's T07 pin change keeps the grant pinned exactly (read here) |
| V12 | PASS | — | L02, L26, L27, L28, L29, L30, L-CSTR-1, L-CSTR-2, L-CSTR-3 | T08 §4.2, denominator unchanged; T05, T05b and B10–B19 nodes green in step 1 on both Linux legs, none skipped |
| V13 | PASS | — | L10, L22, L23, L24, L36, L38, L43, L-WS-1, L-WS-2 | T08 §4.3 and T08.A71 with MR-7; T01, T02, K03 and B40–B49 nodes green in step 1; B50's counterpart: M07a.A51 green in step 1, digest and schemas by step 8 on three hosts (12 chain rows), under the user's `V17 carry` row, which stands at C' (fingerprint `9f4fb274…6615` recomputed here at C' and at `0a800e69`) |
| V14 | FAIL | V14 (b) | L01, L08, L20, L21, L43, L-COL-10 | T08 §4.4 with T08-verdict-V14b.md; measured at C': step 17's PTC-R1 item ran case `cfa994fe…` on both legs of dispatch 45204778756; recounted here from the raw records, PTC ends `MID` from 149 of 441 starts on ci-aarch64 and on ci-x86-64; T04, T02 and T08.A33 nodes green in step 1; the standing row lapsed at C' (`src/openflowsheet/__init__.py`, `application/cli.py`), so the user is asked after `Judged` (F-1) |
| V15 | PASS | — | L02, L14, L19, L20, L33, L-COL-5 | T08 §4.5; T02, T03 and T06 (ADV-05, THM-09) nodes green in step 1 on both Linux legs; step 10 77 certificates, 0 violations, on the local host and every CI leg |
| V16 | PASS | — | L16, L17, L18, L32 | T08 §4.6; `docs/reviews/T06-verdicts.md` unchanged; T08.A48 (T06.A47, T06.A50) passed at step 7 on ref-x86-64, ci-x86-64 and ci-aarch64, 12 of 12 each |
| V17 | PASS | — | L11, L12, L13 | T08 §4.7 with MR-1, MR-2, MR-6 and RP §4.4; the user's `V17 carry` row (ten links) stands at C' (`9f4fb274…6615`, recomputed here); step 8 on three hosts, 15 of 15 each: rows (1,c_10), (2,c_10) … (2,c_1), (3,None), served `f7ec3c94…d467` = D_10, the strips give `e2c44b6b…` … `171dd768…`, with v17-c2's texts `6d13e13d…`; G16-b 40 of 40 clean |
| V18 | PASS | — | L03, L05, L06, L15, L19, L25, L34, L37, L39, L40, L41 | T08 §4.8 with MR-11 and MR-12; T08.A30 PASS on three hosts (353 modules walked, 348 imported, five nlp-extra modules refused; 381, 381 and 308 objects; required closures 150, 150, 147; nothing undispositioned; METIS not reached); extras unchanged; step 17's MR12 items pass; licence rows stand (recomputed here) |
| V19 | PASS | — | — | T08 §4.9; ADR 0022 Accepted (R-145); `docs/v02-real-chemistry-dossier.md` and `benchmarks/t08/v19/` unchanged C..C' (git diff empty); A60–A64 nodes green in step 1 |
| V20 | PASS | — | L04, L07, L09, L31, L32, L38 | T08 §4.10; T08.A46 S = 437 of 440 on ref-x86-64 and ci-aarch64 (gate 418), 3 F-FALSE-SUCCESS-CAUGHT, same-class replay 25 of 25; T08.A47 12 of 12 on three hosts, worst success ratio 0.0968 |
| W21 | PASS | — | L05, L06, L07, L15, L19, L20, L44, L45, L46, L48 | alpha §6.1 (ADR 0028 D7) with RP §6.4; step 12 at C': G10v3, G11v3, G12 met, reproduce MATCH, VERIFIED; `r375.audit` 210 of 210 results, 0 problems; reactor pin `6089593…`; `M02 N1` stands at C' (recomputed here); the four reactor statements are stated in W21's section and travel with this row's ids into the notes (F-2) |
| W22 | PASS | — | L42, L47 | alpha §6.2; step 1: M01.A05–A22, A34, A37, M02 G7, G8 nodes; step 11: cross-check matches (0.012675, 0.040096, 0.042371 against 0.02, 0.05, 0.05); IDAES re-run equals the committed record `add9557a…`, no differing member |
| W23 | PASS | — | L49 | M07 §7.3 and M04 §15; step 13 at C': 11943 claims passed, schema fixtures exit 0, 961 nodes, 942 passed, 19 archived-history skips, all 281 M04 nodes passed (including the two x86-64 platform skips of step 1) |
| W24 | PASS | — | L19, L44, L46, L48, L49 | M07 §7.3 and RP §6.5; step 14 at C': nlp tier 213 passed, selection 213 = 213; M03 and M05 tiers 713 nodes, 711 passed, 2 skipped; REAL replay differences 0, host platform = record platform; M03 reference byte-identical; `M03 N1` stands at C' |
| W25 | PASS | — | L44, L45, L46, L48, L49 | M07 §5 on the journey of J' = 6cf18bb1 (RP §4.5): step 15 carried, check ACCEPT, replay bitwise; refined at 653.1500351610193 K, BOUND_LOWER, TC1_HOLDS; R1 36 of 60 cold, R3 48 of 400 cold, none exhausted |
| W26 | PASS | — | L-WEB-1, L-WEB-2, L-WEB-3, L-WEB-4 | M07 §7.3 with its first clause as RP §4.6 states it (RP.S19): step 16 4 of 4 (668 M06 nodes, 0 skipped; node 105 of 105; the 25 named nodes passed; the W27-R63 refusal exact, exit 1, no summary); CI x86-64 exports the browser requirement. G14 not judged at 0.5.1: W27 registration v1 refuses this build (ADR 0050 D9, W27-R63); W27 not claimed |
| X31 | FAIL | X31 (c) | L-COL-1, L-COL-2, L-COL-3, L-COL-4, L-COL-5, L-COL-6, L-COL-7, L-COL-8, L-COL-9, L-COL-10 | RP §4.3 as pre-registered; RC1–RC4 and the refusals green in step 1 on both Linux legs; S09 verdict 3 unchanged: "met where available, 3 of 4" (RC4 has one reference, BioSTEAM); the standing acceptance row stands at C' (`59503316…1864`, recomputed here) |

## Read this first

**The seventeen.** Fifteen PASS (V11, V12, V13, V15, V16, V17, V18, V19, V20, W21, W22, W23, W24, W25, W26). Two
FAIL: V14 on clause (b) and X31 on clause (c). None BLOCKED. 15 + 2 + 0 = 17. The words are 0.5.0's; every row was
re-judged on C''s records.

**What 0.5.1 changes under the gates.** From C to C' the D2.4 paths change in five files outside the re-taken records
(42 under `benchmarks/m05/`, 12 under `benchmarks/m07/journey/`): the two version files, `README.md`, the envelope and
`src/openflowsheet/application/cli.py` (X32: the grant's human lines move to stderr, the token alone to stdout). No
numerical code changed. Every judged record's check list equals 0.5.0's (compared here record by record, 53 of 53),
and every number quoted below equals 0.5.0's.

**What blocks the tag today. Two step-18 inputs, one of them a stop.**
1. **V14 (b) has no standing row at C'** (F-1). Its row of 2026-11-22 lapsed by its `paths:` scope because X32 and the
   version changed two files under `src/openflowsheet/`. V14's FAIL is not releasable until the user's new row.
2. **RP.S02 fails on the 0.5 line at C' (F-7; an RP §12 stop: A-14 is incomplete in a way that changes a step-18
   input).** RP §11.1 registers `M.m.1` as *not covered* by a line's `covers`; A-14 widens `covers` to admit 0.5.1.
   Measured here: `release_evidence_manifest._m_version_table` on the line at C' gives `fail`, `misclassified:
   ['0.5.1']`. The generator writes `tested` only when every check passes, and step 18 refuses a release manifest that
   is not `tested`. So §9.2 step 4 cannot produce a `tested` manifest and step 18 will give NO. This verdict reports
   it and does not choose the fix (A-14 section). It changes no gate verdict.

**Standing.** An agent verdict, numerical and procedural only. It is not scientific review, and it is not the human
numerical and process-modeling sign-off, which is recorded separately and which no agent may claim. It sets no
manifest to `reviewed`, moves no tolerance, band or classification rule, and edits no record.

**Criteria, read before the evidence:** RP §4.1–§4.7, §5.2, §8.3–§8.5, §3.1 D1.5, §3.4 RP.L11, §11.1 RP.S02 and
RP.S22, §17.3 (A-10) and §17.7 (A-14); the clause criteria §4.2 names, unchanged since 0.5.0's verdict. RP changed
C..C' by A-14 only (git diff read here).

## The user's answers each row waits on (`release/acceptances.md` at C', unchanged since; lapse report of 2026-11-23)

Every fingerprint below was **recomputed here with independent code** from RP §8.2's definitions (`git ls-tree -r -z
--full-tree`, `ast` on `LINKS`, the step-8 records, `tomllib`), at C' and at each row's `Accepted at`. It agrees with
the committed lapse report on all seven rows.

| Item or clause | State at C' | Rows that wait on it | When it is asked |
| --- | --- | --- | --- |
| `V14 (b)` | **lapsed**: changed paths `src/openflowsheet/__init__.py`, `src/openflowsheet/application/cli.py`; fingerprint at C' `5718167d51f860377e9ec03dd80ebd6e6081b2492dcb54f13915a6f418ccf509` against the row's `82469c08…2c40`, which reproduces at its `Accepted at` `0a800e69`: lapsed, not unsupported | V14 FAIL: not releasable until a new row | after `Judged` (RP §8.4, §8.5); dated on or after 2026-11-23, Accepted at C' |
| `V17 carry` | stands (`9f4fb274…6615`, equal at C' and at `0a800e69`) | V13 (e) and V17 (a): met | not asked |
| `M02 N1` | stands (`7de4c931…4680`, equal at C' and at `0a800e69`) | W21 (c): met | not asked |
| `X31 (c)` | stands (`59503316…1864`, equal at C' and at `a3e508e3`) | X31 FAIL, releasable | not asked |
| `M03 N1` | stands (`8eafbfef…a430`) | W24 (a): met | not asked |
| `coolprop and lca licences` | stands (`0bb1c634…2ce7`) | V18 (MR-12): met | not asked |
| `Claim set` | stands (`f4a3cfbe…a881`) | the claim set judged here | not asked |

No decision item lapsed, so RP §8.5's first message was empty and no row waited on it.

## Evidence and provenance

| Evidence | Produced by, where | Independent expectation | Class |
| --- | --- | --- | --- |
| RC record `docs/REL051-rc-record.md` (69 rows, 0 failing) | build lane, SMM-TR09 from a clean detached worktree at C', three `release_rc.py local` invocations, then `ci`, `step1`, `records` (system gh 2.105.0) | none: it reports | record |
| The 126 cited records (`rc/records.json`) | as above; 6 gzip-compressed | **recomputed here: 126 of 126 SHA-256 and byte counts equal**; the RC record's 123 distinct 64-hex tokens are all in `records.json` | provenance |
| The 53 `t08-rc-v1` records | the records | checked here: each has `provenance.commit` = C' and `tree_clean` true, every check `pass`; each record's (id, result) list equals 0.5.0's committed record at the same path | provenance |
| Step 1 | CI push run 45204749193, **attempt 2** (`s1.push_run` attempt 2, `success`); attempt 1 failed on `check (ubuntu-latest)` only, "The hosted runner lost communication with the server", no test result | summary lines grepped here: x86-64 21113 passed, 120 skipped, 223 deselected, 3 xfailed; aarch64 21083, 118, 223, 3; 0 FAILED/ERROR lines | tested (CI) |
| Steps 2–17 | local and CI legs (dispatch 45204778756, attempt 1) | as at 0.5.0: registered digests, S_min, A34's rule, M01/M02 bounds, IDAES's own numbers, reference EOS bands, committed records | identity verification; tested; numerical verification; empirical validation (W22 (c) only) |
| Re-take proofs at K3' (RP §7.1) | build lane, committed at J'; decisions log 2026-11-23 | five G10 `platform=0 other=0 environment=equal host=0`; REAL `version=0 platform=0 other=0 environment=equal host=0`; IDAES byte-identical; **read from the log, not re-run here** | provenance |
| Journey at J' | build lane, `PYTHONPATH=src` (0.5.0's line, F-3 of 0.5.0) | `check` ACCEPT and replay bitwise at C' (step 15); 71 of 10794 leaves differ from 0.5.0's record, all walls, digests, the commit and R3's M05 record reference (log; not re-diffed here) | numerical verification; replay |
| Local full gate at C' | `GATE PASS ee934680: 21126 passed, 107 skipped, 223 deselected, 3 xfailed` | none beyond the suite | tested (quoted; gates nothing) |
| Acceptance fingerprints | committed lapse report | recomputed here independently (table above) | provenance |

**What pins nothing.** Wall times. A record that recomputes to the same bytes shows determinism, not correctness:
steps 14 and 15 compare against records taken at J' on the same host the same day; their link to 0.5.0's numbers is
the re-take proofs (`other=0` in each), read and not re-run. Step 17's PTC-R1 item `pass` means the comparison ran to
completion (N-2); V14's measurement is the class counts. The step-13 junit count 961 (0.5.0: 949) is 12 more
`test_evidence_manifests` cases for manifests added since C; it gates nothing. A30's `files_digest` of 8 pure-Python
distributions differs from 0.5.0's at unchanged versions; the build lane infers the venv path and did not trace it;
objects, closures and checks are equal, and no clause reads that digest.

## V11: PASS

(a) T07 `diff_revisions`/`semantic_diff`, (b) K06 revision nodes, (c) T01 STR-01…06 and R-022's rule, (d) T06 A43,
A55–A57, A67–A74, THM-05 and T01 A09, (e) T08.A35 and M07a.A42: green in step 1 on both Linux legs at attempt 2. X32
changed `tests/test_t07_authz.py`, `tests/test_t07_w5b_cli.py` and the T07 pins file: the pin now holds the grant's
new streams exactly (`stdout` `"<TOKEN>\n"`, three lines and the note on stderr), and the history comparison reverses
exactly that one entry after asserting there is one; no assertion is relaxed. **Does not establish:** gauge-pressure
input; migration of instances emitted after `v0.1.1` beyond step 5's 52 bundles.

## V12: PASS

As at 0.5.0, on C''s step 1: every model of §14.3's list has passing contract, limiting/failure, balance and
derivative nodes and a coupled case (T05, T05b, B10–B19), none skipped on either leg. **Does not establish:** units
outside the list.

## V13: PASS

(a) T01, (b) T02 A13–A15, A32, A34 (E1/E2 library-level, L43), (c) K03 and T02, (d) K03 §10.1 (L10), (e) B40–B49 in
step 1, and B50's counterpart under MR-7: M07a.A51 in step 1 (in neither skip file), digest and schemas by step 8 on
three hosts under the `V17 carry` row, which stands at C'. **Does not establish:** agent behaviour on the 0.5 surface;
warm starts beyond exact id-set compatibility (L-WS-1, L-WS-2).

## V14: FAIL on V14 (b)

| Clause | Judgement | Evidence at C' |
| --- | --- | --- |
| (a) one typed homotopy | met | T04 A02–A12 nodes in step 1, both Linux legs |
| (b) one PTC family qualified by §7.5 with tested SER | **not met** | (b1)'s saddle clause fails, measured at C': step 17's `PTC-R1` item ran T08's registered comparison (case `cfa994fe…`) on both legs of dispatch 45204778756, results with `provenance.commit` C'. Recounted here from `results-ci-aarch64.json.gz` and `results-ci-x86-64.json.gz`, 441 starts per arm: Newton LOW/MID/HIGH/FAIL 113/161/166/1, PTC 182/149/109/1 on both legs. PTC ends `MID` from 149 starts on `ci-aarch64`, a registered platform; `ci-x86-64` gives the same. T08-verdict-V14b.md's counts; its verdict is FAIL on the saddle clause |
| (c) three recovery edges | met | T04 §5.5's edges, T02 and T08.A33 nodes in step 1 |

`benchmarks/t08/ptc_r1/` is unchanged C..C'. The skips of `test_t08_ptc_r1_diagnostic` (6, x86-64) and
`test_t08_ptc_r1_case` (2, history) cannot change a FAIL. **Acceptance:** the row lapsed at C' (F-1). **Does not
establish:** that PTC is useless elsewhere; any other PTC family.

## V15: PASS

(a) T03 A00–A26, (b) T02 (A02), (c) T03's root fingerprint and branch provenance, T06 ADV-05 (A15) and THM-09 (A31),
green in step 1 on both legs. Step 10 at C' audited 77 certificates under A34 with 0 violations, as did each CI leg
(`rc-steps` both legs, `clean-install` both legs, `bundle-set`). **Does not establish:** root completeness,
uniqueness or stability (L19); any column multiplicity claim (L-COL-5).

## V16: PASS

T06 verdict 1 stands (`docs/reviews/T06-verdicts.md` unchanged). T08.A48 at step 7 (`corpus-ref-x86-64.json` and both
CI copies, 12 of 12 each): T06.A47 and T06.A50 passed on three hosts, none skipped. **Does not establish:** agreement
beyond the registered near-sharp ε (L16); DWSIM's environment past .NET 8's end of life (L17).

## V17: PASS

- **(a) met.** Step 8 at C' on three hosts (`surface/rc-alpha-surface.json` and both CI copies, 15 of 15 each). Read
  here: `a37.item1.c_10_r1051` found `f7ec3c94…d467` = D_10 (R-1051); `a37.item2` c_10 … c_1 found, in order,
  `e2c44b6b…`, `6be1c002…`, `553b7612…`, `3fdc797a…`, `f51b69bf…`, `eaff4585…`, `455d01eb…`, `383b4e2c…`, `6c4375b4…`,
  `171dd768…` (D_9 … D_0); `a37.item3.r137` `6d13e13d…`; `a37.item4` no problems. Twelve rows, n + 2 with n = 10, in
  RP §4.4's order. `LINKS` (ten registers) recomputed with `ast` at C' and at `0a800e69`: equal. The `V17 carry` row
  stands at C' and at its `Accepted at`, so `v17-c2`'s evidence carries to C'.
- **(b) met.** G16-b 40 of 40 clean on three hosts; `a16` attributable.

**Does not establish:** agent behaviour on the 0.5 surface; F1's and F3's seven tools have not been driven by an agent
(0.5.0's F-5 holds unchanged). X32 changes the CLI's `project grant` streams, which no chain link covers (the chain
covers the MCP surface's tools and descriptions; step 8 passes).

## V18: PASS

(a) T08.A30 PASS at C' on `ref-x86-64`, `ci-x86-64` and `ci-aarch64` (read here: 353 modules walked, 348 imported,
the five nlp-extra modules refused as registered; 381, 381 and 308 objects; required closures 150, 150, 147; no
undispositioned object; METIS not reached). MR-12: `pyproject.toml`'s optional dependencies equal 0.5.0's (the
`pyproject_extra` terms recompute equal); the licence rows stand; step 17's MR12-coolprop and MR12-lca items pass.
X05's lock checks pass on both legs (step 4). (b)–(d) T06 A32, A33, A37–A46 and T08.A33 nodes in step 1; T08.A34 0
violations over 77 certificates. **Does not establish:** closures beyond the audits; a licence opinion.

## V19: PASS

(i) ADR 0022 Accepted with Frank's selection (R-145); (ii)–(v) the dossier and `benchmarks/t08/v19/` unchanged C..C',
A60–A64 nodes green in step 1; the one `test_t08_w1_ledger` `[V19]` skip is the parametrization not expected in A02.
**Does not establish:** a comparison of the selected chemistry with data by this project.

## V20: PASS

(a)–(c) T08.A47 at step 7, 12 of 12 on three hosts; T08.A10 in step 1. (d) T08.A46 at step 6 with the registered
starts: S = 437 of 440 on `ref-x86-64` and on `ci-aarch64` (gate 418), the other 3 `F-FALSE-SUCCESS-CAUGHT`;
`a46.registered_class` passes on `ref-x86-64`; no `VERIFIED` outside S3 (worst success ratio 0.0968); A33 0 failures;
same-class replay 25 of 25 on each class. The Clopper–Pearson figure (0.98247 at 437 of 440) is 0.5.0's computation;
the count is unchanged; it is reported, never gated.

## Skip audit (step 1 at attempt 2, R-376)

0.5.0's table (`docs/reviews/REL050-verdicts.md`, "Skip audit") holds for C' line by line, with one change. The
aarch64 skip set equals 0.5.0's exactly (121 junit lines = 118 + 3). The x86-64 set is 0.5.0's plus two lines (123 =
120 + 3), both M04 platform-bound on this attempt's runner:

| New reason (file) | x86-64 | aarch64 | Clause input? |
| --- | --- | --- | --- |
| `test_m04_quadratic::test_a49_…_at_one_and_eight_blas_threads`: "the negative control is vacuous on this host's BLAS" | 1 | 0 | Covered: step 13 ran it on `ref-x86-64`, passed |
| `test_m04_schemas::test_a35_the_fixtures_are_what_the_code_emits_today`: "floats compared on x86_64/Haswell only … this is x86_64/SkylakeX" | 1 | 0 | Covered: step 13 ran it, passed |

Step 13's junit at C': 961 nodes, 942 passed, 19 skipped (the archived-history `test_evidence_manifests` nodes, as
at 0.5.0, F-4 of 0.5.0), all 281 M04 nodes passed, both nodes above among them. The 223 deselected (0.5.0: 222) are
the `nlp` and `pymrm` markers run at steps 14 and 12; the one added node was not traced here and is not a clause input
of step 1. The CPU change between 0.5.0's runner and attempt 2's is CI's assignment, not a change at C'. No clause
judged here rests on a node skipped at every place it could run.

## W21: PASS

Judged by alpha §6.1 as ADR 0028 D7 reads it, with RP §6.4. Read here from `step12/rc-step12.json` (6 of 6) and
`step12/experiments/rc-step12-experiments.json` (1 of 1):

| Clause | Judgement | Evidence at C' |
| --- | --- | --- |
| (a) port mapping | met | M02 G4, G8, G9 nodes in step 1; step 12's M02 tests with the reactor 573 nodes, 0 failures, 1 skip (A47 (a)'s node; (b) decides); A47 (b) 1.43 × 10⁻⁸ against 10⁻⁶ |
| (b) accuracy contract | met | A42 1.56 × 10⁻⁸ (10⁻⁶); A45 3.84 × 10⁻⁸ (10⁻⁷); A46 5.06 × 10⁻⁵ (10⁻³); A48 estimates equal the reference on all three; G12 floor ratios 13.30 (T) and 65.32 (ξ) against ≥ 10 |
| (c) out-of-process execution policy | met | G3–G5 nodes in step 1; `docs/support-matrix.md` at C' still states `external-subprocess-v1`, "not a sandbox", Linux registered, Windows refused; `M02 N1` stands at C' |
| (d) timeout | met | G3 (b) node; G12 `VERIFIED` in 4 outer iterations; G11v3 met (V5, two runs of 121 points, all equal) |
| (e) provenance | met | G6 nodes; `r375.audit` pass, "2 runs, 210 boundary points, 210 results, 210 attempts, 0 without a result" against step 12's own runs file; G10 (g) A47 (a) bitwise; G12 reproduce MATCH, bitwise floats; reactor commit `6089593464fc…` = ADR 0022's pin |
| (f) parent-model validation | met | (f1)–(f3) as at 0.5.0 on C''s numbers above; (f4) **stated here**: the group's published comparison with experimental data (Gargiulo et al. 2025 §3.1, of Rossetti et al. 2006's rate law) is the group's evidence; this project has compared no reactor result with data; the numbers are the group's model at the pin, a regression; their discretization bias is 1.0–1.4 % in NH₃ (M02 §13). The notes' half is L46, which this row carries (F-2) |

**W21 does not establish:** that the reactor is right (L46); aarch64 or cross-machine runs (L44, L15); a sandbox,
Windows support or concurrency across hosts (L45); coupled-loop convergence beyond G11's corners and centre (L48).

## W22: PASS

(a) M01.A05–A22, A34 in step 1. (b) M01.A37 in step 1; step 11's IDAES re-run equals `benchmarks/m01/idaes-conformance.json`
(`add9557a…`, `differing_members` []), whose re-take at J' was byte-identical. (c) empirical validation of
pure-component behaviour: step 11's `external_crosscheck.py --check` "external-crosscheck.json matches"; the record
holds 0.012675 against M01.A38's 0.02, 0.040096 against A39's 0.05 and 0.042371 against A40's 0.05 (R-160's
validation bands, not tolerances). (d) G7, G8 nodes; G12 `VERIFIED` on `pr-c1-v1`. **Does not establish:** mixture
VLE; the near-critical region; liquid-density fitness (L47).

## W23: PASS

(a)–(g), M04 §15's rows, on numerical verification: step 13 at C' (3 of 3): "11943 claims passed", schema fixtures
exit 0, 281 M04 nodes passed, none skipped; M04 and manifest nodes green in step 1. Amendment 4 (R-1068) read as at
0.5.0; unchanged since. **Does not establish:** a promotable surrogate of the real reactor (L49).

## W24: PASS

| Clause | Judgement | Evidence at C' (step 14, `step14/rc-step14.json`, 5 of 5) |
| --- | --- | --- |
| (a) M03's NLP with final parent checks | met | nlp tier 213 passed, 0 skipped; selection 213 = 213 (RP.S20); inventory exit 0; `M03 N1` stands |
| (b)–(e) | met | M03 and M05 tiers 713 nodes, 711 passed, 2 skipped (default-install answers); `REPLAY PASS REAL differences=0`, host platform = record platform `Linux-6.12.86+deb13-amd64-x86_64-with-glibc2.41` |
| (f) constraints kept as constraints | met | the same tiers; the REAL record |
| (g) costs reported | met | the truth-ledger nodes; `m03_reference.py --check` byte-identical |

The REAL record was re-taken at J' on this host; its proof reads `version=0 platform=0 other=0 environment=equal
host=0` (read from the log). **Does not establish:** global optimality; any run outside the audited linux x86-64 nlp
environment (L44); a promotable surrogate (L49).

## W25: PASS

M07 §5's (a)–(h) on the journey record of J' = `6cf18bb1`, committed under `benchmarks/m07/journey/6cf18bb1…/` and
carried to C' by step 15 (3 of 3: "RC step 15: the journey at 6cf18bb1 carried"; `check: ACCEPT`; `replay: bitwise`,
host platform = record platform). Read here from `journey.json`: (a) R0 `INDIFFERENT`, R1 `DECIDED` 653.15 K, R2
`SURROGATE_NOT_PROMOTABLE`, R3 `DECISION_STABLE` at 653.1500351610193 K (M05 re-run at J'); (c) decision `refined`,
`BOUND_LOWER`; (f) `TC1_HOLDS`; (g) cold experiments R1 36 of 60, R3 48 of 400, none exhausted. (b), (d), (e), (h)
asserted by `check`. Run with `PYTHONPATH=src`, 0.5.0's line (0.5.0's F-3, still unregistered). **Evidence class:**
numerical verification of a workflow over the group's model; the decision is a parent evaluation, not an optimality
certificate. **Does not establish:** the objective beyond the lower bound; replay on another kernel or host (L44);
validation against data (L46).

## W26: PASS

(a) as RP §4.6 states it while W27 is not claimed: step 16 at C', 4 of 4: 668 M06 nodes with
`OPENFLOWSHEET_REQUIRE_BROWSER=1`, 0 skipped; `node --test` 105 of 105; the 25 named nodes, each passed; the dry
run's exit 1 with the exact W27-R63 line and no `summary.json`. (b) CI x86-64 at attempt 2 exports the browser
requirement; the only browser skip is aarch64's collection skip. **Travelling limitation (RP §4.6), verbatim:**
`G14 not judged at 0.5.1: W27 registration v1 refuses this build (ADR 0050 D9, W27-R63); W27 not claimed`.
**Does not establish:** G14 or the W27 preflight on this build; usability beyond headless Chromium (L-WEB-3).

## X31: FAIL on X31 (c)

Judged by RP §4.3, which pre-registers (c)'s reading; applied, not chosen. (a) and (b) met in step 1 on both legs as
at 0.5.0 (S02, S03, S08, S08b, S09, S10c modules in neither skip file). (c) **not met**: `docs/reviews/S09-verdicts.md`
verdict 3, `benchmarks/s03/` and `benchmarks/s09/` unchanged C..C' (the `X31 (c)` row's `paths:` term recomputes
equal): "MET WHERE AVAILABLE, 3 of 4"; RC4 has one reference (BioSTEAM). Releasable by the standing row. **Does not
establish:** "met with two references"; validation of any column against data (L-COL-8).

## The release-machinery change (RP amendment A-14, R-1069)

**Judgement: RP.L11 as amended is sound against D1.5, A-10's purpose and RP.S22, and its controls falsify it. A-14 is
not complete: RP.S02 still assumes one release per line and fails at C'. That changes a step-18 input (F-7).**

- **D1.5.** The release of X.Y.Z has the id of X, Y and Z. `line_release` returns `<line>.Z` for the largest Z in
  0…9 999 that `covers` fullmatches, and RP.L11 requires `release_package_id` of it. At C' that is `0.5.1` → `REL051`,
  the version C' builds (`a43.version` `0.5.1`). Consistent.
- **A-10's purpose** (a line inheriting an unchanged `evidence_package`): a 0.5 line keeping `REL040` or `REL050`
  still fails (`REL050` is the new control), and a line covering `<line>.0` only still needs `<line>.0`'s id (the
  narrowed control). Kept.
- **RP.S22** (`_m_harvest`): measured here at C': `pass`, `harvest_excluded` `['evidence/REL051/']`, nothing under it
  at C', no excluded manifest, the `REL051x` sibling not excluded. Under A-10 it would fail (`evidence/REL050/0a800e69…/`
  holds 0.5.0's records), which is A-14's reason. Sound.
- **Controls falsify it.** `test_l11_a_patch_release_takes_its_own_id` and the A-10 tests: 14 L11 tests pass. Mutation
  run here in-process (no file edited): with `line_release` replaced by A-10's rule (`<line>.0`) or by the smallest
  admitted Z, the new test fails each time; the A-10 test passes under both, as it should (it guards the inherited id).
- **What still assumes one release per line.** Grep of `release_gate.py`, `release_evidence_manifest.py`,
  `release_rc.py` and `release.yml` for `.0`, `REL050` and `evidence_package`: `release_gate.py` derives every path
  from `gate_set.evidence_package`; `release_rc.py` names `REL040` only in a usage string; `release.yml` picks the gate
  by `<major>.<minor>` and the version from `pyproject.toml`. **`release_evidence_manifest.version_table` does**: it
  builds RP.S02's table T-V(M.m) from `M.m.0` and lists `M.m.1` as not covered, exactly as RP §11.1 registers it.
  Measured at C': `_m_version_table` → `fail`, `{'covered': 4, 'not_covered': 13, 'misclassified': ['0.5.1']}`. The
  suite did not catch it: `test_s02_and_s05_hold_for_the_committed_lines` is parametrized over lines 0.3 and 0.4 only.
  The release manifest's status is `tested` only if every entry passes (`status()`), and step 18's
  `manifest_problems` refuses a set manifest whose status is not `tested`. A-14's "Nothing else in RP changes" is
  therefore false.
- **Not chosen here (RP §12 stop).** Measured alternative: narrowing `covers` to 0.5.1 alone does not help; RP.S02
  then misclassifies five forms (`0.5.0`, `0.5.0b1`, `0.5.0rc1`, `0.5.0rc12`, `0.5.1`). What resolves it is an RP
  amendment of RP.S02's table for a line whose `covers` admits `M.m.Z` with Z ≥ 1 (for example: covered `M.m.0` …
  `M.m.Z` and their b/rc forms, not covered `M.m.(Z+1)`), with `version_table` reading `line_release`, a control, and
  the S02 test parametrized over the 0.5 line. That is a design-lane amendment and a user decision under the 0.5.1
  authority. By the D2.4 list (`scripts/`, `docs/derivations/` and `release/lines/` are not D2.4 paths) such a change
  needs no new C'; RP.S02 is a "same form" assertion under REL.A20 (§11.2), which the amendment must also address.
- **A side observation, no step-18 input.** RP.L11 ties the id to the largest release `covers` admits, not to the
  candidate's version. The widened `covers` also admits `0.5.0b<N>` and `0.5.0rc<N>`, whose D1.5 id would be REL050.
  Cutting a pre-release of a released version is meaningless and C' is 0.5.1, so nothing is affected now.

## What 0.5.1 changes for users (X32 and the README)

**X32.** `command_project_grant` at C' prints the capability, principal, rights and a note to stderr and the token
alone to stdout (read in the diff C..C'); the parser help says "alone on stdout". `tests/test_tok_grant_token_file.py`
checks that the docs page redirects `grant` into the file `serve-mcp` reads, that the page's recipe writes a token file
`serve-mcp` accepts, and that a file with the old five-line output is still refused. CHANGELOG's Unreleased bullet
states the break for scripts that parsed stdout and the stderr lines. Consistent; no numerical path touched.

**README Status at C'** (unchanged since C') against CHANGELOG `## v0.5.0` (+ X32) and the claimed gates. Checked:
the release dates equal the tags' (v0.3.0 2026-10-31, v0.4.0 2026-11-11, v0.5.0 2026-11-23); the "New in 0.4.0" list
equals v0.4.0's sections (OPT, X02, RRC, ST, X04, X05, MSG); "New in 0.5.0" equals X07a, F1, F3, X01 with "no solve
reads it yet"; "New in 0.5.1" is X32; "123 pure fluids" is CHANGELOG's CoolProp line; the six phrases of the claims
line each have a counterpart in v0.5.0's "What it is not"; the Wilson validation row rests on ADR 0047's held-out
data; nothing is said of W27, and no row claims PTC or two references for RC4. Nothing claimed that 0.5.x does not
ship. Findings:

- **F-8 (notes; no new C').** The claims line sends the reader to "What 0.5.1 claims, and what it is not" in the
  changelog. At C' there is no `## v0.5.1` section (X32 and the README fix are under `## Unreleased`). The notes must
  give 0.5.1 its own section with a "What it is not" list (or an explicit pointer to v0.5.0's), carrying the six
  phrases the README names, the two FAILs with their acceptance lines, W21's L46 (F-2) and W26's G14 sentence with
  `0.5.1`.
- **F-9 (notes; no new C').** CHANGELOG headings `## v0.5.0 — unreleased` and `## v0.4.0 — unreleased` remain after
  both were tagged, while the README now cites the changelog as the claims source. A wording fix in CHANGELOG (not a
  D2.4 path) when the notes are written.
- **F-10 (README wording; a fix needs a new C'; this verdict does not require it for 0.5.1).** Two omissions, neither
  a false claim: the lead's "Python, the `openflowsheet` command line, HTTP and MCP run the same operations with the
  same results" sits beside a Status row that lists cost estimation and LCA, which the changelog says are Python-only;
  and `optimize` ("New in 0.4.0") needs the nlp extra, which the Install table does not say. Both are stated in the
  changelog's "What it is not". Recommended for the next release's README pass.
- **F-11 (by design; no new C').** "Version 0.5.1 is released" and the quickstart's `v0.5.1` download URL become true
  only at the tag; until then the URL does not resolve. This is K3's string move (RP §7.1); the PyPI page shows it only
  after publication.

## Findings (step-18 inputs and design-lane items)

- **F-1 (the user's answer after `Judged`; step-18 input).** V14 (b) fails at C' without a standing row. The replacing
  row keeps the lapsed row's scope (`paths:src/openflowsheet/**,benchmarks/t08/ptc_r1/**,docs/reviews/T08-verdict-V14b.md`),
  carries its fingerprint at C' (recomputed here as `5718167d51f860377e9ec03dd80ebd6e6081b2492dcb54f13915a6f418ccf509`;
  the gate's own `Scopes.evaluate` is the authority), names C' as `Accepted at`, and is dated on or after 2026-11-23.
  The measurement it accepts is 0.5.0's exactly (149 of 441 `MID` on both legs). Without it step 18 gives NO for V14.
- **F-2 (notes; step-18 input, carried from 0.5.0).** The `## v0.5.1` section must carry L46, by the gate's table
  (W21's row lists it) or by the four statements. If it does not, W21 must be judged again.
- **F-7 (RP §12 stop; step-18 input).** RP.S02 fails on the 0.5 line at C' (A-14 section). Until an amendment resolves
  it, §9.2 step 4 cannot produce a `tested` release manifest and step 18 gives NO. No gate verdict depends on it.
- **F-3, F-4, F-5 of 0.5.0** stand unchanged: the journey's invocation line is still unregistered; step 13's 19
  archived-history skips recur; V17's carry has no agent run on 0.5's surface.
- F-8 to F-11: above.

## Alternatives considered and rejected

1. **V14 PASS or BLOCKED because its acceptance lapsed.** Rejected: the clause fails on measurement at C'; an
   acceptance decides releasability, never the verdict word (RP §4.1 item 1).
2. **V14 judged from step 17's PTC-R1 item `pass`, or carried from 0.5.0's verdict because "nothing numerical
   changed".** Rejected: the item asserts completion (N-2); the counts were recounted here from C''s raw records.
3. **X31 written "met with two references".** Rejected by RP §4.3 (R-643).
4. **The V14 (b) row treated as standing because X32's change cannot affect PTC.** Rejected: RP §8.3 reads the
   fingerprint, not a judgement of relevance; the row's scope is `src/openflowsheet/**`, two files under it changed.
5. **Step 1 judged on attempt 1, or failed because attempt 1 failed.** Rejected: RP §6.2 reads the push run at its
   latest attempt and lists every attempt; attempt 1's `check (ubuntu-latest)` ended on runner loss with no test
   result; attempt 2 ran the whole job and passed. A retry of an infrastructure loss is not a re-run to pass a failed
   test.
6. **The two new x86-64 M04 skips as a W23 gap.** Rejected: step 13 ran both nodes on `ref-x86-64` and they passed.
7. **A-14 judged sound on its own tests.** Rejected: its tests cover RP.L11; RP.S02's table, a registered standing
   assertion, contradicts the widened `covers`, measured at C'.
8. **Resolving F-7 here by narrowing `covers`.** Rejected on measurement (five misclassified); and choosing an RP
   amendment is not this verdict's to make (RP §12).
9. **A new C' for F-10.** Not required by any criterion: the README makes no false claim; the omissions are stated in
   the changelog.

## What would change these verdicts

- The user's dated `V14 (b)` row as F-1 states: V14 stays FAIL, releasable. No row: not releasable, no tag.
- An RP.S02 amendment (F-7) changes no gate verdict; it decides whether the release manifest can be `tested`.
- The `## v0.5.1` notes without L46 or the four statements: W21 judged again (F-2).
- Any record whose bytes differ from `rc/records.json`, any step re-run at C' with another result, or a new C' (for
  example for F-10): every row judged again.
- A re-take proof found not to hold (read from the log, not re-run): W22 (b), W24 and W25 judged again.
- Evidence that the `V17 carry` row does not record the user's answer: V13 (e) and V17 (a) BLOCKED until a carry or a
  campaign.

## What this does not establish

- Agent behaviour on the 0.5 surface (L12); V17 is PASS on the user's carry, which measures nothing on it.
- Empirical validation beyond W22 (c)'s pure-component bands; the reactor's validation is the group's, cited (L46).
- Optimality: the journey's decision sits at the lower bound of the reactor's registered domain.
- Portability: the reactor, the journey, steps 6 and 11–16 and W24's environment are measured on one Linux x86-64
  host, SMM-TR09; steps 14 and 15 replay only on its kernel. The macOS and Windows legs are judged by no clause here.
- X32's behaviour on platforms other than the Linux legs, beyond the CI suite's green macOS and Windows legs.
- That J''s re-take proofs and the journey's 71-leaf comparison are correct: read from the log, not re-run.
- Human numerical and process-modeling sign-off, which is recorded separately and is not claimed here.

**Limitations that travel with these verdicts** into the manifest, the gate's report and the notes: each row's
travelling ids; W26's G14 sentence with `0.5.1`; the two FAILs with their acceptance lines (V14 (b) once the user's row
exists); the four reactor statements (L46); the V17 carry's scope (0.5.0's F-5); Linux only, one host for the reactor
and the journey; the journey's invocation line; and, until amended, RP.S02's failure on the 0.5 line (F-7).
