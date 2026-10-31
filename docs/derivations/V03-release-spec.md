# V03 — the 0.3.0 release specification

**Authority.** Design lane (`specifier`), package V03 (manifest id `S13`, R-878). Policy: ADR 0053 (Proposed). Brief:
`docs/briefs/V03-release-policy.md`. Builds on ADR 0042 and `docs/derivations/M07-spec.md` §7–§13; on ADR 0028 and
`docs/derivations/V02-alpha-release-spec.md` §4–§8; and on `docs/RELEASING.md`. Register: R-872…R-880, and R-881…R-883
for Amendment 1, R-903…R-908 for Amendment 2, R-909…R-912 for Amendment 3, and R-913…R-914 for Amendment 4. Facts quoted here were
measured at
`main` = `a1b50ccf` and `wp/E01` = `84d71df8` unless stated otherwise.

**Amendment 1 (2026-10-29, design lane, ruling round 1, brief `docs/briefs/V03-rulings-1.md`).** Two build-lane
questions are answered. (1) `semantic_role` has no role for S11's compressor and turbine: ADR 0054 widens the enum,
§9.4 adds Table R and the corpus, V03.A28–A31 are new, WO-3 does the work, and `required_adrs` gains 0054 (R-881,
R-882). (2) "`wilson-ig-v1` binds from package data" means the binder and the verifier pass the packaged path. v1 is
not edited, and V03.A12 and A19 are restated (R-883). Changed: §1, §2.2, §6, §7 (A12, A19, A25, A27, A28–A31), §9.1,
§9.4 (new), §10, §10.1, §11 (N-9), §12. Amendment 1's facts were measured at `wp/V03` = `98701cca`.

**Amendment 2 (2026-10-30, design lane, RC rulings on the WO-6 stop in `docs/V03_RC_DECISIONS.md`).** Six RC questions
are answered.
(1) Step 16's W27 dry run refuses at C with W27-R63. It first classifies this build under W27 registration version 1,
which ADR 0050 D9 keeps byte-identical and which therefore refuses S11's bases. §4 step 16 had carried M07's "G1–G15"
without applying that ADR, contradicting the refusal §2.1 itself records. W26 (a) is restated for 0.3.0 (§3.5,
V03.A32, R-903): G1–G13 and G15's registered content are judged, G14 is not, and the refusal is asserted exactly. W26
stays claimed, and K3 is not re-cut.
(2) R-902 also covers S11's S4 check (R-904).
(3) V03.A19 (c) names states that exist: RE1–RE3 and A12's state (R-905).
(4) 17b allows S07's registered A31a skip on aarch64 only (R-906).
(5) Step 14's nlp check runs over the modules that contain `mark.nlp`. Its record shows that no node is lost (V03.A33,
R-907).
(6) Step 15's journey commit is J = `2d945b5d`, as WO-5 decided (R-908).
Changed: header, §1, §3.1, §3.4, §3.5 (new), §4, §7 (A19, A21, A27; A32 and A33 new), §10, §10.1, §10.2, §11 (F-4,
N-10), §12. Amendment 2's tree was read at `wp/V03-rc` = `a3e508e3`. Its runs were read at the superseded `4fa15efa`,
whose `src/`, `benchmarks/`, M06 and nlp test modules are byte-identical to it.

**Amendment 3 (2026-10-30, design lane, on the findings of `docs/reviews/V03-verdicts.md` at C = `a3e508e3`).** Five
findings are answered.
(1) F1: §4 carried the alpha's steps 1–12 "read as in M07 §8" without R-375's keep-and-audit of G11's experiment
results, the same gap M07 §8 had at 0.2.0. So C's step 12 kept none, and W21 (e) failed. Step 12 now keeps and audits
them. At 0.3.0 that is a re-run at C compared with step 12's own runs file; from the next release on, it is part of
step 12 itself (§4, V03.A34, R-909).
(2) F2: V03.A12 (c) fails at C only because the version string enters the experiment fingerprint. At a version cut
(c) is judged with the version held equal, by a one-line control run beside the registered run (§7.1, R-910).
(3) F7: S13's own manifest is excluded from the 0.3.0 harvest, as M07's was from 0.2.0's (§4, R-911).
(4) F5: the gate's limitation grammar is not widened for 0.3.0 (§11 N-12, R-912).
(5) F4: Frank is asked to accept the `coolprop` and `lca` licence decisions (§11 N-11).
C stays `a3e508e3`: nothing here changes a D2.4 path. Changed: header, §1, §4, §7 (A12, A27; A34 and §7.1 new), §10,
§10.1, §10.2, §10.5 (new), §11 (N-11, N-12, F-5, F-6), §12. Amendment 3's tree was read at `wp/V03-rc` = `41b99a9b`.

**Amendment 4 (2026-10-31, design lane, on the WO-8 stop in `docs/V03_RC_DECISIONS.md`).** As written, three
conditions waited on each other. ADRs 0053 and 0054 became Accepted only once S13's manifest was `tested`. The manifest
was `tested` only if A25, ADR.0053 and ADR.0054 passed, and those needed the ADRs Accepted. It also needed A08's R part
and A27 to pass, and those needed step 18's YES. Step 18 says YES only on a `tested` manifest and Accepted ADRs. §6.1
now orders WO-8 so that nothing waits on anything after it:
1. the generator's rules (R-913);
2. the manifest, regenerated `tested`, which judges A25 (a) and ADR.0053 and ADR.0054 on what holds before the ADRs
   are marked;
3. ADRs 0053 and 0054 marked Accepted on that manifest;
4. step 18;
5. step 18's output, recorded in the build log.
The manifest never judges step 18 and is not regenerated after it. At 0.2.0, M07's manifest did not judge step 18
either (M07.A36). A08, A25 and A27 are each split into a part the manifest judges and a part step 18 judges. The split
is standing for later release specs (R-914). C stays `a3e508e3`: nothing here changes a D2.4 path. Changed: header,
§1, §4 (step 18), §6 (0053, 0054; §6.1 new), §7 (A08, A25, A27, falsifiability), §10 (WO-8), §10.1, §11 (F-7, F-8),
§12. Amendment 4's tree was read at `wp/V03-rc` = `2fa00ff6`.

**Scope.** What 0.3.0 claims and how each claim is judged. The registry entry, the release candidate C, the RC job,
the version pin and the working form, the ADR acceptance route, the data the wheel ships, the release notes, numbered
assertions, and work orders for one build-lane engineer and one `verdict` agent. No production code is written here.

**In one paragraph.** 0.3.0 re-judges the v0.2 gates V11–V20 and W21–W26 at one candidate C, using 0.2.0's RC
machinery unchanged. It adds X31, the plan's column gate. It does not claim W27, because 0.2.0's agent campaign cannot
reach the S11 build (§2.1). The v0.3 packages S01–S12 enter in three ways: as gate items 8–9 (each has a `tested`
manifest at an ancestor of C), as RC step 17 (the checks their packages left for release time), and as release notes
that say what each establishes and what it does not. Frank answers four items and two D3 clauses after the verdict, as
for 0.2.0. Three choices are asked early (§11).

## 1. What this specification establishes

1. The claim set and its registry entry `v0.3-gate-v1` (§2), and the judgement of X31 (§3).
2. C, K3 and the RC job's 18 steps (§4).
3. The 0.3.0 pin, the working form after it, and A10's pairs, which resolves R-563 (§5).
4. The acceptance route for ADRs 0046–0052 (§6).
5. The wheel's new data (§9) and the release notes' phrases (§8).
6. Assertions V03.A01–A34 (§7), work orders (§10), the `verdict` agent's inputs (§10.2), and open items with defaults
   (§11).
7. The widening of `semantic_role` (ADR 0054), the role of every bindable model (Table R) and the test corpus that
   holds the repository to it (§9.4). Also what "binds from package data" means for Wilson (§9.1, R-883).
8. What W26 (a) judges at 0.3.0 (§3.5), and Amendment 2's RC corrections (§4 steps 14–17b, A19 (c), A21, A32, A33).
9. Step 12's keep-and-audit of G11's experiment results (§4, A34), A12 (c) at a version cut (§7.1), and S13's manifest
   outside the 0.3.0 harvest (§4) (Amendment 3).
10. The order at WO-8 that decides S13's manifest, ADRs 0053 and 0054, and step 18, so that none waits on a step that
    waits on it (§6.1, Amendment 4).

## 2. The claim set and the registry entry

### 2.1 Claimed and not claimed

- **Claimed (17):** V11–V20, W21–W26 and X31, each judged at C.
- **Not claimed:** W27, printed `not claimed (v0.3-gate-v1)` and never read.
  - *Why.* `python -m benchmarks.m06.w27.coverage --out <scratch>` at `a1b50ccf` exits 2 with
    `REFUSED: registry_snapshot: unsupported(provider 'iapws95-v1': no registered records and phases, W27-R63)`.
  - M07 §9's carry needs `coverage_rows` equal at C_W and C. Version 1 cannot be built, and version 3 classifies the
    S11 build's 127 routes (`docs/derivations/W27-registration-v3.md` §"Effects"), so the carry is impossible.
  - The committed `coverage.json` (C7, `f85fcd79`) has rows and `list_models_sha256` equal to 0.2.0's. It describes a
    build before S05–S11.
- **Frank's alternative (N-1):** claim W27 with a new campaign under registration version 3 at a C_W cut before C. That
  amends ADR 0053: W27 moves into `claimed`, the clause grammar gains `W27`, and RC steps 17′ (M07 §9 under W27v3-R01)
  and 18 → 19 are added. The cost is USD 15–45 and about one working day.

### 2.2 Registry entry (the `GateSet` fields of `scripts/v0_2_gate.py`)

| Field | `v0.3-gate-v1` |
| --- | --- |
| covers | `0\.3\.0(?:(?:b\|rc)[1-9][0-9]*)?` |
| claimed / not_claimed | V11–V20, W21–W26, X31 (in this order) / W27 |
| clause | `\b(?:V(?:1[1-9]\|20)\|W2[1-6]\|X31) \([a-z0-9]+\)` |
| policy_adr | `docs/adr/0053-v0.3.0-release-policy.md` |
| verdict_document / rc_record | `docs/reviews/V03-verdicts.md` / `docs/v03-rc-record.md` |
| rc_steps / rc_last_step | 1–17 / 18 |
| evidence_package | `S13`; its specification text is `("the V03 release specification", "§4")` |
| packages (20) | M01, M02, M03, M04, M05, M06, S01, S02, S03, S04, S05, S06, S07, S08, S08b, S09, S10, S10c, S11, S12 |
| envelope_id | `v0.3-envelope-1` |
| required_adrs (25) | 0022, 0026, 0027, 0030, 0031, 0032, 0033, 0034, 0035, 0036, 0037, 0038, 0039, 0041, 0044, 0045, 0046, 0047, 0048, 0049, 0050, 0051, 0052, 0053, 0054 |
| frank_items | `Claim set`, `V17 carry`, `M02 N1`, `M03 N1` |
| rejudge_waits | (V13, V17 carry), (V17, V17 carry), (W21, M02 N1), (W24, M03 N1) |
| links_item | `V17 carry` |

- **Where the strings live.** `benchmarks/v03/registration.json` (`gate_set`, `versions`, `changelog_what_it_is_not`,
  `rc_steps`, `ship_set`) holds the exact strings; `\|` above is the table's escape of `|`. WO-1 transcribes this
  section into that file, and the design-lane review compares the two.
- **Report wording.** The report's first line reads `v0.3 gates (v0.3-gate-v1) at C = <C>; candidate <ref>`. The
  not-covered reason reads `version <v> is not covered by a registered v0.3 gate set`. Everything else is
  `v0_2_gate.py`'s grammar with this entry's values.
- **Decision items.** The alpha's §7.3 items 1–12 apply with this entry's values. Item 7 reads "steps 1–17", item 8
  reads "S13's manifest", and item 9 reads "the twenty packages".

### 2.3 Version table T-V3 (V03.A02)

| Covered by `v0.3-gate-v1` | Not covered by any entry of `scripts/v0_3_gate.py` |
| --- | --- |
| `0.3.0`, `0.3.0b1`, `0.3.0rc1`, `0.3.0rc12` | `0.3.0a1`, `0.3.0b0`, `0.3.0rc0`, `0.3.0rc01`, `0.3.0.dev0`, `0.3.0.post1`, `0.3.1`, `0.3`, `0.30.0`, `1.3.0`, `0.2.0`, `0.2.0rc1`, `0.3.0 ` (trailing space) |

This gives 17 rows. `0.2.0` and `0.2.0rc1` stay covered by `scripts/v0_2_gate.py`, whose Table T-V (29 rows,
M07.A30) does not change.

## 3. Judgement

### 3.1 Rules carried

These rules are carried unchanged: the alpha spec §4 rules, ADR 0042 D2 with ADR 0053 in its place, and the cell rule
(Table T4). An acceptance dated before `Judged` does not count (T6). So does a re-judgement outside its bound (T7, T8).
The clause labels and criteria are carried as follows:

- V11–V20, W21 and W22: alpha spec §5–§6.
- W23–W25: M07 §7.3.
- W26: M07 §7.3, with (a) restated for 0.3.0 in §3.5 (Amendment 2).
- X31: §3.2 below.

The verdict agent applies them at C, with C's records. A clause is judged only on evidence at C or carried to C by a
registered carry (V17 by §3.3, W25 by §3.4).

### 3.2 X31 — "Four matched column cases, invalid specs/phases, two independent references where available"

| Clause | Criterion at C | Evidence |
| --- | --- | --- |
| X31 (a) | RC1–RC4 (S02's M1–M4 at `P_r`) solve, and their registered matches hold | S02 manifest; S03/S09 A10 (i) byte-identity and (ii) live-solve classifications in step 1's default gate |
| X31 (b) | invalid specifications and phase cases are refused with their registered typed outcomes | S02's invalid-spec tests; S08's phases clause (R-736); S08b; S10c column cases, all in step 1 |
| X31 (c) | **PASS iff** S09's three-tool outcome is "met with two references" (4 of 4 at row 5). Any other registered outcome is **FAIL (c)**, stated in its registered words | `docs/reviews/S09-verdicts.md` verdict 3; S03 §17.5, S09 §8.1–§8.3 |

The recorded outcome is "met where available, 3 of 4". RC4, the refluxed absorber, has one reference (BioSTEAM), so
X31 is FAIL (c). It is releasable only by the D3 row `X31 (c)` (N-5). Its notes cite RC4's single reference. This reading
is pre-registered here, so the verdict agent applies it and does not choose it. A verdict that writes "met with two
references" is wrong (R-643's watch item).

### 3.3 V17 carry (unchanged rule; evidence at C)

`v17-c2`'s evidence carries to C iff RC step 8 (`scripts/m07a_rc.py surface`) passes at C with `LINKS` unchanged
(c_1 R-192, c_2 R-234, c_3 R-295). The served digest must be D_3 = `455d01eb…e125`. The chain's rows must be exactly
`[(1,c_3),(2,c_3),(2,c_2),(2,c_1),(3,None)]`, as `test_m07a_a37_the_chain_holds_on_the_served_list` requires. E01 adds no
binding (R-860), and that test passes on `main`. If the digest differs, the RC stops (V03.A23). A new link then needs a
register entry, a strip function, a registered digest and Frank's row extended, or else the alternative in N-2. The
release-time edit is not improvised.

### 3.4 W25 at C

M07 §4.6's carry from 0.2.0's K = `2c508b5` fails, because `carry.journey_files` holds `src/openflowsheet/**`. RC
step 15 therefore re-runs the journey at the journey commit J, under M07 §4–§6 and the registration's budgets
unchanged. J is K3 plus the five re-taken G10 records (`2d945b5d`; Amendment 2, R-908), as 0.2.0's K was A plus its
records. `carry.journey_files` holds `benchmarks/m05/**`, so a journey recorded at K3 itself would not carry past those
records. R3 carries M05's REAL record only if `carry.r3_files` are byte-equal between M05's run commit and J. Otherwise
R3 re-runs M05's study at J. The record is committed in C's tree, carried from J to C by `--carry-journey J --rc C`,
and passes `check` and `replay` at C. This needs workstation compute (the reactor environment) and no money. Honest
outcomes (`BUDGET_EXHAUSTED`, `INCOMPLETE`) are recorded as M07 §5 states. Their verdict is the agent's.

### 3.5 W26 at C (Amendment 2, R-903)

**Why M07's reading cannot be applied at 0.3.0.** M07 §7.3 reads W26 (a) as "M06 G1–G15 at C". M06's G13–G15 are W27
gates that M06 hosts. G14 is the Tier 0 coverage of the build. M07 step 16 runs `python -m benchmarks.m06.w27.dryrun`
for G15, and that command computes the coverage first. Since S11, W27 registration versions 1 and 2 stay byte-identical
(ADR 0050 D9), so they refuse this build's snapshot.
`tests/test_m06_w27_coverage.py::test_s11_the_v2_snapshot_refuses_this_build` registers the refusal. It is the
measurement behind W27's non-claim (§2.1, ADR 0053 D1). At `4fa15efa` the dry run exits 1 with that refusal before it
scores anything. Judging W26 on G14 would fail the web-shell gate for the reason 0.3.0 already does not claim W27. The
defect was in §4 of this document, which carried "G1–G15" without applying ADR 0050 D9 against its own §2.1. Neither the
gate nor the harness is changed to make it pass.

**What W26 (a) judges at 0.3.0.** These are judged at C:
- G1–G13 as M07 reads them: `tests/test_m06_*.py` with `OPENFLOWSHEET_REQUIRE_BROWSER=1`, `node --test`, and G12 by
  step 1 and CI.
- G15's registered content: the twenty scorer states W27-S01…S20 (M06-W27 registration §14.3, with S19 and S20 from its
  Amendment 2, §21.7), run through the production harness and scorer. The non-`CANDIDATE` states are scored against
  the registered rows of the committed `benchmarks/m06/w27/coverage.json`, which §14.3 calls "today's snapshot". The
  `CANDIDATE` states are scored against W27-A13's synthetic row.
- W27-A23 and W27-A79b on stub runs through the real harness.
- The committed record's G14, and the in-process refusal test.

These are the 25 test nodes of V03.A32 (c).

These are not judged at 0.3.0: G14 on this build; the preflight check P3, which re-takes G14 for a campaign; and the
stub campaign rehearsal that the dry run builds on that coverage (sample, confirmation, canaries, P1–P8, 45 stub runs,
`order_check`, and A23 over the campaign directory). Their mechanics stay tested on registered inputs in
`tests/test_m06_w27_campaign_records.py`, within (a)'s module set. Running them on this build is W27's work under
registration version 3 (N-1, declined).

**The refusal is a result.** Step 16 runs the dry run unchanged and asserts the registered refusal exactly (V03.A32
(d)). Step 16 fails, and the engineer stops (§10.1), if the dry run exits 0 (then the v1 snapshot builds this build
and this section's premise is false), fails with a different error, or writes a `summary.json`.

**The verdict.** W26 (a) is PASS iff V03.A32 holds. W26 (b) is unchanged. W26's row carries the travelling limitation
`G14 not judged at 0.3.0: W27 registration v1 refuses this build (ADR 0050 D9, W27-R63); W27 not claimed`. A W26 row
that reads "M06 G1–G15 met" is wrong. This reading is pre-registered, so the verdict agent applies it and does not
choose it. Release-note phrase 15 (`no W27 claim in 0.3.0`) covers it, and §8 does not change. Frank may prefer the
literal reading (N-10).

**Measured at `4fa15efa`** (its M06 tests and `benchmarks/` are byte-identical to `a3e508e3`'s):
- the junit of `tests/test_m06_*.py`: 662 testcases, with 0 failures, 0 errors and 0 skipped;
- the 25 nodes of A32 (c): all passed;
- the dry run: exit 1, with A32 (d)'s exact last line.

The restated step 16 therefore passes there. It is re-measured at C.

## 4. The release candidate C and the RC job

**K3 and C.**

- **K3** is the cut commit on `main` that declares `0.3.0` and pins the envelope (§5.1).
- **C** is K3 plus commits outside the D2.4 paths. Those commits hold the journey record of K3, the RC records,
  `release/rc-trees/<C>.json` (R-151), `evidence/S13/<C>/manifest.json`, the verdicts, the ledger and
  `CHANGELOG.md` `## v0.3.0`.
- C is merged into `main` with a merge commit. From K3 until Frank's dispatch, `main` takes no D2.4 change (RELEASING
  "Pre-releases" step 2).
- S13's manifest is written after C and is not harvested into `v0.3-envelope-1`. `scripts/t08_support_matrix.py`
  sets `HARVEST_EXCLUDED = ("evidence/S13/",)`, as R-485 excluded M07's manifest from 0.2.0's harvest. Classifying its
  items would change `benchmarks/t08/support_envelope.yaml`, a D2.4 path. The next envelope's package harvests it
  (Amendment 3, R-911).

**Preconditions at K3.**

- (P1) E01 is merged.
- (P2) Frank has approved the commit that sets every shipped `primary` range `verified: true`, and it is on `main`.
  That is QA1 against Seider et al., 4th ed., Table 16.32, a separate work item. The commit, or a later one, sets
  `test_e01_a48_tripwire`'s count to 0.
- (P3) WO-1 to WO-4 are merged, after the full gate and CI on both architectures.
- (P4) N-1, N-7 and N-8 are answered, or their defaults stand.

| Step | What, at C unless stated | Assertion |
| --- | --- | --- |
| 1–12 | the alpha spec §8.2 steps 1–12, read as in M07 §8 (step 1's four ledger skips as [A6]; step 9 and step 12 as [A7]). Step 12 also keeps G11's experiment results and audits them (R-375; Amendment 3, R-909; "Step 12's G11 results" below) | V03.A20, V03.A34 |
| 13 | W23 as M07 step 13 | V03.A20 |
| 14 | W24 as M07 step 14. The five in-process G10 records are re-taken at K3 and proved with `scripts/m05_retake_diff.py --digest-only` (R-458). The nlp check runs over the test modules that contain `mark.nlp`, not over `tests/` (Amendment 2, R-907) | V03.A20, V03.A33 |
| 15 | W25 per §3.4: journey at J (K3 plus the G10 records, `2d945b5d`), carried to C, `check` and `replay` at C | V03.A21 |
| 16 | W26 per §3.5: G1–G13 and G15's registered content, with W27's v1 refusal asserted; the browser test on CI x86-64 | V03.A20, V03.A32 |
| 17 | v0.3 package items 17a–17e below | V03.A22 |
| 18 | `scripts/v0_3_gate.py --rc C`, not required in the record. It is run for its YES line at WO-8, after S13's manifest is `tested` and ADRs 0053 and 0054 are Accepted on it (§6.1). Its output is recorded in the build log. S13's manifest does not judge it (Amendment 4, R-913) | V03.A08 (R), V03.A25 (b), V03.A27 (b) |

- **17a.** E01 G10: `e01_evidence_manifest.a48_release_check()` returns `("pass", {"unverified_primary_ranges": 0, …})`.
- **17b.** S07 F-8: with `requirements-coolprop.lock` installed after the main lock (`--no-deps --require-hashes`) and
  `OPENFLOWSHEET_REQUIRE_COOLPROP=1`, every S07 and S11 test module that imports CoolProp passes, with 0 skipped. On
  aarch64 exactly one skip is allowed: S07's `test_a31a_the_digests_own_machine_is_bitwise`, with reason `A31a holds on
  x86_64 only; this machine is aarch64 (A31b)`. Its cross-architecture test `test_a31b_cross_architecture` must pass
  (R-627; Amendment 2, R-906). Any other skip, or that skip on x86-64, fails 17b.
- **17c.** MR-12 v03 (§9.3): `pass`, with `new_since_v0_2_0 == ["coolprop", "lca"]`, and each entry's check is `pass`
  at C.
- **17d.** E01's opt-in tiers at C: G5's A24 and A25 in the `lca` environment (`scripts/build-lca-env.sh`), and G6's
  A33–A36 in the audited `nlp` environment.
- **17e.** The wheel: built from C by `scripts/t08_dist.py` (T08.A43) and inspected (V03.A17). In a fresh venv
  installed from it, V03.A19.

**Step 12's G11 results (R-375; Amendment 3, R-909).** Alpha §6.1 W21 (e) covers every experiment result record that
step 12 writes. G11 writes one at each boundary point, 105 per run and 210 over its two runs. It writes none at its 16
direct points per run (0.2.0's reading, `docs/reviews/V02-verdicts.md`, W21 (e)). Step 12 keeps those records and
audits them for blueprint §9.1's six items. At 0.3.0 step 12 ran without keeping them, so they come from a re-run at C:

1. Step 12's own runs file `step12/g11-coverage-v3.runs.json` (SHA-256 `cdb7d999…fd0a`) is committed before the
   re-run (`3b05511d`). It is the reference for steps 2 and 4.
2. G11 is re-run in the reactor environment built from C's lock, on one thread. It uses step 12's command (step
   `step12-g11` of `tools/run_local.sh`) through 0.2.0's `g11keep.py.txt`, which keeps each point's store.
   `g11collect.py.txt` collects one record per run. Both wrappers are copied unchanged from
   `evidence/M07/ce993651…/tools/` to `evidence/S13/<C>/tools/`. Any change to either is recorded with its diff in
   `docs/V03_RC_DECISIONS.md`.
3. These files go under `step12/experiments/`: the re-run's `g11-coverage-v3.json` and `g11-coverage-v3.runs.json`; the
   collected `g11-experiments-run1.json` and `g11-experiments-run2.json`; the audit's report
   `g11-experiments-audit.json`; and the record `rc-step12-experiments.json`. The record has step `g11-keep-and-audit`,
   format `t08-rc-v1` and the provenance members of `rc-step12.json`, with `commit` = C and `tree_clean` true. Each file
   is listed in `rc/records.json` by that file's rule (gzip beside the path over 1 MB). `docs/v03-rc-record.md` gains
   one step-12 row in the form of `docs/v02-rc-record.md` l.126, citing each file by SHA-256.
4. The record's three checks are V03.A34's. The audit is given step 12's own runs file, not the re-run's. So the
   collected records' labels, order, paths, inlets and `n_tubes` are checked against a record written before the
   re-run. Together with A34 (b), this closes 0.2.0's finding F8 at its root.

No D2.4 path changes, so C stands. From the next release on, step 12 keeps the records in its first run (R-909).

**CI at C** must be green on x86-64 and aarch64 (V03.A24). X31's evidence (§3.2) is step 1's default gate, and no
separate step runs it.

## 5. Version pin, working form, A10's pairs (R-563, R-875)

### 5.1 At K3

- `0.3.0` is written into `pyproject.toml`, `src/openflowsheet/__init__.py`, the two `project_summary` fixtures and
  `tests/test_m06_w27_coverage.py` (RELEASING "After a tag" lists these).
- `benchmarks/t08/support_envelope.yaml` is pinned with `envelope_id: v0.3-envelope-1` and `release: 0.3.0`, and its
  header comment gains one line in the pattern of its 0.2.0 line.
- W27's v1 `coverage.json` is **not** re-taken, because the snapshot refuses (§2.1). RELEASING's sentence is amended by
  WO-4 (F-4).

### 5.2 A10's pairs

`A10_PINS_0_3_0 = (("envelope_id: v0.3-envelope-1\n", "envelope_id: v0.2-envelope-dev\n"), ("release: 0.3.0\n",
"release: 0.2.0.dev0\n"))`.

- They are appended to `test_a10_the_envelope_must_be_pinned_to_the_alpha`'s loop tuple, after `A10_PINS_0_2_0`.
- `tests/test_m07_v0_2_gate.py` gains the constant. `test_a31_b_…` asserts the tuple equals
  `tagged + A10_PINS_0_2_0 + A10_PINS_0_3_0`, and `ALPHA_TESTS_EDITED` is unchanged.
- WO-1 adds them, before the pin. A pair that matches nothing is a no-op on the working form.

### 5.3 After the tag (R-460)

The first D2.4 change after `v0.3.0` does three things:

- It sets `0.4.0.dev0`.
- It returns the envelope to the working form `v0.2-envelope-dev`, `release: 0.2.0.dev0`. This is R-563's fixed token
  and needs no A10 pair.
- It re-takes the five in-process G10 records (R-458).

**Why the token, not D1-O2's version-free form.** `test_a10_…` undoes pins by literal `str.replace` pairs, and
`test_a31_b_…` pins that tuple by `ast.literal_eval`. A working form whose `release` follows `main`'s version needs one
new pair at every bump, plus one for its id. The token needs only each release's two pin pairs. Frank may still choose
the version-free form (N-7). It then costs two more pairs now and one at each later bump.

## 6. ADR acceptance route (R-876)

WO-4 checks each condition against the files cited. It records one check per ADR in S13's manifest, then edits the
status line to `**Accepted, <date>**`, citing the evidence and "marked by the build lane". An unmet condition is a stop
and report. It is not a choice.

| ADR | Condition | Evidence to cite | Route |
| --- | --- | --- | --- |
| 0046 (S07) | manifest `tested` (both architectures); `reviewer` passed the provider and the generator; Q-1 answered with its number; Q-S07-1 answered; F-1 written; Amendment 1's evidence in the manifest | `evidence/S07/7bfab70d…`; `docs/reviews/S07-review.md`, `S07-generator-review.md`; R-627 (x86-64 bitwise, aarch64 classed, worst 2.243e-8); Frank 2026-10-23 "Yes, they wait" | F-1 is **not present** at `a1b50ccf`: neither ADR 0001 nor `interfaces-frozen.md` contains "CoolProp". WO-4 transcribes the `COOLPROP-DEF-ref-v1` line of S07 spec §3.5 verbatim into ADR 0001 D5 and `interfaces-frozen.md` §3, as F-1 prescribes. The text is fixed by S07, so it decides nothing. Then Accepted |
| 0047 (S10) | WO-S10-1/2 manifest `tested` covering A01–A28; `s10_reference.py --check` passes; `reviewer` passed | `evidence/S10/…` (three manifests); `docs/reviews/S10-review-wo1-wo2.md`, `S10-review-final.md`; `--check` run at C | Accepted |
| 0048 (S08) | manifest `tested`; G1, G2 at the merge candidate; full gate and CI at merge; `reviewer` read the ADR | `evidence/S08/6d7d1a6d…`; `docs/reviews/S08-review.md` | Accepted |
| 0049 (S10c) | manifest `tested` with G1–G9; `reviewer` passed WO-1…4 | `evidence/S10c/2aedd250…`, `…/8f38f963…`; `docs/reviews/S10C-review.md` | Accepted |
| 0050, 0051 (S11) | manifest `tested` with G1–G8 (0050) or G1–G13 (0051); `reviewer` passed | `evidence/S11/01e72ca4…` (123/126, G8 outstanding there); merge `1b2758d1` (gate PASS `021441ef`, CI 40877525424 green on both architectures); `docs/reviews/S11-review.md`; G8 again at C (steps 1, 17b; V03.A24) | Accepted **after** V03.A24 holds at C. S13's manifest records `S11.G8` pass |
| 0052 (E01) | manifest `tested` with G1–G9; `reviewer` passed tracks A, B and integration | `evidence/S12/d87078af…`; `docs/reviews/E01-review.md`; E01's merge record (G8); G8 again at C | Accepted after E01's merge and V03.A24 |
| 0043 (L01/S04) | Frank's L01-Q1 and Q-2; manifest; review | L01-Q1 (W27 Amendment 3) is not done | **Stays Proposed.** It is not in `required_adrs`. `pr-lib-v1` is library-only, its records do not ship (L01-Q4), and no 0.3.0 claim rests on it |
| 0053 | §ADR status line | Frank's tables; S13 manifest `tested` | Accepted at WO-8, in §6.1's order: after S13's manifest is `tested`, before step 18 |
| 0054 (V03, Amendment 1) | S13's manifest `tested` at C, listing V03.A28–A31 with their commands | `evidence/S13/<C>/manifest.json` | Accepted at WO-8, with 0053, in §6.1's order |

### 6.1 The order at WO-8 (Amendment 4, R-913)

Before Amendment 4, three conditions waited on each other:
- ADRs 0053 and 0054 waited on S13's manifest being `tested`.
- The manifest waited on A25, ADR.0053 and ADR.0054, which need the ADRs Accepted, and on A08's R part and A27, which
  need step 18's YES.
- Step 18 waited on the manifest being `tested` (its manifest item) and on the ADRs being Accepted (item 12).

The order below has no cycle. Each step reads only what an earlier step wrote.

| Step | What | Reads | Writes |
| --- | --- | --- | --- |
| 1 | The generator `scripts/s13_evidence_manifest.py` takes rules (g1)–(g6), with controls (c1)–(c10) | — | the script; `tests/test_v03_s13_route.py` |
| 2 | S13's manifest is regenerated at a clean commit G that holds step 1 (its `judged_at`), with the `--gate-log` and `--ci-run` arguments of the generation committed in `4ecfc162`. It must come out `tested`. It is committed alone as H1 | tests, RC records, CI, the verdict document, ADR 0053's tables, `docs/adr/` with 0053 and 0054 Proposed | `evidence/S13/<C>/manifest.json` |
| 3 | ADR 0053's and 0054's Status paragraphs are edited to Accepted, citing step 2's manifest | the manifest at H1 | the two ADRs (commit H2) |
| 4 | Step 18 runs at H2: `PYTHONPATH=src .venv/bin/python scripts/v0_3_gate.py --rc a3e508e35fc5451fe56fa7b70941621992d35b50`, with the candidate at HEAD = H2. Its output goes to `evidence/S13/<C>/artifacts/step18-H2.log` | the gate's inputs at H2 | the log (git-ignored) |
| 5 | The build log records step 4 | the log | `docs/V03_RC_DECISIONS.md` (commit H3) |

**The generator's rules (R-913).** These replace 4ac5b66c's pending branch for A25 and the `step18` reading.
- (g1) A08's check is its tests only: `Spec("A08", tests=True)`. A27's check is `_self` only:
  `Spec("A27", measures=("self",))`. It passes if and only if every other check passes and at least one command was
  run, as M07.A43's does. The `step18` measure, `_m_step18`, `Inputs.step18_log` and the `--step18-log` option are
  removed. The parser then refuses the option with exit 2.
- (g2) A25 (a) calls `v0_2_gate.adr_problems` over `docs/adr/` at the commit the generator runs at. Before WO-7, when
  there is no verdict document and some problem is found, A25 (a) is `unsupported`, pending, unchanged. Otherwise it
  passes if and only if two things hold. First, every problem matches `^ADR (0053|0054) is not Accepted: `, and that
  ADR's status line, with `*` removed and stripped, starts `Status: Proposed`. Second, 0043 is Proposed and not
  required. Anything else is `fail`. The value lists those problems as `at_wo8`.
- (g3) ADR.0053 and ADR.0054. Before WO-7 (no verdict document) each is `unsupported`, pending. Otherwise
  each passes if and only if all of these hold:
  - Its status line, with `*` removed and stripped, starts `Status: Proposed` or `Status: Accepted`.
  - For 0053 only, the six cells pass. That means the gate's own `v0_2_gate.policy` over ADR 0053, against the verdict
    document's `Judged` and `Re-judged`, returns no `problems` and no `frank` refusals. It also means every D3
    acceptance it returns is dated on or after `Judged`, or on or after `Re-judged` for a clause of a gate the
    re-judgement lists (Table T7).
  - The catalogue lists V03.A01–A31 (0053) or V03.A28–A31 (0054).
  The value holds the status line, the status (`Proposed` or `Accepted`), the policy's summary and the listed range.
- (g4) The guard. Decide every check except V03.A27. Then, if some check other than ADR.0053 and ADR.0054 is not `pass`,
  or no command was run, each of ADR.0053 and ADR.0054 whose status is Accepted becomes `fail`, with
  `accepted_early: true` in its value. `_self` runs after the guard.
- (g5) A26 takes the same `policy` part as (g3): `Spec("A26", measures=("verdict_document", "policy"))`.
- (g6) In the limitations, the sentence that begins "The design lane's verdicts are not judged here" is replaced by
  these two, verbatim:
  - `Step 18 (scripts/v0_3_gate.py --rc C) is not run by this script and is not judged here. It reads this manifest and ADRs 0053 and 0054, which are marked Accepted on this manifest, so it runs after both (V03 spec §6.1, R-913). V03.A08's R part, A25 (b) and A27 (b) are judged from its output, which docs/V03_RC_DECISIONS.md records with its SHA-256, as M07.A36's R part was at 0.2.0.`
  - `ADR.0053 and ADR.0054 judge their conditions other than this manifest's own status, and pass with the status line Proposed or Accepted; one Accepted while another check does not pass fails (R-913). V03.A25 here is its part (a); item 12 in full is step 18's (A25 (b)).`

**Controls (c1)–(c10)** form `tests/test_v03_s13_route.py`. They call the generator's functions with `docs/adr/` and
the check list substituted. They never run the full generator.
- (c1) A25 (a) on the tree at `2fa00ff6` (0053 and 0054 Proposed) gives `pass`, with both problems in `at_wo8`.
- (c2) A25 (a) with 0046's status line set to `**Status:** **Proposed, 2026-10-29**` gives `fail`.
- (c3) A25 (a) with 0053's status line set to `**Status:** **Rejected, 2026-10-31**` gives `fail`.
- (c4) A25 (a) with 0053 and 0054 Accepted gives `pass`, with `problems` empty.
- (c5) ADR.0053 with Proposed and the committed tables gives `pass`. With one decisions-table cell set to `pending` it
  gives `fail`. With one D3 cell dated 2026-10-29 it gives `fail`.
- (c6) ADR.0054 with Proposed gives `pass`. With the status line `**Status:** **Withdrawn, 2026-10-31**` it gives
  `fail`.
- (c7) The guard. ADR 0053 Accepted with V03.A24 set to `fail` gives ADR.0053 `fail` with `accepted_early`. With every
  other check `pass`, it gives `pass`. The same holds for 0054.
- (c8) `_self` gives `pass` when every other check passes and 1 command was run. It gives `fail` with one other check
  `unsupported`, and `fail` with 0 commands. Its value has no `step18` key.
- (c9) `main(["--step18-log", "x", …])` exits 2, and `MEASURES` has no key `step18`.
- (c10) A26 with one ADR 0053 cell set to `pending` gives `fail`.

**Step 3's Status paragraphs.** Each replaces its ADR's Status paragraph, from `**Status:**` to the line before
`**Author:**`. Nothing else in either ADR changes. Each braced field is replaced by its value.
- ADR 0053: `**Status:** **Accepted, {date}** — its own condition holds: Frank's answers are recorded in the two tables below (all six cells `accepted, 2026-10-30`, on or after the verdict's `Judged` date 2026-10-30), and S13's manifest `evidence/S13/a3e508e3…/manifest.json` is `tested` at the release candidate C = `a3e508e3`, with V03.A01–A31 among its checks (generated at `{G}`, committed in `{H1}`, SHA-256 `{first 8 hex}…`). Marked by the build lane at WO-8, in V03 spec §6.1's order. (Proposed 2026-10-29.)`
- ADR 0054: `**Status:** **Accepted, {date}** — its condition holds: S13's manifest `evidence/S13/a3e508e3…/manifest.json` is `tested` at the release candidate C = `a3e508e3`, with V03.A28–A31 among its checks (generated at `{G}`, committed in `{H1}`, SHA-256 `{first 8 hex}…`). Marked by the build lane at WO-8, with ADR 0053, in V03 spec §6.1's order. (Proposed 2026-10-29.)`

**Step 3 runs only on step 2's manifest.** Before the edit, `git show H1:evidence/S13/<C>/manifest.json` has `status`
`tested`, every check `pass`, and the SHA-256 that the lines cite.

**Steps 4 and 5.** Step 4 must exit 0, and its last line must be exactly `v0.3.0 tag may be proposed: YES`. At H2, F9's
count must be 4 of 4, each phrase exactly once, with `awaits Frank's statement` 0 times. A08's R part is the log's
grammar: the first line is §2.2's; there are 18 gate rows, the 17 claimed gates in order and then W27
`not claimed (v0.3-gate-v1)`; the last line is YES. A short script checks it, and its one summary line goes into the
build log. Step 5 records H2, the command, the exit status, the log's SHA-256, A08's summary line, the last line and
F9's count. H3 touches only `docs/V03_RC_DECISIONS.md` and `docs/progress.md`. `git diff --name-only H2 H3` lists
nothing else. Step 18 reads neither file: it reads the ledger, the envelope, `docs/adr/`, the verdict document, the RC
record, `evidence/`, `scripts/m07a_rc.py` and its own code. So step 4's YES holds at H3. The manifest is not
regenerated. If a stop forces a regeneration,
steps 3–5 are repeated after it, the ADR lines cite the new manifest, and the build log says why.

## 7. Assertions

Gate column: **D** is the default gate (`scripts/gate.sh`), **R** is the RC job or the records at C, and **CI** is both
CI architectures at C. "Exact" means string, byte or set equality. No assertion here compares a floating-point value
except A19 and A24. Their tolerances are the registered ones cited. A31 compares binding outcomes by `float.hex`
as an identity, with no tolerance.

| Id | Assertion | Expected | Tolerance and why | Gate |
| --- | --- | --- | --- | --- |
| V03.A01 | `scripts/v0_3_gate.py`'s registry has exactly one entry; its fields equal §2.2 and `registration.json` `gate_set` | equal | exact | D |
| V03.A02 | `gate_set_of` over Table T-V3 | 4 covered, 13 not covered (17 rows) | exact | D |
| V03.A03 | the v0.2 engine is unchanged. `tests/test_m07a_v0_2_gate.py` and `tests/test_m07_v0_2_gate.py` pass, and their nodes are unchanged except A04's; AM-07 holds (the alpha's `--markdown` output byte-identical); both v0.2 entries equal `benchmarks/m07/registration.json` `gate.gate_sets` | pass | exact (`ast.dump`, bytes) | D |
| V03.A04 | `test_a10_…`'s loop tuple = tagged + `A10_PINS_0_2_0` + `A10_PINS_0_3_0` (§5.2); a control with the pairs swapped fails `test_a31_b_…` | equal; control fails | exact | D |
| V03.A05 | clause grammar. Under v0.3's: `V11 (a)`, `V20 (c)`, `W21 (f)`, `W26 (b)`, `X31 (c)` parse; `W27 (a)`, `W28 (a)`, `V10 (a)`, `X32 (a)`, `X31 (A)` do not. Under `v0.2-gate-v1`'s: `X31 (c)` does not, `W27 (a)` does | 5 / 5 / 2 | exact | D |
| V03.A06 | decision items 1–12 for `v0.3-gate-v1`: one YES fixture; for each item one NO fixture flipping only it | 1 YES, 12 NO, each with its reason | exact | D |
| V03.A07 | X31 FAIL (c) without a D3 row → NO; with a row dated on `Judged` → YES; dated the day before → NO. A verdict document with a W27 row → exit 2 | 2 NO, 1 YES, exit 2 | exact (dates are days) | D |
| V03.A08 | output: the §2.2 first line; 18 gate rows, the 17 claimed in order and then W27 `not claimed (v0.3-gate-v1)`; last line `v0.3.0 tag may be proposed: YES` or `… NO (k reasons)`. D: the gate's tests, which S13's manifest judges. R: step 18's own output at WO-8 (§6.1 step 4), recorded in the build log; S13's manifest does not judge it (Amendment 4, R-913) | grammar | exact | D, R |
| V03.A09 | at K3 and C: the five version-carrying files read `0.3.0`; the envelope `v0.3-envelope-1` / `0.3.0` | as stated | exact | R |
| V03.A10 | `test_e01_a48_tripwire`: count 0 after P2; `a48_release_check()` is `pass`; its synthetic unverified document still gives `fail` | 0; pass; fail | exact count (an accidental 0 is excluded by the `fail` control) | D |
| V03.A11 | MR-12 v03 (§9.3) at HEAD: `new_since_v0_2_0 == ["coolprop", "lca"]`, both with entries; a control extra without an entry → `fail`; `mr12_extras_v02` at `RELEASE_0_2_0_COMMIT` unchanged (S07 A44's release clause) | pass; fail; unchanged | exact | D |
| V03.A12 | the ship set (§9.1) is in `PACKAGED` with `_data` links, bytes equal to the `benchmarks/s10/` files; R-811's wheel row is gone. With `wilson_ig._checkout_records` returning `None`, as in a wheel (the fixture first checks that `wilson_ig.load_records()` then refuses `records_missing: `): (a) `revision_binding.provider_for(WILSON_BASIS)` is not `Unbound`, its `describe()` has `provider_id` `wilson-ig-v2` and the records' `data_sha256`, and `verify.certificate._wilson_provider().describe()` equals it; (b) `WilsonIdealGasProvider(resources.packaged_path(wilson_ig.RECORDS_PATH))` answers `evaluate_phase` (both phases, every property and derivative) and `flash` exactly as the checkout's provider does at one state; (c) S10/S11 identity tests are unchanged, and `tests/test_s11_wilson_v2.py::test_a75_v1_is_not_edited` passes (v1's bytes are not edited, R-883). At a version cut, (c)'s identity run is judged as §7.1 states (Amendment 3, R-910) | as stated | exact (SHA-256; `==` on the answers: same code, same bytes) | D |
| V03.A13 | NOTICE holds the Wilson block (each of `Kurihara`, `J. Chem. Eng. Data 38 (1993) 446`, `NASA TM-4513`, `CoolProp 8.0.0`, `deReuck-BOOK-1993`, `Schroeder-JPCRD-2014`, `Wagner-JPCRD-2002`, `CIAAW`) and the IPCC block (`IPCC AR6 WG1`, `Table 7.15`), each once | 10 substrings | exact substring | D |
| V03.A14 | `docs/s10-rights-check.md` §3 "Ships?" column equals §9.1's table; RC-05 and RC-08 cite Frank 2026-10-29 | equal | exact | D |
| V03.A15 | the RC test step (WO-3) installs `requirements-coolprop.lock` after the main lock and sets `OPENFLOWSHEET_REQUIRE_COOLPROP=1` (read from the script) | present | exact | D |
| V03.A16 | `registration.json` `changelog_what_it_is_not` equals §8's 17 phrases | equal | exact | D |
| V03.A17 | the wheel at C: each §9.1 ship-set file once, with the repository SHA-256; E01's seven data files with `docs/e01-data-licences.json`'s SHA-256; no §9.1 repository-only file | as stated | exact | R |
| V03.A18 | `CHANGELOG.md` `## v0.3.0` holds §8's 17 phrases verbatim | 17 | exact substring | R |
| V03.A19 | in a fresh venv installed from the wheel (the package is imported from site-packages, so v1's own checkout lookup finds nothing): (a) `resources.packaged_path(wilson_ig.RECORDS_PATH)` is a file whose SHA-256 equals the repository's `benchmarks/s10/records.yaml`; (b) `provider_for(WILSON_BASIS)` gives `wilson-ig-v2` with that `data_sha256`, and `certificate._wilson_provider()` describes equal; (c) `WilsonIdealGasProvider(packaged_path(RECORDS_PATH))` answers `evaluate_phase` and `flash` equal to the checkout's at C, at four states (Amendment 2, R-905). `evaluate_phase` covers both phases, every property of `describe().properties` and every derivative in T, P and the three mole numbers; the liquid's `lnphi` carries γ. `flash`'s `k_values` are K. The states are S10's RE1, n = (0.6, 0.4, 1.0) mol, 350 K, 101 325 Pa; RE2, (1, 0, 1), 345 K, 101 325 Pa; RE3, pure H₂O, 360 K, 8 × 10⁴ Pa (S10 spec §9.7); and A12's state, (0.3, 0.3, 0.4), 350 K, 101 325 Pa (`scripts/v03_rc.py` `A19_STATES`); (d) `WilsonIdealGasProvider()` with no argument raises `RecordError` whose message starts `records_missing: `, the library's documented, typed refusal (R-883); a success or any other exception fails | (a), (b) equal; (c) equal; (d) the refusal | (a), (b), (d) exact; (c) bitwise (`float.hex`; same code, data bytes and machine; x86-64) | R |
| V03.A20 | RC steps 1–14 and 16 pass at C; `docs/v03-rc-record.md` has a passed row for each of 1–17 | pass | per-step gates | R |
| V03.A21 | step 15: the journey record of J (`2d945b5d`, §3.4) is in C; `--carry-journey 2d945b5d --rc C` reports carried; `check` and `replay` (bitwise) pass at C | pass | bytes | R |
| V03.A22 | step 17a–17e pass at C; an `unsupported` result is not a pass | pass | as each | R |
| V03.A23 | step 8: served digest D_3 and chain rows as §3.3; otherwise STOP | equal | exact (SHA-256) | R |
| V03.A24 | CI green at C on both architectures. S07 A31: x86-64 bitwise, aarch64 within R-627's classes. S11 thermal check: x86-64 bitwise, aarch64 within R-843/R-845 classes (flash class at the S11 merge: 0.024 of its bound), and the relative class's worst ≤ 0.1 of its bound (R-845's watch). THM-09/4's lines copied into `docs/t07-measurements.md` (R-796) | green; ratios recorded | registered classes; the 0.1 watch is R-845's, not new | CI |
| V03.A25 | gate item 12 at C, in two parts (Amendment 4, R-913). (a) S13's manifest: the gate's own `adr_problems` over `docs/adr/`, at the commit the generator runs at, returns no problem except `ADR 0053 is not Accepted: ` or `ADR 0054 is not Accepted: `, and each of those for a status line that starts `Status: Proposed` (`*` removed, stripped). So the other 23 required ADRs are Accepted, and 0043 is Proposed and not required. (b) Step 18 (§6.1 step 4): item 12 in full, the 25 required ADRs Accepted (0054 included, Amendment 1), shown by its YES line and recorded in the build log | as stated | exact | R |
| V03.A26 | `docs/reviews/V03-verdicts.md`: header names C once and one `Judged`; 17 rows in claimed order; every clause parses under v0.3's grammar. ADR 0053's two tables pass the cell rule. `docs/requirements.yaml` X31 verdict and evidence written from it | as stated | exact | R |
| V03.A27 | two parts (Amendment 4, R-913). (a) S13's manifest, as its own check V03.A27: `evidence/S13/<C>/manifest.json` `tested`, listing V03.A01–A26 and A28–A34 with commands run and `S11.G8`, `S12.G8`, `S12.G10`. That is, every other check passes and commands were run. (b) At WO-8, from step 18's output (§6.1 step 4), not by the manifest: step 18's last line `v0.3.0 tag may be proposed: YES`, recorded in the build log with the log's SHA-256 | (a) present; (b) YES | exact | R |
| V03.A28 | `schemas/process-revision.schema.json`: `properties.instances.items.properties.semantic_role.enum` equals the eleven frozen values in their order (`feed` … `heat_exchanger`) followed by `compressor`, `turbine`, `other`; `$id` equals `https://github.com/frankp/process-runtime/schemas/process-revision.schema.json`; `properties.schema_version` equals `{"type": "integer", "const": 1}` (ADR 0054 D1) | 14 values in order; `$id` and `schema_version` unchanged | exact (list and string equality) | D |
| V03.A29 | every document of §9.4's corpus gets no `SCHEMA-01` FAIL from `application.validation.validate(document)`. The corpus has at least 80 documents and contains the nine cases of §9.4 by path. Control: GP-M1 with `instances[1].semantic_role` set to `purge_sink` (the value V17 c1's agents wrote) gives a `SCHEMA-01` FAIL whose message starts `schema_invalid(/instances/1/semantic_role)` | 0 FAIL over ≥ 80 documents; the control FAILs | exact (count, path set, message prefix) | D |
| V03.A30 | `tests/semantic_roles.py` `ROLE_OF_MODEL` is Table R (§9.4), and: (a) its keys equal `revision_binding.MODEL_SIGNATURES`' keys; (b) every value is in A28's enum, and the set of values equals the enum without `other` (13 values); (c) every instance of every corpus document whose model id is a key of `ROLE_OF_MODEL` has `semantic_role == ROLE_OF_MODEL[instance.model.id]`; an instance with any other model id is counted and not judged (0 of 441 at `98701cca`), because a declared model the binder does not accept may take any value A28 allows; (d) none of §9.4's five builders holds the string constant `"other"` (read by `ast`), and each imports from `semantic_roles`; (e) `ROLE_OF_MODEL` equals §9.4's Table R as parsed from this file (both column pairs, 30 rows), as `test_v03_v0_3_gate.py` parses §2.2. Controls: a copy of the table without `thermal.turbine` fails (a); a copy with `thermal.turbine: pump` fails (b), and (c) on TH-C1 and GP-M2 | (a)–(e) hold; each control fails | exact | D |
| V03.A31 | (a) no `*.py` file under `src/openflowsheet/` contains the text `semantic_role`. (b) For every corpus document d, with d′ = d with every instance's `semantic_role` set to `other`: `s11_identity_recorder.outcome(bind(d), document_sha256(d)) == outcome(bind(d′), document_sha256(d′))`, where bind is `revision_binding.bind_revision_flowsheet` and a raise is compared as (type name, message). Control: GP-M1 with instance `M`'s `efficiency` value replaced by `math.nextafter(v, math.inf)` gives a different outcome | (a) none; (b) equal for every document (measured: 80 of 80; 63 bound, 17 typed `Unbound`, a split that depends on the installed extras and is not asserted); the control differs | exact (`float.hex` inside `outcome`) | D |
| V03.A32 | step 16 at C (§3.5). `step16/rc-step16.json` (step `w26-web-shell`) holds exactly four checks, each `pass`. (a) `a60.w26.m06_tests`, as 0.2.0's: `OPENFLOWSHEET_REQUIRE_BROWSER=1 pytest -q -rs -p no:cacheprovider --junitxml=<rc>/step16/m06-tests.junit.xml tests/test_m06_*.py` exits 0, and the junit has 0 failures and 0 errors. (b) `a60.w26.web_unit_tests`, as 0.2.0's: `node --test` exits 0. (c) `a60.w26.g15_registered_states`: (a)'s junit has 0 skipped, and each of these 25 testcases appears exactly once with no `failure`, `error` or `skipped` child. From `tests.test_m06_w27_scorer`: `test_the_twenty_states_are_registered`, `test_candidate_states[W27-S11]` to `[W27-S16]`, and `test_harness_states[W27-S01]` to `[W27-S10]` and `[W27-S17]` to `[W27-S20]`. From `tests.test_m06_w27_harness`: `test_a23_run_record` and `test_a79b_an_unpinned_attempt_through_the_harness`. From `tests.test_m06_w27_coverage`: `test_s11_the_v2_snapshot_refuses_this_build` and `test_committed_coverage_json_is_g14_and_this_builds_classification`. (d) `a60.w26.w27_v1_refusal`: `python -m benchmarks.m06.w27.dryrun --out evidence/M06/W27/artifacts/dry-run/<C7>` exits 1; its last non-empty output line is exactly `benchmarks.m06.w27.snapshot.SnapshotUnsupportedError: registry_snapshot: unsupported(provider 'iapws95-v1': no registered records and phases, W27-R63)`; and `<out>/summary.json` does not exist. (c) and (d) are judged on the local `ref-x86-64` run, where the pinned archive and `mcp` are present, not on CI | 4 of 4 pass; 25 nodes; exit 1 and the line | exact (names, counts, exit status, string) | R |
| V03.A33 | step 14's nlp selection (R-907). `step14/rc-step14.json` holds `a60.w24.nlp_tier_and_inventory` `pass`, with `scripts/m03_nlp_check.sh` given the modules that `grep -l 'mark.nlp' tests/test_*.py` lists at C (13 at `4fa15efa`), and the record carries that list. It also holds `a60.w24.nlp_selection` `pass`: in the audited nlp environment, `pytest --collect-only -q -m nlp` lists the same set of node ids over those modules as over `tests/`, the set has 190 members, and the run over the modules exits 0. The run over `tests/` exits 2 on the three `tests/test_s10_*.py` modules that import `mpmath`, and its exit status is not judged | pass; 190; equal sets | exact (set equality, count) | R |
| V03.A34 | step 12's G11 experiment results at C (§4, R-375, R-909). `step12/experiments/rc-step12-experiments.json` (step `g11-keep-and-audit`) holds exactly three checks, each `pass`. (a) `r375.g11_rerun`: §4's re-run exits 0. (b) `r375.same_computation`: the re-run's `step12/experiments/g11-coverage-v3.runs.json` and step 12's own `step12/g11-coverage-v3.runs.json` (SHA-256 `cdb7d9993327cd48543212c37063421fa9c82232dd05b356e1609335fce6fd0a`, committed in `3b05511d`) have 2 runs each and the same labels in the same order in each run. At each of the 242 point-runs the members `stage`, `accepted`, `child_accepted`, `tube_outlet`, `path` and `attempts` are equal as JSON. A member present on one side only is a difference. The result is 0 differences. (c) `r375.audit`: `python scripts/m07_g11_experiments_audit.py --variant-file benchmarks/m02/variant-v3-provisional.json --runs <rc>/step12/g11-coverage-v3.runs.json --out <rc>/step12/experiments/g11-experiments-audit.json` over the two collected records (`g11-experiments-run1.json`, `g11-experiments-run2.json`, or their `.gz`). It is given step 12's own runs file. It exits 0, and its line reads exactly `G11 experiments audit: 2 runs, 210 boundary points, 210 results, 210 attempts, 0 without a result, 32 direct points (no records); 6 items + schema: 0 problems; context (job_id): <j> findings: PASS`. j is recorded and not judged: R-375's six items do not include `job_id` (0.2.0's j was 420) | 3 of 3; 0 differences in 242; the line, with 210, 210, 210, 0, 32 and 0 | exact (counts, JSON equality, exit status, the string with j free) | R |

**Falsifiability.** A06 and A07 flip one input at a time, so a dropped item or a mis-dated cell changes the answer.
A10's `fail` control excludes a vacuous 0. A11's control excludes a measure that passes with no entries. A04's swapped
control excludes an order-blind comparison.
A29's control excludes a validator that accepts any role, and its count floor and named paths exclude a corpus that
silently shrank. A30's controls exclude a table check that passes on any table. A31's control excludes an outcome
comparison blind to parameters. A31 (a) alone is not enough: code could reach the role without naming it, for example
by iterating an instance's members, and (b) would catch that. Every A28–A31 assertion is a string, set or identity
comparison, so no tolerance applies. A difference in A31 (b) is a defect, not noise.
A32 (c) names its 25 nodes and requires 0 skipped. A run without the pinned archive or `mcp`, where the harness states
skip, therefore fails it. A32 (d) passes only on the registered refusal, so a dry run that succeeds or fails otherwise
fails it. A33's count excludes an empty selection that would compare equal to an empty collection. A32 and A33 compare
names, counts, exit statuses and strings, so no tolerance applies.
A34 (b) compares the re-run with step 12's own record, written before it. A re-run that took another path at any point
therefore fails it. (c) gives the audit that record too, so a collected record with a missing, extra or reordered point
fails it. (c)'s counts exclude an empty audit, which the script itself refuses (`passed` needs at least one
experiment). §7.1's R1 changes one line. So any digest it still finds changed, and any failure outside the five
registered readers, has a cause other than the version, and (c) fails. The five readers failing shows that the edit took
effect. A34 and §7.1 compare counts, JSON values, exit statuses and strings, so no tolerance applies.
A25 (a) fails on a third required ADR that is not Accepted, and on a 0053 or 0054 status line that is neither Proposed
nor Accepted. §6.1's guard fails ADR 0053 or 0054 when either is marked Accepted while another check of the manifest
does not pass. Controls (c2), (c3), (c6) and (c7) show that each refusal fires. Both compare strings, so no tolerance
applies (Amendment 4).

### 7.1 V03.A12 (c) at a version cut (Amendment 3, R-910)

`scripts/s11_identity.py` compares the judged checkout with its base `8c34ecb0` (S11 design §6). The version string is
part of the in-process experiment fingerprint (`src/openflowsheet/adapters/experiments/backends.py` l.174, and
`tests/support/m04_synthetic_parents.py`). Through `Environment`'s digest (`document_sha256(fingerprint)`) it reaches
the documents built from it. So across a change of `__version__` the comparison differs by construction: at C, 47
family-C digests, all of them binder calls of `tests/test_m04_wo{7,8,19,20}_*.py`. The version is build provenance
(R-902). It sits under a derived digest, so excluding the clear field would not remove it, and (c) holds it equal
instead. The S13 generator decides (c)'s identity part as follows. Any other outcome is `fail`.

0. The judged checkout's tracked files are clean (`git diff --quiet HEAD`). V_C and V_B are the `__version__`
   literals of `src/openflowsheet/__init__.py` at HEAD and at `8c34ecb0` (`git show`). Each is the single match of
   `^__version__ = "([^"]+)"$`. Measured: V_C = `0.3.0`, V_B = `0.3.0.dev0`.
1. **R0, the registered run.** `scripts/s11_identity.py` runs in the checkout as WO-6's generator runs it now, with a
   private `TMPDIR` and no `PYTEST_ADDOPTS`. If it exits 0 and its last line starts `S11-IDENTITY PASS`, (c)'s identity
   part passes, and steps 2–5 do not run.
2. Otherwise V_C ≠ V_B, and R0 exits 1 with a last line matching
   `^S11-IDENTITY FAIL n=(\d+) changed=\[(C:.+)\] \((\d+) digests differ\)$`. The parenthesis then names no problem
   except changed digests: no key set differs, and no shard of either tree exited non-zero. The tool lists A and B keys
   before C keys, so a first key `C:` means that only family-C digests changed.
3. **R1, the aligned run.** Run `git worktree add --detach <W> HEAD`. In `<W>/src/openflowsheet/__init__.py`, the line
   `__version__ = "<V_C>"` becomes `__version__ = "<V_B>"`. Then `git -C <W> diff --numstat` must print exactly one
   line: `1`, `1` and `src/openflowsheet/__init__.py`, tab-separated. Next, with cwd `<W>`,
   `PYTHONPATH=<W>/src:<W>`, a second private `TMPDIR` and no `PYTEST_ADDOPTS`, run
   `python scripts/s11_identity.py --keep <K>`, with `<K>` a fresh directory. `<W>` is removed afterwards. R1 exits 1 with a last line matching
   `^S11-IDENTITY FAIL n=(\d+) changed=\[\] \(C branch shards \[\d+(?:, \d+)*\] exited non-zero\)$`. So no digest
   changed, and the only problem is that some shards of the aligned tree failed.
4. n(R1) = n(R0): the two runs compared the same keys.
5. The aligned tree's failed tests are exactly these five. They are read as the node ids of the lines matching
   `^(?:FAILED|ERROR) (\S+)` in `<K>/branch/shard-*.log`:
   - `tests/test_package_imports.py::test_root_package_exposes_version`
   - `tests/test_v02_main_version.py::test_the_envelope_matches_the_version`
   - `tests/test_m06_w27_coverage.py::test_snapshot_of_this_build_is_todays_registry`
   - `tests/test_t07_w5e_application_results.py::test_the_fixtures_are_what_real_responses_emit_today`
   - `tests/test_m07_journey.py::test_a21_the_carry_identity_is_the_determining_files_at_the_anchor_and_j`
   Each reads the version or hashes `src/**`. By step 2, all five pass in R0's checkout.

S13's manifest records these members in V03.A12's `value`: `a12c_mode` (`plain` or `version_aligned`), V_C, V_B, R0's
and R1's last lines, n, R0's digest count k (47 at C; recorded, not judged), the numstat line and the five failed node
ids. Both commands go into `commands`. `V03.A12c.log`, `V03.A12c-aligned.log` and `<K>/branch/shard-*.log` go under the
manifest's artifacts.

Expected at C, from the run at C and the orchestrator's counterfactual (`docs/reviews/V03-verdicts.md`, "V03.A12
(c)"): R0 `S11-IDENTITY FAIL n=54494 changed=[C:…] (47 digests differ)`; R1 `S11-IDENTITY FAIL n=54494 changed=[] (C
branch shards [1, 3, 7, 11] exited non-zero)`; and the five tests above. n and the shard indices can move at a later
judged commit whose `tests/` differ. Steps 4 and 5 cannot. A different set of failed tests in step 5 is a stop (§10.1),
and the set is never edited to pass.

## 8. Release notes: `CHANGELOG.md` `## v0.3.0`, "What it is not"

Each phrase appears verbatim. The section also lists what each v0.3 package added, with its manifest.

1. `numerical verification, not empirical validation`
2. `no global optimality`
3. `Linux only`
4. `not a sandbox`
5. `the stand-in reactor is synthetic`
6. `the optimization routes need the optional nlp extra`
7. `the CoolProp provider needs the optional coolprop extra`
8. `cost and LCA results are assessment estimates with an accuracy class`
9. `cost and LCA are Python-only`
10. `no ecoinvent data`
11. `Wilson is vapour-liquid only; no liquid-liquid split`
12. `no automatic liquid/vapour regime switching for pure fluids`
13. `X31: one independent reference for the refluxed absorber`
14. `no rate-based column models`
15. `no W27 claim in 0.3.0`
16. `no CFD or Peclet refinement`
17. `no external benchmark score`

0.2.0's "no equilibrium-stage subsystem" is dropped, because S01–S03 built one. If N-1 takes W27, phrase 15 becomes
`the W27 campaign judged 0.3.0's surface`, by amendment.

## 9. Data in the wheel, and MR-12

### 9.1 Wilson (Frank, 2026-10-29, Q-F3: "Ship params + points"; RC-05 and RC-08 settled by Frank)

| File | Ships? |
| --- | --- |
| `benchmarks/s10/records.yaml` (fitted P^sat and Λ; CIAAW molar masses) | **Yes** (package data, R-616's pattern) |
| `benchmarks/s10/vle/kurihara1993_binaries.csv` (Table II, 49 points) | **Yes** |
| `kurihara1993_binaries.{A,B}.csv`, `kurihara1993_ternary{,.A,.B}.csv`, `kurihara1995_binaries{,.A,.B}.csv`, `validation/report.json`, `fit-report.json` | No (RC-06 is unresolved; the double entries and derived reports are repository-only) |
| every other §3 row of `docs/s10-rights-check.md` | unchanged |

NOTICE gains one Wilson block. It meets RC-01 (cite TM-4513), RC-03's three conditions, RC-05 (cite the paper) and
RC-08 (cite CIAAW 2021); the IAPWS block (R-616) already serves RC-04. `docs/attributions/wilson-ig-v1.md` is the
provider's attribution page, after `iapws95-v1.md`. R-811's wheel refusal row is removed ("Reversible by: removing one
registry row"). Bytes stay unchanged, so `data_sha256` does not move.

**What "binds from package data" means (Amendment 1, R-883).** A revision on Wilson's record source selects
`wilson-ig-v2` (S11 units design §4.6, WO-D5), which builds `wilson-ig-v1` from the path it is given. The binder
(`revision_binding.basis_provider`, `_wilson_refusal`) and the verifier (`certificate._wilson_provider`) pass
`resources.packaged_path(wilson_ig.RECORDS_PATH)` (WO-2, D-1 and D-4). So in a wheel, a revision on Wilson's records
binds on the packaged records, and the verifier builds its provider from them. That is the whole of the claim in
V03.A12 and A19, and it is enough.
`thermo/wilson_ig.py` is not edited. Its bytes are pinned by `test_a75_v1_is_not_edited`, its SHA-256 enters both
providers' `implementation_sha256` (v2's chains v1's), and S10's validation verdict names those bytes
(`docs/reviews/S10-validation-verdict-val2.md`, `4bcd8f4dc8115b6b`). An edit would re-open S10's verdict for a library
convenience. The consequence is a library limitation, stated and checkable. `WilsonIdealGasProvider()` and
`WilsonIdealGasProviderV2()` with no argument read a source checkout only, and outside one they refuse
`RecordError("records_missing: …")`, never a fallback (V03.A19 (d)). A library user passes
`resources.packaged_path(wilson_ig.RECORDS_PATH)`. The refusal's text still says the records are read "from a source
checkout only; R-706". That is stale since R-880, and it stays because the message is v1's bytes. The envelope row
L-S11-3 and the attribution page carry the correction (WO-4, texts in §10.4).

### 9.2 E01

The seven files of `docs/e01-data-licences.json` already ship. The five IPCC AR6 GWP-100 values ship as facts with
their citation (Frank, 2026-10-29), and NOTICE gains that citation. QA1's flip is P2.

### 9.3 MR-12 v03 (S07 F-9)

A v03 measure in the M07a evidence script's pattern: every extra new since `v0.2.0` needs an `MR12_AUDITS` entry whose
check passed at C.

- `coolprop`: audit S07 spec §17, inventory `docs/s07-coolprop-licences.json`, decision R-624, check
  `t07_licence_inventory.py --extra coolprop` (G19).
- `lca`: audit E01 design §4.8.4 and WO-B1, inventory `docs/e01-lca-licences.json`, decision R-900, check
  `scripts/e01_d04_inventory.py --check` (E01.A42). *Erratum 2026-10-30 (V03 review, R-900): the decision read R-870 and
  the check had no mode.*

`test_the_git_backed_measure_at_head`'s HEAD clause moves to the v03 measure. The v02 measure stays judged at
`RELEASE_0_2_0_COMMIT`.


### 9.4 Semantic roles (Amendment 1; ADR 0054; R-881, R-882)

**Table R, the role of each model the binder accepts.** Its keys are exactly `revision_binding.MODEL_SIGNATURES`
(30 ids at `98701cca`). Its values cover the thirteen enum values other than `other`, each at least once.

| Model id | Role | Model id | Role |
| --- | --- | --- | --- |
| `c1.adiabatic_mixer` | `mixer` | `syn001.ph_flash` | `flash` |
| `c1.feed_source` | `feed` | `syn001.product_sink` | `product_sink` |
| `c1.product_sink` | `product_sink` | `syn001.stream_splitter` | `splitter` |
| `c1.reactor` | `reactor` | `syn001.tp_flash` | `flash` |
| `c1.reactor_standin` | `reactor` | `syn001.tp_heater` | `heater` |
| `c1.reactor_surrogate` | `reactor` | `syn001.valve` | `valve` |
| `c1.stream_splitter` | `splitter` | `thermal.compressor` | `compressor` |
| `c1.tp_flash` | `flash` | `thermal.flash` | `flash` |
| `c1.tp_heater` | `heater` | `thermal.heater` | `heater` |
| `syn001.adiabatic_mixer` | `mixer` | `thermal.mixer` | `mixer` |
| `syn001.column` | `separator` | `thermal.pump` | `pump` |
| `syn001.component_separator` | `separator` | `thermal.turbine` | `turbine` |
| `syn001.conversion_reactor` | `reactor` | `thermal.valve` | `valve` |
| `syn001.feed_source` | `feed` | `syn001.heat_exchanger` | `heat_exchanger` |
| `syn001.kinetic_cstr` | `reactor` | `syn001.liquid_pump` | `pump` |

Where it comes from. The 23 `c1.*` and `syn001.*` rows are the roles the committed documents already give those
models: over the 80-document corpus at `98701cca`, each of them has exactly one role besides `other`. The five
`thermal.*` rows for flash, heater, mixer, pump and valve take the role of the same kind of unit among those 23. In the
corpus they appear only as `other`. The rows for `thermal.compressor` and `thermal.turbine` are ADR 0054 D1.
`syn001.column` → `separator` is S11 design §4.7.1. The table lives in `tests/semantic_roles.py` as `ROLE_OF_MODEL: Final[Mapping[str, str]]` with `role_of(model) -> str` returning
`ROLE_OF_MODEL[model]`. An unknown model raises `KeyError`, so a new model forces its row (ADR 0054 D5).

**The corpus (V03.A29–A31).** Every file `git ls-files` lists under `benchmarks/`, `examples/`, `tests/` or `docs/`
with suffix `.json`, `.yaml` or `.yml`, that parses (`json.loads`, `yaml.safe_load`) to a mapping holding all of
`schema_version`, `revision_id`, `component_set` and `instances`. Two kinds of file are excluded. First, paths under
`tests/fixtures/` with a segment `invalid`: those are registered schema-invalid fixtures. Second, paths under
`benchmarks/t07/v17/runs/`: those are recorded campaign artifacts, evidence of what agents wrote, never corrected (one
holds `purge_sink`, T07 decisions rf3a). A file that does not parse is not in the corpus. At `98701cca` the corpus is
80 documents (benchmarks/m02 6, m04 1, s11 25, syn001 17, t05 4, t06 23, t08 1; tests/web 3), with 441 instances.

**Measured at `98701cca`** (scratch script, not committed; the assertions are the record):

- `validate`: 71 of 80 give no `SCHEMA-01` FAIL. The nine below FAIL with
  `schema_invalid(/instances/<i>/semantic_role): 'other' is not one of […]`. So A29 would have caught the defect.
- 34 of 441 instances differ from Table R, all `other`, all in the nine.
- With the enum widened in memory and Table R applied: 0 of 80 FAIL. 71 documents are unchanged by the correction. The
  `purge_sink` control FAILs at `/instances/1/semantic_role`.
- The binder's `outcome` is equal for all 80 documents with roles as Table R and with every role `other` (63 bound, 16
  `Unbound` `unsupported`, 1 `Unbound` `incomplete` in that environment). The `efficiency` nudge on GP-M1 changes it,
  as does a `pressure_drop` nudge on SYN-001-nominal.
- No file under `src/` contains `semantic_role`. No committed file contains any of the nine files' SHA-256 or
  `document_sha256`. The served MCP tool list does not contain the enum (digest `455d01eb…` = D_3).
  *Erratum 2026-10-30 (V03 review F-V4): the search missed indirect pins. `tests/test_t07_w5c_signatures.py` pins the
  binding structures of TH-C1, TH-R1 and GP-M1 (through `_structure`), and `revision_sha256` is one of their keys. WO-3
  re-pinned the three in `8c6ddb8a`; the review bound the predecessors and the regenerated documents and found
  `revision_sha256` the only key that differs. A31 (b) exercises little for the 17 corpus documents that come back
  `Unbound` before roles could matter; A31 (a), with the surrogate-bound W5c structures, covers that gap. ADR 0054's
  "no committed record pins" sentence has the same omission.*

**The nine cases and the five builders.** Cases: `benchmarks/s11/gp/GP-C1.json`, `GP-C2.json`, `GP-C3.json`,
`GP-M1.json`, `GP-M2.json` (generator `tests/s11_gp_support.py`) and `benchmarks/s11/thermal/TH-C1.json`, `TH-C2.json`,
`TH-R1.json`, `TH-V1.json` (generator `tests/s11_thermal_support.py`, through `test_s11_thermal_binding.instance`).
Builders: `tests/test_s11_thermal_binding.py` `instance()`, `tests/s11_gp_support.py`, `tests/test_s11_gp_binding.py`,
`tests/test_s11_routing.py` (each `ROLES.get(model, "other")`) and `tests/test_s11_gp_verifier.py` (`roles.get(model,
"other")`). Each builder's role becomes `role_of(model)`, and each local `ROLES`/`roles` map is deleted. The nine files
are regenerated by running their generators, never edited by hand. Their committed-equals-generated tests then hold.
Each regenerated file differs from its predecessor only in `semantic_role` values (checked once by WO-3 and recorded in
`docs/V03_DECISIONS.md`'s run log).

**Identity across the correction.** The correction moves the nine documents' bytes, `document_sha256` and
`revision_sha256`, and the same for documents the five builders make. It moves nothing the binder, solver or verifier
computes (A31). `scripts/s11_identity.py` would report the family C keys of test nodes that bind those documents as
changed, because its digest includes the document's SHA-256. That gate is S11's merge evidence against `8c34ecb0`, it is
not an RC step, and it is not run across the correction as a proof of inertness: by construction it cannot be one. A31
is the proof.

## 10. Work orders

| WO | Lane | What | Depends | Assertions |
| --- | --- | --- | --- | --- |
| WO-1 | Opus | `scripts/v0_3_gate.py` on `v0_2_gate.py`'s engine (registry, line name and spec texts made parameters, v0.2 output byte-identical); `benchmarks/v03/registration.json`; tests in the pattern of `tests/test_m07_v0_2_gate.py`; A10's pairs | this spec | A01–A08, A16 |
| WO-2 | Opus | Wilson ship set as package data; R-811 row removed; NOTICE blocks; `docs/attributions/wilson-ig-v1.md`; rights-check table | — | A12–A14 |
| WO-3 | Opus | MR-12 v03; the RC CoolProp test step (F-8); A48 tripwire at 0 after P2; **Amendment 1:** ADR 0054's roles (§10.3) | E01 merged; P2 for A10 (§10.3 depends on neither) | A10, A11, A15, A28–A31 |
| WO-4 | Sonnet | ADR checks and flips (§6, S07 F-1 transcribed); `## v0.3.0` draft; envelope U02 text (N-8); RELEASING "Per release" for 0.3.0 and the W27 sentence (F-4); **Amendment 1:** L-S11-3 and the attribution page (§10.4) | WO-1–3 | A25 (at C), A18 |
| — | reviewer | one design-lane pass over WO-1–WO-4 before the merge into `main` | WO-1–4 | — |
| WO-5 | Opus | K3 (§5.1); G10 re-take; the journey at K3 in the reactor environment; C | P1–P4 | A09, A21 |
| WO-6 | Opus | the RC job at C, steps 1–17; RC record; tree record; S13 manifest. *V03 review F-V3:* WO-6 owns the producer of step 17c's record `step17/rc-step17c.json` (`checks[].id` = each `MR12_AUDITS_V03` entry's `check` command, `provenance.commit` = C) and the call of `mr12_extras_v03`, which is in the M07a script's `MEASURES` but not in its `SPECS`; a missing record fails the measure (fail-safe). **Amendment 3:** step 12's G11 keep-and-audit at C (§4, A34); A12 (c) judged version-aligned (§7.1); S13's manifest outside the harvest (R-911); §10.5 | WO-5 | A12 (c), A17, A19–A24, A27, A32, A33, A34 |
| WO-7 | verdict (design) | `docs/reviews/V03-verdicts.md` at C | WO-6 | A26 |
| WO-8 | Sonnet | ledger from WO-7; ask Frank the four items and the D3 rows (in plain words, with defaults); record his answers verbatim; then, in §6.1's order (Amendment 4): the generator's R-913 rules, S13's manifest regenerated `tested`, ADRs 0053 and 0054 Accepted on it, step 18, its output in the build log; hand to Frank for the tag | WO-7 | A08 (R), A25, A26, A27 |
| WO-9 | Sonnet | after the tag: §5.3 | the tag | — |

### 10.1 Stops (the engineer reports and does not choose)

The engineer stops on any of these:

- V03.A23 fails.
- Step 9's import workload fails on a v0.3 module (F-3).
- A default-gate test at K3 needs the v1 `coverage.json` re-taken (F-4).
- An ADR condition in §6 is unmet.
- The journey's R1 needs more than its registered budget.
- Any step's result reads `unsupported`. Step 16's check (d) asserts the registered W27-R63 refusal (§3.5). That refusal
  is the check's expected outcome, not an `unsupported` result.
- Step 16's check (d) sees anything but the registered refusal: an exit 0, another error, or a `summary.json`
  (Amendment 2).
- V03.A31 (b) differs for any corpus document. Production code then reads the role after all, and ADR 0054's premise is
  false.
- A regenerated S11 case differs from its predecessor in anything other than `semantic_role` values.
- V03.A34 fails, or step 12's re-run differs from step 12's own runs file (Amendment 3). The records are committed as
  they are, and nothing is re-run to pass.
- A12 (c)'s aligned run (§7.1) finds a changed digest, a failed test outside the five registered readers, or a failed
  base shard (Amendment 3).
- §6.1 step 2's manifest is not `tested`. No ADR is marked Accepted, and step 18 is not run for YES (Amendment 4).
- Step 18 at §6.1 step 4 ends in anything but `v0.3.0 tag may be proposed: YES`, or H2 to H3 touches a file other
  than `docs/V03_RC_DECISIONS.md` and `docs/progress.md`. Nothing is edited to pass, the manifest is not regenerated to pass, and the reasons are reported (Amendment 4).

### 10.3 WO-3, Amendment 1: the roles (one engineer, before the rest of WO-3)

1. `schemas/process-revision.schema.json`: append `"compressor"`, `"turbine"`, `"other"` after `"heat_exchanger"` in
   the `semantic_role` enum, in the file's existing format, and change nothing else (V03.A28).
2. `tests/semantic_roles.py`: `ROLE_OF_MODEL` = Table R and `role_of` (§9.4).
3. The five builders of §9.4 take `role_of(model)`, and their local maps are deleted. Then run
   `python tests/s11_gp_support.py` and `python tests/s11_thermal_support.py` (each module's `__main__` writes its cases), and
   check that each of the nine files differs only in `semantic_role` values.
4. `tests/test_v03_semantic_roles.py`: V03.A28–A31 with their controls.
5. Steps 1–4 are **one commit** (`V03 WO-3 (ADR 0054): …`). The schema without the corrections, or the corrections
   without the schema, leaves the corpus invalid. Reversible by reverting that commit.
6. A second commit: `0054` appended to `required_adrs` in `scripts/v0_3_gate.py` and `benchmarks/v03/registration.json`.
   In `tests/test_v03_v0_3_gate.py`, `test_a01_the_entry_is_the_specification_s_table` reads the label
   `required_adrs (25)` and expects length 25. It fails from this amendment's commit until this commit lands, on purpose
   (the document leads; measured: 1 failed, 91 passed over the two V03 modules).
7. `docs/interfaces-frozen.md` already carries ADR 0054's paragraph (this amendment's commit).
8. Run the touched modules: `test_v03_semantic_roles.py`, `test_v03_v0_3_gate.py`, every `tests/test_s11_*.py`, and
   `test_t08_w4_package_data.py`, `test_schemas_p01.py`, `test_m06_fixtures_valid.py`, `test_m07a_surface_chain.py` (the
   served digest). Record the counts in `docs/V03_DECISIONS.md`'s run log. Do not run `scripts/s11_identity.py` as proof of
   this commit (§9.4).
9. Merge note: if `wp/DOC` is on `main` before V03 merges, V03.A30 (c) names DOC's examples that label
   `thermal.turbine` or `thermal.compressor` `pump`. The merge sets them by Table R, roles only.

### 10.4 WO-4, Amendment 1: the Wilson library limitation in words

- `benchmarks/t08/support_envelope.yaml` row L-S11-3. Replace the sentence "Its records are in the source repository
  only, so in a wheel binding is refused `basis_unavailable(wilson-ig-v2)` (R-706, R-811)." with "Its records ship as
  package data (R-880), so it binds in a wheel. An installation with neither copy is refused
  `basis_unavailable(wilson-ig-v2)`. The library constructors `WilsonIdealGasProvider()` and
  `WilsonIdealGasProviderV2()` with no argument read a source checkout only and elsewhere refuse `records_missing`. A
  library user passes `resources.packaged_path(wilson_ig.RECORDS_PATH)` (R-883)." Add the evidence nodes
  `tests/test_v03_wilson_ship.py::test_a12_r_811_s_wheel_refusal_is_gone` and
  `tests/test_v03_wilson_ship.py::test_a12_wilson_ig_v1_binds_from_package_data`. The crosswalk entry's note for L-S11-3
  reads `S11's envelope row L-S11-3, amended by V03 (R-883)`. Re-emit `docs/support-matrix.md` with
  `scripts/t08_support_matrix.py --emit`, and check with `--check` (T08.A23). This is done with WO-2's deferred L40/L-S11-3
  edit, after E01's merge.
- `docs/attributions/wilson-ig-v1.md` gains a section "Using the provider from the library" with the same three facts:
  the records are package data; the no-argument constructors read a checkout only and otherwise refuse
  `records_missing`, whose text still says "source checkout only" (v1's bytes are pinned, R-883); and the call
  `WilsonIdealGasProvider(resources.packaged_path(wilson_ig.RECORDS_PATH))`.

### 10.2 What the `verdict` agent receives (WO-7)

The brief carries:

- C, K3, and the registry entry (§2.2).
- The criteria: alpha §5–§6 (V11–W22), M07 §7.3 (W23–W26, with W26 (a) as §3.5 here restates it) and §3.2 here (X31).
- The RC record and S13's manifest, with each step's summary line and its record path.
- The step 8 chain rows and the step 15 carry lines.
- `docs/reviews/S09-verdicts.md` verdict 3, and 0.2.0's `docs/reviews/V02-verdicts.md` for comparison.
- For W21 (e) at its next judgement (Amendment 3, R-909): V03.A34's record, the files under `step12/experiments/`, step
  12's own runs file and its commit `3b05511d`. (e) is met if and only if R-909's four conditions hold.

It returns 17 rows in the alpha §6.3 form: verdict, failing clauses (or `—`), and travelling limitations. It judges
nothing that §3 pre-registers differently.

### 10.5 Amendment 3: the build lane's work at C (no re-cut)

1. Step 12's G11 results (§4). The record's checks are V03.A34's.
2. `scripts/s13_evidence_manifest.py` gets a rule for V03.A34. The rule reads `step12/experiments/rc-step12-experiments.json`
   from `rc/records.json`, re-hashes it, reads it with T08's `_record`, and requires exactly A34's three check ids, as
   A32's rule does for step 16. A12 (c) is decided as §7.1 states. `scripts/s11_identity.py` is not edited.
3. `scripts/t08_support_matrix.py` sets `HARVEST_EXCLUDED = ("evidence/S13/",)`, naming R-911 in its comment. In
   `tests/test_m07a_harvest.py`, `test_c4_the_post_0_2_0_harvest_reads_m07a_and_m07` expects that tuple. A new test
   asserts three things: C's tree holds no file under `evidence/S13/`; every manifest the exclusion removes is
   `evidence/S13/<40 hex>/manifest.json`; and S13a's manifest
   (`evidence/S13a/0ce3748a7a473950a295e2668201fb96c44d0ec1/manifest.json`) is still harvested. `HARVEST_SIZE` and
   T08.A21's test do not change.
4. S13's manifest carries these three limitations verbatim, beside anything else it states:
   - `Not harvested into v0.3-envelope-1. This manifest is written after C, and classifying its items would change benchmarks/t08/support_envelope.yaml, a D2.4 path. scripts/t08_support_matrix.py excludes evidence/S13/, as R-485 excluded M07's manifest from 0.2.0's harvest; the next envelope's package harvests it (R-911).`
   - `V03.A12 (c) is judged version-aligned (V03 spec §7.1, R-910). The registered identity run differs from its base only in family-C digests, through the version string; with the version held equal, no digest differs. This shows that no binding outcome changed. It does not make the version string inert: the experiment fingerprint carries it by design (R-458).`
   - `L-S11-1, L-S11-2, L-S11-3 and L-E01-1, and W26's sentence "G14 not judged at 0.3.0", travel in the prose of docs/reviews/V03-verdicts.md and in the envelope, not in the verdict table's limitation column, whose grammar (v0_2_gate.LIMITATION) cannot carry them (R-912).`
5. Controls run before the generator change is committed, recorded in `docs/V03_RC_DECISIONS.md`.
   - **A12 (c).** §7.1's decision is written as a pure function over V_C, V_B, R0's and R1's exit codes and last lines,
     the numstat output and the failed node ids. It passes on a PASS-shaped R0 with exit 0, whatever else it is given.
     It passes on the lines measured at C: `evidence/S13/<C>/artifacts/V03.A12c.log`,
     `~/.cache/v03rc-a12-tmp/identity-cf2.log` and the five failed ids in `~/.cache/v03rc-a12-keep/branch/`. It fails
     on each of these: R0 whose first changed key starts `A:`; R0 whose parenthesis also names a failed shard; R1 with
     a changed key; R1 naming a failed base shard; n(R1) = n(R0) + 1; a sixth failed id; four of the five; a numstat
     of two lines; and V_C = V_B with R0 failing.
   - **A34.** The A34 rule fails on a copy of the record with one check `fail`, on a copy with a fourth check, and on a
     `records.json` without the record. It passes on the committed record.
   - **Harvest.** With S13's manifest present, `tests/test_m07a_harvest.py` and the A21 test of
     `tests/test_t08_w2_support_envelope.py` pass with the exclusion and fail with `HARVEST_EXCLUDED = ()`.
     `scripts/t08_support_matrix.py --check` passes with the exclusion.
6. Then the work proceeds in the order the verdict's Sequencing gives: W21's new judgement (WO-7, with a new `Judged`
   date); then Frank's message (N-2 to N-6, and N-11); then one re-judgement line for V13, V17, W21 and W24.

## 11. Open items (each with a default; work proceeds on the default)

| # | Question | Needs | Default | When |
| --- | --- | --- | --- | --- |
| N-1 | Claim W27 with a new campaign under registration v3 (USD 15–45, about a day, a C_W before C)? | Frank's preference | **No: W27 not claimed** | before K3 |
| N-2 | Carry V17's agent evidence (no new link at C)? | Frank | **Carry** (alternative: about USD 10, one hour) | after the verdict |
| N-3 | M02 N1: ship the reactor child process labelled "not a sandbox"? | Frank | **Yes** | after the verdict |
| N-4 | M03 N1: accept the `nlp` extra's licences? | Frank | **Yes** | after the verdict |
| N-5 | D3 `X31 (c)`: release with "met where available, 3 of 4"? | Frank | **Accept** (S03 Q-A2-4's default) | after the verdict |
| N-6 | D3 `V14 (b)`: accept the PTC failure again? | Frank | **Accept** | after the verdict |
| N-7 | Working form after the tag: keep the token, or D1-O2's version-free id? | Frank's preference | **Keep the token** (§5.3) | before the tag |
| N-8 | S04-O2: correct U02's stale capability text ("any property method other than SYN-001") at K3? | Frank's preference | **Correct it** to name the bases 0.3.0 binds | before K3 |
| N-9 | Keep `other` in the role enum (ADR 0054 D1)? Removing a value after 0.3.0 ships is a narrowing that can invalidate user documents, so the cheap time to decide is before K3 | Frank's preference | **Keep it** (his standing "as few limitations as possible"). Alternative: `compressor` and `turbine` only, with `other` dropped from the ADR, A28 and A30 (b) | before K3 |
| N-10 | W26 at 0.3.0. Option 1: judge the web-shell checks and the W27 scorer's twenty stub cases, and record that W27's old registration refuses this build (§3.5). Option 2: judge M06 G1–G15 literally | Frank's preference | **Option 1, §3.5's reading** (W26 (a) PASS iff A32 holds). Alternative: W26 (a) FAIL on G14 and G15, releasable only with a D3 row `W26 (a)` (an ADR 0053 amendment) | next message to Frank; WO-6 and WO-7 proceed on the default |
| N-11 | Accept the licence decisions of the two new extras? `coolprop`: R-624 (CoolProp is MIT; its numpy as under R-135). `lca`: R-900 (WO-B1/D04's audit of the pinned Brightway lock). The alpha's MR-12 asks for Frank's recorded decision, and V18 was judged on §9.3's registration of R-624 and R-900 (verdict finding F4) | Frank's preference | **Accept** (V18 stays PASS). A decline needs a spec amendment, and V18 (a) is then judged again on MR-12's decision leg. The answer is recorded verbatim here, not in ADR 0053's tables | with N-2 to N-6, after W21's new judgement |
| N-12 | Widen the gate's limitation grammar so that L-S11-1…3 and L-E01-1 can stand in the verdict table (verdict finding F5)? | design lane, at the next release | **Not for 0.3.0** (R-912). They travel in the verdict's prose, the envelope and S13's manifest. The next release adopts R-912's pattern | the next release's spec |
| F-1 | Is the served digest at C equal to D_3? | fact: step 8 | yes (R-860) | at C |
| F-2 | Does the journey at K3 fit its registered budget? | fact: WO-5 | yes, as at 0.2.0 | at K3 |
| F-3 | Do S11's and E01's modules import in step 9's default-install workload? | fact: step 9 | yes (`test_package_imports` lists `assessment`) | at C |
| F-4 | Does any default-gate test need W27's v1 `coverage.json` at the new version? | fact: step 1 at K3 | no (R-566 dropped the byte pin). *Measured (Amendment 2):* yes, twice. Each time a check compared the committed snapshot's `package_version`: `test_committed_coverage_json_is_g14_…` at K3 (R-902), and S11's S4 check at `4fa15efa` (R-904). Both now exclude it as build provenance | at K3 |
| F-5 | Does A12 (c)'s aligned run (§7.1) find no changed digest, at the same n as R0, and fail exactly the five registered readers at the judged commit? | fact: the S13 generator's R1 | yes (the counterfactual at C) | at the generator's run |
| F-6 | Does A34 hold at C, with the re-run equal to step 12's runs file at all 242 point-runs and 210 results audited with 0 problems? | fact: §4's re-run | yes, as at 0.2.0 with byte-identical producing code | before W21's new judgement |
| F-7 | Does S13's manifest, regenerated at §6.1 step 2, come out `tested` with all 48 checks `pass`? That means the five checks the loop held (A08, A25, A27, ADR.0053, ADR.0054) and the 43 that passed in `4ecfc162` | fact: §6.1 step 2 | yes. `4ecfc162`'s 43 passes were measured on the same evidence, Frank's six cells read `accepted, 2026-10-30`, and the dry run at `2b7fc98e` found no other reason | WO-8 (Amendment 4) |
| F-8 | Does step 18 at §6.1 step 4 end in `v0.3.0 tag may be proposed: YES`? | fact: §6.1 step 4 | yes. The dry run at `2b7fc98e` gave `NO (3 reasons)`, exactly the manifest's status and the two ADR lines, and steps 2 and 3 change those | WO-8 (Amendment 4) |

Ask N-1, N-7 and N-8 in one message now, and N-2 to N-6 in one message after the verdict, as 0.2.0 did. N-9 (Amendment
1) rides on the next message to Frank before K3; work proceeds on its default. N-10 (Amendment 2) rides on the next
message to Frank, and work proceeds on its default. N-11 (Amendment 3) rides in the message that asks N-2 to N-6, after
W21's new judgement, and work proceeds on its default. N-12 asks Frank nothing.

**Frank's answers to N-10 and N-11 (2026-10-30, after W21's new judgement; verbatim).** N-10: "Judge as planned
(Recommended)" — Option 1, §3.5's reading. N-11: "Accept (Recommended)" — R-624 and R-900 accepted; V18 stays PASS. N-2
to N-6 and N-1's re-confirmation are recorded in ADR 0053's tables.

**Answered, Frank, 2026-10-29:** N-1 "No, don't claim it (Rec.)" (W27 not claimed); N-7 "Keep the token (Rec.)"; N-8
"Correct it (Rec.)". N-2 to N-6 remain for after the verdict. N-9 (Frank, 2026-10-30): "Keep 'other' (Rec.)".

## 12. What this specification does not establish

- It records no verdict. Every gate's verdict is WO-7's, at C, on evidence that does not exist yet.
- No empirical validation beyond what packages registered. S10's VAL bands, the column references, and E01's
  hand-computed checks are each package's own evidence. Cost and LCA are assessment estimates, and they are not
  validated against plant or audited LCA data.
- No optimality evidence of any kind.
- X31 "met where available" is not "met with two references". RC4 has one independent check.
- No W27 result for 0.3.0. 0.2.0's W27 verdict describes 0.2.0's surface only.
- W26 at 0.3.0 does not establish that the W27 harness is ready to run a campaign on this build. G14, P3 and the stub
  campaign need a coverage of this build, and registration version 1 refuses to build one (§3.5). The G15 states are
  scored against 0.2.0's committed rows. They test the scorer's and the harness's logic at C, not this build's coverage.
- A33 shows that, at C, selecting the modules that contain `mark.nlp` loses no `nlp` node. It does not show that a
  source marker is the only way a test can become `nlp`. A later conftest hook that adds the marker would need A33
  re-measured.
- The QA1 range values are not checked here. They come from P2, a separate Frank-approved commit.
- No legal opinion. The rights readings are technical (R-715). The ship decisions are Frank's.
- No human numerical or process-modelling sign-off. That is Frank's, recorded separately.
- None of these facts is re-established: any number this document quotes from another record (R-627, R-845, CI runs,
  S09 verdict 3). Each is re-measured at C where an assertion says so.
- Table R is a repository convention checked by tests, not a validation rule. A user document is constrained by the
  schema alone, and `validate` does not compare a role with its model (ADR 0054 D4).
- The thirteen named roles are not a taxonomy of process units. They are the roles of the units this build binds, plus
  `other`.
- No inertness proof by the S11 identity gate across the role correction. Its family C differs there in document
  digests by construction, and A31 is the proof (§9.4).
- The no-argument Wilson constructors do not read package data, and their `records_missing` text stays stale (§9.1,
  R-883). The envelope and the attribution page carry the correction.
- A34 shows two things: the experiment records of a re-run of G11 at C carry blueprint §9.1's six items, and the
  re-run's per-point outcomes equal step 12's own record. It audits fields and their bindings, not physics. Nothing in
  it shows that the reactor is right (L46).
- A12 (c) at a version cut (§7.1) shows that, with the version string held equal, C binds every document of the suite
  exactly as the base does. It does not show that the version string is inert. The experiment fingerprint carries it
  by design (R-458), and that is what R0's differences are.
- S13's own manifest is not in `v0.3-envelope-1`'s harvest (R-911). Its limitations reach an envelope only at the next
  release.
- S13's manifest does not establish step 18's YES, gate item 12 in full (A25 (b)) or A08's R part. These come from
  step 18's log at WO-8. Step 18 reads the manifest, so it runs after it (§6.1). The manifest's ADR.0053 and ADR.0054
  checks judge those ADRs' conditions other than the manifest's own status. They do not establish that either ADR is
  Accepted. A26's ledger clause is judged by step 18's item 3 and `tests/test_v03_ledger.py`, not by the manifest
  (Amendment 4).
