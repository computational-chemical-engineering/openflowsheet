# V03 — the 0.3.0 release specification

**Authority.** Design lane (`specifier`), package V03 (manifest id `S13`, R-878). Policy: ADR 0053 (Proposed). Brief:
`docs/briefs/V03-release-policy.md`. Builds on ADR 0042 and `docs/derivations/M07-spec.md` §7–§13; on ADR 0028 and
`docs/derivations/V02-alpha-release-spec.md` §4–§8; and on `docs/RELEASING.md`. Register: R-872…R-880. Facts quoted
here were measured at `main` = `a1b50ccf` and `wp/E01` = `84d71df8` unless stated otherwise.

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
6. Assertions V03.A01–A27 (§7), work orders (§10), the `verdict` agent's inputs (§10.2), and open items with defaults
   (§11).

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
| required_adrs (24) | 0022, 0026, 0027, 0030, 0031, 0032, 0033, 0034, 0035, 0036, 0037, 0038, 0039, 0041, 0044, 0045, 0046, 0047, 0048, 0049, 0050, 0051, 0052, 0053 |
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
- W23–W26: M07 §7.3.
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
step 15 therefore re-runs the journey at the cut commit K3, under M07 §4–§6 and the registration's budgets unchanged.
R3 carries M05's REAL record only if `carry.r3_files` are byte-equal between M05's run commit and K3. Otherwise R3
re-runs M05's study at K3. The record is committed in C's tree, carried from K3 to C by `--carry-journey K3 --rc C`,
and passes `check` and `replay` at C. This needs workstation compute (the reactor environment) and no money. Honest
outcomes (`BUDGET_EXHAUSTED`, `INCOMPLETE`) are recorded as M07 §5 states. Their verdict is the agent's.

## 4. The release candidate C and the RC job

**K3 and C.**

- **K3** is the cut commit on `main` that declares `0.3.0` and pins the envelope (§5.1).
- **C** is K3 plus commits outside the D2.4 paths. Those commits hold the journey record of K3, the RC records,
  `release/rc-trees/<C>.json` (R-151), `evidence/S13/<C>/manifest.json`, the verdicts, the ledger and
  `CHANGELOG.md` `## v0.3.0`.
- C is merged into `main` with a merge commit. From K3 until Frank's dispatch, `main` takes no D2.4 change (RELEASING
  "Pre-releases" step 2).

**Preconditions at K3.**

- (P1) E01 is merged.
- (P2) Frank has approved the commit that sets every shipped `primary` range `verified: true`, and it is on `main`.
  That is QA1 against Seider et al., 4th ed., Table 16.32, a separate work item. The commit, or a later one, sets
  `test_e01_a48_tripwire`'s count to 0.
- (P3) WO-1 to WO-4 are merged, after the full gate and CI on both architectures.
- (P4) N-1, N-7 and N-8 are answered, or their defaults stand.

| Step | What, at C unless stated | Assertion |
| --- | --- | --- |
| 1–12 | the alpha spec §8.2 steps 1–12, read as in M07 §8 (step 1's four ledger skips as [A6]; step 9 and step 12 as [A7]) | V03.A20 |
| 13 | W23 as M07 step 13 | V03.A20 |
| 14 | W24 as M07 step 14. The five in-process G10 records are re-taken at K3 and proved with `scripts/m05_retake_diff.py --digest-only` (R-458) | V03.A20 |
| 15 | W25 per §3.4: journey at K3, carried to C, `check` and `replay` at C | V03.A21 |
| 16 | W26 as M07 step 16 (G1–G15; the browser test on CI x86-64) | V03.A20 |
| 17 | v0.3 package items 17a–17e below | V03.A22 |
| 18 | `scripts/v0_3_gate.py --rc C`, not required in the record; run for its YES line only after the ledger is written | V03.A27 |

- **17a.** E01 G10: `e01_evidence_manifest.a48_release_check()` returns `("pass", {"unverified_primary_ranges": 0, …})`.
- **17b.** S07 F-8: with `requirements-coolprop.lock` installed after the main lock (`--no-deps --require-hashes`) and
  `OPENFLOWSHEET_REQUIRE_COOLPROP=1`, every S07 and S11 test module that imports CoolProp passes, with 0 skipped.
- **17c.** MR-12 v03 (§9.3): `pass`, with `new_since_v0_2_0 == ["coolprop", "lca"]`, and each entry's check is `pass`
  at C.
- **17d.** E01's opt-in tiers at C: G5's A24 and A25 in the `lca` environment (`scripts/build-lca-env.sh`), and G6's
  A33–A36 in the audited `nlp` environment.
- **17e.** The wheel: built from C by `scripts/t08_dist.py` (T08.A43) and inspected (V03.A17). In a fresh venv
  installed from it, V03.A19.

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
| 0053 | §ADR status line | Frank's tables; S13 manifest `tested` | Accepted at WO-8 |

## 7. Assertions

Gate column: **D** is the default gate (`scripts/gate.sh`), **R** is the RC job or the records at C, and **CI** is both
CI architectures at C. "Exact" means string, byte or set equality. No assertion here compares a floating-point value
except A19 and A24. Their tolerances are the registered ones cited.

| Id | Assertion | Expected | Tolerance and why | Gate |
| --- | --- | --- | --- | --- |
| V03.A01 | `scripts/v0_3_gate.py`'s registry has exactly one entry; its fields equal §2.2 and `registration.json` `gate_set` | equal | exact | D |
| V03.A02 | `gate_set_of` over Table T-V3 | 4 covered, 13 not covered (17 rows) | exact | D |
| V03.A03 | the v0.2 engine is unchanged. `tests/test_m07a_v0_2_gate.py` and `tests/test_m07_v0_2_gate.py` pass, and their nodes are unchanged except A04's; AM-07 holds (the alpha's `--markdown` output byte-identical); both v0.2 entries equal `benchmarks/m07/registration.json` `gate.gate_sets` | pass | exact (`ast.dump`, bytes) | D |
| V03.A04 | `test_a10_…`'s loop tuple = tagged + `A10_PINS_0_2_0` + `A10_PINS_0_3_0` (§5.2); a control with the pairs swapped fails `test_a31_b_…` | equal; control fails | exact | D |
| V03.A05 | clause grammar. Under v0.3's: `V11 (a)`, `V20 (c)`, `W21 (f)`, `W26 (b)`, `X31 (c)` parse; `W27 (a)`, `W28 (a)`, `V10 (a)`, `X32 (a)`, `X31 (A)` do not. Under `v0.2-gate-v1`'s: `X31 (c)` does not, `W27 (a)` does | 5 / 5 / 2 | exact | D |
| V03.A06 | decision items 1–12 for `v0.3-gate-v1`: one YES fixture; for each item one NO fixture flipping only it | 1 YES, 12 NO, each with its reason | exact | D |
| V03.A07 | X31 FAIL (c) without a D3 row → NO; with a row dated on `Judged` → YES; dated the day before → NO. A verdict document with a W27 row → exit 2 | 2 NO, 1 YES, exit 2 | exact (dates are days) | D |
| V03.A08 | output: the §2.2 first line; 18 gate rows, the 17 claimed in order and then W27 `not claimed (v0.3-gate-v1)`; last line `v0.3.0 tag may be proposed: YES` or `… NO (k reasons)` | grammar | exact | D, R |
| V03.A09 | at K3 and C: the five version-carrying files read `0.3.0`; the envelope `v0.3-envelope-1` / `0.3.0` | as stated | exact | R |
| V03.A10 | `test_e01_a48_tripwire`: count 0 after P2; `a48_release_check()` is `pass`; its synthetic unverified document still gives `fail` | 0; pass; fail | exact count (an accidental 0 is excluded by the `fail` control) | D |
| V03.A11 | MR-12 v03 (§9.3) at HEAD: `new_since_v0_2_0 == ["coolprop", "lca"]`, both with entries; a control extra without an entry → `fail`; `mr12_extras_v02` at `RELEASE_0_2_0_COMMIT` unchanged (S07 A44's release clause) | pass; fail; unchanged | exact | D |
| V03.A12 | the ship set (§9.1) is in `PACKAGED` with `_data` links, bytes equal to the `benchmarks/s10/` files; R-811's wheel row is gone. A bind of `wilson-ig-v1` from package data with the checkout path hidden succeeds, and S10/S11 identity tests are unchanged | as stated | exact (SHA-256) | D |
| V03.A13 | NOTICE holds the Wilson block (each of `Kurihara`, `J. Chem. Eng. Data 38 (1993) 446`, `NASA TM-4513`, `CoolProp 8.0.0`, `deReuck-BOOK-1993`, `Schroeder-JPCRD-2014`, `Wagner-JPCRD-2002`, `CIAAW`) and the IPCC block (`IPCC AR6 WG1`, `Table 7.15`), each once | 10 substrings | exact substring | D |
| V03.A14 | `docs/s10-rights-check.md` §3 "Ships?" column equals §9.1's table; RC-05 and RC-08 cite Frank 2026-10-29 | equal | exact | D |
| V03.A15 | the RC test step (WO-3) installs `requirements-coolprop.lock` after the main lock and sets `OPENFLOWSHEET_REQUIRE_COOLPROP=1` (read from the script) | present | exact | D |
| V03.A16 | `registration.json` `changelog_what_it_is_not` equals §8's 17 phrases | equal | exact | D |
| V03.A17 | the wheel at C: each §9.1 ship-set file once, with the repository SHA-256; E01's seven data files with `docs/e01-data-licences.json`'s SHA-256; no §9.1 repository-only file | as stated | exact | R |
| V03.A18 | `CHANGELOG.md` `## v0.3.0` holds §8's 17 phrases verbatim | 17 | exact substring | R |
| V03.A19 | in a fresh venv from the wheel: `wilson-ig-v1` binds; S10's P1 state's γ and K equal the checkout's at C | equal | bitwise (same code, data bytes and machine; x86-64) | R |
| V03.A20 | RC steps 1–14 and 16 pass at C; `docs/v03-rc-record.md` has a passed row for each of 1–17 | pass | per-step gates | R |
| V03.A21 | step 15: K3's journey record is in C; `--carry-journey K3 --rc C` reports carried; `check` and `replay` (bitwise) pass at C | pass | bytes | R |
| V03.A22 | step 17a–17e pass at C; an `unsupported` result is not a pass | pass | as each | R |
| V03.A23 | step 8: served digest D_3 and chain rows as §3.3; otherwise STOP | equal | exact (SHA-256) | R |
| V03.A24 | CI green at C on both architectures. S07 A31: x86-64 bitwise, aarch64 within R-627's classes. S11 thermal check: x86-64 bitwise, aarch64 within R-843/R-845 classes (flash class at the S11 merge: 0.024 of its bound), and the relative class's worst ≤ 0.1 of its bound (R-845's watch). THM-09/4's lines copied into `docs/t07-measurements.md` (R-796) | green; ratios recorded | registered classes; the 0.1 watch is R-845's, not new | CI |
| V03.A25 | gate item 12 at C: the 24 required ADRs Accepted; 0043 Proposed and not required | as stated | exact | R |
| V03.A26 | `docs/reviews/V03-verdicts.md`: header names C once and one `Judged`; 17 rows in claimed order; every clause parses under v0.3's grammar. ADR 0053's two tables pass the cell rule. `docs/requirements.yaml` X31 verdict and evidence written from it | as stated | exact | R |
| V03.A27 | `evidence/S13/<C>/manifest.json` `tested`, listing V03.A01–A26 with commands run and `S11.G8`, `S12.G8`, `S12.G10`; step 18's last line `v0.3.0 tag may be proposed: YES` | present; YES | exact | R |

**Falsifiability.** A06 and A07 flip one input at a time, so a dropped item or a mis-dated cell changes the answer.
A10's `fail` control excludes a vacuous 0. A11's control excludes a measure that passes with no entries. A04's swapped
control excludes an order-blind comparison.

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

### 9.2 E01

The seven files of `docs/e01-data-licences.json` already ship. The five IPCC AR6 GWP-100 values ship as facts with
their citation (Frank, 2026-10-29), and NOTICE gains that citation. QA1's flip is P2.

### 9.3 MR-12 v03 (S07 F-9)

A v03 measure in the M07a evidence script's pattern: every extra new since `v0.2.0` needs an `MR12_AUDITS` entry whose
check passed at C.

- `coolprop`: audit S07 spec §17, inventory `docs/s07-coolprop-licences.json`, decision R-624, check
  `t07_licence_inventory.py --extra coolprop` (G19).
- `lca`: audit E01 design §4.8.4 and WO-B1, inventory `docs/e01-lca-licences.json`, decision R-870, check
  `scripts/e01_d04_inventory.py`.

`test_the_git_backed_measure_at_head`'s HEAD clause moves to the v03 measure. The v02 measure stays judged at
`RELEASE_0_2_0_COMMIT`.

## 10. Work orders

| WO | Lane | What | Depends | Assertions |
| --- | --- | --- | --- | --- |
| WO-1 | Opus | `scripts/v0_3_gate.py` on `v0_2_gate.py`'s engine (registry, line name and spec texts made parameters, v0.2 output byte-identical); `benchmarks/v03/registration.json`; tests in the pattern of `tests/test_m07_v0_2_gate.py`; A10's pairs | this spec | A01–A08, A16 |
| WO-2 | Opus | Wilson ship set as package data; R-811 row removed; NOTICE blocks; `docs/attributions/wilson-ig-v1.md`; rights-check table | — | A12–A14 |
| WO-3 | Opus | MR-12 v03; the RC CoolProp test step (F-8); A48 tripwire at 0 after P2 | E01 merged; P2 for A10 | A10, A11, A15 |
| WO-4 | Sonnet | ADR checks and flips (§6, S07 F-1 transcribed); `## v0.3.0` draft; envelope U02 text (N-8); RELEASING "Per release" for 0.3.0 and the W27 sentence (F-4) | WO-1–3 | A25 (at C), A18 |
| — | reviewer | one design-lane pass over WO-1–WO-4 before the merge into `main` | WO-1–4 | — |
| WO-5 | Opus | K3 (§5.1); G10 re-take; the journey at K3 in the reactor environment; C | P1–P4 | A09, A21 |
| WO-6 | Opus | the RC job at C, steps 1–17; RC record; tree record; S13 manifest | WO-5 | A17, A19–A24, A27 |
| WO-7 | verdict (design) | `docs/reviews/V03-verdicts.md` at C | WO-6 | A26 |
| WO-8 | Sonnet | ledger from WO-7; ask Frank the four items and the D3 rows (in plain words, with defaults); record his answers verbatim; step 18; ADR 0053 Accepted; hand to Frank for the tag | WO-7 | A26, A27 |
| WO-9 | Sonnet | after the tag: §5.3 | the tag | — |

### 10.1 Stops (the engineer reports and does not choose)

The engineer stops on any of these:

- V03.A23 fails.
- Step 9's import workload fails on a v0.3 module (F-3).
- A default-gate test at K3 needs the v1 `coverage.json` re-taken (F-4).
- An ADR condition in §6 is unmet.
- The journey's R1 needs more than its registered budget.
- Any step's result reads `unsupported`.

### 10.2 What the `verdict` agent receives (WO-7)

The brief carries:

- C, K3, and the registry entry (§2.2).
- The criteria: alpha §5–§6 (V11–W22), M07 §7.3 (W23–W26) and §3.2 here (X31).
- The RC record and S13's manifest, with each step's summary line and its record path.
- The step 8 chain rows and the step 15 carry lines.
- `docs/reviews/S09-verdicts.md` verdict 3, and 0.2.0's `docs/reviews/V02-verdicts.md` for comparison.

It returns 17 rows in the alpha §6.3 form: verdict, failing clauses (or `—`), and travelling limitations. It judges
nothing that §3 pre-registers differently.

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
| F-1 | Is the served digest at C equal to D_3? | fact: step 8 | yes (R-860) | at C |
| F-2 | Does the journey at K3 fit its registered budget? | fact: WO-5 | yes, as at 0.2.0 | at K3 |
| F-3 | Do S11's and E01's modules import in step 9's default-install workload? | fact: step 9 | yes (`test_package_imports` lists `assessment`) | at C |
| F-4 | Does any default-gate test need W27's v1 `coverage.json` at the new version? | fact: step 1 at K3 | no (R-566 dropped the byte pin) | at K3 |

Ask N-1, N-7 and N-8 in one message now, and N-2 to N-6 in one message after the verdict, as 0.2.0 did.

## 12. What this specification does not establish

- It records no verdict. Every gate's verdict is WO-7's, at C, on evidence that does not exist yet.
- No empirical validation beyond what packages registered. S10's VAL bands, the column references, and E01's
  hand-computed checks are each package's own evidence. Cost and LCA are assessment estimates, and they are not
  validated against plant or audited LCA data.
- No optimality evidence of any kind.
- X31 "met where available" is not "met with two references". RC4 has one independent check.
- No W27 result for 0.3.0. 0.2.0's W27 verdict describes 0.2.0's surface only.
- The QA1 range values are not checked here. They come from P2, a separate Frank-approved commit.
- No legal opinion. The rights readings are technical (R-715). The ship decisions are Frank's.
- No human numerical or process-modelling sign-off. That is Frank's, recorded separately.
- None of these facts is re-established: any number this document quotes from another record (R-627, R-845, CI runs,
  S09 verdict 3). Each is re-measured at C where an assertion says so.
